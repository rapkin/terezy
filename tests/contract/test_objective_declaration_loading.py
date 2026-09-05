"""Every refusal the objective-set declaration owes, one assertion each (019 SC-003).

FR-001: the objectives are **declared data with no default**, on the precedent of 004's segment
bound, 002's staleness threshold and 014's candidate ceiling -- *a forgotten line must never read
as a chosen policy*. Here that rule is sharper than usual: which criteria a comparison is taken
over is the decision itself, so a default would be the tool choosing what the answer means.

Every broken variant is a textual mutation of the **shipped** file, so each case also proves
`data/objectives/owner-001.toml` contains what this test thinks it does. A battery written
against an invented template keeps passing after the shipped format changes underneath it.

**FR-011c's acyclicity floor is deliberately not among these cases.** A declaration file does not
carry the magnitudes the slack depends on, so a load-time check written against the bare constant
would pass a band five orders of magnitude too small; its criterion is SC-004's and SC-007's.
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
SHIPPED = DATA_ROOT / "objectives" / "owner-001.toml"


def _is_comment(line: str) -> bool:
    """The shipped file argues for its numbers in prose quoting its own field names, so a naive
    search would edit the explanation and leave the declaration valid."""
    return line.lstrip().startswith("#")


def _replace(text: str, old: str, new: str) -> str:
    """One textual edit to the first declaring line, refusing to silently do nothing."""
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if old in line and not _is_comment(line):
            lines[index] = line.replace(old, new, 1)
            return "".join(lines)
    pytest.fail(f"the shipped declaration no longer contains {old!r}; this test is stale")


def _drop_line(text: str, needle: str) -> str:
    """Remove the first declaring line containing ``needle`` -- how a field goes missing."""
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if needle in line and not _is_comment(line):
            return "".join(lines[:index] + lines[index + 1 :])
    pytest.fail(f"the shipped declaration no longer contains {needle!r}; this test is stale")


def _written(tmp_path: Path, text: str, name: str = "broken.toml") -> Path:
    target = tmp_path / name
    target.write_text(text, encoding="utf-8")
    return target


def _broken(tmp_path: Path, old: str, new: str) -> Path:
    return _written(tmp_path, _replace(SHIPPED.read_text(encoding="utf-8"), old, new))


def _missing(tmp_path: Path, needle: str) -> Path:
    return _written(tmp_path, _drop_line(SHIPPED.read_text(encoding="utf-8"), needle))


def _refused(path: Path) -> DeclarationError:
    with pytest.raises(DeclarationError) as raised:
        loader.objectives_from_file(path)
    return raised.value


def _scratch_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _resolved(root: Path) -> DeclarationError:
    with pytest.raises(DeclarationError) as raised:
        resolver.answer_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)
    return raised.value


class TestTheShippedFileIsWhatTheBatteryMutates:
    def test_it_loads(self) -> None:
        declared = loader.objectives_from_file(SHIPPED)
        assert declared.id == "money-and-when"
        assert declared.owner_id == "owner-001"


class TestTheDirectoryAndTheIds:
    def test_an_empty_directory_refuses_naming_it_and_the_absent_default(
        self, tmp_path: Path
    ) -> None:
        root = _scratch_root(tmp_path)
        (root / "objectives" / SHIPPED.name).unlink()
        broken = _resolved(root)
        assert broken.file == root / "objectives"
        assert "no *.toml declarations" in broken.problem
        assert "default" in broken.problem

    def test_two_files_declaring_one_set_id_refuse_naming_both(self, tmp_path: Path) -> None:
        root = _scratch_root(tmp_path)
        shutil.copy(SHIPPED, root / "objectives" / "a-second-copy.toml")
        broken = _resolved(root)
        both = {"owner-001.toml", "a-second-copy.toml"}
        assert "money-and-when" in broken.problem
        assert broken.file.name in both
        assert (both - {broken.file.name}).pop() in broken.problem

    def test_a_set_the_owner_does_not_own_refuses_naming_the_owner_field(
        self, tmp_path: Path
    ) -> None:
        root = _scratch_root(tmp_path)
        target = root / "objectives" / SHIPPED.name
        target.write_text(
            _replace(SHIPPED.read_text(encoding="utf-8"), 'id = "owner-001"', 'id = "someone"'),
            encoding="utf-8",
        )
        broken = _resolved(root)
        assert broken.field_path == "owner.id"
        assert "someone" in broken.problem


class TestTheCriterionAndTheDirection:
    def test_a_criterion_outside_the_closed_set_names_the_field_and_what_exists(
        self, tmp_path: Path
    ) -> None:
        broken = _refused(_broken(tmp_path, "money_at_the_endpoint", "the_rate"))
        assert broken.field_path == "objective_set.objective[0].criterion"
        assert "the_rate" in broken.problem
        assert broken.remedy is not None
        assert "all_money_back_on" in broken.remedy

    def test_an_objective_with_no_criterion_refuses(self, tmp_path: Path) -> None:
        broken = _refused(_missing(tmp_path, 'criterion = "money_at_the_endpoint"'))
        assert "criterion" in broken.problem

    def test_a_direction_outside_the_closed_set_refuses(self, tmp_path: Path) -> None:
        broken = _refused(_broken(tmp_path, '"more_is_better"', '"sooner_is_better"'))
        assert broken.field_path == "objective_set.objective[0].direction"
        assert broken.remedy is not None
        assert "less_is_better" in broken.remedy

    def test_an_objective_with_no_direction_refuses(self, tmp_path: Path) -> None:
        broken = _refused(_missing(tmp_path, 'direction = "more_is_better"'))
        assert "direction" in broken.problem

    def test_one_criterion_twice_refuses_naming_it(self, tmp_path: Path) -> None:
        broken = _refused(_broken(tmp_path, '"all_money_back_on"', '"money_at_the_endpoint"'))
        assert "money_at_the_endpoint" in broken.problem

    def test_a_set_stating_it_has_no_objective_refuses(self, tmp_path: Path) -> None:
        """``objective = []`` is a file that says it compares on nothing, which is not a policy.

        Written out rather than omitted, because an omitted array is refused one step earlier by
        the schema and would pass this for the shape stage's reason instead of for FR-001's.
        """
        text = SHIPPED.read_text(encoding="utf-8")
        head = text[: text.index("  [[objective_set.objective]]")] + "objective = []\n"
        broken = _refused(_written(tmp_path, head))
        assert broken.field_path == "objective_set.objective"
        assert "no objective" in broken.problem


class TestTheBandIsOneShapeAndAWidth:
    def test_an_objective_with_no_band_refuses_naming_the_shapes(self, tmp_path: Path) -> None:
        broken = _refused(_missing(tmp_path, "fraction_of_the_question_amount = 0.0001"))
        assert broken.field_path == "objective_set.objective[0].band"
        assert "no band shape" in broken.problem

    def test_two_shapes_on_one_band_refuse(self, tmp_path: Path) -> None:
        broken = _refused(
            _broken(
                tmp_path,
                "fraction_of_the_question_amount = 0.0001",
                "fraction_of_the_question_amount = 0.0001\n    days = 3",
            )
        )
        assert broken.field_path == "objective_set.objective[0].band"
        assert "exactly one" in broken.problem

    def test_a_negative_band_refuses(self, tmp_path: Path) -> None:
        broken = _refused(_broken(tmp_path, "= 0.0001", "= -0.0001"))
        assert "-0.0001" in broken.problem

    def test_a_band_of_zero_refuses_and_says_why_zero_is_not_a_width(self, tmp_path: Path) -> None:
        """Zero is refused for its own reason and it is not the negative one: a band of zero can
        never exceed the slack it has to clear, so it would refuse at every run instead."""
        broken = _refused(_broken(tmp_path, "= 0.0001", "= 0.0"))
        assert "slack" in broken.problem

    def test_a_non_finite_band_refuses(self, tmp_path: Path) -> None:
        broken = _refused(_broken(tmp_path, "= 0.0001", "= inf"))
        assert broken.field_path.endswith("fraction_of_the_question_amount")
        assert "indistinguishable" in broken.problem

    def test_a_fraction_on_a_date_criterion_names_the_criterion_and_its_shapes(
        self, tmp_path: Path
    ) -> None:
        broken = _refused(_broken(tmp_path, "days = 7", "fraction_of_the_question_amount = 0.1"))
        assert "all_money_back_on" in broken.problem
        assert broken.remedy is not None
        assert "days" in broken.remedy

    def test_a_day_count_that_is_not_whole_refuses_at_the_shape_stage(self, tmp_path: Path) -> None:
        broken = _refused(_broken(tmp_path, "days = 7", "days = 7.5"))
        assert "days" in broken.field_path or "days" in broken.problem

    def test_a_money_band_that_is_neither_shape_refuses(self, tmp_path: Path) -> None:
        broken = _refused(_broken(tmp_path, "fraction_of_the_question_amount = 0.0001", "days = 5"))
        assert "money_at_the_endpoint" in broken.problem
        assert broken.remedy is not None
        assert "fraction_of_the_question_amount" in broken.remedy

    def test_an_amount_without_its_currency_refuses_rather_than_guessing_one(
        self, tmp_path: Path
    ) -> None:
        broken = _refused(
            _broken(tmp_path, "fraction_of_the_question_amount = 0.0001", "amount = 5.0")
        )
        assert "currency" in broken.problem

    def test_an_absolute_band_with_its_currency_is_legal_beside_the_fraction(
        self, tmp_path: Path
    ) -> None:
        """FR-011d keeps both money shapes: the clarification asked for a hryvnia figure and was
        answered in percent, so permitting only the shape used would refuse the one asked for."""
        declared = loader.objectives_from_file(
            _broken(
                tmp_path,
                "fraction_of_the_question_amount = 0.0001",
                'amount = 5.0\n    currency = "UAH"',
            )
        )
        band = declared.objectives[0].band
        assert getattr(band, "amount").amount == pytest.approx(5.0)  # noqa: B009


class TestTheFileShapeItself:
    def test_an_unknown_field_refuses_naming_it(self, tmp_path: Path) -> None:
        broken = _refused(_broken(tmp_path, 'id = "money-and-when"', 'id = "x"\nweight = 0.5'))
        assert "weight" in broken.problem

    def test_a_blank_set_id_refuses(self, tmp_path: Path) -> None:
        broken = _refused(_broken(tmp_path, '"money-and-when"', '""'))
        assert broken.field_path == "objective_set.id"
