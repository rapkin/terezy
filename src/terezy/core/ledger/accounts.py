"""Cash balances, one per currency, folded from the event stream.

**C1** (FR-009): *for each currency, on every date, total inflows minus total outflows
equals the recorded cash balance.* This module is what makes that assertable rather than
merely true by construction.

**Why three figures and not one.** A balance alone would satisfy C1 trivially -- comparing
a running sum against itself proves that one loop ran. So :class:`CashBalance` accumulates
``inflows``, ``outflows`` and ``balance`` *separately*, from the same events, and C1
compares three independently maintained numbers. It is also exactly the shape FR-009 is
written in, which is not a coincidence: a requirement phrased as an identity wants the
terms of that identity to exist.

**Why per currency and never combined.** There is no total across currencies here and
there is nowhere to put one. A single "cash" figure spanning UAH and USD would be the
conflation Principle VI forbids, and it is unreachable by construction: adding money of
two currencies raises (C5), so a combined balance cannot be computed even by accident.

**Why the balance may go negative.** Nothing here refuses an outflow larger than the
balance. An overdraft is a *feasibility* question about a plan -- Principle VI's "an
infeasible plan reports the binding constraint instead of results" -- and it belongs where
the plan is checked, with the minimum tickets and the lock-ups, not in the ledger. Clamping
it here would be the silent clamp the constitution puts in its top severity class: the
figures would balance and the plan would be a fiction.

Free functions over a frozen record, and no ``Money`` is constructed here: every amount is
derived through ``core.primitives.money``, which is how an unverified coupon marks the
balance it lands in (FR-015).
"""

from __future__ import annotations

from dataclasses import dataclass

from terezy.core.ledger.events import Event
from terezy.core.primitives import money
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money


@dataclass(frozen=True, slots=True)
class CashBalance:
    """The cash position in one currency: what came in, what went out, what is left."""

    currency: Currency
    """The denomination. Every amount in this record is in it, or the fold raised."""

    inflows: Money
    """Total of every positive amount recorded, as a non-negative figure."""

    outflows: Money
    """Total of every negative amount recorded, as a **positive magnitude**.

    Stored unsigned so that ``inflows - outflows == balance`` reads as FR-009 writes it. A
    signed outflow total would make the identity ``inflows + outflows == balance``, which
    is the same arithmetic and a worse thing to have to check against the requirement.
    """

    balance: Money
    """Accumulated signed net. Compared against ``inflows - outflows`` by C1."""


def opening(currency: Currency) -> CashBalance:
    """An account with nothing in it, in a stated currency.

    ``money.zero`` carries empty provenance, which is correct and is the only place it is:
    an opening balance of nothing is not an observation and rests on no source. The first
    real amount brings its own sources with it.
    """
    return CashBalance(
        currency=currency,
        inflows=money.zero(currency),
        outflows=money.zero(currency),
        balance=money.zero(currency),
    )


def apply(account: CashBalance, event: Event) -> CashBalance:
    """Record one event's cash effect against a balance.

    The sign of ``event.amount`` decides the direction, so a direction cannot disagree
    with the amount it describes. Exactly zero is neither an inflow nor an outflow: it
    still passes through ``balance``, where it changes nothing, and it is *not* dropped --
    the event remains in the ledger and remains traceable, which is how a zero tax charge
    stays visible as a charge rather than becoming an absence (FR-003).

    A foreign amount raises out of ``money.add`` rather than being converted or routed to
    another account. Routing it would mean this function silently decided which account an
    event belonged to; the engine makes that decision, by currency, before calling here.
    """
    signed = event.amount
    inflows = account.inflows
    outflows = account.outflows
    if signed.amount > 0.0:
        inflows = money.add(inflows, signed)
    elif signed.amount < 0.0:
        outflows = money.add(outflows, money.scale(signed, -1.0))
    return CashBalance(
        currency=account.currency,
        inflows=inflows,
        outflows=outflows,
        balance=money.add(account.balance, signed),
    )


def net(account: CashBalance) -> Money:
    """``inflows - outflows`` -- the balance as FR-009 states it, recomputed.

    Deliberately *not* ``account.balance``. This is the left-hand side of C1's identity and
    the stored balance is the right-hand side; a helper that returned the stored figure
    would make the invariant compare a number to itself.
    """
    return money.sub(account.inflows, account.outflows)
