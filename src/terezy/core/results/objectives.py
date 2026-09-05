"""The objectives a dominance pass runs over: what the owner compares on, and how close is close.

019 FR-001 to FR-005, FR-011. **Which criteria he compares on, in which direction, at which
indifference band, is data**; the *criteria themselves* are closed in source, and FR-003 says so
plainly rather than leaving it to be discovered. A criterion is a reader over a computed figure,
so a new criterion is a new figure or a new way of reading one, and both are code.

**No weight, no score, no coefficient, no priority.** A weighted sum of two objectives is the
non-standard composite required test B12 forbids driving the primary ordering, and a partial
order is what makes this step need no calibration at all.

No citation keys and no sources: how much precision the owner believes his inputs support is a
statement about him rather than an observation of the world (FR-004).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final, Literal

from terezy.core.primitives.money import Money


class Criterion(Enum):
    """What a dominance pass may compare on. A **closed** set (FR-002, FR-003).

    Widening it is a reviewed source change rather than a data change, and that is the one place
    this feature is not data-only: each member names a figure ``TupleOutcome`` already carries,
    so a member nothing can read is a member no run constructs.
    """

    MONEY_AT_THE_ENDPOINT = "money_at_the_endpoint"
    """``TupleOutcome.reaches`` -- what actually arrives somewhere the owner can spend it."""

    ALL_MONEY_BACK_ON = "all_money_back_on"
    """The date of the last arrival: when every hryvnia of it is back at an endpoint."""


FigureKind = Literal["money", "date"]
"""What sort of figure a criterion reads. Decides which band shapes are legal on it and, in the
pass, which closeness rule applies -- a date's slack is zero and a money figure's is not."""

READS: Final[dict[Criterion, FigureKind]] = {
    Criterion.MONEY_AT_THE_ENDPOINT: "money",
    Criterion.ALL_MONEY_BACK_ON: "date",
}
"""Which kind of figure each criterion reads, in one place.

The loader checks a band's shape against it and the pass reads the figure through it. Two copies
of this mapping would let a fraction band reach a date criterion in the pass after the loader
had refused it, which is the shape of disagreement one table exists to prevent.
"""


class ObjectiveDirection(Enum):
    """More is better, or less is better. Exactly two members and no per-criterion synonym.

    *Sooner is better* on a date is :attr:`LESS_IS_BETTER`. A third token meaning the same thing
    is a synonym inside a closed set, which is how two spellings of one rule come to be handled
    differently.

    Named ``ObjectiveDirection`` because ``core.results.answer`` already declares a ``Direction``
    over an unrelated closed set, and an import binding one of the two silently is worse than a
    collision that fails.
    """

    MORE_IS_BETTER = "more_is_better"
    LESS_IS_BETTER = "less_is_better"


@dataclass(frozen=True, slots=True, kw_only=True)
class AbsoluteBand:
    """A width stated as an amount of money, in its own currency (FR-011d)."""

    amount: Money


@dataclass(frozen=True, slots=True, kw_only=True)
class FractionOfTheQuestionAmount:
    """A width stated as a fraction of the amount the **question** states (FR-011d).

    Of the question's amount and never of a candidate's own figure: a fraction of each
    candidate's figure is a different width for *A* against *B* than for *B* against *A*, and
    FR-011's relation would stop being symmetric. It resolves in the pass, because which
    currency a pair is compared in is the spendable endpoint's and unknown to a declaration.
    """

    proportion: float
    """Named ``proportion`` rather than ``fraction``: 002's cost records use ``fraction`` for
    what a route charged as a share of what it carried, and two compliance scans read that name
    as *this figure is a price*. An indifference width is not a price."""


@dataclass(frozen=True, slots=True, kw_only=True)
class DaysBand:
    """A width stated as a whole number of days. A date criterion's only shape.

    There is no relative form: a percentage of a date means nothing.
    """

    days: int


Band = AbsoluteBand | FractionOfTheQuestionAmount | DaysBand
"""One objective's indifference band. Declared, with no default, and refused at load when it is
negative, zero, non-finite, or a shape its criterion does not take (FR-011b, FR-011d)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Objective:
    """One criterion, one direction, one band. Carries no weight (FR-005)."""

    criterion: Criterion
    direction: ObjectiveDirection
    band: Band


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectiveSet:
    """The declared collection one dominance pass runs over, identified and digested.

    Non-empty, and its length is the *p* of FR-011c's acyclicity floor. The sequence is the
    declared order and nothing reads it as a ranking: an order that meant something would be the
    priority FR-005 forbids.
    """

    id: str
    owner_id: str
    objectives: tuple[Objective, ...]


__all__ = [
    "READS",
    "AbsoluteBand",
    "Band",
    "Criterion",
    "DaysBand",
    "FigureKind",
    "FractionOfTheQuestionAmount",
    "Objective",
    "ObjectiveDirection",
    "ObjectiveSet",
]
