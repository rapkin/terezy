"""The owner's own question, answered over the shipped registry.

015 SC-001 and SC-002. This is the feature's deliverable and it is a **refusal**: at every one
of the three horizons he asked about, nothing is ranked. Two of the four words he said are
declared by nothing at all, and the other two resolve to seven ids of which five want a resale
price nobody has quoted, one cannot be sized without a rate he has not stated, and one reports
money that arrives sixteen months after the window it was compared over.

An answer that returned a number for each of his four subjects would have lied about all of it.

**Every count below is derived from the labels and declarations the test loads.** A criterion
pinning nine would be pinning the whole registry, which is not the question he asked -- and the
cheapest way to satisfy it would be the class-stands-in-for-the-group inference FR-007a forbids.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.decision.answer import (
    considered_ids,
    key_agreement,
    section_evaluated,
    section_ranking,
    subject_counts,
    undeclared,
)
from terezy.core.decision.candidates import dropped
from terezy.core.results.answer import (
    Answer,
    DeclaredSubject,
    SectionsAgreeByKey,
    SubjectReached,
    SubjectUndeclared,
)
from terezy.core.results.candidates import CandidateSurvey
from terezy.core.results.tuple import BenchmarkUnavailable, DeclarationMissing
from tests import answer_registries as fixtures

pytestmark = pytest.mark.worked_example

HORIZONS = 3
NAMED = 4
UNDECLARED_WORDS = ("cash", "btc")


def _answer() -> Answer:
    return fixtures.answered()


def _labels() -> dict[str, tuple[str, ...]]:
    """Which groups each shipped instrument declares itself into, read off the registry."""
    registries = fixtures.declarations().tuples.registries
    return {
        **{name: declared.groups for name, declared in registries.instruments.items()},
        **{name: declared.groups for name, declared in registries.funds.items()},
    }


def _expected_ids() -> frozenset[str]:
    """What ``ovdp`` and ``inzhur`` reach, derived from the labels rather than written out."""
    wanted = {fixtures.OVDP, fixtures.INZHUR}
    return frozenset(name for name, groups in _labels().items() if wanted & set(groups))


def test_the_question_names_four_subjects_and_two_of_them_are_declared_by_nothing() -> None:
    """SC-002. ``cash`` and ``btc`` reach the answer by the words he wrote."""
    result = _answer()
    assert len(result.subjects) == NAMED
    assert tuple(item.named for item in undeclared(result)) == UNDECLARED_WORDS


def test_the_two_declared_words_resolve_to_the_ids_their_labels_carry() -> None:
    """Derived from the registry, which is what keeps it true after 016 adds 24 issues."""
    result = _answer()
    groups = {item.named: item.ids for item in result.subjects if isinstance(item, DeclaredSubject)}
    assert set(groups) == {fixtures.OVDP, fixtures.INZHUR}
    assert frozenset().union(*groups.values()) == _expected_ids()
    assert all(item.is_group for item in result.subjects if isinstance(item, DeclaredSubject))


def test_it_is_seven_ids_and_not_the_whole_registry() -> None:
    """Seven, because his four words are not *everything the registry declares*.

    The two instruments in neither group are out because their own files say what they are
    for: one is fixed income and deliberately not an OVDP, and the other's whole purpose is
    that it is different from the Inzhur funds.
    """
    registries = fixtures.declarations().tuples.registries
    declared = set(registries.instruments) | set(registries.funds)
    assert set(considered_ids(_answer())) == _expected_ids()
    assert _expected_ids() < declared


def test_there_are_three_sections_and_each_enumerates_the_seven() -> None:
    """SC-001's first half."""
    result = _answer()
    assert len(result.sections) == HORIZONS
    assert tuple(section.horizon for section in result.sections) == result.question.horizons
    for section in result.sections:
        assert isinstance(section.outcome, CandidateSurvey), section.outcome
        enumerated = {item.key.instrument_id for item in section.outcome.enumerated.candidates}
        assert enumerated == _expected_ids()


def test_nothing_is_ranked_at_any_horizon_he_asked_about() -> None:
    """SC-001's second half, and the whole point of the feature."""
    for section in _answer().sections:
        assert section_ranking(section) == ()


def test_every_section_has_no_benchmark_to_rank_against() -> None:
    """The hurdle itself is one of the five wanting a resale price, so there is no ranking."""
    for section in _answer().sections:
        assert isinstance(section.outcome, CandidateSurvey)
        assert isinstance(section.outcome.comparison, BenchmarkUnavailable)


def test_five_want_a_resale_price_at_one_and_three_months_and_three_at_twelve() -> None:
    """SC-023, per section: the count is unchanged from the baseline and the remedy is a file.

    The population differs by horizon because two of the bonds' own schedules end inside the
    twelve-month window and are simply held to their end there.
    """
    wanting = [
        sorted(
            item.key.instrument_id
            for item in dropped(section.outcome.comparison)
            if isinstance(item.refusal, DeclarationMissing)
            and item.refusal.part == "access"
            and "access.resale_price" in item.refusal.what
        )
        for section in _answer().sections
        if isinstance(section.outcome, CandidateSurvey)
    ]
    assert [len(names) for names in wanting] == [5, 5, 3]
    assert set(wanting[2]) < set(wanting[0])


def test_the_one_fund_that_evaluates_is_withheld_because_its_money_arrives_in_2028() -> None:
    """SC-027. Under a label rule the one-month section *is* one number wearing a caveat."""
    for section in _answer().sections:
        withheld = {
            item.key.instrument_id: item.arrives_on for item in section.arrives_after_horizon
        }
        assert withheld == {fixtures.MILTECH: date(2028, 1, 20)}
        assert fixtures.MILTECH not in {
            item.key.instrument_id for item in section_evaluated(section)
        }


def test_every_section_says_how_many_named_subjects_it_reached() -> None:
    """SC-002's second half. Two of four, and the other two need a declaration."""
    result = _answer()
    for section in result.sections:
        counts = subject_counts(result, section)
        assert (counts.reached, counts.declared_but_unreached, counts.undeclared) == (2, 0, 2)
        assert counts.reached + counts.declared_but_unreached + counts.undeclared == NAMED
        assert counts.ids_considered == len(_expected_ids())
        assert counts.ids_considered != NAMED, "the two counts must not be able to coincide"


def test_the_three_states_are_three_types() -> None:
    """FR-010: distinguishable without reading prose, because their remedies differ."""
    for section in _answer().sections:
        by_word = {item.named: item for item in section.standings}
        assert isinstance(by_word[fixtures.OVDP], SubjectReached)
        assert all(isinstance(by_word[word], SubjectUndeclared) for word in UNDECLARED_WORDS)


def test_the_three_sections_enumerate_the_same_candidates() -> None:
    """SC-012 over the shipped registry -- checked per run, never assumed (FR-013)."""
    assert isinstance(key_agreement(_answer()), SectionsAgreeByKey)


def test_answering_twice_produces_an_equal_answer() -> None:
    """FR-027. Pure: no clock, no I/O, no randomness."""
    assert fixtures.answered() == fixtures.answered()
