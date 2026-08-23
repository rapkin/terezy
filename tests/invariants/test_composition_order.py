"""SC-003: reversing the declaration order changes nothing, and a tie stays a tie.

**This is not a flaky-ordering test. It is the test that catches a heuristic.** A search is
where iteration order leaks into output, and the leak is always invisible from inside: an
adjacency bucket left unsorted, a ``set`` iterated, a ``dict`` relied on for order -- each
produces a perfectly plausible answer that happens to depend on which file loaded first. So the
registry is run in **both** declaration orders and *everything* is compared: the candidate set,
its order, every reported figure, the ranking, the recommendation and the ties.

Python dictionaries preserve insertion order, so reversing it is exactly the perturbation such a
search would show up under, and nothing else about the world changes -- which makes the
comparison a controlled one rather than a shuffle.

**The second half is the tie** (FR-008, 002 FR-018). A composed candidate and a declared route
costing the same within the project tolerance are **reported as a tie**, never resolved in
favour of whichever the search found first. The fixture makes the two genuinely different
journeys with identical numbers -- same premium, same fees, a different venue in the middle --
because a chain that reproduced the declared route leg for leg would be suppressed as a
duplicate instead (FR-009), which is a different rule and is tested next door.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from hypothesis import given, settings

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.composed import Enumeration, SegmentBound
from terezy.core.results.ramp import Ranking, RoundTripCost, recommended_cost
from terezy.core.routes import compose, ranking
from terezy.core.routes.legs import Route
from terezy.core.routes.path import (
    Candidate,
    ComposedExit,
    Journey,
    candidate_id,
    segments_of,
)
from tests import composed_registries as fixtures
from tests.invariants import route_graphs
from tests.invariants.route_graphs import CompositionRegistry

pytestmark = pytest.mark.invariant

AMOUNT = Money(10_000.0, Currency.UAH, prov.EMPTY)
EXIT_CHAIN = ComposedExit(segments=("out_broker_to_exchange", "out_exchange_to_home"))
BOUND = SegmentBound(max_segments=3)


def _enumerated(registry: CompositionRegistry, routes: Mapping[str, Route]) -> Enumeration:
    result = compose.compose(
        routes=routes,
        stream=registry.stream,
        destination=registry.destination,
        direction="inbound",
        regime_id="generated",
        bound=BOUND,
        spendable=registry.spendable,
    )
    assert isinstance(result, Enumeration), result
    return result


@settings(max_examples=60, deadline=None)
@given(registry=route_graphs.composition_registries())
def test_reversing_the_declaration_order_changes_no_candidate_and_no_position(
    registry: CompositionRegistry,
) -> None:
    """Not merely the same *set*: the same tuple, in the same order.

    Comparing sets would let the emitted order depend on the walk while the test stayed green,
    and the emitted order is what a ranking's stable sort falls back on when two candidates are
    tied. An order that moved with the declarations would move a reported tie's head.
    """
    forward = _enumerated(registry, registry.routes)
    reverse = _enumerated(registry, dict(reversed(list(registry.routes.items()))))
    assert forward.candidates == reverse.candidates
    assert forward.bound == reverse.bound


@settings(max_examples=40, deadline=None)
@given(registry=route_graphs.composition_registries())
def test_the_emitted_order_is_a_function_of_the_declarations_alone(
    registry: CompositionRegistry,
) -> None:
    """The order is ``(segment count, route ids)`` -- derivable by a reader from the ids.

    Stated as a property rather than left implicit, because it is what makes the previous test
    meaningful: two runs could agree by both being wrong in the same way if the order came out
    of the walk. This one says what the order *is*.
    """
    emitted = [
        segments_of(candidate) for candidate in _enumerated(registry, registry.routes).candidates
    ]
    assert emitted == sorted(emitted, key=lambda chain: (len(chain), chain))


def _ranked(routes: Mapping[str, Route], candidates: tuple[Candidate, ...]) -> Ranking:
    world = fixtures.tied()
    result = ranking.rank(
        [Journey(path=candidate, exit_path=EXIT_CHAIN) for candidate in candidates],
        AMOUNT,
        routes=routes,
        channels=world.channels,
        streams=world.streams,
        kinds=world.kinds,
        on_date=fixtures.ON_DATE,
        as_of=fixtures.AS_OF,
    )
    assert isinstance(result, Ranking), result
    return result


def _candidates(routes: Mapping[str, Route]) -> tuple[Candidate, ...]:
    world = fixtures.tied()
    result = compose.compose(
        routes=routes,
        stream=world.streams[fixtures.SALARY.id],
        destination=fixtures.BROKER_USD,
        direction="inbound",
        regime_id=fixtures.REGIME_ID,
        bound=BOUND,
        spendable=world.spendable,
    )
    assert isinstance(result, Enumeration), result
    return result.candidates


class TestAComposedCandidateAndADeclaredRouteThatCostTheSameAreATie:
    """FR-010 and 002 FR-018, over one league with both kinds of candidate in it."""

    def test_both_kinds_are_enumerated_and_neither_suppresses_the_other(self) -> None:
        """The precondition. They differ in one leg -- the middle venue -- so FR-009 leaves
        both standing, and the tie below is about two real alternatives."""
        ids = {candidate_id(candidate) for candidate in _candidates(fixtures.tied().routes)}
        assert "in_salary_to_broker_via_mirror" in ids
        assert "in_salary_to_exchange+in_exchange_to_broker" in ids

    def test_they_cost_the_same_within_the_project_tolerance(self) -> None:
        ranked = _ranked(fixtures.tied().routes, _candidates(fixtures.tied().routes))
        fractions = [
            entry.round_trip.fraction
            for entry in ranked.costed
            if isinstance(entry.round_trip, RoundTripCost)
        ]
        assert len(fractions) == 2
        assert is_close(fractions[0], fractions[1])

    def test_the_tie_is_reported_rather_than_resolved_by_the_search(self) -> None:
        """The head of a sorted sequence is not a winner. ``Ranking.ties`` is what stops it
        being read as one, and it is populated here rather than left empty because both
        candidates are within one tolerance of each other."""
        ranked = _ranked(fixtures.tied().routes, _candidates(fixtures.tied().routes))
        assert ranked.ties == ((0, 1),)

    def test_reversing_the_declaration_order_changes_no_figure_and_no_tie(self) -> None:
        """SC-003 end to end: the candidates, every figure, the recommendation and the tie.

        This is the assertion the whole module exists for. If a bucket goes unsorted or a set is
        iterated somewhere in the search, the two rankings below stop being equal -- and nothing
        else in the suite would notice, because each one on its own is perfectly self-consistent.
        """
        forward_routes = fixtures.tied().routes
        reverse_routes = dict(reversed(list(forward_routes.items())))
        forward = _ranked(forward_routes, _candidates(forward_routes))
        reverse = _ranked(reverse_routes, _candidates(reverse_routes))
        assert forward.costed == reverse.costed
        assert forward.ties == reverse.ties
        assert forward.recommended == reverse.recommended
        assert forward.excluded == reverse.excluded
        assert forward.not_comparable == reverse.not_comparable
        assert recommended_cost(forward) == recommended_cost(reverse)
