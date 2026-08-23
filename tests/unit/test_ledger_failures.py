"""The ledger's loud refusals: one test per way it declines to produce a wrong number.

The conservation and traceability suites generate *valid* streams on purpose -- mixing
invalid ones in would mean the invariants spent most of their examples on inputs that never
reach a fold (``event_streams`` module docstring). This file is the other half: the
malformed and impossible inputs, each asserted to stop the run rather than fold into a
state that looks complete.

**Why every one of these is an exception and not a typed failure.** FR-017 requires a
degraded *outcome* to be a typed result carrying its reason. None of the cases below is an
outcome. A disposal exceeding the holding, a lot without an identity, a stream that runs
backwards, a fee charged to nothing -- each is a statement about the code that built the
stream, and the engine builds the stream from a validated declaration. So each is a
programmer error, each raises ``LedgerInvariantError``, and none may be caught (see
``core/errors.py``).

**Why they are tested at all, given they should be unreachable.** An untested raise is a
raise that has never been executed, and the usual way one rots is a message that crashes
while formatting itself -- so the guard meant to stop a wrong number becomes the thing that
takes the run down for the wrong reason. Each assertion below also checks that the message
names the offending value, because the message *is* the remedy.

Also here: the parts of the ledger the generated streams do not reach -- LIFO ordering, the
empty ledger, partial lot consumption checked by hand.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from terezy.core.errors import CurrencyMismatchError, LedgerInvariantError
from terezy.core.ledger import accounts, canonical, engine, events, lots
from terezy.core.primitives import money, provenance
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close

OWNER = "owner-001"
INSTRUMENT = "ovdp-synthetic-a"

SOURCE = provenance.of(
    [
        provenance.SourceRef(
            id="test/ledger_failures",
            citation="synthetic test input",
            retrieved_on=date(2026, 8, 1),
            verified_on=date(2026, 8, 21),
        )
    ]
)

TERM = events.CausationRef(
    kind=events.CausationKind.INSTRUMENT_TERM,
    id=f"{INSTRUMENT}:terms",
    detail="synthetic instrument term",
)


def _uah(amount: float) -> Money:
    return Money(amount, Currency.UAH, SOURCE)


def _event(
    sequence: int,
    kind: events.EventKind,
    amount: float,
    *,
    day: int = 1,
    lot_ref: events.LotRef | None = None,
    quantity: float | None = None,
    allocated_to: int | None = None,
    capacity_pool: str | None = None,
) -> events.Event:
    return events.Event(
        sequence=sequence,
        occurred_on=date(2026, 1, day),
        kind=kind,
        amount=_uah(amount),
        owner_id=OWNER,
        caused_by=TERM,
        lot_ref=lot_ref,
        quantity=quantity,
        allocated_to=allocated_to,
        capacity_pool=capacity_pool,
    )


def _deposit(sequence: int = 0, *, day: int = 1) -> events.Event:
    return _event(sequence, events.EventKind.CASH_DEPOSIT, 100_000.0, day=day)


def _purchase(
    sequence: int,
    lot_id: str,
    *,
    cost: float,
    quantity: float,
    day: int = 1,
) -> events.Event:
    return _event(
        sequence,
        events.EventKind.PURCHASE,
        -cost,
        day=day,
        lot_ref=events.LotRef(instrument_id=INSTRUMENT, lot_id=lot_id),
        quantity=quantity,
    )


def _redemption(
    sequence: int,
    *,
    proceeds: float,
    quantity: float,
    day: int = 9,
) -> events.Event:
    return _event(
        sequence,
        events.EventKind.PRINCIPAL_REPAYMENT,
        proceeds,
        day=day,
        lot_ref=events.LotRef(instrument_id=INSTRUMENT, lot_id=None),
        quantity=quantity,
    )


def _fold(stream: list[events.Event], *, method: str = lots.FIFO) -> engine.LedgerState:
    return engine.fold(stream, base_currency=Currency.UAH, consumption_method=method)


# ---------------------------------------------------------------------------
# Event shape
# ---------------------------------------------------------------------------


def test_a_lot_opening_event_must_name_its_lot() -> None:
    """An anonymous acquisition can never be selected for consumption or traced."""
    event = _purchase(1, "lot-1", cost=500.0, quantity=10.0)
    anonymous = replace(event, lot_ref=events.LotRef(instrument_id=INSTRUMENT, lot_id=None))
    with pytest.raises(LedgerInvariantError, match="does not name it"):
        events.check_shape(anonymous)


def test_a_lot_opening_event_must_carry_a_quantity() -> None:
    """Cash out and no units in would pay a basis for a holding that does not exist."""
    event = replace(_purchase(1, "lot-1", cost=500.0, quantity=10.0), quantity=None)
    with pytest.raises(LedgerInvariantError, match="no quantity"):
        events.check_shape(event)


def test_a_lot_may_not_be_opened_at_zero_units() -> None:
    """data-model.md: a lot may not exist at zero. Nor may it be created at zero."""
    event = _purchase(1, "lot-1", cost=500.0, quantity=0.0)
    with pytest.raises(LedgerInvariantError, match="may not exist at zero"):
        events.check_shape(event)


def test_a_lot_opening_event_may_not_increase_cash() -> None:
    """A holding acquired for money *received* means a sign was lost upstream."""
    event = _event(
        1,
        events.EventKind.PURCHASE,
        +500.0,
        lot_ref=events.LotRef(instrument_id=INSTRUMENT, lot_id="lot-1"),
        quantity=10.0,
    )
    with pytest.raises(LedgerInvariantError, match="sign was lost"):
        events.check_shape(event)


def test_a_disposal_may_not_name_a_specific_lot() -> None:
    """Specific-lot selection is refused rather than ignored.

    Ignoring the naming would consume lots by the configured method instead, which is a
    different basis and therefore a different tax -- computed silently, from an instruction
    the caller believed had been followed. E6 in ``docs/REQUIRED_TESTS.md`` is where
    specific-lot selection arrives; until then this is a refusal.
    """
    event = replace(
        _redemption(1, proceeds=600.0, quantity=5.0),
        lot_ref=events.LotRef(instrument_id=INSTRUMENT, lot_id="lot-1"),
    )
    with pytest.raises(LedgerInvariantError, match="Specific-lot selection is not implemented"):
        events.check_shape(event)


def test_a_tax_charge_may_not_move_cash() -> None:
    """FR-001, and defect B5's structural cure: an assessment settles nothing.

    ⚙ **Feature 009.** This is the check that makes "no tax is deducted at event time" a
    property of the ledger rather than a discipline in two result modules. Both of them --
    ``results.project`` and ``results.fund`` -- used to give the charge event the negated
    charge as its cash effect, and it was invisible only because every class in the shipped
    registry was exempt, so the deduction happened to be zero. With this rule in place a
    stream that deducts tax at trade time cannot be folded by any caller, including one
    written later.
    """
    event = _event(1, events.EventKind.TAX_CHARGE, -90.0, day=2)
    with pytest.raises(LedgerInvariantError, match="A charge is an assessment"):
        events.check_shape(event)


def test_a_tax_charge_of_either_signed_zero_is_accepted() -> None:
    """The sign of a zero says nothing about the money, and the check tests the magnitude.

    ``-0.0`` is what ``tax.year.memo_amount`` produces -- a charge recorded on the outflow
    side at no magnitude -- and ``0.0`` is what a hand-built fixture is likely to write. Both
    are the same claim, and a rule that admitted one and refused the other would be a rule
    about floating-point representation rather than about tax.
    """
    events.check_shape(_event(1, events.EventKind.TAX_CHARGE, -0.0, day=2))
    events.check_shape(_event(2, events.EventKind.TAX_CHARGE, 0.0, day=2))


def test_a_tax_payment_may_not_credit_the_account() -> None:
    """Settling a liability takes money out; this feature models no refund (FR-011)."""
    event = _event(1, events.EventKind.TAX_PAYMENT, 90.0, day=2)
    with pytest.raises(LedgerInvariantError, match="sign was lost upstream"):
        events.check_shape(event)


def test_a_tax_payment_takes_money_out_and_touches_no_holding() -> None:
    """The ordinary case, folded: cash down by the liability, positions untouched."""
    stream = [
        _deposit(0),
        _purchase(1, "lot-1", cost=1_000.0, quantity=10.0, day=2),
        _event(2, events.EventKind.TAX_PAYMENT, -230.0, day=3),
    ]
    state = _fold(stream)
    assert_money_close(state.accounts[Currency.UAH].balance, _uah(98_770.0))
    assert state.positions[INSTRUMENT].quantity == 10.0
    assert state.disposals == ()


def test_a_disposal_of_nothing_is_refused() -> None:
    event = _redemption(1, proceeds=600.0, quantity=0.0)
    with pytest.raises(LedgerInvariantError, match="not an event; it is a missing one"):
        events.check_shape(event)


def test_a_disposal_may_not_reduce_cash() -> None:
    """A cost of disposal is a fee line allocated to it, not a negative proceeds."""
    event = _event(
        1,
        events.EventKind.PRINCIPAL_REPAYMENT,
        -600.0,
        lot_ref=events.LotRef(instrument_id=INSTRUMENT, lot_id=None),
        quantity=5.0,
    )
    with pytest.raises(LedgerInvariantError, match="Proceeds are an inflow"):
        events.check_shape(event)


def test_a_cash_only_event_may_not_carry_a_quantity() -> None:
    event = replace(_deposit(), quantity=3.0)
    with pytest.raises(LedgerInvariantError, match="carries a quantity"):
        events.check_shape(event)


def test_a_cash_only_event_may_not_name_a_holding() -> None:
    event = replace(_deposit(), lot_ref=events.LotRef(instrument_id=INSTRUMENT, lot_id="lot-1"))
    with pytest.raises(LedgerInvariantError, match="names a holding but touches none"):
        events.check_shape(event)


def test_only_a_fee_may_be_allocated_to_another_event() -> None:
    """Allocation is the fee mechanism. A coupon allocated to a disposal means nothing."""
    event = replace(_event(1, events.EventKind.COUPON, 500.0), allocated_to=0)
    with pytest.raises(LedgerInvariantError, match="only a fee may be allocated"):
        events.check_shape(event)


def test_quantity_of_refuses_an_event_that_states_none() -> None:
    """The narrowing helper raises rather than substituting zero."""
    with pytest.raises(LedgerInvariantError, match="has no quantity"):
        events.quantity_of(_deposit())


def test_lot_ref_of_refuses_an_event_that_names_no_holding() -> None:
    with pytest.raises(LedgerInvariantError, match="names no holding"):
        events.lot_ref_of(_deposit())


# ---------------------------------------------------------------------------
# Stream shape
# ---------------------------------------------------------------------------


def test_a_repeated_sequence_number_is_refused() -> None:
    """Otherwise the fold order would be decided by sort stability."""
    stream = [_deposit(0), _event(0, events.EventKind.COUPON, 10.0)]
    with pytest.raises(LedgerInvariantError, match="appears more than once"):
        events.in_sequence(stream)


def test_a_stream_that_runs_backwards_is_refused() -> None:
    """A history does not run backwards, and a daily balance of one has no meaning."""
    stream = [_deposit(0, day=10), _event(1, events.EventKind.COUPON, 10.0, day=2)]
    with pytest.raises(LedgerInvariantError, match="does not run backwards"):
        events.in_sequence(stream)


def test_in_sequence_orders_by_sequence_and_not_by_arrival() -> None:
    stream = [_event(2, events.EventKind.COUPON, 10.0, day=3), _deposit(0), _deposit(1, day=2)]
    assert [event.sequence for event in events.in_sequence(stream)] == [0, 1, 2]


def test_dates_of_returns_each_date_once_ascending() -> None:
    stream = [_deposit(0, day=5), _deposit(1, day=5), _deposit(2, day=7)]
    assert events.dates_of(stream) == (date(2026, 1, 5), date(2026, 1, 7))


def test_an_unallocated_fee_is_refused() -> None:
    """A fee that reduces cash and names no disposal would leave the gain gross."""
    stream = [_deposit(0), _event(1, events.EventKind.FEE, -25.0)]
    with pytest.raises(LedgerInvariantError, match="not allocated to anything"):
        events.allocated_fees(stream)


def test_a_fee_allocated_outside_the_stream_is_refused() -> None:
    stream = [_deposit(0), _event(1, events.EventKind.FEE, -25.0, allocated_to=99)]
    with pytest.raises(LedgerInvariantError, match="not in this stream"):
        events.allocated_fees(stream)


# ---------------------------------------------------------------------------
# Lots
# ---------------------------------------------------------------------------


def test_an_unknown_consumption_method_is_refused_with_the_known_ones_named() -> None:
    """There is no default method: the choice changes the tax."""
    with pytest.raises(LedgerInvariantError, match="unknown lot consumption method 'average'"):
        lots.consumption_order("average")


def test_the_engine_refuses_an_unknown_method_before_folding_anything() -> None:
    """Validated when the run opens, not at the first disposal, halfway through."""
    with pytest.raises(LedgerInvariantError, match="unknown lot consumption method"):
        engine.opening(Currency.UAH, "specific")


def test_two_lots_may_not_share_an_identity() -> None:
    position = lots.opening(INSTRUMENT, Currency.UAH, Currency.UAH)
    lot = lots.Lot(
        lot_id="lot-1",
        instrument_id=INSTRUMENT,
        acquired_on=date(2026, 1, 1),
        quantity=10.0,
        cost_trade_ccy=_uah(500.0),
        cost_base_ccy=_uah(500.0),
        fx_rate_used=None,
    )
    with pytest.raises(LedgerInvariantError, match="already exists"):
        lots.add_lot(lots.add_lot(position, lot), lot)


def test_consuming_nothing_is_refused() -> None:
    position = _position_of_one_lot()
    with pytest.raises(LedgerInvariantError, match="A disposal of nothing"):
        lots.consume(position, 0.0, lots.FIFO)


def test_consuming_more_than_is_held_is_refused() -> None:
    """Never clamped to the holding: the shortfall is a bug, not a smaller sale."""
    position = _position_of_one_lot()
    with pytest.raises(LedgerInvariantError, match=r"only 10\.0 are held"):
        lots.consume(position, 11.0, lots.FIFO)


def test_disposing_of_something_never_held_is_refused() -> None:
    """Proceeds with no basis would be reported as pure gain."""
    stream = [_deposit(0), _redemption(1, proceeds=600.0, quantity=5.0)]
    with pytest.raises(LedgerInvariantError, match="which is not held"):
        _fold(stream)


def test_a_foreign_amount_cannot_be_expressed_in_the_base_currency() -> None:
    """No rate exists in this feature, and none is invented (FR-007)."""
    with pytest.raises(CurrencyMismatchError, match="no exchange rate exists"):
        lots.base_amount_of(Money(1.0, Currency.USD, SOURCE), Currency.UAH)


def _position_of_one_lot() -> lots.Position:
    return lots.add_lot(
        lots.opening(INSTRUMENT, Currency.UAH, Currency.UAH),
        lots.Lot(
            lot_id="lot-1",
            instrument_id=INSTRUMENT,
            acquired_on=date(2026, 1, 1),
            quantity=10.0,
            cost_trade_ccy=_uah(500.0),
            cost_base_ccy=_uah(500.0),
            fx_rate_used=None,
        ),
    )


# ---------------------------------------------------------------------------
# Behaviour the generated streams do not reach
# ---------------------------------------------------------------------------


def test_fifo_and_lifo_consume_different_lots_and_so_different_basis() -> None:
    """Worked by hand: two lots, ten units each, at 50 and at 90 per unit.

    Sell ten units for 1,000.

    * FIFO consumes lot 1: basis 500, gain ``1000 - 500 = 500``.
    * LIFO consumes lot 2: basis 900, gain ``1000 - 900 = 100``.

    Same trades, same proceeds, two correct and different answers -- which is why the
    method is configured and why there is no default.
    """
    stream = [
        _deposit(0),
        _purchase(1, "lot-1", cost=500.0, quantity=10.0, day=2),
        _purchase(2, "lot-2", cost=900.0, quantity=10.0, day=3),
        _redemption(3, proceeds=1_000.0, quantity=10.0, day=4),
    ]

    fifo = _fold(stream, method=lots.FIFO).disposals[0]
    assert_money_close(fifo.consumed_basis_trade_ccy, _uah(500.0))
    assert_money_close(fifo.realised_gain_trade_ccy, _uah(500.0))
    assert fifo.consumed_from == (("lot-1", 10.0),)

    lifo = _fold(stream, method=lots.LIFO).disposals[0]
    assert_money_close(lifo.consumed_basis_trade_ccy, _uah(900.0))
    assert_money_close(lifo.realised_gain_trade_ccy, _uah(100.0))
    assert lifo.consumed_from == (("lot-2", 10.0),)


def test_a_partial_consumption_splits_the_lot_cost_pro_rata() -> None:
    """Worked by hand: one lot of ten units costing 500, so 50 per unit.

    Sell four units for 300 with a fee of 20 allocated to the disposal.

    * consumed basis ``500 * 4/10 = 200``
    * realised gain ``300 - 200 - 20 = 80``
    * the lot survives holding six units at a remaining cost of ``500 - 200 = 300``
    """
    stream = [
        _deposit(0),
        _purchase(1, "lot-1", cost=500.0, quantity=10.0, day=2),
        _event(2, events.EventKind.FEE, -20.0, day=4, allocated_to=3),
        _redemption(3, proceeds=300.0, quantity=4.0, day=4),
    ]
    state = _fold(stream)
    disposal = state.disposals[0]
    assert_money_close(disposal.consumed_basis_trade_ccy, _uah(200.0))
    assert_money_close(disposal.allocated_fees_trade_ccy, _uah(20.0))
    assert_money_close(disposal.realised_gain_trade_ccy, _uah(80.0))
    assert disposal.consumed_from == (("lot-1", 4.0),)

    position = state.positions[INSTRUMENT]
    assert position.quantity == 6.0
    assert_money_close(position.basis_trade_ccy, _uah(300.0))
    assert len(position.lots) == 1
    assert position.lots[0].quantity == 6.0
    assert_money_close(position.lots[0].cost_trade_ccy, _uah(300.0))


def test_a_fee_allocated_after_its_disposal_still_reaches_the_gain() -> None:
    """The allocation is indexed before the fold, so stream position does not matter.

    Same arithmetic as the previous test with the fee line moved after the disposal. If
    fees were accumulated during the fold, this would silently report a gain of 100 instead
    of 80 -- the cost paid and omitted, which is the defect ``REWRITE_BRIEF`` B13 names.
    """
    stream = [
        _deposit(0),
        _purchase(1, "lot-1", cost=500.0, quantity=10.0, day=2),
        _redemption(2, proceeds=300.0, quantity=4.0, day=4),
        _event(3, events.EventKind.FEE, -20.0, day=4, allocated_to=2),
    ]
    assert_money_close(_fold(stream).disposals[0].realised_gain_trade_ccy, _uah(80.0))


def test_a_fully_consumed_lot_is_removed_rather_than_kept_at_zero() -> None:
    stream = [
        _deposit(0),
        _purchase(1, "lot-1", cost=500.0, quantity=10.0, day=2),
        _redemption(2, proceeds=600.0, quantity=10.0, day=3),
    ]
    position = _fold(stream).positions[INSTRUMENT]
    assert position.lots == ()
    assert position.quantity == 0.0


def test_a_reinvestment_opens_a_lot_just_as_a_purchase_does() -> None:
    """FR-019's coupon reinvestment is a lot-opening kind, not a cash-only one."""
    reinvestment = _event(
        2,
        events.EventKind.REINVESTMENT,
        -400.0,
        day=3,
        lot_ref=events.LotRef(instrument_id=INSTRUMENT, lot_id="lot-r1"),
        quantity=8.0,
    )
    state = _fold([_deposit(0), _event(1, events.EventKind.COUPON, 500.0, day=3), reinvestment])
    assert state.positions[INSTRUMENT].quantity == 8.0
    assert_money_close(state.positions[INSTRUMENT].basis_trade_ccy, _uah(400.0))


def test_an_empty_stream_folds_to_an_empty_ledger_and_no_history() -> None:
    """Not an error and not a result: nothing happened, and the state says so.

    ``as_of`` is ``None`` because there is no date to report, rather than a stand-in date
    that a later reader would take for a fact.
    """
    state = _fold([])
    assert state == engine.opening(Currency.UAH, lots.FIFO)
    assert state.as_of is None
    assert state.accounts == {}
    assert state.positions == {}
    assert state.disposals == ()
    assert state.applied == ()
    assert engine.history([], base_currency=Currency.UAH, consumption_method=lots.FIFO) == ()
    assert lots.rebuild([], base_currency=Currency.UAH, consumption_method=lots.FIFO) == {}


def test_history_snapshots_after_the_last_event_of_each_date() -> None:
    """Two events on one date give one snapshot, holding both.

    An end-of-day balance is what FR-009 is about. A snapshot taken between a coupon and a
    payment made the same day would show a balance that never existed at the close of any
    day.

    ⚙ The second event is a ``TAX_PAYMENT`` since feature 009: a ``TAX_CHARGE`` moves no
    cash any more, so it could no longer make the point this test is about.
    """
    stream = [
        _deposit(0, day=1),
        _event(1, events.EventKind.COUPON, 500.0, day=5),
        _event(2, events.EventKind.TAX_PAYMENT, -90.0, day=5),
    ]
    snapshots = engine.history(stream, base_currency=Currency.UAH, consumption_method=lots.FIFO)
    assert [state.as_of for state in snapshots] == [date(2026, 1, 1), date(2026, 1, 5)]
    assert_money_close(snapshots[-1].accounts[Currency.UAH].balance, _uah(100_410.0))


def test_a_zero_amount_is_neither_an_inflow_nor_an_outflow_and_is_still_recorded() -> None:
    """FR-003: a zero charge is still a charge. It stays in the ledger and traces.

    The account's totals are untouched -- a zero is not an inflow and not an outflow -- and
    the event is still in ``applied``, so the charge is visible as a charge rather than as
    an absence.
    """
    stream = [_deposit(0), _event(1, events.EventKind.TAX_CHARGE, -0.0, day=2)]
    state = _fold(stream)
    account = state.accounts[Currency.UAH]
    assert_money_close(account.outflows, money.zero(Currency.UAH))
    assert_money_close(account.inflows, _uah(100_000.0))
    assert len(state.applied) == 2


def test_net_recomputes_the_balance_from_the_two_totals() -> None:
    """``accounts.net`` is C1's left-hand side and is deliberately not the stored figure."""
    account = accounts.apply(
        accounts.apply(accounts.opening(Currency.UAH), _deposit(0)),
        _event(1, events.EventKind.FEE, -250.0, allocated_to=0),
    )
    assert_money_close(accounts.net(account), _uah(99_750.0))
    assert_money_close(accounts.net(account), account.balance)


def test_the_canonical_form_of_a_cash_only_event_records_absent_fields_as_absent() -> None:
    """A quantity that was never stated is ``None``, never a zero standing in for it."""
    form = canonical.of_event(_deposit(0))
    assert form[6] is None  # lot_ref
    assert form[7] is None  # quantity
    assert form[8] is None  # allocated_to
    assert canonical.of_optional_number(None) is None
    assert canonical.of_optional_date(None) is None
    half = 0.5
    assert canonical.of_number(half) == half.hex()


def test_the_canonical_form_sorts_its_mappings_by_key() -> None:
    """So that the form is a function of the content and not of the fold order."""
    stream = [
        _deposit(0),
        _purchase(1, "lot-1", cost=500.0, quantity=10.0, day=2),
    ]
    state = _fold(stream)
    positions = canonical.of_result(state)[4]
    assert isinstance(positions, tuple)
    assert len(positions) == 1
    assert canonical.of_position(state.positions[INSTRUMENT]) == positions[0]


def test_a_one_shot_iterator_folds_to_the_same_ledger_as_a_list() -> None:
    """The entry points materialise the stream, because they read it more than once.

    A generator handed to ``fold`` would otherwise be exhausted by the fee-allocation pass
    and the fold would see nothing -- an empty ledger returned quietly for a stream that
    was not empty, which is a wrong answer rather than a failure.
    """
    stream = [
        _deposit(0),
        _purchase(1, "lot-1", cost=500.0, quantity=10.0, day=2),
        _event(2, events.EventKind.FEE, -20.0, day=4, allocated_to=3),
        _redemption(3, proceeds=300.0, quantity=4.0, day=4),
    ]
    from_iterator = engine.fold(
        iter(stream), base_currency=Currency.UAH, consumption_method=lots.FIFO
    )
    assert from_iterator == _fold(stream)
    assert (
        lots.rebuild(iter(stream), base_currency=Currency.UAH, consumption_method=lots.FIFO)
        == from_iterator.positions
    )
    assert engine.history(
        iter(stream), base_currency=Currency.UAH, consumption_method=lots.FIFO
    ) == engine.history(stream, base_currency=Currency.UAH, consumption_method=lots.FIFO)
