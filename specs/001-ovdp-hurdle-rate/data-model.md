# Phase 1 data model: 001-ovdp-hurdle-rate

**Date**: 2026-08-21

Entities, their fields, and the validation rules each one enforces. Core types are plain
frozen dataclasses carrying **only data** — every operation on them is a free function in
the same module (owner decision D-E, functional style). Nothing here imports a validation
framework, and nothing inherits from anything. Field types are given in
Python notation for precision, but the *rules* are the point — they trace back to spec
requirements, which are cited throughout.

---

## Primitives

### `Currency`

A closed enumeration. `UAH` and `USD` exist; only `UAH` is used by this feature.

Enumerated rather than a free string so that a typo is a load-time failure instead of a
silently distinct currency that never matches anything (FR-016).

### `SourceRef`

One cited origin for one or more observed values.

| Field | Type | Rule |
|---|---|---|
| `id` | `str` | Stable, unique within a run. Derived from the declaring file and table so a figure can be traced back to where it was declared. |
| `citation` | `str` | Non-empty. A URL or document reference. |
| `retrieved_on` | `date` | Required. |
| `verified_on` | `date \| None` | `None` means not verified against a primary source. **Permitted and expected**; the key may not be absent from the declaration (FR-014). |

`sources.is_verified(ref)` — a free function, not a property — is
`ref.verified_on is not None`.

### `Provenance`

A frozenset of `SourceRef`, with union as its combining operation — a commutative monoid
with the empty set as identity. This is the mechanism by which FR-015 becomes structural
rather than remembered.

The record holds one field, `sources: frozenset[SourceRef]`. Everything else is a free
function in `core/primitives/provenance.py`:

| Function | Behaviour |
|---|---|
| `merge(a, b)` | Union. Associative and commutative, so evaluation order cannot change the mark. |
| `merge_all(items)` | Fold of `merge` over many, with `EMPTY` as the identity. |
| `is_unverified(p)` | `True` if **any** source has `verified_on is None`. One unverified input taints the result — that is the intended asymmetry. |
| `unverified_sources(p)` | The specific sources responsible, so the mark can name *why*. |

`Provenance.EMPTY` is the identity, used for literals that came from no source (a zero, a
count).

### `Money`

| Field | Type | Rule |
|---|---|---|
| `amount` | `float` | float64, per owner decision D-A. |
| `currency` | `Currency` | Always present. |
| `provenance` | `Provenance` | Excluded from equality — `field(compare=False)`. |

Operations are free functions in `core/primitives/money.py` — `add`, `sub`, `scale`,
`scale_sourced`, `total`, `zero`, `compare` — with **no operator dunders** (D-E).

⚙ `scale_sourced(amount, factor, sources)` was added during Phase 3. There was no way to
apply a **declared** rate and keep the rate's own provenance: `scale` carries only the
amount's, and `Money(` may not be constructed outside this module — so a zero tax charge
could not have cited its exemption, which is precisely the evidence that the exemption was
applied. Its `sources` argument is required and positional, so it cannot be reached and
forgotten, and it only ever *adds* sources. Nothing anywhere removes one, which is what
makes the mark **monotone**: provenance grows as a figure is derived and never shrinks, so
it cannot be laundered out of a chain of arithmetic (FR-015). The union site is therefore
singular and greppable.

- **Currency safety (FR-007, C5).** `add`, `sub` and `compare` raise
  `CurrencyMismatchError` across currencies. This is one of the few places a `raise` is
  correct rather than a tagged union: mixing currencies is a programmer error, not a
  business outcome, so it must stop the run rather than flow into a result.
- **Provenance union (FR-015, E5).** Every combining function returns money whose
  provenance is `merge` of its operands'. `scale(m, k)` by a plain number preserves
  provenance; there is no money × money function, because that product is not money.
- **Equality ignores provenance.** Two amounts equal in value are equal regardless of the
  path that produced them. Without this, the conservation invariants would fail for
  reasons unrelated to conservation.
- **Equality is exact, and is not the financial comparison.** Because money is float,
  tests compare through the tolerance helpers, never `==`.
- Frozen and hashable. No methods.
- **Direct construction is the one hole.** `Money(...)` is callable anywhere, so code could
  build an amount with `Provenance.EMPTY` and launder an unverified input. Guarded by a
  test scanning for `Money(` outside `money.py` and the loader, plus manual review.

### `TOLERANCE` — the single tolerance

Lives in `core/primitives/tolerance.py` and is the **only** tolerance in the project
(FR-002). Exports the constant plus `is_close(a, b)` and `assert_money_close(a, b)`,
which also assert currency equality so a tolerance check cannot accidentally compare
across currencies.

A comparison needing a looser bound states why at the assertion site. A comparison that
defines its own constant is a defect.

### `NominalRate` / `RealRate` / `RealTermsUnavailable`

Three distinct frozen records, so that assigning a nominal figure into a real slot is a
**mypy strict error** rather than a runtime mistake (FR-022, SC-011, decision D4). Not a
hierarchy — three unrelated types, which is exactly why the assignment fails to check.

`RealTermsUnavailable` carries `reason: str` — populated with the fact that inflation is
not modelled in this feature — satisfying FR-017's requirement that a degraded outcome
carry its reason.

### Conventions

Three registries, each a `Mapping[str, Callable]` from a declared name to an implemented
algorithm. No classes, no subclass dispatch.

| Registry | Values this feature implements |
|---|---|
| `DAY_COUNT_FNS` | `act/365`, `act/act`, `30/360` |
| `PERIODICITY_FNS` | `annual`, `semiannual`, `quarterly` |
| `BUSINESS_DAY_FNS` | `following`, `modified_following`, `none` |

An unrecognised name is a load-time failure naming the file and the value (FR-021). The
*choice* is data; the *algorithm* is code — see research.md for why that is not a
Principle II violation.

---

## Declared knowledge

### `TaxClass`

| Field | Type | Rule |
|---|---|---|
| `id` | `str` | Unique across all tax files. A duplicate is a load-time failure. |
| `applies_to` | `frozenset[TaxableEventKind]` | Non-empty. `coupon`, `disposal_gain`, `distribution`, `interest`. |
| `pit_rate` | `float` | Fraction, not percent, once loaded. `0.0` for the exempt class. |
| `levy_rate` | `float` | Fraction. `0.0` for the exempt class. |
| `provenance` | `Provenance` | Required. A rate without a citation cannot be loaded — including a **zero** rate. |

The zero rate needing a citation as much as a non-zero one is deliberate: the exemption
is the single most decision-relevant number in the model (spec §4.5), and an uncited
zero is exactly the kind of value that gets believed without checking.

### `BondTerms`

The contractual terms from which the schedule is computed in closed form.

| Field | Type | Rule |
|---|---|---|
| `face_value` | `Money` | Positive. |
| `coupon_rate` | `float` | Fraction of face per annum. Non-negative; zero is a valid zero-coupon bond. |
| `issue_date` | `date` | |
| `maturity_date` | `date` | **Strictly after** `issue_date` and after any purchase date, else a typed failure (spec edge case). |
| `periodicity` | `str` | Must be a key of `PERIODICITY_FNS`, else a load-time failure (FR-021). |
| `day_count` | `str` | Must be a key of `DAY_COUNT_FNS`. |
| `business_day_rule` | `str` | Must be a key of `BUSINESS_DAY_FNS`. |
| `provenance` | `Provenance` | Required. |

### `InstrumentDeclaration`

| Field | Type | Rule |
|---|---|---|
| `id` | `str` | Unique across all instrument files. |
| `name` | `str` | Non-empty. |
| `instrument_class` | `str` | `fixed_income` for this feature. |
| `currency` | `Currency` | |
| `is_synthetic` | `bool` | **Required, no default.** `True` marks a test fixture whose terms are invented rather than observed. Making it required rather than defaulting to `False` means a real issue cannot be mistaken for a fixture through omission. |
| `terms` | `BondTerms` | |
| `constraints` | `InstrumentConstraints` | |
| `tax_classes` | `dict[TaxableEventKind, str]` | Maps event kind to tax-class id. **Plural by design** — the same instrument is taxed differently on distribution and on disposal (spec §4.1). Every referenced id must resolve, else a load-time failure. |

### `InstrumentConstraints`

| Field | Type | Rule |
|---|---|---|
| `min_ticket` | `Money` | Positive. A purchase below it is infeasible, reported with the shortfall, never rounded (FR-018). |
| `min_unit` | `float` | Smallest buyable increment. Governs the unreinvestable coupon remainder (FR-020). |
| `provenance` | `Provenance` | Required — separate from `terms`, because a minimum ticket and a yield are different facts from different sources. |

---

## Ledger

> **Revised 2026-08-21 after implementation.** The first draft of this section was written
> before any code existed and turned out to be *under-specified* in six places — nothing
> in it was contradicted, but records lacked identities, two `Event` fields were missing,
> and one function signature did not typecheck as written. The shapes below are the ones
> that landed. Each correction is marked ⚙ with what was missing and why it mattered.

### `Event`

One dated, typed thing that moved money or changed a holding. The audit trail behind
every figure (FR-008).

| Field | Type | Rule |
|---|---|---|
| `sequence` | `int` | Monotonic. **Assigned by the producer, not the ledger** — only the schedule applier knows the intended order among same-dated events. The ledger treats it as the sole authority on fold order and *checks* it: `events.in_sequence` refuses a repeat (otherwise the tie is broken by sort stability, i.e. by plumbing) and refuses dates running backwards as the sequence advances. |
| `occurred_on` | `date` | |
| `kind` | `EventKind` | `purchase`, `coupon`, `principal_repayment`, `tax_charge`, `reinvestment`, `cash_deposit`, `fee`, `disposal`. Partitioned by the `frozenset` constants `LOT_OPENING_KINDS`, `LOT_CLOSING_KINDS`, `CASH_ONLY_KINDS`, so the partition is inspectable. |
| `amount` | `Money` | Carries its own provenance. Its **sign** decides cash direction, so a direction can never disagree with an amount. |
| `quantity` | `float \| None` | ⚙ **Was missing.** A disposal must say how many units. `None` for cash-only kinds. |
| `allocated_to` | `int \| None` | ⚙ **Was missing, and its absence would have hollowed out C3.** The sequence number of the event a fee is charged against. C3 asserts `gain = proceeds − consumed basis − allocated fees`, and nothing said how a fee reaches a disposal; inferring it from date adjacency would be a guess. `events.allocated_fees()` indexes fees by target in one pass *before* the fold, so a fee may sit anywhere in the stream. An unallocated fee, or one pointing outside the stream, raises. Without this the third term would have been a hardcoded zero and the invariant would have asserted two thirds of what it claims. |
| `owner_id` | `str` | Present from day one per Principle VII, though there is one owner and no auth. |
| `caused_by` | `CausationRef` | Required, never optional. `CausationKind` has **exactly two** members — `INSTRUMENT_TERM` and `TAX_RULE`. A third kind (`SYSTEM`, `OWNER_ACTION`) was deliberately *not* added: it becomes the bucket for every event whose cause nobody tracked down, and C6 would then pass while meaning nothing. |
| `lot_ref` | `LotRef \| None` | Set where the event touches a specific lot. |

### `Lot` / `Position` / `Consumption` / `Disposal`

⚙ **Identities were missing.** The first draft gave `Lot` only its quantity, dates and
costs — with no `lot_id`, so no lot could be selected for consumption or traced to its
acquisition, and no `instrument_id`. `Position` was described only as "a record".

| Record | Fields |
|---|---|
| `Lot` | `lot_id`, `instrument_id`, `quantity` (strictly positive — a lot may not exist at zero), `acquired_on`, `cost_trade_ccy`, `cost_base_ccy`, `fx_rate_used: float \| None` |
| `Position` | `instrument_id`, `lots: tuple[Lot, ...]`, plus **separately accumulated** `quantity`, `basis_trade_ccy`, `basis_base_ccy` — accumulating them independently of the lot tuple is what makes C2 and C3 non-vacuous |
| `Consumption` | ⚙ **Was missing.** What `consume` returns: the new position, the consumed basis in **both** currencies, and `consumed_from: tuple[tuple[str, float], ...]` naming the lots drawn on |
| `Disposal` | ⚙ **Was missing entirely, and C3 is unassertable without it.** Stores every term of the identity: proceeds, consumed basis and allocated fees in both currencies, the realised gain in both, `consumed_from`, and `caused_by` copied off its event so a realised gain names its cause too |

Functions live in `lots.py` (⚙ the draft said `positions.*`, which contradicted the
plan's own file tree):

- `lots.opening(instrument_id, trade_currency, base_currency)` — an empty position still
  knows what denomination its zero is in.
- `lots.rebuild(events, base_currency, consumption_method)` — ⚙ the draft's
  `rebuild(events)` does not typecheck: neither the base currency nor the consumption
  method is derivable from the events.
- `lots.add_lot(position, lot)`, `lots.consume(position, qty, order)` → `Consumption`,
  `lots.realise(...)` → `Disposal`, `lots.advance(...)`.
- `lots.base_amount_of(...)` — with no FX in this feature and no conversion function
  permitted in `money.py`, this returns the amount unchanged when trade currency **is**
  base currency (recording `fx_rate_used = None`) and raises `CurrencyMismatchError`
  otherwise. Both currency slots are real fields and both C3 assertions are written out,
  so the identity already exists for when dated FX arrives.

**Lot consumption method.** `Mapping[str, ConsumptionOrderFn]` keyed by declared name —
`fifo` and `lifo` — mirroring `primitives/conventions.py` (explicit membership test, no
`dict.get` default, the raise lists the known names). A method is modelled as an
*ordering over lots*, the smallest thing that makes FIFO and LIFO the same code. **There
is no default**, and `engine.opening` validates the name before folding anything, so a
misconfiguration fails at the start of a run rather than at the first disposal.
Average-cost and specific-lot are **absent rather than approximated** — they are E6's
job. A disposal naming a specific `lot_id` is refused loudly rather than having the
naming silently ignored, because ignoring it would tax a different basis than the caller
asked for.

Invariants asserted as properties over generated streams:

- **C2** — `sum(lot.quantity) == position.quantity`; no lot ever negative.
- **C3** — `sum(lot.cost) == position.basis`; the realised-gain identity in **both**
  currencies.

### `CashBalance`

⚙ **Renamed and re-shaped.** The draft described a `CashAccount` as "a record of
per-currency balances" — one record holding many currencies, which puts currency routing
*inside* the account. Split instead: `CashBalance` is **one** currency, and the
per-currency mapping lives on `LedgerState` where the engine does the routing. Renamed
because it is no longer an account-of-accounts.

It carries **three** figures — `inflows`, `outflows`, `balance` — accumulated separately
from the same events, so **C1** compares three independently maintained numbers rather
than a running sum against itself. It is also literally the shape FR-009 is written in.
`accounts.net()` is the identity's left-hand side and deliberately does *not* return the
stored balance.

C1 is asserted **on every date**, not only at the end: an error that cancels out by
maturity is still an error.

**Negative balances are permitted.** An overdraft is a feasibility question about a plan
(Principle VI), not a ledger invariant. Clamping it here would be the silent clamp the
constitution puts in its top severity class.

### `LedgerState`

`engine.opening` / `apply` / `fold` / `history`. Holds the per-currency `Mapping` of
balances, positions, disposals, and `applied` events. A value, rebuilt per event — never
a mutable owner of dicts.

### Canonical form

Free functions in `canonical.py` — `of_event`, `of_lot`, `of_position`, `of_account`,
`of_disposal`, `of_result` — returning nested tuples of primitives, amounts as
`float.hex()`. No serialisation, no hashing; those live in `data`.

⚙ `of_result` is typed on `LedgerState`, because `HurdleRate` does not exist until T030.
Phase 3 needs either a second function or to compose this one — it cannot widen this
signature without a union.

**Provenance is deliberately excluded.** It identifies *sources*, so filling in a
`verified_on` later would change the digest even though no computed amount moved, and C4
would fail on a documentation update. The unverified mark is asserted separately by E5.

## Per-run inputs

⚙ **All three were referenced in the interface contract and defined nowhere.** Kept
minimal on purpose: this feature needs a purchase and a horizon, and a field accepted but
ignored is worse than a field that is missing.

| Record | Fields | Rule |
|---|---|---|
| `Holding` | `owner_id`, `instrument_id`, `quantity`, `purchased_on`, `cost` | It **names** the instrument rather than embedding the declaration. Principle VII separates per-owner from curated data, and a holding carrying its own declaration would put curated data inside per-user data. |
| `DateRange` | `start`, `end`, inclusive | Must reach the **adjusted** final payment. A horizon too short returns `InconsistentTerms` rather than a truncated schedule — a truncated schedule's yield is *wrong*, not partial — and never an implicit liquidation. |
| `Assumptions` | `consumption_method`, `coupon_policy` | ⚙ Two fields as of Phase 5. `coupon_policy` was deliberately absent until reinvestment earned it — an accepted-and-ignored field is worse than a missing one — and `fixed_income.events` now reads it. |

## Results

### `CashFlowSchedule`

The dated sequence a holding will pay: for each row, the date, the gross amount, the tax
charged, the net amount, and the convention that placed the date (FR-021). Derived from
ledger events, never computed alongside them.

### `HurdleRate`

| Field | Type | Rule |
|---|---|---|
| `nominal_ytm` | `NominalRate` | Contractual yield to maturity. |
| `nominal_cash_flow_return` | `NominalRate` | Cash-flow-weighted. Kept separate from the yield and separately labelled; neither substitutes for the other (FR-005). |
| `real` | `RealRate \| RealTermsUnavailable` | Always `RealTermsUnavailable` in this feature, carrying its reason. Present and explicitly empty — never absent (SC-011). |
| `total_tax` | `Money` | Exactly zero for the exempt class (SC-002) — and zero because zeroes were recorded and summed, not because nothing was. |
| `accounts_for` | `frozenset[str]` | ⚙ **Added after implementation.** What the figure *is* net of, in particular that it is after tax. US1's second acceptance scenario requires the figure to state this and none of the six prescribed fields did. Named beside `excludes` so a later feature cannot quietly move a term from one set to the other. |
| `excludes` | `frozenset[str]` | What this figure does **not** account for: route costs, exit costs, inflation. Principle VI forbids presenting a per-instrument access cost, so the figure states its own boundaries rather than leaving a later reader to assume it is comparison-ready. |
| `provenance` | `Provenance` | Unioned from everything upstream. `is_unverified` is `True` while the yield is unverified. |

### Failure results — a tagged union

Every degraded outcome is one of these, never an exception swallowed and never a zero
(FR-017). They are unrelated frozen records combined with `|`, dispatched by `match` with a
`case _:` arm mypy proves unreachable — so adding a variant produces a type error at every
site that must handle it, rather than silently inheriting a default:

| Type | Carries |
|---|---|
| `InfeasiblePurchase` | The constraint violated, the required value, the actual value, the shortfall |
| `InconsistentTerms` | Which two terms conflict and how |
| `UnresolvedTaxClass` | The missing class id and the instrument that referenced it |
| `RealTermsUnavailable` | Why the real figure is absent |
| `DeclarationError` | ⚙ **Not a union member — an exception.** File path, field path, problem and remedy, carried as attributes so the API layer can render them without parsing a string. A broken file is not an outcome about the money: there is no partial answer and every caller's only response is to stop. Principle II says data files fail loudly *at load time*. |

**Two exceptions exist, not one.** `CurrencyMismatchError` and — added during
implementation — `LedgerInvariantError`. Neither is a tagged-union member, because
neither is an outcome the owner can act on: both are statements about the *code* being
wrong, not about the money. Every ledger refusal raises the latter. A domain outcome the
owner could respond to is always a union member instead.
