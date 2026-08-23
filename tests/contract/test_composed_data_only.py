"""SC-010: one route declaration extends the reachable graph, with zero source changes.

Principle II, applied to composition. FR-021 is its other half: composition uses what is
declared, and what is **not** declared is the coverage report's news to deliver (feature 003),
never a gap this feature fills by fabricating a link.

**What "zero source changes" means here, checked rather than claimed.** The registries below
differ by exactly one ``Route`` record -- the same builder, the same fields, no new leg kind, no
new venue type, no branch anywhere in ``core`` that mentions any of them. The wider registry
produces fully costed and fully ranked candidates the narrower one cannot reach, and the only
thing that moved is a declaration.

**And the negative half, which is the harder one.** A corridor broken by one missing segment
stays absent. Nothing bridges it: not an implicit conversion at a junction whose currencies
disagree, not a synthesised leg across a gap, not a "probably similar" corridor. The absence is
the answer, and it is the coverage report's job to say so.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import terezy.core
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.composed import Enumeration, SegmentBound
from terezy.core.results.coverage import Destination
from terezy.core.results.ramp import Ranking, RoundTripCost
from terezy.core.routes import compose, ranking
from terezy.core.routes.legs import Route
from terezy.core.routes.path import Candidate, ComposedExit, Journey, candidate_id
from tests import composed_registries as fixtures

pytestmark = pytest.mark.contract

AMOUNT = Money(10_000.0, Currency.UAH, prov.EMPTY)
BOUND = SegmentBound(max_segments=3)
EXIT_CHAIN = ComposedExit(segments=("out_broker_to_exchange", "out_exchange_to_home"))

CUSTODY = "custody"
"""A venue beyond the broker, reachable only once somebody declares the hop to it."""

CUSTODY_USD = Destination(venue_id=CUSTODY, currency=fixtures.USD)

ONWARD = fixtures.corridor(
    "in_broker_to_custody",
    direction="inbound",
    legs=(
        fixtures.leg(
            index=0,
            from_venue=fixtures.BROKER,
            to_venue=CUSTODY,
            from_ccy=fixtures.USD,
            to_ccy=fixtures.USD,
            fee_fixed=3.0,
        ),
    ),
)
"""**The one declaration** this module adds. A ``Route`` record like any other."""

MISSING_LINK = fixtures.corridor(
    "in_nowhere_to_custody",
    direction="inbound",
    legs=(
        fixtures.leg(
            index=0,
            from_venue=fixtures.MIRROR,
            to_venue=CUSTODY,
            from_ccy=fixtures.USD,
            to_ccy=fixtures.USD,
        ),
    ),
)
"""A corridor into custody that starts somewhere nothing reaches.

The broken-chain case: the last hop exists and the hop *to* its origin does not, so the corridor
is one declaration short of being reachable. Nothing may be fabricated to span the gap.
"""


def _candidates(routes: dict[str, Route], destination: Destination) -> tuple[Candidate, ...]:
    world = fixtures.two_hop()
    result = compose.compose(
        routes=routes,
        stream=world.streams[fixtures.SALARY.id],
        destination=destination,
        direction="inbound",
        regime_id=fixtures.REGIME_ID,
        bound=BOUND,
        spendable=world.spendable,
    )
    assert isinstance(result, Enumeration), result
    return result.candidates


class TestOneDeclarationExtendsTheReachableGraph:
    def test_the_terminal_venue_is_unreachable_before_the_declaration(self) -> None:
        """The broker is where the registry stops, so custody has no candidate at all."""
        assert _candidates(dict(fixtures.two_hop().routes), CUSTODY_USD) == ()

    def test_adding_the_one_route_makes_a_three_segment_candidate_appear(self) -> None:
        """Salary → exchange → broker → custody, composed from three declarations none of which
        mentions the others."""
        routes = {**fixtures.two_hop().routes, ONWARD.id: ONWARD}
        assert [candidate_id(candidate) for candidate in _candidates(routes, CUSTODY_USD)] == [
            "in_salary_to_exchange+in_exchange_to_broker+in_broker_to_custody"
        ]

    def test_the_two_registries_differ_by_exactly_one_declaration(self) -> None:
        """The claim "one declaration" made checkable rather than asserted in prose."""
        before = set(fixtures.two_hop().routes)
        after = set({**fixtures.two_hop().routes, ONWARD.id: ONWARD})
        assert after - before == {ONWARD.id}
        assert before - after == set()

    def test_the_new_candidate_is_fully_costed_and_ranked(self) -> None:
        """Not merely reachable: costed by the one costing function, with a round-trip figure,
        and taking its place in the ordinary ranking.

        The way out is the same chain the broker already had, because custody's own exit is a
        further declaration nobody has written -- so the candidate ranked here is costed in and
        back out through declarations that all existed before this test invented one hop.
        """
        routes = {**fixtures.two_hop().routes, ONWARD.id: ONWARD}
        world = fixtures.two_hop()
        (candidate,) = _candidates(routes, CUSTODY_USD)
        outcome = ranking.rank(
            [Journey(path=candidate, exit_path=EXIT_CHAIN)],
            AMOUNT,
            routes=routes,
            channels=world.channels,
            streams=world.streams,
            kinds=world.kinds,
            on_date=fixtures.ON_DATE,
            as_of=fixtures.AS_OF,
        )
        assert isinstance(outcome, Ranking), outcome
        (entry,) = outcome.costed
        assert isinstance(entry.round_trip, RoundTripCost)
        assert len(entry.one_way.by_segment) == 3
        assert entry.one_way.arrived.currency is Currency.USD

    def test_no_engine_module_mentions_the_new_venue_or_route(self) -> None:
        """The Principle II claim, from the other side: the ids above appear nowhere in ``core``.

        A branch on a venue id is the failure this catches -- the shape where reach *looks*
        data-driven while one corridor is special-cased somewhere. Textual, with the limits every
        scan in this suite states; what it catches is the obvious version, which is the one that
        gets written.
        """
        root = Path(terezy.core.__file__).parent
        offenders = [
            path.name
            for path in root.rglob("*.py")
            for source in [path.read_text(encoding="utf-8")]
            if CUSTODY in source or ONWARD.id in source
        ]
        assert offenders == []


class TestABrokenChainIsAbsentRatherThanBridged:
    def test_a_corridor_one_declaration_short_produces_no_candidate(self) -> None:
        """FR-021: nothing is fabricated to span the gap.

        ``in_nowhere_to_custody`` arrives at custody from the mirror exchange, which nothing in
        this registry reaches. The corridor is one declaration short, so it is simply absent --
        and saying so is the coverage report's job, not this feature's.
        """
        routes = {**fixtures.two_hop().routes, MISSING_LINK.id: MISSING_LINK}
        assert _candidates(routes, CUSTODY_USD) == ()

    def test_a_junction_whose_currencies_disagree_is_not_bridged(self) -> None:
        """The venue matches and the currency does not, so the chain does not exist.

        An implicit conversion here would be an invented leg at an invented rate (FR-002) -- and
        it is the single most tempting fabrication in the whole feature, because the two
        declarations sit at the same venue and look adjacent.
        """
        uah_only = fixtures.corridor(
            "in_broker_uah_to_custody",
            direction="inbound",
            legs=(
                fixtures.leg(
                    index=0,
                    from_venue=fixtures.BROKER,
                    to_venue=CUSTODY,
                    from_ccy=fixtures.UAH,
                    to_ccy=fixtures.UAH,
                ),
            ),
        )
        routes = {**fixtures.two_hop().routes, uah_only.id: uah_only}
        assert _candidates(routes, Destination(venue_id=CUSTODY, currency=fixtures.UAH)) == ()

    def test_nothing_is_written_back_to_the_registry(self) -> None:
        """FR-021: composition is a query-time construction and persists nothing.

        The mapping handed in comes back untouched -- no auto-declared link, no cached chain, no
        composed candidate turned into a route for the next run to find.
        """
        routes = {**fixtures.two_hop().routes, ONWARD.id: ONWARD}
        before = dict(routes)
        _candidates(routes, CUSTODY_USD)
        assert routes == before
