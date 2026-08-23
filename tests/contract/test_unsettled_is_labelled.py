"""SC-012: a figure produced under an unsettled reading of the law says so, or is refused.

Two questions no source answers (spec.md FR-015, FR-024), each a declared switch with no
default:

* whether a carried loss survives a year whose declaration was missed;
* which of the two source-backed basis methods governs a self-declaring individual.

**The chain fixture**, at the fixture rates of 10% and 5%:

```
2025  loss  3 000.00   filed
2026  gain  1 000.00   NOT filed   -> taxed in full: 100.00 + 50.00 = 150.00
2027  gain  5 000.00   filed       -> the chain question arises here

chain-broken-forfeits   2027 base = 5 000.00            liability = 750.00
chain-restorable        2027 base = 5 000.00 - 3 000.00 = 2 000.00   liability = 300.00
```

The two branches differ by 450.00, and the cumulative cost of the missed 2026 declaration
differs with them: 450.00 where the chain broke, and **zero** where it merely deferred the
relief -- 150.00 paid early in 2026, 150.00 less in 2027.
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
from terezy.core.tax import flat_rate
from terezy.core.tax import year as tax_year
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxContext
from tests import tax_years

pytestmark = pytest.mark.contract

UAH: Final = Currency.UAH
OWNER: Final = "owner-1"
INSTRUMENT: Final = "fixture_taxable_a"
SOURCE: Final = prov.of([tax_years.FIXTURE_SOURCE])

BROKEN_LIABILITY: Final = 750.00
RESTORED_LIABILITY: Final = 300.00
BROKEN_COST: Final = 450.00
UNFILED_YEAR_LIABILITY: Final = 150.00


def _uah(amount: float) -> Money:
    return Money(amount, UAH, SOURCE)


def _term() -> CausationRef:
    return CausationRef(
        kind=CausationKind.INSTRUMENT_TERM, id=f"{INSTRUMENT}:terms", detail="fixture term"
    )


def _events() -> tuple[Event, ...]:
    """Three lots bought in 2025, sold one a year: a loss, a small gain, a larger gain."""
    built: list[Event] = [
        Event(
            sequence=1,
            occurred_on=date(2025, 1, 5),
            kind=EventKind.CASH_DEPOSIT,
            amount=_uah(60_000.00),
            owner_id=OWNER,
            caused_by=_term(),
            lot_ref=None,
            quantity=None,
            allocated_to=None,
            capacity_pool=None,
        )
    ]
    for index, lot in enumerate(("lot-a", "lot-b", "lot-c")):
        built.append(
            Event(
                sequence=2 + index,
                occurred_on=date(2025, 1, 5 + index),
                kind=EventKind.PURCHASE,
                amount=_uah(-10_000.00),
                owner_id=OWNER,
                caused_by=_term(),
                lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id=lot),
                quantity=100.0,
                allocated_to=None,
                capacity_pool=None,
            )
        )
    for index, (year, proceeds) in enumerate(
        ((2025, 7_000.00), (2026, 11_000.00), (2027, 15_000.00))
    ):
        built.append(
            Event(
                sequence=5 + index,
                occurred_on=date(year, 6, 10),
                kind=EventKind.PRINCIPAL_REPAYMENT,
                amount=_uah(proceeds),
                owner_id=OWNER,
                caused_by=_term(),
                lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id=None),
                quantity=100.0,
                allocated_to=None,
                capacity_pool=None,
            )
        )
    built.append(
        # A year inside the span with no investment operation at all, so that the "not
        # labelled" assertions below have a quiet statement to be about. Without it they
        # would range over an empty set and pass vacuously.
        Event(
            sequence=8,
            occurred_on=date(2028, 1, 5),
            kind=EventKind.CASH_DEPOSIT,
            amount=_uah(1_000.00),
            owner_id=OWNER,
            caused_by=_term(),
            lot_ref=None,
            quantity=None,
            allocated_to=None,
            capacity_pool=None,
        )
    )
    return tuple(built)


def _charges(state: engine.LedgerState) -> tuple[TaxCharge, ...]:
    by_sequence = {event.sequence: event for event in _events()}
    built: list[TaxCharge] = []
    for disposal in state.disposals:
        event = by_sequence[disposal.sequence]
        charged = flat_rate.charge(
            event,
            tax_years.TAXED_CLASS,
            TaxContext(
                instrument_id=INSTRUMENT,
                taxable_event=TaxableEventKind.DISPOSAL_GAIN,
                taxable_base=disposal.realised_gain_base_ccy,
                charged_for_year=event.occurred_on.year,
            ),
        )
        assert isinstance(charged, TaxCharge), charged
        built.append(charged)
    return tuple(built)


def _assessed(
    *,
    chain: tax_year.ChainPosition | None,
    method: LotMethod = LotMethod.FIFO,
    declared_method: LotMethod | None = LotMethod.AVERAGE_COST,
) -> tuple[tax_year.AnnualStatement, ...] | tax_year.TaxYearRefused:
    state = engine.fold(_events(), base_currency=UAH, consumption_method=LotMethod.FIFO.value)
    return tax_year.statements(
        state,
        _charges(state),
        rules=tax_years.rules(),
        tax_classes=tax_years.TAX_PACK,
        filing=tax_years.filing(y2025=True, y2026=False, y2027=True),
        method=method,
        switches=tax_years.positions(chain=chain, method=declared_method),
    )


def _year(statements: tuple[tax_year.AnnualStatement, ...], year: int) -> tax_year.AnnualStatement:
    found = [
        statement
        for statement in statements
        if statement.tax_year == year and statement.category == tax_years.INVESTMENT
    ]
    assert len(found) == 1, f"expected one {year} statement, got {found!r}"
    return found[0]


class TestTheChainQuestionHasNoDefault:
    """FR-015. Reaching the question without a declared position stops the run."""

    def test_an_undeclared_position_refuses_and_names_the_question(self) -> None:
        outcome = _assessed(chain=None)

        assert isinstance(outcome, tax_year.UnsettledPositionUndeclared), outcome
        assert "survives a year whose declaration was missed" in outcome.question
        assert "art. 52 PKU" in outcome.reason

    def test_the_question_does_not_arise_where_the_chain_is_unbroken(self) -> None:
        """A run with every year filed never reaches the switch, so it need not declare one."""
        state = engine.fold(_events(), base_currency=UAH, consumption_method=LotMethod.FIFO.value)
        outcome = tax_year.statements(
            state,
            _charges(state),
            rules=tax_years.rules(),
            tax_classes=tax_years.TAX_PACK,
            filing=tax_years.filing(y2025=True, y2026=True, y2027=True),
            method=LotMethod.FIFO,
            switches=tax_years.positions(chain=None),
        )

        assert isinstance(outcome, tuple), outcome


class TestBothBranchesComputeTheirOwnFigure:
    """US2 scenario 6: two readings, two numbers, both labelled."""

    def test_the_broken_branch_taxes_the_gain_year_in_full(self) -> None:
        statements = _assessed(chain=tax_year.ChainPosition.BROKEN_FORFEITS)
        assert isinstance(statements, tuple), statements
        year = _year(statements, 2027)

        assert_money_close(year.liability.base, _uah(5_000.00))
        assert_money_close(tax_year.liability_total(year.liability), _uah(BROKEN_LIABILITY))
        assert year.carryforward is not None
        assert_money_close(year.carryforward.forfeited, _uah(3_000.00))

    def test_the_restorable_branch_nets_the_surviving_loss(self) -> None:
        statements = _assessed(chain=tax_year.ChainPosition.RESTORABLE)
        assert isinstance(statements, tuple), statements
        year = _year(statements, 2027)

        assert_money_close(year.liability.base, _uah(2_000.00))
        assert_money_close(tax_year.liability_total(year.liability), _uah(RESTORED_LIABILITY))
        assert year.carryforward is not None
        assert_money_close(year.carryforward.applied, _uah(3_000.00))

    def test_the_unfiled_year_between_them_is_taxed_in_full_under_both(self) -> None:
        # 1 000.00 x 0.15 = 150.00, and the carried loss cannot be claimed without a return.
        for position in tax_year.ChainPosition:
            statements = _assessed(chain=position)
            assert isinstance(statements, tuple), statements

            assert_money_close(
                tax_year.liability_total(_year(statements, 2026).liability),
                _uah(UNFILED_YEAR_LIABILITY),
            )

    def test_the_cumulative_cost_distinguishes_a_lost_relief_from_a_deferred_one(self) -> None:
        """Where the chain breaks the relief is gone; where it survives it only moved."""
        broken = _year(_checked(_assessed(chain=tax_year.ChainPosition.BROKEN_FORFEITS)), 2027)
        restored = _year(_checked(_assessed(chain=tax_year.ChainPosition.RESTORABLE)), 2027)
        assert broken.carryforward is not None
        assert restored.carryforward is not None

        assert_money_close(broken.carryforward.cost_of_not_filing_to_date, _uah(BROKEN_COST))
        assert_money_close(restored.carryforward.cost_of_not_filing_to_date, _uah(0.0))


class TestEveryFigureUnderTheSwitchCarriesIt:
    """SC-012 and G14, and the other half: a label only where the reading changed something."""

    def test_the_year_the_question_arose_in_is_labelled(self) -> None:
        for position in tax_year.ChainPosition:
            statements = _checked(_assessed(chain=position))
            labelled = _year(statements, 2027).unsettled

            assert any("declaration was missed" in switch.question for switch in labelled)
            assert all("art. 52 PKU" in switch.resolution_path for switch in labelled)

    def test_the_years_before_it_are_not_labelled_with_the_chain_switch(self) -> None:
        """A label on every statement is a label a reader learns to ignore."""
        statements = _checked(_assessed(chain=tax_year.ChainPosition.BROKEN_FORFEITS))

        for year in (2025, 2026):
            assert not [
                switch
                for switch in _year(statements, year).unsettled
                if "declaration was missed" in switch.question
            ]

    def test_the_declared_position_is_the_one_recorded_on_the_label(self) -> None:
        statements = _checked(_assessed(chain=tax_year.ChainPosition.RESTORABLE))
        labelled = [
            switch
            for switch in _year(statements, 2027).unsettled
            if "declaration was missed" in switch.question
        ]

        assert [switch.position for switch in labelled] == ["chain_restorable"]


class TestTheMethodQuestionIsLabelledWhereItBites:
    """FR-024: the two source-backed readings give different numbers, and nothing settles which."""

    def test_a_source_backed_method_needs_a_declared_position(self) -> None:
        outcome = _assessed(
            chain=tax_year.ChainPosition.RESTORABLE,
            method=LotMethod.AVERAGE_COST,
            declared_method=None,
        )

        assert isinstance(outcome, tax_year.UnsettledPositionUndeclared), outcome
        assert "self-declaring individual" in outcome.question

    def test_a_year_containing_a_disposal_is_labelled_with_the_method_switch(self) -> None:
        statements = _checked(_assessed(chain=tax_year.ChainPosition.RESTORABLE))

        assert any(
            "basis method governs a self-declarant" in switch.question
            for switch in _year(statements, 2027).unsettled
        )

    def test_a_method_no_source_backs_needs_no_position_and_says_so(self) -> None:
        """LIFO is a what-if against a question the sources do not take a side on."""
        statements = _checked(
            _assessed(
                chain=tax_year.ChainPosition.RESTORABLE,
                method=LotMethod.LIFO,
                declared_method=None,
            )
        )
        year = _year(statements, 2027)

        assert year.liability.standing.verdict is tax_year.MethodVerdict.NO_SOURCE
        assert not [
            switch for switch in year.unsettled if "basis method governs" in switch.question
        ]

    def test_a_year_with_no_disposal_is_not_labelled_with_the_method_switch(self) -> None:
        """Nothing in a year of no operations depends on which lots would have been sold."""
        statements = _checked(_assessed(chain=tax_year.ChainPosition.RESTORABLE))

        quiet = [
            statement
            for statement in statements
            if statement.category == tax_years.INVESTMENT and not statement.charges
        ]

        assert [statement.tax_year for statement in quiet] == [2028]
        assert all(statement.unsettled == () for statement in quiet)


def _checked(
    outcome: tuple[tax_year.AnnualStatement, ...] | tax_year.TaxYearRefused,
) -> tuple[tax_year.AnnualStatement, ...]:
    assert isinstance(outcome, tuple), outcome
    return outcome
