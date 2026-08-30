"""The candidate set, the three columns it accounts for, and the refusals that replace it.

014 FR-008: an enumeration separates and separately counts **three** populations -- candidates
evaluated, candidates dropped with a typed reason, and ``(instrument, stream)`` pairs that
yielded no candidate at all. The third is the one nothing before this feature had a place for,
and the one a reader would otherwise fold into the second and divide by.

**Nothing here holds a figure this feature computed.** Every amount and rate reachable from a
candidate came out of feature 010's ``evaluate``; both route terms came out of feature 004's
``compose``. This module's own content is the accounting.

Frozen records, free functions, tagged unions matched with ``match``. Formatting is not a
result: the core chooses nothing about what a reader sees (Principle III), which is why the
dropped set is carried whole rather than summarised (FR-010).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidateCeiling:
    """How many candidates one enumeration may produce. Declared, never inferred.

    FR-019: the ceiling is data with no default, on the precedent of 004's ``SegmentBound`` and
    002's staleness threshold -- a forgotten line must never read as a chosen policy.

    **Exceeding it refuses; it never truncates.** A truncated set answers a different question
    from the one asked, with an audit trail that looks impeccable, and the ceiling exists to say
    *the enumeration primitive has stopped being the right one for this registry* -- which is a
    finding the owner acts on and a silent cap would hide.

    Carries no ``owner_id``: the owner is a property of the *file* the ceiling was declared in
    and is checked there, so putting him on the record would be one fact in two places.
    """

    max_candidates: int
    """At least one. Zero would refuse every question with the registry blameless."""
