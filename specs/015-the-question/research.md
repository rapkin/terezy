# Research: the decisions this feature takes, and what each was taken against

Feature `015-the-question`. Each entry is a decision the specification leaves to the plan, the
alternative that was live, and the reason the alternative was refused. Decisions the owner
already took — a question is a declaration, the API is one verb, a subject is an id or a group —
are in [spec.md](./spec.md) and are not re-argued here.

## D1 — Group ids are a root-level curated vocabulary, `data/groups.toml`

**Taken against** a per-owner directory `data/groups/`.

The label lives on the **instrument** declaration (FR-007a), and `data/instruments/` is curated
data shared across owners. A curated file referencing a per-owner file inverts Principle VII's
boundary: an instrument would fail to load because *somebody else's* vocabulary file was absent.
So the vocabulary is curated too, and it goes where the project already puts a curated
vocabulary — a root-level file beside `venues.toml` and `observation_kinds.toml`.

It also settles the provenance gate cleanly. That gate walks *directories* under `data/`; a
root-level file is outside it by the same construction that already leaves `venues.toml`
outside, so no exemption widens and no reason has to be written for one. A group id and a human
name are references, not observations, exactly as a venue id is.

## D2 — `groups` is a **required** key on every instrument declaration

**Taken against** an optional key defaulting to *in no group*.

FR-008a names the regression this feature cannot test for: an issue declared in 016 **without**
its label leaves the count lower than the owner expects, and no test can know he expected 24. An
optional key makes that regression a forgotten line; a required one makes it a load failure that
names the file and the field. The cost is `groups = []` on the two shipped fixtures that are in
no group — which is the point, because those two are in no group *deliberately* and the file now
says so.

This is 002 FR-028's rule applied to a list rather than to a number: a forgotten line must never
read as a chosen policy.

## D3 — The subject set travels on 014's `Question`, as **resolved ids**

**Taken against** passing the question's subject *words* into 014 and resolving there.

014's `Question` is the record every count is read beside. Resolution is vocabulary — a fact
about `data/groups.toml` and the instruments' labels — and 014 has no business knowing what a
group is. So `Question.subjects: frozenset[str]` is a set of **instrument ids**, `_considered`
narrows to it, and everything about groups stays in 015.

`frozenset` rather than a tuple because the field is a membership test and an order here would be
a second, silent ordering beside `_ordered`'s.

## D4 — Run plans are declared **per subject** and expanded per instrument

**Taken against** plans keyed by instrument id in the question file.

FR-007's whole argument is that a question file must not grow an entry per issue when 016 lands.
A plan keyed by instrument id would reintroduce exactly that: 24 identical hold-to-maturity
plans, hand-edited per issue. So the file states a sequence of plans per **subject**, and the
verb expands them to 014's `plans` mapping.

**Expansion deduplicates equal plans, in order.** FR-007b requires an id named twice — by a group
and by itself, or by two overlapping groups — to yield **one** candidate and be counted once.
Two subjects reaching one id with the *same* plan is that case; with *different* plans it is two
honest ways of running the instrument and both survive. The dedupe is by plan value, and it is
what makes 014's `DuplicateRunPlan` unreachable from a question rather than a trap in it.

## D5 — The `Answer` carries no manifest; the api layer's record does

**Taken against** a `manifest` field on the core `Answer`.

A manifest holds SHA-256 digests, and `hashlib` sits in the core's forbidden imports beside
`json` and `tomllib` — the constitution's Architecture Constraints, mechanically enforced. So
the core verb returns an `Answer` with no manifest, and `api.answer` returns an
`AnsweredQuestion` holding the answer and its `RunManifest` beside it. That is the shape the
spec already describes for the verb: *"the orchestration entry point in `api/` that loads the
declarations, calls it once, and attaches the run manifest."*

FR-025 is satisfied at the layer that can satisfy it, and no answer a caller can obtain from
`api/` lacks one.

## D6 — This feature's own records carry **no string it composed**

**Taken against** a `reason` field on each new refusal record, on 010's and 014's precedent.

FR-020 forbids a headline, a verdict sentence and any prose composed by this feature, and SC-003
scans for it. 010 and 014 write reasons because their records are the *last* word on a fact; an
`Answer` is a contract with an interface nobody has chosen, and a sentence in it is a rendering
decision taken on that interface's behalf.

So every record this feature adds carries ids, dates, amounts, enum members and other core
records — and the strings that reach a reader are either ids, or strings 010 and 014 already
wrote, carried verbatim. The CLI composes the sentences.

The one exception is deliberate and is not a composed sentence: `TupleOutcome.rests_on` is a
tuple of stated assumptions **in words**, which is what that field is for, and D9's early-exit
assumption joins it there.

## D7 — Counts are derived, never stored

**Taken against** `reached`, `unreached` and `undeclared` integers on each section.

FR-010 requires a section to state each named subject's state and to count them. 014 FR-011's
rule settles the shape: a tally is derived by one named function from the retained records and
never stored beside them. So a section holds one tagged `SubjectStanding` per named subject and
`subject_counts(section)` derives the three numbers. Two fields holding one truth is where the
drift happens, and here the drift would be a count disagreeing with the list it counts.

The same rule gives FR-015 its cross-horizon reading and FR-007b its deduplicated id count.

## D8 — FR-030's withheld candidates are a section field, and the evaluated population is derived

**Taken against** rebuilding 014's `CandidateSurvey` with the late candidate removed.

FR-014 requires a section's outcome to be 014's record **whole**. So the survey is untouched, the
section carries `arrives_after_horizon: tuple[MoneyArrivesAfterHorizon, ...]`, and this feature
provides `section_evaluated(section)` and `section_ranking(section)` — the populations FR-030
speaks about, derived by excluding the withheld keys.

The alternative would have had this feature construct a `Comparison` it did not compute, which is
the privileged side channel 010 FR-012 forbids one layer up.

## D9 — The spread-holds belief is a declaration under `data/scenarios/early_exit/`

**Taken against** a constant in the engine and a field on the question.

FR-032 requires it declared, with no default, marked, and not inventable per run. `data/scenarios/`
is where a belief about the future lives and is already exempt from the citation requirement for
exactly that reason. A **subdirectory**, on `data/scenarios/inflation/`'s precedent: `scenarios/*.toml`
is globbed and validated as scenario documents and `glob` does not recurse, so a sibling file
would be read as a broken scenario.

Not a field on the question, because it is not a property of one question: it is what the owner
believes about how a platform's quoted spread behaves, and two questions asked on one day must
not be able to disagree about it.

**The mark it carries is `rests_on`.** The record carries `is_assumption: Literal[True]` and a
required `rationale`, on `ChosenPoint`'s and `ExchangeRateAssumption`'s shape; every outcome
computed through it names it in `TupleOutcome.rests_on`, which is the field whose stated purpose
is the assumptions an outcome depends on. SC-025's walk over the whole result reads that field.

## D10 — FR-031's refusal uses `DeclarationMissing(part="access")` and widens no union

The specification is explicit that a planner must not settle this early. It does not have to be
settled: `DeclarationMissing.part` already admits `"access"`, `what` already names the missing
term, and 016 declaring the resale price beside `price.per_unit` is the case in which nothing
moves at all. So the resale price is declared on the access record, its absence refuses through
the existing member, and `TupleRefused` stays at seventeen — which
`tests/unit/test_tuple_refusals.py` already pins.

## D11 — The CLI uses `argparse`, and declares no question field the file cannot state

**Taken against** `typer`, which is already a declared optional dependency.

`cli/` renders one record and builds one record from flags. A dependency for one subcommand is
one more thing that has to be installed before an answer can be read, and `argparse` is in the
standard library and forbidden only in `core`.

SC-019's scan is scoped: `--as-of` is exempt because FR-006 puts it on the verb, and the segment
bound and candidate ceiling are exempt because they are declared in `data/composition/` and
`data/candidates/` and reach the verb through its second parameter. An unscoped scan fails on all
three and would push them into the question file, which is the opposite of what FR-006 decided.

## D12 — The manifest stops being single-projection shaped

`RunManifest` today carries `projected_instrument_id`, one `Holding`, one `Assumptions` and one
`horizon`, and has no `as_of` and no `regime`. An answer has many instruments, many horizons and
no single holding, and FR-023 and FR-025 require both of the missing fields.

**Taken against** a second manifest record beside it. Two records would be two places the
answer to *what did this run rest on?* is decided, and the digest scheme, the file-version rule
and the unverified-source roll-up are identical in both. So the fields that are true of one
projection move behind an optional `projection: ProjectedRun | None`, and `as_of` and `regime_id`
join the record proper. `InputKind` widens to name every declaration family a run can read,
because SC-008 requires the manifest to name **every** file the run read and today it names
three.
