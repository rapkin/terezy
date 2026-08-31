"""SC-009 and FR-014: every reported figure states what it accounts for and what it excludes.

Feature 001's hurdle rate carries an ``excludes`` set that admits, in the output's own words,
that it ignores funding and exit route costs. That admission is the honest form of an
incomplete figure, and this feature's job was to move both items from one set to the other.
So the first class checks the **move**: what 001 excluded, a tuple outcome accounts for, and
neither set is a decoration nobody maintains.

The second class reads a scope statement off the outcome and checks it against what the
pipeline **did**. That is the half a set of strings cannot do for itself: the undeployed
clause was false for a whole feature while every assertion about it passed, because every
assertion about it compared the code's constant against the code's constant.

The third class is the "not sampled" clause. It walks every field of every outcome and
refusal this suite can produce and requires each to be classified -- a figure, a statement of
scope, a key, a mark. A field nobody classified is a figure nobody labelled, and the closed
classification is deliberate friction: adding one to the record fails this module until a
reader decides which kind of thing it is.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import date
from typing import Final, get_args

import pytest

from terezy.core.decision.tuple_outcome import evaluate
from terezy.core.instruments.fund import ExchangeRateAssumption
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.rates import NominalRate
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.fund import FundAssumptions
from terezy.core.results.hurdle import EXCLUDES as HURDLE_EXCLUDES
from terezy.core.results.tuple import (
    ACCOUNTS_FOR,
    EXCLUDES,
    Part,
    RateNotComparable,
    Tuple,
    TupleOutcome,
)
from tests import tuple_registries as fixtures

pytestmark = pytest.mark.contract

CLASSIFIED: Final[frozenset[str]] = frozenset(
    {
        # The two figures, each labelled by its own field name (research.md D8).
        "reaches",
        "implied_rate",
        # What the figures are of, and over what.
        "outlay",
        "arrivals",
        "span",
        "horizon",
        # The attribution: what each term took, with the call that produced it named.
        "parts",
        # Money that made the trip and bought nothing. Reported, and netted off the outlay
        # the rate is measured against rather than discounted as a loss.
        "undeployed",
        # The scope statements this module is about.
        "accounts_for",
        "excludes",
        "rests_on",
        # The key, all five terms of it.
        "key",
        "risk_class",
        # How usable the declared ways are -- the field a reader scans to decide whether to
        # trust the figures beside it.
        "routes",
        # How the position closed, where the horizon closed it rather than its own terms
        # (015 FR-029). Not a figure of its own -- every amount in it is already in the
        # arrivals -- and typed rather than readable off `rests_on`, because an early-exit
        # figure carries three stated exclusions and deciding to attach them by searching a
        # sentence is the string-matching a case field exists to avoid.
        "sold_early",
        # Marks travel with every figure; they are not figures.
        "provenance",
        "staleness",
    }
)
"""Every field of :class:`TupleOutcome`, classified. See the module docstring on why closed."""


FLAT_FEE_ROUTE: Final = "test_flat_fee_in"


def _outcome(
    sent: float | None = None,
    *,
    registries: fixtures.Registries | None = None,
    flat: float | None = None,
) -> TupleOutcome:
    """One tuple's outcome, optionally over a way in charging a flat fee and nothing else.

    ``flat`` exists so a test can tell the outlay and the arriving amount apart. Over the
    shipped domestic route they are one number, and a claim about which of them a figure rests
    on cannot be checked against a pair that agrees.
    """
    resolved = registries or fixtures.shipped()
    candidate = fixtures.hurdle_tuple()
    if flat is not None:
        resolved = fixtures.with_new_route(
            resolved,
            fixtures.route(
                FLAT_FEE_ROUTE,
                origin="monobank_uah",
                destination="inzhur",
                direction="inbound",
                partner=fixtures.DOMESTIC_OUT,
                fee_fixed=flat,
            ),
        )
        candidate = fixtures.replace(
            candidate,
            route_in=fixtures.FundingPath(
                destination_id="inzhur", stream_id=fixtures.SALARY, route_id=FLAT_FEE_ROUTE
            ),
        )
    outcome = evaluate(
        candidate,
        amount=fixtures.AMOUNT if sent is None else fixtures.Money(sent, fixtures.UAH, prov.EMPTY),
        horizon=fixtures.DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END),
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=resolved,
    )
    assert isinstance(outcome, TupleOutcome), outcome
    return outcome


def _fund_outcome(candidate: Tuple, horizon: fixtures.DateRange) -> TupleOutcome:
    """One shipped fund's outcome: the other projection kind the join has to handle."""
    outcome = evaluate(
        candidate,
        amount=fixtures.AMOUNT,
        horizon=horizon,
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=fixtures.shipped(),
    )
    assert isinstance(outcome, TupleOutcome), outcome
    return outcome


def _miltech() -> TupleOutcome:
    """MilTech: one taxed disposal gain on the exit date, and nothing before it."""
    return _fund_outcome(
        fixtures.fund_tuple(
            fixtures.MILTECH, exit_on=fixtures.MILTECH_EXIT, yield_point=fixtures.MILTECH_POINT
        ),
        fixtures.DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END),
    )


ON_A_PAYMENT_DAY: Final = date(2027, 6, 10)
"""Exit on one of the REIT's own distribution days, so that date carries **two** taxable
payments and two charges. Every distribution falls on a 10th."""

ON_A_QUIET_DAY: Final = date(2027, 6, 30)
"""Exit at month end, which is not a payment day, so every payment has a date to itself."""


def _reit(exit_on: date) -> TupleOutcome:
    """The REIT over a year of taxed monthly distributions, plus the disposal that ends it.

    ``exchange_rate`` because the REIT's payout is **pegged** and a pegged fund may not be
    projected without an owner-stated rate -- the same construct
    ``tests/contract/test_fund_data_only.py`` attaches, and for the same declared reason. The
    window starts after 2026-06-30, the effective date ``ua_ci_fund_distribution`` is dated
    from, so the distribution class actually charges rather than refusing as pre-schedule.
    """
    candidate = fixtures.fund_tuple(fixtures.REIT, exit_on=exit_on)
    terms = candidate.exit_terms
    assert isinstance(terms, FundAssumptions)
    return _fund_outcome(
        dataclasses.replace(
            candidate,
            exit_terms=dataclasses.replace(
                terms,
                exchange_rate=ExchangeRateAssumption(
                    uah_per_unit=42.0,
                    is_assumption=True,
                    rationale="TEST -- an owner-stated rate, for a payout that is pegged.",
                ),
            ),
        ),
        fixtures.DateRange(start=date(2026, 7, 1), end=date(2027, 6, 30)),
    )


class TestWhatFeatureOneExcludedThisFeatureAccountsFor:
    """The move, asserted rather than described -- so neither set can rot in place."""

    @pytest.mark.parametrize("excluded", ["funding route costs", "exit route costs"])
    def test_the_hurdle_excluded_it_and_the_tuple_accounts_for_it(self, excluded: str) -> None:
        # 001 named both in `excludes` and this feature exists to close them. A later change
        # moving a term the other way has to delete a line in one set and add one to the
        # other, in the same diff, where a reviewer sees both.
        assert any(excluded in item for item in HURDLE_EXCLUDES)
        assert any(excluded in item for item in ACCOUNTS_FOR)
        assert not any(excluded in item for item in EXCLUDES)

    def test_the_two_sets_do_not_overlap(self) -> None:
        # A term in both would let a figure claim to be net of something it also says it
        # ignores, which is worse than either statement alone.
        assert not (ACCOUNTS_FOR & EXCLUDES)

    def test_the_outcome_states_that_it_is_after_tax(self) -> None:
        # US1 scenario 4. Between two instruments taxed at 0% and 23%, "is this after tax?" is
        # the whole decision, and a figure that does not say is exactly the ambiguity
        # Principle I exists to prevent.
        assert any("tax" in item for item in _outcome().accounts_for)

    @pytest.mark.parametrize(
        ("name", "build", "least_dates"),
        [
            # Both taxable event kinds a fund produces, because different declared classes
            # charge them: MilTech's single `disposal_gain` on the exit date under
            # `ua_investment_profit`, and the REIT's year of monthly `distribution` charges
            # under `ua_ci_fund_distribution` plus the disposal that ends it. The second is
            # the multi-charge shape -- a draft of this suite recorded it as unreachable
            # without new data, and it is reachable over the shipped registry.
            ("miltech", _miltech, 1),
            ("reit", lambda: _reit(ON_A_QUIET_DAY), 11),
        ],
    )
    def test_a_taxed_fund_sends_home_what_is_left_after_the_charge(
        self, name: str, build: Callable[[], TupleOutcome], least_dates: int
    ) -> None:
        # The clause above checked against behaviour rather than against itself, on the second
        # projection kind -- `tests/contract/test_h1_data_only.py` does it for a bond. Over the
        # **shipped** registry and not a rigged one: only the bond's class is exempt, and both
        # of these funds are charged at rates `data/tax/ua.toml` declares. An earlier draft
        # passed those same rates in through a fixture, which did nothing except hide that
        # this is the shipped behaviour.
        #
        # Since feature 009 a TAX_CHARGE is an assessment memo that moves nothing, so a join
        # summing the ledger's events alone sends the **gross** proceeds home: every part line
        # still reads correctly and only the arrivals say the rate went pre-tax.
        outcome = build()
        lifecycle = next(line.amount for line in outcome.parts if line.part == "lifecycle")
        charged = next(line.amount for line in outcome.parts if line.part == "tax")
        released = sum(arrival.released.amount for arrival in outcome.arrivals)
        assert charged.amount < 0.0
        assert is_close(released, lifecycle.amount + charged.amount), name
        assert not is_close(released, lifecycle.amount), name
        # Dates, not charges -- the two coincide here and the difference is the subject of the
        # test below. The count says which shape was exercised: the identity above holds just
        # as well over one charge, so without it the multi-charge case could quietly collapse
        # back to the single one and nothing here would notice.
        assert len({arrival.released_on for arrival in outcome.arrivals}) >= least_dates, name

    def test_two_payments_on_one_date_go_home_as_one_arrival(self) -> None:
        # Per-date netting, which is the whole reason `_released_by_date` groups: a date the
        # holding pays twice on is one journey home and one flat fee, not two. Reached by
        # moving the exit onto one of the REIT's own distribution days -- nothing rigged, the
        # shipped registry, and the only difference from the case above is the date.
        #
        # The eleven payments are the same either way. Exiting on a quiet day gives each its
        # own arrival; exiting on a payment day merges two into one whose amount is exactly
        # their sum, so the identity holds per date and not only in total.
        quiet = _reit(ON_A_QUIET_DAY)
        shared = _reit(ON_A_PAYMENT_DAY)
        assert len(quiet.arrivals) == 11
        assert len(shared.arrivals) == 10

        merged = [a for a in shared.arrivals if a.released_on == ON_A_PAYMENT_DAY]
        assert len(merged) == 1
        separate = [
            arrival.released.amount
            for arrival in quiet.arrivals
            if arrival.released_on in (ON_A_PAYMENT_DAY, ON_A_QUIET_DAY)
        ]
        assert len(separate) == 2
        assert is_close(merged[0].released.amount, sum(separate))
        assert is_close(
            sum(arrival.released.amount for arrival in shared.arrivals),
            sum(arrival.released.amount for arrival in quiet.arrivals),
        )

    def test_it_states_that_waiting_is_inside_the_span(self) -> None:
        # The owner's decision of 2026-08-22, on the record's face: a reader comparing this
        # rate against a contractual yield-to-maturity is comparing two different spans, and
        # nothing else in the output would tell them so.
        assert any("latency" in item for item in _outcome().accounts_for)

    def test_it_states_the_five_things_it_still_leaves_out(self) -> None:
        outcome = _outcome()
        assert len(outcome.excludes) == 5
        assert any("inflation" in item for item in outcome.excludes)
        assert any("risk class" in item for item in outcome.excludes)
        assert any("undeployed" in item for item in outcome.excludes)
        assert any("holidays" in item for item in outcome.excludes)
        # The fifth arrived with feature 009, which took the cash out of a tax charge: the
        # charge is still netted where it accrued, and the deadline that would date it lives
        # in declarations a tuple does not carry. It says which way the approximation errs,
        # because "approximate" without a direction is not a statement a reader can use.
        assert any("when the tax is paid" in item for item in outcome.excludes)


class TestAScopeStatementIsCheckedAgainstTheBehaviourItDescribes:
    """SC-009's teeth. A scope statement asserted only against itself is a decoration.

    Every claim below is read **off the outcome's own words** and then checked against what
    the pipeline actually did with the same inputs. The undeployed clause is here because it
    was false once: the rate charged the remainder as a total loss while three statements,
    this set among them, said it was measured on the money actually invested.
    """

    def test_the_undeployed_clause_is_true_of_the_rate(self) -> None:
        # The clause says the rate is measured on **the money actually invested**. Two things
        # have to hold for that to be more than a phrase, and the second needs a way in that
        # charges: over the shipped free route the outlay and the arriving amount are one
        # number, and "netted off the outlay" is then indistinguishable from "measured on what
        # arrived". So every run below crosses a flat-fee route.
        #
        #   100.00 flat, 10 100.00 sent -> 10 000.00 arrives -> 10 units, nothing over
        #   100.00 flat, 10 500.00 sent -> 10 400.00 arrives -> 10 units, 400.00 over
        #   500.00 flat, 10 500.00 sent -> 10 000.00 arrives -> 10 units, nothing over
        #
        # A remainder must move the figure by nothing (first against second: same money
        # invested, same holding), and what left the stream must move it (first against third:
        # same arriving amount, same holding, 400.00 more spent to get there).
        exact = _outcome(10_100.0, flat=100.0)
        stranded = _outcome(10_500.0, flat=100.0)
        dearer = _outcome(10_500.0, flat=500.0)
        clause = next(item for item in stranded.excludes if "undeployed" in item)
        assert "money actually invested" in clause
        assert stranded.undeployed is not None
        assert exact.undeployed is None
        assert dearer.undeployed is None
        rates = [outcome.implied_rate for outcome in (exact, stranded, dearer)]
        assert all(isinstance(rate, NominalRate) for rate in rates)
        values = [rate.value for rate in rates if isinstance(rate, NominalRate)]
        assert values[0] == values[1]
        assert values[2] < values[0]

    def test_a_constrained_way_names_itself_on_the_outcome(self) -> None:
        # `RampCost` says eight things about a way in; four reach the outcome and two more are
        # dropped with a recorded reason. These two were dropped in silence, so a route the
        # owner declared *constrained* produced a figure with nothing on its face saying so --
        # and `RampCost.status`'s own docstring calls it "the field a reader scans to decide
        # whether to trust the figure beside it". Both sides, because a status about the way
        # in alone on a round-trip figure is a half-truth.
        for route_id, side in (
            (fixtures.DOMESTIC_IN, "route_in"),
            (fixtures.DOMESTIC_OUT, "route_out"),
        ):
            outcome = _outcome(
                registries=fixtures.with_route(fixtures.shipped(), route_id, status="constrained")
            )
            assert outcome.routes.status == "constrained", side
            assert outcome.routes.constrained == (side,), side

    def test_an_unconstrained_round_trip_says_that_instead(self) -> None:
        # Otherwise the field above would be one that always warns, which is one nobody reads.
        outcome = _outcome()
        assert outcome.routes.status == "open"
        assert outcome.routes.constrained == ()

    def test_the_disruption_probability_is_the_largest_single_leg_on_either_way(self) -> None:
        # The second field dropped in silence. Both shipped domestic legs declare 1%, and the
        # figure is the largest of them rather than their product: multiplying two
        # independent-looking probabilities would invent a joint distribution nobody declared.
        # Raising one leg to 5% moves it and raising the other does not, which is what says
        # the maximum is a maximum and not a coincidence of equal inputs.
        assert _outcome().routes.disruption_probability == 0.01
        for route_id in (fixtures.DOMESTIC_IN, fixtures.DOMESTIC_OUT):
            raised = _outcome(
                registries=fixtures.with_leg(
                    fixtures.shipped(), route_id, disruption_probability=0.05
                )
            )
            assert raised.routes.disruption_probability == 0.05, route_id

    def test_the_latency_clause_is_true_of_the_span(self) -> None:
        # `accounts_for` says settlement latency is inside the span the rate is measured over.
        # The shipped way out declares three days, so the span has to end three days after the
        # instrument last released anything -- not on the release date.
        outcome = _outcome()
        clause = next(item for item in outcome.accounts_for if "latency" in item)
        assert "inside the span" in clause
        last = outcome.arrivals[-1]
        assert outcome.span.end == last.arrived_on
        assert last.arrived_on > last.released_on


class TestNoFigureIsReportedWithoutItsScope:
    """The "verified across the whole output, not sampled" clause."""

    def test_every_field_of_the_outcome_is_classified(self) -> None:
        fields = {field.name for field in dataclasses.fields(TupleOutcome)}
        assert fields == CLASSIFIED

    def test_every_member_of_the_closed_part_set_is_actually_reported(self) -> None:
        # The claim `Part` cannot make about itself: a closed set is only worth closing if the
        # builder fills every member. A part quietly dropped would leave a term of the round
        # trip with no line at all, and the total a reader adds up would still look right.
        assert {line.part for line in _outcome().parts} == set(get_args(Part))

    def test_every_part_names_the_call_that_produced_it(self) -> None:
        # The mechanical half of "the join invents nothing": a part with no named producer is
        # a figure this module computed, and there is nowhere on the record to write one.
        for line in _outcome().parts:
            assert line.source.strip()

    def test_the_rate_is_a_labelled_type_rather_than_a_bare_float(self) -> None:
        # `NominalRate` says the figure is nominal, which is half of what `excludes` says in
        # words. A bare float would let a real rate be assigned into the same slot with no
        # error anywhere -- the mistake feature 001's `nominal_ytm` mislabelling already made
        # once in this repository.
        rate = _outcome().implied_rate
        assert isinstance(rate, NominalRate | RateNotComparable)

    def test_a_one_way_figure_is_never_presented_where_a_round_trip_belongs(self) -> None:
        # The outcome holds no ramp cost record at all: what it reports is the amount that
        # reached a spendable endpoint, which is the far end of the whole journey. There is no
        # field for a one-way figure to be promoted into.
        annotations = {field.name: str(field.type) for field in dataclasses.fields(TupleOutcome)}
        assert not any("OneWayCost" in text for text in annotations.values())
        assert not any("RoundTripCost" in text for text in annotations.values())

    def test_a_figure_resting_on_an_assumption_says_which(self) -> None:
        # FR-025: figures resting on the continuation assumption are marked assumption-driven.
        # The shipped OVDP's proceeds reach the endpoint before this horizon ends, so the
        # assumption bites and is named.
        outcome = _outcome()
        assert outcome.span.end < outcome.horizon.end
        assert any("hold_as_cash" in item for item in outcome.rests_on)

    def test_a_figure_that_does_not_rest_on_it_does_not_claim_to(self) -> None:
        # A `rests_on` that is always the same is one a reader stops reading, so the
        # continuation statement appears only where the instrument really does terminate
        # early. Here the horizon ends the day the money arrives.
        outcome = evaluate(
            fixtures.hurdle_tuple(),
            amount=fixtures.AMOUNT,
            horizon=fixtures.DateRange(start=fixtures.ISSUE_DATE, end=fixtures.date(2028, 1, 20)),
            as_of=fixtures.AS_OF,
            continuation=fixtures.HOLD_AS_CASH,
            registries=fixtures.shipped(),
        )
        assert isinstance(outcome, TupleOutcome), outcome
        assert outcome.span.end == outcome.horizon.end
        assert not any("hold_as_cash" in item for item in outcome.rests_on)
