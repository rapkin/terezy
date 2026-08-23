# Phase 0 research: composed paths

**Feature**: `004-composed-paths` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

All three clarifications were resolved by the owner on 2026-08-22 and a fourth gap was
closed by external review, so nothing here is a `NEEDS CLARIFICATION`. What follows are
the decisions the plan rests on. Two of them (D3, D9) resolve tensions that features 002
and 003 recorded as future work; both are called out as such, because a reader will
otherwise find a `[[future]]` entry in `features.toml` describing a problem this feature
already fixed.

---

## D1 — Composition is enumeration in `core/routes/`, and it produces no new arithmetic

**Decision.** `core/routes/compose.py` enumerates candidates; `core/routes/cost.py` costs
them, unchanged in what it computes. No new package, no new plugin interface.

**Rationale.** FR-003 and FR-004 say a composed candidate must behave exactly as a
declared route with the same concatenated legs would. The cheapest way to guarantee that
is to make it *literally* that: enumeration produces a leg sequence, and the existing
`_walk` fold consumes it. Anything that gave composition its own costing path would make
SC-002's "asserted by construction" impossible to assert.

**Alternatives rejected.** A `core/paths/` package: composition is a question about routes
and belongs beside them. Costing composed candidates through a wrapper that sums segment
costs: that is a second arithmetic, and the rounding of a sum of sums is not the rounding
of a single fold — 002's cost attribution invariant would start failing for composed
candidates only, which is exactly the "different path for different candidates" FR-003
forbids.

## D2 — The path type widens; `FundingPath` is not repurposed

**Decision.** `core/routes/path.py` gains `ComposedPath(destination_id, stream_id,
segments: tuple[str, ...])` beside the existing `FundingPath`, and a
`Candidate = FundingPath | ComposedPath` alias. `RampCost.path` becomes `Candidate`.

**Rationale.** FR-013: a composed candidate is visibly distinct from a declared route in
every ranking, report and recommendation, and the distinction is **structural, not
decorative**. Two types matched on with `match` is structural; a `FundingPath` whose
`route_id` sometimes holds one id and sometimes a joined string is decorative and
unparseable. It also keeps 002's `FundingPath` meaning exactly what it meant, so no
existing consumer silently changes behaviour.

`path.py` rather than `results/composed.py` because `results/ramp.py` already imports
`FundingPath` from there; putting the union anywhere else creates a cycle.

## D3 — The ranked unit is `(destination × stream × inbound path × exit chain)`

**Decision.** One `RampCost` per inbound candidate **per exit chain**. `RampCost` gains
`exit_path: ExitChain`, and `round_trip` stays a single `RoundTripCost | ExitCostUnknown`.
Two exit chains from one destination are two `RampCost` records in the one candidate set,
ranked together.

**Rationale.** FR-012 says two exit chains are two round-trip figures, never blended, and
FR-010 says one ranking. Those two are only compatible if the exit chain is part of the
ranked item's identity: a record holding several round-trip figures has no defined
position in a ranking ordered by round-trip cost, and the first thing an implementer
would do is pick one — which is the blend FR-012 forbids, arrived at by accident.

**What this preserves.** A declared route with exactly one declared `partner_route`
produces exactly one `RampCost`, as in 002. The shape widens; the behaviour for 002's
registries does not, and 002's golden file is the check.

## D4 — An exit chain has three shapes, and the third resolves a recorded tension

**Decision.** `ExitChain` is a tagged union:

- `DeclaredExit(route_id)` — 002's single declared partner route;
- `ComposedExit(segments: tuple[str, ...])` — FR-012's chain of declared exit routes;
- `EXIT_BY_IDENTITY` — a sentinel: the destination **is** a declared spendable endpoint,
  so no exit is required and none is composed.

**Rationale for the third, which is not in this spec's text.** Feature 003's FR-002, by
owner decision of 2026-08-23, says a destination that is itself a declared spendable
endpoint satisfies its own exit requirement — the money is already where it needed to come
back out to. `features.toml` records the consequence as
`identity-exit-vs-partner-requirement`: coverage calls such a pair ready while costing,
which requires a declared partner, refuses it with `ExitCostUnknown` — the disagreement
FR-018 says must not exist. That entry names composition as the thing that makes it real,
and composition is this feature. So it is resolved here rather than deferred again.

**It must be visibly the identity case, never a computed zero.** A round trip whose exit
costs nothing because there is nothing to do is a different claim from one whose exit
costs nothing because its fees happened to cancel. The sentinel carries that difference;
a zero-length `ComposedExit` would erase it.

**The `[[future]]` entry is closed by this feature**, and the landing change says so
rather than leaving a solved problem on the list.

## D5 — Enumeration: depth-first over an adjacency index, deterministic by construction

**Decision.** Per `(regime, direction)`, build an index from `(venue, currency)` to the
declared routes departing there, with each bucket sorted by route id. Enumerate
depth-first, carrying the set of visited venues; emit a chain when its last segment ends at
the target `(venue, currency)`; stop descending at the declared bound.

**Rationale.** FR-007 requires exhaustiveness within the bound and FR-008 requires that
enumeration order influence nothing. Sorting the buckets makes the emitted order a function
of the declarations alone — not of dict iteration, not of file order. Depth-first with a
visited-venue set is the direct expression of FR-005's cycle rule; nothing is pruned by
cost, which is FR-003's requirement that no heuristic touch the search.

**No memoisation of partial costs.** Out of scope names it, and the reason is worth
keeping: a partial cost is only valid for one amount, because minimums, caps and fixed fees
are not linear. A cache keyed by anything less than the full amount would be an invented
number the first time it hit.

## D6 — Duplicate suppression compares leg chains with `index` normalised

**Decision.** A composed candidate is dropped when its concatenated leg sequence equals a
declared route's, comparing every leg field **except `index`**, which is re-numbered across
the concatenation before the comparison.

**Rationale.** FR-009. The trap is that `Leg.index` is per-route, so concatenating a
two-leg and a one-leg route gives indices `0,1,0` where the declared equivalent has
`0,1,2`. A naive tuple equality never matches, the duplicate is never suppressed, and the
ranking holds the same real-world movement twice — which SC-013 checks for. Normalise
first, compare second, and say so at the site.

## D7 — Attribution gains a segment axis; the components axis is unchanged

**Decision.** `SegmentAttribution(position, route_id, components: Mapping[CostComponent,
Money])`, one per segment, on both `OneWayCost` and `RoundTripCost`. The existing
`components` mapping stays exactly what it is: the whole-candidate total by component.

**Rationale.** FR-020 wants both axes — which component and which segment — and SC-014
wants the dominating segment named. Two flat mappings, each summing to the same total, is
the smallest shape that gives both, and it extends 002's cost-attribution invariant
naturally: components sum to the total, and segments sum to the total, and a leg cannot
hide in either. A nested `Mapping[segment, Mapping[component, Money]]` carries no more
information and makes the invariant harder to state.

A declared route is one segment. That is not a special case in the code and must not be
one: SC-002's "same costing function" applies to attribution too.

## D8 — The segment bound is per-owner policy data, in its own directory

**Decision.** `data/composition/owner-001.toml`, carrying `[owner] id` and
`[composition] max_segments`. Required; no default; malformed or missing fails at load
naming file and field. Added to `EXEMPT_DIRS` in `scripts/check_provenance.py` with its
reason recorded.

**Rationale.** FR-006 and the spec's own analogy to 002 FR-028's refusal of a default
staleness threshold. It is *policy*, in the sense `objectives` and `strategies` already
are — a number the owner chooses, not a number observed in the world — so it carries no
citation and belongs in the exemption list with that reason written beside it, exactly as
feature 003's `spendable` does.

**Per-owner, not root-level**, on feature 003's precedent (its research D3): how far this
person is willing to let a search run is a fact about him, not about the corridors.

**A bound of 1 is legal and means composition is off** (spec edge case). It is not the
same as a missing bound, which is a load failure — the difference between a choice and a
forgotten line, which this project refuses to conflate anywhere.

## D9 — The bound is per chain, and the two chains are enumerated independently

**Decision.** An inbound candidate obeys the bound on its own; an exit chain obeys it on
its own. There is no shared budget across the pair.

**Rationale.** The spec's Assumptions fix this, and the reason is worth restating at the
site: a shared budget would make an inbound path's reachability depend on which exit chain
it happens to be paired with, entangling two independently declared facts. It also makes
the enumeration two independent problems, which is why the same function serves both with
`direction` as a parameter (FR-022).

## D10 — Directions never mix, and the check is in the index, not in a filter

**Decision.** The adjacency index is built **per direction**. An inbound enumeration cannot
see an exit route because it is not in the index it walks.

**Rationale.** FR-022. A post-hoc filter over mixed candidates is the version that gets
one condition wrong under a refactor; an index that never contained the wrong routes cannot
emit them. Same reasoning as 003's decision to find exits by direction rather than by
following `partner_route`.

## D11 — Capacity pools compose for free, and the test is what proves it

**Decision.** No new pool logic. The concatenated leg sequence goes through 002's existing
accumulator, which is keyed by capacity pool and threaded through the fold.

**Rationale.** FR-016 and SC-007. Because the fold is unchanged and the accumulator is
keyed by pool rather than by route, two legs in different segments naming one pool already
share headroom. This is a claim about 002's design surviving contact with composition, so
it lands as a hand-computed worked example rather than as an assertion that the code was
not changed.

## D12 — No path-level disruption, and no field to put one in

**Decision.** Per-leg disruption is reported as 002 reports it. `RampCost` gains no
combined probability, and there is no field a later contributor could fill with one.

**Rationale.** FR-019 and SC-011. Combining per-leg probabilities requires an independence
assumption nobody declared. The structural version of the refusal — no field — is worth
more than a comment, because the comment is what gets deleted when someone "just needs a
single number for the ranking".

## D13 — Composition reads the spendable list; it does not read feature 003

**Decision.** `compose` takes `spendable: frozenset[SpendableEndpoint]` as a parameter.
`core/routes/coverage.py` is not imported, and the coverage report is not consulted.

**Rationale.** The spec's Assumptions: this feature depends on the *concept* of a spendable
endpoint, not on feature 003's artifacts. Importing the audit to decide where an exit chain
may end would couple a costing question to a reporting one and make the ranking depend on a
report — which FR-019 of feature 003 explicitly forbids in the other direction.
`SpendableEndpoint` is a plain record in `core/results/coverage.py`; using the type is not
using the report.
