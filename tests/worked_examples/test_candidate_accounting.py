"""FR-009: the accounting is an asserted identity, not a claim in prose.

Two identities, and both are checked rather than described -- a check cannot go stale silently
and a sentence can:

    pairs considered      = pairs enumerated + pairs yielding no candidate
    candidates enumerated = evaluated        + dropped

The arithmetic on the shipped registry, re-measured on 2026-08-31 under this module's own
question (an outlay on 2026-04-01, a horizon ending 2030-06-30, one plan per instrument):

    66 pairs considered  =  33 pairs enumerated  + 33 pairs yielding no candidate
    33 candidates        =  27 evaluated         +  6 dropped

The **second** line is the one that moves with the question. Refusals across 010's union turn on
the amount, on the horizon and on `as_of`, so 27 and 6 are facts about *this* question rather
than about the registry -- which is why FR-012 puts the whole question on the record beside
every count, and why the identities are asserted against the set rather than against the
numbers above. Both are derived here; the literals are the reader's check on the derivation.

Four of the six drops are what a real registry looks like: `UA4000239016`, `UA4000239040`,
`UA4000239081` and `UA4000239107` were placed after this question's outlay date, so buying them
on it is buying paper that did not exist. The other two are the funds that size their payouts
in USD with no declared rate, and they are the two that dropped before 016 declared anything.
"""

from __future__ import annotations

import pytest

from terezy.core.decision.candidates import dropped, evaluated, survey
from terezy.core.results.candidates import CandidateSurvey
from terezy.core.results.tuple import Comparison
from tests import candidate_registries as fixtures

pytestmark = pytest.mark.worked_example

BENCHMARK_INSTRUMENT = "ovdp_synthetic_a"


def _survey() -> CandidateSurvey:
    registries = fixtures.shipped()
    question = fixtures.question(registries)
    ceiling = fixtures.declarations().ceiling
    result = survey(
        registries=registries,
        routes=registries.routes,
        question=question,
        ceiling=ceiling,
        benchmark=fixtures.benchmark_key(
            registries, BENCHMARK_INSTRUMENT, question_=question, ceiling_=ceiling
        ),
    )
    assert isinstance(result, CandidateSurvey), result
    return result


class TestTheThreePopulationsPartitionEverythingConsidered:
    def test_pairs_considered_equals_pairs_enumerated_plus_pairs_yielding_none(self) -> None:
        enumerated = _survey().enumerated
        pairs_enumerated = {
            (item.key.instrument_id, item.key.stream_id) for item in enumerated.candidates
        }
        assert len(pairs_enumerated) == 33
        assert len(enumerated.no_candidate) == 33
        assert len(pairs_enumerated) + len(enumerated.no_candidate) == enumerated.pairs_considered
        assert enumerated.pairs_considered == 66

    def test_candidates_enumerated_equals_evaluated_plus_dropped(self) -> None:
        result = _survey()
        assert len(evaluated(result.comparison)) == 27
        assert len(dropped(result.comparison)) == 6
        assert len(evaluated(result.comparison)) + len(dropped(result.comparison)) == len(
            result.enumerated.candidates
        )
        assert len(result.enumerated.candidates) == 33

    def test_every_enumerated_key_lands_in_exactly_one_of_the_two_columns(self) -> None:
        """The identity above holds by count; this holds it by **membership**, which is what a
        count cannot say. One candidate evaluated twice and another lost would satisfy the
        arithmetic and be exactly the defect the arithmetic exists to catch."""
        result = _survey()
        scored = [outcome.key for outcome in evaluated(result.comparison)]
        refused = [item.key for item in dropped(result.comparison)]
        assert sorted(map(repr, scored + refused)) == sorted(
            repr(item.key) for item in result.enumerated.candidates
        )

    def test_a_pair_yielding_no_candidate_is_in_neither_evaluated_nor_dropped(self) -> None:
        """FR-013: the absence of an option is not the rejection of one, and folding the two
        would give a reader a drop count to divide by that means nothing."""
        result = _survey()
        never = {(pair.instrument_id, pair.stream_id) for pair in result.enumerated.no_candidate}
        touched = {
            (item.instrument_id, item.stream_id)
            for item in [outcome.key for outcome in evaluated(result.comparison)]
            + [refusal.key for refusal in dropped(result.comparison)]
        }
        assert not never & touched


def test_the_benchmark_is_one_of_the_ranked_candidates() -> None:
    """SC-015: the index points into the same loop's output, never beside it."""
    result = _survey()
    assert isinstance(result.comparison, Comparison)
    benchmark = result.comparison.ranked[result.comparison.benchmark]
    assert benchmark.key in {item.key for item in result.enumerated.candidates}
    assert benchmark.key.instrument_id == BENCHMARK_INSTRUMENT
