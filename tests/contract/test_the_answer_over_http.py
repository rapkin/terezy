"""The answer, over HTTP, is the answer the CLI prints — compared on the canonical digest.

The digest rather than two renderings agreeing: the claim is about the result, not about the
formatting of it (020 FR-042, FR-044, SC-018, SC-019).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from terezy.api import answer as verb
from terezy.api.http import document
from terezy.core.primitives.currency import Currency
from tests.http_client import served

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
AS_OF = "2026-09-03"
QUESTION = "fifty-thousand-hryvnia"


@pytest.fixture(scope="module")
def answered() -> dict[str, Any]:
    response = served(DATA_ROOT).get(
        f"{document.PREFIX}/questions/{QUESTION}/answer", params={"as_of": AS_OF}
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.mark.contract
def test_the_answer_matches_what_the_verb_returns(answered: dict[str, Any]) -> None:
    directly = verb.answer_question(
        DATA_ROOT, QUESTION, as_of=date.fromisoformat(AS_OF), base_currency=Currency.UAH
    )
    served_digest = answered["result"]["manifest"]["result_digest"]
    assert served_digest == directly.manifest.result_digest


@pytest.mark.contract
def test_every_answer_carries_its_manifest(answered: dict[str, Any]) -> None:
    """A result without a manifest is not a result (Principle III)."""
    held = answered["result"]["manifest"]
    assert held["tag"] == "manifest.RunManifest"
    assert held["as_of"] == AS_OF
    assert held["inputs"], "the manifest names what the run read"


@pytest.mark.contract
def test_the_answer_is_tagged_and_narrowable(answered: dict[str, Any]) -> None:
    answer = answered["result"]["answer"]
    assert answer["tag"].startswith("answer.")


@pytest.mark.contract
def test_a_question_nobody_declares_is_a_refusal_and_not_a_load_error() -> None:
    """The trap FR-008 names: `answer_question` raises for an unknown id, and that raise means
    a broken data root rather than a question about an id that does not exist."""
    response = served(DATA_ROOT).get(
        f"{document.PREFIX}/questions/nothing-declares-this/answer", params={"as_of": AS_OF}
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["tag"] == "envelopes.CategoryHasNoSuchId"
    assert result["declared_ids"] == [QUESTION]


@pytest.mark.contract
def test_as_of_is_required_on_the_answer() -> None:
    response = served(DATA_ROOT).get(f"{document.PREFIX}/questions/{QUESTION}/answer")
    assert response.status_code == 422
    assert "as_of" in response.text
