# Implementation Plan: The answer, on the home page, in one visual language

**Feature**: `026-answer-screen` | **Date**: 2026-09-06 | **Spec**: [spec.md](./spec.md)

**Branch**: this plan is written on `spec/026-answer-screen` and lands **squashed** — it is
spec-directory work, not an implementation. The implementation branch is `feat/026-answer-screen`
and lands by `--no-ff`; it may not start until `019-decision-layer` and `021-web-declared-data` are
`done` on `main` (both are, 2026-09-06) and until `fix/undeployed-remainder` is on `main` — Q2's
answer put *money back* in the engine rather than in the card (spec, *Clarifications*).

## Summary

`/` becomes the answer to the owner's declared question: a header, a belief line, three horizon
columns of non-dominated cards, and folded groups of everything else — drawn in the muted
categorical language he chose on 2026-09-06. **Zero engine changes** (owner constraint): the screen
reads what `/api/questions/{id}/answer` and `/api/instruments/{id}` serve today, and every field it
wants and does not get is a listed obligation and a named state rather than a blocker.

The plan's contribution over the spec is four findings and a build order.

**Finding 1 — the card's kind tile has a source, and it is two fields rather than one.** The answer
carries `key.instrument_id` and no class. `GET /api/instruments/{id}` answers
`interface.InstrumentDeclaration` for a bond carrying `instrument_class`, and `fund.FundDeclaration`
for a fund carrying **none** — the class is dropped at load. Where it survives it is `str` on the
record and `string` in the document, so it can carry no exhaustiveness guard: **the read's tag is what
the map is exhaustive over**, the class only separates the bond classes, and an unnamed one renders
raw. One read per distinct member id — measured 2026-09-06, **10** across the three fronts. That is
why FR-006 names an endpoint and FR-005 forbids inference.

**Finding 2 — the separating badge is derivable, and 019's own record cannot derive it.**
`SeparatingAssumptions.per_member[].rests_on` is a tuple of composed sentences, so matching one is
the string matching 014 FR-014a refuses by name — and worse, it is **empty on exactly the member
that most needs a badge**. Measured 2026-09-06, the one-month front's `UA4000239016` is the member
sold at the window's end and its `per_member` list holds **zero** sentences, because what separates
it is the *absence* of the continuation assumption its neighbour carries. A badge read off that
list would be blank on it. The typed facts are all on the member's `TupleOutcome`: `sold_early`
(a `SoldEarly` or `None`), `carried_quotation` (a `QuotationHolds` or `None`), and `span.end`
against `horizon.end` under the section's declared `continuation`. The three badge labels the
owner's mockup uses fall straight out of those:

**Two members, not the mockup's three.** `span` is first outlay to last arrival and `horizon` is the
window (`core/results/tuple.py`), so *back early, sits as cash* and *matures inside the window* are
one condition wearing two labels — measured 2026-09-06 the one-month front's `UA4000235865` (span
ends 09-19) and the twelve-month front's `UA4000239016` (span ends 2027-07-24) are the same typed
case, and reading `span.end` against `horizon.end` would have inverted them.

| Typed fact | Badge |
|---|---|
| `sold_early` is present | sold at the window's end |
| `sold_early` absent | its own terms closed it inside the window, and the proceeds sit as cash under the declared continuation assumption |
| anything else | the raw tag (FR-019) |

The third row is not decoration: an outcome running past the horizon with no `sold_early` exists — the
fund — and 015 FR-030 **withholds** it from the front rather than badging it, so nothing on a card
should claim to know what it is.

`carried_quotation` is deliberately **not** a badge: measured 2026-09-06 every member of every front
carries it, so it separates nothing and is the once-per-screen belief line instead (FR-024). The
**ranked** population is not the front — 21 of 22 rows carry it and one does not — so the row that
does not carries no mark, which is FR-024's rule rather than an exception to it.
`tests/golden/the_answer.golden.txt` says `ranked 21` because the CLI prints the benchmark row
separately; the served array holds 22.

**Finding 3 — what the screen may compute, stated before an implementer has to guess.** Three
operations look like computation and are not: a key-equality join (`non_dominated` → `ranked`),
`Array.length` over a population the API sent, and grouping by typed fields. FR-009 permits exactly
those three and nothing else. **One** operation is computation and it is bounded: comparing served
span lengths for equality to decide whether the comparability banner shows (FR-014) — which yields a
boolean, never a figure. Adding two amounts was the second, and Q2's answer removed it rather than
replacing it with a subtraction: `reaches` arrives whole and the remainder is served beside it, so the
deployed part is never composed (FR-016, FR-017).

**Finding 4 — the shared/unique split is already computed and must not be recomputed.** 019's
`per_member[].rests_on` **is** the difference; the shared set is what an outcome's own `rests_on`
holds beyond it. FR-020 is therefore a set difference over served strings, not a similarity
judgement. Measured 2026-09-06 across all three fronts: the 15 members carry **42** `rests_on`
entries between them and only **14** distinct sentences, **2** of which every member of every front
shares — so the folding puts 14 lines on the screen instead of 42, and the 2 go once.

## Technical Context

**Language**: TypeScript, `strict`, in the existing `web/` tree. No Python changes except FR-007's
venue `kind` (schema, core record, loader, `data/venues.toml`).

**Primary dependencies**: none added. React, TanStack Router + Query, Tailwind, the copied shadcn
components, Vitest, MSW and Playwright are all in `web/package.json` already. Icons are hand-written
SVG components in this repository, not a package — the mockup's 24-grid outline set at stroke 1.75.

**Testing**: Vitest + React Testing Library with MSW handlers typed from the same OpenAPI document
(021 FR-044); Playwright against the real API on loopback over the shipped `data/`, offline.

**Constraints**: same origin, no run-time egress, loopback only — 021 FR-034 to FR-037 unchanged.
The answer document's size (OB-10) is why the fetch has a named loading state (FR-013) and why the
page must not also fetch the registry (FR-008).

## Constitution Check

| Principle | How this feature stays inside it |
|---|---|
| **I — honesty over precision** | Dominance is what the screen leads with, which is the preference order's first form. Nothing is rounded into a point estimate; a refused rate renders as a refusal. |
| **II — data, not code** | The one domain fact this feature adds is a venue's `kind`, and it goes in `data/venues.toml` behind a closed vocabulary refused at load (FR-007). No engine branch. |
| **III — pure core** | Untouched. The client is a client over HTTP. |
| **IV — explicit failure** | FR-010: a missing field is a named state. FR-023: a refusal group is a line with its reason, never a count alone. |
| **VI — the whole tuple** | FR-015's card carries the instrument, and the folded ranking carries all five terms per row — a row headed by an id alone is the complaint `cli/main.py::_candidate` already answers, on a screen. No display role, no conversion, no rate consulted. |
| **VII — private** | No new dependency, no new origin. |

**Prose discipline**: `web/` is deliberately outside `check_prose_budget.py` and
`check_enumerations.py` (021's own reasoning, unchanged) — the enumerations this feature could
overstate are enforced by the typecheck instead (FR-004, FR-019).

## Project structure

```text
specs/026-answer-screen/
├── spec.md
├── plan.md                     # this file
├── tasks.md
├── contracts/
│   ├── components.md           # what is built, what it carries, what holds it
│   └── api-reads.md            # every request the page makes, and what it does with it
└── checklists/requirements.md

web/src/
├── design/                     # the language: tokens, kinds, icons, badges
│   ├── kinds.ts                # kind -> hue, exhaustive over the declared vocabulary
│   ├── icons/                  # one outline component per kind
│   └── format.ts               # FR-026, the one formatting module
├── answer/                     # the screen
│   ├── separating.ts           # typed fact -> badge (Finding 2)
│   ├── grouping.ts             # typed discriminants -> refusal groups (FR-022)
│   └── components/
└── routes/overview.tsx         # becomes the answer; the browser moves under /data
```

## Build order, and why it is this one

**Phase 1 — the language, with no API in it.** Tokens, the kind map with its exhaustiveness test,
the icon set, the badge tones, the formatting module. Every one is testable against fixtures and
none needs a response, so it lands and is reviewed before anything can hide behind a network call.

**Phase 2 — the pure functions over served shapes.** `separating.ts`, `grouping.ts`, the key join,
the shared/unique split. Each takes a typed value and returns a typed value; each is unit-tested
against MSW fixtures typed from the document. Still no screen.

**Phase 3 — the components.** Card, column, banner, header, folded groups — assembled from 1 and 2,
tested with fixtures.

**Phase 4 — the route.** `/` becomes the answer; the browser moves to secondary navigation; the
loading and failure states wire up; Playwright runs against the real API.

**Phase 5 — the venue `kind`**: the five-member vocabulary the owner named, the schema field, the
loader refusal, the nine data lines, and the tests that a malformed kind fails at load naming file
and field. Last because nothing on this screen draws a venue, so it cannot block 1 to 4.

## Risks

- **R1 — the size of the fetch (OB-10).** Not a blocker on loopback and not measured in a browser
  yet. If it is
  worse than the loading state can excuse, the remedy is OB-10 and not a client-side trim, which
  would be the truncation FR-008 forbids. Recorded as a `[[future]]`.
- **R2 — `carried_quotation` on every member today.** Finding 2 rests on a measurement, not a
  guarantee. If a future registry produces members that differ on it, the belief line stops being
  once-per-screen and becomes a badge — which is why FR-024 says *once per distinct belief id*
  rather than *once*.
- **R3 — the kind vocabulary drifting from the drawn kinds.** `instrument_class` has three members
  and the language names four instrument kinds (cash and held asset arrive with 023 and 025). The
  exhaustiveness test (FR-004) is over the **declared** vocabulary, so a fourth class turns the build
  red rather than rendering as nothing.
