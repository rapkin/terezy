"""Every evaluated candidate of the owner's declared question, beside its served projection.

Not a test module -- ``pytest`` collects only ``test_*.py``, so this file is imported, never run.

Built through the same path the endpoint takes: answer the question, then resolve each published
key back through ``decision.card.projection_for``. A suite that reached into ``evaluate``
directly would assert about a projection no reader can obtain.

Cached because one answer over the shipped root is the same answer every time, and re-answering
per assertion is what made the first draft of the key suite take 33 seconds.
"""

from __future__ import annotations

from datetime import date
from functools import cache
from typing import TYPE_CHECKING, Final

from terezy.api.answer import answer_question, inputs_of
from terezy.core.decision.candidates import evaluated
from terezy.core.decision.card import projection_for
from terezy.core.primitives.currency import Currency
from terezy.core.results.answer import Answer
from terezy.core.results.candidates import CandidateSurvey
from terezy.core.results.card import CandidateProjection
from terezy.data.declarations import resolver
from tests.data_roots import SHIPPED

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from terezy.core.instruments.interface import DateRange
    from terezy.core.results.tuple import TupleOutcome

QUESTION: Final = "fifty-thousand-hryvnia"
"""The owner's own declared question -- the one the answer screen renders."""

AS_OF: Final = date(2026, 9, 6)


@cache
def answered() -> Answer:
    result = answer_question(SHIPPED, QUESTION, as_of=AS_OF, base_currency=Currency.UAH)
    assert isinstance(result.answer, Answer), result.answer
    return result.answer


@cache
def published_keys() -> tuple[str, ...]:
    """Every key the shipped question publishes, in section then ranking order."""
    return tuple(outcome.projection_key for outcome, _ in evaluated_outcomes())


@cache
def evaluated_outcomes() -> tuple[tuple[TupleOutcome, DateRange], ...]:
    """Each evaluated candidate and the horizon of the section it was evaluated in."""
    return tuple(
        (outcome, section.horizon)
        for section in answered().sections
        if isinstance(section.outcome, CandidateSurvey)
        for outcome in evaluated(section.outcome.comparison)
    )


@cache
def served() -> tuple[tuple[TupleOutcome, CandidateProjection], ...]:
    """Each evaluated candidate and the projection its published key resolves to."""
    answer = answered()
    declarations = resolver.answer_from_data_root(
        SHIPPED, base_currency=Currency.UAH, scenario_id=None
    )
    inputs = inputs_of(
        declarations,
        regime_id=answer.question.regime_id,
        objective_set_id=answer.question.objective_set_id,
    )
    pairs: list[tuple[TupleOutcome, CandidateProjection]] = []
    for outcome, _ in evaluated_outcomes():
        projection = projection_for(outcome.projection_key, answer, inputs, AS_OF)
        assert isinstance(projection, CandidateProjection), projection
        pairs.append((outcome, projection))
    assert pairs, "the shipped question evaluated nothing, so every assertion would be vacuous"
    return tuple(pairs)
