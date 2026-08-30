"""The shapes 014 returns, and the three things about them that must stay true.

Not a battery of behaviour -- the suites beside this one are that. What is asserted here is
what the *types* claim, because each of the three is a claim a later change could quietly
break while every behavioural test stayed green.

* **The two no-candidate reasons are different types** (FR-014). Their remedies are opposite --
  declare a corridor, versus nothing at all, because the money is already where it was wanted --
  and a reader must tell them apart without reading prose. Collapsing them into one record with
  a flag would move that distinction into the reader's head.
* **`EnumerationRefused` is a strict subset of `SurveyRefused`** (research D5). Two of the
  refusals are about handing the set to `compare` and cannot arise from enumeration alone, so a
  caller of `enumerate_candidates` matching exhaustively must not be made to carry arms that
  never fire.
* **`TupleRefused` still has seventeen members** (FR-006). Pinned in 010's own suite and pinned
  again here, because *this* feature is the one under pressure to add an eighteenth: every drop
  it reports is a value 010 produced, and a new reason to consider a candidate infeasible is a
  change to 010's union made and reviewed there.
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
        """`NothingConnects` names a side; `NothingNeedsToConnect` carries compose's record.

        A `case`-like discriminator on either would be a second place the distinction lives,
        and the day the two disagreed nothing would say which was authoritative.
        """
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
        """FR-006, pinned here as well as in 010's suite.

        Duplicated deliberately and it is not one fact in two places: 010's test asserts the
        union's own size, and this one asserts that *this* feature did not grow it. The two
        would be edited by different changes, and the second is the one under pressure.
        """
        assert len(get_args(TupleRefused)) == 17

    def test_no_record_in_this_module_is_a_feasibility_verdict(self) -> None:
        """A record here holding a refusal *reason of its own* about one candidate would be the
        eighteenth arriving by the back door -- the union unchanged and a second opinion beside
        it. Every drop this feature reports is 010's `RefusedTuple`, carried whole (FR-010)."""
        assert not hasattr(rec, "CandidateRefused")
        assert rec.RefusedTuple.__module__ == "terezy.core.results.tuple"
