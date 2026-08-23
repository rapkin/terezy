"""A refusal is drawn as a refusal, and a missing exit is drawn as an absence.

**SC-010** and **SC-007**; **FR-005**, **FR-010**, **FR-011**.

Predecessor defect B10 was an empty result standing in for a failure, and the visual form of
that defect is an empty diagram. It is worse than the tabular form: an empty picture is
indistinguishable from a graph that genuinely has nothing in it, and a reader has no way to
tell "this route cannot carry your money" from "nothing was declared". So the renderer's answer
to a refusal is a typed :class:`~terezy.api.diagrams.NothingToDraw` carrying the refusal's own
reason -- **verbatim**, because the words the engine chose are the ones the owner has already
learned to read.

The other half is the destination nobody has declared a way out of. Feature 002 answers that
with ``ExitCostUnknown`` and **no round-trip figure**; this feature answers it with an
explicitly absent edge, because *a diagram in which an incomparable destination looks like a
comparable one is the mislabelled figure in picture form* (FR-005). Both halves are asserted
here: the registry graph's *no exit declared* mark, and the costed path's *exit cost unknown*.
"""

from __future__ import annotations

import inspect
import re

import pytest

from terezy.api.diagrams import Diagram, NothingToDraw, numbers, render_path
from terezy.api.diagrams import marks as diagram_marks
from terezy.api.diagrams.marks import Mark
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.ramp import (
    ExitCostUnknown,
    NothingComparable,
    RampCost,
    RouteUnusable,
)
from terezy.core.routes.path import FundingPath, Segment
from tests import diagram_registries as fixture

pytestmark = pytest.mark.contract

FIGURE = re.compile(r"-?\d+\.\d\d")

Refusal = RouteUnusable | ExitCostUnknown | NothingComparable
"""The three inputs that are not a path, each carrying its own reason."""


def a_route_unusable() -> RouteUnusable:
    """A refusal from feature 002's own costing: an amount below a declared minimum.

    Built by costing rather than by hand wherever possible; here the shipped registry has no
    leg minimum, so the record is constructed with the fields ``cost_one`` would fill and the
    reason it would write. What matters to this suite is the *shape*: a refusal carrying a
    binding constraint, the segment it bound on (004 FR-015), and a reason.
    """
    return RouteUnusable(
        path=FundingPath(
            destination_id="binance", stream_id=fixture.UAH_STREAM, route_id=fixture.P2P_ROUTE
        ),
        binding_segment=Segment(position=0, route_id=fixture.P2P_ROUTE),
        binding_constraint="leg.minimum",
        required=Money(500.0, Currency.UAH, prov.EMPTY),
        actual=Money(100.0, Currency.UAH, prov.EMPTY),
        shortfall=Money(400.0, Currency.UAH, prov.EMPTY),
        reason=(
            "leg 0 will not carry 100.00 UAH: it declares a minimum of 500.00 UAH, so the "
            "movement is 400.00 UAH short. Nothing was rounded up to reach it."
        ),
    )


def an_exit_cost_unknown() -> ExitCostUnknown:
    return ExitCostUnknown(
        reason="no exit route is declared from ibkr_usd, so no round-trip figure exists",
        missing_partner_for=fixture.NO_PARTNER_ROUTE,
    )


def nothing_comparable() -> NothingComparable:
    return NothingComparable(
        reason="every candidate lacks a declared exit route, so nothing is comparison-ready",
        excluded=(),
        not_comparable=(),
    )


class TestARefusalIsNeverDrawnAsAPath:
    """SC-010: zero fixtures produce a partial path or a silently empty diagram."""

    @pytest.mark.parametrize(
        "refusal",
        [a_route_unusable(), an_exit_cost_unknown(), nothing_comparable()],
        ids=["route-unusable", "exit-cost-unknown", "nothing-comparable"],
    )
    def test_each_refusal_yields_a_typed_nothing_to_draw(self, refusal: Refusal) -> None:
        rendered = fixture.path_of(refusal)
        assert isinstance(rendered, NothingToDraw)
        assert rendered.kind == "costed_path"

    @pytest.mark.parametrize(
        "refusal",
        [a_route_unusable(), an_exit_cost_unknown(), nothing_comparable()],
        ids=["route-unusable", "exit-cost-unknown", "nothing-comparable"],
    )
    def test_the_reason_is_carried_verbatim_and_not_reworded(self, refusal: Refusal) -> None:
        """The reason the caller needs is already in the input; rewording it loses it."""
        rendered = fixture.path_of(refusal)
        assert isinstance(rendered, NothingToDraw)
        assert rendered.reason == refusal.reason

    def test_a_refusal_is_a_different_type_from_a_diagram(self) -> None:
        """A ``Diagram`` with an ``ok`` flag is the shape this deliberately is not."""
        assert not issubclass(NothingToDraw, Diagram)
        assert not issubclass(Diagram, NothingToDraw)
        assert not hasattr(NothingToDraw, "text")

    def test_the_accepted_inputs_are_a_closed_union_with_no_fallback(self) -> None:
        """No fallback rendering: a shape nobody specified is not a path with parts missing.

        Expressed in the signature rather than as a runtime check, on the precedent of
        ``results.ramp``: the ``match`` over the union is exhaustive and mypy proves the
        default arm unreachable, so a fifth input shape is a type error at the call site
        instead of a picture with parts missing at the owner's desk.
        """
        annotation = inspect.signature(render_path).parameters["result"].annotation
        assert set(str(annotation).replace(" ", "").split("|")) == {
            "RampCost",
            "RouteUnusable",
            "ExitCostUnknown",
            "NothingComparable",
        }


class TestExitCostUnknownIsDrawnWhereTheExitWouldBe:
    """FR-010 and SC-007 on a costed path, from the one shipped route with no partner."""

    @staticmethod
    def _rendered() -> str:
        return fixture.drawn_path(fixture.exit_unknown_cost(), regime_id="normalized").text

    def test_the_result_under_test_really_has_no_declared_exit(self) -> None:
        cost = fixture.exit_unknown_cost()
        assert isinstance(cost, RampCost)
        assert isinstance(cost.round_trip, ExitCostUnknown)

    def test_the_mark_appears_in_the_place_the_exit_would_occupy(self) -> None:
        text = self._rendered()
        assert diagram_marks.token(Mark.EXIT_COST_UNKNOWN) in text
        assert fixture.exit_unknown_cost().round_trip.reason in text  # type: ignore[union-attr]

    def test_no_round_trip_figure_appears_anywhere_on_the_diagram(self) -> None:
        """ "Most of the cost" is not the cost, and a promoted one-way figure is the defect
        FR-030 exists to prevent -- here in the one place a reader would not check."""
        text = self._rendered()
        assert "round-trip cost" not in text
        assert "round-trip" in text, "the absence has to be *said*, not merely left out"

    def test_the_one_way_figure_is_still_there_because_it_is_real(self) -> None:
        """A missing exit is not a failure to cost the way in."""
        cost = fixture.exit_unknown_cost()
        assert f"one-way cost {numbers.percent(cost.one_way.fraction)}" in self._rendered()

    def test_no_exit_legs_are_drawn_because_none_are_declared(self) -> None:
        text = self._rendered()
        for line in text.splitlines():
            assert "exit · route " not in line, "an exit was drawn for a route that declares none"


class TestTheRegistryGraphDrawsTheAbsentEdgeRatherThanOmittingIt:
    """FR-005 and SC-007's first half. The same fact, one layer up from the costed result."""

    def test_a_destination_nothing_leaves_carries_the_mark_on_its_node(self) -> None:
        text = fixture.six_state_graph().text
        node = next(line for line in text.splitlines() if '["venue gamma' in line)
        assert diagram_marks.token(Mark.NO_EXIT_DECLARED) in node
        assert "not comparison-ready" in node

    def test_the_missing_exit_is_an_edge_and_not_an_omission(self) -> None:
        """ "Shown as an explicitly absent edge" -- the words FR-005 uses."""
        text = fixture.six_state_graph().text
        absent = [
            line
            for line in text.splitlines()
            if "-.->" in line and diagram_marks.token(Mark.NO_EXIT_DECLARED) in line
        ]
        assert len(absent) == 2, absent
        assert all("the absent edge, drawn rather than omitted" in line for line in absent)

    def test_a_destination_with_a_declared_exit_carries_no_such_mark(self) -> None:
        """A mark that appears on every destination would say nothing about any of them."""
        text = fixture.six_state_graph().text
        node = next(line for line in text.splitlines() if '["venue beta' in line)
        assert diagram_marks.token(Mark.NO_EXIT_DECLARED) not in node

    def test_no_figure_sits_anywhere_near_the_absent_exit(self) -> None:
        """FR-005 with FR-030: no round-trip figure exists for such a destination, so no
        figure may appear on the element that says the exit is missing either."""
        marked = [
            line
            for line in fixture.six_state_graph().text.splitlines()
            if diagram_marks.token(Mark.NO_EXIT_DECLARED) in line
        ]
        assert marked, "the fixture stopped covering the no-exit case"
        for line in marked:
            assert not FIGURE.search(line), line
