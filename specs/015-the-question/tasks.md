# Tasks: The question, and the answer that refuses in parts

**Feature**: `015-the-question` | **Date**: 2026-08-31

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md),
[data-model.md](./data-model.md)

Test-first throughout: every `T*` marked **(test)** lands before the `T*` it names, and must fail
without it — a test failing with `ImportError` counts. `[P]` marks tasks with no dependency on
each other. Every **Checkpoint** is a `/commit` through the skill with every gate green.

---

## Phase 1 — the group vocabulary (FR-007a, research D1/D2)

- [ ] **T001 (test)** `tests/contract/test_group_declaration_loading.py` — `data/groups.toml`
      loads; a duplicate group id, an empty id and an unknown field each refuse naming the file
      and the field. An instrument naming an undeclared group refuses naming the file and the
      field; an instrument naming one twice refuses. A `groups` key absent from an instrument
      refuses (D2).
- [ ] **T002** `src/terezy/core/instruments/groups.py` — `InstrumentGroup`.
- [ ] **T003** `src/terezy/core/instruments/interface.py`, `fund.py` — `groups: tuple[str, ...]`
      on both declaration records.
- [ ] **T004** `src/terezy/data/declarations/schema.py` — `GroupsFile`, `GroupTable`, `groups` on
      `InstrumentTable` and `FundTable`.
- [ ] **T005** `src/terezy/data/declarations/loader.py` — `groups_from_file`, and `groups=` at
      the three declaration construction sites.
- [ ] **T006** `src/terezy/data/declarations/resolver.py` — `Declarations.groups`, the
      cross-file check that every label names a declared group.
- [ ] **T007** `data/groups.toml` — `ovdp` and `inzhur`, with the argument for the vocabulary in
      the file's own header.
- [ ] **T008** `data/instruments/*.toml` — `groups` on all nine, per *The measurement* item 4.
- [ ] **T009** repair every construction site of the two declaration records in `tests/`.

- [ ] **T010 (test)** `tests/contract/test_group_membership_is_declared.py` — SC-032: an
      instrument whose class, id prefix, tax class and `bought_at` all suggest `ovdp` and whose
      `groups` is empty is in **no** group. One assertion per attribute, so the test fails if any
      is ever consulted.

**Checkpoint**: gates green, commit. The vocabulary exists and nothing infers it.

---

## Phase 2 — 014's declared subject set (FR-008)

- [ ] **T011 (test)** `tests/unit/test_candidate_subject_set.py` — a `Question` whose `subjects`
      names a subset of the registry enumerates only those pairs; `pairs_considered` counts the
      narrowed set; an id in `subjects` that the registry does not declare is not a candidate and
      does not raise.
- [ ] **T012** `src/terezy/core/results/candidates.py` — `Question.subjects: frozenset[str]`.
- [ ] **T013** `src/terezy/core/decision/candidates.py` — `_considered` narrowed to
      `question.subjects`.
- [ ] **T014** `tests/candidate_registries.py` and every 014 suite — supply `subjects`.

**Checkpoint**: gates green, commit.

---

## Phase 3 — the early exit (FR-029, FR-031, FR-032, FR-033)

- [ ] **T015 (test)** `tests/contract/test_early_exit_declaration.py` — the spread-holds file
      loads; an absent directory, two files, `is_assumption = false`, an empty rationale and an
      unknown field each refuse naming the file and the field (SC-024's second half).
- [ ] **T016** `src/terezy/core/scenarios/early_exit.py` — `SpreadHolds`.
- [ ] **T017** `schema.py`, `loader.py`, `resolver.py` — `EarlyExitFile`,
      `early_exit_from_file`, `EarlyExitDeclarations`, and the single-file resolution.
- [ ] **T018** `data/scenarios/early_exit/owner-001.toml` — the belief, its rationale, and the
      argument for it in the file's own header.

- [ ] **T019 (test)** `tests/contract/test_resale_price_declaration.py` — an
      `[access.resale_price]` loads; a currency other than the instrument's, a non-positive
      price and a missing citation key each refuse naming the file and the field.
- [ ] **T020** `src/terezy/core/instruments/access.py` — `resale_price: VenueQuote | None`.
- [ ] **T021** `schema.py`, `loader.py`, `resolver.py` — parse and check it.

- [ ] **T022 (test)** `tests/worked_examples/test_early_exit_sale.py` — a fixture bond with a
      declared resale price, sold at `horizon.end`: the arithmetic on paper — units × resale
      price, the coupons up to `horizon.end` and no others, the realised gain against basis, the
      tax the disposal class charges — checked in beside the assertion.
- [ ] **T023** `src/terezy/core/instruments/interface.py` — `EarlyExit`, and `EventsFn` widened
      by one required keyword-only argument.
- [ ] **T024** `src/terezy/core/instruments/fixed_income.py` — coupons after `horizon.end`
      dropped, the sale at `horizon.end`, and `InconsistentTerms(second_term="access.resale_price")`
      where no price is declared.
- [ ] **T025** `src/terezy/core/instruments/enumerated.py` — the same, over declared payments.
- [ ] **T026** `src/terezy/core/ledger/events.py` — `CausationKind.ACCESS_TERM`, and
      `EventKind.REDEMPTION`'s docstring widened from *fund units* to *units*.
- [ ] **T027** `src/terezy/core/results/project.py` — `early_exit` threaded to `ops.events`.
- [ ] **T028** `src/terezy/core/decision/tuple_outcome.py` — `Registries.spread_holds`; the
      `EarlyExit` built from the access declaration; `_bond_outcome`'s new arm returning
      `DeclarationMissing(part="access", what="access.resale_price")`; `rests_on` naming the
      assumption.

- [ ] **T029 (test)** `tests/unit/test_early_exit_refusals.py` — SC-023: every candidate that
      dropped as `CannotSpanHorizon` with `binding_term = "instrument.maturity_date"` under the
      baseline now refuses for the missing resale price, naming the instrument and the term;
      derived from the registry the test loads. `TupleRefused` still has seventeen members.

**Checkpoint**: gates green, commit. 010 sells at the horizon's end and says what it is missing.

---

## Phase 4 — the question declaration (FR-001 to FR-006, FR-026)

- [ ] **T030 (test)** `tests/contract/test_question_declaration_loading.py` — SC-005 and SC-029,
      one assertion per case: unknown field, missing field, duplicated subject, two identical
      horizons, no horizon, no subject, an amount whose currency its stream does not declare, an
      amount for an undeclared stream, a declared stream with no amount (for a stream that yields
      candidates **and** for one that yields none), a benchmark outside the subjects, both
      `subjects` and the every-instrument token, neither.
- [ ] **T031** `src/terezy/core/results/question.py` — `Question`, `NamedSubject`, `Reserve`.
- [ ] **T032** `schema.py` — `QuestionFile` and its tables, including the two plan shapes.
- [ ] **T033** `loader.py` — `question_from_file`.
- [ ] **T034** `resolver.py` — `AnswerDeclarations` (the candidate declarations, the questions,
      the groups and the spread-holds belief), and `answer_from_data_root`.
- [ ] **T035** `scripts/check_provenance.py` — `data/questions/` in `EXEMPT_DIRS`, with its
      reason (FR-003).
- [ ] **T036** `data/questions/fifty-thousand.toml` — the owner's own question, per *The
      measurement* item 5 and owner verification task 3.

**Checkpoint**: gates green, commit. The question is an artefact.

---

## Phase 5 — the answer records (FR-009 to FR-024)

- [ ] **T037 (test)** `tests/unit/test_answer_records.py` — the shapes are frozen; the three
      subject standings are three types; `Refused` is disjoint from `Answer`; the exclusion set
      is closed and its three FR-033 members carry a direction on exactly two.
- [ ] **T038** `src/terezy/core/results/answer.py` — every record in
      [data-model.md](./data-model.md). No function, no figure.

**Checkpoint**: gates green, commit.

---

## Phase 6 — the verb (FR-007 to FR-023, FR-027, FR-028)

- [ ] **T039 (test)** `tests/worked_examples/test_the_owners_question.py` — SC-001, SC-002: the
      shipped question answered at `as_of` 2026-08-30 produces three sections, **7** candidates
      enumerated in each, no ranking in any, `cash` and `btc` in the undeclared population, and
      every count derived from the labels and declarations the test loads.
- [ ] **T040** `src/terezy/core/decision/answer.py` — `answer`, subject resolution, plan
      expansion, the per-section survey, the standings, and the derived readings.

- [ ] **T041 (test)** `tests/unit/test_answer_refuses_in_parts.py` — SC-009, SC-010, SC-011,
      SC-020: a battery over every member of 014's `EnumerationRefused` and `SurveyRefused` and
      010's `BenchmarkUnavailable`, each planted in one section; the answer stands and exactly one
      section carries the planted refusal unmodified. Two `Refused` cases produce no answer.
- [ ] **T042 (test)** `tests/unit/test_answer_sections_align.py` — SC-012, SC-013: the three
      sections' candidate sets are equal by key on the shipped registry; a fixture where they
      differ reports a finding; the cross-horizon reading recomputed equals the reading reported.
- [ ] **T043 (test)** `tests/unit/test_subject_counts.py` — SC-030, SC-031, SC-033: an instrument
      in two named groups counted once while both subjects are still named, with the group size
      deliberately different from the named-subject count; an instrument declaration naming an
      undeclared group fails at load while a question naming an undeclared word does not; and the
      SC-033 pair — the same added instrument without and with the label.
- [ ] **T044 (test)** `tests/unit/test_reserve_verdicts.py` — SC-014, SC-015: a reserve one day
      before and one day after a qualifying arrival flips the verdict, and the candidate is
      present, evaluated and ranked identically in both; a reserve in a currency the arrivals do
      not deliver is *a partial exit would be needed* and consults no rate.
- [ ] **T045 (test)** `tests/unit/test_money_arrives_after_horizon.py` — SC-027: `inzhur_miltech`
      at a one-month horizon is in no evaluated population and the section carries the typed
      part-refusal naming it and the date its money arrives; the section ranks nothing.
- [ ] **T046 (test)** `tests/unit/test_owner_stated_exchange_rate.py` — SC-028: a question
      carrying an owner-stated rate on `inzhur_reit`'s plan evaluates where the baseline produces
      `PegUnsizable`; removing it returns the refusal naming `FundAssumptions.exchange_rate`.
- [ ] **T047 (test)** `tests/unit/test_cross_currency_candidate.py` — SC-016: a fixture registry
      declaring the inbound USD corridor produces a candidate funded from `contract_usd` whose tax
      figure drops as `TaxCurrencyConversionUnavailable` naming the empty series.
- [ ] **T048** fixes to `core/decision/answer.py` for T041–T047.

**Checkpoint**: gates green, commit. The verb answers.

---

## Phase 7 — the manifest (FR-025, D12, row H3)

- [ ] **T049 (test)** `tests/unit/test_answer_manifest.py` — SC-007 and SC-008: every file under
      `data/` the run read appears in the manifest with its SHA-256, walked from the loader's
      inputs rather than sampled; the question's own file is among them; editing any one file
      moves exactly one digest.
- [ ] **T050** `src/terezy/data/manifest.py` — `as_of`, `regime_id`, `ProjectedRun`, the widened
      `InputKind`, and `of_answer`.
- [ ] **T051** repair 001's manifest suite and any golden the reshape moves, with the changed
      lines quoted in the commit message (Principle V).

**Checkpoint**: gates green, commit.

---

## Phase 8 — the api entry point and the CLI (FR-020a, FR-020b, SC-019, SC-022)

- [ ] **T052 (test)** `tests/contract/test_cli_builds_the_same_record.py` — SC-019: a question
      built from flags equals one loaded from the equivalent file, field for field; the scan
      asserts the CLI declares no option expressing a question field the file cannot express,
      exempting `--as-of`, the segment bound and the candidate ceiling by name.
- [ ] **T053 (test)** `tests/contract/test_cli_renders_every_refusal.py` — SC-022: rendering the
      owner's answer produces output in which each of the three sections' refusal reasons appears
      by its own text; no blank, no dash, no zero, no omitted row.
- [ ] **T054** `src/terezy/api/answer.py` — load, call once, attach the manifest.
- [ ] **T055** `src/terezy/cli/main.py` — one subcommand, `argparse`, rendering only.
- [ ] **T056** `pyproject.toml` — one console script.

**Checkpoint**: gates green, commit.

---

## Phase 9 — the scans, the golden, and the docs

- [ ] **T057 (test)** `tests/contract/test_answer_composes_no_prose.py` — SC-003: a walk over the
      whole result asserts every string is an id, a date, or a byte-for-byte copy of a string a
      core record it carries already held.
- [ ] **T058 (test)** `tests/contract/test_answer_derives_no_rate.py` — SC-004: no module of this
      feature imports `core.tax.official_rate` or derives a rate; scoped so FR-021a's declared
      assumption is not caught.
- [ ] **T059 (test)** `tests/contract/test_answer_marks_survive.py` — SC-017, SC-025: a walk over
      the whole result asserts every figure derived from an unverified or synthetic declaration
      carries the mark where it is reported, and every figure computed through the spread-holds
      assumption names it.
- [ ] **T060 (test)** `tests/contract/test_answer_states_its_exclusions.py` — SC-021, SC-026: the
      exclusions and the absences are checked against each other; a direction is present on
      exactly two of FR-033's three claims and absent on the rate-risk one.
- [ ] **T061 (test)** `tests/golden/test_the_answer.py` + `the_answer.golden.txt` — SC-018: the
      owner's question and its whole answer over the shipped registry, provenance excluded from
      the digest.
- [ ] **T062** `docs/METHODOLOGY.md` — the early-exit figure, its formula and what it excludes.
- [ ] **T063** `docs/REQUIRED_TESTS.md` — H3 flipped with its two test paths; the notes for the
      rows this feature reinforces without closing.

**Checkpoint**: gates green, commit. Then `/condense`, then `/code-review` until clean.
