"""The private overlay: what may live there, what may not live anywhere else, and what refuses.

025 FR-001 to FR-006, SC-003, SC-004. `data/README.md` rule 5 says a figure describing the
owner's actual position may never be committed, and until this feature the rule was kept by a
reviewer noticing. These are the four refusals that keep it instead.

**No test here reads `data/user/`.** It is gitignored, absent in CI, and may hold his real
figures on his own machine; a suite that read it would be the leak the overlay exists to
prevent. Every root below is built in `tmp_path` or is the fixture tree.
"""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

import pytest

from terezy.core.primitives.currency import Currency
from terezy.data.declarations import resolver
from terezy.data.declarations.errors import DeclarationError
from tests import data_roots

pytestmark = pytest.mark.contract

DATA_ROOT = data_roots.with_fixtures()
FIXTURE_INSTRUMENT = "ovdp_enumerated_a"
"""An instrument the composed root declares and its shipped seeds file does not hold."""


def _scratch(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _lot(instrument_id: str, *, is_synthetic: bool = True) -> str:
    return (
        "[[seed]]\n"
        f"is_synthetic  = {str(is_synthetic).lower()}\n"
        f'instrument_id = "{instrument_id}"\n'
        "quantity      = 3.0\n"
        'acquired_on   = "2026-03-14"\n'
        "cost          = 1_000.0\n"
        'basis         = "known"\n'
    )


def _write_overlay_lots(root: Path, body: str) -> Path:
    path = root / resolver.USER_DIR / resolver.SEEDS_DIR / "owner-001.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'[owner]\nid = "owner-001"\n\n{body}', encoding="utf-8")
    return path


def _resolve(root: Path) -> resolver.SeedAndGoalDeclarations:
    return resolver.seeds_and_goals_from_data_roots(
        resolver.data_roots_of(root), base_currency=Currency.UAH
    )


# ---------------------------------------------------------------------------
# FR-002: no overlay is an ordinary state
# ---------------------------------------------------------------------------


def test_an_absent_overlay_declares_nothing_and_says_nothing(tmp_path: Path) -> None:
    """The state a checkout is in, and therefore the state the whole suite runs in."""
    root = _scratch(tmp_path)
    shutil.rmtree(root / resolver.USER_DIR)
    resolved = _resolve(root)
    assert resolved.overlay_seeds == ()
    assert resolved.overlay_seed_file is None
    assert resolved.seeds, "the shipped root's own lots are untouched by the overlay's absence"


def test_an_empty_overlay_is_identical_to_an_absent_one(tmp_path: Path) -> None:
    """A directory that exists and holds no declaration, which is FR-002's second half."""
    root = _scratch(tmp_path)
    for path in (root / resolver.USER_DIR / resolver.SEEDS_DIR).glob("*.toml"):
        path.unlink()
    resolved = _resolve(root)
    assert resolved.overlay_seeds == ()
    assert resolved.overlay_seed_file is None


def test_the_overlay_moves_nothing_it_does_not_declare(tmp_path: Path) -> None:
    """SC-001: the shipped lots resolve identically with and without a private root.

    What the overlay adds is its own lots and nothing else -- no shipped lot's quantity, cost,
    basis or struck rate moves because a second root exists beside it.
    """
    root = _scratch(tmp_path)
    with_overlay = _resolve(root)
    private = set(with_overlay.overlay_seeds)
    shutil.rmtree(root / resolver.USER_DIR)
    without = _resolve(root)
    assert [lot for lot in with_overlay.seeds if lot not in private] == list(without.seeds)
    assert private, "the fixture overlay declares nothing, so this asserts nothing"


# ---------------------------------------------------------------------------
# FR-003: one instrument in two roots is refused; two instruments are unioned
# ---------------------------------------------------------------------------


def test_lots_of_different_instruments_are_unioned_across_the_roots(tmp_path: Path) -> None:
    """Two roots holding different instruments are two halves of one portfolio.

    `_at_most_one` resolves one seeds file per root, so the overlay's file necessarily carries
    the same name as the shipped one; the union is what makes that not an override.
    """
    root = _scratch(tmp_path)
    _write_overlay_lots(root, _lot(FIXTURE_INSTRUMENT))
    resolved = _resolve(root)
    held = [lot.instrument_id for lot in resolved.seeds]
    assert held.count(FIXTURE_INSTRUMENT) == 1
    assert len(held) > 1, "the shipped root's lots survive the union"
    assert [lot.instrument_id for lot in resolved.overlay_seeds] == [FIXTURE_INSTRUMENT]


def test_one_instrument_declared_in_both_roots_refuses_naming_both(tmp_path: Path) -> None:
    """SC-004. Unioning would double the holding; preferring one would let an uncommitted
    file silently change what a reviewed one said."""
    root = _scratch(tmp_path)
    shipped = root / resolver.SEEDS_DIR / "owner-001.toml"
    collided = next(lot.instrument_id for lot in _resolve(root).seeds)
    overlay = _write_overlay_lots(root, _lot(collided))
    with pytest.raises(DeclarationError) as raised:
        _resolve(root)
    message = str(raised.value)
    assert str(overlay) in message
    assert str(shipped) in message
    assert collided in message


def test_two_owners_across_the_roots_refuse(tmp_path: Path) -> None:
    """Principle VII: unioning two people's lots would put two portfolios in one ledger."""
    root = _scratch(tmp_path)
    path = root / resolver.USER_DIR / resolver.SEEDS_DIR / "owner-001.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'[owner]\nid = "somebody-else"\n\n{_lot(FIXTURE_INSTRUMENT)}', encoding="utf-8"
    )
    with pytest.raises(DeclarationError, match="somebody-else"):
        _resolve(root)


# ---------------------------------------------------------------------------
# FR-004, FR-005: the overlay is not a looser dialect, and it is the only real root
# ---------------------------------------------------------------------------


def test_a_real_lot_under_the_shipped_root_refuses_naming_the_file(tmp_path: Path) -> None:
    """SC-003, and `data/README.md` rule 5 made mechanical rather than reviewed."""
    root = _scratch(tmp_path)
    shipped = root / resolver.SEEDS_DIR / "owner-001.toml"
    shipped.write_text(
        f'[owner]\nid = "owner-001"\n\n{_lot(FIXTURE_INSTRUMENT, is_synthetic=False)}',
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError) as raised:
        _resolve(root)
    assert str(shipped) in str(raised.value)
    assert "is_synthetic" in str(raised.value)


def test_a_real_lot_under_the_overlay_loads(tmp_path: Path) -> None:
    """The mutation's other side: the refusal is about the root, not about the flag."""
    root = _scratch(tmp_path)
    _write_overlay_lots(root, _lot(FIXTURE_INSTRUMENT, is_synthetic=False))
    resolved = _resolve(root)
    assert [lot.is_synthetic for lot in resolved.overlay_seeds] == [False]


def test_the_overlay_is_validated_by_the_same_schema(tmp_path: Path) -> None:
    """FR-004: a malformed private file fails as loudly as a malformed committed one."""
    root = _scratch(tmp_path)
    overlay = _write_overlay_lots(root, _lot(FIXTURE_INSTRUMENT).replace("quantity", "qty"))
    with pytest.raises(DeclarationError) as raised:
        _resolve(root)
    assert str(overlay) in str(raised.value)


def test_the_overlay_resolves_against_the_shipped_instrument_set(tmp_path: Path) -> None:
    """The overlay declares holdings, never what a thing *is*: an unknown id refuses."""
    root = _scratch(tmp_path)
    _write_overlay_lots(root, _lot("nothing_declares_this"))
    with pytest.raises(DeclarationError, match="nothing_declares_this"):
        _resolve(root)


# ---------------------------------------------------------------------------
# FR-006: what the overlay may contain is declared and fail-closed
# ---------------------------------------------------------------------------


def test_an_undeclared_overlay_directory_refuses_naming_it(tmp_path: Path) -> None:
    root = _scratch(tmp_path)
    stray = root / resolver.USER_DIR / "instruments"
    stray.mkdir(parents=True)
    with pytest.raises(DeclarationError) as raised:
        _resolve(root)
    assert str(stray) in str(raised.value)


def test_a_stray_declaration_at_the_overlay_root_refuses(tmp_path: Path) -> None:
    """A `.toml` there would look exactly like a declaration and be read by nothing."""
    root = _scratch(tmp_path)
    stray = root / resolver.USER_DIR / "owner-001.toml"
    stray.write_text('[owner]\nid = "owner-001"\n', encoding="utf-8")
    with pytest.raises(DeclarationError) as raised:
        _resolve(root)
    assert str(stray) in str(raised.value)


def test_the_admitted_set_is_what_this_feature_declared() -> None:
    """The mutation the fail-closed rule exists to catch: a directory silently admitted."""
    assert frozenset({resolver.SEEDS_DIR}) == resolver.OVERLAY_DIRS


# ---------------------------------------------------------------------------
# SC-003: nothing in the committed tree describes a real position
# ---------------------------------------------------------------------------


def test_no_root_this_suite_runs_against_can_reach_the_real_overlay() -> None:
    """025 FR-007: his own position must not reach a golden, and a digest is not a file.

    ``data_roots_of`` derives the overlay from whatever root it is handed, so a suite pointed
    at the working tree's ``data/`` would fold his quantities into every golden taken over it
    -- and gitignoring the file does not stop the *digest* encoding them. The exclusion is
    therefore in the roots the suite is built from rather than in a reviewer's attention.

    Asserted over the roots rather than over the filesystem, so it holds whether or not the
    file happens to exist on the machine running this.
    """
    for root in (data_roots.SHIPPED, DATA_ROOT):
        derived = resolver.data_roots_of(root)
        assert derived.shipped != data_roots.COMMITTED, (
            f"{root} is the working tree's own data root, so a test reading it reads whatever "
            "the owner has declared under data/user/"
        )
        if derived.overlay is not None:
            assert data_roots.COMMITTED not in derived.overlay.parents


def test_no_committed_seed_declares_a_real_holding() -> None:
    """The tree as it stands, beside the loader refusal that would catch one being added.

    The refusal fires when a root is *resolved*; a real lot dropped into a fixture root no
    suite resolves would be committed and never opened. This reads every seeds file in the
    repository instead, which is the population `data/README.md` rule 5 is about.
    """
    scanned = [
        path
        for path in sorted(data_roots.REPO_ROOT.rglob("seeds/*.toml"))
        if resolver.USER_DIR not in path.parts and ".venv" not in path.parts
    ]
    assert scanned, "the scan found no seeds file at all, so it asserts nothing"
    for path in scanned:
        declared = tomllib.loads(path.read_text(encoding="utf-8")).get("seed", [])
        real = [lot for lot in declared if lot.get("is_synthetic") is not True]
        assert not real, (
            f"{path} declares {len(real)} lot(s) not labelled synthetic, and it is committed. "
            "A figure describing the owner's actual position belongs under "
            f"{resolver.USER_DIR}/{resolver.SEEDS_DIR}/, which is gitignored."
        )
