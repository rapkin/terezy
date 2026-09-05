"""FR-011 and SC-007: the tally is derived, and it names the declarations to go and fix.

Each group names the distinct instruments, streams, routes and missing declarations its members
implicate, so *twelve candidates dropped, all wanting the same undeclared tax class* is readable
without opening twelve records.

The fixture plants more than one reason at once. A battery whose every drop shared one reason
would pass with the grouping key hard-coded, which is the mutation it exists to catch.
"""

from __future__ import annotations

import collections
from dataclasses import replace
from typing import TYPE_CHECKING

from terezy.core.decision.candidates import drop_tally, dropped, survey
from terezy.core.primitives.money import Money
from terezy.core.results.candidates import CandidateSurvey
from terezy.core.results.tuple import DeclarationMissing
from terezy.core.routes.path import ExitChain, exit_segments_of, segments_of
from tests import candidate_registries as fixtures

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from terezy.core.decision.tuple_outcome import Registries
    from terezy.core.results.candidates import DropGroup
    from terezy.core.results.tuple import RefusedTuple

BENCHMARK = "ovdp_synthetic_a"
GOVERNMENT_BOND = "ua_government_bond"


def _three_faults() -> Registries:
    """One registry carrying unrelated faults, so more than one group is populated.

    The bonds' tax class is gone, so every candidate naming it wants a declaration; one
    instrument's proceeds land where no exit departs from; and the two pegged funds still refuse
    on their own declared terms, untouched.
    """
    registries = fixtures.declared()
    classes = {
        class_id: declared
        for class_id, declared in registries.tax_classes.items()
        if class_id != GOVERNMENT_BOND
    }
    return fixtures.with_access(
        replace(registries, tax_classes=classes), "inzhur_miltech", proceeds_to="binance"
    )


def _drops(registries: Registries, amount: Money | None = None) -> tuple[RefusedTuple, ...]:
    question = fixtures.question(
        registries, amounts=None if amount is None else {fixtures.SALARY: amount}
    )
    result = survey(
        registries=registries,
        routes=registries.routes,
        question=question,
        ceiling=fixtures.ceiling(10_000),
        benchmark=fixtures.benchmark_key(registries, BENCHMARK, question_=question),
    )
    assert isinstance(result, CandidateSurvey), result
    return dropped(result.comparison)


def _groups(registries: Registries, amount: Money | None = None) -> tuple[DropGroup, ...]:
    return drop_tally(_drops(registries, amount))


def test_the_fixture_produces_more_than_one_reason() -> None:
    """The control. Without it every assertion below would pass on a single-reason tally."""
    assert len({group.refusal for group in _groups(_three_faults())}) > 1


def test_the_counts_sum_to_the_records_they_group() -> None:
    drops = _drops(_three_faults())
    assert sum(group.count for group in drop_tally(drops)) == len(drops)


def test_every_group_matches_a_tally_recomputed_here_by_hand() -> None:
    """SC-007, recomputed **independently** rather than by calling the same function twice.

    Comparing `drop_tally(x)` with `drop_tally(x)` proves only that the function is a function.
    What the criterion asks is that the reported grouping is the grouping the retained records
    actually have, so the counts and the implicated ids are rebuilt from the records here.
    """
    drops = _drops(_three_faults())
    by_reason: dict[str, list[RefusedTuple]] = collections.defaultdict(list)
    for item in drops:
        by_reason[type(item.refusal).__name__].append(item)

    reported = {group.refusal: group for group in drop_tally(drops)}
    assert set(reported) == set(by_reason)
    for name, members in by_reason.items():
        group = reported[name]
        assert group.count == len(members)
        assert group.instruments == tuple(sorted({item.key.instrument_id for item in members}))
        assert group.streams == tuple(sorted({item.key.stream_id for item in members}))
        assert group.routes == tuple(
            sorted(
                {name for item in members for name in segments_of(item.key.route_in)}
                | {
                    name
                    for item in members
                    if isinstance(item.key.route_out, ExitChain)
                    for name in exit_segments_of(item.key.route_out)
                }
            )
        )
        assert group.missing == tuple(
            sorted(
                {
                    item.refusal.what
                    for item in members
                    if isinstance(item.refusal, DeclarationMissing)
                }
            )
        )


def test_it_is_grouped_by_the_records_type_and_not_by_its_words() -> None:
    """Two refusals of one type carrying different sentences are one group, so the day a
    sentence is edited for clarity no group splits."""
    drops = _drops(_three_faults())
    instrument = [item for item in drops if type(item.refusal).__name__ == "InstrumentRefused"]
    assert len({item.refusal.reason for item in instrument}) > 1
    group = next(item for item in drop_tally(drops) if item.refusal == "InstrumentRefused")
    assert group.count == len(instrument)


def test_a_group_naming_no_missing_declaration_leaves_that_field_empty() -> None:
    """The field says *this reason implicates no absent declaration*, which is a different
    claim from a group nobody looked at."""
    groups = {group.refusal: group for group in _groups(_three_faults())}
    assert groups["InstrumentRefused"].missing == ()
    assert any(GOVERNMENT_BOND in item for item in groups["DeclarationMissing"].missing)


def test_the_groups_are_sorted_so_two_runs_report_them_in_one_order() -> None:
    names = [group.refusal for group in _groups(_three_faults())]
    assert names == sorted(names)


def test_the_tally_moves_with_the_amount_the_question_states() -> None:
    """SC-016: two amounts over one registry produce two tallies, so a count reported without
    its question is a figure more confident than its inputs."""
    registries = fixtures.declared()
    generous = {group.refusal: group.count for group in _groups(registries)}
    stingy = {
        group.refusal: group.count
        for group in _groups(registries, Money(1.0, fixtures.UAH, fixtures.AMOUNT_UAH.provenance))
    }
    assert generous != stingy
    assert "BelowMinimumTicket" in stingy


def test_the_tally_moves_with_the_horizon_too() -> None:
    """The other half of SC-016. The horizon sets the projection window, so a date-carrying
    refusal moves with it -- which is why FR-012 states the requirement over the whole
    question rather than over a list of the amount-sensitive members."""
    registries = fixtures.declared()
    question = fixtures.question(registries)
    short = replace(question, horizon=replace(question.horizon, end=question.horizon.start))
    result = survey(
        registries=registries,
        routes=registries.routes,
        question=short,
        ceiling=fixtures.ceiling(10_000),
        benchmark=fixtures.benchmark_key(registries, BENCHMARK, question_=short),
    )
    assert isinstance(result, CandidateSurvey), result
    assert {group.refusal: group.count for group in drop_tally(dropped(result.comparison))} != {
        group.refusal: group.count for group in _groups(registries)
    }
