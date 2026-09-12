"""One question, two carriers: a TOML file's bytes and a JSON request body.

029 FR-001, SC-002. The claim the whole feature rests on is that the schema a file declares
survives a JSON round trip, so the loader that validates a file validates a body and there is
no second model. Asserted over the shipped question rather than over a fixture, because the
shipped one is the document 030's form will have to produce.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from terezy.data.declarations import loader
from tests.data_roots import SHIPPED

QUESTION_FILE = SHIPPED / "questions" / "fifty-thousand.toml"
BODY = Path("<request>")


def test_a_question_read_back_from_json_is_the_question_the_file_declares() -> None:
    document = tomllib.loads(QUESTION_FILE.read_text(encoding="utf-8"))
    over_the_wire = json.loads(json.dumps(document))

    assert loader.question_from_document(over_the_wire, BODY) == loader.question_from_file(
        QUESTION_FILE
    )


def test_nothing_in_the_document_needed_a_toml_type_to_carry_it() -> None:
    """The round trip above would also pass if `json.dumps` had *stringified* a date, so the
    document is compared to itself: a `datetime.date` in it would not survive as one."""
    document = tomllib.loads(QUESTION_FILE.read_text(encoding="utf-8"))

    assert json.loads(json.dumps(document)) == document
