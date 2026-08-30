"""FR-018 and FR-019: the whole enumeration refuses, and returns no candidates at all.

Four things do not stand up as questions rather than as candidates -- a reachable instrument
with no run plan, two equal plans for one instrument, a count above the declared ceiling, and a
`compose` refusal that is true of every pair at once. Each returns a typed record **instead of**
a set, so a caller that forgot the case is a type error rather than a partial answer read as a
complete one.

**The ceiling refuses and never truncates**, and that is the design point a reader's instinct
inverts: a shortened list answers a different question from the one asked, with an audit trail
that looks impeccable, and every later pass over it -- dominance, an objective, a stability
check -- would be a false optimum. The ceiling exists to say that enumerating *this* registry
has stopped being the right primitive, which is a finding the owner acts on.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from terezy.core.decision.candidates import enumerate_candidates
from terezy.core.results.candidates import (
    CandidateSet,
    CeilingExceeded,
    DuplicateRunPlan,
    NoPlanSupplied,
    QuestionDoesNotStandUp,
    UndeclaredRouteSupplied,
)
from terezy.core.results.composed import SegmentBound, Unaskable
from terezy.core.routes.path import segments_of
from tests import candidate_registries as fixtures
from tests import tuple_registries as tuples

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from terezy.core.decision.tuple_outcome import Registries
    from terezy.core.results.candidates import CandidateCeiling, Question

OVDP = "ovdp_synthetic_a"


def _run(
    registries: Registries,
    *,
    question: Question | None = None,
    ceiling: CandidateCeiling | None = None,
) -> object:
    return enumerate_candidates(
        registries=registries,
        routes=registries.routes,
        question=question if question is not None else fixtures.question(registries),
        ceiling=ceiling if ceiling is not None else fixtures.ceiling(10_000),
    )


def _shipped_count() -> int:
    result = _run(fixtures.shipped())
    assert isinstance(result, CandidateSet)
    return len(result.candidates)


class TestTheCeilingRefusesAndNeverTruncates:
    def test_a_count_one_above_the_ceiling_refuses_naming_both_numbers(self) -> None:
        reached = _shipped_count()
        result = _run(fixtures.shipped(), ceiling=fixtures.ceiling(reached - 1))
        assert isinstance(result, CeilingExceeded), result
        assert (result.ceiling, result.reached) == (reached - 1, reached)

    def test_a_count_exactly_at_the_ceiling_is_admitted(self) -> None:
        """The boundary, because off-by-one here refuses a question the owner asked."""
        reached = _shipped_count()
        result = _run(fixtures.shipped(), ceiling=fixtures.ceiling(reached))
        assert isinstance(result, CandidateSet), result
        assert len(result.candidates) == reached

    def test_a_ceiling_of_one_returns_no_set_rather_than_one_candidate(self) -> None:
        """The refusal *replaces* the set. A truncating implementation would return a
        ``CandidateSet`` of one here and satisfy every count on it."""
        result = _run(fixtures.shipped(), ceiling=fixtures.ceiling(1))
        assert not isinstance(result, CandidateSet), result
        assert isinstance(result, CeilingExceeded), result
        assert result.reached > result.ceiling


class TestARunPlanIsNeverInvented:
    def test_a_reachable_instrument_with_no_plan_refuses_the_whole_enumeration(self) -> None:
        registries = fixtures.shipped()
        plans = {
            key: value for key, value in fixtures.one_plan_each(registries).items() if key != OVDP
        }
        result = _run(registries, question=fixtures.question(registries, plans=plans))
        assert isinstance(result, NoPlanSupplied), result
        assert result.instrument_id == OVDP

    def test_an_empty_sequence_is_the_same_omission_and_not_a_choice(self) -> None:
        """Supplying `()` reads as *run it no way at all*, which is not a way to run it."""
        registries = fixtures.shipped()
        plans = dict(fixtures.one_plan_each(registries))
        plans[OVDP] = ()
        result = _run(registries, question=fixtures.question(registries, plans=plans))
        assert isinstance(result, NoPlanSupplied), result
        assert result.instrument_id == OVDP

    def test_an_unreachable_instrument_needs_no_plan(self) -> None:
        """The refusal is about *reachable* instruments. A plan for something the routes never
        connect would be a plan for a candidate that cannot exist, and demanding one would make
        a registry gap look like a caller's omission."""
        registries = fixtures.with_access(fixtures.shipped(), OVDP, bought_at="binance")
        plans = {
            key: value for key, value in fixtures.one_plan_each(registries).items() if key != OVDP
        }
        result = _run(registries, question=fixtures.question(registries, plans=plans))
        assert isinstance(result, CandidateSet), result
        assert OVDP not in {item.key.instrument_id for item in result.candidates}

    def test_two_equal_plans_for_one_instrument_refuse_naming_both_positions(self) -> None:
        """One key twice has no defined count, and de-duplicating would answer with fewer
        candidates than were asked for."""
        registries = fixtures.shipped()
        plans = dict(fixtures.one_plan_each(registries))
        plans[OVDP] = (fixtures.HOLD_TO_MATURITY, fixtures.HOLD_TO_MATURITY)
        result = _run(registries, question=fixtures.question(registries, plans=plans))
        assert isinstance(result, DuplicateRunPlan), result
        assert (result.instrument_id, result.positions) == (OVDP, (0, 1))


class TestARouteTheRegistryDoesNotDeclare:
    """FR-018's third clause, reached by the seam its record names.

    The route set composed over and the ``Registries`` evaluated against arrive as separate
    arguments -- 004 FR-017 makes narrowing to one regime the caller's job -- so a caller can
    compose over a corridor the evaluation has never heard of. Left unchecked that produces one
    identical ``DeclarationMissing`` per candidate: a page of drops all saying the same thing
    about the question and nothing about any candidate.
    """

    def test_composing_over_a_route_the_registry_lacks_refuses_as_a_whole(self) -> None:
        registries = fixtures.shipped()
        extra = tuples.route(
            "test_route_the_registry_lacks",
            origin="monobank_uah",
            destination="inzhur",
            direction="inbound",
        )
        wider = {**registries.routes, extra.id: extra}
        result = enumerate_candidates(
            registries=registries,
            routes=wider,
            question=fixtures.question(registries),
            ceiling=fixtures.ceiling(10_000),
        )
        assert isinstance(result, UndeclaredRouteSupplied), result
        assert result.route_ids == (extra.id,)
        assert result.part == "route_in"

    def test_the_same_registry_and_route_set_produces_a_set(self) -> None:
        """The control: the refusal above is the *disagreement*, not the extra corridor."""
        registries = fixtures.shipped()
        extra = tuples.route(
            "test_route_the_registry_lacks",
            origin="monobank_uah",
            destination="inzhur",
            direction="inbound",
        )
        agreed = tuples.with_new_route(registries, extra)
        result = enumerate_candidates(
            registries=agreed,
            routes=agreed.routes,
            question=fixtures.question(agreed),
            ceiling=fixtures.ceiling(10_000),
        )
        assert isinstance(result, CandidateSet), result
        assert extra.id in {
            name for item in result.candidates for name in segments_of(item.key.route_in)
        }


class TestAQuestionThatDoesNotStandUpRefusesRatherThanEmptying:
    def test_a_bound_admitting_nothing_refuses_the_whole_enumeration(self) -> None:
        registries = fixtures.shipped()
        result = _run(
            registries,
            question=fixtures.question(registries, bound=SegmentBound(max_segments=0)),
        )
        assert isinstance(result, QuestionDoesNotStandUp), result
        assert result.refusal.case is Unaskable.BOUND_ADMITS_NOTHING

    def test_no_declared_spendable_endpoint_refuses_the_whole_enumeration(self) -> None:
        """What is missing is the owner's statement of where money counts as spent, not a
        corridor -- so enumerating nothing would blame the registry for it."""
        registries = replace(fixtures.shipped(), spendable=frozenset())
        result = _run(registries)
        assert isinstance(result, QuestionDoesNotStandUp), result
        assert result.refusal.case is Unaskable.NO_SPENDABLE_ENDPOINT

    def test_money_already_where_it_was_wanted_does_not_refuse_the_enumeration(self) -> None:
        """The third case is about one pair and must stay in the no-candidate column: refusing
        the whole run for it would report a broken question where the registry is complete."""
        registries = fixtures.with_access(fixtures.shipped(), OVDP, bought_at="monobank_uah")
        result = _run(registries)
        assert isinstance(result, CandidateSet), result
