"""SC-012: every dominance verdict carries the marks of both figures behind it.

019 FR-022. Principle I's propagation rule applies to a comparison exactly as it applies to a
figure: *A dominates B* computed from two unverified figures is an unverified claim, and a
verdict that looked cleaner than either figure behind it would be a lost mark -- the top
severity class regardless of how small the code change is.

**Walked over the whole result rather than sampled** (010 SC-009's rule): every verdict on every
dominated candidate and on the hurdle's standing, at every horizon.
"""

from __future__ import annotations

import pytest

from terezy.core.decision.answer import section_evaluated
from terezy.core.primitives import provenance as prov
from terezy.core.primitives import staleness
from terezy.core.results.dominance import DominanceVerdict, HurdleIsDominated
from tests import dominance_sections as sections

HORIZONS = [sections.ONE_MONTH, sections.THREE_MONTHS, sections.TWELVE_MONTHS]


def _every_verdict(result: object) -> list[DominanceVerdict]:
    """Every verdict the result holds, from both places it holds one."""
    verdicts = [item for beaten in result.dominated for item in beaten.dominated_by]  # type: ignore[attr-defined]
    standing = result.benchmark_standing  # type: ignore[attr-defined]
    if isinstance(standing, HurdleIsDominated):
        verdicts.extend(standing.by)
    return verdicts


@pytest.mark.parametrize("index", HORIZONS)
def test_every_verdict_carries_the_union_of_both_candidates_marks(index: int) -> None:
    section = sections.section(index)
    result = sections.result(section)
    marks = {item.key: item.provenance for item in section_evaluated(section)}
    verdicts = _every_verdict(result)
    assert verdicts, "no verdict was produced here, so the walk proves nothing"
    for verdict in verdicts:
        expected = prov.merge(marks[verdict.dominates], marks[verdict.over])
        assert verdict.provenance == expected


@pytest.mark.parametrize("index", HORIZONS)
def test_every_verdict_carries_the_merged_staleness_of_both(index: int) -> None:
    section = sections.section(index)
    result = sections.result(section)
    aged = {item.key: item.staleness for item in section_evaluated(section)}
    for verdict in _every_verdict(result):
        expected = staleness.merge(aged[verdict.dominates], aged[verdict.over])
        assert verdict.staleness == expected


@pytest.mark.parametrize("index", HORIZONS)
def test_no_verdict_on_the_shipped_registry_is_unmarked(index: int) -> None:
    """On this registry every figure is unverified, so every verdict over it is too.

    Asserted as a fact about the registry rather than as a property of the pass: it is what
    makes the walk above catch a dropped mark instead of comparing two empty sets.
    """
    for verdict in _every_verdict(sections.result(sections.section(index))):
        assert verdict.provenance.sources, "a verdict is unmarked over a registry that is not"
