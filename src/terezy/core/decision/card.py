"""Resolving one published candidate key back to the projection that produced its figures.

The answer pipeline discards every projection it builds, so re-answering cannot by itself hand
one back. What this does instead is resolve the key against the answer -- which is also what
proves the key is one *this* answer published rather than a string a client made up -- and then
call ``evaluate`` for that one candidate, keeping the half ``compare`` throws away. Answering is
deterministic at a given ``as_of``, so the projection served is the projection that produced the
figure the reader is looking at; ``tests/contract/test_the_card_accounts_for_what_came_back.py``
asserts that rather than assuming it.

**Not a cache.** A cache would be state in a layer whose whole claim is that it computes nothing,
and the constitution's cache rule is about provenance rather than about saving a repeat. If the
cost stops being affordable the remedy is a narrower server-side read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from terezy.core.decision.candidates import evaluated
from terezy.core.decision.tuple_outcome import Evaluated, evaluate
from terezy.core.results.answer import Answer, HorizonSection
from terezy.core.results.candidates import CandidateSurvey

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from datetime import date

    from terezy.core.decision.answer import AnswerInputs
    from terezy.core.results.card import CandidateProjection
    from terezy.core.results.tuple import TupleOutcome


@dataclass(frozen=True, slots=True)
class NoSuchCandidate:
    """The key names no evaluated candidate of this answer.

    Distinct from *the question is not declared*, which is the other refusal this read has,
    because the remedies differ: a wrong URL against a client holding a key from an answer this
    one no longer matches. There is deliberately no third -- a candidate whose projection could
    not be produced never becomes an outcome, so it carries no key and has no address here.
    """

    wanted_key: str
    evaluated_keys: tuple[str, ...]
    reason: str


def projection_for(
    wanted: str,
    answer: Answer,
    inputs: AnswerInputs,
    as_of: date,
) -> CandidateProjection | NoSuchCandidate:
    """One evaluated candidate's projection, or the typed refusal naming what was published."""
    published = tuple(
        (section, outcome) for section in answer.sections for outcome in _outcomes_of(section)
    )
    keys = tuple(outcome.projection_key for _, outcome in published)
    for section, outcome in published:
        if outcome.projection_key != wanted:
            continue
        result = evaluate(
            outcome.key,
            amount=answer.question.amounts[outcome.key.stream_id],
            horizon=section.horizon,
            as_of=as_of,
            continuation=answer.question.continuation,
            registries=inputs.registries,
        )
        if isinstance(result, Evaluated):
            return result.projection
        # Unreachable while answering is deterministic: this candidate produced an outcome in
        # the answer above, from the same registries at the same `as_of`. Reported rather than
        # raised because the one way to reach it is a registry that changed under the read.
        return NoSuchCandidate(
            wanted_key=wanted,
            evaluated_keys=keys,
            reason=(
                f"{wanted!r} named a candidate this answer evaluated, and re-evaluating it "
                f"refused: {result.reason} The answer and this read saw different declarations."
            ),
        )
    return NoSuchCandidate(
        wanted_key=wanted,
        evaluated_keys=keys,
        reason=(
            f"no candidate of this answer is addressed by {wanted!r}. A key is published on "
            "each evaluated outcome and echoed back; one that matches none of them is a client "
            "holding a key from another answer, or another date, or another question."
        ),
    )


def _outcomes_of(section: HorizonSection) -> tuple[TupleOutcome, ...]:
    """Every candidate this section evaluated, ranked or not.

    Read out of the comparison through 014's own accessor, so there is no second opinion here
    about which candidates were evaluated -- and so a candidate the front withheld still has an
    address, which is the reader who most needs the reason for a figure he was not shown.
    """
    survey = section.outcome
    return evaluated(survey.comparison) if isinstance(survey, CandidateSurvey) else ()
