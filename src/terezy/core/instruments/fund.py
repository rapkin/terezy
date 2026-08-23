"""A collective-investment fund as declared terms, and the arithmetic those terms fix.

The second instrument kind, beside :mod:`terezy.core.instruments.fixed_income`, and a very
different sort of thing. A bond's schedule is computed from a contract that says exactly
what it will pay; a fund's is computed from **what the fund says about itself**. Every
number reaching this module came out of a регламент, a проспект or a fund page, and the
whole design is shaped by that one fact.

**Four structural refusals, not four caveats.** Each of these is an absence in the types
rather than a warning in prose, because a caveat gets copied without its caveat:

* :attr:`FundDeclaration.is_assumption_driven` is ``Literal[True]``. There is no ``False``
  case in this feature, and no field anywhere on a fund result where a volatility or a
  Sharpe ratio could sit (research.md D10).
* :class:`DeclaredYield` carries a ``low`` and a ``high``. **There is no midpoint helper**
  in this module, and that absence is the requirement: the midpoint of a fund-stated
  range is the most seductive invented number in the feature, because it looks like
  arithmetic (research.md D11).
* :class:`VerificationTask` carries **no value field**. A record marked "unknown" is a
  record somebody fills in; a record with nowhere to put a number cannot be (research.md
  D8).
* There is **no field for a computed fee**. The management and performance fee facts live
  in :attr:`FundDeclaration.fee_context` as provenance for the declared yield, and nothing
  in this module accrues one (owner decision B, research.md D9).

**A pegged amount is not money.** The REIT's income is declared in USD-equivalent terms
while every hryvnia of it moves in hryvnia (owner decision A). :class:`PeggedAmount` is
therefore deliberately not a :class:`~terezy.core.primitives.money.Money`: it cannot be
added to one, cannot be summed with one, and becomes hryvnia only through
:func:`size_pegged_payment`, which demands an :class:`ExchangeRateAssumption` the owner
stated. The type refuses the conflation so that a reviewer does not have to catch it.

**What this module does not decide.** Whether a purchase is after the cutoff, whether a
buyback is available, whether a needed value is only a verification task -- every one of
those is a *typed refusal*, and they live in :mod:`terezy.core.results.fund` with the
projection that returns them. This module holds the declaration and the arithmetic its
terms fix; the run's outcome is the result layer's. The split is the same one
``fixed_income`` and ``results.project`` already draw, and it keeps the import direction
one-way.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Final, Literal

from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.primitives import conventions, money
from terezy.core.primitives import provenance as prov

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping

    from terezy.core.instruments.interface import Holding
    from terezy.core.primitives.currency import Currency
    from terezy.core.primitives.money import Money
    from terezy.core.primitives.provenance import Provenance
    from terezy.core.tax.interface import TaxableEventKind

COLLECTIVE_INVESTMENT_FUND: Final = "collective_investment_fund"
"""The declared ``class`` of a fund file. The only dispatch key; never the fund's ``id``."""

LiquidityMode = Literal["practice", "legal"]
"""Which set of liquidity terms a projection assumed.

**Required everywhere, with no default anywhere** (research.md D5). A default would make
the more optimistic reading the silent one: the practice mode is a revocable company
practice with an empty verification date, and defaulting to it would quietly promise
same-day liquidity at NAV that the регламент does not owe.
"""

BuybackAvailability = Literal["available", "unavailable"]
"""Whether the scenario assumes the manager exercises its discretionary buyback.

A closed pair rather than a bool, because it is an owner-stated assumption about someone
else's discretion and the output has to name which way it was stated.
"""

MONTHS_IN_YEAR: Final = 12


@dataclass(frozen=True, slots=True)
class DeclaredYield:
    """The rate the fund states about itself. A term, never a promise or an observation.

    Reported as a range, or projected at an explicitly declared point labelled the owner's
    assumption. A point rate declares ``low == high``; MilTech's 25-29% does not.
    """

    low: float
    """The bottom of the fund-stated range, as a fraction. ``0.25`` for 25%."""

    high: float
    """The top of it. Equal to :attr:`low` for a fund stating a single figure."""

    basis: Literal["simple_annual", "usd_equivalent_annual"]
    """How the rate is meant: simple annual in the unit currency, or annual on the unit's
    USD-equivalent value. The second is owner decision A's shape -- a hryvnia flow sized
    by a capped dollar peg -- and it is the reason a peg is a term rather than a rate."""

    provenance: Provenance
    """Fund-stated, ``verified_on`` empty. Every figure derived from the rate inherits
    the mark, which is the point of Principle I applied to a number a fund publishes
    about itself."""


@dataclass(frozen=True, slots=True)
class ChosenPoint:
    """One rate inside a fund-stated range, chosen by the owner and labelled as his.

    Exists so that a projection over a range can produce a single figure **without the
    engine picking one**. The label is not decoration: it is what stops the figure being
    read as something the fund said.
    """

    rate: float
    """The rate to project at. Must lie within the declared range; checked by the caller."""

    is_assumption: Literal[True]
    """Carried where an observation carries a source, on ``RegimeTransition``'s precedent."""

    rationale: str
    """Why this point, in the owner's own words. Non-empty."""


@dataclass(frozen=True, slots=True)
class CapEntry:
    """One dated value of a lease's «граничний курс» -- the ceiling on the pegged rate.

    Dated, because the ceiling is renegotiated: the known history is 2023 at 37.49 and
    2024 at 41.24 (research.md D8). Known-and-weak is not the same as absent, so this
    enters as declared-but-unverified data while the *current* values remain a
    verification task.
    """

    effective_from: date
    uah_per_unit: float
    """Hryvnia per one unit of the pegged currency. Strictly positive."""

    provenance: Provenance


@dataclass(frozen=True, slots=True)
class Peg:
    """The currency an amount is *sized* in, and the ceiling on the rate that sizes it."""

    sized_in: Currency
    """USD for the REIT. Never the currency anything is *paid* in -- see the module
    docstring: a pegged amount is a term, not money."""

    cap: tuple[CapEntry, ...]
    """The dated «граничний курс» ladder, oldest first. May be empty, which declares that
    no ceiling is known -- distinct from a ceiling of zero, which would size every payment
    at nothing."""


@dataclass(frozen=True, slots=True)
class PeggedAmount:
    """An amount denominated in the peg's currency, which is **not** money.

    The whole of owner decision A in one type. A USD-equivalent figure is a *term* of the
    lease, not a dollar anyone holds: nothing in this project can add it to a
    :class:`Money`, sum it with one, or convert it, because it is not one. It becomes
    hryvnia only through :func:`size_pegged_payment`, at a rate the owner stated and
    subject to the declared cap.
    """

    amount: float
    sized_in: Currency
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class ExchangeRateAssumption:
    """The owner's stated exchange rate. An assumption, and it says so.

    Required to size any pegged payment. Absent one the projection returns a typed
    degraded result naming exactly this input -- never an invented or implicit rate
    (FR-021).
    """

    uah_per_unit: float
    """Hryvnia per one unit of the pegged currency. Strictly positive."""

    is_assumption: Literal[True]
    rationale: str


@dataclass(frozen=True, slots=True)
class DistributionTerms:
    """What the fund declares it pays out, when, in what, and sized in what."""

    frequency: Literal["monthly"]
    basis_note: str
    """The declared basis in words -- "at least 90% of net rental profit". Declared, never
    computed: modelling the fund's own books from outside would be an assumption wearing
    the shape of a computation (owner decision B)."""

    record_day: Literal["last_day_of_month"]
    payment_day: int
    """Day of the following month by which the payment is made. 1-28."""

    paid_in: Currency
    peg: Peg | None
    """``None`` for a fund whose payouts are not pegged to another currency."""

    payout_share: float
    """The declared share of the yield that is **paid out**; the rest accretes to NAV.

    ``1.0`` for a fund that distributes everything it earns, which is what both Inzhur
    products' documents describe -- the REIT's target is stated as a *distribution* target,
    so none of it is modelled as NAV growth. That is the conservative reading and it is
    stated rather than assumed: a property portfolio may well revalue, and pretending to
    know by how much would be inventing the fund's balance sheet from outside.

    The field exists because the split is a real term rather than a constant: a fund
    retaining part of its return has a NAV that moves, and one formula covers both cases
    (see :func:`nav_per_unit_on`) where a special case for accumulation funds would not.
    """

    provenance: Provenance


@dataclass(frozen=True, slots=True)
class SpreadTerms:
    """The declared markup and discount around NAV: the access cost this feature models.

    Four numbers rather than two, because "up to 1%" and "what is actually being charged
    today" are different claims and the second is unverified. The legal terms guarantee
    only the maxima; the live settings are what the owner believes he pays.
    """

    entry_markup_max: float
    exit_discount_max: float
    live_entry_markup: float
    live_exit_discount: float
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class LegalTerms:
    """What the регламент owes -- which, before the termination date, is nothing.

    An early buyback is at the manager's discretion, at a discount up to the declared
    maximum, settled within the declared number of business days. Declared as its own
    record rather than as a mode flag on one set of terms, because this and
    :class:`ObservedPractice` are two different kinds of claim and only one of them is
    revocable.
    """

    buyback_before_termination: Literal["discretionary"]
    """Not ``"guaranteed"`` and not a bool: the one word that matters about the exit."""

    settlement_business_days: int
    note: str
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class ObservedPractice:
    """What the company currently does, which it may stop doing tomorrow."""

    settlement_business_days: int
    is_revocable: Literal[True]
    """Always. A practice that could not be withdrawn would be an obligation, and an
    obligation belongs in :class:`LegalTerms`."""

    note: str
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class LiquidityTerms:
    """Both readings of the same exit, kept distinguishable."""

    legal: LegalTerms
    practice: ObservedPractice


@dataclass(frozen=True, slots=True)
class FeeFact:
    """A researched fee term, recorded as **context for the declared yield**.

    Nothing computes from this. Owner decision B: the fund-stated rate is the instrument's
    declared net yield, and modelling the fund's internal profitability would mean
    inventing its books from the outside. The record exists so the reader can see what the
    declared rate is net *of*.
    """

    what: str
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class VerificationTask:
    """A question the primary documents did not answer. It holds no value, by design.

    A projection that would need one refuses by naming the task, which turns "I cannot
    compute this" into "go and read this document" -- the same move feature 003 makes with
    a missing route declaration.
    """

    question: str
    searched: str
    searched_on: date


@dataclass(frozen=True, slots=True)
class FundDeclaration:
    """One collective-investment fund, declared purely as data."""

    id: str
    name: str
    unit_currency: Currency
    """What units and NAV are denominated in. Hryvnia for both Inzhur funds, whatever the
    income is *sized* in."""

    is_assumption_driven: Literal[True]
    """Not a bool. This feature has no ``False`` case -- a fund whose terms are observed
    rather than stated is a different declaration and a different feature -- and a
    ``Literal`` says so where a bool would invite one (FR-004)."""

    nav_per_unit: Money
    """The declared net asset value of one unit, with its own citation.

    ⚙ **Not in data-model.md's table, and needed.** Every figure in a fund projection is a
    price times a number of units: the entry markup, the exit discount and the pegged
    distribution all size from NAV, so without it the spread FR-024 asks to be modelled
    carefully has nothing to be a percentage *of*. It is a declared, cited term like any
    other, and there is no NAV *series* -- that is out of scope, and a single declared
    figure is the honest shape of what the fund publishes.
    """

    day_count: str
    """A key of ``conventions.DAY_COUNT_FNS`` -- how the pro-rata accrual of an
    accumulation fund measures a year."""

    declared_yield: DeclaredYield
    distribution: DistributionTerms | None
    """``None`` for an accumulation fund. MilTech owes no dividend, and that is a declared
    fact rather than a missing field: nothing invents a distribution for it (FR-023)."""

    spread: SpreadTerms
    liquidity: LiquidityTerms
    minimum_units: float
    subscription_cutoff: date | None
    terminates_on: date
    """When the fund ends and its payout is due. Required: a fund with no termination date
    has no guaranteed exit, which is the fact FR-019 needs to be able to name."""

    tax_classes: Mapping[TaxableEventKind, str]
    """Event kind to declared class id -- 001's mapping, with two *different* values for
    the first time (FR-006). A distribution and a redemption of the same units are not
    taxed alike, and this is where that is declared rather than coded."""

    fee_context: tuple[FeeFact, ...]
    verification_tasks: tuple[VerificationTask, ...]


@dataclass(frozen=True, slots=True)
class ExitPlan:
    """A resolved exit: when it executes, when it settles, and why it happens at all.

    Built by the result layer once every refusal has been ruled out, so this module never
    has to decide whether an exit is *allowed* -- only what it pays.
    """

    executed_on: date
    settles_on: date
    """The date the proceeds are received, and therefore the date that selects the tax
    rate (spec.md, Assumptions). Stated rather than left implicit, because an exit whose
    settlement crosses an effective date must not be a silent choice."""

    cause: Literal["requested", "termination"]
    discount: float
    """The fraction of NAV given up. Zero is a real value, not an absence."""


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Everything a run resolved before any event existed. Data, and all of it stated."""

    liquidity_mode: LiquidityMode
    yield_rate: float
    """The rate this run projects at: the fund's point rate, or an owner-chosen point
    inside its range. Never a midpoint the engine picked."""

    entry_markup: float
    exit: ExitPlan | None
    """``None`` where the holding is still open at the horizon and the fund has not
    terminated. The holding stays open; nothing is liquidated because a run ended."""

    exchange_rate: ExchangeRateAssumption | None
    """Required whenever the distribution terms carry a peg; the result layer refuses
    before building a plan without one."""


def lot_id_for(holding: Holding) -> str:
    """The identity of the lot a purchase opens: instrument and settlement date.

    Derived rather than generated, exactly as ``fixed_income.lot_id_for`` is and for the
    same reason: a counter or a clock would break determinism (C4).
    """
    return f"{holding.instrument_id}@{holding.purchased_on.isoformat()}"


def tax_classes(declaration: FundDeclaration) -> Mapping[TaxableEventKind, str]:
    """Which declared class governs each kind of income this fund produces."""
    return declaration.tax_classes


def entry_markup_for(declaration: FundDeclaration, mode: LiquidityMode) -> float:
    """The markup a purchase pays under the assumed mode.

    The legal terms guarantee only a ceiling, so the legal mode charges the **maximum**:
    presenting the live setting as what the регламент allows would report a discretionary
    favour as a right. The practice mode charges the live setting, which is unverified and
    labelled so.
    """
    match mode:
        case "practice":
            return declaration.spread.live_entry_markup
        case "legal":
            return declaration.spread.entry_markup_max


def exit_discount_for(declaration: FundDeclaration, mode: LiquidityMode) -> float:
    """The discount an early exit gives up under the assumed mode. Same reasoning."""
    match mode:
        case "practice":
            return declaration.spread.live_exit_discount
        case "legal":
            return declaration.spread.exit_discount_max


def settlement_business_days_for(declaration: FundDeclaration, mode: LiquidityMode) -> int:
    """How long the proceeds take to arrive under the assumed mode."""
    match mode:
        case "practice":
            return declaration.liquidity.practice.settlement_business_days
        case "legal":
            return declaration.liquidity.legal.settlement_business_days


def settlement_date(executed_on: date, business_days: int) -> date:
    """``business_days`` business days after execution, weekends only.

    Public holidays are declared domain knowledge with a citation and belong in ``data/``,
    exactly as ``conventions._is_weekend`` records: until that data exists a settlement
    landing on a holiday is placed on the holiday, which is wrong in a stated, visible way
    rather than wrong from a calendar somebody remembered.

    Zero business days means same-day settlement, and it is a real declared value -- the
    observed practice settles the day the request is made.
    """
    if business_days < 0:
        raise ValueError(
            f"a settlement delay of {business_days} business days is not a delay. "
            "Refused rather than clamped to zero: a negative delay means a sign was lost."
        )
    settled = executed_on
    remaining = business_days
    while remaining > 0:
        settled += timedelta(days=1)
        if conventions.is_business_day(settled):
            remaining -= 1
    return settled


def nav_per_unit_on(
    declaration: FundDeclaration,
    holding: Holding,
    on_date: date,
    yield_rate: float,
) -> Money:
    """NAV per unit on a date: the declared NAV plus whatever share of the yield is retained.

    The whole of owner decision B's model, and it is deliberately small. There is no NAV
    series, no market price and no return model -- only what the fund states about itself,
    applied **pro rata and simply**:

        nav(t) = nav(0) x (1 + rate x retained_share x years(purchase, t))

    with ``years`` measured by the fund's own declared day count. Simple rather than
    compounded, because the funds state a *simple annual* rate and compounding one would
    report a number the fund never claimed.

    A fund that pays out everything it earns retains nothing and its NAV therefore does
    not move: that is not an assumption that property never revalues, it is the refusal to
    put a revaluation figure nobody published into a model.
    """
    years = conventions.day_count(declaration.day_count)(holding.purchased_on, on_date)
    return money.scale_sourced(
        declaration.nav_per_unit,
        1.0 + yield_rate * retained_share(declaration) * years,
        declaration.declared_yield.provenance,
    )


def retained_share(declaration: FundDeclaration) -> float:
    """The share of the declared yield that stays in the fund and moves NAV.

    ``1.0`` for an accumulation fund, which distributes nothing at all, and
    ``1 - payout_share`` for a distributing one. One formula rather than a branch on
    "is this an accumulation fund", because the two are the same arithmetic with a
    different declared share -- and a fund that pays out most of what it earns and retains
    the rest is an ordinary case rather than a third kind of thing.
    """
    if declaration.distribution is None:
        return 1.0
    return 1.0 - declaration.distribution.payout_share


def purchase_price_per_unit(declaration: FundDeclaration, plan: ExecutionPlan) -> Money:
    """NAV plus the declared entry markup. The price actually paid per unit."""
    return money.scale_sourced(
        declaration.nav_per_unit,
        1.0 + plan.entry_markup,
        declaration.spread.provenance,
    )


def exit_price_per_unit(declaration: FundDeclaration, nav: Money, discount: float) -> Money:
    """NAV less the declared discount. The price actually received per unit."""
    return money.scale_sourced(nav, 1.0 - discount, declaration.spread.provenance)


def cap_on(peg: Peg, on_date: date) -> CapEntry | None:
    """The «граничний курс» in force on a date, or ``None`` if the ladder starts later.

    ``None`` is not "no ceiling": it is "no ceiling is declared for this date", and the
    caller treats it as the pegged rate applying unbounded while saying so. Declaring a
    ceiling of zero would size every payment at nothing, which is why the two cannot be
    the same value.
    """
    for entry in reversed(peg.cap):
        if entry.effective_from <= on_date:
            return entry
    return None


def size_pegged_payment(
    pegged: PeggedAmount,
    assumption: ExchangeRateAssumption,
    ceiling: CapEntry | None,
    *,
    paid_in: Currency,
) -> tuple[Money, bool]:
    """Turn a pegged amount into hryvnia at the owner's stated rate, capped.

    Returns the amount and **whether the cap bound**, because the second is a fact the
    output has to state: a peg that partially breaks under fast devaluation is exactly the
    exposure owner decision A exists to keep visible, and a hryvnia figure alone hides it.

    The rate applied is ``min(assumed, cap)``. That is what a «граничний курс» *is* -- the
    lease converts at the market rate until the ceiling, and at the ceiling thereafter --
    so above the cap the hryvnia payment stops tracking the dollar and the holder starts
    losing real income.

    This is the only place in the fund path where a pegged term becomes money, and it
    demands the assumption in its signature so that it cannot happen without one.
    ``paid_in`` is an argument rather than something read off ``pegged``: a pegged amount
    knows what it is *sized* in and deliberately does not know what it is *paid* in, which
    is the distinction owner decision A turns on.
    """
    applied = assumption.uah_per_unit
    bound = False
    if ceiling is not None and ceiling.uah_per_unit < applied:
        applied = ceiling.uah_per_unit
        bound = True
    sources = prov.merge(
        pegged.provenance,
        prov.EMPTY if ceiling is None else ceiling.provenance,
    )
    return (
        money.from_pegged_term(
            pegged.amount,
            sized_in=pegged.sized_in,
            paid_in=paid_in,
            rate=applied,
            sources=sources,
        ),
        bound,
    )


def distribution_dates(
    terms: DistributionTerms,
    holding: Holding,
    until: date,
) -> tuple[tuple[date, date], ...]:
    """``(record date, payment date)`` for every distribution due up to ``until``.

    The record date is the last day of a month and the payment date is the declared day of
    the month after it, which is what the REIT's terms say. The first month counted is the
    one **after** the purchase settles: the fund's documents state no pro-rating rule for a
    part month, so none is invented -- a part month simply does not pay, which is stated
    here and in ``docs/METHODOLOGY.md`` rather than quietly assumed either way.
    """
    due: list[tuple[date, date]] = []
    year, month = holding.purchased_on.year, holding.purchased_on.month
    while True:
        year, month = (year + 1, 1) if month == MONTHS_IN_YEAR else (year, month + 1)
        record = _last_day_of(year, month)
        pay_year, pay_month = (year + 1, 1) if month == MONTHS_IN_YEAR else (year, month + 1)
        payment = date(pay_year, pay_month, terms.payment_day)
        if payment > until:
            return tuple(due)
        due.append((record, payment))


def _last_day_of(year: int, month: int) -> date:
    """The last calendar day of a month, without a calendar table."""
    first_of_next = date(year + 1, 1, 1) if month == MONTHS_IN_YEAR else date(year, month + 1, 1)
    return first_of_next - timedelta(days=1)


def monthly_yield_fraction(plan: ExecutionPlan, payout_share: float) -> float:
    """One period's declared yield per unit of NAV, as a fraction.

    Monthly, so one twelfth of the **paid-out** part of the annual rate. A fraction rather
    than an amount because what it multiplies depends on the peg: for an unpegged fund it
    scales NAV directly, and for a pegged one it scales the unit's value *in the peg's
    currency* first.

    Applied to the fund's **declared** NAV rather than to the accreted NAV of the month in
    question. That is what "simple pro-rata contractual arithmetic over the declared net
    yield" means (FR-023): the fund states an annual rate on NAV, not a compounding one,
    and letting each payout grow off the last would report a compounding the fund never
    claimed.
    """
    return plan.yield_rate * payout_share / MONTHS_IN_YEAR


def purchase_event(
    declaration: FundDeclaration,
    holding: Holding,
    plan: ExecutionPlan,
    *,
    sequence: int,
) -> Event:
    """Cash out, units in, at NAV plus the declared markup."""
    price = purchase_price_per_unit(declaration, plan)
    return Event(
        sequence=sequence,
        occurred_on=holding.purchased_on,
        kind=EventKind.PURCHASE,
        amount=money.scale(price, -holding.quantity),
        owner_id=holding.owner_id,
        caused_by=CausationRef(
            kind=CausationKind.INSTRUMENT_TERM,
            id=f"{declaration.id}:purchase",
            detail=(
                f"purchase of {holding.quantity} unit(s) of {declaration.name!r} at NAV "
                f"{declaration.nav_per_unit.amount!r} plus the declared entry markup of "
                f"{plan.entry_markup!r} ({plan.liquidity_mode} terms)"
            ),
        ),
        lot_ref=LotRef(instrument_id=declaration.id, lot_id=lot_id_for(holding)),
        quantity=holding.quantity,
        allocated_to=None,
        capacity_pool=None,
    )


def exit_event(
    declaration: FundDeclaration,
    holding: Holding,
    plan: ExecutionPlan,
    exit_plan: ExitPlan,
    *,
    sequence: int,
) -> Event:
    """Cash in, units out, at NAV less the declared discount, dated at settlement."""
    nav = nav_per_unit_on(declaration, holding, exit_plan.executed_on, plan.yield_rate)
    price = exit_price_per_unit(declaration, nav, exit_plan.discount)
    cause = (
        "the fund's declared termination date"
        if exit_plan.cause == "termination"
        else f"a redemption requested for {exit_plan.executed_on.isoformat()}"
    )
    return Event(
        sequence=sequence,
        occurred_on=exit_plan.settles_on,
        kind=EventKind.REDEMPTION,
        amount=money.scale(price, holding.quantity),
        owner_id=holding.owner_id,
        caused_by=CausationRef(
            kind=CausationKind.INSTRUMENT_TERM,
            id=f"{declaration.id}:exit",
            detail=(
                f"{cause}: {holding.quantity} unit(s) at NAV {nav.amount!r} less the "
                f"declared discount of {exit_plan.discount!r}, settled "
                f"{exit_plan.settles_on.isoformat()} under the {plan.liquidity_mode} "
                "terms — the date the proceeds are received, which is the date that "
                "selects the tax rate"
            ),
        ),
        lot_ref=LotRef(instrument_id=declaration.id, lot_id=None),
        quantity=holding.quantity,
        allocated_to=None,
        capacity_pool=None,
    )


def distribution_event(
    declaration: FundDeclaration,
    holding: Holding,
    amount: Money,
    *,
    record_on: date,
    paid_on: date,
    sequence: int,
) -> Event:
    """One declared payout, dated when it is paid rather than when it is earned."""
    return Event(
        sequence=sequence,
        occurred_on=paid_on,
        kind=EventKind.DISTRIBUTION,
        amount=amount,
        owner_id=holding.owner_id,
        caused_by=CausationRef(
            kind=CausationKind.INSTRUMENT_TERM,
            id=f"{declaration.id}:distribution",
            detail=(
                f"declared distribution on {holding.quantity} unit(s) of "
                f"{declaration.name!r}, recorded {record_on.isoformat()} and paid "
                f"{paid_on.isoformat()} — the fund-stated yield applied pro rata, not an "
                "observation of what the fund earned"
            ),
        ),
        lot_ref=None,
        quantity=None,
        allocated_to=None,
        capacity_pool=None,
    )
