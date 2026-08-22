"""FR-030 and G6: a one-way figure cannot occupy the round-trip slot.

FR-027 requires round-trip cost to come from a **separately declared exit route**, never
from reversing the inbound one -- getting money back into spendable base currency has its own
chain, its own spreads and its own limits (``SIMULATOR_SPEC.md`` §4.3.3). FR-030 is the
honest consequence: *a destination with no declared exit route therefore has no round-trip
cost, and MUST NOT be presented as comparison-ready... A one-way figure MUST NOT be silently
promoted to stand in for the missing round trip.*

**The tempting silent fix is the one this module exists to make impossible.** The one-way
figure is "most of" the cost and it is right there. Promoting it would produce a confident
round-trip number for an exit path nobody has ever looked at -- and Principle VI holds that
an asset which cannot be liquidated into spendable base currency at a reasonable cost is not
worth its stated value. "We never checked how to get out" is exactly that case.

**The mechanism is two unrelated types**, following the precedent ``RealRate |
RealTermsUnavailable`` set in feature 001 -- which has already earned its keep. ``OneWayCost``
and ``RoundTripCost`` share no base class and no protocol, so::

    RampCost(..., round_trip=one_way_figure, ...)   # error: incompatible type

is a **mypy strict error** at the assignment. That check cannot be written as a runtime
test -- asserting it here would mean asserting that the type checker ran -- so it lives in
the ``mypy`` gate, and this module's job is the second line of defence: the runtime shape,
and the structural facts that make the type separation real rather than nominal.

The two records are field-for-field similar on purpose (both carry ``sent``, ``arrived``,
``components``, ``fraction``), which is exactly why a naming convention would not have been
enough: nothing about either record's *contents* would stop a mix-up. Only their identities
do.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import pkgutil
from collections.abc import Iterator
from typing import Any, get_args, get_type_hints

import pytest

import terezy.core.results
import terezy.core.routes
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.ramp import (
    CostComponent,
    ExitCostUnknown,
    OneWayCost,
    RampCost,
    RoundTripCost,
    RouteUnusable,
)
from terezy.core.routes import cost
from tests.invariants import route_graphs


class TestTheTwoCostTypesAreUnrelated:
    """No shared base, no protocol, no subclass relation. That is the whole guard."""

    @pytest.mark.parametrize("record", [OneWayCost, RoundTripCost, ExitCostUnknown])
    def test_each_inherits_from_nothing(self, record: type) -> None:
        # A shared base is how a missing case silently acquires a default, and here it
        # would let a one-way figure satisfy a round-trip annotation.
        assert record.__bases__ == (object,)

    def test_neither_is_a_subclass_of_the_other(self) -> None:
        assert not issubclass(OneWayCost, RoundTripCost)
        assert not issubclass(RoundTripCost, OneWayCost)

    def test_they_are_field_for_field_similar_which_is_why_the_types_must_differ(self) -> None:
        # Stated as an assertion rather than a comment: the two records carry the same
        # information in the same shapes, so nothing about their *contents* would catch a
        # mix-up. If a future change made them structurally different this test would fail
        # and the reasoning above would need revisiting.
        one_way = {field.name for field in dataclasses.fields(OneWayCost)}
        round_trip = {field.name for field in dataclasses.fields(RoundTripCost)}
        assert one_way == round_trip

    def test_the_round_trip_slot_admits_only_a_round_trip_or_a_stated_absence(self) -> None:
        # The annotation is the contract mypy enforces, so the annotation is asserted.
        admitted = set(get_args(get_type_hints(RampCost)["round_trip"]))
        assert admitted == {RoundTripCost, ExitCostUnknown}
        assert OneWayCost not in admitted

    def test_the_one_way_slot_is_always_present_and_is_not_a_union(self) -> None:
        # A one-way figure is always computable: it is the route that was declared. There
        # is no "one-way unknown" case, and giving the slot a union would invent one.
        assert get_type_hints(RampCost)["one_way"] is OneWayCost


class TestTheMissingExitNamesItself:
    """FR-017: a degraded outcome carries its reason, and the reason reaches the output."""

    def test_exit_cost_unknown_names_the_route_whose_partner_is_missing(self) -> None:
        unknown = ExitCostUnknown(
            reason=(
                "route monobank_to_binance_p2p declares no partner_route, so nobody has "
                "costed the way out"
            ),
            missing_partner_for="monobank_to_binance_p2p",
        )
        assert unknown.missing_partner_for == "monobank_to_binance_p2p"
        assert "monobank_to_binance_p2p" in unknown.reason

    def test_it_carries_no_number_at_all(self) -> None:
        # The point of the record: there is nothing to report, so it reports nothing --
        # rather than a zero, which would read as "free to exit", the most flattering
        # possible lie about an asset nobody has costed the exit for.
        fields = {field.name for field in dataclasses.fields(ExitCostUnknown)}
        assert fields == {"reason", "missing_partner_for"}


class TestNothingCanPromoteAOneWayFigure:
    """The silent fix, closed structurally: there is no function that performs it."""

    def _modules(self) -> Iterator[Any]:
        for package in (terezy.core.routes, terezy.core.results):
            yield package
            for info in pkgutil.iter_modules(package.__path__):
                yield importlib.import_module(f"{package.__name__}.{info.name}")

    def test_no_function_in_core_turns_a_one_way_cost_into_a_round_trip_one(self) -> None:
        offenders = []
        for module in self._modules():
            for name, value in vars(module).items():
                if name.startswith("_") or inspect.isclass(value) or not callable(value):
                    continue
                if getattr(value, "__module__", None) != module.__name__:
                    continue
                signature = inspect.signature(value)
                takes_one_way = "OneWayCost" in str(signature.parameters)
                returns_round_trip = "RoundTripCost" in str(signature.return_annotation)
                if takes_one_way and returns_round_trip:
                    offenders.append(f"{module.__name__}.{name}")
        assert not offenders, (
            "these promote a one-way figure into a round-trip one, which produces a "
            "confident number for an exit nobody costed (FR-030): " + ", ".join(sorted(offenders))
        )


class TestTheComponentSetIsClosed:
    """FR-003: attribution a reader can trust means a component set nothing can extend."""

    def test_there_are_exactly_three_components_and_they_are_named(self) -> None:
        assert {member.value for member in CostComponent} == {
            "conversion_spread",
            "percentage_fee",
            "fixed_fee",
        }

    def test_the_components_mapping_is_keyed_by_the_enumeration_not_by_strings(self) -> None:
        # A ``dict[str, Money]`` would let a leg invent a component name, and the
        # components-sum-to-total invariant would then be satisfiable by a cost hiding
        # under a key nobody sums. Asserted on the annotation, because that is what
        # constrains every construction site.
        for record in (OneWayCost, RoundTripCost):
            annotation = str(get_type_hints(record)["components"])
            assert "CostComponent" in annotation
            assert "str" not in annotation

    def test_a_component_enum_member_is_not_interchangeable_with_its_name(self) -> None:
        # Deliberately not a ``str`` subclass: a string-valued enum compares equal to a
        # bare string, which would let ``"fixed_fee"`` occupy a position that should
        # require a member and defeat the point of closing the set. mypy rejects the
        # member-to-string comparison outright, which is why this asserts on the class.
        assert not issubclass(CostComponent, str)
        assert CostComponent.FIXED_FEE.value == "fixed_fee"


class TestARouteThatCannotCarryTheAmountSaysWhatBound:
    """FR-014: the binding constraint is named, with the shortfall, and never omitted."""

    def test_route_unusable_carries_the_path_the_constraint_and_the_reason(self) -> None:
        fields = {field.name for field in dataclasses.fields(RouteUnusable)}
        assert {"path", "binding_constraint", "required", "actual", "shortfall", "reason"} == fields

    def test_it_is_unrelated_to_a_cost_so_it_cannot_fill_a_cost_slot(self) -> None:
        # The same discipline as the round-trip split: an unusable route is not a cost of
        # zero, and the two must not be assignable to one another.
        assert RouteUnusable.__bases__ == (object,)
        assert not issubclass(RouteUnusable, RampCost)


class TestADanglingPartnerIsNotAMissingRoundTrip:
    """``null`` and a broken reference are different declarations and must stay different."""

    def test_a_partner_route_that_does_not_exist_raises_rather_than_reporting_unknown(
        self,
    ) -> None:
        # The distinction worth protecting: ``partner_route = null`` is the owner saying
        # "nobody has costed the way out", and it produces ``ExitCostUnknown``. A *dangling*
        # id is a broken declaration, which the resolver refuses at load (FR-027). If it
        # reached here and were reported as ``ExitCostUnknown`` too, a typo in a route file
        # would be indistinguishable from a deliberate statement about the exit -- and the
        # typo would look like an honest gap forever.
        graph = route_graphs.zero_cost_graph()
        route = dataclasses.replace(graph.route, partner_route="typo_route")
        with pytest.raises(KeyError, match="not declared"):
            cost.cost_one(
                graph.path,
                Money(1_000.0, Currency.UAH, prov.EMPTY),
                routes={route.id: route},
                channels=graph.channels,
                streams=route_graphs.STREAMS,
                kinds=route_graphs.KINDS,
                on_date=route_graphs.ON_DATE,
                as_of=route_graphs.AS_OF,
            )

    def test_a_route_declaring_no_partner_reports_exit_cost_unknown(self) -> None:
        graph = route_graphs.zero_cost_graph()
        assert graph.route.partner_route is None
        costed = cost.cost_one(
            graph.path,
            Money(1_000.0, Currency.UAH, prov.EMPTY),
            routes=graph.routes,
            channels=graph.channels,
            streams=route_graphs.STREAMS,
            kinds=route_graphs.KINDS,
            on_date=route_graphs.ON_DATE,
            as_of=route_graphs.AS_OF,
        )
        assert isinstance(costed, RampCost)
        assert isinstance(costed.round_trip, ExitCostUnknown)
        assert costed.round_trip.missing_partner_for == graph.route.id
        # And the one-way figure was not copied into its place: the record that occupies
        # the slot carries no number at all.
        assert not hasattr(costed.round_trip, "fraction")
