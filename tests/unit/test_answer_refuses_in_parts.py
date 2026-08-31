"""A section-level failure is a section, never a missing one -- and never a whole refusal.

015 SC-009, SC-010, SC-011, SC-013 and SC-020. This is the central requirement of the feature:
any of 014's typed refusals is carried as that section's outcome **whole**, with every other
section computed independently, and *nothing could be ranked, and here is why for each* comes
back as an ``Answer`` rather than as a ``Refused``.

The battery below is partitioned the way 014's own seventeen-way battery is: what a **question**
can plant, and what it structurally cannot, each with its reason. A member in neither is a
member nobody thought about.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Final, get_args

import pytest

from terezy.core.decision.answer import (
    cross_horizon,
    key_agreement,
    section_evaluated,
    section_ranking,
    section_scored,
    subject_counts,
)
from terezy.core.decision.candidates import evaluated
from terezy.core.instruments.interface import DateRange
from terezy.core.primitives import provenance as prov
from terezy.core.results.answer import (
    Answer,
    BenchmarkOutsideTheSubjects,
    BenchmarkYieldsNoCandidate,
    HorizonSection,
    SectionsAgreeByKey,
    SubjectUnreached,
)
from terezy.core.results.candidates import CandidateCeiling, CandidateSurvey, SurveyRefused
from terezy.core.results.composed import SegmentBound
from terezy.core.results.tuple import TupleOutcome
from tests import answer_registries as fixtures

UNREACHABLE: Final[dict[str, str]] = {
    "DuplicateRunPlan": (
        "a question's plans are expanded per subject and equal ones are deduplicated in order "
        "(FR-007b), so one instrument cannot receive the same plan twice"
    ),
    "BenchmarkNotACandidate": (
        "the verb resolves the benchmark's key out of the enumerated set before calling survey, "
        "so it is a member exactly once by construction. Zero is BenchmarkYieldsNoCandidate and "
        "more than one is a whole-answer Refused, both of which are asserted here"
    ),
    "MoreThanOneStreamInTheSet": (
        "the benchmark check is about the *question* and fires first. Every instrument in this "
        "registry is bought at one venue, so a corridor that makes a set span two streams gives "
        "the benchmark a second candidate too -- which is a whole-answer Refused. Measured in "
        "tests/unit/test_cross_currency_candidate.py, which declares that corridor"
    ),
}


def _plant_no_plan() -> Answer:
    """A reachable subject with no supplied plan (014 FR-018), which refuses the enumeration."""
    question = fixtures.owners_question()
    return fixtures.answered(
        fixtures.with_plans(question, {fixtures.OVDP: question.plans[fixtures.OVDP]})
    )


def _plant_ceiling() -> Answer:
    """A declared ceiling of one, which the seven-candidate set exceeds."""
    supplied = replace(fixtures.inputs(), ceiling=CandidateCeiling(max_candidates=1))
    return fixtures.answered(supplied=supplied)


def _plant_broken_bound() -> Answer:
    """A segment bound admitting nothing, which is true of every pair at once."""
    supplied = replace(fixtures.inputs(), bound=SegmentBound(max_segments=0))
    return fixtures.answered(supplied=supplied)


def _plant_undeclared_route() -> Answer:
    """A route composed over that the evaluation's own registry does not declare (014 FR-018)."""
    supplied = fixtures.inputs()
    used = "inzhur_direct"
    assert used in supplied.registries.routes, sorted(supplied.registries.routes)
    narrowed = replace(
        supplied.registries,
        routes={name: route for name, route in supplied.registries.routes.items() if name != used},
    )
    return fixtures.answered(supplied=replace(supplied, registries=narrowed))


PLANTED: Final[dict[str, object]] = {
    "NoPlanSupplied": _plant_no_plan,
    "CeilingExceeded": _plant_ceiling,
    "QuestionDoesNotStandUp": _plant_broken_bound,
    "UndeclaredRouteSupplied": _plant_undeclared_route,
}


def test_the_battery_covers_every_member_of_the_union() -> None:
    """A member in neither column is a member nobody thought about."""
    members = {member.__name__ for member in get_args(SurveyRefused)}
    assert set(PLANTED) | set(UNREACHABLE) == members
    assert not set(PLANTED) & set(UNREACHABLE)


@pytest.mark.parametrize("refusal", sorted(PLANTED))
def test_a_planted_refusal_is_carried_whole_and_the_answer_stands(refusal: str) -> None:
    """SC-010. The record 014 produced, unmodified, as that section's outcome."""
    result = PLANTED[refusal]()  # type: ignore[operator]
    assert isinstance(result, Answer)
    assert len(result.sections) == len(result.question.horizons)
    for section in result.sections:
        assert type(section.outcome).__name__ == refusal, section.outcome
        assert section_ranking(section) == ()


def test_a_section_that_refuses_still_states_where_every_named_subject_stands() -> None:
    """FR-010's counts are about the *question*, so a refused section still reports them."""
    result = _plant_ceiling()
    for section in result.sections:
        assert len(section.standings) == len(result.question.subjects)


def test_the_answer_stands_when_no_horizon_produced_a_ranking() -> None:
    """SC-020's neighbour: an ``Answer``, never a ``Refused``. Measured today's behaviour."""
    result = fixtures.answered()
    assert isinstance(result, Answer)
    assert all(section_ranking(section) == () for section in result.sections)


def test_a_question_whose_subjects_the_registry_declares_none_of_still_answers() -> None:
    """SC-020. Every named subject in the undeclared population, every section empty."""
    question = fixtures.owners_question()
    narrowed = fixtures.with_plans(fixtures.with_subjects(question, "cash", "btc"), {})
    result = fixtures.answered(replace(narrowed, benchmark_instrument_id="cash"))
    assert isinstance(result, Answer)
    assert len(result.sections) == 3
    for section in result.sections:
        assert isinstance(section.outcome, BenchmarkYieldsNoCandidate | CandidateSurvey)
        assert section_ranking(section) == ()


def test_a_benchmark_outside_the_subjects_refuses_the_whole_answer() -> None:
    """SC-011. It can never be a member of the set, which is a fact about the question."""
    question = fixtures.owners_question()
    refusal = fixtures.refused(replace(question, benchmark_instrument_id="enumerated_taxable_x"))
    assert isinstance(refusal, BenchmarkOutsideTheSubjects)
    assert refusal.instrument_id == "enumerated_taxable_x"


def test_a_benchmark_that_yields_no_candidate_is_this_sections_own_refusal() -> None:
    """014's record cannot carry it: that one holds a five-term key, and there is none."""
    question = fixtures.owners_question()
    narrowed = fixtures.with_plans(
        fixtures.with_subjects(question, "cash"), {"cash": question.plans[fixtures.OVDP]}
    )
    result = fixtures.answered(replace(narrowed, benchmark_instrument_id="cash"))
    for section in result.sections:
        assert isinstance(section.outcome, BenchmarkYieldsNoCandidate), section.outcome
        assert section.outcome.instrument_id == "cash"


def test_sections_are_computed_independently_of_one_another() -> None:
    """SC-009's claim, over horizons that genuinely differ.

    Over the shipped registry the twelve-month section evaluates two candidates the shorter two
    cannot, so the three sections are demonstrably not copies of one another -- which is what an
    assertion about independence has to rest on.
    """
    result = fixtures.answered()
    dropped_counts = [
        len(section.outcome.comparison.refused)
        for section in result.sections
        if isinstance(section.outcome, CandidateSurvey)
    ]
    assert len(set(dropped_counts)) > 1, dropped_counts


def test_adding_a_horizon_leaves_the_other_sections_untouched() -> None:
    """A section is a function of its own horizon and nothing else."""
    question = fixtures.owners_question()
    two = fixtures.answered(replace(question, horizons=question.horizons[:2]))
    three = fixtures.answered(question)
    assert three.sections[:2] == two.sections


def test_the_cross_horizon_reading_is_derived_and_agrees_with_the_sections() -> None:
    """SC-013. One named function over the answer, never a stored second copy."""
    result = fixtures.answered()
    placements = cross_horizon(result)
    assert len(placements) == len({item.key for item in placements})
    for placement in placements:
        assert len(placement.ranks) == len(result.sections)
        for index, rank in enumerate(placement.ranks):
            ranked = section_ranking(result.sections[index])
            assert rank is None or ranked[rank].key == placement.key


def test_the_sections_are_asserted_equal_by_key_rather_than_assumed() -> None:
    """FR-013 over a question whose horizons differ in length."""
    assert isinstance(key_agreement(fixtures.answered()), SectionsAgreeByKey)


def test_a_horizon_that_starts_before_as_of_is_unremarkable() -> None:
    """``as_of`` decides staleness and nothing else, so asking about April is a real question."""
    question = fixtures.owners_question()
    earlier = replace(
        question, horizons=(DateRange(start=date(2026, 4, 1), end=date(2026, 10, 1)),)
    )
    assert isinstance(fixtures.answered(earlier), Answer)


def test_a_section_that_refused_before_enumerating_says_so_rather_than_naming_a_corridor() -> None:
    """The remedy for a ceiling is ``data/candidates/``, not a corridor.

    *Declared but unreached* names a remedy, and naming it where the section never looked is a
    guard whose message is false, one layer up.
    """
    result = _plant_ceiling()
    for section in result.sections:
        counts = subject_counts(result, section)
        assert counts.not_assessed == 2
        assert counts.declared_but_unreached == 0
        assert counts.undeclared == 2
        assert not [item for item in section.standings if isinstance(item, SubjectUnreached)]


def test_a_benchmark_that_yields_nothing_still_knows_which_subjects_connect() -> None:
    """Enumeration succeeded there -- the benchmark is what failed -- so the set is in hand."""
    question = fixtures.owners_question()
    narrowed = fixtures.with_plans(
        fixtures.with_subjects(question, fixtures.OVDP, "cash"),
        {fixtures.OVDP: question.plans[fixtures.OVDP]},
    )
    result = fixtures.answered(replace(narrowed, benchmark_instrument_id="cash"))
    for section in result.sections:
        assert isinstance(section.outcome, BenchmarkYieldsNoCandidate)
        counts = subject_counts(result, section)
        assert counts.reached == 1
        assert counts.not_assessed == 0


def test_a_section_that_never_enumerated_is_not_a_disagreement_about_candidates() -> None:
    """Counting its empty set would report every other section's keys as unique to it."""
    assert isinstance(key_agreement(_plant_ceiling()), SectionsAgreeByKey)


def evaluated_of(section: HorizonSection) -> tuple[TupleOutcome, ...]:
    """Every candidate the comparison evaluated, before FR-030 withheld any."""
    outcome = section.outcome
    return evaluated(outcome.comparison) if isinstance(outcome, CandidateSurvey) else ()


def test_the_answers_marks_describe_the_figures_it_reports() -> None:
    """A withheld candidate's figure is not reported, so its sources are not behind one."""
    result = fixtures.answered()
    reported = prov.merge_all(
        item.provenance for section in result.sections for item in section_evaluated(section)
    )
    withheld_only = {
        source
        for section in result.sections
        for item in evaluated_of(section)
        if item.key in {late.key for late in section.arrives_after_horizon}
        for source in item.provenance.sources
    } - reported.sources
    assert withheld_only, "the fixture must actually withhold a candidate with sources of its own"
    assert not withheld_only & result.provenance.sources


def test_a_section_with_no_benchmark_still_carries_the_figures_it_computed() -> None:
    """``BenchmarkUnavailable.scored`` exists so the work is not thrown away.

    Nothing is *ranked* -- there is nothing to rank against -- but two candidates produced
    complete outcomes at twelve months, and a reader told only "nothing was ranked" would never
    learn they exist.
    """
    twelve = fixtures.answered().sections[2]
    assert section_ranking(twelve) == ()
    assert len(section_scored(twelve)) == 2
    assert all(item.reaches.amount > 0.0 for item in section_scored(twelve))


def test_a_withheld_benchmark_leaves_nothing_ranked() -> None:
    """The case a reader would miss: the figures are all there and the hurdle is not.

    010 FR-011 says the hurdle is always scored and always shown, so a ranking without it is
    not offered -- the head of the remaining list is exactly the winner it must not read as.
    """
    question = fixtures.owners_question()
    with_price = fixtures.with_resale_price(fixtures.inputs(), "ovdp_synthetic_a")
    result = fixtures.answered(
        replace(question, benchmark_instrument_id=fixtures.MILTECH), with_price
    )
    for section in result.sections:
        withheld = {item.key.instrument_id for item in section.arrives_after_horizon}
        assert fixtures.MILTECH in withheld
        assert section_ranking(section) == ()
        assert section_scored(section)


def test_a_disagreement_names_the_section_a_reader_can_count_to() -> None:
    """``only_in`` is keyed by the section's own index, not by a position in a filtered list."""
    result = _plant_ceiling()
    agreement = key_agreement(result)
    assert isinstance(agreement, SectionsAgreeByKey)
