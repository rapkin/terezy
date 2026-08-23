# Contract: the seed and goal declarations

**Feature**: `008-seed-and-goals` | **Files**: `data/seeds/<owner_id>.toml`, `data/goals/<owner_id>.toml`

The first declarations that live wholly on the private side of Principle VII's boundary —
what the owner already holds, and what the money is for.

## Shape

```toml
# SYNTHETIC FIXTURE. These are not the owner's holdings. His real figures are unstated
# (SIMULATOR_SPEC.md §11 item 3) and will replace this file when they arrive.
#
# **Per-owner data, not curated.** Beside `data/streams/` and `data/spendable/`, on the same
# boundary Principle VII draws: instruments, routes and tax packs are shared public facts;
# what this person holds is his life.
#
# **NO CITATION KEYS.** What the owner paid for a lot is his own record, not an observation of
# the world -- the exemption `objectives` and `strategies` already carry. If a market value
# ever has to live here, it moves to a sourced directory instead of the exemption widening.

[owner]
id = "owner-001"

[[seed]]
instrument_id = "ovdp_synthetic_a"
quantity      = 10.0
acquired_on   = "2025-03-14"
cost          = 9_800.0        # base currency, always (FR-010)
basis         = "known"

[[seed]]
instrument_id = "inzhur_reit"
quantity      = 500.0
acquired_on   = "2024-11-02"
cost          = 5_400.0
basis         = "estimated"
reason        = "bought across several months in 2024; the cabinet shows units, not the prices paid"
```

`basis = "estimated"` **requires** `reason`, and `basis = "known"` **forbids** it. The reason
becomes the `source` text of the `SourceRef` that marks every figure derived from the lot —
including the tax on its disposal.

```toml
[owner]
id = "owner-001"

[[goal]]
id                   = "flat_deposit"
currency             = "UAH"
monthly_contribution = 20_000.0
target_sum           = 1_200_000.0
# target_date omitted -- this is the goal the solver answers
```

Exactly two of `monthly_contribution`, `target_sum`, `target_date` are declared for a solve;
all three is the feasibility question.

## Refusals, all at load, all naming file and field

| Condition | Why |
|---|---|
| `instrument_id` naming no curated declaration | FR-005; the loader's existing `_known` path |
| `basis` neither `known` nor `estimated` | No default; an unrecognised value is a typo, not a choice |
| `estimated` without `reason`, or `known` with one | FR-008: the mark must state its reason, and a reason on a known basis means one of the two fields is wrong |
| Fewer than two of the three goal variables | FR-011, named |
| More than one goal with the same `id` | The loader's duplicate-id precedent |
| `currency` other than the base currency | FR-016 — **refused as not yet modelled**, naming the missing FX modelling. Never "invalid currency" |
| A missing required field, an unrecognised field, a malformed value | FR-023; `STRICT`, and no default substituted |
| An empty `data/seeds/` or `data/goals/` directory | **Not refused.** Unlike every other declaration directory: a person with no goal is an ordinary person, not a mistyped path (FR-024, research.md D9) |

## Provenance gate

Both directories go in `EXEMPT_DIRS` of `scripts/check_provenance.py` **with their reason
recorded** — the gate is fail-closed over the data tree, so absence from `SOURCED_DIRS` is an
error rather than an exemption. The reason is the one `objectives` and `strategies` carry: the
owner's own records, which have nothing to cite.
