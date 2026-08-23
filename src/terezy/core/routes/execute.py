"""``execute``: the ledger events a costed ramp produces. Derived, never recomputed.

FR-005: *costs MUST NEVER be silently clamped. If fees exceed the amount, the system reports
that; the money never vanishes without a diagnostic. **Every fee is an explicit recorded
line**, never blended into the outcome.*

## Why this is a second function and not part of ``cost_one`` (research.md D5)

FR-005 wants every fee in the ledger. But a comparison costs *many* routes and only **one** is
executed, so writing events for every candidate would put fees in the ledger for money that
never moved -- and cash conservation (C1) would have to learn about hypothetical events. So
there are two functions and one arithmetic:

* ``cost_one(path, amount, ...) -> RampCost`` -- pure, no ledger, run for every candidate;
* ``execute(cost, ...) -> tuple[Event, ...]`` -- one fee event per fee-bearing component.

**This function takes the costed figure and nothing else that could price anything.** No
``Route``, no ``Leg``, no ``FxChannel``, no amount. That is the whole guarantee: there is no
arithmetic here that *could* drift from ``cost_one``, because there is nothing here to compute
a cost from. Research.md D5 first wrote ``execute(path, amount, as_of)``, which contradicted
its own conclusion -- taking the path and the amount is exactly the second code path the
decision exists to forbid -- and ``contracts/route-costing.md`` had it right.

The agreement is asserted rather than assumed, in
``tests/invariants/test_cost_execute_agreement.py``:

```
sum(fee events from execute(c)) == sum(c.one_way.components.values())
```

plus the arriving amount in the ledger equalling ``c.one_way.arrived``, currency and all.

## What is emitted, in this order

1. **The departure.** A ``RAMP_MOVEMENT`` for what actually crossed -- ``sent`` less the
   components -- negative, in the sending currency. It is first because it is the **anchor**
   the fee lines are allocated to, and ``events.allocated_fees`` refuses a fee that names no
   target: a fee reducing cash while naming nothing would report a gain gross of a cost that
   was really paid.
2. **One fee line per fee-bearing component**, negative, in the sending currency, each
   allocated to the departure. A component the route declared as *zero* gets no line: the zero
   is already in the ``RampCost``, citing the declaration that says this route charges nothing
   there (FR-009), so a zero ledger line would add no fact and would make the zero-cost
   domestic route emit three of them. (The contrast with a zero *tax charge*, which **is** an
   event, is deliberate: that zero is the only record that the rule ran at all.)
3. **The arrival.** A ``RAMP_MOVEMENT`` for ``c.one_way.arrived``, positive, in the
   destination currency.

**Why the crossing is a pair.** The cash accounts here are per *currency*, and a conversion
touches two of them; one event cannot be in two currencies, and inventing a rate to express it
as one is what FR-010 forbids. On a route that converts nothing the pair is in a single
currency and nets to zero -- which is the honest record, because the money moved between
*venues* and this ledger has no venue dimension. Emitting one event in that case would be a
second code path for the same movement.

**The arithmetic here is one subtraction and three negations**, all over figures the
``RampCost`` already holds. The departure is ``sent - components``, which is what the arriving
amount is worth in the sending currency at the reference rate -- the same identity the
attribution invariant asserts from the other side. It is a *derivation* from the costed
figure, not a re-pricing: no rate, no channel and no leg is consulted.

## Nothing is clamped (B13)

If the fees exceeded the amount, ``c.one_way.arrived`` is zero or negative and the arrival
event records it as such. The departure then has the opposite sign, which reads oddly and is
correct: more was charged than crossed. Predecessor defect **B13** was a ``max(gross - fee,
0)`` that made money vanish with no diagnostic, and no figure here is floored.

Free functions over frozen records (owner decision D-E). No ``Money`` is constructed here:
every amount is derived through ``core.primitives.money``, so an unverified premium's mark
reaches the ledger line it paid for.
"""

from __future__ import annotations

from datetime import date

from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind
from terezy.core.primitives import money
from terezy.core.primitives.money import Money
from terezy.core.results.ramp import CostComponent, RampCost
from terezy.core.routes.path import candidate_id, segments_of

COMPONENT_DETAIL: dict[CostComponent, str] = {
    CostComponent.CONVERSION_SPREAD: (
        "the spread paid to the channel that converted the money -- the term "
        "SIMULATOR_SPEC.md §4.3.1 is about"
    ),
    CostComponent.PERCENTAGE_FEE: "fees declared as a fraction of the amount moved",
    CostComponent.FIXED_FEE: "flat fees declared per movement",
}
"""Plain language per component, for the ``detail`` a human reads on the ledger line.

A mapping over the closed enumeration rather than a formatted member name: FR-005's "explicit
recorded line" is only explicit if a reader can tell what charged, and ``percentage_fee`` with
its underscore removed is a field name rather than an explanation. Every member has an entry,
and :func:`_detail` raises rather than falling back if one ever does not.
"""


def _detail(component: CostComponent) -> str:
    """The prose for one component, or a raise naming the gap.

    No default. A component with no explanation would produce a ledger line saying nothing
    about what charged, and a generic fallback is the shape that makes such a gap permanent.
    """
    if component not in COMPONENT_DETAIL:
        raise KeyError(
            f"cost component {component!r} has no recorded explanation, so a ledger line "
            f"for it would not say what charged (FR-005). Known: "
            f"{sorted(member.value for member in COMPONENT_DETAIL)}"
        )
    return COMPONENT_DETAIL[component]


def _cause(cost: RampCost, detail: str) -> CausationRef:
    """The route declaration that charged, in the form C6 can look up.

    ``ROUTE_TERM`` rather than ``INSTRUMENT_TERM`` or ``TAX_RULE``: a ramp fee is charged by
    neither, and making it claim one of those two would produce a traceable figure pointing at
    the wrong declaration -- worse than a widened set of causes, which is why ``CausationKind``
    gained a third member with this feature rather than this module borrowing an existing one.

    **A composed candidate names its whole chain**, joined by ``+`` (004 FR-013). A declared
    route is one id and every event feature 002 emitted is unchanged. For a chain the ``id`` is
    every segment in order, because the charge this line records is the **chain's**: the events
    below carry one figure per component for the whole movement, and naming one segment for a
    fee several of them contributed to would point a reader at the wrong declaration. Which
    segment charged what is on the cost itself, in ``RampCost.one_way.by_segment``, and the
    ``detail`` says so in words.
    """
    segments = segments_of(cost.path)
    through = (
        f"route {segments[0]!r}"
        if len(segments) == 1
        else f"the chain {' -> '.join(segments)}, segment by segment in RampCost.by_segment"
    )
    return CausationRef(
        kind=CausationKind.ROUTE_TERM,
        id=candidate_id(cost.path),
        detail=(
            f"{detail}, funding {cost.path.destination_id!r} from stream "
            f"{cost.path.stream_id!r} by {through}"
        ),
    )


def _movement(
    cost: RampCost,
    amount: Money,
    *,
    sequence: int,
    owner_id: str,
    on_date: date,
    capacity_pool: str | None,
    detail: str,
) -> Event:
    """One half of the crossing: cash out of one currency, or cash into the other."""
    return Event(
        sequence=sequence,
        occurred_on=on_date,
        kind=EventKind.RAMP_MOVEMENT,
        amount=amount,
        owner_id=owner_id,
        caused_by=_cause(cost, detail),
        lot_ref=None,
        quantity=None,
        allocated_to=None,
        capacity_pool=capacity_pool,
    )


def execute(
    cost: RampCost,
    *,
    owner_id: str,
    sequence_from: int,
    on_date: date,
    capacity_pool: str | None,
) -> tuple[Event, ...]:
    """The ledger events one costed ramp produces, derived from the figure it was given.

    ``sequence_from`` is where the returned events' sequence numbers start, densely. Passed in
    rather than chosen, because the stream this movement joins is the caller's and
    ``events.in_sequence`` refuses a duplicate sequence outright -- a function that guessed at
    ``0`` would make every second execution unfoldable.

    ``on_date`` is when the movement is recorded. It is a parameter because a ``RampCost``
    carries no date: the date the money moves is an input to ``cost_one`` that selects a
    regime and a month, and duplicating it on the result would be two places for one fact.
    There is no clock to fall back on and none is reachable from ``core``.

    ``capacity_pool`` is the shared rail the sending side crossed, or ``None`` for a movement
    that crosses none, and it is **required** rather than defaulted: a rail whose limit is
    silently not consumed is a limit not enforced (FR-012, FR-015). It is passed in rather
    than read off the route because a ``RampCost`` does not carry the legs -- and inferring
    the rail from a route id or a venue pair is precisely the inference research.md D10
    rejected. It is named on the events denominated in the **sending** currency, the fees
    included: the fees came out of the money that crossed, so what the rail carried is the
    whole of ``sent``. The arrival is at the far end and consumes nothing on the sending rail.

    ⚙ **Where this differs from what a route with two rails needs.** One pool is named for the
    whole movement, so a route whose legs cross *different* rails cannot have its consumption
    attributed between them here -- that would need a movement event per leg, which this
    feature does not model. Splitting the amount between two pools by any rule available here
    would be inventing a number, so the caller names the rail whose limit the movement is
    measured against, and a genuinely multi-rail route is a gap stated rather than papered
    over. ``routes.capacity.caps_of`` enumerates a route's rails, so the caller can see when
    there is more than one.
    """
    total = money.total(cost.one_way.components.values(), cost.one_way.sent.currency)
    crossed = money.sub(cost.one_way.sent, total)
    departure = _movement(
        cost,
        money.scale(crossed, -1.0),
        sequence=sequence_from,
        owner_id=owner_id,
        on_date=on_date,
        capacity_pool=capacity_pool,
        detail="the amount that crossed the route, net of every charge attributed to it",
    )
    events: list[Event] = [departure]
    for component, charge in cost.one_way.components.items():
        if charge.amount == 0.0:
            continue
        events.append(
            Event(
                sequence=sequence_from + len(events),
                occurred_on=on_date,
                kind=EventKind.FEE,
                amount=money.scale(charge, -1.0),
                owner_id=owner_id,
                caused_by=_cause(cost, _detail(component)),
                lot_ref=None,
                quantity=None,
                allocated_to=departure.sequence,
                capacity_pool=capacity_pool,
            )
        )
    events.append(
        _movement(
            cost,
            cost.one_way.arrived,
            sequence=sequence_from + len(events),
            owner_id=owner_id,
            on_date=on_date,
            capacity_pool=None,
            detail="the amount that arrived at the far end of the route",
        )
    )
    return tuple(events)
