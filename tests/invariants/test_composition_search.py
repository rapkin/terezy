"""The search stays a search: no venue twice, nothing past the bound, no direction mixed.

Three requirements, each verified **over the entire emitted set** rather than sampled, because
each is a claim about *every* candidate and a spot check on the first one would pass under a
search that got the fourth wrong:

* **SC-004** -- in a registry whose route graph contains a cycle, zero candidates visit any
  venue twice. Venues are the nodes, so a chain that would revisit one is never emitted, even
  in a different currency (spec Assumptions).
* **SC-005** -- with a declared bound of ``n``, no candidate has more than ``n`` segments,
  **every** connectable chain of at most ``n`` appears, and the bound is visible in the result.
* **SC-016** -- no candidate mixes directions, including in a registry where the only way to
  complete an inbound chain runs through a route declared ``exit`` (FR-022).

**Exhaustiveness is checked against a second enumerator, written independently below.** A
property comparing the search with itself would pass under any pruning at all; the brute-force
walk in :func:`_every_chain` is deliberately naive -- no index, no sorting, no visited-set
optimisation, just every permutation of routes that happens to join -- so agreement between the
two is agreement between two ways of reading the declarations rather than one way twice.

The registries come from :func:`~tests.invariants.route_graphs.composition_registries`, whose
every ordered pair of venues is a coin flip in each direction. Cycles, over-long corridors and
direction traps are the ordinary draw there rather than hand-written cases.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import pairwise, permutations

import pytest
from hypothesis import given, settings

from terezy.core.results.composed import CompositionRefused, Enumeration, SegmentBound
from terezy.core.results.coverage import Destination
from terezy.core.routes import compose
from terezy.core.routes.legs import Route, RouteDirection
from terezy.core.routes.path import segments_of
from tests import composed_registries as fixtures
from tests.invariants import route_graphs
from tests.invariants.route_graphs import CompositionRegistry

pytestmark = pytest.mark.invariant

REGIME = "generated"
"""The regime id every enumeration below is asked for. A string, because the search never sees
a regime record -- the narrowing is the caller's, and what travels onto the result is the fact
of which world was searched."""


def _enumerate(
    registry: CompositionRegistry,
    *,
    direction: RouteDirection = "inbound",
    max_segments: int = 3,
) -> Enumeration:
    result = compose.compose(
        routes=registry.routes,
        stream=registry.stream,
        destination=registry.destination,
        direction=direction,
        regime_id=REGIME,
        bound=SegmentBound(max_segments=max_segments),
        spendable=registry.spendable,
    )
    assert isinstance(result, Enumeration), result
    return result


def _venues(routes: Mapping[str, Route], chain: Sequence[str]) -> list[str]:
    """Every venue a chain passes through, start included -- the nodes the search walked."""
    return [routes[chain[0]].origin, *(routes[route_id].destination for route_id in chain)]


def _joins(before: Route, after: Route) -> bool:
    """Whether two segments meet at a venue **and** in a currency. Written out here rather than
    imported, so the second enumerator does not borrow the first one's idea of connecting."""
    return before.destination == after.origin and before.legs[-1].to_ccy is after.legs[0].from_ccy


def _every_chain(
    routes: Mapping[str, Route],
    *,
    direction: RouteDirection,
    start: tuple[str, str],
    targets: frozenset[tuple[str, str]],
    max_segments: int,
) -> set[tuple[str, ...]]:
    """Every connectable chain within the bound, found by brute force over permutations.

    The independent reading of the declarations. It is quadratic in the worst case and would be
    unusable on a real registry -- which is the point: it cannot share a bug with the depth-first
    walk under test, because it shares no structure with it.
    """
    usable = [route for route in routes.values() if route.direction == direction]
    found: set[tuple[str, ...]] = set()
    for length in range(1, max_segments + 1):
        for chain in permutations(usable, length):
            if (chain[0].origin, chain[0].legs[0].from_ccy.value) != start:
                continue
            if (chain[-1].destination, chain[-1].legs[-1].to_ccy.value) not in targets:
                continue
            if not all(_joins(before, after) for before, after in pairwise(chain)):
                continue
            venues = [chain[0].origin, *(route.destination for route in chain)]
            if len(set(venues)) != len(venues):
                continue
            found.add(tuple(route.id for route in chain))
    return found


@settings(max_examples=60, deadline=None)
@given(registry=route_graphs.composition_registries())
def test_no_candidate_visits_a_venue_twice(registry: CompositionRegistry) -> None:
    """SC-004, over the entire emitted set.

    The generator flips a coin on **both** directions of every ordered pair, so a two-cycle is
    the ordinary draw and a search without a visited-venue set would recur forever rather than
    emit a bad candidate. That it terminates at all is half the assertion; that no emitted chain
    repeats a node is the other half.
    """
    for candidate in _enumerate(registry).candidates:
        venues = _venues(registry.routes, segments_of(candidate))
        assert len(set(venues)) == len(venues), (candidate, venues)


@settings(max_examples=60, deadline=None)
@given(registry=route_graphs.composition_registries())
def test_the_bound_is_respected_and_travels_with_the_result(
    registry: CompositionRegistry,
) -> None:
    """SC-005's first and third clauses: nothing longer than ``n``, and ``n`` is in the answer.

    The bound in the result is what makes a missing corridor attributable. Without it, a
    corridor needing four hops under a bound of two is indistinguishable from a corridor nobody
    declared -- and the owner's remedy for those two is opposite.
    """
    for bound in (1, 2, 3):
        enumerated = _enumerate(registry, max_segments=bound)
        assert enumerated.bound.max_segments == bound
        assert enumerated.regime_id == REGIME
        assert all(len(segments_of(c)) <= bound for c in enumerated.candidates)


@settings(max_examples=60, deadline=None)
@given(registry=route_graphs.composition_registries())
def test_every_connectable_chain_within_the_bound_appears(
    registry: CompositionRegistry,
) -> None:
    """SC-005's second clause, against the independently written enumerator.

    **Duplicate suppression is the one difference allowed**, and it is subtracted rather than
    waved through: a chain the brute-force walk finds may be missing from the search only when
    another emitted chain has the identical leg sequence (FR-009). Every other absence is a
    candidate that was dropped, which is what FR-007 forbids.
    """
    bound = 3
    enumerated = _enumerate(registry, max_segments=bound)
    emitted = {segments_of(candidate) for candidate in enumerated.candidates}
    expected = _every_chain(
        registry.routes,
        direction="inbound",
        start=(registry.stream.arrives_at, registry.stream.amount.currency.value),
        targets=frozenset({(registry.destination.venue_id, registry.destination.currency.value)}),
        max_segments=bound,
    )
    legs_emitted = {_leg_shape(registry.routes, chain) for chain in emitted}
    unexplained = [
        chain
        for chain in expected - emitted
        if _leg_shape(registry.routes, chain) not in legs_emitted
    ]
    assert not unexplained, unexplained
    assert emitted <= expected, emitted - expected


def _leg_shape(routes: Mapping[str, Route], chain: Sequence[str]) -> tuple[object, ...]:
    """A chain's legs as a comparable tuple, index renumbered -- FR-009's identity, restated.

    Restated rather than imported for the reason the second enumerator exists: a duplicate rule
    checked with the implementation's own comparison would be checking that the code agrees with
    itself.
    """
    return tuple(
        (position, leg.from_venue, leg.to_venue, leg.from_ccy, leg.to_ccy, leg.fee_pct)
        for position, leg in enumerate(leg for route_id in chain for leg in routes[route_id].legs)
    )


@settings(max_examples=60, deadline=None)
@given(registry=route_graphs.composition_registries())
def test_no_candidate_mixes_directions(registry: CompositionRegistry) -> None:
    """SC-016, over the entire emitted set and in both directions.

    The generator declares both directions of most pairs, so a registry where the only
    completion of an inbound chain runs through a route declared ``exit`` is routine. An
    observation of a corridor one way says nothing about its terms, its limits or its existence
    the other way, so treating one as the other would invent a corridor nobody observed.
    """
    for direction in ("inbound", "exit"):
        result = compose.compose(
            routes=registry.routes,
            stream=registry.stream,
            destination=registry.destination,
            direction=direction,
            regime_id=REGIME,
            bound=SegmentBound(max_segments=3),
            spendable=registry.spendable,
        )
        if isinstance(result, CompositionRefused):
            continue
        for candidate in result.candidates:
            declared = {registry.routes[rid].direction for rid in segments_of(candidate)}
            assert declared == {direction}, (direction, candidate)


@settings(max_examples=40, deadline=None)
@given(registry=route_graphs.composition_registries())
def test_an_exit_chain_ends_where_the_owner_says_money_is_spent(
    registry: CompositionRegistry,
) -> None:
    """FR-022's other half: an exit chain starts at the destination and ends somewhere
    **declared spendable**, never merely somewhere else."""
    result = compose.compose(
        routes=registry.routes,
        stream=registry.stream,
        destination=registry.destination,
        direction="exit",
        regime_id=REGIME,
        bound=SegmentBound(max_segments=3),
        spendable=registry.spendable,
    )
    if isinstance(result, CompositionRefused):
        return
    endpoints = {(entry.venue_id, entry.currency) for entry in registry.spendable}
    for candidate in result.candidates:
        chain = segments_of(candidate)
        first, last = registry.routes[chain[0]], registry.routes[chain[-1]]
        assert (first.origin, first.legs[0].from_ccy) == (
            registry.destination.venue_id,
            registry.destination.currency,
        )
        assert (last.destination, last.legs[-1].to_ccy) in endpoints


class TestTheQuestionsTheSearchRefusesToAnswer:
    """An empty enumeration and a refusal are different claims, and the types say so."""

    def test_a_bound_below_one_is_refused_rather_than_answered_with_nothing(self) -> None:
        """It admits no candidate at all, not even a declared route. Enumerating nothing for it
        would report every corridor as unreachable while the fault was one digit."""
        world = _two_hop_world()
        result = compose.compose(
            routes=world.routes,
            stream=world.stream,
            destination=world.destination,
            direction="inbound",
            regime_id=REGIME,
            bound=SegmentBound(max_segments=0),
            spendable=world.spendable,
        )
        assert isinstance(result, CompositionRefused)
        assert "0" in result.reason

    def test_an_exit_question_with_nowhere_declared_spendable_is_refused(self) -> None:
        """What is missing is the owner's statement of where money counts as spent, not a
        corridor -- and saying "no way out" would blame the registry for it."""
        world = _two_hop_world()
        result = compose.compose(
            routes=world.routes,
            stream=world.stream,
            destination=world.destination,
            direction="exit",
            regime_id=REGIME,
            bound=SegmentBound(max_segments=3),
            spendable=frozenset(),
        )
        assert isinstance(result, CompositionRefused)
        assert "spendable" in result.reason

    def test_a_destination_the_money_already_arrived_at_is_refused(self) -> None:
        """Every chain would have to leave the venue and come back, and a candidate never
        visits a venue twice -- so "no candidates" would read as a registry gap rather than as
        money that is already where it was wanted."""
        world = _two_hop_world()
        result = compose.compose(
            routes=world.routes,
            stream=world.stream,
            destination=Destination(
                venue_id=world.stream.arrives_at, currency=world.stream.amount.currency
            ),
            direction="inbound",
            regime_id=REGIME,
            bound=SegmentBound(max_segments=3),
            spendable=world.spendable,
        )
        assert isinstance(result, CompositionRefused)
        assert result.stream_id == world.stream.id

    def test_nothing_connecting_is_an_empty_enumeration_and_not_a_refusal(self) -> None:
        """The distinction this whole pair of types exists for: "the registry declares nothing
        that connects" is a real finding and the coverage report's news to deliver."""
        world = _two_hop_world()
        result = compose.compose(
            routes={},
            stream=world.stream,
            destination=world.destination,
            direction="inbound",
            regime_id=REGIME,
            bound=SegmentBound(max_segments=3),
            spendable=world.spendable,
        )
        assert isinstance(result, Enumeration)
        assert result.candidates == ()


def _two_hop_world() -> CompositionRegistry:
    """The hand-built corridor, in the shape the generated properties use."""
    return CompositionRegistry(
        routes=fixtures.two_hop().routes,
        currencies={fixtures.BROKER: fixtures.USD},
        stream=fixtures.SALARY,
        destination=fixtures.BROKER_USD,
        spendable=fixtures.SPENDABLE,
    )
