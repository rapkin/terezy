"""Every refusal the spendable-endpoint declaration owes, and the gate it must not move.

``contracts/spendable-schema.md`` has a table of seven refusals plus two field rules, and this
module is that table executed. The construction is
``tests/contract/test_route_declaration_loading.py``'s, restated rather than imported so neither
battery can break the other: **every broken variant is a mutation of the shipped file**, so each
case also proves ``data/spendable/owner-001.toml`` contains what the test thinks it contains. A
battery written against an invented template keeps passing after the shipped format changes
underneath it, which is how a suite like this rots.

**Two assertions apply to every case** (FR-024, and feature 002's FR-016 before it): the raised
:class:`~terezy.data.declarations.errors.DeclarationError` names the *file* that was loaded and
its ``field_path`` locates the problem. Naming the field but not the file is what pydantic's own
rendering does, and it is exactly what the loader adapts ``ValidationError`` to avoid.

**The last two tests are the provenance gate, confirmed rather than assumed** (research.md D4).
The spendable list carries no observed value -- an id, a currency code, and the owner's statement
about his own life -- so ``scripts/check_provenance.py`` does not scan ``data/spendable/``.

⚙ **It does not scan it for a stricter reason than the one D4 originally gave.** That gate is
now **fail-closed** over the whole data tree: a directory in neither ``SOURCED_DIRS`` nor
``EXEMPT_DIRS`` is an *error*, because an allowlist made a new directory the one place the gate
could not see. So being absent from ``SOURCED_DIRS`` is no longer a way to be out of scope --
the exemption has to be written into the script by name, with its argument, where a reviewer
reads it. Both halves are asserted below: **not** in ``SOURCED_DIRS``, and **in**
``EXEMPT_DIRS`` with a non-empty reason. If someone ever has to move it into ``SOURCED_DIRS``, a
number leaked into the file, and that is the finding these tests exist to make loud.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from terezy.core.primitives.currency import Currency
from terezy.core.results.coverage import SpendableEndpoint
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from types import ModuleType

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
SPENDABLE = DATA_ROOT / "spendable" / "owner-001.toml"


def _is_comment(line: str) -> bool:
    """Whether a line is a TOML comment.

    The shipped fixture explains itself in prose that quotes its own field names, so a naive
    text search would edit the explanation of ``currency`` instead of the declaration of it --
    leaving the file valid and the test asserting an error that never came.
    """
    return line.lstrip().startswith("#")


def _replace(text: str, old: str, new: str) -> str:
    """One textual edit to the first declaring line, refusing to silently do nothing.

    ``str.replace`` on a string that does not contain the needle returns the string unchanged,
    so without this a renamed field in the shipped file would turn every case below into a test
    of a *valid* file that expects an error.
    """
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
    """The shipped spendable file with one line edited, where a loader can be pointed at it."""
    target = tmp_path / name
    target.write_text(_replace(SPENDABLE.read_text(encoding="utf-8"), old, new), encoding="utf-8")
    return target


def _scratch_root(tmp_path: Path) -> Path:
    """A whole copy of ``data/``, so a cross-file rule can be broken in one file."""
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _assert_names_file_and_field(exc: DeclarationError, file: Path, contains: str) -> None:
    """FR-016's two halves: which file, and where in it."""
    assert exc.file == file
    assert contains in exc.field_path, f"field_path {exc.field_path!r} does not locate {contains!r}"


# ---------------------------------------------------------------------------
# The shipped declaration loads, and resolves against the shipped data root
# ---------------------------------------------------------------------------


def test_the_shipped_spendable_file_loads() -> None:
    owner_id, endpoints = loader.spendable_from_file(SPENDABLE)
    assert owner_id == "owner-001"
    assert SpendableEndpoint(venue_id="monobank_uah", currency=Currency.UAH) in endpoints


def test_the_shipped_data_root_resolves_for_coverage() -> None:
    declarations = resolver.coverage_from_data_root(
        DATA_ROOT, base_currency=Currency.UAH, scenario_id=None
    )
    assert declarations.spendable == frozenset(
        {SpendableEndpoint(venue_id="monobank_uah", currency=Currency.UAH)}
    )
    assert declarations.spendable_file == SPENDABLE
    # The ramp declarations come along unchanged: a coverage run audits the same registry a
    # ramp comparison costs, which is what makes FR-018's agreement checkable at all.
    assert declarations.ramp.base_currency is Currency.UAH
    assert "monobank_uah" in declarations.ramp.venues


# ---------------------------------------------------------------------------
# Refusals the loader owns: one file, read in isolation
# ---------------------------------------------------------------------------


def test_an_extra_key_is_refused(tmp_path: Path) -> None:
    """``STRICT`` config, as every other declaration file. An ignored field is a declared
    constraint that does nothing."""
    path = _broken(tmp_path, 'currency = "UAH"', 'currency = "UAH"\nnote     = "unrecognised"')
    with pytest.raises(DeclarationError) as caught:
        loader.spendable_from_file(path)
    _assert_names_file_and_field(caught.value, path, "note")


def test_an_empty_spendable_list_is_refused(tmp_path: Path) -> None:
    """research.md D13: a file with no entries would make every exit deficit 3 -- a confident
    wrong answer built out of a forgotten line.

    Declared as an explicit empty array, which is the case the *loader* owns: the list is
    present and says nothing. The neighbouring test covers the other half -- the key absent
    altogether -- because a forgotten line and a deliberate blank must not look alike, exactly
    as they must not for ``verified_on``.
    """
    path = tmp_path / "empty.toml"
    path.write_text('spendable = []\n\n[owner]\nid = "owner-001"\n', encoding="utf-8")
    with pytest.raises(DeclarationError) as caught:
        loader.spendable_from_file(path)
    _assert_names_file_and_field(caught.value, path, loader.SPENDABLE_TABLE)
    assert "deficit" in caught.value.problem


def test_a_missing_spendable_key_is_refused(tmp_path: Path) -> None:
    """No default is substituted for an absent field (FR-016). An omitted ``[[spendable]]``
    is a shape failure naming the key, not an empty list quietly assumed."""
    path = tmp_path / "absent.toml"
    path.write_text('[owner]\nid = "owner-001"\n', encoding="utf-8")
    with pytest.raises(DeclarationError) as caught:
        loader.spendable_from_file(path)
    _assert_names_file_and_field(caught.value, path, loader.SPENDABLE_TABLE)


def test_a_blank_owner_id_is_refused(tmp_path: Path) -> None:
    path = _broken(tmp_path, 'id = "owner-001"', 'id = ""')
    with pytest.raises(DeclarationError) as caught:
        loader.spendable_from_file(path)
    _assert_names_file_and_field(caught.value, path, "owner.id")


def test_a_blank_venue_is_refused(tmp_path: Path) -> None:
    path = _broken(tmp_path, 'venue    = "monobank_uah"', 'venue    = ""')
    with pytest.raises(DeclarationError) as caught:
        loader.spendable_from_file(path)
    _assert_names_file_and_field(caught.value, path, "venue")


def test_an_unmodelled_currency_code_is_refused(tmp_path: Path) -> None:
    """A currency is a closed enum, so a typo is a load-time failure rather than a fourth
    currency that never matches anything."""
    path = _broken(tmp_path, 'currency = "UAH"', 'currency = "UAX"')
    with pytest.raises(DeclarationError) as caught:
        loader.spendable_from_file(path)
    _assert_names_file_and_field(caught.value, path, "currency")


def test_a_duplicate_pair_is_refused(tmp_path: Path) -> None:
    """The loader's existing duplicate-id precedent. Two entries for one endpoint are not
    merged: the second says nothing the first does not, and a file that repeats itself is a
    file somebody edited twice."""
    path = tmp_path / "duplicated.toml"
    path.write_text(
        '[owner]\nid = "owner-001"\n\n'
        '[[spendable]]\nvenue    = "monobank_uah"\ncurrency = "UAH"\n\n'
        '[[spendable]]\nvenue    = "monobank_uah"\ncurrency = "UAH"\n',
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        loader.spendable_from_file(path)
    _assert_names_file_and_field(caught.value, path, loader.SPENDABLE_TABLE)
    assert "monobank_uah" in caught.value.problem


# ---------------------------------------------------------------------------
# Refusals the resolver owns: they need the venues, the base currency, the streams
# ---------------------------------------------------------------------------


def test_an_unknown_venue_is_refused(tmp_path: Path) -> None:
    root = _scratch_root(tmp_path)
    target = root / "spendable" / "owner-001.toml"
    target.write_text(
        _replace(
            target.read_text(encoding="utf-8"), 'venue    = "monobank_uah"', 'venue    = "nowhere"'
        ),
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        resolver.coverage_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)
    _assert_names_file_and_field(caught.value, target, "venue")
    assert "nowhere" in caught.value.problem


def test_a_venue_that_cannot_hold_the_currency_is_refused(tmp_path: Path) -> None:
    """``coinbase`` is declared dollar-only, so naming it as somewhere the owner spends
    *hryvnia* is a contradiction -- and ``Venue.currencies`` already exists for exactly this
    class of check, which is why the resolver reuses ``_check_venue`` rather than writing a
    second one."""
    root = _scratch_root(tmp_path)
    target = root / "spendable" / "owner-001.toml"
    target.write_text(
        _replace(
            target.read_text(encoding="utf-8"), 'venue    = "monobank_uah"', 'venue    = "coinbase"'
        ),
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        resolver.coverage_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)
    _assert_names_file_and_field(caught.value, target, "venue")


def test_a_non_base_currency_is_refused(tmp_path: Path) -> None:
    """FR-004: base currency only. Accepting USD would make the report decide that foreign
    cash counts as spent."""
    root = _scratch_root(tmp_path)
    target = root / "spendable" / "owner-001.toml"
    target.write_text(
        _replace(target.read_text(encoding="utf-8"), 'currency = "UAH"', 'currency = "USD"'),
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        resolver.coverage_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)
    _assert_names_file_and_field(caught.value, target, "currency")
    assert "USD" in caught.value.problem


def test_an_owner_who_does_not_own_the_streams_is_refused(tmp_path: Path) -> None:
    """``contracts/spendable-schema.md``: ``owner.id`` must match the owner of the streams it
    is resolved with. Where the owner spends is a fact about *this* person's life, and a list
    resolved against somebody else's income is two people's facts in one report."""
    root = _scratch_root(tmp_path)
    target = root / "spendable" / "owner-001.toml"
    target.write_text(
        _replace(target.read_text(encoding="utf-8"), 'id = "owner-001"', 'id = "owner-002"'),
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        resolver.coverage_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)
    _assert_names_file_and_field(caught.value, target, "owner.id")


def test_an_empty_spendable_directory_is_refused(tmp_path: Path) -> None:
    """The reason ``ramp_from_data_root`` already gives: a mistyped path and an empty world
    are indistinguishable downstream, and one of them is a mistake."""
    root = _scratch_root(tmp_path)
    for path in (root / "spendable").glob("*.toml"):
        path.unlink()
    with pytest.raises(DeclarationError) as caught:
        resolver.coverage_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)
    assert caught.value.file == root / resolver.SPENDABLE_DIR


def test_a_second_owner_file_is_refused_by_name(tmp_path: Path) -> None:
    """One owner today (spec Assumptions), and ``CoverageDeclarations`` carries one
    ``spendable_file``.

    Refused **by name** rather than silently merged, on the precedent of the ``deposit``
    fallback policy: a real thing that is not built yet and an unrecognised thing are
    different facts, and the owner acts differently on each. Merging two owners' lists would
    let one person's spendable venues decide another person's verdicts.
    """
    root = _scratch_root(tmp_path)
    shutil.copy(root / "spendable" / "owner-001.toml", root / "spendable" / "owner-002.toml")
    with pytest.raises(DeclarationError) as caught:
        resolver.coverage_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)
    assert caught.value.file == root / resolver.SPENDABLE_DIR


SECOND_OWNER_STREAM = """# SYNTHETIC FIXTURE -- a second owner's salary, from a contract test.

[[stream]]
id         = "salary_two"
owner_id   = "owner-002"
currency   = "UAH"
amount     = 0.0
cadence    = "monthly"
arrives_at = "inzhur"
credited_to = "inzhur"

  [stream.indexation]
  policy = "none"
"""
"""A stream belonging to somebody else, in the same data root.

``arrives_at = "inzhur"`` on purpose: ``inzhur`` is a destination the shipped registry has a
declared way in and out of, so if this stream were resolved it would be marked **ready** --
owner-002's verdict decided by owner-001's spendable list, which is the leak this refusal
exists to close.
"""


def test_a_second_owners_streams_in_the_data_root_are_refused_not_blended(
    tmp_path: Path,
) -> None:
    """Principle VII, on the side the spendable check used to leave open.

    ``ramp_from_data_root`` globs every ``streams/*.toml``, so two owners' streams load
    together, and the owner check asked only whether the spendable list's owner was *among*
    them. He was -- so the report went on to score the other owner's streams against this
    owner's spendable list, which is precisely what ``coverage_from_data_root``'s
    second-spendable-file refusal says cannot happen.
    """
    root = _scratch_root(tmp_path)
    foreign = root / "streams" / "owner-002.toml"
    foreign.write_text(SECOND_OWNER_STREAM, encoding="utf-8")
    with pytest.raises(DeclarationError) as caught:
        resolver.coverage_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)
    _assert_names_file_and_field(caught.value, foreign, "owner_id")
    assert "owner-002" in caught.value.problem
    assert "owner-001" in caught.value.problem
    assert "salary_two" in caught.value.problem


# ---------------------------------------------------------------------------
# The provenance gate, confirmed with the new file present (research.md D4)
# ---------------------------------------------------------------------------


def _provenance_module() -> ModuleType:
    """``scripts/check_provenance.py`` imported by path -- ``scripts/`` is not a package."""
    spec = importlib.util.spec_from_file_location(
        "check_provenance_under_test", REPO_ROOT / "scripts" / "check_provenance.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_provenance_gate_does_not_scan_the_spendable_directory() -> None:
    """``SOURCED_DIRS`` is **not** extended, and that is half the assertion.

    There is no observed value in the spendable file for a source to vouch for. If this half
    ever has to change, a number leaked into the declaration -- so the check is on the tuple
    itself rather than on the gate's exit status, which would go green either way.

    ⚙ **The claim is about ``spendable``, not about the whole tuple** (correction,
    2026-08-23). This asserted ``SOURCED_DIRS == ("tax", "instruments", "routes", "channels")``,
    which fails the day a *genuinely sourced* directory is added -- ``data/prices/``, say -- and
    fails under a test name and a docstring that send the reader to ``data/spendable/``, which
    is not what changed. Adding a sourced directory is ordinary growth and no business of this
    test; a spendable directory that started being scanned is the finding it exists to make
    loud.
    """
    module: Any = _provenance_module()
    assert "spendable" not in module.SOURCED_DIRS


LOADER_SOURCE = REPO_ROOT / "src" / "terezy" / "data" / "declarations" / "loader.py"
SPENDABLE_SECTION_BANNER = "# 003-route-coverage: the spendable-endpoint list"


def _loader_spendable_section() -> str:
    """The loader's header for this feature: its banner down to the first declaration."""
    source = LOADER_SOURCE.read_text(encoding="utf-8")
    _, banner, rest = source.partition(SPENDABLE_SECTION_BANNER)
    assert banner, f"{LOADER_SOURCE.name} no longer carries the section this test reads"
    section, marker, _ = rest.partition("SPENDABLE_TABLE")
    assert marker, "the section no longer ends at SPENDABLE_TABLE; this test is stale"
    return section


def test_the_loader_header_teaches_the_fail_closed_exemption_not_the_superseded_rule() -> None:
    """Four places state why the spendable file carries no citation. They must state one rule.

    Absence from ``SOURCED_DIRS`` used to be how a directory was out of scope. Since the gate
    became fail-closed it is an *error*, and ``spendable`` is unscanned only because it is named
    in ``EXEMPT_DIRS`` with its reason recorded. ``research.md`` D4, the schema contract,
    ``data/README.md``, the shipped TOML header and these tests were all restated to say so --
    and the loader's own header was missed, leaving the one place still teaching the old rule to
    the reader most likely to act on it.

    A textual assertion, with the limits every scan in this suite states: it pins the vocabulary
    rather than the argument. What it catches is the sentence going stale again while four
    others move on, which is exactly what happened.
    """
    section = _loader_spendable_section()
    assert "EXEMPT_DIRS" in section, (
        "the loader header explains why no citation is read here, and the reason is now the "
        "named exemption -- a header that does not mention EXEMPT_DIRS is teaching the "
        "superseded 'absent from SOURCED_DIRS is enough' rule"
    )
    assert "is not extended" not in section, (
        "'SOURCED_DIRS is not extended' is the superseded mechanism: under a fail-closed gate "
        "not being extended is an error, not an exemption"
    )


def test_the_spendable_exemption_is_argued_in_the_gate_by_name() -> None:
    """The other half, and the one the fail-closed gate added.

    Absence from ``SOURCED_DIRS`` used to be enough to be out of scope. It is now an *error*:
    the gate errors on any directory under ``data/`` it does not know, because an allowlist
    made a new directory the one place it could not see -- fail-open, in the script whose whole
    job is the opposite.

    So the exemption has to exist positively, with a reason recorded beside it, and this test
    is that requirement made executable. The reason is asserted to be substantive rather than
    merely present: an empty string would satisfy the script and defeat the point of requiring
    one, which is that a reviewer reads the argument.
    """
    module: Any = _provenance_module()
    assert "spendable" in module.EXEMPT_DIRS
    reason = module.EXEMPT_DIRS["spendable"]
    assert reason.strip(), "an exemption with a blank reason is an exemption nobody argued"
    assert "routes" in reason, "the reason must say where the numbers actually live"


def test_the_provenance_gate_stays_green_with_the_new_file_present(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirmed rather than assumed, which is the whole content of research.md D4's task.

    ``main([])`` and not ``main()``: the gate now reads a data root from ``argv`` so it can be
    pointed at a scratch tree, and under pytest a bare call would pick up pytest's own
    arguments and check a directory named ``-q``.
    """
    module: Any = _provenance_module()
    assert SPENDABLE.is_file(), "the shipped spendable declaration is missing"
    assert module.main([]) == 0
    capsys.readouterr()
