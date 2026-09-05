# Data model: what the client renders

**Feature**: `021-web-declared-data` | **Plan**: [plan.md](./plan.md)

There is no client-side data model in the ordinary sense: the client stores nothing, derives
nothing and owns no type for a response body (FR-005). What follows is therefore a model of
**what arrives and how it is rendered**, and every type below is one of three things, marked in
the *Origin* column:

- **generated** — comes from `web/src/api/schema.d.ts`, produced at build time by 020's
  `scripts/generate_openapi.py` and gitignored (FR-003). Never hand-written, never cast over.
- **narrowed** — a generated type reached through a runtime guard in `lib/provenance.ts`. A guard
  *tests* and narrows; a cast *asserts*. FR-005 forbids the second and permits the first, and the
  two compile to the same thing, which is why the distinction is written down.
- **client** — a type this feature owns because it is about *rendering*, not about the wire. The
  only ones permitted, and each is listed here so the list is a check.

## The three states every figure has

FR-007. This is the model's centre; everything else is a container for it.

```
FigureState =
  | { kind: "value";   … }        the API returned a figure and nothing marks it
  | { kind: "marked";  … }        the API returned a figure and its provenance marks it
  | { kind: "refused"; … }        the API returned a refusal instead of a figure
```

**Origin: client.** It is a rendering discriminant, not a wire shape — the API sends an amount with
its provenance, or a tagged refusal, and this union is how one component decides between them. It
is permitted because FR-007 is a requirement about a **component**, and because the mapping from
what arrived to which state is a narrowing over generated types with no invented facts in it.

**The prohibitions travel with it.** FR-008: `refused` never renders as a blank cell, `0`, `—`,
`n/a`, or an empty series. A component with a figure slot and no `refused` arm does not satisfy
FR-007, and SC-002 asserts that by **enumerating** the figure-bearing components rather than by
review.

## What arrives

| Entity | Origin | Fields the screen uses | Requirement |
|---|---|---|---|
| **Category** | generated | id; shape (keyed \| singleton); **a record count where keyed and a resolved-flag where singleton** — the two are different facts and rendering a singleton as `0` collapses `B10` (FR-014, 020 FR-009); merged provenance; unverified count | FR-014, and OB-1's *characterising dates* read as the merged provenance's source dates ([research D1](./research.md)) |
| **Record** | generated | identified by the **pair** `(category, id)` — never by id alone (*Edge Cases*) | FR-016 |
| **Field** | narrowed | label, value, type; and where the value is observed, its provenance | FR-016, FR-017 — **and the obligation 020 does not yet promise**: OB-2. [research D2](./research.md) records the fallback and its cost |
| **Provenance** | generated | `id`, `citation`, `retrieved_on`, `verified_on`, `kind`, and the derived `is_unverified` | FR-017. `is_unverified` is **read, never recomputed** — 020 FR-018 says why: a client computing it is free to get the asymmetry backwards, and the answer would then depend on which client was reading |
| **Staleness verdict** | generated | whatever wire shape 020 gives it | FR-012 — *unverified* and *stale* are different claims and neither implies the other. 020's shape for this is unstated ([research D1](./research.md), OB-4) |
| **Refusal** | generated | the tag, the reason **where there is one**, and the member's own fields verbatim | FR-007, FR-008. Under 020's clarification 3, `reason` is `string \| undefined` on nine members, so the component narrows on the **tag** first ([research D4](./research.md)) |
| **Citation exemption** | generated | that the record's directory is exempt from the citation requirement, and the reason | FR-013 — **unmet by 020 today** (OB-6), and the obligation US1 scenario 3 rests on |
| **Declaring file path** | generated | the path of the file that declares this record | FR-018 — **unmet by 020 today** (OB-3) |
| **Synthetic flag** | generated | where the API sends one | FR-019 — and it must be on the record, never inferable only from a directory name |
| **Series** | generated | identity; **what the values are in** (a quotation unit, or a base description); coverage window; observations in the requested window; a typed refusal for whatever part falls outside it | FR-027–FR-030. The last two **in one response** is OB-7, which conflicts with 020 FR-046 ([research D1](./research.md)) |
| **Observation** | generated | its date or period, its value, and **its own** provenance | 020 FR-047: per-observation, never the series'. FR-032's table carries each point's mark |
| **Resolved scenario** | generated | which scenario the category read resolved under, including *none* | 020 FR-007b. The client sends no scenario and **renders the statement the response carries**, so the default is stated rather than silent ([research D1](./research.md)) |

## What the URL holds

| Parameter | Where | Origin of its value | Requirement |
|---|---|---|---|
| `as_of` | every route | the **one** clock read, written by a redirect on a first load without it | FR-020, FR-021, FR-021a |
| window | the two series routes only | the series' API-stated coverage, fetched from the list read and written by a redirect | FR-027, FR-027a, OB-8 |

**`display` is not here.** The switch is deferred by owner decision 2026-09-03
([research D0](./research.md)); `as_of` is the only global parameter, and the two series routes add
one. That is the whole set, and SC-008a asserts a first load ends at a URL carrying **every
parameter that route takes** — asserting that they arrive, never a value, which is FR-048's one
exception for it.

Both parameters are validated by the router **per route** (FR-020, FR-027). An invalid value is a
visible error naming the parameter; no default is silently substituted, which is the same
prohibition Principle IV puts on a malformed data field one layer down.

## What the client is forbidden to hold

Stated as a model entry because an absent thing is easiest to add back by accident.

- **No copy of `data/`**, no TOML reader, and nothing derived from a file path beyond displaying it
  (spec *Assumptions*, FR-018).
- **No store.** There is no client state: everything on screen is a function of the URL and a
  response, so a store would be a cache of the router and of TanStack Query.
- **No hand-written response type**, and no cast over one (FR-005). The only hand-written shapes in
  the tree are the `client`-origin rows above and the unit-test fixtures, and a fixture is a
  component's input rather than a response type.
- **No second clock.** One read, in `clock.ts`, protected by a lint rule (FR-021a).
- **No computed ordering.** A list may be ordered by a field the API returned and by no field the
  client derived (FR-002): an ordering the client computed is a ranking the engine did not make.
