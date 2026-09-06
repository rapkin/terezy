# Every request the answer screen makes, and what it does with the body

**Feature**: `026-answer-screen` | **Plan**: [../plan.md](../plan.md)

The **obligations** — which of OB-10 to OB-19 the API meets — are in the spec and are not repeated.
This file is the other half: for each request, what the screen reads out of it, so an implementer
reading one row knows what to build and a reviewer knows what to check.

| Request | Why | What the screen reads |
|---|---|---|
| `GET /api/questions/{id}/answer?as_of=` | the whole screen | `question` (header template, FR-011); `subjects` (undeclared → FR-021); `sections[]` — `horizon`, `outcome`'s **nine-member union** and `comparison`'s two, each refusing member rendered as its own reason (FR-012); `outcome.comparison.{ranked, benchmark, ties, beats_benchmark, refused, not_comparable}`, `outcome.enumerated.no_candidate`, `arrives_after_horizon`, `standings`, `reserves`, `dominance.{non_dominated, dominated, not_placed, incomparable, indistinguishable, benchmark_standing, separating, objectives, resolved_bands}`, `excludes`; `provenance` and `staleness` for the marks |
| `GET /api/instruments/{id}?as_of=` | one per **distinct** non-dominated member id ([plan](../plan.md) Finding 1 counts them) | the result's **tag**, and `instrument_class` where the tag carries one — a fund's read carries none (FR-006, OB-14) |

**Never requested**: `/api/registry` (FR-008 — nothing here reads a category index), and any origin
but this one (021 FR-035, checked over the built output).

## What the screen does with the answer, operation by operation

| Operation | Kind | Rule |
|---|---|---|
| `non_dominated[i]` → its `TupleOutcome` | key-equality join | permitted (FR-009). A key with no match is a named state carrying the key, never a card with empty slots |
| `ranked.length`, `refused.length`, `no_candidate.length`, `beats_benchmark.length` | count of served members | permitted (FR-009), and each count's members are reachable in one interaction (FR-012) |
| `no_candidate` → groups | grouping by typed fields | permitted (FR-009): narrow on `why.tag` **first**, then on the fields that member carries — `NothingConnects` has a `side`, `NothingNeedsToConnect` has none, and reading `side` before narrowing merges the two into one group. Never the reason text (FR-022) |
| `refused` → groups | grouping by typed fields | same rule; the discriminant is `refusal.tag` |
| `reaches` and `undeployed.amount` | two figures in two places | FR-017: each labelled by where it is, never summed into one spendable figure; `undeployed` is `null` for a whole-unit purchase, which is *nothing left over* rather than a missing field |
| span lengths all equal? | comparison | yields a **boolean** for FR-014's banner. No span range is composed — that is OB-16 |
| `outcome.rests_on` less `separating.per_member[].rests_on` | set difference over served strings | the shared assumptions, once per screen (FR-020) |
| `sold_early`, `span.end` vs `horizon.end`, `carried_quotation` | typed match | the separating badge (FR-019). Never a match over `rests_on` text |

## Marks

`marksOf(provenance, verdict)` from 021 is reused unchanged. `reaches` carries its own
`Provenance`; `implied_rate` carries none, so a rate wears the **outcome's** merged provenance and
staleness and the slot says which (OB-19). A figure that lost its mark on the way to a card is the
top-severity defect Principle I names, not a rendering detail.
