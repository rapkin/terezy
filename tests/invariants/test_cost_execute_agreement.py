"""FR-005: the ledger cannot disagree with the comparison, because it is derived from it.

FR-005: *costs MUST NEVER be silently clamped... **every fee is an explicit recorded line**,
never blended into the outcome.*

**The tension this closes** (research.md D5). FR-005 wants every fee to be a ledger line. But
a route comparison costs *many* routes and only *one* is executed, so writing events for every
candidate would put fees in the ledger for money that never moved, and cash conservation would
have to learn about hypothetical events. The resolution is two functions and **one**
arithmetic: ``cost_one`` prices, purely, for every candidate; ``execute`` takes the *costed
figure* and emits the events. It never recomputes, because it never sees a route or an amount
-- only a ``RampCost``.

**This invariant is what makes that safe.** From ``contracts/route-costing.md``:

```
sum(fee events from execute(c)) == sum(c.one_way.components.values())
```

plus the arriving amount in the ledger equalling ``c.one_way.arrived``, currency and all, and
``c.one_way.fraction`` equalling the component total over ``sent``. Cost-then-execute agreement
is *asserted*, not assumed.

⚙ **The contract's own note, and why the invariant is stated over the components.** It was
first written as ``sent - arrived``, which cannot typecheck and could not be made to: on a
converting route ``sent`` is hryvnia and ``arrived`` is dollars, and ``money.sub`` refuses a
currency mismatch by design (C5). Restating ``arrived`` in the sending currency would need a
rate, and the only rate available is a side of a channel quote -- so "the difference" is not a
well-defined quantity without saying *which side at which reference*, which is precisely what
FR-010 forbids leaving implicit. The components are all in the sending currency by
construction, so the sum over them closes exactly.

**What the ledger half asserts.** The cash effect per currency, tallied independently from the
``RampCost`` alone:

* the sending currency loses exactly ``sent`` -- the fees plus what crossed;
* the destination currency gains exactly ``arrived``.

On a route that converts nothing those are one currency and the two net to ``arrived - sent``,
which is the fees and nothing else. Stated that way rather than as one number because it is
the same claim in both cases and does not need a rate to express.
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping

import pytest
from hypothesis import given
from hypothesis import strategies as st

from terezy.core.ledger import engine
from terezy.core.ledger.events import CausationKind, Event, EventKind
from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import TOLERANCE, assert_money_close, is_close
from terezy.core.results.ramp import CostComponent, RampCost, RouteUnusable
from terezy.core.routes import capacity, cost, execute
from tests.invariants import route_graphs

pytestmark = pytest.mark.invariant

OWNER = "owner-001"
POOL = "monobank_card_uah_usd"


def _costed(graph: route_graphs.Graph, amount: float) -> RampCost | RouteUnusable:
    return cost.cost_one(
        graph.path,
        Money(amount, Currency.UAH, prov.EMPTY)
        if graph.path.stream_id == route_graphs.SALARY_UAH.id
        else Money(amount, Currency.USD, prov.EMPTY),
        routes=graph.routes,
        channels=graph.channels,
        streams=route_graphs.STREAMS,
        kinds=route_graphs.KINDS,
        on_date=route_graphs.ON_DATE,
        as_of=route_graphs.AS_OF,
    )


def _component_total(costed: RampCost) -> Money:
    """What the cost says the trip charged, summed over the closed component set."""
    return money.total(costed.one_way.components.values(), costed.one_way.sent.currency)


def _expected_cash(costed: RampCost) -> Mapping[Currency, float]:
    """The cash effect per currency, tallied from the ``RampCost`` and nothing else.

    Independent of ``execute`` on purpose: comparing the events against a figure the events
    produced would prove that one loop ran. The same discipline as the ledger conservation
    suite, which recomputes ``inflows - outflows`` rather than reading ``balance``.
    """
    sending = costed.one_way.sent.currency
    arriving = costed.one_way.arrived.currency
    tally: dict[Currency, float] = {sending: -costed.one_way.sent.amount}
    tally[arriving] = tally.get(arriving, 0.0) + costed.one_way.arrived.amount
    return tally


def _events(costed: RampCost, *, pool: str | None = POOL) -> tuple[Event, ...]:
    return execute.execute(
        costed,
        owner_id=OWNER,
        sequence_from=0,
        on_date=route_graphs.ON_DATE,
        capacity_pool=pool,
    )


class TestTheFeeEventsSumToTheCostedFigure:
    """The invariant the contract states, over generated routes and amounts."""

    @given(graph=route_graphs.route_graphs(base=Currency.UAH), amount=route_graphs.AMOUNTS)
    def test_the_fee_events_sum_to_the_components(
        self, graph: route_graphs.Graph, amount: float
    ) -> None:
        costed = _costed(graph, amount)
        if not isinstance(costed, RampCost):
            return  # the route refused this amount; there is nothing to execute
        events = _events(costed)
        fees = [event for event in events if event.kind is EventKind.FEE]
        charged = money.total(
            [money.scale(fee.amount, -1.0) for fee in fees], costed.one_way.sent.currency
        )
        assert_money_close(charged, _component_total(costed))

    @given(graph=route_graphs.route_graphs(base=Currency.UAH), amount=route_graphs.AMOUNTS)
    def test_one_fee_event_per_fee_bearing_component_and_none_for_a_zero(
        self, graph: route_graphs.Graph, amount: float
    ) -> None:
        # "One fee event per fee-bearing component" (the contract). A component declared zero
        # is already in the ``RampCost``, citing the declaration that says the route charges
        # nothing there (FR-009); a zero ledger line would add no fact and would make a
        # zero-cost domestic route emit three of them.
        costed = _costed(graph, amount)
        if not isinstance(costed, RampCost):
            return
        bearing = [
            component
            for component, charge in costed.one_way.components.items()
            if charge.amount != 0.0
        ]
        fees = [event for event in _events(costed) if event.kind is EventKind.FEE]
        assert len(fees) == len(bearing)

    @given(graph=route_graphs.route_graphs(base=Currency.UAH), amount=route_graphs.AMOUNTS)
    def test_the_fraction_is_the_component_total_over_what_was_sent(
        self, graph: route_graphs.Graph, amount: float
    ) -> None:
        # The contract's third clause. Asserted here rather than only in the attribution
        # suite because it is what ties the *reported percentage* to the *recorded lines*:
        # a fraction computed from anything but these components would be a second figure.
        costed = _costed(graph, amount)
        if not isinstance(costed, RampCost):
            return
        total = _component_total(costed)
        if costed.one_way.sent.amount == 0.0:
            return  # the zero-sent case is its own statement; see cost._fraction
        assert is_close(costed.one_way.fraction, total.amount / costed.one_way.sent.amount)


class TestTheLedgerArrivesAtTheAmountTheCostReported:
    """The other half: the fold agrees with the figure, currency and all."""

    @given(graph=route_graphs.route_graphs(base=Currency.UAH), amount=route_graphs.AMOUNTS)
    def test_the_cash_effect_per_currency_is_what_the_cost_says_it_is(
        self, graph: route_graphs.Graph, amount: float
    ) -> None:
        costed = _costed(graph, amount)
        if not isinstance(costed, RampCost):
            return
        folded = engine.fold(_events(costed), base_currency=Currency.UAH, consumption_method="fifo")
        expected = _expected_cash(costed)
        assert set(folded.accounts) == set(expected)
        for currency, figure in expected.items():
            assert is_close(folded.accounts[currency].balance.amount, figure), (
                f"the ledger's {currency.value} balance is "
                f"{folded.accounts[currency].balance.amount!r} where the RampCost implies "
                f"{figure!r}"
            )

    @given(graph=route_graphs.route_graphs(base=Currency.UAH), amount=route_graphs.AMOUNTS)
    def test_the_arriving_event_is_the_arriving_amount(
        self, graph: route_graphs.Graph, amount: float
    ) -> None:
        # The emitted order is part of ``execute``'s contract: the departure first, so the
        # fees have an anchor to be allocated to, then the fees, then the arrival last.
        costed = _costed(graph, amount)
        if not isinstance(costed, RampCost):
            return
        events = _events(costed)
        assert events[-1].kind is EventKind.RAMP_MOVEMENT
        assert_money_close(events[-1].amount, costed.one_way.arrived)

    @given(graph=route_graphs.route_graphs(base=Currency.UAH), amount=route_graphs.AMOUNTS)
    def test_what_crossed_is_what_was_sent_less_what_was_charged(
        self, graph: route_graphs.Graph, amount: float
    ) -> None:
        costed = _costed(graph, amount)
        if not isinstance(costed, RampCost):
            return
        events = _events(costed)
        assert events[0].kind is EventKind.RAMP_MOVEMENT
        assert_money_close(
            money.scale(events[0].amount, -1.0),
            money.sub(costed.one_way.sent, _component_total(costed)),
        )

    @given(graph=route_graphs.route_graphs(base=Currency.UAH), amount=route_graphs.AMOUNTS)
    def test_every_fee_is_allocated_to_the_movement_it_was_charged_on(
        self, graph: route_graphs.Graph, amount: float
    ) -> None:
        # ``events.allocated_fees`` refuses an unallocated fee outright: a fee that reduces
        # cash and names no target would report a gain gross of a cost that was paid. So the
        # departure event is the anchor, and this asserts the anchoring rather than trusting
        # the fold not to have raised.
        costed = _costed(graph, amount)
        if not isinstance(costed, RampCost):
            return
        events = _events(costed)
        anchor = events[0].sequence
        for event in events:
            if event.kind is EventKind.FEE:
                assert event.allocated_to == anchor

    @given(graph=route_graphs.route_graphs(base=Currency.UAH), amount=route_graphs.AMOUNTS)
    def test_the_events_are_densely_sequenced_from_where_the_caller_said(
        self, graph: route_graphs.Graph, amount: float
    ) -> None:
        costed = _costed(graph, amount)
        if not isinstance(costed, RampCost):
            return
        events = execute.execute(
            costed,
            owner_id=OWNER,
            sequence_from=17,
            on_date=route_graphs.ON_DATE,
            capacity_pool=None,
        )
        assert [event.sequence for event in events] == list(range(17, 17 + len(events)))


class TestExecuteDerivesRatherThanRecomputes:
    """The structural half of research.md D5: there is no arithmetic here to drift."""

    def test_execute_cannot_see_a_route_or_an_amount(self) -> None:
        # The signature is the guarantee. ``execute`` takes the costed figure; it takes no
        # ``Route``, no ``FxChannel``, no ``Leg`` and no ``amount``, so there is nothing in it
        # that *could* price anything. Research.md D5 originally wrote
        # ``execute(path, amount, as_of)``, which contradicted its own conclusion -- taking the
        # path and the amount would mean recomputing the arithmetic beside ``cost_one``.
        parameters = inspect.signature(execute.execute).parameters
        assert set(parameters) == {
            "cost",
            "owner_id",
            "sequence_from",
            "on_date",
            "capacity_pool",
        }
        for banned in ("amount", "routes", "channels", "route", "path", "streams", "kinds"):
            assert banned not in parameters

    def test_the_events_name_the_route_declaration_that_charged(self) -> None:
        # FR-005 wants an explicit recorded line, and C6 wants every line resolvable to the
        # rule that produced it. A ramp fee is charged by neither an instrument term nor a tax
        # rule, so it names the route term -- the route id, resolvable back to its declaration.
        graph = route_graphs.p2p_graph()
        costed = _costed(graph, 10_000.0)
        assert isinstance(costed, RampCost)
        for event in _events(costed):
            assert event.caused_by.kind is CausationKind.ROUTE_TERM
            assert event.caused_by.id == graph.path.route_id
            assert event.caused_by.detail

    def test_every_component_has_prose_and_an_unexplained_one_would_raise(self) -> None:
        # FR-005's "explicit recorded line" is only explicit if a reader can tell what
        # charged. So every member of the closed component set has an explanation, and there
        # is no generic fallback -- a fallback is the shape that makes such a gap permanent,
        # because nothing ever fails to reveal it.
        for component in CostComponent:
            assert execute.COMPONENT_DETAIL[component]
        with pytest.raises(KeyError, match="has no recorded explanation"):
            execute._detail("percentage_fee")  # type: ignore[arg-type]

    def test_the_recorded_movement_consumes_the_rail_it_crossed(self) -> None:
        # Ten thousand hryvnia through the card is ten thousand hryvnia of the card's monthly
        # limit -- the fees included, because the fees came out of the money that crossed. The
        # arrival is in dollars at the far end and consumes nothing on the sending rail.
        graph = route_graphs.p2p_graph()
        costed = _costed(graph, 10_000.0)
        assert isinstance(costed, RampCost)
        folded = engine.fold(_events(costed), base_currency=Currency.UAH, consumption_method="fifo")
        key = capacity.key_for(POOL, route_graphs.ON_DATE)
        assert set(folded.capacity) == {key}
        assert_money_close(folded.capacity[key], costed.one_way.sent)

    @given(
        # Signed on purpose, and bounded so the effective rate 42 + p stays positive:
        # a side that pays away the whole reference is refused at load (FR-010).
        buy_premium=st.floats(min_value=-4.0, max_value=4.0, allow_nan=False),
        amount=route_graphs.AMOUNTS,
    )
    def test_the_rail_consumes_what_was_sent_whatever_the_components_signs(
        self, buy_premium: float, amount: float
    ) -> None:
        # FR-015 over *signed* components. A negative buy premium is a legal discount
        # channel: the conversion-spread component goes negative, the departure is then
        # larger than ``sent`` and the fee line is a credit. An accumulator summing the
        # magnitude of every pool-tagged event counts both -- 110 000 consumed where
        # 100 000 was sent -- so headroom goes falsely negative and fallbacks fire despite
        # room. What the rail carried is the whole of ``sent`` (execute's own contract),
        # for every sign the components can take.
        graph = route_graphs.p2p_graph(buy_premium=buy_premium)
        costed = _costed(graph, amount)
        if not isinstance(costed, RampCost):
            return
        folded = engine.fold(_events(costed), base_currency=Currency.UAH, consumption_method="fifo")
        key = capacity.key_for(POOL, route_graphs.ON_DATE)
        assert_money_close(folded.capacity[key], costed.one_way.sent)

    def test_a_discount_channel_leaves_the_headroom_the_rail_really_has(self) -> None:
        # The reproduced defect, in the numbers it was reproduced with: 100 000 UAH sent
        # through a channel buying below the reference must consume exactly 100 000 of a
        # 100 000 cap -- zero headroom, not negative headroom on money never sent.
        graph = route_graphs.p2p_graph(buy_premium=-2.0)
        costed = _costed(graph, 100_000.0)
        assert isinstance(costed, RampCost)
        assert costed.one_way.components[CostComponent.CONVERSION_SPREAD].amount < 0.0, (
            "the fixture must exercise a negative component, or this test shows nothing"
        )
        folded = engine.fold(_events(costed), base_currency=Currency.UAH, consumption_method="fifo")
        headroom = capacity.headroom(
            folded.capacity,
            pool=POOL,
            cap=Money(100_000.0, Currency.UAH, prov.EMPTY),
            on_date=route_graphs.ON_DATE,
        )
        assert_money_close(headroom, Money(0.0, Currency.UAH, prov.EMPTY))

    def test_naming_no_rail_consumes_no_capacity(self) -> None:
        graph = route_graphs.p2p_graph()
        costed = _costed(graph, 10_000.0)
        assert isinstance(costed, RampCost)
        folded = engine.fold(
            _events(costed, pool=None), base_currency=Currency.UAH, consumption_method="fifo"
        )
        assert folded.capacity == {}

    def test_a_zero_cost_route_records_the_movement_and_no_fee_at_all(self) -> None:
        # The bar the others are measured against (SC-004), one layer down: a route whose
        # every leg declares zero charges nothing, so there is no fee line to record, and the
        # money still moved.
        graph = route_graphs.zero_cost_graph()
        costed = _costed(graph, 10_000.0)
        assert isinstance(costed, RampCost)
        events = _events(costed)
        assert not [event for event in events if event.kind is EventKind.FEE]
        assert len(events) == 2
        assert_money_close(money.scale(events[0].amount, -1.0), events[1].amount)
        assert_money_close(events[1].amount, Money(10_000.0, Currency.UAH, prov.EMPTY))


class TestTheProvenanceOfTheFigureReachesTheLedgerLine:
    """Principle I: a derived figure that loses its parent's mark is a defect."""

    def test_every_recorded_amount_carries_the_marks_the_cost_carried(self) -> None:
        graph = route_graphs.p2p_graph()
        costed = _costed(graph, 10_000.0)
        assert isinstance(costed, RampCost)
        for event in _events(costed):
            if event.amount.amount == 0.0:
                continue
            assert prov.is_unverified(event.amount.provenance), (
                "every route number in this fixture is unverified, so every ledger line "
                "derived from one must say so (Principle I)"
            )


def test_the_tolerance_is_the_project_tolerance() -> None:
    """No local bound. The one place a tolerance is defined is the one this module imports."""
    assert TOLERANCE > 0.0
    assert is_close(1.0, 1.0 + TOLERANCE / 2.0)
