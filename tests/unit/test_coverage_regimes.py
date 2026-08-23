"""Coverage is stated per regime, and never blended. **SC-007, SC-018.**

FR-013: *every verdict, deficit and blocked-pair count MUST be stated per regime. A link present
in one regime and absent in another MUST be reported as exactly that, and no blended
cross-regime verdict or count may exist anywhere in the output.* FR-014 adds that the same
missing declaration in two regimes must be recognizably **one** declaration, with its count
stated per regime rather than summed.

**Why blending would be the worst available failure here.** Feature 002 already made regimes
first-class for costing: a scenario runs in one regime and its figures are conditional on the
owner's belief about when the war ends. An audit that reported a corridor as covered *because it
exists in one regime* would tell the owner that a destination is comparable while the scenario
he is actually running silently cannot reach it. That is the confident-but-wrong summary this
project exists to refuse, and it would be invisible -- every number in the report would still be
a real number about a real declaration.

**Why the missing declaration carries no regime field** (research.md D8). FR-014 wants two
identical holes in two regimes to be recognizably one observation, because going out and
observing the corridor is *one* errand. Value equality between two frozen records is the
cheapest possible form of "recognizably one", and a regime field would destroy it -- leaving
every reader to normalise the records by hand before they could tell. What the regime buys is
the *count*, and that is carried as ``(regime_id, count)`` pairs on
:class:`~terezy.core.results.coverage.Observation`, which has no field a sum could live in.

The registry: ``mono`` -> ``broker`` in, ``broker`` -> ``mono`` out. ``wartime`` believes in the
exit; ``normalized`` does not. So one pair is ready in one regime and not in the other, and the
missing exit is one declaration blocking one pair in exactly one of the two.
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from terezy.core.results.coverage import (
    IMPLICIT_REGIME_ID,
    NO_EXIT_DECLARED,
    CoverageReport,
    NotReady,
    Observation,
    Ready,
)
from terezy.core.routes.coverage import coverage
from tests.coverage_registries import UAH, USD, keyed, regime, route, spendable, stream, venue

VENUES = keyed([venue("mono", UAH), venue("broker", USD), venue("fund", UAH)])
STREAMS = keyed([stream("salary_uah", UAH, "mono")])

IN_ROUTE = route(
    "in_mono_broker",
    origin="mono",
    destination="broker",
    direction="inbound",
    from_ccy=UAH,
    to_ccy=USD,
)
OUT_ROUTE = route(
    "out_broker_mono",
    origin="broker",
    destination="mono",
    direction="exit",
    from_ccy=USD,
    to_ccy=UAH,
)
FUND_ROUTE = route(
    "in_mono_fund", origin="mono", destination="fund", direction="inbound", from_ccy=UAH
)
"""A way in to a destination with no way out, in **both** regimes.

Here so the identical-route-set case below still has something to say. ``mono`` is the declared
spendable endpoint, so its exit half is satisfied by identity and it is never a hole; without
``fund`` a registry whose regimes agree would have no holes at all, and the per-regime counts
the test is about would both be zero.
"""

ROUTES = keyed([IN_ROUTE, OUT_ROUTE, FUND_ROUTE])
SPENDABLE = spendable(("mono", UAH))

REGIMES = keyed(
    [
        regime("normalized", IN_ROUTE.id, FUND_ROUTE.id),
        regime("wartime", IN_ROUTE.id, OUT_ROUTE.id, FUND_ROUTE.id),
    ]
)
"""``wartime`` names the exit and ``normalized`` does not.

Deliberately the counter-intuitive way round -- the *war* regime has the corridor and the
normalized one does not -- so a reader cannot check the assertions below against an intuition
about which world ought to be better connected. The report states what the route sets say.
"""


def _report(regimes: object = REGIMES) -> CoverageReport:
    produced = coverage(
        venues=VENUES,
        streams=STREAMS,
        routes=ROUTES,
        regimes=regimes,  # type: ignore[arg-type]
        spendable=SPENDABLE,
    )
    assert isinstance(produced, CoverageReport), produced
    return produced


def _verdict(report: CoverageReport, regime_id: str, venue_id: str) -> Ready | NotReady:
    block = next(block for block in report.regimes if block.regime_id == regime_id)
    return next(v for v in block.verdicts if v.destination.venue_id == venue_id)


def test_a_route_in_one_regime_and_not_the_other_yields_two_different_verdicts() -> None:
    """**SC-007's first half, FR-013.** The same pair, two regimes, two answers."""
    report = _report()
    assert [block.regime_id for block in report.regimes] == ["normalized", "wartime"]
    assert all(block.source == "declared" for block in report.regimes)

    in_wartime = _verdict(report, "wartime", "broker")
    assert isinstance(in_wartime, Ready)
    assert isinstance(in_wartime.exits, tuple), "broker is not itself a spendable endpoint"
    assert [relied.route_id for relied in in_wartime.exits] == [OUT_ROUTE.id]

    in_normalized = _verdict(report, "normalized", "broker")
    assert isinstance(in_normalized, NotReady)
    assert tuple(d.kind for d in in_normalized.deficits) == (NO_EXIT_DECLARED,)


def test_each_block_audits_only_its_own_route_set() -> None:
    """The structural half of FR-013: a block cannot see a corridor its regime excludes.

    ``route_ids`` is what the block audited, and it is the regime's set rather than every
    declared route. Without that the two verdicts above could only differ by accident.
    """
    report = _report()
    by_id = {block.regime_id: block for block in report.regimes}
    assert by_id["normalized"].route_ids == ("in_mono_broker", "in_mono_fund")
    assert by_id["wartime"].route_ids == ("in_mono_broker", "in_mono_fund", "out_broker_mono")


def test_no_blended_verdict_and_no_summed_count_exists_anywhere() -> None:
    """**SC-007's second half, FR-013, FR-014.**

    Two claims. First, every verdict lives inside exactly one regime block -- there is no
    top-level verdict list, so a blended verdict has nowhere to be. Second, every cross-regime
    count in ``to_observe`` is a per-regime pair and there is **no total**: asserted on the
    record's own field names, so it stays true of every report rather than of this one.
    """
    report = _report()
    assert {field.name for field in fields(CoverageReport)} == {
        "audited",
        "regimes",
        "to_observe",
        "enforcement",
    }
    assert {field.name for field in fields(Observation)} == {"missing", "blocked_by_regime"}
    for observation in report.to_observe:
        assert [regime_id for regime_id, _ in observation.blocked_by_regime] == [
            "normalized",
            "wartime",
        ]


def test_the_shared_missing_declaration_is_one_item_with_per_regime_counts() -> None:
    """**SC-007's third half, FR-014, research.md D8.** One errand, two consequences.

    The missing exit from ``broker`` blocks one pair in ``normalized`` and none in ``wartime``,
    and it appears **once** in ``to_observe`` carrying both facts. A zero is stated rather than
    omitted: a declaration listed under one regime and silently absent from the other would
    leave a reader unable to tell "blocks nothing there" from "was not audited there".
    """
    report = _report()
    missing_exit = next(
        observation
        for observation in report.to_observe
        if observation.missing.direction == "exit" and observation.missing.origin_venue == "broker"
    )
    assert missing_exit.blocked_by_regime == (("normalized", 1), ("wartime", 0))

    # One record, not two: the same hole in two regimes is value-equal, which is what makes it
    # recognizably one observation without any consumer normalising anything.
    assert (
        sum(1 for observation in report.to_observe if observation.missing == missing_exit.missing)
        == 1
    )


def test_two_regimes_naming_identical_route_sets_still_produce_two_blocks() -> None:
    """The spec's edge case: agreement today is a fact, not an identity.

    Deduplicating them would state that the two regimes are the same thing, which is a claim
    about the future rather than about the declarations -- and the day one of them gains a
    corridor, the report would have to un-merge a block a reader had learned to expect.
    """
    identical = keyed(
        [
            regime("normalized", IN_ROUTE.id, OUT_ROUTE.id, FUND_ROUTE.id),
            regime("wartime", IN_ROUTE.id, OUT_ROUTE.id, FUND_ROUTE.id),
        ]
    )
    report = _report(identical)
    assert len(report.regimes) == 2
    normalized, wartime = report.regimes
    assert normalized.regime_id == "normalized"
    assert wartime.regime_id == "wartime"
    # The verdicts themselves are value-equal, and that is right: a verdict carries no regime
    # field, because what a regime contributes is *which block it is stated in*. What must not
    # happen is the two blocks collapsing into one, and they do not.
    assert normalized.verdicts == wartime.verdicts
    assert normalized != wartime

    # And the shared hole is one observation carrying the same count under each regime -- one
    # errand, two consequences that happen to agree today.
    (observation,) = report.to_observe
    assert observation.blocked_by_regime == (("normalized", 1), ("wartime", 1))


def test_with_no_regime_declared_one_implicit_regime_covers_every_route_and_says_so() -> None:
    """**SC-018, FR-015, research.md D14.** The report states what it did, structurally.

    ``source == "implicit"`` is the machine-readable half and the parenthesised id is the
    human-readable one; ``audited.regime_ids`` stays empty, because the owner declared none and
    recording the reserved id there would say he had.
    """
    report = _report({})
    (block,) = report.regimes
    assert block.source == "implicit"
    assert block.regime_id == IMPLICIT_REGIME_ID
    assert block.route_ids == tuple(sorted(ROUTES))
    assert report.audited.regime_ids == ()
    # And it is a real audit rather than a placeholder: the corridor is complete here, because
    # the implicit regime believes in every declared route.
    assert isinstance(_verdict(report, IMPLICIT_REGIME_ID, "broker"), Ready)


@pytest.mark.parametrize("regimes", [REGIMES, {}])
def test_the_report_is_deterministic_under_either_regime_source(regimes: object) -> None:
    """FR-016 again, this time across the branch that chooses the regime set.

    Cheap, and it covers the one place a mapping's iteration order could reach the output: the
    implicit block's ``route_ids`` and the declared blocks' order both come from sorting a
    mapping, and sorting is the only thing between them and a report that differs run to run.
    """
    assert _report(regimes) == _report(regimes)
