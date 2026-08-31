"""The landed Ukrainian series, checked over every row rather than sampled.

018 SC-003, SC-006, SC-017, SC-019 and SC-020. A file of a few thousand plausible rates that
nobody can reproduce from a cited source is exactly the artefact Principle I exists to refuse,
so what is asserted here is **completeness of the citation and of the calendar**, mechanically,
on 100% of the observations.

**Nothing here restates a rate.** Every bound, count and value comes out of the declaration at
the moment the test runs; the one literal is the lower bound, which is a fact about the
*publisher* -- the date it moved USD from a quote per 100 units to a quote per 1 -- and not a
rate.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.tax import official_rate
from terezy.core.tax.official_rate import OfficialRateSeries
from terezy.data.declarations import loader, resolver

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
SHIPPED = DATA_ROOT / "official_rates" / "ua_nbu_usd.toml"

FIRST_QUOTED_PER_ONE_UNIT = date(2019, 12, 28)
"""The first date the publisher quotes USD per one unit, retrieved at source on 2026-08-31.

Why that is the series' lower bound rather than a preference is argued where a declarer meets
it, in the file's own generated header.
"""

ENDPOINT = "https://bank.gov.ua/NBU_Exchange/exchange_site"

A_UNITS_MIXUP = 10.0
"""A day-over-day ratio no currency pair moves by, and exactly what reading a per-100 quote as
per-1 would produce. The canary is against the failure the unit refusal exists to prevent, so
it is a ratio rather than a range: a range would be a remembered claim about the hryvnia."""


def _series() -> OfficialRateSeries:
    return loader.official_rate_from_file(SHIPPED)


@pytest.fixture(scope="module")
def series() -> OfficialRateSeries:
    return _series()


class TestTheCalendarIsComplete:
    """SC-017. The National Bank returns a rate for every calendar day, dated that day."""

    def test_one_observation_per_calendar_day_with_none_missing(
        self, series: OfficialRateSeries
    ) -> None:
        """Counted, not read. A hole would refuse under a message naming the series, which
        would blame the publisher for a failed fetch."""
        first, last = series.observations[0].on_date, series.observations[-1].on_date

        assert len(series.observations) == (last - first).days + 1

    def test_the_dates_run_forward_without_a_repeat(self, series: OfficialRateSeries) -> None:
        dates = [observation.on_date for observation in series.observations]

        assert dates == sorted(dates)
        assert len(set(dates)) == len(dates)

    def test_no_non_publication_day_rule_is_declared(self, series: OfficialRateSeries) -> None:
        """Where the publisher publishes for every date, there is no date for a rule to speak
        about -- and nothing here derives a weekend's rate, it is retrieved against that day."""
        assert series.rule is None

    def test_the_series_begins_where_the_publisher_changed_its_unit(
        self, series: OfficialRateSeries
    ) -> None:
        assert series.observations[0].on_date == FIRST_QUOTED_PER_ONE_UNIT
        assert series.quotation_unit == 1.0


class TestEveryObservationCarriesItsProvenance:
    """SC-006 and SC-019, on 100% of the rows rather than on a sample of them."""

    def test_every_citation_names_the_endpoint_its_query_the_unit_and_the_calcdate(
        self, series: OfficialRateSeries
    ) -> None:
        for observation in series.observations:
            (source,) = observation.provenance.sources
            assert ENDPOINT in source.citation, observation.on_date
            assert "valcode=usd" in source.citation, observation.on_date
            assert "units = 1;" in source.citation, observation.on_date
            assert "calcdate = " in source.citation, observation.on_date

    def test_every_observation_was_retrieved_and_none_of_them_verified(
        self, series: OfficialRateSeries
    ) -> None:
        """FR-005. A downloaded number is not a checked number, and the file says so on every
        row until the owner checks one against the publisher himself."""
        for observation in series.observations:
            (source,) = observation.provenance.sources
            assert source.retrieved_on is not None, observation.on_date
            assert source.verified_on is None, observation.on_date
            assert source.kind == "official_rate", observation.on_date

    def test_no_observation_is_dated_after_the_day_it_was_read(
        self, series: OfficialRateSeries
    ) -> None:
        """SC-020. The publisher offers tomorrow's rate today; a file that wrote it would not
        load at all, and the fetch script declines it rather than finding that out."""
        for observation in series.observations:
            (source,) = observation.provenance.sources
            assert source.retrieved_on is not None
            assert observation.on_date <= source.retrieved_on

    def test_no_pair_of_neighbouring_days_differs_by_an_order_of_magnitude(
        self, series: OfficialRateSeries
    ) -> None:
        """The unit refusal's canary in the landed data: a row read at the wrong unit sits a
        hundred times off its neighbours and looks entirely plausible on its own."""
        for before, after in zip(series.observations, series.observations[1:], strict=False):
            assert before.value > 0.0
            ratio = after.value / before.value
            assert 1 / A_UNITS_MIXUP < ratio < A_UNITS_MIXUP, (before.on_date, after.on_date)


class TestADateOutsideTheWindowRefusesByName:
    """SC-003. Populating a series is exactly the change that makes a refusal look like a bug."""

    @staticmethod
    def _uncovered(series: OfficialRateSeries) -> list[date]:
        """Both edges, and a date a declared instrument actually pays on.

        The last is read off the shipped funds rather than written down: a payment date
        restated here would go stale the day an instrument's terms move, and what the case is
        about is that a **projection** cannot have a tax base -- an official rate for a date
        that has not arrived is a forecast wearing an observation's clothes.
        """
        first, last = series.observations[0].on_date, series.observations[-1].on_date
        pays = max(fund.terminates_on for fund in resolver.from_data_root(DATA_ROOT).funds.values())
        assert pays > last, "the declared instruments must reach past the covered window"
        return [
            first - timedelta(days=1),
            first - timedelta(days=1_000),
            last + timedelta(days=1),
            last + timedelta(days=400),
            pays,
        ]

    def test_every_uncovered_date_refuses_naming_the_series_the_pair_and_the_window(
        self, series: OfficialRateSeries
    ) -> None:
        first, last = series.observations[0].on_date, series.observations[-1].on_date

        for wanted in self._uncovered(series):
            outcome = official_rate.strike_base(
                Money(1_000.0, Currency.USD, prov.EMPTY),
                series,
                tax_currency=Currency.UAH,
                on_date=wanted,
            )

            assert isinstance(outcome, official_rate.OfficialRateUndeclaredOnDate), wanted
            assert outcome.series_id == "ua_nbu_usd"
            assert outcome.pair == (Currency.UAH, Currency.USD)
            assert outcome.on_date == wanted
            assert outcome.covers == (first, last)

    def test_the_window_the_refusal_names_is_real_dates_and_not_an_empty_series(
        self, series: OfficialRateSeries
    ) -> None:
        """What changed: the shipped file used to say it declared no observation at all."""
        outcome = official_rate.strike_base(
            Money(1_000.0, Currency.USD, prov.EMPTY),
            series,
            tax_currency=Currency.UAH,
            on_date=self._uncovered(series)[0],
        )
        assert isinstance(outcome, official_rate.OfficialRateUndeclaredOnDate), outcome

        assert "declares no observation at all" not in outcome.reason
        assert series.observations[0].on_date.isoformat() in outcome.reason
        assert series.observations[-1].on_date.isoformat() in outcome.reason

    def test_nothing_in_the_lookup_carries_a_value_forward_to_an_uncovered_date(
        self, series: OfficialRateSeries
    ) -> None:
        """The four ways to produce a number that looks exactly like a correct number, refused
        as one claim: the lookup returns nothing, so there is no value to be carried."""
        for wanted in self._uncovered(series):
            assert official_rate.observation_for(series, wanted) is None
