# Contract: `coverage` and what it guarantees

**Feature**: `003-route-coverage` | **Module**: `terezy.core.routes.coverage`

## Signature

```python
def coverage(
    *,
    venues: Mapping[str, Venue],
    streams: Mapping[str, IncomeStream],
    routes: Mapping[str, Route],
    regimes: Mapping[str, Regime],
    spendable: frozenset[SpendableEndpoint],
) -> CoverageReport | RegistryDimensionEmpty | ReservedRegimeId
```

Keyword-only, on feature 002's precedent: five mappings of the same shape are trivially
swappable positionally, and a swapped pair would produce a confident wrong report rather
than a type error.

No `on_date`, no `as_of`. Coverage is a claim about declarations, not about today
(FR-022 ⚙), so there is no date for it to take — and nothing here reads a clock.

## Guarantees

**G1 — Total.** For every declared venue, every currency that venue can hold, every
declared stream and every regime, `regimes[i].verdicts` contains exactly one verdict. No
pair in the declared universe is absent, and no pair appears twice. (FR-001)

**G2 — Ready means both halves are declared.** `Ready` is returned if and only if, within
that regime, an inbound match exists (or the destination is the stream's arrival point) and
an exit exists whose end is in `spendable`. (FR-002, FR-005)

**G3 — Deficits are distinguished.** Every `NotReady` carries at least one `Deficit`, each
of one of three kinds. There is no undifferentiated "missing route" value. (FR-003)

**G4 — Nothing is composed, inferred or reversed.** No inbound route is read as an exit; no
two routes are chained; no `partner_route` link is followed. A destination whose exit ends
at a venue that itself has a spendable exit is `exit_not_spendable`, full stop. (FR-006)

**G5 — A missing declaration is writable from the report alone.** Origin venue, origin
currency, direction, and target — the destination for an inbound, `ANY_SPENDABLE` with the
candidate list for an exit. Interior hops are absent by design. (FR-007)

**G6 — No values are suggested.** No provider, fee, premium, cap, latency or rate appears
in any missing declaration. Structurally guaranteed: no such field exists. (FR-008)

**G7 — Counts are plain counts.** `TodoEntry.count == len(TodoEntry.blocked)`. No weighting,
no composite score. `todo` is ordered by descending count; equal counts appear in `ties`.
(FR-009, FR-010, required test B12)

**G8 — Necessary is not sufficient.** A pair needing two missing declarations appears in
both entries' `blocked`, with `alone_sufficient = False` in both. (FR-011)

**G9 — Per regime, never blended.** Every verdict, deficit, count and tie lives inside one
`RegimeCoverage`. `to_observe` states per-regime counts as `(regime_id, count)` pairs and
never sums them. (FR-013, FR-014)

**G10 — No regimes means one implicit regime, said out loud.** `source == "implicit"`,
`regime_id == IMPLICIT_REGIME_ID`, `route_ids` is every declared route, and
`audited.regime_ids` is empty. (FR-015)

**G11 — Pure and deterministic.** No I/O, no clock, no randomness, no costing call. Equal
inputs produce an equal report, field for field, tuple order included. (FR-016)

**G12 — No cost figure, no provenance.** No `Money`, `Provenance`, `StalenessVerdict` or
`float` is reachable from the returned value. (FR-017, FR-023)

**G13 — Traceable.** Every `Ready` names the routes it relied on with their statuses; every
`NotReady` names what is missing; `audited` names the exact declaration set. (FR-021)

**G14 — Closed counts as declared, and says so.** A route with `status == "closed"` in a
regime that names it satisfies coverage, and `Ready.rests_on` distinguishes a verdict
resting only on closed routes from one resting on open ones. (FR-022, SC-015)

**G15 — Advisory, in the output.** `enforcement` states that verdicts are advisory, that
feature 002's ranking is unaffected, and that enforcement is a deferral. Calling `coverage`
has no effect on any costing or ranking result. (FR-019)

**G16 — Empty is typed, never empty.** An empty `venues`, `streams`, `routes` or `spendable`
returns `RegistryDimensionEmpty` naming every empty dimension. There is no input for which
`coverage` returns a report with no verdicts. (FR-020, defect B10)

## Agreement with costing (FR-018, SC-009)

Scoped, deliberately, to **costing over single declared routes as of this feature**
(research.md D11):

- For every pair marked `Ready`, there exists a `FundingPath` over one of the relied inbound
  routes for which `cost_one` yields a `RampCost` whose `round_trip` is a `RoundTripCost` —
  given an amount and dates at which no feasibility constraint binds.
- For every pair marked `NotReady`, either no `FundingPath` over a declared route matches
  the stream and destination at all, or every one that does yields `ExitCostUnknown`.

Feasibility refusals (`RouteUnusable`: below a minimum, above a cap, outside a window) are
**out of scope of this agreement**. They are statements about today, and coverage is a
statement about declarations. The property test states this at the assertion site.

When feature 004 lands composition, costing will produce round-trip figures for pairs this
report marks not-ready. The reconciliation is a distinct "reachable by composition only"
annotation computed from declarations alone — never a change to what `Ready` means, and
never a blended verdict. This paragraph is the note the 004 author is expected to find.

## Helper contracts

```python
def destinations(venues: Mapping[str, Venue]) -> tuple[Destination, ...]
def is_spendable(endpoint: Destination, spendable: frozenset[SpendableEndpoint]) -> bool
def blocked_count(entry: TodoEntry) -> int
```

Free functions over frozen records, per owner decision D-E. No class carries behaviour.
