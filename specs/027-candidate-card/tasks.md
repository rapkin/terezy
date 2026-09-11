# Tasks: The candidate card — why exactly this figure

**Feature**: `027-candidate-card` | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

Every gate this depends on is met: `026-answer-screen` and `fix/undeployed-remainder` are on `main`,
and both clarifications were answered 2026-09-11 (`specs/decisions/2026-09-11-clarify-027.toml`),
which opens Phase 6.

Tests are **not optional**. Principle V is NON-NEGOTIABLE; every implementation task is preceded by
the test that fails before it exists.

| Marker | Meaning |
|---|---|
| **[P]** | parallelisable — a different file, no dependency on an incomplete task |
| **[US1]**…**[US3]** | the user story it serves |
| **[API]** | needs a response body or a running API |

---

## Phase 1 — the core stops discarding

Nothing is rendered. This phase either proves the accounting or finds out it does not close, which
is worth knowing before a component exists (plan R1).

- [ ] T001 [P] Test: two sections of one answer give one candidate two distinct published keys, and the same section gives the same one twice — `tests/unit/test_the_candidate_key.py` (FR-006).
- [ ] T002 Publish the key on each evaluated outcome, rendered in `src/terezy/core/results/canonical.py` from the five-term identity plus the horizon, and carried on `TupleOutcome` as `projection_key` — the one field FR-002 permits, and **not** `key`, which is already the five-term `Tuple` and would read as the same thing on the wire (FR-006).
- [ ] T003 [P] Test: no module under `src/terezy/api/http/` composes a candidate key — extend `tests/contract/test_the_http_layer_computes_nothing.py` (FR-006). A scan, warranted because the typecheck cannot see a string built from `key.instrument_id`.
- [ ] T004 [P] Test: each member of the union carries its own arm's dated lines — a bond its schedule rows, `inzhur_miltech` its exit line and, in the shipped window, no distribution — and a bar an arm states no flow for is a typed absence naming it — `tests/unit/test_the_served_projection.py` (FR-003, FR-007).
- [ ] T005 The serialisable projection **union** — one member per projection kind — and its refusal in `src/terezy/core/results/` — the flows, the charges with their bases, the purchase with its date and its clean/accrued split, the premium, the two route charges by component and their declared latencies. Every field a value the join already holds (FR-001, FR-003 to FR-005, FR-007).
- [ ] T006 Widen `_Acquisition` in `src/terezy/core/decision/tuple_outcome.py` to carry the clean/accrued split `_price_for` sums away, and carry the way-in and way-out charges and latencies through `_assemble` (FR-005; plan R2).
- [ ] T007 `evaluate` returns the projection **beside** the outcome; its one caller, `core/decision/compare.py:106`, keeps the outcome half and discards the other unchanged (FR-001, FR-002).
- [ ] T008 [P] Test: the answer's rendered lines and `digest_of_answer` do not move — run `tests/golden/the_answer.golden.txt` and `candidate_set.golden.txt` unchanged (FR-002).
- [ ] T009 Test: for **every ranked candidate** of the owner's declared question over the shipped `data/` — every member of the union, `inzhur_miltech` and the cash baseline included, none skipped — the served flows account for `reaches` at the **imported** project tolerance, and every served flow carries a mark — `tests/contract/test_the_card_accounts_for_what_came_back.py` (FR-030, SC-001, SC-002).
- [ ] T010 Update `docs/METHODOLOGY.md` §29 with what the served projection carries and what it still does not — the ledger, and the terms the way-out charge is netted against out of order (FR-008).

## Phase 2 — the endpoint [API]

- [ ] T011 [P] Test: an unknown question and a key naming no evaluated candidate are **two** distinguishable typed results — and there is no third, because a refused candidate carries no key — `tests/contract/test_the_projection_over_http.py` (FR-011).
- [ ] T012 The envelope in `src/terezy/api/http/envelopes.py` and one GET route in `service._register_fixed`, taking `as_of` and no `scenario_id`: it answers the question to resolve the key to its tuple and horizon, then evaluates that one candidate (FR-009; plan Finding 3).
- [ ] T013 [P] Test: the new path is in the route table's fixed set, it is a GET, its records are distinctly tagged and named, its unions are discriminated on `tag`, every `Money` in it carries provenance, and its bytes are reproducible across hash seeds — extend `tests/contract/test_the_route_table.py` and `test_tags_and_unions.py` (FR-010).
- [ ] T014 Bump `document.VERSION` in the same commit as the wire change (FR-010).
- [ ] T015 [P] Test: the answer document's size is unchanged **by this feature** beyond the published key, measured on the **response body** against a baseline re-taken on the tree this branch starts from — never the 8 492 187 bytes of 2026-09-07, which `fix/undeployed-remainder` moves for its own reasons — `tests/contract/test_the_answer_over_http.py` (FR-012, SC-005).

## Phase 3 — pure functions over served shapes

- [ ] T016 [P] Test: one case per row of plan Finding 4, and a fixture whose bars would sum wrong still yields the served amounts — `web/tests/unit/bars.test.ts` (FR-013, FR-014). [US1]
- [ ] T017 `web/src/card/bars.ts` — served flows → the ordered bar list, with the way-out bar per dated release rather than per flow. Reads no `parts`; performs no subtraction (FR-013, FR-014). [US1]
- [ ] T018 [P] Test: a zero charge carrying sources and one carrying none, both from the shipped registry's own cases — `web/tests/unit/zeros.test.ts` (FR-017). [US1]
- [ ] T019 `web/src/card/zeros.ts` — the two zeros, discriminated on whether the charge carries sources (FR-017). [US1]
- [ ] T020 [P] Test: mixed currencies yield `false`, one currency `true`, and the return type carries no figure and no rate — `web/tests/unit/currencies.test.ts` (FR-015). [US1]
- [ ] T021 `web/src/card/currencies.ts` — the grouping predicate (FR-015). [US1]
- [ ] T022 [P] Test: an event outside the window is outside and marked; a date whose payment its own tax consumed exactly is present; a latency segment's length is the served declared days — `web/tests/unit/events.test.ts` (FR-020 to FR-023). [US2]
- [ ] T023 `web/src/card/events.ts` — served flows and dates → placed events, the two boundaries, and latency segments from the declared days (FR-020 to FR-023). [US2]
- [ ] T024 [P] Test: a bar the arm states no flow for, and each of the two endpoint refusals, render as their own named state — never a zero and never a blank — `web/tests/unit/refusals.test.ts` (FR-007, FR-011, FR-016).
- [ ] T025 `web/src/card/refusals.ts` (FR-011, FR-016).

## Phase 4 — the two components, against fixtures

- [ ] T026 [P] Test: each bar state; the bars readable as text with every style declaration stripped; a two-currency fixture draws no joined baseline — `web/tests/unit/waterfall.test.tsx` (FR-013, FR-015, FR-016, FR-018, FR-019). [US1]
- [ ] T027 `web/src/card/components/Waterfall.tsx` — FR-013's order, refusal bars, a mark per bar, per-currency grouping, and the statement that the bars do not sum to the rate (FR-013, FR-015, FR-016, FR-018, FR-019). [US1]
- [ ] T028 [P] Test: both zeros render differently, neither is blank, and the base is beside the charge with the class named — `web/tests/unit/tax-bar.test.tsx` (FR-017). [US1]
- [ ] T029 `web/src/card/components/TaxBar.tsx` (FR-017). [US1]
- [ ] T030 [P] Test: each event kind, an event outside the window, a missing latency, the remainder's arrival and its named absence, and the whole readable as text with styles stripped — `web/tests/unit/timeline.test.tsx` (FR-020 to FR-024). [US2]
- [ ] T031 `web/src/card/components/Timeline.tsx` (FR-020 to FR-024). [US2]
- [ ] T032 [P] Test: a marked bar carries 026's badge, the full citation is reachable behind one disclosure, the belief is not repeated, and no raw float reaches the output — `web/tests/unit/candidate-card.test.tsx` (FR-025 to FR-027). [US3]
- [ ] T033 `web/src/card/components/CandidateCard.tsx` — the waterfall, the timeline, the marks, the disclosure, every figure through 026's formatter (FR-025 to FR-027). [US3]

## Phase 5 — the card on the screen [API]

- [ ] T034 [P] Test: a named wait and a named failure, neither a spinner nor an empty card — `web/tests/unit/card-states.test.tsx` (SC-006).
- [ ] T035 `web/src/api/queries.ts` — `projectionQuery(questionId, candidateKey, asOf)`, one request per opened card (SC-006).
- [ ] T036 `web/src/card/components/CardRoute.tsx` — openable from **any** ranked row of the answer screen, closable back to the reader's place (FR-028). [US3]
- [ ] T037 [P] E2E: open a card from the answer screen and assert each bar's amount equals the served flow of the same date and kind, and that the card's *money back* is the served `reaches` — `web/e2e/card-waterfall.spec.ts` (SC-001, SC-004). [US1]
- [ ] T038 [P] E2E: every event and boundary the API sends is on the timeline; none is dropped, clamped or merged — `web/e2e/card-timeline.spec.ts` (SC-007). [US2]
- [ ] T039 [P] E2E: no unrounded float reaches the card, and opening one issues exactly one request — `web/e2e/card-text.spec.ts` (SC-006, SC-008). [US3]
- [ ] T040 [P] Test: no module under `web/src/card/` subtracts one served figure from another to obtain a bar — a source scan beside `bars.ts`, warranted because the typecheck cannot see arithmetic over two served amounts — `web/tests/unit/no-derived-bar.test.ts` (SC-004).
- [ ] T041 Extend 021's whole-UI crawl and the accessibility pass to the card in both themes (FR-029, SC-008).

## Phase 6 — what turned on a clarification

- [ ] T042 CL-1: **nothing is built.** The answer is that no rate is served and none is rendered, so the work is the test that the tax bar names the base, the charge and the class and carries no rate — `web/tests/unit/tax-bar.test.tsx` (FR-004).
- [ ] T043 CL-2: the six-part attribution beside the waterfall, labelled as its own reading and folded by default — `web/src/card/components/Attribution.tsx`, with its test first (FR-014).

## Landing

- [ ] T044 Flip **E11** in `docs/REQUIRED_TESTS.md` with its test path, and record the rows this feature reinforces with the reason per row that no other box moves (SC-003).
- [ ] T045 Flip 027's `status` in `specs/features.toml` to `done`.
