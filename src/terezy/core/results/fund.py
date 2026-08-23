"""What one fund holding produced, and the six ways a run can honestly produce nothing.

The result shape for :mod:`terezy.core.instruments.fund`. It exists for one reason beyond
recording amounts: **the two-class split has to be visible**. A projection that taxed a
distribution at 14% and a redemption at 23% and then reported one total would be correct in
the ledger and useless to the reader, which is what FR-007's per-class subtotals are for
(research.md D4).

**Every figure here is read off the ledger**, exactly as ``results.project`` does: the
events are folded, the charges are computed against what the fold realised, the charges are
woven back in, and the whole thing is folded again. Nothing is read off the instrument's own
arithmetic, because a figure that came into existence twice can disagree with itself.

**No statistical metric, and no field one could sit in.** Both Inzhur funds are
assumption-driven, so :func:`statistical_metric` returns a typed refusal and there is
nowhere on :class:`FundProjection` for a volatility or a Sharpe ratio to be written
(research.md D10, FR-005). A caveated number gets copied without its caveat; a refusal
cannot be.

**A range stays a range.** Where the fund states 25-29% and the owner has chosen no point
inside it, the result is a :class:`RangeProjection` -- two complete projections, one at each
end -- rather than one figure at a midpoint nobody declared (research.md D11). There is no
midpoint helper in this module or in any other.

**Six typed refusals**, none of them an exception. Each carries the reason, and the reason
reaches the output.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import TYPE_CHECKING, Final, Literal, assert_never

from terezy.core.errors import (
    InconsistentTerms,
    InfeasiblePurchase,
    InstrumentFailure,
    LedgerInvariantError,
    UnresolvedTaxClass,
)
from terezy.core.instruments import fund
from terezy.core.instruments.fund import (
    BuybackAvailability,
    ChosenPoint,
    DeclaredYield,
    ExchangeRateAssumption,
    ExecutionPlan,
    ExitPlan,
    FundDeclaration,
    LiquidityMode,
    PeggedAmount,
    VerificationTask,
)
from terezy.core.ledger import engine
from terezy.core.ledger.engine import LedgerState
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind
from terezy.core.primitives import conventions, money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.results.hurdle import HurdleRate
from terezy.core.tax import registry as tax_registry
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxClass, TaxContext
from terezy.core.tax.schedule import RateEntry, RateUndeclaredBefore, rate_on

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping, Sequence

    from terezy.core.instruments.interface import DateRange, Holding

CARRYFORWARD_NOT_MODELLED: Final = (
    "the realised loss is reported and not carried forward: loss offset and carryforward "
    "are not modelled in this feature, so nothing here reduces a later year's tax"
)
"""FR-008's required statement, written once so every site says the same thing."""

ROUTE_COSTS_EXCLUDED: Final = (
    "funding and exit route costs are excluded — this compares an instrument against an "
    "instrument, and the route that gets money in and out is a later feature"
)
"""FR-025's required statement. Named rather than repeated, for the same reason."""

NOMINAL_ONLY: Final = "inflation is not modelled, so every figure here is nominal"


# ---------------------------------------------------------------------------
# The owner's per-run inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FundAssumptions:
    """What the owner states for one run, beyond what the fund declares.

    Every field is required and none has a default anywhere in the stack. That is the
    whole discipline of research.md D5 applied to five inputs rather than one: an unstated
    assumption is indistinguishable from a checked one, and each of these changes the
    answer.
    """

    liquidity_mode: LiquidityMode
    """Practice or legal. Stated on every result (FR-016)."""

    buyback: BuybackAvailability
    """Whether the scenario assumes the manager's discretionary buyback is on offer.

    Only meaningful under the legal terms, and read only there: the practice mode *is* the
    assumption that the buyback happens.
    """

    exit_on: date | None
    """When the owner asks to exit, or ``None`` to hold to the fund's own end.

    ``None`` does not mean "sell at the horizon". A holding is never liquidated because a
    projection ran out of dates; it either reaches the termination payout or stays open.
    """

    yield_point: ChosenPoint | None
    """A point inside a fund-stated range, labelled the owner's assumption, or ``None``.

    ``None`` against a range produces a :class:`RangeProjection` rather than a figure.
    """

    exchange_rate: ExchangeRateAssumption | None
    """The rate that sizes a pegged payment, or ``None``. Required wherever a peg exists;
    absent, the run is a typed :class:`PegUnsizable` naming exactly this input."""

    consumption_method: str
    """Which lots a disposal consumes -- a key of ``lots.CONSUMPTION_ORDER_FNS``."""


# ---------------------------------------------------------------------------
# The typed refusals
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PurchaseAfterCutoff:
    """A purchase dated after the fund stopped accepting subscriptions (FR-019)."""

    instrument_id: str
    purchased_on: date
    cutoff: date
    reason: str


@dataclass(frozen=True, slots=True)
class RedemptionRefused:
    """No buyback obligation exists before the termination date, and none was on offer.

    The holding **stays open**: nothing is executed, adjusted or deferred (research.md D6,
    FR-017). The failure mode this forecloses is the tempting one -- executing the exit
    anyway "at the legal discount" because a number was wanted.
    """

    instrument_id: str
    requested_on: date
    terminates_on: date
    """The next guaranteed exit, named so the reader knows what *is* available."""

    reason: str


@dataclass(frozen=True, slots=True)
class MetricRefused:
    """A statistical metric was requested for an assumption-driven instrument (FR-005)."""

    instrument_id: str
    metric: str
    reason: str


@dataclass(frozen=True, slots=True)
class PegUnsizable:
    """A pegged flow cannot become hryvnia without a declared rate assumption (FR-021)."""

    instrument_id: str
    missing_input: str
    """Named exactly, so the remedy is one line of scenario input rather than a search."""

    peg_currency: Currency
    reason: str


@dataclass(frozen=True, slots=True)
class AwaitingVerification:
    """A projection needed a value the primary documents did not give (research.md D8).

    Carries the *question*, not a placeholder value, because the record it comes from
    carries no value either. This turns "I cannot compute this" into "go and read this
    document".
    """

    instrument_id: str
    question: str
    searched: str
    searched_on: date | None
    """When the document was searched, or ``None`` where the declaration records no task.

    ⚙ ``None`` rather than a stand-in. This field used to fall back to the fund's
    termination date when no matching :class:`~terezy.core.instruments.fund.VerificationTask`
    was declared, which put a fabricated date in an audit field — the date would have read
    as "somebody looked on this day" when nobody had. A missing task is itself a defect in
    the declaration, and the refusal now says so instead of dressing it up.
    """

    reason: str


FundRefusal = (
    PurchaseAfterCutoff
    | RedemptionRefused
    | MetricRefused
    | PegUnsizable
    | AwaitingVerification
    | RateUndeclaredBefore
)
"""The six ways a fund run honestly produces no figure. Match exhaustively."""


# ---------------------------------------------------------------------------
# The result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClassSubtotal:
    """What one declared tax class charged across the whole run (FR-007).

    The reason this record exists: without it the two-class split is invisible to a reader
    even when the ledger is right, and E1's whole point is that a fund payout and a fund
    exit are not taxed alike.
    """

    tax_class_id: str
    kinds: tuple[TaxableEventKind, ...]
    """Which income kinds this class actually charged in this run, sorted by name."""

    pit: Money
    levy: Money
    total_charged: Money
    """PIT plus levy for this class.

    Named ``total_charged`` rather than ``total`` deliberately: ``tests/contract/
    test_cost_labels.py`` refuses a bare ``total`` on any record in ``core.results``,
    because that is the name an unlabelled *route* cost arrives under. This one is a tax
    charge and says so.
    """

    charge_count: int
    provenance: Provenance
    """The citations of the dated entries that produced these charges."""


@dataclass(frozen=True, slots=True)
class DistributionLine:
    """One declared payout, with the rate entry that taxed it and the peg that sized it."""

    record_on: date
    paid_on: date
    gross: Money
    tax_class_id: str
    rate_effective_from: date
    """Which dated entry selected the rate, so "which date chose this figure" is stated
    rather than left to be inferred from a payment date (spec.md, Edge Cases)."""

    tax: Money
    net: Money
    pegged: PeggedAmount | None
    """The USD-equivalent term this payment was sized from, where one exists. Never money."""

    cap_bound: bool
    """Whether the declared «граничний курс» bound the conversion — the peg partially
    breaking under devaluation, kept visible rather than lost in a hryvnia figure."""


@dataclass(frozen=True, slots=True)
class ExitLine:
    """The exit, whatever caused it: what was received, what was given up, what was taxed."""

    executed_on: date
    settles_on: date
    cause: Literal["requested", "termination"]
    nav_per_unit: Money
    discount_rate: float
    gross_proceeds: Money
    """Post-discount: what actually arrived. The tax base is computed from this, never
    from NAV before the discount (FR-018)."""

    discount_amount: Money
    """NAV times the discount, as its own line (FR-018)."""

    realised_gain: Money
    """Proceeds less the basis consumed less fees allocated to the disposal, from the
    ledger's own disposal record. Negative for a loss."""

    taxable_base: Money
    """The gain, or **zero** where the disposal realised a loss. Not a silent clamp: the
    loss is on :attr:`realised_loss` and the carryforward statement is beside it."""

    realised_loss: Money | None
    carryforward_note: str | None
    tax_class_id: str
    rate_effective_from: date
    tax: Money


@dataclass(frozen=True, slots=True)
class FundProjection:
    """One fund holding, projected under one stated set of assumptions.

    No ``volatility``, no ``sharpe``, no ``sortino``, and **no field one could live in**.
    No computed fee either: the researched fee facts are context for the declared yield and
    nothing accrues from them (research.md D9, D10).
    """

    instrument_id: str
    liquidity_mode: LiquidityMode
    """Always stated. There is no default anywhere in the stack (FR-016)."""

    is_assumption_driven: Literal[True]
    """Every figure below rests on declared terms and stated assumptions rather than on
    market history, and the result says so on its face (FR-004)."""

    ledger: LedgerState
    charges: tuple[TaxCharge, ...]
    tax_by_class: tuple[ClassSubtotal, ...]
    distributions: tuple[DistributionLine, ...]
    exit_line: ExitLine | None
    """``None`` where the holding is still open at the horizon: nothing was liquidated
    because a projection ended."""

    entry_spread: Money
    exit_spread: Money
    exit_discount: Money | None
    """The legal terms' discount as its own line; ``None`` under the practice mode, where
    the exit is at NAV and there is no discount to report."""

    round_trip_spread: Money
    """Entry plus exit. The figure that belongs in a comparison: a one-way number may
    never be presented as a round trip (Principle VI)."""

    total_tax: Money
    net_proceeds: Money
    """Every inflow less every outflow, tax included: what the holding actually returned."""

    peg_statement: str | None
    yield_basis: DeclaredYield | ChosenPoint
    excludes: tuple[str, ...]
    rests_on: tuple[str, ...]
    """The stated assumptions and unverified terms this result depends on, in words."""

    provenance: Provenance


@dataclass(frozen=True, slots=True)
class RangeProjection:
    """The fund states a range and the owner chose no point, so the answer is two figures.

    Not a midpoint, not the low end, not the high end. The range that survives to the
    output is more useful than a false point, and Principle I's ordering puts a
    distribution ahead of a point estimate anyway (research.md D11, SC-013).
    """

    instrument_id: str
    declared_yield: DeclaredYield
    at_low: FundProjection
    at_high: FundProjection
    note: str


FundOutcome = (
    FundProjection | RangeProjection | FundRefusal | InstrumentFailure | UnresolvedTaxClass
)
"""What a fund projection returns. Never a partial result and never an empty one."""


# ---------------------------------------------------------------------------
# The refusal a metric request gets
# ---------------------------------------------------------------------------

STATISTICAL_METRICS: Final[tuple[str, ...]] = (
    "volatility",
    "sharpe",
    "sortino",
    "beta",
    "var",
)
"""The names a caller might ask for. Listed so the refusal can be specific about what it
is refusing, not so that any of them could be computed."""


def statistical_metric(declaration: FundDeclaration, metric: str) -> MetricRefused:
    """Refuse a statistical metric for an assumption-driven instrument. Always.

    The return type is the refusal itself rather than a union: there is no input to this
    function that produces a number, which is Principle I in its most literal form --
    *refuse to emit a Sharpe ratio rather than computing one from invented data*. A
    signature that could return a float would be a signature somebody eventually makes
    return one.
    """
    return MetricRefused(
        instrument_id=declaration.id,
        metric=metric,
        reason=(
            f"{declaration.id!r} is an assumption-driven instrument: its projections are "
            f"contractual arithmetic over terms the fund states about itself, and there "
            f"is no price history behind them. A {metric!r} computed from that would be a "
            "statistic about invented data wearing the same label as a measured one. "
            "Refused rather than caveated — a caveated number gets copied without its "
            "caveat."
        ),
    )


# ---------------------------------------------------------------------------
# The projection
# ---------------------------------------------------------------------------


def project_fund(
    declaration: FundDeclaration,
    holding: Holding,
    horizon: DateRange,
    assumptions: FundAssumptions,
    *,
    tax_classes: Mapping[str, TaxClass],
) -> FundOutcome:
    """Project one fund holding under one stated set of assumptions.

    The order of the guards is the order a reader would ask the questions in, and the
    **first** problem found is the one reported -- an owner fixing a purchase after the
    cutoff does not also need to be told the peg cannot be sized.

    ``tax_classes`` is passed in rather than looked up, exactly as ``results.project``
    takes it: loading is the data layer's job, and the core must be testable with no file
    on disk near the arithmetic.
    """
    refused = _refuse(declaration, holding, assumptions)
    if refused is not None:
        return refused

    resolved = _resolve_rate(declaration.declared_yield, assumptions.yield_point)
    if resolved is None:
        return _both_ends(declaration, holding, horizon, assumptions, tax_classes=tax_classes)
    return _project_at(
        declaration,
        holding,
        horizon,
        assumptions,
        rate=resolved,
        basis=assumptions.yield_point or declaration.declared_yield,
        tax_classes=tax_classes,
    )


def _resolve_rate(declared: DeclaredYield, chosen: ChosenPoint | None) -> float | None:
    """The one rate to project at, or ``None`` where the honest answer is two.

    Three cases and no fourth. A fund stating a single figure has ``low == high`` and that
    is the rate. A fund stating a range and an owner who chose a point inside it gets the
    owner's point, labelled his. A fund stating a range and no chosen point gets ``None``,
    and the caller projects **both ends** -- because the alternative is picking one, and
    the midpoint is the most seductive invented number in this feature.
    """
    if chosen is not None:
        return chosen.rate
    if declared.low == declared.high:
        return declared.low
    return None


def _both_ends(
    declaration: FundDeclaration,
    holding: Holding,
    horizon: DateRange,
    assumptions: FundAssumptions,
    *,
    tax_classes: Mapping[str, TaxClass],
) -> FundOutcome:
    """Two complete projections, one at each end of the fund-stated range."""
    declared = declaration.declared_yield
    at_low = _project_at(
        declaration,
        holding,
        horizon,
        assumptions,
        rate=declared.low,
        basis=declared,
        tax_classes=tax_classes,
    )
    if not isinstance(at_low, FundProjection):
        return at_low
    at_high = _project_at(
        declaration,
        holding,
        horizon,
        assumptions,
        rate=declared.high,
        basis=declared,
        tax_classes=tax_classes,
    )
    if not isinstance(at_high, FundProjection):
        return at_high  # pragma: no cover -- the low end already succeeded on the same terms
    return RangeProjection(
        instrument_id=declaration.id,
        declared_yield=declared,
        at_low=at_low,
        at_high=at_high,
        note=(
            f"{declaration.id!r} states {declared.low!r} to {declared.high!r} a year and "
            "no "
            "point inside it was chosen, so the outcome is reported at both ends. No "
            "midpoint is taken: the fund did not state one, and a point estimate the "
            "inputs do not support is the false precision this tool exists to refuse."
        ),
    )


def _refuse(
    declaration: FundDeclaration,
    holding: Holding,
    assumptions: FundAssumptions,
) -> FundRefusal | InstrumentFailure | None:
    """Every reason this holding cannot be projected at all, in the order a reader asks."""
    cutoff = declaration.subscription_cutoff
    if cutoff is not None and holding.purchased_on > cutoff:
        return PurchaseAfterCutoff(
            instrument_id=declaration.id,
            purchased_on=holding.purchased_on,
            cutoff=cutoff,
            reason=(
                f"{declaration.id!r} stopped accepting subscriptions on "
                f"{cutoff.isoformat()}, and this purchase is dated "
                f"{holding.purchased_on.isoformat()}. Refused rather than backdated or "
                "queued: a purchase the fund would not have accepted did not happen, and "
                "projecting it would report a holding nobody could have bought."
            ),
        )

    if holding.quantity < declaration.minimum_units:
        required = money.scale(declaration.nav_per_unit, declaration.minimum_units)
        actual = money.scale(declaration.nav_per_unit, holding.quantity)
        return InfeasiblePurchase(
            constraint="minimum_units",
            required=required,
            actual=actual,
            shortfall=money.sub(required, actual),
            reason=(
                f"{declaration.id!r} requires at least {declaration.minimum_units!r} "
                f"unit(s) and this purchase is {holding.quantity!r}. Reported rather "
                "than rounded up to fit: rounding would spend money the owner did not "
                "agree to spend."
            ),
        )

    if declaration.terminates_on < holding.purchased_on:
        return InconsistentTerms(
            first_term="fund.terminates_on",
            second_term="holding.purchased_on",
            reason=(
                f"{declaration.id!r} terminates {declaration.terminates_on.isoformat()}, "
                f"before this purchase settles {holding.purchased_on.isoformat()}. There "
                "is no holding period to project, and a zero-length one would report a "
                "fund that paid nothing rather than one that could not be bought."
            ),
        )

    chosen = assumptions.yield_point
    declared = declaration.declared_yield
    if chosen is not None and not declared.low <= chosen.rate <= declared.high:
        return InconsistentTerms(
            first_term="assumptions.yield_point.rate",
            second_term="fund.declared_yield",
            reason=(
                f"the chosen rate {chosen.rate!r} lies outside the range "
                f"{declared.low!r} to {declared.high!r} that {declaration.id!r} states. A "
                "point outside the fund's own range is not a choice within it: it is a "
                "different claim about the fund, and it would be reported under the "
                "fund's citation. Refused rather than clamped to the nearer end, which "
                "would silently change the owner's stated assumption."
            ),
        )

    return _refuse_the_exit(declaration, holding, assumptions) or _refuse_the_peg(
        declaration, assumptions
    )


def _refuse_the_exit(
    declaration: FundDeclaration,
    holding: Holding,
    assumptions: FundAssumptions,
) -> FundRefusal | InstrumentFailure | None:
    """An early exit the terms do not owe and the scenario does not grant (FR-017)."""
    requested = assumptions.exit_on
    if requested is None:
        return None
    if requested < holding.purchased_on:
        return InconsistentTerms(
            first_term="assumptions.exit_on",
            second_term="holding.purchased_on",
            reason=(
                f"the exit is requested for {requested.isoformat()}, before the purchase "
                f"settles {holding.purchased_on.isoformat()}. Units cannot be sold before "
                "they are held."
            ),
        )
    if requested >= declaration.terminates_on:
        # Not an early exit at all: the fund has ended, and the termination payout is what
        # happens. Handled by the plan rather than refused.
        return None
    if assumptions.liquidity_mode == "legal" and assumptions.buyback == "unavailable":
        return RedemptionRefused(
            instrument_id=declaration.id,
            requested_on=requested,
            terminates_on=declaration.terminates_on,
            reason=(
                f"{declaration.id!r} owes no buyback before it terminates on "
                f"{declaration.terminates_on.isoformat()}: under its регламент an earlier "
                f"exit is {declaration.liquidity.legal.buyback_before_termination}, and "
                "this scenario declares that discretion is not being exercised. The "
                "termination payout is the next guaranteed exit. Nothing is executed at "
                "the legal discount instead — a discretionary favour is not a right, and "
                "the holding stays open."
            ),
        )
    return None


def _refuse_the_peg(
    declaration: FundDeclaration,
    assumptions: FundAssumptions,
) -> FundRefusal | None:
    """A pegged payout with no declared exchange rate, and a cap nobody has confirmed."""
    terms = declaration.distribution
    if terms is None or terms.peg is None:
        return None
    if assumptions.exchange_rate is None:
        return PegUnsizable(
            instrument_id=declaration.id,
            missing_input="FundAssumptions.exchange_rate",
            peg_currency=terms.peg.sized_in,
            reason=(
                f"{declaration.id!r} sizes its payouts in "
                f"{terms.peg.sized_in.value} and pays them in "
                f"{terms.paid_in.value}, so a hryvnia figure cannot exist without a rate. "
                "No rate is assumed and none is read from anywhere: state one as the "
                "owner's assumption, or accept that this flow has no size. There is no "
                "market rate source in this feature."
            ),
        )
    return None


def _plan(
    declaration: FundDeclaration,
    horizon: DateRange,
    assumptions: FundAssumptions,
    rate: float,
) -> ExecutionPlan:
    """Everything one run resolved before any event existed. No refusal reaches here."""
    return ExecutionPlan(
        liquidity_mode=assumptions.liquidity_mode,
        yield_rate=rate,
        entry_markup=fund.entry_markup_for(declaration, assumptions.liquidity_mode),
        exit=_exit_plan(declaration, horizon, assumptions),
        exchange_rate=assumptions.exchange_rate,
    )


def _exit_plan(
    declaration: FundDeclaration,
    horizon: DateRange,
    assumptions: FundAssumptions,
) -> ExitPlan | None:
    """When and how the holding ends, or ``None`` where it is still open at the horizon.

    Three cases, and the third is the one that matters. A **requested** exit before the
    fund's end executes on the day asked for, at the assumed mode's discount and delay. An
    exit requested on or after the termination date, or a horizon that simply reaches it,
    is the **termination payout**: a dated disposal at NAV with no discount, because it is
    the contract ending rather than a favour being asked for. Anything else leaves the
    holding open -- a projection running out of dates is not a reason to sell (FR-019).

    A termination payout settles on the **legal** terms' delay whatever mode was assumed,
    because the payout is an obligation of the регламент and not an instance of the
    company's current practice.
    """
    requested = assumptions.exit_on
    terminates = declaration.terminates_on
    if requested is not None and requested < terminates:
        discount = fund.exit_discount_for(declaration, assumptions.liquidity_mode)
        delay = fund.settlement_business_days_for(declaration, assumptions.liquidity_mode)
        return ExitPlan(
            executed_on=requested,
            settles_on=fund.settlement_date(requested, delay),
            cause="requested",
            discount=discount,
        )
    if requested is not None or horizon.end >= terminates:
        return ExitPlan(
            executed_on=terminates,
            settles_on=fund.settlement_date(
                terminates, declaration.liquidity.legal.settlement_business_days
            ),
            cause="termination",
            discount=0.0,
        )
    return None


def _pegged_distribution(
    declaration: FundDeclaration,
    holding: Holding,
    plan: ExecutionPlan,
    peg: fund.Peg,
    paid_on: date,
) -> tuple[Money, PeggedAmount, bool] | AwaitingVerification:
    """One pegged payout, sized in the peg's currency and converted at the capped rate.

    The unit's value **in the peg's currency** is its declared NAV divided by the owner's
    assumed rate, the period's income is that times a twelfth of the declared annual rate,
    and the hryvnia payment is that term converted at ``min(assumed, cap)``. Written out
    that way rather than collapsed, because the collapse hides what owner decision A is
    about: below the ceiling the payment tracks the dollar exactly, and above it the peg
    partially breaks and the holder starts losing real income.

    A payment dated before the earliest declared ceiling is **refused**, naming the
    verification task: "no ceiling is declared for this date" is not "there is no ceiling",
    and reading the first as the second would size the payment at the full assumed rate --
    the favourable answer, chosen silently.
    """
    assumption = plan.exchange_rate
    if assumption is None:  # pragma: no cover -- _refuse_the_peg rules this out first
        raise ValueError("a pegged distribution reached sizing with no declared rate")
    ceiling = fund.cap_on(peg, paid_on)
    if ceiling is None:
        return _awaiting_cap(declaration, paid_on)
    terms = declaration.distribution
    if terms is None:  # pragma: no cover -- only reached with distribution terms in hand
        raise ValueError("a pegged distribution reached sizing with no distribution terms")
    per_unit_in_peg = declaration.nav_per_unit.amount / assumption.uah_per_unit
    pegged = PeggedAmount(
        amount=(
            per_unit_in_peg
            * holding.quantity
            * fund.monthly_yield_fraction(plan, terms.payout_share)
        ),
        sized_in=peg.sized_in,
        provenance=prov.merge(
            declaration.nav_per_unit.provenance,
            declaration.declared_yield.provenance,
        ),
    )
    amount, bound = fund.size_pegged_payment(pegged, assumption, ceiling, paid_in=terms.paid_in)
    return amount, pegged, bound


def _awaiting_cap(declaration: FundDeclaration, paid_on: date) -> AwaitingVerification:
    """The cap question, as a refusal naming the task and the date it was needed for."""
    task = _task_mentioning(declaration, "курс")
    unrecorded = (
        " This fund declares a peg whose ceiling does not cover the date AND records no "
        "verification task about the ceiling, so there is not even a question to hand back: "
        "add a [[instrument.verification_task]] naming what has to be looked up."
    )
    return AwaitingVerification(
        instrument_id=declaration.id,
        question=(
            task.question
            if task is not None
            else "the «граничний курс» in force — the ceiling the leases convert at"
        ),
        searched=(
            task.searched if task is not None else "nothing; no verification task is declared"
        ),
        searched_on=task.searched_on if task is not None else None,
        reason=(
            f"{declaration.id!r} declares no «граничний курс» in force on "
            f"{paid_on.isoformat()}, so it is not known whether the ceiling binds that "
            "payment. Refused rather than sized at the full assumed rate: 'no ceiling is "
            "declared for this date' and 'there is no ceiling' are different claims, and "
            "the second one is the favourable one. Declare the cap in force, or move the "
            "projection inside the dates the declared ladder covers."
            + ("" if task is not None else unrecorded)
        ),
    )


def _task_mentioning(declaration: FundDeclaration, needle: str) -> VerificationTask | None:
    """The recorded open question about ``needle``, or ``None`` if none was recorded.

    Matched on the declared prose rather than on an enumerated code, deliberately: a task
    is a sentence the owner has to act on, and a parallel code vocabulary would be a second
    thing to keep in step with it. ``None`` where nothing matches, because inventing a
    question is as bad as inventing an answer.
    """
    for task in declaration.verification_tasks:
        if needle.casefold() in task.question.casefold():
            return task
    return None


def _distribution_events(
    declaration: FundDeclaration,
    holding: Holding,
    plan: ExecutionPlan,
    horizon: DateRange,
) -> tuple[tuple[Event, PeggedAmount | None, bool, date], ...] | AwaitingVerification:
    """Every declared payout due while the units are held, with its peg facts beside it.

    Entitlement stops when the exit **executes**, not when it settles: an owner who has
    surrendered the units does not receive the next month's payout while the money is in
    transit.
    """
    terms = declaration.distribution
    if terms is None:
        return ()
    until = horizon.end if plan.exit is None else min(plan.exit.executed_on, horizon.end)
    built: list[tuple[Event, PeggedAmount | None, bool, date]] = []
    for record_on, paid_on in fund.distribution_dates(terms, holding, until):
        pegged: PeggedAmount | None = None
        bound = False
        if terms.peg is None:
            amount = money.scale_sourced(
                declaration.nav_per_unit,
                holding.quantity * fund.monthly_yield_fraction(plan, terms.payout_share),
                declaration.declared_yield.provenance,
            )
        else:
            sized = _pegged_distribution(declaration, holding, plan, terms.peg, paid_on)
            if isinstance(sized, AwaitingVerification):
                return sized
            amount, pegged, bound = sized
        built.append(
            (
                fund.distribution_event(
                    declaration,
                    holding,
                    amount,
                    record_on=record_on,
                    paid_on=paid_on,
                    sequence=0,
                ),
                pegged,
                bound,
                record_on,
            )
        )
    return tuple(built)


def _project_at(
    declaration: FundDeclaration,
    holding: Holding,
    horizon: DateRange,
    assumptions: FundAssumptions,
    *,
    rate: float,
    basis: DeclaredYield | ChosenPoint,
    tax_classes: Mapping[str, TaxClass],
) -> FundOutcome:
    """One projection at one rate: events, fold, charges, fold again, lines.

    The same two-pass shape ``results.project`` uses, and for the same reason: the tax on a
    disposal is knowable only from the realised gain, which is a property of the fold. Tax
    events are cash-only, so weaving them in cannot change a disposal the first fold
    computed -- the two passes agree by construction rather than by coincidence.
    """
    plan = _plan(declaration, horizon, assumptions, rate)
    payouts = _distribution_events(declaration, holding, plan, horizon)
    if isinstance(payouts, AwaitingVerification):
        return payouts

    gross = _sequence(declaration, holding, plan, [event for event, _, _, _ in payouts])
    currency = declaration.unit_currency
    gross_state = engine.fold(
        gross, base_currency=currency, consumption_method=assumptions.consumption_method
    )

    charged = _charge_every_taxable_event(declaration, gross_state, tax_classes)
    if not isinstance(charged, tuple):
        return charged

    combined, charges = _interleave(gross_state, charged)
    state = engine.fold(
        combined, base_currency=currency, consumption_method=assumptions.consumption_method
    )
    return _assemble(
        declaration,
        holding,
        plan,
        state,
        charges,
        payouts=payouts,
        basis=basis,
        tax_classes=tax_classes,
    )


def _sequence(
    declaration: FundDeclaration,
    holding: Holding,
    plan: ExecutionPlan,
    payouts: Sequence[Event],
) -> tuple[Event, ...]:
    """The purchase, every payout and the exit, numbered once in date order.

    Numbered here rather than at construction, because a payout's date and the exit's
    settlement date decide the order and neither is known until the plan is resolved. The
    ledger requires sequence order to agree with date order, and doing the numbering in one
    place is what guarantees it.
    """
    purchase = fund.purchase_event(declaration, holding, plan, sequence=1)
    tail: list[Event] = list(payouts)
    if plan.exit is not None:
        tail.append(fund.exit_event(declaration, holding, plan, plan.exit, sequence=0))
    ordered = sorted(tail, key=lambda event: event.occurred_on)
    return (purchase, *(replace(event, sequence=index) for index, event in enumerate(ordered, 2)))


def _charge_every_taxable_event(
    declaration: FundDeclaration,
    state: LedgerState,
    tax_classes: Mapping[str, TaxClass],
) -> tuple[TaxCharge, ...] | UnresolvedTaxClass | RateUndeclaredBefore:
    """One charge per taxable event, each under the class its own kind maps to (FR-006).

    This is E1's whole mechanism: the mapping is plural, the two values differ, and the
    class is chosen by the *kind of income* rather than by the instrument. Neither class's
    rates can reach the other's events, because neither class is ever looked up for them.
    """
    rule = tax_registry.ops_for(tax_registry.FLAT_RATE)
    charges: list[TaxCharge] = []
    for event in state.applied:
        kind = _taxable_kind(event.kind)
        if kind is None:
            continue
        resolved = _class_for(declaration, kind, tax_classes, event.occurred_on)
        if isinstance(resolved, UnresolvedTaxClass):
            return resolved
        base = _taxable_base(event, kind, state)
        outcome = rule.charge(
            event,
            resolved,
            TaxContext(
                instrument_id=declaration.id,
                taxable_event=kind,
                taxable_base=base,
                charged_for_year=event.occurred_on.year,
            ),
        )
        match outcome:
            case UnresolvedTaxClass() | RateUndeclaredBefore():
                return outcome
            case TaxCharge():
                charges.append(outcome)
            case _:  # pragma: no cover -- mypy proves this unreachable
                assert_never(outcome)
    return tuple(charges)


def _taxable_kind(kind: EventKind) -> TaxableEventKind | None:
    """Which kind of taxable income a fund event is, or ``None`` if it is not income.

    Only two kinds of income exist in a fund's stream, and they are the two that make this
    feature exist. Everything else -- the purchase, the tax charges this very function
    produces -- moves money without being income.
    """
    match kind:
        case EventKind.DISTRIBUTION:
            return TaxableEventKind.DISTRIBUTION
        case EventKind.REDEMPTION:
            return TaxableEventKind.DISPOSAL_GAIN
        case _:
            return None


def _class_for(
    declaration: FundDeclaration,
    kind: TaxableEventKind,
    tax_classes: Mapping[str, TaxClass],
    on_date: date,
) -> TaxClass | UnresolvedTaxClass:
    """The declared class governing one kind of income, or a refusal naming what is missing.

    Never a default and never "untaxed". A missing rule and a cited exemption are opposite
    claims, and reading the first as the second would flatter every figure derived from
    this holding by exactly the tax that was never charged.
    """
    class_id = declaration.tax_classes.get(kind)
    if class_id is None:
        return UnresolvedTaxClass(
            tax_class_id=f"<none declared for {kind.value}>",
            instrument_id=declaration.id,
            reason=(
                f"{declaration.id!r} produces {kind.value!r} income on "
                f"{on_date.isoformat()} but declares no tax class for it. A fund is taxed "
                "differently on a payout and on an exit, so a missing mapping is a "
                "declaration that is incomplete rather than one that means 'untaxed'."
            ),
        )
    declared = tax_classes.get(class_id)
    if declared is None:
        return UnresolvedTaxClass(
            tax_class_id=class_id,
            instrument_id=declaration.id,
            reason=(
                f"{declaration.id!r} taxes its {kind.value!r} income under class "
                f"{class_id!r}, which is not declared in the tax pack this run was given. "
                "The holding is not projected rather than projected untaxed."
            ),
        )
    return declared


def _taxable_base(event: Event, kind: TaxableEventKind, state: LedgerState) -> Money:
    """What the rates apply to: the payout itself, or the gain a disposal realised.

    **A disposal at a loss has a base of zero, and that is not a silent clamp** (FR-008).
    Investment profit tax is charged on profit; a loss produces no charge. The loss is not
    swallowed -- :class:`ExitLine` carries it as its own figure with the statement that
    carryforward is not modelled here -- and the zero keeps the gain's provenance, so it
    still cites what it was computed from. Charging a negative tax instead would report a
    refund this rule does not model, and dropping the line entirely would make the loss
    invisible.
    """
    if kind is not TaxableEventKind.DISPOSAL_GAIN:
        return event.amount
    gain = _realised_gain(event, state)
    return gain if gain.amount > 0.0 else money.scale(gain, 0.0)


def _realised_gain(event: Event, state: LedgerState) -> Money:
    """The gain the fold realised for this disposal: proceeds less basis less fees."""
    for disposal in state.disposals:
        if disposal.sequence == event.sequence:
            return disposal.realised_gain_base_ccy
    raise ValueError(  # pragma: no cover -- the fold always realises a disposal for a REDEMPTION
        f"event {event.sequence} is a redemption but the fold realised no disposal for it"
    )


def _interleave(
    gross_state: LedgerState,
    charges: Sequence[TaxCharge],
) -> tuple[tuple[Event, ...], tuple[TaxCharge, ...]]:
    """Weave each charge in behind the event it taxes, renumbering the whole stream."""
    by_sequence = {charge.event_sequence: charge for charge in charges}
    combined: list[Event] = []
    renumbered: list[TaxCharge] = []
    for event in gross_state.applied:
        taxed = replace(event, sequence=len(combined) + 1)
        combined.append(taxed)
        charge = by_sequence.get(event.sequence)
        if charge is None:
            continue
        moved = replace(charge, event_sequence=taxed.sequence)
        renumbered.append(moved)
        combined.append(_tax_event(taxed, moved, sequence=len(combined) + 1))
    return tuple(combined), tuple(renumbered)


def _tax_event(taxed: Event, charge: TaxCharge, *, sequence: int) -> Event:
    """The ledger line for one charge: cash out, on the date the income arrived."""
    return Event(
        sequence=sequence,
        occurred_on=taxed.occurred_on,
        kind=EventKind.TAX_CHARGE,
        amount=money.scale(charge.total, -1.0),
        owner_id=taxed.owner_id,
        caused_by=CausationRef(
            kind=CausationKind.TAX_RULE,
            id=charge.tax_class_id,
            detail=(
                f"tax class {charge.tax_class_id!r} charged on a taxable base of "
                f"{charge.taxable_base.amount!r} {charge.taxable_base.currency.value} "
                f"arising from event {taxed.sequence}, accruing to the "
                f"{charge.charged_for_year} tax year"
            ),
        ),
        lot_ref=None,
        quantity=None,
        allocated_to=None,
        capacity_pool=None,
    )


def _assemble(
    declaration: FundDeclaration,
    holding: Holding,
    plan: ExecutionPlan,
    state: LedgerState,
    charges: Sequence[TaxCharge],
    *,
    payouts: Sequence[tuple[Event, PeggedAmount | None, bool, date]],
    basis: DeclaredYield | ChosenPoint,
    tax_classes: Mapping[str, TaxClass],
) -> FundProjection:
    """Read every reported figure off the folded ledger and say what it rests on."""
    currency = declaration.unit_currency
    by_event = {charge.event_sequence: charge for charge in charges}
    lines = _distribution_lines(state, by_event, payouts, tax_classes)
    exit_line = _exit_line(
        declaration, holding, plan, state, by_event=by_event, tax_classes=tax_classes
    )
    entry_spread = money.scale_sourced(
        declaration.nav_per_unit,
        holding.quantity * plan.entry_markup,
        declaration.spread.provenance,
    )
    exit_spread = money.zero(currency) if exit_line is None else exit_line.discount_amount
    total_tax = money.total([charge.total for charge in charges], currency)
    return FundProjection(
        instrument_id=declaration.id,
        liquidity_mode=plan.liquidity_mode,
        is_assumption_driven=True,
        ledger=state,
        charges=tuple(charges),
        tax_by_class=_subtotals(state, charges, currency),
        distributions=lines,
        exit_line=exit_line,
        entry_spread=entry_spread,
        exit_spread=exit_spread,
        exit_discount=(
            exit_line.discount_amount
            if exit_line is not None and plan.liquidity_mode == "legal"
            else None
        ),
        round_trip_spread=money.add(entry_spread, exit_spread),
        total_tax=total_tax,
        net_proceeds=_net_proceeds(state, currency),
        peg_statement=_peg_statement(declaration, plan, lines),
        yield_basis=basis,
        excludes=(ROUTE_COSTS_EXCLUDED, NOMINAL_ONLY),
        rests_on=_rests_on(declaration, plan, basis),
        provenance=prov.merge_all(
            [
                *(event.amount.provenance for event in state.applied),
                *(charge.provenance for charge in charges),
            ]
        ),
    )


def _net_proceeds(state: LedgerState, currency: Currency) -> Money:
    """Every inflow less every outflow: what the holding actually returned, after tax."""
    return money.total([event.amount for event in state.applied], currency)


def _distribution_lines(
    state: LedgerState,
    by_event: Mapping[int, TaxCharge],
    payouts: Sequence[tuple[Event, PeggedAmount | None, bool, date]],
    tax_classes: Mapping[str, TaxClass],
) -> tuple[DistributionLine, ...]:
    """One line per payout, carrying which dated rate entry taxed it and which peg sized it."""
    peg_facts = {
        (event.occurred_on, record_on): (pegged, bound)
        for event, pegged, bound, record_on in payouts
    }
    lines: list[DistributionLine] = []
    for event in state.applied:
        if event.kind is not EventKind.DISTRIBUTION:
            continue
        charge = by_event[event.sequence]
        record_on, pegged, bound = _peg_fact_for(peg_facts, event.occurred_on)
        lines.append(
            DistributionLine(
                record_on=record_on,
                paid_on=event.occurred_on,
                gross=event.amount,
                tax_class_id=charge.tax_class_id,
                rate_effective_from=_entry_for(tax_classes, charge, event).effective_from,
                tax=charge.total,
                net=money.sub(event.amount, charge.total),
                pegged=pegged,
                cap_bound=bound,
            )
        )
    return tuple(lines)


def _peg_fact_for(
    peg_facts: Mapping[tuple[date, date], tuple[PeggedAmount | None, bool]],
    paid_on: date,
) -> tuple[date, PeggedAmount | None, bool]:
    """The record date and peg facts recorded for the payout made on this date."""
    for (payment_date, record_on), (pegged, bound) in peg_facts.items():
        if payment_date == paid_on:
            return record_on, pegged, bound
    raise ValueError(  # pragma: no cover -- every payout event was built from these facts
        f"a distribution paid {paid_on.isoformat()} has no recorded terms"
    )


def _entry_for(
    tax_classes: Mapping[str, TaxClass],
    charge: TaxCharge,
    event: Event,
) -> RateEntry:
    """Which dated entry produced this charge, so the output can name the date.

    Re-selected through the same :func:`~terezy.core.tax.schedule.rate_on` the rule used,
    rather than reconstructed from the amounts: two entries can carry the same rates, and a
    figure that named the wrong one would be a wrong label on a right number.
    """
    found = rate_on(tax_classes[charge.tax_class_id], event.occurred_on)
    if isinstance(found, RateUndeclaredBefore):
        raise LedgerInvariantError(  # pragma: no cover -- the charge already succeeded
            f"charge on event {event.sequence} exists but its class declares no rate on "
            f"{event.occurred_on.isoformat()}. The charge and the report disagree about "
            "which entry applied, which is a bug in this module rather than a fact about "
            "the money."
        )
    return found


def _exit_line(
    declaration: FundDeclaration,
    holding: Holding,
    plan: ExecutionPlan,
    state: LedgerState,
    *,
    by_event: Mapping[int, TaxCharge],
    tax_classes: Mapping[str, TaxClass],
) -> ExitLine | None:
    """The exit as its own line: NAV, the discount, the gain, and what was charged on it."""
    if plan.exit is None:
        return None
    exit_event = next(event for event in state.applied if event.kind is EventKind.REDEMPTION)
    charge = by_event[exit_event.sequence]
    nav = fund.nav_per_unit_on(declaration, holding, plan.exit.executed_on, plan.yield_rate)
    gain = _realised_gain(exit_event, state)
    at_a_loss = gain.amount < 0.0
    return ExitLine(
        executed_on=plan.exit.executed_on,
        settles_on=plan.exit.settles_on,
        cause=plan.exit.cause,
        nav_per_unit=nav,
        discount_rate=plan.exit.discount,
        gross_proceeds=exit_event.amount,
        discount_amount=money.scale_sourced(
            nav, holding.quantity * plan.exit.discount, declaration.spread.provenance
        ),
        realised_gain=gain,
        taxable_base=charge.taxable_base,
        realised_loss=money.scale(gain, -1.0) if at_a_loss else None,
        carryforward_note=CARRYFORWARD_NOT_MODELLED if at_a_loss else None,
        tax_class_id=charge.tax_class_id,
        rate_effective_from=_entry_for(tax_classes, charge, exit_event).effective_from,
        tax=charge.total,
    )


def _subtotals(
    state: LedgerState,
    charges: Sequence[TaxCharge],
    currency: Currency,
) -> tuple[ClassSubtotal, ...]:
    """Per-class subtotals: which class charged what, and on which kinds of income (FR-007).

    Sorted by class id so two runs of the same scenario produce the same order. Without
    this record the two-class split is invisible to a reader even when the ledger is right,
    which is the whole reporting requirement E1 turns on.
    """
    kind_of = {event.sequence: _taxable_kind(event.kind) for event in state.applied}
    by_class: dict[str, list[TaxCharge]] = {}
    kinds: dict[str, set[TaxableEventKind]] = {}
    for charge in charges:
        by_class.setdefault(charge.tax_class_id, []).append(charge)
        kind = kind_of.get(charge.event_sequence)
        if kind is not None:
            kinds.setdefault(charge.tax_class_id, set()).add(kind)
    return tuple(
        ClassSubtotal(
            tax_class_id=class_id,
            kinds=tuple(sorted(kinds.get(class_id, set()), key=lambda item: item.value)),
            pit=money.total([charge.pit for charge in grouped], currency),
            levy=money.total([charge.levy for charge in grouped], currency),
            total_charged=money.total([charge.total for charge in grouped], currency),
            charge_count=len(grouped),
            provenance=prov.merge_all(charge.provenance for charge in grouped),
        )
        for class_id, grouped in sorted(by_class.items())
    )


def _peg_statement(
    declaration: FundDeclaration,
    plan: ExecutionPlan,
    lines: Sequence[DistributionLine],
) -> str | None:
    """The peg and its cap, restated on every output that has one (FR-020).

    The whole point of owner decision A is that the currency exposure stays visible instead
    of being lost inside a hryvnia figure, so the statement names the peg, the assumed
    rate, the ceiling and **how often the ceiling bound**. A run where the cap bound every
    month is a run where the holder's dollar income stopped arriving in full, and a
    hryvnia total alone would not say so.
    """
    terms = declaration.distribution
    if terms is None or terms.peg is None or plan.exchange_rate is None:
        return None
    bound = sum(1 for line in lines if line.cap_bound)
    ceiling = fund.cap_on(terms.peg, declaration.terminates_on)
    ceiling_text = (
        "no ceiling is declared for the end of the fund's life"
        if ceiling is None
        else (
            f"the declared «граничний курс» in force at the fund's end is "
            f"{ceiling.uah_per_unit!r} {terms.paid_in.value} per "
            f"{terms.peg.sized_in.value}, effective {ceiling.effective_from.isoformat()}"
        )
    )
    return (
        f"income is sized in {terms.peg.sized_in.value} and paid in "
        f"{terms.paid_in.value}: {ceiling_text}, and every payment above was converted at "
        f"the lower of the owner's assumed {plan.exchange_rate.uah_per_unit!r} and that "
        f"ceiling. The ceiling bound {bound} of {len(lines)} payment(s) — where it binds, "
        "the hryvnia payment stops tracking the dollar and the peg is partially broken. "
        "This is a declared term, not a conversion licence: no amount here changed "
        "currency except through that stated sizing."
    )


def _rests_on(
    declaration: FundDeclaration,
    plan: ExecutionPlan,
    basis: DeclaredYield | ChosenPoint,
) -> tuple[str, ...]:
    """What this result depends on that is not an observation of a market (FR-004).

    Written out rather than left to a mark on a number, because the mark says *that* a
    figure is unverified and this says *what* the reader would have to check.
    """
    stated: list[str] = [
        f"{declaration.id!r} is assumption-driven: every figure is contractual arithmetic "
        "over terms the fund states about itself, not an observation of a market. No "
        "volatility, Sharpe or other statistical metric exists for it, and none can be "
        "requested",
        f"the {plan.liquidity_mode!r} liquidity terms were assumed, and the two modes "
        "differ by the declared spread, discount and settlement delay",
    ]
    match basis:
        case ChosenPoint():
            stated.append(
                f"the projected rate {basis.rate!r} is the owner's chosen point inside the "
                f"fund's stated range, not a figure the fund published: {basis.rationale}"
            )
        case DeclaredYield():
            stated.append(
                f"the projected rate {plan.yield_rate!r} is the fund's own stated "
                f"{basis.basis} figure, entered with its citation and an empty "
                "verification date — a term, not a promise and not a measurement"
            )
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(basis)
    if plan.liquidity_mode == "legal" and plan.exit is not None and plan.exit.cause == "requested":
        # FR-019's feasibility finding. Under the legal terms an early exit is the
        # manager's discretion and nothing else, so a plan that *needs* one to happen is
        # resting on someone else's decision. Executing it and saying nothing would be the
        # silent simulation the requirement forbids -- and the statement is here rather
        # than in a refusal because the exit is possible, just not owed.
        stated.append(
            f"the exit on {plan.exit.executed_on.isoformat()} is "
            f"{declaration.liquidity.legal.buyback_before_termination} under the legal "
            f"terms and is NOT guaranteed: it happens only if the manager chooses to buy "
            f"back, and this run assumed he does. The next exit the fund actually owes is "
            f"the termination payout on {declaration.terminates_on.isoformat()}. A plan "
            "that requires money out before then is resting on a discretion, not on a term"
        )
    if plan.exchange_rate is not None:
        stated.append(
            f"the exchange rate {plan.exchange_rate.uah_per_unit!r} is the owner's stated "
            f"assumption: {plan.exchange_rate.rationale}"
        )
    stated.extend(
        f"unanswered by the fund's primary documents, and not filled in: {task.question}"
        for task in declaration.verification_tasks
    )
    stated.extend(
        f"recorded as context for the declared yield, and not modelled as a flow: {fee.what}"
        for fee in declaration.fee_context
    )
    return tuple(stated)


# ---------------------------------------------------------------------------
# Beside the hurdle rate
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BesideTheHurdle:
    """A fund's after-spread, after-tax outcome next to feature 001's tax-free benchmark.

    FR-025. The comparison exists because a fund-stated 25-29% next to a 15.5% exempt
    government bond is the exact place false precision does its damage, and the honest
    answer is arithmetic rather than a verdict: here is what survives the spread and the
    tax, here is what the benchmark pays, and here is everything the comparison leaves out.

    **The excluded terms are on the record's face, not in a footnote** (Principle VI). This
    compares an instrument against an instrument. The funding route in and the exit route
    out are the largest missing numbers, and naming them is what stops this being read as
    a decision.
    """

    instrument_id: str
    fund_net_simple_annual: float
    """Net profit over what was invested, over the holding's years. Simple, not
    compounded, because the fund states a simple rate and compounding one would report a
    figure it never claimed."""

    hurdle_nominal_ytm: float
    """Feature 001's benchmark: the tax-free yield every other option has to beat."""

    difference: float
    """``fund - hurdle``. Negative means the benchmark wins, which is a real outcome and
    is reported as plainly as the other one."""

    years: float
    """The holding period the fund figure is annualised over, by the fund's own day count."""

    excludes: tuple[str, ...]
    rests_on: tuple[str, ...]
    provenance: Provenance
    """The union of both sides' marks: an unverified fund term marks the comparison."""


def beside_hurdle(
    declaration: FundDeclaration,
    holding: Holding,
    projection: FundProjection,
    hurdle: HurdleRate,
) -> BesideTheHurdle | InconsistentTerms:
    """Put one fund projection beside one hurdle rate, with what it excludes attached.

    The fund figure is ``net profit / invested / years``: everything the holding returned
    after the spread and after tax, as a simple annual rate over the period actually held.
    Read off the projection's own ledger totals rather than recomputed, so it cannot
    disagree with the lines above it.

    Refuses where the holding has no measurable length -- a projection whose events all
    fall on one day annualises to a division by zero, and a large number produced that way
    would be the most confident figure in the output and the least meaningful.
    """
    invested = -_purchase_amount(projection)
    ends_on = _ends_on(projection)
    years = conventions.day_count(declaration.day_count)(holding.purchased_on, ends_on)
    if years <= 0.0 or invested <= 0.0:
        return InconsistentTerms(
            first_term="holding.purchased_on",
            second_term="the projection's last event",
            reason=(
                f"{declaration.id!r} was held from {holding.purchased_on.isoformat()} to "
                f"{ends_on.isoformat()} for {invested!r} — a period or an amount of zero. "
                "There is no annual rate for a holding of no length or no size, and "
                "producing one by dividing would put the most confident figure in the "
                "output where the least meaningful one belongs."
            ),
        )
    net = projection.net_proceeds.amount / invested / years
    return BesideTheHurdle(
        instrument_id=declaration.id,
        fund_net_simple_annual=net,
        hurdle_nominal_ytm=hurdle.nominal_ytm.value,
        difference=net - hurdle.nominal_ytm.value,
        years=years,
        excludes=projection.excludes,
        rests_on=projection.rests_on,
        provenance=prov.merge(projection.provenance, hurdle.provenance),
    )


def _purchase_amount(projection: FundProjection) -> float:
    """What the purchase cost, signed as the ledger holds it: negative, money going out."""
    for event in projection.ledger.applied:
        if event.kind is EventKind.PURCHASE:
            return event.amount.amount
    raise LedgerInvariantError(  # pragma: no cover -- every fund run opens with a purchase
        "a fund projection has no purchase event, so there is nothing it was measured "
        "against. Every run opens with one."
    )


def _ends_on(projection: FundProjection) -> date:
    """The date the last thing happened: the exit's settlement, or the last payout."""
    return max(event.occurred_on for event in projection.ledger.applied)
