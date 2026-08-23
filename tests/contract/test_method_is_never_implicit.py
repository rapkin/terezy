"""FR-024: an unlabelled liability is unrepresentable, not merely discouraged.

The law supports at least two readings of which basis method governs a self-declaring
individual, they give **different numbers** on the same trades, and nothing settles which. A
single figure called "the tax you would owe" would therefore be more confident than its
inputs, where the input is an unanswered legal question.

So the claim under test is about the **types**, not about a particular run: no record this
feature emits can be built holding a liability without the method that produced it, and no
name is a method until it has been checked against the closed set.
"""

from __future__ import annotations

import dataclasses
from typing import Final

import pytest

from terezy.core.errors import LedgerInvariantError
from terezy.core.ledger import engine, lots
from terezy.core.ledger.engine import LedgerState
from terezy.core.ledger.lots import LotMethod
from terezy.core.primitives.currency import Currency
from terezy.core.tax import year as tax_year
from tests import tax_years

pytestmark = pytest.mark.contract

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

    def test_a_statement_names_the_method_too(self) -> None:
        """A liability lifted out of its statement still says what produced it, and so does
        the statement it came from -- neither depends on the other being read."""
        statement_fields = {field.name for field in dataclasses.fields(tax_year.AnnualStatement)}

        assert "liability" in statement_fields
        assert "method" in LIABILITY_FIELDS


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
            method=LotMethod.FIFO,
            switches=tax_year.UnsettledPositions(chain=None, method=None),
        )

        assert isinstance(outcome, tax_year.MethodStandingUndeclared), outcome
        assert outcome.method is LotMethod.FIFO

    def test_a_standing_carries_its_own_citation(self) -> None:
        for standing in tax_years.STANDINGS.values():
            assert standing.provenance.sources
            assert standing.what_the_law_says


def _empty_ledger() -> LedgerState:
    return engine.opening(Currency.UAH, LotMethod.FIFO.value)


def _rules_without_standings() -> tax_year.AssessmentRules:
    return tax_years.rules(methods={})
