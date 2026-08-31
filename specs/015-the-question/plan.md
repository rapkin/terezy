# Implementation Plan: The question, and the answer that refuses in parts

**Feature**: `015-the-question` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Branch**: `feat/015-question`, landing on `main` by a `--no-ff` merge after a clean review.

## Summary

The vertical slice. A question becomes a declaration under `data/questions/`, one verb answers
it, and the answer holds one section per declared horizon — each section being 014's whole
`CandidateSurvey` or one of its typed refusals, carried whole. `api/` and `cli/` stop being
docstrings.

The deliverable is the **refusal**. Measured on the shipped registry the owner's own question
ranks nothing at any of his three horizons, and the answer's job is to say what was enumerated,
what dropped with which typed reason, which of his four named subjects the registry does not
declare at all, and which are declared but unreached — each with a name.

Six pieces of work sit **outside** this feature's module, each made where it lives:

| Where | What | Requirement |
|---|---|---|
| 014 `core/results/candidates.py`, `core/decision/candidates.py` | `Question.subjects`, and `_considered` narrowed to it | FR-008 |
| `data/groups.toml` + every instrument declaration + schema/loader/resolver | group ids, and the label on each instrument | FR-007a |
| 010 `core/decision/tuple_outcome.py`, `core/results/project.py` | the bond arm of `CannotSpanHorizon` becomes a sale at `horizon.end`; the missing resale price refuses through the existing `DeclarationMissing(part="access")` | FR-029, FR-031 |
| `core/instruments/access.py` + `data/access/` | a declarable resale price on the access record | FR-031 |
| `scripts/check_provenance.py` | `data/questions/` in `EXEMPT_DIRS`, with its reason | FR-003 |
| `terezy/data/manifest.py` | `as_of`, `regime`, a widened `InputKind`, and a manifest shape that is not single-projection | FR-023, FR-025, SC-008 |

## Technical Context

**Language/Version**: Python 3.13.

**Primary Dependencies**: none new. The CLI uses `argparse` from the standard library rather
than the declared `typer` extra — `cli/` is a renderer over one record and a dependency it
would use for one subcommand is one more thing that has to be installed to read an answer.

**Storage**: version-controlled TOML. One new per-owner declaration directory
(`data/questions/`), one new root-level curated vocabulary file (`data/groups.toml`, beside
`venues.toml`), one new belief under `data/scenarios/early_exit/`, and a `groups` key on every
instrument declaration.

**Testing**: pytest. Worked examples over the shipped registry; a golden artefact of the
owner's whole answer; walks over the whole result for the four properties a type cannot carry;
a battery over 014's refusal union, partitioned into what a question can plant and what it
structurally cannot.

**Target Platform**: library, plus a loopback-free CLI that reads files and writes stdout.

**Project Type**: single Python library, `cli → api → data → core`.

**Constraints**: the core stays pure; **no rate is derived and none is read from a series**
(FR-021, scanned by SC-004 and SC-028); no `Mark` in a core record (FR-024); no string this
feature composed in any record it returns (FR-020, scanned by SC-003); no objective, no scoring
weight, no shortlist.

**Scale/Scope**: four new core modules, one api module, one cli module, three new declaration
kinds across schema/loader/resolver, and the reshaped run manifest. The source list below is the
inventory; a count here would be a second copy of it.

## Constitution Check

| Principle | Verdict |
|---|---|
| **I — Honesty over precision** | **PASS, and this is the feature that makes the principle visible.** Nothing is ranked over the shipped registry and the answer says so per horizon with a typed reason each. FR-010 stops a ranking that reached two of four named subjects reading as a ranking of four. FR-030 withholds the one figure a one-month section could otherwise show rather than annotating it. |
| **II — Framework, not script** | **PASS.** The question is data, the group vocabulary is data, the spread-holds belief is data. No fifth plugin interface. A new kind of question is a schema field. |
| **III — Pure deterministic core** | **PASS.** `answer` is a pure function of the question, the declarations and `as_of`; `as_of` is a parameter of the verb and never a field of the file (FR-006). Loading and the manifest are the `data` layer's, rendering is `cli/`'s. |
| **IV — Reliability through contracts** | **PASS.** A section-level failure is a typed value carried whole, never a missing section. `Refused` is a different type from `Answer`, never a weaker one. No tolerance is defined here; this feature compares no floats of its own. |
| **V — Test-first** | **PASS.** Every module lands after a test that fails without it. The owner's answer is a golden **and** every count in it is derived from the registry the test loads. |
| **VI — The whole tuple** | **PASS.** Every candidate is 010's five-term key, unchanged. FR-021 forbids deriving an exchange rate; FR-021a lets the *owner* state one, marked, and SC-028 scans both sides. |
| **VII — Owner-scoped** | **PASS.** A question is per-owner data beside `streams/`, `spendable/`, `composition/` and `candidates/`, and its `[owner]` table is checked against the streams it is resolved with. The CLI listens on nothing. |

No violation to justify, so **Complexity Tracking is empty**.

## Project Structure

### Documentation (this feature)

```text
specs/015-the-question/
├── spec.md
├── plan.md          # this file
├── research.md      # D1–D12, the decisions and what they were taken against
├── data-model.md    # the records, and which requirement each field carries
└── tasks.md
```

### Source

```text
src/terezy/core/results/question.py        NEW  the declared question, its subjects, its reserves
src/terezy/core/results/answer.py          NEW  Answer, HorizonSection, the populations, Refused
src/terezy/core/decision/answer.py         NEW  `answer`, and the derived readings
src/terezy/api/answer.py                   NEW  load, call once, attach the manifest
src/terezy/cli/main.py                     NEW  one subcommand, rendering only
src/terezy/core/results/candidates.py      EDIT `Question.subjects` (014's record, FR-008)
src/terezy/core/decision/candidates.py     EDIT `_considered` narrowed to the subject set
src/terezy/core/instruments/interface.py   EDIT `InstrumentDeclaration.groups`
src/terezy/core/instruments/fund.py        EDIT `FundDeclaration.groups`
src/terezy/core/instruments/access.py      EDIT `InstrumentAccess.resale_price`
src/terezy/core/decision/tuple_outcome.py  EDIT the bond arm of `CannotSpanHorizon` (FR-029)
src/terezy/core/results/project.py         EDIT the sale at `horizon.end` (FR-029)
src/terezy/core/instruments/fixed_income.py EDIT the sale, and the refusal naming the price
src/terezy/core/instruments/enumerated.py  EDIT the same, over declared payments
src/terezy/core/instruments/acquire.py     EDIT `early_sale`, beside the purchase
src/terezy/core/ledger/events.py           EDIT `CausationKind.ACCESS_TERM`
src/terezy/core/results/tuple.py           EDIT `TupleOutcome.sold_early`
src/terezy/core/results/canonical.py       EDIT the canonical form of a whole answer
src/terezy/core/scenarios/early_exit.py    NEW  the spread-holds belief, as a record
src/terezy/data/declarations/schema.py     EDIT QuestionFile, GroupsFile, EarlyExitFile, groups, resale price
src/terezy/data/declarations/loader.py     EDIT question_from_file, groups_from_file, early_exit_from_file
src/terezy/data/declarations/resolver.py   EDIT AnswerDeclarations, groups, the answer's data root
src/terezy/data/manifest.py                EDIT as_of, regime, InputKind, of_answer
data/groups.toml                           NEW  the declared group vocabulary
data/instruments/*.toml                    EDIT `groups` on all nine
data/access/instruments.toml               EDIT the header's account of a resale price
data/scenarios/early_exit/owner-001.toml   NEW  the spread-holds belief, with its argument
data/questions/fifty-thousand.toml         NEW  the owner's own question
scripts/check_provenance.py                EDIT `data/questions/` in `EXEMPT_DIRS`, with its reason
pyproject.toml                             EDIT one console script
docs/METHODOLOGY.md                        EDIT the early-exit figure and what it excludes
docs/REQUIRED_TESTS.md                     EDIT H3, and the notes for the rows this reinforces
```

**Structure Decision**: records in `core/results/`, functions in `core/decision/`, on the split
`results/candidates.py` and `decision/candidates.py` already make.

## Where this feature can be wrong

Not in arithmetic — it computes one figure (the early exit) and everything else is 010's. It can
be wrong in six places, and each has a mechanical check rather than a rule to remember:

1. **A group inferred instead of read.** The four live near-misses — class, venue, tax class, id
   prefix — all look right on today's registry. SC-032's fixture fails under each.
2. **A sentence in the `Answer`.** SC-003 scans every string field of the whole result and
   requires it to be an id, a date, or a byte-for-byte copy of a string a core record already
   carried.
3. **The two counts conflated.** *Four named, two answerable* and *seven instruments enumerated*
   are different sentences. SC-030's fixture sets the group size ≠ the named-subject count so a
   conflated implementation cannot pass.
4. **A rate derived.** SC-004 and SC-028 scan from both sides, and the scan is scoped so that
   FR-021a's owner-stated rate is not caught by it.
5. **A mark lost between a declaration and a figure.** SC-017 and SC-025 walk the whole result
   rather than sampling.
6. **The group resolution reported but not read.** SC-033's pair — the same instrument added
   without and with the label — is the criterion; the unchanged half alone passes for three
   broken implementations.

## The numbers this feature declares

One: the **spread-holds** belief under `data/scenarios/early_exit/`. It has no default, it is
marked, and every figure computed through it inherits the mark. Nothing else here is a number —
the candidate ceiling and the segment bound are 014's and 004's, unchanged, and reach the verb
through its second parameter rather than through the question file (FR-014a, SC-019).
