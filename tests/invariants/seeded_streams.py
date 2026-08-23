"""Generated ledgers that **open from declared seed lots**, for SC-005.

The claim under test is research.md D1's: *a seed is an ordinary ledger citizen*. It opens
the ledger through the same path a purchase takes, so every conservation property already
written counts it without being told it exists. The way to test that claim is not to write
new conservation properties for seeded ledgers -- it is to feed the **existing** ones a
body of ledgers that begin from seeds, and change nothing else.

So this module produces the same :class:`~tests.invariants.event_streams.Stream` record the
unseeded generator produces, and ``tests/invariants/test_ledger_conservation.py`` draws from
both. If a property fails only for seeded ledgers, the opening is wrong and the fix is in
``core.ledger.seeds``; it is never a reason to teach an invariant about seeds (quickstart §1).

**The seed events come from the production function.** ``seeds.opening_events`` builds them,
not this module -- a generator that hand-rolled the events would be asserting conservation
over a stream the engine never produces, which is the shape of test that stays green while
the code it claims to cover rots.

**Seeds are dated before the base stream** because an event stream is a history and
``events.in_sequence`` refuses one that runs backwards. Their sequences come first and the
base stream's are shifted past them, ``allocated_to`` included -- a fee whose allocation
was not shifted would point at the wrong event, and the fee would silently leave the gain.

**The seeded instrument is the one the base stream trades**, deliberately. FIFO consumes the
oldest lots first, so a generated redemption draws on the *seeded* basis before any purchase
the stream made -- which is what puts seeded costs inside the realised-gain identity rather
than merely inside the opening balance.

Not a test module -- ``pytest`` collects only ``test_*.py``, so this file is imported, never
run.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from hypothesis import strategies as st

from terezy.core.instruments.interface import InstrumentDeclaration
from terezy.core.ledger import seeds
from terezy.core.ledger.events import Event
from terezy.core.ledger.seeds import SeedLot
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from tests import synthetic
from tests.invariants.event_streams import INSTRUMENT, OWNER, PROVENANCE_POOL, Stream, event_streams

_EARLY_ISSUE = date(2000, 1, 1)
"""An issue date before any generated acquisition.

The generated seeds are dated up to 900 days before a base stream that itself starts as
early as 2024, and ``opening_events`` refuses a lot acquired before its instrument existed.
That refusal is asserted in ``tests/unit/test_seed_opening.py``; here it would only mean the
generator was drawing inputs the engine is entitled to reject.
"""

SEEDED_INSTRUMENTS: dict[str, InstrumentDeclaration] = {
    INSTRUMENT: synthetic.declaration(
        id=INSTRUMENT,
        terms=synthetic.terms(issue_date=_EARLY_ISSUE),
    )
}
"""The curated declarations the seeds are resolved against -- one, and it is synthetic."""

_QUANTITIES = st.integers(min_value=1, max_value=1_000)
_UNIT_COSTS = st.integers(min_value=1, max_value=2_000)
_DAYS_BEFORE = st.integers(min_value=1, max_value=900)
_SEED_COUNT = st.integers(min_value=1, max_value=3)


def _estimated_basis(index: int, acquired_on: date) -> seeds.BasisEstimated:
    """A basis the owner states from memory, marked as one.

    Drawn as often as a known basis, so the generated body exercises marked money through
    the whole fold rather than only through the targeted propagation tests.
    """
    return seeds.basis_estimated(
        declared_at=f"tests/seeded_streams#seed[{index}]",
        reason="SYNTHETIC FIXTURE -- a generated lot whose cost the owner does not recall",
        estimated_for=acquired_on,
    )


def _cost(amount: int, currency: Currency, sources: Provenance) -> Money:
    """The declared acquisition cost.

    Built here rather than in ``core``: a test is entitled to construct money directly, and
    this is the one place the generated declaration enters the system, exactly as the loader
    is that place in production.
    """
    return Money(float(amount), currency, sources)


@st.composite
def seeded_event_streams(draw: st.DrawFn, currency: Currency = Currency.UAH) -> Stream:
    """A base history with one to three declared opening lots in front of it.

    Quantities and costs are whole numbers for the reason ``event_streams`` gives: integral
    values are exact in float64, so a conservation failure is a failure of the ledger's logic
    rather than of binary floating point.
    """
    base = draw(event_streams(currency=currency))
    opens_on = base.events[0].occurred_on

    lots: list[SeedLot] = []
    for index in range(draw(_SEED_COUNT)):
        acquired_on = opens_on - timedelta(days=draw(_DAYS_BEFORE))
        quantity = draw(_QUANTITIES)
        amount = quantity * draw(_UNIT_COSTS)
        if draw(st.booleans()):
            estimated = _estimated_basis(index, acquired_on)
            basis: seeds.Basis = estimated
            sources = prov.of([estimated.mark])
        else:
            basis = seeds.KNOWN
            sources = draw(st.sampled_from((*PROVENANCE_POOL, prov.EMPTY)))
        lots.append(
            SeedLot(
                owner_id=OWNER,
                is_synthetic=True,
                lot_id=f"seed-{index}",
                declared_at=f"tests/seeded_streams#seed[{index}]",
                instrument_id=INSTRUMENT,
                quantity=float(quantity),
                acquired_on=acquired_on,
                cost=_cost(amount, currency, sources),
                basis=basis,
            )
        )

    opened = seeds.opening_events(tuple(lots), SEEDED_INSTRUMENTS, opens_on=opens_on)
    assert isinstance(opened, tuple), f"the generator drew a seed the engine refused: {opened!r}"

    shifted = tuple(_shift(event, by=len(opened)) for event in base.events)
    return Stream(events=(*opened, *shifted), currency=currency, instrument_id=INSTRUMENT)


def _shift(event: Event, *, by: int) -> Event:
    """One base-stream event moved past the opening lots, allocation and all."""
    return replace(
        event,
        sequence=event.sequence + by,
        allocated_to=None if event.allocated_to is None else event.allocated_to + by,
    )
