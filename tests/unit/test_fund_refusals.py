"""Every guard on the fund path, and the claim each refusal message actually makes.

The worked examples check the arithmetic of runs that succeed. This module checks the runs
that must not: a purchase below the minimum, a fund that ends before it is bought, an exit
before the units are held, a class the declaration never names, a class the tax pack does
not contain, an event the schedule does not reach, and an annualisation with no period to
annualise over.

**A guard is only worth its message.** Each test asserts the message names the thing a
reader has to change, not merely that something was refused — a refusal nobody can act on
is one they will route around.

Every fixture here is invented and labelled so.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Final

import pytest

from terezy.core.errors import InconsistentTerms, InfeasiblePurchase, UnresolvedTaxClass
from terezy.core.instruments import fund
from terezy.core.instruments.fund import (
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
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.rates import NominalRate
from terezy.core.results import fund as fund_results
from terezy.core.results import hurdle
from terezy.core.results.fund import (
    AwaitingVerification,
    BesideTheHurdle,
    FundAssumptions,
    FundProjection,
    RangeProjection,
)
from terezy.core.results.hurdle import HurdleRate
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from terezy.core.tax.schedule import RateEntry, RateUndeclaredBefore
from tests import synthetic

UAH: Final = Currency.UAH
FUND_ID: Final = "synthetic_fund_guards"
PAYOUT_CLASS: Final = "fixture_payout"
DISPOSAL_CLASS: Final = "fixture_disposal"

NAV: Final = 100.0
UNITS: Final = 10.0
MINIMUM_UNITS: Final = 4.0
PURCHASED_ON: Final = date(2027, 1, 10)
EXIT_ON: Final = date(2027, 7, 10)
TERMINATES_ON: Final = date(2030, 1, 10)
HORIZON_END: Final = date(2030, 12, 31)
SCHEDULE_FROM: Final = synthetic.SCHEDULE_START


def _fixture(what: str) -> Provenance:
    return prov.of(
        [
            SourceRef(
                id=f"fixture:guards:{what}",
                citation=f"SYNTHETIC FIXTURE — invented {what}.",
                retrieved_on=date(2026, 8, 23),
                verified_on=None,
            )
        ]
    )


def _class(class_id: str, kind: TaxableEventKind, *, since: date = SCHEDULE_FROM) -> TaxClass:
    return TaxClass(
        id=class_id,
        applies_to=frozenset({kind}),
        rates=(
            RateEntry(
                effective_from=since,
                pit_rate=0.1,
                levy_rate=0.05,
                provenance=_fixture(f"{class_id} rate entry"),
            ),
        ),
    )


def _pack(**overrides: TaxClass) -> dict[str, TaxClass]:
    base = {
        PAYOUT_CLASS: _class(PAYOUT_CLASS, TaxableEventKind.DISTRIBUTION),
        DISPOSAL_CLASS: _class(DISPOSAL_CLASS, TaxableEventKind.DISPOSAL_GAIN),
    }
    base.update(overrides)
    return base


def _declaration(**overrides: object) -> FundDeclaration:
    base = FundDeclaration(
        id=FUND_ID,
        name="Synthetic fund for the guards — TEST FIXTURE, terms invented",
        unit_currency=UAH,
        is_assumption_driven=True,
        nav_per_unit=Money(NAV, UAH, _fixture("NAV per unit")),
        day_count="30/360",
        declared_yield=DeclaredYield(
            low=0.1, high=0.1, basis="simple_annual", provenance=_fixture("declared yield")
        ),
        distribution=DistributionTerms(
            frequency="monthly",
            basis_note="FIXTURE — an invented monthly payout.",
            record_day="last_day_of_month",
            payment_day=10,
            paid_in=UAH,
            peg=None,
            payout_share=0.5,
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
                note="FIXTURE — an invented practice.",
                provenance=_fixture("observed practice"),
            ),
        ),
        minimum_units=MINIMUM_UNITS,
        subscription_cutoff=None,
        terminates_on=TERMINATES_ON,
        tax_classes={
            TaxableEventKind.DISTRIBUTION: PAYOUT_CLASS,
            TaxableEventKind.DISPOSAL_GAIN: DISPOSAL_CLASS,
        },
        fee_context=(),
        verification_tasks=(),
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def _holding(**overrides: object) -> Holding:
    base = Holding(
        owner_id="owner-1",
        instrument_id=FUND_ID,
        quantity=UNITS,
        purchased_on=PURCHASED_ON,
        cost=Money(NAV * UNITS, UAH, prov.EMPTY),
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def _assumptions(**overrides: object) -> FundAssumptions:
    base = FundAssumptions(
        liquidity_mode="practice",
        buyback="available",
        exit_on=EXIT_ON,
        yield_point=None,
        exchange_rate=None,
        consumption_method="fifo",
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def _run(
    declaration: FundDeclaration | None = None,
    holding: Holding | None = None,
    assumptions: FundAssumptions | None = None,
    tax_classes: dict[str, TaxClass] | None = None,
) -> fund_results.FundOutcome:
    return fund_results.project_fund(
        declaration or _declaration(),
        holding or _holding(),
        DateRange(start=(holding or _holding()).purchased_on, end=HORIZON_END),
        assumptions or _assumptions(),
        tax_classes=tax_classes or _pack(),
    )


class TestThePurchaseGuards:
    """A holding the fund would not have accepted is not projected."""

    def test_below_the_minimum_is_infeasible_and_names_the_shortfall(self) -> None:
        # Four units at 100.00 is 400.00 required; two units is 200.00 offered.
        outcome = _run(holding=_holding(quantity=2.0))
        assert isinstance(outcome, InfeasiblePurchase), outcome
        assert outcome.constraint == "minimum_units"
        assert outcome.required.amount == MINIMUM_UNITS * NAV
        assert outcome.actual.amount == 2.0 * NAV
        assert outcome.shortfall.amount == (MINIMUM_UNITS - 2.0) * NAV
        assert "rounded up to fit" in outcome.reason

    def test_the_minimum_itself_is_accepted(self) -> None:
        """The boundary is inclusive, and it is tested at the boundary."""
        assert isinstance(_run(holding=_holding(quantity=MINIMUM_UNITS)), FundProjection)

    def test_a_fund_that_ends_before_it_is_bought_is_inconsistent(self) -> None:
        outcome = _run(declaration=_declaration(terminates_on=date(2026, 1, 1)))
        assert isinstance(outcome, InconsistentTerms), outcome
        assert outcome.first_term == "fund.terminates_on"
        assert outcome.second_term == "holding.purchased_on"
        assert "no holding period" in outcome.reason


class TestTheExitGuards:
    """An exit that cannot have happened is refused before anything is priced."""

    def test_an_exit_before_the_purchase_is_inconsistent(self) -> None:
        outcome = _run(assumptions=_assumptions(exit_on=date(2026, 12, 1)))
        assert isinstance(outcome, InconsistentTerms), outcome
        assert outcome.first_term == "assumptions.exit_on"
        assert "before they are held" in outcome.reason


class TestTheTaxClassGuards:
    """A missing rule is never read as an exemption."""

    def test_an_income_kind_the_declaration_maps_to_nothing_is_reported(self) -> None:
        outcome = _run(
            declaration=_declaration(tax_classes={TaxableEventKind.DISPOSAL_GAIN: DISPOSAL_CLASS})
        )
        assert isinstance(outcome, UnresolvedTaxClass), outcome
        assert outcome.tax_class_id == "<none declared for distribution>"
        assert outcome.instrument_id == FUND_ID
        assert "taxed differently on a payout and on an exit" in outcome.reason

    def test_a_class_the_pack_does_not_contain_is_reported(self) -> None:
        outcome = _run(tax_classes={DISPOSAL_CLASS: _pack()[DISPOSAL_CLASS]})
        assert isinstance(outcome, UnresolvedTaxClass), outcome
        assert outcome.tax_class_id == PAYOUT_CLASS
        assert "not projected rather than projected untaxed" in outcome.reason

    def test_a_class_that_does_not_cover_the_kind_it_was_named_for_refuses(self) -> None:
        """The rule's own refusal, reached through the fund path rather than the bond one."""
        crossed = _pack(**{PAYOUT_CLASS: _class(PAYOUT_CLASS, TaxableEventKind.DISPOSAL_GAIN)})
        outcome = _run(tax_classes=crossed)
        assert isinstance(outcome, UnresolvedTaxClass), outcome
        assert "does not cover" in outcome.reason

    def test_a_payout_before_the_schedules_earliest_entry_stops_the_run(self) -> None:
        """FR-012 through a fund: the first payout falls 2027-03-10, the schedule starts later."""
        late = _pack(
            **{
                PAYOUT_CLASS: _class(
                    PAYOUT_CLASS, TaxableEventKind.DISTRIBUTION, since=date(2027, 4, 1)
                )
            }
        )
        outcome = _run(tax_classes=late)
        assert isinstance(outcome, RateUndeclaredBefore), outcome
        assert outcome.tax_class_id == PAYOUT_CLASS
        assert outcome.event_date == date(2027, 3, 10)
        assert outcome.earliest_declared == date(2027, 4, 1)


class TestARefusalPropagatesOutOfARangeRun:
    """A range projects twice, so a refusal at either end has to reach the caller.

    Returning a ``RangeProjection`` with one usable end and one silently dropped would be
    the worst available outcome: a reader would see a range narrower than the fund's own.
    """

    def test_the_low_end_refusing_refuses_the_whole_run(self) -> None:
        ranged = _declaration(
            declared_yield=DeclaredYield(
                low=0.1, high=0.2, basis="simple_annual", provenance=_fixture("range")
            )
        )
        outcome = _run(declaration=ranged, tax_classes={DISPOSAL_CLASS: _pack()[DISPOSAL_CLASS]})
        assert isinstance(outcome, UnresolvedTaxClass), outcome

    def test_a_healthy_range_still_produces_both_ends(self) -> None:
        """So the test above is not passing because ranges never work."""
        ranged = _declaration(
            declared_yield=DeclaredYield(
                low=0.1, high=0.2, basis="simple_annual", provenance=_fixture("range")
            )
        )
        outcome = _run(declaration=ranged)
        assert isinstance(outcome, RangeProjection), outcome
        assert outcome.at_low.net_proceeds.amount != outcome.at_high.net_proceeds.amount


class TestTheAnnualisationGuard:
    """A rate over no time is the most confident meaningless figure available."""

    def _hurdle(self) -> HurdleRate:
        return HurdleRate(
            nominal_ytm=NominalRate(0.16),
            nominal_cash_flow_return=NominalRate(0.16),
            # ⚙ A `RealTerms` since 007. Nothing here deflates, so the slot takes the
            # constant that names both absences (no series, no assumption).
            real=hurdle.NOT_DEFLATED,
            total_tax=Money(0.0, UAH, prov.EMPTY),
            accounts_for=frozenset({"FIXTURE"}),
            excludes=frozenset({"FIXTURE"}),
            provenance=prov.EMPTY,
        )

    def test_a_holding_bought_and_sold_on_one_day_has_no_annual_rate(self) -> None:
        outcome = _run(assumptions=_assumptions(exit_on=PURCHASED_ON))
        assert isinstance(outcome, FundProjection), outcome
        compared = fund_results.beside_hurdle(_declaration(), _holding(), outcome, self._hurdle())
        assert isinstance(compared, InconsistentTerms), compared
        assert "no length or no size" in compared.reason

    def test_a_holding_with_length_does_produce_one(self) -> None:
        outcome = _run()
        assert isinstance(outcome, FundProjection), outcome
        compared = fund_results.beside_hurdle(_declaration(), _holding(), outcome, self._hurdle())
        assert isinstance(compared, BesideTheHurdle), compared
        assert compared.years > 0.0
        assert compared.difference == compared.fund_net_simple_annual - 0.16


@pytest.mark.parametrize("mode", ["practice", "legal"])
def test_every_projection_states_the_mode_it_assumed(mode: str) -> None:
    """FR-016, over both modes, so the field cannot be right by accident in one of them."""
    outcome = _run(assumptions=_assumptions(liquidity_mode=mode))
    assert isinstance(outcome, FundProjection), outcome
    assert outcome.liquidity_mode == mode


class TestTheGuardsWhoseMessagesHadNoTestAtAll:
    """Three refusals the coverage report found unexercised. A refusal nobody runs is a
    refusal whose message can be false without anyone noticing — and one of these was.
    """

    def test_a_negative_settlement_delay_is_refused_rather_than_clamped(self) -> None:
        """A programmer-error guard, and it stays a guard: the loader refuses this in data.

        Reached only if a caller builds terms in code, which the fixtures in this suite do.
        Clamping to zero would turn a lost sign into a same-day settlement that reads as a
        declared term.
        """
        with pytest.raises(ValueError, match="is not a delay"):
            fund.settlement_date(date(2028, 1, 10), -1)

    def test_zero_business_days_is_same_day_and_is_a_real_declared_value(self) -> None:
        """So the guard above is about the sign, not about the boundary."""
        assert fund.settlement_date(date(2028, 1, 10), 0) == date(2028, 1, 10)

    def test_a_pegged_fund_with_no_ceiling_and_no_task_says_the_task_is_missing(
        self,
    ) -> None:
        """The fallback wording in ``_awaiting_cap``, which had never been run.

        Running it found a real defect: it used to report the fund's **termination date**
        as ``searched_on``, which would have read as "somebody looked on this day" when
        nobody had. A missing task is a defect in the declaration, and the refusal now says
        so and carries ``None``.
        """
        pegged = _declaration(
            distribution=DistributionTerms(
                frequency="monthly",
                basis_note="FIXTURE — a payout pegged to a currency with no declared ceiling.",
                record_day="last_day_of_month",
                payment_day=10,
                paid_in=UAH,
                peg=Peg(sized_in=Currency.USD, cap=()),
                payout_share=0.5,
                provenance=_fixture("pegged distribution terms"),
            ),
            verification_tasks=(),
        )
        outcome = _run(
            declaration=pegged,
            assumptions=_assumptions(
                exchange_rate=ExchangeRateAssumption(
                    uah_per_unit=42.0,
                    is_assumption=True,
                    rationale="FIXTURE — an owner-stated rate.",
                )
            ),
        )
        assert isinstance(outcome, AwaitingVerification), outcome
        assert outcome.searched_on is None
        assert "no verification task is declared" in outcome.searched
        assert "not even a question to hand back" in outcome.reason

    def test_the_same_fund_with_a_task_declared_hands_the_question_back(self) -> None:
        """The other half, so the fallback is reached for the reason it claims."""
        pegged = _declaration(
            distribution=DistributionTerms(
                frequency="monthly",
                basis_note="FIXTURE — a payout pegged to a currency with no declared ceiling.",
                record_day="last_day_of_month",
                payment_day=10,
                paid_in=UAH,
                peg=Peg(sized_in=Currency.USD, cap=()),
                payout_share=0.5,
                provenance=_fixture("pegged distribution terms"),
            ),
            verification_tasks=(
                VerificationTask(
                    question="FIXTURE — which «граничний курс» applies?",
                    searched="the fixture's imaginary регламент",
                    searched_on=date(2026, 8, 23),
                ),
            ),
        )
        outcome = _run(
            declaration=pegged,
            assumptions=_assumptions(
                exchange_rate=ExchangeRateAssumption(
                    uah_per_unit=42.0,
                    is_assumption=True,
                    rationale="FIXTURE — an owner-stated rate.",
                )
            ),
        )
        assert isinstance(outcome, AwaitingVerification), outcome
        assert outcome.searched_on == date(2026, 8, 23)
        assert "not even a question to hand back" not in outcome.reason
