# Feature Specification: Route diagrams

**Feature Directory**: `specs/005-route-diagrams`

**Feature Branch**: none — this repo works on `main` by design

**Created**: 2026-08-22

**Status**: Ready for planning — all clarifications resolved 2026-08-22

**Input**: Route diagrams — the declared route graph and any costed path rendered as
Mermaid text, so a human and a coding agent can see the graph they are reasoning about.

---

## Why this feature exists

Feature 002 made the route registry real: venues, routes, legs, channels and regimes are
declared data, and a costed result attributes every hryvnia it charges to a leg and a
component. It also made the registry a **graph** — venues are nodes, routes and their
legs are edges — and then left everyone who debugs it to reconstruct that graph in their
head from TOML tables. The owner reading a comparison, an agent chasing a
non-chaining-leg load failure, and a reviewer checking that a declared corridor actually
connects what it claims to connect are all doing the same mental rendering, each time,
each slightly differently.

This feature does the rendering once, mechanically, and honestly: given the loaded
declarations, produce a Mermaid diagram of the route graph; given a costed ramp result,
produce a Mermaid diagram of that one path with its per-leg cost attribution on the
edges.

Mermaid, because it is plain text. Text is diffable, embeddable in markdown and test
artifacts, and renderable by every tool the owner and the agents already use — and text
output needs no dependency, no network, and no UI. The web interface remains
deliberately deferred (owner decision D-B); this feature produces text, not a surface.
It is expected to be consumed in three places today: by the owner reading a report, by
agents debugging route declarations, and by golden tests as checked-in artifacts.

The constraint that shapes everything below: **the diagram must be as honest as the
numbers.** A diagram that renders an incomparable destination indistinguishably from a
comparable one would be the visual form of the mislabelled figure this project exists to
refuse.

Two adjacent features are being specified in parallel and are deliberately not depended
on here: a parallel feature audits which links are *missing* from the registry, and
another parallel feature chains declared routes into composed paths. This feature
renders what is declared and what has been costed; it neither audits coverage nor
composes anything. Where their results later exist as the same declared records and
result types, they render through the same door — but nothing here waits on their
unfinished decisions.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the graph that was declared (Priority: P1)

An agent (or the owner) loads the route declarations and asks for the picture: every
venue as a node, every declared route as edges along its legs, for one named regime. The
diagram is derived from the declarations — nobody draws it, nobody maintains it, and it
cannot drift from the data because it has no existence apart from the data.

**Why this priority**: this is the feature's reason to exist. The registry is already a
graph; the only question is whether humans keep re-deriving it by hand. Every debugging
session over feature 002's declarations starts with this picture.

**Independent Test**: load a declaration set with a handful of venues and routes, render
the graph, and check by eye and by text assertion that every declared venue and route
appears, connected exactly as declared, under the regime's name.

**Acceptance Scenarios**:

1. **Given** a loaded declaration set and a named regime, **When** the route graph is
   rendered, **Then** the output is Mermaid text in which every venue declared in that
   regime appears exactly once as a node and every route appears as edges following its
   legs in order.
2. **Given** a new venue and route added purely as declaration data, **When** the graph
   is re-rendered, **Then** they appear in the diagram with zero source-code changes —
   the diagram is derived, never hand-maintained.
3. **Given** a route declared closed, **When** the graph is rendered, **Then** the route
   is visibly present and visibly closed — distinct both from an open route and from a
   route that does not exist.
4. **Given** a destination with no declared exit route, **When** the graph is rendered,
   **Then** the missing exit is shown as an explicitly absent edge — a visible mark
   saying *no exit declared*, not an omission — and the destination is visibly not
   comparison-ready.
5. **Given** two routes between the same pair of venues, **When** the graph is rendered,
   **Then** both appear as distinct edges, each carrying its route identity.

---

### User Story 2 - See the path that was costed (Priority: P1)

The owner has a costed ramp result — an amount, a stream, a route, and a per-leg cost
attribution — and asks to see it as a picture: the path from the stream's arrival venue
to the destination, one edge per leg, each edge labelled with what that leg charged and
what state that figure is in.

**Why this priority**: equal-highest with Story 1, because this is where the numbers
meet the picture. Feature 002's central sentence — "most of the gap is the ramp, not the
asset" — is a sentence about *which edge is expensive*, and an edge-labelled path is
that sentence drawn.

**Independent Test**: cost a known fixture route through feature 002's costing, render
the resulting path, and check every edge label against the result's own per-leg
attribution — same figures, same labels, nothing added.

**Acceptance Scenarios**:

1. **Given** a costed ramp result, **When** its path is rendered, **Then** the diagram
   shows exactly the legs the result costed, in order, and every cost figure on an edge
   equals a figure the result itself carries — the diagram never computes, rounds, or
   invents a number of its own.
2. **Given** any cost label on an edge, **When** it is rendered, **Then** it is
   explicitly named one-way or round-trip, and a cost is never conflated with a
   spread-over-reference — the two figures feature 002's FR-004 separates stay separate
   in the picture.
3. **Given** a leg with no declared or computed figure to show, **When** it is rendered,
   **Then** its edge shows no number at all — an edge either shows a figure with its
   provenance state or shows none.
4. **Given** a result whose round trip rests on a separately declared exit route, **When**
   the path is rendered, **Then** the exit route is drawn as itself — its own legs, its
   own venues — never as the inbound path reversed.
5. **Given** a destination whose result is *exit cost unknown*, **When** the path is
   rendered, **Then** the diagram says so where the exit would be, and no round-trip
   figure appears anywhere on it.

---

### User Story 3 - Trust the marks (Priority: P2)

Whatever the diagram shows, it carries the marks the figures carry. A reader who has
learned to trust the engine's unverified and stale marks must be able to extend exactly
that trust to the picture, because the picture will travel further than the tables — it
will be pasted into reports and read by people who never open the TOML.

**Why this priority**: honesty marks are the project's identity (Principle I), but they
are only *this* feature's second story because Stories 1 and 2 define what exists for
the marks to sit on. A diagram with wrong marks is worse than no diagram; a diagram with
no content has nothing to mark.

**Independent Test**: build a fixture registry containing one verified value, one
unverified value, one stale value, one closed route, one destination without an exit,
and one synthetic entry; render it; confirm each state is visibly distinct in the output
text and in the rendered picture.

**Acceptance Scenarios**:

1. **Given** a route resting on any unverified value, **When** it is rendered, **Then**
   the route is visibly marked unverified — the mark that propagates through every
   derived figure propagates into the diagram too.
2. **Given** a value aged past its kind's staleness threshold, **When** anything derived
   from it is rendered, **Then** it is visibly marked stale, and stale is
   distinguishable from unverified.
3. **Given** a value that is both unverified and stale, **When** it is rendered, **Then**
   both marks appear — one never swallows the other.
4. **Given** a synthetic fixture in the rendered data, **When** it appears in a diagram,
   **Then** it is labelled synthetic, so a picture built on test data can never be
   mistaken for a picture of the owner's actual options.
5. **Given** all of the mark states above in one diagram, **When** a reader looks at the
   rendered picture — not the source text — **Then** every state is distinguishable:
   the marks are encoded in visible label text and styling, never only in comments the
   renderer throws away.

---

### User Story 4 - Diff a diagram like a golden file (Priority: P2)

An agent regenerates the diagram after changing a declaration and reads the diff. If the
graph changed, the diff shows it; if the graph did not change, the diff is empty. The
diagram is a golden artifact, and it earns that status the way every golden file does:
by being byte-identical for identical inputs.

**Why this priority**: this is what makes the diagram a *tool* rather than an
illustration. A checked-in diagram whose text churns on every run cannot sit in
`tests/golden/`, and a diagram that cannot be diffed answers no question an agent has.

**Independent Test**: render the same declaration set twice — separate runs, and with
the declaration files presented in permuted order — and confirm the outputs are
byte-identical; change one declared field and confirm the diff touches only what that
field affects.

**Acceptance Scenarios**:

1. **Given** the same declarations, **When** the diagram is rendered twice in separate
   runs, **Then** the two outputs are byte-identical — stable ordering, no timestamps,
   no run-dependent identifiers.
2. **Given** the same declarations loaded from files presented in a different order,
   **When** the diagram is rendered, **Then** the output is byte-identical to the
   original — ordering comes from the data's own identity, not from load order.
3. **Given** one declared value changed, **When** the diagram is regenerated and
   diffed against the checked-in artifact, **Then** the diff is non-empty and confined
   to the parts of the diagram that value affects — a diff on a golden diagram means
   the graph actually changed.

---

### User Story 5 - Add a corridor, see it appear (Priority: P3)

A new bank, provider or corridor is added the feature-002 way — a declaration file — and
the diagram picks it up with no code change, exactly as the costing does.

**Why this priority**: the framework claim (Principle II) applied to presentation. P3
because it is verified rather than built: if Stories 1–4 are implemented by deriving
everything from the declarations, this property falls out, and the test exists to keep
it true.

**Independent Test**: reuse feature 002's data-only extensibility fixture — a new
provider, venue and corridor added purely as data — and assert the regenerated diagram
contains them, with the whole check performed against the diagram text.

**Acceptance Scenarios**:

1. **Given** a route registry extended purely by declaration files, **When** the graph
   is re-rendered, **Then** every added venue and route appears, correctly connected
   and correctly marked, with zero lines of source code changed.

---

### Edge Cases

- **An empty registry, or a regime with no routes** — rendered as an explicitly empty
  diagram that says so under the regime's name, never a blank output indistinguishable
  from a failed render, and never an error.
- **A venue or route name containing Mermaid-significant characters** (quotes, brackets,
  pipes, arrows, non-Latin text — Ukrainian names are the normal case, not the edge) —
  escaped so the output remains valid Mermaid; a name must never corrupt the diagram or
  leak into its structure.
- **Two distinct venues whose names collide after being made into node identifiers** —
  a loud failure naming both, never two venues silently merged into one node.
- **A route from a venue to itself** (a conversion that starts and ends at the same
  venue) — rendered as a visible self-edge, not dropped as degenerate.
- **A refusal instead of a result** — a route unusable for the stated amount, or a
  ranking with nothing comparable — is not a path and is never drawn as one. Asked to
  render a refusal, the renderer produces a typed "nothing to draw" carrying the
  refusal's reason; it never draws a partial path or an empty picture.
- **A very long label** — never silently truncated: truncation is exactly how a mark
  falls off the end of a label. Layout consequences belong to Mermaid (out of scope);
  label integrity belongs to this feature.
- **A diagram asked for a regime that does not exist** — a loud, named failure, not an
  empty diagram.
- **A costed path whose route has since been redeclared** — the path diagram renders the
  result it was given, which carries what was costed; it never re-reads the registry to
  "freshen" a picture of a past result.

## Requirements *(mandatory)*

### Functional Requirements

**Scope of the first slice**

- **FR-001**: The system MUST render two kinds of diagram and nothing else: the declared
  route graph for one named regime, and the path of one costed ramp result. **Both are
  in the first slice** (owner decision, 2026-08-22). The per-regime side-by-side pair —
  wartime and normalized rendered together for comparison — is **deferred**, not asked
  for now; every diagram still shows exactly one named regime per FR-019.

**The route graph**

- **FR-002**: The route graph MUST be derived entirely from the loaded declarations:
  venues as nodes, routes as edges following their legs. No hand-maintained content of
  any kind — a diagram element with no declaration behind it is a defect.
- **FR-003**: Adding a venue, provider, route or corridor as declaration data MUST
  appear in the re-rendered diagram with zero source-code changes (Principle II applied
  to presentation).
- **FR-004**: A closed route MUST render visibly closed — present, marked, and distinct
  both from an open route and from a route that was never declared. Closed and
  nonexistent are different facts and MUST look different.
- **FR-005**: A destination with no declared exit route MUST render as visibly not
  comparison-ready: the missing exit shown as an explicitly absent edge — a visible
  *no exit declared* mark — never omitted. This is feature 002's FR-030 made visual: a
  diagram in which an incomparable destination looks like a comparable one is the
  mislabelled figure in picture form.
- **FR-006**: The registry-wide graph MUST be renderable in **two declared modes**,
  selectable by the caller (owner decision, 2026-08-22):
  - **topology-only** — no numbers at all, a pure picture of what connects to what;
  - **with declared figures** — *declared* per-leg figures (fees, premiums) on edges,
    each carrying its provenance state.

  In **either** mode, a **computed ramp cost MUST NEVER appear on the registry graph**:
  those figures exist only per `(destination × stream × route)`, which a registry graph
  does not name, and placing one there would be feature 002's FR-008 violated in
  picture form. The mode chosen MUST be visible on the diagram itself, so a numberless
  picture can never be mistaken for "zero fees". Determinism (FR-016) applies per mode:
  same declarations and same mode yield byte-identical text.

**The costed path**

- **FR-007**: Given one costed ramp result, the system MUST render that path: the legs
  the result costed, in order, from the stream's arrival venue to the destination, with
  per-leg cost attribution on the edges.
- **FR-008**: Every figure in a diagram MUST be a figure its input already carries. The
  renderer MUST NOT compute, derive, aggregate, round differently, or otherwise invent a
  number; the only transformation it may apply is the single number-rendering rule of
  FR-022. An edge either shows a declared or computed figure with its provenance state,
  or shows none.
- **FR-009**: Cost labels MUST follow the project's labelling rules without exception:
  one-way and round-trip explicitly named wherever a cost appears; cost and
  spread-over-reference never conflated and each labelled as itself where both appear.
- **FR-010**: A round trip MUST be drawn from the separately declared exit route — its
  own legs and venues — never as the inbound path reversed. A result of *exit cost
  unknown* MUST render as exactly that, in the place the exit would occupy, with no
  round-trip figure anywhere in the diagram.
- **FR-011**: A refusal (an unusable route, nothing comparable) MUST NOT be drawn as a
  path. The renderer's answer to a refusal is a typed *nothing to draw* carrying the
  refusal's reason — never a partial path, never a silently empty diagram.

**Honesty marks**

- **FR-012**: The unverified mark MUST propagate into the diagram: any route, edge or
  label resting on an unverified value renders visibly marked, exactly as the derived
  figures it depicts are marked.
- **FR-013**: Staleness MUST surface in the diagram under the same per-kind thresholds
  feature 002 declares (its FR-025/FR-028). Stale MUST be visually distinguishable from
  unverified, and a value that is both MUST show both marks.
- **FR-014**: A synthetic fixture appearing in any diagram MUST be labelled synthetic,
  so a picture of test data can never pass as a picture of the owner's actual options.
- **FR-015**: Every mark MUST survive rendering: marks are encoded in visible label text
  and styling that Mermaid actually displays, never only in source-text comments or
  conventions a renderer discards. The five states — open/verified, unverified, stale,
  closed, no-exit-declared — plus synthetic MUST be pairwise distinguishable in the
  rendered picture.

**Determinism and validity**

- **FR-016**: Same declarations — and, for the registry graph, the same requested mode
  (FR-006) — MUST yield byte-identical Mermaid text: stable ordering derived from the
  data's own identity (never from load order, hash order or insertion order), no
  timestamps, no run-dependent identifiers. This is what qualifies a diagram to be a
  golden artifact.
- **FR-017**: The output MUST be syntactically valid Mermaid. Names and labels MUST be
  escaped such that no declared string — including quotes, brackets, arrows and
  non-Latin text — can corrupt the diagram's structure or leak content into it.
- **FR-018**: Distinct declared entities MUST remain distinct in the diagram. If
  identifier derivation would collide two venues or two routes into one element, the
  render fails loudly naming both — it never silently merges them.
- **FR-022**: ⚙ **Added on external review.** There MUST be exactly **one** defined,
  documented rule for rendering a number into a diagram label, defined in one place and
  used everywhere a figure appears — on the model of the single project tolerance
  (Principle IV). Every figure on every diagram is the input's figure rendered through
  that rule, never a second ad-hoc formatting. The review found the gap: results carry
  floats, the project's canonical float form is unreadable hexadecimal, and no
  human-readable decimal rendering rule existed anywhere — so "the diagram shows the
  result's figure" was undefined as written. The rule's content (decimal places and the
  like) is an implementer choice at planning; its **existence, singularity and
  documentation** are required here. A second rendering rule, or an inline format at a
  call site, is a defect.

**Regimes**

- **FR-019**: A diagram MUST show one named regime, with the regime's name in the
  diagram — or show the transition between regimes explicitly, with the transition date
  stated as an assumption (feature 002's FR-020). A merged graph that exists under no
  regime MUST NOT be producible.

**Boundaries and consumption**

- **FR-020**: Rendering is presentation. The diagram generator consumes the same
  declared records and result types everything else consumes — no parallel data model,
  no independent reading or reinterpretation of declaration files — and it lives outside
  the pure core, which neither formats nor renders (Principle III). Rendering MUST NOT
  change, and MUST NOT be able to change, any computed figure.
- **FR-021**: The generated text MUST land in exactly two places (owner decision,
  2026-08-22): **golden test artifacts**, checked in and regenerated by the golden
  suite; and **a small script that prints a requested diagram to stdout on demand**.
  No reports directory. This is a deliberately minimal delivery surface, recorded as
  such against owner decision D-B: the script is a developer and debugging tool, not a
  UI, and choosing a real surface remains deferred exactly as D-B states.

### Key Entities

- **Route graph diagram** — a Mermaid text document depicting one named regime's
  declared registry: venues as nodes, routes as edges along their legs, with status and
  honesty marks. Wholly derived; has no existence apart from the declarations.
- **Costed-path diagram** — a Mermaid text document depicting one costed ramp result:
  the inbound legs, the separately declared exit legs (or the *exit cost unknown* mark),
  per-leg attribution on the edges, every figure taken verbatim from the result.
- **Honesty mark** — the visual encoding of a figure's or route's epistemic state:
  unverified, stale, closed, no-exit-declared, synthetic. Carried in rendered label text
  and styling, pairwise distinguishable, never comment-only.
- **Ordering rule** — the deterministic identity-derived ordering of nodes, edges and
  labels that makes equal inputs produce byte-equal text. Part of the diagram's
  contract, because golden status depends on it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a fixture registry, every declared venue and route appears in the
  rendered graph exactly once, connected as declared — verified by text assertion over
  the full fixture, not sampled. (FR-002)
- **SC-002**: Feature 002's data-only extensibility fixture — a new provider, venue and
  corridor added purely as data — appears in the regenerated diagram with zero lines of
  source code changed. (FR-003)
- **SC-003**: Rendering the same declarations twice, across separate runs and with
  declaration files presented in permuted order, produces byte-identical output;
  changing one declared field produces a diff confined to what that field affects.
  (FR-016)
- **SC-004**: A fixture containing all six mark states — open/verified, unverified,
  stale, unverified-and-stale, closed, no-exit-declared — plus a synthetic entry renders
  with every state pairwise distinguishable in displayed text and styling, checked
  against the rendered output's visible content, not against comments. (FR-004, FR-005,
  FR-012 through FR-015)
- **SC-005**: With one route input left unverified, 100% of diagram elements depicting
  figures derived from it carry the unverified mark — the same propagation feature 002's
  SC-012 asserts for numbers, asserted for the picture. (FR-012)
- **SC-006**: Every figure on a diagram equals the input's figure **rendered through
  the single documented number-rendering rule** — asserted by construction against that
  one rule, with no second ad-hoc formatting anywhere — and every cost figure is
  explicitly labelled one-way or round-trip; cost and spread-over-reference never share
  a label. Verified across every label on the fixture diagrams, not sampled. (FR-008,
  FR-009, FR-022)
- **SC-007**: A destination with no declared exit renders the explicit *no exit
  declared* mark and no round-trip figure; the costed-path rendering of its *exit cost
  unknown* result shows the same. No fixture produces a diagram where such a destination
  is indistinguishable from a comparison-ready one. (FR-005, FR-010)
- **SC-008**: A battery of hostile names — quotes, brackets, pipes, arrows, Ukrainian
  text, emoji — renders to output that remains syntactically valid Mermaid with every
  name displayed intact; an engineered identifier collision between two distinct venues
  fails loudly naming both. (FR-017, FR-018)
- **SC-009**: Every produced diagram names exactly one regime, or shows a transition
  with its date stated as an assumption; no fixture, however constructed, yields a
  merged no-regime graph. (FR-019)
- **SC-010**: A refusal rendered yields a typed *nothing to draw* carrying the refusal's
  reason; zero fixtures produce a partial path or a silently empty diagram from a
  refusal. (FR-011)
- **SC-011**: At least one route-graph diagram and one costed-path diagram are
  checked in as golden artifacts and regenerated in the golden suite; the suite fails on
  any byte of drift. The stdout script prints a requested diagram byte-identical to what
  the golden suite regenerates for the same inputs. (FR-016, FR-021)
- **SC-012**: The same registry rendered in topology-only mode and in
  with-declared-figures mode produces two diagrams, each naming its mode visibly on the
  diagram itself, each byte-identical across repeated renders in that mode; the
  topology-only diagram contains no figures, the with-figures diagram carries declared
  per-leg figures with their provenance states, and **neither contains a computed ramp
  cost** — verified over every label, not sampled. (FR-006, FR-016)

## Assumptions

- **Feature 002's declared records and result types are the sole inputs.** The renderer
  draws what the registry declares and what the costing computed — venues, routes, legs,
  channels, regimes, ramp costs, refusals — through the same types every other consumer
  uses. No new declared domain knowledge enters with this feature; every mark derives
  from provenance and status fields that already exist.
- **Parallel features are referenced, not depended on.** A parallel feature audits
  missing links in the registry; another chains declared routes into composed paths.
  Nothing in this specification waits on their decisions. If a composed path later
  exists as the same kind of costed result, it renders through the same path renderer —
  an expectation, not a dependency. One consequence of that parallel feature's own
  clarifications is recorded here: composed paths are visibly distinct candidates, so
  when such results exist, their composed nature is one more mark the diagram must
  carry — still with no dependency on that feature's artifacts.
- **Mermaid is the mandated output language; the dialect within Mermaid is an
  implementer choice.** Which Mermaid diagram form to emit, and which of its styling
  facilities encode the marks, is decided at planning — what is fixed here is plain
  text, validity, determinism, and mark visibility.
- **"Renders correctly" is verified by a human once per golden artifact, and by text
  forever after.** Tests never reach the network and never rasterise; they assert on
  the Mermaid text. The human check that a checked-in artifact actually displays — and
  that the marks are distinguishable to a reader — happens when the artifact is created
  or changed, and the byte-identity guarantee makes that check durable.
- **Synthetic labelling keys off the fixtures' own provenance.** Test fixtures already
  declare themselves synthetic in their provenance fields; the diagram surfaces that
  declaration rather than inventing a detection mechanism.
- **One owner, no authentication, and a deliberately minimal delivery surface** — as in
  features 001 and 002, plus the two landing places FR-021 names: golden artifacts and
  a stdout script. The script is a developer and debugging tool, not a UI; decision D-B
  stands untouched.

## Clarifications resolved

All three answered by the owner on 2026-08-22.

| # | Question | Decision | Where it landed |
|---|---|---|---|
| 1 | Which diagram kinds are in the first slice — registry graph, costed path, both, and is a per-regime side-by-side pair wanted? | **Both kinds**; the side-by-side pair is deferred — one named regime per diagram stands | FR-001, FR-019 |
| 2 | Do cost figures appear on the registry-wide graph at all, or only on single-path renderings? | **Two selectable declared modes**: topology-only, and with declared per-leg figures carrying provenance; the mode is visible on the diagram; a computed ramp cost never appears in either mode | FR-006, SC-012 |
| 3 | Where does the generated text land — stdout, a reports directory, golden test artifacts only, or a combination? | **Golden artifacts plus a stdout script**; no reports directory; recorded as a deliberately minimal surface against decision D-B | FR-021, SC-011 |

### Gap found on external review

**SC-006's "byte for byte" claim was undefined as written**, and was fixed rather than
softened. Results carry floats; the project's canonical float form is unreadable
hexadecimal; no human-readable decimal rendering rule existed anywhere — so the criterion
compared diagram text against a form nobody had defined. The fix is FR-022: exactly one
documented number-rendering rule for diagram labels, defined in one place on the model of
the single project tolerance, with SC-006 restated as equality *through that rule*. The
rule's content is an implementer choice at planning; its existence, singularity and
documentation are the requirement.

## Required tests this feature closes

No open row in `docs/REQUIRED_TESTS.md` names a diagram, so this feature closes none —
stated plainly rather than stretched. It extends two standing obligations into a new
surface, and its tests assert that extension:

| Standing obligation | What this feature adds |
|---|---|
| **E5** — empty `verified_on` marks the figure and everything derived from it | The mark propagates into the rendered diagram, not only into tables (SC-005) |
| Feature 002 **SC-014** — no exit route means no round-trip figure, excluded from comparison | The exclusion is *visible*: an explicitly absent edge, never an omission (SC-007) |

## Out of scope

Named explicitly so the plan does not drift:

- **Any web or interactive UI.** Owner decision D-B stands; this feature produces text.
- **Any image rasterisation.** No PNG, no SVG generation, no rendering pipeline; the
  consumer's own tools render the Mermaid.
- **Graph layout tuning beyond what Mermaid does itself.** Where Mermaid places a node
  is Mermaid's business; this feature owns content, marks and determinism, not
  aesthetics.
- **Live data.** Declared observations and computed results only, as in feature 002.
- **New instruments**, and any change to how routes are declared or costed.
- **Diagrams of anything other than the route graph and costed paths.** Ledger and
  schedule visualisation is a separate later feature, as is any waterfall or
  tax-breakdown picture.
- **Round-tripping.** Mermaid text is an output, never an input: no parsing diagrams
  back into declarations, no editing the graph through the picture.
- **Coverage auditing and path composition** — each is a parallel feature; this one
  renders, and only renders, what is declared and what was costed.
