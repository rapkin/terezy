"""SC-009, SC-009a and research D6a: the three refusals about a section rather than a band.

019 FR-018, FR-018a. Without the hurdle among them a set of survivors is a shortlist with
nothing to measure it against, and its head reads as a winner -- the argument 010 FR-011 already
made one layer down and this feature must not undo one layer up.

**The withheld case is the one a reader misses**, and it has no natural test: the comparison is
a ``Comparison``, every figure is there, the benchmark is simply not in the population this pass
runs over, and nothing else refuses. Its reason must differ from the no-benchmark one, which is
asserted by comparing the two records rather than by reading them.
"""

from __future__ import annotations

from dataclasses import replace

from terezy.core.decision.answer import benchmark_unavailable
from terezy.core.results.candidates import CandidateCeiling, CeilingExceeded
from terezy.core.results.dominance import (
    BenchmarkWasWithheld,
    DominanceResult,
    NoBenchmarkToStandAgainst,
    NoSurveyToRunOver,
)
from tests import answer_registries as fixtures
from tests import dominance_sections as sections

REFUSING_BENCHMARK = "UA4000239040"
"""An issue whose 2026-08-24 quotation falls in none of its declared coupon periods, so it
produces no outcome at all (022 FR-001) -- and a benchmark that refused is 010's
``BenchmarkUnavailable``."""


def _answered_with(**edits: object) -> object:
    return fixtures.answered(replace(fixtures.owners_question(), **edits))  # type: ignore[arg-type]


def test_a_section_with_no_benchmark_refuses_carrying_010s_reason_verbatim() -> None:
    """SC-009, asserted by string comparison so the reason cannot be rewritten here."""
    answered = _answered_with(benchmark_instrument_id=REFUSING_BENCHMARK)
    section = answered.sections[sections.ONE_MONTH]  # type: ignore[attr-defined]
    unavailable = benchmark_unavailable(section)
    assert unavailable is not None, "the benchmark produced a rate, so no refusal is reached"
    refusal = sections.run(section)
    assert isinstance(refusal, NoBenchmarkToStandAgainst)
    assert refusal.reason == unavailable.reason


def test_a_withheld_benchmark_refuses_naming_it_and_the_date_its_money_arrives() -> None:
    """FR-018a. ``inzhur_miltech``'s plan requests an exit sixteen months past a one-month
    horizon, so 015 FR-030 withholds it -- and a hurdle whose figure the section refuses to show
    cannot be the member FR-016 requires."""
    answered = _answered_with(benchmark_instrument_id=fixtures.MILTECH)
    section = answered.sections[sections.ONE_MONTH]  # type: ignore[attr-defined]
    refusal = sections.run(section)
    assert isinstance(refusal, BenchmarkWasWithheld)
    assert refusal.key.instrument_id == fixtures.MILTECH
    withheld = {item.key: item.arrives_on for item in section.arrives_after_horizon}
    assert refusal.arrives_on == withheld[refusal.key]


def test_the_two_refusals_are_different_records_rather_than_one_reason_reused() -> None:
    """SC-009a's pair, compared as records: the remedies differ and so must the refusals."""
    no_hurdle = sections.run(
        _answered_with(benchmark_instrument_id=REFUSING_BENCHMARK).sections[0]  # type: ignore[attr-defined]
    )
    withheld = sections.run(
        _answered_with(benchmark_instrument_id=fixtures.MILTECH).sections[0]  # type: ignore[attr-defined]
    )
    assert type(no_hurdle) is not type(withheld)
    assert isinstance(no_hurdle, NoBenchmarkToStandAgainst)
    assert isinstance(withheld, BenchmarkWasWithheld)


def test_a_section_that_never_surveyed_refuses_carrying_the_record_that_replaced_it() -> None:
    """Research D6a's sixth refusal. ``HorizonSection.dominance`` is not optional, so something
    has to go there, and an empty ``DominanceResult`` would be the empty set standing for a
    failure FR-026 forbids -- indistinguishable from a section that evaluated nothing."""
    supplied = replace(fixtures.inputs(), ceiling=CandidateCeiling(max_candidates=1))
    answered = fixtures.answered(supplied=supplied)
    section = answered.sections[sections.ONE_MONTH]
    assert isinstance(section.dominance, NoSurveyToRunOver)
    assert isinstance(section.dominance.refusal, CeilingExceeded)
    assert section.dominance.refusal is section.outcome


def test_a_section_with_a_hurdle_produces_a_set_rather_than_any_of_them() -> None:
    """The mutation these three would otherwise survive: an implementation that refused always."""
    assert isinstance(sections.run(sections.section()), DominanceResult)
