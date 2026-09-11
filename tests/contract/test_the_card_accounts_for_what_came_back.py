"""The served records account for ``reaches``, for every evaluated candidate (FR-030, SC-001).

**Two links rather than one**, because ``reaches == sum of the flows`` is false and not by a
rounding: the tax is netted before a percentage exit fee, a date netting to exactly zero leaves
the release series, and the purchase is not a release. The card states that disagreement rather
than hiding it (FR-019), and what is asserted here is the chain that does hold:

1. each served release's ``sent`` is the sum of the served flows on that date, net of the tax
   charged on each, the purchase excluded; and
2. ``reaches`` is the sum of the served releases' ``arrived`` plus the remainder's ``reached``
   where the outcome's own journey says it came home.

Every ranked candidate of the owner's declared question, none skipped, on all three arms. The
tolerance is the imported project one -- a suite inventing its own would be asserting that the
figures are close rather than that the accounting holds.
"""

from __future__ import annotations

import pytest

from terezy.core.ledger.events import EventKind
from terezy.core.primitives import money
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.card import BondArm, CandidateProjection, CashArm, FundArm, NotStated
from terezy.core.results.ramp import OneWayCost, WayOutCost
from terezy.core.results.tuple import RemainderCameHome, TupleOutcome, UndeployedCash
from tests.served_projections import served

pytestmark = pytest.mark.contract

EVALUATED = 69
"""How many candidates the shipped question evaluates, measured 2026-09-11.

Pinned so a registry change that stopped a whole arm being reached cannot leave the loops below
green over a smaller population -- which is the one way an accounting assertion passes for the
wrong reason.
"""


def test_the_population_is_the_whole_evaluated_set_on_every_arm() -> None:
    pairs = served()
    assert len(pairs) == EVALUATED
    assert {type(projection.arm) for _, projection in pairs} == {BondArm, FundArm, CashArm}


def test_each_release_is_the_flows_of_its_date_net_of_their_tax() -> None:
    checked = 0
    for outcome, projection in served():
        for release in projection.releases:
            netted = money.total(
                [
                    flow.net
                    for flow in projection.flows
                    if flow.occurred_on == release.released_on
                    and flow.kind is not EventKind.PURCHASE
                ],
                release.way_out.sent.currency,
            )
            assert is_close(netted.amount, release.way_out.sent.amount), (
                f"{outcome.projection_key}: the flows of {release.released_on} net to "
                f"{netted.amount!r} and the release sent {release.way_out.sent.amount!r}"
            )
            checked += 1
    assert checked >= EVALUATED, "at least one release per candidate, or this is vacuous"


def test_reaches_is_the_releases_that_arrived_plus_the_remainder_that_came_home() -> None:
    for outcome, projection in served():
        arrived = [release.way_out.arrived for release in projection.releases]
        home = _remainder(outcome)
        total = money.total(arrived if home is None else [*arrived, home], outcome.reaches.currency)
        assert is_close(total.amount, outcome.reaches.amount), outcome.projection_key


def test_the_remainder_that_came_home_is_served_its_own_charge_and_wait() -> None:
    """Its leg is charged and dated like any other, and it was on no served record.

    63 of the 69 evaluated candidates leave a remainder that comes home (measured 2026-09-12),
    so a timeline drawing its arrival with no declared wait beside it, and a waterfall with no
    bar for what that journey was charged, were the live cases rather than the edge ones.
    """
    home = 0
    for outcome, projection in served():
        charged = projection.remainder_way_out
        if _remainder(outcome) is None:
            assert isinstance(charged, NotStated), outcome.projection_key
            continue
        assert not isinstance(charged, NotStated), outcome.projection_key
        assert charged.latency_days >= 0
        assert outcome.undeployed is not None
        assert charged.sent == outcome.undeployed.amount
        home += 1
    assert home == 63


def test_a_release_is_served_for_every_arrival_the_outcome_reports() -> None:
    """The link between the two: a release the card did not draw would break link 2 silently."""
    for outcome, projection in served():
        assert [release.released_on for release in projection.releases] == [
            arrival.released_on for arrival in outcome.arrivals
        ], outcome.projection_key


def test_a_flows_mark_is_the_union_of_the_marks_it_was_netted_from() -> None:
    """SC-002 in the form that can be false: the netting must not drop a source.

    ``net = gross - tax`` is where a mark would be lost, and losing one is the top-severity
    defect Principle I names. Asserting merely that a provenance record is present would pass
    on an empty one, which is what a dropped mark looks like.
    """
    for outcome, projection in served():
        for flow in projection.flows:
            assert {source.id for source in flow.net.provenance.sources} == {
                source.id for source in flow.gross.provenance.sources
            } | {source.id for source in flow.tax.provenance.sources}, outcome.projection_key


def test_every_charge_and_every_route_figure_cites_something() -> None:
    """The amounts that rest on a declaration, and every one of them does.

    A flow's own ``gross`` is deliberately **not** in this sweep: a balance's purchase is the
    amount itself and rests on no observation, which is a real state and not a lost mark. Nor is
    a route that walked no leg -- an entry by identity charges nothing and cites nothing, and its
    empty segment list is what says so. What tells either apart from a dropped mark is the test
    above.
    """
    walked = 0
    for outcome, projection in served():
        for charge in projection.charges:
            assert charge.provenance.sources, outcome.projection_key
        costs: list[OneWayCost | WayOutCost] = [
            projection.way_in.one_way,
            *(release.way_out for release in projection.releases),
        ]
        for cost in costs:
            if not cost.by_segment:
                continue
            assert cost.provenance.sources, outcome.projection_key
            walked += 1
    assert walked >= EVALUATED, "no declared corridor was costed, so this would be vacuous"


def test_a_zero_charge_that_cites_an_exemption_is_distinguishable_from_one_that_does_not() -> None:
    """Required test **E11**, over the shipped registry rather than a fixture.

    Both cases are real on it: every charge the exempt classes strike is a zero carrying its
    exemption's citation, and every purchase row's zero rests on no source because no rule ran.
    """
    cited = [
        charge
        for _, projection in served()
        for charge in projection.charges
        if charge.total.amount == 0.0 and charge.provenance.sources
    ]
    uncited = [
        flow
        for _, projection in served()
        for flow in projection.flows
        if flow.tax.amount == 0.0 and not flow.tax.provenance.sources
    ]
    assert cited, "no cited zero reached a card, so E11's first case is untested"
    assert uncited, "no uncited zero reached a card, so E11's second case is untested"
    assert all(charge.tax_class_id for charge in cited)


def test_the_projection_served_is_the_one_that_produced_the_outcome() -> None:
    """Plan Finding 3's claim, asserted: the endpoint re-evaluates and gets the same run.

    A cache would make this trivially true and would be state in the layer whose claim is that
    it holds none; re-evaluating makes it a real question, and this is the answer.
    """
    for outcome, projection in served():
        assert projection.projection_key == outcome.projection_key
        assert projection.instrument_id == outcome.key.instrument_id
        assert projection.purchase.purchased_on >= outcome.span.start


def _remainder(outcome: TupleOutcome) -> Money | None:
    """What the remainder brought home, where it came home. On the outcome, never duplicated."""
    match outcome.undeployed:
        case UndeployedCash(journey=RemainderCameHome(reached=reached)):
            return reached
    return None


def test_the_served_record_does_not_repeat_the_outcome() -> None:
    """The contract's other half: what is on the outcome is read there and carried once."""
    fields = set(CandidateProjection.__dataclass_fields__)
    assert not fields & {"reaches", "implied_rate", "span", "horizon", "undeployed", "key"}
