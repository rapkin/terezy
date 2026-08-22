---

description: "Task list for 003-route-coverage: the coverage report"
---

# Tasks: The coverage report

**Input**: Design documents from `specs/003-route-coverage/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: **Required, and first.** Constitution Principle V is non-negotiable for this
project: every financial behaviour lands with a worked example, a Hypothesis invariant or a
golden file, and *the test must fail before the implementation exists* — an `ImportError`
counts (`specs/README.md` §2).

**Organization**: grouped by user story, in the order plan.md's Phase 2 note fixes: **the
declaration and its refusals first, then the records, then the fold, then the properties.**

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelisable — different files, no dependency on an incomplete task
- **[Story]**: which user story the task serves (US1…US4)
- Every task names the exact file it touches

## Path conventions

Single Python library, src layout, layered `cli → api → data → core`. Paths are relative to
the worktree root `/Users/rapkin/dev/terezy/.claude/worktrees/003-route-coverage`.

---

## The three things that will go wrong if they are not held in mind

Repeated here because every task below is downstream of them.

1. **No cost figure, no float.** Nothing reachable from `CoverageReport` may be a `Money`, a
   `Provenance`, a `StalenessVerdict` or a bare `float`. Integers only. T027 enforces it with
   a recursive `dataclasses.fields` walk — that is how SC-004 and SC-008's *"across the whole
   output, not sampled"* is satisfied. **This feature imports no tolerance**; needing one
   means a number leaked.
2. **Never compose, infer or reverse a route** (FR-006). No chaining, no reading an inbound
   backwards, no following `partner_route` to find an exit (research.md D6). A two-hop way
   out is deficit 3. Composition is feature 004.
3. **The costing-agreement property is scoped** (research.md D11) to costing's
   *route-existence* refusals — no matching route, and `ExitCostUnknown`. `RouteUnusable`
   is feasibility-today and out of scope. A failure there is fixed in the generator, never by
   weakening the coverage rule.

---

## Phase 1: Setup

**Purpose**: record that implementation has started. No code.

- [X] T001 Flip `status = "spec"` → `status = "in-progress"` for `003-route-coverage` in `specs/features.toml` (goes in the **first** implementation commit; `done` is the landing commit's job, not this branch's)
- [X] T002 Confirm the baseline is green before touching anything: `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run python scripts/check_provenance.py && uv run pytest --cov` — record the test count and coverage % so the final report can state the delta

---

## Phase 2: Foundational — the one new declaration, and every record

**Purpose**: the report cannot be tested without a spendable list, and cannot be written
without the records. Blocking for every user story.

**⚠️ CRITICAL**: no user-story work begins until this phase is complete.

### Tests first

- [X] T003 [P] Write `tests/contract/test_spendable_declaration_loading.py` covering **every** refusal in `specs/003-route-coverage/contracts/spendable-schema.md`: unknown `venue`, venue that cannot hold the currency, currency that is not the base currency, duplicate `(venue, currency)`, empty `[[spendable]]` list, empty `data/spendable/` directory, extra key, blank `owner.id`, and an `owner.id` that does not match the streams it is resolved with. Assert `DeclarationError.file` and `.field_path` on every case, on the pattern of `tests/contract/test_route_declaration_loading.py` (mutate the shipped file's text; a needle that no longer matches fails the test rather than silently passing). Also assert the shipped `data/spendable/owner-001.toml` loads and resolves clean. Must fail with `ImportError` before T005–T009 exist.
- [X] T004 [P] In the same module, assert the provenance gate stays green **with the new file present and `SOURCED_DIRS` unmodified** (research.md D4): run `scripts/check_provenance.py`'s check over the repo data root in-process and assert no error, and assert `"spendable" not in check_provenance.SOURCED_DIRS`. Confirming rather than assuming is the point of the task.

### Implementation

- [X] T005 Create `src/terezy/core/results/coverage.py` with **every** frozen record of [data-model.md](./data-model.md): `SpendableEndpoint`, `Destination`, `RouteRelied`, the `SATISFIED_BY_ARRIVAL` and `ANY_SPENDABLE` sentinels (single-member `Enum`s, not `None` and not an empty tuple — FR-005 and FR-007 ⚙), `DeficitKind` with its three `Final` members, `MissingDeclaration`, `Deficit`, `Ready`, `NotReady`, `PairVerdict`, `BlockedPair`, `TodoEntry`, `Observation`, `OrphanExit`, `RegimeCoverage`, `AuditedDeclarations`, `CoverageReport`, `RegistryDimensionEmpty`, `ReservedRegimeId`, plus the `IMPLICIT_REGIME_ID` and `ENFORCEMENT` module constants (research.md D14, D15). `@dataclass(frozen=True, slots=True, kw_only=True)` throughout, no behaviour, docstring voice matching `core/results/ramp.py`. **No `Money`, `Provenance`, `StalenessVerdict` or `float` field anywhere.** Record in the module docstring why the records live here and not in `core/routes/coverage.py` as data-model.md's headings say: `routes/coverage.py` builds them, so defining them there would be an import cycle — they stay importable from both.
- [X] T006 Add `SpendableFile`, `OwnerTable` and `SpendableTable` to `src/terezy/data/declarations/schema.py` under a `003-route-coverage` banner comment matching the existing `002-ramp-cost` one. `STRICT` config, **zero field defaults**, currency and venue typed `str` and resolved by the loader (shape here, meaning there).
- [X] T007 Add `SPENDABLE_TABLE`, `OWNER_TABLE` and `spendable_from_file(path) -> tuple[str, tuple[SpendableEndpoint, ...]]` to `src/terezy/data/declarations/loader.py`. Owns the single-file refusals: blank `owner.id`, blank `venue`, unknown currency code, duplicate `(venue, currency)` **within** the file, empty `[[spendable]]` list (research.md D13). No citation is read and none is expected — say so in the docstring, on the `streams_from_file` precedent.
- [X] T008 Add `SPENDABLE_DIR`, `CoverageDeclarations`, `resolve_coverage(...)` and `coverage_from_data_root(root, *, base_currency)` to `src/terezy/data/declarations/resolver.py`. Owns the cross-file checks: the venue exists (`_check_venue`, which also gives can-hold for free), the currency **is** the base currency (FR-004), the owner id matches the resolved streams' owner, duplicates across files, and an empty `data/spendable/` directory (the reason `ramp_from_data_root` already gives). `CoverageDeclarations` is a record **beside** `RampDeclarations`, not more fields on it.
- [X] T009 Write `data/spendable/owner-001.toml` exactly as [contracts/spendable-schema.md](./contracts/spendable-schema.md) shapes it: `[owner] id`, one `[[spendable]]` entry for `monobank_uah` / `UAH`, and the header explaining why there are **no citation keys** and why `binance` is not listed despite holding UAH.
- [X] T010 Run T003 and T004 green, then the full gate set. **Checkpoint — commit** (`/commit`): the declaration and its refusals.

**Checkpoint**: the spendable list loads, every refusal is enforced at load, and the
provenance gate is green without `SOURCED_DIRS` growing.

---

## Phase 3: User Story 1 — Audit the whole registry at once (Priority: P1) 🎯 MVP

**Goal**: for every declared destination × stream × regime, a verdict — comparison-ready, or
not with exactly which of the three deficits.

**Independent Test**: a hand-declared registry (two streams, three destinations, a deliberate
mix of complete pairs and each kind of hole) checked against a coverage table enumerated by
hand and checked in beside the assertion.

> **Phase 3 and Phase 4 share one commit.** A report whose `todo` is an empty tuple while its
> verdicts carry deficits would be a confident wrong output, so this phase's checkpoint is
> internal: the commit comes at T023, after the to-do list is populated.

### Tests for User Story 1 (write first, watch them fail)

- [X] T011 [P] [US1] Write `tests/worked_examples/test_coverage_table.py` (marker `worked_example`) — **SC-001, SC-002, SC-012**. Build the registry in-process: two streams (UAH at one arrival venue, USD at another), three destinations with a deliberate mix, and the hand-enumerated coverage table checked in **beside the assertion** as a literal mapping of `(venue, currency, stream, regime) -> expected verdict and deficit kind`. Assert every pair in the declared universe (venue × holdable currency × stream) appears exactly once, that all three deficit kinds occur, that no bare undifferentiated "missing route" value exists anywhere, and that a destination equal to a stream's arrival venue+currency reports `SATISFIED_BY_ARRIVAL` and is ready iff its exit exists.
- [X] T012 [P] [US1] Write `tests/unit/test_coverage_empty.py` — **SC-013** and research.md D13/D14. Each of `venues`, `streams`, `routes`, `spendable` empty (and several at once) returns `RegistryDimensionEmpty` naming **every** empty dimension, not the first; a declared regime carrying `IMPLICIT_REGIME_ID` returns `ReservedRegimeId`; no input produces a report with no verdicts (defect B10).
- [X] T013 [P] [US1] Write `tests/unit/test_coverage_deficits.py` (first half) — **SC-002, SC-010, SC-011, SC-017**. Three crafted registries, one per deficit kind. A missing exit's `origin_venue` is the **destination** venue and its `origin_currency` the destination currency, and nothing in the report reproduces the inbound route's shape (SC-010). A destination whose only exit ends at a venue that itself has a spendable exit is `exit_not_spendable` — **the two-hop path is never composed** (SC-011, FR-006). An orphan exit is listed with `reaches_spendable`, appears in no deficit and blocks no count (SC-017).

### Implementation for User Story 1

- [X] T014 [US1] Create `src/terezy/core/routes/coverage.py` with the module docstring, the pure helpers `destinations(venues)` (venue × holdable currency, sorted by `(venue_id, currency.value)` — research.md D5) and `is_spendable(endpoint, spendable)`, and the `coverage(*, venues, streams, routes, regimes, spendable)` signature of [contracts/coverage-report.md](./contracts/coverage-report.md). Keyword-only, **no `on_date`, no `as_of`** — coverage is a claim about declarations (FR-022 ⚙). No `pathlib`, no clock, no costing call.
- [X] T015 [US1] Implement the empty-dimension and reserved-regime guards in `src/terezy/core/routes/coverage.py`: `RegistryDimensionEmpty` naming every empty dimension of `venues`/`streams`/`routes`/`spendable`, and `ReservedRegimeId` when a declared regime carries `IMPLICIT_REGIME_ID`. An empty `regimes` mapping is **not** a refusal — it is FR-015's implicit regime.
- [X] T016 [US1] Implement matching in `src/terezy/core/routes/coverage.py`, exactly as research.md D6 fixes it: an **inbound match** is `direction == "inbound"`, `origin == stream.arrives_at`, `destination == destination.venue_id`, `legs[0].from_ccy == stream.amount.currency`, `legs[-1].to_ccy == destination.currency`; an **exit from a destination** is `direction == "exit"`, `origin == destination.venue_id`, `legs[0].from_ccy == destination.currency`; a **spendable exit** ends at a `(venue, currency)` in the declared set. **`partner_route` is never read** — say so at the site, because reading it is one step from FR-006's forbidden reversal.
- [X] T017 [US1] Implement `satisfied by arrival` in `src/terezy/core/routes/coverage.py` (FR-005): a destination equal to the stream's arrival venue **and** arrival currency reports the `SATISFIED_BY_ARRIVAL` sentinel — explicitly distinct from an empty tuple of relied routes — and still requires the declared exit.
- [X] T018 [US1] Implement deficit classification in `src/terezy/core/routes/coverage.py` per research.md D7: at most one **inbound** deficit (`no_inbound`) and at most one **exit** deficit (`no_exit_declared` when nothing leaves the destination, `exit_not_spendable` when something leaves and none of it lands on the declared list), and **both may be present at once**. `exit_not_spendable` carries `observed_exits` — the exits that exist, with their statuses — so it cannot read like `no_exit_declared`. Every deficit carries its `MissingDeclaration` (T019).
- [X] T019 [US1] Implement `MissingDeclaration` construction in `src/terezy/core/routes/coverage.py` (FR-007, FR-008): for an inbound, origin is the stream's arrival venue and currency and the target is the `Destination`; for an exit, origin is the destination venue and currency and the target is the `ANY_SPENDABLE` sentinel with the declared spendable list as `candidates`, sorted. **No regime field** (research.md D8), **no interior hops**, and no field a provider, fee, premium, cap, latency or rate could live in.
- [X] T020 [US1] Implement `Ready` and `rests_on` in `src/terezy/core/routes/coverage.py` (research.md D10, FR-022, SC-015): `Ready` lists **every** matching inbound and **every** spendable exit with its `RouteStatus`, not the first; `rests_on` is `"open"` when the inbound side is satisfied (by arrival, or by at least one open inbound route) and at least one relied exit is open, `"closed_only"` when every relied route is closed, `"constrained"` otherwise. Document the arrival case explicitly — arrival is not a route and cannot be closed.
- [X] T021 [US1] Assemble the per-regime verdict tuple in `src/terezy/core/routes/coverage.py`: every `(destination × stream)` in the declared universe, exactly once, sorted by `(venue_id, currency.value, stream_id)`, with no pair absent (G1, FR-001).

**Checkpoint**: every verdict is produced and distinguished. Not yet committable — the to-do
list is still empty. Continue straight into Phase 4.

---

## Phase 4: User Story 2 — Know which observation to make next (Priority: P1)

**Goal**: the to-do list — each missing declaration with the count of `(destination × stream)`
pairs it blocks, ordered by that count, ties reported as ties, and each pair told whether the
declaration alone would unlock it.

**Independent Test**: a registry where one missing exit blocks two pairs and one missing
inbound blocks one; the to-do list orders the exit first with a count of 2, and writing
precisely the declaration the report names — and nothing else — flips the blocked pairs.

### Tests for User Story 2 (write first, watch them fail)

- [X] T022 [US2] Extend `tests/unit/test_coverage_deficits.py` with the to-do half — **SC-003, SC-005, SC-006**. SC-003 closes the loop **by doing it**: take a not-ready pair, add exactly the declaration the report named (for a missing exit, an exit to **any one** of the listed candidates), change nothing else, re-run `coverage`, assert the pair is ready and the to-do item is gone. SC-005: one missing exit blocking two pairs outranks a missing inbound blocking one, with `count == 2`; two declarations blocking equal counts appear as a group in `ties`. SC-006: a pair missing **both** halves appears in both entries' `blocked`, each with `alone_sufficient = False`. Also assert `TodoEntry.count == len(TodoEntry.blocked)` — a plain count, never a composite (required test B12).

### Implementation for User Story 2

- [X] T023 [US2] Implement the to-do fold in `src/terezy/core/routes/coverage.py` (FR-009, FR-010, FR-011): group each regime's deficits by `MissingDeclaration` **value equality** — which is what makes a missing exit one item however long the candidate list is (FR-007 ⚙) — build `BlockedPair` per blocked pair with `alone_sufficient` false whenever that pair carries more than one deficit, sort by `(-count, direction, origin_venue, origin_currency.value)` and record equal-count index groups of two or more in `ties`. State at the site that the sort key beyond the count is **presentation only** and `ties` is the claim (research.md D9, `Ranking.ties` precedent).
- [X] T024 [US2] Implement orphan exits in `src/terezy/core/routes/coverage.py` (FR-012, SC-017): an exit route in the regime whose origin `(venue, first leg's from_ccy)` no stream reaches — by an inbound match or by arrival — is listed with `reaches_spendable`, sorted by route id. It is **not** a deficit and blocks no count.
- [X] T025 [US2] Implement the cross-regime `to_observe` list in `src/terezy/core/routes/coverage.py` (FR-014, research.md D8): one `Observation` per distinct `MissingDeclaration` across the whole report, `blocked_by_regime` as `(regime_id, count)` pairs for **every** regime in the report sorted by regime id — never summed. Sort `to_observe` by declaration identity only, and say at the site that this list carries **no ordering claim**: FR-010's ordering is per regime, and an ordered cross-regime list would be the blend FR-013 forbids.
- [X] T026 [US2] Assemble `CoverageReport` in `src/terezy/core/routes/coverage.py`: `audited` (sorted id tuples and the spendable pairs — ids, never a `Path`, research.md D16), `regimes` sorted by id, `to_observe`, and `enforcement` from the module constant. Add the `blocked_count(entry)` helper of the contract.
- [X] T027 [US2] Write `tests/contract/test_coverage_no_figures.py` (marker `contract`) — **SC-004, SC-008**. A **recursive walk** over `dataclasses.fields` of the whole returned report, following tuples, mappings, sets and nested dataclasses, asserting no value and no annotated field type anywhere is a `Money`, `Provenance`, `StalenessVerdict` or bare `float`. Across the whole output, not sampled (research.md D12) — and assert the walk actually visited a non-trivial number of nodes, so a walk that silently visits nothing cannot pass.
- [X] T028 [US2] Run T011–T013, T022 and T027 green, then the full gate set. **Checkpoint — commit** (`/commit`): the verdicts and the to-do list.

**Checkpoint**: the report is honest end to end for declared regimes — verdicts, deficits, and
an ordered to-do list with ties reported.

---

## Phase 5: User Story 3 — See coverage per regime (Priority: P2)

**Goal**: every verdict, deficit and count stated per regime, with no blended verdict and no
summed cross-regime count anywhere; and, with no regime declared, one implicit regime that
says so.

**Independent Test**: a route named by one regime's route set and absent from the other yields
a pair ready in the first and not ready in the second, with the shared missing declaration
recognisable as one item carrying per-regime counts.

### Tests for User Story 3 (write first, watch them fail)

- [X] T029 [US3] Write `tests/unit/test_coverage_regimes.py` — **SC-007, SC-018**. A route in one regime's set and not the other's: ready in the first, not ready in the second, each stated under its own `RegimeCoverage`; **no blended verdict and no summed count exists anywhere in the output** (assert structurally, by walking `to_observe` and confirming every entry carries per-regime pairs and no total field exists). The shared missing declaration is **one value-equal record** with per-regime counts. Two regimes naming identical route sets still produce two blocks, not one. With `regimes = {}`, one block with `source == "implicit"`, `regime_id == IMPLICIT_REGIME_ID`, `route_ids` every declared route, and `audited.regime_ids` empty (SC-018).

### Implementation for User Story 3

- [X] T030 [US3] Implement regime selection in `src/terezy/core/routes/coverage.py` (FR-013, FR-015, research.md D14): one `RegimeCoverage` per declared regime with `source == "declared"` and its own route subset, or — with no regime declared — exactly one block with `source == "implicit"`, `regime_id == IMPLICIT_REGIME_ID` and every declared route. A regime naming a route nobody declared **raises**, on `regimes.routes_in_force`'s precedent: the loader validates that and can name the file, so reaching core with one means the check was bypassed.
- [X] T031 [US3] Confirm no cross-regime aggregation exists anywhere in `src/terezy/core/routes/coverage.py` — every count is computed inside one regime's fold, and `to_observe` only pairs counts with regime ids. Add the sentence to the module docstring so the next reader does not add one.
- [X] T032 [US3] Run T029 green, then the full gate set. **Checkpoint — commit** (`/commit`): coverage per regime, and the implicit regime.

**Checkpoint**: regimes are separate everywhere, and the no-regime case says what it did.

---

## Phase 6: User Story 4 — Grow the registry without touching the engine (Priority: P3)

**Goal**: a new venue, stream, route or spendable endpoint declared purely as data appears in
the next report — as coverage or as a named hole — with zero lines of source changed.

**Independent Test**: add a venue as data with no routes; the report gains destinations with
named no-inbound deficits and nothing in `src/` changed.

### Tests for User Story 4 (write first, watch them fail)

- [ ] T033 [US4] Write `tests/contract/test_coverage_data_only.py` (marker `contract`) — **SC-014, SC-019, SC-015**. Copy `data/` into a scratch root, add a venue declaring two currencies and no routes, resolve and report: two new destinations appear, each with a named `no_inbound` deficit per stream, **zero lines of source changed** (SC-014). Add a venue to `data/spendable/` in the scratch root and assert an exit ending in UAH there flips from `exit_not_spendable` to ready — a data change only (SC-019). Assert a ready verdict resting only on a `closed` route has `rests_on == "closed_only"`, one resting on an open route has `"open"`, and both are distinct from a hole (SC-015). Also assert, greppably, that no module under `src/terezy/core/routes/coverage.py` or `src/terezy/core/results/coverage.py` names a venue, route or stream id, on the pattern of `tests/contract/test_route_data_only.py`.

### Implementation for User Story 4

- [ ] T034 [US4] Fix whatever T033 exposes in `src/terezy/core/routes/coverage.py` or the data layer. **No new branch per venue, corridor or currency** — if a fix wants one, the design is wrong and the fix belongs in `data/` (Principle II). Expected to be a no-op if T014–T031 held the line; the task exists so the check is run rather than assumed.
- [ ] T035 [US4] Run T033 green, then the full gate set. **Checkpoint — commit** (`/commit`): data-only extensibility verified.

**Checkpoint**: growing the registry is a data change, proved by doing it.

---

## Phase 7: The properties, the documentation, and the gates

**Purpose**: the two Hypothesis properties that pin the report against costing and against
itself, plus the documentation that is part of the feature.

- [ ] T036 [P] Add a coverage-scoped generator to `tests/invariants/route_graphs.py`: a registry (venues, streams, routes, spendable) whose legs declare **no minimum, no maximum, no monthly cap and no availability window**, whose routes are `open`, and which is **partner-closed** — an exit exists from a destination if and only if the inbound route declares it as `partner_route`, and that exit ends in the base currency at a declared spendable venue. Every one of those is a scoping decision required by research.md D11, and each is documented at its definition with the refusal it keeps out of scope.
- [ ] T037 Write `tests/invariants/test_coverage_costing_agreement.py` (marker `invariant`) — **SC-009, FR-018**. Over generated registries: every pair marked `Ready` is one `cost_one` produces a `RampCost` whose `round_trip` is a `RoundTripCost` for, over at least one relied inbound route; every pair marked `NotReady` is one for which no `FundingPath` over a declared route matches at all, or every one that does yields `ExitCostUnknown`. **State the scope at the assertion site**: route-existence refusals only; `RouteUnusable` — below a minimum, above a cap, outside a window, a closed route — is feasibility-today and deliberately excluded (research.md D11). Add the sentence that a failure here is fixed in T036's generator, never by weakening the coverage rule, and the forward note that feature 004's composition is reconciled by a distinct annotation and never by changing what `Ready` means.
- [ ] T038 [P] Write `tests/invariants/test_coverage_totality.py` (marker `invariant`) — **FR-001, G1**. Over generated registries: every `(destination × stream)` of the declared universe appears **exactly once** in every regime's `verdicts`, no pair is absent and none appears twice, and the destination universe is venue × holdable currency rather than anything derived from the routes.
- [ ] T039 Extend `tests/contract/test_coverage_no_figures.py` with **SC-016 and SC-020**: the same declarations produce an **equal** report on two independent runs, field for field and tuple order included, and `audited` names the exact declaration set (SC-016); feature 002's `rank` over one registry produces an identical result with and without `coverage` having been called, and `CoverageReport.enforcement` states in the output itself that the verdicts are advisory, that ranking is unaffected, and that enforcement is a recorded deferral (SC-020, FR-019, research.md D15).
- [ ] T040 [P] Add the coverage section to `docs/METHODOLOGY.md`: the plain-language definition of **comparison-readiness**, the **three deficits** and what different observation each calls for, and the **blocked-pair count** — including, in as many words, that the count is *pairs unblocked and never hryvnia*, and why that boundary is deliberate (valuing a corridor needs costing over a registry that does not yet contain the observation, which is an invented number by construction). State the advisory-not-binding deferral and the no-composition boundary. Add the new tests to the "Where to look next" table.
- [ ] T041 [P] Update `docs/REQUIRED_TESTS.md`: **flip no lettered row** — no row names a registry coverage audit, and the spec says so plainly rather than stretching one. Record in the file's notes that B10, B12, H2 and G6 are reinforced by this feature, naming the test paths that reinforce them.
- [ ] T042 Run the full quickstart verification of [quickstart.md](./quickstart.md) §1–§6 command by command, then the whole gate set: `uv run ruff check . && uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports`, `uv run python scripts/check_provenance.py`, `uv run pytest --cov`, `uv run pytest -m "contract or invariant"`. **Checkpoint — commit** (`/commit`): the properties and the documentation.
- [ ] T043 Final read-through of the branch diff against the twenty success criteria: every SC has a named test, every departure from a research.md decision is recorded in the report, and no tolerance and no `float` appears anywhere in this feature's source.

---

## Dependencies & execution order

### Phase dependencies

- **Phase 1 (Setup)** — no dependencies.
- **Phase 2 (Foundational)** — blocks every user story. The declaration must load before the
  report can be built, and the records must exist before the fold can return one.
- **Phase 3 (US1)** — depends on Phase 2. **Phase 4 (US2)** depends on Phase 3 and shares its
  commit: an empty `todo` beside populated deficits would be a confident wrong output.
- **Phase 5 (US3)** — depends on Phase 4 (the per-regime block is the thing being split).
- **Phase 6 (US4)** — depends on Phase 5; it is verification of what Phases 3–5 built.
- **Phase 7** — depends on all of the above; T037 needs the whole fold.

### Within each phase

- Tests are written first and must fail — an `ImportError` counts.
- Records before the functions that build them.
- Matching before classification before assembly.

### Parallel opportunities

- T003 ∥ T004 (one module, two independent concerns — write together, run together).
- T011 ∥ T012 ∥ T013 — three test modules, no shared file.
- T036 ∥ T038 ∥ T040 ∥ T041 — generator, totality property, and the two docs are disjoint.
- T006, T007, T008 all touch different data-layer modules but must land in order: schema,
  then loader, then resolver.

---

## Implementation strategy

**MVP is Phase 2 + Phase 3 + Phase 4.** At that point the owner can ask what his declared
registry supports and be told, per pair, with a to-do list ordered by what each observation
unblocks. Phase 5 makes it regime-aware, Phase 6 proves it grows on data alone, and Phase 7
pins it to costing and writes it down.

Commit points, all through `/commit`, all gate-clean: **T010**, **T028**, **T032**, **T035**,
**T042**. Nothing half-finished is committed to checkpoint it.

---

## Success-criteria map

| SC | Where it lands |
|---|---|
| SC-001 | T011 `tests/worked_examples/test_coverage_table.py` |
| SC-002 | T011, T013 |
| SC-003 | T022 `tests/unit/test_coverage_deficits.py` |
| SC-004 | T027 `tests/contract/test_coverage_no_figures.py` |
| SC-005 | T022 |
| SC-006 | T022 |
| SC-007 | T029 `tests/unit/test_coverage_regimes.py` |
| SC-008 | T027 |
| SC-009 | T037 `tests/invariants/test_coverage_costing_agreement.py` |
| SC-010 | T013 |
| SC-011 | T013 |
| SC-012 | T011 |
| SC-013 | T012 `tests/unit/test_coverage_empty.py` |
| SC-014 | T033 `tests/contract/test_coverage_data_only.py` |
| SC-015 | T033 |
| SC-016 | T039 |
| SC-017 | T013 |
| SC-018 | T029 |
| SC-019 | T033 |
| SC-020 | T039 |
| FR-001 totality | T038 `tests/invariants/test_coverage_totality.py` |

## Notes

- `[P]` means a different file and no dependency on an incomplete task.
- Every commit goes through `/commit`; never hand-roll `git commit`, never push, never amend.
- Never loosen a gate to pass it, and never skip, `xfail` or delete a `contract` or
  `invariant` test — those are compliance tests for the constitution.
- If a legal, tax or fee value would have to be guessed: stop and ask. There is none in this
  feature by design, and needing one means something has gone wrong.
