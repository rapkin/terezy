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

- [x] No [NEEDS CLARIFICATION] markers remain — the FR-011 marker was downgraded on
      2026-08-23 to an owner verification task, and what remains after that task is a
      declared calendar, which FR-018 records as a feature rather than as a marker
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

**This file certifies that the checks above were made; it does not restate what the
specification says.** Where a note would have to carry a verdict, a citation or a retrieval
claim, it names the section of `spec.md` that owns it. On 2026-08-25 a review found this
checklist still asserting a retrieval claim the specification had labelled false, because
the claim had been copied. One fact, one place.

- **FR-011's marker is gone, and it should never have been one.** The requirement already
  specified the behaviour in the rule's absence — FR-010's refusal stands, and the absence of
  a rule is not permission to choose one. What FR-017 ships is that refusal, live from the
  first run, so the gap is something a run reports rather than something only this
  specification says.

- **What was missing turned out to be more than a value, and FR-018 says so.** Reading НБУ's
  пункт 10 showed it is written in working days and public holidays, which nothing in this
  feature can declare; declaring the rule therefore needs a declared calendar and is not a
  data-only change. That correction is why SC-014 no longer claims a zero-source-lines
  outcome for the Ukrainian rule and SC-015 makes that claim against a synthetic one.

- **The prohibition is a requirement, not a note.** *A paraphrase is not a citation and MUST
  NOT enter as one* sits in FR-011, where an implementer reading only the Requirements block
  meets it; owner verification task 1 records the paraphrase it kept out and what that
  paraphrase lost.

- **The retrieval record and the НБУ citation both live in owner verification task 1.** It
  carries the working URL form, the two earlier retrieval claims re-tested and found false on
  2026-08-25, and the attribution — which абзаци are № 148's own words and which are not, a
  distinction this bullet restated and got wrong for a day before being cut back to a
  pointer.

- No other clarification was needed. The one genuinely load-bearing design question — is the
  official rate a kind of FX channel — is answered in the spec's "Clarifications resolved"
  table from the constitution's three-roles clause and the two refusals already written into
  `core/routes/legs.py` and `data/declarations/resolver.py`, not from a guess.

- Every item passes; the spec is ready for `/speckit-plan`.
