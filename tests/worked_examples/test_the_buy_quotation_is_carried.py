"""The purchase leg, worked by hand on the issue whose coupon falls between the two dates.

UA4000231195 pays 87.50 per unit on declared dates 2026-02-25, **2026-08-26** and 2027-02-24 --
182 days between each pair, ``act/365``. Inzhur quotes it 2026-08-24 at 1110.24 to buy, and the
owner's window buys on 2026-09-02. A whole coupon detaches in between::

    accrued(2026-08-24) = 87.50 x 180/182 = 86.54   two days short of the coupon
    accrued(2026-09-02) = 87.50 x   7/182 =  3.37   seven days into the NEXT period

    clean               = 1110.24 - 86.54 = 1023.70
    purchase 2026-09-02 = 1023.70 +  3.37 = 1027.07

**83.17 below the quotation**, and the drop is the coupon resetting the accrual rather than a
subtraction standing beside the price. Nothing carried this leg before, and where the window
holds to maturity there is no sale to cancel the error: the purchase was struck at 1110.24 and
the whole overstatement stayed in the figure.

The hand columns are rounded and every assertion below is against the unrounded expression at
the project tolerance.
"""

from __future__ import annotations

import functools
from datetime import date

import pytest

from terezy.core.decision.answer import AnswerInputs, section_evaluated
from terezy.core.errors import InconsistentTerms
from terezy.core.instruments import accrual, registry
from terezy.core.instruments.interface import Assumptions, DateRange, Holding
from terezy.core.ledger.events import EventKind
from terezy.core.primitives import money
from terezy.core.primitives.tolerance import TOLERANCE
from terezy.core.results.tuple import TupleOutcome
from tests import answer_registries as answers

pytestmark = pytest.mark.worked_example

CARRIED = "UA4000231195"

QUOTED_ON = date(2026, 8, 24)
PURCHASED_ON = date(2026, 9, 2)
DETACHES_ON = date(2026, 8, 26)

BUY_QUOTE = 1110.24
COUPON = 87.50
PERIOD_DAYS = 182

ACCRUED_AT_QUOTATION = COUPON * 180 / PERIOD_DAYS
ACCRUED_AT_PURCHASE = COUPON * 7 / PERIOD_DAYS
CLEAN = BUY_QUOTE - ACCRUED_AT_QUOTATION
PURCHASE_PRICE = CLEAN + ACCRUED_AT_PURCHASE


@functools.cache
def _supplied() -> AnswerInputs:
    return answers.shipped_inputs()


def _schedule() -> accrual.Schedule:
    declared = _supplied().registries.instruments[CARRIED]
    ops = registry.ops_for(declared.instrument_class)
    return accrual.schedule_of(declared, ops.coupons_per_unit(declared))


def _outcome(horizon_index: int) -> TupleOutcome:
    section = answers.answered(supplied=_supplied()).sections[horizon_index]
    return next(item for item in section_evaluated(section) if item.key.instrument_id == CARRIED)


def test_the_declared_dates_are_the_ones_the_arithmetic_above_assumes() -> None:
    """The coupon between the quotation and the purchase, read off the declaration."""
    dated = dict(_schedule().coupons)
    assert dated[DETACHES_ON].amount == COUPON
    assert (DETACHES_ON - date(2026, 2, 25)).days == PERIOD_DAYS
    assert (date(2027, 2, 24) - DETACHES_ON).days == PERIOD_DAYS
    assert QUOTED_ON < DETACHES_ON < PURCHASED_ON
    quote = _supplied().registries.access[CARRIED].quote
    assert quote is not None
    assert quote.price.amount == BUY_QUOTE
    assert quote.observed_on == QUOTED_ON


def test_the_purchase_is_struck_at_the_clean_price_plus_the_new_periods_accrual() -> None:
    """US2 scenario 1: below the declared quotation, by the coupon that left in between."""
    quote = _supplied().registries.access[CARRIED].quote
    assert quote is not None
    carried = accrual.carried_to(
        _schedule(),
        quote=quote.price,
        observed_on=QUOTED_ON,
        on=PURCHASED_ON,
        quoted_term="access.price.observed_on",
        dated_term="holding.purchased_on",
    )
    assert not isinstance(carried, InconsistentTerms), carried
    assert carried.clean.amount == pytest.approx(CLEAN, abs=TOLERANCE)
    assert carried.accrued.amount == pytest.approx(ACCRUED_AT_PURCHASE, abs=TOLERANCE)
    price = accrual.price(carried).amount
    assert price == pytest.approx(PURCHASE_PRICE, abs=TOLERANCE)
    assert price < BUY_QUOTE


def test_the_engine_bought_at_that_price_over_the_owners_twelve_months() -> None:
    """The same figure, read off the owner's own answer rather than recomputed beside it."""
    outcome = _outcome(2)
    assert outcome.undeployed is not None
    deployed = outcome.outlay.amount - outcome.undeployed.amount.amount
    units = deployed / PURCHASE_PRICE
    assert units == pytest.approx(round(units), abs=TOLERANCE)
    assert deployed == pytest.approx(round(units) * PURCHASE_PRICE, abs=TOLERANCE)


def test_a_candidate_held_to_maturity_reads_no_resale_quotation() -> None:
    """US2 scenario 2, asserted against the event stream rather than against a price.

    UA4000231195 matures 2027-08-25, a week inside the owner's twelve-month horizon, so that
    section holds it to its own terms. What the stream contains is the declared payments and no
    ``REDEMPTION``: nothing struck a quotation, so nothing leaned on the belief for its exit --
    while the **purchase** leaned on it all the same, which is what this module is about.
    """
    quote = _supplied().registries.access[CARRIED].quote
    assert quote is not None
    section = answers.answered(supplied=_supplied()).sections[2]
    assert section.horizon.end == date(2027, 9, 1)
    outcome = _outcome(2)
    assert outcome.sold_early is None
    assert _outcome(0).sold_early is not None

    declared = _supplied().registries.instruments[CARRIED]
    events = registry.ops_for(declared.instrument_class).events(
        declared,
        Holding(
            owner_id="owner-001",
            instrument_id=CARRIED,
            quantity=1.0,
            purchased_on=PURCHASED_ON,
            cost=money.scale(quote.price, 1.0),
        ),
        DateRange(start=section.horizon.start, end=section.horizon.end),
        Assumptions(consumption_method="fifo", coupon_policy="hold_cash"),
        None,
    )
    assert isinstance(events, tuple), events
    assert not [event for event in events if event.kind is EventKind.REDEMPTION]
    paid = {event.occurred_on for event in events if event.kind is not EventKind.PURCHASE}
    assert paid == {date(2027, 2, 24), date(2027, 8, 25)}


def test_the_belief_is_named_even_where_no_quotation_closed_the_position() -> None:
    """FR-018: the purchase was carried across nine days, so the figure rests on the belief --
    and the belief is therefore not the early exit's, because this candidate has none."""
    outcome = _outcome(2)
    assert outcome.sold_early is None
    belief = _supplied().registries.quotation_holds.id
    assert [claim for claim in outcome.rests_on if belief in claim]
