"""Where the join stops short: no rate, no span, and a tax base in the wrong currency.

Four boundaries, and none of them is an error. Each is a **typed occupant of a slot whose
value is genuinely unavailable** -- the shape ``ExitCostUnknown`` and ``RealTermsUnavailable``
already take, applied to the two things this feature computes.

* **No rate.** A tuple funded in one currency and spent in another has an amount and no ratio.
  It is reachable in the shipped registry, not a theoretical case: dollar contract income
  reaching a hryvnia fund produces a dollar outflow and hryvnia inflows, and an internal rate
  of return over the two is not a rate of anything. Valuing the outlay needs a reference rate
  on a date, which is feature 011 -- and a channel rate is not one.
* **No span the instrument can cover.** FR-025's second consequence: an instrument that cannot
  reach the comparison's horizon is infeasible **for that comparison**, with the binding term
  named, rather than silently truncated to whatever span it can manage.
* **No tax base this engine can strike.** FR-024: tax is assessed in the base currency at the
  official rate on the transaction date, and that machinery does not exist. The refusal names
  it. It must never be satisfied with a channel rate: a channel is a market you transact in,
  and the official rate is a legal reference you never transact at.
* **No conventional series.** A round trip whose repatriation charges exceed everything it
  released has no single internal rate of return, and extrapolating one past the bracket
  would invent a figure.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Final

from terezy.core.decision.compare import compare
from terezy.core.decision.tuple_outcome import Registries, evaluate
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.tuple import (
    BenchmarkUnavailable,
    CannotSpanHorizon,
    Comparison,
    InstrumentDemandsCash,
    InstrumentRefused,
    NoExitRouteDeclared,
    RateNotComparable,
    RouteInUnusable,
    TaxCurrencyConversionUnavailable,
    Tuple,
    TupleOutcome,
    WayOutUnusable,
)
from terezy.core.routes.path import DeclaredExit, FundingPath
from terezy.core.tax.schedule import RateEntry
from tests import tuple_registries as fixtures

UAH: Final = fixtures.UAH
BOND_CLASS: Final = "ua_government_bond"
FULL_HORIZON: Final = fixtures.DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END)


def _evaluated(
    registries: Registries,
    candidate: Tuple | None = None,
    *,
    amount: Money | None = None,
    horizon: fixtures.DateRange = FULL_HORIZON,
) -> object:
    return evaluate(
        candidate or fixtures.hurdle_tuple(),
        amount=amount or fixtures.AMOUNT,
        horizon=horizon,
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=registries,
    )


def _taxed_at(registries: Registries, *, pit: float, levy: float) -> Registries:
    """The bond's exempt class, with invented rates in place of its declared nil ones.

    A fixture rather than a declaration: rates above 100% describe no jurisdiction anywhere,
    and they exist here only to reach a shape the shipped rules cannot produce.
    """
    declared = registries.tax_classes[BOND_CLASS]
    entry = declared.rates[0]
    return replace(
        registries,
        tax_classes={
            **registries.tax_classes,
            BOND_CLASS: replace(
                declared,
                rates=(
                    RateEntry(
                        effective_from=entry.effective_from,
                        pit_rate=pit,
                        levy_rate=levy,
                        provenance=entry.provenance,
                    ),
                ),
            ),
        },
    )


class TestATupleFundedInOneCurrencyAndSpentInAnother:
    """The rate refuses; the amount does not."""

    def _registries(self) -> Registries:
        return fixtures.with_new_route(
            fixtures.shipped(),
            fixtures.fx_route("test_deel_to_inzhur", origin="deel", destination="inzhur"),
        )

    def _tuple(self) -> Tuple:
        return Tuple(
            instrument_id=fixtures.OVDP,
            stream_id="contract_usd",
            route_in=FundingPath(
                destination_id="inzhur",
                stream_id="contract_usd",
                route_id="test_deel_to_inzhur",
            ),
            exit_terms=fixtures.HOLD_TO_MATURITY,
            route_out=DeclaredExit(route_id=fixtures.DOMESTIC_OUT),
        )

    def _outcome(self) -> TupleOutcome:
        outcome = _evaluated(
            self._registries(),
            self._tuple(),
            amount=Money(1_000.0, Currency.USD, prov.EMPTY),
        )
        assert isinstance(outcome, TupleOutcome), outcome
        return outcome

    def test_the_amount_that_reaches_the_endpoint_is_reported(self) -> None:
        # 1 000 USD crosses the declared p2p quote into hryvnia, buys whole bonds and comes
        # home in hryvnia. Every one of those figures is real, and refusing the whole tuple
        # would throw them away for want of a ratio.
        outcome = self._outcome()
        assert outcome.reaches.currency is UAH
        assert outcome.reaches.amount > 0.0
        assert outcome.outlay.currency is Currency.USD

    def test_the_rate_is_a_typed_absence_naming_what_is_missing(self) -> None:
        rate = self._outcome().implied_rate
        assert isinstance(rate, RateNotComparable)
        assert "011" in rate.missing
        assert "USD" in rate.reason
        assert "UAH" in rate.reason

    def test_a_benchmark_with_no_rate_leaves_no_comparison_at_all(self) -> None:
        # FR-011: the hurdle is always scored and always shown, so a benchmark with no figure
        # is not a weaker comparison -- it is a different thing, and ranking the rest against
        # nothing would invite the head of the list to be read as a winner.
        comparison = compare(
            (),
            benchmark=self._tuple(),
            amount=Money(1_000.0, Currency.USD, prov.EMPTY),
            horizon=FULL_HORIZON,
            as_of=fixtures.AS_OF,
            continuation=fixtures.HOLD_AS_CASH,
            registries=self._registries(),
        )
        assert isinstance(comparison, BenchmarkUnavailable), comparison
        assert isinstance(comparison.refusal, RateNotComparable)


def _expensive_way_out() -> Registries:
    """The shipped registry with a way out whose flat fee exceeds everything the bond pays."""
    return fixtures.with_new_route(
        fixtures.shipped(),
        fixtures.route(
            "test_ruinous_out",
            origin="inzhur",
            destination="monobank_uah",
            direction="exit",
            fee_fixed=20_000.0,
        ),
    )


class TestASeriesWithNoRateToFind:
    """Two shapes, and neither is extrapolated past the bracket."""

    def test_an_outcome_with_no_rate_is_reported_beside_the_ranking_not_in_it(self) -> None:
        # 002's `Ranking.not_comparable`, unchanged: costed, reported, and not ranked. Ranking
        # it on the amount instead would compare two totals over two different spans.
        comparison = compare(
            (fixtures.hurdle_tuple(route_out=DeclaredExit(route_id="test_ruinous_out")),),
            benchmark=fixtures.hurdle_tuple(),
            amount=fixtures.AMOUNT,
            horizon=FULL_HORIZON,
            as_of=fixtures.AS_OF,
            continuation=fixtures.HOLD_AS_CASH,
            registries=_expensive_way_out(),
        )
        assert isinstance(comparison, Comparison), comparison
        assert len(comparison.not_comparable) == 1
        assert len(comparison.ranked) == 1
        assert comparison.ranked[comparison.benchmark].key == fixtures.hurdle_tuple()

    def test_a_coupon_taxed_away_entirely_travels_nowhere(self) -> None:
        # Taxed at exactly 100%, a coupon date nets to nothing and nothing goes home -- so no
        # exit fee is charged on a movement that did not happen. The principal is not taxable
        # income and still comes back, which is why this leaves a rate rather than no series
        # at all.
        outcome = _evaluated(_taxed_at(fixtures.shipped(), pit=0.5, levy=0.5))
        assert isinstance(outcome, TupleOutcome), outcome
        assert [arrival.released_on for arrival in outcome.arrivals] == [date(2028, 1, 17)]
        assert outcome.reaches.amount == 10_000.0

    def test_arrivals_eaten_by_a_flat_fee_are_reported_rather_than_annualised(self) -> None:
        # An exit charging 20 000.00 a movement takes more than every release, so the arrivals
        # are negative and the series is not one payment out followed by receipts. Reported as
        # it stands: the money did not vanish, and there is no single rate for it.
        outcome = _evaluated(
            _expensive_way_out(),
            fixtures.hurdle_tuple(route_out=DeclaredExit(route_id="test_ruinous_out")),
        )
        assert isinstance(outcome, TupleOutcome), outcome
        assert all(arrival.amount.amount < 0.0 for arrival in outcome.arrivals)
        rate = outcome.implied_rate
        assert isinstance(rate, RateNotComparable)
        assert "conventional series" in rate.missing


class TestAnInstrumentThatCannotSpanTheHorizon:
    """FR-025: infeasible for this comparison, with the binding term named."""

    def test_a_bond_maturing_after_the_horizon_ends(self) -> None:
        refusal = _evaluated(
            fixtures.shipped(),
            horizon=fixtures.DateRange(start=fixtures.ISSUE_DATE, end=date(2027, 6, 30)),
        )
        assert isinstance(refusal, CannotSpanHorizon), refusal
        assert refusal.binding_term == "instrument.maturity_date"

    def test_a_fund_still_open_at_the_horizon(self) -> None:
        # A holding is never sold because a projection ran out of dates. There is no round
        # trip to report, and an implicit liquidation would be a cash flow nobody asked for.
        refusal = _evaluated(
            fixtures.shipped(),
            fixtures.fund_tuple(fixtures.MILTECH, exit_on=None, yield_point=fixtures.MILTECH_POINT),
        )
        assert isinstance(refusal, CannotSpanHorizon), refusal
        assert refusal.binding_term == "instrument.terminates_on"

    def test_a_purchase_the_fund_would_not_have_accepted_carries_its_own_reason(self) -> None:
        # MilTech stopped accepting subscriptions on 2026-12-31, and the reason the join
        # reports is the fund module's own words rather than this module's paraphrase.
        refusal = _evaluated(
            fixtures.shipped(),
            fixtures.fund_tuple(
                fixtures.MILTECH, exit_on=date(2029, 6, 1), yield_point=fixtures.MILTECH_POINT
            ),
            horizon=fixtures.DateRange(start=date(2027, 3, 1), end=date(2029, 12, 31)),
        )
        assert isinstance(refusal, InstrumentRefused), refusal
        assert "subscriptions" in refusal.reason


class TestATaxBaseInTheWrongCurrency:
    """FR-024 and research.md D10: it refuses, and it names the machinery."""

    def test_a_taxable_instrument_in_a_foreign_currency_refuses(self) -> None:
        # Unreachable through the shipped registry -- every declared instrument is hryvnia --
        # which is a property of today's data rather than of the arithmetic. Reaching it needs
        # a registry built in code, and the guard exists because unreachable-today is not the
        # same as never.
        registries = fixtures.shipped()
        declared = registries.instruments[fixtures.OVDP]
        registries = replace(
            registries,
            instruments={
                **registries.instruments,
                fixtures.OVDP: replace(declared, currency=Currency.USD),
            },
        )
        refusal = _evaluated(registries)
        assert isinstance(refusal, TaxCurrencyConversionUnavailable), refusal
        assert refusal.instrument_currency == "USD"
        assert refusal.tax_currency == "UAH"
        assert "011" in refusal.missing
        assert "channel rate" in refusal.reason


class TestTheOtherWaysAPartRefuses:
    """The remaining feasibility paths, so none of them is a branch nothing exercises."""

    def test_a_closed_way_in_is_002s_refusal_carried_whole(self) -> None:
        registries = fixtures.with_route(fixtures.shipped(), fixtures.DOMESTIC_IN, status="closed")
        refusal = _evaluated(registries)
        assert isinstance(refusal, RouteInUnusable), refusal
        assert refusal.refused.binding_constraint == "route.status"

    def test_a_way_out_that_will_not_carry_a_coupon_names_the_date(self) -> None:
        # A minimum above a coupon and below the redemption: the small, frequent releases
        # cannot be repatriated at all, which is a real and non-obvious finding rather than a
        # rounding detail.
        registries = fixtures.with_leg(
            fixtures.shipped(), fixtures.DOMESTIC_OUT, minimum=Money(5_000.0, UAH, prov.EMPTY)
        )
        refusal = _evaluated(registries)
        assert isinstance(refusal, WayOutUnusable), refusal
        assert refusal.released_on == date(2026, 7, 15)
        assert refusal.refused.binding_constraint == "leg.minimum"

    def test_a_date_whose_tax_exceeds_its_income_is_refused_rather_than_netted_forward(
        self,
    ) -> None:
        # Taxed at 180%, each coupon date takes more out than it pays in, so money would have
        # to travel *to* the instrument along a route nobody costed. Netting it against a
        # later receipt would move a real outflow to a date it did not happen on.
        refusal = _evaluated(_taxed_at(fixtures.shipped(), pit=0.9, levy=0.9))
        assert isinstance(refusal, InstrumentDemandsCash), refusal
        assert refusal.on == date(2026, 7, 15)
        assert refusal.shortfall.amount > 0.0

    def test_a_way_out_that_stops_short_of_somewhere_spendable(self) -> None:
        registries = fixtures.with_new_route(
            fixtures.shipped(),
            fixtures.route(
                "test_inzhur_to_binance",
                origin="inzhur",
                destination="binance",
                direction="exit",
            ),
        )
        refusal = _evaluated(
            registries,
            fixtures.hurdle_tuple(route_out=DeclaredExit(route_id="test_inzhur_to_binance")),
        )
        assert isinstance(refusal, NoExitRouteDeclared), refusal
        assert "binance" in refusal.unknown.reason

    def test_proceeds_landing_somewhere_spendable_need_no_way_out_at_all(self) -> None:
        # 003 FR-002: the destination is itself a declared spendable endpoint, so the round
        # trip is complete the moment the instrument pays. Not a promoted one-way figure --
        # there is no way out left to travel.
        registries = fixtures.with_access(
            fixtures.shipped(), fixtures.OVDP, bought_at="monobank_uah", proceeds_to="monobank_uah"
        )
        registries = fixtures.with_new_route(
            registries,
            fixtures.route(
                "test_within_monobank",
                origin="monobank_uah",
                destination="monobank_uah",
                direction="inbound",
            ),
        )
        outcome = _evaluated(
            registries,
            replace(
                fixtures.hurdle_tuple(),
                route_in=FundingPath(
                    destination_id="monobank_uah",
                    stream_id=fixtures.SALARY,
                    route_id="test_within_monobank",
                ),
            ),
        )
        assert isinstance(outcome, TupleOutcome), outcome
        assert all(arrival.arrived_on == arrival.released_on for arrival in outcome.arrivals)
        assert next(line.amount for line in outcome.parts if line.part == "ramp_out").amount == 0.0
