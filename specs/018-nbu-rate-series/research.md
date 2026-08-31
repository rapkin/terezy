# Phase 0 research: 018-nbu-rate-series

Every retrieval recorded here was performed on **2026-08-31** against the National Bank's own
service, with `curl --compressed`, and is reproducible by the command quoted beside it. Nothing
below is remembered.

## D1 — The range endpoint, and one request for the whole span

**Decision.** `https://bank.gov.ua/NBU_Exchange/exchange_site?start=YYYYMMDD&end=YYYYMMDD&valcode=usd&sort=exchangedate&order=asc&json`,
one request covering the whole window.

**Rationale.** FR-008 requires reading the publisher's own `units` per row and refusing on a
mismatch. The per-date endpoint (`NBUStatService/v1/statdirectory/exchange`) does not state a
unit at all, so a script built on it could not perform the refusal — it would have to assume the
unit, which is the two-orders-of-magnitude failure FR-008 exists to prevent.

**Measured.** `start=20191228&end=20260901` returned **2,439 rows in 0.41 s**, `units = 1` on all
2,439, `cc = USD` on all, strictly ascending, one row per calendar day for
2019-12-28 .. 2026-08-31 — 2,439 days, zero missing.

**Alternative rejected:** chunking by year. Unnecessary at this size and it turns one shape check
into N, each of which could disagree with its neighbours at a seam.

## D2 — The requested window is one day wider than the required one

**Decision.** Request `START .. retrieval_date + 1 day`; require completeness only over
`START .. retrieval_date`; **drop** every row dated after the retrieval date, naming it.

**Rationale.** FR-010's day-ahead drop has to be *reachable*. Requesting `START .. today` would
mean the publisher never offers a day-ahead row, the drop would never fire, and the requirement
would be satisfied by a branch nothing ever takes. Asking for the day the publisher has already
set and declining it is the honest form, and it is what makes SC-020 an assertion about
behaviour rather than about a window choice.

**Measured 2026-08-31 (local, EEST).** The publisher's last available row is `31.08.2026`
(44.5505, `calcdate` 28.08.2026) and `start=20260901&end=20260902` returns `[]`. So on this
retrieval date nothing is dropped; the drop is exercised against a constructed response
(SC-020's second clause).

## D3 — The lower bound is the publisher's unit change, retrieved

**Decision.** `2019-12-28`.

**Measured.** `start=20191220&end=20200105`:

| exchangedate | rate | units | rate_per_unit |
|---|---|---|---|
| 27.12.2019 | 2329.2885 | **100** | 23.292885 |
| 28.12.2019 | 23.6862 | **1** | 23.6862 |

`quotation_unit` is one value for the whole series (`schema.py`), the shipped file declares
`1.0`, so 2019-12-27 and earlier is a **second series** (FR-011) and not a longer one.

## D4 — `verified_on` is carried forward by re-reading the file the script is about to replace

**Decision.** `main` parses the existing declaration with `tomllib` into
`{on_date: (value, verified_on)}` and passes it to the pure `render`. `render` emits the stored
`verified_on` only where the date is present **and** the value compares equal; otherwise `""`.

**Rationale.** FR-006 is per observation. Comparing the value is what makes the clearing
automatic: an attestation was about a number, and a restated number is a different one. The
comparison is float equality rather than a tolerance — a restatement the publisher made is a
different published figure however small, and a tolerance here would silently keep an
attestation about a value nobody checked.

**Alternative rejected:** a separate sidecar of verifications. It moves the attestation away from
the row it is about, and `check_provenance.py` globs `*.toml` under sourced directories only, so
the field would leave the one gate whose job is to see it.

## D5 — `observation_for` indexes by bisection, not by a second copy

**Decision.** `bisect.bisect_left` over a tuple of the observation dates, built by a module-level
helper from the ascending observations the loader already guarantees.

**Rationale.** FR-022. The dict rebuild is O(rows) per call, so at 2,439 rows and one lookup per
taxable event it is O(rows × events). Bisection is O(log rows) and adds **no state**: the
alternative — caching a date-keyed mapping on `OfficialRateSeries` — would put the same fact in
two places on a frozen record, which is where drift has come from in this repository, and the
loader's strict-ascending check is what makes the search total.

The rule path keeps its linear scan over `NonPublicationRule.days`: a rule is an explicitly
enumerated mapping of the handful of dates a publisher skips, its size is not a function of the
series', and this series declares none.

## D6 — The manifest gains a kind, mirroring the inflation split

**Decision.** `InputKind` gains `"official_rate"`; a new `official_rate_input_refs` takes
`resolver.OfficialRateDeclarations`; `of_run` takes `official_rates=None` beside `inflation`.

**Rationale.** `OfficialRateDeclarations` already carries `series` and `files`, which is exactly
what an `InputRef` needs, and it is resolved separately from `Declarations` — the same shape
`InflationDeclarations` has, so it gets the same treatment rather than a new one.

**Consequence, deliberate:** the golden run passes its official rates and so gains one input
line. The spec anticipates this (*"any re-fetch rewrites `retrieved_on` and moves that digest, so
a golden recording this file is regenerated on every re-fetch"*) and Principle V says an input
digest is a witness, not a term.

## D7 — The gate summarises unverified values per file, and errors stay per value

**Decision.** `check_provenance.py` prints one `warning:` line per file carrying unverified
values, stating the count. Errors are unchanged.

**Measured before the change.** 704 unverified values across 32 files. Adding 2,439 takes the
per-value form to ~3,140 lines.

**Rationale.** FR-023. An error is a thing to fix and there are none; a warning is a standing
state a human is supposed to read, and 3,140 lines of it is a gate that is off.

## D8 — No fixture may be mistaken for a real rate

**Decision.** The fetch script's tests build **constructed** response payloads in the test module,
with invented rates and a marker in the module docstring; no captured live response is checked
in, and no test restates a value from `ua_nbu_usd.toml` as a literal.

**Rationale.** spec.md, Assumptions. A checked-in "captured response" is a retrieval record
nobody can date, and its values would look exactly like the real ones. The script's tests are
about *shape* handling — a unit mismatch, a short range, a day-ahead row — and shape needs no
real rates.

**The one exception, and it is not a fixture.** SC-001 and SC-002 must strike a base against the
**shipped** series. Those tests read the value out of the declaration and re-derive the base from
it; they never copy a literal.

## D9 — Prose in the tree that says the series is empty

Landing data falsifies four claims. They are part of the change, not follow-up:

| where | claim |
|---|---|
| `data/official_rates/ua_nbu_usd.toml` header | the whole file: "NO OBSERVATION IS DECLARED", and the rule paragraph's reason |
| `data/tax/timing/ua.toml` | "The series it points at declares no observation yet" |
| `tests/worked_examples/test_base_versus_received.py` | "the shipped Ukrainian series declares **no observation at all**" |
| `tests/contract/test_official_rate_declaration_loading.py` | the same, plus a test asserting `covers is None` |
| `scripts/check_provenance.py` | "closing it belongs with whoever builds the fetch script" |
