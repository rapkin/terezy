"""Day-count, periodicity and business-day conventions: registries of functions.

FR-021.

**Why the algorithms are code and only the choice is data**, since this looks like a
Principle II violation and is not. Principle II requires that adding an *instrument*, a
*venue*, a *tax regime* or a *jurisdiction* be a data-only change. A day-count
convention is none of those four -- it is an algorithm, and adding an algorithm is code
by nature. What must stay data-only is the *choice* of convention per issue, and it does:
a second OVDP issue using a different day count is a new file and no engine edit, which
is SC-012 (research.md, "A boundary worth naming explicitly").

**There is no fallback convention, anywhere.** The three lookup functions below take a
name and either return the implementation or raise naming the value and listing what is
known. None of them uses ``dict.get`` with a default, and none of them substitutes a
"sensible" convention for an unrecognised name. Silently applying ``act/365`` to an
issue that declared something else would produce a wrong schedule that looked entirely
plausible, which is the defect class the constitution puts at top severity. The data
layer validates names against these key sets and reports file and field; a name reaching
here unrecognised means that validation was bypassed, which is a programmer error, hence
a raise.
"""

from __future__ import annotations

import calendar
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

DayCountFn = Callable[[date, date], float]
"""Fraction of a year between two dates, under one convention. ``(start, end) -> years``."""

PeriodicityFn = Callable[[date, date], tuple[date, ...]]
"""Coupon dates in ``(start, end]``, ascending, anchored on ``end``.

``start`` is excluded and ``end`` included, because the issue date pays no coupon and
the maturity date pays the final one.
"""

BusinessDayFn = Callable[[date], date]
"""Adjust one date off a non-business day, or return it unchanged."""

_DAYS_IN_COMMON_YEAR: Final = 365
_DAYS_IN_LEAP_YEAR: Final = 366
_DAYS_IN_30_360_MONTH: Final = 30
_DAYS_IN_30_360_YEAR: Final = 360
_LAST_DAY_OF_LONG_MONTH: Final = 31
_MONTHS_IN_YEAR: Final = 12
_SATURDAY: Final = 5


def _require_ordered(start: date, end: date) -> None:
    """Reject a period that runs backwards.

    A negative year fraction would flow into a coupon amount and produce a negative
    payment -- nonsense that looks like a number. Inconsistent *declared* dates are
    caught earlier and reported as a typed ``InconsistentTerms`` value the owner sees
    (FR-018); dates arriving here reversed means the caller skipped that check, which is
    a bug in the code rather than a fact about the instrument, so it raises.
    """
    if end < start:
        raise ValueError(
            f"a period cannot run backwards: start {start.isoformat()} is after end "
            f"{end.isoformat()}"
        )


def _act_365(start: date, end: date) -> float:
    """Actual elapsed days over a fixed 365-day year.

    Leap years are invisible to the denominator, so a calendar year containing 29
    February comes to 366/365 rather than 1.0. That is the convention, not an error.
    """
    _require_ordered(start, end)
    return (end - start).days / _DAYS_IN_COMMON_YEAR


def _act_act_isda(start: date, end: date) -> float:
    """ACT/ACT (ISDA): each calendar year's days over that year's own length.

    The period is split at every 1 January and each part divided by 366 or 365 according
    to whether *its* year is a leap year. Any whole calendar year therefore comes to
    exactly 1.0, which is the property this convention exists to provide.
    """
    _require_ordered(start, end)
    fraction = 0.0
    for year in range(start.year, end.year + 1):
        part_start = max(start, date(year, 1, 1))
        part_end = min(end, date(year + 1, 1, 1))
        if part_end <= part_start:
            continue
        days_in_year = _DAYS_IN_LEAP_YEAR if calendar.isleap(year) else _DAYS_IN_COMMON_YEAR
        fraction += (part_end - part_start).days / days_in_year
    return fraction


def _thirty_360(start: date, end: date) -> float:
    """30/360 US bond basis: every month 30 days, every year 360.

    The end-of-month rule: the start day is capped at 30, and an end day of 31 becomes
    30 only when the capped start day is already 30. That asymmetry is what makes two
    month-end dates six months apart come to exactly 0.5, so a bond on this convention
    pays equal coupons -- which is what a fixed-coupon bond actually does.
    """
    _require_ordered(start, end)
    start_day = min(start.day, _DAYS_IN_30_360_MONTH)
    end_day = end.day
    if end_day == _LAST_DAY_OF_LONG_MONTH and start_day == _DAYS_IN_30_360_MONTH:
        end_day = _DAYS_IN_30_360_MONTH
    days = (
        _DAYS_IN_30_360_YEAR * (end.year - start.year)
        + _DAYS_IN_30_360_MONTH * (end.month - start.month)
        + (end_day - start_day)
    )
    return days / _DAYS_IN_30_360_YEAR


DAY_COUNT_FNS: Final[Mapping[str, DayCountFn]] = {
    "act/365": _act_365,
    "act/act": _act_act_isda,
    "30/360": _thirty_360,
}
"""The day-count conventions this engine implements. The key set is the whole contract."""


def shift_months(anchor: date, months: int) -> date:
    """Move a date by whole months, clamping the day to the target month's length.

    31 January minus one month is 31 December; 31 March minus one month is 28 February
    in a common year. The clamp is applied to a shift measured from the original anchor
    every time, never to the result of a previous shift, so a schedule cannot drift: a
    quarterly bond maturing on a 31st has coupons on the 31st of every long month rather
    than sliding to the 30th once it has passed a short one.

    Public because a bond's month and a goal's contribution month are the same month, and
    two implementations of this clamping rule would be two answers to "what is one month
    after 31 January".
    """
    month_index = anchor.month - 1 + months
    year = anchor.year + month_index // _MONTHS_IN_YEAR
    month = month_index % _MONTHS_IN_YEAR + 1
    day = min(anchor.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _coupon_dates(start: date, end: date, months: int) -> tuple[date, ...]:
    """Coupon dates in ``(start, end]``, stepping back from ``end`` by whole months.

    Anchored on ``end`` because the final coupon is paid with the principal at maturity.
    A short first period is left short rather than a coupon being dropped: the day-count
    fraction, not the step, is what makes that first coupon smaller.
    """
    _require_ordered(start, end)
    dates: list[date] = []
    steps = 0
    current = end
    while current > start:
        dates.append(current)
        steps += 1
        current = shift_months(end, -steps * months)
    return tuple(reversed(dates))


def _periodicity_fn(months: int) -> PeriodicityFn:
    """Close over a month step to make one periodicity's generator.

    A closure rather than a class with a ``months`` attribute: same information, no
    instance state, and the result is a plain function that satisfies ``PeriodicityFn``
    without declaring that it does (owner decision D-E).
    """

    def generate(start: date, end: date) -> tuple[date, ...]:
        return _coupon_dates(start, end, months)

    return generate


_PERIOD_MONTHS: Final[Mapping[str, int]] = {
    "annual": 12,
    "semiannual": 6,
    "quarterly": 3,
}

PERIODICITY_FNS: Final[Mapping[str, PeriodicityFn]] = {
    name: _periodicity_fn(months) for name, months in _PERIOD_MONTHS.items()
}
"""The coupon frequencies this engine implements, built from one month-step mapping.

Derived from ``_PERIOD_MONTHS`` rather than written out twice, so the names and the
steps cannot drift apart.
"""


def _is_weekend(day: date) -> bool:
    """Saturday or Sunday, uncited, and knowing nothing about holidays.

    Declared calendars exist -- ``core.calendars.working_day`` over ``data/calendars/`` -- and
    this function consults none, by owner decision CL-1 of 2026-08-30. So a coupon falling on
    a public holiday is placed on the holiday, and Saturday is asserted a rest day with no
    source behind it. ``tests/contract/test_no_calendar_free_working_day.py`` counts every
    site that inherits both, so a fourth cannot appear quietly.
    """
    return day.weekday() >= _SATURDAY


def is_business_day(day: date) -> bool:
    """Whether a date is a business day -- that is, not a weekend.

    Public so that counting *forward* N business days to a settlement date does not
    reimplement "what counts as a business day" beside its caller. Public holidays are
    declared data now and this function is unchanged: rewiring a site needs an answer to
    *which kind* of calendar governs it, which CL-1 left to whichever feature first has one.
    """
    return not _is_weekend(day)


def _unadjusted(day: date) -> date:
    """Leave the date where the schedule put it.

    A declared choice, not a fallback. An issue whose terms say coupon dates are
    unadjusted says so by naming this rule; the engine never selects it by omission.
    """
    return day


def _following(day: date) -> date:
    """The first business day on or after this date."""
    adjusted = day
    while _is_weekend(adjusted):
        adjusted += timedelta(days=1)
    return adjusted


def _preceding(day: date) -> date:
    """The last business day on or before this date."""
    adjusted = day
    while _is_weekend(adjusted):
        adjusted -= timedelta(days=1)
    return adjusted


def _modified_following(day: date) -> date:
    """Following, unless that would leave the month; then preceding.

    Keeps a coupon inside the month its accrual was measured against, which is why the
    "modified" variant exists.
    """
    adjusted = _following(day)
    if adjusted.month != day.month:
        return _preceding(day)
    return adjusted


BUSINESS_DAY_FNS: Final[Mapping[str, BusinessDayFn]] = {
    "none": _unadjusted,
    "following": _following,
    "modified_following": _modified_following,
}
"""The non-business-day rules this engine implements."""


def _resolve[T](registry: Mapping[str, T], kind: str, name: str) -> T:
    """Look up a declared convention name, or raise naming it and what is known.

    Written as an explicit membership test rather than ``registry.get(name, default)``
    so that no reading of this code suggests a default exists. The raise carries the
    offending value and the full list of accepted names, because the message is the
    remedy: an unrecognised convention is almost always a typo, and a message that names
    the alternatives fixes it in one step.
    """
    if name not in registry:
        raise KeyError(
            f"unknown {kind} convention {name!r}. There is no default convention: an "
            f"issue must declare one this engine implements. Known {kind} conventions: "
            f"{sorted(registry)}"
        )
    return registry[name]


def day_count(name: str) -> DayCountFn:
    """The day-count implementation a declared name selects."""
    return _resolve(DAY_COUNT_FNS, "day-count", name)


def periodicity(name: str) -> PeriodicityFn:
    """The coupon-date generator a declared periodicity name selects."""
    return _resolve(PERIODICITY_FNS, "periodicity", name)


def business_day_rule(name: str) -> BusinessDayFn:
    """The non-business-day adjustment a declared name selects."""
    return _resolve(BUSINESS_DAY_FNS, "business-day", name)


# ---------------------------------------------------------------------------
# What a schedule applied, as the statement a row makes about itself
# ---------------------------------------------------------------------------
#
# 001 FR-021 asks a cash-flow row to **state which convention it applied**, and 013 FR-016
# adds that a schedule of declared payments has to be able to state that two of the three
# never ran. Two records rather than one with nullable fields: a nullable periodicity is a
# question about which kind of declaration produced the row, asked without naming it, and a
# statement carrying a field it cannot fill is a statement a reader has to interpret.
#
# They live here, below both the instrument layer that answers the question and the result
# layer that renders the answer, so neither has to import the other to say what happened.


@dataclass(frozen=True, slots=True)
class ConventionsApplied:
    """The three declared conventions that generated a schedule's dates and amounts.

    Carried on every row rather than once on the schedule, because 001 FR-021 is a statement
    about what the schedule *says*: a row lifted out of the table -- into a report, into a
    comparison -- has to keep saying which convention placed it. They are identical across
    the rows of one issue today; they will not be when a schedule spans two instruments.
    """

    periodicity: str
    """The declared coupon frequency that generated the dates."""

    day_count: str
    """The declared day-count convention that turned each accrual period into a fraction
    of a year, and therefore fixed each coupon's size **on this schedule** -- a claim about
    these rows, not about day counts in general (013 FR-016).
    """

    business_day_rule: str
    """The declared rule that moved a payment off a non-business day. It did not move the
    period each coupon's **size** was measured over (`docs/METHODOLOGY.md` §1.3)."""


_DECLARED_REASON: Final = (
    "no periodicity generated this date, no business-day rule moved it, and no day count "
    "sized this amount -- the amount is declared, per unit, and is carried through "
    "unchanged. The day count named here annualises a span and does nothing else."
)


@dataclass(frozen=True, slots=True)
class AmountsAsDeclared:
    """What a schedule of declared dated payments applied: one convention, to annualise.

    The sibling of :class:`ConventionsApplied`, and FR-016's two halves are what shape it.
    It **names** a day count, because one is declared and a yield is annualised on it, and a
    row claiming none had been applied would be false the moment that yield is emitted from
    the same projection. It names **no** periodicity and **no** business-day rule, because
    neither ran, and there is nowhere here to put one.
    """

    day_count: str
    """The declared convention that annualises a span. It sizes nothing (FR-003b)."""

    reason: str = _DECLARED_REASON
    """What the row states, in the words it states it in.

    Defaulted because it is the same sentence on every such row and a caller retyping it is
    a caller who can get it subtly wrong; overridable because a later schedule shape may have
    a different true thing to say.
    """
