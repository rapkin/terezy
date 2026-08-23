# Contract: the fund instrument declaration

**Feature**: `006-inzhur-instruments` | **Files**: `data/instruments/inzhur_reit.toml`, `inzhur_miltech.toml`, `synthetic_fund_c.toml`

A collective-investment fund declared as data. Three files: the two real funds, and a third
synthetic one with different liquidity terms, spread, peg and tax classes, which is SC-010's
proof that a fund is data rather than code.

## Shape

```toml
# Researched from the fund's primary public documents (регламент and проспект), read in
# full on 2026-08-22. **Researched is not verified**: every value below carries its citation
# and an EMPTY verification date until the owner checks it against his investor cabinet,
# and the mark propagates to every figure derived from it.
#
# This is an ASSUMPTION-DRIVEN instrument. No volatility, no Sharpe, no statistical metric
# may ever be emitted for it -- its projections are contractual arithmetic over declared
# terms, and the output says so.

[instrument]
id                     = "inzhur_reit"
class                  = "collective_investment_fund"
unit_currency          = "UAH"
is_assumption_driven   = true
minimum_units          = 1.0
terminates_on          = "2045-05-20"

  [instrument.declared_yield]
  low   = 9.5
  high  = 9.5
  basis = "usd_equivalent_annual"
  # Fund-stated target, not a promise and not an observation of the market. The shown
  # trailing twelve months (11.52%) is recorded as an observation elsewhere, never as a term.
  source       = "..."
  retrieved_on = "2026-08-22"
  verified_on  = ""

  [instrument.tax_classes]
  distribution  = "ua_ci_fund_distribution"
  disposal_gain = "ua_investment_profit"

  [[instrument.verification_task]]
  question    = "The rate-fixing rule converting each pegged payment: which rate, on which date?"
  searched    = "регламент, проспект"
  searched_on = "2026-08-22"
```

`[[verification_task]]` carries **no value field**, deliberately: there is nowhere for a
number to be put by a later contributor in a hurry.

## Guarantees

**G1 — Two classes, one instrument.** `tax_classes` maps event kind to class id, and the two
values differ: distributions under the fund-distribution class, redemption gain under
investment profit. Neither class's rates are ever applied to the other's events. (FR-006,
FR-007)

**G2 — Assumption-driven is enforced, not labelled.** Asking either fund for a statistical
metric returns a typed refusal. No result record has a field one could sit in. (FR-004,
FR-005, SC-009)

**G3 — Every fund-stated value is marked, and the mark propagates.** With any term left
unverified, 100% of figures derived from it carry the mark. (FR-002, SC-008)

**G4 — The spread is the modelled access cost; fees are context.** Purchase at NAV plus the
declared entry markup, exit at NAV minus the declared discount, round-trip erosion its own
line. No management fee, no performance fee, no coupon reinvestment is computed. (FR-023,
FR-024, owner decision B)

**G5 — Both liquidity modes are projectable, and the mode is always stated.** No default —
defaulting to the practice mode would quietly promise same-day NAV liquidity the регламент
does not owe. (FR-015, FR-016)

**G6 — A refused redemption leaves the holding open.** Nothing silently executed, adjusted
or deferred. (FR-017)

**G7 — A pegged payment needs a declared rate assumption.** Absent one, a typed degraded
result naming that input. Where the assumed rate exceeds the declared cap, the payment is
sized at the cap and the output says the cap bound. A USD-equivalent term is never itself
treated as money. (FR-020–FR-022)

**G8 — A range stays a range** unless an explicitly declared point overrides it, labelled the
owner's assumption. There is no midpoint helper. (FR-023, SC-013)

**G9 — Data only.** A third fund with different terms declared purely as data projects
correctly with zero lines of source changed. (SC-010)

## Refusals at load

| Condition | Why |
|---|---|
| A term with a value but no `source` / `retrieved_on` | The provenance gate; empty `verified_on` is expected |
| `tax_classes` naming an undeclared class | The loader's existing `_known` path |
| A `verification_task` carrying a value | The whole point of the record is that it holds none |
| `is_assumption_driven = false` | Not expressible in this feature — the field is `Literal[True]`; a fund whose terms are observed rather than stated is a different declaration and a different feature |
| Missing `terminates_on` | A fund with no termination date has no guaranteed exit, which FR-019 needs to name |
| Extra keys | `STRICT`, as every other declaration |
