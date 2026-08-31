"""A result without a manifest is not a result, and an answer's manifest names every input.

015 SC-006, SC-007 and SC-008, and required-test row **H3**. Two claims that only hold together:
one digest moves per edited file, and the manifest names **every** file the run read rather than
a sample of them. The second is walked from the resolved declarations' own ``Path`` fields --
an independent computation from the one that builds the references, which is what stops the
assertion being that a function equals itself.

**The manifest is not single-projection shaped any more.** An answer has many instruments over
many horizons and no one holding, so those four facts sit behind ``projection``, which is
``None`` here -- inventing a holding to fill them would be a false record rather than an
incomplete one.
"""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path
from typing import Any

import pytest

from terezy.api.answer import answer_question
from terezy.core.primitives.currency import Currency
from terezy.core.results.answer import Answer
from terezy.core.results.coverage import IMPLICIT_REGIME_ID
from terezy.data import manifest as run_manifest
from tests import answer_registries as fixtures


def _answered(root: Path = fixtures.DATA_ROOT) -> object:
    return answer_question(
        root, fixtures.OWNERS_QUESTION, as_of=fixtures.AS_OF, base_currency=Currency.UAH
    )


def _scratch_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(fixtures.DATA_ROOT, root)
    return root


def _declared_files(value: object, seen: set[int] | None = None) -> set[Path]:
    """Every ``Path`` the resolved declarations name, walked generically.

    A second, independent walk: the references are built by naming each family, and this finds
    them by type. A family somebody adds to the resolver and forgets to record shows up here.
    """
    seen = set() if seen is None else seen
    if id(value) in seen:
        return set()
    seen.add(id(value))
    if isinstance(value, Path):
        return {value} if value.suffix == ".toml" else set()
    found: set[Path] = set()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for field in dataclasses.fields(value):
            found |= _declared_files(getattr(value, field.name), seen)
    elif isinstance(value, dict):
        for item in value.values():
            found |= _declared_files(item, seen)
    elif isinstance(value, tuple | list | frozenset | set):
        for item in value:
            found |= _declared_files(item, seen)
    return found


def test_the_manifest_records_the_run_and_not_a_holding_it_did_not_have() -> None:
    run: Any = _answered()
    assert run.manifest.projection is None
    assert run.manifest.as_of == fixtures.AS_OF
    assert run.manifest.regime_id == IMPLICIT_REGIME_ID
    assert run.manifest.owner_id == "owner-001"
    assert run.manifest.code_version
    assert run.manifest.encoding == run_manifest.ENCODING
    assert run.manifest.seed is None


def test_the_question_is_an_input_reference_like_any_other_declaration() -> None:
    """FR-025. An answer traces to the sentence that asked for it."""
    run: Any = _answered()
    questions = [ref for ref in run.manifest.inputs if ref.kind == "question"]
    assert [ref.id for ref in questions] == [fixtures.OWNERS_QUESTION]
    assert questions[0].file == "questions/fifty-thousand.toml"


def test_the_manifest_names_every_file_the_run_read() -> None:
    """SC-008, and the half of H3 that a sample cannot claim."""
    declarations = fixtures.declarations()
    named = {ref.file for ref in run_manifest.answer_input_refs(declarations)}
    walked = {run_manifest.file_name(path) for path in _declared_files(declarations)}
    assert walked - named == set(), sorted(walked - named)


def test_the_inputs_are_ordered_by_kind_and_id_rather_than_by_the_filesystem() -> None:
    run: Any = _answered()
    assert list(run.manifest.inputs) == sorted(
        run.manifest.inputs, key=lambda ref: (ref.kind, ref.id)
    )


@pytest.mark.parametrize(
    "relative",
    [
        "questions/fifty-thousand.toml",
        "instruments/ovdp_synthetic_a.toml",
        "access/instruments.toml",
        "groups.toml",
        "candidates/owner-001.toml",
        "composition/owner-001.toml",
        "scenarios/early_exit/owner-001.toml",
    ],
)
def test_editing_one_file_moves_exactly_one_digest(tmp_path: Path, relative: str) -> None:
    """SC-007. A version that said otherwise would answer a question nobody asked."""
    root = _scratch_root(tmp_path)
    before: Any = _answered(root)
    target = root / relative
    target.write_text(target.read_text(encoding="utf-8") + "\n# a comment\n", encoding="utf-8")
    after: Any = _answered(root)

    versions_before = {ref.file: ref.version for ref in before.manifest.inputs}
    versions_after = {ref.file: ref.version for ref in after.manifest.inputs}
    moved = {name for name in versions_before if versions_before[name] != versions_after.get(name)}
    assert moved == {run_manifest.file_name(target)}


def test_answering_twice_produces_an_equal_digest() -> None:
    """SC-006. Bit-identity, so agreement means agreement to the last bit."""
    first: Any = _answered()
    second: Any = _answered()
    assert first.manifest.result_digest == second.manifest.result_digest
    assert first.answer == second.answer


def test_the_answers_digest_is_a_function_of_the_canonical_form_alone(tmp_path: Path) -> None:
    """Provenance is excluded by design, so a documentation edit cannot move a result."""
    root = _scratch_root(tmp_path)
    before: Any = _answered(root)
    target = root / "instruments" / "ovdp_synthetic_a.toml"
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            'verified_on  = ""', 'verified_on  = "2026-08-31"', 1
        ),
        encoding="utf-8",
    )
    after: Any = _answered(root)
    assert after.manifest.result_digest == before.manifest.result_digest
    assert after.manifest.inputs != before.manifest.inputs


def test_the_roll_up_names_the_unverified_sources_behind_the_figures() -> None:
    """The shipped registry is entirely unverified, so a clean roll-up would be a lie."""
    run: Any = _answered()
    assert isinstance(run.answer, Answer)
    assert run.manifest.unverified_sources
