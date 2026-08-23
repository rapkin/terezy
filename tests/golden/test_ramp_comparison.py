"""The ramp comparison, recorded, so a refactor can be *proven* output-preserving.

This is the counterpart of ``test_end_to_end_ovdp.py`` for feature 002: the full ranking of
every declared route to one destination, built from the shipped declarations in ``data/`` and
compared against a checked-in artefact.

**Why an artefact rather than only assertions.** The contract tests already compare the
loader-built records against hand-built ones *in process*. A golden file is a different
guarantee: it compares today's output against a recorded one from a previous run, so a
refactor that quietly changed a figure fails here even when every assertion elsewhere still
passes on its own terms.

**Why the digest and the rendering both.** The digest is the assertion -- it covers every
amount as ``float.hex()``, so agreement means bit-identity. The readable half beside it is the
same claim written out, so a ``git diff`` says *which route moved and by how much* instead of
only "the hash changed". Amounts are rendered with ``repr``, which round-trips a float64
exactly, so the readable half is not the weaker of the two.

**The input digests are recorded on purpose.** A change to a declaration file *should* fail
this test, on the line that names the file. The last time the OVDP artefact moved, the diff
was exactly three input digests and an unchanged result digest -- which is how the file
distinguishes "the inputs changed" from "the answer changed".

**The two fields feature 004 added are rendered and digested**: ``exit_path`` -- which way out
this figure is keyed by -- and ``by_segment``, the attribution's second axis. Both are
user-visible, and a recorded result that omitted them would let either move without the artefact
noticing, which is the one thing a golden file exists to prevent.

**Deliberately excluded**: provenance. Filling in a ``verified_on`` must not move the digest,
or the test would fail on a documentation edit; that exclusion is asserted below, and the mark
itself is checked separately.

**How to update it deliberately**::

    TEREZY_UPDATE_GOLDEN=1 uv run pytest tests/golden/test_ramp_comparison.py
    git diff tests/golden/ramp_comparison.golden.txt

then read the diff and justify each changed line in the commit message. A **missing** file is
a failure, never a silent regeneration: a golden file that reappeared on its own would make a
deleted artefact indistinguishable from a passing run.

**And it cannot be green-and-wrong.** An artefact recorded from a broken run agrees with
itself forever, so the constants below restate the hand-computed figures from
``tests/worked_examples/test_ramp_p2p_premium.py`` and the numbers in `docs/METHODOLOGY.md`
§16-§17, and they are checked against the run.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Final, assert_never

import pytest

from terezy.core.ledger.canonical import Canonical
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.coverage import SpendableEndpoint
from terezy.core.results.ramp import (
    ExitCostUnknown,
    NothingComparable,
    RampCost,
    Ranking,
    RoundTripCost,
    SegmentAttribution,
    recommended_cost,
)
from terezy.core.routes import ranking
from terezy.core.routes.path import (
    ExitByIdentity,
    ExitChain,
    FundingPath,
    candidate_id,
    exit_segments_of,
)
from terezy.data import manifest
from terezy.data.declarations import loader, resolver

pytestmark = pytest.mark.golden

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
DATA_ROOT: Final = REPO_ROOT / "data"
GOLDEN_FILE: Final = Path(__file__).with_name("ramp_comparison.golden.txt")
SPENDABLE_FILE: Final = DATA_ROOT / "spendable" / "owner-001.toml"

UPDATE_VARIABLE: Final = "TEREZY_UPDATE_GOLDEN"
"""Set it to rewrite the artefact. See the module docstring for the procedure."""

DESTINATION: Final = "binance"
STREAM: Final = "salary_uah"
AMOUNT: Final = 10_000.0
ON_DATE: Final = date(2026, 8, 21)
AS_OF: Final = date(2026, 8, 21)

# The hand-computed figures this run must reproduce. METHODOLOGY §16.2 and §17 show the
# arithmetic; the worked examples check it. Restated here so the artefact cannot agree with
# a broken run:
#
#   reference 42, buy premium +3 -> price 45, sell premium -2.5 -> price 39.5
#   one way    1 - 42/45     = 3/45   = 6.6667 %
#   round trip 1 - 39.5/45   = 5.5/45 = 12.2222 %
#   and the domestic route is exactly zero, both ways.
P2P_ROUTE: Final = "monobank_to_binance_p2p"
P2P_ONE_WAY: Final = 3.0 / 45.0
P2P_ROUND_TRIP: Final = 5.5 / 45.0
P2P_SPREAD_OVER_REFERENCE: Final = 3.0 / 42.0
"""§4.3.1's own figure, reported beside the cost and never as it (METHODOLOGY §16.2)."""

UAH: Final = Currency.UAH


# --- the run under test ---------------------------------------------------------------


def _declarations() -> resolver.RampDeclarations:
    return resolver.ramp_from_data_root(DATA_ROOT, base_currency=UAH)


def _spendable() -> frozenset[SpendableEndpoint]:
    """The shipped spendable list, read from ``data/`` like every other input to this run.

    Loaded rather than restated, because ranking now consults it: a destination that is itself
    somewhere the owner spends satisfies its own exit requirement (003 FR-002), and a hand-written
    copy here could disagree with the file while the artefact still looked authoritative. The
    file's digest is recorded with the other inputs below, so editing it fails this test on its
    own line -- which is the point of recording inputs at all.
    """
    owner_id, endpoints = loader.spendable_from_file(SPENDABLE_FILE)
    assert owner_id == "owner-001", owner_id
    return frozenset(endpoints)


def _paths(declared: resolver.RampDeclarations) -> tuple[FundingPath, ...]:
    """Every inbound route that ends at the destination, in a stable order.

    Sorted by route id so the artefact does not move when the loader's iteration order does --
    a golden file that changed with dictionary ordering would teach its reader to overwrite it.
    """
    return tuple(
        FundingPath(destination_id=DESTINATION, stream_id=STREAM, route_id=route_id)
        for route_id, route in sorted(declared.routes.items())
        if route.direction == "inbound" and route.destination == DESTINATION
    )


def _rank(declared: resolver.RampDeclarations) -> Ranking | NothingComparable:
    return ranking.rank(
        _paths(declared),
        Money(AMOUNT, UAH, prov.EMPTY),
        routes=declared.routes,
        channels=declared.channels,
        streams=declared.streams,
        kinds=declared.kinds,
        on_date=ON_DATE,
        as_of=AS_OF,
        spendable=_spendable(),
    )


def _ranking() -> Ranking:
    result = _rank(_declarations())
    assert isinstance(result, Ranking), result
    return result


# --- rendering ------------------------------------------------------------------------


def _money(value: Money) -> str:
    return f"{value.amount!r} {value.currency.value}"


def _segments(label: str, attributions: tuple[SegmentAttribution, ...]) -> Iterable[str]:
    """One line per segment per component, so a change to either axis shows up as a line.

    Rendered in full rather than summarised: ``by_segment`` is a *user-visible attribution*, and
    the value of recording it here is that a diff says which hop moved, not that a hash changed.
    A declared route has exactly one segment, so on today's registry these lines restate the
    component totals -- which is the correct reading, and is what would stop being true the day
    a composed candidate entered this comparison.
    """
    for entry in attributions:
        for component, amount in sorted(entry.components.items(), key=lambda kv: kv[0].value):
            yield (
                f"      {label} seg[{entry.position}] {entry.route_id:<26} "
                f"{component.value:<18} {_money(amount)}"
            )


def _exit(chain: ExitChain | None) -> str:
    """The way out this figure is keyed by, in the output's own words.

    ``none`` is not decoration: it means there is no round-trip figure at all, and the
    correspondence is exact (FR-012). The identity case renders as itself rather than as an
    empty chain, because a round trip that costs nothing *because there is nothing to do* is a
    different claim from one whose fees cancelled.
    """
    match chain:
        case None:
            return "none"
        case ExitByIdentity():
            return "by-identity"
        case _:
            return "+".join(exit_segments_of(chain))


def _cost(index: int, cost: RampCost) -> Iterable[str]:
    yield f"[{index}] {candidate_id(cost.path)}"
    yield f"      exit_path         {_exit(cost.exit_path)}"
    yield f"      stream            {cost.path.stream_id}"
    yield f"      destination       {cost.path.destination_id}"
    yield f"      status            {cost.status}"
    yield f"      latency_days      {cost.latency_days}"
    yield f"      ceiling           {'none' if cost.ceiling is None else _money(cost.ceiling)}"
    yield f"      disruption        {cost.disruption_probability!r}"
    yield f"      one_way  sent     {_money(cost.one_way.sent)}"
    yield f"      one_way  arrived  {_money(cost.one_way.arrived)}"
    yield f"      one_way  fraction {cost.one_way.fraction!r}"
    yield f"      one_way  channels {cost.one_way.channels_applied}"
    yield f"      one_way  spread/r {cost.one_way.spreads_over_reference}"
    for component, amount in sorted(cost.one_way.components.items(), key=lambda kv: kv[0].value):
        yield f"      one_way  {component.value:<16} {_money(amount)}"
    yield from _segments("one_way ", cost.one_way.by_segment)
    match cost.round_trip:
        case RoundTripCost() as round_trip:
            yield f"      round    fraction {round_trip.fraction!r}"
            yield f"      round    channels {round_trip.channels_applied}"
            yield from _segments("round   ", round_trip.by_segment)
        case ExitCostUnknown() as unknown:
            yield f"      round    UNKNOWN  {unknown.reason}"
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(cost.round_trip)


def _render(result: Ranking, declared: resolver.RampDeclarations) -> str:
    lines: list[str] = [
        "# terezy ramp comparison -- a recorded result, not a source of truth.",
        "# Regenerate deliberately: TEREZY_UPDATE_GOLDEN=1 uv run pytest"
        " tests/golden/test_ramp_comparison.py",
        "# then read the diff. Every changed line needs a reason in the commit message.",
        "",
        f"destination   {DESTINATION}",
        f"stream        {STREAM}",
        f"amount        {AMOUNT!r} {UAH.value}",
        f"on_date       {ON_DATE.isoformat()}",
        f"as_of         {AS_OF.isoformat()}",
        "",
        "## inputs -- a change to any of these SHOULD fail this test, on its own line",
    ]
    for name in sorted(declared.routes):
        digest = manifest.file_version(DATA_ROOT / "routes" / f"{name}.toml")
        lines.append(f"route      {name:<34} {digest}")
    for stem in (
        "channels/uah_usd",
        "streams/owner-001",
        "spendable/owner-001",
        "observation_kinds",
        "venues",
    ):
        candidate = DATA_ROOT / f"{stem}.toml"
        if candidate.is_file():
            lines.append(f"file       {stem:<34} {manifest.file_version(candidate)}")

    lines += ["", "## ranking -- lexicographic on (round trip, ceiling desc, latency)", ""]
    for index, cost in enumerate(result.costed):
        lines.extend(_cost(index, cost))
        lines.append("")
    lines.append(
        f"recommended   {result.recommended} ({candidate_id(recommended_cost(result).path)})"
    )
    lines.append(f"ties          {result.ties}")
    lines.append(f"excluded      {len(result.excluded)}")
    for unusable in result.excluded:
        lines.append(f"      {candidate_id(unusable.path)}: {unusable.binding_constraint}")
    lines.append(f"not_comparable {len(result.not_comparable)}")
    for cost in result.not_comparable:
        lines.append(f"      {candidate_id(cost.path)}")

    lines += ["", "## digest over core.routes.ranking output", digest_of(result), ""]
    return "\n".join(lines)


def digest_of(result: Ranking) -> str:
    """The assertion: a digest over every costed candidate, amounts as ``float.hex()``."""
    shapes: tuple[Canonical, ...] = tuple(manifest_shape(cost) for cost in result.costed)
    return manifest.digest((*shapes, str(result.recommended)))


def manifest_shape(cost: RampCost) -> tuple[str | tuple[str, ...], ...]:
    """The parts of a cost the digest covers. Provenance is excluded, deliberately."""
    return (
        candidate_id(cost.path),
        cost.path.stream_id,
        cost.path.destination_id,
        cost.one_way.sent.amount.hex(),
        cost.one_way.arrived.amount.hex(),
        cost.one_way.fraction.hex(),
        tuple(cost.one_way.channels_applied),
        tuple(value.hex() for value in cost.one_way.spreads_over_reference),
        str(cost.latency_days),
        cost.status,
        _exit(cost.exit_path),
        tuple(
            f"{entry.position}:{entry.route_id}:{component.value}:{amount.amount.hex()}"
            for entry in cost.one_way.by_segment
            for component, amount in sorted(entry.components.items(), key=lambda kv: kv[0].value)
        ),
    )


# --- comparison -----------------------------------------------------------------------


def _recorded() -> str:
    if not GOLDEN_FILE.is_file():
        raise AssertionError(
            f"{GOLDEN_FILE.name} does not exist. A golden file is never regenerated "
            f"silently -- produce it deliberately with {UPDATE_VARIABLE}=1 uv run pytest "
            "tests/golden/test_ramp_comparison.py, then read the diff."
        )
    return GOLDEN_FILE.read_text(encoding="utf-8")


def _today() -> str:
    declared = _declarations()
    result = _rank(declared)
    assert isinstance(result, Ranking), result
    rendered = _render(result, declared)
    if os.environ.get(UPDATE_VARIABLE):
        GOLDEN_FILE.write_text(rendered, encoding="utf-8")
    return rendered


class TestTheRecordedComparisonIsStillTheComparison:
    """Today's ranking against the one recorded on a previous run."""

    def test_the_whole_comparison_matches_the_checked_in_artefact(self) -> None:
        assert _today() == _recorded()

    def test_the_recorded_digest_is_the_digest_of_todays_ranking(self) -> None:
        """The assertion inside the assertion, so a rendering drift cannot hide a figure."""
        assert digest_of(_ranking()) in _recorded()

    def test_no_rendered_line_ends_in_whitespace(self) -> None:
        """An editor stripping trailing space must not produce a failure about a route."""
        assert all(line == line.rstrip() for line in _today().splitlines())


class TestTheArtefactCannotBeGreenAndWrong:
    """The figures tied back to the hand arithmetic, so a broken recording is caught."""

    def test_the_domestic_route_is_absent_because_it_goes_somewhere_else(self) -> None:
        """FR-008, visible as a shape rather than a rule.

        ``inzhur_direct`` is the zero-cost route and it is **not** in this ranking, because it
        ends at ``inzhur`` and this comparison is about reaching ``binance``. A cost is per
        ``(destination x stream x route)``, so a ranking is per destination too -- and the
        temptation this guards against is a "cheapest route" list that quietly mixes
        destinations and then reports a zero next to a 12%% figure for a journey that does not
        go to the same place.

        The zero-cost claim itself is checked where it belongs, in
        ``tests/unit/test_zero_cost_domestic_route.py``.
        """
        route_ids = {candidate_id(cost.path) for cost in _ranking().costed}
        assert route_ids, "the ranking is empty, so nothing below proves anything"
        assert "inzhur_direct" not in route_ids
        assert all(cost.path.destination_id == DESTINATION for cost in _ranking().costed)

    def test_the_p2p_route_reproduces_the_hand_computed_cost(self) -> None:
        p2p = next(c for c in _ranking().costed if candidate_id(c.path) == P2P_ROUTE)
        assert is_close(p2p.one_way.fraction, P2P_ONE_WAY)
        assert isinstance(p2p.round_trip, RoundTripCost), p2p.round_trip
        assert is_close(p2p.round_trip.fraction, P2P_ROUND_TRIP)

    def test_the_rate_space_spread_is_reported_beside_the_cost_not_as_it(self) -> None:
        """METHODOLOGY §16.2: `p/r` is §4.3.1's figure and is not the cost."""
        p2p = next(c for c in _ranking().costed if candidate_id(c.path) == P2P_ROUTE)
        assert p2p.one_way.spreads_over_reference == (P2P_SPREAD_OVER_REFERENCE,)
        assert not is_close(p2p.one_way.fraction, P2P_SPREAD_OVER_REFERENCE)

    def test_the_recommendation_is_one_of_the_costed_candidates(self) -> None:
        """SC-016 again, at this level: identity, not equality."""
        result = _ranking()
        assert recommended_cost(result) is result.costed[result.recommended]

    def test_every_shipped_route_figure_is_marked_unverified(self) -> None:
        """None of §11 item 1's numbers has been observed, and the output says so."""
        for cost in _ranking().costed:
            if cost.one_way.provenance.sources:
                assert prov.is_unverified(cost.one_way.provenance), candidate_id(cost.path)
