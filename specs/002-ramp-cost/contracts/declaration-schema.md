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
partner_route = "binance_p2p_to_monobank"   # null means NO round-trip figure exists
status        = "open"

  [[route.leg]]
  index        = 0
  kind         = "fx"
  from_venue   = "monobank_uah"
  to_venue     = "monobank_uah"
  from_ccy     = "UAH"
  to_ccy       = "USD"
  channel      = "p2p"
  fee_pct      = 0.0
  fee_fixed    = 0.0
  latency_days = 0
  disruption_probability = 0.0
  kind_of_observation = "p2p_premium"
  source       = "SYNTHETIC FIXTURE — invented leg."
  retrieved_on = "2026-08-21"
  verified_on  = ""

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

`partner_route = null` is a legitimate declaration meaning *nobody has costed the way out*.
It produces `ExitCostUnknown`, not a reversal (FR-027, FR-030).

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
2. Every sourced table must name a `kind`, and the kind must be declared in
   `data/observation_kinds.toml`. This is the mechanical half of FR-028.
3. `STRUCTURAL_KEYS` gains `kind`, `direction`, `provider`, `partner_route`, `channel`,
   `cadence`, `policy`, `index`, `pair` — identifiers and references, not observations, so
   they must not trip the "table carries observed values" heuristic.

The script still cannot evaluate staleness: it has no as-of date and must not invent one.
It verifies the **declaration** is complete and leaves the verdict to the engine.
