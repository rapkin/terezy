"""The delivery framework is importable in exactly one module tree, and nothing is unguarded.

`.importlinter` carries two `forbidden` contracts that between them cover every module tree in
the package: `core-independent-of-frameworks` over `terezy.core`, and
`frameworks-only-in-the-http-module` over `terezy.data`, `terezy.cli`, `terezy.api.answer` and
`terezy.api.diagrams`. Neither can reach `src/terezy/__init__.py` or `src/terezy/api/__init__.py`:
a contract naming `terezy` or `terezy.api` matches its descendants, one of which is
`terezy.api.http`, which has to import the framework. Both are modules an import would sit in
perfectly comfortably, so a scan covers them.

An inclusion list needs its own completeness check or it is the prose enumeration the
constitution says is a check or is not written. `test_every_module_is_guarded` is that check: it
walks `src/terezy/` and requires every module to be named by a contract, named by the scan, or
under `terezy.api.http`. Adding `src/terezy/api/export.py` turns it red before anybody imports
anything into it (020 FR-002, SC-023).
"""

from __future__ import annotations

import configparser
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "src" / "terezy"
CONTRACTS_FILE = REPO_ROOT / ".importlinter"

FRAMEWORKS = ("fastapi", "starlette", "uvicorn")

SCANNED = (Path("__init__.py"), Path("api/__init__.py"))
"""The two files no `forbidden` contract can name. See the module docstring."""

HTTP_TREE = Path("api/http")

FRAMEWORK_IMPORT = re.compile(
    r"^\s*(?:from|import)\s+(" + "|".join(FRAMEWORKS) + r")\b",
    re.MULTILINE,
)


def _contract_source_modules() -> frozenset[str]:
    """Every module tree the two framework contracts guard, read from `.importlinter`."""
    parsed = configparser.ConfigParser()
    parsed.read(CONTRACTS_FILE)
    guarded: set[str] = set()
    for section in parsed.sections():
        forbidden = parsed[section].get("forbidden_modules", "")
        if not all(name in forbidden.split() for name in FRAMEWORKS):
            continue
        guarded.update(parsed[section].get("source_modules", "").split())
    return frozenset(guarded)


def _module_name(relative: Path) -> str:
    parts = relative.with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(("terezy", *parts))


@pytest.mark.contract
def test_the_two_package_inits_import_no_framework() -> None:
    """The two files a contract cannot reach, scanned instead."""
    offenders = {
        str(relative): FRAMEWORK_IMPORT.findall((SOURCE_ROOT / relative).read_text("utf-8"))
        for relative in SCANNED
        if FRAMEWORK_IMPORT.search((SOURCE_ROOT / relative).read_text("utf-8"))
    }
    assert not offenders, (
        "a delivery framework is imported in a package __init__ that no import contract can "
        f"name, so `lint-imports` would stay green: {offenders}"
    )


@pytest.mark.contract
def test_the_scan_would_catch_an_import() -> None:
    """A scan that matches nothing passes forever. Prove the pattern matches."""
    assert FRAMEWORK_IMPORT.search("import fastapi\n")
    assert FRAMEWORK_IMPORT.search("from starlette.responses import Response\n")
    assert FRAMEWORK_IMPORT.search("    import uvicorn\n")
    assert not FRAMEWORK_IMPORT.search("# fastapi is forbidden here\n")


@pytest.mark.contract
def test_every_module_is_guarded() -> None:
    """No module under `src/terezy/` is outside both contracts, the scan and the HTTP tree.

    Both contracts, not only the new one: a check counting only
    `frameworks-only-in-the-http-module` would be red on every module under `core/`, which is
    guarded rather than unguarded.
    """
    guarded = _contract_source_modules()
    assert guarded, "no contract in .importlinter forbids all three frameworks"

    unguarded = sorted(
        str(relative)
        for path in SOURCE_ROOT.rglob("*.py")
        for relative in [path.relative_to(SOURCE_ROOT)]
        if relative not in SCANNED
        and HTTP_TREE not in relative.parents
        and not any(
            _module_name(relative) == tree or _module_name(relative).startswith(tree + ".")
            for tree in guarded
        )
    )
    assert not unguarded, (
        "these modules are named by no framework contract, by no scan, and are not under "
        f"terezy.api.http, so nothing stops one of them importing the framework: {unguarded}"
    )
