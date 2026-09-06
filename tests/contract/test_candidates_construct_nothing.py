"""SC-019 and FR-002: every route term in a produced set came out of `compose`.

The rule this feature is most likely to break by accident, because building a chain is one
line and reads perfectly reasonable. What stops it is not a convention: every way in is
asserted **object-identical** to a record `compose` returned, so a chain assembled here fails
even when it is assembled correctly.

The way out is compared by **equality** rather than identity, and the difference is the whole
of the carve-out: `exit_chain_of` builds a fresh record, and `compose` emits no `ExitChain` for
one to be identical to. `FROM_THE_DECLARATION` appears in no produced set at all (FR-004).

**Two constructions are permitted, and both are the absence of a chain rather than a claim
about what connects**: the identity exit (003 FR-002) and, since 023, the identity entry, for a
pair whose money is already at the venue that sells the thing. Each is bounded from the other
side below -- it appears exactly where the declarations put it and nowhere else.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from terezy.core.decision import candidates as module
from terezy.core.decision.tuple_outcome import currency_of
from terezy.core.results.candidates import CandidateSet
from terezy.core.results.composed import Enumeration
from terezy.core.results.coverage import Destination
from terezy.core.routes.compose import compose
from terezy.core.routes.path import (
    ENTRY_BY_IDENTITY,
    EXIT_BY_IDENTITY,
    FROM_THE_DECLARATION,
    ExitChain,
    exit_chain_of,
)
from tests import candidate_registries as fixtures
from tests import tuple_registries as tuples

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from terezy.core.decision.tuple_outcome import Registries

pytestmark = pytest.mark.contract

OVDP = "ovdp_synthetic_a"
CASH = "cash_uah_monobank"


def _set(registries: Registries) -> CandidateSet:
    result = fixtures.enumerated(registries)
    assert isinstance(result, CandidateSet), result
    return result


def _recorded(
    registries: Registries, monkeypatch: pytest.MonkeyPatch
) -> tuple[CandidateSet, list[object]]:
    """One enumeration, with every record `compose` handed *it* captured on the way past.

    Identity is the claim SC-019 makes, and it can only be checked against the objects the
    enumeration actually received: calling `compose` again from a test builds equal records with
    different identities, which would make the assertion structural and let a rebuilt chain pass.
    """
    emitted: list[object] = []
    real = compose

    def recording(**kwargs: object) -> object:
        result = real(**kwargs)  # type: ignore[arg-type]
        if isinstance(result, Enumeration):
            emitted.extend(result.candidates)
        return result

    monkeypatch.setattr(module, "compose", recording)
    produced = fixtures.enumerated(registries)
    assert isinstance(produced, CandidateSet), produced
    return produced, emitted


def _declared(registries: Registries, instrument_id: str) -> tuple[object, object]:
    """What `compose` emits for one instrument's two questions, asked here independently."""
    access = registries.access[instrument_id]
    declared = (
        registries.funds.get(instrument_id)
        or registries.cash.get(instrument_id)
        or registries.instruments[instrument_id]
    )
    currency = currency_of(declared)
    question = fixtures.question(registries)
    ways_in = compose(
        routes=registries.routes,
        stream=registries.streams[fixtures.SALARY],
        destination=Destination(venue_id=access.bought_at, currency=currency),
        direction="inbound",
        regime_id=question.regime_id,
        bound=question.bound,
        spendable=registries.spendable,
    )
    ways_out = compose(
        routes=registries.routes,
        stream=registries.streams[fixtures.SALARY],
        destination=Destination(venue_id=access.proceeds_to, currency=currency),
        direction="exit",
        regime_id=question.regime_id,
        bound=question.bound,
        spendable=registries.spendable,
    )
    return ways_in, ways_out


def test_every_way_in_is_object_identical_to_something_compose_emitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    produced, emitted = _recorded(fixtures.declared(), monkeypatch)
    assert produced.candidates
    identities = {id(item) for item in emitted}
    routed = [
        candidate
        for candidate in produced.candidates
        if candidate.key.route_in is not ENTRY_BY_IDENTITY
    ]
    assert routed
    for candidate in routed:
        assert id(candidate.key.route_in) in identities, candidate


def test_the_only_way_in_this_feature_builds_is_the_identity_entry() -> None:
    """The second carve-out, bounded from the other side (023 FR-015).

    The balance is bought at the venue the hryvnia salary already lands at, and it is the one
    pair in this registry that is: every other way in came out of `compose`. A construction
    appearing anywhere else would be a corridor from a venue to itself, invented.
    """
    registries = fixtures.declared()
    built = [
        candidate.key
        for candidate in _set(registries).candidates
        if candidate.key.route_in is ENTRY_BY_IDENTITY
    ]
    assert built
    for key in built:
        stream = registries.streams[key.stream_id]
        access = registries.access[key.instrument_id]
        assert stream.arrives_at == access.bought_at
        assert stream.amount.currency is currency_of(
            registries.cash.get(key.instrument_id)
            or registries.funds.get(key.instrument_id)
            or registries.instruments[key.instrument_id]
        )


def test_every_non_identity_way_out_equals_exit_chain_of_something_compose_emitted() -> None:
    registries = fixtures.declared()
    for candidate in _set(registries).candidates:
        way_out = candidate.key.route_out
        if way_out is EXIT_BY_IDENTITY:
            continue
        _, ways_out = _declared(registries, candidate.key.instrument_id)
        assert isinstance(ways_out, Enumeration)
        assert way_out in [exit_chain_of(way) for way in ways_out.candidates], candidate


def test_the_sentinel_that_settles_a_journey_after_the_fact_is_never_emitted() -> None:
    """FR-004. A set holding `FROM_THE_DECLARATION` holds a journey whose identity is decided
    later, and a reader cannot tell which chain was costed."""
    for candidate in _set(fixtures.declared()).candidates:
        assert candidate.key.route_out is not FROM_THE_DECLARATION


def test_the_only_way_out_this_feature_builds_is_the_identity_exit() -> None:
    """The carve-out, bounded from the other side: where `compose` *can* answer, its answer is
    what travels; where it cannot, the one thing constructed is the sentinel 003 declared."""
    registries = fixtures.with_access(fixtures.declared(), OVDP, proceeds_to="monobank_uah")
    built = [
        candidate
        for candidate in _set(registries).candidates
        if candidate.key.route_out is EXIT_BY_IDENTITY
    ]
    # The balance is the other one, and it is not an edit: its proceeds land where the owner
    # already spends, which is what makes it the do-nothing baseline.
    assert [candidate.key.instrument_id for candidate in built] == [CASH, OVDP]


def test_no_produced_chain_holds_a_segment_compose_did_not_put_there() -> None:
    """A chain extended by one hop would still be a valid `ExitChain` and would still pass a
    type check, so the segments are compared against the enumeration rather than the type."""
    registries = fixtures.declared()
    for candidate in _set(registries).candidates:
        way_out = candidate.key.route_out
        assert isinstance(way_out, ExitChain)
        if way_out is EXIT_BY_IDENTITY:
            continue  # the permitted construction, bounded by the test two above
        _, ways_out = _declared(registries, candidate.key.instrument_id)
        assert isinstance(ways_out, Enumeration)
        assert way_out in [exit_chain_of(way) for way in ways_out.candidates]


def test_a_registry_offering_two_ways_in_yields_both_and_invents_no_third(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The count, so the identity assertions above cannot pass by there being one of everything."""
    second = tuples.route(
        "test_second_way_in",
        origin="monobank_uah",
        destination="inzhur",
        direction="inbound",
        fee_pct=0.02,
    )
    registries = tuples.with_new_route(fixtures.declared(), second)
    ways_in, _ = _declared(registries, OVDP)
    assert isinstance(ways_in, Enumeration)
    assert len(ways_in.candidates) == 2
    produced, emitted = _recorded(registries, monkeypatch)
    mine = [item for item in produced.candidates if item.key.instrument_id == OVDP]
    assert len(mine) == 2
    identities = {id(item) for item in emitted}
    assert {id(item.key.route_in) for item in mine} <= identities


def test_narrowing_the_route_set_removes_the_candidates_that_needed_it() -> None:
    """The corridors a regime disbelieves in produce nothing, rather than being composed anyway.

    The *other* half of that seam -- composing over a route set wider than the registry
    declares -- is `tests/unit/test_candidate_refusals.py::TestARouteTheRegistryDoesNotDeclare`,
    where it refuses as a whole rather than dropping one identical candidate per pair.
    """
    registries = fixtures.declared()
    narrowed = {key: value for key, value in registries.routes.items() if key != "inzhur_direct"}
    enumerated = fixtures.enumerated(replace(registries, routes=narrowed), routes=narrowed)
    assert isinstance(enumerated, CandidateSet), enumerated
    # The balance survives, and for the reason this test is about: it needed no corridor to
    # begin with, so removing one cannot take it away.
    assert [candidate.key.instrument_id for candidate in enumerated.candidates] == [CASH]
