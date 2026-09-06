# Specification Quality Checklist: The answer, on the home page, in one visual language

**Purpose**: Validate specification completeness and quality before planning
**Created**: 2026-09-06
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — both answered by the owner 2026-09-06,
      `specs/decisions/2026-09-06-clarify-026.toml`.
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

## House rules

- [x] At most 30 functional requirements (exactly 30)
- [x] Every obligation on 020 measured against the **served** document, not read off a spec
- [x] Every figure quoted in the spec is dated and reproducible from the shipped `data/`

## Notes

Everything was settled against a measurement rather than a guess; the measurements are in the spec
beside the requirement they warrant. The two markers were the owner's, and he answered both on
2026-09-06 — Q2 by rejecting every option offered, which is why the figure moved into the engine.

## Review, round one (2026-09-06, `main...spec/026-answer-screen`)

Eleven findings, all against prose that made a checkable claim, all fixed. The three that
mattered:

- `GET /api/instruments/{id}` returns **no** class for a fund — `FundDeclaration` drops it at load —
  so FR-006 now keys on the read's own tag first and `instrument_class` second, and OB-14 records
  both halves.
- `dominance.indistinguishable` (4 members at one month), `incomparable`, `standings` and `reserves`
  were read by nothing while SC-005 claimed no population is dropped.
- FR-028 claimed every 021 route keeps its path while the feature moves `/`.

Also fixed: a header naming one stated amount where the question states two; SC-007's negative half
having no witness in the shipped data; the absolute *zero engine changes* claim against FR-007's
declaration; a belief line covering a ranked row that does not lean on it; hue 300 assigned to both
the broker kind and the assumption badge; a component row naming a file no task creates; a
`[[future]]` id contradicting its own corrected measurement; and a Phase 1 exhaustiveness test over a
vocabulary Phase 5 creates.

## Review, round two (2026-09-06, same diff, five commits)

Ten findings; **nine fixed, one rejected with evidence**. The two that changed a decision and still
stand — a third, on Q2's recommendation, was superseded by the owner's own answer:

- `instrument_class` is `str` on the core record and `string` in the generated document, so it can
  carry no exhaustiveness guard. FR-006 now runs FR-004 over the instrument read's **tag**, which is a
  literal union, and renders an unnamed class raw. OB-14 records the third half.
- The badge vocabulary was **three** labels over **two** conditions, and reading `span.end` against
  `horizon.end` inverted them: `span` is first outlay to last arrival, so a member that ran to the
  window's end would have been badged *matures inside the window*. It is now `sold_early` present or
  absent, plus the raw-tag fallback.

Also fixed: `/` had a redirect requirement no path could satisfy; `outcome`'s nine-member and
`comparison`'s two-member refusal unions had no named state; `MoneyBack` was missing from the
component enumeration; SC-008 and SC-010 had no asserting task; and `why.side` was read as a
discriminant on a variant that does not carry it.

**Rejected**: *"the ranked population is 21, not 22"*. The served array holds 22 in every section and
21 of them carry `carried_quotation`; `the_answer.golden.txt` prints `ranked 21` because the CLI
renders the benchmark row separately. The plan now says so, so the next reader does not reopen it.

**Nothing is left open.** The cap is spent; the two `[NEEDS CLARIFICATION]` markers were the owner's,
not the review's, and both are answered.

## Review of the clarification diff (2026-09-06, `main...spec/clarify-026`)

One round, six findings, all fixed; nothing left open. Three changed a requirement:

- FR-017 asked for the **deployed/remainder split**, and the API serves `reaches` and the remainder
  but not the deployed part — so the card would have had to subtract, which is FR-008. It now shows
  the served `UndeployedCash` record beside the figure and composes nothing.
- Nothing served said whether a remainder **came home**, so a cross-currency one would have left the
  headline understating money back — FR-016's own measured defect. That verdict is now OB-13's second
  half and a named state on the card.
- OB-13's row was flipped to *met* against a branch carrying no commits and a decision file that does
  not exist. It reads *unmet*, and is named as the one obligation that blocks implementation.

Also fixed: what the exit route charges the remainder was being settled by inference from the owner's
account of his own bank, and is now the fix's to declare and cite; `UndeployedCash` carries no date,
so FR-017 no longer asks a card to label one; and *Assumptions* claimed no obligation blocks
implementation while OB-13 does.
