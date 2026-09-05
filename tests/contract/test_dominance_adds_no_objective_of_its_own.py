"""SC-005: no feasibility rule in the pass, and no weight in any declared objective.

019 FR-005, FR-010, on 014 SC-006's technique. Both halves are **absences**, which no value can
be read for, so both are scans:

* naming one of 010's refusals here would mean this feature had an opinion about which
  candidates are infeasible, beside the opinion that already exists -- and a pre-screen, a cheap
  filter or an early exit is exactly how a comparison comes to recommend the only option left
  standing;
* a weighted sum of two objectives is a non-standard composite driving the primary user-visible
  ordering, which required test **B12** forbids, and a partial order is what makes this step
  need no calibration at all.

Prose is stripped before searching (``tests/source_scan.py``): this feature's own docstrings
name feasibility, weights and priorities at length, and a rule described is not a rule broken.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path
from typing import Final, get_args

import pytest

from terezy.core.results.tuple import TupleRefused
from tests import data_roots
from tests.source_scan import executable_source

pytestmark = pytest.mark.contract

SOURCE_ROOT: Final = data_roots.REPO_ROOT / "src" / "terezy"
MODULES: Final = (
    SOURCE_ROOT / "core" / "decision" / "dominance.py",
    SOURCE_ROOT / "core" / "results" / "dominance.py",
    SOURCE_ROOT / "core" / "results" / "objectives.py",
)

REFUSALS: Final = tuple(member.__name__ for member in get_args(TupleRefused))

SCORING: Final = ("weight", "score", "coefficient", "priority", "rank_by", "utility")
"""The keys a well-meaning author reaches for when trading one criterion against another. Each
would turn a partial order into a total one, which is the point at which a calibration nobody
declared decides the answer."""


def _behaviour() -> dict[Path, str]:
    return {path: executable_source(path) for path in MODULES}


def test_the_scan_is_looking_at_something() -> None:
    """The control. A scan over an empty string passes every assertion below."""
    for path, source in _behaviour().items():
        assert "class " in source or "def " in source, path
        assert len(source) > 500, path
    assert len(REFUSALS) == 17


def test_no_module_constructs_or_matches_a_feasibility_verdict_of_its_own() -> None:
    """FR-010. A candidate is infeasible only for a member of 010's ``TupleRefused`` union, and
    this feature must not contain a reason of its own to consider one unavailable."""
    offenders = {
        str(path.relative_to(SOURCE_ROOT)): sorted(name for name in REFUSALS if name in source)
        for path, source in _behaviour().items()
        if any(name in source for name in REFUSALS)
    }
    assert not offenders, offenders


def test_no_record_or_function_here_declares_a_weight() -> None:
    """FR-005, read off the source rather than off one declaration file: a set that could carry
    a weight would carry one the day somebody wanted a tie broken."""
    offenders = {
        str(path.relative_to(SOURCE_ROOT)): sorted(name for name in SCORING if name in source)
        for path, source in _behaviour().items()
        if any(name in source for name in SCORING)
    }
    assert not offenders, offenders


def test_no_declared_objective_set_carries_a_weight_either() -> None:
    """The value half, over every objective set on disk -- shipped and fixture alike.

    The schema forbids an unknown field, so this cannot fail while the schema holds; it is the
    check that says so of the **files**, which is where a reader looks for the owner's policy.
    """
    files = sorted((data_roots.SHIPPED / "objectives").glob("*.toml")) + sorted(
        (data_roots.FIXTURES / "objectives").glob("*.toml")
    )
    assert files, "no objective set was found, so this asserts nothing"
    for path in files:
        declared = tomllib.loads(path.read_text(encoding="utf-8"))
        for objective in declared["objective_set"]["objective"]:
            assert set(objective) == {"criterion", "direction", "band"}, path


def test_the_pass_raises_only_where_a_caller_built_a_record_against_itself() -> None:
    """Principle IV's split: ``raise`` for a violated invariant or a programmer error, a typed
    value for every business outcome. Each raise is reachable only from a hand-built record or
    from a band the pass has already refused, and they are pinned so a sixth is argued for."""
    raised = {
        str(path.relative_to(SOURCE_ROOT)): [
            node
            for node in ast.walk(ast.parse(executable_source(path)))
            if isinstance(node, ast.Raise)
        ]
        for path in MODULES
    }
    assert raised["core/results/dominance.py"] == [], "a record must never raise"
    assert raised["core/results/objectives.py"] == []
    kinds = sorted(
        ast.unparse(node.exc.func)  # type: ignore[union-attr]
        for node in raised["core/decision/dominance.py"]
    )
    assert kinds == ["AssertionError"] * 4 + ["TypeError"] * 2
