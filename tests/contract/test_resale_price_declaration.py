"""What an early exit is struck at: a declared seller's quote, or a refusal naming the term.

015 FR-031. A horizon means the money comes out at its end, so an instrument whose terms run
past it is sold there -- at a price that comes from a **declaration**, never from a face value,
a NAV or a purchase price standing in for one.

**Exactly the real ОВДП issues carry one**, and not one fixture does. 016 declared the seller's
observed sell quotation on their access records, which is where 015 FR-031 left the question
open -- so `DeclarationMissing(part="access")` stays the home, `TupleRefused` stays at
seventeen, and the refusal is still the shipped behaviour for every invented bond rather than a
guard nothing reaches. A fixture gets none because nobody quotes a resale price for a bond that
does not exist, and inventing one would put a made-up spread inside the worked examples a
reader checks on paper.

What is also tested here is that the term is checked exactly as the purchase quote is, and that
a fund may not declare one -- a fund prices its own exit from NAV and a declared discount, and a
second price would be one fact in two places.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from terezy.core.primitives.currency import Currency
from terezy.data.declarations import resolver
from terezy.data.declarations.errors import DeclarationError
from tests import data_roots
from tests import observations as obs

pytestmark = pytest.mark.contract

DATA_ROOT = data_roots.with_fixtures()

BOND = "ovdp_synthetic_a"
FUND = "inzhur_reit"

QUOTED_ON = "2026-01-15"
"""The day this bond's declared buy price was read. A resale price must carry the same one:
the pair is one observation of one market, and each side is carried to the day it prices."""

RESALE = f"""
  [access.resale_price]
  per_unit     = 995.0
  currency     = "UAH"
  kind         = "venue_terms"
  source       = "TEST FIXTURE -- invented seller's quote, not observed at any venue."
  retrieved_on = "{QUOTED_ON}"
  verified_on  = ""
"""

RESALE_READ_A_WEEK_LATER = RESALE.replace(QUOTED_ON, "2026-08-31")


def _scratch_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _with_resale(root: Path, instrument_id: str, block: str = RESALE) -> Path:
    """Whichever access file declares this instrument, with a resale price added in place."""
    for target in sorted((root / "access").glob("*.toml")):
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
        for index, line in enumerate(lines):
            if not (line.startswith("[[access]]") and f'"{instrument_id}"' in lines[index + 1]):
                continue
            end = index + 1
            while end < len(lines) and not (lines[end].startswith("[[access]]") and end != index):
                end += 1
            lines.insert(end, block)
            target.write_text("".join(lines), encoding="utf-8")
            return target
    pytest.fail(f"no access file under {root} declares {instrument_id!r}")


def _resolve(root: Path) -> resolver.TupleDeclarations:
    return resolver.tuple_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)


def test_the_real_issues_carry_a_resale_price_and_no_fixture_does() -> None:
    """FR-031's refusal is still the shipped behaviour for every invented bond."""
    declared = _resolve(DATA_ROOT)
    quoted = {name for name, entry in declared.access.items() if entry.resale_price is not None}
    assert quoted == set(obs.declared_isins())
    assert set(declared.access) - quoted, "there must still be a declaration that refuses"


def test_every_real_resale_price_is_the_sellers_observed_sell_quotation() -> None:
    """Declared, never inferred: not the face value, not the purchase quote, not a NAV. On five
    of the 24 the seller quotes buy equal to sell, so an assertion that the two merely differ
    would be wrong -- what is asserted is that each equals what the seller published."""
    access = _resolve(DATA_ROOT).access
    for isin in obs.declared_isins():
        quote = access[isin].resale_price
        assert quote is not None, isin
        assert quote.price.amount == obs.seller_bonds()[isin]["sell"], isin
        assert quote.price.currency is Currency.UAH, isin


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


def test_a_resale_price_read_on_another_day_than_the_purchase_quote_refuses(
    tmp_path: Path,
) -> None:
    """One instrument, one market, one morning.

    Each price is carried to the day it prices net of the coupons that detached since it was
    read, so two retrieval dates would carry the pair by two different windows -- a coupon
    could come out of the sale and stay in the purchase, charging the holder for one he never
    received. Nothing downstream sees the pair, so the agreement is enforced at load or nowhere.
    """
    root = _scratch_root(tmp_path)
    _with_resale(root, BOND, block=RESALE_READ_A_WEEK_LATER)
    with pytest.raises(DeclarationError) as raised:
        _resolve(root)
    assert "resale_price.retrieved_on" in str(raised.value)
    assert "one observation of one market" in str(raised.value)
