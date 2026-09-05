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

**A fixture whose subject is the sale quotes the resale price on its own sale day**, so nothing
detaches between the quotation and the sale and the arithmetic above is the whole of it. What a
quotation taken *earlier* is worth on the sale day is a separate rule with its own tests below;
separating the two is what lets each be checked on paper.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.errors import InconsistentTerms
from terezy.core.instruments import fixed_income
from terezy.core.instruments.interface import DateRange, EarlyExit
from terezy.core.ledger.events import EventKind
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import SourceRef
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import project
from terezy.core.results.project import Projection
from terezy.core.scenarios.early_exit import QuotationHolds
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

QUOTATION_HOLDS = QuotationHolds(
    id="test_quotation_holds",
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
            observed_on=HORIZON_END,
            assumption=QUOTATION_HOLDS,
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
    assert sold.assumption.id == QUOTATION_HOLDS.id


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
            observed_on=synthetic.horizon().end,
            assumption=QUOTATION_HOLDS,
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
            observed_on=date(2026, 2, 1),
            assumption=QUOTATION_HOLDS,
        ),
    )
    assert isinstance(outcome, InconsistentTerms), outcome
    assert outcome.second_term == "holding.purchased_on"


def test_a_coupon_paid_on_the_day_of_the_sale_is_not_reinvested() -> None:
    """The round trip nobody made: bought at face and surrendered at the resale price, same day.

    ``_decide`` already refuses to reinvest the **last** coupon for this exact reason, and the
    guard was written against the maturity date rather than against the window's end. Under a
    reinvesting policy it would post a gain equal to units x (resale price - face value), and a
    disposal-gain charge on a trade that never happened.
    """
    coupon_day = date(2026, 7, 15)
    outcome = project.project(
        synthetic.declaration(),
        synthetic.holding(),
        synthetic.horizon(end=coupon_day),
        synthetic.assumptions(coupon_policy="reinvest"),
        tax_classes=synthetic.TAX_PACK,
        early_exit=EarlyExit(
            price_per_unit=Money(RESALE_PER_UNIT, synthetic.UAH, synthetic.TERMS_PROVENANCE),
            observed_on=coupon_day,
            assumption=QUOTATION_HOLDS,
        ),
    )
    assert isinstance(outcome, Projection), outcome
    assert not [event for event in outcome.ledger.applied if event.kind is EventKind.REINVESTMENT]
    assert outcome.sold_early is not None
    assert outcome.sold_early.units == UNITS


def test_a_sale_says_the_contractual_figure_is_no_longer_to_maturity() -> None:
    """FR-023a's rule at the level below: an exclusion that is not stated is a silent default."""
    sold = _sold_at_the_horizon()
    assert any("declared resale price" in claim for claim in sold.hurdle.excludes), (
        sold.hurdle.excludes
    )
    to_maturity = project.project(
        synthetic.declaration(),
        synthetic.holding(),
        synthetic.horizon(),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
    )
    assert isinstance(to_maturity, Projection), to_maturity
    assert not [claim for claim in to_maturity.hurdle.excludes if "resale" in claim]


def test_what_the_position_gets_back_is_the_sale_rather_than_the_principal() -> None:
    """015 FR-029 at the record the disposal-gain rule reads.

    ``PurchasePremium`` says what **this** holding gets back, and a maturity the window ends
    before is not it: reporting the paper's 10 000.00 principal there would state a premium of
    zero over a sale that realised a loss of 50.00, and the record and the ledger would then
    disagree about the same trade -- one of them governing a tax class.
    """
    sold = _sold_at_the_horizon()
    assert is_close(sold.at_purchase.principal_returned.amount, PROCEEDS)
    assert is_close(sold.at_purchase.difference.amount, -REALISED)
    assert is_close(sold.ledger.disposals[0].realised_gain_base_ccy.amount, REALISED)

    to_maturity = project.project(
        synthetic.declaration(),
        synthetic.holding(),
        synthetic.horizon(),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
    )
    assert isinstance(to_maturity, Projection), to_maturity
    assert to_maturity.at_purchase.principal_returned != sold.at_purchase.principal_returned


QUOTED_ON = date(2026, 1, 15)
"""The purchase day, so the one coupon inside the window detaches after the quotation."""

CARRIED_PER_UNIT = RESALE_PER_UNIT - COUPON_PER_UNIT
CARRIED_PROCEEDS = CARRIED_PER_UNIT * UNITS


def test_the_sale_price_is_the_quotation_less_the_coupon_that_detached() -> None:
    """A quotation taken before the coupon does not still contain it on the sale day.

        quoted 2026-01-15    995.000000000000 per unit
        coupon 2026-07-15    1 000.00 x 15.5% x 181/365   =   76.863013698630 per unit
        sale   2026-12-31    995.00 - 76.863013698630     =  918.136986301370 per unit
                             x 10 units                   = 9 181.369863013699

    The check that makes it more than a subtraction: the coupon and the sale together come to
    768.630136986301 + 9 181.369863013699 = **9 950.00**, which is ten units at the quoted
    995.00 exactly. Carrying the quotation forward unchanged reached 9 950.00 + 768.63 instead
    -- the coupon once as income and once inside a price quoted while it was still attached.
    """
    outcome = project.project(
        synthetic.declaration(),
        synthetic.holding(),
        synthetic.horizon(end=HORIZON_END),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
        early_exit=EarlyExit(
            price_per_unit=Money(RESALE_PER_UNIT, synthetic.UAH, synthetic.TERMS_PROVENANCE),
            observed_on=QUOTED_ON,
            assumption=QUOTATION_HOLDS,
        ),
    )
    assert isinstance(outcome, Projection), outcome
    sold = outcome.sold_early
    assert sold is not None
    assert is_close(sold.price_per_unit.amount, CARRIED_PER_UNIT)
    assert is_close(sold.proceeds.amount, CARRIED_PROCEEDS)
    assert is_close(COUPON + CARRIED_PROCEEDS, PROCEEDS)
    assert is_close(
        outcome.ledger.disposals[0].realised_gain_base_ccy.amount,
        CARRIED_PROCEEDS - 10_000.0,
    )


def test_a_zero_coupon_issue_sells_at_the_whole_quotation() -> None:
    """Nothing detaches from a bond that pays nothing before it redeems, whenever it is quoted.

    A zero-coupon declaration is a valid instrument and not a missing rate, so the sale is
    struck at the whole quotation. ``coupons_per_unit`` returns early rather than generating a
    schedule of zero-amount periods -- the two give the same price, and the early return is
    what keeps a reader from looking for a coupon that does not exist.
    """
    outcome = project.project(
        synthetic.declaration(terms=synthetic.terms(coupon_rate=0.0)),
        synthetic.holding(),
        synthetic.horizon(end=HORIZON_END),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
        early_exit=EarlyExit(
            price_per_unit=Money(RESALE_PER_UNIT, synthetic.UAH, synthetic.TERMS_PROVENANCE),
            observed_on=QUOTED_ON,
            assumption=QUOTATION_HOLDS,
        ),
    )
    assert isinstance(outcome, Projection), outcome
    assert outcome.sold_early is not None
    assert is_close(outcome.sold_early.price_per_unit.amount, RESALE_PER_UNIT)


def test_a_coupon_paid_on_the_day_of_the_sale_has_already_left_the_price() -> None:
    """The boundary, pinned rather than described.

    The seller receives a coupon dated on the day he sells -- ``enumerated`` pays every payment
    with ``payment.on <= horizon.end`` and this module's own reinvestment guard fires on
    ``paid_on >= horizon.end`` -- so it has detached by the time the price is struck. A
    half-open window ending before the sale day would pay the coupon and sell at a price that
    still held it, which is the whole defect one day narrower.

        quoted 2026-01-15    995.000000000000 per unit
        coupon 2026-07-15    paid ON the sale day                  =   76.863013698630
        sale   2026-07-15    995.00 - 76.863013698630              =  918.136986301370
    """
    sale_day = date(2026, 7, 15)
    outcome = project.project(
        synthetic.declaration(),
        synthetic.holding(),
        synthetic.horizon(end=sale_day),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
        early_exit=EarlyExit(
            price_per_unit=Money(RESALE_PER_UNIT, synthetic.UAH, synthetic.TERMS_PROVENANCE),
            observed_on=QUOTED_ON,
            assumption=QUOTATION_HOLDS,
        ),
    )
    assert isinstance(outcome, Projection), outcome
    paid = [event for event in outcome.ledger.applied if event.kind is EventKind.COUPON]
    assert [event.occurred_on for event in paid] == [sale_day]
    assert outcome.sold_early is not None
    assert outcome.sold_early.on == sale_day
    assert is_close(outcome.sold_early.detached_per_unit.amount, COUPON_PER_UNIT)
    assert is_close(outcome.sold_early.price_per_unit.amount, CARRIED_PER_UNIT)


def test_a_quotation_worth_less_than_its_own_coupons_refuses_by_name() -> None:
    """Two declarations that cannot both describe the same paper, refused rather than struck.

    Unreachable on the shipped registry -- at most three coupons of ~85 leave a quotation of
    ~1 000 -- and reached here by quoting one unit at 100.00 while 231.863013698630 of coupon
    detaches over a window spanning three of them. Without the guard the sale is struck at a
    negative price and the ledger posts a disposal of a negative amount, which is a raise from
    the pure core on a condition two data files produced.
    """
    outcome = project.project(
        synthetic.declaration(),
        synthetic.holding(),
        synthetic.horizon(end=date(2027, 7, 15)),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
        early_exit=EarlyExit(
            price_per_unit=Money(100.0, synthetic.UAH, synthetic.TERMS_PROVENANCE),
            observed_on=QUOTED_ON,
            assumption=QUOTATION_HOLDS,
        ),
    )
    assert isinstance(outcome, InconsistentTerms), outcome
    assert outcome.first_term == "access.resale_price.per_unit"
    assert outcome.second_term == "instrument.schedule.payment"
    assert "cannot be worth less than the coupons it still contains" in outcome.reason


MOVED_ISSUE = date(2026, 1, 5)
MOVED_ACCRUAL_END = date(2026, 7, 5)
MOVED_PAID_ON = date(2026, 7, 6)
MOVED_PER_UNIT = 76.863013698630
MOVED_STRUCK = 918.136986301370
"""A coupon whose accrual ends on a Sunday and is therefore paid on the Monday, bought on the
Sunday itself. The only pair of dates on this fixture that can tell the two readings of
*whose coupon is it* apart.

The amounts are written out rather than recomputed: a test that derives what it asserts from
the same two dates the engine uses cannot tell a reader that the arithmetic beside it is
right."""


def test_a_coupon_the_business_day_rule_moves_past_the_purchase_is_bought_with_the_paper() -> None:
    """Ownership and detachment read the **same** date, and this is the day they could differ.

    The accrual ends 2026-07-05, a Sunday, so ``following`` pays it on the Monday. Buy on the
    Sunday and the two readings disagree: the unadjusted end is not after the purchase, the paid
    date is. Reading the unadjusted one for ownership and the paid one for detachment would take
    the coupon out of the sale price while crediting it to the seller -- the branch's own
    defect, one leg over.

        accrual     2026-01-05 -> 2026-07-05                   =      181 days
        coupon paid 2026-07-06   1 000.00 x 15.5% x 181/365    =   76.863013698630 per unit
        sale        2026-12-31   995.00 - 76.863013698630      =  918.136986301370 per unit
    """
    terms = synthetic.terms(issue_date=MOVED_ISSUE, maturity_date=date(2028, 1, 5))
    assert (MOVED_ACCRUAL_END - MOVED_ISSUE).days == 181
    outcome = project.project(
        synthetic.declaration(terms=terms),
        synthetic.holding(purchased_on=MOVED_ACCRUAL_END),
        synthetic.horizon(start=MOVED_ISSUE, end=HORIZON_END),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
        early_exit=EarlyExit(
            price_per_unit=Money(RESALE_PER_UNIT, synthetic.UAH, synthetic.TERMS_PROVENANCE),
            observed_on=MOVED_ISSUE,
            assumption=QUOTATION_HOLDS,
        ),
    )
    assert isinstance(outcome, Projection), outcome
    paid = [event for event in outcome.ledger.applied if event.kind is EventKind.COUPON]
    assert [event.occurred_on for event in paid] == [MOVED_PAID_ON]
    assert outcome.sold_early is not None
    assert is_close(outcome.sold_early.detached_per_unit.amount, MOVED_PER_UNIT)
    assert is_close(outcome.sold_early.price_per_unit.amount, MOVED_STRUCK)


def test_a_coupon_before_the_quotation_is_already_out_of_it() -> None:
    """The lower bound is the quotation's own day, and it is not the purchase date.

    Quoted on the sale day, the same holding pays the same 2026-07-15 coupon and sells at the
    full 995.00: a coupon that detached *before* the quotation was taken was never in it, so
    subtracting it would report a loss the holder never took.
    """
    sold = _sold_at_the_horizon().sold_early
    assert sold is not None
    assert is_close(sold.price_per_unit.amount, RESALE_PER_UNIT)


REINVEST_UNITS = 100.0
REINVEST_COST = 100_000.0
REINVEST_END = date(2027, 12, 31)
UNITS_AT_THE_SALE = 123.0
"""100 bought, then 7, 8 and 8 whole units bought out of the three coupons inside the window."""

BASIS_AT_THE_SALE = REINVEST_COST + 7_000.0 + 8_000.0 + 8_000.0
REINVEST_PROCEEDS = UNITS_AT_THE_SALE * RESALE_PER_UNIT
PREMIUM_ON_WHAT_WAS_BOUGHT = REINVEST_COST - REINVEST_UNITS * RESALE_PER_UNIT


def _reinvested_then_sold() -> Projection:
    outcome = project.project(
        synthetic.declaration(),
        synthetic.holding(
            quantity=REINVEST_UNITS,
            cost=Money(REINVEST_COST, synthetic.UAH, synthetic.holding().cost.provenance),
        ),
        synthetic.horizon(end=REINVEST_END),
        synthetic.assumptions(coupon_policy=fixed_income.REINVEST),
        tax_classes=synthetic.TAX_PACK,
        early_exit=EarlyExit(
            price_per_unit=Money(RESALE_PER_UNIT, synthetic.UAH, synthetic.TERMS_PROVENANCE),
            observed_on=REINVEST_END,
            assumption=QUOTATION_HOLDS,
        ),
    )
    assert isinstance(outcome, Projection), outcome
    return outcome


def test_reinvestment_plus_a_moved_quotation_is_refused_rather_than_priced() -> None:
    """One quotation cannot price units bought on different days.

    The sale applies a single per-unit adjustment to every unit held, and a unit bought out of
    the 2026-07-15 coupon was not in existence when that coupon detached -- so it would be
    discounted for a coupon it never contained. Quoted on the sale day (the fixture above)
    nothing detaches and the sale stands; quoted earlier it refuses by name.
    """
    outcome = project.project(
        synthetic.declaration(),
        synthetic.holding(
            quantity=REINVEST_UNITS,
            cost=Money(REINVEST_COST, synthetic.UAH, synthetic.holding().cost.provenance),
        ),
        synthetic.horizon(end=REINVEST_END),
        synthetic.assumptions(coupon_policy=fixed_income.REINVEST),
        tax_classes=synthetic.TAX_PACK,
        early_exit=EarlyExit(
            price_per_unit=Money(RESALE_PER_UNIT, synthetic.UAH, synthetic.TERMS_PROVENANCE),
            observed_on=QUOTED_ON,
            assumption=QUOTATION_HOLDS,
        ),
    )
    assert isinstance(outcome, InconsistentTerms), outcome
    assert outcome.first_term == "assumptions.coupon_policy"
    assert outcome.second_term == "access.resale_price"
    assert "units acquired on different dates" in outcome.reason


def test_the_premium_measures_the_units_the_purchase_paid_for() -> None:
    """A schedule that reinvests ends holding more units than the outlay bought.

        bought 2026-01-15    100 units for                     = 100 000.00
        reinvested                 7 + 8 + 8 whole units       =  23 000.00 of coupons
        sale   2027-12-31    123 units x 995.00                = 122 385.00
                             basis 123 000.00 -> realised      =    -615.00
        at purchase          100 units x 995.00                =  99 500.00
                             paid 100 000.00 -> premium        =     500.00

    Measuring the **sale** against the **purchase** would set 122 385.00 against 100 000.00 and
    report a par purchase sold at a spread as a discount of 22 385.00 -- a figure the
    disposal-gain class then governs. The two sides count one population or the record is a
    statement about no trade that happened.
    """
    outcome = _reinvested_then_sold()
    assert outcome.sold_early is not None
    assert outcome.sold_early.units == UNITS_AT_THE_SALE
    assert is_close(outcome.sold_early.proceeds.amount, REINVEST_PROCEEDS)
    assert is_close(outcome.at_purchase.paid.amount, REINVEST_COST)
    assert is_close(outcome.at_purchase.principal_returned.amount, REINVEST_UNITS * RESALE_PER_UNIT)
    assert is_close(outcome.at_purchase.difference.amount, PREMIUM_ON_WHAT_WAS_BOUGHT)
    assert is_close(
        outcome.ledger.disposals[0].realised_gain_base_ccy.amount,
        REINVEST_PROCEEDS - BASIS_AT_THE_SALE,
    )


QUOTE_SOURCE = SourceRef(
    id="synthetic:resale_quote",
    citation="SYNTHETIC FIXTURE -- an invented resale quote. Not an observation of any venue.",
    retrieved_on=date(2026, 8, 31),
    verified_on=None,
)


def test_the_figure_is_marked_by_the_quote_and_not_by_the_terms() -> None:
    """Principle I at the level a gate cannot see: which file a reader is sent to.

    The whole purchase is sold here, so what comes back is the struck price times a quantity the
    holding declared and the terms had no part in. Carrying the terms' sources **on account of
    the quantity** would say the figure rests on the issue's declaration, and a reader chasing
    the unverified mark would open the wrong file. Nothing is dropped either: the quote's own
    mark is on the figure.

    **Quoted on the sale day, so nothing detached and the struck price is the quotation.** That
    is what makes the set equality below a statement about the *quantity* rather than about the
    price: where a coupon does detach the schedule's sources join the price and belong there,
    which `test_a_coupon_inside_the_window.py` asserts on the owner's own answer.
    """
    outcome = project.project(
        synthetic.declaration(),
        synthetic.holding(),
        synthetic.horizon(end=HORIZON_END),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
        early_exit=EarlyExit(
            price_per_unit=Money(RESALE_PER_UNIT, synthetic.UAH, prov.of([QUOTE_SOURCE])),
            observed_on=HORIZON_END,
            assumption=QUOTATION_HOLDS,
        ),
    )
    assert isinstance(outcome, Projection), outcome
    assert set(outcome.at_purchase.principal_returned.provenance.sources) == {QUOTE_SOURCE}
