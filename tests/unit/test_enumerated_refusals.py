"""What a schedule of declared payments refuses, and how (SC-008, SC-009, SC-024).

Every one of these is a **typed value carrying its reason** rather than an exception or a
number computed around the gap (FR-019). A figure silently computed on a missing fact is
the defect this whole form exists to prevent, and a refusal that is not typed is a refusal
caught in review rather than by a test.

The refusals are all members of the **existing** instrument failure union, which is
load-bearing rather than pedantic: *different failures* is one of the three mismatches that
kept a fund out of the instrument registry, so widening the union would be the sentence
putting a constitution amendment back on the table (FR-013). That claim is asserted at the
foot of this file rather than left as a sentence.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Final, get_args

import pytest

from terezy.core.errors import InconsistentTerms, InfeasiblePurchase, InstrumentFailure
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
    TERMS,
)

HOLD_CASH = Assumptions(consumption_method="fifo", coupon_policy="hold_cash")
DAY = timedelta(days=1)
LAST_PAYMENT = max(payment.on for payment in TERMS.payments)
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


class TestAHorizonThatCannotContainThePurchase:
    """The two guards that are about the *window* rather than about the declaration."""

    def test_a_horizon_running_backwards_refuses(self) -> None:
        outcome = _events(horizon=DateRange(start=HORIZON.end, end=HORIZON.start))
        assert isinstance(outcome, InconsistentTerms), outcome
        assert outcome.first_term == "horizon.start"
        assert "runs backwards" in outcome.reason

    def test_a_horizon_opening_after_the_purchase_refuses(self) -> None:
        """The purchase is the origin of every time measurement in the result, so a window
        that excludes it would measure returns from a date on which nothing was bought."""
        outcome = _events(horizon=replace(HORIZON, start=COVERS_FROM + timedelta(days=1)))
        assert isinstance(outcome, InconsistentTerms), outcome
        assert outcome.second_term == "holding.purchased_on"


class TestAPaymentDatedOnOrBeforeThePurchase:
    """It went to whoever held the paper then, exactly as a coupon does for a bond declared
    by its terms.

    There is no accrued-interest apportionment of the payment straddling the purchase, and
    there could not be: the two facts it would need are not declared and may not be inferred
    (FR-017).
    """

    def test_it_is_not_this_holding_s_income(self) -> None:
        first = min(payment.on for payment in TERMS.payments)
        bought_on_the_first_payment = replace(HOLDING, purchased_on=first)
        produced = _events(
            holding=bought_on_the_first_payment,
            horizon=replace(HORIZON, start=first),
        )
        assert isinstance(produced, tuple), produced
        assert first not in [event.occurred_on for event in produced[1:]]

    def test_every_later_payment_still_arrives(self) -> None:
        first = min(payment.on for payment in TERMS.payments)
        produced = _events(
            holding=replace(HOLDING, purchased_on=first),
            horizon=replace(HORIZON, start=first),
        )
        assert isinstance(produced, tuple), produced
        assert len(produced) == 1 + len([p for p in TERMS.payments if p.on > first])

    def test_nothing_is_apportioned_to_make_up_for_it(self) -> None:
        """The whole payment goes to the earlier holder; this one is not paid a fraction of
        it. A schedule that apportioned would need an accrual period nobody declared."""
        first = min(payment.on for payment in TERMS.payments)
        produced = _events(
            holding=replace(HOLDING, purchased_on=first), horizon=replace(HORIZON, start=first)
        )
        assert isinstance(produced, tuple), produced
        declared = {payment.amount.amount * HOLDING.quantity for payment in TERMS.payments}
        assert all(event.amount.amount in declared for event in produced[1:])


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


class TestEveryReasonSurvivesIntoTheOutput:
    """SC-024. A refusal whose reason is dropped between the core and the result is a
    refusal a reader is never told about.

    ⚙ **A battery over every refusal this form adds**, because that is what SC-024 asks for
    and one round-tripped case is not it: the requirement is that *no* refusal loses its
    reason at the seam, and a seam only leaks for some of what crosses it.
    """

    REFUSALS: Final[tuple[tuple[str, Holding], ...]] = (
        ("purchased before the coverage start", replace(HOLDING, purchased_on=COVERS_FROM - DAY)),
        ("purchased after every payment", replace(HOLDING, purchased_on=LAST_PAYMENT)),
        ("no units acquired", replace(HOLDING, quantity=0.0)),
        ("nothing paid", replace(HOLDING, cost=Money(0.0, COST.currency, COST.provenance))),
        (
            "below the minimum ticket",
            replace(HOLDING, quantity=0.5, cost=Money(500.0, COST.currency, COST.provenance)),
        ),
    )
    """Every refusal reachable by varying the **holding**. The two reachable by varying the
    assumptions and the horizon are separate parameters below, because they are not holdings.
    """

    @staticmethod
    def _projected(
        *, holding: Holding = HOLDING, horizon: DateRange = HORIZON, policy: Assumptions = HOLD_CASH
    ) -> object:
        return project.project(DECLARATION, holding, horizon, policy, tax_classes=TAX_CLASSES)

    @pytest.mark.parametrize(("what", "holding"), REFUSALS, ids=[case[0] for case in REFUSALS])
    def test_a_refused_holding_reaches_the_result_unchanged(
        self, what: str, holding: Holding
    ) -> None:
        horizon = replace(HORIZON, start=min(HORIZON.start, holding.purchased_on))
        from_the_core = _events(holding=holding, horizon=horizon)
        from_the_result = self._projected(holding=holding, horizon=horizon)
        assert isinstance(from_the_core, InconsistentTerms | InfeasiblePurchase), what
        assert from_the_result == from_the_core, what
        assert from_the_core.reason in str(from_the_result), what

    def test_a_refused_policy_reaches_the_result_unchanged(self) -> None:
        assert self._projected(policy=REINVEST) == _events(assumptions=REINVEST)

    def test_a_refused_horizon_reaches_the_result_unchanged(self) -> None:
        short = replace(HORIZON, end=LAST_PAYMENT - DAY)
        assert self._projected(horizon=short) == _events(horizon=short)

    def test_every_one_of_them_carries_a_reason_a_reader_can_act_on(self) -> None:
        short = replace(HORIZON, end=LAST_PAYMENT - DAY)
        crossed = [
            self._projected(
                holding=holding,
                horizon=replace(HORIZON, start=min(HORIZON.start, holding.purchased_on)),
            )
            for _, holding in self.REFUSALS
        ] + [self._projected(policy=REINVEST), self._projected(horizon=short)]
        assert len(crossed) == len(self.REFUSALS) + 2
        for outcome in crossed:
            assert isinstance(outcome, InconsistentTerms | InfeasiblePurchase), outcome
            assert len(outcome.reason) > 80, "a reason a reader cannot act on is not a reason"


def test_the_instrument_failure_union_is_unchanged() -> None:
    """FR-013. The claim the module docstring makes, checked rather than stated.

    A test over the union's *membership* rather than over this form's behaviour, because
    that is what the requirement is about: a member added for the enumerated form would be a
    member every existing caller has to learn, and the callers are the reason the union is
    narrow. Written as an exact set so a widening is a decision somebody has to take here.
    """
    assert set(get_args(InstrumentFailure)) == {InfeasiblePurchase, InconsistentTerms}


def test_every_refusal_this_form_produces_is_a_member_of_it() -> None:
    """And the other direction: the form uses the union rather than merely not widening it."""
    early = replace(HOLDING, purchased_on=COVERS_FROM - timedelta(days=1))
    produced = (
        _events(holding=early, horizon=replace(HORIZON, start=early.purchased_on)),
        _events(assumptions=REINVEST),
        _events(holding=replace(HOLDING, quantity=0.0)),
        _events(
            holding=replace(
                HOLDING, quantity=0.5, cost=Money(500.0, COST.currency, COST.provenance)
            )
        ),
    )
    assert all(isinstance(outcome, InfeasiblePurchase | InconsistentTerms) for outcome in produced)
