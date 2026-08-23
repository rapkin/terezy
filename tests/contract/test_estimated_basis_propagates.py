"""SC-003, FR-007, FR-008, G14: a guessed cost is a guessed tax, all the way through.

Required test **J2**, second half: *a basis-estimated seed marks every downstream tax
figure.* The first half -- the hand-computed gain on a known-basis lot -- is
``tests/worked_examples/test_seeded_disposal.py``.

**Two runs, identical but for one word.** The same instrument, the same quantity, the same
cost, the same disposal at the same price on the same date. One declares its basis *known*
and the other *estimated*. Everything asserted below is the difference that one word makes,
which is what makes the suite discriminating: a mark smeared over every figure would pass
the marked half and fail the unmarked one.

**Why the tax figures are swept by reflection.** SC-003 says *100% of the tax figures*, and
a test that lists the fields it knows about closes over today's record. Every ``Money``
field of ``TaxCharge`` is derived from the taxable base, so every one of them must carry the
mark, and enumerating them from the dataclass means a field added tomorrow is covered
tonight. The disposal's fields are checked explicitly instead, because two of them --
proceeds and allocated fees -- genuinely do **not** rest on the basis, and demanding a mark
on those would be asserting that the mark is meaningless.

**Why the class used here is the taxed one with a verified citation.** Under the exempt
class the charge is zero and under an unverified citation everything is marked anyway;
either would let this suite pass while proving nothing. With verified rates the *only*
unverified source anywhere in the run is the owner's estimate, so
``provenance.is_unverified`` on a tax figure is a statement about the basis and nothing else.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import date

import pytest

from terezy.core.instruments.interface import InstrumentDeclaration
from terezy.core.ledger import engine, lots, seeds
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.ledger.lots import Disposal
from terezy.core.ledger.seeds import SeedLot
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.tax import registry as tax_registry
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxContext
from tests import synthetic

pytestmark = pytest.mark.contract

UAH = Currency.UAH
OWNER = "owner-001"
INSTRUMENT = "ovdp_synthetic_a"
ACQUIRED_ON = date(2025, 3, 14)
OPENS_ON = date(2026, 1, 1)
DISPOSED_ON = date(2026, 6, 30)

DECLARED: dict[str, InstrumentDeclaration] = {
    INSTRUMENT: synthetic.declaration(
        id=INSTRUMENT, terms=synthetic.terms(issue_date=date(2020, 1, 1))
    )
}

ESTIMATE_REASON = "bought across several months in 2024; the cabinet shows units, not prices"

MARKET_OBSERVATION = SourceRef(
    id="synthetic:market_price",
    citation="SYNTHETIC FIXTURE -- an invented quoted price, never verified.",
    retrieved_on=date(2026, 6, 30),
    verified_on=None,
)
"""An ordinary unverified observation, for the case where a figure rests on both marks."""

_TERM = CausationRef(
    kind=CausationKind.INSTRUMENT_TERM,
    id=f"{INSTRUMENT}:redemption",
    detail="synthetic redemption",
)


def _seed(*, estimated: bool) -> SeedLot:
    """One lot of 100 units costing 98 000.00 UAH, known or estimated, and nothing else differs.

    **The cost is built with empty provenance in both cases, deliberately.** The mark lives on
    ``basis`` and nowhere else here, which is exactly the lot a caller assembling seeds without
    a file produces -- the caller ``core.errors`` and the resolver both keep a refusal for. If
    the join between the two fields ever moves back out of ``core.ledger.seeds``, every
    assertion below goes red rather than only the ones that happen to go through the loader.
    """
    if estimated:
        basis: seeds.Basis = seeds.basis_estimated(
            declared_at="tests/test_estimated_basis_propagates#seed[0]",
            reason=ESTIMATE_REASON,
            estimated_for=ACQUIRED_ON,
        )
    else:
        basis = seeds.KNOWN
    return SeedLot(
        owner_id=OWNER,
        is_synthetic=True,
        lot_id="seed-0",
        declared_at="tests/test_estimated_basis_propagates#seed[0]",
        instrument_id=INSTRUMENT,
        quantity=100.0,
        acquired_on=ACQUIRED_ON,
        cost=Money(98_000.0, UAH, prov.EMPTY),
        basis=basis,
    )


def _disposal(*, estimated: bool, proceeds_sources: Provenance = prov.EMPTY) -> Disposal:
    """The seeded lot, redeemed whole for 110 000.00 UAH."""
    opened = seeds.opening_events((_seed(estimated=estimated),), DECLARED, opens_on=OPENS_ON)
    assert isinstance(opened, tuple), opened
    stream = (
        *opened,
        Event(
            sequence=len(opened),
            occurred_on=DISPOSED_ON,
            kind=EventKind.PRINCIPAL_REPAYMENT,
            amount=Money(110_000.0, UAH, proceeds_sources),
            owner_id=OWNER,
            caused_by=_TERM,
            lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id=None),
            quantity=100.0,
            allocated_to=None,
            capacity_pool=None,
        ),
    )
    state = engine.fold(stream, base_currency=UAH, consumption_method=lots.FIFO)
    (realised,) = state.disposals
    return realised


def _charge(disposal: Disposal) -> TaxCharge:
    """The tax on that gain, through the declared rule the projection uses.

    ``synthetic.TAXED_CLASS`` carries a **verified** citation, so any unverified source on a
    figure below came from the owner's estimate rather than from the rate.
    """
    outcome = tax_registry.ops_for(tax_registry.FLAT_RATE).charge(
        Event(
            sequence=disposal.sequence,
            occurred_on=disposal.occurred_on,
            kind=EventKind.PRINCIPAL_REPAYMENT,
            amount=disposal.proceeds_base_ccy,
            owner_id=OWNER,
            caused_by=_TERM,
            lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id=None),
            quantity=disposal.quantity,
            allocated_to=None,
            capacity_pool=None,
        ),
        synthetic.TAXED_CLASS,
        TaxContext(
            instrument_id=INSTRUMENT,
            taxable_event=TaxableEventKind.DISPOSAL_GAIN,
            # Exactly what ``results.project`` charges a disposal against: the realised
            # gain in the base currency, not the proceeds.
            taxable_base=disposal.realised_gain_base_ccy,
            charged_for_year=disposal.occurred_on.year,
        ),
    )
    assert isinstance(outcome, TaxCharge), outcome
    return outcome


def _money_fields(record: Disposal | TaxCharge) -> dict[str, Money]:
    """Every ``Money`` on a record, by field name. See the module docstring."""
    return {
        field.name: value
        for field in fields(record)
        if isinstance(value := getattr(record, field.name), Money)
    }


# ---------------------------------------------------------------------------
# The estimated basis reaches the gain, and through it the tax
# ---------------------------------------------------------------------------


def test_the_mark_reaches_the_ledger_from_the_declaration_rather_than_from_the_cost() -> None:
    """The structural claim, stated as its own case rather than left implicit in the others.

    ``SeedLot`` holds the amount and the basis in two fields, and nothing in the type system
    couples them. Before ``seeds.seed_cost`` existed the mark reached the gain only because the
    loader attached it at construction, so a lot assembled in code -- with ``basis`` saying
    *estimated* and ``cost`` carrying nothing -- folded into an entirely unmarked gain and an
    entirely unmarked tax. The declaration and the amount are joined in the module that owns
    the declaration, so the route the lot took cannot change what it says.
    """
    lot = _seed(estimated=True)
    assert lot.cost.provenance == prov.EMPTY
    assert seeds.rests_on_estimated_basis(seeds.seed_cost(lot).provenance)
    opened = seeds.opening_events((lot,), DECLARED, opens_on=OPENS_ON)
    assert isinstance(opened, tuple), opened
    (opening,) = opened
    assert seeds.rests_on_estimated_basis(opening.amount.provenance)


def test_the_gain_on_an_estimated_basis_lot_is_marked() -> None:
    """FR-007, US2 scenario 1. The basis is guessed, so the gain computed from it is."""
    disposal = _disposal(estimated=True)
    for name in ("consumed_basis_trade_ccy", "consumed_basis_base_ccy"):
        assert seeds.rests_on_estimated_basis(_money_fields(disposal)[name].provenance), name
    for name in ("realised_gain_trade_ccy", "realised_gain_base_ccy"):
        assert seeds.rests_on_estimated_basis(_money_fields(disposal)[name].provenance), name


def test_every_tax_figure_downstream_of_an_estimated_basis_carries_the_mark() -> None:
    """SC-003 and required test **J2**, second half: 100% of them, not most of them.

    Swept from the dataclass rather than listed, so the claim covers the whole record --
    including a field somebody adds later without reading this file.
    """
    charge = _charge(_disposal(estimated=True))
    figures = _money_fields(charge)
    assert set(figures) == {"pit", "levy", "total", "taxable_base"}, (
        "TaxCharge gained or lost a money field; the sweep below is meant to cover all of them"
    )
    for name, figure in figures.items():
        assert seeds.rests_on_estimated_basis(figure.provenance), f"{name} lost the mark"
        assert prov.is_unverified(figure.provenance), f"{name} does not render marked"
    assert seeds.rests_on_estimated_basis(charge.provenance)


def test_the_mark_names_the_lot_and_states_the_reason() -> None:
    """FR-008: a mark that cannot say what it rests on is a taint flag, not provenance."""
    charge = _charge(_disposal(estimated=True))
    (mark,) = seeds.basis_estimated_sources(charge.total.provenance)
    assert mark.id.endswith("seed[0]")
    assert ESTIMATE_REASON in mark.citation
    assert mark.verified_on is None


# ---------------------------------------------------------------------------
# The known-basis twin, and the difference one word makes
# ---------------------------------------------------------------------------


def test_a_known_basis_marks_nothing() -> None:
    """US2 scenario 2. The negative half, and the reason the positive half means anything.

    With a known basis and a verified tax class there is no unverified source anywhere in
    the run, so the figures render unmarked -- which is only assertable because the mark is
    carried by data rather than switched on by a flag somebody could leave set.
    """
    charge = _charge(_disposal(estimated=False))
    for name, figure in _money_fields(charge).items():
        assert not seeds.rests_on_estimated_basis(figure.provenance), name
        assert not prov.is_unverified(figure.provenance), name
    assert seeds.basis_estimated_sources(charge.provenance) == frozenset()


def test_a_figure_resting_on_both_kinds_of_mark_shows_both() -> None:
    """FR-008's last sentence, and the reason there is one marking system and not two.

    The proceeds carry an unverified market observation and the basis is estimated. Both
    reach the gain, both reach the tax, and ``unverified_sources`` names them separately --
    while ``merge`` treats them identically, which is what FR-007 requires.
    """
    charge = _charge(_disposal(estimated=True, proceeds_sources=prov.of([MARKET_OBSERVATION])))
    unverified = prov.unverified_sources(charge.total.provenance)
    estimated = seeds.basis_estimated_sources(charge.total.provenance)
    assert len(unverified) == 2
    assert estimated < unverified
    assert MARKET_OBSERVATION in unverified - estimated


def test_the_proceeds_are_not_marked_by_the_basis_they_are_compared_against() -> None:
    """The mark travels with what depends on it, and no further.

    A mark on every figure in the record would be indistinguishable from no mark at all: the
    reader could not tell which numbers the owner's guess actually moved. What the owner
    received is an observation of the disposal, not of the acquisition.
    """
    disposal = _disposal(estimated=True)
    for name in ("proceeds_trade_ccy", "proceeds_base_ccy", "allocated_fees_base_ccy"):
        assert not seeds.rests_on_estimated_basis(_money_fields(disposal)[name].provenance), name
