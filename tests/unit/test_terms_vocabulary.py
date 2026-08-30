"""A payment kind settles two vocabularies at once, from one declared label (FR-007).

The trap this file exists for is FR-010's: for ОВДП both income kinds are exempt, so a
payment whose ledger movement and whose taxable kind disagreed would change **no figure
today**. One mapping rather than two is what makes the disagreement unrepresentable rather
than merely unlikely.
"""

from __future__ import annotations

from terezy.core.instruments import interface
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

    def test_each_label_settles_both_halves_in_one_lookup(self) -> None:
        """The shape, not the contents: one entry carries both, so a kind cannot be present
        in one vocabulary and missing from the other.

        ⚙ This used to build two comprehensions over ``PAYMENT_KINDS.items()`` and compare
        their key sets, which is true of any mapping whatsoever and passed for every value.
        What is actually checkable is the arity of an entry -- two mappings would be two
        module attributes, and there is one.
        """
        both_halves = 2
        assert all(len(pair) == both_halves for pair in PAYMENT_KINDS.values())
        assert [name for name in dir(interface) if name.endswith("_KINDS")] == ["PAYMENT_KINDS"], (
            "a second mapping would be a second module attribute, and two mappings can "
            "disagree about a label the day a third payment kind is added to one of them"
        )
