"""SC-012: with every inference unverified, every figure derived from it is marked.

Principle I, and the reason FR-020 introduces **no new kind of mark**: an inference is an
unverified value, and the propagation that already exists carries it. What this feature adds
is that a transcribed schedule is unverified *by construction* -- the four things it infers
are nobody's statement, so an empty ``verified_on`` is their expected first state rather
than an oversight somebody will get round to.

The assertion runs both ways. Every figure carries the mark while the sources are
unverified, and **no derived figure appears unmarked** -- because "some of them are marked"
is what a transform that drops the mark on one path looks like from the outside.
"""

from __future__ import annotations

from dataclasses import replace

from terezy.core.instruments.interface import Assumptions, DateRange, EnumeratedTerms, Holding
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results import project
from terezy.core.results.project import Projection
from terezy.data.declarations import loader, resolver
from tests import tuple_registries as fixtures

DECLARATIONS = resolver.from_data_root(fixtures.DATA_ROOT)
MIRROR = "ovdp_enumerated_mirror"
DECLARED = DECLARATIONS.instruments[MIRROR]

HOLDING = Holding(
    owner_id="owner-1",
    instrument_id=MIRROR,
    quantity=10.0,
    purchased_on=fixtures.ISSUE_DATE,
    cost=Money(10_000.0, Currency.UAH, prov.EMPTY),
)
HORIZON = DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END)
HOLD_CASH = Assumptions(consumption_method="fifo", coupon_policy="hold_cash")


def _projected() -> Projection:
    outcome = project.project(
        DECLARED, HOLDING, HORIZON, HOLD_CASH, tax_classes=DECLARATIONS.tax_classes
    )
    assert isinstance(outcome, Projection), outcome
    return outcome


def _terms() -> EnumeratedTerms:
    terms = DECLARED.terms
    assert isinstance(terms, EnumeratedTerms)
    return terms


class TestEveryInferenceEntersUnverified:
    def test_the_schedule_s_own_source_says_it_is_an_inference(self) -> None:
        for source in _terms().provenance.sources:
            assert source.citation.startswith(loader.INFERENCE_MARKER)

    def test_every_payment_s_source_says_so_too(self) -> None:
        for payment in _terms().payments:
            for source in payment.amount.provenance.sources:
                assert source.citation.startswith(loader.INFERENCE_MARKER)

    def test_none_of_them_carries_a_verification_date(self) -> None:
        """Their expected first state, and not a gap somebody will get round to: an
        inference is unverified by construction. What a later reading verifies is the
        source it rests on, which is a different table."""
        assert prov.is_unverified(_terms().provenance)
        for payment in _terms().payments:
            assert prov.is_unverified(payment.amount.provenance)


class TestEveryFigureDerivedFromThemCarriesTheMark:
    def test_the_yield(self) -> None:
        assert prov.is_unverified(_projected().hurdle.provenance)

    def test_every_amount_in_the_ledger(self) -> None:
        for event in _projected().ledger.applied:
            if event.amount.provenance.sources:
                assert prov.is_unverified(event.amount.provenance), event.sequence

    def test_every_tax_charge(self) -> None:
        for charge in _projected().charges:
            assert prov.is_unverified(charge.provenance), charge.tax_class_id

    def test_no_derived_figure_appears_unmarked(self) -> None:
        """The half that catches a transform dropping the mark on one path: an unmarked
        figure resting on sources is the top-severity defect, and it looks exactly like a
        marked one from every angle but this."""
        projected = _projected()
        resting = [
            row.gross.provenance for row in projected.schedule.rows if row.gross.provenance.sources
        ]
        assert resting, "a schedule with no sourced amount would pass this vacuously"
        assert all(prov.is_unverified(sources) for sources in resting)

    def test_each_payment_s_own_sources_reach_the_row_it_became(self) -> None:
        """Not merely *a* mark: the payment's own citation. A figure marked by somebody
        else's source is traceable to the wrong file.

        Matched by date to *some* row rather than to one, because two payments of different
        kinds share a date -- which is the ordinary way a bond ends and the case a mapping
        keyed by date would silently collapse."""
        rows = _projected().schedule.rows
        for payment in _terms().payments:
            on_that_date = [row for row in rows if row.occurred_on == payment.on]
            assert on_that_date, payment.on
            assert any(
                payment.amount.provenance.sources <= row.gross.provenance.sources
                for row in on_that_date
            ), payment.on


def test_verifying_every_source_would_lift_the_mark() -> None:
    """The other direction, so the assertions above cannot pass because `is_unverified` is
    simply always true. Nothing in either tree is verified, so this constructs the
    counterfactual rather than waiting for one."""
    verified = prov.of(
        [replace(source, verified_on=fixtures.AS_OF) for source in _terms().provenance.sources]
    )
    assert not prov.is_unverified(verified)
