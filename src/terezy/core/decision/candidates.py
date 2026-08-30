"""Enumeration: what the declarations offer, and what each pair that offered nothing was.

Every feature before this one costs a tuple somebody handed it. This one **finds** them --
`SIMULATOR_SPEC.md` §4.10.2 in the product's own words: *"Infeasible candidates are dropped with
the reason recorded, because 'your preferred plan is impossible in March' is itself an output."*

## This module constructs nothing

Both route terms of every candidate are read off what
:func:`terezy.core.routes.compose.compose` emitted. Nothing here builds a chain, extends one, or
decides that two routes join, and no rule about what connects lives here (FR-002). The
**single** permitted construction is the identity exit, and it is about the *absence* of a chain
rather than about what connects.

## It adds no feasibility rule either

Pruning is feature 010's typed refusals, reached by ``compare``'s own loop, and this module
contains no pre-screen, no cheap filter and no early exit that skips evaluation (FR-006,
FR-007). Two of ``compose``'s own guards -- a segment bound below one, a stream that already
arrives where the purchase happens -- are deliberately **not** re-checked before calling it: a
second copy of a rule is where the drift happens.

## Three columns, because a pair can fail in a way no candidate-level reason can carry

A ``Tuple`` cannot exist without a ``route_in``, so 010 was never asked whether a way in exists;
it was handed one, and the fact is about an ``(instrument, stream)`` pair rather than about a
candidate. So a pair that yields nothing is its own population and is never counted among the
drops: a drop count folding in combinations that were never real is a figure a reader divides
by and gets a meaningless answer (FR-008).

## Enumeration, not search

Every candidate is evaluated in full, so nothing is ever excluded by an estimate -- which is
what makes the label-correcting version checkable later against this one on a registry small
enough to run both. When enumeration stops being the right primitive,
:class:`~terezy.core.results.candidates.CandidateCeiling` says so by refusing (FR-019); the
refusal is the signal, and a silent cap would hide it.

Pure: no clock, no I/O, no state. ``as_of`` and the horizon are the caller's.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from terezy.core.decision.compare import compare
from terezy.core.decision.tuple_outcome import Registries, currency_of
from terezy.core.primitives import provenance as prov
from terezy.core.primitives import staleness
from terezy.core.results.candidates import (
    BenchmarkNotACandidate,
    CandidateCeiling,
    CandidateSet,
    CandidateSurvey,
    CeilingExceeded,
    DropGroup,
    DuplicateRunPlan,
    EnumerationRefused,
    MoreThanOneStreamInTheSet,
    NoPlanSupplied,
    NothingConnects,
    NothingNeedsToConnect,
    PairYieldedNoCandidate,
    PlannedCandidate,
    Question,
    QuestionDoesNotStandUp,
    SurveyRefused,
    UndeclaredRouteSupplied,
)
from terezy.core.results.composed import CompositionRefused, Unaskable
from terezy.core.results.coverage import Destination, SpendableEndpoint
from terezy.core.results.tuple import (
    BenchmarkUnavailable,
    Comparison,
    DeclarationMissing,
    RefusedTuple,
    Tuple,
    TupleOutcome,
)
from terezy.core.routes.compose import compose
from terezy.core.routes.path import (
    EXIT_BY_IDENTITY,
    Candidate,
    ExitChain,
    candidate_id,
    exit_chain_of,
    exit_segments_of,
    segments_of,
)

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Iterable, Mapping, Sequence

    from terezy.core.instruments.access import InstrumentAccess
    from terezy.core.primitives.currency import Currency
    from terezy.core.primitives.provenance import Provenance
    from terezy.core.routes.legs import Route


def enumerate_candidates(
    *,
    registries: Registries,
    routes: Mapping[str, Route],
    question: Question,
    ceiling: CandidateCeiling,
) -> CandidateSet | EnumerationRefused:
    """Every candidate the declarations offer for one question, or a typed refusal.

    ``routes`` is the route set of the **one regime in force**, narrowed by
    :func:`terezy.core.scenarios.regimes.routes_in_force`, and ``question.regime_id`` names it.
    It arrives beside ``registries`` rather than being narrowed here because 004 FR-017 makes
    that the caller's job for ``compose``, and this function is that caller -- which is also
    what makes :class:`~terezy.core.results.candidates.UndeclaredRouteSupplied` reachable
    rather than a guard that reads as protection.

    **The complete set or nothing** (FR-021). A partial set is never returned, because every
    later pass -- dominance, an objective, a stability check -- would then be computed over a
    silently partial universe, which is a false optimum with an impeccable audit trail.
    """
    considered = _considered(registries)
    walked = _walk(considered, registries=registries, routes=routes, question=question)
    if not isinstance(walked, tuple):
        return walked
    reach, no_candidate = walked
    refusal = _plans_stand_up(reach, question) or _within_the_ceiling(reach, question, ceiling)
    if refusal is not None:
        return refusal
    candidates = _ordered(reach, question)
    undeclared = _undeclared_routes(
        [candidate.key for candidate in candidates], routes=registries.routes
    )
    if undeclared is not None:
        return undeclared
    sources = _sources_read(candidates, considered=considered, routes=registries.routes)
    return CandidateSet(
        question=question,
        candidates=candidates,
        no_candidate=no_candidate,
        pairs_considered=len(considered) * len(registries.streams),
        provenance=prov.merge_all(item[0] for item in sources),
        staleness=staleness.merge_all(
            staleness.staleness_of(mark, registries.kinds, kind=kind, as_of=question.as_of)
            for mark, kind in sources
        ),
    )


def survey(
    *,
    registries: Registries,
    routes: Mapping[str, Route],
    question: Question,
    ceiling: CandidateCeiling,
    benchmark: Tuple,
) -> CandidateSurvey | SurveyRefused:
    """Enumerate the set and hand it to feature 010's ``compare``, with the accounting beside it.

    **``compare``'s own loop is the only evaluation** (FR-001a). A second call here would produce
    two outcomes per candidate and two dropped sets, and this feature's columns could then
    disagree with ``Comparison.refused`` with nothing to say which was authoritative. So
    :func:`evaluated` and :func:`dropped` read the first two populations *out of* the comparison.

    ``benchmark`` must be a member of the enumerated set exactly once (FR-022). It is not
    appended to a set that does not contain it: ``compare`` prepends a benchmark it was not
    handed, and 010's FR-012 forbids one arriving by a privileged side channel -- appending it
    here would reintroduce exactly that, one layer up.
    """
    undeclared = _undeclared_routes([benchmark], routes=registries.routes)
    if undeclared is not None:
        return undeclared
    enumerated = enumerate_candidates(
        registries=registries, routes=routes, question=question, ceiling=ceiling
    )
    if not isinstance(enumerated, CandidateSet):
        return enumerated
    keys = [candidate.key for candidate in enumerated.candidates]
    occurrences = keys.count(benchmark)
    if occurrences != 1:
        return BenchmarkNotACandidate(
            benchmark=benchmark,
            occurrences=occurrences,
            reason=(
                f"the named benchmark for {benchmark.instrument_id!r} appears {occurrences} "
                f"time(s) among the {len(keys)} enumerated candidate(s), and a benchmark is "
                "one of them exactly once (FR-022). It is not appended beside the set to make "
                "it fit: a benchmark that never came out of the same loop as what it "
                "benchmarks drifts from it, and the drift is invisible because both figures "
                "look reasonable."
            ),
        )
    streams = sorted({key.stream_id for key in keys})
    unfunded = [stream_id for stream_id in streams if stream_id not in question.amounts]
    if unfunded:
        raise ValueError(
            f"the question states no amount for {unfunded}, and the enumerated set is funded "
            f"from {streams}. An amount is stated per stream with no default anywhere "
            "(FR-005), so a missing one is an incomplete question rather than a fact about "
            "the money -- and defaulting it to zero would score a real option at nothing."
        )
    if len(streams) > 1:
        return MoreThanOneStreamInTheSet(
            stream_ids=tuple(streams),
            reason=(
                f"the enumerated set spans {streams}, and `compare` takes one amount for the "
                "whole set while this question states one per stream in each stream's own "
                "currency (FR-005). Widening that signature is a change to feature 010, made "
                "and reviewed there; scoring per stream here would produce one ranking per "
                "stream and no ranking of the set."
            ),
        )
    return CandidateSurvey(
        enumerated=enumerated,
        comparison=compare(
            keys,
            benchmark=benchmark,
            amount=question.amounts[streams[0]],
            horizon=question.horizon,
            as_of=question.as_of,
            continuation=question.continuation,
            registries=registries,
        ),
    )


def evaluated(comparison: Comparison | BenchmarkUnavailable) -> tuple[TupleOutcome, ...]:
    """Every candidate that produced an outcome, ranked or not (FR-008's first population).

    Read out of 010's result rather than counted beside it, so there is no second opinion here
    about which candidates were evaluated. A comparison places an outcome in one of two slots by
    whether it holds a rate; both are evaluations, and the distinction between them is 010's to
    make and to report.
    """
    match comparison:
        case Comparison():
            return (*comparison.ranked, *comparison.not_comparable)
        case BenchmarkUnavailable():
            return (*comparison.scored, *comparison.not_comparable)
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(comparison)


def dropped(comparison: Comparison | BenchmarkUnavailable) -> tuple[RefusedTuple, ...]:
    """Every candidate that produced no outcome, with its typed reason (FR-008, FR-010).

    The whole records, never a summary of them: the core formats nothing, and choosing what a
    reader sees is the presenting layer's job.
    """
    return comparison.refused


def drop_tally(refused: Sequence[RefusedTuple]) -> tuple[DropGroup, ...]:
    """The dropped candidates grouped by reason, with the declarations each group implicates.

    FR-011. **Derived on demand and stored nowhere**, so a tally can never disagree with the
    records it summarises. Grouped by the refusal record's type name rather than by a
    hand-written match, so a change to 010's union groups itself instead of leaving a second
    copy of that union's membership here -- and by the *type*, never by the ``reason`` text.
    """
    groups: dict[str, list[RefusedTuple]] = {}
    for item in refused:
        groups.setdefault(type(item.refusal).__name__, []).append(item)
    return tuple(
        DropGroup(
            refusal=name,
            count=len(members),
            instruments=_sorted_distinct(item.key.instrument_id for item in members),
            streams=_sorted_distinct(item.key.stream_id for item in members),
            routes=_sorted_distinct(
                route_id for item in members for route_id in _route_ids_of(item.key)
            ),
            missing=_sorted_distinct(
                item.refusal.what
                for item in members
                if isinstance(item.refusal, DeclarationMissing)
            ),
        )
        for name, members in sorted(groups.items())
    )


# ---------------------------------------------------------------------------
# The walk: one pass over the pairs, calling `compose` and nothing else
# ---------------------------------------------------------------------------


def _considered(registries: Registries) -> tuple[tuple[str, InstrumentAccess, Currency], ...]:
    """Every instrument that is both declared and reachable-in-principle, with its currency.

    An access entry naming an instrument nobody declared is skipped rather than refused here:
    FR-015 says such a tuple is never constructed and appears in **no** population, and the data
    layer already refuses the declaration at load, so this is the same rule stated where a
    hand-built registry can also reach it.
    """
    entries = []
    for instrument_id in sorted(registries.access):
        fund = registries.funds.get(instrument_id)
        bond = registries.instruments.get(instrument_id)
        declared = fund if fund is not None else bond
        if declared is None:
            continue
        entries.append((instrument_id, registries.access[instrument_id], currency_of(declared)))
    return tuple(entries)


_Reach = dict[tuple[str, str], tuple[tuple[Candidate, ...], tuple[ExitChain, ...]]]
"""For each pair that connects, the ways in and the ways out, both read off ``compose``."""


def _walk(
    considered: Sequence[tuple[str, InstrumentAccess, Currency]],
    *,
    registries: Registries,
    routes: Mapping[str, Route],
    question: Question,
) -> tuple[_Reach, tuple[PairYieldedNoCandidate, ...]] | EnumerationRefused:
    """Every pair asked of ``compose`` twice, sorted, with each answer put in its own column."""
    reach: _Reach = {}
    empty: list[PairYieldedNoCandidate] = []
    for instrument_id, access, currency in considered:
        for stream_id in sorted(registries.streams):
            ways_in = compose(
                routes=routes,
                stream=registries.streams[stream_id],
                destination=Destination(venue_id=access.bought_at, currency=currency),
                direction="inbound",
                regime_id=question.regime_id,
                bound=question.bound,
                spendable=registries.spendable,
            )
            if isinstance(ways_in, CompositionRefused):
                about_the_question = _about_the_question(ways_in)
                if about_the_question is not None:
                    return about_the_question
                empty.append(
                    PairYieldedNoCandidate(
                        instrument_id=instrument_id,
                        stream_id=stream_id,
                        why=NothingNeedsToConnect(refusal=ways_in),
                    )
                )
                continue
            ways_out = _ways_out(
                access,
                currency=currency,
                registries=registries,
                routes=routes,
                stream_id=stream_id,
                question=question,
            )
            if not isinstance(ways_out, tuple):
                return ways_out
            absent = _nothing_connects(
                ways_in.candidates,
                ways_out,
                instrument_id=instrument_id,
                stream_id=stream_id,
                access=access,
            )
            if absent is not None:
                empty.append(
                    PairYieldedNoCandidate(
                        instrument_id=instrument_id, stream_id=stream_id, why=absent
                    )
                )
                continue
            reach[instrument_id, stream_id] = (ways_in.candidates, ways_out)
    return reach, tuple(empty)


def _ways_out(
    access: InstrumentAccess,
    *,
    currency: Currency,
    registries: Registries,
    routes: Mapping[str, Route],
    stream_id: str,
    question: Question,
) -> tuple[ExitChain, ...] | EnumerationRefused:
    """Every declared way out of the venue the proceeds land at, or the identity exit.

    **The one construction this module makes** (FR-002's carve-out, FR-004a). Where the
    instrument's ``proceeds_to`` is itself a declared spendable endpoint, the way out *is* the
    identity exit -- 003's FR-002, an owner decision this feature does not re-decide -- and no
    chain is enumerated beside it. That the sentinel supersedes exit routes actually declared
    from a spendable venue is the recorded ``superseded-exit-visibility`` deferral, followed
    here rather than reopened.

    Emitting nothing in that case would put the pair in the *no candidate* column and report a
    corridor nobody declared, which is the false verdict the column exists to prevent.
    """
    if SpendableEndpoint(venue_id=access.proceeds_to, currency=currency) in registries.spendable:
        return (EXIT_BY_IDENTITY,)
    enumerated = compose(
        routes=routes,
        stream=registries.streams[stream_id],
        destination=Destination(venue_id=access.proceeds_to, currency=currency),
        direction="exit",
        regime_id=question.regime_id,
        bound=question.bound,
        spendable=registries.spendable,
    )
    if isinstance(enumerated, CompositionRefused):
        # Every exit refusal is about the question. `ALREADY_ARRIVED` is constructed under
        # `direction == "inbound"` only, so the two that remain are true of every pair at once.
        return _question_refusal(enumerated)
    return tuple(exit_chain_of(candidate) for candidate in enumerated.candidates)


def _question_refusal(refusal: CompositionRefused) -> QuestionDoesNotStandUp:
    """``compose``'s words carried onto a whole-enumeration refusal. One construction site."""
    return QuestionDoesNotStandUp(
        refusal=refusal,
        reason=(
            "the whole enumeration is refused rather than any candidate: "
            f"{refusal.reason} That is true of every pair at once, so a set built around it "
            "would be shaped by the broken input rather than by the declarations."
        ),
    )


def _about_the_question(refusal: CompositionRefused) -> QuestionDoesNotStandUp | None:
    """Whether ``compose`` refused about the *question* rather than about this one pair.

    FR-014a: read off the record, never off its text. *The money is already where it was
    wanted* is one pair with nothing missing, and belongs in the no-candidate column; the other
    two are true of every pair at once, so enumerating the rest would report a set shaped by a
    broken input as though it were an answer.
    """
    match refusal.case:
        case Unaskable.BOUND_ADMITS_NOTHING | Unaskable.NO_SPENDABLE_ENDPOINT:
            return _question_refusal(refusal)
        case Unaskable.ALREADY_ARRIVED:
            return None
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(refusal.case)


def _nothing_connects(
    ways_in: Sequence[Candidate],
    ways_out: Sequence[ExitChain],
    *,
    instrument_id: str,
    stream_id: str,
    access: InstrumentAccess,
) -> NothingConnects | None:
    """FR-013's reason where one side came back empty, or ``None`` if both connect.

    The side is named because the remedies differ: a corridor into the buying venue, or one out
    of the venue the proceeds land at. Reported in journey order, so a pair missing both is sent
    to the first thing that has to exist.
    """
    if not ways_in:
        return NothingConnects(
            side="route_in",
            reason=(
                f"no declared inbound route, within the bound, carries money from where "
                f"{stream_id!r} arrives to {access.bought_at!r} in the currency "
                f"{instrument_id!r} trades in. That is the absence of an option rather than the "
                "rejection of one: nothing was costed and nothing refused, and the remedy is a "
                "declaration rather than a different amount."
            ),
        )
    if not ways_out:
        return NothingConnects(
            side="route_out",
            reason=(
                f"no declared exit route, within the bound, carries money from "
                f"{access.proceeds_to!r} -- where {instrument_id!r} releases its proceeds -- to "
                "any declared spendable endpoint. An asset that cannot be liquidated into "
                "spendable base currency is not worth its stated value (Principle VI), so there "
                "is no candidate rather than a candidate with an unpriced way out."
            ),
        )
    return None


# ---------------------------------------------------------------------------
# The plans, the ceiling, and the order
# ---------------------------------------------------------------------------


def _plans_stand_up(reach: _Reach, question: Question) -> EnumerationRefused | None:
    """Every reachable instrument has plans, and no two of them are the same one twice.

    FR-003 and FR-018: a reachable instrument with no supplied plan refuses the **whole**
    enumeration rather than being skipped or defaulted. A default ``exit_on`` would silently pick
    one of a fund's declared ways out and drop the other from the comparison, and both figures
    would look entirely reasonable.
    """
    for instrument_id in sorted({key[0] for key in reach}):
        supplied = question.plans.get(instrument_id, ())
        if not supplied:
            return NoPlanSupplied(
                instrument_id=instrument_id,
                reason=(
                    f"{instrument_id!r} is reachable and no run plan was supplied for it. There "
                    "is no default anywhere in the stack for a consumption method, a coupon "
                    "policy, a liquidity mode, a buyback availability, an exit date or a chosen "
                    "point inside a stated range, and running in a loop does not create one. "
                    "The whole enumeration refuses rather than the instrument being skipped: a "
                    "set silently missing an option is the false optimum this tool exists to "
                    "avoid."
                ),
            )
        for later, plan in enumerate(supplied):
            first = supplied.index(plan)
            if first != later:
                return DuplicateRunPlan(
                    instrument_id=instrument_id,
                    positions=(first, later),
                    reason=(
                        f"the same run plan was supplied for {instrument_id!r} at positions "
                        f"{first} and {later}. The two produce one candidate twice, and a set "
                        "with a repeated member has no defined count -- the identity between "
                        "candidates enumerated and evaluated-plus-dropped fails by one. It is "
                        "refused rather than de-duplicated, because answering with fewer "
                        "candidates than were asked for is answering a different question."
                    ),
                )
    return None


def _within_the_ceiling(
    reach: _Reach, question: Question, ceiling: CandidateCeiling
) -> CeilingExceeded | None:
    """The whole count against the declared ceiling, before any candidate is built (FR-019).

    Counted in full rather than stopped at the ceiling, because the refusal names the count
    reached -- and *how far past* is what tells the owner whether the remedy is a tighter
    question or a different primitive.
    """
    reached = sum(
        len(ways_in) * len(ways_out) * len(question.plans.get(instrument_id, ()))
        for (instrument_id, _), (ways_in, ways_out) in reach.items()
    )
    if reached <= ceiling.max_candidates:
        return None
    return CeilingExceeded(
        ceiling=ceiling.max_candidates,
        reached=reached,
        reason=(
            f"the declarations offer {reached} candidates and the declared ceiling is "
            f"{ceiling.max_candidates}. No candidates are returned and the set is **not** "
            "truncated: a shortened set answers a different question from the one asked, and "
            "every later pass over it would be a false optimum with an impeccable audit trail. "
            "The ceiling exists to say that enumerating this registry has stopped being the "
            "right primitive, which is a finding rather than a limit to work around."
        ),
    )


def _ordered(reach: _Reach, question: Question) -> tuple[PlannedCandidate, ...]:
    """Every candidate, totally ordered by the declarations and the caller's inputs alone.

    FR-016: instrument id, stream id, the way in's ``candidate_id``, the way out's segment ids,
    then the plan's position in the caller's sequence. Loading the same declarations in a
    different file order changes neither membership nor sequence, because no term of the key is
    a property of the walk.
    """
    built: list[tuple[tuple[str, str, str, tuple[str, ...], int], PlannedCandidate]] = []
    for (instrument_id, stream_id), (ways_in, ways_out) in reach.items():
        for way_in in ways_in:
            for way_out in ways_out:
                for position, plan in enumerate(question.plans[instrument_id]):
                    built.append(
                        (
                            (
                                instrument_id,
                                stream_id,
                                candidate_id(way_in),
                                exit_segments_of(way_out),
                                position,
                            ),
                            PlannedCandidate(
                                key=Tuple(
                                    instrument_id=instrument_id,
                                    stream_id=stream_id,
                                    route_in=way_in,
                                    exit_terms=plan,
                                    route_out=way_out,
                                ),
                                plan_position=position,
                            ),
                        )
                    )
    return tuple(candidate for _, candidate in sorted(built, key=lambda item: item[0]))


# ---------------------------------------------------------------------------
# What the set rests on
# ---------------------------------------------------------------------------


def _route_ids_of(key: Tuple) -> tuple[str, ...]:
    """Every declared route id a key names, both ways.

    ``route_out`` is typed ``ExitChoice`` on the key and this feature never emits the
    ``FROM_THE_DECLARATION`` sentinel (FR-004), so a key that carries one came from somewhere
    else and names no route of its own here.
    """
    way_out = key.route_out
    out = exit_segments_of(way_out) if isinstance(way_out, ExitChain) else ()
    return (*segments_of(key.route_in), *out)


def _undeclared_routes(
    keys: Sequence[Tuple], *, routes: Mapping[str, Route]
) -> UndeclaredRouteSupplied | None:
    """Every route id named by a key resolves against the registry the evaluation will use."""
    for part, ids in (
        ("route_in", [name for key in keys for name in segments_of(key.route_in)]),
        (
            "route_out",
            [
                name
                for key in keys
                if isinstance(key.route_out, ExitChain)
                for name in exit_segments_of(key.route_out)
            ],
        ),
    ):
        unknown = sorted({name for name in ids if name not in routes})
        if unknown:
            return UndeclaredRouteSupplied(
                part=part,  # type: ignore[arg-type]
                route_ids=tuple(unknown),
                reason=(
                    f"the {part} of at least one candidate names {unknown}, which no declaration "
                    "under routes/ declares. That is a fact about the question rather than about "
                    "any candidate -- the route set composed over and the registry evaluated "
                    "against disagree -- so the whole enumeration refuses rather than reporting "
                    "one identical drop per candidate."
                ),
            )
    return None


def _sources_read(
    candidates: Sequence[PlannedCandidate],
    *,
    considered: Sequence[tuple[str, InstrumentAccess, Currency]],
    routes: Mapping[str, Route],
) -> tuple[tuple[Provenance, str], ...]:
    """Every declared table **enumeration itself** read, with the kind each ages under.

    FR-024. Two families: the legs of every route a candidate is built from, and the venue quote
    of every access entry the walk considered. What 010's ``evaluate`` reads is marked on its
    outcomes, so merging those here as well would be one fact in two places -- and would stop
    this mark saying what *enumeration* rested on.
    """
    read = [
        (leg.provenance, leg.kind_of_observation)
        for route_id in sorted({name for item in candidates for name in _route_ids_of(item.key)})
        for leg in routes[route_id].legs
    ]
    read.extend(
        (access.quote.price.provenance, access.quote.kind)
        for _, access, _ in considered
        if access.quote is not None
    )
    return tuple(read)


def _sorted_distinct(values: Iterable[str]) -> tuple[str, ...]:
    """The distinct strings an iterable yields, sorted -- the shape every tally field takes."""
    return tuple(sorted(set(values)))
