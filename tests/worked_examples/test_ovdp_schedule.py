"""D1 -- a synthetic OVDP issue held to maturity, with every figure worked out by hand.

**The issue below is SYNTHETIC. Its terms are invented, not observed.** The real
OVDP issue's yield, maturity and coupon terms are not confirmed
(``SIMULATOR_SPEC.md`` §11 item 2, restated in spec.md's Assumptions), so nothing here
claims to describe a bond anyone can buy. That is legitimate and deliberate: this test
checks the *engine's arithmetic*, not the market. Every term is stated in this file, in
one place, so a reader can check the whole schedule on a calculator without opening
another document. The real issue arrives later as a declaration file carrying its own
provenance, and nothing about it is invented to make this example work.

The fixture's source ref says so in its citation, and its ``verified_on`` is empty, so
every figure derived from it carries the unverified mark -- which is the honest state of
affairs and is asserted here rather than worked around.

**What this closes**: D1 in ``docs/REQUIRED_TESTS.md``, SC-001 (every cash flow matches
an independently hand-computed schedule within the single project tolerance) and SC-002
(the total tax over the life of an exempt holding is *exactly* zero).

**The arithmetic, once, so the assertions below can refer to it.**

Terms: face 1 000.00 UAH per unit, coupon 15.5% per annum, issued 2026-01-15, maturing
2028-01-15, semiannual coupons, ``act/365`` day count, ``following`` business-day rule.
The purchase is 10 units at par on the issue date, so 10 000.00 UAH of notional and
10 000.00 UAH of cost.

Coupon dates come from the declared periodicity, stepping back from maturity in
six-month strides: 2028-01-15, 2027-07-15, 2027-01-15, 2026-07-15. The next stride back
lands on the issue date itself, which pays no coupon, so the schedule is those four
dates in ascending order.

Accrual periods, counted month by month on the *unadjusted* dates:

* 2026-01-15 -> 2026-07-15: 31 + 28 + 31 + 30 + 31 + 30 = 181 days  (2026 is not a leap year)
* 2026-07-15 -> 2027-01-15: 31 + 31 + 30 + 31 + 30 + 31 = 184 days
* 2027-01-15 -> 2027-07-15: 31 + 28 + 31 + 30 + 31 + 30 = 181 days  (2027 is not a leap year)
* 2027-07-15 -> 2028-01-15: 31 + 31 + 30 + 31 + 30 + 31 = 184 days

181 + 184 + 181 + 184 = 730 days = exactly two ``act/365`` years, which is the check
that no period was dropped or double-counted.

A year of interest on 10 000.00 of notional at 15.5% is 1 550.00 UAH, so each coupon is
1 550.00 x (days / 365):

* 1 550.00 x 181/365 =   768.6301369863014 UAH
* 1 550.00 x 184/365 =   781.3698630136986 UAH
* 1 550.00 x 181/365 =   768.6301369863014 UAH
* 1 550.00 x 184/365 =   781.3698630136986 UAH
* total                = 3 100.00 UAH, i.e. exactly two years of interest

2028-01-15 is a **Saturday** (2026-01-01 was a Thursday; 2027-01-01 a Friday; 2028-01-01
a Saturday, and the 15th is two weeks later). The declared ``following`` rule therefore
moves the final coupon *and* the principal repayment to Monday **2028-01-17**. The
accrual is measured on the unadjusted date, so the coupon amount is unchanged -- only the
payment date moves. That is what makes this fixture worth using: it exercises FR-021's
requirement that the schedule state the convention it applied.

Tax: the holding declares the exempt class on both coupon income and disposal gain, so
five charges are recorded -- four coupons and the redemption -- each of them zero and
each citing the exemption. The redemption's gain is zero besides: 10 units bought for
10 000.00 are redeemed for 10 000.00.
"""

from __future__ import annotations

from datetime import date

import pytest

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
from terezy.core.primitives.rates import NominalRate, RealTermsUnavailable
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results import project
from terezy.core.results.hurdle import HurdleRate
from terezy.core.results.project import Projection
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from terezy.core.tax.schedule import RateEntry

pytestmark = pytest.mark.worked_example

UAH = Currency.UAH

# --- the fixture's sources ------------------------------------------------------------
#
# Both are unverified, which is not an oversight: the terms are invented and the tax
# exemption has not been checked against primary legislation. FR-014 requires the field
# to be present and permits it to be empty; FR-015 then requires every derived figure to
# carry the mark, which the last test in this module asserts.

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
    citation="SYNTHETIC FIXTURE -- minimum ticket invented for this example.",
    retrieved_on=date(2026, 8, 21),
    verified_on=None,
)

EXEMPTION_SOURCE = SourceRef(
    id="synthetic:ua:government_bond",
    citation=(
        "SYNTHETIC FIXTURE standing in for the cited exemption; the real citation "
        "arrives with data/tax/ua.toml."
    ),
    retrieved_on=date(2026, 8, 21),
    verified_on=None,
)

PURCHASE_SOURCE = SourceRef(
    id="synthetic:owner:purchase",
    citation="Owner-stated purchase for this example.",
    retrieved_on=date(2026, 8, 21),
    verified_on=None,
)

TERMS_PROVENANCE = prov.of([TERMS_SOURCE])

# --- the fixture ----------------------------------------------------------------------

FACE_VALUE = Money(1000.0, UAH, TERMS_PROVENANCE)
COUPON_RATE = 0.155
ISSUE_DATE = date(2026, 1, 15)
MATURITY_DATE = date(2028, 1, 15)
ADJUSTED_MATURITY = date(2028, 1, 17)  # 2028-01-15 is a Saturday; "following" -> Monday

TERMS = BondTerms(
    face_value=FACE_VALUE,
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

QUANTITY = 10.0
COST = Money(10_000.0, UAH, prov.of([PURCHASE_SOURCE]))

HOLDING = Holding(
    owner_id="owner-1",
    instrument_id=DECLARATION.id,
    quantity=QUANTITY,
    purchased_on=ISSUE_DATE,
    cost=COST,
)

HORIZON = DateRange(start=ISSUE_DATE, end=date(2028, 1, 31))
# Coupons are held as cash, so this example is the contractual schedule and nothing
# else: what the bond pays, not what a policy does with it afterwards. The reinvesting
# policy is D2's subject (tests/worked_examples/test_coupon_reinvestment.py).
ASSUMPTIONS = Assumptions(consumption_method="fifo", coupon_policy="hold_cash")
TAX_CLASSES = {EXEMPT_CLASS.id: EXEMPT_CLASS}

# --- the hand-computed schedule -------------------------------------------------------
#
# Written as ``1550.0 * days / 365`` rather than as decimal literals copied from a run.
# The day counts are the ones derived in the module docstring, so a reader checks the
# convention rather than checking that the code still does what it did last time.

ANNUAL_INTEREST = 1550.0  # 10 units x 1 000.00 face x 15.5%

EXPECTED_COUPONS: tuple[tuple[date, int], ...] = (
    (date(2026, 7, 15), 181),
    (date(2027, 1, 15), 184),
    (date(2027, 7, 15), 181),
    (ADJUSTED_MATURITY, 184),
)


def _coupon_amount(days: int) -> float:
    return ANNUAL_INTEREST * days / 365


def _projection() -> Projection:
    outcome = project.project(
        DECLARATION,
        HOLDING,
        HORIZON,
        ASSUMPTIONS,
        tax_classes=TAX_CLASSES,
    )
    assert isinstance(outcome, Projection), f"expected a projection, got {outcome!r}"
    return outcome


class TestTheScheduleToMaturity:
    """Every cash flow, against arithmetic worked out on paper (D1, SC-001)."""

    def test_the_schedule_is_a_purchase_four_coupons_and_the_principal(self) -> None:
        # Six rows, not five: the final coupon and the redemption fall on the same
        # adjusted date but are different events, and merging them would hide the
        # coupon inside the principal.
        rows = _projection().schedule.rows
        assert [row.kind for row in rows] == [
            EventKind.PURCHASE,
            EventKind.COUPON,
            EventKind.COUPON,
            EventKind.COUPON,
            EventKind.COUPON,
            EventKind.PRINCIPAL_REPAYMENT,
        ]

    def test_the_purchase_is_the_stated_cost_and_nothing_else(self) -> None:
        # 10 units at 1 000.00 par = 10 000.00 out. Cash out is negative.
        purchase = _projection().schedule.rows[0]
        assert purchase.occurred_on == ISSUE_DATE
        assert_money_close(purchase.gross, Money(-10_000.0, UAH, prov.EMPTY))
        assert_money_close(purchase.net, Money(-10_000.0, UAH, prov.EMPTY))

    def test_each_coupon_matches_its_hand_computed_day_count_fraction(self) -> None:
        # 1 550.00 x 181/365 =   768.6301369863014
        # 1 550.00 x 184/365 =   781.3698630136986
        # 1 550.00 x 181/365 =   768.6301369863014
        # 1 550.00 x 184/365 =   781.3698630136986
        coupons = [row for row in _projection().schedule.rows if row.kind is EventKind.COUPON]
        assert len(coupons) == len(EXPECTED_COUPONS)
        for row, (expected_date, days) in zip(coupons, EXPECTED_COUPONS, strict=True):
            assert row.occurred_on == expected_date
            assert_money_close(row.gross, Money(_coupon_amount(days), UAH, prov.EMPTY))

    def test_the_coupons_sum_to_exactly_two_years_of_interest(self) -> None:
        # 181 + 184 + 181 + 184 = 730 days = 2 x 365, so the four coupons must come to
        # 2 x 1 550.00 = 3 100.00. This is the check that no accrual period was dropped,
        # double-counted, or measured from the adjusted rather than the unadjusted date.
        coupons = [row for row in _projection().schedule.rows if row.kind is EventKind.COUPON]
        assert sum(days for _, days in EXPECTED_COUPONS) == 730
        total = sum(row.gross.amount for row in coupons)
        assert is_close(total, 2 * ANNUAL_INTEREST)

    def test_the_final_coupon_and_the_principal_move_to_the_following_business_day(
        self,
    ) -> None:
        # 2028-01-15 is a Saturday, so the declared "following" rule pays on Monday
        # 2028-01-17. The accrual is still measured 2027-07-15 -> 2028-01-15 = 184 days,
        # so only the date moved.
        assert MATURITY_DATE.weekday() == 5  # Saturday
        rows = _projection().schedule.rows
        assert rows[-2].occurred_on == ADJUSTED_MATURITY
        assert rows[-1].occurred_on == ADJUSTED_MATURITY
        assert_money_close(rows[-2].gross, Money(_coupon_amount(184), UAH, prov.EMPTY))

    def test_the_principal_repayment_returns_face_value_per_unit(self) -> None:
        # 10 units x 1 000.00 = 10 000.00 in, and 10 units surrendered.
        principal = _projection().schedule.rows[-1]
        assert_money_close(principal.gross, Money(10_000.0, UAH, prov.EMPTY))
        assert principal.quantity == QUANTITY

    def test_the_schedule_states_the_conventions_it_applied(self) -> None:
        # FR-021: the produced schedule must say which conventions placed its dates,
        # rather than leaving a reader to assume the engine's favourite.
        for row in _projection().schedule.rows:
            assert row.conventions.periodicity == "semiannual"
            assert row.conventions.day_count == "act/365"
            assert row.conventions.business_day_rule == "following"


class TestTheTaxIsExactlyZero:
    """SC-002: exactly zero over the whole life, and every zero cites the exemption."""

    def test_total_tax_is_exactly_zero_not_approximately_zero(self) -> None:
        # Five charges of zero sum to zero exactly; no tolerance is involved and none
        # should be, because "approximately exempt" is not a thing.
        result = _projection()
        assert result.hurdle.total_tax.amount == 0.0
        assert result.hurdle.total_tax.currency is UAH

    def test_a_charge_is_recorded_for_every_taxable_event(self) -> None:
        # Four coupons and one disposal. A missing charge would be indistinguishable
        # from a rule that never ran, which is why zero is recorded rather than skipped.
        charges = _projection().charges
        assert len(charges) == 5
        assert all(charge.total.amount == 0.0 for charge in charges)
        assert all(charge.pit.amount == 0.0 for charge in charges)
        assert all(charge.levy.amount == 0.0 for charge in charges)

    def test_every_zero_charge_cites_the_exemption_it_applied(self) -> None:
        # The evidence that the exemption was applied is the zero *carrying its source*.
        for charge in _projection().charges:
            assert charge.tax_class_id == EXEMPT_CLASS.id
            assert EXEMPTION_SOURCE in charge.provenance.sources
            assert EXEMPTION_SOURCE in charge.pit.provenance.sources
            assert EXEMPTION_SOURCE in charge.levy.provenance.sources

    def test_the_disposal_gain_is_zero_because_the_bond_redeems_at_par(self) -> None:
        # 10 000.00 of proceeds against 10 000.00 of basis: no gain, so nothing to tax
        # even if the class were not exempt.
        disposals = _projection().ledger.disposals
        assert len(disposals) == 1
        assert_money_close(disposals[0].realised_gain_base_ccy, Money(0.0, UAH, prov.EMPTY))

    def test_the_net_of_every_row_equals_its_gross_under_the_exemption(self) -> None:
        for row in _projection().schedule.rows:
            assert row.tax.amount == 0.0
            assert_money_close(row.net, row.gross)


class TestTheHurdleRate:
    """The number the feature exists to produce (FR-004, FR-005, FR-022)."""

    def test_the_returned_yield_discounts_the_hand_listed_flows_to_the_cost(self) -> None:
        # The yield is a root, so it cannot be written down as a closed form and checked
        # against a decimal literal. What *can* be checked by hand is the identity that
        # defines it: at the returned rate, the present value of the receipts listed in
        # this module's docstring equals the 10 000.00 that was paid.
        #
        # Times are measured act/365 from the purchase date, on the *payment* dates:
        #   2026-07-15 -> 181 days
        #   2027-01-15 -> 365 days
        #   2027-07-15 -> 546 days   (365 + 181)
        #   2028-01-17 -> 732 days   (365 + 365, plus the two days the Saturday moved)
        rate = _projection().hurdle.nominal_ytm.value
        flows = (
            (181, _coupon_amount(181)),
            (365, _coupon_amount(184)),
            (546, _coupon_amount(181)),
            (732, _coupon_amount(184) + 10_000.0),
        )
        present_value = sum(amount / (1.0 + rate) ** (days / 365) for days, amount in flows)
        assert is_close(present_value, 10_000.0)

    def test_the_yield_is_the_semiannual_coupon_compounded_within_a_percentage_point(
        self,
    ) -> None:
        # A sanity band, not a second definition of the answer. Two half-year coupons of
        # 15.5% simple compound to roughly
        #   (1 + 0.155 x 181/365) x (1 + 0.155 x 184/365) - 1
        #   = 1.0768630... x 1.0781369... - 1 = 0.16093...
        # The engine's figure is a little lower because the final payment arrives two
        # days late, so the band is deliberately loose and is *stated* as loose rather
        # than dressed up as the project tolerance (FR-002).
        approximate = (1 + 0.155 * 181 / 365) * (1 + 0.155 * 184 / 365) - 1
        rate = _projection().hurdle.nominal_ytm.value
        assert approximate - 0.01 < rate < approximate

    def test_the_contractual_yield_and_the_after_tax_return_coincide_when_tax_is_zero(
        self,
    ) -> None:
        # They are computed on different series -- the contractual gross flows and the
        # flows actually received net of tax -- and are reported as separate figures
        # (FR-005). Under a 0% class the two series are identical, so the figures must
        # agree; if they did not, one of them would not be what it claims to be.
        result = _projection()
        assert isinstance(result.hurdle.nominal_ytm, NominalRate)
        assert isinstance(result.hurdle.nominal_cash_flow_return, NominalRate)
        assert is_close(
            result.hurdle.nominal_ytm.value,
            result.hurdle.nominal_cash_flow_return.value,
        )

    def test_the_figure_is_nominal_and_says_what_it_leaves_out(self) -> None:
        # Principle VI forbids presenting a per-instrument access cost, so the figure
        # states its own boundaries instead of letting a reader assume it is
        # comparison-ready.
        hurdle: HurdleRate = _projection().hurdle
        assert isinstance(hurdle.real, RealTermsUnavailable)
        assert "inflation" in hurdle.real.reason
        assert hurdle.excludes
        assert any("inflation" in item for item in hurdle.excludes)
        assert any("route" in item for item in hurdle.excludes)

    def test_the_unverified_terms_mark_the_figure(self) -> None:
        # The fixture's terms have no verification date, so the hurdle rate rests on an
        # unverified input and says so. This is the expected first-run state, and the
        # full propagation check is E5's job.
        hurdle = _projection().hurdle
        assert prov.is_unverified(hurdle.provenance)
        assert TERMS_SOURCE in hurdle.provenance.sources
        assert EXEMPTION_SOURCE in hurdle.provenance.sources


class TestAPurchaseAfterTheIssueDate:
    """A holder who buys mid-life receives only the coupons dated after the purchase."""

    def test_only_the_coupons_after_the_purchase_date_are_paid_to_this_holder(
        self,
    ) -> None:
        # Bought 2026-08-01, after the 2026-07-15 coupon has already been paid to
        # somebody else. Three coupons remain: 2027-01-15, 2027-07-15 and the adjusted
        # 2028-01-17.
        #
        # The 2027-01-15 coupon is paid in full, for its whole 184-day accrual period,
        # even though this holder held the bond for only part of it. Accrued interest
        # settled at purchase is a secondary-market mechanic that this feature does not
        # model (spec.md, "Hold-to-maturity only"); it is stated here rather than
        # approximated, because a partial first coupon computed from an unmodelled
        # settlement would be a number with nothing behind it.
        holding = Holding(
            owner_id="owner-1",
            instrument_id=DECLARATION.id,
            quantity=QUANTITY,
            purchased_on=date(2026, 8, 1),
            cost=COST,
        )
        outcome = project.project(
            DECLARATION,
            holding,
            DateRange(start=date(2026, 8, 1), end=date(2028, 1, 31)),
            ASSUMPTIONS,
            tax_classes=TAX_CLASSES,
        )
        assert isinstance(outcome, Projection)
        coupons = [row for row in outcome.schedule.rows if row.kind is EventKind.COUPON]
        assert [row.occurred_on for row in coupons] == [
            date(2027, 1, 15),
            date(2027, 7, 15),
            ADJUSTED_MATURITY,
        ]
        assert_money_close(coupons[0].gross, Money(_coupon_amount(184), UAH, prov.EMPTY))
