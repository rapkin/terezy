# Specification Quality Checklist: The ФОП group 3 regime

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-23
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [ ] No [NEEDS CLARIFICATION] markers remain — **one open**, FR-022
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

- **The one open marker is FR-022**: whether contract income credited somewhere other than
  a ФОП account falls under this regime at all. That is a legal question about the owner's
  position, not a modelling choice, and no source for it was found. The specified behaviour
  in the meantime is a typed refusal naming the destination and the regime (SC-013), so the
  feature is implementable and correct without the answer — merely narrower.

  **What resolves it**: a cited public source, or the owner's accountant, stating the
  treatment of contract income received outside the ФОП account.

- **Five owner verification tasks** are recorded in the spec rather than guessed. The one
  with teeth is the first: the statutory ЄСВ monthly minimum-contribution amounts and their
  effective dates were not supplied and cannot be invented. Its consequence is specified
  rather than deferred — the declared exemption resolves every month to nil today, so the
  amounts are never reached, and the first non-exempt month refuses naming what is missing
  (FR-021). This is deliberately **not** a `[NEEDS CLARIFICATION]`: the shape is settled and
  only data is absent, which is the ordinary state of a declaration file.

- **Every legal value came from a handed or retrieved citation, none from memory.** Of the
  three sources supplied for the військовий збір, only zaxid.net was retrievable in full on
  2026-08-23 (business.diia.gov.ua returned only its page title, oschadbank.ua a redirect
  loop); the quotes in the spec's facts table are from the page that was read. The 1.5% → 5%
  personal-income change is cited as the argument for dated schedules and deliberately not
  entered as a rate, because nothing in the model consumes it.

- Four design positions (ЄСВ is not a rate; "currently zero" is the wrong shape; the scalar
  is retired; base and received are two numbers) are argued in the spec rather than
  asserted, and are recorded in the "Clarifications resolved" table.

- Every other item passes; the spec is ready for `/speckit-clarify` (one question) and then
  `/speckit-plan`.
