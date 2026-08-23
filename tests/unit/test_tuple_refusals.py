"""SC-005: remove any one of the four parts' declarations and get a typed refusal naming it.

FR-006's rule and the reason for it: *never an outcome computed with the missing part assumed
zero, free, or instantaneous.* Those are the three flattering defaults, and a comparison built
on any of them recommends whatever nobody has finished costing -- which is the predecessor's
headline defect with the arrow pointing the other way.

The battery runs over all four parts and the two exit gaps, and the last class asserts the
property the battery exists to establish: **no case in it produces an outcome**. A refusal that
named the right thing while a sibling path quietly returned a figure would satisfy every
assertion above it.

FR-008's distinction is the subtle one, and it has its own class. *No declared exit route* and
*no exit terms* are both "there is no way out", and they call for different actions: one is
answered by declaring a route, the other by waiting for the instrument's own termination or
accepting a discount the terms do not owe. They are different **types**, so a consumer that
treats them alike is a mypy error rather than a report that gives the wrong advice.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Final, get_args

import pytest

from terezy.core.decision.tuple_outcome import Registries, evaluate
from terezy.core.results.tuple import (
    DeclarationMissing,
    NoExitRouteDeclared,
    NoExitTermsDeclared,
    PlanDoesNotFitInstrument,
    TupleOutcome,
    TupleRefused,
    TwoFiguresNotOne,
)
from tests import tuple_registries as fixtures

DEAD_END: Final = "test_dead_end_in"
"""A way in to a venue nobody has declared a way out of. Its `partner_route` is omitted, which
is the declared statement that nobody has costed the exit."""


def _evaluated(registries: Registries, candidate: object | None = None) -> object:
    return evaluate(
        candidate if candidate is not None else fixtures.hurdle_tuple(),  # type: ignore[arg-type]
        amount=fixtures.AMOUNT,
        horizon=fixtures.DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END),
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=registries,
    )


class TestOneMissingDeclarationPerPart:
    """Four parts, four removals, four typed refusals naming what is gone."""

    def test_an_instrument_nobody_declared(self) -> None:
        refusal = _evaluated(
            fixtures.shipped(),
            replace(fixtures.hurdle_tuple(), instrument_id="nothing_declares_this"),
        )
        assert isinstance(refusal, DeclarationMissing), refusal
        assert refusal.part == "instrument"
        assert "nothing_declares_this" in refusal.what

    def test_an_instrument_with_no_access_declaration(self) -> None:
        # The part this feature added, and the one that makes both venue seams anchorable.
        # Without
        # it the join could check only the currency -- which is feature 004's defect exactly.
        refusal = _evaluated(fixtures.without_access(fixtures.shipped(), fixtures.OVDP))
        assert isinstance(refusal, DeclarationMissing), refusal
        assert refusal.part == "access"
        assert fixtures.OVDP in refusal.what

    def test_a_tax_class_the_instrument_names_and_no_jurisdiction_declares(self) -> None:
        # Refused rather than projected untaxed: "no rule was found" and "the rule charged
        # nothing" are opposite claims and only one of them is cited.
        refusal = _evaluated(fixtures.without_tax_class(fixtures.shipped(), "ua_government_bond"))
        assert isinstance(refusal, DeclarationMissing), refusal
        assert refusal.part == "tax_class"
        assert "ua_government_bond" in refusal.what

    def test_an_income_stream_nobody_declared(self) -> None:
        refusal = _evaluated(
            fixtures.shipped(), replace(fixtures.hurdle_tuple(), stream_id="no_such_income")
        )
        assert isinstance(refusal, DeclarationMissing), refusal
        assert refusal.part == "route_in"
        assert "no_such_income" in refusal.what

    def test_a_way_in_naming_a_route_nobody_declared(self) -> None:
        refusal = _evaluated(
            fixtures.shipped(),
            replace(
                fixtures.hurdle_tuple(),
                route_in=fixtures.FundingPath(
                    destination_id="inzhur",
                    stream_id=fixtures.SALARY,
                    route_id="no_such_route",
                ),
            ),
        )
        assert isinstance(refusal, DeclarationMissing), refusal
        assert refusal.part == "route_in"

    def test_a_way_out_naming_a_route_nobody_declared(self) -> None:
        refusal = _evaluated(
            fixtures.shipped(),
            fixtures.hurdle_tuple(route_out=fixtures.DeclaredExit(route_id="no_such_exit")),
        )
        assert isinstance(refusal, DeclarationMissing), refusal
        assert refusal.part == "route_out"


class TestTheTwoExitGapsAreDistinguishable:
    """FR-008: route-level and instrument-level, and the owner acts differently on each."""

    def test_a_destination_with_no_declared_exit_route(self) -> None:
        # 002's FR-030, inherited whole: not comparison-ready, and the one-way figure is not
        # promoted into the gap. `binance` is not a declared spendable endpoint, so no exit by
        # identity rescues it either.
        registries = fixtures.with_new_route(
            fixtures.shipped(),
            fixtures.route(
                DEAD_END,
                origin="monobank_uah",
                destination="binance",
                direction="inbound",
            ),
        )
        registries = fixtures.with_access(registries, fixtures.OVDP, bought_at="binance")
        registries = fixtures.with_access(registries, fixtures.OVDP, proceeds_to="binance")
        refusal = _evaluated(
            registries,
            replace(
                fixtures.hurdle_tuple(),
                route_in=fixtures.FundingPath(
                    destination_id="binance", stream_id=fixtures.SALARY, route_id=DEAD_END
                ),
            ),
        )
        assert isinstance(refusal, NoExitRouteDeclared), refusal
        assert refusal.unknown.missing_partner_for == DEAD_END

    def test_an_instrument_whose_terms_owe_no_way_out(self) -> None:
        # The other gap, and a different type. The регламент owes no buyback before the fund's
        # termination in 2045, so under the legal terms with no discretionary buyback on offer
        # there is no exit at all -- and the holding stays open rather than being liquidated
        # at a discount nobody granted.
        refusal = _evaluated(
            fixtures.shipped(),
            fixtures.fund_tuple(
                fixtures.REIT,
                exit_on=date(2028, 1, 17),
                liquidity_mode="legal",
                buyback="unavailable",
            ),
        )
        assert isinstance(refusal, NoExitTermsDeclared), refusal
        assert refusal.instrument_id == fixtures.REIT

    def test_the_union_has_the_fifteen_members_its_docstring_counts(self) -> None:
        # A count in prose that nothing checks is a count that goes stale on the next commit,
        # and this one already did once -- it was written as fourteen, deleted as though it
        # were wrong, and is now a number with a test under it.
        assert len(get_args(TupleRefused)) == 15

    def test_the_two_are_separate_members_of_the_refusal_union(self) -> None:
        # The mechanism behind the distinction, stated so a later refactor cannot collapse
        # them into one record with a flag: they share no base, so a consumer that matched one
        # and forgot the other is a type error rather than a report giving the wrong advice.
        members = set(get_args(TupleRefused))
        assert {NoExitRouteDeclared, NoExitTermsDeclared} <= members
        assert not issubclass(NoExitRouteDeclared, NoExitTermsDeclared)
        assert not issubclass(NoExitTermsDeclared, NoExitRouteDeclared)


class TestRunSettingsAndRangesRefuseRatherThanGuess:
    """Two more ways there is honestly no single figure."""

    def test_a_bonds_settings_on_a_fund_are_reported_rather_than_coerced(self) -> None:
        # Silently dropping the fields that do not apply would run the holding under settings
        # the caller believes are in force -- a fund projected with no liquidity mode at all.
        refusal = _evaluated(
            fixtures.shipped(),
            replace(
                fixtures.fund_tuple(fixtures.MILTECH, exit_on=fixtures.MILTECH_EXIT),
                exit_terms=fixtures.HOLD_TO_MATURITY,
            ),
        )
        assert isinstance(refusal, PlanDoesNotFitInstrument), refusal
        assert refusal.instrument_id == fixtures.MILTECH

    def test_a_stated_range_with_no_chosen_point_is_two_figures_and_no_tuple(self) -> None:
        # MilTech states 25-29% and a tuple has one outcome. Taking the midpoint, the low end
        # or the high end would be the false point a range exists to refuse.
        refusal = _evaluated(
            fixtures.shipped(),
            fixtures.fund_tuple(fixtures.MILTECH, exit_on=fixtures.MILTECH_EXIT),
        )
        assert isinstance(refusal, TwoFiguresNotOne), refusal
        assert refusal.instrument_id == fixtures.MILTECH


class TestNoCaseInTheBatteryProducesAFigure:
    """The property the battery exists to establish, checked over all of it at once."""

    @pytest.mark.parametrize(
        ("registries", "candidate"),
        [
            pytest.param(
                fixtures.shipped(),
                replace(fixtures.hurdle_tuple(), instrument_id="nothing_declares_this"),
                id="instrument",
            ),
            pytest.param(
                fixtures.without_access(fixtures.shipped(), fixtures.OVDP),
                fixtures.hurdle_tuple(),
                id="access",
            ),
            pytest.param(
                fixtures.without_tax_class(fixtures.shipped(), "ua_government_bond"),
                fixtures.hurdle_tuple(),
                id="tax class",
            ),
            pytest.param(
                fixtures.shipped(),
                replace(fixtures.hurdle_tuple(), stream_id="no_such_income"),
                id="stream",
            ),
            pytest.param(
                fixtures.shipped(),
                fixtures.hurdle_tuple(route_out=fixtures.DeclaredExit(route_id="no_such_exit")),
                id="way out",
            ),
            pytest.param(
                fixtures.shipped(),
                fixtures.fund_tuple(
                    fixtures.REIT,
                    exit_on=date(2028, 1, 17),
                    liquidity_mode="legal",
                    buyback="unavailable",
                ),
                id="instrument exit terms",
            ),
        ],
    )
    def test_the_missing_part_is_never_assumed_zero_free_or_instantaneous(
        self, registries: Registries, candidate: object
    ) -> None:
        assert not isinstance(_evaluated(registries, candidate), TupleOutcome)
