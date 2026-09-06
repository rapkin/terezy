"""The owner's own question, one month, UA4000238968: the change from the purchase comes home.

Owner decision of 2026-09-06
(``specs/decisions/2026-09-06-undeployed-remainder-returns.toml``). What he saw was a card
reading *49 776.69 back* against the 50 000.00 he asked about, and what he said is that the
money the purchase could not deploy can be withdrawn from the broker without a fee and without
a tax. It can, so it is: the remainder rides this tuple's own declared way out.

UA4000238968 pays 87.40 per unit on declared dates 2026-03-11, 2026-09-09 and 2027-03-10 --
182 days between each pair -- and declares ``day_count = "act/365"``. Inzhur quotes it on
2026-08-24 at 1113.04, and its sell quotation is the same 1113.04: the spread is zero, which is
what makes the whole answer below reduce to accrual. The horizon opens 2026-09-01,
``inzhur_direct`` declares one day, so the purchase settles 2026-09-02 and the sale is struck
at the window's end on 2026-10-01.

A quotation is a **dirty** price, so the interest accrued by the day it was read comes out and
the interest accrued by the day it is used goes back in::

    accrued(2026-08-24) = 87.40 x 166/182 =   79.72      166 days into [03-11, 09-09)
    accrued(2026-09-02) = 87.40 x 175/182 =   84.04      175 days into the same period
    accrued(2026-10-01) = 87.40 x  22/182 =   10.56       22 days into [09-09, 03-10)

    clean         = 1113.04 - 79.72 = 1033.32     buy and sell alike: the spread is zero
    purchase      = 1033.32 + 84.04 = 1117.36
    sale          = 1033.32 + 10.56 = 1043.89

**The purchase, and what it could not deploy**::

    units       floor(50 000 / 1117.36)  =  44
    deployed    44 x 1117.36             =  49 163.93
    remainder   50 000 - 49 163.93       =     836.07   at `inzhur`

**The remainder's own journey.** It never became a position, so it leaves on the purchase date
and waits for nothing; `inzhur_to_monobank` charges nothing and declares three days; nothing was
disposed of, so no tax touches it::

    leaves 2026-09-02   ->   836.07   arrives 2026-09-05

**What comes home, in date order**::

    2026-09-05      836.07                         the remainder
    2026-09-12    3 845.60   = 44 x 87.40          the coupon of 2026-09-09
    2026-10-04   45 931.09   = 44 x 1 043.89       the sale of 2026-10-01
                 ----------
    reaches      50 612.76

**The identity a reader can check with no decimals at all.** The clean price cancels between
the two legs and the spread is zero, so per unit the whole month is 29 days of the issue's own
accrual::

    sale + coupon - purchase  =  87.40 x 29/182  =  13.9263...

On 44 units that is 612.76, and 50 000.00 + 612.76 is exactly the 50 612.76 above. **That
identity is the point**: the gain is readable against the amount he asked about, with no
intermediate figure between the two.
"""

from __future__ import annotations

import functools
from datetime import date, timedelta

import pytest

from terezy.core.decision.answer import AnswerInputs, section_evaluated
from terezy.core.primitives.tolerance import TOLERANCE
from terezy.core.results.tuple import RemainderCameHome, TupleOutcome
from tests import answer_registries as answers

pytestmark = pytest.mark.worked_example

WORKED = "UA4000238968"

ASKED = 50_000.0
QUOTE = 1113.04
COUPON = 87.40
PERIOD_DAYS = 182

QUOTED_ON = date(2026, 8, 24)
PURCHASED_ON = date(2026, 9, 2)
SOLD_ON = date(2026, 10, 1)
COUPON_ON = date(2026, 9, 9)
EXIT_LATENCY_DAYS = 3
"""What `inzhur_to_monobank` declares, and it applies to the remainder like anything else."""

CLEAN = QUOTE - COUPON * 166 / PERIOD_DAYS
PURCHASE_PRICE = CLEAN + COUPON * 175 / PERIOD_DAYS
SALE_PRICE = CLEAN + COUPON * 22 / PERIOD_DAYS

UNITS = 44.0
"""45 x 1117.36 is 50 281, which exceeds the 50 000 he asked about, so 44 whole units is what
the declared minimum increment allows."""

DAYS_HELD = 29
"""2026-09-02 to 2026-10-01."""


@functools.cache
def _outcome() -> TupleOutcome:
    """His own answer over what ships, at his shortest horizon. No fixture is overlaid."""
    supplied: AnswerInputs = answers.shipped_inputs()
    section = answers.answered(supplied=supplied).sections[0]
    return next(item for item in section_evaluated(section) if item.key.instrument_id == WORKED)


def _remainder() -> RemainderCameHome:
    undeployed = _outcome().undeployed
    assert undeployed is not None
    assert isinstance(undeployed.journey, RemainderCameHome), undeployed.journey
    return undeployed.journey


def test_the_purchase_leaves_eight_hundred_and_thirty_six_at_the_broker() -> None:
    """44 units at 1117.36 is 49 163.93 of the 50 000.00 he asked about."""
    outcome = _outcome()
    undeployed = outcome.undeployed
    assert undeployed is not None
    assert outcome.outlay.amount == pytest.approx(ASKED, abs=TOLERANCE)
    assert outcome.sold_early is not None
    assert outcome.sold_early.units == UNITS
    assert outcome.sold_early.price_per_unit.amount == pytest.approx(SALE_PRICE, abs=TOLERANCE)
    deployed = outcome.outlay.amount - undeployed.amount.amount
    assert deployed == pytest.approx(UNITS * PURCHASE_PRICE, abs=TOLERANCE)
    assert undeployed.amount.amount == pytest.approx(ASKED - UNITS * PURCHASE_PRICE, abs=TOLERANCE)
    assert undeployed.amount.amount == pytest.approx(836.07, abs=0.005)
    assert undeployed.venue_id == "inzhur"


def test_it_leaves_on_the_purchase_date_and_is_home_three_days_later_whole() -> None:
    """The way out charges nothing and no tax touches it: nothing was disposed of."""
    journey = _remainder()
    undeployed = _outcome().undeployed
    assert undeployed is not None
    assert journey.left_on == PURCHASED_ON
    assert journey.arrived_on == PURCHASED_ON + timedelta(days=EXIT_LATENCY_DAYS)
    assert journey.reached.amount == pytest.approx(undeployed.amount.amount, abs=TOLERANCE)
    assert journey.arrived_on < COUPON_ON, "it is home before the holding has paid anything"


def test_fifty_thousand_six_hundred_and_twelve_reaches_a_spendable_endpoint() -> None:
    """The coupon, the sale, and the remainder: three dated amounts and one total."""
    outcome = _outcome()
    coupon, sale = (UNITS * COUPON, UNITS * SALE_PRICE)
    assert [arrival.released_on for arrival in outcome.arrivals] == [COUPON_ON, SOLD_ON]
    assert [arrival.amount.amount for arrival in outcome.arrivals] == [
        pytest.approx(coupon, abs=TOLERANCE),
        pytest.approx(sale, abs=TOLERANCE),
    ]
    assert outcome.reaches.amount == pytest.approx(
        coupon + sale + _remainder().reached.amount, abs=TOLERANCE
    )
    assert outcome.reaches.amount == pytest.approx(50_612.76, abs=0.005)


def test_the_gain_is_twenty_nine_days_of_the_issues_own_accrual_on_the_whole_amount() -> None:
    """The identity in this module's docstring, and the point of the decision.

    ``reaches - outlay`` is now the answer to the question he asked -- *what do I get back on
    50 000* -- with no intermediate figure between them. It reduces to 29 days of accrual
    because the buy and sell quotations of this issue are the same number, so the round trip
    gives up no spread at all.
    """
    outcome = _outcome()
    assert outcome.reaches.amount - outcome.outlay.amount == pytest.approx(
        UNITS * COUPON * DAYS_HELD / PERIOD_DAYS, abs=TOLERANCE
    )
    assert outcome.reaches.amount > outcome.outlay.amount, (
        "and it is a gain, not the loss the card read as before the remainder came home"
    )


def test_the_remainders_arrival_is_inside_the_span_the_rate_is_measured_over() -> None:
    """FR-015: waiting is a cost, and the remainder waits three days like anything else.

    The span still ends on the sale's arrival here, because the remainder is home first -- so
    this is the weaker of the two claims and the one that holds for every candidate.
    """
    outcome = _outcome()
    assert outcome.span.start <= _remainder().arrived_on <= outcome.span.end
    assert outcome.span.end == SOLD_ON + timedelta(days=EXIT_LATENCY_DAYS)
