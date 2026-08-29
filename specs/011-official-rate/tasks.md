# Tasks: The official rate and the tax-currency role

**Feature**: `011-official-rate` | **Plan**: [plan.md](./plan.md) | **Model**: [data-model.md](./data-model.md)

Tests first throughout: a test written before its module and failing with `ImportError`
counts, and every task below that adds behaviour names the test that must fail first.
`[P]` marks tasks touching disjoint files.

## Phase 1 — Foundations: the core module (US1, US3)

- [x] **T001** `tests/official_rates.py` — synthetic fixtures: a series builder, an
  observation builder stamping `SourceRef.kind = "official_rate"`, an enumerated rule
  builder. Every citation says SYNTHETIC FIXTURE in its own text.
- [x] **T002** `tests/worked_examples/test_official_rate_base.py` — SC-001, SC-002, SC-012:
  hand arithmetic checked in beside each assertion, including a series quoting per 100 units.
  Fails with `ImportError`.
- [x] **T003** `tests/unit/test_official_rate_refusals.py` — SC-003: a gap in the middle, a
  date before the first observation, a date after the last, a series with no observations, a
  pair the series does not quote, and the inverse direction. The uncovered-date cases name the
  series, the pair and the date; the pair cases name both pairs and no date, because there is
  no date the question turned on. None returns a number.
- [x] **T004** `src/terezy/core/tax/official_rate.py` — the records, `strike_base`,
  `observation_for`, `covered_window`, `provenance_of`, and the two refusals. Makes T002–T003
  pass.
- [x] **T005** `tests/unit/test_official_rate_rule.py` — the enumerated rule applied in the
  core: `event_date` and `rate_date` both reported, `applied_rule` named; a rule that does not
  cover the date still refuses.

## Phase 2 — The declaration (US1, US4, US5)

- [x] **T006** `tests/contract/test_official_rate_declaration_loading.py` — SC-004's battery of
  broken files against a scratch data root, one case per load failure listed in
  data-model.md. Fails with `AttributeError` on the missing loader.
- [x] **T007** `data/observation_kinds.toml` — the `official_rate` kind, 7 days, with its note.
- [x] **T008** `src/terezy/data/declarations/schema.py` — `OfficialRateSeriesTable`,
  `OfficialRateObservationTable`, `NonPublicationRuleTable`, `NonPublicationDayTable`,
  `OfficialRateFile`; `TimingTable` gains `official_rate_series: str | None = None`.
- [x] **T009** `src/terezy/data/declarations/loader.py` — `official_rate_from_file`, every
  refusal naming file and field; `TimingDeclaration` carries the series reference.
- [x] **T010** `src/terezy/data/declarations/resolver.py` — `OFFICIAL_RATES_DIR`,
  `official_rates_from_data_root`, the duplicate-identity refusal naming both files, and the
  `official_rate_series` reference check including "the series' price currency is this
  jurisdiction's tax currency".
- [x] **T011** [P] `scripts/check_provenance.py` — `official_rates` in `SOURCED_DIRS`,
  `quotation_unit` in `STRUCTURAL_KEYS`, each with its reason in the comment beside it.
- [x] **T012** `data/official_rates/ua_nbu_usd.toml` — identity only. Header states: no
  observation is declared, values arrive from the publisher through the fetch script
  (`provider-automation`), the file is not hand-edited, and no non-publication-day rule is
  declared because declaring it needs `declared-working-day-calendar` (FR-017, FR-018).
- [x] **T013** `data/tax/timing/ua.toml` — `official_rate_series = "ua_nbu_usd"`.
- [x] **T014** `tests/contract/test_official_rate_data_only.py` — SC-011: a second series with
  a distinct identity loads and is addressable from a scratch root, zero source lines changed;
  and SC-015: a synthetic series declaring an enumerated rule produces the applied-date output,
  also zero source lines changed.
- [x] **T015** `tests/contract/test_ua_series_refuses.py` — SC-014, against the **shipped**
  file: it loads, declares no rule, and a base struck on a date it does not cover refuses. The
  docstring states that the shipped series declares no observations, so this is what ships and
  not a demonstration of a published window with holes in it.

## Phase 3 — The strike (US1, US2, US4)

- [x] **T016** `tests/unit/test_tax_base_in_the_tax_currency.py` — a foreign coupon charge
  assessed through `tax.year.statements` comes back with a hryvnia base and a `ChargeRef`
  naming the series, the rate, its date and the quotation unit (FR-016); a hryvnia charge comes
  back with `conversion is None` and no rate-unavailable reason (SC-010); a foreign **disposal**
  gain refuses naming `fx-tax-asymmetry-f1` (research D3).
- [x] **T017** `src/terezy/core/tax/year.py` — `AssessmentRules.official_rate`,
  `ChargeRef.conversion`, `TaxCurrencyConversionUnavailable.unavailable`,
  `ForeignGainNotStruckPerDate`, and `_items` doing the conversion. `total` recomputed as
  `add(pit, levy)`.
- [x] **T018** `src/terezy/data/declarations/resolver.py` — `tax_rules_from_data_root` passes
  the resolved series into `AssessmentRules`.
- [x] **T019** `tests/contract/test_official_rate_marks.py` — SC-005 and SC-006: an unverified
  rate marks the base, the charge and the liability; a marked amount survives a verified rate;
  an observation aged past 7 days reports staleness naming the observation and the threshold
  through `staleness_of_sources`; a fresh one reports none.
- [x] **T020** `tests/contract/test_tax_declaration_loading.py` — update the foreign-currency
  case. **What landed differs from what this task predicted**: that ledger's taxable result is
  a realised *gain*, so the class is now `TestAForeignCurrencyDisposalGainRefuses` and it
  asserts `ForeignGainNotStruckPerDate` naming `fx-tax-asymmetry-f1` — a refusal that consults
  no series and so names none (research D3).
- [x] **T021** `src/terezy/core/results/tuple.py`, `src/terezy/core/decision/tuple_outcome.py`
  — the prose and the refusal text stop saying the official rate is what is missing, because
  after this feature it is not. Pinned by a test that asserts what the refusal now names.

## Phase 4 — The standing properties (US2)

- [x] **T022** `.importlinter` — two contracts,
  `official-rate-never-prices-a-leg` (FR-012) and `no-tax-base-from-a-channel` (FR-013).
- [x] **T023** `tests/contract/test_architecture_boundaries.py` — both contract names added to
  the pinned list, so deleting one is a test failure.
- [x] **T024** `tests/contract/test_the_rate_you_are_taxed_at.py` — SC-007 (one dollar amount
  through a declared channel and through the official rate on deliberately different dates and
  rates: two figures, separately labelled, never equal by construction), SC-008 (both
  directions asserted over executable source, prose stripped) and SC-009 (research D11: the
  absence of any display choice the tax base could read, with the date measured).

## Phase 5 — Documentation and the graph

- [x] **T025** `docs/METHODOLOGY.md` — a new section: what the tax base is in plain language,
  the date-selection rule, the quotation unit, the worked example from T002, and what refuses.
  In this change, not a follow-up (SC-013). `uv run python scripts/check_methodology_refs.py`.
- [x] **T026** `docs/REQUIRED_TESTS.md` — F1's note narrowed to its remaining blocker; F2 and
  F3 left open with what 011 established and what it did not; F5 untouched.
- [x] **T027** `specs/features.toml` — 011 `in-progress` then `done` at landing;
  `fx-tax-asymmetry-f1`'s note narrowed.
- [x] **T028** `specs/011-official-rate/quickstart.md`.

## Phase 6 — Close

- [x] **T029** Full gates: `ruff check` + `ruff format --check`, `mypy`, `pytest --cov`,
  `lint-imports`, `check_provenance.py`. Any golden whose recorded digest moves is regenerated
  deliberately with the changed lines quoted in the commit message.
- [x] **T030** `/condense` over the branch diff, then `/code-review` until clean.

---

## What the plan did not predict

Recorded because the next feature to touch this area will meet the same three things.

- **The conversion could not go where User Story 1 reads as putting it.** Story 1 says *"when
  the charge is computed"*, which points at `core.results.project`, where `TaxContext` is
  built. That site cannot take it: `project` folds a holding under `declaration.currency` and
  sums `charge.total` in it, so a hryvnia charge inside a dollar projection is a
  `CurrencyMismatchError` before any rate is consulted. The strike is in
  `core.tax.year._in_tax_currency` instead (research D2), and the consequence is that a
  `TaxCharge` may leave `flat_rate` denominated in a foreign currency — which is now stated at
  the `TaxRule` interface, where two docstrings had claimed the opposite since feature 001.

- **A realised gain must not be converted, and the spec does not say so.** FR-007's subject is
  *"that event's own amount"*, and a gain is not one. Striking it at the disposal date's rate
  reports zero hryvnia for a position flat in dollars across a devaluation — deleting the
  gain required test F1 exists to find. It is refused by name (research D3). This narrowed
  `fx-tax-asymmetry-f1` from "needs a taxable foreign instrument" to two specific things.

- **Five review rounds, and three of them found prose written to fix false prose.** A count
  corrected to another wrong count; a remedy prescribed through an interface that cannot
  reach it; a refusal promising to name a series that does not exist. Every one was in a
  sentence less than an hour old. The lesson the branch acted on: a claim about behaviour gets
  executed before it gets committed, or it does not get written.
