"""G1, SC-003: the same acquisition from two streams, and the gap between them.

``SIMULATOR_SPEC.md`` §4.2 makes the structural claim this module exists to compute:

    **money that arrives in USD needs no UAH→USD conversion.** The 5-10% ramp cost in
    §4.3.1 applies only to the UAH stream. So the allocation question is per-stream.

That is why access cost is never quoted per instrument or per destination but only per
``(instrument x income stream x route)`` (constitution, Principle VI; FR-008). Quoting one
number for "buying dollars at the exchange" would average a route that pays a 3-hryvnia
premium with one that pays nothing, and the average is wrong for both.

## The arithmetic, once, in full

One reference rate, ``r = 42`` UAH per dollar, and one declared P2P buy premium, ``p = +3``,
so the price actually transacted at is ``r + p = 45``. Both funding paths start at the same
venue and end at the same venue -- dollars at the exchange -- and both deploy **the same
value**: ten thousand hryvnia, or the dollars that same ten thousand is worth at the
reference.

    from the UAH salary    10 000 UAH -> P2P at 45  ->  10 000 / 45 = 222.222222... USD
    from the USD contract  10 000 / 42 = 238.095238... USD -> no conversion -> 238.095238...

    difference in what arrives   238.095238... - 222.222222... =  15.873015873... USD
    checked independently        10 000 x (45 - 42) / (42 x 45) =  15.873015873... USD
    the same gap in hryvnia      15.873015873... x 42           = 666.666666...   UAH
    which is the salary path's   10 000 x 3 / 45                = 666.666666...   UAH

The last two lines are the point: **the whole of the difference between the two net
positions is the ramp cost, and nothing else.** Same destination, same value deployed, same
day; one path crossed a spread and the other did not.

As a fraction of what the dollar stream deployed, that gap is ``15.873 / 238.095 = 3/45 =
1/15 = 6.67%`` -- the one-way cost figure of ``tests/worked_examples/test_ramp_p2p_premium.py``,
arrived at from the other end. It is not a coincidence and it is asserted below: what the
salary path lost *is* what the two paths differ by.

## Stating the dollar amount at the reference rate is a valuation, not a transaction

Comparing a hryvnia amount with a dollar amount needs a rate, and FR-010 forbids a
single mid-rate being used **for a transaction**. Nothing here transacts at 42: the salary's
conversion happens at 45, through a declared two-sided channel, and the reference is used
only to say *how much value each stream deploys* so that the two paths are given the same
question. That is the same distinction ``terezy.core.routes.cost`` draws when it values a
mid-route fee in the sending currency -- a valuation of a figure, not a movement of money --
and it is stated here rather than left for a reader to reconstruct.

## Why exactly zero, and not merely small

The dollar path's conversion component is ``0.0`` **exactly** (FR-009, SC-006). Not a
rounded residual, not a converted zero: the route has no ``fx`` leg, so no rate is ever
applied. What it is *not* is an unmarked ``money.zero`` -- the zero carries the provenance of
the leg declaring that this leg converts nothing, because a zero that cannot cite its own
declaration is indistinguishable from a conversion nobody costed. That is asserted in
``tests/unit/test_usd_stream_converts_nothing.py``, which is this module's other half.
"""

from __future__ import annotations

import pytest

from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results.ramp import CostComponent, RampCost
from terezy.core.routes import cost
from tests.invariants import route_graphs

pytestmark = pytest.mark.worked_example

REFERENCE = 42.0
"""The stated reference rate: UAH per USD. Invented, like every route number in this
feature, and marked as a synthetic fixture where it is declared."""

BUY_PREMIUM = 3.0
"""+3 UAH per dollar -- the middle of §4.3.1's stated +2 to +4 range."""

BUY_PRICE = REFERENCE + BUY_PREMIUM
"""45 UAH per dollar: the price a P2P screen would show, and the rate the money crosses at."""

SALARY_SENDS = 10_000.0
"""What the hryvnia salary deploys. Round, so every division below stays readable."""

CONTRACT_SENDS = SALARY_SENDS / REFERENCE
"""What the dollar contract income deploys: **the same value**, stated in dollars at the
reference rate. 238.095238... USD. See the module docstring on why a reference rate may
state a value without any money crossing at it."""

RAMP_COST_IN_USD = SALARY_SENDS / REFERENCE - SALARY_SENDS / BUY_PRICE
"""15.873015873... USD -- the hand-computed gap, written as the difference of the two
arrivals so the expression itself is the arithmetic."""


def _cost(graph: route_graphs.Graph, amount: Money) -> RampCost:
    """Cost one amount along one graph's path, narrowing away the unusable case.

    Every assertion below is about a figure, so a ``RouteUnusable`` reaching one would fail
    on a missing attribute rather than on the number the test is about.
    """
    costed = cost.cost_one(
        graph.path,
        amount,
        routes=graph.routes,
        channels=graph.channels,
        streams=route_graphs.STREAMS,
        kinds=route_graphs.KINDS,
        on_date=route_graphs.ON_DATE,
        as_of=route_graphs.AS_OF,
        spendable=graph.spendable,
    )
    assert isinstance(costed, RampCost), costed
    return costed


def _from_the_salary() -> RampCost:
    """Ten thousand hryvnia, out of the UAH salary, through the P2P route."""
    return _cost(
        route_graphs.p2p_graph(),
        Money(SALARY_SENDS, Currency.UAH, prov.EMPTY),
    )


def _from_the_contract() -> RampCost:
    """The same value in dollars, out of the USD contract income, converting nothing."""
    return _cost(
        route_graphs.usd_direct_graph(),
        Money(CONTRACT_SENDS, Currency.USD, prov.EMPTY),
    )


def _gap() -> Money:
    """What the dollar-funded path ends up with, less what the hryvnia-funded path does.

    Through ``money.sub`` rather than on the bare floats, and not as a formality: both
    arrivals are dollars, so the subtraction is legitimate -- and if a later edit made one of
    them hryvnia, ``money`` would refuse the mismatch instead of returning a number. A gap
    between two currencies is not a gap (C5).
    """
    return money.sub(_from_the_contract().one_way.arrived, _from_the_salary().one_way.arrived)


class TestTheHryvniaSalaryPaysTheRamp:
    """One conversion at 45, and 6.67% of the money gone to the spread."""

    def test_ten_thousand_hryvnia_arrives_as_two_hundred_and_twenty_two_dollars(self) -> None:
        #   10 000 / 45 = 222.22222222222223 USD
        # The price transacted at, not the reference: this is what the venue hands over.
        costed = _from_the_salary()
        assert costed.one_way.arrived.currency is Currency.USD
        assert is_close(costed.one_way.arrived.amount, SALARY_SENDS / BUY_PRICE)
        assert is_close(costed.one_way.arrived.amount, 222.22222222222223)

    def test_the_conversion_cost_the_premium_over_the_price(self) -> None:
        #   spread   = 10 000 x 3/45 = 666.6666666666666 UAH
        #   fraction = 3/45 = 1/15   = 0.06666666666666667
        costed = _from_the_salary()
        spread = costed.one_way.components[CostComponent.CONVERSION_SPREAD]
        assert spread.currency is Currency.UAH
        assert is_close(spread.amount, SALARY_SENDS * BUY_PREMIUM / BUY_PRICE)
        assert is_close(spread.amount, 666.6666666666666)
        assert is_close(costed.one_way.fraction, BUY_PREMIUM / BUY_PRICE)
        assert is_close(costed.one_way.fraction, 1.0 / 15.0)

    def test_the_channel_it_crossed_is_named(self) -> None:
        # FR-011: the choice of channel changes the number, so the number says which one.
        # One conversion in, so one entry -- and the dollar path below has none.
        costed = _from_the_salary()
        assert costed.one_way.channels_applied == ("p2p",)
        assert costed.one_way.spreads_over_reference == (BUY_PREMIUM / REFERENCE,)


class TestTheDollarStreamConvertsNothingAndPaysNothing:
    """SC-006: the same acquisition, funded from money that is already in dollars."""

    def test_what_was_sent_is_what_arrives_bit_for_bit(self) -> None:
        # Not "within tolerance of what was sent" -- the *same float*. No conversion, no
        # fee, so no arithmetic touched it. ``hex()`` because that is the only comparison
        # strong enough to say so (the same discipline as SC-004's zero-cost route).
        costed = _from_the_contract()
        assert costed.one_way.arrived.currency is Currency.USD
        assert costed.one_way.arrived.amount.hex() == CONTRACT_SENDS.hex()
        assert costed.one_way.sent.amount.hex() == CONTRACT_SENDS.hex()

    def test_the_conversion_component_is_exactly_zero(self) -> None:
        # FR-009: exactly, not approximately. Asserted with ``==`` against ``0.0`` rather
        # than through the tolerance, because "small" is the wrong answer here: a residual
        # would mean a rate was applied to money that never changed currency.
        costed = _from_the_contract()
        assert costed.one_way.components[CostComponent.CONVERSION_SPREAD].amount == 0.0
        assert costed.one_way.fraction == 0.0

    def test_no_channel_was_consulted_even_though_one_was_declared(self) -> None:
        # The stronger statement: the fixture declares the same P2P channel the salary path
        # crossed, and this route still reports no conversion. A conversion happens because
        # a leg declares an ``fx`` kind, never because a rate happened to be available.
        costed = _from_the_contract()
        assert costed.one_way.channels_applied == ()
        assert costed.one_way.spreads_over_reference == ()
        assert route_graphs.CHANNEL_ID in route_graphs.usd_direct_graph().channels


class TestTheTwoNetPositionsDifferByExactlyTheRampCost:
    """G1: the finding, stated as one subtraction.

    Same destination venue, same origin venue, same value deployed, same date. One path
    crossed a declared P2P spread; the other did not. Everything else was held equal so that
    the difference has exactly one cause.
    """

    def test_the_gap_between_the_two_arrivals_is_the_hand_computed_figure(self) -> None:
        #   238.095238095... - 222.222222222... = 15.873015873015873 USD
        # and independently, from the two prices rather than the two arrivals:
        #   10 000 x (45 - 42) / (42 x 45) = 30 000 / 1 890 = 15.873015873015873
        gap = _gap()
        assert_money_close(gap, Money(RAMP_COST_IN_USD, Currency.USD, prov.EMPTY))
        assert is_close(
            gap.amount, SALARY_SENDS * (BUY_PRICE - REFERENCE) / (REFERENCE * BUY_PRICE)
        )
        assert is_close(gap.amount, 15.873015873015873)

    def test_the_gap_is_the_salary_paths_spread_and_nothing_else(self) -> None:
        # The claim G1 actually makes, and the one worth protecting: the difference between
        # the two net positions is *the ramp cost*, not a mixture of the ramp cost and
        # something else. 15.873015873 USD valued at the reference is 666.666666... UAH,
        # which is precisely what the P2P leg charged.
        #
        # The two sides land one bit apart (666.6666666666667 against 666.6666666666666),
        # which is the whole reason the project tolerance exists: money is float64, and
        # ``x/r`` then ``x*r`` is not the identity in binary floating point.
        spread = _from_the_salary().one_way.components[CostComponent.CONVERSION_SPREAD]
        # Valued at the reference through ``money.convert``, which demands the rate's sources
        # in its signature -- so the hryvnia figure admits which declared quote it rests on,
        # and ``assert_money_close`` can refuse a currency mismatch rather than compare bare
        # floats that happen to agree.
        in_hryvnia = money.convert(
            _gap(),
            to_currency=Currency.UAH,
            rate=REFERENCE,
            sources=route_graphs.RATE_SOURCES,
        )
        assert_money_close(in_hryvnia, spread)
        assert is_close(in_hryvnia.amount, 666.6666666666666)
        assert prov.is_unverified(in_hryvnia.provenance)

    def test_the_gap_as_a_fraction_is_the_one_way_cost_of_the_ramp(self) -> None:
        # 15.873015873 / 238.095238095 = 3/45 = 1/15 = 6.67%. The same figure the salary
        # path reports as its own cost fraction, reached from the other direction: what one
        # stream lost is what the two streams differ by.
        salary = _from_the_salary()
        deployed = _from_the_contract().one_way.arrived.amount
        assert is_close(_gap().amount / deployed, 1.0 / 15.0)
        assert is_close(_gap().amount / deployed, salary.one_way.fraction)

    def test_the_dollar_stream_is_the_cheaper_way_to_the_same_place(self) -> None:
        # Stated in the plainest possible form, because this is the sentence the feature
        # exists to let the tool write: 6.67% against 0.00% to the same destination.
        salary = _from_the_salary()
        contract = _from_the_contract()
        assert contract.one_way.fraction < salary.one_way.fraction
        assert contract.one_way.fraction == 0.0
        assert is_close(salary.one_way.fraction, 1.0 / 15.0)


class TestTheCostIsPerStreamAndNeverPerDestination:
    """FR-008 in its concrete form: one destination, two streams, two costs.

    The two paths agree on their destination and differ only in the stream that funds them,
    so a figure keyed by the destination alone would have to be one of these two numbers or
    an average of them -- and all three of those are wrong.
    """

    def test_both_paths_end_at_the_same_venue(self) -> None:
        assert (
            route_graphs.p2p_graph().path.destination_id
            == route_graphs.usd_direct_graph().path.destination_id
        )

    def test_they_are_different_paths_because_the_stream_differs(self) -> None:
        salary_path = route_graphs.p2p_graph().path
        contract_path = route_graphs.usd_direct_graph().path
        assert salary_path.stream_id == route_graphs.SALARY_UAH.id
        assert contract_path.stream_id == route_graphs.CONTRACT_USD.id
        assert salary_path != contract_path

    def test_each_cost_says_which_stream_paid_for_the_trip(self) -> None:
        # Not merely two different numbers: two numbers that each name their own stream, so
        # neither can be quoted as "the cost of reaching the exchange".
        assert _from_the_salary().path.stream_id == route_graphs.SALARY_UAH.id
        assert _from_the_contract().path.stream_id == route_graphs.CONTRACT_USD.id

    def test_a_blended_figure_would_be_wrong_for_both_streams(self) -> None:
        # The averaging argument, asserted rather than left in a comment. Halfway between
        # 6.67% and 0% is 3.33%, which overstates the dollar stream's cost by a third of a
        # year of the domestic risk-free return and understates the salary's by the same.
        salary = _from_the_salary()
        contract = _from_the_contract()
        blended = (salary.one_way.fraction + contract.one_way.fraction) / 2.0
        assert not is_close(blended, salary.one_way.fraction)
        assert not is_close(blended, contract.one_way.fraction)
