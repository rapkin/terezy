"""How much of a holding one declared repayment of principal surrenders.

A repayment retires **its share of the repayments this holding receives**, so the stream as
a whole retires the holding as a whole -- whatever the schedule's shape, and wherever in the
schedule the purchase falls.

⚙ **The second half of that is a defect this file did not catch and now does.** The rule was
first written as a share of every repayment the *declaration* lists, which is a different set
the moment a repayment falls before the purchase: the emitted repayments then retire strictly
less than the holding, stranding basis in a position that never closes and reporting the
stranded basis as a realised gain on a break-even trade. Every case below used to vary only
the *split*, with every repayment after the purchase, so the property passed for a narrower
reason than the one it stated.

⚙ **Its share of the repayments, not its share of the face value**, and the difference is a
bond redeemed above par. A schedule returning 1 050.00 against a declared face of 1 000.00
repays the whole of each unit and realises a gain of 50.00; measured against face it would
retire 1.05 units of every 1 held, which is not a bond -- it is arithmetic run past the
thing it was describing, and the ledger would refuse the disposal. Face value is what a
redemption is compared *with* (FR-025), never what it is divided by.

Three shapes, and the first is the one the whole comparison with the generative form rests
on: one repayment at face must retire exactly what the generative redemption retires, or
SC-002 is comparing two different trades.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from terezy.core.errors import InconsistentTerms
from terezy.core.instruments import registry
from terezy.core.instruments.interface import PaymentKind, ScheduledPayment
from terezy.core.ledger.events import Event, EventKind
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from tests.unit.test_enumerated_refusals import HOLD_CASH
from tests.worked_examples.test_enumerated_schedule import (
    DECLARATION,
    FIXTURE,
    HOLDING,
    HORIZON,
    QUANTITY,
    TERMS,
    UAH,
)


def _repayments(*amounts: float, on: tuple[date, ...] | None = None) -> tuple[Event, ...]:
    """The declaration's three coupons, with its repayments replaced by ``amounts``.

    Each replacement falls on the schedule's last date unless ``on`` says otherwise, so a
    caller varies the split alone or the split and the dates together.
    """
    coupons = tuple(p for p in TERMS.payments if p.pays is PaymentKind.COUPON)
    last = max(p.on for p in TERMS.payments)
    dates = on or (last,) * len(amounts)
    principal = tuple(
        ScheduledPayment(
            on=when, amount=Money(amount, UAH, FIXTURE), pays=PaymentKind.PRINCIPAL_REPAYMENT
        )
        for amount, when in zip(amounts, dates, strict=True)
    )
    payments = tuple(sorted(coupons + principal, key=lambda p: (p.on, p.pays.value)))
    produced = registry.ops_for(DECLARATION.instrument_class).events(
        replace(DECLARATION, terms=replace(TERMS, payments=payments)),
        HOLDING,
        HORIZON,
        HOLD_CASH,
        None,
    )
    assert isinstance(produced, tuple), produced
    return produced


def _retired(events: tuple[Event, ...]) -> list[float]:
    return [
        event.quantity
        for event in events
        if event.kind is EventKind.PRINCIPAL_REPAYMENT and event.quantity is not None
    ]


def test_one_repayment_at_face_retires_the_whole_holding() -> None:
    """What the generative form's redemption does, reached by a different route."""
    assert _retired(_repayments(1000.0)) == [QUANTITY]


def test_one_repayment_above_par_also_retires_the_whole_holding() -> None:
    """And realises a gain of the difference, rather than surrendering units nobody holds."""
    assert _retired(_repayments(1050.0)) == [QUANTITY]


def test_one_repayment_below_par_also_retires_the_whole_holding() -> None:
    """The mirror: a bond redeemed at 95 returns less, and the holding still closes."""
    assert _retired(_repayments(950.0)) == [QUANTITY]


def test_an_amortising_schedule_retires_a_share_at_a_time() -> None:
    retired = _retired(_repayments(400.0, 600.0))
    assert [is_close(part, share) for part, share in zip(retired, (4.0, 6.0), strict=True)] == [
        True,
        True,
    ]


def test_the_repayments_together_always_retire_exactly_the_holding() -> None:
    """The property the shape rests on: whatever the split, the position closes. A rule
    that could over-retire would meet `ledger.lots.consume`, which raises."""
    for amounts in ((1000.0,), (1050.0,), (400.0, 600.0), (333.0, 333.0, 334.0)):
        assert is_close(sum(_retired(_repayments(*amounts))), QUANTITY), amounts


def test_a_repayment_before_the_purchase_does_not_shrink_what_the_later_ones_retire() -> None:
    """The defect the header names. An amortising schedule that repaid half its principal
    before this buyer arrived sells units of what **remains**, so the remaining repayment
    retires the whole of what was bought -- not half of it.

    Measured on the position rather than on the event, because the symptom is a holding that
    never closes: the quantity is what the ledger would be left holding."""
    before, after = date(2026, 1, 20), date(2027, 7, 15)
    assert before < HOLDING.purchased_on < after
    retired = _retired(_repayments(500.0, 500.0, on=(before, after)))
    assert retired == [QUANTITY], (
        "the repayment this holding receives must retire all of it; measured against every "
        "repayment the paper ever made it would retire half, and the other half of the "
        "basis would be reported as a realised gain on a trade that broke even"
    )


def test_a_purchase_after_every_repayment_refuses_rather_than_never_closing() -> None:
    """The other side of the same fact. A buyer who arrives after the last repayment of
    principal holds a position nothing closes, so there is no honest yield to report --
    and the division that sizes a retirement would have nothing to divide by."""
    coupons_only = replace(
        TERMS,
        payments=tuple(
            replace(payment, on=date(2026, 1, 20))
            if payment.pays is PaymentKind.PRINCIPAL_REPAYMENT
            else payment
            for payment in TERMS.payments
        ),
    )
    outcome = registry.ops_for(DECLARATION.instrument_class).events(
        replace(DECLARATION, terms=coupons_only), HOLDING, HORIZON, HOLD_CASH, None
    )
    assert isinstance(outcome, InconsistentTerms), outcome
    assert "repayment of principal" in outcome.reason


def test_a_purchase_after_every_payment_refuses_rather_than_projecting_nothing() -> None:
    """An empty stream would look like a legitimate 'no events in this horizon', which is a
    different claim entirely."""
    last = max(payment.on for payment in TERMS.payments)
    outcome = registry.ops_for(DECLARATION.instrument_class).events(
        DECLARATION,
        replace(HOLDING, purchased_on=last),
        replace(HORIZON, start=last),
        HOLD_CASH,
        None,
    )
    assert isinstance(outcome, InconsistentTerms), outcome
    assert "receives nothing" in outcome.reason


def test_a_coupon_surrenders_nothing() -> None:
    coupons = [event.quantity for event in _repayments(1000.0) if event.kind is EventKind.COUPON]
    assert coupons == [None, None, None]


def test_the_dates_are_the_declared_ones_and_nothing_moves_them() -> None:
    dates = [event.occurred_on for event in _repayments(400.0, 600.0)]
    assert dates == sorted(dates)
    assert max(dates) == date(2027, 7, 15)
