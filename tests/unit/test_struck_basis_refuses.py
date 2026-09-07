"""025 FR-028: an acquisition date the rate series does not declare refuses, naming it.

011 FR-010's rule applied to a cost basis. Nothing interpolates, extrapolates, carries a
previous date's value forward or snaps to the nearest -- each of those produces a number that
looks exactly like a correct one, and the basis is what every later gain and every tax charged
on it is measured from.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path
from typing import Final

import pytest

from terezy.core.primitives.currency import Currency
from terezy.data.declarations import resolver
from terezy.data.declarations.errors import DeclarationError
from tests import data_roots

DATA_ROOT: Final = data_roots.with_fixtures()
ASSET: Final = "synthetic_held_dollar"
SERIES: Final = "ua_nbu_usd"

BEFORE_THE_WINDOW: Final = date(2019, 1, 2)
"""Before the shipped series begins. It starts 2019-12-28, where the publisher's own unit
changed from 100 to 1 -- an earlier date is a second series nobody has declared."""

AFTER_THE_WINDOW: Final = date(2026, 9, 30)
"""After the shipped series ends. A recent acquisition is the refusal's live case rather than
a guard nothing reaches: the series stops at the day it was last fetched."""

DECLARATION: Final = f"""\
# SYNTHETIC FIXTURE, written by a test. Every term invented.
[instrument]
id             = "{ASSET}"
name           = "Synthetic dollar-priced held asset -- TEST FIXTURE"
class          = "held_asset"
quantity_unit  = "XBT"
price_currency = "USD"
venue_id       = "binance"
symbol         = "SYNTHXUSDT"
quote_asset    = "USDT"
is_synthetic   = true
groups         = []

[instrument.tax_classes]
disposal_gain = "no_pack_declares_this"
"""


def _resolve(tmp_path: Path, acquired_on: date) -> resolver.SeedAndGoalDeclarations:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    (root / "instruments" / f"{ASSET}.toml").write_text(DECLARATION, encoding="utf-8")
    overlay = root / resolver.USER_DIR / resolver.SEEDS_DIR / "owner-001.toml"
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.write_text(
        '[owner]\nid = "owner-001"\n\n'
        "[[seed]]\n"
        "is_synthetic  = true\n"
        f'instrument_id = "{ASSET}"\n'
        "quantity      = 0.5\n"
        f'acquired_on   = "{acquired_on.isoformat()}"\n'
        "cost          = 1_000.0\n"
        'basis         = "known"\n',
        encoding="utf-8",
    )
    return resolver.seeds_and_goals_from_data_roots(
        resolver.data_roots_of(root), base_currency=Currency.UAH
    )


@pytest.mark.parametrize("acquired_on", [BEFORE_THE_WINDOW, AFTER_THE_WINDOW])
def test_a_date_outside_the_declared_window_refuses_naming_the_series(
    tmp_path: Path, acquired_on: date
) -> None:
    """The refusal names the series, the pair and the date, carrying 011's own reason."""
    with pytest.raises(DeclarationError) as raised:
        _resolve(tmp_path, acquired_on)
    message = str(raised.value)
    assert SERIES in message
    assert acquired_on.isoformat() in message
    assert "UAH" in message
    assert "USD" in message
    assert "nearest" in message, "the refusal must say what it declined to do, not only that"


@pytest.mark.parametrize("acquired_on", [BEFORE_THE_WINDOW, AFTER_THE_WINDOW])
def test_no_lot_loads_with_a_neighbouring_dates_rate(tmp_path: Path, acquired_on: date) -> None:
    """The mutation this exists to catch: a load that succeeds with a rate from another day."""
    with pytest.raises(DeclarationError):
        _resolve(tmp_path, acquired_on)


def test_a_date_inside_the_window_loads(tmp_path: Path) -> None:
    """The control. Without it the two above would pass on any load failure at all."""
    resolved = _resolve(tmp_path, date(2025, 4, 7))
    struck = next(lot for lot in resolved.seeds if lot.instrument_id == ASSET)
    assert struck.cost.currency is Currency.UAH
    assert struck.struck_from is not None
    assert struck.struck_from.series_id == SERIES
