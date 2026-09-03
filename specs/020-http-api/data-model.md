# Data model: 020-http-api

Nothing here is a domain record. The core is untouched; what this file describes is the shape
algebra that turns a core record into a schema, the four response envelopes, and the category table
the route set is built from.

## The shape algebra

`plan_of(annotation) -> Shape`, memoised per annotation. `Shape` is a tagged union dispatched with
`match`, and every arm has exactly two consumers: `model_of(shape)` and `encode(shape, value)`.

| Arm | Carries | Model | Encoding |
|---|---|---|---|
| `ScalarShape` | `str`, `int`, `float`, `bool`, `date` | the type itself | the value; a `date` as `YYYY-MM-DD` |
| `LiteralShape` | the literal values | `Literal[...]` | the value |
| `EnumShape` | the enum class | the enum class | `.value` |
| `RecordShape` | the dataclass, its tag, its fields as shapes | a model with `tag: Literal[...]` required, `extra="forbid"` | an object whose first key is `tag` |
| `OptionalShape` | the inner shape | `X \| None` | `null` or the inner encoding |
| `UnionShape` | the member shapes | `Annotated[A \| B, Field(discriminator="tag")]` when every member is a record; a plain union otherwise | the member's own encoding |
| `SequenceShape` | element shape | `list[X]` | a list in declaration order |
| `SetShape` | element shape | `list[X]` | a list sorted by the canonical JSON text of each encoded element |
| `MappingShape` | key kind, value shape | `dict[K, V]` | an object with keys sorted; an enum key by its value, an `int` key in decimal |

`RecordShape` is the only arm that can fail to build, and it fails loudly: a field whose annotation
is a callable, or a type the algebra has no arm for, raises naming the record and the field. Nothing
is skipped and nothing is serialised as a string of its `repr`.

**Hint resolution.** A record's annotations resolve against its own module's globals layered over a
small fallback namespace (`research.md` R3). The fallback is a dict in `shapes.py`; a test asserts
every record reachable from a response type resolves, so a missing name is a red suite rather than a
missing field.

## The tag

`tags.tag_of(record) -> str` returns the override table's entry if there is one and
`f"{module leaf}.{ClassName}"` otherwise. The table is empty. The model name a component is filed
under is `f"{leaf}_{ClassName}"`, and a test asserts both are injective over the reachable set.

## The envelopes

Four families, each a model built by a factory over a category's payload model, each carrying a
literal `tag` of its own and the parameters the read resolved under. Their payload refusals are
ordinary frozen dataclasses under `envelopes.py`, so they go through the shape algebra like any
core record and carry `envelopes.<Name>` tags.

| Envelope | Fields | Where the refusal comes from |
|---|---|---|
| **listing** — `GET /api/{category}` | `tag`, `category`, `as_of`, `scenario_id`, `ids`, and `coverage` on the two series | none: an empty category is an empty list (B10) |
| **read** — `GET /api/{category}/{id}` | `tag`, `category`, `as_of`, `scenario_id`, `declared_in`, `fields`, `result` | `CategoryHasNoSuchId(category, wanted_id, declared_ids, reason)` |
| **singleton** — `GET /api/{category}` for the seven | the same, with `result` the document or its refusal | `NothingDeclared(category, reason)` |
| **observations** — `GET /api/{series}/{id}/observations` | `tag`, `category`, `as_of`, `result` — and inside it `series_id`, `window`, `covers`, `observations` **and** `outside` | `CategoryHasNoSuchId`; `WindowOutsideCoverage(series_id, asked, covers, missing, reason)` **beside** the covered observations, never instead of them |

`declared_in` is the declaring file relative to the data root, or a typed `FileNotRecorded`
carrying the reason where the resolver exposes no file map — one category, `tax-timing`.
`fields` is the ordered descriptor of whichever record the read returned: a name, a kind from a
closed vocabulary, what it names where the kind names something, and whether it is optional. No
label: one invented here would be a second vocabulary nobody could correct.

Beside them, three fixed endpoints with their own models: the registry summary, the answer, and the
committed OpenAPI document served verbatim.

`coverage` is filled only by the two series categories, and it is what FR-045a requires: a client
that has never seen the series can construct a window from the list read.

`as_of` is a **required** query parameter on every endpoint that reads declared data, echoed in
every envelope (owner decision 2026-09-03). No code path in this feature reads the clock.

## The category table

Twenty-five rows. `scenario` marks the six whose entry point takes a `scenario_id`, defaulting to
*no scenario in force*. Counts are what the shipped `data/` resolved to on 2026-09-03 and are
asserted by the suite rather than trusted from here.

| Category | Path | Shape | Entry point | Selects | Record |
|---|---|---|---|---|---|
| `instruments` | `/instruments` | keyed | `from_data_root` | `instruments` + `funds` | `InstrumentDeclaration \| FundDeclaration` |
| `groups` | `/groups` | keyed | `from_data_root` | `groups` | `InstrumentGroup` |
| `tax-classes` | `/tax-classes` | keyed | `from_data_root` | `tax_classes` | `TaxClass` |
| `observation-kinds` | `/observation-kinds` | keyed | `ramp_from_data_root` | `kinds` | `ObservationKind` |
| `venues` | `/venues` | keyed | `ramp_from_data_root` | `venues` | `Venue` |
| `channels` | `/channels` | keyed | `ramp_from_data_root` | `channels` | `FxChannel` |
| `routes` | `/routes` | keyed | `ramp_from_data_root` | `routes` | `Route` |
| `streams` | `/streams` | keyed | `ramp_from_data_root` | `streams` | `IncomeStream` |
| `scenarios` | `/scenarios` | keyed | `ramp_from_data_root` | `scenarios` | `loader.ScenarioDeclaration` |
| `spendable` | `/spendable` | singleton · scenario | `coverage_from_data_root` | `spendable` | `tuple[SpendableEndpoint, ...]` |
| `composition` | `/composition` | singleton · scenario | `composition_from_data_root` | `bound` | `SegmentBound` |
| `candidate-ceiling` | `/candidate-ceiling` | singleton · scenario | `candidates_from_data_root` | `ceiling` | `CandidateCeiling` |
| `access` | `/access` | keyed · scenario | `tuple_from_data_root` | `access` | `InstrumentAccess` |
| `seeds` | `/seeds` | singleton | `seeds_and_goals_from_data_root` | `seeds` | `tuple[SeedLot, ...]` |
| `goals` | `/goals` | keyed | `seeds_and_goals_from_data_root` | `goals`, by each goal's own `id` | `Goal` |
| `cpi` | `/cpi` · `/cpi/{id}/observations` | keyed | `inflation_from_data_root` | `series` | `CpiSeries` |
| `inflation-assumption` | `/inflation-assumption` | singleton | `inflation_from_data_root` | `assumption` | `InflationAssumption` |
| `official-rates` | `/official-rates` · `/official-rates/{id}/observations` | keyed | `official_rates_from_data_root` | `series` | `OfficialRateSeries` |
| `tax-schemes` | `/tax-schemes` | keyed | `schemes_from_data_root` | `schemes` | `TaxationScheme` |
| `crediting-destinations` | `/crediting-destinations` | keyed | `schemes_from_data_root` | `destinations`, id `scheme:venue` | `CreditingDestination` |
| `tax-timing` | `/tax-timing` | keyed | `tax_rules_from_data_root` | by jurisdiction | `AssessmentRules` |
| `tax-positions` | `/tax-positions` | singleton | `tax_positions_from_data_root` | the filing decisions and the unsettled positions | `FilingDecisions`, `UnsettledPositions` |
| `early-exit-belief` | `/early-exit-belief` | singleton · scenario | `tuple_from_data_root` | `registries.spread_holds` | `SpreadHolds` |
| `questions` | `/questions` · `/questions/{id}/answer` | keyed · scenario | `answer_from_data_root` | `questions` | `Question` |
| `calendars` | `/calendars` | keyed | `working_day_calendars_from_data_root` | `calendars` | `WorkingDayCalendar` |

**Keyed or singleton is decided by FR-008's test**, and the row records the answer: either the
resolver hands back a `Mapping[str, X]` whose key *is* the selector, or a sequence whose records
carry their own declared `id`. `goals` is the second form; `seeds` fails both and is a singleton;
`access` is keyed on the mapping's key although its record has no `id` of its own.

**Fail-closed both ways.** Every directory under `data/` at any depth and every `.toml` at the data
root is covered by a row or named in the exemption list with its reason (`observations/`,
`instruments/nav/`, `objectives/`, `strategies/`); and every `*_DIR`/`*_FILE` constant in the
resolver is named by a row. Two tests, each red on its own.

## The registry summary

Per category: its shape; whether its directory is **sourced or exempt from the citation
requirement**, and for an exempt one the gate's own recorded reason; for a keyed one the number of declared ids, for a singleton **whether the
document resolved**; the files behind it with each file's digest; the merged provenance of every
record in it; and the count of unverified sources within it.

Digests come from `terezy.data.manifest`'s `file_version`/`file_name` — the same functions
`input_refs` uses — never from a second hashing path, and a file at the data root is named by
its bare name for the reason the manifest gives: keeping the parent would name it after one
machine's layout. The citation verdict comes from `terezy.data.citation_policy`, which the
provenance gate imports, so there is one definition rather than a copy. Merged provenance is
`terezy.core.primitives.provenance.merge` folded over the category's records, so the monoid stays
the single definition of what a union of marks is.

## The bind context

```
BindContext = LOOPBACK | CONTAINER_PUBLISHED_TO_LOOPBACK
```

A closed two-member enum read from `TEREZY_BIND_CONTEXT`. Unset means `LOOPBACK`. A third value
refuses at startup naming both declared ones — never a fallback to the default. The container value
is a claim about where the process runs and is verified against a container marker before it is
honoured; what that verification is worth is stated in FR-027b's terms and nowhere overstated.

| Guard | Where | What it decides |
|---|---|---|
| per-request client check | middleware | under `LOOPBACK`, a request whose client address is absent or not loopback is refused |
| startup address check | `serve.py` | terezy's own entry point refuses a non-loopback address; it takes an address and never resolves a name |
| container marker | `bind.py` | the container context is refused where no marker is found |
| published ports | `docker-compose.yml` + its test | every published port is `127.0.0.1:<port>:<port>` |

## Error and refusal bodies

| Situation | Status | Body |
|---|---|---|
| a declared id nobody declares | 200 | the read envelope carrying `envelopes.CategoryHasNoSuchId` |
| a singleton nothing declares | 200 | the singleton envelope carrying `envelopes.NothingDeclared` |
| a window outside a series' coverage | 200 | the observations envelope carrying `envelopes.WindowOutsideCoverage` |
| an answer the verb refuses | 200 | the answer envelope carrying the `Refused` member, tagged |
| a malformed declaration | 500 | `envelopes.DeclarationFailed`, carrying `file`, `field_path`, `problem`, `remedy` verbatim |
| a path beneath `/api` that is served by nothing | 404 | `service.PathNotServed`, in JSON even where the SPA fallback is mounted |
| any other unknown path, with a built client present | 200 | the client's `index.html` |
| a missing or malformed query parameter | 422 | the framework's validation body, naming the parameter |
| a non-loopback or absent client under `LOOPBACK` | 403 | `middleware.NotOnLoopback`, naming the release gate |
| a `Host` header the service does not declare | 400 | `middleware.HostNotDeclared`, naming the declared hosts |

A typed refusal is never a status code alone, and the envelope shape is the same whether the result
was a record or a refusal.
