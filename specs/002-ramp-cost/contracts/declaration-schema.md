# Contract: route, stream, channel and kind declarations

**Date**: 2026-08-22

The TOML shapes this feature adds. Same validation regime as feature 001 —
pydantic v2 in `terezy.data.declarations.schema` with
`ConfigDict(extra="forbid", strict=True, frozen=True)` and **no field defaults** — and the
same rules: provenance per table, `_pct` fields converted to fractions exactly once at the
loader boundary, dates quoted and parsed there.

Two directories are new and their separation is deliberate: `data/routes/` and
`data/channels/` are **curated** data shared across owners; `data/streams/` is **per-owner**
data. Principle VII's boundary made structural rather than a matter of reading field names.

---

## `data/observation_kinds.toml` — new, and required

Every sourced table in the project names a kind, and every kind declares how fast it ages.

```toml
[[kind]]
id             = "p2p_premium"
staleness_days = 7
note           = "A peer-to-peer premium moves with demand and can shift within a week."

[[kind]]
id             = "bank_fee_schedule"
staleness_days = 365
note           = "A published tariff changes on the bank's own schedule, rarely mid-year."

[[kind]]
id             = "regulatory_limit"
staleness_days = 180
note           = "NBU limits change by decision, not by drift; six months is a review prompt."
```

`staleness_days` has **no default** (FR-028). A kind without it fails at load, and so does a
sourced table naming a kind that is not declared here. `note` is required: a threshold
nobody explained is a number nobody can argue with.

⚙ **Every existing declaration from feature 001 gains a `kind`.** The OVDP terms become
`bond_terms`, the tax class becomes `tax_rule`. That is a migration this feature owns, and
it is the reason `check_provenance.py` must learn to require the field.

## ⚙ `data/venues.toml` — a file this contract forgot

Added during implementation. `Venue.currencies` exists so that a leg moving a currency its
venue cannot hold fails at load, and SC-010 requires adding a **venue** to be a data-only
change — but this contract enumerated routes, channels, streams and kinds and never mentioned
venues. Without the file, "adding a venue" was a code change and the leg/venue currency check
had nothing to check against. Same class of gap as Phase 7b's missing task.

```toml
[[venue]]
id         = "monobank_uah"
name       = "Monobank"
currencies = ["UAH", "USD"]
```

No citation keys: a venue holds no observed number, and `Venue` has no provenance field.

## `data/channels/<pair>.toml`

```toml
[[channel]]
id             = "p2p"
pair           = ["UAH", "USD"]
reference_rate = 42.0
observed_on    = "2026-08-21"
kind           = "p2p_premium"
source         = "SYNTHETIC FIXTURE — invented reference. Not an observed quote."
retrieved_on   = "2026-08-21"
verified_on    = ""

  [channel.buy_side]
  premium_per_unit = 3.0     # UAH per USD, the form the owner actually observes

  [channel.sell_side]
  premium_per_unit = -2.5    # negative is legal: P2P does trade below reference

[[channel]]
id             = "card"
pair           = ["UAH", "USD"]
reference_rate = 42.0
observed_on    = "2026-08-21"
kind           = "bank_fee_schedule"
source         = "SYNTHETIC FIXTURE — invented markup."
retrieved_on   = "2026-08-21"
verified_on    = ""

  [channel.buy_side]
  markup_bps = 150.0

  [channel.sell_side]
  markup_bps = 150.0
```

**Exactly one of `markup_bps` / `premium_per_unit` per side.** Both set, or neither, is a
load-time failure. A precedence rule ("markup wins if both") would silently ignore one of
the two numbers the owner wrote, and there is no reading of that which is not a bug.

**Both sides are required and neither is derived from the other.** A single mid-rate is
never used for a transaction (FR-010), and a system that computed the sell side from the buy
side would be using a mid-rate with extra steps.

A premium of **zero** means the channel is at reference and is legal. A **missing** premium
is refused. A **negative** premium is legal with its observation date.

## `data/routes/<id>.toml` — declared in pairs

```toml
[route]
id            = "monobank_to_binance_p2p"
provider      = "Binance P2P"
origin        = "monobank_uah"
destination   = "binance"
direction     = "inbound"
partner_route = "binance_p2p_to_monobank"   # ⚙ OMIT the key for no exit; see below
status        = "open"

  [[route.leg]]
  index         = 0
  kind          = "fx"
  capacity_pool = "monobank_card_uah_usd"   # the shared rail; ⚙ omit the key if none
  from_venue    = "monobank_uah"
  to_venue      = "monobank_uah"
  from_ccy      = "UAH"
  to_ccy        = "USD"
  channel       = "p2p"
  fee_pct       = 0.0
  fee_fixed     = 0.0
  latency_days  = 0
  disruption_probability = 0.0
  kind_of_observation    = "p2p_premium"
  source        = "SYNTHETIC FIXTURE — invented leg."
  retrieved_on  = "2026-08-21"
  verified_on   = ""

  [[route.leg]]
  index        = 1
  kind         = "transfer"
  from_venue   = "monobank_uah"
  to_venue     = "binance"
  from_ccy     = "USD"
  to_ccy       = "USD"
  fee_pct      = 0.0
  fee_fixed    = 0.0
  latency_days = 0
  disruption_probability = 0.0
  kind_of_observation = "bank_fee_schedule"
  source       = "SYNTHETIC FIXTURE — invented leg."
  retrieved_on = "2026-08-21"
  verified_on  = ""
```

`channel` is **required** when `kind == "fx"` and **forbidden** otherwise — a transfer with a
channel is a declaration that means nothing, and accepting it would let a reader believe a
conversion happened.

⚙ **TOML has no `null`, and this contract wrote one.** An earlier version showed
`partner_route = null` and `capacity_pool = null`; no parser accepts that. **Absence is
expressed by omitting the key**, which means those two pydantic fields carry `X | None = None`.

That is the one qualification on the zero-defaults rule, and it is narrow: a `= None` default
is permitted **only** where the core field is itself `X | None` meaning *the owner declared
nothing*, and never where it would stand in for a number, a date or a policy. `verified_on`
stays present-and-empty, because "unverified" is a state to record rather than an absence.

An omitted `partner_route` means *nobody has costed the way out*. It produces
`ExitCostUnknown`, not a reversal (FR-027, FR-030).

## `data/streams/<owner>.toml` — per-owner

```toml
[[stream]]
id              = "salary_uah"
owner_id        = "owner-001"
currency        = "UAH"
amount          = 0.0
cadence         = "monthly"
arrives_at      = "monobank_uah"
income_tax_rate_pct = 0.0

  [stream.indexation]
  policy   = "cpi"
  rate_pct = 0.0
```

⚙ **`via` and `arrival_form` from §4.2 are deliberately absent.** Whether Deel money arrives
as USD or as a stablecoin (§11 item 4) changes which conversions are taxable events, and
changes nothing about the ramp cost. Declaring the fields without the tax treatment would be
a declaration the engine ignores. Named in the spec's Out of scope alongside F1.

`amount = 0.0` is the honest placeholder: `SIMULATOR_SPEC.md` §11 item 3 records that the
owner's actual monthly figures have not been stated. A zero produces a zero result rather
than a made-up one.

`income_tax_rate_pct` may be omitted — and omitting it means **the owner has not stated
one**, which is different from zero. Since there are no defaults, the field is optional in
the schema and `None` in the core, and the output says "no income-tax rate declared" rather
than showing a net figure that quietly equals the gross.

Streams carry no `source`/`verified_on`: an owner's own salary is not an observation needing
a citation, it is a statement of fact by the only person who can make it. This is the same
exemption `data/scenarios/` already has.

⚙ **The exemption covers `income_tax_rate_pct` too, and that needs saying rather than
inheriting silently.** It looks like a tax rate, and every other tax rate in this project
must carry a citation (Principle I). It is exempt because it is not a *modelled* rate: §4.2
puts the owner's own income-tax position outside the simulator entirely — the tool takes
net-of-income-tax amounts as input, and this field exists only so the deployable figure is
not overstated. A rate the engine *applies to a taxable event* would need a source; a rate
the owner states about his own payslip does not. If that ever changes, this sentence is the
thing to revisit.

## Enforced rules

Each maps to a requirement and to a case in `tests/contract/test_route_declaration_loading.py`.

| Rule | On violation | Requirement |
|---|---|---|
| Unrecognised, missing or wrong-typed field | Error naming file and field; no default substituted | FR-024 |
| `verified_on` key absent (curated files) | Error. Empty string is fine; absence is not | FR-022 |
| Table with observed values but no `source`/`retrieved_on`/`kind` | Error | FR-022, FR-028 |
| `kind` naming an undeclared `ObservationKind` | Error naming the kind and the known ones | FR-028 |
| An `ObservationKind` with no `staleness_days` | Error — no permissive default | FR-028 |
| Duplicate route id, or duplicate `(provider × currency path × venue)` | Error naming both files | FR-023 |
| A route with no legs | Error — never costed as free | Spec edge case |
| Legs that do not chain by venue or currency | Error naming file and leg index | FR-024, spec edge case |
| First leg not at `origin`, last not at `destination` | Error | FR-024 |
| A leg moving a currency its venue cannot hold | Error | FR-024 |
| Unknown `leg.kind` / `channel` / `venue` / `cadence` | Error naming the value and the known ones | FR-021 |
| `channel` set on a non-`fx` leg, or missing on an `fx` leg | Error | FR-011 |
| Both or neither of `markup_bps` / `premium_per_unit` on a side | Error | FR-010 |
| A channel side missing entirely | Error — no mid-rate is ever synthesised | FR-010 |
| `disruption_probability` outside `[0, 1]` | Error | FR-026 |
| Negative `fee_pct`, `fee_fixed`, or `latency_days` | Error | FR-024 |
| `partner_route` naming a route that does not exist | Error. `null` is legal; a dangling id is not | FR-027 |
| `partner_route` whose `direction` is not `exit` | Error — an inbound route is not an exit | FR-027 |
| ⚙ Exit route whose `origin` is not the inbound route's `destination` | Error. A pair that does not meet would load and produce a **confident round-trip figure for two unrelated journeys** — the exact class of number FR-030 exists to refuse | FR-027 |
| ⚙ Exit route whose `destination` does not hold the base currency | Error. "Getting money back into **spendable** base currency" is what §4.3.3 asks for; an exit ending in a third currency at an exchange has not got the money out | FR-027 |
| ⚙ Two legs naming one `capacity_pool` with different `monthly_cap` values | Error naming both files. Two numbers for one real limit means at least one is wrong, and choosing either would be a guess | FR-015 |
| ⚙ A fallback policy of `place_on_deposit` | Error naming the feature that will bring it. The core's `DEFERRED_POLICIES` key is `place_on_deposit`; this table said `deposit`, and an alias was **not** added — two spellings for one policy is the duplication this project removes everywhere else. Any other spelling gets the unknown-policy error listing the three that work. This feature adds no instruments, and treating it as "hold as cash" would be a substituted default | FR-013 |
| A stream's `arrives_at` naming an unknown venue | Error | FR-024 |
| Malformed TOML | Error naming the file | FR-024 |

Cross-file checks — duplicate identity triples, leg chaining, `partner_route` resolution,
kind resolution, venue and channel references — run in
`terezy.data.declarations.resolver`, after each file is parsed individually. pydantic cannot
see across files.

## `scripts/check_provenance.py` changes

Three, all small:

1. `SOURCED_DIRS` gains `streams`... **no** — streams are exempt, as argued above. It gains
   **`channels`** only; `routes` is already there.
2. Every sourced table must name its observation kind, and it must be declared in
   `data/observation_kinds.toml`. This is the mechanical half of FR-028.

   ⚙ **On a route leg the key is `kind_of_observation`, not `kind`** — a leg's own `kind` is
   `transfer`/`fx`. Trying the two keys in order produced a *true statement about the wrong
   field* ("names the observation kind 'transfer'"), so a leg table is recognised by name and
   required to declare `kind_of_observation` and nothing else.
3. `STRUCTURAL_KEYS` gains `kind`, `direction`, `provider`, `partner_route`, `channel`,
   `cadence`, `policy`, `index`, `pair` — identifiers and references, not observations, so
   they must not trip the "table carries observed values" heuristic.

The script still cannot evaluate staleness: it has no as-of date and must not invent one.
It verifies the **declaration** is complete and leaves the verdict to the engine.
