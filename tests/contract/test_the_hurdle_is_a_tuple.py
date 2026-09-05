"""SC-002 and SC-003: the benchmark is a tuple through the same code path, and it is always there.

FR-012 is a claim about **origin**, not about agreement: *the hurdle's own benchmark figure in
the comparison MUST be produced by this same pipeline. A benchmark computed by a privileged
side channel would make the comparison unfalsifiable.* Two numbers that agree today prove
nothing about tomorrow, and the drift would be invisible because both would look reasonable.

So the first class asserts the **origin** rather than the agreement: the benchmark is an
*index*, so the figure the comparison calls the hurdle is literally an element of the sequence
it ranks, and there is no field on the record for a second figure to live in. The falsifying
experiment is in the same class: break the benchmark tuple's declarations and the whole
comparison comes back as ``BenchmarkUnavailable`` -- which a side-channel benchmark could not
do, because it would not have gone through the refusals.

⚙ **SC-002 as literally written does not hold, and this is where the departure lives.** The
criterion says *the OVDP evaluated as a tuple through its zero-cost domestic routes reproduces
feature 001's hurdle rate within the project tolerance*. Over the routes as they are declared
the two figures are 0.1598 and 0.16059, which is outside it. The gap is entirely the one day
in and the three days out that FR-015 puts **inside** the span the rate is measured over --
waiting is a cost, and that is an owner decision of 2026-08-22 rather than an inference. So
the equality is asserted over ``without_latency``, a fixture that edits the declarations, and
the class below isolates what the edit removed. It is recorded on ``plan.md``'s departures
list as well as here, because a departure that lives only in a test docstring is one the next
reader of the spec will not find.
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
        comparison = _ranked(fixtures.declared())
        assert 0 <= comparison.benchmark < len(comparison.ranked)
        assert comparison.ranked[comparison.benchmark].key == fixtures.hurdle_tuple()

    def test_the_benchmark_carries_the_same_parts_as_any_other_tuple(self) -> None:
        # A privileged figure would be a bare rate. This one has a way in, a purchase, a
        # lifecycle, a tax line, exit terms and a way out, like everything it is ranked with.
        benchmark = _ranked(fixtures.declared()).ranked[_ranked(fixtures.declared()).benchmark]
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
        comparison = _compared(fixtures.without_access(fixtures.declared(), fixtures.OVDP))
        assert isinstance(comparison, BenchmarkUnavailable)
        assert isinstance(comparison.refusal, DeclarationMissing)
        assert comparison.refusal.part == "access"

    def test_other_tuples_are_still_scored_when_the_benchmark_refuses(self) -> None:
        # Carried rather than discarded: they were computed, they are real, and throwing them
        # away would hide work. What is withheld is the *ranking*, because a ranking with no
        # benchmark invites its own head to be read as a winner (FR-011).
        comparison = _compared(
            fixtures.without_access(fixtures.declared(), fixtures.OVDP),
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

    def test_the_carried_outcomes_are_in_candidate_order_and_not_ranked(self) -> None:
        # The other half of the sentence above, and it needs **two** outcomes to say anything:
        # with one, "unranked" and "ranked" are the same list. These two are offered dearest
        # first, so candidate order and rate order disagree -- and `scored` must be the former.
        # Sorting here would hand back the ordering `BenchmarkUnavailable` exists to withhold,
        # and its own `reason` says so: a ranking with no benchmark invites its own head to be
        # read as a winner.
        registries = fixtures.with_new_route(
            fixtures.without_access(fixtures.declared(), fixtures.OVDP),
            fixtures.route(
                "test_costly_in",
                origin="monobank_uah",
                destination="inzhur",
                direction="inbound",
                partner=fixtures.DOMESTIC_OUT,
                fee_pct=0.05,
            ),
        )
        dear = fixtures.replace(
            fixtures.fund_tuple(
                fixtures.MILTECH,
                exit_on=fixtures.MILTECH_EXIT,
                yield_point=fixtures.MILTECH_POINT,
            ),
            route_in=fixtures.FundingPath(
                destination_id="inzhur", stream_id=fixtures.SALARY, route_id="test_costly_in"
            ),
        )
        cheap = fixtures.fund_tuple(
            fixtures.MILTECH, exit_on=fixtures.MILTECH_EXIT, yield_point=fixtures.MILTECH_POINT
        )
        comparison = _compared(registries, (dear, cheap))
        assert isinstance(comparison, BenchmarkUnavailable)
        assert [outcome.key for outcome in comparison.scored] == [dear, cheap]
        rates = [outcome.implied_rate for outcome in comparison.scored]
        assert all(isinstance(rate, NominalRate) for rate in rates)
        values = [rate.value for rate in rates if isinstance(rate, NominalRate)]
        assert values != sorted(values, reverse=True)
        assert "not ranked" in comparison.reason


class TestTheHurdleReproducesFeatureOnesFigure:
    """SC-002, at the project tolerance, over routes that cost and delay nothing."""

    def _one_hundred_percent_domestic(self) -> Registries:
        return fixtures.without_latency(fixtures.declared())

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
        # thousand buys exactly ten units and leaves no remainder, so the money that left the
        # stream and the money the rate is measured on are the same number here. The equality
        # therefore rests on the pipeline rather than on the netting rule for a remainder.
        outcome = _outcome(self._one_hundred_percent_domestic(), fixtures.hurdle_tuple(), AT_ISSUE)
        assert outcome.undeployed is None


def _ramp_costs(outcome: TupleOutcome) -> list[float]:
    """What the way in and the way out charged, read off the outcome's own attribution."""
    return [part.amount.amount for part in outcome.parts if part.part in {"ramp_in", "ramp_out"}]


class TestWaitingIsACostAndTheShippedRoutesCharge:
    """Why the shipped domestic pair does *not* reproduce 001's figure, stated as arithmetic."""

    def test_the_shipped_pair_costs_nothing_and_still_returns_less(self) -> None:
        # Every leg of both routes declares zero fees -- the SC-004 bar -- so the whole gap is
        # the one day in and the three days out. FR-015 puts them inside the span, because
        # waiting is a cost (owner decision, 2026-08-22), and a rate that ignored them would
        # report the same figure for a route that settles today and one that settles in a
        # month.
        #
        # **The whole outlay is accounted for on both**, which is what says neither route
        # charged anything: a fee changes what *arrives*, so it would leave a purchase plus a
        # remainder short of what was sent. The two do not reach the same amount, and since
        # 022 they cannot: a day of latency buys a day dirtier quotation, so the slower route
        # deploys into a different number of whole units. That is time showing up in the
        # price as well as in the dates, not a cost either route levied.
        shipped = _outcome(fixtures.declared(), fixtures.hurdle_tuple(), AT_ISSUE)
        instant = _outcome(
            fixtures.without_latency(fixtures.declared()), fixtures.hurdle_tuple(), AT_ISSUE
        )
        for outcome in (shipped, instant):
            charged = _ramp_costs(outcome)
            assert charged
            assert all(is_close(amount, 0.0) for amount in charged), charged
        slow, quick = shipped.implied_rate, instant.implied_rate
        assert isinstance(slow, NominalRate)
        assert isinstance(quick, NominalRate)
        assert slow.value < quick.value

    def test_the_gap_is_four_days_of_it_and_no_more(self) -> None:
        # A sanity band, stated as loose (docs/METHODOLOGY.md §11.3): four days on a two-year
        # holding at roughly 16% is of the order of 16% x 4/730 = 0.09 percentage points. The
        # exact figure is the root of a series whose dates all moved, so there is no closed
        # form to check it against, and inventing a tighter bound would be asserting the
        # implementation.
        #
        # The band does **not** rule out a fee, and saying it did would be over-claiming: a
        # 0.10% exit fee moves the two rates 0.00143 apart, inside the 0.002 bound. What rules
        # a fee out is the sibling assertion above -- a fee changes what *arrives*, and
        # `reaches` is equal at the project tolerance, which fails for a fee as small as
        # 0.05%. The two assertions together say "the dates moved and the amounts did not".
        shipped = _outcome(fixtures.declared(), fixtures.hurdle_tuple(), AT_ISSUE)
        instant = _outcome(
            fixtures.without_latency(fixtures.declared()), fixtures.hurdle_tuple(), AT_ISSUE
        )
        slow, quick = shipped.implied_rate, instant.implied_rate
        assert isinstance(slow, NominalRate)
        assert isinstance(quick, NominalRate)
        assert 0.0 < quick.value - slow.value < 0.002

    def test_the_arrivals_are_three_days_after_the_releases(self) -> None:
        # The mechanism behind the gap, so the band above rests on something checkable.
        for arrival in _outcome(fixtures.declared(), fixtures.hurdle_tuple(), AT_ISSUE).arrivals:
            assert (arrival.arrived_on - arrival.released_on).days == 3


class TestEveryTupleOfferedLandsInExactlyOneOfTheThreePlaces:
    """Ranked, not comparable, or refused -- a **partition**, not a total that adds up.

    A silent exclusion is how a comparison comes to recommend the only option left standing,
    and here the missing ones would be precisely the options nobody has finished declaring.
    Counting the three lists and comparing the total against the number offered does not catch
    that: one tuple in two buckets and another in none sums correctly. So the keys are
    compared as sets, and duplicates are ruled out separately.
    """

    def _all_three(self) -> Registries:
        """A twin of the free way in, and a way out whose flat fee exceeds every release."""
        registries = fixtures.with_new_route(
            fixtures.declared(),
            fixtures.route(
                "test_twin_in",
                origin="monobank_uah",
                destination="inzhur",
                direction="inbound",
                partner=fixtures.DOMESTIC_OUT,
            ),
        )
        return fixtures.with_new_route(
            registries,
            fixtures.route(
                "test_ruinous_out",
                origin="inzhur",
                destination="monobank_uah",
                direction="exit",
                fee_fixed=20_000.0,
            ),
        )

    def _offered(self) -> tuple[Tuple, ...]:
        """One tuple bound for each of the three places, so the partition has work to do."""
        return (
            fixtures.replace(
                fixtures.hurdle_tuple(),
                route_in=fixtures.FundingPath(
                    destination_id="inzhur",
                    stream_id=fixtures.SALARY,
                    route_id="test_twin_in",
                ),
            ),
            fixtures.hurdle_tuple(route_out=fixtures.DeclaredExit(route_id="test_ruinous_out")),
            fixtures.replace(
                fixtures.hurdle_tuple(),
                route_in=fixtures.FundingPath(
                    destination_id="inzhur",
                    stream_id=fixtures.SALARY,
                    route_id="no_such_route",
                ),
            ),
        )

    def test_the_three_lists_partition_the_tuples_offered(self) -> None:
        comparison = _ranked(self._all_three(), self._offered())
        landed = [
            *(outcome.key for outcome in comparison.ranked),
            *(outcome.key for outcome in comparison.not_comparable),
            *(item.key for item in comparison.refused),
        ]
        assert len(landed) == len(set(landed))
        assert set(landed) == {*self._offered(), fixtures.hurdle_tuple()}

    def test_each_of_the_three_places_is_actually_occupied(self) -> None:
        # Otherwise the partition above would hold on a comparison that ranked everything, and
        # the two lists it exists to police would never be exercised at all.
        comparison = _ranked(self._all_three(), self._offered())
        assert len(comparison.ranked) == 2
        assert len(comparison.not_comparable) == 1
        assert len(comparison.refused) == 1


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
        comparison = _ranked(fixtures.declared(), others)
        assert 0 <= comparison.benchmark < len(comparison.ranked)

    def test_the_benchmark_listed_twice_is_evaluated_once(self) -> None:
        # Otherwise a comparison would rank the hurdle against itself and report a tie with
        # itself, which is a sentence nobody should have to read.
        comparison = _ranked(fixtures.declared(), (fixtures.hurdle_tuple(),))
        assert len(comparison.ranked) == 1

    def test_when_nothing_beats_the_hurdle_the_output_says_so_plainly(self) -> None:
        # The answer this product exists to be able to give (FR-011). A second OVDP tuple
        # through a route that charges 5% cannot beat the free one, and `beats_benchmark`
        # being empty is that verdict as a value rather than as something a reader infers
        # from the order of a list.
        registries = fixtures.with_new_route(
            fixtures.declared(),
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
            fixtures.declared(),
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
