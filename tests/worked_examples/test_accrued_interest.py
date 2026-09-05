"""Accrued interest on a carried quotation, worked by hand on a real issue.

UA4000236228 pays 85.50 per unit on declared dates 2026-03-11, 2026-09-09 and 2027-03-10 --
182 days between each pair -- and declares ``day_count = "act/365"``. Inzhur quotes it on
2026-08-24 at 1089.32 to buy and 1087.89 to sell. The owner's one-month horizon opens
2026-09-01, ``inzhur_direct`` declares one day of latency, so the purchase settles 2026-09-02
and the sale is struck 2026-10-01.

A quotation is a **dirty** price. The interest accrued by the day it was observed comes out of
it, and the interest accrued by the day it is used goes back in::

    accrued(2026-08-24) = 85.50 x 166/182 =   77.98      166 days into [03-11, 09-09)
    accrued(2026-09-02) = 85.50 x 175/182 =   82.21      175 days into the same period
    accrued(2026-10-01) = 85.50 x  22/182 =   10.34       22 days into [09-09, 03-10)

    clean (buy)   = 1089.32 - 77.98 = 1011.34
    clean (sell)  = 1087.89 - 77.98 = 1009.91   the two clean prices differ by the whole
                                                1.43 spread, and by nothing else
    purchase 2026-09-02 = 1011.34 + 82.21 = 1093.55
    sale     2026-10-01 = 1009.91 + 10.34 = 1020.24

**The two-decimal columns are for a reader and the engine works unrounded**, so 1009.91 + 10.34
reads 1020.25 against a true 1020.2417. Every assertion below is therefore against the
unrounded expression -- ``85.50 * 166 / 182`` rather than ``77.98`` -- at the project tolerance.

What a reader can check without any decimals at all is the identity the model reduces to. The
clean price cancels between the two legs, so per unit::

    sale + coupon - purchase = 85.50 x 29/182 - 1.43 = 13.6236... - 1.43 = 12.1936...

29 days held at the issue's own 85.50 per 182 days, less the round-trip spread. On 45 units
that is 548.71, which is the gain the whole answer reports.
"""

from __future__ import annotations

import functools
from datetime import date

import pytest

from terezy.core.decision.answer import AnswerInputs, section_evaluated
from terezy.core.errors import InconsistentTerms
from terezy.core.instruments import accrual, registry
from terezy.core.instruments.interface import EnumeratedTerms, PaymentKind
from terezy.core.primitives.tolerance import TOLERANCE
from terezy.core.results.tuple import TupleOutcome
from tests import answer_registries as answers

pytestmark = pytest.mark.worked_example

WORKED = "UA4000236228"

QUOTED_ON = date(2026, 8, 24)
PURCHASED_ON = date(2026, 9, 2)
SOLD_ON = date(2026, 10, 1)

BUY_QUOTE = 1089.32
SELL_QUOTE = 1087.89
SPREAD = BUY_QUOTE - SELL_QUOTE

COUPON = 85.50
PERIOD_DAYS = 182
"""2026-03-11 to 2026-09-09, and 2026-09-09 to 2027-03-10. Both 182 days, asserted below off
the declared dates rather than trusted here."""

ACCRUED_AT_QUOTATION = COUPON * 166 / PERIOD_DAYS
ACCRUED_AT_PURCHASE = COUPON * 175 / PERIOD_DAYS
ACCRUED_AT_SALE = COUPON * 22 / PERIOD_DAYS

CLEAN_BUY = BUY_QUOTE - ACCRUED_AT_QUOTATION
CLEAN_SELL = SELL_QUOTE - ACCRUED_AT_QUOTATION
PURCHASE_PRICE = CLEAN_BUY + ACCRUED_AT_PURCHASE
SALE_PRICE = CLEAN_SELL + ACCRUED_AT_SALE

UNITS = 45.0
"""46 x 1093.55 is 50 303, which exceeds the declared 50 000, so 45 whole units is what the
declared minimum increment allows."""

DAYS_HELD = 29
"""2026-09-02 to 2026-10-01."""


@functools.cache
def _supplied() -> AnswerInputs:
    """What the tool ships, with no fixture overlaid. The owner's own answer is the subject."""
    return answers.shipped_inputs()


def _schedule() -> accrual.Schedule:
    """The worked issue's coupon schedule, through the plugin interface.

    ``ops_for`` rather than a direct call into either schedule module: what this module measures
    is the rule both declaration forms share, and reaching for one of them by name here would
    be this test knowing which form the declaration is in.
    """
    declared = _supplied().registries.instruments[WORKED]
    coupons = registry.ops_for(declared.instrument_class).coupons_per_unit(declared)
    return accrual.schedule_of(declared, coupons)


def _accrued(on: date) -> float:
    """The accrual per unit on one date, or the refusal, which is a failure here."""
    figure = accrual.accrued_on(
        _schedule(),
        on=on,
        currency=_supplied().registries.base_currency,
        dated_term="tests.worked_examples.test_accrued_interest",
    )
    assert not isinstance(figure, InconsistentTerms), figure
    return figure.amount


def _worked(horizon_index: int) -> TupleOutcome:
    section = answers.answered(supplied=_supplied()).sections[horizon_index]
    return next(item for item in section_evaluated(section) if item.key.instrument_id == WORKED)


def test_the_declared_dates_are_the_ones_the_arithmetic_above_assumes() -> None:
    """182-day periods and 85.50 a coupon, read off the declaration rather than retyped."""
    dated = {on: amount.amount for on, amount in _schedule().coupons}
    assert dated[date(2026, 3, 11)] == COUPON
    assert dated[date(2026, 9, 9)] == COUPON
    assert dated[date(2027, 3, 10)] == COUPON
    assert (date(2026, 9, 9) - date(2026, 3, 11)).days == PERIOD_DAYS
    assert (date(2027, 3, 10) - date(2026, 9, 9)).days == PERIOD_DAYS
    assert (PURCHASED_ON - QUOTED_ON).days == 9
    assert (SOLD_ON - PURCHASED_ON).days == DAYS_HELD
    assert _schedule().day_count == "act/365"


def test_the_accrual_on_each_of_the_three_dates() -> None:
    """77.98 at the quotation, 82.21 at the purchase, 10.34 at the sale."""
    assert _accrued(QUOTED_ON) == pytest.approx(ACCRUED_AT_QUOTATION, abs=TOLERANCE)
    assert _accrued(PURCHASED_ON) == pytest.approx(ACCRUED_AT_PURCHASE, abs=TOLERANCE)
    assert _accrued(SOLD_ON) == pytest.approx(ACCRUED_AT_SALE, abs=TOLERANCE)
    # The sale sits in the NEXT period, which is the whole reason the coupon subtraction this
    # feature deletes is not a rule of its own: detaching a coupon is the accrual resetting.
    assert _accrued(date(2026, 9, 9)) == 0.0
    assert _accrued(date(2026, 9, 8)) == pytest.approx(COUPON * 181 / PERIOD_DAYS, abs=TOLERANCE)


def _carried(quote: float, on: date) -> accrual.Carried:
    declared = _supplied().registries.access[WORKED]
    assert declared.quote is not None
    assert declared.resale_price is not None
    source = declared.quote if quote == BUY_QUOTE else declared.resale_price
    assert source.price.amount == quote
    carried = accrual.carried_to(
        _schedule(),
        quote=source.price,
        observed_on=source.observed_on,
        on=on,
        quoted_term="access.price.observed_on",
        dated_term="tests.worked_examples.test_accrued_interest",
    )
    assert not isinstance(carried, InconsistentTerms), carried
    return carried


def test_both_clean_prices_and_both_carried_prices() -> None:
    """1011.34 and 1009.91 clean; 1093.55 at the purchase and 1020.24 at the sale.

    The two clean prices differ by the whole 1.43 spread and by nothing else, which is what
    "one accrual, applied to both legs" means: the quotation's own day cancels out of the
    difference.
    """
    buy = _carried(BUY_QUOTE, PURCHASED_ON)
    sell = _carried(SELL_QUOTE, SOLD_ON)
    assert buy.clean.amount == pytest.approx(CLEAN_BUY, abs=TOLERANCE)
    assert sell.clean.amount == pytest.approx(CLEAN_SELL, abs=TOLERANCE)
    assert buy.clean.amount - sell.clean.amount == pytest.approx(SPREAD, abs=TOLERANCE)
    assert accrual.price(buy).amount == pytest.approx(PURCHASE_PRICE, abs=TOLERANCE)
    assert accrual.price(sell).amount == pytest.approx(SALE_PRICE, abs=TOLERANCE)


def test_the_identity_the_clean_price_cancels_out_of() -> None:
    """``sale + coupon - purchase == 85.50 x 29/182 - 1.43``, with no decimals to check.

    The clean price is assumed constant, so it leaves the round trip entirely: what a unit
    returns over the window is the issue's own accrual over the days held, less the spread
    between the two quotations of the same morning.
    """
    purchase = accrual.price(_carried(BUY_QUOTE, PURCHASED_ON)).amount
    sale = accrual.price(_carried(SELL_QUOTE, SOLD_ON)).amount
    assert sale + COUPON - purchase == pytest.approx(
        COUPON * DAYS_HELD / PERIOD_DAYS - SPREAD, abs=TOLERANCE
    )


def _sold_early(horizon_index: int) -> list[TupleOutcome]:
    section = answers.answered(supplied=_supplied()).sections[horizon_index]
    return [item for item in section_evaluated(section) if item.sold_early is not None]


def test_the_whole_answer_over_the_owners_month() -> None:
    """45 units, 49 209.66 deployed, 3 847.50 collected, 45 910.87 sold, 49 758.37 reached.

    ``reaches`` is what came home and excludes the 790.34 that never deployed, so the gain is
    ``reaches - deployed``: 548.71 on 49 209.66, **+1.1151% over 29 days held**. Annualised
    simple (x365/29) that is 14.03%; the engine's own ``implied_rate`` is an IRR over the whole
    span from the horizon's start and is a different figure, measured by the golden.
    """
    outcome = _worked(0)
    assert outcome.sold_early is not None
    assert outcome.sold_early.units == UNITS
    assert outcome.sold_early.clean_per_unit.amount == pytest.approx(CLEAN_SELL, abs=TOLERANCE)
    assert outcome.sold_early.accrued_per_unit.amount == pytest.approx(
        ACCRUED_AT_SALE, abs=TOLERANCE
    )
    assert outcome.sold_early.price_per_unit.amount == pytest.approx(SALE_PRICE, abs=TOLERANCE)
    assert outcome.sold_early.proceeds.amount == pytest.approx(UNITS * SALE_PRICE, abs=TOLERANCE)
    assert outcome.undeployed is not None
    deployed = outcome.outlay.amount - outcome.undeployed.amount.amount
    assert deployed == pytest.approx(UNITS * PURCHASE_PRICE, abs=TOLERANCE)
    assert outcome.reaches.amount == pytest.approx(
        UNITS * SALE_PRICE + UNITS * COUPON, abs=TOLERANCE
    )
    # The gain, and the identity it reduces to: 29 days of the issue's own accrual, less the
    # round-trip spread, on every one of the 45 units.
    assert outcome.reaches.amount - deployed == pytest.approx(
        UNITS * (COUPON * DAYS_HELD / PERIOD_DAYS - SPREAD), abs=TOLERANCE
    )


def test_a_longer_hold_returns_more_than_a_shorter_one() -> None:
    """SC-002. The defect this feature closes made the one-month and three-month holds reach
    **exactly** the same amount, because no accrual was carried and one coupon fell in both.

    The twelve-month section is a different case and is asserted as one: UA4000236228 matures
    2027-03-10, inside that horizon, so it is held to its own terms and strikes no sale.
    """
    one_month, three_months, twelve_months = (_worked(index) for index in (0, 1, 2))
    assert one_month.sold_early is not None
    assert three_months.sold_early is not None
    assert three_months.sold_early.on > one_month.sold_early.on
    assert three_months.reaches.amount > one_month.reaches.amount
    assert twelve_months.sold_early is None
    assert twelve_months.reaches.amount > three_months.reaches.amount
    # The two clean prices are the same figure: what grew is the accrual, not the belief.
    assert three_months.sold_early.clean_per_unit == one_month.sold_early.clean_per_unit
    assert three_months.sold_early.accrued_per_unit.amount > (
        one_month.sold_early.accrued_per_unit.amount
    )


def test_the_carried_price_keeps_the_marks_of_the_quote_and_of_every_coupon_it_used() -> None:
    """Principle I and FR-023: the struck price is an unverified quotation less one declared
    accrual and plus another, and subtracting one marked figure from another may launder
    neither."""
    quote = _supplied().registries.access[WORKED].resale_price
    assert quote is not None
    outcome = _worked(0)
    assert outcome.sold_early is not None
    behind = outcome.sold_early.price_per_unit.provenance.sources
    assert quote.price.provenance.sources <= behind
    bounding = [
        amount
        for on, amount in _schedule().coupons
        if on in {date(2026, 3, 11), date(2026, 9, 9), date(2027, 3, 10)}
    ]
    assert len(bounding) == 3
    for amount in bounding:
        assert amount.provenance.sources <= behind
    assert not any(source.verified_on for source in behind)


def test_no_early_exit_window_contains_a_repayment_of_principal() -> None:
    """Why every figure in this module is a figure and not a refusal.

    A repayment retires units, so what *a unit* means changes at that date, and a coupon
    declared after one is per original unit while the quotation carried to the sale is per
    remaining unit. `enumerated.events` refuses that combination rather than pricing it, so
    this check is what says the owner's answer is on the other side of that refusal: every real
    issue repays once, at maturity, past his horizons.
    """
    declared = _supplied().registries.instruments
    checked = 0
    inside = []
    for index, section in enumerate(answers.answered(supplied=_supplied()).sections):
        for item in _sold_early(index):
            terms = declared[item.key.instrument_id].terms
            assert isinstance(terms, EnumeratedTerms), item.key.instrument_id
            assert item.sold_early is not None
            checked += 1
            inside += [
                (item.key.instrument_id, payment.on)
                for payment in terms.payments
                if payment.pays is PaymentKind.PRINCIPAL_REPAYMENT
                and section.horizon.start < payment.on <= item.sold_early.on
            ]
    assert checked
    assert not inside, inside
