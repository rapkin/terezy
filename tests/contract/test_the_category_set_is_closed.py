"""The exposed set is fail-closed against `data/`, in both directions.

Two tests rather than one, and the reason is the one `.importlinter`'s FR-012/FR-013 pair states
at its own site: a single check naming both directions stays green if either is deleted, and the
surviving direction then looks enforced (020 FR-006, FR-007, SC-002, SC-003).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from terezy.api.http import categories
from terezy.data.declarations import resolver

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"


def _covered() -> frozenset[str]:
    return frozenset(categories.directory_of(category) for category in categories.CATEGORIES)


def _directories(root: Path) -> frozenset[str]:
    return frozenset(
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_dir() and not path.name.startswith(".")
    )


@pytest.mark.contract
def test_every_directory_is_served_or_exempt() -> None:
    """Recursive, because six resolver constants point at a subdirectory.

    A one-level walk would report `tax/` and `scenarios/` covered and stop looking -- fail-open
    in exactly the two directories a subdirectory has been added to twice.
    """
    unaccounted = sorted(
        _directories(DATA_ROOT) - _covered() - frozenset(categories.EXEMPT_DIRECTORIES)
    )
    assert not unaccounted, (
        "these directories under data/ are served by no category and named in no exemption, so "
        f"the API is silent about declarations the loader may be reading: {unaccounted}"
    )


@pytest.mark.contract
def test_every_root_file_is_served() -> None:
    covered = _covered()
    unaccounted = sorted(path.name for path in DATA_ROOT.glob("*.toml") if path.name not in covered)
    assert not unaccounted, f"root declaration files no category serves: {unaccounted}"


@pytest.mark.contract
def test_a_directory_nobody_declares_fails_the_check(tmp_path: Path) -> None:
    """The mutation, performed rather than described: a new directory is unaccounted for."""
    scratch = tmp_path / "data"
    scratch.mkdir()
    (scratch / "commitments").mkdir()
    unaccounted = _directories(scratch) - _covered() - frozenset(categories.EXEMPT_DIRECTORIES)
    assert unaccounted == {"commitments"}


@pytest.mark.contract
def test_every_resolver_constant_is_served() -> None:
    """The reverse direction: nothing the loader reads is invisible to the API."""
    declared = {
        name
        for name in dir(resolver)
        if (name.endswith("_DIR") or name.endswith("_FILE")) and name.isupper()
    }
    named = {category.constant for category in categories.CATEGORIES}
    assert declared == named, (
        "the resolver's declaration constants and the categories serving them disagree; "
        f"unserved: {sorted(declared - named)}, named but not declared: {sorted(named - declared)}"
    )


@pytest.mark.contract
def test_every_exemption_names_a_directory_that_exists() -> None:
    """An exemption for a directory nobody has is an exemption nobody can review."""
    missing = sorted(
        name for name in categories.EXEMPT_DIRECTORIES if not (DATA_ROOT / name).is_dir()
    )
    assert not missing, f"exemptions naming directories that do not exist: {missing}"
    assert all(categories.EXEMPT_DIRECTORIES.values()), "every exemption states its reason"
