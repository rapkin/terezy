"""What an early exit is struck at: a declared seller's quote, or a refusal naming the term.

015 FR-031. A horizon means the money comes out at its end, so an instrument whose terms run
past it is sold there -- at a price that comes from a **declaration**, never from a face value,
a NAV or a purchase price standing in for one.

**No shipped declaration carries one**, and that is the point of this module's first assertion:
the refusal FR-031 requires is the shipped behaviour rather than a guard that reads as
protection. What is tested here is that the term is declarable, that it is checked exactly as
the purchase quote is, and that a fund may not declare one -- a fund prices its own exit from
NAV and a declared discount, and a second price would be one fact in two places.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from terezy.core.primitives.currency import Currency
from terezy.data.declarations import resolver
from terezy.data.declarations.errors import DeclarationError

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
ACCESS = DATA_ROOT / "access" / "instruments.toml"

BOND = "ovdp_synthetic_a"
FUND = "inzhur_reit"

RESALE = """
  [access.resale_price]
  per_unit     = 995.0
  currency     = "UAH"
  kind         = "venue_terms"
  source       = "TEST FIXTURE -- invented seller's quote, not observed at any venue."
  retrieved_on = "2026-08-31"
  verified_on  = ""
"""


def _scratch_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _with_resale(root: Path, instrument_id: str, block: str = RESALE) -> Path:
    """The shipped access file with one entry given a resale price, in place."""
    target = root / "access" / "instruments.toml"
    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith("[[access]]") and f'"{instrument_id}"' in lines[index + 1]:
            end = index + 1
            while end < len(lines) and not (lines[end].startswith("[[access]]") and end != index):
                end += 1
            lines.insert(end, block)
            target.write_text("".join(lines), encoding="utf-8")
            return target
    pytest.fail(f"{target.name} no longer declares access for {instrument_id!r}")


def _resolve(root: Path) -> resolver.TupleDeclarations:
    return resolver.tuple_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)


def test_no_shipped_declaration_carries_a_resale_price() -> None:
    """FR-031's refusal is the shipped behaviour, not a guard nothing reaches."""
    access = _resolve(DATA_ROOT).access
    assert all(entry.resale_price is None for entry in access.values())


def test_a_declared_resale_price_loads(tmp_path: Path) -> None:
    root = _scratch_root(tmp_path)
    _with_resale(root, BOND)
    quote = _resolve(root).access[BOND].resale_price
    assert quote is not None
    assert quote.price.amount == 995.0
    assert quote.price.currency is Currency.UAH


def test_a_resale_price_in_another_currency_is_refused(tmp_path: Path) -> None:
    """There is no rate here, and inventing one would strike every early exit at a made-up sum."""
    root = _scratch_root(tmp_path)
    target = _with_resale(root, BOND, RESALE.replace('"UAH"', '"USD"'))
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    assert caught.value.file == target
    assert caught.value.field_path == "access[0].resale_price.currency"
    assert "USD" in caught.value.problem


def test_a_non_positive_resale_price_is_refused(tmp_path: Path) -> None:
    root = _scratch_root(tmp_path)
    target = _with_resale(root, BOND, RESALE.replace("995.0", "0.0"))
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    assert caught.value.file == target
    assert caught.value.field_path == "access[0].resale_price.per_unit"


def test_a_resale_price_with_an_undeclared_kind_is_refused(tmp_path: Path) -> None:
    """A quote whose staleness kind nobody declared would age under a threshold nobody set."""
    root = _scratch_root(tmp_path)
    target = _with_resale(root, BOND, RESALE.replace('"venue_terms"', '"venue_term"'))
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    assert caught.value.file == target
    assert caught.value.field_path == "access[0].resale_price.kind"
    assert "venue_term" in caught.value.problem


def test_a_fund_may_not_declare_a_resale_price(tmp_path: Path) -> None:
    """It prices its own exit from NAV and a declared discount; a second price is two truths."""
    root = _scratch_root(tmp_path)
    target = _with_resale(root, FUND)
    with pytest.raises(DeclarationError) as caught:
        _resolve(root)
    assert caught.value.file == target
    assert caught.value.field_path.endswith(".resale_price")
    assert "net asset value" in caught.value.problem
