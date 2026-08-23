"""Calendar months as ``YYYY-MM``, and the inclusive window a deflation runs over.

The arithmetic under every coverage check in feature 007. It is small enough to look
obvious and is tested anyway, because two of its edges are the ones a deflation gets
wrong in silence: **December rolls to January of the next year**, and a window whose
first month is after its last contains *nothing* rather than everything.

The second is the one that matters. ``months_in`` is what ``coverage`` iterates, so a
reversed window that enumerated a month would send a real figure to the Fisher relation
for a span nobody asked about -- the exact failure research.md D4 forbids one level up.
Here it returns an empty tuple, and ``real_terms`` refuses on the emptiness by name.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.primitives import periods
from terezy.core.primitives.periods import Window


def test_a_date_renders_as_its_zero_padded_month() -> None:
    """Zero-padded, because ``2026-1`` sorts before ``2026-10`` and ``2026-01`` does not."""
    assert periods.month_of(date(2026, 1, 15)) == "2026-01"
    assert periods.month_of(date(2026, 10, 1)) == "2026-10"
    assert periods.month_of(date(1991, 8, 31)) == "1991-08"


def test_december_rolls_into_january_of_the_next_year() -> None:
    """The one edge a hand-rolled month increment gets wrong."""
    assert periods.next_month("2025-12") == "2026-01"
    assert periods.next_month("2026-01") == "2026-02"
    assert periods.next_month("2026-09") == "2026-10"


def test_a_window_enumerates_every_month_from_first_to_last_inclusive() -> None:
    assert periods.months_in(Window(first="2026-11", last="2027-02")) == (
        "2026-11",
        "2026-12",
        "2027-01",
        "2027-02",
    )


def test_a_single_month_window_enumerates_that_month() -> None:
    """Inclusive at both ends: one month is a window, not an empty one."""
    assert periods.months_in(Window(first="2026-03", last="2026-03")) == ("2026-03",)
    assert periods.month_count(Window(first="2026-03", last="2026-03")) == 1


def test_a_reversed_window_enumerates_nothing_rather_than_everything() -> None:
    """A window with no elapsed month is empty, and its emptiness is the caller's to report.

    Not a raise: the caller -- ``real_terms`` -- turns it into a typed refusal naming the
    window, because a holding bought and matured in one month is a fact about the money
    rather than a programmer error.
    """
    assert periods.months_in(Window(first="2026-05", last="2026-04")) == ()
    assert periods.month_count(Window(first="2026-05", last="2026-04")) == 0


def test_the_month_count_agrees_with_the_enumeration_across_a_year_boundary() -> None:
    """Two ways of answering one question, held to agreeing.

    ``month_count`` is arithmetic and ``months_in`` is a walk; the annualisation divides by
    the first and the product multiplies over the second, so a disagreement between them
    would be an off-by-one inside a real rate.
    """
    window = Window(first="2025-11", last="2028-01")
    assert periods.month_count(window) == len(periods.months_in(window))
    assert periods.month_count(window) == 27


def test_a_period_is_recognised_only_in_the_declared_shape() -> None:
    assert periods.is_period("2026-01")
    assert periods.is_period("1991-08")
    for malformed in ("2026-1", "2026-13", "2026-00", "26-01", "2026/01", "2026", "", "x"):
        assert not periods.is_period(malformed), malformed


def test_a_malformed_period_reaching_the_arithmetic_is_a_programmer_error() -> None:
    """The data layer checks the shape and can name the file; here it is a bypass.

    Same reading as ``staleness.kind_for`` and ``regimes._checked``: a value that failed
    validation cannot have arrived honestly, so the honest answer is a raise rather than a
    guess at what ``"2026-13"`` was supposed to mean.
    """
    with pytest.raises(ValueError, match="2026-13"):
        periods.next_month("2026-13")
    with pytest.raises(ValueError, match="not-a-month"):
        periods.months_in(Window(first="not-a-month", last="2026-01"))


def test_a_window_is_frozen_and_compares_by_value() -> None:
    """It travels on a ``RealRate`` and is compared in the golden; both need value equality."""
    assert Window(first="2026-01", last="2026-02") == Window(first="2026-01", last="2026-02")
    assert Window(first="2026-01", last="2026-02") != Window(first="2026-01", last="2026-03")
