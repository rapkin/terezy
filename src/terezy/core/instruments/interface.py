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

from terezy.core.errors import InstrumentFailure
from terezy.core.ledger.events import Event
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

    terms: BondTerms
    """The contractual terms."""

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
