"""Opening a lot: the one event every instrument class that pays a schedule begins with.

Shared rather than written twice, because a purchase is not a term of either declaration
form -- the two bond forms open a lot the same way, and this is where they do it.

**A fund keeps its own** (`core.instruments.fund`), byte-identical today, and that is a
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

from terezy.core.errors import InconsistentTerms
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.primitives import money
from terezy.core.scenarios import early_exit

if TYPE_CHECKING:  # pragma: no cover -- the records live beside the interface
    from collections.abc import Iterable
    from datetime import date

    from terezy.core.instruments.interface import EarlyExit, Holding, InstrumentDeclaration
    from terezy.core.primitives.money import Money


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


def early_sale(
    declaration: InstrumentDeclaration,
    holding: Holding,
    quantity: float,
    *,
    on: date,
    exit_: EarlyExit,
    coupons: Iterable[tuple[date, Money]],
    sequence: int,
) -> Event | InconsistentTerms:
    """Cash in, units out, at the carried-forward resale price, on the horizon's last day.

    015 FR-029. A **disposal**, like a redemption at maturity and unlike a cash receipt: it
    consumes basis and realises a gain or a loss, and the loss is what a spread *is*. Reporting
    it as cash would make the cost of the early exit invisible in the ledger.

    ``coupons`` is this instrument's whole per-unit coupon schedule, dates and amounts, and it
    is a **required** argument rather than an adjustment a caller may apply first: the sale
    price is the quotation net of what detached from it while the holding held it
    (:func:`early_exit.detached_since`), and a caller that forgot would credit a coupon and sell
    at a price that still contained it.

    ``EventKind.REDEMPTION`` rather than ``PRINCIPAL_REPAYMENT``, on the reasoning that kind's
    own docstring already gives for a fund buyback: nothing is repaying principal here, the
    price is somebody's quote, and the amount can be less than what was put in.

    The cause is the **access** declaration, because that is where the price is declared. An
    instrument term would be a traceable figure pointing at the wrong file, which
    ``CausationKind`` names as worse than a widened set.

    ``quantity`` is passed rather than read off the holding, for the reason a redemption's is:
    under a reinvesting policy the units sold are the purchase plus every reinvestment.

    **A quotation worth less than the coupons still inside it refuses**, in the words below.
    Unreachable on the shipped registry, where the smallest quote is three figures against
    coupons of tens, and reached deliberately in the worked examples rather than asserted here.
    """
    detached = early_exit.detached_since(
        observed_on=exit_.observed_on,
        held_from=holding.purchased_on,
        sold_on=on,
        coupons=coupons,
        currency=exit_.price_per_unit.currency,
    )
    price = money.sub(exit_.price_per_unit, detached)
    if price.amount <= 0.0:
        return InconsistentTerms(
            first_term="access.resale_price.per_unit",
            second_term="instrument.schedule.payment",
            reason=(
                f"{declaration.id!r} quotes {exit_.price_per_unit.amount!r} "
                f"{exit_.price_per_unit.currency.value} per unit as of "
                f"{exit_.observed_on.isoformat()}, and {detached.amount!r} of coupon detaches "
                f"from it before the sale on {on.isoformat()}. A quotation cannot hold less "
                "than the coupons it still contains: the two declarations describe different "
                "paper, and striking the sale would post a disposal of a negative amount."
            ),
        )
    return Event(
        sequence=sequence,
        occurred_on=on,
        kind=EventKind.REDEMPTION,
        amount=money.scale_sourced(price, quantity, price.provenance),
        owner_id=holding.owner_id,
        caused_by=CausationRef(
            kind=CausationKind.ACCESS_TERM,
            id=f"{declaration.id}:resale_price",
            detail=(
                f"sale of {quantity!r} units at {price.amount!r} {price.currency.value} on "
                f"{on.isoformat()}, the last day of the horizon: the resale quotation declared "
                f"as of {exit_.observed_on.isoformat()}, less the {detached.amount!r} per "
                f"unit that detached from it while the holding held it, under the assumption "
                f"{exit_.assumption.id!r}"
            ),
        ),
        lot_ref=LotRef(instrument_id=declaration.id, lot_id=None),
        quantity=quantity,
        allocated_to=None,
        capacity_pool=None,
    )
