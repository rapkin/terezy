"""Fixtures for the candidate suites: the shipped question, and deliberate edits to it.

Built from ``data/`` rather than by hand, on ``tests/tuple_registries.py``'s reasoning
unchanged: enumeration's whole claim is that it walks declarations, so a suite that hand-built
every record would be measuring a world the loader never validated.

Each helper makes **one** change and says what it is breaking. A fixture that changed two
things at once would let a test pass for the other reason.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Final

from terezy.core.decision.candidates import enumerate_candidates
from terezy.core.instruments.fund import ChosenPoint, FundDeclaration
from terezy.core.instruments.interface import Assumptions, DateRange
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.candidates import (
    CandidateCeiling,
    CandidateSet,
    EnumerationRefused,
    Question,
)
from terezy.core.results.coverage import IMPLICIT_REGIME_ID, SpendableEndpoint
from terezy.core.results.fund import FundAssumptions
from terezy.core.results.tuple import HOLD_AS_CASH, Tuple
from terezy.data.declarations import resolver

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping

    from terezy.core.decision.tuple_outcome import Registries
    from terezy.core.results.composed import SegmentBound
    from terezy.core.results.tuple import InstrumentPlan
    from terezy.core.routes.legs import Route

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
DATA_ROOT: Final = REPO_ROOT / "data"

UAH: Final = Currency.UAH
USD: Final = Currency.USD

SALARY: Final = "salary_uah"
CONTRACT: Final = "contract_usd"

OUTLAY_ON: Final = date(2026, 4, 1)
"""When the money leaves.

On or after every shipped instrument's issue date and schedule start, so a bond bought here is
bought into terms that are already complete. An earlier outlay refuses most of the registry as
``InstrumentRefused`` before anything else can be exercised, which would leave a battery
measuring the date rather than what it planted.
"""

HORIZON_END: Final = date(2030, 6, 30)
AS_OF: Final = date(2026, 8, 23)
HORIZON: Final = DateRange(start=OUTLAY_ON, end=HORIZON_END)

AMOUNT_UAH: Final = Money(10_000.0, UAH, prov.EMPTY)
"""Ten units of issue A at its declared par price of 1 000.00, so nothing is left undeployed."""

AMOUNT_USD: Final = Money(250.0, USD, prov.EMPTY)
"""The dollar stream's own amount, in its own currency. Nothing converts it (FR-005)."""

FUND_EXIT: Final = date(2028, 1, 17)
"""When a fund holding is exited: the date issue A's principal comes back, so the tuples are
compared over one span as well as over one horizon."""

HOLD_TO_MATURITY: Final = Assumptions(consumption_method="fifo", coupon_policy="hold_cash")

RATIONALE: Final = (
    "TEST FIXTURE -- the low end of this fund's own stated range, so the figure is the least "
    "flattering one the range admits rather than a midpoint nobody stated."
)


def low_end(declared: FundDeclaration) -> ChosenPoint:
    """The bottom of one fund's own declared range.

    Read from the declaration rather than written out, so no fixture point can wander outside
    the range its fund states -- which refuses as ``InstrumentRefused`` and would give a suite
    a drop it never planted.
    """
    return ChosenPoint(rate=declared.declared_yield.low, is_assumption=True, rationale=RATIONALE)


def fund_plan(
    declared: FundDeclaration,
    *,
    exit_on: date | None = FUND_EXIT,
    yield_point: ChosenPoint | None = None,
    liquidity_mode: str = "practice",
    buyback: str = "available",
) -> FundAssumptions:
    """One way of running a fund. Every field stated, because none has a default."""
    return FundAssumptions(
        liquidity_mode=liquidity_mode,  # type: ignore[arg-type]
        buyback=buyback,  # type: ignore[arg-type]
        exit_on=exit_on,
        yield_point=low_end(declared) if yield_point is None else yield_point,
        exchange_rate=None,
        consumption_method="fifo",
    )


def declarations() -> resolver.CandidateDeclarations:
    """Every declaration an enumeration needs, under the shipped data root."""
    return resolver.candidates_from_data_root(DATA_ROOT, base_currency=UAH, scenario_id=None)


def shipped() -> Registries:
    """The join's registries for the shipped data root."""
    return resolver.tuple_from_data_root(DATA_ROOT, base_currency=UAH, scenario_id=None).registries


def one_plan_each(registries: Registries) -> dict[str, tuple[InstrumentPlan, ...]]:
    """One run plan per declared instrument, of the kind that instrument's declaration takes.

    A fund gets a fund plan and a bond gets a bond plan, because a plan of the wrong kind is
    ``PlanDoesNotFitInstrument`` -- a *drop*, which several suites here plant deliberately and
    none of them wants by accident.
    """
    return {
        instrument_id: (
            (fund_plan(registries.funds[instrument_id]),)
            if instrument_id in registries.funds
            else (HOLD_TO_MATURITY,)
        )
        for instrument_id in sorted(registries.access)
    }


def question(
    registries: Registries,
    *,
    bound: SegmentBound | None = None,
    plans: Mapping[str, tuple[InstrumentPlan, ...]] | None = None,
    amounts: Mapping[str, Money] | None = None,
    horizon: DateRange = HORIZON,
    as_of: date = AS_OF,
    regime_id: str = IMPLICIT_REGIME_ID,
) -> Question:
    """The shipped question: an amount per stream, one horizon, one plan per instrument."""
    return Question(
        amounts=dict(amounts)
        if amounts is not None
        else {SALARY: AMOUNT_UAH, CONTRACT: AMOUNT_USD},
        horizon=horizon,
        as_of=as_of,
        continuation=HOLD_AS_CASH,
        plans=dict(plans) if plans is not None else one_plan_each(registries),
        bound=bound if bound is not None else declarations().composition.bound,
        regime_id=regime_id,
    )


def enumerated(
    registries: Registries,
    *,
    question_: Question | None = None,
    ceiling_: CandidateCeiling | None = None,
    routes: Mapping[str, Route] | None = None,
) -> CandidateSet | EnumerationRefused:
    """``enumerate_candidates`` with the shipped wiring. Argument plumbing and nothing else.

    Deliberately thin: a fixture that decided anything the function under test decides would
    let a suite pass on the fixture's judgement rather than on the engine's.
    """
    return enumerate_candidates(
        registries=registries,
        routes=registries.routes if routes is None else routes,
        question=question(registries) if question_ is None else question_,
        ceiling=ceiling(10_000) if ceiling_ is None else ceiling_,
    )


def benchmark_key(registries: Registries, instrument_id: str, **kwargs: object) -> Tuple:
    """The enumerated candidate for one instrument, to be named as a comparison's benchmark.

    Read out of the set rather than built, which is FR-022 in the fixture: a benchmark
    constructed beside the set is exactly the privileged side channel 010 FR-012 forbids.
    """
    result = enumerated(registries, **kwargs)  # type: ignore[arg-type]
    assert isinstance(result, CandidateSet), result
    return next(item.key for item in result.candidates if item.key.instrument_id == instrument_id)


def ceiling(max_candidates: int) -> CandidateCeiling:
    """A ceiling stated by a test rather than declared, so a battery can plant one."""
    return CandidateCeiling(max_candidates=max_candidates)


def with_access(registries: Registries, instrument_id: str, **changes: object) -> Registries:
    """The same registry with one access declaration edited -- a venue, a price, a risk class."""
    access = dict(registries.access)
    access[instrument_id] = replace(access[instrument_id], **changes)  # type: ignore[arg-type]
    return replace(registries, access=access)


def with_spendable(registries: Registries, venue_id: str, currency: Currency = UAH) -> Registries:
    """The same registry with one more declared spendable endpoint."""
    return replace(
        registries,
        spendable=registries.spendable | {SpendableEndpoint(venue_id=venue_id, currency=currency)},
    )
