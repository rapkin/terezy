"""A charge triggered by a period elapsing, and the three different ways a nil can be nil.

FR-019: a periodic component's trigger is a **period**, not income, and its base is a
statutory amount, not a percentage. The zero-income month is the case a rate-shaped model
gets wrong, so it is the first test here.

FR-020 and SC-011: *this scheme charges no such component*, *it was charged and came to
nothing*, and *it is declared and nothing is in force* are three claims. They are three
return types, so no caller can collapse them by accident.
"""

from __future__ import annotations

from datetime import date

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.periods import Window
from terezy.core.primitives.tolerance import assert_money_close
from terezy.core.tax import scheme as schemes
from tests import schemes as fixtures

FROM = date(2026, 1, 1)
CHARGED_AMOUNT = 1_760.00
"""SYNTHETIC monthly statutory sum. Not any published contribution."""

QUARTER = Window(first="2026-01", last="2026-03")


def _charging() -> schemes.TaxationScheme:
    return fixtures.scheme(
        scheme_id="synthetic_scheme_charging",
        periodic_components=[
            fixtures.periodic_component([(FROM, CHARGED_AMOUNT)], component_id="contribution")
        ],
    )


def _nil() -> schemes.TaxationScheme:
    return fixtures.scheme(
        scheme_id="synthetic_scheme_nil",
        periodic_components=[
            fixtures.periodic_component([(FROM, 0.0)], component_id="contribution")
        ],
    )


def _silent() -> schemes.TaxationScheme:
    return fixtures.scheme(
        scheme_id="synthetic_scheme_silent",
        rate_components=[fixtures.rate_component([(FROM, 0.02)], component_id="levy")],
    )


class TestThePeriodIsTheTrigger:
    """US4 scenario 3. A month with no income at all still owes the periodic component."""

    def test_every_month_of_the_window_is_charged_once(self) -> None:
        charged = schemes.charge_periods(_charging(), QUARTER)
        assert [item.period for item in charged] == ["2026-01", "2026-02", "2026-03"]

    def test_no_income_is_consulted_anywhere_in_the_signature(self) -> None:
        """``charge_periods`` takes a scheme and a window. There is no amount to pass it."""
        charged = schemes.charge_periods(_charging(), QUARTER)
        for item in charged:
            assert isinstance(item, schemes.PeriodicCharge), item
            assert_money_close(item.charged, Money(CHARGED_AMOUNT, Currency.UAH, prov.EMPTY))

    def test_two_schemes_differing_only_in_the_amount_differ_by_exactly_it(self) -> None:
        """SC-010, with no source line changed between the two -- they are two declarations."""
        charging = schemes.charge_periods(_charging(), QUARTER)
        nil = schemes.charge_periods(_nil(), QUARTER)
        assert len(charging) == len(nil) == 3
        for one, other in zip(charging, nil, strict=True):
            assert isinstance(one, schemes.PeriodicCharge), one
            assert isinstance(other, schemes.PeriodicCharge), other
            assert one.charged.amount - other.charged.amount == CHARGED_AMOUNT


class TestTheThreeNils:
    """SC-011. Three claims, three types, and none of them a bare zero.

    ``component_standing`` answers *what is declared and in force*; the charge functions
    answer *what was charged*. Keeping those two questions apart is what lets the first be
    asked about a component the scheme never mentions, which is the state that has no charge.
    """

    def test_a_component_the_scheme_does_not_declare_says_so(self) -> None:
        standing = schemes.component_standing(_silent(), "contribution", period="2026-02")
        assert isinstance(standing, schemes.ComponentNotDeclared), standing
        assert standing.component_id == "contribution"
        assert "charges no such component" in standing.reason

    def test_a_declared_zero_is_in_force_and_carries_its_own_citation(self) -> None:
        """FR-020: an uncited zero is the figure that gets believed without checking."""
        standing = schemes.component_standing(_nil(), "contribution", period="2026-02")
        assert isinstance(standing, schemes.ComponentAmount), standing
        assert standing.amount.amount == 0.0
        assert standing.provenance.sources
        assert prov.is_unverified(standing.amount.provenance)

    def test_a_declared_component_with_nothing_in_force_refuses_naming_the_period(self) -> None:
        standing = schemes.component_standing(_charging(), "contribution", period="2025-12")
        assert isinstance(standing, schemes.PeriodicAmountNotInForce), standing
        assert standing.period == "2025-12"
        assert standing.earliest_declared == FROM
        assert "never a zero" in standing.reason

    def test_the_three_outcomes_are_three_unrelated_types(self) -> None:
        """A caller matching on one of them cannot be handed another by mistake."""
        outcomes = {
            type(schemes.component_standing(_silent(), "contribution", period="2026-02")),
            type(schemes.component_standing(_nil(), "contribution", period="2026-02")),
            type(schemes.component_standing(_charging(), "contribution", period="2025-12")),
        }
        assert len(outcomes) == 3

    def test_a_zero_amount_is_charged_and_reported_rather_than_skipped(self) -> None:
        """The second nil, as it reaches an output: a line of zero, citing what produced it."""
        charged = schemes.charge_periods(_nil(), QUARTER)
        assert len(charged) == 3
        for item in charged:
            assert isinstance(item, schemes.PeriodicCharge), item
            assert item.charged.amount == 0.0
            assert prov.is_unverified(item.charged.provenance)

    def test_a_period_with_no_amount_in_force_refuses_inside_a_window(self) -> None:
        """US4 scenario 4: a refusal per period, never a zero standing in for a missing one."""
        charged = schemes.charge_periods(_charging(), Window(first="2025-12", last="2026-01"))
        assert isinstance(charged[0], schemes.PeriodicAmountNotInForce), charged[0]
        assert isinstance(charged[1], schemes.PeriodicCharge), charged[1]


class TestARateComponentIsAskedAboutADateAndNotAPeriod:
    """The two component kinds are asked different questions, which is FR-019's whole claim."""

    def test_a_rate_component_answers_on_a_date(self) -> None:
        standing = schemes.component_standing(_silent(), "levy", on_date=date(2026, 6, 1))
        assert isinstance(standing, schemes.ComponentRate), standing
        assert standing.rate == 0.02

    def test_a_rate_component_before_its_schedule_refuses_on_the_date(self) -> None:
        standing = schemes.component_standing(_silent(), "levy", on_date=date(2025, 6, 1))
        assert isinstance(standing, schemes.ComponentRateUndeclaredBefore), standing
