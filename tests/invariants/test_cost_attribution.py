"""FR-003: the components account for the whole cost, over generated routes and amounts.

*The system MUST attribute cost to its components -- conversion spread, percentage fees,
fixed fees -- so a reader can see which term dominates. "Most of the gap is the ramp, not the
asset" is the sentence this feature exists to let the tool write.*

A reader can only believe that sentence if the terms add up. So the property asserted here is
the one that makes the attribution worth reading:

    sum(components) == sent - (what arrived, valued in the sending currency)

**Why it is a property and not an example.** An attribution can be right on the route it was
written against and wrong on the next one -- a spread charged after a fee instead of before,
a fixed fee counted in the wrong currency, a component quietly dropped on a route with three
legs. Generated routes are what turn "the arithmetic works" into "the arithmetic closes".

**Why the right-hand side is recomputed in the test.** ``tests/invariants/route_graphs.py``
walks the legs itself to work out what one unit of the arriving currency is worth in the
sending currency. A conservation test that compares the engine's total against the engine's
own running sum proves only that one loop ran once; the point is to check the fold against an
independent tally drawn from the same declarations. The same discipline as C1-C3.

**Why the components are in one currency.** They are all in the sending currency, so they can
be added at all -- ``money.add`` refuses a mismatch, which is exactly the protection wanted
here. A cost charged in a foreign currency mid-route is translated at the reference rate of
the conversion it crossed. That is a *valuation*, not a transaction, so it does not breach
FR-010's prohibition on transacting at a mid-rate: no money moves at the reference without a
declared side's spread being charged first.

**The other half of the property: a route that cannot carry the amount.** ``cost_one`` is
total -- every call returns a ``RampCost`` or a ``RouteUnusable``, never an exception and
never a zero cost standing in for a refusal (FR-014). Both branches are asserted, so the
property cannot pass by every generated case falling into the easy one.

Comparisons go through the single project tolerance. Nothing here uses ``pytest.approx``,
``math.isclose`` with a bound of its own, or a numeric literal as a bound.
"""

from __future__ import annotations

import dataclasses
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.staleness import any_stale
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results.ramp import (
    CostComponent,
    OneWayCost,
    RampCost,
    RoundTripCost,
    RouteUnusable,
)
from terezy.core.routes import cost
from terezy.core.routes.legs import Leg
from tests.invariants import route_graphs
from tests.invariants.route_graphs import AS_OF, KINDS, ON_DATE, Graph

pytestmark = pytest.mark.invariant


def _cost(graph: Graph, amount: float) -> RampCost | RouteUnusable:
    return cost.cost_one(
        graph.path,
        Money(amount, graph.route.legs[0].from_ccy, prov.EMPTY),
        routes=graph.routes,
        channels=graph.channels,
        kinds=KINDS,
        on_date=ON_DATE,
        as_of=AS_OF,
    )


def _total(costed: RampCost) -> Money:
    return money.total(costed.one_way.components.values(), costed.one_way.sent.currency)


def _sent_currency(graph: Graph) -> Currency:
    return graph.route.legs[0].from_ccy


def _value_in_sending_currency(graph: Graph, legs: tuple[Leg, ...], arrived: Money) -> Money:
    """What the arriving amount is worth where it started, recomputed from the legs.

    Built with ``money.scale`` when the currency already matches and ``money.convert``
    otherwise, so the comparison is between two amounts of the same currency and
    ``assert_money_close`` can refuse a mismatch rather than compare bare floats.
    """
    factor = route_graphs.base_factor(legs, _sent_currency(graph), graph.reference_rate)
    sending = _sent_currency(graph)
    if arrived.currency is sending:
        return arrived
    return money.convert(arrived, to_currency=sending, rate=factor, sources=prov.EMPTY)


@given(graph=route_graphs.route_graphs(), amount=route_graphs.AMOUNTS)
@settings(max_examples=250)
def test_the_components_account_for_the_whole_one_way_cost(graph: Graph, amount: float) -> None:
    """The invariant behind FR-003, over generated routes."""
    costed = _cost(graph, amount)
    if isinstance(costed, RouteUnusable):
        return  # the other branch is asserted below, on its own terms
    gap = money.sub(
        costed.one_way.sent,
        _value_in_sending_currency(graph, graph.route.legs, costed.one_way.arrived),
    )
    assert_money_close(_total(costed), gap)


@given(graph=route_graphs.route_graphs(), amount=route_graphs.AMOUNTS)
@settings(max_examples=200)
def test_every_component_is_present_in_the_sending_currency(graph: Graph, amount: float) -> None:
    """FR-009: a component that does not apply is a declared zero, not an absence.

    "No conversion happened" and "conversion cost unknown" are different claims, and a
    missing key would read as the second while meaning the first. The closed enumeration is
    only checkable if every member is always there.
    """
    costed = _cost(graph, amount)
    if isinstance(costed, RouteUnusable):
        return
    outcomes: list[OneWayCost | RoundTripCost] = [costed.one_way]
    if isinstance(costed.round_trip, RoundTripCost):
        outcomes.append(costed.round_trip)
    for outcome in outcomes:
        assert set(outcome.components) == set(CostComponent)
        for component in outcome.components.values():
            assert component.currency is outcome.sent.currency


@given(graph=route_graphs.route_graphs(), amount=route_graphs.AMOUNTS)
@settings(max_examples=200)
def test_the_fraction_is_the_total_over_what_was_sent(graph: Graph, amount: float) -> None:
    """The reported percentage is the attribution's own sum, not a separately kept figure.

    A second place for the fraction to come from is a second place for it to disagree with
    the components a reader was shown -- and the reader would have no way to tell which of
    the two was wrong.
    """
    costed = _cost(graph, amount)
    if isinstance(costed, RouteUnusable):
        return
    total = _total(costed)
    if costed.one_way.sent.amount == 0.0:
        # Nothing was sent. A route with no fixed fee costs nothing on nothing, and the
        # fraction is zero; a route with one charges a fee on nothing, and the fraction is
        # genuinely infinite. Neither is invented and neither is capped: an infinite cost
        # sorts last in a ranking, which is the correct treatment of paying to move
        # nothing.
        assert costed.one_way.fraction == 0.0 or math.isinf(costed.one_way.fraction)
        return
    assert is_close(costed.one_way.fraction, total.amount / costed.one_way.sent.amount)


@given(graph=route_graphs.route_graphs(with_partner=True), amount=route_graphs.AMOUNTS)
@settings(max_examples=200)
def test_the_round_trip_components_account_for_the_whole_round_trip(
    graph: Graph, amount: float
) -> None:
    """The same closure over both routes, because the round trip is the comparable figure.

    FR-002 makes round trip the number that belongs in a comparison, so its attribution has
    to close too -- and it is the one most likely not to, since it sums terms charged in two
    currencies across two declarations.
    """
    costed = _cost(graph, amount)
    if isinstance(costed, RouteUnusable) or not isinstance(costed.round_trip, RoundTripCost):
        return
    round_trip = costed.round_trip
    partner = graph.routes["exit_route"]
    total = money.total(round_trip.components.values(), round_trip.sent.currency)
    gap = money.sub(
        round_trip.sent,
        _value_in_sending_currency(graph, graph.route.legs + partner.legs, round_trip.arrived),
    )
    assert_money_close(total, gap)


@given(graph=route_graphs.route_graphs(), amount=route_graphs.AMOUNTS)
@settings(max_examples=200)
def test_every_figure_admits_the_observations_it_rests_on(graph: Graph, amount: float) -> None:
    """FR-022 / SC-012: 100% of figures derived from an unverified input carry the mark.

    Every declared number in a generated graph is unverified, so *every* figure must be. A
    single figure that came back unmarked would mean a transform dropped a mark, which the
    constitution puts in its top severity class.
    """
    costed = _cost(graph, amount)
    if isinstance(costed, RouteUnusable):
        return
    assert prov.is_unverified(costed.one_way.provenance)
    assert prov.is_unverified(costed.one_way.arrived.provenance)
    for component in costed.one_way.components.values():
        # A zero component rests on the declaration that said zero, so it is marked too.
        assert prov.is_unverified(component.provenance)


@given(graph=route_graphs.route_graphs(), amount=route_graphs.AMOUNTS)
@settings(max_examples=100)
def test_staleness_is_assessed_rather_than_assumed_fresh(graph: Graph, amount: float) -> None:
    """FR-025: a figure that was never aged must not look like one that was found current.

    Every generated graph's observations are 20 days old, which is stale for a P2P premium
    and current for a fee schedule. The verdict must name what it looked at either way --
    an unassessed verdict reaching a result is a silent permissive default.
    """
    costed = _cost(graph, amount)
    if isinstance(costed, RouteUnusable):
        return
    assert costed.one_way.staleness.assessed
    if any(leg.kind == "fx" for leg in graph.route.legs):
        assert any_stale(costed.one_way.staleness)


@given(graph=route_graphs.route_graphs(), amount=route_graphs.AMOUNTS)
@settings(max_examples=250)
def test_a_route_that_cannot_carry_the_amount_names_what_bound_it(
    graph: Graph, amount: float
) -> None:
    """FR-014, and the totality of ``cost_one``: two outcomes, both of them explicit."""
    costed = _cost(graph, amount)
    if isinstance(costed, RampCost):
        return
    assert costed.path == graph.path
    assert costed.binding_constraint
    assert costed.reason
    if costed.required is not None and costed.actual is not None:
        assert costed.shortfall is not None
        assert_money_close(costed.shortfall, money.sub(costed.required, costed.actual))


@given(graph=route_graphs.route_graphs())
@settings(max_examples=50)
def test_costing_the_same_path_twice_gives_the_same_answer(graph: Graph) -> None:
    """C4 in miniature: ``cost_one`` is a pure function of its arguments.

    No clock, no I/O, no state. Asserted over generated graphs because the cheapest way for
    this to stop being true is a helper reaching for the day's date to decide staleness.
    """
    assert _cost(graph, 10_000.0) == _cost(graph, 10_000.0)


def test_a_route_of_zero_fee_legs_costs_exactly_zero() -> None:
    """SC-004: the bar every other route is measured against.

    Not "within tolerance of zero" -- **exactly** zero, and exactly what was sent arrives.
    A domestic route that leaked a small residual would make every comparison against it
    slightly flattering to the expensive alternatives.
    """
    graph = route_graphs.zero_cost_graph()
    costed = cost.cost_one(
        graph.path,
        Money(10_000.0, Currency.UAH, prov.EMPTY),
        routes=graph.routes,
        channels=graph.channels,
        kinds=KINDS,
        on_date=ON_DATE,
        as_of=AS_OF,
    )
    assert isinstance(costed, RampCost)
    assert costed.one_way.arrived.amount == 10_000.0
    assert costed.one_way.fraction == 0.0
    assert all(component.amount == 0.0 for component in costed.one_way.components.values())


@given(fixed=st.floats(min_value=0.01, max_value=100.0, allow_nan=False))
@settings(max_examples=25)
def test_a_fee_on_a_zero_amount_is_reported_rather_than_absorbed(fixed: float) -> None:
    """Nothing is clamped, in the degenerate case that most invites it.

    Moving nothing through a route with a flat fee costs the fee. The arriving amount is
    negative and the cost fraction is infinite, and both are reported: a zero here would
    say the route is free, which is the most flattering possible lie about it.
    """
    graph = route_graphs.zero_cost_graph(fixed_fee=fixed)
    costed = cost.cost_one(
        graph.path,
        Money(0.0, Currency.UAH, prov.EMPTY),
        routes=graph.routes,
        channels=graph.channels,
        kinds=KINDS,
        on_date=ON_DATE,
        as_of=AS_OF,
    )
    assert isinstance(costed, RampCost)
    assert costed.one_way.arrived.amount < 0.0
    assert math.isinf(costed.one_way.fraction)


def test_a_negative_amount_is_refused_rather_than_costed() -> None:
    """A negative movement is not this route in reverse -- the way out is its own route.

    So a negative amount can only be an arithmetic error in the caller, and costing it would
    report a negative cost that reads as a gain. Refused, not clamped to zero: the clamp
    would hide the caller's bug behind a plausible free route.
    """
    graph = route_graphs.zero_cost_graph()
    with pytest.raises(ValueError, match="cannot be moved"):
        cost.cost_one(
            graph.path,
            Money(-1.0, Currency.UAH, prov.EMPTY),
            routes=graph.routes,
            channels=graph.channels,
            kinds=KINDS,
            on_date=ON_DATE,
            as_of=AS_OF,
        )


def test_a_closed_route_is_excluded_with_its_status_recorded() -> None:
    """FR-014: its absence from a comparison is visible rather than silent.

    A closed route is the one exclusion a reader is most likely to want explained -- "why is
    the cheap corridor missing?" -- so it comes back as a ``RouteUnusable`` naming
    ``route.status`` rather than simply not appearing.
    """
    graph = route_graphs.zero_cost_graph()
    closed = dataclasses.replace(graph.route, status="closed")
    costed = cost.cost_one(
        graph.path,
        Money(1_000.0, Currency.UAH, prov.EMPTY),
        routes={closed.id: closed},
        channels=graph.channels,
        kinds=KINDS,
        on_date=ON_DATE,
        as_of=AS_OF,
    )
    assert isinstance(costed, RouteUnusable)
    assert costed.binding_constraint == "route.status"
    # No amount bound, so no amount is invented for the report: a zero here would put a
    # number where there is none, and the reason states it in words instead.
    assert costed.required is None
    assert costed.actual is None
    assert costed.shortfall is None
    assert "closed" in costed.reason


def test_a_declared_monthly_cap_is_reported_as_the_ceiling_in_the_sending_currency() -> None:
    """FR-012's ceiling, and the honest limit of what this figure means.

    It is the tightest declared cap on any leg, valued where the money started -- not the
    largest amount that may be sent, which also depends on the fees upstream of the leg that
    binds and on how much of the month is already consumed. That second figure belongs to the
    capacity accumulator (FR-015), and conflating the two here would overstate what the route
    will carry.
    """
    graph = route_graphs.capped_graph(cap=50_000.0)
    costed = cost.cost_one(
        graph.path,
        Money(1_000.0, Currency.UAH, prov.EMPTY),
        routes=graph.routes,
        channels=graph.channels,
        kinds=KINDS,
        on_date=ON_DATE,
        as_of=AS_OF,
    )
    assert isinstance(costed, RampCost)
    assert costed.ceiling is not None
    assert_money_close(costed.ceiling, Money(50_000.0, Currency.UAH, prov.EMPTY))


def test_the_disruption_probability_rides_beside_the_cost_and_never_inside_it() -> None:
    """FR-026: the chance a route stops working is a different claim from what it charges.

    Two zero-fee legs, one of them 40% likely to break. The cost stays exactly zero and the
    probability is reported beside it. A single blended number would answer neither question,
    and compounding the legs would smuggle in an independence assumption nobody stated -- so
    the figure is the largest single leg's, read as a lower bound.
    """
    graph = route_graphs.capped_graph(cap=None, disruption=(0.4, 0.1))
    costed = cost.cost_one(
        graph.path,
        Money(1_000.0, Currency.UAH, prov.EMPTY),
        routes=graph.routes,
        channels=graph.channels,
        kinds=KINDS,
        on_date=ON_DATE,
        as_of=AS_OF,
    )
    assert isinstance(costed, RampCost)
    assert costed.one_way.fraction == 0.0
    assert costed.disruption_probability == 0.4
