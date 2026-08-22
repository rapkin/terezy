# Specification Quality Checklist: Inzhur instruments and dated tax schedules

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-22
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — all three resolved 2026-08-22
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

### Iteration 1 — implementation vocabulary kept out

The feature description arrived carrying schema and interface vocabulary
("`tax_classes` mapping", "`income_currency` field", "scalar rate per class",
"schema change plus a core change"). These were rewritten as observable behaviour:

| Was | Became |
|---|---|
| "001's plural `tax_classes` mapping was built for exactly this" | FR-006/FR-007 — one instrument declares different classes for distributions and disposal; per-class subtotals; no collision |
| "rates must become dated schedules (schema change)" | FR-010…FR-014 — a rate is declarable as ordered dated entries, each with its own provenance; a legislated change is one data-only entry |
| "`income_currency` reserved for this case" | FR-020/FR-022 — income declared in USD-equivalent terms while all money is hryvnia, the peg always visible |
| "owner-reported observation with empty verification date" | FR-002 — provenance fields and mark propagation, restated as behaviour |

The ⚙ notes on FR-006, FR-011 and FR-015 record load-bearing design context (why the
plural mapping exists; that the rate-selection timing rule is a default that yields to
a cited source; why "windows" became liquidity terms), not implementation
instructions.

### Iteration 2 — traceability gaps closed

FR-021 (typed degraded result when a pegged flow would need an undeclared rate) had no
measurable outcome — folded into SC-011. FR-009 (rates enter with the reference spec's
citations, never from memory) was asserted only by an acceptance scenario — added to
SC-001.

### Iteration 3 — clarifications resolved from primary sources

All three markers were resolved on 2026-08-22: two owner design decisions (A —
USD-equivalent declaration over hryvnia money; B — declared net yield plus a
carefully-modelled entry/exit spread, fund-internal profitability recorded as context
only) plus a research pass over the funds' primary documents (both регламент and
проспект read in full, fund pages, Inzhur news; accessed 2026-08-22, every value
entering with an empty verification date). The resolution reshaped the spec beyond
marker substitution:

- **"Redemption windows" do not exist** — the funds' documents show no windows, only
  a legal floor (no buyback obligation before termination; discretionary buyback at a
  discount, ≤ 15 business days) and a revocable company practice (same-day at NAV,
  zero commission). FR-015…FR-019 were respecified over declared liquidity terms with
  the two modes kept distinguishable; required test J3's substance (refuse, or execute
  at the declared haircut, taxed correctly either way) is preserved, and the spec
  notes the row's wording should be annotated at landing.
- **FR-023/FR-024 inverted their draft shape** per owner decision B: the draft
  computed management-fee erosion as its own line; the resolved spec forbids modelling
  fund-internal profitability as computed terms and moves the erosion visibility to
  the round-trip spread, which the owner named as the main thing.
- **MilTech is an accumulation fund** — no dividend obligation, so the draft's
  invented-distribution risk is now an explicit prohibition (US4 scenario 1), and its
  fund-stated 25–29% range must never collapse to a silent midpoint (FR-023,
  SC-013).
- Six facts the primary documents do not settle are recorded as **owner verification
  tasks** (rate-fixing rule, current cap values, live spread settings, ІНЖУР КЕПІТАЛ
  commission, MilTech buyback-practice coverage, secondary market) — tasks, not
  gaps to invent.

Every FR maps to at least one SC or acceptance scenario:

- FR-001 → SC-010 · FR-002 → SC-008 · FR-003 → SC-005 · FR-004/005 → SC-009
- FR-006/007/009 → SC-001, SC-002 · FR-008 → SC-012, US1 scenarios 2–3
- FR-010/011/013 → SC-003, SC-004 · FR-012 → SC-005 · FR-014 → SC-006
- FR-015…FR-018 → SC-007 · FR-019 → SC-014, US3 scenarios 4–6
- FR-020/021/022 → SC-011 · FR-023/025 → SC-013 · FR-024 → SC-012
- FR-026…FR-028 → the real declarations; they are data files whose content is fixed
  by the Clarifications-resolved citations, asserted by SC-008's marking and the
  provenance gate

### Recorded scope decisions

- Required-test rows claimed: **E1, E10, J3** only. FR-019 and FR-005 specify the
  behaviours behind J4 and J6, but whether those rows flip here is a planning
  decision, stated as such in the spec.
- The E10 worked example uses a **synthetic** schedule: the real 1.5% → 5% levy step
  is expressible but its effective date is not fabricated without a citation.
- No market FX source: the peg sizes payments only under an explicitly declared,
  owner-stated rate assumption; an assumed rate above the declared cap binds at the
  cap, visibly.
- No fund-internal profitability as computed terms, no NAV, no probabilities, no
  filing mechanics — each named in Out of scope with the owner decision,
  reference-spec item or required-test row it defers to.

Final counts: 28 functional requirements (FR-001…FR-028, no gaps or duplicates),
14 measurable outcomes, 5 prioritised user stories, 14 edge cases, 3 resolved
clarifications, 6 owner verification tasks, 3 required-test rows claimed.
