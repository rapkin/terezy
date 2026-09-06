"""``slack`` is the width :func:`is_close` allows, and not a second closeness rule.

019 FR-011c needs the width of the project comparison as a **value**: a refusal has to name
what a declared band failed to clear, and a floor has to be measured against it. Two functions
that could disagree about how wide the tolerance is would be the second tolerance policy
Principle IV forbids, so the agreement is asserted over generated pairs rather than obtained by
construction -- ``is_close`` is not rewritten in terms of ``slack``, because ``math.isclose``
and ``abs(left - right)`` part company on non-finite inputs (research D3).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from terezy.core.primitives.tolerance import TOLERANCE, is_close, slack

pytestmark = pytest.mark.invariant

FINITE = st.floats(allow_nan=False, allow_infinity=False, width=64)


@given(left=FINITE, right=FINITE)
def test_the_width_decides_exactly_what_is_close_decides(left: float, right: float) -> None:
    assert is_close(left, right) == (abs(left - right) <= slack(left, right))


@given(left=FINITE, right=FINITE)
def test_the_width_is_symmetric(left: float, right: float) -> None:
    """An asymmetric width would make FR-011's indistinguishability asymmetric with it."""
    assert slack(left, right) == slack(right, left)


@given(left=FINITE, right=FINITE)
def test_the_width_is_never_below_the_absolute_bound(left: float, right: float) -> None:
    """The tolerance is relative *and* absolute, so its width never falls below the constant.

    This is what FR-011c's floor rests on, and why a floor written in units of ``1e-9`` would
    guarantee nothing: at money scale the width is orders of magnitude above it.
    """
    assert slack(left, right) >= TOLERANCE


def test_the_width_is_the_relative_bound_where_the_figures_are_large() -> None:
    """One worked figure, so the relative half is pinned by arithmetic rather than by a property.

    On 50 000 UAH the width is ``1e-9 * 50000 = 5e-5`` -- five hundredths of a kopiyka, and
    five orders of magnitude above the constant an implementer would otherwise write.
    """
    assert slack(50_000.0, 49_999.0) == TOLERANCE * 50_000.0
    assert slack(0.5, -0.25) == TOLERANCE
