"""The shapes the feature rests on, and the fields it deliberately does not have.

FR-013 says a composed candidate is *"its own kind of candidate, visibly distinct from a
hand-declared route in every ranking, report and recommendation"*, and that **the distinction
is structural, not decorative**. This module is that sentence held to: two types matched with
``match``, no boolean flag, no route id that sometimes holds a joined string.

**Half of what is asserted here is an absence**, and that is the point. A routing search is
exactly where a composite score sneaks into a user-visible ordering (required test **B12**), and
combining per-leg disruption probabilities requires an independence assumption nobody declared
(FR-019). A comment saying so is what gets deleted by the next contributor who "just needs a
single number for the ranking"; a missing field is not.
"""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import assert_never

import pytest

from terezy.core.results import composed, ramp
from terezy.core.routes import path as path_module
from terezy.core.routes.path import (
    EXIT_BY_IDENTITY,
    FROM_THE_DECLARATION,
    Candidate,
    ComposedExit,
    ComposedPath,
    DeclaredExit,
    ExitChain,
    FundingPath,
    Journey,
    Segment,
)

DECLARED = FundingPath(destination_id="broker", stream_id="salary_uah", route_id="in_a")
COMPOSED = ComposedPath(destination_id="broker", stream_id="salary_uah", segments=("in_a", "in_b"))


def _kind(candidate: Candidate) -> str:
    """A ``match`` over the union, which is the whole of FR-013's structural claim.

    Written out rather than asserted with ``isinstance`` because the requirement is that a
    reader *can* dispatch on the two kinds: if the union ever collapses to one type with a flag,
    this stops compiling as an exhaustive match and ``assert_never`` becomes reachable.
    """
    match candidate:
        case FundingPath():
            return "declared"
        case ComposedPath():
            return "composed"
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(candidate)


class TestTheTwoKindsOfCandidateAreTwoTypes:
    def test_a_declared_route_and_a_chain_are_distinguished_by_type(self) -> None:
        assert _kind(DECLARED) == "declared"
        assert _kind(COMPOSED) == "composed"

    def test_neither_kind_carries_a_boolean_flag_saying_which_it_is(self) -> None:
        """A flag is the decorative version FR-013 rules out.

        It is also the version that goes wrong quietly: a ``FundingPath`` whose ``route_id``
        sometimes holds one id and sometimes a joined string reads fine at every call site and
        is unparseable at exactly one -- the report that has to say which declarations a
        comparison rests on.
        """
        names = {field.name for field in dataclasses.fields(DECLARED)} | {
            field.name for field in dataclasses.fields(COMPOSED)
        }
        assert not [name for name in names if "composed" in name or name.startswith("is_")]

    def test_the_declared_path_gained_nothing(self) -> None:
        """002's record means exactly what it meant, so no existing consumer changed behaviour."""
        assert [field.name for field in dataclasses.fields(FundingPath)] == [
            "destination_id",
            "stream_id",
            "route_id",
        ]

    def test_segments_of_reads_both_kinds_as_one_chain(self) -> None:
        assert path_module.segments_of(DECLARED) == ("in_a",)
        assert path_module.segments_of(COMPOSED) == ("in_a", "in_b")

    def test_positions_are_numbered_from_zero_across_the_chain(self) -> None:
        assert path_module.positions_of(COMPOSED) == (
            Segment(position=0, route_id="in_a"),
            Segment(position=1, route_id="in_b"),
        )
        assert path_module.positions_of(DECLARED) == (Segment(position=0, route_id="in_a"),)

    def test_a_declared_route_is_one_segment_and_that_is_not_a_special_case(self) -> None:
        """research.md D7. Attribution over one segment is attribution, not an exception."""
        assert len(path_module.positions_of(DECLARED)) == 1


class TestTheExitChainHasExactlyThreeShapes:
    def test_each_shape_is_a_distinct_value(self) -> None:
        shapes: list[ExitChain] = [
            DeclaredExit(route_id="out_a"),
            ComposedExit(segments=("out_a", "out_b")),
            EXIT_BY_IDENTITY,
        ]
        assert len({repr(shape) for shape in shapes}) == 3
        assert shapes[0] != shapes[1]
        assert shapes[2] != shapes[1]

    def test_the_identity_case_is_a_value_and_not_an_empty_chain(self) -> None:
        """A round trip that costs nothing **because there is nothing to do** is a different
        claim from one whose fees happened to cancel, and only a distinct value carries it.

        An empty ``ComposedExit`` would erase the difference: a reader of a ranking could not
        tell "the money is already spendable" from "the way out was free", and Principle I is
        exactly about not letting those two produce the same output.

        ⚙ **The comparison this test would naturally make does not typecheck**, and that is the
        stronger result: ``EXIT_BY_IDENTITY == ComposedExit(segments=())`` is a
        ``comparison-overlap`` error under strict mypy, because the two have no common type. So
        the guarantee is not "they are unequal at run time" but "they cannot be confused at
        all", and what is asserted below is the shape that makes it so.
        """
        identity: ExitChain = EXIT_BY_IDENTITY
        assert isinstance(identity, Enum)
        assert identity is not None
        assert not dataclasses.is_dataclass(identity)
        assert path_module.exit_segments_of(identity) == ()

    def test_the_segments_of_an_exit_chain_read_uniformly(self) -> None:
        assert path_module.exit_segments_of(DeclaredExit(route_id="out_a")) == ("out_a",)
        assert path_module.exit_segments_of(ComposedExit(segments=("out_a", "out_b"))) == (
            "out_a",
            "out_b",
        )
        assert path_module.exit_segments_of(EXIT_BY_IDENTITY) == ()


class TestAJourneyPairsAWayInWithAWayOut:
    def test_a_bare_candidate_defers_to_what_the_declaration_says(self) -> None:
        """The unpaired case is not a missing value: it is *"use the way out that was
        declared"*, which is 002's rule (FR-027) and is named rather than defaulted to."""
        assert path_module.journey_of(DECLARED) == Journey(
            path=DECLARED, exit_path=FROM_THE_DECLARATION
        )

    def test_a_journey_passes_through_unchanged(self) -> None:
        journey = Journey(path=COMPOSED, exit_path=ComposedExit(segments=("out_a", "out_b")))
        assert path_module.journey_of(journey) is journey

    def test_two_exit_chains_from_one_path_are_two_journeys(self) -> None:
        """FR-012: the exit chain is part of the ranked unit's identity, so this pair is two
        candidates rather than one record holding two figures."""
        first = Journey(path=COMPOSED, exit_path=DeclaredExit(route_id="out_a"))
        second = Journey(path=COMPOSED, exit_path=ComposedExit(segments=("out_b", "out_c")))
        assert first != second
        assert len({first, second}) == 2


class TestTheFieldsThatAreDeliberatelyAbsent:
    """B12 and FR-019, asserted as absences because an absence cannot be deleted by accident."""

    FORBIDDEN = ("score", "rank_value", "estimate", "heuristic", "weight")

    @pytest.mark.parametrize(
        "record",
        [
            ComposedPath,
            Segment,
            ramp.RampCost,
            ramp.OneWayCost,
            ramp.RoundTripCost,
            ramp.SegmentAttribution,
            composed.Enumeration,
            composed.CompositionRefused,
        ],
    )
    def test_no_record_has_a_field_that_could_hold_a_path_score(self, record: type) -> None:
        names = [field.name for field in dataclasses.fields(record)]
        assert not [name for name in names if any(token in name for token in self.FORBIDDEN)], (
            f"{record.__name__} has a field a composite score could live in (B12)"
        )

    def test_the_only_probability_on_a_cost_is_the_per_leg_one_002_already_reported(self) -> None:
        """FR-019: no *combined* path-level figure, and no field for one.

        ``RampCost.disruption_probability`` is 002's largest-single-leg figure and stays exactly
        that -- a lower bound, reported beside the cost. What must not appear is a second field
        holding a compounded one, because compounding assumes the legs fail independently and
        nobody declared that.
        """
        names = [field.name for field in dataclasses.fields(ramp.RampCost)]
        assert [name for name in names if "probability" in name] == ["disruption_probability"]

    def test_an_enumeration_holds_no_number_at_all_beyond_its_bound(self) -> None:
        """The search produces candidates, never figures. A float on this record would be the
        first place a partial cost could be cached, and a partial cost is valid for one amount
        only."""
        types = {field.type for field in dataclasses.fields(composed.Enumeration)}
        assert not [name for name in types if "float" in str(name)]
