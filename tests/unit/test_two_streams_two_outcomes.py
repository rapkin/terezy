"""SC-004 and FR-010: one instrument, two streams, two outcomes -- and no cost without a key.

`SIMULATOR_SPEC.md` §4.3.1's finding is that the same acquisition is nearly free from one
income and five to ten percent from another. Feature 002 made that true of a *currency
balance*; this suite makes it true of a **holding**, which is the whole point of the join.

The two streams here are both hryvnia, and deliberately so. A dollar stream funding a hryvnia
fund would differ in the ramp *and* in whether a rate exists at all
(``tests/unit/test_rate_and_horizon_boundaries.py`` covers that separately), and a fixture
differing in two things lets a test pass for the other reason.

**What each class isolates**, because the two questions are different and the second one is
the one that was untested. A stream's contribution to a *cost* runs through the route: its
currency and its arrival venue decide which declared routes can carry its money at all, so two
streams that genuinely differ are also two routes, and the first class below measures that
difference. Two hryvnia streams arriving at the same venue are cost-identical over one route --
and they are still **two tuples**, with two keys, and the way out of each is charged under its
own. The second class holds the route fixed, varies only the stream, and reads that key off a
refusal rather than inferring it from a figure that would differ anyway.

The instrument is ``inzhur_miltech``, which declares no buyable increment, so the ramp
difference flows through the purchase proportionally instead of being rounded away by a whole
unit. That is not a convenience: with a bond's whole-unit rule two ramps a hundred hryvnia
apart can buy the *same* nine units, and the difference this suite exists to show would land
entirely in the undeployed remainder.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from terezy.core.decision.tuple_outcome import Registries, evaluate
from terezy.core.primitives.rates import NominalRate
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.tuple import Tuple, TupleOutcome, WayOutUnusable
from terezy.core.routes.path import FundingPath
from tests import tuple_registries as fixtures

FREE_ROUTE: Final = "test_free_in"
COSTLY_ROUTE: Final = "test_one_percent_in"
SECOND_STREAM: Final = "salary_uah_second"
RAMP_PCT: Final = 0.01


def _registries() -> Registries:
    """Two hryvnia streams landing at the same venue, and two ways on to `inzhur`.

    The second stream is a copy of the owner's declared salary with a different id, so the two
    differ in **nothing** except which income they are -- which is exactly the term FR-008 says
    a cost must be keyed by.
    """
    registries = fixtures.with_stream(
        fixtures.declared(),
        replace(fixtures.declared().streams[fixtures.SALARY], id=SECOND_STREAM),
    )
    for route_id, fee in ((FREE_ROUTE, 0.0), (COSTLY_ROUTE, RAMP_PCT)):
        registries = fixtures.with_new_route(
            registries,
            fixtures.route(
                route_id,
                origin="monobank_uah",
                destination="inzhur",
                direction="inbound",
                partner=fixtures.DOMESTIC_OUT,
                fee_pct=fee,
            ),
        )
    return registries


def _tuple(stream_id: str, route_id: str) -> Tuple:
    return replace(
        fixtures.fund_tuple(
            fixtures.MILTECH,
            exit_on=fixtures.MILTECH_EXIT,
            stream_id=stream_id,
            yield_point=fixtures.MILTECH_POINT,
        ),
        route_in=FundingPath(destination_id="inzhur", stream_id=stream_id, route_id=route_id),
    )


def _outcome(candidate: Tuple) -> TupleOutcome:
    outcome = evaluate(
        candidate,
        amount=fixtures.AMOUNT,
        horizon=fixtures.DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END),
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=_registries(),
    )
    assert isinstance(outcome, TupleOutcome), outcome
    return outcome


class TestTheSameInstrumentFromTwoStreamsIsTwoOutcomes:
    """FR-010: the key is all five terms, so two streams cannot share one figure."""

    def test_the_two_outcomes_differ_by_exactly_the_ramp_difference(self) -> None:
        #   free route:  10 000.00 arrives
        #   1% route:     9 900.00 arrives
        # The fund declares no buyable increment and the shipped way out charges nothing, so
        # everything downstream scales by 9 900 / 10 000 = 0.99 exactly. A difference of any
        # other size means a term was applied to the departing amount somewhere.
        free = _outcome(_tuple(fixtures.SALARY, FREE_ROUTE))
        costly = _outcome(_tuple(SECOND_STREAM, COSTLY_ROUTE))
        assert is_close(costly.reaches.amount / free.reaches.amount, 1.0 - RAMP_PCT)
        assert is_close(free.reaches.amount - costly.reaches.amount, free.reaches.amount * RAMP_PCT)

    def test_the_expensive_stream_returns_a_lower_rate(self) -> None:
        # The same outlay leaves both streams and less of it is invested, so the money-weighted
        # return is lower -- which is the sentence this project exists to be able to write about
        # a holding rather than about a transfer.
        free = _outcome(_tuple(fixtures.SALARY, FREE_ROUTE)).implied_rate
        costly = _outcome(_tuple(SECOND_STREAM, COSTLY_ROUTE)).implied_rate
        assert isinstance(free, NominalRate)
        assert isinstance(costly, NominalRate)
        assert costly.value < free.value

    def test_each_outcome_names_its_own_stream_and_its_own_route(self) -> None:
        # The key, read back. An outcome that could not say which income paid for the trip is
        # a figure about nothing (FR-008), and there is no shape here for one to take.
        free = _outcome(_tuple(fixtures.SALARY, FREE_ROUTE))
        costly = _outcome(_tuple(SECOND_STREAM, COSTLY_ROUTE))
        assert free.key.stream_id == fixtures.SALARY
        assert costly.key.stream_id == SECOND_STREAM
        assert free.key.route_in.destination_id == costly.key.route_in.destination_id
        assert free.key != costly.key

    def test_the_ramp_line_differs_and_the_instrument_line_does_not(self) -> None:
        # Where the difference lives, stated as an assertion: the access cost, not the asset.
        # "Most of the gap is the ramp, not the asset" is the sentence the parts exist to let
        # a reader check, and here the asset's own terms are identical in both tuples.
        free = _outcome(_tuple(fixtures.SALARY, FREE_ROUTE))
        costly = _outcome(_tuple(SECOND_STREAM, COSTLY_ROUTE))
        ramp = {
            outcome.key.stream_id: next(
                line.amount.amount for line in outcome.parts if line.part == "ramp_in"
            )
            for outcome in (free, costly)
        }
        assert ramp[fixtures.SALARY] == 0.0
        assert is_close(ramp[SECOND_STREAM], -fixtures.AMOUNT.amount * RAMP_PCT)
        assert free.key.instrument_id == costly.key.instrument_id


class TestNoFigureIsAttributableToTheInstrumentAlone:
    """The prohibition Principle VI names by name, checked on the outcome record itself."""

    def test_an_outcome_cannot_be_built_without_the_whole_key(self) -> None:
        # `TupleOutcome.key` is required and is a `Tuple`, which is five required terms with no
        # partial form. "The outcome of holding MilTech" therefore has no type to live in --
        # it is not a discouraged call but an expression that does not construct.
        outcome = _outcome(_tuple(fixtures.SALARY, FREE_ROUTE))
        assert outcome.key.instrument_id
        assert outcome.key.stream_id
        assert outcome.key.route_in.destination_id
        assert outcome.key.route_out is not None
        assert outcome.key.exit_terms is not None


class TestTheStreamIsTheTermAndNotTheRouteWearingItsName:
    """One route, two streams. Whatever differs here differs because of the *income*."""

    def test_two_streams_over_one_route_are_two_tuples_with_two_keys(self) -> None:
        # Cost-identical, and still two entries. A comparison that collapsed them would be
        # answering "what does MilTech return" -- the question Principle VI says has no answer.
        first = _outcome(_tuple(fixtures.SALARY, FREE_ROUTE))
        second = _outcome(_tuple(SECOND_STREAM, FREE_ROUTE))
        assert first.key != second.key
        assert first.key.route_in == replace(second.key.route_in, stream_id=fixtures.SALARY)
        assert is_close(first.reaches.amount, second.reaches.amount)

    def test_the_way_out_cost_is_keyed_by_the_stream_that_funded_the_holding(self) -> None:
        # The key, **read** -- not inferred from two amounts that would have differed anyway.
        # A way out that will not carry what the holding released refuses with the candidate it
        # was costing, and that candidate's `stream_id` is the join's own answer to "which
        # income is this exit a cost of". Hard-coding it would blend the two silently: the same
        # exit route repatriating two holdings bought from two incomes is two figures.
        blocked = fixtures.with_leg(
            _registries(),
            fixtures.DOMESTIC_OUT,
            minimum=fixtures.Money(1_000_000.0, fixtures.UAH, fixtures.prov.EMPTY),
        )
        keyed = {}
        for stream in (fixtures.SALARY, SECOND_STREAM):
            refusal = evaluate(
                _tuple(stream, FREE_ROUTE),
                amount=fixtures.AMOUNT,
                horizon=fixtures.DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END),
                as_of=fixtures.AS_OF,
                continuation=fixtures.HOLD_AS_CASH,
                registries=blocked,
            )
            assert isinstance(refusal, WayOutUnusable), refusal
            keyed[stream] = refusal.refused.path.stream_id
        assert keyed == {fixtures.SALARY: fixtures.SALARY, SECOND_STREAM: SECOND_STREAM}
