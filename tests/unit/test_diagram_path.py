"""One costed result, drawn as its path, with every figure taken verbatim from the result.

**SC-006**; **FR-007** through **FR-010**. This is where the numbers meet the picture, and
feature 002's central sentence -- *"most of the gap is the ramp, not the asset"* -- is a
sentence about **which edge is expensive**.

Four claims, each of which is a way the picture could disagree with the result it depicts:

1. **The legs drawn are the legs costed**, in order. A path diagram that redrew the route
   from the registry rather than from the result would freshen a picture of a past decision.
2. **The exit is the declared exit route's own legs and venues** (FR-010), never the inbound
   chain reversed. Reversal is the mistake feature 002 designed ``partner_route`` to prevent,
   and it is invisible in a picture unless someone checks the venues.
3. **Every cost is labelled one-way or round-trip, and the spread over reference is labelled
   as itself** (FR-009). The two differ -- 6.67% against 7.14% at §4.3.1's numbers -- and
   reporting the rate-space figure as the cost is a mistake this project made once already.
4. **Every figure equals the result's figure through the one rule** (SC-006, FR-022). Asserted
   by construction against ``numbers``, over every figure in the text, not sampled.
"""

from __future__ import annotations

import re
from dataclasses import replace

import pytest

from terezy.api.diagrams import Diagram, figures, numbers, render_path
from terezy.api.diagrams import marks as diagram_marks
from terezy.api.diagrams.marks import Mark
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.ramp import CostComponent, RoundTripCost
from terezy.core.routes import path as candidates
from terezy.core.routes.path import ExitByIdentity
from tests import diagram_registries as fixture

SEPARATOR = " · "
FIGURE = re.compile(r"-?\d+\.\d\d")
EDGE = re.compile(r'^\s*(\w+) -\.?->\|"(.*?)"\| (\w+)$', re.MULTILINE)
NODE = re.compile(r'^\s*(\w+)\["(.*?)"\](?::::\w+)?$', re.MULTILINE)


def venue_nodes(text: str) -> dict[str, str]:
    return {
        identifier: label.split(SEPARATOR)[0].removeprefix("venue ")
        for identifier, label in NODE.findall(text)
        if label.split(SEPARATOR)[0].startswith("venue ")
    }


def _leg_edge_fields(text: str) -> list[tuple[str, str, list[str]]]:
    """``(source node, target node, fields)`` for every edge that draws a leg."""
    found = []
    for source, label, target in EDGE.findall(text):
        fields = label.split(SEPARATOR)
        if len(fields) < 3 or not fields[2].startswith("route "):
            continue
        found.append((source, target, fields))
    return found


def leg_edges(text: str) -> list[tuple[str, str, str, str]]:
    """``(direction, route id, from venue, to venue)`` for every leg edge, in drawn order."""
    nodes = venue_nodes(text)
    return [
        (fields[0], fields[2].removeprefix("route "), nodes[source], nodes[target])
        for source, target, fields in _leg_edge_fields(text)
    ]


def segment_edges(text: str) -> list[tuple[str, int, str]]:
    """``(direction, segment position, route id)`` for every leg edge, in drawn order.

    The chain, as the diagram draws it. A composed candidate is several segments and a declared
    route is one, and the position is what makes ``leg 0`` twice in one journey readable.
    """
    return [
        (fields[0], int(fields[1].removeprefix("segment ")), fields[2].removeprefix("route "))
        for _, _, fields in _leg_edge_fields(text)
    ]


def all_labels(text: str) -> list[str]:
    return [found.group(2) for found in EDGE.finditer(text)] + [
        found.group(2) for found in NODE.finditer(text)
    ]


class TestTheDrawnLegsAreTheCostedLegs:
    """FR-007, and the exit route drawn as itself (FR-010)."""

    def test_the_inbound_legs_are_the_routes_own_legs_in_order(self) -> None:
        declared = fixture.shipped_declarations()
        route = declared.routes[fixture.P2P_ROUTE]
        drawn = [
            entry
            for entry in leg_edges(fixture.drawn_path(fixture.p2p_cost()).text)
            if entry[0] == "inbound"
        ]
        assert drawn == [
            ("inbound", route.id, leg.from_venue, leg.to_venue)
            for leg in sorted(route.legs, key=lambda item: item.index)
        ]

    def test_the_exit_is_the_declared_partner_routes_own_legs(self) -> None:
        """Never the inbound reversed: the way out has its own legs and its own side of
        every spread, and reversing the way in would be wrong wherever the two differ."""
        declared = fixture.shipped_declarations()
        inbound = declared.routes[fixture.P2P_ROUTE]
        assert inbound.partner_route is not None
        exit_route = declared.routes[inbound.partner_route]
        drawn = [
            entry
            for entry in leg_edges(fixture.drawn_path(fixture.p2p_cost()).text)
            if entry[0] == "exit"
        ]
        assert drawn == [
            ("exit", exit_route.id, leg.from_venue, leg.to_venue)
            for leg in sorted(exit_route.legs, key=lambda item: item.index)
        ]

    def test_the_exit_is_not_the_inbound_chain_reversed(self) -> None:
        """The assertion that would fail if someone "simplified" FR-010 away."""
        declared = fixture.shipped_declarations()
        inbound = declared.routes[fixture.P2P_ROUTE]
        edges = leg_edges(fixture.drawn_path(fixture.p2p_cost()).text)
        reversed_inbound = [
            ("exit", inbound.id, leg.to_venue, leg.from_venue) for leg in reversed(inbound.legs)
        ]
        assert [entry for entry in edges if entry[0] == "exit"] != reversed_inbound

    def test_every_venue_on_the_path_is_a_node_exactly_once(self) -> None:
        text = fixture.drawn_path(fixture.p2p_cost()).text
        drawn = list(venue_nodes(text).values())
        assert len(set(drawn)) == len(drawn)
        touched = {venue for _, _, source, target in leg_edges(text) for venue in (source, target)}
        assert set(drawn) == touched

    def test_the_diagram_names_the_whole_triple_a_cost_is_keyed_by(self) -> None:
        """FR-008 of feature 002: a cost is per ``(destination x stream x route)``.

        A path diagram that named only the destination would be the per-destination cost
        this project made structurally unrepresentable, re-created in a picture.
        """
        caption = fixture.drawn_path(fixture.p2p_cost()).text.splitlines()[1]
        for field in (
            "destination: binance",
            f"stream: {fixture.UAH_STREAM}",
            f"way in: declared route {fixture.P2P_ROUTE}",
        ):
            assert field in caption


class TestEveryFigureIsTheResultsFigureThroughTheOneRule:
    """SC-006, over every figure in the text rather than a sampled one."""

    def test_the_one_way_cost_is_the_results_own_fraction(self) -> None:
        cost = fixture.p2p_cost()
        text = fixture.drawn_path(cost).text
        assert f"one-way cost {numbers.percent(cost.one_way.fraction)}" in text
        assert numbers.amount(cost.one_way.sent) in text
        assert numbers.amount(cost.one_way.arrived) in text

    def test_the_round_trip_cost_is_the_results_own_fraction(self) -> None:
        cost = fixture.p2p_cost()
        assert isinstance(cost.round_trip, RoundTripCost)
        text = fixture.drawn_path(cost).text
        assert f"round-trip cost {numbers.percent(cost.round_trip.fraction)}" in text

    def test_every_component_of_the_charge_appears_with_its_own_name(self) -> None:
        """The closed component set, all three, so a zero is visible as a zero."""
        cost = fixture.p2p_cost()
        text = fixture.drawn_path(cost).text
        for component in CostComponent:
            amount = cost.one_way.components[component]
            assert f"{component.value} {numbers.amount(amount)}" in text

    def test_every_figure_in_the_text_is_a_figure_the_result_carries(self) -> None:
        """No number on the diagram was computed here.

        Built as a set membership rather than by re-deriving anything: every two-decimal
        value in the text must be one the result's own fields render to through the one rule.
        A figure the renderer invented would not be in the permitted set.
        """
        cost = fixture.p2p_cost()
        assert isinstance(cost.round_trip, RoundTripCost)
        permitted = {
            numbers.percent(cost.one_way.fraction),
            numbers.percent(cost.round_trip.fraction),
            numbers.percent(cost.disruption_probability),
            numbers.amount(cost.one_way.sent),
            numbers.amount(cost.one_way.arrived),
            numbers.amount(cost.round_trip.sent),
            numbers.amount(cost.round_trip.arrived),
            *(numbers.amount(value) for value in cost.one_way.components.values()),
            *(numbers.amount(value) for value in cost.round_trip.components.values()),
            # 004's second axis: what each segment charged, by component. The result's own
            # figures, so they belong in the permitted set exactly as the totals do.
            *(
                numbers.amount(amount)
                for half in (cost.one_way.by_segment, cost.round_trip.by_segment)
                for entry in half
                for amount in entry.components.values()
            ),
            *(numbers.percent(value) for value in cost.one_way.spreads_over_reference),
            *(numbers.percent(value) for value in cost.round_trip.spreads_over_reference),
            *(
                f"{numbers.percent(leg.fee_pct)}"
                for route_id in (fixture.P2P_ROUTE, *candidates.segments_of(cost.path))
                for leg in fixture.shipped_declarations().routes[route_id].legs
            ),
            # Declared, not computed: the quote each converting leg applies, rendered by the
            # same one rule and taken from the same channel records the costing used.
            *(
                field
                for route in fixture.shipped_declarations().routes.values()
                for leg in route.legs
                for quote in [figures.quote_for(leg, fixture.shipped_declarations().channels)]
                if quote is not None
                for field in [quote.figure]
            ),
        }
        if cost.ceiling is not None:
            permitted.add(numbers.amount(cost.ceiling))
        rendered = {found.group(0) for found in FIGURE.finditer(fixture.drawn_path(cost).text)}
        unexplained = {
            value for value in rendered if not any(value in allowed for allowed in permitted)
        }
        assert not unexplained, f"the diagram carries figures the result does not: {unexplained}"

    def test_the_converting_leg_carries_the_channel_premium_that_is_its_whole_cost(
        self,
    ) -> None:
        """**M4.** The edge where the §4.3.1 cost actually lives must say where it comes from.

        Every declared fee on this corridor is zero and the whole 6.67% is the ``p2p``
        channel's ``+3.00 UAH per USD`` against a 42.00 reference. An edge labelled
        ``declared fee 0.00%`` and nothing else, on the very picture drawn to show where a cost
        comes from, answers that question with a zero -- and the figures node above it does not
        repair it, because a total at the top does not survive someone looking at one edge.
        """
        declared = fixture.shipped_declarations()
        text = fixture.drawn_path(fixture.p2p_cost(declared)).text
        converting = [label for _, label, _ in EDGE.findall(text) if " fx · " in f" {label} "]
        assert converting, "the fixture route no longer converts, so this proves nothing"
        for label in converting:
            assert figures.PREMIUM_FIELD in label
            assert figures.ABOVE in label or figures.BELOW in label
        inbound = next(label for label in converting if label.startswith("inbound"))
        assert "+3.00 UAH per USD" in inbound
        assert "declared fee 0.00% + 0.00 UAH" in inbound, (
            "if the fee stopped being zero, this corridor would no longer be the case where "
            "the premium is the entire cost"
        )

    def test_the_inbound_and_exit_legs_take_opposite_sides_of_the_same_channel(self) -> None:
        """Both cross ``p2p``; the way in buys dollars and the way out sells them.

        Drawn as the same channel with opposite directions, which is what makes the round trip
        cost 12.22% rather than twice nothing -- and what a reader checking FR-010 looks for.
        """
        text = fixture.drawn_path(fixture.p2p_cost()).text
        inbound = next(
            label
            for _, label, _ in EDGE.findall(text)
            if "inbound · " in label and " fx · " in label
        )
        outbound = next(
            label for _, label, _ in EDGE.findall(text) if "exit · " in label and " fx · " in label
        )
        assert "(buy side)" in inbound
        assert "(sell side)" in outbound
        assert "+3.00 UAH per USD" in inbound
        assert "-2.50 UAH per USD" in outbound

    def test_the_same_leg_carries_the_same_figures_on_both_diagram_kinds(self) -> None:
        """The costed path and the registry graph draw the same leg, so they say the same thing.

        Compared field by field rather than by eye: a reader holding the two diagrams together
        is entitled to line them up, and either renderer quietly gaining or losing a figure is
        exactly what this catches.
        """
        declared = fixture.shipped_declarations()
        leg = declared.routes[fixture.P2P_ROUTE].legs[0]
        quote = figures.quote_for(leg, declared.channels)
        expected = figures.edge_figures(leg, quote)
        path_text = fixture.drawn_path(fixture.p2p_cost(declared)).text
        label = next(
            label
            for _, label, _ in EDGE.findall(path_text)
            if f"route {fixture.P2P_ROUTE}" in label and "leg 0 " in label
        )
        assert [
            field for field in label.split(SEPARATOR) if field.startswith(figures.FIGURE_FIELD)
        ] == expected

    def test_a_stale_premium_marks_the_edge_that_charges_it(self) -> None:
        """**M4.** The verdict is matched against the whole edge, the quote included.

        Costed at :data:`fixture.STALE_PREMIUM_AS_OF`, where exactly one observation on this
        corridor has aged: the ``p2p`` premium, at 7 days. The route's own legs age under
        ``regulatory_limit`` (180) and ``bank_fee_schedule`` (365) and are current.

        So matching the result's stale list against the leg's own sources alone leaves the fx
        edge -- the one that charges the entire 6.67% -- rendering clean while the figure it
        shows is years-stale in premium terms. The transfer leg beside it stays unmarked, which
        is what makes the mark mean something rather than appear everywhere.
        """
        text = fixture.drawn_path(fixture.stale_premium_cost()).text
        converting = next(
            label for _, label, _ in EDGE.findall(text) if "inbound" in label and " fx · " in label
        )
        transferring = next(
            label
            for _, label, _ in EDGE.findall(text)
            if "inbound" in label and " transfer · " in label
        )
        assert diagram_marks.token(Mark.STALE) in converting
        assert diagram_marks.token(Mark.STALE) not in transferring

    def test_that_result_really_has_a_stale_premium_and_fresh_legs(self) -> None:
        """Otherwise the contrast above holds for a reason that is not about the premium."""
        declared = fixture.shipped_declarations()
        cost = fixture.stale_premium_cost()
        stale_ids = {source.source_id for source in cost.one_way.staleness.stale}
        assert stale_ids, "nothing is stale at this as-of date, so the test above is vacuous"
        for leg in declared.routes[fixture.P2P_ROUTE].legs:
            assert not {ref.id for ref in leg.provenance.sources} & stale_ids, (
                "a leg's own observation has gone stale too, so the edge would be marked "
                "whether or not the quote were consulted"
            )
        quote = figures.quote_for(declared.routes[fixture.P2P_ROUTE].legs[0], declared.channels)
        assert quote is not None
        assert {ref.id for ref in figures.sources(quote).sources} & stale_ids

    def test_an_edge_whose_quote_was_never_aged_says_so_rather_than_reading_clean(
        self,
    ) -> None:
        """**F3.** ``AGE NOT ASSESSED`` is the third absence, and it must reach a real edge.

        The sibling of the stale case, and it fails the same way: if the verdict is consulted
        only about the leg's own sources, an edge whose *premium* was never aged reports
        ``VERIFIED AND CURRENT`` -- "nobody checked" wearing "checked and clean"'s tick, which
        is the exact ambiguity ``staleness.UNASSESSED`` exists to remove.

        No real run produces this: ``cost._aged`` ages every observation on every leg. A caller
        holding a narrower verdict can, so the renderer must not assume otherwise.
        """
        text = fixture.drawn_path(fixture.unassessed_cost()).text
        converting = next(
            label for _, label, _ in EDGE.findall(text) if "inbound" in label and " fx · " in label
        )
        transferring = next(
            label
            for _, label, _ in EDGE.findall(text)
            if "inbound" in label and " transfer · " in label
        )
        assert diagram_marks.UNASSESSED in fixture.marks_in(converting)
        assert diagram_marks.CLEAN not in fixture.marks_in(converting)
        assert diagram_marks.UNASSESSED not in fixture.marks_in(transferring), (
            "the transfer leg's own sources were assessed, so it must stay unmarked -- an "
            "absence reported everywhere reports nothing"
        )

    def test_that_narrowed_verdict_still_covers_every_leg_the_result_costed(self) -> None:
        """Otherwise the contrast above is about a missing leg, not a missing quote."""
        declared = fixture.shipped_declarations()
        assessed = set(fixture.unassessed_cost().one_way.staleness.assessed)
        for route_id in (fixture.P2P_ROUTE, "binance_p2p_to_monobank"):
            for leg in declared.routes[route_id].legs:
                assert {ref.id for ref in leg.provenance.sources} <= assessed
        quote = figures.quote_for(declared.routes[fixture.P2P_ROUTE].legs[0], declared.channels)
        assert quote is not None
        assert not {ref.id for ref in figures.sources(quote).sources} <= assessed

    def test_a_leg_with_no_figure_to_show_shows_no_number(self) -> None:
        """FR-008's second half: an edge shows a figure with its provenance state, or none.

        The result carries no *per-leg* attribution -- ``OneWayCost.components`` is the
        route's charge, split by term -- so an edge shows the leg's **declared** fees and
        nothing computed. The zero-fee legs of the P2P route render an explicit zero rather
        than a blank, because a declared zero is a figure and an absent one is not.
        """
        declared = fixture.shipped_declarations()
        text = fixture.drawn_path(fixture.p2p_cost(declared)).text
        for source, label, target in EDGE.findall(text):
            fields = label.split(SEPARATOR)
            if len(fields) < 2 or not fields[1].startswith("route "):
                continue
            found = [field for field in fields if FIGURE.search(field)]
            assert all(field.startswith(figures.FIGURE_FIELD) for field in found), (
                f"an edge from {source} to {target} carries a figure that is not a declared "
                f"one: {found}"
            )


class TestTheLabellingRulesHold:
    """FR-009, which is the rule this project already broke once."""

    def test_every_cost_figure_is_named_one_way_or_round_trip(self) -> None:
        text = fixture.drawn_path(fixture.p2p_cost()).text
        for label in all_labels(text):
            for field in label.split(SEPARATOR):
                if "cost " in field and FIGURE.search(field):
                    assert field.startswith(("one-way cost ", "round-trip cost ")), field

    def test_the_spread_over_reference_is_labelled_as_itself_and_never_as_the_cost(
        self,
    ) -> None:
        """§4.3.1's ``p/r`` is reported beside the cost, never as it (METHODOLOGY §16.2)."""
        cost = fixture.p2p_cost()
        text = fixture.drawn_path(cost).text
        spread = numbers.percent(cost.one_way.spreads_over_reference[0])
        assert f"spread over reference (one-way): {spread}" in text
        assert "not the cost" in text.casefold()
        assert spread != numbers.percent(cost.one_way.fraction), (
            "the fixture's spread and cost coincide, so this test proves nothing"
        )

    def test_the_disruption_probability_is_reported_beside_the_cost_never_inside_it(
        self,
    ) -> None:
        """FR-026: two different claims, and a single number blending them answers neither."""
        cost = fixture.p2p_cost()
        text = fixture.drawn_path(cost).text
        assert "reported beside the cost, never folded into it" in text
        assert numbers.percent(cost.disruption_probability) in text


class TestTheRegimeIsNamedAndEnforced:
    """FR-019 on a costed path: one regime, and it has to be the right one."""

    def test_the_regime_is_on_the_diagram_and_on_the_record(self) -> None:
        rendered = fixture.drawn_path(fixture.p2p_cost())
        assert isinstance(rendered, Diagram)
        assert rendered.regime_id == "wartime"
        assert rendered.kind == "costed_path"
        assert rendered.mode is None, "a costed path has no modes -- the figures are the point"
        assert "regime: wartime" in rendered.text.splitlines()[1]

    def test_a_path_whose_route_the_regime_excludes_fails_loudly(self) -> None:
        """A picture of a corridor the regime says does not exist is a picture of nothing."""
        with pytest.raises(ValueError, match=fixture.NO_PARTNER_ROUTE):
            fixture.path_of(fixture.exit_unknown_cost(), regime_id="wartime")

    def test_the_same_path_renders_under_the_regime_that_includes_it(self) -> None:
        """If it failed under both, the test above would prove nothing about the regime."""
        rendered = fixture.drawn_path(fixture.exit_unknown_cost(), regime_id="normalized")
        assert rendered.regime_id == "normalized"


class TestDeterminism:
    """FR-016 on the costed path too: the same result renders to the same bytes."""

    def test_two_renders_of_one_result_agree_byte_for_byte(self) -> None:
        cost = fixture.p2p_cost()
        assert fixture.drawn_path(cost).text == fixture.drawn_path(cost).text

    def test_the_text_ends_in_a_newline_and_no_line_carries_trailing_space(self) -> None:
        text = fixture.drawn_path(fixture.p2p_cost()).text
        assert text.endswith("\n")
        assert all(line == line.rstrip() for line in text.splitlines())


class TestTheDiagramRendersTheResultAndNotTheRegistry:
    """**004.** The way out comes from ``RampCost.exit_path``, never from ``partner_route``.

    Feature 002 read the inbound route's declared partner, because that was the only way out
    there was. 004 made the exit chain part of the *result's* identity -- three shapes, and the
    caller may choose among them -- so the diagram reads what was costed. That closes a real
    hole this test used to guard from the wrong side: repointing a declaration after a result
    was produced now cannot change the picture of that result, which is what "the path diagram
    renders the result it was given and never re-reads the registry to freshen a picture of a
    past decision" has meant in the docstring all along.
    """

    def test_repointing_the_declaration_does_not_move_the_drawn_exit(self) -> None:
        declared = fixture.shipped_declarations()
        cost = fixture.p2p_cost(declared)
        inbound = declared.routes[fixture.P2P_ROUTE]
        repointed = {**declared.routes, inbound.id: replace(inbound, partner_route=None)}
        drawn = render_path(
            cost,
            routes=repointed,
            channels=declared.channels,
            regime=fixture.shipped_regime(declared, "war_end", "wartime"),
        )
        assert isinstance(drawn, Diagram)
        assert drawn.text == fixture.drawn_path(cost).text

    def test_the_drawn_exit_is_exactly_the_results_exit_chain(self) -> None:
        cost = fixture.p2p_cost()
        assert cost.exit_path is not None
        drawn = list(
            dict.fromkeys(
                (position, route_id)
                for direction, position, route_id in segment_edges(fixture.drawn_path(cost).text)
                if direction == "exit"
            )
        )
        expected = list(enumerate(candidates.exit_segments_of(cost.exit_path)))
        assert drawn == expected, "a segment contributes one edge per leg; its identity is one"


class TestAComposedCandidateDrawsAsTheChainItIs:
    """**004 FR-013**: a composed candidate is visibly distinct from a declared route.

    *In every report* — and a diagram is a report. A chain exists only at query time: nobody
    declared it end to end, and a reader who could not tell it from a declared corridor would
    go looking for a file nobody wrote. Three things carry the distinction, and each is here:
    the ``COMPOSED`` mark, the caption saying so in words, and a ``segment`` field on every
    edge naming the declared route that hop **is**.

    The fixture is hand-built because the shipped registry composes nothing — see
    ``diagram_registries.CHAIN_IN`` for why searching for one would have produced no test.
    """

    @staticmethod
    def _text() -> str:
        return fixture.chain_path_of(fixture.composed_cost()).text

    def test_the_caption_says_the_way_in_is_a_chain_and_names_its_segments(self) -> None:
        caption = self._text().splitlines()[1]
        assert "way in: composed chain of 2 declared routes" in caption
        assert f"({fixture.HOP_ONE}+{fixture.HOP_TWO})" in caption
        assert "nobody declared this corridor end to end" in caption

    def test_the_caption_carries_the_composed_mark(self) -> None:
        caption = self._text().splitlines()[1]
        assert diagram_marks.token(Mark.COMPOSED) in fixture.marks_in(
            caption.split('["', 1)[1].rstrip('"]')
        )

    def test_a_declared_route_is_not_marked_composed(self) -> None:
        """A mark on every candidate would distinguish none of them."""
        caption = fixture.chain_path_of(fixture.declared_exit_chain_cost()).text.splitlines()[1]
        assert diagram_marks.token(Mark.COMPOSED) not in caption
        assert f"way in: declared route {fixture.HOP_ONE}" in caption

    def test_every_hop_is_drawn_as_a_numbered_segment_naming_its_declared_route(self) -> None:
        inbound = [entry for entry in segment_edges(self._text()) if entry[0] == "inbound"]
        assert list(dict.fromkeys(inbound)) == [
            ("inbound", 0, fixture.HOP_ONE),
            ("inbound", 1, fixture.HOP_TWO),
        ]

    def test_the_drawn_hops_are_the_segments_the_result_was_keyed_by(self) -> None:
        cost = fixture.composed_cost()
        drawn = list(
            dict.fromkeys(
                (position, route_id)
                for direction, position, route_id in segment_edges(self._text())
                if direction == "inbound"
            )
        )
        assert drawn == list(enumerate(candidates.segments_of(cost.path)))

    def test_the_exit_chain_draws_as_its_own_declared_segments(self) -> None:
        """004 FR-012's way out: a chain of declared exit routes, never the way in reversed."""
        cost = fixture.composed_cost()
        assert cost.exit_path is not None
        drawn = list(
            dict.fromkeys(
                (position, route_id)
                for direction, position, route_id in segment_edges(self._text())
                if direction == "exit"
            )
        )
        assert drawn == list(enumerate(candidates.exit_segments_of(cost.exit_path)))
        assert "way out: composed chain of 2 declared exit routes" in self._text().splitlines()[1]

    def test_the_by_segment_attribution_names_which_hop_charged(self) -> None:
        """004's second axis. On a chain the segment figures stop restating the totals, which
        is the whole reason the axis exists: a reader can see which declaration dominates."""
        cost = fixture.composed_cost()
        text = self._text()
        assert "one-way cost by segment" in text
        for entry in cost.one_way.by_segment:
            assert f"segment {entry.position} route {entry.route_id}: " in text
            for component, amount in entry.components.items():
                assert f"{component.value} {numbers.amount(amount)}" in text

    def test_the_segments_charged_differently_so_the_axis_says_something(self) -> None:
        """If every hop charged the same, naming the dominant one would be meaningless."""
        totals = [
            sum(amount.amount for amount in entry.components.values())
            for entry in fixture.composed_cost().one_way.by_segment
        ]
        assert len(totals) == 2
        assert totals[0] != totals[1]

    def test_the_status_field_says_which_half_it_describes(self) -> None:
        """004: on a chain the status is the tightest **inbound** segment's, and a constrained
        exit segment deliberately does not move it. An unqualified label on a record whose
        headline number is the round trip would read as covering both halves."""
        assert "status (way in, tightest segment): open" in self._text().splitlines()[1]

    def test_a_chain_whose_segment_the_regime_excludes_is_refused_naming_it(self) -> None:
        """Every segment, both halves: a regime that excluded one hop of a chain would
        otherwise get a picture with two thirds of it looking perfectly ordinary."""
        narrowed = type(fixture.chain_regime())(id="narrow", route_ids=frozenset({fixture.HOP_ONE}))
        with pytest.raises(ValueError, match=fixture.HOP_TWO):
            render_path(
                fixture.composed_cost(),
                routes=fixture.chain_routes(),
                channels=fixture.fixture_channels(),
                regime=narrowed,
            )


class TestExitByIdentityIsNotAnEdge:
    """**004**: the destination *is* a declared spendable endpoint, so there is no way out.

    The trap is that this result carries a real ``RoundTripCost`` whose figure equals the
    one-way figure. Drawing a zero-cost exit edge would explain that coincidence with a
    falsehood — a journey that costs nothing is a different claim from no journey — and drawing
    nothing at all would leave a reader wondering why the two figures match.

    So the claim goes where it is true: on the **venue**, which is the thing that is spendable,
    and in a note that states the consequence. ``core.routes.path.ExitByIdentity`` exists for
    exactly this distinction one layer down, where ``None`` would have said "no exit chain" and
    an empty chain "a chain that charged nothing".
    """

    @staticmethod
    def _text() -> str:
        return fixture.chain_path_of(fixture.identity_exit_cost()).text

    def test_the_result_under_test_really_exits_by_identity(self) -> None:
        cost = fixture.identity_exit_cost()
        assert isinstance(cost.exit_path, ExitByIdentity)
        assert isinstance(cost.round_trip, RoundTripCost)
        assert cost.round_trip.fraction == cost.one_way.fraction

    def test_no_exit_edge_is_drawn_at_all(self) -> None:
        assert not [entry for entry in segment_edges(self._text()) if entry[0] == "exit"]

    def test_the_destination_venue_carries_the_mark(self) -> None:
        node = next(line for line in self._text().splitlines() if '["venue gamma' in line)
        assert diagram_marks.token(Mark.EXIT_BY_IDENTITY) in node
        assert "a declared spendable endpoint, so nothing has to leave it" in node

    def test_the_note_explains_why_the_two_figures_coincide(self) -> None:
        text = self._text()
        assert "the money is already where it needed to come back out to" in text
        assert "the round-trip figure is the one-way figure" in text
        assert "not a way out that happened to cost nothing" in text

    def test_no_figure_sits_on_the_identity_note(self) -> None:
        """It is a statement about where the money is, and a figure there would be a cost."""
        note = next(
            line
            for line in self._text().splitlines()
            if diagram_marks.token(Mark.EXIT_BY_IDENTITY) in line and line.lstrip().startswith("x")
        )
        assert not FIGURE.search(note)

    def test_the_caption_names_the_way_out_as_needing_none(self) -> None:
        caption = self._text().splitlines()[1]
        assert "way out: none needed" in caption
        assert "the destination is itself a declared spendable endpoint" in caption

    def test_a_round_trip_figure_is_still_drawn_because_the_result_carries_one(self) -> None:
        """Suppressing it would be the opposite error: there *is* a round-trip cost here."""
        cost = fixture.identity_exit_cost()
        assert isinstance(cost.round_trip, RoundTripCost)
        assert f"round-trip cost {numbers.percent(cost.round_trip.fraction)}" in self._text()

    def test_the_four_exit_shapes_render_four_different_captions(self) -> None:
        """``DeclaredExit``, ``ComposedExit``, ``EXIT_BY_IDENTITY`` and none costed."""
        captions = {
            fixture.chain_path_of(fixture.declared_exit_chain_cost()).text.splitlines()[1],
            fixture.chain_path_of(fixture.composed_cost()).text.splitlines()[1],
            self._text().splitlines()[1],
            fixture.drawn_path(
                fixture.exit_unknown_cost(), regime_id="normalized"
            ).text.splitlines()[1],
        }
        ways_out = {
            field
            for caption in captions
            for field in caption.split(SEPARATOR)
            if field.startswith("way out: ")
        }
        assert len(ways_out) == 4, ways_out


class TestTheRoundingTheSegmentAxisMakesVisible:
    """Two rounded parts need not display-sum to a rounded total, and the diagram says so.

    On the §4.3.1 round trip the segments render ``666.67`` and ``555.56`` against a stated
    ``1222.22``: the underlying figures add exactly, and their *renderings* differ by a
    hundredth because each goes through the one rule on its own. That is the rounding
    ``numbers`` admits to, surfacing where a reader is most likely to check the arithmetic by
    adding two lines -- so the note is on the node rather than left to be discovered.
    """

    def test_the_rendered_segments_do_not_add_to_the_rendered_total_here(self) -> None:
        cost = fixture.p2p_cost()
        assert isinstance(cost.round_trip, RoundTripCost)
        parts = [
            entry.components[CostComponent.CONVERSION_SPREAD].amount
            for entry in cost.round_trip.by_segment
        ]
        total = cost.round_trip.components[CostComponent.CONVERSION_SPREAD]
        assert is_close(sum(parts), total.amount), "the underlying figures must add exactly"
        rendered = [
            numbers.amount(entry.components[CostComponent.CONVERSION_SPREAD])
            for entry in cost.round_trip.by_segment
        ]
        as_written = sum(float(value.split()[0]) for value in rendered)
        assert f"{as_written:.2f}" != numbers.amount(total).split()[0], (
            "the fixture no longer exhibits the rounding this note exists to explain"
        )

    def test_the_note_is_on_the_node_a_reader_would_add_up(self) -> None:
        text = fixture.drawn_path(fixture.p2p_cost()).text
        node = next(line for line in text.splitlines() if "round-trip cost by segment" in line)
        assert "each figure rounded on its own" in node
        assert "need not add to the total above" in node

    def test_a_single_segment_gets_no_such_note(self) -> None:
        """One figure cannot fail to add to itself, and a caveat that never applies is noise."""
        text = fixture.drawn_path(fixture.p2p_cost()).text
        node = next(line for line in text.splitlines() if "one-way cost by segment" in line)
        assert "each figure rounded on its own" not in node
