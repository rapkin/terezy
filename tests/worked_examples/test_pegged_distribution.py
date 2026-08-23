"""The peg by hand: a hryvnia payment sized in dollars, and the ceiling that breaks it.

SC-011 and owner decision A. Ukrainian commercial rent is priced against the dollar and
settled in hryvnia under a «граничний курс» — a ceiling on the rate the lease converts at.
So the REIT's income is *declared* in USD-equivalent terms while every hryvnia of it moves
in hryvnia, and this module checks that arithmetic by hand on a **SYNTHETIC FIXTURE**.

Four things are asserted, and three of them are refusals:

1. a payment sized under the owner's stated rate, matching hand arithmetic;
2. an assumed rate **above** the declared ceiling, sized at the ceiling, with the output
   saying the ceiling bound — the peg partially breaking, kept visible;
3. **no stated rate** — a typed degraded result naming exactly that input, never an
   implicit one;
4. a payment dated **before** the declared ceiling ladder — a typed refusal naming the
   open question, because "no ceiling is declared here" is not "there is no ceiling".

---

## The fixture

| Term | Value |
|---|---|
| NAV per unit | 1 000.00 UAH |
| units | 20 |
| declared yield | 12% a year on the unit's USD-equivalent value, all paid out |
| distributions | monthly, record last day of month, paid on the 5th following |
| peg | sized in USD, ceiling 40.00 UAH per USD from 2027-01-01 |
| purchased | 2027-01-10 |
| exit | 2027-05-10, practice mode, at NAV |
| distribution tax | 9% + 5% = 14% |

## The sizing, written out

The unit's value **in the peg's currency** is its declared NAV over the stated rate, the
month's income is a twelfth of the declared rate on that, and the hryvnia payment is that
term converted at the **lower** of the stated rate and the ceiling:

    per unit in USD = 1 000.00 / rate
    pegged (USD)    = per unit in USD x 20 units x 0.12 / 12
    payment (UAH)   = pegged x min(rate, 40.00)

## Below the ceiling — rate 38.00

    per unit in USD = 1 000.00 / 38.00 = 26.315789...
    pegged          = 26.315789... x 20 x 0.01 = 5.263157... USD
    payment         = 5.263157... x 38.00 = **200.00 UAH**

The rate cancels, which is the point: below the ceiling the hryvnia payment tracks the
dollar exactly, so it is simply 1 000.00 x 20 x 1% — and it does not matter what the owner
assumed.

## Above the ceiling — rate 50.00

    per unit in USD = 1 000.00 / 50.00 = 20.00
    pegged          = 20.00 x 20 x 0.01 = 4.00 USD
    payment         = 4.00 x **40.00** = **160.00 UAH**

    160.00 / 200.00 = 40.00 / 50.00 = 0.8

The hryvnia payment is a fifth smaller. That is the peg partially breaking under a
devaluation the ceiling does not follow, and it is exactly the exposure a hryvnia total
alone would hide.

## Three payments over the holding

February, March and April are the whole months held, paid on 2027-03-05, 2027-04-05 and
2027-05-05 — all before the exit executes on 2027-05-10.

    below the ceiling: 3 x 200.00 = 600.00 gross, tax 3 x 28.00 = 84.00
    above it:          3 x 160.00 = 480.00 gross, tax 3 x 22.40 = 67.20
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Final

import pytest

from terezy.core.errors import CurrencyMismatchError
from terezy.core.instruments import fund
from terezy.core.instruments.fund import (
    CapEntry,
    DeclaredYield,
    DistributionTerms,
    ExchangeRateAssumption,
    FundDeclaration,
    LegalTerms,
    LiquidityTerms,
    ObservedPractice,
    Peg,
    SpreadTerms,
    VerificationTask,
)
from terezy.core.instruments.interface import DateRange, Holding
from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import fund as fund_results
from terezy.core.results.fund import (
    AwaitingVerification,
    FundAssumptions,
    FundProjection,
    PegUnsizable,
)
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from terezy.core.tax.schedule import RateEntry
from tests import synthetic

pytestmark = pytest.mark.worked_example

UAH: Final = Currency.UAH
USD: Final = Currency.USD
FUND_ID: Final = "synthetic_fund_pegged"
DISTRIBUTION_CLASS: Final = "ua_ci_fund_distribution"
DISPOSAL_CLASS: Final = "ua_investment_profit"

NAV: Final = 1_000.00
UNITS: Final = 20.0
YIELD: Final = 0.12
MONTHLY: Final = YIELD / 12.0
CEILING: Final = 40.00
CEILING_FROM: Final = date(2027, 1, 1)

BELOW_THE_CEILING: Final = 38.00
ABOVE_THE_CEILING: Final = 50.00

PURCHASED_ON: Final = date(2027, 1, 10)
EXIT_ON: Final = date(2027, 5, 10)
TERMINATES_ON: Final = date(2035, 1, 1)
HORIZON_END: Final = date(2027, 12, 31)

PAYMENT_DATES: Final = (date(2027, 3, 5), date(2027, 4, 5), date(2027, 5, 5))

UNCAPPED_PAYMENT: Final = NAV * UNITS * MONTHLY  # 200.00
CAPPED_PAYMENT: Final = UNCAPPED_PAYMENT * CEILING / ABOVE_THE_CEILING  # 160.00
DISTRIBUTION_TAX_RATE: Final = 0.09 + 0.05


def _fixture(what: str) -> Provenance:
    return prov.of(
        [
            SourceRef(
                id=f"fixture:peg:{what}",
                citation=f"SYNTHETIC FIXTURE — invented {what}. Not observed from any fund.",
                retrieved_on=date(2026, 8, 23),
                verified_on=None,
            )
        ]
    )


def _tax_pack() -> dict[str, TaxClass]:
    return {
        DISTRIBUTION_CLASS: TaxClass(
            id=DISTRIBUTION_CLASS,
            applies_to=frozenset({TaxableEventKind.DISTRIBUTION}),
            rates=(
                RateEntry(
                    effective_from=synthetic.SCHEDULE_START,
                    pit_rate=0.09,
                    levy_rate=0.05,
                    provenance=_fixture("distribution rate entry"),
                ),
            ),
        ),
        DISPOSAL_CLASS: TaxClass(
            id=DISPOSAL_CLASS,
            applies_to=frozenset({TaxableEventKind.DISPOSAL_GAIN}),
            rates=(
                RateEntry(
                    effective_from=synthetic.SCHEDULE_START,
                    pit_rate=0.18,
                    levy_rate=0.05,
                    provenance=_fixture("disposal rate entry"),
                ),
            ),
        ),
    }


def _declaration() -> FundDeclaration:
    return FundDeclaration(
        id=FUND_ID,
        name="Synthetic pegged fund — TEST FIXTURE, terms invented",
        unit_currency=UAH,
        is_assumption_driven=True,
        nav_per_unit=Money(NAV, UAH, _fixture("NAV per unit")),
        day_count="30/360",
        declared_yield=DeclaredYield(
            low=YIELD,
            high=YIELD,
            basis="usd_equivalent_annual",
            provenance=_fixture("declared yield"),
        ),
        distribution=DistributionTerms(
            frequency="monthly",
            basis_note="FIXTURE — an invented monthly payout sized against the dollar.",
            record_day="last_day_of_month",
            payment_day=5,
            paid_in=UAH,
            peg=Peg(
                sized_in=USD,
                cap=(
                    CapEntry(
                        effective_from=CEILING_FROM,
                        uah_per_unit=CEILING,
                        provenance=_fixture("ceiling"),
                    ),
                ),
            ),
            payout_share=1.0,
            provenance=_fixture("distribution terms"),
        ),
        spread=SpreadTerms(
            entry_markup_max=0.0,
            exit_discount_max=0.0,
            live_entry_markup=0.0,
            live_exit_discount=0.0,
            provenance=_fixture("spread terms"),
        ),
        liquidity=LiquidityTerms(
            legal=LegalTerms(
                buyback_before_termination="discretionary",
                settlement_business_days=0,
                note="FIXTURE — an invented legal floor.",
                provenance=_fixture("legal terms"),
            ),
            practice=ObservedPractice(
                settlement_business_days=0,
                is_revocable=True,
                note="FIXTURE — an invented same-day practice.",
                provenance=_fixture("observed practice"),
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
        verification_tasks=(
            VerificationTask(
                question=(
                    "FIXTURE — what «граничний курс» applied before the declared ladder begins?"
                ),
                searched="nothing; this fund does not exist",
                searched_on=date(2026, 8, 23),
            ),
        ),
    )


def _assumption(rate: float) -> ExchangeRateAssumption:
    return ExchangeRateAssumption(
        uah_per_unit=rate,
        is_assumption=True,
        rationale="FIXTURE — the owner's stated rate for this run, and nothing more.",
    )


def _assumptions(rate: float | None) -> FundAssumptions:
    return FundAssumptions(
        liquidity_mode="practice",
        buyback="available",
        exit_on=EXIT_ON,
        yield_point=None,
        exchange_rate=None if rate is None else _assumption(rate),
        consumption_method="fifo",
    )


def _run(
    rate: float | None,
    *,
    purchased_on: date = PURCHASED_ON,
) -> fund_results.FundOutcome:
    return fund_results.project_fund(
        _declaration(),
        Holding(
            owner_id="owner-1",
            instrument_id=FUND_ID,
            quantity=UNITS,
            purchased_on=purchased_on,
            cost=Money(NAV * UNITS, UAH, prov.EMPTY),
        ),
        DateRange(start=purchased_on, end=HORIZON_END),
        _assumptions(rate),
        tax_classes=_tax_pack(),
    )


def _projected(rate: float) -> FundProjection:
    outcome = _run(rate)
    assert isinstance(outcome, FundProjection), f"expected a projection, got {outcome!r}"
    return outcome


class TestSizedBelowTheCeiling:
    """The rate cancels, and the payment is the plain hryvnia figure."""

    def test_three_payments_on_the_declared_dates(self) -> None:
        assert (
            tuple(line.paid_on for line in _projected(BELOW_THE_CEILING).distributions)
            == PAYMENT_DATES
        )

    def test_each_payment_is_the_hand_computed_two_hundred(self) -> None:
        # 1 000.00 / 38.00 x 20 x 0.01 = 5.263157... USD, x 38.00 = 200.00 UAH
        for line in _projected(BELOW_THE_CEILING).distributions:
            assert is_close(line.gross.amount, UNCAPPED_PAYMENT)
            assert line.gross.currency is UAH

    def test_the_pegged_term_is_recorded_in_the_pegs_own_currency(self) -> None:
        # 5.263157... USD, and it is a *term*, not an amount anybody holds.
        for line in _projected(BELOW_THE_CEILING).distributions:
            assert line.pegged is not None
            assert line.pegged.sized_in is USD
            assert is_close(line.pegged.amount, NAV / BELOW_THE_CEILING * UNITS * MONTHLY)

    def test_the_ceiling_did_not_bind(self) -> None:
        projection = _projected(BELOW_THE_CEILING)
        assert not any(line.cap_bound for line in projection.distributions)
        assert projection.peg_statement is not None
        assert "bound 0 of 3" in projection.peg_statement

    def test_the_tax_is_the_distribution_class_on_the_hryvnia_actually_paid(self) -> None:
        # 200.00 x 0.14 = 28.00 each, 84.00 over three payments.
        projection = _projected(BELOW_THE_CEILING)
        (subtotal,) = [
            item for item in projection.tax_by_class if item.tax_class_id == DISTRIBUTION_CLASS
        ]
        assert is_close(
            subtotal.total_charged.amount,
            UNCAPPED_PAYMENT * DISTRIBUTION_TAX_RATE * len(PAYMENT_DATES),
        )


class TestTheCeilingBinds:
    """SC-011: sized **at** the cap, and the output says the cap bound."""

    def test_each_payment_is_the_hand_computed_one_hundred_and_sixty(self) -> None:
        # 1 000.00 / 50.00 x 20 x 0.01 = 4.00 USD, x 40.00 (not 50.00) = 160.00 UAH
        for line in _projected(ABOVE_THE_CEILING).distributions:
            assert is_close(line.gross.amount, CAPPED_PAYMENT)

    def test_the_shortfall_is_exactly_the_ratio_of_the_ceiling_to_the_assumed_rate(
        self,
    ) -> None:
        """160.00 / 200.00 = 40.00 / 50.00. The peg breaks by exactly the gap, no more."""
        below = _projected(BELOW_THE_CEILING).distributions[0].gross.amount
        above = _projected(ABOVE_THE_CEILING).distributions[0].gross.amount
        assert is_close(above / below, CEILING / ABOVE_THE_CEILING)

    def test_every_line_says_the_ceiling_bound_it(self) -> None:
        projection = _projected(ABOVE_THE_CEILING)
        assert all(line.cap_bound for line in projection.distributions)

    def test_the_output_states_the_peg_the_ceiling_and_how_often_it_bound(self) -> None:
        """FR-020: the currency exposure stays visible instead of being lost in a total.

        A run where the ceiling bound every month is a run in which the holder's dollar
        income stopped arriving in full, and a hryvnia total alone would not say so.
        """
        statement = _projected(ABOVE_THE_CEILING).peg_statement
        assert statement is not None
        assert "USD" in statement
        assert "40.0" in statement
        assert "50.0" in statement
        assert "bound 3 of 3" in statement
        assert "partially broken" in statement


class TestWithoutAStatedRateThereIsNoFigure:
    """FR-021: never an invented rate, and never an implicit one."""

    def test_the_outcome_is_a_typed_degraded_result(self) -> None:
        outcome = _run(None)
        assert isinstance(outcome, PegUnsizable), outcome

    def test_it_names_exactly_which_input_is_missing(self) -> None:
        """A remedy of one line of scenario input, not a search through the codebase."""
        outcome = _run(None)
        assert isinstance(outcome, PegUnsizable)
        assert outcome.missing_input == "FundAssumptions.exchange_rate"
        assert outcome.peg_currency is USD
        assert "no market rate source" in outcome.reason.casefold()

    def test_no_figure_is_produced_at_all(self) -> None:
        outcome = _run(None)
        assert not isinstance(outcome, FundProjection)
        assert not hasattr(outcome, "distributions")


class TestAPaymentBeforeTheDeclaredCeiling:
    """research.md D8: the question is named, and no favourable reading is chosen."""

    def test_it_is_refused_rather_than_sized_at_the_full_assumed_rate(self) -> None:
        # Bought 2026-10-10, so the first payment falls 2026-12-05 -- before the ladder
        # starts on 2027-01-01. Sizing it at 38.00 would be the favourable answer, chosen
        # in silence.
        outcome = _run(BELOW_THE_CEILING, purchased_on=date(2026, 10, 10))
        assert isinstance(outcome, AwaitingVerification), outcome

    def test_the_refusal_carries_the_recorded_open_question(self) -> None:
        outcome = _run(BELOW_THE_CEILING, purchased_on=date(2026, 10, 10))
        assert isinstance(outcome, AwaitingVerification)
        assert "граничний курс" in outcome.question
        assert outcome.searched_on == date(2026, 8, 23)
        assert "2026-12-05" in outcome.reason

    def test_the_refusal_carries_no_value_because_the_task_does_not(self) -> None:
        outcome = _run(BELOW_THE_CEILING, purchased_on=date(2026, 10, 10))
        assert isinstance(outcome, AwaitingVerification)
        assert not hasattr(outcome, "value")
        assert not hasattr(outcome, "assumed")


class TestAPeggedAmountIsNotMoney:
    """FR-022: the peg is a declared term, not a conversion licence.

    Asserted on the types rather than on a convention, because a convention is a thing to
    remember and a type is a thing the checker enforces.
    """

    def test_a_pegged_amount_cannot_be_added_to_money(self) -> None:
        line = _projected(BELOW_THE_CEILING).distributions[0]
        assert line.pegged is not None
        # mypy proves the two types are disjoint -- it rejects even the comparison -- and
        # that is the real assertion. This is the runtime half: a pegged amount has no
        # currency tag, because it is a term rather than an amount of anything.
        assert not hasattr(line.pegged, "currency")
        assert hasattr(line.pegged, "sized_in")
        with pytest.raises(AttributeError):
            money.add(line.gross, line.pegged)  # type: ignore[arg-type]

    def test_hryvnia_and_dollars_still_cannot_be_combined(self) -> None:
        """001's prohibition, unchanged: the peg did not create an exception to it."""
        line = _projected(BELOW_THE_CEILING).distributions[0]
        dollars = Money(1.0, USD, prov.EMPTY)
        with pytest.raises(CurrencyMismatchError):
            money.add(line.gross, dollars)

    def test_sizing_a_term_into_its_own_currency_is_refused(self) -> None:
        """Not a conversion, and accepting it would let a lost currency pass through."""
        with pytest.raises(ValueError, match="not pegged to anything"):
            money.from_pegged_term(1.0, sized_in=UAH, paid_in=UAH, rate=1.0, sources=prov.EMPTY)

    def test_a_rate_of_zero_is_refused_rather_than_producing_a_zero_payment(self) -> None:
        with pytest.raises(ValueError, match="is not a rate"):
            money.from_pegged_term(1.0, sized_in=USD, paid_in=UAH, rate=0.0, sources=prov.EMPTY)

    def test_the_sized_payment_carries_the_ceilings_citation_as_well_as_the_terms(
        self,
    ) -> None:
        """The ceiling is an input to the figure, so its mark has to reach the figure."""
        line = _projected(ABOVE_THE_CEILING).distributions[0]
        ids = {ref.id for ref in line.gross.provenance.sources}
        assert "fixture:peg:ceiling" in ids
        assert "fixture:peg:NAV per unit" in ids
        assert "fixture:peg:declared yield" in ids


class TestTheCeilingLookupItself:
    """``cap_on`` at the boundary, because the ladder's edges are where a payment is lost."""

    def test_a_date_on_the_ceilings_own_effective_day_is_covered(self) -> None:
        peg = _declaration().distribution
        assert peg is not None
        assert peg.peg is not None
        found = fund.cap_on(peg.peg, CEILING_FROM)
        assert found is not None
        assert found.uah_per_unit == CEILING

    def test_the_day_before_is_not(self) -> None:
        peg = _declaration().distribution
        assert peg is not None
        assert peg.peg is not None
        assert fund.cap_on(peg.peg, date(2026, 12, 31)) is None

    def test_a_ceiling_stays_in_force_until_a_later_one_supersedes_it(self) -> None:
        """The same rule a rate schedule follows, so a reader learns it once."""
        peg = _declaration().distribution
        assert peg is not None
        assert peg.peg is not None
        later = replace(
            peg.peg,
            cap=(
                *peg.peg.cap,
                CapEntry(
                    effective_from=date(2028, 1, 1),
                    uah_per_unit=44.0,
                    provenance=_fixture("later ceiling"),
                ),
            ),
        )
        first = fund.cap_on(later, date(2027, 12, 31))
        second = fund.cap_on(later, date(2028, 1, 1))
        assert first is not None
        assert second is not None
        assert first.uah_per_unit == CEILING
        assert second.uah_per_unit == 44.0

    def test_an_empty_ladder_declares_no_ceiling_rather_than_a_ceiling_of_zero(self) -> None:
        """The two are different claims, and only one of them sizes a payment at nothing."""
        assert fund.cap_on(Peg(sized_in=USD, cap=()), date(2027, 6, 1)) is None
