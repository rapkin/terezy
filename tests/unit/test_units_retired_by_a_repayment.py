"""How much of a holding one declared repayment of principal surrenders.

A repayment retires **its share of the repayments the schedule declares**, so the stream as
a whole retires the holding as a whole -- once, whatever the schedule's shape.

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


def _repayments(*amounts: float) -> tuple[Event, ...]:
    """The declaration's three coupons, with its repayments replaced by ``amounts``.

    Every replacement falls on the schedule's last date, so only the split changes.
    """
    coupons = tuple(p for p in TERMS.payments if p.pays is PaymentKind.COUPON)
    last = max(p.on for p in TERMS.payments)
    principal = tuple(
        ScheduledPayment(
            on=last, amount=Money(amount, UAH, FIXTURE), pays=PaymentKind.PRINCIPAL_REPAYMENT
        )
        for amount in amounts
    )
    terms = replace(TERMS, payments=coupons + principal)
    produced = registry.ops_for(DECLARATION.instrument_class).events(
        replace(DECLARATION, terms=terms), HOLDING, HORIZON, HOLD_CASH
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


def test_a_coupon_surrenders_nothing() -> None:
    coupons = [event.quantity for event in _repayments(1000.0) if event.kind is EventKind.COUPON]
    assert coupons == [None, None, None]


def test_the_dates_are_the_declared_ones_and_nothing_moves_them() -> None:
    dates = [event.occurred_on for event in _repayments(400.0, 600.0)]
    assert dates == sorted(dates)
    assert max(dates) == date(2027, 7, 15)
