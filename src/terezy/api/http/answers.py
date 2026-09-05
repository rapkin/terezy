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


def answered(
    ask: categories.Ask, question_id: str, *, as_of: date
) -> verb.AnsweredQuestion | envelopes.CategoryHasNoSuchId:
    """One declared question's answer and its manifest, or the typed refusal for an unknown id."""
    category = categories.BY_ID["questions"]
    assert isinstance(category.shape, categories.Keyed)
    declared = category.shape.resolve(ask).records
    if question_id not in declared:
        return envelopes.CategoryHasNoSuchId(
            category=category.id,
            wanted_id=question_id,
            declared_ids=tuple(sorted(declared)),
            reason=(
                f"no question with the id {question_id!r} is declared. This is a question about "
                "an id that does not exist, not a broken data root."
            ),
        )
    return verb.answer_question(
        ask.root,
        question_id,
        as_of=as_of,
        base_currency=ask.base_currency,
    )
