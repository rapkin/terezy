"""The two data roots a test may run against, and the one that composes them.

Not a test module -- ``pytest`` collects only ``test_*.py``, so this file is imported, never
run.

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

import atexit
import shutil
import tempfile
from functools import cache
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]

SHIPPED: Final = REPO_ROOT / "data"
"""What the tool ships. Real securities only, since 2026-09-02."""

FIXTURES: Final = REPO_ROOT / "tests" / "fixtures" / "data"
"""The overlay of invented declarations. See its own README for what each one is for."""


@cache
def with_fixtures() -> Path:
    """The shipped root with the fixture overlay copied over it, built once per process.

    Cached because the copy is the same tree every time and a suite that rebuilt it per test
    would be measuring the filesystem. Removed at interpreter exit rather than by a fixture:
    module-level constants read it at import time, which is before any fixture runs.
    """
    root = Path(tempfile.mkdtemp(prefix="terezy-composed-root-"))
    atexit.register(shutil.rmtree, root, True)
    shutil.copytree(SHIPPED, root, dirs_exist_ok=True)
    shutil.copytree(FIXTURES, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns("README.md"))
    return root
