"""SC-011: this feature makes no claim about which assumption decides between two members.

019 FR-021. It is `docs/DIRECTION.md`'s own phrase and the temptation is strong, so the boundary
is checked rather than remembered: naming the assumptions the members **do not share** is a read
over records that already exist, and naming the one that **decides** requires re-evaluating the
set under a changed assumption -- required test I5, and a per-assumption perturbation policy
nobody has declared. Writing the second sentence while computing only the first is the shape of
defect this repository keeps finding: a claim whose warrant is somewhere else.

**A scan, because the criterion is an absence**, and no value can be read for one: no record
carries a deciding-assumption field, and no string this feature produces asserts one.
"""

from __future__ import annotations

import ast
import re

import pytest

from tests.data_roots import REPO_ROOT
from tests.source_scan import executable_source

pytestmark = pytest.mark.contract

MODULES = ("core/decision/dominance.py", "core/results/dominance.py")
"""This feature's own two modules. The declaration module carries no verdict at all and the
answer records are 015's, so a claim about a deciding belief could only be written here."""

DECIDING = re.compile(r"decid|because_of|due_to|explains|driven_by|the_reason", re.IGNORECASE)
"""The words an author reaches for when attributing a set's shape to one belief.

Deliberately over-broad: a field named ``decided_by`` and a string saying *this assumption
decides* are the same claim, and a pattern narrow enough to admit one would admit the other.
"""


def _fields() -> list[str]:
    """Every field name this feature's records declare."""
    names = []
    for module in MODULES:
        tree = ast.parse((REPO_ROOT / "src" / "terezy" / module).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.append(node.target.id)
    return names


def _literals() -> list[str]:
    """Every string literal the behaviour holds, prose stripped."""
    found = []
    for module in MODULES:
        tree = ast.parse(executable_source(REPO_ROOT / "src" / "terezy" / module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                found.append(node.value)
    return found


def test_no_record_carries_a_deciding_assumption_field() -> None:
    offenders = [name for name in _fields() if DECIDING.search(name)]
    assert not offenders, (
        "a record names an assumption as deciding between two members, which needs a "
        f"re-evaluation this feature does not perform (FR-021): {sorted(offenders)}"
    )
    assert _fields(), "the scan found no fields at all, so it proves nothing"


def test_no_string_this_feature_produces_asserts_one() -> None:
    offenders = [text for text in _literals() if DECIDING.search(text)]
    assert not offenders, (
        f"a string asserts which belief decided a verdict (FR-021): {sorted(offenders)}"
    )
