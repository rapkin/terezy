"""A built client is served from this origin, and an unknown API path still refuses in JSON.

An SPA document returned with status 200 for a missing API route reaches a generated client as a
parse error rather than as the missing route it is (020 FR-055, SC-030).
"""

from __future__ import annotations

from pathlib import Path

from terezy.api.http import document
from tests.data_roots import SHIPPED
from tests.http_client import served

DATA_ROOT = SHIPPED
AS_OF = {"as_of": "2026-09-03"}


def _dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<title>terezy</title>", encoding="utf-8")
    (dist / "app.js").write_text("export const ok = 1;\n", encoding="utf-8")
    return dist


def test_with_no_built_client_nothing_static_is_served() -> None:
    response = served(DATA_ROOT).get("/index.html")
    assert response.status_code == 404
    assert response.json()["tag"] == "service.PathNotServed"


def test_a_built_client_is_served_from_this_origin(tmp_path: Path) -> None:
    client = served(DATA_ROOT, client_dist=_dist(tmp_path))
    assert client.get("/app.js").status_code == 200
    fallback = client.get("/instruments/UA4000236228")
    assert fallback.status_code == 200
    assert "terezy" in fallback.text


def test_an_unknown_api_path_refuses_in_json_even_with_the_fallback_mounted(
    tmp_path: Path,
) -> None:
    client = served(DATA_ROOT, client_dist=_dist(tmp_path))
    response = client.get(f"{document.PREFIX}/nothing-here", params=AS_OF)
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["tag"] == "service.PathNotServed"


def test_the_api_still_answers_with_the_fallback_mounted(tmp_path: Path) -> None:
    client = served(DATA_ROOT, client_dist=_dist(tmp_path))
    response = client.get(f"{document.PREFIX}/venues", params=AS_OF)
    assert response.status_code == 200
    assert response.json()["category"] == "venues"


def test_a_client_route_that_merely_begins_with_api_is_still_the_app_shell(
    tmp_path: Path,
) -> None:
    """The API owns paths by segment, not by prefix: `/api-docs` is a client route."""
    client = served(DATA_ROOT, client_dist=_dist(tmp_path))
    served_shell = client.get("/api-docs")
    assert served_shell.status_code == 200
    assert "terezy" in served_shell.text
