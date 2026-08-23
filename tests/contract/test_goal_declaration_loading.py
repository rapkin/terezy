"""SC-004 for goals: every refusal the goal declaration owes, naming file and field.

The seed half of ``contracts/owner-declarations.md`` is
``tests/contract/test_seed_declaration_loading.py``; this is the other half, built the same
way and for the same reason: **every broken variant is a mutation of the shipped file**, so
each case also proves ``data/goals/owner-001.toml`` contains what the test thinks it does.

**The refusal that is this feature's own is the currency one** (FR-016). A goal denominated
in dollars is refused as *not yet modelled*, naming the missing FX modelling -- never as an
invalid currency, because USD is a currency this engine models perfectly well and the thing
that is absent is the deflation-and-rate machinery that would make a USD target comparable
with a UAH one. §4.7 is explicit that the two are different goals under devaluation, so the
message must not paint the multi-currency case as closed.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

from terezy.core.primitives.currency import Currency
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
GOALS = DATA_ROOT / "goals" / "owner-001.toml"


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith("#")


def _replace(text: str, old: str, new: str) -> str:
    """One textual edit to the first declaring line, refusing to silently do nothing."""
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if old in line and not _is_comment(line):
            lines[index] = line.replace(old, new, 1)
            return "".join(lines)
    pytest.fail(f"the shipped fixture no longer declares {old!r}; this test is stale")


def _drop_line(text: str, needle: str) -> str:
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if needle in line and not _is_comment(line):
            return "".join(lines[:index] + lines[index + 1 :])
    pytest.fail(f"the shipped fixture no longer declares {needle!r}; this test is stale")


def _broken(tmp_path: Path, old: str, new: str) -> Path:
    target = tmp_path / "broken.toml"
    target.write_text(_replace(GOALS.read_text(encoding="utf-8"), old, new), encoding="utf-8")
    return target


def _without(tmp_path: Path, needle: str) -> Path:
    target = tmp_path / "missing.toml"
    target.write_text(_drop_line(GOALS.read_text(encoding="utf-8"), needle), encoding="utf-8")
    return target


def _scratch_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _assert_names_file_and_field(exc: DeclarationError, file: Path, contains: str) -> None:
    assert exc.file == file
    assert contains in exc.field_path, f"field_path {exc.field_path!r} does not locate {contains!r}"


# ---------------------------------------------------------------------------
# The shipped declaration loads, and says what it is
# ---------------------------------------------------------------------------


def test_the_shipped_goal_file_loads() -> None:
    owner_id, declared = loader.goals_from_file(GOALS)
    (goal,) = declared
    assert owner_id == "owner-001"
    assert goal.id == "flat_deposit"
    assert goal.owner_id == "owner-001"
    assert goal.currency is Currency.UAH
    assert goal.monthly_contribution is not None
    assert goal.monthly_contribution.amount == 20_000.0
    assert goal.target_sum is not None
    assert goal.target_sum.amount == 1_200_000.0


def test_the_undeclared_variable_is_none_rather_than_a_filled_in_value() -> None:
    """FR-011: the third variable is the question, so it must be absent in the record.

    A zero or a far-off date standing in for "not declared" would make the solver unable to
    tell what it was asked, and it would answer the wrong question confidently.
    """
    _, (goal,) = loader.goals_from_file(GOALS)
    assert goal.target_date is None


def test_the_shipped_file_says_on_its_face_that_it_is_synthetic() -> None:
    """FR-025."""
    assert "SYNTHETIC FIXTURE" in GOALS.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The refusal battery
# ---------------------------------------------------------------------------


def test_an_unrecognised_field_is_refused(tmp_path: Path) -> None:
    path = _broken(
        tmp_path, 'id                   = "flat_deposit"', 'id = "flat_deposit"\nrate = 0.1'
    )
    with pytest.raises(DeclarationError) as caught:
        loader.goals_from_file(path)
    _assert_names_file_and_field(caught.value, path, "rate")


def test_a_growth_rate_declared_on_the_goal_is_refused_as_an_unrecognised_field(
    tmp_path: Path,
) -> None:
    """FR-012, and the reason the unrecognised-field rule matters here specifically.

    The growth assumption is an input to the evaluation, carrying its own provenance. A rate
    accepted here would become a default nobody chose, which is the substitution FR-012 names.
    """
    path = _broken(
        tmp_path,
        'currency             = "UAH"',
        'currency             = "UAH"\nannual_growth_pct    = 12.0',
    )
    with pytest.raises(DeclarationError) as caught:
        loader.goals_from_file(path)
    _assert_names_file_and_field(caught.value, path, "annual_growth_pct")


def test_fewer_than_two_variables_is_refused_naming_what_is_missing(tmp_path: Path) -> None:
    """FR-011: the tool never fills in a variable to make a goal solvable."""
    path = _without(tmp_path, "target_sum           =")
    with pytest.raises(DeclarationError) as caught:
        loader.goals_from_file(path)
    _assert_names_file_and_field(caught.value, path, "goal")
    assert "target_sum" in caught.value.problem
    assert "target_date" in caught.value.problem


def test_a_goal_declaring_none_of_the_three_is_refused(tmp_path: Path) -> None:
    """The degenerate case of the same rule: an id and a currency are not a goal."""
    path = tmp_path / "bare.toml"
    path.write_text(
        '[owner]\nid = "owner-001"\n\n[[goal]]\nid = "bare"\ncurrency = "UAH"\n', encoding="utf-8"
    )
    with pytest.raises(DeclarationError) as caught:
        loader.goals_from_file(path)
    _assert_names_file_and_field(caught.value, path, "goal")


def test_all_three_variables_are_accepted_because_that_is_the_feasibility_question(
    tmp_path: Path,
) -> None:
    """FR-018: three fixed variables is not an over-declaration, it is a different question."""
    path = _broken(
        tmp_path,
        "target_sum           = 1_200_000.0",
        'target_sum           = 1_200_000.0\ntarget_date          = "2031-06-30"',
    )
    _, (goal,) = loader.goals_from_file(path)
    assert goal.target_date == date(2031, 6, 30)


def test_a_duplicate_goal_id_is_refused(tmp_path: Path) -> None:
    """Spec, Edge Cases: a collision, reported at load time. Two goals with one id cannot be
    told apart, so neither could be reported against."""
    path = tmp_path / "twice.toml"
    path.write_text(
        '[owner]\nid = "owner-001"\n\n'
        '[[goal]]\nid = "flat"\ncurrency = "UAH"\nmonthly_contribution = 1.0\n'
        "target_sum = 2.0\n\n"
        '[[goal]]\nid = "flat"\ncurrency = "UAH"\nmonthly_contribution = 3.0\n'
        "target_sum = 4.0\n",
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        loader.goals_from_file(path)
    _assert_names_file_and_field(caught.value, path, "goal")
    assert "flat" in caught.value.problem


def test_a_negative_contribution_is_refused(tmp_path: Path) -> None:
    """A withdrawal is not a contribution. Zero is legal -- a goal reached by growth alone --
    which is why this is a non-negativity check rather than a positivity one."""
    path = _broken(tmp_path, "monthly_contribution = 20_000.0", "monthly_contribution = -20_000.0")
    with pytest.raises(DeclarationError) as caught:
        loader.goals_from_file(path)
    _assert_names_file_and_field(caught.value, path, "monthly_contribution")


def test_a_zero_contribution_is_accepted(tmp_path: Path) -> None:
    """Spec, Edge Cases: a valid goal -- the sum grows from the starting amount alone."""
    path = _broken(tmp_path, "monthly_contribution = 20_000.0", "monthly_contribution = 0.0")
    _, (goal,) = loader.goals_from_file(path)
    assert goal.monthly_contribution is not None
    assert goal.monthly_contribution.amount == 0.0


def test_a_non_positive_target_is_refused(tmp_path: Path) -> None:
    """A target of zero is not something to aim at, and a negative one is not a target."""
    path = _broken(tmp_path, "target_sum           = 1_200_000.0", "target_sum           = 0.0")
    with pytest.raises(DeclarationError) as caught:
        loader.goals_from_file(path)
    _assert_names_file_and_field(caught.value, path, "target_sum")


def test_a_malformed_target_date_is_refused(tmp_path: Path) -> None:
    path = _broken(
        tmp_path,
        "target_sum           = 1_200_000.0",
        'target_sum           = 1_200_000.0\ntarget_date          = "2031-13-40"',
    )
    with pytest.raises(DeclarationError) as caught:
        loader.goals_from_file(path)
    _assert_names_file_and_field(caught.value, path, "target_date")


def test_an_unmodelled_currency_code_is_refused(tmp_path: Path) -> None:
    """A closed enum, so a typo is a load-time failure rather than a currency that never
    matches anything. Distinct from the *base currency* refusal below, which is about a
    currency this engine knows and cannot yet convert."""
    path = _broken(tmp_path, 'currency             = "UAH"', 'currency             = "UAX"')
    with pytest.raises(DeclarationError) as caught:
        loader.goals_from_file(path)
    _assert_names_file_and_field(caught.value, path, "currency")


def test_a_blank_goal_id_is_refused(tmp_path: Path) -> None:
    path = _broken(tmp_path, 'id                   = "flat_deposit"', 'id                   = ""')
    with pytest.raises(DeclarationError) as caught:
        loader.goals_from_file(path)
    _assert_names_file_and_field(caught.value, path, "id")


def test_an_empty_goal_list_is_a_person_with_no_goal(tmp_path: Path) -> None:
    """FR-024, research.md D9: an ordinary state, not a refusal."""
    path = tmp_path / "none.toml"
    path.write_text('goal = []\n\n[owner]\nid = "owner-001"\n', encoding="utf-8")
    owner_id, declared = loader.goals_from_file(path)
    assert owner_id == "owner-001"
    assert declared == ()


# ---------------------------------------------------------------------------
# The refusal the resolver owns: the base currency is a property of the run
# ---------------------------------------------------------------------------


def test_a_non_base_currency_goal_is_refused_as_not_yet_modelled(tmp_path: Path) -> None:
    """FR-016, G11, research.md D7 -- and the wording is the requirement, not decoration.

    The message must name the missing FX modelling and must not call the currency invalid.
    A reader told "USD is not a valid currency" would go and fix the file; a reader told "a
    dollar target cannot yet be compared with a hryvnia one because no dated rate is
    modelled" knows the file is fine and the feature is missing.
    """
    root = _scratch_root(tmp_path)
    target = root / "goals" / "owner-001.toml"
    target.write_text(
        _replace(
            target.read_text(encoding="utf-8"),
            'currency             = "UAH"',
            'currency             = "USD"',
        ),
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        resolver.seeds_and_goals_from_data_root(root, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, target, "currency")
    rendered = str(caught.value).lower()
    assert "not yet" in rendered
    assert "invalid" not in rendered
    assert "rate" in rendered or "fx" in rendered


def test_the_two_owner_files_must_name_the_same_owner(tmp_path: Path) -> None:
    """Principle VII: one run holds one person's life.

    Resolving one person's holdings beside another's goals would produce a report measuring
    somebody's portfolio against somebody else's target, and every figure in it would be
    arithmetically correct.
    """
    root = _scratch_root(tmp_path)
    target = root / "goals" / "owner-001.toml"
    target.write_text(
        _replace(target.read_text(encoding="utf-8"), 'id = "owner-001"', 'id = "owner-002"'),
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        resolver.seeds_and_goals_from_data_root(root, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, target, "owner.id")
    assert "owner-001" in caught.value.problem


def test_a_second_file_in_one_directory_is_refused(tmp_path: Path) -> None:
    """One owner today (spec Assumptions). Two files cannot both be in force, and merging
    them silently would put two people's declarations in one run."""
    root = _scratch_root(tmp_path)
    shutil.copy(root / "goals" / "owner-001.toml", root / "goals" / "owner-002.toml")
    with pytest.raises(DeclarationError) as caught:
        resolver.seeds_and_goals_from_data_root(root, base_currency=Currency.UAH)
    assert caught.value.file == root / "goals"
