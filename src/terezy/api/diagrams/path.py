"""One costed ramp result, drawn as its path -- and a refusal drawn as a refusal.

FR-007 through FR-011. This is where the numbers meet the picture. Feature 002's central
sentence -- *"most of the gap is the ramp, not the asset"* -- is a sentence about **which edge
is expensive**, and an edge-labelled path is that sentence drawn.

## Every figure is the result's own, through the one rule

FR-008 is absolute: the renderer computes, derives, aggregates and re-rounds nothing. The only
transformation it applies is :mod:`terezy.api.diagrams.numbers`, once, at each site.

**The result carries no per-leg attribution today**, and the diagram says only what the result
says. ``OneWayCost.components`` is the whole route's charge split into three terms, not one
figure per leg, so the *edges* carry each leg's **declared** fees -- which the ``Leg`` records
in ``routes`` do carry -- and the computed one-way and round-trip figures live in their own
labelled nodes. That is FR-008's second half working as intended: an edge shows a figure with
its provenance state, or it shows none.

Feature 004 is landing in parallel and may give ``RampCost`` a composed path and a per-segment
attribution. **Nothing here anticipates it.** Rendering what a type might carry is how a
special case gets written that later has to be deleted; when a composed candidate is an
ordinary costed result, it renders through this same door.

## Labelling, which is the rule this project already broke once

Every cost figure is named **one-way** or **round-trip** (FR-009). The spread over reference is
labelled as itself, in its own node, saying in words that it is *not* the cost -- because ``p/r``
and the cost differ on the buy side (6.67% against 7.14% at §4.3.1's numbers) and reporting the
rate-space figure as the cost is the correction ``METHODOLOGY`` §16.2 records.

The round trip is drawn from the **declared exit route's** own legs and venues (FR-010), never
the inbound chain reversed. That is why ``routes`` is an argument: the result names its route,
the route names its ``partner_route``, and the partner's legs are the way out. A result whose
round-trip slot is ``ExitCostUnknown`` renders that fact in the place the exit would occupy,
with **no round-trip figure anywhere** on the diagram.

## Staleness comes out of the verdict the result carries

``render_path`` takes no ``kinds`` and no ``as_of``, and needs neither: ``OneWayCost.staleness``
is the verdict feature 002 already computed, under each leg's own declared threshold, at the
run's as-of date. A leg is stale here when one of its own sources appears in that verdict's
stale list -- the result's figure, read rather than recomputed. A source the verdict never
assessed is reported as unassessed rather than as current (``marks.UNASSESSED``): "nobody
checked" and "checked and clean" are different claims.

## A refusal is a refusal

``RouteUnusable``, ``ExitCostUnknown`` and ``NothingComparable`` each yield a typed
``NothingToDraw`` carrying the refusal's own reason verbatim -- never a partial path, never a
silently empty diagram (predecessor defect B10 in its visual form). The words the engine chose
are the ones the owner has already learned to read, so they are not reworded here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import assert_never

from terezy.api.diagrams import Diagram, NothingToDraw, marks, mermaid, numbers
from terezy.api.diagrams.marks import Mark
from terezy.core.primitives.staleness import StalenessVerdict
from terezy.core.results.ramp import (
    CostComponent,
    ExitCostUnknown,
    NothingComparable,
    OneWayCost,
    RampCost,
    RoundTripCost,
    RouteUnusable,
)
from terezy.core.routes.legs import Leg, Route
from terezy.core.scenarios.regimes import Regime

INBOUND: str = "inbound"
EXIT: str = "exit"
"""Which half of the round trip an edge belongs to, said on the edge.

Stated rather than inferred from position, because "the exit is the inbound reversed" is
exactly the reading FR-010 forbids and a reader must be able to see which half they are
looking at without counting arrows.
"""

ONE_WAY: str = "one-way"
ROUND_TRIP: str = "round-trip"
"""The two names every cost figure must wear (FR-009).

Constants rather than literals at each site, because "one-way and round-trip explicitly named
wherever a cost appears" is one rule and a diagram that spelled it two ways would let a reader
believe the two spellings meant two things.
"""

FIGURE_FIELD: str = "declared fee "
"""The per-leg figure prefix, the same one the registry graph uses. One prefix, so "every
figure on an edge is a declared leg fee" is one claim about both diagram kinds."""


def _leg_is_stale(leg: Leg, verdict: StalenessVerdict) -> bool:
    """Whether any of this leg's own sources is in the result's stale list.

    Read out of the verdict rather than recomputed. The verdict was produced by feature 002's
    ``staleness_of`` under this leg's declared ``kind_of_observation`` at the run's as-of date;
    ageing the leg again here would need a second as-of date and a second kind registry, and
    two computations of one fact eventually disagree.
    """
    stale_ids = {source.source_id for source in verdict.stale}
    return any(ref.id in stale_ids for ref in leg.provenance.sources)


def _leg_is_assessed(leg: Leg, verdict: StalenessVerdict) -> bool:
    """Whether every source behind this leg was aged at all. See :data:`marks.UNASSESSED`."""
    assessed = set(verdict.assessed)
    return all(ref.id in assessed for ref in leg.provenance.sources)


def _leg_fields(leg: Leg, route: Route, direction: str, verdict: StalenessVerdict) -> list[str]:
    """One edge's label, field by field. Declared figures only; nothing computed."""
    currency = (
        leg.from_ccy.value
        if leg.from_ccy is leg.to_ccy
        else f"{leg.from_ccy.value} to {leg.to_ccy.value}"
    )
    fields = [
        direction,
        f"route {mermaid.escape(route.id)}",
        mermaid.escape(route.provider),
        f"leg {leg.index} {mermaid.escape(leg.kind)}",
        currency,
    ]
    if leg.channel is not None:
        fields.append(f"via channel {mermaid.escape(leg.channel)}")
    fields.append(f"{FIGURE_FIELD}{numbers.percent(leg.fee_pct)} + {numbers.amount(leg.fee_fixed)}")
    fields.append(f"status: {route.status}")
    fields.append(
        marks.segment(
            marks.epistemic(leg.provenance, stale=_leg_is_stale(leg, verdict)),
            unsourced=marks.is_unsourced(leg.provenance),
            assessed=_leg_is_assessed(leg, verdict),
        )
    )
    return fields


def _cost_marks(cost: OneWayCost | RoundTripCost) -> tuple[Mark, ...]:
    """The marks a costed figure earns from the provenance and verdict it carries.

    Derived once and used twice -- for the label text and for the style class -- so a node
    can never be coloured for a mark its words do not carry, which is the failure D4 is about.
    """
    return marks.epistemic(cost.provenance, stale=bool(cost.staleness.stale))


def _cost_fields(label: str, cost: OneWayCost | RoundTripCost) -> list[str]:
    """One costed figure, named as itself, with the whole closed component set beside it.

    ``label`` is ``one-way`` or ``round-trip`` and is not optional at any call site: FR-009
    requires every cost figure to say which it is, wherever it appears, and a default would be
    a way to forget. Every member of :class:`CostComponent` is rendered, including the zeros,
    so a reader sees that a component is zero rather than absent.
    """
    fields = [
        f"{label} cost {numbers.percent(cost.fraction)} of {numbers.amount(cost.sent)} sent",
        f"arrived {numbers.amount(cost.arrived)}",
    ]
    fields.extend(
        f"{component.value} {numbers.amount(cost.components[component])}"
        for component in sorted(CostComponent, key=lambda item: item.value)
    )
    fields.append(
        marks.segment(
            _cost_marks(cost),
            unsourced=marks.is_unsourced(cost.provenance),
            assessed=bool(cost.staleness.assessed),
        )
    )
    return fields


def _spread_fields(label: str, cost: OneWayCost | RoundTripCost) -> list[str]:
    """The rate-space spread, labelled as itself and never as the cost (FR-009).

    ``p/r`` is the figure ``SIMULATOR_SPEC.md`` §4.3.1 quotes; the cost is
    ``channels.loss_fraction``, and the two differ on the buy side. Reporting only the
    rate-space figure is the mistake this project made once, and it reported an arriving amount
    short of what the venue pays. So the two live in separate labels, and this one says in
    words what it is not.
    """
    per_leg = [
        f"{numbers.percent(spread)} via {mermaid.escape(channel)}"
        for spread, channel in zip(cost.spreads_over_reference, cost.channels_applied, strict=True)
    ]
    return [
        f"spread over reference ({label}): {', '.join(per_leg)}",
        f"this is NOT the cost -- the cost is the {label} cost figure above",
    ]


def _reported_beside_fields(result: RampCost) -> list[str]:
    """What travels with a cost without ever being folded into it (FR-026).

    Latency, the tightest declared monthly ceiling, and the disruption probability. A slow
    route is not an expensive one and a fragile route is not an expensive one; a single number
    blending any two of these would answer neither question. The disruption figure is the
    largest single leg's, which makes it a **lower bound**, and the label says so -- compounding
    would require assuming the legs fail independently, which nobody has stated.
    """
    ceiling = "none declared" if result.ceiling is None else numbers.amount(result.ceiling)
    return [
        "reported beside the cost, never folded into it",
        f"latency {result.latency_days} days",
        f"tightest declared monthly ceiling: {ceiling}",
        "disruption probability (largest single leg, so a lower bound): "
        f"{numbers.percent(result.disruption_probability)}",
    ]


def _exit_route(result: RampCost, routes: Mapping[str, Route]) -> Route | None:
    """The declared exit route, or ``None`` when the result says none was costed.

    Keyed off the *result*: a ``RoundTripCost`` means an exit route was costed, and the route's
    ``partner_route`` names which. Never a search for something that leaves the destination,
    which would be composition -- a different feature's question with a different answer.
    """
    if isinstance(result.round_trip, ExitCostUnknown):
        return None
    inbound = routes[result.path.route_id]
    if inbound.partner_route is None:
        raise ValueError(
            f"route {inbound.id!r} carries a round-trip cost but declares no partner_route. A "
            "round trip is drawn from the declared exit route's own legs (FR-010); there is no "
            "reversal of the inbound chain to fall back on"
        )
    return routes[inbound.partner_route]


def _drawn(result: RampCost, routes: Mapping[str, Route], regime_id: str) -> Diagram:
    """The path itself, once the input has been established to be a costed result."""
    inbound = routes[result.path.route_id]
    exit_route = _exit_route(result, routes)

    chains: list[tuple[str, Route, StalenessVerdict]] = [
        (INBOUND, inbound, result.one_way.staleness)
    ]
    if exit_route is not None:
        # The exit legs' observations are in the *round-trip* verdict: it is the merged
        # verdict over both routes, and the one-way verdict never aged them. Using the
        # one-way verdict here would report every exit leg as unassessed -- honest, but a
        # verdict that does cover them exists and this is a picture of that result.
        assert isinstance(result.round_trip, RoundTripCost)
        chains.append((EXIT, exit_route, result.round_trip.staleness))

    venue_ids = sorted(
        {
            venue
            for _, route, _ in chains
            for leg in route.legs
            for venue in (leg.from_venue, leg.to_venue)
        }
    )
    node_of = {venue_id: mermaid.node_id(index) for index, venue_id in enumerate(venue_ids)}

    caption_marks = marks.epistemic(
        result.one_way.provenance, stale=bool(result.one_way.staleness.stale)
    )
    lines = [
        mermaid.node(
            mermaid.CAPTION_ID,
            mermaid.label(
                "costed path",
                f"regime: {mermaid.escape(regime_id)}",
                f"destination: {mermaid.escape(result.path.destination_id)}",
                f"stream: {mermaid.escape(result.path.stream_id)}",
                f"route: {mermaid.escape(result.path.route_id)}",
                f"status: {inbound.status}",
                marks.segment(caption_marks),
            ),
        )
    ]

    annotations: list[tuple[list[str], str | None]] = [
        (
            _cost_fields(ONE_WAY, result.one_way),
            marks.style_class_for(_cost_marks(result.one_way)),
        )
    ]
    exit_unknown_node: str | None = None
    match result.round_trip:
        case RoundTripCost() as round_trip:
            annotations.append(
                (
                    _cost_fields(ROUND_TRIP, round_trip),
                    marks.style_class_for(_cost_marks(round_trip)),
                )
            )
        case ExitCostUnknown() as unknown:
            exit_unknown_node = mermaid.annotation_id(len(annotations))
            annotations.append(
                (
                    [
                        marks.segment((Mark.EXIT_COST_UNKNOWN,)),
                        mermaid.escape(unknown.reason),
                        f"no exit route is declared as partner of "
                        f"{mermaid.escape(unknown.missing_partner_for)}",
                        "so no round-trip figure appears on this diagram",
                    ],
                    marks.STYLE_CLASS[Mark.EXIT_COST_UNKNOWN],
                )
            )
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(result.round_trip)

    if result.one_way.spreads_over_reference:
        annotations.append((_spread_fields(ONE_WAY, result.one_way), None))
    if isinstance(result.round_trip, RoundTripCost) and result.round_trip.spreads_over_reference:
        annotations.append((_spread_fields(ROUND_TRIP, result.round_trip), None))
    annotations.append((_reported_beside_fields(result), None))

    lines.extend(
        mermaid.node(mermaid.annotation_id(index), mermaid.label(*fields), style_class=style)
        for index, (fields, style) in enumerate(annotations)
    )

    lines.extend(
        mermaid.node(node_of[venue_id], mermaid.label(f"venue {mermaid.escape(venue_id)}"))
        for venue_id in venue_ids
    )

    for direction, route, verdict in chains:
        for leg in sorted(route.legs, key=lambda item: item.index):
            lines.append(
                mermaid.edge(
                    node_of[leg.from_venue],
                    node_of[leg.to_venue],
                    mermaid.label(*_leg_fields(leg, route, direction, verdict)),
                )
            )

    if exit_unknown_node is not None:
        lines.append(
            mermaid.edge(
                node_of[inbound.destination],
                exit_unknown_node,
                mermaid.label(
                    marks.segment((Mark.EXIT_COST_UNKNOWN,)),
                    "the exit that would go here has not been declared",
                ),
                dotted=True,
            )
        )

    lines.extend(mermaid.class_def(name, style) for name, style in marks.CLASS_DEFS)

    return Diagram(
        text=mermaid.document(lines),
        kind="costed_path",
        regime_id=regime_id,
        mode=None,
    )


def render_path(
    result: RampCost | RouteUnusable | ExitCostUnknown | NothingComparable,
    *,
    routes: Mapping[str, Route],
    regime: Regime,
) -> Diagram | NothingToDraw:
    """One costed result as Mermaid text, or a typed refusal carrying its reason.

    ``regime`` is required and has no default, for the reason FR-019 gives: a diagram existing
    under no regime must not be **producible**, and no argument list here expresses one. It is
    also *checked* -- rendering a path whose route the regime excludes would be a picture of a
    corridor that does not exist under the belief the caption names.

    The diagram renders **the result it was given** and never re-reads the registry to freshen
    a picture of a past decision: ``routes`` supplies the legs the result costed and the exit
    route it named, and nothing else.
    """
    match result:
        case RampCost():
            if result.path.route_id not in regime.route_ids:
                raise ValueError(
                    f"regime {regime.id!r} does not include route {result.path.route_id!r}, so "
                    "this path does not exist under it. A diagram shows one regime (FR-019), "
                    "and drawing a corridor the regime excludes would picture something the "
                    "scenario says is not there"
                )
            return _drawn(result, routes, regime.id)
        case RouteUnusable() | ExitCostUnknown() | NothingComparable():
            return NothingToDraw(reason=result.reason, kind="costed_path")
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(result)
