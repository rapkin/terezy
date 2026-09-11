"""What one evaluated candidate's projection looks like on the wire: flows, not the ledger.

The join computes a projection per candidate and drops it (027, *Why this feature exists*).
This module is the shape it stops dropping in. **Nothing here computes a figure the projection
did not already hold**: every amount is read off a ledger event, a tax charge, a route cost or
the acquisition, and the one arithmetic step is ``gross - tax`` per row, which is the netting
``results.schedule`` performs for a bond and ``_released_by_date`` performs per date for every
arm. ``tests/unit/test_the_served_projection.py`` asserts the two agree on a bond, which is what
keeps the two netting sites from drifting apart.

**The ledger itself is not here.** ``LedgerState.capacity`` is keyed by ``CapacityKey``, which
has no JSON object key form, so the serialiser refuses the record outright. What the card needs
of it travels instead as each flow's own ``caused_by``, which names a declaration rather than
pointing at an event nobody can fetch.

**An arm is a union member, not a flag.** A bond states a premium against the principal its
paper repays; a fund states dated distributions and an exit line; a balance states neither and
releases what it cost. Flattening a fund's lines into a bond's row shape would be the core
computing something new, and a record with every field optional would leave a reader unable to
tell *this arm has no such thing* from *this arm reported nothing*. The absences are
:class:`NotStated` records for that second reason (FR-007).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, assert_never

from terezy.core.instruments.accrual import Carried
from terezy.core.ledger.events import CausationRef, EventKind
from terezy.core.primitives import money
from terezy.core.primitives.conventions import AmountsAsDeclared, ConventionsApplied
from terezy.core.primitives.money import Money
from terezy.core.results.cash import CashProjection
from terezy.core.results.fund import DistributionLine, ExitLine, FundProjection
from terezy.core.results.project import Projection, PurchasePremium
from terezy.core.results.ramp import OneWayCost, WayOutCost
from terezy.core.tax.interface import TaxCharge

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from terezy.core.ledger.engine import LedgerState
    from terezy.core.results.tuple import Arrival


@dataclass(frozen=True, slots=True)
class NotStated:
    """A record this arm does not state, named rather than left absent or zeroed (FR-007).

    A bar the card cannot draw is a **refusal bar** carrying this reason, which is a different
    thing on the screen from a bar of zero -- and on the shipped registry both are real: a fund
    states no cash-flow schedule and no distribution in the window, and a bond's purchase row
    carries a zero tax resting on no source.
    """

    what: str
    """The record that is absent, in the name the arm would have used for it."""

    arm: str
    """Which projection kind does not state it."""

    reason: str


@dataclass(frozen=True, slots=True)
class FlowLine:
    """One dated ledger line: what moved, what was taxed on it, and what was left.

    ``results.schedule.CashFlowRow`` for the arms that state a schedule, widened by one arm on
    :attr:`conventions` so the two that do not can still place their dates.
    """

    sequence: int
    occurred_on: date
    kind: EventKind
    quantity: float | None
    gross: Money
    """Signed: negative out of the account, positive in."""

    tax: Money
    """The charge struck on this line, as a positive magnitude, carrying its own sources.

    Zero is a value and it means two different things: a zero **charge** citing an exemption,
    and a line no rule ran on at all, whose zero rests on no source. E11 is that distinction,
    and the provenance is what tells them apart.
    """

    net: Money
    conventions: ConventionsApplied | AmountsAsDeclared | NotStated
    caused_by: CausationRef


@dataclass(frozen=True, slots=True)
class Purchase:
    """What the arriving money bought, when, and the split of the price it paid."""

    purchased_on: date
    quantity: float
    price_per_unit: Money
    paid: Money
    """``price_per_unit x quantity``, as the acquisition struck it."""

    carried: Carried | NotStated
    """The clean/accrued split of the quotation carried to the settlement date (022).

    Computed at the buy leg and summed to one dirty price before this feature, so the accrued
    interest paid **into** a purchase reached no reader while the accrual sold **out** at an
    early exit did. An arm that buys at no quotation states none.
    """


@dataclass(frozen=True, slots=True)
class WayIn:
    """The inbound charge as the costing struck it, with the declared wait beside it.

    The whole ``OneWayCost`` under the field name FR-002 requires, never a copy of its figures:
    ``tests/contract/test_cost_labels.py`` forbids a cost figure outside a labelled record, and
    a card that re-listed ``sent``, ``arrived`` and ``components`` here would be exactly the
    unlabelled price that guard exists to catch. The latency is beside it because
    ``OneWayCost`` does not carry one -- ``cost_one`` reports it separately.
    """

    one_way: OneWayCost
    latency_days: int


@dataclass(frozen=True, slots=True)
class Release:
    """One date's netted release, the charge struck on it, and where it arrived.

    **Per dated release and never per flow.** The way out charges a flat fee per movement, so
    two lifecycle flows on one date travel home once and share one charge; splitting it between
    them would be a figure with no owning call, and drawing one bar per flow would report the
    fee twice.

    The cost's own ``sent`` and ``arrived`` restate what ``Arrival`` already carries,
    deliberately: the charge between them is what this record exists for, and a card that had
    the two amounts and not the charge would subtract one from the other.

    The whole ``WayOutCost`` for :class:`WayIn`'s reason, and it carries its own latency.
    """

    released_on: date
    arrived_on: date
    way_out: WayOutCost


@dataclass(frozen=True, slots=True)
class BondArm:
    """An instrument that repays a principal: what was paid over or under it."""

    at_purchase: PurchasePremium
    distributions: NotStated
    exit_line: NotStated


@dataclass(frozen=True, slots=True)
class FundArm:
    """A fund: dated distributions and an exit line, and no schedule of coupons.

    Ranked on the shipped registry rather than a fixture case -- ``inzhur_miltech`` is a member
    of every section -- which is what makes the absences below a bar-level statement rather than
    a refusal of the whole card.
    """

    distributions: tuple[DistributionLine, ...]
    exit_line: ExitLine | NotStated
    entry_spread: Money
    exit_spread: Money
    at_purchase: NotStated


@dataclass(frozen=True, slots=True)
class CashArm:
    """A declared balance: it releases what it cost, and nothing happens in between."""

    released: Money
    at_purchase: NotStated
    distributions: NotStated
    exit_line: NotStated


@dataclass(frozen=True, slots=True)
class CandidateProjection:
    """One evaluated candidate's dated flows, its two route charges, and its purchase.

    What is **not** here, each because it is already on the ``TupleOutcome`` the card holds:
    ``reaches``, the rate, the span, the horizon, the remainder and its journey. Carrying one
    twice is where two copies of a fact come to disagree.
    """

    projection_key: str
    """The address the answer published for this candidate, echoed so a client can check that
    the body it got is the one it asked for."""

    instrument_id: str
    arm: BondArm | FundArm | CashArm
    flows: tuple[FlowLine, ...]
    charges: tuple[TaxCharge, ...]
    purchase: Purchase
    way_in: WayIn
    releases: tuple[Release, ...]


NO_SCHEDULE = "cash_flow_schedule"
NO_DISTRIBUTIONS = "distributions"
NO_EXIT_LINE = "exit_line"
NO_PREMIUM = "at_purchase"


def flows_of(
    ledger: LedgerState,
    charges: Sequence[TaxCharge],
    *,
    conventions: ConventionsApplied | AmountsAsDeclared | NotStated,
) -> tuple[FlowLine, ...]:
    """Every dated line of a folded ledger, with the charge struck on it folded into the row.

    The ``TAX_CHARGE`` events are left out and their amounts read off the **charges** instead,
    for ``results.schedule``'s reason: since feature 009 a charge event is an assessment memo
    that moves nothing, so summing the events would report zero tax on every row.
    """
    charged = {charge.event_sequence: charge.total for charge in charges}
    return tuple(
        FlowLine(
            sequence=event.sequence,
            occurred_on=event.occurred_on,
            kind=event.kind,
            quantity=event.quantity,
            gross=event.amount,
            tax=(tax := charged.get(event.sequence, money.zero(event.amount.currency))),
            net=money.sub(event.amount, tax),
            conventions=conventions,
            caused_by=event.caused_by,
        )
        for event in ledger.applied
        if event.kind is not EventKind.TAX_CHARGE
    )


def arm_of(projected: Projection | FundProjection | CashProjection) -> BondArm | FundArm | CashArm:
    """Which member of the union this projection is, with the records the others state."""
    match projected:
        case Projection():
            return BondArm(
                at_purchase=projected.at_purchase,
                distributions=NotStated(
                    what=NO_DISTRIBUTIONS,
                    arm="bond",
                    reason=(
                        "a bond pays coupons and repays principal on its own declared schedule; "
                        "a distribution is a fund's dated payout and this paper declares none. "
                        "The coupons are flows on this record."
                    ),
                ),
                exit_line=NotStated(
                    what=NO_EXIT_LINE,
                    arm="bond",
                    reason=(
                        "a bond's way out is a redemption or an early sale, both of which are "
                        "flows on this record; an exit line is a fund's buyback and this paper "
                        "declares none."
                    ),
                ),
            )
        case FundProjection():
            return FundArm(
                distributions=projected.distributions,
                exit_line=projected.exit_line
                if projected.exit_line is not None
                else NotStated(
                    what=NO_EXIT_LINE,
                    arm="fund",
                    reason=(
                        "this run's liquidity mode owes no buyback inside the window, so the "
                        "fund states no exit line. The position is not thereby worthless: what "
                        "it is worth is a question the declaration does not answer here."
                    ),
                ),
                entry_spread=projected.entry_spread,
                exit_spread=projected.exit_spread,
                at_purchase=NotStated(
                    what=NO_PREMIUM,
                    arm="fund",
                    reason=(
                        "a fund states no principal to repay, so there is nothing for a price "
                        "to be a premium or a discount against. What it charges on the way in "
                        "and out is the entry and exit spread beside this."
                    ),
                ),
            )
        case CashProjection():
            return CashArm(
                released=projected.released,
                at_purchase=NotStated(
                    what=NO_PREMIUM,
                    arm="cash",
                    reason=(
                        "a balance is bought at par by construction: an amount of the declared "
                        "currency buys that amount of balance, so no premium or discount arises."
                    ),
                ),
                distributions=NotStated(
                    what=NO_DISTRIBUTIONS,
                    arm="cash",
                    reason=(
                        "the declared rate is zero, so the balance pays nothing between the day "
                        "it opens and the day it is released."
                    ),
                ),
                exit_line=NotStated(
                    what=NO_EXIT_LINE,
                    arm="cash",
                    reason=(
                        "a balance is released rather than sold, which is a flow on this record."
                    ),
                ),
            )
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(projected)


def conventions_of(
    projected: Projection | FundProjection | CashProjection,
) -> ConventionsApplied | AmountsAsDeclared | NotStated:
    """What the arm says shaped its dates and its amounts, or that it says nothing.

    Read off the schedule the arm already built rather than off the declaration a second time:
    two readings of one declaration are two answers waiting to disagree about which convention
    placed a date.
    """
    match projected:
        case Projection():
            return projected.schedule.rows[0].conventions if projected.schedule.rows else _silent()
        case FundProjection() | CashProjection():
            return _silent()
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(projected)


def _silent() -> NotStated:
    return NotStated(
        what="conventions",
        arm="fund or cash",
        reason=(
            "this arm builds no cash-flow schedule, so no periodicity generated these dates, no "
            "business-day rule moved one, and no day count sized an amount. The dates are the "
            "ones its own dated records state."
        ),
    )


def releases_of(repatriated: Sequence[tuple[Arrival, WayOutCost]]) -> tuple[Release, ...]:
    """One record per dated release: when it left, when it arrived, and what it was charged."""
    return tuple(
        Release(released_on=arrival.released_on, arrived_on=arrival.arrived_on, way_out=charged)
        for arrival, charged in repatriated
    )
