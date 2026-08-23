# Contract: `compose`, and what costing guarantees over its output

**Feature**: `004-composed-paths` | **Modules**: `terezy.core.routes.compose`, `terezy.core.routes.cost`

## Signatures

```python
def compose(
    *,
    routes: Mapping[str, Route],
    stream: IncomeStream,
    destination: Destination,
    direction: RouteDirection,
    regime: Regime,
    bound: SegmentBound,
    spendable: frozenset[SpendableEndpoint],
) -> Enumeration | CompositionRefused

def legs_of(candidate: Candidate, routes: Mapping[str, Route]) -> tuple[Leg, ...]
```

`legs_of` is the whole of "composition adds no arithmetic": it turns either kind of
candidate into one leg sequence, re-indexed across the concatenation, and `cost_one` walks
that sequence exactly as it always did. There is no second costing path to keep in step.

`spendable` is a parameter, not a lookup into feature 003 (research.md D13).

## Guarantees

**G1 — Connectivity is exact.** Adjacent segments join only where the destination venue and
arriving currency of one equal the origin venue and departing currency of the next. A
junction never converts, charges or waits. (FR-001, FR-002)

**G2 — Nothing is invented.** No rate, fee, cap, minimum, latency, status, window or
probability exists on a composed candidate that does not exist on one of its segments. No
implicit conversion, no bridging leg. (FR-002)

**G3 — One costing function.** Every candidate is costed by `cost_one` over `legs_of`.
Asserted by construction, not by comparing numbers that agree. (FR-003, SC-002)

**G4 — Directions never mix.** The adjacency index is per direction, so an inbound
enumeration cannot see an exit route. (FR-022, research.md D10)

**G5 — No venue twice.** Verified over the entire emitted set. (FR-005)

**G6 — Exhaustive within the bound, and the bound is visible.** Every connectable chain of
at most `max_segments` segments is emitted; none longer is; the bound travels with the
results. (FR-006, FR-007)

**G7 — Deterministic.** Same registry, bound, regime and as-of date produce the same
candidates in the same order, and that order influences no figure, position, recommendation
or tie. Reversing the declaration order changes nothing. (FR-008, SC-003)

**G8 — No duplicate leg chain.** A composed concatenation identical leg-for-leg to a
declared route is not emitted; the declared route stands. Compared with `Leg.index`
normalised. (FR-009, research.md D6)

**G9 — One ranking.** Composed candidates enter 002's lexicographic ranking with no bonus,
no penalty and no separate league; ties are 002's ties. (FR-010)

**G10 — Keyed per `(destination × stream × path × exit chain)`.** A cost attributed to a
destination alone stays unrepresentable. (FR-011, FR-012, 002 FR-008)

**G11 — A round trip exists exactly when an exit chain does.** `DeclaredExit`,
`ComposedExit`, or `EXIT_BY_IDENTITY` when the destination is itself spendable. Where none
exists, `ExitCostUnknown` stands and no one-way figure is promoted. (FR-012, 002 FR-030)

**G12 — Feasibility binds per segment and names it.** A closed, disrupted or out-of-window
segment excludes the candidate with the binding segment recorded. (FR-015)

**G13 — Pools bind jointly.** Two legs in different segments naming one pool consume one
headroom, and headroom spent earlier in the month applies. (FR-016, research.md D11)

**G14 — One regime.** Every segment belongs to the route set of the regime in force on the
date; no candidate mixes route sets across a transition. (FR-017)

**G15 — Provenance survives the join.** An unverified value on any segment marks every
figure derived from it on the candidate; staleness is evaluated per value by its kind. A
join launders nothing. (FR-018)

**G16 — Attribution names component and segment.** Both mappings sum to the same total.
(FR-020, SC-014)

**G17 — Nothing is declared, fabricated or persisted.** (FR-021)

## The two reconciliations this feature closes

**`identity-exit-vs-partner-requirement`** (recorded 2026-08-23). Feature 003's FR-002 lets
a spendable destination satisfy its own exit; 002's costing required a declared partner, so
coverage said ready where costing refused — the disagreement 003 FR-018 forbids.
`EXIT_BY_IDENTITY` closes it: costing now produces a round trip for exactly the pairs
coverage calls ready by identity. The landing change removes the `[[future]]` entry rather
than leaving a solved problem on the list.

**003's FR-018 forward note.** 003 marks not-ready any pair reachable only by composition,
and promised the reconciliation would be a distinct *"reachable by composition only"*
annotation computed from declarations — never a change to what `Ready` means. **This feature
does not implement that annotation**, and must not quietly make coverage aware of
composition instead. It is 003's surface to grow, on 003's terms, and it is out of scope
here. Say so where the two features meet.
