# terezy — project goal, audit, and rewrite brief

**Audience:** an engineering agent tasked with rewriting this project into a real,
usable, interactive personal-investment simulator with proper tax modelling.
**Status of the current code:** working research prototype, 64 passing tests, correct
on the market-mechanics side, *not* a real-world after-tax tool.
**Date of audit:** 2026-08-21 (HEAD `550021b`).

Read sections 1–2 to know *why* the project exists, 3–4 for what is worth keeping and
what is broken, 5–8 for what to build. Section 9 lists the decisions only the owner can make.

---

## 1. The goal, in one paragraph

An ordinary person with a salary wants to know: **"If I put a fixed part of every
paycheck into X for N years, what would I actually end up with — after inflation,
after fees, after tax — and what pain would I have lived through to get it?"**
The project answers that with historical simulation of dollar-cost averaging (DCA),
holding methodology identical across every asset so results are comparable, and always
against the alternatives a real person has: cash, bank deposits/T-bills, and a
diversified portfolio.

The original goal statement (Ukrainian, `legacy/SPECIFICATION.md`) frames it as five
questions, which are still the right product spec:

1. **Where to invest?** — stocks, indices, bonds, gold, crypto: which, and in what mix?
2. **Is it even worth it?** — versus holding cash or a deposit.
3. **What is the *real* return?** — nominal numbers are meaningless under inflation.
4. **What is the risk?** — how much could I have lost, and for how long?
5. **How do I balance a portfolio?** — how much of each asset?

Its five stated principles are the ones the rewrite must keep: **realism,
transparency (every formula documented), comparability (one methodology for all
assets), inflation-awareness, and risk-adjusted judgement** (return without risk is
gambling, not investing).

### What changed since that spec was written

The original spec explicitly excluded taxes and fees "because they depend on
jurisdiction". That exclusion is now the main thing standing between this project and
usefulness: for the owner's actual situation — a **non-USD salary, IBKR brokerage, tax
residency in Ukraine or Cyprus** — taxes and FX are not a footnote, they are among the
largest terms in the result. The rewrite's defining goal is:

> **A tool whose headline number is money the investor actually keeps, in the currency
> they actually spend, under the tax rules they are actually subject to — and that a
> non-programmer can drive interactively.**

### Non-goals (keep these)

- Not financial advice; an analysis tool.
- Not a forecaster. Historical/statistical simulation only, clearly labelled as such.
- Not a trading system or broker integration. No order execution, ever.
- Not a tax filing tool. It models tax to compare scenarios; it does not produce
  filings, and every rate must be user-verifiable and user-overridable.

---

## 2. Who uses it, and how it should feel

| | Now | Target |
|---|---|---|
| Interface | `terezy run -s 2018 -e 2025 -a 500 -p ukraine-ibkr` → PNGs + CSVs + static HTML | Interactive app: define a plan, move sliders, see the after-tax outcome update; CLI/API retained for scripting |
| Output | 20-column metric tables, tearsheet PNGs | A narrative answer ("you'd have kept €X of €Y, tax cost you €Z") backed by drill-down |
| Configuration | 8 cost flags + a TOML profile | A *scenario* object (income, currency, jurisdiction, broker, assets, rules) that is saved, shared, diffed, and version-stamped |
| Audience | the author | the author + anyone he shows it to, without a Python env |

---

## 3. Where the project stands

### 3.1 History (three experiments, one lineage)

1. **`legacy/`** (commits up to `ffe4982`) — five scripts passing CSVs through a bash
   orchestrator: `investment_simulation.py`, `aggregate_results.py`,
   `optimize_portfolio.py`, `grid_search.py`, `generate_report.py` (~3,700 lines,
   mixed Ukrainian/English). Produced useful output with a dozen financial-math bugs.
2. **`terezy/`** (`be3de3d`, then named `invsim/`) — full reimplementation as one package (~2,500 lines,
   vectorized, tested). `docs/LEGACY_REVIEW.md` is the honest changelog of the 12
   correctness bugs it fixed; **read it, it encodes hard-won knowledge.**
3. **Hardening** (`c7c530d`, `28daab9`, `550021b`) — rolling-window robustness,
   walk-forward hyperparameter validation, a trading-cost model, a tearsheet-style
   report, and named cost/tax profiles.

### 3.2 Current module inventory

| Module | LOC | Responsibility | Verdict |
|---|---|---|---|
| `terezy/data.py` | 152 | yfinance + FRED access, per-year pickle cache | Rewrite (see 4.2, 5.7) |
| `terezy/schedule.py` | 48 | biweekly paydays → next trading day | **Keep the logic verbatim** |
| `terezy/simulation.py` | 343 | vectorized DCA engines, `Costs`, benchmarks | Keep as a "fast/no-tax" path; replace as the primary engine (5.1) |
| `terezy/metrics.py` | 237 | TWR returns, XIRR, drawdown, VaR/CVaR, score | **Keep; port nearly as-is** |
| `terezy/optimize.py` | 138 | max-Sharpe / min-var, walk-forward weights | Keep; extend (5.6) |
| `terezy/robustness.py` | 94 | rolling-window outcome distributions | Keep the idea; generalize beyond single assets |
| `terezy/validation.py` | 188 | anchored walk-forward CV of hyperparameters | **Keep; this is a differentiator** |
| `terezy/profiles.py` | 120 | named cost/tax profiles from built-ins + TOML | Keep the *pattern*, replace the model (5.3) |
| `terezy/plots.py` | 412 | matplotlib tearsheets | Replace (static PNG → interactive) |
| `terezy/report.py` | 230 | self-contained HTML report | Replace |
| `terezy/cli.py` | 551 | 6 subcommands | Thin down; it currently carries orchestration logic that belongs in the core |
| `tests/` | 817 | 64 tests, no network needed | **Keep and extend; see 7** |
| `legacy/` | 3,708 | previous implementation | Archive out of the repo root |

### 3.3 Capability matrix

| Capability | State |
|---|---|
| Biweekly DCA, next-trading-day execution, holiday-safe | ✅ correct |
| Time-weighted vs money-weighted returns kept separate | ✅ correct, tested |
| No look-ahead in portfolio weights | ✅ correct, tested (test corrupts future data and asserts weights unchanged) |
| Inflation-adjusted (real) values | ✅ but US CPI only |
| T-bill benchmark, ACT/365 | ✅ correct, tested |
| Risk metrics (vol, Sharpe, Sortino, MDD, Calmar, VaR/CVaR) | ✅ correct definitions |
| MPT optimization, static + walk-forward + equal-weight | ✅ correct, honest baselines |
| Rolling-window robustness, walk-forward CV | ✅ rare and valuable |
| Commissions, FX fee, annual fee drag | ⚠️ simplistic (4.3) |
| Capital-gains tax | ⚠️ toy model: one flat rate, average-cost basis, no lots, no carryforward (4.3) |
| **Dividend / withholding tax** | ❌ not modelled at all — and structurally *cannot* be, see 4.2-D1 |
| **Base currency other than USD** | ❌ absent; FX exists only as a fee |
| **Tax paid from cash, in the right tax year** | ❌ tax is silently deducted from the portfolio at the moment of the trade |
| Interest/deposit taxation (benchmark symmetry) | ❌ benchmarks are pre-tax while the portfolio is post-tax |
| Withdrawal / decumulation phase | ❌ accumulate-only |
| Interactivity | ❌ CLI → static files |
| Machine-readable results (JSON/typed schema) | ❌ CSV only |
| Reproducibility manifest (params + data versions) | ❌ none |

---

## 4. Audit findings

### 4.1 Preserve these — they are correct and were expensive to get right

Do not "simplify" any of the following during the rewrite. Each has a test.

1. **Flow-adjusted (time-weighted) returns** `r_t = (V_t − F_t)/V_{t−1} − 1` for every
   risk metric. A DCA value series must never be `pct_change()`d: each deposit would
   register as a fake gain. Test: flat-price asset with contributions ⇒ exactly 0
   return, 0 volatility.
2. **XIRR reported separately** as the money-weighted outcome. `(final/invested)^(1/y)`
   is *not* a DCA CAGR and must not reappear.
3. **Sortino uses the 2nd lower partial moment over all observations**
   `√(mean(min(r−rf,0)²))`, not `std(r[r<0])`.
4. **Optimizer input is asset price returns**, never portfolio values.
5. **No look-ahead:** static weights come from the warm-up window only; walk-forward
   weights use data strictly before each rebalance date.
6. **Paydays map to the next trading day on/after**, colliding paydays sum, and every
   compared strategy uses the *identical* contribution schedule.
7. **T-bills accrue ACT/365** over calendar-day gaps (weekends earn interest).
8. **Periods-per-year measured from the data** (~252 equities, ~365 crypto).
9. **Infeasible constraints raise** instead of silently returning an invalid portfolio.
10. **Walk-forward CV with an equal-weight baseline** and an explicit train→test
    degradation number. The honest verdict line ("tuning does NOT beat 1/N out of
    sample") is a feature — keep that spirit in the UI.
11. **Rolling-window robustness** as the antidote to single-backtest storytelling
    (gold beat inflation in only ~41% of 5-year windows since 2010).
12. **Only completed calendar years are cached**; the current year is always refetched.

### 4.2 Confirmed defects

Severity: **H** = wrong numbers or crash, **M** = misleading, **L** = papercut.

| # | Sev | Where | Finding |
|---|---|---|---|
| D1 | **H** | `data.py:90` (`auto_adjust=True`) + README | **Index vs ETF total-return mismatch.** For ETFs (`QQQ`, `TLT`, `VNQ`, `GLD`) adjusted close includes dividends; for indices (`^GSPC`, `^DJI`, `^IXIC`) there are no dividends to adjust — the series is a *price* index. The default ticker list mixes both and ranks them in one table, so `GSPC` is understated by roughly its dividend yield (~1.5–2 %/yr, compounding to a large gap over 8 years) relative to `QQQ`. The README's claim that prices are "adjusted close (splits + dividends included)" is only true for the ETFs. This violates the project's own comparability principle. |
| D2 | **H** | `data.py:57-64` + `cpi()`/`tbill_rate()` fallbacks | **A network failure permanently poisons the cache.** The FRED fetchers *return synthetic data* on exception (3 %/yr CPI, flat 2 % T-bill); `_load_yearly` then writes that synthetic series to `cache/cpi/CPIAUCSL_<year>.pkl` because the year is complete and the series is non-empty. Every later run reads the fake data from disk with **no warning**. Verified experimentally: after one simulated outage, a recovered FRED is never consulted again. Fix: never cache fallback data (tag it), or cache with a provenance marker and refuse to use it silently. |
| D3 | **H** | `simulation.py:291`, `optimize.py:120`, `validation.py:72`, `robustness.py:24-26` | **Non-integer year offsets crash.** `pd.DateOffset(years=2.5)` raises `ValueError: Non-integer years and months are ambiguous`. The CLI declares `--lookback` and `--window` as `float`, so `--lookback 2.5` or `--window 4.5` is an accepted argument that blows up mid-run. Use months (`DateOffset(months=round(12*y))`) or reject non-integers at parse time. |
| D4 | **H** | `simulation.py:81-89` (`after_exit_tax`) | **Exit tax double-taxes.** It charges `exit_rate × (final − invested)` even for gains already taxed at rebalances, and treats commissions as part of the basis in one place but not the other. Documented as "slightly conservative"; in a rebalancing portfolio over 8 years the overlap is not slight. Only lot-level accounting fixes this (5.1). |
| D5 | **H** | `simulation.py:254-286` (`_rebalance`) | **Tax is paid out of the portfolio, instantly.** Real capital-gains tax is assessed on the realizing year and paid from outside cash months later (Ukraine: annual declaration). Deducting it from the position at the moment of the trade both understates compounding and misstates *when* money leaves the investor's pocket. Also: average-cost basis is not a permitted method in most jurisdictions (Ukraine's "investment profit" rules are per-disposal), and there is no loss offset or carryforward, so a losing year is taxed as if flat. |
| D6 | **M** | `simulation.py:310` (`simulate_tbill`), `add_benchmarks` | **Benchmarks are pre-tax while the strategy is post-tax.** Interest on T-bills/deposits is taxable income (in Ukraine, at the same 18 % + 5 %). Comparing an after-tax portfolio to a pre-tax risk-free benchmark biases every "did it beat the alternative?" verdict — including the `beat_tbills_pct` column of the rolling analysis, which is a headline number. |
| D7 | **M** | `profiles.py:_IBKR_FEES`, `simulation.py:135-153` | **Per-leg minimum commission penalizes diversification unrealistically.** `commission_min = $1` is charged on *every asset* of *every* biweekly contribution: a 10-asset portfolio pays $10 on a $500 contribution (2 %/yr of contributions) — so the cost model alone can make portfolios lose to single assets. Real investors batch, rotate purchases, use fractional shares, or accumulate cash. The engine has no notion of order batching, minimum order size, or idle cash, so there is no way to model the mitigation. |
| D8 | **M** | `data.py:108` (`price_matrix` inner join) | **A young asset silently truncates the whole study.** `join="inner"` + `dropna()` means adding `SOL-USD` (2020) to a 2010–2025 portfolio silently shortens *every* series to SOL's history. No warning, no report of the effective window. Should be an explicit, surfaced decision. |
| D9 | **M** | `metrics.py:95-104` | `rolling_sharpe`/`rolling_volatility` hardcode 252 periods/year and a 126-observation window, while `performance_metrics` correctly measures periods-per-year from the data. Crypto rolling charts are therefore annualized wrongly (~√(365/252) ≈ 1.2× off). |
| D10 | **M** | `metrics.py:172-176` | `performance_metrics` returns `{}` when data is short; callers drop the row or print a generic message. Silent partial results — should be a typed "insufficient data" outcome with the reason. |
| D11 | **M** | `report.py:160`, `cli.py:_run_portfolio` | The report's headline tiles assume `portfolio_metrics.iloc[0]` is the dynamic strategy — an ordering coupling to dict insertion order in a different module. |
| D12 | **M** | `metrics.py:risk_reward_score` | The default asset ranking (`comparison.csv` sort, report headline) is a non-standard heuristic with two hardcoded 0.7 "suspicion" penalties. It is honestly documented, but it drives the primary user-visible ordering. Demote to one optional lens among standard ones (Sharpe, Sortino, Calmar, after-tax real XIRR). |
| D13 | **M** | `simulation.py:net_of_commission`, `net_of_fx` | Costs are silently clamped at zero (`max(gross − fee, 0)`): if fees exceed a contribution, the money vanishes with no diagnostic. Also `invested` never includes fees, so `total_return_pct` quietly blends "market loss" and "fees paid". A real ledger needs a cash account and explicit fee/tax expense lines. |
| D14 | **L** | `cli.py:_add_common` | `--end` defaults to the hardcoded year `2025` (today: 2026). Defaults should be relative ("last full year"). |
| D15 | **L** | `robustness.py`, `validation.py` | Rolling robustness only covers single-asset DCA (not portfolios); walk-forward CV only scores Sharpe. Both should accept the strategy and objective as parameters. |
| D16 | **L** | everywhere | No parallelism and no retry/backoff. The default in-sample grid is 4×4×4 = 64 sequential simulations; yfinance failures are fatal per ticker. |
| D17 | **L** | `tests/` | `cli.py`, `report.py`, `plots.py` have **zero** test coverage — no smoke test that `run` completes or that the report renders. No golden-file regression test, so a refactor cannot be proven output-preserving. |
| D18 | **L** | repo root | `legacy/` (3,708 lines, mixed-language), `venv/`, `.pytest_cache/`, `.DS_Store`, and a stale `simulation_results_v2/` all sit in the root. `requirements.txt` duplicates `pyproject.toml`. |

### 4.3 Structural limits (not bugs — the reason a rewrite is warranted)

- **L1 — No lots, no cash, no ledger.** State is `holdings: np.ndarray` plus an
  average-cost scalar per asset. Every real tax rule needs *tax lots* (acquisition
  date, quantity, cost in base currency) and a *cash account* (uninvested cash, fees,
  dividends received, tax paid, withdrawals). Without them, FIFO/LIFO/specific-lot
  selection, holding-period rules, wash-sale-style rules, loss carryforward, and
  dividend taxation are all unimplementable. **This is the single biggest change.**
- **L2 — Single currency.** Everything is USD. The owner earns in a non-USD currency,
  spends in it, and (in Ukraine) computes taxable gains in UAH at the official rate on
  the **transaction dates** — so a position can post a taxable gain in UAH while losing
  money in USD. FX is currently a fee, not an exposure.
- **L3 — Total-return prices hide the taxable event.** `auto_adjust=True` folds
  dividends into the price. Dividends are the *taxed* cash flow (and the withheld one).
  The engine needs price series **and** distribution series, and must reinvest them
  explicitly, net of withholding.
- **L4 — Accumulation only.** No withdrawal phase, no goal ("can I live on this?"), no
  safe-withdrawal-rate or depletion analysis. Yet "what do I get out at the end, after
  exit tax" is the question the tax model exists to answer.
- **L5 — Static artifacts.** Results are PNGs and CSVs, produced by a CLI, with the
  computation intertwined with formatting in `cli.py`. Nothing can be driven
  interactively, and no result is machine-readable.
- **L6 — No reproducibility manifest.** Results carry no record of parameters, code
  version, or data vintage; caches are silently mutable (see D2). Two runs can differ
  with no way to see why.

---

## 5. The target: what "the real thing" means

### 5.1 Core: an event-sourced ledger with tax lots (P0)

Replace the array-based engine with a deterministic event loop over a single ordered
event stream, keeping a full audit trail. Every number in the UI must be traceable to
events.

**Entities:** `Account` (cash balances per currency, broker, jurisdiction) ·
`Lot` (asset, quantity, acquisition date, cost in trade currency **and** base
currency, FX rate used) · `Position` (list of lots) · `Transaction` (typed, below) ·
`TaxYear` (realized gains/losses, income, credits, computed liability, payment date).

**Event types:** `Income` (salary → base cash) · `FxConversion` · `Buy` · `Sell` ·
`Dividend` (gross, withheld, net) · `Interest` · `Fee` · `TaxPayment` · `Withdrawal` ·
`Rebalance` (expands to Sell/Buy) · `CorporateAction` (split, ticker change, delisting).

**Invariants** (assert in tests, not just docs):
- Cash conservation: `Σ inflows − Σ outflows = cash balance`, per currency, every day.
- Lot conservation: `Σ lot.quantity = position.quantity`; a sale consumes lots by the
  configured method and never produces negative quantities.
- Basis conservation: `Σ lot.cost = position basis`; realized gain =
  `proceeds − consumed basis − allocated fees`, in **both** currencies.
- Determinism: same scenario + same data snapshot ⇒ byte-identical results.

Keep the existing vectorized engine as an explicit **"fast mode"** for cost- and
tax-free exploration (grid search, rolling windows over hundreds of configurations),
and add a test asserting the two agree to a tight tolerance when costs and taxes are zero.

### 5.2 Multi-currency (P0)

- A scenario declares a **base currency** (what the investor earns and spends in) and
  each asset's **trade currency**.
- Real (inflation-adjusted) values use the **base-currency CPI** (UA CPI, HICP for
  Cyprus, US CPI), not always US CPI.
- Daily FX rates from a real source; for Ukraine, the **NBU official rate** on the
  transaction date is what tax law refers to — model rate *sources* as first-class and
  allow "tax rate source ≠ market rate source".
- Report the outcome in base currency **and** trade currency, and decompose the return
  into `asset return × FX return × cost drag × tax drag` so the user can see how much
  of the result was currency.

### 5.3 The tax engine (P0 — the defining feature)

Design goal: **jurisdiction rules as declarative, versioned, user-inspectable data
plus a small number of well-named hooks** — never rates hardcoded in the simulation
path. A user must be able to read the rule pack, disagree with a number, override it,
and see the result change.

**Taxable events the engine must express:**

| Event | Must model |
|---|---|
| Disposal of securities | Realized gain/loss per lot, in base currency, at transaction-date FX; lot-selection method (FIFO / LIFO / average / specific / highest-cost); netting of gains against losses within the tax year; **loss carryforward** across years |
| Dividends | Gross, **source-country withholding** (US: 30 % default, 15 % under a treaty with a filed W-8BEN — model the form status as a scenario flag), residence-country top-up, and any foreign-tax credit; distinguish qualified/ordinary or per-instrument-type where a jurisdiction does |
| Interest | Deposit/T-bill/money-market interest as taxable income — so benchmarks are compared after tax (fixes D6) |
| Rebalancing | A disposal like any other; the engine should be able to answer "what did rebalancing cost me in tax?" |
| Final liquidation / withdrawal | Disposal of the remaining lots, not a flat `rate × (final − invested)` (fixes D4) |
| Surcharges & contributions | Levies computed on a different base than the main tax (e.g. a military levy; health-system contributions with annual caps) — these are *not* just "add to the rate" |
| Timing | Liability accrues to a tax year; payment happens on a configurable date in the following year, **from cash** (fixes D5). If cash is insufficient, model the forced sale — and tax it. |
| Allowances | Annual exemptions/thresholds, minimum holding periods, and per-instrument exclusions |

**Rule-pack shape** (illustrative — the point is that this is *data*, with provenance
and effective dates, not code):

```toml
[jurisdiction.ukraine]
display_name   = "Ukraine (tax resident)"
base_currency  = "UAH"
tax_year       = "calendar"
payment_due    = "07-31"              # of the following year
fx_source      = "NBU-official"       # rate used for tax computation
lot_method     = "fifo"
loss_carryforward = true              # verify: scope and duration
source = "Tax Code of Ukraine, art. 170.2 — VERIFY against current text"
effective_from = "2025-01-01"

  [[jurisdiction.ukraine.rule]]
  applies_to = "capital_gain"          # 'investment profit'
  rate = 0.18
  surcharge = { name = "military levy", rate = 0.05, base = "same" }
  note = "netting of investment losses within the year; VERIFY carryforward"

  [[jurisdiction.ukraine.rule]]
  applies_to = "foreign_dividend"
  rate = 0.09                          # VERIFY: differs from the 18% gains rate
  surcharge = { name = "military levy", rate = 0.05, base = "same" }
  foreign_tax_credit = true            # US withholding creditable? VERIFY

[jurisdiction.cyprus_nondom]
display_name = "Cyprus (non-domiciled resident)"
base_currency = "EUR"
  [[jurisdiction.cyprus_nondom.rule]]
  applies_to = "capital_gain"
  rate = 0.0                           # securities exempt — VERIFY scope
  [[jurisdiction.cyprus_nondom.rule]]
  applies_to = "dividend"
  rate = 0.0                           # non-dom SDC exemption — VERIFY duration
  contribution = { name = "GHS/GESY", rate = 0.0265, annual_cap = true }  # VERIFY
```

> ⚠️ **Legal accuracy is a hard requirement and cannot come from the model's memory.**
> The current built-ins (`ukraine-ibkr` = 18 % + 5 % on gains; `cyprus-ibkr` = 0 %) are
> the author's approximations. Every rate in a shipped rule pack must carry a
> `source`, an `effective_from`, and a `verified_on` date, must be rendered in the UI
> next to the number it produces, and the app must show a prominent
> "verify against current law / consult a tax adviser" notice. Treat every
> `VERIFY` marker above as a task for a human, not something to fill in confidently.
> Prefer shipping fewer jurisdictions, well-sourced, over many guessed ones.

**Required outputs:** effective tax rate; tax paid per year; after-tax real XIRR in base
currency; **tax drag decomposition** (withholding vs realized gains vs rebalancing vs
exit); and a counterfactual — "the same plan under jurisdiction B / with no
rebalancing / holding to the exemption threshold". The comparison of *tax scenarios*
is the product's unique value; make it a first-class view.

### 5.4 Broker & cost model (P1)

Extend beyond flat per-leg fees: tiered/fixed commission schedules (per-share with
min/max, per-order minimums), **order batching and minimum order size**, fractional-share
availability per broker, FX conversion tiers, custody/inactivity fees, ETF expense
ratios (without double-counting what adjusted closes already include), and
bid/ask or slippage as an option. Fixes D7 and makes portfolio-vs-single-asset
comparisons honest.

### 5.5 Life-cycle realism (P1)

- **Contributions:** amount in base currency, arbitrary cadence (biweekly / monthly /
  semi-monthly), salary growth or CPI indexation, bonus lump sums, pauses, and a
  contribution *cap* by affordability.
- **Cash buffer:** idle cash earning a configurable deposit rate; contributions need
  not be fully invested the same day.
- **Withdrawal phase:** a target date, then withdrawals (fixed real amount, % of
  portfolio, or a safe-withdrawal-rate rule), with the tax of each withdrawal
  computed via lot selection — and depletion/ruin probability reported.
- **Glide path:** age- or date-based target weights (e.g. bonds ↑ over time) as an
  alternative to Sharpe-optimization.

### 5.6 Analytics (P1, mostly port existing)

Keep all of §4.1. Add: after-tax real metrics as the *primary* series;
bootstrap/block-bootstrap and Monte Carlo forward projections (clearly labelled
"not a forecast"); rolling robustness generalized to portfolios; attribution
(asset / FX / cost / tax); and a tax-lot-level "what if I sold now" view. Extend
walk-forward CV to accept an arbitrary objective (D15) — including after-tax XIRR,
which is the only objective the user actually cares about.

### 5.7 Data layer (P0)

- Pluggable providers behind one interface (`prices`, `distributions`, `fx`, `cpi`,
  `rates`), so yfinance is one implementation, not the architecture.
- **Prices *and* distributions separately** (fixes D1/L3); store `close`,
  `adj_close`, `dividend`, `split` and let the engine choose. Refuse to compare a
  price index with a total-return series without labelling it.
- **Never cache fallback/synthetic data** (fixes D2). Cache entries carry
  provenance: source, fetch time, and a `synthetic` flag; synthetic data is rejected
  unless explicitly requested.
- Retry with backoff; per-asset failures degrade gracefully and are *reported*.
- A small **vendored offline dataset** so the demo, tests, and CI run with no network,
  deterministically.
- A **snapshot/manifest** per run: scenario hash, code version, provider + data
  vintage per series, so any result can be reproduced or diffed (fixes L6).

### 5.8 Interactivity & UX (P0 for "usable")

Structure the app around the five original questions, not around the code's modules.

1. **Plan** — a form: income and currency, contribution amount and cadence, horizon,
   jurisdiction + broker (with the rule pack visible and editable), assets and mix.
2. **Result** — one headline sentence in base currency, after tax, in today's
   purchasing power; then the money-vs-contributions chart with benchmark lines
   (cash, deposit/T-bills after tax) and the drawdown ribbon.
3. **Cost & tax breakdown** — a waterfall: gross market outcome → fees → FX →
   withholding → realized-gains tax → exit tax → what you keep. Every bar clicks
   through to the underlying events and the rule that produced it.
4. **Risk** — drawdown, underwater duration, VaR/CVaR, monthly heatmap, and the
   **rolling-window distribution** ("if you'd started at a random time, here's the
   spread and the realistic bad case") — the single most honest view in the tool.
5. **Compare** — scenarios side by side: assets, mixes, jurisdictions, rebalancing
   on/off, contribution levels. Saved, named, shareable, diffable.
6. **Explain** — every metric has a one-line plain-language definition on hover and a
   link to the methodology; every rate shows its source and verification date.

Suggested shape (owner's call — see §9): Python core (keep pandas/numpy/scipy and the
tested logic) exposed as a typed API, driven by a local web UI. Charts must be
interactive (zoom, hover, series toggles). Keep the CLI for scripting and batch runs;
add JSON output. If a static shareable artifact is wanted, generate it *from* the same
result objects rather than a parallel reporting path.

---

## 6. Proposed architecture

```
core/                     pure, deterministic, no I/O, no plotting
  scenario.py             typed scenario model + validation + hashing
  ledger.py               events, lots, cash accounts, invariants
  engine.py               event loop: income → fx → buy/sell → dividend → fee → tax
  strategies/             dca, fixed_weight, glide_path, walk_forward_mpt, withdrawal
  tax/
    rules.py              rule-pack loader, effective dates, provenance
    events.py             taxable-event classification
    engine.py             per-tax-year computation: netting, carryforward, credits,
                          surcharges, allowances, payment timing
    packs/                ukraine.toml, cyprus.toml, us.toml, ... (data + sources)
  brokers/                commission schedules, fx tiers, fractional support, batching
  metrics/                ported from terezy/metrics.py (+ after-tax variants)
  analysis/               rolling windows, walk-forward CV, bootstrap/MC, attribution
data/                     providers (prices, distributions, fx, cpi, rates), cache
                          with provenance, offline snapshot, run manifest
api/                      typed result schema (JSON), scenario CRUD, run orchestration
ui/                       interactive app consuming api/
cli/                      thin wrapper over api/ (scriptable, JSON out)
tests/                    unit + invariant + golden + worked tax examples
docs/                     METHODOLOGY.md (port), TAX_MODEL.md (new), sources/
```

**Rules:** the core never touches the network, never plots, and never formats;
orchestration lives in `api/`, not in the CLI (fixes the `cli.py` bloat); every
scenario is serializable and hashable; every result carries its manifest.

---

## 7. Acceptance criteria

Port the existing 64 tests (they encode §4.1) and add:

**Ledger invariants** — cash conservation per currency per day; lot and basis
conservation; no negative quantities; realized gain = proceeds − basis − fees in both
currencies; determinism (same scenario + snapshot ⇒ identical output hash).

**Equivalence** — with zero fees and zero taxes, the ledger engine matches the
vectorized fast path within 1e-9 relative; with zero taxes but nonzero fees, it matches
a closed-form fee-drag calculation.

**Tax correctness — worked examples, hand-computed, in the repo, one per rule pack:**
- FIFO vs LIFO vs average on a three-lot position with a partial sale, and the tax
  each method produces.
- A dividend with 15 % withholding plus residence top-up plus foreign-tax credit ⇒
  the net cash and the credit carried.
- A losing year followed by a winning year ⇒ loss netting and carryforward applied.
- A position that gains in base currency while losing in trade currency (pure FX gain)
  ⇒ taxable gain > 0 with a negative USD return. **This test is the reason the rewrite exists.**
- Tax paid from cash in the following tax year; insufficient cash ⇒ forced sale, itself taxed.
- Exit-tax path: liquidation taxes only unrealized gains, never gains already taxed
  (regression test for D4).
- Same scenario under jurisdiction A vs B ⇒ only the tax terms differ; gross market
  outcome is bit-identical.

**Regression against the defects** — one test per D1–D18: e.g. a FRED outage never
writes to cache and never silently reuses synthetic data (D2); `--lookback 2.5`
either works or is rejected at parse time, never crashes mid-run (D3); a benchmark
comparison applies interest tax (D6); a portfolio containing a young asset reports its
truncated effective window (D8); rolling metrics use measured periods-per-year (D9).

**Smoke/golden** — a full end-to-end run on the offline snapshot completes and matches
a checked-in golden result file; the report/UI renders without error (fixes D17).

---

## 8. Suggested phasing

| Phase | Deliverable | Contains |
|---|---|---|
| **P0** | Correct after-tax core | Ledger + lots + cash (5.1) · multi-currency (5.2) · tax engine + Ukraine/Cyprus packs with sources (5.3) · data layer with distributions and provenance (5.7) · fixes D1–D6, D8 · invariant + worked-example tests |
| **P1** | Usable | Interactive app around the five questions (5.8) · typed JSON results · scenario save/compare · cost/tax waterfall · broker model (5.4) · fixes D7, D9–D13 |
| **P2** | Real-life planning | Withdrawal/decumulation, glide paths, cash buffer, salary indexation (5.5) · bootstrap/Monte Carlo · attribution · generalized rolling robustness and walk-forward CV over after-tax objectives (5.6) |
| **P3** | Polish | More jurisdictions/brokers (each with sources) · shareable export · parallelism (D16) · repo hygiene (D18) · legacy archived |

Each phase must land with green tests and updated methodology docs. The project's
transparency principle means **an undocumented formula is an incomplete feature.**

---

## 9. Decisions needed from the owner

1. **Base currency and jurisdictions to ship first.** UAH + Ukraine, EUR + Cyprus, or
   both? Which is the primary scenario (it decides the default rule pack, CPI series,
   and FX source)?
2. **Tax-rule verification.** Who confirms the rates and rules — the owner from primary
   sources, or a tax adviser? Nothing legal should be filled in by the implementing
   agent from memory. Until verified, ship rates as clearly-marked, user-editable
   estimates.
3. **Deployment shape.** Local desktop/web app for one user, or something shareable
   with others (which raises the bar on the "not advice" framing and on data licensing)?
4. **Stack.** Keep the Python core and add a web UI, or move the whole thing to a
   single-language stack? Recommendation: keep Python — the tested financial logic is
   the asset, and rewriting it would forfeit §4.1.
5. **Dividend data source.** yfinance distributions are adequate for exploration but
   patchy historically. Is a paid/alternative source acceptable for the accuracy that
   dividend *taxation* requires?
6. **Scope of the withdrawal phase.** Full retirement-planning (P2), or just
   "liquidate at the end and pay exit tax" (P0)?
7. **Fate of `legacy/`.** Delete, or keep as an archived reference branch/tag?

---

## 10. Appendix

- **Formulas and assumptions as currently implemented:** `docs/METHODOLOGY.md` — port
  it forward, extend it with the tax model; it is the transparency principle in practice.
- **The 12 legacy bugs and their fixes:** `docs/LEGACY_REVIEW.md` — the list of
  mistakes not to repeat.
- **Original goal statement (Ukrainian):** `legacy/SPECIFICATION.md` §"Мета проекту".
- **Current cost/tax profiles:** `terezy/profiles.py` + `profiles.toml` — the shape to
  generalize into rule packs.
- **Example current output:** `simulation_results_v2/` (2018–2025, $500/2wk:
  `comparison.csv`, `rolling_summary.csv`, `report.html`) — useful as a
  before/after reference for what the rewrite must at least match.
- **Test suite:** `tests/` — 64 tests, no network required, ~3 s. The contract to preserve.
