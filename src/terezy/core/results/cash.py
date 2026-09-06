"""Projecting a cash balance: a purchase on the horizon's first day, a release on its last.

The whole lifecycle of a zero-rate balance, and it is two events. There is no coupon, no
distribution and no accrual, because the declared rate is exactly zero -- so nothing happens
between the two dates and the amount that comes back is the amount that went in.

**The release is dated at the horizon's end rather than omitted** (FR-018). A projection with
no arrival at all would report the same ``reaches`` -- a sum over an empty series against an
outlay is not a figure, and a total of zero would refuse the rate instead -- while claiming
something quite different: that nothing ever came out. Releasing the balance at the end is
what makes the span the horizon, which is also why cash is the one member of a ranking the
`rates-in-one-ranking-span-different-periods` gap cannot touch.

**No tax is charged and no class is named** (FR-009). The release returns the basis exactly,
so there is no gain to realise and no income to assess. That is a fact about the arithmetic
rather than an exemption: an exemption is a legal value and would need a citation, and this
feature introduces none.

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from terezy.core.errors import InconsistentTerms
from terezy.core.instruments.cash import CashDeclaration
from terezy.core.ledger import engine, lots
from terezy.core.ledger.engine import LedgerState
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.primitives import money
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from terezy.core.instruments.interface import DateRange, Holding

SELECTION: Final = lots.FIFO
"""Which lot the one disposal consumes.

The fold needs a method because a disposal in general selects between lots. Here one purchase
opens one lot and one release closes it, so every registered selection returns the same lot --
which is why the method is named here rather than carried on ``CashAssumptions``, where it
would offer a caller a choice that cannot change an answer.
"""


@dataclass(frozen=True, slots=True)
class CashProjection:
    """One balance, held from the horizon's first day to its last.

    No ``schedule``, no ``charges`` and **no field for a rate**: what a balance pays is
    declared to be nothing, and a field here would be somewhere for a later contributor to put
    a figure the declaration refuses.
    """

    instrument_id: str

    ledger: LedgerState
    """The folded ledger: the purchase, the release, and the lot between them.

    Carried rather than discarded for ``Projection.ledger``'s reason -- it is the audit trail,
    and every figure the join reads resolves through it.
    """

    released: Money
    """What the balance paid back, in its own currency. Equal to what it cost, by
    construction, which is why no gain arises and no tax is charged."""

    provenance: Provenance
    """The declared rate's citation, and the one observed value behind every figure here.

    **Deliberately the same source :attr:`released` already carries**, and it stays because the
    two say different things: this is what the *projection* rested on, and the amount's own mark
    is what travels with the money. Merging is a union, so the duplicate costs nothing -- what
    it means is that neither path can be checked by removing the other, and the assertion that
    bites is on ``TupleOutcome.reaches``.
    """


def project_cash(
    declaration: CashDeclaration, holding: Holding, horizon: DateRange
) -> CashProjection | InconsistentTerms:
    """Project one balance over one horizon, or the one thing that can be wrong about it.

    **One refusal, where a bond has several**, and the difference is the declaration's: there
    is no cutoff to be after, no minimum number of units, no terms that end before the window,
    no rate to size and no class to resolve. What is left is the window itself -- a balance
    cannot be released before it is placed -- and it is a typed refusal rather than a raise
    because it is a fact about the round trip somebody asked for.
    """
    if horizon.end < holding.purchased_on:
        return InconsistentTerms(
            first_term="horizon.end",
            second_term="holding.purchased_on",
            reason=(
                f"the horizon ends {horizon.end.isoformat()} and {declaration.id!r} is placed "
                f"on {holding.purchased_on.isoformat()}. A balance is released at the end of "
                "the window, so a window that closes before the money is placed would report "
                "it coming back before it went in."
            ),
        )
    paid = money.scale(holding.cost, -1.0)
    # `also_resting_on` rather than `scale`: the declared rate decides this figure without
    # appearing in its arithmetic -- what comes back is what went in *because* the rate is zero
    # -- and it is the mark's only way onto the amount itself (FR-004).
    released = money.also_resting_on(holding.cost, declaration.rate_provenance)
    events = (
        Event(
            sequence=1,
            occurred_on=holding.purchased_on,
            kind=EventKind.PURCHASE,
            amount=paid,
            owner_id=holding.owner_id,
            caused_by=CausationRef(
                kind=CausationKind.INSTRUMENT_TERM,
                id=f"{declaration.id}:open",
                detail=(
                    f"{holding.cost.amount!r} {holding.cost.currency.value} placed on the "
                    f"balance {declaration.name!r}, one unit per "
                    f"{holding.cost.currency.value}"
                ),
            ),
            lot_ref=LotRef(instrument_id=declaration.id, lot_id=_lot_id(holding)),
            quantity=holding.quantity,
            allocated_to=None,
            capacity_pool=None,
        ),
        Event(
            sequence=2,
            occurred_on=horizon.end,
            kind=EventKind.PRINCIPAL_REPAYMENT,
            amount=released,
            owner_id=holding.owner_id,
            caused_by=CausationRef(
                kind=CausationKind.INSTRUMENT_TERM,
                id=f"{declaration.id}:release",
                detail=(
                    f"the balance is released on {horizon.end.isoformat()}, the end of the "
                    f"comparison's horizon, at the {declaration.rate!r} rate it declares: "
                    "what comes back is what went in"
                ),
            ),
            lot_ref=LotRef(instrument_id=declaration.id, lot_id=None),
            quantity=holding.quantity,
            allocated_to=None,
            capacity_pool=None,
        ),
    )
    return CashProjection(
        instrument_id=declaration.id,
        ledger=engine.fold(
            events, base_currency=holding.cost.currency, consumption_method=SELECTION
        ),
        released=released,
        provenance=declaration.rate_provenance,
    )


def _lot_id(holding: Holding) -> str:
    """The identity of the lot the placement opens, on ``fund.lot_id_for``'s rule."""
    return f"{holding.instrument_id}@{holding.purchased_on.isoformat()}"


__all__ = ["CashProjection", "project_cash"]
