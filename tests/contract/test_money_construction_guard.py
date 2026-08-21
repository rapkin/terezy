"""The one hole in the provenance mechanism, closed as far as a test can close it.

Provenance propagation is structural: every combining function in
``terezy.core.primitives.money`` unions its operands' provenance, and those functions
are the only way to combine money, so a sum cannot lose a mark (research.md D2). What
remains constructible anywhere is the record itself. Code elsewhere could write
``Money(amount, currency, provenance.EMPTY)`` from a value that came from an unverified
source and produce an apparently unmarked figure -- FR-015's top-severity defect, with
no gate able to see it.

This test is that gate, within its limits. It scans the shipped source tree for direct
construction of the money record outside the two places entitled to perform it:

* ``core/primitives/money.py`` -- where every derivation happens and provenance is
  unioned;
* ``data/declarations/`` -- the boundary where declared values *enter* the system, and
  the only place where an amount is created from something other than other amounts.
  This is precisely where provenance is attached, so it must be able to construct.

Tracked alongside **E5** in ``docs/REQUIRED_TESTS.md``.

**What this test cannot do**, stated plainly so nobody mistakes a green tick for a
guarantee. It is a textual scan, so an alias (``M = Money``), a ``getattr`` or a
``dataclasses.replace`` would slip past it. It does not read the loader to check that
the provenance it attaches is the *right* provenance. And it deliberately does not scan
``tests/``: tests must be able to build arbitrary inputs, including deliberately
unmarked ones, because that is how the propagation itself gets asserted. The manual
review in T055 exists because of these limits, not in spite of them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "terezy"

CONSTRUCTION = re.compile(r"\bMoney\s*\(")

ALLOWED_FILES = frozenset({Path("core/primitives/money.py")})
ALLOWED_PACKAGES = (Path("data/declarations"),)


def _is_allowed(relative: Path) -> bool:
    if relative in ALLOWED_FILES:
        return True
    return any(package in relative.parents for package in ALLOWED_PACKAGES)


def _offending_lines(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    return [
        (number, line.strip())
        for number, line in enumerate(text.splitlines(), start=1)
        if CONSTRUCTION.search(line)
    ]


@pytest.mark.contract
def test_money_is_constructed_only_where_provenance_is_established() -> None:
    """No module builds money directly except its own module and the loader.

    A violation is not a style problem. It is a place where an amount could be given
    provenance that does not describe it, which is the failure FR-015 calls the highest
    severity class in the project. Derive money through ``money.add``, ``money.sub``,
    ``money.scale``, ``money.total`` or ``money.zero`` instead; every one of them
    carries the mark for you.
    """
    offenders: dict[str, list[tuple[int, str]]] = {}
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        relative = path.relative_to(SOURCE_ROOT)
        if _is_allowed(relative):
            continue
        found = _offending_lines(path)
        if found:
            offenders[str(relative)] = found

    assert not offenders, (
        "money is constructed directly outside the modules entitled to do it, so a "
        "figure could be given provenance that does not describe it (FR-015):\n"
        + "\n".join(
            f"  {name}:{number}: {line}"
            for name, lines in offenders.items()
            for number, line in lines
        )
    )


@pytest.mark.contract
def test_the_scan_would_actually_catch_a_violation() -> None:
    """The guard is only worth having if it can fail. Prove the pattern matches.

    A scan that silently matches nothing passes forever and protects nothing, which is
    the most likely way this test rots: someone renames the record, the regex stops
    matching, and the suite stays green.
    """
    assert CONSTRUCTION.search("    return Money(1.0, Currency.UAH, provenance.EMPTY)")
    assert CONSTRUCTION.search("x = Money (1.0, c, p)")
    assert not CONSTRUCTION.search("def f(amount: Money) -> Money:")
    assert not CONSTRUCTION.search("from terezy.core.primitives.money import Money")


@pytest.mark.contract
def test_the_permitted_sites_are_the_ones_that_exist() -> None:
    """The allow-list names real files, so it cannot quietly permit everything.

    ``core/primitives/money.py`` must exist and must in fact construct money -- if it
    stopped doing so, the allow-list entry is stale and the assumption behind this whole
    guard has changed. ``data/declarations/`` is a package that exists; its modules
    arrive with the loader in a later phase.
    """
    money_module = SOURCE_ROOT / "core" / "primitives" / "money.py"
    assert money_module.is_file()
    assert _offending_lines(money_module), (
        "money.py no longer constructs money; the allow-list, and the assumption that "
        "all derivation happens there, need re-examining"
    )
    assert (SOURCE_ROOT / "data" / "declarations").is_dir()
