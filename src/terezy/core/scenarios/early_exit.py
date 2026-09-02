"""What an early-exit figure rests on: that the quotation holds, net of what detaches from it.

015 FR-032. A horizon means the money comes out at its end, so an instrument whose terms run
past it is **sold** there. The price it is sold at is a declaration observed on one day; whether
that declaration still describes the market on the exit date is not.

**The quotation is not carried forward unchanged.** A bond's price falls by a coupon on the day
that coupon detaches, so a holding credited a coupon inside the window and sold at a price
quoted while the coupon was still attached is credited it twice. What is assumed to hold is the
quotation **as this holding's price on the day it is bought, net of every coupon that detached
after that** -- the clean price is taken as constant and the price moves only by detachment
(:func:`price_at`).

**Nobody can observe it, and that is why it is a belief rather than a term.** A platform that
committed to its quoted buyback price would have declared a *term*, and there would be no
assumption to make. The assumption exists precisely because none does -- which is also why this
record carries no citation keys: there is nothing for a source to vouch for.

**The figure it produces errs in stated directions**, and what it does not account for reaches
a reader as this feature's typed exclusions rather than as prose here (FR-033;
``core.results.answer.Exclusion``, where each claim carries its own warrant for having a sign
or not having one).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Literal

from terezy.core.primitives import money
from terezy.core.primitives.money import Money

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Iterable


@dataclass(frozen=True, slots=True, kw_only=True)
class QuotationHolds:
    """The owner's declared belief that an observed quotation holds, net of detachment."""

    id: str
    """Named in every outcome that rests on it, so a reader can find the file."""

    is_assumption: Literal[True]
    """Not a bool. There is no observed case, and a ``Literal`` says so where a bool invites
    one -- ``FundDeclaration.is_assumption_driven``'s reading."""

    rationale: str
    """Why the owner is willing to assume it, in his own words. Required and non-empty."""


@dataclass(frozen=True, slots=True, kw_only=True)
class SoldEarly:
    """The position closed by a sale at the horizon's end rather than by its own terms.

    015 FR-029, and ``FundProjection.exit_line``'s shape for a bond: a reported line saying
    what the early exit did, so a reader is never left to infer it from a date. Its absence is
    the ordinary case -- the window reached maturity, no spread was paid, and no figure carries
    the assumption's mark.
    """

    on: date
    """The horizon's last day, which is when the money comes out."""

    units: float
    """What was still held: the purchase plus every reinvestment, less what payments retired."""

    price_per_unit: Money
    """What one unit fetched: :func:`price_at`'s answer, read back off the sale event."""

    proceeds: Money
    """``units x price_per_unit``. Gross: the disposal's tax is charged like any other."""

    assumption: QuotationHolds
    """The belief the figure rests on, named so a reader can find the file (FR-032)."""


def price_at(
    quotation: Money,
    *,
    observed_on: date,
    held_from: date,
    sold_on: date,
    coupons: Iterable[tuple[date, Money]],
) -> Money:
    """The quotation less every coupon per unit that detached while this holding held it.

    ``coupons`` is the instrument's whole per-unit coupon schedule -- the holding's units are
    not in it, and neither is any filtering: which of them detached is decided here, once, or
    the two instrument forms would decide it twice and come to disagree.

    **A coupon dated on the sale day counts as detached**, and the convention is the one the
    schedule generators already fix rather than a new one: ``enumerated`` pays every payment
    with ``payment.on <= horizon.end`` and ``fixed_income`` pays a coupon whose ``paid_on``
    equals the window's end and refuses to reinvest it. The holder receives it, so it has left
    the price by the time he sells.

    **The window opens at the LATER of the quotation and the purchase**, and the purchase half
    is what stops this fix from becoming its own wrong number: the *buy* quotation of the same
    morning is carried to the purchase date **unadjusted** by the code that sizes the purchase,
    so a coupon detaching between the two dates is out of both legs or in neither. Subtracting
    it here alone would report a loss of a whole coupon that nobody took. What is double-counted,
    and all that is, is a coupon the holding both **receives** and is still credited with inside
    its sale price. Reached on the shipped registry, and pinned in
    ``tests/worked_examples/test_a_coupon_inside_the_window.py`` rather than described here.

    **Accrued interest is not modelled** and this does not model it: the residual between the
    accrual inside the quotation and the accrual on the sale date is what this subtraction
    leaves behind, and it is stated as its own exclusion rather than estimated.
    """
    since = max(observed_on, held_from)
    detached = [amount for on, amount in coupons if since < on <= sold_on]
    return money.sub(quotation, money.total(detached, quotation.currency))


def rests_on(assumption: QuotationHolds) -> str:
    """How an outcome computed through the belief names it in ``TupleOutcome.rests_on``.

    One place, because that field is what SC-025's walk reads: a sentence composed at each site
    would let one site quietly stop saying it while the walk kept passing on the others.
    """
    return (
        f"the observed resale quotation is assumed to be this holding's price on the day it "
        f"is bought and to fall only by the coupons that detach after that "
        f"({assumption.id}): {assumption.rationale}"
    )


__all__ = ["QuotationHolds", "SoldEarly", "price_at", "rests_on"]
