"""Every refusal the segment-bound declaration owes, and the gate it must not move.

``contracts/composition-declaration.md`` has a table of six refusals plus two field rules, and
this module is that table executed. The construction is
``tests/contract/test_spendable_declaration_loading.py``'s, restated rather than imported so
neither battery can break the other: **every broken variant is a mutation of the shipped file**,
so each case also proves ``data/composition/owner-001.toml`` contains what the test thinks it
contains. A battery written against an invented template keeps passing after the shipped format
changes underneath it, which is how a suite like this rots.

**Two assertions apply to every case** (FR-006, and feature 002's FR-024 before it): the raised
:class:`~terezy.data.declarations.errors.DeclarationError` names the *file* that was loaded and
its ``field_path`` locates the problem.

**The distinction this whole battery is about.** ``max_segments = 1`` is a *choice* -- composition
off, only declared routes are candidates -- and it loads. A **missing** ``max_segments`` is a
forgotten line and is refused, by the rule that refuses a default staleness threshold (002
FR-028). A permissive default here would make a registry silently stop looking one segment out,
and the corridor it stopped finding would be indistinguishable from one nobody declared.

**The last tests are the provenance gate, confirmed rather than assumed.** The bound is owner
policy -- how far this person is willing to let a search run -- and there is no observed value in
the file for a source to vouch for. The gate is **fail-closed** over the data tree, so being
absent from ``SOURCED_DIRS`` is an *error*, not an exemption: ``composition`` is unscanned only
because it is named in ``EXEMPT_DIRS`` with its reason recorded beside it. Both halves are
asserted.
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
COMPOSITION = DATA_ROOT / "composition" / "owner-001.toml"


def _is_comment(line: str) -> bool:
    """Whether a line is a TOML comment.

    The shipped fixture explains itself in prose that quotes its own field names, so a naive
    text search would edit the explanation of ``max_segments`` instead of the declaration of it
    -- leaving the file valid and the test asserting an error that never came.
    """
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


def _broken(tmp_path: Path, old: str, new: str, name: str = "broken.toml") -> Path:
    """The shipped composition file with one line edited, where a loader can be pointed at it."""
    target = tmp_path / name
    target.write_text(_replace(COMPOSITION.read_text(encoding="utf-8"), old, new), encoding="utf-8")
    return target


def _scratch_root(tmp_path: Path) -> Path:
    """A whole copy of ``data/``, so a cross-file rule can be broken in one file."""
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _resolve(root: Path) -> resolver.CompositionDeclarations:
    return resolver.composition_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)


def _assert_names_file_and_field(exc: DeclarationError, file: Path, contains: str) -> None:
    """FR-006's two halves: which file, and where in it."""
    assert exc.file == file
    assert contains in exc.field_path, f"field_path {exc.field_path!r} does not locate {contains!r}"


# ---------------------------------------------------------------------------
# The shipped declaration loads, and resolves against the shipped data root
# ---------------------------------------------------------------------------


def test_the_shipped_composition_file_loads() -> None:
    owner_id, bound = loader.composition_from_file(COMPOSITION)
    assert owner_id == "owner-001"
    assert bound.max_segments >= 1


def test_the_shipped_data_root_resolves_for_composition() -> None:
    declarations = _resolve(DATA_ROOT)
    assert declarations.composition_file == COMPOSITION
    assert declarations.bound.max_segments >= 1
    # The spendable list and the ramp declarations come along, because a composed exit chain
    # has to end at a declared spendable endpoint (FR-022) and every segment is a declared
    # route.
    assert declarations.coverage.spendable
    assert "monobank_uah" in declarations.coverage.ramp.venues


def test_a_bound_of_one_is_a_choice_and_loads(tmp_path: Path) -> None:
    """The explicit way to turn composition off, and it is **not** the same as a missing bound.

    A bound of 1 admits exactly the declared routes and nothing composed. The neighbouring
    test refuses a *missing* bound, and the two together are the whole point of this
    declaration: a choice and a forgotten line must never look alike.
    """
    path = _broken(tmp_path, "max_segments = ", "max_segments = 1  # ")
    _, bound = loader.composition_from_file(path)
    assert bound.max_segments == 1


# ---------------------------------------------------------------------------
# Refusals the loader owns: one file, read in isolation
# ---------------------------------------------------------------------------


def test_a_missing_max_segments_is_refused(tmp_path: Path) -> None:
    """FR-006: no permissive default. A forgotten line is not a policy."""
    path = tmp_path / "absent.toml"
    path.write_text(
        _drop_line(COMPOSITION.read_text(encoding="utf-8"), "max_segments"), encoding="utf-8"
    )
    with pytest.raises(DeclarationError) as caught:
        loader.composition_from_file(path)
    _assert_names_file_and_field(caught.value, path, "max_segments")


def test_a_bound_below_one_is_refused(tmp_path: Path) -> None:
    """A bound of zero admits nothing, including declared routes.

    It is not a way to disable composition -- that is a bound of 1 -- it is a broken registry,
    and a run that quietly returned no candidates for it would report every corridor as
    unreachable.
    """
    path = _broken(tmp_path, "max_segments = ", "max_segments = 0  # ")
    with pytest.raises(DeclarationError) as caught:
        loader.composition_from_file(path)
    _assert_names_file_and_field(caught.value, path, "max_segments")
    assert "1" in caught.value.problem


def test_a_non_integer_bound_is_refused(tmp_path: Path) -> None:
    """``STRICT`` config, as every other declaration. Two and a half segments is not a chain."""
    path = _broken(tmp_path, "max_segments = ", "max_segments = 2.5  # ")
    with pytest.raises(DeclarationError) as caught:
        loader.composition_from_file(path)
    _assert_names_file_and_field(caught.value, path, "max_segments")


def test_a_quoted_bound_is_refused(tmp_path: Path) -> None:
    """Strict mode turns coercion off: a quoted number is a string, and a string is not a bound."""
    path = _broken(tmp_path, "max_segments = ", 'max_segments = "3"  # ')
    with pytest.raises(DeclarationError) as caught:
        loader.composition_from_file(path)
    _assert_names_file_and_field(caught.value, path, "max_segments")


def test_an_extra_key_is_refused(tmp_path: Path) -> None:
    """An ignored field is a declared policy that does nothing."""
    path = _broken(tmp_path, "max_segments = ", 'note = "unrecognised"\nmax_segments = ')
    with pytest.raises(DeclarationError) as caught:
        loader.composition_from_file(path)
    _assert_names_file_and_field(caught.value, path, "note")


def test_a_missing_composition_table_is_refused(tmp_path: Path) -> None:
    """No default is substituted for an absent table (FR-024)."""
    path = tmp_path / "no-table.toml"
    path.write_text('[owner]\nid = "owner-001"\n', encoding="utf-8")
    with pytest.raises(DeclarationError) as caught:
        loader.composition_from_file(path)
    _assert_names_file_and_field(caught.value, path, loader.COMPOSITION_TABLE)


def test_a_blank_owner_id_is_refused(tmp_path: Path) -> None:
    path = _broken(tmp_path, 'id = "owner-001"', 'id = ""')
    with pytest.raises(DeclarationError) as caught:
        loader.composition_from_file(path)
    _assert_names_file_and_field(caught.value, path, "owner.id")


def test_an_unparseable_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "broken.toml"
    path.write_text("[composition\nmax_segments = 3\n", encoding="utf-8")
    with pytest.raises(DeclarationError) as caught:
        loader.composition_from_file(path)
    assert caught.value.file == path


# ---------------------------------------------------------------------------
# Refusals the resolver owns: they need the streams and the data root
# ---------------------------------------------------------------------------


def test_an_owner_who_does_not_own_the_streams_is_refused(tmp_path: Path) -> None:
    """How far this person will let a search run is a fact about *him* (Principle VII).

    A bound belonging to somebody else would decide this owner's reach, which is feature 003's
    argument about the spendable list applied to the one knob this feature adds.
    """
    root = _scratch_root(tmp_path)
    target = root / resolver.COMPOSITION_DIR / "owner-001.toml"
    target.write_text(
        _replace(target.read_text(encoding="utf-8"), 'id = "owner-001"', 'id = "owner-002"'),
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    _assert_names_file_and_field(caught.value, target, "owner.id")


def test_an_empty_composition_directory_is_refused(tmp_path: Path) -> None:
    """FR-006: the absence of the file is the absence of the policy, and is refused by name.

    A mistyped path and an unstated policy are indistinguishable downstream, and one of them is
    a mistake -- so the directory is reported rather than read as "do not compose".
    """
    root = _scratch_root(tmp_path)
    for path in (root / resolver.COMPOSITION_DIR).glob("*.toml"):
        path.unlink()
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    assert caught.value.file == root / resolver.COMPOSITION_DIR


def test_a_second_owner_file_is_refused_by_name(tmp_path: Path) -> None:
    """One owner today (spec Assumptions), and two policies cannot both be in force.

    Merging them silently would let one owner decide the other's reach -- and this file is
    per-owner precisely so that cannot happen. Feature 003's precedent, applied unchanged.
    """
    root = _scratch_root(tmp_path)
    shutil.copy(
        root / resolver.COMPOSITION_DIR / "owner-001.toml",
        root / resolver.COMPOSITION_DIR / "owner-002.toml",
    )
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    assert caught.value.file == root / resolver.COMPOSITION_DIR
    assert "owner-002.toml" in caught.value.problem


# ---------------------------------------------------------------------------
# The provenance gate, confirmed with the new directory present (research.md D8)
# ---------------------------------------------------------------------------


def _provenance_module() -> ModuleType:
    """``scripts/check_provenance.py`` imported by path -- ``scripts/`` is not a package."""
    spec = importlib.util.spec_from_file_location(
        "check_provenance_composition_under_test", REPO_ROOT / "scripts" / "check_provenance.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_composition_directory_is_exempt_by_name_and_never_sourced() -> None:
    """Both halves, because the gate is fail-closed and only one of them is an exemption.

    Absent from ``SOURCED_DIRS`` is an **error** under a fail-closed gate, not a way to be out
    of scope. The directory goes unscanned only because it is named in ``EXEMPT_DIRS`` with a
    reason a reviewer can read. If it ever has to move into ``SOURCED_DIRS``, a number that
    describes the world leaked into a policy file, and that is the finding this test exists to
    make loud.
    """
    module: Any = _provenance_module()
    assert "composition" not in module.SOURCED_DIRS
    assert "composition" in module.EXEMPT_DIRS
    assert module.EXEMPT_DIRS["composition"].strip(), (
        "an exemption with no reason recorded beside it is an allowlist entry, which is the "
        "fail-open shape this gate was changed to close"
    )


SECOND_OWNER_STREAM = """# SYNTHETIC FIXTURE -- a second owner's salary, from a contract test.

[[stream]]
id         = "salary_two"
owner_id   = "owner-002"
currency   = "UAH"
amount     = 0.0
cadence    = "monthly"
arrives_at = "monobank_uah"

  [stream.indexation]
  policy = "none"
"""
"""A stream belonging to somebody else, in the same data root.

It arrives where the owner's own salary does, so if it were resolved it would be enumerated
against **this** owner's declared reach -- one person's stated policy deciding how far another
person's money is allowed to travel, and therefore which corridors he is shown at all.
"""


def test_a_second_owners_streams_in_the_data_root_are_refused_not_blended(
    tmp_path: Path,
) -> None:
    """Principle VII, on the side a membership check leaves open -- **inherited, not re-armed.**

    ``ramp_from_data_root`` globs every ``streams/*.toml``, so two owners' streams load together,
    and a run that enumerated the other owner's streams against this owner's declared reach would
    apply one person's stated policy to another person's registry.

    ⚙ **The refusal comes from the coverage resolution this record builds on**, not from a
    composition-specific check. ``resolve_composition`` takes an already-resolved
    ``CoverageDeclarations``, and the spendable list's owner check has already refused the
    foreign stream by then -- so a second copy in ``_check_composition_owner`` was unreachable
    code and was removed. This test is what keeps the inheritance honest: composition must not
    grow an entry point that skips it.
    """
    root = _scratch_root(tmp_path)
    foreign = root / "streams" / "owner-002.toml"
    foreign.write_text(SECOND_OWNER_STREAM, encoding="utf-8")
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    _assert_names_file_and_field(caught.value, foreign, "owner_id")
    assert "owner-002" in caught.value.problem
    assert "owner-001" in caught.value.problem
    assert "salary_two" in caught.value.problem
