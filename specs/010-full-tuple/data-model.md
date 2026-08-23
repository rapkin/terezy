# Phase 1 data model: the full tuple

**Feature**: `010-full-tuple` | **Date**: 2026-08-23

Frozen records, free functions, tagged unions matched with `match`. One imported tolerance.

**The rule that governs this file: the join holds no figure it computed itself.** Every
amount below came from a call that owns it, and the join's own content is the chaining and
the refusals (research.md D1).

---

### `Tuple` — the unit of analysis, `core/results/tuple.py`

| Field | Type | Meaning |
|---|---|---|
| `instrument_id` | `str` | |
| `stream_id` | `str` | |
| `route_in` | `Candidate` | 002/004's declared or composed path |
| `exit_terms` | declared | The instrument's own exit conditions |
| `route_out` | `ExitChain` | |
| `risk_class` | `str` | **Declared, not scored** (research.md D9) |

Identity is all five (FR-010). A cost or outcome attributed to an instrument alone stays
unrepresentable, as 002 FR-008 and 004 FR-011 already require.

### `TupleOutcome`

| Field | Type | Meaning |
|---|---|---|
| `parts` | `tuple[PartContribution, ...]` | Ramp in, entry fees, lifecycle flows, tax, exit terms, ramp out — each separately (FR-005) |
| `reaches` | `Money` | What arrives at a spendable endpoint |
| `implied_rate` | `float` | The rate that amount implies over the horizon |
| `horizon` | `DateRange` | The **one** horizon of the comparison (FR-025) |
| `accounts_for` | `str` | Stated on every figure |
| `excludes` | `str` | Stated on every figure (FR-014) |
| `provenance` | `Provenance` | The union of all four parts' |
| `staleness` | `StalenessVerdict` | Merged across the parts |

**Both figures, always** (research.md D8): the amount is what can be spent, the rate is what
compares across horizons, and reporting one invites deriving the other under an assumption
the tool did not make.

### `PartContribution`

| Field | Type | Meaning |
|---|---|---|
| `part` | `Literal["ramp_in","entry","lifecycle","tax","exit_terms","ramp_out"]` | Closed |
| `amount` | `Money` | |
| `source` | `str` | Which call produced it — so a reader can go check it |

### `Comparison`

| Field | Type | Meaning |
|---|---|---|
| `horizon` | `DateRange` | Stated once, applied to all (FR-025) |
| `ranked` | `tuple[TupleOutcome, ...]` | After-tax, after-cost |
| `benchmark` | `TupleOutcome` | **The hurdle, produced by the same path** (FR-012) |
| `ties` | `tuple[tuple[int, ...], ...]` | 002's tie rules unchanged, hurdle included (FR-013) |
| `refused` | `tuple[TupleRefused, ...]` | Visible, never silently absent |

## Refusals

| Record | When |
|---|---|
| `SeamDoesNotChain` | Names **both sides** — where the route in ends and where the purchase begins, or where the exit produces and where the route out starts (FR-004) |
| `NoExitRouteDeclared` | Inherits 002 FR-030's treatment (FR-007) |
| `NoExitTermsDeclared` | The instrument side of the same gap (FR-008) |
| `BelowMinimumTicket` | Names the minimum and the shortfall (FR-017) |
| `PartiallyDeployable` | Each tranche and the **undeployed remainder** — never rounded (FR-018) |
| `DeclarationMissing` | Which of the four parts, and which declaration (FR-006) |
| `TaxCurrencyConversionUnavailable` | A foreign-currency taxable event, naming the missing official-rate machinery (research.md D10) |

## What is deliberately absent

- **No figure the join computed.** Only sums of what the owning calls returned.
- **No reinvestment assumption** for proceeds arriving before the horizon ends.
- **No risk score.** The class is declared and carried; scoring needs a model nobody declared.
- **No display currency** of any kind (FR-024).
- **No special case that makes H1 pass.** A data-only addition needing an engine edit is a
  recorded defect in the abstraction, and fixing the abstraction is in scope (FR-023).
