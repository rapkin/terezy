"""A contractual yield to maturity may not move when the coupon policy changes.

FR-005 requires two figures, "kept as separate figures and separately labelled", and the
first of them is *contractual*. Reinvestment is a decision about the proceeds, not a term
of the paper, so a bond's promised yield cannot depend on it. If it does, the figure is
labelled as something it is not -- which is the failure Principle I exists to prevent, and
it is invisible in the output: 16.0536% and 16.0586% both look like a plausible yield.

The regression this guards against was real. `nominal_ytm` was originally computed from
the taxed event stream minus its tax charges, which under ``reinvest`` still contains the
reinvestment purchases and the enlarged redemption -- so the "contractual" yield moved with
the policy. It is now generated from a second, policy-free stream.

The holding here is deliberately **100 units**, not the 10 of the standard fixture. At 10
units a coupon is ~768 UAH against a 1000 UAH minimum unit, so reinvestment can never buy
anything and both policies produce identical events -- the bug is invisible. Any test of
this property has to be large enough that reinvestment actually happens.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from terezy.core.instruments import fixed_income
from terezy.core.primitives import money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import project
from terezy.core.results.project import Projection
from tests import synthetic

REINVESTING_SIZE = 100.0
"""Large enough that a coupon clears the minimum unit and units are actually bought."""


def _projection(policy: str) -> Projection:
    terms = synthetic.terms()
    holding = replace(
        synthetic.holding(),
        quantity=REINVESTING_SIZE,
        cost=money.scale(terms.face_value, REINVESTING_SIZE),
    )
    outcome = project.project(
        synthetic.declaration(),
        holding,
        synthetic.horizon(),
        replace(synthetic.assumptions(), coupon_policy=policy),
        tax_classes=synthetic.TAX_PACK,
    )
    assert isinstance(outcome, Projection), outcome
    return outcome


@pytest.fixture(scope="module")
def held() -> Projection:
    return _projection(fixed_income.HOLD_CASH)


@pytest.fixture(scope="module")
def reinvested() -> Projection:
    return _projection(fixed_income.REINVEST)


def test_the_policies_really_do_diverge_at_this_size(
    held: Projection, reinvested: Projection
) -> None:
    """Guard the guard: if reinvestment bought nothing, everything below is vacuous."""
    assert len(reinvested.ledger.applied) > len(held.ledger.applied), (
        "reinvestment bought no units at this size, so the invariance below proves nothing"
    )


def test_the_contractual_yield_is_the_same_under_both_policies(
    held: Projection, reinvested: Projection
) -> None:
    """The paper promises what it promises, whatever the owner does with the coupons."""
    assert is_close(held.hurdle.nominal_ytm.value, reinvested.hurdle.nominal_ytm.value), (
        f"contractual yield moved with the coupon policy: "
        f"{held.hurdle.nominal_ytm.value!r} vs {reinvested.hurdle.nominal_ytm.value!r}"
    )


def test_the_cash_flow_return_does_differ(held: Projection, reinvested: Projection) -> None:
    """The other half of FR-005: the two figures must not be substitutes.

    The cash-flow-weighted return *should* move with the policy -- it describes what
    actually happened. If both figures were invariant, one of them would be redundant.
    """
    assert not is_close(
        held.hurdle.nominal_cash_flow_return.value,
        reinvested.hurdle.nominal_cash_flow_return.value,
    ), "both figures are policy-invariant, so one of them is not measuring what it claims"
