"""Two views of one registry never disagree about what is comparable. **SC-009, FR-018.**

FR-018: *a pair marked comparison-ready MUST be one for which feature 002's costing can produce
a round-trip figure, and a pair whose costing over single declared routes is refused (no route,
or "exit cost unknown") MUST NOT be marked ready.*

The report and the costing engine answer the same question by different means -- one folds over
declarations, the other walks legs and charges fees -- and the whole value of the report rests on
them agreeing. If they can disagree, the owner has two tools telling him different things about
the same registry and no way to know which is lying.

## Read the scope before debugging a failure

The property covers costing's **route-existence** refusals, and only those (research.md D11):

* *no matching route* -- no ``FundingPath`` over a declared route carries this stream's money to
  this destination at all, which ``cost_one`` reports as a funding mismatch naming
  ``stream.arrives_at`` or ``stream.amount.currency``;
* *``ExitCostUnknown``* -- the way in is costable and nobody has declared the way out.

It does **not** cover ``RouteUnusable`` for a binding limit, a closed window or a closed route
-- including, since 002's review, **a closed exit partner**, which ``cost_one`` now reports as
``ExitCostUnknown`` while coverage still counts the closed exit as *declared*. Those are all
statements about **today**, and coverage is a statement about **declarations** (FR-022 ⚙): a
closed corridor is already observed, and telling the owner to go and observe it would be the
wrong instruction. So the generator holds amount, dates and statuses where feasibility cannot
bite, and every one of those scoping decisions is written out at
``route_graphs.coverage_registries``.

**Nor does it cover a pair costing has no ``FundingPath`` for at all.** A ``FundingPath`` is a
``(destination, stream, route)`` triple, and the *route* in it is the way **in**: so a pair
whose inbound half is satisfied by *arrival* names no route, costing is never asked about it,
and it produces neither a figure nor a refusal. That pair is outside the agreement's **domain**
rather than in disagreement with it -- the two views answer the same question about corridors,
and this one needs no corridor on the way in. Such pairs are partitioned out below **and
asserted on**, rather than skipped, so the exclusion cannot quietly swallow a real
disagreement.

⚙ **The exit half is not part of that exclusion, and saying it was is a correction of
2026-08-23.** This note first read "arrival *and/or* identity", which is false for identity: a
pair whose exit half is satisfied because the destination *is* the spendable endpoint (FR-002)
still has a declared route on the way in, so a ``FundingPath`` exists, and where that inbound
names a partner exit ``cost_one`` returns a ``RoundTripCost``. Coverage says ready, costing
produces a figure, **the two agree** -- and the widened partition excluded the pair and then
asserted no figure existed for it, a tripwire that fires on agreement. It was latent only
because the generator never routed an inbound into ``HOME_VENUE``. It does now, drawn, so the
corrected partition is exercised rather than argued (``route_graphs.SPENDABLE_INBOUND``).

**If this test fails with a ``RouteUnusable``, the generator has drifted into feasibility
territory. Fix the generator's amounts, dates and limits -- never the coverage rule.** The
temptation runs the other way, because weakening the audit makes the red go away and produces a
report that is quietly wrong about the registry, which is the failure this whole feature exists
to prevent.

## What will have to change, and when

Feature 004 composes multi-route paths, and the owner has already decided (in 004's
clarification) that a chain of separately declared exit segments satisfies feature 002's FR-027.
So once composition lands, costing will produce round-trip figures for pairs **this report marks
not-ready**, and the second half of the property below will start failing on registries where a
two-hop way out exists.

The reconciliation is written into ``contracts/coverage-report.md`` and it is not a change to
this assertion's strictness: coverage gains a distinct *"reachable by composition only"*
annotation, computed by chaining declarations -- pure, no costing -- and the two views stay
reconciled through that annotation. ``Ready`` keeps meaning exactly what it means here. The
generator today is partner-closed, so no such pair is produced and the property holds as written.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings

from terezy.core.results.coverage import (
    SATISFIED_BY_IDENTITY,
    CoverageReport,
    NotReady,
    Ready,
    SpendableEndpoint,
)
from terezy.core.results.ramp import ExitCostUnknown, RampCost, RoundTripCost, RouteUnusable
from terezy.core.routes.cost import cost_one
from terezy.core.routes.coverage import coverage
from terezy.core.routes.path import EXIT_BY_IDENTITY, FundingPath
from tests.invariants import route_graphs
from tests.invariants.route_graphs import CoverageRegistry, coverage_registries

pytestmark = pytest.mark.invariant


def _costed(
    registry: CoverageRegistry, destination_venue: str, stream_id: str
) -> list[RampCost | RouteUnusable]:
    """What costing says about every declared route that ends at this venue.

    Built from the **routes** rather than from anything coverage computed, which is what keeps
    the property from being circular: coverage's matcher is the thing under test, so the paths
    here are every route whose declared destination is this venue, and ``cost_one`` is left to
    refuse the ones that cannot carry this stream's money. Its refusal *is* the second view's
    answer to "is there a way in".
    """
    return [
        cost_one(
            FundingPath(destination_id=destination_venue, stream_id=stream_id, route_id=route.id),
            route_graphs.COVERAGE_AMOUNTS[stream_id],
            routes=registry.routes,
            channels=registry.channels,
            streams=registry.streams,
            kinds=route_graphs.KINDS,
            on_date=route_graphs.ON_DATE,
            as_of=route_graphs.AS_OF,
            spendable=registry.spendable,
        )
        for route in registry.routes.values()
        if route.destination == destination_venue
    ]


def _round_trips(outcomes: list[RampCost | RouteUnusable]) -> list[RoundTripCost]:
    return [
        outcome.round_trip
        for outcome in outcomes
        if isinstance(outcome, RampCost) and isinstance(outcome.round_trip, RoundTripCost)
    ]


def _assert_in_scope(outcomes: list[RampCost | RouteUnusable]) -> None:
    """Every refusal the generator produced must be a route-existence one (research.md D11).

    Asserted rather than assumed, and asserted **here** rather than left to surface as a
    confusing failure of the real property. A ``RouteUnusable`` naming a limit, a window or a
    status means the generator drifted out of scope, and this assertion says so in those words
    so nobody reaches for the coverage rule to make it green.
    """
    for outcome in outcomes:
        if isinstance(outcome, RouteUnusable):
            assert outcome.binding_constraint in {
                "stream.arrives_at",
                "stream.amount.currency",
            }, (
                f"the generator produced a feasibility refusal ({outcome.binding_constraint}), "
                "which FR-018's agreement is deliberately not about: that is a statement about "
                "today, and coverage is a statement about declarations (research.md D11). Fix "
                "route_graphs.coverage_registries -- never the coverage rule."
            )


def _is_costable(verdict: Ready) -> bool:
    """Whether costing has a ``FundingPath`` for this ready pair at all.

    **The inbound half alone decides it**, and that is the correction of 2026-08-23. A
    ``FundingPath`` is ``(destination, stream, route)`` where the route is the way *in*: a pair
    reached by *arrival* names none, so costing is never asked and has no opinion to agree or
    disagree with. The exit half is a different matter -- a verdict whose exit is satisfied by
    *identity* still names an inbound route, so costing has a path, walks it, and (where that
    inbound declares its partner) produces the round-trip figure. Excluding it would put a pair
    the two views **agree** about outside the domain, and then assert there was no figure for
    it.
    """
    return isinstance(verdict.inbound, tuple)


@given(registry=coverage_registries())
@settings(max_examples=100, deadline=None)
def test_a_ready_pair_is_one_costing_produces_a_round_trip_for(
    registry: CoverageRegistry,
) -> None:
    """**SC-009's first half.** Ready means a round-trip figure exists over a declared route."""
    report = coverage(
        venues=registry.venues,
        streams=registry.streams,
        routes=registry.routes,
        regimes={},
        spendable=registry.spendable,
    )
    assert isinstance(report, CoverageReport)
    (block,) = report.regimes

    for verdict in block.verdicts:
        if not isinstance(verdict, Ready):
            continue
        outcomes = _costed(registry, verdict.destination.venue_id, verdict.stream_id)
        _assert_in_scope(outcomes)
        if not _is_costable(verdict):
            _ARRIVAL_BACKED.add((verdict.destination.venue_id, verdict.stream_id))
            # Outside the domain, and asserted to be outside it rather than merely skipped:
            # the money is born at this destination, so no ``FundingPath`` names it and costing
            # produces no figure. If a future generator ever makes one costable, this fails and
            # sends the reader to the scope note above instead of letting the partition hide a
            # real disagreement.
            assert not _round_trips(outcomes), (
                f"{verdict.destination.venue_id}/{verdict.stream_id} is ready by arrival -- no "
                "declared route carries this stream in -- and costing produced a round-trip "
                "figure for it anyway, so it is *inside* the agreement's domain after all and "
                "the partition above is wrong."
            )
            continue
        assert _round_trips(outcomes), (
            f"coverage marked {verdict.destination.venue_id}/{verdict.stream_id} ready, and "
            "costing produced no round-trip figure for it over any declared route. The two "
            "views of one registry must not disagree about what is comparable (FR-018)."
        )
        _ROUTE_BACKED.add((verdict.destination.venue_id, verdict.stream_id))
        if not isinstance(verdict.exits, tuple):
            _IDENTITY_BACKED.add((verdict.destination.venue_id, verdict.stream_id))


_ROUTE_BACKED: set[tuple[str, str]] = set()
"""Ready pairs the agreement actually constrained, accumulated across examples."""

_ARRIVAL_BACKED: set[tuple[str, str]] = set()
"""Ready pairs excluded from the domain because no declared route carries the money in."""

_IDENTITY_BACKED: set[tuple[str, str]] = set()
"""Constrained pairs whose *exit* half was a sentinel: ready on a route in and identity out.

The shape the old partition wrongly excluded. Tallied separately so the corrected partition is
provably exercised rather than merely believed.
"""


@given(registry=coverage_registries())
@settings(max_examples=100, deadline=None)
def test_a_not_ready_pair_is_one_costing_refuses_over_single_declared_routes(
    registry: CoverageRegistry,
) -> None:
    """**SC-009's second half.** Not ready means every single-route costing is refused.

    Either nothing matched at all -- ``cost_one`` refused the funding, which is its way of
    saying there is no such route -- or something matched and yielded ``ExitCostUnknown``,
    which is feature 002's FR-030 refusal and the same fact this report calls a missing way
    out. What may **not** happen is a round-trip figure existing for a pair the audit called a
    hole.
    """
    report = coverage(
        venues=registry.venues,
        streams=registry.streams,
        routes=registry.routes,
        regimes={},
        spendable=registry.spendable,
    )
    assert isinstance(report, CoverageReport)
    (block,) = report.regimes

    for verdict in block.verdicts:
        if not isinstance(verdict, NotReady):
            continue
        outcomes = _costed(registry, verdict.destination.venue_id, verdict.stream_id)
        _assert_in_scope(outcomes)
        assert not _round_trips(outcomes), (
            f"coverage marked {verdict.destination.venue_id}/{verdict.stream_id} not ready, "
            "and costing produced a round-trip figure for it. Within this feature's "
            "single-route scope the two views must agree; a pair reachable only by composing "
            "two declared routes is feature 004's, and it is reconciled by a distinct "
            "annotation rather than by loosening this assertion."
        )
        # And the refusals are the two kinds the scope names, rather than anything else.
        for outcome in outcomes:
            if isinstance(outcome, RampCost):
                assert isinstance(outcome.round_trip, ExitCostUnknown)


@given(registry=coverage_registries())
@settings(max_examples=50, deadline=None)
def test_the_generator_reaches_both_verdicts(registry: CoverageRegistry) -> None:
    """A property both halves of which pass vacuously is not a property.

    ``hypothesis`` will report the distribution if this ever starts failing, but the cheap
    version of the check is that a single generated registry is not always all-ready or
    all-not-ready. Asserted across the run rather than per example, using the module-level
    tally below -- the same trick ``event_streams`` uses for its own coverage of the two ledger
    outcomes.
    """
    report = coverage(
        venues=registry.venues,
        streams=registry.streams,
        routes=registry.routes,
        regimes={},
        spendable=registry.spendable,
    )
    assert isinstance(report, CoverageReport)
    (block,) = report.regimes
    _SEEN.update(type(verdict).__name__ for verdict in block.verdicts)


_SEEN: set[str] = set()
"""Which verdict types the generated battery actually produced, accumulated across examples."""


def test_the_agreement_constrained_real_pairs_and_the_exclusion_is_not_everything() -> None:
    """The partition above is only honest if both sides of it are non-empty.

    A property that excluded every ready pair would pass for the worst possible reason. Runs
    after the two properties, which pytest orders within a file.

    The third assertion is the one the 2026-08-23 correction owes: the corrected partition
    keeps *exit-by-identity* pairs inside the domain, and a partition nothing ever falls on the
    inside of is a partition nobody has tested.
    """
    assert _ROUTE_BACKED, "the agreement never constrained a single route-backed ready pair"
    assert _ARRIVAL_BACKED, "the arrival exclusion never fired; the note above is untested"
    assert _IDENTITY_BACKED, (
        "no ready pair was constrained whose exit half is the identity sentinel, so the "
        "corrected partition is argued and not exercised. The generator's drawn way in to the "
        "spendable endpoint (route_graphs.SPENDABLE_INBOUND) is what produces it."
    )


def test_the_battery_produced_both_ready_and_not_ready_verdicts() -> None:
    """Runs after the property above and checks it was not vacuous.

    Depends on test order within the module, which pytest guarantees for a single file. If it
    ever fails, the generator has stopped producing one of the two shapes and the two
    properties above have been passing for the wrong reason.
    """
    assert {"Ready", "NotReady"} == _SEEN, f"the battery only produced {_SEEN or 'nothing'}"


# ---------------------------------------------------------------------------
# 004-composed-paths: the reconciliation, pinned rather than drawn
# ---------------------------------------------------------------------------


def _identity_registry() -> CoverageRegistry:
    """One inbound route landing on the spendable endpoint, declaring **no** partner.

    The exact shape ``features.toml`` recorded as ``identity-exit-vs-partner-requirement``:
    coverage marks the pair ready because the money has arrived where the owner spends (003
    FR-002), while 002's costing found no ``partner_route`` and refused with
    ``ExitCostUnknown`` -- the FR-018 disagreement that entry says must not exist.

    Built by hand rather than drawn, because the generator reaches this shape by a coin flip and
    a reconciliation that a re-seed can skip is not pinned.
    """
    return CoverageRegistry(
        venues={
            route_graphs.HOME_VENUE: route_graphs.venues_for_agreement()[0],
            route_graphs.CONTRACT_VENUE: route_graphs.venues_for_agreement()[1],
        },
        streams=route_graphs.COVERAGE_STREAMS,
        routes={
            route_graphs.SPENDABLE_INBOUND: route_graphs.spendable_inbound(partner=None),
        },
        channels=route_graphs.AGREEMENT_CHANNELS,
        spendable=frozenset(
            {
                SpendableEndpoint(
                    venue_id=route_graphs.HOME_VENUE, currency=route_graphs.BASE_CURRENCY
                )
            }
        ),
    )


def _verdict_for(report: CoverageReport, venue: str, stream_id: str) -> Ready | NotReady:
    (block,) = report.regimes
    for verdict in block.verdicts:
        if verdict.destination.venue_id == venue and verdict.stream_id == stream_id:
            return verdict
    raise AssertionError(f"no verdict for {venue!r} and {stream_id!r}")


def test_a_spendable_destination_with_no_partner_is_ready_and_costing_agrees() -> None:
    """**The closed tension, run through both views on one registry.**

    Coverage is *invoked*, not restated: a hand-written precondition asserting what coverage
    would say is a second implementation of the rule under test, and it agrees with itself by
    construction. So this builds one registry, folds it through ``coverage``, walks it through
    ``cost_one``, and asserts the two reach the same verdict about the same pair.

    Without the derivation in ``_exit_chain_of`` this fails exactly as the recorded entry
    described: ``Ready`` on one side, ``ExitCostUnknown`` on the other.
    """
    registry = _identity_registry()
    report = coverage(
        venues=registry.venues,
        streams=registry.streams,
        routes=registry.routes,
        regimes={},
        spendable=registry.spendable,
    )
    assert isinstance(report, CoverageReport), report
    verdict = _verdict_for(report, route_graphs.HOME_VENUE, route_graphs.COVERAGE_CONTRACT.id)
    assert isinstance(verdict, Ready), verdict
    assert verdict.exits is SATISFIED_BY_IDENTITY, verdict.exits

    (costed,) = _costed(registry, route_graphs.HOME_VENUE, route_graphs.COVERAGE_CONTRACT.id)
    assert isinstance(costed, RampCost), costed
    assert isinstance(costed.round_trip, RoundTripCost), costed.round_trip
    assert costed.exit_path is EXIT_BY_IDENTITY
