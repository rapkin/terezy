"""What the money is for: a sum, a date and a contribution, of which any two fix the third.

``SIMULATOR_SPEC.md`` §4.7. The owner states two of the three and the tool solves the
remaining one against an explicitly stated growth assumption and an explicitly stated
starting amount -- neither of which is ever defaulted, because a goal evaluated against
a rate nobody chose is a number about nobody's plan.

**Why this is its own package and not part of ``core.decision``** (008 research.md D11).
``core.decision`` is reserved for candidate generation and strategy choice. A goal solver
is arithmetic over a contribution schedule: it knows nothing about which instrument the
money sits in, which route it took, or which allocation is better. Keeping the two apart
keeps that distinction legible -- a goal is the bar a later recommendation is measured
against, not the thing that does the measuring.

The conventions the arithmetic depends on travel in the result rather than living
implicitly in this code; why there is no root finder is argued in
:mod:`terezy.core.goals.solve`.
"""
