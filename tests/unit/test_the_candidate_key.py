"""The address an answer publishes per evaluated candidate (027 FR-006).

The five-term key is not enough: the same candidate is evaluated once per horizon and the three
evaluations have three different projections, so a key built from the five terms alone would send
a reader to whichever section the endpoint happened to find first.
"""

from __future__ import annotations

from datetime import date
from functools import cache
from typing import Final

import pytest

from terezy.api.answer import answer_question
from terezy.core.decision.candidates import evaluated
from terezy.core.primitives.currency import Currency
from terezy.core.results.answer import Answer
from terezy.core.results.candidates import CandidateSurvey
from terezy.core.results.canonical import CANDIDATE_KEY_SEPARATOR, candidate_key
from terezy.core.results.tuple import TupleOutcome
from tests.data_roots import SHIPPED

QUESTION: Final = "fifty-thousand-hryvnia"
AS_OF: Final = date(2026, 9, 6)


@cache
def _answer() -> Answer:
    answered = answer_question(SHIPPED, QUESTION, as_of=AS_OF, base_currency=Currency.UAH)
    assert isinstance(answered.answer, Answer), answered.answer
    return answered.answer


@cache
def _published() -> tuple[tuple[int, TupleOutcome], ...]:
    return tuple(
        (index, outcome)
        for index, section in enumerate(_answer().sections)
        if isinstance(section.outcome, CandidateSurvey)
        for outcome in evaluated(section.outcome.comparison)
    )


def test_one_candidate_in_three_sections_has_three_distinct_keys() -> None:
    published = _published()
    assert published, "the shipped question evaluated nothing, so this would pass vacuously"
    by_instrument: dict[str, set[str]] = {}
    for _, outcome in published:
        by_instrument.setdefault(outcome.key.instrument_id, set()).add(outcome.projection_key)
    sections = len(_answer().sections)
    assert sections > 1
    assert all(len(keys) == sections for keys in by_instrument.values()), by_instrument


def test_every_published_key_is_distinct() -> None:
    keys = [outcome.projection_key for _, outcome in _published()]
    assert len(set(keys)) == len(keys)


def test_the_key_is_the_horizon_and_the_five_terms_and_nothing_else() -> None:
    """Rendered by the one function, so an endpoint cannot compose a second spelling."""
    for _, outcome in _published():
        section = next(
            held
            for held in _answer().sections
            if candidate_key(outcome.key, held.horizon) == outcome.projection_key
        )
        assert outcome.projection_key == candidate_key(outcome.key, section.horizon)
        assert outcome.projection_key.startswith(section.horizon.start.isoformat())
        assert outcome.key.instrument_id in outcome.projection_key.split(CANDIDATE_KEY_SEPARATOR)


def test_a_term_carrying_a_separator_is_refused_rather_than_rendered() -> None:
    """The mutation this guard exists for: two candidates differing in one term, one key.

    Reached by planting the separator in a declared id, because nothing else can: every shipped
    term is free of both, which is what makes the flat rendering injective today.
    """
    _, outcome = _published()[0]
    section = _answer().sections[0]
    broken = type(outcome.key)(
        instrument_id=f"a{CANDIDATE_KEY_SEPARATOR}b",
        stream_id=outcome.key.stream_id,
        route_in=outcome.key.route_in,
        exit_terms=outcome.key.exit_terms,
        route_out=outcome.key.route_out,
    )
    with pytest.raises(ValueError, match="candidate-key separator"):
        candidate_key(broken, section.horizon)
