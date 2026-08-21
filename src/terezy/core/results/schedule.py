"""The cash-flow schedule: the dated sequence a holding pays, derived from the ledger.

FR-001 asks for "the complete dated schedule of cash flows from purchase to maturity",
and FR-021 adds that the schedule must **state which convention it applied**. This module
is that answer, and its one structural rule is the direction of derivation: the schedule
is a *projection of the ledger*, never a parallel computation beside it (research.md D3).
Two things that both compute the coupon are two answers to the same question, and the one
that reaches the reader would be whichever the presenter happened to call.

**Tax is folded into the row it was charged on, not given a row of its own.** A reader
asking what a coupon paid wants gross, tax and net on one line, which is also the shape
the waterfall in spec §5.3 needs. The pairing between a tax event and the event it taxed
is **passed in**, not inferred: ``taxed_by`` comes from the code that created both events
and therefore knows. Matching them by date adjacency would be a guess dressed as an audit
trail -- the same reason a fee's allocation is a stored field rather than a heuristic --
and it would start lying the moment two taxable events shared a date.

A tax event nobody claims is refused rather than dropped. A tax figure that cannot be
traced to the event it was charged on may not be reported at all (FR-008), and silently
omitting it would understate the tax while leaving the arithmetic looking tidy.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from terezy.core.errors import LedgerInvariantError
from terezy.core.ledger.engine import LedgerState
from terezy.core.ledger.events import CausationRef, Event, EventKind
from terezy.core.primitives import money
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money


@dataclass(frozen=True, slots=True)
class ConventionsApplied:
    """The three declared conventions that shaped a schedule's dates and amounts.

    Carried on every row rather than once on the schedule, because FR-021 is a statement
    about what the schedule *says*: a row lifted out of the table -- into a report, into a
    comparison -- has to keep saying which convention placed it. They are identical across
    the rows of one issue today; they will not be when a schedule spans two instruments.
    """

    periodicity: str
    """The declared coupon frequency that generated the dates."""

    day_count: str
    """The declared day-count convention that turned each accrual period into a fraction
    of a year, and therefore fixed each coupon's size."""

    business_day_rule: str
    """The declared rule that moved a payment off a non-business day. Applied to the
    payment date only; the accrual was measured on the unadjusted dates."""


@dataclass(frozen=True, slots=True)
class CashFlowRow:
    """One dated line of a schedule: what moved, what was taxed on it, what was left."""

    sequence: int
    """The sequence number of the ledger event this row reports, so the row resolves back
    to the record behind it (FR-008)."""

    occurred_on: date
    """The date money actually changed hands, after any business-day adjustment."""

    kind: EventKind
    """What the movement was. The ledger's own vocabulary, not a display label."""

    quantity: float | None
    """Units acquired or surrendered, or ``None`` for a purely cash line."""

    gross: Money
    """The pre-tax amount, signed: negative out of the account, positive in."""

    tax: Money
    """The tax charged on this line, as a **positive magnitude**.

    Unsigned so that ``net = gross - tax`` reads the way the requirement is written. Zero
    is a real value here and means one of two quite different things depending on the
    row: a zero *charge* carrying the exemption's provenance, or -- on a purchase, where
    no tax rule ran at all -- a zero resting on no source. The provenance tells them
    apart, which is why it is carried rather than discarded.
    """

    net: Money
    """``gross - tax``: what the holding actually received or paid on this date."""

    conventions: ConventionsApplied
    """Which declared conventions placed this date and sized this amount (FR-021)."""

    caused_by: CausationRef
    """The instrument term or tax rule that produced the event behind this row."""


@dataclass(frozen=True, slots=True)
class CashFlowSchedule:
    """Every dated line of a holding's life, in fold order."""

    currency: Currency
    """The denomination of every amount in every row. One currency, stated once."""

    rows: tuple[CashFlowRow, ...]
    """The lines, in the ledger's own order -- ascending sequence, ascending date."""


def of_ledger(
    state: LedgerState,
    *,
    conventions: ConventionsApplied,
    taxed_by: Mapping[int, int],
) -> CashFlowSchedule:
    """Build the schedule a folded ledger implies.

    ``taxed_by`` maps the sequence number of a taxed event to the sequence number of the
    tax event charged on it. It is required rather than defaulted: an empty default would
    silently produce a schedule where every net equals its gross, which is exactly what an
    exempt holding looks like -- so the bug would be invisible in the one case this
    feature cares most about.
    """
    by_sequence = {event.sequence: event for event in state.applied}
    claimed = set(taxed_by.values())
    for event in state.applied:
        if event.kind is EventKind.TAX_CHARGE and event.sequence not in claimed:
            raise LedgerInvariantError(
                f"tax event {event.sequence} is not charged against any event in this "
                "ledger, so the figure it reports cannot be traced to what was taxed. A "
                "figure that cannot be traced may not be reported (FR-008), and dropping "
                "it from the schedule would understate the tax while leaving the "
                "arithmetic looking tidy."
            )

    rows = [
        _row(event, by_sequence, taxed_by, conventions)
        for event in state.applied
        if event.kind is not EventKind.TAX_CHARGE
    ]
    return CashFlowSchedule(currency=state.base_currency, rows=tuple(rows))


def _row(
    event: Event,
    by_sequence: Mapping[int, Event],
    taxed_by: Mapping[int, int],
    conventions: ConventionsApplied,
) -> CashFlowRow:
    """One row: the event's own amount, and the tax event charged against it."""
    tax_sequence = taxed_by.get(event.sequence)
    if tax_sequence is None:
        # No tax rule ran on this line -- a purchase, or a reinvestment. The zero rests
        # on no source, which is the one legitimate use of empty provenance and is a
        # different claim from a zero *charge* that cites an exemption.
        charged = money.zero(event.amount.currency)
    else:
        charged = money.scale(by_sequence[tax_sequence].amount, -1.0)
    return CashFlowRow(
        sequence=event.sequence,
        occurred_on=event.occurred_on,
        kind=event.kind,
        quantity=event.quantity,
        gross=event.amount,
        tax=charged,
        net=money.sub(event.amount, charged),
        conventions=conventions,
        caused_by=event.caused_by,
    )
