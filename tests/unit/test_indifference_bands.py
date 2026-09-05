"""SC-006: too close to call is reported as too close to call, and never as a partition.

019 FR-011, FR-011a, FR-011d. Principle I's own sentence, one level down from allocations:
*reporting 51.3% when anything in 40-60% is indistinguishable is a defect, not a rounding
choice*. The relation is symmetric, is reported per candidate, and is **not** transitive -- so
there is no partition to report and any procedure producing one depends on an anchor the
objectives do not fix.

Asserted over figure vectors rather than over registries, because the four cases turn on where
two figures sit relative to a band and no declaration puts them there on purpose.
"""

from __future__ import annotations

from typing import Final

from terezy.core.decision.dominance import relates
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.dominance import (
    LeftDominates,
    MoneyFigure,
    MoneyWidth,
    RightDominates,
    TooCloseToCall,
)
from terezy.core.results.objectives import ObjectiveDirection

BAND: Final = 6.0
"""A six-hryvnia band on a single money objective. Wide enough that the arithmetic below is
readable, and orders of magnitude above the slack at these magnitudes."""

MORE: Final = (ObjectiveDirection.MORE_IS_BETTER,)
WIDTHS: Final = (MoneyWidth(amount=Money(BAND, Currency.UAH, prov.EMPTY)),)


def _at(amount: float) -> tuple[MoneyFigure]:
    return (MoneyFigure(amount=Money(amount, Currency.UAH, prov.EMPTY)),)


def _width(amount: float) -> tuple[MoneyWidth]:
    return (MoneyWidth(amount=Money(amount, Currency.UAH, prov.EMPTY)),)


def _verdict(left: float, right: float) -> object:
    return relates(_at(left), _at(right), directions=MORE, widths=WIDTHS)


def test_two_candidates_inside_the_band_are_too_close_to_call() -> None:
    """100 against 105 is five hryvnia apart inside a six-hryvnia band."""
    assert isinstance(_verdict(100.0, 105.0), TooCloseToCall)
    assert isinstance(_verdict(105.0, 100.0), TooCloseToCall)


def test_moving_one_past_the_band_replaces_that_with_a_dominance_verdict() -> None:
    """The pair is the criterion: the first half alone passes for an implementation that calls
    everything indistinguishable, and this is the half that fails it."""
    assert isinstance(_verdict(107.0, 100.0), LeftDominates)
    assert isinstance(_verdict(100.0, 107.0), RightDominates)


def test_a_difference_exactly_the_band_wide_is_not_strict() -> None:
    """FR-007's strict half is *better by more than the band*, so the boundary is inclusive of
    indifference and exclusive of dominance. Written out because an implementation reaching for
    ``>=`` here would report a winner at exactly the width the owner called indistinguishable."""
    assert isinstance(_verdict(106.0, 100.0), TooCloseToCall)


def test_closeness_does_not_chain_and_no_partition_is_produced() -> None:
    """FR-011a's three candidates: 100 ~ 105 and 105 ~ 110, and 100 against 110 is not close.

    Asserted in **both** candidate orders, because a partition built by anchoring on the first
    member produces ``{100, 105}`` in one order and ``{105, 110}`` in the other -- and FR-025
    orders by the candidate key, so the anchor would be an instrument id.
    """
    figures = (100.0, 105.0, 110.0)
    for order in (figures, tuple(reversed(figures))):
        close = {
            (left, right)
            for left in order
            for right in order
            if left != right and isinstance(_verdict(left, right), TooCloseToCall)
        }
        assert close == {(100.0, 105.0), (105.0, 100.0), (105.0, 110.0), (110.0, 105.0)}


def test_one_width_per_pair_is_what_makes_the_relation_symmetric() -> None:
    """SC-006's fourth case, and the pair it is asserted on is the criterion rather than a detail.

    A fraction resolved against **each candidate's own figure** gives *A* against *B* a
    different width from *B* against *A*, and FR-011's relation stops being symmetric. The two
    orders disagree only where the gap lies **between** the two widths, so that is the pair:
    figures of 10.00 and 6.00 at a half-of-itself fraction produce widths of 5.00 and 3.00, and
    the gap of 4.00 sits inside one and outside the other.

    Under the question's own amount there is **one** width for the pair, whatever it is, so both
    orders give the same verdict -- which is why FR-011d puts the resolution on the question.
    """
    per_candidate = (10.0 * 0.5, 6.0 * 0.5)
    gap = 10.0 - 6.0
    assert per_candidate[1] < gap < per_candidate[0]

    wider, narrower = (_width(value) for value in per_candidate)
    left_first = relates(_at(10.0), _at(6.0), directions=MORE, widths=wider)
    right_first = relates(_at(6.0), _at(10.0), directions=MORE, widths=narrower)
    assert isinstance(left_first, TooCloseToCall)
    assert isinstance(right_first, RightDominates), (
        "the two orders agree under per-candidate widths, so this pair is not the criterion"
    )

    one = _width(4.0)
    assert isinstance(relates(_at(10.0), _at(6.0), directions=MORE, widths=one), TooCloseToCall)
    assert isinstance(relates(_at(6.0), _at(10.0), directions=MORE, widths=one), TooCloseToCall)
