"""SC-006, SC-020 and SC-022, as scans over this feature's own source.

Three rules that are cheap to state and cheap to break, each turned into a check because a
check cannot go stale silently:

* **No feasibility verdict of its own** (FR-006). Every drop in the output is a value 010's
  ``evaluate`` produced. A pre-screen here would be a second opinion about what is infeasible,
  and in this repository the duplicate is where the drift happened every time.
* **No exchange rate, channel rate or currency conversion** (FR-005). Converting one stream's
  amount into another's needs a rate that values one currency in another *for a return*, and
  neither declared rate is one.
* **No branch on a refusal's ``reason`` text** (FR-014a). Which of ``compose``'s three cases
  fired is read from the record; the only use made of the string is carrying it through.

Prose is stripped before searching, using ``tests/source_scan.py``: half the docstrings in this
repository name the thing a scan looks for, and a rule described is not a rule broken.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import get_args

import pytest

from terezy.core.results.tuple import TupleRefused
from tests.source_scan import executable_source, strip_prose

pytestmark = pytest.mark.contract

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "terezy"
MODULES = (
    SOURCE_ROOT / "core" / "decision" / "candidates.py",
    SOURCE_ROOT / "core" / "results" / "candidates.py",
)

REFUSALS = tuple(member.__name__ for member in get_args(TupleRefused))


def _behaviour() -> dict[Path, str]:
    return {path: executable_source(path) for path in MODULES}


def test_the_scan_is_looking_at_something() -> None:
    """The control. A scan over an empty string passes every assertion below."""
    for path, source in _behaviour().items():
        assert "class " in source or "def " in source, path
        assert len(source) > 500, path
    assert len(REFUSALS) == 17


def test_no_module_constructs_or_matches_a_feasibility_verdict_of_its_own() -> None:
    """SC-006. Naming one of 010's refusals here would mean this feature had an opinion about
    which candidates are infeasible, beside the opinion that already exists."""
    offenders = {
        str(path.relative_to(SOURCE_ROOT)): sorted(name for name in REFUSALS if name in source)
        for path, source in _behaviour().items()
        if any(name in source for name in REFUSALS)
    }
    # `DeclarationMissing` is read in the tally to name what a group's members said was absent.
    # That is reporting a value 010 produced, never producing one, so it is the one permitted
    # mention and it is named here rather than excluded by a pattern.
    assert offenders == {"core/decision/candidates.py": ["DeclarationMissing"]}, offenders


def test_no_module_raises_for_a_business_outcome() -> None:
    """Principle IV: every degraded outcome is a typed value. ``raise`` is for a programmer
    error, and this feature has none of its own to report."""
    for path in MODULES:
        tree = ast.parse(strip_prose(path.read_text(encoding="utf-8")))
        raises = [node for node in ast.walk(tree) if isinstance(node, ast.Raise)]
        assert not raises, path


def test_no_module_names_a_rate_a_channel_or_a_conversion() -> None:
    """SC-020. FR-005 forbids converting one stream's amount into another's, and the tempting
    fillers are all named: an exchange rate, a channel's two-sided quote, an official rate."""
    forbidden = (
        "exchange_rate",
        "reference_rate",
        "official_rate",
        "channels",
        "channel",
        "convert",
        "conversion",
        "FxChannel",
        "ChannelSide",
    )
    offenders = {
        str(path.relative_to(SOURCE_ROOT)): sorted(token for token in forbidden if token in source)
        for path, source in _behaviour().items()
        if any(token in source for token in forbidden)
    }
    assert not offenders, offenders


def test_no_module_branches_on_a_refusals_reason_text() -> None:
    """SC-022. The discrimination FR-014 rests on comes from ``CompositionRefused.case``; the
    only thing done with ``reason`` is reading one to build a sentence or carrying it through.

    A comparison, a membership test or a method call on a ``.reason`` is what this forbids --
    an f-string interpolation of one is how compose's words reach the report verbatim.
    """
    for path in MODULES:
        tree = ast.parse(strip_prose(path.read_text(encoding="utf-8")))
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                assert not any(_reads_a_reason(item) for item in [node.left, *node.comparators]), (
                    f"{path} compares a refusal's reason text"
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert not _reads_a_reason(node.func.value), (
                    f"{path} calls a method on a refusal's reason text"
                )


def _reads_a_reason(node: ast.expr) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "reason"


def test_the_reason_text_scan_would_catch_the_thing_it_forbids() -> None:
    """The scan's own control, because an AST walk that matched nothing would pass silently."""
    tree = ast.parse('if refusal.reason == "already arrives":\n    pass\n')
    compares = [node for node in ast.walk(tree) if isinstance(node, ast.Compare)]
    assert compares
    assert any(
        _reads_a_reason(item) for node in compares for item in [node.left, *node.comparators]
    )
