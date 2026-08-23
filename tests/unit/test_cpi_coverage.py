"""Coverage is all-or-nothing, checked before any arithmetic, and a gap is named.

G5 and research.md D4. The realized real figure requires observations covering **every**
month of the deflation window. One missing month makes it unavailable naming that month;
nothing is interpolated, nothing is carried forward, and the window is never shortened to
the part that happens to be covered.

**Shortening is the tempting one**, which is why half the tests below are about it: it
produces a number, and the number really is real -- for *a* window, just not the one asked
about. A reader shown a real rate over "the covered part" has no way to know the question
changed under them.

The union is returned *before* the product runs, so an uncovered window cannot reach the
Fisher relation at all (plan.md, Complexity Tracking). ``test_the_uncovered_case_carries_no
_observations`` is what makes that structural rather than a convention: ``NotCovered`` has
no field an implementation could reach into for a partial answer.
"""

from __future__ import annotations

import pytest

from terezy.core.inflation import series as cpi
from terezy.core.inflation.deflate import deflate
from terezy.core.inflation.series import Covered, NotCovered
from tests import cpi_fixtures


def test_a_fully_covered_window_returns_its_observations_in_order() -> None:
    declared = cpi_fixtures.series(cpi_fixtures.run_of("2026-01", 6, 101.0))
    result = cpi.coverage(declared, cpi_fixtures.window("2026-02", "2026-05"))
    assert isinstance(result, Covered)
    assert tuple(item.period for item in result.observations) == (
        "2026-02",
        "2026-03",
        "2026-04",
        "2026-05",
    )


def test_observations_outside_the_window_do_not_participate() -> None:
    """The window decides, not the series: a longer series does not lengthen the deflation."""
    declared = cpi_fixtures.series(cpi_fixtures.run_of("2020-01", 120, 101.0))
    result = cpi.coverage(declared, cpi_fixtures.window("2026-02", "2026-03"))
    assert isinstance(result, Covered)
    assert len(result.observations) == 2


def test_the_observations_come_back_in_window_order_not_file_order() -> None:
    """A file may declare months in any order; the chain multiplies them in calendar order.

    Multiplication is commutative, so this does not change the product -- it changes what a
    reader is shown when the observations are enumerated for provenance, and an out-of-order
    enumeration of the months behind a figure is a trail nobody can follow.
    """
    declared = cpi_fixtures.series([("2026-03", 103.0), ("2026-01", 101.0), ("2026-02", 102.0)])
    result = cpi.coverage(declared, cpi_fixtures.window("2026-01", "2026-03"))
    assert isinstance(result, Covered)
    assert tuple(item.period for item in result.observations) == ("2026-01", "2026-02", "2026-03")


def test_one_missing_month_makes_the_whole_window_uncovered_and_names_it() -> None:
    """The gap-in-the-middle case: months 1-3 and 5-6 declared, a window crossing month 4."""
    declared = cpi_fixtures.series(
        [
            ("2026-01", 101.0),
            ("2026-02", 101.0),
            ("2026-03", 101.0),
            ("2026-05", 101.0),
            ("2026-06", 101.0),
        ]
    )
    result = cpi.coverage(declared, cpi_fixtures.window("2026-01", "2026-06"))
    assert isinstance(result, NotCovered)
    assert result.missing == ("2026-04",)


def test_every_missing_month_is_named_not_only_the_first() -> None:
    """A reader fixing a series needs the whole list; naming one month invites two round trips."""
    declared = cpi_fixtures.series([("2026-01", 101.0), ("2026-05", 101.0)])
    result = cpi.coverage(declared, cpi_fixtures.window("2026-01", "2026-05"))
    assert isinstance(result, NotCovered)
    assert result.missing == ("2026-02", "2026-03", "2026-04")


def test_a_window_running_past_the_end_of_the_series_is_uncovered() -> None:
    """The case that bites today: the shipped series ends 2025-10 and every hurdle reaches 2026.

    Never extrapolated and never carried forward. Re-running the fetcher is the fix, and the
    refusal is what stops a number being invented in the meantime (research.md D4).
    """
    declared = cpi_fixtures.series(cpi_fixtures.run_of("2025-08", 3, 100.9))
    result = cpi.coverage(declared, cpi_fixtures.window("2025-09", "2026-01"))
    assert isinstance(result, NotCovered)
    assert result.missing == ("2025-11", "2025-12", "2026-01")


def test_a_window_before_the_start_of_the_series_is_uncovered() -> None:
    """Backwards is the same rule as forwards. There is no earliest month to carry back from."""
    declared = cpi_fixtures.series(cpi_fixtures.run_of("2026-01", 3, 101.0))
    result = cpi.coverage(declared, cpi_fixtures.window("2025-11", "2026-01"))
    assert isinstance(result, NotCovered)
    assert result.missing == ("2025-11", "2025-12")


def test_a_series_with_no_observations_covers_nothing_and_says_which_months() -> None:
    declared = cpi_fixtures.series([])
    result = cpi.coverage(declared, cpi_fixtures.window("2026-01", "2026-02"))
    assert isinstance(result, NotCovered)
    assert result.missing == ("2026-01", "2026-02")


def test_the_window_is_never_shortened_to_its_covered_part() -> None:
    """Partial coverage is not coverage (spec.md, Edge Cases).

    The series covers four of the six months asked about. A shortened answer would be a
    perfectly good real rate for a four-month window nobody asked about, and the reader has
    no way to see the substitution.
    """
    declared = cpi_fixtures.series(cpi_fixtures.run_of("2026-01", 4, 101.0))
    result = cpi.coverage(declared, cpi_fixtures.window("2026-01", "2026-06"))
    assert isinstance(result, NotCovered)
    assert result.missing == ("2026-05", "2026-06")


def test_the_uncovered_case_carries_no_observations_at_all() -> None:
    """The structural half: ``NotCovered`` has no field a partial answer could come out of.

    A check *inside* the computation is a check someone later moves, reorders or
    short-circuits. A union returned first makes the uncovered case unrepresentable
    downstream -- there is nothing on it to multiply.
    """
    declared = cpi_fixtures.series(cpi_fixtures.run_of("2026-01", 4, 101.0))
    result = cpi.coverage(declared, cpi_fixtures.window("2026-01", "2026-06"))
    assert isinstance(result, NotCovered)
    assert not hasattr(result, "observations")


def test_a_window_with_no_elapsed_month_is_not_reported_as_covered() -> None:
    """A holding bought and matured inside one month has nothing to deflate over.

    ``months_in`` returns nothing for such a window, and returning ``Covered(())`` would let
    the product of no months -- exactly zero inflation -- reach the Fisher relation and
    produce a real rate equal to the nominal one. That is a confident wrong answer, so the
    emptiness is reported instead.
    """
    declared = cpi_fixtures.series(cpi_fixtures.run_of("2026-01", 6, 101.0))
    result = cpi.coverage(declared, cpi_fixtures.window("2026-05", "2026-04"))
    assert isinstance(result, NotCovered)
    assert result.missing == ()


# --- the programmer-error guards -------------------------------------------------------
#
# Three refusals in this feature's core are raises rather than typed values, because reaching
# them means a data-layer check was bypassed rather than that something is wrong with the
# money. They are still tested, for the reason ``primitives/periods.py::_parts`` is: an
# untested guard is a guard whose message can be false and nobody notices, and its message is
# the only thing a reader of the traceback gets.


def test_a_series_declaring_one_period_twice_is_refused_rather_than_read() -> None:
    """The loader refuses a duplicate period and can name the file; reaching here is a bypass.

    Silently keeping either copy would make the chained product depend on which row was read
    second -- a figure that changes when a file is reordered, with nothing saying so.
    """
    doubled = cpi_fixtures.series([("2026-01", 101.0), ("2026-01", 109.0)])

    with pytest.raises(KeyError, match="2026-01"):
        cpi.coverage(doubled, cpi_fixtures.window("2026-01", "2026-01"))


def test_annualising_over_no_periods_is_refused_rather_than_answered() -> None:
    """A window with no elapsed period is reported by name before the arithmetic runs.

    There is no rate per annum for a span of no time, and returning one -- or dividing by zero
    and letting the traceback explain -- would be worse than saying so.
    """
    with pytest.raises(ValueError, match="0 periods"):
        cpi.annualised(0.05, periods=0, per_year=12)

    with pytest.raises(ValueError, match="-1 periods"):
        cpi.annualised(0.05, periods=-1, per_year=12)


def test_deflating_by_total_collapse_is_refused_rather_than_dividing_by_zero() -> None:
    """Inflation of exactly -1 is prices having fallen to nothing; every real rate is infinite.

    Declared index values are strictly positive and declared assumed rates strictly above -1,
    both checked at the data boundary, so this is unreachable from declared data. The message
    is what a reader gets if it ever is reached, and ``ZeroDivisionError`` says nothing about
    money.
    """
    with pytest.raises(ValueError, match="fallen to nothing"):
        deflate(nominal=0.155, inflation=-1.0)
