"""SC-016 and FR-029: the winner and the alternatives came out of one function.

FR-029: *every candidate route MUST be costed **in full, through the same path as the
recommendation** -- never summarised, estimated, or costed by a cheaper approximation. A
comparison whose alternatives were priced differently from its winner is not a comparison; it
is a recommendation with decoration.* SC-016 asks for that *by construction*, and this module
is where "by construction" is cashed out.

**The mechanism is that the recommendation is an index** (research.md D3). ``Ranking`` holds
``costed: tuple[RampCost, ...]`` and ``recommended: int``, and ``recommended_cost(r)`` is
``r.costed[r.recommended]`` and nothing else. So the winner is not *compared against* the
alternatives -- it **is** one of them, and the assertion below uses ``is`` rather than ``==``.
That distinction is the whole test: two numbers that agree today prove nothing about
tomorrow, whereas the same object cannot disagree with itself.

**The shape that was rejected** is the natural one:
``Ranking(recommended: RampCost, alternatives: tuple[RampCost, ...])``. It reads better and it
is wrong: ``recommended`` would be a separate value that *could* have been produced by a
separate path, and a test comparing it to the alternatives would be comparing two numbers
rather than establishing they share an origin. A field of that shape is therefore asserted
absent below, because the day someone adds it "for convenience" is the day FR-029 stops being
structural.

**Three further scans, because identity alone is not the whole requirement.** A ranking could
hold one object per candidate and still have costed them differently on the way in. So this
module also asserts that every entry in a ranking equals what ``cost_one`` returns for the
same path; that exactly one function in the engine produces a ``RampCost`` at all; and that
the ranking module contains no money arithmetic of its own -- no ``money.*`` call, no rate,
no spread. There is nowhere for a second code path to be.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import inspect
import pkgutil
import textwrap
from collections.abc import Iterator, Mapping, Sequence
from typing import Any, get_type_hints

import pytest

import terezy.core.results
import terezy.core.routes
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results import ramp
from terezy.core.results.coverage import SpendableEndpoint
from terezy.core.results.ramp import (
    NothingComparable,
    RampCost,
    Ranking,
    RouteUnusable,
    recommended_cost,
)
from terezy.core.routes import cost, ranking
from terezy.core.routes.legs import Route
from terezy.core.routes.path import FundingPath
from tests.invariants import route_graphs

pytestmark = pytest.mark.contract

SPENDABLE: frozenset[SpendableEndpoint] = frozenset()
"""**Nowhere is declared spendable here, and that is deliberate.**

These fixtures predate the spendable list and their subject is 002's partner rule: a route
with a declared way out, and one without. A destination that happened to appear in this set
would satisfy its own exit requirement by identity (003 FR-002) and quietly acquire a
round-trip figure, turning "nobody costed the way out" into "there was nothing to do" --
which is a different claim and is exercised where it belongs, in the composed suites and in
``tests/invariants/test_coverage_costing_agreement.py``.
"""

AMOUNT = Money(10_000.0, Currency.UAH, prov.EMPTY)
"""One amount for every candidate, which is what makes a comparison a comparison."""


def _candidates() -> tuple[Mapping[str, Route], Sequence[FundingPath]]:
    """Three routes worth ranking: two comparable, one with no declared exit.

    The third is deliberately included. A ranking whose every candidate is comparable would
    never exercise the split between ``costed`` and ``not_comparable``, and the identity
    assertion would then be true of a list that happened to hold everything.
    """
    domestic = route_graphs.zero_cost_graph(with_exit=True)
    offshore = route_graphs.p2p_graph()
    orphan_route = dataclasses.replace(
        offshore.route, id="p2p_with_no_declared_exit", partner_route=None
    )
    routes: dict[str, Route] = {**domestic.routes, **offshore.routes}
    routes[orphan_route.id] = orphan_route
    paths = (
        domestic.path,
        offshore.path,
        dataclasses.replace(offshore.path, route_id=orphan_route.id),
    )
    return routes, paths


def _ranked() -> Ranking:
    routes, paths = _candidates()
    ranked = ranking.rank(
        paths,
        AMOUNT,
        routes=routes,
        channels=route_graphs.p2p_graph().channels,
        streams=route_graphs.STREAMS,
        kinds=route_graphs.KINDS,
        on_date=route_graphs.ON_DATE,
        as_of=route_graphs.AS_OF,
        spendable=SPENDABLE,
    )
    assert isinstance(ranked, Ranking), ranked
    return ranked


class TestTheRecommendationIsAnIndexIntoWhatWasRanked:
    """SC-016, asserted with ``is``. The point of the whole design."""

    def test_the_recommended_cost_is_the_very_object_in_the_costed_tuple(self) -> None:
        # ``is``, not ``==``. Equality would pass for two figures computed by two paths
        # that happened to agree on this input, which is precisely the reassurance FR-029
        # says a comparison must not rest on.
        ranked = _ranked()
        assert recommended_cost(ranked) is ranked.costed[ranked.recommended]

    def test_the_recommendation_is_an_integer_position_and_not_a_second_copy(self) -> None:
        ranked = _ranked()
        assert isinstance(ranked.recommended, int)
        assert 0 <= ranked.recommended < len(ranked.costed)
        assert get_type_hints(Ranking)["recommended"] is int

    def test_no_field_of_a_ranking_holds_a_single_cost_of_its_own(self) -> None:
        # The rejected shape, asserted absent: a ``recommended: RampCost`` field would be a
        # second place for a cost to come from, and no test could then establish that the
        # two places agree for reasons other than luck.
        hints = get_type_hints(Ranking)
        assert not [name for name, annotation in hints.items() if annotation is RampCost]

    def test_recommended_cost_reads_the_tuple_rather_than_computing_anything(self) -> None:
        # Asserted on the source, because the guarantee is about what the function *does
        # not* do. A projection out of a tuple cannot disagree with the tuple; anything
        # that recomputed a figure here would reintroduce the second path by the back door.
        referenced = _code_references(inspect.getsource(recommended_cost))
        assert "costed" in referenced
        assert "recommended" in referenced
        assert not referenced & (COMPUTES_MONEY | {"cost_one", "rank"})


class TestEveryCandidateWasCostedByTheOneCostingFunction:
    """FR-029 from the other side: the alternatives are not summaries."""

    def test_every_ranked_entry_equals_what_cost_one_returns_for_its_path(self) -> None:
        # Equality is the right relation here, unlike above: these are two *calls*, and the
        # claim is that ranking added no arithmetic of its own. Purity makes the comparison
        # meaningful -- ``cost_one`` called twice with equal arguments returns equal results.
        routes, _ = _candidates()
        ranked = _ranked()
        for entry in (*ranked.costed, *ranked.not_comparable):
            assert entry == cost.cost_one(
                entry.path,
                AMOUNT,
                routes=routes,
                channels=route_graphs.p2p_graph().channels,
                streams=route_graphs.STREAMS,
                kinds=route_graphs.KINDS,
                on_date=route_graphs.ON_DATE,
                as_of=route_graphs.AS_OF,
                spendable=SPENDABLE,
            )

    def test_every_candidate_appears_exactly_once_somewhere(self) -> None:
        # Nothing is silently dropped (FR-014). A route that fell out of the comparison
        # without landing in ``excluded`` or ``not_comparable`` would be invisible, and an
        # invisible exclusion is how a ranking comes to recommend the only route left.
        _, paths = _candidates()
        ranked = _ranked()
        reported = [
            *(entry.path for entry in ranked.costed),
            *(entry.path for entry in ranked.not_comparable),
            *(entry.path for entry in ranked.excluded),
        ]
        assert sorted(reported, key=str) == sorted(paths, key=str)


def _modules() -> Iterator[Any]:
    """Every module of the two packages that could hold a costing function.

    Walked rather than listed, because a hand-written list stops covering the package the
    moment someone adds a file -- and it stops silently, which is the failure mode this
    module exists to prevent one level up.
    """
    for package in (terezy.core.routes, terezy.core.results):
        yield package
        for info in pkgutil.iter_modules(package.__path__):
            yield importlib.import_module(f"{package.__name__}.{info.name}")


def _public_functions() -> Iterator[tuple[str, Any]]:
    for module in _modules():
        for name, value in vars(module).items():
            if name.startswith("_") or inspect.isclass(value) or not callable(value):
                continue
            if getattr(value, "__module__", None) != module.__name__:
                continue  # imported from elsewhere; scanned where it is defined
            yield f"{module.__name__}.{name}", value


def _dotted(node: ast.Attribute) -> str:
    """``money.scale`` for the expression ``money.scale(...)``, and ``""`` for anything else.

    Only the one-level ``name.attr`` form is spelt out, because that is the shape every call
    the scans below care about takes: ``money.add``, ``cost.cost_one``, ``channels.side_for``.
    """
    if isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    return ""


def _code_references(source: str) -> frozenset[str]:
    """Every name and dotted attribute the code *references*, ignoring prose entirely.

    Parsed rather than grepped, and that is not a refinement -- it is what makes the scans
    honest. A substring search over the source hits docstrings and comments too, so a module
    that merely *explained* why it does not scale money would fail; and the obvious fix to
    such a failure is to stop naming the thing in the prose, or worse, to loosen the scan.
    An AST walk sees only what the module actually does.
    """
    tree = ast.parse(textwrap.dedent(source))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
            dotted = _dotted(node)
            if dotted:
                names.add(dotted)
    return frozenset(names)


COMPUTES_MONEY = frozenset(
    {
        "money.add",
        "money.sub",
        "money.scale",
        "money.scale_sourced",
        "money.convert",
        "money.total",
        "loss_fraction",
        "spread_over_reference",
        "effective_rate",
        "side_for",
        "LEG_COST_FNS",
        "cost_fn_for",
    }
)
"""Every way there is of pricing something. A module referencing none of these priced nothing."""


class TestThereIsOnlyOneCostingFunctionToBeginWith:
    """The structural claim behind FR-029, scanned rather than asserted in prose."""

    def test_exactly_two_functions_yield_a_ramp_cost_and_only_one_of_them_computes(
        self,
    ) -> None:
        # ``cost_one`` computes one; ``recommended_cost`` projects one out of a tuple it was
        # handed. Any third would be the second code path, whatever it was called -- a
        # "quick estimate", a "summary cost", a cached variant. The allow-list is two names
        # long so that adding one is a visible act.
        producers = {
            name
            for name, value in _public_functions()
            if "RampCost" in str(inspect.signature(value).return_annotation)
        }
        assert producers == {
            "terezy.core.routes.cost.cost_one",
            "terezy.core.results.ramp.recommended_cost",
        }

    def test_the_ranking_module_contains_no_arithmetic_of_its_own(self) -> None:
        # If ranking cannot add, subtract, scale or convert money, and cannot reach a
        # channel or the leg registry, then it cannot have priced anything. It orders what
        # ``cost_one`` gave it, and that is the whole of FR-029's guarantee.
        offenders = _code_references(inspect.getsource(ranking)) & COMPUTES_MONEY
        assert not offenders, (
            "the ranking module computes money, so it is a second costing path (FR-029): "
            + ", ".join(sorted(offenders))
        )

    def test_ranking_calls_the_costing_function_by_name(self) -> None:
        # The positive half. A scan for what is absent passes vacuously if the module never
        # costed anything at all, so this asserts the call it is supposed to make.
        assert "cost.cost_one" in _code_references(inspect.getsource(ranking))


class TestTheScansWouldActuallyCatchAViolation:
    """Every structural scan above is only worth having if it can fail."""

    def test_the_producer_scan_sees_a_decoy_summary_function(self) -> None:
        def summarise(path: FundingPath) -> RampCost:
            """The tempting second path: a cheap figure for the also-rans."""
            raise NotImplementedError

        assert "RampCost" in str(inspect.signature(summarise).return_annotation)

    def test_the_rejected_ranking_shape_would_be_caught(self) -> None:
        @dataclasses.dataclass(frozen=True)
        class ScoredRanking:
            recommended: RampCost
            alternatives: tuple[RampCost, ...]

        hints = get_type_hints(ScoredRanking)
        assert [name for name, annotation in hints.items() if annotation is RampCost]

    def test_the_module_walk_actually_finds_the_functions(self) -> None:
        # If the walk returned nothing, every scan above would pass vacuously.
        found = {name for name, _ in _public_functions()}
        assert "terezy.core.routes.ranking.rank" in found
        assert "terezy.core.routes.cost.cost_one" in found


class TestNothingComparableIsNotARankingWithAnEmptySlot:
    """The case the design documents did not settle: no candidate is comparison-ready.

    ``Ranking.recommended`` is an ``int`` index, and there is no honest integer to put in it
    when ``costed`` is empty. A sentinel would be worse than the problem: ``-1`` indexes the
    last element of a tuple in Python, so a ranking that had recommended nothing would
    silently recommend something.

    So the empty case is its own typed value, carrying the reasons rather than losing them --
    the same shape as ``ExitCostUnknown`` and for the same reason. The consequence is that
    every ``Ranking`` in existence has a valid recommendation, which is what lets
    ``recommended_cost`` be total.
    """

    def test_a_ranking_of_only_unusable_routes_is_not_a_ranking(self) -> None:
        graph = route_graphs.zero_cost_graph(with_exit=True)
        closed = dataclasses.replace(graph.route, status="closed")
        outcome = ranking.rank(
            [graph.path],
            AMOUNT,
            routes={**graph.routes, closed.id: closed},
            channels=graph.channels,
            streams=route_graphs.STREAMS,
            kinds=route_graphs.KINDS,
            on_date=route_graphs.ON_DATE,
            as_of=route_graphs.AS_OF,
            spendable=SPENDABLE,
        )
        assert isinstance(outcome, NothingComparable)
        assert len(outcome.excluded) == 1
        assert outcome.excluded[0].binding_constraint == "route.status"
        assert "closed" in outcome.reason

    def test_a_ranking_of_only_exit_less_routes_is_not_a_ranking_either(self) -> None:
        # Costed, reported, and out of the comparison (FR-030). The reason names the count,
        # because "nothing was comparable" and "nothing was costable" are different facts.
        graph = route_graphs.zero_cost_graph()
        assert graph.route.partner_route is None
        outcome = ranking.rank(
            [graph.path],
            AMOUNT,
            routes=graph.routes,
            channels=graph.channels,
            streams=route_graphs.STREAMS,
            kinds=route_graphs.KINDS,
            on_date=route_graphs.ON_DATE,
            as_of=route_graphs.AS_OF,
            spendable=SPENDABLE,
        )
        assert isinstance(outcome, NothingComparable)
        assert len(outcome.not_comparable) == 1
        assert outcome.excluded == ()

    def test_a_mixture_of_the_two_failures_reports_both_counts(self) -> None:
        # The fourth branch, and the one a reader is most likely to meet in practice: some
        # routes refused, the rest costed with no declared exit. The two facts are separate
        # and the owner acts differently on each -- one is about limits and dates, the other
        # about a declaration nobody has written -- so the reason names both counts rather
        # than reporting "nothing to rank" and leaving him to work out which happened.
        refusable = route_graphs.zero_cost_graph(with_exit=True)
        closed = dataclasses.replace(refusable.route, status="closed")
        orphan = dataclasses.replace(
            route_graphs.p2p_graph().route, id="no_way_back", partner_route=None
        )
        outcome = ranking.rank(
            [
                refusable.path,
                dataclasses.replace(route_graphs.p2p_graph().path, route_id=orphan.id),
            ],
            AMOUNT,
            routes={closed.id: closed, orphan.id: orphan},
            channels=route_graphs.p2p_graph().channels,
            streams=route_graphs.STREAMS,
            kinds=route_graphs.KINDS,
            on_date=route_graphs.ON_DATE,
            as_of=route_graphs.AS_OF,
            spendable=SPENDABLE,
        )
        assert isinstance(outcome, NothingComparable)
        assert len(outcome.excluded) == 1
        assert len(outcome.not_comparable) == 1
        assert "1 candidate route(s) were refused" in outcome.reason
        assert "1 were" in outcome.reason

    def test_no_paths_at_all_is_the_same_answer_rather_than_a_zero_cost_one(self) -> None:
        outcome = ranking.rank(
            [],
            AMOUNT,
            routes={},
            channels={},
            streams=route_graphs.STREAMS,
            kinds=route_graphs.KINDS,
            on_date=route_graphs.ON_DATE,
            as_of=route_graphs.AS_OF,
            spendable=SPENDABLE,
        )
        assert isinstance(outcome, NothingComparable)
        assert outcome.excluded == ()
        assert outcome.not_comparable == ()

    def test_the_two_outcomes_are_unrelated_types_so_neither_fills_the_others_slot(
        self,
    ) -> None:
        # The precedent of ``RoundTripCost | ExitCostUnknown``, one level up: no shared
        # base, so a caller that forgot the empty case is a mypy error rather than an
        # ``IndexError`` in front of the owner.
        assert Ranking.__bases__ == (object,)
        assert NothingComparable.__bases__ == (object,)
        assert not issubclass(NothingComparable, Ranking)
        assert {field.name for field in dataclasses.fields(NothingComparable)} == {
            "reason",
            "excluded",
            "not_comparable",
        }

    def test_the_reasons_are_carried_rather_than_summarised_away(self) -> None:
        # Whatever went wrong, the records that say so are the same records a ``Ranking``
        # would have carried -- ``RouteUnusable`` for a refusal, a costed ``RampCost`` for a
        # missing exit. Nothing is reduced to a count on the way out.
        hints = get_type_hints(NothingComparable)
        assert hints["excluded"] == tuple[RouteUnusable, ...]
        assert hints["not_comparable"] == tuple[RampCost, ...]
        assert hints["excluded"] == get_type_hints(Ranking)["excluded"]
        assert hints["not_comparable"] == get_type_hints(Ranking)["not_comparable"]


def test_the_ranking_records_live_beside_the_costs_they_are_made_of() -> None:
    """``Ranking`` is a result record, so it sits with the other result records.

    Stated as an assertion because the alternative placement -- in ``core.routes.ranking``
    beside ``rank`` -- is the more obvious one and the wrong one. data-model.md lists
    ``Ranking`` under Results alongside ``RampCost`` and ``RouteUnusable``, and
    ``recommended_cost`` is a free function over a frozen record, which owner decision D-E
    puts in the record's own module rather than in the module that happens to build it.
    """
    assert Ranking.__module__ == ramp.__name__
    assert NothingComparable.__module__ == ramp.__name__
    assert recommended_cost.__module__ == ramp.__name__
    assert ranking.rank.__module__ == "terezy.core.routes.ranking"
