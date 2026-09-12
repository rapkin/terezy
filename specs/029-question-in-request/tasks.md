# Tasks: The question goes in the request body

**Feature**: `029-question-in-request` | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

Both `needs` are `done` on `main` (`015-the-question`, `020-http-api`), so implementation is
unblocked. **Two clarifications are open**; Phase 7 is the only phase either gates, and CL-2 gates
nothing here.

Tests are **not optional**. Principle V is NON-NEGOTIABLE; every implementation task is preceded by
the test that fails before it exists.

| Marker | Meaning |
|---|---|
| **[P]** | parallelisable — a different file, no dependency on an incomplete task |
| **[US1]**…**[US3]** | the user story it serves |
| **[API]** | needs a running application or a response body |

---

## Phase 0 — the round trip, red

- [ ] T001 [P] [US1] Test: the document of `data/questions/fifty-thousand.toml`, rendered as JSON and read back, builds a `Question` equal field for field to `loader.question_from_file`'s — `tests/unit/test_a_question_from_a_document.py` (FR-001, SC-002).
- [ ] T002 [P] [US1] Test: every field of `schema.QuestionFile`, walked recursively, is a string, number, boolean, list or nested model — asserted over the schema, not over a list of names, so a TOML-only field added later is red — `tests/contract/test_a_question_is_json_expressible.py` (FR-002, SC-003). A schema scan, warranted because the type checker accepts a `date` field that JSON cannot carry.

## Phase 1 — the question's identity in the manifest

- [ ] T003 [P] [US3] Test: two documents differing in one horizon digest differently; and the three spellings one question has — the file's own, an amount written as an integer, an optional field written as an explicit `null` — all digest identically, because the digest is of the validated record — `tests/unit/test_the_question_digest.py` (FR-018).
- [ ] T004 [US3] The canonical renderer and `sha256:<hex>` digest of a **validated** question document in `src/terezy/data/manifest.py`, beside the digesting it feeds. Not shared with `api/http/document.rendered`, which serves a wire artefact (FR-018; plan Finding 4).
- [ ] T005 [US3] `manifest.answer_input_refs` records the **answered** question as an input when it has no file: kind `question`, the body/flags sentinel where a path would be, the digest as its version (FR-019). It takes only `AnswerDeclarations` today and cannot see which question was answered, so this is a signature change reaching `manifest.of_answer`, its four call sites in `tests/unit/test_answer_manifest.py`, `test_overlay_manifest.py` and `test_the_registry_summary.py`, and `api/projection.py` — 027's endpoint, the caller an implementer following the answer path alone would miss.
- [ ] T006 [P] [US3] Test: a file-declared question's input version is still the digest of the file's bytes, asserted over the **manifest's** inputs — `tests/unit/test_the_question_digest.py` (FR-021). Not over `tests/golden/the_answer.golden.txt`, which renders no manifest input at all and would stay green whatever this phase does to them.
- [ ] T007 [US3] Delete the claim in `api/answer.answer_declared` that a question with no file contributes no input reference. The change falsifies it.
- [ ] T008 [P] [US3] Test: `terezy --set` over the document of `fifty-thousand.toml` yields a manifest whose question input carries the digest T004 computes for that document — `tests/unit/test_the_cli_records_its_question.py` (FR-020, SC-007).

## Phase 2 — attribution

- [ ] T009 [P] [US2] Test: a question naming an undeclared regime refuses naming **the question's own artefact** and the field `question.regime`, for a file-declared question and for a caller-built record alike — `tests/unit/test_an_undeclared_regime_blames_the_question.py` (FR-015).
- [ ] T010 [US2] Move **both** undeclared-regime refusals off `root/scenarios` and onto the question's artefact in `src/terezy/api/answer.py` — `_scenario_of`'s and `inputs_of`'s, which are near-identical and both rooted at `resolver.SCENARIOS_DIR` (FR-015; plan Finding 3).
- [ ] T011 [P] [US2] [API] Test: a body fault is attributed to the request and a data-root fault to the server — **both cases in one test file**, so neither passes by answering everything one way — `tests/contract/test_a_broken_declaration_reaches_the_caller.py` extended (FR-013, SC-005).
- [ ] T012 [US2] The `DeclarationError` handler in `src/terezy/api/http/service.py` branches on which artefact the refusal names (FR-013, FR-014).

## Phase 3 — the endpoint [API]

- [ ] T013 [P] [US1] Test: posting the document of `fifty-thousand.toml` with the saved question's `as_of` returns an answer byte-identical to `GET /api/questions/fifty-thousand-hryvnia/answer`, and a manifest carrying **exactly one added input** — the body's own question reference — and otherwise equal. An added input rather than a differing one, for SC-001's reason: the file's ref survives, because every declared question file is recorded whichever was answered — `tests/contract/test_the_answer_from_a_body.py` (FR-009, SC-001).
- [ ] T014 [US1] `POST /api/answers` in `service._register_fixed`: the **raw** body into `loader.question_from_document` with a body sentinel, `as_of` as the required query parameter, no `scenario_id` (FR-007, FR-004).
- [ ] T015 [US1] The published request schema on that route, generated from `schema.QuestionFile` rather than written out, so it cannot drift from the validator (FR-001; plan Finding 2).
- [ ] T016 [US1] The response container in `src/terezy/api/http/envelopes.py` — the answer and its manifest, with **no** `CategoryHasNoSuchId` member, which a POST can never produce (plan, Phase 3).
- [ ] T017 [P] [US1] [API] Test: `GET /api/questions/{id}/answer` is unchanged — same path, same envelope, same body for the shipped question — `tests/contract/test_the_answer_over_http.py` extended (FR-008).

## Phase 4 — the boundary's refusals [API]

- [ ] T018 [P] [US2] Test: a body missing `question.objectives`, a body with an unrecognised field, and a body naming an owner no stream belongs to each produce the loader's four fields and the same tag the equivalent **file** fault produces — `tests/contract/test_a_body_refuses_like_a_file.py` (FR-003, FR-012, SC-004).
- [ ] T019 [US2] Carry the loader's record verbatim at the boundary, naming the request where a file names its path; synthesise no message, code or severity (FR-012, FR-014, SC-006).
- [ ] T020 [P] [US1] Test: a posted body whose subjects are group labels resolves exactly as the file's do — the same four standings and the same counts as the saved read, `btc` **held** rather than undeclared — and a body naming a word nothing declares reaches the undeclared population, which the shipped question leaves empty — `tests/contract/test_the_answer_from_a_body.py` (FR-017).
- [ ] T021 [P] [US1] Test: a posted body whose plan names nothing returns `PlanForNothing` in a **200** body, the same shape an answer has — `tests/contract/test_the_answer_from_a_body.py` (FR-016).
- [ ] T022 [P] [US3] [API] Test: one body, one `as_of`, one data root, answered in two processes under two hash seeds — identical answer digest and identical manifest — `tests/contract/test_the_answer_from_a_body.py` (FR-022, SC-008).
- [ ] T023 [P] [US1] [API] Test: every `Money` in a posted answer carries provenance and the unverified roll-up equals the saved read's — `tests/contract/test_marks_survive_the_join.py` extended (FR-023).

## Phase 5 — the cap

- [ ] T024 [P] Test: a body one byte over the cap is refused with a tagged record naming the cap and what was received and nothing is parsed; a **body** arriving with no declared length is refused too; and every GET, which declares none, is untouched — `tests/contract/test_a_body_has_a_ceiling.py` (FR-024, SC-009). The third case is the one that keeps the guard from refusing the whole surface.
- [ ] T025 The `Content-Length` cap in `src/terezy/api/http/middleware.py`, refusing through the same path `NotOnLoopback` does (FR-024; plan Finding 6).
- [ ] T026 [P] Test: a body cannot raise, state or opt out of the candidate ceiling — a posted question over a root whose `max_candidates` is small refuses exactly as the saved read does — `tests/contract/test_candidate_ceiling_declaration.py` extended (FR-025).

## Phase 6 — the published contract

- [ ] T027 [P] Test: the set of non-GET operations in the served document is exactly `POST /api/answers`, and the two answer routes are both present — replacing `test_no_route_writes`'s verb assertion and `test_the_only_answer_route_names_a_declared_question`'s absence, whose `endswith("/answer")` filter would otherwise leave it green while missing the new route entirely — `tests/contract/test_the_route_table.py` (FR-010, FR-027, SC-010).
- [ ] T027a [P] `answers` joins the `fixed` set of `test_every_route_group_owns_a_distinct_first_segment`, which asserts every first segment is a declared category or a fixed endpoint and goes red on the new one — `tests/contract/test_the_route_table.py` (FR-010).
- [ ] T028 [P] [API] Test: `data/` is byte-identical before and after a POST, digested tree-wide — `tests/contract/test_the_route_table.py` (FR-006, FR-010, SC-012). This is the half that makes T027 a guard about writing rather than about a verb.
- [ ] T029 [P] [API] Test: the served document carries the request schema, every record reachable from it is distinctly tagged and every union discriminated, and the bytes are reproducible across hash seeds — `tests/contract/test_the_openapi_document.py` and `test_tags_and_unions.py` extended (FR-028, SC-011).
- [ ] T030 Bump `document.VERSION` in the same commit as the wire change (FR-028).
- [ ] T031 Flip the rows this feature closes in `docs/REQUIRED_TESTS.md`; set `029-question-in-request` to `done` in `specs/features.toml`, and close `http-question-from-request-parameters` there — it is marked *superseded by a planned feature* until this lands, because a deferral recorded as closed by work that does not exist is a false record on `main`.

## Phase 7 — gated by CL-1

- [ ] T032 [US2] Test and requirement for the shape an **undeclared stream** in a body comes back in. Under recommendation A this is a test over what Phases 2 and 4 already build; under B it is a second refusal shape at the boundary (spec CL-1).

---

## Dependencies

Phase 0 is red against nothing and blocks nothing. Phase 1 is independent of every HTTP task and
lands first on purpose — it is what makes the endpoint reproducible. Phase 2 precedes Phase 4, which
needs the attribution rule. Phase 3 precedes Phases 4, 5 and 6. Phase 7 waits on the owner.

**MVP**: Phases 0–3. At that point a whole question is answered from a body, reproducibly, and every
refusal still arrives — only its attribution and its cap are unfinished.
