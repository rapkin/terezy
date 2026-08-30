"""Narrowing helpers for tests that are about the **generative** form specifically.

A declaration's terms are one of two records and a schedule row's conventions statement is
one of two records (013 FR-002, FR-016). Most of this suite is about behaviour that does not
care which; the tests that import this module are about a bond declared by its rate, its
periodicity and its issue date, and they say so here rather than by asserting on a field
that may not exist.

A raise rather than a skip or a cast: a test reaching for an issue date on a declaration
that has none has been given the wrong fixture, and the message should say so at the line
that asked.

Not a test module -- ``pytest`` collects only ``test_*.py``, so this file is imported,
never run.
"""

from __future__ import annotations

from terezy.core.instruments.interface import BondTerms, InstrumentDeclaration
from terezy.core.primitives.conventions import AmountsAsDeclared, ConventionsApplied


def contractual(declaration: InstrumentDeclaration) -> BondTerms:
    """The declaration's terms, as the closed form this test is about."""
    terms = declaration.terms
    if not isinstance(terms, BondTerms):
        raise TypeError(
            f"{declaration.id!r} is not declared in the generative form, so it states no "
            "issue date, coupon rate, periodicity or business-day rule. This test is about "
            "an instrument that does."
        )
    return terms


def generated(statement: ConventionsApplied | AmountsAsDeclared) -> ConventionsApplied:
    """A row's conventions statement, as the three-convention one this test is about."""
    if not isinstance(statement, ConventionsApplied):
        raise TypeError(
            "this row states that its amounts were declared rather than computed from a "
            "periodicity, a day count and a business-day rule, so it names only the "
            "convention that annualises. This test is about a row that names three."
        )
    return statement
