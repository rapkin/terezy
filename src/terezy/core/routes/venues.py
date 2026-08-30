"""A venue: a place money can sit, and the currencies it can hold.

A bank account, an exchange account, a broker account, a fund platform. Declared data with
no behaviour of its own -- the record exists so that a leg's endpoints are *named things
with stated capabilities* rather than free strings, and so that "this leg moves dollars into
a hryvnia-only account" is a question something can answer.

**Why the currency set is on the venue and not inferred from the legs that touch it.** A
route declaration is written by hand, and the mistake it invites is a leg that moves a
currency its endpoint cannot hold -- a USD transfer into a UAH-only card account. Inferring
the venue's capabilities from the legs would make that mistake self-justifying: the leg
declaring the impossible movement would be the evidence that it was possible. Declaring the
capability separately means the two statements can disagree, and the resolver reports it
naming the file and the leg index (FR-024).

**No behaviour beyond a membership test**, per owner decision D-E. The check lives here
rather than in the resolver so that the *question* is asked in the same words wherever it is
asked; the resolver supplies the file and the field, which is knowledge this module does not
have and must not acquire.
"""

from __future__ import annotations

from dataclasses import dataclass

from terezy.core.primitives.currency import Currency


@dataclass(frozen=True, slots=True)
class Venue:
    """One place money can sit. Curated, shared, declared data."""

    id: str
    """Unique across every venue declaration; a duplicate is a load-time failure."""

    name: str
    """Human-readable, non-empty. For a synthetic fixture it says so in words."""

    currencies: frozenset[Currency]
    """The currencies this venue can hold. Non-empty.

    A ``frozenset`` of the enum rather than of strings: a misspelt currency is a load-time
    failure at the boundary rather than a fourth currency that quietly never matches
    anything (``primitives.currency``).
    """


def can_hold(venue: Venue, currency: Currency) -> bool:
    """Whether this venue can hold this currency.

    Deliberately a plain predicate returning a ``bool`` rather than a raising check: the
    caller that knows *which file and which leg index* asked the question is the one that
    must build the error message (FR-024), and it lives in the data layer where this
    module may not reach.
    """
    return currency in venue.currencies
