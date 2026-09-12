"""A question typed on the command line appears in the manifest it produced (029 FR-019, FR-020).

The record before this feature was that a question with no file contributed no input reference
at all, so a run recorded every file it read and not the question it answered. One question
asked two ways now carries one identity, which is what lets a posted answer be re-derived on a
command line.
"""

from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path
from typing import Any

from terezy.cli import main as cli
from terezy.data import manifest as run_manifest
from tests.data_roots import SHIPPED

QUESTION_FILE = SHIPPED / "questions" / "fifty-thousand.toml"
QUESTION_ID = "fifty-thousand-hryvnia"
AS_OF = date(2026, 9, 3)
BODY = Path("<request>")


def _document() -> dict[str, Any]:
    parsed: dict[str, Any] = tomllib.loads(QUESTION_FILE.read_text(encoding="utf-8"))
    return parsed


def test_the_flags_path_records_the_question_it_answered() -> None:
    run = cli._from_flags(SHIPPED, [QUESTION_FILE.read_text(encoding="utf-8")], as_of=AS_OF)

    from_flags = [
        ref for ref in run.manifest.inputs if ref.kind == "question" and ref.file == cli.FLAGS.name
    ]
    assert [ref.id for ref in from_flags] == [QUESTION_ID]
    assert from_flags[0].version == run_manifest.question_version(_document(), cli.FLAGS)


def test_the_digest_does_not_depend_on_what_carried_the_document() -> None:
    """FR-020's whole content: a request body and `--set` lines digest one question the same, so
    the sentinel a refusal names cannot leak into the identity."""
    assert run_manifest.question_version(_document(), BODY) == run_manifest.question_version(
        _document(), cli.FLAGS
    )


def test_the_file_that_declares_the_same_question_is_recorded_beside_it() -> None:
    """The file's reference survives: every declared question file is recorded whichever was
    answered, so the flags run adds one input rather than replacing one."""
    run = cli._from_flags(SHIPPED, [QUESTION_FILE.read_text(encoding="utf-8")], as_of=AS_OF)

    questions = [ref for ref in run.manifest.inputs if ref.kind == "question"]
    assert sorted(ref.file for ref in questions) == ["<flags>", "questions/fifty-thousand.toml"]
