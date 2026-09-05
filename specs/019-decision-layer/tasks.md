# Tasks: Dominance, and the set that has no winner

**Feature**: `019-decision-layer` | **Date**: 2026-09-05

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

Every `T*` marked **(test)** lands before the tasks under it and must fail without them — an
`ImportError` counts. `[P]` marks tasks with no dependency on each other; `[US1]`–`[US5]` name the
user story. Each **Checkpoint** is a `/commit` with every gate green. The *why* of every design
choice is in [research.md](./research.md); it is not repeated here.

**Nothing starts until `fix/coupon-inside-the-window` and `feat/real-only-registry` are on `main`**
(research D12). **(re-measures)** marks the tasks whose figures move when they land.

---

## Phase 1 — the slack, as a value (FR-011c; the project tolerance's module, 001 FR-002)

- [ ] **T001 (test)** `tests/invariants/test_the_slack_is_the_comparison.py` — over generated finite pairs, `is_close(a, b) == (abs(a - b) <= slack(a, b))`, and `slack` is symmetric and never below `TOLERANCE`.
- [ ] **T002** `src/terezy/core/primitives/tolerance.py` — `slack(left, right, *, tolerance=TOLERANCE)`, beside `is_close` and not replacing it (research D3).

**Checkpoint**: gates green, commit.

---

## Phase 2 — the objective set as a declaration (FR-001 to FR-005, FR-011b, FR-011d) `[US5]`

- [ ] **T003 (test)** `[US5]` `tests/contract/test_objective_declaration_loading.py` — every row of [contracts/the-declaration.md](./contracts/the-declaration.md)'s refusal table, one assertion each, each variant a textual mutation of the shipped file (SC-003 less T009's two).
- [ ] **T004** `[US5]` `src/terezy/core/results/objectives.py` — `Criterion`, `ObjectiveDirection`, `AbsoluteBand`, `FractionOfTheQuestionAmount`, `DaysBand`, `Objective`, `ObjectiveSet`.
- [ ] **T005** `[US5]` `src/terezy/data/declarations/schema.py` — `ObjectiveTable`, `BandTable`, `ObjectiveSetTable`, `ObjectiveSetFile`, every field required.
- [ ] **T006** `[US5]` `src/terezy/data/declarations/loader.py` — `OBJECTIVES_TABLE`, `objectives_from_file`, with the band-shape check FR-011d requires.
- [ ] **T007** `[US5]` `src/terezy/data/declarations/resolver.py` — `OBJECTIVES_DIR`, `_check_objectives_owner`, the empty-directory and duplicate-id refusals, `objective_sets` on `AnswerDeclarations`.
- [ ] **T008** `[US5]` `data/objectives/owner-001.toml` — CL-1's two criteria and CL-2's two bands, replacing the `.gitkeep`.
- [ ] **T009 (test)** `[US5]` `tests/contract/test_question_declaration_loading.py` — a question with no `objectives` refuses; one naming an undeclared set refuses through `resolver.check_question` (FR-001a).
- [ ] **T010** `[US5]` `core/results/question.py`, `schema.py`, `loader.question_from_document`, `resolver.check_question` — the required `objective_set_id`.
- [ ] **T011** `[US5]` `data/questions/fifty-thousand.toml` — `objectives = "money-and-when"`.
- [ ] **T012 (test)** `[US5]` `tests/worked_examples/test_the_owners_objectives.py` — SC-001a: the shipped declaration holds a fraction of **0.0001** and **7** days, by value.

**Checkpoint**: gates green, commit.

---

## Phase 3 — the manifest names the set (FR-030; `data/`, 015 FR-025's module) `[US5]`

- [ ] **T013 (test)** `[US5]` `tests/unit/test_answer_manifest.py` — an answer's manifest carries an `InputRef` of kind `objective_set` naming the file and its version.
- [ ] **T014** `[US5]` `src/terezy/data/manifest.py` — `"objective_set"` in `InputKind`, and its `_ref` in `answer_input_refs`.

**Checkpoint**: gates green, commit.

---

## Phase 4 — the relation (FR-007, FR-011a to FR-011c) `[US1]` `[US2]`

- [ ] **T015 (test)** `[P]` `[US1]` `tests/invariants/test_dominance_relation.py` — SC-004 at three to five objectives, bands drawn at or above `(p − 1) · slack`; figures on `[-6e-9, 6e-9]`, where the slack is exactly `TOLERANCE` (research D2).
- [ ] **T016 (test)** `[P]` `[US1]` `tests/worked_examples/test_dominance_is_not_transitive.py` — SC-004a's planted triple, arithmetic checked in beside the assertion.
- [ ] **T017** `[US1]` `src/terezy/core/results/dominance.py` — the figures, widths, `PairVerdict`, the verdicts, populations and the six-member `DominanceRefused` union of [data-model.md](./data-model.md).
- [ ] **T018** `[US1]` `src/terezy/core/decision/dominance.py` — `relates`, FR-007's definition, in one place, over tagged figure vectors (research D1, D7a).
- [ ] **T019 (test)** `[US2]` `tests/unit/test_indifference_bands.py` — SC-006's four cases, the third asserted in both candidate-key orders and the fourth both ways round.
- [ ] **T020** `[US2]` `src/terezy/core/decision/dominance.py` — the indifference relation, per candidate, never a partition (FR-011, FR-011a).
- [ ] **T021 (test)** `[US2]` `tests/unit/test_the_acyclicity_floor.py` — a band below the slack at two objectives, and one of one and a half slacks at **three**, each producing `BandBelowTheAcyclicityFloor` and no set.
- [ ] **T022** `[US2]` `src/terezy/core/decision/dominance.py` — both of FR-011c's conditions, `band > slack` and `band >= (p − 1) · slack`, against the widest slack in the section; skipped on a date objective.

**Checkpoint**: gates green, commit.

---

## Phase 5 — the pass over a section (FR-006 to FR-010, FR-011d, FR-014, FR-016 to FR-018a) `[US1]` `[US3]`

- [ ] **T023** `[US1]` `tests/fixtures/data/` — the fixtures the phase plants, named against the test that plants each: T030 (nothing dominates the benchmark; something does), T031 (a `BenchmarkUnavailable` section; a withheld benchmark; a section that never surveyed), T033 (an outcome with no arrivals; a section delivering two currencies), T036 (members on differing and on identical assumptions), T045 (a second objective set and a second question naming it). **First in the phase.**
- [ ] **T024 (test)** `[P]` `[US1]` `tests/unit/test_dominance_populations.py` — FR-008's identity asserted; a lone evaluated candidate is non-dominated; nothing is pruned (FR-009).
- [ ] **T025 (test)** `[P]` `[US1]` `tests/unit/test_dominance_band_resolution.py` — a fraction resolves per currency and only where a pair is compared; absent and ambiguous produce two different refusals (research D6).
- [ ] **T026** `[US1]` `src/terezy/core/decision/dominance.py` — `dominance(outcome, *, withheld, excludes, objectives, amounts)`: the readers, the resolution, the pairwise pass, the three populations, `resolved_bands`.
- [ ] **T027** `[US1]` `src/terezy/core/decision/dominance.py` — `why_one_member`, derived from FR-008's counts (FR-014).
- [ ] **T028 (test)** `[P]` `[US1]` `tests/unit/test_dominance_provenance.py` — SC-012, walked over the whole result rather than sampled.
- [ ] **T029** `[US1]` `src/terezy/core/decision/dominance.py` — `prov.merge` and `staleness.merge` on every verdict (FR-022).
- [ ] **T030 (test)** `[P]` `[US3]` `tests/unit/test_the_hurdle_in_the_set.py` — SC-008, the *nothing dominates the hurdle* wording included.
- [ ] **T031 (test)** `[P]` `[US3]` `tests/unit/test_dominance_refuses_without_a_hurdle.py` — SC-009 (the reason verbatim, by string comparison), SC-009a (a different reason, by comparing records), and `NoSurveyToRunOver` (research D6a).
- [ ] **T032** `[US3]` `src/terezy/core/decision/dominance.py` — FR-016's membership, FR-017's standing, and the three refusals of FR-018, FR-018a and D6a.
- [ ] **T033 (test)** `[P]` `[US1]` `tests/unit/test_incomparable_pairs.py` — SC-013 and SC-014's four halves, no exchange rate consulted anywhere.
- [ ] **T034** `[US1]` `src/terezy/core/decision/dominance.py` — FR-008a: incomparability per pair, *not placed* as the every-pair condition with at least one pair.
- [ ] **T035 (test)** `[P]` `[US1]` `tests/unit/test_a_withheld_candidate_decides_nothing.py` — SC-015 on `inzhur_miltech`.

**Checkpoint**: gates green, commit. The pass refuses in the five ways this phase owns — FR-018,
FR-018a, D6a's `NoSurveyToRunOver` and FR-011d's two. FR-011c's floor is Phase 4's.

---

## Phase 6 — what separates the members (FR-015, FR-019 to FR-021) `[US4]`

- [ ] **T036 (test)** `[US4]` `tests/unit/test_separating_assumptions.py` — SC-010's three cases on T023's fixtures, ids and words compared byte-for-byte.
- [ ] **T037** `[US4]` `src/terezy/core/decision/dominance.py` — the separating read, over `rests_on` and the **section's** `excludes`, verbatim (FR-015, FR-019, FR-020).
- [ ] **T038 (test)** `[US4]` `tests/contract/test_no_deciding_assumption_is_claimed.py` — SC-011. Scans this feature's source as text because the criterion is the **absence** of a field and of a claim, which no value can be read for.

**Checkpoint**: gates green, commit.

---

## Phase 7 — the answer carries it (FR-023 to FR-025, FR-027, FR-028) `[US1]` `[US5]`

- [ ] **T039 (test)** `[US1]` `tests/unit/test_the_section_carries_the_dominance_result.py` — SC-016a's survey equality field for field, FR-023's bands and widths, FR-025's order. Its FR-028 half scans the result's strings, because *this string was composed here* is a property of the source and not of the value.
- [ ] **T040** `[US1]` `src/terezy/core/results/answer.py` — `HorizonSection.dominance`, required, `DominanceResult | DominanceRefused`.
- [ ] **T041** `[US1]` `src/terezy/core/decision/answer.py` — `AnswerInputs.objectives`, and `_section` calling the pass with the parts it already computes (research D9a).
- [ ] **T042** `[US1]` `src/terezy/api/answer.py`, `tests/answer_registries.py` — thread the resolved objective set into `AnswerInputs`.
- [ ] **T043** `[US1]` `src/terezy/core/results/canonical.py` — `of_section` encodes the dominance result; moves every answer digest (research D9).
- [ ] **T044 (test)** `[US1]` `tests/invariants/test_determinism.py` — SC-017's two runs and the renamed-files run.
- [ ] **T045 (test)** `[US5]` `tests/worked_examples/test_two_objective_sets_disagree.py` — SC-002's both halves. **Flips I2 in `docs/REQUIRED_TESTS.md`.**

**Checkpoint**: gates green, commit.

---

## Phase 8 — the surface a person reads (FR-029, FR-029a) `[US2]` `[US3]`

- [ ] **T046 (test)** `[US2]` `tests/contract/test_cli_is_sugar_over_the_file.py` — SC-016: every item found in the output, each naming candidates rather than positions, no withheld candidate mentioned, and two sections rendering differently.
- [ ] **T047** `[US3]` `src/terezy/core/decision/answer.py` — `section_ties` and `section_beats_benchmark`, resolving 010's indices to keys and narrowing to the reported population (FR-029a).
- [ ] **T048** `[US2]` `src/terezy/cli/main.py` — `_dominance_lines(section)`, and `_beats_line` reading `section_beats_benchmark` and rendering the tie groups by candidate.

**Checkpoint**: gates green, commit.

---

## Phase 9 — the scans, the golden and the record `[US1]`

- [ ] **T049 (test)** `[P]` `[US1]` `tests/contract/test_dominance_adds_no_objective_of_its_own.py` — SC-005. Scans this feature's source as text because both halves are absences: no feasibility verdict constructed, no weight declared.
- [ ] **T050 (test)** `[P]` `[US1]` `tests/contract/test_two_closeness_rules_stay_apart.py` — SC-007. Scans as text because the criterion is *which call sites exist*, which no run observes.
- [ ] **T051 (test)** `[US1]` **(re-measures)** `tests/worked_examples/test_the_owners_question.py` — SC-001, every count derived from what the test loads and none hard-coded.
- [ ] **T052** `[US1]` **(re-measures)** `tests/golden/test_the_answer.py`, `tests/golden/the_answer.golden.txt` — SC-018, regenerated with the diff read and the changed lines quoted.
- [ ] **T053** `[P]` `docs/METHODOLOGY.md` — what dominance is here, and what an indifference band is not.
- [ ] **T054** `docs/REQUIRED_TESTS.md` — I2 flipped with T045's path, and the Section I notes recording that I6 is reinforced rather than covered.
- [ ] **T055** `specs/features.toml` — `status = "done"`, and the two gaps research D6 records.

**Checkpoint**: gates green, `/condense`, `/code-review`, land by `--no-ff` merge.

---

## Dependencies

```text
Phase 1 ──┐
Phase 2 ──┼──▶ Phase 4 ──▶ Phase 5 ──┬──▶ Phase 6 ─┐
Phase 3 ◀─┘                          ├──▶ Phase 7 ─┼──▶ Phase 9
                                     └──▶ Phase 8 ◀┘
```

Phase 3 needs Phase 2's resolver fields; Phase 4 needs Phases 1 and 2; Phase 5 needs Phase 4, and
**T023 comes first inside it**; Phase 8 needs Phase 7's `HorizonSection` field. Phase 9's two
**(re-measures)** tasks are written last, because their inputs move under both branches in flight.

## Which rows and artefacts move

| Task | Moves |
|---|---|
| **T045** | flips **I2** — the only row this feature closes |
| **T051** | the owner's-question worked example; **re-measures** |
| **T052** | the golden, and every answer digest (T043) |
| **T054** | the Section I notes |

## MVP

Phases 1, 2, 4 and 5 — User Story 1 whole. Stories 2, 3 and 5 complete after Phases 7 and 8;
Story 4 is Phase 6.
