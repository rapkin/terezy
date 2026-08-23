"""G1, G2, G11: the solver's typed refusals, and what each of them refuses to invent.

Every one of these is a question the tool cannot answer, and the requirement in each case is
not that it fails but *how*: a typed value naming the missing thing, never a default, never an
exception, and never an answer to a nearby question.

The load-time halves of the same rules live in
``tests/contract/test_goal_declaration_loading.py``: a declaration with fewer than two
variables and a declaration in a non-base currency are both refused at the boundary, naming
the file and the field. These are the core's own guards, for a caller that assembles a goal
without a file -- the division ``UnresolvedTaxClass`` already draws between the resolver and
``results.project``.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.errors import CurrencyMismatchError
from terezy.core.goals import solve
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.goal import (
    CurrencyNotYetModelled,
    Goal,
    GoalInputs,
    GoalUnderdetermined,
    GrowthAssumption,
    GrowthAssumptionMissing,
    StartingAmountMissing,
    TargetDateNotInFuture,
)

UAH = Currency.UAH
USD = Currency.USD
AS_OF = date(2026, 1, 31)
IN_A_YEAR = date(2027, 1, 31)

GROWTH = GrowthAssumption(annual_rate=0.1, provenance=prov.EMPTY)
STARTING = Money(100_000.0, UAH, prov.EMPTY)


def _inputs(
    *,
    starting: Money | None = STARTING,
    growth: GrowthAssumption | None = GROWTH,
    base_currency: Currency = UAH,
) -> GoalInputs:
    return GoalInputs(
        as_of=AS_OF, base_currency=base_currency, starting_amount=starting, growth=growth
    )


def _goal(
    *,
    contribution: float | None = 10_000.0,
    target_sum: float | None = None,
    target_date: date | None = IN_A_YEAR,
    currency: Currency = UAH,
) -> Goal:
    return Goal(
        owner_id="owner-001",
        is_synthetic=True,
        id="refusals",
        currency=currency,
        monthly_contribution=(
            None if contribution is None else Money(contribution, currency, prov.EMPTY)
        ),
        target_sum=None if target_sum is None else Money(target_sum, currency, prov.EMPTY),
        target_date=target_date,
    )


def _outcome(goal: Goal, inputs: GoalInputs | None = None) -> object:
    return solve.solve(
        goal,
        inputs=inputs if inputs is not None else _inputs(),
        conventions=solve.MONTHLY_END_OF_PERIOD,
    )


# ---------------------------------------------------------------------------
# G1: any two solve the third, and fewer than two solve nothing
# ---------------------------------------------------------------------------


def test_one_declared_variable_is_underdetermined_and_names_the_missing_ones() -> None:
    """FR-011. A goal with only a contribution could be completed by inventing a sum or by
    inventing a date, and either would be the tool writing the owner's plan for him."""
    outcome = _outcome(_goal(target_date=None))
    assert isinstance(outcome, GoalUnderdetermined), outcome
    assert set(outcome.missing) == {"target_sum", "target_date"}
    assert "target_sum" in outcome.reason


def test_no_declared_variable_is_underdetermined_too() -> None:
    """The degenerate case of the same rule, so the guard covers the whole range rather than
    the one case somebody thought of."""
    outcome = _outcome(_goal(contribution=None, target_date=None))
    assert isinstance(outcome, GoalUnderdetermined), outcome
    assert len(outcome.missing) == 3


# ---------------------------------------------------------------------------
# G2 -- nothing is defaulted, ever
# ---------------------------------------------------------------------------


def test_a_missing_starting_amount_is_refused_naming_it() -> None:
    """FR-012: no assumed opening balance. Zero is a legitimate *declaration* and produces a
    real answer; an absent one is a question about a plan nobody has stated the start of."""
    outcome = _outcome(_goal(target_sum=500_000.0, target_date=None), _inputs(starting=None))
    assert isinstance(outcome, StartingAmountMissing), outcome
    assert outcome.reason.strip()


def test_a_declared_starting_amount_of_zero_is_not_a_missing_one() -> None:
    """The distinction the refusal above exists to draw: starting from nothing is a plan."""
    outcome = _outcome(
        _goal(target_sum=500_000.0, target_date=None),
        _inputs(starting=Money(0.0, UAH, prov.EMPTY)),
    )
    assert not isinstance(outcome, StartingAmountMissing)


def test_a_missing_growth_assumption_is_refused_naming_it() -> None:
    """FR-012: no default rate, ever. Which figure the assumption points at -- the hurdle
    rate, an inflation forecast, nothing at all -- is the owner's declaration, and a rate
    chosen here would make every solved figure an answer about somebody else's plan."""
    outcome = _outcome(_goal(target_sum=500_000.0, target_date=None), _inputs(growth=None))
    assert isinstance(outcome, GrowthAssumptionMissing), outcome
    assert outcome.reason.strip()


def test_a_declared_growth_of_zero_is_not_a_missing_assumption() -> None:
    """Saving without growth is a real plan and hand-computes; it is not an absent rate."""
    outcome = _outcome(
        _goal(target_sum=500_000.0, target_date=None),
        _inputs(growth=GrowthAssumption(annual_rate=0.0, provenance=prov.EMPTY)),
    )
    assert not isinstance(outcome, GrowthAssumptionMissing)


# ---------------------------------------------------------------------------
# G11: not yet modelled, never invalid
# ---------------------------------------------------------------------------


def test_a_non_base_currency_is_refused_as_not_yet_modelled() -> None:
    """FR-016, G11, research.md D7 -- and the wording is the requirement.

    USD is a currency this engine models perfectly well. What is missing is the dated rate
    that would make a dollar target comparable with a hryvnia balance, and §4.7 is explicit
    that under devaluation the two are different goals rather than one goal in two
    denominations. A message calling the currency invalid would send the owner to fix a
    declaration that is correct.
    """
    outcome = _outcome(_goal(target_sum=500_000.0, target_date=None, currency=USD))
    assert isinstance(outcome, CurrencyNotYetModelled), outcome
    assert outcome.declared is USD
    assert outcome.base_currency is UAH
    assert "not yet" in outcome.reason.lower()
    assert "invalid" not in outcome.reason.lower()


def test_the_refusal_does_not_paint_the_multi_currency_case_as_closed() -> None:
    """FR-016's stated deferral: a named seam, not a door.

    Multi-jurisdiction support is planned and ``specs/features.toml`` records
    ``multi-currency-goals`` as owner-requested future work, so the reason must read as
    "not yet" rather than as "never".
    """
    outcome = _outcome(_goal(target_sum=500_000.0, target_date=None, currency=USD))
    assert isinstance(outcome, CurrencyNotYetModelled), outcome
    for closed in ("impossible", "never", "unsupported", "not supported"):
        assert closed not in outcome.reason.lower()


def test_the_goal_record_keeps_its_currency_rather_than_assuming_the_base_one() -> None:
    """The shape half of FR-016: the widening changes a validation rule, not the data."""
    assert _goal(currency=USD).currency is USD


def test_a_starting_amount_in_another_currency_is_a_programmer_error() -> None:
    """Not a typed refusal, and the difference matters.

    A goal denominated in a currency the engine cannot yet convert is a fact about the
    *feature* and the owner can act on it. A starting amount that disagrees with the run's own
    base currency is a fact about the *code* -- somebody assembled the inputs wrongly -- and
    the constitution reserves ``raise`` for exactly that (Principle IV, and ``money``'s
    ``CurrencyMismatchError``).
    """
    with pytest.raises(CurrencyMismatchError, match="base currency"):
        _outcome(
            _goal(target_sum=500_000.0, target_date=None),
            _inputs(starting=Money(100_000.0, USD, prov.EMPTY)),
        )


# ---------------------------------------------------------------------------
# A date that is not in the future
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target_date", [date(2026, 1, 31), date(2025, 12, 1)])
def test_a_target_date_at_or_before_the_evaluation_date_is_refused(target_date: date) -> None:
    """Spec, Edge Cases: never solved "backwards".

    A target date in the past has no schedule to run over, and the same date as the evaluation
    has none either -- the contribution mode would divide by a horizon of zero. Both are
    refused naming the two dates rather than answered for the nearest horizon that works.
    """
    outcome = _outcome(_goal(target_sum=500_000.0, target_date=target_date))
    assert isinstance(outcome, TargetDateNotInFuture), outcome
    assert outcome.target_date == target_date
    assert outcome.as_of == AS_OF
    assert outcome.reason.strip()


def test_the_date_mode_needs_no_target_date_and_is_not_refused_by_that_rule() -> None:
    """The guard applies to a declared date, not to the mode that solves for one."""
    outcome = _outcome(_goal(target_sum=500_000.0, target_date=None))
    assert not isinstance(outcome, TargetDateNotInFuture)


# ---------------------------------------------------------------------------
# The two programmer errors, which are raises rather than typed values
# ---------------------------------------------------------------------------


def test_a_growth_assumption_at_or_below_minus_one_hundred_percent_is_a_raise() -> None:
    """Not a rate this project evaluates, on ``core.results.hurdle``'s reasoning about the
    bottom of its bracket: a total loss is described by saying so, not by quoting a percentage
    and solving a goal against it. The twelfth root of a negative number is not real either,
    and Python would hand back a complex one rather than fail.
    """
    with pytest.raises(ValueError, match="total loss"):
        solve.monthly_rate(GrowthAssumption(annual_rate=-1.0, provenance=prov.EMPTY))
    with pytest.raises(ValueError, match="total loss"):
        solve.monthly_rate(GrowthAssumption(annual_rate=-1.5, provenance=prov.EMPTY))


def test_evaluating_a_balance_without_the_stated_inputs_is_a_raise() -> None:
    """``solve`` refuses a missing starting amount or growth assumption as a typed value; the
    arithmetic underneath refuses it as a programmer error, because reaching it means that
    refusal was bypassed and there is nothing an owner could do about it."""
    with pytest.raises(ValueError, match="FR-012"):
        solve.projected_value(
            _inputs(starting=None), contribution=Money(1.0, UAH, prov.EMPTY), months=1.0
        )
    with pytest.raises(ValueError, match="FR-012"):
        solve.projected_value(
            _inputs(growth=None), contribution=Money(1.0, UAH, prov.EMPTY), months=1.0
        )
