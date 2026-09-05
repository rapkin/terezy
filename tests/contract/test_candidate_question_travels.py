"""SC-012, SC-017 and SC-021: what leaves this feature, and what it leaves attached to.

FR-020's list is not a summary a later pass re-derives: every field it names is reachable from
an evaluated candidate **without a second call to `evaluate`**, and the two segment counts are
read off the carried key. A candidate set reduced to *feasible / not feasible* would make every
one of I2--I7 begin by enumerating and costing everything again.

FR-012's other half is asserted by a walk rather than a sample: a count can never be read
without the question that determined it, because the question is on the record beside it.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import pytest

from terezy.core.decision.candidates import evaluated, survey
from terezy.core.primitives.rates import NominalRate
from terezy.core.results.candidates import CandidateSet, CandidateSurvey, Question
from terezy.core.results.tuple import RateNotComparable
from terezy.core.routes.path import ExitChain, exit_segments_of, segments_of
from tests import candidate_registries as fixtures

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from terezy.core.results.tuple import TupleOutcome

pytestmark = pytest.mark.contract

OVDP = "ovdp_synthetic_a"


def _surveyed() -> CandidateSurvey:
    registries = fixtures.declared()
    question = fixtures.question(registries)
    result = survey(
        registries=registries,
        routes=registries.routes,
        question=question,
        ceiling=fixtures.ceiling(10_000),
        benchmark=fixtures.benchmark_key(registries, OVDP, question_=question),
    )
    assert isinstance(result, CandidateSurvey), result
    return result


def _outcomes() -> tuple[TupleOutcome, ...]:
    outcomes = evaluated(_surveyed().comparison)
    assert outcomes
    return outcomes


def test_everything_fr020_names_is_on_every_evaluated_candidate() -> None:
    """Walked over the record rather than sampled from it: a field absent on one outcome and
    present on the rest is exactly what a sample misses."""
    named = {
        "key",
        "reaches",
        "implied_rate",
        "span",
        "parts",
        "routes",
        "provenance",
        "staleness",
        "rests_on",
        "risk_class",
    }
    for outcome in _outcomes():
        fields = {field.name for field in dataclasses.fields(outcome)}
        assert named <= fields, sorted(named - fields)
        assert len(outcome.parts) == 6
        assert isinstance(outcome.implied_rate, NominalRate | RateNotComparable)
        assert outcome.routes.status
        assert outcome.routes.disruption_probability >= 0.0


def test_both_segment_counts_are_read_off_the_carried_key() -> None:
    """SC-012's second half, and part of why the key must travel: the counts are derived from
    it rather than stored, so a count and the chain it describes cannot disagree."""
    for outcome in _outcomes():
        assert len(segments_of(outcome.key.route_in)) >= 1
        way_out = outcome.key.route_out
        assert isinstance(way_out, ExitChain)
        assert len(exit_segments_of(way_out)) >= 0


def test_no_field_this_feature_returns_is_a_lossy_projection_of_an_outcome() -> None:
    """FR-020: enumeration hands the whole record forward. A `feasible: bool` beside the
    outcomes would be the summary the requirement forbids, and it would be the field every
    later pass reached for."""
    result = _surveyed()
    fields = {field.name for field in dataclasses.fields(result)}
    assert fields == {"enumerated", "comparison"}


def test_every_count_travels_with_the_whole_question() -> None:
    """SC-017, by a walk over the question's own fields rather than by naming a few."""
    enumerated = _surveyed().enumerated
    assert isinstance(enumerated, CandidateSet)
    assert isinstance(enumerated.question, Question)
    stated = {field.name for field in dataclasses.fields(Question)}
    assert stated == {
        "amounts",
        "horizon",
        "as_of",
        "continuation",
        "plans",
        "bound",
        "regime_id",
        "subjects",
    }
    for name in stated:
        assert getattr(enumerated.question, name) is not None, name


def test_the_result_states_how_many_plans_were_supplied_per_instrument() -> None:
    """FR-025 and SC-021. Read off the question rather than counted into a second field: a
    declared way out no supplied plan reaches is visibly absent, and there is nowhere for a
    count to disagree with the plans it counts."""
    enumerated = _surveyed().enumerated
    supplied = {key: len(value) for key, value in enumerated.question.plans.items()}
    assert supplied
    for candidate in enumerated.candidates:
        assert candidate.plan_position < supplied[candidate.key.instrument_id]


def test_a_tuple_naming_something_undeclared_is_in_none_of_the_three_populations() -> None:
    """FR-015: never constructed, never counted. It was not a candidate; it was a typo."""
    registries = fixtures.declared()
    access = {**registries.access, "no_such_instrument": registries.access[OVDP]}
    enumerated = fixtures.enumerated(dataclasses.replace(registries, access=access))
    assert isinstance(enumerated, CandidateSet), enumerated
    names = {candidate.key.instrument_id for candidate in enumerated.candidates} | {
        pair.instrument_id for pair in enumerated.no_candidate
    }
    assert "no_such_instrument" not in names
    assert enumerated.pairs_considered == len(registries.access) * len(registries.streams)
