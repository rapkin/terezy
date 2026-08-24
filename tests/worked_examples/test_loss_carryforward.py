"""E2: a loss year, then a gain year, hand-computed twice -- filed and unfiled.

Fixture rates are 10% PIT and 5% levy (``tests/tax_years.py``), so every figure below is
checkable in the head, and none of them is a Ukrainian liability.

```
2025-01-05  deposit                                         +40 000.00
2025-01-05  purchase lot-a, 100 units at 100.00             -10 000.00
2025-01-06  purchase lot-b, 100 units at 100.00             -10 000.00
2025-06-10  disposal of 100 units for  7 000.00              +7 000.00   FIFO: lot-a
2026-09-15  disposal of 100 units for 18 000.00             +18 000.00   FIFO: lot-b
```

```
2025 result =  7 000.00 - 10 000.00 = -3 000.00     a loss
2026 result = 18 000.00 - 10 000.00 = +8 000.00     a gain

FILED         2026 base = 8 000.00 - 3 000.00 = 5 000.00
              PIT  = 500.00   levy = 250.00   liability = 750.00
UNFILED       2026 base = 8 000.00                        (the loss never carried)
              PIT  = 800.00   levy = 400.00   liability = 1 200.00

the difference = 1 200.00 - 750.00 = 450.00 = 3 000.00 x 0.15
```

The 2026 liability falls due on 1 August 2027, **a Sunday**, so the declared ``following``
convention moves the payment to Monday 2027-08-02 (FR-008).
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
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxClass, TaxContext
from tests import tax_years

pytestmark = pytest.mark.worked_example

UAH: Final = Currency.UAH
OWNER: Final = "owner-1"
TAXABLE: Final = "fixture_taxable_a"
EXEMPT_BOND: Final = "fixture_exempt_bond_a"

LOSS: Final = 3_000.00
GAIN: Final = 8_000.00
FILED_BASE: Final = 5_000.00
FILED_LIABILITY: Final = 750.00
UNFILED_LIABILITY: Final = 1_200.00
COST_OF_NOT_FILING: Final = 450.00

DUE_ON: Final = date(2027, 8, 2)
"""1 August 2027 is a Sunday; the declared ``following`` convention pays on the Monday."""

HORIZON_END: Final = date(2027, 12, 31)
SOURCE: Final = prov.of([tax_years.FIXTURE_SOURCE])


def _uah(amount: float) -> Money:
    return Money(amount, UAH, SOURCE)


def _term(instrument: str) -> CausationRef:
    return CausationRef(
        kind=CausationKind.INSTRUMENT_TERM, id=f"{instrument}:terms", detail="fixture term"
    )


def _cash(sequence: int, on: date, amount: float) -> Event:
    return Event(
        sequence=sequence,
        occurred_on=on,
        kind=EventKind.CASH_DEPOSIT,
        amount=_uah(amount),
        owner_id=OWNER,
        caused_by=_term(TAXABLE),
        lot_ref=None,
        quantity=None,
        allocated_to=None,
        capacity_pool=None,
    )


def _buy(sequence: int, on: date, *, instrument: str, lot: str, cost: float, units: float) -> Event:
    return Event(
        sequence=sequence,
        occurred_on=on,
        kind=EventKind.PURCHASE,
        amount=_uah(-cost),
        owner_id=OWNER,
        caused_by=_term(instrument),
        lot_ref=LotRef(instrument_id=instrument, lot_id=lot),
        quantity=units,
        allocated_to=None,
        capacity_pool=None,
    )


def _sell(sequence: int, on: date, *, instrument: str, proceeds: float, units: float) -> Event:
    return Event(
        sequence=sequence,
        occurred_on=on,
        kind=EventKind.PRINCIPAL_REPAYMENT,
        amount=_uah(proceeds),
        owner_id=OWNER,
        caused_by=_term(instrument),
        lot_ref=LotRef(instrument_id=instrument, lot_id=None),
        quantity=units,
        allocated_to=None,
        capacity_pool=None,
    )


def _events(
    *,
    with_exempt_loss: bool = False,
    with_gain: bool = True,
    proceeds_2025: float = 7_000.00,
) -> tuple[Event, ...]:
    """The fixture above, with three optional variants each isolating one claim.

    ``with_exempt_loss`` adds an exempt-security loss beside the 2026 gain (SC-005).
    ``with_gain`` drops the gain year, leaving the carryforward unabsorbed at the horizon so
    that FR-019's reporting has something to report; a 2026 cash event keeps the ledger's span
    two years either way, so the quiet-year statement is the same one in both.
    ``proceeds_2025`` at 10 000.00 makes the loss year net to **exactly nothing**, which is
    the boundary where a sign is all that separates a break-even year from a loss year.
    """
    base = [
        _cash(1, date(2025, 1, 5), 40_000.00),
        _buy(2, date(2025, 1, 5), instrument=TAXABLE, lot="lot-a", cost=10_000.00, units=100.0),
        _buy(3, date(2025, 1, 6), instrument=TAXABLE, lot="lot-b", cost=10_000.00, units=100.0),
        _sell(4, date(2025, 6, 10), instrument=TAXABLE, proceeds=proceeds_2025, units=100.0),
        (
            _sell(5, date(2026, 9, 15), instrument=TAXABLE, proceeds=18_000.00, units=100.0)
            if with_gain
            else _cash(5, date(2026, 9, 15), 1.00)
        ),
    ]
    if with_exempt_loss:
        # 5 000.00 of an exempt security bought in 2025 and sold for 3 000.00 in 2026: a
        # 2 000.00 loss that buys no shield, because exempt operations are outside the
        # investment-profit calculation on both sides (FR-013).
        base.extend(
            [
                _buy(
                    6,
                    date(2025, 1, 6),
                    instrument=EXEMPT_BOND,
                    lot="lot-x",
                    cost=5_000.00,
                    units=50.0,
                ),
                _sell(7, date(2026, 9, 15), instrument=EXEMPT_BOND, proceeds=3_000.00, units=50.0),
            ]
        )
    return tuple(sorted(base, key=lambda event: (event.occurred_on, event.sequence)))


def _renumbered(events: tuple[Event, ...]) -> tuple[Event, ...]:
    from dataclasses import replace  # noqa: PLC0415 -- local to this fixture helper

    return tuple(replace(event, sequence=index + 1) for index, event in enumerate(events))


def _ledger(events: tuple[Event, ...]) -> engine.LedgerState:
    return engine.fold(events, base_currency=UAH, consumption_method=LotMethod.FIFO.value)


def _charges(state: engine.LedgerState, events: tuple[Event, ...]) -> tuple[TaxCharge, ...]:
    """One charge per disposal, through the production rule, on the signed realised gain."""
    by_sequence = {event.sequence: event for event in events}
    built: list[TaxCharge] = []
    for disposal in state.disposals:
        event = by_sequence[disposal.sequence]
        declared: TaxClass = (
            tax_years.EXEMPT_CLASS
            if disposal.instrument_id == EXEMPT_BOND
            else tax_years.TAXED_CLASS
        )
        charged = flat_rate.charge(
            event,
            declared,
            TaxContext(
                instrument_id=disposal.instrument_id,
                taxable_event=TaxableEventKind.DISPOSAL_GAIN,
                taxable_base=disposal.realised_gain_base_ccy,
                charged_for_year=event.occurred_on.year,
            ),
        )
        assert isinstance(charged, TaxCharge), charged
        built.append(charged)
    return tuple(built)


def _statements(
    *,
    filed_2025: bool,
    with_exempt_loss: bool = False,
    with_gain: bool = True,
    proceeds_2025: float = 7_000.00,
) -> tuple[tax_year.AnnualStatement, ...]:
    events = _renumbered(
        _events(with_exempt_loss=with_exempt_loss, with_gain=with_gain, proceeds_2025=proceeds_2025)
    )
    state = _ledger(events)
    built = tax_year.statements(
        state,
        _charges(state, events),
        rules=tax_years.rules(),
        tax_classes=tax_years.TAX_PACK,
        filing=tax_years.filing(y2025=filed_2025, y2026=True),
        switches=tax_years.positions(),
    )
    assert isinstance(built, tuple), built
    return built


def _investment(
    statements: tuple[tax_year.AnnualStatement, ...], year: int
) -> tax_year.AnnualStatement:
    found = [
        statement
        for statement in statements
        if statement.tax_year == year and statement.category == tax_years.INVESTMENT
    ]
    assert len(found) == 1, f"expected one {year} investment statement, got {found!r}"
    return found[0]


class TestTheFiledBranch:
    """SC-001: the loss carries, and the gain year is taxed on the netted figure."""

    def test_the_loss_year_owes_nothing_and_says_why(self) -> None:
        loss_year = _investment(_statements(filed_2025=True), 2025)

        assert_money_close(loss_year.netted_base, _uah(-LOSS))
        assert_money_close(tax_year.liability_total(loss_year.liability), _uah(0.0))
        assert loss_year.zero_because is tax_year.ZeroReason.NETTED_TO_ZERO

    def test_the_loss_becomes_a_carryforward_attributed_to_its_year(self) -> None:
        carried = _investment(_statements(filed_2025=True), 2025).carryforward
        assert carried is not None

        assert_money_close(carried.created, _uah(LOSS))
        assert_money_close(carried.open_balance, _uah(LOSS))
        assert carried.origins == ((2025, carried.origins[0][1]),)
        assert_money_close(carried.origins[0][1], _uah(LOSS))

    def test_the_gain_year_is_taxed_on_the_netted_base(self) -> None:
        # 8 000.00 - 3 000.00 = 5 000.00; PIT 500.00, levy 250.00.
        gain_year = _investment(_statements(filed_2025=True), 2026)

        assert_money_close(gain_year.netted_base, _uah(GAIN))
        assert_money_close(gain_year.liability.base, _uah(FILED_BASE))
        assert_money_close(gain_year.liability.pit, _uah(500.00))
        assert_money_close(gain_year.liability.levy, _uah(250.00))
        assert_money_close(tax_year.liability_total(gain_year.liability), _uah(FILED_LIABILITY))

    def test_the_carryforward_is_fully_absorbed(self) -> None:
        carried = _investment(_statements(filed_2025=True), 2026).carryforward
        assert carried is not None

        assert_money_close(carried.applied, _uah(LOSS))
        assert_money_close(carried.open_balance, _uah(0.0))
        assert carried.origins == ()

    def test_nothing_was_forfeited_and_nothing_cost_anything(self) -> None:
        for year in (2025, 2026):
            carried = _investment(_statements(filed_2025=True), year).carryforward
            assert carried is not None
            assert_money_close(carried.forfeited, _uah(0.0))
            assert_money_close(carried.cost_of_not_filing_to_date, _uah(0.0))


class TestAYearNettingToExactlyNothingIsNotALossYear:
    """The boundary at zero, where a sign is all that separates two different claims.

    Selling lot-a for exactly what it cost gives a 2025 result of ``0.00``. That is a
    break-even year: nothing is owed and nothing carries. Sent down the loss branch instead it
    reports a *loss* of ``-0.0`` and files an origin holding nothing -- a loss year in the
    output that never happened, and an empty shell in the queue later years draw from.
    """

    @staticmethod
    def _break_even() -> tax_year.AnnualStatement:
        return _investment(_statements(filed_2025=True, proceeds_2025=10_000.00), 2025)

    def test_it_creates_no_loss_and_files_no_origin(self) -> None:
        carried = self._break_even().carryforward
        assert carried is not None

        # ``repr`` rather than ``== 0.0``, which -0.0 also satisfies: the sign is the defect.
        assert repr(carried.created.amount) == "0.0"
        assert carried.origins == ()
        assert_money_close(carried.open_balance, _uah(0.0))

    def test_the_zero_is_a_netted_zero_and_not_an_exemption(self) -> None:
        year = self._break_even()

        assert_money_close(year.netted_base, _uah(0.0))
        assert year.zero_because is tax_year.ZeroReason.NETTED_TO_ZERO

    def test_the_following_gain_year_is_therefore_taxed_in_full(self) -> None:
        # Nothing carried out of 2025, so 2026's 8 000.00 is charged whole: 800.00 + 400.00.
        year = _investment(_statements(filed_2025=True, proceeds_2025=10_000.00), 2026)

        assert_money_close(year.liability.base, _uah(GAIN))
        assert_money_close(tax_year.liability_total(year.liability), _uah(UNFILED_LIABILITY))


class TestTheUnfiledBranch:
    """SC-001 and SC-010: the gain is taxed in full, and the cost is a figure on the page."""

    def test_the_loss_is_forfeited_rather_than_carried(self) -> None:
        carried = _investment(_statements(filed_2025=False), 2025).carryforward
        assert carried is not None

        assert_money_close(carried.forfeited, _uah(LOSS))
        assert_money_close(carried.created, _uah(0.0))
        assert_money_close(carried.open_balance, _uah(0.0))

    def test_the_gain_year_is_taxed_in_full(self) -> None:
        # 8 000.00 at 10% and 5% = 800.00 + 400.00 = 1 200.00.
        gain_year = _investment(_statements(filed_2025=False), 2026)

        assert_money_close(gain_year.liability.base, _uah(GAIN))
        assert_money_close(tax_year.liability_total(gain_year.liability), _uah(UNFILED_LIABILITY))

    def test_the_cost_of_not_filing_is_readable_from_one_figure(self) -> None:
        """SC-010: quotable without re-running the filed branch."""
        carried = _investment(_statements(filed_2025=False), 2026).carryforward
        assert carried is not None

        assert_money_close(carried.cost_of_not_filing_to_date, _uah(COST_OF_NOT_FILING))
        assert_money_close(carried.base_above_all_filed, _uah(LOSS))


class TestTheTwoBranchesDifferByExactlyTheCarryforward:
    """SC-001's arithmetic identity, asserted across the two runs."""

    def test_the_difference_is_the_loss_at_the_declared_rates(self) -> None:
        # 1 200.00 - 750.00 = 450.00 = 3 000.00 x (0.10 + 0.05).
        filed = tax_year.liability_total(_investment(_statements(filed_2025=True), 2026).liability)
        unfiled = tax_year.liability_total(
            _investment(_statements(filed_2025=False), 2026).liability
        )

        assert_money_close(
            Money(unfiled.amount - filed.amount, UAH, SOURCE), _uah(COST_OF_NOT_FILING)
        )

    def test_the_difference_is_what_the_unfiled_branch_reported_as_the_cost(self) -> None:
        carried = _investment(_statements(filed_2025=False), 2026).carryforward
        assert carried is not None
        filed = tax_year.liability_total(_investment(_statements(filed_2025=True), 2026).liability)
        unfiled = tax_year.liability_total(
            _investment(_statements(filed_2025=False), 2026).liability
        )

        assert_money_close(
            carried.cost_of_not_filing_to_date,
            Money(unfiled.amount - filed.amount, UAH, SOURCE),
        )


class TestBothLinesComeFromTheSameBase:
    """SC-011 and FR-017: the levy follows the netted base, never the gross."""

    def test_pit_and_levy_are_both_computed_from_the_reduced_figure(self) -> None:
        gain_year = _investment(_statements(filed_2025=True), 2026)
        base = gain_year.liability.base

        assert_money_close(gain_year.liability.pit, _uah(base.amount * tax_years.PIT_RATE))
        assert_money_close(gain_year.liability.levy, _uah(base.amount * tax_years.LEVY_RATE))

    def test_the_levy_base_never_exceeds_the_pit_base(self) -> None:
        """The defect this criterion exists for: one base, two lines, one reduction."""
        gain_year = _investment(_statements(filed_2025=True), 2026)

        assert_money_close(
            gain_year.liability.pit,
            _uah(gain_year.liability.levy.amount * (tax_years.PIT_RATE / tax_years.LEVY_RATE)),
        )

    def test_a_negative_year_charges_neither_line(self) -> None:
        loss_year = _investment(_statements(filed_2025=True), 2025)

        assert_money_close(loss_year.liability.pit, _uah(0.0))
        assert_money_close(loss_year.liability.levy, _uah(0.0))
        assert_money_close(loss_year.liability.base, _uah(0.0))

    def test_the_per_event_charge_on_a_loss_never_becomes_a_negative_liability(self) -> None:
        """``flat_rate`` charges a negative base as a negative pair; the year clamps once.

        The clamp is the statute's, not a convenience: a negative annual result means a zero
        base and no levy, with the loss preserved as a carryforward rather than swallowed.
        """
        loss_year = _investment(_statements(filed_2025=True), 2025)
        per_event = loss_year.charges[0].charge

        assert per_event.pit.amount < 0.0
        assert loss_year.liability.pit.amount == 0.0


class TestAnExemptLossBuysNoShield:
    """SC-005. The unwelcome half of the exemption, and it must be visible."""

    def test_the_taxable_result_is_identical_with_and_without_the_exempt_loss(self) -> None:
        without = _investment(_statements(filed_2025=True), 2026)
        with_loss = _investment(_statements(filed_2025=True, with_exempt_loss=True), 2026)

        assert_money_close(with_loss.netted_base, without.netted_base)
        assert_money_close(with_loss.liability.base, without.liability.base)
        assert_money_close(
            tax_year.liability_total(with_loss.liability),
            tax_year.liability_total(without.liability),
        )

    def test_the_exempt_operations_appear_nowhere_in_the_netting(self) -> None:
        statements = _statements(filed_2025=True, with_exempt_loss=True)
        investment = _investment(statements, 2026)

        assert [item.charge.tax_class_id for item in investment.charges] == [
            tax_years.TAXED_CLASS_ID
        ]

    def test_the_exempt_loss_is_still_recorded_in_its_own_category(self) -> None:
        """Outside the calculation is not the same as invisible."""
        statements = _statements(filed_2025=True, with_exempt_loss=True)
        exempt = [
            statement
            for statement in statements
            if statement.category == tax_years.EXEMPT and statement.tax_year == 2026
        ]

        assert len(exempt) == 1
        assert exempt[0].treatment is tax_year.Treatment.OUTSIDE
        assert exempt[0].carryforward is None
        assert exempt[0].zero_because is tax_year.ZeroReason.EXEMPT


class TestThePaymentMovesToTheNextBusinessDay:
    """FR-008: the convention is declared, applied, and stated on the event."""

    def test_the_sunday_deadline_pays_on_the_monday(self) -> None:
        statements = _statements(filed_2025=True)
        outcome = settlement.settle(
            _renumbered(_events()),
            statements,
            owner_id=OWNER,
            base_currency=UAH,
            method=LotMethod.FIFO,
            horizon_end=HORIZON_END,
        )
        assert isinstance(outcome, settlement.Settlement), outcome

        assert len(outcome.payments) == 1
        assert outcome.payments[0].due_on == DUE_ON
        assert_money_close(outcome.payments[0].amount, _uah(FILED_LIABILITY))

    def test_the_loss_year_produces_no_payment_at_all(self) -> None:
        outcome = settlement.settle(
            _renumbered(_events()),
            _statements(filed_2025=True),
            owner_id=OWNER,
            base_currency=UAH,
            method=LotMethod.FIFO,
            horizon_end=HORIZON_END,
        )
        assert isinstance(outcome, settlement.Settlement), outcome

        assert [payment.tax_year for payment in outcome.payments] == [2026]


class TestACarryforwardStillOpenAtTheHorizonIsReported:
    """FR-019. A loss nobody absorbed is a balance, not a rounding error to drop."""

    def test_the_open_balance_is_reported_with_its_origin_year(self) -> None:
        statements = _statements(filed_2025=True, with_gain=False)

        open_balances = settlement.open_carryforward(statements)

        assert len(open_balances) == 1
        assert open_balances[0].category == tax_years.INVESTMENT
        assert_money_close(open_balances[0].open_balance, _uah(LOSS))
        assert [year for year, _ in open_balances[0].origins] == [2025]

    def test_the_quiet_year_after_it_still_carries_the_balance(self) -> None:
        """A statement in a year with no operations says the balance passed through it."""
        quiet = _investment(_statements(filed_2025=True, with_gain=False), 2026)

        assert quiet.charges == ()
        assert quiet.carryforward is not None
        assert_money_close(quiet.carryforward.brought_in, _uah(LOSS))
        assert_money_close(quiet.carryforward.open_balance, _uah(LOSS))
        assert quiet.carryforward.filed is None

    def test_an_absorbed_carryforward_is_reported_as_nothing_open(self) -> None:
        """The other half: a balance of zero is not listed, because nothing is open."""
        assert settlement.open_carryforward(_statements(filed_2025=True)) == ()
