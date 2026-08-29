"""A date with no declared rate refuses, and no configuration makes it return a number.

SC-003 and FR-010. The battery is deliberate: a gap in the middle of a declared run, a date
before the first observation, a date after the last, and a series that declares nothing at
all. All four are the same refusal in shape, because the engine cannot tell a weekend from a
gap and must not try (spec.md, Edge Cases).

One more refusal lives here because it is the same class of answer -- *no rate is inferred*
-- rather than because it is about a date: a series asked for a pair it does not quote.
``resolver._check_channel`` refuses to infer one pair from another for a channel, and
inverting a published quote is inferring.

⚙ ``Currency`` declares exactly two members, so "the series quotes a different pair" and
"the series quotes this pair the other way round" are the **same case** here and are tested
once. A third currency would separate them, and would not change the answer: neither is
inferred from the other.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.tax import official_rate
from tests import official_rates

MARCH_2 = date(2026, 3, 2)
MARCH_3 = date(2026, 3, 3)
MARCH_5 = date(2026, 3, 5)

DECLARED = [(MARCH_2, 41.50), (MARCH_3, 42.25), (MARCH_5, 42.75)]
"""A run with 2026-03-04 missing: the gap the middle case asks about. Invented values."""

AMOUNT = Money(100.0, Currency.USD, prov.EMPTY)


def _struck(on_date: date) -> object:
    return official_rate.strike_base(
        AMOUNT, official_rates.series(DECLARED), tax_currency=Currency.UAH, on_date=on_date
    )


class TestADateTheSeriesDoesNotCover:
    """Three uncovered dates, three refusals naming the series, the pair and the date."""

    def test_a_gap_in_the_middle_refuses(self) -> None:
        outcome = _struck(date(2026, 3, 4))

        assert isinstance(outcome, official_rate.OfficialRateUndeclaredOnDate), outcome
        assert outcome.series_id == "synthetic_official_usd"
        assert outcome.pair == (Currency.UAH, Currency.USD)
        assert outcome.on_date == date(2026, 3, 4)
        assert outcome.covers == (MARCH_2, MARCH_5)

    def test_a_date_before_the_first_observation_refuses(self) -> None:
        outcome = _struck(date(2026, 3, 1))

        assert isinstance(outcome, official_rate.OfficialRateUndeclaredOnDate), outcome
        assert outcome.on_date == date(2026, 3, 1)
        assert outcome.covers == (MARCH_2, MARCH_5)

    def test_a_date_after_the_last_observation_refuses(self) -> None:
        outcome = _struck(date(2026, 3, 6))

        assert isinstance(outcome, official_rate.OfficialRateUndeclaredOnDate), outcome
        assert outcome.on_date == date(2026, 3, 6)
        assert outcome.covers == (MARCH_2, MARCH_5)

    def test_a_series_with_no_observations_refuses_and_says_the_window_is_empty(self) -> None:
        """What the shipped Ukrainian series does, until the publisher's values are fetched."""
        outcome = official_rate.strike_base(
            AMOUNT,
            official_rates.series([]),
            tax_currency=Currency.UAH,
            on_date=MARCH_2,
        )

        assert isinstance(outcome, official_rate.OfficialRateUndeclaredOnDate), outcome
        assert outcome.covers is None


class TestNothingIsInvented:
    """Neither neighbour is borrowed, in either direction, and no number comes back."""

    def test_the_refusal_carries_no_value_a_caller_could_read(self) -> None:
        outcome = _struck(date(2026, 3, 4))

        assert isinstance(outcome, official_rate.OfficialRateUndeclaredOnDate), outcome
        for invented in ("value", "rate", "base", "nearest"):
            assert not hasattr(outcome, invented), invented

    def test_the_dates_either_side_of_the_gap_are_themselves_declared(self) -> None:
        """So the gap's refusal is about the gap, not about a series nothing can be found in."""
        for on_date in (MARCH_3, MARCH_5):
            struck = _struck(on_date)
            assert isinstance(struck, official_rate.TaxCurrencyConversion), struck
            assert struck.rate_date == on_date


class TestNoPairIsInferredFromAnother:
    """A series quotes one ordered pair in one direction, and the other is not derived."""

    def test_a_series_that_does_not_quote_the_wanted_pair_refuses_naming_both(self) -> None:
        outcome = official_rate.strike_base(
            AMOUNT,
            official_rates.series(DECLARED, pair=(Currency.USD, Currency.UAH)),
            tax_currency=Currency.UAH,
            on_date=MARCH_2,
        )

        assert isinstance(outcome, official_rate.OfficialRateSeriesUnavailable), outcome
        assert outcome.wanted == (Currency.UAH, Currency.USD)
        assert outcome.quotes == (Currency.USD, Currency.UAH)
        assert outcome.series_id == "synthetic_official_usd"


class TestAnAmountAlreadyInTheTaxCurrencyNeverAsks:
    """FR-009: no rate is consulted, and no rate-unavailable reason is produced."""

    def test_striking_a_base_in_the_tax_currency_is_a_programmer_error(self) -> None:
        """Refused by raising, so the caller must check first and the false refusal is
        unrepresentable. A refusal for a rate nobody needed trains a reader to ignore true
        ones (spec.md, Edge Cases)."""
        with pytest.raises(ValueError, match="already in the tax currency"):
            official_rate.strike_base(
                Money(100.0, Currency.UAH, prov.EMPTY),
                official_rates.series(DECLARED),
                tax_currency=Currency.UAH,
                on_date=MARCH_2,
            )
