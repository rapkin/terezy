"""One costed ramp result, drawn as its path -- and a refusal drawn as a refusal.

FR-007 through FR-011. This is where the numbers meet the picture. Feature 002's central
sentence -- *"most of the gap is the ramp, not the asset"* -- is a sentence about **which edge
is expensive**, and an edge-labelled path is that sentence drawn.

## Every figure is the result's own, through the one rule

FR-008 is absolute: the renderer computes, derives, aggregates and re-rounds nothing. The only
transformation it applies is :mod:`terezy.api.diagrams.numbers`, once, at each site.

**The result carries no per-leg attribution today**, and the diagram says only what the result
says. ``OneWayCost.components`` is the whole route's charge split into three terms, not one
figure per leg, so the *edges* carry the **declared** figures -- each leg's fees, and the quote
its channel applies -- and the computed one-way and round-trip figures live in their own
labelled nodes. That is FR-008's second half working as intended: an edge shows a figure with
its provenance state, or it shows none.

**The channel premium is on the edges here too, and this is the diagram where it matters most.**
Every fee on the §4.3.1 corridor is declared zero and the whole 6.67% is the ``p2p`` channel's
``+3.00 UAH per USD``. An edge labelled ``declared fee 0.00%`` and nothing else, on the very
picture that exists to show where a cost comes from, would answer the question it was drawn to
answer with a zero. The figures node above it does not repair that: a total at the top does not
survive someone looking at one edge. It is the same argument the registry graph makes, with
more force rather than less, which is why ``channels`` is a required parameter here as well.

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
is the verdict feature 002 already computed, under **each observation's** own declared threshold
-- the leg's fee schedule, the channel's reference rate, each channel side -- at the run's as-of
date. An edge is stale here when any source behind it appears in that verdict's stale list: the
result's own verdict, read rather than recomputed. The quote's sources are part of "behind it",
because matching only the leg's own left a stale premium invisible on the edge that charges it.
A source the verdict never assessed is reported as unassessed rather than as current
(``marks.UNASSESSED``): "nobody checked" and "checked and clean" are different claims.

## A refusal is a refusal

``RouteUnusable``, ``ExitCostUnknown`` and ``NothingComparable`` each yield a typed
``NothingToDraw`` carrying the refusal's own reason verbatim -- never a partial path, never a
silently empty diagram (predecessor defect B10 in its visual form). The words the engine chose
are the ones the owner has already learned to read, so they are not reworded here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import assert_never

from terezy.api.diagrams import Diagram, NothingToDraw, figures, marks, mermaid, numbers
from terezy.api.diagrams.figures import Quote
from terezy.api.diagrams.marks import Mark
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.staleness import StalenessVerdict
from terezy.core.results.ramp import (
    CostComponent,
    ExitCostUnknown,
    NothingComparable,
    OneWayCost,
    RampCost,
    RoundTripCost,
    RouteUnusable,
    SegmentAttribution,
)
from terezy.core.routes import path as candidates
from terezy.core.routes.channels import FxChannel
from terezy.core.routes.legs import Leg, Route
from terezy.core.routes.path import (
    ComposedExit,
    ComposedPath,
    DeclaredExit,
    ExitByIdentity,
    FundingPath,
    Segment,
)
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

# The declared-figure field prefixes are ``terezy.api.diagrams.figures``' -- one definition,
# imported by both renderers, because they draw the same edge. Duplicating the literal here
# is how the two diagram kinds come to disagree about what a declared figure is, and how
# SC-012's strip assertion -- built from ``figures.FIGURE_FIELD`` -- comes to cover less
# than it claims.


def _is_stale(provenance: Provenance, verdict: StalenessVerdict) -> bool:
    """Whether any source behind this edge is in the result's stale list.

    Read out of the verdict rather than recomputed. The verdict was produced by feature 002's
    ``cost._aged`` under each observation's own declared kind -- the leg's fee schedule, the
    channel's reference rate, each channel side -- at the run's as-of date. Ageing them again
    here would need a second as-of date and a second kind registry, and two computations of one
    fact eventually disagree.

    Asked of the **whole** edge, the applied channel quote included. Matching only the leg's own
    sources left a stale premium invisible on the very edge that charges it -- and on the
    §4.3.1 corridor the premium is the entire cost.
    """
    stale_ids = {source.source_id for source in verdict.stale}
    return any(ref.id in stale_ids for ref in provenance.sources)


def _is_assessed(provenance: Provenance, verdict: StalenessVerdict) -> bool:
    """Whether every source behind this edge was aged at all. See :data:`marks.UNASSESSED`."""
    assessed = set(verdict.assessed)
    return all(ref.id in assessed for ref in provenance.sources)


def _leg_fields(
    leg: Leg,
    segment: Segment,
    route: Route,
    *,
    direction: str,
    quote: Quote | None,
    verdict: StalenessVerdict,
) -> list[str]:
    """One edge's label, field by field. Declared figures only; nothing computed.

    The same declared figures, in the same order, as the registry graph puts on the same leg
    (``figures.edge_figures``) -- so a reader holding the two diagrams side by side can compare
    them line by line, and so neither can quietly start showing a figure the other does not.

    **The segment field is what makes a chain readable.** ``Leg.index`` is declared per route,
    so a two-segment chain says ``leg 0`` twice; ``segment 0 · leg 0`` and ``segment 1 · leg 0``
    are the two different movements they are. The segment also names the declared route it is,
    which is 004's FR-013 on an edge: every hop of a composed candidate is somebody's
    declaration, and a reader must be able to open it.
    """
    currency = (
        leg.from_ccy.value
        if leg.from_ccy is leg.to_ccy
        else f"{leg.from_ccy.value} to {leg.to_ccy.value}"
    )
    fields = [
        direction,
        f"segment {segment.position}",
        f"route {mermaid.escape(route.id)}",
        f"provider {mermaid.escape(route.provider)}",
        f"leg {leg.index} {mermaid.escape(leg.kind)}",
        currency,
    ]
    if leg.channel is not None:
        fields.append(f"via channel {mermaid.escape(leg.channel)}")
    fields.extend(figures.edge_figures(leg, quote))
    fields.append(f"status: {route.status}")
    behind = figures.edge_provenance(leg, quote)
    fields.append(
        marks.segment(
            marks.epistemic(behind, stale=_is_stale(behind, verdict)),
            unsourced=marks.is_unsourced(behind),
            assessed=_is_assessed(behind, verdict),
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


def _by_segment_fields(label: str, attributions: tuple[SegmentAttribution, ...]) -> list[str]:
    """What each segment of a candidate charged, named by the declared route it is.

    004's second axis of attribution (its FR-020). ``components`` says which *term* charged --
    spread, percentage, flat -- and this says which *hop* did, which is the question a reader of
    a chain actually has: **which declaration dominates, and where do I open it?**

    On its own node rather than on the edges. A segment is a declared route and an edge is a
    leg, so a segment's charge belongs to neither one of its legs nor to all of them; repeating
    it on each would read as each leg charging it. A declared route has exactly one of these and
    that is not a special case -- the figures restate the component totals, which is the correct
    reading and exactly what stops being true the day a chain is costed.
    """
    fields = [f"{label} cost by segment"]
    if len(attributions) > 1:
        # Each figure goes through the one rule and is rounded on its own, so two segments
        # rounding up can display a total a hundredth above the rounded sum above -- 666.67 and
        # 555.56 against 1222.22 on the §4.3.1 round trip. The underlying figures add exactly;
        # what does not add is the *rendering*, which is the rounding this diagram admits to
        # (METHODOLOGY, the number rule). Said here rather than left for a reader to find,
        # because a reader who adds them and comes up short will suspect the arithmetic.
        fields.append(
            "each figure rounded on its own, so the segments need not add to the total above"
        )
    fields.extend(
        f"segment {entry.position} route {mermaid.escape(entry.route_id)}: "
        + ", ".join(
            f"{component.value} {numbers.amount(entry.components[component])}"
            for component in sorted(CostComponent, key=lambda item: item.value)
        )
        for entry in attributions
    )
    return fields


def _way_in_field(candidate: candidates.Candidate) -> str:
    """How the money got in, said in the caption: one declaration, or a chain of them.

    004's FR-013 -- *a composed candidate is visibly distinct from a declared route in every
    report* -- and a diagram is a report. A chain exists only at query time, so a reader who
    could not tell it from a declared corridor would go looking for a file nobody wrote.
    """
    match candidate:
        case FundingPath():
            return f"way in: declared route {mermaid.escape(candidate.route_id)}"
        case ComposedPath():
            joined = mermaid.escape(candidates.candidate_id(candidate))
            return (
                f"way in: composed chain of {len(candidate.segments)} declared routes "
                f"({joined}) -- nobody declared this corridor end to end"
            )
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(candidate)


def _way_out_field(result: RampCost) -> str:
    """How the money gets back out, in the four shapes the result can carry.

    Three members of ``ExitChain`` plus ``None``, each a different claim the owner acts on
    differently: one declared partner, a chain of declared exit routes, a destination that is
    already spendable, and nobody having costed a way out at all.
    """
    match result.exit_path:
        case None:
            return "way out: NONE COSTED -- see the exit-cost-unknown note"
        case DeclaredExit():
            return f"way out: declared route {mermaid.escape(result.exit_path.route_id)}"
        case ComposedExit():
            joined = mermaid.escape("+".join(result.exit_path.segments))
            return (
                f"way out: composed chain of {len(result.exit_path.segments)} declared exit "
                f"routes ({joined})"
            )
        case ExitByIdentity():
            return "way out: none needed -- the destination is itself a declared spendable endpoint"
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(result.exit_path)


def _identity_fields(result: RampCost) -> list[str]:
    """The ``EXIT_BY_IDENTITY`` note: why this diagram has a round trip and no exit legs.

    **It is not an edge, and drawing one would say something false.** An edge is a movement of
    money; here no money moves, because the destination *is* somewhere the owner spends. A
    zero-cost edge would assert a journey that costs nothing, which is a different claim from
    there being no journey -- the same distinction ``core.routes.path.ExitByIdentity`` exists to
    carry, where ``None`` would have said "no exit chain" and an empty chain "a chain that
    charged nothing".

    So the claim goes where it is true: on the **venue**, which is the thing that is spendable,
    and in this note. The consequence a reader needs is stated too -- the round-trip figure
    equals the one-way figure, and that is arithmetic rather than a coincidence.
    """
    return [
        marks.segment((Mark.EXIT_BY_IDENTITY,)),
        f"{mermaid.escape(result.path.destination_id)} is itself a declared spendable endpoint",
        "the money is already where it needed to come back out to, so there are no exit legs",
        "and the round-trip figure is the one-way figure -- not a way out that happened to cost "
        "nothing",
    ]


def _walked(
    segment_ids: tuple[str, ...],
    routes: Mapping[str, Route],
    direction: str,
    verdict: StalenessVerdict,
    *,
    position_from: int = 0,
) -> list[tuple[str, Segment, Route, StalenessVerdict]]:
    """One half of a journey, as the declared routes it is made of, numbered in chain order.

    A declared route is a chain of one and is not a special case here, which is the reading
    ``core.routes.path.segments_of`` establishes and this follows: one code path draws both, so
    a composed candidate cannot acquire a rendering of its own.

    ``position_from`` continues the numbering from the previous half, because **the round trip
    is one journey and core numbers it as one** -- ``cost._exit_chain`` takes the same argument
    for the same reason, and ``SegmentAttribution.position`` is documented as *matching*
    ``Segment.position``. Restarting the exit at zero was a real defect while it lasted: the
    by-segment node reported ``segment 2`` and ``segment 3`` for the way out while the exit
    edges said ``segment 0`` and ``segment 1``, so the one cross-reference FR-020's second axis
    exists to provide -- see which hop dominates, then go find it -- pointed at the wrong hop.
    """
    return [
        (
            direction,
            Segment(position=position_from + offset, route_id=route_id),
            routes[route_id],
            verdict,
        )
        for offset, route_id in enumerate(segment_ids)
    ]


def _annotations(result: RampCost) -> tuple[list[tuple[list[str], str | None]], str | None]:
    """Every free-standing note beside the path, in a fixed order, and the exit-unknown node.

    Separated from :func:`_drawn` because it is where all the branching lives: four exit shapes,
    two optional spread notes, one optional identity note. A function whose job is "which notes
    does this result earn" is readable; the same branches inlined among node and edge emission
    were not.

    The order is fixed and therefore so are the ``x<k>`` ids (FR-016). The exit-unknown node's
    id is returned because an edge points at it, and finding it again by matching on its text
    would make the diagram's structure depend on its prose.
    """
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

    if isinstance(result.exit_path, ExitByIdentity):
        annotations.append((_identity_fields(result), marks.STYLE_CLASS[Mark.EXIT_BY_IDENTITY]))
    annotations.append((_by_segment_fields(ONE_WAY, result.one_way.by_segment), None))
    if isinstance(result.round_trip, RoundTripCost):
        annotations.append((_by_segment_fields(ROUND_TRIP, result.round_trip.by_segment), None))
    if result.one_way.spreads_over_reference:
        annotations.append((_spread_fields(ONE_WAY, result.one_way), None))
    if isinstance(result.round_trip, RoundTripCost) and result.round_trip.spreads_over_reference:
        annotations.append((_spread_fields(ROUND_TRIP, result.round_trip), None))
    annotations.append((_reported_beside_fields(result), None))
    return annotations, exit_unknown_node


def _drawn(
    result: RampCost,
    routes: Mapping[str, Route],
    channels: Mapping[str, FxChannel],
    regime_id: str,
) -> Diagram:
    """The path itself, once the input has been established to be a costed result."""
    chains = _walked(candidates.segments_of(result.path), routes, INBOUND, result.one_way.staleness)
    if isinstance(result.round_trip, RoundTripCost) and result.exit_path is not None:
        # The exit segments' observations are in the *round-trip* verdict: it is the merged
        # verdict over every route the journey touched, and the one-way verdict never aged
        # them. Empty for EXIT_BY_IDENTITY, which is a way out with no legs.
        chains.extend(
            _walked(
                candidates.exit_segments_of(result.exit_path),
                routes,
                EXIT,
                result.round_trip.staleness,
                position_from=len(candidates.segments_of(result.path)),
            )
        )

    venue_ids = sorted(
        {
            venue
            for _, _, route, _ in chains
            for leg in route.legs
            for venue in (leg.from_venue, leg.to_venue)
        }
    )
    node_of = {venue_id: mermaid.node_id(index) for index, venue_id in enumerate(venue_ids)}

    composed = isinstance(result.path, ComposedPath)
    by_identity = isinstance(result.exit_path, ExitByIdentity)
    caption_marks = list(
        marks.epistemic(result.one_way.provenance, stale=bool(result.one_way.staleness.stale))
    )
    if composed:
        caption_marks.append(Mark.COMPOSED)
    if by_identity:
        caption_marks.append(Mark.EXIT_BY_IDENTITY)

    lines = [
        mermaid.node(
            mermaid.CAPTION_ID,
            mermaid.label(
                "costed path",
                f"regime: {mermaid.escape(regime_id)}",
                f"destination: {mermaid.escape(result.path.destination_id)}",
                f"stream: {mermaid.escape(result.path.stream_id)}",
                _way_in_field(result.path),
                _way_out_field(result),
                # Named as the way in's, because that is what it describes: on a chain it is the
                # tightest *inbound* segment's status, and a constrained exit segment does not
                # move it (004, a stated gap). An unqualified "status" on a record whose headline
                # number is the round trip would read as covering both halves.
                f"status (way in, tightest segment): {result.status}",
                marks.segment(tuple(caption_marks)),
            ),
            # Through the rule, not around it. What a composed caption emphasises is that
            # it is composed (004 FR-013): the epistemic marks are already emphasised on
            # the cost nodes beside it, and ``style_class_for``'s own docstring says which
            # of several marks draws the eye changes nothing a reader needs.
            style_class=marks.style_class_for((Mark.COMPOSED,) if composed else caption_marks),
        )
    ]

    annotations, exit_unknown_node = _annotations(result)

    lines.extend(
        mermaid.node(mermaid.annotation_id(index), mermaid.label(*fields), style_class=style)
        for index, (fields, style) in enumerate(annotations)
    )

    for venue_id in venue_ids:
        fields = [f"venue {mermaid.escape(venue_id)}"]
        style: str | None = None
        if by_identity and venue_id == result.path.destination_id:
            fields.append(marks.segment((Mark.EXIT_BY_IDENTITY,)))
            fields.append("a declared spendable endpoint, so nothing has to leave it")
            style = marks.STYLE_CLASS[Mark.EXIT_BY_IDENTITY]
        lines.append(mermaid.node(node_of[venue_id], mermaid.label(*fields), style_class=style))

    for direction, segment, route, verdict in chains:
        for leg in sorted(route.legs, key=lambda item: item.index):
            lines.append(
                mermaid.edge(
                    node_of[leg.from_venue],
                    node_of[leg.to_venue],
                    mermaid.label(
                        *_leg_fields(
                            leg,
                            segment,
                            route,
                            direction=direction,
                            quote=figures.quote_for(leg, channels),
                            verdict=verdict,
                        )
                    ),
                )
            )

    if exit_unknown_node is not None:
        lines.append(
            mermaid.edge(
                node_of[result.path.destination_id],
                exit_unknown_node,
                mermaid.label(
                    marks.segment((Mark.EXIT_COST_UNKNOWN,)),
                    "the exit that would go here has not been declared",
                ),
                dotted=True,
            )
        )

    lines.extend(mermaid.class_defs(lines, marks.CLASS_DEFS))

    return Diagram(
        text=mermaid.document(lines),
        kind="costed_path",
        regime_id=regime_id,
        mode=None,
    )


def _in_force(result: RampCost, regime: Regime) -> None:
    """Refuse to draw a journey the regime does not include, naming every segment it excludes.

    **Every** segment, both halves. A chain is in force only if each of its declared routes is,
    and a regime that excluded one hop of a three-hop candidate would otherwise get a picture of
    a corridor its own belief says is not there -- with two thirds of it looking perfectly
    ordinary. Checking the way out too is the same reading ``regimes.routes_in_force`` takes when
    it refuses a regime that includes an inbound route while excluding its declared partner.

    ``EXIT_BY_IDENTITY`` contributes no segments and so is never excluded: it is a fact about the
    owner's spendable list, which a regime has no opinion about.
    """
    walked = candidates.segments_of(result.path)
    if result.exit_path is not None:
        walked += candidates.exit_segments_of(result.exit_path)
    missing = sorted(set(walked) - regime.route_ids)
    if missing:
        raise ValueError(
            f"regime {regime.id!r} does not include route(s) {missing}, so this journey does "
            "not exist under it. A diagram shows one regime (FR-019), and drawing a corridor "
            "the regime excludes would picture something the scenario says is not there"
        )


def render_path(
    result: RampCost | RouteUnusable | ExitCostUnknown | NothingComparable,
    *,
    routes: Mapping[str, Route],
    channels: Mapping[str, FxChannel],
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
            _in_force(result, regime)
            return _drawn(result, routes, channels, regime.id)
        case RouteUnusable() | ExitCostUnknown() | NothingComparable():
            return NothingToDraw(reason=result.reason, kind="costed_path")
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(result)
