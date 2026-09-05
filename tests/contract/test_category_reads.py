"""Every category, read over the shipped data: the ids it declares and nothing else.

Checked over all of them rather than a sample, with each category's shape read off the mapping
rather than assumed (020 SC-001, SC-002a, SC-005c, SC-027, SC-028).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from terezy.api.http import categories, document
from terezy.core.primitives.currency import Currency
from tests.data_roots import SHIPPED
from tests.http_client import served

DATA_ROOT = SHIPPED
AS_OF = {"as_of": "2026-09-03"}


@pytest.fixture(scope="module")
def client() -> Any:
    return served(DATA_ROOT)


def _ask(scenario_id: str | None = None) -> categories.Ask:
    return categories.Ask(DATA_ROOT, Currency.UAH, scenario_id)


def _get(client: Any, path: str, **params: str) -> dict[str, Any]:
    response = client.get(f"{document.PREFIX}{path}", params={**AS_OF, **params})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.mark.contract
@pytest.mark.parametrize("category", categories.CATEGORIES, ids=lambda held: held.id)
def test_a_listing_is_exactly_what_the_resolver_declares(
    client: Any, category: categories.Category
) -> None:
    body = _get(client, f"/{category.id}")
    assert body["category"] == category.id
    assert body["as_of"] == AS_OF["as_of"]
    if isinstance(category.shape, categories.Keyed):
        assert body["ids"] == sorted(category.shape.resolve(_ask()).records)
    else:
        assert "ids" not in body
        assert body["result"]["tag"]


@pytest.mark.contract
@pytest.mark.parametrize(
    "category",
    [held for held in categories.CATEGORIES if categories.is_keyed(held)],
    ids=lambda held: held.id,
)
def test_every_declared_id_reads_back(client: Any, category: categories.Category) -> None:
    shape = category.shape
    assert isinstance(shape, categories.Keyed)
    declared = sorted(shape.resolve(_ask()).records)
    assert declared, f"{category.id} declares nothing, so the read is untested"
    for record_id in declared:
        body = _get(client, f"/{category.id}/{record_id}")
        assert body["result"]["tag"] != "envelopes.CategoryHasNoSuchId"
        assert body["fields"], "a read describes the record it returned"


@pytest.mark.contract
@pytest.mark.parametrize(
    "category",
    [held for held in categories.CATEGORIES if categories.is_keyed(held)],
    ids=lambda held: held.id,
)
def test_an_id_nobody_declares_is_a_typed_refusal(
    client: Any, category: categories.Category
) -> None:
    """Never a load error: the trap FR-008 names is copying the raise that means a broken root."""
    body = _get(client, f"/{category.id}/nothing-declares-this")
    result = body["result"]
    assert result["tag"] == "envelopes.CategoryHasNoSuchId"
    assert result["category"] == category.id
    assert result["wanted_id"] == "nothing-declares-this"
    assert result["declared_ids"] == sorted(result["declared_ids"])
    assert result["reason"]


@pytest.mark.contract
def test_a_read_and_a_refusal_have_the_same_body_shape(client: Any) -> None:
    found = _get(client, "/venues/inzhur")
    refused = _get(client, "/venues/nothing-declares-this")
    assert set(found) == set(refused)
    assert found["result"]["tag"] != refused["result"]["tag"]


@pytest.mark.contract
@pytest.mark.parametrize("category", categories.CATEGORIES, ids=lambda held: held.id)
def test_every_read_names_the_scenario_it_resolved_under(
    client: Any, category: categories.Category
) -> None:
    assert _get(client, f"/{category.id}")["scenario_id"] is None


@pytest.mark.contract
def test_a_declared_scenario_changes_what_a_scenario_scoped_category_returns(
    client: Any,
) -> None:
    """`/spendable` is the one `tests/contract/test_coverage_scenario_scoping.py` pins."""
    under_none = _get(client, "/spendable")
    under_war = _get(client, "/spendable", scenario_id="war_end")
    assert under_none["scenario_id"] is None
    assert under_war["scenario_id"] == "war_end"


@pytest.mark.contract
def test_a_category_with_no_scenario_refuses_the_parameter(client: Any) -> None:
    """A parameter that decides nothing is worse than absent, so it is not advertised."""
    response = client.get(f"{document.PREFIX}/venues", params={**AS_OF, "scenario_id": "war_end"})
    assert response.status_code == 200
    assert response.json()["scenario_id"] is None


@pytest.mark.contract
def test_as_of_is_required(client: Any) -> None:
    """No default and no clock read (owner decision 2026-09-03)."""
    response = client.get(f"{document.PREFIX}/venues")
    assert response.status_code == 422
    assert "as_of" in response.text


@pytest.mark.contract
@pytest.mark.parametrize(
    "category",
    [held for held in categories.CATEGORIES if categories.is_keyed(held)],
    ids=lambda held: held.id,
)
def test_a_read_states_the_file_that_declared_it(
    client: Any, category: categories.Category
) -> None:
    shape = category.shape
    assert isinstance(shape, categories.Keyed)
    first = sorted(shape.resolve(_ask()).records)[0]
    declared_in = _get(client, f"/{category.id}/{first}")["declared_in"]
    if isinstance(declared_in, dict):
        assert declared_in["tag"] == "envelopes.FileNotRecorded"
        assert declared_in["reason"]
    else:
        assert not Path(declared_in).is_absolute()
        assert (DATA_ROOT / declared_in).is_file()


@pytest.mark.contract
def test_the_categories_with_no_file_map_are_the_ones_pinned() -> None:
    """One member, measured. A second would be a deliberate edit rather than a silent gap."""
    without = {
        category.id
        for category in categories.CATEGORIES
        if isinstance(category.shape, categories.Keyed)
        and isinstance(category.shape.resolve(_ask()).files, categories.NoFileMap)
    }
    assert without == {"tax-timing"}


@pytest.mark.contract
def test_a_scenario_nobody_declares_is_refused_as_a_parameter(client: Any) -> None:
    """Not as a broken data root: the resolver's error means `data/` is at fault, and a caller
    who named an undeclared scenario would be sent there to look for a fault that is not there.
    """
    response = client.get(
        f"{document.PREFIX}/spendable", params={**AS_OF, "scenario_id": "nothing-declares-this"}
    )
    assert response.status_code == 400
    body = response.json()
    assert body["tag"] == "envelopes.ScenarioNotDeclared"
    assert body["declared_ids"] == ["war_end"]


@pytest.mark.contract
def test_a_union_field_names_every_member_it_may_hold(client: Any) -> None:
    """Naming only the first told a client that every instrument's terms were `BondTerms`,
    which is false for every enumerated one."""
    body = _get(client, "/instruments/UA4000207518")
    described = {held["name"]: held for held in body["fields"]}
    assert described["terms"]["kind"] == "union"
    assert set(described["terms"]["of"]) == {"interface.BondTerms", "interface.EnumeratedTerms"}
    assert body["result"]["terms"]["tag"] in described["terms"]["of"]


@pytest.mark.contract
def test_a_mapping_field_is_described_by_what_its_values_are(client: Any) -> None:
    """Found by review: the generic walk visits a mapping's key first, so an enum-keyed mapping
    was labelled with the type of its keys."""
    described = {held["name"]: held for held in _get(client, "/tax-timing/ua")["fields"]}
    assert described["methods"]["kind"] == "mapping"
    assert described["methods"]["of"] == ["year.MethodStanding"]
