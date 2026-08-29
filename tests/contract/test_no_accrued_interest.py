"""SC-023: no output of a declared schedule splits a purchase price.

FR-017. Two facts are missing and neither may be inferred: the start of the accrual period
containing the purchase, and the basis interest accrues on within it. So no accrued-interest
figure, no clean price, and no field separating what was paid.

⚙ **A prohibition, not a refusal, and the difference is why this is a walk rather than an
assertion on a value.** Nothing in this engine computes accrued interest today, so a typed
refusal for it would be dead code -- a caller would have to ask for the figure to be told it
cannot have it, and nobody asks. What can be checked is the **absence**, and an absence is
only proved by looking everywhere. The walk is what makes "no such figure exists" evidence
instead of an assumption.

The refusal arrives with the figure, if it ever does. `specs/features.toml` records the
seam: what would restore the split is a declared previous-coupon date plus a declared
accrual basis, and neither of them is the issue date.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass, make_dataclass, replace
from typing import Any

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

FORBIDDEN = ("accrued", "accrual", "clean_price", "clean_amount", "dirty_price")
"""Field names that would mean a purchase price had been separated.

``accrual`` as well as ``accrued`` because reconstructing the *period* is the first of the
two missing facts, and a field carrying one would be the invention rather than the figure
derived from it.
"""


def _projected() -> Projection:
    declared = DECLARATIONS.instruments[MIRROR]
    outcome = project.project(
        declared,
        Holding(
            owner_id="owner-1",
            instrument_id=MIRROR,
            quantity=10.0,
            purchased_on=fixtures.ISSUE_DATE,
            cost=Money(10_150.0, Currency.UAH, prov.EMPTY),
        ),
        DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END),
        Assumptions(consumption_method="fifo", coupon_policy="hold_cash"),
        tax_classes=DECLARATIONS.tax_classes,
    )
    assert isinstance(outcome, Projection), outcome
    return outcome


def _walk(value: Any, path: str, seen: set[int], found: list[str]) -> None:
    """Every field name reachable from a result record, depth first.

    Cycles are impossible over frozen records built by a pure fold, and ``seen`` is carried
    anyway: a walk that could loop is a test that hangs rather than fails.
    """
    if id(value) in seen:
        return
    seen.add(id(value))
    if is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            name = f"{path}.{field.name}"
            if any(word in field.name for word in FORBIDDEN):
                found.append(name)
            _walk(getattr(value, field.name), name, seen, found)
    elif isinstance(value, (tuple, list, frozenset, set)):
        for index, item in enumerate(value):
            _walk(item, f"{path}[{index}]", seen, found)
    elif isinstance(value, dict):
        for key, item in value.items():
            _walk(item, f"{path}[{key!r}]", seen, found)


def test_no_field_of_any_result_record_splits_the_purchase_price() -> None:
    found: list[str] = []
    _walk(_projected(), "projection", set(), found)
    assert not found, (
        "a projection of a declared schedule carries a field separating what was paid "
        f"(FR-017): {found}. Two facts are missing and neither may be inferred."
    )


def test_the_walk_reaches_the_records_that_could_hold_such_a_field() -> None:
    """A walk of nothing passes forever. These are the records a split would land in."""
    named: list[str] = []
    _collect(_projected(), "projection", set(), named)
    for reached in (
        "projection.ledger.applied[0].amount.amount",
        "projection.ledger.disposals[0]",
        "projection.schedule.rows[0]",
        "projection.hurdle",
        "projection.charges",
    ):
        assert reached in named, reached


def _collect(value: Any, path: str, seen: set[int], found: list[str]) -> None:
    """The same walk, recording every name rather than only the forbidden ones."""
    if id(value) in seen:
        return
    seen.add(id(value))
    found.append(path)
    if is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            _collect(getattr(value, field.name), f"{path}.{field.name}", seen, found)
    elif isinstance(value, (tuple, list, frozenset, set)):
        for index, item in enumerate(value):
            _collect(item, f"{path}[{index}]", seen, found)


def test_the_walk_would_catch_a_split_if_one_were_added() -> None:
    """Falsifiability: a record carrying the forbidden field is found, and the ordinary
    records are not."""
    projected = _projected()
    planted = replace(
        projected,
        hurdle=replace(projected.hurdle, excludes=frozenset({"accrued interest"})),
    )
    found: list[str] = []
    _walk(planted, "projection", set(), found)
    assert not found, "a forbidden *value* is not a forbidden field; the scan reads names"

    fake = make_dataclass("WithASplit", [("accrued_interest", float)])(1.0)
    caught: list[str] = []
    _walk(fake, "planted", set(), caught)
    assert caught == ["planted.accrued_interest"]


def test_the_purchase_cost_is_recorded_in_full_as_the_lot_s_basis() -> None:
    """FR-024, the positive half of the same requirement. Nothing is amortised, nothing is
    imputed, and no part of what was paid is reclassified -- which is the only honest
    treatment while the two facts FR-017 names are missing."""
    projected = _projected()
    purchase = projected.ledger.applied[0]
    assert purchase.amount.amount == -10_150.0
    (disposal,) = projected.ledger.disposals
    assert disposal.consumed_basis_base_ccy.amount == 10_150.0, (
        "the whole of what was paid is the basis the redemption consumes; a part "
        "reclassified as accrued interest would show up here as a smaller one"
    )
