# Tasks: The BTC he already holds

**Feature**: `025-btc-holdings` | **Input**: [plan.md](./plan.md), [spec.md](./spec.md)

**Tests are not optional here.** Constitution Principle V is NON-NEGOTIABLE: no financial
behaviour is implemented before a test that would fail without it, and a test written before its
module — failing with `ImportError` — counts. Every phase opens with its checks.

**The gate is by artefact, not by phase.** The two clarifications in spec.md block the shipped
files that would have to state one — the instrument's price currency and the answer's shape. They
block no code. Phases 1–4 build the mechanism against fixtures and commit it; Phase 5 does not
start until the owner has answered both.

**No task may use the owner's real quantities, prices or dates.** Every fixture is invented and
labelled, and `data/user/` is never read by a test.

`[P]` marks a task touching files no incomplete task touches.

---

## Phase 1: The private overlay (foundational — blocks Phase 4)

**Goal**: the owner's real declarations have somewhere to go that is not git, and four things
that would leak or silently override refuse instead.

- [ ] T001 Write `tests/contract/test_private_overlay.py` against a scratch root pair: a seeds file in both roots refuses naming **both** paths (FR-003); a seed with `is_synthetic = false` under the shipped root refuses naming the file (FR-005); an overlay directory that is not `seeds/` refuses naming it (FR-006); an absent and an empty overlay each load and declare nothing (FR-002). Fails with `ImportError`.
- [ ] T002 [P] Write `tests/unit/test_overlay_manifest.py`: an input supplied by the overlay is recorded with a `user/` prefixed id and its path, and no declared value appears anywhere in the manifest (FR-008). Fails with `ImportError`.
- [ ] T003 Add the frozen `DataRoots(shipped, overlay)` record and the two-root file lookup to `src/terezy/data/declarations/resolver.py`, with the admitted-directory set fail-closed and the collision refusal (FR-001, FR-003, FR-004, FR-006).
- [ ] T004 Change `seeds_and_goals_from_data_root` to take `DataRoots`; enforce the `is_synthetic` rule where both the path and the lots are in hand (FR-005). Leave every other `*_from_data_root` on `Path`.
- [ ] T004a Move every caller with it: `src/terezy/api/http/categories.py` and the contract suites that pass a `Path`. The HTTP layer is a caller and the plan's blast radius covers it.
- [ ] T005 [P] Record overlay inputs in `src/terezy/data/manifest.py` under the `user/` prefix, with the path and the digest `InputRef` requires; add the seed member `InputKind` lacks — `check_enumerations.py` gates `Literal` alternatives, so a forgotten one is a red gate (FR-008).
- [ ] T006 [P] Correct `citation_policy.EXEMPT_DIRS["user"]`'s reason and `data/README.md`'s `data/user/` row: it holds the owner's own declarations, exempt for the reason `seeds/` is exempt (FR-007). Delete the run-output claim, do not rewrite it.
- [ ] T007 [P] Add `tests/fixtures/user_root/seeds/owner-001.toml` — a labelled **synthetic** overlay seed holding the fixture **held asset and nothing else**, in **its own root** passed as the overlay argument. Not under `tests/fixtures/data/`, which `tests/data_roots.py` copies *into* the shipped root; and disjoint from that root's two ОВДП lots, so FR-003 unions rather than refuses.

**Checkpoint**: gates green, every golden byte-identical, `data/user/` absent in CI. Commit.

---

## Phase 2: The held asset (US1, US2 — the instrument and its refused tax)

**Goal**: a thing whose only property is a price is declarable, and its tax refuses by name
without suppressing its value.

- [ ] T008 Write `tests/contract/test_held_asset_data_only.py`: a second held asset declared in a scratch data directory — a declaration, a group label and a seed lot, no engine edit — reaches the pipeline and is reported (FR-016, SC-008). Fails with `ImportError`.
- [ ] T009 [P] Write `tests/unit/test_held_asset_refusals.py`: a declaration carrying a price refuses (FR-011); a declaration whose tax class no pack declares yields `UnresolvedTaxClass` naming the class and the instrument (FR-014); the value, basis and nominal change survive that refusal (FR-015); a quantity is never inferred from a price (FR-012). Fails with `ImportError`.
- [ ] T010 Add `src/terezy/core/instruments/held.py`: the frozen declaration record — id, name, quantity unit, price currency, groups, tax class references — and nothing that projects an event (FR-009).
- [ ] T011 Add `HELD_ASSET` to `registry.DECLARATION_KINDS` and **not** to `registry.REGISTRY`; state at the site that it projects no event stream, in one sentence beside the fund's existing argument rather than a second copy of it (FR-010).
- [ ] T012 Add `loader.held_asset_from_file` and the resolver's dispatch on the declared kind (FR-009, FR-011).
- [ ] T013 [P] Declare `btc` in `data/groups.toml` — a label states nothing an answer turns on. **`data/instruments/btc.toml` is T027's**, because it must state a price currency and that is Clarification 1; the loader and the refusals are exercised here against a fixture instrument instead (FR-013).
- [ ] T014 [P] Read every prose enumeration of the declaration kinds and correct it in this change. **No gate catches this one**: `check_enumerations.py` reads `id =` columns, `Enum` members and `Literal` alternatives, and `DECLARATION_KINDS` is a `frozenset` of `Final` constants.

**Checkpoint**: gates green, the kind loadable, the tax refusal reached through a fixture. No golden moves — nothing shipped declares a held asset yet. Commit.

---

## Phase 3: The provider (US1 — the price exists as dated data)

**Goal**: one fetch, one file, one refusal per malformed shape, and nothing written when
anything is wrong.

- [ ] T015 Write `tests/unit/test_fetch_binance.py` with an **invented** recorded response fixture and its mutations: a row that is not twelve elements, a non-positive price, a gap in the window, a window ending short, a non-list body, and a row dated **on** the retrieval date — the open candle — each writes nothing and leaves the previous file byte-identical (FR-021, FR-024). No symbol check: a klines row carries none. Fails with `ImportError`.
- [ ] T016 [P] Add to it: the written file carries the endpoint, the retrieval date, one dated cited observation per row, and an **empty** `verified_on` on every one, including on a re-run over an existing file (FR-020, SC-007).
- [ ] T017 [P] Add to it: `_get` is replaced and never called, and the socket guard in `tests/conftest.py` covers the case where it is (SC-009).
- [ ] T018 Add `src/terezy/data/providers/interface.py`: the `fetch(kind, symbol, as_of)` signature and the typed refusal, as a function signature and a frozen record of functions — no class hierarchy, no `Protocol` with methods (FR-017). Replace the package docstring rather than extending it.
- [ ] T019 Add `src/terezy/data/providers/binance.py` over `GET /api/v3/klines` with `interval=1d` on the market-data-only host, behind a module-level `_get` seam, paginating at the documented 1000-row cap, taking each row's close and open time and recording the symbol **as requested** without splitting it; a `429` or `418` refuses (FR-018, FR-019, FR-021, FR-023).
- [ ] T020 [P] Add `scripts/fetch_binance.py`: `--symbol`, `--dry-run`, `--out`; build in memory, write to a temp path, rename over the target (FR-020, FR-021).
- [ ] T020a Declare the market-quotation kind in `data/observation_kinds.toml` with its threshold recorded **inert** and the reason why, run the script for real, and pass `check_provenance.py` over the file (FR-024).
- [ ] T021 Add the loader and resolver reader for `observations/binance_*.toml` as a declared dated series, selected by exact `as_of` and refusing by name otherwise, exercised against a fixture file (FR-011, FR-022). Correct `data/README.md`'s `observations/` row: it is read at run time now.

**Checkpoint**: gates green including `check_provenance.py` over the new file. Commit.

---

## Phase 4: The struck basis (US1 — the cost in hryvnia)

**Goal**: a dollar cost becomes a hryvnia basis at the official rate on its own date, carrying
both marks.

- [ ] T022 Write `tests/worked_examples/test_struck_basis.py` with hand-computed arithmetic on **placeholder** figures: `cost × rate ÷ quotation_unit` at a chosen acquisition date, the rate read out of `data/official_rates/ua_nbu_usd.toml` rather than retyped, to the imported project tolerance (FR-026, SC-005). Fails with `ImportError`.
- [ ] T023 [P] Write `tests/invariants/test_struck_basis_marks.py`: over generated lots and dates, no figure resting on a struck estimated basis carries fewer than two marks, and the two are distinguishable on inspection (FR-027, SC-006). Fails with `ImportError`.
- [ ] T024 [P] Write `tests/unit/test_struck_basis_refuses.py`: an acquisition date outside the declared series window is 011 FR-010's typed refusal naming the series, the pair and the date, and no lot loads with a neighbouring date's rate (FR-028).
- [ ] T025 Strike in `resolver.resolve_seeds_and_goals`, **not** in `core.ledger.seeds.seed_cost`: by then the cost is already `Money(x, base_currency)` and `strike_base` raises on an amount already in the tax currency. The resolver holds the instruments and gains the rate series; `seeds_from_file` stops tagging a cost whose currency it cannot know. Union the provenances (FR-025, FR-026, FR-027).
- [ ] T026 [P] Add the formula and its refusal to `docs/METHODOLOGY.md`, and record the narrowing in `specs/008-seed-and-goals/spec.md` FR-010 — two live documents disagreeing about what a declared cost means is how the wrong number gets written (FR-025).

**Checkpoint**: gates green, worked example and invariant passing, goldens still byte-identical. Commit.

---

## Phase 5: What the answer shows — BLOCKED on the three clarifications

**Do not start until the owner has answered all three.** Each task below names which answer it
depends on; guessing one is the failure this phase exists to prevent.

- [ ] T027 **[Clarification 1]** Declare the USDT/USD treatment as the owner settled it — a labelled belief in `data/scenarios/`, a refusal, or a cited observation — write `data/instruments/btc.toml` with the price currency that answer implies and no `data/access/` entry, and propagate the mark through every dollar and hryvnia figure (FR-009, FR-014, FR-023).
- [ ] T028 Re-run `scripts/fetch_binance.py` so the shipped observation covers the run's `as_of`, and confirm `market-quotation-staleness-kind` stays **open** in `specs/features.toml` with FR-024's reason recorded against it.
- [ ] T029 **[Clarification 2]** Write the answer test first, then build the shape the owner chose: the held standing distinguishable from the other four (FR-029), and the reported quantity, price with its date, value, basis, nominal change, and the typed refusals for tax, yield and rank (FR-030).
- [ ] T030 Assert what a held position is **not**: it is never enumerated as a candidate and never ranked against the benchmark, and `btc` leaves the undeclared population (FR-030). Re-measure 015 SC-002, which pins that population at two words and becomes one, `cash`.
- [ ] T031 Regenerate `tests/golden/the_answer.golden.txt` and `tests/golden/candidate_set.golden.txt` deliberately, reading the diff and quoting the changed lines in the commit message. Regenerate the OpenAPI document and re-run its golden.
- [ ] T032 Mark `docs/REQUIRED_TESTS.md` row **B2** `[~]`, not `[x]`: the fetch test covers *a provider outage never writes*, and the row's other half — cache entries carrying provenance and a synthetic flag — is untested because this feature ships no cache. Flip `025-btc-holdings` to `done` in `specs/features.toml`; record anything still open as a `[[future]]`.

**Checkpoint**: full gate list, `/condense`, then the review.

---

## Dependencies

- Phase 1 blocks Phase 4 (a struck basis needs a lot, and a real lot needs the overlay).
- Phase 2 blocks Phase 3 (the observation is read for a declared instrument) and Phase 4.
- Phase 3 blocks Phase 5 (a value needs a price).
- Phases 1, 2 and 3 are otherwise independent after their first task and may be worked in parallel by separate lanes.
- Phase 5 is blocked by the owner, not by code — and it holds every `data/` file that states an answer.
- **025 and 019 are declared parallelisable and are not**: both regenerate `tests/golden/the_answer.golden.txt` and both change the answer record. Whichever lands second re-measures.

## What is deliberately not here

No cache, no retry, no schedule — `provider-automation`'s job. No buy path, no disposal, no tax
rule. No return series, no volatility, no Sharpe.
