# Specification Quality Checklist: Real terms on a tuple

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-06
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — record and field names are the
      contract this feature changes, not an implementation choice; no module layout is prescribed
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — the future-span question is settled by the
      owner's 2026-08-22 decision (007), applied rather than re-asked
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

## Project gates

- [x] 367 lines, 23 functional requirements — inside `specs/README.md`'s ~300 / ≤30
- [x] Every new figure lands with a hand-computed worked example (the worked example section)
- [x] No legal, tax or fee value originates here; the two deflators are already declared data
- [x] Provenance propagation stated as a requirement, not assumed (FR-011)
- [x] The golden that moves is named, and the one that must not is named (FR-018, FR-019)
- [x] Two review rounds, both against the shipped root: every figure, span and declared date the
      spec states was reproduced by running the engine. Round one corrected three false claims;
      round two corrected the refusal precedence (FR-013b), the window rule's parameter, one
      declared payment date and two named files. Nothing is left open.
