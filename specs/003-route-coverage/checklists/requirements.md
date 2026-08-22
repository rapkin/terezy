# Specification Quality Checklist: The coverage report

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-22
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — both resolved by the owner 2026-08-22
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

### The two markers were reserved owner decisions, and the owner answered both

Both questions were about the owner's life and the owner's rule rather than about the
system, so they were left as markers rather than guessed. Answered 2026-08-22:

- **FR-004 — spendable endpoint**: UAH only, at the specific venues the owner actually
  spends from, declared as a data-file list of `(venue × currency)` pairs. Not "UAH
  anywhere", not foreign cash in hand. SC-019 measures it, including that changing the
  list is a data-only change.
- **FR-019 — binding vs advisory**: **advisory for now, deferral recorded.** The rule
  "before it may appear in any comparison" remains the destination; enforcement moves
  to a later feature, and the gap this leaves (a deficit-3 destination still ranked by
  feature 002 while the report says it should not be compared) is stated on the spec's
  face and in the report's own output — a recorded incompleteness in the style of
  001's nominal-only decision, not a final softer reading. SC-020 measures both the
  no-behaviour-change property and that the output states the deferral.

### Iteration 5 — external review, two findings fixed

- **Missing-exit target underdetermined.** For a missing exit, any declared spendable
  endpoint satisfies the rule — a set, not a point — so FR-007's "write the file from
  the report alone" promise was untestable as written. Fixed: the missing-exit item
  names origin + direction with "any declared spendable endpoint" and the candidate
  list; identity is origin + direction (+ regime), one item per hole, so blocked
  counts never multiply by the spendable list's length. SC-003 now accepts an exit to
  any one listed endpoint.
- **FR-018/SC-009 collision with feature 004.** The owner decided in 004's clarify
  that chained exit segments satisfy 002's FR-027, so composition will make costing
  produce round-trip figures for pairs this report marks not-ready. FR-018 and SC-009
  are now scoped to costing over single declared routes as of this feature, with a
  forward note committing to a distinct "reachable by composition only" annotation
  (computed by chaining declarations — pure, no costing) as the reconciliation path.

The three load-bearing derivations below were resolved in the spec at drafting time,
marked ⚙ so clarify/plan can challenge them:

### Iteration 1 — three ⚙ derivations recorded instead of asked

- **FR-001 ⚙ — the destination universe is venue × holdable currency**, derived rather
  than separately declared. "Every declared destination" needed a universe; deriving
  it from venue declarations is what makes an unreachable venue visible as a hole the
  moment it exists, which is the feature's stated purpose ("a hole is a fact the owner
  acts on").
- **FR-007 ⚙ — "currency path" in a missing declaration means the endpoints.** The
  interior hops of an unobserved corridor are precisely what only an observation can
  supply; naming them would invent the link the report refuses to invent (and would
  collide with FR-027's no-reversal rule the moment the suggested path mirrored the
  inbound).
- **FR-022 ⚙ — declared-but-closed counts as coverage, visibly annotated.** The
  owner's rule is about declarations; a closed route is observed and declared, and
  telling the owner to "go observe" an already-observed corridor would misdirect the
  to-do list. The compensating obligation (a ready verdict on closed routes must be
  visibly distinct) is SC-015.

### Iteration 2 — blocked-count semantics pinned to the description's own words

The description says both "how many pairs each single missing declaration **blocks**"
and "which single missing declaration would **unlock** the most". Where a pair needs
two declarations, these diverge — strict "unlocks alone" would credit neither. The
spec follows the description's operative verb: count pairs the declaration is
*required* for (FR-009), and mark each blocked pair "not alone sufficient" where more
is needed (FR-011), so the ordering never overstates what one observation buys
(Principle I). Ties are ties (FR-010), and the count is a plain count per required
test B12.

### Iteration 3 — honesty guards added past the description

- **FR-012 orphan exits** — an exit nothing reaches is not a hole under the rule, but
  omitting it would misstate the registry; listed as "observed, unused".
- **FR-018 consistency with costing** — a report that called a pair ready while
  costing refused it (or vice versa) would be two authorities disagreeing about one
  registry; SC-009 pins them together over generated registries.
- **FR-023 no provenance marks of its own** — the report contains no observed values,
  and a *summarized second copy* of provenance here would drift from the authoritative
  marks that live on costing figures. Verified inside SC-008's whole-output sweep.
- **Out of scope's last paragraph** — the to-do list orders by pairs unblocked, never
  by hryvnia value, because valuing an unobserved corridor is an invented number by
  construction.

### FR ↔ SC traceability

Every FR except the two markers maps to at least one SC, tagged inline in the Success
Criteria section: FR-001 → SC-001/SC-014 · FR-002 → SC-001 · FR-003 → SC-002 ·
FR-005 → SC-012 · FR-006 → SC-010/SC-011 · FR-007 → SC-003 · FR-008 → SC-004 ·
FR-009/010 → SC-005 · FR-011 → SC-006 · FR-012 → SC-017 · FR-013/014 → SC-007 ·
FR-015 → SC-018 · FR-016 → SC-016 · FR-017 → SC-008 · FR-018 → SC-009 ·
FR-020 → SC-013 · FR-021 → SC-016 · FR-022 → SC-015 · FR-023 → SC-008 ·
FR-024 → SC-014 · FR-004 → SC-019 · FR-019 → SC-020. Every FR now maps to at least
one SC.
