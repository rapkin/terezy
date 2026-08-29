# Quickstart: validating the enumerated form

**Feature**: `013-enumerated-schedule` | **Date**: 2026-08-29

Prerequisites: `uv sync --all-extras --dev`. No network at any point — `tests/conftest.py`
fails loudly on a socket attempt.

## The gates

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run lint-imports
uv run python scripts/check_provenance.py
uv run pytest --cov
```

All blocking. `mypy` is the interesting one during phase 1: making
`InstrumentDeclaration.terms` a union is what enumerates the sites that must change, so a
long list there is the design working rather than a problem.

## The five checks that decide whether this landed

```bash
# 1. The schedule and its totals against arithmetic worked out by hand      (SC-001)
uv run pytest tests/worked_examples/test_enumerated_schedule.py -q

# 2. An enumerated tuple and a generative tuple with the same cash flows,
#    compared field by field                                               (SC-002)
uv run pytest tests/golden/test_enumerated_matches_generative.py -q

# 3. No layer knows the form; nothing is inferred; the day count reaches no
#    amount; no result record splits a purchase price      (SC-003/014/020/023)
uv run pytest -m contract -k "form or inferred or day_count or accrued" -q

# 4. The battery of broken declarations, every failure naming file and entry (SC-006)
uv run pytest tests/contract/test_enumerated_declaration_loading.py -q

# 5. A third enumerated instrument, data only                               (SC-004)
uv run pytest tests/contract/test_enumerated_data_only.py -q
```

## Regenerating the goldens

Deliberately, with the diff read, per constitution 1.2.0 Principle V:

```bash
TEREZY_UPDATE_GOLDEN=1 uv run pytest tests/golden -q
git diff tests/golden/
```

Two digests are **expected** to move in this feature and their changed lines are quoted in
the commit message: `Projection` now carries the premium-or-discount figure, so
`canonical.of_projection` says one more true thing about every holding. No generative amount,
date, tax or rate moves — assert that by reading the rendering half of the diff, which is
where an unintended change would show.

## Trying the form by hand

```python
from pathlib import Path
from datetime import date
from terezy.data.declarations import resolver
from terezy.core.results import project
from terezy.core.instruments.interface import Assumptions, DateRange, Holding
from terezy.core.primitives.money import Money
from terezy.core.primitives.currency import Currency

declarations = resolver.from_data_root(Path("data"))
declared = declarations.instruments["ovdp_enumerated_a"]

outcome = project.project(
    declared,
    Holding(
        owner_id="owner-001",
        instrument_id=declared.id,
        quantity=10.0,
        purchased_on=date(2026, 2, 1),
        cost=Money(10_255.90, Currency.UAH, declared.terms.provenance),
    ),
    DateRange(start=date(2026, 2, 1), end=date(2029, 12, 31)),
    Assumptions(consumption_method="fifo", coupon_policy="hold_cash"),
    tax_classes=declarations.tax_classes,
)
```

Then ask it the three questions this feature is about:

- `outcome.schedule.rows[1].conventions` — states that no periodicity generated the date and
  no day count sized the amount, and names the day count that annualises.
- `outcome.hurdle.excludes` — contains the dirty-price clause, which the generative
  equivalent's does not.
- `outcome.at_purchase` — the premium over face, and the category treatment that governs it.

Ask it something it cannot know and it refuses in a typed value rather than computing around
the gap: move `purchased_on` a day before `covers_from`, or set
`coupon_policy="reinvest"`.
