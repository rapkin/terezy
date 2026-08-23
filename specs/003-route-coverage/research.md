# Phase 0 research: the coverage report

**Feature**: `003-route-coverage` | **Date**: 2026-08-22 | **Spec**: [spec.md](./spec.md)

The spec arrived with both clarifications resolved and two external-review corrections
already folded in, so nothing here is a `NEEDS CLARIFICATION`. What follows are the
design decisions the plan rests on, each with the alternative it rejected. Where a
decision reads a requirement in a particular way, that reading is written down — because
the next person to touch this will read the requirement, not the code.

---

## D1 — The report is a pure core computation, with its records beside the other results

**Decision.** Computation in `core/routes/coverage.py`; result records in
`core/results/coverage.py`. No new package.

**Rationale.** Exactly the split feature 002 established: `core/routes/cost.py` computes,
`core/results/ramp.py` holds the frozen records it produces. Coverage is the same shape of
thing — declarations in, frozen record out, no clock, no I/O — and putting it anywhere
else would suggest it is a different *kind* of thing. It is not.

**Alternatives rejected.** A `core/coverage/` package: one module of computation and one of
records does not need a package, and a package would invite the report to grow a second
concern. The `api` layer: the report is a domain computation over declarations, and putting
it above `data` would make it untestable without the loader and unusable from `core`.

## D2 — No new plugin interface, and no new code branch per venue, stream or corridor

**Decision.** Coverage is a fold over declared records. The four plugin interfaces are
untouched; the feature adds none and implements none.

**Rationale.** Principle II. Every question the report asks — does a route exist from here
to there, is this endpoint in the spendable list — is a query over data. FR-024 and SC-014
make this executable: a venue declared as data appears in the next report with no source
change. There is nothing here an `Instrument`, `Provider`, `TaxRule` or `ReturnModel` would
be asked to decide.

## D3 — The spendable-endpoint list is owner data, in its own directory

**Decision.** A new declaration file `data/spendable/owner-001.toml`, carrying `owner_id`
and a list of `(venue, currency)` pairs. Loaded by the data layer into a frozen
`SpendableEndpoint` set. Not a root-level file beside `venues.toml`.

**Rationale.** Principle VII, and the boundary feature 002's plan made structural: a
*curated* declaration is a public fact about the world (a corridor, a venue, a fee
schedule) and lives in a shared directory; a *per-owner* declaration is a fact about this
person's life and lives in a per-owner file. FR-004 says in as many words that the
spendable list is "a fact about the owner's life". `data/streams/owner-001.toml` is the
precedent, and putting the spendable list at the root next to `venues.toml` would put
per-owner and curated data at the same filesystem level — the exact distinction the
constitution says makes multi-user cheap later.

**Alternatives rejected.** Root-level `spendable.toml` in the shape of `venues.toml`: reads
tidier, loses the owner boundary. A `spendable = true` flag on the venue table: a venue is
curated and shared; whether the owner spends from it is not a property of the venue, and
the flag would be per-currency anyway.

## D4 — No citation keys on the spendable file, and the exemption argued in the gate

**Decision.** The file carries no `source` / `retrieved_on` / `verified_on`, and it is **not**
added to `scripts/check_provenance.py`'s `SOURCED_DIRS`. It *is* named in that script's
`EXEMPT_DIRS`, with the reason recorded beside it.

**Rationale.** FR-023: the report contains no observed values, and neither does this file —
an id, a currency code, and the owner's statement of where he spends. There is no number
here for a source to vouch for. This is the same reading `data/venues.toml` already carries
in its own header, and the same exemption `data/streams/` already has for the same reason.

⚙ **Amended 2026-08-23. The mechanism sentence was stale before the feature landed, and the
decision it served was not.** This decision originally read "the gate agrees by construction:
`SOURCED_DIRS` does not list this directory, so it is out of scope without touching the
script." Between planning and landing, the 002 code review made the gate **fail-closed** over
the whole data tree: its directory list had been an *allowlist*, so a new directory — the very
place a future rate is most likely to land — was exactly the place the gate could not see.
That is fail-open, which the constitution puts in its top severity class, in the one script
whose job is to prevent it.

So "not listed" is no longer a way to be out of scope; it is now an error. The exemption has to
be **written down in the script, by name, with its argument**, which is a stricter regime than
the one this decision assumed and not a weaker one: what was previously true by omission now
has to be defended in a sentence a reviewer reads. The decision — *no citation keys on this
file* — is unchanged. **Confirm both halves rather than assume either**: a task asserts
`spendable` is absent from `SOURCED_DIRS` **and** present in `EXEMPT_DIRS` with a non-empty
reason, and that the gate is green with the file present.

## D5 — Destinations are derived: venue × holdable currency

**Decision.** `Destination(venue_id, currency)` for every declared venue and every currency
that venue declares it can hold. Not a separately declared list.

**Rationale.** FR-001's ⚙ says so, and the reason is the feature's whole point: a venue with
zero routes must be visible as a hole *the moment it is declared*, not when someone tries to
cost it. `Venue.currencies` already exists and is already load-checked against every leg.

## D6 — What matches, exactly

**Decision.** Within one regime's route set:

- **Inbound match** for `(destination, stream)`: a declared route with
  `direction == "inbound"`, `origin == stream.arrives_at`, `destination == destination.venue_id`,
  `legs[0].from_ccy == stream.amount.currency`, `legs[-1].to_ccy == destination.currency`.
- **Exit from a destination**: a declared route with `direction == "exit"`,
  `origin == destination.venue_id`, `legs[0].from_ccy == destination.currency`.
- **Spendable exit**: an exit whose `(destination, legs[-1].to_ccy)` is in the declared
  spendable set.

**Rationale.** This is the same chaining discipline the loader already enforces on legs,
applied at the audit level, and it is the same rule `core/routes/cost.py` applies when it
refuses a funding mismatch — which is what makes FR-018 checkable rather than aspirational.
The currency endpoints matter: a route from the right venue in a currency the stream does
not arrive in does not carry that stream's money (spec Assumptions).

**Not used: `partner_route`.** An exit is found by its own direction and origin, never by
following an inbound route's partner link. Two reasons: an exit declared without being
anyone's partner must still count as a declared way out, and reading coverage off the
partner field would be one short step from FR-006's forbidden "reverse the inbound".

## D7 — A pair can carry two deficits at once, and FR-003's kind 2 is read as "no exit at all"

**Decision.** A not-ready verdict carries at most one *inbound* deficit and at most one
*exit* deficit, and may carry both. The exit deficits are mutually exclusive:
`no_exit_declared` (nothing leaves this destination) and `exit_not_spendable` (something
leaves, none of it lands on the declared spendable list).

**Rationale.** FR-003 names kind 2 "inbound exists but no exit partner", but the spec's own
edge case — "a pair missing both its inbound and its exit" — and FR-011 require both
missing declarations to be listed and both marked not-alone-sufficient. So the exit deficit
cannot be conditioned on the inbound being present. The reading: kinds 2 and 3 classify the
*exit* side, and the inbound side is reported independently. This is a widening of FR-003's
phrasing, not a narrowing of its intent — the three deficits remain distinguished, and no
bare "missing route" exists anywhere.

## D8 — A missing declaration has no regime field; the regime is the block it appears in

**Decision.** `MissingDeclaration` is a frozen record of origin venue, origin currency,
direction, and target — for an inbound, the destination venue and currency; for an exit,
the sentinel *any declared spendable endpoint* plus the candidate list. It carries no
regime. It appears inside a per-regime block, and additionally in one cross-regime
`Observation` list that pairs it with a per-regime count.

**Rationale.** FR-014 wants the same missing declaration in two regimes to be *recognizably
one declaration*. A regime field would make two value-equal records unequal and force the
reader to normalise them by hand. Value equality is the cheapest possible form of
"recognizably one". FR-007's requirement that the missing declaration name the regime it is
missing in is satisfied structurally — it is stated inside that regime's block — and
explicitly by `Observation.blocked_by_regime`, which is a tuple of `(regime_id, count)`
pairs, never a sum.

**The exit target is a set, not a point** (FR-007's second ⚙): identity is origin +
direction, so one missing exit is one to-do item however long the spendable list is, and
blocked-pair counts cannot multiply by it.

## D9 — Ordering is deterministic; ties are reported, not broken

**Decision.** Every collection in the report is a tuple in a stated order: destinations by
`(venue_id, currency)`, streams by id, regimes by id, orphan exits by route id, to-do
entries by `(-blocked_count, direction, origin_venue, origin_currency)`. Equal counts are
additionally recorded in a `ties` field of index groups.

**Rationale.** FR-010 forbids breaking a tie arbitrarily; FR-016 requires the identical
report on every run. Those pull in opposite directions unless the presentation order and
the *claim* are separated — which is exactly what `results/ramp.py::Ranking.ties` already
does for the route ranking. The sort key beyond the count is presentation only; the `ties`
field is the claim, and a reader that honours it cannot mistake position for precedence.

## D10 — Closed routes count, and a verdict says what it rests on

**Decision.** `Ready` carries the routes it relied on with their statuses, plus a derived
`rests_on` of `open` / `constrained` / `closed_only`. `open` requires at least one open
inbound *and* at least one open exit among the relied routes; `closed_only` means every
relied route is closed; `constrained` is the remainder.

**Rationale.** FR-022 and its ⚙: coverage measures *declaration*, because the hole it
exists to surface is a corridor nobody has observed, and the fix for a closed route is not
an observation. But SC-015 requires a ready verdict resting only on closed routes to be
visibly distinct, or the report quietly overstates what can be compared today. A derived
three-value field, beside the statuses it was derived from, is the smallest thing that
carries the distinction without duplicating feature 002's feasibility reporting.

**Alternatives rejected.** A separate `ReadyButClosed` type: the claim is the same claim —
a way in and a way out are declared — and splitting the type would force every consumer to
handle two cases that mean one thing. A bare boolean: loses `constrained`, which is neither
open nor closed and would have to be rounded to one of them.

## D11 — FR-018's consistency property is scoped to route-existence refusals

**Decision.** The SC-009 invariant compares coverage against costing's **route-existence**
refusals only: no matching route, and `ExitCostUnknown`. It does *not* claim that a
ready pair always costs successfully, and the generated registries hold amount and dates
where feasibility cannot bite (above every minimum, below every maximum and cap, inside
every availability window).

**Rationale.** `cost_one` refuses for two different reasons. One is "there is no such way"
— a funding mismatch, or a partner-less inbound yielding `ExitCostUnknown` — and that is
the same fact coverage reports. The other is `RouteUnusable`: the amount is below a
minimum, the window has closed, the monthly cap is spent. Those are *feasibility today*,
which FR-022 deliberately excludes from coverage. An unscoped property would fail the first
time Hypothesis generated a small amount, and the temptation would then be to weaken
coverage rather than the property. Scope it now, in writing, and say so at the assertion
site.

FR-018's own forward note is the other half: when feature 004 composes paths, costing will
produce round-trip figures for pairs this report marks not-ready. The reconciliation is a
distinct "reachable by composition only" annotation, not a change to this verdict — and
this property's docstring names that as the thing that will have to change.

## D12 — "No cost figures" is enforced mechanically, not by review

**Decision.** A contract test walks the report recursively over `dataclasses.fields` and
asserts that no field anywhere holds a `Money`, a `Provenance`, a `StalenessVerdict`, or a
bare `float`. Integers (counts, indices) are the only quantities permitted.

**Rationale.** SC-004 and SC-008 both say *verified across the whole output, not sampled*.
A recursive type walk is the only reading of "not sampled" that stays true when someone
adds a field in six months. It also covers FR-023 for free: a provenance mark cannot be
restated here if the type cannot appear. The float ban is what makes FR-017 airtight — a
percentage is a float, and there is no legitimate float in this report.

## D13 — Empty dimensions are a typed outcome from core, and a refusal at the loader

**Decision.** `coverage(...)` returns `CoverageReport | RegistryDimensionEmpty`, where the
latter names **every** empty dimension of `venues`, `streams`, `routes`, `spendable`. The
loader separately refuses an empty `data/spendable/` directory and an empty `[[spendable]]`
list, naming the file.

**Rationale.** FR-020 and predecessor defect B10: an empty report is indistinguishable from
full coverage, so there must be no code path that produces one. Core needs the typed
outcome because core can be called with empty mappings directly, which the tests do. The
loader needs the refusal for the reason `ramp_from_data_root` already gives about empty
directories: a mistyped path and an empty world are indistinguishable downstream, and one
of them is a mistake. An empty spendable *list* gets the same treatment as an empty
directory — a file with no entries would silently make every exit deficit 3, which is a
confident wrong answer built out of a forgotten line.

**Note.** `spendable` is a dimension of *this* feature, not of feature 002's registry.
Naming it alongside the three FR-020 lists is a widening, taken because leaving it out
would produce exactly the confident-but-empty report FR-020 exists to forbid.

## D14 — No regimes declared means one implicit regime, and the report says so

**Decision.** With an empty `regimes` mapping, the report contains a single block whose
`source` is `implicit` and whose route set is every declared route. Its id is the reserved
string `(no regime declared)`. A declared regime carrying that id is refused as a typed
outcome rather than silently shadowed.

**Rationale.** FR-015. The parenthesised id is not a valid-looking identifier anywhere else
in the registry, so it reads as a statement rather than as something the owner declared —
and `source` carries the fact structurally so no consumer has to string-match the id. The
refusal exists because "MUST say that this is what it did" is not satisfied by a block the
owner cannot tell apart from his own.

## D15 — Advisory status is stated in the output, not only in the spec

**Decision.** `CoverageReport.enforcement` carries a module-constant sentence saying the
verdicts are advisory, that feature 002's ranking is unaffected, and that enforcement is a
recorded deferral. SC-020 additionally asserts a ranking is identical with and without the
report produced.

**Rationale.** FR-019 requires it in as many words: "the report itself MUST state that its
verdicts are advisory ... so a reader of the output, not only of this spec, sees the gap".
The ranking-identity assertion is nearly free — both computations are pure — and it is what
catches the day someone makes coverage "helpfully" prune a ranking.

## D16 — Declarations are audited by id in core; files stay in the data layer

**Decision.** `CoverageReport.audited` holds sorted tuples of the venue, stream, route and
regime ids and the spendable pairs that produced the report. It holds no `Path`.

**Rationale.** FR-021 wants the exact declaration set identified. Core cannot import
`pathlib` (`.importlinter` forbids it, and the reason is determinism, not tidiness). Ids are
the identity; the data layer already keeps `route_files` and friends beside them, and
`terezy.data.manifest` is where a digest belongs if one is ever wanted. Recording the ids in
core keeps the report self-describing without dragging the filesystem into it.
## D17 — The audit runs against one named scenario, and two are never blended

**Decision.** `resolve_coverage(...)` and `coverage_from_data_root(...)` take a **required,
nullable** `scenario_id`. A named scenario resolves to that scenario's regimes, keyed by
regime id, and `CoverageDeclarations` carries them as the `regimes` argument `coverage()`
takes. `scenario_id=None` is FR-015's single implicit regime. An unknown id is refused at
load, naming the scenario directory, the files read and every declared scenario id.

**Rationale.** Until this decision the loader could not produce a `regimes` mapping at all:
`CoverageDeclarations` exposed `ramp.scenarios` and nothing flattened `ScenarioDeclaration.regimes`,
so every real-data call site passed `regimes={}` — including the feature's own contract test.
On the shipped registry, which declares `wartime` and `normalized` in
`data/scenarios/war_end.toml`, that produced `source="implicit"`, no audited regime ids, and an
audit of **every** declared route: a route set no declared regime believes in. FR-013's and
FR-015's per-regime audit was unreachable from real data and untested through the loader.

**A scenario is the unit of belief.** It declares its regimes *and* the transition between
them, so its regimes are alternatives to each other; two scenarios are alternatives to one
another. Pooling two scenarios' regimes into one mapping would produce a report about a world
nobody declared — four blocks where the owner holds two beliefs of two regimes each, every
block honestly labelled and the set of them meaningless. So the audit takes one scenario, there
is no way to ask for two, and there is no merge to get wrong. Adding a second scenario file to
the data root changes nothing about a report audited under the first.

**Why the unknown id is refused rather than defaulted to implicit.** The fallback is the
flattering reading of a typo: it audits every declared route, reports `source="implicit"`, and
looks like thorough coverage of a world nobody stated — the confident-wrong output this feature
exists to prevent (Principle I, FR-020's reasoning applied to the regime dimension).

**Why the parameter is required rather than defaulted to `None`.** The two spellings behave
identically until the day an argument is forgotten, and then they differ by exactly that
failure: FR-015's implicit regime is a legitimate answer to *"audit everything"* and an
illegitimate one to *"audit my scenario"*, and only the caller knows which was asked. Required
forces the sentence to be written at every call site; nullable keeps FR-015 reachable without a
second entry point.

**Alternatives rejected.** *Flatten every scenario's regimes into one mapping*: the blend
above, and it also breaks on two scenarios sharing a regime id, where one would silently win.
*Take a `Mapping[str, Regime]` from the caller*: pushes the flattening — and the blend — into
every call site, which is where it would be got wrong quietly. *Default `scenario_id=None`*:
see above.
