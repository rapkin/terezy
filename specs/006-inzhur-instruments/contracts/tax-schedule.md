# Contract: dated tax rate schedules

**Feature**: `006-inzhur-instruments` | **Module**: `terezy.core.tax.schedule`

## Signature

```python
def rate_on(tax_class: TaxClass, on_date: date) -> RateEntry | RateUndeclaredBefore
```

Pure. No clock — the date is an argument, as everywhere in `core`.

## Guarantees

**G1 — In force from the effective date inclusive.** The entry returned is the one with the
latest `effective_from` on or before `on_date`. The boundary is inclusive and is tested *at*
the boundary. (FR-011)

**G2 — Before the earliest entry is a typed refusal, never a default.** No rate is assumed,
no zero is silently charged, and the refusal names the class, the event date and the earliest
date the schedule does declare. (FR-012)

**G3 — A legislated change is one dated entry in a data file.** No source-code change, no
rebuild. A run whose events straddle the effective date charges the old rate before it and
the new rate on and after it. (FR-013, required test E10)

**G4 — Every entry carries its own provenance.** Two rates cited by two sources are two
observations with two verification dates; the class does not carry one mark for both.

**G5 — The exempt class survives the migration unchanged.** It charges exactly zero on every
event, and feature 001's golden file is byte-identical. (FR-014, research.md D13)

## The effective date is a cited fact

`effective_from` is exactly the date the entry's citation attests. Where a source establishes
the current rate but not when the previous one began, **no earlier entry is invented** — the
schedule starts at the attested date and G2 covers everything before it.

This is the feature's sharpest trap. Back-dating one entry to `1900-01-01` so that
"everything just works" makes every test pass while putting an invented legal fact in a data
file — the one thing the constitution forbids in those words. If feature 001's golden run
(2026-01-15 onward) falls before the attested date for the exempt class, the fix is a
citation for the earlier entry. **If none can be found, stop and ask the owner.** It is not an
implementer's judgement call.

## Loader validation

All at load, all naming file and field:

| Condition | Why |
|---|---|
| Empty `rates` list | A class with no rate cannot charge anything, and a silent zero is the worst possible reading |
| Duplicate `effective_from` within a class | Two rates in force at once has no meaning; one of them is a typo |
| Unsorted entries | Sorted at load so the fold is a scan, and so the file's order cannot change a figure |
| A rate that is not a percentage | `_as_fraction` at the boundary, exactly once, as 002 established |
| Missing `source` or `retrieved_on` on an entry | The provenance gate; `verified_on` empty is expected and correct |
