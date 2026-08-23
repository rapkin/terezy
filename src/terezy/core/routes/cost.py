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
* **Assume a stream's money is already where the route begins.** A route whose ``origin`` is
  not the stream's arrival venue, or whose first leg moves a currency the stream does not
  deliver, is reported as unusable naming both sides (spec.md, Edge Cases). Costing it would
  price a journey that skips its own first and most expensive step.
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
from itertools import pairwise
from typing import Final

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
    SegmentAttribution,
)
from terezy.core.routes import channels as fx
from terezy.core.routes import legs as leg_module
from terezy.core.routes.channels import FxChannel, Side
from terezy.core.routes.legs import FX, Leg, LegOutcome, Route, RouteStatus
from terezy.core.routes.path import (
    FROM_THE_DECLARATION,
    Candidate,
    ComposedExit,
    ComposedPath,
    DeclaredExit,
    ExitByIdentity,
    ExitChain,
    ExitChoice,
    FromTheDeclaration,
    FundingPath,
    Segment,
    exit_segments_of,
    segments_of,
)
from terezy.core.streams.streams import IncomeStream

_COMPOSED_MINIMUM: Final = 2
"""How many segments a composition has at the least.

Named rather than written inline because it is a *definition* -- a chain of one is a declared
route, and a chain of none is not a journey -- and the two places that enforce it, the inbound
candidate and the exit chain, must enforce the same one."""


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

    segments: tuple[SegmentAttribution, ...]
    """The same charges, split by **segment** rather than by term (FR-020, research.md D7).

    Accumulated **beside** the three fields above and never summed into them. That is the trap
    this feature was warned about: the whole-candidate totals keep the exact addition order
    feature 002 established, because the rounding of a sum of sums is not the rounding of one
    fold, and reconstructing a total from segment subtotals would move numbers 002 recorded in
    a golden file. Each per-leg charge is translated **once** and added into both, so the two
    axes see the same figures in the same currency and differ only in association.

    One entry per segment, in chain order, growing as the fold crosses into a new segment. A
    declared route therefore ends with exactly one, which is not a special case anywhere.
    """


def _routes_for(routes: Mapping[str, Route], candidate: Candidate) -> tuple[Route, ...]:
    """The declared routes a candidate names, in chain order, or a raise naming what is wrong.

    A candidate is built **from** declared routes -- by hand for a :class:`FundingPath`, by
    :func:`terezy.core.routes.compose.compose` for a chain -- so a name that does not resolve,
    a chain of one, a junction that does not join, or a destination that is not where the last
    segment ends all mean the caller assembled something incoherent. Those are programmer
    errors rather than facts about the money, so they raise, on ``conventions._resolve``'s
    reasoning: reporting them as a cost failure would invite callers to keep building
    mismatched candidates and read the answer as a cost.

    ⚙ **A composed chain is re-validated here, and a declared route is not.** Venue and
    currency continuity *within* a declared route is a structural property of the declaration
    and is checked at load, where the error can name the file and the leg index (002
    research.md D6). A chain between routes has no file: it is assembled at query time, so this
    is the only place its junctions can be checked at all -- and an unchecked junction is
    exactly where an implicit conversion would appear, which FR-002 forbids outright.
    """
    chain = segments_of(candidate)
    if isinstance(candidate, ComposedPath) and len(chain) < _COMPOSED_MINIMUM:
        raise ValueError(
            f"a composed path names {len(chain)} segment(s), and a composition has at least two. "
            "A chain of one *is* a declared route and belongs in a FundingPath: costing it "
            "under the composed type would put one journey in a ranking under two shapes, and "
            "every report would then have to guess which it was looking at (FR-013)."
        )
    missing = [route_id for route_id in chain if route_id not in routes]
    if missing:
        raise KeyError(
            f"unknown route(s) {missing}: a candidate names declared routes. "
            f"Known routes: {sorted(routes)}"
        )
    resolved = tuple(routes[route_id] for route_id in chain)
    for position, (before, after) in enumerate(pairwise(resolved)):
        if (
            before.destination != after.origin
            or before.legs[-1].to_ccy is not after.legs[0].from_ccy
        ):
            raise ValueError(
                f"segments {position} and {position + 1} of this candidate do not join: route "
                f"{before.id!r} arrives as {before.legs[-1].to_ccy.value} at "
                f"{before.destination!r} and route {after.id!r} departs as "
                f"{after.legs[0].from_ccy.value} from {after.origin!r}. A junction converts "
                "nothing and charges nothing, so a chain whose venue or currency disagrees does "
                "not exist -- and bridging it would be an invented leg at an invented rate "
                "(FR-002)."
            )
    if resolved[-1].destination != candidate.destination_id:
        raise ValueError(
            f"the candidate ends at route {resolved[-1].id!r}, which arrives at "
            f"{resolved[-1].destination!r}, but names {candidate.destination_id!r} as its "
            "destination. The key has to be coherent: a candidate is built from routes, so a "
            "disagreement is a construction error, and reporting it as a fact about the money "
            "would invite callers to build mismatched candidates and read the answer as a cost "
            "(FR-008)."
        )
    return resolved


def _chain(candidate: Candidate, routes: Mapping[str, Route]) -> tuple[tuple[Leg, Segment], ...]:
    """Every leg of every segment, in order, each paired with the segment it belongs to.

    **The whole of "composition adds no arithmetic"** (research.md D1). What comes back is one
    flat sequence, and :func:`_walk` folds over it exactly as it folded over a single route's
    legs in feature 002. There is no second costing path to keep in step, which is what makes
    SC-002's "asserted by construction" a fact about the code rather than a comparison of two
    numbers that happen to agree.

    ``Leg.index`` is **renumbered across the concatenation**. Per-route indices repeat -- a
    two-leg route followed by a one-leg route gives ``0, 1, 0`` -- and a refusal saying "leg 0"
    twice in one chain is a message that cannot be acted on. For a declared route the
    renumbering is the identity, because the loader already numbers legs from zero.

    The :class:`~terezy.core.routes.path.Segment` travelling beside each leg is what lets a
    refusal name the **binding segment** (FR-015) and the attribution name the **charging
    segment** (FR-020) without either of them recomputing which route a leg came from.
    """
    paired: list[tuple[Leg, Segment]] = []
    for position, route in enumerate(_routes_for(routes, candidate)):
        segment = Segment(position=position, route_id=route.id)
        for leg in route.legs:
            paired.append((replace(leg, index=len(paired)), segment))
    return tuple(paired)


def legs_of(candidate: Candidate, routes: Mapping[str, Route]) -> tuple[Leg, ...]:
    """One candidate as one sequence of legs -- the only way a journey is assembled.

    A declared route's own legs, or the concatenation of a chain's, renumbered once across the
    whole. :func:`cost_one` walks what this returns and nothing else, so a composed candidate
    is not *costed like* a declared route: it is costed **by the same call**, over a longer
    tuple.

    Public because SC-002 is a claim about there being one producer of leg sequences, and a
    claim about a private helper is a claim a test cannot make.
    """
    return tuple(leg for leg, _ in _chain(candidate, routes))


def _stream_for(streams: Mapping[str, IncomeStream], path: Candidate) -> IncomeStream:
    """The declared income stream a path names, or a raise naming what is known.

    A raise rather than a typed failure, on exactly the reasoning of :func:`_route_for`: a
    funding path is built *from* the owner's declared streams, so a ``stream_id`` that does
    not resolve means the caller assembled a path for a stream nobody declared. That is a
    construction error rather than a fact about the money, and reporting it as a cost failure
    would invite callers to keep building unresolvable paths and read the answer as a cost.
    """
    if path.stream_id not in streams:
        raise KeyError(
            f"unknown income stream {path.stream_id!r}: a funding path names a declared "
            f"stream, because which stream funds a purchase is part of what a cost is "
            f"(FR-008). Known streams: {sorted(streams)}"
        )
    return streams[path.stream_id]


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
        segments=(),
    )


def _unusable(
    path: Candidate,
    constraint: str,
    reason: str,
    *,
    segment: Segment | None,
    required: Money | None = None,
    actual: Money | None = None,
) -> RouteUnusable:
    """A refusal, with its constraint named, its segment named and its gap computed once.

    ``shortfall`` is ``required - actual`` in every case, which reads as a shortfall against
    a minimum and as a (negative) excess against a maximum. One subtraction, one direction,
    so the figure the owner sees does not depend on which constraint bound.

    **The segment is dropped for a declared route** (data-model.md). A ``FundingPath`` names
    exactly one route and ``path`` already carries it, so a ``Segment(position=0, ...)`` beside
    it would be the same fact twice and would read as though something had been selected out of
    several. On a chain it is the whole point: ``leg.minimum`` on a three-segment candidate is
    not actionable until a reader knows which declaration to open.
    """
    shortfall = None if required is None or actual is None else money.sub(required, actual)
    return RouteUnusable(
        path=path,
        binding_segment=None if isinstance(path, FundingPath) else segment,
        binding_constraint=constraint,
        required=required,
        actual=actual,
        shortfall=shortfall,
        reason=reason,
    )


def _funding_mismatch(
    stream: IncomeStream, route: Route, path: Candidate, segment: Segment
) -> RouteUnusable | None:
    """Whether this stream's money can start down this route at all.

    Two ways it cannot, and each is a *mismatch reported rather than assumed away* (spec.md,
    Edge Cases). Both are facts about a declared pair rather than errors in the caller's
    arithmetic, which is why they come back as :class:`RouteUnusable` naming what disagreed:
    the owner's remedy is to declare a route from where his money actually lands, and a
    refusal that names both ends says so without further investigation.

    * **The venue.** A route whose ``origin`` is not where the stream's money arrives cannot
      carry it. Costing it anyway would price a journey that starts with the money already
      somewhere it is not -- the cost of getting it *there* being exactly the term this
      feature exists to stop leaving out.
    * **The currency.** A stream delivering dollars cannot start down a route whose first leg
      moves hryvnia, even at the same venue -- and a multi-currency account is the ordinary
      case, so the venues matching proves nothing about the currencies. Without this check the
      arithmetic would fail several legs later inside ``money.sub``, as a currency mismatch
      naming two currencies and neither the stream nor the route: a true message about the
      wrong thing.

    The first leg is the one that matters because it is the leg the stream's money enters. A
    route with no legs is refused at load and never costed as free (data-model.md), so the
    guard on ``route.legs`` here is only to keep that load-time defect from arriving as an
    ``IndexError`` rather than as the error it is.
    """
    if route.origin != stream.arrives_at:
        return _unusable(
            path,
            "stream.arrives_at",
            f"stream {stream.id!r} arrives at venue {stream.arrives_at!r}, but route "
            f"{route.id!r} starts at venue {route.origin!r}. The money is not where this "
            "route begins, so the route cannot carry it: the mismatch is reported rather "
            "than assumed away, because assuming it away would price a journey that skips "
            "the part nobody has costed.",
            segment=segment,
        )
    if route.legs and stream.amount.currency is not route.legs[0].from_ccy:
        return _unusable(
            path,
            "stream.amount.currency",
            f"stream {stream.id!r} delivers {stream.amount.currency.value} at venue "
            f"{stream.arrives_at!r}, but leg {route.legs[0].index} of route {route.id!r} "
            f"moves {route.legs[0].from_ccy.value} out of it. Arriving at the right venue in "
            "the wrong currency is still a mismatch, and no conversion is invented to bridge "
            "it -- a conversion is a declared leg with a declared channel (FR-010).",
            segment=segment,
        )
    return None


def _availability(
    leg: Leg, path: Candidate, segment: Segment, on_date: date
) -> RouteUnusable | None:
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
            segment=segment,
        )
    if leg.available_until is not None and on_date > leg.available_until:
        return _unusable(
            path,
            "leg.available_until",
            f"leg {leg.index} closed on {leg.available_until.isoformat()}, and the movement "
            f"is dated {on_date.isoformat()}",
            segment=segment,
        )
    return None


def _limits(leg: Leg, amount: Money, path: Candidate, segment: Segment) -> RouteUnusable | None:
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
            segment=segment,
            required=leg.minimum,
            actual=amount,
        )
    if leg.maximum is not None and money.compare(amount, leg.maximum) > 0:
        return _unusable(
            path,
            "leg.maximum",
            f"leg {leg.index} carries no more than {leg.maximum.amount!r} "
            f"{leg.maximum.currency.value}, and {amount.amount!r} reaches it",
            segment=segment,
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


def _channel_verdicts(
    channel: FxChannel,
    kinds: Mapping[str, ObservationKind],
    as_of: date,
) -> tuple[StalenessVerdict, ...]:
    """One verdict per observation in a channel, each aged under its own declared kind.

    A channel file declares a kind **three times** -- once for the reference rate and once
    per side -- because they are three observations that go out of date at three speeds. A
    single verdict over ``channel.provenance`` under ``channel.kind`` was the first
    implementation, and it aged a 7-day P2P premium under the reference's 365-day schedule
    threshold: reported fresh at 82 days, which is the silent permissive default FR-028
    exists to close. The reference's own sources are what remain of the union once the
    sides' are taken out, so no source is aged under a kind its table did not declare --
    in either direction, since the opposite error (a slow side reported stale under a fast
    reference kind) is the cry-wolf warning the per-kind design exists to avoid.
    """
    side_sources = channel.buy_side.provenance.sources | channel.sell_side.provenance.sources
    reference = prov.of(ref for ref in channel.provenance.sources if ref not in side_sources)
    return (
        stale.staleness_of(reference, kinds, kind=channel.kind, as_of=as_of),
        stale.staleness_of(
            channel.buy_side.provenance, kinds, kind=channel.buy_side.kind, as_of=as_of
        ),
        stale.staleness_of(
            channel.sell_side.provenance, kinds, kind=channel.sell_side.kind, as_of=as_of
        ),
    )


def _aged(
    walk: _Walk,
    leg: Leg,
    channel: FxChannel | None,
    kinds: Mapping[str, ObservationKind],
    as_of: date,
) -> StalenessVerdict:
    """The walk's verdict extended with this leg's -- and its channel's -- observations.

    Several declarations, several kinds: a leg's fee schedule ages on the bank's timetable
    while the premium on the channel it uses ages in days. Aging both under one threshold is
    what FR-028 exists to prevent, so each is aged under the kind its own table declared --
    the channel's sides included, per :func:`_channel_verdicts` -- and the verdicts are
    merged.
    """
    verdicts = [
        walk.staleness,
        stale.staleness_of(leg.provenance, kinds, kind=leg.kind_of_observation, as_of=as_of),
    ]
    if channel is not None:
        verdicts.extend(_channel_verdicts(channel, kinds, as_of))
    return stale.merge_all(verdicts)


def _ceiling_after(walk: _Walk, leg: Leg, sending: Currency) -> Money | None:
    """The tightest declared monthly cap so far, in the sending currency."""
    if leg.monthly_cap is None:
        return walk.ceiling
    candidate = _translated(walk, leg.monthly_cap, sending)
    if walk.ceiling is None or money.compare(candidate, walk.ceiling) < 0:
        return candidate
    return walk.ceiling


def _attributed(
    walk: _Walk,
    segment: Segment,
    *,
    spread: Money,
    percentage: Money,
    fixed: Money,
) -> tuple[SegmentAttribution, ...]:
    """One leg's charges folded into its segment's running attribution (FR-020).

    The charges arrive **already translated into the sending currency** by :func:`_applied`,
    which is what keeps the two axes honest: the same three figures are added into the
    whole-candidate totals and into this segment's subtotal, so neither axis can see a number
    the other did not.

    A leg whose segment is the one already at the end of the tuple extends it; a leg that has
    crossed into the next segment starts a new entry. The fold visits segments in order and
    never returns to one, so a single tail check is the whole of the grouping -- and a chain
    that could revisit a segment would be a chain that revisited a venue, which the search
    refuses (FR-005).
    """
    charges = {
        CostComponent.CONVERSION_SPREAD: spread,
        CostComponent.PERCENTAGE_FEE: percentage,
        CostComponent.FIXED_FEE: fixed,
    }
    if walk.segments and walk.segments[-1].position == segment.position:
        running = walk.segments[-1]
        return (
            *walk.segments[:-1],
            replace(
                running,
                components={
                    component: money.add(running.components[component], charge)
                    for component, charge in charges.items()
                },
            ),
        )
    return (
        *walk.segments,
        SegmentAttribution(
            position=segment.position, route_id=segment.route_id, components=charges
        ),
    )


def _applied(
    walk: _Walk,
    leg: Leg,
    outcome: LegOutcome,
    *,
    sending: Currency,
    staleness: StalenessVerdict,
    segment: Segment,
) -> _Walk:
    """Fold one leg's outcome into the walk, with every charge valued where it started.

    Each charge is translated **once** and then added into both axes: the three running totals
    feature 002 established, in their original order, and this segment's own subtotal. Deriving
    either axis from the other would be the sum-of-sums the whole design refuses.
    """
    spread = _translated(walk, outcome.conversion_spread, sending)
    percentage = _translated(walk, outcome.percentage_fee, sending)
    fixed = _translated(walk, outcome.fixed_fee, sending)
    return replace(
        walk,
        amount=outcome.outgoing,
        staleness=staleness,
        spread=money.add(walk.spread, spread),
        percentage=money.add(walk.percentage, percentage),
        fixed=money.add(walk.fixed, fixed),
        segments=_attributed(walk, segment, spread=spread, percentage=percentage, fixed=fixed),
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
    segment: Segment,
    *,
    path: Candidate,
    sending: Currency,
    channels: Mapping[str, FxChannel],
    kinds: Mapping[str, ObservationKind],
    on_date: date,
    as_of: date,
) -> _Walk | RouteUnusable:
    """Apply one leg: check what it will carry, then charge what it charges."""
    blocked = _availability(leg, path, segment, on_date) or _limits(leg, walk.amount, path, segment)
    if blocked is not None:
        return blocked
    channel = leg_module.channel_for(channels, leg)
    outcome = leg_module.cost_fn_for(leg.kind)(leg, walk.amount, channel)
    stepped = _applied(
        walk,
        leg,
        outcome,
        sending=sending,
        staleness=_aged(walk, leg, channel, kinds, as_of),
        segment=segment,
    )
    if leg.kind == FX and channel is not None:
        factor, sources = _factor_after(walk, leg, channel)
        stepped = replace(stepped, factor=factor, factor_sources=sources)
    return stepped


def _walk(
    chain: tuple[tuple[Leg, Segment], ...],
    walk: _Walk,
    *,
    path: Candidate,
    sending: Currency,
    channels: Mapping[str, FxChannel],
    kinds: Mapping[str, ObservationKind],
    on_date: date,
    as_of: date,
) -> _Walk | RouteUnusable:
    """Fold every leg in chain order, stopping at the first that will not carry it.

    One fold over one sequence, whether that sequence came from one declared route or from five
    chained ones. That is the whole of FR-003: there is no per-segment costing step to sum, so
    a composed candidate cannot be priced by a different arithmetic than a declared one.
    """
    for leg, segment in chain:
        stepped = _step(
            walk,
            leg,
            segment,
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
        by_segment=walk.segments,
    )


def _exit_chain_of(
    path: Candidate, exit_path: ExitChoice, routes: Mapping[str, Route]
) -> ExitChain | None:
    """The way out this candidate is keyed by, or ``None`` when nobody has declared one.

    :data:`~terezy.core.routes.path.FROM_THE_DECLARATION` applies 002's FR-027 rule unchanged:
    the way out is the ``partner_route`` of the route that **arrives** -- the last segment --
    because that is the route whose declaration was written about getting money out of the
    destination it lands at. A route with no partner still yields ``None``, and ``None`` still
    means ``ExitCostUnknown`` with no one-way figure promoted into its place (FR-030).

    Anything else is the caller's own statement about the way out: a declared exit, a composed
    chain of declared exits (FR-012), or the destination being spendable in its own right
    (003 FR-002). None of the three is inferred here, because each rests on a declaration --
    the partner link, the enumerated chain, the spendable list -- that this function is not
    the owner of.
    """
    match exit_path:
        case FromTheDeclaration():
            partner = routes[segments_of(path)[-1]].partner_route
            return None if partner is None else DeclaredExit(route_id=partner)
        case _:
            return exit_path


def _exit_routes(chain: ExitChain, routes: Mapping[str, Route]) -> tuple[Route, ...]:
    """The declared routes an exit chain names, in order, or a raise naming what is wrong.

    Validates the same three things :func:`_routes_for` validates, for the same reason -- a
    composed exit chain is assembled at query time and has no file to have been checked in --
    plus one this feature adds: **every segment is declared ``exit``** (FR-022). An observation
    of a corridor in one direction says nothing about its terms, its limits, or its existence in
    the other, so an inbound route used as a way out would be a corridor nobody observed.

    Resolution comes **before** the closed-status check, and the order is load-bearing: a
    ``partner_route`` naming a route nobody declared has to raise saying so (002's rule), and a
    status lookup on an unresolved id would raise a bare ``KeyError`` naming only the id --
    true, and about the wrong thing.
    """
    ids = exit_segments_of(chain)
    if isinstance(chain, ComposedExit) and len(ids) < _COMPOSED_MINIMUM:
        raise ValueError(
            f"a composed exit names {len(ids)} segment(s), and a composition has at least two. "
            "One declared exit route is a DeclaredExit, and a chain of none is not a way out at "
            "all -- that is ExitCostUnknown, which is a different claim."
        )
    missing = [route_id for route_id in ids if route_id not in routes]
    if missing:
        raise KeyError(
            f"exit chain names route(s) {missing}, which are not declared. A dangling partner "
            f"is refused at load (FR-027) precisely so it cannot become a missing round trip "
            f"here -- ``null`` is the way to say nobody has costed the exit. Known routes: "
            f"{sorted(routes)}"
        )
    resolved = tuple(routes[route_id] for route_id in ids)
    inbound = [route.id for route in resolved if route.direction != "exit"]
    if inbound:
        raise ValueError(
            f"exit chain names route(s) {inbound} declared inbound. Directions never mix "
            "(FR-022): what was observed one way says nothing about the other way, so using an "
            "inbound route as a way out would invent a corridor nobody observed."
        )
    for position, (before, after) in enumerate(pairwise(resolved)):
        if (
            before.destination != after.origin
            or before.legs[-1].to_ccy is not after.legs[0].from_ccy
        ):
            raise ValueError(
                f"exit segments {position} and {position + 1} do not join: route {before.id!r} "
                f"arrives as {before.legs[-1].to_ccy.value} at {before.destination!r} and route "
                f"{after.id!r} departs as {after.legs[0].from_ccy.value} from {after.origin!r}. "
                "A junction converts nothing and charges nothing (FR-002)."
            )
    return resolved


def _exit_chain(
    resolved: tuple[Route, ...], *, position_from: int, index_from: int
) -> tuple[tuple[Leg, Segment], ...]:
    """An exit chain's legs, paired with segments numbered on from the inbound chain's.

    Continuous numbering because the round trip is **one** journey: the amount that leaves the
    inbound chain is the amount that enters the exit chain, with nothing re-derived in between,
    and two independent numberings would make "position 0" ambiguous in a report.
    """
    paired: list[tuple[Leg, Segment]] = []
    for offset, route in enumerate(resolved):
        segment = Segment(position=position_from + offset, route_id=route.id)
        for leg in route.legs:
            paired.append((replace(leg, index=index_from + len(paired)), segment))
    return tuple(paired)


def _closed_exit(resolved: tuple[Route, ...]) -> Route | None:
    """The first segment of an already-resolved exit chain that is declared closed, if any.

    Takes the resolved routes rather than the ids so it cannot be reached before
    :func:`_exit_routes` has said whether they exist -- a lookup that raised here would report a
    dangling partner as a missing key rather than as the declaration error it is.
    """
    return next((route for route in resolved if route.status == "closed"), None)


def _round_trip(
    sent: Money,
    walk: _Walk,
    *,
    path: Candidate,
    exit_chain: ExitChain | None,
    routes: Mapping[str, Route],
    channels: Mapping[str, FxChannel],
    kinds: Mapping[str, ObservationKind],
    on_date: date,
    as_of: date,
) -> RoundTripCost | ExitCostUnknown:
    """The cost in and back out again, or a typed statement of why there is none.

    Computed by continuing the *same* walk through the exit chain, so the exit's charges land in
    the same three components, valued in the same sending currency, as the inbound ones.
    Continuing the walk rather than starting a new one is what makes the round-trip attribution
    close: the amount that leaves the inbound chain is the amount that enters the exit chain,
    with nothing re-derived in between.

    **Three ways there is a round trip, and they are three different claims.**
    :class:`~terezy.core.routes.path.DeclaredExit` is 002's single declared partner;
    :class:`~terezy.core.routes.path.ComposedExit` is FR-012's chain of declared exit segments,
    which the owner decided satisfies FR-027 because every link of it **is** an observation; and
    :data:`~terezy.core.routes.path.EXIT_BY_IDENTITY` is the destination already being a declared
    spendable endpoint, so there is nothing to do and nothing to charge.

    **The identity case is not a promoted one-way figure**, and the distinction is the reason the
    sentinel exists rather than a zero-length chain. The money has arrived somewhere the owner
    spends from: the round trip is complete at the moment the inbound chain ends, so the
    round-trip figure *is* the inbound figure -- not because a way out was assumed free, but
    because there is no way out left to travel. A ``RoundTripCost`` here says "this is the whole
    cost of getting in and being able to spend it"; ``ExitCostUnknown`` would say the opposite,
    and a one-way figure quietly copied into the round-trip slot would say it while looking like
    the first.

    A candidate with no exit chain at all yields :class:`ExitCostUnknown` (FR-030). So does an
    exit segment **declared closed** -- a way out that carries nothing on the date is not a
    usable way out -- and so does an exit chain that will not carry what arrived. The reason says
    which, because "nobody declared the way out", "the way out is closed" and "the way out will
    not take this much" are different facts and the owner acts on them differently. In no case is
    the one-way figure promoted.
    """
    arriving = routes[segments_of(path)[-1]]
    if exit_chain is None:
        return ExitCostUnknown(
            reason=(
                f"route {arriving.id!r} declares no partner_route, so nobody has costed the way "
                "out. Round-trip cost is computed from separately declared exit routes and "
                "never by reversing the way in (FR-027), and the one-way figure is not "
                "promoted into its place (FR-030): a destination whose exit nobody has "
                "costed is not comparison-ready."
            ),
            missing_partner_for=arriving.id,
        )
    if isinstance(exit_chain, ExitByIdentity):
        # No legs, and therefore no charges: the destination is itself a declared spendable
        # endpoint, so the money is already where it needed to come back out to (003 FR-002).
        # The figure below is the inbound walk's, because the inbound walk is the whole journey
        # -- see this function's docstring for why that is not FR-030's forbidden promotion.
        components, fraction, provenance = _figure(sent, walk)
        return RoundTripCost(
            sent=sent,
            arrived=walk.amount,
            components=components,
            fraction=fraction,
            spreads_over_reference=walk.spreads,
            channels_applied=walk.channels,
            provenance=provenance,
            staleness=walk.staleness,
            by_segment=walk.segments,
        )
    resolved_exit = _exit_routes(exit_chain, routes)
    closed = _closed_exit(resolved_exit)
    if closed is not None:
        return ExitCostUnknown(
            reason=(
                f"exit route {closed.id!r} is declared closed, so it carries nothing on "
                f"{on_date.isoformat()}: the way out is declared and is not usable. There "
                "is therefore no round-trip figure for this path, and the one-way figure "
                "is not promoted into its place (FR-030); the exclusion is recorded rather "
                "than silent (FR-014)."
            ),
            missing_partner_for=arriving.id,
        )
    exited = _walk(
        _exit_chain(
            resolved_exit,
            position_from=len(segments_of(path)),
            index_from=sum(len(routes[route_id].legs) for route_id in segments_of(path)),
        ),
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
                f"exit chain {'+'.join(exit_segments_of(exit_chain))!r} will not carry what "
                f"arrives: {exited.reason}. There is therefore no round-trip figure for this "
                "path, and the one-way figure is not promoted into its place (FR-030)."
            ),
            missing_partner_for=arriving.id,
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
        by_segment=exited.segments,
    )


def _status_of(resolved: tuple[Route, ...]) -> RouteStatus:
    """The status a whole candidate reports: the most constrained any segment declares.

    A chain is no more usable than its tightest link, so a candidate one of whose segments is
    ``constrained`` is reported constrained even where the others are open. Taking the first
    segment's status, or the last, would let a constrained corridor hide behind an open one --
    and the status is what a reader scans to decide whether to trust the figure beside it.

    ``closed`` never reaches here: :func:`cost_one` excludes such a candidate with the binding
    segment recorded, before anything is costed (FR-014, FR-015).
    """
    return "constrained" if any(route.status == "constrained" for route in resolved) else "open"


def cost_one(
    path: Candidate,
    amount: Money,
    *,
    routes: Mapping[str, Route],
    channels: Mapping[str, FxChannel],
    streams: Mapping[str, IncomeStream],
    kinds: Mapping[str, ObservationKind],
    on_date: date,
    as_of: date,
    exit_path: ExitChoice = FROM_THE_DECLARATION,
) -> RampCost | RouteUnusable:
    """Cost one amount along one candidate. The only costing function in the project.

    Pure: no clock, no I/O, no state. Called twice with equal arguments it returns equal
    results, which is what makes C4 determinism reachable and what lets a ranking cost every
    candidate through this same function without any of them influencing another.

    ``path`` is a :class:`~terezy.core.routes.path.Candidate`: one declared route, or a chain of
    them composed at query time. **There is no separate function for the second kind**
    (FR-003). :func:`legs_of` turns either into one leg sequence and the fold below walks it
    unchanged, so a composed candidate is not costed *like* a declared route -- it is costed by
    the same call, over a longer tuple. That is why SC-002 can be asserted by construction
    rather than by comparing two figures that happen to agree.

    Returns a :class:`RampCost` -- one way, round trip, latency, ceiling, status and disruption
    probability, attributed by **component and by segment** and carrying merged provenance and a
    staleness verdict -- or a :class:`RouteUnusable` naming the constraint that bound and the
    segment it bound on. Never an exception for a fact about the money, and never a zero cost
    standing in for a refusal.

    A negative amount raises. It is not a movement of money in the other direction -- that is
    a different route, declared separately (FR-027) -- so it can only be a caller's arithmetic
    error, and costing it would produce a negative cost that looks like a gain.

    **``exit_path`` names the way out, and its default is the declaration rather than a
    guess.** :data:`~terezy.core.routes.path.FROM_THE_DECLARATION` applies 002's FR-027 rule
    unchanged -- the arriving route's ``partner_route``, or ``ExitCostUnknown`` where it names
    none -- so every caller written before this feature keeps the behaviour it had, and says so
    by name in the signature rather than inheriting it silently. It substitutes nothing for
    missing data: a route with no declared partner still has no round trip. A caller who has
    *found* a way out -- an enumerated chain of declared exit segments (FR-012), or a
    destination that is itself spendable (003 FR-002) -- passes it, because those rest on
    declarations this function is not the owner of.

    **The order the refusals are checked in is deliberate**, because two of them can be true at
    once and the one reported should be the one the owner acts on first. They run from the least
    dependent on circumstance to the most: the candidate's own coherence (a raise -- a chain
    whose junctions do not join is not a question about money), then the stream against the way
    in (true on every date and at every amount), then each segment's status (true on this date),
    then each leg's window and limits (true of this amount on this date). A candidate whose
    stream does not reach its first segment is reported as such even if a later segment also
    happens to be closed, because declaring a route from where the money actually lands is the
    owner's next move either way.

    ``amount`` and ``streams`` are separate arguments and the amount must be in the named
    stream's currency; a disagreement raises. The amount is deliberately not read off the
    stream: what to move is a decision (a whole month's arrival, a part of it, a figure from
    :func:`terezy.core.streams.streams.deployable`), while the stream says where money lands
    and in what currency. What the two may not do is disagree about the currency, because then
    the cost would be attributed to a stream that never delivered the money being costed --
    and the stream is the term that carries the finding (FR-008).
    """
    if amount.amount < 0.0:
        raise ValueError(
            f"an amount of {amount.amount!r} {amount.currency.value} cannot be moved along a "
            "route: a negative movement is not this route in reverse -- the way out is its "
            "own declaration (FR-027) -- so a negative amount here is an arithmetic error in "
            "the caller, and costing it would report a negative cost that reads as a gain"
        )
    resolved = _routes_for(routes, path)
    stream = _stream_for(streams, path)
    if amount.currency is not stream.amount.currency:
        raise ValueError(
            f"an amount of {amount.amount!r} {amount.currency.value} cannot be funded from "
            f"stream {stream.id!r}, which delivers {stream.amount.currency.value}: the stream is "
            "part of what a cost *is* (FR-008), so costing money the named stream never "
            "delivered would attribute a real figure to the wrong income. Like a currency "
            "mismatch in ``money``, this is a caller's error rather than a fact about the "
            "money, so it raises rather than returning a cost or a refusal."
        )
    mismatched = _funding_mismatch(
        stream, resolved[0], path, Segment(position=0, route_id=resolved[0].id)
    )
    if mismatched is not None:
        return mismatched
    for position, route in enumerate(resolved):
        if route.status == "closed":
            return _unusable(
                path,
                "route.status",
                f"route {route.id!r} is declared closed, so it carries nothing on "
                f"{on_date.isoformat()}. Its exclusion is recorded rather than silent "
                "(FR-014), and the segment it bound on is named so a chain's reader knows "
                "which declaration to open (FR-015).",
                segment=Segment(position=position, route_id=route.id),
            )
    walked = _walk(
        # Inlined rather than bound to a name, so that "the fold is only ever handed a chain
        # this module built" is visible at the call site and checkable by a scan over the
        # syntax. A local variable would put one indirection between the two, which is exactly
        # where a second way of assembling a journey would appear.
        _chain(path, routes),
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
    exit_chain = _exit_chain_of(path, exit_path, routes)
    return RampCost(
        path=path,
        exit_path=exit_chain,
        one_way=_one_way(amount, walked),
        round_trip=_round_trip(
            amount,
            walked,
            path=path,
            exit_chain=exit_chain,
            routes=routes,
            channels=channels,
            kinds=kinds,
            on_date=on_date,
            as_of=as_of,
        ),
        latency_days=walked.latency_days,
        ceiling=walked.ceiling,
        status=_status_of(resolved),
        disruption_probability=walked.disruption,
    )
