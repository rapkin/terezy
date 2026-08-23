# Implementation Plan: Route diagrams

**Feature**: `005-route-diagrams` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-route-diagrams/spec.md`

**Branch**: `feat/005-route-diagrams` in `.claude/worktrees/005-route-diagrams`, landing on
`main` by a `--no-ff` merge after a clean review pass (`specs/README.md` §4–5)

## Summary

Render the declared route graph, and any costed path, as Mermaid text — so the graph
everyone currently reconstructs in their head from TOML tables gets reconstructed once,
mechanically, and identically for everyone.

The technical shape, decided in [research.md](./research.md): the renderer is a package of
free functions in **`api`**, because the core neither formats nor rounds and
`.importlinter` enforces it. It consumes the records everything else consumes — no parallel
data model, no second reading of the declaration files — so a diagram cannot drift from the
numbers it depicts.

Three decisions do the real work. **One number rule**, in one module, on the model of the
single project tolerance, because the review found that "the diagram shows the result's
figure" was undefined when the canonical float form is hexadecimal — and a contract test
greps for a second one. **Marks live in label text**, never only in styling, because a mark
carried by a colour is lost the moment the text is diffed or read as a golden file. And
**node ids are positional**, not derived from declared ids, because sanitising
`binance-p2p` and `binance_p2p` into one safe identifier merges two venues invisibly —
FR-018 violated in the one way nobody would notice.

Deliberately not depended on: features 003 and 004, landing in parallel. The *no exit
declared* mark is computed here from the declarations, which is a smaller question than the
audit with the same answer.

## Technical Context

**Language/Version**: Python 3.13; CI matrix 3.12 / 3.13 / 3.14

**Primary Dependencies**: **none new.** The Mermaid text is a few kinds of line, written by
hand. A rendering dependency would put a third party between a declaration and its picture
and make the escaping someone else's semantics.

**Storage**: none. The output lands in exactly two places (FR-021): golden artifacts under
`tests/golden/`, and stdout from a small script. No reports directory.

**Testing**: pytest. Golden files for the two diagram kinds; contract tests for mark
survival with styling stripped, for the single-number-rule grep, and for hostile-name
escaping; determinism asserted across separate processes.

**Target Platform**: library plus one developer script. No UI — owner decision D-B stands,
and this feature is deliberately not a step toward one.

**Project Type**: single Python library, src layout, layered `cli → api → data → core`.
This is the first feature to put anything substantial in `api`.

**Performance Goals**: none. A few dozen nodes and edges.

**Constraints**: `core` untouched and unimportable-from; every figure is the input's figure
through one rule; byte-identical output for identical input; valid Mermaid under hostile
names; no dependency that phones home.

**Scale/Scope**: 1 new `api` package (4 modules), 1 new script, ~6 test modules, 2 golden
artifacts. No change to `core`, no change to `data`, no new declaration.

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design.*

| Principle | Gate | Verdict |
|---|---|---|
| **I — Honesty over precision** | No figure more confident than its inputs; degraded outcomes typed | **PASS, and the feature is the principle applied to pictures.** A diagram where an incomparable destination looks comparable is the mislabelled figure in visual form, and FR-004/FR-005/FR-010 refuse each way that could happen. A refusal renders as a typed `NothingToDraw` carrying its reason, never as an empty diagram (defect B10 in its visual form). |
| **II — Framework, not script** | Data-only extensibility | **PASS.** The graph is derived; a venue or route added as data appears with zero source changes, which is SC-002 reusing 002's own extensibility fixture. Nothing about a specific venue, provider or corridor is named in the renderer. |
| **III — Pure deterministic core** | No I/O, no clock; core does not format | **PASS, and this feature is where the boundary earns its keep.** The renderer is in `api` because `core` may not format — and the first instinct when a figure is awkward will be a helper in `core`. `lint-imports` refuses it. Output is byte-identical for identical input, which is determinism made checkable by diff. |
| **IV — Reliability through contracts** | Property-based invariants; one rule; explicit failure | **PASS.** FR-022's single number rule is the tolerance discipline applied to formatting: defined once, imported everywhere, a second one is a defect and a grep proves there is none. Failure is `Diagram \| NothingToDraw`, a union matched on. |
| **V — Test-first** | Worked example, invariant or golden per behaviour; no network | **PASS.** Golden artifacts are the natural form here and FR-021 makes them a delivery target rather than only a test device. Hostile names and mark survival are contract tests; determinism runs across processes. |
| **VI — Model the whole tuple** | Round-trip not one-way; costs never per destination | **PASS.** FR-009 puts 002's labelling rules on every edge, and FR-006 forbids a computed ramp cost on a registry graph in **either** mode — because such a cost exists only per `(destination × stream × route)`, which a registry graph does not name. That is FR-008 of 002 defended in a place nobody would have thought to defend it. |
| **Engineering Standards — functional style (D-E)** | Free functions over frozen records; closed enums; tagged unions | **PASS.** `render_graph` and `render_path` are functions; `Mode` and `Mark` are closed enums; the return is a union, not a `Diagram` with an `ok` flag. |
| **VII — Owner-scoped and private** | No telemetry, no phone-home dependency | **PASS, and notably so.** Zero new dependencies, text output only, no network, no CDN, no fonts fetched. Rendering happens in whatever tool the reader already has. |

**No violations requiring justification.** Two design costs are recorded in Complexity
Tracking; both are trades taken deliberately.

### Post-Phase-1 re-evaluation

Re-checked after the design artifacts. No verdict changed. Two things the design surfaced:

- **"Distinct entities stay distinct" and "valid Mermaid under hostile names" are the same
  requirement pulling in opposite directions**, and only positional node ids satisfy both.
  Any scheme that derives the id from the declared id has to sanitise, and sanitising is
  exactly a non-injective map — two venues become one node, the diagram is wrong, and
  nothing in the output says so. This was the single most consequential decision in the
  feature and it is not visible anywhere in the spec's text.
- **FR-022's rule had to be allowed to round, and that fact had to be written down.** FR-008
  forbids the renderer to "round differently", which reads as forbidding rounding until you
  notice the canonical float form is hexadecimal. The rule rounds, the diagram is therefore
  not the audit trail, and the module docstring says so — otherwise the next contributor
  adds a third decimal at one call site and calls it a fix.

## Project Structure

### Documentation (this feature)

```text
specs/005-route-diagrams/
├── spec.md              # Feature specification (22 FRs, 12 SCs, 2 clarifications + 1 review finding)
├── plan.md              # This file
├── research.md          # Phase 0 — eleven decisions with rationale
├── data-model.md        # Phase 1 — records, the number rule, the node-identity rule
├── quickstart.md        # Phase 1 — how to verify, starting with your own eyes
├── contracts/
│   └── rendering.md     # render_graph / render_path, guarantees G1–G14, delivery surface
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source code

```text
src/terezy/api/
└── diagrams/                           NEW — the whole feature
    ├── __init__.py                     the two public functions and the result types
    ├── numbers.py                      THE number-rendering rule, and nothing else
    ├── marks.py                        the mark vocabulary and its label tokens
    ├── mermaid.py                      node ids, escaping, the dialect
    ├── graph.py                        the declared route graph, two modes
    └── path.py                         one costed path, and refusals drawn as refusals

scripts/render_diagram.py               NEW — argument parsing, one call, stdout

src/terezy/core/                        UNTOUCHED — deliberately
```

### Tests

```text
tests/golden/
├── route_graph_wartime.mmd             SC-011 — checked-in artifact
├── costed_path_p2p.mmd                 SC-011 — checked-in artifact
└── test_diagrams.py                    SC-003, SC-011 — byte-identical across processes

tests/contract/
├── test_diagram_marks.py               SC-004, SC-005 — six states, styling stripped first
├── test_diagram_one_number_rule.py     SC-006 — the rule, and the grep for a second one
├── test_diagram_modes.py               SC-012, SC-009 — modes differ by figures only; one regime
├── test_diagram_refusals.py            SC-010, SC-007 — NothingToDraw; the no-exit mark
└── test_diagram_data_only.py           SC-002 — 002's extensibility fixture, re-used

tests/unit/
└── test_diagram_escaping.py            SC-008, SC-001 — hostile names, injective node ids
```

**Structure Decision**: a new `api.diagrams` package — the first substantial inhabitant of
the `api` layer — one script beside `scripts/check_provenance.py`, and `core` untouched.
No change to `.importlinter`: the existing layer contract already permits `api → core` and
forbids the reverse, which is exactly the boundary this feature needs.

## Complexity Tracking

| Design cost | Why accepted | Alternative rejected because |
|---|---|---|
| Positional node ids make the raw Mermaid text less readable to a human reading the source | Injective by construction; hostile names become a labelling problem, never an identity problem | Deriving ids from declared ids requires sanitising, which merges `binance-p2p` and `binance_p2p` into one node — FR-018 violated with nothing in the output to say so |
| A separate `marks.py` vocabulary rather than formatting marks where they arise | FR-015 requires marks to survive rendering; one vocabulary is what makes "strip all styling and assert the marks are still there" a single testable claim | Formatting at each site guarantees drift, and the drift is invisible until someone reads two diagrams side by side |

## Phase 2 note

`/speckit-tasks` generates `tasks.md` next. The order that matters: **`numbers.py` and
`mermaid.py` first** — the escaping and the one number rule are what everything else calls,
and getting them last means rewriting every call site — then `marks.py`, then the two
renderers, then the script, then the goldens **last**, because a golden checked in before
the behaviour is settled trains everyone to regenerate without reading.

## A note on the parallel lane

Feature 004 is being implemented at the same time and touches `core/results/ramp.py`
(new fields on `RampCost`, `OneWayCost`, `RoundTripCost`) and `core/routes/`. This feature
touches neither. Where they meet is at `render_path`'s input type: after 004 lands, a
`RampCost` may carry a composed path and a per-segment attribution. **Do not anticipate it
here** — render what the type carries today. Rendering composed candidates is 004's
successor's business, and guessing its shape now would produce a special case that has to be
deleted.
