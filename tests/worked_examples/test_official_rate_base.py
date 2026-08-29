"""The hryvnia tax base of a dollar amount, worked out by hand.

SC-001, SC-002 and SC-012, and every figure below is arithmetic a reader can check on
paper. **Nothing here is a rate anybody published**: the values are invented and say so in
their own citations, because the examples test the conversion, not the hryvnia
(spec.md, Assumptions).

## Claim 1 -- the base is the amount at *that date's* declared rate

A series quoting hryvnia per dollar, one rate per date::

    2026-03-02   41.50 UAH per 1 USD
    2026-03-03   42.25 UAH per 1 USD

A receipt of 1 200.00 USD on 2026-03-02::

    1200.00 x 41.50 = 49 800.00 UAH

## Claim 2 -- the date is load-bearing, not decorative

The same 1 200.00 USD a day later::

    1200.00 x 42.25 = 50 700.00 UAH

and the difference is exactly the declared rate difference times the amount, which is the
half of SC-002 that a test comparing the engine against its own other answer would miss::

    (42.25 - 41.50) x 1200.00 = 0.75 x 1200.00 = 900.00 UAH
    50 700.00 - 49 800.00                      = 900.00 UAH

## Claim 3 -- a quotation unit other than one is applied, and appears in the output

A published table that quotes some currencies per 1 unit and others per 100 is normal, and
a value read at the wrong unit is wrong by two orders of magnitude while looking entirely
plausible (FR-002). A synthetic series quoting **4 150.00 hryvnia per 100 dollars** is the
same rate as claim 1's, and 1 200.00 USD must strike the same base::

    1200.00 x 4150.00 / 100 = 1200.00 x 41.50 = 49 800.00 UAH

An implementation that ignored the unit would produce 4 980 000.00 UAH -- a hundred times
the answer, and not a near miss.

Every comparison uses the single imported project tolerance. Nothing here defines its own.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.tax import official_rate
from tests import official_rates

pytestmark = pytest.mark.worked_example

FIRST = date(2026, 3, 2)
SECOND = date(2026, 3, 3)

RATE_FIRST = 41.50
RATE_SECOND = 42.25
"""Invented. See the module docstring: these are not published rates."""

AMOUNT = Money(1200.00, Currency.USD, prov.EMPTY)
"""A literal that came from nowhere, so ``EMPTY`` is the honest provenance for it: the
sources under test are the *rate's*, and the propagation checks live in
``tests/contract/test_official_rate_marks.py``."""


def _struck(on_date: date, *, quotation_unit: float = 1.0) -> official_rate.TaxCurrencyConversion:
    """The base struck on one date, or a failure naming what came back instead."""
    scale = quotation_unit
    declared = official_rates.series(
        [(FIRST, RATE_FIRST * scale), (SECOND, RATE_SECOND * scale)],
        quotation_unit=quotation_unit,
    )
    struck = official_rate.strike_base(AMOUNT, declared, tax_currency=Currency.UAH, on_date=on_date)
    assert isinstance(struck, official_rate.TaxCurrencyConversion), struck
    return struck


def test_a_dollar_receipt_strikes_the_hand_computed_hryvnia_base() -> None:
    """1200.00 x 41.50 = 49 800.00 UAH, on the event's own date."""
    struck = _struck(FIRST)

    assert struck.base.currency is Currency.UAH
    assert is_close(struck.base.amount, 49_800.00)
    assert is_close(1200.00 * 41.50, 49_800.00)


def test_the_same_amount_on_two_dates_differs_by_the_declared_rate_difference() -> None:
    """SC-002, checked against hand arithmetic rather than against the engine's other answer."""
    first = _struck(FIRST)
    second = _struck(SECOND)

    assert is_close(first.base.amount, 49_800.00)
    assert is_close(second.base.amount, 50_700.00)
    assert is_close(second.base.amount - first.base.amount, 900.00)
    assert is_close((RATE_SECOND - RATE_FIRST) * AMOUNT.amount, 900.00)


def test_the_conversion_reports_enough_to_re_derive_the_base_on_paper() -> None:
    """FR-016: the series, the observation date, the rate and the quotation unit."""
    struck = _struck(FIRST)

    assert struck.series_id == "synthetic_official_usd"
    assert struck.pair == (Currency.UAH, Currency.USD)
    assert struck.event_date == FIRST
    assert struck.rate_date == FIRST
    assert struck.applied_rule is None
    assert is_close(struck.rate, RATE_FIRST)
    assert is_close(struck.quotation_unit, 1.0)
    assert is_close(struck.amount.amount * struck.rate / struck.quotation_unit, 49_800.00)


def test_a_rate_quoted_per_a_hundred_units_strikes_the_same_base() -> None:
    """SC-012: 4150.00 per 100 is 41.50 per 1, and ignoring the unit is wrong by 100x."""
    struck = _struck(FIRST, quotation_unit=100.0)

    assert is_close(struck.rate, 4150.00)
    assert is_close(struck.quotation_unit, 100.0)
    assert is_close(struck.base.amount, 49_800.00)
    assert not is_close(struck.base.amount, 4_980_000.00)
