# Specification Quality Checklist: The official rate and the tax-currency role

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-23
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [ ] No [NEEDS CLARIFICATION] markers remain — **one open**, FR-011
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

## Notes

- **The one open marker is FR-011**: the citable primary text of the Ukrainian rule for a
  date the National Bank does not publish a rate for. The *shape* is specified and closed —
  a per-series declared rule carrying its own citation, or a refusal; never engine logic,
  and the engine never learns what a weekend is. Only the *content* of the UA rule is
  missing, and its absence is not a blocker: FR-010's refusal is the specified default, so
  the feature is implementable and correct without it, merely stricter.

  Retrieval was attempted and failed rather than skipped: `bank.gov.ua` returns HTTP 403 to
  automated retrieval, and `zakon.rada.gov.ua` renders statute text client-side, so neither
  the NBU methodology note nor NBU Board Resolution No. 148 of 10 December 2019 could be
  quoted. Search engines paraphrase the rule consistently, and a paraphrase is not a
  citation — entering one would be the exact failure Principle I forbids.

  **What resolves it**: the owner supplying or confirming the clause that states which rate
  governs a non-publication day, with a URL the value can be re-read from. It then enters
  as declared data on the UA series with an empty `verified_on`, like every other observed
  value.

- No other clarification was needed. The one genuinely load-bearing design question — is the
  official rate a kind of FX channel — is answered in the spec's "Clarifications resolved"
  table from the constitution's three-roles clause and the two refusals already written into
  `core/routes/legs.py` and `data/declarations/resolver.py`, not from a guess.

- Every other item passes; the spec is ready for `/speckit-clarify` (one question) and then
  `/speckit-plan`.
