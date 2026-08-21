"""Where a number came from, and the monoid that carries it through every figure.

This module is the mechanism behind FR-015 -- *a value with an empty verification date
MUST be marked as unverified, and every figure computed from it MUST carry that mark* --
and behind the constitution's Principle I clause that a derived figure losing its
parent's mark is a defect. The constitution puts that failure in its top severity class,
and no gate can detect it, which is exactly why the mechanism has to be structural.

The structure is a commutative monoid:

* the carrier is ``Provenance``, a frozenset of ``SourceRef``;
* the operation is :func:`merge`, which is set union -- associative and commutative, so
  **evaluation order can never change a mark**;
* the identity is :data:`EMPTY`, used for a literal that came from no source at all.

Those three properties are what make the mark safe to propagate mechanically. If
``merge`` were order-dependent, ``a + (b + c)`` and ``(a + b) + c`` could disagree about
whether a figure rests on an unverified input, and the mark would become a fact about
the code path rather than about the data. They are asserted in
``tests/unit/test_provenance_monoid.py``.

The asymmetry in :func:`is_unverified` is deliberate: **one** unverified source taints
the whole figure. A figure is only as trustworthy as its least-trustworthy input, and
the alternative -- marking only when *every* input is unverified -- would let a single
invented number hide behind a crowd of cited ones.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Final


@dataclass(frozen=True, slots=True)
class SourceRef:
    """One cited origin for one or more observed values.

    A record carrying only data; ``is_verified`` is a free function below rather than a
    property, per owner decision D-E.
    """

    id: str
    """Stable and unique within a run.

    Derived by the loader from the declaring file and table, so a figure can be traced
    back to where it was declared rather than merely to a citation string.
    """

    citation: str
    """A URL or document reference. Non-empty -- enforced at the data boundary."""

    retrieved_on: date
    """When the value was read from the source. Required."""

    verified_on: date | None
    """When the value was checked against a primary source, or ``None``.

    ``None`` is permitted and expected -- the headline OVDP yield enters the system
    unverified and the first figure this tool produces therefore carries a mark
    (spec.md, Assumptions). What is *not* permitted is the key being absent from the
    declaration: FR-014 requires the field to be present and allows it to be empty, so
    that "nobody has verified this" is a recorded state rather than an oversight.
    """


@dataclass(frozen=True, slots=True)
class Provenance:
    """The set of sources a figure rests on.

    A frozenset rather than a sequence because provenance is a *set* of facts: the same
    source contributing twice to a sum says nothing more than it contributing once, and
    duplicate-sensitivity would make the mark depend on the shape of the arithmetic.
    """

    sources: frozenset[SourceRef]


EMPTY: Final[Provenance] = Provenance(frozenset())
"""The identity of :func:`merge`: a figure resting on no cited source.

Used for a literal that genuinely came from nowhere -- a zero, a count, the starting
balance of an empty account. It is **not** a stand-in for "source unknown": a declared
value must never be given ``EMPTY``, because that launders an unverified input into an
apparently unmarked figure. That is the one hole in this design and it is guarded by
``tests/contract/test_money_construction_guard.py`` plus manual review.

Note that ``EMPTY`` is *not* unverified. A sum of nothing is not resting on an
unverified observation; it is resting on nothing, and claiming otherwise would make the
mark meaningless by making it universal.
"""


def of(refs: Iterable[SourceRef]) -> Provenance:
    """Provenance from the sources it rests on."""
    return Provenance(frozenset(refs))


def is_verified(ref: SourceRef) -> bool:
    """Whether this source has been checked against a primary source."""
    return ref.verified_on is not None


def merge(left: Provenance, right: Provenance) -> Provenance:
    """Union two provenances. Associative, commutative, with :data:`EMPTY` as identity.

    Called by every combining function in ``terezy.core.primitives.money``. Those are
    the only way to combine money, so this is the only place the mark needs to be
    carried -- and therefore the only place it could be dropped.
    """
    return Provenance(left.sources | right.sources)


def merge_all(items: Iterable[Provenance]) -> Provenance:
    """Fold :func:`merge` over many provenances, starting from :data:`EMPTY`."""
    merged = EMPTY
    for item in items:
        merged = merge(merged, item)
    return merged


def is_unverified(prov: Provenance) -> bool:
    """Whether **any** source behind this figure lacks a verification date.

    One unverified input taints the result. See the module docstring for why the
    asymmetry is the intended one.
    """
    return any(not is_verified(ref) for ref in prov.sources)


def unverified_sources(prov: Provenance) -> frozenset[SourceRef]:
    """The specific sources responsible for the mark, so it can name *why*.

    A mark that cannot say which input it rests on is the run-scoped taint flag
    rejected in research.md D2: cheap, unfalsifiable, and useless to the owner.
    """
    return frozenset(ref for ref in prov.sources if not is_verified(ref))
