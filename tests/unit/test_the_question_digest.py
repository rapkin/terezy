"""What identifies a question in the run manifest (029 FR-018, FR-021, SC-007).

A question a **file** declares is identified by its file's bytes, unchanged. One nothing
declares -- a request body, or `--set` lines -- is identified by a digest of its **validated
document**, because JSON spells two things TOML cannot and both spellings are one question.
"""

from __future__ import annotations

import copy
import tomllib
from datetime import date
from pathlib import Path
from typing import Any

from terezy.api.answer import answer_question
from terezy.core.primitives.currency import Currency
from terezy.data import manifest as run_manifest
from tests.data_roots import SHIPPED

QUESTION_FILE = SHIPPED / "questions" / "fifty-thousand.toml"
QUESTION_ID = "fifty-thousand-hryvnia"
AS_OF = date(2026, 9, 3)
BODY = Path("<request>")


def _document() -> dict[str, Any]:
    parsed: dict[str, Any] = tomllib.loads(QUESTION_FILE.read_text(encoding="utf-8"))
    return parsed


def test_two_questions_differing_in_one_horizon_digest_differently() -> None:
    moved = _document()
    moved["question"]["horizon"][0]["end"] = "2026-10-02"

    assert run_manifest.question_version(moved, BODY) != run_manifest.question_version(
        _document(), BODY
    )


def test_the_three_spellings_of_one_question_digest_identically() -> None:
    """An amount written as an integer and an optional field written as an explicit `null` are
    two things a TOML file cannot say and a JSON body can. Digesting what *arrived* would give
    one question three identities and put the command line out of reach of a posted answer."""
    stated = _document()
    as_an_integer = copy.deepcopy(stated)
    as_an_integer["question"]["amount"][0]["amount"] = 50000
    with_an_explicit_null = copy.deepcopy(stated)
    with_an_explicit_null["question"]["every_declared_instrument"] = None

    digests = {
        run_manifest.question_version(spelling, BODY)
        for spelling in (stated, as_an_integer, with_an_explicit_null)
    }
    assert len(digests) == 1


def test_a_file_declared_question_is_still_versioned_by_its_files_bytes() -> None:
    """Asserted over the **manifest's** inputs rather than over a golden: no golden renders a
    manifest input at all, so all of them stay green whatever this phase does to the versions."""
    run = answer_question(SHIPPED, QUESTION_ID, as_of=AS_OF, base_currency=Currency.UAH)

    questions = [ref for ref in run.manifest.inputs if ref.kind == "question"]
    assert [ref.id for ref in questions] == [QUESTION_ID]
    assert questions[0].version == run_manifest.file_version(QUESTION_FILE)
    assert questions[0].version != run_manifest.question_version(_document(), QUESTION_FILE)
