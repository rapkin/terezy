# Implementation Plan: An instrument declared as the payments it will make

**Feature**: `013-enumerated-schedule` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)

**Branch**: `feat/013-enumerated-schedule`, landing on `main` by a `--no-ff` merge after a
clean review pass.

## Summary

An instrument declaration describes a bond generatively and the engine derives the schedule.
The 32 real ОВДП issues in `data/observations/inzhur.toml` are the opposite: a list of dated
payments, no coupon rate, and **no issue date**. This feature adds the enumerated form so
that those issues can be declared without inventing the one fact that is not derivable.

The shape, decided in [research.md](./research.md): **one declaration record, two `terms`
records, one registry, three questions**. `InstrumentDeclaration.terms` becomes
`BondTerms | EnumeratedTerms`; `[instrument] class` selects the form as it already selects
everything else; and the three sites that read a generative field today ask the terms a
question both forms answer instead of reading a field only one has.

**The delegation is the whole design, not a refactoring detail.** FR-011a's observation is
that `seeds.py` never needed an issue date — it needed *the earliest date from which this
instrument's terms are known*, and it asked for the only spelling that existed. Once the
question is asked in those words, both forms answer it and the site gains an answer rather
than a case. The same move covers the day count (`tuple_outcome`) and the conventions
statement (`project.py`). That is what makes SC-003's scan passable: no module under the
ledger, the tax engine, the decision layer or the results ever learns that a second form
exists.

**Where this feature can be wrong.** Not in the schedule arithmetic — there is none; the
amounts are declared. It can be wrong in exactly two places:

1. **The day count reaching an amount.** FR-003a lets the enumerated form carry a day count
   because the yield cannot be annualised without one. FR-003b forbids it being an input to
   any derived amount, date, schedule, accrual period **or coupon rate** — the last one
   because *day count + one coupon amount + the interval ⇒ a coupon rate ⇒ an extrapolated
   issue date*, which is the invented legal fact this whole feature exists to refuse,
   reached in two steps from a required field. FR-003c refuses to let FR-003b believe itself
   sufficient. SC-020 is the mechanical lock: change the declared day count in a copy of a
   declaration, the yield moves, **every cash-flow amount stays bit-identical**.
2. **A form test spelled without the form's name.** SC-003 records its own limit honestly: a
   name scan catches `isinstance(...)` and `case EnumeratedTerms()` because those name the
   type, and does not catch `terms.schedule is not None`, a bare `case _:` pair, or
   `if decl.form != "generative"`. None of the three is written; the design that makes them
   unnecessary is D2's four questions.

## Technical Context

**Language/Version**: Python 3.13; CI matrix 3.12 / 3.13 / 3.14.

**Primary Dependencies**: none new.

**Storage**: version-controlled TOML. Four new synthetic declaration files, two new synthetic
tax classes and one new synthetic timing file. **No real ОВДП issue is wired in** — the spec
puts that out of scope; it is what this feature makes possible, not what it does.

**Testing**: pytest. Hand-computed worked examples for the schedule and the premium; a
field-by-field tuple comparison for SC-002; four source-tree scans; the existing goldens as
regressions plus a new enumerated golden.

**Target Platform**: library only. No API, no CLI.

**Project Type**: single Python library, `cli → api → data → core`.

**Constraints**: core pure, no clock; exactly four plugin interfaces and **this feature adds
none**; functional style per D-E; one imported tolerance; provenance propagates from every
declared payment to every figure.

**Scale/Scope**: 2 new core modules, 1 record moved, 3 call sites delegated, 3 docstrings
corrected, 1 gate extended, ~14 test modules, 7 new/edited data files.

## Constitution Check

| Principle | Verdict |
|---|---|
| **I — Honesty over precision** | **PASS, and this feature is that principle applied to a date.** The enumerated form exists so that no figure rests on an extrapolated issue date. Every inferred value — face, kind, kopeck scaling, coverage — is declared as an inference with an empty `verified_on`, and the mark propagates (SC-012). What the form cannot answer refuses in a typed value rather than being computed around (FR-014, FR-015). |
| **II — Framework, not script** | **PASS.** A second declaration *kind* under the existing `Instrument` interface: same signature, same return type, the existing failure union unchanged (FR-013). No fifth plugin interface, no amendment. SC-004 proves a third enumerated instrument is data only. |
| **III — Pure deterministic core** | **PASS.** No clock, no I/O. Every date is declared or passed. |
| **IV — Reliability through contracts** | **PASS.** Every refusal is a typed member of the existing union carrying its reason (FR-019, SC-024). The tolerance is imported; SC-002 states at the assertion site why tolerance rather than bit-equality (the two forms reach the same amount by different arithmetic). |
| **V — Test-first** | **PASS.** Every module lands after a test that fails without it, `ImportError` counted. **And the golden rule is applied in the direction 1.2.0 wrote it**: D9 moves two recorded digests deliberately rather than shaping the design around not disturbing them. |
| **VI — Model the whole tuple** | **PASS.** SC-002 is a full-tuple comparison; the enumerated form changes no term of the tuple but the instrument. |
| **Engineering Standards — D-E** | **PASS.** Frozen records, free functions, tagged unions matched with `match`. The one `match` on the form is `core/instruments/terms.py`, and that is the point. |
| **VII — Owner-scoped and private** | **PASS.** No per-owner data. Every fixture is synthetic and says so. |

### Post-Phase-1 re-evaluation

Three things the design surfaced, each recorded because it will be tempting to undo:

- **FR-025's figure cannot both exist and leave the goldens alone.** D9 chooses the figure
  and regenerates. Reported as the feature's principal finding against the spec, because
  SC-017's reasoning is right and its conclusion does not follow.
- **`core/results/*` may not contain the word.** FR-012 forbids naming the form, and prose
  is naming. So no docstring in `project.py`, `schedule.py`, `canonical.py`, `hurdle.py` or
  `tuple.py` may explain itself by saying "for an enumerated instrument". Each says what it
  does instead, which is the better sentence anyway — and it is asserted by SC-003's scan
  rather than by a reviewer noticing.
- **The provenance gate now knows a declaration kind.** `check_provenance.py` has been
  shape-driven until now (a table with a numeric leaf needs a citation). FR-022 asks it to
  check a *relation* — that an inferred value has a verification task. That is a real
  widening of the gate's job and it is worth naming rather than sliding in.

## A boundary this feature must not cross

**The 32 real issues stay out.** `data/instruments/` gains synthetic fixtures only. Every
count this specification quotes is a measurement over `data/observations/inzhur.toml`, and
that file is an observation with every `verified_on` empty by construction. Declaring a real
ОВДП needs the owner's verification tasks answered (face value, kopeck scaling, coverage per
issue, the coupon/principal reading) and is a later data change.

**No accrued-interest figure appears.** FR-017 is a prohibition, not a refusal: nothing in
the engine computes accrued interest today, so a typed refusal for it would be dead code.
SC-023 walks every result record and proves the absence.

## Project Structure

### Documentation (this feature)

```text
specs/013-enumerated-schedule/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── the-enumerated-form.md
└── tasks.md
```

### Source code

```text
src/terezy/core/
├── primitives/conventions.py        ConventionsApplied moves here; AmountsAsDeclared added
├── instruments/
│   ├── interface.py                 EnumeratedTerms, ScheduledPayment, PaymentKind;
│   │                                InstrumentDeclaration.terms becomes a union
│   ├── enumerated.py                NEW — events / tax_classes / constraints
│   ├── terms.py                     NEW — the four questions both forms answer
│   └── registry.py                  a second entry
├── ledger/seeds.py                  asks known_from
├── decision/tuple_outcome.py        asks day_count_of; one docstring corrected
└── results/
    ├── schedule.py                  row typed on the union; one docstring corrected
    ├── canonical.py                 of_conventions matches; of_projection gains the premium
    ├── hurdle.py                    of_flows takes excludes; the "Three items" count fixed
    └── project.py                   asks conventions_of, day_count_of, excludes_of;
                                     builds PurchasePremium

src/terezy/data/declarations/
├── schema.py                        EnumeratedInstrumentFile and its tables
├── loader.py                        enumerated_instrument_from_file
└── resolver.py                      dispatch on the declared class

scripts/check_provenance.py          the inference checks (FR-022)

data/
├── instruments/ovdp_enumerated_a.toml        SC-001's hand-sized schedule
├── instruments/ovdp_enumerated_mirror.toml   SC-002's mirror of ovdp_synthetic_a
├── instruments/enumerated_taxable_x.toml     FR-010 / FR-026's two-rate fixture
├── instruments/enumerated_out_of_order.toml  SC-018's transcription record
├── tax/synthetic_fixture.toml                two new classes at different rates
└── tax/timing/synthetic_fixture.toml         NEW — one netting category, one per-event
```

### Tests

```text
tests/worked_examples/test_enumerated_schedule.py        SC-001
tests/worked_examples/test_enumerated_premium.py         SC-016
tests/unit/test_enumerated_refusals.py                   SC-008, SC-009, SC-024
tests/unit/test_enumerated_yield.py                      SC-011, SC-015
tests/unit/test_payment_label_is_load_bearing.py         SC-005
tests/unit/test_seed_lot_before_coverage.py              SC-008, SC-022
tests/contract/test_enumerated_declaration_loading.py    SC-006, SC-019, SC-021
tests/contract/test_enumerated_data_only.py              SC-004
tests/contract/test_no_layer_knows_the_form.py           SC-003
tests/contract/test_nothing_is_inferred.py               SC-014
tests/contract/test_day_count_reaches_no_amount.py       SC-020
tests/contract/test_no_accrued_interest.py               SC-023
tests/contract/test_provenance_gate.py                   SC-013 (extended)
tests/golden/test_enumerated_matches_generative.py       SC-002, SC-010, SC-017
```

## Phasing

Six phases, each a green checkpoint and a commit.

1. **The vocabulary.** `PaymentKind`, `ScheduledPayment`, `EnumeratedTerms`, the union on
   `terms`, `AmountsAsDeclared`, and the move of `ConventionsApplied` into `primitives`.
   Ends with mypy listing every site that reads a generative field — which is FR-002's
   promise, verified rather than asserted.
2. **The delegation.** `core/instruments/terms.py` and the three call sites, plus the three
   false docstrings and `hurdle.py`'s "Three items". Nothing new is projectable yet; the
   generative suite is the regression, and SC-017's half about worked examples holds from
   here.
3. **The instrument.** `core/instruments/enumerated.py`, the registry entry, the refusals.
4. **The data boundary.** Schema, loader, resolver, the fixtures, the provenance gate.
5. **The figures.** `PurchasePremium`, per-declaration exclusions, the goldens regenerated.
6. **The scans and the documentation.** SC-003, SC-014, SC-020, SC-023,
   `docs/METHODOLOGY.md`, and the two `docs/REQUIRED_TESTS.md` rows that are *touched and
   not claimed* (H1 and D1).

## Complexity Tracking

| Departure | Why | Simpler alternative rejected because |
|---|---|---|
| `ConventionsApplied` moves out of `core/results/schedule.py` | The declaration must be able to build the answer, so the type must sit below both `core/instruments/` and `core/results/` | Leaving it put makes an *instrument* module import a *result* module — allowed by `.importlinter`, wrong by every other reading of this codebase |
| `Projection` gains a required field and two goldens move | FR-025 asks for a named figure and FR-026 asks for its treatment to be asserted | An optional field present only where there is a premium makes "no figure" mean "bought at par", which is a silent default |
| `check_provenance.py` learns a declaration kind | FR-022 asks it to check a relation, not a shape | A test instead of a gate: the gate must be runnable by a non-developer maintaining a declaration by hand, which is its stated reason for not being a test |
