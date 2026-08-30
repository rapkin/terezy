"""SC-007 and SC-008: where the legal values live, and that their marks reach every figure.

Two claims, and the first is what makes the second worth having.

**No tax rate this feature consumes lives in per-owner data.** The retired
``income_tax_rate_pct`` let a public legal fact about the Republic be written into a file
whose citation exemption is argued for the owner's statements about himself, uncited, where
no gate would look at it. Every rate is in ``data/tax/schemes/`` now, where the provenance
gate reads it and a missing citation is a load failure.

**Exactly one shipped value is sourced to the owner rather than to a public text** — the ЄСВ
nil — and it says so on its face, so it is never read as a curated legal fact.

**The mark propagates, in both directions.** An unverified rate marks a charge struck from a
verified official rate, and an unverified official rate marks a charge computed at a verified
rate. Both directions are checked, because a merge that dropped either would still pass one
of them.
"""

from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.tax import scheme as schemes
from terezy.core.tax.scheme import PeriodicComponent, RateComponent, TaxationScheme
from terezy.data.declarations import resolver
from tests import official_rates
from tests import schemes as fixtures

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
STREAM_FILE = DATA_ROOT / "streams" / "owner-001.toml"

CREDIT_DATE = date(2027, 3, 15)
VERIFIED_ON = date(2026, 8, 30)
DOLLARS = Money(1_000.00, Currency.USD, prov.EMPTY)
SCHEDULE_START = date(2025, 1, 1)


def _declared() -> resolver.SchemeDeclarations:
    return resolver.schemes_from_data_root(DATA_ROOT, base_currency=Currency.UAH)


def _components(scheme: TaxationScheme) -> list[RateComponent | PeriodicComponent]:
    """Both kinds in one list, typed as their union so a shared field can be read."""
    components: list[RateComponent | PeriodicComponent] = list(scheme.rate_components)
    components.extend(scheme.periodic_components)
    return components


def _charged(*, rate_verified: date | None, series_verified: date | None) -> schemes.SchemeCharge:
    scheme = fixtures.scheme(
        rate_components=[
            fixtures.rate_component(
                [(SCHEDULE_START, 0.05)], component_id="one", verified_on=rate_verified
            )
        ]
    )
    charge = schemes.charge_income(
        scheme,
        DOLLARS,
        on_date=CREDIT_DATE,
        series=official_rates.series([(CREDIT_DATE, 42.00)], verified_on=series_verified),
    )
    assert isinstance(charge, schemes.SchemeCharge), charge
    return charge


class TestNoLegalRateIsLeftInPerOwnerData:
    def test_the_stream_file_declares_no_rate_and_no_percentage_at_all(self) -> None:
        """Read as TOML rather than as text: a key in a comment is not a key."""
        declared = tomllib.loads(STREAM_FILE.read_text(encoding="utf-8"))
        for stream in declared["stream"]:
            assert "income_tax_rate_pct" not in stream
            numeric = {
                key
                for key, value in stream.items()
                if isinstance(value, int | float) and not isinstance(value, bool)
            }
            assert numeric == {"amount"}, stream["id"]

    def test_what_it_declares_instead_is_a_name_that_resolves_to_a_cited_scheme(self) -> None:
        declared = _declared()
        contract = declared.ramp.streams["contract_usd"]
        assert contract.tax_scheme is not None
        scheme = declared.schemes[contract.tax_scheme]
        for component in scheme.rate_components:
            for entry in component.schedule:
                assert entry.provenance.sources, component.id

    def test_every_rate_the_shipped_schemes_carry_names_a_source_and_a_retrieval_date(
        self,
    ) -> None:
        for scheme in _declared().schemes.values():
            for component in _components(scheme):
                for entry in component.schedule:
                    for ref in entry.provenance.sources:
                        assert ref.citation.strip(), (scheme.id, component.id)
                        assert ref.retrieved_on is not None
                        assert ref.kind == "tax_rule"


class TestExactlyOneValueIsSourcedToTheOwner:
    """SC-007's second half: identifiable as such wherever it appears."""

    @staticmethod
    def _owner_sourced() -> list[tuple[str, str]]:
        found = []
        for scheme in _declared().schemes.values():
            for component in _components(scheme):
                for entry in component.schedule:
                    for ref in entry.provenance.sources:
                        if "The owner, stating his own tax position" in ref.citation:
                            found.append((scheme.id, component.id))
        return found

    def test_there_is_exactly_one_and_it_is_the_esv_nil(self) -> None:
        assert self._owner_sourced() == [("ua_fop_group_3_non_vat", "esv")]

    def test_it_is_unverified_so_every_figure_resting_on_it_renders_marked(self) -> None:
        scheme = _declared().schemes["ua_fop_group_3_non_vat"]
        charged = schemes.charge_period(
            scheme,
            next(item for item in scheme.periodic_components if item.id == "esv"),
            "2026-09",
        )
        assert isinstance(charged, schemes.PeriodicCharge), charged
        assert charged.charged.amount == 0.0
        assert prov.is_unverified(charged.charged.provenance)

    def test_the_zero_carries_its_citation_exactly_as_a_non_zero_value_would(self) -> None:
        """An uncited zero is the figure that gets believed without checking."""
        scheme = _declared().schemes["ua_fop_group_3_non_vat"]
        standing = schemes.component_standing(scheme, "esv", period="2026-09")
        assert isinstance(standing, schemes.ComponentAmount), standing
        assert standing.amount.provenance.sources


class TestTheMarkReachesEveryFigureInBothDirections:
    def test_an_unverified_rate_marks_a_charge_struck_from_a_verified_official_rate(
        self,
    ) -> None:
        charge = _charged(rate_verified=None, series_verified=VERIFIED_ON)
        assert prov.is_unverified(charge.total.provenance)
        assert prov.is_unverified(charge.lines[0].charged.provenance)

    def test_an_unverified_official_rate_marks_a_charge_computed_at_a_verified_rate(
        self,
    ) -> None:
        charge = _charged(rate_verified=VERIFIED_ON, series_verified=None)
        assert prov.is_unverified(charge.base.provenance)
        assert prov.is_unverified(charge.total.provenance)

    def test_two_verified_inputs_leave_the_figure_unmarked(self) -> None:
        """Without this the propagation checks would pass by marking everything for ever."""
        charge = _charged(rate_verified=VERIFIED_ON, series_verified=VERIFIED_ON)
        assert not prov.is_unverified(charge.total.provenance)
        assert charge.total.provenance.sources

    def test_every_shipped_figure_is_marked_because_every_shipped_value_is_unverified(
        self,
    ) -> None:
        declared = _declared()
        charge = schemes.charge_income(
            declared.schemes["ua_fop_group_3_non_vat"],
            DOLLARS,
            on_date=CREDIT_DATE,
            series=official_rates.series([(CREDIT_DATE, 42.00)], verified_on=VERIFIED_ON),
        )
        assert isinstance(charge, schemes.SchemeCharge), charge
        assert prov.is_unverified(charge.total.provenance)
        for line in charge.lines:
            assert prov.is_unverified(line.charged.provenance), line.component_id

    def test_a_scheme_that_charges_no_rate_still_marks_its_zero_total(self) -> None:
        """A sum of nothing rests on nothing, and that zero sat beside a base that was marked.

        A scheme declaring only periodic components is legal -- the loader requires one
        component of *either* kind -- so its income charge has no rate line at all. The total
        is then a zero, and an uncited zero is the figure that gets believed without checking.
        """
        scheme = fixtures.scheme(
            scheme_id="synthetic_periodic_only",
            periodic_components=[fixtures.periodic_component([(SCHEDULE_START, 100.0)])],
        )
        charge = schemes.charge_income(
            scheme,
            DOLLARS,
            on_date=CREDIT_DATE,
            series=official_rates.series([(CREDIT_DATE, 42.00)]),
        )
        assert isinstance(charge, schemes.SchemeCharge), charge
        assert charge.lines == ()
        assert charge.total.amount == 0.0
        assert charge.total.provenance.sources
        assert charge.total.provenance.sources == charge.base.provenance.sources
        assert prov.is_unverified(charge.total.provenance)

    def test_the_rows_own_citation_reaches_the_figure_it_selected(self) -> None:
        """A row and a reading decide WHICH rates strike a figure without multiplying it, so
        their marks reach the money only if they are put there."""
        declared = _declared()
        outcome = schemes.apply(
            scheme_id="ua_fop_group_3_non_vat",
            credited_to="fop",
            amount=DOLLARS,
            on_dates={"credited": CREDIT_DATE},
            schemes=declared.schemes,
            destinations=declared.destinations,
            series=official_rates.series([(CREDIT_DATE, 42.00)], verified_on=VERIFIED_ON),
        )
        assert isinstance(outcome, schemes.ChargedUnderTheScheme), outcome
        row = declared.destinations[("ua_fop_group_3_non_vat", "fop")]
        assert row.provenance.sources <= outcome.charge.total.provenance.sources
        assert row.provenance.sources <= outcome.charge.base.provenance.sources
