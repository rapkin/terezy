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
| E1 | An Inzhur distribution taxed at 9% + 5% and a redemption of the same units taxed at 18% + 5%, both in one run from one instrument — the two classes must not collide. | `[x]` `tests/worked_examples/test_two_tax_classes.py`, with the isolation property in `tests/invariants/test_rate_schedule_isolation.py` |
| E2 | A loss year followed by a gain year nets correctly; a run that omits the loss-year declaration forfeits the carryforward. **Both branches tested.** | `[x]` `tests/worked_examples/test_loss_carryforward.py`, with the chain-continuity branches in `tests/contract/test_unsettled_is_labelled.py` |
| E3 | Foreign dividend with 15% withholding: PIT credit applied, military levy **not** credited. | `[ ]` |
| E4 | Crypto scenarios `current_practice`, `draft_18_5`, `draft_transitional_5_5` produce three different hand-checkable results from identical market data. | `[ ]` |
| E5 | Every tax figure renders with `source` and `verified_on`; an empty `verified_on` marks the figure **and everything derived from it**. | `[x]` `tests/contract/test_provenance_propagation.py` |
| E6 | Lot-selection methods (FIFO / LIFO / average / specific) on a three-lot position with a partial sale each produce their own hand-computed tax. | `[x]` `tests/worked_examples/test_four_lot_methods.py`, with the refusals in `tests/unit/test_ledger_failures.py` and the four drawn into the conservation properties in `tests/invariants/test_ledger_conservation.py` |
| E7 | Tax paid from cash in the following tax year; insufficient cash forces a sale, which is itself taxed. | `[ ]` — **first clause closed, second deliberately open.** Tax is assessed to its year and paid from cash on the declared due date of the following year: `tests/worked_examples/test_tax_payment.py`. Insufficient cash produces a typed shortfall report and **sells nothing**: `tests/unit/test_insufficient_cash.py`, with the same three prohibitions asserted over generated scenarios in `tests/invariants/test_no_silent_clamping.py`. The forced sale is an owner-recorded deferral (009 FR-010, `forced-sale-policy` in `specs/features.toml`) — which holdings it would draw on, in what order, sized how, is a portfolio decision the owner reserved, so the row stays open until that feature lands |
| E8 | The same scenario under jurisdiction A vs B differs only in the tax terms; the gross market outcome is bit-identical. | `[ ]` |
| E9 | A residency change mid-simulation is applied by date, including positions held across the change. | `[ ]` |
| E11 | A **zero** tax figure distinguishes *exempted* from *not applicable* when rendered. The engine already separates them — a taxable event's zero cites its tax class, a non-taxable row's zero cites nothing because there is nothing to cite — but a reader looking at a schedule table sees `0.00` on every row either way. A presentation requirement for the waterfall (spec §5.3), recorded here so the distinction the engine preserves is not thrown away at the last step. | `[ ]` |
| E10 | A rate declared as a **dated schedule** changes on its effective date, so a legislated change is modelled rather than requiring a rebuild. **Closed by feature 006:** the scalar rate was removed, not deprecated, and `data/README.md` rule 3 and `SIMULATOR_SPEC.md` §4.5.1 are now satisfied. An event before a schedule's earliest cited entry is a typed refusal rather than a defaulted rate — see `docs/METHODOLOGY.md` §25.2 on why that refusal is what makes an honest schedule writable. | `[x]` `tests/worked_examples/test_rate_schedule_straddle.py`, with the boundary in `tests/unit/test_rate_lookup_boundary.py` and the refusals in `tests/unit/test_schedule_refusals.py`. **Feature 012 exercised the same mechanism a second time, on income rather than on an instrument, against a real statute**: the ФОП військовий збір commences 1 January 2025 under a law that is not the one setting its rate, a projection straddling that date charges 1% from it and refuses by name before it (`tests/unit/test_scheme_refusals.py`), and a legislated change entered as one dated entry takes effect in the next run with no source line changed (`tests/contract/test_scheme_data_only.py`). The row stays flipped and is not re-flipped |

## F. FX, display currency, and asymmetry

| # | Example | Test |
|---|---|---|
| F1 | **A position flat in USD across a devaluation produces a positive taxable gain in UAH.** This test is the reason the rewrite exists. | `[ ]` — **one of its two blockers is gone and the row stays open.** Feature 011 built the official rate: a foreign amount is struck in the tax currency at the series' declared rate for the event's own date, hand-checked in `tests/worked_examples/test_official_rate_base.py`. What is still missing is the **position**: `core.results.project` folds a holding under one currency and sums every charge in it, and a realised gain needs a per-lot basis carried in both currencies with each leg struck at its own date's rate. 011 refuses that case by name rather than converting the gain at one date's rate — which would report zero hryvnia for a position flat in dollars and make this very row unfalsifiable (`tests/unit/test_tax_base_in_the_tax_currency.py`). Tracked as `fx-tax-asymmetry-f1`. |
| F2 | Switching display currency changes no realised amount, no tax figure, and no after-tax UAH ranking. | `[ ]` — the tax-figure half is established **before** the switch exists, so the row cannot be closed later by a feature that never checked it: no module under `core/tax/` reads a display choice, and a struck base takes its currency from the jurisdiction's declaration and from nowhere else (`tests/contract/test_the_rate_you_are_taxed_at.py::TestNoDisplayChoiceCanReachATaxFigure`, measured 2026-08-29). The realised-amount and ranking halves need the switch. |
| F3 | Historical series convert at per-date rates, never at today's rate. | `[ ]` — **deliberately not attempted by 011**, and the shared phrase is a coincidence of wording. F3 is about the display switch converting a chart, which is a channel-rate question about presentation; 011 built the *tax* role, and treating the two as one requirement would conflate the two roles the constitution names explicitly. |
| F4 | The real-terms view uses UA CPI in the UAH display and US CPI in the USD display. | `[ ]` — **half of the machinery exists; the row stays open because the example does not.** Feature 007 built the UA half: CPI enters as declared, dated, cited observations (`data/cpi/ua.toml`, 411 months, every one unverified), a window is deflated by the exact Fisher relation over the chained monthly product, and `HurdleRate.real` carries a realized and an assumed figure that never mix — `tests/worked_examples/test_deflation_arithmetic.py`, `tests/worked_examples/test_falling_prices.py`, `tests/contract/test_two_figures_never_blend.py`. What F4 actually asks is that the **display switch** selects the deflator, and there is no display switch yet: that is the display-currency feature's, alongside F1–F3. 007's obligation to it was structural and is discharged — a second series with a distinct identity is a data-only addition that loads and deflates, proved by `tests/contract/test_cpi_data_only.py`, so the shape does not preclude US CPI. |
| F5 | Cash-vs-non-cash channel selection changes the result and is visible in the attribution. A single mid-rate is never used for a transaction. | `[x]` `tests/contract/test_route_data_only.py::TestTheChannelChoiceChangesTheResultAndIsVisible` — closed by **declared data**, not by code: `data/routes/monobank_to_binance_card.toml` differs from `monobank_to_binance_p2p.toml` in the `channel` its one `fx` leg names (and the provider doing the converting), and nothing else. The card's 150 bps costs **1.4778%** one way (`0.63/42.63`) against the P2P premium's **6.6667%** (`3/45`); round trip through the same declared exit, **7.3422%** against **12.2222%**. Each result names the channel it took in `channels_applied` — `('card', 'p2p')` and `('p2p', 'p2p')` — and reports `3/42 = 7.14%` as the spread over the reference *beside* the cost, never instead of it. `tests/worked_examples/test_channel_rates.py` holds the two-sided arithmetic. |

## G. Streams and routes

| # | Example | Test |
|---|---|---|
| G1 | The same crypto purchase funded from the UAH salary and from the USD income yields different net positions, differing by exactly the hand-computed ramp cost. (The two paths deploy the same *value* to the same destination venue: 10 000 UAH at a P2P price of 45 arrives as 222.222222 USD, while the same 10 000 stated in dollars at the reference — 238.095238 USD — arrives untouched. The gap of **15.873015873 USD** is 666.666666 UAH at the reference, which is exactly the spread the hryvnia path paid, and 1/15 = 6.67% of what the dollar stream deployed.) | `[x]` `tests/worked_examples/test_two_streams.py` |
| G2 | A P2P premium of +3 UAH at a stated reference rate reproduces the `SIMULATOR_SPEC.md` §4.3.1 percentage. (Reproduced as the **rate-space spread** `3/42 = 7.14%`, reported beside the **cost** `3/45 = 6.67%` — see FR-004's correction. §4.3.1 labels its own arithmetic illustrative, so it defines a spread over the reference rate and not a fraction of money.) | `[x]` `tests/worked_examples/test_ramp_p2p_premium.py` |
| G3 | A plan exceeding a monthly cap queues the excess per the fallback policy and reports each occurrence; total deployed equals the cap, never the plan. ("Queues" is §4.3.4's own wording for *hold as cash* — not carrying the excess into next month's capacity, which no policy in the closed set expresses. Of the four policies, feature 002 implements **hold as cash, redirect, skip**; *place on deposit* needs a deposit instrument and fails at load naming the feature that will bring it.) | `[x]` `tests/worked_examples/test_monthly_cap.py` — 150 000 planned against a declared 100 000 card limit deploys 100 000 and reports 50 000 held as cash; a second 80 000 over a **different route on the same card** deploys 0 and reports 80 000, because the limit belongs to the rail (`tests/invariants/test_capacity_accumulator.py` is the accumulator property). *Place on deposit* fails by name. |
| G4 | A regime transition on the war-end date switches the route set; round-trip cost drops by exactly the hand-computed difference. (A regime is **scenario** data and a leg window is **route** data — the split is epistemic, research.md D8: a window is an observed fact with a source, a transition date is an assumption nobody can source. The regime narrows the *candidates*, so an assumed exclusion never arrives as a `RouteUnusable` naming a declared field.) | `[x]` `tests/worked_examples/test_regime_transition.py` — the same 10 000 UAH, the same reference rate and the same channels either side: the wartime P2P corridor costs **2/15 = 13.3333%** round trip (1 333.33 UAH), the normalized bank corridor **2/85 = 2.3529%** (235.29 UAH), a drop of **28/255 = 10.9804%**, or **1 098.04 UAH**. `tests/unit/test_transition_is_an_assumption.py` holds the other half: `is_assumption` admits one value and cannot be omitted, a regime carries no date and a leg carries no assumption marker, and `core/routes/` never imports `core/scenarios/`. |
| G5 | Two variants of one route differing only in conversion count rank in the expected order. | `[x]` `tests/contract/test_route_data_only.py::TestTwoVariantsDifferingOnlyInConversionCount` — closed by **declared data** exercised through `rank`: `data/routes/monobank_to_binance_p2p_double.toml` is `data/routes/monobank_to_binance_p2p.toml` with two extra `fx` legs and *nothing else* changed — same provider, endpoints, channel, zero fees, rail and cap. On 10 000 UAH the single conversion costs **6.6667%** one way and **12.2222%** round trip; the triple costs **18.0741%** and **22.9506%**. The gap of **10.7284%** (1 072.84 UAH) sits **entirely** in the `conversion_spread` component — both routes report exactly zero percentage and fixed fees — and the extra crossings are visible as four `channels_applied` entries against two (FR-017). |
| G6 | No comparison reports a one-way cost as if it were round-trip. | `[x]` `tests/unit/test_round_trip_types.py` and `tests/contract/test_cost_labels.py` — `OneWayCost` and `RoundTripCost` are unrelated frozen records, so assigning one into the other's slot is a mypy strict error rather than a convention (research.md D4), and every cost figure in every result type is reachable only through a field named one way or round trip. A destination whose exit nobody declared yields `ExitCostUnknown` naming the route, is kept out of the ranking, and its one-way figure is **not** promoted into the gap — asserted on the shipped `data/routes/coinbase_to_ibkr.toml` in `tests/contract/test_route_data_only.py::TestTheShippedCorridorsRankAsHandComputed`. |

## H. The framework surface

Compliance tests for Principle II. May not be skipped without an amendment.

| # | Example | Test |
|---|---|---|
| H1 | Adding a new instrument, route, tax class and jurisdiction **in data only** — no engine edit — runs the full pipeline and appears in the comparison. **Closed by feature 010**, and it did not pass for free: nothing declared *where* an instrument is bought, so the join could anchor neither of its two positional seams (there is a third, the funding stream, and it has no venue in it). That gap was closed as a declaration kind (`data/access/`, `docs/METHODOLOGY.md` §29.6) rather than as a special case inside the join — FR-023's rule, and the reason this row is worth having. **A second FR-023 gap is recorded and not closed** (2026-08-24): the `[jurisdiction]` table's `id`, `name` and `base_currency` are validated at load and then discarded — no registry is keyed by jurisdiction and `TaxClass` carries no jurisdiction field — so that kind is exercised as a *container* for its classes rather than as a term. The row is claimed on the other three; the test module states the gap and what closing it would take. H1 also funds from the shipped `salary_uah`, so it says nothing about the income-stream term. | `[x]` `tests/contract/test_h1_data_only.py` |
| H2 | A malformed or unknown field in any data file fails loudly at load time, naming file and field; it never silently defaults. | `[x]` `tests/contract/test_declaration_loading.py` |
| H3 | Every data file's values round-trip through the run manifest, so a result traces to the exact configuration that produced it. | `[ ]` |
| H4 | Architecture boundaries hold: the core imports no I/O, no network, no framework, and nothing from a layer above it. | `[x]` `tests/contract/test_architecture_boundaries.py` |

## I. The decision layer

| # | Example | Test |
|---|---|---|
| I1 | Feasibility pruning drops infeasible candidates with a recorded reason, and the count of dropped candidates is reported. **Closed at the tuple level**, which is the level `SIMULATOR_SPEC.md` §4.3.4's feasibility list is written at. §4.10.2's *allocation* candidates are a second population, pruned again under a rule feature 014 does not build (its *The one place the framing genuinely breaks*): monthly capacity is a shared rail resource, so two candidates each feasible alone can be jointly infeasible the moment a strategy holds both. Do not read this row as covering that. | `[x]` `tests/unit/test_seventeen_refusals_through_the_loop.py`, `tests/worked_examples/test_candidate_accounting.py`, `tests/unit/test_drop_tally.py` |
| I2 | Two objectives over the same candidate set produce different rankings, and each run's manifest records which objective was used. | `[ ]` |
| I3 | A binding constraint reports a non-zero shadow cost; a non-binding one reports zero. | `[ ]` |
| I4 | The naive baseline (100% OVDP; 50/50 OVDP + VWCE) is always scored and always shown, and a synthetic case where nothing beats it produces the honest verdict. | `[ ]` |
| I5 | Stability: perturbing one assumed input by 1% must not silently change the top recommendation; if the ranking flips, the run is labelled unstable. | `[ ]` |
| I6 | Indifference band: a synthetic case where a range of allocations scores within noise reports the band, not a point. No allocation is ever reported to sub-percent precision. | `[ ]` |
| I7 | "Sometimes best" and "never bad" are computed separately, and a synthetic case where they differ shows both. | `[ ]` |

## J. Goals, seed, liquidity, honesty

| # | Example | Test |
|---|---|---|
| J1 | The three goal modes are mutually consistent: solving for date from (contribution, sum) and then for sum from (contribution, that date) returns the original sum. | `[x]` `tests/invariants/test_goal_mode_consistency.py`, `tests/worked_examples/test_goal_arithmetic.py` |
| J2 | A seed lot with a known basis produces the hand-computed gain on disposal; a basis-estimated seed marks every downstream tax figure. | `[x]` `tests/worked_examples/test_seeded_disposal.py`, `tests/contract/test_estimated_basis_propagates.py` |
| J3 | Redemption outside an Inzhur window is refused, or executed at the stated haircut when allowed — taxed correctly either way. ⚙ **The wording is annotated rather than reinterpreted.** The funds' primary documents, read in full on 2026-08-22, show that **no redemption windows exist**: legally neither fund owes a buyback before its termination date, an earlier exit is at the manager's discretion, and the same-day buyback at NAV is a revocable company practice (006 spec FR-015). The row's substance is preserved over those declared liquidity terms — refuse, or execute at the declared discount, taxed on the proceeds actually received either way. | `[x]` `tests/worked_examples/test_fund_liquidity.py` |
| J4 | A lock-up longer than the horizon is a feasibility error, not a silent simulation. | `[~]` `tests/worked_examples/test_fund_liquidity.py::TestAGuaranteedExitBeforeTerminationIsAFeasibilityFinding` and `::TestCaseThreeTheBuybackIsNotOnOffer` — a fund whose only guaranteed exit is its termination surfaces that as a finding on the result, and a redemption the terms do not owe is refused with the holding left open. **Not claimed closed:** a declared `lock_up_months` term and a horizon-versus-lock-up check do not exist, and 006's spec deliberately did not claim this row |
| J5 | Correlated stress hits OVDP, Inzhur and UAH simultaneously, never as independent draws. | `[ ]` |
| J6 | No Sharpe ratio or volatility figure is emitted for an assumption-driven instrument. | `[x]` `tests/contract/test_assumption_driven_refusal.py` — the refusal, and a walk over every fund result record proving there is no field one could sit in |

## K. Equivalence and golden results

| # | Example | Test |
|---|---|---|
| K1 | With zero fees and zero taxes, the ledger engine matches the vectorized fast path within the project tolerance. | `[ ]` |
| K2 | With zero taxes but nonzero fees, the ledger engine matches a closed-form fee-drag calculation. | `[ ]` |
| K3 | A full end-to-end run on the offline snapshot completes and matches a checked-in golden result file. | `[x]` `tests/golden/test_end_to_end_ovdp.py` |
| K4 | Tests never reach the network; CI runs with networking unavailable. | `[x]` `tests/conftest.py`, `tests/contract/test_no_network.py` |

---

## Rows a feature reinforced without closing

A feature sometimes exercises a row without satisfying it. Recording that here keeps two
things straight at once: the box stays honest about what is actually covered, and the next
person does not re-derive work that already exists somewhere.

**003-route-coverage** closes **no** row. No lettered behaviour above names a registry
coverage audit, and the feature's spec says so plainly rather than stretching one. Four rows
it reinforces:

| Row | How, and why the box does not move |
|---|---|
| **B10** | Exercised anew: an empty registry dimension returns `RegistryDimensionEmpty` naming **every** empty dimension, and every not-ready verdict carries its deficit and the declaration that would fix it — never an empty result a caller could read as full coverage. `tests/unit/test_coverage_empty.py`, `tests/invariants/test_coverage_totality.py`. The row is about *insufficient data anywhere in the engine*, so one feature's typed outcome does not close it. |
| **B12** | Honoured by construction: the to-do ordering is a plain blocked-pair count with ties reported as ties, and `TodoEntry.count == len(TodoEntry.blocked)` is asserted. `tests/unit/test_coverage_deficits.py`, `tests/invariants/test_coverage_totality.py`. Again a whole-engine row — this is one more ordering that does not use a composite score, not the last one. |
| **H2** | Relied on and extended, not re-derived: the one new declaration (`data/spendable/`) fails at load naming file and field for every refusal in its contract, on the existing loader path. `tests/contract/test_spendable_declaration_loading.py`. The row's own test stays `tests/contract/test_declaration_loading.py`. |
| **G6** | Extended in visibility: feature 002's per-route *exit cost unknown* refusal becomes an audit of the whole registry, and `tests/invariants/test_coverage_costing_agreement.py` pins the two views together — a pair the audit marks ready is one costing produces a round-trip figure for, within this feature's single-route scope. |

**006-inzhur-instruments** closes **E1**, **E10**, **J3** and **J6**. Two rows it
reinforces without closing:

| Row | How, and why the box does not move |
|---|---|
| **J4** | Half-covered and marked `[~]` above. A fund whose only guaranteed exit is its termination now says so on the result, and a redemption the terms do not owe is refused with the holding left open. What the row asks for and does not exist is a declared **lock-up** term compared against a horizon: these funds declare no lock-up, they declare an absence of obligation, which is a different fact reached by a different route. |
| **E11** | Reinforced: every fund charge is recorded including a zero, and a disposal at a loss carries a `taxable_base` of zero *with the loss beside it on its own line*. The row is a **presentation** requirement for the waterfall — that a reader looking at `0.00` can tell exempted from not-applicable — and there is still no presentation surface. |
| **B5** | Approached from one side: tax is assessed per disposal against per-lot basis consumed, and `charged_for_year` records the year it accrues to. The row also wants it **paid from cash on the due date**, with loss offset and carryforward, and this feature explicitly does not model any of the three (FR-008 says so in the output). Feature 009's. |

**004-composed-paths** closes **no** row either, and says so rather than stretching one: no
lettered behaviour above names composing declared routes into a candidate. Three rows it presses
on directly, and one it reinforces along the way:

| Row | How, and why the box does not move |
|---|---|
| **B12** | The row's hardest case, because a routing search is exactly where a composite score sneaks into a user-visible ordering. Composed candidates enter 002's lexicographic ranking with no bonus, no penalty and no separate league; nothing is pruned by cost, no partial cost is cached, and **no record in the feature has a field a score could live in** — asserted as an absence in `tests/unit/test_composed_path_types.py`, and as order-independence in `tests/invariants/test_composition_order.py`, which runs a registry in both declaration orders and compares every figure, position, recommendation and tie. Still a whole-engine row: this is one more ordering that does not use a score, not the last one. |
| **G6** | Pressed on from the other side. A composed round trip exists **only** through a chain of declared exit routes (FR-012, owner decision 2026-08-22) or where the destination is itself spendable; where nothing chains, *exit cost unknown* stands, the candidate stays out of the round-trip ranking, and its one-way figure is not promoted — both directions verified in `tests/worked_examples/test_composed_exit_chain.py`. `tests/contract/test_composed_distinct.py` pins the correspondence: `RampCost.exit_path` is `None` exactly when the round trip is unknown. |
| **H1** | The row's claim applied to composition, and the closest any feature has come to it: `tests/contract/test_composed_data_only.py` adds **one** `Route` declaration, gets a three-segment candidate that is fully costed and ranked, and asserts that no module under `core/` mentions the new venue or route at all. The box stays open because H1 asks for an instrument, a route, a tax class and a jurisdiction through the **full pipeline**, which is feature 010's scope. |
| **B10** | Exercised again: `CompositionRefused` is a typed statement that a question could not be asked — a bound admitting nothing, an exit chain with nowhere declared to end — and it is a *different type* from an empty enumeration, which is the legitimate answer "nothing connects". `tests/invariants/test_composition_search.py` asserts both, because a caller who counts rows cannot tell them apart. |

**005-route-diagrams** closes **no** row either. No lettered behaviour above names a diagram,
and the feature's spec states that plainly rather than stretching one. It extends two standing
obligations into a new surface, and its tests assert the extension:

| Row | How, and why the box does not move |
|---|---|
| **E5** | The mark propagates into the *picture*, not only into tables. One unverified route input marks 100% of the diagram elements depicting figures derived from it, and the assertion strips every style declaration first so a mark carried by a colour fails. `tests/contract/test_diagram_marks.py`. The row is about every figure in the engine, so one more surface carrying the mark does not close it — it is the row still holding. |
| **B10** | Exercised again in its visual form: a refusal renders as a typed `NothingToDraw` carrying the refusal's own reason verbatim, never an empty diagram — because an empty picture is indistinguishable from a graph with nothing in it. `tests/contract/test_diagram_refusals.py`. Same reading as 003: a whole-engine row, and one more typed outcome does not close it. |

Feature 002's **SC-014** — no exit route means no round-trip figure, and the destination is
excluded from comparison — is likewise extended rather than restated: the exclusion becomes
*visible*, as an explicitly absent edge and a `NO EXIT DECLARED` mark on the destination,
never an omission. `tests/contract/test_diagram_refusals.py`.

**008-seed-and-goals** closes **J1** and **J2** above. Four rows it reinforces without closing:

| Row | How, and why the box does not move |
|---|---|
| **C1–C3** | The conservation properties now draw ledgers that **open from declared seed lots** as well as unseeded ones, and **not one of the properties changed** to accommodate them — which is the executable form of the feature's central claim that a seed is an ordinary ledger citizen. `tests/invariants/seeded_streams.py` builds them through `seeds.opening_events` rather than by hand, so the invariants cover the events the engine actually produces. The rows were already flipped by 001; this widens their inputs. |
| **E5** | Pressed on from a new direction: the propagating mark now describes the *owner's own memory* rather than only a market observation, and it reaches the tax through the transforms that already existed rather than through a second system. `tests/contract/test_estimated_basis_propagates.py` sweeps every money field of `TaxCharge` from the dataclass, so a field added later is inside the 100% claim. The row's own test stays `tests/contract/test_provenance_propagation.py`. |
| **B10** | Exercised again, and deliberately in the opposite direction from 003: no seeds and no goals is an **ordinary run**, not a typed empty outcome, because an absent holding cannot be mistaken for a mistyped path. `tests/contract/test_empty_seeds_and_goals.py`. The row is about insufficient data anywhere in the engine, so one feature's rule about emptiness does not close it. |
| **H2** | Two new declarations fail at load naming file and field for every refusal in their contract, on the existing loader path: `tests/contract/test_seed_declaration_loading.py`, `tests/contract/test_goal_declaration_loading.py`. The row's own test stays `tests/contract/test_declaration_loading.py`. |

**009-tax-depth** closes **E2** and **E6**, and closes the first clause of **E7**. Four rows it
reinforces without closing:

| Row | How, and why the box does not move |
|---|---|
| **C1–C3** | The conservation and traceability properties now draw ledgers containing **tax payments**, and are folded under **all four** basis methods rather than only FIFO — and again **not one property changed**. `tests/invariants/event_streams.py` draws the method with the stream, because two of the four constrain what a valid stream looks like. If a property fails only for ledgers containing a payment, the event is wrong, never the invariant. |
| **E5** | Pressed on again: the propagating mark now describes a **legal rule** — a deadline, a netting treatment, a finding about a basis method — and reaches the annual liability, the carryforward and the dated payment that settles it. `tests/contract/test_provenance_propagation.py` sweeps every money field of `AnnualStatement`, `AssessedLiability` and `CarryforwardState` off the dataclasses and asserts the mark on each non-zero one, so a field added later is inside the claim. The deadline case is the one that shows why the sweep has to reach the money: a `date` carries no provenance in this codebase, so an unverified deadline can only be visible on the amounts it governs. |
| **E11** | The *exempted* / *not applicable* distinction now exists at the **annual** level too: `AnnualStatement.zero_because` tells an exempt zero from a netted one from a year in which nothing happened, and exemption is read off the **rates** rather than off the amounts, so a break-even disposal under a 23% class is not called an exemption. Still a presentation requirement, so the box does not move. |
| **H2** | Two new declarations fail at load naming file and field for every refusal in their contract: `tests/contract/test_tax_declaration_loading.py`. The row's own test stays `tests/contract/test_declaration_loading.py`. |

**010-full-tuple** closes **H1**. Four rows it reinforces without closing:

| Row | How, and why the box does not move |
|---|---|
| **G6** | Extended, not re-derived: a third labelled cost record, `WayOutCost`, prices what an instrument *released* rather than what a ramp delivered — unrelated to `OneWayCost` and `RoundTripCost` by type, so none can stand in for another. `tests/contract/test_cost_labels.py` was widened to pin it. The row is 002's and stays where it is. |
| **I4** | *Naive baseline strategies always scored.* Half of it is now structural: the hurdle is always scored, always shown, and held as an **index** into the ranking rather than as a second figure beside it (`tests/contract/test_the_hurdle_is_a_tuple.py`). The box stays open because I4 is about a *strategy* shortlist, and there is no decision layer to shortlist anything yet. |
| **F1** | The FX tax asymmetry stays with the feature that introduces a real taxable foreign position. What 010 added is the refusal in its place, and feature 011 narrowed what that refusal names — see F1's own row. Unreachable through the shipped registry, which is a property of today's data. |
| **H3** | Unmoved and worth naming: the new `data/access/` declarations are **not** in the run manifest's input references, so a result does not yet trace to the access file that priced its purchase. H3 asks for every data file's values to round-trip through the manifest, and this feature widened what a run reads without widening what it records. |

**013-enumerated-schedule** closes **nothing**, and says so rather than inventing a row for
itself. There is no row here for a declaration *form*, and writing one would be a row created
to be flipped by the feature that created it. Two rows are **touched and not claimed**:

| Row | How, and why the box does not move |
|---|---|
| **H1** | The data-only claim gains a second instrument **shape**. `tests/contract/test_enumerated_data_only.py` adds a third bond declared as its payments — a file this repository has never seen, in a scratch data root, differing in its schedule, its coverage claim, its face value and its day count — and runs the full pipeline on it with no engine edit. It sits **beside** H1 rather than strengthening it: H1's own claim is about four declaration kinds through the join, and this is one kind declared a second way. The two gaps H1 already records are untouched. |
| **D1** | **Unchanged by design.** A reader will reasonably expect a schedule feature to move it and it does not: D1 is about a bond bought at a stated price and held to maturity reproducing a hand-computed schedule, and no generative declaration's behaviour changed. The enumerated form has its own hand-computed example (`tests/worked_examples/test_enumerated_schedule.py`), which is a second answer to a different question rather than a second proof of this one. ⚙ What *did* move is the golden's recorded digest, because a projection now reports the premium at purchase — one more true thing about every holding, and exactly the direction constitution 1.2.0 Principle V says a golden is supposed to move in. No amount, date, tax or rate changed with it. |

---

## On tolerance

Owner decision **D-A**: money is `float64`. The specification's phrasing "reproduces a
hand-computed schedule **exactly**" is therefore implemented as "within the project
tolerance", which is defined in exactly one place and imported. A test that invents
its own tolerance is a defect; a test that needs a looser one states why at the
assertion site (constitution, Principle IV).

---

**011-official-rate** closes no row and moves three notes. **F1** loses one of its two
blockers: the dated official rates exist, and what remains is a position and a basis in two
currencies. **F2** gains its tax-figure half as a standing property asserted before the
display switch exists. **F3** is recorded as deliberately not attempted, so a later reader
does not mistake "per-date rates" for the same requirement. **E8** — a second jurisdiction —
is unmoved, and 011's obligation to it is discharged structurally: a second official-rate
series with a distinct identity is a data-only addition that loads and is addressable
(`tests/contract/test_official_rate_data_only.py`).

---

**012-fop-group-3** closes no row and moves four notes.

**E10** is exercised a second time and is not re-flipped — see its row: 006 closed it on an
instrument's tax class, 012 ran the same mechanism on income against a statute whose rate and
whose commencement come from different laws.

**E8** — the same scenario under two jurisdictions — stays open, and 012's obligation to it is
structural and discharged: a second taxation scheme with a distinct identity, a different
component set and a periodic component the first does not have is a data-only addition that
loads, charges and is addressable (`tests/contract/test_scheme_data_only.py`). What is still
missing is a *second jurisdiction consumed in one comparison*, which no feature has built.

**E7** — tax paid from cash in the following year — is untouched and was not attempted. 012
records a liability against the period it accrues to and declares the reporting cadence 009
will need; payment timing, filing and the cash movement that settles a liability stay where
that row already puts them.

**E4** — the three crypto scenarios — is untouched, and the resemblance is worth naming so
nobody flips it. E4 is about disposing of a crypto **asset** under a regime that does not
exist; 012's crypto-exchange destination is about where contract **income** is credited, and
it produces one labelled personal-income figure. The 18% + 5% those two share is the same
numbers from different places.

**F1** is unmoved. 012 produces a different asymmetry from the one F1 names — a base fixed at
the credit-date official rate against hryvnia received at a market rate on the sale date, with
no holding period and no cost basis anywhere in it. Both come from the same conflation this
project exists to refuse, and they are not the same test.

---

**014-candidates** closes **I1** — see its row for what "at the tuple level" excludes. Three
rows it presses on without closing:

| Row | How, and why the box does not move |
|---|---|
| **B12** | The row's shape again, one layer above 004's: enumeration is where a candidate generator quietly acquires an opinion. Nothing here is pruned by score, by cost, by bound or by ordering — every candidate is evaluated in full, and a scan asserts this feature's modules construct, match on and raise no feasibility verdict of their own (`tests/contract/test_candidates_add_no_rule.py`). The set's own order is lexicographic over declared terms and the caller's plan sequence, never a composite (`tests/unit/test_candidate_order.py`). Still a whole-engine row: one more ordering that does not use a score. |
| **J4** | Touched and deliberately not claimed. A lock-up longer than the horizon reaches `CannotSpanHorizon`, and this feature makes every such candidate visible in one report rather than one at a time — planted and asserted in `tests/unit/test_seventeen_refusals_through_the_loop.py`. What the row asks for still does not exist: a declared `lock_up_months` term compared against a horizon. 006 did not claim it and neither does this. |
| **E5** | Pressed on at the level of a *set* rather than a figure: a candidate set carries the union of the marks on every declaration enumeration itself read — the legs of every route it put in a candidate, and the venue quote of every access entry it considered — so a set never looks cleaner than the registry behind it (`tests/unit/test_candidate_marks.py`, walked over both families rather than sampled). **The per-drop half is open and recorded**: 010's refusal records carry no provenance, so which unverified value caused a particular drop is not traceable from the drop. That is the `provenance-on-a-refusal` future entry. |

---

**018-nbu-rate-series** closes **no** row and moves two notes. It lands data, not behaviour:
the National Bank's published UAH/USD rate for every calendar day from 2019-12-28, plus the
script that retrieves it and the three shipped-code defects an empty series was hiding.

**F1** loses nothing further and gains nothing further. 011 supplied the machinery and this
supplies the rates both halves of F1 would read; what is still missing is unchanged — a per-lot
basis carried in both currencies with each leg struck at its own date's rate, and a projection
fold that does not sum a hryvnia charge inside a dollar holding. `ForeignGainNotStruckPerDate`
still refuses, and must.

**F2**'s tax-figure half was established by 011 before the display switch existed, and this is
the first time it is established **against real data**: populating the series moves no cost,
route, leg, channel or ranking figure, asserted as the diff of the golden — one added input
line and no result line — rather than as a claim
(`tests/golden/ovdp_synthetic_a.golden.txt`). The realised-amount and ranking halves still need
the switch.

**F3** stays deliberately not attempted, for 011's reason: F3 is about a display switch
converting a chart, which is a channel-rate question about presentation, and treating it as
this feature's subject would conflate the two roles the constitution names explicitly.

**K3** is unmoved and its artefact was regenerated deliberately: the run manifest can now name
the official-rate series a tax base rested on, which it could not before —
`InputKind` had no member for it — so the golden gains that one input reference. An input
digest is a witness, not a term (Principle V).
