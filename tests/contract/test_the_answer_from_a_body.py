"""A whole question in the request body, answered exactly as the saved one is.

029 SC-001, SC-008, and the two boundary properties that would otherwise be claimed rather than
checked: the posted answer is the *same value* the saved read returns, and the manifest says
which question it answered by digest rather than by a path on the serving machine.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

from terezy.api.http import document
from tests.data_roots import SHIPPED
from tests.http_client import served

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = SHIPPED
AS_OF = "2026-09-03"
QUESTION = "fifty-thousand-hryvnia"
QUESTION_FILE = SHIPPED / "questions" / "fifty-thousand.toml"
ANSWERS = f"{document.PREFIX}/answers"
DECLARED_SUBJECT = "answer.DeclaredSubject"


def _document() -> dict[str, Any]:
    parsed: dict[str, Any] = tomllib.loads(QUESTION_FILE.read_text(encoding="utf-8"))
    return parsed


def _posted(body: dict[str, Any]) -> Any:
    return served(DATA_ROOT).post(ANSWERS, params={"as_of": AS_OF}, json=body)


@pytest.fixture(scope="module")
def both() -> tuple[dict[str, Any], dict[str, Any]]:
    """The posted answer and the saved read of the same question, at the same `as_of`."""
    posted = _posted(_document())
    assert posted.status_code == 200, posted.text
    saved = served(DATA_ROOT).get(
        f"{document.PREFIX}/questions/{QUESTION}/answer", params={"as_of": AS_OF}
    )
    assert saved.status_code == 200, saved.text
    return posted.json()["result"], saved.json()["result"]


@pytest.mark.contract
def test_the_posted_answer_is_the_answer_the_saved_read_returns(
    both: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    posted, saved = both
    assert posted["answer"] == saved["answer"]
    assert posted["manifest"]["result_digest"] == saved["manifest"]["result_digest"]


@pytest.mark.contract
def test_the_manifest_carries_exactly_one_added_input(
    both: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    """An *added* input rather than a differing one: every declared question file is recorded
    whichever question was answered, so the file's own reference survives the post."""
    posted, saved = both
    added = [ref for ref in posted["manifest"]["inputs"] if ref not in saved["manifest"]["inputs"]]
    dropped = [
        ref for ref in saved["manifest"]["inputs"] if ref not in posted["manifest"]["inputs"]
    ]

    assert dropped == []
    assert [(ref["kind"], ref["id"], ref["file"]) for ref in added] == [
        ("question", QUESTION, "<request>")
    ]
    assert added[0]["version"].startswith("sha256:")


@pytest.mark.contract
def test_the_manifest_names_no_path_on_the_serving_machine(
    both: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    """The data root is a temporary directory per run, so a manifest that leaked one would be
    a manifest two machines could not compare -- and there is no file behind it to go and read."""
    posted, _ = both
    assert str(DATA_ROOT) not in json.dumps(posted["manifest"])


@pytest.mark.contract
def test_a_body_with_one_horizon_moved_is_answered_as_that_question(
    both: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    """And nothing under `data/` is consulted for it: the file still declares the old window."""
    posted, _ = both
    moved = _document()
    moved["question"]["horizon"][0]["end"] = "2026-10-15"

    answered = _posted(moved)
    assert answered.status_code == 200, answered.text
    result = answered.json()["result"]
    assert result["manifest"]["result_digest"] != posted["manifest"]["result_digest"]
    assert QUESTION_FILE.read_text(encoding="utf-8").count("2026-10-15") == 0


@pytest.mark.contract
def test_a_posted_subject_list_resolves_exactly_as_the_files_does(
    both: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    """Group labels mean over a body what they mean in a file -- `btc` is **held**, not
    undeclared, and the counts are the saved read's (029 FR-017)."""
    posted, saved = both
    assert posted["answer"]["subjects"] == saved["answer"]["subjects"]
    assert not [held for held in posted["answer"]["subjects"] if held["tag"] != DECLARED_SUBJECT]


@pytest.mark.contract
def test_a_subject_nothing_declares_reaches_the_undeclared_population() -> None:
    """The shipped question leaves that population empty, so a word nothing declares is the
    only way to reach it at all."""
    asked = _document()
    asked["question"]["subjects"] = [*asked["question"]["subjects"], "nothing-declares-this"]

    answered = _posted(asked)
    assert answered.status_code == 200, answered.text
    subjects = answered.json()["result"]["answer"]["subjects"]
    undeclared = [held for held in subjects if held["tag"] == "answer.UndeclaredSubject"]
    assert [held["named"] for held in undeclared] == ["nothing-declares-this"]


@pytest.mark.contract
def test_a_plan_for_nothing_arrives_in_a_200_with_the_shape_an_answer_has() -> None:
    """The answer's own `Refused` union reaches a posting caller exactly as it reaches a saved
    one: a refusal is a **result**, and nothing about a request changes that (029 FR-016)."""
    asked = _document()
    asked["question"]["plan"] = [
        *asked["question"]["plan"],
        {"subject": "nothing-declares-this", "kind": "cash"},
    ]

    answered = _posted(asked)
    assert answered.status_code == 200, answered.text
    result = answered.json()["result"]
    assert result["answer"]["tag"] == "answer.PlanForNothing"
    assert result["answer"]["named"] == "nothing-declares-this"
    assert result["manifest"]["tag"] == "manifest.RunManifest"


def _tagged(node: object, tag: str) -> list[dict[str, Any]]:
    """Every record with that tag anywhere in a served body, at whatever depth."""
    if isinstance(node, dict):
        found = [held for value in node.values() for held in _tagged(value, tag)]
        return [node, *found] if node.get("tag") == tag else found
    if isinstance(node, list):
        return [held for value in node for held in _tagged(value, tag)]
    return []


@pytest.mark.contract
def test_every_figure_in_a_posted_answer_keeps_its_mark(
    both: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    """No figure gains or loses a mark because the question arrived in a body (029 FR-023)."""
    posted, saved = both
    money = _tagged(posted["answer"], "money.Money")

    assert money, "no money reached the posted answer, so this would pass vacuously"
    assert not [held for held in money if "provenance" not in held]
    assert posted["manifest"]["unverified_sources"] == saved["manifest"]["unverified_sources"]
    assert posted["manifest"]["unverified_sources"], "every shipped source is unverified today"


PROGRAM = """
import sys, tomllib
from pathlib import Path
sys.path.insert(0, "src")
from tests.http_client import served
from terezy.api.http import document

root = Path("data")
body = tomllib.loads((root / "questions" / "fifty-thousand.toml").read_text(encoding="utf-8"))
response = served(root).post(
    f"{document.PREFIX}/answers", params={"as_of": "2026-09-03"}, json=body
)
sys.stdout.buffer.write(response.content)
"""


def _posted_under(seed: str) -> bytes:
    return subprocess.run(
        [sys.executable, "-c", PROGRAM],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONHASHSEED": seed},
        capture_output=True,
        check=True,
    ).stdout


@pytest.mark.contract
@pytest.mark.slow
def test_two_processes_with_different_hash_seeds_post_the_same_answer() -> None:
    """Within one process a `frozenset` iterates stably, so nothing smaller than two processes
    can see a manifest or a digest that followed a set's iteration order (029 FR-022)."""
    assert _posted_under("0") == _posted_under("1")


@pytest.mark.contract
def test_two_spellings_of_one_amount_carry_one_identity() -> None:
    """The digest is of the validated record, so a body that writes 50000 where the file writes
    50000.0 is the same question with the same version -- which is what puts a posted answer
    within reach of the command line (029 FR-018)."""
    as_an_integer = copy.deepcopy(_document())
    as_an_integer["question"]["amount"][0]["amount"] = 50000

    versions = {
        ref["version"]
        for body in (_document(), as_an_integer)
        for ref in _posted(body).json()["result"]["manifest"]["inputs"]
        if ref["file"] == "<request>"
    }
    assert len(versions) == 1
