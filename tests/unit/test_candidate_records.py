"""What the types claim, where a later change could break the claim with every behaviour green.

FR-014's no-candidate reason names its side, research D5's two unions stay nested, and FR-006's
union is not grown by it.
"""

from __future__ import annotations

import dataclasses
from typing import get_args

from terezy.core.results import candidates as rec
from terezy.core.results.tuple import TupleRefused


class TestTheOneNoCandidateReason:
    def test_the_column_holds_the_absence_of_a_corridor_and_nothing_else(self) -> None:
        """023 retired the second member: *the money is already where it was wanted* is a
        candidate now, so the column that made it visible no longer holds it."""
        assert get_args(rec.NoCandidateReason) == ()
        assert rec.NoCandidateReason is rec.NothingConnects

    def test_it_names_the_side_rather_than_carrying_a_flag(self) -> None:
        """The remedies differ by side -- a corridor in, or one out -- and a row count shows
        neither."""
        connects = {field.name for field in dataclasses.fields(rec.NothingConnects)}
        assert connects == {"side", "reason"}


class TestTheTwoRefusalUnions:
    def test_every_enumeration_refusal_is_also_a_survey_refusal(self) -> None:
        assert set(get_args(rec.EnumerationRefused)) <= set(get_args(rec.SurveyRefused))

    def test_the_survey_only_refusals_are_the_two_about_handing_the_set_to_compare(self) -> None:
        extra = set(get_args(rec.SurveyRefused)) - set(get_args(rec.EnumerationRefused))
        assert extra == {rec.BenchmarkNotACandidate, rec.MoreThanOneStreamInTheSet}


class TestThisFeatureAddsNoRefusalOfItsOwn:
    def test_the_pruning_union_is_still_the_size_010_declares_it(self) -> None:
        """Pinned in 010's suite too, and not one fact twice: that one asserts the union's size,
        this one asserts *this* feature did not grow it. Different changes edit each."""
        assert len(get_args(TupleRefused)) == 18

    def test_no_record_in_this_module_is_a_feasibility_verdict(self) -> None:
        """A candidate-level refusal here would be the eighteenth by the back door: the union
        unchanged and a second opinion beside it."""
        assert not hasattr(rec, "CandidateRefused")
        assert rec.RefusedTuple.__module__ == "terezy.core.results.tuple"
