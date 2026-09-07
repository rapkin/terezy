"""A close is taken from the day asked about, and from no neighbouring day (025 FR-011).

Written because the answer-level test could not catch the defect it claimed to: it asks about
a date **after** the series ends, and the bounds check alone refuses that one. The mutation
that matters is a date **inside a gap**, where the search lands on a real row belonging to
another day -- ``bisect_left`` returns the nearest row not before the date, so deleting the
equality check turns every missing day into a plausible price from the wrong one.
"""

from __future__ import annotations

from datetime import date
from typing import Final

import pytest

from terezy.core.instruments.quotations import (
    NoQuotationOnDate,
    Quotation,
    QuotationSeries,
    close_on,
    covered_window,
)
from terezy.core.primitives import provenance as prov

GAP: Final = date(2026, 8, 27)
"""A day the series does not carry, with a row on either side of it."""

DAYS: Final = (date(2026, 8, 25), date(2026, 8, 26), date(2026, 8, 28))
CLOSES: Final = (60_000.0, 61_000.0, 62_000.0)
"""Invented. Distinct, so a price taken from the wrong day is a different number."""


def _series(days: tuple[date, ...] = DAYS) -> QuotationSeries:
    return QuotationSeries(
        symbol="SYNTHUSDT",
        venue_id="binance",
        endpoint="https://example.invalid/klines",
        quotations=tuple(
            Quotation(on_date=day, close=close, provenance=prov.EMPTY)
            for day, close in zip(days, CLOSES, strict=False)
        ),
    )


def test_a_day_the_series_carries_is_the_close_of_that_day() -> None:
    """The control: without it every assertion below would pass on a broken lookup."""
    for day, close in zip(DAYS, CLOSES, strict=True):
        found = close_on(_series(), day)
        assert isinstance(found, Quotation)
        assert found.on_date == day
        assert found.close == close


def test_a_day_inside_a_gap_refuses_rather_than_taking_the_next_row() -> None:
    """The mutation: dropping the equality check returns 2026-08-28's close for 2026-08-27.

    62 000 is a perfectly plausible price for the missing day and nothing downstream could
    tell -- which is why the refusal is asserted by type rather than by the number being wrong.
    """
    found = close_on(_series(), GAP)
    assert isinstance(found, NoQuotationOnDate)
    assert found.on_date == GAP
    assert found.covers == (DAYS[0], DAYS[-1])


def test_a_day_before_the_series_refuses() -> None:
    found = close_on(_series(), date(2026, 8, 24))
    assert isinstance(found, NoQuotationOnDate)


def test_a_day_after_the_series_refuses() -> None:
    """The day of a fetch: the newest closed day is the one before it (FR-024)."""
    found = close_on(_series(), date(2026, 8, 29))
    assert isinstance(found, NoQuotationOnDate)


def test_a_series_with_no_rows_refuses_and_says_it_covers_nothing() -> None:
    """The declared shape of a file no fetch has filled: reported, never an error."""
    empty = _series(days=())
    assert covered_window(empty) is None
    found = close_on(empty, DAYS[0])
    assert isinstance(found, NoQuotationOnDate)
    assert found.covers is None
    assert "no observation at all" in found.reason


@pytest.mark.parametrize("day", [*DAYS, GAP, date(2026, 8, 24), date(2026, 8, 29)])
def test_the_lookup_never_returns_a_row_for_another_day(day: date) -> None:
    """The property the equality check exists for, over every position in the series."""
    found = close_on(_series(), day)
    assert isinstance(found, NoQuotationOnDate) or found.on_date == day
