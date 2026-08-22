"""``coverage``: the only function that audits the declared route graph. A fold, not a costing.

Feature 002 made a destination without a declared exit honestly incomparable, one destination
at a time (its FR-030). This module turns those scattered refusals into a first-class audit of
the whole registry, enforcing the owner's rule:

    Everything money can be moved into must have a declared way in AND a declared way out --
    at least through one other venue -- before it may appear in any comparison.

A hole in the route graph is **a fact the owner acts on** ("go observe that corridor"), never a
silent absence. So every not-ready verdict names the exact declaration that is missing, and the
missing declarations are counted and ordered by how many `(destination x stream)` comparisons
each one would unblock -- which is ``SIMULATOR_SPEC.md`` §11's *"your observations beat any
published schedule"* turned into a to-do list.

## What this function refuses to do

* **Cost anything.** The report is computed from declarations alone -- costing is not needed to
  establish absence -- and no figure it produces is a cost. See ``results/coverage.py`` on why
  that is enforced by the types rather than by review.
* **Compose, infer or reverse a link** (FR-006, G4). No chaining two declared routes into a way
  out; no reading an inbound route backwards; no assuming a same-currency transfer needs no
  declaration. A destination whose exit ends at a venue that itself has a spendable exit is
  ``exit_not_spendable``, full stop -- a human sees a path, and this feature reports what the
  declarations support. Composition is feature 004's, and it arrives as a distinct *"reachable
  by composition only"* annotation beside the verdict rather than as a change to what
  :class:`~terezy.core.results.coverage.Ready` means.
* **Read ``partner_route``** (research.md D6). An exit is found by its own ``direction`` and
  ``origin``, never by following an inbound route's partner link. Two reasons: an exit declared
  without being anyone's partner is still a declared way out and must count, and reading
  coverage off the partner field is one short step from the reversal FR-006 forbids.
* **Take a date.** There is no ``on_date`` and no ``as_of``, because coverage is a claim about
  *declarations* rather than about today (FR-022 ⚙). A route declared but closed counts as
  declared -- the fix for a closed corridor is not an observation -- and the verdict carries
  that visibly through ``Ready.rests_on`` so a ready verdict resting only on closed routes is
  never mistaken for one resting on open ones.
* **Blend two regimes.** Every verdict, deficit, count and tie is computed inside one regime's
  fold. The only cross-regime structure in the output is
  :class:`~terezy.core.results.coverage.Observation`, which pairs one missing declaration with
  a count **per regime** and has no field a total could live in (FR-013, FR-014). Do not add
  one.
* **Return an empty report.** Every empty dimension is a typed outcome naming it, because an
  empty report is indistinguishable from full coverage and is the more flattering of the two
  readings -- predecessor defect B10 (FR-020).

## What matches what

The rule is research.md D6's, and it is the same chaining discipline the loader already
enforces on legs and ``cost.py`` already applies when it refuses a funding mismatch -- which is
what makes FR-018's agreement with costing checkable rather than aspirational.

* An **inbound match** for ``(destination, stream)``: ``direction == "inbound"``, the route's
  origin is the stream's arrival venue, its destination is the destination's venue, its first
  leg takes in the stream's arrival currency and its last leg hands out the destination's
  currency. A route from the right venue in a currency the stream does not arrive in does not
  carry that stream's money.
* An **exit from a destination**: ``direction == "exit"``, the route's origin is the
  destination's venue, and its first leg takes in the destination's currency.
* A **spendable exit**: an exit whose last leg hands out a currency at a venue named in the
  declared spendable list (FR-004).

Pure: no clock, no I/O, no randomness, no costing call, and every collection returned is a
tuple in a stated order -- so equal declarations produce an equal report, field for field
(FR-016, G11).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Literal, assert_never

from terezy.core.results.coverage import (
    ANY_SPENDABLE,
    ENFORCEMENT,
    EXIT_NOT_SPENDABLE,
    IMPLICIT_REGIME_ID,
    NO_EXIT_DECLARED,
    NO_INBOUND,
    SATISFIED_BY_ARRIVAL,
    AnySpendableEndpoint,
    AuditedDeclarations,
    BlockedPair,
    CoverageReport,
    Deficit,
    Destination,
    InboundEvidence,
    MissingDeclaration,
    MissingTarget,
    NotReady,
    Observation,
    OrphanExit,
    PairVerdict,
    Ready,
    RegimeCoverage,
    RegistryDimensionEmpty,
    ReservedRegimeId,
    RouteRelied,
    SpendableEndpoint,
    TodoEntry,
)

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from terezy.core.routes.legs import Route
    from terezy.core.routes.venues import Venue
    from terezy.core.scenarios.regimes import Regime
    from terezy.core.streams.streams import IncomeStream

__all__ = [
    "Destination",
    "SpendableEndpoint",
    "blocked_count",
    "coverage",
    "destinations",
    "is_spendable",
]
"""Re-exports :class:`Destination` and :class:`SpendableEndpoint`, which ``data-model.md``
heads with this module. They are *defined* in ``results/coverage.py`` -- defining them here
would make the records module and this one import each other -- and named here so the
document's reading resolves."""


def destinations(venues: Mapping[str, Venue]) -> tuple[Destination, ...]:
    """Every currency balance money could be moved into: venue x holdable currency.

    **Derived, never declared** (FR-001 ⚙, research.md D5), and that is what makes a venue with
    zero routes visible as a hole *the moment it is declared* rather than invisible until
    somebody tries to cost it. Building the universe from the routes instead -- the obvious
    shortcut, since a destination nothing reaches produces nothing but deficits -- is precisely
    the way to lose the holes this report exists to find.

    Sorted by ``(venue_id, currency)``, so the report's verdict order is a property of the
    declarations rather than of a mapping's iteration.
    """
    return tuple(
        sorted(
            (
                Destination(venue_id=venue.id, currency=currency)
                for venue in venues.values()
                for currency in venue.currencies
            ),
            key=_destination_key,
        )
    )


def is_spendable(endpoint: Destination, spendable: frozenset[SpendableEndpoint]) -> bool:
    """Whether money resting here counts as having come back out (FR-004).

    A plain membership test against declared data, and deliberately nothing more: there is no
    "UAH anywhere" rule and no venue class that qualifies by kind. What counts as spent is a
    fact about the owner's life, entered as data, so this predicate can be a lookup -- which is
    what makes SC-019 true, that adding a venue to the list flips a verdict with no source
    change.
    """
    return SpendableEndpoint(venue_id=endpoint.venue_id, currency=endpoint.currency) in spendable


def blocked_count(entry: TodoEntry) -> int:
    """How many comparisons this one observation would unblock. A plain count of pairs.

    Never a weighted or composite score (FR-010, required test B12). The temptation the report
    will create is "which observation is worth the most hryvnia", and that is a costing
    question over a registry that does not yet contain the observation -- an invented number by
    construction. This report must never grow one.
    """
    return len(entry.blocked)


# ---------------------------------------------------------------------------
# Ordering. Every one of these exists so the report is reproducible (FR-016).
# ---------------------------------------------------------------------------


def _destination_key(destination: Destination) -> tuple[str, str]:
    return destination.venue_id, destination.currency.value


def _target_key(target: MissingTarget) -> tuple[str, str]:
    """A missing declaration's target, as something sortable.

    :data:`ANY_SPENDABLE` sorts as the empty pair. It is a sentinel rather than a place, so any
    stable position would do; what matters is that two missing *inbound* declarations differing
    only in their target are ordered by it, since without that they would be two entries the
    sort could not separate and the report would not be reproducible.
    """
    match target:
        case Destination():
            return target.venue_id, target.currency.value
        case AnySpendableEndpoint():
            return "", ""
        case _:  # pragma: no cover -- exhaustive over the union
            assert_never(target)


def _missing_key(missing: MissingDeclaration) -> tuple[str, str, str, str, str]:
    """A missing declaration's identity, in the order the to-do list breaks its ties by.

    **Presentation only** beyond the count (research.md D9). FR-010 forbids breaking a tie
    arbitrarily and FR-016 requires the identical report on every run, and the two are
    reconciled the way ``results.ramp.Ranking`` already reconciles them: the sequence is
    ordered so it is deterministic, and :attr:`RegimeCoverage.ties` is where the claim lives.
    """
    return (
        missing.direction,
        missing.origin_venue,
        missing.origin_currency.value,
        *_target_key(missing.target),
    )


def _endpoint_key(endpoint: SpendableEndpoint) -> tuple[str, str]:
    return endpoint.venue_id, endpoint.currency.value


def _sorted_routes(routes: Mapping[str, Route]) -> tuple[Route, ...]:
    return tuple(routes[route_id] for route_id in sorted(routes))


# ---------------------------------------------------------------------------
# Matching: research.md D6, and nothing beyond it
# ---------------------------------------------------------------------------


def _inbound_matches(
    routes: Mapping[str, Route], destination: Destination, stream: IncomeStream
) -> tuple[RouteRelied, ...]:
    """Every declared route that carries **this stream's** money to **this** destination.

    Four conditions, and the two about currency are the ones that do the work. A route leaving
    the right venue in a currency the stream does not arrive in cannot carry that stream's
    money, and a route arriving in a currency the destination is not denominated in reaches a
    different destination -- both are the same chaining discipline the loader enforces on legs,
    applied at the audit level (spec Assumptions).

    Every match, not the first: a ready verdict has to be able to name all of them, or the edge
    case "two inbound routes to one destination, only one with an exit partner" would hide the
    partner-less one behind the word *ready*.
    """
    return tuple(
        RouteRelied(route_id=route.id, status=route.status)
        for route in _sorted_routes(routes)
        if route.direction == "inbound"
        and route.origin == stream.arrives_at
        and route.destination == destination.venue_id
        and route.legs[0].from_ccy is stream.amount.currency
        and route.legs[-1].to_ccy is destination.currency
    )


def _exits_from(routes: Mapping[str, Route], destination: Destination) -> tuple[RouteRelied, ...]:
    """Every declared way out of this destination, whether or not it reaches somewhere spendable.

    Found by the route's **own** direction and origin. Never by following an inbound route's
    ``partner_route``: an exit declared without being anybody's partner is still a declared way
    out, and reading the partner link would be one step from reversing the inbound (FR-006).
    """
    return tuple(
        RouteRelied(route_id=route.id, status=route.status)
        for route in _sorted_routes(routes)
        if route.direction == "exit"
        and route.origin == destination.venue_id
        and route.legs[0].from_ccy is destination.currency
    )


def _lands_spendable(route: Route, spendable: frozenset[SpendableEndpoint]) -> bool:
    """Whether this route's last leg hands the money over somewhere the owner spends from."""
    return is_spendable(
        Destination(venue_id=route.destination, currency=route.legs[-1].to_ccy), spendable
    )


def _leaves_from(route: Route) -> Destination:
    """The currency balance an exit route leaves: its origin venue, in its first leg's currency.

    The mirror of :func:`_lands_spendable`, and separate from it because an exit has two ends
    and the report says something different about each: where it leaves from decides whether it
    is an orphan, and where it lands decides whether it satisfies the owner's rule.
    """
    return Destination(venue_id=route.origin, currency=route.legs[0].from_ccy)


def _satisfied_by_arrival(destination: Destination, stream: IncomeStream) -> bool:
    """Whether the money is *born* at this destination (FR-005).

    Both halves have to match. A stream arriving as dollars at a venue does not satisfy the
    hryvnia balance at the same venue: a multi-currency account is the ordinary case, and
    treating the venue alone as the match would report a way in that nobody declared and that
    would have to cross a spread to exist.
    """
    return (
        destination.venue_id == stream.arrives_at and destination.currency is stream.amount.currency
    )


# ---------------------------------------------------------------------------
# Missing declarations: precise enough to write the file from, silent on every value
# ---------------------------------------------------------------------------


def _missing_inbound(destination: Destination, stream: IncomeStream) -> MissingDeclaration:
    """The way in nobody has declared: from where the money lands, to where it must go.

    Both endpoints are determined -- the stream fixes the origin, the destination fixes the
    target -- so this names a single corridor. The *interior* of that corridor is deliberately
    absent (FR-007 ⚙): whether it goes UAH -> USDT -> USD or UAH -> USD directly is exactly the
    thing only an observation can supply, and naming it would be inventing the link the report
    exists to refuse to invent.
    """
    return MissingDeclaration(
        direction="inbound",
        origin_venue=stream.arrives_at,
        origin_currency=stream.amount.currency,
        target=destination,
        candidates=(),
    )


def _missing_exit(
    destination: Destination, candidates: tuple[SpendableEndpoint, ...]
) -> MissingDeclaration:
    """The way out nobody has declared: from this destination, to anywhere spendable.

    **The target is a set, not a point** (FR-007 ⚙, and a correction from external review). Any
    declared spendable endpoint satisfies the owner's rule, so the report lists the candidates
    and picks none -- picking would be inventing a preference. Identity is therefore origin plus
    direction, which is what keeps this one to-do item however long the spendable list grows,
    and what stops every blocked-pair count multiplying by the length of that list.

    The origin is the **destination's** venue and currency. Not the inbound route's endpoints
    reversed, which is what SC-010 measures.
    """
    return MissingDeclaration(
        direction="exit",
        origin_venue=destination.venue_id,
        origin_currency=destination.currency,
        target=ANY_SPENDABLE,
        candidates=candidates,
    )


# ---------------------------------------------------------------------------
# One verdict
# ---------------------------------------------------------------------------


def _rests_on(
    inbound: InboundEvidence, exits: tuple[RouteRelied, ...]
) -> Literal["open", "constrained", "closed_only"]:
    """Whether the declarations a ready verdict rests on actually work today (SC-015).

    ``open`` needs both halves open: an open way in **and** an open way out. ``closed_only`` is
    every relied route closed. Everything else is ``constrained``, which is a real third state
    rather than a rounding of the other two -- a constrained route is costed and reported as
    constrained by feature 002, and flattening it into either neighbour would state something
    the declarations do not.

    **Arrival is not a route and cannot be closed.** Where the inbound half is satisfied by
    arrival it contributes no status: the money is already there, so the verdict rests on the
    exits alone. That is why the inbound half counts as open in the first test and contributes
    nothing to the "every relied route is closed" test in the second -- a pair reached by
    arrival whose only exit is closed is ``closed_only``, which is the honest reading and the
    one an empty ``relied`` list would have got wrong.

    Derived here rather than declared, and reported beside the statuses it came from, so a
    reader can check it against them.
    """
    if isinstance(inbound, tuple):
        relied = [*inbound, *exits]
        inbound_open = any(relied_route.status == "open" for relied_route in inbound)
    else:
        relied = [*exits]
        inbound_open = True
    if inbound_open and any(relied_route.status == "open" for relied_route in exits):
        return "open"
    if relied and all(relied_route.status == "closed" for relied_route in relied):
        return "closed_only"
    return "constrained"


def _verdict(
    destination: Destination,
    stream: IncomeStream,
    *,
    routes: Mapping[str, Route],
    spendable: frozenset[SpendableEndpoint],
    candidates: tuple[SpendableEndpoint, ...],
) -> PairVerdict:
    """One pair, in one regime: ready, or not ready with every deficit that applies.

    **The two sides are decided independently** (research.md D7), and that is a widening of
    FR-003's phrasing taken deliberately. FR-003 names its second kind "inbound exists but no
    exit partner", but the spec's own "missing both" edge case and FR-011 require a pair
    missing both halves to list *both* declarations -- so conditioning the exit deficit on the
    inbound being present would make the second observation invisible until the first had been
    made. The three kinds stay distinguished; what changed is only that kinds 2 and 3 classify
    the exit side alone.
    """
    arrival = _satisfied_by_arrival(destination, stream)
    matches = () if arrival else _inbound_matches(routes, destination, stream)
    inbound: InboundEvidence = SATISFIED_BY_ARRIVAL if arrival else matches
    exits = _exits_from(routes, destination)
    reaching = tuple(
        relied for relied in exits if _lands_spendable(routes[relied.route_id], spendable)
    )

    deficits: list[Deficit] = []
    if not arrival and not matches:
        deficits.append(
            Deficit(
                kind=NO_INBOUND,
                missing=_missing_inbound(destination, stream),
                observed_exits=(),
            )
        )
    if not exits:
        deficits.append(
            Deficit(
                kind=NO_EXIT_DECLARED,
                missing=_missing_exit(destination, candidates),
                observed_exits=(),
            )
        )
    elif not reaching:
        deficits.append(
            Deficit(
                kind=EXIT_NOT_SPENDABLE,
                missing=_missing_exit(destination, candidates),
                # The exits that *do* exist, so the owner can see the corridor was already
                # observed and why it does not count -- the difference between this and
                # NO_EXIT_DECLARED, which is a different errand.
                observed_exits=exits,
            )
        )

    if deficits:
        return NotReady(
            destination=destination,
            stream_id=stream.id,
            inbound=inbound,
            deficits=tuple(deficits),
        )
    return Ready(
        destination=destination,
        stream_id=stream.id,
        inbound=inbound,
        exits=reaching,
        rests_on=_rests_on(inbound, reaching),
    )


# ---------------------------------------------------------------------------
# The to-do list, the ties, and the orphans
# ---------------------------------------------------------------------------


def _todo(verdicts: tuple[PairVerdict, ...]) -> tuple[TodoEntry, ...]:
    """Group the regime's deficits by the declaration that would fix them, and count.

    Grouped by **value equality** of the missing declaration, which is what makes one missing
    exit one to-do item however many pairs it blocks and however long the candidate list is
    (FR-007 ⚙, research.md D8). ``alone_sufficient`` is decided per blocked pair rather than per
    entry, because the same missing exit can be the only thing standing between the owner and
    one pair while being half of what a second pair needs (FR-011).

    ``blocked`` inherits the verdict order, which is already
    ``(venue_id, currency, stream_id)`` -- so it is sorted without being re-sorted, and the two
    orders cannot drift apart.
    """
    grouped: dict[MissingDeclaration, list[BlockedPair]] = {}
    for verdict in verdicts:
        if not isinstance(verdict, NotReady):
            continue
        alone = len(verdict.deficits) == 1
        for deficit in verdict.deficits:
            grouped.setdefault(deficit.missing, []).append(
                BlockedPair(
                    destination=verdict.destination,
                    stream_id=verdict.stream_id,
                    alone_sufficient=alone,
                )
            )
    return tuple(
        sorted(
            (
                TodoEntry(missing=missing, blocked=tuple(blocked), count=len(blocked))
                for missing, blocked in grouped.items()
            ),
            key=lambda entry: (-entry.count, *_missing_key(entry.missing)),
        )
    )


def _ties(todo: tuple[TodoEntry, ...]) -> tuple[tuple[int, ...], ...]:
    """Index groups in ``todo`` whose counts are equal. Groups of one are not ties.

    On the ``results.ramp.Ranking.ties`` precedent, and simpler than it: these are integer
    counts, so equality is exact and there is no tolerance to anchor against. The sequence is
    already sorted by descending count, so equal entries are adjacent and one pass suffices.
    """
    groups: list[tuple[int, ...]] = []
    current: list[int] = []
    count: int | None = None
    for index, entry in enumerate(todo):
        if entry.count == count:
            current.append(index)
            continue
        if len(current) > 1:
            groups.append(tuple(current))
        count = entry.count
        current = [index]
    if len(current) > 1:
        groups.append(tuple(current))
    return tuple(groups)


def _orphan_exits(
    routes: Mapping[str, Route],
    *,
    reachable: frozenset[Destination],
    spendable: frozenset[SpendableEndpoint],
) -> tuple[OrphanExit, ...]:
    """Declared exits leaving somewhere no stream can reach in this regime (FR-012).

    **Not a deficit**, and listing them as one would send the owner to observe a corridor he has
    already observed. Not hidden either: he has paid attention to that corridor, and knowing so
    changes which observation he makes next. ``reaches_spendable`` is carried because an orphan
    that *would* satisfy the exit half is a different finding from one that would not -- the
    first is waiting for a way in, the second for two observations.
    """
    return tuple(
        OrphanExit(
            route_id=route.id,
            origin=_leaves_from(route),
            reaches_spendable=_lands_spendable(route, spendable),
        )
        for route in _sorted_routes(routes)
        if route.direction == "exit" and _leaves_from(route) not in reachable
    )


# ---------------------------------------------------------------------------
# Regimes
# ---------------------------------------------------------------------------


def _regime_sets(
    regimes: Mapping[str, Regime], routes: Mapping[str, Route]
) -> Iterator[tuple[str, str, tuple[str, ...]]]:
    """Each regime the report covers, as ``(id, source, its route ids)``, sorted by id.

    With no regime declared this yields exactly one implicit block holding **every** declared
    route, and says so structurally through ``source`` (FR-015, research.md D14) rather than by
    a spelling a consumer would have to recognise.

    A regime naming a route nobody declared **raises**, on ``regimes.routes_in_force``'s
    precedent and for its reason: the resolver refuses that at load and can name the file and
    the row, so reaching here with one means the check was bypassed. That is a programmer error
    rather than a fact about the money, and returning it as a typed outcome would invite callers
    to keep building incoherent regimes and read the answer as coverage.
    """
    if not regimes:
        yield IMPLICIT_REGIME_ID, "implicit", tuple(sorted(routes))
        return
    for regime_id in sorted(regimes):
        regime = regimes[regime_id]
        missing = sorted(regime.route_ids - set(routes))
        if missing:
            raise KeyError(
                f"regime {regime_id!r} names route(s) {missing} that are not declared. A "
                f"regime selects from the declared routes; it does not declare any of its "
                f"own, so a name that resolves to nothing is a belief about a corridor that "
                f"does not exist. Known routes: {sorted(routes)}"
            )
        yield regime_id, "declared", tuple(sorted(regime.route_ids))


def _regime_block(
    regime_id: str,
    source: str,
    route_ids: tuple[str, ...],
    *,
    routes: Mapping[str, Route],
    universe: tuple[Destination, ...],
    streams: Sequence[IncomeStream],
    spendable: frozenset[SpendableEndpoint],
    candidates: tuple[SpendableEndpoint, ...],
) -> RegimeCoverage:
    """Everything the report says about one regime, computed from that regime's routes alone.

    Nothing here reads another regime, and nothing another regime computes reaches this block.
    That is FR-013 held structurally: a corridor present in wartime and absent from the
    normalized regime produces two different verdicts for one pair, and there is no place for a
    blended third.
    """
    in_force = {route_id: routes[route_id] for route_id in route_ids}
    verdicts = tuple(
        _verdict(
            destination,
            stream,
            routes=in_force,
            spendable=spendable,
            candidates=candidates,
        )
        for destination in universe
        for stream in streams
    )
    reachable = frozenset(
        destination
        for destination in universe
        for stream in streams
        if _satisfied_by_arrival(destination, stream)
        or _inbound_matches(in_force, destination, stream)
    )
    todo = _todo(verdicts)
    return RegimeCoverage(
        regime_id=regime_id,
        source="implicit" if source == "implicit" else "declared",
        route_ids=route_ids,
        verdicts=verdicts,
        todo=todo,
        ties=_ties(todo),
        orphan_exits=_orphan_exits(in_force, reachable=reachable, spendable=spendable),
    )


def _observations(blocks: tuple[RegimeCoverage, ...]) -> tuple[Observation, ...]:
    """One entry per distinct missing declaration, with its count in **every** regime.

    Every regime, including those where the count is zero (FR-014): a declaration listed under
    one regime and absent from another would leave a reader unable to tell "blocks nothing
    there" from "was not audited there", and the second reading is the dangerous one.

    **Never summed.** Which observation to make is one decision; what it unlocks differs by
    regime, and the owner weighs regimes rather than the tool. Sorted by declaration identity
    and carrying **no ordering claim** -- FR-010's ordering lives in each regime's ``todo``, and
    an ordered cross-regime list would be exactly the blend FR-013 forbids.
    """
    counts = {
        (block.regime_id, entry.missing): entry.count for block in blocks for entry in block.todo
    }
    distinct = {entry.missing for block in blocks for entry in block.todo}
    return tuple(
        Observation(
            missing=missing,
            blocked_by_regime=tuple(
                (block.regime_id, counts.get((block.regime_id, missing), 0)) for block in blocks
            ),
        )
        for missing in sorted(distinct, key=_missing_key)
    )


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def _empty_dimensions(
    *,
    venues: Mapping[str, Venue],
    streams: Mapping[str, IncomeStream],
    routes: Mapping[str, Route],
    spendable: frozenset[SpendableEndpoint],
) -> RegistryDimensionEmpty | None:
    """Every empty dimension, named at once, or ``None`` when there is a report to produce.

    All of them rather than the first, because an owner with an empty data root should not have
    to fix four things in four runs. ``regimes`` is **not** here: no declared regime is FR-015's
    implicit one, which is a report rather than a refusal.
    """
    empty = tuple(
        sorted(
            name
            for name, declared in (
                ("venues", venues),
                ("streams", streams),
                ("routes", routes),
                ("spendable", spendable),
            )
            if not declared
        )
    )
    if not empty:
        return None
    return RegistryDimensionEmpty(
        dimensions=empty,
        reason=(
            f"the registry declares no {', no '.join(empty)}, so there is nothing to audit and "
            "no report is produced. An empty report is reported as this refusal instead, "
            "because a report with no verdicts in it is indistinguishable from a registry "
            "where everything is comparable -- and that is the more flattering of the two "
            "readings, which is why it is the one that gets believed (FR-020)."
        ),
    )


def coverage(
    *,
    venues: Mapping[str, Venue],
    streams: Mapping[str, IncomeStream],
    routes: Mapping[str, Route],
    regimes: Mapping[str, Regime],
    spendable: frozenset[SpendableEndpoint],
) -> CoverageReport | RegistryDimensionEmpty | ReservedRegimeId:
    """Audit the declared route graph: what can be compared, what cannot, and what to observe.

    Pure: no clock, no I/O, no state, no costing call. Called twice with equal arguments it
    returns an equal report, field for field and tuple order included, which is what makes
    FR-016 a checkable claim rather than an aspiration.

    Keyword-only, on feature 002's precedent and for a sharper reason here: five mappings of the
    same shape are trivially swappable positionally, and a swapped pair would produce a
    confident wrong report rather than a type error.

    **There is no date argument, and there will not be one.** Coverage is a claim about
    declarations, not about today (FR-022 ⚙): the hole it exists to surface is a corridor nobody
    has observed, and the fix is an observation. A closed route is a different fact -- observed,
    declared, currently unusable -- which feature 002's feasibility reporting already owns at
    costing time. What that leaves is discharged by ``Ready.rests_on``: a ready verdict resting
    only on closed routes is visibly different from one resting on open ones.

    Returns a :class:`~terezy.core.results.coverage.CoverageReport`, or
    :class:`~terezy.core.results.coverage.RegistryDimensionEmpty` naming every empty dimension,
    or :class:`~terezy.core.results.coverage.ReservedRegimeId` when a declared regime carries
    the id reserved for the implicit one. A tagged union in every case: there is no input for
    which this function returns a report with no verdicts in it.

    **The verdict is advisory** (FR-019, owner decision 2026-08-22). Producing this report has
    no effect on any costing or ranking output; the report says so in its own ``enforcement``
    field, so a reader of the output rather than of the spec sees the gap between the owner's
    rule and today's enforcement of it.
    """
    empty = _empty_dimensions(venues=venues, streams=streams, routes=routes, spendable=spendable)
    if empty is not None:
        return empty
    if IMPLICIT_REGIME_ID in regimes:
        return ReservedRegimeId(
            regime_id=IMPLICIT_REGIME_ID,
            reason=(
                f"a declared regime carries the id {IMPLICIT_REGIME_ID!r}, which this report "
                "reserves for the single regime it supplies when the owner has declared none "
                "(FR-015). It is refused rather than shadowed: the report must be able to say "
                "which of the two it did, and a block the owner cannot tell apart from one of "
                "his own does not say it."
            ),
        )

    universe = destinations(venues)
    ordered_streams = tuple(streams[stream_id] for stream_id in sorted(streams))
    candidates = tuple(sorted(spendable, key=_endpoint_key))
    blocks = tuple(
        _regime_block(
            regime_id,
            source,
            route_ids,
            routes=routes,
            universe=universe,
            streams=ordered_streams,
            spendable=spendable,
            candidates=candidates,
        )
        for regime_id, source, route_ids in _regime_sets(regimes, routes)
    )
    return CoverageReport(
        audited=AuditedDeclarations(
            venue_ids=tuple(sorted(venues)),
            stream_ids=tuple(sorted(streams)),
            route_ids=tuple(sorted(routes)),
            regime_ids=tuple(sorted(regimes)),
            spendable=candidates,
        ),
        regimes=blocks,
        to_observe=_observations(blocks),
        enforcement=ENFORCEMENT,
    )
