"""One candidate's projection over HTTP: the route, its two refusals, and what it costs the answer.

027 FR-009 to FR-012. The refusals are **two** and distinguishable because the remedies differ --
a wrong URL against a client holding a key from another answer -- and there is deliberately no
third: a candidate whose projection could not be produced never became an outcome, so it carries
no key and has no address here.
"""

from __future__ import annotations

import json
from datetime import date
from functools import cache
from typing import Any, Final
from urllib.parse import quote

import pytest

from terezy.api.answer import answer_question
from terezy.api.http import document
from terezy.core.decision.candidates import evaluated
from terezy.core.primitives.currency import Currency
from terezy.core.results.answer import Answer
from terezy.core.results.candidates import CandidateSurvey
from tests.data_roots import SHIPPED
from tests.http_client import served

pytestmark = pytest.mark.contract

AS_OF: Final = "2026-09-06"
QUESTION: Final = "fifty-thousand-hryvnia"


@cache
def _published_keys() -> tuple[str, ...]:
    answered = answer_question(
        SHIPPED, QUESTION, as_of=date.fromisoformat(AS_OF), base_currency=Currency.UAH
    ).answer
    assert isinstance(answered, Answer)
    return tuple(
        outcome.projection_key
        for section in answered.sections
        if isinstance(section.outcome, CandidateSurvey)
        for outcome in evaluated(section.outcome.comparison)
    )


def _read(question: str, key: str, *, as_of: str = AS_OF) -> dict[str, Any]:
    response = served(SHIPPED).get(
        f"{document.PREFIX}/questions/{quote(question, safe='')}/candidates/{quote(key, safe='')}",
        params={"as_of": as_of},
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_a_published_key_answers_that_candidates_projection() -> None:
    key = _published_keys()[0]
    body = _read(QUESTION, key)
    assert body["question_id"] == QUESTION
    assert body["candidate_key"] == key
    result = body["result"]
    assert result["tag"] == "projection.ProjectedCandidate"
    assert result["projection"]["projection_key"] == key
    assert result["projection"]["flows"], "a projection with no flow draws no bar"
    assert result["manifest"]["tag"] == "manifest.RunManifest"


def test_one_key_of_each_arm_resolves_over_the_wire() -> None:
    """The wire, per arm. *Every* published key is resolved by
    ``tests/contract/test_the_card_accounts_for_what_came_back.py``, at the layer that decides
    which candidates were evaluated and without paying for 69 manifests to say it."""
    keys = _published_keys()
    assert len(keys) == 69, "the evaluated population moved; re-take the figure and say so"
    per_arm = {
        arm: next(key for key in keys if key.split("|")[1] == arm)
        for arm in ("inzhur_miltech", "cash_uah_monobank", "UA4000231195")
    }
    for arm, key in per_arm.items():
        body = _read(QUESTION, key)["result"]
        assert body["tag"] == "projection.ProjectedCandidate", arm
        assert body["projection"]["arm"]["tag"].startswith("card."), arm


def test_an_unknown_question_and_an_unknown_key_are_two_distinguishable_refusals() -> None:
    unknown_question = _read("no-such-question", _published_keys()[0])["result"]
    unknown_key = _read(QUESTION, "no-such-candidate")["result"]
    assert unknown_question["tag"] == "envelopes.CategoryHasNoSuchId"
    assert unknown_key["tag"] == "card.NoSuchCandidate"
    assert unknown_question["tag"] != unknown_key["tag"]
    assert unknown_key["evaluated_keys"], "a stale client is told what this answer did publish"
    assert unknown_question["declared_ids"], "a wrong URL is told which questions exist"


def test_the_key_of_one_section_does_not_answer_from_another() -> None:
    """The horizon is in the key because the same candidate is evaluated once per section."""
    by_instrument: dict[str, list[str]] = {}
    for key in _published_keys():
        by_instrument.setdefault(key.split("|")[1], []).append(key)
    repeated = next(keys for keys in by_instrument.values() if len(keys) > 1)
    served_keys = {
        _read(QUESTION, key)["result"]["projection"]["projection_key"] for key in repeated
    }
    assert served_keys == set(repeated)


def test_as_of_is_required() -> None:
    response = served(SHIPPED).get(
        f"{document.PREFIX}/questions/{QUESTION}/candidates/{quote(_published_keys()[0], safe='')}"
    )
    assert response.status_code == 422
    assert response.json()["tag"] == "envelopes.RequestMalformed"


def test_the_route_is_in_the_published_table_and_is_a_get() -> None:
    body = served(SHIPPED).get(f"{document.PREFIX}/openapi.json")
    paths = json.loads(body.text)["paths"]
    route = f"{document.PREFIX}/questions/{{question_id}}/candidates/{{candidate_key}}"
    assert route in paths
    assert set(paths[route]) == {"get"}


def test_the_document_version_moved_with_the_wire_change() -> None:
    """A client is generated from the document; a shape that changed under a fixed version
    drifts with no diff to read."""
    assert document.VERSION != "1.0.0"
    assert (
        json.loads(served(SHIPPED).get(f"{document.PREFIX}/openapi.json").text)["info"]["version"]
        == document.VERSION
    )


def test_the_answer_document_grows_only_by_the_published_key() -> None:
    """SC-005, measured on the response body against this branch's own baseline.

    8 540 464 bytes on the tree this branch started from (2026-09-11). What this feature adds
    to it is one short string per evaluated outcome and nothing else, so the bound is the
    published keys' own length rather than a constant -- a constant would go red the day the
    registry declares another issue, for a reason that is not this feature's.
    """
    body = served(SHIPPED).get(
        f"{document.PREFIX}/questions/{QUESTION}/answer", params={"as_of": AS_OF}
    )
    assert body.status_code == 200
    keys = _published_keys()
    # The JSON overhead of each key: the field name, two pairs of quotes, a colon and a comma.
    overhead = len('"projection_key":"",') * len(keys)
    baseline = 8_540_464
    assert len(body.content) <= baseline + sum(len(key) for key in keys) + overhead


def test_the_route_takes_no_scenario_parameter() -> None:
    """The answer resolves its own regime from the question's declared one, and so does this."""
    document_paths = json.loads(served(SHIPPED).get(f"{document.PREFIX}/openapi.json").text)[
        "paths"
    ]
    route = f"{document.PREFIX}/questions/{{question_id}}/candidates/{{candidate_key}}"
    named = {held["name"] for held in document_paths[route]["get"].get("parameters", [])}
    assert "scenario_id" not in named
    assert {"question_id", "candidate_key", "as_of"} <= named
