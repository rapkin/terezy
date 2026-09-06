"""FR-008's three populations partition the evaluated set, and FR-009 prunes nothing.

019. The accounting identity is *evaluated = non-dominated + dominated + not placed*, and it is
an asserted check rather than a claim in prose (014 FR-009's rule) -- the pass raises where it
does not hold, so this suite's job is to reach it over real sections and over the two edge cases
no declaration produces.
"""

from __future__ import annotations

import pytest

from terezy.core.decision.answer import section_evaluated
from terezy.core.decision.dominance import why_one_member
from terezy.core.results.dominance import (
    EveryOtherIsDominated,
    Mixed,
    OnlyOneEvaluated,
    TheSetDoesNotHaveOneMember,
)
from tests import dominance_sections as sections

HORIZONS = [sections.ONE_MONTH, sections.THREE_MONTHS, sections.TWELVE_MONTHS]


@pytest.mark.parametrize(
    "index", [sections.ONE_MONTH, sections.THREE_MONTHS, sections.TWELVE_MONTHS]
)
def test_every_evaluated_candidate_lands_in_exactly_one_population(index: int) -> None:
    """SC-001's identity, derived from the registry the test loads and never hard-coded."""
    section = sections.section(index)
    result = sections.result(section)
    evaluated = {item.key for item in section_evaluated(section)}
    placed = (
        {*result.non_dominated}
        | {item.key for item in result.dominated}
        | {item.key for item in result.not_placed}
    )
    counted = len(result.non_dominated) + len(result.dominated) + len(result.not_placed)
    assert placed == evaluated
    assert counted == len(evaluated), "a candidate is in two populations"


@pytest.mark.parametrize(
    "index", [sections.ONE_MONTH, sections.THREE_MONTHS, sections.TWELVE_MONTHS]
)
def test_nothing_is_pruned(index: int) -> None:
    """FR-009: dominance is a reported relation over the population, never a filter on it.

    A dominated candidate is one the owner may still choose, for a reason no declared objective
    carries -- a maturity he likes, an issuer he trusts, a paper he already holds.
    """
    section = sections.section(index)
    result = sections.result(section)
    assert result.dominated, "nothing was dominated here, so this asserts nothing"
    for beaten in result.dominated:
        assert beaten.key in {item.key for item in section_evaluated(section)}
        assert beaten.dominated_by, "a dominated candidate names no candidate that dominates it"


def test_a_lone_evaluated_candidate_is_non_dominated_and_says_why() -> None:
    """The specification's own edge case, and the one *every pair is incomparable* would break.

    *Every pair is incomparable* is vacuously true of a section's only candidate, so a
    ``not_placed`` rule written without the *at least one pair* clause would put it there, leave
    the set empty, and pass SC-004's emptiness property vacuously.
    """
    lone = sections.only(sections.section(), [])
    result = sections.result(lone)
    assert len(result.non_dominated) == 1
    assert not result.dominated
    assert not result.not_placed
    assert isinstance(why_one_member(result), OnlyOneEvaluated)


def test_a_set_of_one_over_several_candidates_says_every_other_is_dominated() -> None:
    """FR-014's only *finding* case, distinguished from the one above on the record."""
    two = sections.only(sections.section(), ["UA4000239016"])
    result = sections.result(two)
    assert len(result.non_dominated) == 1
    assert isinstance(why_one_member(result), EveryOtherIsDominated)


def test_a_set_of_several_says_the_question_does_not_arise() -> None:
    result = sections.result(sections.section())
    reading = why_one_member(result)
    assert isinstance(reading, TheSetDoesNotHaveOneMember)
    assert reading.members == len(result.non_dominated)


def test_the_populations_are_in_the_candidate_order_and_in_no_objectives_order() -> None:
    """FR-025. An order by an objective is the ranking this feature exists to refuse to present.

    Asserted against the **enumerated** order rather than against a re-derived sort key: 014
    FR-016 fixes that order, and a second sort rule here is where the two would disagree.
    """
    section = sections.section(sections.TWELVE_MONTHS)
    result = sections.result(section)
    survey = section.outcome
    order = [item.key for item in survey.enumerated.candidates]  # type: ignore[union-attr]
    for population in (
        list(result.non_dominated),
        [item.key for item in result.dominated],
        [item.key for item in result.not_placed],
    ):
        assert population == [key for key in order if key in set(population)]


def test_an_empty_set_is_reported_as_empty_rather_than_as_several_members() -> None:
    """The count is what says which way the question does not arise, and zero is one of them."""
    pair = sections.only(sections.section(), ["UA4000239016"])
    result = sections.result(sections.with_no_arrivals(pair, "UA4000239016"))
    reading = why_one_member(result)
    assert isinstance(reading, TheSetDoesNotHaveOneMember)
    assert reading.members == 0


def test_a_section_every_pair_of_which_is_incomparable_has_an_empty_set_honestly() -> None:
    """SC-004's own scoping, reached rather than argued.

    Two candidates whose only pair cannot be decided are **both** *not placed*, so the set is
    empty over a population **neither** member of which is placed -- which is why the never-empty
    guarantee is scoped to the placed population and not to the evaluated one.
    """
    pair = sections.only(sections.section(), ["UA4000239016"])
    planted = sections.with_no_arrivals(pair, "UA4000239016")
    result = sections.result(planted)
    assert len(result.not_placed) == 2
    assert not result.non_dominated
    assert not result.dominated


def test_a_set_of_one_beside_both_kinds_reports_the_counts() -> None:
    """FR-014's fourth case: *some mixture, in which case the counts say which*."""
    three = sections.only(sections.section(), ["UA4000239016", "UA4000238281"])
    planted = sections.with_no_arrivals(three, "UA4000238281")
    result = sections.result(planted)
    reading = why_one_member(result)
    assert isinstance(reading, Mixed)
    assert reading.dominated == len(result.dominated)
    assert reading.not_placed == len(result.not_placed)
    assert reading.dominated
    assert reading.not_placed


def test_the_readings_this_pass_can_produce_are_distinguishable_without_prose() -> None:
    """FR-014's own requirement, over the four the pass reaches.

    ``EveryOtherIsNotPlaced`` is the fifth and is **not** among them, for the reason
    ``why_one_member`` states at its own site: it would need exactly one placed candidate, and a
    candidate is placed only by a decided pair with another -- which places that one too.
    """
    lone = why_one_member(sections.result(sections.only(sections.section(), [])))
    beaten = why_one_member(sections.result(sections.only(sections.section(), ["UA4000239016"])))
    mixed = why_one_member(
        sections.result(
            sections.with_no_arrivals(
                sections.only(sections.section(), ["UA4000239016", "UA4000238281"]),
                "UA4000238281",
            )
        )
    )
    several = why_one_member(sections.result(sections.section()))
    assert len({type(reading) for reading in (lone, beaten, mixed, several)}) == 4
