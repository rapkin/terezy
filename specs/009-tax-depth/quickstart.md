# Quickstart: verifying 009-tax-depth

**Date**: 2026-08-23

```bash
uv sync --all-extras --dev
uv run pytest -q
```

## 1. The regression first

```bash
uv run pytest tests/golden/test_end_to_end_ovdp.py -v
```

001's golden **bit-identical**. Per-event zero charges still recorded; a year of exclusively
exempt income produces **no payment event**, so no cash moves. If it moves, the exempt path
grew a behaviour it should not have — read the diff before anything else.

## 2. Four methods, four different numbers

```bash
uv run pytest tests/worked_examples/test_four_lot_methods.py -v
```

One three-lot position, one partial sale, four hand-computed figures **pairwise distinct**
(FR-025). The distinctness is the point: a fixture where two methods agree cannot detect one
being silently substituted for another.

And the claim that matters more than the arithmetic — **no figure is labelled the tax you
owe**. Each states its method; the two source-backed candidates carry their citations; the
choice between them is a labelled switch. If you can find a liability in the output without
a method attached, that is the defect.

## 3. Losses, both branches

```bash
uv run pytest tests/worked_examples/test_loss_carryforward.py -v
```

A loss year then a gain year, hand-computed **twice** — filed and unfiled. The unfiled branch
names the forfeited amount, so the cost of not filing is a number rather than an absence.
Neither branch is a default: a run that does not state which one refuses.

## 4. Tax is paid with money, on a date

```bash
uv run pytest tests/worked_examples/test_tax_payment.py tests/unit/test_insufficient_cash.py -v
uv run pytest -m invariant -k conservation -v
```

Nothing is deducted from a position or from proceeds at event time; the payment debits cash
on the declared due date. Conservation properties must pass **unchanged** over ledgers
containing payments — as they did for 008's seeds. If one fails only for those ledgers, fix
the event, not the invariant.

With insufficient cash: a typed report naming the shortfall, the date and the statement.
**Nothing is sold** — which positions a forced sale would draw on is the owner's recorded
deferral, not this feature's guess.

## 5. The gates

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy && uv run lint-imports
uv run python scripts/check_provenance.py
uv run python scripts/check_methodology_refs.py
uv run pytest --cov
```

Every due-date rule and carryforward rule is a legal value: cited, with an empty
`verified_on`. The unsettled switches live in `data/scenarios/`, which is exempt from the
citation gate because a belief needs a label and a visible consequence, not a source.

## What "done" looks like

- **E2**, **E6** and **E7** flipped in `docs/REQUIRED_TESTS.md` with paths — E7 partially,
  since the forced-sale half is the owner's deferral and stays open.
- `docs/METHODOLOGY.md` gains: how a year is assessed, why no tax is deducted at event time,
  the four methods with their legal standing, and why none is labelled the liability.
- `scripts/check_methodology_refs.py` passes.
