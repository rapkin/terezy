"""SC-007: the project tolerance and the declared band are used only where each belongs.

019 FR-012. The project tolerance is the width of float64 rounding and is defined in exactly one
place (Principle IV); an indifference band is a statement about what the **inputs** support.
Conflating them would put a modelling judgement inside the constant that exists so hand
arithmetic and machine arithmetic can agree -- and the reverse, loosening the tolerance to
implement a band, is the same defect wearing the other hat.

**A scan, because the criterion is *which call sites exist***, which no run observes: an
implementation that read the band where the tolerance belongs would still produce a set, and the
set would be wrong in a way only the source shows.

Stated as a site map rather than as a blanket ban on importing the tolerance, which an earlier
draft of the specification said and which FR-007 makes impossible to satisfy: the weak half **is**
the project comparison.
"""

from __future__ import annotations

import ast
from typing import Final

import pytest

from tests import data_roots
from tests.source_scan import executable_source

pytestmark = pytest.mark.contract

SOURCE_ROOT: Final = data_roots.REPO_ROOT / "src" / "terezy"
PASS: Final = SOURCE_ROOT / "core" / "decision" / "dominance.py"
RECORDS: Final = (
    SOURCE_ROOT / "core" / "results" / "dominance.py",
    SOURCE_ROOT / "core" / "results" / "objectives.py",
)

IS_CLOSE: Final = "is_close"
SLACK: Final = "slack"


def _calls(name: str) -> list[str]:
    """Every function the pass calls ``name`` from, so a second site names itself."""
    tree = ast.parse(executable_source(PASS))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == name
            ):
                found.append(node.name)
    return sorted(found)


def test_the_scan_is_looking_at_something() -> None:
    """The control: a scan over a source that calls neither passes both assertions below."""
    source = executable_source(PASS)
    assert IS_CLOSE in source
    assert SLACK in source


def test_the_project_comparison_is_read_in_the_weak_half_and_nowhere_else() -> None:
    """FR-007's weak half is the one site. ``_decide`` is what ``relates`` reads a position
    through, and it is the only function that asks whether two figures are the same figure."""
    assert _calls(IS_CLOSE) == ["_decide"]


def test_its_width_is_read_in_the_floor_check_and_nowhere_else() -> None:
    """FR-011c's floor is the other. A band is measured against the width the comparison
    actually allows on the figures in hand, which is why the check cannot live at load."""
    assert _calls(SLACK) == ["_below_the_floor"]


def test_no_record_module_reaches_for_a_closeness_rule_at_all() -> None:
    """A record carries data. A comparison written into one would be a second definition of the
    relation, in a module nothing calls to compare anything."""
    for path in RECORDS:
        source = executable_source(path)
        assert IS_CLOSE not in source, path
        assert "tolerance" not in source, path


def test_the_declared_band_is_never_read_where_the_tolerance_belongs() -> None:
    """The other direction. ``_decide`` reads two figures and no width at all -- it takes none --
    so the band structurally cannot reach the weak half, and this says so of the signature."""
    tree = ast.parse(executable_source(PASS))
    decide = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_decide"
    )
    taken = [argument.arg for argument in decide.args.args + decide.args.kwonlyargs]
    assert taken == ["left", "right"]


def test_010s_tie_groups_are_never_recomputed_here() -> None:
    """FR-013: 010's ties are read off the comparison record this feature carries through.

    A second implementation of *what counts as a tie* would report a strict winner in one
    comparison and a tie in the other, over the same two numbers -- which is the defect
    ``tolerance.tied_groups`` exists in one place to prevent.
    """
    assert "tied_groups" not in executable_source(PASS)
