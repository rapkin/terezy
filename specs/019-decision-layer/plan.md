# Implementation Plan: Dominance, and the set that has no winner

**Feature**: `019-decision-layer` | **Date**: 2026-09-05 | **Spec**: [spec.md](./spec.md)

**Branch**: `feat/019-decision-layer`, landing on `main` by a `--no-ff` merge after a clean review.

## Summary

A pass over what a horizon section already evaluated, producing the **non-dominated set** on the
owner's two declared objectives — the money that reaches a spendable endpoint, and the date all of
it is back there. Every evaluated candidate lands in exactly one of three counted populations, no
candidate is pruned, and the hurdle is inside the population rather than beside it.

The deliverable is that **the answer stops having a head**. The measurement's item 3 is the whole
argument in one row: at twelve months the rate's first place returns the least money of the 24.

Four pieces of work sit **outside** this feature's module, each made where it lives:

| Where | What | Requirement |
|---|---|---|
| 015 `core/results/question.py`, `schema.py`, `loader.py`, `resolver.py` | the question's `objectives` field, required, and the cross-file check | FR-001a |
| `core/primitives/tolerance.py` | `slack(left, right)` — the width of the project comparison, as a value | FR-011c |
| `terezy/data/manifest.py` | `"objective_set"` in the closed `InputKind`, and its `_ref` in the walk | FR-030 |
| `src/terezy/cli/main.py` | the three populations, the incomparable pairs, the indistinguishable neighbours, the benchmark's standing, and 010's **tie groups** | FR-029, FR-029a |

## Implementation starts after two branches land

`fix/coupon-inside-the-window` and `feat/real-only-registry` are in flight and not on `main`.
The first moves `TupleOutcome.reaches`, which is the money objective; the second is what makes the
specification's *shipped registry* exist at all, and without it every section refuses under FR-018.
Both, and what re-measures after them, are in [research.md](./research.md) D12.

## Technical Context

**Language/Version**: Python 3.13.

**Primary Dependencies**: none new, and CL-3 makes that a standing position rather than a
convenience — no optimisation library, no solver, no dependency for one. At 24 candidates a
pairwise pass is 276 comparisons per section.

**Storage**: version-controlled TOML. One new per-owner declaration directory, `data/objectives/`,
which exists on disk carrying a `.gitkeep` and is already named in `check_provenance.py`'s
`EXEMPT_DIRS` with its reason (FR-004) — so the gate needs no edit and no exemption widens.

**Testing**: pytest. A Hypothesis battery over the relation at three to five objectives (SC-004); a
planted non-transitive witness (SC-004a); worked examples over the shipped registry with every
count derived from what the test loads; four scans (SC-005, SC-007, SC-011, and FR-028's inside
SC-016a); a walk over the whole result for provenance (SC-012); fixtures under `tests/fixtures/data/` for the cases the shipped
registry cannot plant (SC-002's second objective set and question, SC-008, SC-009a, SC-010, SC-013,
SC-014); a golden (SC-018).

**Target Platform**: library, plus the existing loopback-free CLI.

**Project Type**: single Python library, `cli → api → data → core`.

**Constraints**: the core stays pure — no clock, no I/O, no randomness, no solver, no seed
(FR-024); no weight, coefficient or priority anywhere in the declaration or the pass (FR-005,
scanned by SC-005); no feasibility rule, no pre-screen, no early exit, no filter (FR-010, same
scan); no second tolerance policy (FR-012, scanned by SC-007); no string this feature composed in
any record it returns (FR-028, scanned by SC-016a).

**Scale/Scope**: two new core modules, one new declaration family across schema/loader/resolver,
one field on 015's question, one function in the tolerance module, one member of `InputKind`, and
one rendering block.

## Constitution Check

| Principle | Verdict |
|---|---|
| **I — Honesty over precision** | **PASS, and this is the principle's own first step.** Dominance is the head of the preference order, and the feature exists to stop an ordered list's head reading as a winner. The indifference band is the owner's statement about what his inputs support (FR-011), kept distinct from the float tolerance (FR-012). FR-014 makes a one-member set say **why** it has one member. FR-017 says *nothing dominates the hurdle* rather than *the hurdle is best*. |
| **II — Framework, not script** | **PASS, with one stated exception.** Which criteria the owner compares on, in which direction, at which band, is data. The **criterion set** is closed in source and FR-003 says so plainly rather than leaving it to be discovered: a criterion is a reader over a computed figure, so a new one is a new figure. No fifth plugin interface. |
| **III — Pure deterministic core** | **PASS.** The pass is a function of the section, the objective set and the question's amounts. Loading is `data/`'s, the manifest is `data/`'s, rendering is `cli/`'s. FR-024 and SC-017 pin it. |
| **IV — Reliability through contracts** | **PASS.** Every degraded outcome is a typed record (FR-026): six, being the three the spec enumerates, the two FR-011d hands to this plan (research D6) and the one for a section that never surveyed (D6a). No empty set stands for a failure. One tolerance policy — the project comparison in FR-007's weak half and the same rule's **width** in FR-011c's floor, and nowhere else (SC-007). |
| **V — Test-first** | **PASS.** Every task names its test and the test lands first. The two counts a reader wants hard-coded — the non-dominated sizes and the beats-the-hurdle counts — are derived from the registry the test loads, which is what keeps them true across the two branches in flight. |
| **VI — The whole tuple** | **PASS.** The population is 014's five-term key, unchanged. A cross-currency pair yields no verdict and **no exchange rate is consulted** (FR-008a, SC-014). The benchmark is a member of the population, not a figure beside it (FR-016). |
| **VII — Owner-scoped** | **PASS.** An objective set is per-owner data beside `questions/` and `candidates/`, carrying an `[owner]` table checked against the streams it is resolved with. No citation and no source: how much precision he believes his inputs support is a statement about him (FR-004). The CLI listens on nothing. |

No violation to justify, so **Complexity Tracking is empty**.

## Project Structure

### Documentation (this feature)

```text
specs/019-decision-layer/
├── spec.md
├── plan.md          # this file
├── research.md      # the decisions, and where FR-011d's three mechanics are settled
├── data-model.md    # the records, and which requirement each field carries
├── contracts/       # the objective-set declaration, and the question's new field
├── quickstart.md
└── tasks.md
```

### Source

```text
src/terezy/core/results/objectives.py       NEW  Criterion, ObjectiveDirection, the bands, ObjectiveSet
src/terezy/core/results/dominance.py        NEW  the verdicts, the populations, the refusals, the result
src/terezy/core/decision/dominance.py       NEW  the relation, the criteria readers, the pass, the readings
src/terezy/core/primitives/tolerance.py     EDIT `slack` -- the project comparison's width, as a value
src/terezy/core/results/question.py         EDIT `Question.objective_set_id`
src/terezy/core/results/answer.py           EDIT `HorizonSection.dominance`
src/terezy/core/results/canonical.py        EDIT `of_section` encodes the dominance result
src/terezy/core/decision/answer.py          EDIT `AnswerInputs.objectives`; `_section` calls the pass;
                                                 `section_ties` and `section_beats_benchmark` readings
src/terezy/data/declarations/schema.py      EDIT ObjectiveTable, ObjectiveSetFile; `objectives` on QuestionTable
src/terezy/data/declarations/loader.py      EDIT objectives_from_file; `objectives` in question_from_document
src/terezy/data/declarations/resolver.py    EDIT OBJECTIVES_DIR, AnswerDeclarations, check_question
src/terezy/data/manifest.py                 EDIT `"objective_set"` in InputKind, and its `_ref` in the walk
src/terezy/api/answer.py                    EDIT thread the objective set into AnswerInputs
src/terezy/cli/main.py                      EDIT the dominance block, and 010's tie groups
data/objectives/owner-001.toml              NEW  the owner's two criteria and two bands (CL-1, CL-2)
data/questions/fifty-thousand.toml          EDIT `objectives = "..."`
tests/answer_registries.py                  EDIT the objective set on the fixture inputs
tests/fixtures/data/objectives/*.toml       NEW  the sets the fixture-only criteria need
docs/METHODOLOGY.md                         EDIT what dominance is here, and what the band is not
docs/REQUIRED_TESTS.md                      EDIT I2, and the notes for the rows this reinforces
```

**Structure Decision**: records in `core/results/`, functions in `core/decision/`, on the split
`results/candidates.py` and `decision/candidates.py` already make.

## The numbers this feature declares

Two, and both are the owner's: an indifference band of **0.0001** as a fraction of the question's
amount on the money, and **7** days on the date (CL-2). SC-001a asserts them against the shipped
declaration **by value**, because every other criterion here passes over *an* objective set and the
one thing nothing else notices is his answers never reaching `data/objectives/`.

Nothing else here is a number. No legal, tax or fee value is introduced, and comparing two computed
figures needs none.

## Required tests

**I2 only**, claimed on SC-002 and flipped by the task that lands it. The dominance step itself
closes no row, and the landing change records — in the notes beside Section I — that I3, I4, I5, I6
and I7 are now blocked on named things rather than on the decision layer not existing, and that I6
is **reinforced rather than covered**: its own words are about *allocations*, and there are none.
