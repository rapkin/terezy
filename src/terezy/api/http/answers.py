"""The answer, over declared questions only.

`api.answer.answer_question` raises `DeclarationError` for an id nothing declares, and the CLI
maps that to a different exit code from a refusal -- so reaching it for a well-formed question
about an id that does not exist would report a broken data root to a caller whose data root is
fine. The declared ids are checked here first, against the same category the list read serves
(020 FR-008, FR-042).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from terezy.api import answer as verb
from terezy.api.http import categories, envelopes

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from datetime import date


CATEGORY = "questions"


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
