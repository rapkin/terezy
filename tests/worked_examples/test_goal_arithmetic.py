"""FR-014: each solved figure against arithmetic worked out here, in the same model.

Required test **J1**'s hand-computed half; the generated round trips are
``tests/invariants/test_goal_mode_consistency.py``.

**The model, stated once, because the whole requirement is that the engine and the hand are
checking the same one** (FR-014's second half, and it travels in the result as
``GoalOutcome.conventions``):

* a contribution lands at the **end** of each whole month;
* the balance compounds **monthly**;
* the monthly rate is the **twelfth root** of the annual one, ``i = (1+g)^(1/12) - 1``, so
  twelve months of growth is exactly the declared annual rate rather than 1.0617x it. This is
  the convention ``core.results.hurdle`` already discounts with -- ``(1+r)**years`` at a
  fractional exponent -- and a second convention here would make a goal disagree with the
  hurdle rate the owner most likely points it at;
* time is measured in **monthly anniversaries** of the evaluation date, plus the elapsed
  fraction of the month in progress.

So after ``t`` months, starting from ``S`` and paying ``C`` at each month end::

    V(t) = S * (1+i)^t  +  C * ((1+i)^t - 1) / i        (i != 0)
    V(t) = S + C * t                                    (i == 0)

**The numbers are chosen so the monthly rate is exactly 1%.** The declared annual rate is
``1.01^12 - 1 = 0.12682503013196977``, which is what "12.68% a year" means under this
convention, and every figure below follows from ``i = 0.01``. The one compounding factor they
all rest on is written out here so the assertions can be read without a calculator::

    1.01^2  = 1.0201
    1.01^4  = 1.0201^2         = 1.04060401
    1.01^8  = 1.04060401^2     = 1.0828567056280801
    1.01^12 = 1.01^8 * 1.01^4  = 1.1268250301319698
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.goals import solve
from terezy.core.goals.solve import months_between, projected_value
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results.goal import Goal, GoalInputs, GoalOutcome, GrowthAssumption, Met

pytestmark = pytest.mark.worked_example

UAH = Currency.UAH
OWNER = "owner-001"
AS_OF = date(2026, 1, 31)

ANNUAL = 0.12682503013196977
"""``1.01^12 - 1``: an annual rate that compounds to exactly one percent a month."""

STARTING = 100_000.0
CONTRIBUTION = 10_000.0


def _inputs(*, starting: float = STARTING, annual: float = ANNUAL) -> GoalInputs:
    """The frame a goal is evaluated in: from when, from what, at what rate."""
    return GoalInputs(
        as_of=AS_OF,
        base_currency=UAH,
        starting_amount=Money(starting, UAH, prov.EMPTY),
        growth=GrowthAssumption(annual_rate=annual, provenance=prov.EMPTY),
    )


def _goal(
    *,
    contribution: float | None = None,
    target_sum: float | None = None,
    target_date: date | None = None,
) -> Goal:
    return Goal(
        owner_id=OWNER,
        id="worked_example",
        currency=UAH,
        monthly_contribution=None if contribution is None else Money(contribution, UAH, prov.EMPTY),
        target_sum=None if target_sum is None else Money(target_sum, UAH, prov.EMPTY),
        target_date=target_date,
    )


def _solved(goal: Goal, *, inputs: GoalInputs | None = None) -> GoalOutcome:
    outcome = solve.solve(
        goal,
        inputs=inputs if inputs is not None else _inputs(),
        conventions=solve.MONTHLY_END_OF_PERIOD,
    )
    assert isinstance(outcome, GoalOutcome), outcome
    return outcome


# ---------------------------------------------------------------------------
# The sum mode: what will I have by then
# ---------------------------------------------------------------------------


def test_the_sum_reached_by_a_stated_date_is_the_hand_computed_figure() -> None:
    """US3 scenario 1. Twelve months from 2026-01-31 is 2027-01-31, exactly 12 periods.

        growth on the opening balance   = 100 000.00 * 1.1268250301319698
                                        = 112 682.50301319698

        the twelve contributions        = 10 000.00 * (1.1268250301319698 - 1) / 0.01
                                        = 10 000.00 * 12.682503013196973
                                        = 126 825.03013196973

        total                           = 239 507.53314516676 UAH

    The second term is the ordinary annuity factor: the first contribution lands at the end of
    month one and earns eleven months of growth, the last lands at the end of month twelve and
    earns none. Paying at the *start* of each month instead would multiply that term by 1.01
    and add 1 268.25 -- which is why the timing convention travels in the result.
    """
    outcome = _solved(_goal(contribution=CONTRIBUTION, target_date=date(2027, 1, 31)))
    assert outcome.solved_for == "sum"
    assert_money_close(outcome.target_sum, Money(239_507.53314516676, UAH, prov.EMPTY))


def test_the_zero_growth_case_degenerates_to_saving_and_still_hand_computes() -> None:
    """Spec, Edge Cases: a growth assumption of exactly zero is valid.

        V(10) = 50 000.00 + 5 000.00 * 10 = 100 000.00 UAH

    Ten anniversaries of 2026-01-31 is 2026-11-30 -- the day is clamped to the length of the
    target month, which is the same rule a bond's coupon dates follow.
    """
    outcome = _solved(
        _goal(contribution=5_000.0, target_date=date(2026, 11, 30)),
        inputs=_inputs(starting=50_000.0, annual=0.0),
    )
    assert_money_close(outcome.target_sum, Money(100_000.0, UAH, prov.EMPTY))


# ---------------------------------------------------------------------------
# The contribution mode: what must I put in
# ---------------------------------------------------------------------------


def test_the_required_contribution_is_the_hand_computed_figure() -> None:
    """US3 scenario 3, and the inverse of the example above.

        required = (target - opening grown) * i / ((1+i)^t - 1)
                 = (239 507.53314516676 - 112 682.50301319698) * 0.01 / 0.12682503013196973
                 = 126 825.03013196978 * 0.01 / 0.12682503013196973
                 = 10 000.00 UAH a month

    Evaluating that contribution forward reproduces the target, which is the round trip
    FR-013 requires and which the property suite checks over a generated body.
    """
    outcome = _solved(_goal(target_sum=239_507.53314516676, target_date=date(2027, 1, 31)))
    assert outcome.solved_for == "contribution"
    assert_money_close(outcome.monthly_contribution, Money(10_000.0, UAH, prov.EMPTY))
    assert_money_close(
        projected_value(_inputs(), contribution=outcome.monthly_contribution, months=12.0),
        Money(239_507.53314516676, UAH, prov.EMPTY),
    )


# ---------------------------------------------------------------------------
# The date mode: when do I get there
# ---------------------------------------------------------------------------


def test_the_date_solved_from_a_contribution_and_a_target_is_the_hand_computed_one() -> None:
    """US3 scenario 2.

        t = ln((target + C/i) / (S + C/i)) / ln(1+i)
          = ln((239 507.53314516676 + 1 000 000) / (100 000 + 1 000 000)) / ln(1.01)
          = ln(1.1268250301319698) / 0.009950330853155723
          = 0.11940964836...  / 0.009950330853155723
          = 12 months

    ``C/i`` is 10 000 / 0.01 = 1 000 000: the balance the contribution alone would settle at
    if the rate were negative, and the constant that turns the annuity into a plain
    exponential. It is the same rearrangement as the sum mode, run backwards.
    """
    outcome = _solved(_goal(contribution=CONTRIBUTION, target_sum=239_507.53314516676))
    assert outcome.solved_for == "date"
    assert outcome.exact_date is not None
    assert is_close(outcome.exact_date.exact, 12.0)
    assert outcome.exact_date.first_reached_on == date(2027, 1, 31)
    assert outcome.target_date == date(2027, 1, 31)


def test_a_solution_between_two_contribution_dates_reports_both_answers() -> None:
    """FR-015, G5, and the reason there are two fields rather than one.

        V(12.5) = 100 000 * 1.01^12.5 + 10 000 * (1.01^12.5 - 1) / 0.01
                = 100 000 * 1.1324451399592097 + 10 000 * 13.244513995920966
                = 113 244.51399592097 + 132 445.13995920966
                = 245 689.65395513066 UAH

    Solved backwards that target lands at **12.5 months**, which is no date at all: the
    twelfth contribution has landed and the thirteenth has not. The exact solution is what
    makes the round trip close; the first calendar date on which the target is actually
    reached is the thirteenth month end, 2027-02-28. Reporting either one alone would break
    the other, and rounding one into the other silently is what FR-015 forbids by name.
    """
    outcome = _solved(_goal(contribution=CONTRIBUTION, target_sum=245_689.65395513066))
    assert outcome.exact_date is not None
    assert is_close(outcome.exact_date.exact, 12.5)
    assert outcome.exact_date.first_reached_on == date(2027, 2, 28)

    # Neither is the other: at the exact solution the target is met to the kopiyka, and by the
    # first reached date it has been overshot -- by the thirteenth contribution and a month of
    # growth on the twelfth balance.
    assert_money_close(
        projected_value(_inputs(), contribution=Money(CONTRIBUTION, UAH, prov.EMPTY), months=12.5),
        Money(245_689.65395513066, UAH, prov.EMPTY),
    )
    at_thirteen = projected_value(
        _inputs(), contribution=Money(CONTRIBUTION, UAH, prov.EMPTY), months=13.0
    )
    assert at_thirteen.amount > 245_689.65395513066


# ---------------------------------------------------------------------------
# The conventions travel with the answer
# ---------------------------------------------------------------------------


def test_a_target_date_inside_a_month_counts_the_days_of_that_month() -> None:
    """The month-count convention, hand-checked on the case that makes it a convention at all.

    From 2026-01-31 to 2026-02-27 is *not* one month: the first anniversary is 2026-02-28 --
    the day clamped to the length of February, the rule a bond's coupon dates follow -- and the
    target date falls a day short of it.

        whole anniversaries passed        = 0
        days from 2026-01-31 to 2026-02-27 = 27
        days in the anniversary month      = 28   (2026-01-31 -> 2026-02-28)
        months                             = 0 + 27 / 28 = 0.9642857142857143

    A fixed 30.44-day month would give 0.887 for the same pair, and every figure solved over
    that horizon would be wrong by the difference while looking entirely plausible.
    """
    assert is_close(months_between(AS_OF, date(2026, 2, 27)), 27.0 / 28.0)
    assert is_close(months_between(AS_OF, date(2026, 2, 28)), 1.0)
    assert is_close(months_between(AS_OF, date(2027, 1, 31)), 12.0)


def test_the_conventions_the_arithmetic_depends_on_are_in_the_result() -> None:
    """FR-014's second half, G4: the hand computation above is only checkable against a
    stated model, so the model is on the record rather than implicit in the code."""
    conventions = _solved(_goal(contribution=CONTRIBUTION, target_date=date(2027, 1, 31)))
    assert conventions.conventions == solve.MONTHLY_END_OF_PERIOD
    assert conventions.conventions.contribution_timing == "end_of_period"
    assert conventions.conventions.compounding == "monthly"
    assert conventions.conventions.monthly_rate == "twelfth_root_of_annual"
    assert conventions.conventions.month_count == "anniversary_actual_days"


def test_a_solved_goal_is_met_with_no_margin_worth_reporting() -> None:
    """The residual of the solve, reported rather than assumed to be zero.

    A margin that was not ~0 here would mean the closed form and the evaluation disagree --
    that the engine solved one model and reports another -- which is exactly the failure an
    iterative solver would hide inside the tolerance.
    """
    outcome = _solved(_goal(contribution=CONTRIBUTION, target_sum=239_507.53314516676))
    assert isinstance(outcome.feasibility, Met)
    assert_money_close(outcome.feasibility.margin, Money(0.0, UAH, prov.EMPTY))
