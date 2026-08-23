---

description: "Task list for 005-route-diagrams"
---

# Tasks: Route diagrams

**Input**: Design documents from `specs/005-route-diagrams/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md` (D1–D11), `data-model.md`,
`contracts/rendering.md`, `quickstart.md`

**Tests**: required. Principle V is non-negotiable — every behaviour lands with a worked
example, an invariant or a golden, and **the test fails before the implementation exists**
(an `ImportError` counts). Test tasks therefore come first inside every phase.

**Organization**: grouped by user story, in the order plan.md's Phase 2 note fixes —
`numbers.py` and `mermaid.py` first because everything calls them, `marks.py` next, then the
two renderers, then the script, and **the goldens last**, because a golden checked in before
the behaviour is settled trains everyone to regenerate without reading.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 from `spec.md`; setup, foundational and polish tasks carry none

## Path conventions

Single Python project, src layout, layered `cli → api → data → core`. The whole feature is
`src/terezy/api/diagrams/`, one script in `scripts/`, tests under `tests/`. **`src/terezy/core/`
is not touched** — that is FR-020 and Principle III, and `lint-imports` enforces it.

---

## Phase 1: Setup

**Purpose**: the package exists and the layer boundary is proved before anything is built in it.

- [x] T001 Create the package skeleton `src/terezy/api/diagrams/__init__.py` with the module
  docstring only (why the renderer is in `api` — research.md D1) and no public names yet, so
  every test below fails on the name it needs rather than on the import path
- [x] T002 Extend `tests/contract/test_architecture_boundaries.py` with a case asserting
  `terezy.api.diagrams` imports nothing from `terezy.cli`, imports no rendering dependency, and
  that no module under `src/terezy/core/` imports `terezy.api` — the `api → core` direction only
  (Principle III, plan.md constitution check)

**Checkpoint**: `uv run lint-imports` and `uv run pytest -m contract` are green; the package is
an empty, correctly placed shell.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the one number rule, the Mermaid dialect and the mark vocabulary. Everything in
Phases 3–7 calls these; getting them last means rewriting every call site (plan.md Phase 2 note).

**⚠️ CRITICAL**: no user story work begins until this phase is complete.

### Tests first

- [x] T003 [P] Write `tests/contract/test_diagram_one_number_rule.py` asserting: `percent` and
  `amount` render fixed two decimals through one shared private helper; the rule **rounds** and
  the rounding is visible (`0.005` cases stated); `numbers.py`'s executable source contains
  exactly **one** float format spec; and the grep — no `:.Nf`, `round(`, `format(`, `%.Nf` or
  `Decimal` anywhere else in `src/terezy/api/diagrams/`, with a planted-violation positive
  control proving the scan can fail (SC-006, FR-022, research.md D2)
- [x] T004 [P] Write `tests/unit/test_diagram_escaping.py` asserting: SC-008's hostile-name
  battery (double quote, `#`, `|`, `[`, `]`, `<`, `>`, backtick, braces, `-->`, Cyrillic, emoji,
  a newline, a very long name) escapes to output whose structure is intact and whose name is
  displayed intact after entity decoding; node ids are positional `n<k>` and **injective** over a
  list containing `binance-p2p` and `binance_p2p` (research.md D3); a label is never truncated
  (SC-008, SC-001, FR-017, FR-018)
- [x] T005 [P] Write `tests/contract/test_diagram_marks.py` covering the mark vocabulary in
  isolation: the six `Mark` members render pairwise-distinct tokens, an empty mark set renders
  the named clean state rather than an empty space, unsourced renders as itself, and
  unverified-and-stale shows **both** — one never swallows the other (SC-004, FR-012–FR-015)

### Implementation

- [x] T006 `src/terezy/api/diagrams/numbers.py` — `DECIMAL_PLACES`, one private `_fixed`
  helper holding the project's only diagram float format, `percent(fraction) -> str` and
  `amount(Money) -> str`. The module docstring states that the rule **rounds** and that **the
  diagram is therefore not the audit trail**, on the model of the single project tolerance
  (FR-022, research.md D2)
- [x] T007 [P] `src/terezy/api/diagrams/mermaid.py` — the dialect: `flowchart LR`, `escape`
  (numeric character references, `#` first), positional `node_id(index)`, `node`, `edge`,
  `class_def`, and `document`. No venue, provider, route or corridor is named here (Principle II)
- [x] T008 `src/terezy/api/diagrams/marks.py` — the closed `Mark` enum (six members from
  data-model.md), its label tokens, the two named non-mark states (clean, unsourced), the
  `classDef` style-class names, and the synthetic-citation token the declarations already use.
  Marks live in **label text**; styling may only add emphasis (FR-015, research.md D4)
- [x] T009 `src/terezy/api/diagrams/__init__.py` — the shared records: frozen `Diagram`
  (`text`, `kind`, `regime_id`, `mode`), frozen `NothingToDraw` (`reason`, `kind`), and the
  closed `Mode` enum (`TOPOLOGY | DECLARED_FIGURES`). A tagged union, never a `Diagram` with an
  `ok` flag (owner decision D-E, research.md D7)

**Checkpoint**: T003, T004 and T005 pass. The renderers can now be written without inventing a
second way to format a number.

---

## Phase 3: User Story 1 — See the graph that was declared (Priority: P1) 🎯 MVP

**Goal**: the declared registry for one named regime, rendered from the declarations alone.

**Independent test**: load a fixture registry, render the graph, and assert by text over the
whole fixture — not sampled — that every declared venue is a node exactly once and every route
in the regime is edges following its legs in order.

### Tests first

- [x] T010 [P] [US1] Write `tests/contract/test_diagram_modes.py`: the same registry in
  `TOPOLOGY` and in `DECLARED_FIGURES` differs **by figures only** (strip the figure segments
  from the with-figures text and it equals the topology text); each names its mode on the
  diagram itself; **neither** carries a computed ramp cost, verified over every label; every
  diagram names exactly one regime and a merged no-regime graph is not expressible
  (SC-012, SC-009, FR-006, FR-019)
- [x] T011 [P] [US1] Write `tests/unit/test_diagram_graph.py`: SC-001 over a whole fixture —
  every venue a node exactly once, every regime route drawn as edges in leg order, two routes
  between the same pair drawn as two distinct edges, a self-edge drawn and not dropped, an
  isolated venue present, an empty registry and a regime with no routes rendered as an
  explicitly empty diagram that says so under the regime's name (never blank, never an error),
  a regime naming an undeclared route a loud failure, and two venues keyed differently but
  declaring one id a loud failure naming both (SC-001, FR-002, FR-018, edge cases)

### Implementation

- [x] T012 [US1] `src/terezy/api/diagrams/graph.py` — `render_graph`: sorted venues to
  positional nodes, sorted regime routes to edges in leg order, the caption node carrying the
  regime, the mode and the as-of date, the two modes, and the loud failures. Derived entirely
  from the declarations; nothing hand-maintained (FR-002, FR-006, FR-019, research.md D5, D8, D9)
- [x] T013 [US1] Export `render_graph` from `src/terezy/api/diagrams/__init__.py`

**Checkpoint**: US1 is independently verifiable — `uv run pytest -k diagram_graph` and
`-k diagram_modes` are green.

---

## Phase 4: User Story 2 — See the path that was costed (Priority: P1)

**Goal**: one costed ramp result drawn as its path, every figure taken verbatim from the result
through the one rule, refusals drawn as refusals.

**Independent test**: cost a fixture route through feature 002's costing, render it, and check
every label against the result's own figures — same figures, same labels, nothing added.

### Tests first

- [x] T014 [P] [US2] Write `tests/contract/test_diagram_refusals.py`: `RouteUnusable`,
  `ExitCostUnknown` and `NothingComparable` each yield a typed `NothingToDraw` carrying the
  refusal's own reason verbatim — never an empty diagram, never a partial path; and a `RampCost`
  whose `round_trip` is `ExitCostUnknown` renders the inbound path with the *exit cost unknown*
  mark where the exit would be and **no round-trip figure anywhere** in the text; plus the
  registry-graph *no exit declared* mark for a destination nothing exits (SC-010, SC-007,
  FR-005, FR-010, FR-011, research.md D6, D7)
- [x] T015 [P] [US2] Write `tests/unit/test_diagram_path.py`: the drawn legs are exactly the
  legs the result costed, in order; the exit route is drawn as **its own** legs and venues, never
  the inbound reversed; every cost label is explicitly one-way or round-trip; cost and
  spread-over-reference are labelled as themselves and never conflated; a leg with no figure to
  show carries **no number at all**; and every figure in the text equals the result's figure
  through `numbers` (SC-006, FR-007–FR-010)

### Implementation

- [x] T016 [US2] `src/terezy/api/diagrams/path.py` — `render_path`: match on the input union;
  the inbound chain from the route's legs, the declared exit route drawn as itself, the
  route-level figures node with one-way and round-trip named separately, and `NothingToDraw` for
  every refusal. Renders what the type carries **today** — no anticipation of feature 004's
  composed paths (plan.md, "A note on the parallel lane")
- [x] T017 [US2] Export `render_path` from `src/terezy/api/diagrams/__init__.py`

**Checkpoint**: US1 and US2 both work independently.

---

## Phase 5: User Story 3 — Trust the marks (Priority: P2)

**Goal**: the marks a reader has learned to trust on the tables reach the picture, and survive it.

**Independent test**: a fixture registry with one verified value, one unverified, one stale, one
both, one closed route, one destination without an exit and one synthetic entry; render it;
every state visibly distinct in the text **with all styling stripped first**.

### Tests first

- [x] T018 [US3] Extend `tests/contract/test_diagram_marks.py` with the end-to-end half:
  a single fixture carrying all six states renders them pairwise-distinguishable **after every
  `classDef` line and every `:::class` suffix is removed** — a mark carried only by a colour
  fails here; a closed route is present, marked, and distinct from an open one and from one that
  does not exist; 100% of elements depicting figures derived from one unverified input carry the
  unverified mark; and every route shipped in `data/routes/` renders synthetic, because every one
  of them says so in its citation (SC-004, SC-005, FR-004, FR-012–FR-015)

### Implementation

- [x] T019 [US3] Wire the marks through `graph.py` and `path.py`: unverified from `Provenance`,
  stale through the core's own `staleness_of` under each leg's declared kind, synthetic from the
  citation token, closed from the declared status, *no exit declared* computed here from the
  declarations, *exit cost unknown* from the result. Add the `classDef` block as emphasis only

**Checkpoint**: the marks survive a styling strip. This is the test that keeps D4 honest.

---

## Phase 6: User Story 4 — Diff a diagram like a golden file (Priority: P2)

**Goal**: byte-identical output for identical input, and two checked-in artifacts to diff against.

**Independent test**: render the same declarations twice — separate processes, and with the
declaration mappings presented in permuted order — and confirm byte-identity; change one declared
field and confirm the diff is confined to what that field affects.

### Tests first

- [x] T020 [US4] Write `tests/golden/test_diagrams.py`: byte-identity across a **separate
  process** and across permuted input ordering, per mode; a changed declared field produces a
  non-empty diff confined to what it affects; the two checked-in artifacts match today's render;
  a missing artifact is a failure and never a silent regeneration; and the stdout script prints
  **byte-identically** to what the suite regenerates for the same inputs (SC-003, SC-011, FR-016,
  FR-021, research.md D9)

### Implementation

- [x] T021 [US4] `scripts/render_diagram.py` — argument parsing, one call into
  `terezy.api.diagrams`, write to stdout. No file writing, no reports directory, no formatting of
  its own; the only clock in the feature is this script's `--as-of` default, and the resolved
  date is printed on the face of the diagram (FR-021, research.md D11)
- [x] T022 [US4] Generate the golden artifacts **last**, deliberately, and read them before
  committing: `tests/golden/route_graph_wartime.mmd`, `tests/golden/costed_path_p2p.mmd`, and
  — added on the owner's ruling of 2026-08-23 — `tests/golden/route_graph_normalized.mmd`,
  the shipped regime that produces a *no exit declared* mark and declares a premium in basis
  points (SC-011)

**Checkpoint**: `uv run pytest -m golden -k diagram` is green and the artifacts are readable by eye.

---

## Phase 7: User Story 5 — Add a corridor, see it appear (Priority: P3)

**Goal**: the framework claim applied to presentation — a corridor added as data appears with no
source change.

**Independent test**: reuse feature 002's data-only extensibility fixture and assert the
regenerated diagram contains the added venue and route, correctly connected and correctly marked.

### Tests first

- [x] T023 [US5] Write `tests/contract/test_diagram_data_only.py` on the pattern of
  `tests/contract/test_data_only_extensibility.py`: a new provider, venue and corridor written to
  a scratch data root appear in the regenerated diagram with **zero** lines of source changed, and
  no module under `src/terezy/api/diagrams/` names a venue, provider, route or corridor —
  greppable, with a positive control (SC-002, FR-003, Principle II)

### Implementation

- [x] T024 [US5] Fix anything the scan finds. If nothing is found the task is the scan itself;
  a renderer that needed a change here would mean the graph was not derived

**Checkpoint**: all five stories independently functional.

---

## Phase 8: Polish & cross-cutting

- [x] T031 Draw the declared **channel premium** on every `fx` edge in
  `Mode.DECLARED_FIGURES` (owner ruling, 2026-08-23). `render_graph` takes `channels`; both
  declared side forms render in the unit the file used; the applied side carries its own
  source, kind and staleness, so a stale premium on a fresh-fee leg does not render clean.
  Three rules join `numbers.py`, one per new unit, all through the one decimal format (FR-006,
  FR-012, FR-013, FR-022)
- [x] T032 Stop emitting the `closedRoute` `classDef`, which nothing can carry — Mermaid
  applies a class to a node and `CLOSED` only ever lands on an edge. The explanation moves into
  `marks.CLASS_DEFS`; the mark itself stays in the vocabulary and in the label text

- [x] T025 [P] `docs/METHODOLOGY.md` gains a new section: **the** number-rendering rule, stated
  once, with its decimal places and the fact that it **rounds** (and that the diagram is therefore
  not the audit trail), plus the mark vocabulary a diagram uses and what each token claims
  ("documentation is part of the feature")
- [x] T026 [P] Add the feature's rows to §21's "where to look next" table in
  `docs/METHODOLOGY.md`
- [x] T027 Record in `docs/REQUIRED_TESTS.md` that this feature flips **no** row and why — it
  extends E5 and 002's SC-014 into a new surface rather than closing either (spec.md, "Required
  tests this feature closes")
- [x] T028 Flip `005-route-diagrams` to `status = "in-progress"` in `specs/features.toml` in the
  first implementation commit. **Do not flip it to `done`** — the owner reviews and lands
- [x] T029 Run every gate from the worktree and record the numbers:
  `uv run ruff check . && uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports`,
  `uv run python scripts/check_provenance.py`, `uv run pytest --cov`,
  `uv run pytest -m "contract or invariant"`
- [x] T030 Walk `specs/005-route-diagrams/quickstart.md` end to end, including looking at the two
  rendered diagrams with your own eyes, and correct the quickstart where the built commands differ

---

## Dependencies & execution order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Phase 1 — **blocks every story**
- **US1 (Phase 3)** and **US2 (Phase 4)**: depend on Phase 2; independent of each other
- **US3 (Phase 5)**: depends on Phase 2 for the vocabulary and on Phases 3–4 for something to
  mark — its end-to-end half is what makes the marks a testable claim
- **US4 (Phase 6)**: depends on Phases 3–4; the goldens come **last**
- **US5 (Phase 7)**: depends on Phase 3
- **Polish (Phase 8)**: depends on everything

### Within each story

- Tests are written first and **must fail** before the implementation exists
- `numbers.py` and `mermaid.py` before every call site
- `marks.py` before either renderer
- Both renderers before the script; the script before the goldens

### Parallel opportunities

- T003, T004, T005 — three test modules, three files, no shared state
- T007 is parallel with T006 (different modules; `mermaid.py` does not import `numbers.py`)
- T010 and T011 (US1 tests); T014 and T015 (US2 tests)
- T025 and T026 (documentation)

---

## Implementation strategy

### MVP (US1 only)

1. Phase 1, then Phase 2 — the rule, the dialect, the vocabulary
2. Phase 3 — `render_graph`
3. **Stop and look at the output with your own eyes.** This is a feature whose defects are
   visible, and the fastest review is the picture, before any assertion runs

### Incremental delivery

Phase 2 → US1 → US2 → US3 → US4 → US5 → polish. Commit at every green checkpoint through the
`/commit` skill, ticking these boxes in the same commit as the work.

---

## Notes

- **Node ids are positional.** Never derived from a declared id — sanitising `binance-p2p` and
  `binance_p2p` into one identifier merges two venues invisibly (research.md D3, FR-018)
- **One number rule**, and a grep proving there is no second (research.md D2, FR-022)
- **Marks live in label text**; styling adds emphasis only (research.md D4, FR-015)
- **A refusal is a typed `NothingToDraw`**, never an empty diagram (research.md D7, FR-011)
- **Do not import `core.routes.coverage`** and do not anticipate composed paths (research.md D6)
- `src/terezy/core/` is untouched. If a figure is awkward to render, the fix is in the renderer
