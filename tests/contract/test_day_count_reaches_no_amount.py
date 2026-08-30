"""SC-020: the declared day count annualises, and reaches nothing else.

FR-003a lets a declared schedule carry a day count because the contractual yield cannot be
computed without one and a hard-coded 365 is forbidden at the site that would need it.
FR-003b then forbids it being an input to **any figure describing the instrument's own
terms** -- not an amount, and **not a rate**.

**Why the boundary is drawn at return figures versus issue terms rather than at rates
versus amounts.** A day count plus one coupon amount plus the interval between two coupons
yields a **coupon rate**; a coupon rate plus the spacing yields an extrapolated **issue
date**. That is the invented legal fact this whole declaration form exists to refuse,
reached in two steps from a field FR-003a requires. An earlier draft of the specification
drew the line one category short of that door and permitted the first step in its own
sentence.

**Two locks, deliberately** (FR-003c). This file is the first: change the declared day
count and watch the yield move while every cash-flow amount stays bit-identical.
`tests/contract/test_nothing_is_inferred.py` is the second, and it scans for the
coupon-rate derivation itself -- because a guard that believes itself sufficient is the one
nobody adds a second lock to.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from terezy.core.instruments.interface import Assumptions, DateRange, EnumeratedTerms, Holding
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.conventions import DAY_COUNT_FNS
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results import project
from terezy.core.results.project import Projection
from terezy.data.declarations import resolver
from tests import source_scan
from tests import tuple_registries as fixtures

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "src" / "terezy"

DECLARATIONS = resolver.from_data_root(fixtures.DATA_ROOT)
MIRROR = "ovdp_enumerated_mirror"
DECLARED = "act/365"
OTHER = "30/360"

HOLDING = Holding(
    owner_id="owner-1",
    instrument_id=MIRROR,
    quantity=10.0,
    purchased_on=fixtures.ISSUE_DATE,
    cost=Money(10_000.0, Currency.UAH, prov.EMPTY),
)


def _under(day_count: str) -> Projection:
    """The same declaration, the same purchase, one convention changed and nothing else."""
    declared = DECLARATIONS.instruments[MIRROR]
    terms = declared.terms
    assert isinstance(terms, EnumeratedTerms)
    outcome = project.project(
        replace(declared, terms=replace(terms, day_count=day_count)),
        HOLDING,
        DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END),
        Assumptions(consumption_method="fifo", coupon_policy="hold_cash"),
        tax_classes=DECLARATIONS.tax_classes,
    )
    assert isinstance(outcome, Projection), outcome
    return outcome


class TestChangingTheDeclaredDayCount:
    def test_moves_the_yield(self) -> None:
        """It must, or the convention is a field nobody reads and FR-003a's argument for
        requiring it collapses."""
        assert _under(DECLARED).hurdle.nominal_ytm.value != _under(OTHER).hurdle.nominal_ytm.value

    def test_leaves_every_cash_flow_amount_bit_identical(self) -> None:
        """``float.hex()``, not a tolerance. A tolerance here would pass on a day count that
        reached an amount and moved it by a fraction of a percent -- which is exactly the
        size of change this assertion exists to catch."""
        declared, other = _under(DECLARED).schedule.rows, _under(OTHER).schedule.rows
        assert len(declared) == len(other)
        for one, two in zip(declared, other, strict=True):
            assert one.gross.amount.hex() == two.gross.amount.hex(), one.occurred_on
            assert one.tax.amount.hex() == two.tax.amount.hex(), one.occurred_on
            assert one.net.amount.hex() == two.net.amount.hex(), one.occurred_on

    def test_leaves_every_date_and_every_quantity_untouched(self) -> None:
        """FR-003b's other clauses: it places no date, generates no schedule, and
        reconstructs no accrual period."""
        declared, other = _under(DECLARED).schedule.rows, _under(OTHER).schedule.rows
        assert [(row.occurred_on, row.kind, row.quantity) for row in declared] == [
            (row.occurred_on, row.kind, row.quantity) for row in other
        ]

    def test_leaves_the_realised_gain_and_the_tax_total_untouched(self) -> None:
        for one, two in zip(
            _under(DECLARED).ledger.disposals, _under(OTHER).ledger.disposals, strict=True
        ):
            assert (
                one.realised_gain_base_ccy.amount.hex() == two.realised_gain_base_ccy.amount.hex()
            )
        assert _under(DECLARED).hurdle.total_tax.amount.hex() == (
            _under(OTHER).hurdle.total_tax.amount.hex()
        )

    @pytest.mark.parametrize("day_count", sorted(DAY_COUNT_FNS))
    def test_every_implemented_convention_gives_the_same_amounts(self, day_count: str) -> None:
        """Not just the two above. Whichever convention is declared, the amounts are the
        declared payments times the units held, and the convention has no way in."""
        for one, two in zip(
            _under(DECLARED).schedule.rows, _under(day_count).schedule.rows, strict=True
        ):
            assert one.gross.amount.hex() == two.gross.amount.hex()


def test_every_amount_is_traceable_to_a_declared_payment() -> None:
    """The other half of SC-020: the amounts are not merely stable under the convention,
    they are the declared figures. A computation that happened to be convention-invariant
    would pass the assertions above and fail this one."""
    terms = DECLARATIONS.instruments[MIRROR].terms
    assert isinstance(terms, EnumeratedTerms)
    per_unit = {payment.amount.amount for payment in terms.payments}
    for row in _under(DECLARED).schedule.rows:
        if row.gross.amount <= 0.0:
            continue  # the purchase, which is the owner's stated cost
        assert row.gross.amount / HOLDING.quantity in per_unit


def test_the_module_that_builds_the_events_never_calls_a_day_count() -> None:
    """The scan half of SC-020, and the reason it is worth having beside the behavioural
    half: an amount computed from a convention and then rounded back would be invisible to
    a bit-comparison of two runs whose rounding agreed."""
    building = source_scan.executable_source(SOURCE_ROOT / "core" / "instruments" / "enumerated.py")
    for reaching in ("day_count", "conventions.", "year_fraction"):
        assert reaching not in building, (
            f"{reaching!r} appears in the module that turns declared payments into events; "
            "a day count reaching an amount is the door FR-003b closes"
        )
