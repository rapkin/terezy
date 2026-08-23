"""SC-007 and FR-019: the unverified mark reaches the outcome from every one of the four parts.

Principle I's propagation rule is already enforced inside each part. The join is a **new
figure-producing site**, and a join that launders a mark is a top-severity defect: the whole
comparison would read as resting on checked values while one of its terms came from a number
nobody has ever verified.

The battery plants exactly one unverified source in each part in turn -- **with every other
source verified**, so a mark reaching the outcome can only have come from the part under test.
A suite that left the shipped citations alone would pass with the propagation deleted, because
every value in this repository is unverified today.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Final

import pytest

from terezy.core.decision.compare import compare
from terezy.core.decision.tuple_outcome import Registries, evaluate
from terezy.core.primitives import provenance as prov
from terezy.core.primitives import staleness as stale
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.staleness import ObservationKind
from terezy.core.results.tuple import Comparison, TupleOutcome
from terezy.core.routes.legs import Leg, Route
from tests import tuple_registries as fixtures

pytestmark = pytest.mark.contract

CHECKED: Final = date(2026, 8, 1)
"""A verification date. Applied to everything except the one value under test."""

VERY_OLD: Final = date(2020, 1, 1)
"""A retrieval date far enough back that any declared threshold has passed."""

PART_NAMES: Final = ("route in", "instrument", "tax", "route out")


def _verified(source: SourceRef, *, retrieved_on: date | None = None) -> SourceRef:
    return replace(
        source,
        verified_on=CHECKED,
        retrieved_on=retrieved_on or source.retrieved_on,
    )


def _all_verified(provenance: Provenance) -> Provenance:
    return prov.of(_verified(source) for source in provenance.sources)


def _leg(leg: Leg, *, verified: bool, retrieved_on: date | None = None) -> Leg:
    """One leg's citations, verified or not, and optionally aged.

    The two are separate knobs because they are separate claims: a value can be checked
    against a primary source and still be years old, and the outcome has to be able to say so
    -- which it cannot if a fixture can only make a source unverified *and* stale together.
    """
    sources = prov.of(
        replace(
            source,
            verified_on=CHECKED if verified else None,
            retrieved_on=retrieved_on or source.retrieved_on,
        )
        for source in leg.provenance.sources
    )
    return replace(leg, provenance=sources, fee_fixed=replace(leg.fee_fixed, provenance=sources))


def _route(route: Route, *, verified: bool, retrieved_on: date | None = None) -> Route:
    return replace(
        route,
        legs=tuple(_leg(leg, verified=verified, retrieved_on=retrieved_on) for leg in route.legs),
    )


def _registries(
    *,
    unverified_part: str | None,
    stale_route_in: bool = False,
) -> Registries:
    """The shipped registry with everything verified except the named part.

    ``None`` verifies everything, which is the control: without it the whole battery could
    pass on a join that never propagated anything, because the shipped repository has no
    verified value in it at all.
    """
    registries = fixtures.shipped()
    routes = dict(registries.routes)
    for route_id, part in (
        (fixtures.DOMESTIC_IN, "route in"),
        (fixtures.DOMESTIC_OUT, "route out"),
    ):
        routes[route_id] = _route(
            registries.routes[route_id],
            verified=unverified_part != part,
            retrieved_on=VERY_OLD if stale_route_in and part == "route in" else None,
        )
    declared = registries.instruments[fixtures.OVDP]
    instrument_verified = unverified_part != "instrument"
    terms = replace(
        declared.terms,
        provenance=_all_verified(declared.terms.provenance)
        if instrument_verified
        else declared.terms.provenance,
        face_value=replace(
            declared.terms.face_value,
            provenance=_all_verified(declared.terms.face_value.provenance)
            if instrument_verified
            else declared.terms.face_value.provenance,
        ),
    )
    tax_verified = unverified_part != "tax"
    tax_class = registries.tax_classes["ua_government_bond"]
    entries = tuple(
        replace(
            entry, provenance=_all_verified(entry.provenance) if tax_verified else entry.provenance
        )
        for entry in tax_class.rates
    )
    access = registries.access[fixtures.OVDP]
    price = access.price_per_unit
    assert price is not None
    return replace(
        registries,
        routes=routes,
        instruments={
            **registries.instruments,
            fixtures.OVDP: replace(
                declared,
                terms=terms,
                constraints=replace(
                    declared.constraints,
                    provenance=_all_verified(declared.constraints.provenance),
                    min_ticket=replace(
                        declared.constraints.min_ticket,
                        provenance=_all_verified(declared.constraints.min_ticket.provenance),
                    ),
                ),
            ),
        },
        tax_classes={
            **registries.tax_classes,
            "ua_government_bond": replace(tax_class, rates=entries),
        },
        access={
            **registries.access,
            fixtures.OVDP: replace(
                access, price_per_unit=replace(price, provenance=_all_verified(price.provenance))
            ),
        },
    )


def _outcome(registries: Registries) -> TupleOutcome:
    outcome = evaluate(
        fixtures.hurdle_tuple(),
        amount=fixtures.AMOUNT,
        horizon=fixtures.DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END),
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=registries,
    )
    assert isinstance(outcome, TupleOutcome), outcome
    return outcome


class TestOneUnverifiedValueInEachPartMarksTheOutcome:
    """SC-007: 100% of cases, and the control that makes the 100% mean something."""

    def test_with_everything_verified_the_outcome_carries_no_mark(self) -> None:
        # The control. Without it the four assertions below would pass on a join that marked
        # every outcome unconditionally -- and on one that never propagated at all, since the
        # shipped repository has no verified value in it.
        assert not prov.is_unverified(_outcome(_registries(unverified_part=None)).provenance)

    @pytest.mark.parametrize("part", PART_NAMES)
    def test_one_unverified_value_in_one_part_marks_it(self, part: str) -> None:
        assert prov.is_unverified(_outcome(_registries(unverified_part=part)).provenance)

    @pytest.mark.parametrize("part", PART_NAMES)
    def test_the_mark_names_the_source_responsible(self, part: str) -> None:
        # A mark that cannot say which input it rests on is a run-scoped taint flag: cheap,
        # unfalsifiable, and useless to the owner.
        outcome = _outcome(_registries(unverified_part=part))
        assert prov.unverified_sources(outcome.provenance)

    def test_the_mark_reaches_the_comparison_and_not_only_the_figure(self) -> None:
        # US4 scenario 3: the marks are visible in the comparison itself. A ranking whose
        # entries carried marks the ranking could not show would be a ranking a reader trusts
        # more than its inputs deserve.
        comparison = compare(
            (),
            benchmark=fixtures.hurdle_tuple(),
            amount=fixtures.AMOUNT,
            horizon=fixtures.DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END),
            as_of=fixtures.AS_OF,
            continuation=fixtures.HOLD_AS_CASH,
            registries=_registries(unverified_part="instrument"),
        )
        assert isinstance(comparison, Comparison), comparison
        assert prov.is_unverified(comparison.ranked[comparison.benchmark].provenance)


class TestStalenessSurfacesOnTheOutcome:
    """FR-019's other half, and 002's FR-025/FR-028 rules unchanged."""

    def test_a_value_aged_past_its_kinds_threshold_is_reported_stale(self) -> None:
        # The way in's legs are retrieved in 2020 and the question is asked in 2026, which is
        # past every declared threshold. The verdict rides on the outcome, so a comparison
        # cannot rank a figure whose inputs went out of date without saying so.
        #
        # They are left **unverified** as well, and that is forced rather than incidental: a
        # source ages from the later of its retrieval and its verification, so a value checked
        # last month is fresh however old the reading behind it is. Making this one stale means
        # making it unverified, which is the honest pairing anyway.
        outcome = _outcome(_registries(unverified_part="route in", stale_route_in=True))
        assert stale.any_stale(outcome.staleness)
        assert any(
            item.source_id.startswith("routes/inzhur_direct") for item in outcome.staleness.stale
        )

    def test_a_fresh_value_is_assessed_and_found_fresh(self) -> None:
        # Distinguishable from "nothing was aged": the sources are named in `assessed`, so an
        # empty `stale` is a claim only as strong as that list.
        outcome = _outcome(_registries(unverified_part=None))
        assert outcome.staleness.assessed
        assert not stale.any_stale(outcome.staleness)

    def test_the_thresholds_are_the_declared_ones(self) -> None:
        # Stated as an assertion rather than assumed: the verdict above is only meaningful if
        # the kind the legs name is a kind somebody declared a threshold for.
        registries = fixtures.shipped()
        kind = registries.kinds[registries.routes[fixtures.DOMESTIC_IN].legs[0].kind_of_observation]
        assert isinstance(kind, ObservationKind)
        assert kind.staleness_days > 0


class TestTheJoinDoesNotLaunderAMoneyValue:
    """The mechanical half: every amount the join reports came through `money.*`."""

    def test_the_amount_that_reaches_the_endpoint_carries_the_sources_behind_it(self) -> None:
        # `reaches` is a sum of arrivals, each of which is a sum of what the way out returned.
        # A join that rebuilt it as a bare float would produce the same number with an empty
        # provenance, which is the laundering FR-019 puts at top severity.
        outcome = _outcome(_registries(unverified_part="instrument"))
        assert outcome.reaches.provenance.sources
        assert prov.is_unverified(outcome.reaches.provenance)

    def test_every_part_line_carries_provenance_or_is_a_declared_zero(self) -> None:
        # The exit-terms line of a bond is a recorded zero resting on nothing, which is the
        # one legitimate empty provenance: a sum of nothing is not resting on an unverified
        # observation, and claiming otherwise would make the mark universal and meaningless.
        for line in _outcome(_registries(unverified_part="instrument")).parts:
            assert line.amount.provenance.sources or line.amount.amount == 0.0

    def test_a_zero_valued_money_is_still_a_currency_tagged_amount(self) -> None:
        outcome = _outcome(_registries(unverified_part=None))
        for line in outcome.parts:
            assert isinstance(line.amount, Money)
            assert line.amount.currency is not None
