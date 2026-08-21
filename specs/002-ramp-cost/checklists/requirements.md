# Specification Quality Checklist: The ramp

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-22
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

### Iteration 1 — scope narrowed, and why

The feature description reached for "the crypto ramp", which would have pulled in a crypto
instrument, a price series, and a tax regime that does not exist in adopted law. The spec
narrows the destination to **a currency balance at a venue** instead. That is not a
compromise: the ramp is the cost of *getting money there*, and §3.6 already makes cash and
FX first-class. It answers §8 question 7 in full while leaving instruments out entirely.

`G1`'s wording ("the same crypto purchase funded from the UAH salary and from the USD
income") is therefore satisfied in its essential form — the same USD acquisition from each
stream, differing by exactly the ramp cost. The crypto instrument adds nothing to what that
test asserts. Recorded as an assumption rather than left as an unstated reinterpretation.

### Iteration 2 — a requirement strengthened past the description

The description said access cost must be "never quoted per instrument". FR-008 goes
further: a per-destination cost must be **unrepresentable**, not merely discouraged.
Principle VI's rule is the one most likely to be violated by accident — a helper that
returns "the cost of reaching Binance" reads perfectly reasonable and is wrong — so the
requirement asks the shape to forbid it. SC-006 measures it.

### Iteration 3 — two edge cases the description did not name

- **A fixed fee on a very small amount** makes cost-as-a-percentage exceed 100%. Reported
  honestly rather than capped, because a cap here would be the silent clamp of
  predecessor defect B13 wearing a different hat.
- **A negative declared premium.** P2P does sometimes trade below the reference rate, so a
  discount is permitted with its observation date. Refusing it would force the owner to
  record a real observation as something it is not.

### Iteration 4 — clarifications resolved

All three answered. The owner took the more expensive option in every case, and each
choice has a cost worth recording so it is not later mistaken for an accident:

- **FR-027** — exit routes are **declared**, not reversed. The cost is that the registry
  must be populated in pairs before any round-trip figure exists.
- **FR-028** — staleness thresholds are **per value kind**, with no permissive default. The
  cost is one more field per kind.
- **FR-029** — every route is costed **in full through the same path** as the
  recommendation. The cost is more work per contribution.

**FR-030 was added, not asked for.** The exit-route decision implies that a destination
whose exit nobody declared has no round-trip figure at all — and since FR-002 makes
round-trip *the* comparison number, such a destination cannot be compared. That needed
saying explicitly, because the tempting silent fix (promote the one-way figure) is exactly
the kind of confident-but-unfounded number Principle I exists to refuse. It is written as
the decision working rather than as a gap in it.

**SC-014 to SC-016 were added** so each of the three decisions has a measurable outcome.
SC-016 in particular asserts the same-code-path property *by construction* rather than by
comparing two numbers that happen to agree — a comparison that agrees today by coincidence
is not evidence of anything.
