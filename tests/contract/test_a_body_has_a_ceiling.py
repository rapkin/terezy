"""The two ceilings a request meets, and cannot move: the body's size and the candidate cap.

029 FR-024, FR-025, SC-009. The size cap is a service limit and lives here; the candidate
ceiling is a fact about the owner and stays declared under `data/candidates/`, so a body can
neither raise it, state one, nor opt out.

The third size case is what keeps the guard from refusing the whole surface: every read here is
a GET that legitimately declares no `Content-Length`, so a cap applied to *every* request would
refuse all of them wearing a message about a question document.
"""

from __future__ import annotations

import json
import re
import shutil
import tomllib
from pathlib import Path
from typing import Any

import pytest

from terezy.api.http import document, middleware
from tests.data_roots import SHIPPED
from tests.http_client import served

DATA_ROOT = SHIPPED
AS_OF = {"as_of": "2026-09-03"}
ANSWERS = f"{document.PREFIX}/answers"
QUESTION_FILE = SHIPPED / "questions" / "fifty-thousand.toml"


def _document() -> dict[str, Any]:
    parsed: dict[str, Any] = tomllib.loads(QUESTION_FILE.read_text(encoding="utf-8"))
    return parsed


@pytest.mark.contract
def test_the_shipped_question_is_far_inside_the_cap() -> None:
    """The cap is measured against the real thing, so a number chosen too low is red here rather
    than on the day somebody posts the question this repository ships."""
    canonical = json.dumps(_document(), sort_keys=True, ensure_ascii=False).encode("utf-8")

    assert len(canonical) * 10 < middleware.BODY_LIMIT


@pytest.mark.contract
def test_a_body_one_byte_over_the_cap_is_refused_with_the_cap_and_the_size_named() -> None:
    oversized = b"x" * (middleware.BODY_LIMIT + 1)

    response = served(DATA_ROOT).post(
        ANSWERS, params=AS_OF, content=oversized, headers={"content-type": "application/json"}
    )

    assert response.status_code == 413
    body = response.json()
    assert body["tag"] == "middleware.BodyTooLarge"
    assert body["limit_bytes"] == middleware.BODY_LIMIT
    assert body["declared_bytes"] == middleware.BODY_LIMIT + 1


@pytest.mark.contract
def test_a_body_exactly_at_the_cap_is_not_refused_by_it() -> None:
    """The boundary, so the cap cannot pass this file by refusing everything: a body at the
    limit reaches the loader and refuses there, as a fault in the **request**."""
    at_the_limit = b"x" * middleware.BODY_LIMIT

    response = served(DATA_ROOT).post(
        ANSWERS, params=AS_OF, content=at_the_limit, headers={"content-type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["tag"] == "envelopes.RequestMalformed"


@pytest.mark.contract
def test_a_body_that_declares_no_length_is_refused_rather_than_counted() -> None:
    """Streamed with no `Content-Length`, which is what a chunked request looks like from
    inside the process: refused, because counting the bytes as they arrive is the machinery the
    cap exists to avoid."""

    def chunked() -> Any:
        yield json.dumps(_document()).encode("utf-8")

    response = served(DATA_ROOT).post(
        ANSWERS, params=AS_OF, content=chunked(), headers={"content-type": "application/json"}
    )

    assert response.status_code == 411
    body = response.json()
    assert body["tag"] == "middleware.BodyLengthNotDeclared"
    assert body["method"] == "POST"


@pytest.mark.contract
def test_every_read_declares_no_length_and_is_untouched() -> None:
    """The case that would break the whole surface if the cap looked at every request."""
    client = served(DATA_ROOT)

    for path in ("/venues", "/questions", "/registry", "/openapi.json"):
        response = client.get(f"{document.PREFIX}{path}", params=AS_OF)
        assert response.status_code == 200, path


@pytest.mark.contract
def test_a_method_that_carries_no_body_is_left_to_the_route_table() -> None:
    """Found by review: skipping only GET, HEAD and OPTIONS answered a bodyless `DELETE` with
    *this request carries a body*, which the guard had not checked and could not. The route
    table's own refusal is the right one for a verb this surface does not serve."""
    response = served(DATA_ROOT).delete(f"{document.PREFIX}/venues", params=AS_OF)

    assert response.status_code != 411
    assert "BodyLengthNotDeclared" not in response.text


@pytest.mark.contract
def test_the_cap_is_declared_on_the_route_that_can_answer_with_it() -> None:
    """A refusal a client is not told about is one its generated types cannot narrow on."""
    published = json.loads(served(DATA_ROOT).get(f"{document.PREFIX}/openapi.json").text)["paths"][
        ANSWERS
    ]["post"]["responses"]

    assert set(published) >= {"411", "413"}


@pytest.mark.contract
def test_a_posted_question_meets_the_declared_candidate_ceiling(tmp_path: Path) -> None:
    """Exactly as the saved read meets it: same refusal, same numbers, same section (FR-025)."""
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    ceiling = root / "candidates" / "owner-001.toml"
    ceiling.write_text(
        re.sub(r"(?m)^max_candidates = \d+", "max_candidates = 1", ceiling.read_text("utf-8")),
        encoding="utf-8",
    )
    client = served(root)

    posted = client.post(ANSWERS, params=AS_OF, json=_document())
    saved = client.get(f"{document.PREFIX}/questions/fifty-thousand-hryvnia/answer", params=AS_OF)

    assert (posted.status_code, saved.status_code) == (200, 200)
    assert posted.json()["result"]["answer"] == saved.json()["result"]["answer"]
    assert "candidates.CeilingExceeded" in posted.text


@pytest.mark.contract
def test_the_request_schema_names_no_ceiling_for_a_caller_to_state() -> None:
    """The other half of FR-025: how far the owner will let a search run is not a request
    parameter, so there is no field in the published body for one."""
    published = json.dumps(
        json.loads(served(DATA_ROOT).get(f"{document.PREFIX}/openapi.json").text)["paths"][ANSWERS]
    )

    assert "max_candidates" not in published
    assert "ceiling" not in published
