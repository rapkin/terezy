"""The declaration is his: SC-001a, asserted by value against the shipped file.

Every other criterion in feature 019 passes over *an* objective set -- an implementer can satisfy
all of them with criteria and bands nobody chose. The one thing no other assertion notices is the
owner's own answers never reaching ``data/objectives/``, so this reads the shipped declaration
and checks it against what he said on 2026-09-03
(``specs/decisions/2026-09-03-clarify-019.toml``).

**The money band is a fraction of 0.0001 and not 0.01.** He was asked for a hryvnia figure and
answered *0.01 %*; stored as a percent-looking ``0.01`` it would be a 500 UAH band on his 50 000,
a hundred times what he said, and it would swallow every gap in the registry. The arithmetic that
converts one to the other is checked in below beside the assertion.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from terezy.core.primitives.tolerance import is_close
from terezy.core.results.objectives import (
    Criterion,
    DaysBand,
    FractionOfTheQuestionAmount,
    ObjectiveDirection,
)
from terezy.data.declarations import loader
from tests import answer_registries as fixtures

pytestmark = pytest.mark.worked_example

SHIPPED: Path = fixtures.SHIPPED_ROOT / "objectives" / "owner-001.toml"

PERCENT_HE_ANSWERED = 0.01
"""CL-2's money half, in his own words: 0.01 %."""

AS_A_FRACTION = PERCENT_HE_ANSWERED / 100.0
"""0.01 / 100 = 0.0001. The division is the whole of the trap, so it is written out."""

HIS_AMOUNT = 50_000.0
"""What his question states leaves ``salary_uah``."""

RESOLVES_TO = 5.00
"""0.0001 x 50 000 = 5.00 UAH. Narrower than any gap the money objective separates on the
shipped registry, which is the honest thing to know about his band: it is a floor under a later
registry whose candidates sit closer together, not a correction to this one."""


def test_the_shipped_set_holds_his_two_criteria_in_his_two_directions() -> None:
    declared = loader.objectives_from_file(SHIPPED)
    assert declared.id == "money-and-when"
    assert [(objective.criterion, objective.direction) for objective in declared.objectives] == [
        (Criterion.MONEY_AT_THE_ENDPOINT, ObjectiveDirection.MORE_IS_BETTER),
        (Criterion.ALL_MONEY_BACK_ON, ObjectiveDirection.LESS_IS_BETTER),
    ]


def test_the_money_band_is_the_fraction_he_answered_and_not_the_percent_figure() -> None:
    band = loader.objectives_from_file(SHIPPED).objectives[0].band
    assert isinstance(band, FractionOfTheQuestionAmount)
    assert is_close(band.proportion, AS_A_FRACTION)
    assert is_close(band.proportion, 0.0001)
    assert is_close(band.proportion * HIS_AMOUNT, RESOLVES_TO)


def test_the_date_band_is_seven_days() -> None:
    band = loader.objectives_from_file(SHIPPED).objectives[1].band
    assert band == DaysBand(days=7)


def test_his_question_is_answered_under_that_set() -> None:
    assert fixtures.owners_question().objective_set_id == "money-and-when"


def test_no_objective_carries_a_weight() -> None:
    """FR-005, read off the declaration rather than off the schema: a set that grew a weight
    would be scoring rather than comparing, and a partial order needs no calibration."""
    declared = loader.objectives_from_file(SHIPPED)
    fields = {name for objective in declared.objectives for name in objective.__slots__}
    assert fields == {"criterion", "direction", "band"}
