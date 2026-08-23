"""SC-013: no ranking holds two candidates with identical leg chains.

FR-009: *where a composed concatenation reproduces a declared route leg for leg, the declared
route stands and the duplicate is not emitted. Candidates over the same venues with differing
legs or terms are distinct and all stand.*

The registry here declares a route **and its exact segment-wise equivalent**: ``in_salary_to_
broker_declared`` is leg for leg what you get by concatenating ``in_salary_to_exchange`` with
``in_exchange_to_broker`` -- same venues, same currencies, same fees, same latencies. It is the
same real-world sequence of movements, so it appears **once**.

## The trap, stated because the naive implementation passes review

``Leg.index`` is **per route**. Concatenating a one-leg route with a one-leg route gives indices
``0, 0`` where the declared equivalent has ``0, 1``; concatenating a two-leg route with a
one-leg route gives ``0, 1, 0`` against ``0, 1, 2``. Compared as declared, the two tuples never
match, the duplicate is never suppressed, and the ranking quietly holds the same movement twice
-- with two round-trip figures, two rows and one of them a phantom alternative.

Normalise the index first, compare second. The neighbouring case is what keeps the rule from
over-reaching: two chains over the same *venues* with any difference in any leg are two genuine
candidates, and both stand.
"""

from __future__ import annotations

from terezy.core.results.composed import Enumeration, SegmentBound
from terezy.core.routes import compose
from terezy.core.routes.path import (
    Candidate,
    ComposedPath,
    FundingPath,
    candidate_id,
    segments_of,
)
from tests import composed_registries as fixtures

BOUND = SegmentBound(max_segments=3)


def _candidates(world: fixtures.Registry) -> tuple[Candidate, ...]:
    result = compose.compose(
        routes=world.routes,
        stream=world.streams[fixtures.SALARY.id],
        destination=fixtures.BROKER_USD,
        direction="inbound",
        regime_id=fixtures.REGIME_ID,
        bound=BOUND,
        spendable=world.spendable,
    )
    assert isinstance(result, Enumeration), result
    return result.candidates


class TestAChainThatReproducesADeclaredRouteAppearsOnce:
    def test_the_fixture_really_declares_the_same_legs_twice(self) -> None:
        """Without this the suppression below could be passing because nothing matched.

        Compared field by field with the index renumbered, which is the comparison the rule
        itself makes -- and the comparison whose *absence* is the defect. Written out here so a
        reader can see the two leg chains really are the same movements.
        """
        world = fixtures.duplicated()
        chained = [
            leg
            for route_id in ("in_salary_to_exchange", "in_exchange_to_broker")
            for leg in world.routes[route_id].legs
        ]
        declared = list(world.routes["in_salary_to_broker_declared"].legs)
        assert len(chained) == len(declared)
        for position, (left, right) in enumerate(zip(chained, declared, strict=True)):
            assert (left.from_venue, left.to_venue) == (right.from_venue, right.to_venue)
            assert (left.from_ccy, left.to_ccy) == (right.from_ccy, right.to_ccy)
            assert (left.fee_pct, left.fee_fixed.amount) == (right.fee_pct, right.fee_fixed.amount)
            assert left.latency_days == right.latency_days
            # And the trap itself: the declared route numbers its legs 0, 1 while each segment
            # of the chain numbers its own from zero. Compared as declared they never match.
            assert right.index == position
        assert [leg.index for leg in chained] == [0, 0]

    def test_the_declared_route_stands_and_the_concatenation_is_not_emitted(self) -> None:
        candidates = _candidates(fixtures.duplicated())
        assert [candidate_id(candidate) for candidate in candidates] == [
            "in_salary_to_broker_declared"
        ]
        assert all(isinstance(candidate, FundingPath) for candidate in candidates)

    def test_no_two_candidates_share_a_leg_chain(self) -> None:
        """The rule as a property of the emitted set, on every fixture that has one.

        Stated over the whole set rather than over the one pair above, because FR-009 is about
        a *ranking* never holding two identical movements -- and a second composed chain
        duplicating a first is the same defect as one duplicating a declared route.
        """
        for world in (fixtures.two_hop(), fixtures.tied(), fixtures.duplicated()):
            shapes = [
                tuple(
                    (position, leg.from_venue, leg.to_venue, leg.from_ccy, leg.to_ccy, leg.fee_pct)
                    for position, leg in enumerate(
                        leg
                        for route_id in segments_of(candidate)
                        for leg in world.routes[route_id].legs
                    )
                )
                for candidate in _candidates(world)
            ]
            assert len(shapes) == len(set(shapes)), shapes


class TestTheRuleDoesNotOverReach:
    def test_two_journeys_with_identical_terms_but_different_legs_both_stand(self) -> None:
        """A chain differing in **any** leg is a genuinely different candidate.

        ``in_salary_to_broker_via_mirror`` charges the same premium and the same fees and takes
        the same time -- and passes through a different middle venue, so its legs differ. The
        rule is about identical **legs**, not identical numbers: suppressing this one because
        the figures agree would delete a real alternative and hide the useful fact that the two
        agree, which is a tie, reported as one, and never a reason to drop a row.
        """
        ids = {candidate_id(candidate) for candidate in _candidates(fixtures.tied())}
        assert ids == {
            "in_salary_to_broker_via_mirror",
            "in_salary_to_exchange+in_exchange_to_broker",
        }

    def test_a_chain_with_no_declared_equivalent_is_emitted_as_a_composition(self) -> None:
        candidates = _candidates(fixtures.two_hop())
        assert [candidate_id(candidate) for candidate in candidates] == [
            "in_salary_to_exchange+in_exchange_to_broker"
        ]
        assert all(isinstance(candidate, ComposedPath) for candidate in candidates)
