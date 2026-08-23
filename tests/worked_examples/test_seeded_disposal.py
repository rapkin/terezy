"""SC-002, FR-003, FR-004: disposing of a seeded lot, with the arithmetic worked out here.

Required test **J2**, first half: *a seed lot with a known basis produces the hand-computed
gain on disposal.* The second half -- a basis-estimated seed marking every downstream tax
figure -- is ``tests/contract/test_estimated_basis_propagates.py``.

Every number below is invented and every one is computed by hand in the comments beside the
assertion that checks it. Nothing here reads a data file: the declaration is stated in this
module so a reader verifying the arithmetic opens one file (the D1 rule
``tests/synthetic.py`` states).

**The scenario.** The owner already holds two lots of one synthetic bond, bought on two dates
at two prices. The projection opens holding them, and then 120 of the 150 units are redeemed
with a fee charged against the disposal.

    lot A   100 units, acquired 2024-03-14, cost  98 000.00 UAH   (known basis)
    lot B    50 units, acquired 2025-06-02, cost  52 500.00 UAH   (known basis)
    disposal 120 units on 2026-05-20, proceeds 138 000.00 UAH, fee 250.00 UAH

FIFO consumes the oldest acquisition first, which is lot A entire and 20 units of lot B.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.instruments.interface import InstrumentDeclaration
from terezy.core.ledger import engine, lots, seeds
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.ledger.seeds import SeedLot
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close, is_close
from tests import synthetic

pytestmark = pytest.mark.worked_example

UAH = Currency.UAH
OWNER = "owner-001"
INSTRUMENT = "ovdp_synthetic_a"
OPENS_ON = date(2026, 1, 1)

DECLARED: dict[str, InstrumentDeclaration] = {
    INSTRUMENT: synthetic.declaration(
        id=INSTRUMENT, terms=synthetic.terms(issue_date=date(2020, 1, 1))
    )
}

LOT_A = SeedLot(
    owner_id=OWNER,
    lot_id="seed-0",
    declared_at="tests/test_seeded_disposal#seed[0]",
    instrument_id=INSTRUMENT,
    quantity=100.0,
    acquired_on=date(2024, 3, 14),
    cost=Money(98_000.0, UAH, prov.EMPTY),
    basis=seeds.KNOWN,
)

LOT_B = SeedLot(
    owner_id=OWNER,
    lot_id="seed-1",
    declared_at="tests/test_seeded_disposal#seed[1]",
    instrument_id=INSTRUMENT,
    quantity=50.0,
    acquired_on=date(2025, 6, 2),
    cost=Money(52_500.0, UAH, prov.EMPTY),
    basis=seeds.KNOWN,
)

_TERM = CausationRef(
    kind=CausationKind.INSTRUMENT_TERM,
    id=f"{INSTRUMENT}:redemption",
    detail="synthetic redemption, worked example",
)


def _opening() -> tuple[Event, ...]:
    opened = seeds.opening_events((LOT_A, LOT_B), DECLARED, opens_on=OPENS_ON)
    assert isinstance(opened, tuple), opened
    return opened


def _with_disposal() -> tuple[Event, ...]:
    """The two opening lots, then a fee and the redemption it is charged against."""
    opened = _opening()
    fee_sequence = len(opened)
    disposal_sequence = fee_sequence + 1
    return (
        *opened,
        Event(
            sequence=fee_sequence,
            occurred_on=date(2026, 5, 20),
            kind=EventKind.FEE,
            amount=Money(-250.0, UAH, prov.EMPTY),
            owner_id=OWNER,
            caused_by=_TERM,
            lot_ref=None,
            quantity=None,
            allocated_to=disposal_sequence,
            capacity_pool=None,
        ),
        Event(
            sequence=disposal_sequence,
            occurred_on=date(2026, 5, 20),
            kind=EventKind.PRINCIPAL_REPAYMENT,
            amount=Money(138_000.0, UAH, prov.EMPTY),
            owner_id=OWNER,
            caused_by=_TERM,
            lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id=None),
            quantity=120.0,
            allocated_to=None,
            capacity_pool=None,
        ),
    )


def _folded(stream: tuple[Event, ...]) -> engine.LedgerState:
    return engine.fold(stream, base_currency=UAH, consumption_method=lots.FIFO)


def test_the_ledger_opens_holding_the_declared_lots() -> None:
    """FR-001, FR-003, US1 scenario 1.

    quantity   = 100 + 50            = 150 units
    cost basis = 98 000 + 52 500     = 150 500.00 UAH
    """
    position = _folded(_opening()).positions[INSTRUMENT]
    assert is_close(position.quantity, 150.0)
    assert_money_close(position.basis_base_ccy, Money(150_500.0, UAH, prov.EMPTY))
    assert_money_close(position.basis_trade_ccy, Money(150_500.0, UAH, prov.EMPTY))


def test_each_lot_keeps_its_own_acquisition_date_and_cost() -> None:
    """FR-003, US1 scenario 3: two acquisitions, not one blended average.

    An average would give both lots a cost of 150 500 / 150 = 1 003.33 per unit and would
    change the tax on any partial disposal -- which is why average-cost is a *declared*
    consumption method this engine does not implement rather than something it does quietly.
    """
    held = _folded(_opening()).positions[INSTRUMENT].lots
    assert [(lot.lot_id, lot.acquired_on, lot.quantity) for lot in held] == [
        ("seed-0", date(2024, 3, 14), 100.0),
        ("seed-1", date(2025, 6, 2), 50.0),
    ]
    assert_money_close(held[0].cost_base_ccy, Money(98_000.0, UAH, prov.EMPTY))
    assert_money_close(held[1].cost_base_ccy, Money(52_500.0, UAH, prov.EMPTY))


def test_the_realised_gain_on_a_seeded_lot_is_the_hand_computed_figure() -> None:
    """SC-002, FR-004, US1 scenario 2, and required test **J2**, first half.

    FIFO consumes lot A whole and 20 of lot B's 50 units:

        consumed basis = 98 000.00                     (all of lot A)
                       + 52 500.00 x 20 / 50           (20 units of lot B)
                       = 98 000.00 + 21 000.00
                       = 119 000.00 UAH

        realised gain  = proceeds - consumed basis - allocated fees
                       = 138 000.00 - 119 000.00 - 250.00
                       = 18 750.00 UAH

    The declared cost is used exactly as if the engine had witnessed the purchase itself:
    nothing about this arithmetic knows the lots were seeded.
    """
    (disposal,) = _folded(_with_disposal()).disposals
    assert is_close(disposal.quantity, 120.0)
    assert disposal.consumed_from == (("seed-0", 100.0), ("seed-1", 20.0))
    assert_money_close(disposal.consumed_basis_base_ccy, Money(119_000.0, UAH, prov.EMPTY))
    assert_money_close(disposal.allocated_fees_base_ccy, Money(250.0, UAH, prov.EMPTY))
    assert_money_close(disposal.realised_gain_base_ccy, Money(18_750.0, UAH, prov.EMPTY))
    assert_money_close(disposal.realised_gain_trade_ccy, Money(18_750.0, UAH, prov.EMPTY))


def test_what_is_left_is_the_remainder_of_the_second_lot() -> None:
    """The unconsumed part of lot B keeps ``cost - consumed``, not a rescaled cost:

        quantity = 50 - 20                    = 30 units
        cost     = 52 500.00 - 21 000.00      = 31 500.00 UAH

    Subtracting is what makes the two halves add back to the original exactly, so basis
    conservation does not depend on two independent multiplications agreeing.
    """
    position = _folded(_with_disposal()).positions[INSTRUMENT]
    assert is_close(position.quantity, 30.0)
    assert_money_close(position.basis_base_ccy, Money(31_500.0, UAH, prov.EMPTY))
    (remaining,) = position.lots
    assert remaining.lot_id == "seed-1"
    assert remaining.acquired_on == date(2025, 6, 2)


def test_the_cash_account_records_the_outlay_the_lots_actually_cost() -> None:
    """A seeded ledger's cash is the history it was given, not a balance invented for it.

        -98 000.00 - 52 500.00 - 250.00 + 138 000.00 = -12 750.00 UAH

    The balance is negative because this stream contains the acquisitions and not the
    funding that paid for them: a seed declares what is *held*, and the deposit that bought
    it is not something the owner declared. Inventing one to make the balance tidy would be
    a placeholder value in the result (FR-024), and cash conservation would then be checking
    a number this engine made up.
    """
    account = _folded(_with_disposal()).accounts[UAH]
    assert_money_close(account.balance, Money(-12_750.0, UAH, prov.EMPTY))
