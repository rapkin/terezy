"""What a route costs: the result records, and the types that keep the labels honest.

FR-002: *the system MUST report cost both **one way** and **round trip**, each explicitly
labelled, and MUST NOT present a one-way figure where a round-trip figure belongs. Round-trip
cost is what belongs in a comparison.* FR-003 adds the attribution, FR-030 the missing-exit
case, FR-014 the unusable route.

Three design decisions are carried by the *shapes* here rather than by rules a reader has to
remember.

**One-way and round-trip are unrelated types** (research.md D4), on the precedent
``RealRate | RealTermsUnavailable`` set in feature 001. :class:`OneWayCost` and
:class:`RoundTripCost` share no base and no protocol, so assigning one into the other's slot
is a mypy strict error rather than a plausible line of code. They are field-for-field
similar, which is precisely why nothing weaker would do: no naming convention and no
inspection of their contents would catch the mix-up, because their contents are the same
shapes. Only their identities differ, and that is the guard.

**A missing exit route produces no number at all.** ``round_trip`` is typed
``RoundTripCost | ExitCostUnknown``, always present, never absent, and never a promoted
one-way figure (FR-030). The one-way figure is "most of" the cost and it is right there,
which is what makes the promotion tempting; it would produce a confident round-trip number
for an exit path nobody has ever looked at, and Principle VI says an asset that cannot be
liquidated into spendable base currency at a reasonable cost is not worth its stated value.

**The component set is closed.** :class:`CostComponent` is an enumeration of three members,
not a ``dict[str, Money]``. A free-form mapping would let a leg invent a component name, and
then "the components sum to the total" -- the invariant behind FR-003 -- would be satisfiable
by a cost hiding under a key nobody sums. A closed set makes the sum checkable, which is the
whole point of attributing cost in the first place: the sentence this feature exists to let
the tool write is *"most of the gap is the ramp, not the asset"*, and a reader can only
believe it if the terms add up.

**Every cost is keyed by a ``FundingPath``.** Not by a destination (FR-008): the same
acquisition is nearly free from the USD stream and 5-10% from the UAH one, and a figure that
cannot say which stream paid for the trip is not a figure about anything.

**Formatting is not a result** (this package's standing rule). No percent signs, no currency
symbols, no rounding for display. :attr:`OneWayCost.fraction` is a fraction, and it may
exceed ``1.0``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.staleness import StalenessVerdict
from terezy.core.routes.legs import RouteStatus
from terezy.core.routes.path import FundingPath


class CostComponent(Enum):
    """What a route charged, split into the three terms that can charge anything.

    A **closed** enumeration. Adding a fourth term is a code change reviewed against the
    invariant that the components sum to the total, which is the review a free-form mapping
    would have skipped.

    Deliberately not a ``str`` subclass: a string-valued enum compares equal to a bare
    string, which would let ``"conversion_spread"`` occupy a position that should require a
    member and defeat the point of closing the set (the same argument as
    ``primitives.currency``).
    """

    CONVERSION_SPREAD = "conversion_spread"
    """What the channel's spread cost -- the term §4.3.1 is about, and usually the largest."""

    PERCENTAGE_FEE = "percentage_fee"
    """Fees declared as a fraction of the amount moved."""

    FIXED_FEE = "fixed_fee"
    """Flat fees. The term that makes a small transfer's cost fraction exceed ``1.0``."""


@dataclass(frozen=True, slots=True)
class OneWayCost:
    """What it costs to get money **in**: from the stream's venue to the destination.

    Unrelated to :class:`RoundTripCost` by design. See the module docstring.
    """

    sent: Money
    """What departed, in the funding stream's currency. Every figure below is measured
    against it, and it is the base currency of :attr:`components`."""

    arrived: Money
    """What reached the far end, in the destination's currency.

    **May be zero or negative** when the fees exceed the amount, and is reported that way.
    Predecessor defect B13 was exactly a ``max(gross - fee, 0)`` that made money vanish
    with no diagnostic.
    """

    components: Mapping[CostComponent, Money]
    """The charge, split by term, in :attr:`sent`'s currency. Every member present, zero
    where it does not apply -- so a reader can see that a component is zero rather than
    absent, and so the sum is over a known set (FR-003, FR-009)."""

    fraction: float
    """Cost as a fraction of :attr:`sent`.

    **May exceed 1.0** on a small amount with a fixed fee, and is reported that way rather
    than capped: a cap here is B13's silent clamp in a new hat. **May be negative** where a
    channel trades below its reference.
    """

    channels_applied: tuple[str, ...]
    """Which channel each ``fx`` leg used, in leg order. Present because the choice changes
    the number (FR-011), and empty for a route that converts nothing."""

    provenance: Provenance
    """The union of every declared value behind this figure -- every fee schedule, every
    premium, every reference rate. ``provenance.is_unverified`` is ``True`` while any of them
    lacks a verification date, which for every route number in this feature is the expected
    first-run state (FR-022)."""

    staleness: StalenessVerdict
    """Which of those observations have aged past their kind's threshold, and by how many
    days, at the run's as-of date (FR-025)."""


@dataclass(frozen=True, slots=True)
class RoundTripCost:
    """What it costs to get money in **and back out again**, through a declared exit route.

    Computed from the route's declared ``partner_route`` and never by reversing the inbound
    chain (FR-027): the way out has its own legs, its own side of every spread and its own
    limits, and reversing the way in would be wrong wherever the two differ -- which they do.

    This is the figure that belongs in a comparison (FR-002). Unrelated to
    :class:`OneWayCost`, so it cannot be filled with one.
    """

    sent: Money
    """What departed on the way in. The denominator of :attr:`fraction`, so the round-trip
    percentage is measured against the same amount as the one-way percentage."""

    arrived: Money
    """What came back at the end of the exit route -- what is actually spendable again."""

    components: Mapping[CostComponent, Money]
    """The whole round trip's charge, split by term, in :attr:`sent`'s currency: the inbound
    legs' and the exit legs' terms summed into the same three buckets."""

    fraction: float
    """Round-trip cost as a fraction of :attr:`sent`. The number §4.3.1's *9-19% round trip*
    refers to."""

    channels_applied: tuple[str, ...]
    """Every channel used, inbound legs first and then exit legs. A round trip crossing the
    same channel twice lists it twice, because it was paid for twice."""

    provenance: Provenance
    """The union over both routes."""

    staleness: StalenessVerdict
    """The merged verdict over both routes' observations."""


@dataclass(frozen=True, slots=True)
class ExitCostUnknown:
    """The round-trip slot, present and explicitly empty, naming what is missing.

    Not an error and not a failure -- a valid, honest occupant of a slot whose value is
    genuinely unknown, exactly as ``RealTermsUnavailable`` occupies the real-terms slot. The
    route is perfectly costable one way; what is missing is a declaration of the way out.

    A destination in this state is **not comparison-ready** (FR-030) and is kept out of any
    round-trip ranking, reported separately. That is the decision working rather than a gap
    in it: "nobody has costed the exit" is a fact about the asset, and Principle VI says an
    asset that cannot be liquidated at a reasonable cost is not worth its stated value.
    """

    reason: str
    """Why there is no round-trip figure, in the output's own words (FR-017)."""

    missing_partner_for: str
    """The route whose ``partner_route`` could not produce an exit cost. Named so the
    remedy -- declare the exit route -- is obvious from the output alone."""


@dataclass(frozen=True, slots=True)
class RampCost:
    """One costed way of getting money to one place: the feature's central result.

    Keyed by the whole triple, never by a destination alone (FR-008).
    """

    path: FundingPath
    """Which destination, from which stream, by which route. Never a bare destination."""

    one_way: OneWayCost
    """The cost in. Always computable, since the inbound route is the one that was declared."""

    round_trip: RoundTripCost | ExitCostUnknown
    """The cost in and back out, or a typed statement of why there is none.

    Present and typed either way; never absent, and never a promoted one-way figure
    (FR-030).
    """

    latency_days: int
    """Summed over the inbound route's legs. Reported beside the cost, never inside it: a
    slow route is not an expensive one, and adding a day to a percentage is not a number."""

    ceiling: Money | None
    """The tightest declared monthly cap on any leg of the inbound route, in the sending
    currency, or ``None`` when no leg declares one.

    It is the cap on what passes the leg that binds -- **not** the largest amount that may be
    sent, which additionally depends on the fees upstream of that leg and on how much of the
    month's capacity is already consumed. That second figure is the capacity accumulator's
    (FR-012, FR-015), and conflating the two here would overstate what a route will carry.
    """

    status: RouteStatus
    """The route's declared status. A ``constrained`` route is costed and reported as
    constrained; a ``closed`` one never reaches this record at all -- it is excluded with its
    status recorded (FR-014)."""

    disruption_probability: float
    """The largest single-leg probability that this route stops working, in ``[0, 1]``.

    Reported **beside** the cost and never folded into it (FR-026): the chance a route stops
    working is a different claim from what it charges, and a single number blending the two
    answers neither question.

    The *largest leg's* figure rather than a compound one, deliberately. Compounding
    (``1 - prod(1 - p)``) would require assuming the legs fail independently, and nobody has
    stated that -- an assumption smuggled into an arithmetic step is the thing Principle I
    forbids. So this is a **lower bound** on the route's disruption probability: at least this
    likely, and no more likely than the sum of the legs'. A route with one 5% leg and one 3%
    leg reports 5%, and the honest reading is "at least 5%".
    """


@dataclass(frozen=True, slots=True)
class RouteUnusable:
    """A route that cannot carry this amount on this date, and what bound it.

    Returned *instead of* a :class:`RampCost` -- a tagged-union member, not an exception and
    not a zero cost. FR-014: reported with the binding constraint named, and never silently
    adjusted, rounded, or dropped from a comparison. Rounding a transfer up to a minimum
    would move money the owner did not agree to move; rounding it down would report a cost
    for a movement that never happened.

    Unrelated to :class:`RampCost`, so the two cannot stand in for one another. An unusable
    route is not a cost of zero, and zero is the answer a reader would least question.
    """

    path: FundingPath
    """Which way was tried. The same key a successful cost carries, so an exclusion can be
    reported beside the alternatives it was excluded from."""

    binding_constraint: str
    """What bound, named as the declared field that bound it -- ``leg.minimum``,
    ``leg.maximum``, ``leg.available_from``, ``route.status``. The field name rather than
    prose so a caller can group and count without parsing sentences."""

    required: Money | None
    """What the constraint demands, or ``None`` when the constraint is not an amount.

    A closed route and an availability window bind without any amount being involved, and
    inventing a zero for those cases would put a number where there is none. The
    :attr:`reason` states it in words either way.
    """

    actual: Money | None
    """What was offered, or ``None`` for a non-amount constraint."""

    shortfall: Money | None
    """``required - actual``, or ``None``. Carried rather than left to the caller to
    subtract, so the figure the owner is shown comes from the same arithmetic every time."""

    reason: str
    """Plain-language statement of what bound and by how much, for the output (FR-017)."""
