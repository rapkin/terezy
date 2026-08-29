""":func:`statements` folds a ledger's charges into annual statements, one per
``(tax year x declared income category)``.

It nets where the declared treatment nets, carries losses where the declared rule carries
them, and refuses -- by name -- wherever a declared input is missing. Everything it reads is
already in the ledger: a charge accrues beside its event and moves no money, which is what
makes tax-deducted-at-trade-time (defect B5) unreachable rather than discouraged
(``ledger.events.EventKind.TAX_CHARGE``, research.md D1).

**Two traps the arithmetic here is shaped around.**

*The levy's base is the netted base.* PIT and the military levy are separate lines computed
from the **same** carryforward-reduced figure. Assessing the levy on gross while the PIT uses
the netted figure gives a levy whose base exceeds the PIT's, which no reader catches from a
total (FR-017; the citations are in ``data/tax/timing/``).

*No figure is a liability without the method that produced it.* The sources point two ways on
which basis method governs a self-declarant and give **different numbers**, so "the tax you
would owe" is not expressible here -- see :class:`AssessedLiability` (FR-024).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from enum import Enum
from typing import Final

from terezy.core.errors import LedgerInvariantError
from terezy.core.ledger import lots
from terezy.core.ledger.engine import LedgerState
from terezy.core.ledger.lots import LotMethod
from terezy.core.primitives import conventions, money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.tax.interface import TaxCharge, TaxClass
from terezy.core.tax.official_rate import (
    OfficialRateSeries,
    OfficialRateSeriesUnavailable,
    OfficialRateUnavailable,
    TaxCurrencyConversion,
    strike_base,
)
from terezy.core.tax.schedule import RateEntry, RateUndeclaredBefore, rate_on

_NO_CASH_EFFECT: Final = -0.0
"""The factor that turns a charge into a memo: it settles nothing, so it moves nothing.

**Why a negative zero rather than a positive one.** Signed zero carries no information about
an amount -- ``0.0 == -0.0`` -- and the sign convention in this ledger is that an outflow is
negative. A charge is recorded on the outflow side of the account (it is a debt being
recognised, never a receipt), and multiplying by ``-0.0`` keeps the recorded amount on that
side while making its magnitude nothing.

**The sign is a cosmetic pin, not a regression guard.** A signed zero carries no information
about an amount, and ``canonical.of_number`` normalises it away before hashing -- so the only
place it can be seen at all is a ``repr`` in 001's golden rendering, whose own header says as
much. Flipping it would move that artefact while proving nothing had changed, which is a
reason to leave it alone and not a claim that anything rests on it.
"""


def memo_amount(total: Money) -> Money:
    """The cash effect of recording one tax charge in the ledger: none, in its own currency.

    The charge's own provenance rides along -- ``money.scale`` preserves it -- so the event
    still cites the rate entry, and the exemption, that produced the figure. An amount of
    zero built with :func:`terezy.core.primitives.money.zero` would rest on no source at all
    and would quietly drop that citation, which is the one thing a zero charge exists to
    carry (``tax.interface``: *zero is a charge, not an absence*).
    """
    return money.scale(total, _NO_CASH_EFFECT)


# ---------------------------------------------------------------------------
# The declared law: categories, timing, and what each basis method stands on
# ---------------------------------------------------------------------------


class Treatment(Enum):
    """How a category's year is assembled. Declared per category, with its citation, in data.

    Three different claims about the same money, not three levels of one.
    """

    NETS = "nets"
    """Gains and losses net to one annual result before any rate applies, and a negative
    result carries forward."""

    PER_EVENT = "per_event"
    """Nothing nets: the year's liability is the sum of the charges already computed."""

    OUTSIDE = "outside"
    """Outside the netting on **both** sides, income and costs alike. The consequence that
    must be modelled is the unwelcome half: an exempt loss buys no shield (SC-005)."""


class Carryforward(Enum):
    """What a category does with a negative annual result. Declared, never inferred."""

    UNLIMITED = "unlimited"
    """Carries into the following years until fully absorbed, with no time limit."""

    NONE = "none"
    """A negative result carries nowhere -- there is no annual result for it to be part of."""


class SettlementBehaviour(Enum):
    """Who pays, and when. FR-003: a declared property of the class, entered as data."""

    SELF_ASSESSED = "self_assessed"
    """The individual declares and pays, on the declared deadlines."""

    WITHHELD_AT_SOURCE = "withheld_at_source"
    """An agent withholds at payment, so nothing is owed on a later date. **Declarable and
    not implemented** (FR-003): settling one is a refusal rather than a self-assessed payment
    invented on its behalf."""


class MethodVerdict(Enum):
    """What backs a basis method. A property of the *law*, declared with its citation in data.

    All four methods compute; what differs is what stands behind them, and a figure that does
    not say which is one a reader cannot weigh.
    """

    SELF_DECLARANT_GUIDANCE = "self_declarant_guidance"
    """Guidance addressed to a self-declaring individual recognises this method."""

    TAX_AGENT_METHODOLOGY = "tax_agent_methodology"
    """A methodology binding a **tax agent** prescribes it, and says nothing about a
    self-declarant."""

    NO_SOURCE = "no_source"
    """Nothing found backs it for either case. Computable as a what-if, never the liability."""


SOURCE_BACKED: Final[frozenset[MethodVerdict]] = frozenset(
    {MethodVerdict.SELF_DECLARANT_GUIDANCE, MethodVerdict.TAX_AGENT_METHODOLOGY}
)
"""The verdicts a source stands behind, and the reason the gap has to stay visible.

The two give **different numbers** on the same trades, and which governs a self-declarant is
unanswered -- so a figure produced under either also carries the self-declarant switch. The
arithmetic is certain; the choice of arithmetic is not (FR-024).
"""


@dataclass(frozen=True, slots=True)
class MethodStanding:
    """One basis method and what the law is found to say about it. Declared, cited data."""

    method: LotMethod
    """Which method this is a statement about."""

    verdict: MethodVerdict
    """What backs it, if anything."""

    what_the_law_says: str
    """The finding in words, for the output a human reads."""

    provenance: Provenance
    """The citation behind the finding. Required for ``NO_SOURCE`` exactly as for the
    others: "no source prescribes this" is itself a claim about the law, and an uncited one
    is indistinguishable from nobody having looked."""


@dataclass(frozen=True, slots=True)
class AnnualDate:
    """A recurring calendar deadline: a month and a day, with no year of its own.

    A deadline is not a date: 1 August is the rule, and *which* 1 August depends on the year
    being settled. Storing a full date would need a year invented at load time.
    """

    month: int
    """1--12, checked at the data boundary where the file can be named."""

    day: int
    """1--28, capped at the shortest month so that no deadline can fail to exist in a year."""


@dataclass(frozen=True, slots=True)
class TimingRule:
    """When a category's year is declared and paid, and by whom. Declared, cited data.

    **Per category rather than per class**, which still satisfies FR-003's "a property of the
    tax class": a class names its category and the category names its timing, so a
    withheld-at-source class stays a data-only addition. Deadlines declared per class would
    let two classes in one category declare two deadlines for the *same* annual statement.
    """

    category_id: str
    """The category these deadlines govern."""

    settlement: SettlementBehaviour
    """Self-assessed, or withheld by an agent."""

    declare_by: AnnualDate
    """The declaration deadline in the year **after** the tax year. Carried although no filing
    event is modelled: FR-005 makes it a declared legal value, so its absence is a refusal
    rather than a blank."""

    pay_by: AnnualDate
    """The payment deadline in the year after the tax year. This is the date cash moves."""

    non_business_day_rule: str
    """The declared convention applied when a deadline falls on a non-business day (FR-008).
    Resolved through ``primitives.conventions``; an unrecognised name fails at load, naming
    the file and the value."""

    note: str
    """What the citation attests, in words."""

    provenance: Provenance
    """Where the deadlines came from. An empty ``verified_on`` marks every figure below."""


@dataclass(frozen=True, slots=True)
class IncomeCategory:
    """One declared income category: how its year nets, and what a loss in it does."""

    id: str
    treatment: Treatment
    carryforward: Carryforward
    note: str
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class AssessmentRules:
    """Everything declared about how a jurisdiction assembles a tax year.

    One record rather than four arguments, so a caller cannot supply the categories and
    forget the timing -- a half-supplied rule set would produce statements that look complete
    and are missing the half that says when the money leaves.
    """

    jurisdiction_id: str
    tax_currency: Currency
    """The currency a liability is assessed in. Stated rather than assumed."""

    official_rate: OfficialRateSeries | None
    """The declared series that strikes a base in :attr:`tax_currency`, or ``None``.

    ``None`` is a declared absence and not a permissive one: a taxable result in another
    currency then comes back :class:`TaxCurrencyConversionUnavailable` saying the jurisdiction
    declared none -- there is no series for it to name -- and no other series is picked for it
    by load order (FR-007).
    A realised *gain* in another currency does not reach that check at all -- it comes back
    :class:`ForeignGainNotStruckPerDate`, whose own reason says why.

    One series, so income in two foreign currencies is not expressible today. That is inside
    FR-005 -- a second series is declarable and addressable, and no run consumes one -- and is
    noted here because this field is where a second one would have to arrive.

    Never a channel. A channel is a market you transact in and decides an amount received; an
    official rate is a legal reference nobody transacts at and decides a tax base. The two may
    not stand in for each other in either direction, which ``.importlinter`` enforces as two
    separate contracts because they are two separate requirements (FR-012, FR-013).
    """

    categories: Mapping[str, IncomeCategory]
    category_of_class: Mapping[str, str]
    """Tax class id -> category id. A reference, resolved at load against both files."""

    timing: Mapping[str, TimingRule]
    """Category id -> its declared deadlines and settlement behaviour."""

    methods: Mapping[LotMethod, MethodStanding]
    """What the law is found to say about each basis method."""


# ---------------------------------------------------------------------------
# The owner's own inputs: what he filed, and where he stands on the open questions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FilingDecisions:
    """Whether the owner filed, per year. **An input, never a prediction** (FR-014, D4).

    There is no default and no inference from behaviour. A year with investment operations
    and no decision is a refusal, because *"the tool assumed you filed"* and *"the tool
    assumed you did not"* are different wrong answers and each silently changes the after-tax
    ranking.
    """

    owner_id: str
    declared_at: str
    """Where this was declared, so a figure resting on it names a line in a file."""

    by_year: Mapping[int, bool]
    """Tax year -> was that year's declaration filed. Absence is a refusal, not a ``False``."""


class ChainPosition(Enum):
    """The two readings of a carryforward that meets a year whose declaration was missed.

    **UNSETTLED**, and neither branch is a default: they give different tax, every figure
    produced under either is labelled, and the declared position carries its own reasoning
    (FR-015, ``data/scenarios/tax/``).
    """

    BROKEN_FORFEITS = "chain_broken_forfeits"
    """A missed declaration ends the carry: the balance is forfeited at that year."""

    RESTORABLE = "chain_restorable"
    """The loss survives the gap and is available again in the next filed year."""


@dataclass(frozen=True, slots=True)
class UnsettledSwitch:
    """A legal question no source settles, the position taken, and how it will be retired.

    Declared rather than coded: an unsettled reading is a **belief**, and it needs a label and
    a visible consequence rather than a source. In code it would look like a rule
    (research.md D6).
    """

    question: str
    """The legal question, in words a reader can take to an adviser."""

    position: str
    """The branch this run takes, as declared."""

    resolution_path: str
    """What would retire the label -- an IPK under art. 52 PKU, and nothing less."""

    declared_at: str
    """The file and entry this was declared in."""


@dataclass(frozen=True, slots=True)
class ChainContinuity:
    """The declared position on carryforward chain continuity, with its label."""

    position: ChainPosition
    switch: UnsettledSwitch


@dataclass(frozen=True, slots=True)
class SelfDeclarantMethod:
    """The declared position on which source-backed method a self-declarant uses, labelled."""

    method: LotMethod
    switch: UnsettledSwitch


@dataclass(frozen=True, slots=True)
class UnsettledPositions:
    """The owner's declared positions on the questions the law does not answer.

    ``None`` on either field means *not declared*, which is a refusal at the point the answer
    is needed -- never a silently chosen branch.
    """

    chain: ChainContinuity | None
    method: SelfDeclarantMethod | None


# ---------------------------------------------------------------------------
# What an assessment produces
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChargeRef:
    """One per-event charge inside an annual statement, with what it contributes.

    FR-002: the statement enumerates the charges composing it, each traceable to its event
    and its rule, so the year's liability can be checked without re-deriving it.
    """

    charge: TaxCharge
    """The per-event assessment as ``tax.flat_rate`` computed it: both lines, its base, its
    class and its provenance."""

    occurred_on: date
    """The date of the event it was charged on -- the fact that decides both the tax year and
    which dated rate entry was in force."""

    from_disposal: bool
    """Whether :attr:`result` came from a disposal the fold realised.

    It decides one thing: only a disposal's result depends on which lots were consumed, so
    only a statement containing one rests on the basis method's unsettled reading. A year of
    coupons is the same number under all four methods, and a label on it would be a label on
    nothing (SC-012).
    """

    result: Money
    """What this item contributes to the year's netting: **signed**, so a loss is negative.

    Deliberately not ``charge.taxable_base``. For a disposal this is the realised gain the
    fold computed, because a per-event rule is entitled to charge a *different* base -- one
    that charges nothing on a loss is right for a line saying what was charged and wrong for a
    year that has to net. The year clamps once, where the statute clamps it, not once per
    event.
    """

    conversion: TaxCurrencyConversion | None
    """How this item reached the tax currency, or ``None`` when it was already in it.

    ``None`` is the answer for every item in a hryvnia run, and it says *no rate was
    consulted* rather than *a rate was unavailable*: an event already denominated in the tax
    currency must not consult one at all (FR-009), and a rate-unavailable reason attached to a
    figure that never needed a rate is a false refusal.

    When it is present it names the series, the observation date whose rate was applied, the
    rate and the quotation unit, so a reader can re-derive the base on paper without opening a
    data file (FR-016) -- and a rate applied from a date other than the event's own is visible
    rather than implied.
    """


@dataclass(frozen=True, slots=True)
class AssessedLiability:
    """What a year owes, and what produced it. **Never a bare total** (FR-024).

    There is no field named ``total`` alone and no way to build this record without naming the
    basis method and its standing. The law supports at least two readings of which method
    governs a self-declarant and they give different numbers, so a single unlabelled figure
    would be more confident than its inputs -- where the input is an unanswered legal question.
    """

    pit: Money
    """The personal income tax line."""

    levy: Money
    """The military levy line, assessed on the **same netted base** as the PIT (FR-017)."""

    base: Money
    """What both rates were applied to: the netted, carryforward-reduced figure."""

    method: LotMethod
    """Which basis method produced the disposals behind the base.

    Not a stamp: :func:`statements` takes no method and reads
    ``LedgerState.consumption_method``, so this is the method the fold actually consumed by
    and there is no argument it could disagree with.
    """

    standing: MethodStanding
    """What the law is found to say about that method, so the citation travels with the
    figure."""

    rests_on: Provenance
    """The rate entries, the category, the timing rule, the method standing and the bases.
    An unverified value among them marks this figure and everything derived from it."""


def liability_total(liability: AssessedLiability) -> Money:
    """PIT plus levy, computed on demand rather than stored.

    A stored total would be a field a caller could read *without* the method beside it, which
    is the one thing :class:`AssessedLiability` exists to prevent. As a function it can only
    be reached through the record that names the method, and it can never drift from the two
    lines it adds.
    """
    return money.add(liability.pit, liability.levy)


class ZeroReason(Enum):
    """Why a year owes nothing. Three different claims, and E11 at the annual level."""

    EXEMPT = "exempt"
    """The rules that applied charged zero -- an exemption, cited by the charges themselves."""

    NETTED_TO_ZERO = "netted_to_zero"
    """There were taxable operations and they netted to nothing positive, so the base is zero
    and any excess became (or stayed) a carryforward."""

    NO_TAXABLE_EVENTS = "no_taxable_events"
    """Nothing happened in this category this year. Distinct from both zeros above: no rule
    ran, so there is nothing to cite."""


@dataclass(frozen=True, slots=True)
class CarryforwardState:
    """What a year did with losses: brought in, used, created, forfeited, left open."""

    filed: bool | None
    """Whether this year's declaration was filed. Declared per year, no default (FR-014).

    ``None`` **only** for a year with no investment operations, where no declaration was due
    and none was declared. It is not a third position on filing: it is the absence of the
    question, and reporting the previous year's answer here instead would be a claim nobody
    made.
    """

    brought_in: Money
    """The balance standing at the start of the year, before this year's filing status is
    taken into account."""

    applied: Money
    """How much of it actually reduced this year's positive result. Zero in an unfiled year:
    the deduction is claimed in a declaration, and there is none."""

    created: Money
    """A new loss added by this year -- only in a filed year (FR-014, FR-016)."""

    forfeited: Money
    """What was lost this year and will never reduce anything: an unfiled year's own loss, or
    a balance the chain-broken reading discards."""

    open_balance: Money
    """What remains after the year. Reported at the horizon with its origins (FR-019)."""

    origins: tuple[tuple[int, Money], ...]
    """``(origin year, amount still open)`` for each loss year still contributing, so a later
    expiry or partial absorption stays attributable."""

    base_above_all_filed: Money
    """How much larger this year's base is than it would have been had every declaration been
    filed. **Signed**, and genuinely negative sometimes.

    A missed declaration does not always destroy relief: under the chain-restorable reading it
    can merely postpone it, so the year that finally claims the whole carried loss has a
    *smaller* base than the all-filed counterfactual, which had already spent part of it.
    Clamping that at zero would hide it. What a reader wants over a whole run is
    :attr:`cost_of_not_filing_to_date`, which nets those years against each other.
    """

    cost_of_not_filing_to_date: Money
    """The **cumulative** extra tax every missed declaration has caused up to and including
    this year, PIT and levy together, against the all-filed counterfactual.

    This is SC-010's one figure: a reader quotes the last year's value as the cost of not
    filing, without re-running the other branch and subtracting. Cumulative rather than
    per-year because a single year cannot answer the question -- under the chain-restorable
    reading, an unfiled year pays tax early and the year that absorbs the loss pays less, and
    only the running total says whether anything was actually lost.
    """


@dataclass(frozen=True, slots=True)
class AnnualStatement:
    """One owner, one tax year, one income category: what was assessed and what it rests on.

    The bridge between per-event charges (001) and a dated payment: charges accrue to a year,
    the year nets them per its declared treatment, and the liability is settled from cash on
    :attr:`due_on` by ``core.results.tax_year.settle``.
    """

    tax_year: int
    category: str
    treatment: Treatment
    """How this category's year was assembled -- carried so a reader can see *why* a loss did
    or did not reduce anything, rather than inferring it from the arithmetic."""

    charges: tuple[ChargeRef, ...]
    """Every charge composing the year, in ledger order (FR-002). Empty for a year in which
    nothing happened, which is a statement and not an absence (FR-006)."""

    netted_base: Money
    """The year's own result before any carried loss: gains less losses within the year for a
    netting category, and the sum of the items' own bases otherwise."""

    carryforward: CarryforwardState | None
    """The year's loss accounting, or ``None`` for a category that does not carry losses.

    ``None`` says *this category has no carryforward machinery* -- ISI distributions and
    exempt operations do not net, so there is no annual result for a loss to be part of. A
    zero balance would say something different and weaker: that a mechanism ran and found
    nothing.
    """

    liability: AssessedLiability
    zero_because: ZeroReason | None
    """Why the liability is zero, or ``None`` when it is not. FR-006 wants exemption, netting
    and "nothing happened" told apart, and a reader of a bare ``0.00`` cannot tell them."""

    settlement: SettlementBehaviour
    due_on: date | None
    """The date the liability is payable, from the declared rule and its non-business-day
    convention. ``None`` only for a withheld-at-source class, where there is no later date
    because there is no later payment.

    **A bare date, and there is nothing to hang a mark on.** There is no dated-value wrapper
    here the way :class:`~terezy.core.primitives.money.Money` is an amount carrying its own
    sources, so the timing rule's ``verified_on`` cannot ride on this field. It rides on the
    money instead: the rule's provenance is unioned into every amount the **year** computes --
    the liability, the netted base, the carryforward, and the payment that settles them -- so
    an unverified deadline is visible rather than silent
    (``tests/contract/test_provenance_propagation.py``).

    Not into :attr:`charges`, deliberately. Those amounts were computed per event by
    ``tax.flat_rate`` before any year existed, and a coupon's charge does not rest on the
    deadline the year is eventually paid on. Marking them would say it did.
    """

    unsettled: tuple[UnsettledSwitch, ...]
    """Every declared switch this statement's figures actually rest on (SC-012).

    *Actually* rest on: a statement is labelled with the chain switch when a broken chain
    changed its arithmetic, not merely because the switch exists somewhere. A label on
    everything is a label on nothing.
    """


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CategoryUndeclared:
    """A charge's tax class names no declared income category, so its year cannot be built."""

    tax_class_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class TimingRuleUndeclared:
    """A category with taxable events declares no deadlines (FR-005).

    Refused rather than defaulted at the point of assessment, not at the point of payment: a
    statement that cannot say when it is due is not a statement, and a run that produced one
    would carry the gap all the way to a cash plan that never checked a date.
    """

    category_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class FilingStatusUndeclared:
    """A year with investment operations, and no declared filing decision (FR-014)."""

    tax_year: int
    reason: str


@dataclass(frozen=True, slots=True)
class UnsettledPositionUndeclared:
    """An unsettled legal question was reached and no position is declared (FR-015, FR-024)."""

    question: str
    reason: str


@dataclass(frozen=True, slots=True)
class MethodStandingUndeclared:
    """No declared finding about what the law says for this basis method (FR-024)."""

    method: LotMethod
    reason: str


@dataclass(frozen=True, slots=True)
class RateChangedWithinTaxYear:
    """A netting year's items fall under two different dated rate entries.

    Refused rather than resolved: a netting category charges one annual result, and nothing in
    the sources says how an annual base is split across a mid-year change. The reason carried
    on the record says what the evidence for that is.
    """

    tax_year: int
    category_id: str
    effective_dates: tuple[date, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class CategoryTaxedByTwoClasses:
    """One netting category, one year, two tax classes with two rate schedules.

    Reported separately from :class:`RateChangedWithinTaxYear` because the fix differs: this
    is a declaration that puts two treatments in one bucket, and that is corrected in the
    category mapping rather than in a rate schedule.
    """

    tax_year: int
    category_id: str
    tax_class_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class TaxCurrencyConversionUnavailable:
    """A taxable amount is not in the tax currency, and no declared official rate strikes it.

    Two ways to get here, told apart by :attr:`unavailable`: the jurisdiction names no
    official-rate series at all, or the series it names declares nothing for this date and no
    rule covering it. Both are declarations that are missing, and both are fixed in ``data/``.

    **It is never satisfied with a channel rate.** A channel is a market you transact in and
    an official rate is a legal reference you never transact at; substituting one for the
    other would strike a real liability at a price nobody was charged. That is the same rule
    ``core.routes.legs.channel_for`` enforces in the other direction, and ``.importlinter``
    keeps both directions structural rather than remembered.

    Unreachable with the shipped registry, where every taxable event is in hryvnia -- which is
    a property of today's data rather than of the arithmetic, and is why the guard exists.
    """

    event_sequence: int
    found: Currency
    tax_currency: Currency

    unavailable: OfficialRateUnavailable
    """Which half is missing -- the series, or the date -- naming the series, the pair and the
    date. Carried rather than flattened into the reason, so a caller can act on it without
    parsing prose."""

    reason: str


@dataclass(frozen=True, slots=True)
class ForeignGainNotStruckPerDate:
    """A realised gain in a foreign currency. Refused, and deliberately never converted.

    A gain is not an amount on a date. It is the difference between proceeds received on one
    date and a basis struck on another, and each of those has its own official rate.

    Converting the difference at the disposal date's rate is not an approximation, it is the
    arithmetic that deletes the thing being looked for: a position flat in dollars across a
    devaluation realises **zero dollars**, and zero at any rate is zero hryvnia. Required test
    F1 -- *"a position flat in USD across a devaluation produces a positive taxable gain in
    UAH"* -- would then be unfalsifiable, and it is the test the rewrite exists for.

    What is missing is a per-lot basis carried in both currencies, each leg struck at its own
    date's official rate. That is ``fx-tax-asymmetry-f1`` in ``specs/features.toml``; feature
    011 supplies the dated rates it needs and does not build it.
    """

    event_sequence: int
    found: Currency
    tax_currency: Currency
    reason: str


TaxYearRefused = (
    CategoryUndeclared
    | TimingRuleUndeclared
    | FilingStatusUndeclared
    | UnsettledPositionUndeclared
    | MethodStandingUndeclared
    | RateChangedWithinTaxYear
    | CategoryTaxedByTwoClasses
    | TaxCurrencyConversionUnavailable
    | ForeignGainNotStruckPerDate
    | RateUndeclaredBefore
)
"""Why a year could not be assessed. Match exhaustively; every member names its own fix.

``RateUndeclaredBefore`` is 006's and is reused rather than re-declared: a netting year whose
rate entry does not reach back to it is the same fact about the same schedule, and a private
copy would be a second type a caller has to learn for one claim.
"""


# ---------------------------------------------------------------------------
# The assessment
# ---------------------------------------------------------------------------


def statements(
    state: LedgerState,
    charges: Sequence[TaxCharge],
    *,
    rules: AssessmentRules,
    tax_classes: Mapping[str, TaxClass],
    filing: FilingDecisions,
    switches: UnsettledPositions,
) -> tuple[AnnualStatement, ...] | TaxYearRefused:
    """Fold a ledger's charges into one statement per ``(tax year x income category)``.

    Pure, and there is no clock anywhere in it: every year comes from an event's own date and
    every deadline from a declared rule. The same ledger yields the same statements for ever,
    which is what makes a tax figure checkable a year from now.

    **Nothing here can deduct tax at event time**, because nothing here touches the ledger:
    the charges arrive already recorded beside their events, and this function only reads
    them. That is defect B5 cured by shape rather than by care (research.md D1).

    **Every keyword is required and none has a default.** The filing decisions and the
    unsettled positions are each a choice that changes the number, and a default for either
    would be this tool taking a position on the owner's behalf.

    Years run from the first to the last event in the ledger, so a year in which a category
    saw nothing still produces a statement saying so -- FR-006's third distinguishable zero,
    and the difference between "nothing was owed" and "nobody looked".

    **The basis method is read off the ledger and is not an argument.** It is the method
    ``state`` was folded under that decided which lots every disposal drew on, so it is the
    only method these figures could honestly be labelled with -- and a second argument saying
    the same thing is a second place for it to be said differently. There is still no default:
    ``engine.opening`` required the name, and it is still required, one layer up (FR-024).
    """
    basis = _basis_for(state, rules=rules, switches=switches)
    if not isinstance(basis, tuple):
        return basis
    method, standing, method_switch = basis

    grouped = _items(state, charges, rules)
    if not isinstance(grouped, Mapping):
        return grouped

    built: list[AnnualStatement] = []
    for category_id in sorted(grouped):
        rule = rules.timing.get(category_id)
        if rule is None:
            return TimingRuleUndeclared(
                category_id=category_id,
                reason=(
                    f"income category {category_id!r} has taxable events in this run and no "
                    "declared timing rule, so there is no declared date on which its "
                    "liability is due. Refused rather than assumed: a due date is a legal "
                    "value like a rate (FR-005), and paying at trade time -- the "
                    "predecessor's defect B5 -- is exactly what this feature exists to stop. "
                    f"Declare a [[timing.category]] entry for {category_id!r}."
                ),
            )
        assessed = _category_statements(
            grouped[category_id],
            category=rules.categories[category_id],
            rule=rule,
            years=_years_of(state),
            tax_classes=tax_classes,
            filing=filing,
            method=method,
            standing=standing,
            method_switch=method_switch,
            switches=switches,
        )
        if not isinstance(assessed, tuple):
            return assessed
        built.extend(assessed)
    return tuple(sorted(built, key=lambda statement: (statement.tax_year, statement.category)))


def _basis_for(
    state: LedgerState,
    *,
    rules: AssessmentRules,
    switches: UnsettledPositions,
) -> tuple[LotMethod, MethodStanding, UnsettledSwitch | None] | TaxYearRefused:
    """The basis method this ledger was folded under, and everything a year needs about it.

    ``lots.method_named`` rather than a second argument: the name in the state has already
    passed ``engine.opening``'s check, so it is a method here by construction and an unknown
    one would be a state this engine could not have produced.
    """
    method = lots.method_named(state.consumption_method)
    standing = rules.methods.get(method)
    if standing is None:
        return MethodStandingUndeclared(
            method=method,
            reason=(
                f"no declared finding about what the law says for the {method.value!r} basis "
                "method, so a figure produced under it could not state what backs it. A tax "
                "figure that does not name its basis convention hides the one input the "
                "sources disagree about (FR-024). Declare a [[timing.lot_method]] entry for "
                f"{method.value!r} with its citation."
            ),
        )
    switch = _method_switch(standing, switches)
    if isinstance(switch, UnsettledPositionUndeclared):
        return switch
    return method, standing, switch


def _method_switch(
    standing: MethodStanding, switches: UnsettledPositions
) -> UnsettledSwitch | UnsettledPositionUndeclared | None:
    """The self-declarant switch a figure under this method rests on, if it rests on one.

    A method **no source backs** rests on no switch: it is a what-if against a question the
    sources do not even take a side on, and :class:`MethodStanding` already says so on every
    figure. A method one of the two sources backs is different -- the two give different
    numbers for a self-declarant and nothing says which governs -- so the position must be
    declared, and the figure carries the label (FR-024, SC-012).
    """
    if standing.verdict not in SOURCE_BACKED:
        return None
    if switches.method is None:
        return UnsettledPositionUndeclared(
            question=(
                "which source-backed basis method governs a self-declaring individual: the "
                "proportional/average-cost reading ДПС guidance recognises, or the FIFO "
                "Методика МФУ № 1484 prescribes where a tax agent computes"
            ),
            reason=(
                f"this run assesses under {standing.method.value!r}, which one of the two "
                "sources backs -- and the two give different numbers for a self-declarant. "
                "Which governs is unanswered, so the position must be declared and labelled "
                "rather than picked here. Declare it under data/scenarios/tax/, and record "
                "an individual tax consultation (art. 52 PKU) as the resolution path."
            ),
        )
    return switches.method.switch


def _years_of(state: LedgerState) -> tuple[int, ...]:
    """Every calendar year the ledger spans, ascending, gaps included.

    From the ledger rather than from the charges, because a year in which a category saw no
    taxable event is exactly the year FR-006's third zero is about -- and it is invisible to
    anything that looks only at the charges.
    """
    if not state.applied:
        return ()
    first = min(event.occurred_on.year for event in state.applied)
    last = max(event.occurred_on.year for event in state.applied)
    return tuple(range(first, last + 1))


def _items(
    state: LedgerState,
    charges: Sequence[TaxCharge],
    rules: AssessmentRules,
) -> (
    Mapping[str, tuple[ChargeRef, ...]]
    | CategoryUndeclared
    | TaxCurrencyConversionUnavailable
    | ForeignGainNotStruckPerDate
):
    """The charges as category-keyed items, each carrying the signed result it contributes."""
    by_sequence = {event.sequence: event for event in state.applied}
    gains = {disposal.sequence: disposal.realised_gain_base_ccy for disposal in state.disposals}
    grouped: dict[str, list[ChargeRef]] = {}
    for charge in charges:
        event = by_sequence.get(charge.event_sequence)
        if event is None:
            raise LedgerInvariantError(
                f"charge on event {charge.event_sequence} has no such event in the ledger it "
                "is being assessed against, so the year it accrues to cannot be checked "
                "against the date it arose on. A charge and its event are produced together; "
                "one without the other means two different runs were mixed."
            )
        category_id = rules.category_of_class.get(charge.tax_class_id)
        if category_id is None:
            return CategoryUndeclared(
                tax_class_id=charge.tax_class_id,
                reason=(
                    f"tax class {charge.tax_class_id!r} charged event {event.sequence} and "
                    "names no declared income category, so the year cannot know whether its "
                    "result nets with the others, stands on its own, or falls outside the "
                    "calculation entirely -- three different answers (FR-013). Declare a "
                    f"[[timing.class]] entry mapping {charge.tax_class_id!r} to a category."
                ),
            )
        realised = gains.get(event.sequence)
        result = charge.taxable_base if realised is None else realised
        item = _in_tax_currency(
            charge,
            result,
            sequence=event.sequence,
            occurred_on=event.occurred_on,
            from_disposal=realised is not None,
            rules=rules,
        )
        if not isinstance(item, tuple):
            return item
        struck_charge, struck_result, conversion = item
        grouped.setdefault(category_id, []).append(
            ChargeRef(
                charge=struck_charge,
                occurred_on=event.occurred_on,
                from_disposal=realised is not None,
                result=struck_result,
                conversion=conversion,
            )
        )
    return {category_id: tuple(items) for category_id, items in grouped.items()}


def _in_tax_currency(
    charge: TaxCharge,
    result: Money,
    *,
    sequence: int,
    occurred_on: date,
    from_disposal: bool,
    rules: AssessmentRules,
) -> (
    tuple[TaxCharge, Money, TaxCurrencyConversion | None]
    | TaxCurrencyConversionUnavailable
    | ForeignGainNotStruckPerDate
):
    """One item restated in the tax currency, or the typed reason it cannot be.

    **The whole charge is restated, not only the netting result.** A per-event category sums
    ``charge.pit`` and ``charge.levy`` against the result's own currency, so converting one
    and leaving the other would be a currency mismatch on the first such category. Each line
    is struck at the same rate on the same date.

    **Restating after the fact is equivalent to charging on a converted base only because the
    rule is linear in its base**, and that assumption belongs to the ``TaxRule`` interface
    rather than to this function -- ``core.tax.interface`` states it, and states what a rule
    with a bracket, a cap or an allowance must do instead. This site cannot enforce it: by the
    time a charge reaches here it has already been computed.

    ``total`` is **recomputed** from the two struck lines rather than converted with them, so
    the record's own identity ``total == pit + levy`` stays exact rather than holding to a
    tolerance.

    A **realised gain** never reaches the conversion. See
    :class:`ForeignGainNotStruckPerDate` for why converting one is the defect rather than the
    feature.
    """
    if result.currency is rules.tax_currency:
        return charge, result, None
    if from_disposal:
        return ForeignGainNotStruckPerDate(
            event_sequence=sequence,
            found=result.currency,
            tax_currency=rules.tax_currency,
            reason=(
                f"event {sequence} realises a gain in {result.currency.value} and tax is "
                f"assessed in {rules.tax_currency.value}. The gain is refused rather than "
                "converted: it is the difference between proceeds on one date and a basis "
                "struck on another, and striking it at the disposal date's rate would report "
                "zero hryvnia for a position that stood still in dollars across a devaluation "
                "-- deleting the taxable gain required test F1 exists to find. What it needs "
                "is a per-lot basis carried in both currencies, each leg at its own date's "
                "official rate: specs/features.toml, fx-tax-asymmetry-f1."
            ),
        )
    if rules.official_rate is None:
        struck: TaxCurrencyConversion | OfficialRateUnavailable = OfficialRateSeriesUnavailable(
            wanted=(rules.tax_currency, result.currency),
            series_id=None,
            quotes=None,
            reason=(
                f"jurisdiction {rules.jurisdiction_id!r} names no official-rate series for its "
                "tax currency. No series is chosen for it by load order, and no channel rate "
                "stands in: a channel is a market you transact in and the official rate is a "
                "legal reference you never transact at. Declare official_rate_series in the "
                "jurisdiction's assessment rules."
            ),
        )
    else:
        struck = strike_base(
            result, rules.official_rate, tax_currency=rules.tax_currency, on_date=occurred_on
        )
    if not isinstance(struck, TaxCurrencyConversion):
        return TaxCurrencyConversionUnavailable(
            event_sequence=sequence,
            found=result.currency,
            tax_currency=rules.tax_currency,
            unavailable=struck,
            reason=(
                f"event {sequence} on {occurred_on.isoformat()} produces a taxable result in "
                f"{result.currency.value} and no official rate strikes it in "
                f"{rules.tax_currency.value}: {struck.reason}"
            ),
        )

    # The two lines are restated at **the same rate the base was struck at**, read off the
    # conversion rather than looked up again: a second lookup could in principle disagree with
    # the first, and there would be no honest value to fall back on if it did. The rate's own
    # sources ride on ``struck.base``, so the union carries them onto every line.
    def _line(amount: Money) -> Money:
        return money.convert(
            amount,
            to_currency=rules.tax_currency,
            rate=struck.rate / struck.quotation_unit,
            sources=struck.base.provenance,
        )

    pit = _line(charge.pit)
    levy = _line(charge.levy)
    return (
        TaxCharge(
            event_sequence=charge.event_sequence,
            pit=pit,
            levy=levy,
            total=money.add(pit, levy),
            taxable_base=struck.base,
            tax_class_id=charge.tax_class_id,
            charged_for_year=charge.charged_for_year,
            provenance=prov.merge(charge.provenance, struck.base.provenance),
        ),
        struck.base,
        struck,
    )


@dataclass(frozen=True, slots=True)
class _Carried:
    """The running carryforward between the years of one category.

    ``shadow`` is the counterfactual balance under *every declaration filed*. Carrying it
    alongside the real balance is what makes
    :attr:`CarryforwardState.cost_of_not_filing_to_date` readable from one run instead of by
    running the other branch and subtracting -- which is SC-010's requirement in as many words.
    """

    balance: Money
    origins: tuple[tuple[int, Money], ...]
    shadow: Money
    cost_to_date: Money
    """The cumulative extra tax the missed declarations have caused so far. Running, because a
    single year cannot answer the question a reader asks at the end of a run."""

    last_operations_year_filed: bool
    """Whether the most recent year that *had* investment operations was declared.

    Opens ``True`` because there is no earlier year to have missed a declaration for: the
    chain is unbroken until something breaks it, and opening it ``False`` would consult the
    unsettled chain switch on a run's very first year. A year with no operations leaves it
    alone -- the filing duty is a duty for years with operations (пп. 170.2.1 ПКУ), so a
    quiet year breaks nothing.
    """


def _category_statements(
    items: Sequence[ChargeRef],
    *,
    category: IncomeCategory,
    rule: TimingRule,
    years: Sequence[int],
    tax_classes: Mapping[str, TaxClass],
    filing: FilingDecisions,
    method: LotMethod,
    standing: MethodStanding,
    method_switch: UnsettledSwitch | None,
    switches: UnsettledPositions,
) -> tuple[AnnualStatement, ...] | TaxYearRefused:
    """Every year of one category, ascending, carrying the balance from each into the next.

    Ascending is not a convenience. A carryforward is a fact the previous year produced, so
    the years cannot be assessed independently and cannot be reordered.
    """
    currency = items[0].result.currency
    by_year: dict[int, list[ChargeRef]] = {year: [] for year in years}
    for item in items:
        by_year.setdefault(item.charge.charged_for_year, []).append(item)

    zero = money.zero(currency)
    carried = _Carried(
        balance=zero,
        origins=(),
        shadow=zero,
        cost_to_date=zero,
        last_operations_year_filed=True,
    )
    built: list[AnnualStatement] = []
    for year in sorted(by_year):
        assessed = _one_year(
            tuple(by_year[year]),
            year=year,
            carried=carried,
            currency=currency,
            category=category,
            rule=rule,
            tax_classes=tax_classes,
            filing=filing,
            method=method,
            standing=standing,
            method_switch=method_switch,
            switches=switches,
        )
        if not isinstance(assessed, tuple):
            return assessed
        statement, carried = assessed
        built.append(statement)
    return tuple(built)


def _one_year(
    items: tuple[ChargeRef, ...],
    *,
    year: int,
    carried: _Carried,
    currency: Currency,
    category: IncomeCategory,
    rule: TimingRule,
    tax_classes: Mapping[str, TaxClass],
    filing: FilingDecisions,
    method: LotMethod,
    standing: MethodStanding,
    method_switch: UnsettledSwitch | None,
    switches: UnsettledPositions,
) -> tuple[AnnualStatement, _Carried] | TaxYearRefused:
    """One ``(year x category)`` statement, and the carryforward it hands to the next year."""
    entries = _entries_for(items, tax_classes)
    if isinstance(entries, RateUndeclaredBefore):
        return entries  # pragma: no cover -- flat_rate refuses such an event before this
    declared = prov.merge_all(
        [
            category.provenance,
            rule.provenance,
            standing.provenance,
            *(e.provenance for e in entries),
        ]
    )
    if category.treatment is Treatment.NETS:
        return _netting_year(
            items,
            year=year,
            carried=carried,
            currency=currency,
            category=category,
            rule=rule,
            entries=entries,
            declared=declared,
            filing=filing,
            method=method,
            standing=standing,
            method_switch=method_switch,
            switches=switches,
        )
    return (
        _per_event_year(
            items,
            year=year,
            currency=currency,
            category=category,
            rule=rule,
            entries=entries,
            declared=declared,
            method=method,
            standing=standing,
            method_switch=method_switch,
        ),
        carried,
    )


def _per_event_year(
    items: tuple[ChargeRef, ...],
    *,
    year: int,
    currency: Currency,
    category: IncomeCategory,
    rule: TimingRule,
    entries: tuple[RateEntry, ...],
    declared: Provenance,
    method: LotMethod,
    standing: MethodStanding,
    method_switch: UnsettledSwitch | None,
) -> AnnualStatement:
    """A year of a category that does not net: the liability is the charges already computed.

    Nothing is re-derived, and that is the point. Where no netting happens, applying a rate to
    an annual total and applying it per event agree only while the rate does not change
    mid-year. Summing the charges is right either way, and it keeps every dated entry that was
    actually in force.

    **A category declared ``OUTSIDE`` comes through here too, and that is deliberate.** Its
    operations net with nothing, so an exempt loss reduces no other year's base (SC-005). What
    distinguishes the two treatments is not the arithmetic but the claim, and
    :attr:`AnnualStatement.treatment` carries it.
    """
    # ``declared`` is unioned into the amounts and not only into ``rests_on``: the category's
    # treatment is why these items were summed rather than netted, and the timing rule is why
    # the sum falls due when it does. A mark that reached the record's provenance field and
    # stopped there would leave the money it governs -- and the payment that settles it --
    # looking checked (FR-027).
    pit = money.also_resting_on(
        money.total([item.charge.pit for item in items], currency), declared
    )
    levy = money.also_resting_on(
        money.total([item.charge.levy for item in items], currency), declared
    )
    base = money.also_resting_on(money.total([item.result for item in items], currency), declared)
    liability = AssessedLiability(
        pit=pit,
        levy=levy,
        base=base,
        method=method,
        standing=standing,
        rests_on=prov.merge_all([declared, *(item.charge.provenance for item in items)]),
    )
    return AnnualStatement(
        tax_year=year,
        category=category.id,
        treatment=category.treatment,
        charges=items,
        netted_base=base,
        carryforward=None,
        liability=liability,
        zero_because=_zero_reason(liability, items=items, entries=entries),
        settlement=rule.settlement,
        due_on=_due_on(rule, year),
        unsettled=_labels(method_switch, None, items=items),
    )


def _netting_year(
    items: tuple[ChargeRef, ...],
    *,
    year: int,
    carried: _Carried,
    currency: Currency,
    category: IncomeCategory,
    rule: TimingRule,
    entries: tuple[RateEntry, ...],
    declared: Provenance,
    filing: FilingDecisions,
    method: LotMethod,
    standing: MethodStanding,
    method_switch: UnsettledSwitch | None,
    switches: UnsettledPositions,
) -> tuple[AnnualStatement, _Carried] | TaxYearRefused:
    """One year of a netting category: net, carry, charge the remainder, and say what it rests on.

    The order is the law's, not a convenience (пп. 170.2.6 ПКУ, абзац третій):

    1. the year's operations net to **one** result -- gains against losses, before any rate;
    2. a carried loss reduces that result, if there is a declaration to claim it in;
    3. only what remains positive is charged, and **both** lines are charged on it (FR-017);
    4. anything negative becomes, or stays, a carryforward attributed to its origin year.

    Step 3 is the only clamp in the feature, and it is the clamp the statute makes: a negative
    annual result means a zero base and no levy, with the loss preserved rather than swallowed.
    """
    zero, carried = _under(declared, currency, carried)
    if not items:
        # A year in which this category saw nothing. The balance passes through untouched and
        # no filing decision is needed: the duty attaches to years with investment operations
        # (пп. 170.2.1 ПКУ), so a quiet year neither breaks the chain nor requires an answer.
        return _quiet_year(
            year=year,
            carried=carried,
            zero=zero,
            category=category,
            rule=rule,
            declared=declared,
            method=method,
            standing=standing,
        )

    filed = filing.by_year.get(year)
    if filed is None:
        return FilingStatusUndeclared(
            tax_year=year,
            reason=(
                f"the {year} tax year has investment operations in category "
                f"{category.id!r} and the run declares no filing decision for it. Refused "
                "rather than assumed in either direction: 'the tool assumed you filed' and "
                "'the tool assumed you did not' are different wrong answers, and each "
                "silently changes the after-tax ranking (FR-014). Declaring an annual return "
                "is a duty for every year with investment operations (пп. 170.2.1 ПКУ), so "
                "the answer is a fact the owner knows and the tool cannot infer."
            ),
        )

    chain = _chain(carried, zero=zero, switches=switches, year=year)
    if isinstance(chain, UnsettledPositionUndeclared):
        return chain
    available, forfeited_by_chain, origins_in, chain_switch = chain

    single = _single_entry(entries, year=year, category=category, items=items)
    if not isinstance(single, RateEntry):
        return single

    # See ``_per_event_year``: the mark on a declared rule rides on the money, because the
    # money is what a reader is handed. ``_under`` has already put ``declared`` on this year's
    # zero and on the balance carried into it, so every figure below either derives from one
    # of those by a ``money`` function -- each of which unions provenance -- or from ``netted``
    # here (FR-027).
    netted = money.also_resting_on(money.total([item.result for item in items], currency), declared)
    claimable = available if filed else zero
    outcome = _apply_carryforward(
        netted=netted,
        claimable=claimable,
        available=available,
        origins_in=origins_in,
        shadow=carried.shadow,
        filed=filed,
        year=year,
        zero=zero,
    )

    base = outcome.base
    pit = money.scale_sourced(base, single.pit_rate, single.provenance)
    levy = money.scale_sourced(base, single.levy_rate, single.provenance)
    # The same rates against the all-filed counterfactual base, so the cost of the missed
    # declarations is measured in tax rather than in base -- and measured cumulatively, since
    # a year that pays early and a year that pays less have to net against each other.
    cost_to_date = money.add(
        carried.cost_to_date,
        money.sub(_at_these_rates(base, single), _at_these_rates(outcome.shadow_base, single)),
    )
    liability = AssessedLiability(
        pit=pit,
        levy=levy,
        base=base,
        method=method,
        standing=standing,
        rests_on=prov.merge_all([declared, *(item.charge.provenance for item in items)]),
    )
    state = CarryforwardState(
        filed=filed,
        brought_in=carried.balance,  # already under ``declared``: see ``_under``
        applied=outcome.applied,
        created=outcome.created,
        forfeited=money.add(forfeited_by_chain, outcome.forfeited),
        open_balance=outcome.open_balance,
        origins=outcome.origins,
        base_above_all_filed=money.sub(base, outcome.shadow_base),
        cost_of_not_filing_to_date=cost_to_date,
    )
    statement = AnnualStatement(
        tax_year=year,
        category=category.id,
        treatment=category.treatment,
        charges=items,
        netted_base=netted,
        carryforward=state,
        liability=liability,
        zero_because=_zero_reason(liability, items=items, entries=entries),
        settlement=rule.settlement,
        due_on=_due_on(rule, year),
        unsettled=_labels(method_switch, chain_switch, items=items),
    )
    return statement, _Carried(
        balance=outcome.open_balance,
        origins=outcome.origins,
        shadow=outcome.shadow_after,
        cost_to_date=cost_to_date,
        last_operations_year_filed=filed,
    )


def _under(declared: Provenance, currency: Currency, carried: _Carried) -> tuple[Money, _Carried]:
    """This year's zero and its opening balances, all resting on the rules that produced them.

    A zero here is **not** the additive identity ``money.zero`` stands for. A base of zero is a
    figure the statute produced -- the clamp пп. 170.2.6 puts on a negative annual result -- and
    a carryforward of zero is what a declared carryforward rule says the year leaves behind.
    Leaving those as bare zeroes was how an unverified rule marked a loss year's ``rests_on``
    and none of its amounts: the loss branches return ``base``, ``applied`` and ``forfeited``
    straight from the zero, and a quiet year is built out of nothing else.

    The balance carried in is re-marked for the same reason. It is reported *on this statement*,
    computed under these declared rules, and the first year's opening zero rests on nothing at
    all -- so without this it would arrive unmarked and leave unmarked.

    :attr:`_Carried.origins` is **not** re-marked, and does not need to be: it opens as an
    empty tuple, so there is no unmarked zero in it to leak, and every entry added later is a
    loss derived from a ``netted`` that already carries the year's rules. The amounts inside it
    are therefore marked by derivation rather than by this function -- which is why the sweep
    that checks them has to descend into containers to see them at all.
    """
    return (
        money.also_resting_on(money.zero(currency), declared),
        replace(
            carried,
            balance=money.also_resting_on(carried.balance, declared),
            shadow=money.also_resting_on(carried.shadow, declared),
            cost_to_date=money.also_resting_on(carried.cost_to_date, declared),
        ),
    )


def _quiet_year(
    *,
    year: int,
    carried: _Carried,
    zero: Money,
    category: IncomeCategory,
    rule: TimingRule,
    declared: Provenance,
    method: LotMethod,
    standing: MethodStanding,
) -> tuple[AnnualStatement, _Carried]:
    """A year in which this category saw no taxable event -- recorded, not omitted.

    FR-006's third distinguishable zero. A missing statement and a statement saying *nothing
    happened here* are different claims, and only the second one can be checked: it says the
    year was looked at. The carried balance passes through unchanged and is visible on the
    statement, which is also how an open carryforward stays reportable in the quiet years
    between the loss and the gain that absorbs it (FR-019).
    """
    return (
        AnnualStatement(
            tax_year=year,
            category=category.id,
            treatment=category.treatment,
            charges=(),
            netted_base=zero,
            carryforward=CarryforwardState(
                filed=None,
                brought_in=carried.balance,
                applied=zero,
                created=zero,
                forfeited=zero,
                open_balance=carried.balance,
                origins=carried.origins,
                base_above_all_filed=zero,
                cost_of_not_filing_to_date=carried.cost_to_date,
            ),
            liability=AssessedLiability(
                pit=zero,
                levy=zero,
                base=zero,
                method=method,
                standing=standing,
                rests_on=declared,
            ),
            zero_because=ZeroReason.NO_TAXABLE_EVENTS,
            settlement=rule.settlement,
            due_on=_due_on(rule, year),
            unsettled=(),
        ),
        carried,
    )


@dataclass(frozen=True, slots=True)
class _Outcome:
    """What the carryforward arithmetic produced for one year. Internal, and all of it named.

    A record rather than a seven-tuple because every field is a different claim about the
    money, and a positional unpacking of seven amounts is how two of them end up swapped.
    """

    base: Money
    applied: Money
    created: Money
    forfeited: Money
    open_balance: Money
    origins: tuple[tuple[int, Money], ...]
    shadow_base: Money
    """What the base would have been had every declaration been filed. Charged at the same
    rates to give the counterfactual tax, which is what the cumulative cost is measured
    against."""

    shadow_after: Money


def _apply_carryforward(
    *,
    netted: Money,
    claimable: Money,
    available: Money,
    origins_in: tuple[tuple[int, Money], ...],
    shadow: Money,
    filed: bool,
    year: int,
    zero: Money,
) -> _Outcome:
    """Net against the carried loss, and say what happened to every hryvnia of it.

    ``available`` is the balance that survived the chain question; ``claimable`` is what this
    year can actually deduct, which is ``available`` in a filed year and **nothing** in an
    unfiled one -- a carried loss is claimed *in a declaration*, and there is none.

    ``shadow`` is the same balance under "every declaration filed", carried alongside so the
    year can report what not filing cost **here** rather than leaving a reader to run the
    other branch and subtract (SC-010). It differs from the real balance in exactly two ways:
    it always absorbs a loss, and it is never forfeited.

    Every amount below is produced by choosing between two ``Money`` values or subtracting
    one from another -- never by dividing an amount out and scaling it back. That keeps each
    figure's provenance exactly the union of what it was computed from, and it means the
    identities the tests assert (``base = netted - applied``, ``open = available - applied``)
    hold to the bit rather than to a tolerance.
    """
    # ``>= 0.0`` rather than ``> 0.0``: a year netting to exactly nothing is not a loss year.
    # Sending it down the loss branch produced a ``created`` of ``-0.0`` and appended an
    # origin holding nothing, which reports a loss that never happened and puts an empty
    # shell in the queue ``_consume`` draws from.
    if netted.amount >= 0.0:
        applied = _smaller(claimable, netted)
        base = money.sub(netted, applied)
        shadow_used = _smaller(shadow, netted)
        return _Outcome(
            base=base,
            applied=applied,
            created=zero,
            forfeited=zero,
            open_balance=money.sub(available, applied),
            origins=_consume(origins_in, applied),
            shadow_base=money.sub(netted, shadow_used),
            shadow_after=money.sub(shadow, shadow_used),
        )

    loss = money.scale(netted, -1.0)
    if filed:
        return _Outcome(
            base=zero,
            applied=zero,
            created=loss,
            forfeited=zero,
            open_balance=money.add(available, loss),
            origins=(*origins_in, (year, loss)),
            shadow_base=zero,
            shadow_after=money.add(shadow, loss),
        )
    # Unfiled, and at a loss: the loss never becomes a carryforward at all. Forfeiture is per
    # loss year rather than a permanent state -- a later loss year that *is* filed carries
    # normally, which is why nothing about ``available`` changes here (spec.md, edge cases).
    return _Outcome(
        base=zero,
        applied=zero,
        created=zero,
        forfeited=loss,
        open_balance=available,
        origins=origins_in,
        shadow_base=zero,
        shadow_after=money.add(shadow, loss),
    )


def _smaller(left: Money, right: Money) -> Money:
    """Whichever amount is smaller, as the object it already is.

    ``min`` on the record rather than on ``.amount`` followed by a rebuild: the smaller
    amount keeps its own provenance, and no arithmetic is performed on a figure that is
    merely being selected.
    """
    return left if left.amount <= right.amount else right


def _consume(
    origins: tuple[tuple[int, Money], ...], applied: Money
) -> tuple[tuple[int, Money], ...]:
    """Draw ``applied`` from the open losses, oldest origin year first.

    Oldest first is not arbitrary: пп. 170.2.6 carries a loss «до його повного погашення», and
    absorbing the oldest first is what keeps each origin year's remainder attributable --
    which FR-019 asks for at the horizon. An origin fully absorbed is dropped rather than kept
    at zero, on the same reasoning ``ledger.lots`` drops an exhausted lot: an empty shell would
    take its turn in the order and report a loss year that has nothing left in it.
    """
    remaining = applied.amount
    kept: list[tuple[int, Money]] = []
    for origin_year, amount in sorted(origins, key=lambda item: item[0]):
        if remaining <= 0.0:
            kept.append((origin_year, amount))
            continue
        if amount.amount <= remaining:
            remaining -= amount.amount
            continue
        kept.append((origin_year, money.scale(amount, (amount.amount - remaining) / amount.amount)))
        remaining = 0.0
    return tuple(kept)


_ChainOutcome = tuple[Money, Money, tuple[tuple[int, Money], ...], UnsettledSwitch | None]
"""``(available, forfeited by the chain, the origins that survived, the label)``."""


def _chain(
    carried: _Carried,
    *,
    zero: Money,
    switches: UnsettledPositions,
    year: int,
) -> _ChainOutcome | UnsettledPositionUndeclared:
    """What survives a gap in the declarations, per the declared -- and unsettled -- reading.

    The question arises only where a loss was declared and a later year with investment
    operations was not, so the label is ``None`` in the ordinary case: an unbroken chain, or
    nothing carried. A label attached to every statement regardless of whether the reading
    changed its arithmetic is a label a reader learns to ignore.
    """
    if carried.last_operations_year_filed or carried.balance.amount <= 0.0:
        return carried.balance, zero, carried.origins, None
    if switches.chain is None:
        return UnsettledPositionUndeclared(
            question=(
                "whether an investment loss survives a year whose declaration was missed, "
                "given that form Ф1 pulls the loss from the immediately previous year's "
                "declaration"
            ),
            reason=(
                f"the {year} tax year follows a year with investment operations whose "
                "declaration was not filed, and a carryforward is still open. No source "
                "settles whether it survives the gap, so the position must be declared and "
                "labelled rather than chosen here -- the two branches give different tax "
                "(FR-015). Declare chain_broken_forfeits or chain_restorable under "
                "data/scenarios/tax/, and record an IPK (art. 52 PKU) as the resolution path."
            ),
        )
    if switches.chain.position is ChainPosition.BROKEN_FORFEITS:
        return zero, carried.balance, (), switches.chain.switch
    return carried.balance, zero, carried.origins, switches.chain.switch


def _entries_for(
    items: Sequence[ChargeRef], tax_classes: Mapping[str, TaxClass]
) -> tuple[RateEntry, ...] | RateUndeclaredBefore:
    """The dated rate entry in force behind each item, in item order.

    Looked up rather than stored on the charge: ``TaxCharge`` carries the provenance of the
    entry that produced it but not the entry itself, and the year needs the **rates** -- to
    charge a netted base, and to tell an exempt zero from a netted one.
    """
    found: list[RateEntry] = []
    for item in items:
        declared = tax_classes.get(item.charge.tax_class_id)
        if declared is None:
            raise LedgerInvariantError(
                f"charge on event {item.charge.event_sequence} names tax class "
                f"{item.charge.tax_class_id!r}, which is not in the pack this assessment was "
                "given. A charge exists only because a class produced it, so the two came "
                "from different runs."
            )
        entry = rate_on(declared, item.occurred_on)
        if isinstance(entry, RateUndeclaredBefore):
            # pragma: no cover -- unreachable within one run: the charge exists only because
            # ``flat_rate`` found an entry on this same date, and a class whose schedule has
            # since changed would be a pack from a different run.
            return entry  # pragma: no cover
        found.append(entry)
    return tuple(found)


def _single_entry(
    entries: tuple[RateEntry, ...],
    *,
    year: int,
    category: IncomeCategory,
    items: Sequence[ChargeRef],
) -> RateEntry | RateChangedWithinTaxYear | CategoryTaxedByTwoClasses:
    """The one rate entry a netting year's annual base is charged at, or why there is not one.

    A netting category charges **one** annual result, so it needs one pair of rates. Two
    refusals rather than one, because the fixes differ: a year spanning two dated entries is
    corrected in a rate schedule, and a category holding two classes is corrected in the
    category mapping. Each refusal's own reason says why it is not inferred instead.
    """
    classes = tuple(sorted({item.charge.tax_class_id for item in items}))
    if len(classes) > 1:
        return CategoryTaxedByTwoClasses(
            tax_year=year,
            category_id=category.id,
            tax_class_ids=classes,
            reason=(
                f"the {year} tax year nets {category.id!r} into one annual result, and its "
                f"items were charged by {len(classes)} different tax classes "
                f"({', '.join(classes)}). "
                "One result cannot be charged at two schedules, and picking one would tax "
                "part of the year at the wrong rate. Either the classes belong in different "
                "categories, or they are one class."
            ),
        )
    dates = tuple(sorted({entry.effective_from for entry in entries}))
    if len(dates) > 1:
        return RateChangedWithinTaxYear(
            tax_year=year,
            category_id=category.id,
            effective_dates=dates,
            reason=(
                f"the {year} tax year of {category.id!r} spans {len(dates)} dated rate "
                f"entries ({', '.join(day.isoformat() for day in dates)}), and a netting "
                "category charges one annual result. No source says how an annual base is "
                "split across a mid-year change: the 2024 levy rise needed its own law to "
                "settle that (Закон № 4113-IX), which is why it is refused here rather than "
                "inferred. Declare how the split works, with its citation, before assessing "
                "a year that straddles a change."
            ),
        )
    return entries[0]


def _at_these_rates(amount: Money, entry: RateEntry) -> Money:
    """One amount at both of a dated entry's rates -- the tax a relief is worth.

    PIT and levy added together **here and only here**: this is not a liability, it is the
    *difference* one input made to a pair of liabilities, and it is the single figure SC-010
    asks a reader to be able to quote. Where the two lines are a result they stay separate
    (:class:`AssessedLiability`); where they answer "what did this cost", one number is the
    answer to the question.
    """
    return money.add(
        money.scale_sourced(amount, entry.pit_rate, entry.provenance),
        money.scale_sourced(amount, entry.levy_rate, entry.provenance),
    )


def _zero_reason(
    liability: AssessedLiability,
    *,
    items: Sequence[ChargeRef],
    entries: Sequence[RateEntry],
) -> ZeroReason | None:
    """Why a year owes nothing, or ``None`` because it owes something (FR-006, E11).

    **Exemption is read off the rates, not off the amounts.** A break-even disposal under a
    23% class also charges zero, and calling that an exemption would cite a rule that says the
    opposite. So a zero is ``EXEMPT`` only when every entry that applied charges nothing at
    all, which is a claim about the law rather than about the arithmetic.
    """
    if liability_total(liability).amount != 0.0:
        return None
    if not items:
        return ZeroReason.NO_TAXABLE_EVENTS
    if all(entry.pit_rate == 0.0 and entry.levy_rate == 0.0 for entry in entries):
        return ZeroReason.EXEMPT
    return ZeroReason.NETTED_TO_ZERO


def _due_on(rule: TimingRule, tax_year: int) -> date | None:
    """The date a year's liability is payable: the declared deadline, in the following year.

    ``None`` for a withheld-at-source class, where there is no later date because there is no
    later payment -- an absence that means something, not a gap.

    The year is ``tax_year + 1`` because that is what the declared rule *means*: a deadline of
    1 August is 1 August of the year after the one being declared. The non-business-day
    convention is the declared one, resolved through ``primitives.conventions`` exactly as an
    instrument's coupon date is -- the same registry, the same four names, and an unrecognised
    one refused at load rather than here (FR-008).
    """
    if rule.settlement is SettlementBehaviour.WITHHELD_AT_SOURCE:
        return None
    adjust = conventions.business_day_rule(rule.non_business_day_rule)
    return adjust(date(tax_year + 1, rule.pay_by.month, rule.pay_by.day))


def _labels(
    method_switch: UnsettledSwitch | None,
    chain_switch: UnsettledSwitch | None,
    *,
    items: Sequence[ChargeRef],
) -> tuple[UnsettledSwitch, ...]:
    """The unsettled switches this statement's figures actually rest on (SC-012, G14).

    Two rules, and both are about *actually*:

    * the **method** switch attaches only where the year contains a disposal, because only a
      disposal's result depends on which lots were consumed. A year of coupons is the same
      number under all four methods;
    * the **chain** switch attaches only where a broken chain changed the arithmetic --
      ``_chain`` returns ``None`` when the question did not arise.

    A label on every statement regardless is a label a reader learns to ignore, which is worse
    than no label: it makes the statements that genuinely rest on an unanswered question
    indistinguishable from the ones that do not.
    """
    method_applies = method_switch if any(item.from_disposal for item in items) else None
    return tuple(switch for switch in (method_applies, chain_switch) if switch is not None)
