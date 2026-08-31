# Quickstart: validating the working-day calendar

**Feature**: `017-working-day-calendar`

```bash
cd .claude/worktrees/017-calendar
uv sync --all-extras --dev
```

## The feature's own suites

```bash
uv run pytest tests/unit/test_working_day_calendar.py \
              tests/worked_examples/test_working_day_classification.py \
              tests/contract/test_calendar_declaration_loading.py \
              tests/contract/test_calendar_data_only.py \
              tests/contract/test_no_calendar_free_working_day.py
```

## The gates, by exit code

```bash
uv run pytest --cov
uv run mypy
uv run ruff check . && uv run ruff format --check .
uv run lint-imports
uv run python scripts/check_provenance.py
uv run python scripts/check_prose_budget.py
uv run python scripts/check_enumerations.py
uv run python scripts/check_methodology_refs.py
```

## What proves the feature, by hand

The shipped calendar covers 2025-01-01 … 2026-10-30 and declares no holidays, because ст. 53 and
ст. 73 КЗпП are not applied during martial law (research D9). So:

* **2026-08-30** (a Sunday, inside the window) classifies **non-working**, decided by the rest
  pattern.
* **2026-08-29** (a Saturday) classifies **working** — the shipped calendar's week is Sunday
  only, and `conventions._is_weekend` disagrees with it. Neither is consumed, so no figure moves.
* **2026-01-01** classifies **working**. The holiday regime is suspended, and the file says so
  with the suspending act cited on its coverage window.
* **2026-10-31** refuses: `CalendarOutOfCoverage`, `AFTER_WINDOW`, naming the calendar, the date
  and the window.
* Asking the same questions with `scope=CalendarScope.SETTLEMENT` refuses with
  `CalendarScopeMismatch`, naming both scopes.

## What must not change

No golden result file moves and no figure changes (SC-010). `uv run pytest tests/golden` is the
check, and it is a check on this feature staying on its own side of the no-consumer line.
