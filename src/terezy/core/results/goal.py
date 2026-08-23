"""What the owner is aiming at, and what the solver answers about it.

``SIMULATOR_SPEC.md`` §4.7, required test **J1**. A goal is any two of three variables --
a monthly contribution, a target sum, a target date -- and the tool solves the third. All
three declared is not an over-declaration: it is a different question, the feasibility one
(FR-018).

**Nothing here is a rate the tool chose.** A goal is evaluated against an explicitly stated
starting amount and an explicitly stated growth assumption, both carrying provenance, and
neither is declared on the goal itself. Pointing the assumption at the hurdle rate, or at
anything else, is the owner's declaration -- so a missing one is a typed refusal naming it
rather than a default (FR-012). There is no field either could hide in.

This module holds the **records**; ``core.goals.solve`` holds the arithmetic that fills them.
The split follows ``core.results.hurdle`` and ``core.results.rates``: what a result *is* can
be read without reading how it was computed, and the shape is what a later delivery surface
depends on.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.rates import RealTermsUnavailable


@dataclass(frozen=True, slots=True)
class Goal:
    """One declared target: any two of contribution, sum and date -- or all three.

    Per-owner declared data (Principle VII, FR-022), beside the seed lots and on the private
    side of the same boundary.
    """

    owner_id: str
    """Whose goal this is. On every record, not only on the file that declared them."""

    id: str
    """Unique within the declaration. A duplicate is refused at load: two goals with one id
    cannot be told apart, so neither could be reported against."""

    currency: Currency
    """The denomination of the target, **stated rather than assumed** (FR-016).

    It must be the base currency in this feature, and a goal in any other is refused as *not
    yet modelled* -- naming the missing FX modelling, never the currency as invalid. §4.7's
    point stands that a dollar target and a hryvnia target are different goals under
    devaluation, so the field exists rather than hryvnia being implicit: the widening changes
    a validation rule, not the shape of the data. ``specs/features.toml`` records
    ``multi-currency-goals`` as owner-requested future work.
    """

    monthly_contribution: Money | None
    """What goes in each month, or ``None`` when this is the variable to solve for.

    ``None`` means **the owner declared nothing here**, which is why the field is nullable at
    all. It is never a zero standing in for an absent declaration: zero is itself a legitimate
    contribution -- a goal reached out of growth alone -- and conflating the two would make
    the solver unable to tell what it was asked.
    """

    target_sum: Money | None
    """How much is wanted, or ``None`` when that is the question."""

    target_date: date | None
    """By when, or ``None`` when that is the question."""


@dataclass(frozen=True, slots=True)
class GrowthAssumption:
    """The rate a goal is evaluated against, and where it came from.

    **Never defaulted** (FR-012). The tool does not choose this: pointing it at the hurdle
    rate, at an inflation forecast, or at nothing at all is the owner's declaration, and a
    rate chosen here would make every solved figure an answer about somebody else's plan.

    It is an *assumption* rather than an observation even when it is copied from a computed
    figure -- what a portfolio will return is not a thing anyone has measured -- so the marks
    it carries reach every figure solved against it.
    """

    annual_rate: float
    """A fraction per annum: ``0.155``, never ``15.5``. Percent lives only in data files.

    Under the convention this feature applies (``Conventions.monthly_rate``) it is the
    *effective* annual rate: twelve months of compounding come to exactly this, which is the
    same reading ``core.results.hurdle`` discounts with.
    """

    provenance: Provenance
    """Whatever the rate rests on. Marks here reach every solved figure (SC-010)."""


@dataclass(frozen=True, slots=True)
class GoalInputs:
    """The frame a goal is evaluated in: from when, in what currency, from what, at what rate.

    Two of the four are ``| None`` on purpose. FR-012 requires a *typed refusal naming the
    missing input* when either the starting amount or the growth assumption is absent, and a
    guard that cannot fire is worse than no guard: if the record could not express the
    absence, the refusal would be unreachable code that reads as protection.
    """

    as_of: date
    """The date the starting amount is measured at and the contribution schedule begins from.

    An argument because there is no clock in the core, and the reason is not ceremony: the
    solved date of a goal must be the same figure a year from now as it is today, or nothing
    computed from it is reproducible.
    """

    base_currency: Currency
    """The run's base currency, stated rather than read off :attr:`starting_amount`.

    Principle VI gives currency three distinct roles and calls conflating any two a defect.
    The base currency of a run and the denomination of an amount are two of them: they
    coincide in every correct run, and inferring one from the other would mean a goal in the
    wrong currency was checked against an amount that was also in the wrong currency, and
    both would pass.
    """

    starting_amount: Money | None
    """What the goal starts from, or ``None`` if the owner has not stated it.

    **Zero is a declaration and ``None`` is not** -- starting from nothing is a plan, while an
    absent opening balance is a question about a plan whose start nobody stated. No opening
    balance is ever assumed (FR-012).
    """

    growth: GrowthAssumption | None
    """The rate, or ``None`` if the owner has not stated one. No rate is ever defaulted."""


@dataclass(frozen=True, slots=True)
class Conventions:
    """The evaluation model, stated on the record rather than left implicit in the code.

    FR-014's second half, and it is load-bearing rather than descriptive: *"reproduces
    hand-computed arithmetic"* is only checkable when the hand and the engine are evaluating
    the same model, and four of the choices below change the answer materially.

    Every field is a ``Literal`` with exactly one permitted value, because exactly one model is
    implemented. That is deliberate: a second convention becomes a *type* change, visible in
    every signature it touches, rather than a new string that silently starts appearing in
    results a reader assumed were computed the old way.
    """

    contribution_timing: Literal["end_of_period"]
    """When in the month a contribution lands.

    At the end, so the first payment earns growth for one month less than the last. Paying at
    the start instead multiplies the whole annuity term by ``(1 + i)`` -- on a twelve-month,
    ten-thousand-a-month plan at one percent, a difference of 1 268 UAH that no reader could
    attribute without being told which convention produced it.
    """

    compounding: Literal["monthly"]
    """How growth accrues between contributions: once per month, on the whole balance."""

    monthly_rate: Literal["twelfth_root_of_annual"]
    """How the declared annual rate becomes a monthly one: ``i = (1 + annual) ** (1/12) - 1``.

    The *effective* reading, so twelve months of growth come to exactly the declared annual
    rate. The alternative -- a nominal annual rate divided by twelve -- gives 12.68% a year
    for a declared 12%, and the gap grows with the rate. This convention is the one
    ``core.results.hurdle`` already discounts with (``(1 + r) ** years`` at a fractional
    exponent), and a goal that used the other would disagree with the hurdle rate the owner is
    most likely to point it at.
    """

    month_count: Literal["anniversary_actual_days"]
    """How a span of dates becomes a number of months.

    Whole monthly anniversaries of :attr:`GoalInputs.as_of` -- clamped to the length of the
    target month, the same rule a bond's coupon dates follow -- plus the elapsed fraction of
    the month in progress, measured in actual days over that month's own length. A fixed
    30.44-day month would be simpler and would make a target date fall on a fractional month
    it does not fall on.
    """


MONTHLY_END_OF_PERIOD: Final[Conventions] = Conventions(
    contribution_timing="end_of_period",
    compounding="monthly",
    monthly_rate="twelfth_root_of_annual",
    month_count="anniversary_actual_days",
)
"""The one model this feature implements, as a value callers pass in.

A module constant rather than a default argument, on the precedent this project sets against
defaults everywhere else: the conventions are part of the question, so a caller states them.
It is also what makes the second convention set, when it arrives, a visible choice at every
call site rather than a change of behaviour under callers who never asked for it.
"""

NO_REAL_TERMS: Final[RealTermsUnavailable] = RealTermsUnavailable(
    reason=(
        "inflation is not modelled in this feature, so the target and every figure solved "
        "against it are nominal and say so. No real figure is computed and none is assumed: a "
        "real target derived from a guessed inflation rate would be a fabricated number "
        "wearing the same label as a measured one. The slot is filled by the CPI feature; "
        "whether a real figure then becomes the headline is a separate decision the owner has "
        "not taken."
    )
)
"""The occupant of the real-terms slot for every goal this feature solves (FR-017, SC-009).

A module constant rather than a value built per call, so every result gives the same reason
and the reason improves in one place. It is not an error -- nothing failed -- which is why it
lives with the result records rather than in ``core.errors``.
"""

DETERMINISM_NOTE: Final = (
    "This verdict is one path under one stated growth assumption, not a probability. No "
    "distribution of outcomes was computed and none is implied: shortfall probability across "
    "scenarios needs stochastic machinery this feature does not have (FR-021). Change the "
    "assumption and the verdict may change with it."
)
"""What every goal result says about the standing of its own verdict (FR-021, research.md D10).

A bare "missed by 40 000 UAH" invites being read as a likelihood. Saying out loud that it is
one path under one assumption costs a sentence and forecloses the misreading -- and there is
no field anywhere in this module a probability could later be quietly written into.
"""


@dataclass(frozen=True, slots=True)
class RealTargetSum:
    """A target restated in the purchasing power of a stated period. Nothing here builds one.

    It exists so the real-terms slot has a type today and the CPI feature can fill it without
    reshaping the result -- and, more importantly, so that a *nominal* ``Money`` cannot be
    assigned into that slot at all. That is 001's mechanism (its research.md D4): the two
    types are unrelated, so the mistake is a mypy error rather than something a test has to
    notice.
    """

    amount: Money
    """The target expressed in the purchasing power of :attr:`measured_in`."""

    measured_in: date
    """The period whose prices the amount is expressed in. Without it a "real" figure is a
    number with no unit: real *when* is half of what real means."""


@dataclass(frozen=True, slots=True)
class SolvedDate:
    """The date mode's two answers, each labelled as what it is (FR-015, research.md D5).

    They are different facts and neither substitutes for the other. Rounding one into the
    other silently is the nearest answer this spec forbids twice.
    """

    exact: float
    """Months from ``as_of``, real-valued: the point at which the balance equals the target.

    Generally not a date. A target reached at 12.5 months is reached when the twelfth
    contribution has landed and the thirteenth has not. This is the value FR-013's round trip
    closes on, which is what makes it the *exact* one -- and it may be negative, meaning the
    target was already passed before the evaluation date.
    """

    first_reached_on: date
    """The first month end on which the balance is at or above the target.

    What the owner can act on. It is the first *contribution date* at or after
    :attr:`exact`, which is an exact statement rather than a rounding: between contributions
    the balance moves monotonically whenever the target is reachable at all, so the first
    month end past the crossing is the first schedule date that gets there.
    """


@dataclass(frozen=True, slots=True)
class Met:
    """The three declared variables hold together, by this much (FR-018)."""

    margin: Money
    """Reached balance minus target. Zero when the target is met exactly, which is a verdict
    of *met* rather than *missed by a rounding hair*: the single project tolerance governs the
    boundary (spec, Edge Cases)."""


@dataclass(frozen=True, slots=True)
class Missed:
    """The three cannot hold together, stated from both sides (FR-018).

    Both faces, because either alone leaves the owner with half the decision: how much more to
    put in, or how much longer to wait.
    """

    shortfall_at_target: Money
    """Target minus reached balance on the target date. Strictly positive."""

    reached_on: date
    """The first month end on which the target *would* be reached, later than the target date.

    A fact, not a suggestion. Nothing declared is adjusted to produce it: the contribution and
    the target come back exactly as stated, and this says when they would meet.
    """


@dataclass(frozen=True, slots=True)
class Unreachable:
    """The target is never reached under the stated assumption, and here is why (FR-019).

    Never a capped horizon, never an arbitrarily distant date, never a nearest answer. There
    are two shapes of this in practice and the reason distinguishes them: a balance that does
    not grow at all against a bigger target, and a balance whose growth has a ceiling -- under
    a negative assumption a fixed contribution settles where the monthly loss equals the
    monthly payment, and a target above that level is never reached however long anyone waits.
    """

    reason: str
    """Why, in the output's own words, naming the figures that make it so."""


Feasibility = Met | Missed | Unreachable
"""The verdict on a fully declared goal. Match exhaustively; there is no fourth answer."""


@dataclass(frozen=True, slots=True)
class GoalOutcome:
    """One solved goal: what was asked, what came back, and under what model.

    Every field is populated in every mode. The three variables are the two the owner declared
    plus the one that was solved, so a reader never has to know which was which to read the
    answer -- :attr:`solved_for` says which, and the declared ones come back exactly as they
    were declared (FR-018: nothing is adjusted to make a goal pass).
    """

    goal_id: str
    """Which declared goal this answers."""

    owner_id: str
    """Whose goal it is. Principle VII, on the record rather than only on the file."""

    solved_for: Literal["contribution", "sum", "date", "feasibility"]
    """Which of the three was unknown -- or ``"feasibility"`` when all three were declared.

    All three declared is not an over-declaration: it is a different question, and naming it
    here keeps the result honest about which one it answered.
    """

    monthly_contribution: Money
    """What goes in each month: declared, or solved."""

    target_sum: Money
    """The target: declared, or the sum the plan reaches."""

    target_date: date
    """When: declared, or -- in the date mode -- the first date the target is actually reached.

    In the date mode this is :attr:`SolvedDate.first_reached_on` and it is the *actionable*
    answer. The exact solution is not folded into it; it sits beside it in
    :attr:`exact_date`, in months, because they are different facts (FR-015).
    """

    exact_date: SolvedDate | None
    """Both of the date mode's answers, or ``None`` in the modes that solved something else.

    ``None`` here is not a missing value: in the sum and contribution modes the date was
    *declared*, so there is no exact solution to report and nothing was rounded.
    """

    conventions: Conventions
    """The model the arithmetic used, so a hand computation checks the same one (FR-014)."""

    feasibility: Feasibility
    """The verdict. In a solve mode it is ``Met`` by a margin of zero -- the residual of the
    solve, reported rather than assumed: a non-zero margin there would mean the closed form
    and the evaluation disagree about the same model."""

    terms: Literal["nominal"]
    """Nominal, on the result's face (FR-017, owner decision 2026-08-22)."""

    real: RealTargetSum | RealTermsUnavailable
    """The real-terms figure, or a typed statement of why there is none.

    Always the latter in this feature. Present and explicitly empty rather than absent, so the
    CPI feature fills the slot without changing the shape of the result or anything that
    consumes it (SC-009).
    """

    determinism_note: str
    """That this is one path under one stated assumption, not a probability (FR-021)."""

    provenance: Provenance
    """Every source behind every figure here -- in particular the growth assumption's marks."""


@dataclass(frozen=True, slots=True)
class GoalUnderdetermined:
    """Fewer than two of the three variables were declared, so there is nothing to solve.

    FR-011. Names what is missing rather than choosing one to invent: a goal with only a
    contribution could be completed by inventing a sum or by inventing a date, and either
    would be the tool writing the owner's plan for him.
    """

    goal_id: str

    missing: tuple[str, ...]
    """Which of the three were not declared, by field name."""

    reason: str


@dataclass(frozen=True, slots=True)
class StartingAmountMissing:
    """No opening balance was declared, and none is assumed (FR-012)."""

    goal_id: str

    reason: str


@dataclass(frozen=True, slots=True)
class GrowthAssumptionMissing:
    """No growth assumption was declared, and no rate is defaulted (FR-012)."""

    goal_id: str

    reason: str


@dataclass(frozen=True, slots=True)
class CurrencyNotYetModelled:
    """The target is denominated in a currency this feature cannot yet evaluate (FR-016).

    **Not yet modelled, never invalid.** The declared currency is one the engine knows; what is
    missing is the dated rate that would make a target in it comparable with a balance in the
    base currency. §4.7 is explicit that a dollar target and a hryvnia target are different
    goals under devaluation, so this is a stated deferral rather than a boundary --
    ``specs/features.toml`` records ``multi-currency-goals`` as owner-requested future work,
    and the message must not read as though the case were closed.
    """

    goal_id: str

    declared: Currency
    """What the goal is denominated in."""

    base_currency: Currency
    """What this run evaluates in."""

    reason: str


@dataclass(frozen=True, slots=True)
class NoContributionNeeded:
    """The target is already met without paying anything in (FR-020).

    Returned instead of a negative monthly figure. A negative contribution is arithmetically
    fine and operationally nonsense: it is an instruction to withdraw, which is not the
    question the owner asked, and presenting it as the answer would be the tool answering a
    nearby one.
    """

    goal_id: str

    margin: Money
    """By how much the target is already met on the target date. Zero at the boundary, which
    is why FR-020 says *at or below*: a solved contribution of exactly zero is "none needed",
    not "pay zero a month"."""

    reason: str


@dataclass(frozen=True, slots=True)
class TargetDateNotInFuture:
    """The target date is on or before the evaluation date, so there is no schedule to run.

    Spec, Edge Cases: never solved "backwards". The same date as the evaluation is refused
    too -- a horizon of zero months has no contributions in it and no growth on it, so the
    contribution mode would be dividing by nothing.
    """

    goal_id: str

    as_of: date

    target_date: date

    reason: str
