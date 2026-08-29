"""Opening a lot: the one event every instrument class that pays a schedule begins with.

Shared rather than written twice, because a purchase is not a term of either declaration
form -- the two bond forms open a lot the same way, and this is where they do it.

⚙ **A fund keeps its own** (`core.instruments.fund`), byte-identical today, and that is a
recorded duplicate rather than an oversight: a fund purchase is priced from its declared NAV
plus an entry markup, so what it will need from a shared helper is not yet what these two
need. Unifying all three is a decision about the fund's shape and belongs to whoever changes
it (noted 2026-08-30).

What the owner paid, on what date, for how many units of what is the same fact
whether the paper's terms were declared in closed form or as a list of payments — and the
lot id it derives is what a later disposal consumes, so two implementations that drifted
would open two lots nothing could reconcile.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.primitives import money

if TYPE_CHECKING:  # pragma: no cover -- the records live beside the interface
    from terezy.core.instruments.interface import Holding, InstrumentDeclaration


def lot_id_for(holding: Holding) -> str:
    """The identity of the lot a purchase opens: instrument and settlement date.

    Derived from the purchase rather than generated, because a generated id would need a
    counter or a clock and the core has neither -- and because two runs of the same
    scenario must produce the same lot ids or the determinism digest compares two
    different-looking results (C4).
    """
    return f"{holding.instrument_id}@{holding.purchased_on.isoformat()}"


def purchase(declaration: InstrumentDeclaration, holding: Holding, *, sequence: int) -> Event:
    """Cash out, one lot in, at the cost the owner stated.

    The cause is recorded as an instrument term rather than an owner action because
    ``CausationKind`` admits no owner-action member by design (see ``ledger.events``): the
    term named is the declared instrument the purchase acquired, which is the fact a reader
    following the audit trail actually wants.
    """
    return Event(
        sequence=sequence,
        occurred_on=holding.purchased_on,
        kind=EventKind.PURCHASE,
        amount=money.scale(holding.cost, -1.0),
        owner_id=holding.owner_id,
        caused_by=CausationRef(
            kind=CausationKind.INSTRUMENT_TERM,
            id=f"{declaration.id}:purchase",
            detail=(
                f"purchase of {holding.quantity!r} units of {declaration.name!r} at the stated cost"
            ),
        ),
        lot_ref=LotRef(instrument_id=declaration.id, lot_id=lot_id_for(holding)),
        quantity=holding.quantity,
        allocated_to=None,
        capacity_pool=None,
    )
