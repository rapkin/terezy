"""A dollar credit's hryvnia base at the National Bank's own published rate, worked by hand.

018 SC-001 and SC-002. This is the first module in the repository whose arithmetic runs over
**real** official rates rather than invented ones, and it is where 012's ФОП-against-personal-
income comparison stops being a thing the specification describes and becomes a number.

## No rate is written down here

Every value comes out of ``data/official_rates/ua_nbu_usd.toml`` at the moment the test runs.
A rate restated as a literal in a test is a rate with no citation the moment the file moves --
the publisher restates a past date's value and the literal keeps its own -- so what is checked
in is the **arithmetic over** the declared rate, not the rate (spec.md, Assumptions).

## Claim 1 -- the base is the credited amount at that date's rate

A credit of **1 000.00 USD**, so the multiplication is one a reader checks by moving a decimal
point three places::

    base = 1 000.00 x R(credit date) / quotation_unit

where ``R`` is what the declaration carries for that date and ``quotation_unit`` is 1.0. An
implementation that ignored the unit, inverted the pair, or reached for a neighbouring date's
value produces a different number, and each of those is asserted against separately below.

## Claim 2 -- the date is load-bearing

The same 1 000.00 USD on the next day strikes a base that differs by exactly the declared rate
difference times the amount::

    base(day + 1) - base(day) = (R(day + 1) - R(day)) x 1 000.00

## Claim 3 -- two schemes, one base

The credit is charged under **ФОП group 3, non-VAT** and under the **personal-income** reading.
Each scheme's total is the sum of its own lines and never a combined rate applied once, and
both rest on the *same* hryvnia base -- bit-for-bit, not within a tolerance, because the base
is not computed twice from two roundings but struck from one rate on one date.

The state this replaced is kept executable rather than described:
``test_the_same_comparison_against_a_series_with_no_observations_refuses``.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.tax import official_rate
from terezy.core.tax import scheme as schemes
from terezy.core.tax.official_rate import OfficialRateSeries
from terezy.data.declarations import resolver

pytestmark = pytest.mark.worked_example

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"

CREDIT_DATE = date(2026, 3, 2)
"""Inside the covered window and after every rate entry both schemes declare comes into force.
Nothing distinguishes it otherwise: any covered date would do, and one is named so the
arithmetic below is about a single, checkable day."""

CREDITED = 1_000.00
"""Dollars credited. Round on purpose: the product is then the rate with its decimal point
moved three places, which is what makes the assertion checkable by eye."""

FOP = "ua_fop_group_3_non_vat"
PERSONAL = "ua_personal_income"

UAH = Currency.UAH
USD = Currency.USD


def _declared() -> resolver.SchemeDeclarations:
    return resolver.schemes_from_data_root(DATA_ROOT, base_currency=UAH)


def _series() -> OfficialRateSeries:
    series = _declared().official_rates["ua"]
    assert series is not None, "the Ukrainian rules declare the series this module is about"
    return series


def _declared_rate(on_date: date) -> float:
    """What the file says for one date, read out rather than remembered."""
    found = official_rate.observation_for(_series(), on_date)
    assert found is not None, f"{on_date.isoformat()} is outside the covered window"
    return found[0].value


def _struck(on_date: date = CREDIT_DATE) -> official_rate.TaxCurrencyConversion:
    outcome = official_rate.strike_base(
        Money(CREDITED, USD, prov.EMPTY), _series(), tax_currency=UAH, on_date=on_date
    )
    assert isinstance(outcome, official_rate.TaxCurrencyConversion), outcome
    return outcome


def _charged(scheme_id: str, *, series: OfficialRateSeries | None = None) -> object:
    return schemes.charge_income(
        _declared().schemes[scheme_id],
        Money(CREDITED, USD, prov.EMPTY),
        on_date=CREDIT_DATE,
        series=_series() if series is None else series,
    )


class TestTheBaseIsTheCreditedAmountAtThatDatesPublishedRate:
    def test_the_base_matches_the_product_of_the_amount_and_the_declared_rate(self) -> None:
        """1 000.00 x R / 1.0, with R read off the declaration."""
        rate = _declared_rate(CREDIT_DATE)
        struck = _struck()

        assert struck.base.currency is UAH
        assert is_close(struck.base.amount, CREDITED * rate / 1.0)
        assert is_close(struck.base.amount, rate * 1_000.0)

    def test_the_conversion_reports_every_term_of_the_arithmetic(self) -> None:
        """A hryvnia figure gives no hint of which dollars and which date produced it."""
        struck = _struck()

        assert struck.series_id == "ua_nbu_usd"
        assert struck.pair == (UAH, USD)
        assert struck.event_date == CREDIT_DATE
        assert struck.rate_date == CREDIT_DATE
        assert struck.applied_rule is None
        assert struck.quotation_unit == 1.0
        assert is_close(struck.rate, _declared_rate(CREDIT_DATE))

    def test_the_quotation_unit_is_applied_and_the_pair_is_not_inverted(self) -> None:
        """The two ways to be wrong by orders of magnitude while looking plausible.

        A hryvnia base for a dollar credit is a number of thousands, not of tens and not of
        hundreds of thousands -- and the bound is expressed against the declared rate rather
        than against a remembered exchange rate.
        """
        rate = _declared_rate(CREDIT_DATE)
        struck = _struck()

        assert not is_close(struck.base.amount, CREDITED / rate)
        assert not is_close(struck.base.amount, CREDITED * rate / 100.0)
        assert not is_close(struck.base.amount, CREDITED * rate * 100.0)

    def test_the_mark_reaches_the_base_because_nobody_has_verified_the_observation(
        self,
    ) -> None:
        """SC-008. Every ``verified_on`` the fetch script writes is empty, so every figure
        struck through one renders marked -- which is the true description of the data."""
        assert prov.is_unverified(_struck().base.provenance)


class TestTheDateIsLoadBearing:
    def test_the_next_days_base_differs_by_the_declared_rate_difference(self) -> None:
        """Checked against hand arithmetic on the two declared rates, not against the
        engine's other answer -- which would agree with itself whatever it did."""
        following = CREDIT_DATE + timedelta(days=1)
        moved = _declared_rate(following) - _declared_rate(CREDIT_DATE)
        assert moved != 0.0, "this claim needs two days the publisher priced differently"

        assert is_close(_struck(following).base.amount - _struck().base.amount, moved * CREDITED)

    def test_a_date_before_the_window_refuses_naming_the_window(self) -> None:
        outside = _series().observations[0].on_date - timedelta(days=1)

        outcome = official_rate.strike_base(
            Money(CREDITED, USD, prov.EMPTY), _series(), tax_currency=UAH, on_date=outside
        )

        assert isinstance(outcome, official_rate.OfficialRateUndeclaredOnDate), outcome
        assert outcome.covers is not None


class TestOneDollarCreditUnderTwoSchemes:
    """SC-002, and the comparison 012 declares, on a real dollar amount for the first time."""

    def test_both_schemes_charge_on_one_hryvnia_base(self) -> None:
        fop = _charged(FOP)
        personal = _charged(PERSONAL)
        assert isinstance(fop, schemes.SchemeCharge), fop
        assert isinstance(personal, schemes.SchemeCharge), personal

        # Bit-for-bit rather than within the tolerance: this is not two computations agreeing,
        # it is one rate on one date reaching both charges.
        assert fop.base.amount.hex() == personal.base.amount.hex()
        assert is_close(fop.base.amount, _declared_rate(CREDIT_DATE) * CREDITED)

    @pytest.mark.parametrize("scheme_id", [FOP, PERSONAL])
    def test_each_total_is_the_sum_of_its_lines_and_never_a_combined_rate(
        self, scheme_id: str
    ) -> None:
        charge = _charged(scheme_id)
        assert isinstance(charge, schemes.SchemeCharge), charge

        by_hand = sum(charge.base.amount * line.rate for line in charge.lines)

        assert len(charge.lines) > 1, "a sum of one line would assert nothing about blending"
        assert is_close(charge.total.amount, by_hand)
        assert not hasattr(charge, "combined_rate")

    def test_the_two_totals_differ_by_the_base_times_the_difference_of_the_rates(self) -> None:
        """The comparison itself, stated as arithmetic over the declared rates so it cannot
        pass by both sides being computed the same wrong way."""
        fop = _charged(FOP)
        personal = _charged(PERSONAL)
        assert isinstance(fop, schemes.SchemeCharge), fop
        assert isinstance(personal, schemes.SchemeCharge), personal

        gap = sum(line.rate for line in personal.lines) - sum(line.rate for line in fop.lines)
        assert gap > 0.0, "the personal-income reading is the dearer of the two"

        assert is_close(personal.total.amount - fop.total.amount, fop.base.amount * gap)

    def test_the_same_comparison_against_a_series_with_no_observations_refuses(self) -> None:
        """What the shipped data produced until this feature landed.

        The refusal is what made the comparison unanswerable: not badly answered, not
        approximately answered -- not produced at all.
        """
        empty = OfficialRateSeries(
            id="ua_nbu_usd",
            authority=_series().authority,
            pair=_series().pair,
            quotation_unit=_series().quotation_unit,
            rule=None,
            observations=(),
        )

        for scheme_id in (FOP, PERSONAL):
            refused = _charged(scheme_id, series=empty)
            assert isinstance(refused, schemes.TaxBaseUnavailable), refused
