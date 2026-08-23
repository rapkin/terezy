---

description: "Task list for 004-composed-paths"
---

# Tasks: Composed paths

**Input**: Design documents from `specs/004-composed-paths/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md) (D1–D13),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: mandatory. Constitution Principle V is non-negotiable — every behaviour lands with a
hand-computed worked example, a Hypothesis invariant, or a golden file, and **the test fails
before the implementation exists** (an `ImportError` counts). Every task group below is written
tests-first for that reason.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: which user story the task serves (US1–US5); setup, foundational and polish carry none

## Path conventions

Single Python library, src layout: `src/terezy/`, `tests/`, `data/`, `scripts/`. All paths below
are repository-relative and live inside the worktree.

## The order that matters (plan.md Phase 2 note)

1. the **declaration and its refusals**, then
2. the **widened types** — nothing costs until `Candidate` exists, then
3. **`legs_of` with 002's golden file green** — the checkpoint proving the shape widened without
   moving a number, then
4. **enumeration**, then
5. the **properties**.

**Trap register**, carried at the top because each one is a silent wrong answer rather than a red
test:

- **T-1** `tests/golden/ramp_comparison.golden.txt` must not move. Its *rendering test* may change
  where the widened type forces it; the artefact may not.
- **T-2** One fold, not a sum of segment costs. `legs_of` concatenates and `cost_one` walks once.
  The whole-candidate accumulators keep their existing addition order; the per-segment
  attribution is a **separate** accumulator beside them, never their source.
- **T-3** `Leg.index` is normalised before duplicate comparison (research.md D6).
- **T-4** Nothing is pruned by cost. No shortest path, no partial-cost cache, no field for a score.
- **T-5** Determinism: adjacency buckets sorted by route id, no `set` iterated, no `dict` trusted
  for order, and the emitted candidate tuple sorted by `(segment count, route ids)`.

---

## Phase 1: Setup

**Purpose**: record the baseline the final report is measured against, and put the one new data
directory in front of the fail-closed provenance gate before anything reads it.

- [X] T001 Record the baseline in the implementation notes: `uv run pytest --cov` test count and
      coverage percentage, and that `uv run ruff check . && uv run ruff format --check .`,
      `uv run mypy`, `uv run lint-imports` and `uv run python scripts/check_provenance.py` are
      green on `feat/004-composed-paths` before any edit.
- [X] T002 Flip `004-composed-paths` to `status = "in-progress"` in `specs/features.toml` (lands
      with the first implementation commit; **not** to `done`, and no merge — the owner reviews).

---

## Phase 2: Foundational — the declaration, then the widened types

**⚠️ Blocking.** No user story can be implemented until the segment bound loads and `Candidate`
exists. FR-006 first because a bound with a permissive default is the failure that would be
invisible afterwards; the types second because nothing costs until they exist.

### The segment-bound declaration (FR-006, research.md D8)

- [X] T003 Write `tests/contract/test_composition_declaration.py` — every refusal in
      [contracts/composition-declaration.md](./contracts/composition-declaration.md), each
      asserting the file **and** the field are named: directory or file absent, `max_segments`
      missing, `max_segments < 1`, `max_segments` not an integer, a second file in
      `data/composition/`, an extra key, an empty `owner.id`, and an owner who does not own the
      streams the bound is resolved with. Plus the accepting case: `max_segments = 1` loads and
      means composition is off. Must fail with `ImportError` before T005–T007 exist.
- [X] T004 [P] Add `"composition"` to `EXEMPT_DIRS` in `scripts/check_provenance.py` **with its
      reason recorded beside it** — owner policy, nothing to cite, the reason `objectives`,
      `strategies` and `spendable` already carry. Never `SOURCED_DIRS`: the gate is fail-closed
      over the data tree, so a directory in neither list is an error.
- [X] T005 Add `CompositionTable` and `CompositionFile` to
      `src/terezy/data/declarations/schema.py`, `STRICT` like every neighbour, **zero field
      defaults**, reusing the existing `OwnerTable`.
- [X] T006 Add `composition_from_file(path) -> tuple[str, SegmentBound]` to
      `src/terezy/data/declarations/loader.py`, with the header comment its neighbours carry
      explaining why no citation is read here.
- [X] T007 Add `COMPOSITION_DIR`, `CompositionDeclarations`, `resolve_composition` and
      `composition_from_data_root` to `src/terezy/data/declarations/resolver.py`, on feature
      003's `CoverageDeclarations` precedent: a record **beside** `RampDeclarations`, not more
      fields on it, so a data root with no composition file can still cost a ramp. Refuse a
      second file by name, and check the owner against the streams.
- [X] T008 Write `data/composition/owner-001.toml` — `[owner] id`, `[composition] max_segments`,
      with the header comment that says out loud that this is policy rather than an observation,
      that there is no default, and that `1` means composition is off.

**Checkpoint**: `uv run python scripts/check_provenance.py` and
`uv run pytest tests/contract/test_composition_declaration.py` green. **Commit.**

### The widened path type (FR-013, research.md D2, D4)

- [X] T009 Write `tests/unit/test_composed_path_types.py` — `ComposedPath` needs at least two
      segments to mean anything, `Candidate` is matched with `match` and carries no
      `is_composed` flag, `ExitChain` has exactly three shapes, `EXIT_BY_IDENTITY` is a distinct
      value rather than an empty `ComposedExit` or `None`, and no record in the feature has a
      field for a path score or a combined disruption probability (FR-019, research.md D12).
- [X] T010 Extend `src/terezy/core/routes/path.py` with `ComposedPath`, `Segment`, `Candidate`,
      `DeclaredExit`, `ComposedExit`, `EXIT_BY_IDENTITY`, `ExitChain`, `Journey`,
      `FROM_THE_DECLARATION`, and the free functions `segments_of`, `exit_segments_of`,
      `candidate_id`, `journey_of`. `FundingPath` is **not** repurposed and gains nothing.
- [X] T011 Extend `src/terezy/core/results/ramp.py`: `RampCost.path: Candidate`,
      `RampCost.exit_path: ExitChain | None`, `SegmentAttribution`, `OneWayCost.by_segment`,
      `RoundTripCost.by_segment`, `RouteUnusable.binding_segment: Segment | None`. No field for a
      path-level disruption probability, and that absence is the requirement.
- [X] T012 Add `src/terezy/core/results/composed.py`: `Enumeration` and `CompositionRefused`.

**Checkpoint**: `uv run mypy` green on `src/`. **Commit.**

### `legs_of`, and the golden file still green (FR-003, FR-004, SC-002)

- [X] T013 Write `tests/contract/test_composed_same_costing.py` (SC-002, SC-006, SC-009, SC-011)
      — asserted **by construction** as 002's `test_same_code_path.py` asserts its own: `legs_of`
      is the only producer of a leg sequence, `cost_one` is the only costing function, a composed
      candidate reaches neither by a second path; provenance and staleness on a composed
      candidate are the concatenation's (SC-006); no cost figure is attributable to a destination
      alone (SC-009); per-leg disruption everywhere and no combined figure anywhere (SC-011).
- [X] T014 Add `legs_of(candidate, routes)` to `src/terezy/core/routes/cost.py` together with the
      private `_chain` that pairs each leg with its `Segment`, and widen `cost_one` to take a
      `Candidate` and an `exit_path`. **T-2**: the whole-candidate accumulators keep their exact
      addition order and the per-segment attribution is a separate accumulator beside them.
- [X] T015 Widen `src/terezy/core/routes/ranking.py` to one league over `Candidate | Journey`
      (FR-010) — no bonus, no penalty, no separate league, 002's ties unchanged.
- [X] T016 Widen `src/terezy/core/routes/execute.py` to derive its events from a composed figure,
      and `paths_in_force` in `src/terezy/core/scenarios/regimes.py` to narrow a `Candidate` by
      every segment.
- [X] T017 Get `tests/golden/test_ramp_comparison.py` green **without the artefact moving**
      (**T-1**), updating only the rendering where the widened type forces it, and run the whole
      existing suite to confirm 002's and 003's numbers did not move.

**Checkpoint**: full suite green, `ramp_comparison.golden.txt` unchanged in `git status`.
**Commit — this is the checkpoint the feature is judged on.**

---

## Phase 3: User Story 1 — reach a destination nobody declared end to end (P1) 🎯 MVP

**Goal**: compose candidates from declared routes, cost each exactly as a declared route, rank
them in one league.

**Independent Test**: declare A→B and B→C and no A→C; ask for C; check the composed candidate's
arriving amount and cost percentages against hand-computed leg-by-leg arithmetic.

- [X] T018 [P] [US1] Add the composed fixtures to `tests/composed_registries.py` — a hand-built
      A→B→C registry with no end-to-end declaration, a junction whose venue matches and whose
      currency does not, and a chain whose concatenation reproduces a declared route leg for leg.
      Every number invented, every `verified_on` empty, said so in capitals.
- [X] T019 [US1] Write `tests/worked_examples/test_composed_arithmetic.py` (SC-001, SC-014) —
      leg-by-leg arithmetic worked out by hand and checked in beside the assertion; the composed
      figure against it within the single imported tolerance; attribution naming both the
      dominating component and the dominating segment, each traced to its declaration.
- [X] T020 [US1] Implement `compose` and `SegmentBound` in `src/terezy/core/routes/compose.py`:
      an adjacency index per direction from `(venue, currency)` to departing routes with each
      bucket **sorted by route id** (**T-5**), depth-first with a visited-venue set (**T-4**: no
      pruning by cost, no partial-cost cache, no heuristic), the declared bound as the only depth
      limit, and a typed `CompositionRefused` for a question that could not be asked.
- [ ] T021 [US1] Extend `tests/invariants/test_cost_attribution.py` with the second axis
      (research.md D7): the segment attributions sum to the same total as the components, on
      composed candidates as on declared routes.

**Checkpoint**: US1 independently testable — a composed candidate is costed and ranked beside a
declared one. **Commit.**

---

## Phase 4: User Story 2 — trust that composition invented nothing (P1)

**Goal**: provenance, staleness, capacity pools, latency, status and disruption compose by 002's
rules, because the fold never knew what a route was.

**Independent Test**: compose a path with one unverified and one stale segment value; confirm
every derived figure carries the mark and the verdict.

- [ ] T022 [P] [US2] Write `tests/worked_examples/test_composed_pool.py` (SC-007) — two legs in
      **different segments** naming one capacity pool consume one shared monthly headroom; the
      deployable amount equals the hand-computed joint figure, never the sum of two full limits.
- [ ] T023 [US2] Confirm SC-006 and SC-011 hold in `tests/contract/test_composed_same_costing.py`
      against the real implementation, and record in the module docstring that they hold because
      the fold is unchanged rather than because new code was written for them (research.md D11).

**Checkpoint**: US2 independently testable. **Commit.**

---

## Phase 5: User Story 3 — keep the search honest and bounded (P2)

**Goal**: exhaustive within a declared bound, cycles refused, nothing dropped without a reason,
and enumeration order influencing nothing.

**Independent Test**: a registry whose graph contains a loop and a corridor longer than the bound;
no candidate visits a venue twice, none exceeds the bound, and the bound is visible in the result.

- [X] T024 [P] [US3] Add the search strategies to `tests/invariants/route_graphs.py` — a
      Hypothesis strategy producing a connectable route graph with cycles, with corridors beyond
      any plausible bound, and with routes declared in both directions.
- [X] T025 [US3] Write `tests/invariants/test_composition_search.py` (SC-004, SC-005, SC-016) —
      zero candidates visit a venue twice **over the entire emitted set**; with a bound of `n`
      nothing longer than `n` appears and **everything** connectable up to `n` does, checked
      against an independently written brute-force enumerator; the bound travels with the
      results; and no candidate mixes directions, including on a registry where the only
      completion of an inbound chain runs through a route declared exit.
- [X] T026 [US3] Write `tests/invariants/test_composition_order.py` (SC-003) — reversing the
      declaration order of the registry changes no candidate, no figure, no ranking position, no
      recommendation and no tie; and a composed candidate and a declared route costing the same
      within the project tolerance are reported as a tie rather than resolved by which the search
      found first.
- [X] T027 [US3] Write `tests/unit/test_composed_duplicates.py` (SC-013) — a registry declaring a
      route **and** its exact segment-wise equivalent yields the declared route once and the
      composed duplicate never, with `Leg.index` normalised before the comparison (**T-3**), and
      a chain over the same venues with different legs standing as a distinct candidate.

**Checkpoint**: US3 independently testable. **Commit.**

---

## Phase 6: User Story 4 — respect feasibility, regimes and the join (P2)

**Goal**: a composed candidate is subject to every constraint its segments declare, on the date in
question, within one regime.

**Independent Test**: compose a path with one segment closed on the date; the candidate is
excluded with the binding segment named and its absence visible.

- [ ] T028 [US4] Write `tests/unit/test_composed_feasibility.py` (SC-008, SC-012) — a closed,
      disrupted or out-of-window segment excludes the candidate with the **binding segment**
      recorded and the exclusion visible in the output; an amount below a minimum anywhere along
      the chain reports the minimum, the shortfall and the segment and is never rounded up; and
      across a regime transition no candidate mixes route sets, on a registry where only a mixed
      chain would connect.
- [ ] T029 [US4] Make it pass in `src/terezy/core/routes/cost.py`: `binding_segment` set from the
      `_chain` pairing, and every segment's declared status checked in order.

**Checkpoint**: US4 independently testable. **Commit.**

---

## Phase 7: User Story 5 — extend reach with a declaration (P3), and the exit chain

**Goal**: one route declaration extends the reachable graph with zero source changes; a chain of
declared exit routes satisfies 002 FR-027 (FR-012), and `EXIT_BY_IDENTITY` closes the recorded
tension with feature 003.

**Independent Test**: add one route declaration connecting a terminal venue onward; new composed
candidates appear, fully costed and ranked, with no source-code change.

- [ ] T030 [P] [US5] Write `tests/worked_examples/test_composed_exit_chain.py` (SC-015) — a round
      trip whose exit is reachable only by chaining declared exit routes, hand-computed leg by
      leg; and the other way, a destination from which nothing chains still reporting *exit cost
      unknown*, staying out of the round-trip ranking, and never promoting its one-way figure.
- [ ] T031 [P] [US5] Write `tests/contract/test_composed_distinct.py` (SC-017, SC-018) — every
      composed candidate in every ranking, report and recommendation is a distinct **type** shown
      segment by segment, each segment naming its declared route, verified across every reported
      candidate rather than sampled; and two distinct exit chains from one destination give two
      distinct round-trip figures, each keyed by its chain, tying when equal within tolerance.
- [ ] T032 [P] [US5] Write `tests/contract/test_composed_data_only.py` (SC-010) — adding one route
      declaration that connects a terminal venue onward makes new composed candidates appear,
      fully costed and ranked, with **zero** lines of source code changed; and a corridor broken
      by one missing segment is simply absent, never fabricated.
- [ ] T033 [US5] Implement exit-chain enumeration in `src/terezy/core/routes/compose.py` — the
      same function with `direction` as its parameter (research.md D9, D10), the bound applying to
      each chain separately, and a chain ending at a **declared spendable endpoint** passed in as
      a parameter rather than read out of feature 003 (research.md D13).
- [ ] T034 [US5] Implement `EXIT_BY_IDENTITY` costing in `src/terezy/core/routes/cost.py` and
      state at the site that a round trip costing nothing **because there is nothing to do** is a
      different claim from one whose fees cancelled.

**Checkpoint**: all five stories independently functional. **Commit.**

---

## Phase 8: Polish & cross-cutting

- [ ] T035 [P] Update `docs/METHODOLOGY.md` in the same change as the behaviour: what a composed
      candidate is, why every one is costed in full, what a junction does **not** do, how the
      segment bound bounds reach, why there is no path-level disruption probability, and what
      `EXIT_BY_IDENTITY` claims.
- [ ] T036 [P] Update `docs/REQUIRED_TESTS.md`: this feature closes **no** row; record the
      pressure it puts on **B12**, **G6** and **H1** in *Rows a feature reinforced without
      closing*, with the test paths that hold them.
- [ ] T037 [P] Add the `data/composition/` section to `data/README.md`, in the voice its
      neighbours use.
- [ ] T038 Record in `specs/features.toml` that `identity-exit-vs-partner-requirement` is closed
      by this feature — the `[[future]]` entry comes off the list rather than being left as a
      solved problem, with the removal justified in the commit message.
- [ ] T039 Run the quickstart end to end
      ([quickstart.md](./quickstart.md)) and every gate:
      `uv run ruff check . && uv run ruff format --check .`, `uv run mypy`,
      `uv run lint-imports`, `uv run python scripts/check_provenance.py`, `uv run pytest --cov`,
      `uv run pytest -m "contract or invariant"`.

**Checkpoint**: every gate green, the golden artefact unmoved, all eighteen success criteria named
to a test. **Commit.**

---

## Dependencies & execution order

### Phase dependencies

- **Phase 1 (setup)**: no dependencies.
- **Phase 2 (foundational)**: blocks every story. Within it the order is fixed by plan.md's Phase 2
  note: declaration → types → `legs_of` with the golden green.
- **Phase 3 (US1)**: needs Phase 2 whole.
- **Phase 4 (US2)**: needs T020 (`compose`) for a composed candidate to exist.
- **Phase 5 (US3)**: needs T020.
- **Phase 6 (US4)**: needs T020.
- **Phase 7 (US5)**: needs T020 for reach and T014 for exit costing.
- **Phase 8 (polish)**: needs every story.

### Within each story

Tests first, and they must fail before the implementation exists. An `ImportError` counts.

### Parallel opportunities

- T004 runs beside T003 (different files).
- T018, T022, T024, T030, T031, T032 are independent test modules and can be written in parallel.
- T035, T036, T037 are three different documents.

---

## Implementation strategy

**MVP** is Phase 1 + Phase 2 + Phase 3: a composed candidate exists, is costed by the one costing
function, and ranks beside a declared route — with 002's golden file unmoved. Everything after
that adds honesty guarantees over the same machinery rather than new machinery.

**Incremental delivery**: commit at every checkpoint above, ticking the boxes in this file in the
same commit as the work, so an interruption is cheap to recover from.

---

## Notes

- Commit through the `/commit` skill only. Never hand-roll `git commit`. No push, no PR, no amend.
- Never loosen a gate to pass it, and never skip, `xfail` or delete a `contract` or `invariant`
  test — that requires a constitution amendment.
- No legal, tax or fee value is guessed. The only number this feature adds to `data/` is the
  owner's own segment bound, which is policy and cites nothing.
