# Implementation Plan: The NBU rate series — filling a declared, empty series

**Feature**: `018-nbu-rate-series` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Branch**: `feat/018-nbu-rates`, landing on `main` by a `--no-ff` merge after a clean review.

## Summary

`data/official_rates/ua_nbu_usd.toml` has declared an identity and no observations since 011,
so every tax figure struck from a foreign amount refuses. This feature retrieves the National
Bank's published USD rates for **2019-12-28 .. the retrieval date** and declares them, through a
repository script that fetches, cites, and never verifies.

Four things travel with the data because the data is what makes them matter:

- **a fetch script** (`scripts/fetch_nbu_rates.py`) that reads the publisher's own `units` and
  **refuses** a mismatch rather than normalising (FR-008), stops at its own retrieval date
  (FR-010), writes atomically, and preserves a hand-filled `verified_on` only while the value it
  attested to is unchanged (FR-006);
- **a lookup that does not rebuild a dict per call** — `observation_for` bisects
  ([research D5](./research.md)), a defect zero rows have been hiding (FR-022);
- **a manifest entry** — `InputKind` is a closed `Literal` with no official-rate member, so no
  run can name the series a tax base rested on (FR-020);
- **a gate that stays legible** — `check_provenance.py` summarises unverified values per file
  rather than emitting ~3,140 lines (FR-023).

What it does **not** do is give anything outside the tax path a rate. A real official rate now
sits one directory from `data/channels/uah_usd.toml`'s invented `reference_rate = 42.0`, and
FR-018/SC-010 keep it invented: the diff must not touch that file.

## Technical Context

**Language/Version**: Python 3.12+. **Primary dependencies**: none new (`urllib`, `tomllib`).

**Storage**: version-controlled TOML. One file rewritten:
`data/official_rates/ua_nbu_usd.toml`, ~2,439 observations, self-citing per row
(spec.md, "The volume, and why the container does not change").

**Testing**: pytest. Hand-computed base against the shipped series (SC-001); the two shipped
schemes on one base (SC-002); an uncovered-date battery (SC-003); the script's determinism,
refusals and day-ahead drop against **constructed** responses (SC-004, SC-005, SC-020); a
mechanical sweep of every landed observation's citation (SC-006, SC-019); verification
carry-forward and clearing (SC-007); the manifest entry (SC-012); the lookup's shape (SC-013);
the gate's output (SC-014); the calendar-completeness count (SC-017).

**Network**: the script only, run by an operator. Tests never reach it (`tests/conftest.py`).

**Constraints**: core pure, no clock, no I/O; no fifth plugin interface; frozen records and free
functions; the single imported tolerance; the three currency roles kept apart.

## Constitution Check

| Principle | How this feature meets it |
|---|---|
| I — honesty over precision | Every observation carries the retrieval URL, the publisher's `units` and `calcdate`, and an **empty** `verified_on` (FR-005). No value originates from memory: each one is in the response D1 quotes the command for. A unit mismatch **refuses** rather than normalises. |
| II — framework not script | No engine branch is added. The change to `core/` is one lookup's algorithm; everything else is data, a script outside the package, and a manifest kind. |
| III — pure deterministic core | The script lives in `scripts/`, reads the clock **once** in `main`, and its `render` is a pure function of a response and a date. FR-020 closes the reproducibility hole the manifest had. |
| IV — stated contracts | Failure is explicit throughout: the script writes nothing on any surprise, and every uncovered date returns `OfficialRateUndeclaredOnDate` rather than a number. |
| V — test-first | Every requirement below lands with its test written first. The goldens move deliberately and the moved lines are quoted in the commit message. |
| VI — the whole tuple | FR-016 through FR-019 are the tax/display/base separation, asserted over the goldens and the two `.importlinter` contracts rather than argued. |
| VII — owner-scoped and private | `bank.gov.ua` is the publisher of the data being read; nothing is sent but the query. No new dependency. |

**Prose discipline (1.3.0).** The generated header is data, not source, and is exempt from the
`check_prose_budget.py` ratchet — which measures `*.py` only. What the ratchet *will* see is the
script and its tests, so the script carries the arguments a reader could not infer (why a
mismatch refuses, why the requested window is a day wider) and states nothing the code says.

**No violations to justify.** The Complexity Tracking table is empty.

## Project Structure

```text
specs/018-nbu-rate-series/
├── spec.md
├── plan.md            (this file)
├── research.md        D1–D9, each retrieval with its command
├── data-model.md      what changes shape, and what deliberately does not
├── quickstart.md      how to re-run the retrieval and check one row by hand
└── tasks.md           (/speckit-tasks)
```

### Source

```text
scripts/
├── fetch_nbu_rates.py                  NEW — retrieve, refuse, declare
└── check_provenance.py                 per-file unverified summary (FR-023)

src/terezy/
├── core/tax/official_rate.py           observation_for bisects (FR-022)
└── data/manifest.py                    InputKind + official_rate_input_refs (FR-020)

data/
├── official_rates/ua_nbu_usd.toml      GENERATED — ~2,439 observations
└── tax/timing/ua.toml                  a claim about the series that stops being true

tests/
├── worked_examples/test_nbu_official_rate_base.py     NEW — SC-001, SC-002
├── unit/test_fetch_nbu_rates.py                       NEW — SC-004, SC-005, SC-007, SC-020
├── contract/test_nbu_series_is_declared.py            NEW — SC-003, SC-006, SC-017, SC-019
├── contract/test_official_rate_declaration_loading.py the shipped-series battery
├── contract/test_provenance_gate.py                   SC-014
├── unit/test_official_rate_rule.py                    SC-013
├── unit/test_run_manifest.py (or nearest)             SC-012
├── golden/test_end_to_end_ovdp.py + its artefact       the input line FR-020 adds
└── worked_examples/test_base_versus_received.py        a docstring that stops being true

docs/
├── METHODOLOGY.md      the covered window, its lower bound's reason, what falls outside
└── REQUIRED_TESTS.md   F1/F2/F3 notes only — no row flips (SC-016)
```

**Structure Decision**: no new package, no new layer, no new directory. The one new runtime
module is a script, which is where network access already lives.

## Complexity Tracking

None.
