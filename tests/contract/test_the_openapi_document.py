"""The OpenAPI document, generated on the fly and stored nowhere.

A published contract rather than evidence of a run: a second codebase is generated from it. It
was a checked-in file under a byte gate until the owner's decision of 2026-09-05
(`specs/decisions/2026-09-05-openapi-on-the-fly.toml`) made it a build step, so what is asserted
here is what a build actually depends on -- that the generator and the endpoint emit one document,
and that its bytes are canonical (020 FR-038, FR-038a, FR-039, FR-040, FR-041, SC-007, SC-007a,
SC-007b, SC-007c).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from terezy.api.http import document
from tests.data_roots import SHIPPED
from tests.http_client import served

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "scripts" / "generate_openapi.py"
DATA_ROOT = SHIPPED


def _served_document() -> str:
    response = served(DATA_ROOT).get(f"{document.PREFIX}/openapi.json")
    assert response.status_code == 200
    return response.text


def _generated(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GENERATOR), *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.mark.contract
def test_the_endpoint_serves_what_the_generator_writes(tmp_path: Path) -> None:
    """The gate the checked-in file used to be. A client's types come from the generator and its
    requests go to the endpoint, so the two emitting different bytes is drift with no diff."""
    written = tmp_path / "openapi.json"
    _generated("--out", str(written))
    assert written.read_text(encoding="utf-8") == _served_document()


@pytest.mark.contract
def test_the_generator_writes_to_stdout_by_default() -> None:
    """A build pipes it; naming a path is the exception, not the interface."""
    assert _generated().stdout == _served_document()


@pytest.mark.contract
def test_the_document_is_canonical() -> None:
    """Sorted keys, two-space indent, a trailing newline -- reproducible bytes, per FR-039."""
    body = _served_document()
    assert body.endswith("\n")
    parsed = json.loads(body)
    assert body == json.dumps(parsed, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


@pytest.mark.contract
def test_the_version_is_a_literal_and_no_path_reads_distribution_metadata() -> None:
    """A package version is read from installed metadata, so an editable install of a dirty tree
    and a built wheel of the same source would publish different versions of one wire shape."""
    parsed: dict[str, Any] = json.loads(_served_document())
    assert parsed["info"]["version"] == document.VERSION
    sources = sorted((REPO_ROOT / "src" / "terezy" / "api" / "http").rglob("*.py"))
    reading = [
        path.name
        for path in sources
        if "importlib.metadata" in (text := path.read_text(encoding="utf-8"))
        or "distribution(" in text
    ]
    assert not reading, f"these modules read distribution metadata: {reading}"


UNDER_A_SCENARIO = f"{document.PREFIX}/spendable"
"""One scenario-taking route, whose 400 is the document's only hand-declared union."""


@pytest.mark.contract
def test_the_refusals_a_route_answers_with_are_the_ones_it_declares() -> None:
    """A route's `responses` are declared by hand and nothing else here reaches them: the walk in
    `test_tags_and_unions.py` starts at the response envelope and never sees a refusal declared
    beside it. A member dropped from that union leaves the endpoint answering a body the generated
    client has no type for, and until 2026-09-05 the only thing that caught it was the committed
    document's bytes."""
    client = served(DATA_ROOT)
    answered = [
        client.get(
            UNDER_A_SCENARIO, params={"as_of": "2026-09-03"}, headers={"host": "evil.example"}
        ),
        client.get(
            UNDER_A_SCENARIO, params={"as_of": "2026-09-03", "scenario_id": "nothing-declares-this"}
        ),
    ]
    assert [response.status_code for response in answered] == [400, 400]
    tags = {response.json()["tag"] for response in answered}
    assert len(tags) == 2, "the two provocations returned one refusal, so this would pass vacuously"

    schema = json.loads(_served_document())["paths"][UNDER_A_SCENARIO]["get"]["responses"]["400"]
    declared = set(schema["content"]["application/json"]["schema"]["discriminator"]["mapping"])
    assert tags == declared
