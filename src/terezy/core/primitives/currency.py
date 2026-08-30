"""The closed set of currencies. Nothing here knows a rate.

Enumerated rather than a free string so that a typo is a load-time failure instead of a
silently distinct currency that never matches anything (data-model.md, FR-016). A
misspelled ``"UHA"`` in a declaration file cannot become a fourth currency that quietly
never equals anything else; it fails where it was written.

This enum names the *denomination* only. It is deliberately not one of the currency
roles of constitution Principle VI: a role is a property of the scenario, not of the
amount, and encoding one here would be the first step towards exactly the conflation
that principle forbids.

Feature 001 uses only ``UAH``. ``USD`` exists from the first commit because the
prohibition on mixing currencies is untestable with one currency, and C5 is a
compliance test for the constitution.
"""

from __future__ import annotations

from enum import Enum


class Currency(Enum):
    """A currency an amount may be denominated in.

    A plain ``Enum`` and deliberately not a ``str`` subclass: a string-valued enum
    compares equal to a bare string, which would let ``"UAH"`` slip into a position
    that should require a ``Currency`` and defeat the point of enumerating at all.

    ``value`` is the stable identifier used in canonical form and in declaration files;
    it is part of the data contract and may not be renamed casually.
    """

    UAH = "UAH"
    """Ukrainian hryvnia. The base currency, and the currency tax is assessed in."""

    USD = "USD"
    """United States dollar. Present so that currency safety is testable."""
