"""FR-016 and FR-017: the sequence is a function of the declarations and the caller's inputs.

Two runs of one question are equal element for element, and **a registry whose files sort
differently returns the same set in the same order** -- the second is the one that catches an
ordering that depends on the filesystem, which is invisible until the day a file is renamed.

FR-017's own half is separate and is the last test here: a run plan's order is its **position in
the caller's sequence**, so supplying two plans the other way round permutes those two
candidates and changes nothing else. A plan record holds a date, a chosen point and an
exchange-rate assumption; there is no ordering over those a reader could reproduce, and
inventing one would make the sequence depend on a comparison nobody asked for.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from terezy.core.decision.candidates import enumerate_candidates
from terezy.core.primitives.currency import Currency
from terezy.core.results.candidates import CandidateSet
from terezy.core.routes.path import candidate_id, exit_segments_of
from terezy.data.declarations import resolver
from tests import candidate_registries as fixtures
from tests import tuple_registries as tuples

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping

    from terezy.core.decision.tuple_outcome import Registries
    from terezy.core.results.tuple import InstrumentPlan

REIT = "inzhur_reit"


def _enumerate(
    registries: Registries, plans: Mapping[str, tuple[InstrumentPlan, ...]] | None = None
) -> CandidateSet:
    result = enumerate_candidates(
        registries=registries,
        routes=registries.routes,
        question=fixtures.question(registries, plans=plans),
        ceiling=fixtures.ceiling(10_000),
    )
    assert isinstance(result, CandidateSet), result
    return result


def test_the_same_question_twice_returns_an_equal_set_in_an_equal_order() -> None:
    first, second = _enumerate(fixtures.shipped()), _enumerate(fixtures.shipped())
    assert first.candidates == second.candidates
    assert first.no_candidate == second.no_candidate


def test_a_registry_whose_files_sort_differently_returns_the_same_sequence(
    tmp_path: Path,
) -> None:
    """SC-003's second half. The ids live *inside* the files, so renaming changes only the
    glob order the loader walks -- which is exactly the dependency this asserts is absent."""
    root = tmp_path / "data"
    shutil.copytree(fixtures.DATA_ROOT, root)
    for index, path in enumerate(sorted((root / "instruments").glob("*.toml"), reverse=True)):
        path.rename(path.with_name(f"{index:02d}-{path.name}"))
    shuffled = resolver.tuple_from_data_root(
        root, base_currency=Currency.UAH, scenario_id=None
    ).registries
    assert [item.key for item in _enumerate(shuffled).candidates] == [
        item.key for item in _enumerate(fixtures.shipped()).candidates
    ]


def test_the_sequence_is_the_one_fr016s_five_terms_imply() -> None:
    """The ordering **rule**, computed here from the declarations rather than read off the
    output. Asserting only that two runs agree pins determinism and says nothing about *which*
    order.

    Run over a registry where the middle terms actually discriminate. On the shipped
    declarations every candidate shares its stream, its way in, its way out and its plan
    position, so four of FR-016's five terms are inert and the assertion is really about
    ``instrument_id`` alone. A second inbound corridor and a second run plan give the way-in
    term and the position term something to order.
    """
    registries = tuples.with_new_route(
        fixtures.shipped(),
        tuples.route(
            "test_second_way_in",
            origin="monobank_uah",
            destination="inzhur",
            direction="inbound",
            fee_pct=0.02,
        ),
    )
    plans = dict(fixtures.one_plan_each(registries))
    plans[REIT] = (
        fixtures.fund_plan(registries.funds[REIT], exit_on=date(2027, 6, 30)),
        fixtures.fund_plan(registries.funds[REIT], exit_on=date(2028, 1, 17)),
    )
    produced = _enumerate(registries, plans).candidates
    assert produced
    assert len({candidate_id(item.key.route_in) for item in produced}) > 1
    assert len({item.plan_position for item in produced}) > 1
    expected = sorted(
        produced,
        key=lambda item: (
            item.key.instrument_id,
            item.key.stream_id,
            candidate_id(item.key.route_in),
            exit_segments_of(item.key.route_out),  # type: ignore[arg-type]
            item.plan_position,
        ),
    )
    assert list(produced) == expected


class TestARunPlansOrderIsItsPositionInTheCallersSequence:
    """FR-017 and SC-011: two plans for one fund, keyed apart and never blended."""

    @staticmethod
    def _two_plans(first_exit: date, second_exit: date) -> dict[str, tuple[InstrumentPlan, ...]]:
        registries = fixtures.shipped()
        plans = dict(fixtures.one_plan_each(registries))
        declared = registries.funds[REIT]
        plans[REIT] = (
            fixtures.fund_plan(declared, exit_on=first_exit),
            fixtures.fund_plan(declared, exit_on=second_exit),
        )
        return plans

    EARLY = date(2027, 6, 30)
    LATE = date(2028, 1, 17)

    def test_two_plans_yield_two_candidates_with_two_distinct_keys(self) -> None:
        produced = [
            item
            for item in _enumerate(
                fixtures.shipped(), self._two_plans(self.EARLY, self.LATE)
            ).candidates
            if item.key.instrument_id == REIT
        ]
        assert len(produced) == 2
        assert produced[0].key != produced[1].key
        assert [item.plan_position for item in produced] == [0, 1]

    def test_supplying_them_the_other_way_round_permutes_those_two_and_nothing_else(self) -> None:
        forwards = _enumerate(fixtures.shipped(), self._two_plans(self.EARLY, self.LATE))
        backwards = _enumerate(fixtures.shipped(), self._two_plans(self.LATE, self.EARLY))

        def elsewhere(result: CandidateSet) -> list[object]:
            return [item.key for item in result.candidates if item.key.instrument_id != REIT]

        assert elsewhere(forwards) == elsewhere(backwards)
        pair = [
            item.key.exit_terms for item in forwards.candidates if item.key.instrument_id == REIT
        ]
        flipped = [
            item.key.exit_terms for item in backwards.candidates if item.key.instrument_id == REIT
        ]
        assert pair == list(reversed(flipped))

    def test_the_position_is_recorded_and_not_read_back_off_the_order(self) -> None:
        """The claim FR-017 makes that the sequence alone cannot: the number on the record is
        the caller's index. Reading it off the sorted set would be reading the input off the
        output, and a sort that ignored the sequence would still satisfy that."""
        backwards = _enumerate(fixtures.shipped(), self._two_plans(self.LATE, self.EARLY))
        by_exit = {
            item.key.exit_terms.exit_on: item.plan_position  # type: ignore[union-attr]
            for item in backwards.candidates
            if item.key.instrument_id == REIT
        }
        assert by_exit == {self.LATE: 0, self.EARLY: 1}
