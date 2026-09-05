# Specification Quality Checklist: Dominance, and the set that has no winner

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-02
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — all four were answered 2026-09-03 and are
      recorded in `specs/decisions/2026-09-03-clarify-019.toml`; the status is `spec`.
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Project-specific gates

- [x] No legal, tax or fee value originates here — comparing two computed figures needs none
- [x] Every measurement is dated and reproducible by loading `data/` and answering the declared
      question **in the states *The measurement* names** — the tree as it stands, the tree after
      the owner's 2026-09-02 decision, and, for the tie-swap alone, that tree under a second
      benchmark — and is stated **once**, in *The measurement*. The Pareto counts are the one
      thing the engine cannot produce, and *The measurement* says so and names the reading of
      FR-007 the hand-written pass implements
- [x] Counts belonging to other features (instruments, streams, routes, pairs, candidates) are
      **cited** to 014 and 015 rather than copied
- [x] Never a number more confident than its inputs: the indifference band is a requirement
      (FR-011) and is kept distinct from the project tolerance (FR-012)
- [x] Provenance propagates — onto a *comparison*, not only onto a figure (FR-022)
- [x] Failure is a typed result carrying its reason; no empty set stands for a refusal (FR-026)
- [x] The core stays pure: no clock, no I/O, no randomness, no solver, no seed (FR-024)
- [x] Domain knowledge is data — the objectives are declared; the one place this is **not**
      data-only is stated plainly rather than left to be discovered (FR-003)
- [x] No new plugin interface, and no fifth one proposed
- [x] Which required-test rows move, and which do not, is decided explicitly with a reason per
      row — Section I flips **I2** only, Section A flips nothing

## Notes

- The spec is **`spec`** in `specs/features.toml` — clarified and ready to plan. It was
  `drafted` from 2026-09-02 until the owner answered CL-1 to CL-4 on 2026-09-03; the answers,
  the options and his own words are in `specs/decisions/2026-09-03-clarify-019.toml` and are
  not restated here or in the spec's option tables, which the answers replaced.
- **The measurements the answers touched were re-read** rather than left standing, and its *The
  measurement* preamble names which, how, and the two readings that step outside the two states
  it otherwise works in — a **third state**, that tree under a second declared benchmark, for the
  tie-swap alone, and a hand-written Pareto pass for every non-dominated count, because the engine
  has none.
