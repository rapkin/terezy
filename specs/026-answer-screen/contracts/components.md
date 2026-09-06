# Component inventory

**Feature**: `026-answer-screen` | **Plan**: [../plan.md](../plan.md)

Every component the feature builds, the requirement it carries, and the test that holds it. A
**contract, not a description**: SC-002 and 021's SC-002 are both checked by enumerating this table.

**✱ marks a figure-bearing component** — one with a slot where a figure appears. Each must compose
021's `FigureSlot` rather than print a value, so a refused rate and a marked amount already have
somewhere to go (FR-015). Components that *are* a state — a badge, a refusal group — are not marked.

## The language — `src/design/`

| Component | ✱ | Carries | Test |
|---|---|---|---|
| the kind tokens in `styles.css` | | FR-001 — one hue per kind at equal chroma and lightness, each value once in `light-dark()`, beside 021's | e2e contrast pass in both themes (FR-027) |
| `kinds.ts` | | FR-004 — the kind → hue map, exhaustive over the declared vocabulary, keyed by no category id | unit: a mapped type over the vocabulary leaves the object one key short and the build red |
| `KindTile` | | FR-002 — icon **and** the kind as text; hue never the sole carrier | unit: strip every style declaration, read the kind |
| `icons/` | | one 24-grid outline component per kind at stroke 1.75 | unit: one per key of `kinds.ts`, enumerated from the map |
| `Badge` (extended) | | FR-003 — a fourth tone, `assume`, beside 021's `warn`, `refuse` and neutral | unit: each tone renders its own text |
| `format.ts` | | FR-026 — money, percent and date in **one** module, precision stated once | unit per shape; e2e asserts no raw float in the document |

## Pure functions over served shapes — `src/answer/`

| Module | Carries | Test |
|---|---|---|
| `separating.ts` | FR-019 — typed facts → a closed badge vocabulary; an unmatched case yields the raw tag | unit: one case per row of plan Finding 2's table, **including the sold-early member whose `per_member` list is empty** |
| `grouping.ts` | FR-022 — group by typed discriminants, never by reason text | unit: the shipped no-candidate population collapses to one group, and every id it counted is reachable (FR-022's measurement) |
| `join.ts` | FR-009 — `non_dominated` key → its outcome | unit: a key with no match returns the named state, not `undefined` |
| `assumptions.ts` | FR-020 — shared versus per-member, by set difference over served strings | unit: the shared set is the same for every member of a section |
| `comparability.ts` | FR-014 — do the section's rows share a span length? | unit: a boolean, and no figure in the return type |

## The screen — `src/answer/components/`

| Component | ✱ | Carries | Test |
|---|---|---|---|
| `AnswerHeader` | ✱ | FR-011 — the question as a template over typed fields, naming the benchmark instrument; FR-021's undeclared subjects as refusals. It states **no** standing: that is per section (FR-012) | unit against fixtures |
| `BeliefLine` | | FR-024 — once per screen per distinct belief id, with a link to the full statement | unit: two members leaning on one belief render one line; e2e counts occurrences |
| `SharedAssumptions` | | FR-020, FR-018 — what every member rests on, and that a rate is measured on the money invested | unit: no shared sentence appears on a card |
| `HorizonColumn` | | FR-012 — every count the section reports, its `benchmark_standing`, `standings` and `reserves`; FR-014's banner at its head; every member of `outcome`'s nine-member union and `comparison`'s two rendered as its own reason | unit: a survey refusal, a dominance refusal and a missing benchmark each render their reason and no card; each population the API sent has a count; e2e reads the standing off each column |
| `ComparabilityBanner` | | FR-014 — condition and consequence, no derived figure | unit: shown for mixed spans, absent for equal ones; e2e asserts it is above the fold |
| `MoneyBack` | ✱ | FR-016 — one served figure, `reaches`, neither added to nor subtracted from; FR-017 — the served `undeployed` record behind a disclosure, and a named state where it says the remainder did not come home; `null` `undeployed` is *nothing left over* | unit: the figure is the served one, the disclosure expands, a remainder that did not come home is named, and a `null` remainder reads *nothing left over* |
| `CandidateCard` | ✱ | FR-015's field order; FR-016/FR-017's money back; FR-019's single badge; the *indistinguishable from* line | unit: each of the three figure states, each badge variant, each kind tile, and a member with neighbours naming them |
| `FullRanking` | ✱ | FR-012 — every ranked row with all five terms, the benchmark row marked in **text**, tie groups as groups | unit: a tie group of two renders as one group |
| `RefusalGroup` | | FR-022, FR-023 — one line with its typed reason, expandable to each member | unit: never a count alone, never a blank |
| `LoadingState` / `AnswerUnavailable` | | FR-013 — a named wait and a named failure | unit both; e2e is 021's api-down scenario on `/` |

## Cross-cutting

| Thing | Carries | Test |
|---|---|---|
| `routes/overview.tsx` → the answer, browser under secondary nav | FR-028 | e2e: 021's whole-UI crawl extended to `/` |
| the venue `kind` declaration | FR-007 — the five-member closed vocabulary in `core/`, refused at load naming file and field | `tests/contract/`: a malformed kind fails at load; **tasks Phase 5** |
| `missing.ts` — the named state for an absent field | FR-010 | unit: names the field, renders no blank |
