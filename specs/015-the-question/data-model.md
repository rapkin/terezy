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

The same `VenueQuote` an `[access.price]` builds — a `Money` per unit with its citation, the
`ObservationKind` it ages under, and (added 2026-09-03) `observed_on`, the declaration's own
`retrieved_on`: the day the quotation described the market, which is what a sale carried to a
later date subtracts detached coupons from. `None` is what FR-031 refuses by name; the fixture
instruments still make that statement and every real issue declares a quote.

### `data/scenarios/early_exit/<owner>.toml` → `core.scenarios.early_exit.QuotationHolds`

| Field | Type | Requirement |
|---|---|---|
| `id` | `str` | named in `rests_on`, so a reader can find the file |
| `is_assumption` | `Literal[True]` | FR-032 — it is a belief, not an observation |
| `rationale` | `str` | required and non-empty; the owner's own words |

No citation keys, and their absence is the design: a platform that committed to its quoted
buyback price would have declared a **term**, so a source here would replace the belief rather
than vouch for it.


Exactly one file; an absent directory refuses at load naming it (FR-032, D9).

### `data/questions/<id>.toml` → `core.results.question.Question`

| Field | Type | Requirement |
|---|---|---|
| `id` | `str` | FR-002 |
| `asked_on` | `date` | FR-002. Not `as_of`, which is the verb's (FR-006) |
| `regime_id` | `str` | FR-002 — one regime per question |
| `continuation` | `ContinuationAssumption` | FR-002, 010's enum |
| `amounts` | `Mapping[str, Money]` | FR-002, FR-004 — per stream, in that stream's own currency |
| `subjects` | `tuple[str, ...]` | FR-007, the words the owner wrote, in declared order |
| `every_declared_instrument` | `bool` | FR-007's explicit token; `True` forbids `subjects` and vice versa |
| `horizons` | `tuple[DateRange, ...]` | FR-012, in declared order |
| `benchmark_instrument_id` | `str` | FR-026 |
| `plans` | `Mapping[str, tuple[InstrumentPlan, ...]]` | FR-002, keyed by a **subject** word or by an instrument id the subjects reach; the per-instrument one wins (D4) |
| `reserves` | `tuple[Reserve, ...]` | FR-016 |
| `owner_id` | `str` | Principle VII |

**The subjects are untagged**, and that is forced by FR-009: whether a word is an instrument id,
a group id or neither is a fact about the *registry*, and a word that is neither must reach the
answer as its own population rather than refuse the file. Tagging them at load would need the
registry there and would turn the owner's vocabulary into curated data. The tagging happens in
the answer, as `DeclaredSubject.is_group`.

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
| `outcome` | `CandidateSurvey \| SurveyRefused \| BenchmarkYieldsNoCandidate` | FR-014 — 014's records, whole, widened by one |
| `standings` | `tuple[SubjectStanding, ...]` | FR-010; one per named subject, declared order |
| `arrives_after_horizon` | `tuple[MoneyArrivesAfterHorizon, ...]` | FR-030 |
| `reserves` | `tuple[ReserveVerdict, ...]` | FR-016 — one per `(candidate × reserve)` |

`SubjectStanding = SubjectReached | SubjectUnreached | SubjectUndeclared`, each carrying the
named subject and, for the first two, the ids it resolved to and the ids that yielded a
candidate. Three records rather than one with a discriminator, because FR-010 requires the three
distinguishable without reading prose and their remedies differ.

`MoneyArrivesAfterHorizon(key: Tuple, arrives_on: date)` — FR-030's typed part-refusal, naming
the candidate and the date its money actually reaches a spendable endpoint.

`ReserveVerdict = CoveredByThePlan | PartialExitWouldBeNeeded`:

* `CoveredByThePlan(key, reserve, arrivals_read: tuple[Arrival, ...], covered_on: date)` —
  FR-017, FR-019. The arrivals are named so a verdict computed over arrivals falling past the
  horizon's end is visible as such.
* `PartialExitWouldBeNeeded(key, reserve, arrivals_read, short_by: Money)` — FR-017, FR-018.
  Never *the reserve cannot be met*, and never *no price is declared*.

`section_evaluated(section)` and `section_ranking(section)` are derived and exclude every key in
`arrives_after_horizon` (D8, FR-030). **The withholding tests the date the holding released the
money**, not the date it arrived: a sale at `horizon.end` settles a few days later on every
declared corridor, and 010's `accounts_for` already says settlement latency sits inside the span
because waiting is a cost. Testing the arrival would withhold every early exit there is.

### `core.results.answer.StatedExclusion`

| Field | Type | Requirement |
|---|---|---|
| `what` | `Exclusion` (enum) | FR-023a — a closed set |
| `applies_to` | `Tuple \| None` | FR-023a — the candidate, where it is specific to one |
| `supplied_by` | `str` | FR-023a — a feature id or a declaration path, never a search |
| `direction` | `Direction \| None` | FR-033 — `None` where the claim has no warranted sign |

`Exclusion` members: `NO_REAL_TERMS_FIGURE`, `NO_INCOME_TAX_ON_THE_STATED_AMOUNT`,
`EARLY_EXIT_CARRIES_NO_RATE_RISK`, `EARLY_EXIT_IS_A_POINT_NOT_A_DISTRIBUTION`,
`EARLY_EXIT_SPREAD_IS_A_SELLERS_QUOTE`, and (added 2026-09-03)
`EARLY_EXIT_IGNORES_ACCRUED_INTEREST`. The first three early-exit members are FR-033's split:
the certainty claim and the spread claim carry a direction, the rate-risk one carries `None`,
and SC-026 asserts the absence rather than tolerating it. The fourth is what carrying a dirty
quotation to a later date leaves behind; it carries a direction only where the quotation
predates the sale **and** no coupon detached before the purchase, which is the case its warrant
covers.

### `core.results.answer.Refused`

Returned **instead of** an `Answer` (FR-026). A tagged union over what is wrong with the
*question*: `NoHorizonDeclared`, `NoSubjectDeclared`, `AmountForAnUndeclaredStream(stream_id)`,
`StreamWithNoAmount(stream_id)`, `BenchmarkOutsideTheSubjects(instrument_id)`,
`BenchmarkYieldsSeveralCandidates(instrument_id, occurrences)`, `TwoIdenticalHorizons(horizon)`,
`PlanForNothing(named)`.

`BenchmarkOutsideTheSubjects` is a benchmark the question does not **name**; a benchmark that is
a named subject and reaches nothing is that section's `BenchmarkYieldsNoCandidate` instead. The
split is what lets SC-020's question — four words the registry declares none of — be answered at
all. `PlanForNothing` is a plan keyed by a word no subject reaches, refused for the reason every
declaration here refuses an ignored field: a setting silently dropped is a stated choice that
does nothing.

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
