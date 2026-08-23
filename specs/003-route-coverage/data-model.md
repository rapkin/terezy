# Phase 1 data model: the coverage report

**Feature**: `003-route-coverage` | **Date**: 2026-08-22 | **Spec**: [spec.md](./spec.md)

Every record here is a frozen dataclass (`frozen=True, slots=True, kw_only=True` where it
has more than two fields), in the functional style owner decision D-E requires: records and
free functions, no classes with behaviour. Every collection is a `tuple` in a stated order
(research.md D9), so the same declarations produce the identical report.

**No `Money`, no `Provenance`, no `StalenessVerdict`, no `float` appears anywhere below.**
That is FR-017 and FR-023, and it is enforced by a recursive type walk, not by review
(research.md D12).

---

## Declared input: the spendable-endpoint list

### `SpendableEndpoint` — `core/routes/coverage.py`

| Field | Type | Meaning |
|---|---|---|
| `venue_id` | `str` | A declared venue the owner actually spends from |
| `currency` | `Currency` | Base currency only, in practice UAH (FR-004) |

Validation, at the data layer:

- `venue_id` must name a declared venue — unknown ids fail at load, naming file and field,
  on the loader's existing `_known` path.
- `currency` must be the base currency the declarations were resolved against. FR-004 says
  base currency only; a spendable endpoint in USD would be the report quietly deciding that
  foreign cash counts as spent.
- The venue must be able to hold that currency (`Venue.currencies`). A spendable endpoint at
  a venue that cannot hold hryvnia is a contradiction, and the loader already owns exactly
  this check for legs.
- Duplicate `(venue_id, currency)` pairs are refused, on the loader's existing duplicate-id
  precedent.
- An empty list is refused (research.md D13).

## Loading entry point: which declarations, and under whose belief

### `CoverageDeclarations` — `data/declarations/resolver.py`

| Field | Type | Meaning |
|---|---|---|
| `ramp` | `RampDeclarations` | Venues, streams, routes, channels, kinds, scenarios |
| `spendable` | `frozenset[SpendableEndpoint]` | The resolved list |
| `spendable_file` | `Path` | Which file declared it |
| `scenario_id` | `str \| None` | Which belief the audit runs under; `None` is FR-015's implicit regime |
| `regimes` | `Mapping[str, Regime]` | That scenario's regimes by id — the `regimes` argument of `coverage()`. Empty when `scenario_id` is `None` |

`resolve_coverage(*, ramp, spendable_file, scenario_id)` and
`coverage_from_data_root(root, *, base_currency, scenario_id)` are the two entry points, and
`scenario_id` is **required and nullable** on both (research.md D17). One scenario's regimes
reach the audit, never two blended; an unknown id is refused at load rather than falling back
to the implicit regime. Without this the loader could produce no `regimes` mapping at all and
the shipped registry's declared regimes could not reach FR-013.

## The destination universe

### `Destination` — `core/routes/coverage.py`

| Field | Type | Meaning |
|---|---|---|
| `venue_id` | `str` | Declared venue |
| `currency` | `Currency` | A currency that venue declares it can hold |

Derived, never declared: the product of every declared venue and its `currencies`
(FR-001 ⚙, research.md D5). Sort order `(venue_id, currency.value)`.

## Verdicts

### `RouteRelied`

| Field | Type | Meaning |
|---|---|---|
| `route_id` | `str` | A declaration the verdict rests on |
| `status` | `RouteStatus` | `open` / `constrained` / `closed`, carried from the declaration |

### `Ready`

| Field | Type | Meaning |
|---|---|---|
| `destination` | `Destination` | |
| `stream_id` | `str` | |
| `inbound` | `tuple[RouteRelied, ...]` \| `SATISFIED_BY_ARRIVAL` | Every matching inbound route, or the sentinel of FR-005 |
| `exits` | `tuple[RouteRelied, ...]` \| `SATISFIED_BY_IDENTITY` | Every exit route reaching a declared spendable endpoint, or the sentinel of FR-002 ⚙ |
| `rests_on` | `Literal["open", "constrained", "closed_only"]` | FR-022 / SC-015, derived per research.md D10. Neither sentinel is a route, so neither contributes a status and neither can be closed |

`SATISFIED_BY_ARRIVAL` is a distinct sentinel value, not an empty tuple: FR-005 requires
"satisfied by arrival" to be explicitly distinct from "satisfied by a route", and an empty
tuple would read as "nothing relied on", which is a different claim.

`SATISFIED_BY_IDENTITY` is its mirror on the exit side, added by the owner decision of
**2026-08-23** (FR-002 ⚙): a destination that is itself a declared spendable endpoint has its
way out satisfied without any corridor, because the money is already where it needed to come
back out to. Same shape and same reason as the arrival sentinel — a single-member `Enum`, so
"already spendable" can never be read as "a declared route gets the money out", and so a
`match` over either half of the rule reads the same way.

⚙ **Both sentinels supersede the routes they stand in for.** A pair satisfied by arrival does
not list matching inbound routes, and a spendable destination does not list its declared exits:
the verdict rests on the money's position, and nothing is *relied on*. On the arrival side that
loses nothing real — a superseded inbound route would have to run from a venue to itself — but
on the exit side it is a real loss, and it is taken deliberately so the two halves behave
identically. Such an exit is still listed as an orphan where its origin is unreachable.

`inbound` and `exits` list **every** match, not the first. The edge case "two inbound
routes to one destination, only one with an exit partner" requires the partner-less inbound
to stay visible, and a ready verdict that named one route would hide it.

### `Deficit`

| Field | Type | Meaning |
|---|---|---|
| `kind` | `Literal["no_inbound", "no_exit_declared", "exit_not_spendable"]` | The three of FR-003, read per research.md D7. Neither exit kind is ever produced for a destination in the spendable set (FR-002 ⚙) |
| `missing` | `MissingDeclaration` | What to go observe |
| `observed_exits` | `tuple[RouteRelied, ...]` | For `exit_not_spendable` only: the exits that exist and where they end. Empty otherwise |

`observed_exits` is what stops deficit 3 from reading like deficit 2: the owner can see that
a way out was declared and why it does not count.

### `NotReady`

| Field | Type | Meaning |
|---|---|---|
| `destination` | `Destination` | |
| `stream_id` | `str` | |
| `inbound` | `tuple[RouteRelied, ...]` \| `SATISFIED_BY_ARRIVAL` | What does exist on the inbound side; empty tuple when the deficit is `no_inbound` |
| `deficits` | `tuple[Deficit, ...]` | One or two: at most one inbound deficit and at most one exit deficit (research.md D7). Never empty |

`PairVerdict = Ready | NotReady` — a tagged union, matched on, never a `ready: bool` flag.

## Missing declarations and the to-do list

### `MissingDeclaration`

| Field | Type | Meaning |
|---|---|---|
| `direction` | `RouteDirection` | `inbound` or `exit` |
| `origin_venue` | `str` | Where the corridor starts: the stream's arrival venue, or the destination's venue |
| `origin_currency` | `Currency` | The currency it starts in |
| `target` | `Destination` \| `ANY_SPENDABLE` | The destination for an inbound; the sentinel for an exit (FR-007 ⚙) |
| `candidates` | `tuple[SpendableEndpoint, ...]` | For an exit: the declared spendable endpoints, any one of which satisfies it. Empty for an inbound |

**No regime field, deliberately** (research.md D8): value equality is what makes the same
missing declaration in two regimes recognizably one declaration.

**No interior hops** (FR-007 ⚙): endpoints only. Naming the hops of an unobserved corridor
would be inventing the very link the report exists to refuse to invent.

**No values of any kind** (FR-008): no provider, fee, premium, cap, latency or rate. There is
no field here one could live in, which is how SC-004 is satisfied across the whole output
rather than sampled.

### `BlockedPair`

| Field | Type | Meaning |
|---|---|---|
| `destination` | `Destination` | |
| `stream_id` | `str` | |
| `alone_sufficient` | `bool` | `False` when the pair also needs another missing declaration (FR-011) |

### `TodoEntry`

| Field | Type | Meaning |
|---|---|---|
| `missing` | `MissingDeclaration` | |
| `blocked` | `tuple[BlockedPair, ...]` | Sorted by `(venue_id, currency, stream_id)` |
| `count` | `int` | `len(blocked)`, carried so the ordering claim is readable (FR-009) |

### `Observation` — the cross-regime view

| Field | Type | Meaning |
|---|---|---|
| `missing` | `MissingDeclaration` | |
| `blocked_by_regime` | `tuple[tuple[str, int], ...]` | `(regime_id, count)`, sorted by regime id |

One entry per distinct missing declaration across the whole report. **Never summed**
(FR-014): which observation to make is one decision, but what it unlocks differs by regime,
and the owner weighs regimes, not the tool.

### `OrphanExit`

| Field | Type | Meaning |
|---|---|---|
| `route_id` | `str` | |
| `origin` | `Destination` | The destination it leaves, which no stream can reach in this regime |
| `reaches_spendable` | `bool` | Whether it lands on the declared spendable list |

Listed, never counted as a deficit and never blocking anything (FR-012, SC-017). It is an
observation already made that nothing yet uses.

## The report

### `RegimeCoverage`

| Field | Type | Meaning |
|---|---|---|
| `regime_id` | `str` | |
| `source` | `Literal["declared", "implicit"]` | FR-015, research.md D14 |
| `route_ids` | `tuple[str, ...]` | The regime's route set, sorted — what this block audited |
| `verdicts` | `tuple[PairVerdict, ...]` | Every `(destination × stream)` in the declared universe, sorted by `(venue_id, currency, stream_id)`. No pair may be absent (FR-001) |
| `todo` | `tuple[TodoEntry, ...]` | Ordered by descending `count`, then by identity for determinism only |
| `ties` | `tuple[tuple[int, ...], ...]` | Index groups in `todo` with equal counts (FR-010, research.md D9) |
| `orphan_exits` | `tuple[OrphanExit, ...]` | Sorted by route id |

### `AuditedDeclarations`

| Field | Type | Meaning |
|---|---|---|
| `venue_ids` | `tuple[str, ...]` | |
| `stream_ids` | `tuple[str, ...]` | |
| `route_ids` | `tuple[str, ...]` | |
| `regime_ids` | `tuple[str, ...]` | Empty when the implicit regime was used |
| `spendable` | `tuple[SpendableEndpoint, ...]` | |

All sorted. Ids, not paths — core cannot import `pathlib`, and the data layer already keeps
the file maps beside the ids (research.md D16).

### `CoverageReport`

| Field | Type | Meaning |
|---|---|---|
| `audited` | `AuditedDeclarations` | FR-021 |
| `regimes` | `tuple[RegimeCoverage, ...]` | Sorted by regime id. Exactly one entry when implicit |
| `to_observe` | `tuple[Observation, ...]` | Cross-regime, per-regime counts, never summed |
| `enforcement` | `str` | The advisory statement, a module constant (FR-019, research.md D15) |

### `RegistryDimensionEmpty`

| Field | Type | Meaning |
|---|---|---|
| `dimensions` | `tuple[str, ...]` | Every empty dimension of `venues`, `streams`, `routes`, `spendable` — all of them, not the first |
| `reason` | `str` | Names each empty dimension and says why an empty report was not produced instead |

Returned *instead of* a report. `coverage(...) -> CoverageReport | RegistryDimensionEmpty`
is a tagged union, so a caller cannot read an empty report as full coverage (FR-020, B10).

An empty `regimes` mapping is **not** in this list: it is FR-015's implicit regime, which is
a report, not a refusal.

### `ReservedRegimeId`

| Field | Type | Meaning |
|---|---|---|
| `regime_id` | `str` | The reserved implicit id, declared by the owner |
| `reason` | `str` | Why the report refuses rather than shadowing it |

Also returned instead of a report (research.md D14). Rare, and cheaper as a typed outcome
than as an unwritten assumption.

## Relationships

```text
CoverageReport
├── audited: AuditedDeclarations
├── regimes: (RegimeCoverage, ...)
│   ├── verdicts: (Ready | NotReady, ...)
│   │   ├── Ready    -> inbound (RouteRelied,...) | SATISFIED_BY_ARRIVAL, exits (RouteRelied,...)
│   │   └── NotReady -> deficits (Deficit, ...) -> MissingDeclaration
│   ├── todo: (TodoEntry, ...) -> MissingDeclaration + (BlockedPair, ...)
│   ├── ties: ((index, ...), ...)
│   └── orphan_exits: (OrphanExit, ...)
├── to_observe: (Observation, ...) -> MissingDeclaration + ((regime_id, count), ...)
└── enforcement: str
```

## What is deliberately absent

- **No cost figure, no percentage, no amount** — FR-017. No field above can hold one.
- **No provenance or staleness mark** — FR-023. Those belong to the values they describe,
  and a summarized second copy here would drift from the authoritative one.
- **No composed path, no reversed route** — FR-006. There is no field for a chain, which is
  the cheapest way to keep feature 004's work out of this feature's records.
- **No "reachable by composition only" annotation** — FR-018's forward note. It arrives with
  004, as a distinct field beside the verdict, never as a change to what `Ready` means.
