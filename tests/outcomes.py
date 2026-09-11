"""``evaluate`` read for its outcome alone, for the suites that predate the projection.

Not a test module -- ``pytest`` collects only ``test_*.py``, so this file is imported, never
run.

Since 027 the join returns its projection beside the outcome and ``compare`` discards the half
it does not want through ``outcome_of``. The suites below were written against the outcome and
are still about the outcome; routing them through the same accessor keeps them saying what they
say. What the projection half carries is asserted where it belongs --
``tests/unit/test_the_served_projection.py`` and
``tests/contract/test_the_card_accounts_for_what_came_back.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from terezy.core.decision.tuple_outcome import evaluate as _evaluate
from terezy.core.decision.tuple_outcome import outcome_of

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from datetime import date

    from terezy.core.decision.tuple_outcome import Registries
    from terezy.core.instruments.interface import DateRange
    from terezy.core.primitives.money import Money
    from terezy.core.results.tuple import (
        ContinuationAssumption,
        Tuple,
        TupleOutcome,
        TupleRefused,
    )


def evaluated_outcome(
    tuple_: Tuple,
    *,
    amount: Money,
    horizon: DateRange,
    as_of: date,
    continuation: ContinuationAssumption,
    registries: Registries,
) -> TupleOutcome | TupleRefused:
    """One tuple's outcome, or its refusal. The projection is discarded, as ``compare`` does."""
    return outcome_of(
        _evaluate(
            tuple_,
            amount=amount,
            horizon=horizon,
            as_of=as_of,
            continuation=continuation,
            registries=registries,
        )
    )
