"""The vocabulary a question is written in: declared labels an instrument declares itself into.

015 FR-007a. The owner asks about *OVDP* and *Inzhur*, and neither is an instrument id. A group
is a **declared label** and never a rule: an instrument says which groups it is in, this record
says which groups exist, and nothing computes membership from a class, an id prefix, a tax class
or the venue an instrument is bought at. All four of those look right on today's registry and
all four are wrong -- see the specification's FR-007a for each near-miss.

Curated rather than per-owner, and the label lives on the curated instrument declaration: a
curated file that referenced a per-owner one would fail to load because somebody else's
vocabulary was absent.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class InstrumentGroup:
    """One declared group id, and what to call it.

    Carries no membership. Membership is on the instruments, which is what makes a new issue
    join a group by carrying the label rather than by an edit here (FR-007's 016 argument).
    """

    id: str
    """What a question names. The whole of the record's meaning."""

    name: str
    """For a reader. Nothing dispatches on it."""


__all__ = ["InstrumentGroup"]
