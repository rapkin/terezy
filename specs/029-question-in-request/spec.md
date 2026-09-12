# Feature Specification: The question goes in the request body

**Feature Directory**: `specs/029-question-in-request`

**Feature Branch**: `spec/029-question-in-request` (spec-writing worktree; squash-lands per `specs/README.md`)

**Created**: 2026-09-13

**Status**: **Planned** — `plan.md` and `tasks.md` exist and both clarifications are answered
(`specs/decisions/2026-09-13-clarify-029.toml`, 2026-09-13).

**Input**: Owner decision of 2026-09-13, after an outside review. The natural operation — *"I have
₴170 000, I need the money accessible in nine months, keep ₴50k liquid, what should I do?"* — must
not require editing a TOML file. The owner chose: the question goes in the request body, as the
**same record** a declaration file holds. Declaration files stay as **saved** questions. This
feature is the API half; the question form in the UI is feature **030** and is out of scope here.

---

## Why this feature exists

Feature 015 settled that **a question is a declaration** (owner, 2026-08-30, taken against a
command-line-arguments-are-canonical alternative), and its own note settled the other half in the
same sentence: *"flags remain as sugar that builds the same record in memory."* The CLI has that
sugar; the HTTP surface has none, because 020 FR-043 kept it out and `SC-026a` asserts its absence
over the route table. What that costs is now visible: asking a new question means editing a file,
which is fine for a standing question and wrong for *what if it were nine months instead of six* —
a question asked and thrown away.

**The measurement that makes the body cheap.** Read 2026-09-13 off `schema.QuestionFile`: the
question schema is **36 fields across 8 tables**, every one a string, a number, a boolean, a list or
a nested table, and not one a TOML date or datetime. So JSON carries the whole schema, and the round
trip is not a claim: `data/questions/fifty-thousand.toml` parsed, rendered as JSON, read back and
handed to `loader.question_from_document` yields a `Question` **equal** to `question_from_file`'s.

**And the measurement that keeps files.** That file is 8 499 bytes; its canonical JSON is **2 159**.
The difference is comment — why the benchmark is that ISIN, why a token dollar amount is required,
which three facts the owner still has to confirm. A saved question carries its reasoning; a request
body carries none. That is the reason declaration files are not replaced by this feature, and the
reason the answer to *"should the API save a body as a file"* is no.

### What the body does not remove

The review's sentence names three of the question's fields — an **amount**, a **horizon**, and a
**reserve** ("keep ₴50k liquid" is `[[question.reserve]]`, which already has `amount`, `currency`
and `by`). It names none of the other required ones: the owner, the regime, the continuation
assumption, the benchmark, the objective set, the subjects, and a run plan per subject — none with
a default, because 015 refused to give them one. **The body removes the file edit, not the
declarations**, and supplying them from something a person would say is 030's problem.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A question nobody saved is answered (Priority: P1)

A caller holds a whole question — the document a file would hold — and wants its answer without
committing a file. **Independent Test**: post the document of `data/questions/fifty-thousand.toml`
and compare against the saved question's GET.

1. **Given** the shipped data root, **When** that body is posted verbatim with the same `as_of`,
   **Then** the answer is byte-identical to `GET /api/questions/fifty-thousand-hryvnia/answer`, and
   the posted manifest carries **exactly one input the saved read does not** — the body's own
   question reference — and is otherwise equal.
2. **Given** that body with one horizon's `end` moved, **When** it is posted, **Then** the answer is
   the answer to *that* question and nothing under `data/` has changed.

### User Story 2 — A bad body is the caller's fault, and says which field (Priority: P1)

**Independent Test**: post a body with a missing table, an unknown field, an undeclared owner.

1. **Given** a body missing `question.objectives`, **When** it is posted, **Then** the refusal
   carries the loader's own four fields with the same tag a malformed *file* produces, and a status
   saying the **request** was wrong rather than the data root.
2. **Given** a body naming a regime no scenario declares, **When** it is posted, **Then** the
   refusal names `question.regime` and is attributed to the request.
3. **Given** a data root with a broken instrument file, **When** any body is posted, **Then** that
   refusal is attributed to the **server**, unchanged.

### User Story 3 — The answer stays reproducible (Priority: P1)

**Independent Test**: read a posted answer's manifest; re-run the same document through the CLI.

1. **Given** a posted question, **When** its manifest is read, **Then** it names the question as an
   input whose version is a digest of the body, and no path on the serving machine.
2. **Given** one body, one `as_of` and one data root, **When** it is answered in two processes,
   **Then** both answers and both manifests agree exactly.

### Edge Cases

- A body whose `question.id` equals a declared question's — permitted; the two inputs are told apart
  by what declared each.
- A body over the cap; a body that is valid JSON but not an object; an empty body.
- A body whose subjects resolve to nothing — not a refusal, the answer's content. Not `btc`, which
  025 declared and which the shipped answer reports as **held**; measured 2026-09-13 the undeclared
  population is empty, so a test needs a word nothing declares to reach it.

---

## Requirements *(mandatory)*

### One schema, two sources

- **FR-001**: The request body MUST be the same document a question file declares — the `[owner]`
  and `[question]` tables — as JSON, and MUST be validated by the **one** function that validates a
  file's document. There MUST be no second question model, no second validator, and no default a
  file cannot state. This is 015 FR-005's rule, which the CLI already lives under, applied to HTTP.
  What a body may not do is **mean** something a file cannot: JSON can spell a value two ways a file
  cannot (FR-018), and both spellings must produce one question and one identity — never a field the
  file has no way to write.
- **FR-002**: Every field of the question schema MUST remain JSON-expressible. A field typed so
  only TOML can carry it would make the body a second schema, and a test MUST assert the property
  over the schema rather than over a list of field names.
- **FR-003**: The body MUST name its owner in `[owner]` exactly as a file does. An owner no
  declared income stream belongs to MUST refuse: a question is one person's, and answering it from
  another person's money puts two people's facts in one comparison (Principle VII, 015 FR-005).
- **FR-004**: `as_of` MUST stay a **query parameter**, required, with no default, and MUST NOT be
  a body field. 015 FR-006's reason is unchanged and reaches further here: it is the field the
  digest would make a lie, since a body whose horizons moved with the calendar would be a different
  question under one digest. 020's Answered 2 keeps it required, and no code path reads a clock.
- **FR-005**: There MUST be no partial override of a saved question. A request states a whole
  question or it states none: a saved question with three fields replaced is a third source of
  truth, reproducible only by whoever still holds the overrides.
- **FR-006**: This feature MUST write nothing. No endpoint saves a body as a declaration file, and
  no response carries a "saved as" name. Saving is the owner's editor, and 020's *writes of any
  kind* stays out of scope.

### The endpoint

- **FR-007**: The endpoint MUST be `POST /api/answers`, taking a whole question as its body and
  `as_of` as its query parameter, and returning what the saved read returns: the answer or its
  typed refusal, and the run manifest (020 FR-042, FR-044).

  **The alternative, and why not.** `POST /api/questions/{id}/answer` carrying overrides was
  considered and rejected by FR-005: it reads as *this saved question, but*, and the thing answered
  is then declared in two places. A body-taking route under `/questions` was rejected too — that
  segment is the **declared** category, and a route there that answers something undeclared makes
  the category's own list a lie about what it covers.

- **FR-008**: `GET /api/questions/{id}/answer` MUST be unchanged: same path, same envelope, same
  behaviour for a declared id. A saved question is still read by name.
- **FR-009**: The answer this feature returns for a given question MUST be the **same value** the
  saved read returns for the same question and `as_of`. There is one answer verb and this adds no
  second one.
- **FR-010**: 020's read-only guard MUST be restated rather than deleted. It asserts today that
  *every route is a GET*, which this feature falsifies while the property it was defending — **no
  route writes** — is untouched. The replacement MUST assert what no route does, and MUST name the
  one non-GET route explicitly, so that a second POST added later is a red build rather than a
  silent widening.
- **FR-011**: The candidate projection endpoint MUST stay addressed by a declared question id.
  A candidate's card is reached by `(question id, candidate key)` and a body-asked question has no
  address. The owner settled on 2026-09-13 that a card for an unsaved question is decided with the
  UI form (030) and the redesign that comes with it; the `a-card-for-a-body-asked-candidate` future
  entry carries it, and nothing here builds it.

### Refusals, and whose fault a request is

- **FR-012**: A malformed body MUST refuse with the **same record and the same tag** a malformed
  file produces, carrying the loader's four fields verbatim — what declared it, the field path, the
  problem, the remedy — with nothing synthesised (020 FR-015). An unrecognised field MUST be named
  and MUST NOT be ignored, which is the strict behaviour a file already gets (Principle II).
- **FR-013**: The refusal MUST say **whose fault it is**: a fault in the body is the request's, a
  fault in the data root is the server's. Both are one exception type today, and a body fault
  reported as a broken data root sends a caller to fix a file that is fine. The two MUST be told
  apart by which artefact the refusal names, not by which call site raised it.
- **FR-014**: A body-attributed refusal MUST name the **request** where a file names its path.
  An absolute path on the serving machine is a fact about that machine (020's own rule), and there
  is no file to go and look at.
- **FR-015**: A body naming a regime no scenario declares MUST refuse as a **request** fault naming
  `question.regime`. Today that check runs before the question is cross-checked and its refusal
  names a data-root directory, so without this requirement the first typo a caller makes is
  reported as a broken installation.
- **FR-016**: The answer's own `Refused` union MUST be unchanged and MUST still arrive in the body
  with the same shape as an answer (020 FR-016). A plan for nothing, a benchmark outside the
  subjects, two identical horizons, a subject that reaches no candidate — all reach a posting
  caller exactly as they reach a saved one.
- **FR-017**: A body MUST name subjects by **group label** exactly as a file does, and the
  resolution, the undeclared-subject population and the counts MUST be unchanged (015 FR-007a).
  Nothing about a request may make a label mean something a file's label does not.
- **FR-029**: A body naming an **income stream no declaration names** MUST refuse with the
  loader's own record, attributed to the request, naming the field `question.amount.stream`
  (owner decision 2026-09-13). One shape for every body mistake: never a 200 whose body is a
  different record. `AmountForAnUndeclaredStream` and `StreamWithNoAmount` therefore stay
  unreachable through `api/` and remain the form the **verb** returns to a caller holding a
  record it built itself — which is what `answer_declared` already records about itself.

### Reproducibility

- **FR-018**: The run manifest MUST record the posted question as an input of kind `question`,
  whose **version is a digest of the validated question document in canonical form** — sorted keys,
  the rendering the OpenAPI document already defines — and whose declaring artefact is the request
  rather than a path. Two runs of one body agree on that digest; two different questions do not.

  **The digest is taken over the validated record, never over the bytes received**, and that is the
  requirement rather than an implementation note. JSON has two spellings a TOML file cannot produce
  — an integer where the schema declares a number, and an explicit `null` where a file simply omits
  the key — and both are **accepted**, both yield the *identical* `Question`, and both differ from
  the file's bytes. Measured 2026-09-13: `"amount": 50000` validates and dumps as `50000.0`, and an
  explicit `null` on any of the nine optional fields is indistinguishable from omission. Digesting
  what arrived would give one question two identities, which is the one thing this field exists to
  prevent.
- **FR-019**: **Every question a run was answered from MUST appear in the manifest's inputs**,
  whatever declared it — a file, a request body, or CLI flags. The record today is that a question
  with no file contributes no input reference at all; that was true when there was nothing to
  digest and is false once a canonical form exists, and the run then records every file it read and
  not the question it answered.
- **FR-020**: The CLI's flags path MUST record the **same digest** for the same question, so that
  one question asked two ways has one identity and a posted answer can be re-derived on a command
  line. This is what *flags are sugar over the file* means once the file is optional, and FR-018's
  rule is what makes it reachable: TOML and JSON do not spell one question the same way, so only a
  digest of the validated record can agree across them.
- **FR-021**: A file-declared question MUST keep digesting its **file's bytes**. A body's digest and
  a file's digest of the "same" question therefore differ, and the specification states it here
  rather than letting a reader infer equality: a digest is a witness of what was fed in, and what
  was fed in was different bytes carrying different comment.
- **FR-022**: The same body, the same `as_of` and the same data root MUST yield the same answer and
  the same digest **across two processes**, so nothing rests on hash seed or insertion order.
- **FR-023**: Provenance MUST be untouched. No figure gains or loses a mark, and no staleness
  verdict changes, because the question arrived in a body (Principle I).

### Size, and what a request may not raise

- **FR-024**: A body above a declared size cap MUST be refused with a typed record naming the cap
  and what was received, **before** it is parsed. Never truncated, never parsed in part. The cap is
  measured against the real thing: the shipped question's canonical JSON is 2 159 bytes.

  The rule MUST apply only to a request that **carries a body**. Every read on this surface is a GET
  that legitimately declares no length, so a cap that refused a request stating no `Content-Length`
  would refuse every existing endpoint — and it would do it wearing a message about a question
  document.
- **FR-025**: The candidate ceiling MUST stay 014's declared `max_candidates` under
  `data/candidates/`. A request MUST NOT be able to raise it, state one, or opt out: how far the
  owner will let a search run is a fact about him, declared as data.
- **FR-026**: There MUST be no rate limiting, quota or throttle, and no change to the bind: one
  user on loopback, and Principle VII's authentication gate is neither approached nor weakened
  (020 FR-026 to FR-030).

### What this changes in the published contract

- **FR-027**: 020 FR-043 is **superseded** by this feature, and its `SC-026a` absence test MUST be
  replaced by the presence of exactly this one body-taking answer route — an absence asserted after
  the thing exists is a test that passes for the wrong reason.
- **FR-028**: The OpenAPI document MUST publish the request body's schema, the tag and
  discriminated-union walk MUST cover every record reachable from it (020 FR-011 to FR-014), and
  `document.VERSION` MUST be bumped in the same commit (020 FR-041).

---

## Key entities

- **The question document** — `[owner]` and `[question]`, the same 36 fields whether it arrives as a
  file's bytes or a request's JSON.
- **The question input reference** — the kind, the declared id, what declared it, and a digest of
  that artefact.

---

## Success Criteria *(mandatory)*

- **SC-001**: The document of `data/questions/fifty-thousand.toml` posted verbatim yields an answer
  byte-identical to the saved GET's, and a manifest carrying **exactly one added input** — the
  body's question reference — and otherwise equal. An *added* input rather than a differing one,
  because the manifest already records every question file the root declares whichever was
  answered; a test asserting an equal-sized difference would be written to a claim that is false.
  (FR-001, FR-009, FR-019)
- **SC-002**: A `Question` built from the file and one built from the body's JSON are equal, field
  for field. (FR-001)
- **SC-003**: Every field of the question schema is JSON-expressible, asserted over the schema.
  (FR-002)
- **SC-004**: A malformed body and the same malformation in a file produce the same refusal tag and
  the same field path. (FR-012)
- **SC-005**: A body fault is attributed to the request and a data-root fault to the server, each
  asserted with the other's case present so neither passes by answering everything one way.
  (FR-013)
- **SC-006**: An undeclared regime, an undeclared owner and a body-attributed refusal all name the
  request and no filesystem path. (FR-014, FR-015)
- **SC-007**: The manifest of a posted answer carries a question input whose version is the digest
  of the validated document, the same question answered through the CLI carries the same digest,
  and a body spelling an amount as an integer or an omitted field as `null` digests the same as the
  file's own spelling. (FR-018, FR-020)
- **SC-008**: One body, one `as_of`, one data root, two processes: identical answer digest and
  identical manifest. (FR-022)
- **SC-009**: A body one byte over the cap is refused with the cap and the size named, and nothing
  is parsed. (FR-024)
- **SC-010**: The route table has exactly one non-GET route, and no route writes to the data root.
  (FR-010, FR-027)
- **SC-011**: The served OpenAPI document contains the request schema and every union reachable
  from it carries its discriminator. (FR-028)
- **SC-012**: Answering by body leaves `data/` unchanged, asserted by digesting the tree before and
  after. (FR-006)
- **SC-013**: A body naming an undeclared stream refuses as a request fault on
  `question.amount.stream`, and no response on this surface carries
  `AmountForAnUndeclaredStream` or `StreamWithNoAmount`. (FR-029)

---

## Answered by the owner, 2026-09-13

Both answers are recorded verbatim in `specs/decisions/2026-09-13-clarify-029.toml`; neither moves
a figure.

**An undeclared stream in a body comes back as the loader's refusal** (FR-029), attributed to the
request and naming `question.amount.stream` — one shape for every body mistake, so a form
highlights a field and a client narrows on one record. The alternative, a 200 carrying the verb's
`AmountForAnUndeclaredStream`, was refused because it makes one class of caller mistake arrive in
two shapes. The two union members stay unreachable through `api/`.

**A card for a candidate of a body-asked question is not in this feature** (FR-011). It is decided
with 030's form and the redesign that comes with it, where whether such a card is opened at all is
visible; `a-card-for-a-body-asked-candidate` in `specs/features.toml` carries it.

## Assumptions

- The body is **JSON**. TOML on the wire would need a second parser at the boundary and a media
  type nothing else here uses, for a document whose every field JSON already carries.
- The size cap is a service limit rather than domain knowledge, so it is stated in the HTTP layer
  and not in `data/`. **64 KiB** is proposed — about thirty times the shipped question's canonical
  body — and the number is changeable without a spec edit.
- `POST` here is not a write: it is a read whose input is too large for a URL.
- The answer document's size and the web client are both unchanged.

---

## Out of scope

- **The question form in the UI.** Feature **030**. This feature is the API half, and the form is
  where a person's sentence becomes the eight required fields it does not contain.
- **Saving a body as a declaration file.** FR-006, carried by the `saving-a-body-as-a-question`
  future entry; the owner's editor and the CLI are how a question becomes saved today.
- **Partial overrides of a saved question.** FR-005.
- **More than one owner.** Principle VII's boundary is unchanged: one owner, and the body names
  him exactly as a file does.
- **Authentication.** Unchanged and not approached (FR-026).
- **A card for a body-asked candidate.** FR-011, and the owner's answer of 2026-09-13.
