"""The fold: an event stream in, ledger state out. Pure, and ordered by ``sequence``.

Every figure this project reports comes through here (research.md D3). The instrument
computes its contractual schedule in closed form, the engine applies that schedule as
events, and nothing reaches the output except by being folded. That is what makes FR-008
achievable: a figure is traceable because there is no other way for it to have come into
existence.

**Determinism is by explicit order, never by sort stability.** ``events.in_sequence``
sorts on ``sequence`` and refuses a stream where two events share one, so the fold order
is a property of the stream rather than of the collection the caller happened to build.
This matters more than it looks: several events legitimately share a date -- a coupon, the
tax on it, and the reinvestment of what is left -- and their order changes the result. A
fold that sorted by date alone would produce a different answer depending on how the list
was assembled, and C4's digest would disagree with itself for reasons no reader could
find.

**Fees are indexed before the fold, not accumulated during it.** ``events.allocated_fees``
groups fee lines by the disposal they are charged against in one prior pass, so a fee may
appear anywhere in the stream relative to that disposal. Accumulating them during the fold
would have made "a fee must precede its disposal" an unwritten rule, and an unwritten rule
about a cost is how a cost goes missing.

**Why ``history`` exists beside ``fold``.** C1 is asserted *on every date*, not at the end.
An error that cancels out by maturity -- a coupon credited a day late, a purchase settled a
day early -- leaves the closing balance correct and every intermediate balance wrong. So
the engine can hand back a snapshot per date, and both entry points share one per-event
step: two implementations would be two answers.

Free functions over frozen records. Nothing here performs I/O, formats anything, or
constructs ``Money``: every amount is derived through ``core.primitives.money``, which is
how the mark on an unverified yield reaches the balance and the realised gain (FR-015).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from terezy.core.ledger import accounts, lots
from terezy.core.ledger import events as ev
from terezy.core.ledger.accounts import CashBalance
from terezy.core.ledger.events import Event, EventKind
from terezy.core.ledger.lots import Disposal, Position
from terezy.core.primitives import money
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.routes import capacity as cap


@dataclass(frozen=True, slots=True)
class LedgerState:
    """Everything the ledger knows after folding some prefix of a stream.

    A value, not a store: every function below returns a new one. The mappings are typed
    ``Mapping`` rather than ``dict`` to say that a caller reads them and does not write
    them; nothing here mutates a mapping it was given.
    """

    as_of: date | None
    """The date of the last event folded, or ``None`` before any was.

    ``None`` is a real state and not a missing value: the opening ledger has no date
    because nothing has happened yet. A snapshot from :func:`history` always has one.
    """

    base_currency: Currency
    """The currency every figure is also expressed in. UAH throughout feature 001."""

    consumption_method: str
    """The configured lot selection method. Recorded because it changes the answer.

    Kept in the state rather than passed and forgotten, so that a result can say which
    method produced its basis figures. FIFO and LIFO give different -- both correct --
    taxes on the same trades, and a figure that does not say which it used cannot be
    checked by hand.
    """

    accounts: Mapping[Currency, CashBalance]
    """One balance per currency that has moved. Never a total across currencies."""

    positions: Mapping[str, Position]
    """One position per instrument held or once held, keyed by instrument id."""

    disposals: tuple[Disposal, ...]
    """Every disposal realised so far, in fold order. The basis of every tax on a gain."""

    applied: tuple[Event, ...]
    """The events folded, in sequence order.

    Carried so that any figure in this state can be resolved back to the records behind it
    without the caller having to keep the stream alongside (FR-008, C6). It is also the
    check that nothing was dropped: an event that was folded is here, and an event that is
    here was folded.
    """

    capacity: Mapping[cap.CapacityKey, Money]
    """How much each shared rail has carried in each calendar month.

    One more accumulator in a fold that already accumulates cash per currency, and it is
    accumulated the same way: from the events themselves, with the month read off
    ``occurred_on`` because there is no clock in ``core`` (research.md D7). It is keyed by
    ``(capacity_pool, year, month)`` and **never** by route -- two routes through one card
    consume one limit (research.md D10, and ``routes.capacity``).

    A rail with no key here carried nothing that month, which is a different claim from a
    zero; ``routes.capacity.consumed`` returns ``None`` for it and the full declared cap is
    the honest headroom.

    **It changes no other figure in this state.** The accumulator is read by feasibility, not
    by the cash, lot or basis arithmetic, so C1-C6 hold exactly as they did before it existed
    -- which is a claim the conservation suite checks rather than one this docstring makes.
    """


def opening(base_currency: Currency, consumption_method: str) -> LedgerState:
    """The empty ledger: no dates, no balances, no holdings.

    The consumption method is validated here rather than at the first disposal, so that a
    misconfigured method fails when the run starts instead of halfway through a projection
    that has already produced figures.
    """
    lots.selection_for(consumption_method)
    return LedgerState(
        as_of=None,
        base_currency=base_currency,
        consumption_method=consumption_method,
        accounts={},
        positions={},
        disposals=(),
        applied=(),
        capacity=cap.NOTHING_CONSUMED,
    )


def apply(state: LedgerState, event: Event, *, fees: Iterable[Event]) -> LedgerState:
    """Fold one event into the state.

    ``fees`` is the fee lines allocated to *this* event, passed in rather than looked up,
    because the index over the whole stream is not knowable from one event. Making it a
    required keyword rather than defaulting to empty is deliberate: a default would let a
    caller silently drop every fee in the run and still get a plausible gain.

    The event's currency selects its account, opening one on first use. That is the only
    place an account comes into existence, so C1's "every currency that moved has an
    account" holds by construction rather than by remembering to pre-create them.

    An event naming a ``capacity_pool`` also consumes that rail's monthly capacity, per the
    two-rule accounting :func:`_consumed` states and defends. The month comes from
    ``occurred_on``, which is data.
    """
    ev.check_shape(event)
    currency = event.amount.currency
    account = state.accounts.get(currency) or accounts.opening(currency)
    positions, disposal = lots.advance(
        state.positions,
        event,
        base_currency=state.base_currency,
        consumption_method=state.consumption_method,
        fees=fees,
    )
    return LedgerState(
        as_of=event.occurred_on,
        base_currency=state.base_currency,
        consumption_method=state.consumption_method,
        accounts={**state.accounts, currency: accounts.apply(account, event)},
        positions=positions,
        disposals=state.disposals if disposal is None else (*state.disposals, disposal),
        applied=(*state.applied, event),
        capacity=_consumed(state.capacity, event),
    )


def _consumed(
    used: Mapping[cap.CapacityKey, Money], event: Event
) -> Mapping[cap.CapacityKey, Money]:
    """The capacity accumulator after one event, unchanged when it crossed no rail.

    A separate function so that the ``None`` case is one branch in one place rather than a
    conditional expression inside the state constructor: an event that names no pool is the
    ordinary case, and the accumulator it is given back is the same object.

    **Two rules, one target: consumption equals what the rail actually carried.**

    * A **movement** consumes its magnitude. A rail's limit is on the money put through it,
      and a transfer out and a transfer in of the same size both used the rail.
    * A **fee** consumes its signed charge -- the negation of the event's amount, since a
      fee line records a charge as a negative amount. The fee came out of the money that
      crossed, so together with its movement it accounts for the whole amount sent
      (``routes.execute``'s contract: what the rail carried is the whole of ``sent``).

    The sign on the fee rule is the point, and summing magnitudes instead was a defect:
    a *negative* cost component -- a channel legally trading below its reference -- makes
    the departure larger than ``sent`` and the fee line a credit, and magnitudes counted
    both. 100 000 sent through a discount channel consumed |105 000| + |5 000| = 110 000,
    so headroom went falsely negative and fallbacks fired despite room (FR-015, FR-012).
    """
    if event.capacity_pool is None:
        return used
    if event.kind is EventKind.FEE:
        consumed = money.scale(event.amount, -1.0)
    else:
        consumed = money.scale(event.amount, -1.0 if event.amount.amount < 0.0 else 1.0)
    return cap.record(
        used,
        pool=event.capacity_pool,
        amount=consumed,
        on_date=event.occurred_on,
    )


def fold(
    items: Iterable[Event],
    *,
    base_currency: Currency,
    consumption_method: str,
) -> LedgerState:
    """Fold a whole stream into one state. The single entry point for every figure.

    Order comes from ``events.in_sequence``, which also checks the stream: unique
    sequences, dates that do not run backwards, and every event's fields agreeing with its
    kind. A stream that fails any of those raises rather than folding into a state that
    looks complete.
    """
    records = tuple(items)
    fee_index = ev.allocated_fees(records)
    state = opening(base_currency, consumption_method)
    for event in ev.in_sequence(records):
        state = apply(state, event, fees=fee_index.get(event.sequence, ()))
    return state


def history(
    items: Iterable[Event],
    *,
    base_currency: Currency,
    consumption_method: str,
) -> tuple[LedgerState, ...]:
    """One snapshot per date in the stream, ascending: the ledger as C1 checks it.

    A snapshot is taken after the **last** event of each date, which is the state the
    requirement is about -- "on every date, inflows minus outflows equals the balance"
    describes an end-of-day position, not a position halfway through a day's postings
    where a coupon has landed and the tax on it has not.

    Shares :func:`apply` with :func:`fold`, so the last snapshot and the fold are the same
    state reached the same way; the conservation suite asserts exactly that.
    """
    records = tuple(items)
    fee_index = ev.allocated_fees(records)
    ordered = ev.in_sequence(records)
    state = opening(base_currency, consumption_method)
    snapshots: list[LedgerState] = []
    for index, event in enumerate(ordered):
        state = apply(state, event, fees=fee_index.get(event.sequence, ()))
        last_of_day = (
            index + 1 == len(ordered) or ordered[index + 1].occurred_on != event.occurred_on
        )
        if last_of_day:
            snapshots.append(state)
    return tuple(snapshots)
