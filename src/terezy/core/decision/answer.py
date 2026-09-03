"""The one verb: a declared question in, an answer that refuses in parts out.

015. Everything before this feature costs a tuple somebody handed it or finds one; this answers
a sentence a person said out loud. It is **one** verb, and the two that will be proposed beside
it are not verbs: the cross-horizon reading is :func:`cross_horizon` over the answer, and
*"just rank it"* is this function with a question declaring one horizon.

**It calls 014's ``survey`` and 010's ``compare``; it forks neither.** No feasibility rule, no
objective, no scoring weight, no shortlist. The two rules it adds about *candidates* are both
section-level, so neither needs a change to 010's union: a candidate whose money the holding
released after the window is withheld rather than labelled (FR-030), and a reserve gets a
verdict that removes nothing (FR-018).

**No exchange rate is derived and none is read from a series** (FR-021). A cross-currency
candidate is evaluated and reported and not ranked, by 010's ``RateNotComparable``; a reserve in
a currency the arrivals do not deliver is *not covered by the plan* rather than converted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from terezy.core.decision import candidates as enumeration
from terezy.core.decision.tuple_outcome import Registries
from terezy.core.primitives import money, staleness
from terezy.core.primitives import provenance as prov
from terezy.core.results import candidates as candidate_results
from terezy.core.results.answer import (
    AmountForAnUndeclaredStream,
    Answer,
    BenchmarkOutsideTheSubjects,
    BenchmarkYieldsNoCandidate,
    BenchmarkYieldsSeveralCandidates,
    CoveredByThePlan,
    DeclaredSubject,
    Direction,
    Exclusion,
    HorizonSection,
    KeyAgreement,
    MoneyArrivesAfterHorizon,
    NoHorizonDeclared,
    NoSubjectDeclared,
    PartialExitWouldBeNeeded,
    Placement,
    PlanForNothing,
    Refused,
    ReserveVerdict,
    ResolvedSubject,
    SectionOutcome,
    SectionsAgreeByKey,
    SectionsDisagreeByKey,
    StatedExclusion,
    StreamWithNoAmount,
    SubjectCounts,
    SubjectNotAssessed,
    SubjectReached,
    SubjectStanding,
    SubjectUndeclared,
    SubjectUnreached,
    TwoIdenticalHorizons,
    UndeclaredSubject,
)
from terezy.core.results.candidates import CandidateSet, CandidateSurvey
from terezy.core.results.tuple import BenchmarkUnavailable, Comparison, Tuple, TupleOutcome

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from terezy.core.instruments.groups import InstrumentGroup
    from terezy.core.instruments.interface import DateRange
    from terezy.core.results.composed import SegmentBound
    from terezy.core.results.question import Question, Reserve
    from terezy.core.results.tuple import Arrival, InstrumentPlan
    from terezy.core.routes.legs import Route
    from terezy.core.scenarios.early_exit import SoldEarly

REAL_TERMS_SUPPLIED_BY = "a real-terms rate on TupleOutcome, which feature 010 does not produce"
INCOME_TAX_SUPPLIED_BY = "a deployable-capacity figure, which is a question about a stream"
RATE_RISK_SUPPLIED_BY = "[[future]] secondary-market-rate-risk"
ACCRUED_INTEREST_SUPPLIED_BY = (
    "a declared accrual basis, and for a listed schedule the [[future]] "
    "enumerated-accrued-interest entry"
)


@dataclass(frozen=True, slots=True, kw_only=True)
class AnswerInputs:
    """Everything the verb reads. ``Registries`` alone cannot carry it.

    The **candidate ceiling** comes from ``data/candidates/`` and the **segment bound** from
    ``data/composition/``, and 014's ``survey`` takes both as its own arguments -- so a verb
    that could not receive them could not call it. The **group vocabulary** is here for a
    different reason: without it a declared group nobody labelled and a word nobody declared
    would be the same answer, and telling them apart is FR-008a's whole guard.
    """

    registries: Registries
    routes: Mapping[str, Route]
    """The route set of the one regime in force, narrowed by the caller (004 FR-017)."""

    groups: Mapping[str, InstrumentGroup]
    bound: SegmentBound
    ceiling: candidate_results.CandidateCeiling


def answer(question: Question, inputs: AnswerInputs, as_of: date) -> Answer | Refused:
    """Answer one declared question over one registry, at one as-of date.

    Pure: no clock, no I/O, no randomness. ``as_of`` is a parameter rather than a field of the
    question because it decides staleness and nothing else, and a file whose horizons moved with
    the calendar would be a different question every day under one digest (FR-006).
    """
    wrong = _about_the_question(question, inputs)
    if wrong is not None:
        return wrong
    subjects = _resolve(question, inputs)
    considered = _considered_ids(subjects)
    if question.benchmark_instrument_id not in _named_or_reached(subjects):
        return BenchmarkOutsideTheSubjects(instrument_id=question.benchmark_instrument_id)
    unused = _plan_for_nothing(question, subjects)
    if unused is not None:
        return unused
    plans = _expanded_plans(question, subjects)
    sections: list[HorizonSection] = []
    for horizon in question.horizons:
        outcome = _section_outcome(
            question, inputs, horizon, considered=considered, plans=plans, as_of=as_of
        )
        if isinstance(outcome, BenchmarkYieldsSeveralCandidates):
            return outcome
        sections.append(_section(question, subjects, horizon, outcome))
    return Answer(
        question=question,
        as_of=as_of,
        subjects=subjects,
        sections=tuple(sections),
        excludes=_answer_wide_excludes(),
        provenance=prov.merge_all(_reported_provenance(sections)),
        staleness=staleness.merge_all(_reported_staleness(sections)),
    )


# ---------------------------------------------------------------------------
# What is wrong with the question itself
# ---------------------------------------------------------------------------


def _about_the_question(question: Question, inputs: AnswerInputs) -> Refused | None:
    """The five ways a question does not stand up on its own, in the order a reader would ask.

    The other three members of ``Refused`` are about the question meeting a **registry** -- the
    benchmark it names, and a plan for a word nothing reaches -- and are decided where that
    resolution happens.

    All five are reachable **only** from a caller-built record: the loader refuses every one of
    them before the verb sees it -- no horizon, a repeated window and no subject in
    ``question_from_document``, an unknown stream and a missing amount in ``check_question`` --
    because in an artefact under review each of them is a typo rather than a decision. Stated
    here as well because a record no file produced has had none of that said about it.
    """
    if not question.horizons:
        return NoHorizonDeclared()
    if not question.subjects and not question.every_declared_instrument:
        return NoSubjectDeclared()
    for position, horizon in enumerate(question.horizons):
        if horizon in question.horizons[:position]:
            return TwoIdenticalHorizons(horizon=horizon)
    for stream_id in sorted(question.amounts):
        if stream_id not in inputs.registries.streams:
            return AmountForAnUndeclaredStream(stream_id=stream_id)
    for stream_id in sorted(inputs.registries.streams):
        if stream_id not in question.amounts:
            return StreamWithNoAmount(stream_id=stream_id)
    return None


# ---------------------------------------------------------------------------
# Subjects: what the question named, and what the registry made of it
# ---------------------------------------------------------------------------


def _resolve(question: Question, inputs: AnswerInputs) -> tuple[ResolvedSubject, ...]:
    """Each named word as an instrument id, a declared group, or nothing at all (FR-007).

    **Read from the declared label alone.** Nothing here consults an instrument's class, its id
    prefix, its tax class or the venue it is bought at, and all four look right on today's
    registry -- ``tests/contract/test_group_membership_is_declared.py`` builds one instrument
    that trips every one of them and asserts it is in no group.
    """
    if question.every_declared_instrument:
        return tuple(
            DeclaredSubject(named=instrument_id, is_group=False, ids=(instrument_id,))
            for instrument_id in sorted(_declared(inputs))
        )
    return tuple(_resolve_one(word, inputs) for word in question.subjects)


def _resolve_one(word: str, inputs: AnswerInputs) -> ResolvedSubject:
    """One word. An instrument id first, then the group vocabulary, then nothing."""
    if word in _declared(inputs):
        return DeclaredSubject(named=word, is_group=False, ids=(word,))
    if word in inputs.groups:
        return DeclaredSubject(
            named=word,
            is_group=True,
            ids=tuple(
                sorted(
                    instrument_id
                    for instrument_id, labels in _labels(inputs).items()
                    if word in labels
                )
            ),
        )
    return UndeclaredSubject(named=word)


def _declared(inputs: AnswerInputs) -> frozenset[str]:
    """Every instrument id the registry declares, of either declaration kind."""
    return frozenset(inputs.registries.instruments) | frozenset(inputs.registries.funds)


def _labels(inputs: AnswerInputs) -> Mapping[str, tuple[str, ...]]:
    """Which groups each declared instrument declares itself into."""
    return {
        **{name: declared.groups for name, declared in inputs.registries.instruments.items()},
        **{name: declared.groups for name, declared in inputs.registries.funds.items()},
    }


def _considered_ids(subjects: Sequence[ResolvedSubject]) -> frozenset[str]:
    """The union of every declared subject's ids, deduplicated (FR-007b).

    An id named twice -- by a group and by itself, or by two overlapping groups -- yields one
    candidate and is counted once. Stated as a rule rather than left to the loader because an id
    counted twice is a wrong count in exactly the line FR-010 exists to produce.
    """
    return frozenset(
        instrument_id
        for subject in subjects
        if isinstance(subject, DeclaredSubject)
        for instrument_id in subject.ids
    )


def _named_or_reached(subjects: Sequence[ResolvedSubject]) -> frozenset[str]:
    """The words the question wrote, plus every id they reach.

    What a benchmark and a run plan are both checked against. A benchmark **outside** the
    subjects can never be a member of the set, which is a fact about the question (FR-026); a
    benchmark that *is* a named subject and reaches nothing is that section's own refusal, which
    is a fact about one enumeration -- and the two must not be the same answer, because SC-020's
    question names four words the registry declares none of and is still answerable.
    """
    return frozenset(subject.named for subject in subjects) | _considered_ids(subjects)


def _plan_for_nothing(
    question: Question, subjects: Sequence[ResolvedSubject]
) -> PlanForNothing | None:
    """A plan keyed by a word that runs nothing at all."""
    reachable = _named_or_reached(subjects)
    for word in sorted(question.plans):
        if word not in reachable:
            return PlanForNothing(named=word)
    return None


def _expanded_plans(
    question: Question, subjects: Sequence[ResolvedSubject]
) -> Mapping[str, tuple[InstrumentPlan, ...]]:
    """The plans, expanded to 014's per-instrument mapping.

    **A plan keyed by an instrument id wins over its subject's**, and the shipped question needs
    it: a chosen point has to lie inside the instrument's *own* declared range, and the two
    Inzhur funds state ranges that do not overlap -- so one plan for the group could not be a
    point inside both. The 016 argument survives, because what a new issue joins is a group
    whose plan does not have to name it.

    **Equal plans are deduplicated, in order.** Two subjects reaching one id with the same plan
    is FR-007b's case and yields one candidate; with *different* plans it is two honest ways of
    running the instrument and both survive. This is also what makes 014's ``DuplicateRunPlan``
    unreachable from a question rather than a trap in it.
    """
    expanded: dict[str, list[InstrumentPlan]] = {}
    for subject in subjects:
        if not isinstance(subject, DeclaredSubject):
            continue
        for instrument_id in subject.ids:
            supplied = expanded.setdefault(instrument_id, [])
            for plan in question.plans.get(instrument_id) or question.plans.get(subject.named, ()):
                if plan not in supplied:
                    supplied.append(plan)
    return {instrument_id: tuple(plans) for instrument_id, plans in expanded.items()}


# ---------------------------------------------------------------------------
# One section
# ---------------------------------------------------------------------------


def _section_outcome(
    question: Question,
    inputs: AnswerInputs,
    horizon: DateRange,
    *,
    considered: frozenset[str],
    plans: Mapping[str, tuple[InstrumentPlan, ...]],
    as_of: date,
) -> SectionOutcome | BenchmarkYieldsSeveralCandidates:
    """One horizon's whole survey, or the typed refusal that replaces it (FR-014).

    ``as_of`` is the **verb's**, not the question's ``asked_on``: it decides staleness and
    nothing else, and putting a clock in the artefact is what FR-006 refuses. Answering the same
    file next year must age its sources a year, or the figure is more confident than its inputs.

    The set is enumerated **twice**: once here to resolve the benchmark's five-term key, and
    once inside ``survey``. Enumeration is a pure function of the same inputs, so the two agree
    by construction -- and the alternative is forking 014's accounting, which is the one thing
    this feature must not do.
    """
    asked = candidate_results.Question(
        amounts=question.amounts,
        horizon=horizon,
        as_of=as_of,
        continuation=question.continuation,
        plans=plans,
        bound=inputs.bound,
        regime_id=question.regime_id,
        subjects=considered,
    )
    enumerated = enumeration.enumerate_candidates(
        registries=inputs.registries,
        routes=inputs.routes,
        question=asked,
        ceiling=inputs.ceiling,
    )
    if not isinstance(enumerated, CandidateSet):
        return enumerated
    keys = [
        item.key
        for item in enumerated.candidates
        if item.key.instrument_id == question.benchmark_instrument_id
    ]
    if len(keys) > 1:
        return BenchmarkYieldsSeveralCandidates(
            instrument_id=question.benchmark_instrument_id, occurrences=len(keys)
        )
    if not keys:
        return BenchmarkYieldsNoCandidate(
            instrument_id=question.benchmark_instrument_id, enumerated=enumerated
        )
    return enumeration.survey(
        registries=inputs.registries,
        routes=inputs.routes,
        question=asked,
        ceiling=inputs.ceiling,
        benchmark=keys[0],
    )


def _section(
    question: Question,
    subjects: Sequence[ResolvedSubject],
    horizon: DateRange,
    outcome: SectionOutcome,
) -> HorizonSection:
    """One section: the survey whole, plus what this feature withholds and what it verdicts."""
    late = _arrives_after_horizon(outcome, horizon)
    withheld = frozenset(item.key for item in late)
    return HorizonSection(
        horizon=horizon,
        outcome=outcome,
        standings=_standings(subjects, outcome),
        arrives_after_horizon=late,
        reserves=tuple(
            verdict
            for reserve in question.reserves
            for verdict in _verdicts(outcome, reserve, withheld)
        ),
        excludes=tuple(
            stated
            for item in _outcomes(outcome)
            if item.sold_early is not None and item.key not in withheld
            for stated in _early_exit_exclusions(item.key, item.sold_early)
        ),
    )


def _outcomes(outcome: SectionOutcome) -> tuple[TupleOutcome, ...]:
    """Every candidate this section evaluated, before FR-030 withholds any."""
    if not isinstance(outcome, CandidateSurvey):
        return ()
    return enumeration.evaluated(outcome.comparison)


def _arrives_after_horizon(
    outcome: SectionOutcome, horizon: DateRange
) -> tuple[MoneyArrivesAfterHorizon, ...]:
    """The candidates FR-030 withholds, naming each and the date its money actually arrives.

    The test is on the date the **holding released** the money, and the date reported is the
    date it reached a spendable endpoint. They differ by the way out's declared latency, and
    testing on the arrival would withhold every figure there is: a sale at ``horizon.end``
    settles a few days later on every declared corridor, and 010's ``accounts_for`` already says
    settlement latency sits *inside* the span because waiting is a cost. What FR-030 exists to
    withhold is a candidate whose money comes out long after the window **because its plan says
    so** -- measured, ``inzhur_miltech``, whose plan requests an exit sixteen months past a
    one-month horizon.
    """
    return tuple(
        MoneyArrivesAfterHorizon(key=item.key, arrives_on=item.arrivals[-1].arrived_on)
        for item in _outcomes(outcome)
        if item.arrivals and item.arrivals[-1].released_on > horizon.end
    )


def _standings(
    subjects: Sequence[ResolvedSubject], outcome: SectionOutcome
) -> tuple[SubjectStanding, ...]:
    """Where each named subject stands here, in one of the four states FR-010 distinguishes.

    **A section that refused before enumerating knows nothing about any subject**, and saying
    *declared but unreached* there would name a remedy -- declare a corridor -- for a cause that
    is a ceiling or a bound. That is a guard whose message is false, one layer up.
    """
    enumerated = _enumerated_of(outcome)
    if enumerated is None:
        return tuple(
            SubjectUndeclared(named=subject.named)
            if isinstance(subject, UndeclaredSubject)
            else SubjectNotAssessed(named=subject.named, ids=subject.ids)
            for subject in subjects
        )
    reached = frozenset(item.key.instrument_id for item in enumerated.candidates)
    return tuple(
        SubjectUndeclared(named=subject.named)
        if isinstance(subject, UndeclaredSubject)
        else (
            SubjectReached(
                named=subject.named,
                ids=subject.ids,
                with_candidates=tuple(name for name in subject.ids if name in reached),
            )
            if any(name in reached for name in subject.ids)
            else SubjectUnreached(named=subject.named, ids=subject.ids)
        )
        for subject in subjects
    )


def _enumerated_of(outcome: SectionOutcome) -> CandidateSet | None:
    """The set this section enumerated, or ``None`` where it refused before enumerating.

    A benchmark that yields no candidate is **not** that case: enumeration succeeded and the
    set is in hand, so a section carrying it knows exactly which subjects connect.
    """
    match outcome:
        case CandidateSurvey():
            return outcome.enumerated
        case BenchmarkYieldsNoCandidate():
            return outcome.enumerated
        case _:
            return None


def _verdicts(
    outcome: SectionOutcome, reserve: Reserve, withheld: frozenset[Tuple]
) -> tuple[ReserveVerdict, ...]:
    """One verdict per evaluated candidate for one reserve (FR-016, FR-017).

    Computed over the candidates whose figures this section reports, so a candidate withheld by
    FR-030 gets no verdict: a verdict over arrivals the section refused to rank would be a claim
    about a figure it declined to show.
    """
    return tuple(_verdict(item, reserve) for item in _outcomes(outcome) if item.key not in withheld)


def _verdict(item: TupleOutcome, reserve: Reserve) -> ReserveVerdict:
    """Whether this candidate's own arrivals put the reserve where it can be spent, in time.

    **No rate is consulted** (FR-021). Only arrivals in the reserve's own currency count, so a
    reserve in a currency the arrivals do not deliver is short by the whole of it -- which is
    *a partial exit would be needed* rather than a conversion at a rate nobody declared.
    """
    read: list[Arrival] = []
    running = money.zero(reserve.amount.currency)
    covered_on: date | None = None
    for arrival in item.arrivals:
        if (
            arrival.arrived_on > reserve.by
            or arrival.amount.currency is not reserve.amount.currency
        ):
            continue
        read.append(arrival)
        running = money.add(running, arrival.amount)
        if covered_on is None and running.amount >= reserve.amount.amount:
            covered_on = arrival.arrived_on
    if covered_on is not None:
        return CoveredByThePlan(
            key=item.key,
            reserve=reserve,
            arrivals_read=tuple(read),
            covered_on=covered_on,
        )
    short_by = money.sub(reserve.amount, running)
    return PartialExitWouldBeNeeded(
        key=item.key,
        reserve=reserve,
        arrivals_read=tuple(read),
        short_by=short_by,
    )


# ---------------------------------------------------------------------------
# What the answer excludes, and what it rests on
# ---------------------------------------------------------------------------


def _answer_wide_excludes() -> tuple[StatedExclusion, ...]:
    """The two an answer always states, whatever it computed.

    Every candidate-specific exclusion is on its **section**, because it is specific to a
    candidate *in a window*: the same key can be an early exit at one month and a
    hold-to-maturity at twelve.
    """
    return (
        StatedExclusion(
            what=Exclusion.NO_REAL_TERMS_FIGURE,
            applies_to=None,
            supplied_by=REAL_TERMS_SUPPLIED_BY,
            direction=None,
        ),
        StatedExclusion(
            what=Exclusion.NO_INCOME_TAX_ON_THE_STATED_AMOUNT,
            applies_to=None,
            supplied_by=INCOME_TAX_SUPPLIED_BY,
            direction=None,
        ),
    )


def _early_exit_exclusions(key: Tuple, sold: SoldEarly) -> tuple[StatedExclusion, ...]:
    """What an early-exit figure does not account for, and which way each one errs.

    Rate risk is **symmetric** -- a bond sold after rates rise fetches less than its spread
    implies and one sold after rates fall fetches more -- so it carries no direction, and SC-026
    asserts that absence rather than tolerating it: a sign asserted without a warrant is a number
    more confident than its inputs, which is worse than one left unstated.

    **The accrued-interest claim is on every early exit, not only on the ones a coupon detached
    from.** What it states is that a dirty quotation is carried across a gap without the accrual
    that gap builds, and the gap exists whenever the sale is not struck on the quotation's own
    day -- which for a horizon's end is always. Gating it on a detachment would have left it
    unstated on the majority of the owner's sales while the figure was understated all the same.
    """
    return (
        StatedExclusion(
            what=Exclusion.EARLY_EXIT_IS_A_POINT_NOT_A_DISTRIBUTION,
            applies_to=key,
            supplied_by=sold.assumption.id,
            direction=Direction.MORE_CERTAIN_THAN_IT_IS,
        ),
        StatedExclusion(
            what=Exclusion.EARLY_EXIT_SPREAD_IS_A_SELLERS_QUOTE,
            applies_to=key,
            supplied_by=sold.assumption.id,
            direction=Direction.UNDERSTATED,
        ),
        StatedExclusion(
            what=Exclusion.EARLY_EXIT_CARRIES_NO_RATE_RISK,
            applies_to=key,
            supplied_by=RATE_RISK_SUPPLIED_BY,
            direction=None,
        ),
        StatedExclusion(
            what=Exclusion.EARLY_EXIT_IGNORES_ACCRUED_INTEREST,
            applies_to=key,
            supplied_by=ACCRUED_INTEREST_SUPPLIED_BY,
            direction=Direction.UNDERSTATED,
        ),
    )


def _reported_provenance(sections: Sequence[HorizonSection]) -> list[prov.Provenance]:
    """Every mark behind every figure the answer reports, and behind the sets it enumerated."""
    marks: list[prov.Provenance] = []
    for section in sections:
        enumerated = _enumerated_of(section.outcome)
        if enumerated is not None:
            marks.append(enumerated.provenance)
        marks.extend(item.provenance for item in section_evaluated(section))
    return marks


def _reported_staleness(sections: Sequence[HorizonSection]) -> list[staleness.StalenessVerdict]:
    """The merged verdict over the same sources."""
    verdicts: list[staleness.StalenessVerdict] = []
    for section in sections:
        enumerated = _enumerated_of(section.outcome)
        if enumerated is not None:
            verdicts.append(enumerated.staleness)
        verdicts.extend(item.staleness for item in section_evaluated(section))
    return verdicts


# ---------------------------------------------------------------------------
# The derived readings
# ---------------------------------------------------------------------------


def subject_counts(answer_: Answer, section: HorizonSection) -> SubjectCounts:
    """How many named subjects each state holds, and how many ids they deduplicate to.

    Derived rather than stored (014 FR-011): a count beside the list it counts is where the two
    come to disagree. The two figures are reported together because conflating them is the
    defect -- *he named four things and two can be answered* is not *seven instruments were
    enumerated*.
    """
    return SubjectCounts(
        reached=sum(1 for item in section.standings if isinstance(item, SubjectReached)),
        declared_but_unreached=sum(
            1 for item in section.standings if isinstance(item, SubjectUnreached)
        ),
        undeclared=sum(1 for item in section.standings if isinstance(item, SubjectUndeclared)),
        not_assessed=sum(1 for item in section.standings if isinstance(item, SubjectNotAssessed)),
        ids_considered=len(_considered_ids(answer_.subjects)),
    )


def section_evaluated(section: HorizonSection) -> tuple[TupleOutcome, ...]:
    """The candidates this section reports figures for: 014's population, less FR-030's.

    Ranked or not -- ``BenchmarkUnavailable.scored`` exists for exactly the unranked case, and
    this is the population a reader is shown when :func:`section_ranking` is empty.

    Derived rather than rebuilt, because FR-014 requires 014's survey to be carried **whole**:
    reconstructing a ``Comparison`` without a candidate would be this feature computing a
    comparison it did not run, which is the privileged side channel 010 FR-012 forbids.
    """
    withheld = frozenset(item.key for item in section.arrives_after_horizon)
    return tuple(item for item in _outcomes(section.outcome) if item.key not in withheld)


def section_ranking(section: HorizonSection) -> tuple[TupleOutcome, ...]:
    """This section's ranking, in order, or empty where there is nothing to rank against.

    Empty in three cases, and all three are the same claim: **there is no benchmark here**.
    The comparison itself may be a ``BenchmarkUnavailable``; or it may be a ``Comparison``
    whose benchmark FR-030 withheld, which is the case a reader would miss -- the figures are
    all there, the head of the list looks like a winner, and the thing it would be a winner
    against is not being shown. 010 FR-011 says the hurdle is always scored and always shown,
    so a ranking without it is not offered.

    :func:`section_evaluated` is what carries the figures in those cases: they were computed and
    throwing them away would hide work the owner paid for.
    """
    if not isinstance(section.outcome, CandidateSurvey):
        return ()
    comparison = section.outcome.comparison
    if not isinstance(comparison, Comparison):
        return ()
    withheld = frozenset(item.key for item in section.arrives_after_horizon)
    if comparison.ranked[comparison.benchmark].key in withheld:
        return ()
    return tuple(item for item in comparison.ranked if item.key not in withheld)


def benchmark_unavailable(section: HorizonSection) -> BenchmarkUnavailable | None:
    """010's record where this section had no benchmark to rank against, or ``None``."""
    if not isinstance(section.outcome, CandidateSurvey):
        return None
    comparison = section.outcome.comparison
    return comparison if isinstance(comparison, BenchmarkUnavailable) else None


def cross_horizon(answer_: Answer) -> tuple[Placement, ...]:
    """Where each candidate placed in each section, keyed by 014's five-term key (FR-015).

    One named function over the answer, never a stored second copy. The alignment is exact
    rather than approximate: 014 FR-023 fixes the key as the five declared terms and nothing
    else, so two sections align by key equality with nothing to reconcile.
    """
    order: list[Tuple] = []
    for section in answer_.sections:
        for item in _outcomes(section.outcome):
            if item.key not in order:
                order.append(item.key)
    rankings = [
        {item.key: position for position, item in enumerate(section_ranking(section))}
        for section in answer_.sections
    ]
    return tuple(
        Placement(key=key, ranks=tuple(ranking.get(key) for ranking in rankings)) for key in order
    )


def key_agreement(answer_: Answer) -> KeyAgreement:
    """Whether every section enumerated the same candidate keys (FR-013).

    Checked per run rather than assumed. Measured on 2026-08-30 the shipped registry produces
    identical keys across 1, 3 and 12 months, and that is an observed property of today's
    enumeration rather than a contract -- so an inequality is reported as a finding instead of
    being smoothed over.
    """
    by_index = {
        index: tuple(item.key for item in item_set.candidates)
        for index, item_set in enumerate(
            _enumerated_of(section.outcome) for section in answer_.sections
        )
        if item_set is not None
    }
    per_section = list(by_index.values())
    shared = (
        frozenset.intersection(*[frozenset(keys) for keys in per_section])
        if per_section
        else frozenset()
    )
    only_in = {
        index: tuple(key for key in keys if key not in shared)
        for index, keys in by_index.items()
        if any(key not in shared for key in keys)
    }
    if only_in:
        return SectionsDisagreeByKey(only_in=only_in)
    return SectionsAgreeByKey(keys=per_section[0] if per_section else ())


def undeclared(answer_: Answer) -> tuple[UndeclaredSubject, ...]:
    """The words the owner wrote that the registry declares nothing by (FR-009).

    *You named this and nothing declares it* is the sentence worth having, and its remedy is a
    **declaration** -- a different job from a corridor and from a different amount.
    """
    return tuple(item for item in answer_.subjects if isinstance(item, UndeclaredSubject))


def considered_ids(answer_: Answer) -> tuple[str, ...]:
    """Every instrument id the question's subjects resolve to, deduplicated and sorted."""
    return tuple(sorted(_considered_ids(answer_.subjects)))


__all__ = [
    "AnswerInputs",
    "answer",
    "benchmark_unavailable",
    "considered_ids",
    "cross_horizon",
    "key_agreement",
    "section_evaluated",
    "section_ranking",
    "subject_counts",
    "undeclared",
]
