"""FR-020 -- a coupon that cannot be fully reinvested is reported and kept, never lost.

*"When a coupon cannot be fully reinvested because of the instrument's minimum unit, the
unreinvested remainder MUST be reported and retained as cash."*

Three things could go wrong with that requirement, and each of them is a different defect:

* **buying a fraction** -- a third of a bond, which does not exist. The engine would produce
  a holding nobody could hold and a redemption nobody would receive;
* **discarding the remainder** -- money that was paid to the owner and then vanished from
  the ledger, which is a cash-conservation failure (C1) wearing a rounding excuse;
* **retaining it silently** -- the arithmetic right and the reason missing, so a reader sees
  a coupon that was not reinvested and cannot tell whether that was the minimum unit, the
  minimum ticket, or a bug. FR-017 requires a degraded outcome to carry its reason, and this
  is one.

So each case below checks all three: the units bought are whole, the coupon equals what was
spent plus what was kept, and the decision says why in words a reader can act on.

**The declared constraints do the work, not a constant in the engine.** ``min_unit`` and
``min_ticket`` come from the declaration, so the cases here vary them in the fixture rather
than in code -- which is also the demonstration that a venue selling bonds in blocks of five
is a data change (Principle II).
"""

from __future__ import annotations

import math
from datetime import date

from terezy.core.instruments import fixed_income
from terezy.core.instruments.interface import InstrumentDeclaration
from terezy.core.ledger.events import EventKind
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results import project
from terezy.core.results.project import Projection
from tests import synthetic

UAH = Currency.UAH

REINVEST = synthetic.assumptions(coupon_policy=fixed_income.REINVEST)
HOLD_CASH = synthetic.assumptions(coupon_policy=fixed_income.HOLD_CASH)

UNIT_YEAR_OF_INTEREST = 155.0
"""1 000.00 of face at 15.5% -- the synthetic issue's interest per unit per year."""

FIRST_PERIOD_DAYS = 181
SECOND_PERIOD_DAYS = 184
"""2026-01-15 -> 2026-07-15 -> 2027-01-15, counted in the D1 worked example."""


def _coupon(units: float, days: int) -> float:
    return units * UNIT_YEAR_OF_INTEREST * days / 365


def _plan(
    *,
    quantity: float,
    min_unit: float = 1.0,
    min_ticket: float = 1000.0,
) -> tuple[fixed_income.CouponPeriod, ...]:
    return fixed_income.coupon_plan(
        _declaration(min_unit=min_unit, min_ticket=min_ticket),
        synthetic.holding(quantity=quantity, cost=_cost(quantity)),
        REINVEST,
    )


def _declaration(*, min_unit: float = 1.0, min_ticket: float = 1000.0) -> InstrumentDeclaration:
    return synthetic.declaration(
        constraints=synthetic.constraints(
            min_unit=min_unit,
            min_ticket=Money(min_ticket, UAH, prov.of([synthetic.CONSTRAINTS_SOURCE])),
        )
    )


def _cost(quantity: float) -> Money:
    """The purchase at par, so the fixture's cost always matches its quantity."""
    return Money(quantity * 1000.0, UAH, prov.of([synthetic.PURCHASE_SOURCE]))


def _projection(
    *,
    quantity: float,
    min_unit: float = 1.0,
    min_ticket: float = 1000.0,
    policy: str = fixed_income.REINVEST,
) -> Projection:
    outcome = project.project(
        _declaration(min_unit=min_unit, min_ticket=min_ticket),
        synthetic.holding(quantity=quantity, cost=_cost(quantity)),
        synthetic.horizon(),
        synthetic.assumptions(coupon_policy=policy),
        tax_classes=synthetic.TAX_PACK,
    )
    assert isinstance(outcome, Projection), f"expected a projection, got {outcome!r}"
    return outcome


class TestACouponTooSmallToBuyAnything:
    """Ten units: every coupon is smaller than one bond, so nothing is ever bought."""

    def test_the_first_coupon_does_not_cover_one_unit(self) -> None:
        # 1 550.00 x 181/365 = 768.6301369863014, against a face value of 1 000.00.
        # 0.768... of a bond is not a quantity anyone can hold.
        assert is_close(_coupon(10.0, FIRST_PERIOD_DAYS), 768.6301369863014)
        assert _coupon(10.0, FIRST_PERIOD_DAYS) < 1000.0

    def test_nothing_is_bought_and_the_whole_coupon_is_retained(self) -> None:
        for period in _plan(quantity=10.0):
            assert period.reinvestment.units_bought == 0.0
            assert_money_close(period.reinvestment.reinvested, Money(0.0, UAH, prov.EMPTY))
            assert_money_close(period.reinvestment.retained_as_cash, period.coupon)

    def test_the_reason_names_the_coupon_the_increment_and_the_price(self) -> None:
        """A reader must be able to see *why* without reading the engine.

        The coupon is quoted from the figure itself rather than compared against a literal
        768.6301369863014: the engine multiplies ``face x (rate x fraction x units)`` and
        this module's check multiplies ``units x 155 x days / 365``, which agree to within
        the project tolerance and differ in the last bit. Pinning the decimal here would be
        asserting an order of operations, not an amount -- and the requirement is that the
        reason quotes the coupon it is about.
        """
        (first, *_) = _plan(quantity=10.0)
        assert repr(first.coupon.amount) in first.reinvestment.reason
        assert first.coupon.amount == 768.6301369863013
        assert is_close(first.coupon.amount, _coupon(10.0, FIRST_PERIOD_DAYS))
        assert "1000.0" in first.reinvestment.reason
        assert "FR-020" in first.reinvestment.reason
        assert "retained as cash" in first.reinvestment.reason

    def test_no_reinvestment_event_is_emitted_at_all(self) -> None:
        """Nothing was bought, so there is no purchase to record.

        An event of zero units would be refused by the ledger anyway -- *"a lot may not
        exist at zero"* -- and recording one would claim a transaction that did not happen.
        """
        rows = _projection(quantity=10.0).schedule.rows
        assert not [row for row in rows if row.kind is EventKind.REINVESTMENT]

    def test_the_retained_coupons_are_all_still_in_the_cash_balance(self) -> None:
        # Four coupons on a flat 10 units = 2 x 1 550.00 = 3 100.00, and the purchase of
        # 10 000.00 comes back as 10 000.00 of principal. Nothing was spent, so nothing is
        # missing: the balance is exactly the interest.
        result = _projection(quantity=10.0)
        retained = sum(
            period.reinvestment.retained_as_cash.amount for period in _plan(quantity=10.0)
        )
        assert is_close(retained, 3_100.0)
        assert_money_close(result.ledger.accounts[UAH].balance, Money(3_100.0, UAH, prov.EMPTY))

    def test_the_holding_never_grows(self) -> None:
        result = _projection(quantity=10.0)
        assert result.schedule.rows[-1].quantity == 10.0


class TestAMinimumUnitLargerThanOneBond:
    """A venue selling in blocks of five: a data change, and the remainder grows."""

    def test_the_first_coupon_buys_one_block_and_retains_the_rest(self) -> None:
        # 100 units: coupon 15 500 x 181/365 = 7 686.301369863014.
        # A block of five costs 5 x 1 000.00 = 5 000.00, so one block is affordable and two
        # are not: 7 686.30 / 5 000 = 1.537...
        # Retained: 7 686.301369863014 - 5 000.00 = 2 686.301369863014
        (first, *_) = _plan(quantity=100.0, min_unit=5.0)
        assert first.reinvestment.units_bought == 5.0
        assert_money_close(first.coupon, Money(_coupon(100.0, FIRST_PERIOD_DAYS), UAH, prov.EMPTY))
        assert_money_close(first.reinvestment.reinvested, Money(5_000.0, UAH, prov.EMPTY))
        assert_money_close(
            first.reinvestment.retained_as_cash, Money(2_686.301369863014, UAH, prov.EMPTY)
        )

    def test_the_second_coupon_accrues_on_the_hundred_and_five_units_then_held(self) -> None:
        # 105 x 155 x 184/365 = 16 275 x 184/365 = 2 994 600 / 365 = 8 204.383561643836,
        # since 365 x 8 204 = 2 994 460 and the remainder is 140.
        # One more block: 8 204.38 / 5 000 = 1.64..., so 5 units for 5 000.00 and
        # 3 204.383561643836 retained.
        (_, second, *_) = _plan(quantity=100.0, min_unit=5.0)
        assert second.units_held == 105.0
        assert_money_close(
            second.coupon, Money(_coupon(105.0, SECOND_PERIOD_DAYS), UAH, prov.EMPTY)
        )
        assert is_close(second.coupon.amount, 8_204.383561643836)
        assert second.reinvestment.units_bought == 5.0
        assert_money_close(
            second.reinvestment.retained_as_cash, Money(3_204.383561643836, UAH, prov.EMPTY)
        )

    def test_every_purchase_is_a_whole_number_of_increments(self) -> None:
        for period in _plan(quantity=100.0, min_unit=5.0):
            units = period.reinvestment.units_bought
            assert units % 5.0 == 0.0, f"{units!r} is not a whole block of five"


class TestAReinvestmentBelowTheMinimumTicket:
    """FR-018 applies to a reinvestment too: a reinvestment is a purchase."""

    def test_a_coupon_that_buys_units_worth_less_than_the_ticket_buys_nothing(self) -> None:
        # 100 units, minimum ticket 8 000.00. The first coupon of 7 686.30 buys 7 whole
        # units for 7 000.00 -- below the ticket, so the venue would refuse it. The coupon
        # is retained instead of executing a purchase that could not happen, and instead of
        # rounding up to eight units with money the owner does not have.
        (first, *_) = _plan(quantity=100.0, min_ticket=8_000.0)
        assert first.reinvestment.units_bought == 0.0
        assert_money_close(first.reinvestment.retained_as_cash, first.coupon)
        assert "minimum ticket" in first.reinvestment.reason
        assert "8000.0" in first.reinvestment.reason
        assert "FR-018" in first.reinvestment.reason

    def test_the_holding_therefore_never_grows_and_nothing_is_lost(self) -> None:
        result = _projection(quantity=100.0, min_ticket=8_000.0)
        assert not [row for row in result.schedule.rows if row.kind is EventKind.REINVESTMENT]
        assert_money_close(result.ledger.accounts[UAH].balance, Money(31_000.0, UAH, prov.EMPTY))


class TestNothingIsEverLostOrFractional:
    """The two identities that hold for every purchase, whatever the constraints."""

    def test_the_coupon_always_equals_what_was_spent_plus_what_was_kept(self) -> None:
        """The whole of FR-020 in one line, over a range of purchases and constraints."""
        for quantity in (1.0, 2.0, 7.0, 13.0, 100.0, 1_001.0):
            for min_unit in (1.0, 5.0):
                for period in _plan(quantity=quantity, min_unit=min_unit):
                    assert_money_close(
                        period.coupon,
                        Money(
                            period.reinvestment.reinvested.amount
                            + period.reinvestment.retained_as_cash.amount,
                            UAH,
                            prov.EMPTY,
                        ),
                    )

    def test_no_purchase_ever_costs_more_than_the_coupon_that_funded_it(self) -> None:
        """A reinvestment spends the coupon and never a hryvnia more.

        Overspending would fund a purchase from money that had not arrived, which is a
        fabricated cash flow rather than an overdraft.
        """
        for quantity in (1.0, 7.0, 13.0, 100.0, 1_001.0):
            for period in _plan(quantity=quantity):
                spent = period.reinvestment.reinvested.amount
                assert spent <= period.coupon.amount or is_close(spent, period.coupon.amount)
                assert period.reinvestment.retained_as_cash.amount >= 0.0 or is_close(
                    period.reinvestment.retained_as_cash.amount, 0.0
                )

    def test_no_purchase_is_ever_a_fraction_of_an_increment(self) -> None:
        for quantity in (1.0, 7.0, 13.0, 100.0, 1_001.0):
            for period in _plan(quantity=quantity):
                units = period.reinvestment.units_bought
                assert units == math.floor(units), f"{units!r} is a fraction of a bond"

    def test_every_reinvested_amount_carries_the_terms_it_was_priced_from(self) -> None:
        """The price is the declared face value, so the mark comes with it (FR-015)."""
        for period in _plan(quantity=100.0):
            assert prov.is_unverified(period.reinvestment.price_per_unit.provenance)
            assert prov.is_unverified(period.reinvestment.reinvested.provenance)
            assert prov.is_unverified(period.reinvestment.retained_as_cash.provenance)


class TestTheWholeUnitRuleIsNotDefeatedByFloatingPoint:
    """A unit the owner can afford must not be lost to the last bit of a division."""

    def test_a_coupon_a_hair_below_an_exact_multiple_still_buys_the_whole_unit(self) -> None:
        """``floor`` alone would discard a real bond over a representation artefact.

        The ratio here is ``6.999999999999999...``, which the single project tolerance calls
        seven. Treating a difference the tolerance calls zero as zero is exactly what the
        tolerance is for -- and the remainder is still *reported* as whatever it is, a
        negative hair, rather than clamped to a tidier number.
        """
        buy = fixed_income.coupon_policy(fixed_income.REINVEST)
        price = Money(1000.0, UAH, prov.EMPTY)
        assert buy(Money(7_000.0 - 1e-9, UAH, prov.EMPTY), price, 1.0) == 7.0
        assert buy(Money(7_000.0, UAH, prov.EMPTY), price, 1.0) == 7.0
        assert buy(Money(7_000.0 + 1e-9, UAH, prov.EMPTY), price, 1.0) == 7.0

    def test_a_coupon_genuinely_short_of_a_unit_buys_one_fewer(self) -> None:
        """The snap is a tolerance, not a rounding-up rule.

        One hryvnia short of eight bonds buys seven. If this bought eight, the "tolerance"
        would have become a licence to spend money that was not paid.
        """
        buy = fixed_income.coupon_policy(fixed_income.REINVEST)
        price = Money(1000.0, UAH, prov.EMPTY)
        assert buy(Money(7_999.0, UAH, prov.EMPTY), price, 1.0) == 7.0
        assert buy(Money(999.99, UAH, prov.EMPTY), price, 1.0) == 0.0

    def test_holding_cash_buys_nothing_whatever_the_coupon(self) -> None:
        """The other policy, for contrast: it does not consult the price at all."""
        buy = fixed_income.coupon_policy(fixed_income.HOLD_CASH)
        price = Money(1000.0, UAH, prov.EMPTY)
        for amount in (0.0, 999.99, 7_000.0, 1e9):
            assert buy(Money(amount, UAH, prov.EMPTY), price, 1.0) == 0.0


class TestAZeroCouponBondHasNothingToReinvest:
    """The policy is not a reason to invent a coupon."""

    def test_the_plan_is_empty_and_the_schedule_is_principal_only(self) -> None:
        declaration = synthetic.declaration(terms=synthetic.terms(coupon_rate=0.0))
        holding = synthetic.holding(quantity=10.0, cost=_cost(10.0))
        assert fixed_income.coupon_plan(declaration, holding, REINVEST) == ()
        outcome = project.project(
            declaration,
            holding,
            synthetic.horizon(),
            REINVEST,
            tax_classes=synthetic.TAX_PACK,
        )
        assert isinstance(outcome, Projection)
        assert [row.kind for row in outcome.schedule.rows] == [
            EventKind.PURCHASE,
            EventKind.PRINCIPAL_REPAYMENT,
        ]


class TestTheRemainderIsTheSameUnderBothPoliciesWhenNothingCanBeBought:
    """When reinvestment is impossible the two policies must agree exactly.

    Not a tautology: it is the statement that the difference between the policies comes from
    the arithmetic they perform and not from the label on the run. A ``reinvest`` run that
    produced a different schedule while buying nothing would mean something else in the
    engine was reading the policy.
    """

    def test_ten_units_produce_the_same_schedule_under_either_policy(self) -> None:
        reinvest = _projection(quantity=10.0, policy=fixed_income.REINVEST)
        held = _projection(quantity=10.0, policy=fixed_income.HOLD_CASH)
        assert [row.kind for row in reinvest.schedule.rows] == [
            row.kind for row in held.schedule.rows
        ]
        for left, right in zip(reinvest.schedule.rows, held.schedule.rows, strict=True):
            assert left.occurred_on == right.occurred_on
            assert_money_close(left.gross, right.gross)
        assert_money_close(reinvest.ledger.accounts[UAH].balance, held.ledger.accounts[UAH].balance)

    def test_the_dates_are_the_ones_the_declared_conventions_placed(self) -> None:
        """A sanity anchor, so the equality above is between two real schedules."""
        assert [period.paid_on for period in _plan(quantity=10.0)] == [
            date(2026, 7, 15),
            date(2027, 1, 15),
            date(2027, 7, 15),
            date(2028, 1, 17),
        ]
