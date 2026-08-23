"""Properties of the deflation arithmetic that must hold for every input, not only the examples.

The worked examples pin four hand-computed points. These are the claims that must be true
everywhere between them, generated rather than chosen -- because the failure mode a chosen
example cannot see is a branch on the sign, a clamp that only fires outside the range someone
happened to test, or a chain whose answer depends on where it is split.

Five properties:

* **The relation inverts.** ``(1 + real) * (1 + inflation) == 1 + nominal``. This is the
  definition of the Fisher relation, and asserting it back rather than re-deriving it forward
  is what makes the assertion independent of the implementation.
* **The sign rule has no exceptions.** The real rate exceeds the nominal one whenever prices
  fell, sits below it whenever they rose, and returns it when they did not move. A clamp
  anywhere -- to zero, to the nominal figure, to a floor -- breaks this for some generated
  input even if it survives every example a person would write. The two strict directions
  generate inflation bounded away from zero by the *project* tolerance, because below that
  bound the codebase does not claim two rates differ at all.
* **The chain is a monoid.** Chaining a window is the same as chaining its halves and
  compounding the results, for every split point. If it were not, the answer would depend on
  how the months happened to be grouped, which is the property that makes a *sum* wrong.
* **The chain is a product, structurally.** For a run of equal months the cumulative figure is
  a power, and for a run of two it is the pairwise product -- both stated against generated
  values so that no single magnitude can hide a summation.
* **Coverage is total.** Every window over every series returns exactly one of the two union
  members, and a ``Covered`` result always holds exactly one observation per month of the
  window.

Nothing here uses a tolerance of its own; ``is_close`` from ``primitives.tolerance`` is the
single project tolerance and is imported.
"""

from __future__ import annotations

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from terezy.core.inflation import series as cpi
from terezy.core.inflation.deflate import deflate
from terezy.core.primitives import periods
from terezy.core.primitives.tolerance import TOLERANCE, is_close
from tests import cpi_fixtures

pytestmark = pytest.mark.invariant

rates = st.floats(min_value=-0.9, max_value=5.0, allow_nan=False, allow_infinity=False)
"""Nominal rates from a near-total loss to 500% -- the range this project will report."""

inflations = st.floats(min_value=-0.9, max_value=20.0, allow_nan=False, allow_infinity=False)
"""Inflation from 90% deflation to twentyfold. The upper end is not hypothetical: Ukraine's
1993 monthly indices chain past it inside a year."""

rising = st.floats(min_value=TOLERANCE, max_value=20.0, allow_nan=False, allow_infinity=False)
"""Inflation strictly above the project tolerance, so "prices rose" is a claim float64 can keep.

Bounded below by ``TOLERANCE`` rather than by zero, and by the project's own tolerance rather
than by a number invented here: below it two rates are indistinguishable *by this project's
definition*, so asserting a strict inequality there would be asserting something the rest of
the codebase does not believe. It is a bound on the generated input, not a slackened
comparison -- the assertions themselves stay exact.
"""

falling = st.floats(min_value=-0.9, max_value=-TOLERANCE, allow_nan=False, allow_infinity=False)
"""Deflation strictly below the negative project tolerance. See :data:`rising`."""

index_values = st.floats(min_value=50.0, max_value=200.0, allow_nan=False, allow_infinity=False)
"""A published month-on-month index: half to double in one month. Strictly positive, which is
what keeps a chained factor above zero and the Fisher denominator away from it."""


@given(nominal=rates, inflation=inflations)
def test_the_fisher_relation_inverts(nominal: float, inflation: float) -> None:
    """``(1 + real) * (1 + inflation) == 1 + nominal``, which is what "exact" means."""
    real = deflate(nominal=nominal, inflation=inflation)

    assert is_close((1.0 + real) * (1.0 + inflation), 1.0 + nominal)


@given(nominal=rates, inflation=rising)
def test_rising_prices_always_put_the_real_rate_below_the_nominal_one(
    nominal: float, inflation: float
) -> None:
    """No floor, anywhere. A clamp at zero would survive every example with a positive answer."""
    assert deflate(nominal=nominal, inflation=inflation) < nominal


@given(nominal=rates, inflation=falling)
def test_falling_prices_always_put_the_real_rate_above_the_nominal_one(
    nominal: float, inflation: float
) -> None:
    """The other direction, and the one a ``min(nominal, ...)`` would break invisibly."""
    assert deflate(nominal=nominal, inflation=inflation) > nominal


@given(nominal=rates)
def test_zero_inflation_returns_the_nominal_rate(nominal: float) -> None:
    """To within the project tolerance, and not exactly -- which is float64's doing, not a choice.

    ``(1 + n) / 1 - 1`` re-derives ``n`` through an addition that is not lossless: at
    ``n = 0.2543421417542501`` the round trip lands one ulp away. The alternative would be a
    special case for zero inflation inside ``deflate``, which is a branch on the value of the
    input in the one function that must not have one -- the clamp the tests above exist to
    forbid, arriving as a convenience.
    """
    assert is_close(deflate(nominal=nominal, inflation=0.0), nominal)


@given(values=st.lists(index_values, min_size=1, max_size=24), split=st.integers(min_value=0))
def test_chaining_a_window_is_chaining_its_halves_and_compounding(
    values: list[float], split: int
) -> None:
    """The monoid property, and the reason a sum is wrong.

    ``(1 + whole) == (1 + left) * (1 + right)`` for every split point. A summing
    implementation satisfies this too -- which is why it is not the only property here -- but
    an implementation that lost the association would produce an answer depending on how the
    months were grouped, and no example would ever show it.
    """
    at = split % (len(values) + 1)
    months = cpi_fixtures.run_of("2026-01", len(values), 100.0)
    observations = tuple(
        cpi_fixtures.observation(period, value)
        for (period, _), value in zip(months, values, strict=True)
    )

    whole = cpi.cumulative_inflation(observations)
    left = cpi.cumulative_inflation(observations[:at])
    right = cpi.cumulative_inflation(observations[at:])

    assert is_close(1.0 + whole, (1.0 + left) * (1.0 + right))


@given(value=index_values, count=st.integers(min_value=1, max_value=12))
def test_a_run_of_equal_months_chains_to_a_power_and_never_to_a_multiple(
    value: float, count: int
) -> None:
    """The product, asserted as a power -- and asserted *not* to be the sum, wherever they differ.

    The ``assume`` is what keeps the second half honest: at exactly 100.0 the sum and the
    product agree at zero, so that one input would make the falsifier vacuous.
    """
    observations = tuple(
        cpi_fixtures.observation(period, value)
        for period, _ in cpi_fixtures.run_of("2026-01", count, value)
    )
    factor = value / 100.0

    cumulative = cpi.cumulative_inflation(observations)
    assert is_close(1.0 + cumulative, factor**count)

    assume(count > 1 and abs(factor - 1.0) > 0.01)
    assert not is_close(cumulative, count * (factor - 1.0))


@given(
    monthly=st.floats(min_value=0.9, max_value=1.2, allow_nan=False, allow_infinity=False),
    months=st.integers(min_value=1, max_value=120),
)
def test_annualising_a_window_recovers_the_rate_its_months_were_running_at(
    monthly: float, months: int
) -> None:
    """A window of months all growing at one rate annualises to that rate compounded twelve times.

    Stated forwards -- from a known monthly factor to a known annual one -- rather than as a
    round trip through ``(1 + annual) ** (months / 12)``. The round trip is algebraically the
    same claim and numerically a worse test: at a single month of severe deflation the
    annualised figure sits within a hair of -1, ``1 + annual`` then holds only a handful of
    significant digits, and the assertion would be measuring float64's resolution rather than
    the exponent.

    A wrong exponent -- 12/n inverted, or n counted off by one -- fails this for every window
    that is not exactly a year, which is the case a twelve-month example cannot see. The
    generated factors are a realistic month: 10% off to 20% on.
    """
    cumulative = monthly**months - 1.0

    annual = cpi.annualised(cumulative, periods=months, per_year=12)

    assert is_close(annual, monthly**12 - 1.0)


@given(
    values=st.lists(index_values, min_size=0, max_size=18),
    first_offset=st.integers(min_value=0, max_value=24),
    length=st.integers(min_value=0, max_value=24),
)
def test_coverage_is_total_and_a_covered_window_holds_one_observation_per_month(
    values: list[float], first_offset: int, length: int
) -> None:
    """Exactly one union member, always, and no partial answers hiding in the covered one."""
    declared = cpi_fixtures.series(
        [
            (period, value)
            for (period, _), value in zip(
                cpi_fixtures.run_of("2026-01", len(values), 100.0), values, strict=True
            )
        ]
    )
    first = "2026-01"
    for _ in range(first_offset):
        first = periods.next_month(first)
    last = first
    for _ in range(length):
        last = periods.next_month(last)
    window = cpi_fixtures.window(first, last)

    result = cpi.coverage(declared, window)

    match result:
        case cpi.Covered():
            assert tuple(item.period for item in result.observations) == periods.months_in(window)
        case cpi.NotCovered():
            assert set(result.missing) <= set(periods.months_in(window))
