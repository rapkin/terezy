# Phase 1 data model: composed paths

**Feature**: `004-composed-paths` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

Frozen dataclasses, free functions, tagged unions matched with `match` — owner decision
D-E throughout. Every collection is a `tuple` in a stated order (FR-008).

The rule that governs this whole file: **composition adds reach, never arithmetic**
(FR-004). Where a record below carries a figure, that figure came out of the one costing
fold over a concatenated leg sequence — not out of a sum of per-segment results.

---

## The candidate

### `ComposedPath` — `core/routes/path.py`

| Field | Type | Meaning |
|---|---|---|
| `destination_id` | `str` | Venue the chain ends at, as `FundingPath` means it |
| `stream_id` | `str` | Whose money moves |
| `segments` | `tuple[str, ...]` | Declared route ids in order, at least two |

`Candidate = FundingPath | ComposedPath`, a union matched on — never a `is_composed: bool`
(FR-013, research.md D2). At least two segments: a one-segment chain **is** a declared
route and is emitted as `FundingPath`, so a single-element `ComposedPath` never exists.

**No amount.** Same reason `FundingPath` has none: a path is *which way*, an amount is *how
much*, and folding the amount in would make the key of a cost include the cost's input.

### `ExitChain` — `core/routes/path.py`

A tagged union of three (research.md D4):

| Member | Fields | When |
|---|---|---|
| `DeclaredExit` | `route_id: str` | 002's single declared `partner_route` |
| `ComposedExit` | `segments: tuple[str, ...]` (≥ 2) | FR-012's chain of declared exit routes |
| `EXIT_BY_IDENTITY` | sentinel, no fields | The destination is itself a declared spendable endpoint (003 FR-002) |

The sentinel is a single-member `Enum`, not `None` and not an empty `ComposedExit`: a round
trip that costs nothing **because there is nothing to do** is a different claim from one
whose fees happened to cancel, and only a distinct value carries that difference.

### `Segment` — `core/routes/path.py`

| Field | Type | Meaning |
|---|---|---|
| `position` | `int` | 0-based place in the chain |
| `route_id` | `str` | The declared route this segment **is** |

Carries nothing of its own. Every term is the declared route's, used verbatim (spec Key
Entities) — so there is deliberately no field here for a fee, a cap or a window.

## Costing

### `SegmentAttribution` — `core/results/ramp.py`

| Field | Type | Meaning |
|---|---|---|
| `position` | `int` | |
| `route_id` | `str` | |
| `components` | `Mapping[CostComponent, Money]` | What this segment charged, by component |

One per segment, on both `OneWayCost` and `RoundTripCost`. A declared route has exactly
one, and that is **not** a special case in the code (research.md D7).

Two invariants, both testable and both extending 002's: the components mapping sums to the
total, and the segment attributions sum to the same total.

### Changes to existing records

| Record | Change | Why |
|---|---|---|
| `RampCost.path` | `FundingPath` → `Candidate` | FR-013 |
| `RampCost.exit_path` | **new**, `ExitChain` | FR-012: the exit chain is part of the ranked unit's identity (research.md D3) |
| `OneWayCost.by_segment` | **new**, `tuple[SegmentAttribution, ...]` | FR-020 |
| `RoundTripCost.by_segment` | **new**, `tuple[SegmentAttribution, ...]` | FR-020 |
| `RouteUnusable.binding_segment` | **new**, `Segment \| None` | FR-015: which segment bound, `None` for a declared route |
| `Ranking` | unchanged in shape | FR-010: one league, one lexicographic key, one tie rule |

`RampCost` gains **no** combined disruption probability, and that absence is the
requirement (FR-019, research.md D12).

## Enumeration

### `SegmentBound` — `core/routes/compose.py`

| Field | Type | Meaning |
|---|---|---|
| `max_segments` | `int` | ≥ 1, declared, no default (FR-006) |

`1` means composition is off — legal, and the explicit way to disable it. **Absent** is a
load failure, which is a different thing entirely.

### `Enumeration` — `core/results/composed.py`

| Field | Type | Meaning |
|---|---|---|
| `candidates` | `tuple[Candidate, ...]` | Every declared route and every composed chain for this query, sorted |
| `bound` | `SegmentBound` | The bound in force, recorded with the results (FR-007) |
| `regime_id` | `str` | The single regime every segment belongs to (FR-017) |

The bound travels with the results so a corridor's absence is attributable to the bound
rather than mistaken for a registry gap. That is FR-007's second sentence, and it is the
difference between "you have not declared that corridor" and "you told me not to look that
far".

### `CompositionRefused` — `core/results/composed.py`

| Field | Type | Meaning |
|---|---|---|
| `reason` | `str` | Why no enumeration was produced |
| `destination_id`, `stream_id` | `str` | What was asked for |

Returned instead of an `Enumeration`. An empty candidate tuple is a legitimate answer
("nothing connects") and is **not** this: the typed refusal is for a question that could
not be asked, not for one whose answer is none.

## What is deliberately absent

- **No path score, no heuristic value, no estimated cost.** There is no field for one, and
  required test B12 is why: a routing search is exactly where a composite score sneaks into
  a user-visible ordering.
- **No persisted candidate.** Composition is query-time (FR-021). Nothing is written back
  to the registry, so no record here has an id, a file or a lifetime.
- **No combined disruption probability** (FR-019).
- **No instrument terminal node** (FR-014) — destinations stay currency balances at venues.
  The seam is *what counts as a destination*, and every rule here is written over venues,
  currencies, directions and regimes so the widening is a change to the destination type
  alone.
