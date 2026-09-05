"""FR-013 versus FR-014: two pairs that yield nothing, and two opposite remedies.

**The discrimination is by record and never by text** (FR-014a). `NothingConnects` says the
routes declare no corridor and the remedy is a declaration; `NothingNeedsToConnect` says the
money is already where it was wanted and the remedy is nothing at all. Reporting the second as
the first would send the owner to declare a corridor that is not missing -- and it is the
reading an implementer reaches for, because both look like *no candidate* from a row count.

Neither ever appears among the dropped candidates. A drop count that folded in combinations
which were never real is a figure a reader divides by and gets a meaningless answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from terezy.core.decision.candidates import enumerate_candidates
from terezy.core.primitives.currency import Currency
from terezy.core.results.candidates import (
    CandidateSet,
    NothingConnects,
    NothingNeedsToConnect,
)
from terezy.core.results.composed import CompositionRefused, Unaskable
from terezy.core.results.coverage import Destination
from terezy.core.routes.compose import compose
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
            assert isinstance(pair.why, NothingConnects), pair
            assert pair.why.side == "route_in"

    def test_a_registry_with_no_way_out_reports_the_other_side(self) -> None:
        """The exit half, which no declared registry reaches: every instrument's
        proceeds land at `inzhur`, which `inzhur_to_monobank` carries out of."""
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
        assert enumerated.candidates == ()
        sides = {
            pair.why.side
            for pair in enumerated.no_candidate
            if isinstance(pair.why, NothingConnects)
        }
        assert "route_out" in sides


class TestMoneyAlreadyWhereItWasWantedIsNotAGapInTheRegistry:
    """FR-014, and the `zero-hop-way-in` gap made visible rather than closed.

    A stream arriving in the right currency at the venue an instrument is bought at needs no way
    in -- and 010's `Tuple` requires one, so that candidate is not representable. What the column
    reports is the *pair*, with compose's own words, so the missing candidate is never mistaken
    for a corridor nobody declared.
    """

    @staticmethod
    def _bought_where_the_salary_lands() -> Registries:
        return fixtures.with_access(fixtures.declared(), OVDP, bought_at="monobank_uah")

    def test_the_pair_is_reported_with_the_other_reason_type(self) -> None:
        pairs = _enumerate(self._bought_where_the_salary_lands()).no_candidate
        already = [
            pair
            for pair in pairs
            if pair.instrument_id == OVDP and pair.stream_id == fixtures.SALARY
        ]
        assert len(already) == 1
        assert isinstance(already[0].why, NothingNeedsToConnect)

    def test_it_carries_composes_case_so_nothing_reads_the_words_to_classify_it(self) -> None:
        pairs = _enumerate(self._bought_where_the_salary_lands()).no_candidate
        why = next(
            pair.why
            for pair in pairs
            if pair.instrument_id == OVDP and pair.stream_id == fixtures.SALARY
        )
        assert isinstance(why, NothingNeedsToConnect)
        assert why.refusal.case is Unaskable.ALREADY_ARRIVED

    def test_composes_reason_reaches_the_report_verbatim(self) -> None:
        """SC-008, asserted by string equality against `compose`'s own answer.

        Rebuilt by calling `compose` here rather than compared against a copy of the sentence:
        a copy would agree with itself forever, which is exactly the staleness the assertion
        exists to catch.
        """
        registries = self._bought_where_the_salary_lands()
        refusal = compose(
            routes=registries.routes,
            stream=registries.streams[fixtures.SALARY],
            destination=Destination(venue_id="monobank_uah", currency=Currency.UAH),
            direction="inbound",
            regime_id=fixtures.question(registries).regime_id,
            bound=fixtures.declarations().composition.bound,
            spendable=registries.spendable,
        )
        why = next(
            pair.why
            for pair in _enumerate(registries).no_candidate
            if pair.instrument_id == OVDP and pair.stream_id == fixtures.SALARY
        )
        assert isinstance(refusal, CompositionRefused)
        assert isinstance(why, NothingNeedsToConnect)
        assert why.refusal.reason == refusal.reason

    def test_the_other_stream_for_the_same_instrument_is_still_a_plain_gap(self) -> None:
        """The two reasons appear side by side for one instrument, which is what makes the
        distinction load-bearing rather than a property of a whole registry."""
        pairs = {
            (pair.instrument_id, pair.stream_id): pair.why
            for pair in _enumerate(self._bought_where_the_salary_lands()).no_candidate
        }
        assert isinstance(pairs[OVDP, fixtures.SALARY], NothingNeedsToConnect)
        assert isinstance(pairs[OVDP, fixtures.CONTRACT], NothingConnects)


def test_a_pair_yielding_nothing_is_never_among_the_candidates() -> None:
    """The populations are disjoint, which is what lets FR-009's identity be a partition."""
    enumerated = _enumerate(fixtures.declared())
    with_candidates = {
        (candidate.key.instrument_id, candidate.key.stream_id)
        for candidate in enumerated.candidates
    }
    without = {(pair.instrument_id, pair.stream_id) for pair in enumerated.no_candidate}
    assert not with_candidates & without
