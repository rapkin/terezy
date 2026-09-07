# The endpoint, and what it answers

**Feature**: `027-candidate-card` | **Plan**: [../plan.md](../plan.md)

The **decision** — a separate endpoint rather than a field on the outcome, and what each costs — is
in the spec and is not repeated. This file is the other half: what one request answers, so an
implementer reading a row knows what to build and a reviewer knows what to check.

## The request

| | |
|---|---|
| method | `GET`, because every route under `/api` is one (`tests/contract/test_the_route_table.py`) |
| shape | one candidate's projection, under the answer it belongs to, addressed by the key that answer published |
| parameters | `as_of`, required and validated the way every other route validates it. No `scenario_id` — the answer resolves its own regime from the question's declared one |
| the key | published by the core on each evaluated outcome as `projection_key`; **(horizon, the five candidate terms)**. The client echoes it and never composes one |

## What the body carries

Each row is a thing the join computes and drops today. Nothing here is a new figure.

| Field | What it is | Why the card needs it |
|---|---|---|
| the flows | one per dated ledger line: date, kind from the ledger's closed vocabulary, quantity where units moved, gross, tax, net, the convention that shaped it, the declaration that caused it | every lifecycle bar and every timeline event |
| the charges | per charge: the two lines **and their total**, the **taxable base**, the class that struck it, the year it accrues to, its own provenance | the tax bar's base, and E11's cited zero |
| the purchase | its **date**, the quantity, the price per unit and the **clean/accrued split** of it | the timeline's first event after the money leaves, and the accrued bar the owner named |
| the premium at purchase | what was paid against what the paper repays, and the treatment governing the difference | a bar for a real term that today reaches no reader |
| the way in | the charge **by component and by segment**, what was sent, what arrived, and the declared latency in days | the entry bars, and the timeline's first latency segment |
| the way out | per **dated release** — the charge is struck once on what a date nets: the charge, what was sent, what arrived, and the declared latency in days | the exit bar, without which the card must subtract `Arrival.released` from `Arrival.amount`. One bar per date, never one per flow |
| the arm | which projection kind this is, as a tag; a fund's dated lines are its distributions and its exit line, a bond's are its schedule rows | the two are different records and neither is re-shaped into the other |
| a typed absence | per bar and per event an arm states no flow for | a fund states no cash-flow schedule and, in the shipped window, no distribution — and the shipped registry **ranks** it |

**Not carried, and each for a stated reason:**

- **the ledger.** The shape algebra refuses it outright, for the reason the spec measures. The
  traceability the card needs travels instead as each flow's own `caused_by`, which names a
  **declaration** rather than pointing at an event nobody can fetch.
- **the remainder and its journey.** Already on `TupleOutcome` since `fix/undeployed-remainder`.
  Carrying it twice is where two copies of one fact drift.
- **the tax rate.** The engine has never recorded it — CL-1.
- **`reaches`, the rate, the span, the horizon.** All on the outcome the card already holds.

## What the card does with it

| Operation | Kind | Rule |
|---|---|---|
| a flow → a bar | read | permitted. The amount is the served one; the bar's length is a layout decision and not a figure |
| a flow → a timeline event | read | permitted, placed by its served date |
| a charge's zero → *exempted* or *no rule ran* | typed match on whether the charge carries sources | permitted, and it is E11. Never a match on an amount alone |
| bars in one currency? | comparison of served currency tags | yields a **boolean** for the grouping. No rate is consulted, ever |
| `outlay − arrived`, `gross − net`, `released − amount`, the sum of the bars | **forbidden** | each is a figure with no owning call and no test. The served charge is what the bar is |
| a flow kind with no label | render the raw kind | never blank, never absent |
| the latency segment's length | the served declared latency in days | never the gap between two dates, which is the same number until the day it is not |

## Refusals

**Two**, and they must be distinguishable because the remedies differ: **the question is not
declared** — a wrong URL — and **the key names no evaluated candidate in this answer** — a stale
client. There is deliberately no third. A candidate whose projection could not be produced never
becomes an outcome, so it carries no key and has no address here; what the card meets instead is a
bar the arm states no flow for, which is FR-007 and lives in the body rather than in this list.
