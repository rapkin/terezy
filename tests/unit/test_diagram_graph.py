"""Every declared venue and route, drawn exactly once, connected exactly as declared.

**SC-001** and **FR-002**, plus the edge cases spec.md enumerates -- each of which is a way a
graph could be *wrong while looking right*, which is why they are here rather than left to a
reader's eye:

* two routes between the same pair of venues, which a naive keying by ``(from, to)`` would
  silently collapse into one edge;
* a route from a venue to itself, which "skip degenerate edges" would drop;
* a venue no route touches, which "draw the venues the routes mention" would omit;
* an empty registry, which must render as a diagram *saying* it is empty rather than as blank
  output indistinguishable from a failed render;
* a regime naming a route nobody declared, and a leg naming a venue nobody declared, both of
  which must fail loudly rather than draw a plausible partial picture;
* two records declaring one id, which must fail loudly naming both (FR-018).

SC-001 asks for the check *over the full fixture, not sampled*, so the first class below
reconstructs the whole graph from the rendered text and compares it against the declarations.
"""

from __future__ import annotations

import re
from dataclasses import replace

import pytest

from terezy.api.diagrams import Diagram, Mode, render_graph
from terezy.core.primitives.currency import Currency
from terezy.core.scenarios.regimes import Regime
from tests import diagram_registries as fixture

NODE = re.compile(r'^\s*(n\d+)\["(.*?)"\](?::::\w+)?$', re.MULTILINE)
EDGE = re.compile(r'^\s*(n\d+) -\.?->\|"(.*?)"\| (n\d+|x\d+)$', re.MULTILINE)


def venue_nodes(text: str) -> dict[str, str]:
    """Node id to declared venue id, read back out of the rendered text."""
    found = {}
    for identifier, label in NODE.findall(text):
        fields = label.split(" · ")
        if fields[0].startswith("venue "):
            found[identifier] = fields[0].removeprefix("venue ")
    return found


def drawn_edges(text: str) -> list[tuple[str, str, str]]:
    """``(route id, from venue, to venue)`` for every route edge, in rendered order."""
    nodes = venue_nodes(text)
    edges = []
    for source, label, target in EDGE.findall(text):
        fields = label.split(" · ")
        if not fields[0].startswith("route "):
            continue
        edges.append((fields[0].removeprefix("route "), nodes[source], nodes[target]))
    return edges


class TestTheWholeFixtureIsDrawnExactlyAsDeclared:
    """SC-001, reconstructed from the text rather than sampled out of it."""

    def test_every_declared_venue_is_a_node_exactly_once(self) -> None:
        registry = fixture.six_state_registry()
        nodes = venue_nodes(fixture.graph_of(registry).text)
        assert sorted(nodes.values()) == sorted(registry.venues)
        assert len(set(nodes.values())) == len(nodes), "a venue was drawn twice"

    def test_every_route_the_regime_includes_is_drawn_along_its_legs_in_order(self) -> None:
        registry = fixture.six_state_registry()
        expected = [
            (route.id, leg.from_venue, leg.to_venue)
            for route_id in sorted(registry.regime.route_ids)
            for route in [registry.routes[route_id]]
            for leg in sorted(route.legs, key=lambda item: item.index)
        ]
        assert drawn_edges(fixture.graph_of(registry).text) == expected

    def test_a_venue_no_route_touches_is_still_drawn(self) -> None:
        """A place money can sit with no declared way in or out is a fact worth seeing."""
        text = fixture.graph_of(fixture.six_state_registry()).text
        assert "orphan" in venue_nodes(text).values()
        touched = {venue for _, source, target in drawn_edges(text) for venue in (source, target)}
        assert "orphan" not in touched, "the fixture's isolated venue stopped being isolated"

    def test_the_node_ids_are_positional_and_assigned_in_sorted_order(self) -> None:
        """Determinism (FR-016) with the identity rule (FR-018): sorted, then numbered."""
        registry = fixture.six_state_registry()
        nodes = venue_nodes(fixture.graph_of(registry).text)
        assert nodes == {f"n{index}": v for index, v in enumerate(sorted(registry.venues))}


class TestTheCasesThatLookRightWhileBeingWrong:
    """spec.md's edge cases, each of which a plausible implementation gets wrong."""

    def test_two_routes_between_the_same_pair_are_two_edges_each_named(self) -> None:
        """User Story 1's fifth acceptance scenario."""
        edges = drawn_edges(fixture.graph_of(fixture.six_state_registry()).text)
        alpha_to_beta = [
            route_id for route_id, source, target in edges if (source, target) == ("alpha", "beta")
        ]
        assert sorted(alpha_to_beta) == [fixture.UNVERIFIED_ROUTE, fixture.VERIFIED_ROUTE]

    def test_a_route_from_a_venue_to_itself_is_drawn_as_a_self_edge(self) -> None:
        """A conversion that starts and ends at one venue -- not dropped as degenerate."""
        registry = fixture.six_state_registry()
        loop = fixture.route(
            "r_loop",
            origin="alpha",
            destination="alpha",
            provenance=fixture.source("s_loop", verified=True, fresh=True, synthetic=False),
            kind_of_observation=fixture.SLOW_KIND,
            from_ccy=Currency.UAH,
            to_ccy=Currency.USD,
        )
        routes = {**registry.routes, loop.id: loop}
        extended = fixture.Registry(
            venues=registry.venues,
            routes=routes,
            regime=Regime(id=fixture.REGIME_ID, route_ids=frozenset(routes)),
            kinds=registry.kinds,
        )
        assert ("r_loop", "alpha", "alpha") in drawn_edges(fixture.graph_of(extended).text)

    def test_an_empty_registry_renders_a_diagram_that_says_it_is_empty(self) -> None:
        """Never blank, never an error -- a blank render is indistinguishable from a crash."""
        rendered = render_graph(
            venues={},
            routes={},
            regime=Regime(id="deserted", route_ids=frozenset()),
            mode=Mode.TOPOLOGY,
            kinds=fixture.declared_kinds(),
            as_of=fixture.AS_OF,
        )
        assert isinstance(rendered, Diagram)
        caption = rendered.text.splitlines()[1]
        assert "regime: deserted" in caption
        assert "EMPTY: no venues are declared and this regime includes no routes" in caption

    def test_a_regime_with_no_routes_over_a_populated_registry_says_so(self) -> None:
        registry = fixture.six_state_registry()
        empty_regime = fixture.Registry(
            venues=registry.venues,
            routes=registry.routes,
            regime=Regime(id="believes_nothing", route_ids=frozenset()),
            kinds=registry.kinds,
        )
        text = fixture.graph_of(empty_regime).text
        assert "EMPTY: this regime includes no routes" in text.splitlines()[1]
        assert not drawn_edges(text)
        assert sorted(venue_nodes(text).values()) == sorted(registry.venues)


class TestTheLoudFailures:
    """Every one of these draws a plausible picture if it is allowed to pass quietly."""

    def test_a_regime_naming_an_undeclared_route_fails_naming_it(self) -> None:
        registry = fixture.six_state_registry()
        broken = fixture.Registry(
            venues=registry.venues,
            routes=registry.routes,
            regime=Regime(id=fixture.REGIME_ID, route_ids=frozenset({"no_such_route"})),
            kinds=registry.kinds,
        )
        with pytest.raises(KeyError) as raised:
            fixture.graph_of(broken)
        assert "no_such_route" in str(raised.value)

    def test_a_leg_naming_an_undeclared_venue_fails_naming_it(self) -> None:
        registry = fixture.six_state_registry()
        without_gamma = {k: v for k, v in registry.venues.items() if k != "gamma"}
        broken = fixture.Registry(
            venues=without_gamma,
            routes=registry.routes,
            regime=registry.regime,
            kinds=registry.kinds,
        )
        with pytest.raises(KeyError) as raised:
            fixture.graph_of(broken)
        assert "gamma" in str(raised.value)

    def test_two_venues_declaring_one_id_fail_loudly_naming_both_keys(self) -> None:
        """SC-008's second half. Positional ids cannot merge two entities by *sanitising*;
        two records the declarations say are one still have to be refused, and named."""
        registry = fixture.six_state_registry()
        colliding = {
            **registry.venues,
            "second_key": replace(registry.venues["alpha"], name="a different name"),
        }
        broken = fixture.Registry(
            venues=colliding,
            routes=registry.routes,
            regime=registry.regime,
            kinds=registry.kinds,
        )
        with pytest.raises(ValueError, match="alpha") as raised:
            fixture.graph_of(broken)
        assert "second_key" in str(raised.value)

    def test_a_venue_keyed_under_an_id_it_does_not_declare_fails(self) -> None:
        registry = fixture.six_state_registry()
        misfiled = {k: v for k, v in registry.venues.items() if k != "orphan"}
        misfiled["mistyped"] = registry.venues["orphan"]
        broken = fixture.Registry(
            venues=misfiled,
            routes=registry.routes,
            regime=registry.regime,
            kinds=registry.kinds,
        )
        with pytest.raises(ValueError, match="mistyped"):
            fixture.graph_of(broken)

    def test_a_leg_declaring_an_unknown_observation_kind_fails_rather_than_ages_freely(
        self,
    ) -> None:
        """There is no default staleness threshold, and a diagram may not invent one."""
        registry = fixture.six_state_registry()
        route = registry.routes[fixture.VERIFIED_ROUTE]
        broken_leg = replace(route.legs[0], kind_of_observation="no_such_kind")
        routes = {**registry.routes, route.id: replace(route, legs=(broken_leg,))}
        broken = fixture.Registry(
            venues=registry.venues,
            routes=routes,
            regime=registry.regime,
            kinds=registry.kinds,
        )
        with pytest.raises(KeyError, match="no_such_kind"):
            fixture.graph_of(broken)


class TestTheShippedRegistryDrawsWithoutBeingTouched:
    """FR-002 against the real declarations rather than a fixture built to suit."""

    @pytest.mark.parametrize("regime_id", ["wartime", "normalized"])
    def test_each_declared_regime_renders_its_own_routes(self, regime_id: str) -> None:
        declared = fixture.shipped_declarations()
        regime = fixture.shipped_regime(declared, "war_end", regime_id)
        rendered = render_graph(
            venues=declared.venues,
            routes=declared.routes,
            regime=regime,
            mode=Mode.DECLARED_FIGURES,
            kinds=declared.kinds,
            as_of=fixture.AS_OF,
        )
        assert isinstance(rendered, Diagram)
        edges = drawn_edges(rendered.text)
        assert {route_id for route_id, _, _ in edges} == set(regime.route_ids)
        assert sorted(venue_nodes(rendered.text).values()) == sorted(declared.venues)

    def test_the_two_regimes_draw_different_graphs(self) -> None:
        """If they did not, "one regime per diagram" would be decoration."""
        declared = fixture.shipped_declarations()
        drawn = [
            render_graph(
                venues=declared.venues,
                routes=declared.routes,
                regime=fixture.shipped_regime(declared, "war_end", regime_id),
                mode=Mode.DECLARED_FIGURES,
                kinds=declared.kinds,
                as_of=fixture.AS_OF,
            )
            for regime_id in ("wartime", "normalized")
        ]
        first, second = drawn
        assert isinstance(first, Diagram)
        assert isinstance(second, Diagram)
        assert first.text != second.text
