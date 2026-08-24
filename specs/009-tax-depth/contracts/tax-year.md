# Contract: the tax year, the payment, and the four methods

**Feature**: `009-tax-depth` | **Modules**: `terezy.core.tax.year`,
`terezy.core.results.tax_year`, `terezy.core.ledger.lots`

## Signatures

As built. The three departures from the drafted shape are argued in
[research.md](../research.md) D10 and in the note below.

```python
def statements(state, charges, *, rules, tax_classes, filing, switches
               ) -> tuple[AnnualStatement, ...] | TaxYearRefused
def settle(events, statements, *, owner_id, base_currency, method, horizon_end
           ) -> Settlement | SettlementRefused
def basis_consumed(lots, quantity, *, method, named_lot=None) -> Selection | LotRefusal
```

Pure. No clock. `filing` and `switches` are required with no default.

**`statements` takes no basis method.** It reads `state.consumption_method` — the field that
decided which lots each disposal actually drew on — so the label on a figure and the
arithmetic behind it cannot disagree. That is not a default appearing: the name is still
required, one layer up, by `engine.opening`. **`settle` does take one**, because it folds the
raw stream before it has looked at the statements and must fold when there are none; it
refuses where the method it folds under is not the one the statements were assessed on.

**`statements` takes the charges beside the ledger** rather than deriving them, because a
charge is produced together with its event by `tax.flat_rate` and re-deriving it here would be
a second answer to a question already answered. `tax_classes` comes with them: the year needs
the *rates* in force to charge a netted base, and a charge carries the provenance of its dated
entry rather than the entry itself.

## Guarantees

**G1 — No tax is deducted at event time.** Gross amounts land in the ledger and the charge
is recorded beside them; the year is assembled afterwards by a fold. Defect B5 is
unrepresentable, not merely avoided. (FR-001)

**G2 — A statement is verifiable from the ledger.** Every charge it contains names its event
and its rule, so the liability can be checked without re-deriving it. (FR-002)

**G3 — A payment is an ordinary ledger event.** Dated by the declared rule, debiting the
tax-currency balance, naming the statement it settles, participating in cash conservation
and traceability like everything else. (FR-004)

**G4 — Due dates are data.** No constant in the engine; a missing rule is a refusal naming
the missing declaration. (FR-005)

**G5 — A zero year still produces a statement, and produces no payment.** Two distinct
claims, both required. (FR-006, FR-026)

**G6 — A liability assessed but not yet due at the horizon is reported as outstanding**,
never dropped and never brought forward into the horizon. (FR-007)

**G7 — Insufficient cash is a typed report** naming the shortfall, the date and the
statement. Nothing is sold, nothing clamped, no position touched. (FR-009, FR-012)

**G8 — Netting is within the year and within the category**, and the levy is assessed on the
**same netted base** as the PIT. (FR-013, FR-017)

**G9 — The filing branch is declared.** Filed reduces later years by the carried loss;
unfiled taxes later gains in full and **names the forfeited amount** so the cost of not
filing is visible. Neither is a default. (FR-014, FR-015, FR-016, SC-010)

**G10 — A carryforward still open at the horizon is reported.** (FR-019)

**G11 — Four methods, four figures, none of them "the tax you owe".** Every figure states
the method that produced it; the two source-backed candidates carry their citations; the
choice between them is a labelled UNSETTLED switch. No type can express an unlabelled
liability. (FR-020, FR-024)

**G12 — Specific-lot names its lot; every other method refuses one.** A disposal naming a
lot under FIFO is a refusal, not a silently ignored hint. (FR-021, FR-022)

**G13 — Average-cost consumes basis proportionally** over the packet, per пп. 170.2.7's
definition of the investment asset. (FR-023)

**G14 — Every figure under an unsettled switch is labelled with it.** (SC-012)

**G15 — 001's exempt results are bit-identical.** Per-event zero charges still recorded, no
payment event from a year of exclusively exempt income, and every figure, schedule row, charge
and ledger line in the golden artefact unchanged — its `== digest ==` has not moved. The
artefact's `== inputs ==` sha256 lines did move, deliberately and for reasons outside the
engine: upgrading the OVDP citation to the primary text changed `data/tax/ua.toml`, and
`canonical.py` excludes provenance from the digest by design. (FR-026, SC-009)

## The boundary

**A foreign-currency taxable event refuses**, naming the missing official-rate machinery.
Feature 011 is `drafted`, not built. Converting at a channel rate would substitute a market
you transact in for a legal reference you never transact at — the substitution 002 already
refuses at `legs.py::channel_for`. Every taxable event in the shipped registry is hryvnia,
so this refusal is unreachable today and must exist anyway.
