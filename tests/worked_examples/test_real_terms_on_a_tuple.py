"""What one candidate returns in purchasing power, checked by hand (024 SC-001).

UA4000236228 over the owner's twelve-month horizon: 50 000 UAH from `salary_uah` through
`inzhur_direct`, out through `inzhur_to_monobank`, over the shipped root at `as_of` 2026-08-30.

| | |
| --- | --- |
| span | 2026-09-01 .. 2027-03-13 (the issue redeems 2027-03-10; three days settle) |
| deflation window | 2026-10 .. 2027-03 -- six months |
| nominal `implied_rate` | `0.14943820648570882` |
| declared belief | 10.0% per annum, `owner_placeholder_inflation` |

**The assumed half**, both rates per annum. The numerator is written as the sum it is computed
from, because the decimal literal `1.14943820648570882` is a *different* double from
`1 + 0.14943820648570882` and this check does not reproduce from it::

    1 + nominal = 1.149438206485709
    real        = 1.149438206485709 / 1.10 - 1 = 0.044943824077917194

Checkable by multiplying back: `1.10 * 1.044943824077917194 = 1.149438206485709`, the
numerator exactly.

**The realized half refuses**, because `data/cpi/ua.toml` covers 1991-08 .. 2025-10 and all six
months of this window are undeclared.

**And why the approximation is refused.** `0.14943820... - 0.10 = 0.04943820...`, which is
`1.10 x` the exact figure -- the approximation overstates the real return by exactly the
inflation rate, here 0.45 percentage points on a 4.49% figure, a tenth of the number itself.
Both look like plausible real returns, which is what makes the wrong one dangerous rather than
merely inaccurate.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.decision.answer import section_evaluated
from terezy.core.inflation.series import deflation_window
from terezy.core.primitives.periods import Window, months_in
from terezy.core.primitives.rates import NominalRate, RealRate, RealTermsUnavailable
from terezy.core.primitives.tolerance import TOLERANCE, is_close
from terezy.core.results.tuple import TupleOutcome
from tests import answer_registries as fixtures

pytestmark = pytest.mark.worked_example

INSTRUMENT = "UA4000236228"
TWELVE_MONTHS = 2
"""Index of the owner's longest declared horizon, 2026-09-01 .. 2027-09-01."""

SPAN_START = date(2026, 9, 1)
SPAN_END = date(2027, 3, 13)
WINDOW = Window(first="2026-10", last="2027-03")

NOMINAL = 0.14943820648570882
BELIEF = 1.10
NUMERATOR = 1 + NOMINAL
REAL = 0.044943824077917194

BELIEF_ID = "owner_placeholder_inflation"
SERIES_ID = "ua_cpi_monthly"


def _twelve_months() -> list[TupleOutcome]:
    result = fixtures.answered(supplied=fixtures.shipped_inputs())
    return list(section_evaluated(result.sections[TWELVE_MONTHS]))


def _outcome(instrument_id: str = INSTRUMENT) -> TupleOutcome:
    evaluated = _twelve_months()
    found = [item for item in evaluated if item.key.instrument_id == instrument_id]
    assert len(found) == 1, [item.key.instrument_id for item in evaluated]
    return found[0]


def test_the_span_and_the_nominal_rate_are_what_the_arithmetic_below_deflates() -> None:
    """Pinned first, because every figure after this is computed from these two."""
    outcome = _outcome()

    assert (outcome.span.start, outcome.span.end) == (SPAN_START, SPAN_END)
    assert isinstance(outcome.implied_rate, NominalRate)
    assert outcome.implied_rate.value == NOMINAL


def test_the_assumed_real_rate_is_the_nominal_one_deflated_by_the_declared_belief() -> None:
    """`(1 + 0.14943820648570882) / 1.10 - 1 = 0.044943824077917194`, at the imported tolerance."""
    figure = _outcome().real.assumed

    assert isinstance(figure, RealRate), figure
    assert is_close(figure.value, REAL)
    assert is_close(figure.value, NUMERATOR / BELIEF - 1.0)


def test_multiplying_the_real_rate_back_by_the_belief_returns_the_numerator() -> None:
    """The check a reader performs on paper: `1.10 * 1.044943824077917194 = 1.149438206485709`.

    It is the exact Fisher relation stated the other way round, so it fails on the subtraction
    approximation -- `1.10 * 1.04943820648570882` is `1.1543820271342797`, off in the third
    decimal place.
    """
    figure = _outcome().real.assumed

    assert isinstance(figure, RealRate)
    assert is_close(BELIEF * (1.0 + figure.value), NUMERATOR)


def test_the_subtraction_approximation_is_further_out_than_the_tolerance_admits() -> None:
    """4.944% against 4.494%: the gap is a tenth of the figure, and both look plausible."""
    figure = _outcome().real.assumed

    assert isinstance(figure, RealRate)
    assert not is_close(figure.value, NOMINAL - (BELIEF - 1.0))
    assert abs(figure.value - (NOMINAL - (BELIEF - 1.0))) > TOLERANCE


def test_the_assumed_figure_names_the_window_the_belief_and_that_it_is_an_assumption() -> None:
    """024 FR-006 and FR-010: what it is real against, over what, and on whose word."""
    figure = _outcome().real.assumed

    assert isinstance(figure, RealRate)
    assert figure.window == WINDOW
    assert months_in(figure.window) == (
        "2026-10",
        "2026-11",
        "2026-12",
        "2027-01",
        "2027-02",
        "2027-03",
    )
    assert figure.basis == "declared_assumption"
    assert figure.series_id == BELIEF_ID


def test_the_realized_half_names_the_six_months_the_series_does_not_declare() -> None:
    """024 FR-008. The series ends 2025-10, so every month of this window is undeclared."""
    figure = _outcome().real.realized

    assert isinstance(figure, RealTermsUnavailable), figure
    assert SERIES_ID in figure.reason
    for month in months_in(WINDOW):
        assert month in figure.reason


def test_each_realized_refusal_names_the_months_of_its_own_window() -> None:
    """024 SC-002: not one shared list -- a candidate maturing in 2027-03 and one running to
    2027-09 name different sets, and the twelve-month section produces at least three.

    The window is derived from each outcome's own span by the same function the figure used, so
    what is asserted is that the refusal follows the span rather than a set retyped here.
    """
    named: set[tuple[str, ...]] = set()
    for outcome in _twelve_months():
        figure = outcome.real.realized
        assert isinstance(figure, RealTermsUnavailable), outcome.key.instrument_id
        months = months_in(deflation_window(outcome.span.start, outcome.span.end))
        if not months:
            continue
        for month in months:
            assert month in figure.reason, (outcome.key.instrument_id, month)
        named.add(months)

    assert len(named) >= 3, sorted(named)
