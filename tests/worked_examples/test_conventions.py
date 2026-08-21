"""Coupon dates and business-day adjustment, worked out by hand.

The companion to ``test_day_count.py``: those three algorithms say how much accrues
between two dates, and these two say *which* dates. Together they are the whole of
FR-021, which requires periodicity, day count and the non-business-day rule to be
declared per issue and forbids the engine from fixing any of them.

Each expected coupon date below is written out as a calendar date a reader can check,
not derived by re-running the generator with different arguments.

**A stated limitation, so no reader assumes more than is here.** The business-day rules
know about weekends and nothing else. Ukrainian public holidays are not modelled, and a
holiday calendar is declared domain knowledge that belongs in ``data/`` with a citation
and a verification date -- not invented in code from memory (constitution, Principle I:
no legal or calendar value may originate from an implementer's memory). Until that data
exists, a coupon falling on a public holiday will be placed on the holiday. That is
visible and wrong in a stated way, which is preferable to being invisibly wrong from an
uncited hard-coded list.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.primitives import conventions

pytestmark = pytest.mark.worked_example


class TestCouponDates:
    """Periodicity generates the dated coupons of a period, anchored on maturity.

    Anchored on the **end** date, stepping backwards, because that is what a bond
    actually does: the final coupon is paid with the principal on the maturity date, and
    earlier coupons are counted back from it. Anchoring on the issue date instead would
    leave a short irregular final period, and would put the last coupon somewhere other
    than maturity.
    """

    def test_semiannual_over_two_years(self) -> None:
        # Issued 2025-01-15, maturing 2027-01-15, coupons every 6 months.
        # Counting back from maturity in six-month steps:
        #   2027-01-15, 2026-07-15, 2026-01-15, 2025-07-15, and then 2025-01-15
        #   which is the issue date itself and therefore not a coupon.
        # Four coupons, ascending.
        dates = conventions.periodicity("semiannual")(date(2025, 1, 15), date(2027, 1, 15))
        assert dates == (
            date(2025, 7, 15),
            date(2026, 1, 15),
            date(2026, 7, 15),
            date(2027, 1, 15),
        )

    def test_annual_over_three_years(self) -> None:
        # Issued 2025-03-01, maturing 2028-03-01: 2026-03-01, 2027-03-01, 2028-03-01.
        dates = conventions.periodicity("annual")(date(2025, 3, 1), date(2028, 3, 1))
        assert dates == (date(2026, 3, 1), date(2027, 3, 1), date(2028, 3, 1))

    def test_quarterly_over_one_year(self) -> None:
        # Issued 2025-01-31, maturing 2026-01-31, every 3 months. Counting back:
        #   2026-01-31, 2025-10-31, 2025-07-31, 2025-04-30 (April has 30 days, so the
        #   31st is clamped to the last day of the month), and 2025-01-31 = issue.
        # The clamp applies to each step measured from the anchor, so 2025-10-31 is a
        # 31st again rather than drifting to the 30th once April has shortened it.
        dates = conventions.periodicity("quarterly")(date(2025, 1, 31), date(2026, 1, 31))
        assert dates == (
            date(2025, 4, 30),
            date(2025, 7, 31),
            date(2025, 10, 31),
            date(2026, 1, 31),
        )

    def test_the_final_coupon_always_lands_on_maturity(self) -> None:
        # Whatever the periodicity, the last generated date is the maturity date --
        # the property that makes the schedule end with principal and coupon together.
        for name in ("annual", "semiannual", "quarterly"):
            dates = conventions.periodicity(name)(date(2025, 2, 28), date(2029, 2, 28))
            assert dates[-1] == date(2029, 2, 28)

    def test_an_irregular_first_period_is_short_not_dropped(self) -> None:
        # Issued 2025-04-01, maturing 2027-01-15, semiannual. Counting back from
        # maturity: 2027-01-15, 2026-07-15, 2026-01-15, 2025-07-15, then 2025-01-15
        # which is before the issue date and so is not generated. The first period is
        # therefore short (2025-04-01 to 2025-07-15) rather than a coupon being lost.
        # The day-count fraction, not the step, is what makes that coupon smaller.
        dates = conventions.periodicity("semiannual")(date(2025, 4, 1), date(2027, 1, 15))
        assert dates == (
            date(2025, 7, 15),
            date(2026, 1, 15),
            date(2026, 7, 15),
            date(2027, 1, 15),
        )

    def test_a_zero_length_life_has_no_coupons(self) -> None:
        assert conventions.periodicity("annual")(date(2025, 1, 1), date(2025, 1, 1)) == ()

    def test_a_reversed_life_raises(self) -> None:
        with pytest.raises(ValueError, match="2027-01-15"):
            conventions.periodicity("semiannual")(date(2027, 1, 15), date(2025, 1, 15))

    def test_the_three_periodicities_produce_different_counts(self) -> None:
        # One year from 2025-01-01 to 2026-01-01: 1, 2 and 4 coupons respectively.
        # SC-012 rests on two issues with different periodicities producing different
        # schedules, so the three must genuinely differ.
        start, end = date(2025, 1, 1), date(2026, 1, 1)
        assert len(conventions.periodicity("annual")(start, end)) == 1
        assert len(conventions.periodicity("semiannual")(start, end)) == 2
        assert len(conventions.periodicity("quarterly")(start, end)) == 4


class TestBusinessDayRules:
    """The rule that moves a coupon date off a weekend, or declines to.

    2025-05-31 is a Saturday and 2025-06-01 a Sunday; 2025-05-30 is a Friday and
    2025-06-02 a Monday. Those four dates are enough to separate all three rules.
    """

    def test_none_leaves_the_date_alone(self) -> None:
        # An issue may legitimately declare that its coupon dates are unadjusted.
        # "none" is a declared choice, not a fallback: FR-021 forbids the engine
        # silently picking a convention, and this is how an issue says "do not adjust".
        assert conventions.business_day_rule("none")(date(2025, 5, 31)) == date(2025, 5, 31)
        assert conventions.business_day_rule("none")(date(2025, 6, 1)) == date(2025, 6, 1)

    def test_following_rolls_a_weekend_forward_to_monday(self) -> None:
        # Saturday 2025-05-31 -> Sunday 2025-06-01 -> Monday 2025-06-02.
        assert conventions.business_day_rule("following")(date(2025, 5, 31)) == date(2025, 6, 2)
        # Sunday 2025-06-01 -> Monday 2025-06-02.
        assert conventions.business_day_rule("following")(date(2025, 6, 1)) == date(2025, 6, 2)

    def test_following_leaves_a_weekday_alone(self) -> None:
        # Friday 2025-05-30 is already a business day.
        assert conventions.business_day_rule("following")(date(2025, 5, 30)) == date(2025, 5, 30)

    def test_modified_following_rolls_back_rather_than_into_the_next_month(self) -> None:
        # Saturday 2025-05-31: rolling forward reaches Monday 2025-06-02, which is in
        # June. "Modified" means the adjustment may not cross a month boundary, so the
        # date rolls backwards instead, to Friday 2025-05-30.
        # This matters for a bond because it keeps the coupon inside its accrual month,
        # which is what the accrual period was measured against.
        adjusted = conventions.business_day_rule("modified_following")(date(2025, 5, 31))
        assert adjusted == date(2025, 5, 30)

    def test_modified_following_behaves_like_following_inside_a_month(self) -> None:
        # Saturday 2025-05-10 -> Monday 2025-05-12, still in May, so no roll back.
        adjusted = conventions.business_day_rule("modified_following")(date(2025, 5, 10))
        assert adjusted == date(2025, 5, 12)
        assert adjusted == conventions.business_day_rule("following")(date(2025, 5, 10))

    def test_the_reference_dates_really_are_the_weekdays_claimed(self) -> None:
        """Guard the premises of the cases above, so a mis-stated date cannot mislead.

        Monday is 0. If one of these ever fails, the expectations above are being read
        against the wrong calendar and every assertion in this class is suspect.
        """
        assert date(2025, 5, 30).weekday() == 4
        assert date(2025, 5, 31).weekday() == 5
        assert date(2025, 6, 1).weekday() == 6
        assert date(2025, 6, 2).weekday() == 0
        assert date(2025, 5, 10).weekday() == 5
