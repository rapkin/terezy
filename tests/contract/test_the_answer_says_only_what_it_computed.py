"""Four properties of the answer that no type can carry, asserted by walking the whole result.

015 SC-003, SC-004, SC-017, SC-021, SC-025 and SC-026.

* **No string this feature composed.** The ``Answer`` is the API's contract with an interface
  nobody has chosen, and a sentence in it is a rendering decision taken on that interface's
  behalf. Every string on a record this feature defines is an id, a date, an enum member or one
  of the named constants that say what would supply an exclusion.
* **No rate derived and none read from a series.** Scoped to *this feature's* modules, because
  FR-021a requires a question to carry an owner-**stated** rate and the loader that reads one is
  shared with every other declaration.
* **Marks survive.** Verified by a walk over the whole result rather than by sampling: the
  shipped set is both unverified and synthetic, so an answer presenting a clean figure would be
  presenting a fixture as an observation.
* **The exclusions and the absences are checked against each other**, so neither can drift.
"""

from __future__ import annotations

import dataclasses
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any, Final

import pytest

from terezy.core.decision import answer as verb
from terezy.core.decision.answer import section_evaluated
from terezy.core.instruments.interface import DateRange
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.rates import RealRate, RealTermsUnavailable
from terezy.core.results import answer as records
from terezy.core.results import question as question_records
from terezy.core.results.answer import Answer, Direction, Exclusion
from terezy.core.scenarios import early_exit
from tests import answer_registries as fixtures

pytestmark = pytest.mark.contract

THIS_FEATURES_MODULES: Final = (
    Path(verb.__file__),
    Path(records.__file__),
    Path(question_records.__file__),
    Path(fixtures.REPO_ROOT / "src" / "terezy" / "api" / "answer.py"),
    Path(fixtures.REPO_ROOT / "src" / "terezy" / "cli" / "main.py"),
)

FORBIDDEN_IN_THIS_FEATURE: Final = (
    "official_rate",
    "reference_rate",
    "money.convert",
    "from_pegged_term",
)
"""Every way a rate could reach a figure here. **Not** ``exchange_rate``: FR-021a requires the
owner to be able to *state* one, and forbidding the word would forbid the record he states."""

ANSWER_WIDE: Final = frozenset(
    {Exclusion.NO_REAL_TERMS_FIGURE, Exclusion.NO_INCOME_TAX_ON_THE_STATED_AMOUNT}
)

EARLY_EXIT_CLAIMS: Final = frozenset(
    {
        Exclusion.EARLY_EXIT_IS_A_POINT_NOT_A_DISTRIBUTION,
        Exclusion.EARLY_EXIT_SPREAD_IS_A_SELLERS_QUOTE,
        Exclusion.EARLY_EXIT_CARRIES_NO_RATE_RISK,
    }
)


def _walk(value: object, seen: set[int] | None = None) -> list[object]:
    """Every record, string and figure reachable from a result, once each."""
    seen = set() if seen is None else seen
    if id(value) in seen:
        return []
    seen.add(id(value))
    found: list[object] = [value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for field in dataclasses.fields(value):
            found.extend(_walk(getattr(value, field.name), seen))
    elif isinstance(value, tuple | list | frozenset | set):
        for item in value:
            found.extend(_walk(item, seen))
    elif isinstance(value, dict):
        for key, item in value.items():
            found.extend(_walk(key, seen))
            found.extend(_walk(item, seen))
    return found


def _strings_this_feature_holds(result: Answer) -> set[str]:
    """Every string field of every record **this feature defines**, reachable from the answer."""
    mine = {
        name
        for module in (records, question_records)
        for name, value in vars(module).items()
        if isinstance(value, type)
        and dataclasses.is_dataclass(value)
        and value.__module__ == module.__name__
    }
    strings: set[str] = set()
    for item in _walk(result):
        if not dataclasses.is_dataclass(item) or isinstance(item, type):
            continue
        if type(item).__name__ not in mine:
            continue
        for field in dataclasses.fields(item):
            value: Any = getattr(item, field.name)
            if isinstance(value, str):
                strings.add(value)
            elif isinstance(value, tuple) and all(isinstance(entry, str) for entry in value):
                strings.update(value)
    return strings


def _vocabulary(result: Answer) -> set[str]:
    """Every string an answer is *entitled* to hold: ids, declared words and named constants."""
    registries = fixtures.declarations().tuples.registries
    return {
        *registries.instruments,
        *registries.funds,
        *registries.streams,
        *registries.access,
        *registries.routes,
        *result.question.subjects,
        result.question.id,
        result.question.owner_id,
        result.question.regime_id,
        result.question.benchmark_instrument_id,
        result.question.continuation.value,
        *(member.value for member in Exclusion),
        *(member.value for member in Direction),
        verb.REAL_TERMS_SUPPLIED_BY,
        verb.INCOME_TAX_SUPPLIED_BY,
        verb.RATE_RISK_SUPPLIED_BY,
        registries.spread_holds.id,
    }


def test_the_answer_holds_no_string_this_feature_composed() -> None:
    """SC-003. Every string on this feature's own records is an id or a named constant."""
    result = fixtures.answered()
    composed = _strings_this_feature_holds(result) - _vocabulary(result)
    assert not composed, sorted(composed)


def test_the_early_exit_answer_holds_no_composed_string_either() -> None:
    """The path that adds three exclusions, walked as well as the shipped one."""
    result = fixtures.answered(
        supplied=fixtures.with_resale_price(fixtures.inputs(), "ovdp_synthetic_a")
    )
    composed = _strings_this_feature_holds(result) - _vocabulary(result)
    assert not composed, sorted(composed)


@pytest.mark.parametrize("module", THIS_FEATURES_MODULES, ids=lambda path: path.name)
def test_no_module_of_this_feature_derives_a_rate(module: Path) -> None:
    """SC-004, scoped so the owner-stated assumption FR-021a requires is not caught."""
    source = module.read_text(encoding="utf-8")
    executable = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    for token in FORBIDDEN_IN_THIS_FEATURE:
        assert token not in executable, f"{module.name} mentions {token!r}"


def test_the_two_answer_wide_exclusions_are_always_stated() -> None:
    """SC-021's first half. An exclusion that is not stated is a silent default."""
    result = fixtures.answered()
    stated = {item.what for item in result.excludes if item.applies_to is None}
    assert stated == ANSWER_WIDE


def test_no_real_terms_figure_appears_anywhere_in_the_result() -> None:
    """SC-021's second half: the exclusion and the absence checked against each other."""
    walked = _walk(fixtures.answered())
    assert not [item for item in walked if isinstance(item, RealRate | RealTermsUnavailable)]


def test_every_figure_the_shipped_answer_reports_carries_the_marks_of_its_registry() -> None:
    """SC-017, by a walk over the whole result rather than by sampling.

    The shipped registry is entirely unverified, so a figure that came back clean would be
    reporting a fixture as an observation.
    """
    result = fixtures.answered()
    assert prov.is_unverified(result.provenance)
    for section in result.sections:
        for outcome in section_evaluated(section):
            assert prov.is_unverified(outcome.provenance), outcome.key.instrument_id


def test_the_answers_marks_are_the_union_of_what_its_figures_rest_on() -> None:
    """A merge that dropped one would be a top-severity defect rather than a cosmetic one."""
    result = fixtures.answered()
    for section in result.sections:
        for outcome in section_evaluated(section):
            assert outcome.provenance.sources <= result.provenance.sources


def test_every_early_exit_figure_names_the_assumption_it_rests_on() -> None:
    """SC-025, by a walk: the implementable half of the criterion, and the one that catches it."""
    supplied = fixtures.with_resale_price(fixtures.inputs(), "ovdp_synthetic_a")
    result = fixtures.answered(supplied=supplied)
    sold = [
        outcome
        for section in result.sections
        for outcome in section_evaluated(section)
        if outcome.sold_early is not None
    ]
    assert sold, "the fixture must actually reach an early exit"
    expected = early_exit.rests_on(supplied.registries.spread_holds)
    for outcome in sold:
        assert expected in outcome.rests_on, outcome.rests_on


def test_an_early_exit_claim_appears_exactly_where_a_holding_was_sold_early() -> None:
    """The machinery is reachable only where an early exit actually happens, and it IS reached:
    016 declared 24 real issues with an observed resale price and most run past every horizon
    the owner asked about. An `if` here rather than a `not` -- the claim is the equivalence, and
    a section that carried the exclusion without selling anything would be marking a figure it
    did not earn."""
    result = fixtures.answered()
    claimed = [
        any(item.what in EARLY_EXIT_CLAIMS for item in section.excludes)
        for section in result.sections
    ]
    sold = [
        any(outcome.sold_early is not None for outcome in section_evaluated(section))
        for section in result.sections
    ]
    assert claimed == sold
    assert any(sold), "the shipped registry must actually reach an early exit"


def test_a_section_that_holds_to_maturity_inherits_no_early_exit_claim() -> None:
    """The exclusion is specific to a candidate **in a window**, not to a candidate.

    One key can be an early exit at one month and a hold-to-maturity at twelve. An exclusion
    carried on the answer would tag both, which is a mark the second figure did not earn --
    exactly the edge case FR-033 names.
    """
    question = fixtures.owners_question()
    both = replace(
        question,
        subjects=("ovdp_synthetic_a",),
        plans={"ovdp_synthetic_a": question.plans["ovdp"]},
        horizons=(
            DateRange(start=date(2026, 9, 1), end=date(2027, 6, 1)),
            DateRange(start=date(2026, 9, 1), end=date(2028, 6, 1)),
        ),
    )
    # ONE instrument, because the claim is about one key across two windows. Left over the whole
    # registry the second section would carry the exclusion honestly -- a real issue maturing in
    # 2029 is sold at 2028-06-01 -- and the demonstration would prove nothing about this key.
    result = fixtures.answered(
        both, fixtures.with_resale_price(fixtures.inputs(), "ovdp_synthetic_a")
    )
    sold, held = result.sections
    assert any(item.sold_early is not None for item in section_evaluated(sold))
    assert all(item.sold_early is None for item in section_evaluated(held))
    assert [item.what for item in sold.excludes if item.what in EARLY_EXIT_CLAIMS]
    assert not [item.what for item in held.excludes if item.what in EARLY_EXIT_CLAIMS]


def test_an_early_exit_states_three_claims_and_signs_exactly_two() -> None:
    """SC-026. The absence of a direction on rate risk is **asserted**, not tolerated.

    Rate risk is symmetric -- a bond sold after rates rise fetches less than its spread implies
    and one sold after rates fall fetches more -- and an approximation whose sign is asserted
    without a warrant is a number more confident than its inputs, which is worse than none.
    """
    result = fixtures.answered(
        supplied=fixtures.with_resale_price(fixtures.inputs(), "ovdp_synthetic_a")
    )
    specific = [
        item
        for section in result.sections
        for item in section.excludes
        if item.applies_to is not None
    ]
    assert specific
    assert not [item for item in result.excludes if item.applies_to is not None]
    by_claim = {item.what: item for item in specific}
    assert set(by_claim) == EARLY_EXIT_CLAIMS
    assert by_claim[Exclusion.EARLY_EXIT_IS_A_POINT_NOT_A_DISTRIBUTION].direction is not None
    assert by_claim[Exclusion.EARLY_EXIT_SPREAD_IS_A_SELLERS_QUOTE].direction is not None
    assert by_claim[Exclusion.EARLY_EXIT_CARRIES_NO_RATE_RISK].direction is None


def test_every_exclusion_names_what_would_supply_it() -> None:
    """FR-023a: a feature or a declaration, never a search."""
    for item in fixtures.answered().excludes:
        assert item.supplied_by.strip()
