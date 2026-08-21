"""``scale_sourced``: the one way a *declared factor* keeps its sources.

``money.scale`` multiplies by a dimensionless factor and carries only the amount's own
provenance, which is right for a factor that is arithmetic -- a lot fraction, a sign, a
count of units. It is wrong, silently, for a factor that came from data: a declared tax
rate or a declared coupon rate has sources of its own, and ``scale`` would drop them.
Dropping them is FR-015's top-severity defect, and it is invisible: the figure comes out
looking as trustworthy as the amount it was scaled from.

So the declared-factor case has its own function, and the sources are a **required**
argument. That is the whole design: a caller cannot reach for it and forget them, and a
reviewer checking FR-015 reads two short functions rather than auditing every
multiplication in the codebase.

The property that makes the mark safe is **monotonicity**. Nothing anywhere removes a
source; provenance only ever grows as a figure is derived. So a mark cannot be laundered
out of a chain of arithmetic, and the asymmetry in ``is_unverified`` -- one unverified
input taints the result -- holds all the way to the last figure.
"""

from __future__ import annotations

from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import SourceRef

UAH = Currency.UAH

VERIFIED = SourceRef(
    id="verified",
    citation="a checked source",
    retrieved_on=date(2026, 8, 21),
    verified_on=date(2026, 8, 21),
)

UNVERIFIED = SourceRef(
    id="unverified",
    citation="an unchecked source",
    retrieved_on=date(2026, 8, 21),
    verified_on=None,
)

AMOUNT = Money(1000.0, UAH, prov.of([VERIFIED]))

AMOUNTS = st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False)
FACTORS = st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False)


def test_the_factors_sources_reach_the_product() -> None:
    scaled = money.scale_sourced(AMOUNT, 0.18, prov.of([UNVERIFIED]))
    assert VERIFIED in scaled.provenance.sources
    assert UNVERIFIED in scaled.provenance.sources


def test_an_unverified_factor_marks_a_verified_amount() -> None:
    """The case the function exists for: a cited rate applied to a checked figure."""
    assert not prov.is_unverified(AMOUNT.provenance)
    scaled = money.scale_sourced(AMOUNT, 0.18, prov.of([UNVERIFIED]))
    assert prov.is_unverified(scaled.provenance)


def test_plain_scale_would_have_dropped_the_factors_sources() -> None:
    """Stated as a test so the difference between the two functions is not folklore."""
    assert money.scale(AMOUNT, 0.18).provenance == AMOUNT.provenance
    assert UNVERIFIED not in money.scale(AMOUNT, 0.18).provenance.sources


def test_a_zero_factor_still_carries_the_factors_sources() -> None:
    """An exempt rate is a zero *factor*, and the zero it produces must cite the rule.

    This is the exact shape of the exemption: ``base x 0.0`` from a class whose source
    says why the rate is zero. A product that lost the citation would be a zero
    indistinguishable from a rule that never ran.
    """
    scaled = money.scale_sourced(AMOUNT, 0.0, prov.of([UNVERIFIED]))
    assert scaled.amount == 0.0
    assert UNVERIFIED in scaled.provenance.sources


@given(amount=AMOUNTS, factor=FACTORS)
def test_the_amount_is_the_plain_product(amount: float, factor: float) -> None:
    scaled = money.scale_sourced(
        Money(amount, UAH, prov.of([VERIFIED])), factor, prov.of([UNVERIFIED])
    )
    assert scaled.amount == amount * factor
    assert scaled.currency is UAH


@given(factor=FACTORS)
def test_provenance_only_ever_grows(factor: float) -> None:
    """Monotonicity: the operand's sources are always a subset of the product's."""
    scaled = money.scale_sourced(AMOUNT, factor, prov.of([UNVERIFIED]))
    assert AMOUNT.provenance.sources <= scaled.provenance.sources


def test_empty_sources_leave_the_provenance_unchanged() -> None:
    """``EMPTY`` is the identity of the merge, so this degenerates to ``scale``."""
    assert (
        money.scale_sourced(AMOUNT, 2.0, prov.EMPTY).provenance
        == money.scale(AMOUNT, 2.0).provenance
    )
