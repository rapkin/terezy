"""The real figure is reported beside the nominal one and never sorted on (024 FR-017, FR-018).

Principle VI's display rule in another shape: a figure added for the reader must not reorder
the answer. It is the cheapest defect here to introduce and the hardest to notice, so it is
asserted by running the whole answer twice under two different beliefs and comparing every
field of it -- rather than by reading the call graph, which says what the code does today.

**Two alternative beliefs, and the second one is the one that bites.** Deflating by a higher
rate is monotone in the nominal figure, so an answer sorted on the real rate under 25% inflation
would come out in the same order as one sorted under 10% -- which makes that pair alone a test
that passes for the wrong reason. Declaring **no** belief is the discriminator: every assumed
half is then typed-unavailable, and a ranking that consulted one would have nothing to sort by.

The candidate survey's recorded digest is asserted alongside, because it covers the candidate
key, the amount reached and the nominal rate -- the three ranking inputs -- and this feature
moves none of them.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest

from terezy.core.decision.answer import section_evaluated, section_ranking
from terezy.core.decision.candidates import dropped
from terezy.core.inflation.series import InflationAssumption
from terezy.core.results.answer import Answer, HorizonSection
from terezy.core.results.candidates import CandidateSurvey
from terezy.core.results.tuple import Comparison
from tests import answer_registries as fixtures

pytestmark = pytest.mark.contract

GOLDEN_FILE: Final = Path(__file__).parents[1] / "golden" / "candidate_set.golden.txt"
RECORDED_DIGEST: Final = "9ee9fb7897d14afc2f35901fd8f51817"
"""The digest recorded in `candidate_set.golden.txt`, retyped here so that a regeneration of
that artefact does not carry this assertion along with it. It covers the key, the amount and
the nominal rate; FR-018 is that this feature moves none of the three."""

OTHER_BELIEF: Final = InflationAssumption(
    id="test_quarter_inflation",
    annual_rate=0.25,
    is_assumption=True,
    rationale=(
        "TEST FIXTURE -- not a forecast. Far enough from the declared 10% that every real "
        "rate in the answer moves by more than any declared band, so a ranking that consulted "
        "one would reorder."
    ),
    provenance=None,
    kind=None,
)


def _under(assumption: InflationAssumption | None) -> Answer:
    supplied = fixtures.shipped_inputs()
    return fixtures.answered(
        supplied=replace(supplied, registries=replace(supplied.registries, inflation=assumption))
    )


def _survey(section: HorizonSection) -> CandidateSurvey | None:
    return section.outcome if isinstance(section.outcome, CandidateSurvey) else None


def _declared() -> Answer:
    return _under(fixtures.shipped_inputs().registries.inflation)


ALTERNATIVES: Final = [
    pytest.param(OTHER_BELIEF, id="a_higher_rate"),
    pytest.param(None, id="none"),
]


@pytest.mark.parametrize("belief", ALTERNATIVES)
def test_another_belief_produces_the_same_ranking_in_the_same_order(
    belief: InflationAssumption | None,
) -> None:
    """US2 scenario 1's first half: order by key, position by position."""
    declared, other = _declared(), _under(belief)

    for one, two in zip(declared.sections, other.sections, strict=True):
        assert [item.key for item in section_ranking(one)] == [
            item.key for item in section_ranking(two)
        ]


@pytest.mark.parametrize("belief", ALTERNATIVES)
def test_another_belief_moves_no_amount_rate_refusal_or_dominance_verdict(
    belief: InflationAssumption | None,
) -> None:
    """The rest of scenario 1: every field that is not the real slot, compared bit for bit."""
    declared, other = _declared(), _under(belief)

    for one, two in zip(declared.sections, other.sections, strict=True):
        for left, right in zip(section_evaluated(one), section_evaluated(two), strict=True):
            assert left.key == right.key
            assert left.reaches == right.reaches
            assert left.implied_rate == right.implied_rate
            assert left.arrivals == right.arrivals
            assert left.outlay == right.outlay
            assert replace(left, real=right.real) == right
        assert _refusals(one) == _refusals(two)
        assert one.dominance == two.dominance


def _refusals(section: HorizonSection) -> tuple[object, ...]:
    """Every candidate the comparison dropped, with the typed reason it was dropped for."""
    survey = _survey(section)
    if survey is None or not isinstance(survey.comparison, Comparison):
        return (type(section.outcome).__name__,)
    return tuple(dropped(survey.comparison))


@pytest.mark.parametrize("belief", ALTERNATIVES)
def test_only_the_real_slots_differ_between_the_two_answers(
    belief: InflationAssumption | None,
) -> None:
    """The other half of the claim: the belief did reach the figures, so the tests above are not
    passing because nothing changed at all."""
    declared, other = _declared(), _under(belief)
    moved = [
        left.key.instrument_id
        for one, two in zip(declared.sections, other.sections, strict=True)
        for left, right in zip(section_evaluated(one), section_evaluated(two), strict=True)
        if left.real != right.real
    ]

    assert moved


def test_the_candidate_surveys_recorded_digest_is_unchanged() -> None:
    """FR-018 and US2 scenario 2. A digest that moved would mean a ranking input changed."""
    recorded = [
        line for line in GOLDEN_FILE.read_text(encoding="utf-8").splitlines() if "[digest]" in line
    ]

    assert len(recorded) == 1
    assert RECORDED_DIGEST in recorded[0]


def test_no_module_that_orders_a_comparison_names_the_real_slot() -> None:
    """FR-017 as a property of the call graph, which is what makes it hard to lose.

    A source scan rather than an ordinary test because the claim is about *absence* -- nothing
    reads the field -- and no behavioural test can distinguish "not sorted on" from "sorted on,
    and the two orders happen to agree". The two answers above cover the behaviour; this covers
    the reason it cannot regress under a registry where they would agree by luck.
    """
    ordering = Path(__file__).parents[2] / "src" / "terezy" / "core" / "decision"
    named = {
        path.name
        for path in sorted(ordering.glob("*.py"))
        if ".real" in path.read_text(encoding="utf-8")
    }

    assert named == {"tuple_outcome.py"}, sorted(named)
