# Tasks: CPI and the real hurdle rate

**Input**: Design documents from `specs/007-cpi-real-terms/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md) (D1–D10),
[data-model.md](./data-model.md), [contracts/deflation.md](./contracts/deflation.md) (G1–G13)

**Tests**: **Required, and required first.** Constitution Principle V is non-negotiable: every
financial behaviour lands with a hand-computed worked example, a Hypothesis invariant or a
golden file, and **the test must fail before the implementation exists**. Test tasks are
therefore not optional here and each story's tests precede its implementation.

**Organization**: Grouped by user story. The order that matters is plan.md's Phase 2 note —
**the series and its coverage first**, because the refusal path is the one that runs today;
then the Fisher relation with its worked example; then the slot; then the assumption.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 / US4, mapping to spec.md's user stories

## Path Conventions

Single Python library, src layout, layered `cli → api → data → core`. Paths are relative to
the worktree root `/Users/rapkin/dev/terezy/.claude/worktrees/007-cpi-real-terms`.

## The six traps these tasks exist to avoid

1. Inflation over a window is a **product**, not a sum (D1).
2. The **exact** Fisher relation; the subtraction approximation is *absent*, not discouraged (D3).
3. Coverage is **all-or-nothing, checked before any arithmetic** (D4).
4. **Two figures, never mixed**; `HurdleRate.real` stays **one** field (D2).
5. **A cited forecast is still an assumption** (D5).
6. 001's generic *"inflation is not modelled"* must **survive nowhere** (FR-012).

---

## Phase 1: Setup

**Purpose**: record the baseline every later claim is measured against. No source changes.

- [x] T001 Record the pre-change gate baseline (ruff, mypy, lint-imports, check_provenance,
      `pytest --cov`) in the implementation notes; it is the delta every later gate run is
      reported against. No file in `src/`, `data/` or `tests/` changes in this task.
- [x] T002 Flip `007-cpi-real-terms` to `status = "in-progress"` in `specs/features.toml`,
      landing in the first implementation commit per `specs/README.md`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the calendar primitive and the empty package every story below imports. Nothing
domain-specific happens here, and nothing downstream can start without it.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 Write the failing month-arithmetic tests in `tests/unit/test_periods.py`: `Window`
      is inclusive; `months_in` enumerates every month between `first` and `last`; a window
      whose `first` is after its `last` enumerates nothing; `next_month` rolls December into
      January; `month_of(date)` renders `YYYY-MM`; a malformed period is refused.
- [x] T004 Implement `src/terezy/core/primitives/periods.py`: frozen `Window(first, last)`,
      `month_of`, `next_month`, `months_in`, `month_count`, `is_period`. Pure, no clock, no
      I/O. Placed in `primitives` rather than in `core/inflation/` so that
      `primitives/rates.py` can type `RealRate.window` without importing upward.
- [x] T005 [P] Create the empty package `src/terezy/core/inflation/__init__.py` with the
      module docstring stating what the package is for and what it deliberately does not do
      (no network, no cache, no fetcher, no forecasting model).

**Checkpoint**: `Window` exists and is tested; the package imports.

---

## Phase 3: User Story 1 — See the hurdle rate in purchasing power (Priority: P1) 🎯 MVP

**Goal**: declared CPI observations deflate the contractual YTM, and where they do not cover
the window the slot says exactly which months are missing.

**Independent Test**: declare clearly-labelled synthetic monthly observations covering a known
window, deflate a known nominal figure over it, and check the result against arithmetic worked
out by hand — with the window chosen so a *summing* implementation gives a visibly different
answer and cannot pass.

### Tests for User Story 1 (write first; they must fail) ⚠️

- [x] T006 [P] [US1] `tests/unit/test_cpi_coverage.py` — coverage is all-or-nothing (G5):
      a fully covered window returns `Covered` with the window's observations in order; one
      missing month returns `NotCovered` **naming that month**; several gaps name all of
      them; a window is never shortened to its covered part; observations outside the window
      do not participate.
- [x] T007 [P] [US1] `tests/worked_examples/test_deflation_arithmetic.py` — the chained
      product and the exact Fisher relation, both hand-computed with the arithmetic checked in
      beside the assertion, over a window long enough that the sum and the product visibly
      disagree (D1). Compared with the single imported `TOLERANCE`.
- [x] T008 [P] [US1] `tests/worked_examples/test_falling_prices.py` — a negative-inflation
      window gives a real rate **above** the nominal one (G6), hand-computed; and a
      high-inflation window gives a **negative** real rate, neither clamped.
- [x] T009 [P] [US1] `tests/contract/test_no_subtraction_approximation.py` — an AST scan over
      `src/terezy/core/inflation/` and `src/terezy/core/results/hurdle.py` using
      `tests/source_scan.py`, asserting that no executable expression subtracts an inflation
      term from a nominal one (G3), and asserting the scan is falsifiable against a fixture
      that does.
- [x] T010 [P] [US1] `tests/unit/test_real_terms_reasons.py` — every `RealTermsUnavailable`
      reason is specific (G11): the absent series, the uncovered months listed, the absent
      nominal figure, the absent assumption, and a window with no elapsed month. Plus the
      repository-wide assertion that 001's *"inflation is not modelled"* appears nowhere under
      `src/`.
- [x] T011 [P] [US1] `tests/invariants/test_deflation_invariants.py` — Hypothesis properties:
      `deflate` is exact-Fisher (`(1+real)*(1+inflation) == 1+nominal` to tolerance); real
      exceeds nominal exactly when inflation is negative; `cumulative_inflation` of a
      concatenation is the compounded product of the parts (associativity of the chain);
      zero inflation leaves the nominal rate unchanged.

### Implementation for User Story 1

- [x] T012 [US1] `src/terezy/core/inflation/series.py` — `CpiObservation`, `CpiSeries`,
      the `Covered | NotCovered` tagged union, `coverage()`, `cumulative_inflation()` (the
      product, never a sum), `periods_per_year()` and `annualised()`. Frozen records, free
      functions, `match` over the union.
- [x] T013 [US1] `src/terezy/core/inflation/deflate.py` — `deflate(*, nominal, inflation)`,
      the exact Fisher relation **and nothing else** in the module.
- [x] T014 [US1] Extend `RealRate` in `src/terezy/core/primitives/rates.py` with `basis`,
      `series_id`, `window` and `provenance`, and record in the module docstring why the real
      rate is the one rate that carries provenance (its inputs are not the holding's inputs).
- [x] T015 [US1] `src/terezy/core/results/hurdle.py` — `RealTerms` (two independently typed
      outcomes, never itself unavailable), `HurdleRate.real` retyped to `RealTerms` (still
      **one** field, G2), the specific-reason builders replacing `NO_REAL_TERMS`, and
      `real_terms(*, nominal, series, window, assumption)` returning coverage-first.
- [x] T016 [US1] `src/terezy/core/results/hurdle.py` — `of_flows` gains the deflation inputs
      and fills the slot; no nominal computation is touched (G1).
- [x] T017 [US1] `src/terezy/core/results/project.py` — derive the deflation window from the
      holding and the contractual flows and pass it through, documenting why the window starts
      the month **after** the purchase month.
- [x] T018 [US1] `src/terezy/core/results/canonical.py` — `of_real_terms` renders both figures,
      each tagged, so a figure and its absence can never digest alike; bump
      `manifest.ENCODING` and move the pinned entry in
      `tests/unit/test_results_canonical.py`, because the projection's canonical shape changed.
- [x] T019 [US1] Update the 001-era consumers of the slot so they read `RealTerms`:
      `tests/unit/test_hurdle_real_slot.py`, `tests/unit/test_hurdle_arithmetic.py`,
      `tests/unit/test_results_canonical.py`, `tests/worked_examples/test_ovdp_schedule.py`,
      `tests/contract/test_data_only_extensibility.py`.

**Checkpoint**: the arithmetic is right, the refusals are specific, and nothing nominal moved.

---

## Phase 4: User Story 2 — Never mistake an assumption for an observation (Priority: P1)

**Goal**: a realized figure and an assumption-driven figure are two figures, distinguishable
at a glance and in the type, and every mark on either side of the deflation survives it.

**Independent Test**: produce a real figure from observed CPI and one from a declared
assumption, and confirm neither's provenance trail leads to the other's inputs and that no
field anywhere holds a number blending the two.

### Tests for User Story 2 (write first; they must fail) ⚠️

- [x] T020 [P] [US2] `tests/contract/test_two_figures_never_blend.py` — realized and assumed
      carry different `basis` values; no reported number combines observed and assumed
      inflation; **a cited external forecast is still labelled an assumption** (G8); two runs
      differing only in the declared assumption are two results, each naming the assumption it
      used (SC-008).
- [x] T021 [P] [US2] Extend `tests/contract/test_provenance_propagation.py` — the real
      figure's provenance is the **union** of the nominal figure's and every observation that
      deflated it, asserted **by count** rather than by sample (D6); an unverified observation
      marks the real figure; an unverified nominal input marks it even when every observation
      is verified; and the mark is falsifiable (all-verified inputs produce no mark).

### Implementation for User Story 2

- [x] T022 [US2] `src/terezy/core/inflation/series.py` — `InflationAssumption`
      (`annual_rate`, `is_assumption: Literal[True]`, `rationale`, `id`, optional `provenance`
      and staleness `kind`), on `RegimeTransition`'s precedent.
- [x] T023 [US2] `src/terezy/core/results/hurdle.py` — `real_terms` computes the assumed
      figure from the declared assumption, independently of the realized one, and refuses with
      a named reason when no assumption was declared (G9).
- [x] T024 [P] [US2] `src/terezy/data/declarations/schema.py` — `InflationAssumptionTable`
      and `InflationAssumptionFile`, appended under a `007-cpi-real-terms` banner.
- [x] T025 [US2] `src/terezy/data/declarations/loader.py` — `inflation_assumption_from_file`,
      appended under the same banner: percent to fraction exactly once, `is_assumption` refused
      when false, and a half-filled citation refused rather than half-read.
- [x] T026 [US2] `data/scenarios/inflation/owner-001.toml` — the declared owner assumption,
      `is_assumption = true`, a placeholder rationale in `war_end.toml`'s own words. In a
      **subdirectory** because `scenarios/*.toml` is globbed as scenario files and does not
      recurse (the `instruments/nav/` precedent).
- [x] T027 [US2] `src/terezy/data/manifest.py` — `InputKind` gains `cpi_series` and
      `inflation_assumption`, so FR-015's *"the run manifest records which declaration produced
      it"* is a recorded input rather than a claim.

**Checkpoint**: the two figures exist, never blend, and carry every mark their inputs carry.

---

## Phase 5: User Story 3 — Know when the CPI data has gone stale (Priority: P2)

**Goal**: a CPI observation aged past its declared threshold marks every real figure derived
from it, and a kind with no threshold fails at load.

**Independent Test**: age declared observations past the threshold and confirm the derived
figure reports it; declare a kind with no threshold and confirm loading fails naming the kind.

### Tests for User Story 3 (write first; they must fail) ⚠️

- [x] T028 [P] [US3] `tests/unit/test_cpi_staleness.py` — stale observations produce a verdict
      naming the value and its threshold; fresh ones produce **no** warning; the age is measured
      from the later of verification and retrieval (002 FR-025); a kind declared with no
      threshold fails at load naming the kind; and the staleness question is kept distinct from
      the coverage question (D7) — both can fire on one run and the messages do not merge.

### Implementation for User Story 3

- [x] T029 [US3] `src/terezy/core/inflation/series.py` — `staleness_of_observations`, folding
      the existing `staleness.staleness_of` per observation under that observation's declared
      kind, and merging with the existing monoid rather than inventing a second path.

**Checkpoint**: freshness is reported, and a warning never fires on fresh data.

---

## Phase 6: User Story 4 — Add CPI data without touching the engine (Priority: P3)

**Goal**: CPI is data. Extending the series, correcting a value, or declaring a second
country's series are data-only changes, and every malformed file fails naming the offence.

**Independent Test**: extend the declared series and declare a second, differently identified
series purely as data; both load, the first drives results, and no source file is edited.

### Tests for User Story 4 (write first; they must fail) ⚠️

- [x] T030 [P] [US4] `tests/contract/test_cpi_declaration_loading.py` — the refusal battery
      (SC-005): malformed value, unrecognised field, missing required field, duplicate period,
      overlapping/out-of-order periods, a period inconsistent with the declared periodicity, a
      period that has not yet elapsed, a duplicated series identity, an empty series, a blank
      citation, an absent `verified_on` key. Every case names the file and the offending field
      or period, and no case substitutes a default. Plus the shipped `data/cpi/ua.toml` loading
      clean with 411 observations, 1991-08 .. 2025-10, every one unverified.
- [x] T031 [P] [US4] `tests/contract/test_cpi_data_only.py` — G13: a second CPI series with a
      distinct identity, declared purely as data, loads and is addressable with **zero** lines
      of source changed (SC-009); nothing treats "the CPI" as a singleton; periodicity is read
      from the declaration.

### Implementation for User Story 4

- [x] T032 [US4] `src/terezy/data/declarations/schema.py` — `CpiSeriesTable`,
      `CpiObservationTable`, `CpiFile`, appended under the `007-cpi-real-terms` banner, matching
      the shape `data/cpi/ua.toml` already has.
- [x] T033 [US4] `src/terezy/data/declarations/loader.py` — `cpi_from_file`, appended under the
      banner: one `SourceRef` per observation table, every refusal in T030 raised here with the
      file and the field or period named.
- [x] T034 [US4] `src/terezy/data/declarations/resolver.py` — `InflationDeclarations`,
      `resolve_inflation` and `inflation_from_data_root`, appended under the banner: series
      keyed by id with a duplicated identity refused across files, plus the optional declared
      assumption and the files both came from.

**Checkpoint**: a second series is a data-only addition, and a broken file cannot load quietly.

---

## Phase 7: The golden, the documentation and the recorded obligations

**Purpose**: the claims this feature makes about itself, made checkable.

- [x] T035 `tests/golden/test_end_to_end_ovdp.py` — render both real-slot entries, feed the
      shipped CPI series, and regenerate `tests/golden/ovdp_synthetic_a.golden.txt`. **Read the
      diff**: the real slot's lines, the canonical encoding tag and the digest may move; **every
      nominal figure, schedule row and tax charge must be byte-identical** (G1, FR-014). If a
      nominal figure moves, stop.
- [x] T036 [P] `docs/METHODOLOGY.md` — the Fisher relation, its plain-language definition and a
      **worked example**, in the same change as the formula (FR-008, SC-010), plus the
      month-on-month chaining rule and the annualisation it feeds.
- [x] T037 [P] `docs/REQUIRED_TESTS.md` — flip the rows this feature closes and record their
      test paths; **F4 stays unflipped**, its second half being the display-currency feature's.
- [x] T038 [P] `specs/001-ovdp-hurdle-rate/spec.md` — the ⚙ cross-reference at FR-022 recording
      that the prohibition was **refined, not repealed** (FR-009's recorded obligation).
- [x] T039 [P] `data/README.md` — the `cpi/` row and the inflation-assumption row, so the data
      surface documents itself.
- [x] T040 Run every gate from the worktree and record the delta from T001's baseline:
      `ruff check`, `ruff format --check`, `mypy`, `lint-imports`, `check_provenance.py`,
      `pytest --cov`, `pytest -m "contract or invariant"`. Confirm
      `grep -rn "inflation is not modelled" src/` is empty.

---

## Phase 8: Review round

**Purpose**: the findings of the independent code review, which is a blocking gate before
anything lands on `main`. One was a blocker; the rest were concrete and confirmed.

- [x] T041 **Blocker.** `core/inflation/series.py`'s two verdict functions had **no production
      call sites** — `real_terms` took no `as_of`, `RealRate` had no field for a verdict — while
      US3 scenario 1, `contracts/deflation.md` G10 and `METHODOLOGY` §23.6 all asserted that a
      real figure reports its staleness. Implemented: `staleness.Ageing`, `RealRate.staleness`,
      `Deflation.ageing`, `project(ageing=...)`, merged over the CPI side and the nominal side.
- [x] T042 Hoist the no-elapsed-month guard from `_realized` into `real_terms`, where it covers
      **both** figures. `_assumed` had none, so a reversed window produced a `RealRate` whose
      `window` named a span containing no months — a breach of FR-011 the existing test could
      not see because it checked `.realized` only.
- [x] T043 `docs/METHODOLOGY.md` §12.2 documented the digest prefix as `terezy-canonical-v2`.
      It is the only human-readable specification of the digest bytes, so anyone reproducing a
      digest from it got the wrong answer. Corrected, with a version table and the ramp golden's
      blast radius stated.
- [x] T044 `manifest.of_run`'s `inflation` branch had no caller anywhere. Wired through
      `tests/unit/test_manifest_records_inputs.py`, so FR-015's manifest clause is exercised by
      the function runs actually use rather than only by calling `inflation_input_refs` directly.
- [x] T045 Widen the encoding-tag fingerprint from one of `of_projection`'s four components to
      all four, plus the real slot's **unavailable** branch — whose shape differs from the
      populated one and was outside the pin.
- [x] T046 Widen the construction-site scan to module-qualified calls and to
      `dataclasses.replace`, which the first cut could not see; add a containment property
      naming every module allowed to touch a real figure at all.
- [x] T047 `RunManifest.unverified_sources` claimed *every source behind the headline figure*
      while being built from `hurdle.provenance`, which deliberately excludes CPI. Widened to
      the real figures too, so 411 unverified observations behind a reported number are named.
- [x] T048 Test the three programmer-error guards this feature added (`deflate` at −100%
      inflation, `annualised` over no periods, `coverage` on a duplicated period), and close the
      `NotCovered(missing=())` hole in the coverage totality invariant.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies.
- **Phase 2 (Foundational)**: depends on Phase 1. **Blocks every user story** — `Window` is in
  the signature of everything below.
- **Phase 3 (US1)**: depends on Phase 2. The MVP, and the phase that must land first: the
  refusal path is the one that runs against today's data.
- **Phase 4 (US2)**: depends on Phase 3 — the assumed figure shares `real_terms` with the
  realized one, and the provenance union is asserted over both.
- **Phase 5 (US3)**: depends on Phase 3 (needs `CpiObservation`); independent of Phase 4.
- **Phase 6 (US4)**: depends on Phase 3 (needs the core records to load into) and, for the
  assumption half of the resolver, on Phase 4.
- **Phase 7**: depends on all of the above.

### Within Each User Story

Tests first, and they must fail before the implementation exists (Principle V). Then core
records, then core functions, then the data layer, then the wiring.

### Parallel Opportunities

- T006–T011 are six different test files and run in parallel.
- T020 and T021 are two different test files and run in parallel.
- T030 and T031 are two different test files and run in parallel.
- T036–T039 touch four different documents and run in parallel.
- T024, T032 and T034 all append to the shared declaration modules under one banner each and
  are therefore **not** parallel with one another.

---

## Parallel Example: User Story 1

```bash
# The six US1 test files, all failing before any implementation exists:
uv run pytest tests/unit/test_cpi_coverage.py \
              tests/unit/test_real_terms_reasons.py \
              tests/worked_examples/test_deflation_arithmetic.py \
              tests/worked_examples/test_falling_prices.py \
              tests/contract/test_no_subtraction_approximation.py \
              tests/invariants/test_deflation_invariants.py
```

---

## Implementation Strategy

### MVP (User Story 1 only)

Phases 1–3. At that point the slot is filled, the arithmetic is hand-checked, and every
refusal names what is missing — which is the whole of spec.md's Story 1 and the larger half of
this feature's value.

### Incremental delivery

1. Phases 1–2 → the calendar primitive and the package.
2. Phase 3 → US1. **Commit at green.**
3. Phase 4 → US2. **Commit at green.**
4. Phase 5 → US3. **Commit at green.**
5. Phase 6 → US4. **Commit at green.**
6. Phase 7 → the golden, the documentation and the gates. **Commit at green.**

Each commit goes through `/commit`, which runs the gates and stops if any is red.

---

## Notes

- Every commit ticks the boxes above **in the same commit as the work**.
- `data/cpi/` is already in `SOURCED_DIRS` and reports 411 unverified values. That is correct
  and expected: nobody has checked them against Держстат yet.
- `scripts/fetch_cpi.py` is not part of this feature. Where the schema and the file disagree,
  **the schema is right and the script is updated** (D10).
- Never loosen a gate; never skip, `xfail` or delete a `contract` or `invariant` test.
