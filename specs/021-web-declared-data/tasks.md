# Tasks: The declared data, on a screen that can refuse

**Feature**: `021-web-declared-data` | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

**Implementation may not start until `020-http-api` is `done` on `main`.** The order below exists
because of that: Phases 1–7 need no OpenAPI document and no running server, and Phases 8–10 are
everything that does. What should be waiting on the day 020 lands is a component library with a
green test suite.

Tests are **not optional**. Principle V is NON-NEGOTIABLE, and every component task below is
preceded by a test that fails before the component exists.

## Markers used here

| Marker | Meaning |
|---|---|
| **[P]** | parallelisable — a different file, no dependency on an incomplete task |
| **[US1]**…**[US4]** | the user story the task serves |
| **[020]** | needs the real OpenAPI document or a running API. Nothing before Phase 8 carries it |
| **[OB-n]** | blocked on an obligation 020 does not yet promise, or one whose reading is unsettled ([research D1](./research.md)). **Raise before starting the phase, not when the task is reached** |
| **[base path]** | blocked on 020 and 021 agreeing where the API is mounted ([research D3a](./research.md)) |


**No task is conditional on an open question.** All three of the spec's clarifications are answered
(`specs/decisions/2026-09-03-clarify-021.toml`, [research D11](./research.md)): English only, the
owner's own declarations shown and labelled as his statements, and the display-currency selector
**moot** because the switch is deferred. Where an answer is what makes a task possible or
unnecessary, the task says so.

---

## Phase 1: Setup — the tree and the toolchain

No API. Everything here is green on an empty component tree.

- [ ] T001 Scaffold `web/` with pnpm and Vite (React + TypeScript), writing `web/package.json`, `web/pnpm-lock.yaml`, `web/tsconfig.json`, `web/vite.config.ts` and `web/index.html`. `strict` on in `tsconfig.json`; the dev server proxies `/api` to `127.0.0.1:8000` (FR-033, and 020 FR-032 fixes the port). Pin every dependency the lockfile names and assert no version anywhere else — [contracts/dependencies.md](./contracts/dependencies.md) is the package list.
- [ ] T002 [P] Add Tailwind and its Vite plugin to `web/`, and the shadcn/ui configuration in `web/components.json`, taking the **copied-in** arrangement: components land as owned code in `web/src/components/ui/` and reviewed in git, and nothing named `shadcn` appears in `dependencies` ([research D10](./research.md), risk R6 on the config shape).
- [ ] T003 [P] Vendor the fonts into `web/public/fonts/` and reference them from the app's own origin (FR-035). A `fonts.googleapis.com` link is the failure T012's check is written to catch, so land the fonts before the check.
- [ ] T004 [P] Configure Vitest + React Testing Library + jsdom in `web/vitest.config.ts` and `web/tests/setup.ts`, and Playwright in `web/e2e/playwright.config.ts` pointing at a loopback base URL supplied by the environment.
- [ ] T005 [P] Configure ESLint in `web/eslint.config.js` with the TypeScript ESLint packages, and record risk **R1** at the config site: the rule that forbids a `default` arm on a discriminated-union switch must be read off the installed version's documentation, never assumed by name.

**Checkpoint**: `pnpm -C web exec tsc --noEmit`, `pnpm -C web lint` and `pnpm -C web test` all run and are green on an empty tree. Commit.

---

## Phase 2: Foundational — the mechanisms every story rests on

These are FR-004, FR-021a and FR-020 in their mechanical form. Each lands before anything that
depends on it, and each lands with the test that proves it is wired rather than merely present.

- [ ] T006 Write `web/src/lib/exhaustive.ts` — `assertNever(x: never): never` — with `web/tests/unit/exhaustive.test.ts` asserting that a switch missing a member fails to typecheck (a `// @ts-expect-error` at the call site, which goes red when the error stops occurring).
- [ ] T007 Add the ESLint rule forbidding a `default` arm on a discriminated-union switch (risk **R1**), with `web/tests/unit/lint-rules.test.ts` asserting the configuration contains it — because a rule that is configured off is FR-004 switched off everywhere at once ([research D4](./research.md)).
- [ ] T008 Write the failing test for the one clock read in `web/tests/unit/clock.test.ts`: a lint run over a fixture module **inside the rule's own scope** — `web/src/__fixtures__/second-clock.ts`, which is where it has to be, since a fixture outside `web/src` is outside the rule and the test would then be red for a reason that has nothing to do with the rule — containing a second `new Date()`, fails. Then write `web/src/clock.ts` and the `no-restricted-syntax` rule that fails any `new Date()` or `Date.now()` in `web/src` outside it, listing that module as the sole exception with its reason (FR-021, FR-021a).
- [ ] T009 Write the failing tests for search-parameter validation in `web/tests/unit/search-params.test.ts` — an invalid `as_of` and an invalid window each produce an error **naming the parameter**, and neither substitutes a default (FR-020, FR-027). Then write `web/src/search/params.ts`. `as_of` is the only global parameter; the window belongs to the two series routes ([research D0](./research.md)).
- [ ] T010 Write `web/src/routes/` with the five routes of the owner's routing map — `/`, `/data/:category`, `/data/:category/:id`, `/series/official-rate`, `/series/cpi` — wiring T009's validators per route, and the FR-021 redirect that writes `as_of` from T008's clock read and renders nothing until it is there. Risk **R4**: read the router's exact API for per-route validation and a pre-render redirect off the installed version.
- [ ] T011 [P] Write `web/tests/msw/handlers.ts` and hand-written fixtures shaped like the spec's *Key Entities*. **These are the one place a hand-written shape is permitted** — a fixture is a component's input, and FR-005 governs response types. T045 replaces them with types generated from the real document, and the note saying so lives here.

**Checkpoint**: the router validates, redirects once, and reads one clock; a missing union member is a compile error. Commit.

---

## Phase 3: The gates — every check that can exist before the API does

The spec's seven-job table is the requirement; [plan.md](./plan.md) has the wiring. **Four** of the
seven are buildable now: types generate has nothing to typecheck until there is a client API layer, and the
other two need a browser or an image.

- [ ] T012 Write `web/tools/check-bundle-urls.mjs` and `web/tools/bundle-url-allowlist.txt`, failing on any absolute URL in a build output not listed with a one-line reason (FR-036). Land it with a test that a fixture bundle carrying an unlisted URL **fails**, because a checker that passes on everything is green for the wrong reason.
- [ ] T013 [P] Write `web/tools/category-scan-exceptions.txt` — the checked-in exception list FR-015 requires, each entry a path with a one-line reason, expected to hold the two series route modules and the routing map. The scan itself is T054: it needs the running API's index.
- [ ] T014 Add **four** jobs to `.github/workflows/ci.yml` — **Typecheck**, **Lint**, **Unit** and **Bundle URLs** — each **unconditional**, not filtered on a `web/` path, and each green on the tree as it stands. **Types generate is deliberately not here**: there is nothing to typecheck against the generated types until T043 and T045, so adding it now would make it a blocking gate that is red, and Phases 3 to 7 each end in a commit that `/commit` refuses to make while a gate is red. It is added by T044, in the phase that gives it an input.

**Checkpoint**: four jobs exist and each is green on the tree as it stands. Commit.

---

## Phase 4: User Story 2 — a refusal arrives, and the screen says what it is (P1)

**Ordered first among the stories** because every other screen is built out of these three
components, and because `docs/DIRECTION.md` names flattening a refusal into a blank cell as the
failure this project exists to prevent.

**Independent test**: hand a fixture refusal to the component and read its reason off the rendered
output; hand it one with no reason and read the tag and the member's own fields.

- [ ] T015 [P] [US2] Write `web/tests/unit/figure-slot.test.tsx` against a component that does not exist: each of FR-007's three states renders, and the `refused` state renders **none** of FR-008's five placeholders — no blank, no `0`, no `—`, no `n/a`, no empty series.
- [ ] T016 [US2] Write `web/src/components/figure/FigureSlot.tsx` (FR-007, FR-008).
- [ ] T017 [P] [US2] Write `web/tests/unit/refusal.test.tsx`: a refusal **with** a reason renders it verbatim; a refusal **without** one renders its tag and its own fields, and neither path renders a placeholder. Under 020's clarification 3 `reason` is `string | undefined` on nine members, so the component must narrow on the tag first ([research D4](./research.md)).
- [ ] T018 [US2] Write `web/src/components/figure/Refusal.tsx`, switching on the tag with `assertNever` in the final arm and no `default` (FR-004, FR-007).
- [ ] T019 [P] [US2] Write `web/tests/unit/mark.test.tsx`: the assertion **strips every style declaration first**, then reads the mark — the reading `tests/contract/test_diagram_marks.py` already applies to diagrams, carried onto a rendered page (FR-009, E5's reinforcement).
- [ ] T020 [US2] Write `web/src/components/figure/Mark.tsx`, switching exhaustively over the mark vocabulary with `assertNever` and no `default`. In this phase that vocabulary comes from T011's fixtures, because `schema.d.ts` does not exist yet; **FR-010's mechanical form arrives with T045**, which re-points the switch at the generated types so a mark the API adds then fails the build rather than rendering as nothing. Writing the switch now is what makes that a type change rather than a rewrite.
- [ ] T021 [P] [US2] Write `web/tests/unit/api-error-state.test.tsx`: a transport failure and a non-2xx response are each a **named** state, and neither presents as an empty list, an empty chart or an unresolved loading state (FR-006). Then write `web/src/components/shell/ApiErrorState.tsx`. Risk **R3**: confirm whether a 020 typed refusal arrives in `openapi-fetch`'s `data` or its `error` before wiring this — getting it backwards renders a refusal as a transport failure, which is FR-006 and FR-007 both wrong and both green.

**Checkpoint**: a refusal renders as its reason and never as an absence. Commit.

---

## Phase 5: User Story 1 — he can see what the tool rests on (P1)

**This is the feature.** Everything else is a refinement of this screen.

**Independent test**: reach a record card and read a citation off it that matches the file on disk
(the API half of that is T040).

- [ ] T022 [P] [US1] **[OB-4]** Write `web/tests/unit/provenance.test.tsx`: an empty `verified_on` renders as the unverified mark and never as an empty field (FR-017); *unverified* and *stale* render as different claims and neither implies the other (FR-012) — the unverified half is a boolean 020 declares, and **the staleness half has no wire shape in 020's draft** ([research D1](./research.md), OB-4), so raise it with the rest; `is_unverified` is **read from the response, never recomputed** — 020 FR-018 says why. Then write `web/src/components/figure/Provenance.tsx`.
- [ ] T023 [P] [US1] Write `web/src/lib/provenance.ts` — the runtime **guards** that narrow a response value to the provenance shape, with `web/tests/unit/provenance-guards.test.ts`. A guard tests and narrows; a cast asserts. FR-005 forbids the second, and the two compile to the same thing, which is why the module carries the distinction as its reason for existing.
- [ ] T024 [P] [US1] Write `web/tests/unit/field-row.test.tsx` and `web/src/components/record/FieldRow.tsx` — label, value, type, and provenance where the value is observed (FR-016, FR-017).
- [ ] T025 [US1] **[OB-2]** Write `web/tests/unit/record-card.test.tsx`: **every** field the API returns renders, in the order returned; a field the component has no special rendering for renders its **raw value** rather than being dropped (US1 scenario 4); a card whose every field is unverified marks **each figure** and does not replace them with a banner (FR-011, FR-016). Then write `web/src/components/record/RecordCard.tsx`. **Raise OB-2 with 020 before starting this task** — [research D2](./research.md) records the fallback and its cost, and the fallback is a scope cut, not a workaround.
- [ ] T026 [P] [US1] **[OB-3]** Write `web/tests/unit/declaring-path.test.tsx` and `web/src/components/record/DeclaringPath.tsx` — the path of the file that declares the record, as text (FR-018).
- [ ] T027 [P] [US1] Write `web/tests/unit/synthetic-flag.test.tsx` and `web/src/components/record/SyntheticFlag.tsx` — rendered on the record, never inferable only from a directory name (FR-019).
- [ ] T028 [P] [US1] **[OB-6]** Write `web/tests/unit/citation-exemption.test.tsx` and `web/src/components/figure/CitationExemption.tsx` — an exempt directory renders the exemption **with the API's reason**, never an empty citation block (FR-013). Under Q3's answer this is also what labels a per-owner record as the owner's **statement** rather than as an observation, and it is the mechanism rather than a caption: the reason the exemption carries *is* "this directory holds the owner's own statements".
- [ ] T029 [P] [US1] Write `web/tests/unit/long-value.test.tsx` and `web/src/components/record/LongValue.tsx` — a value that is itself a long, multi-sentence citation string is shown **in full**, not elided to a fixed length with no way to see the rest (*Edge Cases*).
- [ ] T030 [P] [US1] Write `web/tests/unit/category-index.test.tsx` and `web/src/components/category/` — `CategoryIndex`, `CategoryCard`, `RecordList`, and `EmptyCategory` where an empty list and an absent category **render differently** (FR-014, *Edge Cases*, `B10` on a screen). A **singleton** category renders whether its document resolved and never a count — `0` for a resolved singleton is that same `B10` collapse, and seven of the twenty-five categories are singletons, so it is the ordinary case. No category id, label or branch appears in any of them (FR-015). Labels are the API's own field names, untranslated (Q1: English only), so no key file exists to drift.
- [ ] T031 [P] [US1] Write `web/src/components/shell/AppShell.tsx` and `SkipLink.tsx` — keyboard reach, a visible focus indicator, no focus trap, and a skip link to main content on every route (FR-038). The a11y assertion is T053; this is the markup it will run over.
- [ ] T032 [US1] Wire the three `/data/` routes to TanStack Query in `web/src/api/queries.ts`, one place a request is described (spec's decision table, taken against `useEffect` + `fetch`). Render the **resolved scenario** the response names, including when that is none — 020 FR-007b, and the reason the client sends no scenario parameter ([contracts/api-obligations.md](./contracts/api-obligations.md)).

**Checkpoint**: a record card renders every field of a fixture with its citation and its mark. Commit.

---

## Phase 6: User Story 4 — changing what the figure means changes only what it should (P1)

The display half of this story is deferred ([research D0](./research.md)); what remains is `as_of`,
which was always the harder half.

**Independent test**: two loads of one record card differing only in `as_of`, compared field by field.

- [ ] T033 [P] [US4] Write `web/tests/unit/as-of-control.test.tsx` and `web/src/components/shell/AsOfControl.tsx` — it displays `as_of` and edits the URL, reads no clock, and changing it **re-queries** rather than recomputing anything held (FR-022).
- [ ] T034 [P] [US4] Write `web/tests/unit/parameter-error.test.tsx` and `web/src/components/shell/ParameterError.tsx` — an `as_of` the router cannot validate is a **visible error naming the parameter**, with no default silently substituted (FR-020, US4 scenario 2).
- [ ] T035 [P] [US4] Write `web/tests/unit/theme.test.tsx` and `web/src/components/shell/ThemeToggle.tsx` — the theme follows the OS setting and is switchable, and a rendered figure, mark and ordering are **identical** across the two themes (FR-042).
- [ ] T036 [US4] Write `web/tests/unit/as-of-staleness.test.tsx` over MSW fixtures — SC-006 as a **biconditional**: a move across a threshold changes that source's staleness state, and a move crossing none changes **no** staleness state (FR-023). The one-directional reading is satisfied by a screen that re-renders on every date and says nothing true, which is why the test asserts both halves. A figure the API returned **identically twice** renders identically twice; a figure the API resolved differently changes with it, and the test asserts neither the suppression nor the production of that (FR-023a).

**Checkpoint**: `as_of` changes staleness and nothing else. Commit.

---

## Phase 7: User Story 3 — the two series, drawn honestly (P2)

**Independent test**: hand the chart a fixture series with a gap and count the drawn segments.

- [ ] T037 [P] [US3] Write `web/tests/unit/series-chart.test.tsx` against a component that does not exist — four properties, each a way a chart lies: a **gap** is a break with its own label and never a straight line between the two points (FR-028); the axis states the API's declared identity and what the values are **in**, and is never bare and never inferred (FR-030); a **one-observation** series is exactly one plotted point and **zero** line segments (FR-031, SC-008); a **retrieval** is refused rather than charted (FR-031a). The last two are unit-only **by design** — neither shape is reachable from either routed series, and an acceptance scenario no run can execute is a green box over an unasserted claim.
- [ ] T038 [US3] Write `web/src/components/series/SeriesChart.tsx` over Recharts (FR-028, FR-030, FR-031, FR-031a).
- [ ] T039 [P] [US3] Write `web/tests/unit/series-table.test.tsx` and `web/src/components/series/SeriesTable.tsx` — the same rows, keyboard-reachable, each carrying its point's mark and any per-point refusal (FR-032, FR-041). A chart is an approximation of a table here, not the other way round.
- [ ] T040 [US3] **[OB-7]** Write `web/tests/unit/coverage-refusal.test.tsx` and `web/src/components/series/CoverageRefusal.tsx` — a window reaching outside coverage renders the refusal **in place of the missing part**, with the in-coverage observations still plotted, never in place of the whole chart (FR-029, US3 scenario 4). **Settle OB-7 with 020 before this task**: 020 FR-046 requires a window past coverage to *refuse by name* and forbids returning a truncated result **silently**, which leaves two readings — the whole request refuses, or the in-coverage rows come back beside the named refusal. Only the second makes this component and SC-007 implementable, and the first would leave no option but the client trimming the window, which FR-001 and FR-027 forbid ([research D1](./research.md)).
- [ ] T041 [US3] Wire the two series routes with the FR-027a redirect: on a route loaded with no window, fetch the series' API-stated coverage from the list read, redirect with it written into the URL, and render from there. The client chooses no window and falls back to no "recent" and no fixed span. Carry [research D8](./research.md)'s sizing note at the site and act on none of it: if the coverage is too large to render, the fix is 020 stating a smaller default, never the client picking one.
- [ ] T042 [P] Write `web/tests/unit/sc-002-enumeration.test.tsx` — SC-002's enumerating test: it walks the figure-bearing components marked in [contracts/components.md](./contracts/components.md) and asserts each has a `refused` and a `marked` state. A component added without one fails here, which is the whole point of enumerating rather than reviewing. **Last of the story phases, not first**: four components carry the mark, and three of them — `FieldRow`, `SeriesChart`, `SeriesTable` — are built in Phases 5 and 7, so placed earlier this test would be red at every checkpoint before the last one.

**Checkpoint**: a gap is a break, a one-point series is a point, and the axis is never bare. Commit.

---

## Phase 8: The API-bound work — the real document and the real server

**Everything from here needs `020-http-api` `done` on `main`.**

- [ ] T043 **[020]** Add a `gen:types` script to `web/package.json` that runs `uv run python scripts/generate_openapi.py` and pipes the document into `openapi-typescript`, writing `web/src/api/schema.d.ts`; **gitignore the output** and make every script that needs it (`build`, `test`, the typecheck) depend on it (FR-003, owner decision 2026-09-05 — 020 stores no document to read). **Settle what the image does with this**: generation now needs `uv`, a Python interpreter and the `api` extra, which the previous design's checked-in JSON did not, and FR-049's single production image builds the client in a stage that has none of them. Verify risk **R2** at this task and nowhere later: each `oneOf` member must carry its tag as a **literal** type, not as `string`. If it does not, FR-004 has no mechanical form and the fix belongs in 020's document — stop and raise it.
- [ ] T044 **[020]** Add the **Types generate** job to `.github/workflows/ci.yml`, immediately after T043 and T045 give it something to typecheck: run `pnpm -C web gen:types`, then `tsc --noEmit` (FR-003, SC-013). **Unconditional**, not filtered on a `web/` path — the job exists to turn red when a *Python* change moves the OpenAPI document, and a path filter would disable it on the only change it was built for.
- [ ] T045 **[020]** **[base path]** Write `web/src/api/client.ts` over `openapi-fetch` — same origin, always (FR-035). **Settle the base path with 020 first** ([research D3a](./research.md)): FR-033 puts requests under `/api` and 020's document is root-relative, so in production — where there is no proxy — the client would ask for `/api/instruments` and get the SPA fallback's `200 text/html` handed to a JSON parser, which FR-006 would then report as a transport failure against a healthy API. Land a test for that shape whichever way it resolves: a path the API does not serve must not present as a parse error. Then, with the prefix agreed, and re-type `web/src/api/queries.ts`, `web/tests/msw/handlers.ts` and every component that switches on a generated vocabulary onto the generated types, deleting T011's hand-written fixtures. This is where FR-010 and FR-004 become mechanical for `Mark` and `Refusal` rather than fixture-shaped. FR-044: a fixture that has drifted from the contract must now **fail to compile**, not pass.
- [ ] T046 **[020]** Write `web/tests/unit/no-hand-written-types.test.ts` — a scan of `web/src` for a hand-written response type and for a cast or assertion over one (FR-005). A cast is FR-004 switched off at one site, so the scan is what stops it being added quietly.
- [ ] T047 **[020]** Write SC-003's demonstration in `web/tests/unit/union-widening.test.ts`: add a member to a **copy** of the generator's output, regenerate into a scratch directory, and assert `tsc` **fails**. This is the only one of FR-004's three mechanisms that cannot pass vacuously, and it is what proves T006 and T007 are actually wired.
- [ ] T048 **[020]** Write the Playwright suite in `web/e2e/` covering FR-046's minimum: opening a category and seeing its records; opening a record and reading its source, `retrieved_on`, `verified_on` and mark; and opening the official-rate chart. Assertions are about **states and relations** — present, marked, refused, unchanged, changed — and hard-code **no figure copied out of `data/`** (FR-047): files under `data/cpi/` and `data/official_rates/` are regenerated by fetch scripts and are supposed to move, and a number pinned in a browser test is a second copy of a golden in the one place nobody would look for one.
- [ ] T049 **[020]** Add the offline guard to `web/e2e/playwright.config.ts`: a context route handler that **aborts** every request whose URL is not the loopback base URL, installed for the whole suite (FR-045). A page that tried to reach a CDN then fails the suite instead of merely being slow. Risk **R5**: job-level network isolation is the belt; this handler is the load-bearing strap.
- [ ] T050 **[020]** Write `web/e2e/determinism.spec.ts` — FR-048: every URL from which a test asserts a figure, a mark or a refusal carries an explicit `as_of`, asserted by a scan over the suite's own URLs. The **one** exception is SC-008a's redirect test, which starts from a URL with a parameter missing and asserts **that the parameters arrive** and that each is the one that route takes, never a value — so the clock it reads decides nothing it looks at.
- [ ] T051 **[020]** Write `web/e2e/us1-citation.spec.ts` — US1's own independent test: reach a record card and read a citation, `retrieved_on` and `verified_on` off it that match the declaring file on disk; and US1 scenario 3, an exempt record rendering the exemption **with its reason** rather than an empty citation block. Scenario 3 is exercisable **because** Q3 resolved to showing the owner's own declarations: every citation-exempt directory that ships records is an owner-statement directory, so under the alternative there would have been no exempt record to run against.
- [ ] T052 **[020]** **[OB-7]** Write `web/e2e/us3-coverage.spec.ts` — US3 scenario 4 and SC-007: a window past coverage plots the in-coverage observations **and** shows the refusal with its reason, with **zero** plotted points past the last observation. Dropped only if 020 settles OB-7 on the reading where the whole request refuses.
- [ ] T053 **[020]** Write `web/e2e/a11y.spec.ts` with `@axe-core/playwright` over **every** rendered route in **both** themes, blocking on any AA violation (FR-043, SC-011). Both themes, because a check that visits only the default one passes on a broken one — and the theme is a runtime choice, so a token-level contrast check alone cannot see what a rendered page composes. It is a floor: FR-038 to FR-042 are the requirements, not this job's ruleset.
- [ ] T054 **[020]** Write `web/e2e/category-id-scan.spec.ts` — FR-015 and SC-012: fetch the running API's index, take its category ids, and scan `web/src` for each, failing on a hit outside T013's exception list. **Match string and template literals only, parsed rather than grepped**, and skip a literal that is a path segment of the file's own path or of an import specifier — thirteen of the ids are ordinary English words and `web/src/routes/` alone would make a substring grep fire on the id `routes` in files that hard-code nothing (FR-015 states the rule and why). Assert additionally that the exception list contains **no module under `/data/`**, which is the half that stops the exception becoming the branch.
- [ ] T055 **[020]** Add the **End-to-end** job to `.github/workflows/ci.yml`: `uv sync` plus Node, start the API on `127.0.0.1` **through terezy's own entry point** (020 FR-026b — never a bare server command, because the entry point is the one that refuses early), then run Playwright. T053 and T054 run inside this job because both need what it already has.

**Checkpoint**: the suite proves a mark survives from a TOML file to a pixel. Commit.

---

## Phase 9: Packaging — two files this feature does not own

**`docker-compose.yml` and the `Dockerfile` belong to feature 020** (its FR-032, and this spec's
*Assumptions*). Every task here is an edit to a file another feature owns and is taken by
agreement with it, not unilaterally. [research D3](./research.md) is the conversation to have
first: 020's FR-032a argues for a CORS allowance partly on a **false premise** about this feature's
development loop, and declines the static-serving responsibility FR-049 requires.

- [ ] T056 **[020]** Add the pnpm build stage whose only input is `web/`, and copy `web/dist` into the API image, which serves it with SPA fallback from the same origin (FR-033, FR-049). Install **frozen from the lockfile**, offline-capable, failing rather than resolving a version the lockfile does not name (FR-050).
- [ ] T057 **[020]** Add the `web` service to `docker-compose.yml` behind a **dev profile**, running the Vite dev server with hot reload and proxying `/api` to the `api` service over the compose network (FR-051). Bringing the stack up **without** the profile starts no `web` service, because in production there is nothing for it to do.
- [ ] T058 **[020]** Write the **static** compose check: every published host port, across **every service and every profile**, names `127.0.0.1` explicitly (FR-052). Static rather than runtime-only, because the smoke job brings up the production stack and the `web` service is dev-profile-only — so a runtime check alone never looks at the stanza most likely to carry a blank host. Docker's default host address is every interface, so a blank host is the constitution's authentication release gate bypassed by a missing field.
- [ ] T059 **[020]** Add the **Compose smoke** job to `.github/workflows/ci.yml`: T058's static check, then build and `up`, asserting one container (SC-014), one origin serving both, no Node toolchain and no `web/` source in the image (FR-053, SC-015), and T012's URL check re-run over the assets **extracted from the built image** (FR-054, SC-009).

**Checkpoint**: one container, one origin, loopback only. Commit.

---

## Phase 10: Landing

- [ ] T060 Flip `021-web-declared-data` to `done` in `specs/features.toml`, and add the `[[future]]` entry `web-display-currency-switch` drafted in the spec's Appendix — so the deferral is tracked in the graph rather than only in the spec's *Deferred by owner decision* section.
- [ ] T061 Record **F2** and **E5** in `docs/REQUIRED_TESTS.md` under *Rows a feature reinforced without closing*, flipping **no** box. This feature closes no row and adds none: no lettered behaviour names a browsing surface, and stretching one to fit would be the inverse of what that file is for. Under the display deferral, F2's reason is simply that there is no switch.
- [ ] T062 Run `uv run pytest --cov`, `uv run mypy`, `uv run lint-imports`, `uv run python scripts/check_provenance.py`, `uv run python scripts/check_prose_budget.py` and `uv run python scripts/check_enumerations.py` — confirming the two prose scripts stay green on a tree that has grown a `web/` directory rather than assuming they will. Neither is extended to `web/`, and [research D12](./research.md) is why.
- [ ] T063 `/condense` over the branch diff, then `/code-review` until clean. Both are blocking, and the review must cover the diff that is **actually merged** — a review is spent the moment the branch changes after it, including by `main` being merged in.

---

## Dependencies

```
Phase 1 (setup)
  └─> Phase 2 (exhaustiveness, clock, router)      ─┐
        ├─> Phase 3 (the four API-independent jobs) │  all API-independent
        └─> Phase 4 (US2: refusal, mark) ───────────┤
              ├─> Phase 5 (US1: record, category)   │
              ├─> Phase 6 (US4: as_of)              │
              └─> Phase 7 (US3: series, then SC-002)─┘
                    └─> Phase 8 (020: generated types, Playwright)
                          └─> Phase 9 (packaging — 020's two files)
                                └─> Phase 10 (landing)
```

**Phase 4 before Phase 5** is the one non-obvious edge: the record card is built out of
`FigureSlot`, `Mark` and `Refusal`, so US2's P1 primitives precede US1's P1 screen even though US1
is the feature. Phases 5, 6 and 7 are otherwise independent of each other and may run in parallel
once Phase 4 is green — with the exception of **T042**, SC-002's enumeration, which asserts over
components Phases 5 and 7 both contribute to and is therefore last.

**Four tasks are blocked on an obligation rather than on a phase** — T022 (OB-4), T025 (OB-2),
T026 (OB-3), T028 (OB-6) — two on an ambiguity 020 must close, T040 and T052 (OB-7), and one on the
base path, T045 (D3a). Raise all **seven** before the phase that contains them, not when the task is
reached: each is a paragraph in 020 or a scope cut here, and both are cheaper before the component
exists.

## The split, and what it buys

| | Tasks | |
|---|---|---|
| **API-independent** | T001–T042 | **42** — the whole component library, the router, four of the seven CI jobs, and every unit assertion |
| **API-bound** | T043–T063 | **21** — the generated types, the types-generate gate, the Playwright suite, packaging, and landing |

The point of the ratio is the block: `021` cannot start until `020` is `done`, and 42 of 63 tasks
do not care. What waits on 020 is a typed client and a browser, not a design.

## MVP

**Phases 1, 2, 4 and 5** — the setup, the mechanisms, the refusal-and-mark primitives, and the
record card. That is US1 and US2, both P1, and it is the smallest thing that answers the question
the feature was built for: *what does the tool rest on, and what does it refuse to tell me?*
