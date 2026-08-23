"""Growing the registry is a data change. **SC-014, SC-019, SC-015.**

FR-024: *a new venue, stream, route or regime declared purely as data MUST appear in the next
report -- as coverage or as a named hole -- with no source-code change.* This is constitution
Principle II applied to the audit itself, and it is the check with the sharpest teeth here: the
report's whole purpose is to direct registry growth, so if growing the registry required a code
change the report would be directing work on itself.

**How "zero lines of source code" is proved**, since the claim is easy to assert and easy to
fake. Every case below copies ``data/`` into a scratch root, edits **files**, resolves the lot
through the ordinary loader, and asserts on the report that comes out -- and the last test
greps this feature's two source modules for a venue, route or stream id, because a branch on an
id is the Principle II violation this design exists to prevent and it is greppable.

SC-015 lives here too, and not by accident. *"A ready verdict resting only on a closed route is
visibly distinct from one resting on an open route, and both are distinct from a hole"* is the
obligation FR-022 leaves behind when it decides that coverage measures **declaration** rather
than availability. A closed corridor is already observed, so telling the owner to go and observe
it would be wrong -- but a report that showed a closed way out as plainly ready would be
overstating what can be compared today. ``rests_on`` is the whole of the difference, and it is
declared data driving it, which is why the case belongs beside the other two.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from terezy.core.primitives.currency import Currency
from terezy.core.results.coverage import (
    EXIT_NOT_SPENDABLE,
    NO_EXIT_DECLARED,
    NO_INBOUND,
    SATISFIED_BY_ARRIVAL,
    SATISFIED_BY_IDENTITY,
    CoverageReport,
    NotReady,
    Ready,
)
from terezy.core.routes.coverage import coverage
from terezy.data.declarations import resolver
from tests.coverage_registries import UAH, USD, keyed, route, spendable, stream, venue

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
COVERAGE_SOURCES = (
    REPO_ROOT / "src" / "terezy" / "core" / "routes" / "coverage.py",
    REPO_ROOT / "src" / "terezy" / "core" / "results" / "coverage.py",
)


def _scratch(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _report_from(root: Path, *, scenario_id: str | None = None) -> CoverageReport:
    """The report the ordinary loading path produces for a data root.

    Through :func:`coverage_from_data_root` rather than by building records by hand, because
    the claim under test is about *declarations reaching the report*, and a test that assembled
    the records itself would skip the half of the journey that could break -- which is what
    ``regimes={}`` used to do here, before the loader could flatten a scenario's regimes at
    all. The regimes now come from the declarations like everything else.

    ``scenario_id`` defaults to ``None`` -- FR-015's implicit regime, every declared route in
    one block -- because that is what every case in *this* module wants: a venue added as data
    must appear as a hole regardless of anybody's belief about the war. The loader itself
    requires the argument (see ``resolve_coverage``); the default here is a fixture's choice,
    stated once. What a declared scenario does to the report is
    ``test_coverage_scenario_scoping.py``'s subject.
    """
    declarations = resolver.coverage_from_data_root(
        root, base_currency=Currency.UAH, scenario_id=scenario_id
    )
    produced = coverage(
        venues=declarations.ramp.venues,
        streams=declarations.ramp.streams,
        routes=declarations.ramp.routes,
        regimes=declarations.regimes,
        spendable=declarations.spendable,
    )
    assert isinstance(produced, CoverageReport), produced
    return produced


def _verdicts(report: CoverageReport) -> dict[tuple[str, str, str], Ready | NotReady]:
    (block,) = report.regimes
    return {
        (v.destination.venue_id, v.destination.currency.value, v.stream_id): v
        for v in block.verdicts
    }


# ---------------------------------------------------------------------------
# SC-014: a new venue, declared as data, appears as named holes
# ---------------------------------------------------------------------------


def test_a_new_venue_with_no_routes_appears_as_named_no_inbound_deficits(tmp_path: Path) -> None:
    """**SC-014, FR-001 ⚙, FR-024.** The hole is visible the moment the venue exists.

    Two currencies on the new venue, so it contributes **two** destinations -- which is the
    destination universe being venue x holdable currency rather than anything derived from the
    routes. A universe built from the routes would give this venue no destinations at all and
    its emptiness would be invisible, which is the failure mode the whole feature exists to
    close.

    Zero lines of source changed: the only edit below is to a ``.toml`` file.
    """
    root = _scratch(tmp_path)
    venues_file = root / "venues.toml"
    venues_file.write_text(
        venues_file.read_text(encoding="utf-8")
        + '\n[[venue]]\nid         = "wise"\nname       = "Wise account (SYNTHETIC FIXTURE)"\n'
        'currencies = ["UAH", "USD"]\n',
        encoding="utf-8",
    )

    before = _verdicts(_report_from(DATA_ROOT))
    after = _verdicts(_report_from(root))

    new_pairs = set(after) - set(before)
    assert {(venue_id, currency) for venue_id, currency, _ in new_pairs} == {
        ("wise", "UAH"),
        ("wise", "USD"),
    }
    for key in new_pairs:
        verdict = after[key]
        assert isinstance(verdict, NotReady), key
        assert NO_INBOUND in {deficit.kind for deficit in verdict.deficits}, key

    # And the hole is *named*: the owner can write the declaration from the report alone.
    missing = next(
        deficit.missing
        for key in sorted(new_pairs)
        for deficit in _as_not_ready(after[key]).deficits
        if deficit.kind == NO_INBOUND
    )
    assert missing.direction == "inbound"
    assert missing.origin_venue in {"monobank_uah", "coinbase"}
    assert missing.candidates == ()


def _as_not_ready(verdict: Ready | NotReady) -> NotReady:
    assert isinstance(verdict, NotReady)
    return verdict


# ---------------------------------------------------------------------------
# SC-019: the spendable list is data, and changing it changes verdicts
# ---------------------------------------------------------------------------


def test_adding_a_venue_to_the_spendable_list_flips_a_deficit_three_pair(
    tmp_path: Path,
) -> None:
    """**SC-019, FR-004.** What counts as "out" is a fact about the owner's life, entered as data.

    The scratch registry gains a hryvnia-only venue ``wise``, a way in to it from the salary
    rail, and a way **out** of it that ends in hryvnia at ``binance``. ``binance`` can hold
    hryvnia -- ``data/venues.toml`` says so -- and is deliberately absent from the spendable
    list, because holding hryvnia on an exchange is not the same as being able to spend it. So
    the pair is deficit 3: a way out exists and it does not reach a spendable endpoint.

    Then ``binance`` joins the list. **Three lines in one TOML file**, no source change, and the
    verdict flips to ready. That is the whole of FR-004: not "UAH anywhere", and not a rule in
    code -- an exit ending in hryvnia at a venue the list does not name is deficit 3 exactly as
    one ending in dollars is.
    """
    root = _scratch(tmp_path)
    venues_file = root / "venues.toml"
    venues_file.write_text(
        venues_file.read_text(encoding="utf-8")
        + '\n[[venue]]\nid         = "wise"\nname       = "Wise (SYNTHETIC FIXTURE)"\n'
        'currencies = ["UAH"]\n',
        encoding="utf-8",
    )
    (root / "routes" / "monobank_to_wise.toml").write_text(
        _corridor_toml(
            "monobank_to_wise", origin="monobank_uah", destination="wise", direction="inbound"
        ),
        encoding="utf-8",
    )
    (root / "routes" / "wise_to_binance.toml").write_text(
        _corridor_toml("wise_to_binance", origin="wise", destination="binance", direction="exit"),
        encoding="utf-8",
    )

    before = _verdicts(_report_from(root))[("wise", "UAH", "salary_uah")]
    assert isinstance(before, NotReady)
    (deficit,) = before.deficits
    assert deficit.kind == EXIT_NOT_SPENDABLE
    # The way out was observed; it just lands somewhere the owner cannot spend from.
    assert [relied.route_id for relied in deficit.observed_exits] == ["wise_to_binance"]

    spendable_file = root / "spendable" / "owner-001.toml"
    spendable_file.write_text(
        spendable_file.read_text(encoding="utf-8")
        + '\n[[spendable]]\nvenue    = "binance"\ncurrency = "UAH"\n',
        encoding="utf-8",
    )

    after = _verdicts(_report_from(root))[("wise", "UAH", "salary_uah")]
    assert isinstance(after, Ready)
    assert isinstance(after.exits, tuple), "wise is not itself a spendable endpoint"
    assert [relied.route_id for relied in after.exits] == ["wise_to_binance"]


def _corridor_toml(route_id: str, *, origin: str, destination: str, direction: str) -> str:
    """A one-leg hryvnia corridor, declared by a contract test.

    Every number in it is zero and says SYNTHETIC, and ``verified_on`` is empty, exactly like
    every other route figure in this project. The point of the fixture is its **endpoints**;
    nothing in coverage reads a fee, and inventing a plausible one would be inventing a number
    no assertion depends on.
    """
    return f"""# SYNTHETIC FIXTURE -- an invented corridor, declared by a contract test.

[route]
id            = "{route_id}"
provider      = "{route_id} (SYNTHETIC FIXTURE)"
origin        = "{origin}"
destination   = "{destination}"
direction     = "{direction}"
status        = "open"

  [[route.leg]]
  index                  = 0
  kind                   = "transfer"
  from_venue             = "{origin}"
  to_venue               = "{destination}"
  from_ccy               = "UAH"
  to_ccy                 = "UAH"
  fee_pct                = 0.0
  fee_fixed              = 0.0
  latency_days           = 1
  disruption_probability = 0.0
  kind_of_observation    = "bank_fee_schedule"
  source                 = "SYNTHETIC FIXTURE -- invented, not an observed tariff"
  retrieved_on           = "2026-08-01"
  verified_on            = ""
"""


# ---------------------------------------------------------------------------
# SC-015: a ready verdict says what it rests on
# ---------------------------------------------------------------------------

VENUES = keyed([venue("mono", UAH), venue("broker", USD)])
STREAMS = keyed([stream("salary_uah", UAH, "mono")])
SPENDABLE = spendable(("mono", UAH))


def _rests_on(inbound_status: str, exit_status: str) -> str:
    routes = keyed(
        [
            route(
                "in_mono_broker",
                origin="mono",
                destination="broker",
                direction="inbound",
                from_ccy=UAH,
                to_ccy=USD,
                status=inbound_status,  # type: ignore[arg-type]
            ),
            route(
                "out_broker_mono",
                origin="broker",
                destination="mono",
                direction="exit",
                from_ccy=USD,
                to_ccy=UAH,
                status=exit_status,  # type: ignore[arg-type]
            ),
        ]
    )
    produced = coverage(
        venues=VENUES, streams=STREAMS, routes=routes, regimes={}, spendable=SPENDABLE
    )
    assert isinstance(produced, CoverageReport)
    (block,) = produced.regimes
    verdict = next(v for v in block.verdicts if v.destination.venue_id == "broker")
    assert isinstance(verdict, Ready), verdict
    return verdict.rests_on


@pytest.mark.parametrize(
    ("inbound", "exit_status", "expected"),
    [
        ("open", "open", "open"),
        ("closed", "closed", "closed_only"),
        ("constrained", "open", "constrained"),
        ("open", "constrained", "constrained"),
        ("closed", "open", "constrained"),
    ],
)
def test_a_ready_verdict_says_whether_it_rests_on_open_or_closed_declarations(
    inbound: str, exit_status: str, expected: str
) -> None:
    """**SC-015, FR-022.** Declared is declared -- and the report says how solid it is.

    A closed route still satisfies coverage, because the hole this audit exists to surface is a
    corridor **nobody has observed** and a closed one is already observed: sending the owner
    out to look at it again would be the wrong instruction. What FR-022 leaves owing is exactly
    this field -- a ready verdict resting only on closed routes must not look identical to one
    resting on open ones.

    ``constrained`` is a real third state rather than a rounding. The last two rows are the
    ones that make that necessary: half-open is neither of the other two, and flattening it
    into either would state something the declarations do not.
    """
    assert _rests_on(inbound, exit_status) == expected


ARRIVAL_VENUES = keyed([venue("mono", UAH), venue("pocket", USD)])
ARRIVAL_STREAMS = keyed([stream("contract_usd", USD, "pocket")])
"""``pocket`` is the arrival venue and is **not** spendable, so its exit half is carried by a
declared route rather than by identity -- which is what makes the arrival branch of
``rests_on`` reachable at all."""


def _rests_on_from_arrival(exit_status: str) -> str:
    routes = keyed(
        [
            route(
                "out_pocket_mono",
                origin="pocket",
                destination="mono",
                direction="exit",
                from_ccy=USD,
                to_ccy=UAH,
                status=exit_status,  # type: ignore[arg-type]
            )
        ]
    )
    produced = coverage(
        venues=ARRIVAL_VENUES,
        streams=ARRIVAL_STREAMS,
        routes=routes,
        regimes={},
        spendable=SPENDABLE,
    )
    assert isinstance(produced, CoverageReport)
    (block,) = produced.regimes
    verdict = next(v for v in block.verdicts if v.destination.venue_id == "pocket")
    assert isinstance(verdict, Ready), verdict
    assert verdict.inbound is SATISFIED_BY_ARRIVAL
    return verdict.rests_on


@pytest.mark.parametrize(
    ("exit_status", "expected"),
    [("open", "open"), ("constrained", "constrained"), ("closed", "closed_only")],
)
def test_a_verdict_reached_by_arrival_still_reports_its_exits_status(
    exit_status: str, expected: str
) -> None:
    """**SC-015 where the inbound half is a sentinel** -- and a regression test with a history.

    The first implementation of ``rests_on`` collected the relied routes only when the inbound
    half was a tuple, so a pair reached by *arrival* contributed an empty relied list and could
    never be ``closed_only``: an arrival-reached destination whose only way out was declared
    closed reported ``constrained``, which says some route still works. It was found by
    reading, fixed, and left unpinned -- every case exercising the arrival branch happened to
    use an open exit, so reverting the fix left the whole suite green.

    That is what this parametrisation closes. The money being already at the destination says
    nothing about whether the way out works, and a ready verdict resting on one closed route
    must say so.
    """
    assert _rests_on_from_arrival(exit_status) == expected


IDENTITY_VENUES = keyed([venue("mono", UAH), venue("hub", UAH)])
IDENTITY_STREAMS = keyed([stream("salary_uah", UAH, "hub")])
"""The mirror: ``mono`` is the spendable endpoint, reached by a declared inbound route from a
stream that arrives somewhere else. The exit half is the sentinel and the inbound half is not."""


@pytest.mark.parametrize(
    ("inbound_status", "expected"),
    [("open", "open"), ("constrained", "constrained"), ("closed", "closed_only")],
)
def test_a_verdict_whose_exit_is_satisfied_by_identity_still_reports_its_inbounds_status(
    inbound_status: str, expected: str
) -> None:
    """The same claim on the other half, so the two sentinels cannot drift apart.

    Money already at a spendable endpoint has nowhere left to go, and that says nothing about
    whether the corridor that would get it there works. A ready verdict resting on one closed
    inbound is ``closed_only`` here exactly as it is when both halves are routes.
    """
    routes = keyed(
        [
            route(
                "in_hub_mono",
                origin="hub",
                destination="mono",
                direction="inbound",
                from_ccy=UAH,
                status=inbound_status,  # type: ignore[arg-type]
            )
        ]
    )
    produced = coverage(
        venues=IDENTITY_VENUES,
        streams=IDENTITY_STREAMS,
        routes=routes,
        regimes={},
        spendable=SPENDABLE,
    )
    assert isinstance(produced, CoverageReport)
    (block,) = produced.regimes
    verdict = next(v for v in block.verdicts if v.destination.venue_id == "mono")
    assert isinstance(verdict, Ready), verdict
    assert verdict.exits is SATISFIED_BY_IDENTITY
    assert verdict.rests_on == expected


def test_a_verdict_resting_on_no_route_at_all_is_open() -> None:
    """Both halves sentinels: there is nothing there to be shut.

    ``mono`` is the salary's arrival venue **and** the declared spendable endpoint, so the pair
    is ready on arrival and identity with no route in the registry touching it. ``open`` is the
    honest answer -- ``closed_only`` would name a closed declaration that does not exist, and
    ``constrained`` would imply a limit nobody declared.
    """
    produced = coverage(
        venues=keyed([venue("mono", UAH)]),
        streams=keyed([stream("salary_uah", UAH, "mono")]),
        routes=keyed(
            [route("in_mono_mono", origin="x", destination="y", direction="inbound", from_ccy=UAH)]
        ),
        regimes={},
        spendable=SPENDABLE,
    )
    assert isinstance(produced, CoverageReport)
    (block,) = produced.regimes
    verdict = next(v for v in block.verdicts if v.destination.venue_id == "mono")
    assert isinstance(verdict, Ready)
    assert verdict.inbound is SATISFIED_BY_ARRIVAL
    assert verdict.exits is SATISFIED_BY_IDENTITY
    assert verdict.rests_on == "open"


def test_a_ready_verdict_resting_on_closed_routes_is_still_distinct_from_a_hole() -> None:
    """The third distinction SC-015 asks for, which the parametrisation above cannot make.

    ``closed_only`` and *not ready* are different claims: the first says a way in and a way out
    are declared and neither works today, the second says one of them was never declared at
    all. The owner acts differently on each -- wait, versus go and observe -- and the type is
    what keeps them apart.
    """
    routes = keyed(
        [
            route(
                "in_mono_broker",
                origin="mono",
                destination="broker",
                direction="inbound",
                from_ccy=UAH,
                to_ccy=USD,
                status="closed",
            )
        ]
    )
    produced = coverage(
        venues=VENUES, streams=STREAMS, routes=routes, regimes={}, spendable=SPENDABLE
    )
    assert isinstance(produced, CoverageReport)
    (block,) = produced.regimes
    verdict = next(v for v in block.verdicts if v.destination.venue_id == "broker")
    # Not ready, and for the reason that distinguishes the two: nothing leaves ``broker`` at
    # all. ``closed_only`` would have said a way out is declared and shut, which is a different
    # instruction to the owner -- wait, rather than go and observe.
    assert isinstance(verdict, NotReady)
    assert {deficit.kind for deficit in verdict.deficits} == {NO_EXIT_DECLARED}


# ---------------------------------------------------------------------------
# Principle II, greppably
# ---------------------------------------------------------------------------


def test_no_coverage_source_module_names_a_venue_route_or_stream_id() -> None:
    """A branch on an id is the Principle II violation this design exists to prevent.

    Every question the report asks -- does a route exist from here to there, is this endpoint
    in the spendable list -- is a query over data, so no declared identifier should appear in
    this feature's source at all. A textual scan, with the same limits
    ``test_money_construction_guard`` states: it would not catch an id assembled from parts.
    What it catches is the obvious version, which is the one that gets written.

    The ids are taken from the shipped declarations rather than listed here, so the scan grows
    with the registry instead of going stale the day a venue is added.
    """
    declarations = resolver.coverage_from_data_root(
        DATA_ROOT, base_currency=Currency.UAH, scenario_id=None
    )
    identifiers = (
        set(declarations.ramp.venues)
        | set(declarations.ramp.routes)
        | set(declarations.ramp.streams)
    )
    assert identifiers, "the shipped registry declares nothing; this scan would be vacuous"

    offenders: list[tuple[str, int, str]] = []
    for path in COVERAGE_SOURCES:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for identifier in identifiers:
                if identifier in line:
                    offenders.append((path.name, number, identifier))
    assert offenders == []
