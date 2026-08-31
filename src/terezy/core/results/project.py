"""The wiring: declared terms -> schedule -> events -> ledger -> the hurdle rate.

One direction, no shortcuts (research.md D3)::

    declaration --(closed form)--> events --(fold)--> ledger --> schedule, figures

The instrument computes its contractual schedule in closed form, this module applies it as
ledger events, and **every reported figure is read back off the ledger** -- never off the
schedule and never off the instrument's own arithmetic. That is what makes FR-008
achievable rather than aspirational: a figure is traceable because there is no other way
for it to have come into existence.

**Why the ledger is folded twice.** Tax on a coupon is knowable from the coupon. Tax on a
disposal is knowable only from the *realised gain*, which is a property of the fold -- the
basis consumed is decided by the consumption method, over lots that only exist once the
purchase has been applied. So the gross stream is folded first, the charges are computed
against what that fold realised, the tax events are interleaved into the stream, and the
whole thing is folded again. The second fold produces the state every figure comes from.

Tax events are cash-only, so adding them cannot change a single disposal the first fold
computed -- which is what makes the two passes agree by construction rather than by
coincidence. The alternative, computing tax inside the fold, would put tax policy inside
the ledger and make a tax rule able to change the basis it is charged on.

**Sequence numbers are reassigned once, over the combined stream.** A tax charge belongs on
the same date as the income it taxes and immediately after it, and the ledger requires
sequence order to agree with date order. Numbering the gross stream and then inserting into
it means every later number shifts, so the charges are renumbered in the same pass that
builds the stream. Nothing else may hold a sequence number across that boundary.

**No cash deposit funds the purchase**, so the UAH balance goes negative on the purchase
date and recovers as coupons arrive. That is deliberate and is discussed in
``instruments.fixed_income``: an overdraft is a feasibility question about a plan, not a
ledger invariant, and inventing a funding event would need a cause the event vocabulary
does not have.

**The base currency is the instrument's own.** Feature 001 has one currency and no
exchange rate anywhere in the core, so there is nothing to convert and nothing may be
invented (``lots.base_amount_of`` refuses rather than guessing). The base role becomes a
scenario input the moment a foreign instrument arrives, and this is the line that changes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import assert_never

from terezy.core.errors import (
    InconsistentTerms,
    InfeasiblePurchase,
    InstrumentFailure,
    LedgerInvariantError,
    TaxFailure,
    UnresolvedTaxClass,
)
from terezy.core.inflation.series import CpiSeries, InflationAssumption
from terezy.core.instruments import fixed_income
from terezy.core.instruments import registry as instrument_registry
from terezy.core.instruments import terms as instrument_terms
from terezy.core.instruments.interface import (
    Assumptions,
    DateRange,
    EarlyExit,
    Holding,
    InstrumentDeclaration,
)
from terezy.core.ledger import engine
from terezy.core.ledger.engine import LedgerState
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind
from terezy.core.primitives import conventions, money, periods
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.money import Money
from terezy.core.primitives.periods import Window
from terezy.core.primitives.staleness import Ageing
from terezy.core.results import hurdle as hurdle_figures
from terezy.core.results import schedule as schedule_rows
from terezy.core.results.hurdle import CashFlow, HurdleRate
from terezy.core.results.schedule import CashFlowSchedule, ChargedOn
from terezy.core.scenarios.early_exit import SoldEarly
from terezy.core.tax import registry as tax_registry
from terezy.core.tax import year as tax_year
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxClass, TaxContext
from terezy.core.tax.schedule import RateUndeclaredBefore
from terezy.core.tax.year import AssessmentRules


@dataclass(frozen=True, slots=True)
class GovernedBy:
    """Which declared category treatment decides what becomes of a purchase difference."""

    category_id: str
    treatment: str
    reason: str
    """What that treatment means for this difference, in the output's own words."""


@dataclass(frozen=True, slots=True)
class TreatmentUnstated:
    """No assessment rules were given, so nothing here can say what governs the difference.

    A typed absence rather than a blank field or a guess: *outside*, *nets* and *per event*
    are three different claims about the same money, and defaulting to any of them would be
    the tool answering a question nobody asked it.
    """

    reason: str


@dataclass(frozen=True, slots=True)
class PurchasePremium:
    """What was paid, what comes back as principal, and the difference between them.

    FR-025. Reported as its own figure so that a premium or a discount is **visible** rather
    than surfacing only as a realised gain or loss at redemption -- which is where it would
    otherwise appear, a year or five later, indistinguishable from a market movement.

    **Always present, carrying a possibly-zero difference**, on the same reading that makes a
    zero tax charge cite its exemption: an absent figure meaning *bought at par* is a silent
    default, and the whole point of recording zeroes is that they name what produced them.

    **There is no premium rule here.** What happens to the difference is the declared
    tax category's business and nothing else's -- there is no amortisation here, no
    imputation, and no branch of its own. The figure states which treatment governed it and
    stops (FR-026).
    """

    paid: Money
    """What was actually paid, in full and exactly as stated. Nothing is amortised, nothing
    is imputed, and no part of it is reclassified as accrued interest (FR-024).

    Named ``paid`` rather than ``cost`` deliberately. ``cost`` on a result record is one of
    the names `tests/contract/test_cost_labels.py` forbids, because a route cost under an
    unlabelled name is a figure whose one-way-or-round-trip label has stopped travelling with
    it. This is not a route cost -- it is the purchase price -- and the clearer word says so
    without having to argue the point.
    """

    principal_returned: Money
    """What the units ``paid`` bought get back: the repayments they will receive, times
    quantity.

    Where the window closed the position first (015 FR-029), it is what those units get back
    **through the sale instead**: the ones still held at their resale price, and any the
    schedule already retired at the principal that retired them. Always the purchased
    population, never what was held at the end -- a schedule reinvesting its own coupons ends
    holding more units than the outlay bought, and those were bought with income.

    **Not ``face value x quantity``** (FR-025). The
    two coincide for a bond that repays its face once, which is every fixture this
    repository ships -- and they part the moment a schedule has already repaid part of its
    principal before the purchase. A unit of such an issue is a unit of what *remains*: a
    buyer paying the remaining principal exactly has broken even, and measuring them against
    the nominal face reported a discount of everything repaid before they arrived, a figure
    describing somebody else's trade years earlier. It is the same rule the retirement of
    units already follows -- **the share of what this holding receives** -- and it would be
    strange for paid-versus-received to measure "received" differently from the ledger.
    """

    difference: Money
    """``paid - principal_returned``. Positive is a premium, negative a discount, zero is par
    -- and a zero here says *par* rather than saying nothing."""

    tax_class_id: str | None
    """The declared class governing a disposal of this instrument, which is the event the
    difference is realised by -- or ``None`` where the declaration names none.

    **``None`` rather than an empty string**: a declaration is not required to name a class
    for every kind of income it might produce, and a figure carrying ``""`` here would report
    the *rules* as mapping no category to a class, sending a reader to the jurisdiction file
    when the thing to fix is the instrument's own declaration.
    """

    governed_by: GovernedBy | TreatmentUnstated
    """The category treatment that decides what the difference does, or why nobody said."""


@dataclass(frozen=True, slots=True)
class Projection:
    """Everything one projection produced, with the ledger it was all derived from."""

    ledger: LedgerState
    """The folded ledger: the events, the balances, the positions, the disposals.

    Carried rather than discarded because it is the audit trail. Every figure below
    resolves through it, and a result that kept only its conclusions would be exactly the
    untraceable number Principle III forbids reporting.
    """

    schedule: CashFlowSchedule
    """The dated lines a reader reads: gross, tax and net per date."""

    charges: tuple[TaxCharge, ...]
    """Every tax charge recorded, in ledger order. Zeroes included -- a zero charge that
    cites its exemption is the evidence the exemption was applied."""

    hurdle: HurdleRate
    """The benchmark figure this whole feature exists to produce."""

    at_purchase: PurchasePremium
    """What was paid against what this holding gets back, and what governs the difference."""

    sold_early: SoldEarly | None
    """The sale that closed the position, or ``None`` where its own terms did (015 FR-029)."""


ProjectionOutcome = Projection | InstrumentFailure | TaxFailure
"""What a projection returns: a result, or a typed reason there is none.

Never a partial result and never an empty one. Match it exhaustively -- a ``case _:`` arm
the type checker proves unreachable -- so that a new failure variant becomes an error at
every site that must handle it (FR-017).
"""


def project(
    declaration: InstrumentDeclaration,
    holding: Holding,
    horizon: DateRange,
    assumptions: Assumptions,
    *,
    tax_classes: Mapping[str, TaxClass],
    cpi_series: CpiSeries | None = None,
    inflation_assumption: InflationAssumption | None = None,
    ageing: Ageing | None = None,
    assessment_rules: AssessmentRules | None = None,
    early_exit: EarlyExit | None = None,
) -> ProjectionOutcome:
    """Project one holding to maturity and report what it pays and what it returns.

    ``tax_classes`` is the declared tax pack, keyed by class id -- passed in rather than
    looked up, because loading is the ``data`` layer's job and the core must be testable
    with no file on disk anywhere near the arithmetic (research.md D1). A class the
    instrument references and this mapping does not contain is reported, never treated as
    untaxed: those are opposite claims and only one of them is cited.

    **``cpi_series`` and ``inflation_assumption`` fill the real-terms slot.** Both
    default to ``None``, and the default is not a silence: the resulting figures are
    :data:`~terezy.core.results.hurdle.NOT_DEFLATED`, whose two reasons say *no CPI series was
    declared* and *no future-inflation assumption was declared* -- which is exactly what
    happened, and is what a reader is shown. 007's FR-006 and US1 scenario 5 require *a
    projection identical to one that ran under feature 001* to run here unchanged and produce
    a shape-identical result; a required argument would have made every one of those call
    sites a lie about what changed.

    **``assessment_rules`` is what lets the purchase figure say which treatment governs
    the difference** (FR-026). ``None`` is not a silence either: the figure then carries
    :class:`TreatmentUnstated`, saying that nobody supplied the rules -- because *outside*,
    *nets* and *per event* are three different claims about the same money and defaulting to
    one would answer a question nobody asked.

    **Nothing on the tuple path supplies it today** (recorded 2026-08-30):
    ``core.decision.tuple_outcome`` calls this function without rules, so every projection
    reached through the join carries :class:`TreatmentUnstated`. That is honest rather than
    wrong -- the join is given no jurisdiction to resolve them from -- and it means FR-026's
    named treatment is reachable only on a direct call. Closing it needs the join to be told
    which jurisdiction assesses the holding, which is a term the tuple does not carry.

    ``ageing`` carries the declared staleness thresholds and the ``as_of`` date the question is
    asked at (FR-005). ``None`` means this run did not ask, which the figures report as
    :data:`~terezy.core.primitives.staleness.UNASSESSED` rather than as freshness.

    **``early_exit`` is what a window shorter than the instrument's own terms is closed with**
    (015 FR-029). ``None`` is not a silence and is the shipped state: no access declaration
    quotes a resale price, so such a window refuses naming ``access.resale_price`` rather than
    striking a sale at a figure nobody declared.
    """
    ops = instrument_registry.ops_for(declaration.instrument_class)
    produced = ops.events(declaration, holding, horizon, assumptions, early_exit)
    match produced:
        case InfeasiblePurchase() | InconsistentTerms():
            return produced
        case tuple():
            gross_events = produced
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(produced)

    base_currency = declaration.currency
    gross_state = engine.fold(
        gross_events,
        base_currency=base_currency,
        consumption_method=assumptions.consumption_method,
    )

    charged = _charge_every_taxable_event(declaration, gross_state, tax_classes)
    if isinstance(charged, UnresolvedTaxClass | RateUndeclaredBefore):
        return charged

    combined, charges, taxed_by = _interleave(gross_state, charged)
    state = engine.fold(
        combined,
        base_currency=base_currency,
        consumption_method=assumptions.consumption_method,
    )

    year_fraction = conventions.day_count(instrument_terms.day_count_of(declaration.terms))

    # The contractual series is generated WITHOUT the coupon policy, because a
    # contractual yield to maturity is a property of the paper and reinvestment is a
    # decision about the proceeds. Taking it from `state.applied` instead would fold the
    # reinvestment purchases and the larger redemption into the figure, and `nominal_ytm`
    # would then move when the owner changed their mind about coupons -- a figure
    # labelled "contractual" that is not (FR-005). Policy-invariance is asserted by
    # tests/unit/test_contractual_yield_is_policy_invariant.py.
    sold_early = _sold_early(gross_events, early_exit)
    contractual_events = _contractual_events(declaration, holding, horizon, assumptions, early_exit)
    if isinstance(contractual_events, InfeasiblePurchase | InconsistentTerms):
        return contractual_events  # pragma: no cover -- the policy run already succeeded

    return Projection(
        ledger=state,
        schedule=schedule_rows.of_ledger(
            state,
            conventions=instrument_terms.conventions_of(declaration.terms),
            taxed_by=taxed_by,
        ),
        charges=charges,
        at_purchase=_at_purchase(declaration, holding, assessment_rules, sold_early),
        sold_early=sold_early,
        hurdle=hurdle_figures.of_flows(
            contractual=_flows(contractual_events, holding, year_fraction),
            received=_flows(
                state.applied,
                holding,
                year_fraction,
                assessed={charged.tax_event: charged.amount for charged in taxed_by.values()},
            ),
            total_tax=money.total([charge.total for charge in charges], base_currency),
            excludes=hurdle_figures.EXCLUDES
            | instrument_terms.excludes_of(declaration.terms)
            | _sale_excludes(sold_early),
            provenance=prov.merge(
                prov.merge_all(event.amount.provenance for event in state.applied),
                prov.merge_all(charge.provenance for charge in charges),
            ),
            deflate_with=hurdle_figures.Deflation(
                window=_deflation_window(holding, contractual_events),
                series=cpi_series,
                assumption=inflation_assumption,
                ageing=ageing,
            ),
        ),
    )


def _sale_excludes(sold: SoldEarly | None) -> frozenset[str]:
    """What a *contractual* figure stops being when the position is sold before its terms end.

    ``nominal_ytm`` is documented as a yield **to maturity** -- a property of the terms and the
    price, and policy-invariant. Under 015 FR-029 a window that ends first closes the series at
    a **declared resale quote** under a **stated belief**, and neither is a term of the paper.
    The figure is still what the holding pays over the window it was asked about; what it stops
    being is unconditional, and the exclusion is where a reader is told so.
    """
    if sold is None:
        return frozenset()
    return frozenset(
        {
            "the contractual figure closes at a declared resale price rather than at maturity "
            f"({sold.on.isoformat()}), under the stated belief {sold.assumption.id!r} that the "
            "observed spread holds at that date -- neither is a term of the paper"
        }
    )


def _sold_early(events: Sequence[Event], early_exit: EarlyExit | None) -> SoldEarly | None:
    """The sale that closed the position, read off the stream that closed it.

    A bond emits ``EventKind.REDEMPTION`` for one reason only -- an early sale; it repays
    principal under ``PRINCIPAL_REPAYMENT`` -- so the event is found rather than the date
    recomputed. Recomputing *which* day the window ended on would be a second opinion about a
    fact the instrument already settled, and the two would disagree the first time a
    business-day rule moved one of them.
    """
    if early_exit is None:
        return None
    sale = next((event for event in events if event.kind is EventKind.REDEMPTION), None)
    if sale is None:
        return None
    if sale.quantity is None:  # pragma: no cover -- `early_sale` always carries one
        return None
    return SoldEarly(
        on=sale.occurred_on,
        units=sale.quantity,
        price_per_unit=early_exit.price_per_unit,
        proceeds=sale.amount,
        assumption=early_exit.assumption,
    )


def _what_the_treatment_means(treatment: tax_year.Treatment) -> str:
    """What one declared treatment means for a purchase difference, in the output's own words.

    An exhaustive ``match`` rather than a mapping, so a fourth treatment is a **type error**
    here rather than a figure that quietly explains itself wrongly at runtime -- the same
    reason ``_taxable_kind`` below is written the same way.
    """
    match treatment:
        case tax_year.Treatment.OUTSIDE:
            return (
                "this category stands outside the annual calculation on both sides, income "
                "and costs alike, so the difference reduces no other base -- a loss here "
                "buys no shield"
            )
        case tax_year.Treatment.NETS:
            return (
                "this category nets its year's results before any rate applies, so the "
                "difference reaches the annual base and a negative year carries forward"
            )
        case tax_year.Treatment.PER_EVENT:
            return (
                "nothing nets in this category: the difference is realised on the disposal "
                "it belongs to and reaches no other event's charge"
            )
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(treatment)


def _at_purchase(
    declaration: InstrumentDeclaration,
    holding: Holding,
    rules: AssessmentRules | None,
    sold: SoldEarly | None,
) -> PurchasePremium:
    """What was paid against what this holding gets back (FR-025, amended).

    The declaration is **asked** what a unit returns to a buyer arriving on this date rather
    than having its face value read: the two answers differ for a schedule that has already
    repaid part of its principal, and the question both forms answer is the one that is true
    of both.

    **A position sold before its terms end gets back the sale, not the principal** (015 FR-029).
    The field says *what this holding gets back*, and a redemption that will not happen is not
    it: reporting the paper's principal there would assert a premium or a discount realised at a
    maturity the window ends before, while the ledger realises the sale's own gain or loss.

    **A sale is priced over the purchased units, and the rest of them over what repaid them.**
    ``SoldEarly.units`` is not ``holding.quantity``, in either direction: under ``reinvest`` a
    schedule buys further units out of its own coupons and sells more than the outlay bought,
    and an amortising schedule retires units as it repays and sells fewer. Pricing the whole
    sale against ``paid`` reported a par purchase sold at a spread as a large discount, and
    pricing the retired units at the resale quote would charge a spread on units that were
    repaid rather than sold -- and the difference is what the disposal-gain class governs.

    The two cases cannot occur together, so the split is exact rather than an approximation:
    ``enumerated`` refuses ``reinvest`` outright, which is the only way units grow.

    **The sale half is marked by the terms only where the terms decided how much was left.**
    Nothing retired means the whole purchase is sold and the quantity is the holding's own, so
    the figure is the quote times a number the terms had no part in; something retired means
    the units sold are what the declared repayments left, and the terms are behind that figure
    as much as behind the repaid half. A mark that named the terms in both cases would send a
    reader chasing an unverified quote to the wrong declaration.
    """
    per_unit = instrument_terms.principal_returned(
        declaration.terms, bought_on=holding.purchased_on
    )
    terms = declaration.terms.provenance
    if sold is None:
        returned = money.scale_sourced(per_unit, holding.quantity, terms)
    else:
        still_held = min(sold.units, holding.quantity)
        retired = holding.quantity - still_held
        returned = (
            money.scale(sold.price_per_unit, still_held)
            if retired == 0.0
            else money.add(
                money.scale_sourced(sold.price_per_unit, still_held, terms),
                money.scale_sourced(per_unit, retired, terms),
            )
        )
    disposal_class = declaration.tax_classes.get(TaxableEventKind.DISPOSAL_GAIN)
    return PurchasePremium(
        paid=holding.cost,
        principal_returned=returned,
        difference=money.sub(holding.cost, returned),
        tax_class_id=disposal_class,
        governed_by=_governed_by(disposal_class, rules),
    )


def _governed_by(
    disposal_class: str | None, rules: AssessmentRules | None
) -> GovernedBy | TreatmentUnstated:
    """The declared category treatment that decides what the difference does, or why not.

    Three ways there can be no answer, and they send a reader to three different files, so
    each says which one: the run was given no rules, the **instrument** names no class for a
    disposal, or the **rules** map no category to the class it does name.
    """
    if disposal_class is None:
        return TreatmentUnstated(
            reason=(
                "this instrument declares no tax class for a disposal, so nothing here can "
                "say what governs the difference between what was paid and what comes "
                "back. It is the "
                "declaration that is incomplete rather than the rules: a class named and "
                "unmapped is a different fault, and reported as one."
            )
        )
    if rules is None:
        return TreatmentUnstated(
            reason=(
                "this run was given no assessment rules, so nothing here can say whether "
                "the difference nets with the year's other results, is charged on its own "
                "event, or falls outside the calculation entirely. Those are three "
                "different claims about the same money and none of them is assumed."
            )
        )
    category_id = rules.category_of_class.get(disposal_class)
    category = None if category_id is None else rules.categories.get(category_id)
    if category is None:
        return TreatmentUnstated(
            reason=(
                f"the rules of {rules.jurisdiction_id!r} map no income category to the tax "
                f"class {disposal_class!r}, so what governs the difference is undeclared "
                "rather than decided here."
            )
        )
    return GovernedBy(
        category_id=category.id,
        treatment=category.treatment.value,
        reason=_what_the_treatment_means(category.treatment),
    )


def _deflation_window(holding: Holding, contractual: Sequence[Event]) -> Window:
    """The span a real counterpart of the contractual yield is deflated over (007 FR-007).

    From the month **after** the purchase to the month the last contractual flow lands in,
    inclusive. Two boundary decisions, both made here rather than at each call site so they
    cannot drift apart by a month:

    * **The first month is the one after the purchase month**, because a published index for
      month *M* measures the price change *during* *M* relative to *M-1*, and a purchase made
      on any day of *M* has already paid *M*'s prices. The first change the owner actually
      lives through is the one in *M + 1*. Counting *M* itself would charge the holding for
      inflation that happened before it existed.
    * **The last month is the last contractual flow's**, not the horizon's. The yield being
      deflated is a property of the paper -- it annualises the contractual series -- so the
      deflator has to span the same thing. A horizon running past redemption would deflate the
      yield by months in which the holding had already paid out.

    The count of months between the two is therefore the number of monthly price changes the
    holding lived through, which is exactly what the annualisation divides by.
    """
    last = max(event.occurred_on for event in contractual)
    return Window(
        first=periods.next_month(periods.month_of(holding.purchased_on)),
        last=periods.month_of(last),
    )


def _contractual_events(
    declaration: InstrumentDeclaration,
    holding: Holding,
    horizon: DateRange,
    assumptions: Assumptions,
    early_exit: EarlyExit | None,
) -> tuple[Event, ...] | InfeasiblePurchase | InconsistentTerms:
    """The events the paper itself produces, with no coupon policy and no tax applied.

    Regenerated rather than filtered out of the taxed stream. Filtering could remove the
    tax charges but not the *consequences* of reinvestment -- the extra purchases and the
    larger redemption are ordinary events indistinguishable from contractual ones once
    they are in the ledger. Generating a second, policy-free stream is the only way to
    get a series that answers "what does this bond promise", and it is cheap and pure.

    ``hold_cash`` is the policy-free case by construction: it buys nothing, so the events
    are exactly the declared coupons and the principal.
    """
    ops = instrument_registry.ops_for(declaration.instrument_class)
    produced = ops.events(
        declaration,
        holding,
        horizon,
        replace(assumptions, coupon_policy=fixed_income.HOLD_CASH),
        early_exit,
    )
    match produced:
        case InfeasiblePurchase() | InconsistentTerms():
            return produced
        case tuple():
            return produced
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(produced)


def _flows(
    events: Sequence[Event],
    holding: Holding,
    year_fraction: conventions.DayCountFn,
    *,
    assessed: Mapping[int, Money] | None = None,
) -> tuple[CashFlow, ...]:
    """Ledger events as ``(years from purchase, signed amount)`` pairs for a root find.

    Time is measured with the issue's **declared** day-count convention, from the purchase
    date -- the same convention that sized the coupons. A separate hard-coded 365 here
    would let the yield disagree with the schedule it was computed from, in a way that
    would look like a rounding difference and would not be one.

    **``assessed`` is what keeps the cash-flow return an after-tax figure.** A tax charge does
    not debit the account, so a series taken from the ledger's own amounts would silently be a
    **pre-tax** series while the field still called itself net of tax. The
    mapping supplies, per **charge-event** sequence -- the memo's own, not the taxed event's --
    what that event assessed, and it is the same ``taxed_by`` pairing the schedule uses, so
    the two cannot disagree about which line a charge belongs to.

    **Accrual rather than payment, deliberately.** This figure annualises the return of the
    *paper*: what the holding earns and what the tax on it costs. When that tax is settled is
    a fact about the owner's tax year rather than about the instrument. Accrual is also the
    conservative of the two readings -- paying earlier is worse.
    """
    charged = assessed or {}
    return tuple(
        (
            year_fraction(holding.purchased_on, event.occurred_on),
            _flow_amount(event, charged),
        )
        for event in events
    )


def _flow_amount(event: Event, assessed: Mapping[int, Money]) -> float:
    """One event's contribution to a return series: its cash, or the tax it assessed.

    A charge event contributes the negated charge rather than its own (zero) amount.
    """
    charge = assessed.get(event.sequence)
    return event.amount.amount if charge is None else -charge.amount


def _charge_every_taxable_event(
    declaration: InstrumentDeclaration,
    state: LedgerState,
    tax_classes: Mapping[str, TaxClass],
) -> tuple[TaxCharge, ...] | TaxFailure:
    """One charge per taxable event, keyed later by the event it was charged on.

    Every taxable event gets a charge, including one whose base is zero and one whose rate
    is zero. Skipping either would leave the ledger unable to distinguish "the rule applied
    and the answer was nothing" from "no rule ran here", and the second of those is how a
    holding silently becomes untaxed.
    """
    rule = tax_registry.ops_for(tax_registry.FLAT_RATE)
    charges: list[TaxCharge] = []
    for event in state.applied:
        kind = _taxable_kind(event.kind)
        if kind is None:
            continue
        class_id = declaration.tax_classes.get(kind)
        if class_id is None:
            if not any(kind in declared.applies_to for declared in tax_classes.values()):
                # Not applicable, and the claim is the data's: no class in the declared
                # tax pack applies to this event kind, so there is no rule to run and
                # nothing to cite. Distinct from an exemption, whose zero charge cites
                # its class (E11), and distinct from the unresolved reference below,
                # which fires exactly when the pack *does* declare a class for the kind
                # and the instrument fails to say which treatment governs it.
                continue
            return UnresolvedTaxClass(
                tax_class_id=f"<none declared for {kind.value}>",
                instrument_id=declaration.id,
                reason=(
                    f"{declaration.id!r} produces {kind.value!r} income on "
                    f"{event.occurred_on.isoformat()} but declares no tax class for it. "
                    "Reported rather than treated as untaxed: an exemption is a cited "
                    "claim and a missing rule is not, and treating the second as the "
                    "first would flatter every figure derived from this holding."
                ),
            )
        tax_class = tax_classes.get(class_id)
        if tax_class is None:
            return UnresolvedTaxClass(
                tax_class_id=class_id,
                instrument_id=declaration.id,
                reason=(
                    f"{declaration.id!r} taxes its {kind.value!r} income under class "
                    f"{class_id!r}, which is not declared in the tax pack this run was "
                    "given. The holding is not projected rather than projected untaxed."
                ),
            )
        outcome = rule.charge(
            event,
            tax_class,
            TaxContext(
                instrument_id=declaration.id,
                taxable_event=kind,
                taxable_base=_taxable_base(event, kind, state),
                charged_for_year=event.occurred_on.year,
            ),
        )
        match outcome:
            case UnresolvedTaxClass() | RateUndeclaredBefore():
                # A class can exist, cover the kind, and still have no
                # rate in force on the event's date. Returned rather than skipped -- an
                # uncharged event is indistinguishable from an exempt one in the ledger,
                # and the whole point of FR-012 is that the two are opposite claims.
                return outcome
            case TaxCharge():
                charges.append(outcome)
            case _:  # pragma: no cover -- mypy proves this unreachable
                assert_never(outcome)
    return tuple(charges)


def _taxable_kind(kind: EventKind) -> TaxableEventKind | None:
    """Which kind of taxable income a ledger event is, or ``None`` if it is not income.

    An exhaustive ``match`` rather than a mapping with a default, so that adding an event
    kind is a type error here instead of quietly becoming untaxable. ``None`` is the
    considered answer for the kinds listed, not the fallback for the ones nobody thought
    about.
    """
    match kind:
        case EventKind.COUPON:
            return TaxableEventKind.COUPON
        case EventKind.DISTRIBUTION:  # pragma: no cover -- unreachable on this path
            # Present for exhaustiveness and **not** reachable here: no ``InstrumentOps``
            # implementation this function maps emits a distribution. The arm cannot simply
            # be dropped -- the ``assert_never`` below is what makes a forgotten event kind a
            # type error, and omitting this one would make that assertion fail to compile
            # rather than making the case impossible.
            return TaxableEventKind.DISTRIBUTION
        case EventKind.PRINCIPAL_REPAYMENT | EventKind.REDEMPTION:
            # A redemption is a disposal: what is taxable is the realised gain, not the
            # amount returned. For a bond redeemed at par that gain is exactly zero, and
            # taxing the principal instead would tax the owner's own money back. A fund
            # buyback is the same claim about a different contract, which is why the two
            # kinds share this arm.
            return TaxableEventKind.DISPOSAL_GAIN
        case EventKind.RAMP_MOVEMENT:
            # Whether a conversion is taxable is a *declaration*, never a claim of this
            # engine (SIMULATOR_SPEC §4.2: a stablecoin's later conversion may itself be
            # taxable, and both interpretations must be modellable). The kind maps
            # mechanically; the charge happens only under a declared class whose
            # ``applies_to`` covers it, and a kind no declared class applies to is *not
            # applicable* -- see ``_charge_every_taxable_event``.
            return TaxableEventKind.CONVERSION
        case (
            EventKind.PURCHASE
            | EventKind.REINVESTMENT
            | EventKind.CASH_DEPOSIT
            | EventKind.TAX_CHARGE
            | EventKind.TAX_PAYMENT
            | EventKind.FEE
        ):
            # Mechanics, not tax policy: a purchase and a reinvestment are money going
            # out, a deposit arrives from outside the modelled system, a fee is a cost,
            # and a tax charge is the output of this very process. A tax *payment* is
            # the settlement of that output: taxing it would tax the tax. Listed
            # explicitly rather than falling through, because the ``assert_never`` below
            # is what makes "nobody thought about this kind" a type error.
            return None
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(kind)


def _taxable_base(event: Event, kind: TaxableEventKind, state: LedgerState) -> Money:
    """What the rates apply to: the coupon itself, or the gain a disposal realised.

    The disposal's **base-currency** gain, because tax is assessed in the tax currency and
    that is UAH. The two coincide here and the choice is still made explicitly, because
    the day they differ -- a position flat in dollars across a devaluation realises a gain
    in hryvnia -- the trade-currency figure would be the wrong number to tax.
    """
    match kind:
        case (
            TaxableEventKind.COUPON
            | TaxableEventKind.INTEREST
            | TaxableEventKind.DISTRIBUTION
            # The base a declared conversion class applies to is the amount the movement
            # records. A gain-based reading of a conversion needs a basis model for the
            # converted asset, which arrives with the feature that models virtual-asset
            # bases -- as cited data, not as an assumption here.
            | TaxableEventKind.CONVERSION
        ):
            return event.amount
        case TaxableEventKind.DISPOSAL_GAIN:
            for disposal in state.disposals:
                if disposal.sequence == event.sequence:
                    return disposal.realised_gain_base_ccy
            raise LedgerInvariantError(
                f"event {event.sequence} is taxed as a disposal gain but the fold "
                "realised no disposal for it, so there is no gain to charge against. "
                "Charging the proceeds instead would tax the owner's own basis back."
            )
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(kind)


def _interleave(
    gross_state: LedgerState,
    charges: Sequence[TaxCharge],
) -> tuple[tuple[Event, ...], tuple[TaxCharge, ...], Mapping[int, ChargedOn]]:
    """Weave each charge in behind the event it taxes, renumbering the whole stream.

    Returns the combined stream, the charges carrying their new event sequence numbers,
    and the mapping from a taxed event to the assessment recorded against it. The mapping is
    built here, by the code that creates both sides of it, rather than reconstructed later
    from dates -- an inferred pairing would be a guess, and it would break the first time
    two taxable events shared a date.

    **The charged amount is in the mapping** rather than left for the schedule to read off
    the tax event: a charge moves no cash, so the memo event's amount is zero and a schedule
    reading it would report no tax at all.
    """
    by_gross_sequence = {charge.event_sequence: charge for charge in charges}
    combined: list[Event] = []
    renumbered: list[TaxCharge] = []
    taxed_by: dict[int, ChargedOn] = {}
    for event in gross_state.applied:
        taxed = replace(event, sequence=len(combined) + 1)
        combined.append(taxed)
        charge = by_gross_sequence.get(event.sequence)
        if charge is None:
            continue
        moved = replace(charge, event_sequence=taxed.sequence)
        renumbered.append(moved)
        combined.append(_tax_event(taxed, moved, sequence=len(combined) + 1))
        taxed_by[taxed.sequence] = ChargedOn(tax_event=combined[-1].sequence, amount=moved.total)
    return tuple(combined), tuple(renumbered), taxed_by


def _tax_event(taxed: Event, charge: TaxCharge, *, sequence: int) -> Event:
    """The ledger line for one charge: an assessment recorded, and no cash moved.

    Dated with the income it taxes rather than with a payment date, because that is the date
    the liability *accrued*; ``charged_for_year`` records the year it accrues to.

    **No cash moves on this line** (research.md D1), because debiting the account on the day
    the income arrived is defect B5. The amount is
    :func:`terezy.core.tax.year.memo_amount` -- the charge's own money at no magnitude, so the
    citation still travels -- and the liability leaves cash as a ``TAX_PAYMENT`` later.

    A charge of zero still becomes an event: it is the record that the exemption was applied,
    traceable to its class and its citation like any other figure (FR-003, C6).
    """
    return Event(
        sequence=sequence,
        occurred_on=taxed.occurred_on,
        kind=EventKind.TAX_CHARGE,
        amount=tax_year.memo_amount(charge.total),
        owner_id=taxed.owner_id,
        caused_by=CausationRef(
            kind=CausationKind.TAX_RULE,
            id=charge.tax_class_id,
            detail=(
                f"tax class {charge.tax_class_id!r} charged on a taxable base of "
                f"{charge.taxable_base.amount!r} "
                f"{charge.taxable_base.currency.value} arising from event "
                f"{taxed.sequence}, accruing to the {charge.charged_for_year} tax year"
            ),
        ),
        lot_ref=None,
        quantity=None,
        allocated_to=None,
        capacity_pool=None,
    )
