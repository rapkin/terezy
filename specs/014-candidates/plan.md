# Implementation Plan: The candidate set, and what the loop discarded

**Feature**: `014-candidates` | **Date**: 2026-08-30 | **Spec**: [spec.md](./spec.md)

**Branch**: `feat/014-candidates`, landing on `main` by a `--no-ff` merge after a clean
review pass.

## Summary

Every feature so far costs a tuple somebody typed out. This one finds them: it walks the
`(instrument × income stream)` pairs the registry admits, reads both route terms off what
004's `compose` emitted, crosses them with the run plans the caller supplied, and hands the
ordered set to 010's `compare`. The three places a pair can land — a candidate that was
evaluated, a candidate 010 dropped, a pair that was never a candidate — are separately
counted and the two identities between them are asserted (FR-009).

**It adds no feasibility rule.** Pruning is 010's seventeen typed refusals, reached by
`compare`'s own loop, and the union stays seventeen. **It constructs no route chain.** Both
route terms come off `compose`, with one carve-out: the identity exit, which `compose` states
it never emits.

Two pieces of work sit outside this feature's module and it cannot ship without either:
`CompositionRefused` gains a field saying which of its three cases fired (004's type, 004's
module — [research.md](./research.md) D2), and the candidate ceiling becomes a declaration
kind with a loader (D9).

## Technical Context

**Language/Version**: Python 3.13.

**Primary Dependencies**: none new.

**Storage**: version-controlled TOML. One new per-owner declaration file,
`data/candidates/owner-001.toml`, and one new directory in the provenance gate's exemption
list with its reason.

**Testing**: pytest. A property-based invariant for the accounting identity; hand-computed
worked examples for the shipped registry's 18 = 9 + 9; a golden set; four source-tree scans;
a seventeen-way battery over 010's union.

**Target Platform**: library only. No API, no CLI.

**Project Type**: single Python library, `cli → api → data → core`.

**Constraints**: core pure, no clock; no fifth plugin interface; functional style per D-E;
**no exchange rate, channel rate or currency conversion anywhere in this feature** (FR-005,
scanned by SC-020); one imported tolerance — this feature compares no floats of its own.

**Scale/Scope**: 2 new core modules, 1 record widened in 004, 1 new declaration kind across
schema/loader/resolver, 1 data file, 1 gate entry, ~11 test modules.

## Constitution Check

| Principle | Verdict |
|---|---|
| **I — Honesty over precision** | **PASS, and FR-019 is the principle applied to the loop itself.** A count above the ceiling refuses and returns nothing; a truncated set would answer a different question with an impeccable audit trail. Every count travels with the whole question that produced it (FR-012). The set carries the union of the marks enumeration read, so it never looks cleaner than the registry (FR-024, D8). |
| **II — Framework, not script** | **PASS.** No new plugin interface. The one new domain fact — how many candidates the owner will let a search produce — is a declaration under `data/`, with no default (D9). SC-006's scan asserts the loop contains no feasibility judgement of its own. |
| **III — Pure deterministic core** | **PASS.** Enumeration is a pure function of the declarations and the caller's inputs. `as_of` and the horizon are arguments; nothing reads a clock. FR-016's total order makes two runs equal element for element, and a registry loaded in a different file order produces the same sequence (SC-003). |
| **IV — Reliability through contracts** | **PASS.** Every degraded outcome is a typed record: a pair that yields nothing carries a tagged reason, a whole-enumeration failure is a typed refusal returned *instead of* a set. The accounting is an asserted identity, not a sentence (FR-009). No tolerance is defined here and none is needed. |
| **V — Test-first** | **PASS.** Each module lands after a test that fails without it. The shipped candidate set is a golden **and** is derived from the registry inside the test, so a golden that stopped matching the declarations fails on the derivation rather than freezing the number. Feature 016 took the set from nine to thirty-three and the derivation absorbed it. |
| **VI — The whole tuple** | **PASS, and this is the feature that makes the tuple findable.** Both route terms are per `(instrument × stream × route)` by construction. The three currency roles stay apart: FR-005 forbids converting one stream's amount into another's, and SC-020 scans for it. |
| **VII — Owner-scoped** | **PASS.** The ceiling is per-owner data beside `streams/`, `spendable/` and `composition/`, and its `[owner]` table is checked against the streams it is resolved with. |

No violation to justify, so **Complexity Tracking is empty**.

## Project Structure

### Documentation (this feature)

```text
specs/014-candidates/
├── spec.md
├── plan.md          # this file
├── research.md      # D1–D9, the decisions and what they were taken against
├── data-model.md    # the records, and which requirement each field carries
└── tasks.md
```

### Source

```text
src/terezy/core/results/candidates.py     NEW  every record this feature returns
src/terezy/core/decision/candidates.py    NEW  enumerate_candidates, survey, the derivations
src/terezy/core/results/composed.py       EDIT `Unaskable`, and `CompositionRefused.case`
src/terezy/core/routes/compose.py         EDIT set `case=` at the three refusal sites
src/terezy/data/declarations/schema.py    EDIT `CandidatesFile`, `CandidatesTable`
src/terezy/data/declarations/loader.py    EDIT `candidates_from_file`
src/terezy/data/declarations/resolver.py  EDIT `CandidateDeclarations`, `candidates_from_data_root`
data/candidates/owner-001.toml            NEW  the declared ceiling, with its argument
scripts/check_provenance.py               EDIT `data/candidates/` in `EXEMPT_DIRS`, with its reason
docs/METHODOLOGY.md                       EDIT new `## 32` before "Where to look next"
docs/REQUIRED_TESTS.md                    EDIT I1, and the B12/J4 notes
```

**Structure Decision**: records in `core/results/`, functions in `core/decision/`, on the
split `results/tuple.py` and `decision/compare.py` already make. `SegmentBound` living in
`results/composed.py` rather than beside `compose` sets the precedent for `CandidateCeiling`
living beside the set it bounds.

## Where this feature can be wrong

Not in arithmetic — it computes no number. It can be wrong in four places, and each has a
mechanical check rather than a rule to remember:

1. **A second opinion about feasibility growing up beside 010's.** SC-006 scans this
   feature's modules for a constructed `TupleRefused`, and `tests/unit/test_tuple_refusals.py`
   already pins the union at seventeen.
2. **A route chain built here.** SC-019 asserts every `route_in` in a produced set is
   *object-identical* to something `compose` emitted, and every non-identity `route_out`
   equals `exit_chain_of` of one — identity for the first because `compose` returns the record
   itself, equality for the second because that function builds a fresh one.
3. **The discrimination between the two no-candidate reasons decided by a string.** SC-022
   scans for any use of a refusal's `reason` other than carrying it through.
4. **A currency conversion.** SC-020 scans for a rate, a channel and a conversion.

## The one number this feature declares

The ceiling. It is data with no default, it refuses rather than truncates, and its value and
the argument for it are in `data/candidates/owner-001.toml` — see [research.md](./research.md)
D9. Nothing computes it and changing it changes no code.
