# Implementation Plan: The OVDP hurdle rate

**Feature**: `001-ovdp-hurdle-rate` | **Date**: 2026-08-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-ovdp-hurdle-rate/spec.md`

**Branch**: none — this repo works on `main` by design (no feature branches)

## Summary

Build the smallest thing that produces the project's benchmark number — the after-tax
return of an OVDP held to maturity — and in doing so establish the four foundations
everything later depends on: currency-tagged money with automatic provenance
propagation, an event-sourced ledger with per-lot basis, declared instruments and tax
classes loaded from data, and one project-wide tolerance.

The technical shape, decided in [research.md](./research.md): the instrument computes its
contractual schedule in closed form, the engine applies that schedule as ledger events,
and every reported figure derives from the ledger. Provenance rides inside `Money` and is
unioned by the one `money.add`, so losing an unverified mark is structurally impossible
rather than a discipline. Validation is pydantic in the `data` layer with coercion and
defaults turned off; the core stays plain frozen records.

Everything is written as **free functions over immutable records** — no classes with
behaviour, no inheritance, no ABCs, no `Protocol` classes, no operator dunders (owner
decision D-E, added to the constitution as v1.1.0 while this plan was being written).
Plugin interfaces are function signatures gathered into frozen records; dispatch is a
`dict`. See research.md D7 for what that changed and what it did not.

## Technical Context

**Language/Version**: Python 3.13 (`.python-version`); CI matrix 3.12 / 3.13 / 3.14

**Primary Dependencies**: none new. `pydantic` (already present) for declaration
validation in `data` only. `numpy`/`pandas`/`scipy` are **not** used by this feature —
the arithmetic is tens of values in plain Python, and pulling in an array library here
would put a BLAS reduction between the inputs and the determinism digest for no benefit.

**Storage**: version-controlled TOML under `data/instruments/` and `data/tax/`. No
database, no cache, no network. Per-user data does not exist yet.

**Testing**: pytest; Hypothesis for the invariant suite; hand-computed worked examples
with their arithmetic checked in. Markers `worked_example`, `invariant`, `contract`.
Network is blocked by `tests/conftest.py`.

**Target Platform**: library only. No API, no CLI, no UI in this feature.

**Project Type**: single Python library, src layout, layered `cli → api → data → core`.

**Performance Goals**: none. A coupon schedule is tens of rows. Correctness and
traceability are the only goals; the vectorized fast path is a later feature and is
explicitly not designed for here.

**Constraints**: core is pure and deterministic (no I/O, network, logging, formatting,
`random`, `datetime.now`); money is float64 with one imported tolerance; exactly four
plugin interfaces project-wide, of which this feature implements two.

**Scale/Scope**: ~10 new core modules, ~4 data-layer modules, 2–3 declaration files,
9 test modules covering 10 rows of `docs/REQUIRED_TESTS.md`.

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design.*

| Principle | Gate | Verdict |
|---|---|---|
| **I — Honesty over precision** | No point estimate more confident than inputs; unverified marks propagate; no statistical metric for assumption-driven instruments | **PASS.** The return figure is contractual, not estimated, so a point estimate is legitimate here. It is labelled nominal (FR-022) and carries the unverified mark from the yield. No volatility or Sharpe is emitted — none is computed. |
| **II — Framework, not script** | New instrument / venue / tax regime / jurisdiction is data-only; exactly four plugin interfaces | **PASS.** Implements `Instrument` and `TaxRule`; no fifth interface. SC-003 and SC-012 are executable tests of data-only extensibility. Day-count *algorithms* are code — justified in research.md, since a convention is none of the four data categories. |
| **III — Pure deterministic core** | No I/O in core; seeds recorded; every figure traceable; run manifest | **PASS.** Loader, pydantic and the digest all live in `data`. The canonical functions in core are structural only. No randomness exists in this feature, so there is no seed to record; the manifest records inputs and versions. **Done:** `hashlib`, `pydantic` and `abc` were added to core's forbidden modules in `.importlinter`. |
| **IV — Reliability through contracts** | Invariants are property-based; float64 money currency-tagged; one tolerance; explicit failure; no synthetic cache | **PASS.** C1–C6 are Hypothesis suites. One `TOLERANCE` in `core/primitives/tolerance.py`, imported everywhere. Domain failures are a tagged union; `raise` is reserved for programmer errors such as a currency mismatch. No cache exists yet. |
| **V — Test-first for financial logic** | Every financial behaviour lands with a worked example, an invariant, or a golden file; tests never reach the network | **PASS.** D1 and D2 are hand-computed with arithmetic checked in; C1–C6 are property-based; the network guard is already in place and tested. Tests are written before the code they cover. |
| **VI — Model the whole tuple** | Access cost never per-instrument; round-trip not one-way; three currency roles kept distinct | **PASS, with a boundary to hold.** This slice models `(instrument × tax)` only; routes, streams and exit are out of scope per the spec. The result type must therefore **not** be named or shaped as if it were route-adjusted — see the risk register below. Only one currency is in play, but currency tagging is built now. |
| **Engineering Standards — functional style (D-E)** | Free functions over immutable records; no inheritance, ABCs or `Protocol` methods; tagged unions; function registries | **PASS.** Enforced mechanically by `abc` in the core's forbidden imports, and by review for the rest. |
| **VII — Owner-scoped and private** | `owner_id` from day one; curated vs per-user data separated; no telemetry | **PASS.** The holding and run records carry `owner_id` even though there is one owner and no auth. Curated data is under `data/`; `data/user/` stays gitignored and unused. No new dependency phones home. |

**No violations requiring justification.** One item of genuine added complexity is
recorded in Complexity Tracking below.

### Post-Phase-1 re-evaluation

Re-checked after the design artifacts were written. No verdict changed. Two things the
design surfaced that the pre-check had not made explicit:

- **The canonical form must not include provenance.** Provenance identifies *sources*,
  and if a source's `verified_on` is filled in later, the digest would change even though
  no computed amount did — making C4 fail on a documentation update. The digest covers
  amounts, currencies, dates, kinds and identifiers only; the unverified *mark* is
  asserted separately by E5.
- **Excluding provenance from `Money` equality is load-bearing**, not a convenience.
  Without it, two amounts equal in value but reached by different paths would compare
  unequal, and the invariant suites would fail for reasons unrelated to conservation.
- **The functional style removed a guard and added one.** Dropping operator dunders means
  provenance union now lives in one named function instead of several — easier to review.
  But `Money(...)` remains constructible anywhere, so a test scans for direct
  construction outside `money.py` and the loader.

## Project Structure

### Documentation (this feature)

```text
specs/001-ovdp-hurdle-rate/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file
├── research.md          # Phase 0 — seven decisions with rationale
├── data-model.md        # Phase 1 — entities, fields, validation rules
├── quickstart.md        # Phase 1 — how to verify the feature works
├── contracts/
│   ├── instrument-interface.md   # The Instrument plugin contract
│   ├── taxrule-interface.md      # The TaxRule plugin contract
│   └── declaration-schema.md     # The TOML shapes and their rules
├── checklists/
│   └── requirements.md  # Spec quality checklist (16/16 passing)
└── tasks.md             # Phase 2 — created by /speckit-tasks, not here
```

### Source code (repository root)

```text
src/terezy/core/                        pure, deterministic
├── errors.py                           typed failures carrying reasons
├── primitives/
│   ├── currency.py                     Currency
│   ├── provenance.py                   SourceRef, Provenance (frozenset monoid)
│   ├── money.py                        Money — float64, currency-tagged, provenance-carrying
│   ├── tolerance.py                    THE tolerance constant + comparison helpers
│   ├── rates.py                        NominalRate, RealRate, RealTermsUnavailable
│   └── conventions.py                  day-count, periodicity, business-day registries
├── ledger/
│   ├── events.py                       typed event stream
│   ├── lots.py                         Lot, Position
│   ├── accounts.py                     CashAccount, per-currency balances
│   ├── engine.py                       fold events -> state
│   └── canonical.py                    of_event / of_result — structural, no serialisation
├── instruments/
│   ├── interface.py                    EventsFn signatures, InstrumentOps record, REGISTRY
│   └── fixed_income.py                 free functions + OPS: closed-form bond schedule
├── tax/
│   ├── interface.py                    ChargeFn signature, TaxRuleOps record, REGISTRY
│   └── flat_rate.py                    free functions + OPS: apply declared rates
└── results/
    ├── schedule.py                     CashFlowSchedule
    └── hurdle.py                       HurdleRate — nominal + typed-empty real slot

src/terezy/data/
├── declarations/
│   ├── schema.py                       pydantic models: extra=forbid, strict, no defaults
│   ├── loader.py                       tomllib -> validate -> construct core types
│   ├── resolver.py                     cross-file: duplicate ids, undeclared tax refs
│   └── errors.py                       DeclarationError carrying file + field path
└── manifest.py                         run manifest + SHA-256 digest (hashlib lives here)

data/
├── instruments/
│   ├── ovdp_synthetic_a.toml           labelled synthetic fixture for D1/D2
│   └── ovdp_synthetic_b.toml           different conventions — proves SC-012
└── tax/
    └── ua.toml                         ua_government_bond, exempt, cited

tests/
├── worked_examples/
│   ├── test_ovdp_schedule.py           D1 — schedule to maturity, zero tax
│   └── test_coupon_reinvestment.py     D2 — two-period reinvestment
├── invariants/
│   ├── test_ledger_conservation.py     C1, C2, C3
│   ├── test_determinism.py             C4
│   ├── test_currency_safety.py         C5
│   └── test_traceability.py            C6
├── contract/
│   ├── test_declaration_loading.py     H2 — loud, field-naming failures
│   ├── test_data_only_extensibility.py SC-003, SC-012
│   └── test_provenance_propagation.py  E5, FR-015
└── unit/                               focused tests for conventions, money, rates
```

**Structure Decision**: single project, src layout, using the layered directories already
established in the foundation commit. The feature adds nothing to `api/` or `cli/` —
they stay empty, matching the spec's Out of scope and owner decision D-B (defer the
delivery surface until the result schema stabilises).

The one structural choice worth naming is the `core/primitives/` package. `Money`,
`Provenance` and `TOLERANCE` are imported by every other core package, so they need a
home that cannot import from its siblings — otherwise the first circular import appears
the moment the tax engine needs money and money needs a rate. `primitives` depends on
nothing but the standard library.

## Implementation sequence

Ordered so that each step is independently testable and nothing is written before the
test that would fail without it (Principle V).

| # | Step | Closes | Depends on |
|---|---|---|---|
| 1 | `primitives`: currency, provenance, money (free fns), tolerance, rates | C5, part of E5 | — |
| 2 | `conventions`: day-count, periodicity, business-day registries, unknown-name failure | part of FR-021 | 1 |
| 3 | `ledger`: events, lots, accounts, fold engine, canonical fns | C1, C2, C3, C6 | 1 |
| 4 | `instruments`: signatures, registry + closed-form bond schedule | part of D1 | 1, 2 |
| 5 | `tax`: signature, registry + declared-rate application | part of D1 | 1, 3 |
| 6 | `results`: schedule, `HurdleRate` with typed-empty real slot | SC-011 | 1, 4, 5 |
| 7 | `data.declarations`: schema, loader, resolver, errors | H2 | 1–6 |
| 8 | declaration files: two synthetic issues + the UA tax pack | SC-012 | 7 |
| 9 | `data.manifest`: digest over the canonical form | C4, SC-006 | 3, 7 |
| 10 | end-to-end wiring + the D1 and D2 worked examples | D1, D2 | all |
| 11 | flip the ten rows in `docs/REQUIRED_TESTS.md`, record test paths | — | all |

Steps 1–3 are the foundation and are worth landing as one green checkpoint before
anything else starts. Steps 4–6 and 7–8 are largely parallelisable.

## Risk register

Things most likely to go wrong, and what catches them.

| Risk | Why it matters here | Guard |
|---|---|---|
| A transform drops the unverified mark | FR-015 calls this top-severity; it makes an unverified figure look verified | Provenance unions inside the `money` module's combining functions (D2), so it cannot be forgotten. A test also scans for direct `Money(` construction outside `money.py` and the loader. **Plus manual review** — the gates cannot see this. |
| A test invents its own tolerance | Defeats FR-002; each drift is invisible alone | One `TOLERANCE` export; review any `pytest.approx`/`abs(... ) <` in a diff |
| The result gets read as route-adjusted | Principle VI forbids per-instrument access cost; a later reader could compare this figure against a route-adjusted one | Name the type `HurdleRate` and carry an explicit field stating route costs are excluded. Revisit when routes land. |
| pydantic coerces or defaults something | Would violate FR-016 silently | `strict=True`, `extra="forbid"`, zero defaults, and `test_declaration_loading.py` feeds a battery of broken files |
| Determinism hides inside the tolerance | A real nondeterminism could pass C4 | Digest uses `float.hex()` — bit-identity, deliberately stricter than the tolerance (D5) |
| Coverage floor gamed by testing trivia | 90% is blocking and easy to satisfy dishonestly | Coverage is necessary, not sufficient; the ten required-test rows are the real gate |

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| `Money` carries provenance, making the most-used record in the system heavier than a plain `(amount, currency)` pair | FR-015 names a dropped provenance mark as a defect of the highest severity, and this work is being delegated to subagents. Automatic union inside the one combining function is the only mechanism that does not depend on every future contributor remembering | Provenance on schedule rows, or a `Sourced[T]` wrapper, both leave aggregation as a manual step where the mark is silently lost — the exact defect. A run-scoped taint flag is unfalsifiable but useless, since it cannot say *which* figure is affected |
| A `core/primitives/` package rather than flat modules | `Money`, `Provenance` and `TOLERANCE` are imported by every core package; they need a leaf with no sibling imports | Flat modules produce a circular import as soon as tax needs money and money needs a rate |
| Exhaustive `match` with an unreachable `case _:` at every dispatch over a failure union | Adding a variant then produces a type error at every site that must handle it | A base class with a default would silently absorb the new variant — the exact silent-default failure mode FR-016 exists to prevent |

## Changes made outside this feature while planning

Two, both recorded rather than slipped in:

1. **`.importlinter` tightened.** `hashlib` and `pydantic` added to the core's forbidden
   imports (hashing implies serialisation; validation belongs at the boundary), and `abc`
   added as the mechanical guard for D-E. All four contracts still pass.
2. **Constitution 1.0.0 → 1.1.0.** A functional-style clause was added to Engineering
   Standards as owner decision D-E, and Principle IV's "currency-tagged value object" was
   reworded to "currency-tagged immutable record" so the document does not contradict
   itself. MINOR: guidance added, no principle removed or redefined.
