# Implementation Plan: Tax depth

**Feature**: `009-tax-depth` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Branch**: `feat/009-tax-depth`, landing on `main` by a `--no-ff` merge after a clean
review pass.

## Summary

Feature 001 built the tax interface and proved it on an exempt class — a flat zero, charged
per event. This is everything hard that was left: losses that carry between years, lots the
owner chooses between, and tax that is paid with real money on a real date.

The shape, decided in [research.md](./research.md). A **tax year is a record built by a
fold**, so no code path can deduct tax at event time — defect B5 cured structurally rather
than by discipline. A **payment is an ordinary ledger event**, on 008's seed precedent, so
cash conservation covers it without being taught it exists. **Due dates are declared data**
and their absence is a refusal.

And the spine: **four lot-selection methods, four figures, and none of them is "the tax you
owe"**. The legal texture is genuinely unresolved — the ПКУ prescribes no method, ДПС
guidance points at proportional/average-cost for a self-declarant, Методика МФУ № 1484
prescribes FIFO where an agent computes, and the taxpayer's freedom to choose is unsettled.
Every figure states the method that produced it; the two source-backed candidates carry
their citations; and for a self-declarant they **give different numbers**, which the output
shows rather than reconciles.

## Technical Context

**Language/Version**: Python 3.13; CI matrix 3.12 / 3.13 / 3.14.

**Primary Dependencies**: none new.

**Storage**: version-controlled TOML — due-date rules under `data/tax/`, unsettled-question
switches under `data/scenarios/`. No network.

**Testing**: pytest. Hand-computed arithmetic for the four-method fixture (FR-025) and for
the filed/unfiled branches; Hypothesis for conservation over ledgers containing payments;
001's golden as the regression.

**Target Platform**: library only.

**Project Type**: single Python library, `cli → api → data → core`.

**Constraints**: core pure, no clock; exactly four plugin interfaces and **this feature adds
none**; functional style per D-E; one imported tolerance; **no tax deducted at event time**.

**Scale/Scope**: 3 new core modules, ~4 touched, 2 new declaration kinds, ~12 test modules.
Closes **E2**, **E6** and **E7** (partially — see below).

## Constitution Check

| Principle | Verdict |
|---|---|
| **I — Honesty over precision** | **PASS, and FR-024 is the sharpest application in the repository so far.** Four methods produce four different tax figures and the law does not say which is right; emitting one as "the tax you owe" would be a number more confident than its inputs, where the input is an unanswered legal question. Four labelled what-ifs, each naming its method and citation, is the honest shape. Insufficient cash is a typed insolvency report, not a silent sale. |
| **II — Framework, not script** | **PASS.** No fifth interface. Due dates, carryforward rules and the unsettled switches are all data; the four methods are a mapping of functions on the established registry pattern. A withheld-at-source class becomes a data-only addition (FR-003) without being implemented here. |
| **III — Pure deterministic core** | **PASS.** No clock: every date is declared or passed. The tax year is a fold over events, so the same ledger yields the same statements. |
| **IV — Reliability through contracts** | **PASS.** Conservation properties extend to ledgers containing payment events — and must pass **unchanged**, as 008's did for seeds. One imported tolerance. Every degraded outcome is a typed union member. |
| **V — Test-first** | **PASS.** FR-025's three-lot fixture is hand-computed under all four methods and constructed so the four results are **pairwise distinct** — a fixture where two methods agree cannot detect a method being silently substituted. |
| **VI — Model the whole tuple** | **PASS.** The tax term gains its real depth here. Currency roles stay separate; see the boundary below. |
| **Engineering Standards — D-E** | **PASS.** Methods are a mapping of functions, statements and refusals are frozen records, outcomes are tagged unions matched with `match`. |
| **VII — Owner-scoped and private** | **PASS.** Due-date rules and carryforward rules are curated legal facts in `data/tax/`; whether the owner filed a loss-year declaration is his own per-run input and is never inferred. |

### Post-Phase-1 re-evaluation

Three things the design surfaced:

- **The word "the" is the defect.** "The tax you would owe" is one figure; the law supports
  at least two, and picking between them is the unanswered question. The result shape must
  make a single unlabelled liability *unrepresentable*, not merely discouraged.
- **A zero year still produces a statement, and produces no payment.** Those are two
  different claims and both are required — FR-006 and FR-026 together. A missing statement
  and a statement saying zero are distinguishable, and 001's golden depends on the second
  producing no cash movement.
- **The levy's base is the netted base.** Assessing it on gross while the PIT uses the
  netted figure yields a levy whose base exceeds the PIT's, which no reader catches from a
  total. SC-011 exists for exactly this.

## A boundary this feature must not cross

**The official rate does not exist yet.** Feature 011 is `drafted`, not built. FR-024 of
*this* spec keeps computation in the amounts' own currencies and tax in the tax currency —
which is only reachable today because every taxable event in the shipped registry is already
hryvnia. **A foreign-currency taxable event must refuse**, naming the missing official-rate
machinery, rather than converting at a channel rate. A channel is a market you transact in;
the official rate is a legal reference you never transact at, and 002 already refuses to
substitute one for the other at `legs.py::channel_for`.

## Project Structure

```text
src/terezy/core/
├── tax/
│   ├── year.py                 NEW — assessment to a year, netting, carryforward
│   ├── lots.py                 NEW — the four selection methods as a mapping of functions
│   └── registry.py             TOUCHED
└── results/
    └── tax_year.py             NEW — AnnualStatement, the payment record, typed refusals

data/
├── tax/                        due-date rules, with provenance
└── scenarios/                  the UNSETTLED switches, labelled as beliefs
```

```text
tests/worked_examples/
├── test_four_lot_methods.py    FR-025, SC-002 — one fixture, four hand-computed figures
├── test_loss_carryforward.py   SC-001 — filed and unfiled, both by hand
└── test_tax_payment.py         SC-003 — nothing leaves a position at event time

tests/invariants/
└── test_ledger_conservation.py TOUCHED — SC-006, now over ledgers containing payments

tests/unit/
├── test_annual_statement.py    FR-001, FR-002, FR-006
└── test_insufficient_cash.py   SC-004 — typed, naming the shortfall

tests/contract/
├── test_tax_declaration_loading.py  SC-007 — the whole misdeclaration battery
├── test_method_is_never_implicit.py FR-024 — no figure without its method
└── test_unsettled_is_labelled.py    SC-012

tests/golden/
└── test_end_to_end_ovdp.py     UNCHANGED FILE — SC-009, bit-identical
```

## Complexity Tracking

| Added complexity | Why | Alternative rejected because |
|---|---|---|
| Every tax figure carries its method | FR-024: the law supports two readings that give different numbers | A single liability figure would have to pick one, and picking is the unanswered question |
| The filed/unfiled branch is a required input | Two defaults, two different wrong answers | Either default silently changes the after-tax ranking |

## Phase 2 note

Order: **the annual statement and the payment event first, with 001's golden green** —
that proves the fold gained a year without moving a figure. Then the due-date declaration
and its refusals; then netting and carryforward with both branches; then the four methods.
Tests before implementation in each group.
