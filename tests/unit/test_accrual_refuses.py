"""What the accrual refuses to price, and the one absence it treats as a figure.

Three cases, and the difference between the first two and the third is the whole of FR-008 and
FR-009:

* a date **before** the first declared coupon date has no period start, and ``covers_from``, an
  issue date and a placement date are all coverage claims rather than declared accrual starts
  (FR-001) -- so the figure refuses by name rather than accruing a full coupon over a stub;
* a date **on or after** the last declared coupon date has no period end, so the coupon that
  would size the accrual does not exist;
* a schedule declaring **no coupon at all** accrues zero on every date. That is a legitimate
  zero, not an absence: a zero-coupon bond earns its return in the price, and refusing here
  would refuse a correct figure -- the mirror of a silent default.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from terezy.core.errors import InconsistentTerms
from terezy.core.instruments import accrual
from terezy.core.instruments.interface import InstrumentDeclaration
from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import TOLERANCE
from tests import answer_registries as answers

UAH = Currency.UAH

DECLARED = prov.of(
    (
        prov.SourceRef(
            id="tests.unit.test_accrual_refuses",
            citation="a schedule declared by this module",
            retrieved_on=date(2026, 9, 5),
            verified_on=None,
        ),
    )
)

FIRST = date(2026, 3, 11)
SECOND = date(2026, 9, 9)
THIRD = date(2027, 3, 10)

COUPONS = (
    (FIRST, Money(85.50, UAH, DECLARED)),
    (SECOND, Money(85.50, UAH, DECLARED)),
    (THIRD, Money(85.50, UAH, DECLARED)),
)

SCHEDULE = accrual.Schedule(
    instrument_id="UA-FIXTURE",
    coupons=COUPONS,
    day_count="act/365",
    declared_by="instrument.schedule.payment",
)


def _declaration() -> InstrumentDeclaration:
    """The one declaration in this module, and it is enumerated: `schedule_of` prepends an
    accrual opening only for a form that declares an issue date, and this module is about the
    boundaries a payment list states."""
    return next(
        declared
        for declared in answers.shipped_inputs().registries.instruments.values()
        if declared.id == "UA4000236228"
    )


def _accrued(on: date, schedule: accrual.Schedule = SCHEDULE) -> Money | InconsistentTerms:
    return accrual.accrued_on(schedule, on=on, currency=UAH, dated_term="holding.purchased_on")


def test_a_date_before_the_first_declared_coupon_refuses_by_name() -> None:
    """And names the date, the instrument and the coupon dates it falls outside."""
    refusal = _accrued(FIRST - timedelta(days=1))
    assert isinstance(refusal, InconsistentTerms)
    assert refusal.first_term == "holding.purchased_on"
    assert refusal.second_term == "instrument.schedule.payment"
    assert "2026-03-10" in refusal.reason
    assert "UA-FIXTURE" in refusal.reason
    assert FIRST.isoformat() in refusal.reason
    assert THIRD.isoformat() in refusal.reason


def test_a_date_on_or_after_the_last_declared_coupon_refuses() -> None:
    """The interval is half-open at the far end, so the last coupon date opens nothing."""
    for on in (THIRD, THIRD + timedelta(days=1)):
        refusal = _accrued(on)
        assert isinstance(refusal, InconsistentTerms), on
        assert on.isoformat() in refusal.reason


def test_one_declared_coupon_date_bounds_no_period_at_all() -> None:
    """A period needs two consecutive coupon dates. One is a payment, not an interval."""
    lone = accrual.Schedule(
        instrument_id="UA-FIXTURE",
        coupons=((FIRST, Money(85.50, UAH, DECLARED)),),
        day_count="act/365",
        declared_by="instrument.schedule.payment",
    )
    refusal = _accrued(FIRST, lone)
    assert isinstance(refusal, InconsistentTerms)
    assert refusal.reason.count(FIRST.isoformat()) >= 2


def test_a_schedule_declaring_no_coupon_accrues_zero_and_refuses_nothing() -> None:
    """FR-009: a legitimate zero. The price is the quotation, carried unchanged."""
    none = accrual.Schedule(
        instrument_id="UA-ZERO",
        coupons=(),
        day_count="act/365",
        declared_by="instrument.schedule.payment",
    )
    for on in (FIRST, SECOND, THIRD):
        assert _accrued(on, none) == money.zero(UAH)


def test_a_period_of_no_year_fraction_refuses_rather_than_dividing_by_it() -> None:
    """Two coupon dates a 30/360 convention puts zero days apart.

    Reachable rather than defensive: 30/360 caps the start day at 30 and pulls a 31st back to
    it, so 30 and 31 January are the same date to the convention while being different dates to
    the schedule. Dividing by that denominator would put a ``ZeroDivisionError`` in a caller's
    hands in place of a figure, which is the one shape Principle IV forbids outright.
    """
    degenerate = accrual.Schedule(
        instrument_id="UA-FIXTURE",
        coupons=(
            (date(2026, 1, 30), Money(85.50, UAH, DECLARED)),
            (date(2026, 1, 31), Money(85.50, UAH, DECLARED)),
        ),
        day_count="30/360",
        declared_by="instrument.schedule.payment",
    )
    refusal = _accrued(date(2026, 1, 30), degenerate)
    assert isinstance(refusal, InconsistentTerms)
    assert "30/360" in refusal.reason


def test_either_leg_refusing_refuses_the_whole_carry() -> None:
    """A clean price built on half the formula is a number with no arithmetic behind it."""
    quote = Money(1089.32, UAH, DECLARED)
    before = accrual.carried_to(
        SCHEDULE,
        quote=quote,
        observed_on=date(2026, 1, 1),
        on=date(2026, 4, 1),
        quoted_term="access.price.observed_on",
        dated_term="holding.purchased_on",
    )
    assert isinstance(before, InconsistentTerms)
    assert before.first_term == "access.price.observed_on"
    assert "2026-01-01" in before.reason
    after = accrual.carried_to(
        SCHEDULE,
        quote=quote,
        observed_on=date(2026, 4, 1),
        on=date(2027, 4, 1),
        quoted_term="access.price.observed_on",
        dated_term="holding.purchased_on",
    )
    assert isinstance(after, InconsistentTerms)
    assert after.first_term == "holding.purchased_on"
    assert "2027-04-01" in after.reason


@pytest.mark.parametrize("on", [FIRST, SECOND])
def test_a_coupon_date_opens_its_own_period(on: date) -> None:
    """``accrued(c_i) == 0``, and the last one is refused rather than zeroed -- the difference
    between "the coupon just left" and "no period ends here"."""
    figure = _accrued(on)
    assert isinstance(figure, Money)
    assert figure.amount == 0.0


def test_two_coupons_on_one_date_are_one_boundary_carrying_both() -> None:
    """Both leave the price that morning, so the accrual toward them is sized on their sum.

    Reading only the first understates every accrual in the period by the rest -- a wrong
    number with no refusal beside it, which is the shape Principle IV puts at top severity. The
    loader permits the shape: it refuses a *decreasing* payment list, not a repeated date.
    """
    split = accrual.schedule_of(
        _declaration(),
        (
            (FIRST, Money(30.0, UAH, DECLARED)),
            (SECOND, Money(55.50, UAH, DECLARED)),
            (SECOND, Money(30.0, UAH, DECLARED)),
        ),
    )
    assert [when for when, _ in split.coupons] == [FIRST, SECOND]
    on = date(2026, 6, 11)
    both = accrual.accrued_on(split, on=on, currency=UAH, dated_term="holding.purchased_on")
    one = accrual.accrued_on(
        accrual.schedule_of(
            _declaration(),
            ((FIRST, Money(30.0, UAH, DECLARED)), (SECOND, Money(55.50, UAH, DECLARED))),
        ),
        on=on,
        currency=UAH,
        dated_term="holding.purchased_on",
    )
    assert isinstance(both, Money)
    assert isinstance(one, Money)
    # The same elapsed fraction of the same period, sized on 85.50 rather than on 55.50.
    assert both.amount == pytest.approx(one.amount * 85.50 / 55.50, abs=TOLERANCE)
