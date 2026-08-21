# Contract: the `Instrument` plugin interface

**Date**: 2026-08-21

One of the four plugin interfaces permitted by constitution Principle II. Adding a fifth
requires a constitution amendment; this feature implements this one and `TaxRule`.

The shape follows what the product spec already fixed in §4.1, so that market instruments
can arrive later without the interface being redesigned.

---

## The protocol

```python
class Instrument(Protocol):
    id: str
    name: str
    instrument_class: str
    currency: Currency
    income_currency: Currency

    def events(
        self,
        holding: Holding,
        horizon: DateRange,
        assumptions: Assumptions,
    ) -> Sequence[Event] | InstrumentFailure: ...

    def tax_classes(self) -> Mapping[TaxableEventKind, str]: ...

    def constraints(self) -> InstrumentConstraints: ...
```

## Obligations on every implementation

**Purity.** `events()` is a pure function of its arguments. No I/O, no clock, no
randomness. Called twice with equal arguments it returns equal results — this is what
makes C4 achievable at all.

**Provenance.** Every `Money` in every returned event carries the provenance of the terms
that produced it. An implementation that constructs money with `Provenance.EMPTY` from
declared terms is defective: it launders an unverified input into an apparently verified
figure, which FR-015 calls top-severity.

**Explicit failure.** An instrument that cannot produce events returns an
`InstrumentFailure` carrying the reason. It does not raise, does not return an empty
sequence, and does not clamp anything to zero (FR-017). An empty sequence means
"legitimately no events in this horizon" and nothing else.

**`income_currency` may differ from `currency`.** Not exercised in this feature — both are
UAH — but the field exists because the Inzhur REIT case (a UAH-denominated unit paying
USD-pegged rent) is the reason it must not be collapsed into one field.

**`tax_classes()` is plural.** A mapping from event kind to tax-class id, because the same
instrument is taxed one way on distribution and another on disposal. Returning a single
class for all kinds is the modelling error this signature exists to prevent.

## What implementations must NOT do

- **Apply tax.** Instruments emit gross events. Tax is the `TaxRule`'s job, applied
  downstream. An instrument that nets tax into its own amounts makes the waterfall in
  spec §5.3 impossible to build.
- **Apply route or access costs.** Out of scope here, and per Principle VI an access cost
  is never a property of the instrument alone — it belongs to
  `(instrument × income stream × route)`.
- **Branch on instrument identity.** Behaviour comes from declared terms. A conditional on
  `id == "ovdp_synthetic_a"` is a Principle II violation.

## `FixedIncomeInstrument` — this feature's implementation

Computes the coupon and principal schedule in closed form from `BondTerms`, then returns
it as events.

| Aspect | Behaviour |
|---|---|
| Coupon amount | `face_value × coupon_rate × period_fraction`, where the fraction comes from the declared `day_count` |
| Coupon dates | Placed by declared `periodicity` from `issue_date`, then adjusted by the declared `business_day_rule` |
| Principal | One `principal_repayment` event on the adjusted `maturity_date` |
| Reinvestment | Per declared policy: `hold_cash` emits nothing further; `reinvest` emits a `reinvestment` event buying whole units at the yield available on the coupon date, and reports the unbought remainder as retained cash (FR-020) |
| Zero-coupon | `coupon_rate == 0.0` is valid: principal only, no coupon events |
| Maturity ≤ issue | Returns `InconsistentTerms`, not an empty schedule |
| Purchase below `min_ticket` | Returns `InfeasiblePurchase` with the shortfall (FR-018) |

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
| `tests/invariants/test_determinism.py` | C4 — `events()` called twice yields an identical digest |
