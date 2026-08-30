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

    def test_a_declared_zero_is_in_force_and_is_the_entry_the_period_selects(self) -> None:
        """FR-020: an uncited zero is the figure that gets believed without checking.

        The entry is compared against the one the schedule actually holds for that period,
        because asserting only that a `ComponentAmount` came back with a zero on it re-reads
        what the fixture put there.
        """
        scheme = fixtures.scheme(
            scheme_id="synthetic_scheme_two_entries",
            periodic_components=[
                fixtures.periodic_component(
                    [(FROM, CHARGED_AMOUNT), (date(2026, 6, 1), 0.0)],
                    component_id="contribution",
                )
            ],
        )
        earlier = schemes.component_standing(scheme, "contribution", period="2026-02")
        later = schemes.component_standing(scheme, "contribution", period="2026-07")
        assert isinstance(earlier, schemes.ComponentAmount), earlier
        assert isinstance(later, schemes.ComponentAmount), later
        assert earlier.effective_from == FROM
        assert later.effective_from == date(2026, 6, 1)
        assert later.amount.amount == 0.0
        assert later.amount.provenance.sources
        assert prov.is_unverified(later.amount.provenance)

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


class TestAnAmountTakesEffectForTheWHOLEMonthItLandsIn:
    """``amount_in_force``'s documented rule, which had no case until it was written.

    A statutory sum takes effect on a **date** and is owed for a **period**, so the two must
    be compared in one vocabulary, and the period's is the coarser. The month is the trigger
    and there is no half-month to charge, so an amount effective on the 15th governs the
    month it lands in — including the days before it.
    """

    def test_the_month_an_effective_date_falls_in_is_charged_in_full(self) -> None:
        scheme = fixtures.scheme(
            scheme_id="synthetic_scheme_mid_month",
            periodic_components=[
                fixtures.periodic_component(
                    [(date(2026, 3, 15), CHARGED_AMOUNT)], component_id="contribution"
                )
            ],
        )
        charged = schemes.charge_periods(scheme, Window(first="2026-02", last="2026-04"))
        assert isinstance(charged[0], schemes.PeriodicAmountNotInForce), charged[0]
        for item in charged[1:]:
            assert isinstance(item, schemes.PeriodicCharge), item
            assert_money_close(item.charged, Money(CHARGED_AMOUNT, Currency.UAH, prov.EMPTY))
        assert [item.period for item in charged] == ["2026-02", "2026-03", "2026-04"]

    def test_the_month_before_it_is_refused_rather_than_charged_a_part(self) -> None:
        scheme = fixtures.scheme(
            scheme_id="synthetic_scheme_mid_month",
            periodic_components=[
                fixtures.periodic_component(
                    [(date(2026, 3, 15), CHARGED_AMOUNT)], component_id="contribution"
                )
            ],
        )
        standing = schemes.component_standing(scheme, "contribution", period="2026-02")
        assert isinstance(standing, schemes.PeriodicAmountNotInForce), standing


class TestEveryComponentIsChargedForEveryPeriod:
    """Two components over two months, so the fold cannot be right by having only one of each."""

    def test_the_charges_run_period_by_period_and_component_by_component(self) -> None:
        scheme = fixtures.scheme(
            scheme_id="synthetic_scheme_two_components",
            periodic_components=[
                fixtures.periodic_component([(FROM, 100.0)], component_id="first"),
                fixtures.periodic_component([(FROM, 25.0)], component_id="second"),
            ],
        )
        charged = schemes.charge_periods(scheme, Window(first="2026-01", last="2026-02"))
        assert [(item.period, item.component_id) for item in charged] == [
            ("2026-01", "first"),
            ("2026-01", "second"),
            ("2026-02", "first"),
            ("2026-02", "second"),
        ]
        for item, expected in zip(charged, [100.0, 25.0, 100.0, 25.0], strict=True):
            assert isinstance(item, schemes.PeriodicCharge), item
            assert_money_close(item.charged, Money(expected, Currency.UAH, prov.EMPTY))


class TestARateComponentIsAskedAboutADateAndNotAPeriod:
    """The two component kinds are asked different questions, which is FR-019's whole claim."""

    def test_a_rate_component_answers_on_a_date(self) -> None:
        standing = schemes.component_standing(_silent(), "levy", on_date=date(2026, 6, 1))
        assert isinstance(standing, schemes.ComponentRate), standing
        assert standing.rate == 0.02

    def test_a_rate_component_before_its_schedule_refuses_on_the_date(self) -> None:
        standing = schemes.component_standing(_silent(), "levy", on_date=date(2025, 6, 1))
        assert isinstance(standing, schemes.ComponentRateUndeclaredBefore), standing
