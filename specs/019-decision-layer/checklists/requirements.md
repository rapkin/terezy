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

- [ ] No [NEEDS CLARIFICATION] markers remain — **four are open** (CL-1 to CL-4) and the status
      is `drafted`. CL-1 and CL-2 decide what the output *is*, so planning may not start on
      either; CL-3 is a standing position; CL-4 is one word in the owner's own question file.
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
      question **in the two states *The measurement* names** — the tree as it stands, and the tree
      after the owner's 2026-09-02 decision — and is stated **once**, in *The measurement*
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

- The spec is **drafted**, not ready for planning: `spec.md` exists and four
  `[NEEDS CLARIFICATION]` markers are open, so planning may not start — guessing the answer is
  what the marker exists to prevent. That word is `specs/features.toml`'s, and **this feature has
  no row in that file yet**: the `[[feature]]` entry is proposed with the spec and added by the
  change that lands it, so nothing here should be read as a claim about what the graph currently
  says.
