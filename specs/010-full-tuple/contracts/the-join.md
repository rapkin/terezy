# Contract: the join and the comparison

**Feature**: `010-full-tuple` | **Modules**: `terezy.core.decision.tuple_outcome`, `terezy.core.decision.compare`

**Reconciled with the code**: 2026-08-24. The signatures below were written before the code
and showed a `declarations` argument the implementation never took; they are now what is
actually exported.

## Signatures

```python
def evaluate(
    tuple_: Tuple,
    *,
    amount: Money,
    horizon: DateRange,
    as_of: date,
    continuation: ContinuationAssumption,
    registries: Registries,
) -> TupleOutcome | TupleRefused: ...


def compare(
    tuples: Sequence[Tuple],
    *,
    benchmark: Tuple,
    amount: Money,
    horizon: DateRange,
    as_of: date,
    continuation: ContinuationAssumption,
    registries: Registries,
) -> Comparison | BenchmarkUnavailable: ...
```

Pure. No clock: `horizon.start` is when the money leaves, `as_of` is when the question is
asked, and neither is read from the machine. `continuation` has no default anywhere in the
stack, because FR-025 forbids defaulting what an instrument terminating early does with its
proceeds. The horizon is stated once and applies to every tuple.

`Registries` is every declared set the join reads, passed rather than loaded, so the core is
testable with no file on disk near the arithmetic: instruments, funds, tax classes, access,
routes, channels, streams, observation kinds, spendable endpoints, and the base currency.

The way out is costed by `terezy.core.routes.cost.cost_exit`, added by this feature beside
`cost_one`:

```python
def cost_exit(
    chain: ExitChain,
    amount: Money,
    *,
    stream_id: str,
    departing_from: Junction,
    routes,
    channels,
    kinds,
    on_date: date,
    as_of: date,
    spendable,
) -> WayOutCost | RouteUnusable: ...
```

## Guarantees

**G1 — The join invents nothing.** Every term comes from the call that owns it; the join sums
and chains. (FR-002)

**G2 — All three seams are anchored, and a mismatch names both sides.** The tuple's stream
must be the stream its way in is costed from; the route in must end where and in the currency
the purchase begins; the instrument's exit must produce a balance where the route out starts.
(FR-004, FR-010)

**G3 — Each part's contribution is separately reported**, so a reader sees which term
dominates and can go check it. (FR-005)

**G4 — A missing declaration in any of the four parts is a typed refusal naming it.** (FR-006)

**G5 — No declared exit route, or no declared exit terms, inherits 002 FR-030's refusal** —
a one-way figure is never promoted. (FR-007, FR-008)

**G6 — Keyed per `(instrument × stream × route in × exit terms × route out)`.** The same
instrument from two streams is two outcomes. (FR-010, SC-004)

**G7 — The benchmark is a tuple through the same code path**, asserted by construction — an
index into the ranked sequence, with no field for a second figure — and by the falsifying
experiment: break its declarations and the whole comparison refuses. (FR-012, SC-002, SC-003)

**G8 — Ties are 002's ties**, with the imported tolerance, including a tie between a tuple
and the hurdle. (FR-013)

**G9 — Every figure states what it accounts for and what it excludes**, and at least one of
those statements is checked against the behaviour it describes rather than against itself.
(FR-014, SC-009)

**G10 — Two figures per outcome**: the amount reaching a spendable endpoint, and the implied
rate — measured against the money **actually invested**, which is the outlay less any
remainder the purchase could not deploy. (FR-015, FR-003)

**G11 — One horizon for every tuple in a comparison**, with early termination reported and
**no reinvestment assumed**. (FR-025)

**G12 — Feasibility is 002's, unchanged**, on the way in and the way out. Below-minimum is
infeasible and named; a remainder is reported with its amount and its venue. A cap-exceeding
amount refuses through 002's feasibility, and partial deployment is deferred (FR-018, owner
decision 2026-08-22). (FR-016, FR-017, FR-018)

**G13 — Marks survive the join.** An unverified value in any part marks the outcome, and
staleness is merged from every part that ages one — the way in, each way-out charge, and the
venue quote this feature's own declaration kind added. (FR-019, SC-007)

**G14 — Currency roles stay separate.** Amounts in different currencies are never silently
combined; a foreign-currency taxable event refuses, naming the missing official-rate
machinery, and a rate over more than one currency is a typed absence rather than a figure.
(FR-024, research.md D10)

## H1 — the constitution's acceptance test

**G15 — A new instrument, route, tax class and jurisdiction added in data only run the full
pipeline and appear in the comparison, with zero source lines changed.** (FR-021, SC-006)

**G16 — If some addition cannot be data-only, the gap is a recorded defect in the
abstraction** — which seam, which declaration kind, what edit it forced — and fixing the
abstraction is in scope. **Papering over it with a special case inside the join is not.**
(FR-023)

That second guarantee is the one that matters, and it has been exercised twice. The access
declaration kind exists because H1 found that nothing declared *where* an instrument is
bought; the jurisdiction's own fields are validated and discarded, and that one is **recorded
and open** (2026-08-24) rather than worked around — see `tests/contract/test_h1_data_only.py`.
