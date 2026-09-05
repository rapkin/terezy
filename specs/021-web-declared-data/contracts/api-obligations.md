# The contract with feature 020, as the client will consume it

**Feature**: `021-web-declared-data` | **Plan**: [../plan.md](../plan.md)

The **audit** — which of OB-1 to OB-9 feature 020's draft satisfies — is
[research D1](../research.md) and is not repeated here. This file is the other half: for each
obligation, **what the client actually does with the response**, so that an implementer reading
one row knows what to build and a reviewer knows what to check.

Where an obligation is unmet, the row states what is blocked and names nothing else. The spec's
*Assumptions* fix the response: *"Where 020 does not satisfy an obligation, that is 020's
requirement to add or this feature's scope to cut — never a client-side workaround."*

| | The client's use of it | Blocked, if unmet |
|---|---|---|
| **OB-1** | `GET /registry` once per `as_of`; renders one card per category with **what the API reports for it** — a count where it is keyed, a resolved statement where it is a singleton, never `0` for a singleton (FR-014) — and its dates. Hard-codes no id: the index is the list | the overview route in full |
| **OB-2** | Maps each field to a `FieldRow` in the order returned. Label from the descriptor; provenance rendered where the field has one; an unrecognised field displayed with its raw value | **the record card**, which is the feature. [research D2](../research.md) has the fallback and its cost |
| **OB-3** | Renders the path under the card's heading, as text | `DeclaringPath`, FR-018, and SC-001's third click has nothing to land on |
| **OB-4** | Switches on the mark vocabulary with no `default` arm, so a mark the API adds turns the build red rather than rendering as nothing (FR-010). Keeps *unverified* and *stale* apart (FR-012) | the staleness half of `Provenance`; the unverified half works today |
| **OB-5** | Narrows on the tag; renders the reason where the member has one, and the member's own fields where it does not. Never a placeholder (FR-008) | nothing — this is the obligation 020 satisfies most completely |
| **OB-6** | Where the record's directory is exempt, renders `CitationExemption` with the API's reason instead of an empty citation block | **FR-013 and US1 acceptance scenario 3**, which is also the scenario Q3's argument turns on |
| **OB-7** | Plots the in-coverage observations **and** renders `CoverageRefusal` for the rest, in one view | **US3 scenario 4 and SC-007.** Conflicts with 020 FR-046 as drafted; one of the two specs moves |
| **OB-8** | On a series route with no window, reads the coverage off the list read, redirects with it in the URL, and renders from there. Chooses no window and truncates nothing | FR-027a. Met by 020's *omitted window returns the whole coverage*, with the sizing note in [research D8](../research.md) |
| **OB-9** | *(withdrawn)* — the display switch is deferred ([research D0](../research.md)). Every amount renders in the currency the API returned it in | nothing |

## The generated types, and what makes them a contract rather than a copy

| | |
|---|---|
| **Input** | `src/terezy/api/http/openapi.json` — 020 FR-038, checked in, byte-reproducible (FR-039), resolved **by package path** so generation works the same from a source checkout and from a built wheel |
| **Output** | `web/src/api/schema.d.ts`, **committed** (FR-003) |
| **Gate** | the type-sync CI job regenerates and fails on any difference (SC-013). It is **unconditional**, not filtered on a `web/` path: it exists to turn red when a *Python* change moves the document, and a path filter would disable it on the only change it was built for |
| **Prohibition** | no hand-written response type, and no cast or assertion over one (FR-005). A cast is FR-004 switched off at one site |
| **Unsettled** | the **base path**. FR-033 puts requests under `/api`; 020's document is root-relative. [research D3a](../research.md) — settle before wiring the client |

**The thing to verify before anything is built on it** (risk **R2**): that each `oneOf` member in
the real document carries its tag as a **literal** type, not as `string`. Narrowing needs the
literal; without it FR-004 has no mechanical form, and the fix belongs in 020's document rather
than anywhere in `web/`.

## What the client sends, and what it never sends

| Sends | Why it is not a silent default |
|---|---|
| `as_of`, on every request | it is in the URL, put there by the one clock read or by the reader (FR-021) |
| a **window**, on the two series reads | it is in the URL, put there from the API's own stated coverage (FR-027a, OB-8) |

| Never sends | Why |
|---|---|
| `display` | deferred ([research D0](../research.md)) |
| a **scenario** | 020 FR-007b's default is *no scenario in force*, and the response **names the scenario it resolved under** — so the client renders that statement rather than choosing a world. A third search parameter would be the client picking one |
| anything to another origin | FR-035, checked over the built output (FR-036) and over the artefact inside the image (FR-054) |
