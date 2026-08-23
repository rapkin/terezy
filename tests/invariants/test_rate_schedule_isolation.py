"""SC-002: two declared classes on one instrument cannot collide, whatever their rates.

The instrument declares one class for its coupons and a **different** one for its
disposal, and the property is that editing the coupon class's schedule moves the coupon
subtotal and leaves every disposal figure **bit-identical** -- not close, identical. A
crossed lookup, a shared mutable default, a rate cached on the wrong key: each of those
would show up as a disposal figure that drifted when nothing about the disposal changed.

**Why property-based rather than one example.** A collision is invisible whenever the two
classes happen to carry the same rates, and an example test picks one pair of rates
forever. Generated rates walk over the case where the two classes agree, the case where
one is zero, and the case where they differ by a hair -- and the assertion is bit-equality,
so a drift smaller than any tolerance still fails.

The bond is bought **below par** (9 000.00 for 10 units redeeming at 10 000.00) so the
disposal realises a gain of exactly 1 000.00. At par the gain is zero and every disposal
charge is zero whatever the rates are, which would make this property pass for the wrong
reason -- it would be asserting that zero equals zero.
"""

from __future__ import annotations

from datetime import date
from typing import Final

import pytest
from hypothesis import given
from hypothesis import strategies as st

from terezy.core.ledger.events import EventKind
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import project
from terezy.core.results.project import Projection
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxClass
from tests import synthetic

pytestmark = pytest.mark.invariant

COUPON_CLASS_ID: Final = "fixture_coupon_class"
DISPOSAL_CLASS_ID: Final = "fixture_disposal_class"

COST_BELOW_PAR: Final = 9_000.00
"""Bought below par, so the redemption realises a gain of 1 000.00 to charge against."""

REALISED_GAIN: Final = 1_000.00

DISPOSAL_PIT: Final = 0.18
DISPOSAL_LEVY: Final = 0.05
"""The disposal class's rates, held fixed while the coupon class's vary. Invented."""

RATES = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


def _class_of(class_id: str, kind: TaxableEventKind, pit: float, levy: float) -> TaxClass:
    return TaxClass(
        id=class_id,
        applies_to=frozenset({kind}),
        rates=synthetic.rates(pit, levy),
    )


def _disposal_class() -> TaxClass:
    return _class_of(DISPOSAL_CLASS_ID, TaxableEventKind.DISPOSAL_GAIN, DISPOSAL_PIT, DISPOSAL_LEVY)


def _projected(coupon_pit: float, coupon_levy: float) -> Projection:
    coupon_class = _class_of(COUPON_CLASS_ID, TaxableEventKind.COUPON, coupon_pit, coupon_levy)
    disposal_class = _disposal_class()
    outcome = project.project(
        synthetic.declaration(
            tax_classes={
                TaxableEventKind.COUPON: COUPON_CLASS_ID,
                TaxableEventKind.DISPOSAL_GAIN: DISPOSAL_CLASS_ID,
            }
        ),
        synthetic.holding(cost=Money(COST_BELOW_PAR, Currency.UAH, prov.EMPTY)),
        synthetic.horizon(),
        synthetic.assumptions(),
        tax_classes={COUPON_CLASS_ID: coupon_class, DISPOSAL_CLASS_ID: disposal_class},
    )
    assert isinstance(outcome, Projection), f"expected a projection, got {outcome!r}"
    return outcome


def _by_class(projection: Projection, class_id: str) -> list[TaxCharge]:
    return [charge for charge in projection.charges if charge.tax_class_id == class_id]


def test_the_fixture_realises_a_gain_so_the_property_is_not_asserting_zero_equals_zero() -> None:
    """The precondition every case below rests on, checked once and explicitly."""
    projection = _projected(0.0, 0.0)
    (disposal,) = _by_class(projection, DISPOSAL_CLASS_ID)
    assert is_close(disposal.taxable_base.amount, REALISED_GAIN)
    assert is_close(disposal.total.amount, REALISED_GAIN * (DISPOSAL_PIT + DISPOSAL_LEVY))
    assert disposal.total.amount > 0.0


@given(pit=RATES, levy=RATES)
def test_changing_the_coupon_schedule_leaves_every_disposal_figure_bit_identical(
    pit: float,
    levy: float,
) -> None:
    """SC-002. Bit-identity, not tolerance: nothing about the disposal changed at all."""
    baseline = _by_class(_projected(0.0, 0.0), DISPOSAL_CLASS_ID)
    varied = _by_class(_projected(pit, levy), DISPOSAL_CLASS_ID)
    assert len(baseline) == len(varied) == 1
    for was, now in zip(baseline, varied, strict=True):
        assert now.pit.amount == was.pit.amount
        assert now.levy.amount == was.levy.amount
        assert now.total.amount == was.total.amount
        assert now.taxable_base.amount == was.taxable_base.amount
        assert now.tax_class_id == was.tax_class_id == DISPOSAL_CLASS_ID


@given(pit=RATES, levy=RATES)
def test_the_coupon_subtotal_is_exactly_what_the_coupon_class_declares(
    pit: float,
    levy: float,
) -> None:
    """The other half: the class that *was* edited moves, and by the declared amount.

    Without this, a lookup that returned the same rate for both classes would satisfy the
    bit-identity property above by never charging the coupons at all.
    """
    charges = _by_class(_projected(pit, levy), COUPON_CLASS_ID)
    assert len(charges) == 4, "four coupons over the two-year holding"
    for charge in charges:
        base = charge.taxable_base.amount
        assert is_close(charge.pit.amount, base * pit)
        assert is_close(charge.levy.amount, base * levy)


@given(pit=RATES, levy=RATES)
def test_no_coupon_charge_ever_carries_the_disposal_class_and_the_reverse(
    pit: float,
    levy: float,
) -> None:
    """Neither class's rates may ever be applied to the other's events (FR-007).

    Asserted on the *event kinds* rather than on the charge count, because a projection
    that charged the right number of events under the wrong classes would pass a count.
    """
    projection = _projected(pit, levy)
    kind_of = {event.sequence: event.kind for event in projection.ledger.applied}
    for charge in projection.charges:
        expected = (
            COUPON_CLASS_ID
            if kind_of[charge.event_sequence] is EventKind.COUPON
            else DISPOSAL_CLASS_ID
        )
        assert charge.tax_class_id == expected


def test_the_two_classes_are_declared_from_different_dates_without_interfering() -> None:
    """A schedule is per class: one starting later does not shorten the other's reach.

    The coupon class starts on the bond's issue date and the disposal class two years
    later, just before the redemption. Both events are covered, each by its own class, and
    neither class's earliest date constrains the other's events.
    """
    coupon_class = TaxClass(
        id=COUPON_CLASS_ID,
        applies_to=frozenset({TaxableEventKind.COUPON}),
        rates=synthetic.rates(0.18, 0.05, effective_from=date(2026, 1, 15)),
    )
    disposal_class = TaxClass(
        id=DISPOSAL_CLASS_ID,
        applies_to=frozenset({TaxableEventKind.DISPOSAL_GAIN}),
        rates=synthetic.rates(DISPOSAL_PIT, DISPOSAL_LEVY, effective_from=date(2028, 1, 1)),
    )
    outcome = project.project(
        synthetic.declaration(
            tax_classes={
                TaxableEventKind.COUPON: COUPON_CLASS_ID,
                TaxableEventKind.DISPOSAL_GAIN: DISPOSAL_CLASS_ID,
            }
        ),
        synthetic.holding(cost=Money(COST_BELOW_PAR, Currency.UAH, prov.EMPTY)),
        synthetic.horizon(),
        synthetic.assumptions(),
        tax_classes={COUPON_CLASS_ID: coupon_class, DISPOSAL_CLASS_ID: disposal_class},
    )
    assert isinstance(outcome, Projection), f"expected a projection, got {outcome!r}"
    assert len(_by_class(outcome, COUPON_CLASS_ID)) == 4
    assert len(_by_class(outcome, DISPOSAL_CLASS_ID)) == 1
