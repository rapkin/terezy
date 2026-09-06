"""The window a real figure is deflated over, both boundaries pinned by hand (024 FR-005).

One rule for two callers -- a projection's purchase and last contractual flow, a tuple's span
-- so the boundaries cannot drift a month apart between them. The dates below straddle a month
end deliberately: the first month of the window is decided by the *month* the money left and
not by how many days of it were left, which is the off-by-one a hard-wired purchase date
introduced on an outlay made on a month's last day.
"""

from __future__ import annotations

from datetime import date

from terezy.core.inflation.series import deflation_window
from terezy.core.primitives.periods import Window, months_in


def test_money_leaving_on_the_last_day_of_a_month_starts_the_window_the_month_after() -> None:
    """2026-09-30 out, 2027-03-13 back: the window is 2026-10..2027-03, six months.

    September's published index measures September's own price change, and money that left on
    the 30th has already met those prices. Counting 2026-09 would charge the holding for
    inflation it never lived through.
    """
    window = deflation_window(date(2026, 9, 30), date(2027, 3, 13))

    assert window == Window(first="2026-10", last="2027-03")
    assert months_in(window) == (
        "2026-10",
        "2026-11",
        "2026-12",
        "2027-01",
        "2027-02",
        "2027-03",
    )


def test_money_leaving_on_the_first_day_of_a_month_starts_the_same_month_after() -> None:
    """2026-09-01 out, the same 2027-03-13 back: the same six months.

    The pair with the case above, and the whole content of *the month the money left*: one day
    of exposure to September's prices and thirty are the same month, so both windows begin in
    October.
    """
    assert deflation_window(date(2026, 9, 1), date(2027, 3, 13)) == Window(
        first="2026-10", last="2027-03"
    )


def test_the_window_ends_in_the_month_the_last_flow_landed_in() -> None:
    """A flow on the first of a month is that month's, not the previous month's.

    The last boundary is inclusive: money back on 2027-04-01 lived through April's prices for
    a day, and a window ending 2027-03 would deflate by one month less than the span.
    """
    assert deflation_window(date(2026, 9, 30), date(2027, 4, 1)).last == "2027-04"


def test_a_span_inside_one_month_yields_a_window_of_no_elapsed_month() -> None:
    """2026-09-01 out, 2026-09-19 back: first 2026-10 after last 2026-09, so no months.

    Not an error here. The emptiness is what the caller reports by name -- the shipped
    instance is UA4000235865, which pays out eighteen days after the money leaves.
    """
    window = deflation_window(date(2026, 9, 1), date(2026, 9, 19))

    assert window == Window(first="2026-10", last="2026-09")
    assert months_in(window) == ()
