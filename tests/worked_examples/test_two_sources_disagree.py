"""Where the seller's schedule and the issuer's register disagree, per issue, by name.

FR-009. This is a fact about **two observation files** and about neither instrument, so it has
no home on a declaration and lives here instead. What it prevents is specific: a rule stated
once -- "the seller is a day early" -- is true of fifteen issues and false of nine, and
adopting it would have absorbed two outright errors silently, one of which feature 013 built a
fixture around.

**Sets, never counts.** Asserting that *fifteen* issues carry the offset would pass if the
wrong fifteen did.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from tests import observations as obs

pytestmark = pytest.mark.worked_example

ONE_DAY_EARLY = (
    "UA4000233712",
    "UA4000234223",
    "UA4000234413",
    "UA4000235196",
    "UA4000236228",
    "UA4000236475",
    "UA4000236624",
    "UA4000237416",
    "UA4000237556",
    "UA4000237804",
    "UA4000238281",
    "UA4000238968",
    "UA4000238976",
    "UA4000238992",
    "UA4000239008",
)
"""Every date the seller publishes is exactly one day earlier than the register's."""

WRONG_DATE = "UA4000235782"
"""One date wrong inside an otherwise exact schedule: 2027-06-03 for 2027-06-02."""

PRINCIPAL_A_DAY_EARLY = "UA4000235865"
"""The seller publishes the repayment of principal on 2026-09-15, a day BEFORE the final
coupon it also publishes. The register puts both on 2026-09-16, the ordinary way a bond ends.
So the one issue whose payments are published out of date order is publishing an ERROR -- 013
FR-020a's mechanism survives its real-world instance turning out to be a seller's mistake."""


def _offset(isin: str) -> int:
    """How many days the register's last payment falls after the seller's."""
    register = max(obs.register_dates(obs.register_issues()[isin]))
    published = max(obs.seller_dates(obs.seller_bonds()[isin]))
    return (register - published).days


def _shifted(isin: str, offset: int) -> list[date]:
    return sorted(
        day + timedelta(days=offset) for day in obs.seller_dates(obs.seller_bonds()[isin])
    )


def test_the_fifteen_offset_issues_are_exactly_these_fifteen() -> None:
    offset_by_one = tuple(isin for isin in obs.declared_isins() if _offset(isin) == 1)
    assert offset_by_one == ONE_DAY_EARLY


def test_the_nine_that_agree_are_exactly_the_complement() -> None:
    """No third offset: every declared issue is either exactly a day early or exact."""
    agreeing = tuple(isin for isin in obs.declared_isins() if _offset(isin) == 0)
    assert agreeing == tuple(isin for isin in obs.declared_isins() if isin not in ONE_DAY_EARLY)
    assert set(agreeing) | set(ONE_DAY_EARLY) == set(obs.declared_isins())


def test_twenty_two_schedules_are_exact_once_their_own_offset_is_applied() -> None:
    """The offset is per issue and it explains everything except two errors. Named rather
    than counted, for the reason the module docstring gives."""
    inexact = tuple(
        isin
        for isin in obs.declared_isins()
        if not set(_shifted(isin, _offset(isin)))
        <= set(obs.register_dates(obs.register_issues()[isin]))
    )
    assert inexact == (WRONG_DATE, PRINCIPAL_A_DAY_EARLY)


def test_one_schedule_carries_a_single_wrong_date() -> None:
    published = set(obs.seller_dates(obs.seller_bonds()[WRONG_DATE]))
    registered = set(obs.register_dates(obs.register_issues()[WRONG_DATE]))
    assert _offset(WRONG_DATE) == 0
    assert published - registered == {date(2027, 6, 3)}
    assert date(2027, 6, 2) in registered
    assert date(2027, 6, 3) not in registered


def test_the_principal_a_day_early_is_the_sellers_error_and_not_the_issuers_habit() -> None:
    published = obs.seller_dates(obs.seller_bonds()[PRINCIPAL_A_DAY_EARLY])
    registered = obs.register_dates(obs.register_issues()[PRINCIPAL_A_DAY_EARLY])
    assert published != sorted(published)
    assert published[-1] == date(2026, 9, 15)
    assert registered == sorted(registered)
    assert registered[-2:] == [date(2026, 9, 16), date(2026, 9, 16)]


def test_the_seller_contradicts_its_own_maturity_field_on_the_offset_fifteen() -> None:
    """`matures_on` equals the register's `pgs_date` on ALL twenty-four, so on the fifteen the
    seller's schedule disagrees with the seller's own maturity. That is the disagreement 013
    measured from one side and could not explain."""
    for isin in obs.declared_isins():
        seller_maturity = date.fromisoformat(obs.seller_bonds()[isin]["matures_on"])
        assert seller_maturity == date.fromisoformat(obs.register_issues()[isin]["pgs_date"]), isin
        published = max(obs.seller_dates(obs.seller_bonds()[isin]))
        assert (seller_maturity != published) == (isin in ONE_DAY_EARLY), isin


def test_every_declared_amount_is_the_sellers_figure_divided_by_one_hundred() -> None:
    """The kopeck reading, checked against the register rather than against a buy price. The
    LOT reading -- a hundred bonds of 1 000 nominal -- predicts the same ratio and is refused
    by the price: 1 025.59 against a 100 000 nominal is one per cent of face."""
    for isin in obs.declared_isins():
        seller = sorted(payment["amount"] for payment in obs.seller_bonds()[isin]["payment"])
        registered = sorted(row["pay_val"] for row in obs.register_issues()[isin]["payment"])
        tail = registered[-len(seller) :]
        assert [value / 100.0 for value in seller] == pytest.approx(tail, abs=1e-9), isin
        assert obs.seller_bonds()[isin]["buy"] < 2 * obs.register_issues()[isin]["nominal"], isin


def _scratch(tmp_path: Path, source: Path, anchor: str, old: str, new: str) -> Path:
    """A copy of an observation with one date moved inside one issue's own block.

    Scoped to the block because a payment date is not unique across a register of 195 issues,
    and a global replace would move four unrelated rows and prove nothing about this one.
    """
    text = source.read_text(encoding="utf-8")
    start = text.index(anchor)
    end = text.find("\n[[", start + len(anchor))
    block = text[start : end if end != -1 else len(text)]
    assert block.count(old) == 1, f"{old!r} is not unique inside {anchor!r}"
    copy = tmp_path / source.name
    copy.write_text(text[:start] + block.replace(old, new) + text[start + len(block) :], "utf-8")
    return copy


def test_moving_a_date_in_the_register_fails_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The control. Without it every assertion above could be reading a constant."""
    copy = _scratch(
        tmp_path,
        obs.REGISTER,
        f'isin   = "{WRONG_DATE}"',
        'pay_date     = "2027-06-02"',
        'pay_date     = "2027-06-03"',
    )
    monkeypatch.setattr(obs, "REGISTER", copy)
    with pytest.raises(AssertionError):
        test_one_schedule_carries_a_single_wrong_date()


def test_moving_a_date_in_the_sellers_file_fails_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy = _scratch(
        tmp_path,
        obs.SELLER,
        f'id     = "{PRINCIPAL_A_DAY_EARLY}"',
        'date         = "2026-09-15"',
        'date         = "2026-09-16"',
    )
    monkeypatch.setattr(obs, "SELLER", copy)
    with pytest.raises(AssertionError):
        test_the_principal_a_day_early_is_the_sellers_error_and_not_the_issuers_habit()
