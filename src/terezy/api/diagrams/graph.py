"""The declared route graph for one named regime, derived entirely from the declarations.

FR-002 through FR-006 and FR-019. Feature 002 made the registry a graph -- venues are nodes,
routes and their legs are edges -- and then left everyone who debugs it to reconstruct that
graph in their head from TOML tables. This module does that reconstruction once, mechanically.

**Nothing here is hand-maintained.** A diagram element with no declaration behind it is a
defect (FR-002), which is also why adding a venue, provider, route or corridor as data appears
in the re-rendered picture with zero source changes (FR-003, SC-002). No venue, provider or
corridor is named anywhere in this file.

## What is on a registry graph, and what may never be

Two modes (FR-006), each named on the face of the diagram so a numberless picture is never
read as "zero fees":

* :attr:`~terezy.api.diagrams.Mode.TOPOLOGY` -- what connects to what, and no figures.
* :attr:`~terezy.api.diagrams.Mode.DECLARED_FIGURES` -- the same picture plus each leg's
  **declared** fees, each carrying its provenance state.

**A computed ramp cost appears on neither**, and that is the point of forbidding it in the
mode that shows numbers too. Such a figure exists only per ``(destination x stream x route)``
-- a triple a registry graph does not name -- so putting one here would be feature 002's
FR-008 violated in picture form. A costed figure belongs on a costed path
(:mod:`terezy.api.diagrams.path`), which names the triple in its caption.

**The channel premium is on this diagram, and it is the figure that matters most.** Every fee
on the §4.3.1 corridor is declared zero; the whole of its 6.67% one-way cost is the ``p2p``
channel's ``+3.00 UAH per USD`` against a 42.00 reference. A with-figures graph showing only
the leg fees would draw the most expensive corridor in the registry as free -- the mislabelled
figure in picture form. Both declared forms render, each in its own unit and neither converted
into the other, and the applied side carries its own source, its own kind and its own
staleness, so a stale premium on a fresh-fee leg never renders clean.

## Two things this renderer computes, and why each is allowed

FR-008 forbids the renderer to compute a *figure*. These are not figures.

* **The *no exit declared* mark** (FR-005) is computed here from the declarations, by asking
  whether any exit route the regime includes leaves that destination. ``core.routes.coverage``
  is deliberately **not** imported (research.md D6): its verdicts are per regime and advisory,
  and reading them would put a verdict on a diagram that feature 003 says must not drive
  anything. Asking the declarations directly is a smaller question with the same answer.
* **Staleness** is computed through ``core.primitives.staleness``, under each leg's own
  declared ``kind_of_observation`` and against the caller's ``as_of``. The threshold is
  feature 002's, applied by feature 002's function -- not a rule invented here (FR-013).

⚙ **``channels``, ``kinds`` and ``as_of`` are on the signature and were not in
``contracts/rendering.md`` as first written.** The contract's parameter list carried none of
them and could not satisfy its own guarantees. ``kinds`` and ``as_of`` because FR-013's
staleness is ``as_of - retrieved_on`` against a *declared per-kind* threshold; making them
optional was rejected, since an unassessed diagram would be indistinguishable from a clean one,
which is the silent permissive default FR-028 forbids and the very ambiguity
``staleness.UNASSESSED`` exists to remove. ``channels`` because FR-006's with-figures mode
names "fees, premiums" and a premium is declared on an ``FxChannel``. All three are declared
records this renderer is handed; it still reads no declaration file of its own (FR-020).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from terezy.api.diagrams import Diagram, Mode, NothingToDraw, figures, marks, mermaid
from terezy.api.diagrams.figures import Quote
from terezy.api.diagrams.marks import Mark
from terezy.core.primitives import staleness
from terezy.core.primitives.staleness import ObservationKind
from terezy.core.routes.channels import FxChannel
from terezy.core.routes.legs import Leg, Route
from terezy.core.routes.venues import Venue
from terezy.core.scenarios.regimes import Regime

_MODE_NOTE: Mapping[Mode, str] = {
    Mode.TOPOLOGY: "no figures shown -- an absent number is not a zero",
    Mode.DECLARED_FIGURES: (
        "shows declared per-leg fees and channel premiums only -- no computed ramp cost "
        "appears on a registry graph"
    ),
}
"""What each mode's name means, said on the diagram beside it.

FR-006 requires the mode to be visible so a numberless picture is never mistaken for "zero
fees". The name alone would leave that to the reader's memory, so the reason travels with it.
"""


def _distinct_ids(
    records: Mapping[str, Venue] | Mapping[str, Route] | Mapping[str, FxChannel], what: str
) -> None:
    """Refuse a mapping whose keys and declared ids do not agree one-to-one.

    SC-008's second half: *an engineered identifier collision between two distinct venues
    fails loudly naming both*. Node ids are positional, so two entities can never be merged by
    *sanitising* -- but two records declaring one id, reached under two keys, are two things
    the declarations say are one, and drawing them as two nodes labelled identically would be
    a picture nobody could read. Raised rather than typed, on the precedent of
    ``regimes.routes_in_force``: the data layer validates uniqueness at load and can name the
    file, so reaching here collided means that validation was bypassed.
    """
    by_declared_id: dict[str, list[str]] = {}
    for key, record in records.items():
        by_declared_id.setdefault(record.id, []).append(key)
    collided = {
        declared: sorted(keys) for declared, keys in by_declared_id.items() if len(keys) > 1
    }
    if collided:
        raise ValueError(
            f"two distinct {what} records declare one id and would draw as one element: "
            f"{collided}. Distinct declared entities stay distinct (FR-018); they are never "
            "silently merged"
        )
    mismatched = sorted(key for key, record in records.items() if key != record.id)
    if mismatched:
        raise ValueError(
            f"{what} keyed under an id it does not declare: {mismatched}. The mapping key is "
            "the declared id everywhere else in this project, and a diagram that trusted one "
            "and labelled the other would name the wrong thing"
        )


def _drawn_routes(routes: Mapping[str, Route], regime: Regime) -> tuple[Route, ...]:
    """The regime's routes, sorted by id, or a raise naming what it asked for and missed.

    Sorted rather than in the regime's own order, because ``Regime.route_ids`` is a
    ``frozenset`` -- iterating it would make the diagram's text depend on hash order, and
    byte-identity across runs is what qualifies the output to be a golden artifact (FR-016,
    research.md D9).
    """
    missing = sorted(regime.route_ids - set(routes))
    if missing:
        raise KeyError(
            f"regime {regime.id!r} names route(s) {missing} that are not declared. A regime "
            f"selects from the declared routes; it declares none of its own. Known routes: "
            f"{sorted(routes)}"
        )
    return tuple(routes[route_id] for route_id in sorted(regime.route_ids))


def _venue_node_ids(venues: Mapping[str, Venue]) -> dict[str, str]:
    """Every declared venue's positional node id, assigned in sorted order.

    **Every** declared venue, not only the ones the regime's routes touch. SC-001 asks that
    every declared venue appear exactly once, and a venue no route reaches is a fact worth
    seeing: it is a place money can sit with no declared way in or out.
    """
    return {venue_id: mermaid.node_id(index) for index, venue_id in enumerate(sorted(venues))}


def _leg_marks(
    leg: Leg,
    route: Route,
    quote: Quote | None,
    kinds: Mapping[str, ObservationKind],
    as_of: date,
) -> tuple[Mark, ...]:
    """Every mark this leg's edge carries: its epistemic state, plus its route's status.

    The leg's own declaration **and** the quote it applies, unioned. A stale premium on a leg
    whose fee schedule is fresh must not render clean: one unverified or stale input taints the
    figure, the same asymmetry ``provenance.is_unverified`` and ``staleness.any_stale`` use, and
    on this edge the premium is usually the whole cost.

    Each observation is still aged under the kind **its own table** declared -- the leg's fee
    schedule under the leg's, the reference under the channel's, the side under the side's --
    and only the verdicts are merged (FR-028).
    """
    verdicts = [
        staleness.staleness_of(leg.provenance, kinds, kind=leg.kind_of_observation, as_of=as_of)
    ]
    if quote is not None:
        verdicts.extend(figures.verdicts(quote, kinds, as_of))
    stale = staleness.any_stale(staleness.merge_all(verdicts))
    found = list(marks.epistemic(figures.edge_provenance(leg, quote), stale=stale))
    if route.status == "closed":
        found.append(Mark.CLOSED)
    return tuple(mark for mark in Mark if mark in set(found))


def _currency_field(leg: Leg) -> str:
    """What the leg moves: one currency, or the pair it crosses.

    Structure rather than a figure, so it appears in both modes -- which is what makes
    SC-012's "the two modes differ by figures only" a claim about figures.
    """
    if leg.from_ccy is leg.to_ccy:
        return leg.from_ccy.value
    return f"{leg.from_ccy.value} to {leg.to_ccy.value}"


def _leg_fields(
    leg: Leg,
    route: Route,
    mode: Mode,
    quote: Quote | None,
    applicable: tuple[Mark, ...],
) -> list[str]:
    """One edge's label, field by field.

    Every declared string goes through :func:`mermaid.escape`; every figure goes through
    :mod:`terezy.api.diagrams.numbers` and appears only in
    :attr:`~terezy.api.diagrams.Mode.DECLARED_FIGURES`.
    """
    fields = [
        f"route {mermaid.escape(route.id)}",
        f"provider {mermaid.escape(route.provider)}",
        f"leg {leg.index} {mermaid.escape(leg.kind)}",
        _currency_field(leg),
    ]
    if leg.channel is not None:
        fields.append(f"via channel {mermaid.escape(leg.channel)}")
    if mode is Mode.DECLARED_FIGURES:
        fields.extend(figures.edge_figures(leg, quote))
    fields.append(f"status: {route.status}")
    fields.append(
        marks.segment(applicable, unsourced=marks.is_unsourced(figures.edge_provenance(leg, quote)))
    )
    return fields


def _destinations_without_an_exit(drawn: tuple[Route, ...]) -> tuple[str, ...]:
    """Inbound destinations the regime declares no way out of, sorted (FR-005).

    Asked of the regime's own routes rather than of every declared route: a regime is which
    corridors exist while it holds, so an exit route the regime excludes is not a way out
    under it. The same reading ``regimes.routes_in_force`` takes when it refuses a regime that
    includes an inbound route while excluding its declared partner.
    """
    arrivals = {route.destination for route in drawn if route.direction == "inbound"}
    departures = {route.origin for route in drawn if route.direction == "exit"}
    return tuple(sorted(arrivals - departures))


def _caption(regime: Regime, mode: Mode, as_of: date, *, synthetic: bool, empty: str | None) -> str:
    """The node that says what this diagram is a picture of.

    A node and not a comment, because a comment is discarded by every renderer and FR-006,
    FR-014 and FR-019 all require their fact to be *displayed*. It carries the as-of date
    because the stale marks below were assessed against it, and a mark whose reference date is
    invisible cannot be checked by the person reading it.
    """
    fields = [
        "route graph",
        f"regime: {mermaid.escape(regime.id)}",
        f"mode: {mode.value} ({_MODE_NOTE[mode]})",
        f"staleness assessed as of {as_of.isoformat()}",
    ]
    if empty is not None:
        fields.append(f"EMPTY: {empty}")
    if synthetic:
        fields.append(marks.segment((Mark.SYNTHETIC,)))
    return mermaid.label(*fields)


def _emptiness(venues: Mapping[str, Venue], drawn: tuple[Route, ...]) -> str | None:
    """What, if anything, this diagram has nothing of -- said in words, never left blank.

    An empty registry or a regime with no routes is *an explicitly empty diagram that says
    so*, never a blank output indistinguishable from a failed render, and never an error
    (spec.md, Edge Cases). It is a :class:`Diagram`, not a
    :class:`~terezy.api.diagrams.NothingToDraw`: there is genuinely nothing wrong, and the
    honest picture of a registry with nothing in it is a picture that says it is empty.
    """
    missing = []
    if not venues:
        missing.append("no venues are declared")
    if not drawn:
        missing.append("this regime includes no routes")
    return " and ".join(missing) if missing else None


def render_graph(
    *,
    venues: Mapping[str, Venue],
    routes: Mapping[str, Route],
    channels: Mapping[str, FxChannel],
    regime: Regime,
    mode: Mode,
    kinds: Mapping[str, ObservationKind],
    as_of: date,
) -> Diagram | NothingToDraw:
    """The declared registry for one regime, as Mermaid text.

    ``regime`` has no default, sentinel or overload, and that is FR-019 taken at its word: a
    merged graph existing under no regime must not be **producible**, and the strongest
    reading of "not producible" is that no argument list expresses it. A runtime check can be
    bypassed by the next caller; a missing parameter cannot.

    ``as_of`` decides staleness and is never a clock -- the same discipline as
    ``core.routes.cost.cost_one``. It is an input to the run, it is printed on the diagram, and
    it is what makes two renders of the same declarations byte-identical (FR-016).

    Returns a :class:`~terezy.api.diagrams.Diagram`. The declared return type includes
    :class:`~terezy.api.diagrams.NothingToDraw` because that is the union both renderers
    share, so a caller matches once over both -- but **no input to this function produces
    one**, deliberately: the spec turns every candidate refusal into either a diagram that
    says it is empty (an empty registry, a regime with no routes) or a loud failure (a regime
    naming an undeclared route, a leg naming an undeclared venue, two records declaring one
    id). Refusals belong to costed results, where the input is itself a typed refusal.
    """
    _distinct_ids(venues, "venue")
    _distinct_ids(routes, "route")
    _distinct_ids(channels, "channel")
    drawn = _drawn_routes(routes, regime)
    node_of = _venue_node_ids(venues)

    for route in drawn:
        for leg in route.legs:
            for venue_id in (leg.from_venue, leg.to_venue):
                if venue_id not in node_of:
                    raise KeyError(
                        f"leg {leg.index} of route {route.id!r} names venue {venue_id!r}, "
                        f"which is not declared. A diagram draws declared venues; it invents "
                        f"none. Known venues: {sorted(venues)}"
                    )

    without_exit = _destinations_without_an_exit(drawn)
    quotes = {
        (route.id, leg.index): figures.quote_for(leg, channels)
        for route in drawn
        for leg in route.legs
    }
    synthetic = any(
        marks.is_synthetic(figures.edge_provenance(leg, quotes[route.id, leg.index]))
        for route in drawn
        for leg in route.legs
    )

    lines = [
        mermaid.node(
            mermaid.CAPTION_ID,
            _caption(
                regime,
                mode,
                as_of,
                synthetic=synthetic,
                empty=_emptiness(venues, drawn),
            ),
        )
    ]

    for venue_id in sorted(venues):
        venue = venues[venue_id]
        fields = [
            f"venue {mermaid.escape(venue.id)}",
            f"name {mermaid.escape(venue.name)}",
        ]
        style: str | None = None
        if venue_id in without_exit:
            fields.append(marks.segment((Mark.NO_EXIT_DECLARED,)))
            fields.append("not comparison-ready")
            style = marks.STYLE_CLASS[Mark.NO_EXIT_DECLARED]
        lines.append(mermaid.node(node_of[venue_id], mermaid.label(*fields), style_class=style))

    for index, venue_id in enumerate(without_exit):
        lines.append(
            mermaid.node(
                mermaid.annotation_id(index),
                mermaid.label(
                    marks.segment((Mark.NO_EXIT_DECLARED,)),
                    f"nothing this regime includes leaves {mermaid.escape(venue_id)}",
                    "so no round-trip figure exists for it",
                ),
                style_class=marks.STYLE_CLASS[Mark.NO_EXIT_DECLARED],
            )
        )

    for route in drawn:
        for leg in sorted(route.legs, key=lambda item: item.index):
            quote = quotes[route.id, leg.index]
            applicable = _leg_marks(leg, route, quote, kinds, as_of)
            lines.append(
                mermaid.edge(
                    node_of[leg.from_venue],
                    node_of[leg.to_venue],
                    mermaid.label(*_leg_fields(leg, route, mode, quote, applicable)),
                    dotted=route.status == "closed",
                )
            )

    for index, venue_id in enumerate(without_exit):
        lines.append(
            mermaid.edge(
                node_of[venue_id],
                mermaid.annotation_id(index),
                mermaid.label(
                    marks.segment((Mark.NO_EXIT_DECLARED,)),
                    "the absent edge, drawn rather than omitted",
                ),
                dotted=True,
            )
        )

    lines.extend(mermaid.class_defs(lines, marks.CLASS_DEFS))

    return Diagram(
        text=mermaid.document(lines),
        kind="route_graph",
        regime_id=regime.id,
        mode=mode,
    )
