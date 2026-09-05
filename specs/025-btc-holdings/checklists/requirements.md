# Specification Quality Checklist: The BTC he already holds

**Purpose**: Validate specification completeness and quality before planning
**Created**: 2026-09-06
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [ ] No [NEEDS CLARIFICATION] markers remain — **two open**, both for the owner
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

## Notes

**Over the line budget at 400 lines** against `specs/README.md`'s "about 300". The review round
that measured it is right that the limit exists because requirements start contradicting each
other past it — four of its findings were exactly that — so what was cut was the restating and
what was kept is the decisions-against-alternatives and the thirty requirements. Recorded as
residue rather than met.

**Two clarifications are open and the feature is `drafted`, not `spec`.** Each is a value the
owner declares and an implementer may not: what stands between USDT and USD, and whether a held
position gets its own section. Both carry options and a recommendation; neither is a legal or tax
value, and the one that is — the tax class — is refused by FR-014 rather than asked. **A third
was asked and withdrawn**: the staleness threshold cannot fire under this design, and asking for
a number that changes nothing is the more expensive mistake (FR-024).

Module, record and endpoint names appear in the requirements deliberately. Half of this feature
is a statement about *where a thing may not go* — a real figure out of `data/`, a price out of
run time, a branch out of the engine — and a prohibition has to name what it applies to.

The owner's actual quantities, prices and dates are **not in this specification**, by
`data/README.md` rule 5. The record shape is shown with placeholders.

## Residue after two review rounds

The cap is two rounds and both are spent. Round two's own fixes were read before it closed —
the round's last act, not a third round — and nothing below is a wrong number, a lost
provenance mark or a false guard.

- **400 lines against a ~300 budget.** The two rounds were the argument for the limit: four of
  round one's findings and five of round two's were requirements contradicting each other. What
  the trimming removed was restating; what stayed is the decisions-against-alternatives and the
  thirty requirements. Splitting the feature would put the overlay in one spec and the
  instrument in another, and neither half is usable alone.
- **`status = "drafted"` while `plan.md` and `tasks.md` exist.** The graph's vocabulary has no
  word for it, and `drafted` is the reading that blocks implementation, which is the safe one.
  Recorded as `the-graph-has-no-word-for-drafted-and-planned` in `specs/features.toml`.
- **025 and 019 are declared parallel and are not.** Both regenerate
  `tests/golden/the_answer.golden.txt`. Recorded in 025's `why`; whichever lands second
  re-measures.
- **Not reviewed by a fresh pass**: the fixes in `8c30142`. They are round two's own, read back
  at the site rather than by a new round.
