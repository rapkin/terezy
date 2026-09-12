"""The answer: one for a declared question id, one for a whole question in a request body.

`api.answer.answer_question` raises `DeclarationError` for an id nothing declares, and the CLI
maps that to a different exit code from a refusal -- so reaching it for a well-formed question
about an id that does not exist would report a broken data root to a caller whose data root is
fine. The declared ids are checked here first, against the same category the list read serves
(020 FR-008, FR-042).

A posted question goes through the loader that validates a **file**'s document, so there is one
validator, one schema and one set of refusals whichever carried it (029 FR-001). The framework
is deliberately not given the body to validate: a shape fault would then arrive as
`RequestMalformed`, with no field path and no remedy, under a different tag from the one the
same fault in a file produces.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from fastapi.exceptions import RequestValidationError

from terezy.api import answer as verb
from terezy.api.http import categories, envelopes
from terezy.data.declarations import schema

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from datetime import date


CATEGORY = "questions"

REQUEST = Path("<request>")
"""What a question carried by a request body is named by when it refuses, and in the manifest.

Not a real path and shaped so a reader cannot mistake it for one, on `cli.main.FLAGS`'s rule: a
refusal still has to say *where*, an absolute path on the serving machine is a fact about that
machine, and there is no file to go and look at (029 FR-014).
"""

DEFS_PREFIX: Final = "#/$defs/"
"""How pydantic points at a nested model of its own, before :func:`_self_contained` removes it."""


def _self_contained(schema_node: Any, defs: Mapping[str, Any]) -> Any:
    """One JSON Schema with every ``#/$defs/`` reference substituted in place.

    A ``$ref`` in an OpenAPI document resolves from the **document root**, and a schema spliced
    into a path takes its ``$defs`` table with it -- so every one of pydantic's internal
    references points at a root ``$defs`` that does not exist, and a client generator refuses the
    whole document rather than just this route.

    Substituted rather than hoisted into ``components/schemas``, which this application fills
    from its own records: ``OwnerTable`` and six ``Question*Table`` names would join a namespace
    that already holds ``question_Question`` and ``candidates_Question``, and a collision there
    overwrites a response model silently.
    """
    if isinstance(schema_node, dict):
        named = schema_node.get("$ref")
        if isinstance(named, str) and named.startswith(DEFS_PREFIX):
            return _self_contained(defs[named.removeprefix(DEFS_PREFIX)], defs)
        return {key: _self_contained(value, defs) for key, value in schema_node.items()}
    if isinstance(schema_node, list):
        return [_self_contained(value, defs) for value in schema_node]
    return schema_node


def _published_schema() -> dict[str, Any]:
    generated = schema.QuestionFile.model_json_schema()
    inlined: dict[str, Any] = _self_contained(generated, generated.pop("$defs", {}))
    return inlined


REQUEST_BODY: Final[dict[str, Any]] = {
    "required": True,
    "content": {"application/json": {"schema": _published_schema()}},
}
"""The published request schema, generated from the model the loader validates against.

Written out by hand it would be the second question model FR-001 forbids, and it would drift
silently the first time a field was added to the file's schema.
"""


def declared_ids(ask: categories.Ask) -> tuple[str, ...]:
    """The question ids this data root declares, from the same category the list read serves."""
    category = categories.BY_ID[CATEGORY]
    assert isinstance(category.shape, categories.Keyed)
    return tuple(sorted(category.shape.resolve(ask).records))


def no_such_question(question_id: str, declared: tuple[str, ...]) -> envelopes.CategoryHasNoSuchId:
    """The typed refusal for an id nothing declares. One wording, for both reads."""
    return envelopes.CategoryHasNoSuchId(
        category=CATEGORY,
        wanted_id=question_id,
        declared_ids=declared,
        reason=(
            f"no question with the id {question_id!r} is declared. This is a question about "
            "an id that does not exist, not a broken data root."
        ),
    )


def answered(
    ask: categories.Ask, question_id: str, *, as_of: date
) -> verb.AnsweredQuestion | envelopes.CategoryHasNoSuchId:
    """One declared question's answer and its manifest, or the typed refusal for an unknown id."""
    declared = declared_ids(ask)
    if question_id not in declared:
        return no_such_question(question_id, declared)
    return verb.answer_question(
        ask.root,
        question_id,
        as_of=as_of,
        base_currency=ask.base_currency,
    )


def answered_from(ask: categories.Ask, body: bytes, *, as_of: date) -> verb.AnsweredQuestion:
    """One posted question's answer and its manifest. Nothing is written and nothing is saved."""
    return verb.answer_document(
        document_of(body),
        ask.root,
        as_of=as_of,
        base_currency=ask.base_currency,
        declared_in=REQUEST,
    )


def document_of(body: bytes) -> dict[str, Any]:
    """The request's bytes as the document a question file holds, or the framework's own refusal.

    Bytes that are not a JSON object carry no question to validate, so they refuse the way a
    malformed request parameter does rather than as a malformed declaration -- the distinction
    the CLI already keeps between a file `tomllib` would not parse and a document the loader
    refuses.
    """
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as malformed:
        raise _not_a_document(f"the body is not JSON: {malformed}") from malformed
    if not isinstance(parsed, dict):
        raise _not_a_document(
            "the body is JSON but not an object, so it carries no [owner] and no [question] "
            f"table: it is a {type(parsed).__name__}."
        )
    document: dict[str, Any] = parsed
    return document


def _not_a_document(problem: str) -> RequestValidationError:
    """The framework's own parameter refusal, located at the body and echoing none of it back."""
    return RequestValidationError([{"loc": ("body",), "input": None, "msg": problem}])
