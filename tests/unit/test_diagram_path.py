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

from terezy.api.diagrams import Diagram, numbers, render_path
from terezy.core.results.ramp import CostComponent, RoundTripCost
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


def leg_edges(text: str) -> list[tuple[str, str, str, str]]:
    """``(direction, route id, from venue, to venue)`` for every leg edge, in drawn order."""
    nodes = venue_nodes(text)
    found = []
    for source, label, target in EDGE.findall(text):
        fields = label.split(SEPARATOR)
        if len(fields) < 2 or not fields[1].startswith("route "):
            continue
        found.append((fields[0], fields[1].removeprefix("route "), nodes[source], nodes[target]))
    return found


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
            f"route: {fixture.P2P_ROUTE}",
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
            *(numbers.percent(value) for value in cost.one_way.spreads_over_reference),
            *(numbers.percent(value) for value in cost.round_trip.spreads_over_reference),
            *(
                f"{numbers.percent(leg.fee_pct)}"
                for route_id in (fixture.P2P_ROUTE, cost.path.route_id)
                for leg in fixture.shipped_declarations().routes[route_id].legs
            ),
        }
        if cost.ceiling is not None:
            permitted.add(numbers.amount(cost.ceiling))
        rendered = {found.group(0) for found in FIGURE.finditer(fixture.drawn_path(cost).text)}
        unexplained = {
            value for value in rendered if not any(value in allowed for allowed in permitted)
        }
        assert not unexplained, f"the diagram carries figures the result does not: {unexplained}"

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
            figures = [field for field in fields if FIGURE.search(field)]
            assert all(field.startswith("declared fee ") for field in figures), (
                f"an edge from {source} to {target} carries a figure that is not a declared "
                f"leg fee: {figures}"
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


class TestTheRoundTripCannotBeDrawnWithoutADeclaredExit:
    """FR-010 has no fallback, and the absence of one is asserted rather than assumed.

    A ``RoundTripCost`` means an exit route was costed, and the inbound route's
    ``partner_route`` names which. If the two disagree there is no honest picture to draw:
    reversing the inbound chain is the one thing FR-010 forbids outright, because the way out
    has its own legs and its own side of every spread. So it raises, naming the route.
    """

    def test_a_round_trip_whose_route_declares_no_partner_is_refused(self) -> None:
        declared = fixture.shipped_declarations()
        cost = fixture.p2p_cost(declared)
        inbound = declared.routes[fixture.P2P_ROUTE]
        routes = {**declared.routes, inbound.id: replace(inbound, partner_route=None)}
        with pytest.raises(ValueError, match=fixture.P2P_ROUTE):
            render_path(
                cost,
                routes=routes,
                regime=fixture.shipped_regime(declared, "war_end", "wartime"),
            )
