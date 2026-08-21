# Specification — allocation simulator for a UAH-income investor

**Supersedes** the product sections of `docs/REWRITE_BRIEF.md` (§1–2, §5.5–5.8). That
document's engine requirements — event-sourced ledger, tax lots, cash accounts,
multi-currency, provenance, the 12 preserved correctness behaviours in its §4.1 and the 18
defect regressions in its §4.2 — remain in force and are **not** repeated here.
**This document defines what the tool is for and what it must model.**

**Revision 2** (2026-08-21): owner's answers to the open questions are folded in; the tax
section now carries researched, sourced values instead of placeholders (§4.5, §12).

---

## What this is

A **framework** for declaring the rules that actually govern the money — instruments, funding
routes, FX channels, taxes, limits, risks — and a **decision layer** that searches the
strategies those rules allow and helps the owner choose among them.

Two halves, deliberately separated:

- **The framework is data.** Instruments, routes, tax packs, scenarios and strategies are
  declarative, versioned, sourced files with four narrow plugin interfaces behind them
  (§4.10.1). Adding an instrument, a venue, a tax regime or a country must not require
  touching the engine. That constraint is what makes it a framework rather than one person's
  script.
- **The decision layer is search and comparison.** It generates candidate strategies, prunes
  the infeasible ones, scores every survivor under *every* scenario, filters by the owner's
  constraints, and returns a small shortlist with the trade-offs named (§4.10.2–4.10.5).

And the honest bound, which the rest of this document keeps returning to: **it does not
produce *the* optimal strategy.** It produces a defensible shortlist under objectives and
constraints the owner states, shows which assumption decides between them, reports an
indifference band rather than a false optimum, and says plainly when nothing beats the simple
option.

---

## 0. Decisions taken

These were open in revision 1 and are now settled. Each has consequences in the body.

| # | Decision | Consequence |
|---|---|---|
| 1 | **UAH is the base currency**; USD is a co-equal *display* currency, switchable in the UI | §4.4 — a display-currency switch that recomputes every value and chart, while tax always computes in UAH |
| 2 | Instrument shortlist: **Inzhur OVDP, Inzhur REIT, Inzhur MilTech, a UCITS ETF core, BTC/ETH/SOL/XRP + a few mature others** | §3 — the concrete registry, with the ETF selection argued in §3.4 |
| 3 | Tax rules to be **sourced from public information**, not asked of the owner | §4.5 + §12 — researched values with citations; the owner handles his own filings |
| 4 | Venues: **Monobank** primary (plus A-Bank, VST, PrivatBank), **Inzhur** (0 fee), **Binance** (P2P at +2–4 UAH/$), **Coinbase** (funded by Deel), **IBKR** (hard to fund today) | §4.3 — the real route registry, and the finding in §4.3.1 |
| 5 | Goal is **a target sum, a target date, or both** | §4.7 — a three-variable solver: fix two, solve the third |
| 6 | Scope is **investments only**; property and other basics are excluded | §1.2 — the exposure gauge covers the investable portfolio and UAH income, not the whole balance sheet |
| 7 | **Python core + local web UI**, later self-hosted; eventually multi-user | §6 — owner-scoped data model from day one, auth deferred but not designed out |
| 8 | **Configurable initial seed** of existing holdings | §4.8 — seeding requires cost basis and acquisition dates, not just current value |

---

## 1. The decision the tool must support

> **"I have a monthly surplus in UAH. Where should the next hryvnia go, and how much will I
> actually keep — after the FX spread to get it there, the fees, the taxes, the lock-ups, and
> inflation?"**

Not "which ticker had the best 2018–2025". The answer changes every time any of these
changes: the spread on the route in, whether that route is open this month at all, whether
the income is tax-exempt, whether the money can be got back out, and what happens to the
hryvnia.

### 1.1 The options are not comparable as assets

Each option is a **tuple**, and two options with identical gross returns can differ by
several percent a year purely in the non-instrument terms:

```
(instrument) × (funding route in) × (tax treatment) × (exit route out) × (risk class)
```

The current tool models one of the five and calls the rest "limitations". **Modelling all
five is the product.** The researched numbers in §4.5 and the route findings in §4.3.1 show
how large the non-instrument terms actually are: a 23% tax rate versus 0%, and an access
cost of 5–10% one-way, both dwarf the differences between the instruments themselves.

### 1.2 Exposure, scoped to investments

Scope is the investable portfolio (decision 6): property and other basics stay out. But
within that scope the concentration point still holds — the salary that funds the portfolio
is UAH, and OVDP, Inzhur REIT and MilTech are all UAH-denominated claims on Ukrainian
counterparties. A plan that is 100% domestic is a leveraged bet on the same thing that pays
for it.

So the tool reports **portfolio-level Ukraine exposure** alongside a note of the UAH income
stream that funds it, and never treats OVDP and an Inzhur fund as independent diversifiers
(§4.6). It does *not* claim to model total net worth.

### 1.3 What honest output looks like

For assets with no usable price history and risks never sampled — a military-tech fund,
sovereign stress, the date the war ends — a point estimate is a fabrication. Preference
order:

1. **Dominance** — "A beats B under every scenario you specified." A real, defensible answer.
2. **Ranges and distributions** — "between X and Y across your scenarios; worst case Z."
3. **Break-even framing** — "funding IBKR via TransferGo now beats waiting only if the war
   lasts past mid-2028" — which converts an unknowable forecast into a testable belief.
4. A point estimate, only where the inputs justify one.

Where the honest answer is "this depends on an assumption you have to make yourself", the
tool's job is to make that assumption **explicit, editable, and visibly consequential**.

---

## 2. Why each option is hard to model

| Option | Why the current tool cannot model it |
|---|---|
| **OVDP via Inzhur** | No price series to backtest — a *known* cash-flow schedule and a yield curve instead. Tax-exempt (§4.5), which no other option is. Needs maturity, reinvestment at the then-current yield, and a restructuring scenario. |
| **Inzhur REIT / MilTech** | Low-frequency NAV, not a daily series. Thin or absent secondary market — **exit at NAV on any date cannot be assumed**. Distributions and redemptions are taxed differently from each other (§4.5). MilTech is venture-like: possible total loss, long horizon, no meaningful volatility estimate. |
| **Crypto** | Daily prices exist, but the *ramp* is the cost: the P2P spread alone is 5–10% one-way (§4.3.1). Ukrainian tax treatment has **no adopted regime** — the rate must be a scenario variable (§4.5). |
| **IBKR / foreign securities** | The instrument side is the one thing already modelled well. The blocker is **access**. Gains are taxable in **UAH** at NBU rates on each transaction date, so devaluation taxes gains never earned in USD. Fund domicile changes both withholding and estate-tax exposure (§3.4). |
| **Cash / FX** | Must be first-class, not a benchmark afterthought. Cash and non-cash rates differ; deposit interest is taxed at 23% while USD banknotes in a drawer are not. |

Out of scope now, but the instrument interface must not forbid: physical real estate,
pension and insurance products, private lending, metal in hand.

---

## 3. The instrument registry — the P0 shortlist

Concrete instruments, per decision 2. Every field is dated, sourced and editable; the
numbers below are starting values from public sources, **not verified facts** (§4.5.1).

### 3.1 Fixed income — OVDP via Inzhur

```toml
[instrument.ovdp_inzhur]
class = "fixed_income"; currency = "UAH"
name  = "ОВДП via Inzhur"
quoted_yield_pct = 15.5          # owner-reported; auction-dependent — refresh per issue
entry_fee_pct    = 0.0           # Inzhur charges no purchase commission — VERIFY per product
min_ticket_uah   = 1000.0        # ≈ one bond
tax_class        = "ua_government_bond"      # exempt — §4.5
[instrument.ovdp_inzhur.reinvestment]
policy = "roll_same_maturity"    # or: to_current_curve | hold_cash | redirect
[instrument.ovdp_inzhur.risk]
restructuring = { probability = 0.0, haircut_pct = 0.0, delay_years = 0 }   # user assumption
```

The **0% entry fee and 0% tax** are why this is the benchmark every other option must beat,
and the tool should say so explicitly: 15.5% tax-free in UAH is the hurdle rate. Yields are
per-issue and move with auctions, so `quoted_yield_pct` is a dated observation and the
engine prices future purchases off a **yield curve**, not this constant.

### 3.2 Inzhur REIT

```toml
[instrument.inzhur_reit]
class = "ci_fund"; currency = "UAH"
income_currency = "USD"          # VERIFY: commercial rents are commonly USD-pegged
nav_series      = "data/instruments/nav/inzhur_reit.csv"     # low frequency, dated
distribution_policy = { target_yield_pct = 0.0, frequency = 4 }   # VERIFY per fund
tax_class_distribution = "ua_ci_fund_distribution"   # 9% + 5% — §4.5
tax_class_disposal     = "ua_investment_profit"      # 18% + 5% — §4.5
[instrument.inzhur_reit.costs]
entry_commission_pct = 0.0; management_fee_annual_pct = 0.0; exit_commission_pct = 0.0  # VERIFY
[instrument.inzhur_reit.liquidity]
min_ticket_uah = 10.88           # per certificate, per public listing — VERIFY
secondary_market = "thin"; redemption_windows = "…"; forced_exit_haircut_pct = 0.0
```

If rents are USD-pegged while the unit is UAH-denominated, this instrument is **partly a
dollar asset wearing a hryvnia label**, and that must appear in the FX attribution rather
than being lost. Note the two different tax classes: distributions and redemption are not
taxed alike (§4.5).

### 3.3 Inzhur MilTech

```toml
[instrument.inzhur_miltech]
class = "ci_fund"; currency = "UAH"
target_return_pct = 25.0                 # owner-reported target — not a promise
management_fee_annual_pct = 2.0           # "up to 2% of average AUM, accrued monthly" — VERIFY
min_ticket_uah = 1000.0
tax_class_distribution = "ua_ci_fund_distribution"
tax_class_disposal     = "ua_investment_profit"
[instrument.inzhur_miltech.outcomes]      # user assumptions — the tool must not invent these
scenarios = [
  { label = "total loss",        probability = 0.0, multiple = 0.0 },
  { label = "return of capital", probability = 0.0, multiple = 1.0 },
  { label = "target",            probability = 0.0, multiple = 2.0 },
  { label = "upside",            probability = 0.0, multiple = 5.0 },
]
horizon_years = 5; lock_up_months = 0     # VERIFY redemption terms
```

A 25% target next to a 15.5% risk-free tax-exempt alternative means the tool's job is to
show **how much of that 9.5-point premium survives the 2% fee, the tax difference, and the
probability of loss the owner assigns**. Labelled assumption-driven; no Sharpe ratio is
emitted for it (§4.6).

### 3.4 The ETF core — argued, since the owner asked for a recommendation

**Recommendation: Irish-domiciled, accumulating UCITS ETFs, not US-domiciled ones**, for
three reasons that all point the same way for a Ukrainian resident:

1. **Accumulating share classes pay no distributions.** No dividend means no annual
   dividend-tax event and nothing to declare each year; the tax is deferred to disposal and
   taxed once as investment profit (§4.5). For a taxpayer self-declaring foreign income, that
   is a real simplification and a real deferral benefit — and it is a *strategy the tool
   should be able to demonstrate*, by comparing an accumulating and a distributing version
   of the same index.
2. **Withholding leakage is lower.** Irish funds receive US dividends at the 15% treaty rate
   internally; a Ukrainian resident holding a US-domiciled fund suffers withholding on the
   fund's distributions to them, and then still owes Ukrainian tax.
3. **US estate-tax exposure is avoided.** US-situs assets above **USD 60,000** expose a
   non-resident alien's estate to US estate tax at rates reported in the 26–40% band, and
   Ukraine has no US estate-tax treaty. UCITS shares are generally non-US-situs. For a plan
   that accumulates past $60k — which is the whole point of the plan — this is the decisive
   argument. **VERIFY with a professional before relying on it.**

Starting registry (all IBKR-tradeable on LSE/Xetra; TERs approximate, refresh from the
factsheets):

| Ticker | Fund | Role | TER ≈ |
|---|---|---|---|
| **VWCE** | Vanguard FTSE All-World UCITS Acc | One-fund global core — the default | 0.22% |
| **CSPX** | iShares Core S&P 500 UCITS Acc | US large cap | 0.07% |
| **IWDA** | iShares Core MSCI World Acc | Developed markets | 0.20% |
| **EIMI** | iShares Core MSCI EM IMI Acc | Emerging markets, pairs with IWDA | 0.18% |
| **CNDX** | iShares Nasdaq 100 UCITS Acc | Tech tilt (the old QQQ slot) | 0.33% |
| **IGLN** | iShares Physical Gold ETC | Gold (the old GLD slot) | 0.12% |
| **IB01** | iShares $ Treasury 0–1yr Acc | USD cash-like parking | 0.07% |

US-domiciled comparators (**VOO, VTI, QQQ, GLD**) stay in the registry as *reference only*,
flagged with the withholding and estate-tax notes, so the tool can quantify the difference
rather than assert it.

A defensible P0 hypothesis the tool should be able to test: **VWCE alone**, and nothing
else, is the right foreign-equity allocation for someone who does not want to pick markets.
If the comparison cannot show a multi-fund split beating it after costs, that is the answer.

### 3.5 Crypto

`BTC`, `ETH`, `SOL`, `XRP`, plus `LINK` and optionally `ADA`/`AVAX`/`DOT` — mature,
liquid, non-meme, per decision 2. Cap the list around six: beyond that the marginal name
adds correlation, not diversification, and every extra name adds a ramp cost.

Mandatory **ramp model** per venue (§4.3): P2P premium, exchange trading fee, withdrawal and
network fees, and the reverse path out. Custody/counterparty loss as a user probability.
Tax = scenario variable (§4.5).

### 3.6 Cash and FX

UAH deposit (rate, term, early-withdrawal penalty, interest taxed at 23%), USD/EUR deposit,
non-cash FX balance, and physical USD cash (no interest, no interest tax). Cash is where
infeasible or queued contributions land (§4.3.4), so it must be a real instrument.

---

## 4. Domain model

### 4.1 Instruments — one interface

```python
class Instrument(Protocol):
    id: str; name: str; instrument_class: str
    currency: str                     # denomination of the unit/claim
    income_currency: str              # may differ (UAH unit, USD-pegged rent)
    def events(self, period, holding, assumptions) -> list[Event]: ...
    def valuation(self, date, assumptions) -> Money: ...
    def liquidity(self, date) -> LiquidityTerms: ...
    def tax_classes(self) -> dict[str, str]   # per event kind — see §3.2
```

Note `tax_classes` is plural: the same instrument can have one treatment for distributions
and another for disposal, which is exactly the Inzhur case.

### 4.2 Income streams — new, and it changes the route map

The owner has **more than one income currency**: UAH salary into Monobank, and USD contract
income via Deel into Coinbase. That is not a detail — it collapses the most expensive part of
the foreign-investment route.

```toml
[income.salary_uah]
currency = "UAH"; amount = 0.0; cadence = "monthly"; arrives_at = "monobank_uah"
indexation = { policy = "cpi", rate_pct = null }

[income.contract_usd]
currency = "USD"; amount = 0.0; cadence = "monthly"; arrives_at = "coinbase"
via = "Deel"
arrival_form = "usd"          # or "usdc" — materially different tax consequences, see below
```

**The structural point:** money that *arrives* in USD needs no UAH→USD conversion to reach a
USD asset. The 5–10% ramp cost in §4.3.1 applies only to the UAH stream. So the allocation
question is per-stream, and the tool must model it that way:

- UAH salary → cheapest paths are Inzhur (0 fee, 0 tax on OVDP) or a UAH deposit.
- USD contract income → already offshore; routing it to IBKR or holding it as USD costs
  almost nothing in FX. **Converting it to UAH to buy OVDP is the expensive direction.**

This makes "which stream funds which instrument" a first-class decision the optimiser and
the UI must expose. It may well turn out that the right answer is: UAH salary buys OVDP, USD
income buys VWCE, and neither stream ever crosses.

**Two flagged tax questions on the USD stream** (the owner asked about this and it is
genuinely unsettled — professional advice required, and the tool should model both
interpretations rather than pick one):

1. **Income-side.** Foreign income is the owner's own filing matter (decision 3) and sits
   *outside* the simulator; the simulator takes **net-of-income-tax** amounts as input. But it
   must offer an optional income-tax rate per stream so the "how much can I actually deploy"
   figure is not overstated.
2. **If the USD arrives as a stablecoin** (`arrival_form = "usdc"`), then every later
   conversion may itself be a disposal of a virtual asset — under a regime that does not yet
   exist in adopted law (§4.5). The tool should model `usdc` and `usd` arrival as two
   scenarios and show the difference, because it may be large and it is entirely a
   legal-interpretation question, not a market one.

### 4.3 Funding and exit routes

A **route** is an ordered chain of legs moving value between venues, first-class, named,
dated, and scenario-dependent. Every leg carries `fee_pct`, `fee_fixed`, `fx_markup`,
`min`, `max`, `monthly_cap`, `latency_days`, `available_from/until`,
`disruption_probability`, `source`, `verified_on`.

The owner's actual venues (decision 4): `monobank_uah` (primary), `abank_uah`, `vst_uah`,
`privatbank_uah`, `inzhur`, `binance`, `coinbase`, `ibkr_usd`.

```toml
[route.inzhur_direct]                     # the cheap domestic path
from = "monobank_uah"; to = "inzhur"; status = "open"
  [[route.inzhur_direct.leg]]
  kind = "transfer"; ccy = "UAH"; fee_pct = 0.0; fee_fixed = 0.0; latency_days = 0
  # 0 fee, 0 FX legs, no conversion. The bar every other route is measured against.

[route.binance_p2p]                       # the expensive one
from = "monobank_uah"; to = "binance"; status = "open"
  [[route.binance_p2p.leg]]
  kind = "fx"; from_ccy = "UAH"; to_ccy = "USDT"; rate_source = "p2p"
  premium_uah_per_usd = 3.0               # owner-observed +2..4 UAH/$ — dated observation
  [[route.binance_p2p.leg]]
  kind = "trade"; fee_pct = 0.0           # exchange taker fee — VERIFY tier
  [[route.binance_p2p.leg]]
  kind = "withdrawal"; fee_fixed = 0.0    # network fee — VERIFY per asset

[route.ibkr_transfergo_usd]               # the constrained one
from = "monobank_uah"; to = "ibkr_usd"; status = "constrained"
notes = "TransferGo sends USD, so only one conversion is needed"
  [[route.ibkr_transfergo_usd.leg]]
  kind = "fx"; from_ccy = "UAH"; to_ccy = "USD"; rate_source = "bank_card"
  markup_bps = 0; monthly_cap = 0.0       # VERIFY per bank; NBU limits change
  [[route.ibkr_transfergo_usd.leg]]
  kind = "transfer"; provider = "TransferGo"; ccy = "USD"
  fee_pct = 0.0; fee_fixed = 0.0; latency_days = 2
  # USD arrives as USD — no destination-side conversion.

[route.coinbase_to_ibkr]                  # the cheap foreign path, fed by USD income
from = "coinbase"; to = "ibkr_usd"; status = "open"    # VERIFY withdrawal fees and limits
  [[route.coinbase_to_ibkr.leg]]
  kind = "transfer"; ccy = "USD"; fee_pct = 0.0; fee_fixed = 0.0
  # No FX leg at all: USD income never becomes UAH.
```

Derived per route and shown beside every instrument that needs it: **total in-cost %,
effective monthly deployment ceiling, latency, status, disruption probability**.

#### 4.3.1 The finding the route model exists to surface

Take the owner's own numbers. A P2P premium of **+2 to +4 UAH per dollar** against a
reference rate `R`:

```
one-way cost  = premium / R
round trip    ≈ 2 × premium / R          (buy in, sell out)
```

At a reference around 42 UAH/USD — **substitute the live rate; this is illustrative** — that
is roughly **4.8%–9.5% one way and 9%–19% round trip**, before exchange and network fees.

Set against the alternatives: the Inzhur route costs **0%**, and OVDP pays 15.5% tax-free.
So the crypto ramp alone can consume **most or all of a year of the risk-free domestic
return**, and it is invisible in every chart the current tool produces. That comparison —
not the choice of ETF, not the rebalancing frequency — is the largest single number in the
owner's decision, and it is the reason the route layer is P0.

The corollary from §4.2: for the **USD income stream** that cost is zero, because no
conversion happens. The same crypto purchase is cheap from Coinbase and expensive from
Monobank. **The tool must never quote one access cost per instrument — only per
(instrument × stream × route).**

#### 4.3.2 Route variants, and why the leg count is the point

The registry holds **one entry per (provider × currency path × venue)**, not one per
provider — because the number of FX conversions is usually the largest difference between two
ways of doing the same thing. Sending USD end-to-end converts once; going through EUR
converts twice and pays a second spread plus a destination-side conversion fee.

So route selection is a **modelled comparison, not a configuration constant**: given an
instrument and a stream, the tool ranks available routes by round-trip cost, ceiling and
latency, recommends one, and shows what the alternatives would have cost. Currency support
per provider is user-observed data (`ccy`, `source`, `verified_on`) — corridors get added and
dropped, and a stale assumption here silently distorts every comparison.

#### 4.3.3 Exit routes are separate and equally modelled

Getting money back into spendable UAH has its own chain, spread, limits and tax consequences.
**An asset that cannot be liquidated into spendable UAH at a reasonable cost is not worth its
NAV**, and the tool must not report it as if it were. Round-trip cost is the number that
belongs in the comparison; one-way figures live underneath it.

#### 4.3.4 Access regimes, and feasibility

```toml
[scenario.war_ends_2027]
transition_date = "2027-06-30"          # or a distribution over dates
before = "regime.wartime"               # constrained IBKR funding, caps, wide spreads
after  = "regime.normalized"            # direct funding, narrower spreads, no caps
```

This answers the owner's actual question: **pay the wartime route cost now, or hold
UAH/OVDP until IBKR can be funded normally?** — as a break-even on the transition date
(§1.3), with contributions before and after the date using different route sets.

The engine enforces caps, minimum tickets, lock-ups and latency. When a contribution cannot
be executed it applies the scenario's **fallback policy** — queue as UAH cash, deposit it,
redirect to a named instrument, or skip — and **reports every occurrence**. Silent execution
of an infeasible plan is a defect in the same class as the D-numbered defects in the audit.

### 4.4 Currency: computation, tax, and display

Three distinct roles, and conflating any two of them is a bug:

| Role | Value | Rule |
|---|---|---|
| **Base** currency | UAH | What the owner earns and spends; the ledger's home currency |
| **Tax** currency | UAH, at the **official NBU rate on each transaction date** | Fixed by law (§4.5); never affected by the display switch |
| **Display** currency | UAH or USD, user-switchable | A pure view transform — recomputes every figure and redraws every chart |

Requirements for the switch (decision 1):

- Every monetary figure, table and chart re-renders in the selected currency; nothing is
  left in the other one.
- Historical series convert at each date's rate, **not** at today's rate — otherwise a chart
  in USD misrepresents the past.
- Switching display currency changes which **CPI** deflates the real-terms view: Ukrainian
  CPI for the UAH view, US CPI for the USD view. A "real" number carries the currency it is
  real *in*.
- The switch **never** changes the tax computation, the realised amounts, or the ranking of
  strategies by after-tax UAH outcome. If a ranking flips when the display changes, that is
  a genuine finding about currency exposure and must be labelled as such, not hidden.
- FX rates are **two-sided per channel** (NBU official, interbank, bank non-cash, cash desk,
  card, P2P). A single mid-rate is never used for a transaction.
- **Tax on FX gains never received:** the trade uses a channel rate, the tax uses the NBU
  rate. This asymmetry is a headline effect and belongs in the attribution.
- UAH paths are **scenarios, never forecasts**: stable, gradual drift, step devaluation,
  user-defined.

### 4.5 Tax — researched values

Per decision 3, these were sourced from public information rather than left blank. **They are
starting values with citations (§12), not verified facts** — see §4.5.1.

| Tax class | PIT | Military levy | Total | Notes |
|---|---|---|---|---|
| **OVDP** (`ua_government_bond`) | **0%** | **0%** | **0%** | Interest on certain Ukrainian state securities is PIT-exempt, and the levy is not charged on income not subject to PIT. Applies to coupon and gain. **The single most decision-relevant number in the model.** |
| **Bank deposit interest** | 18% | 5% | **23%** | Withheld at source by the bank; no self-declaration |
| **ІСІ distributions** (Inzhur payouts) | **9%** | 5% | **14%** | Dividends paid by mutual investment funds / non-CIT-payers are taxed at 9% |
| **ІСІ unit disposal / redemption** | 18% | 5% | **23%** | Taxed as investment profit. **The fund redeeming its own securities is not a tax agent** → the individual self-declares |
| **Foreign securities disposal** | 18% | 5% | **23%** | Investment profit (art. 170.2). Computed in UAH at the official NBU rate **on the date of each operation**, so FX moves change the taxable base |
| **Foreign dividends** | **9%** (see conflict below) | 5% | **14%** | Dividends from non-residents are taxed at 9%. Foreign withholding is creditable against the PIT, but **not** against the levy |
| **Crypto** | *no adopted regime* | — | **scenario** | See below |
| **Filing** | — | — | — | Declare by **1 May**, pay by **1 August** of the following year |
| **Loss carryforward** | — | — | — | A negative investment result carries to following years — **but only if a declaration is filed for the loss year**. Skipping it forfeits the right |

**Crypto** has no adopted regime. Draft law 10225-д was *accepted as a basis* in September
2025 and was still "preparing for second reading" at the last recorded stage — **not law**.
It proposes 18% + 5% = 23% on net gains, with a transitional **5% + 5%** for assets acquired
before the law takes effect and sold during the first year. So the tool models crypto tax as
**named scenarios**: `current_practice`, `draft_18_5`, `draft_transitional_5_5`, and
`user_defined` — exactly the design revision 1 called for, now confirmed as necessary rather
than merely prudent.

**Two flagged conflicts and gaps**, which the tool must surface rather than resolve:

1. **Foreign dividends: 9% or 18%?** The 9% rate for dividends from non-residents is
   well-attested, but at least one investor-facing source states 18% for foreign dividends.
   That is a 9-point spread on a real cash flow. Ship both as selectable interpretations with
   the citation attached, defaulting to 9% with the conflict visible.
2. **The military levy is not creditable** against foreign withholding even where the PIT is.
   So a foreign dividend can suffer 15% abroad *and* 5% at home. This is one more argument
   for accumulating ETFs (§3.4): no distribution, no leakage.

Also worth encoding as a *strategy*, not just a rate: **the accumulating-UCITS structure
converts a recurring 14% dividend event into a single deferred 23% disposal event.** Whether
that wins depends on horizon and turnover — which is precisely the kind of question the
simulator exists to answer, so make it a built-in comparison.

#### 4.5.1 Sourcing discipline stays, even now that values exist

Rates and rules here are researched, dated and cited — not verified. Ukrainian tax law in
this area changed recently (the levy went from 1.5% to 5% in December 2024, and several
sources still show the old figure) and crypto legislation is mid-process. Therefore:

- Every value carries `value`, `source`, `retrieved_on`, `verified_on` (initially empty), and
  is editable in the UI.
- Every rate accepts a **dated schedule**, so a legislated change is modelled rather than
  requiring a rebuild.
- A value with an empty `verified_on` renders visibly marked, and any output depending on it
  carries that mark through.
- Tax residency is a **timeline**, not a constant, so a future move (e.g. Cyprus) is a
  scenario with dates — including positions held across the change.
- Standing notice in the UI: **assumptions and estimates, not advice.**

### 4.6 Risk — two tiers, never mixed into one number

**Tier 1 — statistical**, where usable history exists: FX, crypto, foreign equities. Keep the
existing metric set, and above all the **rolling-window distribution**.

**Tier 2 — scenario**, where history is absent or irrelevant. Each is an explicit user
assumption with a probability and an impact, and appears as a column in a stress matrix:

| Risk | Parameters |
|---|---|
| Sovereign stress / restructuring | probability, haircut, delay — applied to OVDP and indirectly to domestic funds |
| Fund illiquidity | window missed, redemption suspended, forced-exit haircut |
| Venture total loss (MilTech) | probability, from the instrument's outcome distribution |
| Exchange or custodian failure | probability of loss, per venue (Binance, Coinbase) |
| Route closure | probability per year, per route; effect = the plan becomes infeasible |
| Tax-law change | rate-schedule scenarios — including the crypto regime landing |
| Physical / war damage to underlying | for real-asset funds: probability, impairment |

**Portfolio Ukraine exposure** (§1.2) is a required output, with a correlated-stress view:
one bad Ukraine scenario must hit OVDP, Inzhur funds and UAH *simultaneously*, never as
independent draws. No Sharpe ratio or volatility figure is emitted for an assumption-driven
instrument.

### 4.7 Goals — target sum, target date, or both

Per decision 5, the plan has three variables: **monthly contribution**, **target sum**,
**target date**. The user fixes any two and the tool solves for the third:

| Fixed | Solved | Question answered |
|---|---|---|
| contribution + date | sum | "What will I have by 2035?" |
| contribution + sum | date | "When do I reach $100k?" |
| sum + date | contribution | "What must I put in monthly to hit $100k by 2035?" |
| all three | — | feasibility + **shortfall probability** across scenarios |

With all three fixed the output is the most useful of all: the probability of hitting the
goal, and the distribution of the shortfall when it misses. Goal amounts carry their own
currency (a target in USD and a target in UAH are different goals under devaluation), and
should be expressible in **real or nominal** terms.

### 4.8 Seeding existing holdings

Per decision 8. Critically, a seed is **not** just a current value — the tax engine needs
lots:

```toml
[[seed.holding]]
instrument = "ovdp_inzhur"; quantity = 0.0
acquired_on = "2025-06-01"; cost_uah = 0.0        # basis, per lot
[[seed.holding]]
instrument = "BTC"; quantity = 0.0
acquired_on = "2024-02-11"; cost_uah = 0.0; venue = "binance"
```

Seeding with value but no basis means every later disposal computes the wrong gain. Where the
owner genuinely does not know a basis, the UI must ask for an estimate and mark every
downstream tax figure as basis-estimated.

### 4.9 Engine: projection first, history for calibration

1. **Projection (primary)** — forward from today under stated assumptions. Contractual
   instruments produce exact schedules; market instruments follow a return model; discrete
   events (war end, restructuring, route closure, tax change) fire on scenario dates.
2. **Monte Carlo** — distributions over FX paths, market returns and event timing. Seeded and
   reproducible; the manifest records every assumption.
3. **Historical replay** — the existing DCA backtest, for calibration and for "what would
   have happened", clearly separated in the UI.

Same seed + same scenario ⇒ identical results; every displayed number traceable to ledger
events; the ledger invariants hold in all three modes.

---

### 4.10 Strategy space, objectives, constraints, and recommendation

This is the half of the product the owner named: *help me choose*. It sits on top of
everything above and is the reason the declarative layer has to be clean.

#### 4.10.1 The framework surface

Everything configurable lives in versioned data files, each field carrying `source` and a
date:

```
data/instruments/*.toml    the §3 registry — five classes
data/routes/*.toml         legs, caps, regimes, per (provider × currency path × venue)
data/tax/*.toml            jurisdiction rule packs with dated rate schedules
data/scenarios/*.toml      FX paths, discrete events, regime transitions, risk assumptions
data/strategies/*.toml     named allocations, per income stream
data/objectives/*.toml     objective + constraint sets (§4.10.3, §4.10.4)
```

Behind them, exactly **four** plugin interfaces: `Instrument` (§4.1), `Provider` (§7),
`TaxRule` (§4.5), `ReturnModel` (§4.9). Everything else is data.

**The framework test:** adding a new instrument, venue, tax regime or jurisdiction must be a
data-only change. If it requires an engine edit, the abstraction is wrong — and there is an
acceptance test for exactly that (§9).

#### 4.10.2 Generating candidates

Three sources, combined and de-duplicated:

1. **Named strategies** — hand-authored plans the owner wants to see (§5.1). Always included,
   never pruned silently.
2. **Systematic sweep** — the allocation simplex over the shortlist at a human step (5% or
   10%), **per income stream**, since streams have different route costs (§4.2). Coarse on
   purpose: a 1% grid implies precision the inputs do not support.
3. **Optimiser proposals** — points suggested by maximising the chosen objective directly,
   used as candidates to be scored like any other, never as the answer.

Everything then passes through **feasibility pruning** (§4.3.4): caps, minimum tickets,
lock-ups, route status, tax-cash requirements. Infeasible candidates are dropped *with the
reason recorded*, because "your preferred plan is impossible in March" is itself an output.

#### 4.10.3 Objectives — the owner picks, the tool never assumes

| Objective | Use when |
|---|---|
| **Max probability of reaching the goal** | *Default*, since a goal exists (§4.7) |
| Min expected shortfall (magnitude, not just probability) | The goal matters more than the upside |
| Max expected after-tax real terminal wealth | No binding goal; pure accumulation |
| **Maximin** — maximise the worst case across scenarios | Loss-averse; war and devaluation dominate the worry |
| Min Ukraine exposure subject to a return floor | Diversification is the actual objective (§1.2) |
| Max return subject to a drawdown or illiquidity cap | A specific pain threshold is known |

The objective is part of the run manifest. Two runs with different objectives are different
questions and must never be compared as if they answered the same one.

#### 4.10.4 Constraints — where the real value is

Constraints are how a human encodes what they will not do, and they are usually more
decision-relevant than the optimiser:

- **Feasibility** — caps, minimum tickets, lock-ups, route status (always on).
- **Liquidity floor** — "X UAH reachable within N days at no more than Y% cost."
- **Assumption-driven cap** — "MilTech and venture-like instruments ≤ 10% combined."
- **Exposure caps** — max Ukraine exposure; max single instrument; max share illiquid.
- **Stream rules** — e.g. "never convert USD income to UAH", which alone eliminates a large
  region of the simplex.
- **Effort limit** — max number of distinct instruments, max transactions per month. A real
  constraint for a human being, and one that optimisers habitually ignore.

Every binding constraint is reported with its shadow cost: *what the best feasible strategy
gave up to satisfy it*. That is how the owner learns whether a self-imposed rule is expensive.

#### 4.10.5 Robustness over optimality — the audit's lesson, restated

Choosing the allocation that wins the most likely scenario is precisely the in-sample
overfitting that `terezy grid` already learned to distrust (`REWRITE_BRIEF.md` §4.1, item 10).
The same discipline applies to allocations:

- Score every candidate under **every** scenario; report the distribution, not the best case.
- Distinguish **"sometimes best"** from **"never bad"**, and show both — they are usually
  different strategies, and the second is usually the better plan.
- Always include a **naive baseline** — 100% OVDP, and 50/50 OVDP + VWCE — and state plainly
  when nothing beats it. The direct analogue of the equal-weight verdict the current tool
  already prints honestly.
- **Stability check:** perturb each input by a small amount and re-rank. A recommendation that
  flips on a 1% change in an assumed spread or probability is noise, and must be labelled as
  such rather than presented as a finding.
- **Report an indifference band, not a point allocation.** If every allocation between 40%
  and 60% OVDP scores within the noise, the answer is "anywhere in 40–60%", and quoting
  "51.3%" is false precision that damages trust in everything else on the screen.

#### 4.10.6 Output: a shortlist with named characters

Not a winner — three to five strategies that differ in *kind*, each labelled with what it
trades away:

| Character | Roughly | Trades away |
|---|---|---|
| **Domestic income** | OVDP-heavy | Highest certain UAH yield; maximum Ukraine exposure |
| **Hard-currency preservation** | USD income → VWCE / IB01 | Diversified out of UAH; forgoes the tax-free 15.5% |
| **Split by stream** | UAH → OVDP, USD → VWCE | Cheapest route on both sides, near-zero conversion cost; two books to manage |
| **Barbell** | OVDP base + small crypto / MilTech sleeve | Tax-free floor plus convex tail; high dispersion, illiquid sleeve |
| **Wait-and-see** | OVDP now, foreign after normalisation | Keeps optionality; loses time in the market if the war runs long |

Accompanied by: the dominance table; the **deciding belief** wherever no strategy dominates
("B beats A only if the war ends after mid-2028" / "only if you assign MilTech less than a 20%
chance of total loss"); the binding constraints and their shadow costs; the indifference band;
and the stability verdict.

#### 4.10.7 Explanation is part of the output

For each shortlisted strategy the tool states *why* it ranks where it does: which term drove
the gap (tax, ramp, fee, FX, instrument), which constraint bound, and which single assumption
would flip the order. "Most of the gap is the 7% P2P ramp, not the asset" is worth more to the
owner than any ratio, and it is the sentence the whole framework exists to be able to write.

## 5. Outputs and UI

### 5.1 Plan — the configurator

Income streams with their arrival venues (§4.2); seed holdings (§4.8); goal mode (§4.7);
allocation across the registry, per stream. Each row shows inline: route in, round-trip cost
%, tax class(es), liquidity terms, risk tier, and whether it is data-driven or
assumption-driven. Access regime and war-end date; fallback policy; residency timeline.
**Display-currency switch** (§4.4) in the global header, persisted.

**Named strategies** are saved plans — "All OVDP", "OVDP + VWCE from USD income",
"MilTech 10%", "Wait for normalisation", "Barbell: OVDP + BTC". These are the models to
compare.

### 5.2 Feasibility panel — before any results

Monthly cap exceeded, minimum ticket unmet, lock-up beyond the horizon, route closed at the
plan's start, tax cash requirement unfunded, stream/instrument mismatch. **An infeasible plan
shows this panel instead of results**, naming the binding constraint and the shortfall.

### 5.3 The waterfall — "what you keep"

Per strategy, per instrument, per stream, in the selected display currency:

```
gross instrument return
 → route-in cost (fees + FX spread, per stream)
 → ongoing fees (management, custody, commissions)
 → tax (distributions · realised gains · withholding · exit)
 → route-out cost
 → inflation (UA CPI for the UAH view, US CPI for the USD view)
 = what you keep, in today's purchasing power
```

Every bar drills through to the ledger events and the rule that produced it, with its source
and `verified_on`. This is the direct answer to "compute real numbers".

### 5.4 Comparison — strategies × scenarios

Rows = named strategies; columns = scenarios (UAH stable/drifts/steps; war ends 2027/2029;
sovereign stress; crypto regime lands at 23%; crypto winter). Cells show the kept real
return; the summary states **dominance** where it exists and the **break-even assumption**
where it does not. Distributions wherever Monte Carlo ran.

**Required built-in comparisons**, because each answers a question the owner actually has:
OVDP-vs-everything (the 15.5% tax-free hurdle); accumulating vs distributing ETF; UAH stream
vs USD stream funding the same instrument; and MilTech's 25% target net of fee, tax and loss
probability.

### 5.4a Recommendation panel

The output of §4.10, presented as its own screen: the shortlist of three to five strategies
with named characters, the objective and constraint set that produced it (both editable in
place, re-running on change), the binding constraints with their shadow costs, the
**indifference band** rather than a point allocation, the naive-baseline verdict, the
stability verdict, and for each pair without dominance the **deciding belief**. A single
"optimal portfolio" number is never displayed.

### 5.5 Exposure and liquidity

Portfolio Ukraine exposure with correlated stress. A **liquidity ladder**: when each hryvnia
can realistically be accessed and at what cost — crypto same-day at the P2P spread, IBKR T+2
plus repatriation, OVDP at maturity or a thin secondary market, Inzhur only at its window —
plus an emergency test: "if I needed 200k UAH next month, what would it cost me?"

### 5.6 Assumptions ledger, and Explain

Every parameter with value, source, `retrieved_on`, `verified_on`, and whether it is observed
or assumed — editable in place, outputs recomputing, unverified values visibly marked.
Plain-language definitions on every metric; a link from every tax number to its rule; and a
short generated summary of *why* each strategy ranks where it does ("most of the gap is the
7% P2P ramp, not the asset").

---

## 6. Architecture, hosting, and the second user

Per decision 7: Python core, local web UI, later self-hosted, eventually multi-user.

- **Core** stays pure and deterministic (`REWRITE_BRIEF.md` §6): no I/O, no plotting, no
  formatting. Instruments, routes, tax packs, ledger, metrics, analysis.
- **API** owns orchestration and the typed result schema; the UI and CLI are both clients.
- **Owner-scoped from day one.** Every scenario, portfolio, seed and assumption row carries an
  `owner_id`, even while there is exactly one owner. Retrofitting tenancy into a
  single-tenant schema is the expensive mistake; carrying an unused column is free.
- **Auth is deferred, not designed out.** Localhost needs none. The moment it reaches a home
  server it holds a complete picture of the owner's finances, so: no third-party analytics,
  no CDN calls, secrets out of the repo, and authentication in front of it *before* it
  listens on anything but loopback. Write that down as a release gate.
- **Curated data is version-controlled** (§7) and shared across users; per-user data
  (holdings, goals, assumptions) is separate from it. Getting that boundary right early is
  what makes multi-user cheap later.

---

## 7. Data layer

Most of these instruments have no API, so curated, version-controlled, human-maintained files
are a **first-class source**, not a fallback.

1. **Instrument registry** — `data/instruments/*.toml` per §3, every field with `source` and
   `as_of`, reviewed in git like code.
2. **Series files** — dated CSVs: Inzhur NAV and distributions, OVDP auction yields, observed
   P2P premiums, bank/broker fee schedules. Low frequency, sourced, never silently
   interpolated in the cache.
3. **Automated sources** — NBU official FX and auction data; foreign prices *and*
   distributions; crypto prices; Ukrainian CPI and US CPI (both, for the display switch).
   Behind the provider interface, with provenance and the no-synthetic-caching rule.
4. **Fee, route and tax schedules** — dated, hand-maintained, with a staleness warning when
   `verified_on` or `retrieved_on` ages past a threshold. Route costs and tax rates both move;
   a silently stale value invalidates every comparison.
5. **Data-entry UI is part of the product** — the owner will maintain NAVs, P2P premiums and
   fee schedules by hand.
6. **Offline snapshot** for tests and demos; **run manifest** recording every input version,
   assumption and seed.

---

## 8. Questions the tool must answer

1. **"Does anything beat 15.5% tax-free OVDP?"** — the hurdle-rate comparison, after every
   other option's fees, taxes and access costs.
2. **"Fund IBKR now via TransferGo, or wait for normalisation?"** — break-even on the
   transition date.
3. **"Should my USD income and my UAH salary go to different places?"** — per-stream
   allocation, given that one has a ~0% and the other a 5–10% cost to reach USD assets.
4. **"Is MilTech's 25% worth it?"** — net of the 2% fee, the 14%/23% tax split, and the loss
   probability the owner assigns.
5. **"If the hryvnia devalues 30% in one step, what happens to each strategy?"** — including
   tax on foreign gains that devaluation creates without any USD gain.
6. **"Inzhur REIT versus VWCE, honestly."** — after entry/exit commissions, management fee,
   redemption windows, both tax treatments, both route costs, with USD-pegged rent exposure
   made explicit.
7. **"What does the Binance P2P spread actually cost me per year?"** — the ramp, quantified
   against the OVDP hurdle.
8. **"I need 200k UAH next month — what does that cost me under each strategy?"**
9. **"What if the crypto tax regime lands at 23%?"** and **"what if my USDC conversions are
   disposals?"** — both as scenarios.
10. **"When do I reach my target, and what's the chance I miss it?"** — the goal solver.
11. **"What if I move to Cyprus in 2028?"** — residency change mid-simulation.
12. **"Which strategies should I even be considering?"** — the shortlist with named
    characters, not a single winner (§4.10.6).
13. **"What would have to be true for B to beat A?"** — the deciding belief, stated as a
    testable threshold on one assumption.
14. **"Is my own rule expensive?"** — the shadow cost of a self-imposed constraint, e.g.
    capping MilTech at 10% or refusing to convert USD income.
15. **"Does anything beat just holding OVDP?"** — the naive-baseline verdict, answered
    honestly including when the answer is no.

---

## 9. Acceptance tests

In addition to the engine charter in `REWRITE_BRIEF.md` §7.

**Contractual instruments**
- OVDP bought at a stated price and held to maturity reproduces a hand-computed coupon and
  principal schedule exactly, and pays **zero** tax under the exempt class.
- Coupon reinvestment into the then-current yield curve matches a hand-computed two-period
  example.
- A restructuring scenario with a 40% haircut and two-year delay produces exactly the
  hand-computed shortfall.

**Tax**
- Inzhur distribution taxed at 9% + 5%; redemption of the same units taxed at 18% + 5%; both
  in one run, from one instrument — the two classes must not collide.
- A loss year followed by a gain year nets correctly, **and** a run that omits the loss-year
  declaration forfeits the carryforward (both branches tested).
- Foreign dividend with 15% withholding: PIT credit applied, **levy not credited**.
- Crypto scenarios `current_practice`, `draft_18_5`, `draft_transitional_5_5` produce three
  different, hand-checkable results from identical market data.
- Every tax figure renders with source and `verified_on`; empty `verified_on` marks the
  figure and everything derived from it.

**FX, display, and asymmetry**
- **A position flat in USD across a devaluation produces a positive taxable gain in UAH.**
- Switching display currency changes no realised amount, no tax figure, and no after-tax UAH
  ranking; historical series convert at per-date rates, not today's rate.
- The real-terms view uses UA CPI in the UAH display and US CPI in the USD display.
- Cash-vs-non-cash channel selection changes the result and is visible in attribution.

**Streams and routes**
- The same crypto purchase funded from the UAH salary and from the USD income yields
  different net positions, differing by exactly the hand-computed ramp cost.
- A P2P premium of +3 UAH at a reference rate reproduces the §4.3.1 percentage exactly.
- A plan exceeding a monthly cap queues the excess per the fallback policy and reports each
  occurrence; total deployed equals the cap, never the plan.
- Regime transition on the war-end date switches the route set; round-trip cost drops by
  exactly the hand-computed difference.
- Two variants of one route differing only in conversion count rank in the expected order.
- No comparison reports a one-way cost as if it were round-trip.

**The framework surface**
- Adding a new instrument, a new route, a new tax class and a new jurisdiction **in data only**
  — no engine edit — runs the full pipeline and appears in the comparison. This is the test
  that the abstraction is real.
- A malformed or unknown field in any data file fails loudly at load time, naming file and
  field; it never silently defaults.
- Every data file's values round-trip through the run manifest, so a result can be traced to
  the exact configuration that produced it.

**The decision layer**
- Feasibility pruning drops infeasible candidates **with a recorded reason**, and the count of
  dropped candidates is reported, never silently swallowed.
- Two objectives over the same candidate set produce different rankings, and each run's
  manifest records which objective was used.
- A binding constraint reports a non-zero shadow cost; a non-binding one reports zero.
- The naive baseline (100% OVDP; 50/50 OVDP + VWCE) is always scored and always shown — and a
  synthetic case where nothing beats it produces the honest "nothing beats it" verdict.
- **Stability:** perturbing one assumed input by 1% must not silently change the top
  recommendation; if the ranking flips, the run is labelled unstable.
- **Indifference band:** a synthetic case where a range of allocations scores within noise
  reports the band, not a point; no allocation is ever reported to sub-percent precision.
- "Sometimes best" and "never bad" are computed separately, and a synthetic case where they
  differ shows both.

**Goals, seed, liquidity, honesty**
- The three goal modes are mutually consistent: solving for date from (contribution, sum) and
  then for sum from (contribution, that date) returns the original sum.
- A seed lot with a known basis produces the hand-computed gain on disposal; a
  basis-estimated seed marks every downstream tax figure.
- Redemption outside an Inzhur window is refused, or executed at the stated haircut when
  allowed — taxed correctly either way.
- A lock-up longer than the horizon is a feasibility error, not a silent simulation.
- Correlated stress hits OVDP, Inzhur and UAH simultaneously, never as independent draws.
- No Sharpe ratio is emitted for an assumption-driven instrument.

---

## 10. Phasing

| Phase | Deliverable | Contents |
|---|---|---|
| **P0** | The framework, and honest comparison of named strategies | Declarative data layer + the four plugin interfaces (§4.10.1) · instrument interface + the §3 registry · income streams (§4.2) · route layer with the owner's real venues · UAH base, two-sided channel rates, USD display switch · UA tax pack with the §4.5 values · projection mode · goal solver · seed · feasibility pruning · waterfall + comparison of *hand-authored* strategies against the naive baseline · the §9 tests |
| **P1** | The decision layer, and the UI | Candidate generation (sweep + optimiser proposals) · objectives and constraints with shadow costs · robustness scoring, stability check, indifference bands, dominance and deciding beliefs · the shortlist with named characters (§4.10.6) · configurator, feasibility panel, scenario matrix, exposure gauge, liquidity ladder, assumptions ledger, explain layer · Monte Carlo · saved and diffable strategies |
| **P2** | Depth where the money is | Inzhur specifics (windows, tiered exit fees, USD-pegged income), venture outcome model, residency change, crypto-regime scenarios, emergency-cash test, decumulation |
| **P3** | Breadth and hosting | More instruments, brokers, routes, jurisdictions · auth + multi-user (§6) · data-entry UI polish · staleness monitoring |

`REWRITE_BRIEF.md` P0 — ledger, lots, cash, multi-currency, provenance — is a prerequisite
for P0 here, not a parallel track.

---

## 11. Remaining open questions

Everything from revision 1 is answered (§0). What is still needed:

1. **Actual observed numbers** for the route registry: Monobank's UAH→USD card markup and
   monthly limit, TransferGo's live USD quote, Coinbase withdrawal fees, Binance fee tier.
   Your observations beat any published schedule.
2. **Inzhur product terms** to confirm: REIT and MilTech entry/exit commissions, redemption
   windows and notice periods, whether REIT rents are genuinely USD-pegged, and the current
   OVDP issue's yield and maturity rather than a headline 15.5%.
3. **Monthly amounts per stream** — UAH salary surplus and USD contract income — and the seed
   holdings with acquisition dates and costs.
4. **The USDC question** (§4.2): does Deel money arrive at Coinbase as USD or as a
   stablecoin? It changes which conversions are potentially taxable events, and it is worth
   one professional consultation.
5. **Goal**: target sum, currency, date, and whether it is nominal or real.
6. **Risk assumptions only you can set**: probability of total loss for MilTech, of sovereign
   restructuring, of exchange failure, of each route closing.

---

## 12. Sources for the tax values

Retrieved 2026-08-21. Cited so each value can be re-checked and superseded; none is verified
against primary legislation, and the owner handles his own filings (decision 3).

- Ukraine State Tax Service — PIT and military levy rates, 2026 declaration campaign:
  <https://tax.gov.ua/deklaratsiyna-kampaniya-2026/stavki-podatku-na-dohodi-fizichnih-osib-ta-viyskovogo-zboru>
- PwC Worldwide Tax Summaries, Ukraine — individual income determination: the 9% rate for
  dividends from non-residents, mutual investment funds and non-CIT payers; 18% on interest
  and passive income; exemption for interest on certain Ukrainian state securities; 5% levy
  on income taxed with PIT:
  <https://taxsummaries.pwc.com/ukraine/individual/income-determination>
- Military levy scope, including that it is not charged on income not subject to PIT
  (Oschadbank guide, 2026): <https://www.oschadbank.ua/blog/vijskovij-zbir-2026-cinni-stavki-dedlajni-ta-perelik-pilg>
- Investment profit: 18% + 5%, art. 170.2.2, loss carryforward conditional on filing a
  declaration for the loss year, NBU rate on the date of the operation, declare by 1 May /
  pay by 1 August (YANKIV):
  <https://yankiv.com/opodatkuvannya-investytsiy-ukraina-pdfo-vijskovyj-zbir-ovdp/>
- ІСІ: 9% on fund distributions; investment profit on unit disposal; the issuer redeeming its
  own securities is not a tax agent (Invest-Tandem, KINTO):
  <https://itandem.com.ua/podatky-investoriv-isi/> ·
  <https://kinto.com/investing-from-a-tax?language_content_entity=uk>
- Crypto: draft law 10225-д, status "preparing for second reading", accepted as a basis
  2025-09-03 — **not adopted**; proposed 18% + 5% with a 5% transitional rate:
  <https://itd.rada.gov.ua/billinfo/Bills/Card/56271> ·
  <https://www.ey.com/en_ua/it-tax-law-digest/the-draft-law-on-the-taxation-of-income-from-virtual-assets-approved-by-the-parliamentary-committee>
- Conflicting claim of 18% on foreign dividends (the §4.5 conflict to surface):
  <https://iclub.vc/insights/taxes-for-ukrainian-investors-in-2026.html>
- Non-resident-alien US estate tax above USD 60,000, treaty withholding, and the UCITS
  domicile argument (Bogleheads):
  <https://www.bogleheads.org/wiki/Nonresident_alien_taxation> ·
  <https://www.bogleheads.org/wiki/Nonresident_alien_investors_and_Ireland_domiciled_ETFs>
- Inzhur product facts — minimum tickets, MilTech fee "up to 2% of average AUM", account
  opening free, NSSMC licence: <https://www.inzhur.reit/offer/inzhur-miltech> ·
  <https://www.inzhur.reit/offer/inzhur-reit> · <https://investor24.com.ua/brokers/inzhur/>

---

## 13. Relationship to existing documents

| Document | Role |
|---|---|
| `docs/SIMULATOR_SPEC.md` (this) | **Product specification.** What the tool is for, what it models, what it must answer. |
| `docs/REWRITE_BRIEF.md` | **Engineering audit and engine spec.** Its §4.1 (preserve), §4.2 (defects), §5.1–5.4, §5.7, §6, §7 remain authoritative; its §1–2 and §5.5–5.8 are superseded here. |
| `docs/METHODOLOGY.md` | Formulas as implemented today. Port forward; extend with contractual-instrument, route and FX-channel maths. |
| `docs/LEGACY_REVIEW.md` | The 12 original financial-math bugs. Still the list of mistakes not to repeat. |
| `terezy/` + `tests/` | The correct market-mechanics core to build on: 64 tests, no network, ~3 s. |
