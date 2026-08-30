"""The rate you are taxed at is not the rate you sold at, asserted as a standing property.

Story 2, SC-007, SC-008 and SC-009. Constitution Principle VI names three currency roles --
base, tax and display -- and says conflating any two is a defect. This module is where that
claim stops being prose.

**The prohibition is bidirectional and its two halves are two requirements.** FR-012 says the
amount *received* is never computed from an official rate; FR-013 says a channel's
``reference_rate`` never serves as a tax rate. They are not the same sentence read twice, and
a single check covering "both" would be one requirement short: it would stay green with either
half deleted. So each has its own ``.importlinter`` contract, whose names
``tests/contract/test_architecture_boundaries.py`` pins, and each has its own assertion here.

**Why a source scan as well as the import contracts.** An import contract answers *can this
module reach that one*; it cannot answer *is any tax figure derived from a reference rate*
once the two live in one call site.

The scan reads executable source with prose stripped (``tests/source_scan.py``) rather than
grepping, because a docstring naming the forbidden thing **in the course of forbidding it**
is not a violation of it -- and this feature's own module is exactly that case. That is not
asserted here in prose: ``test_the_official_rate_modules_prose_names_it_and_the_scan_still_passes``
below proves both halves against the file itself, so a naive grep replacing the scan fails.
"""

from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path

import pytest

from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.routes import channels, legs
from terezy.core.tax import official_rate
from tests import composed_registries, official_rates
from tests.source_scan import executable_source

pytestmark = pytest.mark.contract

SRC = Path(__file__).resolve().parents[2] / "src" / "terezy"
CORE_TAX = SRC / "core" / "tax"
CORE_ROUTES = SRC / "core" / "routes"

EARNED_ON = date(2026, 3, 2)

OFFICIAL_ON_EARNED_DAY = 41.0
"""Invented, and deliberately nowhere near the channel's reference of 42."""


class TestTwoFiguresComeOutOfOneDollarAmount:
    """SC-007: what the law says the income was, and what the owner actually has."""

    def test_the_two_are_separately_computed_and_are_not_equal_by_construction(self) -> None:
        earned = Money(1_000.0, Currency.USD, prov.EMPTY)

        # What the owner actually has: the channel that did the converting, on its own date.
        channel = composed_registries.channel()
        side, role = channels.side_for(channel, Currency.USD, Currency.UAH)
        realised = money.convert(
            earned,
            to_currency=Currency.UAH,
            rate=channels.effective_rate(side, channel.reference_rate, role=role),
            sources=channel.provenance,
        )

        # What the law says the income was: the official rate for the date it was earned.
        struck = official_rate.strike_base(
            earned,
            official_rates.series([(EARNED_ON, OFFICIAL_ON_EARNED_DAY)]),
            tax_currency=Currency.UAH,
            on_date=EARNED_ON,
        )
        assert isinstance(struck, official_rate.TaxCurrencyConversion), struck

        # 1000 x 39.5 sold through the P2P sell side; 1000 x 41.00 struck for tax.
        assert is_close(realised.amount, 39_500.0)
        assert is_close(struck.base.amount, 41_000.0)
        assert realised.amount != struck.base.amount

    def test_each_figure_names_the_rate_it_came_from_and_neither_names_the_other(self) -> None:
        """A reader must be able to tell which is which without knowing the arithmetic."""
        struck = official_rate.strike_base(
            Money(1_000.0, Currency.USD, prov.EMPTY),
            official_rates.series([(EARNED_ON, OFFICIAL_ON_EARNED_DAY)]),
            tax_currency=Currency.UAH,
            on_date=EARNED_ON,
        )
        assert isinstance(struck, official_rate.TaxCurrencyConversion), struck

        assert struck.series_id == "synthetic_official_usd"
        assert struck.rate_date == EARNED_ON
        assert not hasattr(struck, "channel_id")
        assert not hasattr(struck, "reference_rate")


class TestNoCostFigureIsDerivedFromAnOfficialRate:
    """FR-012, over the whole of ``core.routes`` rather than one call site."""

    def test_no_routing_module_names_the_official_rate_machinery(self) -> None:
        for path in sorted(CORE_ROUTES.rglob("*.py")):
            behaviour = executable_source(path)
            assert "official_rate" not in behaviour, path
            assert "strike_base" not in behaviour, path

    def test_a_leg_naming_an_unknown_channel_has_no_rate_to_fall_back_on(self) -> None:
        """The refusal feature 002 wrote, still standing and still the only answer.

        This is the half a source scan cannot make: the scan says ``core.routes`` never
        *reaches* the official rate, and this says there is no rate at the one place a
        substitution would be reached for. A later feature adding the "reference rate"
        option FR-012 forbids would make the refusal stop happening, and it is the ``raises``
        that fails then -- the two string assertions never run at all.
        """
        with pytest.raises(KeyError) as caught:
            legs.channel_for(
                composed_registries.CHANNELS,
                composed_registries.leg(
                    index=0,
                    from_venue="a",
                    to_venue="b",
                    from_ccy=Currency.UAH,
                    to_ccy=Currency.USD,
                    channel_id="misspelt",
                ),
            )

        assert "no default channel" in str(caught.value)
        assert "official_rate" not in str(caught.value)


class TestNoTaxBaseIsDerivedFromAChannelRate:
    """FR-013, and the converse of the class above rather than a restatement of it."""

    def test_no_tax_module_names_a_channel_or_its_reference_rate(self) -> None:
        for path in sorted(CORE_TAX.rglob("*.py")):
            behaviour = executable_source(path)
            for forbidden in (
                "reference_rate",
                "FxChannel",
                "effective_rate",
                "side_for",
                "channel_for",
            ):
                assert forbidden not in behaviour, (path, forbidden)

    def test_the_official_rate_modules_prose_names_it_and_the_scan_still_passes(self) -> None:
        """The scan strips prose, and this is what proves it does: the module docstring says
        ``reference_rate`` in the course of forbidding it, and a naive grep would fail."""
        source = (CORE_TAX / "official_rate.py").read_text(encoding="utf-8")

        assert "reference_rate" in source
        assert "reference_rate" not in executable_source(CORE_TAX / "official_rate.py")


class TestNoDisplayChoiceCanReachATaxFigure:
    """SC-009, in the only form that is honest: there is no display switch to exercise.

    The specification says so itself -- required test F2 stays open because the switch does
    not exist -- so a test that "switched the display currency" would have to invent the
    switch, and would pass for the reason it invented rather than for the requirement.

    What can be asserted, and is: **no display choice exists anywhere in the tax path**, so
    there is nothing for a tax base to depend on. When the switch is built, this is the test
    it has to keep green, and the assertion below is what tells its author where to look.
    Measured over ``src/terezy/core/tax`` on 2026-08-29.

    ⚙ **It matches on the word, so it is only as good as the name.** A presentation choice
    called ``render_currency`` or ``shown_in`` would pass this scan. That is the honest limit
    of asserting an absence: the check is that nothing here reads *the thing this project
    calls a display currency*, and whoever names the switch owns keeping it findable.
    """

    def test_no_tax_module_reads_a_display_currency(self) -> None:
        for path in sorted(CORE_TAX.rglob("*.py")):
            assert "display" not in executable_source(path).lower(), path

    def test_the_struck_base_takes_its_currency_from_the_jurisdictions_declaration(
        self,
    ) -> None:
        """The only ``Currency`` inputs are the amount's own and the declared tax currency:
        there is no third argument a presentation choice could arrive through."""
        struck = official_rate.strike_base(
            Money(1_000.0, Currency.USD, prov.EMPTY),
            official_rates.series([(EARNED_ON, OFFICIAL_ON_EARNED_DAY)]),
            tax_currency=Currency.UAH,
            on_date=EARNED_ON,
        )
        assert isinstance(struck, official_rate.TaxCurrencyConversion), struck
        assert struck.base.currency is Currency.UAH


class TestARealOfficialRateIsNotARepairForAnInventedChannelQuote:
    """018 SC-010: the substitution this repository now actually contains the makings of.

    ``data/official_rates/ua_nbu_usd.toml`` carries real published figures for every calendar
    day, and one directory away ``data/channels/uah_usd.toml`` declares three channels whose
    ``reference_rate`` is invented and says so on every line. Pointing the second at the first
    is the cheapest-looking repair in the tree and is the conflation the classes above forbid,
    arriving as a tidy-up. What stops it is this, asserted over the shipped files.
    """

    CHANNELS = Path(__file__).resolve().parents[2] / "data" / "channels" / "uah_usd.toml"
    RATES = Path(__file__).resolve().parents[2] / "data" / "official_rates" / "ua_nbu_usd.toml"

    def _channels(self) -> list[dict[str, object]]:
        declared = tomllib.loads(self.CHANNELS.read_text(encoding="utf-8"))
        found = declared["channel"]
        assert isinstance(found, list), self.CHANNELS
        assert found, self.CHANNELS
        return found

    def test_every_declared_reference_rate_is_still_the_invented_one(self) -> None:
        for channel in self._channels():
            assert channel["reference_rate"] == 42.0, channel["id"]

    def test_every_declared_reference_rate_is_still_marked_synthetic_and_unverified(
        self,
    ) -> None:
        """A real rate that arrived here would have to lose the marking to look right, so the
        marking is the thing to hold: it is what a reader sees on every figure downstream."""
        for channel in self._channels():
            assert "SYNTHETIC" in str(channel["source"]), channel["id"]
            assert channel["verified_on"] == "", channel["id"]

    def test_no_channel_quote_is_sourced_to_the_tax_series(self) -> None:
        """The substitution's other shape: the same number, re-sourced.

        Scoped to the **series and the statistics endpoint it is fetched from**, not to the
        National Bank generally. ``FxChannel.id`` names ``nbu_official`` among the channels a
        declarer may legitimately declare, and such a channel would carry its own two-sided
        quote with its own citation. What is forbidden is a channel quote that takes its
        number from the legal reference nobody transacts at.
        """
        for channel in self._channels():
            source = str(channel["source"])
            assert "ua_nbu_usd" not in source, channel["id"]
            assert "NBU_Exchange/exchange_site" not in source, channel["id"]

    def test_the_invented_reference_is_not_a_value_the_publisher_ever_published(self) -> None:
        """So the fixture cannot be mistaken for a retrieved figure on any date. Checked
        against the landed series rather than asserted, because that is what would change."""
        declared = tomllib.loads(self.RATES.read_text(encoding="utf-8"))
        published = {observation["value"] for observation in declared["observation"]}

        assert published, "this claim is about a populated series"
        assert 42.0 not in published
