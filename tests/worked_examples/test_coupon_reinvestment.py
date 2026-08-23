"""D2 -- coupons reinvested at the declared yield, with every figure worked out by hand.

**The issue below is SYNTHETIC. Its terms are invented, not observed** -- the same fixture
D1 uses, for the same reason (``SIMULATOR_SPEC.md`` §11 item 2). Every term is stated in
this file so a reader can check the whole schedule on a calculator without opening another
document, and no figure computed here describes a bond anyone can buy.

**What this closes**: D2 in ``docs/REQUIRED_TESTS.md``, FR-019 (*"a declared coupon policy
of at least 'hold as cash' and 'reinvest at the yield available on the coupon date', and
the two MUST produce different, separately checkable results"*), FR-020 (the unreinvestable
remainder is reported and retained as cash) and SC-010.

---

**The terms.** Face 1 000.00 UAH per unit, coupon 15.5% per annum, issued 2026-01-15,
maturing 2028-01-15, semiannual coupons, ``act/365`` day count, ``following`` business-day
rule. Minimum ticket 1 000.00, minimum unit 1 whole bond.

**The purchase.** 100 units at par on the issue date: 100 000.00 UAH. A hundred rather than
D1's ten, and the reason is arithmetic rather than taste: at ten units the first coupon is
768.63 and buys no whole bond at all, so the interesting case -- reinvestment *and* a
remainder -- needs a purchase whose coupon exceeds one face value. The ten-unit case is not
thereby untested; it is the subject of ``tests/unit/test_reinvestment_remainder.py``.

**"The yield available on the coupon date" means par**, and that is the whole of the
interpretation. This feature declares exactly one yield -- the issue's own coupon rate --
and has no yield curve; the contract lists *"pricing future purchases off a full yield
curve rather than a single declared yield"* among the things deliberately absent. A unit
bought at face value earns exactly the declared rate, so face value is the only price at
which "the declared yield" is the yield actually obtained. Any other price would be a
market quote, and there is none to be had.

**The accrual periods**, counted month by month on the unadjusted dates, exactly as in D1:

* 2026-01-15 -> 2026-07-15: 31 + 28 + 31 + 30 + 31 + 30 = 181 days
* 2026-07-15 -> 2027-01-15: 31 + 31 + 30 + 31 + 30 + 31 = 184 days
* 2027-01-15 -> 2027-07-15: 181 days
* 2027-07-15 -> 2028-01-15: 184 days

**The schedule, period by period.** A coupon is
``units x 1 000.00 x 0.155 x days / 365``, so a unit-year of interest is 155.00:

| # | accrual | units | coupon | whole units bought | spent | retained |
|---|---|---|---|---|---|---|
| 1 | 181 d | 100 | ``15 500 x 181/365`` = 7 686.301369863014 | 7 | 7 000.00 | 686.301369863014 |
| 2 | 184 d | 107 | ``16 585 x 184/365`` = 8 360.657534246575 | 8 | 8 000.00 | 360.657534246575 |
| 3 | 181 d | 115 | ``17 825 x 181/365`` = 8 839.246575342466 | 8 | 8 000.00 | 839.246575342466 |
| 4 | 184 d | 123 | ``19 065 x 184/365`` = 9 610.849315068493 | 0 | 0.00 | 9 610.849315068493 |

Each division is checkable on paper: ``15 500 x 181 = 2 805 500``, and
``2 805 500 / 365 = 7 686 + 110/365``, since ``365 x 7 686 = 2 805 390``. Likewise
``16 585 x 184 = 3 051 640 = 365 x 8 360 + 240``, ``17 825 x 181 = 3 226 325 = 365 x 8 839
+ 90``, and ``19 065 x 184 = 3 507 960 = 365 x 9 610 + 310``.

The **fourth coupon is not reinvested**: it is paid on the maturity date, and a unit bought
that day would be redeemed the same day. Buying it would be a fabricated round trip, so the
whole coupon is retained and the decision says why.

**Why the two-period compounding is not a simple square.** The two half-years are 181 and
184 days, so their growth factors differ:

* ``1 + 0.155 x 181/365 = 1.0768630136986301``
* ``1 + 0.155 x 184/365 = 1.0781369863013699``
* their product is ``1.1610058442484519``, not ``(1 + 0.155/2)^2 = 1.16005625``

Unrounded, 100 units would compound to ``100 x 1.1610058442484519 = 116.10058442484519``
units after two periods. Whole-unit reinvestment leaves **115** units and
``686.301369863014 + 360.657534246575 = 1 046.958904109589`` UAH of cash. That gap is the
price of FR-020's minimum unit, and the point of FR-020 is that it is *retained* rather than
lost.

**The totals.**

* coupons received: ``7 686.301369863014 + 8 360.657534246575 + 8 839.246575342466 +
  9 610.849315068493 = 34 497.05479452055``
* reinvested: ``7 000 + 8 000 + 8 000 = 23 000.00``
* redemption: ``123 x 1 000.00 = 123 000.00`` on 2028-01-17 (the 15th is a Saturday)
* terminal cash: ``-100 000 + 34 497.05479452055 - 23 000 + 123 000 = 34 497.05479452055``

The terminal amount equalling the coupon total is not a coincidence and is worth stating:
every unit was bought at par and redeemed at par, so the 23 000.00 put back in came out
again unchanged, and what is left over is exactly the interest.

**Against the same purchase held as cash**: four coupons on a flat 100 units come to
``15 500 x (181 + 184 + 181 + 184)/365 = 15 500 x 2 = 31 000.00`` exactly, so the terminal
amount is 31 000.00 and reinvestment is worth **3 497.05479452055 UAH** on this purchase --
the whole of SC-010's "different terminal amounts", in a figure a reader can check.

**Tax is zero throughout**, under the same exempt class D1 uses, so gross and net coincide
and the reinvestment is funded by the whole coupon. That is a property of this fixture and
not of the engine: see ``instruments.fixed_income`` on what a *taxed* coupon would mean for
a reinvestment sized on the gross amount.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from terezy.core.instruments import fixed_income
from terezy.core.instruments.interface import (
    Assumptions,
    BondTerms,
    DateRange,
    Holding,
    InstrumentConstraints,
    InstrumentDeclaration,
)
from terezy.core.ledger.events import EventKind
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import SourceRef
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results import project
from terezy.core.results.project import Projection
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from terezy.core.tax.schedule import RateEntry

pytestmark = pytest.mark.worked_example

UAH = Currency.UAH

# --- the fixture's sources ------------------------------------------------------------

TERMS_SOURCE = SourceRef(
    id="synthetic:ovdp_a:terms",
    citation=(
        "SYNTHETIC FIXTURE -- terms invented for a hand-checkable example. Not an "
        "observation of any real issue, and not to be quoted as one."
    ),
    retrieved_on=date(2026, 8, 21),
    verified_on=None,
)

CONSTRAINTS_SOURCE = SourceRef(
    id="synthetic:ovdp_a:constraints",
    citation="SYNTHETIC FIXTURE -- minimum ticket and minimum unit invented for this example.",
    retrieved_on=date(2026, 8, 21),
    verified_on=None,
)

EXEMPTION_SOURCE = SourceRef(
    id="synthetic:ua:government_bond",
    citation="SYNTHETIC FIXTURE standing in for the cited exemption.",
    retrieved_on=date(2026, 8, 21),
    verified_on=None,
)

PURCHASE_SOURCE = SourceRef(
    id="synthetic:owner:purchase",
    citation="Owner-stated purchase for this example: 100 units at par.",
    retrieved_on=date(2026, 8, 21),
    verified_on=None,
)

TERMS_PROVENANCE = prov.of([TERMS_SOURCE])

# --- the fixture ----------------------------------------------------------------------

FACE_VALUE = 1000.0
COUPON_RATE = 0.155
ISSUE_DATE = date(2026, 1, 15)
MATURITY_DATE = date(2028, 1, 15)
ADJUSTED_MATURITY = date(2028, 1, 17)  # a Saturday; "following" pays on the Monday

TERMS = BondTerms(
    face_value=Money(FACE_VALUE, UAH, TERMS_PROVENANCE),
    coupon_rate=COUPON_RATE,
    issue_date=ISSUE_DATE,
    maturity_date=MATURITY_DATE,
    periodicity="semiannual",
    day_count="act/365",
    business_day_rule="following",
    provenance=TERMS_PROVENANCE,
)

CONSTRAINTS = InstrumentConstraints(
    min_ticket=Money(1000.0, UAH, prov.of([CONSTRAINTS_SOURCE])),
    min_unit=1.0,
    provenance=prov.of([CONSTRAINTS_SOURCE]),
)

EXEMPTION_EFFECTIVE_FROM = date(2020, 1, 1)
"""A FIXTURE effective date, chosen well before the schedule this example projects.

It is not a claim about Ukrainian law. The real exemption in ``data/tax/ua.toml`` starts
at the date its citation attests, and this example is about coupon arithmetic rather than
about when an exemption came into force.
"""

EXEMPT_CLASS = TaxClass(
    id="ua_government_bond",
    applies_to=frozenset({TaxableEventKind.COUPON, TaxableEventKind.DISPOSAL_GAIN}),
    rates=(
        RateEntry(
            effective_from=EXEMPTION_EFFECTIVE_FROM,
            pit_rate=0.0,
            levy_rate=0.0,
            provenance=prov.of([EXEMPTION_SOURCE]),
        ),
    ),
)

DECLARATION = InstrumentDeclaration(
    id="ovdp_synthetic_a",
    name="Synthetic OVDP issue A -- TEST FIXTURE, terms invented",
    instrument_class="fixed_income",
    currency=UAH,
    is_synthetic=True,
    terms=TERMS,
    constraints=CONSTRAINTS,
    tax_classes={
        TaxableEventKind.COUPON: EXEMPT_CLASS.id,
        TaxableEventKind.DISPOSAL_GAIN: EXEMPT_CLASS.id,
    },
)

QUANTITY = 100.0
COST = Money(100_000.0, UAH, prov.of([PURCHASE_SOURCE]))

HOLDING = Holding(
    owner_id="owner-1",
    instrument_id=DECLARATION.id,
    quantity=QUANTITY,
    purchased_on=ISSUE_DATE,
    cost=COST,
)

HORIZON = DateRange(start=ISSUE_DATE, end=date(2028, 1, 31))
TAX_CLASSES = {EXEMPT_CLASS.id: EXEMPT_CLASS}

REINVEST = Assumptions(consumption_method="fifo", coupon_policy=fixed_income.REINVEST)
HOLD_CASH = Assumptions(consumption_method="fifo", coupon_policy=fixed_income.HOLD_CASH)

# --- the hand-computed schedule -------------------------------------------------------
#
# Written as ``units * 1000.0 * 0.155 * days / 365`` rather than as decimal literals copied
# from a run, so a reader checks the convention and the compounding rather than checking
# that the code still does what it did last time. The unit counts are the ones derived in
# the module docstring: 100, then 107, then 115, then 123.

UNIT_YEAR_OF_INTEREST = 155.0  # 1 000.00 face x 15.5%

EXPECTED_PERIODS: tuple[tuple[date, int, float, float, float], ...] = (
    # payment date,        days, units held, units bought, cash retained
    (date(2026, 7, 15), 181, 100.0, 7.0, 686.301369863014),
    (date(2027, 1, 15), 184, 107.0, 8.0, 360.657534246575),
    (date(2027, 7, 15), 181, 115.0, 8.0, 839.246575342466),
    (ADJUSTED_MATURITY, 184, 123.0, 0.0, 9610.849315068493),
)

FINAL_UNITS = 123.0
"""100 bought, then 7 + 8 + 8 reinvested. The quantity redeemed at maturity."""

REINVESTED = 23_000.0
"""``7 000 + 8 000 + 8 000``: three purchases of whole units at par."""

COUPONS_HELD_AS_CASH = 31_000.0
"""``15 500 x 730/365``: two years of interest on a flat 100 units, exactly."""


def _coupon(units: float, days: int) -> float:
    return units * UNIT_YEAR_OF_INTEREST * days / 365


EXPECTED_COUPON_TOTAL = sum(_coupon(units, days) for _, days, units, _, _ in EXPECTED_PERIODS)
"""34 497.05479452055 -- the four coupons of the growing holding, summed."""


def _projection(assumptions: Assumptions) -> Projection:
    outcome = project.project(
        DECLARATION,
        HOLDING,
        HORIZON,
        assumptions,
        tax_classes=TAX_CLASSES,
    )
    assert isinstance(outcome, Projection), f"expected a projection, got {outcome!r}"
    return outcome


def _rows(assumptions: Assumptions, kind: EventKind) -> list[float]:
    return [row.gross.amount for row in _projection(assumptions).schedule.rows if row.kind is kind]


class TestEachPeriodCompoundsOnTheUnitsThenHeld:
    """The two-period arithmetic of the docstring, period by period (D2)."""

    def test_the_schedule_is_a_purchase_four_coupons_three_reinvestments_and_the_principal(
        self,
    ) -> None:
        # Nine rows. The reinvestment sits behind the coupon that funded it, on the same
        # date: the money has to arrive before it can be spent.
        assert [row.kind for row in _projection(REINVEST).schedule.rows] == [
            EventKind.PURCHASE,
            EventKind.COUPON,
            EventKind.REINVESTMENT,
            EventKind.COUPON,
            EventKind.REINVESTMENT,
            EventKind.COUPON,
            EventKind.REINVESTMENT,
            EventKind.COUPON,
            EventKind.PRINCIPAL_REPAYMENT,
        ]

    def test_each_coupon_is_the_rate_on_the_units_held_over_that_period(self) -> None:
        # 15 500 x 181/365 = 7 686.301369863014   on 100 units
        # 16 585 x 184/365 = 8 360.657534246575   on 107 units
        # 17 825 x 181/365 = 8 839.246575342466   on 115 units
        # 19 065 x 184/365 = 9 610.849315068493   on 123 units
        coupons = [
            row for row in _projection(REINVEST).schedule.rows if row.kind is EventKind.COUPON
        ]
        assert len(coupons) == len(EXPECTED_PERIODS)
        for row, (paid_on, days, units, _, _) in zip(coupons, EXPECTED_PERIODS, strict=True):
            assert row.occurred_on == paid_on
            assert_money_close(row.gross, Money(_coupon(units, days), UAH, prov.EMPTY))

    def test_the_first_two_periods_compound_by_their_own_day_counts_and_not_by_a_square(
        self,
    ) -> None:
        # (1 + 0.155 x 181/365) x (1 + 0.155 x 184/365) = 1.0768630136986301
        #                                               x 1.0781369863013699
        #                                               = 1.1610058442484519
        # A flat semiannual square would be (1 + 0.155/2)^2 = 1.16005625, which is a
        # different number: the two half-years are 181 and 184 days, not 182.5 each.
        first = 1 + COUPON_RATE * 181 / 365
        second = 1 + COUPON_RATE * 184 / 365
        assert is_close(first, 1.0768630136986301)
        assert is_close(second, 1.0781369863013699)
        assert not is_close(first * second, (1 + COUPON_RATE / 2) ** 2)

        # Unrounded, 100 units would compound to 116.10058442484519 after two periods.
        # Whole units leave 115, and the difference is retained as cash rather than lost.
        assert is_close(QUANTITY * first * second, 116.10058442484519)
        assert math.floor(QUANTITY * first * second) == 116
        assert EXPECTED_PERIODS[2][2] == 115.0

    def test_each_reinvestment_buys_whole_units_at_face_value(self) -> None:
        # 7 686.30 -> 7 units for 7 000.00;  8 360.66 -> 8 for 8 000.00;
        # 8 839.25 -> 8 units for 8 000.00.  Cash out, so the amount is negative.
        reinvestments = [
            row for row in _projection(REINVEST).schedule.rows if row.kind is EventKind.REINVESTMENT
        ]
        expected = [(paid_on, units) for paid_on, _, _, units, _ in EXPECTED_PERIODS if units]
        assert len(reinvestments) == len(expected)
        for row, (paid_on, units) in zip(reinvestments, expected, strict=True):
            assert row.occurred_on == paid_on
            assert row.quantity == units
            assert_money_close(row.gross, Money(-units * FACE_VALUE, UAH, prov.EMPTY))

    def test_the_units_held_grow_to_a_hundred_and_twenty_three(self) -> None:
        # 100 + 7 + 8 + 8. The redemption surrenders every one of them.
        principal = _projection(REINVEST).schedule.rows[-1]
        assert principal.quantity == FINAL_UNITS
        assert_money_close(principal.gross, Money(FINAL_UNITS * FACE_VALUE, UAH, prov.EMPTY))
        assert principal.occurred_on == ADJUSTED_MATURITY

    def test_the_final_coupon_is_not_reinvested_because_the_bond_matures_that_day(self) -> None:
        # A unit bought on 2028-01-17 would be redeemed on 2028-01-17. The whole coupon is
        # retained, and the decision says so rather than leaving a reader to notice.
        decisions = fixed_income.coupon_plan(DECLARATION, HOLDING, REINVEST)
        assert decisions[-1].reinvestment.units_bought == 0.0
        assert "matur" in decisions[-1].reinvestment.reason
        assert_money_close(
            decisions[-1].reinvestment.retained_as_cash,
            Money(_coupon(123.0, 184), UAH, prov.EMPTY),
        )


class TestTheRemainderIsRetainedAndNotDiscarded:
    """FR-020: the coupon that could not be spent is still the owner's money."""

    def test_each_period_retains_exactly_the_unbought_remainder(self) -> None:
        # 7 686.301369863014 - 7 000 = 686.301369863014
        # 8 360.657534246575 - 8 000 = 360.657534246575
        # 8 839.246575342466 - 8 000 = 839.246575342466
        # 9 610.849315068493 - 0     = 9 610.849315068493
        plan = fixed_income.coupon_plan(DECLARATION, HOLDING, REINVEST)
        assert len(plan) == len(EXPECTED_PERIODS)
        for period, (paid_on, days, units, bought, retained) in zip(
            plan, EXPECTED_PERIODS, strict=True
        ):
            assert period.paid_on == paid_on
            assert period.units_held == units
            assert period.reinvestment.units_bought == bought
            assert_money_close(period.coupon, Money(_coupon(units, days), UAH, prov.EMPTY))
            assert_money_close(
                period.reinvestment.retained_as_cash, Money(retained, UAH, prov.EMPTY)
            )

    def test_nothing_is_lost_between_the_coupon_the_purchase_and_the_remainder(self) -> None:
        # coupon = spent + retained, for every period. The identity is the whole of FR-020:
        # a remainder that did not satisfy it would be money that vanished.
        for period in fixed_income.coupon_plan(DECLARATION, HOLDING, REINVEST):
            assert_money_close(
                period.coupon,
                Money(
                    period.reinvestment.reinvested.amount
                    + period.reinvestment.retained_as_cash.amount,
                    UAH,
                    prov.EMPTY,
                ),
            )

    def test_the_retained_cash_totals_the_coupons_less_what_was_reinvested(self) -> None:
        # 34 497.05479452055 - 23 000 = 11 497.05479452055
        plan = fixed_income.coupon_plan(DECLARATION, HOLDING, REINVEST)
        retained = sum(period.reinvestment.retained_as_cash.amount for period in plan)
        assert is_close(retained, EXPECTED_COUPON_TOTAL - REINVESTED)
        assert is_close(retained, 11_497.05479452055)


class TestTheTerminalAmountsDiffer:
    """SC-010: the two policies produce different, separately checkable results."""

    def test_reinvesting_leaves_the_coupon_total_and_holding_cash_leaves_two_years_interest(
        self,
    ) -> None:
        # reinvest:   -100 000 + 34 497.05479452055 - 23 000 + 123 000 = 34 497.05479452055
        # hold_cash:  -100 000 + 31 000.00                  + 100 000 = 31 000.00
        reinvested = _projection(REINVEST).ledger.accounts[UAH].balance
        held = _projection(HOLD_CASH).ledger.accounts[UAH].balance
        assert_money_close(reinvested, Money(EXPECTED_COUPON_TOTAL, UAH, prov.EMPTY))
        assert_money_close(reinvested, Money(34_497.05479452055, UAH, prov.EMPTY))
        assert_money_close(held, Money(COUPONS_HELD_AS_CASH, UAH, prov.EMPTY))

    def test_reinvestment_is_worth_three_thousand_four_hundred_and_ninety_seven_hryvnia(
        self,
    ) -> None:
        # 34 497.05479452055 - 31 000.00 = 3 497.05479452055
        difference = (
            _projection(REINVEST).ledger.accounts[UAH].balance.amount
            - _projection(HOLD_CASH).ledger.accounts[UAH].balance.amount
        )
        assert is_close(difference, 3_497.05479452055)

    def test_holding_the_coupons_as_cash_leaves_the_holding_flat_at_a_hundred_units(
        self,
    ) -> None:
        # The counterfactual, so the comparison above is between two stated schedules and
        # not between one schedule and a remembered number.
        rows = _projection(HOLD_CASH).schedule.rows
        assert [row.kind for row in rows] == [
            EventKind.PURCHASE,
            EventKind.COUPON,
            EventKind.COUPON,
            EventKind.COUPON,
            EventKind.COUPON,
            EventKind.PRINCIPAL_REPAYMENT,
        ]
        assert is_close(sum(_rows(HOLD_CASH, EventKind.COUPON)), COUPONS_HELD_AS_CASH)
        assert rows[-1].quantity == QUANTITY

    def test_the_extra_principal_is_exactly_what_was_reinvested(self) -> None:
        # 123 000 - 100 000 = 23 000 = the three reinvestments. Every unit was bought at
        # par and redeemed at par, which is why the terminal cash is the interest alone.
        reinvest_principal = _rows(REINVEST, EventKind.PRINCIPAL_REPAYMENT)[0]
        cash_principal = _rows(HOLD_CASH, EventKind.PRINCIPAL_REPAYMENT)[0]
        assert is_close(reinvest_principal - cash_principal, REINVESTED)
        assert is_close(sum(_rows(REINVEST, EventKind.REINVESTMENT)), -REINVESTED)


class TestTheLedgerStillBalancesAndTheTaxIsStillZero:
    """Reinvestment must not quietly break what D1 established."""

    def test_the_coupons_of_the_growing_holding_sum_to_the_hand_computed_total(self) -> None:
        assert is_close(sum(_rows(REINVEST, EventKind.COUPON)), EXPECTED_COUPON_TOTAL)
        assert is_close(EXPECTED_COUPON_TOTAL, 34_497.05479452055)

    def test_total_tax_is_exactly_zero_under_the_exempt_class(self) -> None:
        # Five charges again -- four coupons and the redemption. A reinvestment is not
        # income and is not charged; it is money going out.
        result = _projection(REINVEST)
        assert result.hurdle.total_tax.amount == 0.0
        assert len(result.charges) == 5

    def test_the_redemption_realises_no_gain_because_every_lot_was_bought_at_par(self) -> None:
        # Basis 100 000 + 23 000 = 123 000 against proceeds of 123 000.
        (disposal,) = _projection(REINVEST).ledger.disposals
        assert_money_close(disposal.consumed_basis_base_ccy, Money(123_000.0, UAH, prov.EMPTY))
        assert_money_close(disposal.realised_gain_base_ccy, Money(0.0, UAH, prov.EMPTY))

    def test_every_reinvested_lot_is_recorded_with_its_own_acquisition_date(self) -> None:
        # Four lots: the purchase and three reinvestments. Each one is traceable to the
        # coupon date that funded it, which is what makes a later disposal's basis
        # attributable rather than averaged.
        (disposal,) = _projection(REINVEST).ledger.disposals
        assert [units for _, units in disposal.consumed_from] == [100.0, 7.0, 8.0, 8.0]

    def test_the_unverified_terms_still_mark_the_figure(self) -> None:
        assert prov.is_unverified(_projection(REINVEST).hurdle.provenance)
        assert TERMS_SOURCE in _projection(REINVEST).hurdle.provenance.sources
