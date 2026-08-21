# Phase 1 data model: 002-ramp-cost

**Date**: 2026-08-22

Entities, fields, and the rules each enforces. Everything is a frozen dataclass carrying
only data; every operation is a free function in the same module (D-E). Field types are
given in Python notation for precision, but the rules are the point.

Feature 001's records are reused as they are — `Money`, `Provenance`, `Currency`,
`TOLERANCE`, `Event`, `LedgerState`. Nothing here restates them.

---

## Observation and staleness

### `ObservationKind`

Declared in `data/observation_kinds.toml`. One kind per sort of thing the owner observes.

| Field | Type | Rule |
|---|---|---|
| `id` | `str` | e.g. `p2p_premium`, `bank_fee_schedule`, `regulatory_limit`, `bond_terms` |
| `staleness_days` | `int` | Positive. **No default.** A kind without one fails at load (FR-028), and so does a table naming a kind that does not exist. |
| `note` | `str` | Why this kind ages at this rate — a P2P premium in days, a published schedule in years. Required, because a threshold without a reason is a number nobody can argue with. |

### Staleness evaluation

Free functions in `core/primitives/staleness.py`. There is **no clock**:

```
is_stale(retrieved_on, kind, *, as_of) -> bool
staleness_of(provenance, kinds, *, as_of) -> StalenessVerdict
```

`as_of` is an input to the run, recorded in the manifest. The same inputs therefore produce
the same staleness verdicts forever — which would be false if "now" were read from the
machine, and would break C4 for a convenience.

`StalenessVerdict` carries which sources are stale and by how many days, so the mark can
name *why*, exactly as the unverified mark does.

---

## Declared: the route graph

### `Venue`

| Field | Type | Rule |
|---|---|---|
| `id` | `str` | Unique. `monobank_uah`, `coinbase`, `binance`, `ibkr_usd`, `inzhur` |
| `name` | `str` | Non-empty |
| `currencies` | `frozenset[Currency]` | Non-empty. A leg moving a currency the venue cannot hold is a load-time failure. |

### `FxChannel`

The named two-sided rate source. **A single mid-rate is never used for a transaction**
(FR-010).

| Field | Type | Rule |
|---|---|---|
| `id` | `str` | `nbu_official`, `interbank`, `bank_non_cash`, `cash_desk`, `card`, `p2p` |
| `pair` | `tuple[Currency, Currency]` | The ordered pair this quote is for |
| `reference_rate` | `float` | The mid or official reference the quote is expressed against |
| `buy_side`, `sell_side` | `ChannelSide` | Two sides, both required. Not derived from one another. |
| `observed_on` | `date` | |
| `kind` | `str` | An `ObservationKind` id |
| `provenance` | `Provenance` | Required |

### `ChannelSide`

A side is declared **either** as a markup in basis points **or** as a premium in base
currency per unit of foreign currency — because the second is how the owner actually
observes P2P ("+3 UAH per dollar"), and converting it to a percentage by hand before
entering it would be a place to make an arithmetic error in a data file.

| Field | Type | Rule |
|---|---|---|
| `markup_bps` | `float \| None` | Exactly one of `markup_bps` / `premium_per_unit` is set. Both set, or neither, is a load-time failure — a "helpful" precedence rule here would silently ignore one of the two numbers the owner wrote. |
| `premium_per_unit` | `Money \| None` | May be **zero** (the channel is at reference) and may be **negative** (P2P sometimes trades below reference). A *missing* premium is refused; a zero one is not. |

`effective_rate(side, reference)` is a free function. FR-004: a premium of `p` against
reference `r` costs `p / r`, which reproduces §4.3.1 exactly.

### `Leg`

| Field | Type | Rule |
|---|---|---|
| `index` | `int` | Position in the chain, from zero |
| `kind` | `str` | A key of `LEG_COST_FNS`: `transfer`, `fx`, `trade`, `withdrawal`. An unknown kind fails at load naming the value and the known ones. |
| `from_venue`, `to_venue` | `str` | Venue ids |
| `from_ccy`, `to_ccy` | `Currency` | Equal for every kind except `fx` |
| `channel` | `str \| None` | Required when `kind == "fx"`, forbidden otherwise. The channel applied appears in the attribution (FR-011). |
| `fee_pct` | `float` | Non-negative fraction |
| `fee_fixed` | `Money` | Non-negative |
| `minimum`, `maximum` | `Money \| None` | |
| `monthly_cap` | `Money \| None` | |
| `latency_days` | `int` | Non-negative |
| `available_from`, `available_until` | `date \| None` | **A fact** about the leg, with a source — never an assumption. See `Regime`. |
| `disruption_probability` | `float` | In `[0, 1]`. Reported, **never folded into a cost** (FR-026): the chance a route stops working is a different claim from what it charges. |
| `kind_of_observation` | `str` | An `ObservationKind` id |
| `provenance` | `Provenance` | Required |

### `Route`

| Field | Type | Rule |
|---|---|---|
| `id` | `str` | Unique |
| `provider` | `str` | The named provider — `TransferGo`, `Monobank`, `Binance P2P` |
| `origin`, `destination` | `str` | Venue ids |
| `direction` | `"inbound" \| "exit"` | Declared, not inferred. FR-027: exit routes are separate, not reversals. |
| `partner_route` | `str \| None` | The exit route paired with this inbound one. `None` means **no round-trip figure exists** for this route (FR-030). |
| `status` | `"open" \| "constrained" \| "closed"` | |
| `legs` | `tuple[Leg, ...]` | Non-empty. A route with no legs is refused, never costed as free. |

**Registry identity is `(provider × currency path × venue)`, not provider** (FR-023),
because conversion count is usually the largest difference between two ways of doing the
same thing. A duplicate triple is a load-time failure.

**Chaining, validated at load** (research.md D6): leg *n*'s `to_venue`/`to_ccy` equals leg
*n+1*'s `from_venue`/`from_ccy`; the first leg starts at `origin`; the last ends at
`destination`; every currency is one the venue can hold. Failure names file and leg index.

### `Regime`

Scenario data, not route data — the division is about epistemic status (research.md D8).

| Field | Type | Rule |
|---|---|---|
| `id` | `str` | `wartime`, `normalized` |
| `route_ids` | `frozenset[str]` | Which routes exist under this regime |

### `RegimeTransition`

| Field | Type | Rule |
|---|---|---|
| `on_date` | `date` | |
| `before`, `after` | `str` | Regime ids |
| `is_assumption` | `Literal[True]` | **Structurally always true.** FR-020 requires a transition date be presented as a stated assumption; a `bool` could be set to `False`, so the type admits only one value. It exists to make the claim unmissable in the output, not to be branched on. |
| `rationale` | `str` | Required. The owner's stated belief in words. |

---

## Per-owner: streams

`data/streams/` is separate from `data/routes/` because a stream is per-owner data and a
route is curated. Principle VII's boundary, made structural rather than a matter of reading
field names.

### `IncomeStream`

| Field | Type | Rule |
|---|---|---|
| `id` | `str` | `salary_uah`, `contract_usd` |
| `owner_id` | `str` | Present from day one |
| `currency` | `Currency` | |
| `amount` | `Money` | Positive |
| `cadence` | `str` | `monthly`, `biweekly`, `semimonthly` |
| `arrives_at` | `str` | Venue id. A route whose `origin` differs from this is a mismatch, reported (spec edge case). |
| `indexation` | `Indexation` | Policy plus an optional rate |
| `income_tax_rate` | `float \| None` | Optional. When set, deployable capacity is net of it (FR-007). `None` means the owner has not stated one — **not** zero. |

`deployable(stream)` is a free function returning the amount net of any declared income
tax, so "how much can I actually invest" is never overstated.

---

## The key that cannot be partial

### `FundingPath`

| Field | Type | Rule |
|---|---|---|
| `destination_id` | `str` | Venue id |
| `stream_id` | `str` | |
| `route_id` | `str` | |

**All three required, no defaults, no optional variant.** This is the mechanism for FR-008:
a per-destination cost has no type to live in, so it is not a discouraged call but an
expression that does not typecheck (research.md D2).

**It deliberately does not carry the amount.** A path is *which way*; an amount is *how
much*. Folding the amount in would make a cost's key include the cost's input, so two
amounts through one route would look like two paths — and the capacity accumulator keyed by
route would stop working.

---

## Results

### `CostComponent`

A **closed enumeration**, not a free-form mapping: `conversion_spread`,
`percentage_fee`, `fixed_fee`. A `dict[str, Money]` would let a leg invent a component name
and break the components-sum-to-total invariant silently.

### `OneWayCost` / `RoundTripCost`

Two **unrelated** frozen records, so assigning one into the other's slot is a mypy strict
error (research.md D4).

| Field | Type | Rule |
|---|---|---|
| `sent` | `Money` | What departed |
| `arrived` | `Money` | What reached the far end |
| `components` | `Mapping[CostComponent, Money]` | Every component present, zero where it does not apply. Their sum equals `sent − arrived` in base terms — the invariant behind FR-003. |
| `fraction` | `float` | Cost as a fraction of `sent`. **May exceed 1.0** on a small amount with a fixed fee; reported honestly rather than capped, since a cap here is B13's silent clamp in a new hat. |
| `channels_applied` | `tuple[str, ...]` | Which channel each `fx` leg used (FR-011) |
| `provenance` | `Provenance` | Merged from every declared value that fed the figure |
| `staleness` | `StalenessVerdict` | |

### `ExitCostUnknown`

| Field | Type | Rule |
|---|---|---|
| `reason` | `str` | Carries its reason (FR-017) |
| `missing_partner_for` | `str` | The route whose `partner_route` is `None` |

### `RampCost`

| Field | Type | Rule |
|---|---|---|
| `path` | `FundingPath` | The triple. Never a bare destination. |
| `one_way` | `OneWayCost` | |
| `round_trip` | `RoundTripCost \| ExitCostUnknown` | Present and typed either way; never absent, never a promoted one-way figure (FR-030) |
| `latency_days` | `int` | Sum over legs |
| `ceiling` | `Money \| None` | Effective monthly deployment ceiling |
| `status` | `str` | |
| `disruption_probability` | `float` | Reported beside the cost, never inside it (FR-026) |

### `RouteUnusable`

Returned instead of a `RampCost` when a route cannot carry the amount on the date.

| Field | Rule |
|---|---|
| `path`, `binding_constraint`, `required`, `actual`, `shortfall` | Names what bound and by how much (FR-014). A route excluded from a ranking is excluded *with this recorded*, never silently. |

### `Ranking`

| Field | Type | Rule |
|---|---|---|
| `costed` | `tuple[RampCost, ...]` | Every candidate, each costed by the single costing function |
| `recommended` | `int` | An **index** into `costed`, not a copy (research.md D3). `recommended_cost(r)` returns `r.costed[r.recommended]`, so the winner *is* one of the alternatives and SC-016 can assert identity rather than equality. |
| `excluded` | `tuple[RouteUnusable, ...]` | With reasons |
| `ties` | `tuple[tuple[int, ...], ...]` | Indices that scored equal within the project tolerance. A tie is reported as a tie (FR-018), never broken arbitrarily. |
| `not_comparable` | `tuple[RampCost, ...]` | Those whose `round_trip` is `ExitCostUnknown` — costed, reported, and kept out of the ranking (FR-030) |

### `CapacityUsed`

The monthly cap accumulator, folded into `LedgerState` beside the cash balances
(research.md D7). Keyed by `(route_id, year, month)` taken from each event's `occurred_on`
— data, never a clock. `remaining(cap, used)` is what feasibility consults, so FR-015's
"capacity already consumed in the same month" is not a special case.

### `FallbackApplied`

| Field | Rule |
|---|---|
| `occurred_on`, `amount`, `policy`, `reason` | Every occurrence is a record, and **every one appears in the output** (FR-013). A silently executed infeasible plan is a top-severity defect. |
