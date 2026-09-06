# Implementation Plan: Two regimes, side by side, and what the belief moved

**Branch**: `spec/028-scenarios` (implementation: `feat/028-scenario-comparison`) |
**Date**: 2026-09-07 | **Spec**: [spec.md](./spec.md)

## Summary

A second screen in the web client. It reads two declared questions' answers at one `as_of`,
matches their horizon sections by date, and marks each member of the union of the two
non-dominated sets as *on the front in both*, *in this column only*, or *in that one only* —
saying, for a member on one front only, what the other column's own record does with that key.
Each column names the regime it ran under and, where that regime is a declared scenario's, says
the scenario is a belief and names the gap it does not cover. Nothing computes a figure and
`src/terezy/` does not change.

## Findings that shaped the design

Six, distinct from the spec's three measurements. F1, F2 and F5 were read in the shipped data
and code on 2026-09-07; F3, F4 and F6 are decisions taken here.

### F1 — The dominance buckets do not cover `ranked`, and the missing row is not an error

At each of the owner's three horizons, `outcome.comparison.ranked` holds 22 rows and
`non_dominated ∪ dominated` holds 21. `not_placed` and `incomparable` are both empty. The
twenty-second is `inzhur_miltech`, which is in `sections[].arrives_after_horizon` — withheld
from the dominance pass because its money arrives after the horizon (015 FR-030), exactly as
019's own *evaluated = non-dominated + dominated + not placed* is scoped to the **evaluated**
population and not to the ranked one.

A client that decided *not enumerated there* by failing to find a key in the dominance buckets
would therefore report a candidate as removed by the regime when the answer merely withheld it.
That is the false statement this feature exists not to make, so the lookup order is fixed and
total (contracts/api-reads.md), and the test that pins it uses this row.

### F2 — `indistinguishable` and `incomparable` are overlays, not buckets

Measured: at one month, `indistinguishable` holds 4 members and every one of them is also in
`non_dominated` or in `dominated`. It answers *near which others*, not *where*.
`incomparable` is worse than an overlay — it is a property of a **pair**, carrying `left` and
`right` and no state for either one, and removing neither from any other pair's verdict, so one
key can be dominated and incomparable at the same time. Reading either as a placement reports a
state the answer did not give the key, which is why the lookup has neither as a step.

### F3 — The key is compared structurally, and the client's canonical form is its own

The served key is a nested record of five terms. Equality is over the five terms, so the client
builds a deterministic string from them once, in one module, and uses it as a map key. It does
**not** reproduce `core/results/canonical.py::of_tuple_key`'s byte order: that ordering is the
engine's digest contract, copying it here would put one fact in two places, and nothing about
this screen needs the two strings to agree — only that the client's own function is total and
injective over the five terms.

### F4 — The question difference excludes exactly two fields, and says why

`id` and `asked_on` are excluded from the field-by-field comparison: two questions necessarily
differ in the first, and the second dates the declaration rather than describing the comparison.
Every other field of the served question record is compared and named when it differs. The rule
is mechanical, so no judgement about which difference "matters" is made in the client.

### F5 — One regime declared by two scenarios is resolved by the first scenario id

`api/answer.py::_scenario_of` walks the declared scenarios sorted by **scenario id** — which the
declaration states and the filename need not match — and returns the first whose regimes include
the id; duplicate regime ids are refused only *within* one scenario. So two scenarios naming one
regime is loadable, the answer runs under whichever id sorts first, and the manifest records the
regime and not the scenario. The screen therefore names every scenario
declaring the regime and says the record does not settle which was searched — a `[[future]]`
carries the engine-side remedy, which is not this feature's to make.

### F6 — What the two clarifications gate

Clarification 1 gates only whether a second declared question exists; every task below is
written against whatever the questions category serves, and the shipped-root acceptance case is
the degenerate one (the same question in both columns). Clarification 2 gates the **shape** of
FR-017 — a caveat or a refusal — and therefore one component and one test, which the task list
puts in a phase that may not start until it is answered.

## Technical Context

**Language/Version**: TypeScript 5, React 19 — the `web/` tree, unchanged in stack.

**Primary Dependencies**: TanStack Router and Query, and the types generated at build time from
the API's OpenAPI document. No dependency is added.

**Storage**: none. The screen holds no state beyond the URL and the query cache.

**Testing**: Vitest for the pure functions and the components; Playwright against the real API
on loopback over the shipped `data/`; pytest for the one contract test.

**Target Platform**: a browser on loopback, one owner, no network beyond the app's own origin.

**Project Type**: web client over a published HTTP schema.

**Performance Goals**: one answer read per distinct `(question id, as_of)`, plus the question
and scenario reads the labels need, and no registry read (FR-025).

**Constraints**: no figure computed in the client; no request carries a scenario; every refusal
reaches the reader with its reason.

**Scale/Scope**: one route, four pure modules, six components, one contract test.

## Constitution Check

| Principle | How this feature stands |
|---|---|
| I — Honesty over precision | The screen emits no number of its own. Its one non-served sentence (FR-017) is a stated gap with a recorded remedy, carrying no figure. A scenario renders as the assumption its declaration marks it. |
| II — Framework, not script | Nothing here is a branch on an instrument, a venue, a route or a regime. Scenarios and questions are data; this reads what is declared and refuses what is not. |
| III — Pure deterministic core | `src/terezy/` is untouched. The client's pure modules are total functions over served records. |
| IV — Stated contracts | Every state is named, including *not enumerated there* and *withheld from the pass*. No blank, no dash, no zero. No tolerance is introduced: nothing here compares two floats. |
| V — Test-first | Each pure module lands with its Vitest suite failing first; the end-to-end case runs against the real API; the contract test asserts a regime reaches the answer. |
| VI — The whole tuple | The membership key is all five terms. Merging two rows that share an instrument id is explicitly forbidden and is what F3's key function exists to prevent. |
| VII — Owner-scoped, private | Loopback only, one owner, no new dependency, no outbound call. |

No violation, so the Complexity Tracking table is omitted.

## Project structure

```text
web/
├── src/
│   ├── compare/
│   │   ├── key.ts                    # F3: the five-term key as a string
│   │   ├── membership.ts             # FR-008 to FR-012: horizons, union, marks, the lookup
│   │   ├── difference.ts             # F4, FR-019 to FR-021
│   │   ├── regime.ts                 # FR-015, FR-016, FR-018: regime -> scenario, belief
│   │   └── components/
│   │       ├── MembershipMark.tsx    # FR-010, FR-011, FR-024
│   │       ├── HorizonPair.tsx       # FR-008, FR-010, FR-012, FR-014
│   │       ├── ColumnHead.tsx        # FR-015 to FR-018, FR-022
│   │       ├── QuestionDifference.tsx# FR-019 to FR-021
│   │       ├── ComparePicker.tsx     # FR-004 to FR-006
│   │       └── CompareStates.tsx     # FR-003, FR-023
│   ├── routes/compare.tsx            # FR-001, FR-002
│   ├── search/params.ts              # edited: the two question-id parameters
│   └── api/queries.ts                # edited: the second answer read, keyed by id and as_of
├── tests/unit/                       # the Vitest suites, one per module and component
├── tests/fixtures/compare/           # two recorded served answers, checked in
└── e2e/compare.spec.ts               # FR-027

tests/contract/test_a_regime_reaches_the_answer.py   # FR-028
tests/fixtures/data/questions/                       # two fixture questions differing only in regime
tests/fixtures/data/scenarios/                       # a fixture scenario declaring their regimes
```

**Structure Decision**: a `web/src/compare/` tree beside `web/src/answer/`, on 026's own shape —
pure functions in modules, components under `components/`, one route file. The pure modules are
separated from the components because every membership claim this feature makes is decidable
without rendering, and that is what makes the Vitest suites cheap and the claims checkable.

## Build order, and why it is this one

1. **The key, then the lookup.** `key.ts` before `membership.ts`: every other module keys on it,
   and F1's false statement is only reachable once the lookup exists.
2. **The pure modules before any component.** Each lands with its suite over the checked-in
   recorded answers, failing first. A component built over an unfixed lookup would pin the bug.
3. **The recorded fixtures before the pure modules.** Two served answers, one pair with fronts
   that differ, checked in beside the tests that read them. They are recorded from the real API
   rather than written by hand, so a shape drift shows up as a test failure and not as a fiction.
4. **The route and the picker last of the shipping surface**, because they are what makes the
   screen reachable and everything they compose is by then tested.
5. **The contract test at any time** — it depends on nothing here and is the Python half.
6. **FR-017's component in its own phase**, which may not start until Clarification 2 is answered.

## Risks

- **R1 — a served population is added or renamed and the lookup silently loses totality.** The
  mitigation is the shape of the test rather than a scan: the lookup asserts that every key in
  `enumerated.candidates` resolves to exactly one named state, over the recorded pair, so a new
  population makes that assertion red rather than making a row read *not enumerated*.
- **R2 — the fixtures go stale against the API.** They are recorded output, so a shape change
  makes the Playwright case red while the Vitest suites stay green on old bytes. What keeps the
  two honest is that the end-to-end case asserts the same marks the unit suites do, over live
  bytes; nothing re-records the fixtures automatically, and a drift is a red e2e beside a green
  unit run.
- **R3 — Clarification 1 answered as C.** Then the shipped screen has one column of substance
  and the second is the named empty state. Everything is still built and tested; what is missing
  is a demonstration, and the spec says so.
