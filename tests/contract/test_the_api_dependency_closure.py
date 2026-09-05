"""A new runtime dependency does not arrive unreviewed (020 FR-036, SC-016b).

The closure is walked from the ``api`` extra with **every environment marker included and none
evaluated**, and with extras traversed only where this project asks for one. A marker-evaluating
gate would be green on macOS and red on Windows for the same commit, which is the one thing a
gate must not be -- ``colorama`` reaches the tree behind ``sys_platform == 'win32'`` and is
reviewed here even though it is not installed on this machine.

:data:`REVIEWED` is where the enumeration lives, because a list in prose is one nothing checks.
A package that appears without a line describing its network behaviour fails the build.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping

LOCK = Path(__file__).resolve().parents[2] / "uv.lock"

PROJECT = "terezy"
EXTRA = "api"

REVIEWED: dict[str, str] = {
    "fastapi": "None of its own; serves what the application returns. Its docs UI is disabled.",
    "starlette": "None. The ASGI toolkit under FastAPI.",
    "uvicorn": "Listens on the address it is given; makes no outbound connection.",
    "uvloop": "None. An event-loop implementation.",
    "httptools": "None. An HTTP parser.",
    "websockets": "None unless a WebSocket route exists; this feature declares none.",
    "watchfiles": "None. A filesystem watcher used only by --reload, which is not shipped.",
    "python-dotenv": "None. Reads a local file.",
    "pyyaml": "None. Also what the compose-file test parses with.",
    "pydantic": "None. Already a base dependency, used at the load boundary.",
    "pydantic-core": "None. Pydantic's compiled validation core.",
    "annotated-doc": "None. A typing helper fastapi 0.141 requires directly.",
    "annotated-types": "None. Pydantic's constraint vocabulary.",
    "typing-inspection": "None. A typing helper fastapi 0.141 requires directly.",
    "typing-extensions": "None.",
    "anyio": "None of its own. The async runtime abstraction under Starlette.",
    "idna": "None. Hostname encoding, reached through anyio.",
    "click": "None. Uvicorn's command line.",
    "h11": "None. An HTTP/1.1 state machine.",
    "colorama": "None. Terminal colour, reached through click on Windows only.",
}


def _packages() -> dict[str, Any]:
    lock = tomllib.loads(LOCK.read_text(encoding="utf-8"))
    return {str(package["name"]): package for package in lock["package"]}


def _requirements(package: Mapping[str, Any], extras: tuple[str, ...]) -> list[Any]:
    declared = list(package.get("dependencies", []))
    optional = package.get("optional-dependencies", {})
    for extra in extras:
        declared.extend(optional.get(extra, []))
    return declared


def _closure() -> set[str]:
    packages = _packages()
    seen: set[tuple[str, tuple[str, ...]]] = set()

    def walk(name: str, extras: tuple[str, ...]) -> None:
        if (name, extras) in seen:
            return
        seen.add((name, extras))
        for requirement in _requirements(packages[name], extras):
            walk(str(requirement["name"]), tuple(sorted(requirement.get("extra", []))))

    # Seeded from the extra alone: the base dependencies are a separate closure, which is why
    # `tzdata` -- reached through pandas -- is not a package the API brought in (FR-036).
    for requirement in packages[PROJECT]["optional-dependencies"][EXTRA]:
        walk(str(requirement["name"]), tuple(sorted(requirement.get("extra", []))))

    return {name for name, _ in seen}


@pytest.mark.contract
def test_the_runtime_closure_equals_the_reviewed_list() -> None:
    closure = _closure()

    unreviewed = sorted(closure - set(REVIEWED))
    gone = sorted(set(REVIEWED) - closure)

    assert not unreviewed, (
        "a runtime dependency arrived without a review line describing its network "
        f"behaviour (FR-036): {unreviewed}"
    )
    assert not gone, f"the reviewed list names packages the lock file no longer carries: {gone}"


@pytest.mark.contract
def test_every_reviewed_package_carries_a_note() -> None:
    assert all(note.strip() for note in REVIEWED.values())


@pytest.mark.contract
def test_no_marker_is_evaluated_by_the_walk() -> None:
    """``colorama`` sits behind ``sys_platform == 'win32'`` and is not installed on a mac. It is
    in the closure because the walk reads the lock file rather than the environment, and that is
    what makes this gate give the same answer on every machine."""
    packages = _packages()
    marked = [
        entry for entry in packages["click"]["dependencies"] if entry.get("name") == "colorama"
    ]

    assert marked
    assert "marker" in marked[0]
    assert "colorama" in _closure()


@pytest.mark.contract
@pytest.mark.parametrize("absent", ["certifi", "sniffio", "tzdata", "exceptiongroup"])
def test_the_four_plausible_entries_that_were_measured_out_stay_out(absent: str) -> None:
    """Each was in a draft of the review and each came out because the lock file was read
    rather than the dependency tree remembered. Naming a package that is not there is the same
    defect as omitting one that is."""
    assert absent not in _closure()
    assert absent not in REVIEWED
