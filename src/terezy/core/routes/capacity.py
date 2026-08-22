"""Monthly capacity: whose limit it is, how much of it is left, and what happens to the rest.

FR-012: *declared caps, minimums, latency and status MUST be enforced. Total deployed MUST
equal what the route allows, never what the plan requested.* FR-013: *when a contribution
cannot execute, the declared fallback policy MUST be applied and **every occurrence MUST be
reported** with its date, amount and reason.* FR-015: *a monthly ceiling MUST account for
capacity already consumed in the same month.*

## A cap belongs to a shared rail, not to a route (research.md D10)

The accumulator keys on ``(capacity_pool, year, month)`` and **never** on the route. A limit
is a property of the *rail* -- a card, an account, a corridor under a regulatory ceiling --
and a route is a path that *uses* rails. Two different routes both moving money through the
owner's Monobank card consume **one** limit, and keying on the route would give each its own
full monthly allowance. Monobank's monthly limit is one of the four figures
``SIMULATOR_SPEC.md`` §11 item 1 names as the reason this feature exists, so a model that
cannot express it is not missing a nicety: it fails at the feature's own purpose.

Keying on the route was the first design. It was corrected before any of this code existed,
and :class:`CapacityKey` carries no route field so it cannot come back by accident.

## No clock (research.md D7)

The month comes from a date that arrives as **data** -- an event's ``occurred_on``, or the
``on_date`` a plan is dated. ``datetime.now`` is blocked in ``core`` by ``.importlinter``,
and that prohibition is not an inconvenience worked around here: it is what makes a run
reproducible. Remaining headroom is ``cap - consumed``, passed explicitly to whoever decides
feasibility, so FR-015's "capacity already consumed in the same month" is the ordinary path
rather than a special case.

The accumulator is one more mapping in the fold that already accumulates cash balances per
currency: ``LedgerState.capacity``, updated in ``ledger.engine.apply`` from each event's
``capacity_pool`` and ``occurred_on``.

## Where the cap is *not* consulted, and why

**Not in ``cost_one``.** A declared cap does not make a route unusable -- it makes the route
unable to carry the whole amount *at once*, and the answer to that is FR-013's fallback, not
a refusal. Refusing would deploy nothing, which is the exact opposite of SC-007's *"a plan
exceeding a monthly cap deploys exactly the cap"*. So ``cost_one`` reports the declared
ceiling (``RampCost.ceiling``) and this module decides what fits, which is also what that
field's own docstring already says: the largest amount that may be *sent* depends on how much
of the month is already gone, and that figure is the accumulator's.

## Three fallbacks, not four (FR-013)

Of ``SIMULATOR_SPEC.md`` §4.3.4's four policies this feature implements **hold as cash,
redirect and skip**. *Place on deposit* needs a deposit instrument and this feature adds no
instruments; declaring it and quietly treating it as "hold as cash" would be a substituted
default, so it is refused by name, saying which feature will bring it.

"Queue" in §4.3.4 and in required test **G3** is the same thing as *hold as cash* -- §4.3.4's
own wording is "queue as UAH cash". It does **not** mean carrying the excess into next
month's capacity, which nothing in the specification asks for and which no policy in the
closed set expresses.

Free functions over frozen records (owner decision D-E). No ``Money`` is constructed here:
every amount is derived through ``core.primitives.money``, which is how a declared cap's
provenance reaches the headroom computed from it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

from terezy.core.primitives import money
from terezy.core.primitives.money import Money
from terezy.core.routes.legs import Route


@dataclass(frozen=True, slots=True)
class CapacityKey:
    """What a consumed-capacity total is keyed by: a rail and a calendar month.

    **Three fields, and no route.** See the module docstring: the fourth field a reader most
    wants to add here is ``route_id``, and adding it would restore the defect this record was
    reshaped to remove. A property test asserts the field set is exactly these three.
    """

    pool: str
    """The shared rail whose limit is being consumed -- a ``Leg.capacity_pool`` id."""

    year: int
    """Calendar year of the movement, from its date. Part of the key so that March 2026 and
    March 2027 are different months rather than one recurring one."""

    month: int
    """Calendar month, ``1``--``12``. A *calendar* month rather than a rolling window: the
    declaration says "per month", and a rolling window would need a length nobody stated."""


CapacityUsed = Mapping[CapacityKey, Money]
"""How much each rail has already carried in each month.

A ``Mapping`` rather than a ``dict`` because a caller reads it and does not write it; every
function below returns a new one. An **absent** key means that rail carried nothing that
month, which is a different claim from a zero and is why :func:`consumed` returns ``None``
rather than conjuring one: a mapping that held a zero for every (rail, month) the calendar
allows would be mostly fiction.
"""

NOTHING_CONSUMED: Final[CapacityUsed] = {}
"""The empty accumulator: nothing has moved yet.

Named so that a call site passing it is *stating* that no capacity has been consumed rather
than omitting an argument. An input that means "nothing yet" and an input nobody supplied are
different things, and only one of them is honest.
"""


def key_for(pool: str, on_date: date) -> CapacityKey:
    """The accumulator key for one rail on one date.

    The month is read off the date, which arrived as data. There is no clock here and none is
    reachable from ``core``: every date in this system is an input to the run and is recorded
    in the manifest, which is what makes the same scenario produce the same verdicts forever.
    """
    return CapacityKey(pool=pool, year=on_date.year, month=on_date.month)


def consumed(used: CapacityUsed, key: CapacityKey) -> Money | None:
    """What this rail has already carried in this month, or ``None`` if it carried nothing.

    ``None`` rather than a zero, deliberately. "This rail moved nothing in March" and "this
    rail's March total happens to be zero" are the same number and different facts, and only
    the first can be stated without a currency -- a zero would have to pick one, and the only
    honest source for it is the cap the headroom is measured against.
    """
    return used.get(key)


def remaining(cap: Money, used: Money | None) -> Money:
    """``cap - used`` -- what the rail will still carry this month.

    **Not floored at zero.** A rail already over its declared cap reports a negative
    headroom, and that reads as the diagnostic it is. Flooring it would be predecessor defect
    **B13** in a new place: the figures would look sane and the overrun would be invisible.
    """
    return cap if used is None else money.sub(cap, used)


def headroom(used: CapacityUsed, *, pool: str, cap: Money, on_date: date) -> Money:
    """The rail's remaining capacity in the month ``on_date`` falls in.

    :func:`key_for`, :func:`consumed` and :func:`remaining` in one call, because those three
    always go together and a caller composing them by hand is a caller who can compose them
    wrongly -- keying on the wrong month, or subtracting in the wrong direction.
    """
    return remaining(cap, consumed(used, key_for(pool, on_date)))


def record(used: CapacityUsed, *, pool: str, amount: Money, on_date: date) -> CapacityUsed:
    """The accumulator with ``amount`` added to this rail's total for this month.

    A new mapping; nothing given to this function is mutated. The magnitude is taken as
    supplied: the caller decides what counts as consumption, and for a ledger event that is
    the size of the movement rather than its sign (see ``ledger.engine.apply``).
    """
    key = key_for(pool, on_date)
    existing = used.get(key)
    return {**used, key: amount if existing is None else money.add(existing, amount)}


@dataclass(frozen=True, slots=True)
class PoolCapacity:
    """One rail and the monthly limit it declares.

    The two are one record because a limit with no rail has nowhere to accumulate. A leg
    declaring a ``monthly_cap`` and no ``capacity_pool`` therefore cannot be represented here
    at all, and :func:`caps_of` refuses it rather than inventing a key -- the same shape as an
    ``fx`` leg declaring no channel, which ``legs`` refuses rather than inventing a rate.
    """

    pool: str
    """The rail's id, shared by every leg that consumes its limit."""

    cap: Money
    """The most this rail carries in a calendar month, as declared."""


def caps_of(route: Route) -> tuple[PoolCapacity, ...]:
    """The rails this route consumes, one entry per rail, in first-declaration order.

    **One entry per rail and not per leg**, because the limit belongs to the rail: a route
    whose transfer leg and fx leg both run over one card consumes that card's limit once, and
    reporting it twice would invite a caller to subtract it twice.

    Two failures, both raised rather than returned:

    * **A cap with no pool.** There is no key to accumulate it under, so FR-015 could not
      apply to it -- the leg would silently receive its full cap every time it was consulted.
      D10's own argument is that a pool is a fact about the world and must be *declared*
      rather than inferred, and that applies to a rail used by one leg exactly as it applies
      to one shared by two.
    * **Two legs naming one pool with different caps.** Two numbers for one real limit means
      at least one of them is wrong, and picking either silently would be a guess (D10).

    Both are structural properties of a declaration, knowable with no amount and no date, so
    the resolver checks them at load where the error can name the file and the leg index
    (research.md D6). Reaching here means that validation was bypassed, which is a programmer
    error rather than a fact about the money -- hence a raise.
    """
    found: dict[str, PoolCapacity] = {}
    for leg in route.legs:
        if leg.monthly_cap is None:
            continue
        if leg.capacity_pool is None:
            raise ValueError(
                f"leg {leg.index} of route {route.id!r} declares a monthly cap of "
                f"{leg.monthly_cap.amount!r} {leg.monthly_cap.currency.value} and no "
                "capacity_pool. A monthly limit belongs to a rail, and without a rail there "
                "is no key to accumulate it under -- so capacity already consumed in the "
                "same month could never reduce it (FR-015). Declare the pool, even where "
                "only this leg uses it: a pool is a fact about the world and is declared "
                "rather than inferred (research.md D10)."
            )
        seen = found.get(leg.capacity_pool)
        if seen is not None and money.compare(seen.cap, leg.monthly_cap) != 0:
            raise ValueError(
                f"legs of route {route.id!r} disagree about the monthly cap on pool "
                f"{leg.capacity_pool!r}: {seen.cap.amount!r} {seen.cap.currency.value} and "
                f"{leg.monthly_cap.amount!r} {leg.monthly_cap.currency.value} at leg "
                f"{leg.index}. Two numbers for one real limit means at least one is wrong, "
                "and choosing either would be a guess (research.md D10)."
            )
        if seen is None:
            found[leg.capacity_pool] = PoolCapacity(pool=leg.capacity_pool, cap=leg.monthly_cap)
    return tuple(found.values())


FallbackPolicy = Literal["hold_as_cash", "redirect", "skip"]
"""What happens to a contribution the route will not carry.

A ``Literal`` and not a ``str``, so a misspelt policy is a type error rather than a plan whose
excess quietly went nowhere. Three members, which is three of ``SIMULATOR_SPEC.md`` §4.3.4's
four -- see :data:`DEFERRED_POLICIES`.
"""

HOLD_AS_CASH: Final[FallbackPolicy] = "hold_as_cash"
"""Keep the excess as cash in the currency it is already in.

§4.3.4 also calls this "queue as UAH cash", and required test **G3** calls it "queue". It is
the same policy under three names, and it does **not** mean carrying the excess into next
month's capacity: nothing in the specification asks for that, and no policy in the closed set
expresses it.
"""

REDIRECT: Final[FallbackPolicy] = "redirect"
"""Send the excess to a named alternative destination. The name is required, not optional."""

SKIP: Final[FallbackPolicy] = "skip"
"""Do not deploy the excess at all. The occurrence is still reported (FR-013)."""

POLICIES: Final[tuple[FallbackPolicy, ...]] = (HOLD_AS_CASH, REDIRECT, SKIP)
"""Every policy this feature implements. The tuple is the whole contract."""

DEFERRED_POLICIES: Final[Mapping[str, str]] = {
    "place_on_deposit": (
        "placing the excess on deposit requires a deposit instrument, and this feature adds "
        "no instruments. It will arrive with the instrument that pays a deposit rate; until "
        "then a plan naming this policy fails rather than being treated as 'hold as cash', "
        "which would be a substituted default for a policy the owner explicitly chose "
        "(FR-013)"
    )
}
"""The §4.3.4 policy this feature knows about and does **not** implement, with what it needs.

Named rather than merely absent. An unrecognised policy and a policy that is real but not
built yet are different facts, and the owner acts differently on each: one is a typo, the
other is a wait. A message that could not tell them apart would send him looking for the
first when it was the second.
"""


def policy_for(name: str) -> FallbackPolicy:
    """The declared fallback policy a name selects, or a raise saying why not.

    An explicit membership walk rather than a ``get`` with a default, so no reading of this
    code suggests a default policy exists. There is none: the whole point of FR-013 is that
    what happens to money the route would not carry is a decision the owner made, and
    substituting one would be the silent default the constitution puts at top severity.
    """
    for policy in POLICIES:
        if name == policy:
            return policy
    deferred = DEFERRED_POLICIES.get(name)
    if deferred is not None:
        raise ValueError(f"fallback policy {name!r} is not implemented: {deferred}")
    raise KeyError(
        f"unknown fallback policy {name!r}. There is no default policy: what happens to a "
        f"contribution the route will not carry is the owner's decision, and substituting "
        f"one would execute a plan he did not write. Known policies: {sorted(POLICIES)}"
    )


@dataclass(frozen=True, slots=True)
class FallbackApplied:
    """One occurrence of a fallback: what was displaced, when, under which policy, and why.

    **Every occurrence is a record, and every record appears in the output** (FR-013). A
    silently executed infeasible plan is a defect of the highest severity (Principle VI), so
    there is no aggregate here and no count -- an aggregate is what a reader skims past, and a
    dated line naming an amount is what he acts on.
    """

    occurred_on: date
    """The date of the contribution that could not be deployed in full."""

    amount: Money
    """How much was displaced. In the currency the contribution was stated in."""

    policy: FallbackPolicy
    """Which of the three declared policies handled it."""

    reason: str
    """Plain language: what bound, and by how much. For the output a human reads (FR-017)."""

    redirect_to: str | None
    """The destination the excess was sent to, **required** when :attr:`policy` is
    ``redirect`` and ``None`` otherwise.

    FR-013 says "redirect to a **named** destination", so the name is part of the record
    rather than prose inside :attr:`reason`: a caller grouping occurrences by where the money
    actually went should not have to parse a sentence to do it.
    """


@dataclass(frozen=True, slots=True)
class Deployment:
    """What a contribution actually did: how much went, and what happened to the rest.

    ``requested`` and ``deployed`` are both here because FR-012 is written as the gap between
    them -- *"total deployed MUST equal what the route allows, never what the plan
    requested"*. A record holding only the deployed figure would satisfy the requirement while
    making it uncheckable.
    """

    requested: Money
    """What the plan asked to deploy."""

    deployed: Money
    """What the rail's remaining capacity allowed. Equal to :attr:`requested` when nothing
    bound.

    **Not floored at zero.** A rail already over its cap yields a negative figure, and that is
    reported rather than hidden: see :func:`deploy`.
    """

    fallbacks: tuple[FallbackApplied, ...]
    """Every occurrence, in order. Empty when the whole request was deployed."""


def deploy(
    requested: Money,
    *,
    limit: PoolCapacity | None,
    used: CapacityUsed,
    policy: str,
    on_date: date,
    redirect_to: str | None,
) -> Deployment:
    """Deploy what the rail will carry this month, and report what it will not.

    ``limit`` is ``None`` when no leg of the route declares a cap, and then the whole request
    is deployed with no fallback. That is not a permissive default: an undeclared cap is the
    *least* constrained a route can be, and inventing one would refuse money the declaration
    does not refuse.

    The three implemented policies all deploy the **same** amount -- what the rail allows --
    and differ in what the record says became of the excess. That is deliberate and is stated
    rather than hidden: the amount a rail carries is a fact about the rail, and the policy is
    a decision about the remainder. What this feature can honestly do with the remainder is
    *record* it, with its date, its amount and its reason; moving it to a second destination
    or holding it as a cash position are actions for the layer that owns a portfolio.

    ``redirect_to`` is required with the ``redirect`` policy and forbidden with the other two.
    A redirect with no destination is a plan with a hole in it, and accepting one would let
    the excess vanish into a policy name.

    **Nothing is clamped.** If the rail is already over its cap the headroom is negative,
    :attr:`Deployment.deployed` is negative, and the fallback amount consequently exceeds the
    request. Every one of those figures is reported. A floor at zero would read as tidier and
    would hide an overrun that some earlier movement caused -- predecessor defect **B13** is
    exactly that instinct applied to a fee.
    """
    chosen = policy_for(policy)
    if chosen == REDIRECT and redirect_to is None:
        raise ValueError(
            "the 'redirect' fallback policy requires the destination it redirects to: "
            "FR-013 says redirect to a *named* destination, and a redirect with no name "
            "would let the excess disappear into a policy label"
        )
    if chosen != REDIRECT and redirect_to is not None:
        raise ValueError(
            f"fallback policy {chosen!r} names a redirect destination {redirect_to!r}, but "
            "only 'redirect' sends the excess anywhere. Accepting it would suggest a "
            "movement that does not happen."
        )
    if limit is None:
        return Deployment(requested=requested, deployed=requested, fallbacks=())

    available = headroom(used, pool=limit.pool, cap=limit.cap, on_date=on_date)
    if money.compare(requested, available) <= 0:
        return Deployment(requested=requested, deployed=requested, fallbacks=())

    already = consumed(used, key_for(limit.pool, on_date))
    excess = money.sub(requested, available)
    spent = 0.0 if already is None else already.amount
    reason = (
        f"rail {limit.pool!r} carries no more than {limit.cap.amount!r} "
        f"{limit.cap.currency.value} in the month of {on_date.isoformat()}; "
        f"{spent!r} was already consumed in that month, leaving {available.amount!r}. The "
        f"plan asked for {requested.amount!r}, so {excess.amount!r} could not be deployed "
        f"and was handled by the {chosen!r} policy."
    )
    return Deployment(
        requested=requested,
        deployed=available,
        fallbacks=(
            FallbackApplied(
                occurred_on=on_date,
                amount=excess,
                policy=chosen,
                reason=reason,
                redirect_to=redirect_to,
            ),
        ),
    )
