"""What the application serves, and — as important — what it does not.

Route groups own a first segment beneath the prefix. Mirroring `data/`'s tree was the obvious
design and is wrong: three categories live under `scenarios/`, so a path that mirrored the tree
would put `/scenarios/inflation` beside `/scenarios/{id}` and a scenario declared with the id
`inflation` would be unreachable, silently (020 FR-007a, FR-056, SC-003a, SC-031).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tomllib
from pathlib import Path
from typing import Any

import pytest

from terezy.api.http import categories, document, service
from tests.data_roots import SHIPPED
from tests.http_client import served

DATA_ROOT = SHIPPED


def _published() -> dict[str, dict[str, Any]]:
    """The route table as the *served* document publishes it, which is what a client is generated
    from -- read off the endpoint rather than off `app.openapi()`, because the document is no
    longer a file anyone can compare against and the endpoint is the only thing a client sees."""
    body = served(DATA_ROOT).get(f"{document.PREFIX}/openapi.json")
    assert body.status_code == 200
    paths: dict[str, dict[str, Any]] = json.loads(body.text)["paths"]
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
    fixed = {"registry", "openapi.json", "answers"}
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
def test_both_answer_routes_are_served() -> None:
    """029 FR-027. 020's `SC-026a` asserted the body-taking route's *absence*; an absence test
    kept after the thing exists passes for the wrong reason. Matched on the route table rather
    than on paths ending in `/answer`, which the new one does not."""
    answers = {path for path in _paths() if "answer" in path}
    assert answers == {
        f"{document.PREFIX}/questions/{{question_id}}/answer",
        f"{document.PREFIX}/answers",
    }


@pytest.mark.contract
def test_the_documentation_routes_serve_nothing() -> None:
    """The framework's two default pages reach three external hosts; Principle VII forbids it."""
    app = service.create_app(DATA_ROOT, client=None)
    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None
    assert not [path for path in _paths() if path in {"/docs", "/redoc", "/docs/oauth2-redirect"}]


@pytest.mark.contract
def test_the_one_route_that_is_not_a_get_is_the_posted_answer() -> None:
    """020's read-only guard restated rather than deleted (029 FR-010). It asserted that every
    route is a GET, under a name about writing; a POST falsifies the verb and leaves the
    property untouched, so the surface is pinned by name and a second POST is a red build."""
    not_a_get = {
        f"{method.upper()} {path}"
        for path, operations in _published().items()
        for method in operations
        if method != "get"
    }
    assert not_a_get == {f"POST {document.PREFIX}/answers"}


@pytest.mark.contract
def test_a_posted_answer_leaves_the_data_root_byte_identical(tmp_path: Path) -> None:
    """The half that makes the guard above one about **writing** rather than about a verb: a
    method pinned says nothing about what a route does to `data/` (029 FR-006, SC-012)."""
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    before = _tree_digest(root)

    body = tomllib.loads((root / "questions" / "fifty-thousand.toml").read_text(encoding="utf-8"))
    answered = served(root).post(
        f"{document.PREFIX}/answers", params={"as_of": "2026-09-03"}, json=body
    )

    assert answered.status_code == 200, answered.text
    assert _tree_digest(root) == before


def _tree_digest(root: Path) -> str:
    """Every path under a data root and the digest of its bytes, as one digest.

    Paths as well as contents, so a file *added* by a request moves it too -- a digest over
    contents alone would stay equal when a body was saved beside a file with the same bytes.
    """
    walked = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        walked.update(path.relative_to(root).as_posix().encode("utf-8"))
        if path.is_file():
            walked.update(hashlib.sha256(path.read_bytes()).digest())
    return walked.hexdigest()
