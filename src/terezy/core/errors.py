"""Domain failures as a tagged union of frozen records, and the two exceptions.

FR-017: *any outcome the system cannot compute normally MUST be returned as a typed
result carrying the reason, and that reason MUST appear in the output. The system MUST
NOT clamp a value to zero, substitute a default, or return an empty result to represent
a failure.* The constitution says the same thing twice -- Principle IV ("Failure is
explicit") and the Engineering Standards clause "Tagged unions over exception
hierarchies for domain outcomes, dispatched with ``match``".

**How to consume these.** Match exhaustively, with a final arm the type checker proves
unreachable::

    match outcome:
        case InfeasiblePurchase():
            ...
        case InconsistentTerms():
            ...
        case _:
            assert_never(outcome)

That ceremony is the point. Adding a variant then produces a type error at every site
that must handle it, instead of silently inheriting a base-class default -- which is the
exact silent-default failure mode Principle II and FR-016 exist to prevent. An
exception hierarchy with a common base would have absorbed the new case quietly.

**Every variant carries a ``reason``.** FR-017 requires the reason to reach the output,
so it is a field rather than something a presenter reconstructs from the type. The
structured fields beside it exist so a caller can act on the failure -- report the
shortfall, name the missing class -- without parsing prose.

**The two exceptions, and why they are exceptions.** ``CurrencyMismatchError`` and
``LedgerInvariantError`` are both statements about the *code*, not about the money: a
currency was mixed, or a ledger invariant the engine is supposed to maintain was
violated. Neither is something the owner can act on and neither may flow into a result,
so both stop the run. Every failure that *is* a fact about the money is a record below.

**Why ``RealTermsUnavailable`` is not here.** It lives with the rate records in
``terezy.core.primitives.rates``, because it is a *slot filler*: the result always has
a real-terms slot and that record is what legitimately occupies it. It is a typed
absence in a valid result, not a failed computation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from terezy.core.tax.schedule import RateUndeclaredBefore

if TYPE_CHECKING:  # pragma: no cover -- import-time cycle avoidance, see below
    from terezy.core.primitives.money import Money

# ``money`` raises ``CurrencyMismatchError`` from this module, and
# ``InfeasiblePurchase`` describes its shortfall in ``Money``. Importing ``Money`` only
# under ``TYPE_CHECKING`` keeps that mutual reference to the type checker, where it is
# harmless, and out of the runtime import graph, where it would be a cycle. Both
# modules live in ``terezy.core``, so no layer contract is involved either way.


class CurrencyMismatchError(Exception):
    """Amounts in different currencies were combined. One of the core's two exceptions.

    A currency mismatch is a **programmer error**, not a business outcome, so it stops
    the run rather than flowing into a result as a typed value (FR-007, C5). There is no
    scenario in which a caller should catch this and continue: if UAH met USD, either a
    conversion was forgotten or the wrong amount was passed, and both are bugs in the
    code rather than facts about the money.

    That distinction is the whole reason the rest of this module exists. "This purchase
    is below the minimum ticket" is something the owner needs to see and act on, so it
    is a value. "This code added hryvnia to dollars" is something a developer needs to
    fix, so it is an exception.
    """


class LedgerInvariantError(Exception):
    """A ledger invariant was violated. The second and last exception in the core.

    The ledger's invariants -- cash conservation, lot conservation, basis conservation,
    no negative quantity, a stream that runs forwards, an event whose fields agree with
    its kind -- are properties the engine *maintains*. Nothing a declaration can say and
    nothing the owner can choose is able to break one; only a bug in this code can. So a
    violation is a programmer error and stops the run, exactly as a currency mismatch
    does.

    The distinction from the records below is the same one, drawn twice. "This purchase
    is below the minimum ticket" is a fact about the money that the owner needs to see,
    so it is a value. "This fold produced a position holding minus four units" is a fact
    about the code, so it is an exception -- and it must be a loud one, because the
    alternative is a plausible-looking figure derived from an impossible holding.

    It is deliberately **not** caught anywhere. Continuing past a broken invariant would
    mean reporting numbers computed from a ledger already known to be inconsistent,
    which is the defect class the constitution puts at top severity.
    """


@dataclass(frozen=True, slots=True)
class InfeasiblePurchase:
    """A purchase violates a declared constraint of the instrument.

    FR-018: reported as infeasible, naming the constraint and the shortfall, and **never
    silently adjusted to fit**. Rounding a purchase up to the minimum ticket would spend
    money the owner did not agree to spend; rounding it down would report a return on a
    holding that was never bought.
    """

    constraint: str
    """Which declared constraint was violated, e.g. ``"min_ticket"``."""

    required: Money
    """What the constraint demands."""

    actual: Money
    """What was offered."""

    shortfall: Money
    """``required - actual``. Carried rather than left to the caller to subtract, so the
    figure the owner is shown comes from the same arithmetic every time."""

    reason: str
    """Plain-language statement of the violation, for the output (FR-017)."""


@dataclass(frozen=True, slots=True)
class InconsistentTerms:
    """Two declared terms cannot both hold, so no schedule exists.

    The spec's example is a maturity date on or before the issue or purchase date. The
    honest answer is an inconsistency, **not a zero-length schedule** -- a zero-length
    schedule would report a holding that pays nothing, which is a different and false
    claim.
    """

    first_term: str
    """Name of one conflicting term, e.g. ``"maturity_date"``."""

    second_term: str
    """Name of the other, e.g. ``"issue_date"``."""

    reason: str
    """How the two conflict, in terms a reader can act on (FR-017)."""


@dataclass(frozen=True, slots=True)
class UnresolvedTaxClass:
    """An instrument names a tax class that was never declared.

    Reported rather than defaulted. Treating the holding as untaxed would be the single
    most expensive silent default available in this domain: the exempt case is the
    *desirable* one, so a missing class would quietly flatter every result derived from
    it (spec.md, Story 4 scenario 3).
    """

    tax_class_id: str
    """The class id that could not be resolved."""

    instrument_id: str
    """The instrument that referenced it."""

    reason: str
    """Plain-language statement, for the output (FR-017)."""


@dataclass(frozen=True, slots=True)
class SeedInstrumentUndeclared:
    """A declared opening lot names an instrument no curated declaration defines.

    FR-005 of feature 008, and the same refusal shape :class:`UnresolvedTaxClass` has, for
    the same reason: the alternative is inventing a placeholder instrument, and every figure
    derived from a holding of a made-up instrument would be a confident answer about
    something that does not exist.

    ⚙ **Here rather than in ``core.results.goal``**, which plan.md's file map names as the
    home of this feature's six refusals. The other five are goal outcomes and live there; this
    one is returned by ``core.ledger.seeds``, and putting it in a results module would make
    ``core.ledger`` import ``core.results`` -- backwards, since a result is built *from* the
    ledger. ``core.errors`` is where every other domain failure in the core already lives, and
    the seed opening also returns :class:`InconsistentTerms` from this module.

    The loader refuses the same thing earlier, naming the file and the field
    (``data.declarations.resolver``), which is what FR-005's "at load time" asks for. Both
    exist on :class:`UnresolvedTaxClass`'s precedent: the resolver catches it where the
    message can name a file, and the core refuses it where a caller might assemble seeds
    without going through a file at all.
    """

    instrument_id: str
    """The instrument the seed named and no declaration defines."""

    lot_id: str
    """Which declared lot named it, so the reader is sent to one entry rather than a file."""

    reason: str
    """Plain-language statement, for the output (FR-017)."""


InstrumentFailure = InfeasiblePurchase | InconsistentTerms
"""What an instrument operation may fail with.

An alias over the union rather than a wrapper record: a wrapper would add a layer to
unpack at every call site and would tempt someone into giving it a base type. The names
``InstrumentFailure`` and ``TaxFailure`` exist so that a function signature can say
which failures it can produce, which is narrower and more useful than saying it can
produce any of them.
"""

TaxFailure = UnresolvedTaxClass | RateUndeclaredBefore
"""What a tax rule operation may fail with.

``RateUndeclaredBefore`` joined with feature 006, when rates became dated schedules: a
class can now exist, cover the income kind, and still have nothing to say about an event
that predates its earliest cited entry. That is a third thing, distinct from "no class"
and from "the wrong class", and it is in the union so every consumer must match it
exhaustively rather than inherit a default (FR-012, research.md D2).
"""

SeedFailure = SeedInstrumentUndeclared | InconsistentTerms
"""What opening a ledger from declared seed lots may fail with (feature 008).

``InconsistentTerms`` appears in two unions because it is genuinely the same failure in both:
two declared facts that cannot both hold. A lot acquired before its instrument was issued,
or after the projection it opens, is exactly that -- and giving the seed path a private copy
of the record would mean two types a caller has to learn for one claim.
"""

DomainFailure = InstrumentFailure | TaxFailure | SeedFailure
"""Every domain failure in the core. Match exhaustively; see the module docstring."""
