"""Three issues the owner is offered and this engine will not price, and what it costs.

`covers_from` is the **placement** date, not a declared accrual start, and three of the
twenty-four shipped issues prove the difference is not hypothetical: their depository lists open
at a first coupon far enough from the placement that opening the first period there would
accrue a whole coupon over a stub. Deriving the true start from the amounts is 013 FR-021's
forbidden step, so the 2026-08-24 quotation -- which falls before every one of their declared
coupon dates -- is refused rather than priced (FR-001, FR-008).

They therefore leave every answer, and this module is what makes that a **named refusal**
rather than a shorter list (SC-007). It is the price of FR-001 and it is paid deliberately.
"""

from __future__ import annotations

import functools
from datetime import date

import pytest

from terezy.core.decision.answer import AnswerInputs, section_evaluated
from terezy.core.instruments import registry
from terezy.core.instruments import terms as terms_of
from terezy.core.results.candidates import CandidateSurvey
from terezy.core.results.tuple import RefusedTuple
from tests import answer_registries as answers

pytestmark = pytest.mark.worked_example

QUOTED_ON = date(2026, 8, 24)
"""Inzhur's quotation, buy and sell, for every issue it lists."""

NEWLY_PLACED = ("UA4000239040", "UA4000239081", "UA4000239107")
"""The three whose first declared coupon falls after the quotation. Measured 2026-09-05."""


@functools.cache
def _supplied() -> AnswerInputs:
    return answers.shipped_inputs()


def _first_coupon(name: str) -> date:
    declared = _supplied().registries.instruments[name]
    coupons = registry.ops_for(declared.instrument_class).coupons_per_unit(declared)
    return coupons[0][0]


def _covers_from(name: str) -> date:
    return terms_of.known_from(_supplied().registries.instruments[name].terms).on


def test_the_first_declared_period_would_pay_a_full_coupon_over_a_stub() -> None:
    """Why `covers_from` may not open the first period, in days read off the declarations.

    Each of the three declares a first coupon equal to its own next one -- a full period's
    amount -- while the span from the placement date to it is nothing like a full period. The
    lengths are read rather than retyped, because it is the *comparison* that is the argument.
    """
    for name in NEWLY_PLACED:
        declared = _supplied().registries.instruments[name]
        coupons = registry.ops_for(declared.instrument_class).coupons_per_unit(declared)
        stub = (_first_coupon(name) - _covers_from(name)).days
        full = (coupons[1][0] - coupons[0][0]).days
        assert coupons[0][1].amount == coupons[1][1].amount, name
        assert stub != full, (name, stub, full)
        assert _first_coupon(name) > QUOTED_ON, name


def _refusals(horizon_index: int) -> dict[str, RefusedTuple]:
    section = answers.answered(supplied=_supplied()).sections[horizon_index]
    assert isinstance(section.outcome, CandidateSurvey)
    return {
        item.key.instrument_id: item
        for item in section.outcome.comparison.refused
        if item.key.instrument_id in NEWLY_PLACED
    }


@pytest.mark.parametrize("horizon_index", [0, 1, 2])
def test_each_of_the_three_leaves_the_answer_as_a_refusal_naming_its_own_dates(
    horizon_index: int,
) -> None:
    """Refused, at every horizon the owner asked about, with the reason in the output."""
    refused = _refusals(horizon_index)
    assert set(refused) == set(NEWLY_PLACED)
    for name, item in refused.items():
        reason = item.refusal.reason
        assert QUOTED_ON.isoformat() in reason, name
        assert _first_coupon(name).isoformat() in reason, name
        assert name in reason


@pytest.mark.parametrize("horizon_index", [0, 1, 2])
def test_none_of_the_three_reaches_a_figure(horizon_index: int) -> None:
    """A refusal, not a quieter number: no outcome for any of them anywhere in the section."""
    section = answers.answered(supplied=_supplied()).sections[horizon_index]
    priced = {item.key.instrument_id for item in section_evaluated(section)}
    assert priced.isdisjoint(NEWLY_PLACED)
    # Non-vacuous: the population it is disjoint from is not empty.
    assert priced
