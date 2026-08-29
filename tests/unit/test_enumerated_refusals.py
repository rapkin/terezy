"""What a schedule of declared payments refuses, and how (SC-008, SC-009, SC-024).

Every one of these is a **typed value carrying its reason** rather than an exception or a
number computed around the gap (FR-019). A figure silently computed on a missing fact is
the defect this whole form exists to prevent, and a refusal that is not typed is a refusal
caught in review rather than by a test.

The refusals are all members of the **existing** instrument failure union. Nothing is
widened, and that is load-bearing rather than pedantic: *different failures* is one of the
three mismatches recorded at `core.instruments.registry` that kept a fund out of that
registry, so a widened union would be the sentence putting a constitution amendment back on
the table (FR-013).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest

from terezy.core.errors import InconsistentTerms, InfeasiblePurchase
from terezy.core.instruments import registry
from terezy.core.instruments.interface import Assumptions, DateRange, Holding
from terezy.core.primitives.money import Money
from terezy.core.results import project
from terezy.core.results.project import Projection
from tests.worked_examples.test_enumerated_schedule import (
    COST,
    COVERS_FROM,
    DECLARATION,
    EXEMPT_CLASS,
    HOLDING,
    HORIZON,
    QUANTITY,
    TERMS,
)

HOLD_CASH = Assumptions(consumption_method="fifo", coupon_policy="hold_cash")
REINVEST = Assumptions(consumption_method="fifo", coupon_policy="reinvest")
TAX_CLASSES = {EXEMPT_CLASS.id: EXEMPT_CLASS}


def _events(
    *,
    holding: Holding = HOLDING,
    horizon: DateRange = HORIZON,
    assumptions: Assumptions = HOLD_CASH,
) -> object:
    ops = registry.ops_for(DECLARATION.instrument_class)
    return ops.events(DECLARATION, holding, horizon, assumptions)


class TestAPurchaseBeforeTheCoverageStart:
    """FR-014. The declaration claims completeness from a date and says nothing before it."""

    def test_one_day_early_refuses(self) -> None:
        early = replace(HOLDING, purchased_on=COVERS_FROM - timedelta(days=1))
        outcome = _events(holding=early, horizon=replace(HORIZON, start=early.purchased_on))
        assert isinstance(outcome, InconsistentTerms), outcome
        assert outcome.second_term == "instrument.schedule.covers_from"

    def test_the_refusal_names_both_dates(self) -> None:
        early = replace(HOLDING, purchased_on=COVERS_FROM - timedelta(days=1))
        outcome = _events(holding=early, horizon=replace(HORIZON, start=early.purchased_on))
        assert isinstance(outcome, InconsistentTerms), outcome
        assert early.purchased_on.isoformat() in outcome.reason
        assert COVERS_FROM.isoformat() in outcome.reason

    def test_the_purchase_is_not_re_dated_to_the_coverage_start(self) -> None:
        """Moving it would answer a different question and report the answer as this one."""
        early = replace(HOLDING, purchased_on=COVERS_FROM - timedelta(days=1))
        outcome = _events(holding=early, horizon=replace(HORIZON, start=early.purchased_on))
        assert isinstance(outcome, InconsistentTerms), outcome
        assert "not re-dated" in outcome.reason

    def test_the_same_purchase_on_the_coverage_start_succeeds(self) -> None:
        assert isinstance(_events(), tuple)


class TestAReinvestingCouponPolicy:
    """FR-015. Reinvestment needs a price at which a coupon buys a unit, and there is none."""

    def test_it_refuses(self) -> None:
        outcome = _events(assumptions=REINVEST)
        assert isinstance(outcome, InconsistentTerms), outcome
        assert outcome.first_term == "assumptions.coupon_policy"

    def test_the_refusal_names_the_missing_price_and_refuses_to_use_face(self) -> None:
        outcome = _events(assumptions=REINVEST)
        assert isinstance(outcome, InconsistentTerms), outcome
        assert "price" in outcome.reason
        assert "face value is not substituted" in outcome.reason

    def test_holding_as_cash_is_unaffected(self) -> None:
        """SC-009's second half: the refusal is scoped to the policy that needs a price."""
        outcome = project.project(DECLARATION, HOLDING, HORIZON, HOLD_CASH, tax_classes=TAX_CLASSES)
        assert isinstance(outcome, Projection), outcome

    def test_an_unrecognised_policy_still_raises_naming_the_known_ones(self) -> None:
        """There is no default policy, and this form does not acquire one by refusing the
        policy it cannot carry out."""
        with pytest.raises(KeyError, match="hold_cash"):
            _events(assumptions=replace(HOLD_CASH, coupon_policy="sweep_monthly"))


class TestAHorizonThatDoesNotReachTheLastPayment:
    def test_it_refuses_rather_than_truncating(self) -> None:
        last = max(payment.on for payment in TERMS.payments)
        outcome = _events(horizon=replace(HORIZON, end=last - timedelta(days=1)))
        assert isinstance(outcome, InconsistentTerms), outcome
        assert last.isoformat() in outcome.reason

    def test_no_implicit_liquidation_is_offered(self) -> None:
        last = max(payment.on for payment in TERMS.payments)
        outcome = _events(horizon=replace(HORIZON, end=last - timedelta(days=1)))
        assert isinstance(outcome, InconsistentTerms), outcome
        assert "nobody declared" in outcome.reason


class TestAPurchaseThatIsNotAPurchase:
    def test_no_units_refuses(self) -> None:
        outcome = _events(holding=replace(HOLDING, quantity=0.0))
        assert isinstance(outcome, InconsistentTerms), outcome

    def test_no_money_refuses(self) -> None:
        outcome = _events(holding=replace(HOLDING, cost=Money(0.0, COST.currency, COST.provenance)))
        assert isinstance(outcome, InconsistentTerms), outcome

    def test_below_the_minimum_ticket_reports_the_shortfall(self) -> None:
        outcome = _events(
            holding=replace(
                HOLDING, quantity=0.5, cost=Money(500.0, COST.currency, COST.provenance)
            )
        )
        assert isinstance(outcome, InfeasiblePurchase), outcome
        assert outcome.shortfall.amount == 500.0


class TestPrincipalRepaymentsThatWouldRetireMoreThanIsHeld:
    def test_an_over_amortising_schedule_refuses(self) -> None:
        """Two declared facts that cannot both hold: what the repayments return per unit,
        and the face value they are a fraction of. Reported rather than left to the ledger,
        which raises on an over-disposal."""
        doubled = replace(
            TERMS,
            payments=tuple(
                replace(payment, amount=Money(2000.0, COST.currency, COST.provenance))
                if payment.pays.value == "principal_repayment"
                else payment
                for payment in TERMS.payments
            ),
        )
        ops = registry.ops_for(DECLARATION.instrument_class)
        outcome = ops.events(replace(DECLARATION, terms=doubled), HOLDING, HORIZON, HOLD_CASH)
        assert isinstance(outcome, InconsistentTerms), outcome
        assert outcome.second_term == "instrument.schedule.face_value"
        assert f"{QUANTITY!r} units held" in outcome.reason


class TestEveryReasonSurvivesIntoTheOutput:
    """SC-024. A refusal whose reason is dropped between the core and the result is a
    refusal a reader is never told about."""

    def test_the_projection_returns_the_instrument_s_own_refusal_unchanged(self) -> None:
        early = replace(HOLDING, purchased_on=COVERS_FROM - timedelta(days=1))
        outcome = project.project(
            DECLARATION,
            early,
            replace(HORIZON, start=early.purchased_on),
            HOLD_CASH,
            tax_classes=TAX_CLASSES,
        )
        assert isinstance(outcome, InconsistentTerms), outcome
        assert outcome.reason
        assert outcome == _events(holding=early, horizon=replace(HORIZON, start=early.purchased_on))

    def test_every_refusal_this_form_adds_carries_a_non_empty_reason(self) -> None:
        early = replace(HOLDING, purchased_on=date(2026, 1, 1))
        for outcome in (
            _events(holding=early, horizon=replace(HORIZON, start=early.purchased_on)),
            _events(assumptions=REINVEST),
        ):
            assert isinstance(outcome, InconsistentTerms), outcome
            assert len(outcome.reason) > 80, "a reason a reader cannot act on is not a reason"
