"""What an early-exit figure rests on: that the quotation holds, net of what detaches from it.

015 FR-032. A horizon means the money comes out at its end, so an instrument whose terms run
past it is **sold** there. The price it is sold at is a declaration observed on one day; whether
that declaration still describes the market on the exit date is not.

**The quotation is not carried forward unchanged.** A quoted bond price is a *dirty* price, and
it falls by a coupon on the day that coupon detaches, so a holding credited a coupon inside the
window and sold at a price quoted before it is credited that money twice. What is assumed to
hold is the quotation **net of every coupon that detached while the holding held it** -- the clean
price is taken as constant and the price moves only by detachment (:func:`detached_since`).

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
from terezy.core.primitives.currency import Currency
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
    """What one unit fetched: the quotation less :attr:`detached_per_unit`."""

    detached_per_unit: Money
    """What :func:`detached_since` took out of the quotation, per unit.

    Reported rather than read back: the struck :attr:`price_per_unit` and the quotation on the
    access record differ by exactly this, and a reader who has only the two prices cannot tell
    an adjustment from a spread. Zero is a real answer -- this sale carried no coupon
    adjustment at all -- and not an absence.
    """

    quoted_on: date
    """The day the quotation described the market. Reported because the gap between it and
    :attr:`on` is what the accrued-interest exclusion is about, and its **sign** is what decides
    whether that exclusion may state a direction at all."""

    skipped_before_purchase: Money
    """What left the quotation before this holding bought the paper, per unit, and was therefore
    subtracted from neither leg.

    Zero for all but two shipped issues, and it is what decides whether the accrued-interest
    residual has a warranted sign. The residual is ``a(sale) - a(quotation) + detached``: with
    nothing skipped, ``detached`` covers ``a(quotation)`` -- an accrual within a period is
    smaller than the coupon that ends it -- and the residual is positive. What is skipped is
    exactly what breaks that, because the coupon that reset the accrual comes out of neither
    price.
    """

    proceeds: Money
    """``units x price_per_unit``. Gross: the disposal's tax is charged like any other."""

    assumption: QuotationHolds
    """The belief the figure rests on, named so a reader can find the file (FR-032)."""


def detached_since(
    *,
    observed_on: date,
    held_from: date,
    sold_on: date,
    coupons: Iterable[tuple[date, Money]],
    currency: Currency,
) -> Money:
    """The per-unit coupons that left the quoted price between the quotation and the sale.

    ``coupons`` is the instrument's whole per-unit coupon schedule -- the holding's units are
    not in it, and neither is any filtering: which of them detached is decided here, once, or
    the two instrument forms would decide it twice and come to disagree.

    **A coupon dated on the sale day counts as detached**, and the convention is the one the
    schedule generators already fix rather than a new one: ``enumerated`` pays every payment
    with ``payment.on <= horizon.end`` and ``fixed_income`` pays a coupon whose ``paid_on``
    equals the window's end and refuses to reinvest it. The holder receives it, so it has left
    the price by the time he sells.

    **Carrying is forward-only, and a quotation newer than the date asked about is used
    unchanged.** The window is empty then, and that is the answer rather than an oversight: it
    is what a backdated scenario did before any of this existed -- several shipped fixtures ask
    about windows that closed months before the quotation was taken -- and adding the coupons
    back on would be a second, unstated assumption in the opposite direction. What ages a
    quotation is the staleness verdict, which already covers it.

    **The window opens at the LATER of the quotation and the purchase**, and the purchase half
    is what keeps the pair of quotations coherent. The *buy* quotation of the same morning
    sizes the purchase and is used as declared, so a coupon detaching between the quotation and
    the purchase is in both legs; subtracting it here alone would report a loss of a whole
    coupon that nobody took. Two shipped issues pay one on 2026-08-26, seven days before the
    owner's window buys. What is double-counted, and all that is, is a coupon the holding both
    **receives** and is still credited with inside its sale price.

    **No accrued-interest figure is computed here, and no price is split.** This subtracts whole
    declared coupon amounts on their declared dates, so 013 FR-017 is untouched -- and what it
    leaves behind is the accrual on either side, which is the exclusion every early-exit figure
    carries.
    """
    since = max(observed_on, held_from)
    return money.total([amount for on, amount in coupons if since < on <= sold_on], currency)


def rests_on(assumption: QuotationHolds) -> str:
    """How an outcome computed through the belief names it in ``TupleOutcome.rests_on``.

    One place, because that field is what SC-025's walk reads: a sentence composed at each site
    would let one site quietly stop saying it while the walk kept passing on the others.
    """
    return (
        f"the observed resale quotation is assumed to hold at the exit date, less every coupon "
        f"that detached while the holding held the paper ({assumption.id}): "
        f"{assumption.rationale}"
    )


__all__ = ["QuotationHolds", "SoldEarly", "detached_since", "rests_on"]
