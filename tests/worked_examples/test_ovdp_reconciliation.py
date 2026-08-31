"""The seller's own stated yield, used once -- as a check on the transcription.

FR-017. `return_rate_buy_pct` is the platform's forecast about itself, carried verbatim by
`scripts/fetch_inzhur.py` and never computed from. That makes it useless as an input and
valuable as a **check**: an internal rate of return over the buy quotation and the payments the
DECLARATION makes is a figure this project can compute for itself, and two independent
calculations landing on the same number is evidence the transcription is right.

**Computed over the register's schedule, not the seller's**, because the register's is what a
declaration carries. The difference is visible and it is corroboration: over the seller's own
list the same code agrees to within a thousandth of a percentage point on 7 issues, over the
register's on 19.

**Five issues disagree, and they are exactly the five with one coupon left.** On a
simple-interest reading those five reconcile and the long-dated ones diverge by up to 3.3 pp,
so the residual is a convention difference on a short residual maturity rather than a
transcription error. That inference is what a fetcher cannot make and a human can.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests import observations as obs

pytestmark = pytest.mark.worked_example

TOLERANCE_PP = 0.09
"""Percentage points. **Not the project tolerance**, which governs money compared with money:
this compares a rate we compute against a rate a seller published to two decimal places, so
nothing below 0.005 pp is even measurable in the published figure. 0.09 is set an order of
magnitude above that and an order of magnitude below the smallest real residual (0.641), so it
separates the two populations rather than splitting either."""

MEASURED_RESIDUALS = {
    "UA4000234413": 0.6414,
    "UA4000237416": 0.8017,
    "UA4000238281": 0.7990,
    "UA4000236624": 0.9098,
    "UA4000235865": 0.9788,
}
"""The five, with what they actually measure. Ours is higher in every case, which is the
direction a compounding convention differs from a simple one over a short residual."""


def _internal_rate_of_return(price: float, flows: list[tuple[date, float]], *, on: date) -> float:
    """The annualised rate on act/365 at which the flows discount to the price, in per cent.

    Bisection rather than Newton: the function is monotone over the bracket and a bisection
    cannot wander off a bad derivative, which matters more than speed for 24 issues.
    """
    low, high = -0.99, 10.0
    for _ in range(200):
        middle = (low + high) / 2
        present = sum(
            amount / ((1 + middle) ** ((when - on).days / 365.0)) for when, amount in flows
        )
        low, high = (middle, high) if present > price else (low, middle)
    return (low + high) / 2 * 100.0


def _residual(isin: str) -> float:
    """Ours minus the seller's, in percentage points, as of the seller's retrieval date."""
    bond = obs.seller_bonds()[isin]
    flows = list(obs.remaining_payments(isin, obs.SELLER_RETRIEVED_ON))
    computed = _internal_rate_of_return(float(bond["buy"]), flows, on=obs.SELLER_RETRIEVED_ON)
    return computed - float(bond["return_rate_buy_pct"])


def test_nineteen_issues_reconcile_within_the_stated_tolerance() -> None:
    agreeing = tuple(
        isin
        for isin in obs.declared_isins()
        if isin not in MEASURED_RESIDUALS and abs(_residual(isin)) <= TOLERANCE_PP
    )
    assert set(agreeing) == set(obs.declared_isins()) - set(MEASURED_RESIDUALS)


def test_the_nineteen_reconcile_to_within_a_thousandth_of_a_point() -> None:
    """Far tighter than the tolerance, which is the point: nineteen independent calculations
    landing on the seller's published figure is not a coincidence a wrong schedule survives."""
    for isin in set(obs.declared_isins()) - set(MEASURED_RESIDUALS):
        assert abs(_residual(isin)) <= 0.001, isin


def test_the_five_that_disagree_are_named_with_their_measured_residuals() -> None:
    for isin, expected in MEASURED_RESIDUALS.items():
        assert _residual(isin) == pytest.approx(expected, abs=0.0005), isin


def test_the_five_are_exactly_the_issues_with_one_coupon_left() -> None:
    """The reason the residual is a convention rather than a mistake, asserted rather than
    asserted about."""
    single_coupon = {
        isin
        for isin in obs.declared_isins()
        if len(
            [
                row
                for row in obs.register_issues()[isin]["payment"]
                if row["pay_type"] == obs.COUPON
                and date.fromisoformat(row["pay_date"]) > obs.SELLER_RETRIEVED_ON
            ]
        )
        == 1
    }
    assert single_coupon == set(MEASURED_RESIDUALS)


def test_a_moved_quotation_fails_the_reconciliation(monkeypatch: pytest.MonkeyPatch) -> None:
    """The control. A buy price one per cent off moves the computed rate well past the
    tolerance, so the check is reading the file rather than a constant."""
    real = obs.seller_bonds
    monkeypatch.setattr(
        obs,
        "seller_bonds",
        lambda: {
            isin: (bond if isin != "UA4000239081" else {**bond, "buy": bond["buy"] * 1.01})
            for isin, bond in real().items()
        },
    )
    assert abs(_residual("UA4000239081")) > TOLERANCE_PP
