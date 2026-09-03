"""The owner's own question, answered over the shipped registry.

015 SC-001 and SC-002. Two of the four words he said are declared by nothing at all; the other
two reach every instrument that ships, and at each of his three horizons the ОВДП group is
ranked against the issue he named as his benchmark. The two funds are not: one refuses on its
own terms and the other's money arrives in 2028.

**The benchmark's own terms end 2027-08-25**, a week short of his longest horizon, so at twelve
months the hurdle is a bond held very nearly to maturity and at one and three it is sold at the
window's end like any other candidate. That is why he chose it, and it is asserted below rather
than described.

What the choice does **not** settle is that a comparable rate is an IRR over the span the money
was at work: 1, 3 and 12 of the 24 ranked rows end inside his three windows and are annualised
over their own spans while the rest are annualised over the window, so the ordering is across
periods of different length whatever the hurdle is. `specs/features.toml` records it as
`rates-in-one-ranking-span-different-periods`; the renderer states the count per section.

**Every count below is derived from the labels and declarations the test loads.** A criterion
pinning 24 would be pinning the whole ОВДП group, and the cheapest way to satisfy it would be
the class-stands-in-for-the-group inference FR-007a forbids.
"""

from __future__ import annotations

from datetime import date, timedelta

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
    HorizonSection,
    SectionsAgreeByKey,
    SubjectReached,
    SubjectUndeclared,
)
from terezy.core.results.candidates import CandidateSurvey
from terezy.core.results.tuple import Comparison, DeclarationMissing, TupleOutcome
from tests import answer_registries as fixtures

pytestmark = pytest.mark.worked_example

HORIZONS = 3
EXIT_LATENCY_DAYS = 3
"""What `inzhur_to_monobank` declares. Waiting is inside the span (010 FR-015), so a
candidate sold at the window's end has its money home this many days after it."""

FINAL_PAYMENT = date(2027, 8, 25)
"""When the benchmark's own terms end: its last coupon and its principal, on one date."""
NAMED = 4
UNDECLARED_WORDS = ("cash", "btc")


def _answer() -> Answer:
    """His question over what ships, and nothing else: this is the deliverable, not a mechanism."""
    return fixtures.answered(supplied=fixtures.shipped_inputs())


def _labels() -> dict[str, tuple[str, ...]]:
    return fixtures.declared_labels(fixtures.declarations(fixtures.SHIPPED_ROOT))


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


def test_his_two_words_reach_exactly_what_their_labels_carry() -> None:
    """Which today is everything that ships, and that is a fact about the registry.

    It is not the group rule going slack: an instrument in neither group is reached by neither
    word, which ``tests/contract/test_group_membership_is_declared.py`` plants and asserts. The
    shipped registry simply has nothing outside the two families he asked about.
    """
    registries = fixtures.declarations(fixtures.SHIPPED_ROOT).tuples.registries
    declared = set(registries.instruments) | set(registries.funds)
    assert set(considered_ids(_answer())) == _expected_ids()
    assert _expected_ids() == declared


def test_there_are_three_sections_and_each_enumerates_the_same_ids() -> None:
    """SC-001's first half."""
    result = _answer()
    assert len(result.sections) == HORIZONS
    assert tuple(section.horizon for section in result.sections) == result.question.horizons
    for section in result.sections:
        assert isinstance(section.outcome, CandidateSurvey), section.outcome
        enumerated = {item.key.instrument_id for item in section.outcome.enumerated.candidates}
        assert enumerated == _expected_ids()


def test_every_horizon_ranks_the_bonds_and_only_the_bonds() -> None:
    """SC-001's second half. The ranked population is the ОВДП group, derived from the labels."""
    bonds = frozenset(name for name, groups in _labels().items() if fixtures.OVDP in groups)
    for section in _answer().sections:
        ranked = {item.key.instrument_id for item in section_ranking(section)}
        assert ranked == bonds


def test_the_benchmark_spans_each_window_within_the_exit_latency() -> None:
    """Why the owner picked this issue, asserted rather than left in the question file.

    Its final coupon and its principal both fall on 2027-08-25, so at twelve months it runs to
    its own terms and its money is home 2027-08-28 -- four days short of the window, a bond
    held very nearly to maturity over the longest horizon he asked about. At one and three
    months it is sold at the window's end like any other candidate and the money arrives three
    days later, which is the declared latency of the way out rather than anything about the
    paper (`horizon-as-a-latency-budget` records that the way out is unrefused).

    Either way the span is within days of the window, which is the whole point of the choice:
    the issue it replaced was annualised over 18 days at all three horizons
    (`rates-in-one-ranking-span-different-periods` in `specs/features.toml`).
    """
    short, mid, long = _answer().sections

    for section in (short, mid):
        hurdle = _hurdle(section)
        assert hurdle.sold_early is not None, "sold at the window's end"
        assert hurdle.span.end == section.horizon.end + timedelta(days=EXIT_LATENCY_DAYS), (
            "and home exactly the way out's declared latency later"
        )

    hurdle = _hurdle(long)
    assert hurdle.sold_early is None, "held to its own terms at twelve months"
    assert hurdle.span.end == FINAL_PAYMENT + timedelta(days=EXIT_LATENCY_DAYS)
    assert hurdle.span.end < long.horizon.end, "which fall inside that window"
    assert (long.horizon.end - hurdle.span.end).days <= 7, "and only just -- that is the choice"


def _hurdle(section: HorizonSection) -> TupleOutcome:
    """The benchmark's own outcome in one section."""
    return next(
        item for item in section_ranking(section) if item.key.instrument_id == fixtures.BENCHMARK
    )


def test_every_section_measures_that_ranking_against_the_issue_he_named() -> None:
    """FR-011: the hurdle is a position in the list, not a figure beside it.

    **Every index on ``Comparison`` addresses ``comparison.ranked``**, which is not the tuple
    ``section_ranking`` reports: that one has the withheld candidates removed (FR-030). So the
    hurdle is resolved to a key against ``comparison.ranked`` and then found by identity, and
    what beats it is read off ``beats_benchmark`` rather than off a position -- ``ties`` means
    a candidate can outrank the hurdle in the ordering without beating it.
    """
    for section in _answer().sections:
        assert isinstance(section.outcome, CandidateSurvey)
        comparison = section.outcome.comparison
        assert isinstance(comparison, Comparison), comparison
        hurdle = comparison.ranked[comparison.benchmark].key
        assert hurdle.instrument_id == fixtures.BENCHMARK
        assert hurdle in {item.key for item in section_ranking(section)}
        assert all(
            comparison.ranked[index].key != hurdle for index in comparison.beats_benchmark
        ), "the hurdle cannot be among the things that beat it"


def test_nothing_that_ships_wants_a_resale_price_and_an_invented_bond_still_does() -> None:
    """SC-023, on both roots, because the two halves are different claims.

    Nobody quotes a resale price for a bond that does not exist, and inventing one would put a
    made-up spread inside the worked examples a reader checks on paper -- so the invented bonds
    in ``tests/fixtures/data/`` refuse, and every real issue carries the seller's observed sell
    quotation and is sold at the window's end instead. The population differs by horizon:
    ``ovdp_enumerated_a``'s own schedule ends inside the twelve-month window and it is simply
    held to its end there.
    """
    assert _wanting_a_resale_price(_answer()) == [[], [], []]

    with_fixtures = fixtures.answered()
    declared = fixtures.inputs().registries
    wanting = _wanting_a_resale_price(with_fixtures)
    for names in wanting:
        assert names, "the refusal must stay the behaviour for an invented bond"
        assert all(declared.instruments[name].is_synthetic for name in names)
    assert wanting[0] == wanting[1]
    assert set(wanting[2]) < set(wanting[0])


def _wanting_a_resale_price(result: Answer) -> list[list[str]]:
    """Per section, the candidates dropped for a resale price nobody declared."""
    return [
        sorted(
            item.key.instrument_id
            for item in dropped(section.outcome.comparison)
            if isinstance(item.refusal, DeclarationMissing)
            and item.refusal.part == "access"
            and "access.resale_price" in item.refusal.what
        )
        for section in result.sections
        if isinstance(section.outcome, CandidateSurvey)
    ]


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
    assert _answer() == _answer()
