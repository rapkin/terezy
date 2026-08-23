"""SC-002: a composed candidate is costed by the same function as a declared route.

FR-003: *a composed candidate MUST be costed **in full, through the same single costing function
as a declared route** (002 FR-029), by applying every leg of every segment in order.* SC-002 asks
for that **by construction** -- "as 002 SC-016 asserts it, not by comparing numbers that happen
to agree" -- so this module asserts the *shape* that makes a second arithmetic unreachable, and
only then checks that the shape produces the right kind of answer.

**The mechanism is ``legs_of``** (research.md D1). It turns either kind of candidate into one
leg sequence, and ``cost_one`` walks that sequence exactly as it always did. There is no
composed-costing function to keep in step with the declared one, because there is no second
function: what a composition adds is *reach*, and reach is a longer tuple of legs.

**What a wrapper would have cost.** The obvious alternative -- cost each segment and add the
results -- is a second arithmetic, and it is wrong in a way no reviewer would see: the rounding
of a sum of sums is not the rounding of a single fold, so 002's cost-attribution invariant would
start failing for composed candidates **only**. That is precisely the "different path for
different candidates" FR-003 forbids, and the scan below is what keeps it out.

This module also carries three requirements that hold *because* the fold is unchanged rather
than because new code was written for them, and each is checked rather than asserted in prose:
SC-006 (provenance and staleness survive the join), SC-009 (no cost attributable to a
destination alone) and SC-011 (per-leg disruption, and no combined figure anywhere).
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Mapping

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.ramp import RampCost, RoundTripCost
from terezy.core.routes import cost
from terezy.core.routes.legs import Leg
from terezy.core.routes.path import (
    Candidate,
    ComposedExit,
    ComposedPath,
    DeclaredExit,
    FundingPath,
    segments_of,
)
from tests import composed_registries as fixtures

pytestmark = pytest.mark.contract

AMOUNT = Money(10_000.0, Currency.UAH, prov.EMPTY)
"""One amount, in the salary stream's currency. The figure the worked examples hand-compute."""

CHAIN = ComposedPath(
    destination_id=fixtures.BROKER,
    stream_id=fixtures.SALARY.id,
    segments=("in_salary_to_exchange", "in_exchange_to_broker"),
)
EXIT_CHAIN = ComposedExit(segments=("out_broker_to_exchange", "out_exchange_to_home"))


def _costed(candidate: Candidate = CHAIN) -> RampCost:
    world = fixtures.two_hop()
    outcome = cost.cost_one(
        candidate,
        AMOUNT,
        exit_path=EXIT_CHAIN,
        routes=world.routes,
        channels=world.channels,
        streams=world.streams,
        kinds=world.kinds,
        on_date=fixtures.ON_DATE,
        as_of=fixtures.AS_OF,
    )
    assert isinstance(outcome, RampCost), outcome
    return outcome


def _code_references(source: str) -> set[str]:
    """Every name and attribute mentioned in a function's body, comments and strings excluded.

    Parsed rather than grepped, on ``test_same_code_path``'s precedent: a docstring explaining
    that this module must not sum segment costs would fail a textual scan for ``sum``, and the
    fix a reader would reach for is deleting the sentence.
    """
    tree = ast.parse(inspect.cleandoc(source))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


class TestThereIsOneCostingFunctionAndOneProducerOfLegs:
    """SC-002, by construction. Nothing below compares two figures that agree."""

    def test_the_fold_is_only_ever_handed_a_chain_this_module_built(self) -> None:
        """One producer of leg sequences, asserted on the syntax rather than on two figures.

        ``_walk`` is the fold. Every call to it must be handed the output of ``_chain`` -- the
        function ``legs_of`` exposes -- or of ``_exit_chain``, its counterpart for the way back
        out. A call handed anything else would be a second way to assemble a journey, and the
        two would drift the first time one of them learned about a new kind of candidate.

        Parsed rather than grepped: a docstring explaining that this module must not sum
        segment costs mentions every word a textual scan would look for, and the fix a reader
        would reach for is deleting the sentence.
        """
        tree = ast.parse(inspect.getsource(cost))
        handed = [
            node.args[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_walk"
            and node.args
        ]
        assert handed, "no call to _walk was found; this scan is stale"
        producers = {
            call.func.id
            for call in handed
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
        }
        assert producers == {"_chain", "_exit_chain"}, ast.dump(handed[0])

    def test_costing_a_chain_and_costing_its_legs_is_the_same_call(self) -> None:
        """The composed candidate's legs **are** the concatenation, in order, renumbered once."""
        world = fixtures.two_hop()
        expected: list[Leg] = []
        for route_id in segments_of(CHAIN):
            expected.extend(world.routes[route_id].legs)
        walked = cost.legs_of(CHAIN, world.routes)
        assert [leg.from_venue for leg in walked] == [leg.from_venue for leg in expected]
        assert [leg.to_ccy for leg in walked] == [leg.to_ccy for leg in expected]
        assert [leg.index for leg in walked] == list(range(len(expected)))

    def test_a_declared_route_is_a_chain_of_one_and_takes_the_same_path(self) -> None:
        """research.md D7: one segment is not a special case, in costing or in attribution."""
        world = fixtures.two_hop()
        declared = FundingPath(
            destination_id=fixtures.EXCHANGE,
            stream_id=fixtures.SALARY.id,
            route_id="in_salary_to_exchange",
        )
        assert cost.legs_of(declared, world.routes) == world.routes["in_salary_to_exchange"].legs
        assert len(_costed(declared).one_way.by_segment) == 1

    def test_a_composition_of_one_is_refused_rather_than_costed(self) -> None:
        """A ``ComposedPath`` with a single segment is a declared route wearing the wrong type.

        Costing it anyway would put the same journey in a ranking under two shapes, and every
        report would then have to guess which it was looking at. It is a construction error
        rather than a fact about the money, so it raises.
        """
        world = fixtures.two_hop()
        with pytest.raises(ValueError, match="at least two"):
            cost.legs_of(
                ComposedPath(
                    destination_id=fixtures.EXCHANGE,
                    stream_id=fixtures.SALARY.id,
                    segments=("in_salary_to_exchange",),
                ),
                world.routes,
            )

    def test_nothing_in_the_costing_module_sums_per_segment_results(self) -> None:
        """The rejected implementation, asserted absent.

        ``cost_one`` must fold once over the concatenated legs. A version that costed each
        segment and added the results would agree to a few decimal places and disagree with
        002's attribution invariant, for composed candidates only.
        """
        referenced = _code_references(inspect.getsource(cost.cost_one))
        assert "_walk" in referenced
        assert not referenced & {"cost_segment", "cost_each", "segment_costs"}


class TestTheJoinLaundersNothing:
    """SC-006: provenance and staleness on a chain are the concatenation's, not an average."""

    def test_every_figure_on_a_composed_candidate_carries_the_unverified_mark(self) -> None:
        costed = _costed()
        assert prov.is_unverified(costed.one_way.provenance)
        assert isinstance(costed.round_trip, RoundTripCost)
        assert prov.is_unverified(costed.round_trip.provenance)
        for attribution in costed.one_way.by_segment:
            for charge in attribution.components.values():
                assert prov.is_unverified(charge.provenance), attribution.route_id

    def test_the_sources_of_every_segment_reach_the_composed_figure(self) -> None:
        """One segment's declaration cannot vanish at the join: a figure that could not name
        which fee schedule it rests on is not traceable (Principle III)."""
        costed = _costed()
        assert fixtures.FEE_SOURCE in costed.one_way.provenance.sources
        assert fixtures.RATE_SOURCE in costed.one_way.provenance.sources

    def test_a_stale_value_on_one_segment_makes_the_whole_candidate_stale(self) -> None:
        """FR-018: staleness is evaluated **per value by its declared kind**, across every
        segment, and one stale premium is enough.

        The premium ages in 7 days and the fee schedule in 365, and the fixture's observations
        are 20 days old at the as-of date -- so the conversion on the first segment is stale
        while the transfer fee on the second is not, and the merged verdict says stale rather
        than splitting the difference.
        """
        costed = _costed()
        verdict = costed.one_way.staleness
        assert verdict.stale, verdict
        assert {entry.kind_id for entry in verdict.stale} == {fixtures.P2P_PREMIUM.id}
        assert fixtures.FEE_SOURCE.id in verdict.assessed


class TestNoCostIsAttributableToADestinationAlone:
    """SC-009, extended to composed candidates without exception (FR-011)."""

    def test_every_figure_names_its_stream_and_its_whole_path(self) -> None:
        costed = _costed()
        assert costed.path.stream_id == fixtures.SALARY.id
        assert segments_of(costed.path) == (
            "in_salary_to_exchange",
            "in_exchange_to_broker",
        )

    def test_the_attribution_names_every_segment_it_charged_on(self) -> None:
        """FR-020: which component **and** which segment, so a reader can trace the dominating
        term to the declaration that charged it."""
        costed = _costed()
        assert [entry.route_id for entry in costed.one_way.by_segment] == [
            "in_salary_to_exchange",
            "in_exchange_to_broker",
        ]
        assert [entry.position for entry in costed.one_way.by_segment] == [0, 1]

    def test_both_axes_of_the_attribution_sum_to_the_same_total(self) -> None:
        """research.md D7's invariant, at one worked point: a leg cannot hide in either axis."""
        costed = _costed()
        by_component = sum(charge.amount for charge in costed.one_way.components.values())
        by_segment = sum(
            charge.amount
            for entry in costed.one_way.by_segment
            for charge in entry.components.values()
        )
        assert is_close(by_component, by_segment)


class TestDisruptionIsReportedPerLegAndNeverCombined:
    """SC-011 and FR-019: combining per-leg probabilities assumes independence nobody declared."""

    def test_every_leg_of_every_segment_keeps_its_declared_probability(self) -> None:
        world = fixtures.two_hop()
        declared = [leg.disruption_probability for leg in cost.legs_of(CHAIN, world.routes)]
        assert declared == [0.05, 0.02]

    def test_the_reported_figure_is_the_largest_single_leg_and_not_a_compound(self) -> None:
        """0.05 and 0.02 compound to 0.0690; the reported figure is 0.05, which is the honest
        lower bound -- *at least this likely* -- because nobody declared that the two legs fail
        independently."""
        costed = _costed()
        assert costed.disruption_probability == 0.05
        assert not is_close(costed.disruption_probability, 1 - (1 - 0.05) * (1 - 0.02))

    def test_no_result_record_carries_a_path_level_probability(self) -> None:
        """The structural half. A comment saying "do not combine these" is what gets deleted;
        a missing field is not."""
        costed = _costed()
        fields = set(vars(RampCost).get("__slots__", ()))
        assert [name for name in fields if "probability" in name] == ["disruption_probability"]
        assert isinstance(costed.disruption_probability, float)


def _channels_of(costed: RampCost) -> Mapping[str, int]:
    return {
        name: costed.one_way.channels_applied.count(name)
        for name in costed.one_way.channels_applied
    }


class TestTheChainReportsWhatItsSegmentsDid:
    def test_the_channels_applied_are_the_chain_s_converting_legs_in_order(self) -> None:
        """FR-011: the channel choice changes the number, so it is reported per crossing."""
        costed = _costed()
        assert costed.one_way.channels_applied == (fixtures.CHANNEL_ID,)
        assert _channels_of(costed) == {fixtures.CHANNEL_ID: 1}

    def test_latency_accumulates_across_segments(self) -> None:
        """FR-004: exactly what a declared route with the same concatenated legs would report."""
        assert _costed().latency_days == 3


class TestTheGuardsOnAnIncoherentCandidate:
    """A chain is assembled at query time, so this is the only place its shape can be checked.

    Every one of these is a **construction error** rather than a fact about the money -- the
    caller handed the costing function something that does not describe a journey -- so each
    raises rather than returning a typed refusal. Reporting them as costs would invite callers
    to keep building mismatched candidates and read the answer as a price.
    """

    def test_a_chain_whose_junction_does_not_join_is_refused(self) -> None:
        """The venue matches and the **currency** does not: the first segment arrives in
        dollars at the exchange and the second departs in hryvnia from it.

        A junction converts nothing, charges nothing and waits for nothing, so this chain does
        not exist -- and bridging it would be an invented leg at an invented rate (FR-002). The
        search never emits such a pair; this guard is what catches a hand-assembled one.
        """
        onward = fixtures.corridor(
            "in_exchange_uah_to_fund",
            direction="inbound",
            legs=(
                fixtures.leg(
                    index=0,
                    from_venue=fixtures.EXCHANGE,
                    to_venue=fixtures.FUND,
                    from_ccy=fixtures.UAH,
                    to_ccy=fixtures.UAH,
                ),
            ),
        )
        routes = {**fixtures.two_hop().routes, onward.id: onward}
        with pytest.raises(ValueError, match="do not join"):
            cost.legs_of(
                ComposedPath(
                    destination_id=fixtures.FUND,
                    stream_id=fixtures.SALARY.id,
                    segments=("in_salary_to_exchange", onward.id),
                ),
                routes,
            )

    def test_a_chain_naming_an_undeclared_route_is_refused(self) -> None:
        world = fixtures.two_hop()
        with pytest.raises(KeyError, match="unknown route"):
            cost.legs_of(
                ComposedPath(
                    destination_id=fixtures.BROKER,
                    stream_id=fixtures.SALARY.id,
                    segments=("in_salary_to_exchange", "typo_route"),
                ),
                world.routes,
            )

    def test_a_chain_that_does_not_end_where_it_says_it_does_is_refused(self) -> None:
        """The key has to be coherent: the destination on the record and the venue the last
        segment arrives at are one fact, and two places holding it can disagree."""
        world = fixtures.two_hop()
        with pytest.raises(ValueError, match="names 'home' as its destination"):
            cost.legs_of(
                ComposedPath(
                    destination_id=fixtures.HOME,
                    stream_id=fixtures.SALARY.id,
                    segments=("in_salary_to_exchange", "in_exchange_to_broker"),
                ),
                world.routes,
            )


class TestTheGuardsOnAnIncoherentExitChain:
    """FR-022 and FR-002 on the way out, where a chain is likewise built at query time."""

    def _cost(self, chain: ComposedExit | DeclaredExit) -> object:
        world = fixtures.two_hop()
        return cost.cost_one(
            CHAIN,
            AMOUNT,
            exit_path=chain,
            routes=world.routes,
            channels=world.channels,
            streams=world.streams,
            kinds=world.kinds,
            on_date=fixtures.ON_DATE,
            as_of=fixtures.AS_OF,
        )

    def test_a_composed_exit_of_one_segment_is_refused(self) -> None:
        """One declared exit route is a ``DeclaredExit``; a chain of none is not a way out at
        all, which is ``ExitCostUnknown`` and a different claim."""
        with pytest.raises(ValueError, match="at least two"):
            self._cost(ComposedExit(segments=("out_broker_to_exchange",)))

    def test_an_exit_chain_naming_an_undeclared_route_raises_rather_than_reporting_unknown(
        self,
    ) -> None:
        """A dangling reference is refused at load precisely so it cannot become a missing
        round trip here -- ``null`` is how a declaration says nobody has costed the exit."""
        with pytest.raises(KeyError, match="not declared"):
            self._cost(DeclaredExit(route_id="typo_route"))

    def test_an_inbound_route_used_as_a_way_out_is_refused(self) -> None:
        """FR-022. An observation of a corridor one way says nothing about the other way, so
        this would invent a corridor nobody observed."""
        with pytest.raises(ValueError, match="declared inbound"):
            self._cost(DeclaredExit(route_id="in_exchange_to_broker"))

    def test_an_exit_chain_whose_junction_does_not_join_is_refused(self) -> None:
        with pytest.raises(ValueError, match="do not join"):
            self._cost(ComposedExit(segments=("out_exchange_to_home", "out_broker_to_exchange")))
