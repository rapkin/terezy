# Contract: the two renderers

**Feature**: `005-route-diagrams` | **Module**: `terezy.api.diagrams`

## Signatures

```python
def render_graph(
    *,
    venues: Mapping[str, Venue],
    routes: Mapping[str, Route],
    channels: Mapping[str, FxChannel],      # ⚙ added at implementation — see below
    regime: Regime,
    mode: Mode,
    kinds: Mapping[str, ObservationKind],   # ⚙ added at implementation — see below
    as_of: date,                            # ⚙ added at implementation — see below
) -> Diagram | NothingToDraw

def render_path(
    result: RampCost | RouteUnusable | ExitCostUnknown | NothingComparable,
    *,
    routes: Mapping[str, Route],
    channels: Mapping[str, FxChannel],      # ⚙ added at implementation — see below
    regime: Regime,
) -> Diagram | NothingToDraw
```

⚙ **`kinds` and `as_of` were added to `render_graph` during implementation, and the
signature above as first written could not satisfy G10.** Staleness is
`as_of - retrieved_on` against a **declared per-kind** threshold (FR-013, feature 002's
FR-025/FR-028), so a registry graph cannot carry a `STALE` mark without both. Three options
were weighed:

* **omit staleness from the registry graph** — rejected: FR-015 requires the five states plus
  synthetic to be *pairwise distinguishable in one diagram*, and a closed route never reaches
  a costed path, so no single diagram could then carry all of them;
* **make them optional** — rejected: an unassessed diagram would be indistinguishable from a
  clean one, which is the silent permissive default FR-028 forbids outright and the exact
  ambiguity `staleness.UNASSESSED` exists to remove;
* **require them** — taken. Both are inputs, never a clock, exactly as `cost_one` takes them,
  and the resolved `as_of` is printed on the face of the diagram.

`render_path` needs neither: `OneWayCost.staleness` and `RoundTripCost.staleness` are verdicts
feature 002 already computed under each leg's own declared threshold, so the path renderer
**reads** the result's verdict instead of recomputing it. Two computations of one fact
eventually disagree.

⚙ **`channels` was added on the owner's ruling of 2026-08-23, and the reason is the strongest
in the feature.** FR-006's with-figures mode names "fees, premiums", and a premium is declared
on an `FxChannel`. Without it, every `fx` leg of the §4.3.1 corridor rendered
`declared fee 0.00% + 0.00 UAH` — in the mode whose whole purpose is to show declared figures —
while the real declared figure, `+3.00 UAH per USD` against a `42.00` reference, is the entire
6.67% one-way cost the costed-path diagram then reports. **The registry graph drew the most
expensive corridor in the registry as free.** That is not a gap in coverage; it is the
mislabelled figure in picture form, which is the founding constraint of this whole
specification. The caption's disclaimer does not repair it: a disclaimer at the top does not
survive someone looking at one edge.

The prohibition in FR-006 does not reach it. What that requirement forbids on a registry graph
is a **computed ramp cost**, which exists only per `(destination × stream × route)` — a triple
this diagram does not name. A channel premium is a *declared observation* with its own source,
its own verification date and its own `kind`, exactly like a leg fee, and it carries its own
marks and its own staleness accordingly: a stale premium on a fresh-fee leg never renders
clean.

Both declared side forms render, each in the unit its declaration used and neither converted
into the other (converting would be the renderer deriving a figure, and would erase which form
the file actually used). The two rules for them live in `numbers.py` with the other three —
see `data-model.md`.

⚙ **And `render_path` takes `channels` for the same reason, added on review.** The first
implementation applied the ruling to the registry graph only, leaving the costed path — the
diagram where the cost actually lives — drawing the §4.3.1 fx leg as `declared fee 0.00%` with
no premium at all. The argument above applies here with more force, not less: a totals node at
the top does not survive someone looking at one edge. Both renderers now compose an edge's
declared figures through the same function, so neither can gain or lose one alone.

⚙ **A rendered premium names the side taken and the direction applied.** The two declared forms
have different sign conventions: `premium_per_unit` is a signed offset both sides add, while
`markup_bps` is a cost magnitude the engine adds on the buy side and subtracts on the sell one.
Without the direction, `150.00 bps over reference 42.00 UAH per USD` is one label for an edge
charging +1.5% and an edge charging −1.5%, with the sell side drawn backwards. The phrase comes
from `channels.effective_rate`, so the picture and the arithmetic cannot disagree; the effective
rate itself is not rendered, because it is computed rather than declared (G6).

`regime` is required on both and has no default, sentinel or overload: FR-019 says a merged
graph existing under no regime must not be **producible**, and the strongest reading of that
is that no argument list expresses it.

## Guarantees

**G1 — Two kinds and no others.** The declared route graph, and one costed path. (FR-001)

**G2 — Derived, never maintained.** Every node and edge comes from the loaded declarations;
a venue or route added as data appears with zero source changes. (FR-002, FR-003, SC-002)

**G3 — Closed is visible.** A closed route is present and marked, distinct both from an open
route and from a route that does not exist. (FR-004, SC-004)

**G4 — A missing exit is drawn, not omitted.** A destination with no declared exit renders an
explicit *no exit declared* mark and is visibly not comparison-ready. (FR-005, SC-007)

**G5 — Mode is on the face of the diagram, and a computed cost is on neither mode.**
(FR-006, SC-012)

**G6 — Every figure is the input's figure through the one rule.** No computing, deriving,
aggregating or re-rounding. An edge shows a figure with its provenance state, or shows
nothing. (FR-008, FR-022, SC-006)

**G7 — Labels obey the project's labelling rules.** One-way and round-trip named wherever a
cost appears; cost and spread-over-reference never conflated. (FR-009)

**G8 — A round trip is drawn from the declared exit route**, its own legs and venues, never
the inbound reversed. *Exit cost unknown* renders as itself, in the place the exit would
occupy. (FR-010)

**G9 — A refusal is a refusal.** Typed `NothingToDraw` carrying the reason; never an empty
diagram, never a drawn path. (FR-011, SC-010)

⚙ **No input to `render_graph` produces one.** The union is the shape both renderers share, so
a caller matches once over both — but the spec turns every candidate refusal on the registry
side into either a diagram that *says* it is empty (an empty registry, a regime with no routes
— spec.md's own edge cases) or a loud failure (a regime naming an undeclared route, a leg
naming an undeclared venue, two records declaring one id). Refusals belong to costed results,
where the input is itself a typed refusal carrying a reason.

**G10 — Marks propagate and survive.** Unverified, stale and synthetic reach the diagram and
live in the label text, not only in styling. (FR-012, FR-013, FR-014, FR-015, SC-005)

**G11 — Byte-identical for identical inputs**, across separate runs and processes, per mode.
(FR-016, SC-003)

**G12 — Valid Mermaid under hostile names.** Quotes, brackets, pipes, arrows and Cyrillic in
a declared name produce valid output, and distinct declared entities stay distinct nodes.
(FR-017, FR-018, SC-008)

**G13 — One named regime per diagram.** (FR-019, SC-009)

**G14 — Rendering changes nothing.** It consumes the same records everything else consumes
and cannot alter a computed figure. (FR-020)

## Delivery surface

Exactly two places (FR-021, owner decision):

- **Golden artifacts** under `tests/golden/`, checked in and regenerated by the golden
  suite — at least one route graph and one costed path (SC-011).
- **`scripts/render_diagram.py`**, printing a requested diagram to stdout. A printer with no
  logic of its own: it parses arguments, calls the function above, prints. No file writing,
  no reports directory.

No UI. Owner decision D-B stands, and this feature is deliberately not a step toward one.
