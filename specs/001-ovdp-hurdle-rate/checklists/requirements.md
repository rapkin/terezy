# Specification Quality Checklist: The OVDP hurdle rate

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-21
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

### Iteration 1 — implementation vocabulary removed

The first draft carried implementation vocabulary straight from the feature description
("Money value object", "event-sourced ledger kernel", "plugin interface", "Hypothesis
property-based tests", "float64", "TOML"). These were rewritten as observable behaviour:

| Was | Became |
|---|---|
| "a currency-tagged Money value object over float64" | FR-006/FR-007 — every amount carries its currency; mixing currencies is an error |
| "a single tolerance policy module" | FR-002 — one project-wide tolerance, defined in one place |
| "event-sourced ledger with tax lots" | FR-008/FR-010 — figures trace to transaction records; holdings recorded as lots |
| "the Instrument and TaxRule plugin interfaces" | FR-013 — adding an issue requires no source-code change |
| "property-based Hypothesis tests" | SC-009 — invariants hold across a large body of generated cases |

Implementation choices (the four plugin interfaces, float64, the ledger design) are
governed by `.specify/memory/constitution.md` and belong in `/speckit-plan`, not here.

### Iteration 2 — clarifications resolved

Both `[NEEDS CLARIFICATION]` markers were answered by the owner and folded in:

- **FR-021** — coupon periodicity, day-count convention and non-business-day handling are
  declared **per issue as data**, not fixed in the engine. This was the answer most
  consistent with constitution Principle II: had the convention been hardcoded, adding a
  second issue with different terms would have required an engine edit, contradicting
  FR-013 in the same document.
- **FR-022** — the hurdle rate is **nominal only**, labelled as such, with a defined empty
  slot in the result for the inflation-adjusted figure.

### Iteration 3 — coverage gap closed

FR-021 and FR-022 initially had no measurable outcome behind them. Added **SC-011**
(nominal labelling and the reserved empty real-terms slot) and **SC-012** (two issues with
different conventions, no code change). Every FR now has at least one SC or acceptance
scenario asserting it.

### Recorded incompleteness

The nominal-only decision leaves a real gap by design: a nominal 15.5% against
double-digit inflation is a materially different proposition. The output states it is
nominal rather than implying otherwise, and closing the gap is the job of the feature that
introduces CPI. This is a scope decision, not an oversight.

Final counts: 22 functional requirements (FR-001…FR-022, no gaps or duplicates),
12 measurable outcomes, 4 prioritised user stories, 9 edge cases, 10 required-test rows
closed.
