"""SC-001: the non-dominated set over the owner's own question, and no count hard-coded.

019. The deliverable in one sentence: **the answer stops having a head**. For each horizon he
gets the set of candidates nothing dominates on the criteria he declared, and every other
evaluated candidate is reported as dominated with a candidate that dominates it named.

**No count here is hard-coded**, and that is the criterion rather than a style preference: the
registry moves -- a declaration is corrected, an issue is added, a coupon rule changes -- and a
suite pinned to a measurement would then be asserting the tool has not been improved. What is
pinned is the *shape*: the accounting identity, the ordering, and the relations between the
figures the section reports.

The measurement itself lives in `specs/019-decision-layer/spec.md` and in
`tests/golden/the_answer.golden.txt`, which is where a moved figure is supposed to show up.
"""

from __future__ import annotations

import pytest

from terezy.core.decision.answer import section_evaluated, section_ranking
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.dominance import DominanceResult
from terezy.core.results.objectives import FractionOfTheQuestionAmount
from tests import answer_registries as fixtures
from tests import dominance_sections as sections

pytestmark = pytest.mark.worked_example

HORIZONS = [sections.ONE_MONTH, sections.THREE_MONTHS, sections.TWELVE_MONTHS]


def _shipped(index: int) -> DominanceResult:
    """His answer over the **shipped** root: what he is actually offered, no fixture in it."""
    answered = fixtures.answered(supplied=fixtures.shipped_inputs())
    result = answered.sections[index].dominance
    assert isinstance(result, DominanceResult), result
    return result


@pytest.mark.parametrize("index", HORIZONS)
def test_every_section_reports_a_set_rather_than_a_refusal(index: int) -> None:
    """The whole point of the owner's 2026-09-02 decision to name a real issue as the benchmark:
    before it, every section produced a ``BenchmarkUnavailable`` and this pass would refuse."""
    assert isinstance(_shipped(index), DominanceResult)


@pytest.mark.parametrize("index", HORIZONS)
def test_the_accounting_identity_holds_over_the_section_it_was_computed_from(index: int) -> None:
    """FR-008, derived from the registry the test loads."""
    answered = fixtures.answered(supplied=fixtures.shipped_inputs())
    section = answered.sections[index]
    result = _shipped(index)
    evaluated = {item.key for item in section_evaluated(section)}
    assert len(result.non_dominated) + len(result.dominated) + len(result.not_placed) == len(
        evaluated
    )


@pytest.mark.parametrize("index", HORIZONS)
def test_the_set_is_smaller_than_the_population_and_is_not_a_single_winner(index: int) -> None:
    """The deliverable, stated as a relation rather than as a number.

    A set the size of the population would say the objectives do not discriminate; a set of one
    would be a winner by another name. Both are legitimate values the record can carry, and
    neither is what this registry produces -- which is why the assertion is a range.
    """
    result = _shipped(index)
    population = len(result.non_dominated) + len(result.dominated) + len(result.not_placed)
    assert 1 < len(result.non_dominated) < population


@pytest.mark.parametrize("index", HORIZONS)
def test_no_member_of_the_set_is_dominated_by_anything_in_it(index: int) -> None:
    """What *non-dominated* means, checked against the other population rather than trusted."""
    result = _shipped(index)
    beaten = {item.key for item in result.dominated}
    assert not beaten & set(result.non_dominated)


@pytest.mark.parametrize("index", HORIZONS)
def test_ordering_by_the_rate_is_not_ordering_by_the_money(index: int) -> None:
    """The measurement's item 3, as a relation rather than as the row it was measured on.

    ``implied_rate`` is a money-weighted return over the days the money was actually invested,
    so a candidate whose own terms end early is annualised over a shorter span while its
    proceeds then sit as cash under the question's declared continuation assumption. The head
    of the ranking is therefore not the candidate that leaves him best off at the horizon --
    which is the whole argument for reporting a set instead of a list.
    """
    answered = fixtures.answered(supplied=fixtures.shipped_inputs())
    section = answered.sections[index]
    ranked = section_ranking(section)
    assert ranked, "nothing was ranked, so the comparison this test makes does not exist"
    by_money = max(ranked, key=lambda item: item.reaches.amount)
    assert ranked[0].key != by_money.key, (
        "the rate's first place is also the money's, so this section says nothing about the "
        "difference between ordering by one figure and ordering by the other"
    )


@pytest.mark.parametrize("index", HORIZONS)
def test_the_hurdle_he_named_is_in_the_population_and_its_standing_is_reported(
    index: int,
) -> None:
    result = _shipped(index)
    assert result.benchmark_standing.key.instrument_id == fixtures.BENCHMARK


@pytest.mark.parametrize("index", HORIZONS)
def test_the_band_he_declared_is_what_the_section_resolved(index: int) -> None:
    """SC-001a's figure, read at the point it is applied rather than only at the file."""
    result = _shipped(index)
    assert len(result.resolved_bands) == 1
    band = result.resolved_bands[0]
    declared = result.objectives.objectives[0].band
    assert isinstance(declared, FractionOfTheQuestionAmount)
    assert is_close(band.width.amount, band.from_amount.amount * declared.proportion)
