# Implementation Plan: The question goes in the request body

**Feature**: `029-question-in-request` | **Date**: 2026-09-13 | **Spec**: [spec.md](./spec.md)

**Branch**: written on `spec/029-question-in-request` and lands **squashed** — spec-directory work,
not an implementation. The implementation branch is `feat/029-question-in-request` and lands by
`--no-ff`.

**Both clarifications are answered** (`specs/decisions/2026-09-13-clarify-029.toml`, 2026-09-13).
Neither reaches the endpoint, the schema or the manifest: the undeclared stream comes back as the
loader's refusal attributed to the request, which Phases 2 and 4 already build, so Phase 7 is a
test; and a card for a body-asked candidate is not in this feature.

## Summary

One POST takes the document a question file holds, hands it to the loader that already validates
that document, and returns what the saved read returns. The manifest records the body by digest
instead of by path, so the answer is still reproducible. Zero new core records, zero new figures,
no writes.

The plan's contribution over the spec is six findings and a build order.

**Finding 1 — the validator exists, and so does the sentinel.** `loader.question_from_document`
takes a document and a path and is public *because* the CLI builds its record through it (015
FR-005); the CLI passes `FLAGS = Path("<flags>")` as that path. So FR-001 costs no new model and no
new validation — the route hands the parsed JSON body to that function with a body sentinel in
place of `FLAGS` — and the spec's two measurements are what say it will work.

**Finding 2 — the framework must not validate the body, and must still publish its schema.**
Declaring the parameter as `schema.QuestionFile` makes FastAPI validate it, and a shape fault then
arrives as `RequestMalformed` — no `field_path`, no `remedy`, a different tag from the one a
malformed *file* produces. That is exactly what FR-012 forbids. So the route reads the **raw**
body and publishes the request schema through the route's OpenAPI extension, with the schema
**generated from `schema.QuestionFile`** rather than written out: a hand-written request schema is
the second model FR-001 forbids, and it drifts silently the first time a field is added. Validation
then happens in one place, the loader, for a file and a body alike.

**Finding 3 — attribution is already a field, and one check is on the wrong side of it.**
`DeclarationError` carries the artefact it blames, and `api.answer.answer_declared` already threads
`declared_in` through. So FR-013's rule needs no new exception type: a refusal naming the body
sentinel is the **request's** fault, anything else is the **server's**, and the existing
`DeclarationError` handler branches on that one fact.

**Two** checks sit on the wrong side of it, and they are near-identical: `api.answer._scenario_of`,
which runs *before* `resolver.check_question` because it is evaluated to build that call's argument,
and `api.answer.inputs_of`. Both raise an undeclared-regime refusal rooted at
`resolver.SCENARIOS_DIR`, so a body naming a regime nobody declares reports a broken data root
(FR-015). The fix belongs where the fault is: a question naming an undeclared regime is the
**question's** fault whatever declared it, so both refusals name the question's artefact and the
field `question.regime`. Neither moves a figure, and both improve the file path too, where the same
refusals today also blame the wrong file.

An observation that is **not** fixed here: `inputs_of` re-states the objective-set refusal that
`check_question` already makes, and `run` calls `check_question` first, so `inputs_of`'s copy is
unreachable from the answer path. One fact in two places, predating this feature; recorded, not
touched, because moving it is a change to 019's refusal surface.

**Finding 4 — the manifest records every question file and never the question.**
`manifest.answer_input_refs` builds a `question` reference per entry of
`declarations.question_files`, which is every file the root declares — the one that was *answered*
is not distinguished, and a question with no file appears nowhere. FR-019 closes the second half:
the answered question gets a reference of its own whenever it has no file, with the body sentinel in
place of a path.

Its `version` cannot come from `file_version`, which reads bytes off disk. It is
`sha256:<hex>` over the **validated record's** canonical rendering — sorted keys, optional fields
the record does not hold left out, the convention the OpenAPI document already names. Not the raw
request bytes, and not the caller's document either: measured 2026-09-13, `"amount": 50000` and an
explicit `null` on an optional field both validate, both dump to the file's own spelling, and both
differ from the file's bytes — so anything digested before validation gives one question two
identities and FR-020 cannot hold across TOML and JSON at all. The renderer
lives once, in `terezy.data.manifest`, beside the digesting it exists for;
`api.http.document.rendered` is **not** it and is not merged with it — one renders a wire artefact
for serving, the other feeds a hash — and the shared thing is a convention, not a function.

FR-021 keeps a file digesting its own bytes, so no golden and no existing manifest moves.

**Finding 5 — the POST falsifies a guard that was defending something else.**
`tests/contract/test_the_route_table.py` asserts `methods == {"get"}` under the name
*`test_no_route_writes`*, and asserts the answer routes are exactly the declared-id one. The first
is a guard whose name is about writing and whose body is about a verb; once one POST exists it must
assert what it meant, and it takes **two** tests to do that honestly:

- the surface — the set of non-GET operations is exactly `POST /api/answers`, so a second one added
  later is a red build; and
- the behaviour — a POST leaves `data/` byte-identical, asserted by digesting the tree either side
  (SC-012). Without this one the first is a false guard: it pins a method and says nothing about a
  write.

`test_the_only_answer_route_names_a_declared_question` becomes the presence of the two answer routes
(FR-027). An absence test kept after the thing exists passes for the wrong reason.

**Finding 6 — the cap belongs in the middleware, not the handler.** The body is read and parsed
before a handler runs, so a cap checked in the route has already paid for the parse that FR-024
exists to prevent. The chain that already refuses off-loopback requests
(`middleware.loopback_guard`, `host_allowlist`) is where a `Content-Length` check goes, refusing
with a tagged record the way `NotOnLoopback` does — but that chain wraps **every** route, and every
other route is a GET with no length to declare. So the check applies to a request that carries a
body, and a body arriving without a declared length is refused rather than streamed and counted:
counting as it arrives is the machinery the cap exists to avoid.

## Technical context

**Language**: Python 3.13, as the repository. **Dependencies**: no new one. FastAPI, Pydantic v2 and
the loader are all already present. **Layers touched**: `api/http/` (the route, the envelope, the
refusal mapping, the middleware), `api/answer.py` (the regime refusal's path), `data/manifest.py`
(the body's reference and the canonical renderer), `cli/main.py` (the same digest from `--set`).
**`core/` is not touched at all** — no new record, no new refusal, no new figure.

**Wire version**: `document.VERSION` is bumped once, in the commit that adds the route (020 FR-041).

## Constitution check

| Gate | Verdict |
|---|---|
| Pure deterministic core (III) | `core/` unchanged. The clock is still unread: `as_of` stays required (FR-004). |
| A result without a manifest is not a result (III) | FR-018 and FR-019 make the answered question appear in the manifest for the first time on the flags path too. |
| Framework, not script (II) | No domain knowledge enters code. The candidate ceiling stays declared data (FR-025). |
| Failure is explicit (IV) | Every boundary refusal is the loader's typed record carried verbatim; nothing is synthesised (FR-012). |
| Honesty over precision (I) | No figure moves. Provenance is untouched (FR-023). |
| Owner-scoped and private (VII) | Loopback-only and the authentication gate unchanged (FR-026). The body names its owner and an undeclared one refuses (FR-003). |

No violation to justify; the Complexity Tracking table is empty and omitted.

## Build order

Each phase is green on its own and is a commit.

**Phase 0 — the failing tests.** The contract tests of SC-001 to SC-012, written against nothing
and red. This is the phase that proves the round trip is a test rather than a measurement in a spec.

**Phase 1 — the question's identity in the manifest** (FR-018 to FR-021). The canonical renderer and
the body/flags reference in `data/manifest.py`, plus the CLI's digest. Testable end to end through
the CLI with no HTTP: `--set` produces a manifest naming the question it answered, and the same
document posted later must match it. Lands before the endpoint deliberately — it is the half that
makes the endpoint reproducible, and the half an implementer would otherwise leave to last.

**Phase 2 — attribution** (FR-013, FR-015). The regime refusal names the question's artefact; the
`DeclarationError` handler branches on which artefact is named. Both cases asserted, so neither
passes by answering everything one way.

**Phase 3 — the endpoint** (FR-007 to FR-009). `POST /api/answers`, the raw body into the loader,
the published request schema generated from `schema.QuestionFile`, and its own response container —
**not** `TheAnswer`, whose `result` union carries `CategoryHasNoSuchId`, a member a POST can never
produce. A union member that cannot occur is a switch arm a client writes for nothing.

**Phase 4 — the boundary's refusals** (FR-012, FR-014, FR-016, FR-017). The loader's record and tag
carried through, the sentinel in place of a path, and the assertion that the answer's own `Refused`
union still arrives in a 200 body unchanged.

**Phase 5 — the cap** (FR-024). Middleware, a tagged refusal naming the cap and what was received.

**Phase 6 — the published contract** (FR-010, FR-027, FR-028). The two route-table tests, the
OpenAPI request schema and its union walk, the `document.VERSION` bump,
`docs/REQUIRED_TESTS.md`, and `specs/features.toml`: `status = "done"`, and
`http-question-from-request-parameters` closed.

**Phase 7 — the undeclared stream** (FR-029). The loader's refusal attributed to the request,
naming `question.amount.stream`, which Phases 2 and 4 already build — so this phase is the test
that says so, plus the assertion that neither `AmountForAnUndeclaredStream` nor
`StreamWithNoAmount` reaches this surface.

## Out of the plan, by the spec

The UI form (030), saving a body, partial overrides, a card for a body-asked candidate, and
the answer document's size, which is unchanged and already recorded as a future.
