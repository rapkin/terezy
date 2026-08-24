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

import dataclasses
import shutil
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Final

import pytest

from terezy.core.primitives.currency import Currency
from terezy.core.primitives.provenance import SourceRef
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
        quote = declared[0].quote
        assert quote is not None
        assert quote.price.currency is Currency.UAH

    def test_the_price_carries_its_citation_and_the_kind_it_ages_under(
        self, tmp_path: Path
    ) -> None:
        # Both, on one record: a price whose kind was dropped on the way in would read as
        # fresh forever, and nothing downstream could tell that from a threshold it had met.
        quote = loader.access_from_file(_written(tmp_path, WELL_FORMED))[0].quote
        assert quote is not None
        assert quote.price.provenance.sources
        assert quote.kind == "venue_terms"


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


class TestEveryCitationInTheResolvedRegistriesAgesUnderADeclaredKind:
    """The scan, because this is the third time one kind was validated and then not resolved.

    ``ChannelSide.kind`` was the first -- an earlier revision aged every side under the
    channel's threshold, a seven-day premium under a 365-day one, reported fresh. The access
    price was the second: it loaded clean, *resolved* clean, and then raised ``KeyError`` out
    of the pure core from ``staleness.kind_for``, whose own message says reaching it means
    validation was bypassed and calls that a programmer error. A data-file typo is not one.

    A third point fix would have left the fourth open, so this walks the resolved registries
    instead of naming fields: every ``SourceRef`` reachable from any declaration must carry a
    kind, and every kind must be one ``data/observation_kinds.toml`` declares. A new
    declaration kind whose citation is stamped and not resolved fails here, and so does one
    whose citation is not stamped at all.

    ``scripts/check_provenance.py`` checks something adjacent and cannot replace this: it
    reads the repository's own data files, and a runtime data root is not those.
    """

    def _sources(self, value: object, seen: set[int]) -> Iterator[SourceRef]:
        """Every ``SourceRef`` reachable from a value, without naming a single field."""
        if id(value) in seen:
            return
        seen.add(id(value))
        if isinstance(value, SourceRef):
            yield value
        elif isinstance(value, str | bytes):
            return
        elif dataclasses.is_dataclass(value) and not isinstance(value, type):
            for field in dataclasses.fields(value):
                yield from self._sources(getattr(value, field.name), seen)
        elif isinstance(value, Mapping):
            for item in value.values():
                yield from self._sources(item, seen)
        elif isinstance(value, Iterable):
            for item in value:
                yield from self._sources(item, seen)

    def test_every_source_carries_a_kind_and_every_kind_is_declared(self) -> None:
        registries = fixtures.shipped()
        found = list(self._sources(registries, set()))
        assert len(found) > 20, "the walk reached almost nothing, so it proves almost nothing"
        unstamped = sorted({source.id for source in found if not source.kind})
        assert not unstamped, f"citations reaching the core with no staleness kind: {unstamped}"
        undeclared = sorted(
            {source.kind for source in found if source.kind not in registries.kinds}
        )
        assert not undeclared, f"kinds no declaration file declares: {undeclared}"
