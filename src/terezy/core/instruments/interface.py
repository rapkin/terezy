"""The ``Instrument`` plugin interface: function signatures gathered into a record.

One of the four plugin interfaces permitted by constitution Principle II. Per owner
decision D-E it is a **set of function signatures**, not a class: there is no base class
to inherit, no protocol to implement, and nothing to construct. An instrument kind is a
frozen record of three functions, and dispatch is a mapping
(``terezy.core.instruments.registry``).

⚙ **What this interface covers is a projection that produces a stream of ledger events.**
That is not every declared instrument: a collective-investment fund
(``terezy.core.instruments.fund``) is a declared kind whose projection returns a result
record instead -- and, for a fund stating a range, two of them. It is therefore not in
``registry.REGISTRY`` and does not implement :class:`InstrumentOps`. See that module's
section comment for the three mismatches and for why widening this signature to cover both
was rejected.

This module also defines the records those functions take and return, because they are
the vocabulary of the interface and splitting them into a fourth module would only add a
file to import. They divide into two kinds, and the division is Principle VII's:

* **Curated, shared declarations** -- ``BondTerms``, ``InstrumentConstraints``,
  ``InstrumentDeclaration``. Version-controlled domain knowledge, loaded from
  ``data/instruments/`` by the ``data`` layer, identical for every owner.
* **Per-owner input** -- ``Holding``, ``DateRange``, ``Assumptions``. What *this* owner
  bought, over what horizon, under what modelling choices.

They are deliberately separate records rather than one: a ``Holding`` that embedded its
declaration would put curated data inside per-user data, and the boundary between the
two is what makes multi-user cheap later.

**Why ``events`` takes the declaration explicitly.** The contract in
``specs/001-ovdp-hurdle-rate/contracts/instrument-interface.md`` writes the signature as
``(Holding, DateRange, Assumptions)``, and that does not typecheck: a schedule cannot be
computed from a holding that knows only an instrument *id*. The choices were to embed the
declaration in the holding -- which crosses the boundary above -- or to pass it. It is
passed. The same applies to ``tax_classes`` and ``constraints``, which the contract wrote
as zero-argument functions; a module of free functions has nothing to close over, so the
declaration is their argument too.

**Purity is part of the interface.** Every function here is a pure function of its
arguments: no I/O, no clock, no randomness. Called twice with equal arguments it returns
equal results, which is what makes determinism (C4) achievable at all.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Final

from terezy.core.errors import InstrumentFailure
from terezy.core.ledger.events import Event, EventKind
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.tax.interface import TaxableEventKind


@dataclass(frozen=True, slots=True)
class BondTerms:
    """The contractual terms a fixed-income schedule is computed from, in closed form."""

    face_value: Money
    """Redemption amount **per unit**. Positive; validated at the data boundary.

    Per unit rather than per holding: the holding says how many units, and keeping the
    two apart is what lets one declaration serve purchases of any size.
    """

    coupon_rate: float
    """Annual coupon as a **fraction** of face -- ``0.155``, never ``15.5``.

    Percent lives only in declaration files, where the ``_pct`` suffix names it, and is
    divided by 100 exactly once at the data boundary. Zero is valid: it is a
    zero-coupon bond, not a missing rate.
    """

    issue_date: date
    """When the instrument started accruing. The anchor of the first accrual period."""

    maturity_date: date
    """When the principal is repaid. Strictly after :attr:`issue_date`, else the
    instrument returns ``InconsistentTerms`` rather than an empty schedule."""

    periodicity: str
    """A key of ``conventions.PERIODICITY_FNS`` -- how often a coupon is paid."""

    day_count: str
    """A key of ``conventions.DAY_COUNT_FNS`` -- how an accrual period becomes a
    fraction of a year, and therefore how large each coupon is."""

    business_day_rule: str
    """A key of ``conventions.BUSINESS_DAY_FNS`` -- where a payment lands when its
    scheduled date is not a business day. Applied to the payment date only; accrual is
    measured on the unadjusted dates."""

    provenance: Provenance
    """The sources these terms rest on. Reaches every amount derived from them."""


# ---------------------------------------------------------------------------
# 013-enumerated-schedule: the second thing a declaration can say about a bond
# ---------------------------------------------------------------------------
#
# ⚙ **Two epistemic situations, not two encodings of one.** `BondTerms` says *I know this
# issue's full terms*, and every figure derived from it is checkable on paper against the
# contract. `EnumeratedTerms` says *I am buying a stream of dated payments on the secondary
# market; the issue's history is neither known to me nor relevant to what I will receive*.
#
# The fact that forced the second record is the **issue date**. The endpoint that publishes
# the 32 real OVDP schedules gives a list of dated amounts and no issue date, and no issue
# date is derivable from one: extrapolating one backwards would be inventing a legal fact
# about a state security, which Principle I forbids outright and which is invisible once
# made -- a plausible date produces a plausible schedule and nothing ever contradicts it.
# The issue date affects **no future cash flow of a purchase made today**, so a form that
# demanded one would be forcing an invention that changes no figure.


class PaymentKind(Enum):
    """What one enumerated payment is, from a closed set. Never inferred (FR-008).

    The ``value`` strings are the data contract a declaration file writes.
    """

    COUPON = "coupon"
    """A contractual interest payment. Cash in; it touches no lot."""

    PRINCIPAL_REPAYMENT = "principal_repayment"
    """A repayment of principal: cash in against units surrendered.

    A disposal, like the generative form's redemption -- it consumes basis and realises a
    gain or a loss. Treating it as a cash receipt would tax the owner's own money back.
    """


PAYMENT_KINDS: Final[Mapping[PaymentKind, tuple[EventKind, TaxableEventKind]]] = {
    PaymentKind.COUPON: (EventKind.COUPON, TaxableEventKind.COUPON),
    PaymentKind.PRINCIPAL_REPAYMENT: (
        EventKind.PRINCIPAL_REPAYMENT,
        TaxableEventKind.DISPOSAL_GAIN,
    ),
}
"""What each declared label settles: the ledger movement, and the income kind assessed.

**One mapping, not two**, and that is FR-007's requirement rather than a convenience. Those
are already two distinct vocabularies in this engine -- `EventKind` says what *moved*,
`TaxableEventKind` says what a tax class can speak *about* -- and a payment whose two halves
disagreed would change no figure on the instruments that motivate this feature, because both
OVDP income kinds are exempt. That is luck rather than design, and it is exactly the
condition under which a defect ships (FR-010).
"""


@dataclass(frozen=True, slots=True)
class ScheduledPayment:
    """One dated, per-unit amount with a declared kind. The unit of an enumerated schedule.

    Two of these on one date with different kinds is the normal end of a bond -- the final
    coupon and the principal repayment -- and 31 of the 32 observed issues are shaped that
    way. They are never merged, deduplicated or summed into one row.
    """

    on: date
    """The date money changes hands. Not adjusted by anything: no business-day rule is
    declared, because none was applied to a payment somebody has already published."""

    amount: Money
    """The payment **per unit**, in the instrument's currency, in its major units.

    Per unit for the reason `BondTerms.face_value` is: the holding says how many units, and
    keeping the two apart is what lets one declaration serve purchases of any size. The
    engine performs **no unit scaling** of a declared amount (FR-004) -- a figure published
    in kopecks is converted when it is transcribed, and the conversion is recorded there as
    an inference rather than performed here as a division that looks like plumbing.

    Carries its own provenance, as every `Money` does, so a payment's mark reaches every
    figure derived from it without a second mechanism.
    """

    pays: PaymentKind
    """Declared, never read off the amount, the date or the position in the list (FR-008).

    ``8305, 8305, 8305, 100000`` is obviously three coupons and a principal repayment to a
    human and obviously nothing at all to a machine, and the endpoint does not label them.
    """


@dataclass(frozen=True, slots=True)
class EnumeratedTerms:
    """A bond declared as the payments it will make, for a buyer who knows only those.

    **What is absent is absent by construction**: no issue date, no coupon rate, no
    periodicity, no business-day rule and no maturity date. FR-003 forbids them rather than
    making them optional, because an accepted-and-ignored field is worse than a missing one
    and each of these would be either invented or unread. There is nowhere here to put one.
    """

    face_value: Money
    """Redemption amount **per unit**. Positive.

    A redemption amount and nothing else. It is deliberately **not** a price: for a
    generative bond, face is the price at which a unit earns the issue's declared rate, and
    an enumerated instrument declares no rate (FR-015).
    """

    covers_from: date
    """The date from which this list is complete, to the end of the instrument's life.

    **One-ended by construction** (FR-005). There is no closing field, so a schedule
    truncated at the far end is an unrepresentable state rather than a silently short
    projection. The claim is the transcriber's and it is cited: the endpoint states no
    window, and the window it in fact publishes is not uniform.
    """

    payments: tuple[ScheduledPayment, ...]
    """Every payment, in ascending date order, none before :attr:`covers_from`."""

    day_count: str
    """A key of ``conventions.DAY_COUNT_FNS``. Required, and **not** an exception to FR-003.

    The distinction a reader has to be able to make: the forbidden five are terms of the
    **issue** -- they describe the paper. A day count is a convention of **computation** --
    it describes how *we* turn a span of days into a fraction of a year in order to
    annualise. Nothing about the issue is claimed by declaring one.

    It is required rather than optional because the contractual yield cannot be computed
    without it (FR-018), and `results.hurdle.net_present_value` forbids the hard-coded 365
    that would otherwise be needed: the yield would then disagree with the schedule it was
    computed from.

    ⚙ **It is an input to no figure describing the instrument's own terms** (FR-003b) -- not
    an amount, and **not a rate**. The boundary is *return figures versus issue terms*, and
    the difference is the whole door: a day count plus one coupon amount plus the interval
    between two coupons yields a **coupon rate**, and a coupon rate plus the spacing yields
    an extrapolated **issue date**. That is the invented legal fact this form exists to
    refuse, reached in two steps from a field this record requires.
    """

    published_in_order: tuple[date, ...] | None
    """The dates in the order the **source** published them, where that was not ascending.

    ``None`` where the source published them in date order, which is the ordinary case.
    Ordering is settled at transcription -- the same declared human step that turns kopecks
    into hryvnia -- and the loader neither sorts nor accepts an unordered list (FR-006).

    ⚙ **An observation about the source, not about the money**, and the one that silently
    disappears: that an issuer publishes the principal repayment before the final coupon is
    a fact about how the endpoint reports, and sorting the list is precisely the act that
    would delete it. Of the 32 observed issues exactly one is shaped that way, and it is the
    only one this form would have refused as published.
    """

    provenance: Provenance
    """The sources the schedule table rests on. Every one of them an inference."""


@dataclass(frozen=True, slots=True)
class InstrumentConstraints:
    """What the instrument requires of a purchase. Feasibility, not arithmetic."""

    min_ticket: Money
    """The smallest amount that may be invested. A purchase below it is infeasible and
    is reported with its shortfall, never rounded to fit (FR-018)."""

    min_unit: float
    """The smallest buyable increment, in units. Governs the unreinvestable coupon
    remainder (FR-020), which arrives with the reinvestment policy."""

    provenance: Provenance
    """Kept separate from the terms' provenance: a minimum ticket and a coupon rate are
    different facts, usually from different sources."""


@dataclass(frozen=True, slots=True)
class InstrumentDeclaration:
    """One investable thing, as declared in data. Curated, shared, version-controlled."""

    id: str
    """Unique across every instrument file. A duplicate is a load-time failure."""

    name: str
    """Human-readable, non-empty. For a synthetic fixture it says so in words."""

    instrument_class: str
    """Which ``InstrumentOps`` computes this thing's events -- ``"fixed_income"`` here.

    The **only** permitted dispatch key. Branching on ``id`` would make an issue's
    behaviour code rather than data, which is the Principle II violation this field
    exists to prevent.
    """

    currency: Currency
    """The denomination the instrument trades and pays in."""

    is_synthetic: bool
    """``True`` for a fixture whose terms are invented rather than observed.

    Required with no default, so a real issue cannot be mistaken for a fixture through
    omission -- the omission would run the wrong way round.
    """

    terms: BondTerms | EnumeratedTerms
    """What this declaration says about the paper -- in one of the two forms it can say it.

    ⚙ **A union, and the union is the mechanism** (FR-002). The two forms are two epistemic
    situations rather than two encodings of one thing, and the cost of keeping them apart is
    paid here: code reading a generative-only term cannot type-check against an enumerated
    declaration without handling its absence, so `mypy --strict` is what enumerates the sites
    that must change rather than a reviewer noticing.

    Which form a file is in is settled by :attr:`instrument_class`, the one dispatch key this
    record permits. Nothing outside `core.instruments` asks which member it holds; the four
    questions in `core.instruments.terms` are how the rest of the engine talks to it.
    """

    constraints: InstrumentConstraints
    """The feasibility constraints."""

    tax_classes: Mapping[TaxableEventKind, str]
    """Which declared tax class governs each kind of income, by class id.

    **Plural by design.** The same instrument is taxed one way on a distribution and
    another way on a disposal, so a single class per instrument is the modelling error
    this field exists to prevent. Every id must resolve; an unresolved one is reported,
    never treated as untaxed.
    """


@dataclass(frozen=True, slots=True)
class Holding:
    """What this owner bought: the per-owner half of a projection's input.

    Deliberately minimal. It names the instrument rather than embedding it, states the
    purchase, and stops. Anything an instrument needs beyond this comes from the
    declaration, and anything a *policy* needs comes from :class:`Assumptions`.
    """

    owner_id: str
    """Whose holding this is. Present from the first commit per Principle VII, with one
    owner and no authentication, because retrofitting tenancy is the expensive mistake."""

    instrument_id: str
    """The declared instrument bought. Resolved against the declaration by the caller."""

    quantity: float
    """Units bought. Strictly positive; zero or less is reported, never rounded up."""

    purchased_on: date
    """Settlement date of the purchase, and the origin of every time measurement."""

    cost: Money
    """What was actually paid, in the instrument's currency.

    Stated rather than derived from ``quantity x face_value``, because a bond bought at
    a discount or a premium costs something other than par and the whole yield figure
    turns on the difference.
    """


@dataclass(frozen=True, slots=True)
class DateRange:
    """The projection horizon: the window a run is asked about, inclusive of both ends."""

    start: date
    """First date in the window. Must be on or before the purchase."""

    end: date
    """Last date in the window.

    In this feature it must reach the final payment, adjusted date included: feature 001
    projects hold-to-maturity only (spec.md, Assumptions), so a horizon ending before
    maturity is reported as inconsistent rather than producing a truncated schedule whose
    yield figure would be silently wrong. An implicit liquidation at the horizon is the
    alternative and it is forbidden -- the spec calls it out as an edge case, and a
    liquidation nobody asked for would be a fabricated cash flow.
    """


@dataclass(frozen=True, slots=True)
class Assumptions:
    """The modelling choices a projection makes beyond what the declaration states.

    Kept minimal on purpose: a field here is a place where a result depends on something
    other than declared terms, so each one has to earn its place. Feature 001 has exactly
    two such choices, and the second of them arrived with the feature that reads it --
    ``coupon_policy`` was deliberately absent until then rather than declared and ignored,
    because an accepted-and-ignored field is worse than a missing one.
    """

    consumption_method: str
    """Which lots a disposal consumes: a key of ``lots.CONSUMPTION_ORDER_FNS``.

    An assumption rather than a declared term, because it is the owner's choice and it
    changes the answer: FIFO and LIFO give different, both correct, taxes on the same
    trades. There is no default anywhere in the stack.
    """

    coupon_policy: str
    """What happens to a coupon when it is paid: a key of
    ``fixed_income.COUPON_POLICY_FNS`` -- ``"hold_cash"`` or ``"reinvest"`` (FR-019).

    An assumption rather than a declared term for the same reason as
    :attr:`consumption_method`: the instrument's terms say what it *pays*, and what the
    owner does with the money afterwards is the owner's decision. Two different, both
    correct, answers follow from the same purchase (SC-010), so there is no default here
    either -- a defaulted policy would make one of the two answers the one you get by not
    thinking about it.

    The keys belong to the instrument class that implements the policies, because what
    "reinvest" *means* depends on what the instrument is: buying more of a bond at par is
    not the same operation as reinvesting a fund distribution. An unrecognised name fails
    loudly naming the known ones, exactly as an unrecognised convention does.
    """


EventsFn = Callable[
    [InstrumentDeclaration, Holding, DateRange, Assumptions],
    tuple[Event, ...] | InstrumentFailure,
]
"""Produce the ledger events a holding generates over a horizon, or say why not.

Obligations, all of them checkable by reading one implementation:

* **Gross only.** Events carry pre-tax amounts. Tax is applied downstream by a
  ``ChargeFn``; an instrument that netted tax into its own amounts would make the
  waterfall in spec §5.3 impossible to build.
* **No route or access costs.** Per Principle VI an access cost belongs to
  ``(instrument x income stream x route)`` and is never a property of the instrument
  alone.
* **Provenance on every amount**, built through ``money.*`` functions rather than
  constructed fresh, so a declared term's mark reaches every figure derived from it.
* **Explicit failure.** An instrument that cannot produce events returns an
  ``InstrumentFailure`` -- a typed value, not an exception and not an empty tuple. An
  empty tuple means "legitimately no events in this horizon" and nothing else.
"""

TaxClassesFn = Callable[[InstrumentDeclaration], Mapping[TaxableEventKind, str]]
"""Which declared tax class governs each kind of income this instrument produces."""

ConstraintsFn = Callable[[InstrumentDeclaration], InstrumentConstraints]
"""The feasibility constraints a purchase of this instrument must satisfy."""


@dataclass(frozen=True, slots=True)
class InstrumentOps:
    """The functions that define one instrument kind. Data, not an object.

    A frozen record whose fields happen to be functions. It carries no behaviour of its
    own, nothing inherits from it, and there is no instance state to hold -- which is
    rather the point, since an instrument's behaviour must come from declared terms
    rather than from anything it remembers.
    """

    events: EventsFn
    """The schedule generator. See :data:`EventsFn` for its obligations."""

    tax_classes: TaxClassesFn
    """The income-kind to tax-class mapping."""

    constraints: ConstraintsFn
    """The feasibility constraints."""
