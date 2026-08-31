"""Two counts that must never be conflated, and an asymmetry that must never be smoothed.

015 SC-030 and SC-031. *He named four things and two can be answered* and *seven instruments
were enumerated* are both true and are different sentences; the defect is a single number
standing in for both. An id reached twice -- by a group and by itself, or by two overlapping
groups -- yields **one** candidate and is counted **once**, while the two subjects that reached
it are both still named.

**Every fixture here sets the group size different from the number of named subjects.** A group
of exactly two named by two subjects makes both counts 2, and a conflated implementation passes:
set sizes that happen to coincide are the standing way a discrimination test asserts nothing.
"""

from __future__ import annotations

from dataclasses import replace

from terezy.core.decision.answer import considered_ids, subject_counts
from terezy.core.results.answer import Answer, DeclaredSubject
from terezy.core.results.candidates import CandidateSurvey
from tests import answer_registries as fixtures

ISSUE_A = "ovdp_synthetic_a"
ISSUE_B = "ovdp_synthetic_b"


def _bonds_only(*subjects: str) -> Answer:
    """The owner's question narrowed to the bond side, so the fund plans run nothing.

    A plan keyed by a word no subject reaches refuses the whole answer, which is the rule that
    stops a stated choice silently doing nothing -- so dropping the funds means dropping their
    plans too.
    """
    question = fixtures.owners_question()
    return fixtures.answered(
        fixtures.with_plans(
            fixtures.with_subjects(question, *subjects),
            {fixtures.OVDP: question.plans[fixtures.OVDP]},
        )
    )


def _members(result: Answer, named: str) -> tuple[str, ...]:
    return next(
        item.ids
        for item in result.subjects
        if isinstance(item, DeclaredSubject) and item.named == named
    )


def _candidates_for(result: Answer, instrument_id: str) -> int:
    section = result.sections[0]
    assert isinstance(section.outcome, CandidateSurvey), section.outcome
    return sum(
        1
        for item in section.outcome.enumerated.candidates
        if item.key.instrument_id == instrument_id
    )


def test_a_group_and_one_of_its_members_named_together_count_the_id_once() -> None:
    """SC-030. Two named subjects, five ids, and one candidate for the id both reach."""
    result = _bonds_only(fixtures.OVDP, ISSUE_A)
    counts = subject_counts(result, result.sections[0])

    assert len(result.subjects) == 2
    assert counts.reached == 2
    assert counts.ids_considered == len(_members(result, fixtures.OVDP))
    assert counts.ids_considered != len(result.subjects), "the two counts must not coincide"
    assert _candidates_for(result, ISSUE_A) == 1
    assert considered_ids(result).count(ISSUE_A) == 1


def test_an_instrument_in_two_named_groups_is_counted_once() -> None:
    """FR-007b's other half: overlapping groups, one candidate, both subjects still named.

    016 declares OVDP issues sold *through* Inzhur, so the two groups are not disjoint and this
    is the shape the registry will actually have rather than a hypothetical.
    """
    declarations = fixtures.declarations()
    registries = declarations.tuples.registries
    both = replace(registries.instruments[ISSUE_B], groups=(fixtures.OVDP, fixtures.INZHUR))
    widened = replace(registries, instruments={**registries.instruments, ISSUE_B: both})
    supplied = replace(fixtures.inputs(declarations), registries=widened)

    question = fixtures.owners_question()
    result = fixtures.answered(
        fixtures.with_plans(
            fixtures.with_subjects(question, fixtures.OVDP, fixtures.INZHUR),
            {
                fixtures.OVDP: question.plans[fixtures.OVDP],
                fixtures.REIT: question.plans[fixtures.REIT],
                fixtures.MILTECH: question.plans[fixtures.MILTECH],
            },
        ),
        supplied,
    )
    counts = subject_counts(result, result.sections[0])

    assert ISSUE_B in _members(result, fixtures.OVDP)
    assert ISSUE_B in _members(result, fixtures.INZHUR)
    assert counts.reached == 2
    assert considered_ids(result).count(ISSUE_B) == 1
    assert counts.ids_considered == len(set(considered_ids(result)))
    assert counts.ids_considered != len(result.subjects)
    assert _candidates_for(result, ISSUE_B) == 1


def test_the_named_subject_count_is_over_words_and_not_over_ids() -> None:
    """The discrimination the two assertions above rest on, stated on its own.

    One word reaching five ids and five words reaching five ids are different questions, and a
    count that could not tell them apart is the one FR-010 exists to prevent.
    """
    one_word = _bonds_only(fixtures.OVDP)
    counts = subject_counts(one_word, one_word.sections[0])
    assert len(one_word.subjects) == 1
    assert counts.reached == 1
    assert counts.ids_considered > 1


def test_a_question_naming_an_undeclared_word_answers_where_an_instrument_would_refuse() -> None:
    """SC-031. The asymmetry **is** the requirement, so both halves are asserted together.

    A question is the owner's own vocabulary and its gaps are the answer's content; an
    instrument is curated data and its typos are defects. The load-side half is asserted in
    ``tests/contract/test_group_declaration_loading.py``; this is the answer-side half.
    """
    result = _bonds_only(fixtures.OVDP, "not_a_thing")
    counts = subject_counts(result, result.sections[0])
    assert counts.undeclared == 1
    assert counts.reached == 1
    assert "not_a_thing" not in considered_ids(result)


def test_a_plan_keyed_by_a_word_that_runs_nothing_refuses_the_question() -> None:
    """A setting silently dropped is a stated choice that does nothing."""
    question = fixtures.owners_question()
    refusal = fixtures.refused(
        fixtures.with_plans(
            fixtures.with_subjects(question, fixtures.OVDP),
            {fixtures.OVDP: question.plans[fixtures.OVDP], "nothing_reaches_this": ()},
        )
    )
    assert getattr(refusal, "named", None) == "nothing_reaches_this"


def test_a_plan_for_a_subject_the_registry_does_not_declare_is_not_refused() -> None:
    """``cash`` is a legitimate subject with a legitimate plan and an empty answer."""
    question = fixtures.owners_question()
    result = fixtures.answered(
        fixtures.with_plans(
            fixtures.with_subjects(question, fixtures.OVDP, "cash"),
            {fixtures.OVDP: question.plans[fixtures.OVDP], "cash": question.plans[fixtures.OVDP]},
        )
    )
    assert subject_counts(result, result.sections[0]).undeclared == 1
