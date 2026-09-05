# Research: 020-http-api

Six things the specification left to the plan, each settled by a measurement over this tree rather
than by preference. Every figure below is reproduced by a test in the feature; none of them is
restated in a docstring.

## R1 — How a core record becomes a schema without a second copy of it

**Decision.** One `Shape` per annotated type, derived once and memoised, with two folds over it: a
Pydantic model for the document, and an encoder for the body.

**Rationale.** The alternative — hand-written response models mirroring 155 core records — is the
one-fact-two-places failure the constitution names, in the file whose whole purpose is to be
generated from. A single walk with two folds cannot disagree about a field's presence, and FastAPI
validating the encoder's output against the generated model (`extra="forbid"`, every field required
unless the annotation says otherwise) turns any disagreement into a failed request rather than a
wrong body.

**Alternatives considered.** (a) Pydantic dataclass adapters over the core records: rejected because
they cannot impose FR-019's ordering on a `frozenset` and cannot add FR-011's tag without a field on
the core record, which FR-011 forbids. (b) A single generic walker with no shape value, branching on
`typing.get_origin` at both call sites: rejected because that is two walkers, and the drift it invites
is exactly what the shape exists to prevent.

**Measured while deciding.** 155 records are reachable from the response roots; the graph has **no
cycles**, so no forward reference and no `model_rebuild()` is needed, and **no callable-typed field**
is reachable, so the encoder needs no refusal for one.

## R2 — The tag, and whether it needs an override on day one

**Decision.** `<module leaf>.<ClassName>`, required (no default) in the schema, in a field named
`tag`. The override table lands empty.

**Rationale.** FR-012 measured injectivity over all 314 core records; over the 155 this feature
actually reaches it holds too, with 155 distinct tags. The field name `tag` collides with **no** field
of any core record — measured over all 584 distinct field names — while `kind` collides with eleven,
`SourceRef.kind` among them, which is why the obvious name is the wrong one.

**Alternatives considered.** The bare class name collides twice in the core (`Question`,
`TaxCurrencyConversionUnavailable`) and the fully-qualified path puts the package layout in a wire
contract. Both are rejected in FR-012 itself; the measurement here only confirms that the chosen
scheme needs no tie-break entry yet.

## R3 — Resolving annotations that name a `TYPE_CHECKING` import

**Decision.** Resolve each record's hints against **its own module's globals**, layered over a small
explicit fallback namespace, with the module's own names winning. A test asserts that every record
reachable from a response type resolves.

**Rationale.** `typing.get_type_hints` with the module globals alone fails on **15** of the 314
records, every failure naming a `TYPE_CHECKING`-only import (`Provenance`, `Currency`, `Money`,
`Mapping`, `Route`, `InstrumentAccess`, `InstrumentGroup`, `FxChannel`, `IncomeStream`,
`TaxableEventKind`). Supplying one flat namespace built from every core module instead — the first
attempt — is worse than useless: it shadows `date` and `Mapping` and produces failures on records
that resolve perfectly well on their own, which is the spec's own warning about a figure that depends
on what namespace the caller supplies. Module globals first, fallback second, and a test over the
whole reachable set so a sixteenth case cannot pass unnoticed.

## R4 — A declared total order for every unordered collection

**Decision.** Encode the elements, then sort by the canonical JSON text of each encoded element. One
rule, applied by the serialiser, for `frozenset[str]`, `frozenset[int]`, `frozenset[Enum]` and
`frozenset[record]` alike. Mappings are emitted in sorted-key order.

**Rationale.** FR-019 asks for an ordering that is a property of the serialiser rather than of each
call site. A per-type key table would be a second enumeration of the eleven `frozenset` fields — and
the constitution's rule is that an enumeration of things declared elsewhere is a check or it is not
written. Sorting by the encoded form needs no table, is total, and moves only when the encoding
moves.

**Measured.** Eleven `frozenset` fields in the core, ten of them not provenance:
`DeclaredWeek.rest_days`, `Question.subjects`, `Venue.currencies`, `TaxClass.applies_to`,
`Regime.route_ids`, `Registries.spendable`, and `accounts_for`/`excludes` on both `HurdleRate` and
`TupleOutcome`. Four `Mapping` fields have a non-`str` key — `tax_classes` on the instrument and the
fund declaration (`TaxableEventKind`), `AssessmentRules.methods` (`LotMethod`) and
`FilingDecisions.by_year` (`int`) — so the encoder stringifies a key by its enum value or its
decimal form, and the model keeps the key type so the document says what a key may be.

## R5 — Which resolver entry point backs which category, and what a keyed category's id is

**Decision.** The table in [data-model.md](./data-model.md), verified by loading the shipped `data/`
during planning: every one of the twenty-five entry points resolves, and the counts are 30
instruments + 3 funds, 7 tax classes, 2 groups, 11 observation kinds, 9 venues, 3 channels, 10
routes, 2 streams, 1 scenario, 33 access records, 2 seed lots, 1 goal, 1 CPI series of 411
observations, 1 official-rate series of 2439 observations, 2 schemes, 5 crediting destinations, 2
tax-timing jurisdictions, 1 question, 1 calendar.

**The one id that is not a string in the resolver**: `SchemeDeclarations.destinations` is keyed by
`(scheme id, venue id)`. The category encodes it as `scheme:venue` — `ua_fop_group_3_non_vat:fop` —
because a path segment must be one string and neither part contains a colon. The decoding is in one
function beside the category row, and the list read publishes the encoded ids, so a client never
composes one itself.

**`ScenarioDeclaration` is a `data`-layer record**, not a core one, so its tag is
`loader.ScenarioDeclaration`. No core module is named `loader`, so the scheme stays injective across
the two layers.

## R6 — Reproducible bytes for the OpenAPI document

**Decision.** `json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False)` plus a
trailing newline, written by `scripts/generate_openapi.py` and compared byte for byte by the suite.
`info.version` is a literal constant in `document.py`; `info.title` is a literal too.

**Rationale.** FR-039 needs a fixed key order and no value read from the clock, the environment or
the filesystem. `sort_keys` gives the first; a literal version gives the second, and FR-041 explains
why the package version — read from installed distribution metadata — cannot. The document is served
from the committed file verbatim (FR-038a) rather than re-serialised, because the framework's JSON
response writes compact separators and no trailing newline, and a client told the file is its source
of truth must not get different bytes from the endpoint.

## R7 — What the two guards can and cannot promise

**Decision.** The per-request client check is a middleware and is built first; the startup check is a
second, earlier refusal in terezy's own entry point. The container claim is verified by looking for
`/.dockerenv` or a container runtime named in `/proc/1/cgroup`, and the verification's worth is
stated as what it is.

**Rationale.** FR-029 ranks them and FR-027b bounds the claim: a marker can be forged, so what the
check buys is that publishing to a network stops being one environment variable. Nothing this
feature writes may say the restriction cannot be defeated, and SC-013a scans the added modules and
prose for that claim-shape.

**Measured.** The installed versions match the spec's reviewed table exactly — `fastapi` 0.141.1,
`starlette` 1.6.0, `uvicorn` 0.52.4, `pydantic` 2.13.4 — so the pins record what was reviewed rather
than what a resolver happened to pick. `colorama` is in the lock behind a Windows marker and is not
installed here, which is why the closure test includes markers without evaluating them.
