"""SC-010 -- the two coupon policies produce different terminal amounts, and say so.

*"The reinvesting and cash-holding coupon policies produce different terminal amounts on
the same purchase"*, and FR-019: *"the two MUST produce different, **separately
checkable** results."* The hand-computed arithmetic behind the difference is
``tests/worked_examples/test_coupon_reinvestment.py``; what this module checks is that the
difference is real, that it lands where a reader would look for it, and that neither policy
can be reached by accident.

**Where the terminal amount lives.** In the UAH cash balance of the folded ledger, because
that is the money the owner can actually spend -- Principle VI's *"an asset that cannot be
liquidated into spendable base currency is not worth its NAV"*, seen from the other end. The
position is empty by then: the bond has redeemed, and everything it paid is cash.

**Why "different" needs more than one assertion.** Two policies could differ in the terminal
amount and be wrong in the same way, or agree on the amount and differ in the ledger. So the
checks below take the difference at three levels -- the amount, the units held, and the
determinism digest of the whole result -- and then check the *converse* too: where
reinvestment is impossible the two agree exactly, which is what shows the difference comes
from arithmetic rather than from the label on the run.
"""

from __future__ import annotations

import pytest

from terezy.core.instruments import fixed_income
from terezy.core.ledger.events import EventKind
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results import canonical, project
from terezy.core.results.project import Projection
from terezy.data import manifest
from tests import synthetic

UAH = Currency.UAH

QUANTITY = 100.0
"""A hundred units at par: large enough that a coupon buys whole bonds (see D2)."""

COST = Money(QUANTITY * 1000.0, UAH, prov.of([synthetic.PURCHASE_SOURCE]))

REINVESTED_TERMINAL = 34_497.05479452055
"""The hand-computed terminal cash under ``reinvest`` (D2)."""

HELD_TERMINAL = 31_000.0
"""``15 500 x 730/365`` -- two years of interest on a flat 100 units, exactly."""

DIFFERENCE = 3_497.05479452055
"""What reinvestment is worth on this purchase. The whole of SC-010, in one figure."""


def _projection(policy: str) -> Projection:
    outcome = project.project(
        synthetic.declaration(),
        synthetic.holding(quantity=QUANTITY, cost=COST),
        synthetic.horizon(),
        synthetic.assumptions(coupon_policy=policy),
        tax_classes=synthetic.TAX_PACK,
    )
    assert isinstance(outcome, Projection), f"expected a projection, got {outcome!r}"
    return outcome


def _terminal(policy: str) -> Money:
    """The spendable cash a policy leaves behind: the UAH balance at the end of the fold."""
    return _projection(policy).ledger.accounts[UAH].balance


class TestTheTerminalAmountsDiffer:
    """The claim SC-010 makes, at three levels."""

    def test_the_two_policies_leave_different_amounts_of_cash(self) -> None:
        # 34 497.05479452055 against 31 000.00 -- the difference is the compounding.
        assert_money_close(
            _terminal(fixed_income.REINVEST), Money(REINVESTED_TERMINAL, UAH, prov.EMPTY)
        )
        assert_money_close(_terminal(fixed_income.HOLD_CASH), Money(HELD_TERMINAL, UAH, prov.EMPTY))
        assert is_close(
            _terminal(fixed_income.REINVEST).amount - _terminal(fixed_income.HOLD_CASH).amount,
            DIFFERENCE,
        )

    def test_the_cash_sits_in_a_uah_balance_and_in_no_other_currency(self) -> None:
        """SC-010's *"the cash sits in a UAH balance"*, taken literally.

        One account, in the instrument's own currency, and no second account brought into
        existence by a policy. A reinvestment that opened a balance in another denomination
        would be an FX conversion nobody declared (FR-007).
        """
        for policy in (fixed_income.REINVEST, fixed_income.HOLD_CASH):
            accounts = _projection(policy).ledger.accounts
            assert set(accounts) == {UAH}
            assert accounts[UAH].balance.currency is UAH
            assert accounts[UAH].balance.amount > 0.0

    def test_the_units_held_differ_too_so_the_difference_is_not_only_cash(self) -> None:
        # 123 units redeemed against 100: the reinvestments are real holdings, recorded as
        # lots, and not a cash adjustment dressed up as compounding.
        assert _projection(fixed_income.REINVEST).schedule.rows[-1].quantity == 123.0
        assert _projection(fixed_income.HOLD_CASH).schedule.rows[-1].quantity == QUANTITY

    def test_the_whole_result_differs_and_not_merely_the_headline(self) -> None:
        """Two policies, two digests. The digest covers every event and every figure."""
        assert manifest.digest(
            canonical.of_projection(_projection(fixed_income.REINVEST))
        ) != manifest.digest(canonical.of_projection(_projection(fixed_income.HOLD_CASH)))

    def test_holding_cash_emits_nothing_beyond_the_contractual_schedule(self) -> None:
        """*"``hold_cash`` emits nothing further"* -- the contract, asserted.

        Six rows: the purchase, four coupons, the redemption. Exactly D1's shape at a
        different size, which is what makes ``hold_cash`` the contractual baseline the other
        policy is measured against.
        """
        assert [row.kind for row in _projection(fixed_income.HOLD_CASH).schedule.rows] == [
            EventKind.PURCHASE,
            EventKind.COUPON,
            EventKind.COUPON,
            EventKind.COUPON,
            EventKind.COUPON,
            EventKind.PRINCIPAL_REPAYMENT,
        ]

    def test_reinvesting_adds_a_purchase_behind_each_coupon_that_could_fund_one(self) -> None:
        rows = _projection(fixed_income.REINVEST).schedule.rows
        reinvestments = [row for row in rows if row.kind is EventKind.REINVESTMENT]
        coupons = [row for row in rows if row.kind is EventKind.COUPON]
        assert len(coupons) == 4
        assert len(reinvestments) == 3  # the last coupon is paid at maturity
        for reinvestment in reinvestments:
            assert reinvestment.occurred_on in {row.occurred_on for row in coupons}


class TestTheDifferenceIsNotATaxArtefactOrARateChange:
    """What the difference is *not*, since both would be easy to mistake it for."""

    def test_tax_is_exactly_zero_under_both_policies(self) -> None:
        """The exempt class charges nothing either way, so the gap is pure compounding."""
        for policy in (fixed_income.REINVEST, fixed_income.HOLD_CASH):
            result = _projection(policy)
            assert result.hurdle.total_tax.amount == 0.0
            assert len(result.charges) == 5  # four coupons and the redemption

    def test_reinvestment_raises_the_amount_and_leaves_the_rate_where_it_was(self) -> None:
        """The insight worth stating: the extra units earn the *same* declared yield.

        Reinvesting at par buys more of the same bond, so the rate is unchanged while the
        terminal amount grows by 3 497.05. A reader who expected the *rate* to rise has
        misread what reinvestment does, and a reader who expected the amount not to rise has
        misread compounding.

        **This test originally asserted the opposite of one of the lines below**, and was
        wrong: it required ``nominal_ytm`` to *move* with the policy, reasoning about
        "16.0586% against 16.0536%" as though a contractual yield could depend on what the
        owner does with the coupons. It cannot -- reinvestment is a decision about the
        proceeds, not a term of the paper -- and the figure was being computed from the
        policy's own event stream. Both the figure and this test were corrected; see
        ``tests/unit/test_contractual_yield_is_policy_invariant.py``, which exists so the
        regression cannot come back quietly.

        The two figures now behave as FR-005 says they must: the contractual yield is
        identical, and the cash-flow-weighted return -- which describes what actually
        happened -- moves. The bound on that movement is deliberately loose and stated as
        loose rather than dressed up as the project tolerance (FR-002): reinvesting at par
        should barely shift a money-weighted return, so this is a sanity band, not a
        definition of the figure.
        """
        reinvest = _projection(fixed_income.REINVEST).hurdle
        held = _projection(fixed_income.HOLD_CASH).hurdle

        assert is_close(reinvest.nominal_ytm.value, held.nominal_ytm.value), (
            "the contractual yield must not move with the coupon policy"
        )

        moved = abs(reinvest.nominal_cash_flow_return.value - held.nominal_cash_flow_return.value)
        assert moved > 0.0, "the cash-flow return must reflect what actually happened"
        assert moved < 1e-4, "reinvesting at par should barely shift a money-weighted return"

        assert is_close(
            _terminal(fixed_income.REINVEST).amount - _terminal(fixed_income.HOLD_CASH).amount,
            DIFFERENCE,
        )

    def test_both_figures_still_state_what_they_exclude_and_what_they_are_net_of(self) -> None:
        """A policy does not change the boundaries of the figure (Principle VI)."""
        for policy in (fixed_income.REINVEST, fixed_income.HOLD_CASH):
            hurdle = _projection(policy).hurdle
            assert hurdle.accounts_for
            assert any("route" in item for item in hurdle.excludes)
            assert prov.is_unverified(hurdle.provenance)


class TestNeitherPolicyCanBeReachedByAccident:
    """No default, and an unrecognised name fails loudly naming the alternatives."""

    def test_the_registry_holds_exactly_the_two_names_fr019_requires(self) -> None:
        assert set(fixed_income.COUPON_POLICY_FNS) == {"hold_cash", "reinvest"}
        assert fixed_income.HOLD_CASH == "hold_cash"
        assert fixed_income.REINVEST == "reinvest"

    def test_an_unknown_policy_names_the_value_and_the_known_policies(self) -> None:
        with pytest.raises(KeyError) as caught:
            fixed_income.coupon_policy("reinvest_at_the_curve")
        message = str(caught.value)
        assert "reinvest_at_the_curve" in message
        assert "hold_cash" in message
        assert "reinvest" in message
        assert "no default" in message

    def test_a_projection_with_an_unknown_policy_fails_rather_than_choosing_one(self) -> None:
        """It raises rather than returning a typed failure, and that is the right call.

        A policy name is validated before a run starts -- there are two of them and they are
        not owner prose -- so a name reaching the schedule generator unrecognised means the
        caller passed something no interface offered. That is a statement about the code, not
        about the money, which is the line the constitution draws for ``raise``.
        """
        with pytest.raises(KeyError, match="coupon policy"):
            project.project(
                synthetic.declaration(),
                synthetic.holding(quantity=QUANTITY, cost=COST),
                synthetic.horizon(),
                synthetic.assumptions(coupon_policy="whatever_looks_best"),
                tax_classes=synthetic.TAX_PACK,
            )

    def test_holding_cash_says_it_chose_not_to_buy_rather_than_that_it_could_not(self) -> None:
        """The reason must not blame the minimum unit for a decision the policy made.

        On this purchase the first coupon of 7 686.30 would comfortably buy seven bonds at
        1 000.00. Under ``hold_cash`` nothing is bought anyway, and a reason saying the
        coupon "does not cover one increment" would be false -- the sort of plausible
        explanation that sends a reader looking for a bug in the wrong place.
        """
        (first, *_) = fixed_income.coupon_plan(
            synthetic.declaration(),
            synthetic.holding(quantity=QUANTITY, cost=COST),
            synthetic.assumptions(coupon_policy=fixed_income.HOLD_CASH),
        )
        assert first.reinvestment.units_bought == 0.0
        assert "would cover an increment" in first.reinvestment.reason
        assert "the declared coupon policy bought nothing" in first.reinvestment.reason
        assert "does not cover" not in first.reinvestment.reason
        assert_money_close(first.reinvestment.retained_as_cash, first.coupon)

    def test_the_policy_is_an_assumption_and_not_a_declared_term(self) -> None:
        """It belongs to the owner, not to the issue.

        The same declaration serves both runs unchanged: nothing about the bond's terms
        says what its holder does with a coupon, and putting the policy in the declaration
        would make one owner's choice a property of the instrument.
        """
        declaration = synthetic.declaration()
        assert not hasattr(declaration.terms, "coupon_policy")
        assert declaration == synthetic.declaration()
        assert (
            synthetic.assumptions(coupon_policy=fixed_income.REINVEST).coupon_policy
            != synthetic.assumptions().coupon_policy
        )
