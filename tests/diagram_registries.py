"""Hand-built registries for the diagram suites, on the ``tests/coverage_registries.py`` pattern.

Not a test module -- ``pytest`` collects only ``test_*.py``, so this file is imported, never
run. It exists for the same reason its predecessor does: the mark cases, the mode cases and
the determinism cases all care about *the shape of a registry* rather than about any
particular corridor, and duplicating five venue declarations into each of them would mean
five places to edit when a record gains a field.

**Every number here is invented and almost none of it is read.** A diagram shows what the
declarations say; the fees below are zero or trivial and the citations say so in capitals,
because a fixture that invented a plausible tariff would be inventing a figure no assertion
depends on. The two exceptions are deliberate:

* the **dates** are real inputs -- staleness is ``as_of - retrieved_on`` against a *declared*
  threshold, so :data:`AS_OF` and the retrieval dates below are what make the stale states
  stale, and they are checked against ``data/observation_kinds.toml``'s own numbers rather
  than against a threshold invented here;
* the **citations** carry or omit the phrase ``SYNTHETIC FIXTURE``, because that phrase is
  how a declaration says it is synthetic (FR-014) and the renderer surfaces the declaration
  rather than inventing a detection mechanism.

**The six-state registry is the load-bearing one.** SC-004 asks for one diagram carrying
open/verified, unverified, stale, unverified-and-stale, closed and no-exit-declared, plus a
synthetic entry, all pairwise distinguishable. That is what :func:`six_state_registry`
declares, one route per state, and :class:`TestTheFixtureIsHonestAboutWhatItProves` in
``tests/contract/test_diagram_marks.py`` checks that it has not quietly stopped covering one.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

from terezy.api.diagrams import Diagram, Mode, NothingToDraw, render_graph, render_path
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.staleness import ObservationKind
from terezy.core.results.ramp import (
    ExitCostUnknown,
    NothingComparable,
    RampCost,
    RouteUnusable,
)
from terezy.core.routes import cost
from terezy.core.routes.legs import FX, TRANSFER, Leg, Route, RouteDirection, RouteStatus
from terezy.core.routes.path import FundingPath
from terezy.core.routes.venues import Venue
from terezy.core.scenarios.regimes import Regime
from terezy.data.declarations import loader, resolver

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
DATA_ROOT: Final = REPO_ROOT / "data"

UAH: Final = Currency.UAH
USD: Final = Currency.USD

AS_OF: Final = date(2026, 8, 21)
"""The as-of date every diagram fixture is rendered against.

An input, never a clock (``core.primitives.staleness``). Shared with
``tests/golden/test_ramp_comparison.py`` so the two artifacts describe the same day.
"""

FRESH: Final = date(2026, 8, 20)
"""One day before :data:`AS_OF`: current under every declared threshold."""

LONG_AGO: Final = date(2020, 1, 1)
"""Years before :data:`AS_OF`: stale under every declared threshold."""

FAST_KIND: Final = "p2p_premium"
"""The fastest-ageing declared kind (7 days). The stale routes below age under it."""

SLOW_KIND: Final = "bank_fee_schedule"
"""The slowest (365 days). The current routes age under it, so "fresh" is not an artefact
of a generous threshold applied to a stale date."""

REGIME_ID: Final = "fixture_regime"

VERIFIED_ROUTE: Final = "r_verified"
UNVERIFIED_ROUTE: Final = "r_unverified"
STALE_ROUTE: Final = "r_stale"
BOTH_ROUTE: Final = "r_both"
CLOSED_ROUTE: Final = "r_closed"
EXIT_ROUTE: Final = "r_exit"

DERIVED_FROM: Final = frozenset({UNVERIFIED_ROUTE, BOTH_ROUTE})
"""The routes resting on the one unverified source in :func:`one_unverified_registry`."""

SYNTHETIC_CITATION: Final = (
    "SYNTHETIC FIXTURE -- invented corridor, no observed value. Not a real tariff."
)
CITED_CITATION: Final = "https://example.invalid/a-cited-tariff (fixture, cited on purpose)"
"""Deliberately *not* synthetic in its wording, so ``SYNTHETIC`` is not universal in the
fixture -- a mark that appears on everything carries no information."""


@dataclass(frozen=True, slots=True)
class Registry:
    """What ``render_graph`` takes, kept together so a fixture is one value."""

    venues: Mapping[str, Venue]
    routes: Mapping[str, Route]
    regime: Regime
    kinds: Mapping[str, ObservationKind]


def declared_kinds() -> Mapping[str, ObservationKind]:
    """``data/observation_kinds.toml``, as declared.

    Loaded rather than hand-built: FR-013 requires staleness to surface *under the
    thresholds feature 002 declares*, and a fixture that invented its own would be testing
    the renderer against a rule nobody uses.
    """
    return {
        kind.id: kind
        for kind in loader.observation_kinds_from_file(DATA_ROOT / "observation_kinds.toml")
    }


def source(source_id: str, *, verified: bool, fresh: bool, synthetic: bool) -> Provenance:
    """One cited origin in one of the four states the marks distinguish."""
    return Provenance(
        frozenset(
            {
                SourceRef(
                    id=source_id,
                    citation=SYNTHETIC_CITATION if synthetic else CITED_CITATION,
                    retrieved_on=FRESH if fresh else LONG_AGO,
                    verified_on=(FRESH if fresh else LONG_AGO) if verified else None,
                )
            }
        )
    )


def venue(venue_id: str, *currencies: Currency) -> Venue:
    """One venue and the currencies it declares it can hold."""
    return Venue(
        id=venue_id,
        name=f"{venue_id} (SYNTHETIC FIXTURE)",
        currencies=frozenset(currencies),
    )


def leg(
    index: int,
    *,
    from_venue: str,
    to_venue: str,
    from_ccy: Currency,
    to_ccy: Currency,
    provenance: Provenance,
    kind_of_observation: str,
    fee_pct: float = 0.0,
    fee_fixed: float = 0.0,
) -> Leg:
    """One movement. ``fx`` exactly when the currencies differ, and a channel only there.

    The two rules the loader enforces, honoured here so a fixture never describes a file
    that would be refused at load.
    """
    converts = from_ccy is not to_ccy
    return Leg(
        index=index,
        kind=FX if converts else TRANSFER,
        from_venue=from_venue,
        to_venue=to_venue,
        from_ccy=from_ccy,
        to_ccy=to_ccy,
        channel="p2p" if converts else None,
        fee_pct=fee_pct,
        fee_fixed=Money(fee_fixed, from_ccy, provenance),
        minimum=None,
        maximum=None,
        monthly_cap=None,
        capacity_pool=None,
        latency_days=0,
        available_from=None,
        available_until=None,
        disruption_probability=0.0,
        kind_of_observation=kind_of_observation,
        provenance=provenance,
    )


def route(
    route_id: str,
    *,
    origin: str,
    destination: str,
    provenance: Provenance,
    kind_of_observation: str,
    direction: RouteDirection = "inbound",
    status: RouteStatus = "open",
    partner_route: str | None = None,
    from_ccy: Currency = UAH,
    to_ccy: Currency | None = None,
    fee_pct: float = 0.0,
    fee_fixed: float = 0.0,
) -> Route:
    """One declared corridor as a single leg, on ``coverage_registries.route``'s pattern.

    One leg because the graph reads the chain's endpoints and its legs in order; a
    three-leg fixture would exercise the same code and hide the rule behind arithmetic.
    ``direction`` is declared, never inferred (feature 002's FR-027) -- it is the field
    that stops an exit being found by reading an inbound route backwards.
    """
    return Route(
        id=route_id,
        provider=f"Synthetic provider for {route_id}",
        origin=origin,
        destination=destination,
        direction=direction,
        partner_route=partner_route,
        status=status,
        legs=(
            leg(
                0,
                from_venue=origin,
                to_venue=destination,
                from_ccy=from_ccy,
                to_ccy=from_ccy if to_ccy is None else to_ccy,
                provenance=provenance,
                kind_of_observation=kind_of_observation,
                fee_pct=fee_pct,
                fee_fixed=fee_fixed,
            ),
        ),
    )


def six_state_registry() -> Registry:
    """SC-004's fixture: every mark state a registry graph can carry, in one registry.

    +----------------------+------------------------------------------------------------+
    | route                | the state it is there for                                  |
    +======================+============================================================+
    | ``r_verified``       | open, cited, verified and current -- no mark applies       |
    | ``r_unverified``     | an empty ``verified_on``, and a synthetic citation         |
    | ``r_stale``          | verified years ago and never re-read: stale, not unverified|
    | ``r_both``           | both at once, and neither mark swallows the other          |
    | ``r_closed``         | declared closed: present and marked, never omitted         |
    | ``r_exit``           | the one declared way out, so ``NO EXIT DECLARED`` is not   |
    |                      | universal -- a mark on everything carries no information   |
    +----------------------+------------------------------------------------------------+

    ``gamma`` and ``delta`` receive inbound routes and nothing leaves them, so both carry
    the *no exit declared* mark (FR-005). ``orphan`` is touched by no route at all, which is
    how an isolated declared venue is proved to be drawn rather than dropped.

    Two routes run ``alpha -> beta``, which is User Story 1's fifth acceptance scenario:
    both appear, each carrying its own route identity.
    """
    venues = {
        v.id: v
        for v in (
            venue("alpha", UAH, USD),
            venue("beta", UAH, USD),
            venue("gamma", UAH),
            venue("delta", UAH),
            venue("orphan", USD),
        )
    }
    routes = {
        r.id: r
        for r in (
            route(
                VERIFIED_ROUTE,
                origin="alpha",
                destination="beta",
                provenance=source("s_verified", verified=True, fresh=True, synthetic=False),
                kind_of_observation=SLOW_KIND,
                partner_route=EXIT_ROUTE,
                fee_pct=0.015,
                fee_fixed=12.5,
            ),
            route(
                UNVERIFIED_ROUTE,
                origin="alpha",
                destination="beta",
                provenance=source("s_unverified", verified=False, fresh=True, synthetic=True),
                kind_of_observation=SLOW_KIND,
                partner_route=EXIT_ROUTE,
                from_ccy=UAH,
                to_ccy=USD,
            ),
            route(
                STALE_ROUTE,
                origin="alpha",
                destination="gamma",
                provenance=source("s_stale", verified=True, fresh=False, synthetic=False),
                kind_of_observation=FAST_KIND,
            ),
            route(
                BOTH_ROUTE,
                origin="alpha",
                destination="delta",
                provenance=source("s_both", verified=False, fresh=False, synthetic=True),
                kind_of_observation=FAST_KIND,
            ),
            route(
                CLOSED_ROUTE,
                origin="alpha",
                destination="gamma",
                provenance=source("s_closed", verified=True, fresh=True, synthetic=False),
                kind_of_observation=SLOW_KIND,
                status="closed",
            ),
            route(
                EXIT_ROUTE,
                origin="beta",
                destination="alpha",
                provenance=source("s_exit", verified=True, fresh=True, synthetic=False),
                kind_of_observation=SLOW_KIND,
                direction="exit",
            ),
        )
    }
    return Registry(
        venues=venues,
        routes=routes,
        regime=Regime(id=REGIME_ID, route_ids=frozenset(routes)),
        kinds=declared_kinds(),
    )


def one_unverified_registry() -> Registry:
    """SC-005's fixture: **one** unverified source, reached by two routes.

    Provenance is a set, so one ``SourceRef`` genuinely reaching two routes is the honest
    shape of "everything derived from this input" -- and the third route, resting on a
    verified source, is what makes the assertion mean something.
    """
    shared = source("s_the_one_unverified", verified=False, fresh=True, synthetic=False)
    verified = source("s_verified", verified=True, fresh=True, synthetic=False)
    venues = {v.id: v for v in (venue("alpha", UAH), venue("beta", UAH), venue("gamma", UAH))}
    routes = {
        r.id: r
        for r in (
            route(
                VERIFIED_ROUTE,
                origin="alpha",
                destination="beta",
                provenance=verified,
                kind_of_observation=SLOW_KIND,
            ),
            route(
                UNVERIFIED_ROUTE,
                origin="alpha",
                destination="gamma",
                provenance=shared,
                kind_of_observation=SLOW_KIND,
            ),
            route(
                BOTH_ROUTE,
                origin="beta",
                destination="gamma",
                provenance=shared,
                kind_of_observation=SLOW_KIND,
            ),
        )
    }
    return Registry(
        venues=venues,
        routes=routes,
        regime=Regime(id=REGIME_ID, route_ids=frozenset(routes)),
        kinds=declared_kinds(),
    )


def graph_of(registry: Registry, mode: Mode = Mode.DECLARED_FIGURES) -> Diagram:
    """Render a fixture registry. ``as_of`` is :data:`AS_OF`, never a clock.

    Narrowed to :class:`Diagram` here rather than at every assertion. No registry input
    produces a ``NothingToDraw`` -- an empty one is a diagram that says it is empty -- so a
    fixture that suddenly refused would be a finding, and the assertion says so.
    """
    rendered = render_graph(
        venues=registry.venues,
        routes=registry.routes,
        regime=registry.regime,
        mode=mode,
        kinds=registry.kinds,
        as_of=AS_OF,
    )
    assert isinstance(rendered, Diagram), rendered
    return rendered


def six_state_graph(mode: Mode = Mode.DECLARED_FIGURES) -> Diagram:
    return graph_of(six_state_registry(), mode)


def one_unverified_graph(mode: Mode = Mode.DECLARED_FIGURES) -> Diagram:
    return graph_of(one_unverified_registry(), mode)


def shipped_declarations() -> resolver.RampDeclarations:
    """Everything under ``data/``, resolved -- the registry the owner actually declares."""
    return resolver.ramp_from_data_root(DATA_ROOT, base_currency=UAH)


def shipped_regime(declared: resolver.RampDeclarations, scenario_id: str, regime_id: str) -> Regime:
    """One declared regime, by id, or a loud failure naming what is declared."""
    scenario = declared.scenarios[scenario_id]
    for regime in scenario.regimes:
        if regime.id == regime_id:
            return regime
    raise KeyError(
        f"{scenario_id} declares no regime {regime_id!r}: {[r.id for r in scenario.regimes]}"
    )


EDGE_LABEL: Final = re.compile(r'\|"(.*?)"\|')
"""The label of a Mermaid edge line. Every edge this package emits is quoted."""

ROUTE_FIELD: Final = re.compile(r"route (\S+)")
"""How an edge label names the route it belongs to. Read here so the assertions in the
suites can say "this route's label" rather than "some line containing this string"."""


def labels_by_route(text: str) -> dict[str, str]:
    """Every edge label in a diagram, grouped by the route it names.

    A route with several legs contributes several labels, joined by newlines, so
    ``"UNVERIFIED" in labels[route_id]`` means *some leg of that route*, which is what the
    mark assertions are about. Edges that name no route -- the explicitly absent exit of
    FR-005 -- are not route labels and are deliberately absent from the result.
    """
    grouped: dict[str, list[str]] = {}
    for line in text.splitlines():
        found = EDGE_LABEL.search(line)
        if found is None:
            continue
        named = ROUTE_FIELD.search(found.group(1))
        if named is None:
            continue
        grouped.setdefault(named.group(1), []).append(found.group(1))
    return {route_id: "\n".join(labels) for route_id, labels in grouped.items()}


P2P_ROUTE: Final = "monobank_to_binance_p2p"
"""§4.3.1's corridor, and the one the costed-path golden depicts. Round trip through its
declared partner ``binance_p2p_to_monobank`` -- an exit route with its own legs, never the
inbound chain reversed (feature 002's FR-027)."""

UAH_STREAM: Final = "salary_uah"
USD_STREAM: Final = "contract_usd"

NO_PARTNER_ROUTE: Final = "coinbase_to_ibkr"
"""The one shipped route declaring no ``partner_route``, so costing it yields
``ExitCostUnknown`` -- the state FR-010 and SC-007 are about. It exists only under the
``normalized`` regime."""

AMOUNT: Final = 10_000.0
"""What the golden path sends. Shared with ``tests/golden/test_ramp_comparison.py`` so the two
artifacts describe the same journey."""


def costed(
    declared: resolver.RampDeclarations,
    *,
    route_id: str,
    stream_id: str,
    destination_id: str,
    amount: float,
    currency: Currency = UAH,
) -> RampCost | RouteUnusable:
    """One route costed through feature 002's one costing function.

    Through ``cost_one`` rather than by hand: a costed-path diagram must show *the result's*
    figures, so a fixture that built a ``RampCost`` itself would be testing the renderer
    against numbers nobody computed.
    """
    return cost.cost_one(
        FundingPath(destination_id=destination_id, stream_id=stream_id, route_id=route_id),
        Money(amount, currency, prov.EMPTY),
        routes=declared.routes,
        channels=declared.channels,
        streams=declared.streams,
        kinds=declared.kinds,
        on_date=AS_OF,
        as_of=AS_OF,
    )


def p2p_cost(declared: resolver.RampDeclarations | None = None) -> RampCost:
    """The §4.3.1 round trip, costed. A ``RouteUnusable`` here is a fixture failure."""
    result = costed(
        declared if declared is not None else shipped_declarations(),
        route_id=P2P_ROUTE,
        stream_id=UAH_STREAM,
        destination_id="binance",
        amount=AMOUNT,
    )
    assert isinstance(result, RampCost), result
    return result


def exit_unknown_cost(declared: resolver.RampDeclarations | None = None) -> RampCost:
    """A costed route whose exit nobody has declared: one way real, round trip absent."""
    result = costed(
        declared if declared is not None else shipped_declarations(),
        route_id=NO_PARTNER_ROUTE,
        stream_id=USD_STREAM,
        destination_id="ibkr_usd",
        amount=1_000.0,
        currency=USD,
    )
    assert isinstance(result, RampCost), result
    return result


CostedOutcome = RampCost | RouteUnusable | ExitCostUnknown | NothingComparable
"""Everything ``render_path`` accepts: one costed result, or one of the three refusals."""


def path_of(result: CostedOutcome, *, regime_id: str = "wartime") -> Diagram | NothingToDraw:
    """Render a costed result under one declared regime."""
    declared = shipped_declarations()
    return render_path(
        result,
        routes=declared.routes,
        regime=shipped_regime(declared, "war_end", regime_id),
    )


def drawn_path(result: CostedOutcome, *, regime_id: str = "wartime") -> Diagram:
    """The same, narrowed -- a refusal here is the test's finding, not its input."""
    rendered = path_of(result, regime_id=regime_id)
    assert isinstance(rendered, Diagram), rendered
    return rendered
