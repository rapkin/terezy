"""G6, FR-002, SC-005: every cost figure in the output is labelled one way or round trip.

FR-002: *the system MUST report cost both **one way** and **round trip**, each explicitly
labelled, and MUST NOT present a one-way figure where a round-trip figure belongs.* SC-005 turns
that into a measurement: *no cost figure anywhere in the output is presented without an explicit
one-way or round-trip label -- **verified across every reported figure, not sampled**.* Required
test **G6** is the same claim in the required-test list: no comparison reports a one-way cost as
round-trip.

**Why "not sampled" is the operative word.** ``tests/unit/test_round_trip_types.py`` already
asserts that the two records are unrelated types, which is what stops a one-way figure being
*assigned* into a round-trip slot. What no type can catch is a *third* place a cost figure might
appear -- a ``total_cost`` on a summary record, a ``fraction`` promoted onto ``RampCost`` for
convenience, a rendered figure in a ranking. Each of those is perfectly well typed, and each
would be an unlabelled cost. So this module works two ways round:

* **Structurally**, over every dataclass in ``terezy.core.results`` and ``terezy.core.routes``:
  the fields that *are* a cost figure may live only in the two labelled records, and any field
  holding one of those records must be named ``one_way`` or ``round_trip``.
* **By value**, over a real ``RampCost`` and a real ``Ranking``: every ``Money`` reachable in the
  result is enumerated with the field path that reaches it, and each must either pass through a
  labelled field or be a declared non-cost figure -- a ceiling, a limit, a shortfall.

The second is what makes "every figure, not sampled" true rather than asserted. It walks the
whole record; nothing is picked out.

**The classification is closed, which is the point.** A new field on any of these records fails
this module until it is named in one of the two lists below. That is deliberate friction: the
list is where a reader learns whether a figure is a cost, and a field that nobody classified is a
figure nobody labelled.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import pkgutil
from collections.abc import Iterator, Mapping
from typing import Any, get_type_hints

import pytest

import terezy.core.results
import terezy.core.routes
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.ramp import (
    CostComponent,
    ExitCostUnknown,
    NothingComparable,
    OneWayCost,
    RampCost,
    Ranking,
    RoundTripCost,
    RouteUnusable,
    recommended_cost,
)
from terezy.core.routes import cost, ranking
from tests.invariants import route_graphs

pytestmark = pytest.mark.contract

LABELS = ("one_way", "round_trip")
"""The only two labels a cost figure may carry, and the only two field names that carry them."""

COST_FIGURE_FIELDS = frozenset({"sent", "arrived", "components", "fraction"})
"""The fields that *are* a cost figure, rather than merely sitting near one.

What was sent, what arrived, how the gap between them breaks down, and that gap as a fraction.
Any record carrying one of these is pricing something, and pricing is what FR-002 requires to be
labelled.
"""

NON_COST_MONEY_FIELDS = frozenset(
    {
        "ceiling",
        "required",
        "actual",
        "shortfall",
        "minimum",
        "maximum",
        "monthly_cap",
        "fee_fixed",
        "premium_per_unit",
    }
)
"""``Money``-valued fields that are **not** cost figures, each for a stated reason.

* ``ceiling`` -- the tightest declared monthly cap on the route. A limit on what may pass, not a
  charge on what did.
* ``required`` / ``actual`` / ``shortfall`` -- what a refused constraint demanded, what was
  offered, and the gap. A refusal is not a price; ``RouteUnusable`` deliberately carries no cost
  at all, because a zero there would read as "free".
* ``minimum`` / ``maximum`` / ``monthly_cap`` / ``fee_fixed`` / ``premium_per_unit`` -- declared
  inputs on a ``Leg`` or a ``ChannelSide``. A declaration is not an outcome: ``fee_fixed`` is the
  tariff, and what it *charged* on a given amount appears inside a labelled record as
  ``components[FIXED_FEE]``.

A figure not on this list and not inside a labelled record is an unlabelled cost, which is what
this module fails on.
"""

NON_COST_FIELDS = frozenset(
    {
        # Keys and identity.
        "path",
        "id",
        # Reported beside a cost, never inside one.
        "latency_days",
        "status",
        "disruption_probability",
        "channels_applied",
        # §4.3.1's rate-space spread. Deliberately **not** a cost figure: it is a fraction of
        # the reference *rate*, not of the money, and the two differ on the buy side (6.67%
        # against 7.14%). It sits here rather than in COST_FIGURE_FIELDS precisely so that
        # reporting it where a cost belongs would fail this test -- which is the mistake that
        # already shipped once, reporting an arriving amount short of what the venue pays.
        "spreads_over_reference",
        # Provenance and staleness travel with every figure; they are not figures.
        "provenance",
        "staleness",
        # Typed statements of absence and refusal.
        "reason",
        "missing_partner_for",
        "binding_constraint",
        # A ranking holds costs; it is not itself one.
        "costed",
        "recommended",
        "excluded",
        "ties",
        "not_comparable",
    }
    | NON_COST_MONEY_FIELDS
)
"""Every field of a result record that is not a cost figure. Together with
:data:`COST_FIGURE_FIELDS` and :data:`LABELS` this must cover **every** field of every result
record -- that totality is the "not sampled" clause, and an unclassified field fails the scan.
"""

RESULT_RECORDS = (
    OneWayCost,
    RoundTripCost,
    ExitCostUnknown,
    RampCost,
    RouteUnusable,
    Ranking,
    NothingComparable,
)
"""Every record a comparison hands out, including the two that report a failure.

The failures are here rather than left to the package-wide scans below because they are the
records most likely to grow a figure: a ``RouteUnusable`` that acquired a "cost had it worked"
would be an unlabelled cost on the one record whose whole point is that there is no cost.
"""


def _modules() -> Iterator[Any]:
    for package in (terezy.core.results, terezy.core.routes):
        yield package
        for info in pkgutil.iter_modules(package.__path__):
            yield importlib.import_module(f"{package.__name__}.{info.name}")


def _records() -> Iterator[tuple[str, Any]]:
    """Every public frozen record in the two packages, walked rather than listed.

    A hand-written list stops covering the packages the moment someone adds a record, and it
    stops silently -- which is precisely the failure this module exists to prevent one level up.
    """
    for module in _modules():
        for name, value in vars(module).items():
            if name.startswith("_") or not inspect.isclass(value):
                continue
            if getattr(value, "__module__", None) != module.__name__:
                continue
            if dataclasses.is_dataclass(value):
                yield f"{module.__name__}.{name}", value


def _money_paths(value: Any, prefix: str = "") -> Iterator[tuple[str, Money]]:
    """Every ``Money`` reachable from a value, with the dotted field path that reaches it.

    Recursive over records, mappings and tuples, which is every container a result uses.
    ``Money`` is checked first because it is itself a record, and recursing into it would report
    its ``amount`` rather than the figure the path is about.
    """
    if isinstance(value, Money):
        yield prefix, value
        return
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for field in dataclasses.fields(value):
            child = getattr(value, field.name)
            yield from _money_paths(child, f"{prefix}.{field.name}" if prefix else field.name)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            name = key.name if isinstance(key, CostComponent) else key
            yield from _money_paths(item, f"{prefix}[{name}]")
        return
    if isinstance(value, tuple):
        for index, item in enumerate(value):
            yield from _money_paths(item, f"{prefix}[{index}]")


def _is_labelled(path: str) -> bool:
    """Whether a dotted path passes through a one-way or round-trip field on its way down."""
    segments = [segment.split("[")[0] for segment in path.split(".")]
    return any(label in segments for label in LABELS)


def _leaf(path: str) -> str:
    return path.rsplit(".", maxsplit=1)[-1].split("[", maxsplit=1)[0]


def _cost_one_of(graph: route_graphs.Graph) -> RampCost | Any:
    """Cost ten thousand hryvnia along a fixture's path. One amount, so paths are comparable."""
    return cost.cost_one(
        graph.path,
        Money(10_000.0, Currency.UAH, prov.EMPTY),
        routes=graph.routes,
        channels=graph.channels,
        streams=route_graphs.STREAMS,
        kinds=route_graphs.KINDS,
        on_date=route_graphs.ON_DATE,
        as_of=route_graphs.AS_OF,
    )


def _costed() -> RampCost:
    costed = _cost_one_of(route_graphs.p2p_graph())
    assert isinstance(costed, RampCost), costed
    return costed


def _ranked() -> Ranking:
    domestic = route_graphs.zero_cost_graph(with_exit=True)
    offshore = route_graphs.p2p_graph()
    ranked = ranking.rank(
        [domestic.path, offshore.path],
        Money(10_000.0, Currency.UAH, prov.EMPTY),
        routes={**domestic.routes, **offshore.routes},
        channels=offshore.channels,
        streams=route_graphs.STREAMS,
        kinds=route_graphs.KINDS,
        on_date=route_graphs.ON_DATE,
        as_of=route_graphs.AS_OF,
    )
    assert isinstance(ranked, Ranking), ranked
    return ranked


class TestACostFigureLivesOnlyInALabelledRecord:
    """The structural half: there is no third place for a price to appear."""

    def test_only_the_two_labelled_records_carry_a_cost_figure(self) -> None:
        # A ``fraction`` promoted onto ``RampCost`` "for convenience" would be an unlabelled
        # cost, and it would be the one a caller reached for first. So the set of records
        # carrying a cost figure is asserted to be exactly the two that carry a label.
        carriers = {
            name
            for name, record in _records()
            if {field.name for field in dataclasses.fields(record)} & COST_FIGURE_FIELDS
        }
        assert carriers == {
            "terezy.core.results.ramp.OneWayCost",
            "terezy.core.results.ramp.RoundTripCost",
        }

    def test_every_field_holding_a_one_way_figure_is_named_one_way(self) -> None:
        offenders = [
            f"{name}.{field}"
            for name, record in _records()
            for field, annotation in get_type_hints(record).items()
            if "OneWayCost" in str(annotation) and field != "one_way"
        ]
        assert not offenders, (
            "these hold a one-way cost under some other name, so the label no longer "
            "travels with the figure (FR-002): " + ", ".join(sorted(offenders))
        )

    def test_every_field_holding_a_round_trip_figure_is_named_round_trip(self) -> None:
        offenders = [
            f"{name}.{field}"
            for name, record in _records()
            for field, annotation in get_type_hints(record).items()
            if "RoundTripCost" in str(annotation) and field != "round_trip"
        ]
        assert not offenders, (
            "these hold a round-trip cost under some other name (FR-002): "
            + ", ".join(sorted(offenders))
        )

    def test_no_result_record_invents_an_unlabelled_name_for_a_cost(self) -> None:
        # The names a well-meaning author reaches for when adding a summary *ramp cost*
        # figure. Every one of them would be a cost with no label, and every one reads as
        # helpful. Deliberately synonyms of "what the route charged" and nothing wider:
        # ``CashFlowRow.net`` in feature 001 is a coupon net of tax, which is a real figure
        # whose label is its own record, and a list broad enough to catch it would be
        # asserting a naming convention rather than FR-002.
        tempting = frozenset(
            {
                "cost",
                "total_cost",
                "cost_pct",
                "cost_fraction",
                "total",
                "spread",
                "access_cost",
                "ramp_cost",
                "round_trip_cost",
                "one_way_cost",
            }
        )
        offenders = [
            f"{name}.{field.name}"
            for name, record in _records()
            for field in dataclasses.fields(record)
            if field.name in tempting
        ]
        assert not offenders, (
            "these are cost figures under names that say nothing about one way or round "
            "trip (SC-005): " + ", ".join(sorted(offenders))
        )


class TestEveryFieldIsClassifiedRatherThanSampled:
    """SC-005's "verified across every reported figure": the classification is total."""

    @pytest.mark.parametrize("record", RESULT_RECORDS, ids=lambda record: record.__name__)
    def test_every_field_is_either_a_label_a_cost_figure_or_a_declared_non_cost(
        self, record: type
    ) -> None:
        # The closed classification. A field nobody has put in one of the three buckets is a
        # figure nobody has labelled, and the friction of having to classify it is the whole
        # mechanism -- it is where a reader learns whether a new figure is a cost.
        unclassified = [
            field.name
            for field in dataclasses.fields(record)
            if field.name not in LABELS
            and field.name not in COST_FIGURE_FIELDS
            and field.name not in NON_COST_FIELDS
        ]
        assert not unclassified, (
            f"{record.__name__} has fields that are neither labelled costs, cost figures, "
            "nor declared non-costs, so whether they are prices is unstated (SC-005): "
            + ", ".join(sorted(unclassified))
        )

    def test_the_two_buckets_do_not_overlap(self) -> None:
        # If a name were in both lists the scan above would pass for the wrong reason, and a
        # genuine cost figure could be excused as a declared non-cost.
        assert not COST_FIGURE_FIELDS & NON_COST_FIELDS
        assert not COST_FIGURE_FIELDS & frozenset(LABELS)


class TestEveryMoneyInARealResultIsLabelledOrDeclaredNotACost:
    """The value half: the whole record walked, nothing picked out."""

    def test_a_costed_route_exposes_no_unlabelled_money(self) -> None:
        paths = dict(_money_paths(_costed()))
        assert paths, "the walk found no money at all, so it proves nothing"
        offenders = [
            path
            for path in paths
            if not _is_labelled(path) and _leaf(path) not in NON_COST_MONEY_FIELDS
        ]
        assert not offenders, (
            "these amounts are reachable in a RampCost without passing through a one-way or "
            "round-trip label (G6, SC-005): " + ", ".join(sorted(offenders))
        )

    def test_the_walk_reaches_the_figures_it_is_supposed_to_check(self) -> None:
        # A negative scan passes vacuously if the walk never descended. These are the paths
        # that must be there for the assertion above to mean anything.
        paths = set(dict(_money_paths(_costed())))
        assert "one_way.sent" in paths
        assert "one_way.arrived" in paths
        assert "one_way.components[CONVERSION_SPREAD]" in paths
        assert "round_trip.sent" in paths
        assert "round_trip.arrived" in paths

    def test_a_whole_ranking_exposes_no_unlabelled_money_either(self) -> None:
        # The record a comparison actually hands out. Every amount in it sits under
        # ``costed[i].one_way`` or ``costed[i].round_trip`` -- or is a ceiling, which is a
        # limit rather than a charge.
        paths = dict(_money_paths(_ranked()))
        offenders = [
            path
            for path in paths
            if not _is_labelled(path) and _leaf(path) not in NON_COST_MONEY_FIELDS
        ]
        assert not offenders, ", ".join(sorted(offenders))
        assert any(path.startswith("costed[0].one_way") for path in paths)
        assert any(path.startswith("costed[0].round_trip") for path in paths)

    def test_the_scan_would_catch_an_unlabelled_figure(self) -> None:
        # The decoy: a summary record with a cost on it and no label anywhere in the path.
        @dataclasses.dataclass(frozen=True)
        class Summary:
            total_cost: Money

        offenders = [
            path
            for path, _ in _money_paths(Summary(total_cost=Money(1.0, Currency.UAH, prov.EMPTY)))
            if not _is_labelled(path) and _leaf(path) not in NON_COST_MONEY_FIELDS
        ]
        assert offenders == ["total_cost"]


class TestNoComparisonReportsAOneWayFigureAsRoundTrip:
    """**G6** itself, on a real comparison rather than on a type annotation."""

    def test_the_two_figures_of_a_p2p_route_are_different_numbers(self) -> None:
        # If a round trip ever equalled its one way on a route with a spread both ways, the
        # promotion would have happened. 6.67% in, 13.33% there and back.
        costed = _costed()
        assert isinstance(costed.round_trip, RoundTripCost)
        assert costed.round_trip.fraction > costed.one_way.fraction
        assert costed.round_trip.arrived != costed.one_way.arrived

    def test_the_round_trip_slot_of_every_ranked_entry_holds_a_round_trip_figure(self) -> None:
        # Only the positive half is assertable. ``assert not isinstance(..., OneWayCost)``
        # is a **mypy error** here -- "subclass of RoundTripCost and OneWayCost cannot
        # exist: have distinct disjoint bases" -- which is the type separation of
        # research.md D4 reporting itself. The negative claim is proved statically, so
        # writing it at runtime would be asserting that the type checker ran.
        for entry in _ranked().costed:
            assert isinstance(entry.round_trip, RoundTripCost)

    def test_a_missing_exit_leaves_the_slot_holding_a_statement_rather_than_a_number(
        self,
    ) -> None:
        costed = _cost_one_of(route_graphs.zero_cost_graph())
        assert isinstance(costed, RampCost)
        assert isinstance(costed.round_trip, ExitCostUnknown)
        # And it is not the one-way record wearing a different label: the object in the slot
        # carries no figure at all, so there is nothing for a reader to mistake for a cost.
        assert not dict(_money_paths(costed.round_trip))

    def test_the_recommendation_carries_both_labels_and_neither_stands_in_for_the_other(
        self,
    ) -> None:
        # As above, the "neither is the other" half is a static fact and comparing the two
        # types is a mypy ``comparison-overlap`` error, so what is left to assert at runtime
        # is that both labelled figures are present and that they are different numbers.
        recommended = recommended_cost(_ranked())
        assert isinstance(recommended.one_way, OneWayCost)
        assert isinstance(recommended.round_trip, RoundTripCost)
        assert recommended.round_trip.fraction >= recommended.one_way.fraction
