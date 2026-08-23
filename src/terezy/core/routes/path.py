"""``FundingPath``: the triple that makes a per-destination cost unrepresentable.

FR-008: *access cost MUST be reported per ``(destination x stream x route)``. A cost
attributed to a destination alone MUST NOT be representable -- **not merely
discouraged**.* This module is that requirement's whole mechanism, and it is three fields
long.

**What it prevents.** ``SIMULATOR_SPEC.md`` §4.3.1's finding is that the same acquisition is
nearly free funded from USD contract income and 5-10% expensive funded from a UAH salary. A
function named ``cost_of_reaching(venue)`` reads perfectly reasonable, would pass review from
anyone not holding that finding in mind, and would blend the two into a single figure --
destroying the result while leaving every number plausible. Principle VI's rule is the one
most likely to be broken by accident rather than by intent, and a convention cannot stop
that. A missing type can: with every cost keyed by this record, "the cost of reaching
Binance" has **no type to live in**. It is not a discouraged call; it is an expression that
does not typecheck.

**Why not a required keyword argument.** Better than nothing, and still expressible: a caller
in a hurry passes a constant stream id and gets past it, which is precisely the shortcut this
exists to remove. And why not a naming convention with review? Because that is the mechanism
that already failed once in this repository -- the ``nominal_ytm`` mislabelling in feature 001
passed review and two agents (research.md D2).

**It deliberately does not carry the amount.** A path is *which way*; an amount is *how
much*. Folding the amount in would make a cost's key include the cost's own input, so two
amounts through one route would look like two paths -- and the monthly capacity accumulator,
which is keyed by route, would stop working (plan.md, post-Phase-1 note).

**The fields are keyword-only.** All three are strings, so a positional triple lets a caller
transpose the route id and the destination id and get a confidently wrong answer with no type
error anywhere. Naming them costs one line per call site and removes a class of silent
defect, which is the same trade the rest of this project makes everywhere else.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final, assert_never


@dataclass(frozen=True, slots=True, kw_only=True)
class FundingPath:
    """One way of getting money to one place from one income stream.

    All three terms required, no defaults, no optional variant, and no amount. Frozen and
    hashable because costs are keyed by it; carrying no behaviour because a method here
    would be the natural home for exactly the per-destination helper this record exists to
    make impossible (owner decision D-E).
    """

    destination_id: str
    """The venue the money is going to. A currency balance at a place -- "USD at Binance" --
    not an instrument: what is bought once the money is there is a later feature."""

    stream_id: str
    """Which income stream funds it.

    **The term that carries the finding.** The same USD acquisition funded from the USD
    contract income performs no conversion at all; funded from the UAH salary it crosses a
    P2P spread. Without this field in the key, those two are one number, and the number is
    wrong for both.
    """

    route_id: str
    """Which declared route is taken.

    Route identity is ``(provider x currency path x venue)`` rather than provider alone
    (FR-023), because the number of conversions is usually the largest difference between
    two ways of doing the same thing -- so two routes from the same provider are genuinely
    two paths and must not share a cost.
    """


# ---------------------------------------------------------------------------
# 004-composed-paths: the second kind of candidate, and the way back out
# ---------------------------------------------------------------------------
#
# FR-013: *a composed path MUST be presented as its own kind of candidate, visibly distinct from
# a hand-declared route in every ranking, report and recommendation*, and **the distinction is
# structural, not decorative**.
#
# So the type widens rather than `FundingPath` being repurposed (research.md D2). Two types
# matched with `match` is structural; a `FundingPath` whose `route_id` sometimes holds one id
# and sometimes a joined string is decorative, unparseable, and silently changes what every
# existing consumer of 002's record means. Nothing below touches `FundingPath`.


@dataclass(frozen=True, slots=True, kw_only=True)
class ComposedPath:
    """A chain of declared routes, joined at venues where the currency also matches.

    A query-time construction and never a declaration (FR-021): nothing is written back to the
    registry, so this record has no id, no file and no lifetime. What it *is* is an ordered list
    of declared route ids -- every term of every segment is the declared route's, used verbatim.

    **At least two segments.** A one-segment chain **is** a declared route and is emitted as a
    :class:`FundingPath`, so a single-element ``ComposedPath`` never exists;
    :func:`terezy.core.routes.cost.legs_of` refuses one rather than costing it, because a
    composition of one is a declared route wearing the wrong type and every report would then
    have to guess which it was looking at.

    **No amount**, for :class:`FundingPath`'s reason exactly: a path is *which way* and an
    amount is *how much*, and folding the amount in would make the key of a cost include the
    cost's own input.
    """

    destination_id: str
    """The venue the chain ends at -- the last segment's destination, and the same kind of thing
    :attr:`FundingPath.destination_id` names."""

    stream_id: str
    """Which income stream funds it. The term that carries §4.3.1's finding, and it is on this
    record for the same reason it is on ``FundingPath``: a cost keyed without it is a figure
    about nothing."""

    segments: tuple[str, ...]
    """The declared route ids, in order, from the stream's arrival venue to the destination.

    A ``tuple`` rather than a list because it is part of a key and must hash; in **declared
    order** because the order is the chain, and a set of ids would describe several different
    journeys at once.
    """


Candidate = FundingPath | ComposedPath
"""A way of reaching a destination: one declared route, or a chain of them.

Matched with ``match``, never distinguished by a flag. Every ranking, report and recommendation
holds this union, which is how FR-013's "visibly distinct" survives a refactor: a consumer that
forgets the composed case is a mypy error rather than a report that quietly prints a chain as
though someone had declared it end to end.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class Segment:
    """One declared route playing a position in a chain.

    Carries **nothing of its own** (spec, Key Entities): every term is the declared route's, used
    verbatim, so there is deliberately no field here for a fee, a cap or a window. A segment that
    could hold a number would be somewhere for a junction to charge something, and a junction
    converts nothing, charges nothing and waits for nothing.
    """

    position: int
    """0-based place in the chain. A declared route is position 0 of a chain of one, and that is
    not a special case anywhere in the code."""

    route_id: str
    """The declared route this segment **is**."""


@dataclass(frozen=True, slots=True, kw_only=True)
class DeclaredExit:
    """002's way out: one separately declared exit route, named by the inbound route's partner.

    FR-027's original shape, unchanged. The way out is its own declaration and never a reversal
    of the way in, because the exit has its own legs, its own side of every spread and its own
    limits.
    """

    route_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ComposedExit:
    """FR-012's way out: a chain of separately declared exit routes to a spendable endpoint.

    A chain of declared exit segments **satisfies** 002 FR-027 (owner decision, 2026-08-22). The
    reasoning is recorded because it cuts the other way from 002's caution and deliberately so:
    in 002 the danger was a round-trip figure resting on an exit nobody had observed -- reversing
    the inbound route -- while here every link of the chain **is** an observation, so composing
    them invents nothing. *Everything must have at least one way out*, and "a way out, at least
    through one other venue" is what this record makes real.

    At least two segments, for :class:`ComposedPath`'s reason: one declared exit route is a
    :class:`DeclaredExit`.
    """

    segments: tuple[str, ...]


class ExitByIdentity(Enum):
    """The destination **is** a declared spendable endpoint, so no exit is required.

    A single-member enum rather than ``None`` and rather than a zero-length
    :class:`ComposedExit`, and the difference it carries is a Principle I distinction: a round
    trip that costs nothing **because there is nothing to do** is a different claim from one
    whose fees happened to cancel. ``None`` would say "no exit chain"; an empty chain would say
    "a chain that charged nothing"; only a named value says *the money is already where it
    needed to come back out to*.

    ⚙ **This closes a recorded disagreement.** Feature 003's FR-002 (owner decision, 2026-08-23)
    lets a spendable destination satisfy its own exit requirement, while 002's costing required a
    declared partner and refused such a pair with ``ExitCostUnknown`` -- so coverage called ready
    what costing would not price, which 003's FR-018 says must not happen. ``features.toml``
    recorded it as ``identity-exit-vs-partner-requirement`` and named composition as the thing
    that would make it real. This is that resolution.
    """

    EXIT_BY_IDENTITY = "exit_by_identity"


EXIT_BY_IDENTITY: Final = ExitByIdentity.EXIT_BY_IDENTITY
"""The sentinel itself, so call sites read as the claim rather than as an enum lookup."""


ExitChain = DeclaredExit | ComposedExit | ExitByIdentity
"""How money gets back out, in the three shapes it can take.

Three, because they are three different claims: 002's single declared partner, FR-012's chain of
declared exit segments, and 003's destination that is already spendable. Collapsing any pair
would erase a difference the owner acts on.
"""


class FromTheDeclaration(Enum):
    """Cost the round trip through the way out the inbound declaration itself names.

    Not a way out, and not the absence of one: an instruction to read ``partner_route`` and apply
    002's FR-027 rule, including its refusal -- a route with no declared partner still yields
    ``ExitCostUnknown`` and no round-trip figure. It exists so that a caller who has not looked
    for a composed exit gets 002's behaviour **by naming it**, rather than by a default nobody
    reads.
    """

    FROM_THE_DECLARATION = "from_the_declaration"


FROM_THE_DECLARATION: Final = FromTheDeclaration.FROM_THE_DECLARATION
"""The instruction itself. See :class:`FromTheDeclaration` for why it is a value."""


ExitChoice = ExitChain | FromTheDeclaration
"""What a caller may say about the way out: a specific chain, or *use what was declared*."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Journey:
    """One way in paired with one way out: the unit a ranking orders (research.md D3).

    FR-012 says two exit chains from one destination are **two round-trip figures, never
    blended**, and FR-010 says they go in **one** ranking. Those two are only compatible if the
    exit chain is part of the ranked item's identity: a record holding several round-trip figures
    has no defined position in a ranking ordered by round-trip cost, and the first thing an
    implementer would do is pick one -- which is the blend FR-012 forbids, arrived at by accident
    rather than by decision.

    Carries no amount, and no cost. It is a key, and the figure keyed by it is a
    :class:`~terezy.core.results.ramp.RampCost`.
    """

    path: Candidate
    """The way in: a declared route or a chain of them."""

    exit_path: ExitChoice
    """The way out, or :data:`FROM_THE_DECLARATION` to use the one the inbound route names."""


def segments_of(candidate: Candidate) -> tuple[str, ...]:
    """The declared route ids a candidate is made of, in order.

    One id for a declared route, several for a chain. The uniform reading is what lets every
    consumer -- costing, regime narrowing, duplicate suppression, reporting -- treat "a declared
    route is a chain of one" as a fact rather than as a special case (research.md D7).
    """
    match candidate:
        case FundingPath():
            return (candidate.route_id,)
        case ComposedPath():
            return candidate.segments
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(candidate)


def positions_of(candidate: Candidate) -> tuple[Segment, ...]:
    """A candidate's segments, each numbered from zero in chain order.

    The numbering is derived here rather than stored, so a position and the id it names cannot
    disagree.
    """
    return tuple(
        Segment(position=position, route_id=route_id)
        for position, route_id in enumerate(segments_of(candidate))
    )


def exit_segments_of(chain: ExitChain) -> tuple[str, ...]:
    """The declared route ids an exit chain is made of, in order.

    **Empty for :data:`EXIT_BY_IDENTITY`**, and that emptiness is the claim rather than a gap:
    the destination is already a spendable endpoint, so there are no exit legs to walk and none
    to charge for. The costing side never mistakes it for "no way out", because
    :data:`EXIT_BY_IDENTITY` is a way out and ``ExitCostUnknown`` is the absence of one.
    """
    match chain:
        case DeclaredExit():
            return (chain.route_id,)
        case ComposedExit():
            return chain.segments
        case ExitByIdentity():
            return ()
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(chain)


def exit_chain_of(candidate: Candidate) -> ExitChain:
    """One enumerated way out, read as the exit chain a round trip is keyed by.

    :func:`terezy.core.routes.compose.compose` answers both directions in the same shape -- a
    tuple of candidates -- because it is the same search. This is the one-line translation on
    the way out: one segment is a :class:`DeclaredExit`, several are a :class:`ComposedExit`,
    and the two are different claims about how much was observed rather than two spellings of
    one.

    **It never returns :data:`EXIT_BY_IDENTITY`.** That case is not a chain and cannot be found
    by searching for one: it is the destination appearing in the owner's declared spendable
    list, which is a fact about his life and is his to state rather than the search's to infer.
    """
    segments = segments_of(candidate)
    if len(segments) == 1:
        return DeclaredExit(route_id=segments[0])
    return ComposedExit(segments=segments)


def candidate_id(candidate: Candidate) -> str:
    """A candidate as one string, for a ledger line's causation reference.

    A declared route is its own id, unchanged, so every event feature 002 emitted still names the
    declaration it came from. A chain is its segments joined by ``+``, in order -- because the
    charge a ledger line records is the **chain's**, not any one segment's, and naming one
    segment for a fee several of them contributed to would point a reader at the wrong
    declaration. Which segment charged what is on the cost itself, in
    :attr:`~terezy.core.results.ramp.OneWayCost.by_segment`.
    """
    return "+".join(segments_of(candidate))


def journey_of(item: Candidate | Journey) -> Journey:
    """A candidate or a journey, read as a journey.

    A bare candidate means *use the way out the declaration names* -- 002's rule, said rather
    than assumed. This exists so ranking can take both without every 002-era call site having to
    restate a rule that has not changed.
    """
    return item if isinstance(item, Journey) else Journey(path=item, exit_path=FROM_THE_DECLARATION)
