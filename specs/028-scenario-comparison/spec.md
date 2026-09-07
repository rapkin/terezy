# Feature Specification: Two regimes, side by side, and what the belief moved

**Feature Directory**: `specs/028-scenario-comparison`

**Feature Branch**: `spec/028-scenarios`

**Created**: 2026-09-07

**Status**: **Drafted** — two clarifications are open; planning may start on everything they do
not touch, and the plan says which tasks they gate.

**Input**: The owner's roadmap item of 2026-09-06, step 3: *"Scenario comparison side by side.
The API accepts `scenario_id`, the web never sends it. Two requests with different regimes and
one reading side by side close the words 'adverse scenarios' in the owner's question, with no
engine change."*

## Why this feature exists

The owner asked for "adverse scenarios" on 2026-08-30 and got a stated exclusion. 015's answer
was that a question declares one regime by design, so comparing under two is **two questions and
a reading across them** — recorded as owner verification task 4 and closed by nothing since.
019 then built the thing worth reading across: the non-dominated set, with the assumption that
separates its members named. `docs/DIRECTION.md` calls that the honest output, and a regime is
exactly such an assumption — the one that decides which corridors exist at all.

This feature is the reading. It adds no figure, no verdict and no line of `src/terezy/`.

## What was measured, 2026-09-07

Three measurements, and the first two correct the roadmap item's own premise.

1. **The answer endpoint takes no `scenario_id`, deliberately.** Its published parameters are
   exactly `question_id` and `as_of`, pinned by
   `tests/contract/test_the_answer_over_http.py::test_the_answer_takes_no_scenario_parameter`,
   because *the answer resolves its own scenario from the question's declared regime, so a
   parameter here would be one a caller could set and believe in while it decided nothing*.
   `scenario_id` is a parameter of the **category reads** (`/api/registry`, `/api/spendable` and
   the rest), and there the web indeed never sends it. So the two requests this screen makes are
   two **questions**, and the regime reaches the engine through the declaration, as 015 says.
2. **`war_end` changes nothing in the owner's answer today.** It declares two regimes over the
   ten declared routes: `normalized` names all ten — the same set the implicit regime searches —
   and `wartime` names eight, omitting `monobank_to_binance_card` and `coinbase_to_ibkr`. The
   owner's question answered under `(no regime declared)`, under `wartime` and under
   `normalized` renders **identically**: 1 146 lines each, differing only in the header's
   question id and regime name and in the manifest digest, which moves because the question file
   is one of the 102 inputs. The non-dominated sets stay 2, 3 and 10. The reason is that no
   candidate for this question names either omitted route — the only pair any candidate names is
   `inzhur_direct` out `inzhur_to_monobank`.
3. **`data/questions/` declares exactly one question.** So over the shipped root there is
   nothing to put in the second column, and the honest shipped state is the one that says so and
   names what to declare. Whether a second question is declared, and which regime it names, is
   the owner's — Clarification 1.

The consequence of (2) is not that the feature is pointless. *This belief costs this question
nothing* is a real answer to "adverse scenarios", and it is one the owner cannot get today
because no surface will show him the two answers together. It is also why the acceptance case
that must hold over the shipped root is the degenerate one — the same question in both columns —
where every front member is marked *in both* and the difference block says *these are one
question*.

## What this feature requires of the API

Nothing new. Every obligation below is already met by 020, verified 2026-09-07.

- **OB-1**: the answer read returns `answer.question` — the whole question record, `regime_id`
  among its fields — and `manifest.regime_id`.
- **OB-2**: each section carries its `horizon` (`start`, `end`) and a `dominance` block with
  `non_dominated`, `dominated`, `indistinguishable`, `not_placed` and `incomparable`, beside the
  survey's ranked and refused populations.
- **OB-3**: a candidate key is the five-term `tuple.Tuple` — `instrument_id`, `stream_id`,
  `route_in`, `exit_terms`, `route_out` — identical in shape across two answers, so membership is
  decidable without inventing an identity.
- **OB-4**: the questions category lists the declared ids and serves each record with its
  `regime_id` and its `declared_in` path.
- **OB-5**: the scenarios category serves `regimes[].id` and `transitions[]` with `is_assumption`
  and `rationale`, so *which scenario declares this regime* and *this is a belief* are read
  rather than inferred.
- **OB-6**: an undeclared question id is `envelopes.CategoryHasNoSuchId` with `declared_ids`, not
  a load error.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — He reads two worlds at once (Priority: P1)

From the answer screen a control offers each other declared question, labelled by the regime it
declares and the scenario declaring that regime. He picks one and gets two columns: per horizon,
the union of the two non-dominated sets, each row marked *on the front in both*, *only under
this regime*, or *only under that one*.

**Why this priority**: it is the whole feature; without it "adverse scenarios" stays a stated
exclusion.

**Independent Test**: open the route with two declared ids and one `as_of`; every rendered mark
is derivable from the two responses alone.

**Acceptance Scenarios**:

1. **Given** the shipped root, which declares one question, **When** he opens the compare route
   with that question in both columns, **Then** every horizon shows both fronts, every member is
   marked *on the front in both*, and the difference block says the two columns are one question.
2. **Given** two declared questions differing only in their regime, **When** he compares them,
   **Then** each row's mark agrees with the two served `non_dominated` sets, and a key absent
   from the other column's whole enumeration is marked *not enumerated there* rather than
   *dominated there*.
3. **Given** a horizon declared by one question and not the other, **When** he compares them,
   **Then** that horizon is shown as belonging to one column only, and is never aligned against
   a horizon with a different `start` or `end`.

---

### User Story 2 — The world in the other column is a guess, and says so (Priority: P1)

Each column names the regime its answer ran under. Where that regime belongs to a declared
scenario, the column names the scenario, renders its transition as the assumption the
declaration marks it, and states this system's gap: a scenario switches the route set and does
not switch the tax schedule.

**Why this priority**: a comparison of two worlds that does not say one of them is invented is
the confident-chart failure this project exists to refuse.

**Independent Test**: render one column under a scenario regime and one under the implicit
regime; the first carries the belief mark, the transition's own words in full and the gap
sentence, and the second carries none of the three.

**Acceptance Scenarios**:

1. **Given** a column under `wartime`, **When** it renders, **Then** it names `war_end`, marks
   the 2027-06-30 transition as an assumption, makes the declaration's whole `rationale`
   reachable without elision, and states the tax-schedule gap.
2. **Given** a column under `(no regime declared)`, **When** it renders, **Then** it says so in
   the served string and shows no scenario, no belief mark and no gap sentence.

---

### User Story 3 — He can see whether it was the belief that moved (Priority: P2)

The screen names every field on which the two question records differ, so a difference caused by
his own amount is not read as a consequence of the war ending.

**Why this priority**: without it the screen attributes effects to the wrong cause, which is
worse than showing nothing.

**Independent Test**: compare two questions differing in regime and benchmark; both are named and
the screen states the fronts do not differ by the regime alone.

**Acceptance Scenarios**:

1. **Given** two questions differing only in `regime_id`, **When** they are compared, **Then**
   the screen names that one field and says the difference between the fronts is attributable to
   the regime.
2. **Given** two questions differing in `regime_id` and `benchmark_instrument_id`, **When** they
   are compared, **Then** both are named and the screen states the fronts do not differ by the
   regime alone. It does not refuse.

---

### Edge Cases

- Both fronts empty for a matched horizon: the horizon renders with an empty union stated as
  such, not omitted.
- A regime declared by two scenarios: the label names both rather than picking one. A regime
  declared by none cannot arrive — the answer refuses to load — so the screen has no such state.
- Two questions with no horizon in common: the screen says they share none, rather than showing
  a page of one-column horizons with nothing said about it.
- Every other boundary this screen has is a requirement below rather than an edge case: an
  undeclared id (FR-003), fewer than two declared questions (FR-006), and a refusing section
  (FR-014).

## Requirements *(mandatory)*

### The route, and what it reads

- **FR-001**: The client MUST serve a comparison route reading three typed search parameters:
  `as_of` (021's, unchanged in meaning), and two declared question ids. A missing or malformed
  one is a visible error naming the parameter, and no default is ever substituted (021 FR-020,
  FR-027).
- **FR-002**: Both columns MUST be read at one `as_of`, which is why it is one parameter. Two
  answers at two dates differ for a reason this screen is not about.
- **FR-003**: A question id nothing declares MUST render, for that column, the refusal the
  answer endpoint served for it, with the declared ids it carries. The other column MUST still
  render.
- **FR-004**: The answer screen MUST offer one entry point per declared question other than the
  one it shows, each labelled with that question's declared regime and, where the regime is a
  declared scenario's, that scenario's id.
- **FR-005**: Both lists MUST come from the API: the question ids from the questions category,
  the regime-to-scenario relation from the scenarios category. The client MUST NOT map a
  question, a regime or a scenario to another by any rule it holds itself.
- **FR-006**: Where the API declares fewer than two questions, the entry point MUST be a named
  state that says so and names what would close it — a second question declaration naming a
  declared regime.

### The reading is a set operation over served keys

- **FR-007**: The screen MUST compute no figure. The only things this feature computes are set
  membership over served keys and a field-by-field comparison of two served question records —
  both decidable from the responses alone, and neither a figure with provenance to lose.
- **FR-008**: Horizons MUST be matched between the two answers by the served `start` and `end`
  exactly. A horizon in one answer only MUST be shown as belonging to one column, never aligned
  by position against a horizon with different dates.
- **FR-009**: A candidate MUST be identified by all five terms of OB-3's key. Two rows sharing
  an instrument id and differing in a route are two candidates, and merging them would report a
  membership that is not the engine's.
- **FR-010**: Within a matched horizon the rows shown MUST be the union of the two columns'
  non-dominated sets, each carrying exactly one mark: on the front in both, in the first only, or
  in the second only.
- **FR-011**: For a key on one front only, the screen MUST state the placement the **other**
  column's own record gives it, by the ordered lookup in `contracts/api-reads.md`, and MUST NOT
  leave it blank. *Not enumerated* is what a regime that removed a route produces, and reporting
  it as *dominated* would attribute a corridor's disappearance to a comparison. A population that
  is a property of a pair or an overlay on a placed member — `incomparable`, `indistinguishable`
  — MUST NOT be reported as a placement.
- **FR-012**: Keys **evaluated by the dominance pass** in both columns and on neither front MUST
  be reachable as a named, folded group — the fourth membership state, without which the union
  reads as the whole population. Scoped to the evaluated population and not to `ranked`, because a
  ranked candidate the pass withheld — `inzhur_miltech` at all three horizons of the shipped root
  — would otherwise be folded in as *compared and beaten* when it was never compared.
- **FR-013**: The screen MUST state no verdict about which column is better and MUST NOT present
  the intersection of the two fronts as a result.
- **FR-014**: Where a column has no front at a horizon — the survey refused, the benchmark
  yielded no candidate, or the dominance pass itself refused — the screen MUST render that
  column's own typed reason and invent no membership mark against a set that does not exist. The
  three are distinct and MUST NOT be collapsed: a refused survey enumerated nothing, a benchmark
  that yielded no candidate still carries its enumeration, and a refused dominance pass may sit
  beside a complete comparison. Where one column has a front and the other does not, the front
  still renders, marked as belonging to one column.

### A regime is a belief, and the screen says so

- **FR-015**: Each column MUST name the regime its answer ran under, from the served manifest.
  The implicit regime MUST render in the served string's own words, never as an absence or a
  blank. Resolving that regime to a scenario has exactly two outcomes the API can produce — the
  implicit regime, which belongs to none, and a regime one or more declared scenarios name. A
  regime nobody declares cannot reach this screen: the answer refuses to load at all. Where
  **several** scenarios declare one regime id, the screen MUST name all of them and state that
  the run's own record does not say which was searched — the engine takes the first scenario id
  in sort order and records only the regime
  (`regime-declared-by-two-scenarios-resolves-by-the-first-id` in `specs/features.toml`).
  Choosing one here would name a belief whose route set may not have been the one searched.
- **FR-016**: Where a column's regime belongs to a declared scenario, the column MUST name that
  scenario and render its transitions as the declaration marks them — an assumption, with the
  transition's own rationale reachable in full behind a disclosure. Eliding that text to a fixed
  length is prohibited (021's rule for long provenance).
- **FR-017**: Where a column runs under a declared scenario's regime, the screen MUST state that
  a scenario switches the route set and not the tax schedule. It is a statement about a known
  gap in this system rather than a figure about the owner's money — the one sentence on this
  screen not taken from a response — and it names
  `martial-law-ends-one-belief-two-places` in `specs/features.toml` as where the gap is recorded.
- **FR-018**: Nothing on this screen may present a scenario's content as observed. A scenario
  carries no source and no verification date by design, and the column head MUST say that this
  is what it carries instead.

### What differs between the two questions

- **FR-019**: The screen MUST name every field on which the two served question records differ,
  taken from the records rather than from their ids or file names.
- **FR-020**: Where the regime is the only differing field, the screen MUST say so — that is the
  case in which the difference between the two fronts is attributable to the belief.
- **FR-021**: Where more than the regime differs, the screen MUST name the other differing fields
  and state that the difference between the fronts is not the regime's alone. It MUST NOT refuse:
  two questions differing in one field are two files and two answers (015), and which field
  differs is the owner's choice.
- **FR-022**: Each column MUST name the question it answered by its declared id and by the file
  that declares it, so a reader can open the difference rather than take the screen's word.

### States, requests, and how it is checked

- **FR-023**: Loading, one column failed and both failed MUST each be a named state. A failed
  column names what failed; the other column renders regardless.
- **FR-024**: Every membership mark MUST be carried in text, not by colour alone, and the two
  columns MUST be navigable and readable in the order a screen reader would take them.
- **FR-025**: The screen MUST issue one answer read per distinct `(question id, as_of)` — two
  where the columns name two questions and **one** where they name the same one, which is what the
  client's own cache produces and what the shipped-root case of FR-027 exercises — plus the
  question and scenario reads its labels are built from. It MUST NOT read the registry (026
  FR-008). This screen doubles a recorded gap rather than closing it: an answer document is 8.0 MB
  on the wire (`the-answer-document-is-too-big-for-a-screen`), and two columns are two of them.
- **FR-026**: Unit tests MUST cover each membership state of FR-010 to FR-012, the horizon
  matching of FR-008, the five-term key equality of FR-009, and the field difference of FR-019 to
  FR-021, over recorded pairs of real served answers.
- **FR-027**: An end-to-end test MUST run against the real API over the shipped data root and
  assert that the rendered membership marks agree with the two populations the API served. Over a
  root declaring one question the determinate case is the same question in both columns, where
  every front member is *in both* and the fronts are non-empty (2, 3 and 10 members at the three
  horizons on 2026-09-07), so the assertion cannot pass vacuously.
- **FR-028**: A contract test MUST assert that a question's declared regime reaches the answer —
  that two questions differing only in their regime are answered under the regimes they name, and
  that the manifest records the regime the run actually searched. The existing coverage that this
  test does **not** duplicate is cited rather than rewritten:
  `tests/contract/test_the_answer_over_http.py::test_the_answer_takes_no_scenario_parameter`
  (the answer takes no `scenario_id`) and
  `tests/contract/test_category_reads.py` (a category read takes one, and an undeclared id is
  `envelopes.ScenarioNotDeclared`).

## Success Criteria *(mandatory)*

- **SC-001**: Given two declared questions and one date, a reader sees both non-dominated sets
  per shared horizon without navigating between them.
- **SC-002**: Every rendered membership mark is reproducible by set operations over the two
  responses, with no third input.
- **SC-003**: A key on one front and absent from the other column's enumeration is
  distinguishable, on the screen, from one the other column dominated.
- **SC-004**: A column under a declared scenario's regime carries the scenario id, the assumption
  mark, the transition's full rationale, and the tax-schedule gap sentence. A column under the
  implicit regime carries none of them.
- **SC-005**: The fields on which the two questions differ are stated on the screen, and the
  screen says whether the regime is the only one.
- **SC-006**: Every figure the screen renders is one of the two responses' own, unchanged but for
  formatting.
- **SC-007**: The screen makes one answer request per distinct `(question id, as_of)` and no
  registry request, verified over the browser's own request log.
- **SC-008**: With one declared question, the entry point states that fact and names what would
  close it, and no control silently does nothing.
- **SC-009**: `src/terezy/` is unchanged by this feature, verified over the branch diff.
- **SC-010**: Every refusal either column served reaches the reader with its reason: no blank, no
  dash, no zero, no omitted row.

## Clarifications

Two are open. Both are the owner's, and neither is a legal, tax or fee value.

### Question 1 — Is there a second question to compare against, and which regime does it name?

**Context**: measurement 3 — one question is declared, so the second column has nothing to point
at; measurement 2 — as `war_end` stands today, comparing under `wartime` produces two identical
answers.

| Option | Answer | Implications |
|--------|--------|--------------|
| A | Declare a second question identical to his but naming `wartime` | One data file. A real second column, honestly reporting *this belief costs this question nothing* — measured, not assumed. |
| B | As A, and declare a regime that also removes `inzhur_direct` | The fronts move, so every membership state is demonstrated over shipped data — but it is a **new belief** about a corridor, and inventing one for him is what this project refuses. |
| C | Declare nothing; ship the entry point's named empty state | Nothing is invented, and the feature is still complete and testable (FR-027's degenerate case is determinate). Machinery, no second column. |

**Recommendation**: **A**, with **C** shipped until he writes it. A needs no belief he does not
already hold — `war_end` is his declaration — and *the war ending changes nothing for these
50 000 hryvnia* is a genuine answer to the words he wrote. B is his to state or not: an
implementer choosing which corridor closes would be inventing the term that decides the answer.

### Question 2 — Under a scenario whose transition also moves the tax schedule, caveat or refuse?

**Context**: FR-017 and `martial-law-ends-one-belief-two-places`. `war_end`'s transition is the
end of martial law, and two military-levy facts hang off that same event. The route set follows
the belief; the tax schedule does not. So one column can assume the war ends for routing and
charge the wartime levy for ever.

| Option | Answer | Implications |
|--------|--------|--------------|
| A | State it as a caveat on the column, in FR-017's words | The comparison exists now, with the gap named where it bites. The tax figures are wrong in a stated direction rather than a hidden one. |
| B | Refuse any column under a scenario declaring a transition | Nothing misleading is shown, and "adverse scenarios" stays unanswered until a schedule keyed by a regime exists — a real modelling feature nobody has specified. |
| C | Caveat, plus a mark on every tax-bearing figure in that column | More honest per figure; costs a mark the client would author itself, which is what the API sending provenance exists to prevent. |

**Recommendation**: **A**. B trades a named gap for an unanswered question, and the gap already
has a recorded remedy. C makes the client author a provenance mark, which is the thing 021 was
built not to do.

## Out of scope

- **New scenarios and new questions.** Both are declarations, both are the owner's, and neither
  is an implementer's to write. This feature reads whatever is declared.
- **The engine-side robust set.** An intersection of the fronts across regimes — *sometimes best*
  versus *never bad* — is a decision-layer step, is required test I7, and belongs beside 019's
  dominance pass rather than on a screen. This feature presses on I7 and closes no part of it.
- **A `scenario_id` parameter on the answer endpoint.** Deliberately absent, pinned by a test:
  adding one would put a caller's belief and the question's declaration in disagreement.
- **The interactive graph** — 026's own deferral, unchanged.
- **Which question the answer screen shows** when several are declared. 026 left it open and this
  feature does not settle it: the comparison route names both of its columns explicitly.
- **Any change to `src/terezy/`.**

## Assumptions

- The comparison is presentation because 015 already decided the shape: one regime per question,
  and a reading across two answers. Making the intersection an engine step would be a new
  decision-layer output.
- 026 has landed: its candidate card, refusal groups, formatting module and figure slot are
  reused rather than rebuilt. This feature adds a second column and a membership mark; it
  restyles nothing.
- The web client stays a client of the published schema and of nothing else. Every type this
  feature narrows on is generated from the OpenAPI document.
- The measurements dated 2026-09-07 were taken over the shipped data root at `as_of` 2026-09-06
  and are stated as of that date. They are why the case that must hold over shipped data is the
  degenerate one.
- Authentication is unchanged: loopback only, one owner (Principle VII).
