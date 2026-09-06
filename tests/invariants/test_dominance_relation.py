"""SC-004: the relation is irreflexive, asymmetric and acyclic, and the set is never empty.

019 FR-007. The properties are asserted over **generated** figure vectors rather than over
registries, because the closed criterion set has two members and SC-004 requires at least three
objectives: the definition FR-007 rejects cannot empty the set at two objectives at all, so a
two-objective battery passes under both definitions and proves nothing.

**The acyclicity regime is reached by scale, not by a tolerance parameter** (research D2).
FR-007's measurement is stated with the slack taken as 1 against figures on ``[-6, 6]``. The
shipped slack is ``max(TOLERANCE * max(|a|, |b|), TOLERANCE)``, so where every figure is at most
1 in magnitude the absolute half dominates and the slack is exactly ``TOLERANCE`` for every
pair -- which makes figures uniform on ``[-6e-9, 6e-9]`` the measurement's ``[-6, 6]`` at slack
1, exactly, with the **shipped** comparison and no test hook in a production signature.
"""

from __future__ import annotations

from itertools import combinations
from typing import Final

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from terezy.core.decision.dominance import relates
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import TOLERANCE, slack
from terezy.core.results.dominance import (
    Incomparable,
    LeftDominates,
    MoneyFigure,
    MoneyWidth,
    Neither,
    PairVerdict,
    RightDominates,
    TooCloseToCall,
)
from terezy.core.results.objectives import ObjectiveDirection

pytestmark = pytest.mark.invariant

SCALE: Final = 1e-9
"""The scale at which the shipped slack is exactly ``TOLERANCE`` for every pair drawn below."""

SPREAD: Final = 6.0
"""FR-007's measurement draws every figure uniform on ``[-6, 6]`` at a slack of 1."""

MIN_OBJECTIVES: Final = 3
MAX_OBJECTIVES: Final = 5
MIN_CANDIDATES: Final = 3
MAX_CANDIDATES: Final = 5

FIGURES = st.floats(
    min_value=-SPREAD * SCALE, max_value=SPREAD * SCALE, allow_nan=False, allow_infinity=False
)


ONE_SLACK: Final = slack(SPREAD * SCALE, -SPREAD * SCALE)
"""The widest slack any pair drawn here is read at, taken from the shipped comparison rather
than written out. It is ``TOLERANCE`` exactly, which is what makes this scale the
measurement's -- asserted below rather than believed."""


def test_the_scale_puts_every_pair_at_the_absolute_half_of_the_tolerance() -> None:
    """Without this the battery could drift to a scale where the relative half dominates and a
    uniform draw never produces a cycle, at which point it would prove nothing."""
    assert ONE_SLACK == TOLERANCE


def _uah(value: float) -> MoneyFigure:
    return MoneyFigure(amount=Money(value, Currency.UAH, prov.EMPTY))


def _floor(count: int) -> float:
    """FR-011c's floor: strictly above one slack, and at least *(p - 1)* of them.

    The second term is what binds here, because the battery never draws fewer than three
    objectives and *(p - 1)* is then at least two slacks -- which already exceeds one.
    """
    return ONE_SLACK * (count - 1)


Battery = tuple[list[list[MoneyFigure]], list[MoneyWidth], list[ObjectiveDirection]]
"""One drawn population: a vector per candidate, a width per objective, a direction per
objective. Every direction is more-is-better, because the sign of a direction is applied before
the relation sees a figure and a mixed battery would test the same relation twice."""


@st.composite
def _batteries(draw: st.DrawFn) -> Battery:
    """A population of candidates, a band per objective at or above FR-011c's floor."""
    objectives = draw(st.integers(min_value=MIN_OBJECTIVES, max_value=MAX_OBJECTIVES))
    candidates = draw(st.integers(min_value=MIN_CANDIDATES, max_value=MAX_CANDIDATES))
    vectors = [[_uah(draw(FIGURES)) for _ in range(objectives)] for _ in range(candidates)]
    floor = _floor(objectives)
    widths = [
        MoneyWidth(
            amount=Money(
                draw(st.floats(min_value=floor, max_value=SPREAD * SCALE)),
                Currency.UAH,
                prov.EMPTY,
            )
        )
        for _ in range(objectives)
    ]
    directions = [ObjectiveDirection.MORE_IS_BETTER] * objectives
    return vectors, widths, directions


def _verdict(
    left: list[MoneyFigure],
    right: list[MoneyFigure],
    widths: list[MoneyWidth],
    directions: list[ObjectiveDirection],
) -> PairVerdict:
    return relates(left, right, directions=directions, widths=widths)


@settings(max_examples=400, suppress_health_check=[HealthCheck.too_slow])
@given(battery=_batteries())
def test_the_relation_is_irreflexive(battery: Battery) -> None:
    """Nothing dominates itself. A candidate that did would empty the set on its own."""
    vectors, widths, directions = battery
    for vector in vectors:
        assert isinstance(_verdict(vector, vector, widths, directions), TooCloseToCall)


@settings(max_examples=400, suppress_health_check=[HealthCheck.too_slow])
@given(battery=_batteries())
def test_the_relation_is_asymmetric(battery: Battery) -> None:
    """``relates`` raises where both directions hold, so reaching a verdict at all is the claim.

    Asserted the other way round as well: swapping the arguments must swap the verdict rather
    than producing a second, differently-shaped answer.
    """
    vectors, widths, directions = battery
    for left, right in combinations(vectors, 2):
        forward = _verdict(left, right, widths, directions)
        backward = _verdict(right, left, widths, directions)
        if isinstance(forward, LeftDominates):
            assert isinstance(backward, RightDominates)
        elif isinstance(forward, RightDominates):
            assert isinstance(backward, LeftDominates)
        else:
            assert type(forward) is type(backward)


@settings(max_examples=400, suppress_health_check=[HealthCheck.too_slow])
@given(battery=_batteries())
def test_the_relation_is_acyclic_and_the_set_is_never_empty_over_a_placed_population(
    battery: Battery,
) -> None:
    """The property FR-011c's floor exists to buy, and the one the rejected definition loses.

    Scoped to the **placed** population deliberately: a *not placed* candidate is in the
    population and in neither of the other two, so a section all of whose candidates are not
    placed has an empty set honestly. Nothing here can be *not placed* -- every figure is a
    hryvnia amount -- so the placed population is the whole of it.
    """
    vectors, widths, directions = battery
    dominated = {
        index
        for index, vector in enumerate(vectors)
        for other in vectors
        if isinstance(_verdict(other, vector, widths, directions), LeftDominates)
    }
    assert len(dominated) < len(vectors), (
        "every candidate is dominated, so the non-dominated set is empty over a population "
        "every member of which is placed -- which is the cycle FR-011c's floor exists to prevent"
    )


@settings(max_examples=400, suppress_health_check=[HealthCheck.too_slow])
@given(battery=_batteries())
def test_every_pair_lands_in_exactly_one_verdict(battery: Battery) -> None:
    """The five verdicts are disjoint by construction; this is what says so over real draws."""
    vectors, widths, directions = battery
    for left, right in combinations(vectors, 2):
        verdict = _verdict(left, right, widths, directions)
        assert isinstance(
            verdict, LeftDominates | RightDominates | TooCloseToCall | Neither | Incomparable
        )
