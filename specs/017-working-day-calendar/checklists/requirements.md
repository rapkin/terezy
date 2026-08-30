# Specification Quality Checklist: The declared working-day and public-holiday calendar

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-30
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs). Architecture-layer names
      (`core`) and `file:line` references to **existing** code are deliberate: the first is
      constitutional vocabulary, the second is how a claim about the tree is made checkable.
      No criterion names a module this feature would create.
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
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

## Project-specific gates

Checked because this repository's constitution adds obligations the generic list does not.

- [x] **No legal value from memory.** No holiday date, weekend rule or statutory value is
      asserted in the spec. The one legal text quoted (ч. 6 ст. 6 № 2136-IX) is quoted from a
      primary source retrieved on 2026-08-30, with its amendment marker, and what it does *not*
      settle is stated beside it.
- [x] **Every claim about existing code is verified at source and cited `file:line`.** 18 such
      claims, counted mechanically rather than by eye. All were **re-measured after merging
      `main` at `021a587`**, whose prose sweep shifted `conventions.py` by roughly a dozen lines
      — the first round's references were stale and one of them landed on a plausible
      neighbouring function rather than missing, which is the failure mode a stale line
      reference actually has.
- [x] **Failure is explicit.** Every degraded outcome is a typed refusal (FR-010, FR-011), and
      SC-002 asserts no option turns one into an answer.
- [x] **Domain knowledge is data.** FR-008 forbids a generative rule; FR-018 pins it with a scan.
- [x] **The core stays pure.** FR-016 and SC-011.
- [x] **Prose earns its place / mechanical form preferred.** FR-006, FR-018, SC-003, SC-005 and
      SC-009 turn claims that would otherwise be prose into checks.

## Notes

- **No open clarifications.** CL-1 came back *record and defer* on 2026-08-30, and 018 was
  released from needing this feature the same day.
- **Corrected after review, 2026-08-30.** The first round counted **two** consumers of the
  uncited weekend and concluded "nothing needs this". The set is **three**:
  `fixed_income.py:138/:521/:794` moves coupon and maturity dates through the declared
  business-day registry, and it is blocked on nothing but the calendar. The Status and the
  "why unscheduled" argument were re-derived from the corrected set, and the conclusion moved
  from *nothing needs this* to *nothing needs this urgently, and the live consumer raises a
  scope question this spec has the vocabulary for and deliberately does not answer*.
- **Two requirements are being landed ahead of this feature on `main`** (FR-006b, FR-018a),
  because each has value independent of calendars and neither should wait on an unscheduled
  feature.
- **Two owner verification tasks** are open. Both are legal readings; neither changes the
  design, and the shipped behaviour under both is the refusal that already stands (FR-020).
  Owner verification task 1 records a failed retrieval and the form that failed, so nobody
  spends the attempt twice.
