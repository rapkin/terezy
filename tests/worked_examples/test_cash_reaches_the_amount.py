"""50 000.00 UAH of cash reaches 50 000.00 UAH, at each of the owner's three horizons.

023 SC-001 and SC-002, hand-computed. The arithmetic is `reaches = outlay`, and every term of
it is a separate claim that could be wrong on its own:

===========  ==========================================================================
way in       entry by identity -- 0.00 UAH charged, 0 days, so the purchase is dated
             2026-09-01, the first day of every one of his horizons
bought       50 000.00 UAH of balance, nothing undeployed, because a balance declares no
             increment to round to. The unit price is the identity — one hryvnia of balance
             per hryvnia — and it is **not asserted here**: with no increment and no minimum
             ticket it cancels out of every reported figure, moving only the ledger quantity
             an outcome does not carry. Mutation-checked (1.00 to 2.00 changes no figure in
             the suite) and recorded rather than pinned by a test that would pass on its own
             fixture
lifecycle    +50 000.00 UAH, the balance released on the horizon's last day and nothing
             else: the declared rate is exactly 0 %, so no coupon, no distribution and no
             accrual is added to it. The same money as `entry`, from the other side --
             the part lines are an attribution and never a sum
tax          0.00 UAH -- the release returns the basis and no gain arises, so no class is
             named and none is needed
way out      exit by identity -- `monobank_uah`/UAH is the owner's one declared spendable
             endpoint, 0.00 UAH charged, 0 days
reaches      50 000.00 UAH on 2026-10-01, on 2026-12-01 and on 2027-09-01
implied      0.00 % nominal at all three: one outflow of 50 000 and one inflow of 50 000
round trip   0.00 UAH, **both legs present**, so it is quotable as a round trip
===========  ==========================================================================

Over the **shipped** root, because this is the owner's own answer rather than a mechanism.
"""

from __future__ import annotations

from datetime import date
from typing import Final

import pytest

from terezy.core.decision.answer import section_evaluated
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.rates import NominalRate
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.tuple import EXCLUDES, PartContribution, TupleOutcome
from terezy.core.routes.path import ENTRY_BY_IDENTITY, EXIT_BY_IDENTITY
from tests import answer_registries as fixtures

pytestmark = pytest.mark.worked_example

CASH: Final = "cash_uah_monobank"
OUTLAY: Final = 50_000.00
"""What the question states for `salary_uah`, in hryvnia."""

HORIZON_ENDS: Final = (date(2026, 10, 1), date(2026, 12, 1), date(2027, 9, 1))
FIRST_DAY: Final = date(2026, 9, 1)
"""Every horizon starts here, and with a zero-latency way in the purchase is dated the same."""


def _outcomes() -> tuple[TupleOutcome, ...]:
    """Cash's outcome in each of the owner's three sections, in section order."""
    answered = fixtures.answered(supplied=fixtures.shipped_inputs())
    found = []
    for section in answered.sections:
        cash = [
            outcome for outcome in section_evaluated(section) if outcome.key.instrument_id == CASH
        ]
        assert len(cash) == 1, (section.horizon, cash)
        found.append(cash[0])
    return tuple(found)


def _part(outcome: TupleOutcome, name: str) -> PartContribution:
    return next(item for item in outcome.parts if item.part == name)


def test_fifty_thousand_of_cash_reaches_fifty_thousand_at_every_horizon() -> None:
    """SC-001. One outflow, one inflow, equal to the last bit the tolerance admits."""
    outcomes = _outcomes()
    assert len(outcomes) == len(HORIZON_ENDS)
    for outcome, ends_on in zip(outcomes, HORIZON_ENDS, strict=True):
        assert outcome.horizon.end == ends_on
        assert outcome.outlay.amount == OUTLAY
        assert is_close(outcome.reaches.amount, OUTLAY)
        assert outcome.reaches.currency is fixtures.UAH


def test_the_balance_is_released_at_the_horizons_end_rather_than_summed_from_nothing() -> None:
    """FR-018. An empty arrival list would also total 50 000 against a 50 000 outlay -- no.

    One arrival, on the horizon's own last day, and the span is therefore the horizon: both
    identity legs declare zero latency, so cash is the one member of the set the
    `rates-in-one-ranking-span-different-periods` gap cannot touch.
    """
    for outcome, ends_on in zip(_outcomes(), HORIZON_ENDS, strict=True):
        assert len(outcome.arrivals) == 1
        arrival = outcome.arrivals[0]
        assert arrival.released_on == ends_on
        assert arrival.arrived_on == ends_on
        assert is_close(arrival.amount.amount, OUTLAY)
        assert outcome.span.start == FIRST_DAY
        assert outcome.span.end == ends_on


def test_the_implied_rate_is_zero_per_cent_at_every_horizon() -> None:
    """SC-002. Comparable, not `RateNotComparable`: refusing a rate would hide the baseline.

    Within the project tolerance rather than exactly, because the rate is bisected to a root
    and an exact-zero assertion would fail for a reason unrelated to the claim (FR-019).
    """
    for outcome in _outcomes():
        assert isinstance(outcome.implied_rate, NominalRate), outcome.implied_rate
        assert is_close(outcome.implied_rate.value, 0.0)


def test_both_legs_are_identity_so_the_zero_is_a_round_trip_figure() -> None:
    """SC-002 and FR-020. A one-way zero may never stand in for a round trip (Principle VI)."""
    for outcome in _outcomes():
        assert outcome.key.route_in is ENTRY_BY_IDENTITY
        assert outcome.key.route_out is EXIT_BY_IDENTITY
        assert _part(outcome, "ramp_in").amount.amount == 0.0
        assert _part(outcome, "ramp_out").amount.amount == 0.0
        assert outcome.routes.status == "open"
        assert outcome.routes.constrained == ()


def test_the_only_payment_is_the_balance_itself_and_nothing_is_charged_on_it() -> None:
    """FR-009. The rate adds nothing to the release, and proceeds equal basis so tax is zero.

    A **non-zero** lifecycle is the assertion that matters: the balance really was released,
    which an outcome reaching 50 000 through an empty arrival list would not show.
    """
    for outcome in _outcomes():
        assert is_close(_part(outcome, "lifecycle").amount.amount, OUTLAY)
        assert is_close(_part(outcome, "entry").amount.amount, -OUTLAY)
        assert _part(outcome, "tax").amount.amount == 0.0
        assert _part(outcome, "exit_terms").amount.amount == 0.0


def test_a_balance_strands_nothing_and_the_figures_carry_the_declarations_mark() -> None:
    """FR-011 and FR-004. No increment to round to, and the rate's `verified_on` is empty."""
    for outcome in _outcomes():
        assert outcome.undeployed is None
        assert prov.is_unverified(outcome.provenance)
        assert prov.is_unverified(outcome.reaches.provenance)


def test_cash_carries_the_exclusion_floor_and_adds_nothing_to_it() -> None:
    """SC-007 and FR-021. Above all *inflation*: a 0.00 % is where nominal is misread."""
    for outcome in _outcomes():
        assert outcome.excludes == EXCLUDES
        assert outcome.rests_on == ()
