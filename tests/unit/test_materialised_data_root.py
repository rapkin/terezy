"""The composed root written where a process outside pytest can read it.

`python -m tests.data_roots --materialise` is what the Playwright suite starts the API over, so
that the screen it drives is drawn from invented declarations on every machine.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from terezy.data.declarations import resolver
from tests import data_roots

OVERLAY_SEEDS = Path(resolver.USER_DIR) / resolver.SEEDS_DIR / "owner-001.toml"


def test_it_writes_a_root_that_outlives_the_process_that_composed_it(tmp_path: Path) -> None:
    """The whole point of the entry point: :func:`with_fixtures` unlinks at interpreter exit."""
    written = data_roots.materialise(tmp_path / "root")
    assert (written / resolver.VENUES_FILE).is_file(), "a root the API would refuse to start over"
    assert (written / "questions" / "a-holding-among-the-words.toml").is_file()
    assert (written / "instruments" / "synthetic_held_x.toml").is_file()


def test_the_only_lots_it_carries_are_the_invented_ones(tmp_path: Path) -> None:
    """The private overlay it holds is the fixture's, and the shipped one is not copied at all.

    Both halves are asserted: that it is the fixture file, and that every lot in it is flagged
    synthetic, which is the claim `data/README.md` rule 5 makes about a committed declaration.
    """
    written = data_roots.materialise(tmp_path / "root")
    declared = tomllib.loads((written / OVERLAY_SEEDS).read_text(encoding="utf-8"))
    assert declared["seed"], "the overlay declares a lot, or the held block is vacuous again"
    assert all(lot["is_synthetic"] for lot in declared["seed"])
    assert declared == tomllib.loads(
        (data_roots.FIXTURES / OVERLAY_SEEDS).read_text(encoding="utf-8")
    )


def test_it_replaces_what_a_previous_run_left(tmp_path: Path) -> None:
    destination = tmp_path / "root"
    data_roots.materialise(destination)
    stale = destination / "questions" / "left-behind.toml"
    stale.write_text("", encoding="utf-8")
    assert not (data_roots.materialise(destination) / stale.relative_to(destination)).exists()
