"""Two modes, named on the diagram, and a computed cost on neither.

**SC-012** and **SC-009**; **FR-006** and **FR-019**.

The owner asked for two selectable modes rather than one: a pure topology, and the same
picture carrying the *declared* per-leg figures. The trap in that decision is the numberless
picture, which reads as "zero fees" unless the diagram says which mode it is -- the same class
of error as an unlabelled one-way figure, and the reason FR-006 puts the mode on the face of
the diagram rather than only in the caller's head.

**The second trap is the one this module spends most of its assertions on.** A *computed* ramp
cost exists only per ``(destination x stream x route)``, which a registry graph does not name.
Putting one on a registry graph would be feature 002's FR-008 violated in picture form -- and
it is forbidden in the with-figures mode too, not only in the topology one, because the
with-figures mode is where it would look like it belonged.

**A figure is recognised by the shape the one rule gives it.** Every number this package puts
on a diagram comes out of ``terezy.api.diagrams.numbers`` as a fixed two-decimal value
(FR-022), so ``\\d+\\.\\d\\d`` finds every figure and nothing else: a leg index, a positional
node id, a channel id like ``p2p`` and an ISO date are none of them figures and none of them
match. That is what makes "verified over every label, not sampled" a claim this module can
actually make.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from terezy.api.diagrams import Diagram, Mode, graph, render_graph
from tests import diagram_registries as fixture
from tests import source_scan

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
GRAPH_MODULE = REPO_ROOT / "src" / "terezy" / "api" / "diagrams" / "graph.py"

SEPARATOR = " · "
FIGURE = re.compile(r"\d+\.\d\d")
"""What the one number rule produces, and the only shape a figure can have (FR-022)."""

FIGURE_FIELD = re.compile(
    re.escape(SEPARATOR + graph.FIGURE_FIELD) + r'[^·"]*?(?=' + re.escape(SEPARATOR) + r'|")'
)
"""One declared-figure field, its separator included, as it appears inside a label."""


def body(text: str) -> list[str]:
    """Everything below the header and the caption.

    The caption is excluded on purpose: FR-006 *requires* it to differ between modes, because
    naming the mode on the face of the diagram is the whole point. What must not differ is
    anything else.
    """
    return text.splitlines()[2:]


def caption(text: str) -> str:
    return text.splitlines()[1]


def edge_labels(text: str) -> list[str]:
    return [found.group(1) for found in re.finditer(r'\|"(.*?)"\|', text)]


def node_labels(text: str) -> list[str]:
    return [found.group(1) for found in re.finditer(r'^\s*\w+\["(.*?)"\]', text, re.MULTILINE)]


def figure_bearing_fields(text: str) -> list[str]:
    """Every label field anywhere in the diagram that carries a rendered figure."""
    return [
        field
        for label in [*edge_labels(text), *node_labels(text)]
        for field in label.split(SEPARATOR)
        if FIGURE.search(field)
    ]


class TestTheTwoModesDifferByFiguresAndNothingElse:
    """SC-012's central claim, asserted as an equality rather than as a resemblance."""

    def test_stripping_the_figures_reproduces_the_topology_diagram_exactly(self) -> None:
        topology = fixture.six_state_graph(Mode.TOPOLOGY).text
        with_figures = fixture.six_state_graph(Mode.DECLARED_FIGURES).text
        assert body(FIGURE_FIELD.sub("", with_figures)) == body(topology)

    def test_the_captions_differ_only_in_the_mode_they_name(self) -> None:
        without_mode = [
            SEPARATOR.join(
                field
                for field in caption(fixture.six_state_graph(mode).text).split(SEPARATOR)
                if not field.startswith("mode: ")
            )
            for mode in Mode
        ]
        assert without_mode[0] == without_mode[1]

    def test_the_two_modes_are_actually_different(self) -> None:
        """If they were equal, the assertions above would hold for the wrong reason."""
        assert fixture.six_state_graph(Mode.TOPOLOGY).text != (
            fixture.six_state_graph(Mode.DECLARED_FIGURES).text
        )

    def test_the_topology_diagram_carries_no_figure_at_all(self) -> None:
        """Over every label, not sampled -- the criterion says so in as many words."""
        found = figure_bearing_fields(fixture.six_state_graph(Mode.TOPOLOGY).text)
        assert not found, f"a topology diagram carries figures: {found}"

    def test_the_with_figures_diagram_carries_declared_fees_with_their_provenance_state(
        self,
    ) -> None:
        labels = fixture.labels_by_route(fixture.six_state_graph(Mode.DECLARED_FIGURES).text)
        priced = labels[fixture.VERIFIED_ROUTE]
        assert f"{graph.FIGURE_FIELD}1.50% + 12.50 UAH" in priced
        assert "marks: " in priced, "a figure without its provenance state is half a figure"


class TestNoComputedRampCostReachesARegistryGraph:
    """FR-006's prohibition, in the mode where it would look like it belonged."""

    def test_every_figure_on_the_graph_is_a_declared_leg_fee(self) -> None:
        """A computed ramp cost would have to appear as a figure, and every figure is a fee.

        Checked over every label in both modes. A cost is per
        ``(destination x stream x route)``; a registry graph names no such triple, so a
        number here could only be a figure keyed by nothing.
        """
        for mode in Mode:
            for field in figure_bearing_fields(fixture.six_state_graph(mode).text):
                assert field.startswith(graph.FIGURE_FIELD), (
                    f"{mode.value} carries a figure that is not a declared leg fee: {field!r}"
                )

    def test_the_registry_renderer_cannot_cost_anything(self) -> None:
        """It imports no costing function, so there is nothing for a figure to come from.

        Prose is stripped first: this module's own docstring names ``cost`` repeatedly, and
        so does the renderer's, which explains at length why no cost may appear.
        """
        behaviour = source_scan.executable_source(GRAPH_MODULE)
        for costing in ("routes.cost", "routes.ranking", "cost_one", "rank(", "results.ramp"):
            assert costing not in behaviour, f"the registry renderer reaches for {costing}"

    def test_the_registry_renderer_does_not_read_the_coverage_audit(self) -> None:
        """research.md D6: the *no exit declared* mark is computed from the declarations.

        Reading feature 003's report would make a picture depend on an audit, couple two
        features that landed separately, and put an advisory verdict on a diagram that 003
        says must drive nothing.
        """
        assert "coverage" not in source_scan.executable_source(GRAPH_MODULE)

    def test_the_scan_would_notice_the_import_it_forbids(self) -> None:
        """A scan that cannot fail protects nothing."""
        planted = "from terezy.core.routes import coverage\n\n\nX: int = 1\n"
        assert "coverage" in source_scan.strip_prose(planted)


class TestEveryDiagramNamesExactlyOneRegime:
    """SC-009 and FR-019: a merged graph existing under no regime is not producible."""

    @pytest.mark.parametrize("mode", list(Mode))
    def test_the_regime_is_named_on_the_diagram_itself(self, mode: Mode) -> None:
        rendered = fixture.six_state_graph(mode)
        assert isinstance(rendered, Diagram)
        assert f"regime: {fixture.REGIME_ID}" in caption(rendered.text)
        assert rendered.regime_id == fixture.REGIME_ID

    @pytest.mark.parametrize("mode", list(Mode))
    def test_the_mode_is_named_on_the_diagram_itself(self, mode: Mode) -> None:
        assert f"mode: {mode.value}" in caption(fixture.six_state_graph(mode).text)

    def test_a_numberless_diagram_says_why_it_has_no_numbers(self) -> None:
        """ "No figures shown" is a different claim from "the fees are zero"."""
        assert "an absent number is not a zero" in caption(
            fixture.six_state_graph(Mode.TOPOLOGY).text
        )

    def test_no_argument_list_expresses_a_graph_of_every_route_at_once(self) -> None:
        """The strongest reading of "must not be producible" is a required parameter.

        A runtime check can be bypassed by the next caller who has a reason; a parameter with
        no default, no sentinel and no overload cannot be.
        """
        regime = inspect.signature(render_graph).parameters["regime"]
        assert regime.default is inspect.Parameter.empty
        assert regime.kind is inspect.Parameter.KEYWORD_ONLY

    def test_only_the_regimes_routes_are_drawn(self) -> None:
        """A route the regime excludes exists as a declaration and not under this belief."""
        registry = fixture.six_state_registry()
        narrowed = fixture.Registry(
            venues=registry.venues,
            routes=registry.routes,
            regime=type(registry.regime)(
                id="narrow", route_ids=frozenset({fixture.VERIFIED_ROUTE})
            ),
            kinds=registry.kinds,
        )
        labels = fixture.labels_by_route(fixture.graph_of(narrowed).text)
        assert set(labels) == {fixture.VERIFIED_ROUTE}


class TestDeterminismHoldsPerMode:
    """FR-016 applies *per mode*: same declarations and same mode, same bytes."""

    @pytest.mark.parametrize("mode", list(Mode))
    def test_two_renders_of_the_same_registry_agree_byte_for_byte(self, mode: Mode) -> None:
        assert fixture.six_state_graph(mode).text == fixture.six_state_graph(mode).text

    @pytest.mark.parametrize("mode", list(Mode))
    def test_the_mode_record_travels_with_the_text(self, mode: Mode) -> None:
        rendered = fixture.six_state_graph(mode)
        assert isinstance(rendered, Diagram)
        assert rendered.mode is mode
        assert rendered.kind == "route_graph"
