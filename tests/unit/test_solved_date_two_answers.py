"""FR-015, G5, research.md D5: the date mode has two correct answers and returns both.

They are different facts and neither substitutes for the other.

* **The exact solution** is the real-valued point at which the balance equals the target. It
  is what makes the three modes consistent -- evaluating the sum at that point returns the
  original target, which is FR-013's round trip -- and it is generally not a date at all: a
  target reached at 12.5 months is reached when the twelfth contribution has landed and the
  thirteenth has not.
* **The first calendar date on which the target is actually reached** is what the owner can
  act on. It is the first month end at which the balance is at or above the target.

Reporting only the calendar date breaks the consistency property; reporting only the exact one
answers a question nobody asked; rounding one into the other silently is the nearest answer
this spec forbids twice. So both are on the record, each labelled as what it is.

**The ceiling is exact, not a rounding**, and the distinction is the whole of FR-015. The
balance is strictly increasing between contributions whenever the target is reachable at all,
so "the first month end at or after the exact solution" *is* "the first month end at which the
target is reached" -- the tests below check that directly, by evaluating the balance at the
month before and the month of, rather than by re-deriving the ceiling.
"""

from __future__ import annotations

from datetime import date

from terezy.core.goals import solve
from terezy.core.goals.solve import projected_value
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.conventions import shift_months
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results.goal import (
    Goal,
    GoalInputs,
    GoalOutcome,
    GrowthAssumption,
    NoContributionNeeded,
)

UAH = Currency.UAH
AS_OF = date(2026, 1, 31)
ANNUAL = 0.12682503013196977
"""``1.01^12 - 1``: exactly one percent a month. See ``tests/worked_examples/…``."""

STARTING = 100_000.0
CONTRIBUTION = 10_000.0

BETWEEN_CONTRIBUTIONS = 245_689.65395513066
"""The balance at 12.5 months, so the exact solution lands halfway between two month ends."""

ON_A_CONTRIBUTION = 239_507.53314516676
"""The balance at exactly 12 months, so the two answers coincide."""

INPUTS = GoalInputs(
    as_of=AS_OF,
    base_currency=UAH,
    starting_amount=Money(STARTING, UAH, prov.EMPTY),
    growth=GrowthAssumption(annual_rate=ANNUAL, provenance=prov.EMPTY),
)


def _solved(target: float) -> GoalOutcome:
    outcome = solve.solve(
        Goal(
            owner_id="owner-001",
            id="two_answers",
            currency=UAH,
            monthly_contribution=Money(CONTRIBUTION, UAH, prov.EMPTY),
            target_sum=Money(target, UAH, prov.EMPTY),
            target_date=None,
        ),
        inputs=INPUTS,
        conventions=solve.MONTHLY_END_OF_PERIOD,
    )
    assert isinstance(outcome, GoalOutcome), outcome
    return outcome


def _value_at(months: float) -> Money:
    return projected_value(INPUTS, contribution=Money(CONTRIBUTION, UAH, prov.EMPTY), months=months)


def test_both_answers_are_present_and_they_are_different_numbers() -> None:
    """The case the requirement is about: a solution strictly between two contributions."""
    outcome = _solved(BETWEEN_CONTRIBUTIONS)
    assert outcome.exact_date is not None
    assert is_close(outcome.exact_date.exact, 12.5)
    assert outcome.exact_date.first_reached_on == date(2027, 2, 28)
    assert outcome.exact_date.first_reached_on != shift_months(AS_OF, 12)


def test_the_exact_solution_is_the_one_the_round_trip_closes_on() -> None:
    """FR-013 through FR-015: this is what makes the exact answer the *exact* one."""
    outcome = _solved(BETWEEN_CONTRIBUTIONS)
    assert outcome.exact_date is not None
    assert_money_close(
        _value_at(outcome.exact_date.exact), Money(BETWEEN_CONTRIBUTIONS, UAH, prov.EMPTY)
    )


def test_the_first_reached_date_is_the_first_month_end_that_actually_gets_there() -> None:
    """Checked against the balance rather than against the ceiling that produced it.

    Deriving the date by ``ceil`` and then asserting it equals ``ceil`` would be a test of one
    line against itself. The claim is about the money: at the previous month end the target is
    not met, and at this one it is.
    """
    outcome = _solved(BETWEEN_CONTRIBUTIONS)
    assert outcome.exact_date is not None
    reached_at = outcome.exact_date.first_reached_on
    months_to_reach = 13.0
    assert shift_months(AS_OF, int(months_to_reach)) == reached_at
    assert _value_at(months_to_reach - 1.0).amount < BETWEEN_CONTRIBUTIONS
    assert _value_at(months_to_reach).amount >= BETWEEN_CONTRIBUTIONS


def test_neither_answer_is_rounded_into_the_other() -> None:
    """The exact solution is not the calendar date's month count, and the balance on the
    calendar date is not the target: both statements are true at once, which is exactly why
    reporting one figure would have to be wrong about something."""
    outcome = _solved(BETWEEN_CONTRIBUTIONS)
    assert outcome.exact_date is not None
    assert outcome.exact_date.exact != 13.0
    assert _value_at(13.0).amount > BETWEEN_CONTRIBUTIONS


def test_when_the_solution_lands_on_a_contribution_the_two_answers_coincide() -> None:
    """They are allowed to agree -- what is forbidden is one being derived from the other by
    rounding. Here 12.0 months *is* 2027-01-31, and both fields say so."""
    outcome = _solved(ON_A_CONTRIBUTION)
    assert outcome.exact_date is not None
    assert is_close(outcome.exact_date.exact, 12.0)
    assert outcome.exact_date.first_reached_on == date(2027, 1, 31)
    assert_money_close(_value_at(12.0), Money(ON_A_CONTRIBUTION, UAH, prov.EMPTY))


def test_the_reported_target_date_is_the_one_the_owner_can_act_on() -> None:
    """``target_date`` on the result is the first reached date, and the exact solution sits
    beside it in months rather than being folded into it."""
    outcome = _solved(BETWEEN_CONTRIBUTIONS)
    assert outcome.exact_date is not None
    assert outcome.target_date == outcome.exact_date.first_reached_on


def test_a_target_already_met_at_the_evaluation_date_has_no_date_to_report() -> None:
    """There is no date on which a target that was never unmet is *reached*.

    The alternatives were both worse. Reporting the mathematical crossing would name a date in
    the past -- when this balance would have passed the target at this rate, had it existed --
    which answers a question about history rather than about the plan. And under a *shrinking*
    balance the crossing is in the future and is the moment the money falls **to** the target,
    so a solver that reported it would tell an owner holding five million that he reaches ten
    thousand in a hundred and twenty years. Both are answered the same way and honestly: the
    target is met now, by this margin, and nothing needs to go in to get there.
    """
    outcome = solve.solve(
        Goal(
            owner_id="owner-001",
            id="two_answers",
            currency=UAH,
            monthly_contribution=Money(CONTRIBUTION, UAH, prov.EMPTY),
            target_sum=Money(STARTING / 2.0, UAH, prov.EMPTY),
            target_date=None,
        ),
        inputs=INPUTS,
        conventions=solve.MONTHLY_END_OF_PERIOD,
    )
    assert isinstance(outcome, NoContributionNeeded), outcome
    assert_money_close(outcome.margin, Money(STARTING / 2.0, UAH, prov.EMPTY))
    assert AS_OF.isoformat() in outcome.reason
