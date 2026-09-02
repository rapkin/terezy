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
from terezy.data.declarations.errors import DeclarationError
from tests import data_roots

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = data_roots.with_fixtures()
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


# ---------------------------------------------------------------------------
# The synthetic label, machine-readable rather than a comment
# ---------------------------------------------------------------------------


def test_every_declared_per_owner_record_is_labelled_synthetic() -> None:
    """FR-025, and `data/README.md` rule 5 -- the owner's own rule -- made checkable.

    Over the COMPOSED root, because the label is only checkable where a labelled record
    exists: `data/seeds/` declares no lot since the narrowing of 2026-09-02, and that its
    list is empty rather than mislabelled is
    `test_seed_declaration_loading.py::test_what_ships_declares_an_owner_and_no_lot`.

    What may be committed here is a public fact or a fixture that says it is one. The header
    comment says so to a human; ``is_synthetic`` says so to the tool, which is what makes "the
    day a file stops being synthetic it stops being committable" a sentence something other
    than a reviewer can enforce.

    The assertion is on the **loaded records**, not on the file text: a label that survives
    only as a comment is lost the moment the TOML is discarded, and every downstream figure is
    computed from the records.
    """
    _, declared_seeds = loader.seeds_from_file(SEEDS, base_currency=Currency.UAH)
    _, declared_goals = loader.goals_from_file(GOALS)
    assert declared_seeds
    assert declared_goals
    assert all(lot.is_synthetic for lot in declared_seeds)
    assert all(goal.is_synthetic for goal in declared_goals)


def test_the_label_is_required_rather_than_defaulted(tmp_path: Path) -> None:
    """Omission must fail, and it must fail in the safe direction.

    Defaulting to ``false`` would let a fixture be mistaken for the owner's real position
    through a forgotten line; defaulting to ``true`` would let his real holdings be committed
    while claiming to be invented. Both are worse than a load error, which is the same argument
    ``InstrumentTable.is_synthetic`` already carries.
    """
    target = tmp_path / "unlabelled.toml"
    target.write_text(
        "\n".join(
            line
            for line in SEEDS.read_text(encoding="utf-8").splitlines()
            if not line.startswith("is_synthetic")
        ),
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(target, base_currency=Currency.UAH)
    assert "is_synthetic" in caught.value.field_path
