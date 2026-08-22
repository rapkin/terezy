"""The schedule is a projection of the ledger, and a tax figure it cannot place is refused.

Two behaviours of ``results.schedule.of_ledger`` that the worked example exercises but
does not isolate.

**A tax charge is folded into the row of the event it taxed**, using the pairing the
producer supplied. Read the module docstring of ``results.schedule`` for why the pairing is
passed in rather than inferred from dates: an inferred pairing is a guess, and it starts
lying the moment two taxable events share a date -- which in this feature they do, since
the final coupon and the redemption are both paid on the adjusted maturity date.

**A tax event that nothing claims raises rather than being dropped.** FR-008 says a figure
that cannot be traced may not be reported, and silently omitting the row would understate
the tax while leaving every total looking tidy -- the quiet kind of wrong this project
exists to avoid.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.errors import LedgerInvariantError
from terezy.core.ledger import engine
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close
from terezy.core.results import project, schedule
from terezy.core.results.project import Projection
from terezy.core.results.schedule import ConventionsApplied
from tests import synthetic

UAH = Currency.UAH

CONVENTIONS = ConventionsApplied(
    periodicity="semiannual", day_count="act/365", business_day_rule="following"
)

TERM = CausationRef(kind=CausationKind.INSTRUMENT_TERM, id="fixture:term", detail="a fixture event")
RULE = CausationRef(kind=CausationKind.TAX_RULE, id="fixture:class", detail="a fixture tax")


def _event(sequence: int, kind: EventKind, amount: float, **extra: object) -> Event:
    return Event(
        sequence=sequence,
        occurred_on=date(2026, 1, 15),
        kind=kind,
        amount=Money(amount, UAH, prov.EMPTY),
        owner_id="owner-1",
        caused_by=RULE if kind is EventKind.TAX_CHARGE else TERM,
        lot_ref=extra.get("lot_ref"),  # type: ignore[arg-type]
        quantity=extra.get("quantity"),  # type: ignore[arg-type]
        allocated_to=None,
        capacity_pool=None,
    )


def test_an_unclaimed_tax_event_is_refused_rather_than_dropped() -> None:
    stream = (
        _event(
            1,
            EventKind.PURCHASE,
            -1000.0,
            lot_ref=LotRef(instrument_id="x", lot_id="x@1"),
            quantity=1.0,
        ),
        _event(2, EventKind.TAX_CHARGE, -10.0),
    )
    state = engine.fold(stream, base_currency=UAH, consumption_method="fifo")
    with pytest.raises(LedgerInvariantError, match="not charged against any event"):
        schedule.of_ledger(state, conventions=CONVENTIONS, taxed_by={})


def test_a_tax_charge_lands_on_the_row_of_the_event_it_taxed() -> None:
    # Two taxable events on one date -- exactly the case an inferred pairing would get
    # wrong. The supplied mapping puts each charge where it belongs.
    stream = (
        _event(
            1,
            EventKind.PURCHASE,
            -1000.0,
            lot_ref=LotRef(instrument_id="x", lot_id="x@1"),
            quantity=1.0,
        ),
        _event(2, EventKind.COUPON, 100.0),
        _event(3, EventKind.TAX_CHARGE, -20.0),
        _event(4, EventKind.COUPON, 50.0),
        _event(5, EventKind.TAX_CHARGE, -5.0),
    )
    state = engine.fold(stream, base_currency=UAH, consumption_method="fifo")
    rows = schedule.of_ledger(state, conventions=CONVENTIONS, taxed_by={2: 3, 4: 5}).rows
    assert [row.sequence for row in rows] == [1, 2, 4]
    assert_money_close(rows[1].tax, Money(20.0, UAH, prov.EMPTY))
    assert_money_close(rows[1].net, Money(80.0, UAH, prov.EMPTY))
    assert_money_close(rows[2].tax, Money(5.0, UAH, prov.EMPTY))
    assert_money_close(rows[2].net, Money(45.0, UAH, prov.EMPTY))


def test_a_row_with_no_tax_rule_reports_a_zero_resting_on_no_source() -> None:
    # A purchase is not taxable, so nothing was charged and the zero cites nothing. That
    # is a different claim from a zero *charge* citing an exemption, and the provenance is
    # what tells them apart -- which is why the row carries it rather than a bare float.
    outcome = project.project(
        synthetic.declaration(),
        synthetic.holding(),
        synthetic.horizon(),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
    )
    assert isinstance(outcome, Projection)
    purchase = outcome.schedule.rows[0]
    assert purchase.kind is EventKind.PURCHASE
    assert purchase.tax.amount == 0.0
    assert purchase.tax.provenance == prov.EMPTY

    coupon = outcome.schedule.rows[1]
    assert coupon.tax.amount == 0.0
    assert synthetic.EXEMPTION_SOURCE in coupon.tax.provenance.sources


def test_every_row_resolves_back_to_the_event_behind_it() -> None:
    # FR-008 at the schedule level: the row carries the sequence number and the cause, so
    # a reader can go from a figure to the record that produced it without guessing.
    outcome = project.project(
        synthetic.declaration(),
        synthetic.holding(),
        synthetic.horizon(),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
    )
    assert isinstance(outcome, Projection)
    by_sequence = {event.sequence: event for event in outcome.ledger.applied}
    for row in outcome.schedule.rows:
        event = by_sequence[row.sequence]
        assert row.caused_by == event.caused_by
        assert row.occurred_on == event.occurred_on
        assert_money_close(row.gross, event.amount)
