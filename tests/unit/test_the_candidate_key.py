"""The address an answer publishes per evaluated candidate (027 FR-006).

The five-term key is not enough: the same candidate is evaluated once per horizon and the three
evaluations have three different projections, so a key built from the five terms alone would send
a reader to whichever section the endpoint happened to find first.
"""

from __future__ import annotations

import pytest

from terezy.core.results.canonical import CANDIDATE_KEY_SEPARATOR, candidate_key
from tests.served_projections import answered, evaluated_outcomes


def test_one_candidate_in_three_sections_has_three_distinct_keys() -> None:
    published = evaluated_outcomes()
    assert published, "the shipped question evaluated nothing, so this would pass vacuously"
    by_instrument: dict[str, set[str]] = {}
    for outcome, _ in published:
        by_instrument.setdefault(outcome.key.instrument_id, set()).add(outcome.projection_key)
    sections = len(answered().sections)
    assert sections > 1
    assert all(len(keys) == sections for keys in by_instrument.values()), by_instrument


def test_every_published_key_is_distinct() -> None:
    keys = [outcome.projection_key for outcome, _ in evaluated_outcomes()]
    assert len(set(keys)) == len(keys)


def test_the_key_is_the_horizon_and_the_five_terms_and_nothing_else() -> None:
    """Rendered by the one function, so an endpoint cannot compose a second spelling."""
    for outcome, horizon in evaluated_outcomes():
        assert outcome.projection_key == candidate_key(outcome.key, horizon)
        assert outcome.projection_key.startswith(horizon.start.isoformat())
        assert outcome.key.instrument_id in outcome.projection_key.split(CANDIDATE_KEY_SEPARATOR)


def test_a_term_carrying_a_separator_is_refused_rather_than_rendered() -> None:
    """The mutation this guard exists for: two candidates differing in one term, one key.

    Reached by planting the separator in a declared id, because nothing else can: every shipped
    term is free of both, which is what makes the flat rendering injective today.
    """
    outcome, horizon = evaluated_outcomes()[0]
    broken = type(outcome.key)(
        instrument_id=f"a{CANDIDATE_KEY_SEPARATOR}b",
        stream_id=outcome.key.stream_id,
        route_in=outcome.key.route_in,
        exit_terms=outcome.key.exit_terms,
        route_out=outcome.key.route_out,
    )
    with pytest.raises(ValueError, match="candidate-key separator"):
        candidate_key(broken, horizon)
