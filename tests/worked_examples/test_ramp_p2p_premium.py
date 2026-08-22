"""G2, SC-001, SC-002: the §4.3.1 number, computed and checked against hand arithmetic.

This is the number the whole feature exists to produce. ``SIMULATOR_SPEC.md`` §4.3.1 makes
the largest single claim in the product -- *a P2P premium of +2 to +4 UAH per dollar is
roughly 4.8-9.5% one way* -- and everything downstream of it, including whether a 15.5%
domestic yield is a hurdle or a fact, rests on that figure being right.

**Every number below is derived by hand, in the comment beside its assertion.** The
arithmetic is deliberately reducible to one division per leg, because the fixture declares
no fees at all: a route whose only cost is its channel's spread is the only shape in which
"the spread is 3/45" can be checked rather than reconciled.

## The arithmetic, once, in full

A premium ``p`` against a reference ``r`` means the price transacted at is ``r + p``. With
``r = 42`` and a buy premium of ``+3`` the P2P price is **45 UAH per dollar**, which is what
the screen says; with a sell premium of ``-3`` the price back is **39**. Sending 10 000 UAH::

    in    10 000 / 45            =   222.222222... USD   (what the venue hands over)
    out     222.222222... x 39   = 8 666.666666... UAH   (what comes back)

so the two figures this module pins are::

    one way    cost fraction = 1 - 42/45 = 3/45 = 1/15 = 0.0666666...   =  6.67%
    round trip cost fraction = 1 - 39/45 = 6/45 = 2/15 = 0.1333333...   = 13.33%

The one-way figure is ``p / (r + p)`` -- the fraction of the money the spread actually took.
The round-trip figure is ``1 - (sell price / buy price)``, which needs no reference rate at
all: what you get back over what you put in. Both are labelled, and neither is the other
(FR-002).

## §4.3.1's own figure is also here, and it is a different number

``3 / 42 = 7.14%`` is the spread over the *reference rate*, which is what §4.3.1 quotes and
what ``channels.spread_over_reference`` reports. ``3 / 45 = 6.67%`` is the cost. They differ
on the buy side because a fraction of your money and a fraction of a rate are different
quantities, and an earlier implementation of this project reported the first as the second --
reproducing §4.3.1 exactly while understating the arriving amount by 1.13 USD on this very
purchase. Both are asserted below, each under its own name, because SC-002 asks for both
present and each labelled.

⚙ **Where the two figures live is not symmetric, and that is worth stating.** The cost
reaches the result record; the rate-space spread does not -- ``RampCost`` has no field for
it, so §4.3.1's own percentage is reachable only through ``channels.spread_over_reference``.
Nothing is lost (the function is public, dated and sourced) but "both figures present, each
labelled" is true of the channel module and not of the result record.

## And then the comparison, which is the actual finding

The last class ranks the P2P route against a fully domestic one that costs nothing. That
comparison -- 13.33% round trip against 0.00% -- is §4.3.1's finding in the form a decision
can use: the ramp, not the asset, is the largest term, and a domestic yield does not have to
beat the offshore return, only the offshore return net of getting there and back.
"""

from __future__ import annotations

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.ramp import (
    CostComponent,
    NothingComparable,
    RampCost,
    Ranking,
    RoundTripCost,
    recommended_cost,
)
from terezy.core.routes import channels, cost, ranking
from terezy.core.routes.channels import Side
from tests.invariants import route_graphs

pytestmark = pytest.mark.worked_example

SENT = 10_000.0
"""What departs, in hryvnia. Round, so the divisions below stay readable."""

REFERENCE = 42.0
"""The stated reference rate: UAH per USD. Invented, like every number in this feature."""

BUY_PREMIUM = 3.0
"""+3 UAH per dollar: the middle of §4.3.1's stated +2 to +4 range."""

SELL_PREMIUM = -3.0
"""-3 UAH per dollar on the way back. A *signed* offset, so the sell price is 42 - 3 = 39."""

BUY_PRICE = REFERENCE + BUY_PREMIUM
"""45 UAH per dollar -- the price a P2P screen would show. Stated so the assertions can be
read against it without recomputing it."""

SELL_PRICE = REFERENCE + SELL_PREMIUM
"""39 UAH per dollar received on the way out."""


def _cost(graph: route_graphs.Graph, *, amount: float = SENT) -> RampCost:
    """Cost one amount along the graph's path, asserting the route was usable.

    The narrowing is the point of the helper: every assertion below is about a *figure*, and
    a ``RouteUnusable`` reaching them would fail on an attribute rather than on the number
    the test is actually about.
    """
    costed = cost.cost_one(
        graph.path,
        Money(amount, Currency.UAH, prov.EMPTY),
        routes=graph.routes,
        channels=graph.channels,
        streams=route_graphs.STREAMS,
        kinds=route_graphs.KINDS,
        on_date=route_graphs.ON_DATE,
        as_of=route_graphs.AS_OF,
    )
    assert isinstance(costed, RampCost), costed
    return costed


def _round_trip(costed: RampCost) -> RoundTripCost:
    """The round-trip figure, asserting it exists.

    ``round_trip`` is a union with ``ExitCostUnknown`` (FR-030), and this fixture declares
    its exit route, so the union is narrowed here once rather than at every assertion.
    """
    assert isinstance(costed.round_trip, RoundTripCost), costed.round_trip
    return costed.round_trip


class TestTheOneWayFigure:
    """SC-002: 6.67% cost, 222.22 USD arriving, at a P2P price of 45."""

    def test_ten_thousand_hryvnia_buys_two_hundred_and_twenty_two_dollars(self) -> None:
        # The arriving amount is the one the venue would really hand over, because the
        # conversion happens at the price transacted at and not at the reference:
        #   10 000 / 45 = 222.22222222222223 USD
        # An implementation that charged the spread and converted the remainder at the
        # reference would report 221.09 here -- 1.13 USD short -- while still reproducing
        # §4.3.1's percentage. That is the bug this assertion exists to catch.
        costed = _cost(route_graphs.p2p_graph())
        assert costed.one_way.arrived.currency is Currency.USD
        assert is_close(costed.one_way.arrived.amount, SENT / BUY_PRICE)
        assert is_close(costed.one_way.arrived.amount, 222.22222222222223)

    def test_the_one_way_cost_is_the_premium_over_the_price(self) -> None:
        #   spread  = 10 000 x 3/45 = 666.6666666666666 UAH
        #   fraction = 666.6667 / 10 000 = 3/45 = 1/15 = 0.06666666666666665
        # Equivalently: 1 - 42/45. What the spread took, as a fraction of what was sent.
        costed = _cost(route_graphs.p2p_graph())
        assert is_close(costed.one_way.fraction, BUY_PREMIUM / BUY_PRICE)
        assert is_close(costed.one_way.fraction, 1.0 / 15.0)
        assert is_close(costed.one_way.fraction, 0.06666666666666665)
        spread = costed.one_way.components[CostComponent.CONVERSION_SPREAD]
        assert spread.currency is Currency.UAH
        assert is_close(spread.amount, SENT * BUY_PREMIUM / BUY_PRICE)
        assert is_close(spread.amount, 666.6666666666666)

    def test_the_whole_cost_is_the_spread_because_the_fixture_declares_no_fees(self) -> None:
        # Stated as an assertion so that a fee leaking into this fixture would be caught
        # here rather than absorbed into the headline percentage. The two fee components
        # are *declared* zeroes, present as keys: "no fee was charged" and "the fee is
        # unknown" are different claims, and an absent key would read as the second.
        costed = _cost(route_graphs.p2p_graph())
        assert costed.one_way.components[CostComponent.PERCENTAGE_FEE].amount == 0.0
        assert costed.one_way.components[CostComponent.FIXED_FEE].amount == 0.0
        assert set(costed.one_way.components) == set(CostComponent)

    def test_the_channel_that_priced_it_is_named(self) -> None:
        # FR-011: the choice of channel changes the number, so the number says which
        # channel it used. One conversion in, so one entry.
        costed = _cost(route_graphs.p2p_graph())
        assert costed.one_way.channels_applied == ("p2p",)

    @pytest.mark.parametrize(
        ("premium", "expected_price", "expected_cost_fraction"),
        [
            # §4.3.1's stated range, at both ends, as the *cost* rather than the spread:
            #   +2 -> price 44, cost 2/44 = 0.045454545...  (4.55%)
            #   +4 -> price 46, cost 4/46 = 0.086956521...  (8.70%)
            # The spread-over-reference figures at the same premiums are 2/42 = 4.76% and
            # 4/42 = 9.52%, which is the "4.8-9.5%" the specification quotes. Both ends
            # are asserted so a formula that happened to be right at +3 still fails.
            (2.0, 44.0, 2.0 / 44.0),
            (4.0, 46.0, 4.0 / 46.0),
        ],
    )
    def test_the_ends_of_the_specification_range(
        self, premium: float, expected_price: float, expected_cost_fraction: float
    ) -> None:
        costed = _cost(route_graphs.p2p_graph(buy_premium=premium))
        assert is_close(costed.one_way.arrived.amount, SENT / expected_price)
        assert is_close(costed.one_way.fraction, expected_cost_fraction)


class TestSectionFourThreeOnesOwnFigureIsReportedBesideTheCost:
    """SC-002: both figures present, each labelled. They are not the same number."""

    def test_the_spread_over_the_reference_rate_reproduces_three_over_forty_two(self) -> None:
        #   3 / 42 = 0.07142857142857142 -> 7.14%, the figure §4.3.1 quotes.
        # Reached through the channel rather than through the cost record, which has no
        # field for it -- see the note in this module's docstring.
        graph = route_graphs.p2p_graph()
        channel = graph.channels["p2p"]
        assert is_close(
            channels.spread_over_reference(channel.buy_side, channel.reference_rate, role=Side.BUY),
            BUY_PREMIUM / REFERENCE,
        )
        assert is_close(
            channels.spread_over_reference(channel.buy_side, channel.reference_rate, role=Side.BUY),
            0.07142857142857142,
        )

    def test_the_cost_is_the_smaller_of_the_two_and_they_are_not_interchangeable(self) -> None:
        # 6.67% against 7.14%. The gap is small enough to look like rounding, which is
        # exactly why it went unnoticed once: p/(r+p) < p/r for any positive premium, and
        # a comparison that used the larger figure as the cost would overstate every P2P
        # route by a sixteenth of its own spread.
        graph = route_graphs.p2p_graph()
        channel = graph.channels["p2p"]
        spread = channels.spread_over_reference(
            channel.buy_side, channel.reference_rate, role=Side.BUY
        )
        costed = _cost(graph)
        assert costed.one_way.fraction < spread
        assert not is_close(costed.one_way.fraction, spread)


class TestTheRoundTripFigure:
    """SC-001, FR-002: in and back out again, from a *declared* exit route."""

    def test_a_symmetric_three_hryvnia_spread_costs_thirteen_and_a_third_percent(self) -> None:
        #   in   10 000 / 45          =   222.222222... USD
        #   out    222.222222... x 39 = 8 666.666666... UAH
        #   cost  10 000 - 8 666.667  = 1 333.333333... UAH
        #   fraction = 1 - 39/45 = 6/45 = 2/15 = 0.13333333333333333
        # No reference rate appears in that last line: a round trip is what you get back
        # over what you put in, and the reference cancels.
        costed = _cost(route_graphs.p2p_graph())
        round_trip = _round_trip(costed)
        assert is_close(round_trip.fraction, 1.0 - SELL_PRICE / BUY_PRICE)
        assert is_close(round_trip.fraction, 2.0 / 15.0)
        assert is_close(round_trip.fraction, 0.13333333333333333)
        assert round_trip.arrived.currency is Currency.UAH
        assert is_close(round_trip.arrived.amount, SENT * SELL_PRICE / BUY_PRICE)
        assert is_close(round_trip.arrived.amount, 8666.666666666666)

    def test_the_round_trip_components_are_the_two_spreads_valued_in_hryvnia(self) -> None:
        #   in  leg spread = 10 000 x 3/45                  = 666.666666... UAH
        #   out leg spread = 222.222222... x 3/42 = 15.873 USD, x 42 = 666.666666... UAH
        #   total                                           = 1 333.333333... UAH
        # The two happen to be equal here because ``amount x p/(r+p)`` and
        # ``(amount/(r+p)) x p`` are the same product. That coincidence is why the
        # asymmetric case below exists.
        round_trip = _round_trip(_cost(route_graphs.p2p_graph()))
        spread = round_trip.components[CostComponent.CONVERSION_SPREAD]
        assert is_close(spread.amount, 2.0 * SENT * BUY_PREMIUM / BUY_PRICE)
        assert is_close(spread.amount, 1333.3333333333333)
        assert is_close(spread.amount, SENT - round_trip.arrived.amount)

    def test_an_asymmetric_spread_is_not_twice_the_one_way_figure(self) -> None:
        # Selling back at 40 rather than 39:
        #   out  222.222222... x 40 = 8 888.888888... UAH
        #   fraction = 1 - 40/45 = 5/45 = 1/9 = 0.1111111111111111
        # One way is still 1/15 = 0.0667, so twice the one way would be 0.1333 -- and this
        # assertion is what stands between the round-trip figure and that shortcut. A real
        # P2P book is asymmetric, so a doubling would be wrong on every real route.
        costed = _cost(route_graphs.p2p_graph(sell_premium=-2.0))
        round_trip = _round_trip(costed)
        assert is_close(round_trip.fraction, 1.0 / 9.0)
        assert is_close(round_trip.fraction, 0.1111111111111111)
        assert not is_close(round_trip.fraction, 2.0 * costed.one_way.fraction)

    def test_the_round_trip_costs_more_than_the_one_way_and_says_which_is_which(self) -> None:
        # FR-002: two labelled fields, never one figure standing in for the other. The
        # exit is a separately declared route (FR-027), so both conversions are named.
        costed = _cost(route_graphs.p2p_graph())
        round_trip = _round_trip(costed)
        assert round_trip.fraction > costed.one_way.fraction
        assert costed.one_way.channels_applied == ("p2p",)
        assert round_trip.channels_applied == ("p2p", "p2p")


class TestTheFindingTheFeatureExistsFor:
    """§4.3.1 in the form a decision can use: the ramp against a route with no ramp.

    Ten thousand hryvnia deployed domestically costs nothing to deploy and nothing to get
    back. The same ten thousand converted to dollars and back costs 13.33%. That difference
    is not a detail of the instrument -- it is larger than most of the returns being
    compared, which is the whole reason this project models the route rather than assuming
    it away.
    """

    def _ranked(self) -> Ranking:
        domestic = route_graphs.zero_cost_graph(with_exit=True)
        offshore = route_graphs.p2p_graph()
        ranked = ranking.rank(
            [domestic.path, offshore.path],
            Money(SENT, Currency.UAH, prov.EMPTY),
            routes={**domestic.routes, **offshore.routes},
            # The offshore graph's channels, because the domestic route has no ``fx`` leg
            # and therefore consults no channel at all. Merging the two mappings would
            # silently pick one "p2p" channel over the other, and the one that lost would
            # be the one carrying the premium under test.
            channels=offshore.channels,
            streams=route_graphs.STREAMS,
            kinds=route_graphs.KINDS,
            on_date=route_graphs.ON_DATE,
            as_of=route_graphs.AS_OF,
        )
        assert not isinstance(ranked, NothingComparable), ranked
        return ranked

    def test_both_routes_are_costed_and_neither_is_dropped(self) -> None:
        ranked = self._ranked()
        assert len(ranked.costed) == 2
        assert ranked.excluded == ()
        assert ranked.not_comparable == ()

    def test_the_domestic_route_costs_nothing_and_the_p2p_route_costs_two_fifteenths(
        self,
    ) -> None:
        # The comparison, stated as the two numbers it is made of.
        ranked = self._ranked()
        by_route = {entry.path.route_id: entry for entry in ranked.costed}
        domestic = by_route["inzhur_direct"]
        offshore = by_route["monobank_to_binance_p2p"]
        assert isinstance(domestic.round_trip, RoundTripCost)
        assert isinstance(offshore.round_trip, RoundTripCost)
        assert domestic.round_trip.fraction == 0.0
        assert is_close(offshore.round_trip.fraction, 2.0 / 15.0)

    def test_the_ranking_recommends_the_route_with_no_ramp(self) -> None:
        # Lexicographic on round-trip cost first, so the cheaper route wins even though
        # the P2P route is the *faster* one (one leg against two). Cost leads; latency is
        # the third key and only speaks when the first two are equal.
        ranked = self._ranked()
        assert recommended_cost(ranked).path.route_id == "inzhur_direct"
        assert ranked.costed[0].path.route_id == "inzhur_direct"
        assert ranked.costed[1].path.route_id == "monobank_to_binance_p2p"
        assert ranked.ties == ()

    def test_the_gap_is_the_whole_p2p_round_trip_and_nothing_else(self) -> None:
        # 1 333.33 UAH on ten thousand. Worth stating in money as well as in percent: the
        # decision this tool exists to support is whether a domestic yield clears the
        # offshore alternative *net of this figure*, and a percentage is easy to discount
        # while a number of hryvnia is not.
        ranked = self._ranked()
        offshore = next(
            entry for entry in ranked.costed if entry.path.route_id == "monobank_to_binance_p2p"
        )
        assert isinstance(offshore.round_trip, RoundTripCost)
        spread = offshore.round_trip.components[CostComponent.CONVERSION_SPREAD]
        assert is_close(spread.amount, 1333.3333333333333)
        assert is_close(spread.amount, SENT * (1.0 - SELL_PRICE / BUY_PRICE))
