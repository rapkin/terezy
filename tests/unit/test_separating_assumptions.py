"""SC-010: what the set's members do not share is named, verbatim, and never composed.

019 FR-015, FR-019, FR-020. ``docs/DIRECTION.md``'s own formulation of an honest output is the
non-dominated set with the assumption that separates its members named -- so a reader can see
that the choice between two options is a choice between two beliefs rather than between two
numbers.

**Three cases, because each is a different way for the requirement to be quietly
unimplemented**: members resting on different assumptions, members resting on identical ones,
and members whose *section-level exclusions* differ. The third is the one an implementation
reading ``TupleOutcome.excludes`` would fail silently: measured, that field is identical across
every candidate of the owner's question while the section's records differ per candidate.
"""

from __future__ import annotations

from dataclasses import replace

from terezy.core.decision.answer import section_evaluated
from terezy.core.results.dominance import (
    NoStatedAssumptionSeparatesThem,
    SeparatingAssumptions,
)
from tests import dominance_sections as sections


def test_two_members_resting_on_different_assumptions_name_the_difference() -> None:
    """Measured on the owner's own one-month set: one member rests on the continuation
    assumption -- its money is back before the window ends and sits as cash -- and the other
    rests on the early-exit belief instead."""
    section = sections.section()
    result = sections.result(section)
    separating = result.separating
    assert isinstance(separating, SeparatingAssumptions)
    assert len(separating.per_member) == len(result.non_dominated)
    assert any(item.rests_on for item in separating.per_member)


def test_every_word_is_carried_byte_for_byte_from_the_record_it_came_from() -> None:
    """FR-019's *verbatim*: nothing here composes a sentence of its own."""
    section = sections.section()
    result = sections.result(section)
    separating = result.separating
    assert isinstance(separating, SeparatingAssumptions)
    claims = {item.key: item.rests_on for item in section_evaluated(section)}
    for member in separating.per_member:
        assert set(member.rests_on) <= set(claims[member.key])


def test_the_section_level_exclusions_are_what_a_difference_is_read_from() -> None:
    """FR-015. ``TupleOutcome.excludes`` is identical across the population and the section's
    records are not, so an implementation reading the outcome's fixed set would report *nothing
    separates them* for every set there is -- asserted here as the fact it rests on."""
    section = sections.section()
    outcomes = section_evaluated(section)
    assert len({item.excludes for item in outcomes}) == 1
    per_candidate = {
        item.key: {
            excluded.what for excluded in section.excludes if excluded.applies_to == item.key
        }
        for item in outcomes
    }
    assert len({frozenset(value) for value in per_candidate.values()}) > 1

    separating = sections.result(section).separating
    assert isinstance(separating, SeparatingAssumptions)
    assert any(item.excludes for item in separating.per_member)


def test_members_resting_on_identical_assumptions_produce_the_typed_statement() -> None:
    """FR-020: a typed statement rather than an empty list, which a reader takes as *nothing
    separates them* when the truth is *the same beliefs are behind all of them*.

    Planted by giving every candidate one member's ``rests_on`` and stripping the section's own
    exclusion records, so the members differ in figures and in nothing else.
    """
    section = sections.section()
    shared = section_evaluated(section)[0].rests_on
    identical = replace(
        sections.with_outcomes(section, lambda item: replace(item, rests_on=shared)),
        excludes=(),
    )
    result = sections.result(identical)
    assert len(result.non_dominated) > 1, "one member cannot show what several share"
    assert isinstance(result.separating, NoStatedAssumptionSeparatesThem)


def test_nothing_claims_which_assumption_decides() -> None:
    """FR-021, as a value check beside the scan that asserts the absence of a field.

    Naming the deciding assumption requires re-evaluating under a changed assumption, which is
    required test I5's feature. What is reported is the assumptions that differ.
    """
    separating = sections.result(sections.section()).separating
    assert isinstance(separating, SeparatingAssumptions)
    for member in separating.per_member:
        assert set(member.__slots__) == {"key", "rests_on", "excludes"}
