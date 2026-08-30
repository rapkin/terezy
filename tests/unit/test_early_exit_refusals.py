"""What a horizon shorter than an instrument's own terms now reports, over the shipped registry.

015 FR-029 and FR-031, at the tuple level. Before this feature such a candidate dropped as
``CannotSpanHorizon`` binding on ``instrument.maturity_date`` -- *shorten nothing, it is
impossible*. The clarification of 2026-08-30 says the money **can** be withdrawn, at a spread,
so the drop stays and the remedy changes: **declare what this sells for**.

The count is what does not move. Every candidate that dropped before drops now, for a reason
whose remedy is a file rather than a longer window.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from terezy.core.decision.candidates import dropped, evaluated, survey
from terezy.core.decision.tuple_outcome import Registries
from terezy.core.instruments.access import VenueQuote
from terezy.core.instruments.interface import DateRange
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.money import Money
from terezy.core.results.candidates import CandidateSet, CandidateSurvey
from terezy.core.results.tuple import CannotSpanHorizon, DeclarationMissing
from tests import candidate_registries as fixtures

SHORT = DateRange(start=fixtures.OUTLAY_ON, end=date(2027, 6, 30))
"""A window that ends before several shipped instruments' own terms do, and after others'."""

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
        for item in dropped(_surveyed(fixtures.shipped()).comparison)
        if isinstance(item.refusal, CannotSpanHorizon)
        and item.refusal.binding_term == "instrument.maturity_date"
    ]


def test_the_instruments_that_outlive_the_window_want_a_declared_price() -> None:
    """Derived from the registry the test loads, never written out."""
    wanting = _wanting_a_resale_price(_surveyed(fixtures.shipped()))
    assert wanting
    assert all(name not in wanting for name in fixtures.shipped().funds)


def test_declaring_the_price_moves_exactly_that_instrument_and_no_other() -> None:
    """The pair that makes the refusal a real one rather than a message.

    Asserted as a *difference* between two runs over one registry: an implementation that
    refused everything, or that refused nothing, passes neither half.
    """
    registries = fixtures.shipped()
    before = _surveyed(registries)
    wanted = _wanting_a_resale_price(before)
    subject = wanted[0]

    with_price = fixtures.with_access(
        registries,
        subject,
        resale_price=VenueQuote(price=RESALE, kind="venue_terms"),
    )
    after = _surveyed(with_price)

    assert _wanting_a_resale_price(after) == [name for name in wanted if name != subject]
    reached = {outcome.key.instrument_id for outcome in evaluated(after.comparison)}
    assert subject in reached
    assert subject not in {outcome.key.instrument_id for outcome in evaluated(before.comparison)}


def test_the_figure_it_produces_names_the_declared_belief() -> None:
    """FR-032: every figure computed through the assumption carries it where it is reported."""
    registries = fixtures.shipped()
    subject = _wanting_a_resale_price(_surveyed(registries))[0]
    after = _surveyed(
        fixtures.with_access(
            registries, subject, resale_price=VenueQuote(price=RESALE, kind="venue_terms")
        )
    )
    outcome = next(
        item for item in evaluated(after.comparison) if item.key.instrument_id == subject
    )
    assert any(registries.spread_holds.id in claim for claim in outcome.rests_on), outcome.rests_on


def test_a_holding_the_window_reaches_carries_no_such_claim() -> None:
    """The early-exit machinery is reachable only where an early exit actually happens."""
    registries = fixtures.shipped()
    whole = _surveyed(registries, fixtures.HORIZON)
    for outcome in evaluated(whole.comparison):
        assert all(registries.spread_holds.id not in claim for claim in outcome.rests_on)


def test_the_belief_is_read_from_the_registry_rather_than_written_here() -> None:
    """SC-032's rule applied to the assumption: change the declaration, change what is named."""
    registries = fixtures.shipped()
    subject = _wanting_a_resale_price(_surveyed(registries))[0]
    renamed = replace(
        registries, spread_holds=replace(registries.spread_holds, id="a_different_belief")
    )
    after = _surveyed(
        fixtures.with_access(
            renamed, subject, resale_price=VenueQuote(price=RESALE, kind="venue_terms")
        )
    )
    outcome = next(
        item for item in evaluated(after.comparison) if item.key.instrument_id == subject
    )
    assert any("a_different_belief" in claim for claim in outcome.rests_on), outcome.rests_on
