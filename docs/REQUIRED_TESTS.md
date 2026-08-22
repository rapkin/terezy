# Required tests

This is the standing definition of done referenced by the constitution
(Principle V, and "Provenance of behaviour" under Engineering Standards).

Per owner decision **D-C**, terezy is a fresh implementation. No code was carried over
from the predecessor project. The knowledge that lived in its test suite is carried
over here as **requirements**: every item below must be independently re-derived and
re-tested in this repository. A row without a test is an open gap, and this file is
where that is visible.

**Status legend** — `[ ]` not started · `[~]` partially covered · `[x]` covered, test
path recorded in the Test column.

Sources: `docs/reference/REWRITE_BRIEF.md` §4.1 (preserve), §4.2 (defects), §7
(acceptance); `docs/reference/SIMULATOR_SPEC.md` §9 (acceptance).

---

## A. Preserved correctness behaviours

From `REWRITE_BRIEF.md` §4.1. These were expensive to get right in the predecessor
and must not be "simplified" here. Each is a behaviour, not a code port.

| # | Behaviour | Test |
|---|---|---|
| A1 | Flow-adjusted (time-weighted) returns `r_t = (V_t − F_t)/V_{t−1} − 1` for every risk metric. A DCA value series is never `pct_change()`d. Canonical test: a flat-price asset with contributions yields exactly 0 return and 0 volatility. | `[ ]` |
| A2 | XIRR reported separately as the money-weighted outcome. `(final/invested)^(1/y)` is not a DCA CAGR and must not reappear. | `[ ]` |
| A3 | Sortino uses the 2nd lower partial moment over **all** observations, `√(mean(min(r−rf,0)²))` — never `std(r[r<0])`. | `[ ]` |
| A4 | Optimizer input is asset price returns, never portfolio values. | `[ ]` |
| A5 | No look-ahead: static weights come from the warm-up window only; walk-forward weights use data strictly before each rebalance date. Test corrupts future data and asserts weights unchanged. | `[ ]` |
| A6 | Paydays map to the next trading day on/after; colliding paydays sum; every compared strategy uses the identical contribution schedule. | `[ ]` |
| A7 | T-bills / deposits accrue ACT/365 over calendar-day gaps — weekends earn interest. | `[ ]` |
| A8 | Periods-per-year measured from the data (~252 equities, ~365 crypto), never assumed. | `[ ]` |
| A9 | Infeasible constraints raise instead of silently returning an invalid portfolio. | `[ ]` |
| A10 | Walk-forward CV with an equal-weight baseline and an explicit train→test degradation number. The honest verdict ("tuning does not beat 1/N out of sample") is a feature. | `[ ]` |
| A11 | Rolling-window robustness as the antidote to single-backtest storytelling. | `[ ]` |
| A12 | Only completed calendar years are cached; the current year is always refetched. | `[ ]` |

## B. Defect regressions

From `REWRITE_BRIEF.md` §4.2 — one test per defect, so the class of mistake cannot
recur. Severity is the predecessor's: **H** wrong numbers or crash, **M** misleading,
**L** papercut.

| # | Sev | Regression to assert | Test |
|---|---|---|---|
| B1 | H | Price index vs total-return series are never ranked in one table without labelling. Prices and distributions are separate series. | `[ ]` |
| B2 | H | A provider outage never writes to cache and never silently reuses synthetic data. Cache entries carry provenance and a synthetic flag. | `[ ]` |
| B3 | H | Non-integer year offsets either work or are rejected at parse time — never crash mid-run. | `[ ]` |
| B4 | H | Exit/liquidation taxes only unrealised gains, never gains already taxed at a rebalance. | `[ ]` |
| B5 | H | Tax is assessed to a tax year and paid from cash on the due date, not deducted from the position at trade time. Per-disposal basis, loss offset, and carryforward all modelled. | `[ ]` |
| B6 | M | Benchmarks are compared after tax: deposit and T-bill interest is taxable income. | `[ ]` |
| B7 | M | Per-leg minimum commission does not unrealistically penalise diversification; order batching, minimum order size and idle cash are modelled. | `[ ]` |
| B8 | M | A young asset never silently truncates the study window; the effective window is reported. | `[ ]` |
| B9 | M | Rolling metrics use measured periods-per-year, not a hardcoded 252. | `[ ]` |
| B10 | M | Insufficient data returns a typed outcome carrying its reason, never an empty result that callers drop. | `[ ]` |
| B11 | M | Report/API headline figures are selected explicitly, never by dict insertion order. | `[ ]` |
| B12 | M | No non-standard composite score drives the primary user-visible ordering. | `[ ]` |
| B13 | M | Costs are never silently clamped at zero; fees are explicit ledger lines and never blended into "market loss". | `[x]` `tests/invariants/test_no_silent_clamping.py` |
| B14 | L | Date defaults are relative ("last full year"), never a hardcoded year. | `[ ]` |
| B15 | L | Rolling robustness covers portfolios, and walk-forward CV accepts an arbitrary objective — including after-tax XIRR. | `[ ]` |
| B16 | L | Per-asset provider failures degrade gracefully, are retried with backoff, and are reported. | `[ ]` |
| B17 | L | API and CLI have smoke coverage, and a golden result file makes a refactor provably output-preserving. | `[~]` `tests/golden/test_end_to_end_ovdp.py` — golden half done; API and CLI do not exist yet (owner decision D-B) |
| B18 | L | Repo hygiene: no vendored virtualenv, caches, or stale result directories tracked. | `[x]` `.gitignore` |

## C. Ledger invariants (property-based)

Constitution Principle IV. These are generative tests over event streams, not example
tests, and they are compliance tests for the constitution: they may not be skipped,
xfailed, or deleted without an amendment.

| # | Invariant | Test |
|---|---|---|
| C1 | Cash conservation: `Σ inflows − Σ outflows = cash balance`, per currency, every day. | `[x]` `tests/invariants/test_ledger_conservation.py` |
| C2 | Lot conservation: `Σ lot.quantity = position.quantity`; a sale consumes lots by the configured method and never produces a negative quantity. | `[x]` `tests/invariants/test_ledger_conservation.py` |
| C3 | Basis conservation: `Σ lot.cost = position basis`; realised gain = proceeds − consumed basis − allocated fees, in **both** currencies. | `[x]` `tests/invariants/test_ledger_conservation.py` |
| C4 | Determinism: same scenario + same snapshot ⇒ identical output hash. | `[x]` `tests/invariants/test_determinism.py` |
| C5 | Currency safety: values in different currencies can never be combined. | `[x]` `tests/invariants/test_currency_safety.py` |
| C6 | Every displayed figure resolves to ledger events and to the rule that produced it. | `[x]` `tests/invariants/test_traceability.py` |

## D. Contractual instruments

`SIMULATOR_SPEC.md` §9. Hand-computed worked examples, arithmetic checked in.

| # | Example | Test |
|---|---|---|
| D1 | OVDP bought at a stated price and held to maturity reproduces a hand-computed coupon and principal schedule, and pays **zero** tax under the exempt class. | `[x]` `tests/worked_examples/test_ovdp_schedule.py` |
| D2 | Coupon reinvestment matches a hand-computed two-period example. (Original wording said "into the then-current yield **curve**"; there is no curve in feature 001, so reinvestment is at par — the only price that earns the declared rate. A curve remains a later feature.) | `[x]` `tests/worked_examples/test_coupon_reinvestment.py` |
| D3 | A restructuring scenario with a 40% haircut and two-year delay produces the hand-computed shortfall. | `[ ]` |

## E. Tax

| # | Example | Test |
|---|---|---|
| E1 | An Inzhur distribution taxed at 9% + 5% and a redemption of the same units taxed at 18% + 5%, both in one run from one instrument — the two classes must not collide. | `[ ]` |
| E2 | A loss year followed by a gain year nets correctly; a run that omits the loss-year declaration forfeits the carryforward. **Both branches tested.** | `[ ]` |
| E3 | Foreign dividend with 15% withholding: PIT credit applied, military levy **not** credited. | `[ ]` |
| E4 | Crypto scenarios `current_practice`, `draft_18_5`, `draft_transitional_5_5` produce three different hand-checkable results from identical market data. | `[ ]` |
| E5 | Every tax figure renders with `source` and `verified_on`; an empty `verified_on` marks the figure **and everything derived from it**. | `[x]` `tests/contract/test_provenance_propagation.py` |
| E6 | Lot-selection methods (FIFO / LIFO / average / specific) on a three-lot position with a partial sale each produce their own hand-computed tax. | `[ ]` |
| E7 | Tax paid from cash in the following tax year; insufficient cash forces a sale, which is itself taxed. | `[ ]` |
| E8 | The same scenario under jurisdiction A vs B differs only in the tax terms; the gross market outcome is bit-identical. | `[ ]` |
| E9 | A residency change mid-simulation is applied by date, including positions held across the change. | `[ ]` |
| E11 | A **zero** tax figure distinguishes *exempted* from *not applicable* when rendered. The engine already separates them — a taxable event's zero cites its tax class, a non-taxable row's zero cites nothing because there is nothing to cite — but a reader looking at a schedule table sees `0.00` on every row either way. A presentation requirement for the waterfall (spec §5.3), recorded here so the distinction the engine preserves is not thrown away at the last step. | `[ ]` |
| E10 | A rate declared as a **dated schedule** changes on its effective date, so a legislated change is modelled rather than requiring a rebuild. **Known gap:** as of feature 001 the tax schema carries a scalar rate per class, not a schedule, so `data/README.md` rule 3 and `SIMULATOR_SPEC.md` §4.5.1 are not yet satisfied. Closing it is a schema change plus a core change. | `[ ]` |

## F. FX, display currency, and asymmetry

| # | Example | Test |
|---|---|---|
| F1 | **A position flat in USD across a devaluation produces a positive taxable gain in UAH.** This test is the reason the rewrite exists. | `[ ]` |
| F2 | Switching display currency changes no realised amount, no tax figure, and no after-tax UAH ranking. | `[ ]` |
| F3 | Historical series convert at per-date rates, never at today's rate. | `[ ]` |
| F4 | The real-terms view uses UA CPI in the UAH display and US CPI in the USD display. | `[ ]` |
| F5 | Cash-vs-non-cash channel selection changes the result and is visible in the attribution. A single mid-rate is never used for a transaction. | `[ ]` |

## G. Streams and routes

| # | Example | Test |
|---|---|---|
| G1 | The same crypto purchase funded from the UAH salary and from the USD income yields different net positions, differing by exactly the hand-computed ramp cost. (The two paths deploy the same *value* to the same destination venue: 10 000 UAH at a P2P price of 45 arrives as 222.222222 USD, while the same 10 000 stated in dollars at the reference — 238.095238 USD — arrives untouched. The gap of **15.873015873 USD** is 666.666666 UAH at the reference, which is exactly the spread the hryvnia path paid, and 1/15 = 6.67% of what the dollar stream deployed.) | `[x]` `tests/worked_examples/test_two_streams.py` |
| G2 | A P2P premium of +3 UAH at a stated reference rate reproduces the `SIMULATOR_SPEC.md` §4.3.1 percentage. (Reproduced as the **rate-space spread** `3/42 = 7.14%`, reported beside the **cost** `3/45 = 6.67%` — see FR-004's correction. §4.3.1 labels its own arithmetic illustrative, so it defines a spread over the reference rate and not a fraction of money.) | `[x]` `tests/worked_examples/test_ramp_p2p_premium.py` |
| G3 | A plan exceeding a monthly cap queues the excess per the fallback policy and reports each occurrence; total deployed equals the cap, never the plan. ("Queues" is §4.3.4's own wording for *hold as cash* — not carrying the excess into next month's capacity, which no policy in the closed set expresses. Of the four policies, feature 002 implements **hold as cash, redirect, skip**; *place on deposit* needs a deposit instrument and fails at load naming the feature that will bring it.) | `[x]` `tests/worked_examples/test_monthly_cap.py` — 150 000 planned against a declared 100 000 card limit deploys 100 000 and reports 50 000 held as cash; a second 80 000 over a **different route on the same card** deploys 0 and reports 80 000, because the limit belongs to the rail (`tests/invariants/test_capacity_accumulator.py` is the accumulator property). *Place on deposit* fails by name. |
| G4 | A regime transition on the war-end date switches the route set; round-trip cost drops by exactly the hand-computed difference. (A regime is **scenario** data and a leg window is **route** data — the split is epistemic, research.md D8: a window is an observed fact with a source, a transition date is an assumption nobody can source. The regime narrows the *candidates*, so an assumed exclusion never arrives as a `RouteUnusable` naming a declared field.) | `[x]` `tests/worked_examples/test_regime_transition.py` — the same 10 000 UAH, the same reference rate and the same channels either side: the wartime P2P corridor costs **2/15 = 13.3333%** round trip (1 333.33 UAH), the normalized bank corridor **2/85 = 2.3529%** (235.29 UAH), a drop of **28/255 = 10.9804%**, or **1 098.04 UAH**. `tests/unit/test_transition_is_an_assumption.py` holds the other half: `is_assumption` admits one value and cannot be omitted, a regime carries no date and a leg carries no assumption marker, and `core/routes/` never imports `core/scenarios/`. |
| G5 | Two variants of one route differing only in conversion count rank in the expected order. | `[ ]` |
| G6 | No comparison reports a one-way cost as if it were round-trip. | `[ ]` |

## H. The framework surface

Compliance tests for Principle II. May not be skipped without an amendment.

| # | Example | Test |
|---|---|---|
| H1 | Adding a new instrument, route, tax class and jurisdiction **in data only** — no engine edit — runs the full pipeline and appears in the comparison. | `[ ]` |
| H2 | A malformed or unknown field in any data file fails loudly at load time, naming file and field; it never silently defaults. | `[x]` `tests/contract/test_declaration_loading.py` |
| H3 | Every data file's values round-trip through the run manifest, so a result traces to the exact configuration that produced it. | `[ ]` |
| H4 | Architecture boundaries hold: the core imports no I/O, no network, no framework, and nothing from a layer above it. | `[x]` `tests/contract/test_architecture_boundaries.py` |

## I. The decision layer

| # | Example | Test |
|---|---|---|
| I1 | Feasibility pruning drops infeasible candidates with a recorded reason, and the count of dropped candidates is reported. | `[ ]` |
| I2 | Two objectives over the same candidate set produce different rankings, and each run's manifest records which objective was used. | `[ ]` |
| I3 | A binding constraint reports a non-zero shadow cost; a non-binding one reports zero. | `[ ]` |
| I4 | The naive baseline (100% OVDP; 50/50 OVDP + VWCE) is always scored and always shown, and a synthetic case where nothing beats it produces the honest verdict. | `[ ]` |
| I5 | Stability: perturbing one assumed input by 1% must not silently change the top recommendation; if the ranking flips, the run is labelled unstable. | `[ ]` |
| I6 | Indifference band: a synthetic case where a range of allocations scores within noise reports the band, not a point. No allocation is ever reported to sub-percent precision. | `[ ]` |
| I7 | "Sometimes best" and "never bad" are computed separately, and a synthetic case where they differ shows both. | `[ ]` |

## J. Goals, seed, liquidity, honesty

| # | Example | Test |
|---|---|---|
| J1 | The three goal modes are mutually consistent: solving for date from (contribution, sum) and then for sum from (contribution, that date) returns the original sum. | `[ ]` |
| J2 | A seed lot with a known basis produces the hand-computed gain on disposal; a basis-estimated seed marks every downstream tax figure. | `[ ]` |
| J3 | Redemption outside an Inzhur window is refused, or executed at the stated haircut when allowed — taxed correctly either way. | `[ ]` |
| J4 | A lock-up longer than the horizon is a feasibility error, not a silent simulation. | `[ ]` |
| J5 | Correlated stress hits OVDP, Inzhur and UAH simultaneously, never as independent draws. | `[ ]` |
| J6 | No Sharpe ratio or volatility figure is emitted for an assumption-driven instrument. | `[ ]` |

## K. Equivalence and golden results

| # | Example | Test |
|---|---|---|
| K1 | With zero fees and zero taxes, the ledger engine matches the vectorized fast path within the project tolerance. | `[ ]` |
| K2 | With zero taxes but nonzero fees, the ledger engine matches a closed-form fee-drag calculation. | `[ ]` |
| K3 | A full end-to-end run on the offline snapshot completes and matches a checked-in golden result file. | `[x]` `tests/golden/test_end_to_end_ovdp.py` |
| K4 | Tests never reach the network; CI runs with networking unavailable. | `[x]` `tests/conftest.py`, `tests/contract/test_no_network.py` |

---

## On tolerance

Owner decision **D-A**: money is `float64`. The specification's phrasing "reproduces a
hand-computed schedule **exactly**" is therefore implemented as "within the project
tolerance", which is defined in exactly one place and imported. A test that invents
its own tolerance is a defect; a test that needs a looser one states why at the
assertion site (constitution, Principle IV).
