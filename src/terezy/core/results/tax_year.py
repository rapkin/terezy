"""Settling a tax year: the payment as an ordinary ledger event, and what stops it.

``core.tax.year`` says what a year owes. This module makes the money leave -- on the declared
due date in the following year, out of the tax-currency cash balance, through the same fold
every other event goes through.

**A payment is an ordinary ledger citizen** (research.md D2), on the precedent feature 008 set
for a declared seed lot. It is an ``EventKind.TAX_PAYMENT`` with a cause naming the statement
it settles, it is folded by ``engine.apply`` like a coupon, and every conservation and
traceability property counts it without being taught it exists. *If a property fails only for
ledgers containing a payment, the event is wrong -- never the invariant.*

**Three things it refuses to do on a due date the cash cannot cover**, each of them the
comfortable answer: overdraw the balance, sell something, or pay late. The first is
:class:`InsufficientCashForTax`; the other two are the owner's recorded deferrals (FR-010,
FR-011), because an engine-invented trade is a tax position taken on his behalf, on the worst
possible day.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date

from terezy.core.errors import LedgerInvariantError
from terezy.core.ledger import engine
from terezy.core.ledger import events as ev
from terezy.core.ledger.engine import LedgerState
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind
from terezy.core.ledger.lots import LotMethod
from terezy.core.primitives import money
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.tax.year import AnnualStatement, SettlementBehaviour, liability_total


@dataclass(frozen=True, slots=True)
class TaxPayment:
    """One settled annual statement: what left, when, and which assessment it discharged."""

    tax_year: int
    category: str
    due_on: date
    """From the declared timing rule and its non-business-day convention -- never computed by
    the engine, and never today's date."""

    amount: Money
    """What was paid, as a positive magnitude, in the tax currency."""

    sequence: int
    """The sequence number of the ``TAX_PAYMENT`` event in the settled stream, so the figure
    resolves to the record that moved the money (C6)."""


@dataclass(frozen=True, slots=True)
class OpenObligation:
    """A liability assessed inside the horizon and due after it (FR-007).

    Reported rather than dropped, and deliberately **not** brought forward into the horizon
    so that a closing balance would absorb it: an end-of-horizon figure that quietly omits
    next August's tax bill overstates the outcome by exactly the tax.
    """

    tax_year: int
    category: str
    due_on: date
    amount: Money
    reason: str


@dataclass(frozen=True, slots=True)
class OpenCarryforward:
    """A loss still unabsorbed when the horizon ends, attributed to its origin year (FR-019)."""

    category: str
    open_balance: Money
    origins: tuple[tuple[int, Money], ...]
    """``(origin year, amount still open)``. A balance whose origins nobody kept could not be
    checked against a later expiry rule, and could not tell a reader which year's loss is
    still working for him."""


@dataclass(frozen=True, slots=True)
class Settlement:
    """A ledger with its tax paid: the stream, the payments, and what is still outstanding."""

    stream: tuple[Event, ...]
    """The whole event stream with payments woven in and renumbered.

    The **whole** stream rather than just the payments: a caller handed a handful of payment
    events would have to merge and renumber them itself, and both ways that goes wrong produce
    a ledger that folds and lies (see :func:`_merged`).
    """

    ledger: LedgerState
    """The fold of :attr:`stream`. Returned rather than left to the caller so that the state
    the cash checks were made against is the state the caller reports from."""

    payments: tuple[TaxPayment, ...]
    outstanding: tuple[OpenObligation, ...]
    carryforward: tuple[OpenCarryforward, ...]


@dataclass(frozen=True, slots=True)
class InsufficientCashForTax:
    """The tax-currency balance is smaller than the liability on its due date (FR-009, D7).

    A typed outcome, not an exception and not a clamp: it is a fact about the money that the
    owner can act on -- by holding more back, by planning a sale, by choosing a different
    allocation -- and Principle VI says an infeasible plan reports the binding constraint
    instead of results.

    Nothing was sold, nothing was skipped, nothing was paid in part, and no balance went
    negative. The three figures below are the constraint; :attr:`ledger` is everything that
    happened up to the moment it bound.
    """

    tax_year: int
    category: str
    due_on: date
    liability: Money
    """What was owed on the date, as a positive magnitude."""

    available: Money
    """What the tax-currency balance held, immediately before the payment."""

    shortfall: Money
    """``liability - available``. Carried rather than left to the reader to subtract, so the
    figure comes from the same arithmetic every time."""

    ledger: LedgerState
    """The projection up to the failure date, fully traceable (FR-012). Not an empty result:
    everything that happened before the constraint bound is still there to be read."""

    reason: str


@dataclass(frozen=True, slots=True)
class WithholdingNotModelled:
    """A class whose tax an agent withholds at source has a liability to settle (FR-003).

    The settlement behaviour is **declarable** so that a withheld-at-source class -- bank
    deposit interest, per ``SIMULATOR_SPEC.md`` §4.5 -- is later a data-only addition. It is
    not **implemented**: withholding happens at payment, by someone else, and modelling it as
    a self-assessed payment on a deadline that does not apply would put a wrong date on real
    money. So a declared one refuses here and names the gap.
    """

    tax_year: int
    category: str
    amount: Money
    reason: str


SettlementRefused = InsufficientCashForTax | WithholdingNotModelled
"""Why a set of statements could not be settled. Match exhaustively."""


def settle(
    events: Sequence[Event],
    statements: Sequence[AnnualStatement],
    *,
    owner_id: str,
    base_currency: Currency,
    method: LotMethod,
    horizon_end: date,
) -> Settlement | SettlementRefused:
    """Weave each year's payment into the stream on its declared due date, and fold.

    Pure, and no clock: ``horizon_end`` is an input, every due date comes from a declared
    rule, and the same inputs give the same settled stream for ever.

    **Payments sort last on their date.** A payment settles a *previous* year's assessment, so
    anything else happening that day -- a coupon, a redemption -- has already landed and is
    available to pay from. The other ordering would report a shortfall on a day the money
    arrived, which is a wrong answer rather than a conservative one.

    **The cash check happens before each payment, against the running fold.** Not against a
    balance computed once at the start: two liabilities can fall due in one year and draw on
    the same account, and checking both against the opening balance would let the second one
    overdraw.

    ``owner_id`` is required rather than read off the first event, on Principle VII: whose
    money is leaving is a fact the caller states, and a stream with no events at all would
    otherwise have to invent one.
    """
    ordered = ev.in_sequence(events)
    due, refusal = _due(statements)
    if refusal is not None:
        return refusal
    payable = tuple((day, statement) for day, statement in due if day <= horizon_end)
    outstanding = tuple(
        _open(statement, day, horizon_end) for day, statement in due if day > horizon_end
    )
    stream, settling = _merged(ordered, payable, owner_id=owner_id)
    folded = _fold(stream, settling, base_currency=base_currency, method=method)
    if isinstance(folded, InsufficientCashForTax):
        return folded
    state, payments = folded
    return Settlement(
        stream=stream,
        ledger=state,
        payments=payments,
        outstanding=outstanding,
        carryforward=open_carryforward(statements),
    )


def _due(
    statements: Sequence[AnnualStatement],
) -> tuple[tuple[tuple[date, AnnualStatement], ...], WithholdingNotModelled | None]:
    """The statements that owe money, in the order they fall due, and any that cannot be paid.

    A statement owing nothing produces no payment and appears nowhere below -- FR-006's second
    half. That is not the same as it not existing: the statement is there, saying zero and
    citing the rule that produced the zero, and it is why a year of exclusively exempt income
    moves no cash at all (SC-009).
    """
    owing: list[tuple[date, AnnualStatement]] = []
    for statement in statements:
        amount = liability_total(statement.liability)
        if amount.amount <= 0.0:
            continue
        if statement.settlement is SettlementBehaviour.WITHHELD_AT_SOURCE:
            return (), WithholdingNotModelled(
                tax_year=statement.tax_year,
                category=statement.category,
                amount=amount,
                reason=(
                    f"the {statement.tax_year} tax year of {statement.category!r} is "
                    "declared withheld at source, and this feature settles only "
                    "self-assessed liabilities (FR-003). Withholding happens at payment, by "
                    "the agent, on no later date -- paying it here on a declaration deadline "
                    "would put a wrong date on real money. The behaviour is declarable so "
                    "that implementing it stays a data-only change; implementing it belongs "
                    "with the feature that models the income it is withheld from."
                ),
            )
        owing.append((_due_date(statement), statement))
    owing.sort(key=lambda item: (item[0], item[1].tax_year, item[1].category))
    return tuple(owing), None


def _merged(
    events: Sequence[Event],
    payable: Sequence[tuple[date, AnnualStatement]],
    *,
    owner_id: str,
) -> tuple[tuple[Event, ...], Mapping[int, AnnualStatement]]:
    """The stream with payments in place, renumbered **once**, allocations moved with it.

    Once is the whole point. Numbering the events, inserting, and numbering again is how an
    ``allocated_to`` ends up pointing at a fee's former neighbour -- so the merge and the
    numbering happen in the same pass, and the old-to-new mapping is built as it goes.

    A payment is emitted after every event dated on or before its due date, which is what puts
    the day's income on the paying side of the balance.
    """
    built: list[Event] = []
    settling: dict[int, AnnualStatement] = {}
    moved: dict[int, int] = {}
    index = 0
    for due_on, statement in payable:
        while index < len(events) and events[index].occurred_on <= due_on:
            built.append(_moved(events[index], moved, sequence=len(built) + 1))
            index += 1
        payment = _payment_event(statement, sequence=len(built) + 1, owner_id=owner_id)
        built.append(payment)
        settling[payment.sequence] = statement
    for event in events[index:]:
        built.append(_moved(event, moved, sequence=len(built) + 1))
    return tuple(built), settling


def _moved(event: Event, moved: dict[int, int], *, sequence: int) -> Event:
    """One event at its new sequence number, with its fee allocation following it.

    The mapping is filled as the stream is walked, and an allocation always points *backwards*
    or at an event already emitted -- ``events.allocated_fees`` refuses a fee naming an event
    that is not in the stream, and ``events.in_sequence`` has already established the order. A
    forward-pointing allocation would raise a ``KeyError`` here, which is the right answer: it
    would mean the stream was not the history it claims to be.
    """
    moved[event.sequence] = sequence
    return replace(
        event,
        sequence=sequence,
        allocated_to=None if event.allocated_to is None else moved[event.allocated_to],
    )


def _fold(
    stream: tuple[Event, ...],
    settling: Mapping[int, AnnualStatement],
    *,
    base_currency: Currency,
    method: LotMethod,
) -> tuple[LedgerState, tuple[TaxPayment, ...]] | InsufficientCashForTax:
    """Fold the settled stream, checking the balance immediately before each payment."""
    fees = ev.allocated_fees(stream)
    state = engine.opening(base_currency, method.value)
    payments: list[TaxPayment] = []
    for event in stream:
        statement = settling.get(event.sequence)
        if statement is not None:
            short = _shortfall(statement, state, event)
            if short is not None:
                return short
            payments.append(
                TaxPayment(
                    tax_year=statement.tax_year,
                    category=statement.category,
                    due_on=event.occurred_on,
                    amount=liability_total(statement.liability),
                    sequence=event.sequence,
                )
            )
        state = engine.apply(state, event, fees=fees.get(event.sequence, ()))
    return state, tuple(payments)


def _shortfall(
    statement: AnnualStatement, state: LedgerState, payment: Event
) -> InsufficientCashForTax | None:
    """Whether this payment would overdraw the tax-currency balance, and by how much.

    ``None`` means the money is there -- not a degraded outcome, so not a typed one. The
    balance is read for the **currency the liability is assessed in**, which is the tax
    currency by construction: a liability in another currency never gets this far, because
    ``tax.year`` refuses a taxable result it cannot express in the tax currency.
    """
    amount = liability_total(statement.liability)
    balance = state.accounts.get(amount.currency)
    available = money.zero(amount.currency) if balance is None else balance.balance
    if available.amount >= amount.amount:
        return None
    return InsufficientCashForTax(
        tax_year=statement.tax_year,
        category=statement.category,
        due_on=payment.occurred_on,
        liability=amount,
        available=available,
        shortfall=money.sub(amount, available),
        ledger=state,
        reason=(
            f"the {statement.tax_year} tax year of {statement.category!r} owes "
            f"{amount.amount!r} {amount.currency.value} on "
            f"{payment.occurred_on.isoformat()} and the balance holds "
            f"{available.amount!r}. The run stops here: the payment is not skipped, not "
            "shaved to what is available, and not overdrawn, and nothing has been sold to "
            "cover it -- which holdings a forced sale would draw on is the owner's recorded "
            "deferral (FR-010), not this engine's guess. Everything up to this date is in "
            "the ledger attached to this outcome."
        ),
    )


def _due_date(statement: AnnualStatement) -> date:
    """The statement's declared due date, which a self-assessed statement always has."""
    if statement.due_on is None:  # pragma: no cover -- withheld classes never reach a payment
        raise LedgerInvariantError(
            f"the {statement.tax_year} statement for {statement.category!r} is being settled "
            "and carries no due date. Only a withheld-at-source class has none, and one of "
            "those is refused before it reaches a payment."
        )
    return statement.due_on


def _payment_event(statement: AnnualStatement, *, sequence: int, owner_id: str) -> Event:
    """The ledger line that settles one statement: cash out, on the declared due date.

    The cause is the **tax rule** that assessed it, identified by the category, with the
    statement named in the detail. No fifth ``CausationKind`` was added and none was needed: a
    payment is caused by the same declared timing rule that dated it, and that rule is
    resolvable back to the file it was read from -- which is the test the causation set's
    docstring sets for any new member.
    """
    amount = liability_total(statement.liability)
    return Event(
        sequence=sequence,
        occurred_on=_due_date(statement),
        kind=EventKind.TAX_PAYMENT,
        amount=money.scale(amount, -1.0),
        owner_id=owner_id,
        caused_by=CausationRef(
            kind=CausationKind.TAX_RULE,
            id=statement.category,
            detail=(
                f"settles the {statement.tax_year} annual statement for "
                f"{statement.category!r}: {amount.amount!r} {amount.currency.value} assessed "
                f"on a base of {statement.liability.base.amount!r} under the "
                f"{statement.liability.method.value!r} basis method, due "
                f"{_due_date(statement).isoformat()} by the declared timing rule"
            ),
        ),
        lot_ref=None,
        quantity=None,
        allocated_to=None,
        capacity_pool=None,
    )


def _open(statement: AnnualStatement, due_on: date, horizon_end: date) -> OpenObligation:
    """A liability that falls due after the projection ends (FR-007)."""
    return OpenObligation(
        tax_year=statement.tax_year,
        category=statement.category,
        due_on=due_on,
        amount=liability_total(statement.liability),
        reason=(
            f"the {statement.tax_year} tax year of {statement.category!r} is assessed inside "
            f"this projection and falls due on {due_on.isoformat()}, after the horizon ends "
            f"on {horizon_end.isoformat()}. It is reported as outstanding rather than "
            "dropped, and it is deliberately not paid early: a closing balance that quietly "
            "absorbed next year's tax bill would overstate the outcome by exactly the tax."
        ),
    )


def open_carryforward(statements: Sequence[AnnualStatement]) -> tuple[OpenCarryforward, ...]:
    """Every loss still unabsorbed when the last statement of its category closes (FR-019).

    Read off the **last** year of each category rather than accumulated separately, because
    that year's statement already carries the balance and its origins: a second accumulation
    would be a second answer to the same question, and the two would eventually disagree.
    """
    latest: dict[str, AnnualStatement] = {}
    for statement in statements:
        held = latest.get(statement.category)
        if held is None or statement.tax_year > held.tax_year:
            latest[statement.category] = statement
    return tuple(
        OpenCarryforward(
            category=category,
            open_balance=statement.carryforward.open_balance,
            origins=statement.carryforward.origins,
        )
        for category, statement in sorted(latest.items())
        if statement.carryforward is not None and statement.carryforward.open_balance.amount > 0.0
    )
