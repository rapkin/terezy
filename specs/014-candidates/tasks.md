# Tasks: The candidate set, and what the loop discarded

**Feature**: `014-candidates` | **Date**: 2026-08-30

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md),
[data-model.md](./data-model.md)

Test-first throughout: every `T*` marked **(test)** lands before the `T*` it names, and must
fail without it — a test failing with `ImportError` counts. `[P]` marks tasks with no
dependency on each other.

---

## Phase 1 — the two pieces of work outside this feature's module

- [x] **T001 (test)** `tests/invariants/test_composition_search.py` — extend
      `TestTheQuestionsTheSearchRefusesToAnswer`, which already exercises all three and today
      tells them apart by searching `reason` for a substring: each refusal reports its own
      `Unaskable` case, and the three are distinct. Fails today — the field does not exist.
- [x] **T002** `src/terezy/core/results/composed.py` — add `Unaskable` (three members) and
      `CompositionRefused.case`. FR-014a, research D2.
- [x] **T003** `src/terezy/core/routes/compose.py` — set `case=` at each of `_refusal`'s three
      construction sites. No other change to 004's behaviour.
- [x] **T004** repair every existing site that constructs or asserts a `CompositionRefused`
      (004's suites) so the whole tree is green before anything of 014 exists.

- [x] **T005 (test)** `tests/contract/test_candidate_ceiling_declaration.py` — the loader
      refuses: an absent `candidates/` directory, two files, `max_candidates` below 1, an
      `[owner]` id no stream declares, a missing field. FR-019, research D9.
- [x] **T006** `src/terezy/data/declarations/schema.py` — `CandidatesTable`, `CandidatesFile`.
- [x] **T007** `src/terezy/data/declarations/loader.py` — `candidates_from_file`, on
      `composition_from_file`'s shape exactly.
- [x] **T008** `src/terezy/data/declarations/resolver.py` — `CandidateDeclarations`,
      `resolve_candidates`, `candidates_from_data_root`.
- [x] **T009** `data/candidates/owner-001.toml` — the declared ceiling, with the argument for
      its number in the file's own header.
- [x] **T010** `scripts/check_provenance.py` — `candidates` in `EXEMPT_DIRS`, with its reason.
      The gate is fail-closed: without this the new directory is an error.

**Checkpoint**: gates green, commit. 004's type is widened and the ceiling is declarable.

---

## Phase 2 — the records

- [x] **T011 (test)** `tests/unit/test_candidate_records.py` — the shapes are frozen, the two
      no-candidate reasons are different types, `EnumerationRefused` is a strict subset of
      `SurveyRefused`, and `TupleRefused` still has seventeen members (FR-006, asserted here
      as well as in 010's suite so this feature's own battery cannot drift from it).
- [x] **T012** `src/terezy/core/results/candidates.py` — every record in
      [data-model.md](./data-model.md). No function, no figure.

---

## Phase 3 — enumeration

- [x] **T013 (test)** `tests/worked_examples/test_candidate_enumeration.py` — the shipped
      registry: 18 pairs considered, 9 candidates, 9 pairs yielding none, every one of them
      `contract_usd` and `NothingConnects`. **Derived from the registry inside the test**, not
      hard-coded (SC-001).
- [x] **T014** `src/terezy/core/decision/candidates.py` — `enumerate_candidates`: the pair
      walk, `compose` both directions, the identity-exit carve-out, the plan cross, FR-016's
      total order, the four enumeration refusals, `pairs_considered`, provenance and staleness.
- [x] **T015 (test)** `tests/unit/test_no_candidate_column.py` — FR-013 versus FR-014 by
      **record**; compose's words carried verbatim (SC-008); a pair in the second column is
      never in the drop count.
- [x] **T016 (test)** `tests/unit/test_candidate_order.py` — SC-003 (same question twice; files
      renamed so they sort differently) and SC-011's second half (two plans supplied in the
      opposite order permute those two candidates and nothing else).
- [x] **T017 (test)** `tests/unit/test_candidate_refusals.py` — SC-009 (ceiling one above, zero
      candidates carried), SC-010 (a missing plan names the instrument), research D6's
      duplicate plan, and `QuestionDoesNotStandUp` for both question-level `Unaskable` cases.
- [x] **T018 (test)** `tests/unit/test_identity_exit_candidate.py` — SC-018 on a fixture
      registry whose `proceeds_to` is the spendable endpoint: the way out is the identity exit,
      the candidate is **evaluated**, and its way-out cost is a recorded zero.
- [x] **T019 (test)** `tests/unit/test_candidate_marks.py` — SC-014: the set reports the
      unverified mark the shipped access quotes carry, and reports stale for a value aged past
      its kind's threshold. Walked over the whole result rather than sampled.

**Checkpoint**: gates green, commit. The set exists and is measured.

---

## Phase 4 — the accounting

- [x] **T020 (test)** `tests/worked_examples/test_candidate_accounting.py` — both identities of
      FR-009 by hand on the shipped registry, with the arithmetic beside the assertion.
- [x] **T021** `src/terezy/core/decision/candidates.py` — `survey`, `evaluated`, `dropped`,
      `drop_tally`, and the two survey-only refusals.
- [x] **T022 (test)** `tests/unit/test_drop_tally.py` — SC-007: the tally recomputed from the
      retained records equals the tally reported; each group names the declarations its members
      implicate; the tally is derived and stored nowhere.
- [x] **T023 (test)** `tests/invariants/test_candidate_accounting.py` — SC-004: both identities
      over generated registries and questions, covering all-dropped, all-yielding-nothing, and
      nothing declared at all.
- [x] **T024 (test)** `tests/unit/test_candidate_survey.py` — SC-015 (benchmark index points at
      a member), FR-022's refusal when it is not one, `MoreThanOneStreamInTheSet`, and SC-002
      (a candidate's outcome through the loop is field-for-field the outcome `evaluate` gives
      the same key).
- [x] **T025 (test)** `tests/unit/test_candidate_regimes.py` — SC-013: two regimes, keys equal
      where the candidate exists in both, symmetric difference reported per regime.

**Checkpoint**: gates green, commit.

---

## Phase 5 — the seventeen, and the scans

- [x] **T026 (test)** `tests/unit/test_seventeen_refusals_through_the_loop.py` — SC-005. One
      case per member of `TupleRefused`, each either planted (moves exactly one candidate from
      evaluated to dropped, changes the no-candidate count by zero, appears in the tally under
      its own name) or **recorded unreachable with its reason**. The battery asserts its own
      coverage against `get_args(TupleRefused)`, so an eighteenth member fails here too.
- [x] **T027 (test)** `tests/contract/test_candidates_construct_nothing.py` — SC-019: every
      `route_in` object-identical to something `compose` emitted, every non-identity
      `route_out` equal to `exit_chain_of` of one, `FROM_THE_DECLARATION` in no produced set.
- [x] **T028 (test)** `tests/contract/test_candidates_add_no_rule.py` — SC-006 (no feasibility
      verdict constructed, matched on or raised in this feature's modules), SC-020 (no rate,
      channel or conversion), SC-022 (no branch on a refusal's `reason` text). Source scans
      over prose-stripped modules, using `tests/source_scan.py`.
- [x] **T029 (test)** `tests/contract/test_candidate_question_travels.py` — SC-012, SC-017,
      SC-021: everything FR-020 names reachable without a second `evaluate`; every count walked
      to its question; the plans-per-instrument statement; a tuple naming an undeclared thing in
      no population.
- [x] **T030 (test)** `tests/golden/test_candidate_set.py` — the shipped set as a checked-in
      golden: the nine keys in order, the nine no-candidate pairs, the tally. Evidence beside
      T013's derivation, never a freeze of the number.

**Checkpoint**: gates green, commit.

---

## Phase 6 — documentation, and the boxes

- [x] **T031** `docs/METHODOLOGY.md` — a new `## 32` before *Where to look next*: what a
      candidate set is, the three columns, the two identities, and why the ceiling refuses.
      Renumber *Where to look next* and run `scripts/check_methodology_refs.py`.
- [x] **T032** `docs/REQUIRED_TESTS.md` — flip **I1** with its test path and the note that
      §4.10.2's allocation candidates are a second population this feature does not prune.
      Re-read **B12** and **J4** and record what this feature does and does not add to each.
- [x] **T033** `specs/features.toml` — add to the `[[future]]` notes of
      `one-amount-per-stream-in-compare` and `zero-hop-way-in` where this feature made each
      visible. **Do not resolve either, and do not flip `status`.**
- [ ] **T034** `/condense` over the branch diff, then `/code-review` until clean.

---

## Dependencies

`T001→T004` gate everything (`compose`'s widened record is what FR-014 rests on).
`T005→T010` gate `T014` (the ceiling is an argument to it).
`T012` gates `T014`; `T014` gates `T021`; `T021` gates `T022`, `T023`, `T024`, `T026`, `T030`.
`T027`–`T029` need the modules to exist and nothing else. `T031`–`T033` last.

`[P]`: `T015`–`T019` after `T014`; `T022`, `T024`, `T025` after `T021`; `T027`–`T029` together.
