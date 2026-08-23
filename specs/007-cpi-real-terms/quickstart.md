# Quickstart: verifying 007-cpi-real-terms

**Date**: 2026-08-23

## Prerequisites

```bash
uv sync --all-extras --dev
```

Python 3.13. **No network.** The CPI data is already committed at `data/cpi/ua.toml`;
`scripts/fetch_cpi.py` put it there and this feature does not know it exists.

## The one-command check

```bash
uv run pytest -q
```

## 1. What the shipped data can and cannot answer today

```bash
uv run python scripts/fetch_cpi.py --dry-run
```

411 observations, **1991-08 to 2025-10**. Every hurdle window reaching into 2026 is
therefore **uncovered**, and the realized figure is unavailable — naming the uncovered
months. That is the feature working, not a gap in it: re-running the fetcher is the fix, and
the refusal is what stops a number being invented in the meantime.

## 2. The arithmetic, by hand

```bash
uv run pytest -m worked_example -k "deflation or falling" -v
```

- The Fisher relation exactly: `(1 + nominal) / (1 + inflation) - 1`. The window is chosen so
  that **summing** the month-on-month observations and **multiplying** them give visibly
  different answers — a summing implementation cannot pass.
- A falling-prices window gives a real rate **above** the nominal one. Deflation is a valid
  observation, not an error and not clamped.

If a real figure is close but not equal, suspect the approximation: `nominal - inflation` is
off by percentage points at Ukrainian magnitudes, which is exactly why FR-008 forbids it and
why `test_no_subtraction_approximation.py` scans for it.

## 3. Two figures that never blend

```bash
uv run pytest tests/contract/test_two_figures_never_blend.py -v
```

A realized figure and an assumed figure are distinguishable at a glance and in the type:
each carries its own `basis`, and **no field anywhere holds a number combining observed and
assumed inflation**. A cited external forecast is still labelled an assumption — the National
Bank's number has a source and a retrieval date and is a forecast; cited does not make it
observed.

## 4. The refusals, each naming what is missing

```bash
uv run pytest tests/unit/test_real_terms_reasons.py tests/unit/test_cpi_coverage.py -v
```

| Missing | The reason names |
|---|---|
| The series | the absent series |
| A month inside the window | **the uncovered months**, listed |
| The nominal figure | the absent nominal figure |
| The assumption | that no future-inflation assumption was declared for this run |

And a check worth running by eye: `grep -rn "inflation is not modelled" src/` must come back
empty. That sentence was true in 001 and stops being true here.

## 5. Provenance, and how much of it there is

```bash
uv run pytest tests/contract/test_provenance_propagation.py -v
```

A real figure's provenance is the **union** of the nominal figure's and every observation
that deflated it. A long window means hundreds of sources on one figure — that is the honest
answer, and the test asserts the count rather than sampling. Every shipped observation is
unverified, so every real figure derived from them is marked; deflating a marked nominal
figure never launders its mark either.

## 6. Nothing nominal moved

```bash
uv run pytest tests/golden/test_end_to_end_ovdp.py -v
```

The golden **will** change on the real slot's lines — two entries instead of one, with a
specific reason. **Every nominal figure, schedule row and tax charge must be byte-identical.**
If one moves, stop: FR-014 is this feature's whole claim to being additive.

## 7. The gates

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run lint-imports
uv run python scripts/check_provenance.py
uv run pytest --cov
```

`check_provenance.py` already scans `data/cpi/` — it is in `SOURCED_DIRS`, because a
published index is exactly the cited observation that gate exists for. It reports 411
unverified values and that is correct: nobody has checked them against Держстат yet.

## What "done" looks like

- Every acceptance scenario has a named test, and no nominal figure moved.
- `docs/METHODOLOGY.md` gains the Fisher relation with a worked example, in the same change
  as the formula — the constitution requires it and a reader will otherwise assume the
  subtraction.
- 001's spec gains its ⚙ cross-reference at FR-022 recording that the prohibition was
  **refined, not repealed** (FR-009's recorded obligation).
- `grep -rn "inflation is not modelled" src/` is empty.
