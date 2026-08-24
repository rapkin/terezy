"""US4 and SC-004: the cash is not there on the due date, and the tool says exactly that.

```
2026-03-02  deposit                                        +11 000.00
2026-03-02  purchase 100 units at 100.00                   -10 000.00
2027-05-04  disposal of all 100 units for 14 000.00        +14 000.00
2027-12-20  withdrawal to somewhere else                   -14 900.00

cash on 2028-08-01                                             100.00
liability for the 2027 tax year, on a gain of 4 000.00         600.00
shortfall                                                      500.00
```

The plan looks fine gross and is infeasible net: the money that was going to pay the tax was
spent in December. That is the whole point of E7's second half -- and what the tool must
**not** do about it is sell something to cover the gap, which is the owner's explicitly
recorded deferral (FR-010).

**The deposit funds the purchase**, unlike most fixtures in this suite, so that the balance
is non-negative at every date until the tax is due. Otherwise "no balance ever goes negative"
would be false for a reason that has nothing to do with tax -- an unfunded purchase overdraws
by design, and ``instruments.fixed_income`` says why that is a feasibility question rather
than a ledger invariant.
"""

from __future__ import annotations

from datetime import date
from typing import Final

import pytest

from terezy.core.ledger import engine
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.ledger.lots import LotMethod
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close
from terezy.core.results import tax_year as settlement
from terezy.core.tax import flat_rate
from terezy.core.tax import year as tax_year
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxContext
from tests import tax_years

UAH: Final = Currency.UAH
OWNER: Final = "owner-1"
INSTRUMENT: Final = "fixture_taxable_a"
SOURCE: Final = prov.of([tax_years.FIXTURE_SOURCE])

LIABILITY: Final = 600.00
AVAILABLE: Final = 100.00
SHORTFALL: Final = 500.00
DUE_ON: Final = date(2028, 8, 1)
HORIZON_END: Final = date(2028, 12, 31)


def _uah(amount: float) -> Money:
    return Money(amount, UAH, SOURCE)


def _term() -> CausationRef:
    return CausationRef(
        kind=CausationKind.INSTRUMENT_TERM, id=f"{INSTRUMENT}:terms", detail="fixture term"
    )


def _events(*, withdrawal: float) -> tuple[Event, ...]:
    return (
        Event(
            sequence=1,
            occurred_on=date(2026, 3, 2),
            kind=EventKind.CASH_DEPOSIT,
            amount=_uah(11_000.00),
            owner_id=OWNER,
            caused_by=_term(),
            lot_ref=None,
            quantity=None,
            allocated_to=None,
            capacity_pool=None,
        ),
        Event(
            sequence=2,
            occurred_on=date(2026, 3, 2),
            kind=EventKind.PURCHASE,
            amount=_uah(-10_000.00),
            owner_id=OWNER,
            caused_by=_term(),
            lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id="lot-a"),
            quantity=100.0,
            allocated_to=None,
            capacity_pool=None,
        ),
        Event(
            sequence=3,
            occurred_on=date(2027, 5, 4),
            kind=EventKind.PRINCIPAL_REPAYMENT,
            amount=_uah(14_000.00),
            owner_id=OWNER,
            caused_by=_term(),
            lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id=None),
            quantity=100.0,
            allocated_to=None,
            capacity_pool=None,
        ),
        Event(
            sequence=4,
            occurred_on=date(2027, 12, 20),
            kind=EventKind.RAMP_MOVEMENT,
            amount=_uah(-withdrawal),
            owner_id=OWNER,
            caused_by=CausationRef(
                kind=CausationKind.ROUTE_TERM,
                id="fixture:route",
                detail="the money leaves for somewhere this ledger does not model",
            ),
            lot_ref=None,
            quantity=None,
            allocated_to=None,
            capacity_pool=None,
        ),
    )


def _settled(*, withdrawal: float) -> settlement.Settlement | settlement.SettlementRefused:
    events = _events(withdrawal=withdrawal)
    state = engine.fold(events, base_currency=UAH, consumption_method=LotMethod.FIFO.value)
    charged = flat_rate.charge(
        events[2],
        tax_years.TAXED_CLASS,
        TaxContext(
            instrument_id=INSTRUMENT,
            taxable_event=TaxableEventKind.DISPOSAL_GAIN,
            taxable_base=state.disposals[0].realised_gain_base_ccy,
            charged_for_year=2027,
        ),
    )
    assert isinstance(charged, TaxCharge), charged
    statements = tax_year.statements(
        state,
        (charged,),
        rules=tax_years.rules(),
        tax_classes=tax_years.TAX_PACK,
        filing=tax_years.filing(y2027=True),
        switches=tax_years.positions(),
    )
    assert isinstance(statements, tuple), statements
    return settlement.settle(
        events,
        statements,
        owner_id=OWNER,
        base_currency=UAH,
        method=LotMethod.FIFO,
        horizon_end=HORIZON_END,
    )


class TestTheShortfallIsATypedOutcome:
    """FR-009 and FR-012: the constraint is the result, not an exception and not a clamp."""

    def test_the_run_stops_with_the_three_hand_computed_figures(self) -> None:
        outcome = _settled(withdrawal=14_900.00)

        assert isinstance(outcome, settlement.InsufficientCashForTax), outcome
        assert_money_close(outcome.liability, _uah(LIABILITY))
        assert_money_close(outcome.available, _uah(AVAILABLE))
        assert_money_close(outcome.shortfall, _uah(SHORTFALL))

    def test_it_names_the_year_and_the_date_the_money_was_needed(self) -> None:
        outcome = _settled(withdrawal=14_900.00)

        assert isinstance(outcome, settlement.InsufficientCashForTax), outcome
        assert outcome.tax_year == 2027
        assert outcome.due_on == DUE_ON
        assert outcome.category == tax_years.INVESTMENT

    def test_the_projection_up_to_the_failure_date_is_still_traceable(self) -> None:
        """Not an empty result: everything before the constraint bound is still readable."""
        outcome = _settled(withdrawal=14_900.00)

        assert isinstance(outcome, settlement.InsufficientCashForTax), outcome
        assert [event.sequence for event in outcome.ledger.applied] == [1, 2, 3, 4]
        assert_money_close(outcome.ledger.accounts[UAH].balance, _uah(AVAILABLE))

    def test_the_reason_says_what_was_not_done_about_it(self) -> None:
        outcome = _settled(withdrawal=14_900.00)

        assert isinstance(outcome, settlement.InsufficientCashForTax), outcome
        assert "not skipped" in outcome.reason
        assert "nothing has been sold" in outcome.reason


class TestNothingIsSoldSkippedOrOverdrawn:
    """SC-004's three prohibitions, each asserted separately because each is a way to cheat."""

    def test_no_balance_ever_goes_negative(self) -> None:
        outcome = _settled(withdrawal=14_900.00)

        assert isinstance(outcome, settlement.InsufficientCashForTax), outcome
        history = engine.history(
            outcome.ledger.applied,
            base_currency=UAH,
            consumption_method=LotMethod.FIFO.value,
        )
        assert all(state.accounts[UAH].balance.amount >= 0.0 for state in history)

    def test_no_partial_payment_was_made(self) -> None:
        outcome = _settled(withdrawal=14_900.00)

        assert isinstance(outcome, settlement.InsufficientCashForTax), outcome
        assert not [
            event for event in outcome.ledger.applied if event.kind is EventKind.TAX_PAYMENT
        ]

    def test_no_disposal_appears_that_the_scenario_did_not_declare(self) -> None:
        """FR-010: which holdings a forced sale would draw on is the owner's deferral."""
        outcome = _settled(withdrawal=14_900.00)

        assert isinstance(outcome, settlement.InsufficientCashForTax), outcome
        assert [disposal.sequence for disposal in outcome.ledger.disposals] == [3]


class TestTheSameScenarioWithTheMoneyStillThere:
    """The boundary: one hryvnia either side of the liability decides the outcome."""

    def test_exactly_enough_cash_pays_and_leaves_nothing(self) -> None:
        # 25 000.00 in, 10 000.00 spent, 14 400.00 withdrawn -> 600.00 on the due date.
        outcome = _settled(withdrawal=14_400.00)

        assert isinstance(outcome, settlement.Settlement), outcome
        assert_money_close(outcome.ledger.accounts[UAH].balance, _uah(0.0))
        assert len(outcome.payments) == 1

    def test_one_unit_short_refuses(self) -> None:
        outcome = _settled(withdrawal=14_401.00)

        assert isinstance(outcome, settlement.InsufficientCashForTax), outcome
        assert_money_close(outcome.shortfall, _uah(1.00))


class TestAWithheldAtSourceClassRefusesRatherThanSelfAssessing:
    """FR-003: the behaviour is declarable, and settling one is not implemented."""

    def test_it_names_the_year_the_amount_and_the_gap(self) -> None:
        events = _events(withdrawal=0.0)
        state = engine.fold(events, base_currency=UAH, consumption_method=LotMethod.FIFO.value)
        charged = flat_rate.charge(
            events[2],
            tax_years.TAXED_CLASS,
            TaxContext(
                instrument_id=INSTRUMENT,
                taxable_event=TaxableEventKind.DISPOSAL_GAIN,
                taxable_base=state.disposals[0].realised_gain_base_ccy,
                charged_for_year=2027,
            ),
        )
        assert isinstance(charged, TaxCharge), charged
        withheld = tax_years.rules(
            timing={
                tax_years.INVESTMENT: tax_years.timing(
                    tax_years.INVESTMENT,
                    settlement=tax_year.SettlementBehaviour.WITHHELD_AT_SOURCE,
                ),
                tax_years.DISTRIBUTION: tax_years.timing(tax_years.DISTRIBUTION),
                tax_years.EXEMPT: tax_years.timing(tax_years.EXEMPT),
            }
        )
        statements = tax_year.statements(
            state,
            (charged,),
            rules=withheld,
            tax_classes=tax_years.TAX_PACK,
            filing=tax_years.filing(y2027=True),
            switches=tax_years.positions(),
        )
        assert isinstance(statements, tuple), statements

        outcome = settlement.settle(
            events,
            statements,
            owner_id=OWNER,
            base_currency=UAH,
            method=LotMethod.FIFO,
            horizon_end=HORIZON_END,
        )

        assert isinstance(outcome, settlement.WithholdingNotModelled), outcome
        assert outcome.tax_year == 2027
        assert_money_close(outcome.amount, _uah(LIABILITY))

    def test_a_withheld_statement_carries_no_due_date(self) -> None:
        """An absence that means something: there is no later payment to date."""
        rule = tax_years.timing(
            tax_years.INVESTMENT,
            settlement=tax_year.SettlementBehaviour.WITHHELD_AT_SOURCE,
        )

        assert rule.settlement is tax_year.SettlementBehaviour.WITHHELD_AT_SOURCE


@pytest.mark.parametrize("withdrawal", [14_900.00, 14_950.00, 14_999.00, 15_000.00])
def test_no_shortfall_run_ever_produces_a_payment_or_a_negative_balance(
    withdrawal: float,
) -> None:
    """SC-004 across a battery: 0% of shortfall runs pay, overdraw or sell."""
    outcome = _settled(withdrawal=withdrawal)

    assert isinstance(outcome, settlement.InsufficientCashForTax), outcome
    assert outcome.available.amount >= 0.0
    assert outcome.shortfall.amount > 0.0
    assert not [event for event in outcome.ledger.applied if event.kind is EventKind.TAX_PAYMENT]
