"""Every pair in the declared universe, exactly once. **FR-001, G1.**

FR-001: *the system MUST produce, for every declared destination x every declared income stream
x every declared regime, a verdict. **No pair in the declared universe may be silently absent
from the report.***

This is the property the whole feature rests on, and it is the one an example-based test cannot
establish. A pair that is *absent* looks, in every rendering of the report, exactly like a pair
that nobody asked about -- and an audit whose omissions are invisible is worse than no audit,
because it is believed. So the universe is recomputed here from the venue and stream
declarations, independently of anything the report did, and the verdicts are matched against it
in both directions: nothing missing, and nothing extra.

**The independence matters.** ``coverage`` builds its universe with
:func:`~terezy.core.routes.coverage.destinations`, so a property that called the same function
would be asserting that a function agrees with itself. The set below is built from
``Venue.currencies`` directly, in this module, which is the declaration the requirement is
actually about (FR-001 ⚙): *the universe is every declared venue x every currency it declares it
can hold*.

The other half of the requirement is per **regime**, and it is asserted the same way: every
block covers the same universe, because the destination universe is a property of the venues
rather than of any regime's route set. A regime that dropped the destinations nothing in it can
reach would hide precisely the holes the owner needs to see -- which is the reading this property
rules out.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings

from terezy.core.results.coverage import CoverageReport, Destination, NotReady, Ready
from terezy.core.routes.coverage import coverage
from tests.invariants.route_graphs import CoverageRegistry, coverage_registries

pytestmark = pytest.mark.invariant


def _declared_universe(registry: CoverageRegistry) -> set[tuple[Destination, str]]:
    """Venue x holdable currency x stream, built from the declarations and nothing else."""
    return {
        (Destination(venue_id=venue.id, currency=currency), stream_id)
        for venue in registry.venues.values()
        for currency in venue.currencies
        for stream_id in registry.streams
    }


@given(registry=coverage_registries())
@settings(max_examples=100, deadline=None)
def test_every_declared_pair_appears_exactly_once_in_every_regime(
    registry: CoverageRegistry,
) -> None:
    """**FR-001, G1.** Nothing absent, nothing duplicated, in each regime independently."""
    report = coverage(
        venues=registry.venues,
        streams=registry.streams,
        routes=registry.routes,
        regimes={},
        spendable=registry.spendable,
    )
    assert isinstance(report, CoverageReport)
    expected = _declared_universe(registry)

    for block in report.regimes:
        keys = [(verdict.destination, verdict.stream_id) for verdict in block.verdicts]
        assert len(keys) == len(set(keys)), f"{block.regime_id} reports a pair twice"
        assert set(keys) == expected, (
            f"{block.regime_id} does not cover the declared universe: "
            f"missing {sorted(expected - set(keys))}, extra {sorted(set(keys) - expected)}"
        )


@given(registry=coverage_registries())
@settings(max_examples=100, deadline=None)
def test_every_verdict_is_one_of_the_two_and_a_not_ready_one_always_says_why(
    registry: CoverageRegistry,
) -> None:
    """The union is closed, and there is no bare refusal in it (FR-003, G3).

    A ``NotReady`` with an empty ``deficits`` tuple would be the undifferentiated "missing
    route" FR-003 forbids, arriving through the back door: it would render as *not comparable*
    with nothing to act on. There is no code path that builds one, and this is the property
    that says so over generated registries rather than over the cases somebody thought of.
    """
    report = coverage(
        venues=registry.venues,
        streams=registry.streams,
        routes=registry.routes,
        regimes={},
        spendable=registry.spendable,
    )
    assert isinstance(report, CoverageReport)
    for block in report.regimes:
        for verdict in block.verdicts:
            assert isinstance(verdict, Ready | NotReady)
            if isinstance(verdict, NotReady):
                assert verdict.deficits, "a not-ready verdict carrying no reason is a bare refusal"
                # At most one inbound deficit and at most one exit deficit (research.md D7).
                kinds = [deficit.kind for deficit in verdict.deficits]
                assert len(kinds) == len(set(kinds)) <= 2
            else:
                assert verdict.exits, "a ready verdict resting on no exit is not ready"


@given(registry=coverage_registries())
@settings(max_examples=100, deadline=None)
def test_every_blocked_pair_is_a_pair_the_report_marked_not_ready(
    registry: CoverageRegistry,
) -> None:
    """The to-do list and the verdicts describe one registry (FR-009, G7, G8).

    Three claims that the counting could plausibly get wrong and that no example test would
    notice: a to-do entry's ``count`` is the length of its ``blocked`` tuple and nothing else;
    every pair it claims to block really was marked not ready; and a pair is marked
    alone-sufficient for a declaration exactly when that declaration is the **only** thing it
    is waiting for. The last is FR-011 -- necessary is not sufficient -- checked against the
    verdicts rather than against the entry that made the claim.
    """
    report = coverage(
        venues=registry.venues,
        streams=registry.streams,
        routes=registry.routes,
        regimes={},
        spendable=registry.spendable,
    )
    assert isinstance(report, CoverageReport)
    for block in report.regimes:
        deficit_count = {
            (verdict.destination, verdict.stream_id): len(verdict.deficits)
            for verdict in block.verdicts
            if isinstance(verdict, NotReady)
        }
        for entry in block.todo:
            assert entry.count == len(entry.blocked)
            assert entry.blocked, "a to-do item blocking nothing is not an observation to make"
            for pair in entry.blocked:
                key = (pair.destination, pair.stream_id)
                assert key in deficit_count, f"{key} is blocked but was not marked not ready"
                assert pair.alone_sufficient == (deficit_count[key] == 1)

        # Every deficit is accounted for by exactly one to-do entry, so no hole is reported to
        # the owner as a verdict and then dropped from the list of things to go and observe.
        claimed = sum(entry.count for entry in block.todo)
        assert claimed == sum(deficit_count.values())


@given(registry=coverage_registries())
@settings(max_examples=100, deadline=None)
def test_the_todo_list_is_ordered_and_its_ties_are_real(registry: CoverageRegistry) -> None:
    """Descending counts, and ``ties`` grouping exactly the equal-count runs (FR-010, G7)."""
    report = coverage(
        venues=registry.venues,
        streams=registry.streams,
        routes=registry.routes,
        regimes={},
        spendable=registry.spendable,
    )
    assert isinstance(report, CoverageReport)
    for block in report.regimes:
        counts = [entry.count for entry in block.todo]
        assert counts == sorted(counts, reverse=True)
        for group in block.ties:
            assert len(group) > 1, "a group of one is not a tie"
            assert len({counts[index] for index in group}) == 1
            assert list(group) == list(range(group[0], group[0] + len(group)))
        # Every equal-count run of two or more is reported, not just some of them.
        reported = {index for group in block.ties for index in group}
        for index, count in enumerate(counts):
            neighbours = {
                other for other, value in enumerate(counts) if value == count and other != index
            }
            assert bool(neighbours) == (index in reported)


@given(registry=coverage_registries())
@settings(max_examples=100, deadline=None)
def test_an_orphan_exit_is_never_a_deficit_and_never_blocks_a_count(
    registry: CoverageRegistry,
) -> None:
    """**FR-012, SC-017** over generated registries.

    An orphan exit leaves a destination no stream can reach. It is listed, and it must not
    leak into the to-do list -- an observation already made is not an observation to make, and
    sending the owner out to look at a corridor he has already looked at is the one instruction
    this report must never give.
    """
    report = coverage(
        venues=registry.venues,
        streams=registry.streams,
        routes=registry.routes,
        regimes={},
        spendable=registry.spendable,
    )
    assert isinstance(report, CoverageReport)
    for block in report.regimes:
        orphan_origins = {orphan.origin for orphan in block.orphan_exits}
        for orphan in block.orphan_exits:
            assert orphan.route_id in block.route_ids
        # An orphan's origin is unreachable, so every pair at that destination is not ready --
        # but for a *missing way in*, never for the way out the orphan already provides.
        for verdict in block.verdicts:
            if verdict.destination not in orphan_origins:
                continue
            assert isinstance(verdict, NotReady)
            assert "no_inbound" in {deficit.kind for deficit in verdict.deficits}

        # **The converse, which is the half that actually pins the rule.** Checking only that
        # every *listed* orphan is unreachable is satisfied by listing nothing, and equally by
        # listing too much -- it says nothing about the exits that were left off the list. So
        # the orphan set is derived here from the verdicts, independently of how the report
        # derived it, and the two must agree exactly.
        #
        # "Reachable" is the union of both ways money gets to a destination: a declared inbound
        # route, **and arrival**. Arrival is the term with no route behind it, so it is the one
        # a reachability test can silently stop counting -- and dropping it turns every exit
        # from a stream's own arrival venue into a phantom orphan.
        reached = {
            verdict.destination
            for verdict in block.verdicts
            if isinstance(verdict, Ready) or verdict.inbound != ()
        }
        expected = {
            route_id
            for route_id in block.route_ids
            if (declared := registry.routes[route_id]).direction == "exit"
            and Destination(venue_id=declared.origin, currency=declared.legs[0].from_ccy)
            not in reached
        }
        assert {orphan.route_id for orphan in block.orphan_exits} == expected
