"""The way in that is *there is nothing to do*: when it is legal, and what it costs.

023 FR-013, FR-014, FR-015 and SC-009. Three claims, and each is a way the entry could be
silently wrong:

* it is **constructed** exactly where the stream already arrives at the buying venue in the
  instrument's own currency, and ``compose`` is not asked for a corridor there;
* asserted for a pair where that does not hold, it is **refused with the seam named** rather
  than trusted -- the rule ``_identity_way_out`` already applies to the far end;
* it charges nothing and takes no time, and the ``ramp_in`` contribution is a **recorded
  zero** rather than a part the outcome omits.

The pair is planted by moving one instrument's ``bought_at`` to the venue the hryvnia salary
already lands at, which is the smallest edit that makes the entry legal for something other
than the balance the shipped registry declares.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest

from terezy.core.decision import candidates as module
from terezy.core.decision.tuple_outcome import evaluate
from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.results.candidates import CandidateSet
from terezy.core.results.composed import CompositionRefused, Unaskable
from terezy.core.results.tuple import HOLD_AS_CASH, SeamDoesNotChain, Tuple, TupleOutcome
from terezy.core.routes.cost import cost_entry
from terezy.core.routes.path import (
    ENTRY_BY_IDENTITY,
    FROM_THE_DECLARATION,
    IDENTITY_ENTRY_ID,
    entry_segments_of,
)
from tests import candidate_registries as fixtures

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from terezy.core.decision.tuple_outcome import Registries

OVDP: Final = "ovdp_synthetic_a"
SALARY_LANDS_AT: Final = "monobank_uah"
"""Where `salary_uah` arrives, and therefore the venue an identity entry is legal at."""


def _bought_where_the_salary_lands() -> Registries:
    return fixtures.with_access(fixtures.declared(), OVDP, bought_at=SALARY_LANDS_AT)


def _enumerated(registries: Registries) -> CandidateSet:
    result = fixtures.enumerated(registries)
    assert isinstance(result, CandidateSet), result
    return result


def _ways_in(registries: Registries, stream_id: str) -> list[object]:
    return [
        candidate.key.route_in
        for candidate in _enumerated(registries).candidates
        if candidate.key.instrument_id == OVDP and candidate.key.stream_id == stream_id
    ]


def test_the_pair_the_money_has_already_reached_yields_an_identity_entry() -> None:
    """FR-015. A candidate, where before this feature there was a recorded gap."""
    assert _ways_in(_bought_where_the_salary_lands(), fixtures.SALARY) == [ENTRY_BY_IDENTITY]


def test_no_route_is_invented_from_the_venue_to_itself() -> None:
    """FR-015. The entry names no route id at all, so nothing under `routes/` is implied."""
    registries = _bought_where_the_salary_lands()
    for way_in in _ways_in(registries, fixtures.SALARY):
        assert entry_segments_of(way_in) == ()  # type: ignore[arg-type]
    assert IDENTITY_ENTRY_ID not in registries.routes


def test_the_other_stream_for_the_same_instrument_still_needs_a_declared_corridor() -> None:
    """The short-circuit is about one pair, not about the instrument or the venue.

    The dollar stream arrives somewhere else in another currency, so its way in is whatever
    the routes declare -- which for this registry is nothing at all.
    """
    assert _ways_in(_bought_where_the_salary_lands(), fixtures.CONTRACT) == []


def test_asserted_where_the_money_is_not_there_it_is_refused_with_the_seam_named() -> None:
    """FR-013 and SC-009. A bare claim about where the money is, checked at the join.

    The unedited registry buys this instrument at `inzhur` while the salary lands at
    `monobank_uah`, so an entry by identity asserted for it is a purchase made with money that
    is somewhere else -- and bridging that gap would be a transfer nobody declared.
    """
    registries = fixtures.declared()
    refusal = evaluate(
        Tuple(
            instrument_id=OVDP,
            stream_id=fixtures.SALARY,
            route_in=ENTRY_BY_IDENTITY,
            exit_terms=fixtures.HOLD_TO_MATURITY,
            route_out=FROM_THE_DECLARATION,
        ),
        amount=fixtures.AMOUNT_UAH,
        horizon=fixtures.HORIZON,
        as_of=fixtures.AS_OF,
        continuation=HOLD_AS_CASH,
        registries=registries,
    )
    assert isinstance(refusal, SeamDoesNotChain), refusal
    assert refusal.seam == "route_in_to_purchase"
    assert refusal.left == f"{SALARY_LANDS_AT}/UAH"
    assert refusal.right.startswith("inzhur/")


def test_it_charges_nothing_and_takes_no_time() -> None:
    """FR-014, at the costing. Every component present at zero rather than absent."""
    costed = cost_entry(ENTRY_BY_IDENTITY, fixtures.AMOUNT_UAH)
    assert costed.sent == fixtures.AMOUNT_UAH
    assert costed.arrived == fixtures.AMOUNT_UAH
    assert costed.fraction == 0.0
    assert costed.components
    assert all(charged.amount == 0.0 for charged in costed.components.values())
    assert costed.channels_applied == ()
    assert costed.by_segment == ()
    assert costed.provenance == prov.EMPTY


def test_the_purchase_is_dated_the_horizons_first_day_and_ramp_in_is_a_recorded_zero() -> None:
    """FR-014, through the join: zero latency, and a part line rather than a missing part."""
    registries = _bought_where_the_salary_lands()
    key = next(
        candidate.key
        for candidate in _enumerated(registries).candidates
        if candidate.key.instrument_id == OVDP and candidate.key.stream_id == fixtures.SALARY
    )
    outcome = evaluate(
        key,
        amount=fixtures.AMOUNT_UAH,
        horizon=fixtures.HORIZON,
        as_of=fixtures.AS_OF,
        continuation=HOLD_AS_CASH,
        registries=registries,
    )
    assert isinstance(outcome, TupleOutcome), outcome
    ramp_in = next(part for part in outcome.parts if part.part == "ramp_in")
    assert ramp_in.amount.amount == 0.0
    assert outcome.span.start == fixtures.HORIZON.start
    assert outcome.arrivals[0].released_on >= fixtures.HORIZON.start


def test_a_negative_amount_raises_rather_than_costing_a_gain() -> None:
    """`cost_one`'s and `cost_exit`'s guard, on the third entry point.

    A negative movement is not this one in reverse, so it can only be a caller's arithmetic
    error -- and costing it would report a negative charge that reads as a gain, which is the
    figure the guard exists to keep out of a comparison.
    """
    with pytest.raises(ValueError, match="cannot be placed by"):
        cost_entry(ENTRY_BY_IDENTITY, money.scale(fixtures.AMOUNT_UAH, -1.0))


def test_composes_already_arrived_case_can_no_longer_reach_enumeration() -> None:
    """FR-016a. The arm is kept and raises rather than being deleted from a closed enum.

    Reached by calling the reader directly, because the invariant it names is what makes it
    unreachable through `enumerate_candidates`: enumeration compares the same venue and
    currency `compose` does and short-circuits first. Asserting the message says the guard
    describes what it does -- a raise here is a programmer error, never a fact about money.
    """
    refusal = CompositionRefused(
        case=Unaskable.ALREADY_ARRIVED,
        reason="a fixture standing where compose's own words would be",
        destination_id=SALARY_LANDS_AT,
        stream_id=fixtures.SALARY,
    )
    with pytest.raises(ValueError, match="already where it was wanted"):
        module._about_the_question(refusal)
