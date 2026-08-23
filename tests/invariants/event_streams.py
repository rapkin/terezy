"""A Hypothesis strategy generating *valid* ledger event streams.

Shared by the conservation suite (C1, C2, C3) and the traceability suite (C6), so both
assert over the same body of generated histories rather than two differently-shaped
ones.

Not a test module -- ``pytest`` collects only ``test_*.py``, so this file is imported,
never run.

**Why the generated amounts and quantities are whole numbers.** Every amount below is
drawn as an integer and widened to ``float``. Integral values up to 2**53 are exact in
float64, so the conservation assertions test *the ledger's logic* rather than the
accumulated rounding of binary floating point. That is the right target: the tolerance
policy already covers float behaviour (FR-002), and a conservation test that failed
intermittently on rounding would teach the suite to be loose about conservation. The
comparisons still go through the single project tolerance, so a genuine drift is still
caught.

**Why the streams are valid by construction.** A disposal never exceeds the quantity
held, because the strategy tracks holdings as it draws. Invalid streams are a different
requirement -- the engine raises on them, asserted by targeted tests -- and mixing the
two would mean the conservation properties spent most of their examples on inputs that
never reach a fold.

**Provenance is drawn deliberately**, from a pool containing a verified source, an
unverified one, and both. E5's propagation assertions belong to a later phase, but
generating streams that are sometimes unverified means the ledger is exercised against
marked money from the start rather than having the mark bolted on later.

⚙ **Feature 009 split the tax operations in two, and changed nothing else.** A
``TAX_CHARGE`` is now an assessment that moves no money, so the generator draws it at zero
cash; a ``TAX_PAYMENT`` is the money actually leaving on a declared due date, so the
generator draws that too, from zero upwards. The point of drawing both is the claim 008
made for seeds and 009 makes for payments: a payment is an **ordinary ledger citizen**, and
the way to test that is to feed the conservation and traceability properties that already
exist a body of ledgers containing payments and change not one of them. If a property fails
only for those ledgers, the event is wrong -- never the invariant (009 research.md D2).

**Every disposal carries a fee line**, drawn from zero upwards and allocated to that
disposal by sequence number. Feature 001 charges no fees -- route and exit costs are
outside the hurdle-rate figure by construction -- so without this the third term of C3's
identity (``gain = proceeds - basis - fees``) would be a hardcoded zero and the invariant
would assert two thirds of what it claims. A zero fee is generated as often as a non-zero
one because a zero cost is still a cost line (``REWRITE_BRIEF`` B13) and the ledger must
carry it as one rather than treating it as an absence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from hypothesis import strategies as st

from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.primitives import provenance
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef

OWNER = "owner-001"
"""One owner, per Principle VII: the field exists from day one, unused."""

INSTRUMENT = "ovdp-synthetic-a"

VERIFIED_SOURCE = SourceRef(
    id="test/verified",
    citation="synthetic test input, verified",
    retrieved_on=date(2026, 8, 1),
    verified_on=date(2026, 8, 21),
)

UNVERIFIED_SOURCE = SourceRef(
    id="test/unverified",
    citation="synthetic test input, never verified",
    retrieved_on=date(2026, 8, 1),
    verified_on=None,
)

PROVENANCE_POOL: tuple[Provenance, ...] = (
    provenance.of([VERIFIED_SOURCE]),
    provenance.of([UNVERIFIED_SOURCE]),
    provenance.of([VERIFIED_SOURCE, UNVERIFIED_SOURCE]),
)

_TERM = CausationRef(
    kind=CausationKind.INSTRUMENT_TERM,
    id="ovdp-synthetic-a:terms",
    detail="synthetic instrument term, generated stream",
)

_RULE = CausationRef(
    kind=CausationKind.TAX_RULE,
    id="ua_government_bond",
    detail="synthetic tax rule, generated stream",
)


@dataclass(frozen=True, slots=True)
class Stream:
    """A generated history and the facts a test needs to check it independently."""

    events: tuple[Event, ...]
    currency: Currency
    instrument_id: str


_QUANTITIES = st.integers(min_value=1, max_value=1_000)
_UNIT_PRICES = st.integers(min_value=1, max_value=2_000)
_CASH_AMOUNTS = st.integers(min_value=1, max_value=100_000)
_TAX_PAYMENTS = st.integers(min_value=0, max_value=50_000)
"""What a settled year takes out of cash. Zero is drawn as often as anything else: a year
assessed at nothing produces no payment at all in production, and a zero-amount payment is
the boundary a generator should still put through the fold."""
_FEE_AMOUNTS = st.integers(min_value=0, max_value=500)


@st.composite
def event_streams(draw: st.DrawFn, currency: Currency = Currency.UAH) -> Stream:
    """A funded holding's history: an opening deposit, then purchases, coupons, tax and
    redemptions, in ascending date and sequence order.

    Sequence numbers are assigned densely from zero as events are appended, which is what
    the engine relies on: the fold order is the sequence, never the order the collection
    happened to arrive in.
    """
    opening = draw(st.integers(min_value=10_000, max_value=1_000_000))
    first_day = draw(st.dates(min_value=date(2024, 1, 1), max_value=date(2026, 1, 1)))
    gaps = draw(st.lists(st.integers(min_value=0, max_value=120), min_size=1, max_size=8))

    events: list[Event] = [
        Event(
            sequence=0,
            occurred_on=first_day,
            kind=EventKind.CASH_DEPOSIT,
            amount=Money(float(opening), currency, draw(st.sampled_from(PROVENANCE_POOL))),
            owner_id=OWNER,
            caused_by=_TERM,
            lot_ref=None,
            quantity=None,
            allocated_to=None,
            capacity_pool=None,
        )
    ]

    on = first_day
    held = 0
    lots_created = 0

    for gap in gaps:
        on = on + timedelta(days=gap)
        sequence = len(events)
        prov = draw(st.sampled_from(PROVENANCE_POOL))
        operations = ["buy", "coupon", "assess", "pay_tax"]
        if held > 0:
            operations.append("redeem")
        operation = draw(st.sampled_from(operations))

        if operation == "buy":
            quantity = draw(_QUANTITIES)
            cost = quantity * draw(_UNIT_PRICES)
            lots_created += 1
            held += quantity
            events.append(
                Event(
                    sequence=sequence,
                    occurred_on=on,
                    kind=EventKind.PURCHASE,
                    amount=Money(-float(cost), currency, prov),
                    owner_id=OWNER,
                    caused_by=_TERM,
                    lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id=f"lot-{lots_created}"),
                    quantity=float(quantity),
                    allocated_to=None,
                    capacity_pool=None,
                )
            )
        elif operation == "coupon":
            events.append(
                Event(
                    sequence=sequence,
                    occurred_on=on,
                    kind=EventKind.COUPON,
                    amount=Money(float(draw(_CASH_AMOUNTS)), currency, prov),
                    owner_id=OWNER,
                    caused_by=_TERM,
                    lot_ref=None,
                    quantity=None,
                    allocated_to=None,
                    capacity_pool=None,
                )
            )
        elif operation == "assess":
            events.append(
                Event(
                    sequence=sequence,
                    occurred_on=on,
                    kind=EventKind.TAX_CHARGE,
                    amount=Money(-0.0, currency, prov),
                    owner_id=OWNER,
                    caused_by=_RULE,
                    lot_ref=None,
                    quantity=None,
                    allocated_to=None,
                    capacity_pool=None,
                )
            )
        elif operation == "pay_tax":
            events.append(
                Event(
                    sequence=sequence,
                    occurred_on=on,
                    kind=EventKind.TAX_PAYMENT,
                    amount=Money(-float(draw(_TAX_PAYMENTS)), currency, prov),
                    owner_id=OWNER,
                    caused_by=_RULE,
                    lot_ref=None,
                    quantity=None,
                    allocated_to=None,
                    capacity_pool=None,
                )
            )
        else:
            quantity = draw(st.integers(min_value=1, max_value=held))
            held -= quantity
            proceeds = quantity * draw(_UNIT_PRICES)
            disposal_sequence = sequence + 1
            events.append(
                Event(
                    sequence=sequence,
                    occurred_on=on,
                    kind=EventKind.FEE,
                    amount=Money(-float(draw(_FEE_AMOUNTS)), currency, prov),
                    owner_id=OWNER,
                    caused_by=_TERM,
                    lot_ref=None,
                    quantity=None,
                    allocated_to=disposal_sequence,
                    capacity_pool=None,
                )
            )
            events.append(
                Event(
                    sequence=disposal_sequence,
                    occurred_on=on,
                    kind=EventKind.PRINCIPAL_REPAYMENT,
                    amount=Money(float(proceeds), currency, prov),
                    owner_id=OWNER,
                    caused_by=_TERM,
                    lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id=None),
                    quantity=float(quantity),
                    allocated_to=None,
                    capacity_pool=None,
                )
            )

    return Stream(events=tuple(events), currency=currency, instrument_id=INSTRUMENT)
