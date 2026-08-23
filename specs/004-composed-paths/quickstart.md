# Quickstart: verifying 004-composed-paths

**Date**: 2026-08-23

How to confirm this feature works, ordered so problems surface soonest. No implementation
code — see [data-model.md](./data-model.md) and [contracts/](./contracts/) for shapes.

## Prerequisites

```bash
uv sync --all-extras --dev
```

Python 3.13. No network; `tests/conftest.py` blocks sockets.

## The one-command check

```bash
uv run pytest -q
```

## 1. The regression that matters most, and it is not a new test

```bash
uv run pytest tests/golden/test_ramp_comparison.py -v
```

002's golden file must be **byte-identical** after the path type widens and the exit chain
joins the key. A registry with no composable chains produces exactly the candidates it
produced before, at exactly the same numbers. If this moves, the shape change leaked into
the arithmetic, and nothing below is worth reading until it is green again.

## 2. The number the feature exists for

```bash
uv run pytest -m worked_example -k composed -v
```

- **SC-001** — a chain A→B→C with no declared A→C: arriving amount and cost percentages
  against leg-by-leg arithmetic worked out by hand and checked in beside the assertion.
- **SC-015** — a round trip whose exit is reachable only by chaining declared exit routes,
  hand-computed; and the other direction, a destination from which nothing chains, still
  reporting *exit cost unknown* and staying out of the round-trip ranking.
- **SC-007** — two legs in **different segments** naming one capacity pool consume one
  shared headroom. Hand-computed because it is a claim about 002's accumulator surviving
  composition, not about new code.

If a composed cost is off by a small amount rather than a large one, suspect a sum of
per-segment results creeping in somewhere: the fold must run once over the concatenated
legs, because the rounding of a sum of sums is not the rounding of one fold.

## 3. The search stays a search, not a router

```bash
uv run pytest -m invariant -k composition -v
```

| Covers | Asserts |
|---|---|
| SC-004 | Zero candidates visit a venue twice, over the **entire** emitted set on a registry whose graph contains a cycle |
| SC-005 | With a bound of `n`: nothing longer than `n`, **everything** connectable up to `n`, and the bound visible in the results |
| SC-016 | No candidate mixes directions, verified over the entire set — including a registry where the only completion of an inbound chain runs through a route declared exit |
| SC-003 | Reversing the declaration order changes no figure, no position, no recommendation and no tie |

SC-003 is the one to read carefully if it fails. It is not a flaky-ordering test; it is the
test that catches a heuristic. An adjacency bucket left unsorted, a `set` iterated, a
`dict` relied on for order — each shows up here and nowhere else.

## 4. Composed candidates are visibly composed

```bash
uv run pytest -m contract -k "composed or composition" -v
```

| Covers | Asserts |
|---|---|
| SC-002 | Every candidate is costed through the one function — **by construction**: `legs_of` is the only producer of a leg sequence, asserted structurally as 002 SC-016 asserts its own |
| SC-017 | Every composed candidate in every ranking, report and recommendation is a distinct type shown segment by segment, each naming its declared route |
| SC-018 | Two exit chains from one destination give two round-trip figures, each keyed by its chain; equal within tolerance, they tie |
| SC-009, SC-011 | No cost attributable to a destination alone; per-leg disruption everywhere and no combined path-level figure anywhere |
| SC-013 | No ranking holds two candidates with identical leg chains, on a registry declaring a route **and** its exact segment-wise equivalent |
| FR-006 | Every refusal in [contracts/composition-declaration.md](./contracts/composition-declaration.md) |

SC-013 is the one with a specific trap: `Leg.index` is per-route, so a concatenation gives
`0,1,0` where the declared equivalent gives `0,1,2`. If duplicates are not being suppressed,
the index is not being normalised before the comparison.

## 5. Feasibility and regimes

```bash
uv run pytest tests/unit/test_composed_feasibility.py -v
```

SC-008 — a closed segment excludes the candidate with the **binding segment** named, and the
exclusion is visible in the output rather than silent. SC-012 — across a regime transition,
no candidate mixes route sets, verified on a registry where only a mixed chain would connect.

## 6. The gates

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run lint-imports
uv run python scripts/check_provenance.py
uv run pytest --cov
```

`check_provenance.py` is fail-closed over the data tree, so `data/composition/` must be in
`EXEMPT_DIRS` **with its reason recorded** — absence from `SOURCED_DIRS` is an error, not an
exemption. If the reason reads like a citation, the file has the wrong kind of number in it.

## What "done" looks like

- All eighteen success criteria have a named test above, and 002's golden file has not moved.
- `docs/METHODOLOGY.md` gains: what a composed candidate is, why every one is costed in full,
  what a junction does **not** do, how the segment bound bounds reach, and why there is no
  path-level disruption probability.
- `docs/REQUIRED_TESTS.md` flips no row — this feature closes none — and records the pressure
  it puts on B12, G6 and H1 with the test paths that hold them.
- `features.toml` flips 004 to `done` **and removes** `identity-exit-vs-partner-requirement`
  from the future list, because this feature closed it. A solved problem left on that list
  misdirects the next reader as surely as an unrecorded one.
