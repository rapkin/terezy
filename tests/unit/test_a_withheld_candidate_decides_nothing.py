"""SC-015: a candidate the section withheld is in no dominance population and decides nothing.

019 FR-006. 015 FR-030 withholds a candidate whose money the holding released after the window,
and the withholding is the point: *nothing could be ranked at one month, and here is why for
each* is only available if the figure is withheld rather than labelled. A pass that let a
withheld figure decide another candidate's standing would put that figure back in front of a
reader through the verdict it produced.

Asserted on ``inzhur_miltech``, which the owner's own question withholds from every section --
its plan requests an exit sixteen months past a one-month horizon.
"""

from __future__ import annotations

import pytest

from terezy.core.results.dominance import HurdleIsDominated
from tests import answer_registries as fixtures
from tests import dominance_sections as sections

HORIZONS = [sections.ONE_MONTH, sections.THREE_MONTHS, sections.TWELVE_MONTHS]


@pytest.mark.parametrize("index", HORIZONS)
def test_the_withheld_candidate_is_withheld_at_all_three_horizons(index: int) -> None:
    """The premise, checked rather than assumed: a registry change that stopped withholding it
    would leave every assertion below passing vacuously."""
    section = sections.section(index)
    assert fixtures.MILTECH in {item.key.instrument_id for item in section.arrives_after_horizon}
    assert fixtures.MILTECH in {item.key.instrument_id for item in sections.outcomes(section)}


@pytest.mark.parametrize("index", HORIZONS)
def test_it_is_in_no_dominance_population(index: int) -> None:
    result = sections.result(sections.section(index))
    named = (
        {key.instrument_id for key in result.non_dominated}
        | {item.key.instrument_id for item in result.dominated}
        | {item.key.instrument_id for item in result.not_placed}
    )
    assert fixtures.MILTECH not in named


@pytest.mark.parametrize("index", HORIZONS)
def test_it_decides_no_other_candidates_standing(index: int) -> None:
    """The half a membership check alone would miss: it could be absent from every population
    and still appear as the dominator on somebody else's record."""
    result = sections.result(sections.section(index))
    standing = result.benchmark_standing
    verdicts = [item for beaten in result.dominated for item in beaten.dominated_by]
    if isinstance(standing, HurdleIsDominated):
        verdicts.extend(standing.by)
    for verdict in verdicts:
        assert verdict.dominates.instrument_id != fixtures.MILTECH
        assert verdict.over.instrument_id != fixtures.MILTECH
    for pair in result.incomparable:
        assert fixtures.MILTECH not in (pair.left.instrument_id, pair.right.instrument_id)
    for close in result.indistinguishable:
        assert close.key.instrument_id != fixtures.MILTECH
        assert fixtures.MILTECH not in {key.instrument_id for key in close.neighbours}
