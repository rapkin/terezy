"""Deflation is a valid observation, and a negative real rate is a valid answer.

G6 and SC-007. Two directions, both hand-computed, and neither of them clamped.

## Prices fell: the real rate comes out **above** the nominal one

Twelve months at 99.0 -- one percent off every month::

    0.99 ** 2  = 0.9801
    0.99 ** 4  = 0.9801 ** 2       = 0.96059601
    0.99 ** 8  = 0.96059601 ** 2   = 0.9227446944279201
    0.99 ** 12 = 0.9227446944279201 x 0.96059601 = 0.8863848717161291

    cumulative = -0.11361512828387088   (prices are 11.36% lower than they were)
    real       = 1.155 / 0.8863848717161291 - 1 = 0.30304570492477545

Thirty percent real against fifteen and a half percent nominal. That is not an error and it
is not a bug to be clamped away: money that buys more than it did has earned more than its
coupon says. A ``max(0, ...)`` anywhere in this path would silently delete the finding.

## Prices ran away: the real rate comes out **negative**

Twelve months at 110.0 -- ten percent on every month, which Ukraine has genuinely seen::

    1.1 ** 12  = 3.1384283767210035
    cumulative = 2.1384283767210035    (prices more than tripled)
    real       = 1.155 / 3.1384283767210035 - 1 = -0.6319814055445383

Minus sixty-three percent, reported as such. This is the answer the whole feature exists to
be able to give: a nominal 15.5% against that is a large loss, and a tool that reported the
nominal figure alone would be confidently wrong about the only thing that matters.

Both directions run through the same two functions as every other example. There is no
branch on the sign anywhere -- ``tests/invariants/test_deflation_invariants.py`` asserts the
absence of one over generated inputs, and these two cases are what it looks like at values a
person can check on paper.
"""

from __future__ import annotations

import pytest

from terezy.core.inflation import series as cpi
from terezy.core.inflation.deflate import deflate
from terezy.core.primitives.tolerance import is_close
from tests import cpi_fixtures

pytestmark = pytest.mark.worked_example

NOMINAL_YTM = 0.155
"""The same contractual yield the other worked examples deflate, so the cases compare."""


def _cumulative(value: float) -> float:
    """Twelve declared months at one index value, chained over a fully covered window."""
    declared = cpi_fixtures.series(cpi_fixtures.run_of("2026-01", 12, value))
    covered = cpi.coverage(declared, cpi_fixtures.window("2026-01", "2026-12"))
    assert isinstance(covered, cpi.Covered)
    return cpi.cumulative_inflation(covered.observations)


def test_a_year_of_falling_prices_chains_to_a_negative_cumulative_figure() -> None:
    """0.99 ** 12 - 1 = -0.11361512828387088. Negative, and reported as negative."""
    assert is_close(_cumulative(99.0), -0.11361512828387088)


def test_falling_prices_put_the_real_rate_above_the_nominal_one() -> None:
    """1.155 / 0.8863848717161291 - 1 = 0.30304570492477545, against a nominal 0.155."""
    real = deflate(nominal=NOMINAL_YTM, inflation=-0.11361512828387088)

    assert is_close(real, 0.30304570492477545)
    assert real > NOMINAL_YTM


def test_a_year_of_ten_percent_monthly_inflation_chains_to_a_tripling() -> None:
    """1.1 ** 12 - 1 = 2.1384283767210035. Prices more than tripled in the year."""
    assert is_close(_cumulative(110.0), 2.1384283767210035)


def test_high_inflation_puts_the_real_rate_below_zero_and_it_stays_there() -> None:
    """1.155 / 3.1384283767210035 - 1 = -0.6319814055445383. Not clamped to zero."""
    real = deflate(nominal=NOMINAL_YTM, inflation=2.1384283767210035)

    assert is_close(real, -0.6319814055445383)
    assert real < 0.0


def test_the_two_directions_run_through_the_same_function_with_no_branch_on_sign() -> None:
    """The falsifier: a clamp would be invisible in either case alone.

    A ``max(0, ...)`` would leave the falling-prices example green -- its answer is positive
    anyway -- and only the high-inflation one would fail. A ``min(nominal, ...)`` would do the
    reverse. Asserting both against hand-computed values in one file is what makes either
    clamp a red test rather than a plausible-looking output.
    """
    falling = deflate(nominal=NOMINAL_YTM, inflation=-0.11361512828387088)
    running = deflate(nominal=NOMINAL_YTM, inflation=2.1384283767210035)

    assert falling > NOMINAL_YTM > 0.0 > running
