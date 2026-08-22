# Specification Quality Checklist: Composed paths

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-22
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — all three resolved by the owner 2026-08-22
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

**Status: all items pass. Ready for `/speckit-plan`.**

## Notes

### The three markers went to the owner and came back decided

The spec shipped with three deliberate `[NEEDS CLARIFICATION]` markers — the feature
description named them as questions "the owner must answer before planning, not the
implementer" — and the owner answered all three on 2026-08-22. The decisions and their
reasoning are recorded in the spec's **Clarifications resolved** table, mirroring how
feature 002 shipped: composed exit chains satisfy 002 FR-027 (FR-012); composed paths
are visibly distinct candidates, shown segment by segment (FR-013); destinations remain
currency balances at venues, with instrument access recorded as a stated deferral whose
seam is named (FR-014).

### Iteration 1 — one aggregation rule refused

The first draft was tempted to give a composed path a combined disruption probability
(one minus the product of per-leg survival). Removed: multiplying per-leg probabilities
assumes independence, which nobody declared, so the combined figure would be an invented
number wearing declared clothes. FR-019 now forbids it explicitly and SC-011 measures
its absence. Per-leg reporting (002 FR-026) already says everything the declarations
support.

### Iteration 2 — the unifying rule that removed a class of requirements

Early drafts specified latency, ceiling, minimums and staleness aggregation for composed
paths one by one — each a chance to drift from 002. Replaced by FR-004: a composed
candidate behaves, for every rule 002 states over legs, exactly as a declared route with
the same concatenated legs would. Composition adds reach, never new arithmetic. The
remaining specific FRs (pools, regimes, provenance, disruption) pin the places where a
join could plausibly launder something, rather than restating 002.

### Iteration 3 — two edge cases the description did not name

- **Duplicate candidates**: a composed concatenation can reproduce a declared route leg
  for leg. FR-009/SC-013 make rankings duplicate-free with the declared route standing,
  while venue-identical-but-term-different chains remain distinct candidates — that
  difference is real information.
- **A bound of 1** is the explicit off-switch for composition, distinct from a missing
  bound, which fails at load (FR-006) by the same no-permissive-default rule as 002
  FR-028.

### Iteration 4 — owner resolutions, and one gap the first decision made load-bearing

External review found that "directions connect" did real work in User Story 1 and the
composed-candidate definition while no requirement defined it — and the owner's first
decision turned that gap load-bearing, since composed exit chains now exist and the
inbound/exit boundary had to be drawn by someone. **FR-022** draws it: directions never
mix, because an observation of a corridor in one direction says nothing about the other,
and an exit chain runs from the destination to a declared spendable endpoint.

Decision 1 also forced two consequences into requirements rather than leaving them to
planning: the exit chain is part of the round trip's identity — keyed per
`(destination × stream × inbound path × exit chain)`, two exit chains means two figures —
and ties among exit chains follow 002 FR-018 unchanged. New measurable outcomes
SC-015–SC-018 cover the composed round trip, the direction discipline, the visible
distinctness of composed candidates, and per-exit-chain keying.

One default this pass had to set, recorded as an assumption for the owner's eye: **the
segment bound applies to each chain separately** (inbound candidate and exit chain each
within the bound), because a shared budget would entangle an inbound path's reachability
with whichever exit chain it is paired with.
