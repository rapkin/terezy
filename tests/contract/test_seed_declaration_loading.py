"""SC-004 for seeds: every refusal the opening-lot declaration owes, naming file and field.

``contracts/owner-declarations.md`` has a table of refusals and this module is the seed half
of it executed. The construction is ``tests/contract/test_spendable_declaration_loading.py``'s
and it is restated rather than imported so neither battery can break the other: **every broken
variant is a mutation of the shipped file**, so each case also proves
``data/seeds/owner-001.toml`` contains what the test thinks it contains. A battery written
against an invented template keeps passing after the shipped format changes underneath it.

**Two assertions apply to every case** (FR-023): the raised
:class:`~terezy.data.declarations.errors.DeclarationError` names the *file* and its
``field_path`` locates the problem. Naming the field but not the file is what pydantic's own
rendering does, and it is what the loader adapts ``ValidationError`` to avoid.

**FR-010 is enforced by the shape rather than by a check**, and the case is here to prove it:
there is no `currency` key on a seed, so a file trying to state one is refused as an
unrecognised field. That is stronger than a validation rule -- a basis in another currency
cannot be *expressed*, so it cannot be converted at an assumed rate by a later change that
forgot the requirement.

**What is deliberately not refused here**: an acquisition date before the instrument's issue
date. That is a well-formed declaration of an impossible history, and it is the engine's typed
``InconsistentTerms`` -- the same division the loader already draws for a maturity on or before
its issue date. ``tests/unit/test_seed_opening.py`` covers it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from terezy.core.ledger import seeds
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
SEEDS = DATA_ROOT / "seeds" / "owner-001.toml"


def _is_comment(line: str) -> bool:
    """Whether a line is a TOML comment.

    The shipped fixture explains itself in prose that quotes its own field names, so a naive
    text search would edit the explanation of ``basis`` instead of the declaration of it --
    leaving the file valid and the test asserting an error that never came.
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


def _broken(tmp_path: Path, old: str, new: str) -> Path:
    """The shipped seed file with one line edited, where the loader can be pointed at it."""
    target = tmp_path / "broken.toml"
    target.write_text(_replace(SEEDS.read_text(encoding="utf-8"), old, new), encoding="utf-8")
    return target


def _without(tmp_path: Path, needle: str) -> Path:
    """The shipped seed file with one declaring line removed."""
    target = tmp_path / "missing.toml"
    target.write_text(_drop_line(SEEDS.read_text(encoding="utf-8"), needle), encoding="utf-8")
    return target


def _scratch_root(tmp_path: Path) -> Path:
    """A whole copy of ``data/``, so a cross-file rule can be broken in one file."""
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _assert_names_file_and_field(exc: DeclarationError, file: Path, contains: str) -> None:
    """FR-023's two halves: which file, and where in it."""
    assert exc.file == file
    assert contains in exc.field_path, f"field_path {exc.field_path!r} does not locate {contains!r}"


# ---------------------------------------------------------------------------
# The shipped declaration loads, and says what it is
# ---------------------------------------------------------------------------


def test_the_shipped_seed_file_loads() -> None:
    owner_id, declared = loader.seeds_from_file(SEEDS, base_currency=Currency.UAH)
    assert owner_id == "owner-001"
    assert [lot.instrument_id for lot in declared] == ["ovdp_synthetic_a", "ovdp_synthetic_b"]
    assert declared[0].quantity == 10.0
    assert declared[0].cost.amount == 9_800.0
    assert declared[0].cost.currency is Currency.UAH


def test_the_shipped_file_says_on_its_face_that_it_is_synthetic() -> None:
    """FR-025: no fixture value may be mistaken for the owner's declaration."""
    assert "SYNTHETIC FIXTURE" in SEEDS.read_text(encoding="utf-8")


def test_the_declared_basis_is_read_from_the_file_and_carries_the_owners_reason() -> None:
    """FR-006 and FR-008 at the boundary: the two words, and the reason one of them requires.

    What the loader builds is the *declaration* -- the amount as written and the basis as
    stated. It deliberately does **not** join them: ``core.ledger.seeds.seed_cost`` does that,
    so the join holds for a lot this loader never saw. The next test asserts the join.
    """
    _, declared = loader.seeds_from_file(SEEDS, base_currency=Currency.UAH)
    known, estimated = declared
    assert known.basis == seeds.KNOWN
    assert known.cost.provenance == prov.EMPTY
    assert isinstance(estimated.basis, seeds.BasisEstimated)
    assert estimated.basis.reason in estimated.basis.mark.citation
    assert estimated.basis.mark.verified_on is None


def test_the_cost_a_loaded_lot_enters_the_ledger_with_carries_its_basis_mark() -> None:
    """The join, over the shipped file: an estimated lot's cost is marked and a known one's is
    not, whichever route the lot took into the system."""
    _, declared = loader.seeds_from_file(SEEDS, base_currency=Currency.UAH)
    known, estimated = declared
    assert isinstance(estimated.basis, seeds.BasisEstimated)
    assert seeds.basis_estimated_sources(seeds.seed_cost(estimated).provenance) == frozenset(
        {estimated.basis.mark}
    )
    assert seeds.seed_cost(known).provenance == prov.EMPTY


def test_every_lot_traces_to_the_entry_that_declared_it() -> None:
    """The lot id and the declaration reference both come from the entry's position.

    Two purchases of one instrument on one date are legitimate, so identity cannot come from
    ``(instrument, date)``; and a cause that cannot be resolved back to a file is the guess
    ``CausationKind`` refuses to allow.
    """
    _, declared = loader.seeds_from_file(SEEDS, base_currency=Currency.UAH)
    assert [lot.lot_id for lot in declared] == ["seed-0", "seed-1"]
    assert declared[0].declared_at == "seeds/owner-001.toml#seed[0]"
    assert declared[1].declared_at == "seeds/owner-001.toml#seed[1]"


# ---------------------------------------------------------------------------
# The refusal battery: one file, read in isolation
# ---------------------------------------------------------------------------


def test_an_unrecognised_field_is_refused(tmp_path: Path) -> None:
    """``STRICT``, as every other declaration. A silently ignored field is a declaration
    that does nothing."""
    path = _broken(tmp_path, "quantity      = 10.0", 'quantity      = 10.0\nnote          = "?"')
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(path, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, path, "note")


def test_a_currency_key_is_refused_because_there_is_nowhere_to_state_one(tmp_path: Path) -> None:
    """FR-010, enforced structurally.

    A basis in another currency needs a rate on the acquisition date to become a base-currency
    cost, and this feature has none. Rather than accept the field and refuse the value, the
    field does not exist -- so no later change can quietly start converting it.
    """
    path = _broken(tmp_path, "cost          = 9_800.0", 'cost          = 9_800.0\ncurrency = "USD"')
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(path, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, path, "currency")


def test_a_missing_cost_is_refused(tmp_path: Path) -> None:
    """FR-006: never defaulted, never zero-filled, never back-filled from a current value."""
    path = _without(tmp_path, "cost          = 9_800.0")
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(path, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, path, "cost")


def test_a_missing_basis_declaration_is_refused(tmp_path: Path) -> None:
    """FR-006, US2 scenario 3: a cost with no statement of how well it is known.

    This is the case the whole honesty mechanism rests on. Defaulting it to "known" would
    make every forgotten declaration produce a confidently unmarked tax figure.
    """
    path = _without(tmp_path, 'basis         = "known"')
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(path, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, path, "basis")


def test_an_unrecognised_basis_word_is_refused_naming_the_two_that_work(tmp_path: Path) -> None:
    """A value that is neither ``known`` nor ``estimated`` is a typo, not a third choice."""
    path = _broken(tmp_path, 'basis         = "known"', 'basis         = "guessed"')
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(path, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, path, "basis")
    assert "estimated" in str(caught.value)


def test_an_estimated_basis_without_a_reason_is_refused(tmp_path: Path) -> None:
    """FR-008: the mark must state its reason, so the declaration must carry one."""
    path = _without(tmp_path, "reason        =")
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(path, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, path, "reason")


def test_a_blank_reason_is_refused(tmp_path: Path) -> None:
    """Present-and-empty is not a reason. A mark that says nothing is a taint flag."""
    path = _broken(tmp_path, "reason        =", 'reason        = ""  #')
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(path, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, path, "reason")


def test_a_reason_on_a_known_basis_is_refused(tmp_path: Path) -> None:
    """One of the two fields is wrong and the loader cannot know which.

    Ignoring the reason would drop something the owner wrote; treating the basis as estimated
    would mark a figure the owner said he was sure of. Both are guesses, so it refuses.
    """
    path = _broken(
        tmp_path,
        'basis         = "known"',
        'basis         = "known"\nreason        = "not sure after all"',
    )
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(path, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, path, "reason")


@pytest.mark.parametrize("quantity", ["0.0", "-4.0"])
def test_a_non_positive_quantity_is_refused(tmp_path: Path, quantity: str) -> None:
    """Spec, Edge Cases: rejected as invalid input, naming the file and the field.

    A lot may not exist at zero -- it would keep an acquisition date alive that holds nothing
    and would take its turn in the consumption order.
    """
    path = _broken(tmp_path, "quantity      = 10.0", f"quantity      = {quantity}")
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(path, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, path, "quantity")


def test_a_negative_cost_is_refused(tmp_path: Path) -> None:
    """Spec, Edge Cases: a rebate is not a basis."""
    path = _broken(tmp_path, "cost          = 9_800.0", "cost          = -1.0")
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(path, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, path, "cost")


def test_a_cost_of_zero_is_accepted_because_it_is_a_declaration(tmp_path: Path) -> None:
    """Zero is not the same claim as absent, and the difference matters here.

    A holding that genuinely cost nothing -- a gift, a bonus allocation -- has a basis of
    zero, and refusing it would force the owner to invent a number. What FR-006 forbids is a
    zero *substituted* for a cost nobody stated, which is the case above: the field is absent
    and the load fails.
    """
    path = _broken(tmp_path, "cost          = 9_800.0", "cost          = 0.0")
    _, declared = loader.seeds_from_file(path, base_currency=Currency.UAH)
    assert declared[0].cost.amount == 0.0


def test_a_malformed_date_is_refused(tmp_path: Path) -> None:
    path = _broken(tmp_path, 'acquired_on   = "2026-03-14"', 'acquired_on   = "14/03/2026"')
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(path, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, path, "acquired_on")


def test_a_quoted_number_is_refused_rather_than_coerced(tmp_path: Path) -> None:
    """``strict=True``: a file's type and the engine's type must not disagree while the
    answer still looks right."""
    path = _broken(tmp_path, "quantity      = 10.0", 'quantity      = "10.0"')
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(path, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, path, "quantity")


def test_a_blank_owner_id_is_refused(tmp_path: Path) -> None:
    """Principle VII: every per-owner row carries its owner, and an empty string is not one."""
    path = _broken(tmp_path, 'id = "owner-001"', 'id = ""')
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(path, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, path, "owner.id")


def test_a_blank_instrument_id_is_refused(tmp_path: Path) -> None:
    path = _broken(tmp_path, 'instrument_id = "ovdp_synthetic_a"', 'instrument_id = ""')
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(path, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, path, "instrument_id")


def test_a_file_that_is_not_valid_toml_is_refused_naming_the_file(tmp_path: Path) -> None:
    path = tmp_path / "broken.toml"
    path.write_text('[owner\nid = "owner-001"\n', encoding="utf-8")
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(path, base_currency=Currency.UAH)
    assert caught.value.file == path
    assert "TOML" in caught.value.problem


def test_a_missing_file_is_reported_rather_than_read_as_empty(tmp_path: Path) -> None:
    """An absent declaration is not an empty one. That distinction is made by the *caller* --
    a data root with no ``seeds/`` directory is an ordinary run -- but a path handed to the
    loader and not found is a mistyped path."""
    path = tmp_path / "nowhere.toml"
    with pytest.raises(DeclarationError) as caught:
        loader.seeds_from_file(path, base_currency=Currency.UAH)
    assert caught.value.file == path


def test_an_empty_seed_list_is_a_file_that_declares_nothing(tmp_path: Path) -> None:
    """Unlike every other declaration directory, and deliberately (FR-024, research.md D9).

    A person who holds nothing is an ordinary person. An empty ``[[seed]]`` array is not the
    mistyped path an empty venue registry would be, so it loads and produces no lots.
    """
    path = tmp_path / "none.toml"
    path.write_text('seed = []\n\n[owner]\nid = "owner-001"\n', encoding="utf-8")
    owner_id, declared = loader.seeds_from_file(path, base_currency=Currency.UAH)
    assert owner_id == "owner-001"
    assert declared == ()


# ---------------------------------------------------------------------------
# The refusal the resolver owns: it needs the instrument declarations
# ---------------------------------------------------------------------------


def test_a_seed_naming_an_undeclared_instrument_is_refused_at_load(tmp_path: Path) -> None:
    """FR-005, and the reason it is here rather than only in the core.

    The core returns a typed ``SeedInstrumentUndeclared`` for a caller that assembles seeds
    without a file. FR-005 asks for a load-time failure *naming the file and the instrument*,
    which the core structurally cannot do -- exactly the division ``UnresolvedTaxClass``
    already has between the resolver and ``results.project``.
    """
    root = _scratch_root(tmp_path)
    target = root / "seeds" / "owner-001.toml"
    target.write_text(
        _replace(
            target.read_text(encoding="utf-8"),
            'instrument_id = "ovdp_synthetic_a"',
            'instrument_id = "inzhur_reit"',
        ),
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as caught:
        resolver.seeds_and_goals_from_data_root(root, base_currency=Currency.UAH)
    _assert_names_file_and_field(caught.value, target, "instrument_id")
    assert "inzhur_reit" in caught.value.problem


def test_the_shipped_data_root_resolves() -> None:
    """The whole shipped tree, through the resolver a run would use."""
    declared = resolver.seeds_and_goals_from_data_root(DATA_ROOT, base_currency=Currency.UAH)
    assert declared.owner_id == "owner-001"
    assert len(declared.seeds) == 2
    assert declared.seed_file == SEEDS
