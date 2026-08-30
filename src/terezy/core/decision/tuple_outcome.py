"""The join: an instrument bought through a route from a stream, and what comes back.

Everything built before this computes one term of the constitution's unit of analysis and
says in writing that it ignores the others. This module composes them, and **it computes
nothing of its own beyond summing what they return** (research.md D1). Every term comes from
the call that owns it: 002's :func:`terezy.core.routes.cost.cost_one` for the way in, 001's or
006's projection for the holding and its tax, the same module's ``cost_exit`` for each amount
the instrument releases. A figure this module invented would have no owner, and no test would
know where to check it.

Its only original content is **the chaining rule and the refusals**, and that is where it can
be wrong.

## The three seams, and why all of them are anchored

    the tuple's stream == the stream the way in is costed from
    stream --[ way in ]--> (venue, currency) == where the purchase happens
    where the proceeds land == (venue, currency) --[ way out ]--> a spendable endpoint

Feature 004 learned the cost of leaving one of these open. Its exit chain was anchored at
neither end: money moved between venues for free, and the record still read as a coherent
three-hop journey -- an arriving amount in one currency beside a cost fraction computed in
another. The same failure is available here three times, so all three are checked -- both
halves of the two positional ones (the venue **and** the currency) -- and a mismatch is a
typed refusal naming both sides. Bridging one would be an invented leg at an invented rate,
which is the single most tempting fabrication in this feature: the declarations look adjacent.

The first seam has no venue in it and is the easiest to miss for exactly that reason: the way
in is costed from the *candidate's* stream and everything else reads the *tuple's*, so two
strings hold one fact. A tuple funded on paper from the dollar contract income and costed over
the free domestic hryvnia route is the shape of it, and every figure it produced looked right.

## What travels the way out, and why it is a series

Once something is bought, the amount going home is no longer the amount that arrived. It is
whatever the holding released -- a coupon, a distribution, a redemption -- **on the date it
released it**, and each release travels the declared way out and is charged what that chain
charges. A fixed fee does not scale, so applying a round-trip *fraction* to a coupon would be
a fabricated figure that looks exactly like a real one.

This is also what makes "no reinvestment" (FR-025) structural rather than a rule to remember:
money that reaches a spendable endpoint has left the model, so there is nothing sitting
anywhere for an undeclared reinvestment assumption to be applied to.

## The rate, and where it refuses

The comparable figure is a money-weighted return over the tuple's **actual span**, from the
first outlay to the last arrival, with ramp and settlement latency inside it because waiting
is a cost (FR-015, owner decision 2026-08-22). It is
:func:`terezy.core.results.hurdle.internal_rate_of_return` over the arrivals on their own
dates, against the money that was **actually invested** -- what left the stream, less any
remainder the purchase could not deploy. That is the same root find that produces feature
001's benchmark, which is what makes hurdle-versus-tuple one kind of number against the same
kind.

**It refuses where those amounts are not all in one currency**, and that is reachable in the
shipped registry rather than a theoretical case: the dollar contract income reaching a hryvnia
fund produces a dollar outflow and hryvnia inflows, and an internal rate of return over the
two is not a rate of anything. Valuing one in the other needs a rate that values one currency
in another **for a return**, and nothing declares one: a channel rate is a transaction price,
and the official rate feature 011 brought is a legal reference for what an income was worth --
reusing either to score a return conflates a role rather than filling this one. So
the **amount** is reported and the **rate** is a typed absence naming what is missing, on
``RealTermsUnavailable``'s precedent, and the comparison keeps such a tuple out of the ranking
while showing it (002's ``Ranking.not_comparable``, unchanged).

## No clock

``horizon.start`` is when the money leaves the stream; the purchase happens the way in's
declared latency later; every other date comes from a declaration or from the projection.
``as_of`` is when the question is asked and decides staleness only. Neither is read from a
clock, and there may never be one here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Final, Literal, assert_never

from terezy.core.errors import InconsistentTerms, LedgerInvariantError
from terezy.core.instruments import fund as fund_terms
from terezy.core.instruments import terms as instrument_terms
from terezy.core.instruments.fund import FundDeclaration
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
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import fund as fund_results
from terezy.core.results import project as bond_results
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
    InstrumentRefused,
    NoExitRouteDeclared,
    NoExitTermsDeclared,
    Part,
    PartContribution,
    PlanDoesNotFitInstrument,
    RateNotComparable,
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
)
from terezy.core.routes import cost
from terezy.core.routes.cost import Junction
from terezy.core.routes.legs import RouteStatus
from terezy.core.routes.path import (
    EXIT_BY_IDENTITY,
    Candidate,
    DeclaredExit,
    ExitByIdentity,
    ExitChain,
    ExitChoice,
    FromTheDeclaration,
    exit_segments_of,
    segments_of,
)
from terezy.core.scenarios import early_exit
from terezy.core.scenarios.early_exit import SpreadHolds
from terezy.core.tax.interface import TaxClass

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping

    from terezy.core.instruments.access import InstrumentAccess
    from terezy.core.primitives.staleness import ObservationKind
    from terezy.core.results.coverage import SpendableEndpoint
    from terezy.core.routes.channels import FxChannel
    from terezy.core.routes.legs import Route
    from terezy.core.streams.streams import IncomeStream

Declared = InstrumentDeclaration | FundDeclaration
"""The two declaration kinds a tuple can name, matched with ``match``.

⚙ **A two-armed match, and the seam is recorded rather than hidden.** The two projections
return different shapes, so the join has to know which one to call. That is a branch on a
**declaration kind** -- an algorithm, which Principle II leaves as code -- and never a branch
on an instrument id, which it forbids and which ``tests/contract/test_h1_data_only.py``
scans for. Adding a third instrument is data; adding a third kind is code, here and wherever
else the kind is dispatched on.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class Registries:
    """Every declared set the join reads, in one pure record.

    Passed in rather than loaded, because loading is the ``data`` layer's job and the core
    must be testable with no file on disk anywhere near the arithmetic -- the same reasoning
    ``results.project`` takes ``tax_classes`` by argument. The data layer builds one of these
    from a resolved data root; a test builds one by hand.
    """

    instruments: Mapping[str, InstrumentDeclaration]
    funds: Mapping[str, FundDeclaration]
    tax_classes: Mapping[str, TaxClass]
    access: Mapping[str, InstrumentAccess]
    routes: Mapping[str, Route]
    channels: Mapping[str, FxChannel]
    streams: Mapping[str, IncomeStream]
    kinds: Mapping[str, ObservationKind]
    spendable: frozenset[SpendableEndpoint]

    spread_holds: SpreadHolds
    """The owner's declared belief that a quoted resale spread holds at a future exit date.

    On the registries rather than on the question, because it is not a property of one question:
    two questions asked on one day must not be able to disagree about how a platform's quote
    behaves (015 FR-032). Required with no default -- an absent belief refuses at load, and a
    default here would be the invented number the declaration exists to prevent.
    """

    base_currency: Currency
    """The currency tax is assessed in (Principle VI's tax role).

    Read for exactly one thing: refusing a taxable instrument declared in another currency.
    Not for want of an official rate -- feature 011 built that -- but because the projection
    below holds a holding under one currency and sums its charges in it. See
    :class:`~terezy.core.results.tuple.TaxCurrencyConversionUnavailable`.
    """


def evaluate(
    tuple_: Tuple,
    *,
    amount: Money,
    horizon: DateRange,
    as_of: date,
    continuation: ContinuationAssumption,
    registries: Registries,
) -> TupleOutcome | TupleRefused:
    """Evaluate one tuple end to end, or say precisely why there is no outcome.

    Pure: no clock, no I/O, no state. ``amount`` leaves the stream on ``horizon.start`` and
    must be in the stream's currency; ``as_of`` decides staleness and nothing else;
    ``continuation`` is required with no default, because FR-025 forbids defaulting what an
    instrument terminating before the horizon does with its proceeds.

    The order of the checks is the order a reader would ask the questions in, and the **first**
    problem found is the one reported: an owner whose instrument is undeclared does not also
    need to be told that its route is closed. They run from the declarations (true of every
    run) through the seams (true of this tuple) to feasibility (true of this amount on this
    date).

    Raises only for a caller's construction error, on
    :func:`terezy.core.routes.cost.cost_one`'s reasoning: an amount in a currency the named
    stream does not deliver, a candidate whose junctions do not join, a way out naming an
    inbound route. Every fact about the *money* is a returned value.
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

    A private carrier for the same reason :class:`_Prepared` is one: it makes "both venue seams
    were anchored before anything was bought" a fact about the control flow rather than a rule
    spread over one long function.
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

    The order matters and is the plan's: the chaining rule first, because it is the part that
    can be silently wrong, and everything after it is a sum of calls that already work.

    ⚙ **``cost_one``'s own round-trip figure is deliberately unused.** This tuple's way out
    starts where the *instrument* releases its proceeds, which is not in general where the
    inbound chain ended, so that figure is about a different journey and reporting it would put
    a figure for one journey in the slot for another.
    """
    costed = cost.cost_one(
        tuple_.route_in,
        amount,
        routes=registries.routes,
        channels=registries.channels,
        streams=registries.streams,
        kinds=registries.kinds,
        on_date=horizon.start,
        as_of=as_of,
        spendable=registries.spendable,
    )
    if isinstance(costed, RouteUnusable):
        return RouteInUnusable(
            refused=costed,
            reason=(
                f"the way in to {prepared.access.bought_at!r} will not carry "
                f"{amount.amount!r} {amount.currency.value} on {horizon.start.isoformat()}: "
                f"{costed.reason}"
            ),
        )
    seam_in = _seam_in(tuple_, prepared, costed.one_way.arrived)
    if seam_in is not None:
        return seam_in
    # After the seam, not before, and the order is a decision rather than a habit: a seam
    # mismatch says the tuple is impossible at **any** amount in any month, while a cap says
    # it is impossible at *this* amount *this* month. Reporting the cap first hands the owner
    # a remedy that reads as actionable -- send at most the ceiling -- and sending less would
    # then reveal a seam the first refusal had concealed.
    capped = _over_the_monthly_cap(tuple_.route_in, costed.ceiling, amount)
    if capped is not None:
        return capped
    proceeds_at: Junction = (prepared.access.proceeds_to, prepared.currency.value)
    way_out = _way_out_chain(tuple_, prepared, proceeds_at, registries)
    if not isinstance(way_out, ExitChain):
        return way_out
    return _Routed(
        one_way=costed.one_way,
        latency_days=costed.latency_days,
        status=costed.status,
        disruption=costed.disruption_probability,
        proceeds_at=proceeds_at,
        chain=way_out,
    )


def _over_the_monthly_cap(
    path: Candidate, ceiling: Money | None, amount: Money
) -> RouteInCapExceeded | None:
    """Refuse an amount larger than the tightest monthly cap the way in declares (FR-016).

    ``cost_one`` reports the ceiling rather than refusing, and that is right one layer down:
    a cap is a fact about the rail, and what to do with the excess is the owner's declared
    fallback (``routes.capacity``). It is read **here** because a tuple has nowhere to put an
    excess -- an acquisition is one dated purchase event (FR-018) -- and reading it nowhere is
    what let a 5 000.00 cap deploy 10 000.00 and report ten units bought.

    The deferral goes in the refusal's own words rather than only in the specification,
    because the refusal is what a reader actually meets.
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
) -> TupleOutcome | TupleRefused:
    """Buy with what arrived, live the declared lifecycle, and send every release home."""
    bought = _acquire(prepared, tuple_.route_in, routed.one_way.arrived)
    if not isinstance(bought, _Acquisition):
        return bought
    projected = _project(
        prepared,
        bought,
        purchased_on=horizon.start + timedelta(days=routed.latency_days),
        horizon=horizon,
        tax_classes=registries.tax_classes,
        registries=registries,
    )
    if not isinstance(projected, Projection | FundProjection):
        return projected
    repatriated = _repatriate(
        tuple_, prepared, projected, routed=routed, as_of=as_of, registries=registries
    )
    if not isinstance(repatriated, tuple):
        return repatriated
    return _assemble(
        tuple_,
        prepared,
        projected,
        outlay=amount,
        one_way=routed.one_way,
        arrivals=tuple(arrival for arrival, _ in repatriated),
        way_out_costs=tuple(charged for _, charged in repatriated),
        endpoint_currency=_endpoint_currency(routed.chain, prepared, registries),
        undeployed=bought.undeployed,
        routed=routed,
        horizon=horizon,
        continuation=continuation,
        kinds=registries.kinds,
        as_of=as_of,
    )


# ---------------------------------------------------------------------------
# Resolving the declarations
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class _Prepared:
    """The declarations one tuple names, resolved and checked against each other.

    A private carrier, not a result: it exists so the fifteen lines of resolution happen once,
    in one order, and so the functions below cannot be handed an access declaration for one
    instrument and a currency from another.
    """

    declared: Declared
    access: InstrumentAccess
    currency: Currency
    plan: Assumptions | FundAssumptions
    stream: IncomeStream


def _instrument_side(
    tuple_: Tuple, registries: Registries
) -> tuple[Declared, InstrumentAccess, Currency] | TupleRefused:
    """The instrument, how it is reached, and what it trades in -- or the first thing missing.

    Split from :func:`_prepare` so each half is short enough to read in one go, and along the
    seam the constitution already draws: this is the instrument-and-tax side of the registry,
    and what follows is the route side.
    """
    declared = _declaration(tuple_.instrument_id, registries)
    if not isinstance(declared, InstrumentDeclaration | FundDeclaration):
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
    if tuple_.route_in.stream_id != tuple_.stream_id:
        return FundedFromAnotherStream(
            tuple_stream_id=tuple_.stream_id,
            route_stream_id=tuple_.route_in.stream_id,
            reason=(
                f"this tuple says it is funded from {tuple_.stream_id!r}, and its way in is "
                f"costed from {tuple_.route_in.stream_id!r}. Which income pays for a purchase "
                "is part of what the cost *is* (Principle VI), so the two cannot differ: the "
                "figures would be a ramp from one stream reported under the key of another, "
                "and both halves would look entirely reasonable. Neither is preferred over "
                "the other, because guessing which the caller meant would either re-cost a "
                "way in nobody named or rewrite the key the comparison is built on."
            ),
        )
    unknown = [name for name in segments_of(tuple_.route_in) if name not in registries.routes]
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
    """The declaration an id names, of either kind, or a refusal listing what is declared."""
    fund = registries.funds.get(instrument_id)
    if fund is not None:
        return fund
    bond = registries.instruments.get(instrument_id)
    if bond is not None:
        return bond
    return DeclarationMissing(
        part="instrument",
        what=f"instrument {instrument_id!r}",
        reason=(
            f"no declaration under instruments/ declares {instrument_id!r}. Declared: "
            f"{sorted([*registries.instruments, *registries.funds])}."
        ),
    )


def currency_of(declared: Declared) -> Currency:
    """What the instrument trades and pays in, from whichever declaration kind it is.

    Public because feature 014 anchors an enumeration's two ``Destination`` records on it -- the
    venue a purchase happens at, in the currency the instrument trades in -- and a second copy
    of *which field of which declaration kind holds the currency* is one fact in two places.
    """
    match declared:
        case InstrumentDeclaration():
            return declared.currency
        case FundDeclaration():
            return declared.unit_currency
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(declared)


def _unresolved_class(
    declared: Declared, tax_classes: Mapping[str, TaxClass]
) -> DeclarationMissing | None:
    """Every tax class the instrument names must be declared (FR-020).

    Checked here rather than left to the projection, which would report it as an instrument
    failure: a missing rule pack is a **declaration** that is missing, and FR-006 wants the
    part named so the remedy is a file in ``data/tax/`` rather than a search.
    """
    missing = sorted(
        {class_id for class_id in declared.tax_classes.values() if class_id not in tax_classes}
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
    a hryvnia rate against a dollar base and produced a plausible number. It is unreachable in
    the shipped registry -- every declared instrument is hryvnia -- and that is a property of
    today's data rather than of the arithmetic, which is why the guard exists.
    """
    if currency is base_currency or not declared.tax_classes:
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
    declared: Declared, exit_terms: Assumptions | FundAssumptions
) -> Assumptions | FundAssumptions | PlanDoesNotFitInstrument:
    """The run settings, checked against the declaration kind they are settings for."""
    match declared, exit_terms:
        case InstrumentDeclaration(), Assumptions():
            return exit_terms
        case FundDeclaration(), FundAssumptions():
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


def _seam_in(tuple_: Tuple, prepared: _Prepared, arrived: Money) -> SeamDoesNotChain | None:
    """The way in must end where and in the currency the purchase begins (FR-004).

    Both halves, and the venue half is the one that has no other guard: two hryvnia venues
    look identical to a currency check, and a way in that lands the money at the wrong one
    would produce a purchase funded by money that never got there.
    """
    left: Junction = (tuple_.route_in.destination_id, arrived.currency.value)
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

    Two anchors, and they are the second seam: the chain must **depart from where the
    instrument releases its proceeds**, and it must **end somewhere the owner actually
    spends**. A chain that stops short has not got the money out.
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

    Derived from the declarations it is safe by construction; asserted by a caller it is the
    bare statement that the instrument releases its proceeds somewhere the owner already
    spends from, and its whole content is a claim about the far end.
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

    :data:`~terezy.core.routes.path.FROM_THE_DECLARATION` reads them in the owner's own order,
    which is 002's rule and 003's, unchanged: a destination that is itself spendable needs no
    way out, and otherwise the arriving route's ``partner_route`` is the declared one. No
    partner still means ``ExitCostUnknown`` and no round-trip figure (FR-007, FR-030).
    """
    if not isinstance(choice, FromTheDeclaration):
        return choice
    if proceeds_at in cost.spendable_junctions(registries.spendable):
        return EXIT_BY_IDENTITY
    arriving = registries.routes[segments_of(tuple_.route_in)[-1]]
    partner = arriving.partner_route
    if partner is None:
        return NoExitRouteDeclared(
            unknown=ExitCostUnknown(
                reason=(
                    f"route {arriving.id!r} declares no partner_route, so nobody has costed "
                    "the way out. Round-trip cost is computed from separately declared exit "
                    "routes and never by reversing the way in (FR-027), and the one-way "
                    "figure is not promoted into its place (FR-030)."
                ),
                missing_partner_for=arriving.id,
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
    cost: Money
    undeployed: UndeployedCash | None


def _acquire(prepared: _Prepared, path: Candidate, arrived: Money) -> _Acquisition | TupleRefused:
    """Turn what arrived into units, at the declared price and the declared increment.

    **Bought with what arrived, never with what departed** (FR-003). The two differ by the way
    in's whole charge, and using the departing amount is the mistake that makes an expensive
    ramp invisible in the size of the holding as well as in the rate.

    The **increment is declared or it does not exist**: a bond declares ``min_unit`` and is
    bought in whole increments of it, and a fund declares none, so its arriving amount buys
    exactly what it buys. Rounding a fund's purchase to whole certificates would be inventing
    a term its declaration does not state; the minimum *number* of units it does declare is
    its own projection's check, refused there with its own shortfall.
    """
    price = _price_for(prepared)
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
        cost=spent,
        undeployed=_undeployed(prepared, price, increment, money.sub(arrived, spent)),
    )


def _undeployed(
    prepared: _Prepared, price: Money, increment: float, remainder: Money
) -> UndeployedCash | None:
    """What the purchase could not deploy, or ``None`` where there is no such thing.

    **A declaration with no increment leaves no remainder, by construction.** ``increment ==
    0.0`` is :func:`_min_unit`'s statement that none is declared, and then the arriving amount
    buys exactly what it buys -- so there is nothing left over to report, and a figure here
    would be a category error rather than a small number. What ``price * (arrived / price)``
    leaves behind in binary floating point is not money: the shipped MilTech fund at a net
    asset value of 1006.97 and an arriving 1007.00 produced ``-1.14e-13``, a **negative**
    "money that made the trip in and bought nothing" -- a state
    :class:`~terezy.core.results.tuple.UndeployedCash` forbids in its own words, which
    :func:`_rate` then subtracted to make the invested amount exceed the outlay, under a
    sentence reading "bought in increments of 0.0 unit(s)".

    Where an increment **is** declared the same arithmetic can land a hair either side of
    zero, so the comparison is the imported tolerance rather than ``== 0.0`` -- the same
    tolerance :func:`_whole_increments` uses two lines earlier, for the same reason and now in
    both directions.
    """
    if increment == 0.0 or is_close(remainder.amount, 0.0):
        return None
    return UndeployedCash(
        amount=remainder,
        venue_id=prepared.access.bought_at,
        reason=(
            f"{prepared.declared.id!r} is bought in increments of {increment!r} "
            f"unit(s) at {price.amount!r} {price.currency.value} each, so "
            f"{remainder.amount!r} of what arrived bought nothing. It is money that "
            "made the trip and is sitting where the purchase was made: it is not in "
            "the amount that reaches a spendable endpoint, because bringing it home "
            "would need a date nobody declared, and the rate is measured on what was "
            "actually invested rather than charging it as a loss."
        ),
    )


def _price_for(prepared: _Prepared) -> Money:
    """What one unit costs, from whichever declaration states it.

    A fund prices itself -- its declared net asset value plus the entry markup the assumed
    liquidity mode charges -- through the fund module's own function, so the price the join
    buys at is the price the projection records. A bond states no purchase price at all (a
    face value is what it repays), so the venue's declared quote is the price, and the
    resolver has already refused an access declaration that omits one for a bond or supplies
    one for a fund.
    """
    match prepared.declared, prepared.plan:
        case FundDeclaration(), FundAssumptions():
            return fund_terms.entry_price_for(prepared.declared, prepared.plan.liquidity_mode)
        case _:
            quoted = prepared.access.quote
            if quoted is None:  # pragma: no cover -- the resolver refuses this at load
                raise ValueError(
                    f"{prepared.declared.id!r} declares no price of its own and its access "
                    "declaration quotes none either. The resolver refuses that combination at "
                    "load, so reaching here means a Registries was built in code with a "
                    "declaration the data boundary would not have accepted."
                )
            return quoted.price


def _minimum_ticket(prepared: _Prepared) -> Money | None:
    """The smallest amount that may be invested, where the declaration states one.

    A bond states a minimum ticket in money. A fund states a minimum in **units**, which is a
    different constraint and is checked by its own projection against the quantity -- deriving
    a ticket from it here would be this module computing a figure the declaration does not
    contain, and it would report the wrong one the moment the price moved.
    """
    match prepared.declared:
        case InstrumentDeclaration():
            return prepared.declared.constraints.min_ticket
        case FundDeclaration():
            return None
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(prepared.declared)


def _min_unit(prepared: _Prepared) -> float:
    """The smallest buyable increment the declaration states, or ``0.0`` where it states none.

    ``1.0`` would be an invented increment -- rounding a fund's purchase to whole certificates
    is a term its declaration does not contain. ``0.0`` is read by :func:`_whole_increments` as
    *no increment*, and the arriving amount then buys exactly what it buys.
    """
    match prepared.declared:
        case InstrumentDeclaration():
            return prepared.declared.constraints.min_unit
        case FundDeclaration():
            return 0.0
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(prepared.declared)


def _whole_increments(arrived: Money, price: Money, increment: float) -> float:
    """As many whole declared increments as the arriving amount covers, and no fraction.

    ``increment == 0.0`` means *no increment is declared*, and the amount buys exactly what it
    buys -- see :func:`_min_unit`. Otherwise this is
    ``fixed_income._reinvest_whole_units``' arithmetic on a different amount, including its one
    subtlety: an exact multiple can land a hair below itself in binary floating point, and a
    bare floor would throw away a whole unit the owner could really buy. A ratio within the
    single project tolerance of a whole number is that whole number, and the tolerance is
    imported rather than redefined.
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
) -> Projection | FundProjection | TupleRefused:
    """Run the holding through the call that owns its lifecycle, and read the refusals.

    Nothing about the lifecycle happens here. What this function does is translate the owning
    call's own typed failures into tuple-level ones **without re-wording them**: the reason a
    fund owes no buyback belongs to the fund module, and the join's contribution is to say
    which of the round trip's parts the refusal came from.
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
        case _:  # pragma: no cover -- `_plan_for` has already refused a mismatch
            raise ValueError(
                f"{prepared.declared.id!r} reached the projection with run settings of type "
                f"{type(prepared.plan).__name__}, which _plan_for refuses. A Registries built "
                "in code has bypassed the check."
            )


def _early_exit(prepared: _Prepared, registries: Registries) -> EarlyExit | None:
    """What this holding is sold for if the horizon ends before its own terms do (015 FR-029).

    ``None`` where the access declaration quotes no resale price, which is every shipped
    declaration: the instrument then refuses naming ``access.resale_price`` and
    :func:`_bond_outcome` turns that into a missing declaration. Nothing is inferred from the
    purchase quote or the face value -- either would report a spread of zero.
    """
    quote = prepared.access.resale_price
    if quote is None:
        return None
    return EarlyExit(price_per_unit=quote.price, assumption=registries.spread_holds)


def _bond_outcome(
    prepared: _Prepared, outcome: bond_results.ProjectionOutcome
) -> Projection | TupleRefused:
    """A bond projection, or the refusal its own failure becomes."""
    match outcome:
        case Projection():
            return outcome
        case InconsistentTerms() if outcome.second_term == "access.resale_price":
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
    projected: Projection | FundProjection,
    *,
    routed: _Routed,
    as_of: date,
    registries: Registries,
) -> tuple[tuple[Arrival, WayOutCost], ...] | TupleRefused:
    """Every net amount the holding released, sent home along the declared way out.

    Netted **by date** rather than event by event, because the way out charges a flat fee per
    movement: a date on which the holding pays twice is one journey home and one fee, and
    repatriating each line separately would charge the flat part twice for money that
    travelled once. What travels is what the owner actually has that day.

    A date that nets **negative** is refused rather than absorbed into a later receipt. It
    would mean money travelling *in* along a route nobody costed, on a date nobody planned,
    and netting it forward would move a real outflow to a date it did not happen on -- quietly
    improving the rate.
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


def _over_the_way_out_cap(
    way_out: WayOutCost, released: Money, released_on: date
) -> WayOutCapExceeded | None:
    """Refuse a release larger than the tightest monthly cap the way out declares (FR-016).

    The way in's rule (:func:`_over_the_monthly_cap`) applied where FR-016 says it also
    applies. ``cost_exit`` reports the ceiling for ``cost_one``'s reason -- a cap is a fact
    about the rail and what happens to the excess is the owner's declared fallback -- and a
    caller that reads it nowhere repatriates past it in silence, which is what shipped: a
    1.00 hryvnia monthly cap on the shipped exit route produced a complete outcome reporting
    13 100.00 reaching the endpoint.

    Per release rather than per month, deliberately and with the gap stated on
    :class:`~terezy.core.results.tuple.WayOutCapExceeded`.
    """
    if way_out.ceiling is None or money.compare(released, way_out.ceiling) <= 0:
        return None
    ceiling = way_out.ceiling
    return WayOutCapExceeded(
        path=way_out.path,
        released_on=released_on,
        ceiling=ceiling,
        requested=released,
        excess=money.sub(released, ceiling),
        reason=(
            f"the way out declares a monthly ceiling of {ceiling.amount!r} "
            f"{ceiling.currency.value} and the holding released {released.amount!r} on "
            f"{released_on.isoformat()}, so {money.sub(released, ceiling).amount!r} of it "
            "cannot come home that month. The tuple is refused rather than repatriated up to "
            "the ceiling: splitting a release across months is the same deferred partial "
            "deployment as on the way in (FR-018, owner decision 2026-08-22), and reporting "
            "the remainder needs a declared fallback policy and the month's consumed "
            "capacity, neither of which a tuple carries. Declare a way out that carries it, "
            "or exit on a date whose release fits."
        ),
    )


def _released_by_date(projected: Projection | FundProjection) -> tuple[tuple[date, Money], ...]:
    """The holding's net-of-tax cash effect per date, in date order, purchase excluded.

    The purchase is excluded because the join already paid for it: it is the arriving amount
    turned into units, and it is reported as the ``entry`` part. Every other event is a real
    movement between the owner and the instrument, and dates that net to exactly zero are
    dropped -- there is nothing to send home, and sending nothing would still be charged a
    fixed fee by an exit chain that declares one.

    ⚙ **The tax comes from the charge, not from the charge event's amount** (feature 009).
    A ``TAX_CHARGE`` is an assessment memo that moves nothing -- ``tax_year.memo_amount``, the
    charge's own money at no magnitude -- so summing the events alone would send the **gross**
    coupon home and report a pre-tax amount and a pre-tax rate on a record whose
    :data:`~terezy.core.results.tuple.ACCOUNTS_FOR` says it is net of tax. That is the same
    defect ``results.schedule`` names for the reader-facing rows, and it is read the same way
    out of the same place: ``charges``, paired to the taxed event by its own sequence number.

    ⚙ **It is netted on the date the income accrued, and the settlement date is not modelled
    here.** Since 009 the liability leaves cash as a ``TAX_PAYMENT`` on a declared deadline in
    a later year, and that deadline lives in ``data/tax/timing/`` with the filing decisions
    that assemble the year -- none of which a :class:`Registries` carries. So this dates the
    outflow **earlier than it is due**, exactly as ``results.schedule``'s ``net`` column does,
    and the error runs one way: the money leaves sooner, so the rate is understated rather
    than flattered. Deferring it to a date nobody declared would be the other kind of guess.

    ⚙ **The direction claim above is about the dates only. On the base a percentage exit fee
    charges, the choice here is the *flattering* one.** Netting shrinks that base, so an
    arrival is ``(gross - tax) x (1 - pct)``, which exceeds the ``gross x (1 - pct) - tax`` of
    charging the fee on the gross by exactly ``pct x tax``. It is taken on correctness rather
    than on conservatism: the tax is a domestic liability settled in the base currency and
    never travels the way out, so charging a repatriation fee on it would invent a journey.
    Stated because the two claims point opposite ways and a reader is owed both.
    """
    ledger = projected.ledger
    currency = ledger.base_currency
    taxed_on = {event.sequence: event.occurred_on for event in ledger.applied}
    by_date: dict[date, list[Money]] = {}
    for event in ledger.applied:
        if event.kind is EventKind.PURCHASE:
            continue
        by_date.setdefault(event.occurred_on, []).append(event.amount)
    for charge in projected.charges:
        taxed = taxed_on.get(charge.event_sequence)
        if taxed is None:  # pragma: no cover -- both projections renumber before they fold
            raise LedgerInvariantError(
                f"tax charge on event {charge.event_sequence} names no event in this ledger, "
                "so there is no date to net it on. Dropping it would send the gross amount "
                "home and understate nothing visibly -- every part line would still read "
                "correctly. Both projections renumber their charges onto the combined stream "
                "before folding it, so reaching here means that renumbering was skipped."
            )
        # ⚙ **Which drop this catches, and which it cannot.** It catches a charge naming an
        # event that is not in the ledger. It does not catch *two* charges on one event: both
        # chargers key their pairing by `event_sequence` in a dict, so the second would
        # already have replaced the first before `charges` was built, and the loss happens
        # upstream of anything here. Not reachable today -- each charger walks the events once
        # -- and recorded because it is the same shape as the drop above, on the same field.
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

A closed set naming what a *holding produces*, and **distinct from** the ledger's
``CASH_ONLY_KINDS`` rather than narrower: the two overlap and neither contains the other,
because a redemption is a receipt that also closes a lot. The sets are drawn on different
axes -- that one is the kinds that touch no holding, this one is the kinds that are a receipt.
A fee is a charge rather than a receipt, and a tax charge is neither: since feature 009 it
moves nothing at all, and what it assessed reaches the ``tax`` line from the charge rather
than from the event. Each has a line of its own.
"""


def _assemble(
    tuple_: Tuple,
    prepared: _Prepared,
    projected: Projection | FundProjection,
    *,
    outlay: Money,
    one_way: OneWayCost,
    arrivals: tuple[Arrival, ...],
    way_out_costs: tuple[WayOutCost, ...],
    endpoint_currency: Currency,
    undeployed: UndeployedCash | None,
    routed: _Routed,
    horizon: DateRange,
    continuation: ContinuationAssumption,
    kinds: Mapping[str, ObservationKind],
    as_of: date,
) -> TupleOutcome:
    """Everything the owning calls returned, summed and chained. No new arithmetic here.

    Every amount below is a sum of figures a named call produced, and every part carries the
    name of that call so a reader can go and check it. The six parts are an **attribution**
    and not an addition: they are in up to three currencies and two of them -- the instrument's
    exit terms and its lifecycle receipts -- describe the same money from two sides, so a
    reader who added them up would be double-counting. What adds up is the series of arrivals,
    and that is :attr:`~terezy.core.results.tuple.TupleOutcome.reaches`.
    """
    reaches = money.total([arrival.amount for arrival in arrivals], endpoint_currency)
    provenance = prov.merge_all(
        [
            one_way.provenance,
            *(charged.provenance for charged in way_out_costs),
            _projection_provenance(projected),
            _declaration_provenance(prepared),
        ]
    )
    span = DateRange(
        start=horizon.start,
        end=max((arrival.arrived_on for arrival in arrivals), default=horizon.start),
    )
    return TupleOutcome(
        key=tuple_,
        outlay=outlay,
        parts=_parts(prepared, projected, one_way=one_way, way_out_costs=way_out_costs),
        arrivals=arrivals,
        reaches=reaches,
        implied_rate=_rate(
            prepared,
            outlay=outlay,
            undeployed=undeployed,
            arrivals=arrivals,
            endpoint_currency=endpoint_currency,
            span=span,
        ),
        span=span,
        horizon=horizon,
        undeployed=undeployed,
        routes=_standing(routed, way_out_costs),
        risk_class=prepared.access.risk_class,
        rests_on=_rests_on(
            prepared, projected, span=span, horizon=horizon, continuation=continuation
        ),
        accounts_for=ACCOUNTS_FOR,
        excludes=_excludes_of(prepared),
        provenance=provenance,
        # The costing's own verdicts, plus every source behind the outcome aged under the
        # kind its own citation declares. The third is not a tidier restatement of the first
        # two: it is the only thing that reaches the instrument's terms, its constraints, the
        # tax pack's rates and a fund's tables, none of whose core records names a kind and
        # none of which any other call ages (FR-019). Merging is a union at the strictest
        # reading, so a source both of them reach arrives once.
        staleness=stale.merge_all(
            [
                one_way.staleness,
                *(charged.staleness for charged in way_out_costs),
                stale.staleness_of_sources(provenance, kinds, as_of=as_of),
            ]
        ),
    )


def _standing(routed: _Routed, way_out_costs: tuple[WayOutCost, ...]) -> RouteStanding:
    """How usable both declared ways are, from the figures the costing already returned.

    Both, and never one: a status describing the way in alone on a record whose headline
    number is a round trip is the half-truth ``RampCost.status`` records about itself.

    A holding that released nothing has no way-out cost to read, and then the way out's
    standing is genuinely unknown rather than open -- but such a tuple has no rate either and
    is reported as not comparable, so there is no figure here for a reader to over-trust.
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
      decide how many units were bought and therefore every figure downstream. This feature is
      what made them load-bearing: before :func:`_acquire` nothing sized a purchase from them,
      which is exactly why they were the table left out;
    * a fund's :class:`~terezy.core.instruments.fund.LiquidityTerms`, **both tables**. The
      settlement delay moves the arrival date and therefore the rate -- 0 to 30 business days
      moves the shipped MilTech tuple from 0.17578 to 0.16553 -- and which of the two supplies
      it depends on the run: the assumed mode picks one, and the termination path reads the
      legal one whatever the mode. The join cannot tell which fired without re-deciding the
      exit, so it marks the pair. A mark present where it need not be costs a reader nothing;
      one absent where it belongs is Principle I's defect.

    **Not everything a declaration cites.** ``fee_context`` is recorded context for the
    declared yield and nothing accrues from it (``instruments.fund``, owner decision B), so it
    moves no figure and claiming a figure rests on it would make the mark mean less. The line
    is *can this table move a number*, and it is asserted rather than left to judgement:
    ``tests/contract/test_marks_survive_the_join.py`` partitions every sourced table of the
    declarations a tuple names into those that reach the outcome and those classified as
    unable to move one.

    **The venue quote is not here either, and that is not an omission.** The join did size the
    purchase from it, and the purchase event the projection recorded carries the amount it
    produced -- so the quote's citation arrives through :func:`_projection_provenance`
    already. Merging it a second time changed no outcome, which is how a duplicate is
    recognised.
    """
    tables: list[Provenance] = []
    match prepared.declared:
        case InstrumentDeclaration():
            tables.append(prepared.declared.constraints.provenance)
        case FundDeclaration():
            tables.append(prepared.declared.liquidity.legal.provenance)
            tables.append(prepared.declared.liquidity.practice.provenance)
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(prepared.declared)
    return prov.merge_all(tables)


def _parts(
    prepared: _Prepared,
    projected: Projection | FundProjection,
    *,
    one_way: OneWayCost,
    way_out_costs: tuple[WayOutCost, ...],
) -> tuple[PartContribution, ...]:
    """Each of the six terms, with the call that produced it named (FR-005).

    Signed as the ledger signs things: negative for money leaving the owner. The
    ``exit_terms`` line is a **recorded zero** for an instrument whose declared way out charges
    nothing -- a bond redeeming at face value -- because a declared zero is a value like any
    other and only an *absent* declaration is a refusal (FR-009).
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
            "core.routes.cost.cost_exit -- charged once on each amount the instrument released",
        ),
    )
    return tuple(
        PartContribution(part=part, amount=amount, source=source) for part, amount, source in lines
    )


def _exit_terms_line(
    prepared: _Prepared, projected: Projection | FundProjection
) -> tuple[Money, str]:
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
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(projected)


def _purchase_amount(projected: Projection | FundProjection) -> Money:
    """The purchase event's own amount, read off the ledger rather than recomputed.

    Read back rather than reported from the join's own multiplication, so the ``entry`` line
    is the figure the projection actually charged: if the two ever differed, the ledger's is
    the one every other figure rests on.
    """
    for event in projected.ledger.applied:
        if event.kind is EventKind.PURCHASE:
            return event.amount
    raise LedgerInvariantError(  # pragma: no cover -- every projection opens with a purchase
        "a projection reached the join with no purchase event, so there is nothing the "
        "arriving money became. Every run this module builds opens with one."
    )


def _total_tax(projected: Projection | FundProjection) -> Money:
    """Every charge over the holding's life, from whichever result records it."""
    match projected:
        case Projection():
            return projected.hurdle.total_tax
        case FundProjection():
            return projected.total_tax
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(projected)


def _projection_provenance(projected: Projection | FundProjection) -> Provenance:
    """Every source the holding's own figures rest on."""
    match projected:
        case Projection():
            return projected.hurdle.provenance
        case FundProjection():
            return projected.provenance
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(projected)


def _day_count_of(prepared: _Prepared) -> str:
    """The convention this holding's own figures are annualised on.

    ⚙ The docstring used to say *the convention the instrument's own flows were **sized**
    with*, and that was only ever true of a schedule computed from a rate and a periodicity.
    A day count is a convention of computation: it turns a span of days into a fraction of a
    year. Whether it also sized anything is a fact about the declaration, not about the
    convention -- which is why the declaration is asked rather than a field read.
    """
    match prepared.declared:
        case InstrumentDeclaration():
            return instrument_terms.day_count_of(prepared.declared.terms)
        case FundDeclaration():
            return prepared.declared.day_count
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(prepared.declared)


def _excludes_of(prepared: _Prepared) -> frozenset[str]:
    """What this outcome fails to account for, beyond what every outcome fails to account
    for.

    :data:`~terezy.core.results.tuple.EXCLUDES` is the floor. What a particular declaration
    adds to it is the declaration's answer, not this module's decision (013 FR-023).
    """
    match prepared.declared:
        case InstrumentDeclaration():
            return EXCLUDES | instrument_terms.excludes_of(prepared.declared.terms)
        case FundDeclaration():
            return EXCLUDES
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(prepared.declared)


def _rate(
    prepared: _Prepared,
    *,
    outlay: Money,
    undeployed: UndeployedCash | None,
    arrivals: tuple[Arrival, ...],
    endpoint_currency: Currency,
    span: DateRange,
) -> NominalRate | RateNotComparable:
    """The money-weighted return over the span, or a typed statement of why there is none.

    **The payment out at ``t=0`` is the money that was actually invested**: what left the
    stream, less any remainder the purchase could not deploy. The remainder is not lost -- it
    is cash sitting at the purchase venue -- and leaving it in the series would price it as a
    total loss, which is a figure more confident than its inputs in the mirror image of the
    flattering direction. On the shipped registry the difference is a 16% sovereign bond
    reported at -7% because 500.00 could not buy an eleventh unit.

    Netting it off assumes the remainder is recoverable at par, and it is not: it sits behind
    the same exit the holding does. That assumption is not buried here -- it is one of the
    outcome's own scope statements, in :data:`~terezy.core.results.tuple.EXCLUDES`.

    Time is measured with the **instrument's declared day-count convention**, from the first
    outlay -- the same convention that sized the instrument's own flows, so this rate and
    feature 001's hurdle are measured on the same clock. A hard-coded 365 here would make the
    two disagree in a way that reads as rounding and is not.

    The root find is
    :func:`terezy.core.results.hurdle.internal_rate_of_return`, unchanged: the same function
    that produces the benchmark, which is what makes hurdle-versus-tuple one kind of number
    against the same kind rather than two figures that resemble each other.

    Its precondition is a **conventional series** -- one payment out at the start, receipts
    afterwards -- and that precondition is checked here rather than discovered as an
    exception, because a series that fails it is a fact about this round trip (everything was
    eaten by fees, or nothing came back) and not a caller's mistake. A round trip with no
    arrivals at all falls into the same check rather than into a guard of its own: a total of
    nothing is not positive, and one statement covers both.
    """
    endpoint = endpoint_currency
    stranded = None if undeployed is None else undeployed.amount
    # One guard for one rule: the three amounts the series is built out of -- what left, what
    # stayed behind, what came back -- have to be in one currency, because a money-weighted
    # return over two of them is not a rate of anything.
    #
    # ⚙ **The third amount makes this turn on divisibility, and that is right rather than
    # inconsistent.** A hryvnia stream buying a dollar instrument and coming home in hryvnia
    # is a perfectly good single-currency series -- money left in UAH, money returned in UAH,
    # and the two conversions are costs inside it -- so it has a rate and refusing it would
    # throw away an honest figure. The moment the unit price does not divide the arriving
    # amount, a *dollar* remainder has to be netted off a *hryvnia* outlay, and that needs a
    # declared valuation rate, which nothing supplies. So the same tuple has a rate at one
    # amount and not at another: the difference is a fact about what the data allows, and the
    # refusal's own reason names the stranded amount and its currency so a reader can see
    # which.
    #
    # It is unreachable today, and by construction rather than by the shipped data. A
    # remainder needs a declared increment, and only an `InstrumentDeclaration` declares one:
    # `_undeployed` returns nothing at all where none is (which is a rule about this engine,
    # not about arithmetic, and is pinned in `tests/unit/test_infeasible_tuples.py`). A
    # foreign *bond* is then closed twice over -- `_foreign_tax_currency` refuses one that
    # declares tax classes, and the projection refuses one that does not the moment it pays
    # income of a kind no class covers -- and both halves are pinned in
    # `tests/unit/test_rate_and_horizon_boundaries.py`. A later feature that opens any of the
    # three fails a test rather than discovering this branch by accident.
    currencies = {outlay.currency, endpoint} | (set() if stranded is None else {stranded.currency})
    if len(currencies) > 1:
        stayed = (
            ""
            if stranded is None
            else (
                f", and {stranded.amount!r} {stranded.currency.value} stayed behind at "
                "the purchase venue"
            )
        )
        return RateNotComparable(
            reason=(
                f"the outlay is {outlay.currency.value} and what comes back is "
                f"{endpoint.value}{stayed}. A money-weighted return over two currencies is "
                "not a rate of anything, and valuing one of them in the other needs a rate "
                "that values a currency for a return. Neither rate this system has is one: a "
                "channel rate is a transaction price, and the official rate is what the law "
                "says an income was worth. The amount that reaches a spendable endpoint is "
                "unaffected and is reported."
            ),
            missing="a declared valuation rate for a date",
        )
    invested = outlay if stranded is None else money.sub(outlay, stranded)
    received = money.total([arrival.amount for arrival in arrivals], endpoint)
    if any(arrival.amount.amount < 0.0 for arrival in arrivals) or received.amount <= 0.0:
        return RateNotComparable(
            reason=(
                f"the round trip returned {received.amount!r} {endpoint.value} against an "
                f"outlay of {outlay.amount!r}, over {len(arrivals)} arrival(s). A series that "
                "is not one payment out followed by receipts has no single internal rate of "
                "return, and extrapolating one past the bracket would invent a figure. The "
                "amounts are reported as they stand."
            ),
            missing="a conventional series -- one payment out at the start, receipts after it",
        )
    year_fraction = day_count(_day_count_of(prepared))
    flows: list[CashFlow] = [(0.0, -invested.amount)]
    flows.extend(
        (year_fraction(span.start, arrival.arrived_on), arrival.amount.amount)
        for arrival in arrivals
    )
    return NominalRate(internal_rate_of_return(flows))


def _rests_on(
    prepared: _Prepared,
    projected: Projection | FundProjection,
    *,
    span: DateRange,
    horizon: DateRange,
    continuation: ContinuationAssumption,
) -> tuple[str, ...]:
    """The stated assumptions this outcome depends on, sorted and in words (FR-025).

    The continuation assumption appears **only where it bites** -- where the last arrival is
    before the end of the horizon -- because listing it on a tuple that runs to the horizon
    would be claiming a dependency the figure does not have, and a ``rests_on`` that is always
    the same is one a reader stops reading.
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
        case Projection(), Assumptions():
            stated.append(
                f"coupons are handled under the {prepared.plan.coupon_policy!r} policy and "
                f"disposals consume lots {prepared.plan.consumption_method!r}; both are the "
                "owner's stated choices and both change the answer"
            )
            if projected.sold_early is not None:
                stated.append(early_exit.rests_on(projected.sold_early.assumption))
        case _:  # pragma: no cover -- `_plan_for` has already refused a mismatch
            raise ValueError(
                f"{prepared.declared.id!r} reached the assumptions summary with a projection "
                f"of type {type(projected).__name__} and run settings of type "
                f"{type(prepared.plan).__name__}, a pairing _plan_for refuses."
            )
    return tuple(sorted(stated))
