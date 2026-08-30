"""What a schedule row is allowed to say about the conventions that shaped it (FR-016).

Two statements, and the requirement is that a row can make **either** one without making
the other. FR-016 separates the halves deliberately: a row that said *"no day count was
applied"* would be false the moment a yield is emitted from the same projection, and a row
that named all three conventions would claim two that never ran.
"""

from __future__ import annotations

from functools import cache

from terezy.core.instruments.interface import Assumptions, DateRange, Holding
from terezy.core.primitives import conventions
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.conventions import AmountsAsDeclared, ConventionsApplied
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results import canonical, project
from terezy.core.results.project import Projection
from terezy.core.results.schedule import CashFlowRow
from terezy.data.declarations import resolver
from tests import tuple_registries as fixtures

DECLARED_TAG = "declared"
"""How the canonical form marks a schedule whose amounts were declared. See the test at
the foot of this file for why the string matters."""

DECLARED = AmountsAsDeclared(day_count="act/365")
GENERATED = ConventionsApplied(
    periodicity="semiannual", day_count="act/365", business_day_rule="following"
)


class TestTheStatementAScheduleOfDeclaredPaymentsMakes:
    def test_it_names_the_day_count_that_annualises(self) -> None:
        """FR-003a's convention of computation, carried on to the row that annualises by it.

        ⚙ Asserted through a **projection** rather than on the record this file constructs
        two lines above, which is what it used to do: a test that builds a value and reads
        the field back passes with the feature deleted.
        """
        row = _declared_row()
        assert isinstance(row.conventions, AmountsAsDeclared)
        assert row.conventions.day_count == "act/365"

    def test_it_denies_that_a_periodicity_generated_the_date(self) -> None:
        assert "periodicity" in DECLARED.reason

    def test_it_denies_that_a_business_day_rule_moved_the_date(self) -> None:
        assert "business-day rule" in DECLARED.reason

    def test_it_denies_that_a_day_count_sized_the_amount(self) -> None:
        """The half a reader is most likely to assume, since the row names a day count."""
        assert "sized" in DECLARED.reason
        assert "declared" in DECLARED.reason

    def test_it_names_no_periodicity_and_no_business_day_rule(self) -> None:
        """FR-016: it must not name one. The record has nowhere to put one."""
        assert not hasattr(DECLARED, "periodicity")
        assert not hasattr(DECLARED, "business_day_rule")


class TestTheStatementAGeneratedScheduleMakes:
    def test_it_names_all_three(self) -> None:
        """Read off a projection, for the reason the declared case is: this file builds
        ``GENERATED`` itself, so reading its fields back proves nothing about the engine."""
        row = _generated_row()
        assert isinstance(row.conventions, ConventionsApplied)
        assert (row.conventions.periodicity, row.conventions.day_count) == (
            "semiannual",
            "act/365",
        )
        assert row.conventions.business_day_rule == "following"

    def test_neither_record_can_hold_the_other_s_claim(self) -> None:
        """A row carries one statement or the other, and no field distinguishes them.

        Typed as a union rather than as one record with a nullable periodicity, because
        ``row.conventions.periodicity is None`` is a form test spelled without the form's
        name -- exactly the spelling SC-003 records its scan as unable to catch. The
        assertion is on the *fields*: a shape that could express both would be that
        nullable record wearing two names.
        """
        assert not hasattr(GENERATED, "reason")
        assert not hasattr(DECLARED, "periodicity")


def test_no_periodicity_may_be_spelled_like_the_declared_tag() -> None:
    """The whole of what keeps the two canonical renderings apart (013 FR-016).

    ``of_conventions`` renders three entries for either statement, so arity separates
    nothing: a generated schedule opens with its periodicity and a listed one opens with the
    tag. If a convention named ``declared`` were ever implemented, the two would collide and
    a digest would report a computed schedule and a declared one as the same result.

    ⚙ Written after a review found three artefacts arguing the separation from an arity that
    had stopped being true in the same branch. The property was real; nothing checked it.
    """
    assert DECLARED_TAG not in conventions.PERIODICITY_FNS


def test_the_two_renderings_open_with_different_things() -> None:
    assert canonical.of_conventions(DECLARED)[0] == DECLARED_TAG
    assert canonical.of_conventions(GENERATED)[0] in conventions.PERIODICITY_FNS
    assert len(canonical.of_conventions(DECLARED)) == len(canonical.of_conventions(GENERATED))


@cache
def _declared_row() -> CashFlowRow:
    """A row of a real projection of a declaration whose amounts are declared."""
    return _rows("ovdp_enumerated_mirror")[1]


@cache
def _generated_row() -> CashFlowRow:
    """A row of a real projection of a bond declared by its terms."""
    return _rows("ovdp_synthetic_a")[1]


def _rows(instrument_id: str) -> tuple[CashFlowRow, ...]:
    declarations = resolver.from_data_root(fixtures.DATA_ROOT)
    declared = declarations.instruments[instrument_id]
    outcome = project.project(
        declared,
        Holding(
            owner_id="owner-1",
            instrument_id=instrument_id,
            quantity=10.0,
            purchased_on=fixtures.ISSUE_DATE,
            cost=Money(10_000.0, Currency.UAH, prov.EMPTY),
        ),
        DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END),
        Assumptions(consumption_method="fifo", coupon_policy="hold_cash"),
        tax_classes=declarations.tax_classes,
    )
    assert isinstance(outcome, Projection), outcome
    return outcome.schedule.rows
