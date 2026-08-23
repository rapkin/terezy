"""An accumulation fund by hand: a range that stays a range, and the spread that erodes it.

SC-012 and SC-013. Everything MilTech is, on a **SYNTHETIC FIXTURE** whose numbers are
chosen to be checkable in the head: no invented distributions, a declared rate accreting
pro rata to the exit, the round-trip spread reconciling exactly with the named lines, and
a fund-stated range reported at both ends rather than at a point nobody declared.

---

## The fixture

| Term | Value |
|---|---|
| NAV per unit | 1 000.00 UAH |
| units | 5 |
| declared yield | **20%-30%** a year, simple, all retained |
| day count | 30/360 |
| purchased | 2027-01-01 |
| fund terminates | 2029-01-01 — exactly two years |
| entry markup | live 0%, maximum 1% |
| exit discount | live 0%, maximum 1% |
| disposal tax | 18% + 5% = 23% |

    nav(t) = 1 000.00 x (1 + rate x 2)      two years exactly, on 30/360

## Both ends of the range, practice mode (no spread at all)

| | at 20% | at 30% |
|---|---|---|
| NAV at termination | 1 000 x 1.4 = **1 400.00** | 1 000 x 1.6 = **1 600.00** |
| proceeds (5 units) | 7 000.00 | 8 000.00 |
| cost | 5 000.00 | 5 000.00 |
| gain | 2 000.00 | 3 000.00 |
| tax at 23% | 460.00 | 690.00 |
| net | **1 540.00** | **2 310.00** |
| net simple annual | 1 540 / 5 000 / 2 = **15.40%** | 2 310 / 5 000 / 2 = **23.10%** |

Beside feature 001's tax-free hurdle of **16.0586%**, the low end of this fund's own
stated range **loses**. That is the whole reason the range is not collapsed.

## An owner-chosen point of 25%, legal terms, exiting early — the erosion line by line

A **requested** exit on 2028-07-01, a year and a half in on 30/360. It has to be a
requested one: the termination payout is the contract ending and carries no discount at
all, so a round trip has to be a round trip somebody asked for.

    nav on 2028-07-01 = 1 000.00 x (1 + 0.25 x 1.5) = 1 375.00

    cost      = 1 000.00 x 1.01 x 5 = 5 050.00      of which 50.00 is entry markup
    proceeds  = 1 375.00 x 0.99 x 5 = 6 806.25      of which 68.75 is exit discount
    gain      = 6 806.25 - 5 050.00 = 1 756.25
    tax       = 1 756.25 x 0.23     =   403.9375
    net       = 1 756.25 -  403.9375 = 1 352.3125

**The reconciliation SC-012 asks for.** Without any spread the same run would gain
6 875.00 - 5 000.00 = 1 875.00, so the spread cost exactly

    1 875.00 - 1 756.25 = 118.75 = 50.00 entry + 68.75 exit

and there is no residue: the round-trip figure and the two lines account for the whole
difference.

Settlement is declared same-day under **both** modes in this fixture. The delay is
``test_fund_liquidity.py``'s subject, and a lag here would only make the annualisation
below measure a period nobody was invested for.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Final

import pytest

from terezy.core.errors import InconsistentTerms
from terezy.core.instruments import fund
from terezy.core.instruments.fund import (
    ChosenPoint,
    DeclaredYield,
    FundDeclaration,
    LegalTerms,
    LiquidityTerms,
    ObservedPractice,
    SpreadTerms,
)
from terezy.core.instruments.interface import DateRange, Holding
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.rates import NominalRate, RealTermsUnavailable
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import fund as fund_results
from terezy.core.results.fund import (
    BesideTheHurdle,
    FundAssumptions,
    FundProjection,
    RangeProjection,
)
from terezy.core.results.hurdle import HurdleRate
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from terezy.core.tax.schedule import RateEntry

pytestmark = pytest.mark.worked_example

UAH: Final = Currency.UAH
FUND_ID: Final = "synthetic_fund_range"
DISPOSAL_CLASS: Final = "ua_investment_profit"

NAV: Final = 1_000.00
UNITS: Final = 5.0
LOW: Final = 0.20
HIGH: Final = 0.30
CHOSEN: Final = 0.25
EXIT_ON: Final = date(2028, 7, 1)
EXIT_YEARS: Final = 1.5
MAX_MARKUP: Final = 0.01
MAX_DISCOUNT: Final = 0.01

PURCHASED_ON: Final = date(2027, 1, 1)
TERMINATES_ON: Final = date(2029, 1, 1)
YEARS: Final = 2.0
HORIZON_END: Final = date(2029, 12, 31)

PIT: Final = 0.18
LEVY: Final = 0.05
TAX_RATE: Final = PIT + LEVY

HURDLE_YTM: Final = 0.16058553778779106
"""Feature 001's recorded hurdle, from ``tests/golden/ovdp_synthetic_a.golden.txt``.

Restated here rather than recomputed: this module is about the fund, and re-deriving the
benchmark would make a failure in the bond's arithmetic look like a failure in the fund's.
"""


def _at(
    rate: float,
    *,
    markup: float,
    discount: float,
    years: float = YEARS,
) -> tuple[float, float, float, float]:
    """``(nav, proceeds, gain, tax)`` for one rate, one spread and one holding period."""
    nav = NAV * (1.0 + rate * years)
    cost = NAV * (1.0 + markup) * UNITS
    proceeds = nav * (1.0 - discount) * UNITS
    gain = proceeds - cost
    return nav, proceeds, gain, gain * TAX_RATE


NAV_LOW, PROCEEDS_LOW, GAIN_LOW, TAX_LOW = _at(LOW, markup=0.0, discount=0.0)
NAV_HIGH, PROCEEDS_HIGH, GAIN_HIGH, TAX_HIGH = _at(HIGH, markup=0.0, discount=0.0)
NAV_CHOSEN, PROCEEDS_CHOSEN, GAIN_CHOSEN, TAX_CHOSEN = _at(
    CHOSEN, markup=MAX_MARKUP, discount=MAX_DISCOUNT, years=EXIT_YEARS
)

NET_LOW: Final = GAIN_LOW - TAX_LOW  # 1 540.00
NET_HIGH: Final = GAIN_HIGH - TAX_HIGH  # 2 310.00
NET_CHOSEN: Final = GAIN_CHOSEN - TAX_CHOSEN  # 1 352.3125

INVESTED_NO_SPREAD: Final = NAV * UNITS  # 5 000.00
INVESTED_WITH_SPREAD: Final = NAV * (1.0 + MAX_MARKUP) * UNITS  # 5 050.00

ENTRY_SPREAD: Final = NAV * MAX_MARKUP * UNITS  # 50.00
EXIT_SPREAD: Final = NAV_CHOSEN * MAX_DISCOUNT * UNITS  # 68.75
ROUND_TRIP: Final = ENTRY_SPREAD + EXIT_SPREAD  # 118.75


def _fixture(what: str) -> Provenance:
    return prov.of(
        [
            SourceRef(
                id=f"fixture:range:{what}",
                citation=f"SYNTHETIC FIXTURE — invented {what}. Not observed from any fund.",
                retrieved_on=date(2026, 8, 23),
                verified_on=None,
            )
        ]
    )


def _tax_pack() -> dict[str, TaxClass]:
    return {
        DISPOSAL_CLASS: TaxClass(
            id=DISPOSAL_CLASS,
            applies_to=frozenset({TaxableEventKind.DISPOSAL_GAIN}),
            rates=(
                RateEntry(
                    effective_from=date(2026, 6, 30),
                    pit_rate=PIT,
                    levy_rate=LEVY,
                    provenance=_fixture("disposal rate entry"),
                ),
            ),
        )
    }


def _declaration() -> FundDeclaration:
    return FundDeclaration(
        id=FUND_ID,
        name="Synthetic accumulation fund stating a range — TEST FIXTURE, terms invented",
        unit_currency=UAH,
        is_assumption_driven=True,
        nav_per_unit=Money(NAV, UAH, _fixture("NAV per unit")),
        day_count="30/360",
        declared_yield=DeclaredYield(
            low=LOW, high=HIGH, basis="simple_annual", provenance=_fixture("declared range")
        ),
        distribution=None,
        spread=SpreadTerms(
            entry_markup_max=MAX_MARKUP,
            exit_discount_max=MAX_DISCOUNT,
            live_entry_markup=0.0,
            live_exit_discount=0.0,
            provenance=_fixture("spread terms"),
        ),
        liquidity=LiquidityTerms(
            legal=LegalTerms(
                buyback_before_termination="discretionary",
                settlement_business_days=0,
                note=(
                    "FIXTURE — an invented legal floor, settling same-day so that the "
                    "annualisation here measures the period actually invested. The "
                    "settlement delay is tests/worked_examples/test_fund_liquidity.py's "
                    "subject, not this module's."
                ),
                provenance=_fixture("legal terms"),
            ),
            practice=ObservedPractice(
                settlement_business_days=0,
                is_revocable=True,
                note="FIXTURE — an invented same-day practice.",
                provenance=_fixture("observed practice"),
            ),
        ),
        minimum_units=1.0,
        subscription_cutoff=None,
        terminates_on=TERMINATES_ON,
        tax_classes={TaxableEventKind.DISPOSAL_GAIN: DISPOSAL_CLASS},
        fee_context=(),
        verification_tasks=(),
    )


def _holding() -> Holding:
    return Holding(
        owner_id="owner-1",
        instrument_id=FUND_ID,
        quantity=UNITS,
        purchased_on=PURCHASED_ON,
        cost=Money(INVESTED_NO_SPREAD, UAH, prov.EMPTY),
    )


def _assumptions(
    mode: fund.LiquidityMode,
    *,
    point: ChosenPoint | None = None,
    exit_on: date | None = None,
) -> FundAssumptions:
    return FundAssumptions(
        liquidity_mode=mode,
        buyback="available",
        exit_on=exit_on,
        yield_point=point,
        exchange_rate=None,
        consumption_method="fifo",
    )


def _run(assumptions: FundAssumptions) -> fund_results.FundOutcome:
    return fund_results.project_fund(
        _declaration(),
        _holding(),
        DateRange(start=PURCHASED_ON, end=HORIZON_END),
        assumptions,
        tax_classes=_tax_pack(),
    )


def _chosen_point(rate: float = CHOSEN) -> ChosenPoint:
    return ChosenPoint(
        rate=rate,
        is_assumption=True,
        rationale="FIXTURE — the owner's stated point inside the fund's declared range.",
    )


class TestAnAccumulationFundInventsNothing:
    """FR-023: no distributions for a fund that owes none, and no compounding either."""

    def test_no_distribution_events_are_invented(self) -> None:
        outcome = _run(_assumptions("practice", point=_chosen_point()))
        assert isinstance(outcome, FundProjection), outcome
        assert outcome.distributions == ()
        assert outcome.peg_statement is None

    def test_the_value_accrues_simply_and_comes_out_at_the_exit(self) -> None:
        # 1 000.00 x (1 + 0.25 x 2) = 1 500.00 at the termination two years in.
        # Compounding would give 1 562.50 — a figure the fund never claimed.
        outcome = _run(_assumptions("practice", point=_chosen_point()))
        assert isinstance(outcome, FundProjection), outcome
        assert outcome.exit_line is not None
        assert is_close(outcome.exit_line.nav_per_unit.amount, NAV * (1.0 + CHOSEN * YEARS))

    def test_the_exit_is_taxed_under_the_disposal_class(self) -> None:
        outcome = _run(_assumptions("practice", point=_chosen_point()))
        assert isinstance(outcome, FundProjection), outcome
        (subtotal,) = outcome.tax_by_class
        assert subtotal.tax_class_id == DISPOSAL_CLASS
        assert subtotal.kinds == (TaxableEventKind.DISPOSAL_GAIN,)


class TestARangeStaysARange:
    """SC-013 and research.md D11: two figures, and no midpoint anywhere."""

    def test_a_range_with_no_chosen_point_projects_both_ends(self) -> None:
        outcome = _run(_assumptions("practice"))
        assert isinstance(outcome, RangeProjection), outcome
        assert outcome.declared_yield.low == LOW
        assert outcome.declared_yield.high == HIGH

    def test_each_end_is_the_hand_computed_outcome(self) -> None:
        # 20%: nav 1 400.00, gain 2 000.00, tax 460.00, net 1 540.00
        # 30%: nav 1 600.00, gain 3 000.00, tax 690.00, net 2 310.00
        outcome = _run(_assumptions("practice"))
        assert isinstance(outcome, RangeProjection), outcome
        assert outcome.at_low.exit_line is not None
        assert outcome.at_high.exit_line is not None
        assert is_close(outcome.at_low.exit_line.nav_per_unit.amount, NAV_LOW)
        assert is_close(outcome.at_high.exit_line.nav_per_unit.amount, NAV_HIGH)
        assert is_close(outcome.at_low.total_tax.amount, TAX_LOW)
        assert is_close(outcome.at_high.total_tax.amount, TAX_HIGH)
        assert is_close(outcome.at_low.net_proceeds.amount, NET_LOW)
        assert is_close(outcome.at_high.net_proceeds.amount, NET_HIGH)

    def test_neither_end_is_the_midpoint_and_no_helper_produces_one(self) -> None:
        """The absence *is* the requirement, so it is asserted rather than assumed.

        A midpoint of 25% would give a net of 1 925.00 under this fixture's practice mode.
        No result in this project holds that figure unless the owner asked for it by name.
        """
        outcome = _run(_assumptions("practice"))
        assert isinstance(outcome, RangeProjection), outcome
        midpoint_net = (NET_LOW + NET_HIGH) / 2.0
        assert not is_close(outcome.at_low.net_proceeds.amount, midpoint_net)
        assert not is_close(outcome.at_high.net_proceeds.amount, midpoint_net)
        assert not [name for name in dir(fund) if "midpoint" in name.casefold()]
        assert not [name for name in dir(fund_results) if "midpoint" in name.casefold()]

    def test_a_chosen_point_produces_one_projection_labelled_the_owners(self) -> None:
        outcome = _run(_assumptions("practice", point=_chosen_point()))
        assert isinstance(outcome, FundProjection), outcome
        assert outcome.yield_basis == _chosen_point()
        assert any("chosen point" in statement for statement in outcome.rests_on)

    def test_a_point_outside_the_declared_range_is_refused_rather_than_clamped(self) -> None:
        """35% is not a choice *within* 20-30%; it is a different claim about the fund."""
        outcome = _run(_assumptions("practice", point=_chosen_point(0.35)))
        assert isinstance(outcome, InconsistentTerms), outcome
        assert "0.35" in outcome.reason

    def test_a_fund_stating_one_figure_needs_no_chosen_point(self) -> None:
        """``low == high`` is a point rate, and asking the owner to choose would be absurd."""
        declaration = replace(
            _declaration(),
            declared_yield=DeclaredYield(
                low=CHOSEN,
                high=CHOSEN,
                basis="simple_annual",
                provenance=_fixture("declared point"),
            ),
        )
        outcome = fund_results.project_fund(
            declaration,
            _holding(),
            DateRange(start=PURCHASED_ON, end=HORIZON_END),
            _assumptions("practice"),
            tax_classes=_tax_pack(),
        )
        assert isinstance(outcome, FundProjection), outcome
        assert isinstance(outcome.yield_basis, DeclaredYield)


class TestTheSpreadErosionReconciles:
    """SC-012: every line named, and no unexplained residue."""

    def _legal_run(self) -> FundProjection:
        outcome = _run(_assumptions("legal", point=_chosen_point(), exit_on=EXIT_ON))
        assert isinstance(outcome, FundProjection), outcome
        return outcome

    def test_the_two_spread_lines_are_the_hand_computed_ones(self) -> None:
        # entry 1 000.00 x 0.01 x 5 = 50.00; exit 1 375.00 x 0.01 x 5 = 68.75
        projection = self._legal_run()
        assert is_close(projection.entry_spread.amount, ENTRY_SPREAD)
        assert is_close(projection.exit_spread.amount, EXIT_SPREAD)
        assert is_close(projection.round_trip_spread.amount, ROUND_TRIP)

    def test_the_round_trip_accounts_for_the_whole_difference_from_a_spreadless_run(
        self,
    ) -> None:
        """1 875.00 - 1 756.25 = 118.75, exactly the two lines and nothing else.

        This is the assertion SC-012 is actually about. Two figures being "different" would
        be satisfied by any bug; a difference equal to the sum of the named lines can only
        come from those lines being what moved.
        """
        spreadless = _at(CHOSEN, markup=0.0, discount=0.0, years=EXIT_YEARS)[2]
        assert is_close(spreadless - GAIN_CHOSEN, ROUND_TRIP)
        projection = self._legal_run()
        assert projection.exit_line is not None
        assert is_close(projection.exit_line.realised_gain.amount, GAIN_CHOSEN)

    def test_the_net_reconciles_with_the_gain_and_the_tax(self) -> None:
        # 1 756.25 - 403.9375 = 1 352.3125
        projection = self._legal_run()
        assert is_close(projection.total_tax.amount, TAX_CHOSEN)
        assert is_close(projection.net_proceeds.amount, NET_CHOSEN)


class TestBesideTheHurdleRate:
    """FR-025: the comparison, and everything it leaves out, on the same record."""

    def _hurdle(self) -> HurdleRate:
        """001's benchmark as a record, restated rather than recomputed. See HURDLE_YTM."""
        return HurdleRate(
            nominal_ytm=NominalRate(HURDLE_YTM),
            nominal_cash_flow_return=NominalRate(HURDLE_YTM),
            real=RealTermsUnavailable(
                reason="FIXTURE — inflation is not modelled in this comparison."
            ),
            total_tax=Money(0.0, UAH, prov.EMPTY),
            accounts_for=frozenset({"tax on every taxable event over the holding's life"}),
            excludes=frozenset({"funding route costs (in)", "exit route costs (out)"}),
            provenance=prov.EMPTY,
        )

    def _compared(self, projection: FundProjection) -> BesideTheHurdle:
        outcome = fund_results.beside_hurdle(_declaration(), _holding(), projection, self._hurdle())
        assert isinstance(outcome, BesideTheHurdle), outcome
        return outcome

    def test_the_low_end_of_the_declared_range_loses_to_the_tax_free_bond(self) -> None:
        """15.40% against 16.0586%, and the tool says so plainly rather than rounding it away.

        This is the figure the whole feature exists to be able to produce. A fund-stated
        25-29% reads as an obvious win; after the 23% disposal tax the bottom of its own
        range does not clear a tax-exempt government bond.
        """
        outcome = _run(_assumptions("practice"))
        assert isinstance(outcome, RangeProjection), outcome
        compared = self._compared(outcome.at_low)
        assert is_close(compared.fund_net_simple_annual, NET_LOW / INVESTED_NO_SPREAD / YEARS)
        assert is_close(compared.fund_net_simple_annual, 0.154)
        assert compared.difference < 0.0

    def test_the_high_end_beats_it(self) -> None:
        # 2 310.00 / 5 000.00 / 2 = 23.10%
        outcome = _run(_assumptions("practice"))
        assert isinstance(outcome, RangeProjection), outcome
        compared = self._compared(outcome.at_high)
        assert is_close(compared.fund_net_simple_annual, 0.231)
        assert compared.difference > 0.0

    def test_the_chosen_point_under_the_legal_terms_is_annualised_over_what_was_invested(
        self,
    ) -> None:
        # 1 352.3125 / 5 050.00 / 1.5 = 17.85%, on the cost including the entry markup and
        # over the period actually held rather than over the fund's whole life.
        compared = self._compared(
            self._as_projection(_run(_assumptions("legal", point=_chosen_point(), exit_on=EXIT_ON)))
        )
        assert is_close(
            compared.fund_net_simple_annual, NET_CHOSEN / INVESTED_WITH_SPREAD / EXIT_YEARS
        )
        assert compared.years == EXIT_YEARS

    def _as_projection(self, outcome: fund_results.FundOutcome) -> FundProjection:
        assert isinstance(outcome, FundProjection), outcome
        return outcome

    def test_the_route_costs_excluded_statement_is_on_the_comparison_itself(self) -> None:
        """Not in a footnote and not left to the reader: the largest missing numbers, named."""
        compared = self._compared(
            self._as_projection(_run(_assumptions("legal", point=_chosen_point(), exit_on=EXIT_ON)))
        )
        assert fund_results.ROUTE_COSTS_EXCLUDED in compared.excludes
        assert any("assumption-driven" in statement for statement in compared.rests_on)

    def test_the_comparison_carries_the_marks_of_both_sides(self) -> None:
        compared = self._compared(
            self._as_projection(_run(_assumptions("legal", point=_chosen_point(), exit_on=EXIT_ON)))
        )
        assert prov.is_unverified(compared.provenance)
