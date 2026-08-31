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
from dataclasses import replace
from pathlib import Path
from typing import Any, Final, get_args

import pytest

from terezy.api.answer import answer_question
from terezy.core.primitives.currency import Currency
from terezy.core.results.answer import Answer, NoHorizonDeclared, PlanForNothing
from terezy.core.results.coverage import IMPLICIT_REGIME_ID
from terezy.data import manifest as run_manifest
from terezy.data.manifest import InputKind
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
    """SC-008, and the half of H3 that a sample cannot claim.

    Matched on the **content digest**, not on the name: the manifest's naming rule drops a
    root-level file's parent directory, and a walk that re-derived that rule here would assert
    the rule against itself. A version is what a walk can compute without knowing it.
    """
    declarations = fixtures.declarations()
    recorded = {ref.version for ref in run_manifest.answer_input_refs(declarations)}
    walked = {run_manifest.file_version(path) for path in _declared_files(declarations)}
    assert walked - recorded == set(), sorted(walked - recorded)
    assert len(walked) == len(set(_declared_files(declarations))), (
        "two declaration files with identical bytes would hide a missing reference"
    )


def test_a_root_level_input_is_named_the_same_from_any_checkout(tmp_path: Path) -> None:
    """Two copies of one registry must describe one declaration one way."""
    elsewhere = tmp_path / "registry-copy"
    shutil.copytree(fixtures.DATA_ROOT, elsewhere)
    moved: Any = _answered(elsewhere)
    here: Any = _answered()
    assert {ref.file for ref in moved.manifest.inputs} == {ref.file for ref in here.manifest.inputs}
    assert "groups.toml" in {ref.file for ref in here.manifest.inputs}


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
    was = run_manifest.file_version(target)
    target.write_text(target.read_text(encoding="utf-8") + "\n# a comment\n", encoding="utf-8")
    after: Any = _answered(root)

    versions_before = {ref.file: ref.version for ref in before.manifest.inputs}
    versions_after = {ref.file: ref.version for ref in after.manifest.inputs}
    moved = {name for name in versions_before if versions_before[name] != versions_after.get(name)}
    # The expected name is read off the **pre-edit** manifest by content, not derived from the
    # path: five recorded files are called `owner-001.toml` and three of the targets are, so a
    # basename comparison would pass while a sibling's digest moved instead of this one's.
    edited = {name for name, version in versions_before.items() if version == was}
    assert len(edited) == 1, sorted(edited)
    assert moved == edited


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


def test_two_refusals_of_two_kinds_do_not_share_one_digest() -> None:
    """A constant would give every refused run one identity, and the CLI prints it as such."""
    declarations = fixtures.declarations()
    question = fixtures.owners_question()
    digests = {
        run_manifest.of_answer(
            declarations=declarations,
            question=question,
            as_of=fixtures.AS_OF,
            result=None,
            refusal=refusal,
        ).result_digest
        for refusal in (
            NoHorizonDeclared(),
            PlanForNothing(named="one"),
            PlanForNothing(named="another"),
        )
    }
    assert len(digests) == 3

    assert (
        run_manifest.of_answer(
            declarations=declarations,
            question=replace(question, horizons=()),
            as_of=fixtures.AS_OF,
            result=None,
            refusal=NoHorizonDeclared(),
        ).result_digest
        in digests
    )


NOT_READ_BY_AN_ANSWER: Final = frozenset({"cpi_series", "inflation_assumption", "official_rate"})
"""Series an answer reads none of, named here so their absence is a claim rather than a gap.

The first two are 007's, and an answer computes no real-terms figure. The third is 018's, and
015 FR-021 is the reason: **no rate is derived and none is read from a series.** A tuple whose
figure would need one refuses by name -- ``inzhur_reit`` says so on the shipped registry -- and
that refusal is only honest while nothing behind it quietly consults the National Bank. The
answer's registries carry no ``AssessmentRules``, which is where an official rate would enter.
"""


def test_every_input_kind_the_set_admits_is_one_the_walk_produces() -> None:
    """A member nothing constructs reads as coverage the manifest does not have."""
    produced = {ref.kind for ref in run_manifest.answer_input_refs(fixtures.declarations())}
    admitted = set(get_args(InputKind))
    unreachable = admitted - produced - NOT_READ_BY_AN_ANSWER
    assert not unreachable, sorted(unreachable)


def test_an_answer_reads_no_rate_series_at_all() -> None:
    """015 FR-021 from the input side: the series cannot reach a figure it never loaded.

    Asserted over the resolved registries rather than by scanning imports, because the way a
    rate would arrive is a *value* -- an ``AssessmentRules`` carrying an ``official_rate`` --
    and a scan for the word would pass a run that was handed one.
    """
    registries = fixtures.declarations().tuples.registries
    assert not [name for name in dir(registries) if "rule" in name or "rate" in name.lower()]
