"""What the owner is aiming at, and what the solver answers about it.

``SIMULATOR_SPEC.md`` §4.7, required test **J1**. A goal is any two of three variables --
a monthly contribution, a target sum, a target date -- and the tool solves the third. All
three declared is not an over-declaration: it is a different question, the feasibility one
(FR-018).

**Nothing here is a rate the tool chose.** A goal is evaluated against an explicitly stated
starting amount and an explicitly stated growth assumption, both carrying provenance, and
neither is declared on the goal itself. Pointing the assumption at the hurdle rate, or at
anything else, is the owner's declaration -- so a missing one is a typed refusal naming it
rather than a default (FR-012). There is no field either could hide in.

This module holds the **records**; ``core.goals.solve`` holds the arithmetic that fills them.
The split follows ``core.results.hurdle`` and ``core.results.rates``: what a result *is* can
be read without reading how it was computed, and the shape is what a later delivery surface
depends on.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money


@dataclass(frozen=True, slots=True)
class Goal:
    """One declared target: any two of contribution, sum and date -- or all three.

    Per-owner declared data (Principle VII, FR-022), beside the seed lots and on the private
    side of the same boundary.
    """

    owner_id: str
    """Whose goal this is. On every record, not only on the file that declared them."""

    id: str
    """Unique within the declaration. A duplicate is refused at load: two goals with one id
    cannot be told apart, so neither could be reported against."""

    currency: Currency
    """The denomination of the target, **stated rather than assumed** (FR-016).

    It must be the base currency in this feature, and a goal in any other is refused as *not
    yet modelled* -- naming the missing FX modelling, never the currency as invalid. §4.7's
    point stands that a dollar target and a hryvnia target are different goals under
    devaluation, so the field exists rather than hryvnia being implicit: the widening changes
    a validation rule, not the shape of the data. ``specs/features.toml`` records
    ``multi-currency-goals`` as owner-requested future work.
    """

    monthly_contribution: Money | None
    """What goes in each month, or ``None`` when this is the variable to solve for.

    ``None`` means **the owner declared nothing here**, which is why the field is nullable at
    all. It is never a zero standing in for an absent declaration: zero is itself a legitimate
    contribution -- a goal reached out of growth alone -- and conflating the two would make
    the solver unable to tell what it was asked.
    """

    target_sum: Money | None
    """How much is wanted, or ``None`` when that is the question."""

    target_date: date | None
    """By when, or ``None`` when that is the question."""
