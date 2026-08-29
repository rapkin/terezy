"""A payment kind settles two vocabularies at once, from one declared label (FR-007).

The trap this file exists for is FR-010's: for ОВДП both income kinds are exempt, so a
payment whose ledger movement and whose taxable kind disagreed would change **no figure
today**. One mapping rather than two is what makes the disagreement unrepresentable rather
than merely unlikely.
"""

from __future__ import annotations

from terezy.core.instruments.interface import PAYMENT_KINDS, PaymentKind
from terezy.core.ledger.events import EventKind
from terezy.core.tax.interface import TaxableEventKind


class TestTheSetIsClosedAndSmall:
    def test_it_covers_at_least_a_coupon_and_a_principal_repayment(self) -> None:
        """FR-007's stated minimum. More members are permitted; fewer are not."""
        assert {PaymentKind.COUPON, PaymentKind.PRINCIPAL_REPAYMENT} <= set(PaymentKind)

    def test_every_member_is_declarable_by_its_own_name(self) -> None:
        """The ``value`` strings are the data contract a declaration file writes."""
        for kind in PaymentKind:
            assert PaymentKind(kind.value) is kind


class TestOneLabelSettlesBothVocabularies:
    def test_every_kind_maps_to_exactly_one_pair(self) -> None:
        assert set(PAYMENT_KINDS) == set(PaymentKind)

    def test_a_coupon_moves_cash_and_is_assessed_as_coupon_income(self) -> None:
        assert PAYMENT_KINDS[PaymentKind.COUPON] == (EventKind.COUPON, TaxableEventKind.COUPON)

    def test_a_principal_repayment_is_a_disposal_on_both_sides(self) -> None:
        """A redemption consumes basis and realises a gain; it is not a cash receipt.

        Taxing the amount returned instead would tax the owner's own money back, which is
        the reading ``core.results.project._taxable_kind`` already refuses for the
        generative form.
        """
        assert PAYMENT_KINDS[PaymentKind.PRINCIPAL_REPAYMENT] == (
            EventKind.PRINCIPAL_REPAYMENT,
            TaxableEventKind.DISPOSAL_GAIN,
        )

    def test_the_two_vocabularies_cannot_disagree_because_there_is_one_mapping(self) -> None:
        """The assertion is about the *shape*: one lookup, not two that could drift.

        Two mappings would satisfy every test above and still be able to disagree the day
        a third kind is added to one of them.
        """
        movements = {kind: pair[0] for kind, pair in PAYMENT_KINDS.items()}
        assessed = {kind: pair[1] for kind, pair in PAYMENT_KINDS.items()}
        assert set(movements) == set(assessed) == set(PaymentKind)
