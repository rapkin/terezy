"""``cost_exit``: the way out, costed from what the instrument released rather than from a ramp.

Feature 002's round trip continues the inbound walk, which is right while nothing is bought:
the amount leaving the inbound chain is the amount entering the exit chain. Once something is
bought the two part company, and applying the round-trip *fraction* to a coupon would be a
fabricated figure that looks entirely sound -- a fixed fee does not scale.

So there is one more entry point into the one costing function, and this module holds it to the
same three rules everything else in ``routes.cost`` obeys: the arithmetic is the same fold, the
chain is anchored at **both** ends, and a constraint that binds is a typed refusal naming it.
"""

from __future__ import annotations

from typing import Final

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results.ramp import CostComponent, RouteUnusable, WayOutCost
from terezy.core.routes import cost
from terezy.core.routes.path import EXIT_BY_IDENTITY, ComposedExit, DeclaredExit
from tests import tuple_registries as fixtures

UAH: Final = fixtures.UAH
RELEASED: Final = Money(1_000.0, UAH, prov.EMPTY)
AT_INZHUR: Final = ("inzhur", "UAH")
AT_MONOBANK: Final = ("monobank_uah", "UAH")

PRICED_OUT: Final = "test_priced_out"
"""0.5% plus 25.00 flat, out of `inzhur`. Both terms non-zero so both are visible."""


def _registries() -> fixtures.Registries:
    return fixtures.with_new_route(
        fixtures.shipped(),
        fixtures.route(
            PRICED_OUT,
            origin="inzhur",
            destination="monobank_uah",
            direction="exit",
            fee_pct=0.005,
            fee_fixed=25.0,
        ),
    )


def _cost(
    chain: object,
    *,
    registries: fixtures.Registries | None = None,
    amount: Money = RELEASED,
    departing_from: tuple[str, str] = AT_INZHUR,
) -> WayOutCost | RouteUnusable:
    resolved = registries or _registries()
    return cost.cost_exit(
        chain,  # type: ignore[arg-type]
        amount,
        stream_id=fixtures.SALARY,
        departing_from=departing_from,
        routes=resolved.routes,
        channels=resolved.channels,
        kinds=resolved.kinds,
        on_date=fixtures.ISSUE_DATE,
        as_of=fixtures.AS_OF,
        spendable=resolved.spendable,
    )


def _priced(chain: object, **kwargs: object) -> WayOutCost:
    charged = _cost(chain, **kwargs)  # type: ignore[arg-type]
    assert isinstance(charged, WayOutCost), charged
    return charged


class TestTheArithmeticIsTheSameFold:
    """One costing function, entered at a different point. No new formula anywhere."""

    def test_a_thousand_out_at_half_a_percent_and_twenty_five_flat(self) -> None:
        #   percentage  1 000.00 x 0.005 =  5.00
        #   flat fee                      is 25.00
        #   arrived     1 000 - 5 - 25    = 970.00
        charged = _priced(DeclaredExit(route_id=PRICED_OUT))
        assert_money_close(charged.arrived, Money(970.0, UAH, prov.EMPTY))
        assert_money_close(
            charged.components[CostComponent.PERCENTAGE_FEE], Money(5.0, UAH, prov.EMPTY)
        )
        assert_money_close(
            charged.components[CostComponent.FIXED_FEE], Money(25.0, UAH, prov.EMPTY)
        )
        assert is_close(charged.fraction, 0.03)

    def test_the_flat_fee_does_not_scale_which_is_why_this_function_exists(self) -> None:
        #   on 1 000.00 the flat 25.00 is 2.5%; on 100 000.00 it is 0.025%.
        # One fraction cannot price both, so a round-trip percentage measured on an arriving
        # ramp amount is the wrong number for every release that is not exactly that size.
        small = _priced(DeclaredExit(route_id=PRICED_OUT))
        large = _priced(DeclaredExit(route_id=PRICED_OUT), amount=Money(100_000.0, UAH, prov.EMPTY))
        assert is_close(small.fraction, 0.005 + 25.0 / 1_000.0)
        assert is_close(large.fraction, 0.005 + 25.0 / 100_000.0)

    def test_every_component_is_present_even_where_it_charged_nothing(self) -> None:
        # A component that is zero and a component nobody costed are different claims, and an
        # absent key would read as the second while meaning the first.
        charged = _priced(DeclaredExit(route_id=fixtures.DOMESTIC_OUT))
        assert set(charged.components) == set(CostComponent)
        assert charged.fraction == 0.0

    def test_the_latency_is_on_the_figure_because_it_is_inside_the_span(self) -> None:
        # Unlike a ramp's, whose latency rides beside the cost: here the arrival date is what
        # the money-weighted return is measured against, so a slow way out has to be able to
        # lower the rate (FR-015).
        assert _priced(DeclaredExit(route_id=fixtures.DOMESTIC_OUT)).latency_days == 3


class TestItIsKeyedLikeEveryOtherCost:
    """FR-008 on the way back: the stream is part of what a cost is."""

    def test_a_single_declared_exit_is_keyed_by_the_route_and_the_stream(self) -> None:
        charged = _priced(DeclaredExit(route_id=PRICED_OUT))
        assert charged.path.stream_id == fixtures.SALARY
        assert charged.path.destination_id == "monobank_uah"

    def test_an_exit_by_identity_is_keyed_too_even_though_it_walks_nothing(self) -> None:
        # It charges nothing and takes no time, and it is still a cost of getting *this*
        # holding's proceeds home from *this* income -- so it carries the key rather than
        # becoming the one unkeyed figure in the output.
        charged = _priced(EXIT_BY_IDENTITY, departing_from=AT_MONOBANK)
        assert charged.path.stream_id == fixtures.SALARY
        assert_money_close(charged.arrived, RELEASED)
        assert charged.latency_days == 0


class TestBothEndsAreAnchored:
    """The check feature 004 shipped without, at the end where it went missing."""

    def test_a_chain_departing_from_somewhere_the_money_is_not_is_refused(self) -> None:
        # A raise rather than a refusal, on `_routes_for`'s reasoning: by the time a chain
        # reaches this function the caller has already had the chance to report the mismatch
        # as the data problem it is, so one arriving here is a construction error.
        with pytest.raises(ValueError, match="do not meet"):
            _cost(DeclaredExit(route_id=PRICED_OUT), departing_from=AT_MONOBANK)

    def test_a_chain_that_stops_short_of_a_spendable_endpoint_is_refused(self) -> None:
        registries = fixtures.with_new_route(
            _registries(),
            fixtures.route(
                "test_inzhur_to_binance",
                origin="inzhur",
                destination="binance",
                direction="exit",
            ),
        )
        with pytest.raises(ValueError, match="not a declared spendable endpoint"):
            _cost(DeclaredExit(route_id="test_inzhur_to_binance"), registries=registries)

    def test_an_exit_by_identity_asserted_where_nothing_is_spendable_is_refused(self) -> None:
        # The bare claim *there is nothing to do*, checked rather than taken on trust.
        with pytest.raises(ValueError, match="not a declared spendable endpoint"):
            _cost(EXIT_BY_IDENTITY, departing_from=AT_INZHUR)

    def test_a_composed_chain_is_walked_as_one_journey(self) -> None:
        # Two segments, one fold, continuous segment numbering -- and the second segment's
        # flat fee is charged on what the first delivered rather than on what entered it.
        registries = fixtures.with_new_route(
            _registries(),
            fixtures.route(
                "test_inzhur_to_binance",
                origin="inzhur",
                destination="binance",
                direction="exit",
                fee_fixed=10.0,
            ),
        )
        registries = fixtures.with_new_route(
            registries,
            fixtures.route(
                "test_binance_to_monobank",
                origin="binance",
                destination="monobank_uah",
                direction="exit",
                fee_fixed=10.0,
            ),
        )
        charged = _priced(
            ComposedExit(segments=("test_inzhur_to_binance", "test_binance_to_monobank")),
            registries=registries,
        )
        assert_money_close(charged.arrived, Money(980.0, UAH, prov.EMPTY))
        assert [entry.position for entry in charged.by_segment] == [0, 1]


class TestAConstraintThatBindsIsNamed:
    """002's feasibility, unchanged, on the way back."""

    def test_a_closed_exit_segment_is_a_refusal_naming_the_status(self) -> None:
        registries = fixtures.with_route(_registries(), PRICED_OUT, status="closed")
        refusal = _cost(DeclaredExit(route_id=PRICED_OUT), registries=registries)
        assert isinstance(refusal, RouteUnusable), refusal
        assert refusal.binding_constraint == "route.status"

    def test_a_release_below_the_legs_minimum_is_a_refusal_naming_the_shortfall(self) -> None:
        registries = fixtures.with_leg(
            _registries(), PRICED_OUT, minimum=Money(5_000.0, UAH, prov.EMPTY)
        )
        refusal = _cost(DeclaredExit(route_id=PRICED_OUT), registries=registries)
        assert isinstance(refusal, RouteUnusable), refusal
        assert refusal.binding_constraint == "leg.minimum"
        assert refusal.shortfall is not None
        assert_money_close(refusal.shortfall, Money(4_000.0, UAH, prov.EMPTY))

    def test_a_negative_amount_raises_rather_than_reporting_a_gain(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            _cost(
                DeclaredExit(route_id=PRICED_OUT),
                amount=Money(-1.0, UAH, prov.EMPTY),
            )
