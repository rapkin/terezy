"""SC-007: the owner's life stays in the owner's files, and touches no curated one.

Principle VII draws the boundary between **curated** data -- instruments, routes, tax packs,
public facts about the world, shared and version-controlled -- and **per-owner** data, which
is one person's life. Feature 008 is the first thing that lives wholly on the private side:
what he holds, and what the money is for.

Three claims, and the third is the one that needs a test rather than an argument:

1. every seed lot and every goal carries ``owner_id``;
2. the two files must name the same person, so one run holds one life;
3. **declaring, changing or deleting them modifies no curated file** -- verified by hashing
   the curated tree before and after rather than by reading the code and believing it.

The gate half of the boundary -- that ``data/seeds/`` and ``data/goals/`` are exempt from the
citation requirement **by name, with their reason**, rather than by being unlisted -- is
asserted in ``tests/contract/test_empty_seeds_and_goals.py`` beside the emptiness rule.
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import date
from pathlib import Path

import pytest

from terezy.core.ledger import seeds
from terezy.core.primitives.currency import Currency
from terezy.data.declarations import loader, resolver

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
SEEDS = DATA_ROOT / "seeds" / "owner-001.toml"
GOALS = DATA_ROOT / "goals" / "owner-001.toml"
OWNER = "owner-001"

CURATED_DIRS = ("instruments", "routes", "channels", "tax", "scenarios")
"""The shared side of the boundary. Every directory here is a public fact about the world."""


def _scratch_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _curated_digest(root: Path) -> dict[str, str]:
    """A content hash per curated file, so a change anywhere in the tree is visible.

    Hashed rather than compared by modification time: a file rewritten with identical bytes
    is not a change to the data, and a test that failed on it would be testing the filesystem.
    """
    digests: dict[str, str] = {}
    for directory in CURATED_DIRS:
        for path in sorted((root / directory).rglob("*.toml")):
            digests[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted(root.glob("*.toml")):
        digests[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def test_every_seed_lot_carries_the_owner() -> None:
    """FR-022, and it is on every *row* rather than only on the file.

    The file's ``[owner]`` table is where it is declared once; carrying it on each record is
    what makes a lot self-describing after the TOML has been discarded, which is the point of
    having the field before there is a second owner to need it.
    """
    owner_id, declared = loader.seeds_from_file(SEEDS, base_currency=Currency.UAH)
    assert owner_id == OWNER
    assert declared
    assert all(lot.owner_id == OWNER for lot in declared)


def test_every_goal_carries_the_owner() -> None:
    owner_id, declared = loader.goals_from_file(GOALS)
    assert owner_id == OWNER
    assert declared
    assert all(goal.owner_id == OWNER for goal in declared)


def test_the_events_a_seed_opens_carry_the_owner_too() -> None:
    """The boundary survives the transformation into ledger events.

    An event stream that lost the owner would make the ledger the one place in the system
    where whose money it is cannot be answered -- and the ledger is where every figure comes
    from.
    """
    declarations = resolver.from_data_root(DATA_ROOT)
    _, declared = loader.seeds_from_file(SEEDS, base_currency=Currency.UAH)
    opened = seeds.opening_events(declared, declarations.instruments, opens_on=date(2026, 8, 23))
    assert isinstance(opened, tuple), opened
    assert opened
    assert all(event.owner_id == OWNER for event in opened)


def test_resolving_seeds_and_goals_changes_no_curated_file(tmp_path: Path) -> None:
    """SC-007's measurable half: compare the curated data before and after."""
    root = _scratch_root(tmp_path)
    before = _curated_digest(root)
    resolved = resolver.seeds_and_goals_from_data_root(root, base_currency=Currency.UAH)
    assert resolved.owner_id == OWNER
    assert _curated_digest(root) == before


def test_deleting_the_per_owner_files_removes_every_record_and_no_curated_one(
    tmp_path: Path,
) -> None:
    """SC-007's other half, stated as the owner would experience it.

    Deleting his declarations must remove his holdings and his goal and nothing else -- which
    is what makes the boundary worth having: the private side can be thrown away without
    damaging the shared side.
    """
    root = _scratch_root(tmp_path)
    before = _curated_digest(root)
    shutil.rmtree(root / "seeds")
    shutil.rmtree(root / "goals")

    resolved = resolver.seeds_and_goals_from_data_root(root, base_currency=Currency.UAH)
    assert resolved.seeds == ()
    assert resolved.goals == ()
    assert resolved.owner_id is None
    assert _curated_digest(root) == before
