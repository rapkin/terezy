"""Every broken crediting-destination row fails at load, and the shipped table resolves.

The table is **normative rather than illustrative**: a destination it does not name cannot
be resolved by reasoning about it and refuses instead. Two consequences are checked here.

*Every row records the judgement that put it there.* `grounds` is required and non-empty,
because deciding whether a source's proposition *reaches* a destination is a judgement, and
a verdict with no recorded reasoning is the row this feature's own history exists to prevent.

*A candidate is a declared scheme or a stated reason it is not.* Naming a scheme nobody
declared would be the obvious way to spell an uncomputable candidate, and it collides with
the standing rule that an unresolvable reference fails at load. Declaring the reason keeps
both intact.

The last class loads the **shipped** table, because a battery of broken rows proves nothing
about the rows the project uses — and the shipped counts are what SC-017 pins.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from terezy.core.primitives.currency import Currency
from terezy.core.tax import scheme as schemes
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"

ROW = """
[[destination]]
scheme          = "{scheme}"
venue           = "{venue}"
verdict         = "{verdict}"
grounds         = "{grounds}"
resolution_path = "SYNTHETIC FIXTURE -- an invented way of closing an invented question."
kind            = "tax_rule"
source          = "SYNTHETIC FIXTURE -- an invented judgement."
retrieved_on    = "2026-08-30"
verified_on     = ""
"""

READING = """
  [[destination.reading]]
  id            = "{id}"
  label         = "SYNTHETIC FIXTURE -- an invented reading"
  scheme        = "{scheme}"
  recognised_on = "{recognised_on}"
  kind          = "tax_rule"
  source        = "SYNTHETIC FIXTURE -- an invented reading."
  retrieved_on  = "2026-08-30"
  verified_on   = ""
"""

UNCOMPUTABLE = """
  [[destination.reading]]
  id                   = "{id}"
  label                = "SYNTHETIC FIXTURE -- an invented candidate nobody declared rates for"
  uncomputable_because = "{because}"
  kind                 = "tax_rule"
  source               = "SYNTHETIC FIXTURE -- an invented candidate."
  retrieved_on         = "2026-08-30"
  verified_on          = ""
"""


def _row(*, verdict: str = "unsettled", grounds: str = "SYNTHETIC FIXTURE -- a judgement.") -> str:
    return ROW.format(scheme="xx_scheme", venue="xx_venue", verdict=verdict, grounds=grounds)


def _body(*, verdict: str = "unsettled", readings: str = "") -> str:
    return _row(verdict=verdict) + (
        readings or READING.format(id="one", scheme="xx_scheme", recognised_on="credited")
    )


def _file(tmp_path: Path, body: str, *, name: str = "xx.toml") -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _load_error(path: Path) -> DeclarationError:
    with pytest.raises(DeclarationError) as caught:
        loader.destinations_from_file(path)
    return caught.value


def test_the_control_case_loads_so_every_refusal_below_is_about_one_change(
    tmp_path: Path,
) -> None:
    rows = loader.destinations_from_file(_file(tmp_path, _body()))

    assert [row.venue_id for row in rows] == ["xx_venue"]
    assert rows[0].verdict is schemes.Verdict.UNSETTLED
    assert [reading.id for reading in rows[0].readings] == ["one"]
    assert rows[0].readings[0].recognised_on == "credited"


class TestOneFileReadInIsolation:
    def test_an_unknown_verdict_is_refused_and_the_refusal_lists_the_known_ones(
        self, tmp_path: Path
    ) -> None:
        error = _load_error(_file(tmp_path, _body(verdict="probably_fine")))

        assert "probably_fine" in str(error)
        assert "interpreted" in str(error)
        assert "unsettled" in str(error)

    def test_a_row_with_empty_grounds_is_refused(self, tmp_path: Path) -> None:
        """A verdict with no recorded reasoning is the row that goes stale unnoticed."""
        body = _row(grounds="") + READING.format(
            id="one", scheme="xx_scheme", recognised_on="credited"
        )
        error = _load_error(_file(tmp_path, body))

        assert "grounds" in str(error)

    def test_a_row_with_no_reading_at_all_is_refused(self, tmp_path: Path) -> None:
        """It says nothing about the destination it names, which a missing row already says."""
        error = _load_error(_file(tmp_path, _row() + "\n  reading = []\n"))

        assert "reading" in str(error)

    def test_a_reading_declaring_both_a_scheme_and_a_reason_is_refused(
        self, tmp_path: Path
    ) -> None:
        both = READING.format(id="one", scheme="xx_scheme", recognised_on="credited").replace(
            'verified_on   = ""', 'verified_on   = ""\n  uncomputable_because = "both"'
        )
        error = _load_error(_file(tmp_path, _row() + both))

        assert "reading[one]" in str(error)

    def test_a_reading_declaring_neither_is_refused(self, tmp_path: Path) -> None:
        neither = UNCOMPUTABLE.format(id="one", because="x").replace(
            '  uncomputable_because = "x"\n', ""
        )
        error = _load_error(_file(tmp_path, _row() + neither))

        assert "reading[one]" in str(error)

    def test_a_reading_naming_a_scheme_with_no_date_name_is_refused(self, tmp_path: Path) -> None:
        """Borrowing another reading's date would compute the reading this one contests."""
        without = READING.format(id="one", scheme="xx_scheme", recognised_on="credited").replace(
            '  recognised_on = "credited"\n', ""
        )
        error = _load_error(_file(tmp_path, _row() + without))

        assert "recognised_on" in str(error)

    def test_an_uncomputable_candidate_naming_a_date_is_refused(self, tmp_path: Path) -> None:
        """A field nothing reads is a field a reader believes is doing something."""
        dated = UNCOMPUTABLE.format(id="one", because="nobody declared its rates").replace(
            '  kind                 = "tax_rule"',
            '  recognised_on        = "credited"\n  kind                 = "tax_rule"',
        )
        error = _load_error(_file(tmp_path, _row() + dated))

        assert "recognised_on" in str(error)

    def test_two_readings_sharing_an_id_are_refused(self, tmp_path: Path) -> None:
        body = _body() + READING.format(id="one", scheme="xx_scheme", recognised_on="credited")
        error = _load_error(_file(tmp_path, body))

        assert "one" in str(error)

    def test_an_interpreted_row_with_two_readings_is_refused(self, tmp_path: Path) -> None:
        """An interpreted destination produces a charge, and a charge cannot be two figures."""
        body = _body(
            verdict="interpreted",
            readings=READING.format(id="one", scheme="xx_scheme", recognised_on="credited")
            + READING.format(id="two", scheme="xx_scheme", recognised_on="credited"),
        )
        error = _load_error(_file(tmp_path, body))

        assert "interpreted" in str(error)

    def test_an_interpreted_row_whose_only_candidate_is_uncomputable_is_refused(
        self, tmp_path: Path
    ) -> None:
        body = _body(
            verdict="interpreted",
            readings=UNCOMPUTABLE.format(id="one", because="nobody declared its rates"),
        )
        error = _load_error(_file(tmp_path, body))

        assert "interpreted" in str(error)

    def test_an_uncomputable_candidate_loads_and_is_named_rather_than_dropped(
        self, tmp_path: Path
    ) -> None:
        body = _body(
            readings=READING.format(id="one", scheme="xx_scheme", recognised_on="credited")
            + UNCOMPUTABLE.format(id="two", because="no source cites its rates")
        )
        rows = loader.destinations_from_file(_file(tmp_path, body))

        assert [reading.id for reading in rows[0].readings] == ["one", "two"]
        assert rows[0].readings[1].uncomputable_because == "no source cites its rates"
        assert rows[0].readings[1].scheme_id is None


class TestReferencesResolvedAcrossFiles:
    """What a per-file validator structurally cannot check."""

    @staticmethod
    def _root(tmp_path: Path) -> Path:
        root = tmp_path / "data"
        shutil.copytree(DATA_ROOT, root)
        return root

    def _resolve(self, root: Path) -> DeclarationError:
        with pytest.raises(DeclarationError) as caught:
            resolver.schemes_from_data_root(root, base_currency=Currency.UAH)
        return caught.value

    def test_a_row_naming_a_scheme_nobody_declares_is_refused(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        table = root / "tax" / "destinations" / "ua.toml"
        table.write_text(
            table.read_text(encoding="utf-8").replace(
                'scheme          = "ua_fop_group_3_non_vat"', 'scheme          = "xx_nobody"', 1
            ),
            encoding="utf-8",
        )
        error = self._resolve(root)

        assert "xx_nobody" in str(error)
        assert "ua_fop_group_3_non_vat" in str(error)

    def test_a_reading_naming_a_scheme_nobody_declares_is_refused(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        table = root / "tax" / "destinations" / "ua.toml"
        table.write_text(
            table.read_text(encoding="utf-8").replace(
                '  scheme        = "ua_personal_income"', '  scheme        = "xx_nobody"', 1
            ),
            encoding="utf-8",
        )
        error = self._resolve(root)

        assert "xx_nobody" in str(error)

    def test_a_row_naming_a_venue_nobody_declares_is_refused(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        table = root / "tax" / "destinations" / "ua.toml"
        table.write_text(
            table.read_text(encoding="utf-8").replace(
                'venue           = "payoneer"', 'venue           = "xx_nowhere"', 1
            ),
            encoding="utf-8",
        )
        error = self._resolve(root)

        assert "xx_nowhere" in str(error)

    def test_two_rows_for_one_scheme_and_venue_name_both_files(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        table = root / "tax" / "destinations" / "ua.toml"
        (root / "tax" / "destinations" / "second.toml").write_text(
            table.read_text(encoding="utf-8"), encoding="utf-8"
        )
        error = self._resolve(root)

        assert "ua.toml" in str(error)
        assert "second.toml" in str(error)

    def test_two_files_declaring_one_scheme_identity_name_both(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        shipped = root / "tax" / "schemes" / "ua_fop_group_3.toml"
        (root / "tax" / "schemes" / "copy.toml").write_text(
            shipped.read_text(encoding="utf-8"), encoding="utf-8"
        )
        error = self._resolve(root)

        assert "ua_fop_group_3.toml" in str(error)
        assert "copy.toml" in str(error)

    def test_a_stream_naming_a_treatment_nobody_declares_is_refused(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        streams = root / "streams" / "owner-001.toml"
        streams.write_text(
            streams.read_text(encoding="utf-8").replace(
                'tax_scheme  = "ua_fop_group_3_non_vat"', 'tax_scheme  = "xx_nobody"'
            ),
            encoding="utf-8",
        )
        error = self._resolve(root)

        assert "xx_nobody" in str(error)
        assert "contract_usd" in str(error)

    def test_a_stream_naming_a_reading_only_scheme_is_refused(self, tmp_path: Path) -> None:
        """Those rates exist only inside a what-if that says it is not the tax owed."""
        root = self._root(tmp_path)
        streams = root / "streams" / "owner-001.toml"
        streams.write_text(
            streams.read_text(encoding="utf-8").replace(
                'tax_scheme  = "ua_fop_group_3_non_vat"', 'tax_scheme  = "ua_personal_income"'
            ),
            encoding="utf-8",
        )
        error = self._resolve(root)

        assert "ua_personal_income" in str(error)
        assert "not the tax owed" in str(error)


class TestTheShippedTable:
    """SC-016 and SC-017's per-destination counts, against the file the project uses."""

    @staticmethod
    def _resolved() -> resolver.SchemeDeclarations:
        return resolver.schemes_from_data_root(DATA_ROOT, base_currency=Currency.UAH)

    def test_every_declared_destination_resolves(self) -> None:
        declared = self._resolved()
        assert set(declared.schemes) == {"ua_fop_group_3_non_vat", "ua_personal_income"}
        assert {venue for _, venue in declared.destinations} == {
            "fop",
            "payoneer",
            "monobank_uah",
            "coinbase",
            "foreign_bank_usd",
        }

    def test_only_the_fop_account_is_interpreted(self) -> None:
        rows = self._resolved().destinations
        interpreted = {
            venue for (_, venue), row in rows.items() if row.verdict is schemes.Verdict.INTERPRETED
        }
        assert interpreted == {"fop"}

    @pytest.mark.parametrize(
        ("venue", "count"),
        [
            ("fop", 1),
            ("payoneer", 3),
            ("monobank_uah", 1),
            ("coinbase", 1),
            ("foreign_bank_usd", 2),
        ],
    )
    def test_each_destination_declares_the_readings_the_specification_counts(
        self, venue: str, count: int
    ) -> None:
        rows = self._resolved().destinations
        assert len(rows[("ua_fop_group_3_non_vat", venue)].readings) == count

    def test_every_row_records_its_grounds_and_its_way_out(self) -> None:
        for row in self._resolved().destinations.values():
            assert row.grounds.strip(), row.venue_id
            assert row.resolution_path.strip(), row.venue_id

    def test_every_unsettled_row_names_the_consultation_that_would_close_it(self) -> None:
        for row in self._resolved().destinations.values():
            if row.verdict is schemes.Verdict.UNSETTLED:
                assert "індивідуальна податкова консультація" in row.resolution_path, row.venue_id

    def test_the_shipped_scheme_declares_its_nil_rather_than_omitting_it(self) -> None:
        """SC-007: the one value sourced to the owner rather than to a public text."""
        scheme = self._resolved().schemes["ua_fop_group_3_non_vat"]
        standing = schemes.component_standing(scheme, "esv", period="2026-09")
        assert isinstance(standing, schemes.ComponentAmount), standing
        assert standing.amount.amount == 0.0
        citations = {ref.citation for ref in standing.provenance.sources}
        assert any("The owner, stating his own tax position" in text for text in citations)
        assert all(ref.verified_on is None for ref in standing.provenance.sources)

    def test_the_personal_income_scheme_declares_no_such_component_at_all(self) -> None:
        """The other of SC-011's three nils, on shipped data rather than on a fixture."""
        scheme = self._resolved().schemes["ua_personal_income"]
        standing = schemes.component_standing(scheme, "esv", period="2026-09")
        assert isinstance(standing, schemes.ComponentNotDeclared), standing

    def test_the_levy_carries_its_termination_as_recorded_context(self) -> None:
        """FR-008a: a schedule declaring a commencement and no end asserts a permanent charge."""
        scheme = self._resolved().schemes["ua_fop_group_3_non_vat"]
        levy = next(item for item in scheme.rate_components if item.id == "viyskovyi_zbir")
        assert [item.id for item in levy.context] == ["termination_on_the_end_of_martial_law"]
        recorded = levy.context[0]
        assert "воєнний стан" in recorded.statement
        assert recorded.not_applied_because.strip()
        assert recorded.provenance.sources

    def test_the_levy_cites_4113_for_its_date_and_never_4015(self) -> None:
        """FR-008. A rate whose own cited source contradicts its date is undetectable."""
        scheme = self._resolved().schemes["ua_fop_group_3_non_vat"]
        levy = next(item for item in scheme.rate_components if item.id == "viyskovyi_zbir")
        entry = levy.schedule[0]
        citation = next(iter(entry.provenance.sources)).citation
        assert entry.rate == 0.01
        assert entry.effective_from.isoformat() == "2025-01-01"
        assert "4113-IX" in citation
        assert "4015-IX" in citation
        assert "з 1 жовтня 2024 року" in citation


class TestTheSeriesIsResolvedRatherThanChosenByACaller:
    """The base is struck at the series the jurisdiction NAMES, and nobody picks one by hand.

    Picking a series is exactly how a base comes to rest on one the jurisdiction did not name,
    which 011 already writes a refusal for and which a caller cannot be relied on to avoid.
    """

    def test_the_shipped_scheme_resolves_the_series_its_jurisdiction_names(self) -> None:
        declared = resolver.schemes_from_data_root(DATA_ROOT, base_currency=Currency.UAH)
        series = declared.official_rates["ua"]
        assert series is not None
        assert series.id == "ua_nbu_usd"
        assert series.pair == (Currency.UAH, Currency.USD)

    def test_a_scheme_assessing_in_another_currency_than_its_jurisdiction_is_refused(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "data"
        shutil.copytree(DATA_ROOT, root)
        scheme = root / "tax" / "schemes" / "ua_fop_group_3.toml"
        scheme.write_text(
            scheme.read_text(encoding="utf-8").replace(
                'tax_currency      = "UAH"', 'tax_currency      = "USD"', 1
            ),
            encoding="utf-8",
        )
        with pytest.raises(DeclarationError) as caught:
            resolver.schemes_from_data_root(root, base_currency=Currency.UAH)

        assert "tax_currency" in str(caught.value)
        assert "UAH" in str(caught.value)
        assert "ua.toml" in str(caught.value)
