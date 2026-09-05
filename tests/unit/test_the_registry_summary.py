"""What the registry holds, per category, and where each figure's mark comes from.

A singleton reported as a count would say `0` for a document that resolved fine -- the same body
a caller would get for one the loader found nothing for, which is the B10 distinction collapsing
at the one endpoint whose job is to say what the registry holds (020 FR-009, FR-010, FR-054,
SC-003b, SC-003c, SC-029).
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from typing import Any

import pytest

from terezy.api.http import categories, document, summary
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.data import citation_policy, manifest
from terezy.data.declarations import resolver
from tests.data_roots import SHIPPED
from tests.http_client import served

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = SHIPPED
AS_OF = {"as_of": "2026-09-03"}


@pytest.fixture(scope="module")
def registry() -> dict[str, Any]:
    response = served(DATA_ROOT).get(f"{document.PREFIX}/registry", params=AS_OF)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_every_category_is_reported_and_no_other(registry: dict[str, Any]) -> None:
    reported = [row["category"] for row in registry["categories"]]
    assert reported == [category.id for category in categories.CATEGORIES]


def test_a_keyed_category_reports_a_count_and_a_singleton_reports_resolution(
    registry: dict[str, Any],
) -> None:
    by_id = {row["category"]: row for row in registry["categories"]}
    for category in categories.CATEGORIES:
        row = by_id[category.id]
        if categories.is_keyed(category):
            assert row["tag"] == "summary.KeyedSummary"
            assert row["declared_ids"] >= 0
            assert "resolved" not in row
        else:
            assert row["tag"] == "summary.SingletonSummary"
            assert row["resolved"] is True
            assert "declared_ids" not in row


def test_a_singleton_the_loader_found_nothing_for_reports_unresolved(tmp_path: Path) -> None:
    """The distinction a count of zero cannot make: absent is not empty."""
    scratch = tmp_path / "data"
    shutil.copytree(DATA_ROOT, scratch)
    for declared in (scratch / "seeds").glob("*.toml"):
        declared.unlink()
    response = served(scratch).get(f"{document.PREFIX}/registry", params=AS_OF)
    rows = {row["category"]: row for row in response.json()["categories"]}
    assert rows["seeds"]["resolved"] is False
    assert rows["seeds"]["files"] == []
    assert rows["goals"]["declared_ids"] == 1, "goals is keyed, and its own file is untouched"

    document_read = served(scratch).get(f"{document.PREFIX}/seeds", params=AS_OF).json()
    assert document_read["result"]["tag"] == "envelopes.NothingDeclared"
    assert document_read["result"]["reason"]


def test_every_manifest_input_appears_under_exactly_one_category(
    registry: dict[str, Any],
) -> None:
    """The association is what can be wrong; the digests are the manifest's own function."""
    declarations = resolver.answer_from_data_root(
        DATA_ROOT, base_currency=Currency.UAH, scenario_id=None
    )
    served_files = [
        (row["category"], held["file"], held["version"])
        for row in registry["categories"]
        for held in row["files"]
    ]
    by_file: dict[str, set[str]] = {}
    for category, file, _ in served_files:
        by_file.setdefault(file, set()).add(category)
    shared = {file: sorted(names) for file, names in by_file.items() if len(names) > 1}
    assert not shared, f"these files are listed under more than one category: {shared}"

    versions = {file: version for _, file, version in served_files}
    for ref in manifest.answer_input_refs(declarations):
        assert ref.file in versions, f"{ref.file} is a manifest input no category lists"
        assert versions[ref.file] == ref.version


def test_a_category_with_one_unverified_source_reports_unverified(
    registry: dict[str, Any],
) -> None:
    rows = {row["category"]: row for row in registry["categories"]}
    instruments = rows["instruments"]
    assert instruments["provenance"]["is_unverified"] is True
    assert instruments["unverified_sources"] > 0


def test_the_merged_mark_is_the_monoids_own_fold() -> None:
    """Asserted against `provenance.merge_all` rather than a union computed in the summary."""
    ask = categories.Ask(DATA_ROOT, Currency.UAH, None)
    channels = next(held for held in categories.CATEGORIES if held.id == "channels")
    assert isinstance(channels.shape, categories.Keyed)
    resolved = channels.shape.resolve(ask)
    expected = prov.merge_all(
        held.provenance for held in resolved.records.values() if hasattr(held, "provenance")
    )
    row = next(
        held
        for held in summary.of(ask, as_of=__import__("datetime").date(2026, 9, 3)).categories
        if held.category == "channels"
    )
    assert row.provenance == expected
    assert row.unverified_sources == len(prov.unverified_sources(expected))


def test_every_citation_verdict_is_the_gates_own(registry: dict[str, Any]) -> None:
    """The gate imports the same lists this serves, so there is no second copy to drift."""
    gate = _provenance_gate()
    assert gate.SOURCED_DIRS is citation_policy.SOURCED_DIRS
    assert gate.EXEMPT_DIRS is citation_policy.EXEMPT_DIRS
    for row in registry["categories"]:
        verdict = row["citations"]
        top = row["directory"].split("/", 1)[0]
        if row["directory"].endswith(".toml"):
            expected = row["directory"] != gate.KINDS_FILE
        else:
            expected = top in gate.SOURCED_DIRS
        assert (verdict["tag"] == "citation_policy.CitationsRequired") is expected, row
        if not expected:
            assert verdict["reason"], "an exemption is served with the gate's recorded reason"


def test_an_exempt_category_carries_the_gates_wording(registry: dict[str, Any]) -> None:
    gate = _provenance_gate()
    exempt = {
        row["directory"].split("/", 1)[0]: row["citations"]["reason"]
        for row in registry["categories"]
        if row["citations"]["tag"] == "citation_policy.CitationsExempt"
        and not row["directory"].endswith(".toml")
    }
    assert exempt
    for directory, reason in exempt.items():
        assert reason == gate.EXEMPT_DIRS[directory]


def test_moving_a_directory_between_the_lists_changes_the_verdict() -> None:
    """The mutation, performed: a sourced directory named exempt reads as exempt."""
    verdict = citation_policy.verdict_for("instruments")
    assert isinstance(verdict, citation_policy.CitationsRequired)
    unlisted = "commitments"
    with pytest.raises(ValueError, match="neither SOURCED_DIRS nor EXEMPT_DIRS"):
        citation_policy.verdict_for(unlisted)


def _provenance_gate() -> Any:
    """`scripts/` is not a package, so the gate is imported by path."""
    spec = importlib.util.spec_from_file_location(
        "check_provenance_under_test", REPO_ROOT / "scripts" / "check_provenance.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
