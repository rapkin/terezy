"""The declared price series, the coverage check, and the chain that turns it into a rate.

Three things live here, in the order a deflation uses them: what a series *is*, whether it
covers the window being asked about, and -- only if it does -- what the months multiply to.

## The series is month-on-month, so a window is a product

``data/cpi/ua.toml`` holds the published index of each month **against the previous month**:
``100.9`` means prices rose 0.9% that month. Cumulative inflation over a window is the
product of every month's ``value / 100``, minus one. There is no level index and none is
synthesised (research.md D1): inventing a base-100 series would mean choosing a base period
nobody published and carrying its rounding through every month since 1991, and the product is
exact over whatever window the observations cover without needing a base at all.

**A month-on-month series invites being summed, and at Ukrainian magnitudes the sum is
visibly wrong.** Twelve months at five percent sum to 60% and multiply to 79.6%. The worked
example uses exactly that window so a summing implementation cannot pass it.

## Coverage is a tagged union, returned before any arithmetic runs

:func:`coverage` answers *"is every month of this window declared?"* and returns
:class:`Covered` or :class:`NotCovered` -- never a partial answer, and never a shortened
window. That ordering is the design rather than a convention: a check *inside* the
computation is a check someone later moves, reorders or short-circuits, whereas a union
returned first makes the uncovered case unrepresentable downstream. :class:`NotCovered`
carries the missing months and nothing else, so there is no field a partial product could
come out of.

## A rate per annum is deflated by inflation per annum

``nominal_ytm`` is annualised, so the inflation it is deflated by must be too. A cumulative
figure over six months set against an annual yield would understate inflation by roughly half
-- a modelling error wearing a units error's clothes. :func:`annualised` is the change of
units, and :func:`periods_per_year` reads the divisor off the series' **declared**
periodicity rather than assuming twelve (FR-002: periodicity is declared per series, never
fixed in the engine).

## Nothing here treats "the CPI" as a singleton

A :class:`CpiSeries` declares what it measures -- the economy, the index, the periodicity,
the base -- so a second series for a second country is a data-only addition that loads and is
addressable (FR-002, G13). Nothing in this module or above it holds "the" series.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal, assert_never

from terezy.core.primitives import provenance as prov
from terezy.core.primitives import staleness
from terezy.core.primitives.periods import Window, months_in
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.staleness import ObservationKind, StalenessVerdict

type Periodicity = Literal["monthly"]
"""How often a series is published.

A closed set with one member today, and widening it is a deliberate code change with a
divisor to add in :func:`periods_per_year` -- which is the point. FR-002 requires the
periodicity to be **declared per series** rather than assumed by the engine, and this type is
how the declaration reaches the arithmetic: a quarterly series would annualise by four, and
an engine that assumed twelve would be wrong by a factor of three with no error anywhere.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class CpiObservation:
    """One period's published price-index value: the atom of realized inflation."""

    period: str
    """The month covered, as ``YYYY-MM``, conforming to the series' declared periodicity."""

    value: float
    """The published index **against the previous month**: ``100.9`` is +0.9%.

    Strictly positive, checked at the data boundary. That is not a formality: a factor of
    zero or below would make the chained product zero or negative and put the Fisher
    relation's denominator on or past zero, so the constraint on the declaration is what
    keeps the arithmetic total.
    """

    kind: str
    """The :class:`~terezy.core.primitives.staleness.ObservationKind` id this value ages under.

    Carried on the observation, on ``Leg.kind_of_observation``'s precedent, because the
    threshold belongs to the declaring table and every ``[[observation]]`` in the file is one.
    ``cpi_index`` for everything shipped today.
    """

    provenance: Provenance
    """Where this month's figure came from: source, retrieval date, verification date.

    One ``SourceRef`` per observation, so a real figure over a long window carries hundreds
    of them. That is the honest answer rather than an inconvenience (research.md D6): the
    figure really does rest on every month it chained.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class CpiSeries:
    """A declared, identified sequence of price-index observations for one economy."""

    id: str
    """``ua_cpi_monthly``. Unique across the declared series; a collision is a load failure."""

    country: str
    """What economy this measures. Half of the identity FR-002 requires a series to declare,
    and the reason a second country's index is a data-only addition rather than a rewrite."""

    index: str
    """Which price index this is, in words -- *"consumer price index, all goods and services"*.
    The other half of the identity: two indices for one country are two series."""

    periodicity: Periodicity
    """How often the publisher publishes. Declared, never assumed. See :data:`Periodicity`."""

    base: str
    """The form the values are in, stated: ``"previous month = 100"``.

    Carried as text rather than inferred, because reading a month-on-month series as a level
    index gives a wrong answer that looks entirely plausible, and the file is the only place
    that knows which it is.
    """

    observations: tuple[CpiObservation, ...]
    """The declared months. Sorted, gapless within a run of declared months, and free of
    duplicates -- all three checked at the data boundary, which can name the file."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Covered:
    """Every month of the window has exactly one declared observation."""

    observations: tuple[CpiObservation, ...]
    """The window's months, in calendar order.

    In calendar order rather than file order because this tuple is also what enumerates the
    sources behind the figure, and an out-of-order trail is one nobody can follow. The product
    itself is commutative and does not care.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class NotCovered:
    """At least one month of the window has no declared observation.

    **Carries the missing months and nothing else.** There is deliberately no field holding
    the observations that *were* found: partial coverage is not coverage, and a partial answer
    that existed on this record is a partial answer somebody would eventually return.
    """

    missing: tuple[str, ...]
    """The periods with no declared observation, in calendar order. Named, so the refusal is
    an instruction rather than a shrug.

    Empty when the window itself spans no month -- a window whose first month is after its
    last. That is still not coverage, and the caller reports the emptiness by name.
    """


type Coverage = Covered | NotCovered
"""What :func:`coverage` answers with. Matched with ``match``, never with a boolean flag."""


@dataclass(frozen=True, slots=True, kw_only=True)
class InflationAssumption:
    """A declared, dated belief about future inflation. Never an observation.

    On :class:`~terezy.core.scenarios.regimes.RegimeTransition`'s precedent exactly: a
    statement about the future, carrying ``is_assumption`` where an observation carries a
    source, and a rationale in the owner's own words.

    **A cited forecast is still an assumption** (FR-010, research.md D5). An external
    published forecast -- the National Bank's, say -- has a citation, a retrieval date and a
    staleness kind, and it is still a statement about a year that has not happened. Cited does
    not make it observed, and no verification against a primary source can, because there is
    no primary source for next year's prices. So :attr:`provenance` may be present *and* the
    record is still labelled an assumption everywhere it appears.
    """

    id: str
    """The declared id, recorded in the run manifest so a result can say which belief produced
    it (FR-015). Two runs with two different assumptions are two results, not one."""

    annual_rate: float
    """The assumed rate of inflation per annum, as a fraction: ``0.10``, never ``10``.

    Strictly above ``-1`` -- prices cannot fall to nothing -- checked at the data boundary,
    which keeps the Fisher relation's denominator away from zero.
    """

    is_assumption: Literal[True]
    """**Structurally always true**, and required rather than defaulted.

    A ``bool`` could be set ``False``; the type admits one value, so the claim cannot be
    turned off, and having no default means it cannot be omitted either. Not for branching on:
    there is no other case, so ``if assumption.is_assumption`` would be dead code implying one.
    """

    rationale: str
    """The owner's stated belief, in words. Required.

    A rate with no reasoning behind it is indistinguishable from a typo, and a figure
    conditional on an unexplained guess cannot be argued with.
    """

    provenance: Provenance | None
    """An external forecast's citation, or ``None`` for the owner's own figure.

    ``None`` is a statement, not an omission: the owner's own belief has nothing to cite, and
    attaching a fabricated source to it would be the top-severity defect Principle I names.
    """

    kind: str | None
    """The staleness kind an external forecast ages under, or ``None`` alongside a bare belief.

    A belief does not go stale -- it is superseded when the owner changes his mind, which is a
    different event with no threshold. A *retrieved* forecast does, on exactly the reasoning
    ``cpi_index`` carries: the publisher issues a new one and the old one is out of date.
    """


def coverage(series: CpiSeries, window: Window) -> Coverage:
    """Whether ``series`` declares every month of ``window``, all-or-nothing.

    Returned **before** any arithmetic, so an uncovered window cannot reach the Fisher
    relation at all. Nothing is interpolated, nothing is carried forward, and the window is
    never shortened to the part that happens to be covered -- that last one is the tempting
    repair, because it produces a number, and the number is real for a window nobody asked
    about (research.md D4).

    Raises ``KeyError`` on a series declaring one period twice. That is a programmer error
    rather than a fact about the money: the loader refuses a duplicate period and can name the
    file and the entry, so one arriving here means that check was bypassed -- and silently
    keeping either copy would let a figure depend on which was read second.
    """
    by_period: dict[str, CpiObservation] = {}
    for observation in series.observations:
        if observation.period in by_period:
            raise KeyError(
                f"series {series.id!r} declares the period {observation.period!r} twice. "
                "Duplicates are refused at the data boundary, where the file and the entry can "
                "be named; reaching here with one means that check was bypassed. Keeping "
                "either copy would make the figure depend on read order."
            )
        by_period[observation.period] = observation

    months = months_in(window)
    missing = tuple(month for month in months if month not in by_period)
    if missing or not months:
        return NotCovered(missing=missing)
    return Covered(observations=tuple(by_period[month] for month in months))


def cumulative_inflation(observations: Sequence[CpiObservation]) -> float:
    """The price change over a run of month-on-month observations: the **product**, minus one.

    ``100.9`` and ``101.2`` chain to ``1.009 * 1.012 - 1``, not to ``0.009 + 0.012``. Over
    Ukrainian magnitudes the difference is material, which is the same reason FR-008 forbids
    the subtraction approximation one level up.

    The empty product is one, so an empty run is zero inflation. That is stated for
    completeness and is *not* how an uncovered window is answered: :func:`coverage` refuses
    that case first, precisely so a window nobody has data for cannot arrive here and come
    back as "prices did not move".
    """
    factor = 1.0
    for observation in observations:
        factor *= observation.value / 100.0
    return factor - 1.0


def periods_per_year(periodicity: Periodicity) -> int:
    """How many observations of this periodicity make a year.

    An exhaustive ``match`` rather than a mapping with a default, so adding a periodicity is a
    type error here instead of quietly annualising a quarterly series as if it were monthly --
    which would be wrong by a factor of three with nothing in the output to say so.
    """
    match periodicity:
        case "monthly":
            return 12
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(periodicity)


def annualised(cumulative: float, *, periods: int, per_year: int) -> float:
    """A cumulative price change over ``periods`` observations, as a rate per annum.

    ``(1 + cumulative) ** (per_year / periods) - 1``. A change of units and nothing else, so
    it round-trips: compounding the result back over the same span returns the figure it came
    from, which is what ``tests/invariants/test_deflation_invariants.py`` asserts.

    Required because ``nominal_ytm`` is a rate per annum. Deflating an annual yield by six
    months of inflation would flatter the real return by roughly half the inflation, and
    nothing in the output would say the two figures were measured over different spans.

    Raises ``ValueError`` on a non-positive count. A window with no elapsed period is refused
    by name before this is reached, so one arriving here is a bypass -- and there is no
    honest annualisation of a span of no time.
    """
    if periods <= 0:
        raise ValueError(
            f"cannot annualise over {periods} periods. A window with no elapsed period is "
            "reported by name before the arithmetic runs, so reaching here means that check "
            "was bypassed; there is no rate per annum for a span of no time."
        )
    annual: float = (1.0 + cumulative) ** (per_year / periods) - 1.0
    return annual


def provenance_of(observations: Iterable[CpiObservation]) -> Provenance:
    """The union of every source behind a run of observations.

    One call to the existing monoid rather than a second propagation path. A real figure over
    a long window therefore names every month it chained -- hundreds of sources -- and that is
    the honest answer rather than a summary to be trimmed (research.md D6).
    """
    return prov.merge_all(observation.provenance for observation in observations)


def staleness_of_observations(
    observations: Iterable[CpiObservation],
    kinds: Mapping[str, ObservationKind],
    *,
    as_of: date,
) -> StalenessVerdict:
    """Age every observation against the threshold **its own** declared kind names.

    Folded per observation rather than assessed in one call, because the kind belongs to the
    declaring table and a series is many tables. Merged with the existing verdict monoid, so
    the fold's order cannot change the answer and one stale month taints the figure.

    **This is a different question from coverage** (research.md D7), and the output must not
    merge them. *"Is this observation stale?"* is the threshold: the publisher adds a month
    roughly every month, so a series fetched long ago is a series missing its recent end, and
    forty-five days is the re-fetch prompt. *"Does the series reach the end of my window?"* is
    :func:`coverage`. Both can fire on one run, they mean different things, and reporting one
    as the other would make a re-fetch look like a data gap or the reverse.
    """
    return staleness.merge_all(
        staleness.staleness_of(observation.provenance, kinds, kind=observation.kind, as_of=as_of)
        for observation in observations
    )


def staleness_of_assumption(
    assumption: InflationAssumption,
    kinds: Mapping[str, ObservationKind],
    *,
    as_of: date,
) -> StalenessVerdict:
    """Age a declared assumption, if it is the kind of assumption that can age.

    An external forecast was *retrieved* on a date and is superseded by the publisher's next
    one, so it ages exactly as an observation does. The owner's own belief carries neither a
    citation nor a kind and returns :data:`~terezy.core.primitives.staleness.UNASSESSED`:
    nothing was aged, so nothing is claimed -- which is distinguishable from a clean bill of
    health, and has to be, because a belief with a green freshness tick would be claiming
    something nobody checked.
    """
    if assumption.provenance is None or assumption.kind is None:
        return staleness.UNASSESSED
    return staleness.staleness_of(assumption.provenance, kinds, kind=assumption.kind, as_of=as_of)
