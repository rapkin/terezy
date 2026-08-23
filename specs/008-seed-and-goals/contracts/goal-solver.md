# Contract: the goal solver

**Feature**: `008-seed-and-goals` | **Module**: `terezy.core.goals.solve`

## Signature

```python
def solve(
    goal: Goal,
    *,
    inputs: GoalInputs,
    conventions: Conventions,
) -> GoalOutcome | GoalUnderdetermined | StartingAmountMissing | GrowthAssumptionMissing | CurrencyNotYetModelled | NoContributionNeeded
```

Pure. No clock — every date is an argument or a declaration.

## Guarantees

**G1 — Any two solve the third.** Fewer than two declared is refused naming what is missing.
(FR-011)

**G2 — Nothing is defaulted.** A missing starting amount or growth assumption is a typed
refusal naming that input. No rate is assumed, no opening balance substituted. (FR-012)

**G3 — The three modes agree.** Solving for the date from `(contribution, sum)` and then for
the sum from `(contribution, that date)` returns the original sum within the **imported**
project tolerance, and the round trips through the contribution mode close the same way. **No
mode defines its own tolerance.** (FR-013)

**G4 — The model is stated, not implied.** The conventions the arithmetic depends on travel in
the result, so a hand computation checks the same model the engine ran. (FR-014)

**G5 — The date mode answers twice.** The exact solution and the first calendar date the
target is reached, each labelled. Neither is rounded into the other. (FR-015)

**G6 — Marks propagate.** Every mark on the growth assumption reaches every solved figure.
(FR-012)

**G7 — Nominal on its face**, with a defined empty slot for real terms. (FR-017)

**G8 — Feasibility is reported, never engineered.** With all three fixed: met with the margin,
or missed with **both** the amount missing at the target date and the earliest date the target
would be reached. No declared variable is adjusted to make a goal pass. (FR-018)

**G9 — Unreachable is unreachable.** Never a capped horizon, never an arbitrarily distant
date, never a nearest answer. (FR-019)

**G10 — A non-positive contribution is "no contribution needed", with the margin** — never a
negative number presented as an instruction. (FR-020)

**G11 — A non-base currency is not yet modelled, not invalid.** The refusal names the missing
FX modelling, the record keeps its `currency` field, and nothing in the message or the shape
paints the multi-currency case as closed. (FR-016)

**G12 — The verdict is not a probability, and says so.** Deterministic under one stated
assumption; no field for a likelihood exists. (FR-021)

## Contract for seeds

```python
def opening_events(
    seeds: Sequence[SeedLot],
    instruments: Mapping[str, InstrumentDeclaration],
    *,
    opens_on: date,
) -> tuple[Event, ...] | SeedInstrumentUndeclared | InconsistentTerms
```

⚙ **Amended during implementation (2026-08-23).** `opens_on` is the date the projection's
ledger opens, and it is an argument because the core has no clock; `InconsistentTerms` is the
spec's two date edge cases -- a lot acquired before its instrument existed, or after the ledger
opens -- reported rather than silently re-dated.

**G13 — A seed is an ordinary ledger citizen.** It opens the ledger through the same path a
purchase takes, and every existing conservation invariant counts it with no knowledge that it
was seeded. (FR-002, FR-003)

**G14 — A guessed cost is a guessed tax.** An estimated basis is a `SourceRef` in the lot's
provenance, so the disposal gain and the tax computed from it carry the mark through the
transforms that already exist. No second marking system. (FR-004, FR-007, FR-008)

**G15 — An unknown instrument fails at load, naming file and field.** (FR-005, FR-023)

**G16 — Empty is ordinary.** No seeds and no goals runs correctly, with empty positions and no
goal section — not a refusal. (FR-024)
