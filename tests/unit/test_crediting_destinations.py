"""Where the income is credited, and what each verdict produces.

FR-025 to FR-027. One destination is answered a checkable inference deep and produces a
**charge**; four have no authoritative answer and produce a **labelled switch**; a
destination the declared table has no row for **refuses**.

The values here are synthetic. What is under test is the machinery the spec asks a planner
to build *for the verdicts moving* -- a verdict is a declared word, a reading is a declared
row, and every reading computes from a declared scheme.
"""

from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.tax import scheme as schemes
from tests import official_rates
from tests import schemes as fixtures

CREDIT_DATE = date(2027, 3, 15)
REPATRIATION_DATE = date(2027, 4, 2)
RATE_ON_CREDIT = 42.00
RATE_ON_REPATRIATION = 43.00
DOLLARS = Money(1_000.00, Currency.USD, prov.EMPTY)
DATES = {fixtures.CREDITED: CREDIT_DATE, fixtures.REPATRIATED: REPATRIATION_DATE}
FROM = date(2025, 1, 1)

SCHEME = fixtures.scheme(
    rate_components=[fixtures.rate_component([(FROM, 0.06)], component_id="one_rate")]
)
OTHER_SCHEME = fixtures.scheme(
    scheme_id="synthetic_other_scheme",
    declared_for="reading",
    rate_components=[fixtures.rate_component([(FROM, 0.23)], component_id="other_rate")],
)
ROW_SCHEME = fixtures.scheme(
    scheme_id="synthetic_row_scheme",
    rate_components=[fixtures.rate_component([(FROM, 0.11)], component_id="row_rate")],
)
"""A third scheme, so the **row's** scheme is a different string from the reading's.

Three identities meet at `apply`: the treatment asked about, the row's, and the reading's.
While the fixtures defaulted all three to one id, an engine charging every reading under its
row's scheme -- 5%+1% where the law says 18%+5% -- passed the whole suite.
"""

REGISTRY = {
    SCHEME.id: SCHEME,
    OTHER_SCHEME.id: OTHER_SCHEME,
    ROW_SCHEME.id: ROW_SCHEME,
}
SERIES = official_rates.series(
    [(CREDIT_DATE, RATE_ON_CREDIT), (REPATRIATION_DATE, RATE_ON_REPATRIATION)]
)


def _applied(
    destination: schemes.CreditingDestination | None,
    *,
    venue_id: str = "synthetic_venue",
    on_dates: dict[str, date] | None = None,
) -> object:
    table: dict[tuple[str, str], schemes.CreditingDestination] = (
        {} if destination is None else {(destination.scheme_id, destination.venue_id): destination}
    )
    return schemes.apply(
        scheme_id=SCHEME.id,
        credited_to=venue_id,
        amount=DOLLARS,
        on_dates=DATES if on_dates is None else on_dates,
        schemes=REGISTRY,
        destinations=table,
        series=SERIES,
    )


class TestAReadingIsChargedUnderTheSchemeItNames:
    """The three identities that meet at ``apply``, told apart by using three ids."""

    def test_the_charging_scheme_is_the_readings_and_not_the_rows(self) -> None:
        outcome = schemes.apply(
            scheme_id=SCHEME.id,
            credited_to="synthetic_venue",
            amount=DOLLARS,
            on_dates=DATES,
            schemes=REGISTRY,
            destinations={
                (SCHEME.id, "synthetic_venue"): fixtures.destination(
                    [fixtures.reading(scheme_id=OTHER_SCHEME.id)], scheme_id=SCHEME.id
                )
            },
            series=SERIES,
        )
        assert isinstance(outcome, schemes.UnsettledDestination), outcome
        figure = outcome.figures[0]
        assert figure.scheme_id == OTHER_SCHEME.id
        assert figure.charge.scheme_id == OTHER_SCHEME.id
        assert [line.component_id for line in figure.charge.lines] == ["other_rate"]
        assert figure.charge.lines[0].rate == 0.23

    def test_the_row_it_sits_in_may_name_a_third_scheme_and_still_charge_the_readings(
        self,
    ) -> None:
        outcome = schemes.apply(
            scheme_id=ROW_SCHEME.id,
            credited_to="synthetic_venue",
            amount=DOLLARS,
            on_dates=DATES,
            schemes=REGISTRY,
            destinations={
                (ROW_SCHEME.id, "synthetic_venue"): fixtures.destination(
                    [fixtures.reading(scheme_id=SCHEME.id)], scheme_id=ROW_SCHEME.id
                )
            },
            series=SERIES,
        )
        assert isinstance(outcome, schemes.UnsettledDestination), outcome
        assert outcome.declared_treatment == ROW_SCHEME.id
        assert outcome.figures[0].charge.scheme_id == SCHEME.id
        assert outcome.figures[0].charge.lines[0].rate == 0.06


class TestAnInterpretedDestinationProducesACharge:
    """FR-025. A charge, with the row's recorded judgement and its citations on it."""

    def test_it_is_charged_under_the_scheme_the_reading_names(self) -> None:
        outcome = _applied(
            fixtures.destination(
                [fixtures.reading(scheme_id=SCHEME.id)], verdict=schemes.Verdict.INTERPRETED
            )
        )
        assert isinstance(outcome, schemes.ChargedUnderTheScheme), outcome
        assert outcome.charge.scheme_id == SCHEME.id
        assert outcome.charge.on_date == CREDIT_DATE
        assert outcome.grounds

    def test_it_names_the_treatment_asked_about_and_the_scheme_that_charged_separately(
        self,
    ) -> None:
        """The two are different facts, and a shipped row having them equal hides that.

        An interpreted row may answer that income under one scheme, credited here, is charged
        under another. A record carrying only one of the two would label a charge with a
        scheme that did not produce it -- which is the shape no reader can detect, because
        every term of the figure is internally consistent.
        """
        outcome = schemes.apply(
            scheme_id=ROW_SCHEME.id,
            credited_to="synthetic_venue",
            amount=DOLLARS,
            on_dates=DATES,
            schemes=REGISTRY,
            destinations={
                (ROW_SCHEME.id, "synthetic_venue"): fixtures.destination(
                    [fixtures.reading(scheme_id=SCHEME.id)],
                    scheme_id=ROW_SCHEME.id,
                    verdict=schemes.Verdict.INTERPRETED,
                )
            },
            series=SERIES,
        )
        assert isinstance(outcome, schemes.ChargedUnderTheScheme), outcome
        assert outcome.declared_treatment == ROW_SCHEME.id
        assert outcome.charge.scheme_id == SCHEME.id
        assert outcome.charge.lines[0].rate == 0.06

    def test_the_rows_citations_travel_on_the_figure(self) -> None:
        outcome = _applied(
            fixtures.destination(
                [fixtures.reading(scheme_id=SCHEME.id)], verdict=schemes.Verdict.INTERPRETED
            )
        )
        assert isinstance(outcome, schemes.ChargedUnderTheScheme), outcome
        row = fixtures.destination(
            [fixtures.reading(scheme_id=SCHEME.id)], verdict=schemes.Verdict.INTERPRETED
        )
        # By id, not by `is_unverified`: every fixture citation is unverified already, so the
        # weaker check is true from the rate entry alone and says nothing about the row's.
        assert row.provenance.sources <= outcome.charge.total.provenance.sources
        assert prov.is_unverified(outcome.provenance)


class TestAnUnsettledDestinationProducesOneFigurePerComputableReading:
    """FR-026 and SC-017. The count is an output of the rule, never a fixed number."""

    @pytest.mark.parametrize("count", [1, 2, 3])
    def test_the_figure_count_is_the_number_of_computable_readings(self, count: int) -> None:
        outcome = _applied(
            fixtures.destination(
                [
                    fixtures.reading(reading_id=f"reading_{index}", scheme_id=SCHEME.id)
                    for index in range(count)
                ]
            )
        )
        assert isinstance(outcome, schemes.UnsettledDestination), outcome
        assert len(outcome.figures) == count

    def test_a_reading_recognised_on_a_different_date_strikes_a_different_base(self) -> None:
        """FR-026a's НБУ reading: the same scheme and components, on another date."""
        outcome = _applied(
            fixtures.destination(
                [
                    fixtures.reading(reading_id="on_credit", scheme_id=SCHEME.id),
                    fixtures.reading(
                        reading_id="on_repatriation",
                        scheme_id=SCHEME.id,
                        recognised_on=fixtures.REPATRIATED,
                    ),
                ]
            )
        )
        assert isinstance(outcome, schemes.UnsettledDestination), outcome
        first, second = outcome.figures
        assert first.charge.on_date == CREDIT_DATE
        assert second.charge.on_date == REPATRIATION_DATE
        assert first.charge.base.amount != second.charge.base.amount

    def test_every_figure_names_its_reading_and_carries_that_readings_citations(self) -> None:
        outcome = _applied(
            fixtures.destination(
                [
                    fixtures.reading(reading_id="one", scheme_id=SCHEME.id),
                    fixtures.reading(reading_id="two", scheme_id=OTHER_SCHEME.id),
                ]
            )
        )
        assert isinstance(outcome, schemes.UnsettledDestination), outcome
        assert [figure.reading_id for figure in outcome.figures] == ["one", "two"]
        for figure in outcome.figures:
            assert figure.label
            assert figure.provenance.sources <= figure.charge.provenance.sources

    def test_the_reading_and_the_row_mark_the_money_and_not_only_the_record(self) -> None:
        """A record-level subset check does not see the mark leaving the amounts.

        The row and the reading decide *which* rates strike a figure without multiplying it,
        so their citations reach the money only if they are put there -- and a transform that
        drops a mark is the constitution's top severity whatever it leaves on a sibling field.
        """
        row = fixtures.destination([fixtures.reading(scheme_id=SCHEME.id)])
        outcome = _applied(row)
        assert isinstance(outcome, schemes.UnsettledDestination), outcome
        figure = outcome.figures[0]
        selecting = row.provenance.sources | row.readings[0].provenance.sources
        assert selecting <= figure.charge.base.provenance.sources
        assert selecting <= figure.charge.total.provenance.sources
        for line in figure.charge.lines:
            assert selecting <= line.charged.provenance.sources, line.component_id

    def test_no_figure_is_labelled_the_tax_owed(self) -> None:
        outcome = _applied(fixtures.destination([fixtures.reading(scheme_id=SCHEME.id)]))
        assert isinstance(outcome, schemes.UnsettledDestination), outcome
        for figure in outcome.figures:
            assert "not the tax owed" in figure.not_the_tax_owed

    def test_a_declared_departure_from_the_source_is_reported_on_the_figure(self) -> None:
        """SC-017a. A departure nothing reports is a departure that becomes an absorption."""
        outcome = _applied(
            fixtures.destination(
                [
                    fixtures.reading(
                        scheme_id=SCHEME.id,
                        departs_from_source="SYNTHETIC -- the source computes it another way.",
                    )
                ]
            )
        )
        assert isinstance(outcome, schemes.UnsettledDestination), outcome
        assert outcome.figures[0].departs_from_source is not None


class TestACandidateThatCannotBeComputedIsNamedAndNotOmitted:
    """Line 3's second sentence: an omitted reading is how a switch comes to look complete."""

    def test_it_appears_on_the_switch_with_its_reason(self) -> None:
        outcome = _applied(
            fixtures.destination(
                [
                    fixtures.reading(reading_id="computable", scheme_id=SCHEME.id),
                    fixtures.reading(
                        reading_id="needs_an_undeclared_scheme",
                        scheme_id=None,
                        recognised_on=None,
                        uncomputable_because="no scheme declares them",
                    ),
                ]
            )
        )
        assert isinstance(outcome, schemes.UnsettledDestination), outcome
        assert len(outcome.figures) == 1
        assert [item.reading_id for item in outcome.uncomputable] == ["needs_an_undeclared_scheme"]
        assert "no scheme declares them" in outcome.uncomputable[0].because


class TestTheSwitchHasNowhereToPutABlend:
    """FR-026 and SC-017. A blended number would need somewhere to live. There is nowhere."""

    def test_the_record_holds_no_money_at_all(self) -> None:
        names = {field.name for field in dataclasses.fields(schemes.UnsettledDestination)}
        assert not names & {"total", "mean", "average", "blended", "combined", "owed"}
        annotations = {
            field.name: str(field.type)
            for field in dataclasses.fields(schemes.UnsettledDestination)
        }
        assert not [name for name, kind in annotations.items() if "Money" in kind]

    def test_a_figure_lifted_out_of_the_tuple_still_names_its_reading(self) -> None:
        """The label is on the figure, not on the slot it happened to be sitting in."""
        outcome = _applied(fixtures.destination([fixtures.reading(scheme_id=SCHEME.id)]))
        assert isinstance(outcome, schemes.UnsettledDestination), outcome
        lifted = outcome.figures[0]
        assert lifted.reading_id
        assert lifted.label
        assert lifted.not_the_tax_owed
        assert lifted.provenance.sources


class TestWhenNothingCanBeSaid:
    """FR-027. Refused as a typed result naming the destination, the scheme and its state."""

    def test_a_venue_the_table_has_no_row_for_refuses_and_names_both_closures(self) -> None:
        outcome = _applied(None, venue_id="a_venue_nobody_recorded")
        assert isinstance(outcome, schemes.CreditingDestinationRefused), outcome
        assert outcome.state is schemes.RefusedState.NO_DECLARED_JUDGEMENT
        assert outcome.venue_id == "a_venue_nobody_recorded"
        assert outcome.declared_treatment == SCHEME.id
        assert "find a source" in outcome.reason
        assert "add the row" in outcome.reason

    def test_a_row_whose_every_candidate_is_uncomputable_refuses_naming_them(self) -> None:
        outcome = _applied(
            fixtures.destination(
                [
                    fixtures.reading(
                        reading_id="needs_an_undeclared_scheme",
                        scheme_id=None,
                        recognised_on=None,
                        uncomputable_because="its rates are not declared anywhere",
                    )
                ]
            )
        )
        assert isinstance(outcome, schemes.CreditingDestinationRefused), outcome
        assert outcome.state is schemes.RefusedState.NO_CANDIDATE_IS_COMPUTABLE
        assert outcome.declared_treatment == SCHEME.id
        assert outcome.venue_id == "synthetic_venue"
        assert [item.reading_id for item in outcome.uncomputable] == ["needs_an_undeclared_scheme"]

    def test_a_switch_of_zero_figures_is_never_produced(self) -> None:
        """A switch holding nothing is a refusal wearing a switch's clothes."""
        outcome = _applied(
            fixtures.destination(
                [fixtures.reading(scheme_id=None, recognised_on=None, uncomputable_because="…")]
            )
        )
        assert not isinstance(outcome, schemes.UnsettledDestination), outcome


class TestAReadingThatCannotBeComputedForADataReasonRefuses:
    """A reading dropped from a switch is the defect the *named on the switch* clause prevents."""

    def test_a_date_name_the_caller_did_not_supply_names_the_reading_and_the_name(self) -> None:
        outcome = _applied(
            fixtures.destination(
                [fixtures.reading(scheme_id=SCHEME.id, recognised_on=fixtures.REPATRIATED)]
            ),
            on_dates={fixtures.CREDITED: CREDIT_DATE},
        )
        assert isinstance(outcome, schemes.ReadingRefused), outcome
        because = outcome.because
        assert isinstance(because, schemes.ReadingDateUndeclared), because
        assert because.recognised_on == fixtures.REPATRIATED
        assert because.declared == (fixtures.CREDITED,)

    def test_a_reading_whose_schedule_does_not_reach_its_date_refuses(self) -> None:
        early = date(2024, 6, 1)
        outcome = schemes.apply(
            scheme_id=SCHEME.id,
            credited_to="synthetic_venue",
            amount=DOLLARS,
            on_dates={fixtures.CREDITED: early},
            schemes=REGISTRY,
            destinations={
                (SCHEME.id, "synthetic_venue"): fixtures.destination(
                    [fixtures.reading(scheme_id=SCHEME.id)]
                )
            },
            series=official_rates.series([(early, RATE_ON_CREDIT)]),
        )
        assert isinstance(outcome, schemes.ReadingRefused), outcome
        assert isinstance(outcome.because, schemes.ComponentRateUndeclaredBefore)

    def test_a_reading_naming_a_scheme_the_registry_does_not_hold_raises(self) -> None:
        """The loader refuses a dangling reference, so reaching here is a bypassed check."""
        with pytest.raises(KeyError, match="nobody_declared_this"):
            _applied(fixtures.destination([fixtures.reading(scheme_id="nobody_declared_this")]))


class TestTheTaxOwedAndAWhatIfAreUnrelatedTypes:
    def test_neither_can_stand_in_for_the_other(self) -> None:
        assert not issubclass(schemes.ReadingFigure, schemes.ChargedUnderTheScheme)
        assert not issubclass(schemes.ChargedUnderTheScheme, schemes.ReadingFigure)
        assert schemes.ChargedUnderTheScheme.__bases__ == (object,)
        assert schemes.ReadingFigure.__bases__ == (object,)
