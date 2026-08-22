"""A new provider, venue, channel and corridor -- in data only. **SC-010**, and G5 and F5.

*"A new provider, venue and corridor are added and ranked with **zero** lines of source code
changed"* (SC-010). This is the executable form of constitution Principle II for the ramp:
*adding an instrument, a venue, a route, a tax regime or a jurisdiction must be a data-only
change; if it requires an engine edit, the abstraction is wrong.* It is a compliance test for
the constitution and may not be skipped or deleted without an amendment.

**How "zero lines of source code" is actually proved**, since a claim like that is easy to
assert and easy to fake. Four checks, none a matter of opinion:

1. A scratch data root gains a venue, a channel, a provider and a corridor **in files**, and
   the new corridor is costed and ranked beside the shipped ones.
2. **No module in ``src/`` names a route, venue, channel or pool id.** A branch on an id is
   the Principle II violation this design exists to prevent, and it is greppable.
3. The **four plugin interfaces are still four**: a leg kind is an entry in a mapping of
   functions, not a fifth interface. If ``LEG_COST_FNS`` had grown an ops record or a
   protocol, adding a leg kind would have become an amendment to the constitution.
4. The records the **loader** builds behave identically to the records the tests build **by
   hand** -- asserted on every amount as ``float.hex()``, so it is bit-identity and not
   agreement on a headline.

**G5 and F5 live here because they are closed by fixtures, not by code.** Two declared route
variants differing *only* in conversion count rank in the order cost implies, with the whole
difference in the conversion component (**G5**, FR-017); and two declared variants differing
*only* in the channel their conversion names cost differently, with the channel applied
visible in the attribution (**F5**, FR-011). Neither needed an engine change, which is the
point of both.
"""

from __future__ import annotations

import ast
import re
import shutil
from datetime import date
from pathlib import Path

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.staleness import ObservationKind
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.ramp import (
    CostComponent,
    RampCost,
    Ranking,
    RoundTripCost,
    recommended_cost,
)
from terezy.core.routes import legs, ranking
from terezy.core.routes.channels import ChannelSide, FxChannel
from terezy.core.routes.legs import Leg, Route
from terezy.core.routes.path import FundingPath
from terezy.core.streams.streams import IncomeStream, Indexation
from terezy.data.declarations import resolver

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
SOURCE_ROOT = REPO_ROOT / "src" / "terezy"
CORE_ROOT = SOURCE_ROOT / "core"

ON_DATE = date(2026, 8, 22)
"""When the money moves. Data, never a clock -- the core has none and may not acquire one."""

AS_OF = date(2026, 8, 22)
"""When staleness is judged. Deliberately the same day the fixtures were retrieved, so no
figure here is stale and the ranking is about cost rather than about age."""

AMOUNT = 10_000.0
"""Ten thousand hryvnia, the amount §4.3.1's own arithmetic uses."""

# The shipped corridors, hand-computed against a reference of 42 with a +3 buy premium and a
# -2.5 sell premium, all fees zero. Every figure below is checked in so a reader can verify
# the engine rather than trust it.
#
#   p2p, one conversion in:   10 000 / 45          = 222.222222 USD
#     the spread cost:        10 000 x 3/45        =   666.666667 UAH   (= 1/15 of the amount)
#   p2p, back out at 39.5:    222.222222 x 39.5    = 8 777.777778 UAH
#     the spread cost:        222.222222 x 2.5/42 x 42 = 555.555556 UAH
#   round trip:               (666.666667 + 555.555556) / 10 000 = 12.2222%
#
#   card, one conversion in:  42 x 150bps          = 0.63, so the rate is 42.63
#     the spread cost:        10 000 x 0.63/42.63  =   147.783251 UAH   (1.4778%)
#   card in, p2p out:         (147.783251 + 586.441473) / 10 000        =  7.3422%
#
#   double, three conversions: 666.666667 + 555.555556 + 585.185185     = 1 807.407407 (18.07%)
#     with the p2p exit:      + 487.654321                              = 2 295.061728 (22.95%)
P2P_ONE_WAY = 1.0 / 15.0
P2P_ROUND_TRIP = 0.12222222222222222
CARD_ONE_WAY = 0.63 / 42.63
CARD_ROUND_TRIP = 0.07342247243725088
DOUBLE_ONE_WAY = 0.18074074074074073
DOUBLE_ROUND_TRIP = 0.22950617283950614


def _declarations(root: Path = DATA_ROOT) -> resolver.RampDeclarations:
    """Every ramp declaration under a root. The whole point is that this is all it takes."""
    return resolver.ramp_from_data_root(root, base_currency=Currency.UAH)


def _rank(
    declarations: resolver.RampDeclarations,
    *,
    stream_id: str = "salary_uah",
    origin: str = "monobank_uah",
    amount: float = AMOUNT,
    currency: Currency = Currency.UAH,
) -> Ranking:
    """Rank every declared inbound route that starts where the named stream lands.

    One ranking is one stream currency, which is not a limitation to work around: comparing
    hryvnia through one corridor against dollars through another needs a *valuation*, and
    burying one inside ``rank`` would leave a rate implicit in a comparison (research.md
    D14).
    """
    paths = [
        FundingPath(destination_id=route.destination, stream_id=stream_id, route_id=route_id)
        for route_id, route in sorted(declarations.routes.items())
        if route.direction == "inbound" and route.origin == origin
    ]
    outcome = ranking.rank(
        paths,
        Money(amount, currency, prov.EMPTY),
        routes=declarations.routes,
        channels=declarations.channels,
        streams=declarations.streams,
        kinds=declarations.kinds,
        on_date=ON_DATE,
        as_of=AS_OF,
    )
    assert isinstance(outcome, Ranking), f"nothing was comparable: {outcome}"
    return outcome


def _costed(ranked: Ranking, route_id: str) -> RampCost:
    """One route's cost out of a ranking, by id."""
    found = [cost for cost in ranked.costed if cost.path.route_id == route_id]
    assert len(found) == 1, f"{route_id} appears {len(found)} times in the ranking"
    return found[0]


def _round_trip(cost: RampCost) -> RoundTripCost:
    """The round-trip figure, or a failure saying the exit was never costed.

    Narrowed rather than assumed: ``round_trip`` is ``RoundTripCost | ExitCostUnknown`` by
    design, and a test that reached into it without narrowing would be doing what FR-030
    forbids the engine from doing.
    """
    assert isinstance(cost.round_trip, RoundTripCost), cost.round_trip
    return cost.round_trip


def _order(ranked: Ranking) -> list[str]:
    return [cost.path.route_id for cost in ranked.costed]


class TestTheShippedCorridorsRankAsHandComputed:
    """The baseline: the declared routes produce the arithmetic checked in above."""

    def test_the_ranking_is_cheapest_first_and_the_recommendation_is_one_of_them(self) -> None:
        ranked = _rank(_declarations())
        assert _order(ranked) == [
            "inzhur_direct",
            "monobank_to_binance_card",
            "monobank_to_binance_p2p",
            "monobank_to_binance_p2p_double",
        ]
        assert ranked.recommended == 0
        assert recommended_cost(ranked) is ranked.costed[ranked.recommended], (
            "the winner is not compared against the alternatives -- it is one of them "
            "(SC-016), and identity is what says so"
        )
        assert ranked.ties == (), "no two of these four cost the same"

    def test_the_domestic_route_costs_exactly_zero(self) -> None:
        """SC-004's bar, from the file rather than from a fixture built in code."""
        cost = _costed(_rank(_declarations()), "inzhur_direct")
        assert cost.one_way.fraction == 0.0
        assert cost.one_way.arrived.amount == AMOUNT
        assert _round_trip(cost).fraction == 0.0
        assert _round_trip(cost).arrived.amount == AMOUNT

    def test_each_corridor_reproduces_its_hand_computed_fraction(self) -> None:
        ranked = _rank(_declarations())
        for route_id, one_way, round_trip in (
            ("monobank_to_binance_p2p", P2P_ONE_WAY, P2P_ROUND_TRIP),
            ("monobank_to_binance_card", CARD_ONE_WAY, CARD_ROUND_TRIP),
            ("monobank_to_binance_p2p_double", DOUBLE_ONE_WAY, DOUBLE_ROUND_TRIP),
        ):
            cost = _costed(ranked, route_id)
            assert is_close(cost.one_way.fraction, one_way), route_id
            assert is_close(_round_trip(cost).fraction, round_trip), route_id

    def test_a_route_with_no_declared_exit_is_costed_and_kept_out_of_the_ranking(self) -> None:
        """FR-030 from the file: ``coinbase_to_ibkr`` declares no partner, so no round trip.

        Funded from the dollar stream, which is also the other half of §4.2's finding: money
        that arrives in dollars needs no conversion, so the conversion component is exactly
        zero rather than a small residual (FR-009).
        """
        declarations = _declarations()
        ranked = ranking.rank(
            [
                FundingPath(
                    destination_id="ibkr_usd",
                    stream_id="contract_usd",
                    route_id="coinbase_to_ibkr",
                )
            ],
            Money(1_000.0, Currency.USD, prov.EMPTY),
            routes=declarations.routes,
            channels=declarations.channels,
            streams=declarations.streams,
            kinds=declarations.kinds,
            on_date=ON_DATE,
            as_of=AS_OF,
        )
        assert not isinstance(ranked, Ranking), (
            "the only candidate has no declared exit, so there is nothing comparable to rank "
            "-- and the type says so rather than an index standing in for it"
        )
        assert [cost.path.route_id for cost in ranked.not_comparable] == ["coinbase_to_ibkr"]
        assert "exit" in ranked.reason
        one_way = ranked.not_comparable[0].one_way
        # 1 000 USD, 0.5% plus a flat 25: 5.00 + 25.00 = 30.00, and nothing converted.
        assert one_way.components[CostComponent.PERCENTAGE_FEE].amount == 5.0
        assert one_way.components[CostComponent.FIXED_FEE].amount == 25.0
        assert one_way.components[CostComponent.CONVERSION_SPREAD].amount == 0.0
        assert one_way.arrived.amount == 970.0
        assert one_way.channels_applied == ()


class TestTwoVariantsDifferingOnlyInConversionCount:
    """**G5** and FR-017, closed by two declared files and no engine change.

    ``monobank_to_binance_p2p_double.toml`` is ``monobank_to_binance_p2p.toml`` with two extra
    ``fx`` legs and nothing else changed: same provider, same endpoints, same channel, same
    zero fees, same rail, same cap. So the cost difference can only be the conversions, and
    that is asserted rather than assumed.
    """

    def test_the_single_conversion_variant_ranks_ahead_of_the_triple(self) -> None:
        order = _order(_rank(_declarations()))
        assert order.index("monobank_to_binance_p2p") < order.index(
            "monobank_to_binance_p2p_double"
        )

    def test_the_two_variants_differ_only_in_their_legs(self) -> None:
        """The premise of the whole comparison, checked against the files themselves."""
        routes = _declarations().routes
        single = routes["monobank_to_binance_p2p"]
        double = routes["monobank_to_binance_p2p_double"]
        assert (single.provider, single.origin, single.destination, single.status) == (
            double.provider,
            double.origin,
            double.destination,
            double.status,
        )
        assert single.partner_route == double.partner_route
        assert {leg.channel for leg in single.legs} == {leg.channel for leg in double.legs}
        assert len([leg for leg in single.legs if leg.kind == legs.FX]) == 1
        assert len([leg for leg in double.legs if leg.kind == legs.FX]) == 3

    def test_the_whole_difference_is_the_conversion_component(self) -> None:
        ranked = _rank(_declarations())
        single = _round_trip(_costed(ranked, "monobank_to_binance_p2p"))
        double = _round_trip(_costed(ranked, "monobank_to_binance_p2p_double"))
        for figure in (single, double):
            assert figure.components[CostComponent.PERCENTAGE_FEE].amount == 0.0
            assert figure.components[CostComponent.FIXED_FEE].amount == 0.0
        # 2 295.061728 - 1 222.222222 = 1 072.839506 UAH, which is 10.728395% of 10 000 and
        # is exactly the two extra crossings: 555.555556 + 585.185185 - 67.901234 of the
        # cheaper exit base. Asserted as the difference of the two totals rather than
        # re-derived, so the claim is "the gap is the conversions" and not "our arithmetic
        # agrees with itself".
        gap = (
            double.components[CostComponent.CONVERSION_SPREAD].amount
            - single.components[CostComponent.CONVERSION_SPREAD].amount
        )
        assert is_close(gap, (double.fraction - single.fraction) * AMOUNT)
        assert is_close(double.fraction - single.fraction, 0.10728395061728392)

    def test_the_extra_conversions_are_visible_as_extra_channel_applications(self) -> None:
        ranked = _rank(_declarations())
        assert _round_trip(_costed(ranked, "monobank_to_binance_p2p")).channels_applied == (
            "p2p",
            "p2p",
        )
        assert _round_trip(_costed(ranked, "monobank_to_binance_p2p_double")).channels_applied == (
            "p2p",
            "p2p",
            "p2p",
            "p2p",
        )


class TestTheChannelChoiceChangesTheResultAndIsVisible:
    """**F5**, closed by one field in one file: the channel a leg names.

    ``monobank_to_binance_card.toml`` differs from ``monobank_to_binance_p2p.toml`` in its
    ``channel`` and its ``provider``, and nothing else. The cost differs by the difference
    between a 150 bps card markup and a +3 UAH P2P premium, and each result names the channel
    it took -- which is what FR-011 asks for and what makes the choice arguable.
    """

    def test_the_two_variants_differ_only_in_the_channel_and_the_provider(self) -> None:
        routes = _declarations().routes
        card = routes["monobank_to_binance_card"]
        p2p = routes["monobank_to_binance_p2p"]
        assert (card.origin, card.destination, card.partner_route, card.status) == (
            p2p.origin,
            p2p.destination,
            p2p.partner_route,
            p2p.status,
        )
        assert [(leg.kind, leg.from_ccy, leg.to_ccy, leg.fee_pct) for leg in card.legs] == [
            (leg.kind, leg.from_ccy, leg.to_ccy, leg.fee_pct) for leg in p2p.legs
        ]
        assert card.legs[0].channel == "card"
        assert p2p.legs[0].channel == "p2p"

    def test_the_card_channel_is_cheaper_and_the_ranking_says_so(self) -> None:
        ranked = _rank(_declarations())
        order = _order(ranked)
        assert order.index("monobank_to_binance_card") < order.index("monobank_to_binance_p2p")
        card = _round_trip(_costed(ranked, "monobank_to_binance_card"))
        p2p = _round_trip(_costed(ranked, "monobank_to_binance_p2p"))
        assert is_close(card.fraction, CARD_ROUND_TRIP)
        assert is_close(p2p.fraction, P2P_ROUND_TRIP)
        assert card.fraction < p2p.fraction

    def test_the_channel_applied_is_in_the_attribution_on_both_sides(self) -> None:
        ranked = _rank(_declarations())
        card = _costed(ranked, "monobank_to_binance_card")
        assert card.one_way.channels_applied == ("card",)
        assert _round_trip(card).channels_applied == ("card", "p2p"), (
            "the way in and the way out are separate declarations and may take different "
            "channels; the round trip names both, in order"
        )

    def test_no_mid_rate_is_ever_reported_as_the_transacted_rate(self) -> None:
        """The other half of F5: the reference is quoted beside the cost, never as it.

        ``spread_over_reference`` is §4.3.1's rate-space figure (``3/42 = 7.14%``); the cost
        is ``3/45 = 6.67%``. Both present, each labelled, neither standing in for the other.
        """
        cost = _costed(_rank(_declarations()), "monobank_to_binance_p2p")
        assert cost.one_way.spreads_over_reference == (3.0 / 42.0,)
        assert is_close(cost.one_way.fraction, 3.0 / 45.0)
        assert cost.one_way.fraction != cost.one_way.spreads_over_reference[0]


class TestANewCorridorIsDataOnly:
    """**SC-010**: a new provider, venue, channel and corridor, ranked, with no engine edit.

    Written to a scratch data root this repository has never seen, on the precedent of feature
    001's third issue: nothing in ``src`` changes, nothing is registered, and no shipped
    fixture is edited.
    """

    def test_the_new_corridor_is_costed_and_ranked(self, tmp_path: Path) -> None:
        root = _new_corridor(tmp_path)
        declarations = _declarations(root)
        assert "transfergo_usd" in declarations.venues
        assert "bank_non_cash" in declarations.channels
        assert declarations.routes["monobank_to_transfergo"].provider == "TransferGo"

        ranked = _rank(declarations)
        assert "monobank_to_transfergo" in _order(ranked), (
            "a corridor added in data only must appear in the comparison, not merely load"
        )
        cost = _costed(ranked, "monobank_to_transfergo")
        # 50 bps in and 50 bps out, on a reference of 42: the rate in is 42.21 and the cost
        # is 0.21/42.21 = 0.497512%; the rate out is 41.79 and its cost is 0.21/42 = 0.5%,
        # taken on what arrived. Both figures come from the declared channel, and the whole
        # of the route's cost is conversion because both fees are declared zero.
        assert is_close(cost.one_way.fraction, 0.21 / 42.21)
        assert cost.one_way.channels_applied == ("bank_non_cash",)
        assert _round_trip(cost).channels_applied == ("bank_non_cash", "bank_non_cash")
        assert cost.one_way.components[CostComponent.PERCENTAGE_FEE].amount == 0.0

    def test_the_new_corridor_ranks_where_its_cost_puts_it(self, tmp_path: Path) -> None:
        """A narrower spread than either shipped conversion, so it ranks above both."""
        order = _order(_rank(_declarations(_new_corridor(tmp_path))))
        assert order.index("monobank_to_transfergo") < order.index("monobank_to_binance_card")
        assert order[0] == "inzhur_direct", "the zero-cost domestic route is still the floor"

    def test_the_new_venue_is_enforced_like_every_other(self, tmp_path: Path) -> None:
        """Data-only does not mean unchecked: the new venue's currency set is enforced too."""
        root = _new_corridor(tmp_path)
        path = root / "venues.toml"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                'id         = "transfergo_usd"\nname       = "TransferGo balance (TEST FIXTURE)"\n'
                'currencies = ["USD"]',
                'id         = "transfergo_usd"\nname       = "TransferGo balance (TEST FIXTURE)"\n'
                'currencies = ["UAH"]',
            ),
            encoding="utf-8",
        )
        with pytest.raises(Exception, match="USD"):
            _declarations(root)


class TestNoSourceCodeKnowsAboutARouteOrAVenue:
    """The greppable half of SC-010, and the honest one.

    "Zero lines of source code changed" is a claim about the *engine*, and the way it fails is
    a branch on an id. That is detectable, so it is detected here rather than asserted in a
    commit message.
    """

    IDS = (
        "monobank_to_binance_p2p",
        "binance_p2p_to_monobank",
        "inzhur_direct",
        "coinbase_to_ibkr",
        "monobank_card_uah_usd",
        "monobank_uah",
        "binance",
        "inzhur",
        "ibkr_usd",
        "salary_uah",
        "contract_usd",
        "p2p_premium",
        "bond_terms",
    )

    def test_no_module_mentions_a_declared_id(self) -> None:
        found = {
            str(path.relative_to(SOURCE_ROOT)): [
                identifier
                for identifier in self.IDS
                # Word boundaries, so a function named ``_bond_terms`` is not mistaken for
                # the observation kind ``bond_terms``: what the scan is looking for is an id
                # used as a value, and a helper whose name happens to contain one is not a
                # branch on it.
                if re.search(rf"\b{re.escape(identifier)}\b", _executable_source(path))
            ]
            for path in sorted(SOURCE_ROOT.rglob("*.py"))
        }
        offenders = {path: ids for path, ids in found.items() if ids}
        assert not offenders, (
            "a module names a specific route, venue, pool, stream or observation kind, so "
            f"that thing's behaviour is code rather than data (Principle II): {offenders}"
        )

    def test_the_scan_would_catch_a_branch_on_an_id(self) -> None:
        """A scan that can never fail protects nothing, so prove it can.

        Also proves the docstring stripping does not throw away real code: a string
        *compared against* survives, while a string that only describes survives nowhere --
        which matters here, because half the docstrings in this feature quote a route id.
        """
        assert "inzhur_direct" in _strip_prose(
            '''
"""A docstring mentioning nothing."""
def f(route: object) -> bool:
    return route.id == "inzhur_direct"
'''
        )
        assert "inzhur_direct" not in _strip_prose(
            '''
"""A module docstring about inzhur_direct, which is prose and not behaviour."""
X: int = 1
"""An attribute docstring about inzhur_direct."""
# A comment about inzhur_direct.
'''
        )


class TestTheFourPluginInterfacesAreStillFour:
    """A leg kind is an entry in a mapping of functions, not a fifth interface.

    Principle II permits exactly four -- ``Instrument``, ``Provider``, ``TaxRule``,
    ``ReturnModel`` -- and adding a fifth requires an amendment to the constitution rather
    than a pull request. This feature adds four new kinds of thing (routes, legs, channels,
    streams) and must add none.
    """

    def test_the_core_declares_no_interface_module_beyond_the_two_that_exist(self) -> None:
        modules = {str(path.relative_to(CORE_ROOT)) for path in CORE_ROOT.rglob("interface.py")}
        assert modules == {"instruments/interface.py", "tax/interface.py"}, (
            "two of the four permitted interfaces are implemented; a third file named "
            "interface.py in the core would be a new plugin seam, and the two unimplemented "
            "names are Provider and ReturnModel, whose seams are named in research.md D1"
        )

    def test_no_ops_record_or_protocol_lives_in_the_new_packages(self) -> None:
        for package in ("routes", "streams", "scenarios"):
            for path in sorted((CORE_ROOT / package).rglob("*.py")):
                source = _executable_source(path)
                assert "Ops" not in source, path
                assert "Protocol" not in source, path

    def test_a_leg_kind_is_a_function_in_a_mapping(self) -> None:
        assert set(legs.LEG_COST_FNS) == {"transfer", "fx", "trade", "withdrawal"}
        for kind, fn in legs.LEG_COST_FNS.items():
            assert callable(fn), kind
            assert not hasattr(fn, "__dataclass_fields__"), (
                f"{kind} dispatches through a record rather than a function, which is a "
                "plugin interface wearing a registry's clothes"
            )

    def test_adding_a_leg_that_uses_a_kind_needs_no_code(self) -> None:
        """The boundary, stated as a fact about the shipped data.

        Four kinds in code; thirteen legs across seven files in data, every one of them
        selecting a kind by name. Adding the fourteenth is a line in a file.
        """
        declared = [leg for route in _declarations().routes.values() for leg in route.legs]
        assert len(declared) == 13
        assert {leg.kind for leg in declared} <= set(legs.LEG_COST_FNS)


class TestTheLoaderAndTheHandBuiltRecordsAgree:
    """The loader's records behave **identically** to the ones a test builds by hand.

    The half SC-010 does not state and the whole design depends on. Every other test in this
    feature builds its inputs in code, so without this the loader could be quietly wrong --
    a premium read with the sign flipped, a fee divided twice -- and nothing would see it.

    **Asserted as bit-identity, not as agreement.** Every amount is compared as
    ``float.hex()``, which is exact and round-trippable, so a difference of one representable
    step fails. That is deliberately stricter than the project tolerance: the two paths are
    doing the *same* arithmetic on the *same* declared numbers, so anything but bit-identity
    means one of them read the file differently.
    """

    def test_the_costed_figures_are_bit_identical(self) -> None:
        declarations = _declarations()
        loaded = _costed(_rank(declarations), "monobank_to_binance_p2p")
        by_hand = _hand_built_cost()
        assert _numbers(loaded) == _numbers(by_hand)

    def test_the_hand_built_records_would_notice_a_wrong_premium(self) -> None:
        """A comparison that cannot fail proves nothing, so show what it catches."""
        assert _numbers(_hand_built_cost()) != _numbers(_hand_built_cost(buy_premium=3.5))

    def test_both_paths_carry_the_unverified_mark(self) -> None:
        """Bit-identity of the amounts, and the same epistemic status on both sides.

        The source *ids* differ -- one names a file and a table, the other names a fixture --
        and that is correct. What must not differ is whether the figure admits it rests on
        something nobody has verified.
        """
        loaded = _costed(_rank(_declarations()), "monobank_to_binance_p2p")
        assert prov.is_unverified(loaded.one_way.provenance)
        assert prov.is_unverified(_hand_built_cost().one_way.provenance)
        assert {ref.id for ref in loaded.one_way.provenance.sources} == {
            "routes/monobank_to_binance_p2p.toml#route.leg[0]",
            "routes/monobank_to_binance_p2p.toml#route.leg[1]",
            "channels/uah_usd.toml#channel[p2p]",
            "channels/uah_usd.toml#channel[p2p].buy_side",
            "channels/uah_usd.toml#channel[p2p].sell_side",
        }


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def _is_prose(node: ast.stmt) -> bool:
    """Whether a statement is a docstring -- an expression whose value is a bare string."""
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)


def _strip_prose(source: str) -> str:
    """Source with comments and docstrings removed, so a scan sees only behaviour.

    Prose naming a route is not a Principle II violation: this feature's docstrings quote
    ``monobank_to_binance_p2p`` repeatedly, and the loader's own examples name real files.
    What would be a violation is a comparison, a lookup or a branch, and those survive this
    stripping while prose does not. The same helper, for the same reason, as feature 001's.
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list) and any(isinstance(item, ast.stmt) for item in block):
                kept = [item for item in block if not _is_prose(item)]
                setattr(node, field, kept or [ast.Pass()])
    return ast.unparse(tree)


def _executable_source(path: Path) -> str:
    return _strip_prose(path.read_text(encoding="utf-8"))


def _numbers(cost: RampCost) -> tuple[str, ...]:
    """Every figure in a costed route, as exact hexadecimal floats plus its labels.

    Provenance and staleness ids are excluded on purpose: they *should* differ between a
    file-loaded record and a hand-built one, since they name where each came from. What must
    not differ is a single amount.
    """
    rendered: list[str] = [
        cost.path.route_id,
        cost.status,
        str(cost.latency_days),
        cost.disruption_probability.hex(),
        "none"
        if cost.ceiling is None
        else f"{cost.ceiling.amount.hex()} {cost.ceiling.currency.value}",
    ]
    for label, figure in (("one_way", cost.one_way), ("round_trip", _round_trip(cost))):
        rendered.extend(
            [
                label,
                f"{figure.sent.amount.hex()} {figure.sent.currency.value}",
                f"{figure.arrived.amount.hex()} {figure.arrived.currency.value}",
                figure.fraction.hex(),
                *(
                    f"{component.value}={figure.components[component].amount.hex()}"
                    for component in CostComponent
                ),
                *(spread.hex() for spread in figure.spreads_over_reference),
                *figure.channels_applied,
            ]
        )
    return tuple(rendered)


def _new_corridor(tmp_path: Path) -> Path:
    """A scratch data root with a new venue, channel, provider and corridor -- files only.

    A copy of the shipped tree plus four writes. Nothing here touches ``src``, and the shipped
    files are left exactly as they are so a failure cannot be blamed on an edit to them.
    """
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)

    venues = root / "venues.toml"
    venues.write_text(
        venues.read_text(encoding="utf-8") + '\n[[venue]]\nid         = "transfergo_usd"\n'
        'name       = "TransferGo balance (TEST FIXTURE)"\ncurrencies = ["USD"]\n',
        encoding="utf-8",
    )

    (root / "channels" / "uah_usd_bank.toml").write_text(
        """# TEST FIXTURE — a third channel for the same pair, invented for a data-only test.
[[channel]]
id             = "bank_non_cash"
pair           = ["UAH", "USD"]
reference_rate = 42.0
observed_on    = "2026-08-22"
kind           = "bank_fee_schedule"
source         = "TEST FIXTURE — invented non-cash bank rate."
retrieved_on   = "2026-08-22"
verified_on    = ""

  [channel.buy_side]
  markup_bps   = 50.0
  kind         = "bank_fee_schedule"
  source       = "TEST FIXTURE — invented."
  retrieved_on = "2026-08-22"
  verified_on  = ""

  [channel.sell_side]
  markup_bps   = 50.0
  kind         = "bank_fee_schedule"
  source       = "TEST FIXTURE — invented."
  retrieved_on = "2026-08-22"
  verified_on  = ""
""",
        encoding="utf-8",
    )

    (root / "routes" / "monobank_to_transfergo.toml").write_text(
        """# TEST FIXTURE — a new provider and a new corridor, added in data only.
[route]
id            = "monobank_to_transfergo"
provider      = "TransferGo"
origin        = "monobank_uah"
destination   = "transfergo_usd"
direction     = "inbound"
partner_route = "transfergo_to_monobank"
status        = "open"

  [[route.leg]]
  index                  = 0
  kind                   = "fx"
  from_venue             = "monobank_uah"
  to_venue               = "monobank_uah"
  from_ccy               = "UAH"
  to_ccy                 = "USD"
  channel                = "bank_non_cash"
  fee_pct                = 0.0
  fee_fixed              = 0.0
  latency_days           = 0
  disruption_probability = 0.01
  kind_of_observation    = "bank_fee_schedule"
  source                 = "TEST FIXTURE — invented."
  retrieved_on           = "2026-08-22"
  verified_on            = ""

  [[route.leg]]
  index                  = 1
  kind                   = "transfer"
  from_venue             = "monobank_uah"
  to_venue               = "transfergo_usd"
  from_ccy               = "USD"
  to_ccy                 = "USD"
  fee_pct                = 0.0
  fee_fixed              = 0.0
  latency_days           = 1
  disruption_probability = 0.01
  kind_of_observation    = "bank_fee_schedule"
  source                 = "TEST FIXTURE — invented."
  retrieved_on           = "2026-08-22"
  verified_on            = ""
""",
        encoding="utf-8",
    )

    (root / "routes" / "transfergo_to_monobank.toml").write_text(
        """# TEST FIXTURE — the way back out of the new corridor, declared in its own file.
[route]
id          = "transfergo_to_monobank"
provider    = "TransferGo"
origin      = "transfergo_usd"
destination = "monobank_uah"
direction   = "exit"
status      = "open"

  [[route.leg]]
  index                  = 0
  kind                   = "transfer"
  from_venue             = "transfergo_usd"
  to_venue               = "monobank_uah"
  from_ccy               = "USD"
  to_ccy                 = "USD"
  fee_pct                = 0.0
  fee_fixed              = 0.0
  latency_days           = 1
  disruption_probability = 0.01
  kind_of_observation    = "bank_fee_schedule"
  source                 = "TEST FIXTURE — invented."
  retrieved_on           = "2026-08-22"
  verified_on            = ""

  [[route.leg]]
  index                  = 1
  kind                   = "fx"
  from_venue             = "monobank_uah"
  to_venue               = "monobank_uah"
  from_ccy               = "USD"
  to_ccy                 = "UAH"
  channel                = "bank_non_cash"
  fee_pct                = 0.0
  fee_fixed              = 0.0
  latency_days           = 0
  disruption_probability = 0.01
  kind_of_observation    = "bank_fee_schedule"
  source                 = "TEST FIXTURE — invented."
  retrieved_on           = "2026-08-22"
  verified_on            = ""
""",
        encoding="utf-8",
    )
    return root


FIXTURE_SOURCE = prov.of(
    [
        prov.SourceRef(
            id="hand-built#monobank_to_binance_p2p",
            citation="TEST FIXTURE — the same declared numbers, entered in code.",
            retrieved_on=date(2026, 8, 22),
            verified_on=None,
        )
    ]
)
"""One citation for every hand-built number, unverified like the file it mirrors."""


def _hand_built_cost(*, buy_premium: float = 3.0) -> RampCost:
    """The P2P corridor, built in code from the same declared numbers.

    Written out rather than derived from the loaded records, which would make the comparison
    circular. ``buy_premium`` is a parameter for one reason: to prove the comparison notices
    when a number differs.
    """
    channel = FxChannel(
        id="p2p",
        pair=(Currency.UAH, Currency.USD),
        reference_rate=42.0,
        buy_side=ChannelSide(
            markup_bps=None,
            premium_per_unit=Money(buy_premium, Currency.UAH, FIXTURE_SOURCE),
        ),
        sell_side=ChannelSide(
            markup_bps=None, premium_per_unit=Money(-2.5, Currency.UAH, FIXTURE_SOURCE)
        ),
        observed_on=date(2026, 8, 22),
        kind="p2p_premium",
        provenance=FIXTURE_SOURCE,
    )

    def _leg(
        index: int,
        kind: str,
        from_venue: str,
        to_venue: str,
        *,
        from_ccy: Currency,
        to_ccy: Currency,
        channel_id: str | None = None,
        latency_days: int = 0,
        disruption: float,
        pool: str | None = None,
        cap: float | None = None,
    ) -> Leg:
        return Leg(
            index=index,
            kind=kind,
            from_venue=from_venue,
            to_venue=to_venue,
            from_ccy=from_ccy,
            to_ccy=to_ccy,
            channel=channel_id,
            fee_pct=0.0,
            fee_fixed=Money(0.0, from_ccy, FIXTURE_SOURCE),
            minimum=None,
            maximum=None,
            monthly_cap=None if cap is None else Money(cap, from_ccy, FIXTURE_SOURCE),
            capacity_pool=pool,
            latency_days=latency_days,
            available_from=None,
            available_until=None,
            disruption_probability=disruption,
            kind_of_observation="regulatory_limit" if cap is not None else "bank_fee_schedule",
            provenance=FIXTURE_SOURCE,
        )

    inbound = Route(
        id="monobank_to_binance_p2p",
        provider="Binance P2P",
        origin="monobank_uah",
        destination="binance",
        direction="inbound",
        partner_route="binance_p2p_to_monobank",
        status="open",
        legs=(
            _leg(
                0,
                legs.FX,
                "monobank_uah",
                "monobank_uah",
                from_ccy=Currency.UAH,
                to_ccy=Currency.USD,
                channel_id="p2p",
                disruption=0.05,
                pool="monobank_card_uah_usd",
                cap=100_000.0,
            ),
            _leg(
                1,
                legs.TRANSFER,
                "monobank_uah",
                "binance",
                from_ccy=Currency.USD,
                to_ccy=Currency.USD,
                disruption=0.02,
            ),
        ),
    )
    exit_route = Route(
        id="binance_p2p_to_monobank",
        provider="Binance P2P",
        origin="binance",
        destination="monobank_uah",
        direction="exit",
        partner_route=None,
        status="open",
        legs=(
            _leg(
                0,
                legs.FX,
                "binance",
                "binance",
                from_ccy=Currency.USD,
                to_ccy=Currency.UAH,
                channel_id="p2p",
                disruption=0.05,
            ),
            _leg(
                1,
                legs.TRANSFER,
                "binance",
                "monobank_uah",
                from_ccy=Currency.UAH,
                to_ccy=Currency.UAH,
                latency_days=1,
                disruption=0.02,
            ),
        ),
    )
    stream = IncomeStream(
        id="salary_uah",
        owner_id="owner-001",
        amount=Money(0.0, Currency.UAH, prov.EMPTY),
        cadence="monthly",
        arrives_at="monobank_uah",
        indexation=Indexation(policy="cpi", rate=None),
        income_tax_rate=None,
    )
    outcome = ranking.rank(
        [FundingPath(destination_id="binance", stream_id=stream.id, route_id=inbound.id)],
        Money(AMOUNT, Currency.UAH, prov.EMPTY),
        routes={inbound.id: inbound, exit_route.id: exit_route},
        channels={channel.id: channel},
        streams={stream.id: stream},
        kinds={
            "p2p_premium": ObservationKind(
                id="p2p_premium", staleness_days=7, note="TEST FIXTURE."
            ),
            "bank_fee_schedule": ObservationKind(
                id="bank_fee_schedule", staleness_days=365, note="TEST FIXTURE."
            ),
            "regulatory_limit": ObservationKind(
                id="regulatory_limit", staleness_days=180, note="TEST FIXTURE."
            ),
        },
        on_date=ON_DATE,
        as_of=AS_OF,
    )
    assert isinstance(outcome, Ranking)
    return recommended_cost(outcome)
