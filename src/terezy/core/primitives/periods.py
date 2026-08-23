"""Calendar months as ``YYYY-MM``, and the inclusive window a figure is measured over.

A price index is published *per period*, so every question about it is a question about a
span of periods: which months does this series cover, how many of them did the holding
live through, what is the product of their changes. This module is that arithmetic and
nothing else -- no prices, no rates, no opinion about what a month is worth.

**Why a string and not a ``date``.** A month is not a day. ``date(2026, 1, 1)`` standing
for January 2026 invites two silent errors that a ``YYYY-MM`` string cannot express: a
day-of-month that means nothing but participates in comparisons, and a period that looks
like an instant when it is a span. The declaration files write ``period = "2026-01"``, the
records carry the same text, and the golden renders it unchanged -- one representation
from the file to the output.

**Why it lives in ``primitives`` rather than beside the CPI series it was written for.**
:class:`Window` is a field of ``primitives.rates.RealRate``, and a rate reaching upward
into ``core.inflation`` for its own field's type would invert the direction the rest of
the package points. A window is a calendar fact; the series that fills one is not.

**Why a reversed window is empty rather than an error.** ``months_in`` is what the
coverage check iterates, and a window whose first month is after its last describes a
holding that began and ended in one month. That is a fact about the money, so the
emptiness is returned and the caller reports it by name -- the same reading that makes
``staleness.age_in_days`` return a negative number rather than clamping it. A *malformed*
period is the opposite case and raises: the data layer validates the shape and can name
the file, so one arriving here is a bypass rather than a fact.

**No clock.** Every date in this module is an argument.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

_MONTHS_IN_A_YEAR: Final = 12
"""Named so the modular arithmetic below reads as calendar arithmetic rather than as a
literal twelve that could plausibly be something else."""

_PERIOD_LENGTH: Final = 7
"""``YYYY-MM`` -- four digits, a hyphen, two digits."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Window:
    """An inclusive span of calendar months: ``first`` and ``last`` both belong to it.

    Inclusive at both ends because that is how a coverage question is asked -- *"is every
    month from November to February declared?"* -- and a half-open window would put an
    off-by-one between the question and the answer, in the one place where an off-by-one
    is a whole month of inflation.

    Carries data only, and is compared by value: it travels on a
    ``primitives.rates.RealRate`` as the statement of what the figure was deflated over
    (FR-011), and is rendered into the golden artefact from there.
    """

    first: str
    """The first month in the span, as ``YYYY-MM``."""

    last: str
    """The last month in the span, as ``YYYY-MM``. Inclusive."""


def is_period(text: str) -> bool:
    """Whether ``text`` is a month in the declared shape: four digits, a hyphen, two digits.

    Checked here rather than with a regular expression so that the rule is legible at the
    one place it is defined, and so the data layer and the core agree about it by calling
    the same function rather than by maintaining two patterns that drift.
    """
    if len(text) != _PERIOD_LENGTH or text[4] != "-":
        return False
    year, month = text[:4], text[5:]
    if not (year.isdigit() and month.isdigit()):
        return False
    return 1 <= int(month) <= _MONTHS_IN_A_YEAR


def month_of(day: date) -> str:
    """The month a date falls in, as ``YYYY-MM``. Zero-padded.

    Zero-padded because these strings are sorted and compared as text in the loader's
    duplicate and ordering checks, and ``"2026-9"`` sorts after ``"2026-10"`` while
    ``"2026-09"`` does not.
    """
    return f"{day.year:04d}-{day.month:02d}"


def ordinal(period: str) -> int:
    """A month as a count of months since year zero, for ordering and differencing.

    The one place month arithmetic happens. Comparing two ``YYYY-MM`` strings as text
    happens to give the right order, and differencing them does not -- ``"2027-01"`` minus
    ``"2026-12"`` is one month and no string operation says so.
    """
    year, month = _parts(period)
    return year * _MONTHS_IN_A_YEAR + (month - 1)


def next_month(period: str) -> str:
    """The month after ``period``, rolling December into January of the next year."""
    return _from_ordinal(ordinal(period) + 1)


def month_count(window: Window) -> int:
    """How many months the window contains. Zero when its first month is after its last.

    Arithmetic rather than a walk, and held to agreeing with :func:`months_in` by
    ``tests/unit/test_periods.py``: the annualisation divides by this count and the
    cumulative product multiplies over that enumeration, so a disagreement between the two
    would be an off-by-one *inside* a real rate rather than beside it.
    """
    return max(0, ordinal(window.last) - ordinal(window.first) + 1)


def months_in(window: Window) -> tuple[str, ...]:
    """Every month of the window, in order, inclusive at both ends.

    Empty when the window's first month is after its last. See the module docstring for
    why that is returned rather than raised.
    """
    start = ordinal(window.first)
    return tuple(_from_ordinal(start + offset) for offset in range(month_count(window)))


def _parts(period: str) -> tuple[int, int]:
    """``("2026-01")`` -> ``(2026, 1)``, or a raise naming what was passed instead.

    Raises ``ValueError`` on a malformed period. That is a statement about the code, not
    about the money: ``schema.py`` and the loader check the shape and can name the file and
    the field, so a period reaching here in another shape means that validation was
    bypassed -- and guessing what ``"2026-13"`` meant would put a month in a figure that no
    file declares. The same reading as ``staleness.kind_for`` and ``regimes._checked``.
    """
    if not is_period(period):
        raise ValueError(
            f"{period!r} is not a calendar month in the declared shape YYYY-MM. Periods are "
            "validated at the data boundary, where the file and the field can be named, so "
            "one arriving here in another shape means that check was bypassed. It is refused "
            "rather than interpreted: there is no honest reading of a thirteenth month."
        )
    return int(period[:4]), int(period[5:])


def _from_ordinal(count: int) -> str:
    """The inverse of :func:`ordinal`: a month count back to ``YYYY-MM``."""
    year, month = divmod(count, _MONTHS_IN_A_YEAR)
    return f"{year:04d}-{month + 1:02d}"
