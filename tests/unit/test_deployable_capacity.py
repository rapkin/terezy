"""FR-015 and FR-016: a stream names a treatment, and naming none is still not zero.

Feature 002's ``income_tax_rate: float | None`` is retired. What replaces it is a **named
taxation scheme**, because a scalar cannot carry two components with different commencement
dates, an obligation triggered by a month, or the choice of a whole scheme.

**The behaviour that had to survive the migration verbatim**, and the reason this module
exists rather than being folded into the scheme's own tests: a stream that names **no**
treatment must produce the same claim, the same shape and the same reason it did before —
*the owner has not stated one*, which is not *a treatment that charges zero*. Returning the
gross in both cases would report a net figure that quietly equals the gross, right whenever
the charge happens to be nil and wrong by the charge the rest of the time, with nothing in
the output to say which a reader is looking at.

A schema change is exactly what deletes a carefully argued distinction by accident, and
``deployable`` has **one caller in the whole repository and it is this module**. Nothing else
would have noticed.

## Every value below is invented

The owner's real monthly figures have not been stated (``SIMULATOR_SPEC.md`` §11 item 3) and
the shipped rates are the owner's to verify. The rates here are round numbers chosen to make
the arithmetic checkable by eye and chosen *deliberately unlike* any real schedule.

## The three figures are in the tax currency, and they had to be

``gross - charged = net`` cannot hold across two currencies: the arrival is in dollars and
the charge is in hryvnia, and ``money.sub`` raises rather than pretending otherwise. Both
ways of forcing the identity into the stream's currency are forbidden — converting the
hryvnia charge back at the official rate is an official rate pricing a realised amount (011
FR-012), and putting it through the sale channel is a channel rate deciding a tax figure. So
all three are in the tax currency, and the arrival that produced them is on the conversion
record rather than copied into a second field.
"""

from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.tolerance import assert_money_close
from terezy.core.streams import capacity as capacity_module
from terezy.core.streams.capacity import DeployableCapacity, TaxTreatmentUndeclared
from terezy.core.streams.streams import IncomeStream, Indexation
from terezy.core.tax import scheme as schemes
from tests import official_rates
from tests import schemes as fixtures
from tests.invariants import route_graphs

GROSS = 100_000.0
"""What arrives each month, gross. Invented, and round so that every product below is exact
in binary floating point -- the arithmetic under test is the module's, not the float's."""

RATE = 0.1
"""An invented component rate: ten percent of a hundred thousand is ten thousand."""

CREDIT_DATE = date(2027, 3, 15)
SCHEDULE_START = date(2025, 1, 1)

STREAM_SOURCE = SourceRef(
    id="synthetic:stream-declaration",
    citation="SYNTHETIC FIXTURE -- a stream declaration that did carry a source.",
    retrieved_on=route_graphs.RETRIEVED_ON,
    verified_on=None,
)
STREAM_SOURCES: Provenance = prov.of([STREAM_SOURCE])
"""A mark on the gross amount, so propagation through the charge can be asserted.

Real stream declarations carry **no** source: an owner's own salary is a statement of fact by
the only person who can make it. So this fixture asserts the *mechanism* rather than the
current data -- if a gross amount ever does rest on a source, every figure derived from it
must still admit as much.
"""


def _scheme(*, rate: float = RATE) -> schemes.TaxationScheme:
    return fixtures.scheme(
        rate_components=[fixtures.rate_component([(SCHEDULE_START, rate)], component_id="one")]
    )


def _stream(*, treatment: str | None, gross: float = GROSS) -> IncomeStream:
    """The hryvnia salary with a stated gross and a stated -- or unstated -- treatment."""
    return dataclasses.replace(
        route_graphs.SALARY_UAH,
        amount=Money(gross, Currency.UAH, STREAM_SOURCES),
        tax_scheme=treatment,
    )


def _charged(*, rate: float = RATE, gross: float = GROSS) -> schemes.ChargedUnderTheScheme:
    scheme = _scheme(rate=rate)
    destination = fixtures.destination(
        [fixtures.reading(scheme_id=scheme.id)], verdict=schemes.Verdict.INTERPRETED
    )
    outcome = schemes.apply(
        scheme_id=scheme.id,
        credited_to=destination.venue_id,
        amount=Money(gross, Currency.UAH, STREAM_SOURCES),
        on_dates={fixtures.CREDITED: CREDIT_DATE},
        schemes={scheme.id: scheme},
        destinations={(scheme.id, destination.venue_id): destination},
        series=None,
    )
    assert isinstance(outcome, schemes.ChargedUnderTheScheme), outcome
    return outcome


def _capacity(*, rate: float = RATE, gross: float = GROSS) -> DeployableCapacity:
    charged = _charged(rate=rate, gross=gross)
    outcome = capacity_module.deployable(
        _stream(treatment=charged.scheme_id, gross=gross), charged=charged
    )
    assert isinstance(outcome, DeployableCapacity), outcome
    return outcome


class TestAnUndeclaredTreatmentProducesNoNetFigureAtAll:
    """FR-016, and it is 002's claim in 002's words: nobody said is not zero."""

    def test_a_stream_naming_no_treatment_reports_that_rather_than_a_figure(self) -> None:
        outcome = capacity_module.deployable(_stream(treatment=None), charged=None)
        assert isinstance(outcome, TaxTreatmentUndeclared)
        assert outcome.stream_id == route_graphs.SALARY_UAH.id

    def test_the_reason_says_no_treatment_is_declared_and_that_that_is_not_zero(self) -> None:
        # The output has to say it in words, not merely in a type: every degraded outcome
        # carries its reason, and the reason is what reaches the reader.
        outcome = capacity_module.deployable(_stream(treatment=None), charged=None)
        assert isinstance(outcome, TaxTreatmentUndeclared)
        assert "no tax treatment declared" in outcome.reason
        assert "not a treatment that charges zero" in outcome.reason

    def test_the_record_has_nowhere_for_a_net_figure_to_hide(self) -> None:
        # The structural half, and the one that holds the line: no field named for an amount
        # available to invest exists on this record, so no caller can read one off it and no
        # future edit can quietly start filling one in.
        fields = {field.name for field in dataclasses.fields(TaxTreatmentUndeclared)}
        assert fields == {"reason", "stream_id", "gross"}
        assert not fields & {"net", "charged", "charge", "deployable", "amount"}

    def test_the_gross_is_still_reported_because_it_is_still_known(self) -> None:
        # An upper bound is worth more than nothing, and refusing to report the arrival at
        # all would be its own kind of dishonesty. What the record does not do is call it
        # ``net`` or claim the two are equal.
        outcome = capacity_module.deployable(_stream(treatment=None), charged=None)
        assert isinstance(outcome, TaxTreatmentUndeclared)
        assert_money_close(outcome.gross, Money(GROSS, Currency.UAH, prov.EMPTY))

    def test_it_is_not_a_deployable_capacity_and_cannot_be_used_as_one(self) -> None:
        undeclared = capacity_module.deployable(_stream(treatment=None), charged=None)
        assert not isinstance(undeclared, DeployableCapacity)
        assert DeployableCapacity.__bases__ == (object,)
        assert TaxTreatmentUndeclared.__bases__ == (object,)


class TestTheTwoStatesCannotBeMixedUpByACaller:
    """A charge and a declaration that disagree is a programmer error, not a quiet default."""

    def test_a_charge_for_a_stream_that_names_no_treatment_raises(self) -> None:
        with pytest.raises(ValueError, match="names no tax treatment"):
            capacity_module.deployable(_stream(treatment=None), charged=_charged())

    def test_a_stream_naming_a_treatment_with_no_charge_raises(self) -> None:
        with pytest.raises(ValueError, match="names the tax treatment"):
            capacity_module.deployable(_stream(treatment="synthetic_scheme"), charged=None)


class TestADeclaredTreatmentIsAppliedAndShown:
    """FR-015's arithmetic, hand-computed, with every term of it reachable."""

    def test_ten_percent_of_a_hundred_thousand_leaves_ninety_thousand(self) -> None:
        #   gross   = 100 000.00 UAH
        #   charged = 100 000 x 0.1 =  10 000.00 UAH
        #   net     = 100 000 - 10 000 = 90 000.00 UAH
        capacity = _capacity()
        assert_money_close(capacity.charge.total, Money(10_000.0, Currency.UAH, prov.EMPTY))
        assert_money_close(capacity.net, Money(90_000.0, Currency.UAH, prov.EMPTY))

    def test_every_term_of_the_identity_is_present_and_none_is_duplicated(self) -> None:
        # ``net = gross - charged`` with all three reachable, so the figure can be checked by
        # reading it. ``gross`` is the charge's base and ``charged`` is its total: neither is
        # copied into a field of its own, because two fields holding one truth can disagree.
        capacity = _capacity()
        names = {field.name for field in dataclasses.fields(DeployableCapacity)}
        assert names == {"stream_id", "cadence", "charge", "net"}
        assert_money_close(
            capacity.net,
            Money(
                capacity.charge.base.amount - capacity.charge.total.amount,
                Currency.UAH,
                prov.EMPTY,
            ),
        )

    def test_the_net_is_net_of_the_regimes_charge_rather_than_of_a_scalar(self) -> None:
        # The point of the migration: the charge comes from a declared scheme's components,
        # each with its own dated cited rate, and the deployable figure is what is left of
        # the base after all of them.
        capacity = _capacity()
        assert [line.component_id for line in capacity.charge.lines] == ["one"]
        assert capacity.charge.lines[0].rate == RATE

    def test_the_figure_says_which_stream_and_which_period_it_is_for(self) -> None:
        # A monthly figure read as an annual one is wrong by a factor of twelve, and two
        # streams' capacities must not be addable by accident, so the record names both.
        capacity = _capacity()
        assert capacity.stream_id == route_graphs.SALARY_UAH.id
        assert capacity.cadence == "monthly"

    def test_the_mark_on_the_gross_reaches_the_net(self) -> None:
        # A figure derived from an unverified value inherits the mark. Nothing in this
        # arithmetic may launder it out -- and nothing can, because ``money``'s functions
        # only ever union provenance.
        capacity = _capacity()
        assert STREAM_SOURCE in capacity.net.provenance.sources
        assert prov.is_unverified(capacity.net.provenance)

    def test_the_schemes_own_citation_reaches_the_net_as_well(self) -> None:
        # The rate is a public legal fact now, so its mark has to travel too -- which is the
        # half the retired scalar could not do, because it carried no citation to travel.
        capacity = _capacity()
        rate_sources = capacity.charge.lines[0].provenance.sources
        assert rate_sources <= capacity.net.provenance.sources


class TestADeclaredZeroIsADifferentClaimFromNoTreatmentAtAll:
    """The distinction that makes the whole thing worth having.

    Both cases leave the whole gross available. Only one of them is *reported* as a net
    figure, and it is the one where a declaration says so.
    """

    def test_a_scheme_charging_zero_gives_a_net_figure_equal_to_the_gross(self) -> None:
        # Bit-identical, not merely close: multiplying by zero and subtracting the result is
        # exact, and a gross that came back changed in the last bits would mean an
        # arithmetic path nobody asked for.
        capacity = _capacity(rate=0.0)
        assert capacity.charge.total.amount == 0.0
        assert capacity.net.amount.hex() == capacity.charge.base.amount.hex()

    def test_the_two_cases_are_told_apart_by_type_and_not_by_reading_a_number(self) -> None:
        # The two figures are equal; the two answers are not. This is the assertion that
        # would fail if ``deployable`` ever returned the gross for an undeclared treatment.
        declared_zero = _capacity(rate=0.0)
        undeclared = capacity_module.deployable(_stream(treatment=None), charged=None)
        assert isinstance(undeclared, TaxTreatmentUndeclared)
        assert declared_zero.net.amount == undeclared.gross.amount


class TestNothingIsClamped:
    """B13's rule reaching a new place: a mis-entered rate is reported, not softened."""

    def test_a_rate_above_one_produces_a_negative_net_figure_and_says_so(self) -> None:
        #   charged = 100 000 x 1.5 = 150 000
        #   net     = 100 000 - 150 000 = -50 000
        # Absurd, and reported as absurd. A ``max(net, 0)`` here would turn a declaration
        # nobody could have meant into a plausible-looking zero.
        capacity = _capacity(rate=1.5)
        assert_money_close(capacity.net, Money(-50_000.0, Currency.UAH, prov.EMPTY))

    def test_a_zero_gross_stays_zero_in_every_term(self) -> None:
        # The degenerate case, which is the honest state of the declaration files today:
        # ``amount = 0.0`` because the owner's real figures have not been stated.
        capacity = _capacity(gross=0.0)
        assert capacity.charge.base.amount == 0.0
        assert capacity.charge.total.amount == 0.0
        assert capacity.net.amount == 0.0


class TestAForeignArrivalIsMeasuredInTheTaxCurrency:
    """The identity cannot hold across two currencies, so the figures are struck into one."""

    def test_the_conversion_travels_with_the_capacity_rather_than_a_second_gross_field(
        self,
    ) -> None:
        scheme = _scheme()
        destination = fixtures.destination(
            [fixtures.reading(scheme_id=scheme.id)], verdict=schemes.Verdict.INTERPRETED
        )
        charged = schemes.apply(
            scheme_id=scheme.id,
            credited_to=destination.venue_id,
            amount=Money(1_000.0, Currency.USD, STREAM_SOURCES),
            on_dates={fixtures.CREDITED: CREDIT_DATE},
            schemes={scheme.id: scheme},
            destinations={(scheme.id, destination.venue_id): destination},
            series=official_rates.series([(CREDIT_DATE, 40.0)]),
        )
        assert isinstance(charged, schemes.ChargedUnderTheScheme), charged
        stream = dataclasses.replace(
            route_graphs.SALARY_UAH,
            amount=Money(1_000.0, Currency.USD, STREAM_SOURCES),
            tax_scheme=scheme.id,
        )
        capacity = capacity_module.deployable(stream, charged=charged)
        assert isinstance(capacity, DeployableCapacity), capacity

        #   base = 1 000.00 USD x 40.00 = 40 000.00 UAH
        #   net  = 40 000 - 4 000 = 36 000.00 UAH
        assert_money_close(capacity.charge.base, Money(40_000.0, Currency.UAH, prov.EMPTY))
        assert_money_close(capacity.net, Money(36_000.0, Currency.UAH, prov.EMPTY))
        conversion = capacity.charge.conversion
        assert conversion is not None
        assert conversion.amount.currency is Currency.USD
        assert conversion.amount.amount == 1_000.0


class TestTheRecordsCarryDataAndNothingElse:
    """Owner decision D-E, asserted rather than trusted."""

    @pytest.mark.parametrize(
        "record", [IncomeStream, DeployableCapacity, TaxTreatmentUndeclared, Indexation]
    )
    def test_no_record_in_the_module_carries_behaviour(self, record: type) -> None:
        assert [
            name for name, value in vars(record).items() if callable(value) and "__" not in name
        ] == []

    def test_the_records_are_frozen(self) -> None:
        stream = _stream(treatment=None)
        with pytest.raises(dataclasses.FrozenInstanceError):
            stream.tax_scheme = "anything"  # type: ignore[misc]

    def test_the_retired_scalar_is_gone_rather_than_deprecated(self) -> None:
        # A debt paid halfway is a second debt: two ways to declare a tax position would mean
        # the older one kept working and nothing ever forced the migration.
        fields = {field.name for field in dataclasses.fields(IncomeStream)}
        assert "income_tax_rate" not in fields
        assert {"tax_scheme", "credited_to", "arrives_at"} <= fields
