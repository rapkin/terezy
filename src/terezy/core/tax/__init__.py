"""The tax engine and the ``TaxRule`` plugin interface.

Jurisdiction rules are declarative, versioned, sourced data under ``data/tax/``
with dated rate schedules -- never rates hardcoded in the simulation path
(REWRITE_BRIEF.md §5.3).

Principle I is at its strictest here: no legal or tax value may originate from an
implementer's or an agent's memory. Every value carries ``source``,
``retrieved_on`` and ``verified_on``, an empty ``verified_on`` marks the figure, and
the mark propagates to everything derived from it.
"""
