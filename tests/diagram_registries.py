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
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Final

from terezy.api.diagrams import Diagram, Mode, NothingToDraw, render_graph, render_path
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.staleness import ObservationKind, StalenessVerdict
from terezy.core.results.coverage import SpendableEndpoint
from terezy.core.results.ramp import (
    ExitCostUnknown,
    NothingComparable,
    RampCost,
    RouteUnusable,
)
from terezy.core.routes import cost
from terezy.core.routes.channels import ChannelSide, FxChannel
from terezy.core.routes.legs import FX, TRANSFER, Leg, Route, RouteDirection, RouteStatus
from terezy.core.routes.path import (
    EXIT_BY_IDENTITY,
    FROM_THE_DECLARATION,
    Candidate,
    ComposedExit,
    ComposedPath,
    ExitChoice,
    FundingPath,
)
from terezy.core.routes.venues import Venue
from terezy.core.scenarios.regimes import Regime
from terezy.core.streams.streams import IncomeStream, Indexation
from terezy.data.declarations import loader, resolver

OWNER_ID: Final = "owner-001"
"""The one owner (Principle VII), carried while there is exactly one."""

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

EIGHTY_TWO_DAYS_AGO: Final = date(2026, 5, 31)
"""The **discriminating** age: 82 days before :data:`AS_OF`.

Stale under ``p2p_premium``'s 7 days and current under ``bank_fee_schedule``'s 365. That gap is
the whole content of FR-028 -- and the number is not chosen at random. ``cost._channel_verdicts``
records the defect it was written to fix in exactly these terms: a P2P premium aged under the
reference's schedule threshold was "reported fresh at 82 days".

:data:`LONG_AGO` cannot discriminate. It is stale under *both* thresholds, so a renderer that
collapsed the three declared kinds into one would reach the same verdict and every assertion
built on it would still pass. Any test of per-kind ageing has to use this date.
"""

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
    channels: Mapping[str, FxChannel]
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


def source(
    source_id: str,
    *,
    verified: bool,
    fresh: bool,
    synthetic: bool,
    retrieved_on: date | None = None,
) -> Provenance:
    """One cited origin in one of the states the marks distinguish.

    ``retrieved_on`` overrides the coarse ``fresh`` switch when a test needs a *specific* age --
    :data:`EIGHTY_TWO_DAYS_AGO` is the one that discriminates between two declared thresholds,
    which ``fresh=False`` cannot do because it is stale under both.
    """
    seen = retrieved_on if retrieved_on is not None else (FRESH if fresh else LONG_AGO)
    return Provenance(
        frozenset(
            {
                SourceRef(
                    id=source_id,
                    citation=SYNTHETIC_CITATION if synthetic else CITED_CITATION,
                    retrieved_on=seen,
                    verified_on=seen if verified else None,
                )
            }
        )
    )


def side(
    *,
    premium: float | None = None,
    bps: float | None = None,
    source_id: str,
    kind: str = FAST_KIND,
    verified: bool = True,
    fresh: bool = True,
    retrieved_on: date | None = None,
) -> ChannelSide:
    """One side of a quote, in exactly one of the two declared forms.

    Exactly one of ``premium`` and ``bps``, because that is what the loader enforces and what
    ``figures._declared`` renders: a side with both, or neither, is a file that cannot exist.
    """
    assert (premium is None) != (bps is None), "declare exactly one form"
    sources = source(
        source_id, verified=verified, fresh=fresh, synthetic=True, retrieved_on=retrieved_on
    )
    return ChannelSide(
        markup_bps=bps,
        premium_per_unit=None if premium is None else Money(premium, UAH, sources),
        kind=kind,
        provenance=sources,
    )


def channel(
    channel_id: str,
    *,
    buy: ChannelSide,
    sell: ChannelSide,
    reference: float = 42.0,
    kind: str = SLOW_KIND,
    reference_source: str | None = None,
) -> FxChannel:
    """One two-sided quote for ``(UAH, USD)``, with the reference cited separately.

    ``provenance`` is the union of the reference's sources and both sides', which is how the
    declaration loader builds it -- and what lets a renderer recover the reference's own
    sources by taking the sides' out (``graph._reference_sources``). A fixture that put the
    sides' sources only on the sides would model a file that cannot be produced.
    """
    reference_sources = source(
        reference_source or f"{channel_id}:reference", verified=True, fresh=True, synthetic=True
    )
    return FxChannel(
        id=channel_id,
        pair=(UAH, USD),
        reference_rate=reference,
        buy_side=buy,
        sell_side=sell,
        observed_on=FRESH,
        kind=kind,
        provenance=Provenance(
            reference_sources.sources | buy.provenance.sources | sell.provenance.sources
        ),
    )


def fixture_channels() -> Mapping[str, FxChannel]:
    """Both declared forms, so a fixture graph exercises the same two the shipped data does.

    ``p2p`` quotes a signed premium per unit -- the form the owner actually reads off a screen
    -- and ``card`` quotes a markup in basis points. The renderer must show each in its own
    unit and convert neither into the other.
    """
    return {
        "p2p": channel(
            "p2p",
            buy=side(premium=3.0, source_id="p2p:buy"),
            sell=side(premium=-2.5, source_id="p2p:sell"),
        ),
        "card": channel(
            "card",
            buy=side(bps=150.0, source_id="card:buy", kind=SLOW_KIND),
            sell=side(bps=150.0, source_id="card:sell", kind=SLOW_KIND),
        ),
    }


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
    channel_id: str = "p2p",
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
        channel=channel_id if converts else None,
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
    channel_id: str = "p2p",
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
                channel_id=channel_id,
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
        channels=fixture_channels(),
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
        channels=fixture_channels(),
        regime=Regime(id=REGIME_ID, route_ids=frozenset(routes)),
        kinds=declared_kinds(),
    )


STALE_PREMIUM_ROUTE: Final = "r_fresh_fee_stale_premium"


def stale_premium_registry() -> Registry:
    """One ``fx`` leg whose own fee schedule is fresh and whose **premium** is stale.

    The case the marks would miss if an edge were marked from its leg alone. On the §4.3.1
    corridor every declared fee is zero and the premium is the whole cost, so a diagram that
    marked the leg's fee schedule fresh and said nothing about a premium last seen years ago
    would render the most decision-relevant stale figure in the registry as current.

    The premium ages under ``p2p_premium`` (7 days) and the fee and the reference rate under
    ``bank_fee_schedule`` (365) -- three thresholds across three tables, which is exactly why
    FR-028 declares them per kind.

    **The premium is :data:`EIGHTY_TWO_DAYS_AGO` old, and that number is the point.** At 82 days
    it is stale under the side's own 7-day threshold and *current* under the 365-day one the
    channel declares for its reference rate. A renderer that aged the channel's whole provenance
    under the channel's kind -- the collapse ``cost._channel_verdicts`` exists to prevent --
    renders this edge clean. An older premium would be stale under both thresholds and would let
    that collapse pass unnoticed, which is what happened to the first version of this fixture.
    """
    quote = channel(
        "p2p",
        buy=side(premium=3.0, source_id="p2p:buy:stale", retrieved_on=EIGHTY_TWO_DAYS_AGO),
        sell=side(premium=-2.5, source_id="p2p:sell:stale", retrieved_on=EIGHTY_TWO_DAYS_AGO),
    )
    venues = {v.id: v for v in (venue("alpha", UAH, USD), venue("beta", UAH, USD))}
    routes = {
        STALE_PREMIUM_ROUTE: route(
            STALE_PREMIUM_ROUTE,
            origin="alpha",
            destination="beta",
            provenance=source("s_fresh_fee", verified=True, fresh=True, synthetic=False),
            kind_of_observation=SLOW_KIND,
            from_ccy=UAH,
            to_ccy=USD,
        )
    }
    return Registry(
        venues=venues,
        routes=routes,
        channels={"p2p": quote},
        regime=Regime(id=REGIME_ID, route_ids=frozenset(routes)),
        kinds=declared_kinds(),
    )


FORGERY: Final = "marks: VERIFIED AND CURRENT"
"""A declared string that is, character for character, a clean honesty mark.

Not a hypothetical about a malicious actor. It is the shape of the guarantee the whole feature
rests on: if declared content can read as the renderer's own voice, then no mark on any diagram
means anything, and the mislabelled figure this project exists to refuse has a second way in.
"""

FORGED_VENUE: Final = "v_forged"
FORGED_ROUTE: Final = "r_forged"


def forged_registry() -> Registry:
    """A venue *name* and a route *provider* that both spell a clean mark.

    Both were rendered as **bare, unprefixed declared text**, so neither needed the field
    separator to forge a field -- escaping the separator closed one route to the forgery and
    left these two open. The route is declared closed and unverified, so its real marks are
    ``UNVERIFIED + CLOSED``: a label that also reads clean is reading the declaration, not the
    renderer.
    """
    venues = {
        v.id: v
        for v in (
            Venue(id=FORGED_VENUE, name=FORGERY, currencies=frozenset({UAH})),
            venue("beta", UAH),
        )
    }
    routes = {
        FORGED_ROUTE: replace(
            route(
                FORGED_ROUTE,
                origin=FORGED_VENUE,
                destination="beta",
                provenance=source("s_forged", verified=False, fresh=True, synthetic=False),
                kind_of_observation=SLOW_KIND,
                status="closed",
            ),
            provider=FORGERY,
        )
    }
    return Registry(
        venues=venues,
        routes=routes,
        channels={},
        regime=Regime(id=REGIME_ID, route_ids=frozenset(routes)),
        kinds=declared_kinds(),
    )


CARD_IN_ROUTE: Final = "r_card_buy"
CARD_OUT_ROUTE: Final = "r_card_sell"


def card_registry() -> Registry:
    """Both sides of a **basis-point** channel, in one registry.

    The form that carries no direction of its own. ``markup_bps`` is a *cost magnitude*: the
    engine adds it on the buy side and subtracts it on the sell side, so the identical declared
    ``150.0`` describes an edge that charges +1.5% and an edge that charges -1.5%. Rendering the
    number alone draws the two identically and draws the sell side backwards.

    Two routes, one each way, so a test can compare the two labels. The shipped registry cannot
    do this: it declares exactly one leg through the ``card`` channel and it is buy-side, so no
    golden would ever show the case.
    """
    quote = channel(
        "card",
        buy=side(bps=150.0, source_id="card:buy", kind=SLOW_KIND),
        sell=side(bps=150.0, source_id="card:sell", kind=SLOW_KIND),
    )
    venues = {v.id: v for v in (venue("alpha", UAH, USD), venue("beta", UAH, USD))}
    cited = source("s_card", verified=True, fresh=True, synthetic=False)
    routes = {
        r.id: r
        for r in (
            route(
                CARD_IN_ROUTE,
                origin="alpha",
                destination="beta",
                provenance=cited,
                kind_of_observation=SLOW_KIND,
                from_ccy=UAH,
                to_ccy=USD,
                partner_route=CARD_OUT_ROUTE,
                channel_id="card",
            ),
            route(
                CARD_OUT_ROUTE,
                origin="beta",
                destination="alpha",
                provenance=cited,
                kind_of_observation=SLOW_KIND,
                direction="exit",
                from_ccy=USD,
                to_ccy=UAH,
                channel_id="card",
            ),
        )
    }
    return Registry(
        venues=venues,
        routes=routes,
        channels={"card": quote},
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
        channels=registry.channels,
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


def shipped_spendable() -> frozenset[SpendableEndpoint]:
    """The owner's declared spendable endpoints, read from ``data/`` like every other input.

    Costing consults it since feature 004: a destination that is itself somewhere the owner
    spends satisfies its own exit requirement (003 FR-002), which is the ``EXIT_BY_IDENTITY``
    case. Loaded rather than restated, so a hand-written copy here cannot disagree with the file
    while a diagram built on it still looks authoritative.
    """
    owner_id, endpoints = loader.spendable_from_file(DATA_ROOT / "spendable" / "owner-001.toml")
    assert owner_id == OWNER_ID, owner_id
    return frozenset(endpoints)


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


def fields_of(label: str) -> list[str]:
    """One label split into the fields the renderer composed it from."""
    return label.split(" · ")


def marks_of(label: str) -> str:
    """The renderer's own marks field, found by **position in the grammar**, not by substring.

    The strongest available reading of a label's marks: exactly one field may begin with the
    reserved token, because :func:`mermaid.escape` takes that token out of declared text. A
    label with two is a forgery and a loud failure here rather than a quiet wrong answer.
    """
    found = [field for field in fields_of(label) if field.startswith("marks: ")]
    assert len(found) == 1, (label, found)
    return found[0]


def marks_in(label: str) -> str:
    """Every marks field of a label -- or of several joined labels -- and nothing else.

    **The sound way to ask a diagram what it is marked.** ``token in label`` searches the whole
    label, declared names included, so a route whose provider is literally
    ``marks: VERIFIED AND CURRENT`` answers yes to "is this clean?" while its real marks field
    says ``UNVERIFIED + CLOSED``. The grammar already makes the marks field unambiguous -- one
    per label, opened by a token no declaration can contain -- so an assertion should read that
    field rather than hunt for words.
    """
    return "\n".join(marks_of(one) for one in label.splitlines())


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
"""The shipped **inbound** route declaring no ``partner_route``, so costing anything that ends
on it yields ``ExitCostUnknown`` -- the state FR-010 and SC-007 are about. It exists only under
the ``normalized`` regime, which is what makes it the regime-exclusion fixture too.

**Reached as the second segment of a chain, not on its own.** The dollar contract income arrives
at ``deel`` (the owner's actual flow, corrected 2026-08-23), so no stream starts where this route
starts and ``cost_one`` refuses it as a single-route path -- correctly, and loudly. The way in is
``deel_to_coinbase`` first, which is why :data:`NO_PARTNER_CHAIN` and not a bare ``FundingPath``.
"""

NO_PARTNER_CHAIN: Final = ComposedPath(
    destination_id="ibkr_usd",
    stream_id=USD_STREAM,
    segments=("deel_to_coinbase", NO_PARTNER_ROUTE),
)
"""The dollar income's way to the broker: two declared routes, joined at ``coinbase``.

Both halves are shipped declarations and neither declares a partner, so the chain has a real
one-way figure and no round-trip figure at all -- FR-030 stated by the registry rather than by a
fixture. ``deel_to_coinbase`` charges nothing and ``coinbase_to_ibkr`` charges 0.5% plus a flat
25 USD, so the total is genuinely non-zero while the conversion component is exactly zero: the
chain is dollars end to end.
"""

AMOUNT: Final = 10_000.0
"""What the golden path sends. Shared with ``tests/golden/test_ramp_comparison.py`` so the two
artifacts describe the same journey."""


def costed(
    declared: resolver.RampDeclarations,
    *,
    path: Candidate,
    amount: float,
    currency: Currency = UAH,
) -> RampCost | RouteUnusable:
    """One candidate costed through feature 002's one costing function.

    Through ``cost_one`` rather than by hand: a costed-path diagram must show *the result's*
    figures, so a fixture that built a ``RampCost`` itself would be testing the renderer
    against numbers nobody computed.

    A ``Candidate`` rather than a route id, because the shipped registry now needs both shapes:
    the §4.3.1 corridor is one declared route and the way to the broker is a chain of two.
    """
    return cost.cost_one(
        path,
        Money(amount, currency, prov.EMPTY),
        routes=declared.routes,
        channels=declared.channels,
        streams=declared.streams,
        kinds=declared.kinds,
        on_date=AS_OF,
        as_of=AS_OF,
        spendable=shipped_spendable(),
    )


def p2p_cost(declared: resolver.RampDeclarations | None = None) -> RampCost:
    """The §4.3.1 round trip, costed. A ``RouteUnusable`` here is a fixture failure."""
    result = costed(
        declared if declared is not None else shipped_declarations(),
        path=FundingPath(destination_id="binance", stream_id=UAH_STREAM, route_id=P2P_ROUTE),
        amount=AMOUNT,
    )
    assert isinstance(result, RampCost), result
    return result


def exit_unknown_cost(declared: resolver.RampDeclarations | None = None) -> RampCost:
    """A costed journey whose exit nobody has declared: one way real, round trip absent."""
    result = costed(
        declared if declared is not None else shipped_declarations(),
        path=NO_PARTNER_CHAIN,
        amount=1_000.0,
        currency=USD,
    )
    assert isinstance(result, RampCost), result
    return result


CostedOutcome = RampCost | RouteUnusable | ExitCostUnknown | NothingComparable
"""Everything ``render_path`` accepts: one costed result, or one of the three refusals."""


STALE_PREMIUM_AS_OF: Final = date(2026, 11, 12)
"""82 days after the shipped declarations were retrieved (2026-08-22).

Chosen so exactly one kind of observation on the §4.3.1 corridor has gone stale: the ``p2p``
premium, whose threshold is 7 days. The route's own legs age under ``regulatory_limit`` (180)
and ``bank_fee_schedule`` (365) and are still current. So a costed path at this date has a
**stale premium on fresh legs** -- the case where matching a verdict against the leg's own
sources alone leaves the stale figure invisible on the edge that charges it.
"""


def stale_premium_cost() -> RampCost:
    """The §4.3.1 corridor costed late enough that only its premium has aged.

    Costed through ``cost_one`` like every other fixture here, so the verdict the diagram reads
    is the verdict feature 002 produced -- not one this module invented to suit an assertion.
    """
    declared = shipped_declarations()
    result = cost.cost_one(
        FundingPath(destination_id="binance", stream_id=UAH_STREAM, route_id=P2P_ROUTE),
        Money(AMOUNT, UAH, prov.EMPTY),
        routes=declared.routes,
        channels=declared.channels,
        streams=declared.streams,
        kinds=declared.kinds,
        on_date=AS_OF,
        as_of=STALE_PREMIUM_AS_OF,
        spendable=shipped_spendable(),
    )
    assert isinstance(result, RampCost), result
    return result


def unassessed_cost() -> RampCost:
    """The §4.3.1 corridor costed, then handed a verdict that never aged its channel.

    Built by ``replace``-ing the verdict rather than by costing, because ``cost._aged`` assesses
    every observation on every leg -- so no real run produces this. It is the shape a *caller*
    can produce: a result whose staleness verdict is narrower than the figures the diagram
    draws, which is the one case where "checked and clean" and "nobody checked" must not
    collapse into the same green tick (``staleness.UNASSESSED``).

    The fee schedules stay assessed and the channel's sources are dropped, so the ``fx`` edge
    must say its age was not assessed while the ``transfer`` edge beside it stays clean.
    """
    declared = shipped_declarations()
    result = p2p_cost(declared)
    leg_sources = sorted(
        ref.id
        for route_id in (P2P_ROUTE, "binance_p2p_to_monobank")
        for leg in declared.routes[route_id].legs
        for ref in leg.provenance.sources
    )
    return replace(
        result,
        one_way=replace(
            result.one_way,
            staleness=StalenessVerdict(assessed=tuple(leg_sources), stale=()),
        ),
    )


def path_of(result: CostedOutcome, *, regime_id: str = "wartime") -> Diagram | NothingToDraw:
    """Render a costed result under one declared regime."""
    declared = shipped_declarations()
    return render_path(
        result,
        routes=declared.routes,
        channels=declared.channels,
        regime=shipped_regime(declared, "war_end", regime_id),
    )


def drawn_path(result: CostedOutcome, *, regime_id: str = "wartime") -> Diagram:
    """The same, narrowed -- a refusal here is the test's finding, not its input."""
    rendered = path_of(result, regime_id=regime_id)
    assert isinstance(rendered, Diagram), rendered
    return rendered


# --- composed candidates (feature 004) --------------------------------------------------

HOP_ONE: Final = "r_hop_one"
HOP_TWO: Final = "r_hop_two"
BACK_ONE: Final = "r_back_one"
BACK_TWO: Final = "r_back_two"
CHAIN_STREAM: Final = "wages"

CHAIN_IN: Final = ComposedPath(
    destination_id="gamma", stream_id=CHAIN_STREAM, segments=(HOP_ONE, HOP_TWO)
)
"""Two declared routes, joined at a venue where the currency also matches.

**Hand-built rather than enumerated.** The shipped registry does compose since 2026-08-23 --
``deel_to_coinbase`` into ``coinbase_to_ibkr`` is a real chain, and :data:`NO_PARTNER_CHAIN`
uses it -- but that one chain is a *dollar* journey with no declared exit, so it can state
neither the composed-exit case nor the exit-by-identity case. This fixture exists to hold the
shapes the declarations do not: a chain in with a chain back out, over venues invented for the
purpose. ``ComposedPath`` is an ordinary input to ``cost_one``, the search that finds them is
feature 004's and is tested there, and what this feature has to prove is that a chain *draws*
honestly.
"""

CHAIN_OUT: Final = ComposedExit(segments=(BACK_ONE, BACK_TWO))
"""And a chain of declared **exit** routes back to somewhere the owner spends (004 FR-012)."""


def _chain_registry() -> tuple[
    Mapping[str, Venue], Mapping[str, Route], Mapping[str, IncomeStream]
]:
    """Three venues and four declared routes: two hops out, two hops back.

    ``alpha`` holds hryvnia and is where the wages land; ``gamma`` holds dollars and is the
    destination nobody declared a direct corridor to. The hop that converts carries a fee as
    well as a premium, so the by-segment attribution has something to distinguish -- a chain
    whose every segment charged zero would make "which hop dominates" unanswerable and the
    second axis of attribution pointless to render.
    """
    venues = {v.id: v for v in (venue("alpha", UAH), venue("beta", UAH, USD), venue("gamma", USD))}
    cited = source("s_chain", verified=True, fresh=True, synthetic=True)
    routes = {
        r.id: r
        for r in (
            route(
                HOP_ONE,
                origin="alpha",
                destination="beta",
                provenance=cited,
                kind_of_observation=SLOW_KIND,
                from_ccy=UAH,
                fee_pct=0.01,
                fee_fixed=5.0,
                # So the fixture can also produce 002's original way out -- one declared
                # partner -- and all three ``ExitChain`` members are reachable from one
                # registry. Never consulted by the composed cases, which name their exit.
                partner_route=BACK_TWO,
            ),
            route(
                HOP_TWO,
                origin="beta",
                destination="gamma",
                provenance=cited,
                kind_of_observation=SLOW_KIND,
                from_ccy=UAH,
                to_ccy=USD,
            ),
            route(
                BACK_ONE,
                origin="gamma",
                destination="beta",
                provenance=cited,
                kind_of_observation=SLOW_KIND,
                direction="exit",
                from_ccy=USD,
                to_ccy=UAH,
            ),
            route(
                BACK_TWO,
                origin="beta",
                destination="alpha",
                provenance=cited,
                kind_of_observation=SLOW_KIND,
                direction="exit",
                from_ccy=UAH,
            ),
        )
    }
    streams = {
        CHAIN_STREAM: IncomeStream(
            id=CHAIN_STREAM,
            owner_id=OWNER_ID,
            amount=Money(0.0, UAH, prov.EMPTY),
            cadence="monthly",
            arrives_at="alpha",
            indexation=Indexation(policy="none", rate=None),
            income_tax_rate=None,
        )
    }
    return venues, routes, streams


def chain_regime() -> Regime:
    """A regime that includes every segment of both halves. See ``path._in_force``."""
    _, routes, _ = _chain_registry()
    return Regime(id=REGIME_ID, route_ids=frozenset(routes))


def chain_routes() -> Mapping[str, Route]:
    _, routes, _ = _chain_registry()
    return routes


def _chain_cost(
    *, exit_path: ExitChoice, spendable: frozenset[SpendableEndpoint], path: Candidate = CHAIN_IN
) -> RampCost:
    venues, routes, streams = _chain_registry()
    assert venues
    result = cost.cost_one(
        path,
        Money(AMOUNT, UAH, prov.EMPTY),
        routes=routes,
        channels=fixture_channels(),
        streams=streams,
        kinds=declared_kinds(),
        on_date=AS_OF,
        as_of=AS_OF,
        spendable=spendable,
        exit_path=exit_path,
    )
    assert isinstance(result, RampCost), result
    return result


def composed_cost() -> RampCost:
    """A composed way in and a composed way out, costed by the one costing function."""
    return _chain_cost(
        exit_path=CHAIN_OUT,
        spendable=frozenset({SpendableEndpoint(venue_id="alpha", currency=UAH)}),
    )


def identity_exit_cost() -> RampCost:
    """A composed way in to a destination that **is** a declared spendable endpoint.

    ``EXIT_BY_IDENTITY``: the money is already where it needed to come back out to, so the exit
    chain has no segments and the round-trip figure equals the one-way figure. Not a way out
    that happened to be free -- there is no way out to cost.
    """
    return _chain_cost(
        exit_path=EXIT_BY_IDENTITY,
        spendable=frozenset({SpendableEndpoint(venue_id="gamma", currency=USD)}),
    )


def declared_exit_chain_cost() -> RampCost:
    """One declared route in, one declared route out -- 004's ``DeclaredExit``, on the fixture.

    Here so the three ``ExitChain`` members are all reachable from one registry, and so the
    composed cases can be compared against a declared one that shares their venues.
    """
    return _chain_cost(
        path=FundingPath(destination_id="beta", stream_id=CHAIN_STREAM, route_id=HOP_ONE),
        exit_path=FROM_THE_DECLARATION,
        spendable=frozenset({SpendableEndpoint(venue_id="alpha", currency=UAH)}),
    )


def chain_path_of(result: CostedOutcome) -> Diagram:
    """Render a fixture journey under the regime that includes every one of its segments."""
    rendered = render_path(
        result,
        routes=chain_routes(),
        channels=fixture_channels(),
        regime=chain_regime(),
    )
    assert isinstance(rendered, Diagram), rendered
    return rendered
