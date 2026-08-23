"""SC-008 and SC-012: what a chain refuses, which segment refused, and which world it ran in.

Two requirements, and they fail in opposite directions if either is missed.

**FR-015** -- a composed candidate containing any segment closed, disrupted by status, or
outside its availability window on the date is **excluded with the binding segment and
constraint recorded, never silently omitted**. An unexecutable plan reported as executable is
the top-severity defect class, and a silent exclusion is how a comparison comes to recommend the
only candidate left standing.

**FR-017** -- every segment of a candidate belongs to the route set of the **single** regime in
force on the contribution date. A chain that connected by taking one corridor from wartime and
the next from the normalized regime would be a journey nobody believes in under either, and it
would look exactly like a real corridor in the output.

## Why the binding segment is a field and not a sentence

On a declared route, ``binding_constraint = "leg.minimum"`` is actionable: there is one
declaration to open. On a three-segment chain it is not, and a reader would have to open every
one of them to find out which. So the segment travels with the refusal -- and it is ``None`` on
a declared route, where ``path`` already names the only route there is, because the same fact in
two places eventually disagrees.
"""

from __future__ import annotations

import dataclasses
from datetime import date

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.composed import Enumeration, SegmentBound
from terezy.core.results.ramp import RampCost, Ranking, RouteUnusable
from terezy.core.routes import compose, cost, ranking
from terezy.core.routes.legs import Route
from terezy.core.routes.path import (
    ComposedExit,
    ComposedPath,
    FundingPath,
    Journey,
    Segment,
    candidate_id,
)
from terezy.core.scenarios import regimes
from tests import composed_registries as fixtures

AMOUNT = Money(10_000.0, Currency.UAH, prov.EMPTY)
EXIT_CHAIN = ComposedExit(segments=("out_broker_to_exchange", "out_exchange_to_home"))
CHAIN = ComposedPath(
    destination_id=fixtures.BROKER,
    stream_id=fixtures.SALARY.id,
    segments=("in_salary_to_exchange", "in_exchange_to_broker"),
)


def _world(**edits: Route) -> dict[str, Route]:
    """The two-hop registry with named routes replaced."""
    return {**fixtures.two_hop().routes, **{route.id: route for route in edits.values()}}


def _costed(routes: dict[str, Route], amount: Money = AMOUNT) -> RampCost | RouteUnusable:
    world = fixtures.two_hop()
    return cost.cost_one(
        CHAIN,
        amount,
        exit_path=EXIT_CHAIN,
        routes=routes,
        channels=world.channels,
        streams=world.streams,
        kinds=world.kinds,
        on_date=fixtures.ON_DATE,
        as_of=fixtures.AS_OF,
    )


class TestAClosedSegmentExcludesTheChainAndSaysWhichOne:
    """SC-008. The exclusion appears in the output rather than leaving a silence."""

    def test_a_closed_second_segment_refuses_the_whole_chain(self) -> None:
        shut = dataclasses.replace(fixtures.EXCHANGE_TO_BROKER, status="closed")
        outcome = _costed(_world(second=shut))
        assert isinstance(outcome, RouteUnusable), outcome
        assert outcome.binding_constraint == "route.status"
        assert outcome.binding_segment == Segment(position=1, route_id="in_exchange_to_broker")

    def test_the_first_closed_segment_is_the_one_named(self) -> None:
        """Two segments can be shut at once, and the one reported is the one the money meets
        first -- the order the owner would fix them in."""
        routes = _world(
            first=dataclasses.replace(fixtures.SALARY_TO_EXCHANGE, status="closed"),
            second=dataclasses.replace(fixtures.EXCHANGE_TO_BROKER, status="closed"),
        )
        outcome = _costed(routes)
        assert isinstance(outcome, RouteUnusable), outcome
        assert outcome.binding_segment == Segment(position=0, route_id="in_salary_to_exchange")

    def test_a_declared_route_names_no_segment_because_the_path_already_does(self) -> None:
        """``None`` here is not a gap: a ``FundingPath`` carries the one route there is, and a
        ``Segment(position=0, ...)`` beside it would read as one selected out of several."""
        world = fixtures.two_hop()
        shut = dataclasses.replace(fixtures.SALARY_TO_EXCHANGE, status="closed")
        outcome = cost.cost_one(
            FundingPath(
                destination_id=fixtures.EXCHANGE,
                stream_id=fixtures.SALARY.id,
                route_id=fixtures.SALARY_TO_EXCHANGE.id,
            ),
            AMOUNT,
            routes={**world.routes, shut.id: shut},
            channels=world.channels,
            streams=world.streams,
            kinds=world.kinds,
            on_date=fixtures.ON_DATE,
            as_of=fixtures.AS_OF,
        )
        assert isinstance(outcome, RouteUnusable), outcome
        assert outcome.binding_segment is None

    def test_the_exclusion_is_visible_in_the_ranking_rather_than_silent(self) -> None:
        """FR-014. A candidate that fell out of a comparison without landing in ``excluded``
        would be invisible, and an invisible exclusion is how a ranking comes to recommend the
        only route left standing."""
        world = fixtures.two_hop()
        shut = dataclasses.replace(fixtures.EXCHANGE_TO_BROKER, status="closed")
        outcome = ranking.rank(
            [Journey(path=CHAIN, exit_path=EXIT_CHAIN)],
            AMOUNT,
            routes={**world.routes, shut.id: shut},
            channels=world.channels,
            streams=world.streams,
            kinds=world.kinds,
            on_date=fixtures.ON_DATE,
            as_of=fixtures.AS_OF,
        )
        assert not isinstance(outcome, Ranking)
        (excluded,) = outcome.excluded
        assert candidate_id(excluded.path) == "in_salary_to_exchange+in_exchange_to_broker"
        assert excluded.binding_segment == Segment(position=1, route_id="in_exchange_to_broker")
        assert "closed" in excluded.reason


class TestAConstraintOnASegmentNamesTheShortfallAndTheSegment:
    def test_an_amount_below_a_minimum_anywhere_along_the_chain_is_reported(self) -> None:
        """FR-014 across composition: never silently rounded up.

        The minimum is on the **second** segment and is declared in dollars, so the refusal is
        about a leg the money reaches only after a conversion -- which is exactly the case a
        per-route check would get right and a chain-blind one would miss.
        """
        strict = dataclasses.replace(
            fixtures.EXCHANGE_TO_BROKER,
            legs=(
                dataclasses.replace(
                    fixtures.EXCHANGE_TO_BROKER.legs[0],
                    minimum=Money(1_000.0, Currency.USD, prov.EMPTY),
                ),
            ),
        )
        outcome = _costed(_world(second=strict))
        assert isinstance(outcome, RouteUnusable), outcome
        assert outcome.binding_constraint == "leg.minimum"
        assert outcome.binding_segment == Segment(position=1, route_id="in_exchange_to_broker")
        assert outcome.required is not None
        assert outcome.shortfall is not None
        assert is_close(outcome.required.amount, 1_000.0)
        # 1 000 asked for, 222.222222 arrived at the exchange: the shortfall is the difference,
        # reported rather than rounded away.
        assert is_close(outcome.shortfall.amount, 1_000.0 - 10_000.0 / 45.0)

    def test_an_out_of_window_segment_names_the_window_and_the_segment(self) -> None:
        """A leg's window is a **fact** about the corridor with a source -- "this closed in
        March 2025" -- never an assumption. The assumption is a regime, tested below."""
        shut = dataclasses.replace(
            fixtures.EXCHANGE_TO_BROKER,
            legs=(
                dataclasses.replace(
                    fixtures.EXCHANGE_TO_BROKER.legs[0], available_until=date(2026, 1, 1)
                ),
            ),
        )
        outcome = _costed(_world(second=shut))
        assert isinstance(outcome, RouteUnusable), outcome
        assert outcome.binding_constraint == "leg.available_until"
        assert outcome.binding_segment == Segment(position=1, route_id="in_exchange_to_broker")


# ---------------------------------------------------------------------------
# SC-012: one regime per candidate, on a registry where only a mixed chain connects
# ---------------------------------------------------------------------------

WARTIME = regimes.Regime(id="wartime", route_ids=frozenset({"in_salary_to_exchange"}))
NORMALIZED = regimes.Regime(id="normalized", route_ids=frozenset({"in_exchange_to_broker"}))
REGIMES = {WARTIME.id: WARTIME, NORMALIZED.id: NORMALIZED}
"""The two halves of the corridor, one in each regime and neither in both.

**The registry is built so that only a mixed chain would connect.** Under wartime the money can
reach the exchange and stop; under the normalized regime the second hop exists but nothing
declares a way to the exchange. So a search that took the union -- or that narrowed the routes
once and then forgot -- would produce a candidate reaching the broker under *both* dates, and
the figure beside it would look entirely ordinary.
"""

TRANSITION = regimes.RegimeTransition(
    on_date=date(2027, 1, 1),
    before=WARTIME.id,
    after=NORMALIZED.id,
    is_assumption=True,
    rationale="SYNTHETIC FIXTURE -- an invented date, so the fixture states what it is.",
)

BEFORE = date(2026, 8, 21)
AFTER = date(2027, 8, 21)


def _in_force(on_date: date) -> regimes.RoutesInForce:
    return regimes.routes_in_force(
        REGIMES, fixtures.two_hop().routes, transitions=(TRANSITION,), on_date=on_date
    )


def _enumerated(on_date: date) -> Enumeration:
    in_force = _in_force(on_date)
    world = fixtures.two_hop()
    result = compose.compose(
        routes=in_force.routes,
        stream=world.streams[fixtures.SALARY.id],
        destination=fixtures.BROKER_USD,
        direction="inbound",
        regime_id=in_force.regime.id,
        bound=SegmentBound(max_segments=3),
        spendable=world.spendable,
    )
    assert isinstance(result, Enumeration), result
    return result


class TestNoCandidateMixesRouteSetsAcrossARegimeTransition:
    def test_the_whole_registry_does_connect_so_the_absence_below_means_something(self) -> None:
        """The positive control. Without it, both assertions below would pass on a registry
        where the corridor simply does not exist."""
        world = fixtures.two_hop()
        result = compose.compose(
            routes=world.routes,
            stream=world.streams[fixtures.SALARY.id],
            destination=fixtures.BROKER_USD,
            direction="inbound",
            regime_id=fixtures.REGIME_ID,
            bound=SegmentBound(max_segments=3),
            spendable=world.spendable,
        )
        assert isinstance(result, Enumeration)
        assert [candidate_id(candidate) for candidate in result.candidates] == [
            "in_salary_to_exchange+in_exchange_to_broker"
        ]

    def test_before_the_transition_only_the_first_regimes_routes_are_searched(self) -> None:
        enumerated = _enumerated(BEFORE)
        assert enumerated.regime_id == WARTIME.id
        assert enumerated.candidates == ()

    def test_after_the_transition_only_the_second_regimes_routes_are_searched(self) -> None:
        enumerated = _enumerated(AFTER)
        assert enumerated.regime_id == NORMALIZED.id
        assert enumerated.candidates == ()

    def test_the_regime_in_force_travels_with_the_candidates_it_produced(self) -> None:
        """A report is only reproducible if the world it assumed is recorded. The id is on the
        enumeration; the belief that chose it stays in ``RoutesInForce.decided_by``, where an
        output can show it as the assumption it is."""
        assert _in_force(BEFORE).decided_by is TRANSITION
        assert _enumerated(BEFORE).regime_id == _in_force(BEFORE).regime.id

    def test_a_chain_is_dropped_when_any_one_segment_is_out_of_force(self) -> None:
        """``paths_in_force`` narrows a chain by **every** segment, not merely by its first.

        The filtering is not silent: what it removes is exactly the routes the selection
        already reported as excluded, so a reader can see the belief beside the figures it
        changed.
        """
        in_force = _in_force(BEFORE)
        assert regimes.paths_in_force([CHAIN], in_force) == ()
        assert "in_exchange_to_broker" in in_force.excluded
