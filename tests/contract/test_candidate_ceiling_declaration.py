"""Every refusal the candidate-ceiling declaration owes, and the gate it must not move.

014 FR-019: the ceiling is **declared data with no default**, on the precedent of 004's segment
bound and 002's staleness threshold -- *a forgotten line must never read as a chosen policy*.

Every broken variant is a mutation of the shipped file, so each case also proves
``data/candidates/owner-001.toml`` contains what the test thinks it does. A battery written
against an invented template keeps passing after the shipped format changes underneath it.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from terezy.core.primitives.currency import Currency
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from types import ModuleType

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
CEILING = DATA_ROOT / "candidates" / "owner-001.toml"


def _is_comment(line: str) -> bool:
    """The shipped fixture argues for its number in prose quoting its own field names, so a
    naive search would edit the explanation and leave the file valid."""
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
    """Remove the first declaring line containing ``needle`` -- how a field goes missing."""
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if needle in line and not _is_comment(line):
            return "".join(lines[:index] + lines[index + 1 :])
    pytest.fail(f"the shipped fixture no longer declares {needle!r}; this test is stale")


def _written(tmp_path: Path, text: str, name: str = "broken.toml") -> Path:
    target = tmp_path / name
    target.write_text(text, encoding="utf-8")
    return target


def _broken(tmp_path: Path, old: str, new: str) -> Path:
    """The shipped ceiling file with one line edited, where a loader can be pointed at it."""
    return _written(tmp_path, _replace(CEILING.read_text(encoding="utf-8"), old, new))


def _scratch_root(tmp_path: Path) -> Path:
    """A whole copy of ``data/``, so a cross-file rule can be broken in one file."""
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _resolve(root: Path) -> resolver.CandidateDeclarations:
    return resolver.candidates_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)


def _assert_names_file_and_field(exc: DeclarationError, file: Path, contains: str) -> None:
    assert exc.file == file
    assert contains in exc.field_path, f"field_path {exc.field_path!r} does not locate {contains!r}"


# ---------------------------------------------------------------------------
# The shipped declaration loads, and resolves against the shipped data root
# ---------------------------------------------------------------------------


def test_the_shipped_ceiling_file_loads() -> None:
    owner_id, ceiling = loader.candidates_from_file(CEILING)
    assert owner_id == "owner-001"
    assert ceiling.max_candidates >= 1


def test_the_shipped_data_root_resolves_for_the_ceiling() -> None:
    declarations = _resolve(DATA_ROOT)
    assert declarations.candidates_file == CEILING
    assert declarations.ceiling.max_candidates >= 1
    # The composition declarations come along, because a candidate count is a product of what
    # the bound admits and the ceiling is the statement about that product.
    assert declarations.composition.bound.max_segments >= 1


def test_the_shipped_ceiling_admits_the_shipped_registry() -> None:
    """A ceiling below what the declarations already connect would refuse every run.

    Asserted against the registry rather than against the number, so densifying the registry
    past the declared ceiling fails here -- which is exactly the finding FR-019 exists to
    deliver, arriving at the owner rather than at a reader of the data file.
    """
    declarations = _resolve(DATA_ROOT)
    instruments = len(declarations.composition.coverage.ramp.streams) * len(
        resolver.tuple_from_data_root(
            DATA_ROOT, base_currency=Currency.UAH, scenario_id=None
        ).access
    )
    assert declarations.ceiling.max_candidates >= instruments


# ---------------------------------------------------------------------------
# Refusals the loader owns: one file, read in isolation
# ---------------------------------------------------------------------------


def test_a_missing_max_candidates_is_refused(tmp_path: Path) -> None:
    """A permissive default would let a registry that has outgrown enumeration keep going, and
    a run that took minutes would look like one the owner asked for."""
    path = _written(tmp_path, _drop_line(CEILING.read_text(encoding="utf-8"), "max_candidates"))
    with pytest.raises(DeclarationError) as caught:
        loader.candidates_from_file(path)
    _assert_names_file_and_field(caught.value, path, "candidates")


def test_a_ceiling_below_one_is_refused(tmp_path: Path) -> None:
    """Zero admits nothing at all, so every run would refuse with the registry blameless."""
    path = _broken(tmp_path, "max_candidates = ", "max_candidates = 0  # ")
    with pytest.raises(DeclarationError) as caught:
        loader.candidates_from_file(path)
    _assert_names_file_and_field(caught.value, path, "max_candidates")
    assert "0" in caught.value.problem


def test_a_ceiling_of_one_loads(tmp_path: Path) -> None:
    """The smallest registry that can produce an answer at all -- a choice, not a broken line."""
    path = _broken(tmp_path, "max_candidates = ", "max_candidates = 1  # ")
    _, ceiling = loader.candidates_from_file(path)
    assert ceiling.max_candidates == 1


def test_a_non_integer_ceiling_is_refused(tmp_path: Path) -> None:
    """Half a candidate is not a candidate, and the shape stage is where that is said."""
    path = _broken(tmp_path, "max_candidates = ", "max_candidates = 2.5  # ")
    with pytest.raises(DeclarationError) as caught:
        loader.candidates_from_file(path)
    assert caught.value.file == path


def test_a_quoted_ceiling_is_refused(tmp_path: Path) -> None:
    """A file whose type and the engine's type disagree while the answer still looks right."""
    path = _broken(tmp_path, "max_candidates = ", 'max_candidates = "1000"  # ')
    with pytest.raises(DeclarationError) as caught:
        loader.candidates_from_file(path)
    assert caught.value.file == path


def test_an_extra_key_is_refused(tmp_path: Path) -> None:
    """Principle II: a data file fails loudly on an unknown field, naming file and field."""
    path = _broken(tmp_path, "max_candidates = ", "max_kandidates = 5\nmax_candidates = ")
    with pytest.raises(DeclarationError) as caught:
        loader.candidates_from_file(path)
    assert caught.value.file == path


def test_a_missing_candidates_table_is_refused(tmp_path: Path) -> None:
    path = _written(tmp_path, '[owner]\nid = "owner-001"\n')
    with pytest.raises(DeclarationError) as caught:
        loader.candidates_from_file(path)
    assert caught.value.file == path


def test_a_blank_owner_id_is_refused(tmp_path: Path) -> None:
    """A ceiling belongs to a person, and it is resolved against that person's streams."""
    path = _broken(tmp_path, 'id = "owner-001"', 'id = ""')
    with pytest.raises(DeclarationError) as caught:
        loader.candidates_from_file(path)
    _assert_names_file_and_field(caught.value, path, "owner")


def test_an_unparseable_file_is_refused(tmp_path: Path) -> None:
    path = _written(tmp_path, "[owner\nid = 'owner-001'\n")
    with pytest.raises(DeclarationError) as caught:
        loader.candidates_from_file(path)
    assert caught.value.file == path


# ---------------------------------------------------------------------------
# Refusals only the resolver can make: relations across files
# ---------------------------------------------------------------------------


def test_an_owner_who_does_not_own_the_streams_is_refused(tmp_path: Path) -> None:
    """Principle VII. How many options this person is shown is his own policy.

    A ceiling belonging to somebody else would decide which corridors *this* owner is offered
    at all -- and, because exceeding it refuses rather than truncates, whether he is offered
    any.
    """
    root = _scratch_root(tmp_path)
    target = root / resolver.CANDIDATES_DIR / "owner-001.toml"
    target.write_text(
        _replace(target.read_text(encoding="utf-8"), 'id = "owner-001"', 'id = "owner-002"'),
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    _assert_names_file_and_field(caught.value, target, "owner")


def test_an_empty_candidates_directory_is_refused(tmp_path: Path) -> None:
    """The absence of the file is the absence of the policy, and is reported by name."""
    root = _scratch_root(tmp_path)
    for path in (root / resolver.CANDIDATES_DIR).glob("*.toml"):
        path.unlink()
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    assert caught.value.file == root / resolver.CANDIDATES_DIR


def test_a_second_owner_file_is_refused_by_name(tmp_path: Path) -> None:
    """Two ceilings cannot both be in force, and merging them by taking either is a choice."""
    root = _scratch_root(tmp_path)
    shutil.copy(
        root / resolver.CANDIDATES_DIR / "owner-001.toml",
        root / resolver.CANDIDATES_DIR / "owner-002.toml",
    )
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    assert caught.value.file == root / resolver.CANDIDATES_DIR
    assert "owner-002.toml" in caught.value.problem


# ---------------------------------------------------------------------------
# The provenance gate, confirmed with the new directory present (research.md D9)
# ---------------------------------------------------------------------------


def _provenance_module() -> ModuleType:
    """``scripts/check_provenance.py`` imported by path -- ``scripts/`` is not a package."""
    spec = importlib.util.spec_from_file_location(
        "check_provenance_candidates_under_test", REPO_ROOT / "scripts" / "check_provenance.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_candidates_directory_is_exempt_by_name_and_never_sourced() -> None:
    """Both halves: under a fail-closed gate, absent from ``SOURCED_DIRS`` is an error rather
    than a way to be out of scope. A move into it means a world-describing number leaked."""
    module: Any = _provenance_module()
    assert "candidates" not in module.SOURCED_DIRS
    assert "candidates" in module.EXEMPT_DIRS
