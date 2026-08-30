"""What a taxation scheme charges on one month's foreign income, worked out on paper.

SC-001 and SC-016. The amounts, the rates and the official rate are **synthetic and stated
here**, following 001, 006 and 007: this checks the engine's arithmetic, not Ukrainian tax
law. The shipped rates carry their citations in ``data/tax/schemes/`` and the values there
are the owner's to verify.

The whole point of the example is that both charges rest on **one hryvnia base struck at the
credit date**, and that the base is a different number from anything a channel would produce.
"""

from __future__ import annotations

import dataclasses
import inspect
from datetime import date

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close
from terezy.core.tax import scheme as schemes
from terezy.core.tax.official_rate import OfficialRateSeries, TaxCurrencyConversion
from tests import official_rates
from tests import schemes as fixtures

CREDIT_DATE = date(2027, 3, 15)
"""The date the dollars land. Everything below is struck on it and on nothing else."""

CREDITED = 2_500.00
"""Dollars credited. SYNTHETIC -- the owner's real monthly figure is unstated (§11 item 3)."""

OFFICIAL_RATE = 42.50
"""SYNTHETIC hryvnia per one dollar on the credit date. Not a rate the NBU published."""

TURNOVER_RATE = 0.05
LEVY_RATE = 0.01

BASE = 106_250.00
"""2_500.00 USD x 42.50 UAH/USD = 106_250.00 UAH."""

TURNOVER_CHARGE = 5_312.50
"""106_250.00 x 0.05 = 5_312.50 UAH."""

LEVY_CHARGE = 1_062.50
"""106_250.00 x 0.01 = 1_062.50 UAH."""

TOTAL = 6_375.00
"""5_312.50 + 1_062.50 = 6_375.00 UAH. A sum of two lines, never a blended 6% of the base."""

SCHEDULE_START = date(2025, 1, 1)


def _scheme() -> schemes.TaxationScheme:
    return fixtures.scheme(
        rate_components=[
            fixtures.rate_component(
                [(SCHEDULE_START, TURNOVER_RATE)],
                component_id="turnover_tax",
                name="SYNTHETIC податок з обороту",
            ),
            fixtures.rate_component(
                [(SCHEDULE_START, LEVY_RATE)],
                component_id="levy",
                name="SYNTHETIC збір",
            ),
        ]
    )


def _series() -> OfficialRateSeries:
    return official_rates.series([(CREDIT_DATE, OFFICIAL_RATE)])


def _charged() -> schemes.SchemeCharge:
    charge = schemes.charge_income(
        _scheme(),
        Money(CREDITED, Currency.USD, prov.EMPTY),
        on_date=CREDIT_DATE,
        series=_series(),
    )
    assert isinstance(charge, schemes.SchemeCharge), charge
    return charge


class TestTheBaseIsTheCreditedAmountAtTheCreditDatesRate:
    """FR-011. The base is struck once, from the event's own amount and the event's own date."""

    def test_the_hryvnia_base_matches_the_hand_computed_product(self) -> None:
        assert_money_close(_charged().base, Money(BASE, Currency.UAH, prov.EMPTY))

    def test_the_conversion_carries_every_term_of_the_arithmetic(self) -> None:
        """A hryvnia figure gives no hint of which dollars and which date produced it."""
        conversion = _charged().conversion
        assert isinstance(conversion, TaxCurrencyConversion), conversion
        assert conversion.amount.amount == CREDITED
        assert conversion.amount.currency is Currency.USD
        assert conversion.event_date == CREDIT_DATE
        assert conversion.rate_date == CREDIT_DATE
        assert conversion.rate == OFFICIAL_RATE
        assert conversion.quotation_unit == 1.0
        assert conversion.applied_rule is None

    def test_the_charge_names_the_date_its_rates_were_read_on(self) -> None:
        assert _charged().on_date == CREDIT_DATE


class TestBothComponentsAreChargedOnThatOneBase:
    """FR-005 and FR-006: two lines, each under the name the law uses, never one percentage."""

    @pytest.mark.parametrize(
        ("component_id", "expected", "rate"),
        [("turnover_tax", TURNOVER_CHARGE, TURNOVER_RATE), ("levy", LEVY_CHARGE, LEVY_RATE)],
    )
    def test_each_line_matches_its_hand_computed_product(
        self, component_id: str, expected: float, rate: float
    ) -> None:
        line = next(item for item in _charged().lines if item.component_id == component_id)
        assert_money_close(line.charged, Money(expected, Currency.UAH, prov.EMPTY))
        assert line.rate == rate
        assert line.effective_from == SCHEDULE_START

    def test_every_line_reports_the_name_the_law_uses(self) -> None:
        assert [item.name for item in _charged().lines] == [
            "SYNTHETIC податок з обороту",
            "SYNTHETIC збір",
        ]

    def test_the_total_is_the_sum_of_the_lines_and_not_a_blended_rate(self) -> None:
        """``6%`` of the base is the same number and a different claim, so it is not computed."""
        charge = _charged()
        assert_money_close(charge.total, Money(TOTAL, Currency.UAH, prov.EMPTY))
        assert len(charge.lines) == 2

    def test_each_line_carries_the_provenance_of_the_entry_that_produced_it(self) -> None:
        """FR-003: the mark reaches the figure, not only the record it was read from."""
        for line in _charged().lines:
            assert prov.is_unverified(line.charged.provenance), line.component_id
            assert line.provenance.sources <= line.charged.provenance.sources


class TestAnArrivalAlreadyInTheTaxCurrencyConsultsNoRate:
    """011 FR-009, and the Edge Case *a stream in the tax currency naming this regime*."""

    def test_it_is_charged_on_its_own_amount_with_no_conversion(self) -> None:
        charge = schemes.charge_income(
            _scheme(),
            Money(BASE, Currency.UAH, prov.EMPTY),
            on_date=CREDIT_DATE,
            series=None,
        )
        assert isinstance(charge, schemes.SchemeCharge), charge
        assert charge.conversion is None
        assert_money_close(charge.base, Money(BASE, Currency.UAH, prov.EMPTY))
        assert_money_close(charge.total, Money(TOTAL, Currency.UAH, prov.EMPTY))


class TestNothingIsDeductedFromTheBase:
    """FR-014 and SC-016: the base is the **whole** credited amount.

    For the bank commission this is answered at the INTERPRETED level -- practitioner
    guidance reads the income as the whole invoice amount including it, not the net received
    -- and that citation travels on the figure. Every other candidate deduction is an
    **absence, recorded** as an owner verification task: a modelled zero deduction and an
    unasked question are different claims, and only one of them is what this makes.
    """

    def test_the_base_is_the_credited_amount_at_the_rate_and_nothing_less(self) -> None:
        assert _charged().base.amount == CREDITED * OFFICIAL_RATE

    def test_there_is_no_deduction_to_apply_and_nowhere_to_put_one(self) -> None:
        """Structural, because a deduction nobody cited must be unrepresentable rather than
        merely not applied."""
        names = {field.name for field in dataclasses.fields(schemes.SchemeCharge)}
        assert not names & {"deduction", "deductions", "allowance", "expenses", "net", "gross"}
        parameters = set(inspect.signature(schemes.charge_income).parameters)
        assert parameters == {"scheme", "amount", "on_date", "series"}
