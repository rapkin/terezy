"""What the declared route graph can and cannot support: the coverage report's records.

FR-001, FR-003, FR-007, FR-009, and FR-017 -- the rule that makes this module unusual:
**the output carries no cost figures at all.**

``results/ramp.py`` is this module's sibling and its precedent: frozen records carrying data,
free functions in ``core/routes/`` computing them. What follows are the decisions the *shapes*
here carry rather than leaving to a rule a reader has to remember.

**No field can hold a number that came from money.** Not one record below has a ``Money``, a
``Provenance``, a ``StalenessVerdict`` or a bare ``float`` in it. Integers -- counts and
indices -- are the only quantities. That is FR-017 and FR-023 made structural rather than
conventional, and ``tests/contract/test_coverage_no_figures.py`` asserts it by walking
``dataclasses.fields`` over the whole returned report rather than by sampling it (research.md
D12). It has a consequence worth stating out loud: **this feature imports no tolerance and
defines none**. There is nothing here to compare within one, and a tolerance appearing in this
package would mean a number had leaked into the report.

**A missing declaration carries no regime, deliberately** (research.md D8). FR-014 wants the
same hole in two regimes to be *recognizably one declaration*, and value equality between two
frozen records is the cheapest possible form of that. A regime field would make them unequal
and leave the reader to normalise by hand. The regime is the block the declaration appears in,
and :class:`Observation` states the per-regime counts as pairs that are **never summed**.

**A pair can carry two deficits at once** (research.md D7). FR-003 names its second kind
"inbound exists but no exit partner", but the spec's own "missing both" edge case and FR-011
require both missing declarations to be listed. So kinds 2 and 3 classify the *exit* side and
the inbound side is reported independently: a pair missing both halves reports both, and each
is marked not alone sufficient. The three deficits stay distinguished, which is what FR-003 is
actually protecting; what is widened is only the phrase, not the intent.

**Nothing here can hold a composed path.** There is no field for a chain, no field for a
reversed route, and no "reachable by composition only" annotation. That is FR-006 and FR-018's
forward note kept out of the type system rather than out of a code review: a two-hop way out is
a hole in *this* feature, and feature 004 adds its annotation **beside** the verdict rather
than by changing what :class:`Ready` means.

**Where these records live, against what data-model.md says.** ``data-model.md`` heads
:class:`SpendableEndpoint` and :class:`Destination` with ``core/routes/coverage.py``. They are
defined here instead, with every other record, because ``core/routes/coverage.py`` *builds*
:class:`Ready`, :class:`NotReady` and :class:`CoverageReport` -- so defining the two inputs
there and importing the outputs from here would be an import cycle. Both modules re-export
what they use, so ``from terezy.core.routes.coverage import Destination`` still resolves and
the document's intent survives. This is the same split ``cost.py`` and ``results/ramp.py``
already have, where ``RouteUnusable`` is an outcome living beside the results.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final, Literal

from terezy.core.primitives.currency import Currency
from terezy.core.routes.legs import RouteDirection, RouteStatus

IMPLICIT_REGIME_ID: Final = "(no regime declared)"
"""The id of the single regime the report covers when the owner declared none (FR-015).

Parenthesised on purpose: it is not a valid-looking identifier anywhere else in the registry,
so it reads as a statement rather than as something the owner wrote. The *structural* form of
the same fact is :attr:`RegimeCoverage.source`, so no consumer has to string-match this id --
and a declared regime carrying it is refused as :class:`ReservedRegimeId` rather than silently
shadowed, because "MUST say that this is what it did" is not satisfied by a block the owner
cannot tell apart from his own (research.md D14).
"""

ENFORCEMENT: Final = (
    "ADVISORY, not binding (owner decision, 2026-08-22). These verdicts inform; they change "
    "nothing. Producing this report has no effect on any costing or ranking output, so a "
    "destination whose only declared exit does not reach a spendable endpoint still appears "
    "in the round-trip ranking while this report says it should not be compared. That gap is "
    "deliberate and dated: the owner's rule -- everything money can be moved into must have a "
    "declared way in AND a declared way out before it may appear in any comparison -- remains "
    "the destination, and making it binding is a recorded deferral to a later feature, not a "
    "softer reading of the rule."
)
"""FR-019's sentence, carried in the report's own output rather than only in the spec.

One place, so every rendering says it the same way and none of them can leave it out. On the
precedent of ``regimes.stated_assumption`` and ``RouteUnusable.reason``: a plain-language
statement of a conditional outcome is data beside the rule that produced it, for an output
layer to render, not rendering of its own.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class SpendableEndpoint:
    """A declared ``(venue x currency)`` where money counts as having come back out.

    Declared data, never a built-in constant (FR-004): base currency only, at the specific
    venues the owner actually spends from. Not "UAH anywhere", and not foreign cash in hand.
    An exit ending in hryvnia at a venue this list does not name is deficit 3, exactly as one
    ending in dollars is -- and changing the list changes those verdicts with no source-code
    change, which is what ``tests/contract/test_coverage_data_only.py`` measures.
    """

    venue_id: str
    """A declared venue. The loader refuses one nobody declared, and one that cannot hold
    :attr:`currency`."""

    currency: Currency
    """The base currency the declarations were resolved against. A spendable endpoint in a
    foreign currency would be the report quietly deciding that foreign cash counts as spent,
    so the resolver refuses it (FR-004)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Destination:
    """A currency balance at a venue -- feature 002's shape, and the report's unit of audit.

    **Derived, never declared** (FR-001 ⚙, research.md D5): the universe is every declared
    venue times every currency that venue declares it can hold. That is what makes a venue with
    zero routes visible as a hole *the moment it is declared*, rather than invisible until
    somebody tries to cost it. Building the universe from the routes instead is the way to lose
    exactly the holes this report exists to find.
    """

    venue_id: str

    currency: Currency


@dataclass(frozen=True, slots=True, kw_only=True)
class RouteRelied:
    """One declaration a verdict rests on, with the status it was declared under.

    The status travels with the id because FR-022 counts a closed route as *declared* -- the
    hole this report surfaces is a corridor nobody has observed, and a closed route is already
    observed. But a ready verdict resting only on closed routes must not look identical to one
    resting on open ones, which is what :attr:`Ready.rests_on` is derived from.
    """

    route_id: str

    status: RouteStatus


class SatisfiedByArrival(Enum):
    """The inbound slot, filled by the fact that the money is *born* at the destination.

    A distinct sentinel rather than an empty tuple, because FR-005 requires "satisfied by
    arrival" to be explicitly distinct from "satisfied by a route", and an empty tuple reads as
    *nothing relied on* -- which is a different claim, and the one a not-ready pair makes.

    A single-member ``Enum`` rather than a bare object so the union below is expressible and a
    ``match`` over it is exhaustive under a strict type checker.
    """

    SATISFIED_BY_ARRIVAL = "satisfied_by_arrival"


SATISFIED_BY_ARRIVAL: Final = SatisfiedByArrival.SATISFIED_BY_ARRIVAL
"""The one member of :class:`SatisfiedByArrival`, named for use as a value."""

InboundEvidence = tuple[RouteRelied, ...] | SatisfiedByArrival
"""What satisfies -- or fails to satisfy -- the inbound half of the owner's rule.

Every matching inbound route, or the arrival sentinel. An **empty** tuple is legitimate and
means nothing carries this stream's money to this destination, which is deficit 1.
"""


class SatisfiedByIdentity(Enum):
    """The exit slot, filled by the destination **being** a declared spendable endpoint.

    **Owner decision, 2026-08-23.** FR-002 read literally requires a declared exit route from
    every destination without exception, which makes the hryvnia balance on the owner's own
    salary rail a hole, because no route *out* of it is declared. The money is already where it
    needed to come back out to, and requiring a way out of the place money is spent from would
    have made the salary rail the first finding in the first real report.

    So the exit half of the owner's rule is satisfied **by identity** when the destination is
    itself in the declared spendable set. The mirror of :class:`SatisfiedByArrival` on the
    inbound side, and deliberately the same shape: a distinct single-member sentinel, so
    "already spendable" is explicitly not the same claim as "a declared route gets the money
    out", and so the two halves of the rule read the same way in the record and in a ``match``.

    **It supersedes declared exits, exactly as arrival supersedes declared inbound routes,
    and that is a real consequence.** A spendable destination that also declares exits shows
    this sentinel and not those routes: the verdict rests on the money already being there, and
    nothing is *relied on*. Where those exits leave a destination no stream can reach they are
    still listed as orphan exits; where the destination is reachable they appear nowhere in the
    report. The two sides behave identically, which is the property worth having -- but the
    information loss is real on this side in a way it is not on the arrival side, where a
    superseded inbound route would have to run from a venue to itself.
    """

    SATISFIED_BY_IDENTITY = "satisfied_by_identity"


SATISFIED_BY_IDENTITY: Final = SatisfiedByIdentity.SATISFIED_BY_IDENTITY
"""The one member of :class:`SatisfiedByIdentity`, named for use as a value."""

ExitEvidence = tuple[RouteRelied, ...] | SatisfiedByIdentity
"""What satisfies -- or fails to satisfy -- the exit half of the owner's rule.

Every declared exit reaching a spendable endpoint, or the identity sentinel. An **empty** tuple
means nothing declared gets the money out from here, which is deficit 2 or deficit 3.
"""


class AnySpendableEndpoint(Enum):
    """The target of a missing **exit**: any one of the declared spendable endpoints.

    FR-007 ⚙. For a missing *inbound* both
    endpoints are determined -- the stream fixes one, the destination the other. For a missing
    *exit* only the origin is: any declared spendable endpoint would satisfy the owner's rule,
    and picking one would be the report inventing a preference it has no basis for.

    So the target is this sentinel plus the candidate list, and a missing exit's identity is
    **origin + direction**. One to-do item however long the spendable list is, which is what
    stops every blocked-pair count multiplying by the length of that list.
    """

    ANY_SPENDABLE = "any_declared_spendable_endpoint"


ANY_SPENDABLE: Final = AnySpendableEndpoint.ANY_SPENDABLE
"""The one member of :class:`AnySpendableEndpoint`, named for use as a value."""

MissingTarget = Destination | AnySpendableEndpoint
"""Where a missing declaration would have to deliver money: a point, or a set."""

DeficitKind = Literal["no_inbound", "no_exit_declared", "exit_not_spendable"]
"""FR-003's three, read per research.md D7. A ``Literal`` rather than a ``str`` on the
``RouteStatus`` precedent: a misspelt kind is a type error rather than a deficit nothing ever
matches. There is deliberately **no** fourth member meaning "missing route" -- collapsing the
three is the thing FR-003 forbids, and an undifferentiated value would be the way it happened.
"""

NO_INBOUND: Final[DeficitKind] = "no_inbound"
"""Nothing declared carries money from the stream's arrival venue, in its arrival currency, to
this destination. The observation to make is a way **in**."""

NO_EXIT_DECLARED: Final[DeficitKind] = "no_exit_declared"
"""The destination has no declared way out at all. The observation to make is a way **out**."""

EXIT_NOT_SPENDABLE: Final[DeficitKind] = "exit_not_spendable"
"""A way out is declared, and it ends somewhere the owner cannot spend from. The observation to
make is a way out **that lands on the spendable list** -- a different errand from the one
:data:`NO_EXIT_DECLARED` calls for, which is why the two are separate kinds."""


@dataclass(frozen=True, slots=True, kw_only=True)
class MissingDeclaration:
    """The declaration file the owner could write from this report alone, once he has observed
    the corridor.

    FR-007. Origin venue, origin currency, direction, and target -- and **nothing else**.

    **No interior hops**, deliberately. The description asked for the currency path, and the
    hops of an unobserved corridor (UAH -> USDT -> USD, or UAH -> USD directly) are exactly the
    thing only an observation can supply. Naming them would be inventing the very link this
    report exists to refuse to invent.

    **No values of any kind** (FR-008): no provider, no fee, no premium, no cap, no latency, no
    rate. There is no field here one could live in, which is how SC-004 is satisfied across the
    whole output rather than sampled. This record names *what to observe*, never what the
    numbers will be; the numbers arrive with the owner's observation and its own provenance.

    **No regime field** (research.md D8): value equality is what makes the same hole in two
    regimes recognizably one declaration.
    """

    direction: RouteDirection
    """``inbound`` or ``exit``. Declared, never inferred -- and never satisfied by reversing a
    route in the other direction (FR-006, and feature 002's FR-027)."""

    origin_venue: str
    """Where the corridor would start: the stream's arrival venue for an inbound, the
    destination's own venue for an exit."""

    origin_currency: Currency
    """The currency it would start in. For an exit this is the destination's currency, which is
    what makes SC-010 checkable: the missing exit leaves *from* the destination and is not the
    inbound route's shape written backwards."""

    target: MissingTarget
    """The destination for an inbound; :data:`ANY_SPENDABLE` for an exit (FR-007 ⚙)."""

    candidates: tuple[SpendableEndpoint, ...]
    """For an exit: the declared spendable endpoints, **any one** of which satisfies it, sorted.
    Empty for an inbound, whose target is a single determined point."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Deficit:
    """One reason a pair is not comparison-ready, and the observation that would fix it."""

    kind: DeficitKind
    """Which deficit this is (FR-003). Never a bare "missing route"."""

    missing: MissingDeclaration
    """What to go observe."""

    observed_exits: tuple[RouteRelied, ...]
    """For :data:`EXIT_NOT_SPENDABLE` only: the exits that **do** exist, and therefore where the
    money can already get to. Empty for the other two kinds.

    This is what stops deficit 3 reading like deficit 2. The owner can see that a way out was
    declared and why it does not count, which is the difference between "nobody has looked at
    this" and "somebody looked, and it lands somewhere I cannot spend from".
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class Ready:
    """A pair the declarations support: a declared way in and a declared way out.

    FR-002, the owner's rule made checkable. Unrelated to :class:`NotReady` by design, on the
    ``RoundTripCost | ExitCostUnknown`` precedent: the two are matched on, never distinguished
    by a ``ready: bool`` flag that a caller can forget to read.
    """

    destination: Destination

    stream_id: str

    inbound: InboundEvidence
    """Every matching inbound route, or :data:`SATISFIED_BY_ARRIVAL`.

    **Every** match, not the first. The edge case "two inbound routes to one destination, only
    one with an exit partner" requires the partner-less inbound to stay visible, and a ready
    verdict naming one route would hide it behind the verdict.
    """

    exits: ExitEvidence
    """Every declared exit reaching a spendable endpoint, or :data:`SATISFIED_BY_IDENTITY`.

    A **non-empty** tuple when the way out is a declared route -- that is what makes the
    verdict ready -- and the sentinel when the destination is itself a declared spendable
    endpoint and the money is therefore already out (FR-002, owner decision 2026-08-23). An
    empty tuple never appears here: it would say the verdict rests on nothing, which is what a
    not-ready pair says.
    """

    rests_on: Literal["open", "constrained", "closed_only"]
    """Whether the routes this verdict relies on actually work today (FR-022, SC-015).

    ``open`` -- each half is satisfied either by a sentinel (arrival, identity) or by at least
    one **open** route. ``closed_only`` -- every relied route is declared closed.
    ``constrained`` -- everything in between.

    Neither sentinel is a route, so neither can be closed and neither contributes a status: a
    pair satisfied by arrival on one side and identity on the other rests on no route at all
    and is ``open``, which is the honest reading -- there is nothing there to shut.

    Derived rather than declared, and beside the statuses it was derived from. Coverage measures
    *declaration*, because the hole it exists to surface is an unobserved corridor and the fix
    for a closed route is not an observation (FR-022 ⚙). But a ready verdict resting only on
    closed routes must be visibly different from one resting on open ones, or the report would
    quietly overstate what can be compared today. A three-value field is the smallest thing that
    carries the distinction without duplicating feature 002's feasibility reporting -- a bare
    boolean would have to round ``constrained`` to one side or the other (research.md D10).
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class NotReady:
    """A pair the declarations do not support, and exactly what is missing.

    Never a bare refusal: every instance carries at least one :class:`Deficit`, and every
    deficit carries the declaration that would fix it. A hole in the route graph is a fact the
    owner acts on ("go observe that corridor"), never a silent absence.
    """

    destination: Destination

    stream_id: str

    inbound: InboundEvidence
    """What does exist on the inbound side. An empty tuple when the deficit is
    :data:`NO_INBOUND`; the matching routes, or the arrival sentinel, when the inbound half is
    satisfied and only the exit is missing."""

    deficits: tuple[Deficit, ...]
    """One or two: at most one inbound deficit and at most one exit deficit (research.md D7).
    Never empty -- a not-ready verdict with no reason would be the bare "missing route" FR-003
    forbids, wearing a different name."""


PairVerdict = Ready | NotReady
"""One destination, one stream, one regime. A tagged union matched on with ``match``, never a
record with a ``ready`` flag: a flag can be left unread, and a union member cannot."""


@dataclass(frozen=True, slots=True, kw_only=True)
class BlockedPair:
    """One comparison a missing declaration stands between the owner and."""

    destination: Destination

    stream_id: str

    alone_sufficient: bool
    """``False`` when this pair needs **another** missing declaration too (FR-011).

    The report must never present a necessary-but-not-sufficient declaration as if adding it
    alone would unlock the pair. A destination missing both its way in and its way out appears
    in both to-do items, with this ``False`` in both -- so the owner sees that one observation
    buys him nothing here until the other is made.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class TodoEntry:
    """A missing declaration with the pairs it blocks, inside one regime.

    The to-do list is the feature's answer to ``SIMULATOR_SPEC.md`` §11: *"your observations
    beat any published schedule"*, turned into a list ordered by how much each observation
    unlocks.
    """

    missing: MissingDeclaration

    blocked: tuple[BlockedPair, ...]
    """The pairs this declaration is required for, sorted by ``(venue_id, currency, stream_id)``.
    Non-empty."""

    count: int
    """``len(blocked)``. A **plain count of pairs**, never a weighted or composite score.

    Required test B12 forbids a non-standard composite driving a user-visible ordering, and the
    reason bites here specifically: a score would have to weigh a corridor's *value*, which
    needs costing over a registry that does not yet contain the observation -- an invented
    number by construction. Carried as a field rather than left to the reader to take a length
    of, so the ordering claim is readable beside the ordering.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class Observation:
    """One missing declaration, seen across every regime in the report.

    FR-014: which observation to make is **one** decision, but what it unlocks differs by
    regime, and the owner weighs regimes -- the tool does not.
    """

    missing: MissingDeclaration

    blocked_by_regime: tuple[tuple[str, int], ...]
    """``(regime_id, count)`` for **every** regime in the report, sorted by regime id.

    Every regime, including those where the count is zero: a declaration listed under one
    regime and absent from another would leave a reader unable to tell "blocks nothing there"
    from "was not audited there".

    **Never summed** (FR-013, FR-014). There is deliberately no total field: a single
    cross-regime number is the blended count the spec forbids, and adding one would be the
    easiest possible way to break the rule.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class OrphanExit:
    """A declared exit from a destination no stream can reach in this regime.

    FR-012: an observation already made that nothing yet uses. **Not** a deficit -- nothing is
    missing -- and not hidden either, because hiding it would misstate the registry: the owner
    paid attention to a corridor whose other half nobody has declared, and that is worth
    knowing before he goes and observes a third.
    """

    route_id: str

    origin: Destination
    """The destination it leaves. Unreachable in this regime, which is what makes it an
    orphan."""

    reaches_spendable: bool
    """Whether it lands on the declared spendable list. An orphan that *would* satisfy the exit
    half is a different finding from one that would not, and the owner acts differently on
    each: the first is waiting for a way in, the second for two observations."""


@dataclass(frozen=True, slots=True, kw_only=True)
class RegimeCoverage:
    """Everything the report says about one regime. Nothing crosses between two of these."""

    regime_id: str
    """The declared regime's id, or :data:`IMPLICIT_REGIME_ID`."""

    source: Literal["declared", "implicit"]
    """Whether the owner declared this regime or the report supplied the single implicit one
    (FR-015). Structural, so no consumer has to recognise the implicit id by its spelling."""

    route_ids: tuple[str, ...]
    """The regime's route set, sorted -- what this block audited. Every declared route when
    :attr:`source` is ``implicit``."""

    verdicts: tuple[PairVerdict, ...]
    """Every ``(destination x stream)`` of the declared universe, exactly once, sorted by
    ``(venue_id, currency, stream_id)``. No pair may be absent (FR-001) and none may appear
    twice."""

    todo: tuple[TodoEntry, ...]
    """Ordered by descending :attr:`TodoEntry.count`, then by declaration identity **for
    determinism only** (FR-010, research.md D9).

    Explicitly empty when every pair is ready: the honest happy path states that there is
    nothing to observe rather than leaving the field absent.
    """

    ties: tuple[tuple[int, ...], ...]
    """Groups of indices into :attr:`todo` whose counts are equal, groups of two or more only.

    FR-010 forbids breaking a tie arbitrarily and FR-016 requires the identical report on every
    run, and those pull in opposite directions unless the presentation order and the *claim*
    are separated -- which is exactly what ``results.ramp.Ranking.ties`` already does for the
    route ranking. The order of :attr:`todo` keeps the sequence deterministic; this field is
    what stops a position in it being read as precedence.
    """

    orphan_exits: tuple[OrphanExit, ...]
    """Sorted by route id. Listed, never counted as a deficit and never blocking anything."""


@dataclass(frozen=True, slots=True, kw_only=True)
class AuditedDeclarations:
    """Exactly which declarations produced this report (FR-021).

    **Ids, not paths.** The core cannot import ``pathlib`` and the reason is determinism rather
    than tidiness; the data layer already keeps ``route_files`` and friends beside the ids, and
    ``terezy.data.manifest`` is where a digest belongs if one is ever wanted (research.md D16).
    All five tuples are sorted, so a report is comparable to another field for field.
    """

    venue_ids: tuple[str, ...]

    stream_ids: tuple[str, ...]

    route_ids: tuple[str, ...]

    regime_ids: tuple[str, ...]
    """Empty when the implicit regime was used -- the owner declared none, and recording the
    reserved id here would say he had."""

    spendable: tuple[SpendableEndpoint, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class CoverageReport:
    """The audit: what the declared route graph can support, and what to observe next.

    Deliberately **not** a comparison. It is computed from declarations alone -- costing is not
    needed to establish absence -- and it carries no cost figure anywhere, so it cannot be
    mistaken for one.
    """

    audited: AuditedDeclarations

    regimes: tuple[RegimeCoverage, ...]
    """Sorted by regime id. Exactly one entry when the regime is implicit."""

    to_observe: tuple[Observation, ...]
    """One entry per distinct missing declaration across the whole report, with per-regime
    counts that are never summed (FR-014).

    Sorted by declaration identity and **carrying no ordering claim**: FR-010's ordering is per
    regime, in :attr:`RegimeCoverage.todo`, and an ordered cross-regime list would be a blend
    of regimes that FR-013 forbids. This list is an index, not a ranking.
    """

    enforcement: str
    """:data:`ENFORCEMENT`. Present so a reader of the *output*, not only of the spec, sees that
    the verdicts are advisory and that enforcement is a recorded deferral (FR-019)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class RegistryDimensionEmpty:
    """A dimension of the registry is empty, so there is no report to produce.

    Returned *instead of* a :class:`CoverageReport`, and unrelated to it, so a caller that
    forgot this case is a type error rather than a confident wrong reading. FR-020 and
    predecessor defect B10: an empty report is indistinguishable from full coverage, so there
    must be no code path that produces one.
    """

    dimensions: tuple[str, ...]
    """**Every** empty dimension of ``venues``, ``streams``, ``routes`` and ``spendable``,
    sorted -- not the first one found. Reporting one at a time would make an owner with an
    empty data root fix four things in four runs.

    ``spendable`` is a dimension of *this* feature rather than of feature 002's registry, and
    FR-020 does not name it. Including it is a deliberate widening, recorded in plan.md's
    Complexity Tracking: an empty spendable list makes every exit deficit 3, which is a report
    full of confident wrong verdicts -- exactly the outcome FR-020 exists to forbid.
    """

    reason: str
    """What is empty and why an empty report was not produced instead, in the output's own
    words (FR-017's honesty applied to the refusal itself)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ReservedRegimeId:
    """A declared regime carries the id the report reserves for the implicit one.

    Also returned instead of a report (research.md D14). Rare, and cheaper as a typed outcome
    than as an unwritten assumption: FR-015 requires the report to *say* when it supplied the
    implicit regime, and a block the owner cannot tell apart from one of his own does not say
    it. Shadowing his regime silently would be worse still.
    """

    regime_id: str

    reason: str
