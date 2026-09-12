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
import typing
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from terezy.api.http import document
from terezy.data.declarations import schema
from tests.data_roots import SHIPPED
from tests.http_client import served

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "scripts" / "generate_openapi.py"
DATA_ROOT = SHIPPED


def _served_document() -> bytes:
    """Bytes throughout, for two reasons. The document carries a non-ASCII character, so a text
    hop would encode it with the locale's codec; and text mode translates newlines, which would
    leave a generator writing CRLF against an endpoint serving LF and both assertions below
    green."""
    response = served(DATA_ROOT).get(f"{document.PREFIX}/openapi.json")
    assert response.status_code == 200
    return response.content


def _generated(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, str(GENERATOR), *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )


@pytest.mark.contract
def test_the_endpoint_serves_what_the_generator_writes(tmp_path: Path) -> None:
    """Both sides render one document; what this pins is that they render it the same *way*. The
    framework's JSON response writes compact separators and no trailing newline, so a client
    generated from the generator's bytes and fetching the endpoint's would find they disagree."""
    written = tmp_path / "openapi.json"
    _generated("--out", str(written))
    assert written.read_bytes() == _served_document()


@pytest.mark.contract
def test_the_generator_writes_to_stdout_by_default() -> None:
    """A build pipes it; naming a path is the exception, not the interface."""
    assert _generated().stdout == _served_document()


@pytest.mark.contract
def test_the_document_is_canonical() -> None:
    """Sorted keys, two-space indent, a trailing newline -- reproducible bytes, per FR-039."""
    body = _served_document().decode("utf-8")
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


@pytest.mark.contract
def test_every_reference_in_the_served_document_resolves() -> None:
    """A `$ref` resolves from the **document root**, so a schema that brought its own `$defs`
    table into a path points at a table that is not there -- and a client generator refuses the
    whole document, not just that route. Found by review on the branch that added the first
    hand-published schema; asserted over every reference rather than that one, because the next
    hand-published schema will make the same mistake in a different place."""
    served_document = json.loads(_served_document())
    references = _references(served_document, "")

    assert len(references) > 100, "the walk found suspiciously little to check"
    dangling = [ref for _, ref in references if not _resolves(served_document, ref)]
    assert not dangling, f"{len(dangling)} reference(s) resolve to nothing: {sorted(set(dangling))}"


def _references(node: Any, path: str) -> list[tuple[str, str]]:
    if isinstance(node, dict):
        return [
            (path, value) if key == "$ref" and isinstance(value, str) else held
            for key, value in node.items()
            for held in ([(path, value)] if key == "$ref" else _references(value, f"{path}/{key}"))
        ]
    if isinstance(node, list):
        return [
            held
            for index, value in enumerate(node)
            for held in _references(value, f"{path}/{index}")
        ]
    return []


def _resolves(served_document: dict[str, Any], reference: str) -> bool:
    """Whether a JSON pointer names something in this document. Local references only: an
    external one on this surface would be a second document nobody serves."""
    if not reference.startswith("#/"):
        return False
    node: Any = served_document
    for part in reference[2:].split("/"):
        unescaped = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or unescaped not in node:
            return False
        node = node[unescaped]
    return True


@pytest.mark.contract
def test_the_document_publishes_the_question_a_body_may_carry() -> None:
    """029 FR-028. Generated from the model the loader validates against, so a client is
    generated from the same schema a file is checked by: every field the question schema names,
    at every depth, is a property of the published body, and a hand-written copy that drifted
    would be short of one."""
    served_document = json.loads(_served_document())
    posted = served_document["paths"][f"{document.PREFIX}/answers"]["post"]
    published = posted["requestBody"]["content"]["application/json"]["schema"]

    assert posted["requestBody"]["required"] is True
    assert set(published["required"]) == set(schema.QuestionFile.model_fields)
    assert _properties(published) == _model_fields(schema.QuestionFile)


def _properties(node: Any) -> set[str]:
    """Every property name the published schema declares, at whatever depth."""
    if isinstance(node, dict):
        named = (
            set(node.get("properties", {})) if isinstance(node.get("properties"), dict) else set()
        )
        return named.union(*(_properties(value) for value in node.values()), set())
    if isinstance(node, list):
        return set().union(*(_properties(value) for value in node), set())
    return set()


def _model_fields(model: type[BaseModel]) -> set[str]:
    """Every field name the model declares, at whatever depth, walked off the model itself."""
    names: set[str] = set()
    for name, field in model.model_fields.items():
        names.add(name)
        for argument in (field.annotation, *typing.get_args(field.annotation)):
            for nested in (argument, *typing.get_args(argument)):
                if isinstance(nested, type) and issubclass(nested, BaseModel):
                    names |= _model_fields(nested)
    return names


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
