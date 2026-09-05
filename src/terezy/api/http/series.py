"""The two dated series, and what a window read may and may not say about coverage.

A window is optional; omitted, it returns the whole declared coverage. Given, it is two-ended,
and whatever part of it the series does not declare comes back as a **named refusal beside the
observations that were covered** -- not instead of them. Refusing the whole window would leave a
client to trim the window to what exists, which is a computation 021 FR-001 forbids it; returning
the short list alone is the silent truncation 020 FR-046 forbids.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final

from terezy.api.http import envelopes
from terezy.core.inflation import series as cpi
from terezy.core.inflation.series import CpiObservation, CpiSeries
from terezy.core.primitives.periods import Window, is_period
from terezy.core.tax import official_rate
from terezy.core.tax.official_rate import OfficialRateObservation, OfficialRateSeries

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Sequence

from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class Read:
    """What a windowed read produced: the covered observations, and what fell outside."""

    observations: tuple[object, ...]
    outside: envelopes.WindowOutsideCoverage | None
    checked: envelopes.EveryPeriodChecked | envelopes.OnlyTheEndsChecked


def coverage_of(series: object) -> envelopes.SeriesCoverage | None:
    """The first and last period a series declares, or ``None`` where it declares none."""
    match series:
        case CpiSeries():
            periods = tuple(observation.period for observation in series.observations)
            return None if not periods else envelopes.SeriesCoverage(periods[0], periods[-1])
        case OfficialRateSeries():
            window = official_rate.covered_window(series)
            return (
                None
                if window is None
                else envelopes.SeriesCoverage(window[0].isoformat(), window[1].isoformat())
            )
        case _:
            return None


def window_of(
    series: object, series_id: str, first: str | None, last: str | None
) -> tuple[str, str] | envelopes.WindowMalformed | None:
    """The window a request asked for, checked against the shape the series is keyed by.

    Omitted is a window of its own (the whole declared coverage); one end alone is not, because
    the other would have to be inferred and the inference is what a coverage refusal exists to
    prevent.
    """
    asked = (first, last)
    if first is None and last is None:
        return None
    if first is None or last is None:
        return envelopes.WindowMalformed(
            series_id=series_id,
            asked=asked,
            reason=(
                "a window is two-ended: give both `from` and `to`, or neither. One end alone "
                "would leave the other to be inferred."
            ),
        )
    shape = _shape_of(series)
    malformed = [end for end in (first, last) if not shape.matches(end)]
    if malformed:
        return envelopes.WindowMalformed(
            series_id=series_id,
            asked=asked,
            reason=(
                f"{malformed} is not {shape.description}, which is what this series is keyed by."
            ),
        )
    if first > last:
        return envelopes.WindowMalformed(
            series_id=series_id,
            asked=asked,
            reason=f"the window {(first, last)} ends before it begins.",
        )
    return (first, last)


@dataclass(frozen=True, slots=True)
class _Keying:
    """How one series' periods are spelled, so a request's ends can be checked before use."""

    description: str
    matches: Callable[[str], bool]


def _shape_of(series: object) -> _Keying:
    if isinstance(series, CpiSeries):
        return _Keying("a calendar month as YYYY-MM", is_period)
    return _Keying("a calendar date as YYYY-MM-DD", _is_date)


def _is_date(text: str) -> bool:
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


def read(series: object, window: tuple[str, str] | None) -> Read:
    """Every observation of the window, and a named refusal for whatever it does not cover."""
    match series:
        case CpiSeries():
            return _cpi(series, window)
        case OfficialRateSeries():
            return _rates(series, window)
        case _:
            raise TypeError(f"{type(series).__name__} is not a declared series")


def _cpi(series: CpiSeries, window: tuple[str, str] | None) -> Read:
    if window is None:
        return Read(
            observations=series.observations,
            outside=None,
            checked=envelopes.EveryPeriodChecked(),
        )
    asked = Window(first=window[0], last=window[1])
    covered = cpi.coverage(series, asked)
    inside = _inside(series.observations, window, key=lambda held: held.period)
    match covered:
        case cpi.Covered():
            return Read(
                observations=covered.observations,
                outside=None,
                checked=envelopes.EveryPeriodChecked(),
            )
        case cpi.NotCovered(missing=missing):
            return Read(
                observations=inside,
                outside=_outside(
                    series,
                    window,
                    missing,
                    f"declares no observation for {len(missing)} of the periods asked for",
                ),
                checked=envelopes.EveryPeriodChecked(),
            )


ONLY_THE_ENDS = envelopes.OnlyTheEndsChecked(
    reason=(
        "an official-rate series declares no periodicity, so which dates between its first and "
        "its last were expected is not a fact this layer has. The window's ends were compared "
        "against the declared bounds; a date missing strictly inside them is not detected here."
    )
)
"""What a rate window read actually checked. Enumerating calendar days would infer a
periodicity the declaration does not carry."""


def _rates(series: OfficialRateSeries, window: tuple[str, str] | None) -> Read:
    if window is None:
        return Read(
            observations=series.observations,
            outside=None,
            checked=envelopes.EveryPeriodChecked(),
        )
    inside = _inside(series.observations, window, key=lambda held: held.on_date.isoformat())
    declared = official_rate.covered_window(series)
    missing = _beyond(window, declared)
    return Read(
        observations=inside,
        outside=None
        if not missing
        else _outside(
            series,
            window,
            missing,
            f"does not reach {len(missing)} of the asked window's two ends; what lies between "
            "them was not checked, because this series declares no periodicity",
        ),
        checked=ONLY_THE_ENDS,
    )


def _inside[T](
    observations: Sequence[T], window: tuple[str, str], *, key: Callable[[T], str]
) -> tuple[T, ...]:
    first, last = window
    return tuple(held for held in observations if first <= key(held) <= last)


def _beyond(window: tuple[str, str], declared: tuple[date, date] | None) -> tuple[str, ...]:
    """The ends of the asked window the series does not reach, as the two dates themselves.

    Named ends rather than every uncovered day: see :data:`ONLY_THE_ENDS`, which is what the
    body says about it.
    """
    if declared is None:
        return window
    covers = (declared[0].isoformat(), declared[1].isoformat())
    return tuple(end for end in window if end < covers[0] or end > covers[1])


def _outside(
    series: object, window: tuple[str, str], missing: tuple[str, ...], what: str
) -> envelopes.WindowOutsideCoverage:
    coverage = coverage_of(series)
    series_id = getattr(series, "id", "")
    return envelopes.WindowOutsideCoverage(
        series_id=series_id,
        asked=window,
        covers=None if coverage is None else (coverage.first, coverage.last),
        missing=missing,
        reason=(
            f"the series {series_id!r} {what}. The covered part is returned beside this "
            "refusal; nothing is interpolated, carried forward or snapped to a neighbouring "
            "period."
        ),
    )


OBSERVATION_TYPES: Final[dict[str, type]] = {
    "cpi": CpiObservation,
    "official-rates": OfficialRateObservation,
}
"""Which observation record each series category's window read returns."""
