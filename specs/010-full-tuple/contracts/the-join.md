# Contract: the join and the comparison

**Feature**: `010-full-tuple` | **Modules**: `terezy.core.decision.tuple_outcome`, `terezy.core.decision.compare`

## Signatures

```python
def evaluate(tuple_: Tuple, *, amount: Money, horizon: DateRange, declarations) -> TupleOutcome | TupleRefused
def compare(tuples: Sequence[Tuple], *, amount: Money, horizon: DateRange, declarations) -> Comparison
```

Pure. No clock. The horizon is stated once and applies to every tuple.

## Guarantees

**G1 — The join invents nothing.** Every term comes from the call that owns it; the join sums
and chains. (FR-002)

**G2 — Both seams are anchored, and a mismatch names both sides.** The route in must end
where and in the currency the purchase begins; the instrument's exit must produce a balance
where the route out starts. (FR-004)

**G3 — Each part's contribution is separately reported**, so a reader sees which term
dominates and can go check it. (FR-005)

**G4 — A missing declaration in any of the four parts is a typed refusal naming it.** (FR-006)

**G5 — No declared exit route, or no declared exit terms, inherits 002 FR-030's refusal** —
a one-way figure is never promoted. (FR-007, FR-008)

**G6 — Keyed per `(instrument × stream × route in × exit terms × route out)`.** The same
instrument from two streams is two outcomes. (FR-010, SC-004)

**G7 — The benchmark is a tuple through the same code path**, asserted by construction, not
by comparing numbers that agree. (FR-012, SC-002, SC-003)

**G8 — Ties are 002's ties**, with the imported tolerance, including a tie between a tuple
and the hurdle. (FR-013)

**G9 — Every figure states what it accounts for and what it excludes.** (FR-014, SC-009)

**G10 — Two figures per outcome**: the amount reaching a spendable endpoint, and the implied
rate. (FR-015)

**G11 — One horizon for every tuple in a comparison**, with early termination reported and
**no reinvestment assumed**. (FR-025)

**G12 — Feasibility is 002's, unchanged**, on the way in and the way out. Below-minimum is
infeasible and named; a cap forcing a split reports each tranche and the undeployed
remainder. (FR-016, FR-017, FR-018)

**G13 — Marks survive the join.** An unverified value in any of the four parts marks the
outcome and everything derived from it. (FR-019, SC-007)

**G14 — Currency roles stay separate.** Amounts in different currencies are never silently
combined; a foreign-currency taxable event refuses, naming the missing official-rate
machinery. (FR-024, research.md D10)

## H1 — the constitution's acceptance test

**G15 — A new instrument, route, tax class and jurisdiction added in data only run the full
pipeline and appear in the comparison, with zero source lines changed.** (FR-021, SC-006)

**G16 — If some addition cannot be data-only, the gap is a recorded defect in the
abstraction** — which seam, which declaration kind, what edit it forced — and fixing the
abstraction is in scope. **Papering over it with a special case inside the join is not.**
(FR-023)

That second guarantee is the one that matters. H1's value is that it *can* fail; a special
case added to keep it green converts the only test able to falsify the architecture into one
that cannot.
