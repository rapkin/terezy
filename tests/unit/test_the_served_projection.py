"""What each arm of the served projection carries, and what it says it does not (FR-003, FR-007).

Over the shipped registry rather than fixtures, because the three arms are all live in it:
measured 2026-09-11, the owner's question evaluates 63 candidates on the bond arm, 3 on the fund
arm and 3 on the cash arm.
"""

from __future__ import annotations

import dataclasses

from terezy.core.ledger.events import EventKind
from terezy.core.primitives.conventions import AmountsAsDeclared, ConventionsApplied
from terezy.core.results import project
from terezy.core.results.card import BondArm, CashArm, FundArm, NotStated, flows_of
from terezy.core.results.project import Projection, PurchasePremium
from tests import synthetic
from tests.served_projections import served

BONDS = 63
"""How many of the shipped question's evaluated candidates are on the bond arm.

Pinned so the per-arm assertions below cannot pass by reaching one candidate: an arm that
stopped being evaluated would leave its loop empty and every claim in it vacuously true.
"""


def _arms() -> dict[str, list[object]]:
    held: dict[str, list[object]] = {}
    for _, projection in served():
        held.setdefault(type(projection.arm).__name__, []).append(projection.arm)
    return held


def test_all_three_arms_are_reached_by_the_shipped_question() -> None:
    assert set(_arms()) == {BondArm.__name__, FundArm.__name__, CashArm.__name__}


def test_a_bond_states_a_premium_and_names_the_records_it_does_not_state() -> None:
    arms = _arms()[BondArm.__name__]
    assert len(arms) == BONDS
    for arm in arms:
        assert isinstance(arm, BondArm)
        assert isinstance(arm.at_purchase, PurchasePremium)
        for absent in (arm.distributions, arm.exit_line):
            assert isinstance(absent, NotStated)


def test_a_fund_states_its_own_dated_lines_and_no_premium() -> None:
    """``inzhur_miltech`` is ranked in every section: the fund arm is not a fixture case."""
    arms = _arms()[FundArm.__name__]
    assert arms
    for arm in arms:
        assert isinstance(arm, FundArm)
        assert isinstance(arm.at_purchase, NotStated)
        # Measured on the shipped window: it states an exit line and no distribution at all.
        assert arm.distributions == ()
        assert not isinstance(arm.exit_line, NotStated)
        assert arm.exit_line.executed_on <= arm.exit_line.settles_on


def test_a_balance_states_what_it_released_and_nothing_else() -> None:
    arms = _arms()[CashArm.__name__]
    assert arms
    for arm in arms:
        assert isinstance(arm, CashArm)
        assert arm.released.amount > 0.0
        for absent in (arm.at_purchase, arm.distributions, arm.exit_line):
            assert isinstance(absent, NotStated)


def test_an_absence_names_the_record_and_the_arm_rather_than_carrying_a_zero() -> None:
    """FR-007: never an empty record and never a record of zeros."""
    absences = [
        getattr(projection.arm, field.name)
        for _, projection in served()
        for field in dataclasses.fields(projection.arm)
        if isinstance(getattr(projection.arm, field.name), NotStated)
    ]
    assert absences
    for absence in absences:
        assert absence.what.strip()
        assert absence.arm.strip()
        assert absence.reason.strip()
        assert not hasattr(absence, "amount")


def test_the_purchase_carries_its_date_and_the_split_where_one_was_carried() -> None:
    """022's clean/accrued split, which the buy leg summed away until this feature."""
    split = 0
    for outcome, projection in served():
        purchase = projection.purchase
        assert purchase.purchased_on >= outcome.horizon.start
        assert purchase.quantity > 0.0
        if isinstance(projection.arm, BondArm):
            assert not isinstance(purchase.carried, NotStated)
            assert purchase.carried.clean.amount > 0.0
            split += 1
        else:
            assert isinstance(purchase.carried, NotStated)
    assert split == BONDS


def test_only_the_arm_with_a_schedule_states_a_convention() -> None:
    for _, projection in served():
        stated = {id(flow.conventions) for flow in projection.flows}
        assert len(stated) == 1, projection.projection_key
        held = projection.flows[0].conventions
        if isinstance(projection.arm, BondArm):
            assert isinstance(held, ConventionsApplied | AmountsAsDeclared)
        else:
            assert isinstance(held, NotStated)


def test_no_tax_charge_event_is_served_as_a_flow() -> None:
    """A ``TAX_CHARGE`` moves nothing since 009, so a flow for one would draw a bar of zero
    beside the charge it assessed."""
    kinds = {flow.kind for _, projection in served() for flow in projection.flows}
    assert kinds
    assert EventKind.TAX_CHARGE not in kinds


def test_the_served_flows_are_the_schedule_the_bond_arm_already_builds() -> None:
    """The one check that keeps two netting sites from drifting apart.

    ``results.schedule`` nets ``gross - tax`` per row for an arm that builds a schedule, and
    ``card.flows_of`` does it for every arm because two of the three build none. Nothing in the
    type system says the two agree, and a divergence would be a wrong number on the surface
    built to let a reader check one.
    """
    projected = project.project(
        synthetic.declaration(),
        synthetic.holding(),
        synthetic.horizon(),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
    )
    assert isinstance(projected, Projection)
    assert projected.charges, "a schedule with no charge would not exercise the netting"
    rebuilt = flows_of(
        projected.ledger, projected.charges, conventions=projected.schedule.rows[0].conventions
    )
    assert len(rebuilt) == len(projected.schedule.rows)
    for flow, row in zip(rebuilt, projected.schedule.rows, strict=True):
        assert (flow.sequence, flow.occurred_on, flow.kind, flow.quantity) == (
            row.sequence,
            row.occurred_on,
            row.kind,
            row.quantity,
        )
        assert (flow.gross, flow.tax, flow.net) == (row.gross, row.tax, row.net)
        assert flow.caused_by == row.caused_by
