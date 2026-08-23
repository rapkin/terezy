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
from terezy.core.instruments import fixed_income
from terezy.core.instruments import registry as instrument_registry
from terezy.core.instruments.interface import (
    Assumptions,
    DateRange,
    Holding,
    InstrumentDeclaration,
)
from terezy.core.ledger import engine
from terezy.core.ledger.engine import LedgerState
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind
from terezy.core.primitives import conventions, money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.money import Money
from terezy.core.results import hurdle as hurdle_figures
from terezy.core.results import schedule as schedule_rows
from terezy.core.results.hurdle import CashFlow, HurdleRate
from terezy.core.results.schedule import CashFlowSchedule, ConventionsApplied
from terezy.core.tax import registry as tax_registry
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxClass, TaxContext
from terezy.core.tax.schedule import RateUndeclaredBefore


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
) -> ProjectionOutcome:
    """Project one holding to maturity and report what it pays and what it returns.

    ``tax_classes`` is the declared tax pack, keyed by class id -- passed in rather than
    looked up, because loading is the ``data`` layer's job and the core must be testable
    with no file on disk anywhere near the arithmetic (research.md D1). A class the
    instrument references and this mapping does not contain is reported, never treated as
    untaxed: those are opposite claims and only one of them is cited.
    """
    ops = instrument_registry.ops_for(declaration.instrument_class)
    produced = ops.events(declaration, holding, horizon, assumptions)
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

    year_fraction = conventions.day_count(declaration.terms.day_count)

    # The contractual series is generated WITHOUT the coupon policy, because a
    # contractual yield to maturity is a property of the paper and reinvestment is a
    # decision about the proceeds. Taking it from `state.applied` instead would fold the
    # reinvestment purchases and the larger redemption into the figure, and `nominal_ytm`
    # would then move when the owner changed their mind about coupons -- a figure
    # labelled "contractual" that is not (FR-005). Policy-invariance is asserted by
    # tests/unit/test_contractual_yield_is_policy_invariant.py.
    contractual_events = _contractual_events(declaration, holding, horizon, assumptions)
    if isinstance(contractual_events, InfeasiblePurchase | InconsistentTerms):
        return contractual_events  # pragma: no cover -- the policy run already succeeded

    return Projection(
        ledger=state,
        schedule=schedule_rows.of_ledger(
            state,
            conventions=ConventionsApplied(
                periodicity=declaration.terms.periodicity,
                day_count=declaration.terms.day_count,
                business_day_rule=declaration.terms.business_day_rule,
            ),
            taxed_by=taxed_by,
        ),
        charges=charges,
        hurdle=hurdle_figures.of_flows(
            contractual=_flows(contractual_events, holding, year_fraction),
            received=_flows(state.applied, holding, year_fraction),
            total_tax=money.total([charge.total for charge in charges], base_currency),
            provenance=prov.merge(
                prov.merge_all(event.amount.provenance for event in state.applied),
                prov.merge_all(charge.provenance for charge in charges),
            ),
        ),
    )


def _contractual_events(
    declaration: InstrumentDeclaration,
    holding: Holding,
    horizon: DateRange,
    assumptions: Assumptions,
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
) -> tuple[CashFlow, ...]:
    """Ledger events as ``(years from purchase, signed amount)`` pairs for a root find.

    Time is measured with the issue's **declared** day-count convention, from the purchase
    date -- the same convention that sized the coupons. A separate hard-coded 365 here
    would let the yield disagree with the schedule it was computed from, in a way that
    would look like a rounding difference and would not be one.
    """
    return tuple(
        (year_fraction(holding.purchased_on, event.occurred_on), event.amount.amount)
        for event in events
    )


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
                # ⚙ feature 006: a class can exist, cover the kind, and still have no
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
    about: a purchase and a reinvestment are money going *out*, a deposit is money
    arriving from outside the modelled system, a fee is a cost, and a tax charge is the
    output of this very process.
    """
    match kind:
        case EventKind.COUPON:
            return TaxableEventKind.COUPON
        case EventKind.DISTRIBUTION:  # pragma: no cover -- unreachable on this path
            # ⚙ feature 006. Present for exhaustiveness and **not** reachable here: this
            # function maps the events of an ``InstrumentOps`` implementation, and the only
            # one in ``registry.REGISTRY`` is ``fixed_income``, which emits no distribution.
            # A fund has its own mapping in ``core.results.fund``. The arm cannot simply be
            # dropped -- the ``assert_never`` below is what makes a forgotten event kind a
            # type error, and omitting this one would make that assertion fail to compile
            # rather than making the case impossible. Marked like the ``case _`` beside it,
            # for the same reason: unreachable arms should say so rather than sit as an
            # uncovered line a reader mistakes for an untested one.
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
            | EventKind.FEE
        ):
            # Mechanics, not tax policy: a purchase and a reinvestment are money going
            # out, a deposit arrives from outside the modelled system, a fee is a cost,
            # and a tax charge is the output of this very process. Listed explicitly
            # rather than falling through, because the ``assert_never`` below is what
            # makes "nobody thought about this kind" a type error.
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
) -> tuple[tuple[Event, ...], tuple[TaxCharge, ...], Mapping[int, int]]:
    """Weave each charge in behind the event it taxes, renumbering the whole stream.

    Returns the combined stream, the charges carrying their new event sequence numbers,
    and the mapping from a taxed event to the tax event charged on it. The mapping is
    built here, by the code that creates both sides of it, rather than reconstructed later
    from dates -- an inferred pairing would be a guess, and it would break the first time
    two taxable events shared a date.
    """
    by_gross_sequence = {charge.event_sequence: charge for charge in charges}
    combined: list[Event] = []
    renumbered: list[TaxCharge] = []
    taxed_by: dict[int, int] = {}
    for event in gross_state.applied:
        taxed = replace(event, sequence=len(combined) + 1)
        combined.append(taxed)
        charge = by_gross_sequence.get(event.sequence)
        if charge is None:
            continue
        moved = replace(charge, event_sequence=taxed.sequence)
        renumbered.append(moved)
        combined.append(_tax_event(taxed, moved, sequence=len(combined) + 1))
        taxed_by[taxed.sequence] = combined[-1].sequence
    return tuple(combined), tuple(renumbered), taxed_by


def _tax_event(taxed: Event, charge: TaxCharge, *, sequence: int) -> Event:
    """The ledger line for one charge: cash out, on the date the income arrived.

    Dated with the income it taxes rather than with a payment date. When the liability is
    actually settled is a timing question this feature does not model, and dating the
    charge to an invented payment date would put a fabricated date in the audit trail.
    ``charged_for_year`` on the charge records the year the liability accrues to, which is
    the fact a later feature needs.

    A charge of zero still becomes an event. It moves no cash, and it is the record that
    the exemption was applied -- traceable to its class and its citation like any other
    figure (FR-003, C6).
    """
    return Event(
        sequence=sequence,
        occurred_on=taxed.occurred_on,
        kind=EventKind.TAX_CHARGE,
        amount=money.scale(charge.total, -1.0),
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
