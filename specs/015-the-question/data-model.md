# Data model: the question, the answer, and the four declarations behind them

Feature `015-the-question`. Every record is `@dataclass(frozen=True, slots=True, kw_only=True)`
unless it copies the shape of an existing record that is not. Unions are tagged and matched with
`match`; nothing here is a class with behaviour.

**No record in this feature carries a string this feature composed** (FR-020, D6). Strings are
ids, dates rendered by the file that declared them, or reasons another core record already
wrote, carried verbatim.

---

## The declarations

### `data/groups.toml` → `core.instruments.groups.InstrumentGroup`

| Field | Type | Requirement |
|---|---|---|
| `id` | `str` | FR-007a — a question's vocabulary is these ids |
| `name` | `str` | for a reader; nothing dispatches on it |

Root-level and curated, beside `venues.toml` (D1). No owner table: an instrument's label is
curated data and cannot depend on whose registry is being loaded.

### `[instrument] groups` → `InstrumentDeclaration.groups`, `FundDeclaration.groups`

`tuple[str, ...]`, **required**, possibly empty, each id declared in `data/groups.toml` (D2).
Refused at load: an undeclared id, a duplicate within one list. Nothing infers membership from
class, venue, tax class or id prefix (FR-007a, SC-032).

### `[access.resale_price]` → `InstrumentAccess.resale_price: VenueQuote | None`

The same `VenueQuote` an `[access.price]` builds — a `Money` per unit with its citation, and the
`ObservationKind` it ages under. `None` is the shipped state and is what FR-031 refuses by name.

### `data/scenarios/early_exit/<owner>.toml` → `core.scenarios.early_exit.SpreadHolds`

| Field | Type | Requirement |
|---|---|---|
| `id` | `str` | named in `rests_on`, so a reader can find the file |
| `is_assumption` | `Literal[True]` | FR-032 — it is a belief, not an observation |
| `rationale` | `str` | required and non-empty; the owner's own words |
| `provenance` | `Provenance \| None` | `None` for the owner's own belief; a published forecast fills it |

Exactly one file; an absent directory refuses at load naming it (FR-032, D9).

### `data/questions/<id>.toml` → `core.results.question.Question`

| Field | Type | Requirement |
|---|---|---|
| `id` | `str` | FR-002 |
| `asked_on` | `date` | FR-002. Not `as_of`, which is the verb's (FR-006) |
| `regime_id` | `str` | FR-002 — one regime per question |
| `continuation` | `ContinuationAssumption` | FR-002, 010's enum |
| `amounts` | `Mapping[str, Money]` | FR-002, FR-004 — per stream, in that stream's own currency |
| `subjects` | `tuple[NamedSubject, ...]` | FR-007, in declared order |
| `every_declared_instrument` | `bool` | FR-007's explicit token; `True` forbids `subjects` and vice versa |
| `horizons` | `tuple[DateRange, ...]` | FR-012, in declared order |
| `benchmark_instrument_id` | `str` | FR-026 |
| `plans` | `Mapping[str, tuple[InstrumentPlan, ...]]` | FR-002, keyed by **subject** id (D4) |
| `reserves` | `tuple[Reserve, ...]` | FR-016 |
| `owner_id` | `str` | Principle VII |

`NamedSubject` is `SubjectId | SubjectGroup`, both carrying one `id`. The distinction is what
the question *said*, before anything resolves it; an id naming no instrument and a group naming
no group are both FR-009's population, and the file cannot be refused for either (FR-009).

`Reserve`: `amount: Money`, `by: date`.

Refused at load (FR-001, FR-004, FR-026, SC-005, SC-029): an unknown field, a missing field, a
duplicated subject, two identical horizons, no horizon, no subject, an amount whose currency its
stream does not declare, an amount for an undeclared stream, a declared stream with no amount, a
benchmark outside the subjects, both `subjects` and the every-instrument token, neither.

---

## The answer

### `core.results.answer.Answer`

| Field | Type | Requirement |
|---|---|---|
| `question` | `Question` | FR-023 — the whole question, beside every count |
| `as_of` | `date` | FR-023 |
| `subjects` | `tuple[ResolvedSubject, ...]` | FR-008a, FR-009; declared order |
| `sections` | `tuple[HorizonSection, ...]` | FR-012; declared order |
| `excludes` | `tuple[StatedExclusion, ...]` | FR-023a |
| `provenance` | `Provenance` | FR-024 — never a `Mark` |
| `staleness` | `StalenessVerdict` | FR-024 |

`ResolvedSubject = DeclaredSubject | UndeclaredSubject`:

* `DeclaredSubject(named: str, is_group: bool, ids: tuple[str, ...])` — the resolution FR-008a
  requires; the count is `len(ids)` and is never stored beside it (D7).
* `UndeclaredSubject(named: str)` — FR-009's own population, by the word the owner wrote. No
  reason field: the sentence is the CLI's.

Derived, never stored: `considered_ids(answer)` (FR-007b's deduplicated union),
`undeclared(answer)`, `cross_horizon(answer)` (FR-015).

### `core.results.answer.HorizonSection`

| Field | Type | Requirement |
|---|---|---|
| `horizon` | `DateRange` | FR-012 |
| `outcome` | `CandidateSurvey \| SurveyRefused \| BenchmarkUnavailable` | FR-014 — 014's and 010's records, whole |
| `standings` | `tuple[SubjectStanding, ...]` | FR-010; one per named subject, declared order |
| `arrives_after_horizon` | `tuple[MoneyArrivesAfterHorizon, ...]` | FR-030 |
| `reserves` | `tuple[ReserveVerdict, ...]` | FR-016 — one per `(candidate × reserve)` |

`SubjectStanding = SubjectReached | SubjectUnreached | SubjectUndeclared`, each carrying the
named subject and, for the first two, the ids it resolved to and the ids that yielded a
candidate. Three records rather than one with a discriminator, because FR-010 requires the three
distinguishable without reading prose and their remedies differ.

`MoneyArrivesAfterHorizon(key: Tuple, arrives_on: date)` — FR-030's typed part-refusal, naming
the candidate and the date its money actually arrives.

`ReserveVerdict = CoveredByThePlan | PartialExitWouldBeNeeded`:

* `CoveredByThePlan(key, reserve, arrivals_read: tuple[Arrival, ...], covered_on: date)` —
  FR-017, FR-019. The arrivals are named so a verdict computed over arrivals falling past the
  horizon's end is visible as such.
* `PartialExitWouldBeNeeded(key, reserve, arrivals_read, short_by: Money)` — FR-017, FR-018.
  Never *the reserve cannot be met*, and never *no price is declared*.

`section_evaluated(section)` and `section_ranking(section)` are derived and exclude every key in
`arrives_after_horizon` (D8, FR-030).

### `core.results.answer.StatedExclusion`

| Field | Type | Requirement |
|---|---|---|
| `what` | `Exclusion` (enum) | FR-023a — a closed set |
| `applies_to` | `Tuple \| None` | FR-023a — the candidate, where it is specific to one |
| `supplied_by` | `str` | FR-023a — a feature id or a declaration path, never a search |
| `direction` | `Understated \| Overstated \| None` | FR-033 — `None` where the claim has no warranted sign |

`Exclusion` members: `NO_REAL_TERMS_FIGURE`, `NO_INCOME_TAX_ON_THE_STATED_AMOUNT`,
`EARLY_EXIT_CARRIES_NO_RATE_RISK`, `EARLY_EXIT_IS_A_POINT_NOT_A_DISTRIBUTION`,
`EARLY_EXIT_SPREAD_IS_A_SELLERS_QUOTE`. The last three are FR-033's split: the certainty claim
and the spread claim carry a direction, the rate-risk one carries `None`, and SC-026 asserts the
absence rather than tolerating it.

### `core.results.answer.Refused`

Returned **instead of** an `Answer` (FR-026). A tagged union over what is wrong with the
*question*: `NoHorizonDeclared`, `NoSubjectDeclared`, `AmountForAnUndeclaredStream(stream_id)`,
`StreamWithNoAmount(stream_id)`, `BenchmarkOutsideTheSubjects(instrument_id)`,
`BenchmarkYieldsSeveralCandidates(instrument_id, count)`, `TwoIdenticalHorizons(horizon)`.

Every member is reachable from a **file** as well as from a caller, which is why the first four
are also load-time refusals: in an artefact under review an omitted amount is a typo, and FR-004
requires the file to be refused naming the file and the field.

---

## The manifest

`RunManifest` gains `as_of: date` and `regime_id: str`, and the four single-projection fields
(`projected_instrument_id`, `holding`, `horizon`, `assumptions`) move behind
`projection: ProjectedRun | None` (D12, FR-023, FR-025).

`InputKind` widens from five to name every declaration family a run can read — the five it has,
plus `question`, `group`, `route`, `channel`, `venue`, `stream`, `spendable`, `access`,
`composition`, `candidate_ceiling`, `scenario`, `official_rate_series`, `tax_scheme`,
`tax_destination`, `observation_kind`, `early_exit_assumption`. SC-008 walks the loader's inputs
and asserts the manifest names every file the run read, which is what makes H3 claimable.
