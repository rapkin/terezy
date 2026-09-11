"""What a dominance pass produces: three populations, the verdicts between them, and its refusals.

019. **The answer stops having a head.** A ranked list's top row reads as a recommendation
whatever is printed beside it, and the constitution's first principle puts dominance ahead of
every other form of answer: the honest output is the set no candidate dominates, with the stated
assumptions its members do not share named beside it.

**Nothing here holds a string this feature composed** (FR-028). Every string is an id, a
criterion name, the name of a record field that carried no figure, or a reason another core
record already wrote, carried verbatim.

**Nothing is pruned** (FR-009). Dominance is a reported relation over the evaluated population,
never a filter applied to it: a dominated candidate is one the owner may still take, for a
reason no declared objective carries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.staleness import StalenessVerdict
from terezy.core.results.candidates import SurveyRefused
from terezy.core.results.objectives import Band, Criterion, ObjectiveSet
from terezy.core.results.tuple import Tuple

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from terezy.core.results.answer import BenchmarkYieldsNoCandidate, StatedExclusion

# ---------------------------------------------------------------------------
# What the relation compares: a figure that carries its own kind, and a width
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class MoneyFigure:
    """An amount, in the currency the spendable endpoint delivered it in."""

    amount: Money


@dataclass(frozen=True, slots=True, kw_only=True)
class DateFigure:
    """A date, compared exactly: FR-011d fixes a date's slack at zero."""

    on: date


@dataclass(frozen=True, slots=True, kw_only=True)
class FigureUnavailable:
    """The criterion could read no figure off this candidate, naming what was not there."""

    what: str
    """The record field that carried nothing."""


Figure = MoneyFigure | DateFigure | FigureUnavailable
"""One candidate's reading on one objective.

**The figure carries its own kind** so the closeness rule can follow it rather than a parallel
*is this one a date* flag, which would be the same fact in two places (research D7a).
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class MoneyWidth:
    """An indifference band made comparable to a money figure, in one currency."""

    amount: Money


@dataclass(frozen=True, slots=True, kw_only=True)
class DayWidth:
    """An indifference band on a date, in whole days."""

    days: int


Width = MoneyWidth | DayWidth
"""A declared band resolved against the figures it will be compared with: a fraction met by the
question's stated amount, or an already-absolute band unchanged."""


# ---------------------------------------------------------------------------
# Why a pair could not be decided
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class FigureMissing:
    """One of the two candidates carries no figure on this objective."""

    what: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliveredInTwoCurrencies:
    """The two amounts are in different currencies, and **no exchange rate is consulted**.

    Principle VI: values in different currencies are never silently combined, and *more money*
    is not a question across a rate nobody declared.
    """

    left_currency: Currency
    right_currency: Currency


IncomparableReason = FigureMissing | DeliveredInTwoCurrencies
"""Why one objective could decide nothing between two candidates. Neither member carries a
criterion: ``relates`` is addressed by position and has none to give, and the pair carries it."""


# ---------------------------------------------------------------------------
# One pair's verdict
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class LeftDominates:
    """The left candidate dominates the right, by the positions that decided it."""

    at_least_as_good_at: tuple[int, ...]
    strictly_better_at: tuple[int, ...]
    """Non-empty: dominance requires better on at least one by more than that objective's band."""


@dataclass(frozen=True, slots=True, kw_only=True)
class RightDominates:
    """The right candidate dominates the left. Positions read the same way round."""

    at_least_as_good_at: tuple[int, ...]
    strictly_better_at: tuple[int, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class TooCloseToCall:
    """Within the declared band on **every** objective: neither is reported ahead of the other.

    Named for User Story 2's own words rather than ``Indistinguishable``, which names the
    per-candidate record :class:`Indistinguishable` below. An import binding one of the two
    silently is worse than a collision that fails.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class Neither:
    """Each is better on something. The ordinary state of a partial order, and not a failure."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Incomparable:
    """One objective could read no verdict between the two, at a named position."""

    position: int
    why: IncomparableReason


PairVerdict = LeftDominates | RightDominates | TooCloseToCall | Neither | Incomparable
"""What one pair yielded. Named ``PairVerdict`` rather than ``Verdict`` because
``core.tax.scheme`` declares a ``Verdict`` that ``data.declarations.resolver`` imports
unqualified, which is the same collision one module further out."""


# ---------------------------------------------------------------------------
# What the pass reports
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class DominanceVerdict:
    """One ordered pair: which candidate dominates which, on what, and how marked (FR-022).

    The provenance and staleness are the **merged** marks of both candidates, so a verdict never
    looks cleaner than the figures behind it: *A dominates B* computed from two unverified
    figures is an unverified claim.
    """

    dominates: Tuple
    over: Tuple
    at_least_as_good_on: tuple[Criterion, ...]
    """Every declared criterion, by FR-007's definition: dominance requires the weak half to
    hold on all of them. Carried so one verdict is readable without the rule in hand."""

    strictly_better_on: tuple[Criterion, ...]
    provenance: Provenance
    staleness: StalenessVerdict


@dataclass(frozen=True, slots=True, kw_only=True)
class Dominated:
    """One dominated candidate, and at least one candidate that dominates it.

    Several, where several do. The relation is not a ranking, so *dominated by exactly one* and
    *dominated by nine* are different facts and both are on the record.
    """

    key: Tuple
    dominated_by: tuple[DominanceVerdict, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class IncomparablePair:
    """Two candidates one objective could not decide between (FR-008a).

    A property of the **pair**. It refuses no section and removes neither candidate from any
    other pair's verdict.
    """

    left: Tuple
    right: Tuple
    criterion: Criterion
    why: IncomparableReason


@dataclass(frozen=True, slots=True, kw_only=True)
class NotPlaced:
    """An evaluated candidate with at least one pair, every one of which is incomparable.

    **The *at least one* is load-bearing.** *Every pair is incomparable* is vacuously true of a
    section's only evaluated candidate, which would leave the non-dominated set empty over a
    population of one -- and a lone evaluated candidate is non-dominated.
    """

    key: Tuple
    every_pair: tuple[IncomparablePair, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Indistinguishable:
    """One candidate and the candidates it cannot be told apart from (FR-011).

    A **symmetric relation over pairs**, reported per candidate and never as a partition:
    closeness within a band is not transitive, so no partition exists, and any procedure
    producing one depends on an anchor the objectives do not fix (FR-011a).
    """

    key: Tuple
    neighbours: tuple[Tuple, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class NothingDominatesTheHurdle:
    """No member of the population dominates the benchmark (FR-017).

    Worded as *nothing dominates the hurdle* and never as *the hurdle is best*: other members
    may sit beside it in the set, better on one objective and worse on another, and a hurdle
    that dominates everything is a different and stronger fact.
    """

    key: Tuple


@dataclass(frozen=True, slots=True, kw_only=True)
class HurdleIsDominated:
    """The benchmark is dominated, by the members named."""

    key: Tuple
    by: tuple[DominanceVerdict, ...]


BenchmarkStanding = NothingDominatesTheHurdle | HurdleIsDominated
"""Where the hurdle sits in the partial order. Distinct from 010's ``beats_benchmark``, which is
strict, one-dimensional, on the **rate**, at the **project tolerance** -- the two are separate
fields and neither is derived from the other (FR-013)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class MemberRestsOn:
    """One member of the set, and the stated assumptions at least one other member does not carry.

    Verbatim: the words come from ``TupleOutcome.rests_on`` and from the **section's** own
    exclusion records, and nothing here composes a sentence of its own (FR-019).
    """

    key: Tuple
    rests_on: tuple[str, ...]
    excludes: tuple[StatedExclusion, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class SeparatingAssumptions:
    """What the set's members do not share, per member (FR-019).

    **Not a claim about which one decides** (FR-021). Naming the deciding assumption requires
    re-evaluating the set under a changed assumption, which is required test I5's feature.
    """

    per_member: tuple[MemberRestsOn, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class NoStatedAssumptionSeparatesThem:
    """The members rest on exactly the same stated assumptions (FR-020).

    A typed statement rather than an empty list, which a reader takes as *nothing separates
    them* when the truth is *the same beliefs are behind all of them*.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedBand:
    """One fraction band, met by the question's own stated amount in one currency (FR-023).

    Carried once per ``(criterion, currency)`` actually compared in, rather than on each verdict:
    the same fact repeated once per pair would be 276 copies per section on the owner's registry.
    An absolute band and a day band resolve to themselves and are reported in their declared
    form, so they appear here not at all.
    """

    criterion: Criterion
    currency: Currency
    from_amount: Money
    width: Money


@dataclass(frozen=True, slots=True, kw_only=True)
class DominanceResult:
    """One section's whole dominance reading, beside the survey and replacing nothing in it."""

    objectives: ObjectiveSet
    """The whole declared set, every band in the form it was declared (FR-023). A dominance
    count read without the objectives that produced it is meaningless."""

    resolved_bands: tuple[ResolvedBand, ...]

    evaluated_count: int
    """How many candidates the pass read. The three populations below partition exactly these, so
    a reader is told *N of M* without summing three served counts -- and without reading the
    section's `ranked`, which is this plus whatever FR-030 withheld."""

    non_dominated: tuple[Tuple, ...]
    dominated: tuple[Dominated, ...]
    not_placed: tuple[NotPlaced, ...]
    incomparable: tuple[IncomparablePair, ...]
    indistinguishable: tuple[Indistinguishable, ...]
    benchmark_standing: BenchmarkStanding
    separating: SeparatingAssumptions | NoStatedAssumptionSeparatesThem


# ---------------------------------------------------------------------------
# Why the set has one member (FR-014) -- derived, never stored
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class OnlyOneEvaluated:
    """The section evaluated one candidate. Not a finding about that candidate."""


@dataclass(frozen=True, slots=True, kw_only=True)
class EveryOtherIsDominated:
    """The only case that is a finding."""


@dataclass(frozen=True, slots=True, kw_only=True)
class EveryOtherIsNotPlaced:
    """Every other evaluated candidate could be read on no objective against anything."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Mixed:
    """Some of each, with the counts saying which."""

    dominated: int
    not_placed: int


@dataclass(frozen=True, slots=True, kw_only=True)
class TheSetDoesNotHaveOneMember:
    """The question does not arise, and the count says which way.

    **Zero is one of the ways**, and it is the one a reader most needs named: a section every
    pair of which is incomparable places nobody, so nothing is non-dominated and the set is
    empty honestly. A record naming this *several members* would be false there.
    """

    members: int


WhyOneMember = (
    OnlyOneEvaluated
    | EveryOtherIsDominated
    | EveryOtherIsNotPlaced
    | Mixed
    | TheSetDoesNotHaveOneMember
)
"""Why the reported set holds what it holds, against FR-008's populations rather than in prose.
*Dominates every other* is deliberately not among them: dominance is reported per pair, and a
member can be the only survivor without being the dominator named on every other record."""


# ---------------------------------------------------------------------------
# The refusals (FR-026)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class NoBenchmarkToStandAgainst:
    """The section has no hurdle (FR-018), carrying 010's own reason verbatim.

    Without the hurdle among them a set of survivors is a shortlist with nothing to measure it
    against, and its head reads as a winner -- which is the argument 010 FR-011 already made one
    layer down.
    """

    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkWasWithheld:
    """The hurdle's own money arrives after the window, so 015 FR-030 withheld it (FR-018a).

    The case a reader misses: the comparison is a ``Comparison``, every figure is there, and
    nothing else refuses. A **different reason** from :class:`NoBenchmarkToStandAgainst`,
    because the remedies differ.
    """

    key: Tuple
    arrives_on: date


@dataclass(frozen=True, slots=True, kw_only=True)
class BandBelowTheAcyclicityFloor:
    """A declared band does not clear the slack the figures compared actually allow (FR-011c).

    A refusal rather than a load failure because the slack depends on the magnitudes of those
    figures, which a declaration file does not carry. Below the floor a cycle is possible, and a
    cycle empties the set over a population every member of which is placed.
    """

    criterion: Criterion
    declared: Band
    resolved: Money
    """The width the band was actually measured at, which for an absolute band is its own
    amount. Not optional: the floor is reached only on a money objective, whose width is money
    either way, and a ``None`` here would be a state nothing can produce."""

    slack: float
    floor: float
    objective_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class NoQuestionAmountInTheCurrencyCompared:
    """A fraction band has nothing to be a fraction **of** (FR-011d, research D6).

    Recorded as a refusal rather than as an incomparable pair: both figures are present and in
    one currency, so reporting the population *not placed* would say the figures could not be
    read when what happened is that the question states no amount to size the band against.
    """

    criterion: Criterion
    currency: Currency


@dataclass(frozen=True, slots=True, kw_only=True)
class SeveralQuestionAmountsInTheCurrencyCompared:
    """Two stated amounts in one currency leave a fraction band with no single width.

    FR-011's relation has to be symmetric, so one currency admits one width and there is
    genuinely no way to pick between two amounts the owner stated. The streams are named because
    the remedy is a question edit and *which two* is the whole of what a reader needs -- or an
    absolute band, which FR-011d permits and which has no dependence on the amounts at all.
    """

    criterion: Criterion
    currency: Currency
    stream_ids: tuple[str, ...]
    amounts: tuple[Money, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class BandInAnotherCurrency:
    """An absolute band is stated in one currency and the pair is compared in another.

    Its sibling of :class:`NoQuestionAmountInTheCurrencyCompared` for the shape that does not
    resolve against the question at all: an absolute band **is** its width, and a width in
    hryvnia says nothing about how close two dollar figures are. Refused rather than converted,
    because no exchange rate is consulted anywhere in this pass.
    """

    criterion: Criterion
    declared_in: Currency
    compared_in: Currency


@dataclass(frozen=True, slots=True, kw_only=True)
class NoSurveyToRunOver:
    """The section never surveyed, so there is no population to run a pass over (research D6a).

    Carries the record that replaced the survey, verbatim. An empty ``DominanceResult`` would be
    the empty set standing for a failure FR-026 forbids, and would be indistinguishable from the
    legitimate empty set of a section that evaluated nothing.
    """

    refusal: SurveyRefused | BenchmarkYieldsNoCandidate


DominanceRefused = (
    NoBenchmarkToStandAgainst
    | BenchmarkWasWithheld
    | BandBelowTheAcyclicityFloor
    | NoQuestionAmountInTheCurrencyCompared
    | SeveralQuestionAmountsInTheCurrencyCompared
    | BandInAnotherCurrency
    | NoSurveyToRunOver
)
"""The pass did not stand up, returned **instead of** a set: no empty set standing for a
failure, no partial set, no ``None``.

**Two things a reader expects here and does not find.** A missing or undeclared objective set is
a **load failure** (FR-001, FR-001a), and a runtime refusal for it would be a second answer to a
question the loader has already refused. A figure that cannot be compared is a property of a
**pair** (FR-008a), and refusing the section for it would drop every verdict around it.
"""


__all__ = [
    "BandBelowTheAcyclicityFloor",
    "BandInAnotherCurrency",
    "BenchmarkStanding",
    "BenchmarkWasWithheld",
    "DateFigure",
    "DayWidth",
    "DeliveredInTwoCurrencies",
    "DominanceRefused",
    "DominanceResult",
    "DominanceVerdict",
    "Dominated",
    "EveryOtherIsDominated",
    "EveryOtherIsNotPlaced",
    "Figure",
    "FigureMissing",
    "FigureUnavailable",
    "HurdleIsDominated",
    "Incomparable",
    "IncomparablePair",
    "IncomparableReason",
    "Indistinguishable",
    "LeftDominates",
    "MemberRestsOn",
    "Mixed",
    "MoneyFigure",
    "MoneyWidth",
    "Neither",
    "NoBenchmarkToStandAgainst",
    "NoQuestionAmountInTheCurrencyCompared",
    "NoStatedAssumptionSeparatesThem",
    "NoSurveyToRunOver",
    "NotPlaced",
    "NothingDominatesTheHurdle",
    "OnlyOneEvaluated",
    "PairVerdict",
    "ResolvedBand",
    "RightDominates",
    "SeparatingAssumptions",
    "SeveralQuestionAmountsInTheCurrencyCompared",
    "TheSetDoesNotHaveOneMember",
    "TooCloseToCall",
    "WhyOneMember",
    "Width",
]
