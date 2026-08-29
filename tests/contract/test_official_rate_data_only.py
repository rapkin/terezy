"""Two data-only claims, executed against a scratch data root with no source line changed.

**SC-011 -- nothing treats one country's rate as *the* rate.** Principle II applied to the
input most likely to be hard-coded as a singleton. A second series with a distinct identity is
declared purely as data, loads, and is addressable; and the series a tax base uses is the one
the jurisdiction *declared*, named in the output, rather than whichever loaded first. The
second file is named so it sorts **before** the shipped one, because "whichever loaded first"
is only a falsifiable claim when the wrong answer would win.

**SC-015 -- the declared-rule path exists and reports what it applied.** A synthetic series
declares a non-publication-day rule in the calendar-free form FR-011 admits: an explicitly
enumerated mapping, this date's rate governs that date, listed. The base is struck from
another date's observation and the output states **both** dates, so a Friday rate applied to a
Sunday event is visible rather than implied.

⚙ It is deliberately **not** a claim about the Ukrainian rule, which needs a calendar nothing
declares (``data/official_rates/ua_nbu_usd.toml``). What is exercised is that the *path*
exists and that a rule expressible without a calendar reaches it -- and the enumerated form
needs no calendar precisely because it derives nothing: every date it governs is written down,
which is what the second test below asserts.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from datetime import date
from pathlib import Path

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.staleness import ObservationKind
from terezy.core.primitives.tolerance import is_close
from terezy.core.tax import official_rate
from terezy.data.declarations import loader, resolver

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"

FRIDAY = date(2026, 3, 6)
SATURDAY = date(2026, 3, 7)
SUNDAY = date(2026, 3, 8)
MONDAY = date(2026, 3, 9)
"""Weekday names for the reader. Nothing derives them; the rule below lists each date."""

SECOND_SERIES = """
observation = []

[series]
id             = "xx_reserve_bank_usd"
authority      = "SYNTHETIC FIXTURE -- an invented second authority, no country's"
pair           = ["UAH", "USD"]
quotation_unit = 100.0
"""

WITH_RULE = """
[series]
id             = "xx_enumerated_usd"
authority      = "SYNTHETIC FIXTURE -- an invented authority"
pair           = ["UAH", "USD"]
quotation_unit = 1.0

[non_publication_rule]
id           = "xx_weekend_enumerated"
kind         = "tax_rule"
source       = "SYNTHETIC FIXTURE -- an invented rule, enumerated per date."
retrieved_on = "2026-08-24"
verified_on  = ""

[[non_publication_rule.day]]
applies_to  = "2026-03-07"
governed_by = "2026-03-06"

[[non_publication_rule.day]]
applies_to  = "2026-03-08"
governed_by = "2026-03-06"

[[observation]]
on_date      = "2026-03-06"
value        = 40.0
kind         = "official_rate"
source       = "SYNTHETIC FIXTURE -- an invented rate."
retrieved_on = "2026-08-24"
verified_on  = ""

[[observation]]
on_date      = "2026-03-09"
value        = 44.0
kind         = "official_rate"
source       = "SYNTHETIC FIXTURE -- an invented rate."
retrieved_on = "2026-08-24"
verified_on  = ""
"""


def _kinds(root: Path) -> Mapping[str, ObservationKind]:
    """The declared thresholds, so a rule table's kind is checked against a real registry."""
    return {
        kind.id: kind
        for kind in loader.observation_kinds_from_file(root / "observation_kinds.toml")
    }


def _scratch_root(tmp_path: Path, *, name: str, body: str) -> Path:
    """A copy of the shipped data root plus one declared official-rate file."""
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    (root / "official_rates" / name).write_text(body, encoding="utf-8")
    return root


class TestASecondSeriesIsADataOnlyAddition:
    def test_it_loads_and_is_addressable_beside_the_first(self, tmp_path: Path) -> None:
        root = _scratch_root(tmp_path, name="aa_second.toml", body=SECOND_SERIES)

        declared = resolver.official_rates_from_data_root(root, _kinds(root))

        assert set(declared.series) == {"ua_nbu_usd", "xx_reserve_bank_usd"}
        assert declared.series["xx_reserve_bank_usd"].quotation_unit == 100.0
        assert declared.files["xx_reserve_bank_usd"].name == "aa_second.toml"

    def test_the_jurisdiction_gets_the_series_it_declared_not_the_first_loaded(
        self, tmp_path: Path
    ) -> None:
        """``aa_second.toml`` sorts first, so load order would give the wrong answer."""
        root = _scratch_root(tmp_path, name="aa_second.toml", body=SECOND_SERIES)

        rules = resolver.tax_rules_from_data_root(root, resolver.from_data_root(root))

        assert rules["ua"].official_rate is not None
        assert rules["ua"].official_rate.id == "ua_nbu_usd"


class TestADeclaredRuleReachesTheStruckBase:
    def test_the_base_states_which_dates_rate_was_applied_to_which_dates_event(
        self, tmp_path: Path
    ) -> None:
        root = _scratch_root(tmp_path, name="xx_enumerated.toml", body=WITH_RULE)
        series = resolver.official_rates_from_data_root(root, _kinds(root)).series[
            "xx_enumerated_usd"
        ]

        struck = official_rate.strike_base(
            Money(1_000.0, Currency.USD, prov.EMPTY),
            series,
            tax_currency=Currency.UAH,
            on_date=SUNDAY,
        )

        assert isinstance(struck, official_rate.TaxCurrencyConversion), struck
        assert struck.event_date == SUNDAY
        assert struck.rate_date == FRIDAY
        assert struck.applied_rule == "xx_weekend_enumerated"
        assert is_close(struck.base.amount, 40_000.0)

    def test_the_rule_governs_only_the_dates_it_enumerates(self, tmp_path: Path) -> None:
        """It derives nothing, which is exactly why it needs no calendar. Tuesday the 10th is
        as much a non-publication day as Sunday the 8th for all this rule knows, and it says
        nothing about it."""
        root = _scratch_root(tmp_path, name="xx_enumerated.toml", body=WITH_RULE)
        series = resolver.official_rates_from_data_root(root, _kinds(root)).series[
            "xx_enumerated_usd"
        ]

        for governed, expected in ((SATURDAY, FRIDAY), (MONDAY, MONDAY)):
            struck = official_rate.strike_base(
                Money(1.0, Currency.USD, prov.EMPTY),
                series,
                tax_currency=Currency.UAH,
                on_date=governed,
            )
            assert isinstance(struck, official_rate.TaxCurrencyConversion), struck
            assert struck.rate_date == expected

        beyond = official_rate.strike_base(
            Money(1.0, Currency.USD, prov.EMPTY),
            series,
            tax_currency=Currency.UAH,
            on_date=date(2026, 3, 10),
        )
        assert isinstance(beyond, official_rate.OfficialRateUndeclaredOnDate), beyond
