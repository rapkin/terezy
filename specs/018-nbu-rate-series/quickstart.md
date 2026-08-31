# Quickstart: 018-nbu-rate-series

## Re-run the retrieval

```bash
uv run python scripts/fetch_nbu_rates.py --dry-run   # report, write nothing
uv run python scripts/fetch_nbu_rates.py             # rewrite data/official_rates/ua_nbu_usd.toml
git diff data/official_rates/ua_nbu_usd.toml
```

Expected: a report naming the publisher, the covered window, the row count, the day-ahead rows
declined, and `verified_on (empty, deliberately)`. The diff should be the new tail plus every
row's `retrieved_on`. **A `value` that moved on a past date is the publisher restating it**; that
row's `verified_on` clears, which is the point of FR-006.

A re-fetch moves the file's digest, so the golden moves with it:

```bash
TEREZY_UPDATE_GOLDEN=1 uv run pytest tests/golden/test_end_to_end_ovdp.py
git diff tests/golden/ovdp_synthetic_a.golden.txt
```

Only the `official_rate` input line may move. If a **result** line moves, stop: a rate series is
not an input to any figure in that run.

## Check one row by hand — the check this feature exists to make possible

Pick a date inside the window, read the value out of the declaration, and open the publisher's
own page for it:

```bash
grep -A1 'on_date      = "2026-03-02"' data/official_rates/ua_nbu_usd.toml
open 'https://bank.gov.ua/ua/markets/exchangerates?date=02.03.2026&period=daily'
```

If they agree, that observation — **and only that one** — may have its `verified_on` filled by
hand (FR-006). The next fetch preserves it while the published value is unchanged.

## Prove the feature

```bash
uv run pytest tests/worked_examples/test_nbu_official_rate_base.py   # SC-001, SC-002
uv run pytest tests/contract/test_nbu_series_is_declared.py          # SC-003, SC-006, SC-017, SC-019
uv run pytest tests/unit/test_fetch_nbu_rates.py                     # SC-004, SC-005, SC-007, SC-020
uv run python scripts/check_provenance.py                            # SC-014 — one line for the file
```

Then the whole gate set:

```bash
uv run pytest --cov && uv run mypy && uv run ruff check . && uv run ruff format --check . \
  && uv run lint-imports \
  && uv run python scripts/check_provenance.py \
  && uv run python scripts/check_prose_budget.py \
  && uv run python scripts/check_enumerations.py
```
