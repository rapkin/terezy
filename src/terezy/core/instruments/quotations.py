"""A venue's own dated closing quotations, and what one is worth on a day nobody quoted.

025 FR-011. The first declared series this project reads at **run time** that is not a legal
one: a fund's NAV is promoted into an access declaration by a human because there is a
judgement between two readings of one number, and a daily close has no judgement in it -- the
publisher emits one value per day, and promoting it by hand would be transcription.

**A price is taken from the observation dated the run's own ``as_of`` and from nowhere else.**
Not the latest on or before it, not the nearest: crypto trades every calendar day and the
publisher emits a close for every one, so there is no weekend hole to paper over, and
``core.tax.official_rate`` already decided that snapping to a neighbouring date is how a figure
goes wrong on the dates that matter.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from datetime import date

from terezy.core.primitives.provenance import Provenance


@dataclass(frozen=True, slots=True, kw_only=True)
class Quotation:
    """One day's closing price, as the venue published it."""

    on_date: date
    """The day this is the close **of** -- not the day it was read."""

    close: float
    """The published close, **untagged**, and that is the design.

    ``Money`` is currency-tagged and ``Currency`` is a closed enum a quote asset is not in:
    ``BTCUSDT`` closes in a dollar-referenced token, and tagging it ``USD`` here would be the
    silent equality this feature exists to refuse. It becomes money where the owner's declared
    belief says what the token is worth, and nowhere else (025 FR-023).

    Strictly positive, checked at the data boundary.
    """

    provenance: Provenance
    """The citation, one ``SourceRef`` per day, so a figure names the day it rests on rather
    than the file. Its ``verified_on`` is empty and stays empty: a downloaded number is not a
    checked number."""


@dataclass(frozen=True, slots=True, kw_only=True)
class QuotationSeries:
    """Every dated close one fetch wrote for one symbol at one venue."""

    symbol: str
    """As requested of the venue, never split into a base and a quote asset: a kline row
    publishes neither, and choosing where ``BTCUSDT`` divides would be a judgement."""

    venue_id: str
    endpoint: str
    """Where the rows came from, carried so a reader can go and look."""

    quotations: tuple[Quotation, ...]
    """Strictly ascending by date, without duplicates -- checked at the data boundary, where
    the file can be named. Empty is the declared shape of a file no fetch has filled."""


@dataclass(frozen=True, slots=True, kw_only=True)
class NoQuotationOnDate:
    """The series carries no close for this date, so there is no price to report.

    Not a zero, not the previous day's, and not the nearest. The remedy is running the fetch
    script, which is data, and the refusal carries the window so a reader can tell *before the
    series*, *after it* and *inside a gap* apart without opening the file.
    """

    symbol: str
    on_date: date
    covers: tuple[date, date] | None
    """First and last dates declared, or ``None`` for a series with no rows at all."""

    reason: str


def covered_window(series: QuotationSeries) -> tuple[date, date] | None:
    """The first and last dates the series carries, or ``None`` when it carries none."""
    if not series.quotations:
        return None
    return series.quotations[0].on_date, series.quotations[-1].on_date


def close_on(series: QuotationSeries, on_date: date) -> Quotation | NoQuotationOnDate:
    """The close published for ``on_date``, or the typed refusal naming what is missing.

    ``bisect_left`` lands on the first row not before ``on_date``, which is the *nearest* one --
    so the equality below is what refuses to return it. Dropping that check is the
    carry-forward this module forbids, arriving as an off-by-one.
    """
    position = bisect_left(series.quotations, on_date, key=lambda item: item.on_date)
    if position < len(series.quotations) and series.quotations[position].on_date == on_date:
        return series.quotations[position]
    window = covered_window(series)
    return NoQuotationOnDate(
        symbol=series.symbol,
        on_date=on_date,
        covers=window,
        reason=(
            f"{series.symbol} has no published close for {on_date.isoformat()} "
            + (
                f"and the series covers {window[0].isoformat()} to {window[1].isoformat()}. "
                if window is not None
                else "and the series carries no observation at all. "
            )
            + "Nothing is carried forward and nothing is taken from the nearest day: the "
            "publisher's newest closed day is the day before the fetch ran, so a run asking "
            "about the day it ran finds no row by design rather than by accident. Re-run "
            "scripts/fetch_binance.py, or ask about a day the series covers."
        ),
    )


__all__ = [
    "NoQuotationOnDate",
    "Quotation",
    "QuotationSeries",
    "close_on",
    "covered_window",
]
