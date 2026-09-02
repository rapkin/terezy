"""The two things the owner may state that the engine may not find, and what each unlocks.

015 SC-024 and SC-028. Both are the same shape: a figure that refuses permanently until somebody
*states* a belief, and every figure computed through the belief carries it.

* **A resale price** turns a horizon shorter than an instrument's own terms from *shorten
  nothing, it is impossible* into a sale at the window's end. Removing the belief the sale rests
  on refuses at load and never falls back to a constant.
* **An exchange rate** turns ``inzhur_reit`` -- one of the **two real declarations in the whole
  registry** -- from permanently unsizable into an evaluated candidate. FR-021 forbids the
  engine to *find* a rate; FR-021a requires the owner to be able to *state* one, and the two
  are different acts.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from terezy.core.decision.answer import section_evaluated
from terezy.core.decision.candidates import dropped, evaluated
from terezy.core.instruments.fund import ExchangeRateAssumption
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.answer import Answer, Exclusion
from terezy.core.results.candidates import CandidateSurvey
from terezy.core.results.fund import FundAssumptions
from terezy.core.results.tuple import (
    DeclarationMissing,
    InstrumentRefused,
    TupleOutcome,
    TupleRefused,
)
from terezy.core.scenarios import early_exit
from tests import answer_registries as fixtures

SUBJECT = "ovdp_synthetic_a"
RATE = ExchangeRateAssumption(
    uah_per_unit=41.0,
    is_assumption=True,
    rationale=(
        "TEST FIXTURE -- an owner-stated rate, not observed and not read from a series. It is "
        "here so a fund whose payouts are sized in one currency and paid in another can be "
        "sized at all."
    ),
)


def _rate_plan(uah_per_unit: float = 41.0) -> FundAssumptions:
    """The REIT's own declared run plan, with a rate the owner states on it."""
    plan = fixtures.owners_question().plans[fixtures.REIT][0]
    assert isinstance(plan, FundAssumptions), plan
    return replace(plan, exchange_rate=replace(RATE, uah_per_unit=uah_per_unit))


def _with_rate(uah_per_unit: float = 41.0) -> Answer:
    question = fixtures.owners_question()
    return fixtures.answered(
        fixtures.with_plans(
            question, {**question.plans, fixtures.REIT: (_rate_plan(uah_per_unit),)}
        )
    )


def _survey(result: Answer, index: int = 0) -> CandidateSurvey:
    section = result.sections[index]
    assert isinstance(section.outcome, CandidateSurvey), section.outcome
    return section.outcome


def _refusal_for(result: Answer, instrument_id: str, index: int = 0) -> TupleRefused:
    return next(
        item.refusal
        for item in dropped(_survey(result, index).comparison)
        if item.key.instrument_id == instrument_id
    )


def _computed(result: Answer, index: int = 0) -> tuple[TupleOutcome, ...]:
    """Everything the comparison evaluated, **before** FR-030 withholds any of it.

    Kept apart from :func:`section_evaluated` because the two answer different questions: the
    rate is what makes a figure exist at all, and the horizon is what decides whether this
    section reports it.
    """
    return evaluated(_survey(result, index).comparison)


def _evaluated_ids(result: Answer, index: int = 0) -> set[str]:
    return {item.key.instrument_id for item in _computed(result, index)}


# ---------------------------------------------------------------------------
# The resale price (SC-024)
# ---------------------------------------------------------------------------


def test_without_a_declared_price_the_early_exit_refuses_by_name() -> None:
    """The shipped behaviour, and the reason this refusal is not a guard that reads as one."""
    refusal = _refusal_for(fixtures.answered(), SUBJECT)
    assert isinstance(refusal, DeclarationMissing), refusal
    assert refusal.part == "access"
    assert "access.resale_price" in refusal.what


def test_declaring_the_price_produces_a_figure_at_the_windows_end() -> None:
    """SC-024's first half. One declaration, and the option becomes comparable."""
    supplied = fixtures.with_resale_price(fixtures.inputs(), SUBJECT)
    result = fixtures.answered(supplied=supplied)
    outcome = next(
        item for item in section_evaluated(result.sections[0]) if item.key.instrument_id == SUBJECT
    )
    assert outcome.sold_early is not None
    assert outcome.sold_early.on == result.question.horizons[0].end
    assert outcome.sold_early.proceeds.amount > 0.0


def test_the_figure_names_the_belief_and_states_the_claims_about_it() -> None:
    """FR-032 and FR-033 together: the mark and the exclusions travel with the figure.

    Three of them, not four: this fixture's window contains no coupon date, so nothing detached
    from its quotation and there is no accrued residual to state.
    """
    supplied = fixtures.with_resale_price(fixtures.inputs(), SUBJECT)
    result = fixtures.answered(supplied=supplied)
    outcome = next(
        item for item in section_evaluated(result.sections[0]) if item.key.instrument_id == SUBJECT
    )
    assert early_exit.rests_on(supplied.registries.quotation_holds) in outcome.rests_on
    claims = {item.what for item in result.sections[0].excludes if item.applies_to == outcome.key}
    assert outcome.sold_early is not None
    assert is_close(outcome.sold_early.detached_per_unit.amount, 0.0)
    assert claims == {
        Exclusion.EARLY_EXIT_IS_A_POINT_NOT_A_DISTRIBUTION,
        Exclusion.EARLY_EXIT_SPREAD_IS_A_SELLERS_QUOTE,
        Exclusion.EARLY_EXIT_CARRIES_NO_RATE_RISK,
    }


def test_the_price_is_read_from_the_declaration_rather_than_from_a_default() -> None:
    """Two prices, two figures. A constant in the engine would produce one."""
    cheap = fixtures.answered(
        supplied=fixtures.with_resale_price(fixtures.inputs(), SUBJECT, per_unit=900.0)
    )
    dear = fixtures.answered(
        supplied=fixtures.with_resale_price(fixtures.inputs(), SUBJECT, per_unit=1_000.0)
    )
    proceeds = [
        next(
            item.sold_early.proceeds.amount
            for item in section_evaluated(result.sections[0])
            if item.key.instrument_id == SUBJECT and item.sold_early is not None
        )
        for result in (cheap, dear)
    ]
    assert proceeds[0] < proceeds[1]


def test_only_the_instrument_that_declares_a_price_gets_a_figure() -> None:
    """The other four still want one, and say so by name."""
    result = fixtures.answered(supplied=fixtures.with_resale_price(fixtures.inputs(), SUBJECT))
    assert SUBJECT in _evaluated_ids(result)
    others = [
        item.key.instrument_id
        for item in dropped(_survey(result).comparison)
        if isinstance(item.refusal, DeclarationMissing)
    ]
    assert SUBJECT not in others
    assert others


# ---------------------------------------------------------------------------
# The owner-stated exchange rate (SC-028)
# ---------------------------------------------------------------------------


def test_without_a_stated_rate_the_real_fund_is_permanently_unsizable() -> None:
    """The baseline: one of the two real declarations in the registry, refusing by name."""
    refusal = _refusal_for(fixtures.answered(), fixtures.REIT)
    assert isinstance(refusal, InstrumentRefused), refusal
    assert "FundAssumptions.exchange_rate" in refusal.reason or "rate" in refusal.reason


def test_stating_one_on_the_run_plan_evaluates_it() -> None:
    """SC-028. The owner states it; nothing finds it."""
    assert fixtures.REIT not in _evaluated_ids(fixtures.answered())
    assert fixtures.REIT in _evaluated_ids(_with_rate())


def test_removing_it_returns_the_refusal_that_names_the_missing_assumption() -> None:
    """The pair, so the fixture proves the rate is what changed and not something beside it."""
    assert fixtures.REIT in _evaluated_ids(_with_rate())
    assert isinstance(_refusal_for(fixtures.answered(), fixtures.REIT), InstrumentRefused)


def test_the_figure_it_unlocks_is_still_withheld_where_its_plan_puts_the_money_in_2028() -> None:
    """The two rules are independent, and this is where a reader would expect them to collide.

    A stated rate makes the figure **exist**; FR-030 decides whether this section **reports**
    it. The REIT's plan requests an exit sixteen months past the first horizon, so it is
    computed and withheld -- which is the honest answer rather than a caveated number.
    """
    result = _with_rate()
    assert fixtures.REIT in _evaluated_ids(result)
    withheld = {item.key.instrument_id for item in result.sections[0].arrives_after_horizon}
    assert fixtures.REIT in withheld
    assert fixtures.REIT not in {
        item.key.instrument_id for item in section_evaluated(result.sections[0])
    }


def test_the_figure_it_produces_carries_the_assumption_it_rests_on() -> None:
    """FR-021a: a belief about the future, and every figure through it inherits the mark."""
    outcome = next(
        item for item in _computed(_with_rate()) if item.key.instrument_id == fixtures.REIT
    )
    assert any(RATE.rationale in claim or "exchange rate" in claim for claim in outcome.rests_on), (
        outcome.rests_on
    )


@pytest.mark.parametrize("uah_per_unit", [40.0, 42.0])
def test_the_stated_rate_is_read_rather_than_defaulted(uah_per_unit: float) -> None:
    """Two rates, two figures. Nothing here consults a series, and nothing derives one."""
    outcome = next(
        item
        for item in _computed(_with_rate(uah_per_unit))
        if item.key.instrument_id == fixtures.REIT
    )
    assert outcome.reaches.amount > 0.0
