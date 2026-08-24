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

- [x] No [NEEDS CLARIFICATION] markers remain — FR-022's was several questions wearing one
      marker; separating them gave each destination its own verdict under the criteria in
      spec.md's "Legal grounding", which is where they are counted
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
specification says.** Where a note below would have to carry a verdict, a count or a
citation, it names the section of `spec.md` that owns it instead. That is deliberate: on
2026-08-25 a review found this checklist asserting four things the specification had already
corrected — a verdict that had been reversed, a task count, an inference the spec deleted,
and a retrieval claim the spec labels false — because every one of them was a copy. One
fact, one place.

- **Where the destination verdicts and their grounds live**: `spec.md` → "Legal grounding",
  which states the criteria and applies them in a table, and FR-025 onward for the
  requirements themselves. How many destinations there are, and what each is worth, have both
  changed on this branch and are not restated here — a count is exactly the kind of copy this
  file was rewritten to stop carrying, and it carried a stale one for a day anyway.

- **Where the owner verification tasks live**: `spec.md` → "Owner verification tasks", which
  states how many there are, which are load-bearing, and what each closes. None is a
  `[NEEDS CLARIFICATION]`: each names a value, and a missing value is the ordinary state of
  a declaration file.

- **Every legal value came from a retrieved citation, none from memory, and each was
  re-read against its primary text.** Three rounds of correction are recorded in `spec.md`
  itself — the source table, "One rate, three laws, and an end nobody can put a date on",
  and the Sources block — including the ФОП levy's commencement (Закон № 4113-IX, not
  № 4015-IX) and its sunset (Закон № 4835-IX, FR-008a). The retrieval guidance in the
  Sources block is the current one: always `/laws/show/<id>/print` with `--compressed`; the
  earlier claims about `/go/<id>` and about long documents were re-tested on 2026-08-25 and
  are false.

  ⚙ **Two exceptions, as of 2026-08-27**: the 18% ПДФО of FR-010a rests on one practitioner
  article and its Tax Code article is owner verification task 5; the zero ЄСВ of FR-021 has
  no public source at all, the owner's own statement being its source. Both are marked as
  such in `spec.md`'s source table. *Each was re-read against its primary text* does not
  reach them, and closes when tasks 2 and 5 do.

- Four design positions (ЄСВ is not a rate; a taxation scheme is the declared entity and one
  of its components can be nothing; the scalar is retired; base and received are two
  numbers) are argued in the spec rather than asserted, and are recorded in the
  "Clarifications resolved" table.

- Every item passes; the spec is ready for `/speckit-plan`.
