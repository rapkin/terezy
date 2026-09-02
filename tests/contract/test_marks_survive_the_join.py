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

import dataclasses
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import replace
from datetime import date
from typing import Final

import pytest

from terezy.core.decision.compare import compare
from terezy.core.decision.tuple_outcome import Registries, evaluate
from terezy.core.instruments.fund import FundDeclaration
from terezy.core.instruments.interface import InstrumentDeclaration
from terezy.core.primitives import provenance as prov
from terezy.core.primitives import staleness as stale
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.staleness import ObservationKind
from terezy.core.results.tuple import Comparison, Tuple, TupleOutcome
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


def _verified_unless(provenance: Provenance, *, verified: bool) -> Provenance:
    """Verified, unless this is the part under test.

    ``[instrument.constraints]`` used to be verified **unconditionally** here, outside the
    switch, and that line was dead in the way that matters: it made the instrument part's
    unverified case pass while one of that part's two tables was always clean. It was also
    the evidence -- a fixture nobody could make dirty is a fixture nothing is checking.
    """
    return _all_verified(provenance) if verified else provenance


def _aged(source: SourceRef) -> SourceRef:
    """Read long ago and never checked since -- the only pairing that is actually stale.

    A source ages from the later of its two dates, so backdating the retrieval of a value
    verified last month changes nothing.
    """
    return replace(source, retrieved_on=VERY_OLD, verified_on=None)


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
    stale_price: bool = False,
    stale_instrument: bool = False,
    stale_nav: bool = False,
) -> Registries:
    """The shipped registry with everything verified except the named part.

    ``None`` verifies everything, which is the control: without it the whole battery could
    pass on a join that never propagated anything, because the shipped repository has no
    verified value in it at all.

    ``stale_price`` backdates the **venue quote** rather than a route leg, because that is the
    one declared value this feature added and the one whose ageing had nowhere to go: a leg
    was aged by 002's costing long before the join existed.
    """
    registries = fixtures.declared()
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
    if stale_nav:
        fund = registries.funds[fixtures.MILTECH]
        registries = replace(
            registries,
            funds={
                **registries.funds,
                fixtures.MILTECH: replace(
                    fund,
                    nav_per_unit=replace(
                        fund.nav_per_unit,
                        provenance=prov.of(
                            _aged(source) for source in fund.nav_per_unit.provenance.sources
                        ),
                    ),
                ),
            },
        )
    declared = registries.instruments[fixtures.OVDP]
    instrument_verified = unverified_part != "instrument"
    terms = replace(
        declared.terms,
        provenance=prov.of(_aged(source) for source in declared.terms.provenance.sources)
        if stale_instrument
        else _all_verified(declared.terms.provenance)
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
    quote = access.quote
    assert quote is not None
    price = quote.price
    if stale_price:
        price = replace(
            price, provenance=prov.of(_aged(source) for source in price.provenance.sources)
        )
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
                    provenance=_verified_unless(
                        declared.constraints.provenance, verified=instrument_verified
                    ),
                    min_ticket=replace(
                        declared.constraints.min_ticket,
                        provenance=_verified_unless(
                            declared.constraints.min_ticket.provenance,
                            verified=instrument_verified,
                        ),
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
                access,
                quote=replace(
                    quote,
                    price=price
                    if stale_price
                    else replace(price, provenance=_all_verified(price.provenance)),
                ),
            ),
        },
    )


def _fund() -> Tuple:
    """A MilTech tuple: the other declaration kind, and the one whose NAV nothing aged."""
    return fixtures.fund_tuple(
        fixtures.MILTECH, exit_on=fixtures.MILTECH_EXIT, yield_point=fixtures.MILTECH_POINT
    )


def _outcome(registries: Registries, candidate: Tuple | None = None) -> TupleOutcome:
    outcome = evaluate(
        candidate if candidate is not None else fixtures.hurdle_tuple(),
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
    """FR-019's other half, and 002's FR-025/FR-028 rules unchanged.

    This half held for **two of the four parts** for a whole feature while the provenance half
    held for all four, and the shape of the gap is worth keeping: a mark is a property of a
    citation and survives being merged, while a staleness threshold was a property of a
    *record* and did not. By the time a tuple's provenance is a union across five tables, no
    record is in hand -- so the bond's terms, its constraints, the tax pack's rates and every
    table of a fund's declaration reached the outcome unaged, and nothing said so.
    """

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

    def test_every_source_the_outcome_carries_was_aged(self) -> None:
        # The guard on `SourceRef.kind`'s empty default: a citation the loader forgot to stamp
        # shows up here as a source nobody could age, which is the silent permissive default
        # FR-028 forbids.
        #
        # It proves nothing about **completeness**, and an earlier version of this test
        # claimed it did -- both of its sides came from `provenance`, so it could only ever
        # show that one set self-consistent. Completeness is the class below, whose two sides
        # come from different places.
        for candidate in (fixtures.hurdle_tuple(), _fund()):
            outcome = _outcome(_registries(unverified_part=None), candidate)
            behind = {source.id for source in outcome.provenance.sources}
            assert behind
            assert behind == set(outcome.staleness.assessed), candidate.instrument_id

    def test_a_stale_bond_term_reaches_the_outcome(self) -> None:
        # The coupon rate and the face value size every flow in the schedule. Before the kind
        # travelled with the citation there was no way to age them at all: `[instrument.terms]`
        # declares a threshold, the loader validated it, and `BondTerms` had nowhere to put it.
        registries = _registries(unverified_part=None, stale_instrument=True)
        outcome = _outcome(registries)
        assert stale.any_stale(outcome.staleness)
        assert any(
            item.source_id.startswith("instruments/ovdp_synthetic_a")
            for item in outcome.staleness.stale
        )

    def test_a_stale_fund_nav_reaches_the_outcome(self) -> None:
        # The number the whole outcome is sized from. `project_fund` takes no ageing argument
        # and never has; the join ages the sources the projection rests on instead, which is
        # the only place that can see all of them at once.
        registries = _registries(unverified_part=None, stale_nav=True)
        outcome = _outcome(registries, _fund())
        assert stale.any_stale(outcome.staleness)
        assert any(
            item.source_id.startswith("instruments/inzhur_miltech")
            for item in outcome.staleness.stale
        )

    def test_the_venue_quote_is_aged_too_and_not_merely_carried(self) -> None:
        # The value this feature added, and the one with no earlier owner to age it: the
        # purchase is sized from the quote, and nothing in a projection ever sees it. A quote
        # read in 2020 and never checked since is past every declared threshold, and an
        # outcome that reported it fresh would be resting a whole comparison on a price
        # nobody has looked at in six years.
        outcome = _outcome(_registries(unverified_part=None, stale_price=True))
        assert stale.any_stale(outcome.staleness)
        assert any(item.source_id.startswith("access/") for item in outcome.staleness.stale)

    def test_a_fresh_quote_is_named_in_assessed_rather_than_skipped(self) -> None:
        # "Nothing was aged" and "everything was aged and nothing was stale" are different
        # claims, and before the quote was merged in it was the first one wearing the second
        # one's green tick.
        outcome = _outcome(_registries(unverified_part=None))
        assert any(item.startswith("access/") for item in outcome.staleness.assessed)
        assert not stale.any_stale(outcome.staleness)

    def test_the_thresholds_are_the_declared_ones(self) -> None:
        # Stated as an assertion rather than assumed: the verdict above is only meaningful if
        # the kind the legs name is a kind somebody declared a threshold for.
        registries = fixtures.declared()
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


CANNOT_MOVE_A_FIGURE: Final[frozenset[str]] = frozenset(
    {
        # Recorded context for the declared yield, and nothing accrues from it
        # (`instruments.fund`, owner decision B). It reaches `rests_on` as words.
        "instrument.fee_fact",
    }
)
"""Sourced tables a tuple's outcome deliberately does **not** rest on.

Closed, and named one by one with the reason, because the alternative is a subtraction
nobody has to justify. A sourced table added to a declaration fails the partition below until
somebody decides which side of this line it is on -- which is the friction that would have
caught `[instrument.constraints]` on the commit that made it load-bearing.
"""


class TestEveryDeclaredTableTheTupleReadReachesTheOutcome:
    """FR-019's completeness half, partitioned against a **second** source of truth.

    The two sides are derived differently on purpose. One is `TupleOutcome.provenance`. The
    other is a walk over the declarations the tuple *names* -- its instrument, its access
    entry, the tax classes that instrument references, and the routes at both ends -- reached
    through the registry rather than through anything the join produced. A guard whose two
    sides come from one place can only ever prove that place self-consistent, and the version
    of it that did exactly that is what let two load-bearing tables go unmarked:

    * `[instrument.constraints]`, whose minimum ticket and buyable increment decide how many
      units were bought and therefore every figure. **This feature made them load-bearing** --
      nothing sized a purchase from them before `_acquire` -- and nothing marked them;
    * a fund's `[instrument.liquidity.*]`, whose settlement delay moves the arrival date and
      the rate: 0 to 30 business days moves the shipped MilTech tuple from 0.17578 to 0.16553.

    A years-stale minimum ticket was therefore invisible on the outcome, which is the
    top-severity shape -- a figure resting on an input nobody has checked, saying nothing.
    """

    def _sources(self, value: object, seen: set[int]) -> Iterator[SourceRef]:
        """Every citation reachable from a declaration, without naming a single field."""
        if id(value) in seen:
            return
        seen.add(id(value))
        if isinstance(value, SourceRef):
            yield value
        elif isinstance(value, str | bytes):
            return
        elif dataclasses.is_dataclass(value) and not isinstance(value, type):
            for field in dataclasses.fields(value):
                yield from self._sources(getattr(value, field.name), seen)
        elif isinstance(value, Mapping):
            for item in value.values():
                yield from self._sources(item, seen)
        elif isinstance(value, Iterable):
            for item in value:
                yield from self._sources(item, seen)

    def _declared(self, registries: Registries, candidate: Tuple) -> set[str]:
        """Every sourced table of every declaration this tuple names, read off the registry."""
        fund = registries.funds.get(candidate.instrument_id)
        instrument: FundDeclaration | InstrumentDeclaration = (
            fund if fund is not None else registries.instruments[candidate.instrument_id]
        )
        named: list[object] = [
            instrument,
            registries.access[candidate.instrument_id],
            *(registries.tax_classes[class_id] for class_id in instrument.tax_classes.values()),
            registries.routes[fixtures.DOMESTIC_IN],
            registries.routes[fixtures.DOMESTIC_OUT],
        ]
        seen: set[int] = set()
        return {source.id for item in named for source in self._sources(item, seen)}

    @pytest.mark.parametrize("candidate", [fixtures.hurdle_tuple(), _fund()], ids=["bond", "fund"])
    def test_the_declared_tables_partition_into_carried_and_classified(
        self, candidate: Tuple
    ) -> None:
        registries = _registries(unverified_part=None)
        declared = self._declared(registries, candidate)
        carried = {source.id for source in _outcome(registries, candidate).provenance.sources}
        assert declared, "the walk reached no declaration, so it proves nothing"
        missing = sorted(
            table
            for table in declared - carried
            if not any(excused in table for excused in CANNOT_MOVE_A_FIGURE)
        )
        assert not missing, (
            f"declared tables the outcome rests on and does not carry: {missing}. Either merge "
            "their provenance in `_assemble`, or classify them in CANNOT_MOVE_A_FIGURE with "
            "the reason no figure can move when they change."
        )

    @pytest.mark.parametrize("candidate", [fixtures.hurdle_tuple(), _fund()], ids=["bond", "fund"])
    def test_the_classification_is_not_a_blanket(self, candidate: Tuple) -> None:
        # The other half: an excuse list that excused everything would make the partition
        # vacuous. Most of what a tuple names has to be carried, and here it is all but one.
        registries = _registries(unverified_part=None)
        declared = self._declared(registries, candidate)
        carried = {source.id for source in _outcome(registries, candidate).provenance.sources}
        assert len(declared & carried) >= len(declared) - 2
