# Feature Specification: The HTTP API — the schema the UI is a client of

**Feature Directory**: `specs/020-http-api`

**Feature Branch**: `spec/020-http-api` (spec-writing worktree; squash-lands per `specs/README.md`)

**Created**: 2026-09-03

**Status**: **Spec** — the three clarifications are **answered** (owner, 2026-09-03,
`specs/decisions/2026-09-03-clarify-020.toml`), and each answer is written into the requirement it
governs rather than left in the question. The first of them **defers the display switch entirely**,
which is a narrower feature than either of the standing behaviours the draft shipped: what was
offered is kept under "Display currency — deferred by owner decision", because the record of what
was declined is what stops it being re-proposed as new.

**Input**: Owner decision of 2026-09-03 lifting the D-B deferral of the delivery surface. The stack
is decided and this specification does not reopen it: FastAPI over Pydantic v2, an OpenAPI document
generated from the types and checked in, uvicorn on loopback, packaged with `docker-compose`. What
the specification decides is what the surface *says* — which is where every honesty rule in this
repository either survives serialisation or is lost at it.

---

## Why this feature exists

Constitution Principle III already names this layer's job: *orchestration lives in the API layer*,
and `ui/` is *a client over `api/`, never over `core/`*. `src/terezy/api/` has held that
orchestration — the diagram builders and the answer verb — and has never spoken HTTP. This feature
is the HTTP surface, and one paragraph in `src/terezy/api/__init__.py` says why now rather than
earlier:

> Per owner decision D-B the web UI framework is deliberately deferred until the result schema has
> stabilised against real output; this layer is designed as the UI's only contract so that choice
> stays cheap.

The schema has now met real output — feature 016 declared 24 real securities and feature 018
populated a real rate series — so the deferral's own condition is met.

### The defect this feature is one edit away from

Serialisation is where a type system stops helping. Measured on 2026-09-03 over
`src/terezy/core/` by loading every module and reading `dataclasses.fields`: **314 frozen records,
143 of them under `core/results/`, and not one of them carries a field that names its own kind.**
**Twenty-seven** field annotations across the core spell `Literal[` in a class body — counted from
the AST, which is the measurement `scripts/check_enumerations.py` already takes and the only one that
reproduces. Some are domain values — `side`, `part`, `cause`, `basis`, `solved_for` — and **seven are
structural markers**: `is_assumption: Literal[True]` on five records and `is_assumption_driven:
Literal[True]` on two.

**Not one of the twenty-seven names its record's kind.** The markers come closest and still do not:
`is_assumption: true` is identical on `SpreadHolds`, `RegimeTransition`, `InflationAssumption`,
`ChosenPoint` and `ExchangeRateAssumption`, so it separates assumptions from observations and tells a
client nothing about which of the five it is holding. Calling all twenty-seven domain values was
tidier and wrong; the claim that matters survives either way.

The count is deliberately of *spellings* and not of resolved types. More fields than that resolve to
a `Literal`, because aliases such as `RouteStatus` carry some, but the resolved count is **not a
reproducible number**: `typing.get_type_hints` fails on records whose annotations name imports made
under `TYPE_CHECKING`, and how many it fails on depends on what namespace the caller supplies — three
attempts at this paragraph produced three different figures. A spec whose method is checkable
measurement does not get to quote the one that is not, and the claim it supports holds under either:
no field of any of the 314 records names its own kind. What tells one refusal from another
today is the Python class, which `match` reads and JSON does not.

That is not an abstract concern, because **ten groups of records in the core share an identical
field set**. Three of them are the difference between two answers:

| Records | Their whole field set | What a client cannot tell apart |
|---|---|---|
| `NoHorizonDeclared`, `NoSubjectDeclared`, `BasisKnown` | *(no fields at all)* | "you declared no horizon" from "you declared no subject" — and both from a `BasisKnown` that is not a refusal at all. All three serialise to `{}` |
| `AmountForAnUndeclaredStream`, `StreamWithNoAmount` | `stream_id` | "that stream does not exist" from "that stream got no money" |
| `NoExitTermsDeclared`, `InstrumentRefused`, `TwoFiguresNotOne`, `PlanDoesNotFitInstrument`, `NoPlanSupplied`, `LotNotNamed` | `instrument_id`, `reason` | six records across three families — four of `TupleRefused`'s seventeen, plus one reached through `SectionOutcome` and one from the ledger's lots |

And one of them is a constitutional prohibition:

> Round-trip cost is the number that belongs in a comparison. A one-way figure may **never** be
> reported as if it were round-trip. *(Principle VI)*

`OneWayCost` and `RoundTripCost` (`src/terezy/core/results/ramp.py`) have **the same nine fields in
the same order**. `docs/REQUIRED_TESTS.md` row G6 records how that prohibition is currently kept:
they *"are unrelated frozen records, so assigning one into the other's slot is a mypy strict error
rather than a convention"*. Serialised without a tag they are one shape, and the guard that has
held since feature 002 stops at the socket. FR-011 and FR-012 are what carry it across.

### The second defect, which has a version number

FastAPI serves its interactive documentation by fetching its assets from public CDNs. Read out of
the installed `fastapi.openapi.docs` on 2026-09-03, its two default pages reach **three external
hosts across five asset URLs**: `cdn.jsdelivr.net` for `swagger-ui-bundle.js`, `swagger-ui.css` and
`redoc.standalone.js`; `fastapi.tiangolo.com` for the favicon on both pages; and
`fonts.googleapis.com` for ReDoc's Montserrat and Roboto. Principle VII says **no CDN calls**, in a
repository whose stated purpose is holding one person's complete financial position, and both pages
are served by default with no setting anybody chose. The default is the defect; FR-031 turns it off
and asserts it stays off.

### What this feature is not

It is not the authentication gate, and it does not weaken it. Principle VII:

> **Release gate:** authentication must exist *before* the application listens on any interface
> other than loopback. This is a blocking gate, not a backlog item.

The gate stays exactly where it is. What this feature adds is that listening anywhere else is not
expressible — not defaulted-off, not flag-guarded, not configuration. FR-026 to FR-030.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The owner reads a declared category in a browser (Priority: P1)

The owner opens the API on his own machine and asks what routes are declared. He gets every route
the loader resolves, each with its legs, its caps, its channel, its declared ids — and beside every
figure, whether the source behind it has ever been verified.

**Why this priority**: it is the feature. Twenty-five declaration categories are reachable from the
resolver — one per `*_DIR`/`*_FILE` constant, counted 2026-09-03 — and the only way to read any of
them today is to open a TOML file, which shows what was written and not what the loader made of it.
The two differ exactly where the cross-file checks live, which is the half a file cannot show.

**Independent Test**: start the service against the shipped `data/` and request each declared
category. For a keyed category, check that every id the loader resolves appears and no other; for a
singleton, that the one resolved document comes back and that no id-shaped route exists.

**Acceptance Scenarios**:

1. **Given** the shipped data root, **When** a **keyed** category is requested, **Then** the response
   lists exactly the ids that resolver entry point returns, and a request for one id returns that
   record.
2. **Given** an id nothing declares, **When** it is requested from a keyed category, **Then** the
   response is a typed refusal naming the category and the ids that are declared — never an empty
   object and never a bare 404 body.
2a. **Given** a **singleton** category, **When** it is requested, **Then** the one resolved document
   comes back, and the category offers no id-shaped route to ask the wrong question through.
3. **Given** a data root with a malformed declaration, **When** any category is requested,
   **Then** the load failure reaches the caller naming the file and the field, as
   `DeclarationError` already does at the CLI (`H2`), and no category returns partial data.

---

### User Story 2 - A refusal is something a client can act on (Priority: P1)

The owner asks a question the tool cannot answer. The answer he gets back names *which* refusal it
is, in a field a program can switch on, alongside everything that refusal knows.

**Why this priority**: equal-highest, and it is the half a schema gets wrong silently. A refusal
that arrives as an untagged object is not a refusal — it is a shape, and a client that cannot tell
`{}` from `{}` renders "something went wrong", which is the one thing `docs/DIRECTION.md` says this
project must never become: *a chart that cannot express "this figure refuses to exist, and here is
why" is worse than a table that can*.

**Independent Test**: for every member of every refusal union reachable from a response type,
produce the response and assert the tag is present, distinct, and matches the member the engine
returned. Discovered by walking the response types, never from a hand-written list.

**Acceptance Scenarios**:

1. **Given** a question naming a stream nobody declares, **When** it is answered, **Then** the body
   carries a tag distinguishing it from a stream that got no money, and both tags appear in the
   OpenAPI document as members of the same discriminated union.
2. **Given** a route whose exit nobody declares, **When** its cost is read, **Then** the one-way
   figure and the round-trip refusal are distinguishable in the body without knowing which field
   they came from.
3. **Given** a new member added to any refusal union in the core, **When** the suite runs,
   **Then** it fails until that member appears in the schema — the scan finds it, no list is edited.

---

### User Story 3 - The document the web client is generated from cannot drift (Priority: P1)

Feature 021 generates its TypeScript types from a checked-in OpenAPI document. A change to a
response record that nobody regenerated is a build failure here, not a runtime surprise there.

**Why this priority**: equal-highest because it is the whole reason the boundary is worth drawing.
An OpenAPI file that is *published* rather than *gated* is a second copy of the schema going
quietly out of step with the first — the exact failure the constitution's prose rules name, in a
machine-readable file.

**Independent Test**: regenerate the document and compare bytes with the committed one; then change
one field on one response record and confirm the comparison fails.

**Acceptance Scenarios**:

1. **Given** the committed document, **When** it is regenerated from the running application,
   **Then** the two are byte-identical.
2. **Given** an added, removed or renamed field on any response record, **When** the suite runs,
   **Then** the comparison fails naming the path that moved.
3. **Given** a change to the pinned HTTP framework version, **When** the suite runs, **Then** the
   comparison fails if the generated document changed — the pin exists so that this is visible.

---

### User Story 4 - Switching the display currency changes only what it is allowed to (DEFERRED)

**Deferred by owner decision 2026-09-03** together with FR-021 to FR-025; kept as the record of what
was offered. Nothing below is built in this feature.

The owner switches the display to dollars. Every realised amount, every tax figure and the ranking
of every candidate are the same bytes they were.

**Why this priority**: P2 because the switch is new surface rather than a correction, and because
its rate source is one of the three open questions. It is not lower than P2 because
`docs/REQUIRED_TESTS.md` rows F2, F3 and F4 have been open since the beginning waiting for exactly
this switch to exist, and F2's tax half is already established *before* the switch, deliberately, so
that a later feature could not close the row without checking.

**Independent Test**: request the same resource twice, differing only in the display parameter, and
compare the two bodies field by field. Everything outside the declared display block is identical.

**Acceptance Scenarios**:

1. **Given** any response containing money, **When** it is requested under each declared display
   currency, **Then** every field outside the display block is byte-identical across the responses.
2. **Given** a ranking, **When** the display changes, **Then** the order of its members and every
   figure they are ordered by are unchanged.
3. **Given** a display currency for which no declared rate exists, **When** it is requested,
   **Then** the response refuses by name and returns no converted figure.

---

### User Story 5 - No supported path publishes the service to a network (Priority: P1)

The owner runs the stack with `docker compose up` and gets a service reachable from his own browser
and from nothing on his network. Editing the compose file to publish it turns the build red, and
there is no single variable that lifts the restriction — FR-027b says plainly what that is worth and
what it is not.

**Why this priority**: equal-highest and it is the one story whose failure is not recoverable. Every
other defect in this feature produces a wrong number; this one produces a stranger reading one
person's complete financial position.

**Independent Test**: assert the shipped compose file publishes every port to `127.0.0.1` and no
other address; assert the application refuses a non-loopback bind under the default context; assert
it refuses the container context on a machine with no container marker; assert the bind-context type
admits exactly two values, that an unrecognised third refuses, and that nothing else widens the set
of addresses it may bind to.

**Acceptance Scenarios**:

1. **Given** the application started under the **default** bind context with a non-loopback bind
   address, **When** it starts, **Then** it refuses, names the constitution's release gate, and
   exits non-zero.
2. **Given** the container bind context named on a machine with no container marker, **When** it
   starts, **Then** it refuses naming the marker it looked for — so the variable cannot be set on a
   laptop to publish the service.
3. **Given** the shipped compose file, **When** it is parsed, **Then** every published port on
   every service is of the form `127.0.0.1:<port>:<port>`.
4. **Given** the shipped compose file, **When** it is parsed, **Then** the `api` service declares
   the bind-context value that permits a container-interface bind, and mounts `data/` read-only.
5. **Given** the service started by a bare server command bound to `0.0.0.0`, **When** a request
   arrives from a non-loopback client, **Then** it is refused — the startup guard is bypassed and
   the per-request one is not.

---

## Requirements *(mandatory)*

### The layer, and what it may import

- **FR-001**: The HTTP surface MUST live in a new module tree `terezy.api.http`, under the existing
  `terezy.api` package. It MUST NOT be a fifth layer: `.importlinter`'s `layers` contract already
  places `terezy.api` above `terezy.data` above `terezy.core`, and this module inherits that
  position rather than adding to the stack.

- **FR-002**: The `.importlinter` contract `core-independent-of-frameworks` MUST remain unchanged,
  forbidding `fastapi`, `starlette`, `uvicorn` and `pydantic` in `terezy.core`. A new contract named
  `frameworks-only-in-the-http-module` MUST forbid `fastapi`, `starlette` and `uvicorn` in every
  other importable module tree — `terezy.data`, `terezy.cli`, `terezy.api.answer` and
  `terezy.api.diagrams` — not merely below `terezy.api`. Together with the scan below, the two
  cover the package.

  **The two package `__init__` modules — `src/terezy/__init__.py` and `src/terezy/api/__init__.py` —
  MUST be covered too, by a source scan.** A `forbidden` contract naming `terezy` or `terezy.api`
  matches its descendants, and one of them is `terezy.api.http`, which has to import the framework;
  so neither `__init__` is reachable by a contract written the plain way, and both are modules an
  import would sit in perfectly comfortably. Closing `answer.py` and leaving these two would be the
  same hole a file away, twice.

  The scan is a **choice, not the only possibility**, and the difference is worth stating because
  the other option looks unavailable and is not: a `forbidden` contract over `terezy` with wildcard
  `ignore_imports` entries exempting `terezy.api.http.* -> fastapi` and its siblings does reach the
  `__init__` files. It is rejected for being an exemption list that has to be maintained in step
  with whatever the HTTP module imports next, in a file whose other contracts state prohibitions
  rather than carve-outs. A scan naming two files says the same thing and goes stale in a way the
  reader can see.

  **An inclusion list needs its own completeness check, and it is part of this requirement.** Four
  module trees plus two files plus `terezy.core` — which `core-independent-of-frameworks` covers, and
  which the list above deliberately does not repeat — is exhaustive over `src/terezy/` as it stands,
  and stops being so the moment somebody adds `src/terezy/api/export.py`, which no contract and no
  scan would then reach, with nothing to say so. A test MUST therefore assert that **every module
  under `src/terezy/` is named by one of the two contracts, named by the scan, or under
  `terezy.api.http`**: fail-closed over the package, the shape FR-006 takes over `data/` and
  `scripts/check_provenance.py` takes over its directories. Both contracts, because a check that
  counted only the new one would be red on every module under `core/`, which is guarded and not
  unguarded. Without it this requirement is the prose
  enumeration of things declared elsewhere that the constitution says is a check or is not written.

  Below-only was the obvious contract and it would not hold the claim. `data-below-api` already
  forbids `terezy.api` in `terezy.data`, so a contract about that boundary asserts something already
  asserted; and neither it nor the layers contract says anything about `terezy/api/answer.py`, which
  is orchestration the **CLI** shares. An `import fastapi` there would leave `lint-imports` green
  while falsifying both FR-001's claim that the HTTP surface is one module tree and FR-004's that
  the CLI is unchanged.

  Not `pydantic` anywhere in the new contract: the data layer already imports it at the load
  boundary, in five modules under `src/terezy/data/declarations/` measured on 2026-09-03, which is
  where the constitution says validation belongs. Forbidding what already exists, then loosening the
  contract to accommodate it, teaches nobody anything.

- **FR-003**: `terezy.api.http` MUST NOT compute a financial figure. It selects, serialises and
  refuses. A scan MUST assert that no module under it imports `terezy.core.primitives.money`'s
  combining functions or constructs a `Money`, on the pattern
  `tests/contract/test_money_construction_guard.py` already uses. There is **no exception**: the
  draft carved one out for the display conversion, and the owner's deferral of the switch closes it,
  so no module under `terezy.api.http` constructs money at all.

- **FR-004**: The CLI MUST be unchanged by this feature. It is a client over `api/` and remains one;
  a second client does not make the first one route through it.

### What is exposed, and how the set is decided

- **FR-005**: The exposed categories MUST be a **mapping from category id to a resolver entry point
  and a response type** — a registry of functions, per the constitution's functional-style clause —
  never a series of hand-written route functions each doing its own loading.

- **FR-006**: The category set MUST be **fail-closed against `data/`**, on `scripts/check_provenance.py`'s
  pattern: **every directory under `data/` at any depth**, and every `.toml` file at the data root,
  is either covered by a declared category or **named in an exemption list with its reason**. A
  directory the mapping does not know is an error, never a blind spot.

  The walk has to be recursive rather than one level deep, because **six** of the resolver's
  twenty-five constants point at subdirectories: `TAX_TIMING_DIR`, `SCHEMES_DIR`, `DESTINATIONS_DIR`,
  `INFLATION_ASSUMPTION_DIR`, `TAX_POSITIONS_DIR` and `EARLY_EXIT_DIR`. A top-level walk would report
  `tax/` and `scenarios/` as covered and stop looking — fail-open in exactly the two directories a
  subdirectory has already been added to twice.

  Measured 2026-09-03 there are **26 directories under `data/`**: 22 covered by a resolver constant,
  and four exempt, each for its own reason:

  | Exempt | Why |
  |---|---|
  | `data/observations/` | No loader exists anywhere in `src/terezy/`. These are a fetch script's raw retrievals — *"the evidence a declaration was checked against"* (`data/README.md`) — read by a human promoting them into a declaration and by nothing at run time. Serving them would make the API the first consumer of data the engine deliberately does not consume. |
  | `data/instruments/nav/` | Deliberately not globbed. `resolver.py` states the reason where it globs the parent: *"a subdirectory holds a different shape of file"*. Empty today; a category for it would be a second instrument shape this feature has no response type for. |
  | `data/objectives/` | Empty but for `.gitkeep`, and no loader exists. |
  | `data/strategies/` | Empty but for `.gitkeep`, and no loader exists. |

  The empty ones are exempt *because nothing loads them*, not because they are empty; the day any of
  the four gains a resolver entry point it gains a category, and the exemption's own reason is what
  stops it being forgotten.

- **FR-007**: The reverse direction MUST also be asserted: every `*_DIR` and `*_FILE` constant in
  `terezy.data.declarations.resolver` MUST be reachable from some declared category. The two
  assertions are separate tests because one contract naming both would stay green if either
  direction were deleted — `.importlinter`'s FR-012/FR-013 pair states this reasoning at its own
  site and it applies unchanged.

- **FR-007a**: Every category's path MUST be a **single flat segment**, and every **route group**
  the application serves MUST own a distinct first segment. A route group is a category together
  with everything nested under its own segment, or a fixed endpoint that is not inside a category's
  subtree.

  Mirroring the directory tree was the obvious design and is wrong: three categories live in
  subdirectories of `scenarios/`, so a path that mirrored the tree would put `/scenarios/inflation`
  beside `/scenarios/{id}`, and a scenario declared with the id `inflation` would be unreachable,
  silently, on a tree the shipped data is one file away from.

  The check MUST be over **owners of a first segment**, not over paths, and must include the fixed
  endpoints: `/registry` and `/openapi.json` are declared outside FR-005's mapping, so a category
  later given the id `registry` would shadow the summary endpoint with nothing going red — the same
  silent unreachability one level up. A check written over paths instead would be red against this
  feature's own route table on the first run, because `/questions` and `/questions/{id}/answer`
  share a first segment by design, as do `/cpi` and `/cpi/{id}/observations`. Those are one group,
  not two owners.

  Distinctness rather than a no-prefix rule: flat segments cannot collide by prefix, and a no-prefix
  rule would forbid a legitimate future `/tax` beside `/tax-classes` for no reason.

- **FR-007b**: A category read MUST state **which scenario it resolves under**, and the scenario MUST
  be a **request parameter** on the categories that need one, defaulting to *no scenario in force*.
  The response MUST name the scenario it resolved under — including when that is none — so the answer
  is never silently one of several.

  It is a requirement rather than an implementation detail because five of the resolver entry points
  in the endpoint table take a required keyword-only `scenario_id: str | None`, and they back six
  categories: `/spendable`, `/composition`, `/candidate-ceiling`, `/access`, `/early-exit-belief` and
  `/questions`. The choice changes what comes back —
  `tests/contract/test_coverage_scenario_scoping.py` exists because it does — and `/scenarios` is
  itself a served category, so the values are real declared data a caller can discover. A spec silent
  on this leaves an implementer to invent a parameter or hardcode `None`, and hardcoding it is a
  serving decision taken inside a serialiser, which is what FR-003 says this layer does not do.

  The default is *no scenario* rather than a declared one because `IMPLICIT_REGIME_ID` is already what
  the engine means by an unnarrowed registry, and because a default naming some scenario would make
  the plainest possible request — no parameters — answer under a world nobody asked for.

- **FR-008**: Every category MUST declare its **shape** in FR-005's mapping, and there are exactly
  two:

  | Shape | What it offers | Why |
  |---|---|---|
  | **keyed** | a **list** of the ids it declares, and a **read of one id** | the category resolves a collection an id selects from — instruments, routes, channels, questions |
  | **singleton** | a **read of the one resolved document**, and no id at all | the category resolves to one per-owner document, and there is no id to select with |

  A keyed read of an id nothing declares MUST be a **typed refusal carried in the body**, naming the
  category and the declared ids: never an empty object, never a status code alone, and **never a load
  error**.

  `terezy.api.answer._declared_question` is the right precedent for the **message** — it names the
  declared ids, which is the part worth copying — and the wrong one for the **outcome**. It `raise`s
  `DeclarationError`, and `cli/main.py` maps that to `LOAD_FAILED = 2`, which is the category FR-016
  exists to keep apart from `REFUSED = 1`. An implementer copying the function wholesale produces a
  broken-declaration error for a caller who merely asked about an id that does not exist — a
  well-formed question with a typed answer, reported as a broken data root. The same trap sits under
  `/questions/{id}/answer`, whose `answer_question` reaches that identical raise.

  Two shapes because one does not fit, and the misfit is not marginal. Seven categories are
  **per-owner single documents** resolved by an at-most-one rule rather than keyed collections:
  `composition/`, `candidates/`, `spendable/`, `seeds/` and the three under `scenarios/`. Measured
  2026-09-03, `data/scenarios/tax/owner-001.toml` declares an `owner_id` and **no `id` at all**, and
  `seeds/`'s lots carry an `instrument_id` rather than an id of their own — so "the ids it declares"
  has nothing to return for them, and a single-shape requirement would be unimplementable for them.

  **`goals/` is keyed and is the case worth stating**, because it looks like the others and is not:
  it is per-owner and single-file like `seeds/`, and yet `data/goals/owner-001.toml` declares a goal
  with its own `id` (`flat_deposit`) beside the owner id, so there is something for a read to select.

  **The test is whether a declared string addresses one record, and it takes two forms.** Either the
  resolver returns a `Mapping[str, X]` — its key *is* the selector — or it returns a sequence whose
  records carry their own declared `id`. Neither "per-owner" nor "the record owns an `id` field"
  separates the cases on its own, and the second is measurably wrong: `InstrumentAccess` carries
  `instrument_id`, `bought_at`, `proceeds_to`, `quote`, `resale_price` and `risk_class` and **no `id`
  of its own**, while `Registries.access` is a `Mapping[str, InstrumentAccess]` — so `/access` is
  keyed on the mapping's key. `seeds/` is a singleton under the same test: `resolver` returns
  `tuple[SeedLot, ...]`, no mapping, and a lot carries an `instrument_id` naming what it holds rather
  than an id naming itself, so two lots in one instrument would collide.

  The shape is a field of the mapping rather than a sentence here, so a category added later has to
  state which it is, and a test MUST assert that every keyed category's selector actually resolves —
  against the resolver's own mapping key or against a declared `id` on its records, whichever that
  category uses.

- **FR-009**: A **registry summary** endpoint MUST report, per category: its **shape**; for a keyed
  category the number of declared ids and for a singleton **whether the document was resolved at
  all**; the files behind it with each file's digest; the merged provenance of everything in it; and
  the count of unverified sources within it.

  A singleton reported as a count would say `0` for a category whose document resolved fine, which is
  the same body a caller would get for a category the loader found nothing in — the B10 distinction
  between *empty* and *absent* collapsing at the one endpoint whose job is to say what the registry
  holds.

  **The file digests are a re-export; the rest is new computation.**
  `terezy.data.manifest.input_refs` and its per-family siblings already produce per-file references
  with digests from a loaded `Declarations`, with no run involved, and the summary MUST use them
  rather than digesting files a second way — two functions hashing the same file is exactly the one
  fact in two places that drifts. What does not exist on 2026-09-03 is the per-category counts, the
  merged provenance and the unverified counts; those are new, and FR-010 is what keeps them honest.

- **FR-010**: The summary's provenance per category MUST be the **merge** of the provenance of every
  record in it, computed through `terezy.core.primitives.provenance.merge`, so that one unverified
  source in a category marks the category. Recomputing the union any other way would reintroduce the
  order-dependence that module's docstring exists to rule out.

### Refusals, tags, and the thing a client switches on

- **FR-011**: Every serialised record MUST carry a **tag** naming which record it is. The tag MUST
  be **derived by the HTTP layer from the record's own identity** and MUST NOT be a field added to a
  core record: the core has no delivery surface and acquiring one to please a serialiser is the
  inversion `.importlinter`'s `core-independent-of-frameworks` contract exists to prevent.

- **FR-012**: The derivation MUST be `<module leaf>.<ClassName>` — `answer.NoHorizonDeclared`,
  `ramp.OneWayCost`. Measured on 2026-09-03 over all 314 frozen records in `terezy.core`, this rule
  is **injective**: 314 records, 314 distinct tags.

  The bare class name is not available and the reason is measurable rather than hypothetical: two
  class names each occur twice in the core — `Question` in `results.candidates` and
  `results.question`, and `TaxCurrencyConversionUnavailable` in `results.tuple` and `tax.year`. The
  second of those is a refusal, so a bare-name scheme collides on a member a client has to narrow
  on. The fully-qualified path was rejected for a different reason: it embeds the package layout in
  a wire contract, so moving a module renames a tag every client switches on.

  A test MUST assert injectivity over every record reachable from any response type, so that the
  day a collision is introduced the build says so rather than a client silently narrowing to the
  wrong member.

- **FR-012a**: The scheme MUST carry a **tie-break, declared in the HTTP layer**: a table mapping a
  named record to an explicit tag, consulted before the derivation, and empty on the day this feature
  lands. When FR-012's injectivity test goes red the remedy is one line in that table — never a
  rename in `terezy.core`.

  It is needed because injectivity today is luck, and the measurement says how much. Ten module
  leaves are duplicated inside `terezy.core` — `answer`, `candidates`, `canonical`, `capacity`,
  `coverage`, `fund`, `interface`, `registry`, `schedule`, `streams` — so `leaf.ClassName` is
  injective only because no two same-leaf modules happen to declare a same-named class. The day one
  does, a spec with no tie-break leaves exactly two ways out, and both are the inversion FR-011
  forbids: rename a core record to satisfy a serialiser, or rename a module, which is what FR-012
  rejected the fully-qualified scheme for doing. An override table costs one line and keeps every
  existing tag stable, which is the property a wire contract actually needs.

- **FR-013**: Every union reachable from a response type MUST appear in the OpenAPI document as a
  discriminated union — `oneOf` with a `discriminator` whose mapping names every member — and the
  members MUST be **discovered by walking the response type annotations**, never enumerated by hand.
  A hand list is a prose enumeration of things declared elsewhere, which the constitution says is a
  check or it is not written; here it can be the check.

- **FR-014**: The tagging requirement MUST apply to **every** serialised record and not only to
  union members. `OneWayCost` and `RoundTripCost` are not a union — they are two fields on
  `RampCost` — and they have identical field sets. A rule scoped to unions would leave the
  Principle VI prohibition unenforced at exactly the pair the principle names.

- **FR-015**: A refusal's own fields MUST be carried verbatim. The HTTP layer MUST NOT synthesise a
  message, a summary, a severity or a code the record does not carry. This is the CLI's own rule —
  *"it adds no fact to the record"* (`src/terezy/cli/main.py`) — and it is the rule that stops a
  serialiser becoming a second place where the tool decides what happened.

- **FR-016**: A refusal MUST be carried in the **response body**, and the body MUST be the same
  shape whether the outcome was an answer or a refusal. A refusal is a *result*, not an error: the
  CLI already distinguishes `REFUSED = 1` from `LOAD_FAILED = 2` for this reason. A malformed
  declaration is the second kind and MAY use an error status; a typed refusal MUST NOT be
  represented by a status code alone in either case.

### Provenance, which is the reason any of this is worth reading

- **FR-017**: Every figure in every response MUST carry its provenance. A response type that drops
  the mark is a **top-severity defect** (Principle I, and the constitution's "Defect severity"
  clause). A test MUST sweep every money-valued field off the response dataclasses rather than
  sampling, on the pattern `tests/contract/test_provenance_propagation.py` already uses, so a field
  added later is inside the claim.

- **FR-018**: The serialised provenance MUST carry each `SourceRef`'s `id`, `citation`,
  `retrieved_on`, `verified_on` and `kind`, and MUST carry the derived `is_unverified` verdict
  beside them so a client renders the mark without reimplementing the asymmetry.
  `provenance.is_unverified` is *any* source unverified, deliberately; a client that computed it
  from the list would be free to get that backwards, and the answer would then depend on which
  client was reading.

- **FR-019**: **Every unordered collection MUST be serialised in a declared total order**, and the
  ordering rule MUST be a property of the serialiser rather than of each call site. `Provenance.sources`
  orders by `SourceRef.id`; a set of strings or of enum members orders by its own value; a set of
  records orders by a declared key.

  Not `Provenance` alone, which was the first draft and covered one field in eleven. Measured
  2026-09-03 over the 314 core records, **eleven fields are `frozenset`-typed**, and ten of them are
  not provenance: `Venue.currencies`, `TaxClass.applies_to`, `DeclaredWeek.rest_days`,
  `Regime.route_ids`, `Question.subjects`, `Registries.spendable`, and `accounts_for`/`excludes` on
  both `HurdleRate` and `TupleOutcome`. `frozenset[str]` iteration order varies with
  `PYTHONHASHSEED`, so `GET /venues`, `GET /tax-classes`, `GET /calendars` and any answer carrying a
  hurdle rate would return different bytes in different processes.

  That failure is worth naming precisely because of how it hides: within one process the order is
  stable, so SC-009 run twice in one test session **passes**, and the bodies diverge only between
  runs — on a colleague's machine, in CI, or after a restart. A rule scoped to provenance would have
  left ten fields producing a reproducibility claim that is false and green.

- **FR-020**: The response body MUST NOT be the canonical form.
  `terezy.core.results.canonical`'s own module docstring states that **provenance is deliberately
  excluded** from it, because a digest must not move when a `verified_on` is filled in. That
  exclusion is correct for a digest and disqualifying for a wire format: reusing it would satisfy
  FR-017 nowhere. A response MAY report the canonical digest as a field; it may not be built from
  the canonical encoding.

### Display currency — deferred by owner decision 2026-09-03

**FR-021 to FR-025 are NOT in this feature.** The owner deferred the switch («відкладемо перемикач
курсів поки», `specs/decisions/2026-09-03-clarify-020.toml`, answer 1), and the deferral is wider
than the draft's own standing behaviour: there is **no `display` parameter, no display block, and no
call to `money.convert` anywhere in this feature**. Every amount is served in the currency it was
computed in, which is what `Money` already carries.

They are kept below, unedited, as the record of what was offered — deleting them would leave a
future reader to re-derive the three options and re-propose the one that was declined. The
`[[future]]` entry `display-currency-switch` in `specs/features.toml` is what carries them forward,
and `docs/REQUIRED_TESTS.md` rows F2, F3 and F4 stay open with their notes unchanged: a switch that
does not exist closes none of them.

- **FR-021** *(deferred, not in this feature)*: The display currency MUST be a **request parameter**, resolved on the server. The
  client computes nothing. Constitution Principle VI gives currency three roles, and a client that
  converted for display would be a fourth place a rate lives.

- **FR-022** *(deferred, not in this feature)*: A display switch MUST change **only** an explicitly declared display block attached
  beside each amount. It MUST NOT change the amount, its currency, its provenance, any tax figure,
  any ranking, any ordering, or any field a ranking is computed from. A test MUST request the same
  resource under each declared display currency and assert that every field outside the display
  block is **byte-identical** across the responses.

- **FR-023** *(deferred, not in this feature)*: The display block MUST be **additive**. The originally-computed amount and its own
  currency stay in the body under the same field names regardless of the display choice. A display
  that replaced the amount would make FR-022's byte-identity claim untestable, because the field it
  is about would be the field that moved.

- **FR-024** *(deferred, not in this feature)*: Every converted display figure MUST carry the **rate as its source declares it, the
  direction that declaration is in, the factor actually applied, the source of the rate, and the
  merged provenance of the amount and the rate**. The display path MUST go through
  `terezy.core.primitives.money.convert`, which already demands the rate's provenance in its
  signature and refuses a rate of zero or less, and MUST NOT compute a product itself.

  Five fields rather than two, because **the two numbers are not the same number and one of them is
  a reciprocal**. `convert` takes *units of the target currency per one unit of the source's*, and a
  channel declares `reference_rate = 42.0` meaning UAH per USD — so a UAH amount displayed in USD is
  converted at `1/42`, not at `42`. `convert`'s own docstring names this as the classic FX defect:
  *"an inverted rate is the classic FX defect: every figure stays plausible and every one is wrong
  by a factor of the rate squared"*, and it puts the inversion *"in one reviewable place next to the
  channel that supplied the number"*. Reporting only one of the two numbers is what makes the review
  impossible: a reader given `42` cannot tell which way it was applied, and a reader given `0.0238`
  cannot check it against the declaration. Both, with the direction named, and a worked example
  (SC-011a) is what proves the pair agrees.

- **FR-024a** *(deferred, not in this feature)*: Where the requested display currency **is already the amount's own currency**, the
  amount MUST carry **no display block at all**, and `convert` MUST NOT be called for it. It is not a
  conversion and the core says so by raising: *"a conversion from UAH to UAH is not a conversion.
  Same-currency arithmetic goes through scale, add or sub; reaching here means a currency was lost
  track of."*

  Stated as a requirement because it is the **default request**, not an edge case. `display=UAH` on
  a body of hryvnia figures is the ordinary thing a client asks for, and a response mixing hryvnia
  and dollar amounts hits both arms at once — so a rule that only covered "no rate declared" would
  leave the common case raising out of a serialiser. The absent block is also the right answer on its
  own terms: an amount shown in its own currency has nothing to add beside it, and a display block
  echoing the same number at a rate of 1 would be a rate nobody quoted.

- **FR-025** *(deferred, not in this feature)*: Where no declared rate is available for a requested display currency, the response
  MUST **refuse the display block by name**, with the figure and its own currency left intact. Not a
  missing block, not a null, not the amount shown unconverted as though it had been converted.

  This is a different absence from FR-024a's and MUST be distinguishable from it: *nothing to
  convert* and *nothing to convert with* are not the same fact, and a client showing a mark for one
  of them must not show it for the other.

*(End of the deferred requirements.)*

### The bind, and the gate that stays

- **FR-026**: The application MUST refuse to start bound to an address that is not a loopback
  address, unless a **bind context** says otherwise. The refusal MUST name the constitution's
  release gate and say that authentication is what lifts it.

  The guard MUST take an **address**, never a hostname. Resolving a name is a network act, and a
  guard that resolved one would make the suite's no-network rule (FR-050) depend on the machine's
  resolver — green offline for the wrong reason, and nondeterministic online. A caller supplying a
  hostname resolves it first and hands over what it resolved to; the guard's job is to decide about
  an address, and it is testable precisely because that is all it does.

- **FR-026a**: The **per-request client check is the load-bearing half**, and the spec MUST say so
  rather than resting the guarantee on FR-026. `uvicorn terezy.api.http:app --host 0.0.0.0` — the
  framework's own documented way to start a service — never reaches FR-026's guard, because that
  guard runs in an entry point the command does not call. Everything about the bind that a process
  can enforce from inside is therefore enforced per request: under the default context, a request
  whose client address is not a loopback address is refused, however the process was started and
  whatever it bound to.

  The guard MUST be on the **client** address and not on the server's, and **an absent client
  address MUST itself be a refusal**.

  An ASGI scope does carry a server-side address — `scope["server"]`, which uvicorn fills from the
  socket — so a startup-style check could be attempted per request from it, and it is the wrong
  check: the question worth answering is not what the socket was bound to but who is talking to it.
  But the reason usually given for preferring the client address does not survive the specification:
  **both fields are optional in ASGI and either may be `None`**. So the choice is made on what the
  field means, and the optionality is handled explicitly rather than argued away — a request whose
  client address is absent is refused under the default context, because *no opinion* and *loopback*
  are different facts, and reading the first as the second is the fail-open this section exists for.

  FR-026's startup refusal is the **early and legible** form of the same rule, for the case where
  terezy owns the entry point — a message at boot beats a service that starts and then refuses
  everything. It is not the guarantee.

- **FR-026b**: terezy MUST own a process entry point that takes the address, applies FR-026, and then
  calls the server with the address it just checked. Documentation, the compose file and the
  `Dockerfile` MUST start the service through it and never through a bare server command, so the
  supported path is the one that refuses early.

- **FR-027**: The bind context MUST be a closed set of exactly **two** declared values, read from
  one environment variable:

  | Value | Meaning | Bind permitted | Per-request client check |
  |---|---|---|---|
  | *(unset, the default)* — `loopback` | Running on a host, reachable only from that host | loopback addresses only | every request whose client address is not a loopback address is refused |
  | `container-published-to-loopback` | Running inside a container whose ports the host publishes to loopback | the container interface | relaxed, because inside a container every client address is the bridge and no finer statement is available |

  There MUST be **no third value**, and in particular no value meaning "bind anywhere". A test MUST
  assert the set has exactly two members by reading the closed type, not by listing them in prose.

  A value that is **neither** — a typo such as `containr` — MUST **refuse at startup naming both
  declared values**, never fall back to the default. Parsing into the closed type and defaulting on
  failure is the obvious implementation and it is a silent default for a malformed field, which
  Principle IV forbids in the ordinary case and which is worse here: the person who typed it
  believed they had asked for something.

- **FR-027a**: The second value is a **claim about where the process is running, and the guard MUST
  verify it** before honouring it. Where the environment names
  `container-published-to-loopback` and the process is **not** inside a container, startup MUST
  refuse, naming the marker it looked for and did not find.

  Without this requirement the variable is exactly the off-switch FR-030 forbids, and the reasoning
  that says otherwise is wrong in a way worth writing down. Inside a container the bind address
  *is* `0.0.0.0` — a container has no other interface to offer — so the second value has to permit
  `0.0.0.0`. Setting one environment variable on a laptop and binding `0.0.0.0` would then publish
  one person's finances to the LAN, with no container and no compose file anywhere near it. "The
  compose file is what makes it reachable" is true of the container case and false of that one.

  Verification is what closes it: the value stops being a permission and becomes a statement the
  process can be caught lying about.

- **FR-027b**: What FR-027a's verification is worth MUST be stated honestly. Container membership is
  observable from inside only through markers the runtime leaves — a `/.dockerenv`, a container
  runtime named in the init process's cgroup — and a person who wants to defeat the check can create
  one. **What the check buys is that the wrong thing is no longer the easy thing**: publishing to a
  network stops being one environment variable and becomes forging a container marker, which nobody
  does by accident and nobody does while believing it is supported. That is a different security
  property from impossibility, and it MUST NOT be written as impossibility anywhere in the
  implementation's messages or docs.

- **FR-028**: The compose file MUST make the claim true where the claim is made. A test MUST parse
  the shipped `docker-compose.yml` and assert that **every** published port on **every** service
  matches `127.0.0.1:<port>:<port>` — never `0.0.0.0`, never a bare `<port>:<port>`, which Docker
  publishes on every interface. An edit that publishes the API to the network turns the build red in
  the same commit that makes it reachable.

- **FR-029**: The reach of the whole arrangement MUST be stated rather than overclaimed. Four things
  are guaranteed and one is not:

  | Guaranteed | How |
  |---|---|
  | Under the default context, no request from a non-loopback client is served — **however the process was started** | FR-026a, a refusal per request |
  | Under the default context, terezy's own entry point will not bind off-loopback | FR-026, a refusal on the address |
  | The container context cannot be claimed on a machine carrying no container marker | FR-027a, a refusal naming the marker |
  | The shipped compose file cannot publish off-loopback | FR-028, a gate on the artefact |
  | **Not** guaranteed: `docker run` by hand with its own port mapping, or a forged container marker | Nothing in the process can see a host publication from inside a container |

  **Which row is load-bearing depends on the context, and the shipped deployment is not the default
  one.** Run on a host under the default context, row 1 carries the guarantee and rows 2 to 4 are
  convenience around it: a bare `uvicorn … --host 0.0.0.0` bypasses FR-026's **startup** refusal and
  does not bypass FR-026a's **per-request** one, so the socket opens and every LAN client is refused.

  Under `container-published-to-loopback` — which is what `docker compose up` runs, per FR-032 and
  SC-015 — FR-027's own table says the per-request check is **relaxed**, because every client address
  inside a container is the bridge. So on the supported deployment row 1 is switched off and the
  guarantee rests on **row 4**, the port-publication gate, with row 3 keeping the context from being
  claimed anywhere else. Saying otherwise would leave a reader believing the strongest row protects
  the one path it does not cover, which is the misreading FR-027b exists to prevent. What this feature guarantees is that the shipped way to run the service cannot listen
  off-loopback, that changing that is not a quiet change, and that no single variable lifts it.

- **FR-030**: There MUST be no command-line flag, configuration key or environment variable, other
  than FR-027's two-valued context, that **widens the set of addresses the service may bind to**. A
  scan MUST assert this over the module rather than the reviewer asserting it in prose.

  *Widens*, not *changes*: FR-026b requires the entry point to take an address, so a rule about
  anything that changes the bind address would be red against this feature's own entry point on the
  first run — the failure FR-007a heads off for the route-group check, arriving here. Taking an
  address and refusing most of them is the mechanism; what is forbidden is a second input that lets
  one of the refused ones through.

- **FR-031**: The interactive documentation UI MUST be **disabled** — both the Swagger UI route and
  the ReDoc route. Principle VII forbids CDN calls outright and the framework's default pages reach
  three external hosts across five asset URLs, measured above. The OpenAPI *document* is still served: it is JSON
  read from the committed artefact (FR-038a) and reaches no network.

  The assertion MUST be scoped to **what the browser would fetch**: the markup, scripts,
  stylesheets and other assets this application serves must reference no external host, and the two
  documentation routes must serve nothing at all. It MUST NOT be an assertion over every response
  body, because FR-018 requires every citation to be serialised and a citation *is* an external URL
  — `https://bank.gov.ua/…` on the rate series, `https://zakon.rada.gov.ua/…` on the tax packs. A
  scan that read those as CDN calls would be red on the shipped data and would be measuring the
  opposite of what it claims: a citation the client never fetches is the provenance mark working,
  and a script tag is the defect.

### What a generic client needs, and this feature owes

These four are obligations feature 021 rests on (its OB-2, OB-3 and OB-6, and its FR-049). They
are requirements here rather than assumptions there, because a client that has to know each
category's schema turns a generic screen into a per-category branch — Principle II broken in a new
layer.

- **FR-052**: A record read MUST be **self-describing**: beside the record, the response MUST carry
  the ordered **field descriptors** of the record it returned — each field's name and its kind, and
  for a field whose kind names another record or an enum, which one. Derived from the same shape the
  body is encoded from, never written out per category.

  Names and kinds, and deliberately **no label**: a human label is presentation, and a serialiser
  that invented one would be adding a fact the record does not carry (FR-015). Title-casing a field
  name is the client's to do and is reversible; a label chosen here would be a second vocabulary
  nobody could correct.

- **FR-053**: Every record read MUST state **which file declared it**, as a path relative to the
  data root. Where the resolver exposes no file for a category, the response MUST say so as a
  **typed absence carrying the reason**, never as a null or a missing key — and a test MUST pin the
  set of categories in that state, so it is a measured gap rather than a silent one. Measured
  2026-09-03 the set has one member, `tax-timing`, whose entry point returns rules by jurisdiction
  and no file map.

- **FR-054**: Every category MUST state whether its directory is **sourced or exempt from the
  citation requirement**, and for an exempt one **the recorded reason**. `scripts/check_provenance.py`
  holds both lists by name and fail-closed, and it is the single definition: a test MUST assert the
  API's verdict for every category equals that script's, so the reason is served rather than
  restated. An exemption served as an absent citation is indistinguishable from a citation nobody
  wrote, which is the distinction the whole provenance mechanism exists to keep.

- **FR-055**: Where a built client is present at `web/dist`, the API MUST serve it from its own
  origin with an SPA fallback, and where that directory is **absent the mount MUST be inert** —
  no route, no error, and nothing the Python suite has to build. 021 FR-049 makes production one
  container serving both, which is what removes the cross-origin question in FR-032a; the inert
  case is what keeps `uv run pytest` free of a Node build (FR-035).

  The served bytes stay inside FR-031's scan: a built asset referencing an external host is the
  defect that scan exists to catch, and 021 FR-036 checks the same property over its own build.

### Packaging

- **FR-032**: A `docker-compose.yml` at the repository root MUST declare an `api` service running
  the application under uvicorn.

  **This is the whole contract with feature 021**, stated once and referred to from everywhere else
  in this document: the service name `api`; the port `8000`, published at `127.0.0.1:8000:8000`;
  `src/terezy/api/http/openapi.json` as the file its TypeScript types are generated from; and the
  origin arrangement FR-032a settles. Everything the web client shows comes through those. This
  specification declares no web service; 021 does, and adds its own service to the same file.

- **FR-032a**: The API MUST declare **no cross-origin allowance at all**, and a test MUST assert
  the absence: no CORS middleware is installed and no `access-control-allow-origin` header is ever
  emitted.

  **The premise the first draft argued from was false.** It said the alternative — the API serving
  the built client from its own origin — *"would break 021's development loop, where the client runs
  on its own port against this service"*. It does not: 021 FR-033 proxies `/api` through its dev
  server, so the browser sees one origin in development, and 021 FR-049 makes production **one
  container** whose API serves `web/dist`. There is no supported arrangement in which the two are
  different origins, so an allowance would be a widening declared for a case that does not arise —
  and the one thing it would then do is admit a page the owner merely visited, on a service holding
  his whole position.

  What the draft's last paragraph established stands and is the reason the allowance would not have
  been worth much anyway: **a CORS allowance withholds, it does not refuse.** Starlette's
  `CORSMiddleware` serves a simple `GET` carrying a disallowed `Origin` in full and merely omits the
  header, leaving the *browser* to block the read. Refusal is FR-032b's job, on the `Host` header,
  which is also the only one of the two that survives DNS rebinding.

- **FR-032b**: The service MUST also refuse any request whose **`Host` header** is not one it
  declares, from a closed list of loopback hosts.

  An origin allowance alone does not deliver FR-032a's stated property, and the gap has a name. Under
  **DNS rebinding** a page on `evil.com` re-points its own hostname at `127.0.0.1` and fetches
  `http://evil.com:8000/registry`; the browser considers that **same-origin** and therefore sends no
  `Origin` header at all, so an origin check never fires and the whole registry is readable by a
  site the owner merely visited. The request's `Host` is `evil.com`, which is the one place the
  attack is visible from inside the process — so the `Host` allowlist is the check that closes it,
  and it is the reason this is a requirement rather than a note.

- **FR-033**: The `api` service MUST mount `data/` **read-only**. It is the mechanical form of this
  feature's central non-goal: a read-only API whose data directory is writable is read-only by
  intention, and read-only by mount is read-only by construction.

- **FR-034**: The `api` service's image MUST build from an **official Python base image** and pull
  no other image. A test MUST assert that the `api` service's `image:` and every base image in its
  build context is either the official Python image or built locally from this repository.

  Scoped to the `api` service rather than to the whole compose file, because FR-032 says feature 021
  adds its own service to that file and a web client's base image is a Node image — a file-wide
  assertion would go red on the commit that fulfils this feature's own contract. The general rule
  that a service names an official base image belongs with whoever declares the service; this one
  declares `api`.

  The build reaches the Python package index, which is a build-time fetch of pinned, locked
  dependencies and not a runtime call. Runtime is what Principle VII is about, and at runtime this
  service makes no outbound connection at all (FR-036).

- **FR-035**: `docker-compose.yml`, the `Dockerfile` and the compose-file tests MUST be added
  without changing how the test suite is run. The suite continues to run against the working tree
  with `uv run pytest`; nothing in the gates may require a container to be built.

### Dependencies, enumerated

- **FR-036**: A **new runtime dependency MUST NOT arrive unreviewed**. The standing requirement is a
  test that reads the lock file, takes the runtime closure of the `api` extra, and compares it with
  a list recorded beside the test: a package that appears without a line fails the build. The list
  is where the enumeration lives, because a list in prose is one nothing checks — the constitution's
  rule about enumerating things declared elsewhere applied to a dependency tree.

  The table below is the review as it was performed, dated, not a second copy of that list.
  Installed and measured on 2026-09-03:

  The closure MUST be taken with **every environment marker included and no marker evaluated**, and
  with **extras traversed only where this project asks for one**, so that the reviewed list is a
  property of the lock file rather than of the machine reading it. A marker-evaluating gate would be
  green on macOS and red on Windows for the same commit, which is the one thing a gate must not be.
  So it is **20 packages**, walked from `fastapi` and `uvicorn[standard]`, the last of which is
  conditional and is reviewed anyway:

  | Package | Version | Network behaviour |
  |---|---|---|
  | `fastapi` | 0.141.1 | None of its own. Serves what the application returns. Its default docs UI fetches from three external hosts and is disabled by FR-031. |
  | `starlette` | 1.6.0 | None. The ASGI toolkit under FastAPI. |
  | `uvicorn` | 0.52.4 | Listens on the address it is given; makes no outbound connection. |
  | `uvloop` | 0.22.1 | None. An event-loop implementation. |
  | `httptools` | 0.8.0 | None. An HTTP parser. |
  | `websockets` | 17.0.1 | None unless a WebSocket route exists; this feature declares none. |
  | `watchfiles` | 1.2.0 | None. A filesystem watcher used only by `--reload`, which the shipped configuration does not use. |
  | `python-dotenv` | 1.2.3 | None. Reads a local file. |
  | `pyyaml` | 6.0.3 | None. Also what the compose-file tests parse with. |
  | `pydantic` | 2.13.4 | None. Already a base dependency, used at the load boundary. |
  | `pydantic-core` | 2.46.4 | None. Pydantic's compiled validation core. |
  | `annotated-doc` | 0.0.5 | None. A `typing` helper `fastapi` 0.141 requires directly. |
  | `annotated-types` | 0.8.0 | None. Pydantic's constraint vocabulary. |
  | `typing-inspection` | 0.4.4 | None. A `typing` helper `fastapi` 0.141 requires directly. |
  | `typing-extensions` | 4.16.0 | None. |
  | `anyio` | 4.14.2 | None of its own. The async runtime abstraction under Starlette. |
  | `idna` | 3.19 | None. Hostname encoding, reached through `anyio`. |
  | `click` | 8.4.2 | None. Uvicorn's command line. |
  | `h11` | 0.16.0 | None. An HTTP/1.1 state machine. |
  | `colorama` | 0.4.6 | None. Terminal colour, reached through `click` on Windows only. |

  `certifi`, `sniffio`, `tzdata` and `exceptiongroup` are **not** in this closure and are not
  listed. `anyio` 4.14.2 no longer requires `sniffio`; `certifi` reaches the tree only through the
  dev-only `httpx`; `tzdata` sits behind `pydantic`'s own `timezone` extra, which nothing here asks
  for, and is in `uv.lock` because **pandas**, a base dependency, pulls it; and `exceptiongroup`
  appears in `uv.lock` **not at all** — `anyio`'s locked dependencies are `idna` and
  `typing-extensions` only, the backport having been resolved away under this project's
  `requires-python >= 3.12`.

  Naming a package that is not there is the same defect as omitting one that is, and all four were
  plausible entries measured out rather than reasoned out. Each was in a draft of this table, and
  each came out because the lock file was read rather than the dependency tree remembered.

  **No package in this table phones home.** That is a statement about what they were reviewed to do;
  what asserts it is a test that serves a request and opens no socket, which the suite's existing
  network guard already makes cheap.

- **FR-037**: `fastapi`, `pydantic` **and** `starlette` MUST be **pinned to exact versions** in
  `pyproject.toml`, replacing the present `>=0.115` and `>=2.9` and adding the third. The generated
  OpenAPI document is a gated artefact (FR-038) and its content is a function of all three:
  Starlette owns the routes, FastAPI assembles the document, and Pydantic emits every JSON Schema
  inside it. Pinning only FastAPI would leave the larger half of the bytes floating; leaving
  Starlette out would leave the paths floating, and it is the widest range of the three —
  `fastapi` 0.141.1 declares `starlette>=0.46.0` with **no upper bound**, against an installed
  1.6.0, so a resolver may legitimately cross a major version. Each unpinned contributor is the same
  false alarm arriving from a different direction. The pins make an upgrade a deliberate commit
  whose diff is the schema change it caused.

### The OpenAPI document

- **FR-038**: The OpenAPI document MUST be checked in at **`src/terezy/api/http/openapi.json`**, and
  regenerating it MUST produce a byte-identical file or the build fails.

  Inside the package rather than at the repository root or under `docs/`, for two reasons. It is an
  artefact *of* that module — it changes when and only when that module's response types change, and
  a file that moves with a module belongs beside it. And it ships in the wheel, so a consumer
  resolves it by package path rather than by a relative path into a source checkout, which is what
  makes feature 021's generation step work the same way from a build directory as from the repo.

  It is deliberately **not** under `tests/golden/`. The constitution says a golden file is *evidence*
  of what a run produced; this is a *published contract* that a second codebase is generated from.
  Filing it as evidence would invite the reading Principle V spends a paragraph rejecting — that the
  artefact constrains the input — in the one place where it is nearly true.

- **FR-038a**: The `/openapi.json` route MUST serve **the committed file, verbatim**, rather than
  re-serialising the generated document. Otherwise the endpoint and the file are the same *document*
  and different *bytes*: FR-039 gives the file a fixed indentation and a trailing newline, and the
  framework's JSON response writes compact separators and no trailing newline. A client told by
  FR-032 that the file is its source of truth would fetch the endpoint, get something that does not
  match, and have no requirement to read that explains why. Serving the gated artefact makes the two
  the same thing by construction, which is also the only version of this that stays true.

- **FR-039**: The document MUST be **byte-reproducible**: a fixed key order, a fixed indentation, a
  trailing newline, and no value read from the clock, the environment or the filesystem. A document
  whose bytes depend on where it was generated cannot be gated.

- **FR-040**: The generation MUST be available as a script **under `scripts/`**, beside
  `check_provenance.py` and `fetch_cpi.py`, so that the response to a red gate is *regenerate and read
  the diff*, not *edit JSON by hand*. The location is stated rather than left open because it is the
  one file this feature adds outside `src/terezy/api/http/`, and SC-023a's claim about where the
  feature's modules live has to know about it.

- **FR-041**: The document's `info.version` MUST be a **literal constant in the HTTP module**, named
  as the version of *this contract*, and MUST be bumped in the same commit as any change to the
  committed document that a generated client would have to react to.

  Deliberately **not** the package version, which was the obvious choice and breaks FR-039. A package
  version is read at runtime from installed distribution metadata — the filesystem — and an editable
  install of a dirty tree can report a different string from a built wheel of the same source. The
  byte gate would then be red on one machine and green on another with no source change, which is
  precisely the document-whose-bytes-depend-on-where-it-was-generated FR-039 exists to rule out. It
  is also the wrong number on its own terms: the package version moves when the tax engine changes
  and a generated TypeScript client does not care, while this one moves when the wire shape does.

### The answer endpoint

- **FR-042**: The answer MUST be in this feature, read-only, over **declared questions only**:
  a request names a declared question id and an `as_of`, and receives what
  `terezy.api.answer.answer_question` already returns — the answer or its refusal, and the run
  manifest.

  In this feature rather than a follow-up because the schema is what makes it cheap and the schema is
  what is being written. `AnsweredQuestion` is a stable typed record with two fields; deferring it
  would mean writing the discriminated-union machinery (FR-011 to FR-014) with `Answer`'s eight-member
  `Refused` union — the union that motivates the requirement — outside the scope that tests it.

- **FR-043**: A question built from request parameters — the HTTP equivalent of the CLI's `--set` —
  MUST NOT be in this feature. It is recorded as a `[[future]]` entry. The reason is 015 FR-004's:
  in an artefact under review an unknown stream is a typo, and `answer_declared`'s docstring records
  that two of the four cross-file checks are *unreachable* through the record-taking entry point. An
  ad-hoc HTTP question would need those two refusals to be reachable, which is a change to the verb's
  contract and not a serialisation concern.

- **FR-044**: The run manifest MUST be in the answer response. *A result without a manifest is not a
  result* (Principle III), and `terezy.api.answer`'s own docstring records that no answer obtainable
  from `api/` lacks one. An HTTP response that dropped it would be the first.

### Series

- **FR-045**: The two dated series MUST have windowed reads: the official-rate series
  (`OfficialRateObservation`, keyed by `on_date`) and the CPI series (`CpiObservation`, keyed by a
  `YYYY-MM` period). A window MUST be a request parameter; where one is given it MUST be
  **two-ended**; and it MUST be **optional**, an omitted window returning the series' whole declared
  coverage.

- **FR-045a**: Each series' **declared coverage window MUST be reported by the list read** of its
  category, so a client never has to guess one. Without both halves of FR-045 and this, the pair of
  requirements is a trap: a mandatory window plus FR-046's refusal means a client with no coverage to
  start from guesses, is refused, and has nowhere to look up the answer. The shipped CPI series
  carries 411 monthly observations and the rate series a window that grows with every fetch; neither
  is something a caller can be expected to know.

- **FR-046**: A **given** window reaching outside a series' declared coverage MUST **refuse by name**, naming
  the series and the window it does cover, and MUST NOT return a truncated result silently. This is
  011 FR-012's rule at the read surface: 018's spec records that of the four ways to manage an
  uncovered date — interpolate, extrapolate, carry forward, snap — every one *"produces a number
  indistinguishable from a correct one"*, and quietly returning fewer rows than were asked for is a
  fifth.

  **Silently is the operative word, and 021 depends on it.** A response carrying the observations
  that *are* covered **beside** a typed refusal naming the part that is not is the required shape,
  not a violation of this requirement: the refusal is what makes the body non-silent, and refusing
  the whole window would force the client to trim the window itself, which is a computation 021
  FR-001 forbids it (021 OB-7). What is forbidden is a short body with nothing saying it is short.

- **FR-047**: Every observation returned MUST carry its own provenance, not the series'. Both record
  types already hold one per observation; collapsing them to a series-level mark would lose which
  date was verified, and 018 FR-006 establishes that per-row is the only reading under which
  `verified_on` on these series can be honestly filled at all.

- **FR-048**: `data/observations/` MUST NOT be served. FR-006's exemption table states the reason;
  this requirement exists so that the two files nobody loads — `inzhur.toml` at 91 KB and
  `nbu_depository.toml` at 1.37 MB, measured 2026-09-03 — do not arrive as an endpoint because they
  looked like series.

### Staleness

- **FR-049**: Where a response carries a staleness verdict the engine computed, it MUST be
  serialised. The HTTP layer MUST NOT compute one of its own, and MUST NOT age a value the engine
  did not age. `SourceRef.kind` is `""` for a source naming no threshold, and
  `staleness_of_sources` deliberately neither ages nor lists it — *"nobody could check this" stays
  distinguishable from "checked and current"* — and a serialiser that filled that gap in would erase
  the distinction the field exists to keep.

### Tests

- **FR-050**: Every HTTP test MUST use the **in-process test client**. The suite's guard patches
  `socket.socket.connect`, `connect_ex` and `socket.create_connection`
  (`tests/conftest.py`), and an in-process ASGI client opens none of them. No test may start a real
  server, and no test may be marked `xfail` or skipped to accommodate one.

- **FR-051**: `docs/REQUIRED_TESTS.md` rows MUST be flipped only for what this feature closes. What
  it can close and what it cannot is stated under "Required tests this feature relates to" below,
  and no row is claimed on the strength of a surface existing.

  **F2 MUST NOT be flipped.** The owner deferred the display switch, so this feature has no switch
  to check the row against, and the row's own note records that its tax half was established early
  *"so the row cannot be closed later by a feature that never checked it"*. Flipping it here would be
  that exact failure, performed by the feature the note was written for.

---

## The endpoints

The **set** is decided by FR-005 to FR-007 and asserted mechanically, not by this table, and so is
each row's shape (FR-008). Counts are files under `data/`, measured 2026-09-03. A **singleton**
category has no `/{id}` route: seven of the twenty-five, and the reason is in FR-008.

| Category | Shape | Path | Declared in | Resolver entry point | Files today |
|---|---|---|---|---|---|
| instruments | keyed | `/instruments` | `instruments/` | `from_data_root` | 33 |
| groups | keyed | `/groups` | `groups.toml` | `from_data_root` | 1 |
| tax classes | keyed | `/tax-classes` | `tax/` | `from_data_root` | 2 |
| observation kinds | keyed | `/observation-kinds` | `observation_kinds.toml` | `ramp_from_data_root` | 1 |
| venues | keyed | `/venues` | `venues.toml` | `ramp_from_data_root` | 1 |
| channels | keyed | `/channels` | `channels/` | `ramp_from_data_root` | 1 |
| routes | keyed | `/routes` | `routes/` | `ramp_from_data_root` | 10 |
| streams | keyed | `/streams` | `streams/` | `ramp_from_data_root` | 1 |
| scenarios | keyed | `/scenarios` | `scenarios/` | `ramp_from_data_root` | 1 |
| spendable | singleton | `/spendable` | `spendable/` | `coverage_from_data_root` | 1 |
| composition | singleton | `/composition` | `composition/` | `composition_from_data_root` | 1 |
| candidate ceiling | singleton | `/candidate-ceiling` | `candidates/` | `candidates_from_data_root` | 1 |
| access | keyed | `/access` | `access/` | `tuple_from_data_root` | 1 |
| seeds | singleton | `/seeds` | `seeds/` | `seeds_and_goals_from_data_root` | 1 |
| goals | keyed | `/goals` | `goals/` | `seeds_and_goals_from_data_root` | 1 |
| CPI series | keyed | `/cpi` · `/cpi/{id}/observations` | `cpi/` | `inflation_from_data_root` | 1 |
| inflation assumption | singleton | `/inflation-assumption` | `scenarios/inflation/` | `inflation_from_data_root` | 1 |
| official rates | keyed | `/official-rates` · `/official-rates/{id}/observations` | `official_rates/` | `official_rates_from_data_root` | 1 |
| tax schemes | keyed | `/tax-schemes` | `tax/schemes/` | `schemes_from_data_root` | 2 |
| crediting destinations | keyed | `/crediting-destinations` | `tax/destinations/` | `schemes_from_data_root` | 1 |
| tax timing | keyed | `/tax-timing` | `tax/timing/` | `tax_rules_from_data_root` | 2 |
| tax positions | singleton | `/tax-positions` | `scenarios/tax/` | `tax_positions_from_data_root` | 1 |
| early-exit belief | singleton | `/early-exit-belief` | `scenarios/early_exit/` | `tuple_from_data_root` | 1 |
| questions | keyed | `/questions` | `questions/` | `answer_from_data_root` | 1 |
| calendars | keyed | `/calendars` | `calendars/` | `working_day_calendars_from_data_root` | 1 |

Beside the categories:

| Endpoint | Path | What it returns |
|---|---|---|
| registry summary | `/registry` | FR-009: per-category counts, file digests, merged provenance, unverified counts |
| the answer | `/questions/{id}/answer` | FR-042: `Answer` or `Refused`, and the run manifest |
| the OpenAPI document | `/openapi.json` | FR-038a: the committed file, served verbatim |

`scenarios/` reaches four categories because four resolver constants read it — `SCENARIOS_DIR`,
`INFLATION_ASSUMPTION_DIR`, `TAX_POSITIONS_DIR`, `EARLY_EXIT_DIR` — for the reason `data/README.md`
records: `scenarios/*.toml` is globbed as scenario documents and `glob` does not recurse. Four
categories out of one directory is exactly the case FR-007a's flat paths exist for, and it is why
the segments are named for what a category *holds* rather than for where its file sits.

---

## What only the owner decided

All three are **answered** — owner, 2026-09-03, `specs/decisions/2026-09-03-clarify-020.toml`.
The questions and their options stay as they were asked; each closes with what was chosen, so a
reader can see the alternative that was declined rather than only the rule that survived.

### Answered 1 — Which rate may a display conversion use? → **none: the switch is deferred**

There is no display-currency machinery in this repository today, and the reason is not neglect.
`money.convert` is the only function that produces an amount in another currency and it demands the
rate's provenance in its signature. There are exactly two kinds of rate declared, and the
constitution reserves both:

- an **official rate** is the tax role — *"a legal reference you never transact at"* — and two
  `.importlinter` contracts plus `tests/contract/test_the_rate_you_are_taxed_at.py` exist to stop it
  being used for anything else;
- a **channel's `reference_rate`** is the transaction role. All three declared in
  `data/channels/uah_usd.toml` carry `reference_rate = 42.0` and a source reading *SYNTHETIC
  FIXTURE — invented reference rate*, with an empty `verified_on`.

`docs/REQUIRED_TESTS.md` row F3 already records a position on this: the display switch *"is a
channel-rate question about presentation"*. This question is whether to act on it.

| Option | What it means | The concrete consequence |
|---|---|---|
| **A** *(recommended)* | The request names a **declared channel**, and its `reference_rate` is the display rate. | Display works today. Every converted figure carries the channel's id and its provenance — and because the shipped channels are invented fixtures, **every converted figure would render marked unverified**, which is true and will look alarming until a real channel rate is declared. |
| **B** | No conversion at all: `display` names no rate this feature can honour, and the block refuses by name wherever a conversion would be needed (never where the amount is already in the requested currency — FR-024a). | Nothing is ever wrong, and nothing is ever converted — so **`REQUIRED_TESTS` F2 stays open**, by FR-051: a byte-identity test over a switch that converts nothing is green for the wrong reason, and F2's own note exists to stop exactly that flip. F3 and F4 stay where they are too. |
| **C** | Declare a **fourth** rate role for presentation, in its own data directory with its own citations. | The cleanest long-run answer and the largest change: a new declaration kind, a new provenance surface, and a new argument about what a presentation rate even is. Not a serialisation feature. |

**Recommendation was A. The owner chose none of the three and deferred the switch**, which is
wider than B: B kept the parameter and a block that refuses, and the deferral removes both. FR-021 to
FR-025, SC-010, SC-010a, SC-011 and SC-011a are marked deferred at their own sites, `REQUIRED_TESTS`
F2 stays open by FR-051, and `display-currency-switch` in `specs/features.toml` carries the three
options above forward unchanged.

### Answered 2 — Does `as_of` get a default? → **no**

015 FR-006 put `as_of` on the verb rather than in the question file, because *"a question whose
horizons or amounts moved with the calendar would be a different question each day while its digest
stayed the same"*. The same argument reaches an HTTP request, but not identically: an HTTP request
is not an artefact under review, and a person opening a browser has no obvious place to type a date.

| Option | What it means | The concrete consequence |
|---|---|---|
| **A** *(recommended)* | `as_of` is **required**. A request without it refuses naming the parameter. | Two requests a week apart with the same URL give the same answer forever. The web client must supply a date, which means it has to decide what date it means and say so on screen. No clock is read anywhere in this feature. |
| **B** | `as_of` defaults to the server's current date when omitted, and the date used is echoed in the response. | The browser case is one click. The cost is that the HTTP layer reads the clock, so an identical URL is a different question tomorrow — and the staleness verdict, which is the only thing `as_of` decides, would then change under a reader who did not ask it to. |

**Chosen: A.** `as_of` is required, there is no default, and no code path in this feature reads the
clock. B's conditions — one confined clock read, echoed into the response and the manifest — are the
terms it would have to be built under if it is ever revisited, and are recorded here for that.

### Answered 3 — The nine refusals that carry no reason → **optional in the schema, core untouched**

The decision of 2026-09-03 says each union member carries "its tag and its `reason`". Measured on
2026-09-03 by flattening the refusal families this repository names — `Refused`, `SectionOutcome`'s
refusal arms, `SurveyRefused`, `TupleRefused`, `SettlementRefused`, `DomainFailure`, `LotRefusal`
and `SolveOutcome`'s refusal arms — and reading `dataclasses.fields`: **51 refusal records, 42 carry
`reason: str`, 9 do not.**

Eight of the nine are the whole of `Answer`'s own `Refused` union: `NoHorizonDeclared`,
`NoSubjectDeclared`, `AmountForAnUndeclaredStream`, `StreamWithNoAmount`,
`BenchmarkOutsideTheSubjects`, `BenchmarkYieldsSeveralCandidates`, `TwoIdenticalHorizons`,
`PlanForNothing`. **The ninth is `BenchmarkYieldsNoCandidate`**, a refusal arm of `SectionOutcome`
carrying `instrument_id` and `enumerated`, reached through `Answer.sections`. It is named separately
because it is the one a reader checking this claim will miss: it belongs to no union whose name ends
in `Refused`, so an audit that enumerates the refusal unions finds eight and stops. Only a walk of
the response type finds nine — which is why FR-013 requires the walk and forbids the hand list, and
why clarification 3's own test is specified as a walk rather than as a count.

Everywhere else it is universal: all seventeen of `TupleRefused`, all seven of `SurveyRefused`, all
seven refusal arms of `SolveOutcome`, all five of `DomainFailure`, all three of `SettlementRefused`,
all three of `LotRefusal`.

| Option | What it means | The concrete consequence |
|---|---|---|
| **A** *(recommended)* | `reason` is **optional in the schema**, and a test **discovers** the reason-less records by walking the response types and compares the set against a checked-in list of nine — so a tenth is a deliberate edit rather than a silent widening. A `[[future]]` entry records closing the gap in the core. | Ships now. A TypeScript client's `reason` is `string \| undefined`, so it must narrow on the tag — which is what FR-011 to FR-014 make it able to do, and arguably the better client anyway. |
| **B** | Add `reason` to the nine members first, as a small core change inside this feature. | The schema is uniform and every refusal explains itself in one field. It is a core edit in a feature whose whole point is that the core is untouched, it needs nine sentences nobody has written, and it moves what the CLI prints. |
| **C** | The HTTP layer synthesises a reason for the nine. | **Rejected, not offered as a live option.** It would make the API a second place the tool decides what happened, against FR-015 and against the CLI's own rule that it adds no fact to the record. Recorded here so the option is visibly closed rather than never considered. |

**Chosen: A**, with the `[[future]]` entry. The schema marks `reason` optional; the test **discovers**
the reason-less records by walking the response types and compares the discovered set against a list
checked in beside it, so a tenth is a deliberate edit. B stays the better long-run answer and belongs
to a feature about the answer's vocabulary rather than about serialising it.

---

## Key entities

- **Category** — one declared kind of data, a resolver entry point, and the response type its
  records serialise to. The unit FR-005's mapping is keyed by.
- **Tag** — `<module leaf>.<ClassName>`, derived, never stored on a core record, injective over all
  314 core records as measured. The field a client switches on.
- **Bind context** — a two-valued statement of where the process is running (FR-027). Not a
  permission level and not extensible.
- **The OpenAPI document** — a published contract, checked in, byte-gated, and deliberately not a
  golden file (FR-038).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every **keyed** category in FR-005's mapping returns exactly the ids its resolver entry
  point resolves over the shipped `data/`, and a request for an undeclared id returns a typed refusal
  naming the declared ids. Every **singleton** category returns the one document its entry point
  resolves and offers no id-shaped route at all. Checked over every category, not a sample, with each
  category's shape read off the mapping rather than assumed. (FR-005, FR-008)
- **SC-002**: Adding a directory under `data/` that no category covers and no exemption names fails
  the suite. Demonstrated by adding one in a scratch data root. (FR-006)
- **SC-002a**: Every category read names the scenario it resolved under, including when that is none,
  and the six categories whose entry points take a `scenario_id` return different documents under a
  declared scenario than under none — demonstrated on `/spendable`, which
  `tests/contract/test_coverage_scenario_scoping.py` already pins at the resolver. No category
  hardcodes the value. (FR-007b)
- **SC-003**: Removing a category from the mapping while its resolver constant remains fails the
  suite, and removing the constant while the category remains fails it too — two separate tests,
  each red on its own. (FR-006, FR-007)
- **SC-003a**: Every category path is one segment, and every route group — the fixed endpoints
  included — owns a distinct first segment. The shipped route table passes as it stands, with
  `/questions/{id}/answer` inside the `questions` group rather than a second owner of it. Adding a
  category whose path nests under an existing one turns the suite red, and so does one named
  `registry`. (FR-007a)
- **SC-003b**: The registry summary reports every category in FR-005's mapping and no other, each with
  its shape; a keyed category reports its id count and a singleton reports **whether its document
  resolved**, so a resolved-but-empty singleton is distinguishable from one the loader found nothing
  for. **Every file the resolver read for a category is listed under that category and under no
  other**, and the union across categories equals the manifest's own input references for the run.
  That association is what can actually be wrong; asserting the digest *values* would compare
  `manifest.input_refs`' output with itself, since FR-009 requires the summary to use it. (FR-009)
- **SC-003c**: A category holding one unverified source reports as unverified, and its merged
  provenance equals the fold of its records' provenances through
  `terezy.core.primitives.provenance.merge` — asserted against that function's output rather than
  against a union computed in the summary, so the monoid stays the single definition. Marking one
  source verified changes the category's verdict and nothing else. (FR-010)
- **SC-004**: 100% of records reachable from a response type carry a tag, and the tags are distinct.
  Asserted over the walk, and demonstrated by introducing a colliding record name and watching the
  build go red. (FR-011, FR-012, FR-014)
- **SC-005**: Every member of every union reachable from a response type appears in the committed
  OpenAPI document as a named member of a `discriminator` mapping. Discovered by walking the types;
  the test contains no list of member names. Adding a member to any union in the core turns it red.
  (FR-013)
- **SC-005a**: The tag override table is **empty** in the landed feature, and the derivation consults
  it before deriving. Adding one entry retags exactly one record and leaves **every other tag in the
  document** byte-identical. Stated without a count: FR-012 and SC-004 scope tags to records reachable
  from a response type, and this feature serves no goal solve, no ledger internals and no settlement
  outcome, so the document carries a strict subset of the 314 and "the other 313" is not a number
  anything could check. (FR-012a)
- **SC-005b**: Every field of every refusal body **other than the tag** corresponds to a field of the
  core record it came from — swept off the dataclasses in both directions, so the serialiser can
  neither drop one nor invent a message, code or severity. The tag is carved out because FR-011
  requires it and requires it *not* to be a field on the core record, so a sweep without the carve-out
  is red on the one addition this spec mandates. (FR-011, FR-015)
- **SC-005c**: An answer and a refusal for the same request arrive in the same body shape, and no
  typed refusal is expressed by a status code with an empty body. A malformed declaration is
  distinguishable from a typed refusal in the body, not only in the status. (FR-016)
- **SC-006**: `OneWayCost` and `RoundTripCost` serialise to bodies that differ, on data where every
  one of their nine fields is equal. This is the Principle VI prohibition at the wire, and it fails
  on `main` today for the trivial reason that neither type is serialised at all. (FR-014)
- **SC-007**: Regenerating the OpenAPI document produces bytes identical to
  `src/terezy/api/http/openapi.json`. Changing one field on one response record turns it red naming
  the path that moved; changing any of the three pinned versions turns it red if the output changed.
  (FR-037, FR-038, FR-039)
- **SC-007a**: The body served at `/openapi.json` is **byte-identical** to
  `src/terezy/api/http/openapi.json`. Asserted directly, because it is the whole of what FR-038a is
  for and SC-007 does not reach it: SC-007 compares a regeneration against the file, and this compares
  the endpoint against the file. Re-serialising the generated document instead of serving the artefact
  turns it red on the separator and the trailing newline. (FR-038a)
- **SC-007b**: The regeneration script exists, and running it over an unmodified tree leaves
  `src/terezy/api/http/openapi.json` byte-identical — so the response to a red gate is to run it and
  read the diff. (FR-040)
- **SC-007c**: `info.version` is a literal in the HTTP module, and no code path behind the document
  reads distribution metadata — asserted by a scan, not by building a wheel, so the criterion stays
  inside a test suite that must run without a build step (FR-035). Changing the package version
  leaves the committed document byte-identical. (FR-041)
- **SC-008**: 100% of money-valued fields in every response type carry provenance, swept off the
  dataclasses rather than sampled, so a field added later is inside the claim. A response type that
  drops the mark fails the suite. (FR-017)
- **SC-008a**: Every serialised source carries `id`, `citation`, `retrieved_on`, `verified_on` and
  `kind`, plus the derived `is_unverified` verdict — and that verdict equals
  `provenance.is_unverified` for the same set on every response in the suite, so a client never has
  to recompute the one-taints-all asymmetry. (FR-018)
- **SC-008b**: No response body is built from `terezy.core.results.canonical`. Asserted as an
  absence over the serialiser's imports, because that encoding excludes provenance by design and
  would satisfy the provenance requirement nowhere. A canonical digest reported as a field is
  permitted and is checked to be a field rather than the body. (FR-020)
- **SC-008c**: Every staleness verdict in a response is the one the engine computed, field for
  field, and no module under `terezy.api.http` calls a staleness function or ages a source. A source
  whose kind is empty stays unassessed rather than being reported current. (FR-049)
- **SC-009**: Two runs of the same request over the same data root produce byte-identical bodies,
  including every set-derived list. Asserted **across processes with differing `PYTHONHASHSEED`**,
  not twice within one, because within one process a `frozenset` iterates stably and the criterion
  would pass while the property fails. (FR-019)
- **SC-010** *(deferred with FR-021 to FR-025)*: The same resource requested under each declared display currency differs **only**
  inside the display block; every other byte is identical, including every ranking position and
  every figure a ranking is computed from. Asserted by comparing the two bodies field by field, not
  by comparing a chosen subset. (FR-022, FR-023)
- **SC-010a** *(deferred with FR-021 to FR-025)*: A body containing both hryvnia and dollar amounts, requested under each declared
  display currency, raises nothing: the amounts already in the requested currency carry no display
  block, the others carry one, and the two absences — *already in it* and *no rate for it* — are
  distinguishable in the body. (FR-024a, FR-025)
- **SC-011** *(deferred with FR-021 to FR-025)*: A display currency with no declared rate returns a named refusal in the display block
  and an intact, unconverted figure beside it. No response contains a converted figure without the
  declared rate, its direction, the applied factor, the rate's source and the merged provenance.
  (FR-024, FR-025)
- **SC-011a** *(deferred with FR-021 to FR-025)*: One hand-computed worked
  example, arithmetic checked in beside the assertion, shows a UAH amount displayed in USD against
  a declared `reference_rate` of 42 UAH per USD — the applied factor is the reciprocal, the response
  carries both numbers, and multiplying the reported figure by the reported declared rate returns
  the original amount within the project tolerance. An inverted implementation fails it. (FR-024)
- **SC-012**: Under the **default** bind context a non-loopback bind address exits non-zero with a
  message naming the release gate, for `0.0.0.0`, `::` and a literal LAN address — 3 of 3, and 0 of
  them start, with `127.0.0.1` and `::1` starting. No case resolves a hostname, so no case performs
  a DNS lookup. (FR-026)
- **SC-012a**: With the container bind context named and no container marker present, startup exits
  non-zero naming the marker it looked for. With a marker present it starts. The single-variable
  path from a laptop to a LAN-published service does not exist. (FR-027a)
- **SC-012b**: Under the **default** bind context, a request whose client address is not a loopback
  address is refused, **and so is one whose client address is absent** — asserted through the
  in-process client by supplying each scope directly, which is also what makes the claim independent
  of how the process was started, since the check never consults the bound address. No test starts a
  server, per FR-050. This is the criterion for the half FR-029 calls load-bearing; SC-012 measures
  only the startup refusal, which that same requirement says is not the guarantee. (FR-026a)
- **SC-013**: The bind-context type has exactly two members, read off the closed type rather than
  counted in prose, and no flag, key or variable in the module **other than that context** widens
  the set of addresses the service may bind to. Both carve-outs are named because a scan missing
  either is red on the first run against this feature's own mechanism: FR-026b's entry point takes
  an address, and FR-027's context variable is the one thing that legitimately widens the set, once
  FR-027a's marker check has verified its claim. An unrecognised context value refuses naming both
  declared values. (FR-026b, FR-027, FR-027a, FR-030)
- **SC-013a**: No message, docstring or document this feature adds says the non-loopback restriction
  is impossible to defeat. Asserted by a scan over the added modules and prose for the claim-shape
  FR-027b forbids, because the honest statement of what a container-marker check buys is the whole
  point of that requirement and prose is exactly where it would be quietly overstated. (FR-027b)
- **SC-014**: Every published port on every service in the shipped `docker-compose.yml` matches
  `127.0.0.1:<port>:<port>`. Editing any one of them to `0.0.0.0:<port>:<port>` or to a bare
  `<port>:<port>` turns the suite red. (FR-028)
- **SC-015**: The shipped compose file mounts `data/` read-only on the `api` service and sets that
  service's bind context; the `api` service names no image but the official Python base and this
  repository's own build. Scoped to `api` rather than to the file, so the criterion survives 021
  adding a `web` service with a Node base image. (FR-027, FR-032, FR-033, FR-034)
- **SC-016**: No markup, script, stylesheet or other asset this application serves references an
  external host, and both documentation routes serve nothing. Asserted by scanning the served
  bytes, not by reading the configuration. Serialised citations are outside the scan by
  construction — they are data in a JSON body, never a fetch. (FR-031)
- **SC-016a**: The service installs no CORS middleware and emits no `access-control-allow-origin`
  header on any response, including one carrying an `Origin` of its own loopback. Asserted as an
  absence, because the arrangement 021 declares is same-origin in both development and production.
  (FR-032a)
- **SC-016b**: The runtime closure of the `api` extra in the lock file equals the reviewed list.
  Adding a dependency turns the suite red until a line describing its network behaviour is written.
  (FR-036)
- **SC-016c**: A request whose `Host` header names a host the service does not declare is refused,
  including one carrying no `Origin` header at all — the DNS-rebinding shape, which the origin check
  alone does not see. (FR-032b)
- **SC-017**: Serving any request makes **no outbound connection**, which is what the suite's
  existing guard asserts — it patches `socket.socket.connect`, `connect_ex` and
  `create_connection` and touches neither socket construction nor `bind`/`listen`. The other half,
  that no test starts a **listening** server, needs its own check and gets one: a scan asserting no
  test module under the HTTP suite constructs a server or calls the server runner. Stated as two
  claims because the existing guard covers one of them and reading it as covering both is how a
  green suite would come to mean less than it looks. (FR-036, FR-050)
- **SC-018**: A declared question answered over HTTP returns the same result the CLI prints for the
  same question and the same `as_of` — compared on the canonical digest, so the claim is about the
  result and not about two renderings agreeing. (FR-042)
- **SC-019**: Every answer response carries a manifest, and no code path returns one without.
  (FR-044)
- **SC-020**: A given window reaching outside a series' declared coverage refuses by name in 100% of
  cases, in a body that also carries whatever part of the window the series does cover; no window
  ever returns a short body with nothing saying it is short. An omitted window
  returns every declared observation, and the coverage a client would need to construct a window is
  on the list read of the same category. (FR-045, FR-045a, FR-046)
- **SC-021**: Every observation in a series response carries its own provenance, and a series in
  which one observation is verified and the rest are not renders exactly that split. (FR-047)
- **SC-022**: `data/observations/` is reachable through no endpoint, asserted as an absence over the
  route table. (FR-048)
- **SC-023**: `uv run lint-imports` passes with the added `frameworks-only-in-the-http-module`
  contract, and adding `import fastapi` to `src/terezy/api/answer.py` turns it red — the case a
  below-only contract would have missed. Adding the same import to `src/terezy/api/__init__.py` or
  to `src/terezy/__init__.py` turns the suite red through the scan. Adding a new module under
  `src/terezy/api/` that neither the contract nor the scan names turns the suite red through the
  completeness check, before anybody imports anything into it. `terezy.core` imports no framework,
  unchanged from today. (FR-002)
- **SC-023a**: Every module this feature adds under `src/terezy/` is under `src/terezy/api/http/`,
  and the diff touches no file under `src/terezy/cli/` or `src/terezy/core/`. The CLI's own tests pass
  unchanged. Scoped to `src/terezy/` because FR-040's generation script lands in `scripts/`, beside
  `check_provenance.py` and `fetch_cpi.py` — this repository's own place for a command a person runs
  and reads the diff of — and a claim over the whole diff would be red on it. (FR-001, FR-004, FR-040)
- **SC-023b**: `uv run pytest` passes with no container built and no Docker daemon running; the
  compose-file and Dockerfile checks parse those files as text. (FR-035)
- **SC-024**: No module under `terezy.api.http` constructs a `Money` or calls a combining function,
  anywhere: the display module the draft carved out is not in this feature. Asserted by a scan.
  (FR-003)
- **SC-025**: `docs/METHODOLOGY.md` gains nothing from this feature, and that is checked rather than
  assumed: this feature introduces no formula. The one it would have introduced was the display
  conversion, which the owner deferred.
- **SC-026**: `docs/REQUIRED_TESTS.md` rows are flipped only for what this feature closes — see
  below. F1, F2, F3 and F4 all stay open: the switch F2 needs is deferred.
  (FR-051)
- **SC-026a**: No endpoint accepts a question built from request parameters; the only answer route
  names a declared question id. Asserted as an absence over the route table, so that FR-043's
  deferral is measured rather than merely stated — an out-of-scope requirement that nothing checks is
  the shape by which scope creeps back in. (FR-043)
- **SC-027**: Every record read carries the ordered field descriptors of the record it returned,
  and the descriptor set equals the record's own fields — swept in both directions, so a descriptor
  can neither omit a field nor name one the body does not carry. No descriptor carries a label.
  (FR-052)
- **SC-028**: Every record read states its declaring file relative to the data root, and the
  categories that cannot are exactly the set the test pins, each carrying a typed absence with its
  reason. (FR-053)
- **SC-029**: Every category's citation verdict equals `scripts/check_provenance.py`'s own lists,
  and every exempt one is served with that script's recorded reason. Moving a directory between the
  two lists turns the suite red. (FR-054)
- **SC-030**: With no `web/dist` present the application registers no static route and every test
  passes; with a directory present, a request for an unknown path under it returns the fallback
  document and a request for a known asset returns it. (FR-055)

---

## Required tests this feature relates to

| Row | What this feature does to it |
|---|---|
| **F1** | *A position flat in USD across a devaluation produces a positive taxable gain in UAH.* **Unmoved, and not approached.** The row's own note records that what is still missing is the *position* — a per-lot basis carried in both currencies with each leg struck at its own date's rate — which is a core capability, tracked as `fx-tax-asymmetry-f1`. A serialisation layer cannot supply it and this feature does not try; naming the row here is what stops a reader inferring that a display switch and an FX tax asymmetry are the same subject. |
| **F2** | *Switching display currency changes no realised amount, no tax figure, and no after-tax UAH ranking.* The row's own note records that the tax half was established **before** the switch existed, deliberately, *"so the row cannot be closed later by a feature that never checked it"*, and that the realised-amount and ranking halves *"need the switch"*. This is the switch. This is the switch — and it is **deferred** (owner, 2026-09-03), so the row **stays open** and FR-051 forbids the flip. |
| **F3** | *Historical series convert at per-date rates, never at today's rate.* **Untouched.** Nothing in this feature converts anything. The observation about a channel's `reference_rate` being a single declared value rather than a per-date series is what the deferred switch would have had to answer, and it travels with the `display-currency-switch` future entry. |
| **F4** | *The real-terms view uses UA CPI in the UAH display and US CPI in the USD display.* Unmoved. The row needs a US CPI series and none is declared. 007's own obligation to it is discharged structurally; this feature adds no display switch and no second deflator. |
| **H2** | Reinforced, not re-derived: a malformed declaration reaches an HTTP caller naming the file and the field, on the existing loader path. The row's own test stays `tests/contract/test_declaration_loading.py`. |
| **H3** | Untouched, and worth naming for the same reason 010 named it: this feature widens what a run *reads* only in the sense of reading it aloud. It adds no input the manifest does not already record. |
| **H4** | Reinforced: a new layer arrives and the boundary contract grows rather than bends. FR-002 adds a contract; it loosens none. |
| **E5** | Pressed on at a new surface and **not closed**. The mark now has to survive serialisation, which is a place it has never had to survive, and FR-017's sweep is over the response types. The row is about every figure in the engine, so one more surface carrying the mark does not close it — the reading `docs/REQUIRED_TESTS.md` already records for it under 005 and under 014. The per-refusal half stays open: measured 2026-09-03, **zero** of the refusal-union members in the core carry provenance, which is the `provenance-on-a-refusal` future entry and is not this feature's to close. |
| **B10** | Exercised again, at the boundary where it is easiest to lose: an empty category is a legitimate empty list, a category whose loader refused is a typed refusal, and the two are different bodies. Still a whole-engine row. |
| **K4** | Reinforced: the first HTTP surface in the repository and it still opens no socket in a test. The row's own tests stay where they are. |

---

## Assumptions

- **One owner, one data root, no authentication.** Principle VII's release gate is untouched and
  every request is the owner's. Nothing in the schema carries a user, and `owner_id` continues to
  travel on the records that already carry it.
- **Read-only means read-only.** No endpoint writes a file, mutates a declaration, triggers a
  fetcher, or warms a cache. Under the shipped compose file `data/` is mounted read-only (FR-033),
  which makes the claim structural there; run from a checkout the directory is writable like any
  other and the claim rests on there being no write path, which is what the absence of write
  endpoints is.
- **The data root is fixed per process.** It is not a request parameter, because a request that
  chose its own data root would be a path a caller controls into the filesystem, and the one thing
  this repository holds is a person's finances.
- **Caching is out of scope.** The declarations are small — measured 2026-09-03, `data/` holds 71
  `.toml` files of which 33 are instruments — and a cache is where a synthetic or stale value hides.
  Principle IV's *caches never hold synthetic or fallback data* is easiest to honour by having none.
- **Latency has no target.** There is one user on one machine. A number here would be a number more
  confident than its input.

---

## Out of scope

- **Writes of any kind.** Editing a declaration, recording an answer, saving a question.
- **Authentication and authorisation.** The release gate is unchanged and this feature does not
  approach it. What it does is keep the gate's condition from being reached by any supported path —
  FR-026 to FR-030, whose reach FR-029 tables exactly and whose limits FR-027b states rather than
  dressing up as impossibility.
- **The web client.** Feature 021. What passes between them is FR-032's contract, the four
  obligations under "What a generic client needs", and nothing else. Serving its *built output* is
  not the same thing as building it: FR-055 is a mount that is inert until 021's image puts a
  directory there.
- **Ad-hoc questions over HTTP.** FR-043, recorded as a future entry.
- **Triggering a fetcher.** The scripts under `scripts/` stay commands a person runs and reads the
  diff of. An HTTP endpoint that fetched would be a network call from a service whose dependency
  list says it makes none.
- **Serving `data/observations/`.** FR-048.
- **The display-currency switch.** Deferred by the owner on 2026-09-03; FR-021 to FR-025 are kept
  above under their own heading as the record, and `display-currency-switch` in `specs/features.toml`
  is what carries them.
- **A second display deflator.** `REQUIRED_TESTS` F4.
