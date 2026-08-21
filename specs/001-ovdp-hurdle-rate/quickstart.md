# Quickstart: verifying 001-ovdp-hurdle-rate

**Date**: 2026-08-21

How to confirm this feature works, in the order that finds problems soonest. No
implementation code here — see [data-model.md](./data-model.md) and
[contracts/](./contracts/) for shapes, and `tasks.md` for the work itself.

## Prerequisites

```bash
uv sync --all-extras --dev
```

Python 3.13 (pinned in `.python-version`). No network access is needed at any point —
`tests/conftest.py` blocks sockets and will fail loudly if anything tries.

## The one-command check

```bash
uv run pytest -q
```

Green means every gate below passes. When it is red, the sections that follow narrow it
down.

## 1. The number itself

```bash
uv run pytest -m worked_example -v
```

This is the feature's reason for existing: an OVDP bought at stated terms and held to
maturity, with every coupon and the principal checked against arithmetic worked out by
hand and recorded beside the assertion.

Expect:

- the coupon and principal schedule matching the hand-computed figures within the project
  tolerance (**D1**),
- **total tax exactly zero** — not approximately zero (**SC-002**),
- the two-period coupon-reinvestment case matching by hand (**D2**),
- the reinvesting and cash-holding policies producing *different* terminal amounts
  (**SC-010**).

If the schedule is off by a consistent factor, suspect the day-count fraction or the
percent-to-fraction conversion at the loader boundary — `_pct` fields are divided by 100
exactly once, and doing it twice or not at all are the two likeliest mistakes.

## 2. The invariants

```bash
uv run pytest -m invariant -v
```

Property-based, over generated holdings and dates rather than fixed examples. These are
compliance tests for the constitution and may not be skipped or xfailed without an
amendment.

| Covers | Asserts |
|---|---|
| **C1** | Cash conservation per currency, **on every date** — not only at the end. An error that cancels out by maturity is still an error. |
| **C2** | Lot conservation; no lot ever negative |
| **C3** | Basis conservation; realised gain in both currencies |
| **C4** | Determinism — two runs on identical inputs give an identical digest |
| **C5** | Currency safety — mixing UAH and USD always raises |
| **C6** | Every figure resolves to the events behind it |

A Hypothesis failure prints a minimal counterexample. Take it seriously even when it
looks exotic: these invariants are the reason the ledger exists, and the predecessor
project's worst defects were exactly the cases nobody thought to write an example for.

## 3. Provenance and loud failure

```bash
uv run pytest -m contract -v
uv run python scripts/check_provenance.py
```

The contract suite covers the two things the automated gates cannot see for themselves:

- **E5 / FR-015** — with the yield left unverified, *every* figure derived from it carries
  the mark, and none appears unmarked. This is the top-severity defect class in the whole
  project.
- **H2 / FR-016** — a battery of deliberately broken declaration files, each expected to
  fail naming the file and the field: unknown field, missing field, wrong type, absent
  `verified_on`, duplicate id, undeclared tax-class reference, unknown day-count name,
  malformed TOML. **No case may produce a substituted default.**
- **SC-003 / SC-012** — a second issue with different conventions produces a complete
  result with zero source-code changes.

`check_provenance.py` separately confirms every curated value carries a citation. Expect
warnings about empty `verified_on` — those are correct and expected, since nothing has
been verified against primary legislation yet.

## 4. The structural gates

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run lint-imports
```

`mypy` is doing real work here beyond typos: **assigning a nominal rate into the real-terms
slot is a type error** (decision D4), which is the mechanical guard behind SC-011.
`lint-imports` confirms the core acquired no I/O, no `pydantic` and no `hashlib` — if the
loader drifted into `core`, this is where it shows.

## 5. Coverage

```bash
uv run pytest --cov --cov-report=term-missing
```

The 90% floor is blocking. Treat it as necessary and not sufficient — the real gate is
the ten rows in `docs/REQUIRED_TESTS.md`, and coverage can be satisfied without any of
them being true.

## Definition of done

- [ ] `uv run pytest` green with the coverage floor met
- [ ] `ruff`, `mypy`, `lint-imports`, `check_provenance.py` all clean
- [ ] Ten rows flipped in `docs/REQUIRED_TESTS.md` with test paths recorded: C1–C6, D1,
      D2, E5, H2
- [ ] `.importlinter` tightened with `hashlib` and `pydantic` in the core's forbidden list
- [ ] `docs/METHODOLOGY.md` created, documenting the coupon-schedule and yield formulas —
      an undocumented formula is an incomplete feature
- [ ] Manual review of provenance propagation and tolerance usage, since no gate sees
      either

## What this feature does not tell you

Worth stating plainly, because the output is a confident-looking number:

- It is **nominal**. Inflation is not modelled, so 15.5% nominal against double-digit
  inflation is a materially different proposition than it appears (FR-022).
- It **excludes route and exit costs**. For OVDP via Inzhur those are reported as 0%, so
  the figure happens to be near-complete for this one instrument — but the figure is not
  comparison-ready against instruments whose ramp costs are large, and the `excludes`
  field says so.
- The yield is **unverified**. Every figure derived from it is marked, and that mark is
  the honest state of affairs until the real issue's terms are confirmed from the Inzhur
  listing.
