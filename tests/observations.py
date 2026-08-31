"""The two observation files, read once.

Feature 016 declares an issue from **two** sources and the whole of it turns on keeping them
apart: the National Bank's depository has the terms, Inzhur has the price. Several modules need
both, and a reader in each would be one fact in several places -- so the readers live here and
nothing else does. Nothing here interprets: each caller states its own reading.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
DATA_ROOT: Final = REPO_ROOT / "data"

SELLER: Final = DATA_ROOT / "observations" / "inzhur.toml"
REGISTER: Final = DATA_ROOT / "observations" / "nbu_depository.toml"

SELLER_RETRIEVED_ON: Final = date(2026, 8, 24)
REGISTER_RETRIEVED_ON: Final = date(2026, 8, 31)

COUPON: Final = "1"
PRINCIPAL: Final = "2"


def _load(path: Path) -> Mapping[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def seller() -> Mapping[str, Any]:
    document = _load(SELLER)
    assert date.fromisoformat(document["retrieved_on"]) == SELLER_RETRIEVED_ON, (
        f"{SELLER} was re-fetched; read the diff and re-measure before moving this date"
    )
    return document


def register() -> Mapping[str, Any]:
    document = _load(REGISTER)
    assert date.fromisoformat(document["retrieved_on"]) == REGISTER_RETRIEVED_ON, (
        f"{REGISTER} was re-fetched; read the diff and re-measure before moving this date"
    )
    return document


def active_isins() -> tuple[str, ...]:
    """The bond issues the seller carried as active at its retrieval date, sorted."""
    return tuple(
        sorted(
            entry["isin"]
            for entry in seller()["observation"]
            if entry.get("asset_type") == "bond" and entry["status"] == "active"
        )
    )


def seller_bonds() -> Mapping[str, Mapping[str, Any]]:
    return {
        entry["isin"]: entry
        for entry in seller()["observation"]
        if entry.get("asset_type") == "bond"
    }


def register_issues() -> Mapping[str, Mapping[str, Any]]:
    return {entry["isin"]: entry for entry in register()["issue"]}


def register_dates(issue: Mapping[str, Any]) -> list[date]:
    return [date.fromisoformat(row["pay_date"]) for row in issue["payment"]]


def seller_dates(bond: Mapping[str, Any]) -> list[date]:
    return [date.fromisoformat(payment["date"]) for payment in bond.get("payment", ())]


def declared_isins() -> tuple[str, ...]:
    """The intersection FR-008 defines the declared set as: active at the seller, listed by
    the register. Derived, never written down, so it survives an issue leaving the register."""
    listed = register_issues()
    return tuple(isin for isin in active_isins() if isin in listed)


def undeclarable_isins() -> tuple[str, ...]:
    """Active at the seller and absent from the register -- the refusals FR-008 requires.
    Empty on the shipped observations, and the only half of SC-001 that can fail."""
    listed = register_issues()
    return tuple(isin for isin in active_isins() if isin not in listed)


def remaining_payments(isin: str, after: date) -> Sequence[tuple[date, float]]:
    """The register's payment rows falling strictly after a date, in date order."""
    issue = register_issues()[isin]
    rows = [
        (date.fromisoformat(row["pay_date"]), float(row["pay_val"])) for row in issue["payment"]
    ]
    return sorted(row for row in rows if row[0] > after)
