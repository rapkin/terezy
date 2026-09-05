"""What a position closed at a horizon's end reports about the sale that closed it.

015 FR-029. A horizon means the money comes out at its end, so an instrument whose terms run
past it is **sold** there, at the resale quotation carried to that day
(:func:`terezy.core.instruments.accrual.carried_to`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from terezy.core.primitives.money import Money
from terezy.core.scenarios.quotation import QuotationHolds


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
    """What one unit fetched: :attr:`clean_per_unit` plus :attr:`accrued_per_unit`."""

    clean_per_unit: Money
    """The quotation net of the accrual it carried on the day it was observed.

    Reported rather than left to be re-derived: a reader holding the quotation and the struck
    price can otherwise not tell an accrual from a spread, and the clean price is the thing the
    owner's declared belief actually assumes constant (FR-022).
    """

    accrued_per_unit: Money
    """What one unit had accrued by the sale date. Zero is a real answer -- the sale fell on a
    coupon date, or the paper pays no coupon -- and not an absence."""

    quoted_on: date
    """The day the quotation described the market. Reported because the gap between it and
    :attr:`on` is what the belief was leaned on to cross; struck on the quotation's own day it
    was leaned on nowhere."""

    proceeds: Money
    """``units x price_per_unit``. Gross: the disposal's tax is charged like any other."""

    assumption: QuotationHolds
    """The belief the figure rests on, named so a reader can find the file (FR-032)."""


__all__ = ["SoldEarly"]
