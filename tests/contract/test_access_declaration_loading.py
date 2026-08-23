"""FR-022 for the declaration kind this feature added: every refusal, naming file and field.

002's FR-024 discipline, applied to ``data/access/``: *a malformed, unknown, incomplete or
duplicated field fails loudly at load, naming file and field, with no default substituted.* A
field that is silently ignored is a declared constraint that does nothing, and a default is
the only mechanism by which a forgotten line becomes a value the file does not contain.

Four of the refusals here need a **second file** and therefore belong to the resolver rather
than the loader: whether the instrument exists, whether the venues exist and can hold its
currency, whether the quote is in the instrument's own currency, and whether this kind of
instrument is entitled to quote a price at all. The last is the one worth reading twice: a
fund declares its own net asset value and its own entry markup, so a price here would be one
fact in two files -- and the day either is updated the figures would rest on whichever the
code happened to read.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Final

import pytest

from terezy.core.primitives.currency import Currency
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError
from tests import tuple_registries as fixtures

pytestmark = pytest.mark.contract

WELL_FORMED: Final = """
[[access]]
instrument_id = "ovdp_synthetic_a"
bought_at     = "inzhur"
proceeds_to   = "inzhur"
risk_class    = "sovereign_debt"

  [access.price]
  per_unit     = 1000.0
  currency     = "UAH"
  kind         = "venue_terms"
  source       = "TEST FIXTURE"
  retrieved_on = "2026-08-23"
  verified_on  = ""
"""


def _written(tmp_path: Path, text: str, name: str = "one.toml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _refusal(tmp_path: Path, text: str) -> DeclarationError:
    with pytest.raises(DeclarationError) as caught:
        loader.access_from_file(_written(tmp_path, text))
    return caught.value


def _root(tmp_path: Path, text: str, name: str = "extra.toml") -> Path:
    """A copy of ``data/`` whose access directory gains one more file."""
    root = tmp_path / "data"
    shutil.copytree(fixtures.DATA_ROOT, root)
    (root / "access" / name).write_text(text, encoding="utf-8")
    return root


def _resolved(tmp_path: Path, text: str, name: str = "extra.toml") -> DeclarationError:
    with pytest.raises(DeclarationError) as caught:
        resolver.tuple_from_data_root(
            _root(tmp_path, text, name), base_currency=Currency.UAH, scenario_id=None
        )
    return caught.value


class TestTheWellFormedFileLoads:
    """The control. Without it every refusal below could be a syntax error in the fixture."""

    def test_it_produces_one_declaration(self, tmp_path: Path) -> None:
        declared = loader.access_from_file(_written(tmp_path, WELL_FORMED))
        assert len(declared) == 1
        assert declared[0].instrument_id == "ovdp_synthetic_a"
        assert declared[0].price_per_unit is not None
        assert declared[0].price_per_unit.currency is Currency.UAH

    def test_the_price_carries_its_citation(self, tmp_path: Path) -> None:
        declared = loader.access_from_file(_written(tmp_path, WELL_FORMED))
        price = declared[0].price_per_unit
        assert price is not None
        assert price.provenance.sources


class TestOneFileReadInIsolation:
    """Everything the loader can see without opening a second file."""

    def test_an_unknown_field_is_refused_rather_than_ignored(self, tmp_path: Path) -> None:
        refusal = _refusal(tmp_path, WELL_FORMED.replace("risk_class", "risk_klass"))
        assert "risk_klass" in refusal.problem or "risk_class" in refusal.problem

    def test_a_missing_field_gets_no_default(self, tmp_path: Path) -> None:
        refusal = _refusal(tmp_path, WELL_FORMED.replace('proceeds_to   = "inzhur"\n', ""))
        assert "proceeds_to" in refusal.field_path

    def test_an_empty_file_is_refused_rather_than_read_as_no_instrument_is_reachable(
        self, tmp_path: Path
    ) -> None:
        # A comparison emptied by a forgotten line looks exactly like one emptied by a real
        # gap in the registry, and only one of them is worth acting on.
        refusal = _refusal(tmp_path, "access = []\n")
        assert refusal.field_path == "access"

    def test_a_blank_venue_id_is_refused(self, tmp_path: Path) -> None:
        refusal = _refusal(
            tmp_path, WELL_FORMED.replace('bought_at     = "inzhur"', 'bought_at     = ""')
        )
        assert "bought_at" in refusal.field_path

    def test_a_blank_risk_class_is_refused(self, tmp_path: Path) -> None:
        refusal = _refusal(
            tmp_path, WELL_FORMED.replace('risk_class    = "sovereign_debt"', 'risk_class    = ""')
        )
        assert "risk_class" in refusal.field_path

    def test_a_price_of_zero_is_refused_rather_than_taken_literally(self, tmp_path: Path) -> None:
        # A price of zero would make an arriving amount buy unlimited units, and every figure
        # downstream of it meaningless rather than merely large.
        refusal = _refusal(
            tmp_path, WELL_FORMED.replace("per_unit     = 1000.0", "per_unit     = 0.0")
        )
        assert "per_unit" in refusal.field_path

    def test_a_priceless_quote_is_refused(self, tmp_path: Path) -> None:
        refusal = _refusal(
            tmp_path, WELL_FORMED.replace('source       = "TEST FIXTURE"', 'source       = ""')
        )
        assert "source" in refusal.field_path

    def test_the_same_instrument_twice_in_one_file_is_refused(self, tmp_path: Path) -> None:
        refusal = _refusal(tmp_path, WELL_FORMED + WELL_FORMED)
        assert "instrument_id" in refusal.field_path

    def test_malformed_toml_names_the_file(self, tmp_path: Path) -> None:
        refusal = _refusal(tmp_path, "[[access]\n")
        assert "not valid TOML" in refusal.problem


class TestWhatNeedsASecondFile:
    """The four relations, refused where both files can be named."""

    def test_an_instrument_nobody_declares(self, tmp_path: Path) -> None:
        refusal = _resolved(
            tmp_path, WELL_FORMED.replace("ovdp_synthetic_a", "nothing_declares_this")
        )
        assert "instrument_id" in refusal.field_path
        assert "nothing_declares_this" in refusal.problem

    def test_a_venue_nobody_declares(self, tmp_path: Path) -> None:
        refusal = _resolved(
            tmp_path,
            WELL_FORMED.replace(
                'instrument_id = "ovdp_synthetic_a"', 'instrument_id = "ovdp_synthetic_b"'
            ).replace('bought_at     = "inzhur"', 'bought_at     = "no_such_desk"'),
        )
        assert "bought_at" in refusal.field_path

    def test_a_venue_that_cannot_hold_the_instruments_currency(self, tmp_path: Path) -> None:
        # `coinbase` declares dollars only, and the instrument trades in hryvnia. Money cannot
        # sit in an account that does not hold its currency, so the seam could never be
        # crossed and the arriving amount would describe a balance that cannot exist.
        refusal = _resolved(
            tmp_path,
            WELL_FORMED.replace(
                'instrument_id = "ovdp_synthetic_a"', 'instrument_id = "ovdp_synthetic_b"'
            ).replace('proceeds_to   = "inzhur"', 'proceeds_to   = "coinbase"'),
        )
        assert "proceeds_to" in refusal.field_path

    def test_a_quote_in_a_currency_the_instrument_is_not_declared_in(self, tmp_path: Path) -> None:
        refusal = _resolved(
            tmp_path,
            WELL_FORMED.replace(
                'instrument_id = "ovdp_synthetic_a"', 'instrument_id = "ovdp_synthetic_b"'
            ).replace('currency     = "UAH"', 'currency     = "USD"'),
        )
        assert "price.currency" in refusal.field_path

    def test_a_fund_quoting_a_price_it_already_declares(self, tmp_path: Path) -> None:
        # One price in two files is one fact in two places. Refused rather than preferred or
        # ignored, because the day either is updated the figures would rest on whichever the
        # code happened to read, with nothing in the output to say which.
        refusal = _resolved(
            tmp_path,
            WELL_FORMED.replace(
                'instrument_id = "ovdp_synthetic_a"', 'instrument_id = "inzhur_reit"'
            ),
        )
        assert "price" in refusal.field_path
        assert "net asset value" in refusal.problem

    def test_a_bond_quoting_no_price_at_all(self, tmp_path: Path) -> None:
        # A face value is what a bond repays, not what it costs. Without a quote an arriving
        # amount cannot become units, and assuming par would be a market fact in code.
        text = WELL_FORMED.split("  [access.price]")[0].replace(
            "ovdp_synthetic_a", "ovdp_synthetic_b"
        )
        refusal = _resolved(tmp_path, text)
        assert "access[0]" in refusal.field_path
        assert "no unit price" in refusal.problem

    def test_the_same_instrument_declared_in_two_files_names_both(self, tmp_path: Path) -> None:
        # Both, because knowing one leaves the reader to find the other by hand -- and neither
        # is preferred: whichever loaded last would win by accident of directory ordering.
        refusal = _resolved(tmp_path, WELL_FORMED)
        assert refusal.file.name == "instruments.toml"
        assert "extra.toml" in refusal.problem

    def test_an_empty_access_directory_is_refused(self, tmp_path: Path) -> None:
        root = tmp_path / "data"
        shutil.copytree(fixtures.DATA_ROOT, root)
        for path in (root / "access").glob("*.toml"):
            path.unlink()
        with pytest.raises(DeclarationError) as caught:
            resolver.tuple_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)
        assert "access" in str(caught.value.file)
