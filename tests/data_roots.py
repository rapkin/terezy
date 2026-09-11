"""The two data roots a test may run against, and the one that composes them.

``pytest`` collects only ``test_*.py``, so this file is imported rather than collected. It is
also an entry point: ``python -m tests.data_roots --materialise <dir>`` writes the composed root
where a process outside pytest -- the API the Playwright suite starts -- can be pointed at it.

**The shipped root carries only real instruments** (owner decision, 2026-09-02). The invented
ones a test needs live in ``tests/fixtures/data/``, and :func:`with_fixtures` is the composed
root: ``data/`` copied, then that tree copied over it, so a fixture file replaces a shipped one
of the same path and joins a globbed directory otherwise.

**A copy rather than symlinks or a second registry argument.** The resolver takes one root and
globs it, so composing has to happen on disk, and copying a root to edit it is what the suites
that plant a malformed declaration already do. Paths a manifest records are relative to the root
it was given, so the composed root produces the same input ids as the shipped one.
"""

from __future__ import annotations

import argparse
import atexit
import shutil
import tempfile
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]

COMMITTED: Final = REPO_ROOT / "data"
"""The data root as it sits in the working tree -- **including** anything gitignored in it."""

PRIVATE_OVERLAY: Final = "user"
"""What ``resolver.USER_DIR`` derives from a data root, and the one directory in it this suite
must never read: it is where the owner's real position lives (`data/README.md` rule 5)."""


def _without_the_private_overlay(source: Path, prefix: str) -> Path:
    """A copy of a data root with ``user/`` left out, so no test can resolve his real lots.

    **Copied rather than read in place, and that is the whole point.** ``data_roots_of``
    derives the overlay from whatever root it is given, so a suite pointed at the working
    tree's ``data/`` would fold his quantities and costs into every golden taken over it --
    and the golden's *digest* would then encode them, which being gitignored does not prevent.
    Refusing to run while the directory exists was the other option and is worse: it makes the
    suite unusable on the one machine the file belongs on.
    """
    root = Path(tempfile.mkdtemp(prefix=prefix))
    atexit.register(shutil.rmtree, root, True)
    shutil.copytree(
        source, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns(PRIVATE_OVERLAY)
    )
    return root


SHIPPED: Final = _without_the_private_overlay(COMMITTED, "terezy-shipped-root-")
"""What the tool ships. Real securities only, since 2026-09-02, and never his own position."""

FIXTURES: Final = REPO_ROOT / "tests" / "fixtures" / "data"
"""The overlay of invented declarations. See its own README for what each one is for."""


@cache
def with_fixtures() -> Path:
    """The shipped root with the fixture overlay copied over it, built once per process.

    Cached because the copy is the same tree every time and a suite that rebuilt it per test
    would be measuring the filesystem. Removed at interpreter exit rather than by a fixture:
    module-level constants read it at import time, which is before any fixture runs.
    """
    root = _without_the_private_overlay(SHIPPED, "terezy-composed-root-")
    shutil.copytree(FIXTURES, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns("README.md"))
    return root


def materialise(destination: Path) -> Path:
    """The composed root copied where a process outside pytest can be pointed at it.

    :func:`with_fixtures` builds under ``tempfile`` and unlinks at interpreter exit, so a root
    handed to another process would be gone before it read it. An existing destination is
    replaced rather than merged: a stale file left from a previous run is a declaration nobody
    wrote.
    """
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(with_fixtures(), destination)
    return destination


def _main(argv: Sequence[str] | None = None) -> int:
    parsed = argparse.ArgumentParser(
        prog="python -m tests.data_roots",
        description=(
            "Write the composed data root -- the shipped tree without the private overlay, "
            "plus tests/fixtures/data/ -- to the given directory."
        ),
    )
    parsed.add_argument("--materialise", required=True, type=Path, metavar="DIRECTORY")
    materialise(parsed.parse_args(argv).materialise)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
