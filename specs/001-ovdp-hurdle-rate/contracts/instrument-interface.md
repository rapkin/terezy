# Contract: the `Instrument` plugin interface

**Date**: 2026-08-21

One of the four plugin interfaces permitted by constitution Principle II. Adding a fifth
requires a constitution amendment; this feature implements this one and `TaxRule`.

Per owner decision D-E the interface is a **set of function signatures**, not a class.
There is no base class to inherit and no protocol to implement — an instrument is a record
of functions, and the registry is a mapping.

---

## The signatures

> **Revised 2026-08-21 after implementation.** Two things in the first draft did not
> typecheck. Both are marked ⚙ below.

```python
# --- the functions an instrument must supply ---
# ⚙ All three take the declaration first. The draft's
#   EventsFn(Holding, DateRange, Assumptions) cannot work: a schedule is not
#   computable from a holding that knows only an instrument id. And the draft wrote
#   tax_classes/constraints as zero-argument, which a module of free functions has
#   nothing to close over -- that shape only makes sense for a bound method.

EventsFn = Callable[
    [InstrumentDeclaration, Holding, DateRange, Assumptions],
    Sequence[Event] | InstrumentFailure,
]
TaxClassesFn = Callable[[InstrumentDeclaration], Mapping[TaxableEventKind, str]]
ConstraintsFn = Callable[[InstrumentDeclaration], InstrumentConstraints]


@dataclass(frozen=True)
class InstrumentOps:
    """The functions that define one instrument kind. Data, not an object."""

    events: EventsFn
    tax_classes: TaxClassesFn
    constraints: ConstraintsFn


# --- dispatch is a mapping, not subclass resolution ---
# ⚙ This lives in a THIRD module, instruments/registry.py, not in interface.py.
#   interface.py importing fixed_income to build the mapping, while fixed_income
#   imports interface.py for the types, is a circular import. Splitting it keeps
#   OPS beside its implementation. Semantics unchanged: closed mapping, no subclass
#   dispatch, an unknown name raises and names the known ones.

REGISTRY: Final[Mapping[str, InstrumentOps]] = {
    "fixed_income": fixed_income.OPS,
}
```

An unknown `instrument_class` is a load-time failure naming the file and the value — the
mapping is closed, and a missing key is never a silent fallback.

`InstrumentOps` is a frozen record whose fields happen to be functions. It carries no
behaviour of its own, and nothing inherits from it.

## Obligations on every implementation

**Purity.** `events` is a pure function of its arguments. No I/O, no clock, no
randomness. Called twice with equal arguments it returns equal results — this is what
makes C4 achievable at all.

**Provenance.** Every `Money` in every returned event carries the provenance of the terms
that produced it, built through `money.*` functions rather than constructed fresh. An
implementation that builds money with `Provenance.EMPTY` from declared terms is defective:
it launders an unverified input into an apparently verified figure, which FR-015 calls
top-severity.

**Explicit failure.** An instrument that cannot produce events returns an
`InstrumentFailure` — a tagged union member, not an exception (D-E). It does not raise,
does not return an empty sequence, and does not clamp anything to zero (FR-017). An empty
sequence means "legitimately no events in this horizon" and nothing else.

**Instrument identity is data, not a dispatch key.** Behaviour comes from declared terms.
A conditional on `id == "ovdp_synthetic_a"` is a Principle II violation. Dispatch on
`instrument_class` through the registry is the only branching permitted, and it selects an
algorithm, not an issue.

**`income_currency` may differ from `currency`.** Not exercised in this feature — both are
UAH — but the field exists because the Inzhur REIT case (a UAH-denominated unit paying
USD-pegged rent) is the reason it must not be collapsed into one field.

**`tax_classes` is plural.** A mapping from event kind to tax-class id, because the same
instrument is taxed one way on distribution and another on disposal. Returning a single
class for all kinds is the modelling error this signature exists to prevent.

## What implementations must NOT do

- **Apply tax.** Instruments emit gross events. Tax is applied downstream by a
  `ChargeFn`. An instrument that nets tax into its own amounts makes the waterfall in
  spec §5.3 impossible to build.
- **Apply route or access costs.** Out of scope here, and per Principle VI an access cost
  is never a property of the instrument alone — it belongs to
  `(instrument × income stream × route)`.
- **Hold mutable state between calls.** There is no instance to hold it in, which is
  rather the point.

## `fixed_income` — this feature's implementation

A module of free functions exporting `OPS: InstrumentOps`. Computes the coupon and
principal schedule in closed form from `BondTerms`, then returns it as events.

| Aspect | Behaviour |
|---|---|
| Coupon amount | `face_value × coupon_rate × period_fraction`, where the fraction comes from the declared `day_count` |
| Coupon dates | Placed by declared `periodicity` from `issue_date`, then adjusted by the declared `business_day_rule` |
| Principal | One `principal_repayment` event on the adjusted `maturity_date` |
| Reinvestment | Per declared policy: `hold_cash` emits nothing further; `reinvest` emits a `reinvestment` event buying whole units at the yield available on the coupon date, and reports the unbought remainder as retained cash (FR-020) |
| Zero-coupon | `coupon_rate == 0.0` is valid: principal only, no coupon events |
| Maturity ≤ issue | Returns `InconsistentTerms` |
| Purchase below `min_ticket` | Returns `InfeasiblePurchase` with the shortfall (FR-018) |

Conventions are resolved through three mappings — `DAY_COUNT_FNS`, `PERIODICITY_FNS`,
`BUSINESS_DAY_FNS` — each `str -> Callable`. Adding a convention adds an entry and a
function; adding an *issue* that uses one adds only a data file (SC-012).

**Not implemented here**, and deliberately absent rather than stubbed: secondary-market
sale before maturity, a thin-market haircut, restructuring, and pricing future purchases
off a full yield curve rather than a single declared yield. Each is named in the spec as a
later feature. A stub would invite a caller to depend on it.

## Verified by

| Test | Asserts |
|---|---|
| `tests/worked_examples/test_ovdp_schedule.py` | D1 — schedule matches hand-computed arithmetic; total tax exactly zero |
| `tests/worked_examples/test_coupon_reinvestment.py` | D2 — two-period reinvestment matches by hand; remainder retained as cash |
| `tests/contract/test_data_only_extensibility.py` | SC-003, SC-012 — a second issue with different conventions works with zero code changes |
| `tests/contract/test_provenance_propagation.py` | Every emitted amount carries the terms' provenance |
| `tests/invariants/test_determinism.py` | C4 — `events` called twice yields an identical digest |
