"""What a generated client can name, over every route rather than over one.

Two refusals used to be answerable by routes that did not declare them. The framework's own
validation body -- a bare ``{"detail": [...]}`` for a malformed ``as_of`` -- carries no tag, so a
client generated from this document has nothing to narrow on and 021 FR-004's exhaustive switch
cannot reach it; and the ``Host`` refusal reaches every request while only the scenario-taking
routes said so.
"""

from __future__ import annotations

import json
from functools import cache
from typing import Any

import pytest

from terezy.api.http import document, envelopes
from tests.data_roots import SHIPPED
from tests.http_client import served

DATA_ROOT = SHIPPED

MALFORMED_REFUSAL = f"envelopes.{envelopes.RequestMalformed.__name__}"
HOST_REFUSAL = "middleware.HostNotDeclared"


@cache
def _document() -> dict[str, Any]:
    response = served(DATA_ROOT).get(f"{document.PREFIX}/openapi.json")
    assert response.status_code == 200
    parsed: dict[str, Any] = json.loads(response.text)
    return parsed


def _tags_declared(response: dict[str, Any]) -> set[str]:
    """Every refusal tag one declared status can carry: a member, or a union of members."""
    schema = response["content"]["application/json"]["schema"]
    if "discriminator" in schema:
        mapping: dict[str, str] = schema["discriminator"]["mapping"]
        return set(mapping)
    named = schema["$ref"].rsplit("/", 1)[-1]
    tag = _document()["components"]["schemas"][named]["properties"]["tag"]
    return set(tag["enum"]) if "enum" in tag else {tag["const"]}


@pytest.mark.contract
def test_a_malformed_as_of_is_a_typed_refusal_and_not_the_frameworks_own_body() -> None:
    """A well-formed question with an unreadable parameter, answered as a record like every other
    refusal: never a body whose shape the document does not publish (020 FR-016)."""
    answered = served(DATA_ROOT).get(f"{document.PREFIX}/venues", params={"as_of": "yesterday"})

    assert answered.status_code == 422
    body = answered.json()
    assert body["tag"] == MALFORMED_REFUSAL
    assert [parameter["location"] for parameter in body["parameters"]] == [["query", "as_of"]]
    assert body["parameters"][0]["given"] == "yesterday"


@pytest.mark.contract
def test_an_absent_as_of_names_the_parameter_rather_than_substituting_a_date() -> None:
    answered = served(DATA_ROOT).get(f"{document.PREFIX}/venues")

    assert answered.status_code == 422
    body = answered.json()
    assert body["tag"] == MALFORMED_REFUSAL
    assert [parameter["location"] for parameter in body["parameters"]] == [["query", "as_of"]]
    assert body["parameters"][0]["given"] is None


@pytest.mark.contract
def test_every_parameter_the_validator_reported_is_carried() -> None:
    """The routes served today take one coercible parameter each, so only the mapping can be
    provoked with two -- and a refusal that carried the first would be a silent drop of the rest
    the moment a second one is declared."""
    reported = envelopes.malformed_from(
        (
            {"loc": ("query", "as_of"), "input": "yesterday", "msg": "not a date"},
            {"loc": ("query", "from"), "input": 7, "msg": "not a period"},
        )
    )

    assert [parameter.location for parameter in reported.parameters] == [
        ("query", "as_of"),
        ("query", "from"),
    ]
    assert [parameter.given for parameter in reported.parameters] == ["yesterday", "7"]
    assert [parameter.problem for parameter in reported.parameters] == [
        "not a date",
        "not a period",
    ]


@pytest.mark.contract
def test_every_route_declares_the_malformed_parameter_refusal() -> None:
    """Declared on the router, so a route added later cannot forget it -- and so the framework's
    own untagged 422 is never the one the document publishes."""
    undeclared = [
        path
        for path, methods in _document()["paths"].items()
        if MALFORMED_REFUSAL not in _tags_declared(methods["get"]["responses"]["422"])
    ]
    assert not undeclared, f"these routes declare no typed 422: {undeclared}"
    assert "HTTPValidationError" not in _document()["components"]["schemas"]


@pytest.mark.contract
def test_every_route_declares_the_host_refusal_it_can_answer_with() -> None:
    """The allowlist runs in front of every route, so every route can answer with it."""
    undeclared = [
        path
        for path, methods in _document()["paths"].items()
        if HOST_REFUSAL not in _tags_declared(methods["get"]["responses"]["400"])
    ]
    assert not undeclared, (
        f"these routes can answer a Host refusal they do not declare: {undeclared}"
    )


@pytest.mark.contract
def test_a_route_that_declares_no_scenario_still_answers_the_host_refusal() -> None:
    """The provocation behind the assertion above, so it cannot pass by declaring a refusal the
    service never sends."""
    answered = served(DATA_ROOT).get(
        f"{document.PREFIX}/questions/what_should_i_do_with_the_hryvnia/answer",
        params={"as_of": "2026-09-06"},
        headers={"host": "evil.example"},
    )

    assert answered.status_code == 400
    assert answered.json()["tag"] == HOST_REFUSAL
