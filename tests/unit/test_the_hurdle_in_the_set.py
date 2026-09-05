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


@pytest.mark.parametrize("index", HORIZONS)
def test_the_benchmark_appears_exactly_once_in_the_population(index: int) -> None:
    section = sections.section(index)
    result = sections.result(section)
    evaluated = [item.key for item in section_evaluated(section)]
    hurdle = result.benchmark_standing.key
    assert evaluated.count(hurdle) == 1
    assert hurdle.instrument_id == fixtures.BENCHMARK


@pytest.mark.parametrize("index", HORIZONS)
def test_the_hurdle_the_owner_named_is_dominated_and_the_members_are_named(index: int) -> None:
    """Measured over the shipped registry: his own benchmark is dominated at every horizon."""
    standing = sections.result(sections.section(index)).benchmark_standing
    assert isinstance(standing, HurdleIsDominated)
    assert standing.by
    for verdict in standing.by:
        assert verdict.over == standing.key
        assert verdict.strictly_better_on


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
    Measured, they disagree in both directions on the owner's own question -- which is the
    ordinary state rather than an edge case, because the rate is not a declared objective.
    """
    section = sections.section(sections.ONE_MONTH)
    standing = sections.result(section).benchmark_standing
    assert isinstance(standing, HurdleIsDominated)
    comparison = section.outcome.comparison  # type: ignore[union-attr]
    assert isinstance(comparison, Comparison)
    beats = {comparison.ranked[index].key for index in comparison.beats_benchmark}
    dominators = {verdict.dominates for verdict in standing.by}
    assert dominators - beats, "every dominator also beats the hurdle on the rate"
    assert beats - dominators, "every rate-beater also dominates the hurdle"


@pytest.mark.parametrize("index", HORIZONS)
def test_neither_verdict_is_the_other_at_any_horizon(index: int) -> None:
    """And the disagreement is on the record rather than resolved, because resolving it needs a
    weight (FR-005). At twelve months every dominator happens to beat the hurdle too and the
    inclusion is one-way, which is why the pair above is asserted where both directions hold."""
    section = sections.section(index)
    standing = sections.result(section).benchmark_standing
    assert isinstance(standing, HurdleIsDominated)
    comparison = section.outcome.comparison  # type: ignore[union-attr]
    assert isinstance(comparison, Comparison)
    beats = {comparison.ranked[position].key for position in comparison.beats_benchmark}
    assert beats != {verdict.dominates for verdict in standing.by}
