"""The group vocabulary, and the label an instrument carries to join one.

015 FR-007a. A group is a **declared label**, never a rule: an instrument says which groups it
is in, `data/groups.toml` says which groups exist, and nothing computes membership. This module
is the loading half of that -- every refusal the two declarations owe, plus the shipped
membership, which is the labelling judgement this feature had to make and is therefore pinned
rather than described.

Every broken variant is a mutation of a **shipped** file, on
``tests/contract/test_composition_declaration.py``'s construction: a battery written against an
invented template keeps passing after the shipped format changes underneath it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError
from tests import answer_registries as fixtures
from tests import data_roots
from tests import observations as obs

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = data_roots.with_fixtures()
GROUPS = DATA_ROOT / "groups.toml"

OVDP = "ovdp"
INZHUR = "inzhur"

FIXTURES_IN_OVDP = frozenset(
    {"ovdp_synthetic_a", "ovdp_synthetic_b", "ovdp_enumerated_a", "ovdp_enumerated_mirror"}
)
"""The invented bonds the owner's word ``ovdp`` reaches.

Pinned rather than derived, because a fixture's label **is** a judgement and a test that read
it back off the file would assert that the file equals itself. ``enumerated_out_of_order`` is
deliberately absent: 016 declares ``UA4000235865``, the real issue that fixture is modelled on
and names in its own header, so keeping the label would put one piece of paper in the group
twice -- two candidates with two sets of cash flows, differing only in that one is invented.
015 FR-007b's deduplication cannot catch it, because it deduplicates by id and these are two
ids for one security (016 FR-027a).
"""

DECLARED_MEMBERSHIP: dict[str, frozenset[str]] = {
    OVDP: FIXTURES_IN_OVDP | frozenset(obs.declared_isins()),
    INZHUR: frozenset({"inzhur_reit", "inzhur_miltech"}),
}
"""What the owner's two words resolve to over the composed registry.

The real half is **derived** from the two observation files rather than listed, which is the
whole argument for a group: an issue joins by carrying the label and nothing here changes.
"""

IN_NO_GROUP = frozenset({"enumerated_taxable_x", "synthetic_fund_c", "enumerated_out_of_order"})
"""The three the registry declares and the owner's question does not reach.

The first is fixed income and is not an OVDP; the second's own header says its whole purpose is
that it is different from the Inzhur funds. Both are the reason FR-007a forbids inferring a
group from a class -- and the third is the fixture 016 FR-027a unlabelled, which is why a group
is a label and not a rule: no rule over a class, a venue, a tax class or an id prefix could
have excluded it.
"""


def _scratch_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _edit(path: Path, old: str, new: str) -> None:
    """One textual edit to the first *declaring* line, refusing to silently do nothing."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for index, line in enumerate(lines):
        if old in line and not line.lstrip().startswith("#"):
            lines[index] = line.replace(old, new, 1)
            path.write_text("".join(lines), encoding="utf-8")
            return
    pytest.fail(f"{path.name} no longer declares {old!r}; this test is stale")


def _assert_names_file_and_field(exc: DeclarationError, file: Path, contains: str) -> None:
    assert exc.file == file
    assert contains in exc.field_path, f"{exc.field_path!r} does not locate {contains!r}"


# ---------------------------------------------------------------------------
# The shipped vocabulary, and the shipped labels
# ---------------------------------------------------------------------------


def test_the_shipped_groups_file_loads() -> None:
    declared = loader.groups_from_file(GROUPS)
    assert {group.id for group in declared} == set(DECLARED_MEMBERSHIP)
    assert all(group.name for group in declared)


def test_the_shipped_labels_are_what_the_owners_words_resolve_to() -> None:
    labelled: dict[str, set[str]] = {group: set() for group in DECLARED_MEMBERSHIP}
    for identifier, labels in fixtures.declared_labels().items():
        for group in labels:
            labelled[group].add(identifier)
    assert {name: frozenset(ids) for name, ids in labelled.items()} == DECLARED_MEMBERSHIP


def test_three_declared_instruments_are_in_no_group() -> None:
    """Their own files say what they are for, and none is what the owner asked about."""
    labels = fixtures.declared_labels()
    assert {name for name, groups in labels.items() if not groups} == IN_NO_GROUP


# ---------------------------------------------------------------------------
# Refusals the groups file owes
# ---------------------------------------------------------------------------


def test_a_duplicate_group_id_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "groups.toml"
    path.write_text(
        f'[[group]]\nid = "{OVDP}"\nname = "One"\n\n[[group]]\nid = "{OVDP}"\nname = "Two"\n',
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        loader.groups_from_file(path)
    _assert_names_file_and_field(caught.value, path, "id")


def test_an_empty_group_id_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "groups.toml"
    path.write_text('[[group]]\nid = ""\nname = "Nameless"\n', encoding="utf-8")
    with pytest.raises(DeclarationError) as caught:
        loader.groups_from_file(path)
    _assert_names_file_and_field(caught.value, path, "id")


def test_an_unknown_field_in_the_groups_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "groups.toml"
    path.write_text(
        f'[[group]]\nid = "{OVDP}"\nname = "One"\nnote = "unrecognised"\n', encoding="utf-8"
    )
    with pytest.raises(DeclarationError) as caught:
        loader.groups_from_file(path)
    _assert_names_file_and_field(caught.value, path, "note")


def test_an_empty_groups_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "groups.toml"
    path.write_text("", encoding="utf-8")
    with pytest.raises(DeclarationError) as caught:
        loader.groups_from_file(path)
    assert caught.value.file == path


# ---------------------------------------------------------------------------
# Refusals the label owes -- checked where the relation lives, across files
# ---------------------------------------------------------------------------


def test_an_instrument_naming_an_undeclared_group_is_refused(tmp_path: Path) -> None:
    """FR-007a. Curated data's typos are defects; a *question*'s are the answer's content."""
    root = _scratch_root(tmp_path)
    target = root / "instruments" / "ovdp_synthetic_a.toml"
    _edit(target, f'groups       = ["{OVDP}"]', 'groups       = ["ovdb"]')
    with pytest.raises(DeclarationError) as caught:
        resolver.from_data_root(root)
    _assert_names_file_and_field(caught.value, target, "groups")
    assert "ovdb" in caught.value.problem


def test_a_fund_naming_an_undeclared_group_is_refused(tmp_path: Path) -> None:
    """Asserted for both declaration kinds: one check that covered one of them is half a check."""
    root = _scratch_root(tmp_path)
    target = root / "instruments" / "inzhur_reit.toml"
    _edit(target, f'groups       = ["{INZHUR}"]', 'groups       = ["inzhr"]')
    with pytest.raises(DeclarationError) as caught:
        resolver.from_data_root(root)
    _assert_names_file_and_field(caught.value, target, "groups")


def test_an_instrument_naming_one_group_twice_is_refused(tmp_path: Path) -> None:
    """A repeated label is a typo, not a stronger claim of membership."""
    root = _scratch_root(tmp_path)
    target = root / "instruments" / "ovdp_synthetic_a.toml"
    _edit(target, f'groups       = ["{OVDP}"]', f'groups       = ["{OVDP}", "{OVDP}"]')
    with pytest.raises(DeclarationError) as caught:
        resolver.from_data_root(root)
    _assert_names_file_and_field(caught.value, target, "groups")


def test_an_instrument_with_no_groups_key_is_refused(tmp_path: Path) -> None:
    """No default (research D2). A forgotten line must not read as *in no group*.

    That is the regression FR-008a names and no test can catch downstream: an issue declared in
    016 without its label leaves the count lower than the owner expects, and nothing knows what
    he expected. Required here, the same mistake is a load failure naming the file.
    """
    root = _scratch_root(tmp_path)
    target = root / "instruments" / "ovdp_synthetic_a.toml"
    text = target.read_text(encoding="utf-8")
    target.write_text(
        "".join(
            line
            for line in text.splitlines(keepends=True)
            if not (line.startswith("groups") and not line.lstrip().startswith("#"))
        ),
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        resolver.from_data_root(root)
    _assert_names_file_and_field(caught.value, target, "groups")


def test_an_absent_groups_file_is_refused(tmp_path: Path) -> None:
    """The vocabulary is not optional: without it every label is unresolvable."""
    root = _scratch_root(tmp_path)
    (root / "groups.toml").unlink()
    with pytest.raises(DeclarationError) as caught:
        resolver.from_data_root(root)
    assert caught.value.file == root / "groups.toml"
