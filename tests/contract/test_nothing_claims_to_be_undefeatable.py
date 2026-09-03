"""What the guard buys is that the wrong thing is no longer the easy thing -- not impossibility.

A container marker can be created by someone who wants to create one, so publishing to a
network stops being one environment variable and becomes forging a marker. That is a different
security property from impossibility, and 020 FR-027b forbids writing it as impossibility
anywhere this feature's messages or documents reach. Prose is exactly where it would be quietly
overstated, so the claim-shape is scanned rather than reviewed (SC-013a).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

SCANNED = (
    ROOT / "src" / "terezy" / "api" / "http",
    ROOT / "docker-compose.yml",
    ROOT / "Dockerfile",
    Path(__file__).parent / "test_the_host_header_is_declared.py",
    Path(__file__).parent / "test_the_shipped_compose_file.py",
    ROOT / "tests" / "unit" / "test_the_bind_context_is_closed.py",
    ROOT / "tests" / "unit" / "test_the_client_must_be_on_loopback.py",
    ROOT / "tests" / "unit" / "test_the_container_claim_is_verified.py",
    ROOT / "tests" / "unit" / "test_the_startup_refuses_a_public_bind.py",
)

OVERCLAIM = re.compile(
    r"""
      cannot \s+ be \s+ (?: defeated | bypassed | circumvented | forged )
    | can't  \s+ be \s+ (?: defeated | bypassed | circumvented | forged )
    | impossible
    | unbreakable
    | foolproof
    | airtight
    | \b guarantees? \s+ that \s+ (?: nobody | no \s* one )
    | no \s+ (?: one | body ) \s+ can \s+ (?: ever \s+ )? reach
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _files() -> list[Path]:
    found: list[Path] = []
    for entry in SCANNED:
        assert entry.exists(), f"the scan names a path that is not there: {entry}"
        found.extend(sorted(entry.rglob("*.py")) if entry.is_dir() else [entry])
    return found


@pytest.mark.contract
def test_no_file_this_feature_adds_claims_the_restriction_cannot_be_defeated() -> None:
    offenders: list[str] = []
    for path in _files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if OVERCLAIM.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")

    assert not offenders, (
        "an overclaim about the bind restriction; state what the check buys instead "
        "(FR-027b):\n" + "\n".join(offenders)
    )


@pytest.mark.contract
def test_the_scan_would_actually_catch_an_overclaim() -> None:
    """A scan that silently matches nothing passes forever and protects nothing."""
    assert OVERCLAIM.search("This restriction cannot be defeated.")
    assert OVERCLAIM.search("The marker check makes LAN exposure impossible.")
    assert OVERCLAIM.search("It guarantees that nobody outside the host can read it.")
    assert OVERCLAIM.search("An airtight guard.")

    assert not OVERCLAIM.search("what the check buys is that the wrong thing is not the easy one")
    assert not OVERCLAIM.search("a person who wants to defeat the check can create a marker")
    assert not OVERCLAIM.search("the shipped compose file cannot publish off loopback")
