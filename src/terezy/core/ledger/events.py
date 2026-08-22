"""The event stream: one dated, typed record per thing that moved money or a holding.

The audit trail behind every figure (FR-008). Nothing in the output is computed alongside
the events; the instrument computes its contractual schedule in closed form, the engine
applies that schedule *as events*, and every reported figure derives from the fold of
those events (research.md D3). An event is therefore the smallest unit of traceability in
the system, and this module defines what one is.

**Why ``caused_by`` is a field and not a reconstruction.** FR-008 requires each record to
identify the instrument term or tax rule that generated it, and C6 asserts it. A
reconstruction -- "this looks like a coupon, so the coupon term must have caused it" --
would be a guess dressed as an audit trail, and would silently start lying the moment two
terms could produce the same shape of event. Storing the cause makes C6 a lookup instead
of an inference, which is the whole difference between a traceable figure and a plausible
one.

**Why ``sequence`` exists when the events are also dated.** Several events legitimately
share a date -- a coupon, the tax charged on it, and a reinvestment of what is left all
happen on the coupon date, and the order among them changes the result. Sorting by date
alone leaves that order to whatever the collection happened to be built in, so the fold
would depend on sort stability. ``sequence`` makes the order an explicit, stored fact:
:func:`in_sequence` orders by it and refuses a stream where it is ambiguous.

**Why ``allocated_to`` exists.** A fee is an explicit ledger line -- it reduces cash on
its own date and under its own event kind (``REWRITE_BRIEF`` B13: fees are never blended
into a market loss). But FR-011 also requires the realised gain to be net of *the fees
allocated to that disposal*, and which disposal a fee belongs to is a fact about the
transaction, not something to infer from adjacency of dates. ``allocated_to`` names the
sequence number of the event the fee is charged against, so the allocation is stored and
:func:`allocated_fees` is a grouping rather than a heuristic.

**No behaviour on the records.** ``Event``, ``CausationRef`` and ``LotRef`` carry only
data; everything below is a free function (owner decision D-E). There is no ``Event``
constructor helper here either: an event is built by whoever knows its cause, and hiding
that behind a factory would make the cause easy to leave unset.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Final, assert_never

from terezy.core.errors import LedgerInvariantError
from terezy.core.primitives.money import Money


class EventKind(Enum):
    """What a record says happened. A closed set: there is no "other".

    The ``value`` strings are part of the canonical form (C4) and of anything a later
    layer renders, so they are a data contract and may not be renamed casually.
    """

    CASH_DEPOSIT = "cash_deposit"
    """Money arriving from outside the modelled system -- the funding of the account."""

    PURCHASE = "purchase"
    """Cash out, a lot in. Opens a lot and must name it."""

    COUPON = "coupon"
    """A contractual interest payment. Cash only; it touches no lot."""

    PRINCIPAL_REPAYMENT = "principal_repayment"
    """Cash in against units surrendered -- the disposal of this feature.

    Redemption at maturity is a disposal like any other: it consumes basis and realises a
    gain or loss, which is why it carries a quantity and closes lots rather than being
    treated as a cash-only receipt.
    """

    REINVESTMENT = "reinvestment"
    """Cash out, a lot in, funded by a coupon rather than by a deposit (FR-019).

    A distinct kind from ``PURCHASE`` even though it opens a lot the same way, because
    the two answer different questions of the projection: how much was put in from
    outside, and how much of the return was ploughed back.
    """

    TAX_CHARGE = "tax_charge"
    """Tax assessed and paid. A zero charge is still a charge and still an event."""

    FEE = "fee"
    """An explicit cost line. See the module docstring on ``allocated_to``."""

    RAMP_MOVEMENT = "ramp_movement"
    """Money crossing a funding route: out of one currency, into another.

    A pair of these records one crossing -- what left the sending side, and what arrived at
    the far end -- because the accounts here are per *currency* and a conversion touches two
    of them. On a route that converts nothing the pair is in one currency and nets to zero,
    which is the honest answer: the money moved between venues, and this ledger has no venue
    dimension to record that in.

    The sign carries the direction, as it does for every other kind. There is deliberately no
    separate "out" and "in" kind: a direction flag beside a signed amount is a second place
    for the direction to live, and two places disagree.

    Distinct from ``CASH_DEPOSIT``, which is money arriving from outside the modelled system.
    A ramp movement is money the owner already had, in a different currency or at a different
    venue, and folding the two together would make the funding of an account
    indistinguishable from the shuffling of it.
    """


class CausationKind(Enum):
    """The kinds of declaration that are allowed to cause an event.

    The first two are exactly the two FR-008 names -- *"each such record MUST identify the
    instrument term or tax rule that generated it"* -- and ``ROUTE_TERM`` joined them with
    feature 002, which charges fees no instrument and no tax rule charges.

    What the set is closed *against* is a **catch-all**: there is no "owner action" and no
    "system" member, because such a member would become the place every event whose cause
    nobody tracked down ends up, and C6 would pass while meaning nothing. Every member here
    names a kind of *declaration* that can be resolved back to the file it was read from, and
    that is the test a fourth member would have to pass.
    """

    INSTRUMENT_TERM = "instrument_term"
    """A declared contractual term of the instrument: a coupon rate, a maturity date."""

    TAX_RULE = "tax_rule"
    """A declared tax rule, identified by its class id."""

    ROUTE_TERM = "route_term"
    """A declared term of a funding route -- a leg's fee, a channel's premium, a spread.

    ⚙ **The third member, added with feature 002.** The docstring above warns against a third
    cause, and the warning stands as written: what it forbids is a *catch-all* -- "an owner
    action", "the system" -- which would become the place every event whose cause nobody
    tracked down ends up, leaving C6 passing while meaning nothing.

    This is the opposite of that. A route term is resolvable to a declaration exactly as an
    instrument term is: ``id`` is the route id and ``detail`` names the component that
    charged. FR-005 requires every fee to be an explicit recorded line, and a ramp fee is
    charged by neither an instrument term nor a tax rule -- so without this member such a fee
    would have to claim a cause it does not have, which is worse than a widened set: a
    traceable figure pointing at the wrong declaration.
    """


@dataclass(frozen=True, slots=True)
class CausationRef:
    """What caused an event, in a form that can be looked up rather than guessed."""

    kind: CausationKind
    """Which kind of declaration caused this event."""

    id: str
    """The identifier of the term or rule -- resolvable back to the declaration."""

    detail: str
    """Plain language naming the specific term, for the output a human reads."""


@dataclass(frozen=True, slots=True)
class LotRef:
    """Which holding, and where relevant which specific lot, an event touches."""

    instrument_id: str
    """The instrument whose position this event affects."""

    lot_id: str | None
    """The lot opened by this event, or ``None`` where no single lot is named.

    Set on a lot-opening event, where it is the identity of the lot being created. On a
    disposal it is ``None``: which lots are consumed is decided by the configured
    selection method, not by the event. A disposal that *does* name a lot is asking for
    specific-lot selection, which this feature does not implement -- and is refused
    loudly rather than having the naming quietly ignored.
    """


@dataclass(frozen=True, slots=True)
class Event:
    """One dated, typed, caused thing that moved money or a holding."""

    sequence: int
    """Position in the stream. Unique, and the sole authority on fold order."""

    occurred_on: date
    """The date the movement is recorded against."""

    kind: EventKind
    """What happened."""

    amount: Money
    """The cash effect, signed: positive into the account, negative out of it.

    Signed rather than paired with a separate direction flag, so that a balance is a sum
    and cannot disagree with a direction that was set wrongly. Carries its own
    provenance, which is how the mark reaches every figure folded from it (FR-015).
    """

    owner_id: str
    """Whose money this is. Present from the first commit per Principle VII.

    There is exactly one owner and no authentication yet. The field is here because
    retrofitting tenancy is the expensive mistake and an unused column is free.
    """

    caused_by: CausationRef
    """The term or rule that produced this event. See the module docstring."""

    lot_ref: LotRef | None
    """The holding this event touches, or ``None`` for a purely cash event."""

    quantity: float | None
    """Units acquired or surrendered, always positive, or ``None`` for cash-only events.

    Unsigned, with the direction carried by :class:`EventKind`, because a quantity is a
    count of units rather than a movement: the same 100 units are 100 whether they are
    being bought or redeemed, and a sign here could contradict the kind.
    """

    allocated_to: int | None
    """The sequence number of the event this amount is charged against, or ``None``.

    Only a ``FEE`` may set it. See the module docstring for why the allocation is stored
    rather than inferred.
    """

    capacity_pool: str | None
    """The shared rail this movement crossed, or ``None`` for a movement that crossed none.

    A rail -- a card, an account, a corridor under a regulatory ceiling -- declares a monthly
    limit, and what consumes that limit is the money put *through* it. ``ledger.engine``
    accumulates the magnitude of every event naming a pool into
    ``LedgerState.capacity``, keyed by the pool and by the month of ``occurred_on``, so a cap
    is state in the fold rather than a clock lookup (research.md D7).

    **Stored rather than inferred**, on exactly ``allocated_to``'s reasoning: which rail a
    movement crossed is a fact about the transaction, and deducing it from the route, the
    venue pair or the adjacency of dates would be a guess dressed as an audit trail. It is
    also why the field is on the *event* and not on a parallel index the caller supplies: an
    index can be forgotten, and a limit silently not consumed is a limit not enforced.

    ``None`` is the ordinary case and is not a missing value: a coupon, a tax charge and a
    purchase inside one venue cross no rail at all.
    """


LOT_OPENING_KINDS: Final[frozenset[EventKind]] = frozenset(
    {EventKind.PURCHASE, EventKind.REINVESTMENT}
)
"""The kinds that create a lot. Cash out, units in."""

LOT_CLOSING_KINDS: Final[frozenset[EventKind]] = frozenset({EventKind.PRINCIPAL_REPAYMENT})
"""The kinds that consume lots. Cash in, units out."""

CASH_ONLY_KINDS: Final[frozenset[EventKind]] = frozenset(
    {
        EventKind.CASH_DEPOSIT,
        EventKind.COUPON,
        EventKind.TAX_CHARGE,
        EventKind.FEE,
        EventKind.RAMP_MOVEMENT,
    }
)
"""The kinds that touch no holding at all."""


def opens_lot(event: Event) -> bool:
    """Whether this event creates a lot."""
    return event.kind in LOT_OPENING_KINDS


def closes_lot(event: Event) -> bool:
    """Whether this event consumes lots."""
    return event.kind in LOT_CLOSING_KINDS


def quantity_of(event: Event) -> float:
    """The units this event moved, or a raised invariant violation if it named none.

    Narrowing helper: a lot-touching event is required by :func:`check_shape` to carry a
    quantity, but the field is ``float | None`` because a cash-only event carries none.
    Callers that have already established the kind use this rather than repeating a
    ``None`` check the shape rule has already made impossible.
    """
    if event.quantity is None:
        raise LedgerInvariantError(
            f"event {event.sequence} of kind {event.kind.value!r} has no quantity, and "
            "the caller required one. A lot-touching event must state how many units it "
            "moved; see events.check_shape."
        )
    return event.quantity


def lot_ref_of(event: Event) -> LotRef:
    """The holding this event touches, or a raised invariant violation if it named none."""
    if event.lot_ref is None:
        raise LedgerInvariantError(
            f"event {event.sequence} of kind {event.kind.value!r} names no holding, and "
            "the caller required one. A lot-touching event must say which instrument it "
            "affects; see events.check_shape."
        )
    return event.lot_ref


def check_shape(event: Event) -> None:
    """Assert one event's fields agree with its kind, or raise naming the disagreement.

    A shape rule per kind, checked once at the top of the fold so that every consumer
    downstream can rely on it instead of re-deriving it. The rules are not defensive
    padding: each one is a way an event could otherwise pass silently through the fold
    and produce a figure that is wrong rather than absent.

    * A lot-opening event with no quantity would move cash and create nothing, so the
      basis would be paid for a holding that does not exist.
    * A zero-quantity lot would keep an acquisition date alive that holds nothing, and
      distort a later selection method (data-model.md: *"a lot may not exist at zero"*).
    * A lot-opening event with a positive cash effect would be a holding acquired for
      free, which in this model means a sign was lost somewhere upstream.
    * A cash-only event carrying a quantity or a lot reference is an event whose author
      believed it touched a holding. Ignoring the extra fields would silently drop
      whatever they meant.

    Raises rather than returning a typed failure: an event stream is produced by this
    engine from a validated declaration, so a malformed event is a bug in the code and
    not a fact about the money (constitution, Engineering Standards).
    """
    if event.kind is not EventKind.FEE and event.allocated_to is not None:
        raise LedgerInvariantError(
            f"event {event.sequence} of kind {event.kind.value!r} is allocated to event "
            f"{event.allocated_to}, but only a fee may be allocated to another event."
        )

    match event.kind:
        case EventKind.PURCHASE | EventKind.REINVESTMENT:
            _check_opening(event)
        case EventKind.PRINCIPAL_REPAYMENT:
            _check_closing(event)
        case (
            EventKind.CASH_DEPOSIT
            | EventKind.COUPON
            | EventKind.TAX_CHARGE
            | EventKind.FEE
            | EventKind.RAMP_MOVEMENT
        ):
            _check_cash_only(event)
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(event.kind)


def _check_opening(event: Event) -> None:
    ref = lot_ref_of(event)
    if ref.lot_id is None:
        raise LedgerInvariantError(
            f"event {event.sequence} opens a lot but does not name it. A lot without an "
            "identity cannot be selected for consumption or traced to its acquisition."
        )
    if quantity_of(event) <= 0.0:
        raise LedgerInvariantError(
            f"event {event.sequence} opens a lot of {event.quantity!r} units. A lot may "
            "not exist at zero or below."
        )
    if event.amount.amount > 0.0:
        raise LedgerInvariantError(
            f"event {event.sequence} opens a lot and increases cash by "
            f"{event.amount.amount!r} {event.amount.currency.value}. Acquiring a holding "
            "costs money; a positive amount here means a sign was lost upstream."
        )


def _check_closing(event: Event) -> None:
    ref = lot_ref_of(event)
    if ref.lot_id is not None:
        raise LedgerInvariantError(
            f"event {event.sequence} disposes of lot {ref.lot_id!r} specifically. "
            "Specific-lot selection is not implemented in this feature -- the configured "
            "consumption method decides which lots are consumed. The naming is refused "
            "rather than ignored, because ignoring it would tax the wrong basis."
        )
    if quantity_of(event) <= 0.0:
        raise LedgerInvariantError(
            f"event {event.sequence} disposes of {event.quantity!r} units. A disposal of "
            "nothing is not an event; it is a missing one."
        )
    if event.amount.amount < 0.0:
        raise LedgerInvariantError(
            f"event {event.sequence} disposes of units and reduces cash by "
            f"{abs(event.amount.amount)!r} {event.amount.currency.value}. Proceeds are "
            "an inflow; a cost of disposal is a fee event allocated to it."
        )


def _check_cash_only(event: Event) -> None:
    if event.quantity is not None:
        raise LedgerInvariantError(
            f"event {event.sequence} of kind {event.kind.value!r} carries a quantity of "
            f"{event.quantity!r} but touches no holding. Ignoring it would drop whatever "
            "it was meant to record."
        )
    if event.lot_ref is not None:
        raise LedgerInvariantError(
            f"event {event.sequence} of kind {event.kind.value!r} names a holding but "
            "touches none. Ignoring the reference would drop whatever it was meant to "
            "record."
        )


def in_sequence(items: Iterable[Event]) -> tuple[Event, ...]:
    """The events in fold order: ascending ``sequence``, checked rather than assumed.

    Two properties are enforced here so that the engine never has to think about them.

    **Sequence numbers are unique.** Sorting a stream with a repeated sequence would
    resolve the tie by sort stability -- that is, by the order the collection happened to
    arrive in -- and the fold would silently become a function of the caller's plumbing.
    C4's digest would then disagree with itself for reasons no reader could find.

    **Dates do not go backwards as the sequence advances.** The stream is a history, and
    ``engine.history`` snapshots at each date on that basis. A stream that jumps back a
    month mid-fold has no meaningful daily balance to snapshot, so it is refused here
    rather than quietly producing per-date figures that omit later corrections.

    Every event's shape is checked in the same pass, so a consumer of this function's
    result may rely on the shape rules of :func:`check_shape`.
    """
    ordered = sorted(items, key=lambda event: event.sequence)

    seen: set[int] = set()
    previous: date | None = None
    for event in ordered:
        if event.sequence in seen:
            raise LedgerInvariantError(
                f"sequence {event.sequence} appears more than once in the event stream. "
                "The fold order would be decided by sort stability rather than by the "
                "stream itself."
            )
        seen.add(event.sequence)
        if previous is not None and event.occurred_on < previous:
            raise LedgerInvariantError(
                f"event {event.sequence} is dated {event.occurred_on.isoformat()}, "
                f"before {previous.isoformat()} at an earlier sequence. An event stream "
                "is a history: it does not run backwards."
            )
        previous = event.occurred_on
        check_shape(event)

    return tuple(ordered)


def dates_of(items: Iterable[Event]) -> tuple[date, ...]:
    """The distinct dates in the stream, ascending. One per snapshot in a history."""
    return tuple(sorted({event.occurred_on for event in items}))


def allocated_fees(items: Iterable[Event]) -> Mapping[int, tuple[Event, ...]]:
    """Fee events grouped by the sequence number of the event they are charged against.

    Computed in one pass before the fold rather than accumulated during it, which is what
    makes the allocation independent of whether the fee happens to precede or follow the
    disposal it belongs to. A one-pass accumulation would have made "fees must come
    first" an unwritten rule of the stream, and an unwritten rule is one that gets broken.

    A fee that names no target is refused: charging cash and then leaving the gain gross
    is the silent-cost defect ``REWRITE_BRIEF`` B13 names, and defaulting the allocation
    to "the next disposal" would be a guess. A fee that names a target which is not in
    the stream is refused for the same reason.

    The stream is materialised on entry because this function reads it twice. A one-shot
    iterator would otherwise be exhausted by the first pass and every fee would silently
    look unallocated -- a wrong answer produced quietly, which is worse than a raise.
    """
    records = tuple(items)
    by_sequence = {event.sequence for event in records}
    grouped: dict[int, list[Event]] = {}
    for event in records:
        if event.kind is not EventKind.FEE:
            continue
        target = event.allocated_to
        if target is None:
            raise LedgerInvariantError(
                f"fee event {event.sequence} is not allocated to anything. A fee reduces "
                "cash, so leaving it unallocated would report a gain gross of a cost "
                "that was actually paid."
            )
        if target not in by_sequence:
            raise LedgerInvariantError(
                f"fee event {event.sequence} is allocated to event {target}, which is "
                "not in this stream."
            )
        grouped.setdefault(target, []).append(event)
    return {target: tuple(fees) for target, fees in grouped.items()}
