"""A venue's kind is declared, closed, and refused at load naming file and field.

FR-007 of ``specs/026-answer-screen``: the visual language gives every entity kind one hue, one
icon and one word, and a venue's kind is the one of those the client cannot read anywhere --
``data/venues.toml`` declared an id, a name and a set of currencies, while
``core.routes.venues``'s docstring named the taxonomy in prose. Prose is not a field, so a
client had nothing to key on and the only alternative was inferring the kind from the id, which
021 FR-015 forbids by name.

The vocabulary is the owner's, answered 2026-09-06
(``specs/decisions/2026-09-06-clarify-026.toml``): ``bank``, ``exchange``, ``broker``,
``platform``, ``payroll``. Closed, in ``core/``, and an unknown one refused at load the way every
other closed field is -- which is what this battery asserts, alongside the other half of
Principle II: adding a venue stays a data-only change.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from terezy.core.primitives.currency import Currency
from terezy.core.routes import venues
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError

pytestmark = pytest.mark.contract

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
VENUES = DATA_ROOT / "venues.toml"


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"the shipped fixture no longer contains {old!r}; this test is stale"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


class TestTheVocabularyIsClosed:
    def test_the_five_the_owner_named_are_the_whole_of_it(self) -> None:
        assert set(venues.VENUE_KINDS) == {"bank", "exchange", "broker", "platform", "payroll"}

    def test_every_shipped_venue_declares_one(self) -> None:
        declared = loader.venues_from_file(VENUES)
        assert declared, "the shipped file declares no venue"
        for venue in declared:
            assert venue.kind in venues.VENUE_KINDS, f"{venue.id} declares {venue.kind!r}"

    def test_the_owner_s_assignments_are_the_ones_in_the_decisions_file(self) -> None:
        # Written out rather than read from the decisions file, so a row changed in one place
        # without the other fails here instead of drifting quietly. The three the owner did not
        # name himself are assigned there for his correction: fop, payoneer, foreign_bank_usd.
        assigned = {venue.id: venue.kind for venue in loader.venues_from_file(VENUES)}
        assert assigned == {
            "monobank_uah": "bank",
            "binance": "exchange",
            "coinbase": "exchange",
            "ibkr_usd": "broker",
            "inzhur": "platform",
            "deel": "payroll",
            "fop": "bank",
            "payoneer": "platform",
            "foreign_bank_usd": "bank",
        }


class TestAnUnknownKindIsRefusedAtLoad:
    def test_it_names_the_file_and_the_field(self, tmp_path: Path) -> None:
        broken = tmp_path / "venues.toml"
        _edit_into(broken, 'kind       = "exchange"', 'kind       = "crypto_exchange"')
        with pytest.raises(DeclarationError) as raised:
            loader.venues_from_file(broken)
        assert raised.value.file == broken
        assert raised.value.field_path == "venue[binance].kind"
        assert "crypto_exchange" in raised.value.problem
        # The remedy lists what would have worked, because an unrecognised name is almost
        # always a typo.
        assert raised.value.remedy is not None
        assert "bank" in raised.value.remedy

    def test_a_missing_kind_is_refused_rather_than_defaulted(self, tmp_path: Path) -> None:
        broken = tmp_path / "venues.toml"
        text = VENUES.read_text(encoding="utf-8")
        lines = [line for line in text.splitlines(keepends=True) if not line.startswith("kind ")]
        broken.write_text("".join(lines), encoding="utf-8")
        with pytest.raises(DeclarationError) as raised:
            loader.venues_from_file(broken)
        assert raised.value.file == broken

    def test_the_whole_root_refuses_too(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        _edit(root / "venues.toml", 'kind       = "broker"', 'kind       = "brokerage"')
        with pytest.raises(DeclarationError) as raised:
            resolver.ramp_from_data_root(root, base_currency=Currency.UAH)
        assert raised.value.field_path == "venue[ibkr_usd].kind"


class TestAddingAVenueStaysDataOnly:
    def test_a_tenth_venue_loads_with_no_engine_change(self, tmp_path: Path) -> None:
        broken = tmp_path / "venues.toml"
        broken.write_text(
            VENUES.read_text(encoding="utf-8") + '\n[[venue]]\nid         = "a_tenth_place"\n'
            'name       = "A tenth place (SYNTHETIC FIXTURE)"\n'
            'kind       = "bank"\ncurrencies = ["UAH"]\n',
            encoding="utf-8",
        )
        declared = loader.venues_from_file(broken)
        assert declared[-1].id == "a_tenth_place"
        assert declared[-1].kind == "bank"


def _edit_into(target: Path, old: str, new: str) -> None:
    text = VENUES.read_text(encoding="utf-8")
    assert old in text, f"the shipped fixture no longer contains {old!r}; this test is stale"
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
