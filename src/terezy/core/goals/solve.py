"""Three closed forms over one contribution schedule, and the verdict when all three are fixed.

``SIMULATOR_SPEC.md`` §4.7, required test **J1**. The owner fixes any two of a monthly
contribution, a target sum and a target date; this module solves the third. All three fixed is
a different question -- whether they can hold together -- and it gets a verdict rather than a
number.

**One model, inverted three ways.** Everything below is a rearrangement of :func:`projected_value`::

    V(t) = S * (1+i)^t  +  C * ((1+i)^t - 1) / i        (i != 0)
    V(t) = S + C * t                                    (i == 0)

where ``S`` is the stated starting amount, ``C`` the monthly contribution, ``t`` a real number
of months and ``i`` the monthly rate. Because the three modes are inversions of one function
rather than three implementations, FR-013's agreement between them is a property of the
algebra rather than something to keep in step by hand.

**No root finder, and no iteration to a tolerance** (research.md D4). FR-014 requires each
solved figure to reproduce hand-computed arithmetic, which is only checkable when the engine
and the hand evaluate the *same* closed form. An iterative solver converges to *a* number
while the hand computation checks a different model, and the project tolerance quietly absorbs
the difference between the two. The three closed forms need no
bound at all, and ``tests/invariants/test_goal_mode_consistency.py`` reads this module's
syntax tree to check that none was invented -- because a private bound inside the engine would
make every round-trip property pass by construction.

**Where a bound *is* needed, it is the imported project one and never a local number.** Two
comparisons decide a verdict rather than compute a figure -- whether a plan met its target, and
whether a required contribution came out at or below zero -- and both compare a *computed*
figure against a *declared* one, where the last bits differ for reasons that have nothing to do
with the money. FR-013 says no mode may define its own tolerance; using the single project one
is what that sentence asks for. Comparisons between two *declared* numbers stay exact: no
arithmetic separates them, so there is nothing for a bound to absorb.

**The conventions travel in the result**, not in this docstring (FR-014's second half). See
:class:`~terezy.core.results.goal.Conventions`.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Final, Literal

from terezy.core.errors import CurrencyMismatchError
from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.conventions import shift_months
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.goal import (
    DETERMINISM_NOTE,
    MONTHLY_END_OF_PERIOD,
    NO_REAL_TERMS,
    Conventions,
    CurrencyNotYetModelled,
    Feasibility,
    Goal,
    GoalInputs,
    GoalOutcome,
    GoalUnderdetermined,
    GrowthAssumption,
    GrowthAssumptionMissing,
    Met,
    Missed,
    NoContributionNeeded,
    SolvedDate,
    StartingAmountMissing,
    TargetDateNotInFuture,
    Unreachable,
)

__all__ = [
    "MONTHLY_END_OF_PERIOD",
    "SolveOutcome",
    "monthly_rate",
    "months_between",
    "projected_value",
    "solve",
]

SolveOutcome = (
    GoalOutcome
    | GoalUnderdetermined
    | StartingAmountMissing
    | GrowthAssumptionMissing
    | CurrencyNotYetModelled
    | NoContributionNeeded
    | TargetDateNotInFuture
    | Unreachable
)
"""Everything :func:`solve` can answer with. Match exhaustively; none of it is an exception.

The contract names six members (``contracts/goal-solver.md``); two more are here and each
closes a case the spec's edge-case list names but the contract's signature did not enumerate:

* ``TargetDateNotInFuture`` -- *"a goal whose target date is in the past ... invalid input,
  reported; never solved backwards"*. It cannot be caught at load time, because "in the past"
  is relative to the evaluation date and a declaration file has none.
* ``Unreachable`` -- FR-019 in the date mode, where there is no other answer to give. It is the
  same record the feasibility verdict uses, in the position where it *is* the answer rather
  than part of one: a result with an empty date field would invite a caller to substitute one,
  and nothing could honestly stand in.
"""

Unanswerable = (
    StartingAmountMissing | GrowthAssumptionMissing | CurrencyNotYetModelled | TargetDateNotInFuture
)
"""The refusals that are about the *inputs* rather than about which variable is unknown.

Named as a union so the guard below can say what it returns without repeating four names, and
so a fifth of its kind is added in one place.
"""

MONTHS_IN_YEAR: Final = 12
"""Named so the twelfth-root conversion reads as the convention it is."""


def monthly_rate(growth: GrowthAssumption) -> float:
    """The monthly rate a declared annual rate compounds at: ``(1 + annual)^(1/12) - 1``.

    The *effective* reading, so twelve of these come to exactly the declared annual rate. See
    ``Conventions.monthly_rate`` for why this convention and not a nominal rate over twelve.

    **A rate at or below -100% is refused with a raise**, on ``core.results.hurdle``'s
    reasoning about the bottom of its bracket: that is not a rate this project reports, it is a
    total loss, and a total loss is described by saying so rather than by quoting a percentage.
    The raise rather than a typed value is deliberate -- a growth assumption is an input the
    caller assembled, not a fact about the owner's money, so a nonsensical one is a programmer
    error. It is also not merely a modelling opinion: the twelfth root of a negative number is
    not a real number at all, and Python would hand back a complex one.
    """
    if growth.annual_rate <= -1.0:
        raise ValueError(
            f"a growth assumption of {growth.annual_rate!r} is not a rate this engine will "
            "evaluate: at -100% a year nothing is left to grow, and below it the twelfth root "
            "is not a real number. A total loss is described by saying so, not by quoting a "
            "rate and solving a goal against it."
        )
    monthly: float = (1.0 + growth.annual_rate) ** (1.0 / MONTHS_IN_YEAR)
    return monthly - 1.0


def months_between(start: date, end: date) -> float:
    """How many months apart two dates are, as a real number (``Conventions.month_count``).

    Whole monthly anniversaries of ``start`` -- with the day clamped to the length of the
    target month, the rule ``conventions.shift_months`` applies to a bond's coupon dates --
    plus the elapsed fraction of the month in progress, in actual days over that month's own
    length.

    The anniversary count starts from the plain calendar difference and steps **back** while
    that anniversary is still after ``end``, which is exact rather than a search: the calendar
    difference overshoots only when the day of ``end`` falls before the anchored day, and then
    by exactly one. There is deliberately no loop in the other direction -- the anniversary at
    ``count + 1`` is in the month after ``end``'s own, so it can never fall on or before it, and
    a guard that cannot fire is worse than no guard because it reads as protection.

    Negative spans are computed the same way and come back negative. Nothing in this module
    calls it with one -- ``solve`` refuses a target date at or before the evaluation date
    first -- but a month count that silently changed meaning for a reversed pair would be a
    worse thing to leave lying about than one that simply counts backwards.
    """
    anniversaries = (end.year - start.year) * MONTHS_IN_YEAR + (end.month - start.month)
    while shift_months(start, anniversaries) > end:
        anniversaries -= 1
    reached = shift_months(start, anniversaries)
    following = shift_months(start, anniversaries + 1)
    return anniversaries + (end - reached).days / (following - reached).days


def projected_value(inputs: GoalInputs, *, contribution: Money, months: float) -> Money:
    """The balance after ``months`` of paying ``contribution`` at each month end.

    The one function the three modes are three views of, and the one a hand computation
    checks. It is public for that reason: the exact solution of the date mode is *defined* as
    the point at which this returns the target, and a property that could not evaluate it
    would have to trust the solver's own claim about its own inverse.

    **The growth assumption's provenance is merged into both terms, including when the rate is
    zero.** A zero rate is still a declaration the figure rests on, and dropping its marks
    there would mean a goal evaluated against an unverified "no growth" assumption came back
    unmarked -- a transform losing a mark, which the constitution puts at top severity.

    Raises on absent inputs. Reaching here with a missing starting amount or growth assumption
    means :func:`solve`'s refusals were bypassed, which is a programmer error rather than a
    fact about the money.
    """
    starting, growth = _stated(inputs)
    rate = monthly_rate(growth)
    if rate == 0.0:
        return money.add(starting, money.scale_sourced(contribution, months, growth.provenance))
    grown_by = _growth_over(months, rate)
    return money.add(
        money.scale_sourced(starting, 1.0 + grown_by, growth.provenance),
        money.scale_sourced(contribution, grown_by / rate, growth.provenance),
    )


def _growth_over(months: float, rate: float) -> float:
    """``(1+i)^t - 1``, computed as ``expm1(t * log1p(i))`` rather than by subtracting one.

    Algebraically the same number and arithmetically a different one. The annuity term divides
    this by the rate, so at a small rate or a short horizon the subtraction ``(1+i)**t - 1``
    throws away most of the significant digits of a quantity the answer then multiplies back up
    by ``1/i`` -- the error in the sum scales with ``contribution / rate`` instead of with the
    sum. ``expm1`` and ``log1p`` are built for exactly that shape.

    It is not a tolerance and it hides no disagreement: the same value, computed the way it
    should have been computed in the first place. What it buys is a round trip that closes on a
    five-thousand-hryvnia goal, which is a goal the declaration file accepts.
    """
    return math.expm1(months * math.log1p(rate))


def _stated(inputs: GoalInputs) -> tuple[Money, GrowthAssumption]:
    """The two inputs that are never defaulted, or a raise naming the one that is absent."""
    if inputs.starting_amount is None or inputs.growth is None:
        raise ValueError(
            "a goal cannot be evaluated without both a starting amount and a growth "
            "assumption, and neither is ever substituted (FR-012). solve() refuses this as a "
            "typed value; reaching the arithmetic with one missing means that refusal was "
            "bypassed."
        )
    return inputs.starting_amount, inputs.growth


def solve(
    goal: Goal,
    *,
    inputs: GoalInputs,
    conventions: Conventions,
) -> SolveOutcome:
    """Solve the variable the owner left out, or report why the question cannot be answered.

    The order of the checks is the order in which a question stops making sense: an input that
    was never stated, then a currency this feature cannot evaluate, then a target date that has
    already passed, then how many of the three variables there are to work with. Each is a
    typed value carrying its reason; none of them is an exception, because every one of them is
    a fact about the declaration rather than about the code.
    """
    refusal = _unanswerable(goal, inputs)
    if refusal is not None:
        return refusal

    missing = tuple(
        name
        for name, declared in (
            ("monthly_contribution", goal.monthly_contribution),
            ("target_sum", goal.target_sum),
            ("target_date", goal.target_date),
        )
        if declared is None
    )
    match missing:
        case ():
            return _feasibility(goal, inputs=inputs, conventions=conventions)
        case ("monthly_contribution",):
            return _solve_contribution(goal, inputs=inputs, conventions=conventions)
        case ("target_sum",):
            return _solve_sum(goal, inputs=inputs, conventions=conventions)
        case ("target_date",):
            return _solve_date(goal, inputs=inputs, conventions=conventions)
        case _:
            return GoalUnderdetermined(
                goal_id=goal.id,
                missing=missing,
                reason=(
                    f"the goal {goal.id!r} declares fewer than two of a monthly contribution, "
                    f"a target sum and a target date: nothing is stated for {list(missing)}. "
                    "Any two fix the third and fewer than two fix nothing -- filling one in "
                    "would be the tool inventing the plan rather than solving it (FR-011)."
                ),
            )


def _unanswerable(goal: Goal, inputs: GoalInputs) -> Unanswerable | None:
    """Why the question cannot be asked at all, or ``None`` when it can.

    Separate from the mode dispatch because these are questions about the *inputs* rather than
    about which variable is unknown: every one of them holds whichever two of the three the
    owner declared, and none of them depends on the mode. ``None`` is not a degraded outcome --
    it is "nothing is wrong" -- so it is a plain absence rather than a member of the union.
    """
    if inputs.starting_amount is None:
        return StartingAmountMissing(
            goal_id=goal.id,
            reason=(
                f"the goal {goal.id!r} was evaluated without a starting amount. None is "
                "assumed: a zero opening balance is a legitimate declaration and produces a "
                "real answer, while an absent one is a question about a plan whose starting "
                "point nobody has stated (FR-012)."
            ),
        )
    if inputs.growth is None:
        return GrowthAssumptionMissing(
            goal_id=goal.id,
            reason=(
                f"the goal {goal.id!r} was evaluated without a growth assumption. No rate is "
                "defaulted: which figure the assumption points at -- the hurdle rate, an "
                "inflation forecast, nothing at all -- is the owner's declaration, and a rate "
                "chosen here would make every solved figure an answer about somebody else's "
                "plan (FR-012)."
            ),
        )
    if goal.currency is not inputs.base_currency:
        return CurrencyNotYetModelled(
            goal_id=goal.id,
            declared=goal.currency,
            base_currency=inputs.base_currency,
            reason=(
                f"the goal {goal.id!r} is denominated in {goal.currency.value} and this run "
                f"evaluates in {inputs.base_currency.value}. That is **not yet modelled**: "
                f"restating a {goal.currency.value} target against a "
                f"{inputs.base_currency.value} balance needs a dated exchange rate this "
                "feature does not carry, and a target in one currency is a different goal "
                "from the same number in another once the pair moves. It is refused rather "
                "than converted at a rate nobody declared."
            ),
        )
    if inputs.starting_amount.currency is not inputs.base_currency:
        raise CurrencyMismatchError(
            f"the starting amount is in {inputs.starting_amount.currency.value} and the run's "
            f"base currency is {inputs.base_currency.value}. These are inputs assembled by the "
            "caller rather than a fact about the owner's money, so a disagreement between them "
            "is a bug in the code and not an outcome to report."
        )
    if goal.target_date is not None and goal.target_date <= inputs.as_of:
        return TargetDateNotInFuture(
            goal_id=goal.id,
            as_of=inputs.as_of,
            target_date=goal.target_date,
            reason=(
                f"the goal {goal.id!r} targets {goal.target_date.isoformat()}, which is not "
                f"after the evaluation date {inputs.as_of.isoformat()}. There is no schedule "
                "to run over: a horizon of zero months holds no contributions and no growth, "
                "and one in the past would be solved backwards. The nearest horizon that works "
                "is not the question that was asked."
            ),
        )
    return None


def _solve_sum(goal: Goal, *, inputs: GoalInputs, conventions: Conventions) -> GoalOutcome:
    """What the plan reaches by the declared date (US3 scenario 1)."""
    contribution = _declared(goal.monthly_contribution)
    target_date = _declared(goal.target_date)
    months = months_between(inputs.as_of, target_date)
    reached = projected_value(inputs, contribution=contribution, months=months)
    return _outcome(
        goal,
        inputs=inputs,
        conventions=conventions,
        solved_for="sum",
        contribution=contribution,
        target_sum=reached,
        target_date=target_date,
        exact_date=None,
        # The margin of a solved sum is zero by construction -- the target *is* what the plan
        # reaches. It is built by subtracting the figure from itself rather than with
        # ``money.zero``, which would carry empty provenance and quietly hand back an unmarked
        # figure on a goal solved against a marked assumption (SC-010).
        feasibility=Met(margin=money.sub(reached, reached)),
    )


def _solve_contribution(
    goal: Goal, *, inputs: GoalInputs, conventions: Conventions
) -> GoalOutcome | NoContributionNeeded:
    """What must go in each month to reach the declared sum by the declared date.

    The inverse of :func:`projected_value` in ``C``::

        C = (target - S * (1+i)^t) * i / ((1+i)^t - 1)        (i != 0)
        C = (target - S) / t                                  (i == 0)

    A result at or below zero means the starting amount alone already gets there, and FR-020
    requires that be said rather than presented as a negative instruction to withdraw.
    """
    starting, growth = _stated(inputs)
    target_sum = _declared(goal.target_sum)
    target_date = _declared(goal.target_date)
    months = months_between(inputs.as_of, target_date)
    rate = monthly_rate(growth)

    if rate == 0.0:
        grown = starting
        required = money.scale_sourced(
            money.sub(target_sum, grown), 1.0 / months, growth.provenance
        )
    else:
        grown_by = _growth_over(months, rate)
        grown = money.scale_sourced(starting, 1.0 + grown_by, growth.provenance)
        required = money.scale_sourced(
            money.sub(target_sum, grown), rate / grown_by, growth.provenance
        )

    # "At or below zero" (FR-020) under float64: a required contribution that comes out at a
    # billionth of a hryvnia is zero, and reporting it as an instruction to pay it would be the
    # arithmetic leaking into the advice. The bound is the imported project one.
    if required.amount <= 0.0 or is_close(required.amount, 0.0):
        return NoContributionNeeded(
            goal_id=goal.id,
            margin=money.sub(grown, target_sum),
            reason=(
                f"the goal {goal.id!r} is already met on {target_date.isoformat()} without "
                f"paying anything in: {starting.amount!r} {target_sum.currency.value} grows to "
                f"{grown.amount!r} against a target of {target_sum.amount!r}. The arithmetic "
                f"gives {required.amount!r} a month, and a negative contribution is an "
                "instruction to withdraw rather than an answer to the question that was asked "
                "(FR-020)."
            ),
        )
    return _outcome(
        goal,
        inputs=inputs,
        conventions=conventions,
        solved_for="contribution",
        contribution=required,
        target_sum=target_sum,
        target_date=target_date,
        exact_date=None,
        feasibility=Met(
            margin=money.sub(
                projected_value(inputs, contribution=required, months=months), target_sum
            )
        ),
    )


def _solve_date(
    goal: Goal, *, inputs: GoalInputs, conventions: Conventions
) -> GoalOutcome | NoContributionNeeded | Unreachable:
    """When the declared contribution reaches the declared sum -- twice over (FR-015).

    **A target already met at the evaluation date has no date to report**, and saying so is
    more honest than any of the alternatives. Under a shrinking balance the crossing is the
    moment the money falls *to* the target, which is not what "when do I get there" asks; and
    under a growing one the crossing is in the past. Both are answered the same way: the target
    is met now, by this margin, and no contribution is needed to get there.
    """
    starting, growth = _stated(inputs)
    contribution = _declared(goal.monthly_contribution)
    target_sum = _declared(goal.target_sum)

    # An exact comparison, deliberately, where the two above are toleranced: both of these
    # numbers are *declared* and no arithmetic separates them, so there is no accumulated error
    # for a bound to absorb -- and a bound here would make the mode disagree with
    # ``projected_value`` about which side of the target the plan starts on.
    if starting.amount >= target_sum.amount:
        return NoContributionNeeded(
            goal_id=goal.id,
            margin=money.sub(starting, target_sum),
            reason=(
                f"the goal {goal.id!r} is already met on {inputs.as_of.isoformat()}: the "
                f"starting amount is {starting.amount!r} against a target of "
                f"{target_sum.amount!r}. There is no date on which it is reached because it "
                "has not been unmet since the evaluation began, and no contribution is needed "
                "to get there."
            ),
        )

    crossing = _crossing(
        starting=starting.amount,
        contribution=contribution.amount,
        target=target_sum.amount,
        rate=monthly_rate(growth),
    )
    if crossing is None or crossing <= 0.0:
        return Unreachable(
            reason=_unreachable_reason(
                goal_id=goal.id,
                starting=starting,
                contribution=contribution,
                target=target_sum,
                growth=growth,
            )
        )
    reached_on = _first_month_end_at_or_after(inputs.as_of, crossing)
    if reached_on is None:
        return Unreachable(
            reason=(
                f"the goal {goal.id!r} is reached only after {crossing!r} months, which falls "
                "beyond the last date this calendar can express. The figure is stated here "
                "rather than rounded into a date, and no nearer date is reported in its place: "
                "a horizon of that length is a statement about the plan, not a schedule."
            )
        )
    return _outcome(
        goal,
        inputs=inputs,
        conventions=conventions,
        solved_for="date",
        contribution=contribution,
        target_sum=target_sum,
        target_date=reached_on,
        exact_date=SolvedDate(exact=crossing, first_reached_on=reached_on),
        feasibility=Met(
            margin=money.sub(
                projected_value(inputs, contribution=contribution, months=crossing), target_sum
            )
        ),
    )


def _feasibility(goal: Goal, *, inputs: GoalInputs, conventions: Conventions) -> GoalOutcome:
    """All three declared: met with the margin, missed with both faces, or unreachable.

    Nothing declared is adjusted. The three variables come back exactly as they were stated and
    the verdict sits beside them, which is the difference between reporting a shortfall and
    quietly answering an easier question (FR-018).
    """
    starting, growth = _stated(inputs)
    contribution = _declared(goal.monthly_contribution)
    target_sum = _declared(goal.target_sum)
    target_date = _declared(goal.target_date)
    months = months_between(inputs.as_of, target_date)
    reached = projected_value(inputs, contribution=contribution, months=months)

    verdict: Feasibility
    # The single project tolerance governs this boundary, and the spec's edge-case list says so
    # in as many words: a target met exactly is *met with a zero margin*, not missed by the last
    # bits of a float. The comparison is between a computed balance and a declared target.
    if reached.amount >= target_sum.amount or is_close(reached.amount, target_sum.amount):
        verdict = Met(margin=money.sub(reached, target_sum))
    else:
        verdict = _missed_or_unreachable(
            goal,
            inputs=inputs,
            starting=starting,
            growth=growth,
            contribution=contribution,
            target_sum=target_sum,
            target_date=target_date,
            reached=reached,
        )
    return _outcome(
        goal,
        inputs=inputs,
        conventions=conventions,
        solved_for="feasibility",
        contribution=contribution,
        target_sum=target_sum,
        target_date=target_date,
        exact_date=None,
        feasibility=verdict,
    )


def _missed_or_unreachable(
    goal: Goal,
    *,
    inputs: GoalInputs,
    starting: Money,
    growth: GrowthAssumption,
    contribution: Money,
    target_sum: Money,
    target_date: date,
    reached: Money,
) -> Missed | Unreachable:
    """The target is short on its date. Say by how much, and when it would actually arrive.

    Both faces of the binding shortfall (FR-018), unless there is no second face: a plan that
    never gets there is *unreachable* rather than missed by a date nobody can name, and
    reporting a capped horizon in its place is what FR-019 forbids.

    **A crossing that is not after the target date is not an arrival.** Under a shrinking
    balance the crossing is the moment the money falls *through* the target on its way down,
    which is a real date and the wrong answer twice over: it is in the past relative to the
    target, and it describes losing the target rather than reaching it. The guard is the same
    one :func:`_solve_date` applies at the evaluation date, moved to the date the owner asked
    about -- ``Missed.reached_on`` promises a date *later* than the target date, and a promise
    the record makes in its own docstring is one this function has to keep.
    """
    shortfall = money.sub(target_sum, reached)
    crossing = _crossing(
        starting=starting.amount,
        contribution=contribution.amount,
        target=target_sum.amount,
        rate=monthly_rate(growth),
    )
    horizon = months_between(inputs.as_of, target_date)
    if crossing is not None and crossing > horizon:
        reached_on = _first_month_end_at_or_after(inputs.as_of, crossing)
        if reached_on is not None:
            return Missed(shortfall_at_target=shortfall, reached_on=reached_on)
    return Unreachable(
        reason=(
            f"the goal {goal.id!r} is short by {shortfall.amount!r} "
            f"{shortfall.currency.value} on {target_date.isoformat()}, and there is no later "
            "date on which it arrives. "
            + _never_arrives_reason(
                goal_id=goal.id,
                starting=starting,
                contribution=contribution,
                target=target_sum,
                growth=growth,
                target_date=target_date,
                falling_through=crossing,
            )
        )
    )


def _crossing(*, starting: float, contribution: float, target: float, rate: float) -> float | None:
    """The real-valued month at which the balance equals the target, or ``None`` if never.

    Rearranged from :func:`projected_value` by writing the balance as a single exponential
    around the level ``-C/i`` -- the balance a fixed contribution settles at under a negative
    rate, and the constant that turns an annuity into a plain power::

        V(t) = (S + C/i) * (1+i)^t  -  C/i
        t    = ln((target + C/i) / (S + C/i)) / ln(1+i)
             = log1p((target - S) * i / (S*i + C)) / log1p(i)

    The second line is the one computed, and it is the first with the division by ``i`` cleared
    and the ratio written as one plus the *change* it represents. Both are the same number in
    exact arithmetic; in float64 the first takes the logarithm of a ratio that sits a hair above
    one for any short horizon, which is where its significant digits go. See
    :func:`_growth_over` -- this is the same conditioning problem in the inverse direction.

    ``None`` covers the two shapes of "never", and neither is a search that gave up:

    * the balance does not move at all -- no contribution and no growth, or a contribution
      exactly offset by the loss on the balance it sits on;
    * the target is on the far side of the level the balance converges to, so reaching it would
      take a growth factor of zero or less and the logarithm is undefined. Under a negative
      assumption that level is a genuine ceiling, and a target above it is not reached however
      long anyone waits.
    """
    if _never_moves(starting=starting, contribution=contribution, rate=rate):
        return None
    if rate == 0.0:
        return (target - starting) / contribution
    growth_needed = (target - starting) * rate / (starting * rate + contribution)
    if growth_needed <= -1.0:
        return None
    return math.log1p(growth_needed) / math.log1p(rate)


def _never_moves(*, starting: float, contribution: float, rate: float) -> bool:
    """Whether the balance is the same on every date, so there is no crossing to find.

    Two ways for that to happen and they are the same statement: nothing goes in and nothing
    grows on what is there (``C = 0`` with either no rate or no balance), or -- under a negative
    assumption -- the contribution exactly offsets the loss on the balance it sits on, which is
    ``S = -C/i``.

    Shared with :func:`_unreachable_reason` rather than re-derived there, so the message a
    reader is given cannot claim the balance never changes about a balance that shrinks.
    """
    if rate == 0.0:
        return contribution == 0.0
    return starting * rate + contribution == 0.0


def _first_month_end_at_or_after(as_of: date, crossing: float) -> date | None:
    """The first contribution date on or after the crossing, or ``None`` past the calendar.

    Taking the ceiling is exact rather than a rounding -- a crossing already *on* a month end
    excepted, where the tolerance decides whether the last bits of a float or the schedule is
    telling the truth. The distinction is FR-015's:
    whenever a crossing is reported at all the balance is strictly increasing through it, so
    the first month end past the crossing *is* the first schedule date on which the target is
    reached. The crossing itself is kept beside it, in months, because they are different
    facts.

    **The snap cannot collapse a ``Missed`` arrival onto the target date**, which is the one
    thing it could break: a crossing a fraction of a nanomonth past an integer horizon would
    round back to that horizon and report an arrival on the date the goal was missed on. It is
    unreachable rather than merely unlikely. A gap that small in *time* is a gap far inside the
    same tolerance in *money* -- it would take a monthly rate above roughly 640% for a
    nanomonth to move the balance by more than the tolerance allows -- so a plan that close to
    its target on the target date is met, and the ``Met`` branch of the feasibility verdict has
    already returned by the time this function is called. The bound is stated here rather than
    guarded against, because a guard for a case that cannot arise reads as protection and is
    not.

    ``None`` is returned where the date would fall outside the representable calendar. The
    caller reports the month count instead, which is the honest answer: rounding it back to
    the last expressible date would be the nearest answer FR-019 forbids, and crashing would
    make an arithmetic limit look like a failure of the plan.
    """
    whole = round(crossing)
    # A crossing that lands *on* a contribution date is that date, and float64 will not always
    # say so exactly: the twelve-month example solves to 12.000000000000004, and a bare ceiling
    # turns "you get there in a year" into "you get there in thirteen months". The comparison
    # is between a computed crossing and a schedule position, so the single project tolerance
    # governs it -- the same rule the met-or-missed boundary follows, and never a bound of this
    # module's own.
    months = whole if is_close(crossing, float(whole)) else math.ceil(crossing)
    representable = (date.max.year - as_of.year) * MONTHS_IN_YEAR + (date.max.month - as_of.month)
    if months > representable:
        return None
    return shift_months(as_of, months)


def _never_arrives_reason(
    *,
    goal_id: str,
    starting: Money,
    contribution: Money,
    target: Money,
    growth: GrowthAssumption,
    target_date: date,
    falling_through: float | None,
) -> str:
    """Why a fully declared goal has no arrival date, when it is short on the one it asked for.

    The first branch is the case a downward crossing would otherwise be reported as an arrival:
    a crossing later than the evaluation date but no later than the target date can only be the
    balance passing *below* the target, because a rising balance that crossed before the target
    date would not be short on it. The message says so rather than naming a date, which is the
    same distinction :func:`_solve_date` draws at the evaluation date.
    """
    if falling_through is not None and falling_through > 0.0:
        return (
            f"the balance starts at {starting.amount!r} {target.currency.value}, which is above "
            f"the target, and falls through it about {falling_through!r} months after the "
            f"evaluation date -- before {target_date.isoformat()}, not after it. That is losing "
            "the target rather than reaching it, so it is not reported as the date the goal "
            "arrives: under this assumption there is no such date."
        )
    return _unreachable_reason(
        goal_id=goal_id,
        starting=starting,
        contribution=contribution,
        target=target,
        growth=growth,
    )


def _unreachable_reason(
    *,
    goal_id: str,
    starting: Money,
    contribution: Money,
    target: Money,
    growth: GrowthAssumption,
) -> str:
    """Why a target is never reached, naming which of the four shapes it is.

    Each branch tests the expression that actually produced the failure rather than a
    restatement of it, because a restatement is how a message comes to say something true of the
    case somebody had in mind and false of the case in front of the reader.

    Reaching here at all implies a **negative** assumption and a balance that moves: a balance
    moving at a rate of zero or more passes any target above it eventually, so "not constant"
    and "never reached" together leave only decay. Within decay there are four shapes, and the
    sign of ``S*i + C`` -- the same quantity :func:`_never_moves` tests against zero -- tells
    them apart, so the four cases partition rather than overlap:

    * **The balance never moves** (``S*i + C == 0``): the contribution exactly offsets the loss
      on the balance it sits on, or nothing goes in and there is nothing to lose it from.
    * **Nothing goes in** (``C == 0``, so ``S*i < 0``): the balance decays towards nothing, and
      the level it converges to is zero rather than a ceiling worth naming.
    * **The balance rises towards a ceiling below the target** (``S*i + C > 0``): what goes in
      outweighs the loss for now, the two meet at ``-C/i``, and the target is above that.
    * **The balance falls away from the target** (``S*i + C < 0`` with a target above where it
      started): the loss outweighs what goes in, so the balance recedes from a target it never
      approached. The ceiling exists arithmetically and describing the plan as *converging on
      it* would be a true number inside a false sentence -- 100 UAH a month is not "roughly
      offsetting" a loss of 5 600, and the target is further away every month, not nearer.

    The last two shared one sentence until the review of 2026-08-23 found the second reading
    it. There is no fifth branch and no fallback: a fallback could only describe a case that
    cannot occur, which is the kind of guard that reads as protection and is not.
    """
    rate = monthly_rate(growth)
    if _never_moves(starting=starting.amount, contribution=contribution.amount, rate=rate):
        return (
            f"the goal {goal_id!r} targets {target.amount!r} {target.currency.value} and the "
            f"balance never moves off {starting.amount!r}: a contribution of "
            f"{contribution.amount!r} against a growth assumption of {growth.annual_rate!r} "
            "changes nothing from one month to the next. So there is no date on which the "
            "target is reached -- not a distant one, and not a capped horizon standing in for "
            "one."
        )
    if contribution.amount == 0.0:
        return (
            f"the goal {goal_id!r} targets {target.amount!r} {target.currency.value}, and "
            f"nothing goes in: at a growth assumption of {growth.annual_rate!r} the balance "
            f"decays from {starting.amount!r} towards nothing rather than rising towards the "
            "target. No date is reported because there is none -- an arbitrarily distant one "
            "would be a nearest answer to a question that has no answer."
        )
    ceiling = -contribution.amount / rate
    nowhere_to_go = (
        " No date is reported because there is none -- an arbitrarily distant one would be a "
        "nearest answer to a question that has no answer."
    )
    if starting.amount * rate + contribution.amount > 0.0:
        return (
            f"the goal {goal_id!r} targets {target.amount!r} {target.currency.value}, which the "
            f"stated plan converges towards but never passes. At a growth assumption of "
            f"{growth.annual_rate!r} the balance rises from {starting.amount!r} towards "
            f"{ceiling!r} {target.currency.value} -- the level at which the monthly loss eats "
            f"exactly the {contribution.amount!r} that goes in -- and the target is above it."
            + nowhere_to_go
        )
    return (
        f"the goal {goal_id!r} targets {target.amount!r} {target.currency.value}, which the "
        f"stated plan moves away from rather than towards. At a growth assumption of "
        f"{growth.annual_rate!r} the monthly loss on {starting.amount!r} outweighs the "
        f"{contribution.amount!r} that goes in, so the balance falls towards {ceiling!r} "
        f"{target.currency.value} while the target sits above where it started. Waiting brings "
        "it no closer." + nowhere_to_go
    )


def _declared[T](value: T | None) -> T:
    """A variable the mode has already established is present.

    Narrowing only. ``solve`` decides which mode to run from which fields are ``None``, so a
    ``None`` reaching one of the mode functions means that dispatch is wrong -- a programmer
    error, and one no caller could act on.
    """
    if value is None:  # pragma: no cover -- the mode dispatch in solve() guarantees otherwise
        raise ValueError(
            "a goal mode was run against a variable that was not declared; solve()'s dispatch "
            "and the mode function disagree about which of the three is the question."
        )
    return value


def _outcome(
    goal: Goal,
    *,
    inputs: GoalInputs,
    conventions: Conventions,
    solved_for: Literal["contribution", "sum", "date", "feasibility"],
    contribution: Money,
    target_sum: Money,
    target_date: date,
    exact_date: SolvedDate | None,
    feasibility: Feasibility,
) -> GoalOutcome:
    """Assemble the result, with every mark that reached any figure unioned onto it.

    The union is taken here rather than at each call site so that a mode cannot report a
    figure whose provenance the result does not admit to. It covers the growth assumption, the
    starting amount, and both of the money figures -- whichever of them was declared and
    whichever was solved.
    """
    starting, growth = _stated(inputs)
    return GoalOutcome(
        goal_id=goal.id,
        owner_id=goal.owner_id,
        solved_for=solved_for,
        monthly_contribution=contribution,
        target_sum=target_sum,
        target_date=target_date,
        exact_date=exact_date,
        conventions=conventions,
        feasibility=feasibility,
        terms="nominal",
        real=NO_REAL_TERMS,
        determinism_note=DETERMINISM_NOTE,
        provenance=prov.merge_all(
            (
                growth.provenance,
                starting.provenance,
                contribution.provenance,
                target_sum.provenance,
            )
        ),
    )
