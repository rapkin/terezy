"""FR-018, FR-014, SC-014: what a ranking does with equals, refusals and missing exits.

Three requirements meet in ``rank``, and each of them is about *not* quietly improving the
answer.

**FR-018 -- a tie is a tie, decided on round-trip cost alone.** Two routes costing the same
within the project tolerance are tied even where their ceilings and latencies differ. The owner
asked which is cheapest; "these two cost the same, and here is how they differ" answers that,
while silently preferring one on a tiebreak he did not ask for does not. The sequence is still
deterministically ordered by all three keys of FR-016 -- that is what makes the output
reproducible -- so :attr:`Ranking.ties` is the field that stops the head of the sequence being
read as a strict winner. Both halves are asserted below, because dropping either one turns a
reported tie back into an invented preference.

**FR-014 -- an excluded route carries the constraint that bound it.** Never rounded to a
minimum, never trimmed to a maximum, never dropped. A silent exclusion is how a comparison comes
to recommend the only route left standing, with nothing in the output to say why the others are
missing, and it looks exactly like a comparison that had one good answer.

**SC-014 -- a destination with no declared exit route is costed, reported, and not ranked.**
Round-trip cost is what belongs in a comparison (FR-002), so a route whose way out nobody has
declared is not comparison-ready however cheap it looks going in. The test that matters here
makes the exit-less route the *cheapest one way* in the set and asserts it is still not
recommended: promoting the one-way figure is the tempting silent fix, and it would be a
confident round-trip number for an exit path nobody has ever looked at.

**And B12 -- no composite score.** The last class puts a cheap route with a tiny ceiling and a
long latency against an expensive one with no cap and no delay. Cost leads, so the cheap route
wins. Any weighting of hryvnia against days could have flipped that, which is why there is no
weighting: the exchange rate between money and time is a preference of the owner's, not a fact
about the money.

Every fixture here is the domestic two-leg shape from ``route_graphs``, varied one declared
field at a time, so a failure names the field that broke rather than a route that is different
in four ways at once.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.ramp import (
    ExitCostUnknown,
    NothingComparable,
    Ranking,
    RoundTripCost,
    recommended_cost,
)
from terezy.core.routes import ranking
from terezy.core.routes.legs import Route, RouteStatus
from terezy.core.routes.path import FundingPath
from tests.invariants import route_graphs

AMOUNT = 10_000.0
"""What every candidate is asked to carry. One amount for all of them, because a comparison of
costs at different amounts is not a comparison."""

_TEMPLATE = route_graphs.zero_cost_graph(with_exit=True)
"""The domestic two-leg shape, with its exit declared. Varied one field at a time below."""

_EXIT_TEMPLATE = _TEMPLATE.routes["inzhur_exit"]

Candidate = tuple[FundingPath, Mapping[str, Route]]
"""One path and the route declarations it needs -- the inbound route and, usually, its exit."""


def _uah(amount: float) -> Money:
    """A hryvnia amount with no sources, which is honest for a fixture invented here."""
    return Money(amount, Currency.UAH, prov.EMPTY)


def _candidate(
    route_id: str,
    *,
    fee_pct: float = 0.0,
    cap: float | None = None,
    latency: int = 0,
    status: RouteStatus = "open",
    minimum: float | None = None,
    with_exit: bool = True,
) -> Candidate:
    """One variant of the template route, differing in exactly the fields named.

    Everything lands on the **first** leg so that the arithmetic stays trivial: the fee is
    charged on the full amount and the exit leg charges nothing, which makes the round-trip cost
    fraction equal to ``fee_pct`` exactly. A fixture whose expected cost needs working out is a
    fixture that can agree with a wrong implementation.
    """
    first, second = _TEMPLATE.route.legs
    legs = (
        dataclasses.replace(
            first,
            fee_pct=fee_pct,
            monthly_cap=None if cap is None else _uah(cap),
            latency_days=latency,
            minimum=None if minimum is None else _uah(minimum),
        ),
        dataclasses.replace(second, latency_days=0),
    )
    exit_id = f"{route_id}__exit"
    routes: dict[str, Route] = {
        route_id: dataclasses.replace(
            _TEMPLATE.route,
            id=route_id,
            legs=legs,
            status=status,
            partner_route=exit_id if with_exit else None,
        )
    }
    if with_exit:
        routes[exit_id] = dataclasses.replace(_EXIT_TEMPLATE, id=exit_id)
    return dataclasses.replace(_TEMPLATE.path, route_id=route_id), routes


def _rank(*candidates: Candidate) -> Ranking | NothingComparable:
    routes: dict[str, Route] = {}
    paths: list[FundingPath] = []
    for path, group in candidates:
        routes.update(group)
        paths.append(path)
    return ranking.rank(
        paths,
        _uah(AMOUNT),
        routes=routes,
        channels=_TEMPLATE.channels,
        streams=route_graphs.STREAMS,
        kinds=route_graphs.KINDS,
        on_date=route_graphs.ON_DATE,
        as_of=route_graphs.AS_OF,
    )


def _ranking(*candidates: Candidate) -> Ranking:
    ranked = _rank(*candidates)
    assert isinstance(ranked, Ranking), ranked
    return ranked


def _fraction(ranked: Ranking, index: int) -> float:
    round_trip = ranked.costed[index].round_trip
    assert isinstance(round_trip, RoundTripCost), round_trip
    return round_trip.fraction


def _ids(ranked: Ranking) -> list[str]:
    return [entry.path.route_id for entry in ranked.costed]


class TestATieIsReportedAsATie:
    """FR-018: on round-trip cost alone, even where the other keys differ."""

    def test_two_routes_costing_the_same_are_reported_tied(self) -> None:
        # Both charge one percent on the way in and nothing on the way out, so both cost
        # exactly 0.01 round trip. Two entries, one tie group naming both of them.
        ranked = _ranking(_candidate("first", fee_pct=0.01), _candidate("second", fee_pct=0.01))
        assert len(ranked.costed) == 2
        assert is_close(_fraction(ranked, 0), 0.01)
        assert is_close(_fraction(ranked, 1), 0.01)
        assert ranked.ties == ((0, 1),)

    def test_the_tie_holds_even_where_the_ceilings_and_latencies_differ(self) -> None:
        # This is the clause FR-018 spells out. The two routes are not identical -- one has
        # ten times the ceiling and the other is four days faster -- and they are still tied,
        # because the question asked was which is cheaper and the answer is neither.
        ranked = _ranking(
            _candidate("roomy_and_slow", fee_pct=0.01, cap=1_000_000.0, latency=5),
            _candidate("tight_and_quick", fee_pct=0.01, cap=100_000.0, latency=1),
        )
        assert ranked.ties == ((0, 1),)
        assert set(_ids(ranked)) == {"roomy_and_slow", "tight_and_quick"}

    def test_the_recommendation_is_inside_the_tie_group_so_the_reader_is_told(self) -> None:
        # The two halves held together: a deterministic order *and* an admission that the
        # head of it is not a strict winner. Reporting the order without the tie would be
        # the invented preference; reporting neither would leave nothing to act on.
        ranked = _ranking(
            _candidate("roomy_and_slow", fee_pct=0.01, cap=1_000_000.0, latency=5),
            _candidate("tight_and_quick", fee_pct=0.01, cap=100_000.0, latency=1),
        )
        assert ranked.ties
        assert ranked.recommended in ranked.ties[0]

    def test_routes_that_cost_differently_are_not_tied(self) -> None:
        ranked = _ranking(_candidate("cheap", fee_pct=0.01), _candidate("dear", fee_pct=0.02))
        assert ranked.ties == ()
        assert _ids(ranked) == ["cheap", "dear"]

    def test_a_difference_inside_the_project_tolerance_is_a_tie(self) -> None:
        # Because money is float64, two costs that should be equal after different
        # arithmetic routinely differ in the last bits. The tolerance is the width of that
        # irreducible gap and nothing else -- and the whole point of FR-018's "within the
        # project tolerance" is that such a pair is one answer, not two.
        ranked = _ranking(
            _candidate("plain", fee_pct=0.01),
            _candidate("a_hair_more", fee_pct=0.01 + 8e-10),
        )
        # Exact inequality first, with no tolerance involved at all: if the two costs were
        # the same float, the tie below would prove nothing about the tolerance.
        assert _fraction(ranked, 0) != _fraction(ranked, 1)
        assert is_close(_fraction(ranked, 0), _fraction(ranked, 1))
        assert ranked.ties == ((0, 1),)

    def test_a_tie_group_is_anchored_rather_than_chained_across_the_tolerance(self) -> None:
        # Tolerance-based equality is not transitive, so grouping needs a rule and this is
        # the rule: every member of a group is within one tolerance of the group's *first*
        # member. Chaining neighbour to neighbour would let an arbitrarily wide band become
        # one tie as candidates accumulate -- the tolerance absorbing a real difference,
        # which is the defect the tolerance module exists to warn about.
        ranked = _ranking(
            _candidate("anchor", fee_pct=0.01),
            _candidate("within_of_anchor", fee_pct=0.01 + 8e-10),
            _candidate("within_of_middle_only", fee_pct=0.01 + 1.6e-9),
        )
        anchor, middle, far = (_fraction(ranked, index) for index in range(3))
        # The relations that make the grouping the interesting case: a~b, b~c, a!~c.
        assert is_close(anchor, middle)
        assert is_close(middle, far)
        assert not is_close(anchor, far)
        assert ranked.ties == ((0, 1),)

    def test_a_route_tied_with_nothing_is_not_reported_as_a_tie(self) -> None:
        ranked = _ranking(_candidate("only_one", fee_pct=0.01))
        assert ranked.ties == ()
        assert ranked.recommended == 0


class TestTheOrderIsLexicographicOnTheThreeKeys:
    """FR-016: applied in order, never combined. **B12** forbids a composite score."""

    def test_cheaper_comes_first(self) -> None:
        ranked = _ranking(
            _candidate("dear", fee_pct=0.05),
            _candidate("cheap", fee_pct=0.01),
            _candidate("free"),
        )
        assert _ids(ranked) == ["free", "cheap", "dear"]
        assert recommended_cost(ranked).path.route_id == "free"

    def test_among_equal_costs_the_larger_ceiling_comes_first(self) -> None:
        # The second key, and only ever the second: it speaks when the first is level.
        ranked = _ranking(
            _candidate("tight", fee_pct=0.01, cap=50_000.0),
            _candidate("roomy", fee_pct=0.01, cap=500_000.0),
        )
        assert _ids(ranked) == ["roomy", "tight"]

    def test_no_declared_cap_is_the_roomiest_of_all(self) -> None:
        # ``None`` means no leg of the route declares a monthly cap, which is the least
        # constrained a route can be. Reading it as zero would rank the freest route last
        # while looking like a sensible default for a missing value -- and the field is an
        # absence of a limit, not an unknown limit.
        ranked = _ranking(
            _candidate("capped", fee_pct=0.01, cap=500_000.0),
            _candidate("uncapped", fee_pct=0.01, cap=None),
        )
        assert _ids(ranked) == ["uncapped", "capped"]

    def test_among_equal_costs_and_ceilings_the_faster_comes_first(self) -> None:
        ranked = _ranking(
            _candidate("slow", fee_pct=0.01, latency=9),
            _candidate("quick", fee_pct=0.01, latency=1),
        )
        assert _ids(ranked) == ["quick", "slow"]

    def test_a_worse_ceiling_and_a_longer_wait_cannot_outweigh_being_cheaper(self) -> None:
        # **B12**, stated as the case that would catch a score. The cheap route is capped at
        # a twentieth of the amount and takes ten days; the dear one has no cap and no
        # delay. Cost is the first key, so the cheap route wins -- and it wins by a rule
        # rather than by a weighting, because weighting hryvnia against days would require
        # an exchange rate between them that nobody has stated.
        ranked = _ranking(
            _candidate("cheap_but_capped", fee_pct=0.01, cap=500.0, latency=10),
            _candidate("dear_but_roomy", fee_pct=0.02, cap=None, latency=0),
        )
        assert _ids(ranked) == ["cheap_but_capped", "dear_but_roomy"]
        assert recommended_cost(ranked).path.route_id == "cheap_but_capped"
        assert ranked.ties == ()

    def test_the_ordering_is_the_round_trip_cost_and_not_the_one_way_one(self) -> None:
        # FR-002: the round trip is what belongs in a comparison. Here the two are the same
        # number by construction, so the assertion is on the *field consulted*: the entry
        # ordered first is the one whose round-trip figure is smallest.
        ranked = _ranking(_candidate("dear", fee_pct=0.05), _candidate("cheap", fee_pct=0.01))
        assert _fraction(ranked, 0) < _fraction(ranked, 1)


class TestAnExcludedRouteCarriesItsReason:
    """FR-014: named constraint, stated shortfall, never a silent omission."""

    def test_a_closed_route_is_excluded_with_its_status_recorded(self) -> None:
        ranked = _ranking(
            _candidate("open_one", fee_pct=0.01),
            _candidate("shut", fee_pct=0.0, status="closed"),
        )
        assert _ids(ranked) == ["open_one"]
        assert len(ranked.excluded) == 1
        refused = ranked.excluded[0]
        assert refused.path.route_id == "shut"
        assert refused.binding_constraint == "route.status"
        assert "closed" in refused.reason

    def test_an_amount_below_a_declared_minimum_is_refused_with_the_shortfall(self) -> None:
        # Never rounded up to the minimum: that would move money the owner did not agree to
        # move, and it would report the cost of a movement he did not ask for.
        ranked = _ranking(
            _candidate("usable", fee_pct=0.01),
            _candidate("too_small_for_us", minimum=50_000.0),
        )
        assert _ids(ranked) == ["usable"]
        refused = ranked.excluded[0]
        assert refused.binding_constraint == "leg.minimum"
        assert refused.required is not None
        assert refused.shortfall is not None
        assert refused.required.amount == 50_000.0
        assert refused.shortfall.amount == 50_000.0 - AMOUNT

    def test_the_cheapest_route_being_unusable_does_not_make_it_the_recommendation(
        self,
    ) -> None:
        # The refusal is not a cost of zero. A closed route that charges nothing is the
        # single most attractive-looking entry in any comparison, and it is excluded.
        ranked = _ranking(
            _candidate("dear_but_open", fee_pct=0.05),
            _candidate("free_but_shut", fee_pct=0.0, status="closed"),
        )
        assert recommended_cost(ranked).path.route_id == "dear_but_open"
        assert [item.path.route_id for item in ranked.excluded] == ["free_but_shut"]

    def test_every_refusal_appears_and_none_is_collapsed_into_a_count(self) -> None:
        ranked = _ranking(
            _candidate("usable", fee_pct=0.01),
            _candidate("shut", status="closed"),
            _candidate("too_small_for_us", minimum=50_000.0),
        )
        assert sorted(item.path.route_id for item in ranked.excluded) == [
            "shut",
            "too_small_for_us",
        ]
        assert all(item.reason for item in ranked.excluded)


class TestARouteWithNoDeclaredExitIsCostedButNotRanked:
    """SC-014, FR-030: reported, kept out of the comparison, never promoted."""

    def test_it_lands_in_not_comparable_and_out_of_the_ranking(self) -> None:
        ranked = _ranking(
            _candidate("round_trip_known", fee_pct=0.02),
            _candidate("no_way_back", fee_pct=0.0, with_exit=False),
        )
        assert _ids(ranked) == ["round_trip_known"]
        assert [entry.path.route_id for entry in ranked.not_comparable] == ["no_way_back"]

    def test_the_cheapest_route_going_in_is_not_recommended_when_nobody_costed_the_exit(
        self,
    ) -> None:
        # The test that carries SC-014. The exit-less route is free one way and the ranked
        # one charges two percent, so promoting the one-way figure would make the exit-less
        # route the winner -- a confident round-trip number for a path nobody has looked at.
        ranked = _ranking(
            _candidate("round_trip_known", fee_pct=0.02),
            _candidate("no_way_back", fee_pct=0.0, with_exit=False),
        )
        assert recommended_cost(ranked).path.route_id == "round_trip_known"
        orphan = ranked.not_comparable[0]
        assert orphan.one_way.fraction == 0.0
        assert isinstance(orphan.round_trip, ExitCostUnknown)
        assert orphan.round_trip.missing_partner_for == "no_way_back"

    def test_its_one_way_figure_is_still_reported_because_it_is_a_real_number(self) -> None:
        # Not comparable is not the same as not costed. The one-way cost is known, so it is
        # reported; what is missing is the round trip, and nothing invents one.
        ranked = _ranking(
            _candidate("round_trip_known", fee_pct=0.02),
            _candidate("no_way_back", fee_pct=0.03, with_exit=False),
        )
        orphan = ranked.not_comparable[0]
        assert is_close(orphan.one_way.fraction, 0.03)
        assert not hasattr(orphan.round_trip, "fraction")

    def test_it_is_not_counted_among_the_exclusions_either(self) -> None:
        # Two different facts. An excluded route could not carry the amount; this one could,
        # and the gap is a declaration nobody has written. The owner acts differently on
        # each, so they are reported in different fields.
        ranked = _ranking(
            _candidate("round_trip_known", fee_pct=0.02),
            _candidate("no_way_back", with_exit=False),
        )
        assert ranked.excluded == ()
        assert len(ranked.not_comparable) == 1


class TestNothingIsSilentlyDropped:
    """Every candidate lands in exactly one of the three fields, always."""

    @pytest.mark.parametrize(
        "candidates",
        [
            (("only", {"fee_pct": 0.01}),),
            (("a", {"fee_pct": 0.01}), ("b", {"status": "closed"})),
            (("a", {"fee_pct": 0.01}), ("b", {"with_exit": False})),
            (
                ("a", {"fee_pct": 0.01}),
                ("b", {"status": "closed"}),
                ("c", {"with_exit": False}),
                ("d", {"minimum": 50_000.0}),
            ),
        ],
    )
    def test_the_three_fields_partition_the_candidates(
        self, candidates: tuple[tuple[str, Mapping[str, object]], ...]
    ) -> None:
        built = [_candidate(name, **kwargs) for name, kwargs in candidates]  # type: ignore[arg-type]
        ranked = _ranking(*built)
        reported = [
            *(entry.path.route_id for entry in ranked.costed),
            *(entry.path.route_id for entry in ranked.not_comparable),
            *(item.path.route_id for item in ranked.excluded),
        ]
        assert sorted(reported) == sorted(name for name, _ in candidates)
        assert len(reported) == len(set(reported))
