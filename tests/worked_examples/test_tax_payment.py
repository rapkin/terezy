"""E7, first half: gross in the ledger at the trade, and the tax paid from cash next August.

The predecessor deducted tax from the portfolio at the moment of the trade
(``REWRITE_BRIEF`` §4.3, defect B5). Everything below is the correction, hand-computed.

---

**The fixture.** Synthetic throughout, and the rates are deliberately not Ukrainian --
``tests/tax_years.py`` charges 10% PIT and 5% levy so every figure here is checkable in the
head and none of them could be mistaken for a real liability.

```
2026-03-02  deposit                                        +50 000.00
2026-03-02  purchase 100 units at 100.00                   -10 000.00   lot A
2027-05-04  disposal of all 100 units for 14 000.00        +14 000.00
```

**The arithmetic, by hand.**

```
realised gain   = 14 000.00 - 10 000.00 =  4 000.00
PIT   at 10%    =  4 000.00 x 0.10      =    400.00
levy  at  5%    =  4 000.00 x 0.05      =    200.00      -- its own line, the same base
liability                                =    600.00      accruing to the 2027 tax year

cash at the disposal, GROSS:
   50 000.00 - 10 000.00 + 14 000.00     = 54 000.00      -- no tax has left anything
payment on the declared due date, 2028-08-01 (a Tuesday, so unadjusted):
   54 000.00 -    600.00                 = 53 400.00
```

**What each assertion is for.** The first three are FR-001: gross proceeds, a whole position
consumed, and **nothing deducted** on the day of the trade. The next are FR-004: one payment,
on the declared date, naming what it settles, folded like any other event. The last is
FR-006's other half -- 2026 saw nothing taxable and still produces a statement that says so.
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
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results import tax_year as settlement
from terezy.core.tax import flat_rate
from terezy.core.tax import year as tax_year
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxContext
from tests import tax_years

pytestmark = pytest.mark.worked_example

UAH: Final = Currency.UAH
OWNER: Final = "owner-1"
INSTRUMENT: Final = "fixture_taxable_a"

DEPOSIT: Final = 50_000.00
COST: Final = 10_000.00
PROCEEDS: Final = 14_000.00
GAIN: Final = 4_000.00
PIT: Final = 400.00
LEVY: Final = 200.00
LIABILITY: Final = 600.00
CASH_AT_DISPOSAL: Final = 54_000.00
CASH_AFTER_PAYMENT: Final = 53_400.00

BOUGHT_ON: Final = date(2026, 3, 2)
SOLD_ON: Final = date(2027, 5, 4)
DUE_ON: Final = date(2028, 8, 1)
"""1 August 2028 is a Tuesday, so the declared ``following`` convention leaves it alone. The
Sunday case -- where the convention actually moves a payment -- is exercised in
``test_loss_carryforward.py``, whose 2026 liability falls due on Sunday 2027-08-01."""

HORIZON_END: Final = date(2028, 12, 31)

SOURCE: Final = prov.of([tax_years.FIXTURE_SOURCE])


def _uah(amount: float) -> Money:
    return Money(amount, UAH, SOURCE)


def _term(detail: str) -> CausationRef:
    return CausationRef(kind=CausationKind.INSTRUMENT_TERM, id=f"{INSTRUMENT}:terms", detail=detail)


def _gross_events() -> tuple[Event, ...]:
    """The three events above, gross. Nothing here knows tax exists."""
    return (
        Event(
            sequence=1,
            occurred_on=BOUGHT_ON,
            kind=EventKind.CASH_DEPOSIT,
            amount=_uah(DEPOSIT),
            owner_id=OWNER,
            caused_by=_term("funding the account"),
            lot_ref=None,
            quantity=None,
            allocated_to=None,
            capacity_pool=None,
        ),
        Event(
            sequence=2,
            occurred_on=BOUGHT_ON,
            kind=EventKind.PURCHASE,
            amount=_uah(-COST),
            owner_id=OWNER,
            caused_by=_term("purchase of 100 units at 100.00"),
            lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id="lot-a"),
            quantity=100.0,
            allocated_to=None,
            capacity_pool=None,
        ),
        Event(
            sequence=3,
            occurred_on=SOLD_ON,
            kind=EventKind.PRINCIPAL_REPAYMENT,
            amount=_uah(PROCEEDS),
            owner_id=OWNER,
            caused_by=_term("disposal of 100 units for 14 000.00"),
            lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id=None),
            quantity=100.0,
            allocated_to=None,
            capacity_pool=None,
        ),
    )


def _gross_ledger() -> engine.LedgerState:
    return engine.fold(_gross_events(), base_currency=UAH, consumption_method=LotMethod.FIFO.value)


def _charge(state: engine.LedgerState) -> TaxCharge:
    """The disposal's charge, computed by the production rule on the realised gain.

    Through ``flat_rate.charge`` rather than written out, so this example tests the engine's
    own path from a gain to a charge rather than a hand-built record that happens to agree.
    """
    disposal = state.disposals[0]
    charged = flat_rate.charge(
        _gross_events()[2],
        tax_years.TAXED_CLASS,
        TaxContext(
            instrument_id=INSTRUMENT,
            taxable_event=TaxableEventKind.DISPOSAL_GAIN,
            taxable_base=disposal.realised_gain_base_ccy,
            charged_for_year=SOLD_ON.year,
        ),
    )
    assert isinstance(charged, TaxCharge), charged
    return charged


def _statements() -> tuple[tax_year.AnnualStatement, ...]:
    state = _gross_ledger()
    built = tax_year.statements(
        state,
        (_charge(state),),
        rules=tax_years.rules(),
        tax_classes=tax_years.TAX_PACK,
        filing=tax_years.filing(y2027=True),
        method=LotMethod.FIFO,
        switches=tax_years.positions(),
    )
    assert isinstance(built, tuple), built
    return built


def _charged_events() -> tuple[Event, ...]:
    """The same three events with the assessment memo recorded beside the disposal.

    Built exactly as ``results.project`` builds one -- ``tax_year.memo_amount`` of the charge's
    own total, dated with the income it taxes -- so the thing under test is the memo the
    engine produces and not a hand-written zero that happens to look like it.
    """
    charge = _charge(_gross_ledger())
    events = _gross_events()
    return (
        *events,
        Event(
            sequence=4,
            occurred_on=SOLD_ON,
            kind=EventKind.TAX_CHARGE,
            amount=tax_year.memo_amount(charge.total),
            owner_id=OWNER,
            caused_by=CausationRef(
                kind=CausationKind.TAX_RULE,
                id=charge.tax_class_id,
                detail=f"charged on event {charge.event_sequence}",
            ),
            lot_ref=None,
            quantity=None,
            allocated_to=None,
            capacity_pool=None,
        ),
    )


def _settled(*, charged: bool = False) -> settlement.Settlement:
    outcome = settlement.settle(
        _charged_events() if charged else _gross_events(),
        _statements(),
        owner_id=OWNER,
        base_currency=UAH,
        method=LotMethod.FIFO,
        horizon_end=HORIZON_END,
    )
    assert isinstance(outcome, settlement.Settlement), outcome
    return outcome


class TestNothingIsDeductedAtTheTrade:
    """FR-001. The gross amount lands, and the charge is recorded beside it."""

    def test_the_disposal_realises_the_hand_computed_gain(self) -> None:
        disposal = _gross_ledger().disposals[0]

        assert_money_close(disposal.proceeds_base_ccy, _uah(PROCEEDS))
        assert_money_close(disposal.consumed_basis_base_ccy, _uah(COST))
        assert_money_close(disposal.realised_gain_base_ccy, _uah(GAIN))

    def test_the_cash_balance_at_the_disposal_is_gross_of_the_tax(self) -> None:
        # 50 000.00 - 10 000.00 + 14 000.00 = 54 000.00, with 600.00 assessed and not taken.
        assert_money_close(_gross_ledger().accounts[UAH].balance, _uah(CASH_AT_DISPOSAL))

    def test_the_position_is_consumed_and_holds_nothing_back_for_tax(self) -> None:
        position = _gross_ledger().positions[INSTRUMENT]

        assert is_close(position.quantity, 0.0)
        assert position.lots == ()

    def test_the_charge_is_the_hand_computed_pair_on_the_gain(self) -> None:
        charge = _charge(_gross_ledger())

        assert_money_close(charge.taxable_base, _uah(GAIN))
        assert_money_close(charge.pit, _uah(PIT))
        assert_money_close(charge.levy, _uah(LEVY))
        assert charge.charged_for_year == SOLD_ON.year


class TestTheYearIsAssembledAfterwards:
    """FR-001, FR-002 and FR-006: one statement per year, and the zero years are there too."""

    def test_the_gain_year_carries_the_hand_computed_liability(self) -> None:
        gain_year = _year(2027)

        assert_money_close(gain_year.netted_base, _uah(GAIN))
        assert_money_close(gain_year.liability.base, _uah(GAIN))
        assert_money_close(gain_year.liability.pit, _uah(PIT))
        assert_money_close(gain_year.liability.levy, _uah(LEVY))
        assert_money_close(tax_year.liability_total(gain_year.liability), _uah(LIABILITY))

    def test_the_statement_enumerates_the_charge_it_was_built_from(self) -> None:
        """FR-002: checkable from the ledger, without re-deriving anything."""
        gain_year = _year(2027)

        assert len(gain_year.charges) == 1
        assert gain_year.charges[0].charge.event_sequence == 3
        assert gain_year.charges[0].charge.tax_class_id == tax_years.TAXED_CLASS_ID
        assert gain_year.charges[0].occurred_on == SOLD_ON

    def test_the_year_before_the_disposal_says_nothing_happened(self) -> None:
        """FR-006's third zero: a statement that says the year was looked at."""
        quiet = _year(2026)

        assert quiet.charges == ()
        assert quiet.zero_because is tax_year.ZeroReason.NO_TAXABLE_EVENTS
        assert_money_close(tax_year.liability_total(quiet.liability), _uah(0.0))

    def test_a_liability_cannot_name_a_method_the_ledger_did_not_consume_by(self) -> None:
        """FR-024, checked rather than stamped.

        The label on every figure is read back against ``LedgerState.consumption_method`` --
        the field that actually decided which lots the disposal drew on -- and assessing the
        same ledger under another method is refused by name rather than relabelled.
        """
        state = _gross_ledger()
        for statement in _statements():
            assert statement.liability.method.value == state.consumption_method
            assert statement.liability.standing.method.value == state.consumption_method

        relabelled = tax_year.statements(
            state,
            (_charge(state),),
            rules=tax_years.rules(),
            tax_classes=tax_years.TAX_PACK,
            filing=tax_years.filing(y2027=True),
            method=LotMethod.LIFO,
            switches=tax_years.positions(),
        )

        assert isinstance(relabelled, tax_year.MethodDisagreesWithLedger), relabelled


class TestTheMoneyLeavesOnTheDeclaredDate:
    """FR-004 and SC-003: one payment per positive-liability year, folded like any event."""

    def test_exactly_one_payment_settles_the_one_positive_year(self) -> None:
        settled = _settled()

        assert len(settled.payments) == 1
        assert settled.payments[0].tax_year == 2027
        assert_money_close(settled.payments[0].amount, _uah(LIABILITY))

    def test_the_payment_is_dated_by_the_declared_rule_not_by_the_trade(self) -> None:
        assert _settled().payments[0].due_on == DUE_ON

    def test_the_payment_event_debits_cash_and_names_what_it_settles(self) -> None:
        settled = _settled()
        paid = [event for event in settled.stream if event.kind is EventKind.TAX_PAYMENT]

        assert len(paid) == 1
        assert_money_close(paid[0].amount, _uah(-LIABILITY))
        assert paid[0].caused_by.kind is CausationKind.TAX_RULE
        assert "settles the 2027 annual statement" in paid[0].caused_by.detail

    def test_the_balance_falls_by_exactly_the_liability_and_no_earlier(self) -> None:
        # 54 000.00 gross at the disposal, 53 400.00 after 2028-08-01.
        history = engine.history(
            _settled().stream, base_currency=UAH, consumption_method=LotMethod.FIFO.value
        )
        before = next(state for state in history if state.as_of == SOLD_ON)

        assert_money_close(before.accounts[UAH].balance, _uah(CASH_AT_DISPOSAL))
        assert_money_close(_settled().ledger.accounts[UAH].balance, _uah(CASH_AFTER_PAYMENT))

    def test_no_charge_event_moved_anything(self) -> None:
        """The other half of the same claim: the assessment memo settles nothing.

        Settled from the **charged** stream, which is the only stream that has a memo in it to
        be about. Over the gross events this assertion ranges over nothing and passes for it,
        and a length guard is checked in as well so that it cannot start doing so again.

        The balance is the assertion that carries the claim: 53 400.00 after the payment, the
        same figure the gross stream reaches, so adding the memo moved nothing.
        """
        settled = _settled(charged=True)
        charges = [event for event in settled.stream if event.kind is EventKind.TAX_CHARGE]

        assert len(charges) == 1, settled.stream
        assert charges[0].amount.amount == 0.0
        assert_money_close(settled.ledger.accounts[UAH].balance, _uah(CASH_AFTER_PAYMENT))


class TestALiabilityDueAfterTheHorizonIsReportedNotDropped:
    """FR-007. An end-of-horizon balance that hides next year's bill overstates the outcome."""

    def test_the_obligation_is_reported_with_its_amount_and_its_date(self) -> None:
        outcome = settlement.settle(
            _gross_events(),
            _statements(),
            owner_id=OWNER,
            base_currency=UAH,
            method=LotMethod.FIFO,
            horizon_end=date(2028, 7, 31),
        )
        assert isinstance(outcome, settlement.Settlement), outcome

        assert outcome.payments == ()
        assert len(outcome.outstanding) == 1
        assert outcome.outstanding[0].due_on == DUE_ON
        assert_money_close(outcome.outstanding[0].amount, _uah(LIABILITY))

    def test_the_cash_still_holds_the_money_that_is_owed(self) -> None:
        """It is *not* paid early: the balance is gross, and the obligation is beside it."""
        outcome = settlement.settle(
            _gross_events(),
            _statements(),
            owner_id=OWNER,
            base_currency=UAH,
            method=LotMethod.FIFO,
            horizon_end=date(2028, 7, 31),
        )
        assert isinstance(outcome, settlement.Settlement), outcome

        assert_money_close(outcome.ledger.accounts[UAH].balance, _uah(CASH_AT_DISPOSAL))


def _year(tax_year_number: int) -> tax_year.AnnualStatement:
    found = [
        statement
        for statement in _statements()
        if statement.tax_year == tax_year_number and statement.category == tax_years.INVESTMENT
    ]
    assert len(found) == 1, f"expected one {tax_year_number} statement, got {found!r}"
    return found[0]
