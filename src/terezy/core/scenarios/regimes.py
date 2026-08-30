"""Regimes: which routes exist on a date, and the stated assumption that decides it.

FR-019 and FR-020.

## What a regime is, and what it is not

A regime is a name and a set of route ids: *these are the corridors that exist while this
holds*. A transition is a date, the regime on each side of it, a marker saying the date is a
guess, and the guess in words.

**A regime is not a leg availability window** (research.md D8), and the two must never be
collapsed into one another even though either could mechanically produce the same route set on
a given date. The difference is what the project knows:

* ``Leg.available_from`` / ``Leg.available_until`` is a **fact** about a corridor, carrying a
  source and a retrieval date. "This closed in March 2025."
* :class:`RegimeTransition` is an **assumption**. "The war ends mid-2027." Nobody knows.

Expressed as a leg window, the guess would sit in a field whose every other value is an
observation, and every output downstream would report a corridor ruled out by a belief in the
same shape as one that genuinely closed -- a ``RouteUnusable`` whose ``binding_constraint``
names a declared field. That is the confusion ``SIMULATOR_SPEC.md`` §1.3 is about, and it is why
this module produces a **narrowed set of candidates** rather than a refusal per route.

## How the two compose when both apply to one leg on one date

They compose in one direction only, and the order is the point:

1. The regime decides which routes are **candidates**. :func:`routes_in_force` narrows the
   route mapping and :func:`paths_in_force` narrows the funding paths to match, so a route the
   regime rules out never reaches ``cost_one`` at all and therefore produces no
   ``RouteUnusable``. What it left out is named in :attr:`RoutesInForce.excluded`, beside the
   transition that did it -- reported, never silent, and never disguised as a route's own limit.
2. Each surviving candidate is then costed, and its legs' windows and limits decide whether it
   can carry the money on the date -- reported as a ``RouteUnusable`` naming
   ``leg.available_from``, ``leg.available_until``, ``leg.minimum`` or ``leg.maximum``.

So a leg can be shut for either reason and the output says which: an assumed exclusion appears
as a route the regime does not include, an observed one as a binding constraint on a declared
field. A regime never writes into the second channel, and nothing here touches ``cost_one``.

## One transition, and a sequence anyway

``data-model.md`` records that this feature declares and tests exactly **one** transition,
because a second needs a second assumption the owner has not stated. The functions here take a
whole sequence regardless: a chain of regimes is a sequence of transitions, the selection is
the same fold either way, and a signature that admitted one would have to change to admit two.
The type does not forbid more; the fixtures do not exercise more.

## What this module refuses, and why by raising

Every refusal below is a *structural* incoherence in the declared scenario, not a fact about
money: a sequence with no transitions, two transitions on one date, a chain whose regimes do not
join, a regime naming a route nobody declared, a regime that lets money in through a route whose
declared way out it excludes. In each case there is no honest regime to return, and returning
one would mean inventing the owner's belief for them. So these raise, on the precedent of
``cost._route_for`` and ``legs.cost_fn_for``: the data layer validates the declaration and can
name the file and the row, and reaching here incoherent means that validation was bypassed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from typing import Literal

from terezy.core.routes.legs import Route
from terezy.core.routes.path import Candidate, segments_of


@dataclass(frozen=True, slots=True, kw_only=True)
class Regime:
    """A named state of the world, and the routes that exist while it holds.

    Carries no ``Provenance``: a regime is the owner's belief about what will be available,
    and a belief has no source, no retrieval date and nothing to verify. Attaching a
    fabricated one to satisfy a provenance check would be the top-severity defect Principle I
    names, which is why ``data/scenarios/`` is exempt from the citation gate outright.
    """

    id: str
    """``wartime``, ``normalized``. Unique across the scenario's regimes."""

    route_ids: frozenset[str]
    """Which declared routes exist under this regime.

    Ids rather than :class:`~terezy.core.routes.legs.Route` records, so a regime cannot become
    a second place a route is declared. The routes themselves are curated data shared across
    every regime; what a regime states is only *which of them* it believes in.

    A ``frozenset`` because membership is the whole question and order means nothing. Both
    directions of a corridor belong in it: a set holding an inbound route but not the exit route
    it declares as its partner is refused by :func:`routes_in_force`, because a regime cannot
    make money one-way -- that claim is a route declaring ``partner_route = null``.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class RegimeTransition:
    """One dated change of regime, marked as the assumption it is.

    The whole record is a statement about the future, and every field is there to keep that
    unmissable rather than to be computed with.
    """

    on_date: date
    """The assumed date. The **first** day of :attr:`after` -- see :func:`routes_in_force` for
    why the boundary is decided here rather than at each comparison."""

    before: str
    """The :attr:`Regime.id` in force up to, but not including, :attr:`on_date`."""

    after: str
    """The :attr:`Regime.id` in force from :attr:`on_date` onward."""

    is_assumption: Literal[True]
    """**Structurally always true**, and required rather than defaulted.

    FR-020 requires a transition date be presented as a stated assumption and never as a known
    fact. A ``bool`` could be set ``False``, so the type admits exactly one value: the claim
    cannot be turned off, and because there is no default it cannot be omitted either -- every
    construction site writes ``is_assumption=True`` and says out loud what it is building.

    It exists to make the claim unmissable in the output. It is **not** for branching on: there
    is no other case, so a ``if transition.is_assumption`` would be dead code implying one.
    """

    rationale: str
    """The owner's stated belief, in words. Required.

    A date with no reasoning behind it is indistinguishable from a typo, and FR-020's "stated
    assumption" is not stated by a marker alone. This is what :func:`stated_assumption` puts in
    front of the reader beside every figure the regime changed.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class RoutesInForce:
    """Which routes a scenario says exist on one date, and the assumption that decided it.

    The result of :func:`routes_in_force`. Carries data only; the sentence an output prints is
    :func:`stated_assumption` applied to :attr:`decided_by`, derived rather than stored, because
    two places holding one fact can disagree.
    """

    on_date: date
    """The date this selection was made for.

    Carried, unlike on ``RampCost``, because here the date *is* half the finding: the whole
    content of this record is "which regime was in force **on a date**", and a record whose
    meaning depends on an input the reader cannot see is not traceable (Principle III).
    """

    regime: Regime
    """The regime in force on :attr:`on_date`."""

    decided_by: RegimeTransition
    """The transition whose date placed :attr:`on_date` on one side or the other.

    Travels with the answer because the answer is a number and the reason for it is a guess.
    An output showing the cost drop without this record cannot say what the drop is conditional
    on.
    """

    routes: Mapping[str, Route]
    """The declared routes this regime includes, keyed by id -- ready to hand to ``cost_one``
    or ``rank`` as their ``routes`` argument."""

    excluded: tuple[str, ...]
    """Ids of the declared routes this regime leaves out, sorted.

    **Named rather than quietly absent.** The exclusion is an assumption's consequence, and an
    output that showed a comparison of one route with no hint that three others were ruled out
    by a belief would be hiding the belief. Sorted so the field is deterministic.

    Deliberately *not* a ``RouteUnusable``: that record's ``binding_constraint`` names a
    declared field, and an assumed exclusion arriving in that shape would be indistinguishable
    from an observed one (research.md D8).
    """


def stated_assumption(transition: RegimeTransition) -> str:
    """FR-020's sentence: the transition date, said as an assumption, with its rationale.

    One place, so every output says it the same way and none of them can say it as a fact. On
    the precedent of ``RouteUnusable.reason``: a plain-language statement of a degraded or
    conditional outcome belongs beside the rule that produced it, and is data for the output
    layer to render rather than rendering of its own.
    """
    return (
        f"ASSUMPTION, not an observation: the regime is assumed to change from "
        f"{transition.before!r} to {transition.after!r} on "
        f"{transition.on_date.isoformat()}. Nobody knows this date; it is the owner's stated "
        f"belief and every figure that depends on it is conditional on it. Stated rationale: "
        f"{transition.rationale}"
    )


def _checked(transitions: Sequence[RegimeTransition], regimes: Mapping[str, Regime]) -> None:
    """Refuse a transition sequence that does not describe one chain of regimes.

    Empty, out of order, dated the same day twice, or joined at regimes that do not match: in
    every case some date has no regime the owner named, or has two, and picking one would be
    inventing their belief. Also refuses a transition naming a regime nobody declared.

    The data layer validates the same properties when it loads the declaration and can name the
    file and the row; reaching here incoherent is a bypass, so this raises rather than returning
    a typed refusal.
    """
    if not transitions:
        raise ValueError(
            "a scenario with no declared transition has no regime for any date. There is no "
            "default regime: substituting one would state a belief about which corridors exist "
            "that the owner never expressed (FR-019)"
        )
    for position, transition in enumerate(transitions):
        for named in (transition.before, transition.after):
            if named not in regimes:
                raise KeyError(
                    f"transition {position} names regime {named!r}, which is not declared. "
                    f"Known regimes: {sorted(regimes)}"
                )
    for position, (earlier, later) in enumerate(pairwise(transitions)):
        if later.on_date <= earlier.on_date:
            raise ValueError(
                f"transitions must be declared in strictly ascending date order, but "
                f"transition {position + 1} is dated {later.on_date.isoformat()} and "
                f"transition {position} is dated {earlier.on_date.isoformat()}. They are "
                f"neither reordered nor deduplicated here: two regimes claiming one date is a "
                f"contradiction in the scenario, and choosing between them would be choosing "
                f"the owner's belief for them"
            )
        if earlier.after != later.before:
            raise ValueError(
                f"transition {position} ends in regime {earlier.after!r} but transition "
                f"{position + 1} begins in regime {later.before!r}, so the dates between "
                f"{earlier.on_date.isoformat()} and {later.on_date.isoformat()} fall in a "
                f"regime nobody declared. A chain of regimes has to join up"
            )


def _regime_on(
    transitions: Sequence[RegimeTransition], on_date: date
) -> tuple[str, RegimeTransition]:
    """The regime id in force on a date, and the transition that decided it.

    **The transition date belongs to the regime after it.** "The war ends on the first of July"
    means the first of July is a day of peace, so the comparison is ``on_date >= t.on_date``.
    The boundary is decided once, here, rather than at each comparison, because two comparisons
    written independently would eventually disagree by a day and the disagreement would be
    invisible.

    Walks forward and keeps the last transition already passed. :func:`_checked` has established
    the sequence is ascending and joined, so the first transition's ``before`` is the regime in
    force before anything happens.
    """
    decided = transitions[0]
    regime_id = decided.before
    for transition in transitions:
        if on_date >= transition.on_date:
            decided = transition
            regime_id = transition.after
    return regime_id, decided


def routes_in_force(
    regimes: Mapping[str, Regime],
    routes: Mapping[str, Route],
    *,
    transitions: Sequence[RegimeTransition],
    on_date: date,
) -> RoutesInForce:
    """The routes a scenario says exist on ``on_date``, with the assumption that decided it.

    ``on_date`` is when the money moves, and it is **never** ``as_of``, which decides
    staleness. Both are ``date``, so nothing catches the substitution: a run that passed the
    as-of date here would select the regime in force on the day the question was asked and
    compare against corridors the scenario says do not exist on the day the money moves.

    ``routes`` is **every** declared route, not a regime's own. Declarations do not come and go
    with a belief: the corridors are all declared, and the regime states which of them it
    believes in. What is returned is that narrowing, plus the ids it left out and the transition
    responsible, so an output can show the belief beside the figures it changed
    (:func:`stated_assumption`).

    See this module's docstring for why the refusals below raise.
    """
    _checked(transitions, regimes)
    regime_id, decided_by = _regime_on(transitions, on_date)
    regime = regimes[regime_id]
    missing = sorted(regime.route_ids - set(routes))
    if missing:
        raise KeyError(
            f"regime {regime.id!r} names route(s) {missing} that are not declared. A regime "
            f"selects from the declared routes; it does not declare any of its own. Known "
            f"routes: {sorted(routes)}"
        )
    in_force = {route_id: routes[route_id] for route_id in sorted(regime.route_ids)}
    orphaned = sorted(
        f"{route.id} -> {route.partner_route}"
        for route in in_force.values()
        if route.partner_route is not None and route.partner_route not in in_force
    )
    if orphaned:
        raise ValueError(
            f"regime {regime.id!r} includes route(s) whose declared exit route it excludes: "
            f"{orphaned}. Costing one would raise on the dangling partner and blame the "
            f"loader. A regime cannot make money one-way -- 'there is a way in and none out' is "
            f"a route declaring ``partner_route = null``, which is a fact about the corridor "
            f"with a source, so a regime with only one direction of a corridor is expressed as "
            f"a separately declared pair rather than as half of this one (FR-027)"
        )
    return RoutesInForce(
        on_date=on_date,
        regime=regime,
        decided_by=decided_by,
        routes=in_force,
        excluded=tuple(sorted(set(routes) - regime.route_ids)),
    )


def paths_in_force(paths: Sequence[Candidate], in_force: RoutesInForce) -> tuple[Candidate, ...]:
    """The candidate funding paths whose route the regime includes, in the order given.

    Needed because ``rank`` and ``cost_one`` take a ``routes`` mapping and *raise* on a path
    naming a route that is not in it -- correctly, since a path is built from declared routes.
    Narrowing the routes without narrowing the paths would turn a regime into that raise, with a
    message blaming a load-time resolver for a scenario's belief.

    It filters, and the filtering is not silent: what it removes is exactly the routes named in
    :attr:`RoutesInForce.excluded`, reported beside the transition that excluded them. Keeping
    the regime *outside* ``rank`` is deliberate -- an assumed exclusion arriving in
    ``Ranking.excluded``, whose records name a declared field as the binding constraint, would
    be indistinguishable from an observed one (research.md D8).

    **Every segment of a composed candidate must be in force, not merely the first** (004
    FR-017). A chain that connected by mixing a wartime corridor with a post-war one would be a
    journey nobody believes in under either regime, and it is the ``all`` below rather than a
    comment that stops it. A declared route is a chain of one, so nothing about 002's behaviour
    changes here.
    """
    return tuple(
        path for path in paths if all(route_id in in_force.routes for route_id in segments_of(path))
    )
