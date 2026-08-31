"""**J3** by hand: an exit refused, or executed at the declared haircut, taxed either way.

SC-007. The required-test row speaks of "an Inzhur window"; the funds' primary documents
show **no windows exist** (spec.md FR-015 ⚙). What the документы do give is two
distinguishable readings of the same exit, and the row's substance is preserved over them:
refuse, or execute at the declared discount, and tax the proceeds actually received.

Four cases, each with its arithmetic beside the assertion:

1. **practice** — buy back at NAV, same day, no discount, and the result says the mode
   rests on a revocable company practice with an empty verification date;
2. **legal, buyback available** — at NAV less the declared maximum discount, settled after
   the declared delay, with the discount as its own line and the tax on the post-discount
   proceeds;
3. **legal, buyback unavailable** — refused, naming that no obligation exists before the
   termination date, with the holding left open;
4. **held to the fund's own end** — a dated termination payout, taxed as a disposal.

**The fund is a SYNTHETIC FIXTURE and every term is invented.** It is an *accumulation*
fund, deliberately: with no payouts in the stream the arithmetic below is purely about the
exit, which is what J3 is about.

---

## The fixture

| Term | Value |
|---|---|
| NAV per unit | 200.00 UAH |
| units | 10 |
| declared yield | 10% a year, simple, all retained |
| day count | 30/360 |
| entry markup | live 1%, maximum 2% |
| exit discount | live 0%, maximum 2% |
| settlement | practice same day, legal 10 business days |
| purchased | 2028-01-10 |
| exit requested | 2028-07-10 — exactly half a year on 30/360 |
| fund terminates | 2030-01-10 — exactly two years |

    nav at the exit        = 200.00 x (1 + 0.10 x 0.5) = 210.00
    nav at the termination = 200.00 x (1 + 0.10 x 2.0) = 240.00

## Case 1 — the practice mode

    cost     = 200.00 x 1.01 x 10 = 2 020.00
    proceeds = 210.00 x 1.00 x 10 = 2 100.00      settled 2028-07-10, same day
    gain     = 2 100.00 - 2 020.00 = 80.00
    tax      = 80.00 x 0.18 = 14.40 PIT + 80.00 x 0.05 = 4.00 levy = 18.40

## Case 2 — the legal terms, buyback available

    cost     = 200.00 x 1.02 x 10 = 2 040.00
    discount = 210.00 x 0.02 x 10 =    42.00      its own line
    proceeds = 210.00 x 0.98 x 10 = 2 058.00      settled 2028-07-24, ten business days on
    gain     = 2 058.00 - 2 040.00 = 18.00        -- on the POST-discount proceeds
    tax      = 18.00 x 0.18 = 3.24 PIT + 18.00 x 0.05 = 0.90 levy = 4.14

## The price of relying on the legal floor (SC-007's last clause)

    cost:     2 040.00 - 2 020.00 =  20.00 = 200.00 x (0.02 - 0.01) x 10
    proceeds: 2 100.00 - 2 058.00 =  42.00 = 210.00 x  0.02        x 10
    delay:    2028-07-24 against 2028-07-10 = ten business days

Exactly the declared markup, the declared discount and the declared delay. Nothing else
differs between the two runs.

## Case 3 — the legal terms with the buyback withdrawn

No exit. A typed refusal naming 2030-01-10 as the next guaranteed exit, and the holding
stays open.

## Case 4 — held to the fund's own end

    proceeds = 240.00 x 10 = 2 400.00      no discount: the contract ended, nobody asked a
                                           favour. Settled 2030-01-24, on the legal delay.
    gain     = 2 400.00 - 2 020.00 = 380.00
    tax      = 380.00 x 0.23 = 87.40
"""

from __future__ import annotations

from datetime import date
from typing import Final

import pytest

from terezy.core.instruments import fund
from terezy.core.instruments.fund import (
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
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import fund as fund_results
from terezy.core.results.fund import (
    FundAssumptions,
    FundProjection,
    PurchaseAfterCutoff,
    RedemptionRefused,
)
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from terezy.core.tax.schedule import RateEntry
from tests import synthetic

pytestmark = pytest.mark.worked_example

UAH: Final = Currency.UAH
FUND_ID: Final = "synthetic_fund_liquidity"
DISPOSAL_CLASS: Final = "ua_investment_profit"

NAV: Final = 200.00
UNITS: Final = 10.0
YIELD: Final = 0.10
LIVE_MARKUP: Final = 0.01
MAX_MARKUP: Final = 0.02
LIVE_DISCOUNT: Final = 0.0
MAX_DISCOUNT: Final = 0.02
LEGAL_SETTLEMENT_DAYS: Final = 10

PURCHASED_ON: Final = date(2028, 1, 10)
EXIT_ON: Final = date(2028, 7, 10)
LEGAL_SETTLES_ON: Final = date(2028, 7, 24)
"""Ten business days after 2028-07-10, a Monday: two clear weeks, landing on a Monday."""

TERMINATES_ON: Final = date(2030, 1, 10)
TERMINATION_SETTLES_ON: Final = date(2030, 1, 24)
CUTOFF: Final = date(2029, 6, 30)
HORIZON_END: Final = date(2030, 12, 31)

PIT: Final = 0.18
LEVY: Final = 0.05

NAV_AT_EXIT: Final = NAV * (1.0 + YIELD * 0.5)  # 210.00
NAV_AT_TERMINATION: Final = NAV * (1.0 + YIELD * 2.0)  # 240.00

PRACTICE_COST: Final = NAV * (1.0 + LIVE_MARKUP) * UNITS  # 2 020.00
PRACTICE_PROCEEDS: Final = NAV_AT_EXIT * UNITS  # 2 100.00
PRACTICE_GAIN: Final = PRACTICE_PROCEEDS - PRACTICE_COST  # 80.00

LEGAL_COST: Final = NAV * (1.0 + MAX_MARKUP) * UNITS  # 2 040.00
LEGAL_DISCOUNT_AMOUNT: Final = NAV_AT_EXIT * MAX_DISCOUNT * UNITS  # 42.00
LEGAL_PROCEEDS: Final = NAV_AT_EXIT * (1.0 - MAX_DISCOUNT) * UNITS  # 2 058.00
LEGAL_GAIN: Final = LEGAL_PROCEEDS - LEGAL_COST  # 18.00

TERMINATION_PROCEEDS: Final = NAV_AT_TERMINATION * UNITS  # 2 400.00
TERMINATION_GAIN: Final = TERMINATION_PROCEEDS - PRACTICE_COST  # 380.00


def _fixture(what: str) -> Provenance:
    return prov.of(
        [
            SourceRef(
                id=f"fixture:liquidity:{what}",
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
                    effective_from=synthetic.SCHEDULE_START,
                    pit_rate=PIT,
                    levy_rate=LEVY,
                    provenance=_fixture("disposal rate entry"),
                ),
            ),
        )
    }


def _declaration() -> FundDeclaration:
    """An accumulation fund: no payouts, so the arithmetic is purely about the exit."""
    return FundDeclaration(
        id=FUND_ID,
        name="Synthetic accumulation fund — TEST FIXTURE, terms invented",
        unit_currency=UAH,
        is_assumption_driven=True,
        nav_per_unit=Money(NAV, UAH, _fixture("NAV per unit")),
        day_count="30/360",
        declared_yield=DeclaredYield(
            low=YIELD, high=YIELD, basis="simple_annual", provenance=_fixture("declared yield")
        ),
        distribution=None,
        spread=SpreadTerms(
            entry_markup_max=MAX_MARKUP,
            exit_discount_max=MAX_DISCOUNT,
            live_entry_markup=LIVE_MARKUP,
            live_exit_discount=LIVE_DISCOUNT,
            provenance=_fixture("spread terms"),
        ),
        liquidity=LiquidityTerms(
            legal=LegalTerms(
                buyback_before_termination="discretionary",
                settlement_business_days=LEGAL_SETTLEMENT_DAYS,
                note="FIXTURE — an invented legal floor with a ten-business-day settlement.",
                provenance=_fixture("legal terms"),
            ),
            practice=ObservedPractice(
                settlement_business_days=0,
                is_revocable=True,
                note="FIXTURE — an invented same-day buyback practice, revocable like any.",
                provenance=_fixture("observed practice"),
            ),
        ),
        minimum_units=1.0,
        subscription_cutoff=CUTOFF,
        terminates_on=TERMINATES_ON,
        tax_classes={TaxableEventKind.DISPOSAL_GAIN: DISPOSAL_CLASS},
        fee_context=(),
        verification_tasks=(),
        groups=(),
    )


def _holding(purchased_on: date = PURCHASED_ON) -> Holding:
    return Holding(
        owner_id="owner-1",
        instrument_id=FUND_ID,
        quantity=UNITS,
        purchased_on=purchased_on,
        cost=Money(PRACTICE_COST, UAH, prov.EMPTY),
    )


def _assumptions(
    mode: fund.LiquidityMode,
    *,
    buyback: fund.BuybackAvailability = "available",
    exit_on: date | None = EXIT_ON,
) -> FundAssumptions:
    return FundAssumptions(
        liquidity_mode=mode,
        buyback=buyback,
        exit_on=exit_on,
        yield_point=None,
        exchange_rate=None,
        consumption_method="fifo",
    )


def _run(
    assumptions: FundAssumptions,
    *,
    purchased_on: date = PURCHASED_ON,
) -> fund_results.FundOutcome:
    return fund_results.project_fund(
        _declaration(),
        _holding(purchased_on),
        DateRange(start=purchased_on, end=HORIZON_END),
        assumptions,
        tax_classes=_tax_pack(),
    )


def _projected(
    assumptions: FundAssumptions,
    *,
    purchased_on: date = PURCHASED_ON,
) -> FundProjection:
    outcome = _run(assumptions, purchased_on=purchased_on)
    assert isinstance(outcome, FundProjection), f"expected a projection, got {outcome!r}"
    return outcome


class TestCaseOneThePracticeMode:
    """At NAV, same day, no discount — and labelled as a revocable practice."""

    def test_the_exit_is_at_nav_with_no_discount(self) -> None:
        # 210.00 x 10 = 2 100.00
        line = _projected(_assumptions("practice")).exit_line
        assert line is not None
        assert line.discount_rate == 0.0
        assert is_close(line.nav_per_unit.amount, NAV_AT_EXIT)
        assert is_close(line.gross_proceeds.amount, PRACTICE_PROCEEDS)

    def test_it_settles_the_same_day(self) -> None:
        line = _projected(_assumptions("practice")).exit_line
        assert line is not None
        assert line.executed_on == EXIT_ON
        assert line.settles_on == EXIT_ON

    def test_the_gain_and_its_tax_are_the_hand_computed_ones(self) -> None:
        # 2 100.00 - 2 020.00 = 80.00; 80.00 x 0.23 = 18.40
        line = _projected(_assumptions("practice")).exit_line
        assert line is not None
        assert is_close(line.realised_gain.amount, PRACTICE_GAIN)
        assert is_close(line.tax.amount, PRACTICE_GAIN * (PIT + LEVY))

    def test_the_result_says_the_mode_it_assumed_and_that_it_is_revocable(self) -> None:
        """FR-016: every projection states which mode it assumed, on its face."""
        projection = _projected(_assumptions("practice"))
        assert projection.liquidity_mode == "practice"
        assert any("'practice'" in statement for statement in projection.rests_on)

    def test_every_figure_is_marked_because_the_practice_is_unverified(self) -> None:
        assert prov.is_unverified(_projected(_assumptions("practice")).provenance)


class TestCaseTwoTheLegalTermsWithTheBuybackAvailable:
    """At NAV less the declared maximum, settled after the declared delay."""

    def test_the_discount_is_the_declared_maximum_and_not_the_live_setting(self) -> None:
        """The terms guarantee only a ceiling, so the legal floor charges the ceiling.

        Reporting the live 0% here would present a discretionary favour as a right, which
        is the whole thing FR-017 exists to prevent.
        """
        line = _projected(_assumptions("legal")).exit_line
        assert line is not None
        assert line.discount_rate == MAX_DISCOUNT

    def test_the_discount_appears_as_its_own_line(self) -> None:
        # 210.00 x 0.02 x 10 = 42.00
        projection = _projected(_assumptions("legal"))
        assert projection.exit_discount is not None
        assert is_close(projection.exit_discount.amount, LEGAL_DISCOUNT_AMOUNT)

    def test_it_settles_ten_business_days_later(self) -> None:
        line = _projected(_assumptions("legal")).exit_line
        assert line is not None
        assert line.executed_on == EXIT_ON
        assert line.settles_on == LEGAL_SETTLES_ON

    def test_the_tax_is_computed_on_the_post_discount_proceeds(self) -> None:
        """FR-018 and FR-008 together, and the one figure a reader must be able to check.

        The gain is 18.00 because the proceeds are 2 058.00, not 2 100.00. Taxing the
        pre-discount NAV would give 60.00 of gain and 13.80 of tax on money that never
        arrived.
        """
        line = _projected(_assumptions("legal")).exit_line
        assert line is not None
        assert is_close(line.gross_proceeds.amount, LEGAL_PROCEEDS)
        assert is_close(line.realised_gain.amount, LEGAL_GAIN)
        assert is_close(line.taxable_base.amount, LEGAL_GAIN)
        assert is_close(line.tax.amount, LEGAL_GAIN * (PIT + LEVY))


class TestThePriceOfRelyingOnTheLegalFloor:
    """SC-007: the same request under both modes, differing by exactly what is declared."""

    def test_the_cost_differs_by_exactly_the_declared_markup(self) -> None:
        # 2 040.00 - 2 020.00 = 20.00 = 200.00 x (0.02 - 0.01) x 10
        practice = _projected(_assumptions("practice"))
        legal = _projected(_assumptions("legal"))
        assert is_close(
            legal.entry_spread.amount - practice.entry_spread.amount,
            NAV * (MAX_MARKUP - LIVE_MARKUP) * UNITS,
        )

    def test_the_proceeds_differ_by_exactly_the_declared_discount(self) -> None:
        # 2 100.00 - 2 058.00 = 42.00 = 210.00 x 0.02 x 10
        practice = _projected(_assumptions("practice")).exit_line
        legal = _projected(_assumptions("legal")).exit_line
        assert practice is not None
        assert legal is not None
        assert is_close(
            practice.gross_proceeds.amount - legal.gross_proceeds.amount,
            LEGAL_DISCOUNT_AMOUNT,
        )

    def test_the_settlement_differs_by_exactly_the_declared_delay(self) -> None:
        practice = _projected(_assumptions("practice")).exit_line
        legal = _projected(_assumptions("legal")).exit_line
        assert practice is not None
        assert legal is not None
        assert practice.settles_on == EXIT_ON
        assert legal.settles_on == LEGAL_SETTLES_ON

    def test_nothing_else_differs_between_the_two_runs(self) -> None:
        """The claim SC-007 actually makes: *exactly* the spread, discount and delay.

        Both runs price off the same NAV on the same date and end on the same request. If
        anything else moved, the difference between the modes would not be the declared
        terms -- and a reader comparing them would be reading a difference nobody declared.
        """
        practice = _projected(_assumptions("practice")).exit_line
        legal = _projected(_assumptions("legal")).exit_line
        assert practice is not None
        assert legal is not None
        assert practice.nav_per_unit.amount == legal.nav_per_unit.amount
        assert practice.executed_on == legal.executed_on
        assert practice.cause == legal.cause == "requested"
        assert practice.tax_class_id == legal.tax_class_id


class TestCaseThreeTheBuybackIsNotOnOffer:
    """FR-017 and research.md D6: refused, named, and the holding left open."""

    def test_the_redemption_is_a_typed_refusal(self) -> None:
        outcome = _run(_assumptions("legal", buyback="unavailable"))
        assert isinstance(outcome, RedemptionRefused), outcome

    def test_the_refusal_names_the_termination_date_as_the_next_guaranteed_exit(self) -> None:
        outcome = _run(_assumptions("legal", buyback="unavailable"))
        assert isinstance(outcome, RedemptionRefused)
        assert outcome.terminates_on == TERMINATES_ON
        assert outcome.requested_on == EXIT_ON
        assert "2030-01-10" in outcome.reason
        assert "discretionary" in outcome.reason

    def test_nothing_is_executed_at_the_legal_discount_instead(self) -> None:
        """The tempting failure: producing a number because a number was wanted.

        A refusal is not a projection, so there is no exit line, no proceeds and no tax to
        read off it -- which is the structural version of "the holding stays open".
        """
        outcome = _run(_assumptions("legal", buyback="unavailable"))
        assert not isinstance(outcome, FundProjection)
        assert not hasattr(outcome, "exit_line")
        assert not hasattr(outcome, "net_proceeds")

    def test_the_practice_mode_is_unaffected_because_it_is_the_buyback(self) -> None:
        """``buyback`` is read only under the legal terms: the practice mode *is* the buyback.

        Asserted so that the two switches cannot quietly become one: a run that refused a
        practice-mode exit because the *discretionary* buyback was withdrawn would be
        conflating the obligation with the habit.
        """
        assert isinstance(_run(_assumptions("practice", buyback="unavailable")), FundProjection)


class TestCaseFourHeldToTheFundsOwnEnd:
    """FR-019: a holding never silently outlives the fund that issued it."""

    def test_reaching_the_termination_date_produces_a_dated_payout(self) -> None:
        line = _projected(_assumptions("practice", exit_on=None)).exit_line
        assert line is not None
        assert line.cause == "termination"
        assert line.executed_on == TERMINATES_ON
        assert line.settles_on == TERMINATION_SETTLES_ON

    def test_the_termination_payout_is_at_nav_with_no_discount(self) -> None:
        # 240.00 x 10 = 2 400.00. The contract ended; nobody asked a favour.
        line = _projected(_assumptions("practice", exit_on=None)).exit_line
        assert line is not None
        assert line.discount_rate == 0.0
        assert is_close(line.nav_per_unit.amount, NAV_AT_TERMINATION)
        assert is_close(line.gross_proceeds.amount, TERMINATION_PROCEEDS)

    def test_it_is_taxed_as_a_disposal_like_any_other_exit(self) -> None:
        # 2 400.00 - 2 020.00 = 380.00; 380.00 x 0.23 = 87.40
        projection = _projected(_assumptions("practice", exit_on=None))
        line = projection.exit_line
        assert line is not None
        assert line.tax_class_id == DISPOSAL_CLASS
        assert is_close(line.realised_gain.amount, TERMINATION_GAIN)
        assert is_close(projection.total_tax.amount, TERMINATION_GAIN * (PIT + LEVY))

    def test_a_horizon_ending_before_the_fund_does_leaves_the_holding_open(self) -> None:
        """Nothing is liquidated because a projection ran out of dates."""
        outcome = fund_results.project_fund(
            _declaration(),
            _holding(),
            DateRange(start=PURCHASED_ON, end=date(2029, 6, 30)),
            _assumptions("practice", exit_on=None),
            tax_classes=_tax_pack(),
        )
        assert isinstance(outcome, FundProjection), outcome
        assert outcome.exit_line is None
        assert outcome.total_tax.amount == 0.0

    def test_an_exit_requested_after_the_fund_ends_becomes_the_termination_payout(self) -> None:
        """Not an early exit at all, and not a discounted one: the fund is over."""
        line = _projected(_assumptions("legal", exit_on=date(2030, 6, 1))).exit_line
        assert line is not None
        assert line.cause == "termination"
        assert line.executed_on == TERMINATES_ON
        assert line.discount_rate == 0.0


class TestThePurchaseCutoff:
    """SC-014: a purchase the fund would not have accepted did not happen."""

    def test_a_purchase_after_the_cutoff_is_refused_naming_it(self) -> None:
        outcome = _run(_assumptions("practice"), purchased_on=date(2029, 7, 1))
        assert isinstance(outcome, PurchaseAfterCutoff), outcome
        assert outcome.cutoff == CUTOFF
        assert outcome.purchased_on == date(2029, 7, 1)
        assert "2029-06-30" in outcome.reason

    def test_a_purchase_on_the_cutoff_itself_is_accepted(self) -> None:
        """The boundary is inclusive, and it is tested at the boundary rather than assumed."""
        assert isinstance(
            _run(
                _assumptions("practice", exit_on=None),
                purchased_on=CUTOFF,
            ),
            FundProjection,
        )


class TestAGuaranteedExitBeforeTerminationIsAFeasibilityFinding:
    """FR-019's third clause, and the half of J4 this feature's terms make real.

    Under the legal terms an early exit happens **only if the manager chooses**. Executing
    it and saying nothing would be the silent simulation FR-019 forbids: the run would look
    like a plan that works, when what it rests on is somebody else's discretion.
    """

    def test_a_legal_early_exit_states_that_it_is_not_guaranteed(self) -> None:
        projection = _projected(_assumptions("legal"))
        finding = [statement for statement in projection.rests_on if "NOT guaranteed" in statement]
        assert finding, projection.rests_on
        assert "discretionary" in finding[0]
        assert TERMINATES_ON.isoformat() in finding[0], (
            "the finding must name what the fund actually owes, not merely that it owes nothing"
        )

    def test_the_termination_payout_carries_no_such_finding(self) -> None:
        """Because it is not discretionary: the fund owes it, and the statement would be false."""
        projection = _projected(_assumptions("legal", exit_on=None))
        assert not [statement for statement in projection.rests_on if "NOT guaranteed" in statement]

    def test_the_practice_mode_carries_no_such_finding_either(self) -> None:
        """Its own statement already says the mode is a revocable practice, which is the
        same warning in the words that fit it. Two overlapping warnings would each get
        read as half of the other."""
        projection = _projected(_assumptions("practice"))
        assert not [statement for statement in projection.rests_on if "NOT guaranteed" in statement]
