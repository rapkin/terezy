"""The join: an instrument bought through a route from a stream, and what comes back.

Every term comes from the call that owns it -- the way in from
:func:`terezy.core.routes.cost.cost_one`, the holding and its tax from its own projection,
each release's way home from ``cost_exit`` -- and **this module computes nothing of its own
beyond summing what they return** (research.md D1). Its only original content is the chaining
rule and the refusals, and that is where it can be wrong.

## The three seams, and why all of them are anchored

    the tuple's stream == the stream the way in is costed from
    stream --[ way in ]--> (venue, currency) == where the purchase happens
    where the proceeds land == (venue, currency) --[ way out ]--> a spendable endpoint

All three are checked -- both halves of the two positional ones, the venue **and** the
currency -- and a mismatch is a typed refusal naming both sides. Bridging one would be an
invented leg at an invented rate: feature 004 shipped an exit chain anchored at neither end,
and money moving between venues for free still read as a coherent three-hop journey. The
first seam is the easiest to miss because it has no venue in it -- the way in is costed from
the *candidate's* stream and everything else reads the *tuple's*, so two strings hold one fact.

## What travels the way out, and why it is a series

What goes home is whatever the holding released, **on the date it released it**, charged what
the declared way out charges. A fixed fee does not scale, so applying a round-trip *fraction*
to a coupon would be a fabricated figure that looks exactly like a real one. The remainder the
purchase could not deploy travels the same way out, on the purchase date (owner decision,
2026-09-06); it never became a position, which is what fixes its date and makes it untaxed.
"No reinvestment" (FR-025) is then structural rather than a rule to remember: money that
reaches a spendable endpoint has left the model.

## The rate, and where it refuses

The comparable figure is a money-weighted return over the tuple's **actual span**, from the
first outlay to the last arrival, with ramp and settlement latency inside it because waiting
is a cost (FR-015, owner decision 2026-08-22). It is
:func:`terezy.core.results.hurdle.internal_rate_of_return`, the same root find that produces
feature 001's benchmark, which is what makes hurdle-versus-tuple one kind of number.

**It refuses where those amounts are not all in one currency**, and that is reachable in the
shipped registry. Valuing one in the other needs a rate that values a currency **for a
return**, and nothing declares one: a channel rate is a transaction price and the official
rate is a legal reference for what an income was worth. The **amount** is reported and the
**rate** is a typed absence naming what is missing.

## No clock

``horizon.start`` is when the money leaves the stream; the purchase happens the way in's
declared latency later; every other date comes from a declaration or from the projection.
``as_of`` decides staleness only. Neither is read from a clock, and there may never be one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Final, Literal, assert_never

from terezy.core.errors import InconsistentTerms, LedgerInvariantError
from terezy.core.inflation import series as cpi_series
from terezy.core.inflation.series import CpiSeries, InflationAssumption
from terezy.core.instruments import accrual
from terezy.core.instruments import cash as cash_terms
from terezy.core.instruments import fund as fund_terms
from terezy.core.instruments import registry as instrument_registry
from terezy.core.instruments import terms as instrument_terms
from terezy.core.instruments.accrual import Carried
from terezy.core.instruments.cash import CashAssumptions, CashDeclaration
from terezy.core.instruments.fund import FundDeclaration
from terezy.core.instruments.held import HeldAssetDeclaration
from terezy.core.instruments.interface import (
    Assumptions,
    DateRange,
    EarlyExit,
    Holding,
    InstrumentDeclaration,
)
from terezy.core.ledger.events import EventKind
from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives import staleness as stale
from terezy.core.primitives.conventions import day_count
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.rates import NominalRate
from terezy.core.primitives.staleness import Ageing
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import canonical, card
from terezy.core.results import cash as cash_results
from terezy.core.results import fund as fund_results
from terezy.core.results import hurdle as hurdle_figures
from terezy.core.results import project as bond_results
from terezy.core.results.card import CandidateProjection
from terezy.core.results.cash import CashProjection
from terezy.core.results.fund import FundAssumptions, FundProjection, RangeProjection
from terezy.core.results.hurdle import CashFlow, internal_rate_of_return
from terezy.core.results.project import Projection
from terezy.core.results.ramp import (
    ExitCostUnknown,
    OneWayCost,
    RouteUnusable,
    WayOutCost,
)
from terezy.core.results.tuple import (
    ACCOUNTS_FOR,
    EXCLUDES,
    Arrival,
    BelowMinimumTicket,
    BuysNoWholeUnit,
    CannotSpanHorizon,
    ContinuationAssumption,
    DeclarationMissing,
    FundedFromAnotherStream,
    InstrumentDemandsCash,
    InstrumentPlan,
    InstrumentRefused,
    NoExitRouteDeclared,
    NoExitTermsDeclared,
    Part,
    PartContribution,
    PlanDoesNotFitInstrument,
    RateNotComparable,
    RemainderCameHome,
    RemainderStayed,
    RouteInCapExceeded,
    RouteInUnusable,
    RouteStanding,
    SeamDoesNotChain,
    TaxCurrencyConversionUnavailable,
    Tuple,
    TupleOutcome,
    TupleRefused,
    TwoFiguresNotOne,
    UndeployedCash,
    WayOutCapExceeded,
    WayOutUnusable,
    money_home,
)
from terezy.core.routes import cost
from terezy.core.routes.cost import Junction
from terezy.core.routes.legs import RouteStatus
from terezy.core.routes.path import (
    EXIT_BY_IDENTITY,
    IDENTITY_ENTRY_ID,
    Candidate,
    DeclaredExit,
    EntryByIdentity,
    EntryPath,
    ExitByIdentity,
    ExitChain,
    ExitChoice,
    FromTheDeclaration,
    entry_segments_of,
    exit_segments_of,
)
from terezy.core.scenarios import quotation
from terezy.core.scenarios.quotation import QuotationHolds
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxClass

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping

    from terezy.core.instruments.access import InstrumentAccess
    from terezy.core.primitives.staleness import ObservationKind
    from terezy.core.results.coverage import SpendableEndpoint
    from terezy.core.routes.channels import FxChannel
    from terezy.core.routes.legs import Route
    from terezy.core.streams.streams import IncomeStream

Declared = InstrumentDeclaration | FundDeclaration | CashDeclaration
"""The declaration kinds a tuple can name, matched with ``match``.

The join dispatches on a declaration **kind** because the projections return different
shapes; never on an instrument id, which ``tests/contract/test_h1_data_only.py`` scans for.
"""

Projected = Projection | FundProjection | CashProjection
"""What a projection returns, whichever kind produced it."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Registries:
    """Every declared set the join reads, in one pure record.

    Passed in rather than loaded: loading is the ``data`` layer's job, and the core must be
    testable with no file on disk anywhere near the arithmetic.
    """

    instruments: Mapping[str, InstrumentDeclaration]
    funds: Mapping[str, FundDeclaration]
    cash: Mapping[str, CashDeclaration]
    """Declared cash balances by id.

    A third mapping rather than a widened first: an id in neither existing map was skipped by
    enumeration with **no refusal at all**, so a declared balance disappeared from the
    comparison silently (023 FR-008a).
    """

    held: Mapping[str, HeldAssetDeclaration]
    """Assets held for their price alone (025 FR-009). Empty is ordinary.

    Never a candidate, unlike a balance: a tuple requires a way in, and a held position was not
    funded through a declared corridor. It is here because the group vocabulary and the subject
    resolution read every declared id, and a held asset a question names must not resolve to
    nothing.
    """

    tax_classes: Mapping[str, TaxClass]
    access: Mapping[str, InstrumentAccess]
    routes: Mapping[str, Route]
    channels: Mapping[str, FxChannel]
    streams: Mapping[str, IncomeStream]
    kinds: Mapping[str, ObservationKind]
    spendable: frozenset[SpendableEndpoint]

    cpi: Mapping[str, CpiSeries]
    """Every CPI series this run declares, by declared id. Empty when it declares none.

    No default: an absent deflator is a *reported reason* rather than an error (024 FR-013).
    """

    inflation: InflationAssumption | None
    """The declared future-inflation belief, or ``None`` when this run was given none.

    Required with no default: a caller that could omit it would produce an answer whose
    assumed real figures are all unavailable, and no record of whether that was the data or
    the call.
    """

    quotation_holds: QuotationHolds
    """The owner's declared belief about what a future early exit is struck at.

    On the registries rather than on the question, because it is not a property of one
    question: two questions asked on one day must not be able to disagree about how a
    platform's quote behaves (015 FR-032). Required with no default -- a default here would be
    the invented number the declaration exists to prevent.
    """

    base_currency: Currency
    """The currency tax is assessed in (Principle VI's tax role).

    Read for exactly one thing: refusing a taxable instrument declared in another currency.
    Not for want of an official rate -- feature 011 built that -- but because the projection
    below holds a holding under one currency and sums its charges in it.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class Evaluated:
    """One tuple's outcome and the projection it was read off (027 FR-001).

    A **return value** rather than a field on the outcome: a field on that record would be on
    the wire in every response carrying one.
    """

    outcome: TupleOutcome
    projection: CandidateProjection


def outcome_of(result: Evaluated | TupleRefused) -> TupleOutcome | TupleRefused:
    """The half a caller that does not want the projection reads.

    One named place, so *the projection is discarded here* is a fact about the call rather
    than a line a reader has to notice in each caller.
    """
    return result.outcome if isinstance(result, Evaluated) else result


def evaluate(
    tuple_: Tuple,
    *,
    amount: Money,
    horizon: DateRange,
    as_of: date,
    continuation: ContinuationAssumption,
    registries: Registries,
) -> Evaluated | TupleRefused:
    """Evaluate one tuple end to end, or say precisely why there is no outcome.

    Pure: no clock, no I/O, no state. ``amount`` leaves the stream on ``horizon.start`` and
    must be in the stream's currency; ``as_of`` decides staleness and nothing else;
    ``continuation`` is required with no default, because FR-025 forbids defaulting what an
    instrument terminating before the horizon does with its proceeds.

    The **first** problem found is the one reported. Raises only for a caller's construction
    error; every fact about the *money* is a returned value.
    """
    prepared = _prepare(tuple_, registries)
    if not isinstance(prepared, _Prepared):
        return prepared
    routed = _route_in(
        tuple_, prepared, amount=amount, horizon=horizon, as_of=as_of, registries=registries
    )
    if not isinstance(routed, _Routed):
        return routed
    return _hold(
        tuple_,
        prepared,
        routed,
        amount=amount,
        horizon=horizon,
        as_of=as_of,
        continuation=continuation,
        registries=registries,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class _Routed:
    """The way in, costed, with both venue seams checked and the way out resolved.

    A private carrier, so that "both venue seams were anchored before anything was bought" is
    a fact about the control flow rather than a rule spread over one long function.
    """

    one_way: OneWayCost
    latency_days: int
    status: RouteStatus
    """The way in's declared status. Carried rather than re-derived: ``cost_one`` already
    took the most constrained of the chain's segments, and a second reading of the same
    declarations is a second answer waiting to disagree."""

    disruption: float
    """The way in's largest single-leg disruption probability, from the same figure."""

    proceeds_at: Junction
    chain: ExitChain


def _route_in(
    tuple_: Tuple,
    prepared: _Prepared,
    *,
    amount: Money,
    horizon: DateRange,
    as_of: date,
    registries: Registries,
) -> _Routed | TupleRefused:
    """Cost the way in, check both venue seams, and resolve the way out. Nothing is bought yet.

    **``cost_one``'s own round-trip figure is deliberately unused.** This tuple's way out
    starts where the *instrument* releases its proceeds, which is not in general where the
    inbound chain ended, so that figure is about a different journey.
    """
    entry = tuple_.route_in
    if isinstance(entry, EntryByIdentity):
        seam = _identity_way_in(prepared)
        if seam is not None:
            return seam
        # No cap check, and its absence is the entry rather than an omission: a ceiling is a
        # term of a declared leg and this way in walks none, so there is no rail to exceed.
        costed = _Costed(
            one_way=cost.cost_entry(entry, amount, stream=prepared.stream),
            latency_days=0,
            status="open",
            disruption=0.0,
        )
    else:
        priced = cost.cost_one(
            entry,
            amount,
            routes=registries.routes,
            channels=registries.channels,
            streams=registries.streams,
            kinds=registries.kinds,
            on_date=horizon.start,
            as_of=as_of,
            spendable=registries.spendable,
        )
        if isinstance(priced, RouteUnusable):
            return RouteInUnusable(
                refused=priced,
                reason=(
                    f"the way in to {prepared.access.bought_at!r} will not carry "
                    f"{amount.amount!r} {amount.currency.value} on "
                    f"{horizon.start.isoformat()}: {priced.reason}"
                ),
            )
        seam_in = _seam_in(entry, prepared, priced.one_way.arrived)
        if seam_in is not None:
            return seam_in
        # After the seam, not before: a seam mismatch says the tuple is impossible at **any**
        # amount in any month, while a cap says it is impossible at *this* amount *this*
        # month. Reporting the cap first hands the owner a remedy that reads as actionable,
        # and sending less would then reveal a seam the first refusal had concealed.
        capped = _over_the_monthly_cap(entry, priced.ceiling, amount)
        if capped is not None:
            return capped
        costed = _Costed(
            one_way=priced.one_way,
            latency_days=priced.latency_days,
            status=priced.status,
            disruption=priced.disruption_probability,
        )
    proceeds_at: Junction = (prepared.access.proceeds_to, prepared.currency.value)
    way_out = _way_out_chain(tuple_, prepared, proceeds_at, registries)
    if not isinstance(way_out, ExitChain):
        return way_out
    return _Routed(
        one_way=costed.one_way,
        latency_days=costed.latency_days,
        status=costed.status,
        disruption=costed.disruption,
        proceeds_at=proceeds_at,
        chain=way_out,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class _Costed:
    """What a way in costs, from whichever of the two kinds of way in it is.

    Gathered so the identity branch and the routed one meet at one point instead of building a
    `_Routed` each -- which is where the two would come to disagree.
    """

    one_way: OneWayCost
    latency_days: int
    status: RouteStatus
    disruption: float


def _identity_way_in(prepared: _Prepared) -> SeamDoesNotChain | None:
    """*There is nothing to do* is a claim about where the money is, and it is checked (FR-013).

    **Both halves come from declarations, and the currency half is the one that matters**: the
    amount the caller chose to move says nothing about what the stream delivers, so comparing
    it here would pass a dollar stream against a hryvnia instrument -- an undeclared
    conversion, charged nothing, on the one branch where no walk exists to refuse it.
    """
    left: Junction = (prepared.stream.arrives_at, prepared.stream.amount.currency.value)
    right: Junction = (prepared.access.bought_at, prepared.currency.value)
    if left == right:
        return None
    return SeamDoesNotChain(
        seam="route_in_to_purchase",
        left=f"{left[0]}/{left[1]}",
        right=f"{right[0]}/{right[1]}",
        reason=(
            f"there is said to be nothing to do because {prepared.stream.id!r} already "
            f"arrives as {left[1]} at {left[0]!r}, and {prepared.declared.id!r} is bought as "
            f"{right[1]} at {right[0]!r}. The two do not meet, so the purchase would be made "
            "with money that is somewhere else: what an entry by identity claims is that no "
            "corridor is needed, and where one is needed it has to be declared and costed "
            "rather than assumed free (FR-013)."
        ),
    )


def _over_the_monthly_cap(
    path: Candidate, ceiling: Money | None, amount: Money
) -> RouteInCapExceeded | None:
    """Refuse an amount larger than the tightest monthly cap the way in declares (FR-016).

    ``cost_one`` reports the ceiling rather than refusing, which is right one layer down: what
    to do with the excess is the owner's declared fallback (``routes.capacity``). A tuple has
    nowhere to put an excess -- an acquisition is one dated purchase event (FR-018) -- and
    reading the ceiling nowhere let a 5 000.00 cap deploy 10 000.00 and report ten units.
    """
    if ceiling is None or money.compare(amount, ceiling) <= 0:
        return None
    return RouteInCapExceeded(
        path=path,
        ceiling=ceiling,
        requested=amount,
        excess=money.sub(amount, ceiling),
        reason=(
            f"the way in declares a monthly ceiling of {ceiling.amount!r} "
            f"{ceiling.currency.value} and {amount.amount!r} was asked for, so "
            f"{money.sub(amount, ceiling).amount!r} of it cannot pass this month. The tuple "
            "is refused rather than deployed up to the ceiling: partial deployment is "
            "deferred (FR-018, owner decision 2026-08-22), and reporting the excess needs a "
            "declared fallback policy and the month's consumed capacity, neither of which a "
            "tuple carries. Choosing one here would execute a plan the owner did not write. "
            "Send at most the ceiling, or declare the staggered entry a later feature brings."
        ),
    )


def _hold(
    tuple_: Tuple,
    prepared: _Prepared,
    routed: _Routed,
    *,
    amount: Money,
    horizon: DateRange,
    as_of: date,
    continuation: ContinuationAssumption,
    registries: Registries,
) -> Evaluated | TupleRefused:
    """Buy with what arrived, live the declared lifecycle, and send every release home."""
    purchased_on = horizon.start + timedelta(days=routed.latency_days)
    bought = _acquire(prepared, tuple_.route_in, routed.one_way.arrived, purchased_on=purchased_on)
    if not isinstance(bought, _Acquisition):
        return bought
    projected = _project(
        prepared,
        bought,
        purchased_on=purchased_on,
        horizon=horizon,
        tax_classes=registries.tax_classes,
        registries=registries,
    )
    if not isinstance(projected, Projection | FundProjection | CashProjection):
        return projected
    repatriated = _repatriate(
        tuple_, prepared, projected, routed=routed, as_of=as_of, registries=registries
    )
    if not isinstance(repatriated, tuple):
        return repatriated
    undeployed, remainder_cost = _send_the_remainder_home(
        tuple_,
        prepared,
        bought.remainder,
        routed=routed,
        purchased_on=purchased_on,
        as_of=as_of,
        registries=registries,
    )
    charges = _charges_of(projected)
    return _assemble(
        tuple_,
        prepared,
        projected,
        projection=CandidateProjection(
            projection_key=canonical.candidate_key(tuple_, horizon),
            instrument_id=prepared.declared.id,
            arm=card.arm_of(projected),
            flows=card.flows_of(
                projected.ledger, charges, conventions=card.conventions_of(projected)
            ),
            charges=charges,
            purchase=card.Purchase(
                purchased_on=purchased_on,
                quantity=bought.quantity,
                price_per_unit=bought.price,
                paid=bought.cost,
                carried=bought.carried if bought.carried is not None else _NO_CARRY,
            ),
            way_in=card.WayIn(one_way=routed.one_way, latency_days=routed.latency_days),
            releases=card.releases_of(repatriated),
            remainder_way_out=remainder_cost
            if remainder_cost is not None
            else card.REMAINDER_STAYED,
        ),
        outlay=amount,
        one_way=routed.one_way,
        arrivals=tuple(arrival for arrival, _ in repatriated),
        way_out_costs=tuple(charged for _, charged in repatriated)
        + ((remainder_cost,) if remainder_cost is not None else ()),
        endpoint_currency=_endpoint_currency(routed.chain, prepared, registries),
        undeployed=undeployed,
        routed=routed,
        horizon=horizon,
        purchased_on=purchased_on,
        continuation=continuation,
        quotation_holds=registries.quotation_holds,
        kinds=registries.kinds,
        cpi=registries.cpi,
        inflation=registries.inflation,
        as_of=as_of,
    )


# ---------------------------------------------------------------------------
# Resolving the declarations
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class _Prepared:
    """The declarations one tuple names, resolved and checked against each other.

    A private carrier, not a result: the resolution happens once, in one order, so the
    functions below cannot be handed an access declaration for one instrument and a currency
    from another.
    """

    declared: Declared
    access: InstrumentAccess
    currency: Currency
    plan: InstrumentPlan
    stream: IncomeStream


def _instrument_side(
    tuple_: Tuple, registries: Registries
) -> tuple[Declared, InstrumentAccess, Currency] | TupleRefused:
    """The instrument, how it is reached, and what it trades in -- or the first thing missing."""
    declared = _declaration(tuple_.instrument_id, registries)
    if isinstance(declared, DeclarationMissing):
        return declared
    access = registries.access.get(tuple_.instrument_id)
    if access is None:
        return DeclarationMissing(
            part="access",
            what=f"an [[access]] entry for {tuple_.instrument_id!r}",
            reason=(
                f"nothing declares where {tuple_.instrument_id!r} is bought or where its "
                "proceeds land, so neither seam of the round trip can be anchored. It is "
                "refused rather than checked on currency alone: a way in that ends in the "
                "right currency at the wrong venue is money teleporting between venues for "
                "free, and the record would still read as a coherent journey (FR-004)."
            ),
        )
    currency = currency_of(declared)
    unresolved = _unresolved_class(declared, registries.tax_classes)
    if unresolved is not None:
        return unresolved
    foreign = _foreign_tax_currency(declared, currency, registries.base_currency)
    if foreign is not None:
        return foreign
    return declared, access, currency


def _prepare(tuple_: Tuple, registries: Registries) -> _Prepared | TupleRefused:
    """Every declaration this tuple rests on, or the first one that is missing or wrong."""
    side = _instrument_side(tuple_, registries)
    if not isinstance(side, tuple):
        return side
    declared, access, currency = side
    plan = _plan_for(declared, tuple_.exit_terms)
    if isinstance(plan, PlanDoesNotFitInstrument):
        return plan
    stream = registries.streams.get(tuple_.stream_id)
    if stream is None:
        return DeclarationMissing(
            part="route_in",
            what=f"income stream {tuple_.stream_id!r}",
            reason=(
                f"no declared stream is named {tuple_.stream_id!r}, and which stream funds a "
                "purchase is part of what a cost *is* (Principle VI). Known streams: "
                f"{sorted(registries.streams)}."
            ),
        )
    entry = tuple_.route_in
    # An identity entry names no stream and so cannot name another one: the money that funds
    # the purchase is the money that already arrived, in the stream the tuple names.
    if not isinstance(entry, EntryByIdentity) and entry.stream_id != tuple_.stream_id:
        return FundedFromAnotherStream(
            tuple_stream_id=tuple_.stream_id,
            route_stream_id=entry.stream_id,
            reason=(
                f"this tuple says it is funded from {tuple_.stream_id!r}, and its way in is "
                f"costed from {entry.stream_id!r}. Which income pays for a purchase "
                "is part of what the cost *is* (Principle VI), so the two cannot differ: the "
                "figures would be a ramp from one stream reported under the key of another, "
                "and both halves would look entirely reasonable. Neither is preferred over "
                "the other, because guessing which the caller meant would either re-cost a "
                "way in nobody named or rewrite the key the comparison is built on."
            ),
        )
    unknown = [name for name in entry_segments_of(entry) if name not in registries.routes]
    if unknown:
        return DeclarationMissing(
            part="route_in",
            what=f"route(s) {sorted(unknown)}",
            reason=(
                f"the way in names {sorted(unknown)}, which no declaration under routes/ "
                "declares. A candidate is built from declared routes, and a name that does "
                "not resolve is a way in nobody has costed rather than a free one."
            ),
        )
    return _Prepared(declared=declared, access=access, currency=currency, plan=plan, stream=stream)


def _declaration(instrument_id: str, registries: Registries) -> Declared | DeclarationMissing:
    """The declaration an id names, of whichever kind, or a refusal listing what is declared."""
    fund = registries.funds.get(instrument_id)
    if fund is not None:
        return fund
    balance = registries.cash.get(instrument_id)
    if balance is not None:
        return balance
    bond = registries.instruments.get(instrument_id)
    if bond is not None:
        return bond
    return DeclarationMissing(
        part="instrument",
        what=f"instrument {instrument_id!r}",
        reason=(
            f"no declaration under instruments/ declares {instrument_id!r}. Declared: "
            f"{sorted([*registries.instruments, *registries.funds, *registries.cash])}."
        ),
    )


def currency_of(declared: Declared) -> Currency:
    """What the instrument trades and pays in, from whichever declaration kind it is.

    Public because feature 014 anchors an enumeration's two ``Destination`` records on it, and
    *which field of which declaration kind holds the currency* is one fact.
    """
    match declared:
        case InstrumentDeclaration() | CashDeclaration():
            return declared.currency
        case FundDeclaration():
            return declared.unit_currency
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(declared)


def _tax_classes_of(declared: Declared) -> Mapping[TaxableEventKind, str]:
    """Which declared class governs each kind of income this instrument pays.

    Empty for a balance, and that is the declaration's answer rather than an omitted field
    (FR-009): a release returns the basis, so there is nothing for a class to charge.
    """
    match declared:
        case InstrumentDeclaration() | FundDeclaration():
            return declared.tax_classes
        case CashDeclaration():
            return {}
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(declared)


def _unresolved_class(
    declared: Declared, tax_classes: Mapping[str, TaxClass]
) -> DeclarationMissing | None:
    """Every tax class the instrument names must be declared (FR-020).

    Checked here rather than left to the projection, which would report it as an instrument
    failure: FR-006 wants the part named, so the remedy is a file in ``data/tax/``.
    """
    missing = sorted(
        {class_id for class_id in _tax_classes_of(declared).values() if class_id not in tax_classes}
    )
    if not missing:
        return None
    return DeclarationMissing(
        part="tax_class",
        what=f"tax class(es) {missing}",
        reason=(
            f"{declared.id!r} taxes its income under {missing}, which no declared "
            "jurisdiction contains. The tuple is refused rather than projected untaxed: "
            "'no rule was found' and 'the rule charged nothing' are opposite claims and "
            f"only one of them is cited. Declared classes: {sorted(tax_classes)}."
        ),
    )


def _foreign_tax_currency(
    declared: Declared, currency: Currency, base_currency: Currency
) -> TaxCurrencyConversionUnavailable | None:
    """A taxable instrument in a currency the projection cannot hold its tax in (FR-024).

    Checked before anything is computed, because the alternative is a projection that charged
    a hryvnia rate against a dollar base and produced a plausible number. Unreachable in the
    shipped registry, which is a property of today's data rather than of the arithmetic.
    """
    if currency is base_currency or not _tax_classes_of(declared):
        return None
    return TaxCurrencyConversionUnavailable(
        instrument_id=declared.id,
        instrument_currency=currency.value,
        tax_currency=base_currency.value,
        missing="a holding and its tax in two currencies (fx-tax-asymmetry-f1)",
        reason=(
            f"{declared.id!r} is declared in {currency.value} and declares taxable income, "
            f"but tax is assessed in {base_currency.value} (Principle VI's tax role). The "
            "rate that strikes such a base exists and is applied at assessment; what does not "
            "is a projection holding a position in one currency and its charges in another, "
            "and a per-lot basis carried in both so a realised gain can be struck leg by leg. "
            "Both are specs/features.toml's fx-tax-asymmetry-f1. Refused rather than "
            "converted at a channel rate: a channel is a market you transact in and the "
            "official rate is a legal reference you never transact at, and substituting one "
            "for the other would compute a real tax liability at a price nobody was charged."
        ),
    )


def _plan_for(
    declared: Declared, exit_terms: InstrumentPlan
) -> InstrumentPlan | PlanDoesNotFitInstrument:
    """The run settings, checked against the declaration kind they are settings for."""
    match declared, exit_terms:
        case InstrumentDeclaration(), Assumptions():
            return exit_terms
        case FundDeclaration(), FundAssumptions():
            return exit_terms
        case CashDeclaration(), CashAssumptions():
            return exit_terms
        case _:
            return PlanDoesNotFitInstrument(
                instrument_id=declared.id,
                reason=(
                    f"{declared.id!r} is a {type(declared).__name__} and the run settings "
                    f"given are a {type(exit_terms).__name__}. A bond has no liquidity mode "
                    "and a fund has no coupon policy; the mismatch is reported rather than "
                    "coerced, because silently dropping the fields that do not apply would "
                    "run the holding under settings the caller believes are in force."
                ),
            )


# ---------------------------------------------------------------------------
# The two positional seams (the third, the funding stream, is anchored in `_prepare`)
# ---------------------------------------------------------------------------


def _seam_in(entry: Candidate, prepared: _Prepared, arrived: Money) -> SeamDoesNotChain | None:
    """The way in must end where and in the currency the purchase begins (FR-004).

    The venue half is the one that has no other guard: two hryvnia venues look identical to a
    currency check, and a way in landing the money at the wrong one would fund a purchase with
    money that never got there.
    """
    left: Junction = (entry.destination_id, arrived.currency.value)
    right: Junction = (prepared.access.bought_at, prepared.currency.value)
    if left == right:
        return None
    return SeamDoesNotChain(
        seam="route_in_to_purchase",
        left=f"{left[0]}/{left[1]}",
        right=f"{right[0]}/{right[1]}",
        reason=(
            f"the way in arrives as {left[1]} at {left[0]!r}, and {prepared.declared.id!r} is "
            f"bought as {right[1]} at {right[0]!r}. The two do not meet, so the purchase "
            "would be made with money that is somewhere else: bridging the gap would be a "
            "transfer or a conversion nobody declared, at a rate nobody quoted (FR-004)."
        ),
    )


def _way_out_chain(
    tuple_: Tuple,
    prepared: _Prepared,
    proceeds_at: Junction,
    registries: Registries,
) -> ExitChain | TupleRefused:
    """The declared way out, anchored at both ends, or the refusal that says why there is none.

    It must **depart from where the instrument releases its proceeds** and **end somewhere the
    owner actually spends**. A chain that stops short has not got the money out.
    """
    chain = _chosen_way_out(tuple_.route_out, tuple_, prepared, proceeds_at, registries)
    if not isinstance(chain, ExitChain):
        return chain
    if isinstance(chain, ExitByIdentity):
        return _identity_way_out(chain, prepared, proceeds_at, registries)
    unknown = [name for name in exit_segments_of(chain) if name not in registries.routes]
    if unknown:
        return DeclarationMissing(
            part="route_out",
            what=f"exit route(s) {sorted(unknown)}",
            reason=(
                f"the way out names {sorted(unknown)}, which no declaration under routes/ "
                "declares. A dangling reference is refused rather than skipped: skipping it "
                "would price a shorter journey than the one named."
            ),
        )
    resolved = tuple(registries.routes[name] for name in exit_segments_of(chain))
    departs, _ = cost.junctions_of(resolved[0])
    if departs != proceeds_at:
        return SeamDoesNotChain(
            seam="proceeds_to_route_out",
            left=f"{proceeds_at[0]}/{proceeds_at[1]}",
            right=f"{departs[0]}/{departs[1]}",
            reason=(
                f"{prepared.declared.id!r} releases its proceeds as {proceeds_at[1]} at "
                f"{proceeds_at[0]!r}, and exit route {resolved[0].id!r} departs as "
                f"{departs[1]} from {departs[0]!r}. The two do not meet, so the way out would "
                "be walked with money that is not there -- a junction nobody declared, "
                "crossed for free, with the record still reading as one journey (FR-004)."
            ),
        )
    _, arrives = cost.junctions_of(resolved[-1])
    if arrives not in cost.spendable_junctions(registries.spendable):
        return NoExitRouteDeclared(
            unknown=ExitCostUnknown(
                reason=(
                    f"the way out ends as {arrives[1]} at {arrives[0]!r}, which is not a "
                    "declared spendable endpoint, so nobody has costed the rest of the "
                    "journey. Round-trip cost is what belongs in a comparison, and a "
                    "destination whose exit stops short of somewhere the owner spends is not "
                    "comparison-ready (FR-030, 003 FR-022)."
                ),
                missing_partner_for=resolved[-1].id,
            ),
            reason=(
                f"the declared way out of {prepared.declared.id!r} reaches {arrives[0]!r} and "
                "stops there. The one-way figure is not promoted into the gap: most of the "
                "cost is not the cost."
            ),
        )
    return chain


def _identity_way_out(
    chain: ExitByIdentity,
    prepared: _Prepared,
    proceeds_at: Junction,
    registries: Registries,
) -> ExitByIdentity | SeamDoesNotChain:
    """*There is nothing to do* is a claim about the far end, and it is checked, not trusted.

    Asserted by a caller, its whole content is the claim that the instrument releases its
    proceeds somewhere the owner already spends from.
    """
    endpoints = cost.spendable_junctions(registries.spendable)
    if proceeds_at in endpoints:
        return chain
    return SeamDoesNotChain(
        seam="proceeds_to_route_out",
        left=f"{proceeds_at[0]}/{proceeds_at[1]}",
        right="a declared spendable endpoint",
        reason=(
            f"there is said to be nothing to do because {prepared.declared.id!r} releases its "
            f"proceeds as {proceeds_at[1]} at {proceeds_at[0]!r}, and that is not one of the "
            "owner's declared spendable endpoints. Money in a fund is an asset, not spendable "
            "cash, and a round trip that stopped there would report a journey ending in "
            f"something the owner cannot spend as though it had come back. Declared "
            f"endpoints: {sorted(endpoints)}."
        ),
    )


def _chosen_way_out(
    choice: ExitChoice,
    tuple_: Tuple,
    prepared: _Prepared,
    proceeds_at: Junction,
    registries: Registries,
) -> ExitChain | TupleRefused:
    """What the caller said about the way out, or what the declarations say when he said that.

    :data:`~terezy.core.routes.path.FROM_THE_DECLARATION` reads them in the owner's own order.
    No partner route still means ``ExitCostUnknown`` and no round-trip figure (FR-007, FR-030).
    """
    if not isinstance(choice, FromTheDeclaration):
        return choice
    if proceeds_at in cost.spendable_junctions(registries.spendable):
        return EXIT_BY_IDENTITY
    segments = entry_segments_of(tuple_.route_in)
    arriving = None if not segments else registries.routes[segments[-1]]
    partner = None if arriving is None else arriving.partner_route
    if partner is None:
        return NoExitRouteDeclared(
            unknown=ExitCostUnknown(
                reason=(
                    (
                        f"route {arriving.id!r} declares no partner_route"
                        if arriving is not None
                        else "the way in walks no declared route, so there is no partner_route "
                        "to read"
                    )
                    + ", so nobody has costed the way out. Round-trip cost is computed from "
                    "separately declared exit routes and never by reversing the way in "
                    "(FR-027), and the one-way figure is not promoted into its place (FR-030)."
                ),
                missing_partner_for=IDENTITY_ENTRY_ID if arriving is None else arriving.id,
            ),
            reason=(
                f"nothing declares a way out of {proceeds_at[0]!r} for "
                f"{prepared.declared.id!r}, so this tuple is not comparison-ready: what an "
                "instrument is worth depends on being able to liquidate it into spendable "
                "base currency at a knowable cost (Principle VI)."
            ),
        )
    return DeclaredExit(route_id=partner)


# ---------------------------------------------------------------------------
# The purchase
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class _Acquisition:
    """What the arriving money bought, and what it could not deploy."""

    quantity: float
    price: Money
    carried: Carried | None
    """The clean/accrued split the price was assembled from, or ``None`` where the arm buys at
    no quotation. Carried rather than summed away: the accrual paid **into** a purchase is a
    real term the sell leg already reports and the buy leg did not (027 FR-005)."""

    cost: Money
    remainder: _Remainder | None


@dataclass(frozen=True, slots=True, kw_only=True)
class _Remainder:
    """What the purchase could not deploy, before its way home has been costed.

    Distinct from :class:`~terezy.core.results.tuple.UndeployedCash`, which carries that
    journey: the exit chain and the purchase date are known one level up, so the two halves
    cannot be built in one place.
    """

    amount: Money
    reason: str


def _acquire(
    prepared: _Prepared, path: EntryPath, arrived: Money, *, purchased_on: date
) -> _Acquisition | TupleRefused:
    """Turn what arrived into units, at the declared price and the declared increment.

    **Bought with what arrived, never with what departed** (FR-003). The two differ by the way
    in's whole charge, and using the departing amount makes an expensive ramp invisible in the
    size of the holding as well as in the rate. The **increment is declared or it does not
    exist**: rounding a fund's purchase to whole certificates would invent a term.
    """
    minimum = _minimum_ticket(prepared)
    if minimum is not None and money.compare(arrived, minimum) < 0:
        return BelowMinimumTicket(
            instrument_id=prepared.declared.id,
            path=path,
            required=minimum,
            actual=arrived,
            shortfall=money.sub(minimum, arrived),
            reason=(
                f"{arrived.amount!r} {arrived.currency.value} reached "
                f"{prepared.access.bought_at!r} and {prepared.declared.id!r} requires at "
                f"least {minimum.amount!r}. The tuple is infeasible for this amount and is "
                "reported as such rather than rounded up, which would spend money the owner "
                "did not agree to spend"
                + (
                    ". What arrived is at or below zero because the way in's fees exceeded "
                    "the amount sent, which is reported rather than clamped"
                    if arrived.amount <= 0.0
                    else ""
                )
                + "."
            ),
        )
    # **Priced after the ticket check, not before.** What a unit costs cannot decide whether
    # the amount was large enough to trade at all, and a refusal that could not price the paper
    # would otherwise mask the plainer one a reader needs first.
    priced = _price_for(prepared, purchased_on=purchased_on)
    if isinstance(priced, InstrumentRefused):
        return priced
    price = priced.price
    increment = _min_unit(prepared)
    quantity = _whole_increments(arrived, price, increment)
    if quantity <= 0.0:
        return BuysNoWholeUnit(
            instrument_id=prepared.declared.id,
            path=path,
            price_per_unit=price,
            min_unit=increment,
            actual=arrived,
            reason=(
                f"{arrived.amount!r} {arrived.currency.value} will not buy one increment of "
                f"{increment!r} unit(s) of {prepared.declared.id!r} at "
                f"{price.amount!r} each. Reported rather than rounded up to one: a purchase "
                "the owner cannot afford did not happen."
            ),
        )
    spent = money.scale(price, quantity)
    return _Acquisition(
        quantity=quantity,
        price=price,
        carried=priced.carried,
        cost=spent,
        remainder=_undeployed(prepared, price, increment, money.sub(arrived, spent)),
    )


def _undeployed(
    prepared: _Prepared, price: Money, increment: float, remainder: Money
) -> _Remainder | None:
    """What the purchase could not deploy, or ``None`` where there is no such thing.

    **A declaration with no increment leaves no remainder, by construction** -- the arriving
    amount buys exactly what it buys. What ``price * (arrived / price)`` leaves behind in
    binary floating point is not money: the shipped MilTech fund at a net asset value of
    1006.97 and an arriving 1007.00 produced ``-1.14e-13``, a **negative** "money that made the
    trip in and bought nothing", sent home along a declared exit. So the comparison is the
    imported tolerance rather than ``== 0.0``, and anything at or below zero is refused
    outright as well: :func:`_whole_increments` rounds a *ratio* at the relative tolerance
    while this tests *money* at the absolute one.
    """
    if increment == 0.0 or remainder.amount <= 0.0 or is_close(remainder.amount, 0.0):
        return None
    return _Remainder(
        amount=remainder,
        reason=(
            f"{prepared.declared.id!r} is bought in increments of {increment!r} "
            f"unit(s) at {price.amount!r} {price.currency.value} each, so "
            f"{remainder.amount!r} of what arrived bought nothing. What became of it is "
            "the journey beside this: it is the same sentence whether the remainder came "
            "home or was left where it is."
        ),
    )


_NO_CARRY: Final = card.NotStated(
    what="carried",
    arm="fund or cash",
    reason=(
        "this arm is not bought at a quotation: a fund is priced at its declared net asset "
        "value plus the mode's markup, and a balance at par. There is no clean price and no "
        "accrual to separate out of one."
    ),
)
"""What a purchase states where no quotation was carried to the settlement date."""


@dataclass(frozen=True, slots=True, kw_only=True)
class _Priced:
    """One unit's cost, and the clean/accrued split it was assembled from where there is one."""

    price: Money
    carried: Carried | None


def _price_for(prepared: _Prepared, *, purchased_on: date) -> _Priced | InstrumentRefused:
    """What one unit costs, from whichever declaration states it.

    A fund prices itself through the fund module's own function, so the price the join buys at
    is the price the projection records. A bond states no purchase price at all, so the venue's
    declared quote is the price -- and **a bond's quotation is a dirty price, carried to the
    settlement date** (FR-005), because nothing else would state the difference between the
    quotation's day and the day the money arrives.
    """
    match prepared.declared, prepared.plan:
        case FundDeclaration(), FundAssumptions():
            return _Priced(
                price=fund_terms.entry_price_for(prepared.declared, prepared.plan.liquidity_mode),
                carried=None,
            )
        case CashDeclaration(), _:
            # Sizing is identity: an amount of the declared currency buys that amount of
            # balance (FR-005). What the declaration DOES observe is the rate, and its mark
            # reaches every figure through `_projection_provenance`.
            return _Priced(price=money.unit(prepared.currency), carried=None)
        case InstrumentDeclaration(), _:
            quoted = prepared.access.quote
            if quoted is None:  # pragma: no cover -- the resolver refuses this at load
                raise ValueError(
                    f"{prepared.declared.id!r} declares no price of its own and its access "
                    "declaration quotes none either. The resolver refuses that combination at "
                    "load, so reaching here means a Registries was built in code with a "
                    "declaration the data boundary would not have accepted."
                )
            carried = accrual.carried_to(
                _accrual_schedule(prepared.declared),
                quote=quoted.price,
                observed_on=quoted.observed_on,
                on=purchased_on,
                quoted_term="access.price.observed_on",
                dated_term="holding.purchased_on",
            )
            if isinstance(carried, InconsistentTerms):
                return InstrumentRefused(instrument_id=prepared.declared.id, reason=carried.reason)
            price = accrual.price(carried)
            if price.amount <= 0.0:
                # **The same guard the sell leg carries** (`acquire.early_sale`): the price is
                # the declared quote net of one accrual and plus another, which the resolver
                # cannot see. Zero divides in `_whole_increments`; negative buys a negative
                # number of units and reports `BuysNoWholeUnit`, whose message would blame an
                # owner who can afford it.
                return InstrumentRefused(
                    instrument_id=prepared.declared.id,
                    reason=(
                        f"{prepared.declared.id!r} is quoted {quoted.price.amount!r} "
                        f"{quoted.price.currency.value} as of "
                        f"{quoted.observed_on.isoformat()}, which is a clean "
                        f"{carried.clean.amount!r} plus the accrual of that day; carried to the "
                        f"purchase on {purchased_on.isoformat()} that clean price plus "
                        f"{carried.accrued.amount!r} of accrual leaves {price.amount!r}. A unit "
                        "cannot cost nothing or less: the quotation and the payment schedule "
                        "describe different paper, and sizing a purchase from this would report "
                        "a holding nobody could buy."
                    ),
                )
            return _Priced(price=price, carried=carried)
        case _:  # pragma: no cover -- `_plan_for` has already refused a mismatched pair
            raise ValueError(
                f"{prepared.declared.id!r} reached pricing with run settings of type "
                f"{type(prepared.plan).__name__}, which _plan_for refuses."
            )


def _accrual_schedule(declared: InstrumentDeclaration) -> accrual.Schedule:
    """This instrument's coupon dates and day count, through its own declared plugin.

    ``ops_for`` rather than a match on the declaration form: which coupons one unit pays is a
    question both forms answer, which keeps the decision layer from learning there are two
    (013 FR-011a).
    """
    ops = instrument_registry.ops_for(declared.instrument_class)
    return accrual.schedule_of(declared, ops.coupons_per_unit(declared))


def _minimum_ticket(prepared: _Prepared) -> Money | None:
    """The smallest amount that may be invested, where the declaration states one.

    A bond states it in money. A fund states a minimum in **units**, checked by its own
    projection -- deriving a ticket from it here would report the wrong one once the price
    moved.
    """
    match prepared.declared:
        case InstrumentDeclaration():
            return prepared.declared.constraints.min_ticket
        case FundDeclaration() | CashDeclaration():
            return None
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(prepared.declared)


def _min_unit(prepared: _Prepared) -> float:
    """The smallest buyable increment the declaration states, or ``0.0`` where it states none.

    ``1.0`` would be an invented increment. ``0.0`` is read by :func:`_whole_increments` as
    *no increment*, and the arriving amount then buys exactly what it buys.
    """
    match prepared.declared:
        case InstrumentDeclaration():
            return prepared.declared.constraints.min_unit
        case FundDeclaration() | CashDeclaration():
            return 0.0
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(prepared.declared)


def _whole_increments(arrived: Money, price: Money, increment: float) -> float:
    """As many whole declared increments as the arriving amount covers, and no fraction.

    ``increment == 0.0`` means *no increment is declared*. Otherwise: an exact multiple can
    land a hair below itself in binary floating point and a bare floor would throw away a whole
    unit the owner could really buy, so a ratio within the imported project tolerance of a
    whole number is that whole number.
    """
    units = arrived.amount / price.amount
    if increment == 0.0:
        return units
    ratio = units / increment
    nearest = round(ratio)
    whole = nearest if is_close(ratio, float(nearest)) else math.floor(ratio)
    return whole * increment


# ---------------------------------------------------------------------------
# The holding
# ---------------------------------------------------------------------------


def _project(
    prepared: _Prepared,
    bought: _Acquisition,
    *,
    purchased_on: date,
    horizon: DateRange,
    tax_classes: Mapping[str, TaxClass],
    registries: Registries,
) -> Projected | TupleRefused:
    """Run the holding through the call that owns its lifecycle, and read the refusals.

    The owning call's typed failures are translated **without re-wording them**; the join's
    contribution is to say which of the round trip's parts the refusal came from.
    """
    holding = Holding(
        owner_id=prepared.stream.owner_id,
        instrument_id=prepared.declared.id,
        quantity=bought.quantity,
        purchased_on=purchased_on,
        cost=bought.cost,
    )
    window = DateRange(start=horizon.start, end=horizon.end)
    match prepared.declared, prepared.plan:
        case InstrumentDeclaration(), Assumptions():
            return _bond_outcome(
                prepared,
                bond_results.project(
                    prepared.declared,
                    holding,
                    window,
                    prepared.plan,
                    tax_classes=tax_classes,
                    early_exit=_early_exit(prepared, registries),
                ),
            )
        case FundDeclaration(), FundAssumptions():
            return _fund_outcome(
                prepared,
                fund_results.project_fund(
                    prepared.declared,
                    holding,
                    window,
                    prepared.plan,
                    tax_classes=tax_classes,
                ),
            )
        case CashDeclaration(), CashAssumptions():
            return _cash_outcome(
                prepared, cash_results.project_cash(prepared.declared, holding, window)
            )
        case _:  # pragma: no cover -- `_plan_for` has already refused a mismatch
            raise ValueError(
                f"{prepared.declared.id!r} reached the projection with run settings of type "
                f"{type(prepared.plan).__name__}, which _plan_for refuses. A Registries built "
                "in code has bypassed the check."
            )


def _early_exit(prepared: _Prepared, registries: Registries) -> EarlyExit | None:
    """What this holding is sold for if the horizon ends before its own terms do (015 FR-029).

    ``None`` where the access declaration quotes no resale price. Nothing is inferred from the
    purchase quote or the face value -- either would report a spread of zero. The quotation's
    own date travels with it: it is the date the accrual inside the quotation is measured at.
    """
    quote = prepared.access.resale_price
    if quote is None:
        return None
    return EarlyExit(
        price_per_unit=quote.price,
        observed_on=quote.observed_on,
        assumption=registries.quotation_holds,
    )


def _bond_outcome(
    prepared: _Prepared, outcome: bond_results.ProjectionOutcome
) -> Projection | TupleRefused:
    """A bond projection, or the refusal its own failure becomes."""
    match outcome:
        case Projection():
            return outcome
        # Both terms, not just the second. `access.resale_price` is the second term of two
        # different refusals -- a window that outlives the paper with no price to sell at,
        # whose remedy IS a declaration, and a holding one quotation cannot price, whose remedy
        # is the run plan -- and only the first is a missing declaration.
        case InconsistentTerms(first_term="horizon.end", second_term="access.resale_price"):
            return DeclarationMissing(
                part="access",
                what=f"{prepared.access.instrument_id}: access.resale_price",
                reason=(
                    f"{outcome.reason} The remedy is a declaration rather than a longer "
                    "horizon: this instrument can be sold before its terms end, and what is "
                    "missing is the price it sells at."
                ),
            )
        case _:
            return InstrumentRefused(instrument_id=prepared.declared.id, reason=outcome.reason)


def _cash_outcome(
    prepared: _Prepared, outcome: CashProjection | InconsistentTerms
) -> CashProjection | TupleRefused:
    """A balance projection, or the refusal its one failure becomes."""
    match outcome:
        case CashProjection():
            return outcome
        case InconsistentTerms():
            return InstrumentRefused(instrument_id=prepared.declared.id, reason=outcome.reason)
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(outcome)


def _fund_outcome(
    prepared: _Prepared, outcome: fund_results.FundOutcome
) -> FundProjection | TupleRefused:
    """A fund projection, or the refusal its own failure becomes."""
    match outcome:
        case FundProjection() if outcome.exit_line is not None:
            return outcome
        case FundProjection():
            return CannotSpanHorizon(
                instrument_id=prepared.declared.id,
                binding_term="instrument.terminates_on",
                reason=(
                    f"{prepared.declared.id!r} is still open at the end of this comparison's "
                    "horizon: no exit was requested and the fund has not terminated, so "
                    "nothing was liquidated. A holding is never sold because a projection ran "
                    "out of dates, so there is no round trip to report -- request an exit "
                    "within the horizon, or compare over one the fund's own end fits inside."
                ),
            )
        case RangeProjection():
            return TwoFiguresNotOne(
                instrument_id=prepared.declared.id,
                reason=(
                    f"{prepared.declared.id!r} states a range of "
                    f"{outcome.declared_yield.low!r} to {outcome.declared_yield.high!r} and no "
                    "point inside it was chosen, so the honest answer is two figures. A tuple "
                    "has one outcome, and taking the midpoint, the low end or the high end "
                    "would be the false point a range exists to refuse."
                ),
            )
        case fund_results.RedemptionRefused():
            return NoExitTermsDeclared(instrument_id=prepared.declared.id, reason=outcome.reason)
        case _:
            return InstrumentRefused(instrument_id=prepared.declared.id, reason=_reason_of(outcome))


def _reason_of(outcome: object) -> str:
    """The ``reason`` a typed failure carries, whichever of them it is."""
    reason = getattr(outcome, "reason", None)
    return reason if isinstance(reason, str) else repr(outcome)


# ---------------------------------------------------------------------------
# Bringing every release home
# ---------------------------------------------------------------------------


def _repatriate(
    tuple_: Tuple,
    prepared: _Prepared,
    projected: Projected,
    *,
    routed: _Routed,
    as_of: date,
    registries: Registries,
) -> tuple[tuple[Arrival, WayOutCost], ...] | TupleRefused:
    """Every net amount the holding released, sent home along the declared way out.

    Netted **by date** rather than event by event, because the way out charges a flat fee per
    movement. A date that nets **negative** is refused rather than absorbed into a later
    receipt: it would mean money travelling *in* along a route nobody costed, and netting it
    forward would move a real outflow to a date it did not happen on.
    """
    charged: list[tuple[Arrival, WayOutCost]] = []
    for released_on, released in _released_by_date(projected):
        if released.amount < 0.0:
            return InstrumentDemandsCash(
                instrument_id=prepared.declared.id,
                on=released_on,
                shortfall=money.scale(released, -1.0),
                reason=(
                    f"on {released_on.isoformat()} the holding of {prepared.declared.id!r} "
                    f"takes {-released.amount!r} {released.currency.value} out and pays "
                    "nothing in, so the money would have to travel to the instrument along a "
                    "route nobody costed. It is refused rather than netted against a later "
                    "receipt, which would move a real outflow to a date it did not happen on."
                ),
            )
        way_out = cost.cost_exit(
            routed.chain,
            released,
            stream_id=tuple_.stream_id,
            departing_from=routed.proceeds_at,
            routes=registries.routes,
            channels=registries.channels,
            kinds=registries.kinds,
            on_date=released_on,
            as_of=as_of,
            spendable=registries.spendable,
        )
        if isinstance(way_out, RouteUnusable):
            return WayOutUnusable(
                refused=way_out,
                released_on=released_on,
                reason=(
                    f"the way out will not carry the {released.amount!r} "
                    f"{released.currency.value} that {prepared.declared.id!r} released on "
                    f"{released_on.isoformat()}: {way_out.reason}"
                ),
            )
        capped = _over_the_way_out_cap(way_out, released, released_on)
        if capped is not None:
            return capped
        charged.append(
            (
                Arrival(
                    released_on=released_on,
                    arrived_on=released_on + timedelta(days=way_out.latency_days),
                    released=released,
                    amount=way_out.arrived,
                ),
                way_out,
            )
        )
    return tuple(charged)


def _over_the_way_out_cap(way_out: WayOutCost, sent: Money, on: date) -> WayOutCapExceeded | None:
    """Refuse a movement larger than the tightest monthly cap the way out declares (FR-016).

    A caller that reads ``cost_exit``'s reported ceiling nowhere repatriates past it in
    silence, which is what shipped: a 1.00 hryvnia monthly cap on the shipped exit route
    produced a complete outcome reporting 13 100.00 reaching the endpoint. Per movement rather
    than per month, with the gap on :class:`~terezy.core.results.tuple.WayOutCapExceeded`.
    """
    if way_out.ceiling is None or money.compare(sent, way_out.ceiling) <= 0:
        return None
    ceiling = way_out.ceiling
    return WayOutCapExceeded(
        path=way_out.path,
        released_on=on,
        ceiling=ceiling,
        requested=sent,
        excess=money.sub(sent, ceiling),
        reason=(
            f"the way out declares a monthly ceiling of {ceiling.amount!r} "
            f"{ceiling.currency.value} and {sent.amount!r} was to travel it on "
            f"{on.isoformat()}, so {money.sub(sent, ceiling).amount!r} of it cannot come "
            "home that month. The tuple is refused rather than repatriated up to the "
            "ceiling: splitting a movement across months is the same deferred partial "
            "deployment as on the way in (FR-018, owner decision 2026-08-22), and reporting "
            "the remainder needs a declared fallback policy and the month's consumed "
            "capacity, neither of which a tuple carries. Declare a way out that carries it, "
            "or exit on a date whose movement fits."
        ),
    )


def _send_the_remainder_home(
    tuple_: Tuple,
    prepared: _Prepared,
    remainder: _Remainder | None,
    *,
    routed: _Routed,
    purchased_on: date,
    as_of: date,
    registries: Registries,
) -> tuple[UndeployedCash | None, WayOutCost | None]:
    """Send what the purchase could not deploy back out along the tuple's declared way out.

    **The fourth seam.** The remainder is at the venue the purchase was made at while the chain
    departs from wherever the instrument releases its **proceeds**; where the two declarations
    differ, walking the chain with this money would be the free transfer between venues feature
    004 shipped. **A way out that will not carry it leaves it where it is** rather than
    refusing the tuple (:class:`~terezy.core.results.tuple.RemainderStayed`).
    """
    if remainder is None:
        return None, None
    at: Junction = (prepared.access.bought_at, prepared.currency.value)
    if at != routed.proceeds_at:
        return _stayed(
            prepared,
            remainder,
            f"it is at {at[0]!r} in {at[1]}, and the declared way out departs from "
            f"{routed.proceeds_at[0]!r} in {routed.proceeds_at[1]}, where "
            f"{prepared.declared.id!r} releases its proceeds. Nothing declares how it reaches "
            "the start of that chain, so carrying it there would be a leg nobody declared at "
            "a rate nobody declared.",
        ), None
    way_out = cost.cost_exit(
        routed.chain,
        remainder.amount,
        stream_id=tuple_.stream_id,
        departing_from=routed.proceeds_at,
        routes=registries.routes,
        channels=registries.channels,
        kinds=registries.kinds,
        on_date=purchased_on,
        as_of=as_of,
        spendable=registries.spendable,
    )
    if isinstance(way_out, RouteUnusable):
        return _stayed(prepared, remainder, way_out.reason), None
    # The ceiling rule lives in `_over_the_way_out_cap` and is read here rather than restated;
    # its own reason is not, because that one says the tuple was refused and this one is not.
    if way_out.arrived.amount <= 0.0:
        return _stayed(
            prepared,
            remainder,
            f"the way out would deliver {way_out.arrived.amount!r} "
            f"{way_out.arrived.currency.value} of it, which is nothing or less: its charge is "
            "the whole of the remainder or more. A release has to come home and is reported "
            "arriving at a loss; a remainder does not, and moving it would leave the owner "
            "with less than leaving it there. The two figures are stated rather than "
            "subtracted: an exit chain that converts delivers in a currency this amount is "
            "not in.",
        ), None
    capped = _over_the_way_out_cap(way_out, remainder.amount, purchased_on)
    if capped is not None:
        return _stayed(
            prepared,
            remainder,
            f"the way out declares a monthly ceiling of {capped.ceiling.amount!r} "
            f"{capped.ceiling.currency.value}, and {capped.excess.amount!r} of the remainder "
            "is over it. Splitting a movement across months needs a declared fallback policy "
            "and the month's consumed capacity, neither of which a tuple carries.",
        ), None
    return (
        UndeployedCash(
            amount=remainder.amount,
            venue_id=prepared.access.bought_at,
            journey=RemainderCameHome(
                left_on=purchased_on,
                arrived_on=purchased_on + timedelta(days=way_out.latency_days),
                reached=way_out.arrived,
            ),
            reason=remainder.reason,
        ),
        way_out,
    )


def _stranded(undeployed: UndeployedCash | None) -> Money | None:
    """The part of the outlay that never came home, or ``None`` where none is."""
    match undeployed:
        case UndeployedCash(journey=RemainderStayed(), amount=amount):
            return amount
    return None


def _stayed(prepared: _Prepared, remainder: _Remainder, why: str) -> UndeployedCash:
    """The remainder, left where the purchase left it, with the reason it could not travel."""
    return UndeployedCash(
        amount=remainder.amount,
        venue_id=prepared.access.bought_at,
        journey=RemainderStayed(
            reason=(
                f"{remainder.amount.amount!r} {remainder.amount.currency.value} could not "
                f"leave {prepared.access.bought_at!r} along this tuple's declared way out: "
                f"{why} It is out of what reaches a spendable endpoint, and the rate is "
                "refused rather than measured, because part of the outlay never came home."
            )
        ),
        reason=remainder.reason,
    )


def _charges_of(projected: Projected) -> tuple[TaxCharge, ...]:
    """Every tax charge a projection recorded, whichever kind produced it.

    Empty for a balance, and the emptiness is the declaration's answer rather than a table the
    join failed to read: proceeds equal basis, so none is assessed (FR-009).
    """
    match projected:
        case Projection() | FundProjection():
            return projected.charges
        case CashProjection():
            return ()
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(projected)


def _released_by_date(projected: Projected) -> tuple[tuple[date, Money], ...]:
    """The holding's net-of-tax cash effect per date, in date order, purchase excluded.

    The purchase is excluded because the join already paid for it and reports it as the
    ``entry`` part. Dates that net to exactly zero are dropped: sending nothing would still be
    charged a fixed fee by an exit chain that declares one.

    **The tax comes from the charge, not from the charge event's amount.** A ``TAX_CHARGE`` is
    an assessment memo that moves nothing, so summing the events alone would send the **gross**
    coupon home and report a pre-tax rate on a record whose
    :data:`~terezy.core.results.tuple.ACCOUNTS_FOR` says it is net of tax.

    **It is netted on the date the income accrued**, because the declared settlement deadline
    lives in ``data/tax/timing/``, which a :class:`Registries` does not carry; the error runs
    one way, the money leaving sooner, so the rate is understated. On the base a percentage
    exit fee charges the choice is instead the *flattering* one, by exactly ``pct x tax``, and
    it is taken on correctness: the tax never travels the way out.
    """
    ledger = projected.ledger
    currency = ledger.base_currency
    taxed_on = {event.sequence: event.occurred_on for event in ledger.applied}
    by_date: dict[date, list[Money]] = {}
    for event in ledger.applied:
        if event.kind is EventKind.PURCHASE:
            continue
        by_date.setdefault(event.occurred_on, []).append(event.amount)
    for charge in _charges_of(projected):
        taxed = taxed_on.get(charge.event_sequence)
        if taxed is None:  # pragma: no cover -- both projections renumber before they fold
            raise LedgerInvariantError(
                f"tax charge on event {charge.event_sequence} names no event in this ledger, "
                "so there is no date to net it on. Dropping it would send the gross amount "
                "home and understate nothing visibly -- every part line would still read "
                "correctly. Both projections renumber their charges onto the combined stream "
                "before folding it, so reaching here means that renumbering was skipped."
            )
        # This catches a charge naming an event that is not in the ledger. It does not catch
        # *two* charges on one event: both chargers key their pairing by `event_sequence` in a
        # dict, so the second would already have replaced the first before `charges` was built.
        # Not reachable today -- each charger walks the events once.
        by_date.setdefault(taxed, []).append(money.scale(charge.total, -1.0))
    netted = ((on, money.total(amounts, currency)) for on, amounts in sorted(by_date.items()))
    return tuple((on, amount) for on, amount in netted if amount.amount != 0.0)


# ---------------------------------------------------------------------------
# The outcome
# ---------------------------------------------------------------------------


def _endpoint_currency(chain: ExitChain, prepared: _Prepared, registries: Registries) -> Currency:
    """What the way out delivers in: the last exit leg's currency, or the instrument's own.

    Read from the declared chain rather than from an arrival, so a holding that released
    nothing still has an honest currency to report a zero in -- a zero of no currency would be
    the one figure in the output that could be added to anything.
    """
    segments = exit_segments_of(chain)
    if not segments:
        return prepared.currency
    return registries.routes[segments[-1]].legs[-1].to_ccy


_RELEASE_KINDS: Final[frozenset[EventKind]] = frozenset(
    {
        EventKind.COUPON,
        EventKind.DISTRIBUTION,
        EventKind.PRINCIPAL_REPAYMENT,
        EventKind.REDEMPTION,
    }
)
"""The event kinds that are the instrument paying the owner, for the ``lifecycle`` line.

**Distinct from** the ledger's ``CASH_ONLY_KINDS`` rather than narrower: the two overlap and
neither contains the other, because a redemption is a receipt that also closes a lot. A fee is
a charge rather than a receipt, and a tax charge is neither -- what it assessed reaches the
``tax`` line from the charge rather than from the event.
"""


def _assemble(
    tuple_: Tuple,
    prepared: _Prepared,
    projected: Projected,
    *,
    projection: CandidateProjection,
    outlay: Money,
    one_way: OneWayCost,
    arrivals: tuple[Arrival, ...],
    way_out_costs: tuple[WayOutCost, ...],
    endpoint_currency: Currency,
    undeployed: UndeployedCash | None,
    routed: _Routed,
    horizon: DateRange,
    purchased_on: date,
    continuation: ContinuationAssumption,
    quotation_holds: QuotationHolds,
    kinds: Mapping[str, ObservationKind],
    cpi: Mapping[str, CpiSeries],
    inflation: InflationAssumption | None,
    as_of: date,
) -> Evaluated:
    """Everything the owning calls returned, summed and chained. No new arithmetic here.

    Every part carries the name of the call that produced it. The parts are an **attribution**
    and not an addition: they are in up to three currencies, and the instrument's exit terms
    and its lifecycle receipts describe the same money from two sides. What adds up is
    :attr:`~terezy.core.results.tuple.TupleOutcome.reaches`.
    """
    carried = _carried_quotation(
        prepared, projected, purchased_on=purchased_on, quotation_holds=quotation_holds
    )
    home = money_home(arrivals, undeployed)
    reaches = money.total([amount for _, amount, _ in home], endpoint_currency)
    provenance = prov.merge_all(
        [
            one_way.provenance,
            *(charged.provenance for charged in way_out_costs),
            _projection_provenance(projected),
            _declaration_provenance(prepared),
        ]
    )
    span = DateRange(start=horizon.start, end=max((on for on, _, _ in home), default=horizon.start))
    rate = _rate(
        prepared,
        outlay=outlay,
        arriving=tuple((on, amount) for on, amount, _ in home),
        stranded=_stranded(undeployed),
        endpoint_currency=endpoint_currency,
        span=span,
    )
    staleness = stale.merge_all(
        [
            one_way.staleness,
            *(charged.staleness for charged in way_out_costs),
            stale.staleness_of_sources(provenance, kinds, as_of=as_of),
        ]
    )
    return Evaluated(
        projection=projection,
        outcome=TupleOutcome(
            key=tuple_,
            projection_key=projection.projection_key,
            outlay=outlay,
            parts=_parts(prepared, projected, one_way=one_way, way_out_costs=way_out_costs),
            arrivals=arrivals,
            reaches=reaches,
            implied_rate=rate,
            # `nominal=None` is how FR-002's "there is nothing to deflate" is reached, rather than
            # by a branch here: no refusal is decided at this site.
            real=hurdle_figures.real_terms(
                nominal=rate if isinstance(rate, NominalRate) else None,
                nominal_provenance=provenance,
                nominal_staleness=staleness,
                deflation=hurdle_figures.Deflation(
                    window=cpi_series.deflation_window(span.start, span.end),
                    series=cpi,
                    assumption=inflation,
                    ageing=Ageing(kinds=kinds, as_of=as_of),
                ),
            ),
            span=span,
            horizon=horizon,
            undeployed=undeployed,
            routes=_standing(routed, way_out_costs),
            risk_class=prepared.access.risk_class,
            sold_early=projected.sold_early if isinstance(projected, Projection) else None,
            carried_quotation=carried,
            rests_on=_rests_on(
                prepared,
                projected,
                span=span,
                horizon=horizon,
                continuation=continuation,
                carried=carried,
            ),
            accounts_for=ACCOUNTS_FOR,
            excludes=_excludes_of(prepared),
            provenance=provenance,
            staleness=staleness,
        ),
    )


def _standing(routed: _Routed, way_out_costs: tuple[WayOutCost, ...]) -> RouteStanding:
    """How usable both declared ways are, from the figures the costing already returned.

    Both, and never one: a status describing the way in alone on a record whose headline number
    is a round trip is the half-truth ``RampCost.status`` records about itself. A holding that
    released nothing has no way-out cost, and that standing is unknown rather than open.
    """
    out_status = {charged.status for charged in way_out_costs}
    constrained: list[Literal["route_in", "route_out"]] = []
    if routed.status == "constrained":
        constrained.append("route_in")
    if "constrained" in out_status:
        constrained.append("route_out")
    return RouteStanding(
        status="constrained" if constrained else "open",
        disruption_probability=max(
            [routed.disruption, *(charged.disruption_probability for charged in way_out_costs)]
        ),
        constrained=tuple(constrained),
    )


def _declaration_provenance(prepared: _Prepared) -> Provenance:
    """The declared tables the **join itself** read, which no projection propagates.

    A projection's provenance covers the tables *it* consulted, and there are two the join
    consults that it never sees:

    * ``[instrument.constraints]`` -- the minimum ticket and the buyable increment, which
      decide how many units were bought and therefore every figure downstream;
    * a fund's :class:`~terezy.core.instruments.fund.LiquidityTerms`, **both tables**. The
      settlement delay moves the arrival date and therefore the rate -- 0 to 30 business days
      moves the shipped MilTech tuple from 0.17578 to 0.16553 -- and the join cannot tell which
      of the two supplied it without re-deciding the exit, so it marks the pair. One mark
      absent where it belongs is Principle I's defect; one present where it need not be is not.

    **Not everything a declaration cites.** ``fee_context`` moves no figure
    (``instruments.fund``, owner decision B); the line is *can this table move a number*,
    asserted by ``tests/contract/test_marks_survive_the_join.py``. The venue quote's citation
    arrives through :func:`_projection_provenance` with the purchase event.
    """
    tables: list[Provenance] = []
    match prepared.declared:
        case InstrumentDeclaration():
            tables.append(prepared.declared.constraints.provenance)
        case FundDeclaration():
            tables.append(prepared.declared.liquidity.legal.provenance)
            tables.append(prepared.declared.liquidity.practice.provenance)
        case CashDeclaration():
            # A balance declares no table the join reads: no constraints, no liquidity terms.
            # Its one citation is the rate, and it arrives through the projection, which is
            # where a bond's terms already arrive.
            pass
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(prepared.declared)
    return prov.merge_all(tables)


def _parts(
    prepared: _Prepared,
    projected: Projected,
    *,
    one_way: OneWayCost,
    way_out_costs: tuple[WayOutCost, ...],
) -> tuple[PartContribution, ...]:
    """Each of the six terms, with the call that produced it named (FR-005).

    Signed as the ledger signs things: negative for money leaving the owner. The
    ``exit_terms`` line is a **recorded zero** where the declared way out charges nothing,
    because only an *absent* declaration is a refusal (FR-009).
    """
    currency = prepared.currency
    charged_out = money.total(
        [money.total(charged.components.values(), currency) for charged in way_out_costs],
        currency,
    )
    lines: tuple[tuple[Part, Money, str], ...] = (
        (
            "ramp_in",
            money.scale(money.total(one_way.components.values(), one_way.sent.currency), -1.0),
            "core.routes.cost.cost_one -- the one-way cost of the declared way in",
        ),
        (
            "entry",
            _purchase_amount(projected),
            "the projection's own purchase event -- what the arriving money became",
        ),
        (
            "lifecycle",
            money.total(
                [
                    event.amount
                    for event in projected.ledger.applied
                    if event.kind in _RELEASE_KINDS
                ],
                currency,
            ),
            "the projection's ledger -- every gross payment the instrument made",
        ),
        (
            "tax",
            money.scale(_total_tax(projected), -1.0),
            "the declared tax classes, charged event by event by core.tax",
        ),
        ("exit_terms", *_exit_terms_line(prepared, projected)),
        (
            "ramp_out",
            money.scale(charged_out, -1.0),
            "core.routes.cost.cost_exit -- charged once on each amount that travelled the way "
            "out: every release, and the remainder the purchase could not deploy",
        ),
    )
    return tuple(
        PartContribution(part=part, amount=amount, source=source) for part, amount, source in lines
    )


def _exit_terms_line(prepared: _Prepared, projected: Projected) -> tuple[Money, str]:
    """What the instrument's own way out gave up, and where the figure came from."""
    match projected:
        case FundProjection():
            return (
                money.scale(projected.exit_spread, -1.0),
                "FundProjection.exit_spread -- the declared discount off NAV on the way out",
            )
        case Projection():
            return (
                money.zero(prepared.currency),
                "instrument.terms -- redemption at face value on the maturity date; the "
                "declared terms charge nothing to leave, and this zero is recorded rather "
                "than assumed",
            )
        case CashProjection():
            return (
                money.zero(prepared.currency),
                "instrument.balance -- a balance is released at its own amount; the declared "
                "terms charge nothing to leave, and this zero is recorded rather than assumed",
            )
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(projected)


def _purchase_amount(projected: Projected) -> Money:
    """The purchase event's own amount, read off the ledger rather than recomputed.

    If the two ever differed, the ledger's is the one every other figure rests on.
    """
    for event in projected.ledger.applied:
        if event.kind is EventKind.PURCHASE:
            return event.amount
    raise LedgerInvariantError(  # pragma: no cover -- every projection opens with a purchase
        "a projection reached the join with no purchase event, so there is nothing the "
        "arriving money became. Every run this module builds opens with one."
    )


def _total_tax(projected: Projected) -> Money:
    """Every charge over the holding's life, from whichever result records it."""
    match projected:
        case Projection():
            return projected.hurdle.total_tax
        case FundProjection():
            return projected.total_tax
        case CashProjection():
            # Not an exemption and not an unread rule: proceeds equal basis, so no gain and no
            # income arise and there is nothing to charge (FR-009).
            return money.zero(projected.released.currency)
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(projected)


def _projection_provenance(projected: Projected) -> Provenance:
    """Every source the holding's own figures rest on."""
    match projected:
        case Projection():
            return projected.hurdle.provenance
        case FundProjection() | CashProjection():
            return projected.provenance
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(projected)


def _day_count_of(prepared: _Prepared) -> str:
    """The convention this holding's own figures are annualised on.

    A day count turns a span of days into a fraction of a year. Whether it also sized anything
    is a fact about the declaration, not about the convention, which is why the declaration is
    asked rather than a field read.
    """
    match prepared.declared:
        case InstrumentDeclaration():
            return instrument_terms.day_count_of(prepared.declared.terms)
        case FundDeclaration():
            return prepared.declared.day_count
        case CashDeclaration():
            return cash_terms.DAY_COUNT
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(prepared.declared)


def _excludes_of(prepared: _Prepared) -> frozenset[str]:
    """What this outcome fails to account for, beyond the answer-wide exclusions.

    :data:`~terezy.core.results.tuple.EXCLUDES` is the floor. What a particular declaration
    adds to it is the declaration's answer, not this module's decision (013 FR-023).
    """
    match prepared.declared:
        case InstrumentDeclaration():
            return EXCLUDES | instrument_terms.excludes_of(prepared.declared.terms)
        case FundDeclaration() | CashDeclaration():
            return EXCLUDES
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(prepared.declared)


def _rate(
    prepared: _Prepared,
    *,
    outlay: Money,
    arriving: tuple[tuple[date, Money], ...],
    stranded: Money | None,
    endpoint_currency: Currency,
    span: DateRange,
) -> NominalRate | RateNotComparable:
    """The money-weighted return over the span, or a typed statement of why there is none.

    **The payment out at ``t=0`` is the whole outlay**, and every dated amount that reached the
    endpoint is a receipt against it, including the remainder the purchase could not deploy.
    Netting that off the denominator instead would assume it recoverable at par and free.

    **Where the way out would not carry it there is no figure at all**, and that is Principle I
    rather than caution: measuring on the whole outlay prices the stranded amount at zero and
    netting it off prices it at par, nothing declares which it is worth, and both look like a
    real rate. The amount is unaffected and is reported.

    Time is measured with the **instrument's declared day-count convention**, so this rate and
    feature 001's hurdle are on the same clock. The root find's precondition -- one payment out
    at the start, receipts afterwards, over a period -- is checked here rather than discovered
    as an exception, because a series that fails it is a fact about this round trip.
    """
    endpoint = endpoint_currency
    if stranded is not None:
        return RateNotComparable(
            reason=(
                f"{stranded.amount!r} {stranded.currency.value} of the {outlay.amount!r} "
                f"{outlay.currency.value} that left the stream never came home: the declared "
                "way out will not carry the "
                "remainder the purchase could not deploy. Measuring the return on the whole "
                "outlay prices that amount at zero and netting it off prices it at par, "
                "nothing declares which it is worth, and both produce a figure that looks "
                "like a rate. The amount that reaches a spendable endpoint is unaffected and "
                "is reported, with the remainder beside it."
            ),
            missing="a declared way home for the remainder, or a declared value for cash "
            "stranded at a venue",
        )
    # One guard for one rule: what left and what came back have to be in one currency, because
    # a money-weighted return over two of them is not a rate of anything.
    if outlay.currency is not endpoint:
        return RateNotComparable(
            reason=(
                f"the outlay is {outlay.currency.value} and what comes back is "
                f"{endpoint.value}. A money-weighted return over two currencies is "
                "not a rate of anything, and valuing one of them in the other needs a rate "
                "that values a currency for a return. Neither rate this system has is one: a "
                "channel rate is a transaction price, and the official rate is what the law "
                "says an income was worth. The amount that reaches a spendable endpoint is "
                "unaffected and is reported."
            ),
            missing="a declared valuation rate for a date",
        )
    received = money.total([amount for _, amount in arriving], endpoint)
    if any(amount.amount < 0.0 for _, amount in arriving) or received.amount <= 0.0:
        return RateNotComparable(
            reason=(
                f"the round trip returned {received.amount!r} {endpoint.value} against an "
                f"outlay of {outlay.amount!r}, over {len(arriving)} arrival(s). A series that "
                "is not one payment out followed by receipts has no single internal rate of "
                "return, and extrapolating one past the bracket would invent a figure. The "
                "amounts are reported as they stand."
            ),
            missing="a conventional series -- one payment out at the start, receipts after it",
        )
    year_fraction = day_count(_day_count_of(prepared))
    if all(year_fraction(span.start, on) == 0.0 for on, _ in arriving):
        # `internal_rate_of_return`'s precondition is one payment out at the start and receipts
        # **afterwards**: money out and the same money back on one date discounts to zero at
        # every rate, so the bracket never crosses and the root find raises. A typed absence
        # rather than a raise, because it is a fact about the round trip.
        return RateNotComparable(
            reason=(
                f"{outlay.amount!r} {outlay.currency.value} left the stream on "
                f"{span.start.isoformat()} and {received.amount!r} {endpoint.value} came back "
                f"by {span.end.isoformat()}, which {_day_count_of(prepared)!r} measures as no "
                "time at all. A return over a span of zero length is not a rate -- every rate "
                "discounts these flows to the same nothing, so reporting one would be choosing "
                "a number the arithmetic does not distinguish. The dates are named beside the "
                "convention because a convention can measure two of them as one: what is "
                "refused is the span the rate would be annualised over, not the calendar. The "
                "amounts are reported as they stand."
            ),
            missing="a span the declared convention measures as more than no time",
        )
    flows: list[CashFlow] = [(0.0, -outlay.amount)]
    flows.extend((year_fraction(span.start, on), amount.amount) for on, amount in arriving)
    return NominalRate(internal_rate_of_return(flows))


def _rests_on(
    prepared: _Prepared,
    projected: Projected,
    *,
    span: DateRange,
    horizon: DateRange,
    continuation: ContinuationAssumption,
    carried: QuotationHolds | None,
) -> tuple[str, ...]:
    """The stated assumptions this outcome depends on, sorted and in words (FR-025).

    The continuation assumption appears **only where it bites** -- where the last arrival is
    before the end of the horizon -- because listing it on a tuple that runs to the horizon
    would claim a dependency the figure does not have.
    """
    stated: list[str] = []
    if span.end < horizon.end:
        stated.append(
            f"the proceeds of {prepared.declared.id!r} reach a spendable endpoint on "
            f"{span.end.isoformat()}, before this comparison's horizon ends on "
            f"{horizon.end.isoformat()}, and the declared continuation assumption is "
            f"{continuation.value!r}: they sit as cash and earn nothing. Nothing is "
            "reinvested, because reinvestment would need terms nobody declared."
        )
    match projected, prepared.plan:
        case FundProjection(), _:
            stated.extend(projected.rests_on)
        case CashProjection(), CashAssumptions():
            # Nothing is added, and the emptiness is the claim: a balance is struck at no
            # quotation and states no belief about a future spread, so a figure it produces
            # rests on the declarations alone (FR-021).
            pass
        case Projection(), Assumptions():
            stated.append(
                f"coupons are handled under the {prepared.plan.coupon_policy!r} policy and "
                f"disposals consume lots {prepared.plan.consumption_method!r}; both are the "
                "owner's stated choices and both change the answer"
            )
        case _:  # pragma: no cover -- `_plan_for` has already refused a mismatch
            raise ValueError(
                f"{prepared.declared.id!r} reached the assumptions summary with a projection "
                f"of type {type(projected).__name__} and run settings of type "
                f"{type(prepared.plan).__name__}, a pairing _plan_for refuses."
            )
    if carried is not None:
        stated.append(quotation.rests_on(carried))
    return tuple(sorted(stated))


def _carried_quotation(
    prepared: _Prepared,
    projected: Projected,
    *,
    purchased_on: date,
    quotation_holds: QuotationHolds,
) -> QuotationHolds | None:
    """The belief either leg of this round trip leaned on, or ``None`` where neither did.

    FR-018, and either leg is enough: a hold-to-maturity candidate states no early exit and its
    purchase price is still a quotation carried to the settlement date. A trade struck on the
    quotation's own day carried nothing.
    """
    quoted = prepared.access.quote
    if quoted is not None and quoted.observed_on != purchased_on:
        return quotation_holds
    sold = projected.sold_early if isinstance(projected, Projection) else None
    if sold is not None and sold.quoted_on != sold.on:
        return quotation_holds
    return None
