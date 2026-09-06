# Tasks: Two regimes, side by side, and what the belief moved

**Feature**: `028-scenario-comparison` | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

**Implementation may not start until `026-answer-screen` is `done` on `main`** — its candidate
card, refusal group, figure slot and formatting module are what a column is made of, and building
a second column over an unlanded first one would rebuild them.

Tests are **not optional**. Principle V is NON-NEGOTIABLE; every module and component task is
preceded by the test that fails before it exists.

**Phase 6 may not start until Clarification 2 is answered**, and Phase 1's fixture recording
gains a second real pair only if Clarification 1 is answered A or B. Nothing else turns on either.

| Marker | Meaning |
|---|---|
| **[P]** | parallelisable — a different file, no dependency on an incomplete task |
| **[US1]**…**[US3]** | the user story it serves |
| **[API]** | needs a running API or a recorded response body |

---

## Phase 1 — the evidence the pure modules are tested against

- [ ] T001 [API] Record two served answers to `web/tests/fixtures/compare/` from the real API over the shipped root at a fixed `as_of`, with the recording command checked in beside them so a reader can reproduce the bytes rather than trust them.
- [ ] T002 Record a second pair whose fronts actually differ, from a data root composed with `tests/fixtures/data/`, so every membership state of FR-010 to FR-012 has a real body behind it — `web/tests/fixtures/compare/`.
- [ ] T003 [P] Declare, before T002 records against them, the fixture pair the recordings rest on: two questions differing **only** in their regime, and a scenario declaring both regimes — `tests/fixtures/data/questions/`, `tests/fixtures/data/scenarios/`.

## Phase 2 — the key and the lookup, which every claim rests on

- [ ] T004 [P] Test: the five-term key is injective — two rows sharing an instrument id and differing in `route_in`, in `route_out` or in `exit_terms` produce three different strings (FR-009) — `web/tests/unit/compare-key.test.ts`.
- [ ] T005 `web/src/compare/key.ts` — the five terms to a deterministic string. Not the engine's canonical form and asserted equal to nothing in `src/` (plan F3).
- [ ] T006 [P] Test: over the recorded pair, **every** key in `outcome.enumerated.candidates` resolves to exactly one named placement, and none falls through — `web/tests/unit/membership-lookup.test.ts`. This is Risk R1's guard: a population added later makes it red instead of making a row read *not enumerated*.
- [ ] T006a [P] Test: the three no-front states are distinct — a refused survey enumerates nothing, a benchmark that yielded no candidate still carries its enumeration, and a refused dominance pass beside a complete comparison renders its own reason — `web/tests/unit/membership-lookup.test.ts` (FR-014).
- [ ] T007 [P] Test: `inzhur_miltech`, which is in `ranked` and in no dominance population, resolves to **withheld from the pass** and not to *not enumerated* (plan F1) — `web/tests/unit/membership-lookup.test.ts`.
- [ ] T008 [P] Test: `indistinguishable` and `incomparable` are read as overlays — the lookup returns the member's placement, and a key that is both dominated and incomparable is reported dominated (plan F2) — `web/tests/unit/membership-lookup.test.ts`.
- [ ] T009 `web/src/compare/membership.ts` — the ordered lookup of `contracts/api-reads.md`, total over the enumerated population.

## Phase 3 [US1] — the reading, per horizon

- [ ] T010 [P] [US1] Test: horizons match by `(start, end)` exactly; a horizon in one answer only is returned as belonging to one column and is never paired by position (FR-008) — `web/tests/unit/horizon-match.test.ts`.
- [ ] T011 [P] [US1] Test: the union of the two fronts carries exactly one mark per key, and a member on one front only carries the other column's placement (FR-010, FR-011) — `web/tests/unit/membership-marks.test.ts`.
- [ ] T012 [P] [US1] Test: the *on neither front* group holds keys the pass **evaluated** in both columns, and `inzhur_miltech` — ranked and withheld — is not in it (FR-012) — `web/tests/unit/membership-marks.test.ts`.
- [ ] T013 [US1] Extend `web/src/compare/membership.ts` with the horizon match, the union and its four marks — in both, in the first only, in the second only, and the folded *on neither front* group.
- [ ] T014 [P] [US1] Test: a mark is readable with every style declaration stripped (FR-024) — `web/tests/unit/membership-mark.test.tsx`.
- [ ] T015 [US1] `web/src/compare/components/MembershipMark.tsx`.
- [ ] T016 [P] [US1] Test: a refusing section renders that column's own reason and no rows, and the other column is unaffected (FR-014); an empty union renders as an empty union and the horizon is not omitted — `web/tests/unit/horizon-pair.test.tsx`.
- [ ] T017 [US1] `web/src/compare/components/HorizonPair.tsx`.

## Phase 4 [US2] — a regime is a belief

- [ ] T018 [P] [US2] Test: a `regime_id` resolves to one of three named states — implicit, declared by one scenario, declared by several — and the several case names all of them rather than settling by preference (FR-015) — `web/tests/unit/regime-resolve.test.ts`.
- [ ] T019 [US2] `web/src/compare/regime.ts`.
- [ ] T020 [P] [US2] Test: a scenario column carries the scenario id, the assumption mark, the transition's rationale reachable in full without elision, and what the declaration carries instead of a source; an implicit column carries none of the four and renders the served string (FR-015 to FR-018) — `web/tests/unit/column-head.test.tsx`.
- [ ] T021 [US2] `web/src/compare/components/ColumnHead.tsx`, including the question id and its declaring file (FR-022).

## Phase 5 [US3] — what differs between the two questions

- [ ] T022 [P] [US3] Test: `id` and `asked_on` are excluded, every other differing field is named, and *only the regime differs* is true exactly when `regime_id` is the sole difference (FR-019, FR-020) — `web/tests/unit/question-difference.test.ts`.
- [ ] T023 [P] [US3] Test: two questions differing in regime and benchmark name both fields and state that the fronts do not differ by the regime alone — and the screen does not refuse (FR-021) — `web/tests/unit/question-difference.test.ts`.
- [ ] T024 [US3] `web/src/compare/difference.ts` and `web/src/compare/components/QuestionDifference.tsx`.

## Phase 6 — the tax-schedule gap *(blocked on Clarification 2)*

- [ ] T025 Test: a column under a declared scenario's regime states the gap, and an implicit column does not — `web/tests/unit/column-head.test.tsx`. The assertion's shape is the owner's answer: a caveat on the column, or the column refusing.
- [ ] T026 Implement the answered shape in `web/src/compare/components/ColumnHead.tsx` (FR-017).

## Phase 7 — the route, the picker, and the states

- [ ] T027 [P] Test: each of the two question-id parameters is validated, a missing or malformed one is a visible error naming the parameter, and no default is substituted (FR-001) — `web/tests/unit/search-params.test.ts`.
- [ ] T028 Extend `web/src/search/params.ts` with the two question-id parameters, on `parseAsOf`'s shape.
- [ ] T029 Extend `web/src/api/queries.ts` with the second answer read and the question and scenario reads the labels need, keyed by id and `as_of`. No registry read (FR-025).
- [ ] T030 [P] Test: with fewer than two declared questions the picker is a named state saying so and naming what to declare, never a hidden or disabled control (FR-006); with more, one labelled entry per other question (FR-004, FR-005) — `web/tests/unit/compare-picker.test.tsx`.
- [ ] T031 `web/src/compare/components/ComparePicker.tsx`, and its entry point on 026's answer screen in `web/src/routes/overview.tsx`.
- [ ] T032 [P] Test: loading, one column failed, both failed, and an undeclared id rendered as the served refusal for that column alone while the other still renders (FR-003, FR-023) — `web/tests/unit/compare-states.test.tsx`.
- [ ] T033 `web/src/compare/components/CompareStates.tsx` and the route in `web/src/routes/compare.tsx` (FR-001, FR-002).

## Phase 8 — end to end, and the Python half

- [ ] T034 [API] `web/e2e/compare.spec.ts` — against the real API over the shipped root, the same question in both columns: every front member marked *in both*, the fronts non-empty at all three horizons, and the difference block saying the two columns are one question (FR-027). The case is determinate over a root declaring one question and cannot pass on an empty set.
- [ ] T035 [P] [API] Extend `web/e2e/compare.spec.ts` to assert one answer request per distinct `(question id, as_of)` — **one** for the shipped-root case, where both columns name the same question — and no registry request (FR-025, SC-007).
- [ ] T036 [P] Extend `web/e2e/crawl.spec.ts` and `web/e2e/a11y.spec.ts` so the new route is crawled and checked like every other.
- [ ] T037 [P] `tests/contract/test_a_regime_reaches_the_answer.py` — two fixture questions differing only in their regime are answered under the regimes they name, and the manifest records the regime the run searched (FR-028). Cite, and do not duplicate, `tests/contract/test_the_answer_over_http.py::test_the_answer_takes_no_scenario_parameter` and `tests/contract/test_category_reads.py`.

## Phase 9 — landing

- [ ] T038 Flip `028-scenario-comparison` to `done` in `specs/features.toml`, and record in `docs/REQUIRED_TESTS.md` that I7 is **pressed on and not closed**: this feature reads across regimes and computes no intersection.
- [ ] T039 Run the full gates, then `/condense` over the branch diff, then `/code-review` — two rounds, three finding classes.

---

## Dependencies

Phase 1 → Phase 2 → Phase 3. Phases 4 and 5 depend on Phase 2 only and are parallel with each
other and with Phase 3. Phase 6 waits on Clarification 2. Phase 7 composes Phases 3 to 6.
Phase 8's T037 depends on T003 alone and may run at any time after it.

## Parallel opportunities

T001 with T003; T006/T007/T008 once T005 exists; T010–T012; Phase 4 against Phase 5; T034–T037.

## MVP

Phases 1, 2, 3 and 7, and T034: the two columns, the four membership states, the route and the
determinate end-to-end case. Phases 4 to 6 make the belief legible; without them the screen
compares two worlds without saying one is a guess, so they are not optional for shipping — only
for the first green.
