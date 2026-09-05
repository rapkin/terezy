# Implementation Plan: Real terms on a tuple

**Feature**: `024-real-terms-tuple` | **Date**: 2026-09-06 | **Spec**: [spec.md](./spec.md)

**Branch**: `feat/024-real-terms-tuple`, landing on `main` by a `--no-ff` merge after a clean
review.

## Summary

`TupleOutcome` gains the record the hurdle already carries — a realized real figure and an
assumed one — filled by the function that already fills the hurdle's. Nothing is invented: the
Fisher relation, the two-figures rule, the coverage refusal and the annualisation all exist and
are called from a second site.

The work is therefore three small things and one wide consequence. The window rule moves to one
place so both records derive it identically; the two declared deflators reach the evaluation
through the registries; and the answer's blanket *no real-terms figure* exclusion is deleted
because the figure now exists. The consequence is the answer golden's digest, which moves by
design.

## Technical Context

**Language/Version**: Python 3.13.

**Primary Dependencies**: none new. `core.inflation` supplies the relation, the coverage check,
the annualisation and the staleness of both deflators; `core.results.hurdle.real_terms` is the
one function that assembles them.

**Storage**: version-controlled TOML, unchanged. `data/cpi/ua.toml` and
`data/scenarios/inflation/owner-001.toml` are already declared, already loaded and already
resolved; nothing about either is edited.

**Testing**: pytest. One worked example (the spec's arithmetic), one contract test that the
ranking did not move, one inverted walk, one regenerated golden, one byte-identity assertion on
the golden that must not move.

**Target Platform**: library, plus the published schema.

**Project Type**: single Python library, `cli → api → data → core`, with a TypeScript client
generated from the schema.

**Constraints**: no fifth plugin interface; nothing new imported into `core/`; one deflation
site in the whole codebase; the project tolerance imported, never re-invented; the real figure
never reaches a comparison.

**Scale/Scope**: two new functions in existing core modules, edits to six core modules, one
resolver construction site, one manifest call, one methodology subsection added and one
cross-referenced, six test modules.

## Constitution Check

| Principle | How this feature meets it |
|---|---|
| I — honesty over precision | The figure that cannot be computed is typed-unavailable naming the months (FR-008) or the absent declaration (FR-009), never zero and never carried forward. Observed and assumed inflation stay two figures (FR-007), so no reported number blends a measurement with a belief. |
| II — framework, not script | No branch on an instrument, a venue or a jurisdiction. Both deflators are declarations already in `data/`; a second CPI series stays a data-only addition. |
| III — pure deterministic core | Pure functions over frozen records; the window comes from `span`, not from a clock. |
| IV — stated contracts | Every refusal is a typed value carrying its reason. The tuple's real slot is the same union the hurdle's is, so a nominal rate cannot be assigned into it — mypy, not a test. |
| V — test-first | The worked example is written first and fails before the field exists. |
| V — a golden is evidence | The answer golden moves by design (FR-019), regenerated with its changed lines quoted in the commit message. The candidate golden must **not** move, and that is asserted rather than assumed (FR-018). |
| VI — the whole tuple | The real figure is reported beside the nominal one and never sorted on (FR-017) — the display rule's shape, applied to a figure rather than to a currency. |
| VII — owner-scoped | The belief keeps its `owner_id`; no per-owner data is added. |

No violation to justify.

## The decision this plan does not re-take

**Which inflation deflates a span in the future** looks like this feature's clarification and is
not. The owner answered it on 2026-08-22 (007's Clarifications resolved): *both figures,
separately labelled, never mixed*. Applied here, the realized half refuses on every span this
feature will see — the series ends 2025-10 and the horizons start 2026-09 — and the assumed half
carries the declared belief. Carrying the last published month forward is forbidden by 007
FR-004, and refusing outright would delete the figure the owner asked for.

**What it costs to reuse `RealTerms` rather than one slot** is a refusal on every row that will
never fire differently. That is the price of the owner's rule and it is worth paying: a
single-slot design would have to pick which of the two figures to show, and the benchmark beside
it carries both.

## The work, in phases

**Phase 1 — one window rule, written test-first.** `results/project._deflation_window` derives
the hurdle's window from a purchase date and a last flow, and its two boundary decisions are the
tuple's too. The rule moves to `core/inflation/series.py` as a function over **the two dates a
rate is measured between**, which is what the two callers actually share: the projection passes
`(purchased_on, last contractual flow)` and the tuple passes `(span.start, span.end)`. The moved
docstring says *the month the money left* rather than *the purchase month* — for a tuple the two
are a ramp latency apart, and hard-wiring the purchase would start the window a month early on an
outlay made on the last day of a month. A unit test pins both boundaries and that straddle case,
and the existing hurdle goldens prove nothing moved.

**Phase 2 — the deflators reach the evaluation.** `Registries` gains `cpi: Mapping[str, CpiSeries]`
and `inflation: InflationAssumption | None`. The mapping rather than one series, because
`InflationDeclarations.series` is a mapping and nothing in the repository yet decides which one a
figure is real against — today only a golden test names the id, hard-coded.

**`Deflation.series` widens to that mapping too**, and this is the phase's one change to a 007
record. It is what keeps FR-013b true: the ambiguity refusal is then decided inside `_realized`,
*after* `real_terms` has hoisted the two refusals that apply to both halves, so a tuple with no
comparable rate still says *there is nothing to deflate* rather than *no series was named*. The
projection's caller passes the mapping instead of indexing it by a hard-coded id, and with one
series declared its figure is unchanged, which its golden asserts.

`AnswerDeclarations` carries the whole `InflationDeclarations` record — which is what
`manifest.inflation_input_refs` takes, and which already holds both declaring paths — and
`manifest.answer_input_refs` reads it from there. `api/answer.py` is not edited: it already hands
`declarations` to `of_answer`, and adding a second route for one fact is the duplication this
carries the record to avoid. Both `InputKind` members already exist (FR-012).
The `Ageing` the deflators are aged under is built at the call site from `registries.kinds` and
the run's `as_of`, exactly as the projection builds it — no new field carries it.

**Phase 3 — the figure, written test-first.** The worked example is written first and fails on a
missing field. `TupleOutcome` gains `real: RealTerms`; the single construction site in
`core/decision/tuple_outcome.py` calls `hurdle.real_terms` with the outcome's own provenance and
staleness, a `Deflation` built from `span` and the registries' two deflators, and `nominal=` the
`implied_rate` where it is a `NominalRate` and `None` where it is not — which is how FR-002's
*nothing to deflate* refusal is reached without a branch of its own. **No refusal is decided at
this site**: it builds the arguments and `real_terms` stays the only place a slot is filled.

**Phase 4 — nothing moved that should not.** Two answers differing only in the declared belief
are compared field by field, and the candidate golden is asserted byte-identical. Deliberately
before the exclusion is touched, so the ranking is proved unmoved on a diff that has changed only
the figure.

**Phase 5 — the exclusion the figure retires.** `Exclusion.NO_REAL_TERMS_FIGURE` and
`REAL_TERMS_SUPPLIED_BY` are deleted, `_answer_wide_excludes` returns one record, and
`tuple.EXCLUDES`'s *inflation (every figure here is nominal)* is replaced by the narrower claim
that survives: the amounts stay nominal and only the rate has a real counterpart (FR-015).
`ANSWER_WIDE` in the contract test shrinks to one member and
`test_no_real_terms_figure_appears_anywhere_in_the_result` is inverted to assert the figure's
presence on every evaluated outcome — the same walk, the opposite claim.

**Phase 6 — the digest, the schema and the prose.** `canonical.of_outcome` gains
`of_real_terms(value.real)`; the answer golden is regenerated and its diff read; the candidate
golden is asserted byte-identical, which is FR-018's whole content. The OpenAPI document picks up
the field with no hand-written model and `tests/contract/test_tags_and_unions.py` re-runs over the three
newly reachable records. `docs/METHODOLOGY.md` §27 gains the tuple's entry and §29.5 gains a
cross-reference to it. Then the full gate list.

## Which tests re-measure, and which are written by hand

| Test | How its figures are obtained |
|---|---|
| `tests/worked_examples/test_real_terms_on_a_tuple.py` | **by hand**, from the spec's worked example: the window 2026-10..2027-03, the nominal `0.14949567241454964`, the real `0.044996065831408805`, and the multiplication back |
| `tests/unit/test_deflation_window.py` | **by hand**: both boundaries of the moved rule, on dates chosen to straddle a month end |
| `tests/contract/test_the_real_figure_moves_no_order.py` | measured: two answers differing only in the declared belief, compared field by field except the real slots; the candidate survey's digest asserted equal to the recorded one |
| `tests/contract/test_the_answer_says_only_what_it_computed.py` | re-measured: `ANSWER_WIDE` loses a member and the real-terms walk inverts |
| `tests/unit/test_real_terms_refusals.py` | measured: no belief declared, no series declared, two series and neither named, `RateNotComparable`, and a span with no elapsed month — five named refusals, each asserted by its reason naming what is missing |
| `tests/golden/the_answer.golden.txt` | regenerated. **The rendering is unchanged**, so what moves is the `[digest]` line — `of_outcome` gains the real slot — and the two `[excludes]` lines becoming one. No `evaluated` line changes |
| `tests/golden/candidate_set.golden.txt` | **must not move**; byte-identity is the assertion |
| `tests/contract/test_no_subtraction_approximation.py` | re-run unchanged — its `SCANNED` tuple globs `core/inflation/` and names `hurdle.py` and `rates.py`, which is where every line this feature adds arithmetic to lives |

## Prose this change falsifies, and deletes

Named because each states as fact what the change stops honouring.
`Exclusion.NO_REAL_TERMS_FIGURE`'s docstring in full, with the member; and the sentence in
`TupleOutcome.implied_rate`'s docstring that leaves inflation to `EXCLUDES`.

Three things read as candidates and are **not** touched, checked rather than assumed.
`docs/METHODOLOGY.md` §29.5's *"The two figures"* is the amount and the rate, not the realized and
assumed pair, and stays true — §27.5 is the confusable one and is also untouched.
`core/results/fund.py::NOMINAL_ONLY` scopes its claim to a fund projection's own figures, which
gain no real slot. And 015's spec is not edited: a landed spec records what was true when it
landed, and 024's FR-014 is where the change is recorded.

## Decisions a reader will want the reason for

**The window comes from `span`, never from `horizon`.** A candidate that redeems before the
window's end has a shorter span, and deflating it over the horizon would charge it for months in
which the money was already back at the endpoint. The hurdle made the same choice for the same
reason and this is the same rule, now in one place.

**No new refusal *record*, and one new reason.** Five of the six states are ones 007 already
names — no series, no assumption, window not covered, no nominal figure, no elapsed month — and
each keeps its sentence. FR-013a's *more than one series and none named* is genuinely new and gets
a sixth named builder beside them in `core/results/hurdle.py`, returning the same
`RealTermsUnavailable` record and reached from inside `_realized`. No new type means no new wire
tag, which is what keeps `web/` untouched.

**`accounts_for` gains nothing.** The nominal rate is not net of inflation; a second figure is
reported beside it. Adding a line there would make the nominal figure read as deflated, which is
the exact confusion `NominalRate` and `RealRate` being unrelated types exists to prevent.

**The real figure is not passed to anything that orders.** It is written at the construction site
and read by renderers and the canonical form only. Nothing in `decision/compare.py` or
`decision/candidates.py` learns the field exists, which is what makes FR-017 a property of the
call graph rather than a rule someone has to keep.
