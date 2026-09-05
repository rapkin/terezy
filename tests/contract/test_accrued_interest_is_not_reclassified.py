"""013 FR-024, which 022 leaves standing: the whole purchase price is the lot's basis.

022 lifted 013 FR-017's prohibition -- the accrued/clean split **is** computed now, because the
transcribed depository schedule states every coupon date and the declaration carries a day
count, so the two facts FR-017 named as missing are declared. What did not move is what the
ledger records: no part of what was paid is reclassified as accrued interest, amortised or
imputed. The tax character of accrued interest paid at purchase is 013 FR-025's premium figure
and its declared category treatment (`docs/METHODOLOGY.md` §31.6), and 022 adds no rule of its
own.

The absence walk this module used to carry is gone with the prohibition it proved. What it
would have caught is now a **figure**, checked by `tests/worked_examples/test_accrued_interest.py`
against hand arithmetic.
"""

from __future__ import annotations

import pytest

from terezy.core.instruments.interface import Assumptions, DateRange, Holding
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results import project
from terezy.core.results.project import Projection
from terezy.data.declarations import resolver
from tests import tuple_registries as fixtures

pytestmark = pytest.mark.contract

DECLARATIONS = resolver.from_data_root(fixtures.DATA_ROOT)
MIRROR = "ovdp_enumerated_mirror"

PAID = 10_150.0


def _projected() -> Projection:
    declared = DECLARATIONS.instruments[MIRROR]
    outcome = project.project(
        declared,
        Holding(
            owner_id="owner-1",
            instrument_id=MIRROR,
            quantity=10.0,
            purchased_on=fixtures.ISSUE_DATE,
            cost=Money(PAID, Currency.UAH, prov.EMPTY),
        ),
        DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END),
        Assumptions(consumption_method="fifo", coupon_policy="hold_cash"),
        tax_classes=DECLARATIONS.tax_classes,
    )
    assert isinstance(outcome, Projection), outcome
    return outcome


def test_the_purchase_cost_is_recorded_in_full_as_the_lot_s_basis() -> None:
    """Nothing is amortised, nothing is imputed, and no part of what was paid is reclassified."""
    projected = _projected()
    purchase = projected.ledger.applied[0]
    assert purchase.amount.amount == -PAID
    (disposal,) = projected.ledger.disposals
    assert disposal.consumed_basis_base_ccy.amount == PAID, (
        "the whole of what was paid is the basis the redemption consumes; a part "
        "reclassified as accrued interest would show up here as a smaller one"
    )
