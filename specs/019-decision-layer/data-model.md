# Data model: the objectives, the verdicts, and the three populations

Feature `019-decision-layer`. Every record is `@dataclass(frozen=True, slots=True, kw_only=True)`;
unions are tagged and matched with `match`; nothing here is a class with behaviour.

**No record in this feature carries a string this feature composed** (FR-028). Strings are ids,
criterion names, or reasons another core record already wrote, carried verbatim (SC-016a).

---

## The declaration

### `data/objectives/<owner>.toml` → `core.results.objectives.ObjectiveSet`

One file per set, one set per file. An **empty directory refuses at load** (FR-001, research D8);
two files declaring one id refuse through `resolver._refuse_duplicate`.

| Field | Type | Requirement |
|---|---|---|
| `id` | `str` | what a question names (FR-001a) |
| `owner_id` | `str` | Principle VII; checked against the streams it resolves with |
| `objectives` | `tuple[Objective, ...]` | non-empty; the pass's *p* |

No citation keys, and their absence is the design (FR-004): a stated preference is not an
observation. `data/objectives/` is already in `check_provenance.py`'s `EXEMPT_DIRS` with that
reason.

### `Objective`

| Field | Type | Requirement |
|---|---|---|
| `criterion` | `Criterion` | FR-002 — a member of the closed set below |
| `direction` | `ObjectiveDirection` | FR-002 — `MORE_IS_BETTER` or `LESS_IS_BETTER` |
| `band` | `Band` | FR-011 — no default; the shape must fit the criterion (FR-011d) |

`ObjectiveDirection` has exactly **two** members and no per-criterion synonym. *Sooner is better*
on a date is `LESS_IS_BETTER`; a third token meaning the same thing is a synonym inside a closed
set, which is how two spellings of one rule come to be handled differently. The name is
`ObjectiveDirection` rather than `Direction` because `core/results/answer.py` already declares a
`Direction` over an unrelated closed set (research D10).

**No weight, no score, no coefficient, no priority, and no order that means anything** (FR-005,
scanned by SC-005). The sequence is the declared order and nothing reads it as a ranking.

### `Criterion` — the closed set (FR-002, FR-003)

| Member | Reads | Figure |
|---|---|---|
| `MONEY_AT_THE_ENDPOINT` | `TupleOutcome.reaches` | `Money` |
| `ALL_MONEY_BACK_ON` | `TupleOutcome.arrivals[-1].arrived_on` | `date` |

Closed in **source**. FR-003 states plainly that this is the one place the feature is not
data-only: a criterion is a reader over a computed figure, so a new criterion is a new figure or a
new way of reading one, and both are code. What is data is which criteria the owner compares on and
in which direction.

A criterion naming a figure the outcome record does not carry fails at load naming the criterion
and the figure (FR-002) — which, the set being closed, is a load failure the schema cannot express
and the loader's `_literal` produces.

### `Band` — a tagged union (FR-011d)

| Member | Fields | Legal on |
|---|---|---|
| `AbsoluteBand` | `amount: Money` | a money criterion |
| `FractionOfTheQuestionAmount` | `fraction: float` | a money criterion |
| `DaysBand` | `days: int` | a date criterion |

Refused at load (FR-011b, FR-011d, SC-003): negative, zero, non-finite; a fraction on a date
criterion; a day count that is not a whole number; a money band that is neither shape.

Both money shapes, because CL-2 asked for hryvnia and was answered in percent; permitting only the
shape used would refuse the one asked for.

### `Question.objective_set_id: str` (FR-001a)

Required, no default, on 015's record and its TOML. A question naming a set the registry does not
declare refuses in `resolver.check_question` (research D8), never as a runtime verdict — FR-026
says a runtime refusal for it would be a second answer to a question the loader already refused.

---

## What the pass produces

### `DominanceResult`

Carried on `HorizonSection.dominance`, **beside** the survey and replacing nothing in it (FR-027,
SC-016a).

| Field | Type | Requirement |
|---|---|---|
| `objectives` | `ObjectiveSet` | FR-023 — the whole set, every band in its declared form |
| `resolved_bands` | `tuple[ResolvedBand, ...]` | FR-023 — one per fraction actually resolved (research D6) |
| `non_dominated` | `tuple[Tuple, ...]` | FR-006, FR-025 |
| `dominated` | `tuple[Dominated, ...]` | FR-008 |
| `not_placed` | `tuple[NotPlaced, ...]` | FR-008 |
| `incomparable` | `tuple[IncomparablePair, ...]` | FR-008a |
| `indistinguishable` | `tuple[Indistinguishable, ...]` | FR-011 |
| `benchmark_standing` | `BenchmarkStanding` | FR-017 |
| `separating` | `SeparatingAssumptions \| NoStatedAssumptionSeparatesThem` | FR-019, FR-020 |

Every sequence is in 014 FR-016's candidate order and in **no** objective's order (FR-025). The
three population counts are `len` of three disjoint fields, and `evaluated = non_dominated +
dominated + not_placed` is an asserted check rather than a claim in prose (FR-008, 014 FR-009's
rule).

### `ResolvedBand` (FR-023, research D6)

| Field | Type |
|---|---|
| `criterion` | `Criterion` |
| `currency` | `Currency` |
| `from_amount` | `Money` — the question's stated amount in that currency |
| `width` | `Money` |

One per `(criterion, currency)` actually compared in, ordered by that pair. Absent for an
absolute or a day band, which are reported in their declared form on `objectives`.

### `Dominated` — one dominated candidate

| Field | Type | Requirement |
|---|---|---|
| `key` | `Tuple` | |
| `dominated_by` | `tuple[DominanceVerdict, ...]` | FR-008 — at least one; a candidate may be dominated by several |

### `DominanceVerdict` — one ordered pair (FR-007, FR-022)

| Field | Type | Requirement |
|---|---|---|
| `dominates` | `Tuple` | |
| `over` | `Tuple` | |
| `at_least_as_good_on` | `tuple[Criterion, ...]` | FR-007's weak half |
| `strictly_better_on` | `tuple[Criterion, ...]` | FR-007's strict half; non-empty |
| `provenance` | `Provenance` | FR-022 — the union of **both** candidates' |
| `staleness` | `StalenessVerdict` | FR-022 — the merged verdict of both |

`prov.merge` and `staleness.merge` over the two outcomes. A verdict computed from two unverified
figures is an unverified claim (Principle I), and SC-012 walks the whole result to check it.

### `Figure` and `Width` — what the relation compares (research D7a)

| Union | Members |
|---|---|
| `Figure` | `MoneyFigure(amount: Money)`, `DateFigure(on: date)`, `FigureUnavailable(what: str)` |
| `Width` | `MoneyWidth(amount: Money)`, `DayWidth(days: int)` |
| `PairVerdict` | `LeftDominates`, `RightDominates`, `TooCloseToCall`, `Neither`, `Incomparable(position, why)` |

A figure carries its own kind so the closeness rule can follow it rather than a parallel flag: two
`MoneyFigure`s go through `is_close` and a currency check, two `DateFigure`s compare exactly,
because FR-011d fixes a date's slack at **zero** and a bare float vector would apply the float
comparison to an ordinal. Two kinds at one position is a programmer error and raises.

`Width` is a `Band` made comparable to a figure: a fraction met by the question's amount, or an
already-absolute band unchanged. `ResolvedBand` reports only the first, so its `width` is a `Money`
rather than a `Width` — a day band has nothing to resolve and appears there not at all.

### `IncomparablePair` (FR-008a)

| Field | Type |
|---|---|
| `left` / `right` | `Tuple` |
| `criterion` | `Criterion` |
| `why` | `FigureMissing \| DeliveredInTwoCurrencies` |

`FigureMissing(what: str)` — on the declared objectives this is an outcome with **no arrivals**
(research D5). `DeliveredInTwoCurrencies(left_currency, right_currency)` — and **no exchange rate is
consulted anywhere** (SC-014).

Neither carries a criterion: `relates` is addressed by position and has none to give, and the pair
already carries it. One truth, one field.

A property of the **pair**. It refuses no section and removes neither candidate from any other
pair's verdict.

### `NotPlaced` (FR-008a)

| Field | Type |
|---|---|
| `key` | `Tuple` |
| `every_pair` | `tuple[IncomparablePair, ...]` |

An evaluated candidate with **at least one** pair, every one of which is incomparable. Neither
dominated nor non-dominated, and never dropped (FR-009). A candidate with one incomparable pair and
one decided pair is not here — the case SC-014 exists to exercise.

**The *at least one* is load-bearing, not pedantry.** *Every pair is incomparable* is vacuously
true of a section's **only** evaluated candidate, which would put it in `not_placed`, leave
`non_dominated` empty, and make the specification's own edge case — *one evaluated candidate is a
non-dominated set of one* — unreachable. It would also pass SC-004's emptiness property vacuously,
the placed population being empty too, and leave `why_one_member`'s `OnlyOneEvaluated` branch dead.
A lone evaluated candidate is **non-dominated**.

### `Indistinguishable` (FR-011, FR-011a)

| Field | Type |
|---|---|
| `key` | `Tuple` |
| `neighbours` | `tuple[Tuple, ...]` |

A **symmetric relation over pairs**, reported per candidate. Symmetry is a property of the record:
`b in neighbours(a)` iff `a in neighbours(b)`, which the fraction resolving against the question's
amount rather than a candidate's own is what makes true (FR-011d, SC-006's fourth case).

**No partition, ever** (FR-011a). Closeness within a band is not transitive, so no partition
exists, and any procedure producing one depends on an anchor the objectives do not fix.

### `BenchmarkStanding` — a tagged union (FR-017)

| Member | Fields |
|---|---|
| `NothingDominatesTheHurdle` | `key: Tuple` |
| `HurdleIsDominated` | `key: Tuple`, `by: tuple[DominanceVerdict, ...]` |

Worded as *nothing dominates the hurdle* and never as *the hurdle is best*: other members may sit
beside it in the set, and a hurdle that dominates everything is a different and stronger fact.
Distinct from 010's `beats_benchmark`, which is strict, one-dimensional, on the **rate**, at the
**project tolerance** — the two are separate fields and neither is derived from the other (FR-013).

### `SeparatingAssumptions` (FR-019) / `NoStatedAssumptionSeparatesThem` (FR-020)

| Field | Type |
|---|---|
| `per_member` | `tuple[MemberRestsOn, ...]` |

`MemberRestsOn(key, rests_on: tuple[str, ...], excludes: tuple[Exclusion, ...])` — the words at
least one **other** member does not carry, verbatim from `TupleOutcome.rests_on` and from the
**section's** `excludes` records filtered to that key. The section's, not `TupleOutcome.excludes`,
because measured the latter is identical across all 24 while the section's differ per candidate
(FR-015).

`NoStatedAssumptionSeparatesThem` is a typed statement rather than an empty list, which a reader
takes as *nothing separates them* when the truth is *the same beliefs are behind all of them*.

**Nothing here claims which assumption decides** (FR-021, scanned by SC-011): no field names one,
and no string asserts one.

---

## The refusals — `DominanceRefused` (FR-026)

A different type, returned instead of a set. No empty set standing for a failure, no partial set,
no `None`. The survey stays beside it, whole (FR-027).

| Member | Fields | Requirement |
|---|---|---|
| `NoBenchmarkToStandAgainst` | `reason: str` (010's own, verbatim) | FR-018 |
| `BenchmarkWasWithheld` | `key: Tuple`, `arrives_on: date` | FR-018a |
| `BandBelowTheAcyclicityFloor` | `criterion`, `declared: Band`, `resolved: Money \| None`, `slack: float`, `floor: float`, `objective_count: int` | FR-011c |
| `NoQuestionAmountInTheCurrencyCompared` | `criterion`, `currency` | FR-011d, research D6 |
| `SeveralQuestionAmountsInTheCurrencyCompared` | `criterion`, `currency`, `stream_ids`, `amounts` | FR-011d, research D6 |
| `NoSurveyToRunOver` | `refusal: SurveyRefused \| BenchmarkYieldsNoCandidate` | research D6a |

`NoSurveyToRunOver` is the sixth, and it is the one FR-026's list could not name before the records
were in hand: `SectionOutcome` is a union, a section that never surveyed has no population at all,
and `HorizonSection.dominance` is not optional. It carries the record that replaced the survey
verbatim. The alternative — an empty `DominanceResult` — is the empty set standing for a failure
FR-026 forbids, and would be indistinguishable from the legitimate empty set of a section that
evaluated nothing.

Three of the six are refusals rather than load failures for one reason: they need figures a
declaration file does not have — the magnitudes the slack depends on, and the currency a candidate
delivers in, which is the spendable endpoint's and a property of the route.

`NoBenchmarkToStandAgainst` carries `BenchmarkUnavailable.reason` **verbatim**, asserted by string
comparison so the reason cannot be rewritten (SC-009). `BenchmarkWasWithheld`'s reason differs from
it, asserted by comparing the two records (SC-009a).

**Two things a reader expects here and does not find**: a missing or undeclared objective set,
which is a load failure (FR-001, FR-001a); and a figure that cannot be compared, which is a
property of a pair (FR-008a).

---

## Derived readings, stored nowhere

Named functions over the records, on `subject_counts`'s precedent (014 FR-011, research D11). A
count stored beside the list it counts is where the two come to disagree.

| Function | Returns | Requirement |
|---|---|---|
| `why_one_member(result)` | `OnlyOneEvaluated \| EveryOtherIsDominated \| EveryOtherIsNotPlaced \| Mixed` | FR-014 |
| `section_ties(section)` | `tuple[tuple[Tuple, ...], ...]` | FR-029a — 010's tie groups, resolved to keys, narrowed to the reported population |
| `section_beats_benchmark(section)` | `tuple[Tuple, ...]` | FR-029a — the same, for `beats_benchmark` |

These read a **finished** section. The pass itself takes the section's parts rather than the
section, because `HorizonSection` is frozen and carries the pass's own result (research D9a).

`section_ties` and `section_beats_benchmark` sit beside `section_ranking` in
`core/decision/answer.py`, so the CLI renders and computes nothing. Both resolve an **index into
`Comparison.ranked`** to a key and then drop what 015 FR-030 withheld — measured, `inzhur_miltech`
is inside `beats_benchmark` at all three of the owner's horizons.

---

## The one function outside this feature's records

`core.primitives.tolerance.slack(left, right, *, tolerance=TOLERANCE) -> float` — the width the
project comparison allows for those two figures, as a value rather than a verdict. FR-011c has to
name it in a refusal and FR-007's floor has to be measured against it, and the module exports
nothing today that says *how wide*.

It lives there rather than in `core/decision/` because computing it beside the pass would be the
second copy of the closeness rule FR-012 forbids. It does **not** redefine `is_close`; the two
stand side by side and their agreement over finite pairs is asserted (research D3).
