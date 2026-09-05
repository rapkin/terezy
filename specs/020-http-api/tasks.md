# Tasks: The HTTP API — the schema the UI is a client of

**Feature**: `020-http-api` | **Input**: [plan.md](./plan.md), [spec.md](./spec.md),
[research.md](./research.md), [data-model.md](./data-model.md), [contracts/endpoints.md](./contracts/endpoints.md)

**Tests are not optional.** Constitution Principle V is NON-NEGOTIABLE, and a test that fails with
`ImportError` because its module does not exist yet counts. Every phase opens with its checks.

`[P]` marks a task touching files no incomplete task touches. The display switch is **deferred**
(owner, 2026-09-03), so no task here builds a `display` parameter, a display block or a conversion.

---

## Phase 1: Setup — the pins, the boundary, and the empty tree

**Goal**: the framework is pinned, forbidden everywhere it should be, and there is a module for it
to be allowed in.

- [x] T001 Pin `fastapi==0.141.1`, `pydantic==2.13.4` and add `starlette==1.6.0` to the `api` extra in `pyproject.toml`; re-lock with `uv sync --all-extras --dev` (FR-037).
- [x] T002 Add the `frameworks-only-in-the-http-module` contract to `.importlinter`: `fastapi`, `starlette`, `uvicorn` forbidden in `terezy.data`, `terezy.cli`, `terezy.api.answer`, `terezy.api.diagrams`; `pydantic` deliberately not named, with the reason FR-002 gives (FR-002).
- [x] T003 [P] Write `tests/contract/test_the_framework_stays_in_one_module.py`: the scan over `src/terezy/__init__.py` and `src/terezy/api/__init__.py` for a framework import, **plus the completeness check** — every module under `src/terezy/` is named by one of the two contracts, by the scan, or is under `terezy.api.http` (FR-002, SC-023). Fails today on the completeness half only if it is written wrong; the scan half is green and must stay so.
- [x] T004 Create `src/terezy/api/http/__init__.py` with the module docstring stating what this layer may not do, and nothing else yet.

**Checkpoint**: `uv run lint-imports`, `ruff`, `mypy`, `pytest` green. Commit, and flip
`specs/features.toml` 020 to `status = "in-progress"` in this commit.

---

## Phase 2: Foundational — one shape, two folds (blocks every story)

**Goal**: any frozen dataclass reachable from a response type becomes a schema and a body, tagged,
ordered, and with no second copy of its fields anywhere.

- [x] T005 [P] Write `tests/unit/test_shape_algebra.py`: `plan_of` over each arm — scalar, literal, enum, record, optional, union, sequence, set, mapping — and the two loud failures (a callable field, an unhandled annotation) naming the record and the field.
- [x] T006 [P] Write `tests/contract/test_every_record_resolves.py`: every record reachable from every response root resolves its hints; the fallback namespace is exercised by at least the fifteen `TYPE_CHECKING` cases; nothing is skipped silently (research R3).
- [x] T007 Implement `src/terezy/api/http/shapes.py`: the `Shape` tagged union, `plan_of` with memoisation, hint resolution against module globals layered over the fallback namespace.
- [x] T008 [P] Write `tests/contract/test_tags_are_injective.py`: `tag_of` over every reachable record is distinct; the model names are distinct too; the override table is empty and is consulted **before** the derivation; introducing a colliding record in a scratch module turns it red (FR-011, FR-012, FR-012a, SC-004, SC-005a).
- [x] T009 Implement `src/terezy/api/http/tags.py`.
- [x] T010 [P] Write `tests/unit/test_encoding_is_ordered.py`: a `frozenset[str]`, a `frozenset[Enum]`, a `frozenset[SourceRef]` and a mapping with an enum key each encode in the declared total order; a `date` is ISO; a `Money` carries amount, currency and provenance; `is_unverified` is beside the sources (FR-018, FR-019).
- [x] T011 Implement `src/terezy/api/http/models.py` and `src/terezy/api/http/encode.py` — the two folds over `Shape`, sharing nothing but it.
- [x] T012 [P] Write `tests/unit/test_two_records_one_field_set.py`: `OneWayCost` and `RoundTripCost` with all nine fields equal encode to different bodies, and the difference is the tag (FR-014, SC-006).

**Checkpoint**: the algebra is green with no route registered. Commit.

---

## Phase 3: User Story 1 — a declared category in a browser (P1) 🎯 MVP

**Goal**: twenty-five categories, fail-closed against `data/` in both directions, each read naming
the scenario it resolved under.

**Independent test**: start the app over the shipped `data/` and request every category; a keyed one
lists exactly the ids its entry point resolves, a singleton returns its one document and offers no
`/{id}`.

- [x] T013 [P] [US1] Write `tests/contract/test_the_category_set_is_closed.py`: **(i)** every directory under `data/` at any depth and every `.toml` at the root is covered by a category or named in the exemption list with its reason; **(ii)** adding a directory in a scratch data root fails it (FR-006, SC-002).
- [x] T014 [P] [US1] Write `tests/contract/test_every_resolver_constant_is_served.py`: every `*_DIR`/`*_FILE` in `terezy.data.declarations.resolver` is reachable from a category — a separate test from T013 so either direction is red on its own (FR-007, SC-003).
- [x] T015 [P] [US1] Write `tests/contract/test_route_groups_own_a_segment.py`: every category path is one segment and every route group — `/registry` and `/openapi.json` included — owns a distinct first segment; a category named `registry` turns it red (FR-007a, SC-003a).
- [x] T016 [US1] Implement `src/terezy/api/http/categories.py`: the twenty-five rows of `data-model.md`, each with its path, shape, entry point, selector and record type; the `scheme:venue` id codec for `crediting-destinations` beside its row.
- [x] T017 [US1] Implement `src/terezy/api/http/envelopes.py`: the listing, read, singleton and observations envelopes, and the refusal records `CategoryHasNoSuchId`, `NothingDeclared`, `WindowOutsideCoverage`, `DeclarationFailed`, `NotOnLoopback`, `HostNotDeclared`.
- [x] T018 [US1] Implement the app factory in `src/terezy/api/http/__init__.py`: routes registered from the category registry, `docs_url=None`, `redoc_url=None`, `openapi_url=None`, the data root from `TEREZY_DATA_ROOT`, base currency UAH, `as_of` required on every data read.
- [x] T019 [P] [US1] Write `tests/contract/test_category_reads.py`: over **every** category — a keyed listing equals the resolver's own ids, a read of each id returns that record, a singleton returns its document and has no `/{id}` route; the shape is read off the mapping, never assumed (SC-001).
- [x] T020 [P] [US1] Write `tests/unit/test_an_id_nobody_declares.py`: a keyed read of an undeclared id is `CategoryHasNoSuchId` in a 200 body naming the category and the declared ids — **not** a `DeclarationError`, which is the trap FR-008 names, and not a bare status (FR-008, FR-016, SC-005c).
- [x] T021 [P] [US1] Write `tests/unit/test_a_read_names_its_scenario.py`: every read echoes the scenario it resolved under including `null`; `/spendable` differs between a declared scenario and none; no category hardcodes it (FR-007b, SC-002a).
- [x] T022 [P] [US1] Write `tests/contract/test_a_broken_declaration_reaches_the_caller.py`: a malformed file in a scratch data root reaches an HTTP caller as `DeclarationFailed` naming the file and the field, and no category returns partial data (US1 scenario 3, row H2).
- [x] T023 [P] [US1] Write `tests/unit/test_bodies_are_reproducible.py`: two runs of the same request in **separate processes with differing `PYTHONHASHSEED`** produce identical bytes (FR-019, SC-009).

**Checkpoint**: every category serves. Commit.

---

## Phase 4: User Story 2 — a refusal a client can act on (P1)

**Goal**: every record in every body is tagged; every union is discriminated; the marks survive.

**Independent test**: walk the response types, produce each refusal, and assert the tag is present,
distinct and the member the engine returned.

- [x] T024 [P] [US2] Write `tests/contract/test_unions_are_discriminated.py`: every union reachable from a response type appears in the document as `oneOf` with a `discriminator` mapping naming every member, **discovered by the walk with no list in the test**; adding a member to a core union turns it red (FR-013, SC-005).
- [x] T025 [P] [US2] Write `tests/contract/test_a_refusal_adds_no_fact.py`: every field of every refusal body other than the tag corresponds to a field of the core record, swept in both directions, so the serialiser can neither drop one nor invent a message, code or severity (FR-015, SC-005b).
- [x] T026 [P] [US2] Write `tests/contract/test_the_nine_without_a_reason.py`: the reason-less refusal members are **discovered** by walking the response types and equal the list checked in beside the test; a tenth is a deliberate edit (owner answer 3).
- [x] T027 [P] [US2] Write `tests/contract/test_provenance_survives_serialisation.py`: every money-valued field in every response type carries provenance, swept off the dataclasses; every serialised source carries `id`, `citation`, `retrieved_on`, `verified_on`, `kind` and the derived `is_unverified`, which equals `provenance.is_unverified` for the same set (FR-017, FR-018, SC-008, SC-008a).
- [x] T028 [US2] Make T024 to T027 pass — expected to be assertions over the existing folds rather than new code; where a fold has to change, change the fold and not the test.

**Checkpoint**: commit.

---

## Phase 5: User Story 5 — no supported path publishes the service (P1)

**Goal**: the guard, in FR-029's order — the per-request check first, because it is the one that
holds when the process was not started by us.

- [x] T029 [P] [US5] Write `tests/unit/test_the_client_must_be_on_loopback.py`: under the default context a request whose client address is not loopback is refused, **and so is one whose client address is absent**, asserted by supplying the ASGI scope directly through the in-process client; under the container context it is relaxed (FR-026a, SC-012b).
- [x] T030 [P] [US5] Write `tests/unit/test_the_bind_context_is_closed.py`: the type has exactly two members read off the closed type; an unrecognised value refuses at startup naming both; no flag, key or variable other than the context widens the set of addresses (FR-027, FR-030, SC-013).
- [x] T031 [P] [US5] Write `tests/unit/test_the_startup_refuses_a_public_bind.py`: `0.0.0.0`, `::` and a literal LAN address exit non-zero naming the release gate; `127.0.0.1` and `::1` start; a hostname is refused as a hostname and no case performs a lookup (FR-026, SC-012).
- [x] T032 [P] [US5] Write `tests/unit/test_the_container_claim_is_verified.py`: the container context with no marker refuses naming the marker; with one it starts (FR-027a, SC-012a).
- [x] T033 [US5] Implement `src/terezy/api/http/bind.py` and `src/terezy/api/http/middleware.py`.
- [x] T034 [US5] Implement `src/terezy/api/http/serve.py` — the entry point that takes an address, applies the guard, then calls the server with the address it checked; reachable as `python -m terezy.api.http` (FR-026b).
- [x] T035 [P] [US5] `tests/contract/test_the_host_header_is_declared.py`: no CORS middleware is installed and no `access-control-allow-origin` header is ever emitted (FR-032a, as amended: 021 is same-origin in both modes), and a `Host` the service does not declare is **refused**, including with no `Origin` at all — the DNS-rebinding shape (FR-032b, SC-016a, SC-016c).
- [x] T036 [P] [US5] Write `tests/contract/test_the_shipped_compose_file.py`: every published port on every service is `127.0.0.1:<port>:<port>`; the `api` service mounts `data/` read-only, sets the container bind context, and names only the official Python base or this repository's own build; parsed as text with no daemon (FR-028, FR-033, FR-034, FR-035, SC-014, SC-015, SC-023b).
- [x] T037 [US5] Write `docker-compose.yml` and `Dockerfile` at the repository root — the `api` service published at `127.0.0.1:8000:8000`, `data/` read-only, started through the entry point of T034, and the file shaped so feature 021 can add a `web` service under a dev profile without touching the `api` one.
- [x] T038 [P] [US5] Write `tests/contract/test_nothing_claims_to_be_undefeatable.py`: no message, docstring or document this feature adds says the restriction cannot be defeated (FR-027b, SC-013a).

**Checkpoint**: commit.

---

## Phase 6: The three remaining endpoint families

**Goal**: the registry summary, the two windowed series, and the answer.

- [x] T039 [P] Write `tests/unit/test_the_registry_summary.py`: every category and no other, each with its shape; a keyed one reports its id count and a singleton **whether its document resolved**; every file is listed under exactly one category; every manifest input reference for an answer run appears there with the same file and version (FR-009, SC-003b).
- [x] T040 [P] Write `tests/unit/test_the_summary_merges_marks.py`: a category holding one unverified source reports unverified, and its merged provenance equals the fold through `provenance.merge`; marking one source verified changes that category's verdict and nothing else (FR-010, SC-003c).
- [x] T041 Implement `src/terezy/api/http/summary.py`, using `terezy.data.manifest`'s own digest functions and never a second hashing path.
- [x] T042 [P] Write `tests/unit/test_a_series_window.py`: an omitted window returns the whole declared coverage; a given window is two-ended; one reaching outside coverage refuses by name and returns zero observations, never a truncated result; the list read publishes the coverage a client would need (FR-045, FR-045a, FR-046, SC-020).
- [x] T043 [P] Write `tests/unit/test_an_observation_carries_its_own_mark.py`: every observation carries its own provenance, and a series with one verified observation renders exactly that split (FR-047, SC-021).
- [x] T044 Implement `src/terezy/api/http/series.py` and register the two observation routes.
- [x] T045 [P] Write `tests/contract/test_the_answer_over_http.py`: a declared question answered over HTTP equals what the CLI produces for the same question and `as_of`, compared on the canonical digest; every answer carries its manifest; an undeclared question id is a typed refusal rather than a load error; `as_of` is required and its absence names the parameter (FR-042, FR-044, SC-018, SC-019).
- [x] T046 Implement `src/terezy/api/http/answers.py` and register `/questions/{id}/answer`.
- [x] T047 [P] Write `tests/contract/test_what_is_not_served.py`: `data/observations/` is reachable through no route; no endpoint accepts a question built from request parameters; the two documentation routes serve nothing and no served byte references an external host (FR-031, FR-043, FR-048, SC-016, SC-022, SC-026a).

**Checkpoint**: commit.

---

## Phase 7: User Story 3 — the document the client is generated from (P1)

**Goal**: a checked-in OpenAPI document that cannot drift, and an endpoint that serves those exact
bytes.

**Independent test**: regenerate and compare bytes; then move one field on one response record and
watch it go red.

- [x] T048 [P] [US3] Write `tests/golden/test_the_openapi_document.py`: regenerating produces bytes identical to `src/terezy/api/http/openapi.json`; the body served at `/openapi.json` is byte-identical to the file; `info.version` is a literal and no path behind the document reads distribution metadata (FR-038, FR-038a, FR-039, FR-041, SC-007, SC-007a, SC-007c).
- [x] T049 [US3] Implement `src/terezy/api/http/document.py` — the version literal, the canonical dump, and the route serving the committed file verbatim.
- [x] T050 [US3] Write `scripts/generate_openapi.py` and generate `src/terezy/api/http/openapi.json` (FR-040, SC-007b).
- [x] T051 [US3] Mutation check, recorded in the report rather than in prose: add a field to one response record, confirm T048 fails naming the path that moved, revert.

**Checkpoint**: commit.

---

## Phase 8: The scans that keep the layer honest

- [x] T052 [P] Write `tests/contract/test_the_http_layer_computes_nothing.py`: no module under `terezy.api.http` constructs a `Money` or calls a combining function; none imports `core.results.canonical`; none calls a staleness function or ages a source (FR-003, FR-020, FR-049, SC-008b, SC-008c, SC-024).
- [x] T053 [P] Write `tests/contract/test_the_api_dependency_closure.py`: the runtime closure of the `api` extra in `uv.lock`, markers included and none evaluated, equals the reviewed list beside the test; a new package fails until a line describing its network behaviour is written (FR-036, SC-016b).
- [x] T054 [P] Write `tests/contract/test_no_test_starts_a_server.py`: no test module under the HTTP suite constructs a server or calls the server runner; serving a request opens no socket (FR-050, SC-017).
- [x] T055 [P] The CLI half of SC-023a, in `tests/contract/test_the_http_layer_computes_nothing.py` rather than a module of its own: no module under `cli/` or `core/` names `api.http`, which is the claim `.importlinter`'s layers contract cannot make because it permits `cli` to import anything under `api` (FR-001, FR-004).

**Checkpoint**: commit.

---

## Phase 9: Landing

- [x] T056 Record the test paths on the `docs/REQUIRED_TESTS.md` rows this feature reinforces — H2, H3, H4, E5, B10, K4 — and flip **no** box; F1, F2, F3 and F4 stay open, F2 because the switch is deferred (FR-051, SC-026).
- [x] T057 Confirm `docs/METHODOLOGY.md` gains nothing, as a check rather than an assumption (SC-025).
- [ ] T058 Run `uv run python scripts/check_prose_budget.py` and `scripts/check_enumerations.py`; then `/condense` over the branch diff.
- [ ] T059 `/code-review` at high effort with the explicit target `main...feat/020-http-api`, run inside this worktree; fix findings and repeat until clean.
- [ ] T060 Mutation checks recorded: the loopback guard made to accept a public bind fails a test; the OpenAPI golden fails on a changed response model (both reverted).

---

## Dependencies

- **Phase 1** blocks everything. **Phase 2** blocks every story.
- **US1 (Phase 3)** needs Phase 2. **US2 (Phase 4)** needs Phase 3 for a body to assert over.
- **US5 (Phase 5)** needs only Phase 1 and the app object from T018, and is otherwise independent of
  US1 and US2 — it is the phase that can run in parallel.
- **Phase 6** needs Phase 3. **US3 (Phase 7)** needs every route registered, so it comes after 3, 5
  and 6 — the document is a function of the whole route table.
- **Phase 8** needs the modules to exist. **Phase 9** is last, and the review must cover the diff
  that actually lands.

## Parallel opportunities

Within a phase, every `[P]` task is a different file. Across phases, US5's guard work (T029 to T038)
touches no file the category work touches, and the two can proceed together once T018 exists.

## Implementation strategy

MVP is Phases 1 to 3: every declared category readable over loopback, tagged and provenance-carrying.
US2 and US5 are equal-priority and both land before anything is called done; US3 lands last because
the document it gates is a function of the finished route table.
