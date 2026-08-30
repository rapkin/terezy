"""``enumerated_schedule``: the payments a declaration lists, as events.

There is no arithmetic here to get right, and that is the point. Every amount is
``declared amount per unit x units held`` and every date is the date the declaration
states. Nothing is generated, nothing is adjusted, and the declared **day count sizes
nothing** -- it exists so that a span of days can be turned into a fraction of a year when
a yield is annualised, and it reaches no amount, no date and no rate in this module
(FR-003b).

**What this form refuses, and why each refusal is a value rather than a number.**

*A purchase before the schedule's coverage start* (FR-014). The declaration claims to list
every payment from that date onwards and says nothing about what came before it, so a buyer
dated earlier is a buyer this schedule cannot describe. The date is not moved and no
projection runs: a figure computed on a truncated schedule is wrong rather than partial.

*A reinvesting coupon policy* (FR-015). Reinvestment needs the price at which a coupon buys
further units, and there is none to be had. The face value is **not** substituted: for a
bond declared by its terms, face is the price at which a unit earns the issue's declared
rate, and a declaration that states no rate has no such price -- face is a redemption amount
and nothing else.

*A horizon ending before the last payment.* A truncated schedule's yield is wrong rather
than partial, and an implicit liquidation at the horizon would be a cash flow nobody
declared.

**Both kinds of payment on one date are two payments** -- the ordinary way a bond ends.
They are taxed under different declared classes, so summing them would tax the result under
whichever class won.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from terezy.core.errors import InconsistentTerms, InfeasiblePurchase, InstrumentFailure
from terezy.core.instruments import acquire, fixed_income
from terezy.core.instruments import terms as terms_of
from terezy.core.instruments.interface import (
    PAYMENT_KINDS,
    EnumeratedTerms,
    PaymentKind,
    ScheduledPayment,
)
from terezy.core.ledger.events import CausationKind, CausationRef, Event, LotRef
from terezy.core.primitives import money

if TYPE_CHECKING:  # pragma: no cover -- import-time cycle avoidance
    from terezy.core.instruments.interface import (
        Assumptions,
        DateRange,
        Holding,
        InstrumentConstraints,
        InstrumentDeclaration,
    )
    from terezy.core.tax.interface import TaxableEventKind


def events(
    declaration: InstrumentDeclaration,
    holding: Holding,
    horizon: DateRange,
    assumptions: Assumptions,
) -> tuple[Event, ...] | InstrumentFailure:
    """The purchase and every declared payment falling after it, scaled by units held.

    Payments dated on or before the purchase went to whoever held the paper then, exactly
    as a coupon does under the generative form. There is no accrued-interest apportionment
    of the payment straddling the purchase, and there could not be: the two facts it needs
    -- the start of the accrual period and the basis interest accrues on within it -- are
    not declared and may not be inferred (FR-017).
    """
    terms = terms_of.narrowed(declaration, EnumeratedTerms)
    receivable = terms_of.payments_after(terms.payments, holding.purchased_on)
    problem = _check_feasible(
        declaration, terms, receivable, holding=holding, horizon=horizon, assumptions=assumptions
    )
    if problem is not None:
        return problem

    principal = terms_of.principal_returned(terms, bought_on=holding.purchased_on)
    stream = [acquire.purchase(declaration, holding, sequence=1)]
    for payment in receivable:
        stream.append(
            _payment(
                declaration,
                holding,
                payment,
                principal=principal.amount,
                sequence=len(stream) + 1,
            )
        )
    return tuple(stream)


def tax_classes(declaration: InstrumentDeclaration) -> Mapping[TaxableEventKind, str]:
    """Which declared class governs each kind of income this instrument produces."""
    return declaration.tax_classes


def constraints(declaration: InstrumentDeclaration) -> InstrumentConstraints:
    """The feasibility constraints a purchase of this instrument must satisfy."""
    return declaration.constraints


def _check_feasible(
    declaration: InstrumentDeclaration,
    terms: EnumeratedTerms,
    receivable: tuple[ScheduledPayment, ...],
    *,
    holding: Holding,
    horizon: DateRange,
    assumptions: Assumptions,
) -> InstrumentFailure | None:
    """Every reason this holding cannot be projected, in the order a reader would ask.

    ``None`` is the absence of a failure rather than a degraded outcome needing a reason of
    its own. The **first** problem found is the one reported, on the generative form's
    reading: a reader fixing a purchase below the minimum ticket does not need to be told
    simultaneously that their horizon is short.

    **Written as early returns rather than as a tuple of results, and the difference is
    not style.** A tuple evaluates every check before the first is read, and the horizon
    check reads the *last date this holding receives* -- which does not exist when the
    receivable check is the one that should have fired. Ordering guards by which answers a
    reader wants first only works if the later ones do not run.
    """
    problem = _purchase_problem(declaration, terms, holding)
    if problem is not None:
        return problem
    problem = _policy_problem(declaration, assumptions)
    if problem is not None:
        return problem
    problem = _receivable_problem(declaration, terms, receivable, holding)
    if problem is not None:
        return problem
    return _horizon_problem(declaration, receivable, holding, horizon)


def _purchase_problem(
    declaration: InstrumentDeclaration,
    terms: EnumeratedTerms,
    holding: Holding,
) -> InstrumentFailure | None:
    """Whether this purchase of that instrument is possible and permitted."""
    if holding.quantity <= 0.0:
        return InconsistentTerms(
            first_term="holding.quantity",
            second_term="instrument.constraints.min_unit",
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
    if holding.purchased_on < terms.covers_from:
        return InconsistentTerms(
            first_term="holding.purchased_on",
            second_term="instrument.schedule.covers_from",
            reason=(
                f"{declaration.id!r} was bought {holding.purchased_on.isoformat()}, before "
                f"its schedule claims to be complete from {terms.covers_from.isoformat()}. "
                "The declaration says nothing about what this instrument paid before that "
                "date, so it cannot state what a buyer on the earlier date receives. The "
                "purchase is not re-dated to the coverage start: that would answer a "
                "different question and report the answer as this one."
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
                "The amount is reported as it stands and is not adjusted to fit."
            ),
        )
    return None


def _policy_problem(
    declaration: InstrumentDeclaration,
    assumptions: Assumptions,
) -> InstrumentFailure | None:
    """Whether the declared coupon policy is one this form can carry out (FR-015)."""
    # Validates the declared name against the closed set of policies; an unrecognised one
    # raises naming the known ones, exactly as it does for a bond declared by its terms.
    fixed_income.coupon_policy(assumptions.coupon_policy)
    if assumptions.coupon_policy != fixed_income.REINVEST:
        return None
    return InconsistentTerms(
        first_term="assumptions.coupon_policy",
        second_term="instrument.schedule",
        reason=(
            f"the {fixed_income.REINVEST!r} policy buys further units with each coupon, and "
            f"{declaration.id!r} declares no price at which a coupon could buy one. The "
            "face value is not substituted for it: for a bond declared by its terms, face "
            "is the price at which a unit earns the issue's declared rate, and this "
            "declaration states no rate -- so its face value is a redemption amount and "
            f"nothing else. Project it under {fixed_income.HOLD_CASH!r}, or declare the "
            "instrument's terms in the form that states a rate."
        ),
    )


def _horizon_problem(
    declaration: InstrumentDeclaration,
    receivable: tuple[ScheduledPayment, ...],
    holding: Holding,
    horizon: DateRange,
) -> InstrumentFailure | None:
    """Whether the window asked about contains the purchase and reaches the last payment."""
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
    last = max(payment.on for payment in receivable)
    if horizon.end < last:
        return InconsistentTerms(
            first_term="horizon.end",
            second_term="instrument.schedule.payment",
            reason=(
                f"the horizon ends {horizon.end.isoformat()} but the last payment this "
                f"holding of {declaration.id!r} receives falls on {last.isoformat()}. A truncated "
                "schedule is not reported: the yield of a holding whose principal was cut "
                "off would be wrong rather than partial, and an implicit liquidation at "
                "the horizon would be a cash flow nobody declared."
            ),
        )
    return None


def _receivable_problem(
    declaration: InstrumentDeclaration,
    terms: EnumeratedTerms,
    receivable: tuple[ScheduledPayment, ...],
    holding: Holding,
) -> InstrumentFailure | None:
    """Whether this purchase receives anything, and whether what it receives closes it.

    Both are facts about *this purchase against this schedule* rather than about either
    alone, which is why they are typed refusals here rather than load failures: the same
    declaration is perfectly good for a buyer who bought earlier.

    They also stand where a bare arithmetic error would otherwise reach the caller -- a
    ``max()`` over nothing and a division by nothing. An uncontextualised ``ValueError``
    tells a reader that this engine broke; a refusal tells them which two declared facts
    cannot both hold.
    """
    if not receivable:
        return InconsistentTerms(
            first_term="holding.purchased_on",
            second_term="instrument.schedule.payment",
            reason=(
                f"{declaration.id!r} was bought {holding.purchased_on.isoformat()}, on or "
                "after every payment its schedule declares. The purchase receives nothing, "
                "so there is no holding to project -- and no yield, because there is no "
                "series. The payments before that date went to whoever held the paper then."
            ),
        )
    if terms_of.principal_returned(terms, bought_on=holding.purchased_on).amount > 0.0:
        return None
    return InconsistentTerms(
        first_term="holding.purchased_on",
        second_term="instrument.schedule.payment",
        reason=(
            f"{declaration.id!r} was bought {holding.purchased_on.isoformat()}, after every "
            "repayment of principal its schedule declares. What is left is coupons on a "
            "position nothing ever closes, so the basis would never be recovered and the "
            "yield would be computed on a holding still open at the end of its own "
            f"schedule. The declaration lists {len(terms.payments)} payment(s) in all."
        ),
    )


def _units_retired(payment: ScheduledPayment, *, principal: float, quantity: float) -> float:
    """How many units one payment surrenders: its share of the repayments **this holding
    receives**.

    Zero for a coupon, which surrenders nothing. For a repayment of principal it is
    ``quantity x amount / principal``, where ``principal`` is what the receivable repayments
    return per unit -- so the stream as a whole retires the holding as a whole, whatever the
    schedule's shape and wherever in it the purchase falls. One repayment retires everything,
    which is exactly what the generative form's redemption does; two equal ones retire half
    each.

    **Its share of the repayments, not its share of the face value**, and the difference
    is a bond redeemed above par. A schedule returning 1 050.00 against a declared face of
    1 000.00 repays the whole of each unit and realises a gain; measured against face it
    would retire 1.05 units of every 1 held, which is not a bond -- it is arithmetic run
    past the thing it was describing.

    The denominator comes from `terms.principal_returned`, in one call, so that what a
    repayment is divided by and what a **purchase** is compared with cannot disagree.

    **Arithmetic over declared amounts, not an inference.** It reads no position in the
    list and no relative size: a repayment is a repayment because the declaration says so
    (FR-008), and how much of a unit it retires follows from figures that are on the page.
    """
    if payment.pays is not PaymentKind.PRINCIPAL_REPAYMENT:
        return 0.0
    return quantity * payment.amount.amount / principal


def _payment(
    declaration: InstrumentDeclaration,
    holding: Holding,
    payment: ScheduledPayment,
    *,
    principal: float,
    sequence: int,
) -> Event:
    """One declared payment, scaled by the units held, as the movement its kind names.

    The amount goes through ``money.scale`` rather than being rebuilt, so the payment's own
    sources reach the event and every figure downstream of it.

    A principal repayment carries the units it surrenders and closes lots; a coupon carries
    neither. Which of the two this is comes from the declared label and from nothing else.
    The lot is deliberately **not** named, because naming one would be asking for specific-lot
    selection rather than for the configured consumption method.
    """
    kind, _ = PAYMENT_KINDS[payment.pays]
    retired = _units_retired(payment, principal=principal, quantity=holding.quantity)
    disposal = payment.pays is PaymentKind.PRINCIPAL_REPAYMENT
    return Event(
        sequence=sequence,
        occurred_on=payment.on,
        kind=kind,
        amount=money.scale(payment.amount, holding.quantity),
        owner_id=holding.owner_id,
        caused_by=CausationRef(
            kind=CausationKind.INSTRUMENT_TERM,
            id=f"{declaration.id}:{payment.pays.value}",
            detail=(
                f"declared {payment.pays.value.replace('_', ' ')} of "
                f"{payment.amount.amount!r} {payment.amount.currency.value} per unit on "
                f"{payment.on.isoformat()}, on {holding.quantity!r} unit(s)"
            ),
        ),
        lot_ref=LotRef(instrument_id=declaration.id, lot_id=None) if disposal else None,
        quantity=retired if disposal else None,
        allocated_to=None,
        capacity_pool=None,
    )
