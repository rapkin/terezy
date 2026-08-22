"""``rank``: cost every candidate with ``cost_one``, then order them. No second arithmetic.

FR-016: *given an amount and a destination, the system MUST rank the available routes
**lexicographically** on ``(round-trip cost, ceiling descending, latency)``, recommend one, and
report what each alternative would have cost. Route choice is a modelled comparison, never a
configuration constant.*

This module has no arithmetic in it. It calls :func:`terezy.core.routes.cost.cost_one` once per
candidate, sorts what comes back, and reports what it could not rank. That is the whole
implementation, and its plainness is the requirement rather than a happy accident: FR-029 says
every candidate must be costed *through the same path as the recommendation*, and the cheapest
way to guarantee that is to have nowhere else for a cost to come from. A contract test scans
this module's source for ``money.*``, for a channel function and for the leg registry, and
fails on any of them.

## Lexicographic, not scored

The three keys are applied **in order** -- cheaper first; among equally cheap routes the one
with the larger ceiling; among those the faster one -- and never combined into a single
number. Required test **B12** forbids a non-standard composite score from driving the primary
ordering, and the reason is not stylistic: a weighted score would have to state how many
hryvnia a day of latency is worth, and that is a *preference* of the owner's rather than a fact
about the money. FR-016 already put the three keys in priority order, so they are applied in
that order. Ordering them is a fact; weighting them would be a guess wearing a decimal point.

## Which figure is "the cost"

:attr:`RoundTripCost.fraction` -- the round trip, never the one way (FR-002). Round-trip cost
is what belongs in a comparison, because an asset that cannot be liquidated into spendable base
currency at a reasonable cost is not worth its stated value (Principle VI), and the way out is
where the second spread lives.

The *fraction* rather than the absolute figure, for one reason worth stating: every candidate
was sent the same amount, so ``cost / sent`` and ``cost`` induce the identical ordering, and
the fraction is the figure the engine already computed and stored on the result. Re-deriving an
absolute total here to sort by would mean this module held a number of its own -- small,
correct today, and exactly the seam FR-029 exists to close.

## Ties, and what a tie is decided on

**Round-trip cost alone** (FR-018). Two routes costing the same within the project tolerance
are tied even where their ceilings and latencies differ, and the tie is reported. The owner
asked which is cheapest; "these two cost the same, and here is how they differ" answers that,
while silently preferring one on a tiebreak he did not ask for does not.

The ordering still uses all three keys, so the sequence is deterministic and reproducible --
:attr:`Ranking.ties` is what stops the head of that sequence being read as a strict winner.
Both things are true at once, and they have to be: FR-016 wants a defined order and FR-018
wants no invented preference.

## What is ranked, and what is only reported

* A candidate that cannot carry the amount is a ``RouteUnusable`` and goes to
  :attr:`Ranking.excluded`, carrying the constraint that bound it (FR-014). Never dropped: a
  silent exclusion is how a comparison comes to recommend the only route left standing.
* A candidate whose round trip is ``ExitCostUnknown`` goes to
  :attr:`Ranking.not_comparable` (FR-030). It is costed and reported; it is not ranked, and
  its one-way figure is not promoted into the missing round-trip slot.
* Everything else is ranked.

Every candidate lands in exactly one of the three, which a contract test asserts by counting.

## Purity, and the two dates

Pure: no clock, no I/O, no state, and the sort is stable, so equal keys keep the order the
caller supplied them in. ``on_date`` is when the money moves and ``as_of`` is when the question
is asked, exactly as in ``cost_one`` -- conflating them would report every input of a
projection as stale by years.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date
from typing import assert_never

from terezy.core.primitives.money import Money
from terezy.core.primitives.staleness import ObservationKind
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.ramp import (
    NothingComparable,
    RampCost,
    Ranking,
    RoundTripCost,
    RouteUnusable,
)
from terezy.core.routes import cost
from terezy.core.routes.channels import FxChannel
from terezy.core.routes.legs import Route
from terezy.core.routes.path import FundingPath

_Comparable = tuple[RampCost, RoundTripCost]
"""A candidate paired with its narrowed round-trip figure.

The pair exists so the sort key can read ``RoundTripCost.fraction`` without a cast: the split
below already established that this candidate's ``round_trip`` is a figure rather than an
``ExitCostUnknown``, and carrying the narrowed value forward is how that knowledge survives to
the comparison.
"""


def _ceiling_key(ceiling: Money | None) -> float:
    """The second sort key: ceiling, **descending**, with no declared cap sorting first.

    Negated because :func:`sorted` ascends and FR-016 asks for descending on this key. The
    negation is applied to a sort key and not to a reported figure, which is why a raw float is
    the right thing here -- there is no money being produced, so there is no provenance to
    carry and nothing for ``money.scale`` to do.

    ``None`` means **no leg of the route declares a monthly cap**, which is the least
    constrained a route can be, so it sorts ahead of every finite ceiling. That reading matters
    because the alternative -- treating an absent cap as zero -- would rank the freest route
    last while looking like a sensible default for a missing value. ``Leg.monthly_cap`` is
    ``None`` when no cap was declared rather than when one is unknown, so this is not a
    permissive default standing in for missing data; it is the declared absence of a limit.
    """
    return -math.inf if ceiling is None else -ceiling.amount


def _order_key(entry: _Comparable) -> tuple[float, float, int]:
    """The three keys of FR-016, in the order FR-016 put them, as a tuple.

    A tuple compared element by element **is** lexicographic ordering, which is why there is no
    combining step to review here: Python's tuple comparison only looks at the second key when
    the first ties, and at the third when the first two do. That is the property **B12**
    requires and a composite score would destroy.
    """
    candidate, round_trip = entry
    return (round_trip.fraction, _ceiling_key(candidate.ceiling), candidate.latency_days)


def _ties(ordered: Sequence[_Comparable]) -> tuple[tuple[int, ...], ...]:
    """Groups of indices whose round-trip cost is the same within the project tolerance.

    On round-trip cost **alone** (FR-018): the ceilings and latencies that ordered the sequence
    play no part in deciding what is tied.

    **Grouped against each group's first member rather than chained neighbour to neighbour**,
    and the choice is forced. Tolerance-based equality is not transitive -- ``a ~ b`` and
    ``b ~ c`` does not give ``a ~ c`` -- so some rule has to be picked. Chaining would let a
    band of arbitrary width become one tie as candidates accumulate, which is the tolerance
    absorbing a real difference: exactly the "defect wearing a green tick" the tolerance module
    warns about. Anchoring bounds every reported tie at one tolerance wide.

    The sequence is sorted, so tied entries are adjacent and one pass suffices. Groups of one
    are not ties and are not reported.
    """
    groups: list[tuple[int, ...]] = []
    current: list[int] = []
    anchor: float | None = None
    for index, (_, round_trip) in enumerate(ordered):
        if anchor is not None and is_close(round_trip.fraction, anchor):
            current.append(index)
            continue
        if len(current) > 1:
            groups.append(tuple(current))
        anchor = round_trip.fraction
        current = [index]
    if len(current) > 1:
        groups.append(tuple(current))
    return tuple(groups)


def _nothing_comparable(
    excluded: tuple[RouteUnusable, ...], not_comparable: tuple[RampCost, ...]
) -> NothingComparable:
    """The typed statement that there was nothing to rank, naming why there was not.

    Three distinguishable situations, and they are not interchangeable: no candidate was
    offered at all; every candidate was refused; every candidate lacks a declared exit route.
    The owner acts differently on each -- the second is about limits and dates, the third about
    a declaration nobody has written yet -- so the reason says which rather than reporting an
    empty ranking and leaving the reader to infer it.
    """
    if not excluded and not not_comparable:
        reason = (
            "no candidate paths were offered, so there is nothing to rank. This is not a "
            "ranking in which every route cost the same; it is the absence of a question."
        )
    elif not not_comparable:
        reason = (
            f"all {len(excluded)} candidate route(s) were refused, so none could carry the "
            "amount on the date; each carries the constraint that bound it (FR-014). No "
            f"route is recommended: {'; '.join(item.reason for item in excluded)}"
        )
    elif not excluded:
        reason = (
            f"all {len(not_comparable)} candidate route(s) were costed but none has a "
            "declared exit route, so none has a round-trip figure and none is "
            "comparison-ready (FR-030). The one-way figures are reported and are not "
            "promoted into the round-trip slot."
        )
    else:
        reason = (
            f"{len(excluded)} candidate route(s) were refused and {len(not_comparable)} were "
            "costed without a declared exit route, so nothing remained to rank. Both groups "
            "are reported with their reasons (FR-014, FR-030)."
        )
    return NothingComparable(reason=reason, excluded=excluded, not_comparable=not_comparable)


def rank(
    paths: Sequence[FundingPath],
    amount: Money,
    *,
    routes: Mapping[str, Route],
    channels: Mapping[str, FxChannel],
    kinds: Mapping[str, ObservationKind],
    on_date: date,
    as_of: date,
) -> Ranking | NothingComparable:
    """Cost every path with ``cost_one`` and order the comparable ones. FR-016, FR-018, FR-029.

    One amount for every candidate, because a comparison of costs at different amounts is not a
    comparison. The amount is a separate argument from the paths for the same reason
    ``FundingPath`` carries no amount: a path is *which way* and an amount is *how much*.

    Returns a :class:`Ranking` whose ``recommended`` index is always valid, or
    :class:`NothingComparable` when no candidate was comparison-ready -- see that record for why
    the empty case is a separate type rather than an absent index.

    **The signature is ``cost_one``'s**, and the two inputs
    ``contracts/route-costing.md`` also names for both functions -- ``streams`` and
    ``capacity_used`` -- are absent here for the same stated reason they are absent there.
    ``streams`` arrives with User Story 2 and ``capacity_used`` with User Story 3; both are
    feasibility inputs that produce more ``RouteUnusable`` reasons, and neither changes an
    arithmetic. Adding them extends both signatures together, which is the only way they can be
    added without creating the second code path FR-029 forbids.
    """
    comparable: list[_Comparable] = []
    excluded: list[RouteUnusable] = []
    not_comparable: list[RampCost] = []
    for path in paths:
        outcome = cost.cost_one(
            path,
            amount,
            routes=routes,
            channels=channels,
            kinds=kinds,
            on_date=on_date,
            as_of=as_of,
        )
        match outcome:
            case RouteUnusable():
                excluded.append(outcome)
            case RampCost(round_trip=RoundTripCost() as round_trip):
                comparable.append((outcome, round_trip))
            case RampCost():
                not_comparable.append(outcome)
            case _:  # pragma: no cover -- mypy proves this unreachable
                assert_never(outcome)
    if not comparable:
        return _nothing_comparable(tuple(excluded), tuple(not_comparable))
    ordered = sorted(comparable, key=_order_key)
    return Ranking(
        costed=tuple(candidate for candidate, _ in ordered),
        # The head of the ordered sequence. Stated as an index into what was ranked rather
        # than as the entry itself, so the recommendation cannot be a second figure (FR-029).
        recommended=0,
        excluded=tuple(excluded),
        ties=_ties(ordered),
        not_comparable=tuple(not_comparable),
    )
