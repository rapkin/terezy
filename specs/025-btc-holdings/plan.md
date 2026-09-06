# Implementation Plan: The BTC he already holds

**Feature**: `025-btc-holdings` | **Date**: 2026-09-06 | **Spec**: [spec.md](./spec.md)

**Branch**: this specification is written on `spec/025-btc` and lands squashed. The
implementation gets its own branch, `feat/025-btc-holdings`, landing by a `--no-ff` merge.

**Both clarifications are answered** (2026-09-07,
`specs/decisions/2026-09-07-clarify-025.toml`): the instrument is priced in USD through a
declared USDT=USD belief, and a held position gets its own section of the answer. Nothing in this
plan is gated any more, and `features.toml` moves off `drafted`.

## Summary

Four independent pieces that meet once, at the end.

1. A private second data root, so a real declaration has somewhere to go that is not git.
2. A declaration kind with no terms, so a thing whose only property is a price is declarable.
3. The first `Provider`, so that price exists as dated data.
4. A conversion already built (011), applied to a cost basis for the first time.

Only the fourth is arithmetic. The other three are about **where a fact is allowed to live**,
which is why most of the risk is in the loaders and the gates rather than in a formula.

## Technical Context

**Language/Version**: Python 3.13.

**Primary Dependencies**: none new. `urllib.request` for the fetch, as
`scripts/fetch_nbu_rates.py` uses; `tax.official_rate.strike_base` for the conversion.

**Storage**: version-controlled TOML for the instrument, the group, the observation kind and the
fetched series; **gitignored** TOML under `data/user/` for the owner's lots.

**Testing**: pytest. One worked example (the struck basis), one property-based invariant (both
marks survive), contract tests for the overlay refusals and for data-only extension, unit tests
for the fetch script driven by a recorded response fixture.

**Target Platform**: library plus one script.

**Project Type**: single Python library, `cli → api → data → core`.

**Constraints**: no fifth plugin interface; the core opens no connection and reads no file; the
fetch lives in `data/providers/` with the script a thin wrapper over it; the project tolerance is
imported; the owner's figures never enter the repository, in a test fixture or anywhere else.

**Scale/Scope**: one new core module, one new data module, one new script, edits to the loader,
the resolver, the manifest, the citation policy and three data files, and one new gitignored
directory.

## Constitution Check

| Principle | How this feature meets it |
|---|---|
| I — honesty over precision | The tax figure is refused by name rather than reported as zero (FR-014). The price is unverified for ever and the basis is the owner's estimate; both marks reach every derived figure (FR-027). No volatility, no Sharpe — a daily close series makes them computable and the spec puts them out of scope. |
| II — framework, not script | A fourth declaration *kind*, not a fifth interface: it satisfies no part of `InstrumentOps` because it projects no event stream, which is the fund's ruling (2026-08-23) with a stronger warrant. `Provider` is implemented for the first time. A second held asset is data (SC-008). |
| III — pure deterministic core | The fetch is in `data/`, the script outside the package; the data layer reads the declared series and hands frozen records to the core. No clock: the price is selected by the run's `as_of`, which is an input. |
| IV — stated contracts | Every refusal is a typed value: the collision, the non-synthetic seed under `data/`, the missing observation, the missing rate, the unresolved tax class. The fetch script writes nothing on any refusal and leaves the previous file byte-identical. |
| V — test-first | The struck-basis worked example fails with an `ImportError` before the module exists. The fetch script's malformed-response cases are written before the parser. |
| V — a golden is evidence | The overlay moves nothing (SC-001). The answer golden moves twice by design — when `btc` stops being undeclared, and again when Phase 5 settles the section shape — regenerated each time with the changed lines quoted. |
| VI — the whole tuple | A held position is not a tuple and is not pretended to be one: no route in, no exit terms, no rank. What it reports is a value and a basis, and the spec says in as many words that it is not a candidate. |
| VII — owner-scoped and private | The whole first phase. No key, no account, no header identifying the owner on the fetch; the overlay is gitignored, outside every gate, and its contents never reach a manifest, a test or a log. |

No violation to justify.

## The privacy design, stated once

**The overlay is not composed on disk.** `tests/data_roots.py` copies both trees into a temp
directory, and that is correct for a test and wrong here: copying the owner's real figures to
`/tmp` puts them somewhere nobody gitignored. Composition is therefore **in memory** — a frozen
`DataRoots(shipped, overlay)` record and one function that globs both and refuses a collision.

**The manifest records the path, never the value.** An overlay input's id is prefixed `user/`,
which makes it distinguishable, keeps it from colliding with a shipped id, and lets a reader of
a result see that a private declaration was involved without seeing what it said.

**No test uses the real overlay, and the fixture overlay is its own root.** It lives at
`tests/fixtures/user_root/` and is passed as the overlay argument — *not* under
`tests/fixtures/data/`, which `tests/data_roots.py` copies **into** the shipped root. It declares
a held asset and nothing else, which is what keeps it clear of FR-003: the composed root's
`seeds/owner-001.toml` holds two synthetic ОВДП lots, the overlay holds one held-asset lot, and
the collision rule is per instrument, so the two are unioned. `data/user/` does not exist in CI,
which is FR-002's case, so the whole suite runs the absent-overlay branch as a matter of
course.

## The work, in phases

**Phase 1 — the overlay, written test-first.** `DataRoots`, the two-root glob, the collision
refusal naming both paths, and the `is_synthetic` rule. Only `seeds/` is admitted (FR-006), and
the admitted set is fail-closed so a directory nobody declared is an error rather than ignored.
`seeds_and_goals_from_data_root` takes `DataRoots` instead of a `Path`. Every other
`*_from_data_root` is untouched, but the signature change is **not** one function wide: the HTTP
layer calls it (`src/terezy/api/http/categories.py`) and a dozen contract-test sites do, and all
of them move in the same phase.
`citation_policy.EXEMPT_DIRS["user"]`'s reason is corrected and `data/README.md`'s row with it, and `.gitignore` is left exactly as it is — `data/user/` is already there.

**Phase 2 — the held asset.** `core/instruments/held.py` with the declaration record;
`HELD_ASSET` joins `registry.DECLARATION_KINDS` and stays out of `registry.REGISTRY`;
`loader.held_asset_from_file` and the resolver's dispatch on the declared kind, exercised against
a fixture instrument. `btc` joins `data/groups.toml` — a label turns on nothing. The tax refusal
is `UnresolvedTaxClass`, which already exists and already says why; nothing new is written for
it. **`data/instruments/btc.toml` is not written here**: it would have to state a price currency,
and that is Clarification 1.

**Phase 3 — the provider.** `data/providers/interface.py` declares the signature;
`data/providers/binance.py` implements it over `/api/v3/klines` behind a module-level `_get`
seam, paginating at the documented 1000-row cap; `scripts/fetch_binance.py` is the wrapper with
`--symbol`, `--dry-run` and `--out`, building the file in memory and renaming a temp path over
the target. Every refusal is written first, against a recorded response fixture and its
mutations. The observation kind is declared here with its threshold recorded **inert** and the
reason why (FR-024), so the file can land and the provenance gate can read it.

**Phase 4 — the struck basis.** The strike is in the **resolver**, not in
`core.ledger.seeds.seed_cost`, and the difference is not stylistic: by the time a lot reaches
`seed_cost` its cost is already `Money(x, base_currency)`, so there is nothing left to convert —
and `strike_base` *raises* when the amount is already in the tax currency, which base and tax
both are today. `resolve_seeds_and_goals` already holds the instrument declarations and gains the
rate series; it strikes before the cost is tagged, and refuses per FR-028. `seeds_from_file`
therefore stops tagging a cost it cannot know the currency of. The worked example is written
first, on placeholder figures; `tests/invariants/` gains the property that no figure resting on a
struck estimated basis shows fewer than two marks.

**Phase 5 — the shipped data, and the answer.** The USDT belief is declared and the instrument
states USD; `SubjectStanding` gains a fifth member and `Answer` gains a held section. Then the
goldens, the OpenAPI document and `docs/METHODOLOGY.md`.

## Which tests re-measure, and which are written by hand

| Test | How its figures are obtained |
|---|---|
| `tests/worked_examples/test_struck_basis.py` | **by hand**: `cost × rate ÷ quotation_unit` at a placeholder acquisition date, against a rate read out of the shipped series |
| `tests/invariants/test_struck_basis_marks.py` | property-based: a figure resting on a struck estimated basis carries both marks, over generated lots and dates |
| `tests/contract/test_private_overlay.py` | the four refusals — collision, non-synthetic under `data/`, undeclared overlay directory, absent overlay — against a scratch root |
| `tests/contract/test_held_asset_data_only.py` | a second held asset added in a scratch data directory reaches the pipeline with no engine edit (H1's shape) |
| `tests/unit/test_fetch_binance.py` | a recorded response fixture and its mutations; `_get` is replaced, never called. Prices in the fixture are **invented**, as `test_fetch_nbu_rates.py`'s are |
| `tests/golden/*.golden.txt` | re-measured in Phase 5 only. Byte-identical before it (SC-001) |

## Decisions a reader will want the reason for

**The currency is on the instrument, not on the seed.** Argued in the spec. The operational half
is that it makes 008 FR-010 a rule this feature *narrows* and must say so in 008's own text — two
live documents disagreeing about what a declared cost means is how the 40× error gets written.

**`data/observations/` is read at run time for the first time.** A fund's NAV has a judgement in
it and is promoted by a human; a daily close does not, and hand-promotion would be transcription.
The spec carries the argument; the plan's consequence is that `data/README.md`'s row changes and
the resolver gains a reader for that directory.

**The observation is selected by exact date, never by the nearest one.** Crypto trades every
calendar day and the publisher emits a close for every one of them, so there is no weekend hole
to paper over — and 011 FR-010 already decided that snapping to a neighbouring date is how a tax
base goes wrong on the dates that matter.

**The provider interface is in `data/providers/` and the script is a wrapper.**
`scripts/fetch_nbu_rates.py` is self-contained and its test loads it by path through
`importlib`, which is fine for a script nobody else calls. `Provider` is one of the four
declared interfaces, so its home is the package, and the script becomes the thin part.

**No cache.** Constitution: a cache entry carries provenance and a fetch failure never writes.
The declared file *is* the cache, it is in git, and it is diffable. Adding a second store is
`provider-automation`'s job, not this one's.

## Prose this change falsifies, and deletes

`data/README.md`'s `observations/` row ("read by nothing at run time"), its `data/user/` row in
the rule-5 table ("what a run produces"), and `citation_policy.EXEMPT_DIRS["user"]`'s reason.
`src/terezy/data/providers/__init__.py`'s docstring describes an interface that does not exist;
it is replaced by one, not by a longer docstring. Deleted, not rewritten.
