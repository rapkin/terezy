"""A taxation scheme: the declared set of charges an income stream is under.

The stream-side counterpart of feature 006's instrument tax classes, and the thing feature
002's ``IncomeStream.income_tax_rate`` could not be. A scalar cannot carry two components
with different commencement dates, an obligation triggered by a month rather than by income,
or the choice of a whole scheme -- and which scheme applies is a **declaration**, so it may
not be a branch in here (Principle II).

## Nothing in this module knows what it is charging

A scheme charges exactly the components it declares; a destination's verdict is a declared
word from a closed set; a reading recognises income on a date whose *name* is declared and
whose *value* the caller supplies. That is what makes a second scheme, a moved verdict and a
legislated rate change data-only changes.

Both halves are asserted rather than promised here: no declared id reaches this file's
executable source (``tests/contract/test_no_scheme_is_named_in_code.py``), and renaming every
declared date name changes no figure (``tests/contract/test_scheme_data_only.py``) -- the
second because the shipped date names are ordinary English words, which a source scan would
find in refusal messages rather than in branches.

## Why this is a second charge record and not a generalised ``TaxCharge``

:class:`terezy.core.tax.interface.TaxCharge` has exactly two lines, named ``pit`` and
``levy``, because that is what a tax *class* charges on an *instrument's* income. A єдиний
податок is neither, and writing one into a field named personal income tax is a
mislabelling no downstream reader could detect (012 FR-006).

Generalising that record instead would reach everything that folds one, for a feature that
assembles no annual liability at all. **The seam that would force the merge**: an income
stream that has to be netted into one annual liability beside instrument charges. 012 FR-004
puts that out of scope -- this module records a liability against the period it accrues to
and models no payment, no filing and no cash movement.

## Three roles, and the two this module keeps apart

The base is struck in the **tax** currency, at the official rate for the credit date, through
:func:`terezy.core.tax.official_rate.strike_base` called unchanged. The hryvnia the owner
actually receives comes from a channel on the sale date and is not computed here at all --
:func:`base_versus_received` takes it as an argument. Nothing here imports ``core.routes`` or
reads a ``reference_rate``, asserted over this file's executable source in
``tests/worked_examples/test_base_versus_received.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from enum import Enum
from typing import Literal

from terezy.core.primitives import money, periods
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.periods import Window
from terezy.core.primitives.provenance import Provenance
from terezy.core.tax.official_rate import (
    OfficialRateSeries,
    OfficialRateSeriesUnavailable,
    OfficialRateUnavailable,
    TaxCurrencyConversion,
    strike_base,
)

Period = Literal["month"]
"""The periods a periodic component can be owed per.

**One member, and the reason it is one is worth stating**: ``core.primitives.periods``
enumerates calendar months and nothing else. A ``"quarter"`` would need period arithmetic
that does not exist, so declaring one would be a *code* change wearing a data change's
clothes -- and Principle II's data-only promise would be false for a scheme nobody could run.
The obligation this feature actually models, ЄСВ, is monthly.
"""

DeclaredFor = Literal["stream", "reading"]
"""Whether an income stream may name this scheme, or only a reading of an unsettled question.

The personal-income rates exist here **only** inside a labelled what-if. No personal-income
stream is modelled, and a stream naming such a scheme is refused where the file can be named
(012 FR-010a, FR-026).
"""


class Verdict(Enum):
    """How settled the treatment of a crediting destination is, in feature 009's vocabulary.

    Two members, not three. 009 defines SETTLED, INTERPRETED and UNSETTLED as levels of
    *source quality*; nothing this feature reaches is settled, and a settled destination
    would produce the same charge an interpreted one does. A member nothing constructs is a
    member whose behaviour has never been executed.
    """

    INTERPRETED = "interpreted"
    """Answered an inference deep from provisions a reader can go and check. Produces a charge."""

    UNSETTLED = "unsettled"
    """No authoritative answer. Produces a labelled switch, and never the tax owed."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ComponentRate:
    """One dated rate for one rate component, on whose word it is that rate.

    Provenance is per entry, for feature 006's reason: the rate before a legislated change
    and the rate after it are two observations, and one may be verified while the other is
    not. This feature's own levy is the sharpest case in the repository -- its rate, its
    commencement and its termination come from three different statutes.
    """

    effective_from: date
    """Inclusive, and exactly the date this entry's citation attests."""

    rate: float
    """A fraction of the base, not a percentage. The ``_pct`` fields live in declaration files."""

    provenance: Provenance


@dataclass(frozen=True, slots=True, kw_only=True)
class ComponentAmount:
    """One dated statutory sum for one periodic component.

    Money, not a rate. There is no ``rate`` field here and no ``amount`` field on
    :class:`ComponentRate`, so the confusion FR-019 forbids cannot be spelled.
    """

    effective_from: date
    amount: Money
    provenance: Provenance


@dataclass(frozen=True, slots=True, kw_only=True)
class DeclaredContext:
    """A cited fact recorded on a component and deliberately **not** applied.

    A schedule that declares a commencement and nothing else asserts a permanent charge, and
    the charge this feature models is not permanent: it ends on a date conditioned on an
    event nothing in this system models. Recording the provision as declared, cited data --
    visible, and not applied -- is what stops the absence of an end date reading as a claim
    that there is no end (012 FR-008a).

    A comment could not do this: it cannot be rendered beside the figure it does not move.
    """

    id: str
    statement: str
    """The provision, in its own words."""

    not_applied_because: str
    """Required, so the omission can never be read as an oversight."""

    provenance: Provenance


@dataclass(frozen=True, slots=True, kw_only=True)
class RateComponent:
    """One separately named charge levied as a rate on the base."""

    id: str
    """The handle a declaration refers to."""

    name: str
    """The name the law uses for it, which is what an output reports (012 FR-006)."""

    schedule: tuple[ComponentRate, ...]
    """Non-empty, strictly ascending by ``effective_from``; both enforced at the loader."""

    context: tuple[DeclaredContext, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class PeriodicComponent:
    """One separately named charge owed per elapsed period, whatever the income was.

    Two things differ from a rate component and they are independent: the **trigger** is a
    period elapsing rather than income arriving, and the **base** is a statutory sum rather
    than a percentage of anything. A rate-shaped model is wrong the first period income is
    zero, which is the case :func:`charge_periods` exists to get right.
    """

    id: str
    name: str
    period: Period
    schedule: tuple[ComponentAmount, ...]
    context: tuple[DeclaredContext, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class TaxationScheme:
    """A declared, identified treatment an income stream can name.

    **What this scheme charges is exactly what it declares.** That is the whole of how one
    scheme charges a contribution and another charges none without a rule anywhere deciding
    between them, and it is why a nil is a property of a declaration rather than the output
    of an exemption the engine evaluated (012 FR-001, FR-020, FR-021).
    """

    id: str
    name: str
    jurisdiction_id: str
    tax_currency: Currency
    """The currency the base is struck in. Principle VI's tax role, and not the display one."""

    variant: str
    """Which of the law's alternative rate sets this declaration is (012 FR-002).

    Named even where a scheme has one variant, so the second is a file rather than a schema
    change the day its rate is cited.
    """

    reporting_cadence: str
    """Declared and unused. This feature records a liability against the period it accrues to
    and models no payment timing, no filing deadline and no cash movement (012 FR-004)."""

    declared_for: DeclaredFor
    rate_components: tuple[RateComponent, ...]
    periodic_components: tuple[PeriodicComponent, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ComponentCharge:
    """One component's line on one base: what was charged, at what rate, on whose word."""

    component_id: str
    name: str
    rate: float
    charged: Money
    effective_from: date
    """The entry that supplied the rate, so a reader can find it without re-deriving it."""

    provenance: Provenance


@dataclass(frozen=True, slots=True, kw_only=True)
class SchemeCharge:
    """What one scheme charged on one income event, line by line.

    There is **no combined-rate field anywhere on this record**, which is 012 FR-005 made
    unrepresentable rather than promised: :attr:`total` is a sum of two amounts, and the
    percentage that would produce it in one multiplication is never computed. Two components
    with independent legal lives cannot be unpicked from a blended figure afterwards, and
    these two have independent legal lives -- a different statute created one of them, on its
    own date.
    """

    scheme_id: str
    base: Money
    """What the rates were applied to, in the tax currency."""

    on_date: date
    """The date the rates were read on, and the date the base was struck at."""

    conversion: TaxCurrencyConversion | None
    """011's record of the base being struck, or ``None`` when the arrival was already in the
    tax currency and no rate was consulted (011 FR-009).

    **The foreign arrival is not copied into a field of its own** -- it is
    ``conversion.amount``, beside the rate and the dates that turned it into
    :attr:`base`.
    """

    lines: tuple[ComponentCharge, ...]
    """One line per rate component the scheme declares, in declaration order."""

    total: Money
    provenance: Provenance


@dataclass(frozen=True, slots=True, kw_only=True)
class PeriodicCharge:
    """What one periodic component cost for one elapsed period."""

    scheme_id: str
    component_id: str
    name: str
    period: str
    charged: Money
    effective_from: date
    provenance: Provenance


@dataclass(frozen=True, slots=True, kw_only=True)
class ComponentRateUndeclaredBefore:
    """No entry of this component's schedule is in force on the event's date.

    There is deliberately **no rate on this record**. *"The schedule does not reach this
    date"*, *"the rate was nil"* and *"this scheme charges no such component"* are three
    different claims and only the first is true here, so a caller has nothing to read as a
    number (012 FR-008, 006 FR-012).
    """

    scheme_id: str
    component_id: str
    component_name: str
    on_date: date
    earliest_declared: date
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TaxBaseUnavailable:
    """The base could not be struck in the tax currency, and 011 says why.

    :attr:`unavailable` is carried **whole**: it already names the series, the pair, the date,
    the window it covers and the two remedies, and restating any of those here would be a
    second place for one fact. :attr:`reason` adds only what 011 cannot know -- which scheme
    was charging, and into which currency.
    """

    scheme_id: str
    on_date: date
    amount: Money
    unavailable: OfficialRateUnavailable
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PeriodicAmountNotInForce:
    """A declared periodic component with no amount in force for this period.

    Never a zero, and never a rate on income used as a stand-in: a scheme that declares an
    obligation and cannot say what it costs has a gap in its declaration, and reporting
    nothing owed would answer a question nobody asked (012 FR-021).
    """

    scheme_id: str
    component_id: str
    name: str
    period: str
    earliest_declared: date
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ComponentNotDeclared:
    """This scheme charges no such component at all.

    Distinct from a declared component that charged nothing, and from one declared with
    nothing in force. An omitted component is invisible; this record is what makes it
    visible, and it is the only way the first of SC-011's three nils can be spelled.
    """

    scheme_id: str
    component_id: str
    reason: str


type SchemeChargeRefused = ComponentRateUndeclaredBefore | TaxBaseUnavailable
"""Why no charge could be produced. Each member names its own fix."""

type ComponentStanding = (
    ComponentRate
    | ComponentAmount
    | ComponentNotDeclared
    | ComponentRateUndeclaredBefore
    | PeriodicAmountNotInForce
)
"""What a scheme declares about one component, asked about one date or one period."""


def rate_in_force(component: RateComponent, on_date: date) -> ComponentRate | None:
    """The entry governing ``on_date``: the latest ``effective_from`` on or before it.

    Inclusive at the boundary, and the scan runs backwards so *the last one that applies* is
    the shape of the code rather than a claim in a comment. ``schedule`` is non-empty and
    sorted by the time it leaves the loader, which is where a broken file can be named.
    """
    for entry in reversed(component.schedule):
        if entry.effective_from <= on_date:
            return entry
    return None


def amount_in_force(component: PeriodicComponent, period: str) -> ComponentAmount | None:
    """The entry governing ``period``, comparing the month an ``effective_from`` falls in.

    A statutory sum takes effect on a date and is owed for a period, so the two have to be
    compared in one vocabulary. The period's is the coarser, and it is the one the obligation
    is actually measured in: an amount effective on the 15th governs the month it lands in,
    because the month is the trigger and there is no half-month to charge.
    """
    wanted = periods.ordinal(period)
    for entry in reversed(component.schedule):
        if periods.ordinal(periods.month_of(entry.effective_from)) <= wanted:
            return entry
    return None


def _struck(
    scheme: TaxationScheme, amount: Money, on_date: date, series: OfficialRateSeries | None
) -> tuple[Money, TaxCurrencyConversion | None] | TaxBaseUnavailable:
    """The base in the tax currency, and the conversion that produced it.

    The currency check comes **first**, because ``strike_base`` raises on an amount that
    needs no rate: an event already in the tax currency must not consult a series at all, and
    a false rate-unavailable reason attached to such a figure would train a reader to ignore
    true ones (011 FR-009).
    """
    if amount.currency is scheme.tax_currency:
        return amount, None
    if series is None:
        return TaxBaseUnavailable(
            scheme_id=scheme.id,
            on_date=on_date,
            amount=amount,
            unavailable=OfficialRateSeriesUnavailable(
                wanted=(scheme.tax_currency, amount.currency),
                series_id=None,
                quotes=None,
                reason=(
                    f"jurisdiction {scheme.jurisdiction_id!r} declares no official-rate series, "
                    f"so an amount in {amount.currency.value} has no base in "
                    f"{scheme.tax_currency.value}. Declare a series quoting the pair and name it "
                    "from the jurisdiction's timing declaration."
                ),
            ),
            reason=_base_reason(scheme, amount, on_date),
        )
    struck = strike_base(amount, series, tax_currency=scheme.tax_currency, on_date=on_date)
    if isinstance(struck, TaxCurrencyConversion):
        return struck.base, struck
    return TaxBaseUnavailable(
        scheme_id=scheme.id,
        on_date=on_date,
        amount=amount,
        unavailable=struck,
        reason=_base_reason(scheme, amount, on_date),
    )


def _base_reason(scheme: TaxationScheme, amount: Money, on_date: date) -> str:
    return (
        f"scheme {scheme.id!r} charges on a base in {scheme.tax_currency.value}, and the "
        f"{amount.currency.value} credited on {on_date.isoformat()} could not be struck into "
        "one. No charge is produced and no rate is borrowed from another date; the reason "
        "carried here names what would close it."
    )


def charge_income(
    scheme: TaxationScheme,
    amount: Money,
    *,
    on_date: date,
    series: OfficialRateSeries | None,
) -> SchemeCharge | SchemeChargeRefused:
    """Charge every rate component this scheme declares, on one base struck at ``on_date``.

    ``on_date`` is the date the income is **credited**, and it is an argument because it is
    the caller's fact: there is no clock here, no ledger event to read a date off, and the
    date the money is credited is not the date it is later sold on.

    **The component schedules are read before the base is struck.** Both can fail on the same
    date and only one is the reader's next move: a rate for a date the law did not charge on
    is a value nobody needs to go and find.

    Every line goes through ``money.scale_sourced`` with the **entry's** provenance, so the
    charge cites the entry that produced it and an unverified rate marks the figure. The
    total is a sum of the lines and never a combined rate applied once.
    """
    in_force: list[tuple[RateComponent, ComponentRate]] = []
    for component in scheme.rate_components:
        entry = rate_in_force(component, on_date)
        if entry is None:
            return _rate_not_in_force(scheme, component, on_date)
        in_force.append((component, entry))

    struck = _struck(scheme, amount, on_date, series)
    if isinstance(struck, TaxBaseUnavailable):
        return struck
    base, conversion = struck

    charges = tuple(
        ComponentCharge(
            component_id=component.id,
            name=component.name,
            rate=entry.rate,
            charged=money.scale_sourced(base, entry.rate, entry.provenance),
            effective_from=entry.effective_from,
            provenance=entry.provenance,
        )
        for component, entry in in_force
    )
    return SchemeCharge(
        scheme_id=scheme.id,
        base=base,
        on_date=on_date,
        conversion=conversion,
        lines=charges,
        total=money.total([line.charged for line in charges], base.currency),
        provenance=prov.merge_all([base.provenance, *(line.provenance for line in charges)]),
    )


def _rate_not_in_force(
    scheme: TaxationScheme, component: RateComponent, on_date: date
) -> ComponentRateUndeclaredBefore:
    """The refusal both the charge and the standing return, built in one place.

    Two copies would be two refusal messages for one situation, and the reader would have no
    way to tell which of them fired.
    """
    earliest = component.schedule[0].effective_from
    return ComponentRateUndeclaredBefore(
        scheme_id=scheme.id,
        component_id=component.id,
        component_name=component.name,
        on_date=on_date,
        earliest_declared=earliest,
        reason=(
            f"component {component.id!r} of scheme {scheme.id!r} does not reach "
            f"{on_date.isoformat()}: its earliest entry takes effect {earliest.isoformat()}. "
            "Refused rather than charged at zero or at the earliest rate -- 'the schedule "
            "does not reach this date', 'the rate was nil' and 'this scheme charges no such "
            "component' are three claims and only the first is true here. Find a source for "
            "the rate in force on the event's date and add it as a dated entry."
        ),
    )


def _not_in_force(
    scheme: TaxationScheme, component: PeriodicComponent, period: str
) -> PeriodicAmountNotInForce:
    """The refusal both the charge and the standing return, built in one place."""
    earliest = component.schedule[0].effective_from
    return PeriodicAmountNotInForce(
        scheme_id=scheme.id,
        component_id=component.id,
        name=component.name,
        period=period,
        earliest_declared=earliest,
        reason=(
            f"component {component.id!r} of scheme {scheme.id!r} declares no amount in force "
            f"for {period}: its earliest entry takes effect {earliest.isoformat()}. Refused "
            "rather than charged at zero -- never a zero, and never a rate on income used as "
            "a stand-in for a sum nobody declared."
        ),
    )


def charge_period(
    scheme: TaxationScheme, component: PeriodicComponent, period: str
) -> PeriodicCharge | PeriodicAmountNotInForce:
    """What ``component`` costs for one elapsed ``period``, whatever the income was.

    No income reaches this function, which is the property that distinguishes a periodic
    obligation from a rate: it is owed in a month with nothing in it.
    """
    entry = amount_in_force(component, period)
    if entry is None:
        return _not_in_force(scheme, component, period)
    return PeriodicCharge(
        scheme_id=scheme.id,
        component_id=component.id,
        name=component.name,
        period=period,
        charged=entry.amount,
        effective_from=entry.effective_from,
        provenance=entry.provenance,
    )


def charge_periods(
    scheme: TaxationScheme, window: Window
) -> tuple[PeriodicCharge | PeriodicAmountNotInForce, ...]:
    """Every periodic component charged once per month of ``window``, in period order.

    A scheme declaring none produces an empty tuple, which is the true answer and not an
    absence: :func:`component_standing` is where *this scheme charges no such component* is
    asked and answered by name.
    """
    return tuple(
        charge_period(scheme, component, period)
        for period in periods.months_in(window)
        for component in scheme.periodic_components
    )


def component_standing(
    scheme: TaxationScheme,
    component_id: str,
    *,
    on_date: date | None = None,
    period: str | None = None,
) -> ComponentStanding:
    """What ``scheme`` declares about one component, and whether anything is in force.

    Answers *what is declared*, where the charge functions answer *what was charged*. Keeping
    the two questions apart is what lets this one be asked about a component the scheme never
    mentions -- the state that has no charge to look at, and the one an output would
    otherwise report as an absence (012 FR-020).

    A rate component is asked about a date and a periodic one about a period; asking the
    wrong one is a programmer error and raises, because a period is not a date and silently
    accepting either would be the defaulting this whole module refuses.
    """
    for rate_component in scheme.rate_components:
        if rate_component.id == component_id:
            if on_date is None:
                raise ValueError(
                    f"component {component_id!r} of scheme {scheme.id!r} is a rate component "
                    "and is in force on a date, not for a period. Pass on_date."
                )
            entry = rate_in_force(rate_component, on_date)
            if entry is not None:
                return entry
            return _rate_not_in_force(scheme, rate_component, on_date)
    for periodic in scheme.periodic_components:
        if periodic.id == component_id:
            if period is None:
                raise ValueError(
                    f"component {component_id!r} of scheme {scheme.id!r} is a periodic "
                    "component and is owed per period, not on a date. Pass period."
                )
            amount = amount_in_force(periodic, period)
            if amount is not None:
                return amount
            return _not_in_force(scheme, periodic, period)
    return ComponentNotDeclared(
        scheme_id=scheme.id,
        component_id=component_id,
        reason=(
            f"scheme {scheme.id!r} charges no such component as {component_id!r}. That is a "
            "property of what this scheme declares, not a zero the engine chose and not an "
            "absence in the output: a scheme charges exactly the components it declares."
        ),
    )


NOT_THE_TAX_OWED = (
    "This figure is not the tax owed. It is what one reading of an unsettled question would "
    "produce; nothing numbered answers the question, so no reading here may be presented as "
    "the liability, and no output may report a number combining this figure with another."
)
"""The label every what-if carries, written once and copied onto each figure that needs it.

Written into the figure rather than derived at a call site, so a figure lifted out of the
switch still carries the claim -- the label belongs to the figure, not to the slot it was
sitting in.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class Reading:
    """One candidate treatment at a crediting destination.

    Declares **exactly one** of :attr:`scheme_id` and :attr:`uncomputable_because`, checked
    where the file can be named. The obvious alternative -- naming a scheme nobody declared
    -- collides with the standing rule that an unresolvable reference fails at load, and
    weakening that rule for this one case would weaken it for the cases it exists for.
    """

    id: str
    label: str
    """Which reading this is, in the words a reader will see beside the figure."""

    scheme_id: str | None
    uncomputable_because: str | None
    """Why this candidate cannot be computed: a treatment needing a rate nobody declared is
    not computable here and MUST NOT be computed -- and is also not thereby invisible."""

    recognised_on: str | None
    """The **name** of the date this reading recognises income on, present exactly when
    :attr:`scheme_id` is.

    A name, not a date: two readings of one destination can disagree about *when* income
    arises, and the caller supplies what each name is worth. Nothing here compares the name
    against a literal, which is what keeps a second date name a data-only addition.
    """

    departs_from_source: str | None
    """Where this system deliberately computes something other than what the source computes.

    Declared beside the reading and rendered on the figure, because a departure nothing
    reports is a departure that becomes a silent absorption.
    """

    provenance: Provenance


@dataclass(frozen=True, slots=True, kw_only=True)
class CreditingDestination:
    """One row of a normative table: what a scheme's income is worth, credited here.

    :attr:`grounds` is the row's recorded judgement. Deciding whether a source's proposition
    *reaches* a destination is not mechanical, and this field is where that judgement lives
    once, in a file, rather than in prose that has to be kept in step with four other places.
    """

    scheme_id: str
    venue_id: str
    verdict: Verdict
    grounds: str
    resolution_path: str
    """What closes the question. For an unsettled row it is what the reader must go and get."""

    readings: tuple[Reading, ...]
    provenance: Provenance


@dataclass(frozen=True, slots=True, kw_only=True)
class ChargedUnderTheScheme:
    """The tax owed, at a destination whose treatment is answered.

    Unrelated by type to :class:`ReadingFigure`, so neither can be assigned into the other's
    slot without a strict-typing error -- the trade ``OneWayCost`` and ``RoundTripCost``
    make, for the same reason.
    """

    venue_id: str
    scheme_id: str
    reading_id: str
    charge: SchemeCharge
    grounds: str
    provenance: Provenance


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadingFigure:
    """One labelled what-if on an unsettled destination's switch."""

    reading_id: str
    label: str
    scheme_id: str
    recognised_on: str
    charge: SchemeCharge
    departs_from_source: str | None
    not_the_tax_owed: str
    provenance: Provenance


@dataclass(frozen=True, slots=True, kw_only=True)
class UncomputableCandidate:
    """A candidate named on the switch and not computed, with the reason it cannot be."""

    reading_id: str
    label: str
    because: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UnsettledDestination:
    """A labelled scenario switch: one figure per computable reading, and nothing combined.

    **There is no total, no mean, no range and no money on this record at all.** A blended
    number would need somewhere to live and there is nowhere, which is the prohibition made
    unrepresentable rather than promised.

    A switch of zero figures is never built: where nothing is computable the destination
    refuses instead, and the uncomputable candidates are named in the refusal.
    """

    venue_id: str
    scheme_id: str
    grounds: str
    resolution_path: str
    figures: tuple[ReadingFigure, ...]
    uncomputable: tuple[UncomputableCandidate, ...]


class RefusedState(Enum):
    """Which of a refusal's situations obtains, because they close differently.

    **Two members where 012 FR-027 names three states, and the gap is deliberate.** The
    engine can see that the table has no row and that a row's every candidate is
    uncomputable. It cannot see the difference between *no source reaches this destination*
    and *a source reaches it and the table has not caught it*: that is a fact about the world
    rather than about the data, and 012 SC-013 records it as a reader's determination. So the
    first member covers both, and its reason names both closures rather than asserting which
    obtains.
    """

    NO_DECLARED_JUDGEMENT = "no_declared_judgement"
    NO_CANDIDATE_IS_COMPUTABLE = "no_candidate_is_computable"


@dataclass(frozen=True, slots=True, kw_only=True)
class CreditingDestinationRefused:
    """No reading could be produced for this destination under this scheme."""

    venue_id: str
    scheme_id: str
    state: RefusedState
    uncomputable: tuple[UncomputableCandidate, ...]
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadingDateUndeclared:
    """A reading recognises income on a date name the caller supplied no date for."""

    scheme_id: str
    reading_id: str
    recognised_on: str
    declared: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadingRefused:
    """A computable reading could not be computed, so the whole destination refuses.

    Distinct from :class:`UncomputableCandidate`, which is a candidate no declaration can
    compute and which is *named on a switch that still stands*. This is a missing rate, a
    missing observation or a missing date -- all of them fixable, and none of them a reason
    to publish a switch one figure short. A switch that quietly dropped a reading is the
    defect the *named on the switch* clause exists to prevent, wearing its clothes.
    """

    venue_id: str
    scheme_id: str
    reading_id: str
    label: str
    because: SchemeChargeRefused | ReadingDateUndeclared
    reason: str


type DestinationRefused = CreditingDestinationRefused | ReadingRefused
type DestinationOutcome = ChargedUnderTheScheme | UnsettledDestination | DestinationRefused


def _figure(
    destination: CreditingDestination,
    reading: Reading,
    *,
    amount: Money,
    on_dates: Mapping[str, date],
    schemes: Mapping[str, TaxationScheme],
    series: OfficialRateSeries | None,
) -> ReadingFigure | ReadingRefused:
    """One reading computed, or the reason it could not be — never silently dropped."""
    assert reading.scheme_id is not None
    assert reading.recognised_on is not None
    on_date = on_dates.get(reading.recognised_on)
    if on_date is None:
        return ReadingRefused(
            venue_id=destination.venue_id,
            scheme_id=destination.scheme_id,
            reading_id=reading.id,
            label=reading.label,
            because=ReadingDateUndeclared(
                scheme_id=destination.scheme_id,
                reading_id=reading.id,
                recognised_on=reading.recognised_on,
                declared=tuple(sorted(on_dates)),
                reason=(
                    f"reading {reading.id!r} recognises income on the declared date "
                    f"{reading.recognised_on!r} and no such date was supplied. Refused rather "
                    "than computed on another reading's date: the date is what this reading "
                    "disagrees about, so borrowing one would compute the reading it contests."
                ),
            ),
            reason=_reading_reason(destination, reading),
        )
    charge = charge_income(schemes[reading.scheme_id], amount, on_date=on_date, series=series)
    if not isinstance(charge, SchemeCharge):
        return ReadingRefused(
            venue_id=destination.venue_id,
            scheme_id=destination.scheme_id,
            reading_id=reading.id,
            label=reading.label,
            because=charge,
            reason=_reading_reason(destination, reading),
        )
    rests_on = prov.merge(reading.provenance, destination.provenance)
    return ReadingFigure(
        reading_id=reading.id,
        label=reading.label,
        scheme_id=reading.scheme_id,
        recognised_on=reading.recognised_on,
        charge=_resting_on(charge, rests_on),
        departs_from_source=reading.departs_from_source,
        not_the_tax_owed=NOT_THE_TAX_OWED,
        provenance=rests_on,
    )


def _resting_on(charge: SchemeCharge, sources: Provenance) -> SchemeCharge:
    """The same charge, with the declaration that selected it merged into every amount.

    A reading and the row it sits in decide **which** rates strike this figure without
    multiplying it, so their marks reach the money only if they are put there. Leaving them
    on the record's ``provenance`` field alone would leave the amounts looking checked while
    the judgement behind them was not -- the shape ``tax.year`` uses ``money.also_resting_on``
    for, applied to the same problem here.
    """
    return replace(
        charge,
        base=money.also_resting_on(charge.base, sources),
        lines=tuple(
            replace(line, charged=money.also_resting_on(line.charged, sources))
            for line in charge.lines
        ),
        total=money.also_resting_on(charge.total, sources),
        provenance=prov.merge(charge.provenance, sources),
    )


def _reading_reason(destination: CreditingDestination, reading: Reading) -> str:
    return (
        f"reading {reading.id!r} of {destination.venue_id!r} under scheme "
        f"{destination.scheme_id!r} could not be computed, so no result is reported for the "
        "destination at all. A switch short of one of its readings reads as complete when it "
        "is not, which is the one thing a labelled switch may never do."
    )


def apply(
    *,
    scheme_id: str,
    credited_to: str,
    amount: Money,
    on_dates: Mapping[str, date],
    schemes: Mapping[str, TaxationScheme],
    destinations: Mapping[tuple[str, str], CreditingDestination],
    series: OfficialRateSeries | None,
) -> DestinationOutcome:
    """What ``amount`` is worth under ``scheme_id``, credited at ``credited_to``.

    ``credited_to`` is a **crediting destination** -- the tax event's location -- and not a
    route's destination. The two are different declared facts (012 FR-024a), and the
    parameter is named for the stream field it comes from so that
    ``tests/contract/test_per_destination_cost_unrepresentable.py``'s scan does not read a
    tax charge as an access cost; that module records the boundary from its own side.

    ``on_dates`` maps **declared date names** to dates. Two readings of one destination can
    disagree about when income arises, so a single date argument could not express the
    question; nothing here knows any of the names.

    Three outcomes, and which one is reached is decided by the row's declared verdict and by
    what its readings can compute -- never by the destination, the scheme or a component.
    """
    destination = destinations.get((scheme_id, credited_to))
    if destination is None:
        return CreditingDestinationRefused(
            venue_id=credited_to,
            scheme_id=scheme_id,
            state=RefusedState.NO_DECLARED_JUDGEMENT,
            uncomputable=(),
            reason=(
                f"no declared row records how income under scheme {scheme_id!r} credited at "
                f"{credited_to!r} is treated, so nothing is charged and nothing is estimated. "
                "Two things close this and they are different: find a source that reaches "
                "the destination, and add the row with its reasoning. Where a source already "
                "exists and the table has simply not caught it, only the second is needed."
            ),
        )

    figures: list[ReadingFigure] = []
    uncomputable: list[UncomputableCandidate] = []
    for reading in destination.readings:
        if reading.uncomputable_because is not None:
            uncomputable.append(
                UncomputableCandidate(
                    reading_id=reading.id,
                    label=reading.label,
                    because=reading.uncomputable_because,
                )
            )
            continue
        computed = _figure(
            destination,
            reading,
            amount=amount,
            on_dates=on_dates,
            schemes=schemes,
            series=series,
        )
        if isinstance(computed, ReadingRefused):
            return computed
        figures.append(computed)

    if not figures:
        return CreditingDestinationRefused(
            venue_id=credited_to,
            scheme_id=scheme_id,
            state=RefusedState.NO_CANDIDATE_IS_COMPUTABLE,
            uncomputable=tuple(uncomputable),
            reason=(
                f"every candidate treatment declared for {credited_to!r} under scheme "
                f"{scheme_id!r} needs rates no declaration carries, so there is nothing to "
                "compute. A switch of zero figures is not a switch: the candidates are named "
                "here instead. It closes by declaring the missing scheme with its rates cited."
            ),
        )

    if destination.verdict is Verdict.INTERPRETED:
        if len(figures) != 1 or uncomputable:
            raise ValueError(
                f"destination {credited_to!r} under scheme {scheme_id!r} is declared "
                "INTERPRETED "
                "and carries more than one candidate. An interpreted row is a charge, and a "
                "charge cannot be two figures; the loader refuses such a row, so reaching "
                "here means that check was bypassed."
            )
        only = figures[0]
        return ChargedUnderTheScheme(
            venue_id=credited_to,
            scheme_id=scheme_id,
            reading_id=only.reading_id,
            charge=only.charge,
            grounds=destination.grounds,
            provenance=prov.merge(only.provenance, only.charge.provenance),
        )

    return UnsettledDestination(
        venue_id=credited_to,
        scheme_id=scheme_id,
        grounds=destination.grounds,
        resolution_path=destination.resolution_path,
        figures=tuple(figures),
        uncomputable=tuple(uncomputable),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class BaseVersusReceived:
    """The hryvnia the base implies against the hryvnia the sale produced.

    Two figures, one subtraction, and no netting: the base was fixed at the credit date and
    nothing about the sale moves it. :attr:`difference` is **signed**, because the exposure
    points either way -- the base can exceed what he has or fall short of it -- and an
    absolute value would hide which.
    """

    base: Money
    received: Money
    difference: Money
    outside_the_base: str


OUTSIDE_THE_BASE = (
    "Not part of the taxable base. The base is the credited amount at the official rate on "
    "the credit date; this is the gap against what a declared channel actually produced on "
    "the sale date, and no deduction is claimed for it."
)


def base_versus_received(base: Money, received: Money) -> BaseVersusReceived:
    """Report both figures and their signed difference, labelled as outside the base.

    Takes two amounts rather than a costed route: the received figure comes from the existing
    costing path and this feature adds no mechanism to produce it. Passing the cost record in
    would put a channel one import away from a tax base, which is the direction
    ``no-tax-base-from-a-channel`` exists to keep shut.
    """
    return BaseVersusReceived(
        base=base,
        received=received,
        difference=money.sub(base, received),
        outside_the_base=OUTSIDE_THE_BASE,
    )
