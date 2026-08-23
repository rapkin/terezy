"""What the owner already holds, turned into the opening events the engine already folds.

``SIMULATOR_SPEC.md`` §4.8, required test **J2**. Every projection before this feature
started from zero, which describes a hypothetical person with no assets; the owner's actual
question is what to do next with what is already held.

**A seed is an ordinary ledger citizen** (008 research.md D1). :func:`opening_events` turns
declared lots into ``PURCHASE`` events -- the kind ``core.ledger.lots`` already opens lots
with -- and stops there. There is no seed lot type, no parallel position store, and no
branch anywhere in the fold that knows a lot was seeded. That is not economy for its own
sake: FR-002 requires every conservation invariant to count seeded lots from day one, and
the cheapest way to guarantee it is to give the invariants nothing new to count. A separate
"seed position" would have to be taught to each of them, and the first one nobody taught
would be the defect. ``tests/invariants/test_ledger_conservation.py`` therefore draws seeded
ledgers into the properties that already existed, and not one of them changed.

**The declared cost is the event's cash outflow**, which is what makes the seeded basis
recomputable from the events rather than merely asserted. The consequence is worth stating
plainly: a ledger of nothing but seeds shows *negative* cash, because it contains the
acquisitions and not the funding that paid for them. That is the honest reading. A seed
declares what is **held**; the deposit that bought it years ago is not something the owner
declared, and inventing one to make the balance tidy would put a placeholder value in the
result (FR-024) and leave cash conservation checking a number this engine made up.

**A guessed cost is a guessed tax, and there is one marking system rather than two** (008
research.md D3, the spine of the feature). An estimated basis is a :class:`SourceRef` in the
lot's provenance, so it rides the machinery that already carries an unverified market value
into every figure derived from it: through ``lots.consume`` into the consumed basis, through
``lots.realise`` into the realised gain, and through ``tax.flat_rate.charge`` into the
**tax**. Nobody has to remember to propagate it, because nothing here does the propagating.

FR-007 says an estimated basis must mark downstream figures *exactly as* an unverified value
does, and the only reading of that which stays true is to use the system that already does
it. A parallel mark would need its own ``merge``, its own propagation through every
transform, and its own coverage in the provenance contract test -- and the constitution puts
a transform that drops a mark in its top severity class. One system, already tested end to
end, cannot drop a mark in a place the other system remembered.

Free functions over frozen records, and nothing here constructs ``Money``: the declared cost
arrives already built by the data layer, which is where a declared value enters the system
and where its provenance is attached.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final, assert_never

from terezy.core.errors import InconsistentTerms, SeedInstrumentUndeclared
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.primitives import money
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef

if TYPE_CHECKING:  # pragma: no cover -- typing only, and it keeps the import graph flat
    from terezy.core.instruments.interface import InstrumentDeclaration

BASIS_ESTIMATED_PREFIX: Final = "basis-estimated:"
"""The namespace that makes an estimated-basis mark tell itself apart (FR-008).

``SourceRef.id`` is already required to be unique within a run and to name where a value was
declared, so a prefix on it is a namespace rather than a second field: every mark this module
builds is ``basis-estimated:<declaration reference>``, and :func:`is_basis_estimated` is the
one place that reads it.

**Why not a ``kind`` field on ``SourceRef``.** Because the two marks must propagate *by the
same rule* (FR-007), and they do that by being the same type. Adding a discriminating field
to the shared record would touch every construction site in the project for the benefit of
one caller, and the field would then need a value at each of them -- which is a default with
extra steps. The mark is distinguishable on inspection, which is what FR-008 asks for, and
indistinguishable to ``merge``, which is what FR-007 asks for.
"""


@dataclass(frozen=True, slots=True)
class BasisKnown:
    """The owner knows what this lot cost. Carries nothing, because there is nothing to add.

    A member of a two-case union rather than ``is_estimated: bool``, because the estimated
    case carries a reason and this one does not: a boolean beside a nullable reason is the
    same information with one more way to be inconsistent, and the loader would have to check
    a combination the type can simply not express.
    """


@dataclass(frozen=True, slots=True)
class BasisEstimated:
    """The owner does not know what this lot cost, and says so with a number and a reason.

    **A single point value, not a range** (FR-009, owner decision 2026-08-22). A range form
    was offered and not taken: it would have let Principle I carry the uncertainty into the
    gain and the tax as a range, and the owner chose the simpler declaration. The whole
    honesty burden therefore rests on :attr:`mark` -- a point-estimated basis produces
    point-valued figures that are all visibly marked.
    """

    reason: str
    """Why the owner does not know it, in his own words. Required (FR-008)."""

    mark: SourceRef
    """The propagating mark, built by :func:`basis_estimated`.

    It is *the same kind of object* an unverified market observation carries, which is the
    point: ``provenance.merge`` cannot tell them apart, so no transform can drop one while
    remembering the other.
    """


Basis = BasisKnown | BasisEstimated
"""How the acquisition cost of one lot is known. Explicit -- never inferred (FR-006)."""

KNOWN: Final = BasisKnown()
"""The known case, as one shared value. It has no fields, so two instances say the same thing."""


@dataclass(frozen=True, slots=True)
class SeedLot:
    """One holding the owner already has: what, how many, when, at what cost, how well known.

    Per-owner declared data (Principle VII, FR-022) and the first record in the project that
    lives wholly on the private side of that boundary.
    """

    owner_id: str
    """Whose holding this is. Present from the first commit; there is one owner today."""

    lot_id: str
    """Identity of the lot this seed opens, unique within the declaration that produced it.

    Assigned by the loader from the entry's position in the file rather than declared, so two
    purchases of one instrument on one date -- legitimate, and named in the spec's edge cases
    -- are two lots that can be told apart, selected for consumption separately, and traced to
    separate lines.
    """

    declared_at: str
    """Where this lot was declared: ``seeds/owner-001.toml#seed[0]``.

    Carried rather than reconstructed, because it is what ``CausationKind.SEED_DECLARATION``
    promises -- a cause resolvable back to the file it was read from. It is also the id of the
    estimated-basis mark, so a marked tax figure and the event that opened the lot point at
    the same line of the same file.
    """

    instrument_id: str
    """Must name a curated declaration; an unknown one is refused (FR-005)."""

    quantity: float
    """Units held. Strictly positive -- the loader refuses zero and below."""

    acquired_on: date
    """When it was acquired. What a holding-period rule would later be measured from."""

    cost: Money
    """What was paid for these units, **in the base currency** (FR-010).

    A cost, not a current value. §4.8 is explicit and the spec's own sentence is the argument:
    a seed stated as "I hold 100 units worth X today" cannot produce a disposal gain at all,
    because the tax engine needs lots. Where the number is a guess, :attr:`basis` says so and
    this amount carries the mark.
    """

    basis: Basis
    """Known or estimated, declared explicitly. Never inferred, never defaulted (FR-006)."""


def basis_estimated(*, declared_at: str, reason: str, estimated_for: date) -> BasisEstimated:
    """An estimated basis and the mark that will follow it into every derived figure.

    The mark is a ``SourceRef`` with ``verified_on=None``, so
    ``provenance.is_unverified`` is true for anything computed from this lot and the existing
    machinery reports it. That is deliberate rather than convenient: an amount the owner
    recalls has not been checked against a primary source, and saying so with the project's
    one word for "not checked" is more honest than inventing a second vocabulary.

    ``estimated_for`` fills ``retrieved_on``, and the choice is stated here because the field
    means "when this value was read from its source". The owner's source is his own
    recollection of an acquisition, and the declaration carries no date but the acquisition's,
    so that is the date used. There is no clock in the core and none is wanted: a mark whose
    date depended on when the program ran would make two runs of one declaration produce two
    different provenance sets, and C4's determinism digest would disagree with itself.
    """
    return BasisEstimated(
        reason=reason,
        mark=SourceRef(
            id=f"{BASIS_ESTIMATED_PREFIX}{declared_at}",
            citation=f"the owner's own estimate of an acquisition cost: {reason}",
            retrieved_on=estimated_for,
            verified_on=None,
        ),
    )


def is_basis_estimated(ref: SourceRef) -> bool:
    """Whether one source is an estimated basis rather than an unverified observation.

    FR-008's "distinguishable on inspection". Both marks make a figure unverified and both
    propagate by the same rule; they differ in what a reader should do about them. An
    unverified market value is checked against its source; an estimated basis cannot be, and
    the only cure is the owner finding the receipt.
    """
    return ref.id.startswith(BASIS_ESTIMATED_PREFIX)


def basis_estimated_sources(provenance: Provenance) -> frozenset[SourceRef]:
    """The estimated bases a figure rests on, so the mark can name *which* lot it came from.

    The companion of ``provenance.unverified_sources`` and deliberately the same shape: a mark
    that cannot say which input it rests on is a taint flag, which is cheap, unfalsifiable and
    useless to the owner.
    """
    return frozenset(ref for ref in provenance.sources if is_basis_estimated(ref))


def rests_on_estimated_basis(provenance: Provenance) -> bool:
    """Whether **any** input behind this figure was an estimated acquisition cost.

    The same asymmetry ``provenance.is_unverified`` has, for the same reason: one guessed cost
    makes the gain a guess, and a figure is only as trustworthy as its least-trustworthy input.
    """
    return any(is_basis_estimated(ref) for ref in provenance.sources)


def opening_events(
    seeds: Sequence[SeedLot],
    instruments: Mapping[str, InstrumentDeclaration],
    *,
    opens_on: date,
) -> tuple[Event, ...] | SeedInstrumentUndeclared | InconsistentTerms:
    """The declared holdings as the events that open the ledger, or the reason there are none.

    Ordered by ``(acquired_on, lot_id)`` and sequenced from zero. The order is the acquisition
    order rather than the order the file happened to list, because an event stream is a
    history and ``events.in_sequence`` refuses one that runs backwards; the tie-break is the
    lot id, which is the same key FIFO consumption sorts on, so the history and the
    consumption order cannot disagree about which of two same-day lots came first.

    ``opens_on`` is the date the projection's ledger opens. It is an argument because there is
    no clock here and there will not be one: a lot dated after it has not been acquired yet,
    and the answer to that must be the same in a year's time as it is today.

    **Three refusals, all typed, none of them an exception.** An unknown instrument
    (FR-005), a lot acquired before its instrument existed, and a lot acquired after the
    ledger opens. The first refusal encountered is the whole answer and nothing is partially
    opened: half a ledger would produce figures describing a portfolio the owner does not
    hold, which is worse than no figures.

    **No seeds is an empty tuple and not a refusal** (FR-024, G16, research.md D9). Contrast
    feature 003, where an empty registry dimension *is* a typed outcome: there an empty venue
    list and a mistyped path are indistinguishable downstream and one of them is a mistake.
    Here they are distinguishable and neither is -- a person who holds nothing is an ordinary
    person, and refusing to run for him would be the tool inventing a requirement.
    """
    ordered = sorted(seeds, key=lambda lot: (lot.acquired_on, lot.lot_id))
    built: list[Event] = []
    for sequence, lot in enumerate(ordered):
        refusal = _inconsistency(lot, instruments, opens_on=opens_on)
        if refusal is not None:
            return refusal
        built.append(_opening_event(lot, sequence=sequence))
    return tuple(built)


def _inconsistency(
    lot: SeedLot,
    instruments: Mapping[str, InstrumentDeclaration],
    *,
    opens_on: date,
) -> SeedInstrumentUndeclared | InconsistentTerms | None:
    """Why this lot cannot be admitted, or ``None`` if it can.

    ``None`` is not a degraded outcome -- it is "nothing is wrong" -- which is why it is a
    plain absence here rather than a fourth member of the union.
    """
    declaration = instruments.get(lot.instrument_id)
    if declaration is None:
        return SeedInstrumentUndeclared(
            instrument_id=lot.instrument_id,
            lot_id=lot.lot_id,
            reason=(
                f"the declared opening lot {lot.lot_id!r} holds {lot.instrument_id!r}, which "
                "no curated instrument declaration defines. No placeholder instrument is "
                "created for it: every figure derived from a holding of an invented "
                "instrument would be a confident answer about something that does not exist."
            ),
        )
    if lot.acquired_on < declaration.terms.issue_date:
        return InconsistentTerms(
            first_term="seed.acquired_on",
            second_term="instrument.terms.issue_date",
            reason=(
                f"the declared opening lot {lot.lot_id!r} was acquired on "
                f"{lot.acquired_on.isoformat()}, before {lot.instrument_id!r} was issued on "
                f"{declaration.terms.issue_date.isoformat()}. Two declared facts that cannot "
                "both hold: the lot is not admitted and it is not silently re-dated, because "
                "moving it would change the acquisition date every holding-period rule and "
                "every consumption order is measured from."
            ),
        )
    if lot.acquired_on > opens_on:
        return InconsistentTerms(
            first_term="seed.acquired_on",
            second_term="projection.opens_on",
            reason=(
                f"the declared opening lot {lot.lot_id!r} was acquired on "
                f"{lot.acquired_on.isoformat()}, after the ledger opens on "
                f"{opens_on.isoformat()}. A holding acquired in the future is not a holding "
                "yet; it is a purchase the projection should make, which is a different "
                "declaration."
            ),
        )
    return None


def _opening_event(lot: SeedLot, *, sequence: int) -> Event:
    """One declared lot as the purchase it was.

    ``EventKind.PURCHASE`` rather than a kind of its own. A second kind meaning "cash out, a
    lot in" would have to be learned by the fold, by every conservation recomputation and by
    the tax mapping, and the first consumer that had not learned it would drop seeded holdings
    silently. What distinguishes a seed is not what happened -- units were bought -- but *who
    says so*, and that is recorded in the cause.
    """
    return Event(
        sequence=sequence,
        occurred_on=lot.acquired_on,
        kind=EventKind.PURCHASE,
        amount=money.scale(lot.cost, -1.0),
        owner_id=lot.owner_id,
        caused_by=CausationRef(
            kind=CausationKind.SEED_DECLARATION,
            id=lot.declared_at,
            detail=(
                f"declared opening lot: {lot.quantity} units of {lot.instrument_id} "
                f"acquired {lot.acquired_on.isoformat()} at a "
                f"{_basis_word(lot.basis)} cost"
            ),
        ),
        lot_ref=LotRef(instrument_id=lot.instrument_id, lot_id=lot.lot_id),
        quantity=lot.quantity,
        allocated_to=None,
        capacity_pool=None,
    )


def _basis_word(basis: Basis) -> str:
    """``known`` or ``estimated``, for the cause a human reads.

    A ``match`` over the union rather than a truth test, so that a third kind of basis -- a
    range, if FR-009 is ever widened -- is a type error here instead of quietly rendering as
    "known".
    """
    match basis:
        case BasisKnown():
            return "known"
        case BasisEstimated():
            return "estimated"
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(basis)
