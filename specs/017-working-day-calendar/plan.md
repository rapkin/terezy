# Implementation Plan: The declared working-day and public-holiday calendar

**Feature**: `017-working-day-calendar` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Branch**: `feat/017-calendar`, landing on `main` by a `--no-ff` merge after a clean review
pass. **The owner lands it**; this branch does not merge and does not flip `features.toml`.

## Summary

A new declaration kind: a calendar saying which dates a jurisdiction's law calls working, which
it calls holidays and which it calls pre-holiday days — enumerated over a declared weekly rest
pattern, bounded by an explicit two-ended coverage window, cited per row, and refusing by name
outside it.

**It ships no consumer** (FR-015), moves no golden and changes no figure (SC-010). What it
changes in the existing tree is three sentences that go false (FR-017a) and one scan that must
land whether or not anything ever consumes a calendar (FR-018a).

The shape, decided in [research.md](./research.md): **one record, one form, four questions,
three refusal reasons, and one shipped calendar whose holiday enumeration is empty and means
it.**

**Where this feature can be wrong.** Not in arithmetic — there is none. In three places:

1. **A legal value entering from memory.** The Labour Code articles were retrieved in full on
   2026-08-31 (research D9), so the shipped calendar transcribes four provisions and reads
   none. The one place a reading would hide is the week: ст. 67 ч. 2 makes **Sunday** the
   general rest day and delegates the second day of a five-day week to the enterprise's own
   schedule, so `rest_days = ["sunday"]` is the transcription and Saturday would be the
   invention. Owner verification task 3 records the divergence from `_is_weekend`.
2. **A scan that passes while asserting something false.** FR-018's whole value is that a
   fourth site cannot appear quietly, and the narrowing that would destroy it — counting only
   direct callers of `is_business_day` — is named in the specification. The scan counts the
   registry path, and it lands in phase 1 rather than at the end.
3. **A refusal that is less explicit than the one it replaces.** Answered by the window being
   declared, two-ended, and named in every out-of-coverage refusal, with a discriminator
   separating *never covered* from *the answer ran off an end*.

## Technical Context

**Language/Version**: Python 3.13; CI matrix 3.12 / 3.13 / 3.14.

**Primary Dependencies**: none new.

**Storage**: version-controlled TOML. One new directory, `data/calendars/`, with one file.

**Testing**: pytest. A hand-written classification table checked in beside its assertions; a
load-failure battery; a field-by-field refusal battery; two source-tree scans; the existing
goldens as the regression that nothing moved.

**Target Platform**: library; no delivery surface in this feature.

**Project Type**: single project — pure core plus a data boundary.

**Constraints**: `core/` stays pure (Principle III). The calendar is an argument to every
question; no module holds one.

**Scale/Scope**: one new core package, one loader function, one resolver function, one data
directory, one `SOURCED_DIRS` entry, one METHODOLOGY section.

## Constitution Check

| Principle | How this feature stands |
|---|---|
| **I — Honesty over precision** | No legal value from memory: four provisions transcribed from primary texts retrieved 2026-08-31, `verified_on` empty on all three citation sites. A date outside the window refuses rather than being classified. Three owner verification tasks stay open and none is guessed past. |
| **II — Framework, not script** | A calendar is data. A second jurisdiction's is a data-only addition (SC-006). No fifth plugin interface: a calendar is a declared record, not a plugin. Load failures name file and field (FR-007). |
| **III — Pure deterministic core** | `core/calendars/` imports `datetime`, `bisect`, `dataclasses`, `enum`, and `core.primitives.provenance`. No clock, no I/O, no formatting. `.importlinter` covers it under `terezy.core`. |
| **IV — Stated contracts** | Every degraded outcome is a typed value carrying its reason (`CalendarUnavailable`, three members). No money in this feature, so no tolerance question arises. |
| **V — Test-first** | Every behaviour lands with a hand-computed table, a load-failure case, or a scan. Tests are written before the modules they import. |
| **VI — The whole tuple** | Untouched: no cost, no currency, no route. SC-010 is the check that it stayed untouched. |
| **VII — Owner-scoped and private** | Curated shared data; no per-user data, no network, no new dependency. |
| **Documentation** | `docs/METHODOLOGY.md` gains the classification rule in this change (FR-021); `docs/REQUIRED_TESTS.md` gains this feature's rows. The prose ratchet is a gate, and it is not raised. |

**Post-design re-check**: no violation, and nothing in the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/017-working-day-calendar/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/calendar-queries.md
└── tasks.md
```

### Source code

```text
src/terezy/core/calendars/__init__.py
src/terezy/core/calendars/working_day.py     # records, refusals, four queries
src/terezy/data/declarations/schema.py       # CalendarFile and its four tables
src/terezy/data/declarations/loader.py       # working_day_calendar_from_file
src/terezy/data/declarations/resolver.py     # working_day_calendars_from_data_root
scripts/check_provenance.py                  # data/calendars/ joins SOURCED_DIRS
data/calendars/ua_civil.toml                 # the one shipped calendar

tests/unit/test_working_day_calendar.py                 # queries and refusals, field by field
tests/worked_examples/test_working_day_classification.py# the hand-written table
tests/contract/test_calendar_declaration_loading.py     # SC-004's battery
tests/contract/test_calendar_data_only.py               # SC-006, SC-007, SC-011
tests/contract/test_no_calendar_free_working_day.py     # FR-018's scan
tests/contract/test_provenance_gate.py                  # SC-005's delta, measured
```

**Structure Decision**: a new `core/calendars/` package rather than an addition to
`core/primitives/conventions.py` — research D1. The declaration surface follows
`data/official_rates/` exactly, because 011 settled every question this file shape raises.

## Phases

**Phase 0 — FR-017a and FR-018 first.** The three false sentences and the scan. They are the
part of this feature that is worth landing whether or not a calendar ever has a consumer, and
the scan's value is lost for as long as it waits.

**Phase 1 — the core.** Records, the three refusals, the four queries. Tests first.

**Phase 2 — the declaration.** Schema, loader, resolver, `SOURCED_DIRS`, the load-failure
battery.

**Phase 3 — the shipped calendar** and SC-005's measured delta.

**Phase 4 — the data-only claims** (SC-006, SC-007), SC-010, and the documentation.

## Complexity Tracking

No constitution violation requires justification.
