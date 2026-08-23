"""SC-009 and FR-014: every reported figure states what it accounts for and what it excludes.

Feature 001's hurdle rate carries an ``excludes`` set that admits, in the output's own words,
that it ignores funding and exit route costs. That admission is the honest form of an
incomplete figure, and this feature's job was to move both items from one set to the other.
So the first class checks the **move**: what 001 excluded, a tuple outcome accounts for, and
neither set is a decoration nobody maintains.

The second class is the "not sampled" clause. It walks every field of every outcome and
refusal this suite can produce and requires each to be classified -- a figure, a statement of
scope, a key, a mark. A field nobody classified is a figure nobody labelled, and the closed
classification is deliberate friction: adding one to the record fails this module until a
reader decides which kind of thing it is.
"""

from __future__ import annotations

import dataclasses
from typing import Final, get_args

import pytest

from terezy.core.decision.tuple_outcome import evaluate
from terezy.core.primitives.rates import NominalRate
from terezy.core.results.hurdle import EXCLUDES as HURDLE_EXCLUDES
from terezy.core.results.tuple import (
    ACCOUNTS_FOR,
    EXCLUDES,
    Part,
    RateNotComparable,
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
        # Money that made the trip and bought nothing. Reported, and outside the rate.
        "undeployed",
        # The scope statements this module is about.
        "accounts_for",
        "excludes",
        "rests_on",
        # The key, all five terms of it.
        "key",
        "risk_class",
        # Marks travel with every figure; they are not figures.
        "provenance",
        "staleness",
    }
)
"""Every field of :class:`TupleOutcome`, classified. See the module docstring on why closed."""


def _outcome() -> TupleOutcome:
    outcome = evaluate(
        fixtures.hurdle_tuple(),
        amount=fixtures.AMOUNT,
        horizon=fixtures.DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END),
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=fixtures.shipped(),
    )
    assert isinstance(outcome, TupleOutcome), outcome
    return outcome


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

    def test_it_states_that_waiting_is_inside_the_span(self) -> None:
        # The owner's decision of 2026-08-22, on the record's face: a reader comparing this
        # rate against a contractual yield-to-maturity is comparing two different spans, and
        # nothing else in the output would tell them so.
        assert any("latency" in item for item in _outcome().accounts_for)

    def test_it_states_the_three_things_it_still_leaves_out(self) -> None:
        outcome = _outcome()
        assert any("inflation" in item for item in outcome.excludes)
        assert any("risk class" in item for item in outcome.excludes)
        assert any("undeployed" in item for item in outcome.excludes)


class TestNoFigureIsReportedWithoutItsScope:
    """The "verified across the whole output, not sampled" clause."""

    def test_every_field_of_the_outcome_is_classified(self) -> None:
        fields = {field.name for field in dataclasses.fields(TupleOutcome)}
        assert fields == CLASSIFIED

    def test_the_outcome_carries_both_sets_and_neither_is_empty(self) -> None:
        outcome = _outcome()
        assert outcome.accounts_for == ACCOUNTS_FOR
        assert outcome.excludes == EXCLUDES
        assert outcome.accounts_for
        assert outcome.excludes

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
