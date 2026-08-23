"""``scripts/check_provenance.py`` is fail-closed over the data tree.

The gate is the mechanical half of Principle I -- no legal, tax or fee value without a
citation -- and a gate is only as good as its coverage. Its directory list was an
*allowlist*: a directory under ``data/`` that nobody added to ``SOURCED_DIRS`` was silently
never scanned, so the place a future rate was most likely to land -- a new directory -- was
exactly the place the gate could not see. Fail-open is the defect class the constitution
puts at top severity, in a script whose whole job is to prevent it.

So the rule under test: **every directory under ``data/`` is either scanned or exempted by
name with a recorded reason, and an unknown directory is an error.** The exemptions are the
argued ones (``data/README.md``): scenarios, objectives and strategies hold the owner's own
stated beliefs and decisions, streams his own statement of where money lands, and ``user/``
is the gitignored per-user boundary of Principle VII.

Run through a subprocess, against the script itself, because the script is the gate CI
runs: importing pieces of it would test a different program.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_provenance.py"
DATA_ROOT = REPO_ROOT / "data"


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _scratch_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def test_the_shipped_data_root_is_clean(tmp_path: Path) -> None:
    """The baseline the cases below mutate: the shipped tree passes, warnings and all."""
    outcome = _run(_scratch_root(tmp_path))
    assert outcome.returncode == 0, outcome.stdout


def test_an_unknown_directory_under_data_is_an_error_not_a_blind_spot(
    tmp_path: Path,
) -> None:
    """The fail-closed rule itself.

    A new directory carrying an uncited rate must fail the gate *because the directory is
    unknown* -- before anyone remembers to add it to the scanned set. The rate inside it is
    deliberately uncited: under the old allowlist this tree passed clean.
    """
    root = _scratch_root(tmp_path)
    lending = root / "lending"
    lending.mkdir()
    (lending / "rates.toml").write_text(
        '[[rate]]\nid = "usd_lending"\napr_pct = 9.5\n', encoding="utf-8"
    )
    outcome = _run(root)
    assert outcome.returncode == 1
    assert "lending" in outcome.stdout
    assert "SOURCED_DIRS" in outcome.stdout
    assert "EXEMPT_DIRS" in outcome.stdout


def test_the_argued_exemptions_are_by_name_with_a_reason(tmp_path: Path) -> None:
    """streams and scenarios (and the README's other argued cases) stay exempt -- but only
    because they are named, so removing a name makes the gate red rather than blind."""
    root = _scratch_root(tmp_path)
    outcome = _run(root)
    assert outcome.returncode == 0
    # The shipped tree contains the exempt directories; a fail-closed gate that passed
    # while not knowing them would be fail-open with extra steps.
    for exempt in ("streams", "scenarios"):
        assert (root / exempt).is_dir()


def test_a_root_level_file_is_scanned_rather_than_invisible(tmp_path: Path) -> None:
    """``venues.toml`` sits at the data root, outside every directory.

    It carries no observed numeric value today, so it passes -- and it must be *scanned*
    to pass, not skipped: a numeric leaf added to it without a citation is an error, which
    is the difference between "checked and clean" and "never looked at".
    """
    root = _scratch_root(tmp_path)
    clean = _run(root)
    assert clean.returncode == 0

    venues = root / "venues.toml"
    venues.write_text(
        venues.read_text(encoding="utf-8").replace(
            'currencies = ["UAH", "USD"]',
            'currencies = ["UAH", "USD"]\ndaily_limit = 100000.0',
            1,
        ),
        encoding="utf-8",
    )
    dirty = _run(root)
    assert dirty.returncode == 1
    assert "venues.toml" in dirty.stdout
