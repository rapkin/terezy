"""Fixtures for the answer suites: the owner's question, and deliberate edits to it.

Built from a data root rather than by hand, on ``tests/candidate_registries.py``'s reasoning
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
from terezy.core.instruments.access import VenueQuote
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.answer import Answer
from terezy.data.declarations import loader, resolver
from tests import data_roots

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping

    from terezy.core.results.answer import Refused
    from terezy.core.results.question import Question

REPO_ROOT: Final = data_roots.REPO_ROOT
SHIPPED_ROOT: Final = data_roots.SHIPPED
DATA_ROOT: Final = data_roots.with_fixtures()
"""The composed root. ``SHIPPED_ROOT`` is what the artefacts of the owner's own answer run
against -- the golden, the CLI, the worked example -- because those record what he is actually
offered; everything else here is about a mechanism whose only example is a fixture.
"""

QUESTION_FILE: Final = data_roots.SHIPPED / "questions" / "fifty-thousand.toml"
"""His question. Read from the shipped root under either root: the overlay declares none."""

UAH: Final = Currency.UAH
AS_OF: Final = date(2026, 8, 30)
"""The day the owner asked. Decides staleness and nothing else."""

OWNERS_QUESTION: Final = "fifty-thousand-hryvnia"
BENCHMARK: Final = "UA4000235865"
OVDP: Final = "ovdp"
INZHUR: Final = "inzhur"
MILTECH: Final = "inzhur_miltech"
REIT: Final = "inzhur_reit"


def declarations(root: Path = DATA_ROOT) -> resolver.AnswerDeclarations:
    """Every declaration the verb reads, under a data root."""
    return resolver.answer_from_data_root(root, base_currency=UAH, scenario_id=None)


def inputs(declared: resolver.AnswerDeclarations | None = None) -> AnswerInputs:
    """The verb's second parameter for a resolved registry.

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


def shipped_inputs() -> AnswerInputs:
    """The verb's second parameter over what ships, with no fixture in it."""
    return inputs(declarations(SHIPPED_ROOT))


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


def with_resale_price(
    supplied: AnswerInputs, instrument_id: str, per_unit: float = 995.0
) -> AnswerInputs:
    """The same registry with one instrument declaring what it sells for (015 FR-031).

    Every real ОВДП declaration carries one since 016; no FIXTURE does, because nobody quotes
    a resale price for a bond that does not exist. So this is how an early exit is reached on a
    *checkable* schedule, which is what SC-024 and SC-026 both rest on.
    """
    access = dict(supplied.registries.access)
    access[instrument_id] = replace(
        access[instrument_id],
        resale_price=VenueQuote(price=Money(per_unit, UAH, prov.EMPTY), kind="venue_terms"),
    )
    return replace(supplied, registries=replace(supplied.registries, access=access))


def declared_labels(
    declared: resolver.AnswerDeclarations | None = None,
) -> dict[str, tuple[str, ...]]:
    """Which groups each declared instrument declares itself into, by id.

    Here rather than in each suite because three of them ask the registry the same question, and
    three copies of one traversal is where they come to disagree about what a group *is*.
    """
    registries = (declarations() if declared is None else declared).tuples.registries
    return {
        **{name: item.groups for name, item in registries.instruments.items()},
        **{name: item.groups for name, item in registries.funds.items()},
    }
