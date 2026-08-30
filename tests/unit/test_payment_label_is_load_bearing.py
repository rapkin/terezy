"""SC-005: relabelling one payment moves the tax total by exactly the hand-computed amount.

FR-010's argument, and it is about **when a defect becomes visible** rather than about tax.
For ОВДП both income kinds are exempt, so a payment mislabelled as a coupon rather than a
repayment of principal changes no figure on the instruments the enumerated form was built
for. That is luck rather than design, and it is exactly the condition under which a defect
ships: the first taxable enumerated instrument makes every earlier mislabelling visible at
once. So the label is proved load-bearing here, on a fixture whose two income kinds carry
different declared rates -- and the second half of the test runs the same relabelling on the
exempt instrument and watches nothing happen, which is what makes the first half necessary
rather than decorative.

The arithmetic, on `enumerated_taxable_x` -- 10 units bought on 2026-01-05 at 1 000.00, the
declared face, so there is no premium and nothing but the labels moves:

    as declared
      2026-07-05  coupon               10 x    50.00 =     500.00   at 8%  ->    40.00
      2026-12-05  coupon               10 x    50.00 =     500.00   at 8%  ->    40.00
      2026-12-05  principal            10 x 1 000.00 =  10 000.00
                  realised gain        10 000.00 - 10 000.00 = 0.00  at 15% ->     0.00
                                                                  total       80.00

    with the second coupon relabelled a repayment of principal
      the payment is unchanged -- 500.00 on 2026-12-05 -- and what changes is which
      vocabulary it belongs to. It stops being coupon income taxed at 8% (-40.00) and
      becomes part of a disposal: 10 500.00 of proceeds against the whole 10 000.00 basis,
      realising 500.00 taxed at 15% (+75.00).
                                                                  total      115.00

    the difference = 115.00 - 80.00 = 35.00
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from terezy.core.instruments.interface import (
    Assumptions,
    DateRange,
    EnumeratedTerms,
    Holding,
    InstrumentDeclaration,
    PaymentKind,
)
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import project
from terezy.core.results.project import Projection
from terezy.data.declarations import resolver
from tests import tuple_registries as fixtures

pytestmark = pytest.mark.worked_example

DECLARATIONS = resolver.from_data_root(fixtures.DATA_ROOT)
TAXABLE = "enumerated_taxable_x"
EXEMPT = "ovdp_enumerated_a"

AS_DECLARED = 40.0 + 40.0
RELABELLED = 40.0 + 75.0
DIFFERENCE = 35.0


def _relabelled(declared: InstrumentDeclaration, index: int) -> InstrumentDeclaration:
    """The same declaration with one payment's kind changed and nothing else.

    ``replace`` on the frozen records rather than a second file, so a reader can see that
    the *only* difference between the two runs is a label.
    """
    terms = declared.terms
    assert isinstance(terms, EnumeratedTerms)
    payments = list(terms.payments)
    payments[index] = replace(payments[index], pays=PaymentKind.PRINCIPAL_REPAYMENT)
    return replace(declared, terms=replace(terms, payments=tuple(payments)))


def _projected(declared: InstrumentDeclaration, *, quantity: float = 10.0) -> Projection:
    outcome = project.project(
        declared,
        Holding(
            owner_id="owner-1",
            instrument_id=declared.id,
            quantity=quantity,
            purchased_on=_covers_from(declared),
            cost=Money(1000.0 * quantity, Currency.UAH, prov.EMPTY),
        ),
        DateRange(start=_covers_from(declared), end=fixtures.HORIZON_END),
        Assumptions(consumption_method="fifo", coupon_policy="hold_cash"),
        tax_classes=DECLARATIONS.tax_classes,
    )
    assert isinstance(outcome, Projection), outcome
    return outcome


def _covers_from(declared: InstrumentDeclaration) -> date:
    terms = declared.terms
    assert isinstance(terms, EnumeratedTerms)
    return terms.covers_from


class TestOnAnInstrumentWhoseTwoKindsAreTaxedDifferently:
    def test_the_declared_labels_produce_the_hand_computed_total(self) -> None:
        assert is_close(
            _projected(DECLARATIONS.instruments[TAXABLE]).hurdle.total_tax.amount, AS_DECLARED
        )

    def test_relabelling_the_second_coupon_produces_the_other_hand_computed_total(self) -> None:
        relabelled = _relabelled(DECLARATIONS.instruments[TAXABLE], 1)
        assert is_close(_projected(relabelled).hurdle.total_tax.amount, RELABELLED)

    def test_the_difference_is_exactly_the_hand_computed_one(self) -> None:
        declared = _projected(DECLARATIONS.instruments[TAXABLE]).hurdle.total_tax.amount
        relabelled = _projected(
            _relabelled(DECLARATIONS.instruments[TAXABLE], 1)
        ).hurdle.total_tax.amount
        assert is_close(relabelled - declared, DIFFERENCE)

    def test_the_two_classes_really_do_carry_different_rates(self) -> None:
        """Or the assertion above would pass for the wrong reason -- a label that moved no
        figure because the two rates happened to agree would look exactly like a label that
        was never read."""
        coupon = DECLARATIONS.tax_classes["synthetic_enumerated_coupon"].rates[0]
        disposal = DECLARATIONS.tax_classes["synthetic_enumerated_disposal"].rates[0]
        assert (coupon.pit_rate, coupon.levy_rate) != (disposal.pit_rate, disposal.levy_rate)

    def test_the_money_that_moved_is_unchanged_and_only_its_vocabulary_differs(self) -> None:
        """The relabelled payment is the same amount on the same date. What changed is what
        the ledger records as having moved and which income kind the tax layer assesses --
        the two vocabularies one declared label settles (FR-007)."""
        declared = _projected(DECLARATIONS.instruments[TAXABLE]).schedule.rows
        relabelled = _projected(_relabelled(DECLARATIONS.instruments[TAXABLE], 1)).schedule.rows
        assert [(row.occurred_on, row.gross.amount) for row in declared] == [
            (row.occurred_on, row.gross.amount) for row in relabelled
        ]
        assert [row.kind for row in declared] != [row.kind for row in relabelled]


class TestOnAnInstrumentExemptOnBothSides:
    """The half that proves the half above was necessary."""

    def test_the_declared_labels_produce_no_tax(self) -> None:
        assert _projected(DECLARATIONS.instruments[EXEMPT]).hurdle.total_tax.amount == 0.0

    def test_relabelling_a_payment_changes_nothing_at_all(self) -> None:
        """This is the trap FR-010 names: getting the label wrong on the instruments that
        motivate the enumerated form is currently **free**, so a mislabelling ships
        invisibly and the first taxable instrument makes every earlier one visible at once."""
        relabelled = _relabelled(DECLARATIONS.instruments[EXEMPT], 0)
        assert _projected(relabelled).hurdle.total_tax.amount == 0.0

    def test_and_the_charges_still_cite_the_exemption_on_both_sides(self) -> None:
        """Zero because zeroes were recorded and added up, not because nothing was."""
        for declared in (
            DECLARATIONS.instruments[EXEMPT],
            _relabelled(DECLARATIONS.instruments[EXEMPT], 0),
        ):
            charges = _projected(declared).charges
            assert charges
            assert {charge.tax_class_id for charge in charges} == {"ua_government_bond"}
