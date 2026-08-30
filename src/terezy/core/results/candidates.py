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

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

from terezy.core.instruments.interface import DateRange
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.staleness import StalenessVerdict
from terezy.core.results.composed import CompositionRefused, SegmentBound
from terezy.core.results.tuple import (
    BenchmarkUnavailable,
    Comparison,
    ContinuationAssumption,
    InstrumentPlan,
    RefusedTuple,
    Tuple,
)


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


@dataclass(frozen=True, slots=True, kw_only=True)
class Question:
    """Everything that determines a count, carried beside every count it determined.

    FR-012. Refusals across 010's union turn on the **amount** (a leg minimum, a monthly
    ceiling), on the **horizon** (which sets the projection window, so a date-carrying refusal
    moves with it) and on **as_of** (every staleness verdict). Two runs over one registry drop
    different candidates, so a drop count reported without the inputs that produced it is a
    figure more confident than its inputs.

    Stated over the *whole* question rather than over the subset of the seventeen that are
    amount-sensitive: which members those are is a fact the union owns and may change, and a
    list here would be a second copy of it going quietly out of step.
    """

    amounts: Mapping[str, Money]
    """What leaves each income stream, keyed by stream id, **in that stream's own currency**.

    Per stream and never one figure converted into the other (FR-005). Converting would need a
    rate that values one currency in another *for a return*, and neither declared rate is one: a
    channel rate is a transaction price and an official rate is a legal reference for what an
    income was worth on a date. Reusing either here conflates a role rather than filling this
    one (Principle VI).
    """

    horizon: DateRange
    """The comparison's one horizon, stated once and applied to every candidate."""

    as_of: date
    """When the question is asked. Decides staleness and nothing else; never a clock."""

    continuation: ContinuationAssumption
    """What proceeds arriving before the horizon do until it. No default anywhere."""

    plans: Mapping[str, tuple[InstrumentPlan, ...]]
    """How each instrument is to be run, keyed by instrument id, **in the caller's order**.

    FR-003: there is no default anywhere in the stack for a consumption method, a coupon policy,
    a liquidity mode, a buyback availability, an exit date or a chosen point inside a stated
    range, and running in a loop does not create one. A reachable instrument absent from this
    mapping refuses the whole enumeration rather than being skipped or defaulted.

    **This is also FR-025.** How many plans were supplied for an instrument is ``len`` of its
    entry, so a declared way out no supplied plan reaches is visibly absent rather than silently
    so -- read off the question rather than counted into a second field that could disagree
    with it.
    """

    bound: SegmentBound
    """The declared segment bound the route enumeration ran under (004 FR-007).

    Travels with the answer because it is half of what the answer means: a corridor needing four
    segments under a bound of three is otherwise indistinguishable from one nobody declared.
    """

    regime_id: str
    """The single regime whose route set every candidate's segments belong to (FR-023).

    An id rather than the regime record, on ``Enumeration.regime_id``'s reasoning: what is
    recorded is the *fact* of which world was searched.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class PlannedCandidate:
    """One candidate: 010's key, and where its run plan sat in the caller's sequence.

    Named for the *plan* rather than for the enumeration, because ``Candidate`` already means a
    way of reaching a venue (:data:`terezy.core.routes.path.Candidate`) and one of those is a
    term of the key below.

    **The position is beside the key and not in it**, and both halves matter. FR-023 needs the
    key to be the five declared terms and nothing else, so two sets enumerated under two regimes
    align by key equality; FR-016 and FR-017 need the position, because a run plan holds a date,
    a chosen point and an exchange-rate assumption, and there is no ordering over those a reader
    could reproduce.
    """

    key: Tuple
    """The five declared terms. Feature 010's record, unchanged -- this feature adds no term and
    no field to it."""

    plan_position: int
    """The plan's index in the sequence the caller supplied for this instrument (FR-017).

    Recorded rather than derived from the set's order, because the order is *produced by* it: a
    sort that ignored the caller's sequence would still satisfy an assertion written the other
    way round.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class NothingConnects:
    """The routes declare no way in, or no way out, for this pair (FR-013).

    The **absence of an option**, not the rejection of one, which is why a pair carrying this is
    never counted among the dropped candidates: the owner's remedy is a declaration rather than
    a different amount.
    """

    side: Literal["route_in", "route_out"]
    """Which enumeration came back empty. The remedies differ -- a corridor into the buying
    venue, or one out of the venue the proceeds land at -- and naming the side is what turns a
    finding into an action."""

    reason: str
    """Why there is no option, in the output's own words."""


@dataclass(frozen=True, slots=True, kw_only=True)
class NothingNeedsToConnect:
    """The stream already arrives where the purchase happens, so no way in is required (FR-014).

    The **opposite of a gap**, and reporting it as one would send the owner to declare a corridor
    that is not missing. What *is* missing is the candidate: 010's ``Tuple`` requires a
    ``route_in``, so a zero-hop way in is not representable, and a pair standing in this column
    is that recorded gap made visible rather than a permanent answer.
    """

    refusal: CompositionRefused
    """004's whole record, carried rather than paraphrased.

    Its ``case`` is what this feature matched on (FR-014a) and its ``reason`` is compose's own
    words reaching the report verbatim -- neither copied here, because a copy is what goes stale.
    """


NoCandidateReason = NothingConnects | NothingNeedsToConnect
"""Why an ``(instrument, stream)`` pair produced no candidate. Match exhaustively.

Two records rather than one with a discriminator, because the two remedies are opposite and
FR-014 requires them distinguishable **without reading prose**.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class PairYieldedNoCandidate:
    """One pair that was considered and became no candidate at all.

    FR-008's third population. Not a dropped candidate and never counted with one: a drop count
    that silently folded in combinations that were never real is a figure a reader divides by
    and gets a meaningless answer.
    """

    instrument_id: str
    stream_id: str
    why: NoCandidateReason


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidateSet:
    """The complete, ordered set of candidates for one question, with what yielded none.

    **Complete or a refusal, never most of it** (FR-021). Dominance, an objective, a stability
    check or an indifference band computed over a silently partial set is a false optimum with
    an audit trail that looks impeccable.

    **Empty is a legitimate value**, meaning the declarations connect nothing -- a real finding,
    and a different claim from a refusal, which is a different type. The same distinction 004's
    ``Enumeration`` versus ``CompositionRefused`` already draws, inherited whole.
    """

    question: Question
    """What was asked. Every count below is read beside it, never alone (FR-012)."""

    candidates: tuple[PlannedCandidate, ...]
    """Every candidate the declarations connect, totally ordered by instrument id, stream id,
    the way in's ``candidate_id``, the way out's segment ids, then the plan's position (FR-016).

    Ordered by a function of the declarations and the caller's inputs alone, so loading the same
    declarations in a different file order changes neither membership nor sequence.
    """

    no_candidate: tuple[PairYieldedNoCandidate, ...]
    """Every pair that yielded nothing, each with its typed reason, ordered by pair."""

    pairs_considered: int
    """How many ``(instrument, stream)`` pairs the registry offered.

    Counted from the declarations rather than from the loop, which is what makes FR-009's first
    identity -- *pairs considered = pairs enumerated + pairs yielding no candidate* -- a check
    rather than a tautology. A pair dropped on the floor by the walk fails it.
    """

    provenance: Provenance
    """The union of the marks on every declaration **enumeration itself** read: the legs of every
    route it put in a candidate, and the venue quote of every access entry it considered.

    FR-024, so a candidate set never looks cleaner than the registry behind it. The outcomes'
    own marks stay on the outcomes, where 010 already puts them.

    ⚙ **A known gap, recorded rather than closed:** 010's refusal records carry a reason and no
    provenance, so *which* unverified value caused a particular drop is not traceable from the
    drop itself. Closing it is a change to 010's union and is the ``provenance-on-a-refusal``
    future entry.
    """

    staleness: StalenessVerdict
    """The merged verdict over the same sources, aged at :attr:`Question.as_of` under each
    source's own declared kind."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidateSurvey:
    """A candidate set, compared -- and the accounting `compare` has nowhere to put.

    FR-001a: **`compare`'s own loop is the only evaluation.** A second call here would produce
    two outcomes per candidate and two dropped sets, and this record's columns could then
    disagree with :attr:`Comparison.refused` with nothing to say which was authoritative. So the
    evaluated and dropped populations are *read out of* :attr:`comparison` by
    :func:`terezy.core.decision.candidates.evaluated` and
    :func:`terezy.core.decision.candidates.dropped` rather than counted beside it.
    """

    enumerated: CandidateSet
    """The set that was compared, whole -- including the pairs that never became candidates,
    which is the column `compare` knows nothing about."""

    comparison: Comparison | BenchmarkUnavailable
    """010's result, unchanged. Both cases carry the outcomes and the refusals, so the accounting
    closes either way -- a benchmark that itself refused does not cost the other columns."""


@dataclass(frozen=True, slots=True, kw_only=True)
class NoPlanSupplied:
    """A reachable instrument with no supplied run plan (FR-018, FR-003).

    The whole enumeration refuses rather than the instrument being skipped, defaulted, or
    reported as yielding no candidate. A default ``exit_on`` would silently pick one of a fund's
    declared ways out and drop the other from the comparison, and both figures would look
    entirely reasonable.
    """

    instrument_id: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DuplicateRunPlan:
    """Two equal run plans supplied for one instrument, at two positions.

    Refused rather than deduplicated, because the two produce **one** key twice and a set with a
    repeated member has no defined count: FR-009's second identity fails by one when the repeated
    member is the benchmark, which ``compare`` filters by value. Deduplicating would silently
    answer a question with fewer candidates than the caller asked for (FR-021).
    """

    instrument_id: str
    positions: tuple[int, int]
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CeilingExceeded:
    """The declared candidate ceiling was reached, so nothing is returned (FR-019).

    **Naming both numbers, and carrying no candidates.** The ceiling exists to say *the
    enumeration primitive has stopped being the right one for this registry*, which is a finding
    the owner acts on; a silent cap would hide exactly that.
    """

    ceiling: int
    reached: int
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class QuestionDoesNotStandUp:
    """`compose` refused for a reason about the **question** rather than about one pair.

    A segment bound admitting nothing and an exit enumeration with no declared spendable endpoint
    are both true of every pair at once, so enumerating the rest would report a set shaped by a
    broken registry as though it were an answer.

    Which of the three fired is read off :attr:`CompositionRefused.case` and never off its text
    (FR-014a) -- the third, *the money is already where it was wanted*, is about one pair and
    lands in :class:`NothingNeedsToConnect` instead.
    """

    refusal: CompositionRefused
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UndeclaredRouteSupplied:
    """A way in or a way out names a route no declaration under ``routes/`` declares (FR-018).

    Reachable because the route set composed over and the ``Registries`` evaluated against arrive
    as separate arguments -- 004 FR-017 makes narrowing to one regime the caller's job, so a
    caller can compose over a set the evaluation does not declare. Left unchecked it produces one
    ``DeclarationMissing`` per candidate: a page of drops all saying the same thing about the
    question and nothing about any candidate.
    """

    part: Literal["route_in", "route_out"]
    route_ids: tuple[str, ...]
    reason: str


EnumerationRefused = (
    NoPlanSupplied
    | DuplicateRunPlan
    | CeilingExceeded
    | QuestionDoesNotStandUp
    | UndeclaredRouteSupplied
)
"""The ways the whole enumeration does not stand up. Returned *instead of* a set.

On the precedent of ``CompositionRefused`` and ``BenchmarkUnavailable``: a different type rather
than a weaker answer, so a caller that forgot the case is a type error rather than a partial set
read as a complete one.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkNotACandidate:
    """The named benchmark is not a member of the enumerated set, exactly once (FR-022).

    Refused rather than appended. ``compare`` prepends a benchmark it was not handed, and 010's
    FR-012 forbids a benchmark arriving by a privileged side channel -- appending one here would
    reintroduce it one layer up, ranking the set against a figure that never came out of the same
    loop.
    """

    benchmark: Tuple
    occurrences: int
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class MoreThanOneStreamInTheSet:
    """The set spans two income streams and ``compare`` takes one amount for all of it.

    A recorded gap rather than a workaround. FR-001a: widening ``compare`` to take one amount per
    stream is a change to 010, made and reviewed there -- and a per-stream loop here would produce
    one ranking per stream and no ranking of the set. Unreachable in the shipped registry, where
    the dollar stream connects to nothing inbound.
    """

    stream_ids: tuple[str, ...]
    reason: str


SurveyRefused = EnumerationRefused | BenchmarkNotACandidate | MoreThanOneStreamInTheSet
"""The ways a set cannot be compared, widening :data:`EnumerationRefused` by two.

Two unions rather than one, so a caller of ``enumerate_candidates`` matching exhaustively is not
made to carry arms that never fire -- the shape ``resolver._check_composition_owner`` argues
against, where a guard that cannot fire reads as protection.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class DropGroup:
    """One reason, how many candidates it dropped, and which declarations they implicate.

    FR-011. Derived from the retained ``RefusedTuple`` records by one named function and **never**
    stored beside them: two fields holding one truth is where the drift happens, and here the
    drift would be a tally disagreeing with the records it summarises.
    """

    refusal: str
    """The refusal record's type name -- structural, not a reading of its ``reason`` text.

    Taken from the record rather than written out as a seventeen-arm match, so a change to 010's
    union groups itself instead of leaving a second copy of the union's membership here.
    """

    count: int

    instruments: tuple[str, ...]
    """The distinct instruments the group's members name, sorted."""

    streams: tuple[str, ...]
    """The distinct income streams they name, sorted."""

    routes: tuple[str, ...]
    """The distinct declared routes their ways in and out are made of, sorted."""

    missing: tuple[str, ...]
    """What a ``DeclarationMissing`` in the group said was absent, sorted; empty otherwise.

    So the remedy is readable from the tally alone -- *four candidates dropped, all wanting the
    same undeclared tax class* -- without reading hundreds of individual records.
    """


__all__ = [
    "BenchmarkNotACandidate",
    "CandidateCeiling",
    "CandidateSet",
    "CandidateSurvey",
    "CeilingExceeded",
    "DropGroup",
    "DuplicateRunPlan",
    "EnumerationRefused",
    "MoreThanOneStreamInTheSet",
    "NoCandidateReason",
    "NoPlanSupplied",
    "NothingConnects",
    "NothingNeedsToConnect",
    "PairYieldedNoCandidate",
    "PlannedCandidate",
    "Question",
    "QuestionDoesNotStandUp",
    "RefusedTuple",
    "SurveyRefused",
    "UndeclaredRouteSupplied",
]
"""``RefusedTuple`` is re-exported and defined nowhere here: a dropped candidate is 010's record,
not a new one and not a summary of one (FR-010)."""
