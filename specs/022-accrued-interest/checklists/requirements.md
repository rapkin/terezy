# Specification Quality Checklist: Accrued interest on a carried quotation

**Purpose**: Validate specification completeness and quality before planning
**Created**: 2026-09-05
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
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

## Notes

Module and record names appear in the requirements deliberately: the change is a deletion of
existing behaviour (`detached_since`, `EARLY_EXIT_IGNORES_ACCRUED_INTEREST`,
`SoldEarly.detached_per_unit`), and a requirement to remove a thing has to name it.

The owner settled the substance on 2026-09-05, so nothing is open. Two judgements the spec
makes rather than asks: the generative form is included under one rule (FR-007), and a
zero-coupon schedule is a legitimate zero rather than a refusal (FR-009).
