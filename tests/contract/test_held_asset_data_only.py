"""SC-008, FR-016: a second held asset is a declaration, a label and a lot -- and no engine edit.

Principle II's executable form for this declaration kind. Everything below is written into a
scratch copy of the composed root; nothing under ``src/`` is touched, and the last test asserts
that from the other end: no shipped module names either asset's id in executable code, so
neither works because somebody taught the engine about it.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Final

import pytest

from terezy.core.instruments import registry as instrument_registry
from terezy.core.primitives.currency import Currency
from terezy.data.declarations import resolver
from tests import data_roots, source_scan

SOURCE_ROOT: Final = data_roots.REPO_ROOT / "src" / "terezy"

pytestmark = pytest.mark.contract

DATA_ROOT: Final = data_roots.with_fixtures()
FIRST: Final = "synthetic_held_first"
SECOND: Final = "synthetic_held_second"
GROUP: Final = "ovdp"
"""A group already in the vocabulary, so what this test adds is the *asset*, not a label file."""


def _declaration(asset_id: str, *, quantity_unit: str, currency: str, venue: str) -> str:
    return f"""\
# SYNTHETIC FIXTURE, written by a test. Every term invented.
[instrument]
id             = "{asset_id}"
name           = "Synthetic held asset -- TEST FIXTURE, terms invented"
class          = "{instrument_registry.HELD_ASSET}"
quantity_unit  = "{quantity_unit}"
price_currency = "{currency}"
venue_id       = "{venue}"
symbol         = "{asset_id.upper()}USDT"
quote_asset    = "USDT"
is_synthetic   = true
groups         = ["{GROUP}"]

[instrument.tax_classes]
disposal_gain = "no_pack_declares_this"
"""


@pytest.fixture(scope="module")
def two_assets(tmp_path_factory: pytest.TempPathFactory) -> resolver.Declarations:
    """A root carrying two held assets that agree in nothing but their kind."""
    root = tmp_path_factory.mktemp("held-data-only") / "data"
    shutil.copytree(DATA_ROOT, root)
    (root / "instruments" / f"{FIRST}.toml").write_text(
        _declaration(FIRST, quantity_unit="XBT", currency="USD", venue="binance"),
        encoding="utf-8",
    )
    (root / "instruments" / f"{SECOND}.toml").write_text(
        _declaration(SECOND, quantity_unit="OZT", currency="UAH", venue="monobank_uah"),
        encoding="utf-8",
    )
    return resolver.from_data_root(root)


def test_both_assets_reach_the_registry(two_assets: resolver.Declarations) -> None:
    assert {FIRST, SECOND} <= set(two_assets.held)
    assert two_assets.held[FIRST].price_currency is Currency.USD
    assert two_assets.held[SECOND].price_currency is Currency.UAH
    assert two_assets.held[FIRST].quantity_unit != two_assets.held[SECOND].quantity_unit


def test_both_carry_the_declared_label(two_assets: resolver.Declarations) -> None:
    """A question naming the group reaches both, and nothing infers membership."""
    labelled = {name for name, asset in two_assets.held.items() if GROUP in asset.groups}
    assert {FIRST, SECOND} <= labelled


def test_a_lot_of_each_resolves(tmp_path: Path, two_assets: resolver.Declarations) -> None:
    """The whole path a held position takes: a declaration, a label, and a private lot."""
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    for asset_id, unit, currency, venue in (
        (FIRST, "XBT", "USD", "binance"),
        (SECOND, "OZT", "UAH", "monobank_uah"),
    ):
        (root / "instruments" / f"{asset_id}.toml").write_text(
            _declaration(asset_id, quantity_unit=unit, currency=currency, venue=venue),
            encoding="utf-8",
        )
    overlay = root / resolver.USER_DIR / resolver.SEEDS_DIR / "owner-001.toml"
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.write_text(
        '[owner]\nid = "owner-001"\n\n'
        + "".join(
            "[[seed]]\n"
            "is_synthetic  = true\n"
            f'instrument_id = "{asset_id}"\n'
            f"quantity      = {quantity}\n"
            'acquired_on   = "2024-02-29"\n'
            "cost          = 1_000.0\n"
            'basis         = "known"\n\n'
            for asset_id, quantity in ((FIRST, 0.5), (SECOND, 2.0))
        ),
        encoding="utf-8",
    )
    resolved = resolver.seeds_and_goals_from_data_roots(
        resolver.data_roots_of(root), base_currency=Currency.UAH
    )
    assert [lot.instrument_id for lot in resolved.overlay_seeds] == [FIRST, SECOND]


def test_no_module_names_either_asset() -> None:
    """FR-016 from the other end: neither works because the engine was told about it.

    A source scan, warranted for the reason `test_route_data_only.py`'s is: a branch on an id
    type-checks, passes every ordinary test, and is exactly the Principle II violation that
    makes the two tests above pass for the wrong reason.
    """
    offenders = {
        str(path.relative_to(SOURCE_ROOT)): named
        for path in sorted(SOURCE_ROOT.rglob("*.py"))
        if (
            named := [
                identifier
                for identifier in (FIRST, SECOND, "btc")
                if re.search(rf"\b{identifier}\b", source_scan.executable_source(path))
            ]
        )
    }
    assert not offenders, (
        f"a module names a held asset's id, so that asset's behaviour is code: {offenders}"
    )
