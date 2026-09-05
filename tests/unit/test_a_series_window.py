"""A windowed read returns what the series covers and names what it does not, in one body.

Refusing the whole window would leave a client to trim the window to what exists, which 021
FR-001 forbids it; returning the short list alone is the silent truncation 020 FR-046 forbids
(FR-045, FR-045a, FR-047, SC-020, SC-021).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from terezy.api.http import document
from tests.http_client import served

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
AS_OF = {"as_of": "2026-09-03"}
CPI = "ua_cpi_monthly"
RATES = "ua_nbu_usd"


@pytest.fixture(scope="module")
def client() -> Any:
    return served(DATA_ROOT)


def _observations(client: Any, category: str, series_id: str, **window: str) -> dict[str, Any]:
    response = client.get(
        f"{document.PREFIX}/{category}/{series_id}/observations", params={**AS_OF, **window}
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    result: dict[str, Any] = body["result"]
    return result


def test_a_listing_publishes_the_coverage_a_window_needs(client: Any) -> None:
    """Without this the pair is a trap: a mandatory window and nowhere to read the extent from."""
    listing = client.get(f"{document.PREFIX}/cpi", params=AS_OF).json()
    assert set(listing["coverage"]) == set(listing["ids"])
    coverage = listing["coverage"][CPI]
    assert coverage["tag"] == "envelopes.SeriesCoverage"
    assert coverage["first"] < coverage["last"]


def test_an_omitted_window_returns_the_whole_declared_coverage(client: Any) -> None:
    result = _observations(client, "cpi", CPI)
    assert result["window"] is None
    assert result["outside"] is None
    assert len(result["observations"]) == 411


def test_a_covered_window_returns_exactly_its_periods(client: Any) -> None:
    result = _observations(client, "cpi", CPI, **{"from": "2025-08", "to": "2025-10"})
    assert [held["period"] for held in result["observations"]] == ["2025-08", "2025-09", "2025-10"]
    assert result["outside"] is None


def test_a_window_reaching_outside_coverage_names_what_is_missing(client: Any) -> None:
    result = _observations(client, "cpi", CPI, **{"from": "2025-09", "to": "2026-01"})
    outside = result["outside"]
    assert outside["tag"] == "envelopes.WindowOutsideCoverage"
    assert outside["series_id"] == CPI
    assert outside["asked"] == ["2025-09", "2026-01"]
    assert outside["covers"]
    assert outside["missing"], "the refusal names the periods the series does not declare"
    assert [held["period"] for held in result["observations"]] == ["2025-09", "2025-10"]
    assert outside["missing"] == ["2025-11", "2025-12", "2026-01"]


def test_a_one_ended_window_is_refused(client: Any) -> None:
    response = client.get(
        f"{document.PREFIX}/cpi/{CPI}/observations", params={**AS_OF, "from": "2026-01"}
    )
    assert response.status_code == 422
    assert "two-ended" in response.text


def test_an_undeclared_series_is_a_typed_refusal(client: Any) -> None:
    result = _observations(client, "cpi", "nothing-declares-this")
    assert result["tag"] == "envelopes.CategoryHasNoSuchId"


def test_a_rate_window_outside_the_declared_ends_refuses(client: Any) -> None:
    result = _observations(
        client, "official-rates", RATES, **{"from": "1990-01-01", "to": "1990-12-31"}
    )
    assert result["outside"]["tag"] == "envelopes.WindowOutsideCoverage"
    assert result["observations"] == []


def test_a_rate_window_inside_coverage_returns_its_dates(client: Any) -> None:
    result = _observations(
        client, "official-rates", RATES, **{"from": "2026-08-01", "to": "2026-08-05"}
    )
    assert [held["on_date"] for held in result["observations"]] == [
        "2026-08-01",
        "2026-08-02",
        "2026-08-03",
        "2026-08-04",
        "2026-08-05",
    ]
    assert result["outside"] is None


def test_every_observation_carries_its_own_provenance(client: Any) -> None:
    """Per row, not per series: collapsing them would lose which date was verified."""
    result = _observations(
        client, "official-rates", RATES, **{"from": "2026-08-01", "to": "2026-08-05"}
    )
    for held in result["observations"]:
        assert held["provenance"]["sources"], held
        assert isinstance(held["provenance"]["is_unverified"], bool)
    marks = {held["provenance"]["is_unverified"] for held in result["observations"]}
    assert marks == {True}, "the shipped series is unverified throughout, and says so per row"


def test_an_inverted_window_is_refused_rather_than_named_a_coverage_gap(client: Any) -> None:
    """Found by review: it used to reach the coverage question, where a window covering no
    period read as *the series declares none of it* -- the series named for a caller's typo."""
    for category, series_id, window in (
        ("cpi", CPI, {"from": "2025-06", "to": "2024-01"}),
        ("official-rates", RATES, {"from": "2025-06-01", "to": "2024-01-01"}),
    ):
        response = client.get(
            f"{document.PREFIX}/{category}/{series_id}/observations", params={**AS_OF, **window}
        )
        assert response.status_code == 422, category
        assert "ends before it begins" in response.text


def test_a_window_end_in_the_wrong_shape_is_refused(client: Any) -> None:
    for category, series_id, expected in (
        ("cpi", CPI, "YYYY-MM"),
        ("official-rates", RATES, "YYYY-MM-DD"),
    ):
        response = client.get(
            f"{document.PREFIX}/{category}/{series_id}/observations",
            params={**AS_OF, "from": "banana", "to": "zzz"},
        )
        assert response.status_code == 422, category
        assert expected in response.text
