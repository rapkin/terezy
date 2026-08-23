"""The coverage table, enumerated by hand. **SC-001, SC-002, SC-012.**

*"For a hand-declared registry of two streams, three destinations and a deliberate mix of
holes, every ``(destination x stream x regime)`` verdict matches a hand-enumerated coverage
table checked in beside the assertion, and no pair in the declared universe is absent from the
report."*

The registry is declared **in this file**, and so is the expected table. A worked example that
reached for a shared fixture would make a reader open two files to check one verdict, which is
the whole thing a worked example exists to prevent -- so ``tests/coverage_registries.py``
serves every other coverage suite and not this one.

⚙ **Seven destinations, not SC-001's three.** Three is one short of what the spec's own edge
cases need and four short of what the matching rule needs. The two-hop way out (SC-011) needs a
destination whose exit lands at *another* destination that is itself spendable-reachable; the
satisfied-by-arrival and satisfied-by-identity cases need an arrival venue with no way out and a
destination that is the spendable endpoint; and the endpoint rule below needs a route with an
**interior**. The table is the whole declared universe either way, which is the property SC-001
is actually about.

## The registry, in words before it is in code

Seven venues, each holding one currency, so the destination universe is seven:

| venue | holds | what it is here for |
|---|---|---|
| ``broker`` | USD | a destination with a declared, spendable way out |
| ``fund`` | UAH | reachable from the salary, and nothing leaves it -- deficit 2 |
| ``hop_uah`` | UAH | an interior leg endpoint: a destination no route declares |
| ``hop_usd`` | USD | the same, on the other side of the conversion |
| ``mono`` | UAH | the salary's arrival point, **and** the one declared spendable endpoint |
| ``pocket`` | USD | the contract income's arrival point, with no way out declared |
| ``vault`` | USD | reachable from the salary; its only exit lands at ``broker`` -- deficit 3 |

Two streams: ``salary_uah`` arrives as hryvnia at ``mono``; ``contract_usd`` arrives as dollars
at ``pocket``. One spendable endpoint: hryvnia at ``mono`` -- not "UAH anywhere", which is what
makes ``vault``'s exit to ``broker`` a hole rather than a way out (FR-004).

Five declared corridors, in one regime, **two of them multi-leg**:

| route | direction | from | to | legs |
|---|---|---|---|---|
| ``in_mono_broker`` | inbound | ``mono`` | ``broker`` | UAH -> UAH -> USD -> USD, three legs |
| ``in_mono_fund`` | inbound | ``mono`` | ``fund`` | UAH -> UAH |
| ``in_mono_vault`` | inbound | ``mono`` | ``vault`` | UAH -> USD |
| ``out_broker_mono`` | exit | ``broker`` | ``mono`` | USD -> UAH -> UAH, two legs |
| ``out_vault_broker`` | exit | ``vault`` | ``broker`` | USD -> USD |

⚙ **The multi-leg routes are load-bearing, not decoration.** Matching reads the **endpoints**
of a chain -- the first leg's ``from_ccy`` and the last leg's ``to_ccy`` (research.md D6) -- and
in a one-leg route those are the same leg, so a rule written against the wrong end of the chain
would be indistinguishable from the right one. ``in_mono_broker`` takes in hryvnia and hands out
dollars with an interior that is neither, and ``out_broker_mono`` does the reverse, so each of
the four places the rule is applied has a chain that can tell the two ends apart.

## Three verdicts in the table are worth reading twice

**``(mono, UAH)`` is comparison-ready for the salary with no route declared at either end.**
The money is born there -- inbound is *satisfied by arrival* -- and ``mono`` **is** the declared
spendable endpoint, so the exit half is *satisfied by identity* (FR-002, owner decision
2026-08-23). Nothing is relied on and nothing can be closed. The first implementation read
FR-002 literally and reported this pair as a hole demanding a declared way out of the owner's
own salary rail; the owner's answer was that the money is already where it needed to come back
out to, and requiring a route out of it would have made the salary rail the first finding in
the first real report.

**``(pocket, USD)`` is the other half of that pair of readings.** It is also an arrival point,
and it is *not* spendable, and no exit leaves it -- so it is not ready, with deficit 2. Arrival
satisfies the way in and says nothing at all about the way out, which is what FR-005 means by
"MUST still require the declared exit".

**``(vault, USD)`` is deficit 3 even though a human can see a path out.** ``out_vault_broker``
reaches ``broker``, and ``out_broker_mono`` leaves ``broker`` for the spendable endpoint. Two
declared routes, one obvious journey -- and this feature composes nothing (FR-006). The verdict
says the declared exit does not reach a spendable endpoint, which is exactly what the
declarations support today; feature 004 adds a *"reachable by composition only"* annotation
beside this verdict rather than changing what it means.
"""

from __future__ import annotations

import pytest

from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import EMPTY
from terezy.core.results.coverage import (
    ANY_SPENDABLE,
    EXIT_NOT_SPENDABLE,
    NO_EXIT_DECLARED,
    NO_INBOUND,
    SATISFIED_BY_ARRIVAL,
    SATISFIED_BY_IDENTITY,
    CoverageReport,
    Destination,
    NotReady,
    Ready,
    RegimeCoverage,
    SpendableEndpoint,
)
from terezy.core.routes.coverage import coverage, destinations
from terezy.core.routes.legs import FX, TRANSFER, Leg, Route
from terezy.core.routes.venues import Venue
from terezy.core.scenarios.regimes import Regime
from terezy.core.streams.streams import IncomeStream, Indexation

pytestmark = pytest.mark.worked_example

UAH = Currency.UAH
USD = Currency.USD

REGIME = "wartime"

VENUES = {
    venue_id: Venue(
        id=venue_id,
        name=f"{venue_id} (SYNTHETIC FIXTURE)",
        currencies=frozenset({currency}),
    )
    for venue_id, currency in (
        ("broker", USD),
        ("fund", UAH),
        ("hop_uah", UAH),
        ("hop_usd", USD),
        ("mono", UAH),
        ("pocket", USD),
        ("vault", USD),
    )
}
"""One currency per venue, so a destination and a venue are the same thing here and the table
below has one row per venue per stream."""


def _stream(stream_id: str, currency: Currency, arrives_at: str) -> IncomeStream:
    return IncomeStream(
        id=stream_id,
        owner_id="owner-001",
        amount=Money(0.0, currency, EMPTY),
        cadence="monthly",
        arrives_at=arrives_at,
        indexation=Indexation(policy="none", rate=None),
        income_tax_rate=None,
    )


STREAMS = {
    "contract_usd": _stream("contract_usd", USD, "pocket"),
    "salary_uah": _stream("salary_uah", UAH, "mono"),
}


def _leg(index: int, origin: str, destination: str, from_ccy: Currency, to_ccy: Currency) -> Leg:
    """One movement. ``fx`` exactly when the currencies differ, as the loader requires."""
    converts = from_ccy is not to_ccy
    return Leg(
        index=index,
        kind=FX if converts else TRANSFER,
        from_venue=origin,
        to_venue=destination,
        from_ccy=from_ccy,
        to_ccy=to_ccy,
        channel="p2p" if converts else None,
        fee_pct=0.0,
        fee_fixed=Money(0.0, from_ccy, EMPTY),
        minimum=None,
        maximum=None,
        monthly_cap=None,
        capacity_pool=None,
        latency_days=0,
        available_from=None,
        available_until=None,
        disruption_probability=0.0,
        kind_of_observation="bank_fee_schedule",
        provenance=EMPTY,
    )


def _route(route_id: str, direction: str, hops: tuple[tuple[str, Currency], ...]) -> Route:
    """One corridor from a sequence of ``(venue, currency)`` waypoints.

    Written as waypoints rather than as a first and last endpoint so the **interior** of a
    chain is expressible: matching reads ``legs[0].from_ccy`` and ``legs[-1].to_ccy``, and a
    fixture that could only build one-leg routes would make those the same leg and any rule
    written against the wrong end of the chain invisible (research.md D6).
    """
    legs = tuple(
        _leg(index, hops[index][0], hops[index + 1][0], hops[index][1], hops[index + 1][1])
        for index in range(len(hops) - 1)
    )
    return Route(
        id=route_id,
        provider=f"Synthetic {route_id}",
        origin=hops[0][0],
        destination=hops[-1][0],
        direction="inbound" if direction == "inbound" else "exit",
        partner_route=None,
        status="open",
        legs=legs,
    )


ROUTES = {
    route.id: route
    for route in (
        # Three legs: hryvnia out of the bank, converted at an intermediate venue, dollars in.
        # The interior is what makes the endpoint rule testable.
        _route(
            "in_mono_broker",
            "inbound",
            (("mono", UAH), ("hop_uah", UAH), ("hop_usd", USD), ("broker", USD)),
        ),
        _route("in_mono_fund", "inbound", (("mono", UAH), ("fund", UAH))),
        _route("in_mono_vault", "inbound", (("mono", UAH), ("vault", USD))),
        # Two legs the other way: converted first, then transferred home.
        _route("out_broker_mono", "exit", (("broker", USD), ("hop_uah", UAH), ("mono", UAH))),
        _route("out_vault_broker", "exit", (("vault", USD), ("broker", USD))),
    )
}

REGIMES = {REGIME: Regime(id=REGIME, route_ids=frozenset(ROUTES))}

SPENDABLE = frozenset({SpendableEndpoint(venue_id="mono", currency=UAH)})


# ---------------------------------------------------------------------------
# The table, enumerated by hand
# ---------------------------------------------------------------------------

READY = "ready"

TABLE: dict[tuple[str, Currency, str], tuple[str, ...]] = {
    # (broker, USD) -- a way out is declared and it reaches the spendable endpoint.
    #   contract_usd arrives as dollars at pocket, and no declared route carries dollars from
    #   pocket to broker, so the way *in* is what is missing for it.
    ("broker", USD, "contract_usd"): (NO_INBOUND,),
    #   salary_uah reaches it through in_mono_broker: three legs, taking in hryvnia at the
    #   stream's arrival venue and handing out dollars at the destination.
    ("broker", USD, "salary_uah"): (READY,),
    # (fund, UAH) -- reachable from the salary, and nothing leaves it.
    ("fund", UAH, "contract_usd"): (NO_INBOUND, NO_EXIT_DECLARED),
    ("fund", UAH, "salary_uah"): (NO_EXIT_DECLARED,),
    # (hop_uah, UAH) and (hop_usd, USD) -- venues that exist only as interior leg endpoints.
    #   Nobody declared a route *to* either of them and nothing leaves either, so both are
    #   holes at both ends. That is the destination universe being venue x holdable currency
    #   rather than anything derived from the routes: a venue money passes *through* is still
    #   a place money can sit, and the report says nobody has declared how to stop there.
    ("hop_uah", UAH, "contract_usd"): (NO_INBOUND, NO_EXIT_DECLARED),
    ("hop_uah", UAH, "salary_uah"): (NO_INBOUND, NO_EXIT_DECLARED),
    ("hop_usd", USD, "contract_usd"): (NO_INBOUND, NO_EXIT_DECLARED),
    ("hop_usd", USD, "salary_uah"): (NO_INBOUND, NO_EXIT_DECLARED),
    # (mono, UAH) -- the salary's own arrival point, and the spendable endpoint itself.
    #   For the salary: born there, and already spendable. Ready on two sentinels and no route.
    #   For the contract income: the exit half is satisfied by identity just the same -- the
    #   money would already be out if it were here -- and the way in is missing.
    ("mono", UAH, "contract_usd"): (NO_INBOUND,),
    ("mono", UAH, "salary_uah"): (READY,),
    # (pocket, USD) -- an arrival point that is *not* spendable and has no way out.
    #   Arrival satisfies the way in and says nothing about the way out (FR-005).
    ("pocket", USD, "contract_usd"): (NO_EXIT_DECLARED,),
    ("pocket", USD, "salary_uah"): (NO_INBOUND, NO_EXIT_DECLARED),
    # (vault, USD) -- the two-hop case. out_vault_broker leaves, and lands at broker in
    #   dollars, which is not on the spendable list. Nothing is composed.
    ("vault", USD, "contract_usd"): (NO_INBOUND, EXIT_NOT_SPENDABLE),
    ("vault", USD, "salary_uah"): (EXIT_NOT_SPENDABLE,),
}
"""Every pair in the declared universe: 7 destinations x 2 streams = 14, and none absent.

The value is the tuple of deficit kinds expected, in the order the report states them --
inbound side first, then exit side (research.md D7) -- or ``(READY,)``.
"""


def _report() -> CoverageReport:
    produced = coverage(
        venues=VENUES,
        streams=STREAMS,
        routes=ROUTES,
        regimes=REGIMES,
        spendable=SPENDABLE,
    )
    assert isinstance(produced, CoverageReport), produced
    return produced


def _block() -> RegimeCoverage:
    (block,) = _report().regimes
    return block


def test_every_pair_in_the_declared_universe_appears_exactly_once() -> None:
    """SC-001, FR-001, G1. Seven venues x one currency each x two streams = fourteen verdicts.

    Counted rather than sampled: a pair silently absent from the report is the failure mode
    the whole feature exists to prevent, and it is invisible to any assertion that only checks
    the pairs it thought to name.
    """
    block = _block()
    keys = [(v.destination.venue_id, v.destination.currency, v.stream_id) for v in block.verdicts]
    assert len(keys) == len(TABLE)
    assert len(set(keys)) == len(keys), "a pair appears twice"
    assert set(keys) == set(TABLE)


def test_the_verdicts_match_the_hand_enumerated_table() -> None:
    """SC-001, SC-002. Every verdict, against the table above, one at a time."""
    for verdict in _block().verdicts:
        key = (verdict.destination.venue_id, verdict.destination.currency, verdict.stream_id)
        expected = TABLE[key]
        match verdict:
            case Ready():
                assert expected == (READY,), f"{key} was ready and the table says {expected}"
            case NotReady():
                kinds = tuple(deficit.kind for deficit in verdict.deficits)
                assert kinds == expected, f"{key} reported {kinds}, the table says {expected}"


def test_no_verdict_is_an_undifferentiated_missing_route() -> None:
    """SC-002, FR-003. Every deficit is one of the three, and every not-ready verdict has one.

    The check is on the *set of kinds observed across the whole registry*: all three appear,
    and nothing outside the three does. A bare "missing route" value could only enter as a
    fourth kind, and there is no fourth to enter as -- which is the point of typing the kind
    as a closed ``Literal`` rather than a string.
    """
    observed = {
        deficit.kind
        for verdict in _block().verdicts
        if isinstance(verdict, NotReady)
        for deficit in verdict.deficits
    }
    assert observed == {NO_INBOUND, NO_EXIT_DECLARED, EXIT_NOT_SPENDABLE}
    for verdict in _block().verdicts:
        if isinstance(verdict, NotReady):
            assert verdict.deficits, "a not-ready verdict with no reason is a bare refusal"


def test_a_destination_at_a_streams_arrival_point_is_satisfied_by_arrival() -> None:
    """**SC-012, FR-005.** Money born at the destination needs no way in -- and still needs a
    way out.

    ``(pocket, USD)`` for ``contract_usd`` is where the dollar income lands. Inbound is
    satisfied by arrival, and the pair is **not** ready, because no exit is declared and
    ``pocket`` is not somewhere the owner spends from. Arrival answers one half of the owner's
    rule and says nothing whatever about the other.

    The sentinel is explicitly distinct from an empty tuple, which is the different claim a
    pair with no way in makes.
    """
    verdicts = {(v.destination.venue_id, v.stream_id): v for v in _block().verdicts}

    born_without_an_exit = verdicts[("pocket", "contract_usd")]
    assert isinstance(born_without_an_exit, NotReady)
    assert born_without_an_exit.inbound is SATISFIED_BY_ARRIVAL
    assert tuple(d.kind for d in born_without_an_exit.deficits) == (NO_EXIT_DECLARED,)

    no_way_in = verdicts[("fund", "contract_usd")]
    assert isinstance(no_way_in, NotReady)
    assert no_way_in.inbound == ()


def test_an_arrival_point_is_ready_if_and_only_if_its_exit_exists() -> None:
    """**SC-012's "if and only if"**, measured by declaring the missing half.

    The registry above leaves ``pocket`` with no way out. Declare one -- an exit to the
    spendable endpoint, and nothing else -- and the same pair is ready, still reporting
    *satisfied by arrival* on the inbound side because that has not changed. The exit is what
    the verdict turned on.
    """
    with_exit = _route("out_pocket_mono", "exit", (("pocket", USD), ("mono", UAH)))
    produced = coverage(
        venues=VENUES,
        streams=STREAMS,
        routes={**ROUTES, with_exit.id: with_exit},
        regimes={REGIME: Regime(id=REGIME, route_ids=frozenset({*ROUTES, with_exit.id}))},
        spendable=SPENDABLE,
    )
    assert isinstance(produced, CoverageReport)
    (block,) = produced.regimes
    verdict = next(
        v
        for v in block.verdicts
        if v.destination.venue_id == "pocket" and v.stream_id == "contract_usd"
    )
    assert isinstance(verdict, Ready)
    assert verdict.inbound is SATISFIED_BY_ARRIVAL
    assert verdict.exits != SATISFIED_BY_IDENTITY
    assert [relied.route_id for relied in verdict.exits] == ["out_pocket_mono"]


def test_the_spendable_endpoint_itself_is_ready_on_two_sentinels_and_no_route() -> None:
    """**FR-002, owner decision 2026-08-23.** The exit half satisfied by identity.

    ``(mono, UAH)`` funded from the salary that arrives there: the money is born at the
    destination and the destination *is* the declared spendable endpoint. Both halves of the
    owner's rule hold without a single declared route, and ``rests_on`` is ``open`` because
    neither sentinel is a route and neither can be closed.

    The first implementation read FR-002 literally and reported this as a hole demanding a
    declared way out of the owner's own bank account. It was the right reading of the sentence
    and the wrong answer, which is why the sentence was amended rather than the code bent
    around it.
    """
    verdicts = {(v.destination.venue_id, v.stream_id): v for v in _block().verdicts}
    already_out = verdicts[("mono", "salary_uah")]
    assert isinstance(already_out, Ready)
    assert already_out.inbound is SATISFIED_BY_ARRIVAL
    assert already_out.exits is SATISFIED_BY_IDENTITY
    assert already_out.rests_on == "open"

    # Identity is a property of the destination, not of the stream: the same balance funded
    # from the other income still has its exit half satisfied, and only the way in is missing.
    from_elsewhere = verdicts[("mono", "contract_usd")]
    assert isinstance(from_elsewhere, NotReady)
    assert tuple(d.kind for d in from_elsewhere.deficits) == (NO_INBOUND,)


def test_no_missing_exit_is_ever_named_for_a_spendable_destination() -> None:
    """The consequence of identity for the to-do list, asserted where it would go wrong.

    There is nothing to observe about getting money out of the place it is spent from, so no
    deficit and no to-do item may name ``mono`` as the origin of a missing exit. Checked across
    the whole block rather than on the one verdict, because the to-do list is built by a
    separate fold and could disagree with the verdicts that fed it.
    """
    block = _block()
    for verdict in block.verdicts:
        if isinstance(verdict, NotReady):
            for deficit in verdict.deficits:
                assert not (
                    deficit.missing.direction == "exit" and deficit.missing.origin_venue == "mono"
                )
    assert all(
        not (entry.missing.direction == "exit" and entry.missing.origin_venue == "mono")
        for entry in block.todo
    )


def test_a_ready_verdict_names_the_declarations_it_rests_on() -> None:
    """FR-021, G13. A verdict that cannot say what it rests on is not traceable.

    Both matching inbound routes are named where two exist, and every spendable exit is
    named -- not the first of each. The edge case "two inbound routes to one destination, only
    one with an exit partner" needs the partner-less one to stay visible, and a verdict naming
    one route would hide it behind the word *ready*.
    """
    verdicts = {(v.destination.venue_id, v.stream_id): v for v in _block().verdicts}
    ready = verdicts[("broker", "salary_uah")]
    assert isinstance(ready, Ready)
    assert isinstance(ready.inbound, tuple), "this way in is a declared route, not arrival"
    assert isinstance(ready.exits, tuple), "this way out is a declared route, not identity"
    assert [relied.route_id for relied in ready.inbound] == ["in_mono_broker"]
    assert [relied.route_id for relied in ready.exits] == ["out_broker_mono"]
    assert ready.rests_on == "open"


def test_the_two_hop_way_out_is_reported_as_a_hole_and_never_composed() -> None:
    """SC-011, FR-006, G4. ``vault`` -> ``broker`` -> ``mono`` is a path a human sees.

    The report says deficit 3 and names ``out_vault_broker`` among the exits that exist, so the
    owner can see that a way out was declared and why it does not count. What it does **not**
    do is chain the two declarations into a way out, and the missing declaration it names is an
    exit *from vault* to any spendable endpoint -- not the second hop, and not the inbound
    reversed.
    """
    verdicts = {(v.destination.venue_id, v.stream_id): v for v in _block().verdicts}
    two_hop = verdicts[("vault", "salary_uah")]
    assert isinstance(two_hop, NotReady)
    (deficit,) = two_hop.deficits
    assert deficit.kind == EXIT_NOT_SPENDABLE
    assert [relied.route_id for relied in deficit.observed_exits] == ["out_vault_broker"]
    assert deficit.missing.direction == "exit"
    assert deficit.missing.origin_venue == "vault"
    assert deficit.missing.origin_currency is USD
    assert deficit.missing.target is ANY_SPENDABLE
    assert deficit.missing.candidates == (SpendableEndpoint(venue_id="mono", currency=UAH),)


def test_the_report_names_the_declaration_set_it_audited() -> None:
    """FR-021, SC-016's second half. A verdict traces to the declarations that produced it."""
    audited = _report().audited
    assert audited.venue_ids == (
        "broker",
        "fund",
        "hop_uah",
        "hop_usd",
        "mono",
        "pocket",
        "vault",
    )
    assert audited.stream_ids == ("contract_usd", "salary_uah")
    assert audited.route_ids == tuple(sorted(ROUTES))
    assert audited.regime_ids == (REGIME,)
    assert audited.spendable == (SpendableEndpoint(venue_id="mono", currency=UAH),)


def test_the_destination_universe_is_venue_times_holdable_currency() -> None:
    """FR-001 ⚙, research.md D5. Derived from the venues, never from the routes.

    Building it from the routes is the way to lose exactly the holes the report exists to
    find: a venue nothing touches would contribute no destination and its emptiness would be
    invisible. Asserted here against the venue declarations rather than against the report, so
    the two have to agree.
    """
    assert destinations(VENUES) == (
        Destination(venue_id="broker", currency=USD),
        Destination(venue_id="fund", currency=UAH),
        Destination(venue_id="hop_uah", currency=UAH),
        Destination(venue_id="hop_usd", currency=USD),
        Destination(venue_id="mono", currency=UAH),
        Destination(venue_id="pocket", currency=USD),
        Destination(venue_id="vault", currency=USD),
    )
    # ``hop_uah`` and ``hop_usd`` are the point: no route declares either as its origin or its
    # destination -- they exist only as interior leg endpoints -- and they are destinations
    # anyway, because money can sit there. A universe derived from the routes would not have
    # them, and their emptiness would be invisible.
