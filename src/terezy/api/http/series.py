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
from terezy.core.primitives.periods import Window
from terezy.core.tax import official_rate
from terezy.core.tax.official_rate import OfficialRateObservation, OfficialRateSeries

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Callable, Sequence


@dataclass(frozen=True, slots=True)
class Read:
    """What a windowed read produced: the covered observations, and what fell outside."""

    observations: tuple[object, ...]
    outside: envelopes.WindowOutsideCoverage | None


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
        return Read(observations=series.observations, outside=None)
    asked = Window(first=window[0], last=window[1])
    covered = cpi.coverage(series, asked)
    inside = _inside(series.observations, window, key=lambda held: held.period)
    match covered:
        case cpi.Covered():
            return Read(observations=covered.observations, outside=None)
        case cpi.NotCovered(missing=missing):
            return Read(
                observations=inside,
                outside=_outside(series, window, missing),
            )


def _rates(series: OfficialRateSeries, window: tuple[str, str] | None) -> Read:
    if window is None:
        return Read(observations=series.observations, outside=None)
    inside = _inside(series.observations, window, key=lambda held: held.on_date.isoformat())
    declared = official_rate.covered_window(series)
    missing = _beyond(window, declared)
    return Read(
        observations=inside,
        outside=None if not missing else _outside(series, window, missing),
    )


def _inside[T](
    observations: Sequence[T], window: tuple[str, str], *, key: Callable[[T], str]
) -> tuple[T, ...]:
    first, last = window
    return tuple(held for held in observations if first <= key(held) <= last)


def _beyond(window: tuple[str, str], declared: tuple[date, date] | None) -> tuple[str, ...]:
    """The ends of the asked window the series does not reach, as the two dates themselves.

    Named ends rather than every uncovered day, because an official-rate series **declares no
    periodicity** -- so which days between its first and its last were expected is not a fact
    this layer has, and enumerating calendar days would be inferring one. A gap strictly inside
    the declared bounds is therefore not detectable here; the CPI series has a declared
    periodicity and its own coverage function, which is why that arm can name every missing
    month.
    """
    if declared is None:
        return window
    covers = (declared[0].isoformat(), declared[1].isoformat())
    return tuple(end for end in window if end < covers[0] or end > covers[1])


def _outside(
    series: object, window: tuple[str, str], missing: tuple[str, ...]
) -> envelopes.WindowOutsideCoverage:
    coverage = coverage_of(series)
    series_id = getattr(series, "id", "")
    return envelopes.WindowOutsideCoverage(
        series_id=series_id,
        asked=window,
        covers=None if coverage is None else (coverage.first, coverage.last),
        missing=missing,
        reason=(
            f"the series {series_id!r} declares no observation for "
            f"{len(missing)} of the periods asked for, the first being {missing[0]!r}. "
            "The covered part is returned beside this refusal; nothing is interpolated, "
            "carried forward or snapped to a neighbouring period."
        ),
    )


OBSERVATION_TYPES: Final[dict[str, type]] = {
    "cpi": CpiObservation,
    "official-rates": OfficialRateObservation,
}
"""Which observation record each series category's window read returns."""
