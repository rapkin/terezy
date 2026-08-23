"""SC-009, SC-010, FR-017, FR-021, G6, G7, G12: what a goal result says about itself.

Four claims that are all about honesty rather than about arithmetic, and each of them is a
thing the result must state *on its face* rather than leave to a reader's assumption:

* every figure is **nominal**, and the real-terms slot is present and explicitly empty;
* every mark on the growth assumption reaches **every solved figure**;
* the feasibility verdict says it is **one path under one stated assumption**, not a
  probability;
* nothing anywhere carries a likelihood, because none was computed.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import date

from terezy.core.goals import solve
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import SourceRef
from terezy.core.primitives.rates import RealTermsUnavailable
from terezy.core.results.goal import (
    Goal,
    GoalInputs,
    GoalOutcome,
    GrowthAssumption,
    Met,
    Missed,
)

UAH = Currency.UAH
AS_OF = date(2026, 1, 31)

UNVERIFIED_RATE = SourceRef(
    id="synthetic:growth_assumption",
    citation="SYNTHETIC FIXTURE -- an invented growth assumption, never verified.",
    retrieved_on=date(2026, 8, 1),
    verified_on=None,
)
"""The mark on the assumption. It must reach every figure solved against it (FR-012)."""


def _inputs(*, marked: bool) -> GoalInputs:
    return GoalInputs(
        as_of=AS_OF,
        base_currency=UAH,
        starting_amount=Money(100_000.0, UAH, prov.EMPTY),
        growth=GrowthAssumption(
            annual_rate=0.12682503013196977,
            provenance=prov.of([UNVERIFIED_RATE]) if marked else prov.EMPTY,
        ),
    )


def _goal(
    *,
    contribution: float | None = 10_000.0,
    target_sum: float | None = None,
    target_date: date | None = date(2027, 1, 31),
) -> Goal:
    return Goal(
        owner_id="owner-001",
        id="shape",
        currency=UAH,
        monthly_contribution=None if contribution is None else Money(contribution, UAH, prov.EMPTY),
        target_sum=None if target_sum is None else Money(target_sum, UAH, prov.EMPTY),
        target_date=target_date,
    )


def _solved(goal: Goal, *, marked: bool = False) -> GoalOutcome:
    outcome = solve.solve(
        goal, inputs=_inputs(marked=marked), conventions=solve.MONTHLY_END_OF_PERIOD
    )
    assert isinstance(outcome, GoalOutcome), outcome
    return outcome


# ---------------------------------------------------------------------------
# Nominal on its face, with the real slot present and empty
# ---------------------------------------------------------------------------


def test_every_reported_figure_is_labelled_nominal() -> None:
    """FR-017, G7, owner decision 2026-08-22."""
    assert _solved(_goal()).terms == "nominal"


def test_the_real_terms_slot_is_present_and_explicitly_empty() -> None:
    """SC-009: present, never absent, and never filled with a nominal figure standing in.

    The mechanism is 001's (research.md D4 there): ``RealTargetSum`` and the nominal
    ``Money`` are unrelated types, so assigning a nominal sum into this slot is a mypy error
    rather than something a test has to catch.
    """
    outcome = _solved(_goal())
    assert isinstance(outcome.real, RealTermsUnavailable)
    assert outcome.real.reason.strip()
    assert "inflation" in outcome.real.reason
    # ``assert not isinstance(outcome.real, RealTargetSum)`` is deliberately absent: mypy
    # reports it as unreachable, because the two records share no base and no value can be
    # both. That report *is* the guarantee -- the check lives in the type system, where a
    # nominal figure assigned into this slot is an error before any test runs.


def test_the_empty_real_slot_does_not_promise_real_terms_will_become_the_default() -> None:
    """research.md D8: the owner did not opt into that, and the reason says so.

    Feature 007 fills this slot. Whether a *real* figure then becomes the headline is a new
    decision, and a reason that implied otherwise would make it look like one already taken.
    """
    outcome = _solved(_goal())
    assert isinstance(outcome.real, RealTermsUnavailable)
    assert "nominal" in outcome.real.reason


# ---------------------------------------------------------------------------
# The assumption's marks reach every solved figure
# ---------------------------------------------------------------------------


def test_a_marked_growth_assumption_marks_the_solved_sum() -> None:
    """SC-010, FR-012, G6. The sum is a function of the rate, so it is as good as the rate."""
    outcome = _solved(_goal(), marked=True)
    assert UNVERIFIED_RATE in outcome.target_sum.provenance.sources
    assert prov.is_unverified(outcome.target_sum.provenance)
    assert UNVERIFIED_RATE in outcome.provenance.sources


def test_a_marked_growth_assumption_marks_the_solved_contribution() -> None:
    """The same claim in the mode where the *contribution* is what the rate produced."""
    outcome = _solved(_goal(contribution=None, target_sum=239_507.53314516676), marked=True)
    assert outcome.solved_for == "contribution"
    assert UNVERIFIED_RATE in outcome.monthly_contribution.provenance.sources


def test_a_marked_growth_assumption_marks_every_feasibility_figure() -> None:
    """100% of them, swept from the record rather than listed.

    A margin or a shortfall is the difference between a projected balance and a declared
    target, so it rests on the rate exactly as the balance does -- and it is the figure the
    owner is most likely to read.
    """
    met = _solved(_goal(target_sum=100_000.0), marked=True)
    missed = _solved(_goal(target_sum=10_000_000.0), marked=True)
    for outcome in (met, missed):
        for field in fields(outcome.feasibility):
            value = getattr(outcome.feasibility, field.name)
            if isinstance(value, Money):
                assert UNVERIFIED_RATE in value.provenance.sources, field.name
    assert isinstance(met.feasibility, Met)
    assert isinstance(missed.feasibility, Missed)


def test_an_unmarked_assumption_leaves_the_figures_unmarked() -> None:
    """The negative half, and the reason the positive half means anything: the mark is carried
    by data rather than switched on by a flag somebody could leave set."""
    outcome = _solved(_goal())
    assert not prov.is_unverified(outcome.target_sum.provenance)
    assert outcome.provenance.sources == frozenset()


def test_a_declared_variable_is_echoed_without_acquiring_the_assumptions_mark() -> None:
    """The mark travels with what depends on the rate, and no further.

    In the date mode the target sum is the owner's own declaration, not something the rate
    produced. Marking it would say the owner's stated target rests on an unverified
    assumption, which is false -- and a mark on every figure in the record is indistinguishable
    from no mark at all, because the reader could no longer tell which numbers the assumption
    actually moved.
    """
    outcome = _solved(_goal(target_sum=239_507.53314516676, target_date=None), marked=True)
    assert outcome.solved_for == "date"
    assert UNVERIFIED_RATE not in outcome.target_sum.provenance.sources
    assert UNVERIFIED_RATE in outcome.provenance.sources


# ---------------------------------------------------------------------------
# The verdict is not a probability, and says so
# ---------------------------------------------------------------------------


def test_the_verdict_states_that_it_is_deterministic_under_a_stated_assumption() -> None:
    """FR-021, G12, research.md D10.

    A bare "missed by 40 000" invites being read as a likelihood. Saying it is one path under
    one stated assumption costs a sentence and forecloses the misreading; shortfall
    *probability* needs the stochastic machinery this feature does not have.
    """
    note = _solved(_goal()).determinism_note.lower()
    assert "probability" in note
    assert "assumption" in note


def test_no_record_in_the_result_has_anywhere_to_put_a_likelihood() -> None:
    """The absence is structural rather than a promise. A field named for a probability could
    be filled by a later feature with a number nobody computed."""
    outcome = _solved(_goal())
    named = [field.name for field in fields(outcome)]
    for record in (outcome.feasibility, outcome.conventions):
        named.extend(field.name for field in fields(record))
    for name in named:
        assert "probability" not in name
        assert "likelihood" not in name
        assert "confidence" not in name
