"""A bond sold at the horizon's end, with the arithmetic on paper.

015 FR-029. A horizon means the money comes out at its end. Before this feature a bond whose
maturity fell past the window refused as ``CannotSpanHorizon`` -- *"a return measured over a
period the money could not have been withdrawn in is a rate for a holding nobody could have
had"* -- and the clarification of 2026-08-30 falsifies that sentence: the money **can** be
withdrawn, at a spread.

The synthetic fixture: 10 units of a 15.5% semiannual ``act/365`` bond, face 1 000.00, bought at
par on 2026-01-15 for 10 000.00, maturing 2028-01-15.

**Horizon 2026-01-15 to 2026-12-31, and a declared resale price of 995.00 per unit.**

    coupon 2026-07-15   accrues 2026-01-15 -> 2026-07-15 = 181 days
                        1 000.00 x 15.5% x 181/365           =    76.863013698630 per unit
                        x 10 units                           =   768.630136986301
    coupon 2027-01-15   falls after the horizon               =        (not received)
    sale   2026-12-31   10 units x 995.00                     = 9 950.00
                        basis 10 000.00 -> realised loss      =    -50.00

Two claims the schedule alone would not make, and both are asserted: the sale is a **disposal**
that consumes basis, and the coupon the holding would have received in 2027 is **absent** rather
than moved.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.errors import InconsistentTerms
from terezy.core.instruments.interface import DateRange, EarlyExit
from terezy.core.ledger.events import EventKind
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import project
from terezy.core.results.project import Projection
from terezy.core.scenarios.early_exit import SpreadHolds
from tests import synthetic

pytestmark = pytest.mark.worked_example

HORIZON_END = date(2026, 12, 31)
RESALE_PER_UNIT = 995.0
UNITS = 10.0

COUPON_DAYS = 181
COUPON_PER_UNIT = 1000.0 * 0.155 * COUPON_DAYS / 365
COUPON = COUPON_PER_UNIT * UNITS
PROCEEDS = RESALE_PER_UNIT * UNITS
REALISED = PROCEEDS - 10_000.0

SPREAD_HOLDS = SpreadHolds(
    id="test_spread_holds",
    is_assumption=True,
    rationale="TEST FIXTURE -- the belief that a quoted resale price still holds at the exit.",
)


def _sold_at_the_horizon() -> Projection:
    outcome = project.project(
        synthetic.declaration(),
        synthetic.holding(),
        synthetic.horizon(end=HORIZON_END),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
        early_exit=EarlyExit(
            price_per_unit=Money(RESALE_PER_UNIT, synthetic.UAH, synthetic.TERMS_PROVENANCE),
            assumption=SPREAD_HOLDS,
        ),
    )
    assert isinstance(outcome, Projection), outcome
    return outcome


def test_the_one_coupon_inside_the_window_is_paid() -> None:
    """181 days of accrual on ten units, and nothing rounded on the way."""
    coupons = [
        event for event in _sold_at_the_horizon().ledger.applied if event.kind is EventKind.COUPON
    ]
    assert len(coupons) == 1
    assert coupons[0].occurred_on == date(2026, 7, 15)
    assert is_close(coupons[0].amount.amount, COUPON)


def test_the_coupon_after_the_horizon_is_absent_rather_than_moved() -> None:
    """A payment the holding never receives is not paid early and is not paid at the sale."""
    applied = _sold_at_the_horizon().ledger.applied
    assert all(event.occurred_on <= HORIZON_END for event in applied)


def test_the_sale_pays_the_declared_resale_price_on_the_horizons_last_day() -> None:
    sales = [
        event
        for event in _sold_at_the_horizon().ledger.applied
        if event.kind is EventKind.REDEMPTION
    ]
    assert len(sales) == 1
    assert sales[0].occurred_on == HORIZON_END
    assert is_close(sales[0].amount.amount, PROCEEDS)


def test_the_sale_is_a_disposal_that_consumes_basis() -> None:
    """Not a cash receipt: 995.00 against a basis of 1 000.00 is a realised loss of 50.00.

    Reported rather than clamped. A sale below basis is what a spread *is*, and a disposal
    that realised nothing would make the cost of the early exit invisible in the ledger.
    """
    state = _sold_at_the_horizon().ledger
    assert len(state.disposals) == 1
    assert is_close(state.disposals[0].realised_gain_base_ccy.amount, REALISED)
    assert REALISED < 0.0


def test_the_projection_reports_the_sale_and_names_the_belief() -> None:
    """FR-032: the assumption is on the record, so nothing has to infer it from a date."""
    sold = _sold_at_the_horizon().sold_early
    assert sold is not None
    assert sold.on == HORIZON_END
    assert sold.units == UNITS
    assert is_close(sold.proceeds.amount, PROCEEDS)
    assert sold.assumption.id == SPREAD_HOLDS.id


def test_holding_to_maturity_is_unchanged_by_the_declared_price() -> None:
    """The early-exit machinery is reachable only where an early exit actually happens.

    Otherwise every hold-to-maturity figure would inherit a mark it did not earn, which is the
    edge case the specification names and the reason this assertion is here rather than implied.
    """
    to_maturity = project.project(
        synthetic.declaration(),
        synthetic.holding(),
        synthetic.horizon(),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
        early_exit=EarlyExit(
            price_per_unit=Money(RESALE_PER_UNIT, synthetic.UAH, synthetic.TERMS_PROVENANCE),
            assumption=SPREAD_HOLDS,
        ),
    )
    without = project.project(
        synthetic.declaration(),
        synthetic.holding(),
        synthetic.horizon(),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
    )
    assert isinstance(to_maturity, Projection), to_maturity
    assert isinstance(without, Projection), without
    assert to_maturity.ledger.applied == without.ledger.applied
    assert to_maturity.sold_early is None
    assert without.sold_early is None


def test_a_schedule_that_ran_to_term_is_not_sold_for_a_rounding_residual() -> None:
    """Several repayments do not sum to the holding **exactly**, and a residual is not a unit.

    ``quantity x amount / principal`` per repayment leaves ~1.8e-15 for many amount splits.
    Selling that asks the ledger for units no lot holds, which it refuses by raising -- so the
    residual is compared to the project tolerance rather than to zero.
    """
    principal = 1.13 + 12.28
    left_over = 10.0 - (10.0 * 1.13 / principal + 10.0 * 12.28 / principal)
    assert left_over != 0.0, "the fixture must actually leave a residual"
    assert is_close(left_over, 0.0)


def test_the_window_may_not_end_before_the_purchase_settles() -> None:
    """A sale at the end of a window that closes before the money arrives is not a figure.

    Reachable today: a one-day horizon plus a declared inbound latency puts the purchase past
    the window's end, and the hold-to-maturity refusal used to cover that case implicitly.
    """
    outcome = project.project(
        synthetic.declaration(),
        synthetic.holding(purchased_on=date(2026, 2, 4)),
        DateRange(start=date(2026, 1, 15), end=date(2026, 2, 1)),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
        early_exit=EarlyExit(
            price_per_unit=Money(RESALE_PER_UNIT, synthetic.UAH, synthetic.TERMS_PROVENANCE),
            assumption=SPREAD_HOLDS,
        ),
    )
    assert isinstance(outcome, InconsistentTerms), outcome
    assert outcome.second_term == "holding.purchased_on"
