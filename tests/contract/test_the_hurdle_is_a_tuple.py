"""SC-002 and SC-003: the benchmark is a tuple through the same code path, and it is always there.

FR-012 is a claim about **origin**, not about agreement: *the hurdle's own benchmark figure in
the comparison MUST be produced by this same pipeline. A benchmark computed by a privileged
side channel would make the comparison unfalsifiable.* Two numbers that agree today prove
nothing about tomorrow, and the drift would be invisible because both would look reasonable.

So the first class below asserts **identity**, on 002's SC-016 precedent: the benchmark is an
*index*, so the figure the comparison calls the hurdle is literally an element of the sequence
it ranks, and there is no field on the record for a second figure to live in. The falsifying
experiment is in the same class: break the benchmark tuple's declarations and the whole
comparison comes back as ``BenchmarkUnavailable`` -- which a side-channel benchmark could not
do, because it would not have gone through the refusals.

The second class is SC-002's number, and it is asserted at the project tolerance over routes
that cost and delay **nothing**. The third explains, with an assertion rather than prose, why
the shipped domestic pair does not reproduce 001's figure exactly: it declares one day in and
three days out, and FR-015 puts waiting inside the span the rate is measured over. Asserting
equality against it would need a tolerance loose enough to hide a real defect.
"""

from __future__ import annotations

from typing import Final

import pytest

from terezy.core.decision.compare import compare
from terezy.core.decision.tuple_outcome import Registries, evaluate
from terezy.core.instruments.interface import DateRange, Holding
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.money import Money
from terezy.core.primitives.rates import NominalRate
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.project import Projection, project
from terezy.core.results.tuple import (
    BenchmarkUnavailable,
    Comparison,
    DeclarationMissing,
    Tuple,
    TupleOutcome,
)
from tests import tuple_registries as fixtures

pytestmark = pytest.mark.contract

AT_ISSUE: Final = DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END)
"""The outlay leaves on the issue date, so a zero-latency way in buys on it."""


def _outcome(registries: Registries, candidate: Tuple, horizon: DateRange) -> TupleOutcome:
    outcome = evaluate(
        candidate,
        amount=fixtures.AMOUNT,
        horizon=horizon,
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=registries,
    )
    assert isinstance(outcome, TupleOutcome), outcome
    return outcome


def _compared(
    registries: Registries,
    others: tuple[Tuple, ...] = (),
    horizon: DateRange = AT_ISSUE,
) -> Comparison | BenchmarkUnavailable:
    return compare(
        others,
        benchmark=fixtures.hurdle_tuple(),
        amount=fixtures.AMOUNT,
        horizon=horizon,
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=registries,
    )


def _ranked(
    registries: Registries,
    others: tuple[Tuple, ...] = (),
    horizon: DateRange = AT_ISSUE,
) -> Comparison:
    comparison = _compared(registries, others, horizon)
    assert isinstance(comparison, Comparison), comparison
    return comparison


class TestTheBenchmarkIsOneOfTheThingsItBenchmarks:
    """FR-012, asserted by construction rather than by comparing numbers that agree."""

    def test_the_benchmark_is_an_index_into_the_ranked_sequence(self) -> None:
        # The whole of research.md D3 in one line. There is no `benchmark: TupleOutcome` field
        # for a separately computed figure to occupy, so the hurdle cannot drift from the
        # tuples it is compared against: it *is* one of them.
        comparison = _ranked(fixtures.shipped())
        assert 0 <= comparison.benchmark < len(comparison.ranked)
        assert comparison.ranked[comparison.benchmark].key == fixtures.hurdle_tuple()

    def test_the_benchmark_carries_the_same_parts_as_any_other_tuple(self) -> None:
        # A privileged figure would be a bare rate. This one has a way in, a purchase, a
        # lifecycle, a tax line, exit terms and a way out, like everything it is ranked with.
        benchmark = _ranked(fixtures.shipped()).ranked[_ranked(fixtures.shipped()).benchmark]
        assert [line.part for line in benchmark.parts] == [
            "ramp_in",
            "entry",
            "lifecycle",
            "tax",
            "exit_terms",
            "ramp_out",
        ]

    def test_breaking_the_benchmarks_declarations_removes_the_comparison(self) -> None:
        # The falsifying experiment. A benchmark computed beside the comparison would survive
        # a missing access declaration, because it would never have consulted one. This one
        # refuses, and the refusal is the same typed value any other tuple would have got.
        comparison = _compared(fixtures.without_access(fixtures.shipped(), fixtures.OVDP))
        assert isinstance(comparison, BenchmarkUnavailable)
        assert isinstance(comparison.refusal, DeclarationMissing)
        assert comparison.refusal.part == "access"

    def test_other_tuples_are_still_scored_when_the_benchmark_refuses(self) -> None:
        # Carried rather than discarded: they were computed, they are real, and throwing them
        # away would hide work. What is withheld is the *ranking*, because a ranking with no
        # benchmark invites its own head to be read as a winner (FR-011).
        comparison = _compared(
            fixtures.without_access(fixtures.shipped(), fixtures.OVDP),
            (
                fixtures.fund_tuple(
                    fixtures.MILTECH,
                    exit_on=fixtures.MILTECH_EXIT,
                    yield_point=fixtures.MILTECH_POINT,
                ),
            ),
        )
        assert isinstance(comparison, BenchmarkUnavailable)
        assert len(comparison.scored) == 1
        assert comparison.scored[0].key.instrument_id == fixtures.MILTECH


class TestTheHurdleReproducesFeatureOnesFigure:
    """SC-002, at the project tolerance, over routes that cost and delay nothing."""

    def _one_hundred_percent_domestic(self) -> Registries:
        return fixtures.without_latency(fixtures.shipped())

    def _feature_001_hurdle(self, registries: Registries) -> float:
        """Feature 001's own figure for the very holding the join built.

        Computed here rather than read from a fixture, because the claim is that the *same
        holding* comes out the same way through both paths: ten units at par bought on the
        issue date, held to maturity, coupons in cash, lots consumed first in first out.
        """
        outcome = project(
            registries.instruments[fixtures.OVDP],
            Holding(
                owner_id=registries.streams[fixtures.SALARY].owner_id,
                instrument_id=fixtures.OVDP,
                quantity=10.0,
                purchased_on=fixtures.ISSUE_DATE,
                cost=Money(10_000.0, fixtures.UAH, prov.EMPTY),
            ),
            AT_ISSUE,
            fixtures.HOLD_TO_MATURITY,
            tax_classes=registries.tax_classes,
        )
        assert isinstance(outcome, Projection), outcome
        return outcome.hurdle.nominal_cash_flow_return.value

    def test_the_tuples_rate_is_feature_001s_money_weighted_return(self) -> None:
        # Both are the internal rate of return of the same dated flows, measured with the
        # instrument's own act/365 convention from the same date -- so with a way in and a way
        # out that charge nothing and take no time, they are not merely close: the series is
        # identical and the root find is the same function.
        registries = self._one_hundred_percent_domestic()
        rate = _outcome(registries, fixtures.hurdle_tuple(), AT_ISSUE).implied_rate
        assert isinstance(rate, NominalRate)
        assert is_close(rate.value, self._feature_001_hurdle(registries))

    def test_it_also_equals_the_contractual_yield_because_the_class_is_exempt(self) -> None:
        # Under a nil-rate class the gross and net series coincide, so 001's two figures agree
        # and the tuple's rate equals both. Asserted because the *interesting* case is the one
        # where they diverge: the moment a taxed instrument arrives, a join comparing itself
        # against `nominal_ytm` would be comparing an after-tax figure against a pre-tax one.
        registries = self._one_hundred_percent_domestic()
        outcome = _outcome(registries, fixtures.hurdle_tuple(), AT_ISSUE)
        rate = outcome.implied_rate
        assert isinstance(rate, NominalRate)
        assert is_close(rate.value, 0.16058553778779106)

    def test_the_whole_ten_thousand_was_deployed_so_nothing_is_left_out_of_the_rate(
        self,
    ) -> None:
        # The precondition of the equality above, asserted rather than assumed: at par, ten
        # thousand buys exactly ten units and leaves no remainder. A remainder would sit at
        # the venue and be excluded from the rate, and the two figures would part company for
        # a reason that has nothing to do with the pipeline.
        outcome = _outcome(self._one_hundred_percent_domestic(), fixtures.hurdle_tuple(), AT_ISSUE)
        assert outcome.undeployed is None


class TestWaitingIsACostAndTheShippedRoutesCharge:
    """Why the shipped domestic pair does *not* reproduce 001's figure, stated as arithmetic."""

    def test_the_shipped_pair_costs_nothing_and_still_returns_less(self) -> None:
        # Every leg of both routes declares zero fees -- the SC-004 bar -- so the whole gap is
        # the one day in and the three days out. FR-015 puts them inside the span, because
        # waiting is a cost (owner decision, 2026-08-22), and a rate that ignored them would
        # report the same figure for a route that settles today and one that settles in a
        # month.
        shipped = _outcome(fixtures.shipped(), fixtures.hurdle_tuple(), AT_ISSUE)
        instant = _outcome(
            fixtures.without_latency(fixtures.shipped()), fixtures.hurdle_tuple(), AT_ISSUE
        )
        assert is_close(shipped.reaches.amount, instant.reaches.amount)
        slow, quick = shipped.implied_rate, instant.implied_rate
        assert isinstance(slow, NominalRate)
        assert isinstance(quick, NominalRate)
        assert slow.value < quick.value

    def test_the_gap_is_four_days_of_it_and_no_more(self) -> None:
        # A sanity band, stated as loose (docs/METHODOLOGY.md §11.3): four days on a two-year
        # holding at roughly 16% is of the order of 16% x 4/730 = 0.09 percentage points, and
        # what the band rules out is a gap of the size a *fee* would make. The exact figure is
        # the root of a series whose dates all moved, so there is no closed form to check it
        # against, and inventing a tighter bound would be asserting the implementation.
        shipped = _outcome(fixtures.shipped(), fixtures.hurdle_tuple(), AT_ISSUE)
        instant = _outcome(
            fixtures.without_latency(fixtures.shipped()), fixtures.hurdle_tuple(), AT_ISSUE
        )
        slow, quick = shipped.implied_rate, instant.implied_rate
        assert isinstance(slow, NominalRate)
        assert isinstance(quick, NominalRate)
        assert 0.0 < quick.value - slow.value < 0.002

    def test_the_arrivals_are_three_days_after_the_releases(self) -> None:
        # The mechanism behind the gap, so the band above rests on something checkable.
        for arrival in _outcome(fixtures.shipped(), fixtures.hurdle_tuple(), AT_ISSUE).arrivals:
            assert (arrival.arrived_on - arrival.released_on).days == 3


class TestEveryComparisonCarriesTheBenchmark:
    """SC-003: verified across every comparison these suites produce, not sampled."""

    @pytest.mark.parametrize(
        "others",
        [
            pytest.param((), id="the benchmark alone"),
            pytest.param((fixtures.hurdle_tuple(),), id="the benchmark also listed as a candidate"),
        ],
    )
    def test_the_benchmark_is_present_and_scored(self, others: tuple[Tuple, ...]) -> None:
        comparison = _ranked(fixtures.shipped(), others)
        assert 0 <= comparison.benchmark < len(comparison.ranked)

    def test_the_benchmark_listed_twice_is_evaluated_once(self) -> None:
        # Otherwise a comparison would rank the hurdle against itself and report a tie with
        # itself, which is a sentence nobody should have to read.
        comparison = _ranked(fixtures.shipped(), (fixtures.hurdle_tuple(),))
        assert len(comparison.ranked) == 1

    def test_when_nothing_beats_the_hurdle_the_output_says_so_plainly(self) -> None:
        # The answer this product exists to be able to give (FR-011). A second OVDP tuple
        # through a route that charges 5% cannot beat the free one, and `beats_benchmark`
        # being empty is that verdict as a value rather than as something a reader infers
        # from the order of a list.
        registries = fixtures.with_new_route(
            fixtures.shipped(),
            fixtures.route(
                "test_expensive_in",
                origin="monobank_uah",
                destination="inzhur",
                direction="inbound",
                partner=fixtures.DOMESTIC_OUT,
                fee_pct=0.05,
            ),
        )
        expensive = fixtures.hurdle_tuple()
        comparison = _ranked(
            registries,
            (
                fixtures.replace(
                    expensive,
                    route_in=fixtures.FundingPath(
                        destination_id="inzhur",
                        stream_id=fixtures.SALARY,
                        route_id="test_expensive_in",
                    ),
                ),
            ),
        )
        assert len(comparison.ranked) == 2
        assert comparison.beats_benchmark == ()
        assert comparison.benchmark == 0

    def test_a_fund_that_does_beat_it_is_reported_as_beating_it(self) -> None:
        # And the other half, so the empty list above is a finding rather than a function
        # that always returns nothing.
        comparison = _ranked(
            fixtures.shipped(),
            (
                fixtures.fund_tuple(
                    fixtures.MILTECH,
                    exit_on=fixtures.MILTECH_EXIT,
                    yield_point=fixtures.MILTECH_POINT,
                ),
            ),
        )
        assert comparison.beats_benchmark == (0,)
        assert comparison.ranked[0].key.instrument_id == fixtures.MILTECH
        assert comparison.benchmark == 1
