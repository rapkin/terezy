"""Turning declared seed lots into opening events: the shape, and the four refusals.

FR-001, FR-005, G13, G15, G16. The arithmetic a seeded ledger produces is hand-checked in
``tests/worked_examples/test_seeded_disposal.py`` and the conservation properties over
randomly seeded ledgers are in ``tests/invariants/test_ledger_conservation.py``; this module
is about the events themselves -- what kind they are, what they say caused them, what order
they come in, and when the engine declines to build them at all.

**Why the kind matters enough to assert.** A seed opens the ledger as a ``PURCHASE``: the
kind the engine already opens lots with. Giving seeds a kind of their own would be a second
kind meaning "cash out, a lot in", and every consumer -- the fold, the conservation
recomputations, the tax mapping -- would have to learn it. The first one that did not would
drop seeded holdings silently, which is precisely the failure D1 exists to prevent.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from terezy.core.errors import InconsistentTerms, LedgerInvariantError, SeedInstrumentUndeclared
from terezy.core.instruments.interface import InstrumentDeclaration
from terezy.core.ledger import engine, events, lots, seeds
from terezy.core.ledger.events import CausationKind, EventKind
from terezy.core.ledger.seeds import SeedLot
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close, is_close
from tests import synthetic

UAH = Currency.UAH
OWNER = "owner-001"
INSTRUMENT = "ovdp_synthetic_a"
ISSUE = date(2020, 1, 1)
OPENS_ON = date(2026, 8, 1)

DECLARED: dict[str, InstrumentDeclaration] = {
    INSTRUMENT: synthetic.declaration(id=INSTRUMENT, terms=synthetic.terms(issue_date=ISSUE))
}
"""One curated declaration, synthetic, issued long before every lot below."""


def _lot(**overrides: Any) -> SeedLot:
    """A declared opening lot: 10 units, acquired 2025-03-14, cost 9 800.00 UAH, known.

    Keyword overrides on a valid base, on ``tests/synthetic.py``'s precedent: a test that
    wants a broken variant asks for the one field it is about and inherits a valid value for
    everything else, so a reader can see exactly what the case depends on.
    """
    base = SeedLot(
        owner_id=OWNER,
        is_synthetic=True,
        lot_id="seed-0",
        declared_at="tests/test_seed_opening#seed[0]",
        instrument_id=INSTRUMENT,
        quantity=10.0,
        acquired_on=date(2025, 3, 14),
        cost=Money(9_800.0, UAH, prov.EMPTY),
        basis=seeds.KNOWN,
    )
    return replace(base, **overrides)


def _opened(*lots_declared: SeedLot, opens_on: date = OPENS_ON) -> tuple[events.Event, ...]:
    outcome = seeds.opening_events(lots_declared, DECLARED, opens_on=opens_on)
    assert isinstance(outcome, tuple), outcome
    return outcome


# ---------------------------------------------------------------------------
# The shape of an opening event
# ---------------------------------------------------------------------------


def test_a_seed_opens_a_lot_through_the_kind_the_engine_already_knows() -> None:
    """FR-001, G13: a purchase, because that is what the acquisition was."""
    (event,) = _opened(_lot())
    assert event.kind is EventKind.PURCHASE
    assert events.opens_lot(event)
    assert event.lot_ref is not None
    assert event.lot_ref.lot_id == "seed-0"
    assert event.lot_ref.instrument_id == INSTRUMENT
    assert event.quantity == 10.0
    assert event.owner_id == OWNER


def test_the_cash_effect_is_the_declared_cost_going_out() -> None:
    """The cost is the event's outflow, which is what makes the basis recomputable.

    ``tests/invariants/test_ledger_conservation.py`` derives what was paid for a holding by
    summing the outflow of every lot-opening event. A seed whose cash effect were zero --
    "the money left before the ledger opened" -- would put a basis in the position that no
    event paid for, and basis conservation would fail for seeded ledgers alone.
    """
    (event,) = _opened(_lot())
    assert_money_close(event.amount, Money(-9_800.0, UAH, prov.EMPTY))


def test_the_cause_names_the_declaration_it_came_from() -> None:
    """FR-008 of feature 001, C6: a cause is looked up, never guessed.

    A seed is caused by neither an instrument term nor a tax rule nor a route term. Labelling
    it with one of those would be a traceable figure pointing at the wrong declaration, which
    is worse than a widened enum: the reader would go and read a coupon term that had nothing
    to do with the lot.
    """
    (event,) = _opened(_lot())
    assert event.caused_by.kind is CausationKind.SEED_DECLARATION
    assert event.caused_by.id == "tests/test_seed_opening#seed[0]"
    assert INSTRUMENT in event.caused_by.detail


def test_lots_are_sequenced_in_acquisition_order_whatever_order_they_are_declared() -> None:
    """A stream is a history and ``events.in_sequence`` refuses one that runs backwards.

    So the order is the acquisition order, not the order the file happened to list, and the
    tie-break is the lot id -- the same ``(acquired_on, lot_id)`` key FIFO consumption uses,
    because two rules ordering the same lots differently would be two histories.
    """
    later = _lot(acquired_on=date(2025, 9, 1), lot_id="seed-1")
    earlier = _lot(acquired_on=date(2024, 2, 2), lot_id="seed-2")
    opened = _opened(later, earlier)
    assert [event.sequence for event in opened] == [0, 1]
    assert [event.occurred_on for event in opened] == [date(2024, 2, 2), date(2025, 9, 1)]
    assert events.in_sequence(opened) == opened


def test_two_lots_of_one_instrument_on_one_date_are_two_lots() -> None:
    """Two purchases on one day are two acquisitions (spec, Edge Cases), not a merge."""
    first = _lot(lot_id="seed-0")
    second = _lot(lot_id="seed-1", quantity=4.0, cost=Money(4_100.0, UAH, prov.EMPTY))
    positions = lots.rebuild(
        _opened(first, second), base_currency=UAH, consumption_method=lots.FIFO
    )
    held = positions[INSTRUMENT]
    assert [lot.lot_id for lot in held.lots] == ["seed-0", "seed-1"]
    assert is_close(held.quantity, 14.0)
    assert_money_close(held.basis_base_ccy, Money(13_900.0, UAH, prov.EMPTY))


def test_no_seeds_is_an_ordinary_empty_run() -> None:
    """FR-024, G16, research.md D9. A person who holds nothing is an ordinary person.

    Deliberately unlike feature 003's empty registry dimension, where an empty list and a
    mistyped path are indistinguishable downstream and one of them is a mistake. Here they
    are distinguishable, so emptiness is not a typed outcome and not a refusal.
    """
    assert seeds.opening_events((), DECLARED, opens_on=OPENS_ON) == ()
    state = engine.fold((), base_currency=UAH, consumption_method=lots.FIFO)
    assert state.positions == {}


# ---------------------------------------------------------------------------
# The refusals
# ---------------------------------------------------------------------------


def test_an_undeclared_instrument_is_refused_naming_it() -> None:
    """FR-005, G15: no placeholder instrument is invented for a seed that names one."""
    outcome = seeds.opening_events(
        (_lot(instrument_id="not_declared_anywhere"),), DECLARED, opens_on=OPENS_ON
    )
    assert isinstance(outcome, SeedInstrumentUndeclared)
    assert outcome.instrument_id == "not_declared_anywhere"
    assert outcome.lot_id == "seed-0"
    assert "not_declared_anywhere" in outcome.reason


def test_a_lot_acquired_before_its_instrument_existed_is_an_inconsistency() -> None:
    """Spec, Edge Cases: reported rather than accepted, and never silently re-dated."""
    outcome = seeds.opening_events(
        (_lot(acquired_on=date(2019, 12, 31)),), DECLARED, opens_on=OPENS_ON
    )
    assert isinstance(outcome, InconsistentTerms)
    assert outcome.first_term == "seed.acquired_on"
    assert outcome.second_term == "instrument.terms.issue_date"
    assert "2019-12-31" in outcome.reason


def test_a_lot_acquired_after_the_ledger_opens_is_an_inconsistency() -> None:
    """A holding acquired in the future is not a holding. Not re-dated, not admitted."""
    outcome = seeds.opening_events(
        (_lot(acquired_on=date(2026, 8, 2)),), DECLARED, opens_on=OPENS_ON
    )
    assert isinstance(outcome, InconsistentTerms)
    assert outcome.first_term == "seed.acquired_on"
    assert outcome.second_term == "projection.opens_on"
    assert "2026-08-02" in outcome.reason


def test_a_lot_acquired_on_the_day_the_ledger_opens_is_admitted() -> None:
    """The boundary is inclusive: bought today, held today. Asserted so the guard above
    cannot be tightened into refusing a legitimate holding without a test going red."""
    (event,) = _opened(_lot(acquired_on=OPENS_ON))
    assert event.occurred_on == OPENS_ON


def test_the_first_refusal_wins_and_nothing_is_partially_opened() -> None:
    """A refusal is the whole answer. Half a ledger is worse than none: the figures it
    produced would describe a portfolio the owner does not hold."""
    outcome = seeds.opening_events(
        (_lot(), _lot(lot_id="seed-1", instrument_id="not_declared_anywhere")),
        DECLARED,
        opens_on=OPENS_ON,
    )
    assert isinstance(outcome, SeedInstrumentUndeclared)


def test_disposing_of_more_than_is_seeded_is_refused_naming_what_is_held() -> None:
    """Spec, Edge Cases: never silently clipped.

    The refusal is the ledger's own -- a seeded lot is an ordinary lot, so over-consumption is
    caught by the same guard that catches it for a purchased one, and this asserts that the
    seeded path really does reach it rather than opening a position the engine will let go
    negative.
    """
    opened = _opened(_lot(quantity=10.0))
    stream = (
        *opened,
        events.Event(
            sequence=len(opened),
            occurred_on=date(2026, 8, 1),
            kind=EventKind.PRINCIPAL_REPAYMENT,
            amount=Money(20_000.0, UAH, prov.EMPTY),
            owner_id=OWNER,
            caused_by=events.CausationRef(
                kind=CausationKind.INSTRUMENT_TERM,
                id=f"{INSTRUMENT}:redemption",
                detail="a disposal larger than the holding",
            ),
            lot_ref=events.LotRef(instrument_id=INSTRUMENT, lot_id=None),
            quantity=25.0,
            allocated_to=None,
            capacity_pool=None,
        ),
    )
    with pytest.raises(LedgerInvariantError, match=r"only 10\.0 are held"):
        engine.fold(stream, base_currency=UAH, consumption_method=lots.FIFO)


@pytest.mark.parametrize("quantity", [0.0, -3.0])
def test_a_non_positive_quantity_reaching_the_core_is_a_programmer_error(quantity: float) -> None:
    """The loader refuses it naming the file and the field; if one gets this far the fold
    raises rather than opening a lot that holds nothing (``events.check_shape``)."""
    opened = seeds.opening_events((_lot(quantity=quantity),), DECLARED, opens_on=OPENS_ON)
    assert isinstance(opened, tuple)
    with pytest.raises(LedgerInvariantError, match="lot"):
        engine.fold(opened, base_currency=UAH, consumption_method=lots.FIFO)
