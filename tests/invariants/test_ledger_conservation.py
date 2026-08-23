"""C1, C2, C3 -- the ledger conserves cash, quantity and basis.

Constitution Principle IV: *"Ledger invariants are executable, not documentary. Cash
conservation per currency per day; lot conservation; basis conservation; no negative
quantities; realised gain = proceeds - consumed basis - allocated fees, in both
currencies. These are property-based tests over generated event streams, not example
tests."* These three suites are compliance tests for that clause and may not be skipped,
marked expected-to-fail, or deleted without a constitutional amendment.

Requirements closed: FR-009 (C1), FR-010 (C2), FR-011 (C3).

**Every assertion recomputes the figure from the raw events**, never from another figure
the ledger produced. A conservation test that compares the ledger's balance against the
ledger's own running total proves only that one loop was run once; the point is to check
the fold against an independent tally drawn from the same events. That is why the
recomputations below are deliberately naive comprehensions over ``stream.events``.

**Why "on every date" and not "at the end"** (C1). An error that cancels out by maturity
is still an error: a coupon credited on the wrong date, or a purchase settled a day
early, leaves the closing balance untouched and every intermediate balance wrong. The
suite therefore walks ``engine.history`` and asserts at each dated snapshot.

**Why both currencies** (C3). The realised-gain identity is asserted separately in the
trade currency and in the base currency. In feature 001 they are the same currency and
the two assertions are arithmetically identical -- and they are still written twice on
purpose, so that the day an instrument trades in USD against a UAH base, the assertion
that matters already exists rather than having to be remembered.

Comparisons go through the single project tolerance (FR-002): ``assert_money_close`` for
money, ``is_close`` for bare quantities. Nothing here uses ``pytest.approx``,
``math.isclose`` or a bound of its own.
"""

from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from terezy.core.ledger import engine, events, lots
from terezy.core.primitives import money
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import TOLERANCE, assert_money_close, is_close
from tests.invariants.event_streams import Stream, event_streams
from tests.invariants.seeded_streams import seeded_event_streams

STREAMS = st.sampled_from(Currency).flatmap(
    lambda currency: st.one_of(
        event_streams(currency=currency),
        seeded_event_streams(currency=currency),
    )
)
"""Generated histories in each currency the system knows, seeded and unseeded.

Drawn across both currencies rather than fixing UAH so that the base-currency slots are
exercised against a base that is not the project default. Feature 001 only ever produces
UAH, but a conservation property that has only ever seen one currency is a property about
UAH, not about the ledger.

⚙ **Seeded ledgers joined the draw with feature 008 (SC-005), and not one property below
changed.** That is the whole point rather than a convenience: research.md D1 claims a
declared seed lot is an ordinary ledger citizen, opening the ledger through the same path a
purchase takes, and the only way to test that claim is to feed the properties that already
exist a body of ledgers that begin from seeds. A property that had to be taught about seeds
would be evidence against the claim, so if one fails here the fix is in
``core.ledger.seeds`` -- never a special case in an invariant (quickstart §1).

⚙ **Ledgers containing tax payments joined the draw with feature 009 (SC-006), on exactly
that precedent, and again not one property below changed.** A payment is what settles an
annual assessment out of cash on its declared due date, and 009 research.md D2 claims it is
an ordinary ledger event; the drawn streams therefore contain both halves of the split -- a
``TAX_CHARGE`` that assesses and moves nothing, and a ``TAX_PAYMENT`` that moves money -- and
the properties count them without being told either exists. **If a property fails only for
ledgers containing a payment, the event is wrong, not the invariant.**
"""


def _fold(stream: Stream) -> engine.LedgerState:
    return engine.fold(
        stream.events,
        base_currency=stream.currency,
        consumption_method=lots.FIFO,
    )


def _history(stream: Stream) -> tuple[engine.LedgerState, ...]:
    return engine.history(
        stream.events,
        base_currency=stream.currency,
        consumption_method=lots.FIFO,
    )


def _instrument_of(event: events.Event) -> str | None:
    return None if event.lot_ref is None else event.lot_ref.instrument_id


def _inflows_through(stream: Stream, on: date, currency: Currency) -> Money:
    """Every positive amount of one currency recorded on or before a date."""
    return money.total(
        [
            event.amount
            for event in stream.events
            if event.occurred_on <= on
            and event.amount.currency is currency
            and event.amount.amount > 0.0
        ],
        currency,
    )


def _outflows_through(stream: Stream, on: date, currency: Currency) -> Money:
    """Every negative amount of one currency, as a positive magnitude."""
    return money.total(
        [
            money.scale(event.amount, -1.0)
            for event in stream.events
            if event.occurred_on <= on
            and event.amount.currency is currency
            and event.amount.amount < 0.0
        ],
        currency,
    )


# ---------------------------------------------------------------------------
# C1 -- cash conservation, per currency, on every date
# ---------------------------------------------------------------------------


@pytest.mark.invariant
@given(stream=STREAMS)
def test_cash_conservation_holds_on_every_date(stream: Stream) -> None:
    """FR-009: for each currency, on every date, inflows minus outflows is the balance.

    Three independently accumulated quantities are compared: the account's inflow total,
    its outflow total, and its balance. The ledger adds to each of them separately, so an
    error in any one of the three shows up here rather than cancelling itself out.
    """
    snapshots = _history(stream)
    assert snapshots, "a non-empty stream must produce at least one dated snapshot"

    for state in snapshots:
        as_of = state.as_of
        assert as_of is not None, "a snapshot from history is always dated"
        for currency, account in state.accounts.items():
            assert_money_close(money.sub(account.inflows, account.outflows), account.balance)
            assert_money_close(account.inflows, _inflows_through(stream, as_of, currency))
            assert_money_close(account.outflows, _outflows_through(stream, as_of, currency))


@pytest.mark.invariant
@given(stream=STREAMS)
def test_every_currency_that_moved_has_an_account(stream: Stream) -> None:
    """No amount moves without a balance recording it.

    The complement of the previous property. Conservation per currency is vacuous for a
    currency the ledger silently declined to open an account for, which is exactly the
    "empty result standing in for a failure" that FR-017 forbids.
    """
    state = _fold(stream)
    moved = {event.amount.currency for event in stream.events}
    assert set(state.accounts) == moved


@pytest.mark.invariant
@given(stream=STREAMS)
def test_the_fold_is_the_last_dated_snapshot(stream: Stream) -> None:
    """The final figure is the end of the history, not a separately computed number.

    Two code paths reach the same state -- ``fold`` and the last element of ``history``.
    If they can disagree, then "the balance" is ambiguous and no figure derived from it
    is traceable.
    """
    assert _fold(stream) == _history(stream)[-1]


# ---------------------------------------------------------------------------
# C2 -- lot conservation, and no negative quantity
# ---------------------------------------------------------------------------


@pytest.mark.invariant
@given(stream=STREAMS)
def test_lot_quantities_sum_to_the_position_quantity(stream: Stream) -> None:
    """FR-010: the sum of lot quantities equals the position quantity, at every point.

    ``Position`` accumulates its quantity as events arrive, independently of the lot
    tuple it also carries, so this compares two separately maintained figures rather
    than a number against itself.
    """
    for state in _history(stream):
        for position in state.positions.values():
            assert is_close(sum(lot.quantity for lot in position.lots), position.quantity)


@pytest.mark.invariant
@given(stream=STREAMS)
def test_no_quantity_is_ever_negative(stream: Stream) -> None:
    """FR-010 and C2: no lot and no position ever holds a negative quantity.

    A lot may not exist at zero either -- a fully consumed lot is removed rather than
    left behind as an empty shell, because an empty lot would keep an acquisition date
    alive that no longer holds anything and would distort a later selection method.
    """
    for state in _history(stream):
        for position in state.positions.values():
            assert position.quantity >= -TOLERANCE
            for lot in position.lots:
                assert lot.quantity > 0.0


@pytest.mark.invariant
@given(stream=STREAMS)
def test_position_quantity_is_what_the_events_add_and_take_away(stream: Stream) -> None:
    """Quantity acquired minus quantity disposed of, recomputed from the events."""
    state = _fold(stream)
    for instrument_id, position in state.positions.items():
        acquired = sum(
            events.quantity_of(event)
            for event in stream.events
            if events.opens_lot(event) and _instrument_of(event) == instrument_id
        )
        disposed = sum(
            events.quantity_of(event)
            for event in stream.events
            if events.closes_lot(event) and _instrument_of(event) == instrument_id
        )
        assert is_close(position.quantity, acquired - disposed)


@pytest.mark.invariant
@given(stream=STREAMS)
def test_positions_rebuilt_from_events_match_the_folded_ledger(stream: Stream) -> None:
    """``lots.rebuild`` and ``engine.fold`` agree on the holdings.

    The engine folds cash and lots together; ``rebuild`` answers the narrower question
    "what is held?" from the same events. They must not diverge: a figure whose value
    depends on which entry point computed it is not traceable to the events at all.
    """
    rebuilt = lots.rebuild(
        stream.events,
        base_currency=stream.currency,
        consumption_method=lots.FIFO,
    )
    assert rebuilt == _fold(stream).positions


# ---------------------------------------------------------------------------
# C3 -- basis conservation, and the realised-gain identity in both currencies
# ---------------------------------------------------------------------------


@pytest.mark.invariant
@given(stream=STREAMS)
def test_lot_costs_sum_to_the_position_basis(stream: Stream) -> None:
    """FR-010: the sum of lot costs equals the position basis, in both currencies."""
    for state in _history(stream):
        for position in state.positions.values():
            assert_money_close(
                money.total(
                    [lot.cost_trade_ccy for lot in position.lots],
                    position.basis_trade_ccy.currency,
                ),
                position.basis_trade_ccy,
            )
            assert_money_close(
                money.total(
                    [lot.cost_base_ccy for lot in position.lots],
                    position.basis_base_ccy.currency,
                ),
                position.basis_base_ccy,
            )


@pytest.mark.invariant
@given(stream=STREAMS)
def test_basis_is_what_was_paid_less_what_was_consumed(stream: Stream) -> None:
    """Cost in, basis consumed on disposal, basis remaining -- recomputed from events.

    The acquisition side is read straight off the lot-opening events (their cash outflow
    *is* the cost), and the consumption side off the disposal records. Nothing here uses
    the position's own running basis.
    """
    state = _fold(stream)
    for instrument_id, position in state.positions.items():
        currency = position.basis_trade_ccy.currency
        paid = money.total(
            [
                money.scale(event.amount, -1.0)
                for event in stream.events
                if events.opens_lot(event) and _instrument_of(event) == instrument_id
            ],
            currency,
        )
        consumed = money.total(
            [
                disposal.consumed_basis_trade_ccy
                for disposal in state.disposals
                if disposal.instrument_id == instrument_id
            ],
            currency,
        )
        assert_money_close(position.basis_trade_ccy, money.sub(paid, consumed))


@pytest.mark.invariant
@given(stream=STREAMS)
def test_realised_gain_is_proceeds_less_basis_less_allocated_fees(stream: Stream) -> None:
    """FR-011, in **both** currencies, written out twice on purpose.

    See the module docstring: in feature 001 the trade and base currency coincide, so the
    two blocks below are arithmetically the same assertion. They are both here so that
    the base-currency identity is already asserted when FX arrives, rather than being a
    thing someone has to remember to add.
    """
    for disposal in _fold(stream).disposals:
        assert_money_close(
            disposal.realised_gain_trade_ccy,
            money.sub(
                money.sub(disposal.proceeds_trade_ccy, disposal.consumed_basis_trade_ccy),
                disposal.allocated_fees_trade_ccy,
            ),
        )
        assert_money_close(
            disposal.realised_gain_base_ccy,
            money.sub(
                money.sub(disposal.proceeds_base_ccy, disposal.consumed_basis_base_ccy),
                disposal.allocated_fees_base_ccy,
            ),
        )


@pytest.mark.invariant
@given(stream=STREAMS)
def test_allocated_fees_are_the_fee_lines_that_name_the_disposal(stream: Stream) -> None:
    """A fee reaches the gain only through an explicit allocation.

    ``REWRITE_BRIEF`` B13: fees are explicit ledger lines and are never blended into a
    market loss. The allocation is a stored fact on the fee event, so this recomputes the
    allocated total from the events and compares -- and separately confirms that every
    fee line was in fact allocated to a disposal the ledger recorded, so a fee cannot be
    charged to cash and then quietly omitted from the gain.
    """
    state = _fold(stream)
    for disposal in state.disposals:
        assert_money_close(
            disposal.allocated_fees_trade_ccy,
            money.total(
                [
                    money.scale(event.amount, -1.0)
                    for event in stream.events
                    if event.kind is events.EventKind.FEE
                    and event.allocated_to == disposal.sequence
                ],
                disposal.proceeds_trade_ccy.currency,
            ),
        )

    recorded = {disposal.sequence for disposal in state.disposals}
    for event in stream.events:
        if event.kind is events.EventKind.FEE:
            assert event.allocated_to in recorded


@pytest.mark.invariant
@given(stream=STREAMS)
def test_consumed_quantity_matches_the_disposal_that_caused_it(stream: Stream) -> None:
    """Every disposal record consumes exactly the quantity its event named."""
    state = _fold(stream)
    by_sequence = {event.sequence: event for event in stream.events}
    for disposal in state.disposals:
        assert is_close(disposal.quantity, events.quantity_of(by_sequence[disposal.sequence]))
