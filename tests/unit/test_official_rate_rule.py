"""The declared non-publication-day rule, and what it reports when it applies.

FR-011. A series **may** declare which observation governs a date the publisher does not
publish for, the rule is declared data carrying its own citation, and the engine knows
nothing about weekends, holidays or banking calendars.

The form exercised here is an **explicitly enumerated per-date mapping** -- this date's rate
governs that date, listed -- which is a statement of the kind FR-011 defines and needs no
calendar. It is deliberately **not** the Ukrainian rule: пункт 10 розділу III is written in
working days and pre-holiday days, and declaring it needs a declared, cited working-day and
holiday calendar that this feature does not build (FR-018,
``specs/features.toml`` → ``declared-working-day-calendar``).

The load-time half -- that a rule's ``governed_by`` names a declared observation and its
``applies_to`` does not -- lives in
``tests/contract/test_official_rate_declaration_loading.py``, where a file can be named.
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

FRIDAY = date(2026, 3, 6)
SATURDAY = date(2026, 3, 7)
SUNDAY = date(2026, 3, 8)
MONDAY = date(2026, 3, 9)
"""Weekday names for the reader only. Nothing in the engine derives them, and the rule below
lists each date explicitly rather than deriving any of them."""

AMOUNT = Money(1000.0, Currency.USD, prov.EMPTY)


def _series(*, with_rule: bool) -> official_rate.OfficialRateSeries:
    rule = (
        official_rates.enumerated_rule([(SATURDAY, FRIDAY), (SUNDAY, FRIDAY)])
        if with_rule
        else None
    )
    return official_rates.series([(FRIDAY, 40.0), (MONDAY, 44.0)], rule=rule)


def _struck(on_date: date, *, with_rule: bool) -> object:
    return official_rate.strike_base(
        AMOUNT, _series(with_rule=with_rule), tax_currency=Currency.UAH, on_date=on_date
    )


class TestADeclaredRuleSelectsAnotherDatesObservation:
    def test_the_output_states_which_dates_rate_was_applied_to_which_dates_event(self) -> None:
        """A Friday rate on a Saturday event is visible, not implied."""
        struck = _struck(SATURDAY, with_rule=True)

        assert isinstance(struck, official_rate.TaxCurrencyConversion), struck
        assert struck.event_date == SATURDAY
        assert struck.rate_date == FRIDAY
        assert struck.applied_rule == "synthetic_enumerated_rule"
        assert is_close(struck.rate, 40.0)
        assert is_close(struck.base.amount, 40_000.0)

    def test_the_rules_own_citation_reaches_the_base_it_selected(self) -> None:
        """A rule is a declared legal fact, and a base it chose rests on it (FR-015)."""
        struck = _struck(SUNDAY, with_rule=True)

        assert isinstance(struck, official_rate.TaxCurrencyConversion), struck
        ids = {source.id for source in struck.base.provenance.sources}
        assert "synthetic:official_rate_rule:synthetic_enumerated_rule" in ids
        assert "synthetic:official_rate:2026-03-06" in ids

    def test_a_date_the_rule_does_not_list_still_refuses(self) -> None:
        """A rule covers the dates it enumerates and grants nothing beyond them."""
        outcome = _struck(date(2026, 3, 10), with_rule=True)

        assert isinstance(outcome, official_rate.OfficialRateUndeclaredOnDate), outcome
        assert outcome.on_date == date(2026, 3, 10)


class TestTheAbsenceOfARuleIsNotPermissionToChooseOne:
    def test_the_same_date_refuses_when_no_rule_is_declared(self) -> None:
        """FR-011's last clause, and the shipped Ukrainian behaviour (FR-017)."""
        outcome = _struck(SATURDAY, with_rule=False)

        assert isinstance(outcome, official_rate.OfficialRateUndeclaredOnDate), outcome
        assert outcome.on_date == SATURDAY
        assert outcome.covers == (FRIDAY, MONDAY)


class TestADeclaredDateIsNeverRedirected:
    def test_an_observation_of_its_own_wins_over_any_rule(self) -> None:
        """The rule speaks for dates the publisher does not publish for, and Monday is one it
        does. Load-time refuses a rule claiming otherwise; this pins the runtime order."""
        struck = _struck(MONDAY, with_rule=True)

        assert isinstance(struck, official_rate.TaxCurrencyConversion), struck
        assert struck.rate_date == MONDAY
        assert struck.applied_rule is None


class TestARuleSendingADateNowhereBlamesTheRule:
    def test_a_governed_by_the_series_does_not_declare_raises(self) -> None:
        """The loader refuses this shape, so this is a bypass -- and the honest complaint is
        about the rule. Falling through to "no rate is declared for this date" would blame the
        date and send a reader to add an observation the rule was never pointing at."""
        broken = official_rates.series(
            [(FRIDAY, 40.0)],
            rule=official_rates.enumerated_rule([(SATURDAY, date(2026, 1, 1))]),
        )
        with pytest.raises(KeyError, match="does not declare"):
            official_rate.strike_base(AMOUNT, broken, tax_currency=Currency.UAH, on_date=SATURDAY)
