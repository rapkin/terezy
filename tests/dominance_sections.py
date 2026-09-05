"""Sections for the dominance suites: the owner's own, and real ones with one field planted.

Not a test module -- ``pytest`` collects only ``test_*.py``.

Every section here comes out of a **real** answer over a resolved registry, and the planted
cases change exactly one field of one evaluated outcome. That is the ``with_resale_price``
technique 015 already uses, and the reason is its reason: a survey built by hand would let a
suite pass on a fixture's judgement about what a comparison looks like, and the cases 019 needs
-- an outcome with no arrivals, a section delivering two currencies -- are ones no declaration
in this repository produces.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Final

from terezy.core.decision.dominance import dominance
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.answer import HorizonSection
from terezy.core.results.candidates import CandidateSurvey
from terezy.core.results.dominance import DominanceRefused, DominanceResult
from terezy.core.results.tuple import Comparison, TupleOutcome
from terezy.data.declarations import loader
from tests import answer_registries as fixtures

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Callable, Sequence

    from terezy.core.results.objectives import ObjectiveSet

ONE_MONTH: Final = 0
THREE_MONTHS: Final = 1
TWELVE_MONTHS: Final = 2
"""Which section of the owner's answer, by the order his question declares its horizons."""


def objectives(set_id: str = fixtures.OBJECTIVE_SET) -> ObjectiveSet:
    """One declared objective set, resolved from the composed root."""
    return fixtures.declarations().objective_sets[set_id]


def section(index: int = ONE_MONTH) -> HorizonSection:
    """One section of the owner's own answer."""
    return fixtures.answered().sections[index]


def run(
    subject: HorizonSection,
    *,
    declared: ObjectiveSet | None = None,
    amounts: object = None,
) -> DominanceResult | DominanceRefused:
    """The pass over a section's parts, exactly as ``_section`` calls it.

    Re-run rather than read off ``section.dominance`` where a test plants a field, because the
    planted section was never answered: the point is what the pass makes of it.
    """
    question = fixtures.owners_question()
    return dominance(
        subject.outcome,
        withheld=subject.arrives_after_horizon,
        excludes=subject.excludes,
        objectives=objectives() if declared is None else declared,
        amounts=question.amounts if amounts is None else amounts,  # type: ignore[arg-type]
    )


def result(subject: HorizonSection, **kwargs: object) -> DominanceResult:
    """The pass's result, asserted to be one. A refusal here is the failure under test."""
    produced = run(subject, **kwargs)  # type: ignore[arg-type]
    assert isinstance(produced, DominanceResult), produced
    return produced


def outcomes(subject: HorizonSection) -> tuple[TupleOutcome, ...]:
    """Every outcome the section's comparison ranked, in the comparison's own order."""
    survey = subject.outcome
    assert isinstance(survey, CandidateSurvey), survey
    comparison = survey.comparison
    assert isinstance(comparison, Comparison), comparison
    return comparison.ranked


def with_outcomes(
    subject: HorizonSection, edit: Callable[[TupleOutcome], TupleOutcome]
) -> HorizonSection:
    """The same section with every ranked outcome passed through one edit.

    The edit returns the outcome unchanged for the candidates it does not plant on, so a caller
    writes one function rather than a rebuild of the survey.
    """
    survey = subject.outcome
    assert isinstance(survey, CandidateSurvey), survey
    comparison = survey.comparison
    assert isinstance(comparison, Comparison), comparison
    edited = replace(
        survey,
        comparison=replace(comparison, ranked=tuple(edit(item) for item in comparison.ranked)),
    )
    return replace(subject, outcome=edited)


def named(subject: HorizonSection, instrument_id: str) -> TupleOutcome:
    """One evaluated outcome by its instrument id, asserted to be there."""
    found = [item for item in outcomes(subject) if item.key.instrument_id == instrument_id]
    assert len(found) == 1, f"{instrument_id} yields {len(found)} outcome(s) in this section"
    return found[0]


def only(subject: HorizonSection, instrument_ids: Sequence[str]) -> HorizonSection:
    """The same section with its ranking narrowed to the named candidates, hurdle first.

    How a section that evaluated **one** candidate is reached: no declaration produces one, and
    the specification's own edge case turns on it -- a lone evaluated candidate is a
    non-dominated set of one, which is a different fact from one candidate dominating others.
    """
    survey = subject.outcome
    assert isinstance(survey, CandidateSurvey), survey
    comparison = survey.comparison
    assert isinstance(comparison, Comparison), comparison
    hurdle = comparison.ranked[comparison.benchmark]
    kept = (
        hurdle,
        *(
            item
            for item in comparison.ranked
            if item.key.instrument_id in set(instrument_ids) and item is not hurdle
        ),
    )
    return replace(
        subject,
        outcome=replace(
            survey,
            comparison=replace(comparison, ranked=kept, benchmark=0, ties=(), beats_benchmark=()),
        ),
    )


def with_no_arrivals(subject: HorizonSection, instrument_id: str) -> HorizonSection:
    """One candidate whose arrivals are empty, so the date criterion can read no figure.

    Research D5: the declared objectives read ``reaches``, which is always present, and
    ``arrivals[-1]``, which is not -- so an outcome with **no arrivals** is the missing-figure
    case, and no declaration in this repository produces one.
    """
    return with_outcomes(
        subject,
        lambda item: (
            replace(item, arrivals=()) if item.key.instrument_id == instrument_id else item
        ),
    )


def delivering_dollars(subject: HorizonSection, instrument_ids: Sequence[str]) -> HorizonSection:
    """The named candidates' money arriving in USD, so their pairs cross a currency.

    The amount is carried over unchanged and **no rate is applied**: what the case needs is two
    currencies in one section, and converting one would be the exchange rate SC-014 asserts is
    consulted nowhere.
    """
    wanted = frozenset(instrument_ids)
    return with_outcomes(
        subject,
        lambda item: (
            replace(
                item,
                reaches=Money(item.reaches.amount, Currency.USD, item.reaches.provenance),
            )
            if item.key.instrument_id in wanted
            else item
        ),
    )


def question_amounts(*, uah: float | None = 50_000.0, usd: float | None = 1.0) -> dict[str, Money]:
    """The question's stated amounts, with either stream droppable or repeated.

    What a fraction band resolves against (FR-011d). ``None`` drops the stream, which is how
    *no amount stated in the currency compared* is reached.
    """
    stated: dict[str, Money] = {}
    if uah is not None:
        stated["salary_uah"] = _uah(uah)
    if usd is not None:
        stated["contract_usd"] = Money(usd, Currency.USD, _uah(1.0).provenance)
    return stated


def _uah(amount: float) -> Money:
    """A hryvnia amount carrying the shipped question's own provenance, whatever that is."""
    declared = loader.question_from_file(fixtures.QUESTION_FILE).amounts["salary_uah"]
    return Money(amount, Currency.UAH, declared.provenance)
