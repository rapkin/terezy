"""The three deficits, the to-do list, and the loop from report back to declaration.

**SC-002, SC-003, SC-005, SC-006, SC-010, SC-011, SC-017.**

An audit that says "seven of twelve pairs are not comparable" without saying what to do about
it is a complaint, not a tool. These are the assertions that make it a tool: each deficit calls
for a *different* observation and is reported as such; each missing declaration is precise
enough to write the file from; and the count of pairs each one blocks orders the list, with ties
reported rather than broken.

Three small registries carry the deficit kinds one at a time, and one larger one -- enumerated
in the docstring of :data:`TODO_REGISTRY` -- carries the counting. Each is minimal on purpose: a
registry with a spare corridor in it would let a wrong verdict hide behind a right one.
"""

from __future__ import annotations

from dataclasses import fields
from typing import TYPE_CHECKING

from terezy.core.results.coverage import (
    ANY_SPENDABLE,
    EXIT_NOT_SPENDABLE,
    NO_EXIT_DECLARED,
    NO_INBOUND,
    CoverageReport,
    Destination,
    MissingDeclaration,
    NotReady,
    Ready,
    RegimeCoverage,
    SpendableEndpoint,
)
from terezy.core.routes.coverage import blocked_count, coverage
from tests.coverage_registries import UAH, USD, keyed, route, spendable, stream, venue

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping

    from terezy.core.routes.legs import Route
    from terezy.core.routes.venues import Venue
    from terezy.core.streams.streams import IncomeStream


def _block(
    *,
    venues: Mapping[str, Venue],
    streams: Mapping[str, IncomeStream],
    routes: Mapping[str, Route],
    spendable_set: frozenset[SpendableEndpoint],
) -> RegimeCoverage:
    """The one implicit regime's block for a registry declared with no regimes.

    Every case here is about a deficit rather than about a regime, so they all run under
    FR-015's single implicit regime -- which keeps the assertions about the thing under test.
    ``tests/unit/test_coverage_regimes.py`` is where the split matters.
    """
    produced = coverage(
        venues=venues,
        streams=streams,
        routes=routes,
        regimes={},
        spendable=spendable_set,
    )
    assert isinstance(produced, CoverageReport), produced
    (block,) = produced.regimes
    return block


def _verdicts(block: RegimeCoverage) -> dict[tuple[str, str], Ready | NotReady]:
    return {(v.destination.venue_id, v.stream_id): v for v in block.verdicts}


# ---------------------------------------------------------------------------
# One registry per deficit kind (SC-002), each with nothing else in it
# ---------------------------------------------------------------------------

MONO = venue("mono", UAH)
SALARY = stream("salary_uah", UAH, "mono")
SPENDABLE_AT_MONO = spendable(("mono", UAH))


def test_deficit_one_is_no_inbound_route_from_this_stream() -> None:
    """Nothing declared carries this stream's money to this destination.

    ``island`` has a declared, spendable way **out** and no way in, so the exit half of the
    owner's rule is satisfied and the inbound half is not. The observation to make is a way in,
    and the report says so in the direction of the missing declaration.
    """
    routes = keyed(
        [
            route(
                "out_island_mono",
                origin="island",
                destination="mono",
                direction="exit",
                from_ccy=UAH,
            )
        ]
    )
    block = _block(
        venues=keyed([MONO, venue("island", UAH)]),
        streams=keyed([SALARY]),
        routes=routes,
        spendable_set=SPENDABLE_AT_MONO,
    )
    verdict = _verdicts(block)[("island", "salary_uah")]
    assert isinstance(verdict, NotReady)
    (deficit,) = verdict.deficits
    assert deficit.kind == NO_INBOUND
    assert deficit.missing == MissingDeclaration(
        direction="inbound",
        origin_venue="mono",
        origin_currency=UAH,
        target=Destination(venue_id="island", currency=UAH),
        candidates=(),
    )
    assert deficit.observed_exits == ()


def test_deficit_two_is_no_exit_declared_at_all() -> None:
    """The destination is reachable and nothing leaves it.

    Distinct from deficit 3 because it calls for a different observation: here nobody has
    looked at the way out at all, and there is no ``observed_exits`` to show, which is exactly
    the difference the field exists to carry.
    """
    routes = keyed(
        [
            route(
                "in_mono_fund", origin="mono", destination="fund", direction="inbound", from_ccy=UAH
            )
        ]
    )
    block = _block(
        venues=keyed([MONO, venue("fund", UAH)]),
        streams=keyed([SALARY]),
        routes=routes,
        spendable_set=SPENDABLE_AT_MONO,
    )
    verdict = _verdicts(block)[("fund", "salary_uah")]
    assert isinstance(verdict, NotReady)
    (deficit,) = verdict.deficits
    assert deficit.kind == NO_EXIT_DECLARED
    assert deficit.observed_exits == ()
    assert deficit.missing.direction == "exit"
    assert deficit.missing.origin_venue == "fund"


def test_deficit_three_is_an_exit_that_does_not_reach_a_spendable_endpoint() -> None:
    """A way out is declared, and it lands somewhere the owner cannot spend from.

    ``observed_exits`` is what stops this reading like deficit 2: the owner can see that the
    corridor **was** observed and why it does not count, so he does not go and observe it again.
    """
    routes = keyed(
        [
            route(
                "in_mono_vault",
                origin="mono",
                destination="vault",
                direction="inbound",
                from_ccy=UAH,
                to_ccy=USD,
            ),
            route(
                "out_vault_broker",
                origin="vault",
                destination="broker",
                direction="exit",
                from_ccy=USD,
            ),
        ]
    )
    block = _block(
        venues=keyed([MONO, venue("vault", USD), venue("broker", USD)]),
        streams=keyed([SALARY]),
        routes=routes,
        spendable_set=SPENDABLE_AT_MONO,
    )
    verdict = _verdicts(block)[("vault", "salary_uah")]
    assert isinstance(verdict, NotReady)
    (deficit,) = verdict.deficits
    assert deficit.kind == EXIT_NOT_SPENDABLE
    assert [relied.route_id for relied in deficit.observed_exits] == ["out_vault_broker"]


def test_a_two_hop_way_out_is_deficit_three_and_is_never_composed() -> None:
    """**SC-011, FR-006, G4.** ``vault -> broker -> mono`` is a path; it is not a declaration.

    ``broker`` itself has a declared spendable exit here, so a reader can trace the money all
    the way home. The report still says the exit from ``vault`` does not reach a spendable
    endpoint, because that is what the declarations support **today**. Composition is feature
    004's, and it arrives as a distinct annotation beside this verdict rather than as a change
    to what it means.
    """
    routes = keyed(
        [
            route(
                "in_mono_vault",
                origin="mono",
                destination="vault",
                direction="inbound",
                from_ccy=UAH,
                to_ccy=USD,
            ),
            route(
                "out_vault_broker",
                origin="vault",
                destination="broker",
                direction="exit",
                from_ccy=USD,
            ),
            route(
                "out_broker_mono",
                origin="broker",
                destination="mono",
                direction="exit",
                from_ccy=USD,
                to_ccy=UAH,
            ),
        ]
    )
    block = _block(
        venues=keyed([MONO, venue("vault", USD), venue("broker", USD)]),
        streams=keyed([SALARY]),
        routes=routes,
        spendable_set=SPENDABLE_AT_MONO,
    )
    verdict = _verdicts(block)[("vault", "salary_uah")]
    assert isinstance(verdict, NotReady)
    assert tuple(d.kind for d in verdict.deficits) == (EXIT_NOT_SPENDABLE,)
    # And nothing anywhere in the report claims the composed path exists: the only way *out*
    # it asks anybody to observe is one leaving ``vault`` -- not the second hop, and not the
    # chain. (It also asks for a way *in* to ``broker``, which the salary cannot reach in this
    # registry; that is the other half of a different pair.)
    assert [
        entry.missing.origin_venue for entry in block.todo if entry.missing.direction == "exit"
    ] == ["vault"]


# ---------------------------------------------------------------------------
# SC-010: a missing exit leaves the destination; it is not the inbound reversed
# ---------------------------------------------------------------------------


def test_a_missing_exit_starts_at_the_destination_and_suggests_no_values() -> None:
    """**SC-010, FR-006, FR-008.**

    Two claims, and the second is structural. The missing exit's origin is the **destination**
    venue in the **destination's** currency -- not the inbound route's origin, which is what
    reversing it would produce. And no missing declaration anywhere can carry a provider, a
    fee, a premium, a cap, a latency or a rate, because :class:`MissingDeclaration` has no
    field one could live in. Asserted on the record's own fields rather than on this report's
    contents, so it stays true of every report anyone ever produces (SC-004's "not sampled").
    """
    routes = keyed(
        [
            route(
                "in_mono_fund", origin="mono", destination="fund", direction="inbound", from_ccy=UAH
            )
        ]
    )
    block = _block(
        venues=keyed([MONO, venue("fund", UAH)]),
        streams=keyed([SALARY]),
        routes=routes,
        spendable_set=SPENDABLE_AT_MONO,
    )
    verdict = _verdicts(block)[("fund", "salary_uah")]
    assert isinstance(verdict, NotReady)
    (deficit,) = verdict.deficits
    assert deficit.missing == MissingDeclaration(
        direction="exit",
        origin_venue="fund",
        origin_currency=UAH,
        target=ANY_SPENDABLE,
        candidates=(SpendableEndpoint(venue_id="mono", currency=UAH),),
    )
    # The inbound route's shape is mono -> fund. Nothing in the report reproduces it as an
    # exit, which is what "never the inbound route reversed" means when it is checkable.
    assert deficit.missing.origin_venue != "mono"

    assert {field.name for field in fields(MissingDeclaration)} == {
        "direction",
        "origin_venue",
        "origin_currency",
        "target",
        "candidates",
    }


# ---------------------------------------------------------------------------
# SC-017: an orphan exit is listed, and counts for nothing
# ---------------------------------------------------------------------------


def test_an_orphan_exit_is_listed_as_unused_and_blocks_no_count() -> None:
    """**SC-017, FR-012.** An observation already made that nothing yet uses.

    ``out_island_mono`` leaves a destination no stream can reach, so it satisfies nobody's exit
    half. Hiding it would misstate the registry -- the owner has already paid attention to that
    corridor, and he should know it before going out to observe a third. Listing it as a
    *deficit* would be worse: it would send him to observe a corridor he has already observed.
    """
    routes = keyed(
        [
            route(
                "out_island_mono",
                origin="island",
                destination="mono",
                direction="exit",
                from_ccy=UAH,
            )
        ]
    )
    block = _block(
        venues=keyed([MONO, venue("island", UAH)]),
        streams=keyed([SALARY]),
        routes=routes,
        spendable_set=SPENDABLE_AT_MONO,
    )
    (orphan,) = block.orphan_exits
    assert orphan.route_id == "out_island_mono"
    assert orphan.origin == Destination(venue_id="island", currency=UAH)
    assert orphan.reaches_spendable is True

    # It is in no deficit, and in no to-do item's reckoning.
    for verdict in block.verdicts:
        if isinstance(verdict, NotReady):
            for deficit in verdict.deficits:
                assert all(
                    relied.route_id != "out_island_mono" for relied in deficit.observed_exits
                )
    # One hole remains -- a way in to island -- and it is not the orphan; the orphan added
    # nothing to its count. ``mono`` produces no hole at all: it is the declared spendable
    # endpoint, so its exit half is satisfied by identity (FR-002).
    assert sorted((entry.missing.direction, entry.count) for entry in block.todo) == [
        ("inbound", 1),
    ]


# ---------------------------------------------------------------------------
# The counting registry, enumerated by hand
# ---------------------------------------------------------------------------

TODO_VENUES = keyed(
    [
        venue("cash", UAH),
        venue("coin", USD),
        venue("hub", UAH),
        venue("mono", UAH),
        venue("solo", UAH),
        venue("void", UAH),
    ]
)
TODO_STREAMS = keyed([stream("contract_usd", USD, "coin"), stream("salary_uah", UAH, "mono")])
TODO_REGISTRY: Mapping[str, Route] = keyed(
    [
        route(
            "in_coin_hub",
            origin="coin",
            destination="hub",
            direction="inbound",
            from_ccy=USD,
            to_ccy=UAH,
        ),
        route(
            "in_mono_coin",
            origin="mono",
            destination="coin",
            direction="inbound",
            from_ccy=UAH,
            to_ccy=USD,
        ),
        route("in_mono_hub", origin="mono", destination="hub", direction="inbound", from_ccy=UAH),
        route("in_mono_solo", origin="mono", destination="solo", direction="inbound", from_ccy=UAH),
        route(
            "out_coin_mono",
            origin="coin",
            destination="mono",
            direction="exit",
            from_ccy=USD,
            to_ccy=UAH,
        ),
        route("out_solo_mono", origin="solo", destination="mono", direction="exit", from_ccy=UAH),
    ]
)
"""Six destinations, two streams, six corridors, and exactly eight holes.

⚙ **Two spendable endpoints, and that is load-bearing** (FR-007 ⚙). A missing exit's target is
*any one of them*, so its identity is origin + direction and it stays **one** to-do item
whatever the list's length. With a single-endpoint fixture the two readings -- one item, or one
per candidate -- produce identical counts and nothing tells them apart; with two, a report that
multiplied by the candidate list would report every exit count as four rather than two.

| pair | verdict | why |
|---|---|---|
| ``(cash, UAH)`` x either | not ready | spendable, so out is satisfied by identity; **no way in** |
| ``(coin, USD)`` x ``contract_usd`` | ready | born there; ``out_coin_mono`` reaches spendable |
| ``(coin, USD)`` x ``salary_uah`` | ready | ``in_mono_coin`` in, ``out_coin_mono`` out |
| ``(hub, UAH)`` x either stream | not ready | a way in from each, **nothing out** |
| ``(mono, UAH)`` x ``contract_usd`` | not ready | out satisfied by identity; **no way in** |
| ``(mono, UAH)`` x ``salary_uah`` | ready | born there **and** spendable: two sentinels, no route |
| ``(solo, UAH)`` x ``contract_usd`` | not ready | **no way in**; ``out_solo_mono`` out |
| ``(solo, UAH)`` x ``salary_uah`` | ready | ``in_mono_solo`` in, ``out_solo_mono`` out |
| ``(void, UAH)`` x either | not ready | nothing touches it: **no way in and none out** |

Eight distinct missing declarations, hand-counted:

| # | declaration | blocks | count |
|---|---|---|---|
| E1 | exit from ``hub`` in UAH | both ``hub`` pairs | **2** |
| E2 | exit from ``void`` in UAH | both ``void`` pairs | **2** |
| I1 | inbound ``coin`` USD -> ``(cash, UAH)`` | ``(cash, UAH)`` x ``contract_usd`` | **1** |
| I2 | inbound ``coin`` USD -> ``(mono, UAH)`` | ``(mono, UAH)`` x ``contract_usd`` | **1** |
| I3 | inbound ``coin`` USD -> ``(solo, UAH)`` | ``(solo, UAH)`` x ``contract_usd`` | **1** |
| I4 | inbound ``coin`` USD -> ``(void, UAH)`` | ``(void, UAH)`` x ``contract_usd`` | **1** |
| I5 | inbound ``mono`` UAH -> ``(cash, UAH)`` | ``(cash, UAH)`` x ``salary_uah`` | **1** |
| I6 | inbound ``mono`` UAH -> ``(void, UAH)`` | ``(void, UAH)`` x ``salary_uah`` | **1** |

Both ``void`` pairs need **two** declarations each, so each appears in two entries and is marked
not-alone-sufficient in both (FR-011).
"""

TODO_SPENDABLE = spendable(("cash", UAH), ("mono", UAH))


def _todo_block() -> RegimeCoverage:
    return _block(
        venues=TODO_VENUES,
        streams=TODO_STREAMS,
        routes=TODO_REGISTRY,
        spendable_set=TODO_SPENDABLE,
    )


def test_the_todo_list_is_ordered_by_blocked_pair_count_and_ties_are_reported() -> None:
    """**SC-005, FR-009, FR-010, required test B12.**

    The exit blocking two pairs outranks the inbound blocking one, and the count is a plain
    count of pairs -- ``count == len(blocked)`` -- rather than a composite score. Equal counts
    are reported in ``ties`` instead of being broken: the sequence is still deterministic, so
    the report is reproducible, but a position in it is not a claim of precedence.
    """
    block = _todo_block()
    assert [(e.missing.direction, e.missing.origin_venue, e.count) for e in block.todo] == [
        ("exit", "hub", 2),
        ("exit", "void", 2),
        ("inbound", "coin", 1),
        ("inbound", "coin", 1),
        ("inbound", "coin", 1),
        ("inbound", "coin", 1),
        ("inbound", "mono", 1),
        ("inbound", "mono", 1),
    ]
    for entry in block.todo:
        assert entry.count == len(entry.blocked) == blocked_count(entry)
    assert block.ties == ((0, 1), (2, 3, 4, 5, 6, 7))
    # The count-1 entries differ only in their target, which is what keeps them separate
    # observations rather than one -- and what makes the tie a real tie.
    assert {e.missing.target for e in block.todo[2:]} == {
        Destination(venue_id="cash", currency=UAH),
        Destination(venue_id="mono", currency=UAH),
        Destination(venue_id="solo", currency=UAH),
        Destination(venue_id="void", currency=UAH),
    }


def test_a_missing_exits_count_does_not_multiply_by_the_spendable_list() -> None:
    """**FR-007 ⚙.** One missing exit is one to-do item, however many endpoints would satisfy it.

    The registry declares **two** spendable endpoints, so each missing exit names two
    candidates -- and its blocked-pair count is still the number of pairs, not the number of
    pairs times the number of ways to fix them. A report that produced one item per candidate
    would double every exit entry here and inflate every count with it, which would then
    reorder the whole to-do list against the missing inbounds.

    Asserted against the candidate list's actual length rather than against the constant 2, so
    the test keeps meaning what it says if the fixture gains a third endpoint.
    """
    block = _todo_block()
    exits = [entry for entry in block.todo if entry.missing.direction == "exit"]
    assert len(exits) == 2, "one item per missing exit, not one per candidate endpoint"
    for entry in exits:
        assert len(entry.missing.candidates) == len(TODO_SPENDABLE) == 2
        assert entry.count == 2
        assert entry.count == len({(p.destination, p.stream_id) for p in entry.blocked})


def test_a_pair_missing_both_halves_counts_for_both_and_is_alone_sufficient_for_neither() -> None:
    """**SC-006, FR-011.** Necessary is not sufficient, and the report never implies it is.

    ``(mono, UAH)`` funded from ``contract_usd`` needs a way in *and* a way out. Adding either
    alone leaves the pair not comparable, so both entries carry it with
    ``alone_sufficient = False``. The same to-do entry carries ``(mono, UAH) x salary_uah``
    with ``True``, because for that pair the exit really is the only thing missing -- which is
    why the flag is per blocked pair rather than per entry.
    """
    block = _todo_block()
    by_key = {(e.missing.direction, e.missing.origin_venue): e for e in block.todo}

    # ``void`` is touched by nothing, so both its pairs need a way in *and* a way out.
    exit_from_void = by_key[("exit", "void")]
    blocked = {pair.stream_id: pair for pair in exit_from_void.blocked}
    assert blocked["contract_usd"].alone_sufficient is False
    assert blocked["salary_uah"].alone_sufficient is False

    inbound_to_void = [
        entry
        for entry in block.todo
        if entry.missing.target == Destination(venue_id="void", currency=UAH)
    ]
    assert len(inbound_to_void) == 2, "one missing way in per stream, from each arrival venue"
    for entry in inbound_to_void:
        assert entry.count == 1
        assert entry.blocked[0].alone_sufficient is False

    # And the contrast, on the same registry: ``hub`` is reachable from both streams, so the
    # missing exit really is the only thing either pair waits on.
    exit_from_hub = by_key[("exit", "hub")]
    assert all(pair.alone_sufficient for pair in exit_from_hub.blocked)


def test_writing_the_named_inbound_declaration_and_nothing_else_flips_the_pair() -> None:
    """**SC-003, FR-007.** The report-to-declaration loop, closed by walking it.

    The report names origin venue, origin currency, direction and target. This test writes
    exactly a route with those four properties -- inventing no fee, no provider and no
    premium, because the report suggested none -- and re-runs. The pair is ready, and the
    to-do item is gone.
    """
    before = _todo_block()
    missing = next(
        entry.missing
        for entry in before.todo
        if entry.missing.target == Destination(venue_id="solo", currency=UAH)
    )
    assert isinstance(missing.target, Destination)

    written = route(
        "observed_coin_solo",
        origin=missing.origin_venue,
        destination=missing.target.venue_id,
        direction=missing.direction,
        from_ccy=missing.origin_currency,
        to_ccy=missing.target.currency,
    )
    after = _block(
        venues=TODO_VENUES,
        streams=TODO_STREAMS,
        routes={**TODO_REGISTRY, written.id: written},
        spendable_set=TODO_SPENDABLE,
    )
    assert isinstance(_verdicts(after)[("solo", "contract_usd")], Ready)
    assert all(entry.missing != missing for entry in after.todo)


def test_writing_an_exit_to_any_one_listed_candidate_is_enough() -> None:
    """**SC-003's second half, FR-007 ⚙.** The target of a missing exit is a set, not a point.

    Any *one* of the listed candidates satisfies it, and the report says so by naming
    ``ANY_SPENDABLE`` with the candidates beside it rather than picking one -- picking would be
    the report inventing a preference. Writing an exit to the first candidate flips **both**
    pairs the entry blocked, which is also the claim its count of two was making.
    """
    before = _todo_block()
    entry = next(e for e in before.todo if e.missing.origin_venue == "hub")
    assert entry.missing.target is ANY_SPENDABLE
    assert entry.count == 2
    candidate = entry.missing.candidates[0]

    written = route(
        "observed_hub_out",
        origin=entry.missing.origin_venue,
        destination=candidate.venue_id,
        direction="exit",
        from_ccy=entry.missing.origin_currency,
        to_ccy=candidate.currency,
    )
    after = _block(
        venues=TODO_VENUES,
        streams=TODO_STREAMS,
        routes={**TODO_REGISTRY, written.id: written},
        spendable_set=TODO_SPENDABLE,
    )
    verdicts = _verdicts(after)
    assert isinstance(verdicts[("hub", "contract_usd")], Ready)
    assert isinstance(verdicts[("hub", "salary_uah")], Ready)
    assert all(e.missing != entry.missing for e in after.todo)


def test_a_registry_with_no_holes_states_that_there_is_nothing_to_observe() -> None:
    """The honest happy path: the to-do list is explicitly empty rather than absent.

    An absent list and an empty one read the same to a person and differently to a program,
    and this project has already been bitten once by an empty result standing in for a claim
    (defect B10). ``todo == ()`` beside eight ready verdicts is the statement "nothing to
    observe"; it is not the absence of a statement.
    """
    routes = keyed(
        [
            route(
                "in_mono_solo", origin="mono", destination="solo", direction="inbound", from_ccy=UAH
            ),
            route(
                "out_solo_mono", origin="solo", destination="mono", direction="exit", from_ccy=UAH
            ),
            route(
                "out_mono_solo", origin="mono", destination="solo", direction="exit", from_ccy=UAH
            ),
        ]
    )
    block = _block(
        venues=keyed([MONO, venue("solo", UAH)]),
        streams=keyed([SALARY]),
        routes=routes,
        spendable_set=spendable(("mono", UAH), ("solo", UAH)),
    )
    assert all(isinstance(verdict, Ready) for verdict in block.verdicts)
    assert block.todo == ()
    assert block.ties == ()
    # And nothing is listed as unused. Every declared exit here leaves a destination some
    # stream can reach -- ``solo`` through ``in_mono_solo``, ``mono`` by arrival -- so an
    # orphan listed on this registry would mean the reachability test had stopped counting
    # arrival, which is the one term of it no route declares.
    assert block.orphan_exits == ()


# ---------------------------------------------------------------------------
# The currency half of an inbound match, which no route-graph generator reaches
# ---------------------------------------------------------------------------


def test_a_route_from_the_right_venue_in_the_wrong_currency_is_not_a_way_in() -> None:
    """Spec Assumptions: *an inbound route "from this stream" means from its arrival venue **in
    its arrival currency***.

    A multi-currency account is the ordinary case -- it is what Monobank is -- so the venues
    matching proves nothing about the currencies. A route that leaves the salary's own bank in
    **dollars** cannot carry a hryvnia salary: something would have to convert first, and that
    conversion is a declared leg with a declared channel, not an assumption the audit is
    entitled to make. Reporting the pair as reachable would credit the registry with a corridor
    whose first and most expensive step nobody has declared.

    This is the same chaining discipline the loader enforces on legs and ``cost_one`` enforces
    when it refuses a funding mismatch, applied at the audit level -- and it is asserted here
    because the shape it needs, two currencies at one arrival venue, is exactly what the
    coverage property's generator cannot produce: there a venue holds one currency so that
    costing's per-venue destination and coverage's per-balance destination stay one-to-one.
    """
    routes = keyed(
        [
            route(
                "in_mono_usd_to_fund",
                origin="mono",
                destination="fund",
                direction="inbound",
                from_ccy=USD,
                to_ccy=UAH,
            ),
            route(
                "out_fund_mono", origin="fund", destination="mono", direction="exit", from_ccy=UAH
            ),
        ]
    )
    block = _block(
        venues=keyed([venue("mono", UAH, USD), venue("fund", UAH)]),
        streams=keyed([SALARY]),
        routes=routes,
        spendable_set=SPENDABLE_AT_MONO,
    )
    verdict = _verdicts(block)[("fund", "salary_uah")]
    assert isinstance(verdict, NotReady)
    assert NO_INBOUND in {deficit.kind for deficit in verdict.deficits}
    assert verdict.inbound == ()


def test_a_route_arriving_in_the_wrong_currency_reaches_a_different_destination() -> None:
    """The mirror of the case above, on the destination side rather than the stream side.

    ``broker`` holds both currencies, so it is **two** destinations. A route delivering dollars
    there is a way in to the dollar balance and says nothing at all about the hryvnia one --
    they are different places money can sit, and a report that conflated them would call a
    hryvnia balance reachable on the strength of a corridor that delivers dollars.
    """
    routes = keyed(
        [
            route(
                "in_mono_broker_usd",
                origin="mono",
                destination="broker",
                direction="inbound",
                from_ccy=UAH,
                to_ccy=USD,
            ),
            route(
                "out_broker_usd",
                origin="broker",
                destination="mono",
                direction="exit",
                from_ccy=USD,
                to_ccy=UAH,
            ),
            route(
                "out_broker_uah",
                origin="broker",
                destination="mono",
                direction="exit",
                from_ccy=UAH,
            ),
        ]
    )
    block = _block(
        venues=keyed([MONO, venue("broker", UAH, USD)]),
        streams=keyed([SALARY]),
        routes=routes,
        spendable_set=SPENDABLE_AT_MONO,
    )
    dollars = next(
        v
        for v in block.verdicts
        if v.destination.venue_id == "broker" and v.destination.currency is USD
    )
    hryvnia = next(
        v
        for v in block.verdicts
        if v.destination.venue_id == "broker" and v.destination.currency is UAH
    )
    assert isinstance(dollars, Ready)
    assert isinstance(hryvnia, NotReady)
    assert NO_INBOUND in {deficit.kind for deficit in hryvnia.deficits}
    # Two balances at one venue are two verdicts. Counted here because ``_verdicts`` keys on
    # ``(venue_id, stream_id)`` and would silently collapse them into one -- which is exactly
    # the conflation this test exists to rule out, so it is asserted on the raw tuple.
    assert len([v for v in block.verdicts if v.destination.venue_id == "broker"]) == 2
