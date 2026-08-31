"""The belief an early-exit figure rests on, and every refusal it owes.

015 FR-032. A horizon means the money comes out at its end, so an instrument that outlives the
window is sold at a price somebody quoted *today*. Whether that quote still holds on the exit
date is nobody's observation -- if a platform committed to it, it would be a declared term and
there would be no assumption -- so it is the owner's stated belief, declared with no default and
marked on every figure computed through it.

A subdirectory under ``data/scenarios/``, on ``data/scenarios/inflation/``'s precedent:
``scenarios/*.toml`` is globbed and validated as scenario documents and ``glob`` does not
recurse, so a sibling file would be read as a broken scenario.
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
DECLARED = DATA_ROOT / "scenarios" / "early_exit" / "owner-001.toml"


def _scratch_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _resolve(root: Path) -> object:
    return resolver.tuple_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)


def _assert_names_file_and_field(exc: DeclarationError, file: Path, contains: str) -> None:
    assert exc.file == file
    assert contains in exc.field_path, f"{exc.field_path!r} does not locate {contains!r}"


def test_the_shipped_belief_loads() -> None:
    owner_id, assumption = loader.early_exit_from_file(DECLARED)
    assert owner_id == "owner-001"
    assert assumption.is_assumption is True
    assert assumption.rationale.strip()


def test_the_shipped_data_root_carries_it_into_the_registries() -> None:
    """Every comparison can reach an early exit, so every registry states the belief."""
    declarations = resolver.tuple_from_data_root(
        DATA_ROOT, base_currency=Currency.UAH, scenario_id=None
    )
    assert declarations.registries.spread_holds.rationale.strip()


def test_a_missing_rationale_is_refused(tmp_path: Path) -> None:
    """A belief nobody argued for is the invented number Principle I exists to prevent."""
    path = tmp_path / "early_exit.toml"
    path.write_text(
        DECLARED.read_text(encoding="utf-8").replace("rationale", "# rationale", 1),
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        loader.early_exit_from_file(path)
    _assert_names_file_and_field(caught.value, path, "rationale")


def test_is_assumption_false_is_refused(tmp_path: Path) -> None:
    """There is no observed case. A quote a platform commits to is a *term*, not a belief."""
    path = tmp_path / "early_exit.toml"
    path.write_text(
        DECLARED.read_text(encoding="utf-8").replace(
            "is_assumption = true", "is_assumption = false", 1
        ),
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        loader.early_exit_from_file(path)
    _assert_names_file_and_field(caught.value, path, "is_assumption")


def test_an_unknown_field_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "early_exit.toml"
    path.write_text(
        DECLARED.read_text(encoding="utf-8") + '\nnote = "unrecognised"\n', encoding="utf-8"
    )
    with pytest.raises(DeclarationError) as caught:
        loader.early_exit_from_file(path)
    _assert_names_file_and_field(caught.value, path, "note")


def test_an_absent_directory_is_refused(tmp_path: Path) -> None:
    """No default, and the absence of the file is the absence of the policy (FR-032)."""
    root = _scratch_root(tmp_path)
    DECLARED.name  # noqa: B018 -- names the file the next line removes
    (root / "scenarios" / "early_exit" / "owner-001.toml").unlink()
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    assert caught.value.file == root / "scenarios" / "early_exit"


def test_two_declared_beliefs_are_refused(tmp_path: Path) -> None:
    """Two beliefs cannot both be in force, and taking either would be one by file order."""
    root = _scratch_root(tmp_path)
    shutil.copy2(DECLARED, root / "scenarios" / "early_exit" / "owner-002.toml")
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    assert caught.value.file == root / "scenarios" / "early_exit"


def test_a_belief_belonging_to_another_owner_is_refused(tmp_path: Path) -> None:
    """Principle VII: what this person believes about a spread is not what another believes."""
    root = _scratch_root(tmp_path)
    target = root / "scenarios" / "early_exit" / "owner-001.toml"
    target.write_text(
        target.read_text(encoding="utf-8").replace('"owner-001"', '"owner-002"', 1),
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    _assert_names_file_and_field(caught.value, target, "owner")
