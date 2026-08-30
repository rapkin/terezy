"""``compose``: chain declared routes into candidates. Enumeration, never routing.

FR-001: *the system MUST enumerate composed candidates for a stated
``(stream, amount, destination)``: ordered chains of declared routes in which each segment's
destination venue and arriving currency match the next segment's origin venue and departing
currency.* FR-003 adds that every one of them is costed in full through the one costing
function, and FR-002 that composition invents no numbers.

## This module is a search, and a search is where a heuristic gets in

Composition is a routing problem, and routing problems attract shortest-path algorithms,
pruning by estimate, partial-cost caches, and tie-breaks by whatever order the search visited
things. Every one of those is a number more confident than its inputs. So the design refuses
each of them structurally rather than by convention:

* **Nothing is pruned by cost.** This module never calls a costing function, holds no ``Money``
  and imports none. There is no field on any record here for a path score, and required test
  **B12** is why: a routing search is exactly where a composite score sneaks into a
  user-visible ordering. Every emitted candidate is costed in full afterwards, by
  :func:`terezy.core.routes.cost.cost_one`, exactly as a declared route is.
* **No partial cost is memoised.** A partial cost is valid for **one amount only**, because
  minimums, caps and fixed fees are not linear. A cache keyed by anything less than the whole
  amount would be an invented number the first time it hit (research.md D5).
* **Order influences nothing.** Each adjacency bucket is sorted by route id, so the walk is a
  function of the declarations rather than of dictionary ordering; and the emitted tuple is
  sorted again by ``(segment count, route ids)``, so even the walk's order does not reach the
  output. SC-003 runs a registry in both declaration orders and compares everything, and it is
  the test that catches a heuristic rather than a flaky ordering.

## Directions never mix, and the check is in the index (research.md D10)

The adjacency index is built **per direction**, so an inbound enumeration cannot see an exit
route: it is not in the index it walks. A post-hoc filter over mixed candidates is the version
that gets one condition wrong under a refactor; an index that never contained the wrong routes
cannot emit them. An observation of a corridor in one direction says nothing about its terms,
its limits, or its existence in the other (FR-022).

## A junction converts nothing, charges nothing and waits for nothing

Two segments join only where the destination venue **and** arriving currency of one equal the
origin venue **and** departing currency of the next. Where the venue matches and the currency
does not, the chain simply does not exist -- it is never bridged by an implicit conversion,
because an implicit conversion is an invented leg at an invented rate (FR-002). The corridor's
absence is a fact for the coverage report, not something to paper over here.

## The regime is the caller's, and this module never hears about it

FR-017 requires every segment of a candidate to belong to the route set of the single regime in
force on the date. The narrowing is :func:`terezy.core.scenarios.regimes.routes_in_force`'s, and
what arrives here is the already-narrowed mapping plus the id it was narrowed for. That is the
same division ``cost_one`` already makes -- and it is load-bearing rather than tidy: the
costing engine has never heard of a regime, so an assumption cannot arrive in the same shape as
an observation, and ``tests/unit/test_transition_is_an_assumption.py`` holds the whole package
to it. A ``regime_id`` string carries the *fact* onto the result without carrying the belief
into the search.

⚙ **This is a departure from ``contracts/composition.md``**, which gives ``compose`` a
``regime: Regime`` parameter. Taking the record would put a second place in the engine that
decides which routes a regime includes, and would breach a landed boundary to do it. The
guarantee G14 asks for is unchanged: it is checked by handing this function a regime's routes
and no others, which is what the caller already has.

## No clock, no I/O, no state

``compose`` is pure. There is no date here at all: availability windows, statuses, caps and
minimums are **feasibility**, and feasibility is costing's answer on a date (FR-015), reported
with the binding segment named. A search that dropped a candidate because a leg was shut would
make an exclusion silent, which is precisely what FR-014 forbids.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from terezy.core.results.composed import (
    CompositionRefused,
    Enumeration,
    SegmentBound,
    Unaskable,
)
from terezy.core.results.coverage import Destination, SpendableEndpoint
from terezy.core.routes.legs import Route, RouteDirection
from terezy.core.routes.path import Candidate, ComposedPath, FundingPath
from terezy.core.streams.streams import IncomeStream

_Junction = tuple[str, str]
"""A venue id and a currency code: where value arrives, and in what.

A plain tuple rather than a record because it is a *key* and nothing else -- it is never
reported, never costed, and has no behaviour. The currency is carried as its code rather than
as a :class:`~terezy.core.primitives.currency.Currency` only so the key is trivially sortable
beside the venue id; nothing here converts anything.
"""


def _departs_at(route: Route) -> _Junction:
    """Where a route's money must already be, and in what currency, for the route to carry it."""
    return (route.origin, route.legs[0].from_ccy.value)


def _arrives_at(route: Route) -> _Junction:
    """Where a route's money ends up, and in what currency."""
    return (route.destination, route.legs[-1].to_ccy.value)


def _index(
    routes: Mapping[str, Route], direction: RouteDirection
) -> Mapping[_Junction, tuple[Route, ...]]:
    """Routes of one direction, keyed by where they depart from, each bucket sorted by id.

    **The direction filter is here and nowhere else** (research.md D10). A walk over this index
    cannot emit a candidate that mixes directions, because the routes of the other direction
    were never in it.

    **The sort is the determinism guarantee** (FR-008). A bucket left in dictionary order would
    make the emitted order depend on which file loaded first, and an ordering that depends on
    the filesystem is an ordering a reader cannot reproduce.
    """
    buckets: dict[_Junction, list[Route]] = {}
    for route_id in sorted(routes):
        route = routes[route_id]
        if route.direction != direction or not route.legs:
            continue
        buckets.setdefault(_departs_at(route), []).append(route)
    return {junction: tuple(bucket) for junction, bucket in buckets.items()}


def _chains(
    index: Mapping[_Junction, tuple[Route, ...]],
    *,
    start: _Junction,
    targets: frozenset[_Junction],
    max_segments: int,
) -> tuple[tuple[str, ...], ...]:
    """Every chain of at most ``max_segments`` routes from ``start`` to any of ``targets``.

    Depth-first over the sorted index, carrying the set of venues already visited. A chain is
    emitted the moment it arrives at a target and **is still extended**, because a target may
    also be an intermediate venue on a longer chain that reaches another target -- and FR-007
    wants every connectable chain within the bound, not the first one found.

    **The cycle rule is the visited set** (FR-005). Venues are the nodes of the search, so a
    segment whose destination has already been visited is never taken -- even in a different
    currency, and even when the round trip through it would be cheap. A genuinely useful
    out-and-back corridor can still be hand-declared as a single route, where its terms are
    observations rather than a search artefact.

    Nothing here looks at a cost, a cap, a status or a date. The only thing that stops a descent
    is the bound or a venue already seen.
    """
    found: list[tuple[str, ...]] = []

    def walk(junction: _Junction, visited: frozenset[str], taken: tuple[str, ...]) -> None:
        if len(taken) >= max_segments:
            return
        for route in index.get(junction, ()):
            arrival = _arrives_at(route)
            if arrival[0] in visited:
                continue
            chain = (*taken, route.id)
            if arrival in targets:
                found.append(chain)
            walk(arrival, visited | {arrival[0]}, chain)

    walk(start, frozenset({start[0]}), ())
    return tuple(found)


def _normalised(
    routes: Mapping[str, Route], chain: Sequence[str]
) -> tuple[tuple[object, ...], ...]:
    """A chain's legs as a comparable tuple, with ``Leg.index`` renumbered across the whole chain.

    FR-009's whole difficulty, in one function (research.md D6). ``Leg.index`` is **per route**,
    so concatenating a two-leg route and a one-leg route yields indices ``0, 1, 0`` where the
    declared equivalent has ``0, 1, 2``. Compared naively the two never match, the duplicate is
    never suppressed, and the ranking holds the same real-world movement twice -- which is
    exactly what SC-013 checks for. So the index is renumbered first and compared second, and
    that is said here rather than left for a reader to notice.

    Every declared **term** is compared: kind, endpoints, currencies, channel, both fees, the
    limits, the rail, the latency, the window and the disruption probability. Two chains
    differing in any one of them are genuinely different candidates and both stand.

    ⚙ **Provenance is deliberately not compared.** It records *which file declared* a movement,
    not what the movement is, so two declarations of the same real-world sequence differing only
    in their citations are still the same sequence -- and FR-009 is about a ranking never holding
    one movement twice. Including it would make the rule unreachable in exactly the case it was
    written for.
    """
    fields: list[tuple[object, ...]] = []
    position = 0
    for route_id in chain:
        for leg in routes[route_id].legs:
            fields.append(
                (
                    position,
                    leg.kind,
                    leg.from_venue,
                    leg.to_venue,
                    leg.from_ccy,
                    leg.to_ccy,
                    leg.channel,
                    leg.fee_pct,
                    leg.fee_fixed.amount,
                    leg.fee_fixed.currency,
                    None if leg.minimum is None else (leg.minimum.amount, leg.minimum.currency),
                    None if leg.maximum is None else (leg.maximum.amount, leg.maximum.currency),
                    None
                    if leg.monthly_cap is None
                    else (leg.monthly_cap.amount, leg.monthly_cap.currency),
                    leg.capacity_pool,
                    leg.latency_days,
                    leg.available_from,
                    leg.available_until,
                    leg.disruption_probability,
                    leg.kind_of_observation,
                )
            )
            position += 1
    return tuple(fields)


def _candidate(chain: tuple[str, ...], *, stream_id: str, routes: Mapping[str, Route]) -> Candidate:
    """One chain as the candidate it is: a declared route, or a composition of several.

    A one-segment chain **is** a declared route and is emitted as a :class:`FundingPath`, so a
    single-element ``ComposedPath`` never exists. The distinction is the type and not a flag
    (FR-013): a reader of a ranking can see which comparisons rest on composition without
    parsing an id.

    **Both kinds take their destination from where the last segment arrives**, rather than from
    the target that was asked for. The two coincide for an inbound enumeration and they do
    **not** for an exit one, where the target is a set of spendable endpoints and the question
    started at the destination: a one-segment way out labelled with the venue it left would name
    the wrong end of its own journey.
    """
    arrival = routes[chain[-1]].destination
    if len(chain) == 1:
        return FundingPath(destination_id=arrival, stream_id=stream_id, route_id=chain[0])
    return ComposedPath(destination_id=arrival, stream_id=stream_id, segments=chain)


def _deduplicated(
    candidates: Sequence[Candidate],
    routes: Mapping[str, Route],
    segments: Sequence[tuple[str, ...]],
) -> tuple[Candidate, ...]:
    """The candidates with no two identical leg chains, the earlier in the order standing.

    FR-009. The order handed in puts declared routes first (one segment sorts before two), so
    where a composed concatenation reproduces a declared route leg for leg it is the **declared
    route** that survives, which is what the requirement asks for: the same real-world sequence
    of movements appears once.
    """
    kept: list[Candidate] = []
    seen: list[tuple[tuple[object, ...], ...]] = []
    for candidate, chain in zip(candidates, segments, strict=True):
        legs = _normalised(routes, chain)
        if legs in seen:
            continue
        seen.append(legs)
        kept.append(candidate)
    return tuple(kept)


def _targets(
    direction: RouteDirection,
    *,
    destination: Destination,
    spendable: frozenset[SpendableEndpoint],
) -> frozenset[_Junction]:
    """Where a chain of this direction is allowed to end.

    An inbound chain ends at the destination that was asked for. An exit chain ends at **any**
    declared spendable endpoint (FR-022) -- the owner's own list, handed in as a parameter
    rather than read out of feature 003's audit (research.md D13). Using the *type* is not using
    the report, and a costing question that consulted a report would make a ranking depend on
    one.
    """
    if direction == "inbound":
        return frozenset({(destination.venue_id, destination.currency.value)})
    return frozenset({(endpoint.venue_id, endpoint.currency.value) for endpoint in spendable})


def compose(
    *,
    routes: Mapping[str, Route],
    stream: IncomeStream,
    destination: Destination,
    direction: RouteDirection,
    regime_id: str,
    bound: SegmentBound,
    spendable: frozenset[SpendableEndpoint],
) -> Enumeration | CompositionRefused:
    """Every chain of declared routes that connects, within the declared bound. FR-001, FR-007.

    Pure: no clock, no I/O, no state, and nothing costed. Called twice with equal arguments it
    returns equal results, and the order it returns them in is a function of the declarations
    alone (FR-008).

    ``routes`` is the route set of the **one regime in force** on the date in question, narrowed
    by :func:`terezy.core.scenarios.regimes.routes_in_force`; ``regime_id`` names it, and travels
    onto the result so a reader can see which world was searched. Handing in a wider mapping
    than the regime's is how FR-017 gets broken, and it is the caller's to get right for the
    same reason it already is for ``cost_one``.

    For ``direction="inbound"`` a chain starts where the stream's money arrives and ends at
    ``destination``. For ``direction="exit"`` it starts at ``destination`` and ends at any
    declared spendable endpoint -- the same function, the same rules, the bound applying to each
    chain **separately** (research.md D9). An exit enumeration's candidates describe **ways
    out**: each one's ``destination_id`` is the spendable endpoint it reaches, and
    :func:`terezy.core.routes.path.exit_chain_of` turns one into the
    :class:`~terezy.core.routes.path.ExitChain` a round trip is keyed by. A shared budget across
    the pair would make an inbound path's reachability depend on which exit chain it happened to
    be paired with, entangling two independently declared facts.

    Returns an :class:`~terezy.core.results.composed.Enumeration` -- possibly with **no**
    candidates, which is a legitimate answer meaning "nothing connects" -- or a
    :class:`~terezy.core.results.composed.CompositionRefused` for a question that could not be
    asked at all. The two are different claims and are different types, so a caller cannot read
    one as the other.
    """
    refused = _refusal(
        stream=stream,
        destination=destination,
        direction=direction,
        bound=bound,
        spendable=spendable,
    )
    if refused is not None:
        return refused
    start = (
        (stream.arrives_at, stream.amount.currency.value)
        if direction == "inbound"
        else (destination.venue_id, destination.currency.value)
    )
    chains = _chains(
        _index(routes, direction),
        start=start,
        targets=_targets(direction, destination=destination, spendable=spendable),
        max_segments=bound.max_segments,
    )
    # Sorted by segment count and then by the route ids themselves, so the emitted order is a
    # property of the declarations and not of the walk that found them. Declared routes -- one
    # segment -- therefore come first, which is what makes the duplicate rule below keep the
    # declared route rather than whichever concatenation happened to be visited first.
    ordered = tuple(sorted(set(chains), key=lambda chain: (len(chain), chain)))
    candidates = _deduplicated(
        [_candidate(chain, stream_id=stream.id, routes=routes) for chain in ordered],
        routes,
        ordered,
    )
    return Enumeration(candidates=candidates, bound=bound, regime_id=regime_id)


def _refusal(
    *,
    stream: IncomeStream,
    destination: Destination,
    direction: RouteDirection,
    bound: SegmentBound,
    spendable: frozenset[SpendableEndpoint],
) -> CompositionRefused | None:
    """The questions this function cannot answer, each said out loud rather than answered "none".

    An **empty** enumeration means the registry declares nothing that connects, which is a real
    finding and the coverage report's news to deliver. These three are different: the question
    itself does not stand up, and returning an empty candidate set for one of them would report
    a registry gap that does not exist.
    """
    if bound.max_segments < 1:
        return CompositionRefused(
            case=Unaskable.BOUND_ADMITS_NOTHING,
            reason=(
                f"the declared segment bound is {bound.max_segments}, which admits no candidate "
                "at all -- not even a declared route. A bound of 1 is how composition is turned "
                "off; a bound below 1 is a broken registry, and enumerating nothing for it "
                "would report every corridor as unreachable (FR-006)."
            ),
            destination_id=destination.venue_id,
            stream_id=stream.id,
        )
    if direction == "exit" and not spendable:
        return CompositionRefused(
            case=Unaskable.NO_SPENDABLE_ENDPOINT,
            reason=(
                "no spendable endpoint was declared, so an exit chain has nowhere to end. "
                "Enumerating none would say the registry declares no way out, when what is "
                "missing is the owner's statement of where money counts as spent (FR-022)."
            ),
            destination_id=destination.venue_id,
            stream_id=stream.id,
        )
    if direction == "inbound" and (stream.arrives_at, stream.amount.currency) == (
        destination.venue_id,
        destination.currency,
    ):
        return CompositionRefused(
            case=Unaskable.ALREADY_ARRIVED,
            reason=(
                f"stream {stream.id!r} already arrives as {destination.currency.value} at venue "
                f"{destination.venue_id!r}, which is the destination asked for. There is nothing "
                "to compose: every chain would have to leave the venue and come back, and a "
                "candidate never visits a venue twice (FR-005). Reporting no candidates would "
                "read as a registry gap rather than as money that is already where it was "
                "wanted."
            ),
            destination_id=destination.venue_id,
            stream_id=stream.id,
        )
    return None
