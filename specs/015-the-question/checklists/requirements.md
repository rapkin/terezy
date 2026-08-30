# Specification Quality Checklist: The question, and the answer that refuses in parts

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-30
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

Named types and function names appear where they are the **contract** — the one verb, 014's and
010's existing records that this feature carries whole, and the declaration directories the
constitution requires. Naming them is what makes the requirements testable; nothing here
specifies a module layout, a class shape, or an algorithm.

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — both questions were answered by the owner on
      2026-08-30 and are encoded under *Clarifications*: a horizon window means the money comes
      out at its end, and a subject is an instrument id or a declared group. Status is `spec`.
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

- [x] Every count and measurement of the shipped registry was **measured** by loading `data/` on
      2026-08-30, and the date is recorded beside it
- [x] No legal, tax or fee value is introduced or guessed; the three that would be needed are
      owner verification tasks
- [x] Nothing already settled in `specs/014-candidates/spec.md` is restated — it is cited
- [x] Work required outside this feature's module is named rather than assumed (the declared
      subject set, in feature 014)
- [x] Gaps recorded in `specs/features.toml` as `[[future]]` are surfaced, not resolved:
      `one-amount-per-stream-in-compare` (FR-022) and `zero-hop-way-in` (FR-011)

## Notes

Ready for `/speckit-plan`.

**A review on 2026-08-30 found five contradictions between requirements of this specification
itself**, which is the class of defect an implementer resolves by quietly picking a side inside
the record owner decision D-B says the UI will contract against. All five are fixed. What they
were, so the shapes are recognisable next time: two criteria that could not both pass over one
registry (SC-001 against SC-002, and SC-001 against SC-023); a requirement mandating a record
shape another requirement forbade (FR-023a's exclusions against FR-020's no-prose rule); a
requirement forbidding "anywhere in this feature" the very thing another needed to make a real
declaration answerable (FR-021 against the fund exchange-rate assumption); and a verb whose
signature could not receive two values its own requirements mandated. Every measurement in the
spec was re-run by the reviewer and reproduced.

Two claims in earlier drafts were **wrong** and is corrected in the spec rather than quietly
edited: it said the mid-life disposal price was missing. The observations publish a buy and a
sell for every active issue. What is missing is the assumption that today's spread holds at a
future date — declared, marked and propagating (FR-032) — and a declared resale price on any
shipped instrument (FR-031). The correction is recorded because the reasoning that produced the
error is the reasoning someone will repeat: *nothing computes it* was true of the engine and
false of the data.

The second was an attribution: the two fund drops were read as the empty `ua_nbu_usd` series and
they are `PegUnsizable` on a missing **owner-stated** rate, with no series consulted at all. A
message that names a rate is not evidence about which rate, and the fix was to read the
construction site.
