# Implementation Plan: The official rate and the tax-currency role

**Feature**: `011-official-rate` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)

**Branch**: `feat/011-official-rate`, landing on `main` by a `--no-ff` merge after a clean
review pass.

## Summary

Principle VI names three currency roles and two of them are built. The third — **tax**, being
base currency at the official rate on the transaction date — has been a docstring since the
first commit, and two sites refuse to fill it by accident: `routes.legs.channel_for` and
`resolver._check_channel` both say, in as many words, that substituting "the official rate"
for a channel would delete the spread the ramp model exists to measure. Both stay exactly as
they are.

This feature builds the other half. Official rates enter as declared, dated, cited
observations of a named series; the taxable base of a foreign-currency event is that event's
own amount at that event's own date's rate; and the amount received is still, and only, what
a declared channel produced.

**Where it is struck**: `core.tax.year._items`, the one site in the engine where a taxable
result in a currency the tax is not assessed in is already reachable and already refuses for
want of this machinery ([research D2](./research.md)). The refusal is replaced by the
conversion, or by a sharper refusal carrying a typed reason — which names the series, the pair
and the date where a declared series simply does not cover it, and says the jurisdiction
declared no series where there is none to name.

**What it deliberately refuses to convert**: a disposal's realised gain. That is a difference
between two amounts on two dates, and striking it at one date's rate would delete exactly the
FX gain required test F1 exists to find — `0 USD` at any rate is `0 UAH`
([research D3](./research.md)).

**What ships undeclared, on purpose**: the Ukrainian non-publication-day rule. Its text is
written in working days and public holidays, which FR-011 forbids the engine to know and
which no declaration in this system can supply, so declaring it needs the
`declared-working-day-calendar` feature (FR-018). FR-017 ships the refusal live instead, and
SC-015 exercises the declared-rule path against a **synthetic enumerated mapping**, which
needs no calendar.

## Technical Context

**Language/Version**: Python 3.12+. **Primary dependencies**: none new.

**Storage**: version-controlled TOML. One new directory, `data/official_rates/`, holding one
file: the Ukrainian series' identity with **no observations** and no rule
([research D6](./research.md)). No network, in the feature or in its tests.

**Testing**: pytest. Hand-computed conversions (SC-001, SC-002, SC-012); a battery of
uncovered dates (SC-003) and of broken files (SC-004); propagation and staleness (SC-005,
SC-006); two import-linter contracts plus a contract test for the standing prohibition
(SC-008); scratch-data-root contract tests for the second series (SC-011) and the synthetic
enumerated rule (SC-015).

**Target platform**: library only. No API, no CLI, no delivery surface — as in 001, 006, 007.

**Constraints**: core pure, no clock, no I/O; four plugin interfaces and this feature adds
none; frozen records and free functions; the single imported tolerance; the three currency
roles kept apart.

**Scale/scope**: 1 new core module, 1 new data directory with 1 file, ~6 touched source
files, ~9 test modules. Makes F1 *reachable*; closes neither F1 nor F2 nor F3.

## Constitution Check

| Principle | Verdict |
|---|---|
| **I — Honesty over precision** | **PASS.** No rate value is invented anywhere: the shipped series declares its identity and no observations, and every acceptance example states its own synthetic values in the test. A date with no declared rate refuses; nothing interpolates, extrapolates, carries forward or snaps to the nearest. The rule this feature could not declare refuses instead of being paraphrased. |
| **II — Framework, not script** | **PASS.** A second series with a distinct identity is a data-only addition (SC-011), and so is a non-publication rule (SC-015) — both asserted with zero source lines changed. No fifth plugin interface. |
| **III — Pure deterministic core** | **PASS.** `official_rate` imports `date` for typing and reads no clock; the event's date is an input and `as_of` stays a run input recorded in the manifest. |
| **IV — Reliability through contracts** | **PASS.** Every degraded outcome is a typed record naming its own fix. `total` is recomputed rather than converted so `total == pit + levy` stays exact. The one tolerance is imported. |
| **V — Test-first** | **PASS.** Every conversion lands with hand arithmetic checked in beside the assertion; the golden files are regenerated deliberately if a recorded digest moves, with the changed lines quoted. |
| **VI — Model the whole tuple** | **PASS — this feature *is* the third role.** The prohibition is enforced in both directions, as two separate contracts, because they are two separate requirements. |
| **VII — Owner-scoped and private** | **PASS.** No per-owner data, no network, no new dependency. |
| **Engineering Standards — D-E** | **PASS.** Frozen records, free functions, tagged unions matched with `match`. |

### Post-design re-evaluation

Three things the design surfaced and the plan carries forward:

- **The two directions of the prohibition are two contracts.** One import-linter contract
  naming both source modules would stay green if either direction were deleted. FR-012 and
  FR-013 get one each, and the contract *names* are pinned by the existing architecture test.
- **Converting a realised gain would have looked like success.** It type-checks, it produces a
  hryvnia figure, and it is the precise arithmetic that makes F1 unfalsifiable. The refusal is
  the feature, not a gap in it.
- **A conversion that dropped the rate's mark would pass every gate.** `money.convert` demands
  the rate's provenance in its signature, so the propagation is structural — and SC-005 checks
  both directions: an unverified rate marking a verified amount, and a marked amount surviving
  a verified rate.

## A boundary this feature must not cross

**Do not declare the Ukrainian non-publication-day rule, and do not extrapolate a calendar.**
FR-018 and the `declared-working-day-calendar` future entry record why: пункт 10 розділу III is
written entirely in working days, pre-holiday days, weekends and holidays, and пункт 11 adds
the Cabinet's power to move working days. The one calendar-free encoding — *the latest
observation on or before the event date* — is refused by the spec itself, because it cannot
tell a weekend from a gap in the series and would make FR-010's refusal unreachable for
exactly the dates it exists to refuse.

**A paraphrase is not a citation** (FR-011). The secondary restatement everyone reaches for
merges two підпункти the primary text keeps apart. It does not enter, in a data file or in a
comment.

**No legal, tax or fee value from memory, and no retrieval on this feature.** The owner has
ended further legal retrieval here. A value that turns out to be needed and is not in the spec
is recorded as a gap and reported; it is not researched and not guessed.

## Structure

```text
src/terezy/core/tax/official_rate.py          new — the series, the lookup, the struck base
src/terezy/core/tax/year.py                   AssessmentRules, ChargeRef, _items, refusals
src/terezy/core/results/tuple.py              prose: what is actually missing after 011
src/terezy/core/decision/tuple_outcome.py     prose + refusal text, same reason
src/terezy/data/declarations/schema.py        OfficialRate* tables, timing gains one key
src/terezy/data/declarations/loader.py        official_rate_from_file, timing link
src/terezy/data/declarations/resolver.py      OFFICIAL_RATES_DIR, identity collisions, the link
scripts/check_provenance.py                   SOURCED_DIRS + quotation_unit
.importlinter                                 two contracts, one per direction
data/official_rates/ua_nbu_usd.toml           new — identity only, no observations, no rule
data/observation_kinds.toml                   + official_rate, 7 days
data/tax/timing/ua.toml                       + official_rate_series
docs/METHODOLOGY.md                           + §31 the tax base
docs/REQUIRED_TESTS.md                        F1/F2/F3 notes narrowed, not flipped
specs/features.toml                           011 status; fx-tax-asymmetry-f1 note narrowed
tests/official_rates.py                       new — synthetic fixtures, labelled
```

## Phasing

1. **Foundations** — the core module and its tests, with nothing loading it.
2. **The declaration** — schema, loader, resolver, the gate, the shipped file.
3. **The strike** — `tax.year` wiring, the refusals, FR-016 reaching the statement.
4. **The standing properties** — the two import contracts, SC-008, SC-009, SC-010.
5. **Documentation and the graph** — METHODOLOGY §31, REQUIRED_TESTS, features.toml.
6. **`/condense`, then `/code-review` until clean.**

## Complexity tracking

| Departure | Why | Alternative rejected because |
|---|---|---|
| An official-rate series may declare **no** observations, where a CPI series may not | The shipped file is the declared shape the fetch script writes into, and no rate value may be invented to populate it | Shipping invented rates violates FR-001; shipping no file leaves `official_rate_series` unresolvable and FR-017 unimplementable |
| `OfficialRateObservation` carries no `kind`, unlike `CpiObservation` | 010's finding: a threshold on a record does not survive a merge of provenance, a kind on a citation does | Copying CPI's shape would put the same fact in two places and lose it at exactly the merge a derived tax figure passes through |
