"""What the token a price is quoted in is worth in real money, and whose belief that is.

025 Clarification 1, answered by the owner on 2026-09-07: «прирівнюй до долара». The price this
repository can fetch is `BTCUSDT`, and every hryvnia figure downstream needs dollars. That one
USDT is one USD is a **belief**, not an observation: the peg holds by the issuer's practice
rather than by any obligation somebody published, so there is nothing for a source to vouch for
and the record carries `is_assumption` and a reason where an observation carries a citation.

**It is never a silent equality.** With no belief declared the dollar figure does not appear --
it refuses by name. That is what makes swapping this for a cited USDT/USD observation a change
to a data file and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True, kw_only=True)
class QuoteAssetIsWorth:
    """The owner's declared belief that one unit of a quote asset is one unit of a currency."""

    id: str
    """Named on every figure struck through it, so a reader can find the file."""

    quote_asset: str
    """The token a venue quotes in -- ``USDT``. Matched against the symbol's own tail by the
    data layer, which is the only place that holds both."""

    currency: str
    """The currency it is taken to equal, as a code. A string rather than the enum, because the
    belief is about a *token* and the loader is what resolves the pair."""

    is_assumption: Literal[True]
    """Not a bool. There is no observed case here -- a cited rate would be an observation and a
    different declaration -- and a ``Literal`` says so where a bool invites one."""

    rationale: str
    """Why the owner is willing to assume it, in his own words. Required and non-empty."""


def rests_on(belief: QuoteAssetIsWorth) -> str:
    """How a figure struck through the belief names it, composed in one place.

    One place, because a sentence composed at each site would let one site quietly stop saying
    it while a walk over the others kept passing -- ``scenarios.quotation.rests_on``'s reason.
    """
    return (
        f"one {belief.quote_asset} is assumed to be one {belief.currency} "
        f"({belief.id}): {belief.rationale}"
    )


__all__ = ["QuoteAssetIsWorth", "rests_on"]
