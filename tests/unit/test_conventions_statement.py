"""What a schedule row is allowed to say about the conventions that shaped it (FR-016).

Two statements, and the requirement is that a row can make **either** one without making
the other. FR-016 separates the halves deliberately: a row that said *"no day count was
applied"* would be false the moment a yield is emitted from the same projection, and a row
that named all three conventions would claim two that never ran.
"""

from __future__ import annotations

from terezy.core.primitives.conventions import AmountsAsDeclared, ConventionsApplied

DECLARED = AmountsAsDeclared(day_count="act/365")
GENERATED = ConventionsApplied(
    periodicity="semiannual", day_count="act/365", business_day_rule="following"
)


class TestTheStatementAScheduleOfDeclaredPaymentsMakes:
    def test_it_names_the_day_count_that_annualises(self) -> None:
        """FR-003a's convention of computation, on the row that annualises by it."""
        assert DECLARED.day_count == "act/365"

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
        assert (GENERATED.periodicity, GENERATED.day_count, GENERATED.business_day_rule) == (
            "semiannual",
            "act/365",
            "following",
        )

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
