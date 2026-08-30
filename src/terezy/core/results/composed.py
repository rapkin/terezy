"""What an enumeration of composed candidates is, and what a refusal to enumerate one is.

FR-007 requires the bound in force to be recorded alongside the results, and that is why this
module exists at all: a bare tuple of candidates cannot say how far the search was allowed to
look, and "you have not declared that corridor" and "you told me not to look that far" are
different findings the owner acts on differently.

**An empty candidate tuple is a legitimate answer.** It means the registry declares nothing that
connects, which is a real fact and the coverage report's news to deliver (feature 003), not this
feature's gap to fill. :class:`CompositionRefused` is a *different* claim -- the question could
not be asked -- and the two are unrelated types so a caller cannot read one as the other. That is
the same shape as ``RoundTripCost | ExitCostUnknown`` one level down, and the reasoning is the
same: an empty result and a refusal look identical to anyone who only counts rows.

**Nothing here is costed.** There is no figure on any record below, and no field a partial cost
could be cached in -- see :mod:`terezy.core.routes.compose` for why a partial cost would be an
invented number the first time it was reused.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from terezy.core.routes.path import Candidate


@dataclass(frozen=True, slots=True, kw_only=True)
class SegmentBound:
    """How many declared routes may be chained into one candidate. Declared, never inferred.

    FR-006: the bound is data. It has no default here and none at the data boundary, because a
    forgotten line must never read as a chosen policy -- the rule that refuses a default
    staleness threshold (002 FR-028), applied to the one knob this feature adds.

    Carries no ``owner_id``: the owner is a property of the *file* the bound was declared in and
    is checked there, so putting him on the record would be one fact in two places.
    """

    max_segments: int
    """At least one. **One means composition is off** -- only declared routes are candidates,
    which is a legal choice and the explicit way to disable it. Zero admits nothing at all,
    including declared routes, and is refused at load as a broken registry rather than read as
    a way to turn the feature off."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Enumeration:
    """Every candidate the declarations connect, for one question, with the bound that shaped it.

    **:class:`SegmentBound` lives here rather than in the module that enumerates with it**,
    which is a departure from data-model.md and a cycle rather than a preference. ``compose``
    returns this record, so it imports this module; had the bound stayed there, this module
    would have had to import back. The bound also *belongs* here on its own merits -- FR-007
    says it is recorded **alongside the results**, so it is half of what an enumeration means --
    and it follows the pattern ``results/coverage.py`` already sets, where ``Destination`` and
    ``SpendableEndpoint`` are inputs to the audit declared beside its output.
    """

    candidates: tuple[Candidate, ...]
    """Every declared route and every composed chain that connects, sorted by
    ``(segment count, route ids)``.

    **Sorted rather than emitted in walk order** (FR-008). The order a depth-first search visits
    things in is a property of the walk, and a reported order that depended on it would let a
    change to the walk move a ranking. Sorting by segment count first also puts declared routes
    ahead of every composition, which is what makes the duplicate rule keep the declared route
    where a chain reproduces one leg for leg (FR-009).

    **May be empty**, and that means "nothing connects" -- see the module docstring.
    """

    bound: SegmentBound
    """The bound in force when these candidates were enumerated (FR-007).

    Travels with the answer because it is half of what the answer means. Without it, a corridor
    that needs four segments under a bound of three is indistinguishable from a corridor nobody
    declared -- and the owner's remedy for the two is opposite: raise the bound, or write a
    declaration.
    """

    regime_id: str
    """The single regime whose route set every segment belongs to (FR-017).

    An id rather than the regime record, deliberately: the costing engine has never heard of a
    regime, and carrying the belief into the search would let an assumption arrive in the same
    shape as an observation. What is recorded here is the *fact* of which world was searched, so
    a reader can reproduce it.
    """


class Unaskable(Enum):
    """Which of the three questions could not be asked, as a value rather than as a sentence.

    A closed set beside :attr:`CompositionRefused.reason` rather than instead of it: the words
    are for a reader and this is for a caller, and the two halves fail differently. A sentence
    edited for clarity must not change what any caller does, and today it would -- the only way
    to tell the three apart was to search the text for a substring.

    The distinction is worth a field because the remedies are **opposite**.
    :attr:`BOUND_ADMITS_NOTHING` and :attr:`NO_SPENDABLE_ENDPOINT` are about the *question* and
    are answered by changing it; :attr:`ALREADY_ARRIVED` is about one
    ``(stream, destination)`` pair and is answered by nothing at all, because the money is
    already where it was wanted. A caller that read the second as the first would report a
    corridor nobody declared where the registry is complete.
    """

    BOUND_ADMITS_NOTHING = "bound_admits_nothing"
    """The declared segment bound is below one, so no candidate is admissible at all."""

    NO_SPENDABLE_ENDPOINT = "no_spendable_endpoint"
    """An exit enumeration was asked for and the owner has declared nowhere money counts as
    spent, so a chain has nowhere to end."""

    ALREADY_ARRIVED = "already_arrived"
    """The stream already arrives, in the currency asked for, at the destination asked for."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CompositionRefused:
    """No enumeration was produced, and this says why. Returned *instead of* an
    :class:`Enumeration`.

    Not an error and not a failure -- a valid, honest occupant of a slot whose value is genuinely
    unavailable, exactly as ``ExitCostUnknown`` occupies the round-trip slot. What it marks is a
    question that does not stand up: a bound that admits nothing, an exit chain with nowhere
    declared to end, a destination the money has already arrived at.

    **It is not "no candidates".** That answer is an :class:`Enumeration` with an empty tuple,
    and conflating the two would report a registry gap where the registry is fine.
    """

    case: Unaskable
    """Which of the three fired. See :class:`Unaskable` for why this is a field and not a
    reading of :attr:`reason`."""

    reason: str
    """Why no enumeration was produced, in the output's own words -- naming the input that did
    not stand up, so the remedy is obvious from the output alone."""

    destination_id: str
    """The venue that was asked about."""

    stream_id: str
    """The stream that was asked about. Present for the same reason every cost carries it: a
    statement about reaching a place, with no stream in it, is a statement about nothing."""
