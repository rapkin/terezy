"""The chained product and the exact Fisher relation, worked out by hand.

SC-001 and FR-008. Two claims, and the window is chosen so that getting either one wrong
gives a visibly different answer rather than a slightly different one.

## Claim 1 -- a window is a product, not a sum

``data/cpi/ua.toml`` holds the published index of each month **against the previous month**:
``100.9`` means prices rose 0.9% *that month*. Cumulative inflation over a window is
therefore the product of every month's ``value / 100``, minus one -- never the sum of the
monthly changes.

Twelve months at 5% each is the example, because the two answers are nowhere near each
other::

    sum:      12 x 0.05                    = 0.60          (60%)
    product:  1.05 ** 12 - 1               = 0.7958563...  (79.59%)

Nineteen and a half percentage points apart. A summing implementation cannot pass this
file, which is the whole reason the window is twelve months of five percent rather than
three months of one (research.md D1).

The power is hand-checkable by squaring twice and multiplying once::

    1.05 ** 2  = 1.1025
    1.05 ** 4  = 1.1025 ** 2      = 1.21550625
    1.05 ** 8  = 1.21550625 ** 2  = 1.4774554437890625
    1.05 ** 12 = 1.4774554437890625 x 1.21550625 = 1.7958563260221301

## Claim 2 -- the exact Fisher relation, never the subtraction

The real rate is::

    real = (1 + nominal) / (1 + inflation) - 1

not ``nominal - inflation``. At the magnitudes above the two are not close::

    exact:          1.155 / 1.7958563260221301 - 1 = -0.3568527820049191
    approximation:  0.155 - 0.7958563260221301     = -0.6408563260221301

Twenty-eight percentage points apart, on a decision this tool exists to get right. The
approximation is not merely discouraged: no function in the feature performs it, and
``tests/contract/test_no_subtraction_approximation.py`` scans the source to keep it so.

## Claim 3 -- a rate is annualised before it is deflated

``nominal_ytm`` is a rate **per annum**, so the inflation it is deflated by must be per annum
too. A cumulative figure over six months compared against an annual yield would understate
inflation by roughly half, which is a modelling error dressed as a units error. The second
example below runs over six months precisely so the annualisation has something to do.

Every comparison uses the single imported project tolerance. Nothing here defines its own.
"""

from __future__ import annotations

import pytest

from terezy.core.inflation import series as cpi
from terezy.core.inflation.deflate import deflate
from terezy.core.primitives.tolerance import TOLERANCE, is_close
from tests import cpi_fixtures

pytestmark = pytest.mark.worked_example

NOMINAL_YTM = 0.155
"""The contractual yield the examples deflate: feature 001's synthetic 15.5% coupon at par."""


def test_twelve_months_at_five_percent_chain_to_the_hand_computed_product() -> None:
    """1.05 ** 12 - 1 = 0.7958563260221301, and it is emphatically not 0.60."""
    months = cpi_fixtures.run_of("2026-01", 12, 105.0)
    declared = cpi_fixtures.series(months)
    covered = cpi.coverage(declared, cpi_fixtures.window("2026-01", "2026-12"))
    assert isinstance(covered, cpi.Covered)

    cumulative = cpi.cumulative_inflation(covered.observations)

    assert is_close(cumulative, 0.7958563260221301)


def test_the_product_and_the_sum_are_far_enough_apart_that_the_test_can_tell() -> None:
    """Guard against the example above passing for a reason other than the one claimed.

    If the two answers were within the tolerance of one another, the first test would be
    green under a summing implementation and would say nothing. They are 0.196 apart.
    """
    months = cpi_fixtures.run_of("2026-01", 12, 105.0)
    summed = sum(value / 100.0 - 1.0 for _, value in months)

    assert is_close(summed, 0.6000000000000005)
    assert abs(0.7958563260221301 - summed) > 0.19
    assert not is_close(0.7958563260221301, summed)


def test_the_real_rate_is_the_exact_fisher_relation() -> None:
    """1.155 / 1.7958563260221301 - 1 = -0.3568527820049191.

    Deeply negative, and correctly so: 15.5% nominal against 79.6% inflation is a large loss
    of purchasing power. It is reported as the negative number it is, never clamped.
    """
    real = deflate(nominal=NOMINAL_YTM, inflation=0.7958563260221301)

    assert is_close(real, -0.3568527820049191)


def test_the_subtraction_approximation_would_give_a_different_answer() -> None:
    """The falsifier for the test above: -0.3569 exact against -0.6409 approximate.

    Without this, a Fisher implementation that silently subtracted would have to be caught by
    reading the source. Here the arithmetic itself says the two are 28 percentage points
    apart, which is why FR-008 forbids the approximation rather than tolerating it.
    """
    approximation = NOMINAL_YTM - 0.7958563260221301

    assert is_close(approximation, -0.6408563260221301)
    assert abs(-0.3568527820049191 - approximation) > 0.28


def test_a_six_month_window_is_annualised_before_it_is_deflated() -> None:
    """Six declared months, chained, raised to the 12/6 power, then deflated.

        1.009 x 1.012 x 0.998 x 1.003 x 1.021 x 1.000 = 1.043587563960392
        cumulative over six months                    = 0.043587563960391984
        annualised: 1.043587563960392 ** 2 - 1        = 0.0890750036527852
        real:  1.155 / 1.0890750036527852 - 1         = 0.060533017584740056

    The annualised figure is roughly twice the cumulative one, which is the whole point: a
    hurdle rate quoted per annum deflated by six months of inflation would flatter the real
    return by about four and a half percentage points.
    """
    months = [
        ("2026-01", 100.9),
        ("2026-02", 101.2),
        ("2026-03", 99.8),
        ("2026-04", 100.3),
        ("2026-05", 102.1),
        ("2026-06", 100.0),
    ]
    declared = cpi_fixtures.series(months)
    covered = cpi.coverage(declared, cpi_fixtures.window("2026-01", "2026-06"))
    assert isinstance(covered, cpi.Covered)

    cumulative = cpi.cumulative_inflation(covered.observations)
    assert is_close(cumulative, 0.043587563960391984)

    annual = cpi.annualised(cumulative, periods=6, per_year=12)
    assert is_close(annual, 0.0890750036527852)

    real = deflate(nominal=NOMINAL_YTM, inflation=annual)
    assert is_close(real, 0.060533017584740056)


def test_annualising_a_twelve_month_window_changes_nothing() -> None:
    """The identity case, checked because an exponent of one is where an off-by-one hides.

    Twelve monthly observations annualise to themselves. If ``month_count`` and the
    enumeration ever disagreed by one, the exponent would be 12/11 or 12/13 and this would be
    the first test to notice.
    """
    annual = cpi.annualised(0.7958563260221301, periods=12, per_year=12)

    assert is_close(annual, 0.7958563260221301, tolerance=TOLERANCE)


def test_zero_inflation_leaves_the_nominal_rate_where_it_was() -> None:
    """The degenerate case, and the one a reader checks first: no inflation, no deflation.

    Within the project tolerance rather than bit-exact, and that is float64 rather than a
    choice: ``(1 + 0.155) / 1 - 1`` re-derives 0.155 through an addition that loses a bit at
    some values. Special-casing zero inside ``deflate`` would put a branch on the input's value
    into the one function that must not have one.
    """
    assert is_close(deflate(nominal=NOMINAL_YTM, inflation=0.0), NOMINAL_YTM)


def test_the_chain_over_no_observations_is_no_inflation() -> None:
    """The empty product is one, so the empty chain is zero inflation.

    Stated rather than left implicit, and it is *not* how an uncovered window is answered:
    ``coverage`` refuses that case before this function is reached, precisely so a window
    nobody has data for cannot arrive here and come back as "prices did not move".
    """
    assert cpi.cumulative_inflation(()) == 0.0
