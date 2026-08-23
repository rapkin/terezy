# Phase 0 research: CPI and real terms

**Feature**: `007-cpi-real-terms` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

The owner resolved this feature's one collision on 2026-08-22 — 001's FR-022 forbids a real
figure from an assumed rate, and a hurdle projects into the future where only assumptions
exist. The answer was **both figures, separately labelled, never mixed**, and it shapes
almost every decision below.

**The data already exists.** `data/cpi/ua.toml` was fetched on 2026-08-23 by
`scripts/fetch_cpi.py` from Держстат via data.gov.ua: 411 monthly observations,
**1991-08 to 2025-10**, each with its citation, its retrieval date and an **empty**
verification date. D1 and D9 are about living with what that series actually is.

---

## D1 — The declared series is month-on-month, so a window is a product, not a difference

**Decision.** `data/cpi/ua.toml` holds the published index of each month **against the
previous month** (100.9 means prices rose 0.9% that month). Cumulative inflation over a
window is the product of every month's `value / 100`, minus one. There is no level index and
none is synthesised.

**Rationale.** That is the form Держстат publishes and the form the fetcher wrote; inventing
a base-100 level series would mean choosing a base period nobody published and carrying a
rounding error through every month since 1991. The product is exact over whatever window the
observations cover, and it needs no base.

**The trap this creates and the test that catches it.** A month-on-month series invites
being summed. Over Ukrainian inflation magnitudes the difference between the sum and the
product is material — the same reason FR-008 forbids the subtraction approximation one level
up. The hand-computed worked example uses a window long enough that summing and multiplying
give visibly different answers, so the wrong one cannot pass.

## D2 — The reserved slot holds a two-figure record, and always holds one

**Decision.** `HurdleRate.real` becomes `RealTerms`, a record with two fields, each
`RealRate | RealTermsUnavailable`:

- `realized` — deflated by declared CPI observations, for the portion of the horizon they
  cover;
- `assumed` — deflated by the declared future-inflation assumption, for the projected
  portion.

`HurdleRate` keeps exactly one field named `real`. `RealTerms` is never itself the
unavailable value: when neither figure can be computed it holds two unavailable values, each
with its own reason.

**Rationale.** FR-009 says the real-terms output carries two figures and neither may stand in
for the other; FR-006 says the result's shape must not change. Those are only compatible if
the *slot* stays one field and the *occupant* carries both. Adding a second field to
`HurdleRate` would break FR-006's invariance claim, which 001's FR-022 existed to make.

**Always a `RealTerms`, never a bare unavailable**, because "which of the two is missing" is
the question FR-012 requires answering, and a single unavailable value cannot answer it.

## D3 — The Fisher relation exactly, and the approximation is unrepresentable

**Decision.** `real = (1 + nominal) / (1 + inflation) - 1`. There is no function in this
feature that subtracts an inflation rate from a nominal one.

**Rationale.** FR-008 in as many words, and the reason is arithmetic: at 20% inflation the
subtraction approximation is off by several percentage points — larger than most of the
differences this tool exists to detect. The methodology entry lands in the same change as
the formula, with a worked example, because the constitution requires it and because the
approximation is what a reader will assume unless told otherwise.

## D4 — Coverage is all-or-nothing per window, and a gap is a refusal naming the gap

**Decision.** The realized figure requires observations covering **every** month of the
deflation window. One missing month makes it `RealTermsUnavailable` naming that month. No
interpolation, no carry-forward, no shortening of the window to what happens to be covered.

**Rationale.** FR-004 and FR-012. Shortening the window silently would be the most tempting
of the three: it produces a number, and the number is real for *a* window — just not the one
asked about. Naming the missing month turns the refusal into an instruction, which is the
same move feature 003 makes with a missing route.

**This bites immediately and that is correct.** The declared series ends 2025-10, so every
window reaching into 2026 is uncovered, and today the realized figure for 001's own hurdle is
unavailable — with a reason naming the uncovered period rather than 001's "inflation is not
modelled". That is FR-012 working, not a defect, and re-running the fetcher is the fix.

## D5 — The future-inflation assumption is scenario data, in the shape a regime transition has

**Decision.** A per-run declaration under `data/scenarios/`, carrying `is_assumption = true`,
a rate, a rationale, and — where it is an external forecast — its own citation, retrieval
date and staleness kind. Passed in per run; never a constant, never a default.

**Rationale.** FR-015, and the precedent is exact: `data/scenarios/war_end.toml` carries a
transition date that is a belief, marked `is_assumption = true`, and `data/scenarios/` is
exempt from the provenance gate for that reason. An inflation forecast is the same epistemic
object. **An external forecast is still an assumption** (FR-010): the National Bank's number
has a citation and a retrieval date, and it is a forecast — cited does not make it observed,
and the label says assumption either way.

**No default rate.** A missing assumption makes the assumed figure unavailable naming that
absence. The refusal is the feature, not a gap in it.

## D6 — Provenance is the union of both sides, and there is no place to lose it

**Decision.** A real figure's provenance is `merge_all` over the nominal figure's provenance
and every CPI observation used. Not a summary, not a count — the same `SourceRef` set the
inputs carried.

**Rationale.** FR-013, and the constitution's top severity class. The union is one call to
machinery that already exists and is already covered by
`tests/contract/test_provenance_propagation.py`; anything cleverer would be a second
propagation path, which is how a mark gets dropped. **411 observations means a real figure
over a long window carries hundreds of sources** — that is the honest answer, and the test
asserts the count rather than a sample.

## D7 — CPI's staleness kind already exists, and it ages the retrieval rather than the value

**Decision.** `cpi_index`, declared in `data/observation_kinds.toml` with a 45-day threshold,
is the kind every CPI observation names. Staleness is measured from the later of verification
and retrieval, per 002's FR-025.

**Rationale.** FR-005. The kind was declared when the fetcher landed, and its note states the
distinction this feature depends on: **a published index for a month that has ended is a
historical fact and does not decay** — what ages is the *retrieval*, because the publisher
adds a month roughly every month and a series fetched long ago is missing its recent end.
Forty-five days is the re-fetch prompt.

**Do not confuse the two questions.** "Is this observation stale?" is answered by the
threshold. "Does the series reach the end of my window?" is answered by the coverage check of
D4. Both can fire, they mean different things, and the output must not merge them.

## D8 — Nothing about a nominal figure changes, and the golden proves it

**Decision.** No nominal computation is touched. `tests/golden/ovdp_synthetic_a.golden.txt`
keeps every figure it has.

**Rationale.** FR-014. **The golden will move on exactly one kind of line**: the real slot
renders two entries instead of one, and its reason text changes from 001's "inflation is not
modelled in this feature" — which stops being true the moment this lands — to the specific
reason FR-012 requires. That is the expected diff and the only expected diff; every nominal
figure, schedule row and tax charge stays byte-identical. State it before regenerating, read
the diff, and if a nominal figure moves, stop.

## D9 — Where the code lives

**Decision.**

- `core/inflation/series.py` — the declared series, its coverage check, the cumulative factor.
- `core/inflation/deflate.py` — the Fisher relation, and nothing else.
- `core/results/hurdle.py` — touched: `RealTerms`, and `real`'s type.
- `data/declarations/{schema,loader,resolver}.py` — touched: the CPI series and the inflation
  assumption.

**Rationale.** Not `core/metrics/`, which is reserved for the twelve preserved return and risk
behaviours — burying a deflator among Sortino and XIRR would make it look like one of them.
Not `core/analysis/`, which is projection and replay. Inflation is its own small domain with
its own declared data, and one package says so.

## D10 — The fetcher is not part of this feature, and the shape it writes is now load-bearing

**Decision.** `scripts/fetch_cpi.py` stays what it is: tooling that writes a declaration. This
feature's loader reads that file and **must not** reach for the network, cache anything, or
know the script exists.

**Rationale.** Principle III and the K4 no-network rule. But the coupling is real in one
direction: the loader now defines the contract the script's output must satisfy. Where this
feature's schema and the file disagree, **the schema is right and the script is updated** —
the file is generated and can be regenerated, while a loader bent to match a script's
convenience is a loader that will accept the next convenience too.
