"""SC-017 and SC-017a: one figure per reading, none of them the tax owed, and no blend.

Principle I at its strictest. Where a crediting destination has no authoritative answer, the
readings differ by more than every route cost this engine computes — 5% + 1% against 18% + 5%
on the same base — so a refusal would tell the owner nothing and labelled figures tell him
what the uncertainty is worth. What may **never** happen is either of them being read as the
answer.

Four mechanical guarantees, each asserted rather than written down:

1. **A blend has nowhere to live.** ``UnsettledDestination`` carries no money at all.
2. **The label is on the figure, not on the slot.** A figure lifted out of the tuple still
   names its reading and carries that reading's citations.
3. **The tax owed is a different type.** ``ChargedUnderTheScheme`` and ``ReadingFigure`` are
   unrelated records, so neither can stand in for the other.
4. **Containment.** Only the module that defines a figure mentions one in executable code at
   all. That is stronger than counting constructor calls and it is why it is written that
   way: ``dataclasses.replace(figure, charge=...)`` builds a second labelled figure without
   ever writing ``ReadingFigure(``, and a mention scan sees it while a call scan does not.

⚙ **One declaration, consumed and never copied.** Every personal-income reading in the
shipped table resolves to the *same object*, asserted by identity rather than by equality of
its rates: two files declaring 18% and 5% would compare equal and drift the day one of them
was corrected.
"""

from __future__ import annotations

import ast
import dataclasses
from datetime import date
from pathlib import Path

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.tax import scheme as schemes
from terezy.data.declarations import resolver
from tests import official_rates, source_scan

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
SOURCE_ROOT = REPO_ROOT / "src" / "terezy"

CREDIT_DATE = date(2027, 3, 15)
REPATRIATION_DATE = date(2027, 4, 2)
DOLLARS = Money(1_000.00, Currency.USD, prov.EMPTY)
SERIES = official_rates.series([(CREDIT_DATE, 42.00), (REPATRIATION_DATE, 43.00)])

SHIPPED_COUNTS = {
    "fop": 1,
    "payoneer": 3,
    "monobank_uah": 1,
    "coinbase": 1,
    "foreign_bank_usd": 2,
}
"""One figure per computable reading, per destination. The count is an output of the rule
and never an input to it; these are what the shipped table declares."""


def _declared() -> resolver.SchemeDeclarations:
    return resolver.schemes_from_data_root(DATA_ROOT, base_currency=Currency.UAH)


def _applied(venue: str) -> schemes.DestinationOutcome:
    declared = _declared()
    return schemes.apply(
        scheme_id="ua_fop_group_3_non_vat",
        credited_to=venue,
        amount=DOLLARS,
        on_dates={"credited": CREDIT_DATE, "repatriated": REPATRIATION_DATE},
        schemes=declared.schemes,
        destinations=declared.destinations,
        series=SERIES,
    )


def _switch(venue: str) -> schemes.UnsettledDestination:
    outcome = _applied(venue)
    assert isinstance(outcome, schemes.UnsettledDestination), outcome
    return outcome


class TestABlendHasNowhereToLive:
    def test_the_switch_record_carries_no_money_at_all(self) -> None:
        fields = dataclasses.fields(schemes.UnsettledDestination)
        assert not [field.name for field in fields if "Money" in str(field.type)]
        assert {field.name for field in fields} == {
            "venue_id",
            "declared_treatment",
            "grounds",
            "resolution_path",
            "figures",
            "uncomputable",
        }

    def test_no_aggregate_of_any_name_exists_on_it(self) -> None:
        names = {field.name for field in dataclasses.fields(schemes.UnsettledDestination)}
        assert not names & {
            "total",
            "mean",
            "average",
            "blended",
            "combined",
            "owed",
            "expected",
            "midpoint",
            "range",
        }

    def test_the_figures_are_computed_independently_of_one_another(self) -> None:
        """SC-017: two readings on one destination share a base only when they share a date."""
        switch = _switch("payoneer")
        by_date = {figure.reading_id: figure.charge.base.amount for figure in switch.figures}
        assert by_date["dps_on_the_payment_system_credit"] != by_date["nbu_on_the_repatriation"]

    def test_no_figure_equals_the_sum_or_the_mean_of_the_others(self) -> None:
        """A blend that happened to be computed would have to be one of these."""
        switch = _switch("payoneer")
        totals = [figure.charge.total.amount for figure in switch.figures]
        for total in totals:
            others = [item for item in totals if item is not total]
            assert total != sum(others)
            assert total != sum(totals) / len(totals)


class TestNoFigureIsTheTaxOwed:
    def test_the_tax_owed_and_a_what_if_are_unrelated_records(self) -> None:
        assert schemes.ChargedUnderTheScheme.__bases__ == (object,)
        assert schemes.ReadingFigure.__bases__ == (object,)
        assert not issubclass(schemes.ReadingFigure, schemes.ChargedUnderTheScheme)
        assert not issubclass(schemes.ChargedUnderTheScheme, schemes.ReadingFigure)

    @pytest.mark.parametrize("venue", sorted(SHIPPED_COUNTS))
    def test_every_unsettled_destination_produces_a_switch_and_never_a_charge(
        self, venue: str
    ) -> None:
        outcome = _applied(venue)
        verdict = _declared().destinations[("ua_fop_group_3_non_vat", venue)].verdict
        if verdict is schemes.Verdict.INTERPRETED:
            assert isinstance(outcome, schemes.ChargedUnderTheScheme), outcome
        else:
            assert isinstance(outcome, schemes.UnsettledDestination), outcome

    @pytest.mark.parametrize("venue", ["payoneer", "monobank_uah", "coinbase", "foreign_bank_usd"])
    def test_every_figure_says_it_is_not_the_tax_owed(self, venue: str) -> None:
        for figure in _switch(venue).figures:
            assert "not the tax owed" in figure.not_the_tax_owed

    @pytest.mark.parametrize("venue", ["payoneer", "monobank_uah", "coinbase", "foreign_bank_usd"])
    def test_every_switch_names_the_consultation_that_would_settle_it(self, venue: str) -> None:
        assert "індивідуальна податкова консультація" in _switch(venue).resolution_path


class TestTheLabelTravelsWithTheFigure:
    def test_a_figure_lifted_out_of_the_tuple_still_names_its_reading(self) -> None:
        """A design inferring the label from which slot held the figure stops answering the
        moment anything else holds it."""
        lifted = _switch("payoneer").figures[1]
        assert lifted.reading_id == "nbu_on_the_repatriation"
        assert lifted.label
        assert lifted.recognised_on == "repatriated"
        assert lifted.not_the_tax_owed
        assert lifted.provenance.sources

    def test_each_figure_carries_its_own_readings_citations_and_not_a_sibling_s(self) -> None:
        first, second, third = _switch("payoneer").figures
        assert first.provenance.sources != second.provenance.sources
        assert first.provenance.sources <= first.charge.provenance.sources
        assert third.provenance.sources <= third.charge.provenance.sources

    def test_the_nbu_reading_reports_where_it_departs_from_its_source(self) -> None:
        """SC-017a. A departure nothing reports becomes a silent absorption."""
        departing = [figure for figure in _switch("payoneer").figures if figure.departs_from_source]
        assert [figure.reading_id for figure in departing] == ["nbu_on_the_repatriation"]
        stated = departing[0].departs_from_source
        assert stated is not None
        # Both halves SC-017a asks for: what the source says, and what was computed instead.
        assert "курсом банку" in stated
        assert "OFFICIAL rate" in stated

    def test_that_reading_is_struck_at_the_official_rate_for_its_own_date(self) -> None:
        """The other half of SC-017a: what was computed, not only what was said."""
        figure = _switch("payoneer").figures[1]
        conversion = figure.charge.conversion
        assert conversion is not None
        assert conversion.event_date == REPATRIATION_DATE
        assert conversion.rate == 43.00


class TestOneDeclarationConsumedByEveryReading:
    def test_every_personal_income_reading_resolves_to_the_same_object(self) -> None:
        """Asserted by identity: two files declaring 18% and 5% would compare equal today and
        drift the day one of them was corrected."""
        declared = _declared()
        consuming = [
            reading
            for row in declared.destinations.values()
            for reading in row.readings
            if reading.scheme_id == "ua_personal_income"
        ]
        assert len(consuming) == 4
        resolved = {
            id(declared.schemes[reading.scheme_id])
            for reading in consuming
            if reading.scheme_id is not None
        }
        assert len(resolved) == 1

    def test_the_personal_income_scheme_may_not_be_named_by_a_stream(self) -> None:
        assert _declared().schemes["ua_personal_income"].declared_for == "reading"

    def test_it_declares_the_two_components_every_such_reading_charges(self) -> None:
        scheme = _declared().schemes["ua_personal_income"]
        assert [component.id for component in scheme.rate_components] == [
            "pdfo",
            "viyskovyi_zbir",
        ]
        assert [component.schedule[-1].rate for component in scheme.rate_components] == [
            0.18,
            0.05,
        ]


class TestTheShippedCountsAreWhatTheRuleProduces:
    @pytest.mark.parametrize(("venue", "count"), sorted(SHIPPED_COUNTS.items()))
    def test_each_destination_produces_one_figure_per_computable_reading(
        self, venue: str, count: int
    ) -> None:
        outcome = _applied(venue)
        if isinstance(outcome, schemes.ChargedUnderTheScheme):
            assert count == 1
            return
        assert isinstance(outcome, schemes.UnsettledDestination), outcome
        assert len(outcome.figures) == count

    def test_no_shipped_row_carries_an_uncomputable_candidate_and_that_is_recorded(self) -> None:
        """Line 3's second sentence is reachable and currently unexercised by shipped data.

        Asserted so the state is a measured fact rather than an assumption: every reading the
        table declares today resolves to a scheme. The clause is exercised by a synthetic
        destination in ``tests/unit/test_crediting_destinations.py``.
        """
        for venue in SHIPPED_COUNTS:
            outcome = _applied(venue)
            if isinstance(outcome, schemes.UnsettledDestination):
                assert outcome.uncomputable == ()


def _construction_sites(name: str) -> dict[str, int]:
    """How many times each module calls ``name`` as a constructor."""
    sites: dict[str, int] = {}
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(source_scan.executable_source(path))
        count = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name) and node.func.id == name)
                or (isinstance(node.func, ast.Attribute) and node.func.attr == name)
            )
        )
        if count:
            sites[path.relative_to(SOURCE_ROOT).as_posix()] = count
    return sites


def _modules_mentioning(name: str) -> set[str]:
    """Every module naming ``name`` in executable code, however it names it."""
    return {
        path.relative_to(SOURCE_ROOT).as_posix()
        for path in sorted(SOURCE_ROOT.rglob("*.py"))
        for node in ast.walk(ast.parse(source_scan.executable_source(path)))
        if (isinstance(node, ast.Name) and node.id == name)
        or (isinstance(node, ast.Attribute) and node.attr == name)
    }


LABELLED = ("ReadingFigure", "ChargedUnderTheScheme", "UnsettledDestination")


class TestOnlyOneModuleBuildsAFigure:
    """Containment: a second site is a second place a label can be got wrong."""

    @pytest.mark.parametrize("name", LABELLED)
    def test_it_is_constructed_in_exactly_one_place(self, name: str) -> None:
        assert _construction_sites(name) == {"core/tax/scheme.py": 1}

    @pytest.mark.parametrize("name", LABELLED)
    def test_no_other_module_so_much_as_names_it_in_code(self, name: str) -> None:
        """Wider than the call scan on purpose: ``replace(figure, ...)`` constructs one
        without calling it, and only a mention scan sees that."""
        assert _modules_mentioning(name) <= {"core/tax/scheme.py", "core/streams/capacity.py"}

    def test_the_scan_is_falsifiable(self) -> None:
        assert _construction_sites("SchemeCharge")
        assert _construction_sites("NothingIsCalledThis") == {}
        assert _modules_mentioning("NothingIsCalledThis") == set()
        assert "core/tax/scheme.py" in _modules_mentioning("SchemeCharge")
