"""How old an observation is allowed to be, per kind of observation, with no clock.

FR-025: *staleness MUST surface. A value whose verification or retrieval date has aged past
its threshold MUST be reported as stale on every figure derived from it. A silently stale
route cost invalidates every comparison built on it.* FR-028 adds the shape: the threshold
is **per kind of value**, declared with the kind, and a kind with no threshold **fails at
load** rather than defaulting to a permissive one.

**Why per kind and not one number for the project.** A peer-to-peer premium moves with
demand and can shift within a week. A bank's published tariff changes on the bank's own
schedule, rarely mid-year. A regulatory limit changes when the regulator says so. A single
threshold would either cry wolf on fee schedules or stay silent on premiums -- and a
staleness warning that is usually wrong is one that gets ignored, which is worse than
having none. Declaring the threshold once per *kind* rather than once per *value* is the
other half of that argument: repeating it per value would guarantee drift, and drift in a
staleness threshold is invisible.

**There is no clock here and there may never be one** (research.md D9). Staleness is
``as_of - retrieved_on > staleness_days``, where ``as_of`` is an input to the run and is
recorded in the manifest. The same inputs therefore produce the same verdicts forever, which
would be false if the day were read from the machine -- and C4 asserts bit-identical reruns.
There is a second reason, and it is the one that decides the argument rather than merely
supporting it: ``as_of`` and ``on_date`` mean different things. ``on_date`` is when money
moves; ``as_of`` is when the question is asked. A projection into the future asked today has
``on_date`` in 2030 and ``as_of`` today, and a clock-driven implementation would report every
one of its inputs as stale by years.

**The verdict is a value that merges**, on the same monoid shape as
``provenance.merge`` and for the same reason: a ``RampCost`` rests on several legs and
several channels, each with its own kind and retrieval date, and no call site should have to
remember to combine them. :func:`merge` is a union that keeps one entry per source at its
*strictest* reading, so a lenient second look at a source cannot dilute a stale first one.

**Why the verdict says what it assessed.** An empty verdict is ambiguous in the one
direction that matters: "everything was checked and nothing is stale" and "nobody checked"
would otherwise be the same value, and the second one wearing the first one's green tick is
exactly the silent permissive default FR-028 forbids. :attr:`StalenessVerdict.assessed`
names the sources that were aged, so :data:`UNASSESSED` is distinguishable from a clean
bill of health.

**Staleness is not verification, and neither implies the other.** ``provenance`` answers
"has anyone checked this against a primary source"; this module answers "was it read from
the source too long ago to trust". A value can be verified and stale (a tariff verified two
years ago), or unverified and fresh (this morning's P2P premium, from a screenshot). Both
marks propagate, separately, because they are different claims.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final

from terezy.core.primitives.provenance import Provenance, SourceRef


@dataclass(frozen=True, slots=True)
class ObservationKind:
    """One sort of thing the owner observes, and how fast it goes out of date.

    Declared in ``data/observation_kinds.toml``; every sourced table in the project names
    one. A record carrying only data, per owner decision D-E.
    """

    id: str
    """The name a declaration uses -- ``p2p_premium``, ``bank_fee_schedule``,
    ``regulatory_limit``, ``bond_terms``, ``tax_rule``."""

    staleness_days: int
    """How many days after retrieval a value of this kind is still current.

    **No default, and none may be added.** A kind declared without one fails at load
    (FR-028); the omission cannot be papered over here, because the record has no
    default to fall back to and this module has no opinion about what a reasonable
    threshold would be. Guessing one would be exactly the invented domain value
    Principle I forbids.
    """

    note: str
    """Why this kind ages at this rate, in words.

    Required, because a threshold nobody explained is a number nobody can argue with --
    and a threshold nobody can argue with is one that never gets corrected.
    """


@dataclass(frozen=True, slots=True)
class StaleSource:
    """One observation that has aged past its kind's threshold, with the arithmetic shown.

    Every field is stated rather than left for a reader to derive, so the figure the owner
    is shown comes from the same subtraction every time.
    """

    source_id: str
    """The ``SourceRef`` id, so the mark can name *which* input is stale."""

    kind_id: str
    """The kind whose threshold was applied. Two kinds disagree about the same date, and
    the output has to be able to say which rule it used."""

    retrieved_on: date
    """When the value was read from its source."""

    age_days: int
    """``as_of - retrieved_on`` in days."""

    threshold_days: int
    """The kind's declared ``staleness_days``."""

    overdue_days: int
    """``age_days - threshold_days``: how far past its threshold this value is."""


@dataclass(frozen=True, slots=True)
class StalenessVerdict:
    """What was aged, and what came back stale. Merges like provenance does."""

    assessed: tuple[str, ...]
    """Source ids that were aged, sorted. Present so that :data:`UNASSESSED` -- nothing
    checked -- is distinguishable from a verdict that checked and found nothing stale."""

    stale: tuple[StaleSource, ...]
    """The sources past their threshold, sorted by id. Empty means nothing among
    :attr:`assessed` was stale, which is a claim only as strong as that list."""


UNASSESSED: Final[StalenessVerdict] = StalenessVerdict((), ())
"""The identity of :func:`merge`: nothing was aged, so nothing is claimed.

Distinct from a verdict that assessed sources and found none stale. A figure carrying this
has had no observation aged against any threshold -- which is the correct verdict for a
figure resting on ``provenance.EMPTY``, and a red flag anywhere else.
"""


def kind_for(kinds: Mapping[str, ObservationKind], name: str) -> ObservationKind:
    """The declared kind a name selects, or a raise naming it and what is known.

    An explicit membership test rather than ``kinds.get(name, default)``, so that no
    reading of this code suggests a default exists -- the same discipline as
    ``conventions._resolve``, and for a sharper reason: the comfortable default for a
    staleness threshold is a generous one, and a generous default would silently bless
    every value whose kind was misspelt.

    The data layer validates kind names when it loads a declaration and reports file and
    field (FR-028). A name reaching here unrecognised means that validation was bypassed,
    which is a programmer error rather than a fact about the money -- hence a raise.
    """
    if name not in kinds:
        raise KeyError(
            f"unknown observation kind {name!r}. There is no default threshold: a value "
            f"kind must declare its own staleness_days in data/observation_kinds.toml "
            f"(FR-028). Known kinds: {sorted(kinds)}"
        )
    return kinds[name]


def age_in_days(retrieved_on: date, *, as_of: date) -> int:
    """How many days old an observation is at the as-of date.

    **May be negative**, and is reported that way rather than clamped: a backdated
    question asked against a later retrieval date genuinely has a negative age, and the
    honest answer is the number, not zero (Principle IV, "no silent clamping"). Such a
    value is not stale -- an observation cannot have aged past a threshold before it
    existed -- and :func:`is_stale` says so without inventing a verdict for it.
    """
    return (as_of - retrieved_on).days


def freshest_date(source: SourceRef) -> date:
    """The date a value's age is measured from: the **later** of the two dates on the source.

    FR-025 says "verification **or** retrieval date has aged" and left which one open. It is
    the later of the two, taken literally: a verification after retrieval refreshes the age,
    and a re-retrieval after an old verification refreshes it just the same. A value verified
    in 2024 and re-fetched last month is weeks old, not years -- both dates are looks at the
    source, and the age runs from the most recent look.

    Verifying a value against a primary source is the strongest possible refresh of
    confidence in it. A value retrieved two years ago and verified last week is not stale,
    and reporting it as stale would tell the owner to re-check the one thing he has actually
    checked -- a warning that fires on refreshed values is one that gets ignored, which is
    worse than none.

    The asymmetry is deliberate: an **unverified** value ages from retrieval, which is every
    value in this project today and the stricter of the two readings.
    """
    if source.verified_on is None:
        return source.retrieved_on
    return max(source.verified_on, source.retrieved_on)


def is_stale(source: SourceRef, kind: ObservationKind, *, as_of: date) -> bool:
    """Whether a value of this kind is stale at the as-of date.

    Ages from :func:`freshest_date`, so a verified value ages from its verification.

    ``as_of - freshest > staleness_days``: strictly past the threshold, so a value on
    the boundary is still current. ``as_of`` is keyword-only, because it is the argument a
    caller is most likely to confuse with ``on_date`` -- the date money moves -- and the
    two are never interchangeable.
    """
    return age_in_days(freshest_date(source), as_of=as_of) > kind.staleness_days


def _verdict_for(source: SourceRef, kind: ObservationKind, *, as_of: date) -> StaleSource | None:
    """One source aged against one kind, or ``None`` when it is still current.

    Ages from :func:`freshest_date`, the same date :func:`is_stale` uses -- if the two aged
    from different dates, a value could be stale by one and current by the other.
    """
    age = age_in_days(freshest_date(source), as_of=as_of)
    if age <= kind.staleness_days:
        return None
    return StaleSource(
        source_id=source.id,
        kind_id=kind.id,
        retrieved_on=freshest_date(source),
        age_days=age,
        threshold_days=kind.staleness_days,
        overdue_days=age - kind.staleness_days,
    )


def staleness_of(
    provenance: Provenance,
    kinds: Mapping[str, ObservationKind],
    *,
    kind: str,
    as_of: date,
) -> StalenessVerdict:
    """Age every source behind one declared record against that record's kind.

    ``kind`` is the id the *record* declared -- a leg's ``kind_of_observation``, a
    channel's ``kind`` -- and ``kinds`` is the declared registry it resolves against. The
    kind belongs to the declaring table rather than to the individual ``SourceRef``,
    because that is where it is declared: one table, one kind, however many sources it
    cites. Combining several records' verdicts is :func:`merge`'s job, not this
    function's.

    A provenance resting on no source returns :data:`UNASSESSED`: there is nothing to age,
    and claiming freshness for a figure that rests on nothing would make the mark
    meaningless by making it universal.
    """
    resolved = kind_for(kinds, kind)
    stale = [_verdict_for(source, resolved, as_of=as_of) for source in provenance.sources]
    return StalenessVerdict(
        assessed=tuple(sorted(source.id for source in provenance.sources)),
        stale=tuple(sorted((s for s in stale if s is not None), key=lambda s: s.source_id)),
    )


def staleness_of_sources(
    provenance: Provenance,
    kinds: Mapping[str, ObservationKind],
    *,
    as_of: date,
) -> StalenessVerdict:
    """Age every source in a merged provenance under **its own** declared kind.

    :func:`staleness_of`'s sibling, and the distinction is which of the two knows the kind.
    ``staleness_of`` is for a caller holding **one declaring record** whose own field names the
    threshold for the whole table -- a leg, a channel, a venue quote -- and it is the right
    call there because a table may cite several sources under one kind.

    This one is for a **derived figure** whose provenance has already been merged across
    several tables. By then no record is in hand: a tuple's outcome rests on the bond's terms,
    its constraints, the tax pack's rates and every table of a fund's declaration, and none of
    those core records carries a kind. The kind rides on the citation instead
    (:attr:`~terezy.core.primitives.provenance.SourceRef.kind`), which is the only thing that
    survives the merge -- and without it FR-019's staleness half was unreachable for two of a
    tuple's four parts while its provenance half worked perfectly.

    A source whose kind is empty is **not aged and not listed in** :attr:`assessed`. That is
    the strict reading: it says nobody could check this rather than claiming it is current,
    which is the same distinction :data:`UNASSESSED` exists to preserve. Every citation the
    loader reads is stamped, so an empty kind means a source built in code.
    """
    aged = [
        (source, _verdict_for(source, kind_for(kinds, source.kind), as_of=as_of))
        for source in provenance.sources
        if source.kind
    ]
    return StalenessVerdict(
        assessed=tuple(sorted(source.id for source, _ in aged)),
        stale=tuple(sorted((v for _, v in aged if v is not None), key=lambda s: s.source_id)),
    )


def merge(left: StalenessVerdict, right: StalenessVerdict) -> StalenessVerdict:
    """Union two verdicts. Associative, commutative, with :data:`UNASSESSED` as identity.

    Called once per leg and once per channel as a route is costed, so a ``RampCost``
    carries one verdict covering every observation it rests on. The monoid properties are
    what make that safe: evaluation order can never change a verdict, so the mark is a
    fact about the data rather than about the fold that produced it.

    **One entry per source, at its strictest reading.** Provenance is a set, so the same
    source can reach a figure by two paths and be aged under two kinds. Keeping the larger
    ``overdue_days`` means a lenient second look cannot dilute a stale first one -- the
    same asymmetry as ``provenance.is_unverified``, where one unverified input taints the
    result.
    """
    worst: dict[str, StaleSource] = {}
    for source in (*left.stale, *right.stale):
        seen = worst.get(source.source_id)
        if seen is None or source.overdue_days > seen.overdue_days:
            worst[source.source_id] = source
    return StalenessVerdict(
        assessed=tuple(sorted(set(left.assessed) | set(right.assessed))),
        stale=tuple(worst[key] for key in sorted(worst)),
    )


def merge_all(items: Iterable[StalenessVerdict]) -> StalenessVerdict:
    """Fold :func:`merge` over many verdicts, starting from :data:`UNASSESSED`."""
    merged = UNASSESSED
    for item in items:
        merged = merge(merged, item)
    return merged


def any_stale(verdict: StalenessVerdict) -> bool:
    """Whether **any** source behind this figure has aged past its threshold.

    One stale input makes the figure stale. A figure is only as current as its least
    current input, and marking only when *every* input is stale would let one stale
    premium hide behind a crowd of fresh fee schedules -- which is the P2P premium's
    situation exactly, since it is the fastest-ageing number in the system.
    """
    return bool(verdict.stale)


@dataclass(frozen=True, slots=True, kw_only=True)
class Ageing:
    """The two things ageing an observation needs, kept together so neither can go missing.

    ⚙ **Added by feature 007**, and a record rather than two parameters for one reason:
    where ageing is *optional*, two separate optional parameters can be half-supplied.
    Passing ``kinds`` and forgetting ``as_of`` would age nothing and say nothing about not
    having done so -- a silent :data:`UNASSESSED` wearing a caller's intention to check. One
    optional record cannot be half-passed.

    Functions where ageing is *required* -- ``routes.cost.cost_one`` and everything under it
    -- keep taking the two separately, because there the type checker already forbids omitting
    either and a wrapper would be ceremony.

    ``as_of`` is an input to the run and is recorded in the manifest. There is no clock here
    and there may never be one: the same inputs must give the same verdict for ever.
    """

    kinds: Mapping[str, ObservationKind]
    """The declared registry from ``data/observation_kinds.toml``, keyed by kind id."""

    as_of: date
    """The date the question is asked -- never ``on_date``, which is when money moves."""
