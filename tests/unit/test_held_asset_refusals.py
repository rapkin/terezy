"""What a held-asset declaration refuses, and what it deliberately does not.

025 FR-009 to FR-014. Every root here is written into ``tmp_path``: the shipped registry
declares no held asset until this feature's last phase, and a test that needed one to exist
would be asserting the data rather than the mechanism.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from terezy.core.instruments import registry as instrument_registry
from terezy.core.primitives.currency import Currency
from terezy.data.declarations import resolver
from terezy.data.declarations.errors import DeclarationError
from tests import data_roots

DATA_ROOT = data_roots.with_fixtures()
ASSET = "synthetic_held_x"
UNDECLARED_CLASS = "nothing_declares_this_class"

DECLARATION = f"""\
# SYNTHETIC FIXTURE, written by a test. Every term invented.
[instrument]
id            = "{ASSET}"
name          = "Synthetic held asset X -- TEST FIXTURE"
class         = "{instrument_registry.HELD_ASSET}"
quantity_unit = "XBT"
price_currency = "USD"
venue_id      = "binance"
symbol        = "SYNTHXUSDT"
is_synthetic  = true
groups        = []

[instrument.tax_classes]
disposal_gain = "{UNDECLARED_CLASS}"
"""


def _root(tmp_path: Path, declaration: str = DECLARATION) -> Path:
    root = tmp_path / f"data-{len(list(tmp_path.iterdir()))}"
    shutil.copytree(DATA_ROOT, root)
    (root / "instruments" / f"{ASSET}.toml").write_text(declaration, encoding="utf-8")
    return root


def _declared(tmp_path: Path, declaration: str = DECLARATION) -> resolver.Declarations:
    return resolver.from_data_root(_root(tmp_path, declaration))


# ---------------------------------------------------------------------------
# FR-009, FR-010: it loads, and it is not an event stream
# ---------------------------------------------------------------------------


def test_a_held_asset_loads_into_its_own_map(tmp_path: Path) -> None:
    declared = _declared(tmp_path)
    assert ASSET in declared.held
    assert ASSET not in declared.instruments
    assert ASSET not in declared.funds
    asset = declared.held[ASSET]
    assert asset.quantity_unit == "XBT"
    assert asset.price_currency is Currency.USD


def test_the_kind_is_in_the_vocabulary_and_out_of_the_event_registry() -> None:
    """FR-010: no fifth plugin interface, because there is no event stream to compute."""
    assert instrument_registry.HELD_ASSET in instrument_registry.DECLARATION_KINDS
    assert instrument_registry.HELD_ASSET not in instrument_registry.REGISTRY


def test_the_id_space_is_shared_with_the_other_kinds(tmp_path: Path) -> None:
    """A holding names an asset by id, so a bond and a held asset sharing one is refused."""
    root = _root(tmp_path, DECLARATION.replace(ASSET, "ovdp_synthetic_a"))
    with pytest.raises(DeclarationError, match="ovdp_synthetic_a"):
        resolver.from_data_root(root)


# ---------------------------------------------------------------------------
# FR-011: the price is an observation, and a declaration may not state one
# ---------------------------------------------------------------------------


def test_a_declaration_stating_a_price_refuses(tmp_path: Path) -> None:
    stating = DECLARATION.replace(
        "groups        = []", "price         = 61_000.0\ngroups        = []"
    )
    with pytest.raises(DeclarationError) as raised:
        _declared(tmp_path, stating)
    message = str(raised.value)
    assert "instrument.price" in message
    assert "observation" in message


# ---------------------------------------------------------------------------
# FR-012: a quantity comes from a declared lot and from nothing else
# ---------------------------------------------------------------------------


def test_the_declaration_carries_no_quantity(tmp_path: Path) -> None:
    """A price cannot imply a holding: there is no field for one to be written into."""
    asset = _declared(tmp_path).held[ASSET]
    assert not hasattr(asset, "quantity")


def test_a_lot_of_a_held_asset_resolves(tmp_path: Path) -> None:
    """FR-012's other half: the quantity enters through a seed lot, and only through one."""
    root = _root(tmp_path)
    overlay = root / resolver.USER_DIR / resolver.SEEDS_DIR / "owner-001.toml"
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.write_text(
        '[owner]\nid = "owner-001"\n\n'
        "[[seed]]\n"
        "is_synthetic  = true\n"
        f'instrument_id = "{ASSET}"\n'
        "quantity      = 0.5\n"
        'acquired_on   = "2024-02-29"\n'
        "cost          = 12_345.0\n"
        'basis         = "estimated"\n'
        'reason        = "an invented reason for an invented lot"\n',
        encoding="utf-8",
    )
    resolved = resolver.seeds_and_goals_from_data_roots(
        resolver.data_roots_of(root), base_currency=Currency.UAH
    )
    assert [lot.instrument_id for lot in resolved.overlay_seeds] == [ASSET]
    assert [lot.quantity for lot in resolved.overlay_seeds] == [0.5]


# ---------------------------------------------------------------------------
# FR-014: the tax class is permitted to be undeclared, and required to be named
# ---------------------------------------------------------------------------


def test_an_undeclared_tax_class_loads_rather_than_refusing(tmp_path: Path) -> None:
    """The asymmetry with an instrument, and it is the feature.

    A bond naming an unresolved class is refused at load, because a projection would charge
    nothing and flatter every after-tax figure. A held asset projects nothing: the refusal is
    the reported figure, and refusing the load instead would mean the whole answer failed
    because Ukraine's treatment of a virtual asset is unsettled.
    """
    declared = _declared(tmp_path)
    assert declared.held[ASSET].tax_classes
    assert UNDECLARED_CLASS not in declared.tax_classes


def test_naming_no_tax_class_at_all_refuses(tmp_path: Path) -> None:
    """Silence about the tax reads exactly like an exemption, and only one of them is cited."""
    silent = DECLARATION.split("[instrument.tax_classes]", maxsplit=1)[0]
    with pytest.raises(DeclarationError) as raised:
        _declared(tmp_path, silent)
    assert "tax_classes" in str(raised.value)


# ---------------------------------------------------------------------------
# FR-013: membership is a declared label
# ---------------------------------------------------------------------------


def test_an_undeclared_group_label_refuses(tmp_path: Path) -> None:
    labelled = DECLARATION.replace("groups        = []", 'groups        = ["no_such_group"]')
    with pytest.raises(DeclarationError, match="no_such_group"):
        _declared(tmp_path, labelled)


def test_a_declared_label_is_carried_and_nothing_is_inferred(tmp_path: Path) -> None:
    """Neither the class, the venue, the tax class nor the id prefix puts it in a group."""
    labelled = DECLARATION.replace("groups        = []", 'groups        = ["ovdp"]')
    assert _declared(tmp_path, labelled).held[ASSET].groups == ("ovdp",)
    assert _declared(tmp_path).held[ASSET].groups == ()
