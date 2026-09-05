"""FR-011c: a band that does not clear the slack produces a refusal, not a set.

Both conditions, and the second is the one a plan drops: the floor is ``band > slack`` **and**
``band >= (p - 1) * slack``. At two objectives the second is implied by the first and looks
redundant; at three it is the whole guarantee, and the specification's own verified
counterexample is what a floor of one slack lets through -- ``(0, 0, 0)``, ``(-1.6, 0.8, 0.8)``
and ``(-0.8, -0.8, 1.6)`` at a band of one and a half slacks form a three-cycle with every
candidate placed and the set **empty**.

**The check cannot live at load, and that is the requirement rather than an inconvenience.** The
slack is not a constant: it depends on the magnitudes of the figures compared, which a
declaration file does not carry. So the band the shipped question resolves to -- 5.00 UAH on
figures near 50 000, where the slack is 5e-5 -- clears the floor by five orders of magnitude,
and a band that does not has to be planted.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

import pytest

from terezy.core.decision.dominance import relates
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import TOLERANCE, slack
from terezy.core.results.dominance import (
    BandBelowTheAcyclicityFloor,
    DominanceResult,
    LeftDominates,
    MoneyFigure,
    MoneyWidth,
)
from terezy.core.results.objectives import (
    AbsoluteBand,
    Criterion,
    DaysBand,
    FractionOfTheQuestionAmount,
    ObjectiveDirection,
)
from tests import dominance_sections as sections

S: Final = TOLERANCE
"""One slack, at magnitudes of at most one, where the tolerance's absolute half dominates."""


def _uah(amount: float) -> Money:
    return Money(amount, Currency.UAH, prov.EMPTY)


def _figures(*values: float) -> tuple[MoneyFigure, ...]:
    return tuple(MoneyFigure(amount=_uah(value)) for value in values)


def test_a_band_narrower_than_the_slack_lets_two_candidates_dominate_each_other() -> None:
    """FR-011c's **first** clause, load-bearing at every objective count including two.

    At a slack of one and a band of half a slack, two candidates differing by ``(0.8, -0.8)``
    each clear the other's weak half -- both differences are inside one slack -- and each is
    strictly better on one, by more than half a slack. Both dominate, the set is empty over a
    population both of whose members are placed, and the relation says so by raising rather than
    returning a verdict it cannot justify.
    """
    band = (MoneyWidth(amount=_uah(0.5 * S)), MoneyWidth(amount=_uah(0.5 * S)))
    directions = (ObjectiveDirection.MORE_IS_BETTER,) * 2
    with pytest.raises(AssertionError, match="dominate each other"):
        relates(
            _figures(0.8 * S, 0.0),
            _figures(0.0, 0.8 * S),
            directions=directions,
            widths=band,
        )


def test_a_band_of_one_and_a_half_slacks_at_three_objectives_admits_a_three_cycle() -> None:
    """FR-011c's ***(p - 1)* factor**, and why a floor of one slack is not enough.

    The specification's own triple, verified 2026-09-03. Every pair yields a verdict, no pair
    raises, and yet no candidate survives: A dominates B, B dominates C, and C dominates A.
    """
    band = (MoneyWidth(amount=_uah(1.5 * S)),) * 3
    directions = (ObjectiveDirection.MORE_IS_BETTER,) * 3
    vectors = [
        _figures(0.0, 0.0, 0.0),
        _figures(-1.6 * S, 0.8 * S, 0.8 * S),
        _figures(-0.8 * S, -0.8 * S, 1.6 * S),
    ]
    dominated = {
        index
        for index, vector in enumerate(vectors)
        for other in vectors
        if isinstance(relates(other, vector, directions=directions, widths=band), LeftDominates)
    }
    assert len(dominated) == len(vectors), (
        "the triple no longer forms a cycle, so this test no longer says why the (p - 1) "
        "factor is load-bearing"
    )
    assert 1.5 * S > S, "the band clears a floor of ONE slack, which is the whole point"
    assert 1.5 * S < 2.0 * S, "and fails the (p - 1) = 2 floor, which is what refuses it"


def test_the_shipped_band_clears_the_floor_by_orders_of_magnitude() -> None:
    """Why the cases above have to be planted: on figures near 50 000 the slack is 5e-5."""
    section = sections.section()
    result = sections.result(section)
    assert isinstance(result, DominanceResult)
    width = result.resolved_bands[0].width.amount
    assert width == pytest.approx(5.0)
    assert width > slack(50_000.0, 50_000.0) * (len(result.objectives.objectives) - 1)


def test_a_band_below_the_floor_produces_the_refusal_and_no_set() -> None:
    """SC-007's second half: the case that would otherwise have nothing asserting it.

    The band clears FR-011b's load-time check -- it is finite and strictly positive -- and fails
    here, against figures a declaration file has never seen.
    """
    declared = sections.objectives()
    tiny = replace(
        declared,
        objectives=(
            replace(declared.objectives[0], band=AbsoluteBand(amount=_uah(1e-8))),
            declared.objectives[1],
        ),
    )
    refusal = sections.run(sections.section(), declared=tiny)
    assert isinstance(refusal, BandBelowTheAcyclicityFloor)
    assert refusal.criterion is Criterion.MONEY_AT_THE_ENDPOINT
    assert refusal.objective_count == 2
    assert refusal.slack == pytest.approx(slack(50_529.0, 50_529.0), rel=1e-3)
    assert refusal.resolved == _uah(1e-8)


def test_the_refusal_names_the_width_a_fraction_resolved_to() -> None:
    """FR-011c: *where the band is a fraction, the width it resolved to*.

    A fraction reported without its width is a band nobody can check against a figure, and this
    is the one refusal that has both to hand.
    """
    declared = sections.objectives()
    tiny = replace(
        declared,
        objectives=(
            replace(
                declared.objectives[0],
                band=FractionOfTheQuestionAmount(proportion=1e-13),
            ),
            declared.objectives[1],
        ),
    )
    refusal = sections.run(sections.section(), declared=tiny)
    assert isinstance(refusal, BandBelowTheAcyclicityFloor)
    assert isinstance(refusal.declared, FractionOfTheQuestionAmount)
    assert refusal.resolved is not None
    assert refusal.resolved.amount == pytest.approx(1e-13 * 50_000.0)


def test_no_floor_is_checked_on_a_date_objective() -> None:
    """FR-011d fixes a date's slack at **zero**, so the floor reduces to FR-011b's positivity.

    Asserted by narrowing the day band to its smallest legal value and getting a set: a floor
    applied there with a money slack would refuse every section over any registry.
    """
    declared = sections.objectives()
    one_day = replace(
        declared,
        objectives=(
            declared.objectives[0],
            replace(declared.objectives[1], band=DaysBand(days=1)),
        ),
    )
    assert isinstance(sections.run(sections.section(), declared=one_day), DominanceResult)
