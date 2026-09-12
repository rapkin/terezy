"""A fault in a posted question refuses exactly as the same fault in a file does.

029 FR-003, FR-012, FR-029, SC-004, SC-006, SC-013. One record, one tag and the loader's own
four fields whichever carried the question; what separates them is the artefact the refusal
names and therefore the status, because a fault in the body reported as a broken data root
sends a caller to fix a file that is fine.

Each body fault is provoked **against the same fault planted in the file**, so the claim is that
the two agree rather than that the body produces some refusal.
"""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path
from typing import Any

import pytest

from terezy.api.http import document
from tests.data_roots import SHIPPED
from tests.http_client import served

DATA_ROOT = SHIPPED
AS_OF = "2026-09-03"
QUESTION = "fifty-thousand-hryvnia"
QUESTION_FILE = SHIPPED / "questions" / "fifty-thousand.toml"
ANSWERS = f"{document.PREFIX}/answers"
DECLARATION_FAILED = "envelopes.DeclarationFailed"


def _document() -> dict[str, Any]:
    parsed: dict[str, Any] = tomllib.loads(QUESTION_FILE.read_text(encoding="utf-8"))
    return parsed


def _posted(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    response = served(DATA_ROOT).post(ANSWERS, params={"as_of": AS_OF}, json=body)
    return response.status_code, response.json()


def _in_a_file(tmp_path: Path, rendered: str) -> tuple[int, dict[str, Any]]:
    """The same fault planted in the declaring file, read through the saved-question route.

    The file is rewritten from the TOML the fault is described in rather than patched, so the
    two sides are provoked by one description of one mistake.
    """
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    (root / "questions" / "fifty-thousand.toml").write_text(rendered, encoding="utf-8")
    response = served(root).get(
        f"{document.PREFIX}/questions/{QUESTION}/answer", params={"as_of": AS_OF}
    )
    return response.status_code, response.json()


def _without_objectives() -> tuple[dict[str, Any], str]:
    body = _document()
    del body["question"]["objectives"]
    return body, QUESTION_FILE.read_text(encoding="utf-8").replace(
        'objectives   = "money-and-when"', "", 1
    )


@pytest.mark.contract
def test_a_missing_table_refuses_with_the_tag_and_field_a_file_refuses_with(
    tmp_path: Path,
) -> None:
    body, rendered = _without_objectives()
    posted_status, posted = _posted(body)
    file_status, in_a_file = _in_a_file(tmp_path, rendered)

    assert posted["tag"] == in_a_file["tag"] == DECLARATION_FAILED
    assert posted["field_path"] == in_a_file["field_path"] == "question.objectives"
    assert posted["remedy"] == in_a_file["remedy"]
    assert (posted_status, file_status) == (400, 500)


@pytest.mark.contract
def test_the_body_is_blamed_and_the_data_root_is_not(tmp_path: Path) -> None:
    """Both cases in one test, so neither passes by answering everything one way (SC-005)."""
    body, _ = _without_objectives()
    _, posted = _posted(body)

    broken = tmp_path / "data"
    shutil.copytree(DATA_ROOT, broken)
    (broken / "venues.toml").write_text("[[venue]]\nid = 1\n", encoding="utf-8")
    from_a_broken_root = served(broken).post(ANSWERS, params={"as_of": AS_OF}, json=_document())

    assert posted["file"] == "<request>"
    assert from_a_broken_root.status_code == 500
    assert from_a_broken_root.json()["file"].endswith("venues.toml")


@pytest.mark.contract
def test_an_unrecognised_field_is_named_rather_than_ignored() -> None:
    body = _document()
    body["question"]["invented_field"] = "whatever"

    status, refused = _posted(body)

    assert (status, refused["tag"]) == (400, DECLARATION_FAILED)
    assert "invented_field" in refused["field_path"] + refused["problem"]


@pytest.mark.contract
def test_an_owner_no_stream_belongs_to_refuses(tmp_path: Path) -> None:
    body = _document()
    body["owner"]["id"] = "owner-nobody"
    rendered = QUESTION_FILE.read_text(encoding="utf-8").replace(
        'id = "owner-001"', 'id = "owner-nobody"', 1
    )

    posted_status, posted = _posted(body)
    _, in_a_file = _in_a_file(tmp_path, rendered)

    assert (posted_status, posted["tag"]) == (400, DECLARATION_FAILED)
    assert posted["field_path"] == in_a_file["field_path"] == "owner.id"
    assert posted["file"] == "<request>"


@pytest.mark.contract
def test_an_undeclared_stream_names_the_field_and_blames_the_request() -> None:
    """The owner's answer of 2026-09-13: one shape for every body mistake, never a 200 whose
    body is a different record. `AmountForAnUndeclaredStream` and `StreamWithNoAmount` stay the
    form the **verb** returns to a caller holding a record it built itself."""
    body = _document()
    body["question"]["amount"][0]["stream"] = "nothing-declares-this"

    status, refused = _posted(body)

    assert (status, refused["tag"]) == (400, DECLARATION_FAILED)
    assert refused["field_path"] == "question.amount.stream"
    assert refused["file"] == "<request>"


@pytest.mark.contract
def test_neither_unreachable_union_member_reaches_this_surface() -> None:
    """The other half of the owner's answer, asserted over what the body actually carries: a
    200 carrying one of those two records is what option B would have produced."""
    body = _document()
    body["question"]["amount"][0]["stream"] = "nothing-declares-this"
    _, refused = _posted(body)

    assert "AmountForAnUndeclaredStream" not in str(refused)
    assert "StreamWithNoAmount" not in str(refused)


@pytest.mark.contract
def test_a_body_that_is_not_json_is_the_frameworks_own_malformed_refusal() -> None:
    """Bytes that will not parse carry no question to validate, so they refuse the way a
    malformed parameter does -- the division a file already gets from `tomllib`."""
    response = served(DATA_ROOT).post(
        ANSWERS,
        params={"as_of": AS_OF},
        content=b"not json at all {{{",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["tag"] == "envelopes.RequestMalformed"
    assert [held["location"] for held in response.json()["parameters"]] == [["body"]]


@pytest.mark.contract
def test_a_body_that_is_json_but_not_an_object_refuses_the_same_way() -> None:
    response = served(DATA_ROOT).post(ANSWERS, params={"as_of": AS_OF}, json=[1, 2, 3])

    assert response.status_code == 422
    assert response.json()["tag"] == "envelopes.RequestMalformed"


@pytest.mark.contract
def test_as_of_is_required_on_the_posted_answer() -> None:
    """FR-004: the one field a digest would make a lie, kept off the body and off any default."""
    response = served(DATA_ROOT).post(ANSWERS, json=_document())

    assert response.status_code == 422
    assert [held["location"] for held in response.json()["parameters"]] == [["query", "as_of"]]
