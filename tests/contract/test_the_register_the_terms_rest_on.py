"""What the issuer's register states, asserted rather than described.

Feature 016 moves six facts about an ОВДП issue from "inferred by a human reading a seller's
list of unlabelled numbers" to "stated by the issuer" -- the currency, the face value, the
payment dates, the amounts, the payment kinds, and the claim that the list is complete. Each
assertion below is one of those facts being a fact.

The counts that describe the register are **derived from it** rather than written beside it,
on `test_the_observation_the_form_rests_on.py`'s precedent: a re-fetch that moves one fails
here, naming the claim that moved.
"""

from __future__ import annotations

from collections import Counter
from datetime import date

import pytest

from tests import observations as obs

pytestmark = pytest.mark.contract

COMPLETED_AND_DELISTED = (
    "UA4000229264",
    "UA4000230262",
    "UA4000230809",
    "UA4000232599",
    "UA4000233332",
    "UA4000233696",
    "UA4000235378",
)
"""Bond issues the seller carries as `completed` that the register no longer lists. Named
rather than counted: a check asserting only that seven have gone would pass if the wrong
seven had."""


def test_one_issuer_is_named_on_every_entry() -> None:
    """What makes this the ISSUER's record and not a third party's compilation. A second
    name here would mean the register is not what the citation says it is."""
    issues = obs.register_issues().values()
    assert {issue["emit_name"] for issue in issues} == {"Міністерство фінансів України"}
    assert {issue["emit_okpo"] for issue in issues} == {"00013480"}


def test_the_payment_kind_is_labelled_by_the_issuer_and_takes_two_values() -> None:
    """013's `payment_kind` inference, closed. The kind is stated per row, so no declaration
    reads it off an amount, a date or a position in a list."""
    kinds = Counter(
        row["pay_type"] for issue in obs.register_issues().values() for row in issue["payment"]
    )
    assert set(kinds) == {obs.COUPON, obs.PRINCIPAL}
    assert kinds[obs.PRINCIPAL] < kinds[obs.COUPON]


def test_every_issue_states_its_own_currency() -> None:
    """013's withdrawn fifth inference. The programme issues in more than one currency, so
    reading it off the issuer's nationality would have been wrong for nineteen issues."""
    stated = Counter(issue["val_code"] for issue in obs.register_issues().values())
    assert set(stated) == {"UAH", "USD", "EUR"}
    assert all(count > 0 for count in stated.values())


def test_every_issue_states_a_face_value_and_never_zero() -> None:
    """013's `face_value` inference, closed: the nominal is published rather than read off
    the largest payment in a list."""
    for isin, issue in obs.register_issues().items():
        assert issue["nominal"] > 0, isin


def test_every_declared_issue_is_listed_and_every_delisted_one_is_completed() -> None:
    """FR-008's boundary, from the register's side. The seven absentees are named, and each
    is one the seller itself marks completed -- so the register agrees with the boundary this
    feature chose on other grounds."""
    assert obs.undeclarable_isins() == ()
    listed = obs.register_issues()
    absent = tuple(sorted(isin for isin in obs.seller_bonds() if isin not in listed))
    assert absent == COMPLETED_AND_DELISTED
    for isin in absent:
        assert obs.seller_bonds()[isin]["status"] == "completed"


def test_the_coupon_is_the_rate_halved_against_the_nominal_on_every_declared_issue() -> None:
    """Two published figures agreeing about a third, which is what makes the transcription
    checkable at all. The identity is `auk_proc * nominal / 200` -- a rate halved for a
    half-year period. It is the reason a **generative** declaration is still refused: the
    convention that produces it is not named anywhere in the register, so reproducing the
    schedule from a rate would mean inventing one."""
    for isin in obs.declared_isins():
        issue = obs.register_issues()[isin]
        expected = issue["auk_proc"] * issue["nominal"] / 200
        coupons = [row["pay_val"] for row in issue["payment"] if row["pay_type"] == obs.COUPON]
        assert coupons, isin
        assert all(value == pytest.approx(expected, abs=1e-9) for value in coupons), isin


def test_every_declared_issue_runs_from_placement_to_maturity() -> None:
    """The `coverage` inference, closed. The list starts at or after `razm_date` and its last
    payment is `pgs_date` -- which is what a declaration's `covers_from` rests on."""
    for isin in obs.declared_isins():
        issue = obs.register_issues()[isin]
        dates = obs.register_dates(issue)
        assert min(dates) >= date.fromisoformat(issue["razm_date"]), isin
        assert max(dates) == date.fromisoformat(issue["pgs_date"]), isin


def test_every_declared_issue_repays_its_principal_exactly_once() -> None:
    for isin in obs.declared_isins():
        issue = obs.register_issues()[isin]
        repayments = [row for row in issue["payment"] if row["pay_type"] == obs.PRINCIPAL]
        assert len(repayments) == 1, isin
        assert repayments[0]["pay_val"] == issue["nominal"], isin


def test_every_declared_schedule_is_published_in_ascending_date_order() -> None:
    """Why no declaration carries `published_in_order` (FR-009a): the field records that a
    source published out of order, and this one does not. `UA4000235865`'s out-of-order
    publication is the SELLER's, and lives in the disagreement check."""
    for isin in obs.declared_isins():
        dates = obs.register_dates(obs.register_issues()[isin])
        assert dates == sorted(dates), isin
