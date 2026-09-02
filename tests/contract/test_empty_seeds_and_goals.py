"""SC-008, FR-024, G16: no seeds and no goals is an ordinary run, not a refusal.

**This is deliberately the opposite of feature 003**, and the contrast is the point rather
than an inconsistency. There, an empty registry dimension is a typed outcome, because an
empty venue list and a mistyped path are indistinguishable downstream and one of them is a
mistake. Here they are distinguishable and neither is a mistake: a person who holds nothing
and has declared no target is an ordinary person, and refusing to run for him would be the
tool inventing a requirement he never accepted.

The general rule the two features share, written down so a later reader does not read them as
contradictory: **refuse emptiness where it cannot be told from an error, accept it where it
can** (008 research.md D9).

The other half of this module is the provenance gate, confirmed rather than assumed. The gate
is fail-closed over the whole data tree -- a directory in neither ``SOURCED_DIRS`` nor
``EXEMPT_DIRS`` is an *error* -- so ``data/seeds/`` and ``data/goals/`` are out of scope only
because they are named in ``EXEMPT_DIRS`` with their argument written where a reviewer reads
it. If either ever has to move to ``SOURCED_DIRS``, a market value leaked into a file that
should hold none, and that is the finding these tests exist to make loud.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from terezy.core.ledger import engine, lots, seeds
from terezy.core.primitives.currency import Currency
from terezy.data.declarations import resolver
from tests import data_roots

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from types import ModuleType

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = data_roots.with_fixtures()
GATE = REPO_ROOT / "scripts" / "check_provenance.py"
OPENS_ON = date(2026, 8, 23)
"""The date the empty projection opens. An argument, because there is no clock in the core."""


def _scratch_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _gate() -> ModuleType:
    """``scripts/check_provenance.py`` as a module, so its lists can be read as data.

    It is a script rather than a package, so it is loaded by path -- the same way
    ``tests/contract/test_provenance_gate.py`` reaches it.
    """
    spec = importlib.util.spec_from_file_location("check_provenance", GATE)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Emptiness is ordinary
# ---------------------------------------------------------------------------


def test_a_data_root_with_no_seed_or_goal_directory_resolves(tmp_path: Path) -> None:
    """FR-024: nothing is invented in their absence, and nothing refuses to run.

    The directories are *absent*, not empty -- the case a fresh checkout of somebody else's
    repository would be in.
    """
    root = _scratch_root(tmp_path)
    shutil.rmtree(root / "seeds")
    shutil.rmtree(root / "goals")
    resolved = resolver.seeds_and_goals_from_data_root(root, base_currency=Currency.UAH)
    assert resolved.seeds == ()
    assert resolved.goals == ()
    assert resolved.owner_id is None
    assert resolved.seed_file is None
    assert resolved.goal_file is None


def test_an_empty_seed_or_goal_directory_resolves(tmp_path: Path) -> None:
    """The directory exists and holds no declaration: still ordinary, still not a refusal.

    Contrast ``composition_from_data_root``, where this exact shape *is* an error, because
    the absence of a segment bound is the absence of a policy the search cannot proceed
    without. A projection can proceed perfectly well without a holding.
    """
    root = _scratch_root(tmp_path)
    for directory in ("seeds", "goals"):
        for path in (root / directory).glob("*.toml"):
            path.unlink()
    resolved = resolver.seeds_and_goals_from_data_root(root, base_currency=Currency.UAH)
    assert resolved.seeds == ()
    assert resolved.goals == ()


def test_one_declared_and_the_other_absent_is_also_ordinary(tmp_path: Path) -> None:
    """A person may hold something and want nothing in particular, or the reverse."""
    root = _scratch_root(tmp_path)
    shutil.rmtree(root / "goals")
    holdings_only = resolver.seeds_and_goals_from_data_root(root, base_currency=Currency.UAH)
    assert holdings_only.seeds
    assert holdings_only.goals == ()
    assert holdings_only.owner_id == "owner-001"

    other = _scratch_root(tmp_path / "second")
    shutil.rmtree(other / "seeds")
    goals_only = resolver.seeds_and_goals_from_data_root(other, base_currency=Currency.UAH)
    assert goals_only.seeds == ()
    assert goals_only.goals
    assert goals_only.owner_id == "owner-001"


def test_a_projection_over_no_seeds_starts_from_empty_positions() -> None:
    """SC-008: empty positions and no invented placeholder anywhere in the result."""
    opened = seeds.opening_events((), {}, opens_on=OPENS_ON)
    assert opened == ()
    state = engine.fold(opened, base_currency=Currency.UAH, consumption_method=lots.FIFO)
    assert state.positions == {}
    assert state.accounts == {}
    assert state.disposals == ()
    assert state.as_of is None


# ---------------------------------------------------------------------------
# The provenance gate: exempt by name, with the reason, and never sourced
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("directory", ["seeds", "goals"])
def test_the_owner_directories_are_exempt_by_name_with_a_reason(directory: str) -> None:
    """Being absent from ``SOURCED_DIRS`` is not a way to be out of scope: the gate is
    fail-closed, so an unlisted directory is an error rather than a blind spot."""
    gate = _gate()
    assert directory not in gate.SOURCED_DIRS
    assert directory in gate.EXEMPT_DIRS
    assert gate.EXEMPT_DIRS[directory].strip()


@pytest.mark.parametrize("directory", ["seeds", "goals"])
def test_the_recorded_reason_is_the_one_the_other_owner_directories_carry(directory: str) -> None:
    """The exemption is the owner's-own-records one, and the reason has to say so.

    A reason that read like a citation would mean somebody had put an observation of the
    world into a file that holds none, which is the thing the wording is there to prevent.
    """
    reason = _gate().EXEMPT_DIRS[directory].lower()
    assert "owner" in reason
    assert "observation" in reason or "cite" in reason or "vouch" in reason


def test_the_shipped_data_root_still_passes_the_gate(tmp_path: Path) -> None:
    """With two new directories in the tree, the gate is still clean -- and still looking."""
    root = _scratch_root(tmp_path)
    outcome = subprocess.run(
        [sys.executable, str(GATE), str(root)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert outcome.returncode == 0, outcome.stdout
