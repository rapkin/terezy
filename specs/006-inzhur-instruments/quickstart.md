# Quickstart: verifying 006-inzhur-instruments

**Date**: 2026-08-23

## Prerequisites

```bash
uv sync --all-extras --dev
```

Python 3.13. No network at any point — the fund documents were read by a human on
2026-08-22 and their values are in the spec.

## The one-command check

```bash
uv run pytest -q
```

## 1. The migration proof, before anything else

```bash
uv run pytest tests/golden/test_end_to_end_ovdp.py -v
```

Feature 001's golden must be **byte-identical** after tax rates become dated schedules. The
exempt class charges exactly zero on every event, before and after (SC-006, FR-014). If this
moves, the migration changed a number and nothing below is worth reading.

**If it moves because the exempt class's cited effective date falls after 2026-01-15, do not
widen the date.** That is the one failure with a wrong fix available. The right fix is a
citation for the earlier entry; if none exists, it is an owner question.

## 2. Both taxes in one run

```bash
uv run pytest -m worked_example -k "tax_classes or schedule" -v
```

- **SC-001** — one projection charges a distribution under the fund-distribution class and a
  redemption of the same units under investment profit, with per-class subtotals matching
  hand-computed arithmetic checked in beside the assertion. This is required test **E1**.
- **SC-003, SC-004** — a run straddling an effective date charges the old rate before it and
  the new rate on and after it, and the change was entered as **one dated entry in a data
  file**. Required test **E10**.

If a subtotal is right but the split is invisible, the ledger is correct and the *result
shape* is not — FR-007's per-class reporting is the requirement, not a nicety.

## 3. Liquidity, and the exit that is refused

```bash
uv run pytest tests/worked_examples/test_fund_liquidity.py -v
```

Three cases, hand-computed (SC-007), which together are required test **J3**:

| Mode | Outcome |
|---|---|
| practice | Exit at NAV, same day, zero commission — and the output says this is a **revocable company practice**, not an obligation |
| legal, buyback available | Exit at NAV less the declared discount, settled after the declared delay; the discount is its **own line**, and the disposal tax is computed on the post-discount proceeds |
| legal, buyback unavailable | **Refused**, naming that no obligation exists before the termination date. The holding stays open — nothing silently executed, adjusted or deferred |

## 4. The peg, and the number that cannot be invented

```bash
uv run pytest tests/worked_examples/test_pegged_distribution.py -v
```

- **SC-011** — a pegged payment sized under a declared exchange-rate assumption; and with no
  assumption declared, a typed degraded result naming exactly which input is missing. Never
  an implicit rate.
- Where the assumed rate exceeds the declared cap, the payment is sized **at the cap** and the
  output says the cap bound.
- **SC-012** — round-trip spread erosion and any exit discount each appear as their own line.

## 5. The structural refusals

```bash
uv run pytest -m contract -k "fund or assumption or schedule" -v
```

| Covers | Asserts |
|---|---|
| SC-009 | No output for either fund contains a volatility, Sharpe or Sortino figure — and no result record has a field one could sit in |
| SC-005 | An event before a schedule's earliest entry is a typed refusal naming the class and the date |
| SC-008 | With any fund term left unverified, **100%** of figures derived from it carry the mark |
| SC-010 | A third fund with different liquidity terms, spread, peg and tax classes projects correctly with **zero** lines of source changed |
| SC-013 | Every figure derived from a fund-stated yield is labelled as such; a range stays a range unless an explicitly declared point overrides it |
| SC-014 | A purchase after the subscription cutoff is refused naming the cutoff |
| — | Every refusal in [contracts/fund-declaration.md](./contracts/fund-declaration.md) and [contracts/tax-schedule.md](./contracts/tax-schedule.md), including a `verification_task` that carries a value |

## 6. The gates

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run lint-imports
uv run python scripts/check_provenance.py
uv run pytest --cov
```

`check_provenance.py` matters more here than in any feature so far: `data/instruments/` and
`data/tax/` are **sourced** directories, so every value needs `source` and `retrieved_on`.
An **empty `verified_on` is expected and correct** for every fund term and every new tax
rate — researched is not verified, and the gate reports them as unverified rather than
failing.

## What "done" looks like

- All fourteen success criteria have a named test, and 001's golden has not moved.
- `docs/REQUIRED_TESTS.md` flips **E1**, **E10** and **J3**, with test paths recorded — and
  J3's wording is annotated: the funds have no redemption windows, and the row's substance is
  preserved over the declared liquidity terms instead.
- `docs/METHODOLOGY.md` gains: how a rate schedule is read, what "assumption-driven" forbids,
  what the declared net yield is and is not, how the peg and its cap are stated, and why no
  fund-internal fee is modelled.
- Every fund term and every new tax rate is in `data/`, cited, with an empty `verified_on`.
