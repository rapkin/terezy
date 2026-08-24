# Quickstart: verifying 010-full-tuple

**Date**: 2026-08-23

```bash
uv sync --all-extras --dev
uv run pytest -q
```

## 1. The seams, first

```bash
uv run pytest tests/unit/test_chaining_refusals.py -v
```

A deliberate mismatch at each seam: a route in ending somewhere the purchase does not begin,
and an instrument exit producing a balance the route out cannot take. Both must refuse,
**naming both sides**.

This is first because it is the part that can be silently wrong. Feature 004 shipped an exit
chain anchored at neither end: money moved between venues for free and the record still read
as a coherent three-hop journey. The same failure is available here twice.

## 2. The number the feature exists for

```bash
uv run pytest tests/worked_examples/test_full_round_trip.py -v
```

Ramp in, purchase, lifecycle, tax, exit terms, ramp out — hand-computed end to end, with the
arithmetic checked in. A join that sums the right parts in the wrong order passes every
structural test and fails only this one.

## 3. The benchmark is not special

```bash
uv run pytest tests/contract/test_the_hurdle_is_a_tuple.py -v
```

The hurdle in the comparison is the OVDP evaluated as a tuple through its declared zero-cost
domestic routes — **the same code path**, asserted by construction. A separately-computed
benchmark can drift from what it benchmarks, and the drift is invisible because both numbers
look reasonable.

## 4. H1 — the test that can falsify the architecture

```bash
uv run pytest tests/contract/test_h1_data_only.py -v
```

A new instrument, route, tax class and jurisdiction added **in data only**, running the full
pipeline and appearing in the comparison with **zero source lines changed**.

**If it fails, do not fix it in the join.** Record which seam, which declaration kind and
what edit it forced; fixing the abstraction is in scope, hiding the finding is not. A special
case added to keep this green turns the only test that can falsify the architecture into one
that cannot.

## 5. Everything the goldens already pin

```bash
uv run pytest -m golden -v
```

001's, 002's and 007's goldens must not move. This feature adds a join; it changes no
existing computation. If one moves, something was changed that should only have been called.

## 6. The gates

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy && uv run lint-imports
uv run python scripts/check_provenance.py
uv run python scripts/check_methodology_refs.py
uv run pytest --cov
```

## What "done" looks like

- **H1** flipped in `docs/REQUIRED_TESTS.md` with its path — or open, with the recorded
  defect naming exactly what stopped it.
- `docs/METHODOLOGY.md` gains: what a tuple is, how the parts chain, why the benchmark comes
  from the same path, and why proceeds arriving early are not reinvested.
- No existing golden moved.
