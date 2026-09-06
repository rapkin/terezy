# Tasks: The answer, on the home page, in one visual language

**Feature**: `026-answer-screen` | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

**Implementation may not start until `019-decision-layer` and `021-web-declared-data` are `done` on
`main`** — both are, 2026-09-06 — **and until `fix/undeployed-remainder` is on `main`**, which is what
makes `reaches` the whole figure T023 renders. The order below is the plan's: Phases 1–3 need no
response body and no running server, so what is waiting when Phase 4 begins is a tested component
library.

Tests are **not optional**. Principle V is NON-NEGOTIABLE; every component task is preceded by the
test that fails before it exists.

| Marker | Meaning |
|---|---|
| **[P]** | parallelisable — a different file, no dependency on an incomplete task |
| **[US1]**…**[US4]** | the user story it serves |
| **[API]** | needs a response body or a running API |

---

## Phase 1 — the language, with no API in it

- [ ] T001 [P] Test: every member of the **instrument** vocabulary the document declares today — the bond classes and the fund read's tag (FR-006) — has a hue, an icon and a word — `web/tests/unit/kinds.test.ts`. The venue half is T046a, because its vocabulary does not exist until Phase 5.
- [ ] T002 Add the kind tokens to `web/src/styles.css`: one hue per kind, ink `oklch(40% 0.11 h)` / tint `oklch(94% 0.03 h)`, each value once in `light-dark()`, cash achromatic (FR-001). The five venue hues land with Phase 5.
- [ ] T003 `web/src/design/kinds.ts` — the instrument kind → hue map as a mapped type over the vocabularies FR-006 names, so a member added leaves it one key short and the build red (FR-004).
- [ ] T004 [P] Test: a rendered tile's kind is readable after every style declaration is stripped — `web/tests/unit/kind-tile.test.tsx` (FR-002).
- [ ] T005 `web/src/design/icons/` — one 24-grid outline component per kind at stroke 1.75, and `KindTile` composing icon + text + tint (FR-002).
- [ ] T006 [P] Test: the `assume` tone renders its own text and is not a restyled `warn` — `web/tests/unit/badge-tones.test.tsx` (FR-003).
- [ ] T007 Extend `web/src/components/ui/badge.tsx` with the `assume` tone over new violet tokens beside 021's `--warn-*` and `--refuse-*` (FR-003).
- [ ] T008 [P] Test: money to the kopeck with thin-space grouping, percent to two decimals, `4 Oct 2026` from an ISO date, and a currency mismatch refused — `web/tests/unit/format.test.ts` (FR-026).
- [ ] T009 `web/src/design/format.ts` — the **one** formatting module, precision stated once and imported (FR-026).

## Phase 2 — pure functions over served shapes

- [ ] T010 [P] Test: one case per row of plan Finding 2's table — the two members it reaches and the raw-tag fallback — **including the sold-early member whose `per_member` list is empty** — `web/tests/unit/separating.test.ts` (FR-019). [US2]
- [ ] T011 `web/src/answer/separating.ts` — `sold_early` present or absent → a closed two-member badge vocabulary plus the raw-tag fallback. No `span.end` comparison and no match over `rests_on` text (FR-019). [US2]
- [ ] T012 [P] Test: the no-candidate fixtures FR-022 measures collapse to one group, and every id it counted is reachable — `web/tests/unit/grouping.test.ts`. [US3]
- [ ] T013 `web/src/answer/grouping.ts` — group by typed discriminants, never by reason text (FR-022). [US3]
- [ ] T014 [P] Test: a `non_dominated` key with no ranked match returns the named state, not `undefined` — `web/tests/unit/join.test.ts` (FR-009, FR-010). [US1]
- [ ] T015 `web/src/answer/join.ts` and `web/src/answer/missing.ts` — the key-equality join, and the named state for an absent field (FR-009, FR-010).
- [ ] T016 [P] Test: the shared set is identical for every member of a section and appears on no card — `web/tests/unit/assumptions.test.ts` (FR-020). [US3]
- [ ] T017 `web/src/answer/assumptions.ts` — shared versus per-member by set difference over served strings (FR-020). [US3]
- [ ] T018 [P] Test: mixed span lengths yield `true`, equal ones `false`, and the return type carries no figure — `web/tests/unit/comparability.test.ts` (FR-014). [US1]
- [ ] T019 `web/src/answer/comparability.ts` — the banner's predicate (FR-014). [US1]

## Phase 3 — components, against fixtures

- [ ] T020 [P] Test: each of `FigureSlot`'s three states inside a card, each badge variant, each kind tile, and no raw float in the output — `web/tests/unit/candidate-card.test.tsx` (FR-015, FR-023). [US2]
- [ ] T021 `web/src/answer/components/CandidateCard.tsx` — FR-015's whole field order, the *indistinguishable from* line included, composing `FigureSlot`, `KindTile`, `Badge` and `format.ts`. [US2]
- [ ] T022 Test: *money back* is the served `reaches`, with nothing added to it and no deployed part composed from it — an expansion carrying the served remainder record, a remainder the record says did not come home rendering as a named state, and a `null` remainder rendering as *nothing left over* — `web/tests/unit/money-back.test.tsx` (FR-016, FR-017).
- [ ] T023 `web/src/answer/components/MoneyBack.tsx` — one figure from `reaches`, the served `UndeployedCash` record behind a disclosure (FR-016, FR-017).
- [ ] T024 [P] Test: shown for mixed spans, absent for equal ones, and no span range in its text — `web/tests/unit/comparability-banner.test.tsx` (FR-014). [US1]
- [ ] T025 `web/src/answer/components/ComparabilityBanner.tsx` — condition and consequence, no derived figure (FR-014). [US1]
- [ ] T026 [P] Test: two members leaning on one belief render one line; two distinct belief ids render two — `web/tests/unit/belief-line.test.tsx` (FR-024). [US3]
- [ ] T027 `web/src/answer/components/BeliefLine.tsx` and `SharedAssumptions.tsx` — once per screen per belief id, plus FR-018's statement that the rate is on the money invested (FR-018, FR-020, FR-024, FR-025). [US3]
- [ ] T028 [P] Test: a group renders its typed reason and expands to each member; never a count alone, never a blank — `web/tests/unit/refusal-group.test.tsx` (FR-023). [US3]
- [ ] T029 `web/src/answer/components/RefusalGroup.tsx` (FR-023). [US3]
- [ ] T030 [P] Test: the benchmark row is marked in text, a tie group of two renders as one group, and every row carries all five terms — `web/tests/unit/full-ranking.test.tsx` (FR-012). [US3]
- [ ] T031 `web/src/answer/components/FullRanking.tsx` (FR-012). [US3]
- [ ] T032 [P] Test: an undeclared subject renders as a refusal with its remedy, and a subject with no entry in the map fails the test — `web/tests/unit/undeclared-subject.test.tsx` (FR-021). [US3]
- [ ] T033 `web/src/answer/components/AnswerHeader.tsx` — the question as a template over typed fields, naming the benchmark instrument, undeclared subjects as refusals; no standing (FR-011, FR-021). [US1]
- [ ] T034 [P] Test: a **survey** refusal, a dominance refusal and a comparison with no benchmark each render their own reason and no card; every population the API sent has a count and each count matches its expanded members — `web/tests/unit/horizon-column.test.tsx` (FR-012). [US1]
- [ ] T035 `web/src/answer/components/HorizonColumn.tsx` — banner, every count the section reports, its `benchmark_standing`, its `standings` and `reserves`, cards, folded groups (FR-012). [US1]
- [ ] T036 [P] Test: the loading and failure states are each named and neither is a spinner or an empty column — `web/tests/unit/answer-states.test.tsx` (FR-013). [US4]
- [ ] T037 `web/src/answer/components/LoadingState.tsx` and `AnswerUnavailable.tsx` (FR-013).

## Phase 4 — the route [API]

- [ ] T038 `web/src/api/queries.ts` — `answerQuery(questionId, asOf)` and `instrumentClassQuery(id, asOf)`; no registry read on this page (FR-008).
- [ ] T039 `web/src/routes/overview.tsx` becomes the answer; the 021 browser moves to a secondary navigation entry with every path unchanged (FR-028). [US4]
- [ ] T040 Wire the kind tile to the instrument read — its tag, then `instrument_class` where the tag carries one — one read per distinct member id (FR-006). [US2]
- [ ] T041 [P] E2E: the three columns' members match the API's `non_dominated` by count and by id, per section — `web/e2e/answer-fronts.spec.ts` (SC-001). [US1]
- [ ] T042 [P] E2E: the belief text appears exactly once, and no unrounded float reaches the document — `web/e2e/answer-text.spec.ts` (SC-003, SC-004). [US3]
- [ ] T043 [P] E2E: the 26-row group is one line and one count, expanding to 26 ids — `web/e2e/answer-groups.spec.ts` (SC-006). [US3]
- [ ] T044 [P] E2E: the comparability banner is above the fold where spans differ — `web/e2e/comparability.spec.ts` (SC-007). [US1]
- [ ] T045 Extend `web/e2e/crawl.spec.ts` and the accessibility pass to `/` in both themes (SC-009, SC-011, FR-027). [US4]
- [ ] T045a [P] E2E: loading `/` issues no request to `/api/registry`, asserted by failing the run on one — `web/e2e/answer-requests.spec.ts` (SC-008). [US1]
- [ ] T045b [P] Test: no module under `web/src/answer/` or `web/src/design/` derives a kind from an id, a name or a path — a source scan beside the kind map, warranted because the typecheck cannot see a string built from `key.instrument_id` — `web/tests/unit/kind-provenance.test.ts` (SC-010, FR-005).

## Phase 5 — the venue `kind`

Last because nothing on this screen draws a venue, so it blocks no phase above.

- [ ] T046 Test: a venue declaring an unknown kind fails at load naming file and field — `tests/contract/test_venue_kind_declaration.py` (FR-007).
- [ ] T046a Test: every member of the venue kind vocabulary has a hue, an icon and a word — `web/tests/unit/kinds.test.ts`, extending T001 (FR-004).
- [ ] T047 Add the five-member closed vocabulary — `bank`, `exchange`, `broker`, `platform`, `payroll` — to `src/terezy/core/routes/venues.py`, the `kind` field to `VenueTable` and the `Venue` record, and the `_known` check to the loader (FR-007).
- [ ] T048 Declare each venue's kind in `data/venues.toml` (nine lines, the assignment in `specs/decisions/2026-09-06-clarify-026.toml`) and regenerate whatever golden the change moves, quoting the moved lines in the commit message (Principle V).

## Landing

- [ ] T049 Update `docs/REQUIRED_TESTS.md`: record the rows this feature reinforces, with the reason per row that no box moves. E11 is **not** among them — no tax waterfall is rendered — and F2 still waits on the display switch.
- [ ] T050 Flip 026's `status` in `specs/features.toml` to `done`. `cli-renders-raw-floats`'s note already records that 026 closes the web half.
