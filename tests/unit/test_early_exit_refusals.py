"""What a horizon shorter than an instrument's own terms now reports, over the composed registry.

015 FR-029 and FR-031, at the tuple level. Before this feature such a candidate dropped as
``CannotSpanHorizon`` binding on ``instrument.maturity_date`` -- *shorten nothing, it is
impossible*. The clarification of 2026-08-30 says the money **can** be withdrawn, at a spread,
so the drop stays and the remedy changes: **declare what this sells for**.

The count is what does not move. Every candidate that dropped before drops now, for a reason
whose remedy is a file rather than a longer window.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from terezy.core.decision.candidates import dropped, evaluated, survey
from terezy.core.decision.tuple_outcome import Registries
from terezy.core.instruments import registry
from terezy.core.instruments.access import VenueQuote
from terezy.core.instruments.interface import DateRange
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.money import Money
from terezy.core.results.candidates import CandidateSet, CandidateSurvey
from terezy.core.results.tuple import CannotSpanHorizon, DeclarationMissing, InstrumentRefused
from tests import candidate_registries as fixtures

SHORT = DateRange(start=fixtures.OUTLAY_ON, end=date(2027, 6, 30))
"""A window that ends before several declared instruments' own terms do, and after others'."""

RESALE = Money(995.0, fixtures.UAH, prov.EMPTY)


def _surveyed(registries: Registries, horizon: DateRange = SHORT) -> CandidateSurvey:
    question = fixtures.question(registries, horizon=horizon)
    enumerated = fixtures.enumerated(registries, question_=question)
    assert isinstance(enumerated, CandidateSet), enumerated
    result = survey(
        registries=registries,
        routes=registries.routes,
        question=question,
        ceiling=fixtures.ceiling(10_000),
        benchmark=enumerated.candidates[0].key,
    )
    assert isinstance(result, CandidateSurvey), result
    return result


def _wanting_a_resale_price(result: CandidateSurvey) -> list[str]:
    return sorted(
        item.key.instrument_id
        for item in dropped(result.comparison)
        if isinstance(item.refusal, DeclarationMissing)
        and item.refusal.part == "access"
        and "access.resale_price" in item.refusal.what
    )


def test_no_bond_binds_on_its_maturity_date_any_more() -> None:
    """The sentence FR-029 falsified is gone from the output, not merely from the docstring."""
    assert not [
        item
        for item in dropped(_surveyed(fixtures.declared()).comparison)
        if isinstance(item.refusal, CannotSpanHorizon)
        and item.refusal.binding_term == "instrument.maturity_date"
    ]


def test_the_instruments_that_outlive_the_window_want_a_declared_price() -> None:
    """Derived from the registry the test loads, never written out."""
    wanting = _wanting_a_resale_price(_surveyed(fixtures.declared()))
    assert wanting
    assert all(name not in wanting for name in fixtures.declared().funds)


def test_declaring_the_price_moves_exactly_that_instrument_and_no_other() -> None:
    """The pair that makes the refusal a real one rather than a message.

    Asserted as a *difference* between two runs over one registry: an implementation that
    refused everything, or that refused nothing, passes neither half.
    """
    registries = fixtures.declared()
    before = _surveyed(registries)
    wanted = _wanting_a_resale_price(before)
    subject = wanted[0]

    with_price = fixtures.with_access(
        registries,
        subject,
        resale_price=VenueQuote(price=RESALE, kind="venue_terms", observed_on=fixtures.OUTLAY_ON),
    )
    after = _surveyed(with_price)

    assert _wanting_a_resale_price(after) == [name for name in wanted if name != subject]
    reached = {outcome.key.instrument_id for outcome in evaluated(after.comparison)}
    assert subject in reached
    assert subject not in {outcome.key.instrument_id for outcome in evaluated(before.comparison)}


def test_the_figure_it_produces_names_the_declared_belief() -> None:
    """FR-032: every figure computed through the assumption carries it where it is reported."""
    registries = fixtures.declared()
    subject = _wanting_a_resale_price(_surveyed(registries))[0]
    after = _surveyed(
        fixtures.with_access(
            registries,
            subject,
            resale_price=VenueQuote(
                price=RESALE, kind="venue_terms", observed_on=fixtures.OUTLAY_ON
            ),
        )
    )
    outcome = next(
        item for item in evaluated(after.comparison) if item.key.instrument_id == subject
    )
    assert any(registries.quotation_holds.id in claim for claim in outcome.rests_on), (
        outcome.rests_on
    )


def test_a_holding_the_window_reaches_is_sold_nowhere_and_still_leans_on_the_quotation() -> None:
    """The early-exit machinery is reachable only where an early exit happens -- and the belief
    is not the early exit's (022 FR-017).

    Over a window every instrument's own terms end inside, nothing is sold. The belief is named
    all the same, because the **purchase** was priced from a quotation read on another day: it
    governs every use of a dated quotation, and a hold-to-maturity figure leans on it with no
    exit anywhere in it.
    """
    registries = fixtures.declared()
    whole = _surveyed(registries, fixtures.HORIZON)
    named = 0
    for outcome in evaluated(whole.comparison):
        assert outcome.sold_early is None, outcome.key.instrument_id
        named += any(registries.quotation_holds.id in claim for claim in outcome.rests_on)
    assert named


def test_the_belief_is_read_from_the_registry_rather_than_written_here() -> None:
    """SC-032's rule applied to the assumption: change the declaration, change what is named."""
    registries = fixtures.declared()
    subject = _wanting_a_resale_price(_surveyed(registries))[0]
    renamed = replace(
        registries, quotation_holds=replace(registries.quotation_holds, id="a_different_belief")
    )
    after = _surveyed(
        fixtures.with_access(
            renamed,
            subject,
            resale_price=VenueQuote(
                price=RESALE, kind="venue_terms", observed_on=fixtures.OUTLAY_ON
            ),
        )
    )
    outcome = next(
        item for item in evaluated(after.comparison) if item.key.instrument_id == subject
    )
    assert any("a_different_belief" in claim for claim in outcome.rests_on), outcome.rests_on


def test_a_schedule_whose_last_payment_is_a_coupon_sells_nothing_at_the_window_end() -> None:
    """The residual decides whether there is a sale, and it can be zero.

    ``enumerated_out_of_order`` repays its principal on 2027-03-31 and pays its final coupon the
    day after, so a window ending on the repayment leaves **nothing to sell** while a payment
    still falls outside it. Striking a sale for zero units emits a disposal of nothing, which
    the ledger refuses by *raising* -- an uncaught exception where the honest answer is a coupon
    the holding simply never receives.
    """
    registries = fixtures.declared()
    subject = "enumerated_out_of_order"
    with_price = fixtures.with_access(
        registries,
        subject,
        resale_price=VenueQuote(price=RESALE, kind="venue_terms", observed_on=date(2026, 10, 2)),
    )
    # Opened after this issue's first declared coupon: its accrual periods begin there, and a
    # window opening on `covers_from` could not price a purchase at all (022 FR-001).
    result = _surveyed(with_price, DateRange(start=date(2026, 10, 1), end=date(2027, 3, 31)))
    outcome = next(
        item for item in evaluated(result.comparison) if item.key.instrument_id == subject
    )
    assert outcome.sold_early is None
    assert all(claim for claim in outcome.rests_on)


NOT_ENOUGH = Money(10.0, fixtures.UAH, prov.EMPTY)
"""A quotation worth less than one of the issue's own coupons. Unreachable on the shipped
registry -- the smallest declared quote is three figures against coupons of tens -- and the
whole point of the refusal below is that it is a **declaration** conflict rather than a number
to be clamped."""


def _refusal_reasons(registries: Registries, horizon: DateRange = SHORT) -> list[str]:
    result = _surveyed(registries, horizon)
    return [item.refusal.reason for item in dropped(result.comparison)]


def test_a_carried_price_at_or_below_zero_refuses_rather_than_going_negative() -> None:
    """The sell leg's guard, reached on a listed schedule.

    Striking the sale anyway posts a disposal of a negative amount, which the ledger answers by
    raising -- an uncaught exception out of the pure core on a condition two data files
    produced between them. Reached by quoting a unit at 10.00 the day before a coupon of tens
    detaches: the clean price that implies is negative, and a sale struck on the coupon date
    finds the accrual reset to zero with nothing left under it.
    """
    registries = fixtures.declared()
    subject = _wanting_a_resale_price(_surveyed(registries))[0]
    declared = registries.instruments[subject]
    coupons = registry.ops_for(declared.instrument_class).coupons_per_unit(declared)
    detaches = next(on for on, _ in coupons if on > fixtures.OUTLAY_ON)
    starved = fixtures.with_access(
        registries,
        subject,
        resale_price=VenueQuote(
            price=NOT_ENOUGH, kind="venue_terms", observed_on=detaches - timedelta(days=1)
        ),
    )
    assert [
        reason
        for reason in _refusal_reasons(starved, DateRange(start=fixtures.OUTLAY_ON, end=detaches))
        if "A sale cannot be struck at nothing or at less" in reason
    ]


def test_only_a_missing_price_is_reported_as_a_missing_declaration() -> None:
    """Two refusals name `access.resale_price`, and only one is a gap in the declarations.

    A window that outlives the paper with no quotation to sell at wants a **file**. A quotation
    that cannot be carried to the sale date wants a different **window** -- the price it needs
    is already declared, and routing on the second term alone would send the owner looking for
    a file he has, which is a guard whose message is false.
    """
    registries = fixtures.declared()
    subject = _wanting_a_resale_price(_surveyed(registries))[0]
    # Quoted before the issue's first declared coupon period opens, so the carry refuses.
    uncarriable = fixtures.with_access(
        registries,
        subject,
        resale_price=VenueQuote(price=RESALE, kind="venue_terms", observed_on=date(2020, 1, 1)),
    )
    refused = {
        item.key.instrument_id: item.refusal for item in dropped(_surveyed(uncarriable).comparison)
    }
    assert isinstance(refused[subject], InstrumentRefused), refused[subject]
    assert "access.resale_price" not in refused[subject].reason
    assert isinstance(
        next(
            item.refusal
            for item in dropped(_surveyed(registries).comparison)
            if item.key.instrument_id == subject
        ),
        DeclarationMissing,
    )
