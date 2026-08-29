"""FR-004 and SC-004: every broken official-rate file fails at load, naming the offence.

*"Loading official-rate data MUST fail loudly -- naming the file and the offending field or
date -- on a malformed value, an unrecognised field, a missing required field, a duplicate
date, a non-positive rate, a missing or non-positive quotation unit, a date that has not yet
arrived, an observation carrying two sides, or a duplicated series identity. No default MUST
be substituted for anything absent."*

A battery rather than a handful, because SC-004 is a claim about *every* way a file can be
wrong and a sampled version would go stale the first time somebody added a field.

**Two cases are this feature's own.**

*An observation carrying two sides.* A ``buy_side`` on an official rate is not a richer
declaration, it is a channel with a government's name on it -- and the whole distinction the
feature rests on would be gone. The mechanism is ``extra="forbid"``: there is no field for a
second side, so declaring one is an unrecognised field.

*A rule that redirects a date the series publishes for.* A non-publication-day rule speaks
for dates the publisher does **not** publish for. One claiming a published date contradicts
the publication, and the two answers would then depend on lookup order.

The last tests load the **shipped** ``data/official_rates/ua_nbu_usd.toml``, because a
battery of broken files proves nothing about the file the project actually uses.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.staleness import ObservationKind
from terezy.core.tax import official_rate
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED = REPO_ROOT / "data" / "official_rates" / "ua_nbu_usd.toml"

EMPTY_SERIES = """
# ``observation`` sits above ``[series]`` because TOML binds a bare key to the table it
# follows: written below, it would declare ``series.observation``.
observation = []

[series]
id             = "xx_official_usd"
authority      = "SYNTHETIC FIXTURE -- an invented publishing authority"
pair           = ["UAH", "USD"]
quotation_unit = 1.0
"""

HEADER = EMPTY_SERIES.replace("observation = []\n", "")

OBSERVATION = """
[[observation]]
on_date      = "{on_date}"
value        = {value}
kind         = "official_rate"
source       = "SYNTHETIC FIXTURE -- an invented rate."
retrieved_on = "{retrieved_on}"
verified_on  = ""
"""

RULE = """
[non_publication_rule]
id           = "xx_rule"
kind         = "tax_rule"
source       = "SYNTHETIC FIXTURE -- an invented rule, cited so the path can be exercised."
retrieved_on = "2026-08-24"
verified_on  = ""

[[non_publication_rule.day]]
applies_to  = "{applies_to}"
governed_by = "{governed_by}"
"""


_A_DECLARED_KIND = ObservationKind(
    id="tax_rule",
    staleness_days=180,
    note="SYNTHETIC FIXTURE -- a registry of one, so the refusal can list what would have worked.",
)


def _shipped_root(tmp_path: Path) -> Path:
    """A copy of the shipped data root, so a case changes exactly one thing about it."""
    root = tmp_path / "data"
    shutil.copytree(SHIPPED.parents[1], root)
    return root


def _file(tmp_path: Path, body: str, *, name: str = "xx.toml") -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _body(*, quotation_unit: str = "1.0") -> str:
    body = HEADER.replace("quotation_unit = 1.0", f"quotation_unit = {quotation_unit}")
    body += OBSERVATION.format(on_date="2026-03-02", value=41.50, retrieved_on="2026-08-24")
    body += OBSERVATION.format(on_date="2026-03-03", value=42.25, retrieved_on="2026-08-24")
    return body


def _load_error(path: Path) -> DeclarationError:
    with pytest.raises(DeclarationError) as caught:
        loader.official_rate_from_file(path)
    return caught.value


def test_the_control_case_loads_so_every_refusal_below_is_about_one_change(
    tmp_path: Path,
) -> None:
    series = loader.official_rate_from_file(_file(tmp_path, _body()))

    assert series.id == "xx_official_usd"
    assert series.pair == (Currency.UAH, Currency.USD)
    assert series.quotation_unit == 1.0
    assert series.rule is None
    assert tuple(item.on_date for item in series.observations) == (
        date(2026, 3, 2),
        date(2026, 3, 3),
    )
    stamped = {ref.kind for item in series.observations for ref in item.provenance.sources}
    assert stamped == {"official_rate"}


class TestOneFileReadInIsolation:
    """Every refusal a single file can earn, each naming the file and the field or date."""

    def test_a_malformed_value_is_refused_rather_than_coerced(self, tmp_path: Path) -> None:
        body = HEADER + OBSERVATION.format(
            on_date="2026-03-02", value='"41.50"', retrieved_on="2026-08-24"
        )
        error = _load_error(_file(tmp_path, body))

        assert "value" in str(error)
        assert "xx.toml" in str(error)

    def test_an_unrecognised_field_is_refused(self, tmp_path: Path) -> None:
        error = _load_error(_file(tmp_path, _body() + '\nnote_to_self = "hello"\n'))

        assert "note_to_self" in str(error)

    def test_a_missing_required_field_is_refused(self, tmp_path: Path) -> None:
        """``authority`` is half of what makes a second country's series a data-only
        addition, so a file that omits it is a series nobody can tell apart from another."""
        without = "\n".join(
            line for line in _body().splitlines() if not line.startswith("authority")
        )
        error = _load_error(_file(tmp_path, without))

        assert "authority" in str(error)

    def test_a_missing_verified_on_is_refused_rather_than_defaulted(self, tmp_path: Path) -> None:
        """Empty is a state; absent is an oversight, and the two must not look alike."""
        error = _load_error(_file(tmp_path, _body().replace('verified_on  = ""', "", 1)))

        assert "verified_on" in str(error)

    def test_a_duplicate_date_is_refused(self, tmp_path: Path) -> None:
        body = _body() + OBSERVATION.format(
            on_date="2026-03-02", value=99.0, retrieved_on="2026-08-24"
        )
        error = _load_error(_file(tmp_path, body))

        assert "2026-03-02" in str(error)

    def test_dates_running_backwards_are_refused_rather_than_sorted(self, tmp_path: Path) -> None:
        body = HEADER
        body += OBSERVATION.format(on_date="2026-03-03", value=42.25, retrieved_on="2026-08-24")
        body += OBSERVATION.format(on_date="2026-03-02", value=41.50, retrieved_on="2026-08-24")
        error = _load_error(_file(tmp_path, body))

        assert "2026-03-02" in str(error)

    @pytest.mark.parametrize("value", ["0.0", "-41.5"])
    def test_a_non_positive_rate_is_refused(self, tmp_path: Path, value: str) -> None:
        body = HEADER + OBSERVATION.format(
            on_date="2026-03-02", value=value, retrieved_on="2026-08-24"
        )
        error = _load_error(_file(tmp_path, body))

        assert "value" in str(error)

    def test_a_missing_quotation_unit_is_refused_rather_than_defaulted_to_one(
        self, tmp_path: Path
    ) -> None:
        """A rate quoted per 100 read as per 1 is wrong by two orders of magnitude and looks
        entirely reasonable, which is why there is no default (FR-002, SC-012)."""
        error = _load_error(_file(tmp_path, _body().replace("quotation_unit = 1.0\n", "")))

        assert "quotation_unit" in str(error)

    @pytest.mark.parametrize("unit", ["0.0", "-100.0"])
    def test_a_non_positive_quotation_unit_is_refused(self, tmp_path: Path, unit: str) -> None:
        error = _load_error(_file(tmp_path, _body(quotation_unit=unit)))

        assert "quotation_unit" in str(error)

    def test_a_rate_dated_after_its_own_retrieval_is_refused(self, tmp_path: Path) -> None:
        """A rate for a date that has not arrived is a forecast wearing an observation's
        clothes -- and this one would silently set a legal base. Checked against the file's
        own retrieval date rather than a clock, so the file loads the same way for ever."""
        body = HEADER + OBSERVATION.format(
            on_date="2027-01-04", value=41.50, retrieved_on="2026-08-24"
        )
        error = _load_error(_file(tmp_path, body))

        assert "2027-01-04" in str(error)
        assert "2026-08-24" in str(error)

    def test_an_observation_carrying_two_sides_is_refused(self, tmp_path: Path) -> None:
        """Two sides is what a channel has; an official rate that acquired a spread would be a
        channel with a government's name on it."""
        body = _body() + "\n[observation.buy_side]\npremium_per_unit = 0.5\n"
        error = _load_error(_file(tmp_path, body))

        assert "buy_side" in str(error)
        assert "xx.toml" in str(error)

    def test_a_rule_with_no_citation_is_refused(self, tmp_path: Path) -> None:
        """FR-011: a rule is declared data carrying its own citation, and a paraphrase is not
        one."""
        rule = RULE.format(applies_to="2026-03-04", governed_by="2026-03-03")
        uncited = "\n".join(
            'source       = ""' if line.startswith("source") else line for line in rule.splitlines()
        )
        error = _load_error(_file(tmp_path, _body() + uncited))

        assert "source" in str(error)

    def test_a_rule_governed_by_a_date_the_series_does_not_declare_is_refused(
        self, tmp_path: Path
    ) -> None:
        body = _body() + RULE.format(applies_to="2026-03-04", governed_by="2026-03-01")
        error = _load_error(_file(tmp_path, body))

        assert "2026-03-01" in str(error)

    def test_a_rule_redirecting_a_date_the_series_publishes_for_is_refused(
        self, tmp_path: Path
    ) -> None:
        body = _body() + RULE.format(applies_to="2026-03-03", governed_by="2026-03-02")
        error = _load_error(_file(tmp_path, body))

        assert "2026-03-03" in str(error)

    def test_a_rule_listing_one_date_twice_is_refused(self, tmp_path: Path) -> None:
        body = _body() + RULE.format(applies_to="2026-03-04", governed_by="2026-03-03")
        body += (
            "\n[[non_publication_rule.day]]\n"
            'applies_to  = "2026-03-04"\n'
            'governed_by = "2026-03-02"\n'
        )
        error = _load_error(_file(tmp_path, body))

        assert "2026-03-04" in str(error)

    @pytest.mark.parametrize(
        "pair",
        ['["UAH"]', '["UAH", "USD", "USD"]'],
    )
    def test_a_pair_that_is_not_two_currencies_is_refused(self, tmp_path: Path, pair: str) -> None:
        """The order of the two decides which direction the series converts, so a list that
        is not a pair has no direction to read off."""
        error = _load_error(_file(tmp_path, _body().replace('["UAH", "USD"]', pair)))

        assert "pair" in str(error)

    def test_a_series_quoting_a_currency_against_itself_is_refused(self, tmp_path: Path) -> None:
        """An amount already in the tax currency needs no official rate at all (FR-009), so a
        self-quote is a series with nothing to convert."""
        error = _load_error(_file(tmp_path, _body().replace('["UAH", "USD"]', '["UAH", "UAH"]')))

        assert "pair" in str(error)

    def test_a_rule_declaring_an_empty_list_of_days_is_refused(self, tmp_path: Path) -> None:
        """A rule that governs no date grants nothing and refuses nothing, and reads as though
        the dates it was written for were covered.

        ⚙ Written as ``day = []`` and **not** by deleting the rows, because those are two
        different refusals: an absent key is the schema's (the field has no default, so it
        cannot be omitted), and this is the loader's. A first draft of this test deleted the
        rows, passed, and stayed green with the loader's guard disabled.
        """
        rule = RULE.format(applies_to="2026-03-04", governed_by="2026-03-03")
        empty = rule[: rule.index("[[non_publication_rule.day]]")] + "day = []\n"
        error = _load_error(_file(tmp_path, _body() + empty))

        assert "with no days" in str(error)

    def test_a_rule_omitting_its_days_entirely_is_refused_by_the_schema(
        self, tmp_path: Path
    ) -> None:
        """The other half: absent and empty are different states and neither defaults."""
        rule = RULE.format(applies_to="2026-03-04", governed_by="2026-03-03")
        error = _load_error(
            _file(tmp_path, _body() + rule[: rule.index("[[non_publication_rule.day]]")])
        )

        assert "day" in str(error)
        assert "is required and is absent" in str(error)

    def test_a_series_with_no_observations_loads_when_it_says_so(self, tmp_path: Path) -> None:
        """The one place this departs from ``cpi_from_file``, which refuses an empty series.

        An official-rate file is the declared shape a fetch script writes into, and the
        Ukrainian series ships that way today: no value may be invented to populate it, and
        every date asked of it refuses by name meanwhile (FR-017, plan research D6).
        """
        series = loader.official_rate_from_file(_file(tmp_path, EMPTY_SERIES))

        assert series.observations == ()
        assert series.rule is None

    def test_forgetting_the_observations_entirely_is_still_refused(self, tmp_path: Path) -> None:
        """``observation = []`` is a statement; an absent key is an oversight, and a default
        would make the two indistinguishable."""
        error = _load_error(_file(tmp_path, HEADER))

        assert "observation" in str(error)
        assert "is required and is absent" in str(error)


class TestTheRelationsOneFileCannotSee:
    """What a per-file validator structurally cannot check."""

    def test_two_files_declaring_one_series_identity_are_refused_naming_both(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "data" / "official_rates"
        root.mkdir(parents=True)
        _file(root, _body(), name="first.toml")
        _file(root, _body(), name="second.toml")

        with pytest.raises(DeclarationError) as caught:
            resolver.official_rates_from_data_root(tmp_path / "data", {})

        assert "first.toml" in str(caught.value)
        assert "second.toml" in str(caught.value)

    def test_a_jurisdiction_naming_a_series_no_file_declares_is_refused(
        self, tmp_path: Path
    ) -> None:
        """FR-007: no default series and no fallback to whichever one loaded first."""
        root = _shipped_root(tmp_path)
        timing = root / "tax" / "timing" / "ua.toml"
        timing.write_text(
            timing.read_text(encoding="utf-8").replace("ua_nbu_usd", "no_such_series"),
            encoding="utf-8",
        )

        with pytest.raises(DeclarationError) as caught:
            resolver.tax_rules_from_data_root(root, resolver.from_data_root(root))

        assert "no_such_series" in str(caught.value)
        assert "official_rate_series" in str(caught.value)

    def test_a_series_quoting_the_tax_currency_the_wrong_way_round_is_refused(
        self, tmp_path: Path
    ) -> None:
        """The guard whose message claims the largest disaster, so it is the one most worth
        exercising: a series quoting USD per UAH would strike every base at the reciprocal of
        the published rate and leave every figure plausible."""
        root = _shipped_root(tmp_path)
        shipped = root / "official_rates" / "ua_nbu_usd.toml"
        shipped.write_text(
            shipped.read_text(encoding="utf-8").replace(
                'pair           = ["UAH", "USD"]', 'pair           = ["USD", "UAH"]'
            ),
            encoding="utf-8",
        )

        with pytest.raises(DeclarationError) as caught:
            resolver.tax_rules_from_data_root(root, resolver.from_data_root(root))

        assert "reciprocal" in str(caught.value)
        assert "ua_nbu_usd" in str(caught.value)

    def test_a_rule_naming_an_undeclared_staleness_kind_is_refused(self, tmp_path: Path) -> None:
        """A rule table's kind is checked by the resolver, because nothing else can.

        Why nothing else can is `resolver.official_rates_from_data_root`'s docstring; this
        asserts that the check exists and names both the offending kind and the alternatives.
        """
        root = tmp_path / "data" / "official_rates"
        root.mkdir(parents=True)
        rule = RULE.format(applies_to="2026-03-04", governed_by="2026-03-03")
        _file(root, _body() + rule.replace('kind         = "tax_rule"', 'kind = "not_a_kind"'))

        with pytest.raises(DeclarationError) as caught:
            resolver.official_rates_from_data_root(
                tmp_path / "data", {"tax_rule": _A_DECLARED_KIND}
            )

        assert "not_a_kind" in str(caught.value)
        assert "tax_rule" in str(caught.value)

    def test_an_absent_directory_is_an_empty_set_rather_than_a_load_failure(
        self, tmp_path: Path
    ) -> None:
        """A run that never strikes a foreign base needs none, and the refusal that does need
        one names the pair and the date -- which is more use than an error naming a directory."""
        assert resolver.official_rates_from_data_root(tmp_path, {}).series == {}


class TestTheShippedUkrainianSeries:
    """A battery of broken files proves nothing about the file the project uses."""

    def test_it_loads_and_declares_its_identity(self) -> None:
        series = loader.official_rate_from_file(SHIPPED)

        assert series.id == "ua_nbu_usd"
        assert series.pair == (Currency.UAH, Currency.USD)
        assert series.quotation_unit == 1.0

    def test_it_declares_no_non_publication_day_rule(self) -> None:
        """FR-017, and it is not an oversight: пункт 10 розділу III is written in working days
        and pre-holiday days, so declaring it needs a declared, cited working-day and holiday
        calendar -- a feature (``declared-working-day-calendar``), not a data entry (FR-018)."""
        assert loader.official_rate_from_file(SHIPPED).rule is None

    def test_a_base_struck_against_it_refuses_naming_the_series_the_pair_and_the_date(
        self,
    ) -> None:
        """SC-014: the missing rule is something a run reports, not something a spec says.

        **What ships is stronger than FR-017's sentence and demonstrates less of it.** FR-017
        says "every date the National Bank does not publish for refuses"; this series declares
        no observation at all yet, because no rate value may originate from an implementer's
        memory and retrieval is the fetch script's job (FR-001, plan research D6). So *every*
        date refuses, and the refusal says the window is empty rather than naming a hole in a
        published run. The published-window case is exercised against synthetic series in
        ``tests/unit/test_official_rate_refusals.py``.
        """
        outcome = official_rate.strike_base(
            Money(1_000.0, Currency.USD, prov.EMPTY),
            loader.official_rate_from_file(SHIPPED),
            tax_currency=Currency.UAH,
            on_date=date(2026, 3, 8),
        )

        assert isinstance(outcome, official_rate.OfficialRateUndeclaredOnDate), outcome
        assert outcome.series_id == "ua_nbu_usd"
        assert outcome.pair == (Currency.UAH, Currency.USD)
        assert outcome.on_date == date(2026, 3, 8)
        assert outcome.covers is None
