"""SC-018 and FR-004a: a destination that is already spendable satisfies its own exit.

The obvious reading -- *no exit chain, therefore no candidate* -- is the false verdict, and it
is the one an implementer arrives at by following FR-002 without its carve-out. Where an
instrument's `proceeds_to` is itself a declared spendable endpoint, the money has already come
back out: there are no exit legs to walk and none to charge for, and the candidate exists and is
evaluated like any other.

It is feature 003's FR-002 (owner decision, 2026-08-23), and `compose` cannot produce the
sentinel -- which is why FR-002 needs a carve-out here and why FR-004's prohibition is on the
**default** rather than on a way out with no segments.

No declared registry reaches this, so the fixture moves one instrument's proceeds and the
first test proves the move is what did it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from terezy.core.decision.candidates import evaluated, survey
from terezy.core.results.candidates import CandidateSet, CandidateSurvey
from terezy.core.routes.path import EXIT_BY_IDENTITY, DeclaredExit
from tests import candidate_registries as fixtures

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from terezy.core.decision.tuple_outcome import Registries

OVDP = "ovdp_synthetic_a"
SPENDABLE_VENUE = "monobank_uah"


def _proceeds_land_where_the_owner_spends() -> Registries:
    return fixtures.with_access(fixtures.declared(), OVDP, proceeds_to=SPENDABLE_VENUE)


def _set(registries: Registries) -> CandidateSet:
    result = fixtures.enumerated(registries)
    assert isinstance(result, CandidateSet), result
    return result


def test_the_declared_registry_reaches_this_nowhere() -> None:
    """The control that makes the fixture mean something: on the declarations as they stand
    every way out is a declared chain, so finding the sentinel there would be finding a bug."""
    ways_out = {item.key.route_out for item in _set(fixtures.declared()).candidates}
    assert ways_out == {DeclaredExit(route_id="inzhur_to_monobank")}


def test_the_way_out_is_the_identity_exit() -> None:
    produced = [
        item
        for item in _set(_proceeds_land_where_the_owner_spends()).candidates
        if item.key.instrument_id == OVDP
    ]
    assert len(produced) == 1
    assert produced[0].key.route_out is EXIT_BY_IDENTITY


def test_the_pair_is_a_candidate_and_not_a_gap_in_the_registry() -> None:
    """Emitting nothing here would put the pair in the no-candidate column and report a corridor
    nobody declared, which is the false verdict the column exists to prevent."""
    enumerated = _set(_proceeds_land_where_the_owner_spends())
    assert (OVDP, fixtures.SALARY) not in {
        (pair.instrument_id, pair.stream_id) for pair in enumerated.no_candidate
    }


def test_it_is_evaluated_and_its_way_out_costs_a_recorded_zero() -> None:
    """A round trip that costs nothing **because there is nothing to do** is a different claim
    from one whose fees happened to cancel, and only a recorded zero says which."""
    registries = _proceeds_land_where_the_owner_spends()
    result = survey(
        registries=registries,
        routes=registries.routes,
        question=fixtures.question(registries),
        ceiling=fixtures.ceiling(10_000),
        benchmark=fixtures.benchmark_key(registries, OVDP),
    )
    assert isinstance(result, CandidateSurvey), result
    outcome = next(item for item in evaluated(result.comparison) if item.key.instrument_id == OVDP)
    ramp_out = next(part for part in outcome.parts if part.part == "ramp_out")
    assert ramp_out.amount.amount == 0.0
    assert outcome.key.route_out is EXIT_BY_IDENTITY
