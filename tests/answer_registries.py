"""Fixtures for the answer suites: the shipped question, and deliberate edits to it.

Built from ``data/`` rather than by hand, on ``tests/candidate_registries.py``'s reasoning
unchanged: the whole claim of this feature is that it answers a **declared** question over a
**declared** registry, so a suite that hand-built both would measure a world the loader never
validated.

Each helper makes **one** change and says what it is breaking.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Final

from terezy.core.decision.answer import AnswerInputs, answer
from terezy.core.primitives.currency import Currency
from terezy.core.results.answer import Answer
from terezy.data.declarations import loader, resolver

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping

    from terezy.core.results.answer import Refused
    from terezy.core.results.question import Question

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
DATA_ROOT: Final = REPO_ROOT / "data"
QUESTION_FILE: Final = DATA_ROOT / "questions" / "fifty-thousand.toml"

UAH: Final = Currency.UAH
AS_OF: Final = date(2026, 8, 30)
"""The day the owner asked. Decides staleness and nothing else."""

OWNERS_QUESTION: Final = "fifty-thousand-hryvnia"
BENCHMARK: Final = "ovdp_synthetic_a"
OVDP: Final = "ovdp"
INZHUR: Final = "inzhur"
MILTECH: Final = "inzhur_miltech"
REIT: Final = "inzhur_reit"


def declarations() -> resolver.AnswerDeclarations:
    """Every declaration the verb reads, under the shipped data root."""
    return resolver.answer_from_data_root(DATA_ROOT, base_currency=UAH, scenario_id=None)


def inputs(declared: resolver.AnswerDeclarations | None = None) -> AnswerInputs:
    """The verb's second parameter for the shipped registry.

    Deliberately thin, on ``candidate_registries.enumerated``'s rule: a fixture that decided
    anything the function under test decides would let a suite pass on the fixture's judgement.
    """
    resolved = declarations() if declared is None else declared
    return AnswerInputs(
        registries=resolved.tuples.registries,
        routes=resolved.tuples.registries.routes,
        groups=resolved.tuples.instruments.groups,
        bound=resolved.candidates.composition.bound,
        ceiling=resolved.candidates.ceiling,
    )


def owners_question() -> Question:
    """The owner's own question, loaded from the file that is its canonical form."""
    return loader.question_from_file(QUESTION_FILE)


def answered(
    question: Question | None = None,
    supplied: AnswerInputs | None = None,
    as_of: date = AS_OF,
) -> Answer:
    """The answer, asserted to be one. A ``Refused`` here is a fixture error, not a result."""
    result = answer(
        owners_question() if question is None else question, supplied or inputs(), as_of
    )
    assert isinstance(result, Answer), result
    return result


def refused(question: Question, supplied: AnswerInputs | None = None) -> Refused:
    """The refusal, asserted to be one. An ``Answer`` here is the failure under test."""
    result = answer(question, supplied or inputs(), AS_OF)
    assert not isinstance(result, Answer), result
    return result


def with_subjects(question: Question, *words: str) -> Question:
    """The same question asking about different words. Plans travel unchanged."""
    return replace(question, subjects=words)


def with_plans(question: Question, plans: Mapping[str, object]) -> Question:
    """The same question with a different plan mapping."""
    return replace(question, plans=plans)  # type: ignore[arg-type]


def one_horizon(question: Question, index: int = 0) -> Question:
    """The same question over one of its declared horizons."""
    return replace(question, horizons=(question.horizons[index],))
