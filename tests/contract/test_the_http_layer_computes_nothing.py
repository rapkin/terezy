"""This layer selects, serialises and refuses. Asserted as four absences over its source.

There is no exception for a display conversion: the owner deferred the switch on 2026-09-03, so
no module here constructs money at all (020 FR-003, FR-020, FR-049, FR-050, SC-008b, SC-008c,
SC-017, SC-023a, SC-024).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HTTP = REPO_ROOT / "src" / "terezy" / "api" / "http"
HTTP_TESTS = (
    REPO_ROOT / "tests" / "http_client.py",
    *sorted((REPO_ROOT / "tests").rglob("test_the_*.py")),
    *sorted((REPO_ROOT / "tests").rglob("test_a_*.py")),
)

MONEY = re.compile(r"\bMoney\s*\(|\bmoney\.(add|sub|scale|total|convert|zero|from_pegged_term)\b")
CANONICAL = re.compile(r"results\.canonical|from terezy\.core\.results import canonical")
STALENESS = re.compile(r"staleness_of_\w+|\bstaleness\.\w*\(")
SERVER = re.compile(r"uvicorn\.run|\.serve\(\)|socket\.socket\(|\.listen\(|\.bind\(")


def _sources() -> list[Path]:
    return sorted(HTTP.rglob("*.py"))


def _hits(pattern: re.Pattern[str], paths: list[Path]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in paths:
        lines = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if pattern.search(line)
        ]
        if lines:
            found[path.relative_to(REPO_ROOT).as_posix()] = lines
    return found


@pytest.mark.contract
def test_no_module_constructs_money_or_combines_it() -> None:
    assert not _hits(MONEY, _sources())


@pytest.mark.contract
def test_the_scan_would_catch_a_construction() -> None:
    assert MONEY.search("    return Money(1.0, Currency.UAH, provenance.EMPTY)")
    assert MONEY.search("    total = money.add(left, right)")
    assert not MONEY.search("def _figure(amount: Money) -> Money:")


@pytest.mark.contract
def test_no_module_builds_a_body_from_the_canonical_encoding() -> None:
    """That encoding excludes provenance by design, so it would satisfy FR-017 nowhere."""
    assert not _hits(CANONICAL, _sources())


@pytest.mark.contract
def test_no_module_ages_a_source() -> None:
    """A serialiser that filled the gap in would erase the distinction an empty kind keeps:
    *nobody could check this* is not *checked and current*."""
    assert not _hits(STALENESS, _sources())


@pytest.mark.contract
def test_no_test_starts_a_server() -> None:
    """The other half of the no-network rule: the guard covers outbound, this covers listening."""
    assert not _hits(SERVER, [path for path in HTTP_TESTS if path.is_file()])


@pytest.mark.contract
def test_the_only_server_call_is_the_entry_points() -> None:
    """A scan that matched nothing anywhere would pass for the wrong reason."""
    assert set(_hits(SERVER, _sources())) == {"src/terezy/api/http/serve.py"}


@pytest.mark.contract
def test_the_cli_does_not_route_through_the_http_layer() -> None:
    """A second client does not make the first one a client of it (FR-004).

    `.importlinter`'s layers contract permits `cli` to import anything under `api`, so this is
    the half a contract cannot state: the CLI is a client of `api.answer`, unchanged.
    """
    reaching = {
        path.relative_to(REPO_ROOT).as_posix()
        for tree in ("cli", "core")
        for path in (REPO_ROOT / "src" / "terezy" / tree).rglob("*.py")
        if "api.http" in path.read_text(encoding="utf-8")
    }
    assert not reaching, f"these modules reach into the HTTP layer: {sorted(reaching)}"
