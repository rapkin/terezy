# Implementation Plan: The candidate card — why exactly this figure

**Feature**: `027-candidate-card` | **Date**: 2026-09-07 | **Spec**: [spec.md](./spec.md)

**Branch**: written on `spec/027-candidate-card` and lands **squashed** — spec-directory work, not an
implementation. The implementation branch is `feat/027-candidate-card` and lands by `--no-ff`.

**Both clarifications were answered 2026-09-11 by the conductor, provisionally**
(`specs/decisions/2026-09-11-clarify-027.toml`): no rate on the tax bar, and the attribution beside
the waterfall behind a fold. Phase 6 is therefore open, and each answer is overruled by the one-line
change that file names rather than by a re-plan.

## Summary

The join computes a `Projection` per candidate and drops it. It stops dropping it; one GET endpoint
serves one candidate's flows; the card draws a waterfall and a timeline from them, bar by bar, event
by event, with every mark carried through. Zero new figures in the core.

The plan's contribution over the spec is five findings and a build order.

**Finding 1 — the change is a return value, not a field.** `_hold` (`tuple_outcome.py:414`) holds
`projected` at line 430 and `_assemble` (`:1468`) builds the outcome at `:1529` without it. The
change is that `evaluate` returns the outcome **and** the projection, and its **one** caller —
`core/decision/compare.py:106`, the only site in `src/` that calls it — keeps the outcome half and
discards the other, exactly as it does today. That is what makes FR-002 satisfiable: `TupleOutcome`
gains only FR-006's key — one short string per outcome against the tens of kilobytes a projection is
— so no golden's rendered lines move and `digest_of_answer` is untouched. Carrying the projection on
the record was the obvious shape, and the spec's decision table says why it is the wrong one.

**Finding 2 — the key is the core's to publish, and it must carry the horizon.** The HTTP layer may
not compose one: `tests/contract/test_the_http_layer_computes_nothing.py` forbids any `api/http/`
module from touching `core/results/canonical.py`, which is where the five-term identity already
lives (`of_tuple_key`). And five terms are not enough — the same candidate is evaluated in every
section, so `UA4000231195 × salary_uah × …` names three outcomes with three different projections.
So the key is **(horizon, the five terms)**, rendered once in `core/`, published on each evaluated
outcome as `projection_key` — **not** `key`, which is already the five-term `Tuple` and would read
as the same thing on the wire — and echoed by the client. `categories.DESTINATION_SEPARATOR` is the
precedent for the **shape**: a compound id in one path segment, published by the API and never built
by a client. It is not a precedent for the location, because `destination_id()` composes it inside
`api/http/categories.py`; what puts this key in `core/` is the contract test above. The key is
derived from the identity the digest already encodes, so it is not added to the digest — that would
be one fact in two places.

**Finding 3 — the endpoint answers to resolve the key, then evaluates one candidate.** Finding 1
has the answer pipeline discarding every projection, so re-answering cannot by itself produce one:
the endpoint answers the question to resolve the key to **the tuple and the horizon it names** —
which is also what proves the key is one this answer produced rather than a string a client made up
— and then calls `evaluate` for that one tuple, keeping the half `compare` throws away. Answering is
deterministic at a given `as_of`, so the projection served is the projection that produced the figure
the reader is looking at, and the cost is the spec's measurement of both steps. A **cache** is what
an implementer would reach for instead, and it is refused on two counts: it is state in the one layer
whose whole claim is that it computes nothing, and the constitution's cache rule is about provenance
rather than about saving a repeat. If the cost stops being affordable the remedy is 026's OB-10 — a
narrower server-side read — and not a cache.

**Finding 4 — a waterfall bar has one of four sources, and the card must not mix them.** This is
where a client-side subtraction would creep in, so the mapping is fixed here rather than left to an
implementer:

| Bar | Comes from | Not from |
|---|---|---|
| what left the stream | `TupleOutcome.outlay` | — |
| the way-in charge | the served way-in cost's **components**, one bar per component | `outlay − arrived` |
| what arrived | the served way-in cost's `arrived` | `outlay` less the components |
| what bought units, and what was left over | the purchase flow's amount; `TupleOutcome.undeployed.amount` | `arrived` less the remainder |
| the accrued interest inside the price paid | the served clean/accrued split at purchase | any re-derivation from a coupon |
| what the holding released, gross | each served schedule row's `gross` | the lifecycle part |
| the tax struck on it | each served charge's `total`, with its `taxable_base` beside it | `gross − net` |
| the way-out charge | the served per-release charge | `released − amount` on an `Arrival` |
| what reached home | `TupleOutcome.reaches` | the sum of the bars |

The last row is the one that matters most and is the reason FR-019 exists: the bars do **not** sum to
`reaches`, because the tax is netted before the percentage exit fee and because a date that netted to
zero left the released series. The card states the disagreement rather than hiding it, and SC-001's
contract test asserts the accounting at the project tolerance on the **served** side, where every
term is present.

**Finding 5 — the fund arm is live, ranked, and shaped differently.** Measured 2026-09-07: the
registry declares **two** funds, and while `inzhur_reit` refuses, **`inzhur_miltech` is a ranked
candidate in all three sections** of the shipped answer. So the fund arm is not a fixture-only case
and cannot be dismissed as a refusal. `FundProjection` (`core/results/fund.py:310`) carries a ledger
and charges and **no `CashFlowSchedule`**, so there are no rows to draw — and what it carries
instead is dated all the same: `DistributionLine` with a record date, a pay date, gross, tax and net,
and an `ExitLine` with its execution and settlement dates. Measured in the shipped window it states
**no distribution at all** and an exit line, so a fund's card is drawn from that line and from
absences — which is what makes FR-007 a bar-level statement rather than a refusal of the card.

That is why FR-003 is a **union** rather than one flow record. Flattening a fund's lines into a
bond's row shape would be the core computing something new, which FR-001 forbids; declaring the fund
a refusal would put a ranked candidate behind an empty card and would make FR-030's *every ranked
candidate* a claim no test can keep. The union is what lets the accounting hold on every arm — there
were two when this was written and `023-cash-instrument` landed a third — and it
is what makes a bar a bond has and a fund does not a **refusal bar** rather than a missing one.

## Technical Context

**Language**: Python (`core/`, `api/http/`) and TypeScript in `web/`, both existing trees. No
dependency added on either side.

**Testing**: `tests/contract/` for the accounting identity and the wire; `tests/unit/` for the
serialisable projection's shape and its refusals; Vitest + MSW typed from the generated document for
the waterfall and timeline components; Playwright against the real API on loopback over the shipped
`data/`, offline.

**Constraints**: the core stays pure and computes no new figure (FR-001); the HTTP layer computes
nothing (FR-010); same origin, loopback only, 021 FR-034 to FR-037 unchanged.

## Constitution Check

| Principle | How this feature stays inside it |
|---|---|
| **I — honesty over precision** | The feature exists to stop a conclusion standing without its intermediates. A refused bar is drawn as a refusal; a zero says which zero it is (FR-017); no rate is consulted to join two currencies (FR-015). |
| **II — data, not code** | No domain fact is added. No new plugin interface; the flow vocabulary is the ledger's existing closed enum. |
| **III — pure core** | The change is a return value. No I/O, no formatting, no new computation — the audit-trail claim this feature *serves* is the one Principle III already makes. |
| **IV — explicit failure** | FR-011's two refusals are distinguishable because the remedies differ, and FR-007 records why there is no third rather than shipping an unreachable one. FR-016: a missing bar is a refusal bar. |
| **V — test-first** | SC-001 is a contract test over the shipped `data/`; the fund refusal and the two zeros each land with a test before the code. Required test **E11** closes here. |
| **VI — the whole tuple** | The key is all five terms plus the horizon (Finding 2). FR-015 keeps the three currency roles apart by refusing to join them. |
| **VII — private** | No new dependency, no new origin, one more loopback GET. |

**Prose discipline**: `web/` stays outside `check_prose_budget.py` and `check_enumerations.py` (021's
reasoning, unchanged); the flow-kind exhaustiveness is a typecheck rather than a prose list.

## Project structure

```text
specs/027-candidate-card/
├── spec.md
├── plan.md                     # this file
├── tasks.md
├── contracts/
│   ├── the-served-projection.md   # what the endpoint answers, field by field
│   └── components.md              # what is built, what it carries, what holds it
└── checklists/requirements.md

src/terezy/
├── core/decision/tuple_outcome.py  # evaluate returns the projection beside the outcome
├── core/results/                   # the serialisable projection record and its refusals
└── api/http/                       # one fixed route, one envelope

web/src/card/                       # the waterfall, the timeline, and the pure functions under them
```

## Build order, and why it is this one

**Phase 1 — the core stops discarding.** The serialisable projection record, `evaluate` returning it,
the published key, and the tests that the served flows account for `reaches` at the imported
tolerance for every ranked candidate of the shipped question. Nothing is rendered yet, and this is
the phase that either proves the accounting or finds out it does not hold — which is worth knowing
before a single component exists.

**Phase 2 — the endpoint.** One GET, its envelope, its two distinguishable refusals, and the wire
contracts re-run. `document.VERSION` bumps in the same commit.

**Phase 3 — the pure functions over served shapes.** Flows → bars, flows → events, the currency
grouping predicate, the two-zero discriminator. Each takes a typed value and returns a typed value;
each is unit-tested against fixtures typed from the document. Still no screen.

**Phase 4 — the two components.** Waterfall and timeline, assembled from 3 and 026's language, tested
against fixtures in every state including both refusal shapes.

**Phase 5 — the card on the screen.** Opening from any ranked row, the named wait, the disclosure,
and Playwright against the real API.

**Phase 6 — what turns on a clarification.** The tax bar's rate (CL-1) and the attribution panel
(CL-2). Last, and **may not start** until both are answered.

## Risks

- **R1 — the accounting may not close.** Six things happen outside the projection (spec, *What the
  join drops today*), and Phase 1's test is what says whether serving the way-in and way-out charges
  is enough to account for `reaches` at the project tolerance. If it is not, the gap is a finding
  about the join and is reported as one, not absorbed into a looser tolerance.
- **R2 — the accrued split at entry.** It is computed at `tuple_outcome.py:999` and summed away at
  `:1009`, inside a helper that returns one price. Carrying it means widening `_Acquisition`, which
  is a real edit rather than a field copy — and it is the one bar the owner named that the sell side
  already has and the buy side does not.
- **R3 — the cost of a card is a measurement in one process on one machine, and it has already
  disagreed.** The spec records ~0.16 s over four warm runs; a second reading on 2026-09-07 put the
  same call at 0.45–0.49 s. Under the server it is a request per card open. So the figure decides
  *endpoint over field* — where the margin is 37% of a document either way — and decides nothing
  about how fast a card feels; SC-006's named wait is what covers that.
