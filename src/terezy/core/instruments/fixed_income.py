"""``fixed_income``: the closed-form coupon and principal schedule of a bond, as events.

The arithmetic this whole feature exists to get right, and it is deliberately small
enough to check on paper. Every coupon is

    face_value x coupon_rate x year_fraction(previous accrual date, this accrual date)

multiplied by the units held, where the year fraction comes from the issue's **declared**
day-count convention and the coupon dates come from its **declared** periodicity. Nothing
here is fixed in the engine: a second issue with a different frequency and a different day
count is a data file and no code change (FR-021, SC-012), which is the property SC-003
exists to prove.

**Accrual is measured on unadjusted dates; only the payment date moves.** The declared
business-day rule is applied to the date money changes hands, not to the period interest
accrued over. Adjusting the accrual boundary as well would make every coupon depend on
where weekends fell, and two economically identical bonds would pay different amounts --
which is not what a fixed-coupon bond does. The consequence is visible in the D1 worked
example, where the final coupon of a Saturday maturity is paid on the Monday and is
nonetheless the ordinary 184-day amount.

**Gross amounts only.** No tax is netted here (that is a ``ChargeFn``'s job downstream)
and no route or access cost is applied (per Principle VI those belong to
``(instrument x income stream x route)``, never to the instrument alone).

**No cash deposit funds the purchase.** The cash balance goes negative on the purchase
date and recovers as coupons arrive, and that is the honest ledger for a feature whose
spec says "the purchase is taken as given". Inventing a funding deposit would require an
event caused by an owner action, and ``CausationKind`` has exactly two members --
instrument term and tax rule -- precisely so that no event can be attributed to a
vague third cause nobody tracked down.

**Deliberately absent rather than stubbed**: secondary-market sale before maturity, the
thin-market haircut that would apply to one, accrued interest settled at purchase,
restructuring, and pricing future purchases off a yield curve. Each is named in the spec
as a later feature, and a stub would invite a caller to depend on it.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from terezy.core.errors import (
    InconsistentTerms,
    InfeasiblePurchase,
    InstrumentFailure,
)
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.primitives import conventions, money
from terezy.core.primitives.money import Money

if TYPE_CHECKING:  # pragma: no cover -- import-time cycle avoidance
    from collections.abc import Mapping

    from terezy.core.instruments.interface import (
        Assumptions,
        BondTerms,
        DateRange,
        Holding,
        InstrumentConstraints,
        InstrumentDeclaration,
    )
    from terezy.core.tax.interface import TaxableEventKind

# The registry in ``terezy.core.instruments.registry`` imports this module to build its
# mapping, and the records above live beside that interface. Importing them only under
# ``TYPE_CHECKING`` keeps the reference where it is useful -- the type checker -- and out
# of the runtime import graph, where it would be a cycle. Nothing here constructs one of
# those records; this module reads declarations and produces events, which is why the
# type-only import is sufficient rather than a trick.


def lot_id_for(holding: Holding) -> str:
    """The identity of the lot a purchase opens: instrument and settlement date.

    Derived from the purchase rather than generated, because a generated id would need a
    counter or a clock and the core has neither -- and because two runs of the same
    scenario must produce the same lot ids or the determinism digest compares two
    different-looking results (C4).
    """
    return f"{holding.instrument_id}@{holding.purchased_on.isoformat()}"


def events(
    declaration: InstrumentDeclaration,
    holding: Holding,
    horizon: DateRange,
    _assumptions: Assumptions,
) -> tuple[Event, ...] | InstrumentFailure:
    """The purchase, every coupon and the redemption, as a sequenced event stream.

    ``_assumptions`` is named with a leading underscore because a *contractual* schedule
    assumes nothing beyond its declared terms: this function reads the bond's terms and
    the owner's purchase, and there is no third input that could change its answer. The
    parameter exists because the interface requires it, and FR-019's coupon policy will
    be the first thing to read it.

    Failure is typed and specific. Every guard below returns a value naming what
    conflicts with what, rather than raising or returning an empty tuple -- an empty
    tuple means "legitimately no events in this horizon", which is a different claim
    entirely.
    """
    problem = _check_feasible(declaration, holding, horizon)
    if problem is not None:
        return problem

    terms = declaration.terms
    adjust = conventions.business_day_rule(terms.business_day_rule)
    stream = [_purchase(declaration, holding, sequence=1)]
    stream.extend(_coupons(declaration, holding, start_sequence=2))
    stream.append(_redemption(declaration, holding, sequence=len(stream) + 1))

    final_payment = max(event.occurred_on for event in stream)
    if horizon.end < final_payment:
        return InconsistentTerms(
            first_term="horizon.end",
            second_term="instrument.maturity_date",
            reason=(
                f"the horizon ends {horizon.end.isoformat()} but the last payment of "
                f"{declaration.id!r} falls on {final_payment.isoformat()}"
                + (
                    f" (the declared maturity {terms.maturity_date.isoformat()} moved by "
                    f"the {terms.business_day_rule!r} rule)"
                    if adjust(terms.maturity_date) != terms.maturity_date
                    else ""
                )
                + ". This feature projects hold-to-maturity only, so it will not report "
                "a truncated schedule: the yield of a bond whose principal was cut off "
                "would be wrong rather than partial. Extend the horizon, or wait for the "
                "feature that values an open position at the horizon -- an implicit "
                "liquidation is not available, because nobody asked for one."
            ),
        )
    return tuple(stream)


def tax_classes(declaration: InstrumentDeclaration) -> Mapping[TaxableEventKind, str]:
    """Which declared class governs each kind of income this instrument produces.

    A projection of the declaration, and that is the point: the mapping is *declared*,
    so a new issue sharing an existing class is a data change. A function rather than a
    field access at the call site because a later instrument class may derive part of
    the mapping from its terms -- a fund whose distributions are taxed by what it holds
    -- and the interface should not have to change when one does.
    """
    return declaration.tax_classes


def constraints(declaration: InstrumentDeclaration) -> InstrumentConstraints:
    """The feasibility constraints a purchase of this instrument must satisfy."""
    return declaration.constraints


def _check_feasible(
    declaration: InstrumentDeclaration,
    holding: Holding,
    horizon: DateRange,
) -> InstrumentFailure | None:
    """Every reason this holding cannot be projected, in the order a reader would ask.

    Returns ``None`` when there is nothing wrong. ``None`` here is not a degraded outcome
    needing a reason of its own -- it is the absence of a failure, and the caller's next
    line is the schedule.

    Grouped into three checks by subject -- the instrument's own terms, the purchase, the
    horizon -- and the **first** problem found is the one reported. Reporting only one is
    deliberate: a reader fixing a purchase below the minimum ticket does not need to be
    told simultaneously that their horizon is short, and a list of failures invites a
    caller to handle "the first one" anyway.
    """
    for problem in (
        _terms_problem(declaration),
        _purchase_problem(declaration, holding),
        _horizon_problem(holding, horizon),
    ):
        if problem is not None:
            return problem
    return None


def _terms_problem(declaration: InstrumentDeclaration) -> InstrumentFailure | None:
    """Whether the instrument's own declared terms can hold at all."""
    terms = declaration.terms
    if terms.maturity_date <= terms.issue_date:
        return InconsistentTerms(
            first_term="instrument.maturity_date",
            second_term="instrument.issue_date",
            reason=(
                f"{declaration.id!r} matures {terms.maturity_date.isoformat()}, on or "
                f"before its issue date {terms.issue_date.isoformat()}. No schedule "
                "exists for such an instrument, and a zero-length schedule would be a "
                "different and false claim -- it would report a holding that pays "
                "nothing."
            ),
        )
    return None


def _purchase_problem(
    declaration: InstrumentDeclaration,
    holding: Holding,
) -> InstrumentFailure | None:
    """Whether this purchase of that instrument is possible and permitted.

    The minimum ticket is checked last of the five, because the other four describe a
    purchase that is not a purchase at all -- no units, no money, or a date outside the
    instrument's life -- and reporting a shortfall against a ticket would be answering a
    question the caller has not yet managed to ask.
    """
    terms = declaration.terms
    if holding.quantity <= 0.0:
        return InconsistentTerms(
            first_term="holding.quantity",
            second_term="instrument.min_unit",
            reason=(
                f"a purchase of {holding.quantity!r} units of {declaration.id!r} "
                "acquires nothing. A holding must acquire a positive number of units; "
                "the quantity is rejected rather than rounded up to the minimum unit, "
                "because rounding it would spend money nobody agreed to spend."
            ),
        )
    if holding.cost.amount <= 0.0:
        return InconsistentTerms(
            first_term="holding.cost",
            second_term="holding.quantity",
            reason=(
                f"{holding.quantity!r} units of {declaration.id!r} were acquired for "
                f"{holding.cost.amount!r} {holding.cost.currency.value}. A purchase that "
                "costs nothing has no basis, so every figure derived from it -- the "
                "yield above all -- would be meaningless rather than merely large."
            ),
        )
    if holding.purchased_on < terms.issue_date:
        return InconsistentTerms(
            first_term="holding.purchased_on",
            second_term="instrument.issue_date",
            reason=(
                f"{declaration.id!r} was bought {holding.purchased_on.isoformat()}, "
                f"before it was issued on {terms.issue_date.isoformat()}"
            ),
        )
    if holding.purchased_on >= terms.maturity_date:
        return InconsistentTerms(
            first_term="holding.purchased_on",
            second_term="instrument.maturity_date",
            reason=(
                f"{declaration.id!r} was bought {holding.purchased_on.isoformat()}, on "
                f"or after it matures on {terms.maturity_date.isoformat()}. There is "
                "nothing left to hold."
            ),
        )
    minimum = declaration.constraints.min_ticket
    if money.compare(holding.cost, minimum) < 0:
        return InfeasiblePurchase(
            constraint="min_ticket",
            required=minimum,
            actual=holding.cost,
            shortfall=money.sub(minimum, holding.cost),
            reason=(
                f"{declaration.id!r} requires at least {minimum.amount!r} "
                f"{minimum.currency.value} per purchase; {holding.cost.amount!r} was "
                f"offered, which is {money.sub(minimum, holding.cost).amount!r} short. "
                "The amount is reported as it stands and is not adjusted to fit: "
                "rounding it up would spend money the owner did not agree to spend, and "
                "rounding it down would report a return on a holding that was never "
                "bought."
            ),
        )
    return None


def _horizon_problem(holding: Holding, horizon: DateRange) -> InstrumentFailure | None:
    """Whether the window asked about can contain the purchase at all.

    Whether it also reaches the final payment is checked in :func:`events`, once the
    adjusted payment dates are known -- a business-day rule can move the last flow past a
    horizon that looked long enough against the unadjusted maturity.
    """
    if horizon.end < horizon.start:
        return InconsistentTerms(
            first_term="horizon.start",
            second_term="horizon.end",
            reason=(
                f"the horizon runs backwards: it starts {horizon.start.isoformat()} and "
                f"ends {horizon.end.isoformat()}"
            ),
        )
    if horizon.start > holding.purchased_on:
        return InconsistentTerms(
            first_term="horizon.start",
            second_term="holding.purchased_on",
            reason=(
                f"the horizon starts {horizon.start.isoformat()}, after the purchase on "
                f"{holding.purchased_on.isoformat()}. The purchase is the origin of every "
                "time measurement in the result, so a horizon that excludes it would "
                "measure returns from a date on which nothing was bought."
            ),
        )
    return None


def _purchase(
    declaration: InstrumentDeclaration,
    holding: Holding,
    *,
    sequence: int,
) -> Event:
    """Cash out, one lot in, at the cost the owner stated.

    The cause is recorded as an instrument term rather than an owner action because
    ``CausationKind`` has exactly two members by design (see ``ledger.events``): the term
    named is the declared instrument the purchase acquired, which is the fact a reader
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
    )


def _coupons(
    declaration: InstrumentDeclaration,
    holding: Holding,
    *,
    start_sequence: int,
) -> tuple[Event, ...]:
    """One event per coupon dated after the purchase, in ascending payment order.

    Coupons dated on or before the purchase date were paid to whoever held the bond
    then, so they are not this holding's income. The coupon straddling the purchase is
    nonetheless paid to this holder **in full**: accrued interest settled at purchase is
    a secondary-market mechanic this feature does not model, and apportioning the coupon
    without modelling the settlement that pays for it would invent a cash flow.

    Payment dates keep their ascending order after adjustment because consecutive coupon
    dates are whole months apart and every implemented business-day rule moves a date by
    at most a few days -- so the stream cannot fold out of order.
    """
    terms = declaration.terms
    if terms.coupon_rate == 0.0:
        # A zero-coupon bond, which is a valid declaration and not a missing rate. It
        # pays its principal and nothing else, and emitting a stream of zero-amount
        # coupon events would clutter every schedule with rows that never paid.
        return ()

    year_fraction = conventions.day_count(terms.day_count)
    adjust = conventions.business_day_rule(terms.business_day_rule)
    schedule = conventions.periodicity(terms.periodicity)(terms.issue_date, terms.maturity_date)

    emitted: list[Event] = []
    accrual_start = terms.issue_date
    for accrual_end in schedule:
        if accrual_end > holding.purchased_on:
            emitted.append(
                _coupon(
                    declaration,
                    holding,
                    sequence=start_sequence + len(emitted),
                    accrual_start=accrual_start,
                    accrual_end=accrual_end,
                    paid_on=adjust(accrual_end),
                    fraction=year_fraction(accrual_start, accrual_end),
                )
            )
        accrual_start = accrual_end
    return tuple(emitted)


def _coupon(
    declaration: InstrumentDeclaration,
    holding: Holding,
    *,
    sequence: int,
    accrual_start: date,
    accrual_end: date,
    paid_on: date,
    fraction: float,
) -> Event:
    """One coupon: face x rate x year fraction x units, resting on the declared terms."""
    terms = declaration.terms
    return Event(
        sequence=sequence,
        occurred_on=paid_on,
        kind=EventKind.COUPON,
        amount=_coupon_amount(terms, holding.quantity, fraction),
        owner_id=holding.owner_id,
        caused_by=CausationRef(
            kind=CausationKind.INSTRUMENT_TERM,
            id=f"{declaration.id}:coupon_rate",
            detail=(
                f"coupon at {terms.coupon_rate!r} per annum accrued "
                f"{accrual_start.isoformat()} to {accrual_end.isoformat()} on "
                f"{terms.day_count!r}, paid {paid_on.isoformat()} under the "
                f"{terms.business_day_rule!r} rule"
            ),
        ),
        lot_ref=None,
        quantity=None,
        allocated_to=None,
    )


def _coupon_amount(terms: BondTerms, quantity: float, fraction: float) -> Money:
    """``face x rate x fraction x units``, carrying the terms it was computed from.

    Through ``money.scale_sourced`` rather than ``money.scale``, because the rate and the
    day-count fraction are *declared* values: the factor has sources of its own, and
    ``scale`` would carry only the face value's. The two usually coincide -- a file
    declares face and coupon in one table -- and relying on that coincidence is how a
    mark gets lost the day they are separated.
    """
    return money.scale_sourced(
        terms.face_value,
        terms.coupon_rate * fraction * quantity,
        terms.provenance,
    )


def _redemption(
    declaration: InstrumentDeclaration,
    holding: Holding,
    *,
    sequence: int,
) -> Event:
    """The principal at maturity: cash in, units surrendered.

    Redemption is a **disposal**, not a cash receipt. It consumes basis and realises a
    gain or a loss, which is why it carries a quantity and closes lots -- and why the
    disposal-gain tax class has something to be applied to even for a bond redeemed at
    par, where that gain is exactly zero. Treating it as cash-only would make the gain
    unassertable and the tax on it invisible.

    The lot is deliberately **not** named: which lots a disposal consumes is decided by
    the configured consumption method, and an event that named one would be asking for
    specific-lot selection, which the ledger refuses loudly rather than ignoring.
    """
    terms = declaration.terms
    paid_on = conventions.business_day_rule(terms.business_day_rule)(terms.maturity_date)
    return Event(
        sequence=sequence,
        occurred_on=paid_on,
        kind=EventKind.PRINCIPAL_REPAYMENT,
        amount=money.scale_sourced(terms.face_value, holding.quantity, terms.provenance),
        owner_id=holding.owner_id,
        caused_by=CausationRef(
            kind=CausationKind.INSTRUMENT_TERM,
            id=f"{declaration.id}:maturity_date",
            detail=(
                f"redemption of {holding.quantity!r} units at face value on "
                f"{terms.maturity_date.isoformat()}, paid {paid_on.isoformat()} under "
                f"the {terms.business_day_rule!r} rule"
            ),
        ),
        lot_ref=LotRef(instrument_id=declaration.id, lot_id=None),
        quantity=holding.quantity,
        allocated_to=None,
    )
