"""**E1** by hand: one fund, one run, two tax classes that never touch each other.

SC-001. A distribution is charged under the fund-distribution class and a redemption of
**the same units** under investment profit, in one projection, with the arithmetic for
every charge and every per-class subtotal written out here beside the assertion.

**The fund is a SYNTHETIC FIXTURE and every term in it is invented**, following 001's
precedent and the specification's own Assumptions: these tests check the engine's
arithmetic, not Inzhur. The rates are the real declared ones from ``data/tax/ua.toml``
because the *split* is the thing under test, and 9% + 5% against 18% + 5% is the split
that exists.

---

## The fixture

| Term | Value |
|---|---|
| NAV per unit | 100.00 UAH |
| units bought | 50 |
| declared yield | 12% a year, simple |
| payout share | 0.5 — half is paid out monthly, half accretes to NAV |
| day count | 30/360, so six months is exactly half a year |
| entry markup | live 1%, maximum 2% |
| exit discount | live 0%, maximum 3% |
| settlement | practice same day, legal 5 business days |
| purchased | 2027-01-15 |
| exit requested | 2027-07-15 |

## The practice-mode run, by hand

**Purchase.** 50 units at NAV plus the live 1% markup:

    price  = 100.00 x 1.01 = 101.00 per unit
    cost   = 101.00 x 50   = 5 050.00 out
    spread = 100.00 x 0.01 x 50 = 50.00 of that is markup

**Distributions.** Half of 12% a year is paid out, so each month pays a twelfth of 6% of
the declared NAV:

    per unit  = 100.00 x 0.06 / 12 = 0.50
    per month = 0.50 x 50          = 25.00

The first whole month after the purchase is February, paid on the 10th of March; the last
one entitled before the exit executes on 2027-07-15 is June, paid 2027-07-10. Five
payments:

    2027-03-10, 2027-04-10, 2027-05-10, 2027-06-10, 2027-07-10
    5 x 25.00 = 125.00 gross

Each is charged under **`ua_ci_fund_distribution`** at 9% + 5%:

    PIT  = 25.00 x 0.09 = 2.25      -> 5 x 2.25 = 11.25
    levy = 25.00 x 0.05 = 1.25      -> 5 x 1.25 =  6.25
    tax  = 3.50 each                -> 5 x 3.50 = 17.50

**NAV at the exit.** Half of the 12% is retained, and 30/360 makes 2027-01-15 to
2027-07-15 exactly half a year:

    nav = 100.00 x (1 + 0.06 x 0.5) = 103.00

**Exit.** The practice mode buys back at NAV, same day, no discount:

    proceeds = 103.00 x 50 = 5 150.00
    gain     = 5 150.00 - 5 050.00 = 100.00

Charged under **`ua_investment_profit`** at 18% + 5% on the *gain*, never on the proceeds:

    PIT  = 100.00 x 0.18 = 18.00
    levy = 100.00 x 0.05 =  5.00
    tax  = 23.00

**The two subtotals, which is the whole point:**

| Class | PIT | Levy | Total | Charges |
|---|---|---|---|---|
| `ua_ci_fund_distribution` | 11.25 | 6.25 | 17.50 | 5 |
| `ua_investment_profit` | 18.00 | 5.00 | 23.00 | 1 |
| | | | **40.50** | 6 |

    net = -5 050.00 + 125.00 - 17.50 + 5 150.00 - 23.00 = 184.50

## The legal-terms run, for contrast

Maximum markup and maximum discount, settled five business days later:

    cost     = 100.00 x 1.02 x 50 = 5 100.00
    proceeds = 103.00 x 0.97 x 50 = 4 995.50
    gain     = 4 995.50 - 5 100.00 = -104.50   -- a loss

A loss charges **exactly zero**, never a negative tax, and the loss is reported with the
statement that carryforward is not modelled here (FR-008).
"""

from __future__ import annotations

from datetime import date
from typing import Final

import pytest

from terezy.core.instruments import fund
from terezy.core.instruments.fund import (
    DeclaredYield,
    DistributionTerms,
    FundDeclaration,
    LegalTerms,
    LiquidityTerms,
    ObservedPractice,
    SpreadTerms,
)
from terezy.core.instruments.interface import DateRange, Holding
from terezy.core.ledger.events import EventKind
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import fund as fund_results
from terezy.core.results.fund import FundAssumptions, FundProjection
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from terezy.core.tax.schedule import RateEntry

pytestmark = pytest.mark.worked_example

UAH: Final = Currency.UAH

NAV: Final = 100.00
UNITS: Final = 50.0
YIELD: Final = 0.12
PAYOUT_SHARE: Final = 0.5
LIVE_MARKUP: Final = 0.01
MAX_MARKUP: Final = 0.02
LIVE_DISCOUNT: Final = 0.0
MAX_DISCOUNT: Final = 0.03

PURCHASED_ON: Final = date(2027, 1, 15)
EXIT_ON: Final = date(2027, 7, 15)
TERMINATES_ON: Final = date(2032, 1, 15)
HORIZON_END: Final = date(2027, 12, 31)

DISTRIBUTION_CLASS: Final = "ua_ci_fund_distribution"
DISPOSAL_CLASS: Final = "ua_investment_profit"

# --- the hand-computed figures, written as their arithmetic ---------------------------

PRACTICE_COST: Final = NAV * (1.0 + LIVE_MARKUP) * UNITS  # 5 050.00
ENTRY_SPREAD: Final = NAV * LIVE_MARKUP * UNITS  # 50.00
PER_MONTH: Final = NAV * YIELD * PAYOUT_SHARE / 12.0 * UNITS  # 25.00
PAYMENT_DATES: Final = (
    date(2027, 3, 10),
    date(2027, 4, 10),
    date(2027, 5, 10),
    date(2027, 6, 10),
    date(2027, 7, 10),
)
GROSS_DISTRIBUTIONS: Final = PER_MONTH * len(PAYMENT_DATES)  # 125.00
NAV_AT_EXIT: Final = NAV * (1.0 + YIELD * (1.0 - PAYOUT_SHARE) * 0.5)  # 103.00
PRACTICE_PROCEEDS: Final = NAV_AT_EXIT * UNITS  # 5 150.00
PRACTICE_GAIN: Final = PRACTICE_PROCEEDS - PRACTICE_COST  # 100.00

DISTRIBUTION_PIT: Final = PER_MONTH * 0.09 * len(PAYMENT_DATES)  # 11.25
DISTRIBUTION_LEVY: Final = PER_MONTH * 0.05 * len(PAYMENT_DATES)  # 6.25
DISTRIBUTION_TAX: Final = DISTRIBUTION_PIT + DISTRIBUTION_LEVY  # 17.50
DISPOSAL_PIT: Final = PRACTICE_GAIN * 0.18  # 18.00
DISPOSAL_LEVY: Final = PRACTICE_GAIN * 0.05  # 5.00
DISPOSAL_TAX: Final = DISPOSAL_PIT + DISPOSAL_LEVY  # 23.00
TOTAL_TAX: Final = DISTRIBUTION_TAX + DISPOSAL_TAX  # 40.50
NET: Final = (
    -PRACTICE_COST + GROSS_DISTRIBUTIONS - DISTRIBUTION_TAX + PRACTICE_PROCEEDS - DISPOSAL_TAX
)  # 184.50

LEGAL_COST: Final = NAV * (1.0 + MAX_MARKUP) * UNITS  # 5 100.00
LEGAL_PROCEEDS: Final = NAV_AT_EXIT * (1.0 - MAX_DISCOUNT) * UNITS  # 4 995.50
LEGAL_LOSS: Final = LEGAL_COST - LEGAL_PROCEEDS  # 104.50


def _fixture_source(what: str) -> Provenance:
    return prov.of(
        [
            SourceRef(
                id=f"fixture:fund:{what}",
                citation=f"SYNTHETIC FIXTURE — invented {what}. Not observed from any fund.",
                retrieved_on=date(2026, 8, 23),
                verified_on=None,
            )
        ]
    )


def _rates(pit: float, levy: float, name: str) -> tuple[RateEntry, ...]:
    return (
        RateEntry(
            effective_from=date(2026, 6, 30),
            pit_rate=pit,
            levy_rate=levy,
            provenance=_fixture_source(f"rate entry for {name}"),
        ),
    )


def _tax_pack() -> dict[str, TaxClass]:
    """The two real classes' shapes, with fixture citations: the *split* is the subject."""
    return {
        DISTRIBUTION_CLASS: TaxClass(
            id=DISTRIBUTION_CLASS,
            applies_to=frozenset({TaxableEventKind.DISTRIBUTION}),
            rates=_rates(0.09, 0.05, DISTRIBUTION_CLASS),
        ),
        DISPOSAL_CLASS: TaxClass(
            id=DISPOSAL_CLASS,
            applies_to=frozenset({TaxableEventKind.DISPOSAL_GAIN}),
            rates=_rates(0.18, 0.05, DISPOSAL_CLASS),
        ),
    }


def _declaration() -> FundDeclaration:
    return FundDeclaration(
        id="synthetic_fund_worked_example",
        name="Synthetic distributing fund — TEST FIXTURE, terms invented",
        unit_currency=UAH,
        is_assumption_driven=True,
        nav_per_unit=Money(NAV, UAH, _fixture_source("NAV per unit")),
        day_count="30/360",
        declared_yield=DeclaredYield(
            low=YIELD,
            high=YIELD,
            basis="simple_annual",
            provenance=_fixture_source("declared yield"),
        ),
        distribution=DistributionTerms(
            frequency="monthly",
            basis_note="FIXTURE — a declared monthly payout, not a share of anything real",
            record_day="last_day_of_month",
            payment_day=10,
            paid_in=UAH,
            peg=None,
            payout_share=PAYOUT_SHARE,
            provenance=_fixture_source("distribution terms"),
        ),
        spread=SpreadTerms(
            entry_markup_max=MAX_MARKUP,
            exit_discount_max=MAX_DISCOUNT,
            live_entry_markup=LIVE_MARKUP,
            live_exit_discount=LIVE_DISCOUNT,
            provenance=_fixture_source("spread terms"),
        ),
        liquidity=LiquidityTerms(
            legal=LegalTerms(
                buyback_before_termination="discretionary",
                settlement_business_days=5,
                note="FIXTURE — an invented legal settlement delay.",
                provenance=_fixture_source("legal terms"),
            ),
            practice=ObservedPractice(
                settlement_business_days=0,
                is_revocable=True,
                note="FIXTURE — an invented same-day buyback practice.",
                provenance=_fixture_source("observed practice"),
            ),
        ),
        minimum_units=1.0,
        subscription_cutoff=None,
        terminates_on=TERMINATES_ON,
        tax_classes={
            TaxableEventKind.DISTRIBUTION: DISTRIBUTION_CLASS,
            TaxableEventKind.DISPOSAL_GAIN: DISPOSAL_CLASS,
        },
        fee_context=(),
        verification_tasks=(),
    )


def _assumptions(mode: fund.LiquidityMode) -> FundAssumptions:
    return FundAssumptions(
        liquidity_mode=mode,
        buyback="available",
        exit_on=EXIT_ON,
        yield_point=None,
        exchange_rate=None,
        consumption_method="fifo",
    )


def _projected(mode: fund.LiquidityMode) -> FundProjection:
    outcome = fund_results.project_fund(
        _declaration(),
        Holding(
            owner_id="owner-1",
            instrument_id="synthetic_fund_worked_example",
            quantity=UNITS,
            purchased_on=PURCHASED_ON,
            cost=Money(PRACTICE_COST, UAH, prov.EMPTY),
        ),
        DateRange(start=PURCHASED_ON, end=HORIZON_END),
        _assumptions(mode),
        tax_classes=_tax_pack(),
    )
    assert isinstance(outcome, FundProjection), f"expected a projection, got {outcome!r}"
    return outcome


class TestTheDistributionsAreTheHandComputedOnes:
    """Checked before any tax, so a tax assertion cannot pass against a wrong payout."""

    def test_five_payments_on_the_declared_dates(self) -> None:
        lines = _projected("practice").distributions
        assert tuple(line.paid_on for line in lines) == PAYMENT_DATES

    def test_each_payment_is_a_twelfth_of_the_paid_out_half_of_the_yield(self) -> None:
        # 100.00 x 0.06 / 12 x 50 = 25.00
        for line in _projected("practice").distributions:
            assert is_close(line.gross.amount, PER_MONTH)

    def test_the_first_part_month_pays_nothing_because_no_pro_rating_is_declared(self) -> None:
        """January is not paid: the purchase settles mid-month and no pro-rating exists.

        The fund's documents state no rule for a part month, so none is invented -- a part
        month simply does not pay, which is stated in ``fund.distribution_dates`` and in
        ``docs/METHODOLOGY.md`` rather than quietly assumed either way.
        """
        assert date(2027, 2, 10) not in {
            line.paid_on for line in _projected("practice").distributions
        }


class TestTheTwoClassesInOneRun:
    """SC-001 and FR-006: each event under its own declared class, and never the other's."""

    def test_the_distribution_subtotal_is_the_hand_computed_one(self) -> None:
        # PIT 11.25, levy 6.25, total 17.50, over five charges.
        (subtotal,) = [
            item
            for item in _projected("practice").tax_by_class
            if item.tax_class_id == DISTRIBUTION_CLASS
        ]
        assert subtotal.charge_count == len(PAYMENT_DATES)
        assert is_close(subtotal.pit.amount, DISTRIBUTION_PIT)
        assert is_close(subtotal.levy.amount, DISTRIBUTION_LEVY)
        assert is_close(subtotal.total_charged.amount, DISTRIBUTION_TAX)
        assert subtotal.kinds == (TaxableEventKind.DISTRIBUTION,)

    def test_the_disposal_subtotal_is_the_hand_computed_one(self) -> None:
        # PIT 18.00, levy 5.00, total 23.00, on one charge -- and on the *gain*, not the
        # proceeds: 23% of 5 150.00 would be 1 184.50, which is the mistake this checks.
        (subtotal,) = [
            item
            for item in _projected("practice").tax_by_class
            if item.tax_class_id == DISPOSAL_CLASS
        ]
        assert subtotal.charge_count == 1
        assert is_close(subtotal.pit.amount, DISPOSAL_PIT)
        assert is_close(subtotal.levy.amount, DISPOSAL_LEVY)
        assert is_close(subtotal.total_charged.amount, DISPOSAL_TAX)
        assert subtotal.kinds == (TaxableEventKind.DISPOSAL_GAIN,)

    def test_the_two_subtotals_sum_to_the_total_and_nothing_else_does(self) -> None:
        projection = _projected("practice")
        assert len(projection.tax_by_class) == 2
        assert is_close(projection.total_tax.amount, TOTAL_TAX)
        assert is_close(
            sum(item.total_charged.amount for item in projection.tax_by_class), TOTAL_TAX
        )

    def test_neither_class_ever_charges_the_other_kind_of_event(self) -> None:
        """FR-007's prohibition, checked against the *events* rather than the counts.

        A run that charged the right number of events under the wrong classes would pass a
        count. This maps each charge back to the ledger event it was charged on.
        """
        projection = _projected("practice")
        kind_of = {event.sequence: event.kind for event in projection.ledger.applied}
        for charge in projection.charges:
            expected = (
                DISTRIBUTION_CLASS
                if kind_of[charge.event_sequence] is EventKind.DISTRIBUTION
                else DISPOSAL_CLASS
            )
            assert charge.tax_class_id == expected

    def test_every_tax_figure_names_its_class_its_source_and_its_verification_date(
        self,
    ) -> None:
        """FR-002 and SC-001's last clause: the mark reaches every charge, and says why."""
        for subtotal in _projected("practice").tax_by_class:
            assert subtotal.tax_class_id
            assert subtotal.provenance.sources, "a charge with no citation cites nothing"
            assert prov.is_unverified(subtotal.provenance), (
                "the fixture's rate entries carry an empty verification date, so every "
                "figure derived from them must be marked"
            )

    def test_each_distribution_line_names_the_dated_entry_that_taxed_it(self) -> None:
        for line in _projected("practice").distributions:
            assert line.rate_effective_from == date(2026, 6, 30)
            assert line.tax_class_id == DISTRIBUTION_CLASS


class TestTheDisposalBaseIsTheGain:
    """FR-008: proceeds actually received, less the basis consumed, less allocated fees."""

    def test_the_gain_is_proceeds_minus_the_cost_of_the_units(self) -> None:
        # 5 150.00 - 5 050.00 = 100.00
        exit_line = _projected("practice").exit_line
        assert exit_line is not None
        assert is_close(exit_line.gross_proceeds.amount, PRACTICE_PROCEEDS)
        assert is_close(exit_line.realised_gain.amount, PRACTICE_GAIN)
        assert is_close(exit_line.taxable_base.amount, PRACTICE_GAIN)

    def test_the_nav_at_the_exit_is_the_retained_half_of_the_yield(self) -> None:
        # 100.00 x (1 + 0.06 x 0.5) = 103.00, with 30/360 making the half-year exact.
        exit_line = _projected("practice").exit_line
        assert exit_line is not None
        assert is_close(exit_line.nav_per_unit.amount, NAV_AT_EXIT)

    def test_the_net_outcome_reconciles_with_the_named_lines_and_leaves_no_residue(
        self,
    ) -> None:
        # -5 050.00 + 125.00 - 17.50 + 5 150.00 - 23.00 = 184.50 (SC-012)
        assert is_close(_projected("practice").net_proceeds.amount, NET)


class TestADisposalAtALoss:
    """FR-008: exactly zero, never negative, and the loss is reported with its statement."""

    def test_the_legal_terms_run_realises_the_hand_computed_loss(self) -> None:
        # 4 995.50 - 5 100.00 = -104.50
        exit_line = _projected("legal").exit_line
        assert exit_line is not None
        assert is_close(exit_line.gross_proceeds.amount, LEGAL_PROCEEDS)
        assert is_close(exit_line.realised_gain.amount, -LEGAL_LOSS)

    def test_the_charge_is_exactly_zero_and_never_negative(self) -> None:
        exit_line = _projected("legal").exit_line
        assert exit_line is not None
        assert exit_line.taxable_base.amount == 0.0
        assert exit_line.tax.amount == 0.0

    def test_the_loss_is_reported_with_the_carryforward_statement(self) -> None:
        """A zero charge that hid the loss would be the silent half of FR-008."""
        exit_line = _projected("legal").exit_line
        assert exit_line is not None
        assert exit_line.realised_loss is not None
        assert is_close(exit_line.realised_loss.amount, LEGAL_LOSS)
        assert exit_line.carryforward_note == fund_results.CARRYFORWARD_NOT_MODELLED

    def test_the_zero_still_cites_what_it_was_computed_from(self) -> None:
        """A zero with no provenance is indistinguishable from a rule that never ran."""
        exit_line = _projected("legal").exit_line
        assert exit_line is not None
        assert exit_line.taxable_base.provenance.sources


class TestTheSpreadIsItsOwnLine:
    """FR-024 and SC-012: the erosion is a named line, not a residue in the net figure."""

    def test_the_entry_markup_is_reported_separately_from_the_cost(self) -> None:
        # 100.00 x 0.01 x 50 = 50.00 of the 5 050.00 paid was markup.
        assert is_close(_projected("practice").entry_spread.amount, ENTRY_SPREAD)

    def test_the_practice_exit_gives_up_nothing_and_reports_no_discount_line(self) -> None:
        projection = _projected("practice")
        assert projection.exit_spread.amount == 0.0
        assert projection.exit_discount is None, (
            "there is no discount under the practice mode, and a zero line would suggest "
            "one was applied"
        )

    def test_the_legal_exit_reports_the_discount_as_its_own_line(self) -> None:
        # 103.00 x 0.03 x 50 = 154.50 given up to the declared maximum discount.
        projection = _projected("legal")
        assert projection.exit_discount is not None
        assert is_close(projection.exit_discount.amount, NAV_AT_EXIT * MAX_DISCOUNT * UNITS)

    def test_the_round_trip_is_entry_plus_exit_and_never_one_way(self) -> None:
        # Principle VI: a one-way figure may never be presented as a round trip.
        projection = _projected("legal")
        assert is_close(
            projection.round_trip_spread.amount,
            NAV * MAX_MARKUP * UNITS + NAV_AT_EXIT * MAX_DISCOUNT * UNITS,
        )

    def test_the_gross_distributions_are_the_hand_computed_total(self) -> None:
        # 5 x 25.00 = 125.00, before any tax.
        lines = _projected("practice").distributions
        assert is_close(sum(line.gross.amount for line in lines), GROSS_DISTRIBUTIONS)
        assert is_close(
            sum(line.net.amount for line in lines), GROSS_DISTRIBUTIONS - DISTRIBUTION_TAX
        )
