"""The answer: what was computed, what refused, and what the question named that nothing is.

015 FR-020. This record is the API's contract with an interface nobody has chosen yet -- owner
decision D-B keeps the web framework unchosen *until the result schema has stabilised against
real output* -- which makes its shape the most consequential thing this feature specifies.

**Nothing here holds a string this feature composed.** Every string is an id, or a reason a
core record 010 and 014 own already wrote, carried verbatim. A headline, a verdict sentence or
a rendered amount would be a decision taken on behalf of that unchosen interface; the CLI
composes the sentences, over the same record a UI would read.

**Nothing here holds a `Mark` either** (FR-024). ``Mark`` is an ``api.diagrams`` enum and a core
record importing it fails ``lint-imports``. The answer carries ``Provenance`` and a
``StalenessVerdict`` -- core records -- and rendering those into marks is the api layer's,
through ``marks.epistemic``, which takes exactly those two.

**Counts are derived, never stored** (014 FR-011's rule). A section holds one standing per named
subject and :func:`terezy.core.decision.answer.subject_counts` derives the three numbers; two
fields holding one truth is where a tally comes to disagree with the records it summarises.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum

from terezy.core.instruments.interface import DateRange
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.staleness import StalenessVerdict
from terezy.core.results.candidates import CandidateSet, CandidateSurvey, SurveyRefused
from terezy.core.results.question import Question, Reserve
from terezy.core.results.tuple import Arrival, Tuple

# ---------------------------------------------------------------------------
# What the question named, and what the registry made of it
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class DeclaredSubject:
    """A word the owner wrote that the registry declares: an instrument id, or a group."""

    named: str
    """The word, exactly as the question wrote it."""

    is_group: bool
    """Whether it resolved through the group vocabulary or as an instrument id."""

    ids: tuple[str, ...]
    """The instrument ids it reaches, sorted (FR-008a).

    Printed for a **human** reader, and what is mechanically checkable is the narrower thing:
    that the membership is read from the labels instruments carry and moves when they do. A new
    issue declared without its label leaves this count *lower than the owner expects*, and no
    test can know he expected 24.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class UndeclaredSubject:
    """A word the owner wrote that resolves to no id at all (FR-009).

    Its own record rather than an empty :class:`DeclaredSubject`, because the remedies differ
    and FR-010 requires them distinguishable without reading prose: this one's remedy is a
    **declaration**, which is a different job from a corridor and from a different amount.
    ``cash`` and ``btc`` are exactly this over the shipped registry.
    """

    named: str


ResolvedSubject = DeclaredSubject | UndeclaredSubject
"""What one named subject turned out to be. Match exhaustively."""


# ---------------------------------------------------------------------------
# Where each named subject stands in one section
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class SubjectReached:
    """At least one of this subject's ids yielded a candidate in this section."""

    named: str
    ids: tuple[str, ...]
    with_candidates: tuple[str, ...]
    """Which of them actually yielded one. A subset, and the difference is worth seeing."""


@dataclass(frozen=True, slots=True, kw_only=True)
class SubjectUnreached:
    """Declared, and none of its ids yielded a candidate here (FR-010, FR-011).

    Distinct from :class:`SubjectUndeclared` because the remedy is a declaration of a different
    kind, and from a *dropped* candidate because a drop is the rejection of an option while this
    is the absence of one.

    **Two things reach this state and the section does not tell them apart.** An id the routes
    connect nothing to is in the section's ``no_candidate`` column, in ``compose``'s own words;
    an id with no ``data/access/`` entry is in no column at all, because enumeration walks the
    access declarations and never sees it. The second is a stated gap (2026-08-31): closing it
    means a third population for *declared and unreachable-in-principle*, which is 014's
    ``_considered`` to widen rather than this record's to guess at.
    """

    named: str
    ids: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class SubjectUndeclared:
    """Named, and the registry declares nothing by that word (FR-009)."""

    named: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SubjectNotAssessed:
    """This section refused **before** enumerating, so nothing is known about this subject.

    A fourth state rather than folding into :class:`SubjectUnreached`, because *unreached* names
    a remedy -- a corridor -- and a section that hit its candidate ceiling or was handed a
    segment bound admitting nothing has not looked. Telling a reader to declare a corridor there
    would send him to the wrong file, which is the same defect as a guard whose message is false.
    """

    named: str
    ids: tuple[str, ...]


SubjectStanding = SubjectReached | SubjectUnreached | SubjectUndeclared | SubjectNotAssessed
"""One named subject's state in one section. Four records rather than one with a flag, because
FR-010 requires them distinguishable without reading prose and the remedies differ."""


@dataclass(frozen=True, slots=True, kw_only=True)
class SubjectCounts:
    """How many of the **named subjects** each state holds, plus the deduplicated id count.

    The two are different sentences and the defect is conflating them: *he named four things and
    two can be answered* and *seven instruments were enumerated* are both true. Derived by one
    named function, never stored beside the standings.
    """

    reached: int
    declared_but_unreached: int
    undeclared: int
    not_assessed: int
    """Declared, and this section refused before it could look. Counted apart from
    *unreached*, whose remedy is a corridor and whose remedy this one is not."""

    ids_considered: int
    """The union of every declared subject's ids, deduplicated (FR-007b): an id named twice --
    by a group and by itself, or by two overlapping groups -- is counted once."""


# ---------------------------------------------------------------------------
# The two things a section withholds
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class MoneyArrivesAfterHorizon:
    """A candidate whose money arrives after the window it was compared over (FR-030).

    **Withheld rather than labelled**, and the difference is the whole requirement. Measured on
    2026-08-30 a one-month section had exactly one evaluated candidate, reporting 18.11% over a
    span running to 2028-01-20: under a label rule that section *is* one number wearing a
    caveat, and a reader takes the number. *Nothing could be ranked at one month, and here is
    why for each* is only available if the figure is withheld.
    """

    key: Tuple
    arrives_on: date


@dataclass(frozen=True, slots=True, kw_only=True)
class CoveredByThePlan:
    """The candidate's own arrivals put the reserve at a spendable endpoint in time (FR-017)."""

    key: Tuple
    reserve: Reserve
    arrivals_read: tuple[Arrival, ...]
    """Which arrivals the verdict was computed over (FR-019), so one computed over arrivals
    falling past the horizon's end is visible as such."""

    covered_on: date
    """When the running total first reached the reserve."""


@dataclass(frozen=True, slots=True, kw_only=True)
class PartialExitWouldBeNeeded:
    """The money is not all back in time, and a partly-liquidated holding is not projected.

    **Never phrased as *the reserve cannot be met***, which is a claim this system cannot make,
    and after FR-031 never as a missing price either: a resale price is a declaration like any
    other and selling 20 000 of a 50 000 position is priced by the same term. What does not
    exist is the **projection** -- a holding partly sold on a date carries different remaining
    cash flows and consumes basis under a declared consumption method.
    """

    key: Tuple
    reserve: Reserve
    arrivals_read: tuple[Arrival, ...]
    short_by: Money
    """The reserve less what arrives in its own currency by its date. No rate is consulted: a
    reserve in a currency the arrivals do not deliver is short by the whole of it (FR-021)."""


ReserveVerdict = CoveredByThePlan | PartialExitWouldBeNeeded
"""Exactly two values, and the second is a refusal. There is deliberately no third asserting
that the reserve *cannot* be met, and no verdict removes a candidate (FR-018)."""


# ---------------------------------------------------------------------------
# What the answer excludes
# ---------------------------------------------------------------------------


class Exclusion(Enum):
    """What an answer states it does not account for. A **closed** set (FR-023a).

    Closed for the reason every enumeration here is: a free-form exclusion would let one call
    site invent a token, and an exclusion that is not stated is a silent default -- the top
    severity class regardless of how small the omission looks.
    """

    NO_REAL_TERMS_FIGURE = "no_real_terms_figure"
    """Every rate reported is nominal. The real slot exists on feature 001's hurdle and on
    nothing a tuple produces, so deflating one is a new figure with a formula rather than a
    presentation choice."""

    NO_INCOME_TAX_ON_THE_STATED_AMOUNT = "no_income_tax_on_the_stated_amount"
    """Income tax is a question about a **stream**. Charging it on money already held would
    charge the owner twice for the same hryvnia."""

    EARLY_EXIT_IS_A_POINT_NOT_A_DISTRIBUTION = "early_exit_is_a_point_not_a_distribution"
    """The early-exit figure replaces a distribution with a point, for the one option chosen
    precisely for its optionality (FR-033)."""

    EARLY_EXIT_SPREAD_IS_A_SELLERS_QUOTE = "early_exit_spread_is_a_sellers_quote"
    """The quote is a seller's under today's conditions, and a seller's quote widens exactly
    when a forced sale is most likely (FR-033)."""

    EARLY_EXIT_CARRIES_NO_RATE_RISK = "early_exit_carries_no_rate_risk"
    """A bond's resale price also moves with market rates, and this figure does not model it.
    Modelling it is a secondary-market model and is out of scope."""


class Direction(Enum):
    """Which way an approximation errs, where it has a warranted direction."""

    MORE_CERTAIN_THAN_IT_IS = "more_certain_than_it_is"
    UNDERSTATED = "understated"


@dataclass(frozen=True, slots=True, kw_only=True)
class StatedExclusion:
    """One thing an answer does not account for, what it applies to, and what would supply it."""

    what: Exclusion
    applies_to: Tuple | None
    """The candidate, where the exclusion is specific to one. ``None`` for an answer-wide one."""

    supplied_by: str
    """A feature id or a declaration path -- named so the remedy is a thing rather than a
    search. An id, never a sentence: FR-020 forbids prose this feature composed."""

    direction: Direction | None
    """Which way the approximation errs, or ``None`` where no direction is **warranted**.

    Rate risk is symmetric: a bond sold after rates rise fetches less than its spread implies
    and one sold after rates fall fetches more. An approximation whose sign is unstated is
    incomplete; one whose sign is asserted without a warrant is a number more confident than
    its inputs, which is worse. SC-026 asserts the absence rather than tolerating it.
    """


# ---------------------------------------------------------------------------
# The answer
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkYieldsNoCandidate:
    """The named benchmark is a subject the registry declares, and it connects to nothing here.

    This feature's own, and **section-level**: whether an instrument yields a candidate is a
    fact about one horizon's enumeration. 014's ``BenchmarkNotACandidate`` cannot carry it,
    because that record holds the benchmark's five-term key and there is no key to hold -- the
    set contains none.
    """

    instrument_id: str

    enumerated: CandidateSet
    """The set that *was* enumerated, carried whole. Enumeration succeeded here -- what failed
    is the benchmark -- so throwing the set away would report every subject as unassessed when
    the section knows exactly which of them connect."""


SectionOutcome = CandidateSurvey | SurveyRefused | BenchmarkYieldsNoCandidate
"""What one horizon produced. 014's records whole, widened by exactly one (FR-014)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class HorizonSection:
    """One horizon and one outcome. A failed section is a section, never a missing one."""

    horizon: DateRange

    outcome: SectionOutcome
    """014's record, **whole** (FR-014). Any of its typed refusals -- and 010's
    ``BenchmarkUnavailable``, which lives inside a survey's comparison -- is carried unmodified,
    with every other section computed independently. This is the central requirement of the
    feature: measured today the one- and three-month sections fail and the twelve-month section
    fails differently, and all three facts are the answer.
    """

    standings: tuple[SubjectStanding, ...]
    """One per named subject, in the question's declared order (FR-010)."""

    arrives_after_horizon: tuple[MoneyArrivesAfterHorizon, ...]
    """Candidates withheld from this section's evaluated population (FR-030)."""

    reserves: tuple[ReserveVerdict, ...]
    """One per ``(candidate x reserve)`` over the candidates this section evaluated."""

    excludes: tuple[StatedExclusion, ...]
    """What **this section's** figures do not account for, per candidate (FR-023a, FR-033).

    On the section rather than on the answer, because a candidate is not sold early *as such*:
    it is sold early **in a window that ends before its terms do**. One key can be an early exit
    at one month and a hold-to-maturity at twelve, and an exclusion carried on the answer would
    tag both -- a hold-to-maturity figure inheriting a mark it did not earn, which is the exact
    defect FR-033's own edge case names.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class Answer:
    """One question, one ``as_of``, one section per declared horizon.

    **Nothing could be ranked, and here is why for each** is an ``Answer`` and never a
    :data:`Refused`. Measured on the shipped registry that is what the owner's own question
    produces, and it is the deliverable rather than the fallback.
    """

    question: Question
    """The whole question, beside every count it determined (FR-023, 014 FR-012 one layer up)."""

    as_of: date
    """When it was asked. Decides staleness and nothing else; the verb's, never the file's."""

    subjects: tuple[ResolvedSubject, ...]
    """What each named word turned out to be, in the order the question named them."""

    sections: tuple[HorizonSection, ...]
    """One per declared horizon, in the question's declared order (FR-012)."""

    excludes: tuple[StatedExclusion, ...]
    """What **every** figure in this answer does not account for (FR-023a).

    Answer-wide only: an exclusion specific to one candidate in one window is on that section,
    where the window is part of what it says.
    """

    provenance: Provenance
    """The union of the marks on every declaration behind every figure reported (FR-024)."""

    staleness: StalenessVerdict
    """The merged verdict over the same sources, aged at :attr:`as_of`."""


# ---------------------------------------------------------------------------
# The ways the question itself did not stand up
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class NoHorizonDeclared:
    """A question with no window has no section to put an answer in."""


@dataclass(frozen=True, slots=True, kw_only=True)
class NoSubjectDeclared:
    """Neither a subject list nor the every-instrument token. A question about nothing."""


@dataclass(frozen=True, slots=True, kw_only=True)
class AmountForAnUndeclaredStream:
    """An amount leaves a stream the registry does not declare."""

    stream_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StreamWithNoAmount:
    """A declared stream the question states no amount for -- the case that fails *silently*.

    Such a stream's pairs yield no candidate and never reach 014's ``survey``, so nothing raises
    and the answer is simply missing a stream nobody mentioned. In a file under review an
    omitted amount is a typo, not a fact about the money.
    """

    stream_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkOutsideTheSubjects:
    """The benchmark is not among the question's subjects, so it can never be in the set.

    014 FR-022 requires the benchmark to be a member of the enumerated set exactly once, and a
    benchmark outside the subjects cannot be one -- which makes it a fact about the *question*
    rather than about any horizon.
    """

    instrument_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkYieldsSeveralCandidates:
    """The benchmark instrument yields more than one candidate, naming the count.

    Picking the first would settle by declaration file order which figure everything else is
    ranked against.

    **Whole-answer rather than section-level, and the argument against is worth recording**:
    how many candidates an instrument yields is a fact about one enumeration, which is exactly
    why :class:`BenchmarkYieldsNoCandidate` *is* section-level. FR-026 nevertheless names this
    one among the ways the *question* does not stand up, and the reading it rests on is that an
    ambiguous benchmark is a question nobody can answer at any horizon: whichever candidate a
    section picked, another section could pick differently, and the cross-horizon reading would
    then compare two rankings measured against two different hurdles.
    """

    instrument_id: str
    occurrences: int


@dataclass(frozen=True, slots=True, kw_only=True)
class TwoIdenticalHorizons:
    """Two sections with the same window are not two answers, and the cross-horizon reading
    would key two rows the same."""

    horizon: DateRange


@dataclass(frozen=True, slots=True, kw_only=True)
class PlanForNothing:
    """A run plan keyed by a word that is neither a named subject nor an id the subjects reach.

    Refused rather than ignored, on the rule every declaration in this repository follows: a
    setting that is silently dropped is a stated choice that does nothing, and the run proceeds
    under settings the owner believes are in force.

    A plan for a subject that resolves to **nothing** is not this: ``cash`` is a legitimate
    subject with a legitimate plan and an empty answer, and refusing the question for it would
    discard the one line that says the registry declares nothing by that word (FR-009).
    """

    named: str


Refused = (
    NoHorizonDeclared
    | NoSubjectDeclared
    | AmountForAnUndeclaredStream
    | StreamWithNoAmount
    | BenchmarkOutsideTheSubjects
    | BenchmarkYieldsSeveralCandidates
    | TwoIdenticalHorizons
    | PlanForNothing
)
"""What is wrong with the **question**, returned *instead of* an answer and never beside one.

Anything about one horizon, one pair or one candidate is a part-refusal inside an ``Answer``
(FR-014). A different type rather than a weaker answer, on ``CompositionRefused``'s precedent.
"""


# ---------------------------------------------------------------------------
# The cross-horizon reading
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class Placement:
    """Where one candidate placed in each section, keyed by 014's five-term key (FR-015).

    Derived by one named function over the answer and **never** a stored second copy. The
    alignment is exact because 014 FR-023 fixes the key as the five declared terms and nothing
    else, so sections align by key equality with nothing to reconcile.
    """

    key: Tuple
    ranks: tuple[int | None, ...]
    """Its position in each section's ranking, or ``None`` where that section ranked it
    nowhere -- because it refused, because the section refused, or because its money arrives
    after the window (FR-030)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class SectionsAgreeByKey:
    """Every section enumerated the same candidate keys (FR-013)."""

    keys: tuple[Tuple, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class SectionsDisagreeByKey:
    """Two sections enumerated different keys, reported as a finding rather than smoothed over.

    Measured on 2026-08-30 the shipped registry produces identical keys across 1, 3 and 12
    months -- but that is an observed property of today's enumeration and not a contract, so it
    is checked per run on 014 FR-009's rule: a check cannot go stale silently and a sentence can.
    """

    only_in: Mapping[int, tuple[Tuple, ...]]
    """Which keys each section index holds that some other section does not."""


KeyAgreement = SectionsAgreeByKey | SectionsDisagreeByKey


__all__ = [
    "AmountForAnUndeclaredStream",
    "Answer",
    "BenchmarkOutsideTheSubjects",
    "BenchmarkYieldsNoCandidate",
    "BenchmarkYieldsSeveralCandidates",
    "CoveredByThePlan",
    "DeclaredSubject",
    "Direction",
    "Exclusion",
    "HorizonSection",
    "KeyAgreement",
    "MoneyArrivesAfterHorizon",
    "NoHorizonDeclared",
    "NoSubjectDeclared",
    "PartialExitWouldBeNeeded",
    "Placement",
    "PlanForNothing",
    "Refused",
    "ReserveVerdict",
    "ResolvedSubject",
    "SectionOutcome",
    "SectionsAgreeByKey",
    "SectionsDisagreeByKey",
    "StatedExclusion",
    "StreamWithNoAmount",
    "SubjectCounts",
    "SubjectNotAssessed",
    "SubjectReached",
    "SubjectStanding",
    "SubjectUndeclared",
    "SubjectUnreached",
    "TwoIdenticalHorizons",
    "UndeclaredSubject",
]
