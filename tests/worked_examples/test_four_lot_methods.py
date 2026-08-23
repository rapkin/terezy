"""E6: one three-lot position, one partial sale, four methods, four different taxes.

```
lot-1   2025-01-10   100 units at 100.00   =  10 000.00
lot-2   2025-06-10   200 units at 130.00   =  26 000.00
lot-3   2025-11-10   100 units at 200.00   =  20 000.00
                     400 units             =  56 000.00   -> 140.00 per unit

2026-03-10   sell 150 units for 37 500.00  (250.00 per unit)
```

**Each method's own arithmetic**, at the fixture rates of 10% PIT and 5% levy:

```
FIFO       lot-1 100 x 100 + lot-2  50 x 130 = 10 000 + 6 500 = 16 500  gain 21 000  tax 3 150
LIFO       lot-3 100 x 200 + lot-2  50 x 130 = 20 000 + 6 500 = 26 500  gain 11 000  tax 1 650
AVERAGE    150 x 140.00                      =                  21 000  gain 16 500  tax 2 475
SPECIFIC   lot-2 150 x 130                   =                  19 500  gain 18 000  tax 2 700
```

**The four are pairwise distinct by construction**, and that is the point of the fixture
rather than a property of it: a fixture where two methods agreed could not detect one being
silently substituted for another. The unit costs are 100 / 130 / 200 and the average is 140,
so no lot's price is the average and no single lot answers what FIFO or LIFO answer.

**None of these four figures is the tax anyone owes.** The Tax Code prescribes no method;
guidance points at the proportional reading for a self-declarant; the methodology binding a
tax agent prescribes FIFO. Which governs is unanswered, so every figure here states the
method that produced it and what backs that method -- see
``tests/contract/test_method_is_never_implicit.py`` for the type-level half of that claim.
"""

from __future__ import annotations

from datetime import date
from typing import Final

import pytest

from terezy.core.ledger import engine, lots
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.ledger.lots import LotMethod
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.tax import flat_rate
from terezy.core.tax import year as tax_year
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxContext
from tests import tax_years

pytestmark = pytest.mark.worked_example

UAH: Final = Currency.UAH
OWNER: Final = "owner-1"
INSTRUMENT: Final = "fixture_three_lots"
SOURCE: Final = prov.of([tax_years.FIXTURE_SOURCE])

SOLD_UNITS: Final = 150.0
PROCEEDS: Final = 37_500.00
HELD_UNITS: Final = 400.0
HELD_BASIS: Final = 56_000.00
AVERAGE_UNIT_COST: Final = 140.00
NAMED_LOT: Final = "lot-2"

BASIS: Final = {
    LotMethod.FIFO: 16_500.00,
    LotMethod.LIFO: 26_500.00,
    LotMethod.AVERAGE_COST: 21_000.00,
    LotMethod.SPECIFIC_LOT: 19_500.00,
}
GAIN: Final = {method: PROCEEDS - basis for method, basis in BASIS.items()}
TAX: Final = {
    LotMethod.FIFO: 3_150.00,
    LotMethod.LIFO: 1_650.00,
    LotMethod.AVERAGE_COST: 2_475.00,
    LotMethod.SPECIFIC_LOT: 2_700.00,
}


def _uah(amount: float) -> Money:
    return Money(amount, UAH, SOURCE)


def _term() -> CausationRef:
    return CausationRef(
        kind=CausationKind.INSTRUMENT_TERM, id=f"{INSTRUMENT}:terms", detail="fixture term"
    )


def _events(*, name_the_lot: bool) -> tuple[Event, ...]:
    """The three purchases and the partial sale, naming a lot only where one was chosen."""
    built: list[Event] = [
        Event(
            sequence=1,
            occurred_on=date(2025, 1, 10),
            kind=EventKind.CASH_DEPOSIT,
            amount=_uah(100_000.00),
            owner_id=OWNER,
            caused_by=_term(),
            lot_ref=None,
            quantity=None,
            allocated_to=None,
            capacity_pool=None,
        )
    ]
    purchases = (
        ("lot-1", date(2025, 1, 10), 100.0, 10_000.00),
        ("lot-2", date(2025, 6, 10), 200.0, 26_000.00),
        ("lot-3", date(2025, 11, 10), 100.0, 20_000.00),
    )
    for index, (lot_id, on, units, cost) in enumerate(purchases):
        built.append(
            Event(
                sequence=2 + index,
                occurred_on=on,
                kind=EventKind.PURCHASE,
                amount=_uah(-cost),
                owner_id=OWNER,
                caused_by=_term(),
                lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id=lot_id),
                quantity=units,
                allocated_to=None,
                capacity_pool=None,
            )
        )
    built.append(
        Event(
            sequence=5,
            occurred_on=date(2026, 3, 10),
            kind=EventKind.PRINCIPAL_REPAYMENT,
            amount=_uah(PROCEEDS),
            owner_id=OWNER,
            caused_by=_term(),
            lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id=NAMED_LOT if name_the_lot else None),
            quantity=SOLD_UNITS,
            allocated_to=None,
            capacity_pool=None,
        )
    )
    return tuple(built)


def _folded(method: LotMethod) -> engine.LedgerState:
    return engine.fold(
        _events(name_the_lot=method is LotMethod.SPECIFIC_LOT),
        base_currency=UAH,
        consumption_method=method.value,
    )


def _charge(method: LotMethod) -> TaxCharge:
    state = _folded(method)
    charged = flat_rate.charge(
        _events(name_the_lot=method is LotMethod.SPECIFIC_LOT)[4],
        tax_years.TAXED_CLASS,
        TaxContext(
            instrument_id=INSTRUMENT,
            taxable_event=TaxableEventKind.DISPOSAL_GAIN,
            taxable_base=state.disposals[0].realised_gain_base_ccy,
            charged_for_year=2026,
        ),
    )
    assert isinstance(charged, TaxCharge), charged
    return charged


def _statement(method: LotMethod) -> tax_year.AnnualStatement:
    state = _folded(method)
    built = tax_year.statements(
        state,
        (_charge(method),),
        rules=tax_years.rules(),
        tax_classes=tax_years.TAX_PACK,
        filing=tax_years.filing(y2026=True),
        method=method,
        switches=tax_years.positions(),
    )
    assert isinstance(built, tuple), built
    found = [
        statement
        for statement in built
        if statement.tax_year == 2026 and statement.category == tax_years.INVESTMENT
    ]
    assert len(found) == 1
    return found[0]


class TestEachMethodMatchesItsOwnArithmetic:
    """FR-025 and SC-002: four hand-computed figures, each checked against its own method."""

    @pytest.mark.parametrize("method", list(LotMethod))
    def test_the_basis_consumed_is_the_hand_computed_one(self, method: LotMethod) -> None:
        assert_money_close(
            _folded(method).disposals[0].consumed_basis_base_ccy, _uah(BASIS[method])
        )

    @pytest.mark.parametrize("method", list(LotMethod))
    def test_the_realised_gain_is_the_hand_computed_one(self, method: LotMethod) -> None:
        assert_money_close(_folded(method).disposals[0].realised_gain_base_ccy, _uah(GAIN[method]))

    @pytest.mark.parametrize("method", list(LotMethod))
    def test_the_years_liability_is_the_hand_computed_one(self, method: LotMethod) -> None:
        assert_money_close(
            tax_year.liability_total(_statement(method).liability), _uah(TAX[method])
        )


class TestTheFourResultsArePairwiseDistinct:
    """The fixture's own property, and the reason it can detect a substituted method."""

    def test_no_two_methods_produce_the_same_tax(self) -> None:
        figures = [
            tax_year.liability_total(_statement(method).liability).amount for method in LotMethod
        ]

        assert len(figures) == len(LotMethod)
        assert len(set(figures)) == len(LotMethod), figures

    def test_no_two_methods_consume_the_same_basis(self) -> None:
        consumed = [
            _folded(method).disposals[0].consumed_basis_base_ccy.amount for method in LotMethod
        ]

        assert len(set(consumed)) == len(LotMethod), consumed


class TestEachMethodDrawsOnTheLotsItSays:
    """The basis is right *and* it came from the right acquisitions (FR-008's trace)."""

    def test_fifo_consumes_the_oldest_lot_whole_and_part_of_the_next(self) -> None:
        assert _folded(LotMethod.FIFO).disposals[0].consumed_from == (
            ("lot-1", 100.0),
            ("lot-2", 50.0),
        )

    def test_lifo_consumes_the_newest_lot_whole_and_part_of_the_middle(self) -> None:
        assert _folded(LotMethod.LIFO).disposals[0].consumed_from == (
            ("lot-3", 100.0),
            ("lot-2", 50.0),
        )

    def test_average_cost_draws_a_share_of_every_lot(self) -> None:
        # 150 / 400 = 0.375 of each: 37.5, 75.0, 37.5 units.
        assert _folded(LotMethod.AVERAGE_COST).disposals[0].consumed_from == (
            ("lot-1", 37.5),
            ("lot-2", 75.0),
            ("lot-3", 37.5),
        )

    def test_specific_lot_consumes_exactly_the_lot_it_named(self) -> None:
        assert _folded(LotMethod.SPECIFIC_LOT).disposals[0].consumed_from == (("lot-2", 150.0),)


class TestConservationHoldsUnderEveryMethod:
    """FR-023 and C2/C3 at the level of this one hand-checked position."""

    @pytest.mark.parametrize("method", list(LotMethod))
    def test_the_lots_still_sum_to_the_position(self, method: LotMethod) -> None:
        position = _folded(method).positions[INSTRUMENT]

        assert is_close(sum(lot.quantity for lot in position.lots), position.quantity)
        assert is_close(position.quantity, HELD_UNITS - SOLD_UNITS)

    @pytest.mark.parametrize("method", list(LotMethod))
    def test_the_lot_costs_still_sum_to_the_basis(self, method: LotMethod) -> None:
        position = _folded(method).positions[INSTRUMENT]
        summed = sum(lot.cost_base_ccy.amount for lot in position.lots)

        assert is_close(summed, position.basis_base_ccy.amount)
        assert is_close(position.basis_base_ccy.amount, HELD_BASIS - BASIS[method])

    def test_average_cost_leaves_the_remaining_position_at_the_same_unit_cost(self) -> None:
        """The defining property of the method: 250 units still at 140.00 each."""
        position = _folded(LotMethod.AVERAGE_COST).positions[INSTRUMENT]

        assert is_close(position.basis_base_ccy.amount / position.quantity, AVERAGE_UNIT_COST)
        for lot in position.lots:
            assert is_close(lot.cost_base_ccy.amount / lot.quantity, _unit_cost(lot.lot_id))


class TestNoFigureHidesItsMethod:
    """FR-024, in the results this example produces."""

    @pytest.mark.parametrize("method", list(LotMethod))
    def test_the_liability_states_the_method_and_what_backs_it(self, method: LotMethod) -> None:
        liability = _statement(method).liability

        assert liability.method is method
        assert liability.standing.method is method
        assert liability.standing.what_the_law_says


def _unit_cost(lot_id: str) -> float:
    """The declared unit cost of one fixture lot: average cost leaves it untouched."""
    return {"lot-1": 100.0, "lot-2": 130.0, "lot-3": 200.0}[lot_id]


def test_basis_consumed_is_answerable_without_a_position_or_a_fold() -> None:
    """The selection is pure and inspectable: the contract's ``basis_consumed`` signature."""
    selection = lots.basis_consumed(
        _held_lots(), SOLD_UNITS, method=lots.AVERAGE_COST, named_lot=None
    )

    assert isinstance(selection, tuple), selection
    assert [lot.lot_id for lot, _ in selection] == ["lot-1", "lot-2", "lot-3"]
    assert is_close(sum(units for _, units in selection), SOLD_UNITS)


def _held_lots() -> tuple[lots.Lot, ...]:
    """The three lots as they stand before the sale."""
    return tuple(
        lots.Lot(
            lot_id=lot_id,
            instrument_id=INSTRUMENT,
            acquired_on=on,
            quantity=units,
            cost_trade_ccy=_uah(cost),
            cost_base_ccy=_uah(cost),
            fx_rate_used=None,
        )
        for lot_id, on, units, cost in (
            ("lot-1", date(2025, 1, 10), 100.0, 10_000.00),
            ("lot-2", date(2025, 6, 10), 200.0, 26_000.00),
            ("lot-3", date(2025, 11, 10), 100.0, 20_000.00),
        )
    )
