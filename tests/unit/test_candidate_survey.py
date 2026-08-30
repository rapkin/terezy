"""FR-022, FR-001a and SC-002: handing the set to `compare`, and what that must not become.

Three claims, and each is a place this feature could quietly become something else:

* **The benchmark is a member of the set, exactly once.** `compare` prepends a benchmark it was
  not handed, so a set that does not contain one would be ranked against a figure that never
  came out of the same loop -- 010's FR-012 side channel, reintroduced one layer up. The answer
  is a typed refusal, never an append.
* **The loop is a loop.** An enumerated candidate's outcome is field for field the outcome
  `evaluate` produces for the same key. If it were not, this feature would be a second pipeline
  wearing the first one's name.
* **Two streams are refused rather than converted.** `compare` takes one amount for the whole
  set while a question states one per stream in its own currency, and no landed feature declares
  a rate that values one currency in another *for a return*. The gap is recorded and refused,
  not smoothed over.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from terezy.core.decision.candidates import evaluated, survey
from terezy.core.decision.tuple_outcome import evaluate
from terezy.core.results.candidates import (
    BenchmarkNotACandidate,
    CandidateSet,
    CandidateSurvey,
    MoreThanOneStreamInTheSet,
    SurveyRefused,
    UndeclaredRouteSupplied,
)
from terezy.core.results.tuple import Comparison, TupleOutcome
from terezy.core.routes.path import FROM_THE_DECLARATION, FundingPath
from tests import candidate_registries as fixtures
from tests import tuple_registries as tuples

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from terezy.core.decision.tuple_outcome import Registries
    from terezy.core.results.tuple import Tuple

OVDP = "ovdp_synthetic_a"
FX_IN = "test_deel_to_inzhur"


def _survey(registries: Registries, benchmark: Tuple) -> CandidateSurvey | SurveyRefused:
    return survey(
        registries=registries,
        routes=registries.routes,
        question=fixtures.question(registries),
        ceiling=fixtures.ceiling(10_000),
        benchmark=benchmark,
    )


def _shipped_survey() -> CandidateSurvey:
    registries = fixtures.shipped()
    result = _survey(registries, fixtures.benchmark_key(registries, OVDP))
    assert isinstance(result, CandidateSurvey), result
    return result


class TestTheBenchmarkIsAMemberOfTheSet:
    def test_the_index_points_at_a_candidate_the_same_loop_produced(self) -> None:
        result = _shipped_survey()
        assert isinstance(result.comparison, Comparison)
        pointed = result.comparison.ranked[result.comparison.benchmark].key
        assert pointed in {item.key for item in result.enumerated.candidates}

    def test_a_benchmark_absent_from_the_set_refuses_rather_than_being_appended(self) -> None:
        """A tuple naming the same instrument through the declaration's own way out is a
        perfectly valid tuple and is **not** in this set: FR-004 forbids emitting the
        `FROM_THE_DECLARATION` sentinel, so the set holds the named chain instead."""
        registries = fixtures.shipped()
        outsider = replace(fixtures.benchmark_key(registries, OVDP), route_out=FROM_THE_DECLARATION)
        result = _survey(registries, outsider)
        assert isinstance(result, BenchmarkNotACandidate), result
        assert result.occurrences == 0

    def test_the_refusal_replaces_the_survey_rather_than_weakening_it(self) -> None:
        """A ``CandidateSurvey`` whose comparison was built around an appended benchmark is what
        this returns *instead of*, so the type is the assertion."""
        registries = fixtures.shipped()
        outsider = replace(fixtures.benchmark_key(registries, OVDP), route_out=FROM_THE_DECLARATION)
        result = _survey(registries, outsider)
        assert not isinstance(result, CandidateSurvey), result

    def test_a_benchmark_naming_an_undeclared_route_is_refused_by_the_route_it_names(
        self,
    ) -> None:
        """FR-018's third clause. The remedy is a declaration, not a different benchmark, so
        reporting *not among the candidates* here would point the owner at the wrong file."""
        registries = fixtures.shipped()
        outsider = replace(
            fixtures.benchmark_key(registries, OVDP),
            route_in=FundingPath(
                destination_id="inzhur", stream_id=fixtures.SALARY, route_id="no_such_route"
            ),
        )
        result = _survey(registries, outsider)
        assert isinstance(result, UndeclaredRouteSupplied), result
        assert result.route_ids == ("no_such_route",)
        assert result.part == "route_in"


class TestTheLoopIsALoop:
    def test_each_outcome_is_what_evaluate_gives_the_same_key_directly(self) -> None:
        """SC-002, field for field, over **every** evaluated candidate rather than a sample."""
        registries = fixtures.shipped()
        question = fixtures.question(registries)
        result = _shipped_survey()
        outcomes = evaluated(result.comparison)
        assert outcomes
        for outcome in outcomes:
            direct = evaluate(
                outcome.key,
                amount=question.amounts[outcome.key.stream_id],
                horizon=question.horizon,
                as_of=question.as_of,
                continuation=question.continuation,
                registries=registries,
            )
            assert isinstance(direct, TupleOutcome), direct
            assert direct == outcome

    def test_a_dropped_candidate_is_the_refusal_evaluate_gives_the_same_key(self) -> None:
        registries = fixtures.shipped()
        question = fixtures.question(registries)
        result = _shipped_survey()
        for refused in result.comparison.refused:
            direct = evaluate(
                refused.key,
                amount=question.amounts[refused.key.stream_id],
                horizon=question.horizon,
                as_of=question.as_of,
                continuation=question.continuation,
                registries=registries,
            )
            assert direct == refused.refusal


class TestTwoStreamsAreRefusedRatherThanConverted:
    @staticmethod
    def _both_streams_connect() -> Registries:
        """One fixture inbound corridor turning dollars into hryvnia at the buying venue.

        The shipped registry declares its two USD-to-UAH corridors in the `exit` direction, so
        an inbound enumeration cannot see them and the dollar stream yields nothing. This adds
        the corridor the registry is missing, which is the only way to reach the case at all.
        """
        registries = fixtures.shipped()
        return replace(
            registries,
            routes={
                **registries.routes,
                FX_IN: tuples.fx_route(FX_IN, origin="deel", destination="inzhur"),
            },
        )

    def test_the_fixture_really_does_produce_a_two_stream_set(self) -> None:
        """The positive control. Without it the refusal below would pass on a registry where
        the dollar stream still connects to nothing."""
        result = fixtures.enumerated(self._both_streams_connect())
        assert isinstance(result, CandidateSet), result
        assert {item.key.stream_id for item in result.candidates} == {
            fixtures.SALARY,
            fixtures.CONTRACT,
        }

    def test_the_typed_refusal_wins_over_the_missing_amount_raise(self) -> None:
        """A caller with a two-stream set naturally supplies one amount, because one is all
        `compare` takes. The record naming the real gap must reach him, not a construction
        error about the amount he was never able to state usefully."""
        registries = self._both_streams_connect()
        result = survey(
            registries=registries,
            routes=registries.routes,
            question=fixtures.question(registries, amounts={fixtures.SALARY: fixtures.AMOUNT_UAH}),
            ceiling=fixtures.ceiling(10_000),
            benchmark=fixtures.benchmark_key(registries, OVDP),
        )
        assert isinstance(result, MoreThanOneStreamInTheSet), result

    def test_it_is_refused_naming_both_streams(self) -> None:
        registries = self._both_streams_connect()
        result = _survey(registries, fixtures.benchmark_key(registries, OVDP))
        assert isinstance(result, MoreThanOneStreamInTheSet), result
        assert result.stream_ids == (fixtures.CONTRACT, fixtures.SALARY)

    def test_each_stream_keeps_its_own_amount_in_its_own_currency(self) -> None:
        """FR-005: nothing converts one into the other, so the two amounts stay two amounts."""
        question = fixtures.question(fixtures.shipped())
        assert question.amounts[fixtures.SALARY].currency is fixtures.UAH
        assert question.amounts[fixtures.CONTRACT].currency is fixtures.USD


def test_a_question_stating_no_amount_for_the_funding_stream_raises() -> None:
    """A caller's incomplete question, not a fact about the money, so it raises rather than
    joining a registry gap in a typed column. Defaulting it to zero would score a real option
    at nothing and rank it last with nothing on the record to say why."""
    registries = fixtures.shipped()
    benchmark = fixtures.benchmark_key(registries, OVDP)
    with pytest.raises(ValueError, match="no amount"):
        survey(
            registries=registries,
            routes=registries.routes,
            question=fixtures.question(
                registries, amounts={fixtures.CONTRACT: fixtures.AMOUNT_USD}
            ),
            ceiling=fixtures.ceiling(10_000),
            benchmark=benchmark,
        )


def test_an_amount_in_a_currency_its_stream_does_not_deliver_raises() -> None:
    """SC-020's second half: 010's existing behaviour for a caller's construction error.

    This feature neither catches it nor turns it into a refusal, because it is a mistake in the
    question rather than a fact about the money -- and a typed refusal would put a caller's typo
    in the same column as a registry gap.
    """
    registries = fixtures.shipped()
    benchmark = fixtures.benchmark_key(registries, OVDP)
    with pytest.raises(ValueError, match="currency"):
        survey(
            registries=registries,
            routes=registries.routes,
            question=fixtures.question(registries, amounts={fixtures.SALARY: fixtures.AMOUNT_USD}),
            ceiling=fixtures.ceiling(10_000),
            benchmark=benchmark,
        )
