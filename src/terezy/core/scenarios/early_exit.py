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

**The figure it produces errs in stated directions.** It replaces a distribution with a point
for the one option chosen for its optionality, so the early exit is reported as more certain
than it is; the quote is a seller's, which widens exactly when a forced sale is most likely, so
the spread is understated; rate risk is symmetric and is **not** signed; and accrued interest is
not modelled at all, so what :func:`price_at` leaves behind is the difference between the
accrual carried in the quotation and the accrual on the sale date, which is unsigned too. The
four claims reach a reader as this feature's typed exclusions (FR-033).
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
    is what stops this fix from becoming its own wrong number. Two shipped issues pay a coupon
    on 2026-08-26 -- after the 2026-08-24 quotation and before the owner's window opens -- and
    the *purchase* quote observed the same morning is carried to the purchase date **unadjusted**
    by the code that sizes the purchase. Subtracting such a coupon here would price one leg of
    one morning's two quotations net of it and the other gross, reporting a loss of a whole
    coupon that nobody took. What is double-counted, and all that is, is a coupon the holding
    both **receives** and is still credited with inside its sale price.

    **Accrued interest is not modelled** and this does not model it: the residual between the
    accrual inside the quotation and the accrual on the sale date is a known, smaller error,
    stated as its own exclusion because its sign cannot be warranted.
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
