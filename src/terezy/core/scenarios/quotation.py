"""What a dated quotation is worth on another day, and the owner's belief that makes it one.

015 FR-032, widened by 022 FR-017. A quotation is a **declaration observed on one day**;
whether it still describes the market on the day a price is wanted is not. Both legs of a
round trip lean on it -- the buy quotation carried to the purchase date and the sell quotation
carried to the sale date -- so the belief is not the early exit's and is not named for it.

**Nobody can observe it, and that is why it is a belief rather than a term.** A platform that
committed to its quoted price would have declared a *term*, and there would be no assumption to
make. The assumption exists precisely because none does -- which is also why this record carries
no citation keys: there is nothing for a source to vouch for.

**What it does not account for** reaches a reader as this feature's typed exclusions rather
than as prose here (015 FR-033, 022 FR-020; ``core.results.answer.Exclusion``, where each claim
carries its own warrant for having a sign or not having one).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True, kw_only=True)
class QuotationHolds:
    """The owner's declared belief that an observed quotation's clean price holds."""

    id: str
    """Named in every outcome that rests on it, so a reader can find the file."""

    is_assumption: Literal[True]
    """Not a bool. There is no observed case, and a ``Literal`` says so where a bool invites
    one -- ``FundDeclaration.is_assumption_driven``'s reading."""

    rationale: str
    """Why the owner is willing to assume it, in his own words. Required and non-empty."""


def rests_on(assumption: QuotationHolds) -> str:
    """How an outcome priced through the belief names it in ``TupleOutcome.rests_on``.

    One place, because that field is what SC-025's walk reads: a sentence composed at each site
    would let one site quietly stop saying it while the walk kept passing on the others.
    """
    return (
        f"the clean price implied by the observed quotation is assumed to hold on the date it "
        f"is carried to, with interest accruing linearly within each declared coupon period "
        f"({assumption.id}): {assumption.rationale}"
    )


__all__ = ["QuotationHolds", "rests_on"]
