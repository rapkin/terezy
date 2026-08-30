"""What an early-exit figure rests on: that the spread quoted today still holds at the exit date.

015 FR-032. A horizon means the money comes out at its end, so an instrument whose terms run
past it is **sold** there. The price it is sold at is a declaration; whether that declaration
still describes the market on the exit date is not.

**Nobody can observe it, and that is why it is a belief rather than a term.** A platform that
committed to its quoted buyback price would have declared a *term*, and there would be no
assumption to make. The assumption exists precisely because none does -- which is also why this
record carries no citation keys: there is nothing for a source to vouch for.

**The figure it produces errs in a stated direction.** It replaces a distribution with a point
for the one option chosen for its optionality, so the early exit is reported as more certain
than it is; and the quote is a seller's, which widens exactly when a forced sale is most likely,
so the spread is understated. Rate risk is symmetric and is **not** signed. The three claims
reach a reader as this feature's typed exclusions (FR-033).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True, kw_only=True)
class SpreadHolds:
    """The owner's declared belief that an observed resale spread holds at a future exit."""

    id: str
    """Named in every outcome that rests on it, so a reader can find the file."""

    is_assumption: Literal[True]
    """Not a bool. There is no observed case, and a ``Literal`` says so where a bool invites
    one -- ``FundDeclaration.is_assumption_driven``'s reading."""

    rationale: str
    """Why the owner is willing to assume it, in his own words. Required and non-empty."""


def rests_on(assumption: SpreadHolds) -> str:
    """How an outcome computed through the belief names it in ``TupleOutcome.rests_on``.

    One place, because that field is what SC-025's walk reads: a sentence composed at each site
    would let one site quietly stop saying it while the walk kept passing on the others.
    """
    return (
        f"the observed resale spread is assumed to hold at the exit date ({assumption.id}): "
        f"{assumption.rationale}"
    )


__all__ = ["SpreadHolds", "rests_on"]
