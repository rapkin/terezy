"""Two diagrams, recorded, so a change to the graph is a diff and not a memory.

**SC-003**, **SC-011**; **FR-016** and **FR-021**.

A checked-in diagram is a *tool* rather than an illustration only if it is byte-identical for
identical inputs. That is what lets an agent change one declaration, regenerate, and read the
diff as the answer to "what did that change?". A diagram whose text churns on every run cannot
sit in ``tests/golden/`` and answers no question anybody has.

**The determinism claims are asserted the three ways they can fail**, on the model of
``tests/golden/test_ramp_comparison.py``:

* **across separate processes** -- a hash seed differs between runs, so anything that iterated
  a ``set`` renders differently in a subprocess while agreeing with itself in one;
* **across input ordering** -- the declaration mappings presented in reverse key order, because
  the ordering must come from the data's own identity and never from load order;
* **confined to what changed** -- one declared field altered, and the diff touches only the
  lines that field affects.

**Regenerating is deliberate**::

    TEREZY_UPDATE_GOLDEN=1 uv run pytest tests/golden/test_diagrams.py
    git diff tests/golden/*.mmd

then read the diff and justify each changed line in the commit message. A **missing** artifact
is a failure, never a silent regeneration: an artifact that reappeared on its own would make a
deleted one indistinguishable from a passing run.

**And it cannot be green-and-wrong.** An artifact recorded from a broken render agrees with
itself forever, so the last class below ties the recorded text back to the declarations and to
the hand-computed figures ``tests/worked_examples/test_ramp_p2p_premium.py`` checks.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest

from terezy.api.diagrams import Diagram, Mode, render_graph, render_path
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.ramp import RoundTripCost
from tests import diagram_registries as fixture

pytestmark = pytest.mark.golden

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
SCRIPT: Final = REPO_ROOT / "scripts" / "render_diagram.py"
UPDATE_VARIABLE: Final = "TEREZY_UPDATE_GOLDEN"

GRAPH_FILE: Final = Path(__file__).with_name("route_graph_wartime.mmd")
PATH_FILE: Final = Path(__file__).with_name("costed_path_p2p.mmd")

SCENARIO: Final = "war_end"
REGIME: Final = "wartime"
GRAPH_MODE: Final = Mode.DECLARED_FIGURES

P2P_ONE_WAY: Final = 3.0 / 45.0
"""§4.3.1's one-way P2P cost by hand: reference 42, buy premium +3, so 3/45 = 6.6667%."""

P2P_ROUND_TRIP: Final = 5.5 / 45.0
"""And the round trip through the declared exit route: 5.5/45 = 12.2222%."""


def _graph_text(*, venues_reversed: bool = False, rename: tuple[str, str] | None = None) -> str:
    declared = fixture.shipped_declarations()
    venues = dict(declared.venues)
    if rename is not None:
        venue_id, name = rename
        venues[venue_id] = replace(venues[venue_id], name=name)
    if venues_reversed:
        venues = dict(reversed(list(venues.items())))
    rendered = render_graph(
        venues=venues,
        routes=dict(reversed(list(declared.routes.items())))
        if venues_reversed
        else declared.routes,
        regime=fixture.shipped_regime(declared, SCENARIO, REGIME),
        mode=GRAPH_MODE,
        kinds=declared.kinds,
        as_of=fixture.AS_OF,
    )
    assert isinstance(rendered, Diagram)
    return rendered.text


def _path_text() -> str:
    declared = fixture.shipped_declarations()
    rendered = render_path(
        fixture.p2p_cost(declared),
        routes=declared.routes,
        regime=fixture.shipped_regime(declared, SCENARIO, REGIME),
    )
    assert isinstance(rendered, Diagram)
    return rendered.text


def _recorded(artifact: Path) -> str:
    if not artifact.is_file():
        raise AssertionError(
            f"{artifact.name} does not exist. A golden artifact is never regenerated "
            f"silently -- produce it deliberately with {UPDATE_VARIABLE}=1 uv run pytest "
            "tests/golden/test_diagrams.py, then read the diff."
        )
    return artifact.read_text(encoding="utf-8")


def _today(artifact: Path, text: str) -> str:
    if os.environ.get(UPDATE_VARIABLE):
        artifact.write_text(text, encoding="utf-8")
    return text


def _script(*arguments: str) -> str:
    """The stdout of ``scripts/render_diagram.py``, run as its own process.

    A subprocess and not an import, for two reasons at once: it is what SC-011 asks about --
    the *script's* bytes -- and it is a fresh interpreter with its own hash seed, which is what
    makes the determinism claim in SC-003 more than "the same call twice in one process".
    """
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


GRAPH_ARGUMENTS: Final = (
    "graph",
    "--regime",
    REGIME,
    "--scenario",
    SCENARIO,
    "--mode",
    "declared-figures",
    "--as-of",
    fixture.AS_OF.isoformat(),
)

PATH_ARGUMENTS: Final = (
    "path",
    "--regime",
    REGIME,
    "--scenario",
    SCENARIO,
    "--route",
    fixture.P2P_ROUTE,
    "--stream",
    fixture.UAH_STREAM,
    "--destination",
    "binance",
    "--amount",
    repr(fixture.AMOUNT),
    "--as-of",
    fixture.AS_OF.isoformat(),
)


class TestTheRecordedDiagramsAreStillTheDiagrams:
    """SC-011: both artifacts checked in, and the suite fails on any byte of drift."""

    def test_the_route_graph_matches_the_checked_in_artifact(self) -> None:
        assert _today(GRAPH_FILE, _graph_text()) == _recorded(GRAPH_FILE)

    def test_the_costed_path_matches_the_checked_in_artifact(self) -> None:
        assert _today(PATH_FILE, _path_text()) == _recorded(PATH_FILE)

    def test_neither_artifact_carries_a_line_ending_in_whitespace(self) -> None:
        """An editor stripping trailing space must not produce a failure about a route."""
        for artifact in (GRAPH_FILE, PATH_FILE):
            text = _recorded(artifact)
            assert all(line == line.rstrip() for line in text.splitlines())
            assert text.endswith("\n")

    def test_both_artifacts_are_mermaid_flowcharts_and_nothing_else(self) -> None:
        """Every line is one of the four shapes this package emits (research.md D10)."""
        for artifact in (GRAPH_FILE, PATH_FILE):
            lines = _recorded(artifact).splitlines()
            assert lines[0] == "flowchart LR"
            for line in lines[1:]:
                assert line.startswith("    "), line
                assert line.lstrip().startswith("classDef ") or '["' in line or '|"' in line, line


class TestTheScriptPrintsWhatTheSuiteRegenerates:
    """SC-011's second half, and FR-021's whole delivery surface in one assertion."""

    def test_the_script_reproduces_the_route_graph_artifact_byte_for_byte(self) -> None:
        assert _script(*GRAPH_ARGUMENTS) == _recorded(GRAPH_FILE)

    def test_the_script_reproduces_the_costed_path_artifact_byte_for_byte(self) -> None:
        assert _script(*PATH_ARGUMENTS) == _recorded(PATH_FILE)

    def test_the_script_refuses_rather_than_printing_an_empty_diagram(self) -> None:
        """A refusal on stderr and a non-zero status, so no pipeline captures a blank."""
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "path",
                "--regime",
                "normalized",
                "--scenario",
                SCENARIO,
                "--route",
                fixture.P2P_ROUTE,
                "--stream",
                fixture.USD_STREAM,
                "--destination",
                "binance",
                "--amount",
                "10.0",
                "--currency",
                "USD",
                "--as-of",
                fixture.AS_OF.isoformat(),
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
        )
        assert completed.returncode != 0
        assert completed.stdout == "", "a refusal printed something to stdout"
        assert "NOTHING TO DRAW" in completed.stderr


class TestDeterminism:
    """SC-003, the three ways it fails."""

    def test_the_same_declarations_render_identically_in_a_separate_process(self) -> None:
        """A fresh interpreter has a fresh hash seed, so an iterated ``set`` shows up here."""
        assert _script(*GRAPH_ARGUMENTS) == _script(*GRAPH_ARGUMENTS)
        assert _script(*GRAPH_ARGUMENTS) == _graph_text()

    def test_declarations_presented_in_a_different_order_render_identically(self) -> None:
        """Ordering comes from the data's own identity, never from load order."""
        assert _graph_text(venues_reversed=True) == _graph_text()

    def test_changing_one_declared_field_confines_the_diff_to_what_it_affects(self) -> None:
        """A diff on a golden diagram means the graph actually changed."""
        before = _graph_text().splitlines()
        after = _graph_text(rename=("binance", "A DIFFERENT NAME")).splitlines()
        assert len(before) == len(after)
        differing = [index for index, line in enumerate(before) if line != after[index]]
        assert len(differing) == 1, [before[index] for index in differing]
        assert "venue binance" in after[differing[0]]
        assert "A DIFFERENT NAME" in after[differing[0]]

    def test_the_two_modes_are_each_stable_and_are_not_each_other(self) -> None:
        assert _script(*GRAPH_ARGUMENTS) != _script(
            *(
                argument if argument != "declared-figures" else "topology"
                for argument in GRAPH_ARGUMENTS
            )
        )


class TestTheArtifactsCannotBeGreenAndWrong:
    """An artifact recorded from a broken render agrees with itself forever."""

    def test_the_recorded_graph_holds_every_route_the_regime_declares(self) -> None:
        declared = fixture.shipped_declarations()
        regime = fixture.shipped_regime(declared, SCENARIO, REGIME)
        text = _recorded(GRAPH_FILE)
        for route_id in sorted(regime.route_ids):
            assert f"route {route_id} " in text
        for excluded in sorted(set(declared.routes) - regime.route_ids):
            assert f"route {excluded} " not in text

    def test_the_recorded_graph_holds_every_declared_venue(self) -> None:
        for venue_id in sorted(fixture.shipped_declarations().venues):
            assert f'["venue {venue_id} · ' in _recorded(GRAPH_FILE)

    def test_the_recorded_path_shows_the_hand_computed_p2p_figures(self) -> None:
        """The arithmetic METHODOLOGY §16.2 shows and the worked example checks.

        Restated here so the artifact cannot agree with a broken run: reference 42, buy
        premium +3 gives a price of 45, so one way is 3/45 and the round trip through the
        declared exit route is 5.5/45.
        """
        cost = fixture.p2p_cost()
        assert isinstance(cost.round_trip, RoundTripCost)
        assert is_close(cost.one_way.fraction, P2P_ONE_WAY)
        assert is_close(cost.round_trip.fraction, P2P_ROUND_TRIP)
        text = _recorded(PATH_FILE)
        assert "one-way cost 6.67% of 10000.00 UAH sent" in text
        assert "round-trip cost 12.22% of 10000.00 UAH sent" in text

    def test_the_recorded_path_keeps_the_rate_space_spread_apart_from_the_cost(self) -> None:
        """§4.3.1's ``p/r`` is 7.14% and the cost is 6.67%. Both appear; neither is the other."""
        text = _recorded(PATH_FILE)
        assert "spread over reference (one-way): 7.14% via p2p" in text
        assert "this is NOT the cost" in text
        assert "one-way cost 7.14%" not in text

    def test_the_recorded_diagrams_say_they_are_built_on_synthetic_data(self) -> None:
        """§11 item 1: none of these figures has been observed, and both pictures say so."""
        for artifact in (GRAPH_FILE, PATH_FILE):
            assert "SYNTHETIC" in _recorded(artifact).splitlines()[1]

    def test_the_recorded_graph_names_its_regime_and_its_mode(self) -> None:
        caption = _recorded(GRAPH_FILE).splitlines()[1]
        assert f"regime: {REGIME}" in caption
        assert f"mode: {GRAPH_MODE.value}" in caption
