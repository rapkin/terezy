# Data model — the candidate set and its three columns

**Feature**: `014-candidates` | **Date**: 2026-08-30

Frozen records, free functions, tagged unions matched with `match`. Nothing below holds a
figure this feature computed: every amount and every rate on a `TupleOutcome` came out of
010's `evaluate`, and every route term came out of 004's `compose`.

## `core/results/candidates.py`

### `CandidateCeiling`
| field | carries |
|---|---|
| `max_candidates: int` | FR-019. At least one; declared, no default. No `owner_id` — the owner is a property of the file, checked there (`SegmentBound`'s precedent). |

### `Question` — everything that determines a count (FR-012)
| field | carries |
|---|---|
| `amounts: Mapping[str, Money]` | FR-005. One amount **per stream id**, in that stream's own currency. Nothing converts. |
| `horizon: DateRange` | one horizon for the whole set, 010's FR-025. |
| `as_of: date` | when the question is asked; decides staleness and nothing else. |
| `continuation: ContinuationAssumption` | required, no default anywhere in the stack. |
| `plans: Mapping[str, tuple[InstrumentPlan, ...]]` | FR-003, keyed by instrument id, in the caller's order. **This is also FR-025**: how many plans were supplied per instrument is `len(plans[id])`, read off the question rather than stored a second time. |
| `bound: SegmentBound` | 004 FR-007's bound, travelling with the answer it shaped. |
| `regime_id: str` | FR-023. Which world was searched. |

### `EnumeratedCandidate`
| field | carries |
|---|---|
| `key: Tuple` | 010's record, unchanged. The five declared terms and nothing else, so two sets under two regimes compare by key equality (FR-023). |
| `plan_position: int` | FR-017, D1. The plan's index in the caller's sequence for this instrument — the last term of FR-016's order, and not derivable from the plan record. |

### The no-candidate column (FR-008, FR-013, FR-014)
`NoCandidateReason = NothingConnects | NothingNeedsToConnect` — a union, so the two are
distinguishable without reading prose (FR-014, D3).

| record | fields |
|---|---|
| `NothingConnects` | `side: Literal["route_in", "route_out"]`, `reason: str`. An `Enumeration` came back with no candidates. The remedy is a declaration. |
| `NothingNeedsToConnect` | `refusal: CompositionRefused`. `compose` refused because the stream already arrives where the purchase happens. Its words reach the report verbatim because the whole record is carried (SC-008). |
| `PairYieldedNoCandidate` | `instrument_id`, `stream_id`, `why: NoCandidateReason`. |

### `CandidateSet`
| field | carries |
|---|---|
| `question: Question` | FR-012, SC-017. Every count on this record is read beside it. |
| `candidates: tuple[EnumeratedCandidate, ...]` | FR-016's total order. Empty is a legitimate answer: *the declarations connect nothing*. |
| `no_candidate: tuple[PairYieldedNoCandidate, ...]` | FR-008's third population, ordered by `(instrument_id, stream_id)`. |
| `pairs_considered: int` | the left side of FR-009's first identity, counted from the registry (instruments with an access entry × declared streams) rather than from the loop — which is what makes the identity a check rather than a tautology. |
| `provenance: Provenance` | FR-024, D8: the legs of every route in a produced candidate, and the venue quote of every access entry considered. |
| `staleness: StalenessVerdict` | the same sources aged at `question.as_of` under each source's own declared kind. |

### `CandidateSurvey`
| field | carries |
|---|---|
| `enumerated: CandidateSet` | the set that was compared. |
| `comparison: Comparison \| BenchmarkUnavailable` | 010's result, whole. FR-001a: `compare`'s own loop is the only evaluation, so the evaluated and dropped columns are read out of this rather than computed beside it. |

### Whole-enumeration refusals
`EnumerationRefused = NoPlanSupplied | DuplicateRunPlan | CeilingExceeded | QuestionDoesNotStandUp | UndeclaredRouteSupplied`

| record | fields | why the whole thing refuses |
|---|---|---|
| `NoPlanSupplied` | `instrument_id`, `reason` | FR-018, FR-003. A reachable instrument with no plan; defaulting one would silently pick a way out. |
| `DuplicateRunPlan` | `instrument_id`, `positions: tuple[int, int]`, `reason` | D6. Two equal plans make one key twice, and a set with a repeated member has no defined count. |
| `CeilingExceeded` | `ceiling`, `reached`, `reason` | FR-019. Names both numbers; carries no candidates. |
| `QuestionDoesNotStandUp` | `refusal: CompositionRefused`, `reason` | FR-018, FR-014a. Fires only for `BOUND_ADMITS_NOTHING` and `NO_SPENDABLE_ENDPOINT`, read off `CompositionRefused.case` and never off its text. |
| `UndeclaredRouteSupplied` | `part: Literal["route_in", "route_out"]`, `route_ids: tuple[str, ...]`, `reason` | FR-018's third clause, D4. A way in or way out names a route `registries.routes` does not declare — reachable because the narrowed `routes` and the `Registries` arrive independently. `survey` applies the same record to the **benchmark's** supplied chain, which is the other supplied way in this feature has. |

`SurveyRefused = EnumerationRefused | BenchmarkNotACandidate | MoreThanOneStreamInTheSet`

| record | fields | why |
|---|---|---|
| `BenchmarkNotACandidate` | `benchmark: Tuple`, `occurrences: int`, `reason` | FR-022. The benchmark must be a member exactly once; `compare` would otherwise prepend it, which is the privileged side channel 010 FR-012 forbids, reintroduced one layer up. |
| `MoreThanOneStreamInTheSet` | `stream_ids: tuple[str, ...]`, `reason` | FR-001a's recorded gap. `compare` takes one amount for the whole set while FR-005 takes one per stream; a two-stream set cannot be handed to it, and looping per stream would produce one ranking per stream and none of the set. `[[future]] one-amount-per-stream-in-compare`. |

### `DropGroup` — one row of the tally (FR-011)
| field | carries |
|---|---|
| `refusal: str` | the refusal record's type name (D7). |
| `count: int` | how many candidates that reason dropped. |
| `instruments`, `streams`, `routes`, `missing` | the distinct declarations the group's members implicate, sorted — so the remedy is readable from the tally without reading the records. `missing` is populated from `DeclarationMissing.what` and empty otherwise. |

## `core/decision/candidates.py` — the functions

| function | returns |
|---|---|
| `enumerate_candidates(*, registries, routes, question, ceiling)` | `CandidateSet \| EnumerationRefused` |
| `survey(*, registries, routes, question, ceiling, benchmark)` | `CandidateSurvey \| SurveyRefused` |
| `evaluated(comparison)` | `tuple[TupleOutcome, ...]` — ranked plus not-comparable, or scored plus not-comparable. |
| `dropped(comparison)` | `tuple[RefusedTuple, ...]` |
| `drop_tally(dropped)` | `tuple[DropGroup, ...]`, sorted by refusal name. Derived on demand, **never** a stored field beside the records (FR-011). |

`routes` arrives beside `registries` rather than being narrowed here, because 004 FR-017 makes
the narrowing the caller's (research D4) — and because that seam is what makes
`UndeclaredRouteSupplied` reachable rather than a guard that reads as protection.

## `core/results/composed.py` — widened by this feature (FR-014a)

```python
class Unaskable(Enum):
    BOUND_ADMITS_NOTHING = "bound_admits_nothing"
    NO_SPENDABLE_ENDPOINT = "no_spendable_endpoint"
    ALREADY_ARRIVED = "already_arrived"
```
`CompositionRefused` gains `case: Unaskable`. The first two are about the **question**; the
third is about one pair and is the opposite of a gap.

## `data/candidates/owner-001.toml`

```toml
[owner]
id = "owner-001"

[candidates]
max_candidates = 1000
```
Loader refuses `< 1`, refuses a missing directory, refuses a second file, and checks the
`[owner]` id against the streams the ceiling is resolved with — `data/composition/`'s
precedent at every step.
