# Phase 1 data model: route diagrams

**Feature**: `005-route-diagrams` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

Frozen dataclasses and free functions (owner decision D-E). Everything here lives in
`terezy.api.diagrams` — the core neither formats nor renders (FR-020, Principle III).

**The rule governing every record below: the renderer holds no figure of its own.** Every
number that appears came from the input, rendered through the one rule of FR-022. There is
no field here for a computed, aggregated or re-rounded value.

---

## Output

### `Diagram`

| Field | Type | Meaning |
|---|---|---|
| `text` | `str` | Valid Mermaid, byte-identical for identical inputs (FR-016, FR-017) |
| `kind` | `Literal["route_graph", "costed_path"]` | The two kinds, and there are no others (FR-001) |
| `regime_id` | `str` | The one regime this diagram shows (FR-019) |
| `mode` | `Mode \| None` | The registry graph's mode; `None` for a costed path, which has no modes |

### `NothingToDraw`

| Field | Type | Meaning |
|---|---|---|
| `reason` | `str` | The refusal's own reason, carried verbatim from the input |
| `kind` | `Literal["route_graph", "costed_path"]` | What was asked for |

Returned **instead of** a `Diagram`. Never an empty diagram: an empty picture is
indistinguishable from a graph with nothing in it, and the reason the caller needs is
already in the input (FR-011, SC-010, defect B10).

### `Mode`

A closed enum, `TOPOLOGY | DECLARED_FIGURES` (FR-006). Rendered by name **into** the
diagram, so a numberless picture is never read as "zero fees".

## The one number rule

### `numbers.py`

| Function | Renders |
|---|---|
| `percent(value: float) -> str` | Fixed two decimals with `%` |
| `amount(value: Money) -> str` | Fixed two decimals with the currency code |

The project's only diagram-label number rule (FR-022), on the model of the single project
tolerance. It **rounds**, and that is the one transformation FR-008 permits — the diagram is
a picture, not the audit trail. A second rule anywhere, or an inline format at a call site,
is a defect, and a contract test greps for one.

## Marks

### `Mark`

A closed enum of the states a label can carry: `UNVERIFIED`, `STALE`, `SYNTHETIC`,
`CLOSED`, `NO_EXIT_DECLARED`, `EXIT_COST_UNKNOWN`.

Rendered as **visible tokens inside the label text** (FR-015). Mermaid `classDef` styling
may add emphasis on top; it may never be the only carrier, because a mark that lives in a
colour is lost the moment the text is diffed, re-themed, or read as a golden file — and
golden files are one of the two places this output lands.

Six mark states are what SC-004 enumerates, and the assertion strips all styling first.

## Node identity

Not a record — a rule, stated here because it is the design's load-bearing choice.

A node's Mermaid id is `n<k>`, `k` being the entity's index in the sorted list of entities
drawn. The declared id and name go in the **quoted, escaped label**.

Positional because it is injective by construction: deriving the id from the declared id
means sanitising `binance-p2p` and `binance_p2p` into the same identifier and silently
merging two venues, which is FR-018 violated invisibly. It also makes SC-008's hostile
names — quotes, brackets, pipes, arrows, Cyrillic — a labelling problem only, never an
identity problem.

## Inputs, unchanged

The renderer consumes what already exists and defines no parallel model (FR-020):

| Input | From | Used for |
|---|---|---|
| `Venue`, `Route`, `Leg`, `Regime` | `core.routes`, `core.scenarios` | The registry graph |
| `RampCost`, `OneWayCost`, `RoundTripCost` | `core.results.ramp` | The costed path |
| `ExitCostUnknown`, `RouteUnusable`, `NothingComparable` | `core.results.ramp` | Refusals, drawn as refusals |
| `Provenance`, `StalenessVerdict` | `core.primitives` | The marks |

**No import of `core.routes.coverage` and none of composition** (research.md D6). The *no
exit declared* mark is computed here from the declarations — a smaller question than the
audit, with the same answer, and no dependency on a feature landing in parallel.
