# Phase 0 research: tax depth

**Feature**: `009-tax-depth` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

The spec did the legal research and labelled every fact **SETTLED**, **INTERPRETED** or
**UNSETTLED**. Nothing here re-opens that. These are the shape decisions the implementation
rests on, and D5 is the one the whole feature turns on.

---

## D1 — A tax year is a record, not an accumulator someone remembers to reset

**Decision.** `AnnualStatement` in `core/results/tax_year.py`: a frozen record per
`(tax year × income category)` holding the charges that compose it, the netted result, and
the liability. Produced by a fold over the ledger's charges, never mutated.

**Rationale.** FR-001 and FR-002. The predecessor defect B5 is tax deducted at event time;
the cure is that no code path *can* deduct one, because charges land beside events and the
year is assembled afterwards from what is there. A record built by a fold is also
verifiable from the ledger without re-deriving it, which FR-002 requires in as many words.

## D2 — Payment is an ordinary ledger event, on 008's seed precedent

**Decision.** The year's liability is settled by a dated event debiting the tax-currency
cash balance, carrying a `CausationRef` naming the `AnnualStatement` it settles. It goes
through the same `engine.fold` every other event does.

**Rationale.** FR-004, and the precedent is exact: feature 008 made a declared seed an
ordinary opening event so every conservation invariant counted it without being taught it
exists. Do the same here and cash conservation covers tax payments for free. **If a
conservation property fails only for runs containing a payment, fix the event — never the
invariant.**

## D3 — Due dates are declared data, and their absence is a refusal

**Decision.** A `[[due_date]]` declaration under `data/tax/`, carrying the rule, its source,
its retrieval date and an empty verification date. No constant in the engine. A scenario with
a taxable event and no declared rule fails naming the missing declaration.

**Rationale.** FR-005. The researched starting values — declare by 1 May, pay by 1 August —
are legal values and enter as data like every other. This is the same discipline 006 applied
to rates, and 006's dated-schedule machinery is the precedent for the shape.

## D4 — The filed/unfiled branch is a declared input, never inferred

**Decision.** Whether the loss-year declaration was filed is an explicit per-run input with
no default. Absent it, the run refuses.

**Rationale.** FR-014, and the spec states the reason better than a paraphrase would: *"the
tool assumed you filed"* and *"the tool assumed you did not"* are **different wrong answers**,
and each silently changes the after-tax ranking. A default here would pick one of them.

## D5 — Four methods, four figures, and none of them is "the tax you owe"

**Decision.** FIFO, LIFO, average-cost and specific-lot are all computable. **Every tax
figure states the method that produced it**, and no result may be labelled as the liability
until the ІПК answers. The two source-backed candidates carry their citations on their
results; which one a "most likely" reading takes is an UNSETTLED scenario switch, labelled
like every other.

**Rationale.** FR-024, and this is the feature's spine. The legal texture is genuinely
unresolved: the ПКУ prescribes no method (settled *by absence*), ДПС guidance points at
proportional/average-cost for a self-declarant, Методика МФУ № 1484 п. 3.3 prescribes FIFO
where an agent computes, and the taxpayer's freedom to choose is unsettled.

**The trap is the word "the".** Emitting one number as the tax owed would be a figure more
confident than its inputs, and the inputs here are a legal question nobody has answered.
Four what-if figures, each naming its method and its citation, is the honest shape — and for
a self-declarant the two source-backed methods **give different numbers**, which the output
must show rather than reconcile.

**No method may be the default.** A caller states one; there is no fallback.

## D6 — An unsettled question is a declared scenario switch, not a code branch

**Decision.** Each UNSETTLED item is a declared switch under `data/scenarios/`, carrying its
question, the position taken, and the fact that an індивідуальна податкова консультація
(ст. 52 ПКУ) is the resolution path. Every figure produced under one is labelled with it.

**Rationale.** `data/scenarios/` already holds the owner's beliefs and is exempt from the
citation gate for exactly this reason — an assumption needs a label and a visible
consequence, not a source. An unsettled legal reading is the same epistemic object as a
war-end date. Putting it in code would make a belief look like a rule.

## D7 — Insufficient cash is a typed insolvency report, and the forced sale stays deferred

**Decision.** When the tax-currency balance is smaller than the liability on the due date,
the run produces a typed result naming the shortfall, the date and the statement. Nothing is
sold, nothing is clamped, no position is touched.

**Rationale.** FR-009 and FR-012, and `features.toml` already records `forced-sale-policy`
as the owner-deferred decision about which positions a forced sale draws on. Choosing one
here would be the tool making a portfolio decision the owner explicitly reserved.

## D8 — Netting is per year and per income category, and the levy follows the same base

**Decision.** Gains and losses net within a tax year to an annual result per category; the
military levy is assessed on the same netted base as the PIT, not on gross.

**Rationale.** FR-013 and FR-017. SC-011 is the executable form — in a year whose gain is
reduced by a carried loss, both charges reflect the reduction. Getting this wrong produces a
levy larger than the PIT's own base, which no reader would catch from the total alone.

## D9 — Feature 001's golden is bit-identical, and that is the regression

**Decision.** `tests/golden/ovdp_synthetic_a.golden.txt` unchanged. Per-event zero charges
continue to be recorded, and a year of exclusively exempt income produces **no payment
event**.

**Rationale.** FR-026, SC-009. A year with a zero liability still produces a statement
(FR-006) — an annual statement saying zero is a different claim from no statement at all —
but zero owed generates no payment, so no cash moves and the golden cannot move.

**State the expected diff before regenerating anything.** If the golden moves, the exempt
path grew a behaviour it should not have.

## D10 — Where the code lives

- `core/tax/year.py` — assessment to a year, netting, carryforward.
- `core/tax/lots.py` — the four selection methods, as a mapping of functions (D-E).
- `core/results/tax_year.py` — `AnnualStatement`, the payment record, the typed refusals.
- `data/tax/` — due-date rules; `data/scenarios/` — the unsettled switches.

`core/ledger/lots.py` already holds FIFO and LIFO; the two new methods join them there or in
`core/tax/lots.py` — decide by where the existing two live and keep all four together. Four
methods split across two modules is how a fifth ends up in a third.
