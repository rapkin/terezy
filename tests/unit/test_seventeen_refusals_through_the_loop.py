"""SC-005: every member of 010's union, reached through the loop or proven unreachable by it.

Each planted case asserts three things at once -- one more candidate dropped, the reason
present under its own name in the tally, and **the no-candidate count unchanged**. The last is
the one worth planting for: a drop that silently moved a pair into the third column would leave
the totals looking right while the two populations a reader acts on differently had swapped.

Three members cannot be reached from *any* registry through this loop, and they are recorded
here with the property that makes each impossible rather than with a sentence saying so. All
three are seams enumeration closes by construction: it never names a stream its way in was not
costed from, never anchors a chain at a venue the instrument does not use, and never emits a
way out that stops short of somewhere spendable.

The battery checks its own coverage against ``get_args(TupleRefused)``, so an eighteenth member
fails here as well as in 010's suite.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import TYPE_CHECKING, get_args

import pytest

from terezy.core.decision.candidates import drop_tally, dropped, evaluated, survey
from terezy.core.decision.tuple_outcome import currency_of
from terezy.core.instruments.interface import DateRange
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.candidates import CandidateSet, CandidateSurvey
from terezy.core.results.tuple import TupleRefused
from terezy.core.routes import cost
from terezy.core.routes.legs import Route
from terezy.core.routes.path import (
    EXIT_BY_IDENTITY,
    ExitChain,
    exit_segments_of,
    segments_of,
)
from terezy.core.tax.schedule import RateEntry
from tests import candidate_registries as fixtures
from tests import tuple_registries as tuples

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping

    from terezy.core.decision.tuple_outcome import Registries
    from terezy.core.results.candidates import Question
    from terezy.core.results.tuple import InstrumentPlan, Tuple

BOND_CLASS = "ua_government_bond"
OVDP = "ovdp_synthetic_a"
MILTECH = "inzhur_miltech"
REIT = "inzhur_reit"
UNCHANGED_NO_CANDIDATES = 9
"""What the shipped registry puts in the third column, asserted rather than assumed below."""


# ---------------------------------------------------------------------------
# The fixtures, one deliberate fault each
# ---------------------------------------------------------------------------


def _taxed_at(registries: Registries, *, pit: float, levy: float) -> Registries:
    """The bond's exempt class with invented rates. Rates above 100% describe no jurisdiction;
    they exist to reach a shape the shipped rules cannot produce."""
    declared = registries.tax_classes[BOND_CLASS]
    entry = declared.rates[0]
    return replace(
        registries,
        tax_classes={
            **registries.tax_classes,
            BOND_CLASS: replace(
                declared,
                rates=(
                    RateEntry(
                        effective_from=entry.effective_from,
                        pit_rate=pit,
                        levy_rate=levy,
                        provenance=entry.provenance,
                    ),
                ),
            ),
        },
    )


def _converting(route_id: str, origin: str, destination: str, direction: str) -> Route:
    """One fixture corridor that changes currency between two shipped venues."""
    departing = Currency.UAH if direction == "inbound" else Currency.USD
    arriving = Currency.USD if direction == "inbound" else Currency.UAH
    leg = replace(
        tuples.transfer_leg(from_venue=origin, to_venue=destination, currency=departing),
        kind="fx",
        to_ccy=arriving,
        channel="p2p",
        kind_of_observation="p2p_premium",
    )
    return Route(
        id=route_id,
        provider="TEST FIXTURE",
        origin=origin,
        destination=destination,
        direction="inbound" if direction == "inbound" else "exit",
        partner_route=None,
        status="open",
        legs=(leg,),
    )


def _a_foreign_taxable_bond() -> Registries:
    """A hryvnia bond redeclared in dollars, with the corridors that make it reachable.

    Unreachable through the shipped declarations -- every declared instrument is hryvnia -- so
    both the instrument and the two corridors are stated here. Without the corridors the pair
    yields no candidate and the refusal is never asked for at all.
    """
    registries = fixtures.shipped()
    declared = registries.instruments[OVDP]
    return replace(
        registries,
        instruments={**registries.instruments, OVDP: replace(declared, currency=Currency.USD)},
        routes={
            **registries.routes,
            "t_usd_in": _converting("t_usd_in", "monobank_uah", "inzhur", "inbound"),
            "t_usd_out": _converting("t_usd_out", "inzhur", "monobank_uah", "exit"),
        },
    )


def _plans(**changes: tuple[InstrumentPlan, ...]) -> Mapping[str, tuple[InstrumentPlan, ...]]:
    return {**fixtures.one_plan_each(fixtures.shipped()), **changes}


def _tiny() -> Mapping[str, Money]:
    return {fixtures.SALARY: Money(1.0, fixtures.UAH, prov.EMPTY)}


PLANTED: dict[str, tuple[Registries, dict[str, object]]] = {
    "InstrumentRefused": (fixtures.shipped(), {}),
    "DeclarationMissing": (
        replace(
            fixtures.shipped(),
            tax_classes={
                key: value
                for key, value in fixtures.shipped().tax_classes.items()
                if key != BOND_CLASS
            },
        ),
        {},
    ),
    "RouteInUnusable": (
        tuples.with_route(fixtures.shipped(), "inzhur_direct", status="closed"),
        {},
    ),
    "RouteInCapExceeded": (
        tuples.with_leg(
            fixtures.shipped(), "inzhur_direct", monthly_cap=Money(100.0, fixtures.UAH, prov.EMPTY)
        ),
        {},
    ),
    "WayOutUnusable": (
        tuples.with_leg(
            fixtures.shipped(),
            "inzhur_to_monobank",
            minimum=Money(1_000_000.0, fixtures.UAH, prov.EMPTY),
        ),
        {},
    ),
    "WayOutCapExceeded": (
        tuples.with_leg(
            fixtures.shipped(),
            "inzhur_to_monobank",
            monthly_cap=Money(100.0, fixtures.UAH, prov.EMPTY),
        ),
        {},
    ),
    "BelowMinimumTicket": (fixtures.shipped(), {"amounts": _tiny()}),
    "BuysNoWholeUnit": (
        fixtures.shipped(),
        {"amounts": {fixtures.SALARY: Money(500.0, fixtures.UAH, prov.EMPTY)}},
    ),
    "CannotSpanHorizon": (
        fixtures.shipped(),
        {"horizon": DateRange(start=fixtures.OUTLAY_ON, end=date(2026, 5, 1))},
    ),
    "NoExitTermsDeclared": (
        fixtures.shipped(),
        {
            "plans": _plans(
                inzhur_miltech=(
                    fixtures.fund_plan(
                        fixtures.shipped().funds[MILTECH],
                        liquidity_mode="legal",
                        buyback="unavailable",
                    ),
                )
            )
        },
    ),
    "TwoFiguresNotOne": (
        fixtures.shipped(),
        {
            "plans": _plans(
                inzhur_miltech=(
                    fixtures.fund_plan(fixtures.shipped().funds[MILTECH], yield_point=None),
                )
            )
        },
    ),
    "PlanDoesNotFitInstrument": (
        fixtures.shipped(),
        {"plans": _plans(ovdp_synthetic_a=(fixtures.fund_plan(fixtures.shipped().funds[REIT]),))},
    ),
    "InstrumentDemandsCash": (_taxed_at(fixtures.shipped(), pit=0.9, levy=0.9), {}),
    "TaxCurrencyConversionUnavailable": (_a_foreign_taxable_bond(), {}),
}
"""One registry-and-question per refusal this loop can actually reach."""

UNREACHABLE: dict[str, str] = {
    "FundedFromAnotherStream": (
        "enumeration composes each way in *from* the stream the pair names, so a key whose "
        "two stream ids disagree cannot be built"
    ),
    "SeamDoesNotChain": (
        "both chains are anchored by `compose`: the way in ends at the venue and currency the "
        "purchase happens in, and the way out departs from where the proceeds land"
    ),
    "NoExitRouteDeclared": (
        "every way out is either a chain `compose` walked to a declared spendable endpoint or "
        "the identity exit, and the `FROM_THE_DECLARATION` sentinel is never emitted"
    ),
}
"""The three no registry can reach through this loop, each with the seam that closes it.

Recorded rather than skipped: *unreachable today* and *unreachable by construction* are
different claims, and each of these is checked below by the property that makes it so.
"""


# ---------------------------------------------------------------------------
# The battery
# ---------------------------------------------------------------------------


def _question(registries: Registries, changes: dict[str, object]) -> Question:
    return fixtures.question(registries, **changes)  # type: ignore[arg-type]


def _surveyed(registries: Registries, changes: dict[str, object]) -> CandidateSurvey:
    question = _question(registries, changes)
    enumerated = fixtures.enumerated(registries, question_=question)
    assert isinstance(enumerated, CandidateSet), enumerated
    result = survey(
        registries=registries,
        routes=registries.routes,
        question=question,
        ceiling=fixtures.ceiling(10_000),
        benchmark=enumerated.candidates[0].key,
    )
    assert isinstance(result, CandidateSurvey), result
    return result


def test_the_battery_covers_every_member_of_the_union() -> None:
    """An eighteenth member fails here, not only in 010's own suite."""
    assert set(PLANTED) | set(UNREACHABLE) == {member.__name__ for member in get_args(TupleRefused)}
    assert not set(PLANTED) & set(UNREACHABLE)


def test_the_baseline_puts_nine_pairs_in_the_third_column() -> None:
    """The constant every planted case is measured against, read off the registry."""
    enumerated = fixtures.enumerated(fixtures.shipped())
    assert isinstance(enumerated, CandidateSet), enumerated
    assert len(enumerated.no_candidate) == UNCHANGED_NO_CANDIDATES


@pytest.mark.parametrize("refusal", sorted(PLANTED))
def test_each_planted_refusal_drops_a_candidate_and_appears_in_the_tally(refusal: str) -> None:
    registries, changes = PLANTED[refusal]
    result = _surveyed(registries, changes)
    tally = {group.refusal: group for group in drop_tally(dropped(result.comparison))}
    assert refusal in tally, sorted(tally)
    assert tally[refusal].count >= 1
    assert tally[refusal].instruments


@pytest.mark.parametrize("refusal", sorted(PLANTED))
def test_no_planted_refusal_moves_a_pair_into_the_no_candidate_column(refusal: str) -> None:
    """The assertion the whole battery exists for. A drop is the rejection of an option; a pair
    in the third column is the absence of one, and the owner's remedy for the two is opposite."""
    registries, changes = PLANTED[refusal]
    result = _surveyed(registries, changes)
    assert len(result.enumerated.no_candidate) == UNCHANGED_NO_CANDIDATES


@pytest.mark.parametrize("refusal", sorted(PLANTED))
def test_each_planted_case_still_closes_the_second_identity(refusal: str) -> None:
    registries, changes = PLANTED[refusal]
    result = _surveyed(registries, changes)
    assert len(evaluated(result.comparison)) + len(dropped(result.comparison)) == len(
        result.enumerated.candidates
    )


class TestTheThreeNoLoopCanReach:
    """Each recorded reason, checked as the property that makes it a property.

    Compared as **junctions** -- ``(venue, currency)`` -- because that is what the refusals
    standing in for them compare. A venue-only check would pass on exactly the currency-mismatched
    chain that reaches ``SeamDoesNotChain``, and a shipped registry with one currency could never
    tell the two apart.

    Run over several narrowings of the shipped registry rather than over it alone, so "no loop
    can reach this" is checked against more than one shape of world. That is still not every
    registry: the claim rests on `compose` anchoring both ends exactly, and these are the
    executable half of it.
    """

    @staticmethod
    def _worlds() -> list[Registries]:
        shipped = fixtures.shipped()
        instruments = sorted(shipped.access)
        return [
            shipped,
            # Two currencies, so a venue-only comparison and a junction one are no longer the
            # same assertion on this input.
            _a_foreign_taxable_bond(),
            fixtures.with_access(shipped, OVDP, proceeds_to="monobank_uah"),
            replace(
                shipped,
                access={key: shipped.access[key] for key in instruments[:3]},
            ),
            tuples.with_new_route(
                shipped,
                tuples.route(
                    "test_second_way_in",
                    origin="monobank_uah",
                    destination="inzhur",
                    direction="inbound",
                    fee_pct=0.02,
                ),
            ),
        ]

    @staticmethod
    def _keys(registries: Registries) -> tuple[Tuple, ...]:
        enumerated = fixtures.enumerated(registries)
        assert isinstance(enumerated, CandidateSet), enumerated
        return tuple(item.key for item in enumerated.candidates)

    def test_the_worlds_cover_more_than_one_currency_and_the_identity_exit(self) -> None:
        """The control, and it guards **coverage** rather than variety.

        Set sizes alone would not: the two-currency world yields the same nine candidates the
        shipped one does, so a fixture that quietly stopped producing a dollar candidate would
        leave the sizes unchanged and silently degrade every junction assertion below back to a
        single-currency check -- which is the exact degradation those assertions exist to
        prevent.
        """
        currencies: set[str] = set()
        identity_exits = 0
        for world in self._worlds():
            for key in self._keys(world):
                _, arrives = cost.junctions_of(world.routes[segments_of(key.route_in)[-1]])
                currencies.add(arrives[1])
                if key.route_out is EXIT_BY_IDENTITY:
                    identity_exits += 1
        assert len(currencies) > 1, currencies
        assert identity_exits > 0
        assert len({len(self._keys(world)) for world in self._worlds()}) > 1

    def test_a_way_in_is_always_costed_from_the_stream_the_key_names(self) -> None:
        """``FundedFromAnotherStream`` compares exactly these two ids."""
        for world in self._worlds():
            for key in self._keys(world):
                assert key.route_in.stream_id == key.stream_id

    def test_both_seams_meet_as_junctions_and_not_merely_as_venues(self) -> None:
        """``SeamDoesNotChain``'s two anchors: where the way in arrives against where the
        purchase happens, and where the proceeds land against where the way out departs."""
        for world in self._worlds():
            for key in self._keys(world):
                access = world.access[key.instrument_id]
                declared = (
                    world.funds.get(key.instrument_id) or world.instruments[key.instrument_id]
                )
                purchase = (access.bought_at, currency_of(declared).value)
                proceeds = (access.proceeds_to, currency_of(declared).value)
                way_in = segments_of(key.route_in)
                _, arrives = cost.junctions_of(world.routes[way_in[-1]])
                assert arrives == purchase
                way_out = key.route_out
                if way_out is EXIT_BY_IDENTITY:
                    assert proceeds in cost.spendable_junctions(world.spendable)
                    continue
                assert isinstance(way_out, ExitChain)
                departs, _ = cost.junctions_of(world.routes[exit_segments_of(way_out)[0]])
                assert departs == proceeds

    def test_every_way_out_ends_at_a_declared_spendable_junction(self) -> None:
        """``NoExitRouteDeclared`` fires on ``(venue, currency) not in spendable_junctions``,
        so that is what is compared -- hryvnia at a venue the owner never spends from and
        dollars at one he does are both failures, and a venue check sees neither."""
        for world in self._worlds():
            endpoints = cost.spendable_junctions(world.spendable)
            for key in self._keys(world):
                way_out = key.route_out
                if way_out is EXIT_BY_IDENTITY:
                    continue
                assert isinstance(way_out, ExitChain)
                _, arrives = cost.junctions_of(world.routes[exit_segments_of(way_out)[-1]])
                assert arrives in endpoints
