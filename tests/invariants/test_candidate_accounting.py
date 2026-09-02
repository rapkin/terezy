"""SC-004: the accounting identities hold over generated registries and questions.

    pairs considered      = pairs enumerated + pairs yielding no candidate
    candidates enumerated = evaluated        + dropped

Both are asserted rather than described, over variations of the shipped registry: subsets of
the access declarations, of the routes and of the streams, with the amount and the horizon
varied. Varying the registry rather than generating one from nothing keeps every case a world
the loader validated, which is `tests/tuple_registries.py`'s reasoning applied to a strategy.

The three edge populations the criterion names -- all dropped, all yielding nothing, and
nothing declared at all -- are pinned as their own cases below, because a generated run that
happened to miss one would leave the property looking stronger than it is.
"""

from __future__ import annotations

import collections
import random
from dataclasses import replace
from typing import TYPE_CHECKING, Literal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from terezy.core.decision.candidates import dropped, evaluated, survey
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.money import Money
from terezy.core.results.candidates import CandidateSet, CandidateSurvey
from tests import candidate_registries as fixtures

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from terezy.core.decision.tuple_outcome import Registries

pytestmark = pytest.mark.invariant

Reached = Literal["refused", "empty", "uncomparable", "counted"]
"""How far one generated case got before there was nothing left to assert."""

SHIPPED = fixtures.declared()
INSTRUMENTS = sorted(SHIPPED.access)
ROUTES = sorted(SHIPPED.routes)
STREAMS = sorted(SHIPPED.streams)


def _narrowed(instruments: list[str], routes: list[str], streams: list[str]) -> Registries:
    """The shipped registry with three of its families narrowed to the named members."""
    return replace(
        SHIPPED,
        access={key: SHIPPED.access[key] for key in instruments},
        routes={key: SHIPPED.routes[key] for key in routes},
        streams={key: SHIPPED.streams[key] for key in streams},
    )


def _both_identities(registries: Registries, amount: Money) -> Reached:
    """The two identities, on whatever the registry and the amount produced.

    Returns how far the case got, so the run can prove it exercised the second identity rather
    than returning early every time -- a property that only ever asserts its cheap half is the
    shape that passes for the wrong reason.
    """
    question = fixtures.question(
        registries, amounts=dict.fromkeys(sorted(registries.streams), amount)
    )
    enumerated = fixtures.enumerated(registries, question_=question)
    if not isinstance(enumerated, CandidateSet):
        return "refused"  # a refused question has no set, which is the point of refusing
    pairs = {(item.key.instrument_id, item.key.stream_id) for item in enumerated.candidates}
    assert len(pairs) + len(enumerated.no_candidate) == enumerated.pairs_considered
    assert enumerated.pairs_considered == len(registries.access) * len(registries.streams)
    if not enumerated.candidates:
        return "empty"
    result = survey(
        registries=registries,
        routes=registries.routes,
        question=question,
        ceiling=fixtures.ceiling(10_000),
        benchmark=enumerated.candidates[0].key,
    )
    if not isinstance(result, CandidateSurvey):
        return "uncomparable"  # a two-stream set is refused, and there is nothing to count
    assert len(evaluated(result.comparison)) + len(dropped(result.comparison)) == len(
        enumerated.candidates
    )
    return "counted"


DOMESTIC = ("inzhur_direct", "inzhur_to_monobank")
"""The one pair the shipped declarations connect anything with.

Unioned into half the generated route sets on purpose: without it almost every case is an
empty set, and the second identity -- the one over evaluated and dropped -- would be asserted
on a population that is never populated.
"""


@given(
    instruments=st.lists(st.sampled_from(INSTRUMENTS), unique=True),
    routes=st.lists(st.sampled_from(ROUTES), unique=True),
    streams=st.lists(st.sampled_from(STREAMS), unique=True),
    connected=st.booleans(),
    amount=st.sampled_from([0.0, 1.0, 999.0, 10_000.0, 5_000_000.0]),
)
@settings(deadline=None, max_examples=150, suppress_health_check=[HealthCheck.too_slow])
def test_the_identities_hold_over_narrowed_registries(
    instruments: list[str],
    routes: list[str],
    streams: list[str],
    connected: bool,
    amount: float,
) -> None:
    _both_identities(
        _narrowed(
            instruments,
            sorted({*routes, *DOMESTIC}) if connected else routes,
            streams,
        ),
        Money(amount, fixtures.UAH, prov.EMPTY),
    )


def test_the_generated_cases_reach_the_second_identity_often_enough_to_mean_something() -> None:
    """The property's own control, run deterministically so it cannot itself be flaky.

    `hypothesis` gives no way to assert across examples, so the same space is walked here with
    a seeded sample and the branch each case reached is counted. If the second identity stops
    being reachable -- a fixture change, a narrowing that connects nothing -- this fails loudly
    instead of the property quietly asserting only its first half.
    """
    rng = random.Random(0)
    reached: collections.Counter[Reached] = collections.Counter()
    for _ in range(60):
        registries = _narrowed(
            rng.sample(INSTRUMENTS, rng.randint(0, len(INSTRUMENTS))),
            sorted({*rng.sample(ROUTES, rng.randint(0, len(ROUTES))), *DOMESTIC}),
            rng.sample(STREAMS, rng.randint(0, len(STREAMS))),
        )
        reached[_both_identities(registries, Money(10_000.0, fixtures.UAH, prov.EMPTY))] += 1
    assert reached["counted"] > 10, reached


def test_nothing_declared_at_all_considers_no_pairs_and_is_not_a_refusal() -> None:
    """An empty registry is a legitimate answer -- the declarations connect nothing -- and it
    is a different claim from a question that did not stand up."""
    enumerated = fixtures.enumerated(_narrowed([], [], []))
    assert isinstance(enumerated, CandidateSet), enumerated
    assert enumerated.pairs_considered == 0
    assert enumerated.candidates == ()
    assert enumerated.no_candidate == ()


def test_every_pair_yielding_nothing_still_partitions_the_pairs() -> None:
    """No routes at all: every pair is in the third column and none is a drop."""
    registries = _narrowed(INSTRUMENTS, [], STREAMS)
    enumerated = fixtures.enumerated(registries)
    assert isinstance(enumerated, CandidateSet), enumerated
    assert enumerated.candidates == ()
    assert len(enumerated.no_candidate) == enumerated.pairs_considered
    assert enumerated.pairs_considered == len(INSTRUMENTS) * len(STREAMS)


def test_every_candidate_dropped_still_closes_the_second_identity() -> None:
    """An amount below every declared minimum ticket: the set is full and empty after
    evaluation, and the tally accounts for all of it."""
    registries = _narrowed(INSTRUMENTS, ROUTES, [fixtures.SALARY])
    question = fixtures.question(
        registries, amounts={fixtures.SALARY: Money(1.0, fixtures.UAH, prov.EMPTY)}
    )
    enumerated = fixtures.enumerated(registries, question_=question)
    assert isinstance(enumerated, CandidateSet), enumerated
    result = survey(
        registries=registries,
        routes=registries.routes,
        question=question,
        ceiling=fixtures.ceiling(10_000),
        benchmark=enumerated.candidates[0].key,
    )
    assert isinstance(result, CandidateSurvey), result
    assert evaluated(result.comparison) == ()
    assert len(dropped(result.comparison)) == len(enumerated.candidates)
