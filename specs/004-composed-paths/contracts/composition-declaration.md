# Contract: the segment-bound declaration

**Feature**: `004-composed-paths` | **File**: `data/composition/<owner_id>.toml`

The one declaration this feature adds (FR-006). How far the owner is willing to let the
search run — policy, not an observation.

## Shape

```toml
# How many declared routes may be chained into one candidate.
#
# **Owner policy, not an observation** -- the same class as `data/objectives/` and
# `data/strategies/`, and the reason there are no citation keys here. Every *number* that
# describes the world lives on a leg, in `data/routes/`, cited.
#
# **No default, deliberately.** A registry with no declared bound fails at load naming this
# file and this field, by the rule that refuses a default staleness threshold (002 FR-028):
# a forgotten line must never read as a chosen policy.
#
# `max_segments = 1` means composition is OFF -- only declared routes are candidates. That
# is a legal choice and the explicit way to disable it; it is not the same as leaving the
# field out.

[owner]
id = "owner-001"

[composition]
max_segments = 3
```

## Fields

| Path | Type | Rule |
|---|---|---|
| `owner.id` | string | Non-empty; must match the owner of the streams it is resolved with, on feature 003's one-owner rule |
| `composition.max_segments` | integer | `>= 1`. Not a float, not a string, no default |

## Refusals, all at load, all naming file and field

| Condition | Why |
|---|---|
| File or directory absent | FR-006: no permissive default |
| `max_segments` missing | Same — a forgotten line is not a policy |
| `max_segments < 1` | A bound of zero admits nothing, including declared routes; it is not a way to disable composition, it is a broken registry |
| `max_segments` not an integer | `STRICT` config, as every other declaration |
| A second file in `data/composition/` | Feature 003's precedent: two owners' policies cannot both be in force, and merging them silently would let one decide the other's reach |
| Extra keys | `STRICT` |

## Provenance gate

`data/composition/` goes in `EXEMPT_DIRS` of `scripts/check_provenance.py` **with its reason
recorded beside it** — the gate is fail-closed over the data tree, so absence from
`SOURCED_DIRS` is an error, not an exemption. The reason is the one `objectives` and
`strategies` already carry: the owner's own stated policy, which has nothing to cite. If a
number that describes the world ever has to live here, it moves to a sourced directory
rather than the exemption widening to cover it.
