"""What the application serves, and — as important — what it does not.

Route groups own a first segment beneath the prefix. Mirroring `data/`'s tree was the obvious
design and is wrong: three categories live under `scenarios/`, so a path that mirrored the tree
would put `/scenarios/inflation` beside `/scenarios/{id}` and a scenario declared with the id
`inflation` would be unreachable, silently (020 FR-007a, FR-056, SC-003a, SC-031).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from terezy.api.http import categories, document, service

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"


def _published() -> dict[str, dict[str, Any]]:
    """The route table as the document publishes it, which is what a client is generated from."""
    paths: dict[str, dict[str, Any]] = service.create_app(DATA_ROOT, client=None).openapi()["paths"]
    return paths


def _paths() -> list[str]:
    return list(_published())


@pytest.mark.contract
def test_every_path_is_under_the_prefix() -> None:
    outside = [path for path in _paths() if not path.startswith(f"{document.PREFIX}/")]
    assert not outside, f"paths served outside the {document.PREFIX!r} prefix: {outside}"


@pytest.mark.contract
def test_every_route_group_owns_a_distinct_first_segment() -> None:
    """Owners of a first segment, not paths: `/questions/{id}/answer` is inside its category."""
    owners = [path[len(document.PREFIX) + 1 :].split("/", 1)[0] for path in _paths()]
    categorised = {category.id for category in categories.CATEGORIES}
    fixed = {"registry", "openapi.json"}
    assert set(owners) == categorised | fixed
    assert not categorised & fixed, "a category shadows a fixed endpoint's segment"


@pytest.mark.contract
def test_every_category_path_is_one_segment() -> None:
    nested = [category.id for category in categories.CATEGORIES if "/" in category.id]
    assert not nested, f"category paths that are not one flat segment: {nested}"


@pytest.mark.contract
def test_a_singleton_offers_no_id_route() -> None:
    """The shape is read off the mapping, so a singleton cannot be asked the wrong question."""
    paths = set(_paths())
    for category in categories.CATEGORIES:
        route = f"{document.PREFIX}/{category.id}"
        assert route in paths
        has_id = f"{route}/{{record_id}}" in paths
        assert has_id is categories.is_keyed(category), category.id


@pytest.mark.contract
def test_observations_are_reachable_from_no_other_category() -> None:
    """`data/observations/` is served by nothing: FR-048, asserted over the route table.

    The only routes whose last segment is `observations` are the two series' windowed reads;
    `observation-kinds` is a declared category and not the retrieval files.
    """
    assert "observations" not in {category.id for category in categories.CATEGORIES}
    assert {path for path in _paths() if path.endswith("/observations")} == {
        f"{document.PREFIX}/cpi/{{record_id}}/observations",
        f"{document.PREFIX}/official-rates/{{record_id}}/observations",
    }


@pytest.mark.contract
def test_the_only_answer_route_names_a_declared_question() -> None:
    """FR-043's deferral, measured over the route table rather than merely stated."""
    answers = [path for path in _paths() if path.endswith("/answer")]
    assert answers == [f"{document.PREFIX}/questions/{{question_id}}/answer"]


@pytest.mark.contract
def test_the_documentation_routes_serve_nothing() -> None:
    """The framework's two default pages reach three external hosts; Principle VII forbids it."""
    app = service.create_app(DATA_ROOT, client=None)
    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None
    assert not [path for path in _paths() if path in {"/docs", "/redoc", "/docs/oauth2-redirect"}]


@pytest.mark.contract
def test_no_route_writes() -> None:
    """Read-only means read-only: every route is a GET."""
    methods = {method for operations in _published().values() for method in operations}
    assert methods == {"get"}
