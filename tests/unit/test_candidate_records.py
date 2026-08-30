"""What the types claim, where a later change could break the claim with every behaviour green.

FR-014's two no-candidate reasons stay two records, research D5's two unions stay nested, and
FR-006's union stays at seventeen.
"""

from __future__ import annotations

import dataclasses
from typing import get_args

from terezy.core.results import candidates as rec
from terezy.core.results.tuple import TupleRefused


class TestTheTwoNoCandidateReasonsAreDifferentTypes:
    def test_they_are_two_records_and_not_one_with_a_flag(self) -> None:
        members = set(get_args(rec.NoCandidateReason))
        assert members == {rec.NothingConnects, rec.NothingNeedsToConnect}

    def test_neither_carries_a_field_that_could_hold_the_other_s_claim(self) -> None:
        """A discriminator field on either would be a second place the distinction lives, and
        the day the two disagreed nothing would say which was authoritative."""
        connects = {field.name for field in dataclasses.fields(rec.NothingConnects)}
        needs = {field.name for field in dataclasses.fields(rec.NothingNeedsToConnect)}
        assert connects == {"side", "reason"}
        assert needs == {"refusal"}


class TestTheTwoRefusalUnions:
    def test_every_enumeration_refusal_is_also_a_survey_refusal(self) -> None:
        assert set(get_args(rec.EnumerationRefused)) <= set(get_args(rec.SurveyRefused))

    def test_the_survey_only_refusals_are_the_two_about_handing_the_set_to_compare(self) -> None:
        extra = set(get_args(rec.SurveyRefused)) - set(get_args(rec.EnumerationRefused))
        assert extra == {rec.BenchmarkNotACandidate, rec.MoreThanOneStreamInTheSet}


class TestThisFeatureAddsNoEighteenthRefusal:
    def test_the_pruning_union_still_has_seventeen_members(self) -> None:
        """Pinned in 010's suite too, and not one fact twice: that one asserts the union's size,
        this one asserts *this* feature did not grow it. Different changes edit each."""
        assert len(get_args(TupleRefused)) == 17

    def test_no_record_in_this_module_is_a_feasibility_verdict(self) -> None:
        """A candidate-level refusal here would be the eighteenth by the back door: the union
        unchanged and a second opinion beside it."""
        assert not hasattr(rec, "CandidateRefused")
        assert rec.RefusedTuple.__module__ == "terezy.core.results.tuple"
