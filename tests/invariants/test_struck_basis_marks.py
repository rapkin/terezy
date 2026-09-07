"""025 FR-027, SC-006: a struck estimated basis carries two marks, and both reach every figure.

The two are different things a reader must do something different about. An **estimated
basis** is the owner's own guess and the only cure is his finding the receipt; an **unverified
official rate** was downloaded and not yet checked against the publisher. A figure showing one
and not the other tells the reader half of why it cannot be trusted, which the constitution
puts in its top severity class.

Property-based over generated lots and dates rather than by example, because the failure this
guards against is a *path*: one transform in one currency combination dropping one of the two.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from terezy.core.ledger import seeds
from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.tax import official_rate
from tests import official_rates as fixtures

pytestmark = pytest.mark.invariant

FIRST = date(2026, 1, 1)
"""The first day the fixture series declares. Every generated date is an offset from it."""

SPAN = 30
UAH = Currency.UAH
USD = Currency.USD


SERIES = fixtures.series(
    [(FIRST + timedelta(days=offset), 40.0 + offset * 0.5) for offset in range(SPAN)]
)
"""A synthetic UAH-per-USD series over ``SPAN`` consecutive days, every rate different.

Distinct rates, so a strike that silently used a neighbouring date would produce a different
number rather than the same one. Every ``verified_on`` is empty, which is the state every
fetched rate is in and the one that makes the second mark exist at all.
"""


def _struck(cost: float, acquired_on: date) -> seeds.SeedLot:
    """One estimated lot whose dollar cost has been struck into hryvnia, as the resolver does."""
    declared_at = "tests/test_struck_basis_marks#seed[0]"
    conversion = official_rate.strike_base(
        Money(cost, USD, prov.EMPTY), SERIES, tax_currency=UAH, on_date=acquired_on
    )
    assert isinstance(conversion, official_rate.TaxCurrencyConversion), conversion
    return seeds.SeedLot(
        owner_id="owner-001",
        lot_id="seed-0",
        declared_at=declared_at,
        is_synthetic=True,
        instrument_id="synthetic_held_x",
        quantity=1.0,
        acquired_on=acquired_on,
        cost=conversion.base,
        basis=seeds.basis_estimated(
            declared_at=declared_at,
            reason="AN INVENTED REASON FOR AN INVENTED LOT",
            estimated_for=acquired_on,
        ),
        struck_from=conversion,
    )


@settings(max_examples=100, deadline=None)
@given(
    cost=st.floats(min_value=1.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    offset=st.integers(min_value=0, max_value=SPAN - 1),
    scale=st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False),
)
def test_both_marks_survive_every_figure_derived_from_the_basis(
    cost: float, offset: int, scale: float
) -> None:
    """The estimate and the rate observation both reach a figure computed from the basis.

    ``seed_cost`` is the join, and scaling is the cheapest derived figure there is: anything
    that lost a mark here would lose it everywhere downstream, because provenance only ever
    unions.
    """
    lot = _struck(cost, FIRST + timedelta(days=offset))
    derived = money.scale_sourced(seeds.seed_cost(lot), scale, prov.EMPTY)

    estimated = seeds.basis_estimated_sources(derived.provenance)
    unverified = prov.unverified_sources(derived.provenance)
    assert estimated, "the owner's own estimate was dropped from a figure resting on it"
    assert unverified - estimated, "the official rate's own mark was dropped"


@settings(max_examples=50, deadline=None)
@given(offset=st.integers(min_value=0, max_value=SPAN - 1))
def test_the_two_marks_are_distinguishable_on_inspection(offset: int) -> None:
    """FR-008's requirement, restated for the struck case: the cures are different.

    Indistinguishable to ``merge``, which is what makes them propagate by one rule; told apart
    by ``is_basis_estimated``, which is what lets a reader be told which is which.
    """
    lot = _struck(1_000.0, FIRST + timedelta(days=offset))
    sources = seeds.seed_cost(lot).provenance.sources
    estimated = {ref for ref in sources if seeds.is_basis_estimated(ref)}
    assert len(estimated) == 1
    assert len(sources - estimated) == 1


def test_a_lot_whose_cost_was_never_struck_carries_only_the_estimate() -> None:
    """The control: without a strike there is one mark, so the assertion above can fail."""
    declared_at = "tests/test_struck_basis_marks#seed[0]"
    lot = seeds.SeedLot(
        owner_id="owner-001",
        lot_id="seed-0",
        declared_at=declared_at,
        is_synthetic=True,
        instrument_id="synthetic_held_x",
        quantity=1.0,
        acquired_on=FIRST,
        cost=Money(1_000.0, UAH, prov.EMPTY),
        basis=seeds.basis_estimated(
            declared_at=declared_at, reason="an invented reason", estimated_for=FIRST
        ),
        struck_from=None,
    )
    sources = seeds.seed_cost(lot).provenance.sources
    assert len(sources) == 1
    assert seeds.is_basis_estimated(next(iter(sources)))
