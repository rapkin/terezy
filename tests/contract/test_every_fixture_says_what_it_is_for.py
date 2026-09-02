"""Every invented declaration names the mechanism it is the only example of.

The owner's rule of 2026-09-02 moved the invented instruments out of the shipped registry and
**kept every one of them**, because each is the sole example of something live: retiring one
deletes the only reachable case of a mechanism, and the deletion looks like tidying. The
defence is that the mechanism is written down beside the file -- and a prose list of a
directory is false the moment the directory moves, so it is a check rather than a list.

``tests/fixtures/data/README.md`` is that list, and this asserts both directions of it.
"""

from __future__ import annotations

import re

import pytest

from tests import data_roots

pytestmark = pytest.mark.contract

README = data_roots.FIXTURES / "README.md"

ROW = re.compile(r"^\| `([A-Za-z0-9_./-]+\.toml)` \|", re.MULTILINE)
"""A table row, which is the only place the README accounts for a file of this tree.

Anchored to the row rather than to any backticked path: the prose in the rows also names
files under ``data/``, and those are not this tree's to account for.
"""


def _on_disk() -> set[str]:
    """Every declaration under the overlay, as a path relative to it."""
    root = data_roots.FIXTURES
    return {str(path.relative_to(root)) for path in root.rglob("*.toml")}


def _named() -> set[str]:
    """Every declaration the README's table accounts for."""
    return set(ROW.findall(README.read_text(encoding="utf-8")))


def test_the_readme_names_every_invented_declaration() -> None:
    missing = _on_disk() - _named()
    assert not missing, (
        "a fixture with no line in tests/fixtures/data/README.md is a file nobody can tell "
        "apart from spare data, and the next person to tidy the tree deletes the only example "
        f"of a mechanism. Unnamed: {sorted(missing)}"
    )


REPLACES = frozenset({"seeds/owner-001.toml"})
"""The one shipped path the overlay is allowed to stand in for.

``seeds/`` resolves at most one file per data root, so the fixture lots have to carry the
shipped file's own name. Everywhere else the overlay JOINS a globbed directory, and that is
the difference the test below pins.
"""


def test_the_overlay_replaces_one_shipped_file_and_only_that_one() -> None:
    """A silent substitution is the confusion the owner's decision exists to prevent.

    ``shutil.copytree(..., dirs_exist_ok=True)`` overwrites any shipped path the overlay
    repeats, without a diff in ``data/`` and without a gate noticing. An overlay file named
    ``instruments/UA4000235865.toml`` -- the very ISIN ``enumerated_out_of_order`` is modelled
    on -- would put an invented declaration under a real security's id in every mechanism
    suite. Nothing else in the tree can see that happen, so it is asserted here.
    """
    shipped = {
        str(path.relative_to(data_roots.SHIPPED)) for path in data_roots.SHIPPED.rglob("*.toml")
    }
    assert _on_disk() & shipped == REPLACES


def test_the_readme_names_nothing_that_is_not_there() -> None:
    phantom = _named() - _on_disk()
    assert not phantom, (
        "the README describes a fixture the overlay does not hold, so the argument for keeping "
        f"it outlived the file: {sorted(phantom)}"
    )
