"""**B13**, FR-005, SC-013: nothing is clamped, and money never vanishes quietly.

Required test **B13**: *costs are never silently clamped at zero; fees are explicit ledger
lines and never blended into "market loss".* SC-013 measures it: *fees exceeding the amount
moved are reported as such; no amount is ever clamped to zero, and total fees recorded equal
total fees applied.*

**The predecessor's defect was literally ``max(gross - fee, 0)``.** A flat fee on a small
transfer made the arriving amount zero rather than negative, so money vanished with no
diagnostic, and the cost fraction read as a tidy 100% for a movement that had actually cost
more than it moved. Every clause below is one place that instinct could return:

* ``arrived`` goes to or **below zero** and is reported that way;
* ``fraction`` may **exceed 1.0**, and may be negative where a channel trades below its
  reference;
* the fee lines ``execute`` records sum to exactly the components ``cost_one`` reported --
  *total fees recorded equal total fees applied*;
* a monthly headroom already overrun reports a **negative** figure rather than a zero.

**Why property-based.** A clamp is invisible except at the boundary, and the boundary moves
with the fixed fee, the percentage and the amount. Generated routes and generated amounts walk
across it; a hand-picked case sits on one side of it and passes forever. The one hand-built
case here is the degenerate one no strategy would reliably produce: a flat fee charged on an
amount of exactly zero.

**A source scan closes the gap from the other side.** A property test can only fail on inputs
it happens to draw, so this module also parses ``core.routes`` and ``core.results`` for the
shape of the defect -- ``max(..., 0)``, ``min(..., 0)``, ``abs`` on a cost -- and fails on it
by construction rather than by sampling.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

import terezy.core.results
import terezy.core.routes
from terezy.core.ledger import engine, lots
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results import tax_year as tax_settlement
from terezy.core.results.ramp import RampCost, RouteUnusable
from terezy.core.routes import capacity, cost, execute
from terezy.core.tax import flat_rate
from terezy.core.tax import year as tax_year
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxContext
from tests import tax_years
from tests.invariants import route_graphs

pytestmark = pytest.mark.invariant

OWNER = route_graphs.OWNER_ID
ON_DATE = date(2026, 8, 21)

DEPOSITED: float = 20_000.00
PURCHASE_COST: float = 10_000.00
SOLD_ON: date = date(2027, 5, 4)
WITHDRAWN_ON: date = date(2027, 12, 20)
TAX_HORIZON: date = date(2028, 12, 31)

PROCEEDS_MIN: float = 1_000.00
PROCEEDS_MAX: float = 60_000.00
"""Straddling ``PURCHASE_COST``, so the draw includes loss years as well as gain years."""

COVER_MIN: float = 0.0
COVER_MAX: float = 2.0
"""Multiples of the liability left in the account on the due date. Straddling 1.0, which is
the shortfall boundary -- so half the strategy space is short and the boundary is where
Hypothesis shrinks towards rather than out at the edge of one axis."""


def _uah(amount: float) -> Money:
    return Money(amount, Currency.UAH, prov.EMPTY)


def _cost_through(graph: route_graphs.Graph, amount: float) -> RampCost | RouteUnusable:
    return cost.cost_one(
        graph.path,
        _uah(amount),
        routes=graph.routes,
        channels=graph.channels,
        streams=route_graphs.STREAMS,
        kinds=route_graphs.KINDS,
        on_date=route_graphs.ON_DATE,
        as_of=route_graphs.AS_OF,
        spendable=graph.spendable,
    )


def _component_total(costed: RampCost) -> Money:
    return money.total(costed.one_way.components.values(), costed.one_way.sent.currency)


class TestFeesExceedingTheAmountAreReportedRatherThanClamped:
    """The defect itself, at the boundary where it used to hide."""

    def test_a_flat_fee_larger_than_the_amount_drives_the_arriving_amount_negative(
        self,
    ) -> None:
        # Two legs, each charging a flat 500 on a movement of 100. 100 - 500 = -400 leaves the
        # first leg, and -400 - 500 = -900 leaves the second. The predecessor would have
        # reported 0 arriving and a cost of exactly the amount sent -- a plausible number with
        # 900 of real cost missing from it.
        graph = route_graphs.zero_cost_graph(fixed_fee=500.0)
        costed = _cost_through(graph, 100.0)
        assert isinstance(costed, RampCost)
        assert_money_close(costed.one_way.arrived, _uah(-900.0))
        assert costed.one_way.arrived.amount < 0.0

    def test_the_cost_fraction_exceeds_one_and_is_not_capped(self) -> None:
        # 1 000 of fee on 100 sent is a cost of ten times the amount. Capping the fraction at
        # 1.0 would say the route cost everything, which is the most flattering thing that can
        # be said about a route that cost ten times everything.
        graph = route_graphs.zero_cost_graph(fixed_fee=500.0)
        costed = _cost_through(graph, 100.0)
        assert isinstance(costed, RampCost)
        assert is_close(costed.one_way.fraction, 10.0)
        assert costed.one_way.fraction > 1.0

    def test_a_flat_fee_on_nothing_reports_an_infinite_fraction_rather_than_zero(self) -> None:
        # The degenerate case, and the one where a zero is most tempting: a route that charges
        # a flat fee on an amount of zero. Zero would say the route is free.
        graph = route_graphs.zero_cost_graph(fixed_fee=500.0)
        costed = _cost_through(graph, 0.0)
        assert isinstance(costed, RampCost)
        assert costed.one_way.fraction == float("inf")
        assert_money_close(costed.one_way.arrived, _uah(-1_000.0))

    def test_a_zero_fee_on_nothing_costs_nothing_rather_than_being_undefined(self) -> None:
        # The other half of that division. Charging nothing on nothing costs nothing, and the
        # fraction is zero -- which is a fact and not a fallback.
        graph = route_graphs.zero_cost_graph()
        costed = _cost_through(graph, 0.0)
        assert isinstance(costed, RampCost)
        assert costed.one_way.fraction == 0.0
        assert_money_close(costed.one_way.arrived, _uah(0.0))

    @given(graph=route_graphs.route_graphs(base=Currency.UAH), amount=route_graphs.AMOUNTS)
    def test_the_components_always_account_for_the_whole_gap(
        self, graph: route_graphs.Graph, amount: float
    ) -> None:
        # The general statement, over generated routes: whatever the arriving amount turns out
        # to be, ``sent - components`` is what crossed. A clamp anywhere in the walk would
        # break this identity, because a clamped amount has a cost nobody attributed.
        costed = _cost_through(graph, amount)
        if not isinstance(costed, RampCost):
            return
        crossed = money.sub(costed.one_way.sent, _component_total(costed))
        events = execute.execute(
            costed, owner_id=OWNER, sequence_from=0, on_date=ON_DATE, capacity_pool=None
        )
        assert_money_close(money.scale(events[0].amount, -1.0), crossed)


class TestTotalFeesRecordedEqualTotalFeesApplied:
    """SC-013's own clause, which is the ledger half of B13."""

    @given(graph=route_graphs.route_graphs(base=Currency.UAH), amount=route_graphs.AMOUNTS)
    def test_the_recorded_lines_sum_to_the_applied_components(
        self, graph: route_graphs.Graph, amount: float
    ) -> None:
        costed = _cost_through(graph, amount)
        if not isinstance(costed, RampCost):
            return
        events = execute.execute(
            costed, owner_id=OWNER, sequence_from=0, on_date=ON_DATE, capacity_pool=None
        )
        recorded = money.total(
            [money.scale(event.amount, -1.0) for event in events if event.kind is EventKind.FEE],
            costed.one_way.sent.currency,
        )
        assert_money_close(recorded, _component_total(costed))

    def test_a_fee_larger_than_the_amount_is_still_one_explicit_line(self) -> None:
        # B13's second clause: fees are explicit ledger lines and never blended into the
        # outcome. A 1 000 fee on 100 sent is recorded as 1 000 of fee -- not as an arriving
        # amount of zero with the loss folded into the rate.
        graph = route_graphs.zero_cost_graph(fixed_fee=500.0)
        costed = _cost_through(graph, 100.0)
        assert isinstance(costed, RampCost)
        events = execute.execute(
            costed, owner_id=OWNER, sequence_from=0, on_date=ON_DATE, capacity_pool=None
        )
        fees = [event for event in events if event.kind is EventKind.FEE]
        assert len(fees) == 1
        assert_money_close(money.scale(fees[0].amount, -1.0), _uah(1_000.0))

    def test_the_fold_of_an_over_charged_movement_balances_without_hiding_anything(
        self,
    ) -> None:
        # 100 sent, 1 000 charged, -900 arriving. The ledger records -1 000 of fee, +900 for
        # the "departure" (more was charged than crossed, so the sign inverts) and -900
        # arriving, and the hryvnia balance nets to -1 000: the whole of what was charged.
        # Every figure is reported and none is floored.
        graph = route_graphs.zero_cost_graph(fixed_fee=500.0)
        costed = _cost_through(graph, 100.0)
        assert isinstance(costed, RampCost)
        folded = engine.fold(
            execute.execute(
                costed, owner_id=OWNER, sequence_from=0, on_date=ON_DATE, capacity_pool=None
            ),
            base_currency=Currency.UAH,
            consumption_method="fifo",
        )
        assert_money_close(folded.accounts[Currency.UAH].balance, _uah(-1_000.0))
        assert_money_close(
            folded.accounts[Currency.UAH].balance,
            money.sub(costed.one_way.arrived, costed.one_way.sent),
        )


class TestAnOverrunHeadroomIsReportedNegativeRatherThanZero:
    """The clamp this feature could newly have introduced, in the capacity accumulator."""

    def test_a_rail_already_over_its_cap_reports_a_negative_headroom(self) -> None:
        # A cap lowered mid-month, or a movement recorded that the check should have refused.
        # Either way the honest figure is negative, and it reads as the diagnostic it is.
        used = capacity.record(
            capacity.NOTHING_CONSUMED,
            pool=route_graphs.CARD_POOL,
            amount=_uah(120_000.0),
            on_date=ON_DATE,
        )
        assert_money_close(
            capacity.headroom(
                used, pool=route_graphs.CARD_POOL, cap=_uah(100_000.0), on_date=ON_DATE
            ),
            _uah(-20_000.0),
        )

    def test_deploying_against_an_overrun_rail_reports_the_overrun(self) -> None:
        # ``deployed`` is negative and the fallback consequently exceeds the request. Both are
        # nonsense as instructions and exact as diagnostics, which is the right way round: a
        # floor at zero would look tidier and would hide the overrun that caused it.
        used = capacity.record(
            capacity.NOTHING_CONSUMED,
            pool=route_graphs.CARD_POOL,
            amount=_uah(120_000.0),
            on_date=ON_DATE,
        )
        outcome = capacity.deploy(
            _uah(10_000.0),
            limit=capacity.PoolCapacity(pool=route_graphs.CARD_POOL, cap=_uah(100_000.0)),
            used=used,
            policy=capacity.HOLD_AS_CASH,
            on_date=ON_DATE,
            redirect_to=None,
        )
        assert_money_close(outcome.deployed, _uah(-20_000.0))
        assert_money_close(outcome.fallbacks[0].amount, _uah(30_000.0))
        assert outcome.deployed.amount < 0.0

    @given(
        cap=st.floats(min_value=1.0, max_value=100_000.0, allow_nan=False),
        already=st.floats(min_value=0.0, max_value=500_000.0, allow_nan=False),
        requested=st.floats(min_value=0.0, max_value=500_000.0, allow_nan=False),
    )
    def test_requested_always_equals_deployed_plus_what_fell_back(
        self, cap: float, already: float, requested: float
    ) -> None:
        # The conservation statement for a deployment, over every combination including the
        # overrun ones: nothing is lost between the plan and the two figures that account for
        # it. This is the property a clamp breaks -- a floored ``deployed`` with an unfloored
        # fallback would make the two stop adding up, and a floored *both* would make the
        # excess disappear.
        used = capacity.record(
            capacity.NOTHING_CONSUMED,
            pool=route_graphs.CARD_POOL,
            amount=_uah(already),
            on_date=ON_DATE,
        )
        outcome = capacity.deploy(
            _uah(requested),
            limit=capacity.PoolCapacity(pool=route_graphs.CARD_POOL, cap=_uah(cap)),
            used=used,
            policy=capacity.HOLD_AS_CASH,
            on_date=ON_DATE,
            redirect_to=None,
        )
        displaced = sum(occurrence.amount.amount for occurrence in outcome.fallbacks)
        assert is_close(outcome.requested.amount, outcome.deployed.amount + displaced)


class TestNoTaxSettlementIsEverShavedToWhatTheCashAllows:
    """SC-004 over generated scenarios: the three ways a due date could be made to fit.

    A tax bill that lands in a month with no cash is the boundary this feature exists to
    surface, and it is a boundary that **moves** -- with the gain, with the rate, with what was
    withdrawn before the date. Three comfortable answers sit on it, each a clamp in a different
    disguise: overdraw the balance, pay part of it, or sell something to cover the rest. A
    hand-picked withdrawal sits on one side of the boundary and passes forever; generated ones
    walk across it.

    The scenario is **parametrised by the boundary itself**: ``cover`` says how many times the
    liability is left in the account on the due date, so ``cover < 1`` is short by
    construction and ``cover > 1`` is not. Drawing a withdrawal fraction instead put the
    boundary at 0.89 of one axis and left the property drawing a shortfall 4.6% of the time --
    a property that samples the interesting half once in twenty runs is nearly a property that
    never does. What is withdrawn is still bounded by what is there, so the balance is
    non-negative on every date before the due date whatever is drawn; otherwise "no balance
    ever goes negative" would fail for a reason with nothing to do with tax.
    """

    def test_the_strategy_straddles_both_boundaries_that_matter(self) -> None:
        """Reachability asserted **through the strategy's own bounds**, not beside them.

        A hard-coded pair of inputs would stay green while a narrowed strategy quietly stopped
        drawing shortfalls. These are the same constants the ``@given`` below is built from, so
        narrowing either range fails here first and says which boundary was lost.
        """
        assert COVER_MIN < 1.0 < COVER_MAX, "the shortfall boundary is at cover == 1"
        assert PROCEEDS_MIN < PURCHASE_COST < PROCEEDS_MAX, "a loss year and a gain year"

        assert isinstance(
            _settle_tax(proceeds=PROCEEDS_MAX, cover=COVER_MIN),
            tax_settlement.InsufficientCashForTax,
        )
        settled = _settle_tax(proceeds=PROCEEDS_MAX, cover=COVER_MAX)
        assert isinstance(settled, tax_settlement.Settlement)
        assert len(settled.payments) == 1

    @given(
        proceeds=st.floats(min_value=PROCEEDS_MIN, max_value=PROCEEDS_MAX, allow_nan=False),
        cover=st.floats(min_value=COVER_MIN, max_value=COVER_MAX, allow_nan=False),
    )
    def test_nothing_is_overdrawn_paid_in_part_or_sold(self, proceeds: float, cover: float) -> None:
        outcome = _settle_tax(proceeds=proceeds, cover=cover)

        if isinstance(outcome, tax_settlement.InsufficientCashForTax):
            assert outcome.shortfall.amount > 0.0
            assert outcome.available.amount >= 0.0
            assert not _payments_in(outcome.ledger)
            assert _declared_disposals_only(outcome.ledger)
            assert _never_negative(outcome.ledger)
            return

        assert isinstance(outcome, tax_settlement.Settlement), outcome
        assert _declared_disposals_only(outcome.ledger)
        assert _never_negative(outcome.ledger)
        # Whatever is paid is paid whole: the event's magnitude is the liability the statement
        # carries, never what happened to be in the account.
        for payment in outcome.payments:
            paid = next(event for event in outcome.stream if event.sequence == payment.sequence)
            assert_money_close(money.scale(paid.amount, -1.0), payment.amount)


class TestTheShapeOfTheDefectIsAbsentFromTheSource:
    """A scan, because a property test only fails on inputs it happens to draw."""

    @staticmethod
    def _modules() -> Iterator[Any]:
        for package in (terezy.core.results, terezy.core.routes):
            yield package
            for info in pkgutil.iter_modules(package.__path__):
                yield importlib.import_module(f"{package.__name__}.{info.name}")

    @staticmethod
    def _clamps(source: str) -> list[str]:
        """Calls to ``max``/``min`` with a literal zero, and ``abs`` of anything.

        Parsed rather than grepped so that a module *explaining* why it does not clamp does
        not fail -- and, more to the point, so that the obvious fix to such a failure is not
        to stop naming the thing in the prose.

        ``max(walk.disruption, leg.disruption_probability)`` is a maximum over two
        probabilities and is not a clamp, which is why the rule is "with a literal zero"
        rather than "no ``max``".
        """
        offenders: list[str] = []
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id == "abs":
                offenders.append("abs")
            if node.func.id in {"max", "min"} and any(
                isinstance(argument, ast.Constant) and argument.value in (0, 0.0)
                for argument in node.args
            ):
                offenders.append(f"{node.func.id}(..., 0)")
        return offenders

    def test_no_costing_or_result_module_floors_a_figure_at_zero(self) -> None:
        offenders = [
            f"{module.__name__}: {found}"
            for module in self._modules()
            for found in self._clamps(inspect.getsource(module))
        ]
        assert not offenders, (
            "these floor or absolute-value a figure, which is the shape of predecessor "
            "defect B13: " + ", ".join(sorted(offenders))
        )

    def test_the_scan_would_actually_catch_the_predecessors_line(self) -> None:
        # A negative scan that cannot fail protects nothing. This is the defect verbatim.
        assert self._clamps("arrived = max(gross - fee, 0)") == ["max(..., 0)"]
        assert self._clamps("arrived = max(gross - fee, 0.0)") == ["max(..., 0)"]
        assert self._clamps("loss = abs(sent - arrived)") == ["abs"]
        assert self._clamps("worst = max(first, second)") == []


# --- one taxable year settled from cash, sized by the strategy above ----------------------
#
# Deliberately the smallest scenario that can be short: a funded purchase, one disposal, and a
# withdrawal before the payment date. The tax year, the deadline and the rates come from the
# synthetic fixture pack, so no figure here could be mistaken for a Ukrainian liability.


def _tax_events(*, proceeds: float, withdrawal: float) -> tuple[Event, ...]:
    source = prov.of([tax_years.FIXTURE_SOURCE])
    term = CausationRef(kind=CausationKind.INSTRUMENT_TERM, id="fixture:terms", detail="fixture")

    def event(sequence: int, on: date, kind: EventKind, amount: float, **extra: object) -> Event:
        return Event(
            sequence=sequence,
            occurred_on=on,
            kind=kind,
            amount=Money(amount, Currency.UAH, source),
            owner_id=OWNER,
            caused_by=term,
            lot_ref=extra.get("lot_ref"),  # type: ignore[arg-type]
            quantity=extra.get("quantity"),  # type: ignore[arg-type]
            allocated_to=None,
            capacity_pool=None,
        )

    return (
        event(1, date(2026, 3, 2), EventKind.CASH_DEPOSIT, DEPOSITED),
        event(
            2,
            date(2026, 3, 2),
            EventKind.PURCHASE,
            -PURCHASE_COST,
            lot_ref=LotRef(instrument_id="fixture_taxable_a", lot_id="lot-a"),
            quantity=100.0,
        ),
        event(
            3,
            SOLD_ON,
            EventKind.PRINCIPAL_REPAYMENT,
            proceeds,
            lot_ref=LotRef(instrument_id="fixture_taxable_a", lot_id=None),
            quantity=100.0,
        ),
        event(4, WITHDRAWN_ON, EventKind.RAMP_MOVEMENT, -withdrawal),
    )


def _settle_tax(
    *, proceeds: float, cover: float
) -> tax_settlement.Settlement | tax_settlement.SettlementRefused:
    """Assess the disposal's year and settle it, leaving ``cover`` liabilities in the account.

    The liability is recomputed here to *size the withdrawal*, never to check one: what the
    engine assesses is asserted against hand arithmetic in
    ``tests/worked_examples/test_tax_payment.py``. Sizing it this way is what puts the
    shortfall boundary in the middle of the strategy instead of at the end of an axis.
    """
    available = DEPOSITED - PURCHASE_COST + proceeds
    gain = proceeds - PURCHASE_COST
    liability = (tax_years.PIT_RATE + tax_years.LEVY_RATE) * gain if gain > 0.0 else 0.0
    withdrawal = available - cover * liability
    events = _tax_events(proceeds=proceeds, withdrawal=withdrawal)
    state = engine.fold(
        events, base_currency=Currency.UAH, consumption_method=lots.LotMethod.FIFO.value
    )
    charged = flat_rate.charge(
        events[2],
        tax_years.TAXED_CLASS,
        TaxContext(
            instrument_id="fixture_taxable_a",
            taxable_event=TaxableEventKind.DISPOSAL_GAIN,
            taxable_base=state.disposals[0].realised_gain_base_ccy,
            charged_for_year=SOLD_ON.year,
        ),
    )
    assert isinstance(charged, TaxCharge), charged
    assessed = tax_year.statements(
        state,
        (charged,),
        rules=tax_years.rules(),
        tax_classes=tax_years.TAX_PACK,
        filing=tax_years.filing(y2027=True),
        method=lots.LotMethod.FIFO,
        switches=tax_years.positions(),
    )
    assert isinstance(assessed, tuple), assessed
    return tax_settlement.settle(
        events,
        assessed,
        owner_id=OWNER,
        base_currency=Currency.UAH,
        method=lots.LotMethod.FIFO,
        horizon_end=TAX_HORIZON,
    )


def _payments_in(state: engine.LedgerState) -> list[Event]:
    return [event for event in state.applied if event.kind is EventKind.TAX_PAYMENT]


def _declared_disposals_only(state: engine.LedgerState) -> bool:
    """FR-010: the only disposal in the ledger is the one the scenario declared."""
    return [disposal.sequence for disposal in state.disposals] == [3]


def _never_negative(state: engine.LedgerState) -> bool:
    history = engine.history(
        state.applied, base_currency=Currency.UAH, consumption_method=lots.LotMethod.FIFO.value
    )
    return all(snapshot.accounts[Currency.UAH].balance.amount >= 0.0 for snapshot in history)
