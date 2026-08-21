"""Canonical form: ledger values as nested tuples of primitives. Structural, not serial.

The core's contribution to determinism (C4, FR-012). The **digest** lives in
``terezy.data.manifest``, because hashing implies serialisation and ``hashlib`` is on the
core's forbidden-imports list. What lives here is the part that has to be a domain
decision: *which* facts a result is identified by, and *how* each one is rendered
unambiguously. Nothing below encodes bytes, opens anything, or formats anything for a
reader.

**Amounts are ``float.hex()``, not ``repr`` and not rounded** (research.md D5). The hex
form is exact and round-trippable, so the digest asserts bit-identity of every amount.
That is deliberately *stricter* than the project tolerance: the tolerance exists because
hand-computed arithmetic and float arithmetic differ, whereas determinism means the same
code on the same inputs must produce the same bits. A digest over a rounded rendering
would mask any nondeterminism smaller than the rounding unit -- precisely the bug the
check exists to find.

**Dates are integer triples, not ISO strings.** ``(2026, 8, 21)`` rather than
``"2026-08-21"``: same information, no string formatting anywhere in the core, and no
question about which of several date formats a future reader should assume.

**Provenance is deliberately excluded, and this is the one exclusion that matters.**
Provenance identifies *sources*. If a source's ``verified_on`` is filled in later, a digest
that included provenance would change even though no computed amount moved -- so C4 would
fail on a documentation update, and the only available fix would be to stop trusting C4.
The digest covers amounts, currencies, dates, kinds and identifiers; the unverified *mark*
is a separate claim, asserted separately by E5 (``tests/contract/``). Do not add provenance
here to make some other test easier.

**Mappings are emitted sorted.** A dict's iteration order is its insertion order, which is
the fold order, which is a property of the stream -- so it is *usually* stable and would
silently stop being so the first time a caller merged two ledgers. Sorting by key makes the
form a function of the content alone.
"""

from __future__ import annotations

from datetime import date

from terezy.core.ledger.accounts import CashBalance
from terezy.core.ledger.engine import LedgerState
from terezy.core.ledger.events import CausationRef, Event, LotRef
from terezy.core.ledger.lots import Disposal, Lot, Position
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money

type Canonical = str | int | tuple[Canonical, ...] | None
"""A canonical value: a string, an integer, ``None``, or a tuple of them.

Note what is *not* in the union: ``float``. Every number that could carry rounding is
rendered by ``float.hex()`` into a string first, so no consumer of this form can compare
two amounts with the wrong precision by accident.
"""


def of_number(value: float) -> str:
    """One float, exactly and reversibly: ``float.hex()``."""
    return value.hex()


def of_optional_number(value: float | None) -> str | None:
    """One float or its genuine absence. ``None`` renders as ``None``, never as zero.

    A quantity that was never stated and a quantity of zero are different facts -- a
    cash-only event moved no units, a lot of zero units may not exist at all -- and
    collapsing them would make two different ledgers digest identically.
    """
    return None if value is None else of_number(value)


def of_date(value: date) -> tuple[int, int, int]:
    """One date as ``(year, month, day)``."""
    return (value.year, value.month, value.day)


def of_optional_date(value: date | None) -> tuple[int, int, int] | None:
    """One date or its genuine absence -- the opening ledger has no date."""
    return None if value is None else of_date(value)


def of_money(value: Money) -> tuple[str, str]:
    """One amount as ``(hex amount, currency code)``.

    The currency travels with the number and is never dropped: two identical amounts in
    different currencies are different facts, and a digest that could not tell them apart
    would be blind to the conflation Principle VI forbids. Provenance is excluded -- see
    the module docstring.
    """
    return (of_number(value.amount), value.currency.value)


def of_causation(value: CausationRef) -> tuple[str, str, str]:
    """The cause of an event: ``(kind, id, detail)``.

    ``detail`` is included even though it is prose. It is part of what the audit trail
    *says*, so changing it changes the result a reader is given, and a digest that ignored
    it would call two differently-explained results identical.
    """
    return (value.kind.value, value.id, value.detail)


def of_lot_ref(value: LotRef | None) -> tuple[str, str | None] | None:
    """The holding an event touched, or ``None`` where it touched none."""
    return None if value is None else (value.instrument_id, value.lot_id)


def of_event(value: Event) -> tuple[Canonical, ...]:
    """One event, in field order.

    ``owner_id`` is included. There is one owner today, so it contributes nothing to the
    digest in practice -- and the day there are two, a result computed for one of them must
    not be able to digest identically to the other's (Principle VII).
    """
    return (
        value.sequence,
        of_date(value.occurred_on),
        value.kind.value,
        of_money(value.amount),
        value.owner_id,
        of_causation(value.caused_by),
        of_lot_ref(value.lot_ref),
        of_optional_number(value.quantity),
        value.allocated_to,
    )


def of_lot(value: Lot) -> tuple[Canonical, ...]:
    """One lot: identity, acquisition, quantity, and cost in both currencies."""
    return (
        value.lot_id,
        value.instrument_id,
        of_date(value.acquired_on),
        of_number(value.quantity),
        of_money(value.cost_trade_ccy),
        of_money(value.cost_base_ccy),
        of_optional_number(value.fx_rate_used),
    )


def of_position(value: Position) -> tuple[Canonical, ...]:
    """One position: the totals, then the lots in acquisition order.

    The lots are *not* re-sorted. Their order is a fact about the history and the selection
    method depends on it, so a form that normalised it away could digest two positions
    identically that would be taxed differently.
    """
    return (
        value.instrument_id,
        of_number(value.quantity),
        of_money(value.basis_trade_ccy),
        of_money(value.basis_base_ccy),
        tuple(of_lot(lot) for lot in value.lots),
    )


def of_account(value: CashBalance) -> tuple[Canonical, ...]:
    """One cash balance: the three figures FR-009's identity is written in."""
    return (
        value.currency.value,
        of_money(value.inflows),
        of_money(value.outflows),
        of_money(value.balance),
    )


def of_disposal(value: Disposal) -> tuple[Canonical, ...]:
    """One realised disposal: every term of FR-011's identity, and the lots it drew on."""
    return (
        value.sequence,
        of_date(value.occurred_on),
        value.instrument_id,
        of_number(value.quantity),
        of_money(value.proceeds_trade_ccy),
        of_money(value.proceeds_base_ccy),
        of_money(value.consumed_basis_trade_ccy),
        of_money(value.consumed_basis_base_ccy),
        of_money(value.allocated_fees_trade_ccy),
        of_money(value.allocated_fees_base_ccy),
        of_money(value.realised_gain_trade_ccy),
        of_money(value.realised_gain_base_ccy),
        tuple((lot_id, of_number(units)) for lot_id, units in value.consumed_from),
        of_causation(value.caused_by),
    )


def of_result(value: LedgerState) -> tuple[Canonical, ...]:
    """A whole ledger state: the identity of a run's ledger, for the manifest to digest.

    ``consumption_method`` is part of it because the same events under FIFO and under LIFO
    are genuinely different results, and a digest that could not distinguish them would
    let a configuration change pass as a no-op.

    ``applied`` is included in full rather than summarised. The state is a claim about
    those events; recording only the totals would make the digest agree between a correct
    fold and a fold of a different stream that happened to end in the same place.
    """
    return (
        of_optional_date(value.as_of),
        value.base_currency.value,
        value.consumption_method,
        tuple(
            of_account(value.accounts[currency])
            for currency in sorted(value.accounts, key=_currency_key)
        ),
        tuple(of_position(value.positions[key]) for key in sorted(value.positions)),
        tuple(of_disposal(disposal) for disposal in value.disposals),
        tuple(of_event(event) for event in value.applied),
    )


def _currency_key(currency: Currency) -> str:
    """Sort key for a currency: its stable code, not its definition order.

    Sorting an enum by its member order would tie the canonical form to the order the
    members happen to be declared in, so adding a currency to the middle of the enum
    would change the digest of every existing result.
    """
    return currency.value
