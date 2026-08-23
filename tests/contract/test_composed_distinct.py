"""SC-017 and SC-018: a chain looks like a chain, and two ways out are two figures.

**SC-017** -- every composed candidate in every ranking, report and recommendation is visibly
distinct from a hand-declared route and shown segment by segment, each segment naming its
declared route. Verified across **every** reported candidate rather than sampled, because the
requirement is that a reader can always tell, not usually.

FR-013 says the distinction is *structural, not decorative*, so what is asserted here is the
shape rather than a label: a composed candidate is a different **type**, matched with ``match``,
and every place a candidate is reported carries the whole chain. A ``FundingPath`` whose
``route_id`` sometimes held a joined string would satisfy a decorative reading and would be
unparseable at exactly the point that matters -- the report that has to say which declarations a
comparison rests on.

**SC-018** -- two distinct composed exit chains from one destination produce two distinct
round-trip figures, each keyed per its exit chain; equal within the project tolerance, they tie.

That is FR-012's first consequence made checkable. The alternative shape -- one record holding
several round-trip figures -- has no defined position in a ranking ordered by round-trip cost, so
the first thing an implementer would do is pick one to order by, which is the blend FR-012
forbids arrived at by accident rather than by decision.
"""

from __future__ import annotations

import dataclasses

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.ramp import (
    ExitCostUnknown,
    RampCost,
    Ranking,
    RoundTripCost,
    recommended_cost,
)
from terezy.core.routes import cost, ranking
from terezy.core.routes.legs import Route
from terezy.core.routes.path import (
    EXIT_BY_IDENTITY,
    ComposedExit,
    ComposedPath,
    DeclaredExit,
    FundingPath,
    Journey,
    candidate_id,
    positions_of,
    segments_of,
)
from tests import composed_registries as fixtures

pytestmark = pytest.mark.contract

AMOUNT = Money(10_000.0, Currency.UAH, prov.EMPTY)

CHAIN = ComposedPath(
    destination_id=fixtures.BROKER,
    stream_id=fixtures.SALARY.id,
    segments=("in_salary_to_exchange", "in_exchange_to_broker"),
)
DECLARED = FundingPath(
    destination_id=fixtures.BROKER,
    stream_id=fixtures.SALARY.id,
    route_id="in_salary_to_broker_via_mirror",
)
VIA_EXCHANGE = ComposedExit(segments=("out_broker_to_exchange", "out_exchange_to_home"))


def _mirror_exit() -> tuple[Route, Route]:
    """A **second** way out of the broker, through the mirror exchange rather than the first.

    Two chains, two round-trip figures. Their fees are identical to the first chain's on
    purpose: SC-018 asks both that the figures be separate and that, when they agree within
    tolerance, they are reported as a tie rather than one of them silently winning.
    """
    first = fixtures.corridor(
        "out_broker_to_mirror",
        direction="exit",
        legs=(
            fixtures.leg(
                index=0,
                from_venue=fixtures.BROKER,
                to_venue=fixtures.MIRROR,
                from_ccy=fixtures.USD,
                to_ccy=fixtures.USD,
                fee_fixed=2.0,
            ),
        ),
    )
    second = fixtures.corridor(
        "out_mirror_to_home",
        direction="exit",
        legs=(
            fixtures.leg(
                index=0,
                from_venue=fixtures.MIRROR,
                to_venue=fixtures.HOME,
                from_ccy=fixtures.USD,
                to_ccy=fixtures.UAH,
            ),
        ),
    )
    return first, second


VIA_MIRROR = ComposedExit(segments=("out_broker_to_mirror", "out_mirror_to_home"))


def _world() -> dict[str, Route]:
    return {**fixtures.tied().routes, **{route.id: route for route in _mirror_exit()}}


def _rank(*journeys: Journey) -> Ranking:
    world = fixtures.tied()
    outcome = ranking.rank(
        list(journeys),
        AMOUNT,
        routes=_world(),
        channels=world.channels,
        streams=world.streams,
        kinds=world.kinds,
        on_date=fixtures.ON_DATE,
        as_of=fixtures.AS_OF,
        spendable=fixtures.SPENDABLE,
    )
    assert isinstance(outcome, Ranking), outcome
    return outcome


class TestEveryReportedCandidateSaysWhichKindItIs:
    """SC-017, across the whole reported set rather than a sample of it."""

    def test_a_ranking_holding_both_kinds_distinguishes_them_by_type(self) -> None:
        ranked = _rank(
            Journey(path=CHAIN, exit_path=VIA_EXCHANGE),
            Journey(path=DECLARED, exit_path=VIA_EXCHANGE),
        )
        kinds = {type(entry.path).__name__ for entry in ranked.costed}
        assert kinds == {"ComposedPath", "FundingPath"}

    def test_every_composed_candidate_is_shown_segment_by_segment(self) -> None:
        """Each segment naming the declared route it **is**, so which declarations a comparison
        rests on is visible wherever the candidate appears."""
        ranked = _rank(
            Journey(path=CHAIN, exit_path=VIA_EXCHANGE),
            Journey(path=DECLARED, exit_path=VIA_EXCHANGE),
        )
        for entry in ranked.costed:
            segments = positions_of(entry.path)
            assert segments, entry
            assert [segment.position for segment in segments] == list(range(len(segments)))
            assert all(segment.route_id in _world() for segment in segments)

    def test_the_recommendation_carries_the_whole_chain_and_not_an_opaque_id(self) -> None:
        """A recommendation is the place a reader is least likely to look further, so it is the
        place the distinction matters most."""
        ranked = _rank(Journey(path=CHAIN, exit_path=VIA_EXCHANGE))
        winner = recommended_cost(ranked)
        assert isinstance(winner.path, ComposedPath)
        assert segments_of(winner.path) == (
            "in_salary_to_exchange",
            "in_exchange_to_broker",
        )

    def test_an_exclusion_is_shown_segment_by_segment_too(self) -> None:
        """A refused candidate is reported (FR-014), and it is reported in the same shape --
        otherwise the one place a chain is hardest to read would be the one where something
        went wrong."""
        shut = dataclasses.replace(fixtures.EXCHANGE_TO_BROKER, status="closed")
        world = fixtures.tied()
        outcome = ranking.rank(
            [Journey(path=CHAIN, exit_path=VIA_EXCHANGE)],
            AMOUNT,
            routes={**_world(), shut.id: shut},
            channels=world.channels,
            streams=world.streams,
            kinds=world.kinds,
            on_date=fixtures.ON_DATE,
            as_of=fixtures.AS_OF,
            spendable=fixtures.SPENDABLE,
        )
        (excluded,) = outcome.excluded
        assert isinstance(excluded.path, ComposedPath)
        assert excluded.binding_segment is not None
        assert excluded.binding_segment.route_id == "in_exchange_to_broker"

    def test_the_attribution_names_each_segment_wherever_a_figure_appears(self) -> None:
        """The segment axis is on the one-way figure and on the round-trip figure both, so a
        reader never has to reconstruct which hop charged what."""
        ranked = _rank(Journey(path=CHAIN, exit_path=VIA_EXCHANGE))
        (entry,) = ranked.costed
        assert isinstance(entry.round_trip, RoundTripCost)
        assert [attribution.route_id for attribution in entry.one_way.by_segment] == list(
            segments_of(entry.path)
        )
        assert [attribution.route_id for attribution in entry.round_trip.by_segment][:2] == list(
            segments_of(entry.path)
        )


class TestTwoExitChainsAreTwoRoundTripFigures:
    """SC-018 and FR-012: keyed per exit chain, never blended."""

    def test_the_two_chains_are_genuinely_different_ways_out(self) -> None:
        """The precondition. Both leave the broker and both reach the one spendable endpoint,
        through different venues."""
        world = _world()
        assert VIA_EXCHANGE != VIA_MIRROR
        for chain in (VIA_EXCHANGE, VIA_MIRROR):
            assert all(world[route_id].direction == "exit" for route_id in chain.segments)
            assert world[chain.segments[-1]].destination == fixtures.HOME

    def test_each_produces_its_own_round_trip_figure_keyed_by_its_chain(self) -> None:
        figures = [
            cost.cost_one(
                CHAIN,
                AMOUNT,
                exit_path=chain,
                routes=_world(),
                channels=fixtures.tied().channels,
                streams=fixtures.tied().streams,
                kinds=fixtures.tied().kinds,
                on_date=fixtures.ON_DATE,
                as_of=fixtures.AS_OF,
                spendable=fixtures.SPENDABLE,
            )
            for chain in (VIA_EXCHANGE, VIA_MIRROR)
        ]
        assert all(isinstance(figure, RampCost) for figure in figures)
        assert [figure.exit_path for figure in figures] == [VIA_EXCHANGE, VIA_MIRROR]  # type: ignore[union-attr]
        assert len({figure.exit_path for figure in figures}) == 2  # type: ignore[union-attr]

    def test_both_appear_in_one_ranking_as_two_candidates(self) -> None:
        """FR-010 and FR-012 together: one league, and the exit chain is part of the identity
        of what is ranked."""
        ranked = _rank(
            Journey(path=CHAIN, exit_path=VIA_EXCHANGE),
            Journey(path=CHAIN, exit_path=VIA_MIRROR),
        )
        assert len(ranked.costed) == 2
        assert {entry.exit_path for entry in ranked.costed} == {VIA_EXCHANGE, VIA_MIRROR}
        assert {candidate_id(entry.path) for entry in ranked.costed} == {
            "in_salary_to_exchange+in_exchange_to_broker"
        }

    def test_equal_within_tolerance_they_tie_rather_than_one_winning(self) -> None:
        """The same rule as everything else (002 FR-018). Two ways out that cost the same are
        two facts the owner may choose between on grounds this tool does not model -- and
        picking one for him on a tiebreak he did not ask for is exactly what a tie exists to
        prevent."""
        ranked = _rank(
            Journey(path=CHAIN, exit_path=VIA_EXCHANGE),
            Journey(path=CHAIN, exit_path=VIA_MIRROR),
        )
        first, second = (entry.round_trip for entry in ranked.costed)
        assert isinstance(first, RoundTripCost)
        assert isinstance(second, RoundTripCost)
        assert is_close(first.fraction, second.fraction)
        assert ranked.ties == ((0, 1),)

    def test_nothing_blends_them_into_one_exit_cost(self) -> None:
        """There is no field on any record for an averaged exit, and the two figures are two
        records rather than two fields on one."""
        ranked = _rank(
            Journey(path=CHAIN, exit_path=VIA_EXCHANGE),
            Journey(path=CHAIN, exit_path=VIA_MIRROR),
        )
        assert len({id(entry) for entry in ranked.costed}) == 2
        assert all(isinstance(entry.round_trip, RoundTripCost) for entry in ranked.costed)


class TestTheExitChainAndTheRoundTripSlotAgree:
    """``exit_path`` is ``None`` **exactly when** the round trip is unknown, and never else."""

    def test_a_costed_candidate_with_a_way_out_names_it(self) -> None:
        ranked = _rank(Journey(path=CHAIN, exit_path=VIA_EXCHANGE))
        for entry in ranked.costed:
            assert isinstance(entry.round_trip, RoundTripCost)
            assert entry.exit_path is not None

    def test_a_candidate_with_no_way_out_names_none(self) -> None:
        world = fixtures.stranded()
        costed = cost.cost_one(
            CHAIN,
            AMOUNT,
            routes=world.routes,
            channels=world.channels,
            streams=world.streams,
            kinds=world.kinds,
            on_date=fixtures.ON_DATE,
            as_of=fixtures.AS_OF,
            spendable=fixtures.SPENDABLE,
        )
        assert isinstance(costed, RampCost)
        assert isinstance(costed.round_trip, ExitCostUnknown)
        assert costed.exit_path is None


class TestTheSeamBetweenTheWayInAndTheWayOut:
    """F1: an exit chain is anchored at **both** ends, or the money teleports.

    ``_routes_for`` anchors the inbound chain at its tail against the destination it claims.
    ``_exit_routes`` had no anchor at either end, so a way out for one destination could be
    paired with a way in to another and walked as though they met -- which is a one-loop mistake
    through this feature's own surface, since ``rank`` takes a ``Journey`` from any caller.

    Both faces are pinned below. Neither produced an error before the anchors existed; both
    produced a confident, coherent-looking round-trip figure.
    """

    def test_an_exit_that_departs_from_somewhere_else_is_refused(self) -> None:
        """**Face (a): the money teleports.**

        The candidate arrives at the **broker**; ``out_exchange_to_home`` departs from the
        **exchange**. Walking it moved 219 USD between the two for free, across a junction
        nobody declared -- FR-002's "a junction never converts, charges or waits" broken at the
        one junction nothing checked. The result read as a coherent three-hop journey, which is
        why nothing noticed.
        """
        world = fixtures.tied()
        with pytest.raises(ValueError, match="do not meet"):
            cost.cost_one(
                CHAIN,
                AMOUNT,
                exit_path=DeclaredExit(route_id="out_exchange_to_home"),
                routes=_world(),
                channels=world.channels,
                streams=world.streams,
                kinds=world.kinds,
                on_date=fixtures.ON_DATE,
                as_of=fixtures.AS_OF,
                spendable=world.spendable,
            )

    def test_an_exit_that_does_not_reach_a_spendable_endpoint_is_refused(self) -> None:
        """**Face (b): the round trip does not return spendable money.**

        The seam is fine -- ``out_broker_to_exchange`` does leave the broker -- but the chain
        ends holding **dollars at an exchange**, which is not somewhere the owner spends. FR-012
        and FR-022 both require an exit chain to reach a declared spendable endpoint, and 002's
        loader refused exactly this for a ``partner_route``.

        Worse than a missing figure: ``arrived`` was then in dollars while ``fraction`` was
        computed from hryvnia components, so one record carried two figures describing different
        things.
        """
        world = fixtures.tied()
        with pytest.raises(ValueError, match="not a declared spendable endpoint"):
            cost.cost_one(
                CHAIN,
                AMOUNT,
                exit_path=DeclaredExit(route_id="out_broker_to_exchange"),
                routes=_world(),
                channels=world.channels,
                streams=world.streams,
                kinds=world.kinds,
                on_date=fixtures.ON_DATE,
                as_of=fixtures.AS_OF,
                spendable=world.spendable,
            )

    def test_a_supplied_identity_sentinel_is_anchored_too(self) -> None:
        """The twin, and the hole the first pass left.

        ``EXIT_BY_IDENTITY`` skipped ``_supplied_exit`` entirely because it matched its own
        ``case`` arm before the catch-all -- so the one shape whose **whole content** is a claim
        about the far end was the one shape nothing checked. Passed against a candidate arriving
        at the broker it produced a ``RoundTripCost`` reporting 2199.00 **USD** arrived beside a
        fraction computed from hryvnia components: two figures on one record describing different
        things, which is verbatim the failure ``METHODOLOGY`` §21.8 cites to justify the anchor.

        Reachable through this feature's own surface -- ``rank`` takes a ``Journey`` from any
        caller, and ``Journey(path, exit_path=EXIT_BY_IDENTITY)`` is one line.
        """
        world = fixtures.tied()
        with pytest.raises(ValueError, match="not a declared spendable endpoint"):
            cost.cost_one(
                CHAIN,
                AMOUNT,
                exit_path=EXIT_BY_IDENTITY,
                routes=_world(),
                channels=world.channels,
                streams=world.streams,
                kinds=world.kinds,
                on_date=fixtures.ON_DATE,
                as_of=fixtures.AS_OF,
                spendable=world.spendable,
            )

    def test_the_sentinel_still_costs_where_the_destination_really_is_spendable(self) -> None:
        """The anchor refuses a false claim, not the sentinel. Without this the test above would
        pass against a branch that raised unconditionally."""
        world = fixtures.spendable_destination()
        costed = cost.cost_one(
            FundingPath(
                destination_id=fixtures.HOME,
                stream_id=fixtures.SALARY.id,
                route_id="in_salary_to_home",
            ),
            AMOUNT,
            exit_path=EXIT_BY_IDENTITY,
            routes=world.routes,
            channels=world.channels,
            streams=world.streams,
            kinds=world.kinds,
            on_date=fixtures.ON_DATE,
            as_of=fixtures.AS_OF,
            spendable=world.spendable,
        )
        assert isinstance(costed, RampCost), costed
        assert isinstance(costed.round_trip, RoundTripCost)
        assert costed.exit_path is EXIT_BY_IDENTITY

    def test_a_correctly_anchored_chain_still_costs(self) -> None:
        """The anchors refuse mispairings, not exit chains. Without this the two above would
        pass against a function that refused everything."""
        ranked = _rank(Journey(path=CHAIN, exit_path=VIA_EXCHANGE))
        (entry,) = ranked.costed
        assert isinstance(entry.round_trip, RoundTripCost)


class TestTheKeyAndTheRoundTripSlotCannotDisagree:
    """F2: ``exit_path is None`` **exactly when** there is no round-trip figure.

    The record's own docstring said "and never otherwise ... asserted rather than assumed", and
    it was false: ``cost_one`` filled both slots from the chain it had chosen, while
    ``_round_trip`` refuses on two further paths afterwards. The key is now derived from the
    outcome, so the biconditional holds by construction.
    """

    def test_a_closed_way_out_clears_the_key_it_would_have_been_ranked_under(self) -> None:
        """The case the old tests missed. A chain was chosen, then found closed on the date --
        so there is no round-trip figure, and no chain this figure is keyed by."""
        shut = dataclasses.replace(fixtures.EXCHANGE_TO_HOME, status="closed")
        world = fixtures.tied()
        costed = cost.cost_one(
            CHAIN,
            AMOUNT,
            exit_path=VIA_EXCHANGE,
            routes={**_world(), shut.id: shut},
            channels=world.channels,
            streams=world.streams,
            kinds=world.kinds,
            on_date=fixtures.ON_DATE,
            as_of=fixtures.AS_OF,
            spendable=world.spendable,
        )
        assert isinstance(costed, RampCost), costed
        assert isinstance(costed.round_trip, ExitCostUnknown)
        assert "closed" in costed.round_trip.reason
        assert costed.exit_path is None

    def test_a_way_out_that_will_not_carry_what_arrived_clears_it_too(self) -> None:
        """The second late refusal: the chain exists, is open, and its minimum bites."""
        strict = dataclasses.replace(
            fixtures.BROKER_TO_EXCHANGE,
            legs=(
                dataclasses.replace(
                    fixtures.BROKER_TO_EXCHANGE.legs[0],
                    minimum=Money(10_000.0, Currency.USD, prov.EMPTY),
                ),
            ),
        )
        world = fixtures.tied()
        costed = cost.cost_one(
            CHAIN,
            AMOUNT,
            exit_path=VIA_EXCHANGE,
            routes={**_world(), strict.id: strict},
            channels=world.channels,
            streams=world.streams,
            kinds=world.kinds,
            on_date=fixtures.ON_DATE,
            as_of=fixtures.AS_OF,
            spendable=world.spendable,
        )
        assert isinstance(costed, RampCost), costed
        assert isinstance(costed.round_trip, ExitCostUnknown)
        assert costed.exit_path is None

    def test_the_correspondence_holds_in_both_directions_on_every_reported_candidate(
        self,
    ) -> None:
        """Stated over a whole ranking rather than one record, because the claim is about the
        type and a consumer reads it that way: ``exit_path is not None`` means there is a
        round-trip figure, always."""
        ranked = _rank(
            Journey(path=CHAIN, exit_path=VIA_EXCHANGE),
            Journey(path=CHAIN, exit_path=VIA_MIRROR),
            Journey(path=DECLARED, exit_path=VIA_EXCHANGE),
        )
        for entry in (*ranked.costed, *ranked.not_comparable):
            assert (entry.exit_path is not None) == isinstance(entry.round_trip, RoundTripCost)
