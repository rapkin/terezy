"""SC-015: a round trip whose way out is reachable only by chaining, and the case where none is.

FR-012, the owner's decision of 2026-08-22: **a chain of separately declared exit routes
satisfies 002 FR-027's "separately declared exit route"**. His reasoning is recorded because it
cuts the other way from 002's caution and deliberately so -- in 002 the danger was a round-trip
figure resting on an exit **nobody had observed**, namely the inbound route reversed; here every
link of the chain *is* an observation, so composing them invents nothing. *Everything must have
at least one way out*, and "a way out, at least through one other venue" is what this makes real.

**Both directions are verified, because only one of them is the risk.** A round trip that exists
is arithmetic and is hand-computed below. A round trip that does **not** exist is where a
one-way figure gets quietly promoted into the gap, so the second half of this module is a
registry from which nothing chains, and the assertion is that *exit cost unknown* still stands
and the candidate stays out of the round-trip ranking (002 FR-030).

## The arithmetic, continuing the inbound example

The way in is ``tests/worked_examples/test_composed_arithmetic.py``'s: 10 000 UAH leaves,
219.000000 USD arrives at the broker, and 802.00 UAH has been charged. The way out is two
declared exit segments -- and it is **not** the way in reversed: its flat fee is 2 dollars
against the way in's 1, and the sell price is 39.5 against the buy price of 45.

```
arriving at the broker                                 = 219.000000 USD  (802.00 UAH charged)

out_broker_to_exchange   one transfer leg, flat 2 USD
    fixed        =                                         2.000000 USD
    leaving      = 219 - 2                               = 217.000000 USD
    valued in UAH at the reference (42): 2 * 42          =  84.000000 UAH

out_exchange_to_home     one fx leg, USD -> UAH at the sell price
    price        = 42 + (-2.5)                           =  39.5     UAH per USD
    arriving     = 217 * 39.5                            = 8571.50   UAH
    spread cost  = 217 * (1 - 39.5/42), valued in UAH    = 217 * 2.5 = 542.50 UAH

round trip     spread     666.666666 + 542.500000       = 1209.166666 UAH
               percentage                                 =   93.333333 UAH
               fixed       42 + 84                        =  126.000000 UAH
               total                                      = 1428.500000 UAH
               fraction    1428.5 / 10 000                =    0.14285
```

**The independent check**: 8 571.50 UAH came back out of 10 000 UAH sent, so 1 428.50 went to
the round trip -- the same figure, reached by subtraction rather than by adding components.

## The third shape of a way out, and the tension it closes

``EXIT_BY_IDENTITY`` is the destination already **being** a declared spendable endpoint. Feature
003's FR-002 says such a pair satisfies its own exit requirement; 002's costing required a
declared partner and refused it. ``features.toml`` recorded the disagreement as
``identity-exit-vs-partner-requirement`` and named composition as the thing that would make it
real. The last class below is that reconciliation, with both sides of it asserted.
"""

from __future__ import annotations

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.composed import Enumeration, SegmentBound
from terezy.core.results.ramp import (
    CostComponent,
    ExitCostUnknown,
    NothingComparable,
    RampCost,
    RoundTripCost,
)
from terezy.core.routes import compose, cost, ranking
from terezy.core.routes.path import (
    EXIT_BY_IDENTITY,
    FROM_THE_DECLARATION,
    ComposedExit,
    ComposedPath,
    ExitChoice,
    FundingPath,
    Journey,
    candidate_id,
)
from tests import composed_registries as fixtures

pytestmark = pytest.mark.worked_example

SENT = 10_000.0
ARRIVED_AT_BROKER = 219.0
"""What the inbound chain delivers -- hand-computed in ``test_composed_arithmetic.py``."""

EXIT_FIXED_USD = 2.0
LEAVING_EXCHANGE = ARRIVED_AT_BROKER - EXIT_FIXED_USD
"""217.000000 USD."""

SELL_PRICE = fixtures.REFERENCE + fixtures.SELL_PREMIUM
"""39.5 UAH per dollar. The *sell* side: a real book is asymmetric, and a fixture that could
only express a symmetric spread would let a round trip computed as twice the one way pass."""

CAME_BACK = LEAVING_EXCHANGE * SELL_PRICE
"""8 571.50 UAH."""

EXIT_SPREAD_UAH = LEAVING_EXCHANGE * (1.0 - SELL_PRICE / fixtures.REFERENCE) * fixtures.REFERENCE
"""542.50 UAH -- ``217 * 2.5``. On the sell side the cost and the rate-space spread coincide."""

EXIT_FIXED_UAH = EXIT_FIXED_USD * fixtures.REFERENCE
"""84.00 UAH."""

INBOUND_SPREAD_UAH = SENT * (1.0 - fixtures.REFERENCE / (fixtures.REFERENCE + fixtures.BUY_PREMIUM))
INBOUND_PERCENTAGE_UAH = (
    (SENT / (fixtures.REFERENCE + fixtures.BUY_PREMIUM)) * 0.01 * fixtures.REFERENCE
)
INBOUND_FIXED_UAH = 1.0 * fixtures.REFERENCE

ROUND_TRIP_TOTAL = (
    INBOUND_SPREAD_UAH
    + EXIT_SPREAD_UAH
    + INBOUND_PERCENTAGE_UAH
    + INBOUND_FIXED_UAH
    + EXIT_FIXED_UAH
)
"""1 428.50 UAH."""

ROUND_TRIP_FRACTION = ROUND_TRIP_TOTAL / SENT
"""0.14285."""

CHAIN = ComposedPath(
    destination_id=fixtures.BROKER,
    stream_id=fixtures.SALARY.id,
    segments=("in_salary_to_exchange", "in_exchange_to_broker"),
)
EXIT_CHAIN = ComposedExit(segments=("out_broker_to_exchange", "out_exchange_to_home"))


def _uah(amount: float) -> Money:
    return Money(amount, Currency.UAH, prov.EMPTY)


def _costed(
    world: fixtures.Registry,
    *,
    path: ComposedPath | FundingPath = CHAIN,
    exit_path: ExitChoice = EXIT_CHAIN,
) -> RampCost:
    outcome = cost.cost_one(
        path,
        _uah(SENT),
        exit_path=exit_path,
        routes=world.routes,
        channels=world.channels,
        streams=world.streams,
        kinds=world.kinds,
        on_date=fixtures.ON_DATE,
        as_of=fixtures.AS_OF,
    )
    assert isinstance(outcome, RampCost), outcome
    return outcome


class TestAWayOutReachableOnlyByChaining:
    def test_the_registry_declares_no_single_exit_route_from_the_broker_home(self) -> None:
        """Without this the example proves nothing: a declared broker→home exit would make the
        chain unnecessary."""
        world = fixtures.two_hop()
        assert not [
            route
            for route in world.routes.values()
            if route.direction == "exit"
            and route.origin == fixtures.BROKER
            and route.destination == fixtures.HOME
        ]

    def test_the_search_finds_the_chain_out_and_it_ends_somewhere_spendable(self) -> None:
        world = fixtures.two_hop()
        result = compose.compose(
            routes=world.routes,
            stream=world.streams[fixtures.SALARY.id],
            destination=fixtures.BROKER_USD,
            direction="exit",
            regime_id=fixtures.REGIME_ID,
            bound=SegmentBound(max_segments=3),
            spendable=world.spendable,
        )
        assert isinstance(result, Enumeration), result
        assert [candidate_id(candidate) for candidate in result.candidates] == [
            "out_broker_to_exchange+out_exchange_to_home"
        ]

    def test_the_amount_that_comes_back_is_the_hand_computed_one(self) -> None:
        round_trip = _costed(fixtures.two_hop()).round_trip
        assert isinstance(round_trip, RoundTripCost), round_trip
        assert is_close(round_trip.arrived.amount, CAME_BACK)
        assert round_trip.arrived.currency is Currency.UAH

    def test_the_round_trip_fraction_is_the_hand_computed_one(self) -> None:
        round_trip = _costed(fixtures.two_hop()).round_trip
        assert isinstance(round_trip, RoundTripCost)
        assert is_close(round_trip.fraction, ROUND_TRIP_FRACTION)

    def test_the_total_agrees_with_the_check_by_subtraction(self) -> None:
        """8 571.50 came back out of 10 000 sent: the gap is the round trip, reached without
        adding a single component."""
        round_trip = _costed(fixtures.two_hop()).round_trip
        assert isinstance(round_trip, RoundTripCost)
        assert is_close(SENT - round_trip.arrived.amount, ROUND_TRIP_TOTAL)

    def test_each_round_trip_component_is_the_hand_computed_one(self) -> None:
        round_trip = _costed(fixtures.two_hop()).round_trip
        assert isinstance(round_trip, RoundTripCost)
        assert is_close(
            round_trip.components[CostComponent.CONVERSION_SPREAD].amount,
            INBOUND_SPREAD_UAH + EXIT_SPREAD_UAH,
        )
        assert is_close(
            round_trip.components[CostComponent.FIXED_FEE].amount,
            INBOUND_FIXED_UAH + EXIT_FIXED_UAH,
        )

    def test_the_round_trip_is_not_twice_the_one_way(self) -> None:
        """The book is asymmetric, so a round trip computed as twice the way in would be
        wrong -- and would look entirely plausible."""
        costed = _costed(fixtures.two_hop())
        assert isinstance(costed.round_trip, RoundTripCost)
        assert not is_close(costed.round_trip.fraction, 2.0 * costed.one_way.fraction)

    def test_the_attribution_names_all_four_segments_in_order(self) -> None:
        """FR-020 over a round trip: the way in's segments, then the way out's, numbered on."""
        costed = _costed(fixtures.two_hop())
        assert isinstance(costed.round_trip, RoundTripCost)
        assert [entry.route_id for entry in costed.round_trip.by_segment] == [
            "in_salary_to_exchange",
            "in_exchange_to_broker",
            "out_broker_to_exchange",
            "out_exchange_to_home",
        ]

    def test_the_exit_chain_is_part_of_the_figure_s_identity(self) -> None:
        """FR-012's first consequence: a round-trip figure is keyed per exit chain, so the
        record says which way out it is a figure *for*."""
        assert _costed(fixtures.two_hop()).exit_path == EXIT_CHAIN


class TestWhereNothingChainsTheGapStandsUnchanged:
    """002 FR-030, which FR-012 leaves exactly as it was."""

    def test_no_exit_chain_reaches_a_spendable_endpoint(self) -> None:
        """From the broker the only declared way out stops at the exchange, and dollars at an
        exchange are not spent -- they are held."""
        world = fixtures.stranded()
        result = compose.compose(
            routes=world.routes,
            stream=world.streams[fixtures.SALARY.id],
            destination=fixtures.BROKER_USD,
            direction="exit",
            regime_id=fixtures.REGIME_ID,
            bound=SegmentBound(max_segments=3),
            spendable=world.spendable,
        )
        assert isinstance(result, Enumeration), result
        assert result.candidates == ()

    def test_the_candidate_reports_exit_cost_unknown_and_names_what_is_missing(self) -> None:
        costed = cost.cost_one(
            CHAIN,
            _uah(SENT),
            routes=fixtures.stranded().routes,
            channels=fixtures.stranded().channels,
            streams=fixtures.stranded().streams,
            kinds=fixtures.stranded().kinds,
            on_date=fixtures.ON_DATE,
            as_of=fixtures.AS_OF,
        )
        assert isinstance(costed, RampCost), costed
        assert isinstance(costed.round_trip, ExitCostUnknown)
        assert costed.round_trip.missing_partner_for == "in_exchange_to_broker"
        assert costed.exit_path is None

    def test_the_one_way_figure_is_real_and_is_not_promoted(self) -> None:
        """ "Most of the cost" is not the cost. The one-way figure is reported, in a field named
        one way, and nothing copies it into the round-trip slot."""
        costed = cost.cost_one(
            CHAIN,
            _uah(SENT),
            routes=fixtures.stranded().routes,
            channels=fixtures.stranded().channels,
            streams=fixtures.stranded().streams,
            kinds=fixtures.stranded().kinds,
            on_date=fixtures.ON_DATE,
            as_of=fixtures.AS_OF,
        )
        assert isinstance(costed, RampCost)
        assert is_close(costed.one_way.arrived.amount, ARRIVED_AT_BROKER)
        assert not isinstance(costed.round_trip, RoundTripCost)

    def test_it_is_kept_out_of_the_round_trip_ranking_and_reported_separately(self) -> None:
        world = fixtures.stranded()
        outcome = ranking.rank(
            [CHAIN],
            _uah(SENT),
            routes=world.routes,
            channels=world.channels,
            streams=world.streams,
            kinds=world.kinds,
            on_date=fixtures.ON_DATE,
            as_of=fixtures.AS_OF,
        )
        assert isinstance(outcome, NothingComparable), outcome
        assert [candidate_id(entry.path) for entry in outcome.not_comparable] == [
            "in_salary_to_exchange+in_exchange_to_broker"
        ]
        assert "declared exit route" in outcome.reason


class TestADestinationThatIsItselfSpendable:
    """The recorded tension between feature 003's FR-002 and 002's partner requirement.

    ``features.toml`` calls it ``identity-exit-vs-partner-requirement`` and says composition is
    the thing that makes it real. Both halves are asserted here: what the disagreement looked
    like, and what the sentinel does about it.
    """

    PATH = FundingPath(
        destination_id=fixtures.HOME,
        stream_id=fixtures.SALARY.id,
        route_id="in_salary_to_home",
    )

    def test_the_destination_is_declared_spendable_and_the_route_declares_no_partner(
        self,
    ) -> None:
        """The precondition, and the whole of the disagreement: coverage marks this pair ready
        by identity while 002's costing found no partner to charge."""
        world = fixtures.spendable_destination()
        assert any(
            endpoint.venue_id == fixtures.HOME and endpoint.currency is Currency.UAH
            for endpoint in world.spendable
        )
        assert world.routes["in_salary_to_home"].partner_route is None

    def test_without_the_sentinel_the_declaration_still_yields_exit_cost_unknown(self) -> None:
        """002's behaviour, unchanged and still reachable. The sentinel is a *statement the
        caller makes*, not an inference the engine draws from a venue id -- because whether a
        venue is spendable is the owner's declaration and not costing's to guess."""
        world = fixtures.spendable_destination()
        costed = _costed(world, path=self.PATH, exit_path=FROM_THE_DECLARATION)
        assert isinstance(costed.round_trip, ExitCostUnknown)
        assert costed.exit_path is None

    def test_with_the_sentinel_the_round_trip_exists_and_costs_the_way_in(self) -> None:
        """The money has arrived somewhere the owner spends from, so the journey is complete.

        The round-trip figure equals the one-way figure -- **not** because a way out was assumed
        free, but because there is no way out left to travel. That is why the sentinel is a
        distinct value rather than a zero-length chain: a round trip that costs nothing because
        there is nothing to do is a different claim from one whose fees happened to cancel.
        """
        world = fixtures.spendable_destination()
        costed = _costed(world, path=self.PATH, exit_path=EXIT_BY_IDENTITY)
        assert isinstance(costed.round_trip, RoundTripCost)
        assert costed.exit_path is EXIT_BY_IDENTITY
        assert is_close(costed.round_trip.fraction, costed.one_way.fraction)
        assert is_close(costed.round_trip.arrived.amount, costed.one_way.arrived.amount)

    def test_the_identity_round_trip_charges_the_way_in_and_nothing_more(self) -> None:
        """0.5% of 10 000 is 50 UAH, and the round trip is 50 UAH -- the way in, in full, with
        no exit segment appended to the attribution."""
        world = fixtures.spendable_destination()
        costed = _costed(world, path=self.PATH, exit_path=EXIT_BY_IDENTITY)
        assert isinstance(costed.round_trip, RoundTripCost)
        assert is_close(costed.round_trip.components[CostComponent.PERCENTAGE_FEE].amount, 50.0)
        assert [entry.route_id for entry in costed.round_trip.by_segment] == ["in_salary_to_home"]

    def test_a_comparison_can_therefore_rank_it(self) -> None:
        """The point of the reconciliation: the pair coverage calls ready is one costing can
        price, so a destination that is itself spendable is comparison-ready rather than
        permanently excluded."""
        world = fixtures.spendable_destination()
        outcome = ranking.rank(
            [Journey(path=self.PATH, exit_path=EXIT_BY_IDENTITY)],
            _uah(SENT),
            routes=world.routes,
            channels=world.channels,
            streams=world.streams,
            kinds=world.kinds,
            on_date=fixtures.ON_DATE,
            as_of=fixtures.AS_OF,
        )
        assert not isinstance(outcome, NothingComparable), outcome
        assert len(outcome.costed) == 1
        assert outcome.not_comparable == ()
