"""FR-008 made structural: the subtraction approximation is **absent**, not discouraged.

*"Deflation MUST use the exact compounding relation between the nominal rate, the inflation
rate and the real rate (the Fisher relation), never the subtraction approximation, because
at Ukrainian inflation magnitudes the approximation error is itself material."*

``tests/worked_examples/test_deflation_arithmetic.py`` proves the two answers differ by
twenty-eight percentage points at the magnitudes this project deals in. That is the argument.
This file is the enforcement: a scan over the executable source of every module in the
deflation path, asserting that nothing in it subtracts an inflation term from anything.

**Why a source scan and not only the arithmetic tests.** A worked example proves that the
function it calls is exact. It says nothing about a *second* path someone adds later -- a
convenience helper, a "quick" estimate for a summary line, a comparison written inline. The
approximation is the thing a reader will reach for unless stopped, because it is the version
they were taught. Making it unrepresentable in these modules is what stops it, and this scan
is what makes "unrepresentable" checkable.

**Prose is stripped first.** Half the docstrings in the deflation path spell out the
approximation in order to forbid it -- this one included, twice. ``tests.source_scan``
removes comments and docstrings and leaves behaviour, on the precedent of the diagram
suites, so describing a rule is not a violation of it.

**Two rules, and the second is the load-bearing one.**

* *Named*: no subtraction whose right-hand side mentions an inflation-bearing identifier.
  This catches the approximation written out in full and names it.
* *Structural*: in these modules **every** subtraction has a numeric literal on its right.
  Deliberately stricter than the requirement, because a scan that only knew the names it was
  told about would miss ``real = n - i`` and every other abbreviation. The legitimate
  subtractions in this path are all of the form "minus one" -- turning a growth factor into a
  rate -- and a subtraction that is not is a subtraction a reviewer should be made to look at.

Both rules are proved falsifiable below against fixture sources, because a scan that cannot
fail is a scan that proves nothing.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.source_scan import strip_prose

pytestmark = pytest.mark.contract

SRC = Path(__file__).resolve().parents[2] / "src" / "terezy"

SCANNED = (
    *sorted((SRC / "core" / "inflation").glob("*.py")),
    SRC / "core" / "results" / "hurdle.py",
    SRC / "core" / "primitives" / "rates.py",
)
"""Every module the deflation path runs through.

Globbed rather than listed for ``core/inflation``, so a module added to that package is
scanned the day it appears rather than the day somebody remembers to add it here. That is the
same fail-closed reading ``check_provenance.unknown_directories`` uses on ``data/``.
"""

INFLATION_TERMS = ("inflation", "cpi", "deflat", "cumulative", "price_index", "annual_rate")
"""Identifier fragments that name an inflation quantity, matched case-insensitively.

Not an exhaustive vocabulary and not required to be: the structural rule below catches an
abbreviation this list has never heard of. This list exists so that the *common* mistake
fails with a message naming the requirement rather than with a generic one.
"""


def _subtractions(source: str) -> Iterator[ast.BinOp]:
    """Every binary subtraction in a module's behaviour, docstrings already removed."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
            yield node


def _is_numeric_literal(node: ast.expr) -> bool:
    """Whether an operand is a plain number -- the ``- 1.0`` that turns a factor into a rate."""
    return isinstance(node, ast.Constant) and isinstance(node.value, int | float)


def _mentions_inflation(node: ast.expr) -> bool:
    """Whether an operand's source text names an inflation quantity."""
    rendered = ast.unparse(node).lower()
    return any(term in rendered for term in INFLATION_TERMS)


def _named_violations(source: str) -> list[str]:
    """Subtractions of a named inflation quantity: the approximation, written out."""
    return [
        ast.unparse(node)
        for node in _subtractions(source)
        if _mentions_inflation(node.right) and not _is_numeric_literal(node.right)
    ]


def _structural_violations(source: str) -> list[str]:
    """Subtractions of anything that is not a plain number."""
    return [
        ast.unparse(node) for node in _subtractions(source) if not _is_numeric_literal(node.right)
    ]


@pytest.mark.parametrize("path", SCANNED, ids=lambda path: path.name)
def test_no_module_subtracts_an_inflation_rate_from_anything(path: Path) -> None:
    """FR-008's prohibition, applied by name."""
    found = _named_violations(strip_prose(path.read_text(encoding="utf-8")))

    assert not found, (
        f"{path.name} subtracts a named inflation quantity: {found}. FR-008 forbids the "
        "approximation `real = nominal - inflation`: at 80% inflation it is 28 percentage "
        "points wrong, which is larger than most of the differences this tool exists to "
        "detect. Use the exact Fisher relation, `(1 + nominal) / (1 + inflation) - 1`, which "
        "is `core.inflation.deflate.deflate` and exists exactly once."
    )


@pytest.mark.parametrize("path", SCANNED, ids=lambda path: path.name)
def test_every_subtraction_in_the_deflation_path_subtracts_a_plain_number(path: Path) -> None:
    """The structural rule: the only legitimate subtraction here is "minus one".

    Stricter than FR-008 asks, and deliberately so -- see this module's docstring. If a
    genuinely new kind of subtraction is ever needed in these modules, this test is the place
    the reviewer is made to look at it, and widening it is a visible act.
    """
    found = _structural_violations(strip_prose(path.read_text(encoding="utf-8")))

    assert not found, (
        f"{path.name} contains a subtraction whose right-hand side is not a plain number: "
        f"{found}. Every legitimate subtraction in the deflation path turns a growth factor "
        "into a rate by taking one off it. Anything else is either the forbidden Fisher "
        "approximation or something a reviewer should look at deliberately."
    )


def test_the_exact_relation_exists_and_is_a_division() -> None:
    """The other half: forbidding the approximation is worthless if nothing does it right."""
    behaviour = strip_prose((SRC / "core" / "inflation" / "deflate.py").read_text(encoding="utf-8"))

    assert "(1.0 + nominal) / (1.0 + inflation) - 1.0" in behaviour, (
        "core.inflation.deflate no longer contains the exact Fisher relation in the form the "
        "contract states it. It is the one place in the project that turns a nominal rate "
        "into a real one, and the form is pinned so that a rewrite has to be deliberate."
    )


def test_the_named_scan_is_falsifiable() -> None:
    """A scan that cannot fail proves nothing. This is the fixture that makes it fail."""
    assert _named_violations("real = nominal - inflation\n") == ["nominal - inflation"]
    assert _named_violations("real = nominal_ytm - cumulative_inflation(months)\n")
    assert _named_violations("real = a - cpi_change\n")


def test_the_named_scan_does_not_fire_on_the_legitimate_minus_one() -> None:
    """The other half of falsifiability: a scan that fires on everything is equally useless."""
    assert _named_violations("cumulative = product - 1.0\n") == []
    assert _named_violations("real = (1.0 + nominal) / (1.0 + inflation) - 1.0\n") == []


def test_the_structural_scan_is_falsifiable_in_both_directions() -> None:
    assert _structural_violations("gap = last_month - first_month\n") == [
        "last_month - first_month"
    ]
    assert _structural_violations("cumulative = product - 1.0\n") == []


def test_prose_describing_the_approximation_is_not_a_violation() -> None:
    """This very file, and every module it scans, spells the approximation out to forbid it.

    Without the prose strip the scan would report its own documentation, and the only way to
    get it green would be to stop explaining the rule.
    """
    documented = '"""real = nominal - inflation is forbidden."""\nx = 1\n'

    assert _named_violations(strip_prose(documented)) == []
