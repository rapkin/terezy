"""FR-013: the pairs that yield nothing, and the side each of them is missing.

`NothingConnects` says the routes declare no corridor and the remedy is a declaration, and it
names **which side** came back empty -- a corridor into the buying venue, or one out of the
venue the proceeds land at -- because the two remedies differ and a row count shows neither.

It never appears among the dropped candidates. A drop count that folded in combinations which
were never real is a figure a reader divides by and gets a meaningless answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from terezy.core.decision.candidates import enumerate_candidates
from terezy.core.results.candidates import CandidateSet
from terezy.core.routes.path import EXIT_BY_IDENTITY
from tests import candidate_registries as fixtures

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from terezy.core.decision.tuple_outcome import Registries

OVDP = "ovdp_synthetic_a"


def _enumerate(registries: Registries) -> CandidateSet:
    result = enumerate_candidates(
        registries=registries,
        routes=registries.routes,
        question=fixtures.question(registries),
        ceiling=fixtures.ceiling(10_000),
    )
    assert isinstance(result, CandidateSet), result
    return result


class TestAnAbsentCorridorIsReportedAsAnAbsentCorridor:
    def test_the_dollar_stream_reaches_nothing_and_the_record_says_which_side(self) -> None:
        pairs = _enumerate(fixtures.declared()).no_candidate
        assert pairs
        for pair in pairs:
            assert pair.why.side == "route_in", pair

    def test_a_registry_with_no_way_out_reports_the_other_side(self) -> None:
        """The exit half. Every instrument bought at `inzhur` releases its proceeds there, and
        `inzhur_to_monobank` is the only declared corridor out of it.

        What survives is the balance, whose proceeds land somewhere the owner already spends
        from: its way out is the identity exit and needs no corridor at all. Asserted rather
        than excluded, because a candidate surviving the removal for the *wrong* reason -- a
        corridor nobody declared -- is what this suite exists to catch.
        """
        registries = fixtures.declared()
        routes = {
            route_id: route
            for route_id, route in registries.routes.items()
            if route_id != "inzhur_to_monobank"
        }
        enumerated = enumerate_candidates(
            registries=registries,
            routes=routes,
            question=fixtures.question(registries),
            ceiling=fixtures.ceiling(10_000),
        )
        assert isinstance(enumerated, CandidateSet), enumerated
        assert {candidate.key.route_out for candidate in enumerated.candidates} <= {
            EXIT_BY_IDENTITY
        }
        assert "route_out" in {pair.why.side for pair in enumerated.no_candidate}


def test_a_pair_yielding_nothing_is_never_among_the_candidates() -> None:
    """The populations are disjoint, which is what lets FR-009's identity be a partition."""
    enumerated = _enumerate(fixtures.declared())
    with_candidates = {
        (candidate.key.instrument_id, candidate.key.stream_id)
        for candidate in enumerated.candidates
    }
    without = {(pair.instrument_id, pair.stream_id) for pair in enumerated.no_candidate}
    assert not with_candidates & without
