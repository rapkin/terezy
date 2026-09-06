"""SC-004a: a planted triple for which *A > B* and *B > C* hold and *A > C* does not.

019 FR-007 states plainly that the relation is **not** transitive and does not claim it: the
weak half allows a slack, and slack does not compose, so a difference absorbed once at *A*
against *B* and again at *B* against *C* has accumulated twice by the time *A* meets *C*.
Acyclicity is what the never-empty guarantee needs; transitivity is not.

**Existential where SC-004's properties are universal.** Asserting non-transitivity over
generated inputs would fail on correct code, which is transitive on most triples. It earns its
place because an implementation that quietly strengthened the weak half into a bare
``advantage >= 0`` would become transitive and pass every other criterion in this feature -- and
would also withdraw a dominance verdict a large gap on one objective had earned, because of a
last-bit difference on another.

**The arithmetic is in slacks**, because that is the unit the rule is written in. At the scale
used here every figure is at most ``6e-9`` in magnitude, so the tolerance's absolute half
dominates its relative half and one slack is exactly ``TOLERANCE`` for every pair -- asserted
below rather than assumed.
"""

from __future__ import annotations

from typing import Final

import pytest

from terezy.core.decision.dominance import relates
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import TOLERANCE, slack
from terezy.core.results.dominance import (
    LeftDominates,
    MoneyFigure,
    MoneyWidth,
    Neither,
)
from terezy.core.results.objectives import ObjectiveDirection

pytestmark = pytest.mark.worked_example

S: Final = TOLERANCE
"""One slack, at this scale. ``test_one_slack_is_the_constant_at_this_scale`` pins it."""

BAND: Final = 2.0 * S
"""Two slacks. It clears FR-011c's floor at two objectives -- strictly above one slack, and at
least ``(p - 1) = 1`` of them -- so the triple below is inside the regime the pass permits."""

MORE = ObjectiveDirection.MORE_IS_BETTER
WIDTHS: Final = (
    MoneyWidth(amount=Money(BAND, Currency.UAH, prov.EMPTY)),
    MoneyWidth(amount=Money(BAND, Currency.UAH, prov.EMPTY)),
)
DIRECTIONS: Final = (MORE, MORE)

A: Final = (3.0 * S, 0.0)
B: Final = (0.0, 0.6 * S)
C: Final = (-3.0 * S, 1.2 * S)
"""The triple, in slacks, on two more-is-better hryvnia objectives.

A against B: objective 0 leads by 3.0 slacks, which exceeds the 2.0-slack band, so A is
strictly better there; objective 1 trails by 0.6 slacks, which is inside one slack, so the two
figures are the same money to the project comparison and the weak half holds. A dominates B.
B against C is the same two gaps, shifted, so B dominates C.

A against C: objective 0 leads by 6.0 slacks, and objective 1 now trails by **1.2** slacks --
the two 0.6s have accumulated, 1.2 slacks is not inside one slack, and the weak half fails. A
does not dominate C, and C does not dominate A either, its own objective 0 trailing by 6.0.
"""


def _vector(values: tuple[float, float]) -> tuple[MoneyFigure, ...]:
    return tuple(MoneyFigure(amount=Money(value, Currency.UAH, prov.EMPTY)) for value in values)


def _verdict(left: tuple[float, float], right: tuple[float, float]) -> object:
    return relates(_vector(left), _vector(right), directions=DIRECTIONS, widths=WIDTHS)


def test_one_slack_is_the_constant_at_this_scale() -> None:
    """The arithmetic above is in slacks, so the unit has to be what the code says it is."""
    assert slack(3.0 * S, -3.0 * S) == TOLERANCE
    assert slack(1.2 * S, 0.6 * S) == TOLERANCE


def test_a_dominates_b() -> None:
    verdict = _verdict(A, B)
    assert isinstance(verdict, LeftDominates)
    assert verdict.strictly_better_at == (0,)
    assert verdict.at_least_as_good_at == (0, 1)


def test_b_dominates_c() -> None:
    verdict = _verdict(B, C)
    assert isinstance(verdict, LeftDominates)
    assert verdict.strictly_better_at == (0,)


def test_a_does_not_dominate_c_and_neither_does_c_dominate_a() -> None:
    """The whole point. 0.6 + 0.6 slacks is 1.2 slacks, and slack does not compose."""
    assert isinstance(_verdict(A, C), Neither)
    assert isinstance(_verdict(C, A), Neither)


def test_the_witness_would_die_under_a_bare_weak_half() -> None:
    """What the triple is a witness *against*, said as arithmetic rather than as prose.

    Under ``advantage >= 0`` alone, A's 0.6-slack shortfall on objective 1 would withdraw the
    verdict its 3-slack lead on objective 0 earned, and the first two assertions above would
    fail. The gap is stated here so a reader can see it is real and smaller than one slack.
    """
    assert A[1] - B[1] < 0.0
    assert abs(A[1] - B[1]) < slack(A[1], B[1])
