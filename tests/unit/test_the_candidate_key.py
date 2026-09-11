"""The address an answer publishes per evaluated candidate (027 FR-006).

The five-term key is not enough: the same candidate is evaluated once per horizon and the three
evaluations have three different projections, so a key built from the five terms alone would send
a reader to whichever section the endpoint happened to find first.
"""

from __future__ import annotations

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


def test_two_terms_that_differ_only_in_a_separator_get_different_keys() -> None:
    """The collision the rendering has to survive, and the reason it escapes rather than refuses.

    ``a|b`` beside ``a`` and ``b`` as two terms is the flattening's one failure mode, and it is
    reachable from **data**: nothing at the boundary forbids a declared id containing a comma.
    Refusing it would turn such a declaration into an unhandled failure of the whole answer,
    since this runs on every evaluated tuple.
    """
    outcome, horizon = evaluated_outcomes()[0]

    def keyed(instrument_id: str) -> str:
        planted = type(outcome.key)(
            instrument_id=instrument_id,
            stream_id=outcome.key.stream_id,
            route_in=outcome.key.route_in,
            exit_terms=outcome.key.exit_terms,
            route_out=outcome.key.route_out,
        )
        return candidate_key(planted, horizon)

    for separator in (CANDIDATE_KEY_SEPARATOR, ","):
        planted = keyed(f"a{separator}b")
        assert (
            separator
            not in planted.removeprefix(
                f"{horizon.start.isoformat()}..{horizon.end.isoformat()}{CANDIDATE_KEY_SEPARATOR}"
            ).split(CANDIDATE_KEY_SEPARATOR)[0]
        )
        assert planted != keyed("ab")
    # The escape character escapes itself, so the two below do not render as one key either.
    assert keyed("a%7Cb") != keyed(f"a{CANDIDATE_KEY_SEPARATOR}b")
