"""What a scheme charge does when it cannot answer: refuse, by name, with nothing to read.

Two refusals, and they are two because the remedies are different. A **component** whose
schedule does not reach the date needs a citation for the older rate (FR-008, 006 FR-012).
A **base** that cannot be struck needs a declared observation or a declared rule (FR-011,
011 FR-010). Neither is a zero, and neither is a charge with a line quietly absent.

US3's whole point is that the three claims *"the schedule does not reach this date"*,
*"the rate was nil"* and *"this scheme charges no such component"* are different, so the
straddle below asserts that the uncharged side is the first of them.
"""

from __future__ import annotations

from datetime import date

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.tax import scheme as schemes
from terezy.core.tax.official_rate import (
    OfficialRateSeries,
    OfficialRateSeriesUnavailable,
    OfficialRateUndeclaredOnDate,
)
from tests import official_rates
from tests import schemes as fixtures

COMMENCEMENT = date(2025, 1, 1)
BEFORE = date(2024, 12, 15)
AFTER = date(2025, 1, 15)
RATE = 41.00
DOLLARS = Money(1_000.00, Currency.USD, prov.EMPTY)
HRYVNIA = Money(1_000.00, Currency.UAH, prov.EMPTY)


def _scheme() -> schemes.TaxationScheme:
    return fixtures.scheme(
        rate_components=[fixtures.rate_component([(COMMENCEMENT, 0.01)], component_id="levy")]
    )


def _straddling_series() -> OfficialRateSeries:
    return official_rates.series([(BEFORE, RATE), (AFTER, RATE)])


class TestAProjectionStraddlingTheCommencementDate:
    """US3, SC-003: one run, one month charged and one month refused, and neither is a zero."""

    def test_the_month_the_schedule_reaches_is_charged_at_the_declared_rate(self) -> None:
        charge = schemes.charge_income(
            _scheme(), DOLLARS, on_date=AFTER, series=_straddling_series()
        )
        assert isinstance(charge, schemes.SchemeCharge), charge
        assert [line.rate for line in charge.lines] == [0.01]

    def test_the_month_before_it_refuses_naming_the_component_and_the_date(self) -> None:
        refusal = schemes.charge_income(
            _scheme(), DOLLARS, on_date=BEFORE, series=_straddling_series()
        )
        assert isinstance(refusal, schemes.ComponentRateUndeclaredBefore), refusal
        assert refusal.component_id == "levy"
        assert refusal.on_date == BEFORE
        assert refusal.earliest_declared == COMMENCEMENT
        assert "does not reach" in refusal.reason

    def test_the_refusal_carries_no_rate_and_no_charge_to_read(self) -> None:
        """A caller cannot read a defaulted number off a refusal, because there is none on it."""
        refusal = schemes.charge_income(
            _scheme(), DOLLARS, on_date=BEFORE, series=_straddling_series()
        )
        fields = {name for name in dir(refusal) if not name.startswith("_")}
        assert not fields & {"rate", "charged", "total", "lines", "base"}


class TestTheBaseCannotBeStruck:
    """FR-011 and US1 scenario 3: 011's refusal, carried whole and not restated."""

    def test_a_date_the_series_does_not_declare_names_the_series_the_pair_and_the_date(
        self,
    ) -> None:
        refusal = schemes.charge_income(
            _scheme(),
            DOLLARS,
            on_date=AFTER,
            series=official_rates.series([(date(2025, 1, 14), RATE)]),
        )
        assert isinstance(refusal, schemes.TaxBaseUnavailable), refusal
        undeclared = refusal.unavailable
        assert isinstance(undeclared, OfficialRateUndeclaredOnDate), undeclared
        assert undeclared.on_date == AFTER
        assert undeclared.pair == (Currency.UAH, Currency.USD)
        assert undeclared.covers == (date(2025, 1, 14), date(2025, 1, 14))

    def test_a_jurisdiction_that_declared_no_series_says_so_rather_than_naming_one(self) -> None:
        refusal = schemes.charge_income(_scheme(), DOLLARS, on_date=AFTER, series=None)
        assert isinstance(refusal, schemes.TaxBaseUnavailable), refusal
        unavailable = refusal.unavailable
        assert isinstance(unavailable, OfficialRateSeriesUnavailable), unavailable
        assert unavailable.series_id is None
        assert unavailable.wanted == (Currency.UAH, Currency.USD)

    def test_a_series_quoting_another_pair_names_it_rather_than_saying_none_was_given(
        self,
    ) -> None:
        """The two ``OfficialRateSeriesUnavailable`` cases are different situations.

        *No series was supplied* and *the supplied series quotes the other direction* close
        differently, and the second is the one that gets misreported: a refusal saying nothing
        was supplied, over a series that was, sends the reader to declare what they already
        have. Asserting only the union member cannot tell them apart, because both branches
        return it.
        """
        refusal = schemes.charge_income(
            _scheme(),
            DOLLARS,
            on_date=AFTER,
            series=official_rates.series(
                [(AFTER, RATE)], pair=(Currency.USD, Currency.UAH), series_id="synthetic_inverse"
            ),
        )
        assert isinstance(refusal, schemes.TaxBaseUnavailable), refusal
        unavailable = refusal.unavailable
        assert isinstance(unavailable, OfficialRateSeriesUnavailable), unavailable
        assert unavailable.series_id == "synthetic_inverse"
        assert unavailable.quotes == (Currency.USD, Currency.UAH)
        assert unavailable.wanted == (Currency.UAH, Currency.USD)
        assert "none is inverted" in unavailable.reason

    def test_the_component_schedule_is_checked_before_the_rate_is_looked_up(self) -> None:
        """A date neither the schedule nor the series reaches names the schedule.

        Both are true and only one is the reader's next move: a rate for a date the law did
        not charge on is a value nobody needs to go and find.
        """
        refusal = schemes.charge_income(_scheme(), DOLLARS, on_date=BEFORE, series=None)
        assert isinstance(refusal, schemes.ComponentRateUndeclaredBefore), refusal


class TestAnArrivalInTheTaxCurrencyIsNeverRefusedForWantOfARate:
    """011 FR-009. The currency is checked before a series is, and it has to be.

    ``strike_base`` **raises** on an amount that needs no rate, so the check is not an
    optimisation: without it a hryvnia arrival under a jurisdiction that declares no series
    would come back refused for want of a rate it never needed -- and a false refusal trains
    a reader to ignore the true ones.
    """

    def test_a_hryvnia_arrival_is_charged_with_no_series_at_all(self) -> None:
        charge = schemes.charge_income(_scheme(), HRYVNIA, on_date=AFTER, series=None)
        assert isinstance(charge, schemes.SchemeCharge), charge
        assert charge.conversion is None
        assert charge.base.amount == HRYVNIA.amount

    def test_it_is_charged_even_where_a_series_is_supplied_and_covers_nothing(self) -> None:
        charge = schemes.charge_income(
            _scheme(), HRYVNIA, on_date=AFTER, series=official_rates.series([])
        )
        assert isinstance(charge, schemes.SchemeCharge), charge
        assert charge.conversion is None

    def test_a_hryvnia_arrival_before_the_commencement_still_refuses_by_component(self) -> None:
        refusal = schemes.charge_income(_scheme(), HRYVNIA, on_date=BEFORE, series=None)
        assert isinstance(refusal, schemes.ComponentRateUndeclaredBefore), refusal
