"""**The** rule for putting a number on a diagram. There is one, and this is it.

FR-022, added on external review. The review found a gap that had been invisible because it
was a gap in a *definition* rather than in behaviour: results carry ``float``, this project's
canonical float form is hexadecimal (``METHODOLOGY`` §12.2, chosen so determinism means
bit-identity), and no human-readable decimal rendering rule existed anywhere. So SC-006's
"every figure on a diagram equals the input's figure" compared diagram text against a form
nobody had defined.

**Modelled on the single project tolerance** (``core.primitives.tolerance``, Principle IV):
defined in exactly one place, imported everywhere, and a second one is a **defect** rather
than a preference. Each local rendering rule is defensible on its own and invisible in
aggregate; twenty of them and no reader can tell whether two diagrams disagree about a figure
or about a format. Having exactly one means changing it is a visible, reviewable act.

**This rule ROUNDS, and the diagram is therefore NOT the audit trail.**

Say that plainly, because the next contributor will otherwise reach for a third decimal at
one call site and call it a fix. FR-008 forbids the renderer to compute, derive, aggregate or
*round differently* -- and permits exactly this one transformation, once, here. A figure on a
diagram is the input's figure to two decimal places; the figure itself is in the result
record, in the golden artifact, and in ``float.hex()`` where bit-identity is what is being
asserted. If a decision turns on the third decimal, the diagram is the wrong instrument and
no amount of precision here would make it the right one.

**Two decimals** is the implementer's choice the specification explicitly leaves open. Its
singularity and its documentation are what FR-022 requires, and both are enforced:
``tests/contract/test_diagram_one_number_rule.py`` greps the whole package for a second rule
and proves the grep can fail.
"""

from __future__ import annotations

from typing import Final

from terezy.core.primitives.money import Money

DECIMAL_PLACES: Final = 2
"""How many decimal places a figure gets on a diagram.

Two, because a diagram is read at a glance and because every figure this project puts on one
is either a percentage of a cost or an amount of money in its smallest ordinary unit -- a
kopiyka, a cent. Not a tolerance and not a precision claim: see the module docstring for what
this rule does *not* promise.
"""


def _fixed(value: float) -> str:
    """A ``float`` at :data:`DECIMAL_PLACES` decimals. The project's only diagram format.

    Every figure on every diagram passes through this one line, which is what makes "the
    diagram's figures all come from one rule" a checkable claim rather than a convention.
    Python's format rounds half to even on the *double*, so ``0.125`` renders ``0.12`` and
    ``0.135`` -- which is really ``0.13500000000000001`` -- renders ``0.14``. That is the
    rounding being visible, and it is asserted rather than left to be discovered.

    A rounded-away negative keeps its sign (``-0.00``). Normalising it would be the renderer
    deciding that a small negative amount is really a zero, and a negative arriving amount is
    a real fact this project reports rather than clamps (predecessor defect B13).
    """
    return f"{value:.{DECIMAL_PLACES}f}"


def percent(fraction: float) -> str:
    """A fraction rendered as a percentage: ``0.0667`` becomes ``6.67%``.

    A **fraction** in, because that is what every rate in this engine is: ``0.01`` is one
    percent, and percent lives only in declaration files where a ``_pct`` suffix names it
    (``METHODOLOGY`` §9). The multiplication by 100 is a change of unit, not a computation --
    it is part of this rule, and it is the only place in the package it happens.

    May exceed 100% (a small amount with a fixed fee) and may be negative (a channel trading
    below its reference). Neither is capped: a cap here would be a silent clamp in a new hat.
    """
    return f"{_fixed(fraction * 100.0)}%"


def amount(value: Money) -> str:
    """An amount rendered with its currency **code**: ``1234.57 UAH``.

    The code and never a symbol, for the reason ``core.primitives.money`` exists: UAH and USD
    must never look interchangeable on a page any more than they may be added in a sum. The
    currency is the amount's own, so a display-currency switch cannot reach in here and change
    what a diagram says a leg charged.
    """
    return f"{_fixed(value.amount)} {value.currency.value}"
