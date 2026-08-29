"""A foreign taxable result meets the declared tax currency, and what happens there.

FR-007, FR-009 and FR-016 at the one site in the engine where a taxable result in a currency
the tax is not assessed in is reachable: ``core.tax.year._items``, which already refused for
want of this machinery.

Three answers, and the third is the one worth reading twice.

1. **A receipt in another currency is converted** at the official rate declared for the
   event's own date, and the statement it lands in names the series, the rate, the date that
   rate belongs to and the quotation unit -- enough to re-derive the base without opening a
   data file.
2. **A result already in the tax currency consults no rate**, and no rate-unavailable reason
   is attached to it. A refusal for a rate nobody needed trains a reader to ignore true ones.
3. **A disposal's realised gain is refused, not converted.** It is a difference between
   proceeds on one date and a basis struck on another, and striking it at one date's rate is
   the exact arithmetic required test F1 exists to catch: a position flat in dollars across a
   devaluation realises ``0 USD``, and ``0 USD`` at any rate is ``0 UAH``. The taxable gain
   F1 demands would be deleted by the conversion that was supposed to produce it. What is
   missing is a per-lot basis struck at its own date's rate, which is the
   ``fx-tax-asymmetry-f1`` entry in ``specs/features.toml``.
"""

from __future__ import annotations

from datetime import date

from terezy.core.ledger import engine
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.ledger.lots import LotMethod
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import SourceRef
from terezy.core.primitives.tolerance import is_close
from terezy.core.tax import flat_rate, official_rate
from terezy.core.tax import year as tax_year
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxClass, TaxContext
from tests import official_rates, tax_years

PURCHASED_ON = date(2027, 1, 5)
PAID_ON = date(2027, 6, 5)
REDEEMED_ON = date(2027, 9, 5)

RATE_ON_PAYMENT_DAY = 40.0
"""Invented. The examples check the conversion, not the hryvnia."""

SOURCE = prov.of(
    [
        SourceRef(
            id="tests/test_tax_base#fixture",
            citation="SYNTHETIC FIXTURE -- an invented holding.",
            retrieved_on=date(2026, 8, 24),
            verified_on=date(2026, 8, 24),
            kind="bond_terms",
        )
    ]
)
"""Verified, so a test asserting an *unverified* mark has to introduce one of its own."""

SERIES = official_rates.series(
    [(PAID_ON, RATE_ON_PAYMENT_DAY), (REDEEMED_ON, 44.0)],
    verified_on=date(2026, 8, 24),
)


def _term() -> CausationRef:
    return CausationRef(kind=CausationKind.INSTRUMENT_TERM, id="fixture:term", detail="fixture")


def _events(currency: Currency, *, redeem: bool) -> tuple[Event, ...]:
    """A purchase, a distribution, and optionally a redemption that realises a gain.

    A **distribution** rather than a coupon because the fixture pack taxes one per event and
    the other not at all -- and a per-event category is the arm that sums ``charge.pit``
    against the netting result's own currency, which is what makes converting only half of an
    item a currency mismatch rather than a cosmetic inconsistency.
    """
    events = [
        Event(
            sequence=1,
            occurred_on=PURCHASED_ON,
            kind=EventKind.PURCHASE,
            amount=Money(-1_000.00, currency, SOURCE),
            owner_id="owner-1",
            caused_by=_term(),
            lot_ref=LotRef(instrument_id="fixture", lot_id="lot-a"),
            quantity=10.0,
            allocated_to=None,
            capacity_pool=None,
        ),
        Event(
            sequence=2,
            occurred_on=PAID_ON,
            kind=EventKind.DISTRIBUTION,
            amount=Money(200.00, currency, SOURCE),
            owner_id="owner-1",
            caused_by=_term(),
            lot_ref=None,
            quantity=None,
            allocated_to=None,
            capacity_pool=None,
        ),
    ]
    if redeem:
        events.append(
            Event(
                sequence=3,
                occurred_on=REDEEMED_ON,
                kind=EventKind.PRINCIPAL_REPAYMENT,
                amount=Money(1_600.00, currency, SOURCE),
                owner_id="owner-1",
                caused_by=_term(),
                lot_ref=LotRef(instrument_id="fixture", lot_id=None),
                quantity=10.0,
                allocated_to=None,
                capacity_pool=None,
            )
        )
    return tuple(events)


def _charge(event: Event, kind: TaxableEventKind, base: Money, tax_class: TaxClass) -> TaxCharge:
    charged = flat_rate.charge(
        event,
        tax_class,
        TaxContext(
            instrument_id="fixture",
            taxable_event=kind,
            taxable_base=base,
            charged_for_year=event.occurred_on.year,
        ),
    )
    assert isinstance(charged, TaxCharge), charged
    return charged


def _assessed(
    currency: Currency,
    *,
    redeem: bool = False,
    series: official_rate.OfficialRateSeries | None = SERIES,
) -> tuple[tax_year.AnnualStatement, ...] | tax_year.TaxYearRefused:
    events = _events(currency, redeem=redeem)
    state = engine.fold(events, base_currency=currency, consumption_method=LotMethod.FIFO.value)
    charges = [
        _charge(
            events[1], TaxableEventKind.DISTRIBUTION, events[1].amount, tax_years.DISTRIBUTION_CLASS
        )
    ]
    if redeem:
        charges.append(
            _charge(
                events[2],
                TaxableEventKind.DISPOSAL_GAIN,
                state.disposals[0].realised_gain_base_ccy,
                tax_years.TAXED_CLASS,
            )
        )
    return tax_year.statements(
        state,
        tuple(charges),
        rules=tax_years.rules(official_rate=series),
        tax_classes=tax_years.TAX_PACK,
        filing=tax_years.filing(y2027=True),
        switches=tax_years.positions(),
    )


def _only(
    outcome: tuple[tax_year.AnnualStatement, ...] | tax_year.TaxYearRefused,
) -> tax_year.AnnualStatement:
    assert isinstance(outcome, tuple), outcome
    with_charges = [statement for statement in outcome if statement.charges]
    assert len(with_charges) == 1, with_charges
    return with_charges[0]


class TestAReceiptInAnotherCurrencyIsStruckAtTheOfficialRate:
    def test_the_base_is_the_amount_at_that_dates_declared_rate(self) -> None:
        """200.00 USD on the coupon date at 40.00 UAH per USD is 8 000.00 UAH."""
        statement = _only(_assessed(Currency.USD))

        assert statement.netted_base.currency is Currency.UAH
        assert is_close(statement.netted_base.amount, 8_000.00)
        assert is_close(200.00 * 40.00, 8_000.00)

    def test_the_charge_lines_are_struck_in_the_tax_currency_too(self) -> None:
        """The year sums the per-event lines against the netted result, so leaving them in
        the currency they were charged in would be a mismatch waiting for the first
        per-event category. 10% of 8 000.00 is 800.00; 5% is 400.00."""
        item = _only(_assessed(Currency.USD)).charges[0]

        assert item.charge.pit.currency is Currency.UAH
        assert is_close(item.charge.pit.amount, 800.00)
        assert is_close(item.charge.levy.amount, 400.00)
        assert is_close(item.charge.total.amount, 1_200.00)
        assert is_close(item.charge.total.amount, item.charge.pit.amount + item.charge.levy.amount)

    def test_the_item_names_everything_needed_to_re_derive_the_base(self) -> None:
        """FR-016, where a reader of the statement meets it."""
        item = _only(_assessed(Currency.USD)).charges[0]

        assert item.conversion is not None
        assert item.conversion.series_id == "synthetic_official_usd"
        assert item.conversion.event_date == PAID_ON
        assert item.conversion.rate_date == PAID_ON
        assert is_close(item.conversion.rate, RATE_ON_PAYMENT_DAY)
        assert is_close(item.conversion.quotation_unit, 1.0)


class TestAResultAlreadyInTheTaxCurrencyConsultsNoRate:
    def test_no_conversion_is_recorded_and_no_reason_is_attached(self) -> None:
        """SC-010. A false refusal is worse than none: it trains a reader to ignore true ones."""
        item = _only(_assessed(Currency.UAH)).charges[0]

        assert item.conversion is None
        assert item.charge.pit.currency is Currency.UAH
        assert is_close(item.charge.pit.amount, 20.00)


class TestWhereThereIsNoSeriesToStrikeItFrom:
    def test_a_jurisdiction_declaring_none_refuses_naming_what_is_missing(self) -> None:
        outcome = _assessed(Currency.USD, series=None)

        assert isinstance(outcome, tax_year.TaxCurrencyConversionUnavailable), outcome
        assert outcome.found is Currency.USD
        assert outcome.tax_currency is Currency.UAH
        assert outcome.unavailable.series_id is None

    def test_a_date_the_series_does_not_cover_refuses_naming_the_date(self) -> None:
        outcome = _assessed(Currency.USD, series=official_rates.series([(REDEEMED_ON, 44.0)]))

        assert isinstance(outcome, tax_year.TaxCurrencyConversionUnavailable), outcome
        undeclared = outcome.unavailable
        assert isinstance(undeclared, official_rate.OfficialRateUndeclaredOnDate), undeclared
        assert undeclared.on_date == PAID_ON
        assert undeclared.covers == (REDEEMED_ON, REDEEMED_ON)


class TestADisposalGainIsRefusedRatherThanStruckAtOneDatesRate:
    def test_the_refusal_names_the_machinery_a_two_currency_basis_needs(self) -> None:
        """See the module docstring: converting the gain deletes the FX gain F1 looks for."""
        outcome = _assessed(Currency.USD, redeem=True)

        assert isinstance(outcome, tax_year.ForeignGainNotStruckPerDate), outcome
        assert outcome.found is Currency.USD
        assert outcome.tax_currency is Currency.UAH
        assert "fx-tax-asymmetry-f1" in outcome.reason

    def test_a_hryvnia_disposal_in_the_same_shape_is_assessed_normally(self) -> None:
        """So the refusal above is about the currency and not about the disposal."""
        outcome = _assessed(Currency.UAH, redeem=True)

        assert isinstance(outcome, tuple), outcome


class TestTheRatesOwnSourceReachesTheLiability:
    """SC-005 at the far end: the charge and the year's liability rest on the rate too.

    Asserted at the statement rather than at the conversion because that is where the mark
    would be lost -- ``tests/contract/test_official_rate_marks.py`` checks the conversion
    itself, and a base that carries the mark into a liability that does not is exactly the
    silent laundering Principle I puts in its top severity class.
    """

    def test_the_charge_and_the_liability_name_the_observation_they_rest_on(self) -> None:
        statement = _only(_assessed(Currency.USD))
        rate_source = "synthetic:official_rate:2027-06-05"

        assert rate_source in {ref.id for ref in statement.charges[0].charge.provenance.sources}
        assert rate_source in {ref.id for ref in statement.liability.rests_on.sources}
        assert rate_source in {ref.id for ref in statement.netted_base.provenance.sources}

    def test_a_hryvnia_run_names_no_rate_at_all(self) -> None:
        """So the assertion above is about the conversion and not about every run."""
        statement = _only(_assessed(Currency.UAH))

        kinds = {ref.kind for ref in statement.liability.rests_on.sources}
        assert "official_rate" not in kinds
