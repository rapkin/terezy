"""The seven ways a question does not stand up, and the world the run is asked in.

015 FR-026. A ``Refused`` is returned **instead of** an answer, never beside one, and it is
reserved for what is wrong with the *question* -- anything about one horizon, one pair or one
candidate is a part-refusal inside an ``Answer``.

Every member is reachable from a **caller-built** record as well as from a file. The loader
refuses most of them too, because in an artefact under review a missing amount is a typo; this
is the same rule stated where the CLI and a test can also reach it, and a rule stated in one
place only is one a hand-built record walks straight past.
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any, get_args

import pytest

from terezy.api.answer import answer_question
from terezy.core.instruments.interface import DateRange
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.answer import (
    AmountForAnUndeclaredStream,
    Answer,
    NoHorizonDeclared,
    NoSubjectDeclared,
    Refused,
    StreamWithNoAmount,
    TwoIdenticalHorizons,
)
from terezy.data.declarations.errors import DeclarationError
from tests import answer_registries as fixtures

WARTIME = "wartime"
"""A regime the shipped ``war_end`` scenario declares, and the shipped registry does not use."""


def test_every_member_of_the_union_is_exercised_somewhere() -> None:
    """A member nothing reaches is a refusal nobody would notice going wrong."""
    exercised = {
        "NoHorizonDeclared",
        "NoSubjectDeclared",
        "AmountForAnUndeclaredStream",
        "StreamWithNoAmount",
        "TwoIdenticalHorizons",
        "BenchmarkOutsideTheSubjects",
        "BenchmarkYieldsSeveralCandidates",
        "PlanForNothing",
    }
    assert {member.__name__ for member in get_args(Refused)} == exercised


def test_a_question_with_no_horizon_refuses() -> None:
    refusal = fixtures.refused(replace(fixtures.owners_question(), horizons=()))
    assert isinstance(refusal, NoHorizonDeclared)


def test_a_question_about_nothing_refuses() -> None:
    """Neither a subject list nor the every-instrument token. Omission is never *everything*."""
    question = fixtures.owners_question()
    refusal = fixtures.refused(
        replace(question, subjects=(), every_declared_instrument=False, plans={})
    )
    assert isinstance(refusal, NoSubjectDeclared)


def test_two_identical_horizons_refuse() -> None:
    """Two identical sections are not two answers, and the cross-horizon reading keys by them."""
    question = fixtures.owners_question()
    repeated = (question.horizons[0], question.horizons[0])
    refusal = fixtures.refused(replace(question, horizons=repeated))
    assert isinstance(refusal, TwoIdenticalHorizons)
    assert refusal.horizon == question.horizons[0]


def test_an_amount_for_an_undeclared_stream_refuses() -> None:
    question = fixtures.owners_question()
    amounts = {**question.amounts, "salary_eur": Money(1.0, Currency.USD, prov.EMPTY)}
    refusal = fixtures.refused(replace(question, amounts=amounts))
    assert isinstance(refusal, AmountForAnUndeclaredStream)
    assert refusal.stream_id == "salary_eur"


@pytest.mark.parametrize("stream_id", ["salary_uah", "contract_usd"])
def test_a_declared_stream_with_no_stated_amount_refuses(stream_id: str) -> None:
    """The case that fails *silently* without this: its pairs never reach the comparison."""
    question = fixtures.owners_question()
    amounts = {name: value for name, value in question.amounts.items() if name != stream_id}
    refusal = fixtures.refused(replace(question, amounts=amounts))
    assert isinstance(refusal, StreamWithNoAmount)
    assert refusal.stream_id == stream_id


def test_the_every_instrument_token_asks_about_the_whole_registry() -> None:
    """FR-007's third form, which the owner's own question deliberately does not use."""
    question = fixtures.owners_question()
    registries = fixtures.declarations().tuples.registries
    declared = set(registries.instruments) | set(registries.funds)
    result = fixtures.answered(
        replace(
            question,
            subjects=(),
            every_declared_instrument=True,
            plans=dict.fromkeys(declared, question.plans[fixtures.OVDP]),
        )
    )
    assert {item.named for item in result.subjects} == declared
    assert all(len(item.standings) == len(declared) for item in result.sections)


# ---------------------------------------------------------------------------
# The world the run is asked in
# ---------------------------------------------------------------------------


def test_the_scenario_is_resolved_from_the_regime_the_question_names(tmp_path: Path) -> None:
    """Which scenario a regime belongs to is a fact about ``data/scenarios/``.

    A question restating it would be one fact in two places, disagreeing the day a regime moves.
    """
    root = _scratch_with_regime(tmp_path, WARTIME)
    run: Any = answer_question(
        root, fixtures.OWNERS_QUESTION, as_of=fixtures.AS_OF, base_currency=Currency.UAH
    )
    assert isinstance(run.answer, Answer), run.answer
    assert run.manifest.regime_id == WARTIME


def test_a_regime_no_scenario_declares_is_refused_by_name(tmp_path: Path) -> None:
    """A regime nobody declared would leave the route set unnarrowed."""
    root = _scratch_with_regime(tmp_path, "a_regime_nobody_declared")
    with pytest.raises(DeclarationError) as caught:
        answer_question(
            root, fixtures.OWNERS_QUESTION, as_of=fixtures.AS_OF, base_currency=Currency.UAH
        )
    assert "a_regime_nobody_declared" in caught.value.problem


def test_a_question_id_nothing_declares_is_refused_by_name(tmp_path: Path) -> None:
    with pytest.raises(DeclarationError) as caught:
        answer_question(
            fixtures.DATA_ROOT,
            "a_question_nobody_asked",
            as_of=fixtures.AS_OF,
            base_currency=Currency.UAH,
        )
    assert "a_question_nobody_asked" in caught.value.problem


def _scratch_with_regime(tmp_path: Path, regime_id: str) -> Path:
    """The shipped data root with the owner's question asked under a different world."""
    root = tmp_path / "data"
    shutil.copytree(fixtures.DATA_ROOT, root)
    target = root / "questions" / "fifty-thousand.toml"
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            'regime       = "(no regime declared)"', f'regime       = "{regime_id}"', 1
        ),
        encoding="utf-8",
    )
    return root


def test_a_horizon_that_ends_before_it_starts_is_the_loaders_refusal() -> None:
    """The verb sees a window that ran backwards only if a caller built one.

    It is not in ``Refused``: 010 already refuses it by name at the tuple level, and a second
    copy of that rule one layer up is the duplicate that goes out of step.
    """
    question = fixtures.owners_question()
    backwards = DateRange(start=date(2027, 1, 1), end=date(2026, 1, 1))
    result = fixtures.answered(replace(question, horizons=(backwards,)))
    assert isinstance(result, Answer)
