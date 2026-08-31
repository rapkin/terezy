# Implementation Plan: The first instruments that are not fixtures

**Feature**: `016-real-ovdp` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Branch**: `feat/016-real-ovdp`, landing on `main` by a `--no-ff` merge after a clean review.

## Summary

Twenty-four real ОВДП issues become declarations. The National Bank's securities register is
the source of every **term**; Inzhur's quotation is the source of the **price**; the two never
share a citation. The registry goes from nine instruments to thirty-three, and every count
pinned on nine moves with it.

Data-only (owner, 2026-08-30): the only source this feature writes is a second fetch script,
the scans and assertions the specification names, and the prose it falsifies.

## Technical Context

**Language/Version**: Python 3.13.

**Primary Dependencies**: none new. The second fetcher uses `urllib` and `tomllib`, exactly as
`scripts/fetch_inzhur.py` does.

**Storage**: version-controlled TOML. One new observation file, twenty-four new instrument
declarations, twenty-four new `[[access]]` entries in the existing file.

**Testing**: pytest. A transcription check over the whole schedule of all 24; a per-issue
disagreement check over the two observation files; a reconciliation of the seller's own stated
yield against an internal rate of return computed here; contract scans over `core/` and over
`scripts/`; a regenerated candidate golden and a regenerated answer golden.

**Target Platform**: library. No delivery surface: results are produced and asserted by the
suite.

**Project Type**: single Python library, `cli → api → data → core`.

**Constraints**: no fifth plugin interface, no new member of the instrument failure union, no
new field on the instrument declaration record (FR-029). Nothing under `core/` may name an
ISIN. No script may write under `data/instruments/` or `data/access/`.

**Scale/Scope**: one new script, one generated observation file of 32 982 lines, 24
declaration files, one edited access file, one edited fixture header, and the test modules
below.

## Constitution Check

| Principle | How this feature meets it |
|---|---|
| I — honesty over precision | Every figure a declared issue produces stays marked, because the price is unverified and taint is asymmetric. What changes is *why*: the terms now rest on the issuer's register, so the output can say which source is unverified. No legal, tax or fee value originates here — the terms are transcribed from a cited endpoint, the price from a cited quotation, the dealing terms from a cited page. |
| II — framework, not script | The whole feature is a data change plus tests. FR-029 is the narrow claim and SC-021 its evidence. |
| III — pure deterministic core | Untouched. The new script lives in `scripts/`, the new observation in `data/observations/`, read by tests and by nothing at run time. |
| IV — stated contracts | The transcription is asserted row by row rather than reviewed; the disagreement between the sources is a check rather than a sentence. |
| V — test-first | Each check is written against the shipped observations before the declarations exist, and fails naming the missing ISINs. |
| V — a golden is evidence | Two goldens move by design and are regenerated deliberately with their changed lines quoted. |
| VI — the whole tuple | Each issue is reached by exactly one access declaration naming both venues, the buy quotation, the resale quotation and a risk class. The buy-versus-sell spread is never presented as a round trip. |
| VII — owner-scoped | Curated data only; no per-owner file is touched except through the counts its results carry. |

No violation to justify. The one recorded cost is FR-011's, already decided by the owner: each
schedule carries a citation calling the issuer's published list an inference, because
`scripts/check_provenance.py` refuses any other shape and 016 stays data-only. The remedy is
the `primary-sourced-schedule-may-be-verified` future entry and is deliberately not built.

## Two collisions this plan resolves

**FR-014 is superseded by feature 015**, which landed after this specification was written and
removed the condition FR-014 states for itself. The argument and what it narrows are
[research.md](./research.md) D7.

**FR-027a is this feature's to apply**, because 015 landed first.
`data/instruments/enumerated_out_of_order.toml` loses its `ovdp` group label and keeps
everything else, and its header stops attributing the seller's transcription error to the
issuer.

## The work, in phases

**Phase 1 — the issuer's record, retrieved and snapshotted.** `scripts/fetch_nbu_depository.py`
writes `data/observations/nbu_depository.toml`: the whole register, every issue and every
payment row, because any filter is a judgement a fetcher may not make. It refuses to write a
thinner file on a shape change, exactly as `fetch_inzhur.py` does.

**Phase 2 — the checks, written first.** Three modules, each failing before a declaration
exists:

| Module | What it pins |
|---|---|
| `tests/contract/test_the_register_the_terms_rest_on.py` | the depository observation's own shape, derived not written: which issues it holds, that МФУ is named on every one, that `pay_type` labels the kind, and that the coupon identity `auk_proc × nominal ÷ 200` holds on the declared 24 |
| `tests/worked_examples/test_two_sources_disagree.py` | the three disagreements, per issue, by ISIN (SC-007) |
| `tests/worked_examples/test_ovdp_reconciliation.py` | the internal rate of return against the seller's stated yield (SC-014) |

**Phase 3 — the declarations.** 24 files under `data/instruments/`, 24 `[[access]]` entries,
each carrying a buy quotation and a resale quotation with the seller's citation, and dealing
terms with the venue's own.

**Phase 4 — the scans and the boundary.** `test_no_isin_reaches_the_core.py` (FR-023, FR-019),
and the declared-set boundary assertion (SC-001).

**Phase 5 — the counts.** Re-measure every site under *Counts that move*, regenerate both
goldens, correct the falsified prose.

## Decisions a reader will want the reason for

Recorded once, in [research.md](./research.md): why the whole register is snapshotted rather
than the 24; why `covers_from` is the placement date; why `published_in_order` is absent from
all 24; where the minimum ticket came from and what its word «приблизно» costs; and why the
reconciliation is computed against the depository's schedule rather than the seller's.

## No new formula, and one corrected claim

FR-028 expected `docs/METHODOLOGY.md` to be unchanged and it is not, in one place that is not a
formula: §0 told a reader that **every** shipped instrument is synthetic, which 24 real
declarations make false. Correcting it is FR-028's own requirement rather than an exception to
the prediction. No formula is added, and the internal rate of return in the reconciliation is
not one: it is a **check on a transcription**, computed in the test module, reaching no result
record and carrying no declaration.
