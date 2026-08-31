"""Canonical form of a whole projection: the ledger's, plus the figures derived from it.

``ledger.canonical.of_result`` is typed on ``LedgerState``, because the ledger existed
before any result record did. It stays that way: widening it to
``LedgerState | Projection`` would make every caller unpack a union to find out which
shape it got back, and a module in ``core.ledger`` would acquire an import from
``core.results`` -- a dependency pointing the wrong way through the layer it sits in.

So this module **composes** it instead. :func:`of_projection` calls the ledger's function
for the ledger part and adds the derived figures beside it, which is the option the data
model left open for this phase (data-model.md, "Canonical form", the ⚙ note). The ledger
keeps one signature and one meaning.

The rules of the form are ``terezy.core.ledger.canonical``'s. The one worth repeating here,
because it is the one an editor of this module is tempted to break: **provenance is
deliberately excluded.** It identifies *sources*, so filling in a ``verified_on`` later would
change the digest even though no computed amount moved -- and C4 would then fail on a
documentation update, leaving no honest way to fix it except to stop trusting C4. The
unverified *mark* is a separate claim, asserted separately by E5.
"""

from __future__ import annotations

from typing import assert_never

from terezy.core.instruments.interface import Assumptions
from terezy.core.ledger import canonical as ledger_canonical
from terezy.core.ledger.canonical import Canonical
from terezy.core.primitives.conventions import AmountsAsDeclared, ConventionsApplied
from terezy.core.primitives.rates import NominalRate, RealRate, RealTermsUnavailable
from terezy.core.results.answer import (
    Answer,
    CoveredByThePlan,
    DeclaredSubject,
    HorizonSection,
    PartialExitWouldBeNeeded,
    ReserveVerdict,
    ResolvedSubject,
    SectionOutcome,
    StatedExclusion,
    SubjectNotAssessed,
    SubjectReached,
    SubjectStanding,
    SubjectUndeclared,
    SubjectUnreached,
    UndeclaredSubject,
)
from terezy.core.results.candidates import CandidateSurvey
from terezy.core.results.fund import FundAssumptions
from terezy.core.results.hurdle import HurdleRate, RealTerms
from terezy.core.results.project import (
    GovernedBy,
    Projection,
    PurchasePremium,
    TreatmentUnstated,
)
from terezy.core.results.schedule import CashFlowRow, CashFlowSchedule
from terezy.core.results.tuple import (
    BenchmarkUnavailable,
    Comparison,
    InstrumentPlan,
    Tuple,
    TupleOutcome,
)
from terezy.core.routes.path import ExitChain, candidate_id, exit_segments_of
from terezy.core.tax.interface import TaxCharge


def of_conventions(value: ConventionsApplied | AmountsAsDeclared) -> tuple[str, ...]:
    """Whichever statement a row makes about what shaped it, rendered so the two differ.

    Part of the identity of a result, not decoration: the same terms under ``act/365`` and
    under ``30/360`` are different schedules, and a digest that ignored the convention
    would call two genuinely different answers the same. The same argument reaches one step
    further -- a schedule whose amounts were **declared** and one whose amounts were
    computed from three conventions are two different claims about where the money came
    from, and a digest agreeing between them would report them as one (013 FR-016).

    The **reason** is rendered too, and for the same argument the ledger's canonical form
    makes about a causation's ``detail``: it is overridable, so two rows can make different
    statements about what shaped them, and a digest ignoring it would call two
    differently-explained results identical.

    The two are told apart by the **tag in slot 0**: a generative rendering opens with a
    periodicity, and no key of ``conventions.PERIODICITY_FNS`` may be spelled ``"declared"``.
    That is the whole of the separation -- both renderings are three entries long, so arity
    separates nothing -- and it is asserted rather than argued, in
    ``tests/unit/test_conventions_statement.py``.

    The three-name arm is deliberately **untagged**: it is
    byte-for-byte what it has always been, so no generative row's digest moves for a reason
    that is not about that row (013 SC-017).
    """
    match value:
        case ConventionsApplied():
            return (value.periodicity, value.day_count, value.business_day_rule)
        case AmountsAsDeclared():
            return ("declared", value.day_count, value.reason)
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(value)


def of_row(value: CashFlowRow) -> tuple[Canonical, ...]:
    """One schedule line: what moved, what was taxed on it, and what placed the date."""
    return (
        value.sequence,
        ledger_canonical.of_date(value.occurred_on),
        value.kind.value,
        ledger_canonical.of_optional_number(value.quantity),
        ledger_canonical.of_money(value.gross),
        ledger_canonical.of_money(value.tax),
        ledger_canonical.of_money(value.net),
        of_conventions(value.conventions),
        ledger_canonical.of_causation(value.caused_by),
    )


def of_schedule(value: CashFlowSchedule) -> tuple[Canonical, ...]:
    """The schedule: its currency, then its rows in ledger order.

    The rows are **not** re-sorted. Their order is the fold order, which is a fact about
    the stream, and normalising it away could digest two differently-ordered histories
    identically.
    """
    return (value.currency.value, tuple(of_row(row) for row in value.rows))


def of_charge(value: TaxCharge) -> tuple[Canonical, ...]:
    """One tax charge: both lines, their base, the class that produced them, and its year.

    ``tax_class_id`` is included because a zero charged by one class and a zero charged by
    another are different claims about the money, and the whole point of recording zeroes
    is that they name the rule that produced them.
    """
    return (
        value.event_sequence,
        ledger_canonical.of_money(value.pit),
        ledger_canonical.of_money(value.levy),
        ledger_canonical.of_money(value.total),
        ledger_canonical.of_money(value.taxable_base),
        value.tax_class_id,
        value.charged_for_year,
    )


def of_real_figure(value: RealRate | RealTermsUnavailable) -> Canonical:
    """One real figure, tagged so a number can never be confused with its absence.

    ``("real", <hex>, <basis>, <series id>, <first month>, <last month>)`` or
    ``("unavailable", <reason>)``. The tag is what makes the two cases distinguishable in the
    digest: an untagged rendering could let a real rate of zero and "there is no real rate"
    produce the same bytes, and those are opposite statements. The reason is included because
    it is part of what the result *says*.

    **The basis, the series and the window are in the digest, and they have to be** (007
    FR-010, FR-011). The same value deflated by observed CPI and by a declared assumption is
    two different claims, and the same value over two different windows is two different
    facts; a digest that agreed between them would report two results as one. Provenance stays
    out, as everywhere else in this module -- filling in a ``verified_on`` must not move a
    digest.
    """
    match value:
        case RealRate():
            return (
                "real",
                ledger_canonical.of_number(value.value),
                value.basis,
                value.series_id,
                value.window.first,
                value.window.last,
            )
        case RealTermsUnavailable():
            return ("unavailable", value.reason)
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(value)


def of_real_terms(value: RealTerms) -> Canonical:
    """The whole real slot: the realized figure and the assumed one, in that order, tagged.

    Two entries, always, even when both are unavailable -- because ``RealTerms`` is never
    itself unavailable and *which* half is missing is part of what the result says. Rendering
    them in a fixed order means the digest depends on which figure is which rather than on
    the order they happened to be built in.
    """
    return (of_real_figure(value.realized), of_real_figure(value.assumed))


def of_hurdle_rate(value: HurdleRate) -> tuple[Canonical, ...]:
    """The figures: both nominal rates, the real slot, the tax total, and both boundary sets.

    Both sets are emitted sorted, so the digest depends on their content and not on the
    iteration order of a ``frozenset``, which is not guaranteed stable across interpreter
    runs.

    ``accounts_for`` is in the digest as well as ``excludes``, so that a term moved from one
    set to the other moves the digest. With only ``excludes`` in it, a term added to
    ``accounts_for`` alone -- a *claim that the figure is now net of something* -- would move
    nothing.
    """
    return (
        ledger_canonical.of_number(value.nominal_ytm.value),
        ledger_canonical.of_number(value.nominal_cash_flow_return.value),
        of_real_terms(value.real),
        ledger_canonical.of_money(value.total_tax),
        tuple(sorted(value.accounts_for)),
        tuple(sorted(value.excludes)),
    )


def of_at_purchase(value: PurchasePremium) -> tuple[Canonical, ...]:
    """What was paid, what comes back as principal, the difference, and what governs it.

    The class the difference is realised under and the governing treatment are both
    **tagged**, so that a declared answer and its absence can never render as the same
    bytes: they are opposite claims -- one is a cited rule and the other
    is its absence -- and a digest agreeing between them would report an unanswered question
    as an answer.
    """
    match value.governed_by:
        case GovernedBy():
            governs: Canonical = (
                "governed",
                value.governed_by.category_id,
                value.governed_by.treatment,
            )
        case TreatmentUnstated():
            governs = ("unstated",)
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(value.governed_by)
    return (
        ledger_canonical.of_money(value.paid),
        ledger_canonical.of_money(value.principal_returned),
        ledger_canonical.of_money(value.difference),
        ("class", value.tax_class_id) if value.tax_class_id else ("undeclared",),
        governs,
    )


def of_projection(value: Projection) -> tuple[Canonical, ...]:
    """A whole projection: the ledger it came from, then everything derived from it.

    The ledger is included in full rather than summarised. The figures are a *claim* about
    those events, and a digest covering only the conclusions would agree between a correct
    projection and an incorrect one that happened to land on the same number.
    """
    return (
        ledger_canonical.of_result(value.ledger),
        of_schedule(value.schedule),
        tuple(of_charge(charge) for charge in value.charges),
        of_hurdle_rate(value.hurdle),
        of_at_purchase(value.at_purchase),
    )


# ---------------------------------------------------------------------------
# 015-the-question: the canonical form of a whole answer
# ---------------------------------------------------------------------------
#
# The same rule, restated where it is easiest to break: **provenance is excluded, and so are
# the reason strings**. A reason is 010's and 014's prose about a refusal, and a digest that
# moved when somebody improved a sentence would fail C4 on a wording edit -- while the *kind*
# of refusal, which is what the answer says, is rendered and cannot change silently.


def of_plan(value: InstrumentPlan) -> tuple[Canonical, ...]:
    """How a holding is run, by the choices that were stated rather than by the record's name.

    The kind alone would make two plans one term: a question may state several plans for one
    instrument -- ``DuplicateRunPlan`` refuses only plans that are *equal* -- and two candidates
    differing in the exit date alone are two options whose figures differ. Rendering the type
    name would give them one canonical form and one printed line, which is the collision the
    five-term key exists to prevent.

    The rationale strings are excluded for the reason every reason string here is: a digest that
    moved when somebody improved a sentence fails C4 on a wording edit.
    """
    match value:
        case Assumptions():
            return (type(value).__name__, value.consumption_method, value.coupon_policy)
        case FundAssumptions():
            point, rate = value.yield_point, value.exchange_rate
            return (
                type(value).__name__,
                value.consumption_method,
                value.liquidity_mode,
                value.buyback,
                None if value.exit_on is None else ledger_canonical.of_date(value.exit_on),
                None if point is None else ledger_canonical.of_number(point.rate),
                None if rate is None else ledger_canonical.of_number(rate.uah_per_unit),
            )
        case _:
            assert_never(value)


def of_tuple_key(value: Tuple) -> tuple[Canonical, ...]:
    """One candidate's five declared terms, and nothing else (014 FR-023).

    ``FROM_THE_DECLARATION`` renders under its **own** name. It is an instruction to read the
    inbound route's partner, not a way out, and rendering it as ``EXIT_BY_IDENTITY`` -- *the
    destination is already spendable* -- would put one member of the union under another's name
    in the record a digest is taken over.
    """
    way_out = value.route_out
    return (
        value.instrument_id,
        value.stream_id,
        candidate_id(value.route_in),
        exit_segments_of(way_out) if isinstance(way_out, ExitChain) else (way_out.value,),
        of_plan(value.exit_terms),
    )


def of_outcome(value: TupleOutcome) -> tuple[Canonical, ...]:
    """One evaluated candidate: its key, what reaches, and the rate it is ranked by."""
    rate = value.implied_rate
    return (
        of_tuple_key(value.key),
        ledger_canonical.of_money(value.reaches),
        ledger_canonical.of_number(rate.value) if isinstance(rate, NominalRate) else None,
        ledger_canonical.of_date(value.span.start),
        ledger_canonical.of_date(value.span.end),
        None if value.sold_early is None else ledger_canonical.of_date(value.sold_early.on),
    )


def of_section(value: HorizonSection) -> tuple[Canonical, ...]:
    """One horizon and everything it reported, in the order the record holds it."""
    return (
        ledger_canonical.of_date(value.horizon.start),
        ledger_canonical.of_date(value.horizon.end),
        _of_section_outcome(value.outcome),
        tuple(_of_standing(item) for item in value.standings),
        tuple(
            (of_tuple_key(item.key), ledger_canonical.of_date(item.arrives_on))
            for item in value.arrives_after_horizon
        ),
        tuple(_of_verdict(item) for item in value.reserves),
        tuple(_of_exclusion(item) for item in value.excludes),
    )


def of_answer(value: Answer) -> tuple[Canonical, ...]:
    """A whole answer: what was asked, what each section made of it, and what it excludes."""
    return (
        value.question.id,
        ledger_canonical.of_date(value.as_of),
        value.question.regime_id,
        value.question.continuation.value,
        tuple(_of_subject(item) for item in value.subjects),
        tuple(of_section(item) for item in value.sections),
        tuple(_of_exclusion(item) for item in value.excludes),
    )


def _of_subject(value: ResolvedSubject) -> tuple[Canonical, ...]:
    match value:
        case DeclaredSubject():
            return (value.named, "group" if value.is_group else "id", value.ids)
        case UndeclaredSubject():
            return (value.named, "undeclared")
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(value)


def _of_standing(value: SubjectStanding) -> tuple[Canonical, ...]:
    match value:
        case SubjectReached():
            return ("reached", value.named, value.ids, value.with_candidates)
        case SubjectUnreached():
            return ("unreached", value.named, value.ids)
        case SubjectUndeclared():
            return ("undeclared", value.named)
        case SubjectNotAssessed():
            return ("not_assessed", value.named, value.ids)
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(value)


def _of_verdict(value: ReserveVerdict) -> tuple[Canonical, ...]:
    match value:
        case CoveredByThePlan():
            return (
                "covered",
                of_tuple_key(value.key),
                ledger_canonical.of_money(value.reserve.amount),
                ledger_canonical.of_date(value.reserve.by),
                ledger_canonical.of_date(value.covered_on),
            )
        case PartialExitWouldBeNeeded():
            return (
                "partial_exit",
                of_tuple_key(value.key),
                ledger_canonical.of_money(value.reserve.amount),
                ledger_canonical.of_date(value.reserve.by),
                ledger_canonical.of_money(value.short_by),
            )
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(value)


def _of_exclusion(value: StatedExclusion) -> tuple[Canonical, ...]:
    return (
        value.what.value,
        None if value.applies_to is None else of_tuple_key(value.applies_to),
        value.supplied_by,
        None if value.direction is None else value.direction.value,
    )


def _of_section_outcome(value: SectionOutcome) -> tuple[Canonical, ...]:
    """The survey's whole shape, or the **kind** of refusal that replaced it.

    A refusal renders as its type name and nothing else. Which of them fired is what the answer
    says; the words it says it in are 010's and 014's, and a digest that moved when one was
    improved would fail on a wording edit with no honest way to fix it.
    """
    if not isinstance(value, CandidateSurvey):
        return (type(value).__name__,)
    comparison = value.comparison
    return (
        type(value).__name__,
        tuple((of_tuple_key(item.key), item.plan_position) for item in value.enumerated.candidates),
        tuple(
            (item.instrument_id, item.stream_id, type(item.why).__name__)
            for item in value.enumerated.no_candidate
        ),
        type(comparison).__name__,
        tuple(of_outcome(item) for item in _evaluated_of(comparison)),
        tuple((of_tuple_key(item.key), type(item.refusal).__name__) for item in comparison.refused),
    )


def _evaluated_of(value: Comparison | BenchmarkUnavailable) -> tuple[TupleOutcome, ...]:
    """Both cases carry the outcomes, and a benchmark that refused does not cost the rest."""
    match value:
        case Comparison():
            return (*value.ranked, *value.not_comparable)
        case BenchmarkUnavailable():
            return (*value.scored, *value.not_comparable)
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(value)
