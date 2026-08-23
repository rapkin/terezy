# Contract: the spendable-endpoint declaration

**Feature**: `003-route-coverage` | **File**: `data/spendable/<owner_id>.toml`

The one declaration this feature adds (spec Assumptions: "exactly one new file"). It states
where money counts as having come back out — a fact about the owner's life, entered as data
so that changing it changes verdicts with no source-code change (FR-004, SC-019).

## Location

`data/spendable/`, a per-owner directory beside `data/streams/`, **not** a root-level file
beside `venues.toml`. Principle VII: curated declarations describe the world and are shared;
per-owner declarations describe this person and are not (research.md D3).

## Shape

```toml
# Where money counts as having come back out.
#
# Base currency only, at the venues the owner actually spends from -- not "UAH anywhere",
# and not foreign cash in hand (spec FR-004, owner decision 2026-08-22). An exit ending in
# UAH at a venue absent from this list is deficit 3, exactly as one ending in dollars is.
#
# NO CITATION KEYS, and that is deliberate: there is no observed value here for a source to
# vouch for -- an id, a currency code, and the owner's statement about his own life. Same
# reading as `data/venues.toml`. Every *number* lives on a leg, in `data/routes/`, cited.

[owner]
id = "owner-001"

[[spendable]]
venue    = "monobank_uah"
currency = "UAH"

# Only the venues the owner actually spends from. `binance` can hold UAH and is not
# listed: holding hryvnia on an exchange is not the same as being able to spend it.
```

## Fields

| Path | Type | Rule |
|---|---|---|
| `owner.id` | string | Non-empty. Must match the owner of the streams it is resolved with |
| `spendable[].venue` | string | Must name a declared venue; unknown ids fail at load naming file and field |
| `spendable[].currency` | string | Must be the base currency the set was resolved against (FR-004) |

## Refusals, all at load, all naming file and field

| Condition | Why it is refused rather than defaulted |
|---|---|
| Unknown `venue` | The loader's existing `_known` path. A spendable endpoint at a venue nobody declared cannot be checked against anything |
| Venue cannot hold that currency | `Venue.currencies` already exists for this class of contradiction; the loader owns the same check for legs |
| Currency is not the base currency | FR-004 says base only. Accepting USD would make the report decide that foreign cash counts as spent |
| Duplicate `(venue, currency)` | The loader's existing duplicate-id precedent |
| Empty `[[spendable]]` list | Would make every exit deficit 3 — a confident wrong answer built out of a forgotten line (research.md D13) |
| Empty `data/spendable/` directory | The reason `ramp_from_data_root` already gives: a mistyped path and an empty world are indistinguishable downstream |
| Extra keys | `STRICT` config, as every other declaration file |

## Loader surface

```python
# terezy.data.declarations.loader
SPENDABLE_TABLE: Final = "spendable"
def spendable_from_file(path: Path) -> tuple[str, tuple[SpendableEndpoint, ...]]  # owner_id, endpoints

# terezy.data.declarations.resolver
@dataclass(frozen=True, slots=True)
class CoverageDeclarations:
    ramp: RampDeclarations
    spendable: frozenset[SpendableEndpoint]
    spendable_file: Path

def coverage_from_data_root(root: Path, *, base_currency: Currency) -> CoverageDeclarations
```

A record beside `RampDeclarations` rather than more fields on it, on the precedent
`RampDeclarations` itself sets against `Declarations`: the two describe different runs, and
a data root with no spendable file must still be able to cost a ramp.

## Provenance gate

`scripts/check_provenance.py` scans `SOURCED_DIRS = ("tax", "instruments", "routes",
"channels")`, and `spendable/` is not added to it: there is no observed value in the file
(research.md D4).

⚙ **Amended 2026-08-23, after the 002 review made the gate fail-closed.** Not being in
`SOURCED_DIRS` is no longer sufficient — the gate now errors on any directory under `data/`
that is in neither `SOURCED_DIRS` nor `EXEMPT_DIRS`, because an allowlist made a new directory
the one place the gate could not see. So `spendable` is named in **`EXEMPT_DIRS`, with its
reason recorded beside it**, in the voice of the `streams` entry it mirrors. The intent of D4 is
unchanged and the mechanism is stricter: the exemption now has to be *argued in the script* to
exist at all. The tests assert both halves — not in `SOURCED_DIRS`, and in `EXEMPT_DIRS` with a
non-empty reason — rather than assuming either.
