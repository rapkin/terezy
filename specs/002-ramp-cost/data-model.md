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
is_stale(source, kind, *, as_of) -> bool          # ages from the LATER of the two dates
staleness_of(provenance, kind, *, as_of) -> StalenessVerdict
```

⚙ **Which date ages** was left ambiguous by FR-025's "verification **or** retrieval date".
Resolved: from `verified_on` where one is set, from `retrieved_on` otherwise — the later of
the two, since a verification cannot precede what it verifies. Verifying against a primary
source is the strongest refresh of confidence there is, and a warning that fired on the one
value the owner had actually checked is one that gets ignored. An unverified value therefore
ages from retrieval, the common case today and the stricter one (research.md D12).

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

Three free functions, and the distinction between the last two is the correction FR-004
went through:

- `effective_rate(side, reference, *, role)` — the rate actually transacted at, `r + p` when
  buying and `r - p` when selling. **The conversion happens at this rate**, so the arriving
  amount is the one the venue would really hand over.
- `loss_fraction(side, reference, *, role)` — **the cost**: the fraction of money actually
  lost, `p / (r + p)` buying and `p / r` selling.
- `spread_over_reference(side, reference, *, role)` — `p / r`, the spread over the reference
  *rate*. This is §4.3.1's figure and stays reproducible, reported **beside** the cost and
  never instead of it.

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
| `capacity_pool` | `str \| None` | ⚙ **Added after review.** The shared rail whose limit this leg consumes. Two legs on different routes both using the owner's Monobank card name the **same** pool, and the accumulator keys on the pool — not on the route, which was the first design and gave each route its own full limit. They must declare the **same** cap; a mismatch is a load-time failure (research.md D10). |
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
| `status` | `"open" \| "constrained" \| "closed"` | ⚙ **`constrained` needed defining.** `open` — usable as declared. `constrained` — usable, but a declared cap or window binds in normal use, so it is **ranked and flagged** rather than excluded. `closed` — not usable on the date, excluded with its status recorded (FR-014). The middle value exists because §4.3 uses it for the IBKR route: reachable, but not freely. |
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

⚙ **One transition, and that is a stated limit rather than an oversight.** FR-019 is worded
generally ("a scenario MAY declare a transition date and a route set per regime"), and this
record expresses exactly one. A chain of regimes is representable as a sequence of these, and
the selection function takes the whole sequence — but this feature declares and tests one,
because a second transition needs a second assumption the owner has not stated. The type does
not forbid more, and ⚙ the **tests** now exercise a three-segment chain: a validation loop
never run to completion on a valid chain is untested validation. What still declares one is
`data/scenarios/` (T056).

| Field | Type | Rule |
|---|---|---|
| `on_date` | `date` | |
| `before`, `after` | `str` | Regime ids |
| `is_assumption` | `Literal[True]` | **Structurally always true.** FR-020 requires a transition date be presented as a stated assumption; a `bool` could be set to `False`, so the type admits only one value. It exists to make the claim unmissable in the output, not to be branched on. |
| `rationale` | `str` | Required. The owner's stated belief in words. |

⚙ **Neither `Regime` nor `RegimeTransition` carries provenance, and the absence is
load-bearing rather than an omission.** A belief has nothing to cite: `is_assumption` is what
it carries where an observation carries a `source` and a `verified_on`. Giving a regime a
provenance field would invite a citation for a guess, which is the one thing Principle I
forbids most firmly. Asserted in `tests/unit/test_transition_is_an_assumption.py`.

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
| ~~`currency`~~ | — | ⚙ **Removed.** It duplicated `amount.currency`, and two fields stating one fact can disagree: a record with `currency=UAH` and an amount in USD typechecks and is nonsense. The mitigation on offer — "the loader builds both from one declared value" — puts the guarantee in a layer that cannot help anything constructing a stream in code. `amount.currency` is the single place. |
| `amount` | `Money` | ⚙ **Non-negative**, not positive: the contract prescribes `amount = 0.0` as the honest placeholder while §11 item 3's real figures are unstated, and a zero produces a zero rather than a made-up number. |
| `cadence` | `str` | `monthly`, `biweekly`, `semimonthly` |
| `arrives_at` | `str` | Venue id. A route whose `origin` differs from this is a mismatch, reported (spec edge case). |
| `indexation` | `Indexation` | Policy plus an optional rate. ⚙ The policy set is closed at `none \| cpi \| fixed_rate` — `cpi` from §4.2, `fixed_rate` from the brief's "salary growth", and `none` because the field is required and the absence of indexation has to be sayable. **Nothing in this feature applies an indexation**, so no figure rests on the choice; it is written down here so a document owns the set before a figure does. A `fixed_rate` with no rate is a declaration that means nothing and is the loader's to refuse (T038/T040). |
| `income_tax_rate` | `float \| None` | Optional. When set, deployable capacity is net of it (FR-007). `None` means the owner has not stated one — **not** zero. |

`deployable(stream)` returns **`DeployableCapacity | IncomeTaxRateUndeclared`** — ⚙ a tagged
union, because no `Money` honestly represents "no rate declared". `IncomeTaxRateUndeclared`
carries the reason, the stream id and the gross, and has **no net field at all**, so the
figure is unreadable rather than merely discouraged. A *declared* zero returns a
`DeployableCapacity` whose net is bit-identically the gross, because the owner said so.

`DeployableCapacity` reports `gross`, `withheld`, `net` and `cadence` — all three terms of
`net = gross − withheld` so it can be checked by reading, and the cadence because a monthly
figure read as annual is wrong by twelve and nothing else in the record says which.

Same precedent as `ExitCostUnknown` (D4) and `RealTermsUnavailable` in feature 001: when
there is no answer, the type says so rather than a value standing in for it.

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
| `components` | `Mapping[CostComponent, Money]` | Every component present, zero where it does not apply. **All in the sending currency**, which is what makes them summable at all. ⚙ This row previously said their sum equals `sent − arrived` "in base terms" — which does not typecheck on an FX route, where `sent` is UAH and `arrived` is USD and `money.sub` refuses the mismatch by design (C5). Restating `arrived` would need a rate, and naming which side at which reference is exactly what FR-010 forbids leaving implicit. The invariant is over the components, and `fraction` is their total over `sent`. |
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
| `latency_days` | `int` | Sum over the **inbound** route's legs. ⚙ A round-trip comparison sums both routes' latencies and keeps them as separate fields — the same one-way/round-trip rule as cost (FR-002). |
| `ceiling` | `Money \| None` | Effective monthly deployment ceiling |
| `status` | `str` | |
| `disruption_probability` | `float` | The **maximum** over the route's legs, and documented as a *lower bound*. ⚙ Compounding (`1 − Π(1−pᵢ)`) would assume leg failures are independent, which for two legs at one bank they are not; a lower bound that says it is one is honest, a compounded figure that looks exact is not. Reported beside the cost, never inside it (FR-026). |

### `RouteUnusable`

Returned instead of a `RampCost` when a route cannot carry the amount on the date.

| Field | Rule |
|---|---|
| `path`, `binding_constraint`, `required`, `actual`, `shortfall` | Names what bound and by how much (FR-014). A route excluded from a ranking is excluded *with this recorded*, never silently. |

### `Ranking`

| Field | Type | Rule |
|---|---|---|
| `costed` | `tuple[RampCost, ...]` | Every candidate, each costed by the single costing function, ordered **lexicographically** on `(round-trip cost, ceiling descending, latency)`. ⚙ Lexicographic and not scored: **B12** forbids a non-standard composite score in the primary ordering, and weighting hryvnia against days would be a preference rather than a fact (research.md D11). |
| `recommended` | `int` | An **index** into `costed`, not a copy (research.md D3). `recommended_cost(r)` returns `r.costed[r.recommended]`, so the winner *is* one of the alternatives and SC-016 can assert identity rather than equality. |
| `excluded` | `tuple[RouteUnusable, ...]` | With reasons |
| `ties` | `tuple[tuple[int, ...], ...]` | Indices tied **on round-trip cost alone**, within the project tolerance — even where their ceilings or latencies differ. ⚙ Deliberate: the owner asked which is cheapest, and "these two cost the same, here is how they differ" answers that; preferring one on an unasked-for tiebreak does not. A tie is reported as a tie (FR-018). |
| `not_comparable` | `tuple[RampCost, ...]` | Those whose `round_trip` is `ExitCostUnknown` — costed, reported, and kept out of the ranking (FR-030) |

### `CapacityUsed`

⚙ Lives in `core/routes/capacity.py`, not `core/results/`: `core.ledger.engine` must import the
key type and `core.routes.execute` imports `core.ledger.events`, so the key had to sit
somewhere the ledger can reach without a cycle. `capacity.py` imports nothing from `ledger`.

The monthly cap accumulator, folded into `LedgerState` beside the cash balances
(research.md D7). Keyed by `(capacity_pool, year, month)` taken from each event's `occurred_on`
— ⚙ **not by route** (research.md D10): two routes through one Monobank card consume one
limit, and keying on the route would give each its own. This section still said `route_id`
after the `Leg.capacity_pool` row was added to correct exactly that, so the document
contradicted itself
— data, never a clock. `remaining(cap, used)` is what feasibility consults, so FR-015's
"capacity already consumed in the same month" is not a special case.

### `FallbackApplied`

| Field | Rule |
|---|---|
| `occurred_on`, `amount`, `policy`, `reason`, `redirect_to` | ⚙ `redirect_to` added: FR-013 requires redirect to a **named** destination, and putting the name in `reason` would make a caller parse prose to group occurrences. `None` for the other policies. Every occurrence is a record, and **every one appears in the output** (FR-013). A silently executed infeasible plan is a top-severity defect. |
