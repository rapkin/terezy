"""The coverage table, enumerated by hand. **SC-001, SC-002, SC-012.**

*"For a hand-declared registry of two streams, three destinations and a deliberate mix of
holes, every ``(destination x stream x regime)`` verdict matches a hand-enumerated coverage
table checked in beside the assertion, and no pair in the declared universe is absent from the
report."*

The registry is declared **in this file**, and so is the expected table. A worked example that
reached for a shared fixture would make a reader open two files to check one verdict, which is
the whole thing a worked example exists to prevent -- so ``tests/coverage_registries.py``
serves every other coverage suite and not this one.

⚙ **Four destinations, not three.** SC-001 says three, and three is one short of what the
spec's own edge cases require: the two-hop way out (SC-011, and the "a human sees a path; this
feature MUST NOT compose it" edge case) needs a destination whose exit lands at *another*
destination that is itself spendable-reachable. The fourth venue is declared for exactly that,
and the table below is the whole universe either way -- which is the property SC-001 is
actually about.

## The registry, in words before it is in code

Four venues, each holding one currency, so the destination universe is four:

| venue | holds | what it is here for |
|---|---|---|
| ``broker`` | USD | the USD stream's arrival point, and a destination with a way out |
| ``fund`` | UAH | reachable from the salary, and nothing leaves it -- deficit 2 |
| ``mono`` | UAH | the salary's arrival point, and the **one** spendable endpoint |
| ``vault`` | USD | reachable from the salary; its only exit lands at ``broker`` -- deficit 3 |

Two streams: ``salary_uah`` arrives as hryvnia at ``mono``; ``contract_usd`` arrives as dollars
at ``broker``. One spendable endpoint: hryvnia at ``mono`` -- not "UAH anywhere", which is what
makes ``vault``'s exit to ``broker`` a hole rather than a way out (FR-004).

Five declared corridors, in one regime:

| route | direction | from | to | currencies |
|---|---|---|---|---|
| ``in_mono_broker`` | inbound | ``mono`` | ``broker`` | UAH -> USD |
| ``in_mono_fund`` | inbound | ``mono`` | ``fund`` | UAH -> UAH |
| ``in_mono_vault`` | inbound | ``mono`` | ``vault`` | UAH -> USD |
| ``out_broker_mono`` | exit | ``broker`` | ``mono`` | USD -> UAH |
| ``out_vault_broker`` | exit | ``vault`` | ``broker`` | USD -> USD |

## Two verdicts in the table are worth reading twice

**``(mono, UAH)`` is not ready for its own salary**, and that is FR-002 applied literally
rather than a defect. The money is born there -- inbound is *satisfied by arrival* -- and
``mono`` is the declared spendable endpoint, and there is still no declared route *out* of it,
so the pair is not comparison-ready. The spec's Assumptions fix this reading in as many words:
*"the exit leaves the destination venue -- a way out exists to somewhere else that is
spendable"*. Reading a destination as its own way out would make every spendable venue
comparison-ready by definition, which is the one verdict that could never be wrong and
therefore the one worth nothing.

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
    "broker": Venue(id="broker", name="Broker (SYNTHETIC)", currencies=frozenset({USD})),
    "fund": Venue(id="fund", name="Fund platform (SYNTHETIC)", currencies=frozenset({UAH})),
    "mono": Venue(id="mono", name="Bank card (SYNTHETIC)", currencies=frozenset({UAH})),
    "vault": Venue(id="vault", name="Vault (SYNTHETIC)", currencies=frozenset({USD})),
}


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
    "contract_usd": _stream("contract_usd", USD, "broker"),
    "salary_uah": _stream("salary_uah", UAH, "mono"),
}


def _route(
    route_id: str,
    origin: str,
    destination: str,
    *,
    direction: str,
    from_ccy: Currency,
    to_ccy: Currency,
) -> Route:
    """One corridor as a single leg. Coverage reads the chain's endpoints and nothing else."""
    converts = from_ccy is not to_ccy
    return Route(
        id=route_id,
        provider=f"Synthetic {route_id}",
        origin=origin,
        destination=destination,
        direction="inbound" if direction == "inbound" else "exit",
        partner_route=None,
        status="open",
        legs=(
            Leg(
                index=0,
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
            ),
        ),
    )


ROUTES = {
    route.id: route
    for route in (
        _route("in_mono_broker", "mono", "broker", direction="inbound", from_ccy=UAH, to_ccy=USD),
        _route("in_mono_fund", "mono", "fund", direction="inbound", from_ccy=UAH, to_ccy=UAH),
        _route("in_mono_vault", "mono", "vault", direction="inbound", from_ccy=UAH, to_ccy=USD),
        _route("out_broker_mono", "broker", "mono", direction="exit", from_ccy=USD, to_ccy=UAH),
        _route("out_vault_broker", "vault", "broker", direction="exit", from_ccy=USD, to_ccy=USD),
    )
}

REGIMES = {REGIME: Regime(id=REGIME, route_ids=frozenset(ROUTES))}

SPENDABLE = frozenset({SpendableEndpoint(venue_id="mono", currency=UAH)})


# ---------------------------------------------------------------------------
# The table, enumerated by hand
# ---------------------------------------------------------------------------

READY = "ready"

TABLE: dict[tuple[str, Currency, str], tuple[str, ...]] = {
    # (broker, USD) -- the destination with a declared way in and a declared way out.
    #   contract_usd is born here, so inbound is satisfied by arrival; out_broker_mono
    #   delivers hryvnia to mono, which is the declared spendable endpoint.
    ("broker", USD, "contract_usd"): (READY,),
    #   salary_uah reaches it through in_mono_broker: mono -> broker, UAH -> USD, which is
    #   the stream's arrival venue and arrival currency, and the destination's currency.
    ("broker", USD, "salary_uah"): (READY,),
    # (fund, UAH) -- reachable from the salary, and nothing leaves it.
    #   contract_usd arrives as dollars at broker, and no declared route carries dollars
    #   from broker to fund: both halves are missing, and both are reported.
    ("fund", UAH, "contract_usd"): (NO_INBOUND, NO_EXIT_DECLARED),
    ("fund", UAH, "salary_uah"): (NO_EXIT_DECLARED,),
    # (mono, UAH) -- the salary's own arrival point, and the spendable endpoint itself.
    #   Still not ready: no route out of mono is declared. See this module's docstring.
    #   out_broker_mono ends here but its direction is `exit`, so it is not an inbound
    #   match -- a way out is not a way in read backwards (FR-006).
    ("mono", UAH, "contract_usd"): (NO_INBOUND, NO_EXIT_DECLARED),
    ("mono", UAH, "salary_uah"): (NO_EXIT_DECLARED,),
    # (vault, USD) -- the two-hop case. out_vault_broker leaves, and lands at broker in
    #   dollars, which is not on the spendable list. Nothing is composed.
    ("vault", USD, "contract_usd"): (NO_INBOUND, EXIT_NOT_SPENDABLE),
    ("vault", USD, "salary_uah"): (EXIT_NOT_SPENDABLE,),
}
"""Every pair in the declared universe: 4 destinations x 2 streams = 8, and none absent.

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
    """SC-001, FR-001, G1. Four venues x one currency each x two streams = eight verdicts.

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
    """SC-012, FR-005. Money born at the destination needs no way in -- and still needs a way
    out.

    Two halves, and the second is the one that makes the first honest. ``(broker, USD)`` for
    ``contract_usd`` is satisfied by arrival **and** ready, because an exit is declared;
    ``(mono, UAH)`` for ``salary_uah`` is satisfied by arrival and **not** ready, because none
    is. Comparison-ready if and only if the exit exists, which is exactly what SC-012 asks.
    """
    verdicts = {(v.destination.venue_id, v.stream_id): v for v in _block().verdicts}

    born_with_an_exit = verdicts[("broker", "contract_usd")]
    assert isinstance(born_with_an_exit, Ready)
    assert born_with_an_exit.inbound is SATISFIED_BY_ARRIVAL

    born_without_an_exit = verdicts[("mono", "salary_uah")]
    assert isinstance(born_without_an_exit, NotReady)
    assert born_without_an_exit.inbound is SATISFIED_BY_ARRIVAL
    assert tuple(d.kind for d in born_without_an_exit.deficits) == (NO_EXIT_DECLARED,)

    # Distinct from "nothing relied on", which is what an empty tuple would say and what a
    # pair with no inbound route actually reports.
    no_way_in = verdicts[("fund", "contract_usd")]
    assert isinstance(no_way_in, NotReady)
    assert no_way_in.inbound == ()


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
    assert ready.inbound != SATISFIED_BY_ARRIVAL
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
    assert audited.venue_ids == ("broker", "fund", "mono", "vault")
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
        Destination(venue_id="mono", currency=UAH),
        Destination(venue_id="vault", currency=USD),
    )
