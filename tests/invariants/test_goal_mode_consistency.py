"""SC-001, FR-013, G3: the three modes are one model seen from three sides, and they agree.

Required test **J1**. *Across a generated body of ``(contribution, sum)`` pairs -- not a
single example -- solving the date and then solving the sum back returns the original sum
within the single project tolerance, with zero exceptions.*

**Why a property and not a hand-picked round trip** (research.md D6). A round trip that closes
for one example is a coincidence until it closes for a thousand, and the failure this
requirement is aimed at -- a mode that quietly defines its own epsilon, which FR-013 forbids
in as many words -- shows up as a drift that only a range of magnitudes reveals. The
hand-computed side of J1 is ``tests/worked_examples/test_goal_arithmetic.py``.

**Every comparison here imports the project tolerance.** No ``pytest.approx``, no
``math.isclose`` with a bound of its own, no numeric literal. The last property in this module
checks the *solver* for the same thing, because a tolerance smuggled into the engine would
make every property above pass by construction.

**Why the generated rates are a sampled band rather than an arbitrary float.** The closed
forms divide by the monthly rate, and at a rate of ``1e-300`` that division is a statement
about float64 rather than about the model -- the annuity term and the opening term cancel to
noise. The band spans zero, small, ordinary and large rates, and includes a negative one so
the asymptote branch is exercised; what it excludes is arithmetic that would test the
floating-point unit instead of the solver.

**And why the generated targets start at ten thousand.** The same reason, from the other side:
the annuity term and the opening term are large numbers that cancel down to the target, so the
absolute error in the result scales with ``contribution / monthly rate`` rather than with the
target. Against a target of one hryvnia that cancellation exceeds the project tolerance while
the model is exactly right, which would make the suite a test of float64. The floor keeps the
comparison a test of the arithmetic; the cancellation itself is the reason the closed forms are
written the way the hand computation is, rather than in some algebraically equivalent
rearrangement.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest
from hypothesis import assume, example, given
from hypothesis import strategies as st

from terezy.core.goals import solve
from terezy.core.goals.solve import SolveOutcome, months_between, projected_value
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
    Met,
    Missed,
    NoContributionNeeded,
    Unreachable,
)

UAH = Currency.UAH
OWNER = "owner-001"

_ANNUAL_RATES = st.sampled_from(
    [-0.05, 0.0, 0.005, 0.01, 0.05, 0.1234, 0.12682503013196977, 0.25, 0.4]
)
_FEASIBILITY_RATES = st.sampled_from(
    [-0.5, -0.05, 0.0, 0.005, 0.01, 0.05, 0.1234, 0.12682503013196977, 0.25, 0.4]
)
"""The same band with a **fast** decay added, for the feasibility property only.

A rate of -50% a year takes a balance through a target in months rather than in centuries,
which is what makes the falls-through-the-target case land inside a generated horizon at all.

It is deliberately **not** in the round-trip band. At that rate a horizon of a few hundred
months puts the balance within a nanoshare of the level it converges to, and inverting a value
that close to an asymptote is ill-conditioned in float64 -- the round trip then measures the
resolution of a logarithm rather than the agreement of the modes. That is a property of the
inverse, not of the model, and widening the project tolerance to cover it would be exactly the
absorption FR-013 exists to prevent.
"""
_STARTING = st.integers(min_value=0, max_value=5_000_000)
_CONTRIBUTIONS = st.integers(min_value=0, max_value=200_000)
_TARGETS = st.integers(min_value=10_000, max_value=20_000_000)
_MONTHS = st.floats(min_value=0.5, max_value=480.0, allow_nan=False, allow_infinity=False)
_AS_OF = st.dates(min_value=date(2024, 1, 1), max_value=date(2030, 12, 31))
_HORIZONS = st.integers(min_value=1, max_value=480)


def _inputs(as_of: date, starting: int, annual: float) -> GoalInputs:
    return GoalInputs(
        as_of=as_of,
        base_currency=UAH,
        starting_amount=Money(float(starting), UAH, prov.EMPTY),
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
        id="generated",
        currency=UAH,
        monthly_contribution=None if contribution is None else Money(contribution, UAH, prov.EMPTY),
        target_sum=None if target_sum is None else Money(target_sum, UAH, prov.EMPTY),
        target_date=target_date,
    )


def _solve(goal: Goal, inputs: GoalInputs) -> SolveOutcome:
    return solve.solve(goal, inputs=inputs, conventions=solve.MONTHLY_END_OF_PERIOD)


# ---------------------------------------------------------------------------
# The round trips
# ---------------------------------------------------------------------------


@pytest.mark.invariant
@given(
    as_of=_AS_OF,
    starting=_STARTING,
    annual=_ANNUAL_RATES,
    contribution=_CONTRIBUTIONS,
    target=_TARGETS,
)
def test_the_date_solved_from_a_pair_reproduces_the_sum(
    as_of: date, starting: int, annual: float, contribution: int, target: int
) -> None:
    """SC-001 itself: solve the date, then evaluate the sum at that date, and get the target.

    The *exact* solution is what the round trip closes on, which is what makes it the value
    FR-015 calls "the one for which the consistency property holds". The first calendar date
    beside it is a different fact and closes on a different, larger number -- asserted in
    ``tests/unit/test_solved_date_two_answers.py``.
    """
    inputs = _inputs(as_of, starting, annual)
    outcome = _solve(_goal(contribution=float(contribution), target_sum=float(target)), inputs)
    if isinstance(outcome, Unreachable | NoContributionNeeded):
        # Nothing was solved, so there is nothing to round-trip: the plan never gets there, or
        # it was already there before the first contribution. Both are answers rather than
        # failures, and both are asserted in tests/unit/test_goal_feasibility.py.
        return
    assert isinstance(outcome, GoalOutcome), outcome
    assert outcome.exact_date is not None
    assert_money_close(
        projected_value(
            inputs,
            contribution=Money(float(contribution), UAH, prov.EMPTY),
            months=outcome.exact_date.exact,
        ),
        Money(float(target), UAH, prov.EMPTY),
    )


@pytest.mark.invariant
@given(
    as_of=_AS_OF,
    starting=_STARTING,
    annual=_ANNUAL_RATES,
    contribution=_CONTRIBUTIONS,
    months=_MONTHS,
)
def test_the_sum_at_a_horizon_solves_back_to_that_horizon(
    as_of: date, starting: int, annual: float, contribution: int, months: float
) -> None:
    """The same round trip from the other end: value a horizon, then solve the horizon back.

    This direction is the one that catches an inverse which is only approximately an inverse,
    because the target it feeds in is an arbitrary real number rather than a round figure.
    """
    inputs = _inputs(as_of, starting, annual)
    reached = projected_value(
        inputs, contribution=Money(float(contribution), UAH, prov.EMPTY), months=months
    )
    # A target at or below the starting amount is already met, which the date mode answers with
    # "no contribution needed" rather than with a crossing -- there is no date on which a
    # target that was never unmet is reached. That case is asserted directly in
    # tests/unit/test_solved_date_two_answers.py; here it would only mean the generator drew a
    # horizon the round trip is not about.
    assume(reached.amount > starting)
    outcome = _solve(_goal(contribution=float(contribution), target_sum=reached.amount), inputs)
    assert isinstance(outcome, GoalOutcome), outcome
    assert outcome.exact_date is not None
    assert is_close(outcome.exact_date.exact, months)


@pytest.mark.invariant
@given(as_of=_AS_OF, starting=_STARTING, annual=_ANNUAL_RATES, target=_TARGETS, horizon=_HORIZONS)
def test_the_contribution_solved_for_a_date_reaches_the_target_on_that_date(
    as_of: date, starting: int, annual: float, target: int, horizon: int
) -> None:
    """FR-013's third round trip, G3: contribution -> sum closes as date -> sum does.

    This one runs entirely through the public modes and a calendar date, which is the form
    the owner would actually use: state the sum and the date, get the monthly figure, and
    check that paying it lands on the sum.
    """
    inputs = _inputs(as_of, starting, annual)
    target_date = shift_months(as_of, horizon)
    outcome = _solve(_goal(target_sum=float(target), target_date=target_date), inputs)
    if isinstance(outcome, NoContributionNeeded):
        # The starting amount alone already gets there: FR-020 refuses to present a negative
        # contribution as an instruction, so there is no figure to round-trip.
        return
    assert isinstance(outcome, GoalOutcome), outcome
    forward = _solve(
        _goal(contribution=outcome.monthly_contribution.amount, target_date=target_date), inputs
    )
    assert isinstance(forward, GoalOutcome), forward
    assert_money_close(forward.target_sum, Money(float(target), UAH, prov.EMPTY))


@pytest.mark.invariant
@given(
    as_of=_AS_OF,
    starting=_STARTING,
    annual=_ANNUAL_RATES,
    contribution=_CONTRIBUTIONS,
    horizon=_HORIZONS,
)
def test_a_goal_solved_and_then_fully_declared_is_met_with_no_margin(
    as_of: date, starting: int, annual: float, contribution: int, horizon: int
) -> None:
    """The feasibility verdict agrees with the solve that produced it.

    Solve the sum for a contribution and a date, then declare all three and ask whether they
    are consistent. Anything but "met, by nothing" would mean the two code paths disagree
    about the same model -- and the feasibility path is the one the owner is shown.
    """
    inputs = _inputs(as_of, starting, annual)
    target_date = shift_months(as_of, horizon)
    solved = _solve(_goal(contribution=float(contribution), target_date=target_date), inputs)
    assert isinstance(solved, GoalOutcome), solved

    verdict = _solve(
        _goal(
            contribution=float(contribution),
            target_sum=solved.target_sum.amount,
            target_date=target_date,
        ),
        inputs,
    )
    assert isinstance(verdict, GoalOutcome), verdict
    assert verdict.solved_for == "feasibility"
    assert isinstance(verdict.feasibility, Met), verdict.feasibility
    assert_money_close(verdict.feasibility.margin, Money(0.0, UAH, prov.EMPTY))


# ---------------------------------------------------------------------------
# A reported arrival is an arrival
# ---------------------------------------------------------------------------


@pytest.mark.invariant
@example(
    as_of=date(2026, 1, 31),
    starting=100_000,
    annual=-0.5,
    contribution=0,
    target=90_000,
    horizon=23,
)
@example(
    as_of=date(2026, 1, 31),
    starting=100_000,
    annual=-0.5,
    contribution=100,
    target=90_000,
    horizon=23,
)
@given(
    as_of=_AS_OF,
    starting=_STARTING,
    annual=_FEASIBILITY_RATES,
    contribution=_CONTRIBUTIONS,
    target=_TARGETS,
    horizon=_HORIZONS,
)
def test_a_missed_goal_never_reports_a_date_at_or_before_the_one_it_missed(
    *,
    as_of: date,
    starting: int,
    annual: float,
    contribution: int,
    target: int,
    horizon: int,
) -> None:
    """``Missed.reached_on`` is later than the target date, and the target is met by then.

    A unit test pins the case that was wrong; this pins the *claim*, over every combination of
    rate, contribution, starting amount and horizon the band generates. The failure it exists
    to catch is not arithmetic: under a shrinking balance the crossing formula returns a real,
    finite, entirely plausible date on which the balance passes **below** the target, and
    reporting it says the owner arrives on a date he is in fact leaving.

    Both halves are asserted, because either alone can be satisfied by a wrong answer: a date
    after the target date that the balance has not reached, or a balance above the target on a
    date that is not after the one that was asked for.

    The two ``@example`` cases are the reported regression, pinned so it is checked on every
    run rather than when the draw happens to land on it. The shape needs a fast decay, a
    starting amount above the target *and* a horizon past the crossing all at once, which the
    generated band reaches only occasionally -- and a regression guard that fires four times in
    ten is not a guard.
    """
    inputs = _inputs(as_of, starting, annual)
    target_date = shift_months(as_of, horizon)
    outcome = _solve(
        _goal(
            contribution=float(contribution),
            target_sum=float(target),
            target_date=target_date,
        ),
        inputs,
    )
    assert isinstance(outcome, GoalOutcome), outcome
    if not isinstance(outcome.feasibility, Missed):
        return
    assert outcome.feasibility.reached_on > target_date
    at_arrival = projected_value(
        inputs,
        contribution=Money(float(contribution), UAH, prov.EMPTY),
        months=months_between(as_of, outcome.feasibility.reached_on),
    )
    assert at_arrival.amount >= float(target) or is_close(at_arrival.amount, float(target))


# ---------------------------------------------------------------------------
# No mode defines its own tolerance
# ---------------------------------------------------------------------------


@pytest.mark.invariant
def test_the_solver_invents_no_bound_of_its_own() -> None:
    """FR-013's last sentence, checked in the syntax tree rather than argued in a docstring.

    Every property above compares with the imported project tolerance -- and would keep passing
    if the *solver* had quietly agreed with itself to three decimals, because a bound inside
    the engine makes a round trip close by construction. The constitution calls a local
    tolerance a defect (Principle IV, and FR-002 before it).

    So this reads the module's own AST, not its prose: no ``math.isclose``, no
    ``pytest.approx``, and no float literal beyond the ones the closed forms are written out of.
    A comparison the solver genuinely needs -- met against missed, a required contribution at or
    below zero -- goes through ``primitives.tolerance``, which is the single place FR-002 puts
    it, and that import is what this test permits rather than forbids.
    """
    tree = ast.parse(_solver_source())

    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, float)
    }
    assert literals <= {0.0, 1.0}, (
        f"the solver contains the float literals {sorted(literals - {0.0, 1.0})}; a numeric "
        "bound written into the engine is the local tolerance FR-013 forbids"
    )

    referenced = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)} | {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    assert "isclose" not in referenced
    assert "approx" not in referenced

    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    if {"is_close", "TOLERANCE", "assert_money_close"} & referenced:
        assert "terezy.core.primitives.tolerance" in imported, (
            "the solver compares floats without importing the project tolerance, which means "
            "it has one of its own"
        )


def _solver_source() -> str:
    """The solver's own text, read from the installed module rather than from a guessed path."""
    return Path(str(solve.__file__)).read_text(encoding="utf-8")
