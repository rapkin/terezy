"""The single project tolerance. Every comparison of money imports it from here.

FR-002: *each cash flow MUST reproduce hand-computed arithmetic within a single
project-wide precision tolerance that is defined in exactly one place. No individual
comparison may define its own tolerance; one that requires a looser tolerance MUST state
why where the comparison is made.* The constitution puts it in Principle IV and calls a
test that invents its own tolerance a defect.

**Why a tolerance exists at all.** Money is float64 (owner decision D-A), so the
specification's "reproduces a hand-computed schedule exactly" cannot be taken
literally: a schedule accumulated in binary floating point and the same schedule worked
out on paper will differ in the last bits. The tolerance is the width of that
irreducible gap, and nothing else. It is not slack for a modelling disagreement, and a
comparison that only passes because the tolerance absorbed a real difference is a
defect wearing a green tick.

**Why it must be one value.** Each local tolerance is defensible on its own and
invisible in aggregate. Twenty of them, each a little looser than needed, and the suite
no longer distinguishes "the arithmetic is right" from "the arithmetic is close". Having
exactly one means loosening it is a visible, reviewable act.

**What is deliberately *not* comparable this way.** Determinism. C4 asserts
bit-identity through ``float.hex()`` in the canonical form, which is stricter than this
tolerance on purpose: the tolerance exists because hand arithmetic and float arithmetic
differ, whereas determinism means the same code on the same inputs must produce the same
bits. Conflating the two would let genuine nondeterminism hide inside the tolerance band
(research.md D5).

**If you need a looser bound**, pass ``tolerance=`` explicitly and say why at the
assertion site. The keyword is the sanctioned escape hatch precisely because it is
noisy: it appears in the diff, next to a justification. Writing ``pytest.approx``,
``math.isclose`` with a bound of your own, or a bare numeric literal is not.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

from terezy.core.primitives.money import Money

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Sequence

TOLERANCE: Final[float] = 1e-9
"""The project tolerance: relative and absolute, both ``1e-9``.

Chosen as roughly four decimal orders above float64's ~1e-16 relative resolution, which
leaves room for the accumulated rounding of a schedule of tens of cash flows while
staying far tighter than any amount of money anyone would notice. On a balance of one
million hryvnia that is a bound of ``1e6 * 1e-9 = 0.001`` UAH -- a tenth of a kopiyka,
indistinguishable from exact for a decision, and nowhere near loose enough to hide a
modelling error.
"""


def is_close(left: float, right: float, *, tolerance: float = TOLERANCE) -> bool:
    """Whether two numbers agree to within the project tolerance.

    Applied as both a relative and an absolute bound. Relative alone would be uselessly
    tight near zero -- a balance that should be zero and lands on ``1e-17`` would fail --
    and absolute alone would be uselessly loose on large balances relative to small ones.
    """
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def assert_money_close(left: Money, right: Money, *, tolerance: float = TOLERANCE) -> None:
    """Assert two amounts are the same money, currency included.

    The currency check is the reason this exists rather than callers reaching for
    :func:`is_close` on ``.amount``. Comparing bare amounts would let a UAH figure match
    a USD one whose number happened to agree -- a currency conflation dressed as a
    passing tolerance check, and Principle VI's exact prohibition.

    Raises ``AssertionError`` rather than using an ``assert`` statement, so the check
    survives ``python -O``: a financial invariant that evaporates under an optimisation
    flag is not an invariant.
    """
    if left.currency is not right.currency:
        raise AssertionError(
            f"currency mismatch in a tolerance comparison: "
            f"{left.currency.value} vs {right.currency.value}. These are not the same "
            "money and no tolerance makes them so."
        )
    if not is_close(left.amount, right.amount, tolerance=tolerance):
        raise AssertionError(
            f"{left.amount!r} and {right.amount!r} {left.currency.value} differ by "
            f"{abs(left.amount - right.amount)!r}, which exceeds the tolerance "
            f"{tolerance!r}"
        )


def tied_groups(ordered: Sequence[float]) -> tuple[tuple[int, ...], ...]:
    """Groups of indices whose values agree within the project tolerance, over a sorted run.

    **Anchored, not chained.** Tolerance equality is not transitive -- ``a ~ b`` and ``b ~ c``
    does not give ``a ~ c`` -- so a rule has to be picked, and chaining neighbour to neighbour
    would let a band of arbitrary width become one tie as entries accumulate. That is the
    tolerance absorbing a real difference, which is the defect this module's own docstring
    warns about. Comparing each member against the group's **first** bounds every reported tie
    at one tolerance wide.

    Requires the sequence to be ordered, so tied entries are adjacent and one pass suffices.
    Groups of one are not ties and are not reported.

    ⚙ **One copy, and it is here rather than in either caller.** This loop lived twice -- once
    over round-trip costs and once over tuple returns -- and two implementations of "what
    counts as a tie" that drifted apart would report a strict winner in one comparison and a
    tie in the other, over the same two numbers. It sits beside :data:`TOLERANCE` because the
    rule *is* the tolerance rule; the callers supply the figures they order by.
    """
    groups: list[tuple[int, ...]] = []
    current: list[int] = []
    anchor: float | None = None
    for index, value in enumerate(ordered):
        if anchor is not None and is_close(value, anchor):
            current.append(index)
            continue
        if len(current) > 1:
            groups.append(tuple(current))
        anchor = value
        current = [index]
    if len(current) > 1:
        groups.append(tuple(current))
    return tuple(groups)
