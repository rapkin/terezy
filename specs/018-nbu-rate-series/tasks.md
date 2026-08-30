# Tasks: The NBU rate series — filling a declared, empty series

**Feature**: `018-nbu-rate-series` | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

Tests are **not optional** here: Principle V is NON-NEGOTIABLE and every task below that lands a
financial behaviour is preceded by a test that fails without it.

## Phase 1: Setup

- [x] T001 Record the retrieval facts as executable arguments in `specs/018-nbu-rate-series/research.md` — done in Phase 0; re-verify D1–D3 before the live fetch by re-running the three quoted `curl` commands and confirming the row counts and the `units` boundary still hold.

## Phase 2: Foundational (blocking — every story rests on these)

These three are the defects the empty series has been hiding (spec.md, "The volume"). Each is
fixed in the module that owns it, and each lands before any data does, so that the data lands on
a tree that can carry it.

- [x] T002 [P] Write the failing test for the bisecting lookup in `tests/unit/test_official_rate_lookup.py`: `observation_for` must perform no work proportional to the number of observations per call (SC-013), asserted as a property of the lookup — a series whose observations are instrumented counts how many are touched — not by timing.
- [x] T003 Make `observation_for` bisect in `src/terezy/core/tax/official_rate.py` (FR-022), keeping the declared-observation-beats-rule precedence and the `KeyError` for a rule pointing at an undeclared date.
- [x] T004 [P] Write the failing test for the manifest entry in `tests/unit/test_manifest_records_inputs.py`: a run given official rates carries an `official_rate` input naming `ua_nbu_usd` and the file's digest, and editing one observation moves that digest (SC-012).
- [x] T005 Add `"official_rate"` to `InputKind`, `official_rate_input_refs` and `of_run(official_rates=...)` in `src/terezy/data/manifest.py` (FR-020).
- [x] T006 [P] Write the failing test for the gate's output in `tests/contract/test_provenance_gate.py`: unverified values are reported **one line per file** with a count, errors stay per value, and the total output does not grow by more than a constant with the number of unverified values (SC-014).
- [x] T007 Summarise unverified findings per file in `scripts/check_provenance.py` (FR-023), and correct the `quotation_unit` exemption comment, which assigns the closure to "whoever builds the fetch script" — that script now exists and refuses.

**Checkpoint**: all gates green on an unchanged data root. Commit.

## Phase 3: User Story 3 — the retrieval is reproducible and nobody has verified it (P1)

Ordered first among the stories because the data cannot land honestly before the thing that
retrieves it exists. **Independent test**: run the script twice on one day → byte-identical;
against a deliberately altered response → writes nothing.

- [x] T008 [US3] Write `tests/unit/test_fetch_nbu_rates.py` against a script that does not exist yet (it fails with `ImportError`, which counts): constructed responses only, every rate in them invented and the module docstring saying so (research D8).
- [x] T009 [US3] In that module, assert **determinism**: `render` over one response and one date is byte-identical across two calls, and takes no clock and no disk (SC-004).
- [x] T010 [US3] In that module, assert the **refusals**, each naming what surprised it and each leaving an existing file byte-identical: a row whose `units` differs from the declared `quotation_unit` (naming the date, the published unit and the declared one); a range shorter than the required window; a missing calendar day inside it; an unrecognised or missing field; a row for another currency (SC-005, FR-004, FR-008).
- [x] T011 [US3] In that module, assert the **day-ahead drop**: given a response carrying a row dated after the retrieval date, the row is dropped and named, and the rendered file's last observation is the retrieval date (SC-020, FR-010).
- [x] T012 [US3] In that module, assert **`verified_on` handling**: every rendered row carries a present, empty `verified_on` when nothing was verified before (FR-005); a hand-filled `verified_on` survives a re-render whose value for that date is unchanged; and it is **cleared** when the value has changed (SC-007, FR-006).
- [x] T013 [US3] Write `scripts/fetch_nbu_rates.py` (FR-001–FR-005, FR-008–FR-010, FR-024, FR-025): `fetch(*, today)` requesting `START .. today + 1 day`; shape validation and refusals; `render(fetched, *, verified)` pure; atomic `_write`; `main` reading the clock once, reading the existing file for carry-forward, `--dry-run` and `--out`.
- [x] T014 [US3] Make the generated header carry FR-024's four statements and FR-025's two provisions, distinguishing the term on a reuser (ст. 10¹ ч. 2 абз. 2 ЗУ № 2939-VI) from the notice on the publisher (п. 17 Положення № 835), plus the two arguments that survive from the current file: a date outside the window refuses rather than being interpolated, and why *"the latest observation on or before"* is refused.

**Checkpoint**: `uv run pytest tests/unit/test_fetch_nbu_rates.py` green with no network. Commit.

## Phase 4: User Story 1 — a dollar credit gets a hryvnia base from a published rate (P1)

**Independent test**: pick a date inside the window, read the National Bank's published rate for
it by hand, check the engine's base against hand arithmetic on that figure.

- [x] T015 [US1] Write `tests/worked_examples/test_nbu_official_rate_base.py` — SC-001: a dollar amount on a date inside the covered window strikes a hryvnia base equal to `amount × rate ÷ quotation_unit` within the single imported tolerance, with the arithmetic checked in beside the assertion and the rate **read from the declaration**, never restated as a literal (spec.md, Assumptions).
- [x] T016 [US1] In that module, assert SC-002: the same dollar credit charged under `ua_fop_group_3_non_vat` and under `ua_personal_income` produces two charges on **one** hryvnia base, and the comparison is answerable — a test that on `main` before this feature refuses with `OfficialRateUndeclaredOnDate`.
- [x] T017 [US1] Run the retrieval for real: `uv run python scripts/fetch_nbu_rates.py`, then read the diff. Confirm the row count against the span, the first date, the last date and the unit.
- [x] T018 [US1] Write `tests/contract/test_nbu_series_is_declared.py` asserting the landed file's invariants mechanically over **every** row: one observation per calendar day with zero missing and no `non_publication_rule` (SC-017); a non-empty `source` naming the endpoint, its query and the row's stated `units`, a `retrieved_on`, and a present, empty `verified_on`, on 100% of rows (SC-006); the retrieval URL present on 100% of rows and both provisions named in the header (SC-019); and no row dated after its own `retrieved_on` (SC-020's first clause).

**Checkpoint**: the data is in and re-derivable by hand. Commit.

## Phase 5: User Story 2 — a date outside the covered window refuses by name (P1)

**Independent test**: ask for a base before the first observation, after the last, and on a
declared instrument's own 2029 payment date; all three refuse naming the window, and no flag
returns a figure.

- [x] T019 [US2] Extend `tests/contract/test_nbu_series_is_declared.py` with the uncovered-date battery (SC-003): 100% refuse naming the series, the pair, the date and the covered window; 0% produce a number; the window sentence states **real dates**, not *"declares no observation at all"* (FR-012).
- [x] T020 [US2] Rework `TestTheShippedUkrainianSeries` in `tests/contract/test_official_rate_declaration_loading.py`: the base-struck test now asserts a struck base inside the window and a refusal outside it, and the no-rule test's docstring reason becomes FR-013's publication fact rather than the calendar argument, which stopped being the reason.

## Phase 6: User Story 4 — populating the series moves nothing outside the tax path (P1)

**Independent test**: run every golden before and after; only the rate file's own input digest may
move.

- [x] T021 [US4] Assert SC-010 mechanically in `tests/contract/test_the_rate_you_are_taxed_at.py`: `data/channels/uah_usd.toml` is absent from this feature's diff and its `reference_rate` values still read `42.0` and still carry the synthetic-fixture marking (FR-018).
- [x] T022 [US4] Regenerate the goldens deliberately (`TEREZY_UPDATE_GOLDEN=1`), read the diff, and confirm SC-009: every cost, route, leg, channel and ranking digest is bit-identical; the only movement is the input line FR-020 adds. **If a result line moves, stop and report.**
- [x] T023 [US4] Confirm SC-011: both `.importlinter` contracts and `tests/contract/test_the_rate_you_are_taxed_at.py` still pass over a series that now carries values, unchanged.
- [x] T024 [US4] Confirm SC-008 and FR-019: bases and charges struck from the landed observations carry the unverified mark and propagate it, and `RateNotComparable`, `ForeignGainNotStruckPerDate` and `TaxCurrencyConversionUnavailable` still refuse.

## Phase 7: Polish & cross-cutting

- [x] T025 [P] Update `docs/METHODOLOGY.md` in the same change as the data (SC-015): the covered window, the lower bound's reason (the publisher's own `units` change), and what falls outside it.
- [x] T026 [P] Update `docs/REQUIRED_TESTS.md` notes for F1, F2 and F3 without flipping a box (SC-016).
- [x] T027 [P] Correct the claims that stop being true: `data/tax/timing/ua.toml`'s "declares no observation yet", and the docstring in `tests/worked_examples/test_base_versus_received.py` that says the shipped series is empty (research D9).
- [ ] T028 Run every gate by exit code, `/condense`, then `/code-review`, and iterate until clean.

## What the run changed about the order above

**Phase 2's manifest task moved after the data.** `official_rate_input_refs` reports the
unverified sources of every observation, and the manifest suite asserts that every cited input
reports some -- which an empty series cannot. Landing T004/T005 before the data would have meant
committing a red gate, so they landed with the golden instead. The lookup (T002/T003) and the
provenance gate (T006/T007) were unaffected and landed first as written.

## Dependencies

```text
Phase 1  →  Phase 2  →  Phase 3 (US3)  →  Phase 4 (US1)  →  Phase 5 (US2)
                                       ↘                 ↗
                                          Phase 6 (US4)   →  Phase 7
```

US3 blocks US1 because the data cannot exist before the script that retrieves it. US2, US4 and
Phase 7 depend on the data being in. Within Phase 2, T002/T004/T006 are parallel (three files,
no shared state), and each unblocks its implementation task.

## Parallel opportunities

- T002 ∥ T004 ∥ T006 (three test files, three different modules under test).
- T025 ∥ T026 ∥ T027 (three documents, no shared claim).

## MVP scope

Phases 2–4: the three shipped-code fixes, the script, and the data with its worked example. That
is the point at which 012's 6%-versus-23% comparison runs on a real dollar amount. Phases 5–7 are
the discipline that keeps it honest and are not optional for landing.
