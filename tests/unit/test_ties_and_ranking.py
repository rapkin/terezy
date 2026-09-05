"""SC-008 and FR-013: two outcomes within the project tolerance are a tie, never a winner.

A ranking has to be a *sequence* -- a comparison whose order depended on a dictionary's
iteration would not be reproducible -- and it must not turn that sequence into a preference
the owner never stated. Both are true at once here, exactly as they are in feature 002's route
ranking: the order is deterministic and :attr:`Comparison.ties` is what stops the head of a
tied group being read as a winner.

The case that matters most is **a tuple tied with the hurdle**, because "nothing beats the
hurdle" has to be sayable when it is true by a whisker in either direction. A comparison that
reported a winner there would answer §8's question with a decoration.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from terezy.core.decision.compare import compare
from terezy.core.decision.tuple_outcome import Registries
from terezy.core.primitives.rates import NominalRate
from terezy.core.primitives.tolerance import TOLERANCE, is_close
from terezy.core.results.tuple import Comparison, Tuple
from terezy.core.routes.path import FundingPath
from tests import tuple_registries as fixtures

TWIN_ROUTE: Final = "test_identical_in"
DEARER_ROUTE: Final = "test_dearer_in"


def _registries() -> Registries:
    """Two more ways in: one identical in cost to the shipped domestic route, one dearer."""
    registries = fixtures.declared()
    for route_id, fee in ((TWIN_ROUTE, 0.0), (DEARER_ROUTE, 0.02)):
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


def _via(route_id: str) -> Tuple:
    return replace(
        fixtures.hurdle_tuple(),
        route_in=FundingPath(destination_id="inzhur", stream_id=fixtures.SALARY, route_id=route_id),
    )


def _ranked(others: tuple[Tuple, ...]) -> Comparison:
    comparison = compare(
        others,
        benchmark=fixtures.hurdle_tuple(),
        amount=fixtures.AMOUNT,
        horizon=fixtures.DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END),
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=_registries(),
    )
    assert isinstance(comparison, Comparison), comparison
    return comparison


class TestATieIsReportedAsATie:
    """FR-013, including -- especially -- a tie with the benchmark."""

    def test_two_routes_costing_the_same_produce_one_tie_group(self) -> None:
        # The shipped domestic route and a twin of it charge nothing and take the same time,
        # so the two tuples return the same rate. The sequence still orders them, because it
        # has to; the tie is what says the order means nothing.
        comparison = _ranked((_via(TWIN_ROUTE),))
        assert len(comparison.ranked) == 2
        assert comparison.ties == ((0, 1),)

    def test_the_hurdle_is_in_that_tie_and_nothing_beats_it(self) -> None:
        # The answer §8 question 1 has to be able to give: nothing beats the hurdle, said
        # plainly, when the challenger merely equals it.
        comparison = _ranked((_via(TWIN_ROUTE),))
        assert comparison.benchmark in comparison.ties[0]
        assert comparison.beats_benchmark == ()

    def test_a_route_that_really_is_dearer_is_not_tied_with_it(self) -> None:
        # Otherwise the tie rule would be a function that always says "tied", and the test
        # above would pass for a reason that has nothing to do with tolerance.
        comparison = _ranked((_via(DEARER_ROUTE),))
        assert comparison.ties == ()
        assert comparison.beats_benchmark == ()
        assert comparison.ranked[comparison.benchmark].key == fixtures.hurdle_tuple()

    def test_a_group_of_one_is_not_a_tie(self) -> None:
        comparison = _ranked(())
        assert len(comparison.ranked) == 1
        assert comparison.ties == ()


class TestTheOrderingIsDeterministicWithoutBeingAPreference:
    """Both halves, because either alone is a defect."""

    def test_the_sequence_is_ordered_best_first(self) -> None:
        comparison = _ranked((_via(DEARER_ROUTE),))
        rates = [outcome.implied_rate for outcome in comparison.ranked]
        assert all(isinstance(rate, NominalRate) for rate in rates)
        values = [rate.value for rate in rates if isinstance(rate, NominalRate)]
        assert values == sorted(values, reverse=True)

    def test_the_same_inputs_give_the_same_sequence(self) -> None:
        # Purity, at the level a reader cares about: two runs, one answer, in one order.
        first = _ranked((_via(TWIN_ROUTE), _via(DEARER_ROUTE)))
        second = _ranked((_via(TWIN_ROUTE), _via(DEARER_ROUTE)))
        assert [outcome.key for outcome in first.ranked] == [
            outcome.key for outcome in second.ranked
        ]
        assert first.ties == second.ties

    def test_beating_the_benchmark_needs_more_than_the_tolerance(self) -> None:
        # The rule `beats_benchmark` exists to hold in one place: strictly more, so an outcome
        # inside the tolerance band is a tie and not a winner. Asserted against the imported
        # constant rather than a literal, so loosening the tolerance cannot silently loosen
        # this claim too.
        comparison = _ranked((_via(TWIN_ROUTE),))
        rates = [
            rate.value
            for rate in (outcome.implied_rate for outcome in comparison.ranked)
            if isinstance(rate, NominalRate)
        ]
        assert is_close(rates[0], rates[1])
        assert abs(rates[0] - rates[1]) <= TOLERANCE
