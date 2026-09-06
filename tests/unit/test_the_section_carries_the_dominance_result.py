"""SC-016a: the section carries the dominance result **beside** the survey and changes nothing.

019 FR-023, FR-025, FR-027, FR-028. Two *do not break what exists* requirements, which is the
kind an implementation passes silently unless something asserts them:

* the survey a section reports equals, field for field, the one 014's ``survey`` returned for
  that section -- stated against the survey the pass was **handed** rather than against a run
  with no objectives declared, which FR-001 makes unproducible;
* the ``Answer`` carries no string this feature composed. Every string it adds is an id, a
  criterion name, or a reason another core record already wrote.
"""

from __future__ import annotations

import ast
from dataclasses import fields, is_dataclass

import pytest

from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.staleness import StalenessVerdict
from terezy.core.results.dominance import DominanceResult
from terezy.core.results.objectives import Criterion, ObjectiveDirection
from tests import answer_registries as fixtures
from tests import data_roots
from tests import dominance_sections as sections
from tests.source_scan import executable_source

HORIZONS = [sections.ONE_MONTH, sections.THREE_MONTHS, sections.TWELVE_MONTHS]


@pytest.mark.parametrize("index", HORIZONS)
def test_the_survey_the_section_reports_is_the_one_the_pass_was_handed(index: int) -> None:
    """FR-027: the result replaces, reorders and summarises nothing in the survey."""
    section = sections.section(index)
    survey = section.outcome
    assert survey is section.outcome
    recomputed = sections.run(section)
    assert isinstance(recomputed, DominanceResult)
    assert section.outcome is survey, "the pass moved the survey it was handed"


@pytest.mark.parametrize("index", HORIZONS)
def test_the_section_carries_the_result_the_pass_produces_for_its_own_parts(index: int) -> None:
    section = sections.section(index)
    assert section.dominance == sections.run(section)


@pytest.mark.parametrize("index", HORIZONS)
def test_the_whole_declared_set_travels_beside_every_population_it_counts(index: int) -> None:
    """FR-023: a dominance count read without the objectives that produced it is meaningless,
    and the objectives are the one input a reader is most likely to assume."""
    result = sections.section(index).dominance
    assert isinstance(result, DominanceResult)
    assert result.objectives == sections.objectives()
    assert [objective.criterion for objective in result.objectives.objectives] == [
        Criterion.MONEY_AT_THE_ENDPOINT,
        Criterion.ALL_MONEY_BACK_ON,
    ]
    assert result.objectives.objectives[1].direction is ObjectiveDirection.LESS_IS_BETTER


@pytest.mark.parametrize("index", HORIZONS)
def test_a_fraction_band_travels_with_the_width_it_resolved_to(index: int) -> None:
    """FR-023's second half: a fraction reported without its width is a band nobody can check
    against a figure."""
    result = sections.section(index).dominance
    assert isinstance(result, DominanceResult)
    assert result.resolved_bands
    for band in result.resolved_bands:
        assert band.width.currency is band.from_amount.currency


def _strings(value: object, seen: set[int] | None = None) -> set[str]:
    """Every string reachable in the answer's dominance results, walked generically.

    Provenance and staleness are stepped over: they travel with every figure and are not
    figures, and the citations they carry are the words of the declarations they came from --
    which is the opposite of a string this feature composed. They are what
    ``tests/unit/test_dominance_provenance.py`` walks instead.
    """
    seen = set() if seen is None else seen
    if id(value) in seen:
        return set()
    seen.add(id(value))
    if isinstance(value, Provenance | StalenessVerdict):
        return set()
    if isinstance(value, str):
        return {value}
    if is_dataclass(value) and not isinstance(value, type):
        return {
            text for field in fields(value) for text in _strings(getattr(value, field.name), seen)
        }
    if isinstance(value, tuple | list | frozenset | set):
        return {text for item in value for text in _strings(item, seen)}
    return set()


def test_the_answer_holds_no_string_this_feature_composed() -> None:
    """FR-028, on 015 SC-003's technique, and asserted from **both** sides.

    Every string the dominance results hold is either a vocabulary token -- an id, a criterion,
    a direction -- or a reason another core record already wrote, and the walk below finds them
    all rather than sampling.
    """
    answered = fixtures.answered()
    held: set[str] = set()
    for section in answered.sections:
        held |= _strings(section.dominance)
    assert held, "the walk found no strings at all, so it proves nothing"

    outcomes = {
        text
        for section in answered.sections
        for item in section.outcome.comparison.ranked  # type: ignore[union-attr]
        for text in (*item.rests_on, *item.excludes, *item.accounts_for)
    }
    vocabulary = (
        {member.value for member in Criterion}
        | {member.value for member in ObjectiveDirection}
        | _strings(answered.question)
        # Every id the question's words resolved to. A ranked candidate's key holds one, and
        # until 023 they all arrived incidentally through `rests_on`; a balance rests on
        # nothing, so the vocabulary is now complete by construction rather than by luck.
        | {text for item in answered.subjects for text in _strings(item)}
        | _strings(answered.excludes)
        | {text for section in answered.sections for text in _strings(section.excludes)}
        | outcomes
        | {"TupleOutcome.arrivals"}
    )
    assert not held - vocabulary, sorted(held - vocabulary)


def test_no_record_this_feature_declares_composes_a_sentence() -> None:
    """The source half. A string literal in a **record** module would be a sentence a record
    holds, which is a decision taken on behalf of an interface nobody has chosen.

    ``__all__``'s own entries are the only strings there, and they are the module's export list
    rather than anything a record carries -- so they are excluded by name and everything else is
    a failure.
    """
    source = executable_source(
        data_roots.REPO_ROOT / "src" / "terezy" / "core" / "results" / "dominance.py"
    )
    tree = ast.parse(source)
    exported = {
        node.value
        for assignment in ast.walk(tree)
        if isinstance(assignment, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in assignment.targets
        )
        for node in ast.walk(assignment)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value not in exported
    ]
    assert exported, "the export list was not found, so the exclusion above hides everything"
    assert not literals, literals
