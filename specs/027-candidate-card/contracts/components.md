# Component inventory

**Feature**: `027-candidate-card` | **Plan**: [../plan.md](../plan.md)

Every component the feature builds, the requirement it carries, and the test that holds it. A
**contract, not a description**: SC-004 is checked by enumerating this table's *Comes from* column
against what the drawing components actually read.

**✱ marks a figure-bearing component.** Each composes 021's `FigureSlot` rather than printing a
value, so a refused amount and a marked one already have somewhere to go.

## Python — the core and the wire

| Thing | Carries | Test |
|---|---|---|
| the serialisable projection union and its refusal | FR-001, FR-003 to FR-005, FR-007 — one member per projection kind, each with its arm's dated lines, the charges with their bases, the purchase with its split, the two route charges with their latencies; a typed refusal where no projection was produced | `tests/unit/`: each member carries its own arm's lines; every field is one the join already held |
| `evaluate` returning it beside the outcome | FR-001, FR-002 — `TupleOutcome`'s field set unchanged | `tests/golden/`: the answer's rendered lines and `digest_of_answer` do not move |
| the published candidate key | FR-006 — (horizon, five terms), rendered in `core/`, on each evaluated outcome as `projection_key` beside the existing `key` | `tests/unit/`: two sections of one answer give one candidate two distinct keys; `tests/contract/`: no `api/http/` module composes one |
| the accounting | FR-030, SC-001 — the served flows account for `reaches` at the **imported** tolerance, for every ranked candidate of the shipped question on **both** arms, none skipped; every served flow carries a mark | `tests/contract/test_the_card_accounts_for_what_came_back.py` |
| the endpoint and its envelope | FR-009 to FR-012 — one GET, two distinguishable refusals, `document.VERSION` bumped | the wire contracts re-run unchanged; `tests/contract/`: the answer document's size is unchanged beyond the key |

## TypeScript — pure functions over served shapes, `web/src/card/`

| Module | Carries | Test |
|---|---|---|
| `bars.ts` | FR-013, FR-014 — served flows → the ordered bar list. Reads no `parts`, performs no subtraction | unit: one case per row of plan Finding 4; a fixture whose bars would sum wrong still yields the served amounts |
| `zeros.ts` | FR-017 — a zero charge carrying sources against one carrying none | unit: both shapes, from the shipped registry's own two cases |
| `currencies.ts` | FR-015 — do all bars share a currency? | unit: a boolean, and no figure and no rate in the return type |
| `events.ts` | FR-020 to FR-023 — served flows and dates → placed events, boundaries, and latency segments from the **declared** days | unit: an event outside the window is outside and marked; a date whose payment its tax consumed exactly is present |
| `refusals.ts` | FR-007, FR-011, FR-016 — a bar the arm states no flow for, and each of the two endpoint refusals, as its own named state | unit: never a zero, never a blank |

## TypeScript — the components, `web/src/card/components/`

| Component | ✱ | Carries | Test |
|---|---|---|---|
| `Waterfall` | ✱ | FR-013's order, FR-016's refusal bars, FR-018's per-bar mark, FR-015's per-currency grouping, FR-019's statement that the bars do not sum to the rate | unit: each bar state; strip every style declaration and read the bars as text; a two-currency fixture draws no joined baseline |
| `TaxBar` | ✱ | FR-017 — the two zeros, the base beside the charge, the class named | unit: both zeros render differently and neither is blank |
| `Timeline` | | FR-020 to FR-024 — the window's boundaries, every served event, the latency segments in days, the remainder's arrival or its named absence | unit: each event kind, an event outside the window, a missing latency; readable as text with styles stripped |
| `CandidateCard` | ✱ | FR-025, FR-026, FR-027 — the marks as badges, the provenance behind one disclosure, the belief not repeated, every figure through 026's formatter | unit: a marked bar carries the badge, the full citation is reachable, no raw float |
| `CardRoute` | | FR-028 — openable from any ranked row and closable back to the reader's place; a named wait and a named failure | unit both; e2e from a ranked row and from a card |

## Cross-cutting

| Thing | Carries | Test |
|---|---|---|
| `docs/METHODOLOGY.md` §29 | FR-008 — what the served projection carries, and what it still does not | read at review; no scan |
| `docs/REQUIRED_TESTS.md` **E11** | SC-003 — the row flips, with the test path | the row itself |
| accessibility | FR-029 — keyboard reach, AA in both themes, nothing by colour alone | 021's a11y pass extended to the card |

## Deferred to Phase 6 — turns on a clarification

| Thing | Clarification |
|---|---|
| a rate on the tax bar | CL-1 |
| the six-part attribution panel beside the waterfall | CL-2 |
