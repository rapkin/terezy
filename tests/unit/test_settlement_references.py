"""FR-002 and C6 across the seam settling a year cuts in the stream.

Inserting a payment renumbers every event after it, and the references that point *into* the
stream from outside it do not move on their own. With one payment nothing shows, because the
payment lands last; with two taxable years and a payment date between them the second year's
charges are exactly the references that shift.

```
gross    1 deposit | 2 purchase | 3 purchase | 4 disposal(2027) | 5 disposal(2029)
settled  1 deposit | 2 purchase | 3 purchase | 4 disposal(2027) | 5 tax_payment
                                             | 6 disposal(2029) | 7 tax_payment
```

The 2029 statement was built against the gross stream and its charge names event 5. In the
settled stream event 5 is the 2028 tax payment, so a reader following the charge back to what
was taxed lands on a payment of the *previous* year's bill -- a figure that resolves to the
wrong cause, which is worse than one that resolves to nothing.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Final

import pytest

from terezy.core.errors import LedgerInvariantError
from terezy.core.ledger import engine
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.ledger.lots import LotMethod
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results import tax_year as settlement
from terezy.core.results.schedule import ChargedOn
from terezy.core.tax import flat_rate
from terezy.core.tax import year as tax_year
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxContext
from tests import tax_years

UAH: Final = Currency.UAH
OWNER: Final = "owner-1"
INSTRUMENT: Final = "fixture_two_taxable_years"
SOURCE: Final = prov.of([tax_years.FIXTURE_SOURCE])

FIRST_SOLD_ON: Final = date(2027, 6, 10)
SECOND_SOLD_ON: Final = date(2029, 6, 10)
HORIZON_END: Final = date(2030, 12, 31)

FIRST_GAIN: Final = 5_000.00
SECOND_GAIN: Final = 10_000.00


def _uah(amount: float) -> Money:
    return Money(amount, UAH, SOURCE)


def _term() -> CausationRef:
    return CausationRef(
        kind=CausationKind.INSTRUMENT_TERM, id=f"{INSTRUMENT}:terms", detail="fixture term"
    )


def _event(sequence: int, on: date, kind: EventKind, amount: float, **extra: object) -> Event:
    return Event(
        sequence=sequence,
        occurred_on=on,
        kind=kind,
        amount=_uah(amount),
        owner_id=OWNER,
        caused_by=extra.get("caused_by", _term()),  # type: ignore[arg-type]
        lot_ref=extra.get("lot_ref"),  # type: ignore[arg-type]
        quantity=extra.get("quantity"),  # type: ignore[arg-type]
        allocated_to=extra.get("allocated_to"),  # type: ignore[arg-type]
        capacity_pool=None,
    )


def _events() -> tuple[Event, ...]:
    """Two lots bought together, sold two years apart, so two years each owe something."""
    return (
        _event(1, date(2026, 1, 5), EventKind.CASH_DEPOSIT, 100_000.00),
        _event(
            2,
            date(2026, 1, 5),
            EventKind.PURCHASE,
            -10_000.00,
            lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id="lot-a"),
            quantity=100.0,
        ),
        _event(
            3,
            date(2026, 1, 6),
            EventKind.PURCHASE,
            -10_000.00,
            lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id="lot-b"),
            quantity=100.0,
        ),
        _event(
            4,
            FIRST_SOLD_ON,
            EventKind.PRINCIPAL_REPAYMENT,
            15_000.00,
            lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id=None),
            quantity=100.0,
        ),
        _event(
            5,
            SECOND_SOLD_ON,
            EventKind.PRINCIPAL_REPAYMENT,
            20_000.00,
            lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id=None),
            quantity=100.0,
        ),
    )


def _statements() -> tuple[tax_year.AnnualStatement, ...]:
    events = _events()
    state = engine.fold(events, base_currency=UAH, consumption_method=LotMethod.FIFO.value)
    by_sequence = {event.sequence: event for event in events}
    charges = []
    for disposal in state.disposals:
        charged = flat_rate.charge(
            by_sequence[disposal.sequence],
            tax_years.TAXED_CLASS,
            TaxContext(
                instrument_id=INSTRUMENT,
                taxable_event=TaxableEventKind.DISPOSAL_GAIN,
                taxable_base=disposal.realised_gain_base_ccy,
                charged_for_year=disposal.occurred_on.year,
            ),
        )
        assert isinstance(charged, TaxCharge), charged
        charges.append(charged)
    built = tax_year.statements(
        state,
        tuple(charges),
        rules=tax_years.rules(),
        tax_classes=tax_years.TAX_PACK,
        filing=tax_years.filing(y2027=True, y2029=True),
        method=LotMethod.FIFO,
        switches=tax_years.positions(),
    )
    assert isinstance(built, tuple), built
    return built


def _settled() -> settlement.Settlement:
    outcome = settlement.settle(
        _events(),
        _statements(),
        owner_id=OWNER,
        base_currency=UAH,
        method=LotMethod.FIFO,
        horizon_end=HORIZON_END,
    )
    assert isinstance(outcome, settlement.Settlement), outcome
    return outcome


def _year(statements: tuple[tax_year.AnnualStatement, ...], year: int) -> tax_year.AnnualStatement:
    found = [
        statement
        for statement in statements
        if statement.tax_year == year and statement.category == tax_years.INVESTMENT
    ]
    assert len(found) == 1, f"expected one {year} statement, got {found!r}"
    return found[0]


class TestTheFixtureActuallyCutsTheStream:
    """Without this shape nothing below is about anything: a lone payment lands last."""

    def test_a_payment_falls_between_the_two_taxable_years(self) -> None:
        kinds = [event.kind.value for event in _settled().stream]

        assert kinds == [
            "cash_deposit",
            "purchase",
            "purchase",
            "principal_repayment",
            "tax_payment",
            "principal_repayment",
            "tax_payment",
        ]

    def test_the_two_years_owe_their_own_hand_computed_gains(self) -> None:
        statements = _statements()

        assert _year(statements, 2027).liability.base.amount == FIRST_GAIN
        assert _year(statements, 2029).liability.base.amount == SECOND_GAIN


class TestEveryChargeStillResolvesToWhatItTaxed:
    """FR-002: a statement's charges are traceable to their events, after settling too."""

    def test_the_second_years_charge_points_at_a_payment_before_it_is_restated(self) -> None:
        """The defect this test exists for, pinned so the fix cannot be undone quietly."""
        settled = _settled()
        stale = _year(_statements(), 2029).charges[0].charge.event_sequence

        assert settled.stream[stale - 1].kind is EventKind.TAX_PAYMENT

    def test_every_restated_charge_lands_on_the_event_it_was_charged_on(self) -> None:
        settled = _settled()
        by_sequence = {event.sequence: event for event in settled.stream}

        for statement in settled.statements:
            for item in statement.charges:
                found = by_sequence[item.charge.event_sequence]
                assert found.kind is not EventKind.TAX_PAYMENT, (statement.tax_year, found)
                assert found.occurred_on == item.occurred_on, (statement.tax_year, found)

    def test_restating_moved_the_sequence_numbers_and_nothing_else(self) -> None:
        """A restated statement is the same assessment, so no figure may differ."""
        settled = _settled()

        for original, restated in zip(_statements(), settled.statements, strict=True):
            assert original.tax_year == restated.tax_year
            assert original.liability == restated.liability
            assert original.netted_base == restated.netted_base
            assert original.carryforward == restated.carryforward
            assert [item.result for item in original.charges] == [
                item.result for item in restated.charges
            ]

    def test_a_charge_naming_an_event_the_stream_does_not_hold_is_refused_by_name(self) -> None:
        statements = _statements()
        elsewhere = _year(statements, 2029)
        charge = elsewhere.charges[0].charge
        detached = replace(
            elsewhere,
            charges=(replace(elsewhere.charges[0], charge=replace(charge, event_sequence=99)),),
        )

        with pytest.raises(LedgerInvariantError, match="charge on event 99"):
            settlement.settle(
                _events(),
                (_year(statements, 2027), detached),
                owner_id=OWNER,
                base_currency=UAH,
                method=LotMethod.FIFO,
                horizon_end=HORIZON_END,
            )


class TestTheRenumberingIsHandedBackForEverythingElse:
    """A statement is not the only record holding a sequence number from before the merge."""

    def test_the_map_says_where_each_original_event_went(self) -> None:
        assert _settled().renumbered == {1: 1, 2: 2, 3: 3, 4: 4, 5: 6}

    def test_a_schedule_pairing_moved_by_the_map_still_names_its_own_event(self) -> None:
        """``ChargedOn`` pairs a taxed event with the memo recorded against it, and both
        halves are pre-settlement sequence numbers."""
        settled = _settled()
        pairing = ChargedOn(tax_event=5, amount=_uah(1_500.00))

        moved = replace(pairing, tax_event=settled.renumbered[pairing.tax_event])

        assert moved.tax_event == 6
        assert settled.stream[moved.tax_event - 1].occurred_on == SECOND_SOLD_ON


class TestAnAllocationPointingForwardIsRefusedRatherThanRenumbered:
    """The direction nothing upstream checks: membership is not direction, order is not either."""

    def test_a_fee_allocated_to_a_later_event_names_both(self) -> None:
        stream = (
            _event(1, date(2026, 1, 5), EventKind.CASH_DEPOSIT, 100_000.00),
            _event(2, date(2026, 1, 6), EventKind.FEE, -25.00, allocated_to=3),
            _event(3, date(2026, 1, 7), EventKind.COUPON, 500.00),
        )

        with pytest.raises(LedgerInvariantError, match="it comes later in this stream"):
            settlement.settle(
                stream,
                (),
                owner_id=OWNER,
                base_currency=UAH,
                method=LotMethod.FIFO,
                horizon_end=HORIZON_END,
            )

    def test_the_ordinary_backward_allocation_still_moves_with_the_stream(self) -> None:
        """The falsifying half: a fee that points back is renumbered, not refused."""
        stream = (
            _event(1, date(2026, 1, 5), EventKind.CASH_DEPOSIT, 100_000.00),
            _event(2, date(2026, 1, 6), EventKind.COUPON, 500.00),
            _event(3, date(2026, 1, 7), EventKind.FEE, -25.00, allocated_to=2),
        )

        outcome = settlement.settle(
            stream,
            (),
            owner_id=OWNER,
            base_currency=UAH,
            method=LotMethod.FIFO,
            horizon_end=HORIZON_END,
        )

        assert isinstance(outcome, settlement.Settlement), outcome
        assert outcome.stream[2].allocated_to == 2
