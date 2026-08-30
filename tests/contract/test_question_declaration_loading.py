"""Every refusal a question file owes, and the two it deliberately does not make.

015 FR-001 through FR-006, SC-005 and SC-029. A question is a declaration under
``data/questions/`` and is loaded by the discipline every other declaration is: **fail loudly**
on a malformed or unknown field, naming the file and the field, with no default for anything.

**The two it does not make.** A subject word that names nothing does not refuse -- it is
FR-009's population and the most useful line in the answer. And a benchmark outside the
subjects is a whole-answer ``Refused`` rather than a load failure, because deciding it needs the
registry the file has not been resolved against yet.

Every broken variant is a mutation of the **shipped** question, on
``tests/contract/test_composition_declaration.py``'s construction.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from terezy.core.primitives.currency import Currency
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
QUESTION = DATA_ROOT / "questions" / "fifty-thousand.toml"

SALARY = "salary_uah"
CONTRACT = "contract_usd"


def _scratch_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _edited(tmp_path: Path, *swaps: tuple[str, str], name: str = "broken.toml") -> Path:
    """The shipped question with one or more textual edits to *declaring* lines."""
    lines = QUESTION.read_text(encoding="utf-8").splitlines(keepends=True)
    for old, new in swaps:
        for index, line in enumerate(lines):
            if old in line and not line.lstrip().startswith("#"):
                lines[index] = line.replace(old, new, 1)
                break
        else:
            pytest.fail(f"the shipped question no longer declares {old!r}; this test is stale")
    target = tmp_path / name
    target.write_text("".join(lines), encoding="utf-8")
    return target


def _dropped(tmp_path: Path, needle: str, name: str = "broken.toml") -> Path:
    """The shipped question with one declaring line removed -- how a field goes missing."""
    lines = QUESTION.read_text(encoding="utf-8").splitlines(keepends=True)
    for index, line in enumerate(lines):
        if needle in line and not line.lstrip().startswith("#"):
            target = tmp_path / name
            target.write_text("".join(lines[:index] + lines[index + 1 :]), encoding="utf-8")
            return target
    pytest.fail(f"the shipped question no longer declares {needle!r}; this test is stale")


def _resolve(root: Path) -> resolver.AnswerDeclarations:
    return resolver.answer_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)


def _refused_at(path: Path, contains: str) -> DeclarationError:
    with pytest.raises(DeclarationError) as caught:
        loader.question_from_file(path)
    assert caught.value.file == path
    assert contains in caught.value.field_path, (
        f"{caught.value.field_path!r} does not locate {contains!r}"
    )
    return caught.value


# ---------------------------------------------------------------------------
# The shipped question loads, and resolves against the shipped registry
# ---------------------------------------------------------------------------


def test_the_shipped_question_loads() -> None:
    question = loader.question_from_file(QUESTION)
    assert question.subjects == ("cash", "ovdp", "inzhur", "btc")
    assert question.every_declared_instrument is False
    assert len(question.horizons) == 3
    assert sorted(question.amounts) == [CONTRACT, SALARY]
    assert sorted(question.plans) == ["inzhur_miltech", "inzhur_reit", "ovdp"]


def test_the_shipped_data_root_resolves_for_the_answer() -> None:
    declarations = _resolve(DATA_ROOT)
    assert declarations.question_files["fifty-thousand-hryvnia"] == QUESTION
    assert declarations.candidates.ceiling.max_candidates >= 1
    assert declarations.tuples.registries.spread_holds.rationale


# ---------------------------------------------------------------------------
# Refusals one file carries on its own (SC-005)
# ---------------------------------------------------------------------------


def test_an_unknown_field_is_refused(tmp_path: Path) -> None:
    _refused_at(_edited(tmp_path, ("asked_on ", 'note = "x"\nasked_on ')), "note")


def test_a_missing_field_is_refused(tmp_path: Path) -> None:
    _refused_at(_dropped(tmp_path, "benchmark    ="), "benchmark")


def test_a_duplicated_subject_is_refused(tmp_path: Path) -> None:
    """It would be counted twice in the one line that says what the answer actually covered."""
    error = _refused_at(
        _edited(tmp_path, ("subjects     =", 'subjects     = ["ovdp", "ovdp"]  #')), "subjects"
    )
    assert "ovdp" in error.problem


def test_two_identical_horizons_are_refused(tmp_path: Path) -> None:
    """Two identical sections are not two answers, and the cross-horizon reading keys by them."""
    _refused_at(_edited(tmp_path, ('end   = "2026-12-01"', 'end   = "2026-10-01"')), "horizon")


def test_a_horizon_running_backwards_is_refused(tmp_path: Path) -> None:
    _refused_at(_edited(tmp_path, ('end   = "2026-10-01"', 'end   = "2026-08-01"')), "horizon")


def test_a_question_with_no_horizon_is_refused(tmp_path: Path) -> None:
    text = QUESTION.read_text(encoding="utf-8")
    target = tmp_path / "no-horizon.toml"
    target.write_text(
        "\n".join(block for block in text.split("\n\n") if "[[question.horizon]]" not in block),
        encoding="utf-8",
    )
    _refused_at(target, "horizon")


def test_an_empty_subject_list_is_refused(tmp_path: Path) -> None:
    """Not the way to ask about everything: omission must never read as *everything*."""
    _refused_at(_edited(tmp_path, ("subjects     =", "subjects     = []  #")), "subjects")


def test_stating_both_a_subject_list_and_the_every_instrument_token_is_refused(
    tmp_path: Path,
) -> None:
    error = _refused_at(
        _edited(tmp_path, ("subjects     =", "every_declared_instrument = true\nsubjects     =")),
        "subjects",
    )
    assert "both" in error.problem


def test_stating_neither_is_refused(tmp_path: Path) -> None:
    error = _refused_at(_dropped(tmp_path, "subjects     ="), "subjects")
    assert "neither" in error.problem


def test_the_every_instrument_token_declared_false_is_refused(tmp_path: Path) -> None:
    """It states nothing at all: neither a list nor the token."""
    _refused_at(
        _edited(
            tmp_path,
            ("subjects     =", "every_declared_instrument = false\n#"),
        ),
        "every_declared_instrument",
    )


def test_two_amounts_for_one_stream_are_refused(tmp_path: Path) -> None:
    _refused_at(
        _edited(tmp_path, ('stream   = "contract_usd"', 'stream   = "salary_uah"')), "stream"
    )


def test_an_unrecognised_continuation_assumption_is_refused(tmp_path: Path) -> None:
    """There is no nearest match: *reinvest* would need terms nobody declared."""
    _refused_at(
        _edited(tmp_path, ('continuation = "hold_as_cash"', 'continuation = "reinvest"')),
        "continuation",
    )


def test_a_plan_of_an_unrecognised_kind_is_refused(tmp_path: Path) -> None:
    """Declared rather than inferred from which fields are present."""
    _refused_at(
        _edited(tmp_path, ('kind               = "bond"', 'kind               = "bnod"')), "kind"
    )


def test_a_bond_plan_carrying_a_fund_field_is_refused(tmp_path: Path) -> None:
    """A silently dropped field is a stated choice that does nothing."""
    _refused_at(
        _edited(
            tmp_path,
            (
                'coupon_policy      = "hold_cash"',
                'coupon_policy      = "hold_cash"\nliquidity_mode     = "practice"',
            ),
        ),
        "liquidity_mode",
    )


def test_a_fund_plan_missing_its_liquidity_mode_is_refused(tmp_path: Path) -> None:
    _refused_at(_dropped(tmp_path, 'liquidity_mode     = "practice"'), "liquidity_mode")


def test_a_chosen_point_declared_not_an_assumption_is_refused(tmp_path: Path) -> None:
    """A point inside a stated range is somebody's choice, and the field says so unmissably."""
    _refused_at(
        _edited(tmp_path, ("is_assumption = true", "is_assumption = false")), "is_assumption"
    )


# ---------------------------------------------------------------------------
# Refusals that need a second file (SC-005, SC-029)
# ---------------------------------------------------------------------------


def _into_root(tmp_path: Path, *swaps: tuple[str, str]) -> tuple[Path, Path]:
    root = _scratch_root(tmp_path)
    target = root / "questions" / "fifty-thousand.toml"
    text = target.read_text(encoding="utf-8")
    for old, new in swaps:
        lines = text.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if old in line and not line.lstrip().startswith("#"):
                lines[index] = line.replace(old, new, 1)
                break
        else:
            pytest.fail(f"the shipped question no longer declares {old!r}")
        text = "".join(lines)
    target.write_text(text, encoding="utf-8")
    return root, target


def test_an_amount_in_a_currency_the_stream_does_not_deliver_is_refused(tmp_path: Path) -> None:
    root, target = _into_root(tmp_path, ('currency = "UAH"', 'currency = "USD"'))
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    assert caught.value.file == target
    assert "currency" in caught.value.field_path
    assert "USD" in caught.value.problem


def test_an_amount_for_an_undeclared_stream_is_refused(tmp_path: Path) -> None:
    root, target = _into_root(tmp_path, ('stream   = "salary_uah"', 'stream   = "salary_eur"'))
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    assert caught.value.file == target
    assert "salary_eur" in caught.value.problem


@pytest.mark.parametrize("stream_id", [SALARY, CONTRACT])
def test_a_declared_stream_with_no_stated_amount_is_refused(tmp_path: Path, stream_id: str) -> None:
    """Asserted for the stream that yields candidates **and** for the one that yields none.

    The second is the case that passes silently: its pairs never reach the comparison, so
    nothing raises and the answer is simply missing a stream nobody mentioned.
    """
    root = _scratch_root(tmp_path)
    target = root / "questions" / "fifty-thousand.toml"
    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if f'"{stream_id}"' in line)
    target.write_text("".join(lines[: start - 1] + lines[start + 3 :]), encoding="utf-8")
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    assert caught.value.file == target
    assert stream_id in caught.value.problem


def test_a_question_belonging_to_another_owner_is_refused(tmp_path: Path) -> None:
    root, target = _into_root(tmp_path, ('id = "owner-001"', 'id = "owner-002"'))
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    assert caught.value.file == target
    assert "owner" in caught.value.field_path


def test_two_files_declaring_one_question_id_are_refused(tmp_path: Path) -> None:
    root = _scratch_root(tmp_path)
    shutil.copy2(QUESTION, root / "questions" / "again.toml")
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    assert "fifty-thousand-hryvnia" in caught.value.problem


def test_an_empty_questions_directory_is_refused(tmp_path: Path) -> None:
    root = _scratch_root(tmp_path)
    (root / "questions" / "fifty-thousand.toml").unlink()
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    assert caught.value.file == root / "questions"


def test_a_subject_that_names_nothing_does_not_refuse(tmp_path: Path) -> None:
    """FR-009's asymmetry, from the load side. ``cash`` and ``btc`` are already exactly this."""
    root, _ = _into_root(tmp_path, ("subjects     =", 'subjects     = ["not_a_thing"]  #'))
    assert _resolve(root).questions["fifty-thousand-hryvnia"].subjects == ("not_a_thing",)
