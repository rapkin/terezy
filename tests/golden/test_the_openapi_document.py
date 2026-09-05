"""The committed OpenAPI document, byte for byte.

A published contract rather than evidence of a run: a second codebase is generated from it, so
it is gated rather than merely written out. It is deliberately not filed under a golden's usual
reading -- here the artefact really does constrain the input, because the input is the wire shape
(020 FR-038, FR-038a, FR-039, FR-041, SC-007, SC-007a, SC-007b, SC-007c, SC-031).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from terezy.api.http import document
from terezy.api.http.service import create_app
from tests.data_roots import SHIPPED
from tests.http_client import served

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = SHIPPED


@pytest.mark.golden
def test_regenerating_produces_the_committed_bytes() -> None:
    rendered = document.rendered(create_app(DATA_ROOT, client=None))
    committed = document.committed()
    if rendered != committed:
        moved = _first_difference(rendered, committed)
        pytest.fail(
            "the generated document and the committed one differ, first at "
            f"{moved}. Run `uv run python scripts/generate_openapi.py` and read the diff."
        )


@pytest.mark.golden
def test_the_endpoint_serves_the_committed_file_verbatim() -> None:
    """Not a re-serialisation: the framework writes compact separators and no trailing newline."""
    response = served(DATA_ROOT).get(f"{document.PREFIX}/openapi.json")
    assert response.status_code == 200
    assert response.text == document.committed()


@pytest.mark.golden
def test_the_document_is_canonical() -> None:
    committed = document.committed()
    assert committed.endswith("\n")
    parsed = json.loads(committed)
    assert committed == json.dumps(parsed, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


@pytest.mark.golden
def test_the_version_is_a_literal_and_no_path_reads_distribution_metadata() -> None:
    """A package version is read from installed metadata, so an editable install of a dirty tree
    and a built wheel of the same source can disagree -- and the gate would then be red on one
    machine and green on another with no source change."""
    parsed: dict[str, Any] = json.loads(document.committed())
    assert parsed["info"]["version"] == document.VERSION
    sources = sorted((REPO_ROOT / "src" / "terezy" / "api" / "http").rglob("*.py"))
    reading = [
        path.name
        for path in sources
        if "importlib.metadata" in path.read_text(encoding="utf-8")
        or "distribution(" in path.read_text(encoding="utf-8")
    ]
    assert not reading, f"these modules read distribution metadata: {reading}"


@pytest.mark.golden
def test_every_published_path_is_under_the_prefix() -> None:
    parsed: dict[str, Any] = json.loads(document.committed())
    assert parsed["paths"]
    assert all(path.startswith(f"{document.PREFIX}/") for path in parsed["paths"])


@pytest.mark.golden
def test_the_generator_leaves_an_unmodified_tree_unchanged() -> None:
    before = document.PATH.read_bytes()
    try:
        finished = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "generate_openapi.py")],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "unchanged" in finished.stdout
        assert document.PATH.read_bytes() == before
    finally:
        # The script writes; this test must not leave a tracked file altered when it fails.
        document.PATH.write_bytes(before)


@pytest.mark.golden
def test_a_moved_field_turns_the_gate_red() -> None:
    """The mutation, performed in memory: one renamed field and the bytes no longer match."""
    generated = json.loads(document.rendered(create_app(DATA_ROOT, client=None)))
    venues = generated["components"]["schemas"]["venues_Venue"]["properties"]
    venues["currencies_renamed"] = venues.pop("currencies")
    mutated = json.dumps(generated, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert mutated != document.committed()


def _first_difference(rendered: str, committed: str) -> str:
    for number, (left, right) in enumerate(
        zip(rendered.splitlines(), committed.splitlines(), strict=False), start=1
    ):
        if left != right:
            return f"line {number}: generated {left.strip()!r} against committed {right.strip()!r}"
    return f"line {min(len(rendered.splitlines()), len(committed.splitlines())) + 1}: length"
