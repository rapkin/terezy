"""One evaluated candidate's projection, addressed by the key its answer published.

Orchestration, on ``api.answer``'s rule: the core's ``decision.card.projection_for`` is a pure
function of records, and this is the layer that reads files and records what the run rested on.

The question is **answered** first, which is what resolves the key to the tuple and the horizon
it names and what proves the key is one this answer produced rather than a string a client made
up. Answering is deterministic at a given ``as_of``, so the projection served is the projection
that produced the figure the reader is looking at.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from terezy.api.answer import declared_question, run
from terezy.core.decision.card import NoSuchCandidate, projection_for
from terezy.core.results.answer import Answer
from terezy.data import manifest as run_manifest

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from datetime import date
    from pathlib import Path

    from terezy.core.primitives.currency import Currency
    from terezy.core.results.card import CandidateProjection
    from terezy.data.manifest import RunManifest


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectedCandidate:
    """One candidate's projection and the manifest of the run that produced it.

    The manifest for ``AnsweredQuestion``'s reason: Principle III's *a result without a manifest
    is not a result* applies to this read as much as to the answer, and a card whose flows could
    not be traced to a data version is the untraceable figure the card exists to prevent.
    """

    projection: CandidateProjection
    manifest: RunManifest


def projection_for_candidate(
    root: Path,
    question_id: str,
    candidate_key: str,
    *,
    as_of: date,
    base_currency: Currency,
) -> ProjectedCandidate | NoSuchCandidate:
    """One declared question's candidate, or the typed refusal naming the keys it published."""
    question, path = declared_question(root, question_id)
    declarations, inputs, result = run(
        question, root, as_of=as_of, base_currency=base_currency, declared_in=path
    )
    if not isinstance(result, Answer):
        return NoSuchCandidate(
            wanted_key=candidate_key,
            evaluated_keys=(),
            reason=(
                f"{question_id!r} was not answered as of {as_of.isoformat()}, so it evaluated no "
                f"candidate and published no key: {type(result).__name__}. The remedy is the "
                "answer's, not this read's."
            ),
        )
    found = projection_for(candidate_key, result, inputs, as_of)
    if isinstance(found, NoSuchCandidate):
        return found
    return ProjectedCandidate(
        projection=found,
        manifest=run_manifest.of_answer(
            declarations=declarations,
            question=question,
            declared_in=path,
            question_version=None,
            as_of=as_of,
            result=result,
            refusal=None,
        ),
    )
