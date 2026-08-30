# Specification Quality Checklist: The first instruments that are not fixtures

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-30 · **Revised**: 2026-08-30 (primary source found; owner decisions folded in)
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — all three settled by the owner on 2026-08-30 and
      recorded under *Decisions*. Status is `spec`; planning may start.
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic
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

- [x] No legal, tax or fee value originates here — cited to `data/tax/timing/ua.toml`
- [x] Every measurement is reproducible from a checked-in file or a named endpoint, dated
- [x] The second source's **terms of use** are read **at the legal texts**, not at the
      publisher's page, and the statute and the subordinate act are cited for what each actually
      says (FR-013)
- [x] Round-trip cost is per `(instrument × income stream × route)`; the one-way figure is
      explicitly forbidden as a comparison (FR-015)
- [x] Provenance propagation is a requirement with a test (FR-022, SC-016)
- [x] The two sources are required to stay apart, with the specific failure named (FR-020)
- [x] Data-only: no fifth interface, no widened failure union, no new declaration field (FR-029)
- [x] The one cost of data-only is stated once and not argued, with its remedy recorded as a
      future entry rather than as a complaint (FR-011)
- [x] Counts pinned on the shipped registry are enumerated with their sites (FR-024)

## Notes — claims checked against the sources rather than accepted

- **The 100× is kopecks, not a hundred-bond lot.** The price settles it (1 025.59 against a
  100 000 nominal would be one per cent of face); the lot reading would have made every
  declaration a hundred times too large.
- **The date offset is not universal**: +1 day on 15 of 24 issues, 0 on 9. A rule stated once
  would have absorbed the two outright errors the per-issue comparison found.
- **Two seller schedules are wrong**, one of them 013's motivating example for FR-020a.
- **The round-trip median** over the 24 active issues is **0.237%**, not the 0.220% reported.
- **The auction endpoint returned 3 rows**, not a history.
- **`available_quantity` governs nothing** and is not declared — 015's question, answered
  (FR-017a), with the unenforced inventory cap recorded as a future.
- **The licence was mis-cited and is fixed.** Both fragments quoted from
  `bank.gov.ua/ua/open-data` are **п. 17 Положення, КМУ № 835** verbatim — a notice the
  *publisher* must display — and the word «гіперпосилання» occurs nowhere in ЗУ № 2939-VI. The
  statutory condition on a reuser is ст. 10¹ ч. 2's «посилання на джерело отримання такої
  інформації». Both texts read at `zakon.rada.gov.ua` on 2026-08-30 before rewriting.
- **The disagreement record was unrepresentable and is now a check** over the two observation
  files (FR-009), not a field on a declaration — which no gate would have allowed.
- **FR-008 now states precedence over FR-001**: the declared set is the intersection, and an
  issue leaving the register is a refusal. 7 of the 8 completed issues have already left it.
- **All eleven `⚙` markers removed**, and the changelog sentences inside three of them with
  them.
- **SC-001 no longer asserts a tautology.** *declared == intersection* cannot fail, because the
  declared set is defined as the intersection. The assertion with content is the refusal set —
  every seller-active ISIN absent from the register — and the count is derived, so the criterion
  survives the first issue leaving the register instead of breaking on it.
- **The fifteen offset issues and the nine agreeing ones are named**, not counted: a check
  asserting only that fifteen carry the offset would pass if the wrong fifteen did. Both lists
  re-derived from a fresh probe and diffed against the spec text.
- **Retrieval trap recorded**: `zakon.rada.gov.ua/laws/show/835-2015-п` returns 403, and its
  `#Text` and `/card` variants return 4 259-byte stubs with zero occurrences of the searched
  word — indistinguishable from a real negative. Only `/print` returns the document.
- **One paper, two ids** — `enumerated_out_of_order` is modelled on `UA4000235865`, which 016
  declares for real, so 015's `ovdp` group would hold both. FR-027a drops the label; the fixture
  keeps its place, because 016's own finding is that the real issue is not out of order and 013's
  mechanism therefore still has no other example.
