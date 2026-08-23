"""SC-006, FR-018, FR-019, FR-020, G8-G10: told the truth when the goal cannot be met.

With all three variables fixed the question is no longer "solve the third" but "can these
three hold at once", and the answer is a verdict rather than a number:

* **met**, with the margin;
* **missed**, with *both* faces of the binding shortfall -- how much is missing at the target
  date, and the earliest date the target would actually arrive;
* **unreachable**, with the reason, never a capped horizon and never a distant date.

And in the contribution mode, a solved figure at or below zero is *"no contribution needed"*
with the margin, never a negative number presented as an instruction (FR-020).

**Nothing is ever adjusted to make a goal pass.** Every case below checks the declared
variables come back exactly as declared, because the failure this requirement guards against
is not a wrong number -- it is a right number answering a question the owner did not ask.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.goals import solve
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close
from terezy.core.results.goal import (
    Goal,
    GoalInputs,
    GoalOutcome,
    GrowthAssumption,
    Met,
    Missed,
    NoContributionNeeded,
    Unreachable,
)

UAH = Currency.UAH
AS_OF = date(2026, 1, 31)
IN_A_YEAR = date(2027, 1, 31)
ANNUAL = 0.12682503013196977
"""``1.01^12 - 1``: exactly one percent a month, so the figures below are hand-checkable."""

AT_TWELVE_MONTHS = 239_507.53314516676
"""What 100 000 at 10 000 a month reaches in twelve months. See the worked example."""


def _inputs(*, starting: float = 100_000.0, annual: float = ANNUAL) -> GoalInputs:
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
        owner_id="owner-001",
        id="feasibility",
        currency=UAH,
        monthly_contribution=None if contribution is None else Money(contribution, UAH, prov.EMPTY),
        target_sum=None if target_sum is None else Money(target_sum, UAH, prov.EMPTY),
        target_date=target_date,
    )


def _outcome(goal: Goal, inputs: GoalInputs | None = None) -> object:
    return solve.solve(
        goal,
        inputs=inputs if inputs is not None else _inputs(),
        conventions=solve.MONTHLY_END_OF_PERIOD,
    )


# ---------------------------------------------------------------------------
# All three fixed: met, missed, unreachable
# ---------------------------------------------------------------------------


def test_three_consistent_variables_are_met_with_their_margin() -> None:
    """US4 scenario 1. The target is 200 000 and the plan reaches 239 507.53314516676:

    margin = 239 507.53314516676 - 200 000.00 = 39 507.53314516676 UAH
    """
    outcome = _outcome(_goal(contribution=10_000.0, target_sum=200_000.0, target_date=IN_A_YEAR))
    assert isinstance(outcome, GoalOutcome), outcome
    assert outcome.solved_for == "feasibility"
    assert isinstance(outcome.feasibility, Met)
    assert_money_close(outcome.feasibility.margin, Money(39_507.53314516676, UAH, prov.EMPTY))


def test_a_target_met_exactly_is_met_by_nothing_rather_than_missed_by_a_hair() -> None:
    """Spec, Edge Cases: the single project tolerance governs the boundary.

    Reported as met with a zero margin. The alternative -- "missed by 3e-11" -- would be the
    float representation of the number leaking into a verdict about the owner's plan.
    """
    outcome = _outcome(
        _goal(contribution=10_000.0, target_sum=AT_TWELVE_MONTHS, target_date=IN_A_YEAR)
    )
    assert isinstance(outcome, GoalOutcome), outcome
    assert isinstance(outcome.feasibility, Met)
    assert_money_close(outcome.feasibility.margin, Money(0.0, UAH, prov.EMPTY))


def test_three_inconsistent_variables_are_missed_with_both_faces_of_the_shortfall() -> None:
    """US4 scenario 2, FR-018. The target is 300 000 by 2027-01-31:

        short at the date = 300 000.00 - 239 507.53314516676 = 60 492.46685483324 UAH

    and the earliest it would actually arrive is the seventeenth month end -- 2027-06-30 --
    because the sixteenth is still short. Both faces, because either alone leaves the owner
    with half the decision: how much more to put in, or how much longer to wait.
    """
    outcome = _outcome(_goal(contribution=10_000.0, target_sum=300_000.0, target_date=IN_A_YEAR))
    assert isinstance(outcome, GoalOutcome), outcome
    assert isinstance(outcome.feasibility, Missed)
    assert_money_close(
        outcome.feasibility.shortfall_at_target, Money(60_492.46685483324, UAH, prov.EMPTY)
    )
    assert outcome.feasibility.reached_on == date(2027, 6, 30)
    # The direction the record promises and the shrinking-balance test below pins from the
    # other side: an arrival is *later* than the date it was wanted by. A date before it would
    # be the plan losing the target rather than reaching it.
    assert outcome.feasibility.reached_on > IN_A_YEAR


def test_a_missed_goal_reports_the_variables_exactly_as_declared() -> None:
    """FR-018's last sentence, G8: no declared variable is adjusted to make a goal pass.

    The failure this guards against is not a wrong number. It is a right number answering a
    question the owner did not ask -- "you will have 239 507 by then" reported as though the
    300 000 he asked for had been the target all along.
    """
    outcome = _outcome(_goal(contribution=10_000.0, target_sum=300_000.0, target_date=IN_A_YEAR))
    assert isinstance(outcome, GoalOutcome), outcome
    assert outcome.monthly_contribution.amount == 10_000.0
    assert outcome.target_sum.amount == 300_000.0
    assert outcome.target_date == IN_A_YEAR


def test_a_target_that_can_never_be_reached_is_unreachable_with_its_reason() -> None:
    """US4 scenario 3, FR-019, G9: zero contribution and no growth against a bigger target.

    Nothing about this is a long wait. The balance is constant, so there is no date at which
    the target arrives, and reporting one -- however distant -- would be a nearest answer.

    The assertion is on *which* reason, not merely that there is one. The two shapes of
    unreachable are told apart by the message, and a message that said "the balance never
    moves" about a shrinking balance would be false while still passing a "reason is non-empty"
    check -- which is what the neighbouring shrinking-balance test pins from the other side.
    """
    outcome = _outcome(
        _goal(contribution=0.0, target_sum=500_000.0, target_date=IN_A_YEAR),
        _inputs(annual=0.0),
    )
    assert isinstance(outcome, GoalOutcome), outcome
    assert isinstance(outcome.feasibility, Unreachable)
    assert "never moves" in outcome.feasibility.reason
    assert "capped horizon" in outcome.feasibility.reason


def test_an_unreachable_target_in_the_date_mode_is_the_whole_answer() -> None:
    """FR-019 in the mode where there is no other answer to give.

    ``Unreachable`` is returned rather than wrapped in a result with an empty date field: a
    result whose date is missing invites a caller to substitute one, and there is nothing here
    that a substitution could honestly stand in for.
    """
    outcome = _outcome(
        _goal(contribution=0.0, target_sum=500_000.0),
        _inputs(annual=0.0),
    )
    assert isinstance(outcome, Unreachable), outcome
    assert "500" in outcome.reason or "target" in outcome.reason


def test_a_target_above_the_asymptote_of_a_shrinking_balance_is_unreachable() -> None:
    """The case a capped horizon would have hidden.

    Under a negative growth assumption a fixed contribution settles at a ceiling -- the level
    at which the monthly loss equals the monthly payment -- and a target above it is never
    reached however long the owner waits. A solver that searched forward would return the end
    of its search window and call it a date.
    """
    outcome = _outcome(
        _goal(contribution=1_000.0, target_sum=5_000_000.0),
        _inputs(starting=0.0, annual=-0.20),
    )
    assert isinstance(outcome, Unreachable), outcome
    # The reason names the ceiling rather than saying "never" and stopping, and it does *not*
    # claim the balance never moves -- it moves, which is the whole shape of this case. The
    # ceiling is where a monthly loss of 1.84% eats the thousand that goes in:
    #     1 000 / (1 - 0.8 ** (1/12)) = 54 278.59101175934
    assert "converges" in outcome.reason
    assert "54278.59101175934" in outcome.reason
    assert "never moves" not in outcome.reason


# ---------------------------------------------------------------------------
# The contribution that is not needed
# ---------------------------------------------------------------------------


def test_a_target_already_met_needs_no_contribution_and_says_so() -> None:
    """US4 scenario 4, FR-020, G10.

    The starting amount grows to 112 682.50301319698 in a year, which already exceeds the
    100 000 target, so the solved contribution comes out negative:

        margin = 112 682.50301319698 - 100 000.00 = 12 682.50301319698 UAH

    A negative monthly figure is arithmetically fine and operationally nonsense -- it is an
    instruction to withdraw, which is not what the owner asked for.
    """
    outcome = _outcome(_goal(target_sum=100_000.0, target_date=IN_A_YEAR))
    assert isinstance(outcome, NoContributionNeeded), outcome
    assert_money_close(outcome.margin, Money(12_682.50301319698, UAH, prov.EMPTY))
    assert outcome.reason.strip()


def test_a_target_met_to_the_kopiyka_by_the_starting_amount_alone_needs_no_contribution() -> None:
    """The boundary: a solved contribution of exactly zero is "none needed", not "zero a
    month". They are the same number and different statements, and FR-020 says *at or below*."""
    outcome = _outcome(_goal(target_sum=112_682.50301319698, target_date=IN_A_YEAR))
    assert isinstance(outcome, NoContributionNeeded), outcome
    assert_money_close(outcome.margin, Money(0.0, UAH, prov.EMPTY))


def test_a_target_just_out_of_reach_of_the_starting_amount_still_returns_a_contribution() -> None:
    """The other side of the same boundary, so the guard above cannot swallow a real answer.

    A guard that fired one hryvnia too early would silently tell an owner who needs to save
    that he needs to do nothing, which is the most expensive direction for this mistake.
    """
    outcome = _outcome(_goal(target_sum=112_700.0, target_date=IN_A_YEAR))
    assert isinstance(outcome, GoalOutcome), outcome
    assert outcome.monthly_contribution.amount > 0.0


def test_a_target_reached_past_the_end_of_the_calendar_names_the_months_instead() -> None:
    """FR-019 at the edge of what a date can express, and it is not a capped horizon.

    One hryvnia at half a percent a year reaches ten tredecillion in about two hundred and
    twenty thousand months -- eighteen thousand years, past the last date this calendar holds.
    The month count goes into the reason exactly as computed. What is *not* reported is a date:
    rounding the horizon back to the last expressible one would be the nearest answer FR-019
    forbids, and it would look like a plan that works.
    """
    outcome = _outcome(
        _goal(contribution=0.0, target_sum=1e40),
        _inputs(starting=1.0, annual=0.005),
    )
    assert isinstance(outcome, Unreachable), outcome
    assert "months" in outcome.reason
    assert "calendar" in outcome.reason


@pytest.mark.parametrize("contribution", [0.0, 100.0])
def test_a_shrinking_balance_that_starts_above_the_target_reports_no_arrival(
    contribution: float,
) -> None:
    """A crossing before the target date is the balance falling *through* it, not arriving.

    The regression this pins: with a negative assumption and a starting amount above the
    target, the crossing is a real, finite, future-of-the-evaluation-date month -- and reporting
    it as ``Missed.reached_on`` told the owner he "gets there" on 2026-03-31 for a goal he had
    set for 2028-01-01, twenty-two months later. Both the record's own docstring and
    METHODOLOGY say an arrival is later than the target date, so the guard belongs here rather
    than in the prose.

    Parametrised over a zero and a non-zero contribution because the two take different
    branches through the crossing formula and only one of them was reachable by accident.
    """
    outcome = _outcome(
        _goal(contribution=contribution, target_sum=90_000.0, target_date=date(2028, 1, 1)),
        _inputs(starting=100_000.0, annual=-0.5),
    )
    assert isinstance(outcome, GoalOutcome), outcome
    assert isinstance(outcome.feasibility, Unreachable), outcome.feasibility
    assert "falls through it" in outcome.feasibility.reason
    assert "2028-01-01" in outcome.feasibility.reason
    # The shortfall on the declared date is still reported: what is refused is a *date*, not
    # the arithmetic.
    assert "short by" in outcome.feasibility.reason


def test_a_target_the_plan_decays_away_from_says_so_rather_than_naming_a_ceiling() -> None:
    """The third shape of unreachable, and the one a two-branch message got wrong.

    Nothing goes in and the assumption is negative, so the balance decays towards **nothing**.
    The message must not describe a contribution "settling at" a level -- with no contribution
    that level is zero, and a sentence about a zero ceiling is a true number inside a false
    sentence.
    """
    outcome = _outcome(
        _goal(contribution=0.0, target_sum=500_000.0),
        _inputs(starting=100_000.0, annual=-0.5),
    )
    assert isinstance(outcome, Unreachable), outcome
    assert "decays" in outcome.reason
    assert "nothing goes in" in outcome.reason
    assert "settles at" not in outcome.reason
    assert "never moves" not in outcome.reason
