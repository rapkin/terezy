"""The ``TaxRule`` plugin interface: one function signature, and the records it moves.

The second of the four plugin interfaces permitted by Principle II, and the one whose
governing constraint is the strictest in the project: **no tax value may originate from
an implementer's or an agent's memory.** Every rate arrives in a ``TaxClass`` loaded from
``data/tax/`` as a **dated schedule**, each entry carrying its own citation, retrieval
date and verification date. A rate literal in a Python file is a defect regardless of
whether it happens to be correct -- including ``0.0``, and including an effective date.

Per owner decision D-E the interface is a function signature plus records of data. Note
what the signature does *not* do: it takes the ``TaxClass`` as an **argument** rather than
closing over it. A rule is a stateless function; there is nothing to construct and nothing
to configure.

**Three obligations that shape the records below.**

*Zero is a charge, not an absence.* For an exempt class the rule returns a ``TaxCharge``
of zero **carrying the citation of the entry that produced it** -- not ``None``, not a
skipped event. A zero charge that cites its exemption is the evidence the exemption was
applied; a missing charge is indistinguishable from a rule that never ran, and SC-002's
"exactly zero" is only checkable if the zeroes are recorded.

*PIT and levy are separate lines on separate bases.* The military levy is not a surcharge
folded into a rate. Nothing in feature 001 exercises the difference -- both rates are zero
-- but the cases that matter later are unrepresentable once the two are added together at
source: foreign withholding creditable against PIT but **not** against the levy cannot be
expressed against a blended figure at all.

*Tax currency is not display currency.* No code here may assume the currency a charge is
computed in is the currency anything is displayed in. The three roles Principle VI names are
three because they come apart, and this interface is where they would be collapsed first.

⚙ **A charge is computed in the currency its base arrived in, which is not always the tax
currency.** Feature 011 made that reachable: an event denominated in a foreign currency is
charged here on its own amount, and ``core.tax.year`` restates the whole charge at the
declared official rate for the event's date when it assembles the year -- except for a
realised disposal gain, which it refuses outright rather than converting. So a ``TaxCharge``
leaving this module may be denominated in USD, and a rule that compared its base against the
jurisdiction's tax currency -- or skipped a conversion on the strength of one -- would be
wrong.

That ordering carries **one assumption, and it is this interface's to state**: restating a
charge after the fact is only equivalent to charging the declared rates on a converted base
because ``flat_rate`` is *linear* in its base. A rule with a bracket, a cap, a floor or an
allowance stated in the tax currency would apply those thresholds to a foreign-magnitude base
before ``year`` ever sees the figure, and the answer would be plausible and wrong.

**Such a rule is not expressible against this signature, and that is the thing to know before
writing one.** Striking a base in the tax currency needs the declared rate series and the
currency itself; :data:`ChargeFn` passes an ``Event``, a ``TaxClass`` and a ``TaxContext``,
and none of the three carries either -- a rule cannot even learn what the tax currency is. So
the first non-proportional rule is a change to this interface (the series, or the assessment
rules, reaching the rule), and only then a call to
``core.tax.official_rate.strike_base``. Recorded 2026-08-29, when ``flat_rate`` was still the
only rule and the question was therefore cheap to answer wrongly.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from terezy.core.errors import TaxFailure
from terezy.core.ledger.events import Event
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.tax.schedule import RateEntry


class TaxableEventKind(Enum):
    """The kinds of income a tax class can speak about. A closed set.

    Distinct from ``ledger.events.EventKind``, which says what *moved*. Several ledger
    events map to one taxable kind and several ledger kinds are not taxable at all, so
    collapsing the two enums would put tax policy inside the ledger's vocabulary.

    The ``value`` strings are the data contract used in declaration files.
    """

    COUPON = "coupon"
    """Contractual interest on a debt instrument."""

    DISPOSAL_GAIN = "disposal_gain"
    """Realised gain on disposing of a holding, redemption at maturity included."""

    DISTRIBUTION = "distribution"
    """A distribution from a fund or trust. Declared here because the same instrument is
    taxed differently on distribution and on disposal, which is the reason
    ``tax_classes`` is a mapping; no instrument in feature 001 produces one."""

    INTEREST = "interest"
    """Interest that is not a contractual bond coupon -- a deposit, a cash balance."""

    CONVERSION = "conversion"
    """Value converted along a funding route -- a ramp movement.

    Whether a conversion is taxable **at all** is not this engine's claim to make:
    ``SIMULATOR_SPEC.md`` §4.2 records that a stablecoin's later conversion may itself be
    a taxable disposal under a regime that is genuinely unsettled, and asks for both
    interpretations to be modellable. So the kind exists in the vocabulary, and the
    treatment is a declaration: a jurisdiction that taxes conversions declares a class
    whose ``applies_to`` includes this kind, and one that does not declares none -- in
    which case no rule runs, because no declared class applies, not because a comment
    says nothing was earned.
    """


@dataclass(frozen=True, slots=True)
class TaxClass:
    """A declared tax treatment: what is charged on which kinds of income, and from when.

    Every rate is an observed legal value with a citation, carried on the dated entry it
    belongs to. The exempt class is not a special type and has no special branch
    anywhere: it is this record with an entry declaring both rates zero and a source that
    says why.
    """

    id: str
    """Unique across every tax file. A duplicate is a load-time failure."""

    applies_to: frozenset[TaxableEventKind]
    """The income kinds this class governs. Non-empty.

    A rule asked to charge a kind outside this set **refuses** rather than charging zero:
    "the rule does not cover this" and "the rule applied and the result was zero" are
    opposite claims, and only one of them is cited.
    """

    rates: tuple[RateEntry, ...]
    """The class's rates as a **dated schedule**, sorted by effective date, non-empty.

    ⚙ **Feature 006 replaced feature 001's scalar ``pit_rate`` / ``levy_rate`` pair with
    this field**, closing the gap `data/README.md` rule 3 recorded and required test E10
    named. The scalar was removed rather than kept alongside: two code paths reading a
    rate would mean the older one kept working, and nothing would ever force the
    migration (research.md D1).

    **Provenance lives on each entry, not on the class.** The rate before a legislated
    change and the rate after it are two observations from two sources with two
    verification dates, and one mark for both would let a checked figure vouch for an
    unchecked one. That is why this record no longer carries a ``provenance`` field: a
    charge takes its citation from the entry that produced it.

    Sorted and non-empty are enforced at the data boundary, where the file can be named;
    :func:`terezy.core.tax.schedule.rate_on` relies on both.
    """


@dataclass(frozen=True, slots=True)
class TaxContext:
    """What a charge is being computed *for*: the base, the kind, and whose income it is.

    The base arrives as an argument rather than being derived from the event, because for
    a disposal it cannot be: the taxable amount is the realised gain, which is a property
    of the ledger's disposal record and not of any single event. Making the caller state
    the base keeps the rule a pure application of declared rates, and keeps the question
    of *what is taxable* where it belongs -- with the code that knows the whole ledger.
    """

    instrument_id: str
    """Whose income this is. Carried so a refusal can name the instrument that asked."""

    taxable_event: TaxableEventKind
    """Which kind of income, so the rule can check the class actually covers it."""

    taxable_base: Money
    """The amount the rates are applied to, in whatever currency the caller struck it in.

    **A rule may not assume it is the tax currency**, and may not assume which currency it is
    at all: an income event is charged on its own amount, and a disposal on the realised gain,
    which the ledger computes in its own base currency. A foreign-currency charge on an income
    event is restated in the tax currency when the year is assembled; one on a **gain** is
    refused there instead, for the reason this module's docstring gives -- along with the
    assumption that ordering rests on, and why a non-proportional rule cannot simply convert
    here.

    A negative base is possible -- a realised loss -- and is passed through rather than
    clamped. See :mod:`terezy.core.tax.flat_rate` for what that means and does not mean.
    """

    charged_for_year: int
    """The tax year the liability accrues to. Payment timing is a later feature."""


@dataclass(frozen=True, slots=True)
class TaxCharge:
    """What one rule charged on one event: both lines, their base, and their sources."""

    event_sequence: int
    """The sequence number of the ledger event this charge was computed for.

    Stored rather than inferred, for the same reason a fee's allocation is stored: C6
    requires every tax figure to resolve to its event *and* its rule, and matching a
    charge to an event by date adjacency would be a guess dressed as an audit trail.
    """

    pit: Money
    """The personal income tax line. Zero for an exempt class, and recorded as zero."""

    levy: Money
    """The military levy line, computed on its own base and reported separately."""

    total: Money
    """``money.add(pit, levy)``, same currency enforced by the addition itself."""

    taxable_base: Money
    """What the rates were applied to, recorded so a figure can be checked without
    re-deriving it from the ledger."""

    tax_class_id: str
    """Which declared class produced this charge. The audit trail's "which rule"."""

    charged_for_year: int
    """The tax year this liability accrues to."""

    provenance: Provenance
    """Union of the base's sources and those of the **dated entry** that supplied the
    rates. This is how an exemption's citation reaches the total tax figure, and how an
    unverified rate marks it (FR-015).

    The entry's rather than the whole class's: a class whose December entry is verified
    and whose January entry is not must mark a January charge and only a January charge,
    which a single class-level mark could not express (research.md D1).
    """


ChargeFn = Callable[[Event, TaxClass, TaxContext], TaxCharge | TaxFailure]
"""Charge the declared rates of one class against one event, or say why not.

Obligations: no rate literals in code; provenance unions the base's and the class's; a
zero is returned as a charge rather than skipped; an unresolvable situation returns a
typed ``TaxFailure`` rather than raising or silently charging zero; and no timing logic,
because payment date and cash sourcing are later features.
"""


@dataclass(frozen=True, slots=True)
class TaxRuleOps:
    """How one kind of tax rule behaves. Data, not an object.

    One field today. It is a record rather than a bare function so that the second
    obligation a rule acquires -- a payment schedule, a withholding credit -- is a field
    here instead of a second registry that could disagree with this one about which
    rules exist.
    """

    charge: ChargeFn
    """The rule itself."""
