"""Day-count fractions, worked out by hand, with the arithmetic checked in beside each.

Constitution Principle V: every financial rule lands with a hand-computed worked example
*checked into the repository alongside its arithmetic, so a human can verify the engine
rather than trust it*. That is why each case below shows the day count it depends on as
a division of two integers a reader can confirm on a calendar, rather than a decimal
literal copied out of a previous run. A decimal literal proves only that the code still
does what it did last time; ``181 / 365`` proves the convention.

Part of FR-021. The *choice* of convention is data, declared per issue; the *algorithm*
is code, and these are the three algorithms feature 001 implements. Every comparison
goes through the single project tolerance (FR-002); none is written here.

**Which definitions these are**, since "act/act" and "30/360" each name a small family:

* ``act/365`` -- actual days divided by a fixed 365, ignoring leap years entirely. A
  period spanning 29 February therefore exceeds 1.0 for a calendar year, and that is
  correct for this convention rather than a bug (case 2 below asserts it deliberately).
* ``act/act`` -- ACT/ACT (ISDA): the period is split at each 1 January and each part is
  divided by the length of *its own* year, 366 in a leap year and 365 otherwise.
* ``30/360`` -- the US "bond basis" variant: every month is 30 days and every year 360,
  with the end-of-month rule that a 31st becomes a 30th when the start day is already
  the 30th or 31st.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.primitives import conventions
from terezy.core.primitives.tolerance import is_close

pytestmark = pytest.mark.worked_example


class TestActual365:
    """``act/365``: actual elapsed days over a fixed 365-day year."""

    def test_a_semiannual_period_in_a_common_year(self) -> None:
        # 2025-01-15 -> 2025-07-15, counted month by month:
        #   Jan 15 -> Feb 15 = 31   (January has 31 days)
        #   Feb 15 -> Mar 15 = 28   (2025 is not a leap year)
        #   Mar 15 -> Apr 15 = 31
        #   Apr 15 -> May 15 = 30
        #   May 15 -> Jun 15 = 31
        #   Jun 15 -> Jul 15 = 30
        #   total            = 31 + 28 + 31 + 30 + 31 + 30 = 181 days
        #   so the fraction is 181 / 365
        fraction = conventions.day_count("act/365")(date(2025, 1, 15), date(2025, 7, 15))
        assert is_close(fraction, 181 / 365)

    def test_a_leap_year_exceeds_one_because_the_denominator_is_fixed(self) -> None:
        # 2024-01-01 -> 2025-01-01 spans all of 2024, which is a leap year: 366 days.
        # The denominator is fixed at 365 regardless, so
        # fraction = 366 / 365 = 1.00273972...
        # This is the defining behaviour of act/365, not a rounding artefact: a bond on
        # this convention accrues slightly more than a year's coupon over a leap year.
        fraction = conventions.day_count("act/365")(date(2024, 1, 1), date(2025, 1, 1))
        assert is_close(fraction, 366 / 365)
        assert fraction > 1.0

    def test_a_zero_length_period_accrues_nothing(self) -> None:
        # 0 days / 365 = 0.0 exactly. A holding bought and measured on the same day has
        # accrued nothing -- not a small positive amount, and not an error.
        fraction = conventions.day_count("act/365")(date(2025, 3, 10), date(2025, 3, 10))
        assert fraction == 0.0


class TestActualActual:
    """``act/act`` (ISDA): each calendar year contributes over its own length."""

    def test_a_period_straddling_a_year_boundary_splits_at_1_january(self) -> None:
        # 2024-12-01 -> 2025-03-01 splits into two parts at 2025-01-01:
        #   2024 part: 2024-12-01 -> 2025-01-01 = 31 days, and 2024 is a leap
        #              year, so its denominator is 366  ->  31 / 366
        #   2025 part: 2025-01-01 -> 2025-03-01 = 31 (Jan) + 28 (Feb) = 59 days,
        #              and 2025 is a common year  ->  59 / 365
        # fraction = 31/366 + 59/365 = 0.08469945... + 0.16164383... = 0.24634328...
        fraction = conventions.day_count("act/act")(date(2024, 12, 1), date(2025, 3, 1))
        assert is_close(fraction, 31 / 366 + 59 / 365)

    def test_a_whole_leap_year_is_exactly_one(self) -> None:
        # 2024-01-01 -> 2025-01-01 = 366 days, all of them inside leap year 2024,
        # so fraction = 366 / 366 = 1.0 exactly. This is the difference from act/365,
        # which gives 366/365 for the same dates.
        fraction = conventions.day_count("act/act")(date(2024, 1, 1), date(2025, 1, 1))
        assert is_close(fraction, 1.0)
        assert is_close(
            conventions.day_count("act/365")(date(2024, 1, 1), date(2025, 1, 1)),
            366 / 365,
        )

    def test_a_whole_common_year_is_also_exactly_one(self) -> None:
        # 2025-01-01 -> 2026-01-01 = 365 days over a 365-day denominator = 1.0.
        # Both a leap and a common calendar year come to exactly 1.0, which is the
        # property act/act exists to provide.
        fraction = conventions.day_count("act/act")(date(2025, 1, 1), date(2026, 1, 1))
        assert is_close(fraction, 1.0)

    def test_a_half_year_inside_one_common_year(self) -> None:
        # 2025-07-01 -> 2026-01-01, entirely within 2025 up to the boundary:
        #   Jul 1 -> Aug 1 = 31
        #   Aug 1 -> Sep 1 = 31
        #   Sep 1 -> Oct 1 = 30
        #   Oct 1 -> Nov 1 = 31
        #   Nov 1 -> Dec 1 = 30
        #   Dec 1 -> Jan 1 = 31
        #   total          = 184 days
        # fraction = 184 / 365 = 0.50410958...
        # Note it is not exactly 0.5: a July-to-January half year is longer than a
        # January-to-July one, which is why act/act coupons on this convention are
        # unequal between periods.
        fraction = conventions.day_count("act/act")(date(2025, 7, 1), date(2026, 1, 1))
        assert is_close(fraction, 184 / 365)


class TestThirty360:
    """``30/360`` US bond basis: 30-day months, 360-day years, end-of-month rule."""

    def test_a_semiannual_period_between_month_ends_is_exactly_a_half(self) -> None:
        # 2025-01-31 -> 2025-07-31.
        #   start day 31 -> capped to 30, so d1 = 30
        #   end day 31, and d1 is already 30, so the end-of-month rule gives d2 = 30
        #   360 * (2025 - 2025) = 0
        #    30 * (7 - 1)       = 180
        #        (30 - 30)      = 0
        #   total = 180 days over 360 = 0.5 exactly
        # This exactness is the point of 30/360: coupons are equal between periods,
        # which is what a bond paying a fixed coupon twice a year actually does.
        fraction = conventions.day_count("30/360")(date(2025, 1, 31), date(2025, 7, 31))
        assert fraction == 0.5

    def test_the_end_of_month_rule_does_not_fire_when_the_start_is_not_a_month_end(
        self,
    ) -> None:
        # 2025-02-28 -> 2025-08-31.
        #   start day 28 -> d1 = 28 (below 30, untouched)
        #   end day 31, but d1 is 28, not 30 or 31, so d2 stays 31
        #    30 * (8 - 2) = 180
        #        (31 - 28) =  3
        #   total = 183 days over 360 = 0.50833333...
        # Slightly more than half a year, because February's short month is counted as
        # a full 30 days at the start while August's 31st is counted in full at the end.
        fraction = conventions.day_count("30/360")(date(2025, 2, 28), date(2025, 8, 31))
        assert is_close(fraction, 183 / 360)

    def test_a_whole_year_is_one_regardless_of_leap(self) -> None:
        # 2024-01-15 -> 2025-01-15, spanning leap year 2024:
        #   360 * (2025 - 2024) = 360
        #    30 * (1 - 1)       =   0
        #        (15 - 15)      =   0
        #   total = 360 / 360 = 1.0
        # 29 February is invisible to this convention, by construction.
        fraction = conventions.day_count("30/360")(date(2024, 1, 15), date(2025, 1, 15))
        assert fraction == 1.0

    def test_two_months_from_a_thirtieth_to_a_thirty_first(self) -> None:
        # 2025-01-30 -> 2025-03-31.
        #   start day 30 -> d1 = 30
        #   end day 31, and d1 is 30, so d2 = 30
        #    30 * (3 - 1) = 60
        #        (30 - 30) = 0
        #   total = 60 / 360 = 0.16666666...
        # Two months exactly, even though 59 calendar days elapsed (31 + 28).
        fraction = conventions.day_count("30/360")(date(2025, 1, 30), date(2025, 3, 31))
        assert is_close(fraction, 60 / 360)


class TestTheConventionsDisagree:
    """The three are genuinely different algorithms, not three names for one.

    If a refactor ever made two of them agree everywhere, the per-issue declaration
    required by FR-021 would be decorative. SC-012 rests on them differing.
    """

    def test_the_same_dates_give_three_different_fractions(self) -> None:
        start, end = date(2024, 12, 1), date(2025, 3, 1)
        # act/365: 90 calendar days (31 Dec + 31 Jan + 28 Feb) / 365
        # act/act: 31/366 + 59/365, as worked out above
        # 30/360 : 30 * (3 - 12) + 360 * 1 = 90, so 90/360
        by_name = {
            name: conventions.day_count(name)(start, end)
            for name in ("act/365", "act/act", "30/360")
        }
        assert is_close(by_name["act/365"], 90 / 365)
        assert is_close(by_name["act/act"], 31 / 366 + 59 / 365)
        assert is_close(by_name["30/360"], 90 / 360)
        assert len(set(by_name.values())) == 3


class TestAReversedPeriodIsRejected:
    """An end before a start is a programmer error, so it raises rather than returning.

    A negative fraction would flow into a coupon amount and produce a negative payment,
    which is the silent-nonsense outcome Principle IV's "failure is explicit" clause
    forbids. Inconsistent *declared* dates are a different thing: those are caught
    earlier and reported as ``InconsistentTerms`` (FR-018), a typed value the owner
    sees. By the time dates reach a day-count function they have been validated, so
    reaching here reversed means the caller has a bug.
    """

    @pytest.mark.parametrize("name", ["act/365", "act/act", "30/360"])
    def test_reversed_dates_raise(self, name: str) -> None:
        with pytest.raises(ValueError, match="2025-07-15"):
            conventions.day_count(name)(date(2025, 7, 15), date(2025, 1, 15))
