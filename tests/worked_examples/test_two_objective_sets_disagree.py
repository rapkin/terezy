"""Required test **I2**: two objectives over one candidate set produce different answers.

019 SC-002. The row asks for two things together, and both halves are here because an objective
that changes the answer without being recorded is a run nobody can reproduce:

* two questions differing **only** in the objective set they name, over one registry, produce
  different non-dominated sets;
* each answer's manifest names its own objective file, with its own digest.

**A chosen pair rather than any pair.** Two objective sets may honestly agree, so the criterion
is that a *disagreeing* pair exists and is pinned. The money alone is a total order over the
candidates -- it picks exactly one -- while the money and the date pick several, which is the
option the owner declined (CL-1, option C) and the reason the fixture set exists at all.

The row's word *rankings* is read as *the answers the objectives produce*: this feature's answer
is a partial order rather than a list.
"""

from __future__ import annotations

from typing import Final

import pytest

from terezy.api.answer import answer_question
from terezy.core.decision.dominance import why_one_member
from terezy.core.primitives.currency import Currency
from terezy.core.results.answer import Answer
from terezy.core.results.dominance import DominanceResult, EveryOtherIsDominated
from tests import answer_registries as fixtures

pytestmark = pytest.mark.worked_example

ROOT: Final = fixtures.DATA_ROOT
"""The composed root: the shipped registry plus the second objective set and the question that
names it, which exist for this row and for nothing else."""


def _answered(question_id: str) -> Answer:
    run = answer_question(ROOT, question_id, as_of=fixtures.AS_OF, base_currency=Currency.UAH)
    assert isinstance(run.answer, Answer), run.answer
    return run.answer


def _sets(answer: Answer) -> list[tuple[str, ...]]:
    out = []
    for section in answer.sections:
        assert isinstance(section.dominance, DominanceResult)
        out.append(tuple(key.instrument_id for key in section.dominance.non_dominated))
    return out


def test_the_two_questions_differ_in_exactly_one_field() -> None:
    """The premise. A fixture that also moved the amount or the benchmark would leave which
    difference produced the different answer unsettled, which is the whole of the criterion."""
    his = fixtures.owners_question()
    by_the_money = _answered(fixtures.BY_THE_MONEY).question
    differing = [
        name
        for name in his.__slots__
        if getattr(his, name) != getattr(by_the_money, name) and name != "id"
    ]
    assert differing == ["objective_set_id"]


def test_the_two_objective_sets_produce_different_non_dominated_sets() -> None:
    """The first half of I2, over one registry and one candidate set."""
    his = _sets(_answered(fixtures.OWNERS_QUESTION))
    money_alone = _sets(_answered(fixtures.BY_THE_MONEY))
    assert his != money_alone
    for section in _answered(fixtures.BY_THE_MONEY).sections:
        assert isinstance(section.dominance, DominanceResult)
        assert len(section.dominance.non_dominated) == 1, (
            "the money alone is a total order, so its set has exactly one member -- which is "
            "the winner this feature exists to refuse to present, arrived at by declaring one "
            "criterion rather than by any calibration"
        )
        assert isinstance(why_one_member(section.dominance), EveryOtherIsDominated)


def test_the_member_the_money_alone_picks_is_in_his_own_set_too() -> None:
    """The sets disagree in size and not in kind: dropping the date objective cannot add a
    member, it can only stop one being separated from the rest by the date it comes back."""
    for narrow, wide in zip(
        _sets(_answered(fixtures.BY_THE_MONEY)),
        _sets(_answered(fixtures.OWNERS_QUESTION)),
        strict=True,
    ):
        assert set(narrow) < set(wide)


def test_each_answers_manifest_names_its_own_objective_file_with_its_own_digest() -> None:
    """The second half of I2. Two runs differing only in their criteria are two results, and a
    manifest that did not name the set could not tell them apart."""
    refs = {}
    for question_id in (fixtures.OWNERS_QUESTION, fixtures.BY_THE_MONEY):
        run = answer_question(ROOT, question_id, as_of=fixtures.AS_OF, base_currency=Currency.UAH)
        named = run.answer.question.objective_set_id  # type: ignore[union-attr]
        refs[question_id] = next(
            ref for ref in run.manifest.inputs if ref.kind == "objective_set" and ref.id == named
        )
    assert refs[fixtures.OWNERS_QUESTION].id == fixtures.OBJECTIVE_SET
    assert refs[fixtures.BY_THE_MONEY].id == fixtures.MONEY_ALONE
    assert refs[fixtures.OWNERS_QUESTION].file != refs[fixtures.BY_THE_MONEY].file
    assert refs[fixtures.OWNERS_QUESTION].version != refs[fixtures.BY_THE_MONEY].version


def test_the_two_answers_carry_different_digests() -> None:
    """And the digest moves with them, because ``of_section`` encodes the dominance result."""
    digests = {
        question_id: answer_question(
            ROOT, question_id, as_of=fixtures.AS_OF, base_currency=Currency.UAH
        ).manifest.result_digest
        for question_id in (fixtures.OWNERS_QUESTION, fixtures.BY_THE_MONEY)
    }
    assert digests[fixtures.OWNERS_QUESTION] != digests[fixtures.BY_THE_MONEY]


def test_the_narrower_set_is_reached_over_the_same_candidates() -> None:
    """*Over the same candidate set* is half the row, so it is checked rather than assumed."""
    his = _answered(fixtures.OWNERS_QUESTION)
    money = _answered(fixtures.BY_THE_MONEY)
    for left, right in zip(his.sections, money.sections, strict=True):
        assert isinstance(left.dominance, DominanceResult)
        assert isinstance(right.dominance, DominanceResult)
        assert _population(left.dominance) == _population(right.dominance)


def _population(result: DominanceResult) -> frozenset[str]:
    return frozenset(
        key.instrument_id
        for key in (
            *result.non_dominated,
            *(item.key for item in result.dominated),
            *(item.key for item in result.not_placed),
        )
    )
