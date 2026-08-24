"""FR-024: an unlabelled liability is unrepresentable, not merely discouraged.

The law supports at least two readings of which basis method governs a self-declaring
individual, they give **different numbers** on the same trades, and nothing settles which. A
single figure called "the tax you would owe" would therefore be more confident than its
inputs, where the input is an unanswered legal question.

So the claims under test are about the **types**: no record this feature emits can be built
holding a liability without the method that produced it, no name is a method until it has been
checked against the closed set, and the method a figure is labelled with is read off the
ledger it was assessed from rather than passed in beside it -- which is how a label that
nothing checks is prevented rather than detected.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from pathlib import Path
from typing import Final

import pytest

from terezy.core.errors import LedgerInvariantError
from terezy.core.ledger import engine, lots
from terezy.core.ledger.engine import LedgerState
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.ledger.lots import LotMethod
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results import tax_year as settlement
from terezy.core.tax import flat_rate
from terezy.core.tax import year as tax_year
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxContext
from terezy.data.declarations import loader
from tests import tax_years

pytestmark = pytest.mark.contract

SHIPPED_TIMING: Final = Path(__file__).resolve().parents[2] / "data" / "tax" / "timing" / "ua.toml"

LIABILITY_FIELDS: Final = {field.name for field in dataclasses.fields(tax_year.AssessedLiability)}


class TestALiabilityCannotBeBuiltWithoutItsMethod:
    """The constructor is the guarantee: there is no argument order that omits the method."""

    def test_the_method_and_its_standing_are_required_arguments(self) -> None:
        assert "method" in LIABILITY_FIELDS
        assert "standing" in LIABILITY_FIELDS
        for name in ("method", "standing"):
            field = next(
                item for item in dataclasses.fields(tax_year.AssessedLiability) if item.name == name
            )
            assert field.default is dataclasses.MISSING
            assert field.default_factory is dataclasses.MISSING

    def test_omitting_the_method_is_a_construction_error(self) -> None:
        with pytest.raises(TypeError, match="method"):
            tax_year.AssessedLiability(  # type: ignore[call-arg]
                pit=None,  # type: ignore[arg-type]
                levy=None,  # type: ignore[arg-type]
                base=None,  # type: ignore[arg-type]
                rests_on=None,  # type: ignore[arg-type]
            )

    def test_there_is_no_field_holding_a_bare_total(self) -> None:
        """A ``total`` field would be readable without the method beside it.

        The sum exists as :func:`terezy.core.tax.year.liability_total`, which can only be
        reached through the record that names the method.
        """
        assert "total" not in LIABILITY_FIELDS
        assert callable(tax_year.liability_total)

    def test_the_only_route_from_a_statement_to_its_method_is_the_liability(self) -> None:
        """A statement carries no method of its own, and that is the point.

        A second copy would be a second answer, and the two would eventually disagree. So the
        method is reachable from a statement only through the record that also carries the
        standing behind it -- there is no field a reader can take the method from while
        leaving the citation behind.
        """
        statement_fields = {field.name for field in dataclasses.fields(tax_year.AnnualStatement)}

        assert "method" not in statement_fields
        assert "standing" not in statement_fields
        assert "liability" in statement_fields
        assert {"method", "standing"} <= LIABILITY_FIELDS


class TestTheMethodSetIsClosed:
    """FR-020: four methods, no default, and a name is checked before it is a method."""

    def test_the_enum_and_the_registry_agree_exactly(self) -> None:
        """Two spellings of one set would drift, so the test is that they cannot."""
        assert {method.value for method in LotMethod} == set(lots.SELECTION_FNS)

    def test_an_unrecognised_name_never_becomes_a_method(self) -> None:
        with pytest.raises(LedgerInvariantError, match="unknown lot consumption method"):
            lots.method_named("weighted_average")

    def test_every_declared_method_resolves_to_a_selection_function(self) -> None:
        for method in LotMethod:
            assert callable(lots.selection_for(method.value))
            assert lots.method_named(method.value) is method


class TestAStandingIsDeclaredRatherThanCompiledIn:
    """The legal standing of a method is data with a citation, not an attribute of the code."""

    def test_an_undeclared_standing_refuses_rather_than_defaulting(self) -> None:
        """A figure that cannot say what backs its method may not be produced at all."""
        outcome = tax_year.statements(
            _empty_ledger(),
            (),
            rules=_rules_without_standings(),
            tax_classes={},
            filing=tax_year.FilingDecisions(owner_id="owner-1", declared_at="test", by_year={}),
            switches=tax_year.UnsettledPositions(chain=None, method=None),
        )

        assert isinstance(outcome, tax_year.MethodStandingUndeclared), outcome
        assert outcome.method is LotMethod.FIFO

    def test_every_shipped_standing_carries_its_own_citation(self) -> None:
        """The claim is about the file that ships, not about the fixture beside these tests.

        A fixture's citations say only that the fixture has some. What has to be true is that
        the four findings the project actually loads each name a source and say what the law
        was found to say -- including the two whose finding is *no source prescribes this*,
        which is itself a claim about the law and uncheckable uncited.
        """
        declared = loader.timing_from_file(SHIPPED_TIMING)

        assert {standing.method for standing in declared.methods} == set(LotMethod)
        for standing in declared.methods:
            assert standing.provenance.sources, standing.method
            assert standing.what_the_law_says, standing.method


class TestAFigureIsLabelledWithTheMethodItsLedgerUsed:
    """FR-024 is about the figure, not about an argument -- so there is no argument.

    ``statements`` reads the method off ``LedgerState.consumption_method``, the field that
    actually decided which lots each disposal drew on. A second argument saying the same thing
    could say it differently, and did: the label was a stamp until this round.
    """

    def test_the_two_methods_would_genuinely_produce_different_tax(self) -> None:
        """The premise, worth pinning: a mislabel would be a wrong number, not a wrong word."""
        assert _gain_under(LotMethod.FIFO) == FIFO_GAIN
        assert _gain_under(LotMethod.LIFO) == LIFO_GAIN
        assert _gain_under(LotMethod.FIFO) != _gain_under(LotMethod.LIFO)

    @pytest.mark.parametrize("method", [LotMethod.FIFO, LotMethod.LIFO])
    def test_the_year_is_labelled_and_charged_by_the_ledgers_own_method(
        self, method: LotMethod
    ) -> None:
        """One fold, one method, one label -- and the base is that method's own gain.

        The label is not asserted against the argument that produced the ledger but against
        the hand-computed gain the two methods differ by, so a label that came from anywhere
        else would have to coincide with the arithmetic to pass.
        """
        assessed = _assess(_folded(method))

        assert isinstance(assessed, tuple), assessed
        year = next(item for item in assessed if item.tax_year == SOLD_ON.year)
        assert year.liability.method is method
        assert year.liability.base.amount == (FIFO_GAIN if method is LotMethod.FIFO else LIFO_GAIN)

    def test_settling_under_a_method_the_statements_were_not_assessed_on_is_refused(self) -> None:
        """``settle`` keeps its argument, and earns it.

        It folds the raw stream before it has looked at the statements, and must fold when
        there are none -- so there is nothing to derive from. It also catches what no type
        could: a caller can assemble one sequence out of two assessments under two methods.
        """
        assessed = _assess(_folded(LotMethod.FIFO))
        assert isinstance(assessed, tuple), assessed

        outcome = settlement.settle(
            _events(),
            assessed,
            owner_id=OWNER,
            base_currency=Currency.UAH,
            method=LotMethod.LIFO,
            horizon_end=date(2029, 1, 1),
        )

        assert isinstance(outcome, settlement.MethodDisagreesWithStatements), outcome
        assert outcome.settling_under is LotMethod.LIFO
        assert outcome.assessed_under == (LotMethod.FIFO,)


def _empty_ledger() -> LedgerState:
    return engine.opening(Currency.UAH, LotMethod.FIFO.value)


def _rules_without_standings() -> tax_year.AssessmentRules:
    return tax_years.rules(methods={})


# --- two lots at different prices, so the method changes the number -----------------------

OWNER: Final = "owner-1"
INSTRUMENT: Final = "fixture_two_lots"
SOLD_ON: Final = date(2027, 3, 5)
FIFO_GAIN: Final = 15_000.00
"""25 000.00 proceeds less the 10 000.00 the older lot cost."""

LIFO_GAIN: Final = 5_000.00
"""The same proceeds less the 20 000.00 the newer one cost."""


def _events() -> tuple[Event, ...]:
    source = prov.of([tax_years.FIXTURE_SOURCE])

    def event(sequence: int, on: date, kind: EventKind, amount: float, **extra: object) -> Event:
        return Event(
            sequence=sequence,
            occurred_on=on,
            kind=kind,
            amount=Money(amount, Currency.UAH, source),
            owner_id=OWNER,
            caused_by=CausationRef(
                kind=CausationKind.INSTRUMENT_TERM, id=f"{INSTRUMENT}:terms", detail="fixture"
            ),
            lot_ref=extra.get("lot_ref"),  # type: ignore[arg-type]
            quantity=extra.get("quantity"),  # type: ignore[arg-type]
            allocated_to=None,
            capacity_pool=None,
        )

    return (
        event(1, date(2026, 1, 5), EventKind.CASH_DEPOSIT, 100_000.00),
        event(
            2,
            date(2026, 1, 5),
            EventKind.PURCHASE,
            -10_000.00,
            lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id="lot-a"),
            quantity=100.0,
        ),
        event(
            3,
            date(2026, 2, 5),
            EventKind.PURCHASE,
            -20_000.00,
            lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id="lot-b"),
            quantity=100.0,
        ),
        event(
            4,
            SOLD_ON,
            EventKind.PRINCIPAL_REPAYMENT,
            25_000.00,
            lot_ref=LotRef(instrument_id=INSTRUMENT, lot_id=None),
            quantity=100.0,
        ),
    )


def _folded(method: LotMethod) -> LedgerState:
    return engine.fold(_events(), base_currency=Currency.UAH, consumption_method=method.value)


def _gain_under(method: LotMethod) -> float:
    return _folded(method).disposals[0].realised_gain_base_ccy.amount


def _assess(
    state: LedgerState,
) -> tuple[tax_year.AnnualStatement, ...] | tax_year.TaxYearRefused:
    charged = flat_rate.charge(
        _events()[3],
        tax_years.TAXED_CLASS,
        TaxContext(
            instrument_id=INSTRUMENT,
            taxable_event=TaxableEventKind.DISPOSAL_GAIN,
            taxable_base=state.disposals[0].realised_gain_base_ccy,
            charged_for_year=SOLD_ON.year,
        ),
    )
    assert isinstance(charged, TaxCharge), charged
    return tax_year.statements(
        state,
        (charged,),
        rules=tax_years.rules(),
        tax_classes=tax_years.TAX_PACK,
        filing=tax_years.filing(y2027=True),
        switches=tax_years.positions(),
    )
