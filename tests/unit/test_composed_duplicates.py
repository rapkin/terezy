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

from datetime import date

import pytest

from terezy.core.results.composed import Enumeration, SegmentBound
from terezy.core.routes import compose
from terezy.core.routes.legs import Route
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


# ---------------------------------------------------------------------------
# FR-009's other half: differing **terms** make two candidates, not one
# ---------------------------------------------------------------------------
#
# The suppression rule compares nineteen leg fields. Only some of them are exercised by the
# cases above -- venues, currencies and fees -- and the rest were untested: deleting
# ``latency_days``, ``disruption_probability``, the availability window, the limits or the
# capacity pool from the comparison collapsed two genuinely different candidates into one, and a
# real alternative vanished from the ranking **with no trace**. That is FR-007's "no candidate
# dropped without a recorded reason" broken silently, which is the worst way for it to break.
#
# Each case below is the *same* corridor -- same venues, same currencies, same direction --
# differing in exactly one declared term. Both candidates must stand, because a term is part of
# what a journey costs or what it will carry, and two journeys that differ in one are two things
# the owner may choose between.

BASE_TERMS: dict[str, object] = {
    "index": 0,
    "from_venue": fixtures.EXCHANGE,
    "to_venue": fixtures.BROKER,
    "from_ccy": fixtures.USD,
    "to_ccy": fixtures.USD,
    "fee_pct": 0.01,
    "fee_fixed": 1.0,
    "latency_days": 2,
    "disruption": 0.02,
    "monthly_cap": 5_000.0,
    "pool": "a_rail",
}
"""One corridor, fully specified, so a case below can change exactly one term of it.

It declares a cap **and** a rail from the start: a cap with no rail has no key to accumulate
under and is refused, so a pool-only difference is only expressible against a base that already
has one. Getting that wrong is how the ``capacity_pool`` case first passed while the field was
not compared at all -- the variant differed in its *cap* as well, and the cap carried the test.
"""

ONE_TERM_APART: dict[str, dict[str, object]] = {
    "latency_days": {"latency_days": 5},
    "disruption_probability": {"disruption": 0.5},
    "available_from": {"window": (date(2027, 1, 1), None)},
    "available_until": {"window": (None, date(2026, 1, 1))},
    "minimum": {"minimum": 10.0},
    "maximum": {"maximum": 900.0},
    "monthly_cap": {"monthly_cap": 9_000.0},
    "capacity_pool": {"pool": "another_rail"},
    "fee_pct": {"fee_pct": 0.02},
    "fee_fixed": {"fee_fixed": 7.0},
    "kind_of_observation": {"observation": fixtures.P2P_PREMIUM.id},
}
"""Exactly one declared term each, against :data:`BASE_TERMS`.

Every one of them is part of what a journey costs, what it will carry, or how its numbers age,
so two corridors differing in one are two things the owner may choose between -- and dropping
any of them from the comparison deletes a real alternative from the ranking **with no trace**,
since there is no ``excluded`` entry for a candidate the search never emitted.

⚙ **The comparison holds nineteen elements and this covers fifteen of them**; the remainder are
named rather than left for a reader to count. ``position`` is the renumbered index and is pinned
by SC-013 next door. ``from_venue``, ``to_venue``, ``from_ccy`` and ``to_ccy`` are covered by the
mirror-venue case above. The three that are **not** exercised here -- ``kind``, ``channel`` and
``fee_fixed``'s currency -- cannot vary independently in this builder: ``leg`` derives all three
from the two venue currencies, so a variant differing in one of them differs in a currency too
and would be testing the currency. Exercising them needs a builder that can declare an
inconsistent leg, which is a leg the resolver refuses, so what would be under test is a file
that cannot exist.

``kind_of_observation`` *can* vary on its own -- ``leg`` takes ``observation=`` -- and it was
the one genuine gap: two corridors whose numbers age on different schedules are two corridors,
and collapsing them would report one staleness verdict for two different claims about how fresh
the figures are.
"""


def _variant(route_id: str, **terms: object) -> Route:
    """The corridor of :data:`BASE_TERMS` with some terms changed, under its own id."""
    return fixtures.corridor(
        route_id,
        direction="inbound",
        legs=(fixtures.leg(**{**BASE_TERMS, **terms}),),  # type: ignore[arg-type]
    )


def _both_stand(**terms: object) -> set[str]:
    """Enumerate over a registry holding two variants of the second hop, and name what stood."""
    left = _variant("in_exchange_to_broker_left")
    right = _variant("in_exchange_to_broker_right", **terms)
    world = fixtures.two_hop()
    routes = {
        route_id: route
        for route_id, route in world.routes.items()
        if route_id != "in_exchange_to_broker"
    }
    result = compose.compose(
        routes={**routes, left.id: left, right.id: right},
        stream=world.streams[fixtures.SALARY.id],
        destination=fixtures.BROKER_USD,
        direction="inbound",
        regime_id=fixtures.REGIME_ID,
        bound=BOUND,
        spendable=world.spendable,
    )
    assert isinstance(result, Enumeration), result
    return {candidate_id(candidate) for candidate in result.candidates}


@pytest.mark.parametrize("term", sorted(ONE_TERM_APART), ids=sorted(ONE_TERM_APART))
def test_two_chains_differing_in_one_declared_term_both_stand(term: str) -> None:
    """FR-009: *candidates over the same venues with differing legs or terms are distinct.*"""
    assert _both_stand(**ONE_TERM_APART[term]) == {
        "in_salary_to_exchange+in_exchange_to_broker_left",
        "in_salary_to_exchange+in_exchange_to_broker_right",
    }, f"the {term} difference was suppressed as a duplicate"


def test_two_chains_differing_in_no_term_at_all_collapse_to_one() -> None:
    """The control, without which every case above would pass against a rule that never fires.

    The same corridor declared twice under two ids **is** the same real-world movement, so the
    ranking holds it once -- and which one survives is the deterministic order, not the draw.
    """
    assert _both_stand() == {"in_salary_to_exchange+in_exchange_to_broker_left"}
