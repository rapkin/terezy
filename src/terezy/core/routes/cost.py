"""``cost_one``: the only function that costs a route. Everything else consults it.

FR-029: *every candidate route MUST be costed **in full, through the same path as the
recommendation** -- never summarised, estimated, or costed by a cheaper approximation. A
comparison whose alternatives were priced differently from its winner is not a comparison; it
is a recommendation with decoration.* That requirement is satisfied structurally: there is one
costing function in this package, ranking is defined as calling it once per candidate, and
execution derives its ledger events from the figure it returned rather than recomputing one
beside it (research.md D3, D5).

**The two dates mean different things and are separate arguments.** ``on_date`` is when the
money moves: it decides whether a leg is inside its availability window and which month a cap
belongs to. ``as_of`` is when the question is asked: it decides staleness. Conflating them
would make a projection into the future report every one of its inputs as stale, by years.
Neither is read from a clock; both are inputs to the run and are recorded in the manifest
(research.md D9).

## The cost convention, stated once and in full

A declared premium admits two readings, and getting this wrong once already produced a wrong
number, so the resolution is written out rather than assumed.

**The conversion happens at the rate actually transacted at.** A premium ``p`` against a
reference ``r`` means the price is ``r + p`` when buying the unit currency and ``r - p`` when
selling, and that is the rate the money crosses at. 10 000 UAH at a P2P price of 45 buys
222.22 USD, which is what the screen says and what the venue would hand over. The reference
itself is never transacted at, which is what FR-010's prohibition on a mid-rate protects; the
side taken and the channel used are recorded in ``channels_applied`` (FR-011).

**The spread is then derived from that conversion**, not charged before it: it is the
difference between the value handed over and what the arriving amount is worth at the
reference, expressed in the sending currency. Because it comes from the same effective rate
the conversion used, the components sum to the whole cost exactly rather than approximately,
and FR-003's attribution closes on the nose.

**Two figures, and both are reported.** They differ on the buy side and the difference is the
whole point:

* ``channels.loss_fraction`` -- **the cost**: ``p / (r + p)`` buying, ``p / r`` selling. What
  fraction of the money the spread took. 6.67% at §4.3.1's numbers.
* ``channels.spread_over_reference`` -- ``p / r``, the spread over the reference *rate*.
  7.14% at the same numbers, and the figure §4.3.1 itself quotes.

**This is a correction, recorded because the wrong version shipped.** FR-004 originally named
``p / r`` as *the* cost, on the reading that §4.3.1 defined it, and the first implementation
did exactly that: it charged ``p / r`` of the amount and converted the remainder at the
reference. That reproduced the mandated percentage exactly and reported **221.09 USD arriving
where the venue pays 222.22** -- an implied all-in price of ``r / (1 - p/r)`` = 45.23 rather
than 45. The arriving amount was wrong, not merely differently framed, and no amount of
internal consistency rescues a figure that says the owner ends up with less money than he
does.

§4.3.1 labels its own arithmetic illustrative -- "substitute the live rate; this is
illustrative" -- so reading it as a definition of cost was the error. FR-004 was corrected
rather than the arithmetic bent to it. On the **sell** side the two conventions coincide
exactly (``N(1 - p/r) * r`` is ``N(r - p)``), so only the buy side moved.

## How a cost in a foreign currency becomes a component

Components are all in the sending currency, because otherwise they could not be added at all:
``money.add`` refuses a mismatch, which is exactly the protection wanted. A fee charged
mid-route in a foreign currency is therefore valued in the sending currency at the reference
rate of the conversion it crossed -- a **valuation**, not a transaction, so FR-010 is not in
play: no money moves at a reference without a declared side's spread being charged first.

The valuation factor is built **per leg, from the channel that leg crossed**, and that detail
is what makes the attribution exact. Each conversion preserves value except for what it
charged: an amount ``N`` worth ``N*f`` before a buy leg leaves as ``(N - c)/r`` units worth
``((N - c)/r) * (f*r) = (N - c)*f`` after it. So ``value in - value out`` is exactly the cost
charged, leg by leg, and the route's components close on the nose even where two legs cross
channels quoting different references.

## What this function refuses to do

* **Cost a destination without a stream and a route.** There is no signature for it; the key
  is a ``FundingPath`` triple with no partial form (FR-008).
* **Reverse the inbound route to get a round trip.** The exit route is declared, and a route
  with no ``partner_route`` yields ``ExitCostUnknown`` -- never the one-way figure promoted
  into its place (FR-027, FR-030).
* **Fold ``disruption_probability`` into a cost.** It rides beside the figure (FR-026).
* **Clamp anything.** Fees over the amount leave ``arrived`` at or below zero, and
  ``fraction`` may exceed ``1.0``. Predecessor defect B13 was exactly a ``max(gross - fee, 0)``
  that made money vanish with no diagnostic.
* **Branch on a route, venue or provider id.** Behaviour comes from declared fields; the only
  branching is ``leg.kind`` through the registry, and it selects an algorithm.
* **Re-validate the chain.** Currency and venue continuity is a structural property of the
  declaration and is checked at load, where the error can name the file and the leg index
  (research.md D6). The same applies to a ``partner_route`` pointing at an inbound route,
  which the resolver refuses (FR-027). What *is* checked here is the per-leg consistency the
  arithmetic cannot proceed without -- an ``fx`` leg with no channel, a channel on a leg that
  converts nothing -- because the only way to satisfy such a declaration would be to invent a
  rate.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date

from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives import staleness as stale
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.staleness import ObservationKind, StalenessVerdict
from terezy.core.results.ramp import (
    CostComponent,
    ExitCostUnknown,
    OneWayCost,
    RampCost,
    RoundTripCost,
    RouteUnusable,
)
from terezy.core.routes import channels as fx
from terezy.core.routes import legs as leg_module
from terezy.core.routes.channels import FxChannel, Side
from terezy.core.routes.legs import FX, Leg, LegOutcome, Route
from terezy.core.routes.path import FundingPath


@dataclass(frozen=True, slots=True)
class _Walk:
    """The state carried along a chain of legs. A fold's accumulator, not an object.

    Frozen and replaced rather than mutated, so each step is a pure function of the step
    before it -- which is what makes the whole costing trivially deterministic. Private,
    because it is the shape of the fold rather than part of any result.
    """

    amount: Money
    """What is in hand at this point, in the currency reached so far."""

    factor: float
    """Sending-currency value of one unit of :attr:`amount`'s currency. See the module
    docstring on why this is built per leg from the channel that leg crossed."""

    factor_sources: Provenance
    """The sources of the rates the factor was built from, so a translated component still
    admits which quotes it rests on."""

    spread: Money
    """Conversion spread so far, in the sending currency."""

    percentage: Money
    """Percentage fees so far, in the sending currency."""

    fixed: Money
    """Fixed fees so far, in the sending currency."""

    channels: tuple[str, ...]
    spreads: tuple[float, ...]
    """One rate-space spread per converting leg, parallel to :attr:`channels`.

    §4.3.1's own figure, carried to the result so SC-002's "both figures present, each
    labelled" holds of the record and not only of a function a caller could call. Per leg
    rather than summed: §4.3.1 is about one conversion, and adding rate-space spreads across
    legs would invent a quantity nothing means.
    """
    """Channels applied so far, in leg order."""

    latency_days: int
    """Latency so far, summed over legs."""

    ceiling: Money | None
    """The tightest declared monthly cap met so far, in the sending currency."""

    disruption: float
    """The largest single-leg disruption probability met so far. Never compounded -- see
    ``RampCost.disruption_probability``."""

    staleness: StalenessVerdict
    """Merged verdict over every declaration consulted so far."""


def _route_for(routes: Mapping[str, Route], path: FundingPath) -> Route:
    """The declared route a path names, or a raise naming what is known.

    The path is built *from* declared routes, so a name that does not resolve means the
    caller assembled a path for a route that was never declared -- a programmer error rather
    than a fact about the money, and therefore a raise rather than a typed failure. The same
    reasoning as ``conventions._resolve``.
    """
    if path.route_id not in routes:
        raise KeyError(
            f"unknown route {path.route_id!r}: a funding path names a declared route. "
            f"Known routes: {sorted(routes)}"
        )
    route = routes[path.route_id]
    if route.destination != path.destination_id:
        raise ValueError(
            f"route {route.id!r} ends at {route.destination!r}, but the funding path names "
            f"{path.destination_id!r} as its destination. The triple has to be coherent: a "
            "path is built from a route, so a disagreement is a construction error, and "
            "reporting it as a fact about the money would invite callers to build "
            "mismatched paths and read the answer as a cost (FR-008)."
        )
    return route


def _initial(amount: Money) -> _Walk:
    """A walk that has spent nothing, in the currency the money starts in."""
    currency = amount.currency
    return _Walk(
        amount=amount,
        factor=1.0,
        factor_sources=prov.EMPTY,
        spread=money.zero(currency),
        percentage=money.zero(currency),
        fixed=money.zero(currency),
        channels=(),
        spreads=(),
        latency_days=0,
        ceiling=None,
        disruption=0.0,
        staleness=stale.UNASSESSED,
    )


def _unusable(
    path: FundingPath,
    constraint: str,
    reason: str,
    *,
    required: Money | None = None,
    actual: Money | None = None,
) -> RouteUnusable:
    """A refusal, with its constraint named and its gap computed once.

    ``shortfall`` is ``required - actual`` in every case, which reads as a shortfall against
    a minimum and as a (negative) excess against a maximum. One subtraction, one direction,
    so the figure the owner sees does not depend on which constraint bound.
    """
    shortfall = None if required is None or actual is None else money.sub(required, actual)
    return RouteUnusable(
        path=path,
        binding_constraint=constraint,
        required=required,
        actual=actual,
        shortfall=shortfall,
        reason=reason,
    )


def _availability(leg: Leg, path: FundingPath, on_date: date) -> RouteUnusable | None:
    """Whether this leg works on the date the money moves.

    A leg's window is **a fact** about the corridor, with a source -- "this closed in March
    2025" -- and never an assumption. A regime transition is the assumption, and it lives in
    scenario data with an explicit marker, precisely so an output can tell "closed because it
    closed" from "closed because I guessed a date" (research.md D8).
    """
    if leg.available_from is not None and on_date < leg.available_from:
        return _unusable(
            path,
            "leg.available_from",
            f"leg {leg.index} does not open until {leg.available_from.isoformat()}, and the "
            f"movement is dated {on_date.isoformat()}",
        )
    if leg.available_until is not None and on_date > leg.available_until:
        return _unusable(
            path,
            "leg.available_until",
            f"leg {leg.index} closed on {leg.available_until.isoformat()}, and the movement "
            f"is dated {on_date.isoformat()}",
        )
    return None


def _limits(leg: Leg, amount: Money, path: FundingPath) -> RouteUnusable | None:
    """Whether this leg will carry this amount, with the gap named if it will not.

    Never silently adjusted (FR-014). Rounding up to a minimum would move money the owner
    did not agree to move; rounding down to a maximum would report a cost for a movement
    that never happened.
    """
    if leg.minimum is not None and money.compare(amount, leg.minimum) < 0:
        return _unusable(
            path,
            "leg.minimum",
            f"leg {leg.index} carries no less than {leg.minimum.amount!r} "
            f"{leg.minimum.currency.value}, and {amount.amount!r} reaches it",
            required=leg.minimum,
            actual=amount,
        )
    if leg.maximum is not None and money.compare(amount, leg.maximum) > 0:
        return _unusable(
            path,
            "leg.maximum",
            f"leg {leg.index} carries no more than {leg.maximum.amount!r} "
            f"{leg.maximum.currency.value}, and {amount.amount!r} reaches it",
            required=leg.maximum,
            actual=amount,
        )
    return None


def _translated(walk: _Walk, charge: Money, sending: Currency) -> Money:
    """One leg's charge, valued in the sending currency.

    Identity when the charge is already in the sending currency -- which is the common case
    and, importantly, keeps a zero exactly zero rather than a converted zero (FR-009).
    """
    if charge.currency is sending:
        return charge
    return money.convert(charge, to_currency=sending, rate=walk.factor, sources=walk.factor_sources)


def _factor_after(walk: _Walk, leg: Leg, channel: FxChannel) -> tuple[float, Provenance]:
    """The valuation factor after crossing a conversion, and the sources behind it.

    Buying the unit currency multiplies the factor by the reference, selling divides it: one
    unit of the currency just acquired is worth ``reference`` units of the one just given up,
    or its reciprocal. Built from *this* leg's channel, which is what keeps the attribution
    exact when two legs cross channels quoting different references.
    """
    _, role = fx.side_for(channel, leg.from_ccy, leg.to_ccy)
    factor = (
        walk.factor * channel.reference_rate
        if role is Side.BUY
        else walk.factor / channel.reference_rate
    )
    return factor, prov.merge(walk.factor_sources, channel.provenance)


def _aged(
    walk: _Walk,
    leg: Leg,
    channel: FxChannel | None,
    kinds: Mapping[str, ObservationKind],
    as_of: date,
) -> StalenessVerdict:
    """The walk's verdict extended with this leg's -- and its channel's -- observations.

    Two declarations, two kinds: a leg's fee schedule ages on the bank's timetable while the
    premium on the channel it uses ages in days. Aging both under one threshold is what
    FR-028 exists to prevent, so each is aged under the kind its own table declared and the
    verdicts are merged.
    """
    verdicts = [
        walk.staleness,
        stale.staleness_of(leg.provenance, kinds, kind=leg.kind_of_observation, as_of=as_of),
    ]
    if channel is not None:
        verdicts.append(
            stale.staleness_of(channel.provenance, kinds, kind=channel.kind, as_of=as_of)
        )
    return stale.merge_all(verdicts)


def _ceiling_after(walk: _Walk, leg: Leg, sending: Currency) -> Money | None:
    """The tightest declared monthly cap so far, in the sending currency."""
    if leg.monthly_cap is None:
        return walk.ceiling
    candidate = _translated(walk, leg.monthly_cap, sending)
    if walk.ceiling is None or money.compare(candidate, walk.ceiling) < 0:
        return candidate
    return walk.ceiling


def _applied(
    walk: _Walk,
    leg: Leg,
    outcome: LegOutcome,
    sending: Currency,
    staleness: StalenessVerdict,
) -> _Walk:
    """Fold one leg's outcome into the walk, with every charge valued where it started."""
    return replace(
        walk,
        amount=outcome.outgoing,
        staleness=staleness,
        spread=money.add(walk.spread, _translated(walk, outcome.conversion_spread, sending)),
        percentage=money.add(walk.percentage, _translated(walk, outcome.percentage_fee, sending)),
        fixed=money.add(walk.fixed, _translated(walk, outcome.fixed_fee, sending)),
        channels=(
            walk.channels
            if outcome.channel_applied is None
            else (*walk.channels, outcome.channel_applied)
        ),
        spreads=(
            walk.spreads
            if outcome.spread_over_reference is None
            else (*walk.spreads, outcome.spread_over_reference)
        ),
        latency_days=walk.latency_days + leg.latency_days,
        ceiling=_ceiling_after(walk, leg, sending),
        disruption=max(walk.disruption, leg.disruption_probability),
    )


def _step(
    walk: _Walk,
    leg: Leg,
    *,
    path: FundingPath,
    sending: Currency,
    channels: Mapping[str, FxChannel],
    kinds: Mapping[str, ObservationKind],
    on_date: date,
    as_of: date,
) -> _Walk | RouteUnusable:
    """Apply one leg: check what it will carry, then charge what it charges."""
    blocked = _availability(leg, path, on_date) or _limits(leg, walk.amount, path)
    if blocked is not None:
        return blocked
    channel = leg_module.channel_for(channels, leg)
    outcome = leg_module.cost_fn_for(leg.kind)(leg, walk.amount, channel)
    stepped = _applied(walk, leg, outcome, sending, _aged(walk, leg, channel, kinds, as_of))
    if leg.kind == FX and channel is not None:
        factor, sources = _factor_after(walk, leg, channel)
        stepped = replace(stepped, factor=factor, factor_sources=sources)
    return stepped


def _walk(
    legs: tuple[Leg, ...],
    walk: _Walk,
    *,
    path: FundingPath,
    sending: Currency,
    channels: Mapping[str, FxChannel],
    kinds: Mapping[str, ObservationKind],
    on_date: date,
    as_of: date,
) -> _Walk | RouteUnusable:
    """Fold every leg in declared order, stopping at the first that will not carry it."""
    for leg in legs:
        stepped = _step(
            walk,
            leg,
            path=path,
            sending=sending,
            channels=channels,
            kinds=kinds,
            on_date=on_date,
            as_of=as_of,
        )
        if isinstance(stepped, RouteUnusable):
            return stepped
        walk = stepped
    return walk


def _components(walk: _Walk) -> Mapping[CostComponent, Money]:
    """The three terms, every one present, in the sending currency.

    The closed enumeration bound to the fold's three accumulators, in one place. A component
    that does not apply is a declared zero rather than a missing key: "no conversion
    happened" and "conversion cost unknown" are different claims, and an absent key would
    read as the second while meaning the first (FR-009).
    """
    return {
        CostComponent.CONVERSION_SPREAD: walk.spread,
        CostComponent.PERCENTAGE_FEE: walk.percentage,
        CostComponent.FIXED_FEE: walk.fixed,
    }


def _fraction(total: Money, sent: Money) -> float:
    """Cost as a fraction of what was sent.

    **Not capped**, in either direction: a fixed fee on a small amount genuinely costs more
    than 100%, and a channel trading below its reference genuinely costs less than nothing.
    Capping either would be B13's silent clamp in a new hat.

    Sending nothing is the one case the division cannot answer. A route that charges nothing
    on nothing costs nothing, and the fraction is zero; a route with a flat fee charges it on
    nothing, and the fraction is infinite. The infinity is reported rather than replaced with
    a zero, because a zero would say the route is free -- the most flattering possible lie
    about it -- and because an infinite cost sorts last in a ranking, which is the correct
    treatment of paying to move nothing.
    """
    if sent.amount == 0.0:
        return 0.0 if total.amount == 0.0 else math.inf
    return total.amount / sent.amount


def _figure(sent: Money, walk: _Walk) -> tuple[Mapping[CostComponent, Money], float, Provenance]:
    """The parts a one-way and a round-trip figure are both assembled from.

    Shared so the two cannot be computed differently. They are unrelated *types* on purpose
    (FR-030), which is a statement about what may be assigned where -- not a licence for two
    arithmetics.
    """
    components = _components(walk)
    total = money.total(components.values(), sent.currency)
    provenance = prov.merge_all(
        [walk.amount.provenance, *(part.provenance for part in components.values())]
    )
    return components, _fraction(total, sent), provenance


def _one_way(sent: Money, walk: _Walk) -> OneWayCost:
    components, fraction, provenance = _figure(sent, walk)
    return OneWayCost(
        sent=sent,
        arrived=walk.amount,
        components=components,
        fraction=fraction,
        spreads_over_reference=walk.spreads,
        channels_applied=walk.channels,
        provenance=provenance,
        staleness=walk.staleness,
    )


def _round_trip(
    sent: Money,
    walk: _Walk,
    route: Route,
    *,
    path: FundingPath,
    routes: Mapping[str, Route],
    channels: Mapping[str, FxChannel],
    kinds: Mapping[str, ObservationKind],
    on_date: date,
    as_of: date,
) -> RoundTripCost | ExitCostUnknown:
    """The cost in and back out again, or a typed statement of why there is none.

    Computed by continuing the *same* walk through the declared exit route, so the exit's
    charges land in the same three components, valued in the same sending currency, as the
    inbound ones. Continuing the walk rather than starting a new one is what makes the
    round-trip attribution close: the amount that leaves the inbound route is the amount that
    enters the exit route, with nothing re-derived in between.

    A route with no declared partner yields :class:`ExitCostUnknown` (FR-030). So does a
    partner that will not carry what arrived -- the reason says which, because "nobody
    declared the way out" and "the way out will not take this much" are different facts and
    the owner acts on them differently. In neither case is the one-way figure promoted.
    """
    if route.partner_route is None:
        return ExitCostUnknown(
            reason=(
                f"route {route.id!r} declares no partner_route, so nobody has costed the way "
                "out. Round-trip cost is computed from a separately declared exit route and "
                "never by reversing the way in (FR-027), and the one-way figure is not "
                "promoted into its place (FR-030): a destination whose exit nobody has "
                "costed is not comparison-ready."
            ),
            missing_partner_for=route.id,
        )
    if route.partner_route not in routes:
        raise KeyError(
            f"route {route.id!r} names partner route {route.partner_route!r}, which is not "
            f"declared. A dangling partner is refused at load (FR-027) precisely so it "
            f"cannot become a missing round trip here -- ``null`` is the way to say nobody "
            f"has costed the exit. Known routes: {sorted(routes)}"
        )
    partner = routes[route.partner_route]
    exited = _walk(
        partner.legs,
        walk,
        path=path,
        sending=sent.currency,
        channels=channels,
        kinds=kinds,
        on_date=on_date,
        as_of=as_of,
    )
    if isinstance(exited, RouteUnusable):
        return ExitCostUnknown(
            reason=(
                f"exit route {partner.id!r} will not carry what arrives: "
                f"{exited.reason}. There is therefore no round-trip figure for this path, "
                "and the one-way figure is not promoted into its place (FR-030)."
            ),
            missing_partner_for=route.id,
        )
    components, fraction, provenance = _figure(sent, exited)
    return RoundTripCost(
        sent=sent,
        arrived=exited.amount,
        components=components,
        fraction=fraction,
        spreads_over_reference=exited.spreads,
        channels_applied=exited.channels,
        provenance=provenance,
        staleness=exited.staleness,
    )


def cost_one(
    path: FundingPath,
    amount: Money,
    *,
    routes: Mapping[str, Route],
    channels: Mapping[str, FxChannel],
    kinds: Mapping[str, ObservationKind],
    on_date: date,
    as_of: date,
) -> RampCost | RouteUnusable:
    """Cost one amount along one funding path. The only costing function in the project.

    Pure: no clock, no I/O, no state. Called twice with equal arguments it returns equal
    results, which is what makes C4 determinism reachable and what lets a ranking cost every
    candidate through this same function without any of them influencing another.

    Returns a :class:`RampCost` -- one way, round trip, latency, ceiling, status and
    disruption probability, attributed by component and carrying merged provenance and a
    staleness verdict -- or a :class:`RouteUnusable` naming the constraint that bound. Never
    an exception for a fact about the money, and never a zero cost standing in for a refusal.

    A negative amount raises. It is not a movement of money in the other direction -- that is
    a different route, declared separately (FR-027) -- so it can only be a caller's arithmetic
    error, and costing it would produce a negative cost that looks like a gain.

    **Two arguments the contract in ``contracts/route-costing.md`` also names are not here
    yet, and their absence is deliberate rather than an oversight.** ``streams`` arrives with
    User Story 2, which is what makes the stream/venue mismatch reportable and deployable
    capacity net of income tax computable; ``capacity_used`` arrives with User Story 3, which
    is where the monthly-cap accumulator lives. Both are feasibility inputs that produce more
    ``RouteUnusable`` reasons; neither changes an arithmetic already implemented, so adding
    them is an extension of this signature and not a second code path through it.
    """
    if amount.amount < 0.0:
        raise ValueError(
            f"an amount of {amount.amount!r} {amount.currency.value} cannot be moved along a "
            "route: a negative movement is not this route in reverse -- the way out is its "
            "own declaration (FR-027) -- so a negative amount here is an arithmetic error in "
            "the caller, and costing it would report a negative cost that reads as a gain"
        )
    route = _route_for(routes, path)
    if route.status == "closed":
        return _unusable(
            path,
            "route.status",
            f"route {route.id!r} is declared closed, so it carries nothing on "
            f"{on_date.isoformat()}. Its exclusion is recorded rather than silent (FR-014).",
        )
    walked = _walk(
        route.legs,
        _initial(amount),
        path=path,
        sending=amount.currency,
        channels=channels,
        kinds=kinds,
        on_date=on_date,
        as_of=as_of,
    )
    if isinstance(walked, RouteUnusable):
        return walked
    return RampCost(
        path=path,
        one_way=_one_way(amount, walked),
        round_trip=_round_trip(
            amount,
            walked,
            route,
            path=path,
            routes=routes,
            channels=channels,
            kinds=kinds,
            on_date=on_date,
            as_of=as_of,
        ),
        latency_days=walked.latency_days,
        ceiling=walked.ceiling,
        status=route.status,
        disruption_probability=walked.disruption,
    )
