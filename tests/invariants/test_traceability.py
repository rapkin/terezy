"""C6 -- every figure resolves to the events behind it, and every event to its cause.

Constitution Principle III: *"Every displayed number is traceable to ledger events, and
every ledger event to the rule and the input that produced it. A number that cannot be
traced may not be displayed."* FR-008 says the same in requirement form and adds the
consequence: a figure that cannot be traced must not be reported.

Requirements closed: **C6**, FR-008.

**What "resolves" is taken to mean here**, because the requirement is easy to satisfy
weakly. Three separate claims, asserted separately:

1. *Downwards* -- given a figure the ledger produced, the events behind it can be named,
   and recomputing the figure from those events reproduces it. Anything else makes
   "traceable" mean "accompanied by a plausible list".
2. *Upwards* -- given an event, the term or rule that produced it can be named, and the
   naming is specific rather than a placeholder.
3. *Completely* -- no event is silently dropped on the way in, and no figure appears that
   no event supports. A trace with a hole in it is not a trace.

**Why arrival order is a traceability property and not only a determinism one.** If the
same set of events can produce two different states depending on the order the collection
was assembled in, then the events do not determine the figure and the trace from figure to
events is not a trace at all -- it is a coincidence that holds for one call. The shuffle
property below is therefore here rather than with C4, which asks the narrower question of
whether two identical runs agree.

**Provenance is included in the downward claim, and does not replace E5.** A figure's
sources must be the sources of the events behind it, or the mark on an unverified input
does not survive the fold (FR-015). What that assertion does *not* cover is the path from a
declaration into an event's provenance in the first place, or the rendering of the mark;
those are E5's job in ``tests/contract/test_provenance_propagation.py``.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from terezy.core.ledger import canonical, engine, events, lots
from terezy.core.primitives import money, provenance
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.tolerance import assert_money_close, is_close
from tests.invariants.event_streams import Stream, event_streams

STREAMS = st.sampled_from(Currency).flatmap(lambda currency: event_streams(currency=currency))


def _fold(stream: Stream) -> engine.LedgerState:
    return engine.fold(
        stream.events,
        base_currency=stream.currency,
        consumption_method=lots.FIFO,
    )


# ---------------------------------------------------------------------------
# Upwards: every event names the term or rule that caused it
# ---------------------------------------------------------------------------


@pytest.mark.invariant
@given(stream=STREAMS)
def test_every_event_names_the_term_or_rule_that_caused_it(stream: Stream) -> None:
    """FR-008: each record identifies the instrument term or tax rule that generated it.

    The identifier and the detail are both required to be non-empty. An event carrying an
    empty cause would satisfy a naive presence check and tell a reader nothing, which is
    the failure mode that makes an audit trail decorative.
    """
    for event in _fold(stream).applied:
        assert isinstance(event.caused_by.kind, events.CausationKind)
        assert event.caused_by.id
        assert event.caused_by.detail


@pytest.mark.invariant
@given(stream=STREAMS)
def test_a_tax_charge_is_caused_by_a_tax_rule_and_not_by_a_term(stream: Stream) -> None:
    """The cause is specific, not merely present.

    A ledger that labelled every event "instrument term" would pass the previous property
    and be useless: the question a reader asks of a tax line is *which rule charged this*,
    and answering it with the bond's coupon term is a wrong answer, not a vague one.

    ⚙ **Feature 009 added the payment to the tax side of the split**, and did not loosen it:
    each kind is still pinned to exactly one causation kind, and the money that settles a
    tax year has to name the rule that assessed it for the same reason the assessment does.
    A payment traceable only to "an instrument term" would send a reader to a coupon.
    """
    for event in _fold(stream).applied:
        if event.kind in {events.EventKind.TAX_CHARGE, events.EventKind.TAX_PAYMENT}:
            assert event.caused_by.kind is events.CausationKind.TAX_RULE
        else:
            assert event.caused_by.kind is events.CausationKind.INSTRUMENT_TERM


# ---------------------------------------------------------------------------
# Completely: nothing is dropped, and nothing appears unsupported
# ---------------------------------------------------------------------------


@pytest.mark.invariant
@given(stream=STREAMS)
def test_the_ledger_keeps_every_event_it_was_given(stream: Stream) -> None:
    """No event is dropped, none is invented, and the order is the sequence order.

    The ledger's own record of what it folded is the spine of every trace below. If it can
    quietly omit an event -- one whose kind nothing happened to handle, say -- then every
    figure recomputed from it agrees with the ledger and disagrees with reality.
    """
    applied = _fold(stream).applied
    assert [event.sequence for event in applied] == sorted(
        event.sequence for event in stream.events
    )
    assert set(applied) == set(stream.events)


@pytest.mark.invariant
@given(stream=STREAMS)
def test_every_disposal_resolves_to_the_event_that_caused_it(stream: Stream) -> None:
    """A realised gain names its disposal event, and agrees with it on every shared fact.

    The disposal record is the figure a tax rule will be applied to, so it is the figure
    most in need of a trace. Its sequence number is the trace, and this asserts the trace
    actually leads somewhere consistent rather than to an event that says something else.
    """
    state = _fold(stream)
    by_sequence = {event.sequence: event for event in state.applied}
    for disposal in state.disposals:
        assert disposal.sequence in by_sequence
        event = by_sequence[disposal.sequence]
        assert events.closes_lot(event)
        assert disposal.occurred_on == event.occurred_on
        assert disposal.caused_by == event.caused_by
        assert disposal.instrument_id == events.lot_ref_of(event).instrument_id
        assert is_close(disposal.quantity, events.quantity_of(event))
        assert_money_close(disposal.proceeds_trade_ccy, event.amount)


@pytest.mark.invariant
@given(stream=STREAMS)
def test_every_consumed_lot_was_opened_by_an_event(stream: Stream) -> None:
    """A disposal's basis traces to the specific acquisitions it drew on.

    ``consumed_from`` is what makes a realised gain checkable by hand: without it, "the
    basis was 1,200" is a number a reader has to take on faith. With it, the reader can
    find the purchases and add them up.
    """
    state = _fold(stream)
    opened = {events.lot_ref_of(event).lot_id for event in state.applied if events.opens_lot(event)}
    for disposal in state.disposals:
        assert disposal.consumed_from, "a disposal that consumed no lot has no basis to show"
        for lot_id, units in disposal.consumed_from:
            assert lot_id in opened
            assert units > 0.0
        assert is_close(sum(units for _, units in disposal.consumed_from), disposal.quantity)


# ---------------------------------------------------------------------------
# Downwards: every figure recomputes from the events the ledger kept
# ---------------------------------------------------------------------------


@pytest.mark.invariant
@given(stream=STREAMS)
def test_every_balance_recomputes_from_the_events_the_ledger_kept(stream: Stream) -> None:
    """Given a balance, name its events and add them up: the same number comes back."""
    state = _fold(stream)
    for currency, account in state.accounts.items():
        contributing = [
            event.amount for event in state.applied if event.amount.currency is currency
        ]
        assert contributing, "an account exists only because events moved money in it"
        assert_money_close(account.balance, money.total(contributing, currency))


@pytest.mark.invariant
@given(stream=STREAMS)
def test_every_position_recomputes_from_the_events_the_ledger_kept(stream: Stream) -> None:
    """Given a holding, name the acquisitions and disposals behind it and re-derive it."""
    state = _fold(stream)
    for instrument_id, position in state.positions.items():
        acquired = sum(
            events.quantity_of(event)
            for event in state.applied
            if events.opens_lot(event) and events.lot_ref_of(event).instrument_id == instrument_id
        )
        disposed = sum(
            disposal.quantity
            for disposal in state.disposals
            if disposal.instrument_id == instrument_id
        )
        assert is_close(position.quantity, acquired - disposed)


@pytest.mark.invariant
@given(stream=STREAMS)
def test_a_balances_sources_are_the_sources_of_its_events(stream: Stream) -> None:
    """The mark travels with the figure, because the figure is a sum of marked events.

    FR-015 calls a derived figure that loses its parent's mark the highest-severity defect
    in the project. Here the claim is the traceability half of it: the sources attached to
    a balance are exactly the sources of the events that produced it -- no source appears
    from nowhere, and none is dropped on the way. In particular, if any contributing event
    was unverified then the balance reports itself unverified.
    """
    state = _fold(stream)
    for currency, account in state.accounts.items():
        expected = provenance.merge_all(
            event.amount.provenance for event in state.applied if event.amount.currency is currency
        )
        assert account.balance.provenance == expected
        assert provenance.is_unverified(account.balance.provenance) == provenance.is_unverified(
            expected
        )


@pytest.mark.invariant
@given(stream=STREAMS)
def test_a_realised_gains_sources_are_the_sources_of_its_terms(stream: Stream) -> None:
    """A gain rests on its proceeds, its consumed basis and its fees -- and says so."""
    for disposal in _fold(stream).disposals:
        expected = provenance.merge_all(
            (
                disposal.proceeds_trade_ccy.provenance,
                disposal.consumed_basis_trade_ccy.provenance,
                disposal.allocated_fees_trade_ccy.provenance,
            )
        )
        assert disposal.realised_gain_trade_ccy.provenance == expected


# ---------------------------------------------------------------------------
# The events determine the figure, not the order they arrived in
# ---------------------------------------------------------------------------


@pytest.mark.invariant
@given(stream=STREAMS, data=st.data())
def test_the_state_is_a_function_of_the_events_and_not_of_their_arrival_order(
    stream: Stream,
    data: st.DataObject,
) -> None:
    """Shuffling the input changes nothing: ``sequence`` is the only order that counts.

    See the module docstring for why this is a traceability property. The comparison is on
    the canonical form rather than on the states themselves, so it is a comparison of every
    amount's bits -- a difference hiding below the tolerance would still fail here, which
    is the point.
    """
    shuffled = data.draw(st.permutations(stream.events))
    assert canonical.of_result(_fold(stream)) == canonical.of_result(
        engine.fold(
            shuffled,
            base_currency=stream.currency,
            consumption_method=lots.FIFO,
        )
    )


@pytest.mark.invariant
@given(stream=STREAMS)
def test_the_canonical_form_names_every_event_and_no_amount_as_a_float(
    stream: Stream,
) -> None:
    """The traceable form carries the whole trail, and carries no rounded number.

    Two claims in one walk of the canonical form. It contains one entry per event folded,
    so a digest taken over it is a digest over the audit trail and not only over the
    totals. And it contains no ``float`` anywhere: every amount has been rendered by
    ``float.hex()``, so nothing in it can be compared at the wrong precision.

    ⚙ The events are ``form[-2]`` rather than ``form[-1]`` since feature 002 appended the
    capacity accumulator, which is asserted here too: an accumulator in the state and absent
    from the canonical form would let two runs with different monthly consumption digest
    identically, and C4 would pass while covering less than it says.
    """
    state = _fold(stream)
    form = canonical.of_result(state)
    applied_form, capacity_form = form[-2], form[-1]
    assert len(applied_form) == len(state.applied)  # type: ignore[arg-type]
    assert len(capacity_form) == len(state.capacity)  # type: ignore[arg-type]
    assert not _floats_in(form)


def _floats_in(value: object) -> bool:
    if isinstance(value, tuple):
        return any(_floats_in(item) for item in value)
    return isinstance(value, float)
