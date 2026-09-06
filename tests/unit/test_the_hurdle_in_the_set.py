"""SC-008: the benchmark is a member of the population, and its standing is always reported.

019 FR-016, FR-017. Principle I requires naive baselines always scored and always shown, and 010
FR-012 already puts the hurdle inside the ranking rather than beside it. A dominance pass that
reported a set without saying where the hurdle sits in it would reintroduce the privileged side
channel one layer up.

**The wording is part of the criterion.** *Nothing dominates the hurdle* is not *the hurdle is
best*: other members may sit beside it in the set, better on one objective and worse on another,
and a hurdle that dominates everything is a different and stronger fact.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from terezy.core.decision.answer import section_evaluated
from terezy.core.results.dominance import HurdleIsDominated, NothingDominatesTheHurdle
from terezy.core.results.tuple import Comparison
from tests import answer_registries as fixtures
from tests import dominance_sections as sections

HORIZONS = [sections.ONE_MONTH, sections.THREE_MONTHS, sections.TWELVE_MONTHS]
DOMINATED_AT = [sections.ONE_MONTH, sections.THREE_MONTHS]
"""Where the owner's own benchmark is dominated, measured over the shipped registry. At twelve
months it is a member of the non-dominated set instead, which the pair of tests below is what
keeps apart from *the hurdle is best*."""


@pytest.mark.parametrize("index", HORIZONS)
def test_the_benchmark_appears_exactly_once_in_the_population(index: int) -> None:
    section = sections.section(index)
    result = sections.result(section)
    evaluated = [item.key for item in section_evaluated(section)]
    hurdle = result.benchmark_standing.key
    assert evaluated.count(hurdle) == 1
    assert hurdle.instrument_id == fixtures.BENCHMARK


@pytest.mark.parametrize("index", DOMINATED_AT)
def test_the_hurdle_the_owner_named_is_dominated_and_the_members_are_named(index: int) -> None:
    """Measured over the shipped registry: his own benchmark is dominated at his two shorter
    horizons."""
    standing = sections.result(sections.section(index)).benchmark_standing
    assert isinstance(standing, HurdleIsDominated)
    assert standing.by
    for verdict in standing.by:
        assert verdict.over == standing.key
        assert verdict.strictly_better_on


def test_at_twelve_months_his_benchmark_is_in_the_set_rather_than_under_it() -> None:
    """The other measured half, and the one his choice of benchmark was made for: over the
    longest horizon UA4000231195 runs very nearly to its own terms and nothing dominates it."""
    result = sections.result(sections.section(sections.TWELVE_MONTHS))
    standing = result.benchmark_standing
    assert isinstance(standing, NothingDominatesTheHurdle), standing
    assert standing.key in result.non_dominated
    assert len(result.non_dominated) > 1, "nothing dominates it is not it dominates everything"


def test_a_benchmark_nothing_dominates_produces_the_statement_rather_than_a_bare_set() -> None:
    """The other half of the pair, and the half that would otherwise never be reached.

    A member of the shipped twelve-month non-dominated set is named as the hurdle. Nothing
    dominates it -- that is what being in the set means -- and other members stand beside it,
    which is exactly the case the wording exists to keep apart from *the hurdle is best*.
    """
    twelve = sections.section(sections.TWELVE_MONTHS)
    survivor = sections.result(twelve).non_dominated[0]
    answered = fixtures.answered(
        replace(fixtures.owners_question(), benchmark_instrument_id=survivor.instrument_id)
    )
    result = sections.result(answered.sections[sections.TWELVE_MONTHS])
    standing = result.benchmark_standing
    assert isinstance(standing, NothingDominatesTheHurdle)
    assert standing.key.instrument_id == survivor.instrument_id
    assert standing.key in result.non_dominated
    assert len(result.non_dominated) > 1, (
        "the hurdle is the only member, so this case cannot distinguish *nothing dominates it* "
        "from *it dominates everything*, which is the whole of what the wording is for"
    )


def test_the_standing_is_not_derived_from_010s_one_dimensional_verdict() -> None:
    """FR-013: two verdicts about the hurdle exist and they answer different questions.

    010's ``beats_benchmark`` is strict, one-dimensional, on the **rate**, at the **project
    tolerance**; this one is a partial order over the declared objectives at the declared bands.
    Measured on the owner's own question they disagree -- which is the ordinary state rather
    than an edge case, because the rate is not a declared objective. The inclusion runs one
    way here: everything that dominates the hurdle also out-rates it, and things out-rate it
    that come home later and so dominate nothing.
    """
    section = sections.section(sections.ONE_MONTH)
    standing = sections.result(section).benchmark_standing
    assert isinstance(standing, HurdleIsDominated)
    comparison = section.outcome.comparison  # type: ignore[union-attr]
    assert isinstance(comparison, Comparison)
    beats = {comparison.ranked[index].key for index in comparison.beats_benchmark}
    dominators = {verdict.dominates for verdict in standing.by}
    assert beats - dominators, "every rate-beater also dominates the hurdle"
    assert not dominators - beats


@pytest.mark.parametrize("index", HORIZONS)
def test_neither_verdict_is_the_other_at_any_horizon(index: int) -> None:
    """And the disagreement is on the record rather than resolved, because resolving it needs a
    weight (FR-005). At twelve months it is at its sharpest: candidates out-rate the hurdle and
    none of them dominates it.

    The expected standing is asserted per horizon rather than read off the result. Without it
    the twelve-month case degenerates -- ``dominators`` is empty there, so ``beats !=
    dominators`` follows from ``beats`` alone and would survive the two verdicts becoming one.
    """
    section = sections.section(index)
    standing = sections.result(section).benchmark_standing
    comparison = section.outcome.comparison  # type: ignore[union-attr]
    assert isinstance(comparison, Comparison)
    beats = {comparison.ranked[position].key for position in comparison.beats_benchmark}
    assert beats
    if index in DOMINATED_AT:
        assert isinstance(standing, HurdleIsDominated), standing
        assert beats != {verdict.dominates for verdict in standing.by}
    else:
        assert isinstance(standing, NothingDominatesTheHurdle), standing
