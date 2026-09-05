# Component inventory

**Feature**: `021-web-declared-data` | **Plan**: [../plan.md](../plan.md)

Every component the feature builds, the requirement it carries, and the test that holds it. The
inventory is a **contract, not a description**: SC-002 asserts that 100% of the figure-bearing
components have a refusal state and a marked state *by enumerating them*, and this table is what
that enumeration is checked against.

**✱ marks a figure-bearing component** — one that has a slot where a figure appears. **Four carry
it**, and **T042** is the test that walks them. Each must have a `refused` arm and a `marked` arm
(FR-007); one with a figure slot and neither is a defect, not a simpler component.

`Mark`, `Refusal` and `CoverageRefusal` are **not** marked: they *are* those states, and demanding a
refused arm on a refusal is the enumeration eating itself. `Provenance` is not marked either — it
renders dates and a citation, not a figure. What **is** marked is every component with a place a
number, an amount or an observation can appear: `FigureSlot`, `FieldRow`, `SeriesChart`,
`SeriesTable`.

## Figure primitives — `src/components/figure/`

These are the feature. Everything else is a container for them.

| Component | ✱ | Carries | Test |
|---|---|---|---|
| `FigureSlot` | ✱ | FR-007's three states, and FR-008's prohibition on rendering `refused` as a blank, `0`, `—`, `n/a` or an empty series | unit: each of the three states renders; the `refused` state renders none of FR-008's five placeholders |
| `Mark` | | FR-009 — the mark is carried in **text**. FR-010 — the vocabulary comes from the generated types | unit: the assertion **strips every style declaration first**, then reads the mark, the reading `tests/contract/test_diagram_marks.py` already applies to diagrams |
| `Refusal` | | FR-007's reason verbatim, and what would supply the figure where the API sends it. Narrows on the **tag** before the reason, because `reason` is optional on nine members ([research D4](../research.md)) | unit: a refusal **with** a reason renders it; a refusal **without** one renders the tag and the member's own fields, and neither renders a placeholder |
| `Provenance` | | FR-017 — citation, `retrieved_on`, `verified_on`; an empty `verified_on` renders as the unverified mark and never as an empty field. FR-012 — *unverified* and *stale* stay distinct | unit: an empty `verified_on` produces the mark; a stale-but-verified source produces the stale mark and not the unverified one |
| `CitationExemption` | | FR-013 — an exempt directory renders the exemption **with its reason**, never an empty citation block. Under Q3's answer this is also what labels a per-owner record as the owner's **statement** rather than an observation | unit against a fixture, and e2e against the shipped tree — exercisable because Q3 resolved to showing them ([research D11](../research.md)) |

## Record — `src/components/record/`

| Component | ✱ | Carries | Test |
|---|---|---|---|
| `RecordCard` | | FR-016 — **every** field the API returns, in the order returned; an unrecognised field displayed generically, never dropped. FR-011 — marks are per figure; a card-level banner may summarise and may not replace them | unit: a fixture carrying a field the component has no special rendering for still renders its raw value (US1 scenario 4); a card whose every field is unverified shows a mark on **each**, not one banner |
| `FieldRow` | ✱ | one field: label, value, type, and its provenance where observed | unit, with the three states |
| `DeclaringPath` | | FR-018 — the path of the file that declares the record (OB-3) | unit; **blocked on 020** |
| `SyntheticFlag` | | FR-019 — rendered on the record, never inferable only from a directory name | unit |
| `LongValue` | | *Edge Cases* — a value that is itself a long citation string is shown **in full**, not elided to a fixed length with no way to see the rest | unit: a multi-sentence value is fully reachable |

## Category — `src/components/category/`

| Component | ✱ | Carries | Test |
|---|---|---|---|
| `CategoryIndex` | | FR-014 — the categories the API indexes, each with its record count and the dates it is characterised by. FR-015 — **no hard-coded category id, label or branch** | unit against a fixture index; the id scan is e2e (FR-015 needs the running API's index) |
| `CategoryCard` | | one category's dates, and what the API reports for it: a count where it is keyed, a **resolved statement** where it is a singleton — never `0` for a singleton (FR-014) | unit: a keyed fixture and a singleton fixture render differently, and neither renders the other's shape |
| `RecordList` | | the records of one category | unit |
| `EmptyCategory` | | *Edge Cases* — a category with no records renders as a category with none, **with the API's own statement of why** where it has one. An empty list and an absent category must not look the same | unit: the two fixtures render differently |

## Series — `src/components/series/`

| Component | ✱ | Carries | Test |
|---|---|---|---|
| `SeriesChart` | ✱ | FR-028 — plots exactly the observations returned; a gap is a **break with its own label**, never interpolated, carried forward or extended past coverage. FR-030 — the axis states the API's declared identity and what the values are in, never bare and never inferred. FR-031 — a **one-observation** series is one point, no line. FR-031a — a **retrieval** is not a series and is not charted | unit, and FR-031/FR-031a are unit-only **by design**: neither shape is reachable from either routed series, and an acceptance scenario no run can execute is a green box over an unasserted claim |
| `SeriesTable` | ✱ | FR-032 — the same rows, keyboard-reachable, each point carrying its mark and any per-point refusal. FR-041 — it is the accessible equivalent of every chart | unit: keyboard reach; each row's mark present as text |
| `CoverageRefusal` | | FR-029 — a window reaching outside coverage renders the refusal **in place of the missing part and never in place of the whole chart** | unit; e2e is US3 scenario 4 and **depends on 020 settling OB-7's ambiguity** ([research D1](../research.md)) |

## Shell — `src/components/shell/`

| Component | ✱ | Carries | Test |
|---|---|---|---|
| `AppShell` | | FR-038 — keyboard reach, visible focus, no focus trap | e2e a11y, both themes |
| `SkipLink` | | FR-038 — each route offers a skip link to its main content | e2e a11y |
| `AsOfControl` | | FR-020's error state, FR-022's re-query. It **displays** `as_of` and edits the URL; it reads no clock | unit: changing it re-queries and recomputes nothing locally |
| `ThemeToggle` | | FR-042 — follows the OS setting and is switchable; changes no value, no mark and no ordering | unit: a rendered figure is identical across themes |
| `ApiErrorState` | | FR-006 — a transport failure and a non-2xx response are each a **named** state. Neither presents as an empty list, an empty chart or an unresolved spinner | unit, both cases; e2e is US2 scenario 4 |
| `ParameterError` | | FR-020 — an invalid parameter is a visible error **naming the parameter**, with no default substituted | unit; e2e is US4 scenario 2 |

**No `CurrencySelector`.** The display switch is deferred ([research D0](../research.md)), so the
component that would have carried FR-024a and FR-026 is not built and Q2 is moot. It returns with
the `[[future]]` entry, and it returns as an addition to a `FigureSlot` that already has three
states rather than as a change to one.

## Cross-cutting, not components

| Thing | Carries | Test |
|---|---|---|
| `lib/exhaustive.ts` — `assertNever` | FR-004's mechanism | SC-003: a member added to a **copy** of the document turns the build red |
| the lint rule forbidding a `default` arm | FR-004's other half — a `default` arm absorbs the new member and switches `assertNever` off | lint config test; risk **R1** ([research](../research.md)) |
| `clock.ts` | FR-021, FR-021a — the **one** clock read | lint rule fails any other `new Date()` / `Date.now()` in `web/src`, with this module the sole listed exception |
| `search/params.ts` | FR-020, FR-027 — typed validators for `as_of` and the window | unit: an invalid value produces a named error and no substitution |
| `api/client.ts` | FR-035 — `baseUrl` is `/api`, same origin, always | unit; and the e2e abort handler, which fails the suite on any request to another origin |
