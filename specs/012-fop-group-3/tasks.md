# Tasks: The ФОП group 3 regime

**Feature**: `012-fop-group-3` | **Plan**: [plan.md](./plan.md) | **Model**: [data-model.md](./data-model.md) | **Contract**: [contracts/taxation-scheme-declaration.md](./contracts/taxation-scheme-declaration.md)

Tests first throughout: a test written before its module and failing with `ImportError`
counts, and every task below that adds behaviour names the test that must fail first. `[P]`
marks tasks touching disjoint files.

**Story labels**: US1 the charge on the credit-date base; US2 the stream names a regime;
US3 the commencement date; US4 a scheme is a set of components; US5 the mandatory sale;
US6 a second regime is data.

---

## Phase 1 — Setup

- [x] **T001** `tests/schemes.py` — synthetic fixtures for the whole feature: a scheme builder,
  a rate-component builder, a periodic-component builder, a destination builder and a reading
  builder, every citation saying SYNTHETIC FIXTURE in its own text and every `verified_on`
  empty by default. No fixture reuses a shipped id.

---

## Phase 2 — Foundational: the scheme in the core (US1, US3, US4)

**Blocking.** Nothing else in the feature can be written against a scheme that does not exist.

- [x] **T002** [US1] `tests/worked_examples/test_fop_scheme_charge.py` — SC-001: a synthetic
  monthly dollar amount credited on a known date, a synthetic official rate for that date, the
  hryvnia base and both component charges checked against arithmetic written out beside the
  assertion; and the tax-currency case, where a hryvnia arrival is charged with
  `conversion is None` and no series consulted. Fails with `ImportError`.
- [x] **T003** [P] [US3] `tests/unit/test_scheme_refusals.py` — income before a rate
  component's earliest entry names the component and the date and is neither a zero nor a
  charge with the line absent; a credit date the series does not cover carries 011's own
  refusal whole; a series quoting another pair; a jurisdiction with no series at all. Fails
  with `ImportError`.
- [x] **T004** [P] [US4] `tests/unit/test_periodic_component.py` — a period with zero income
  still charges the periodic component; a declared zero is charged as a zero **carrying its
  provenance**; a period with no amount in force refuses naming the period; and the three
  nils of `component_standing` come back as three distinct types. Fails with `ImportError`.
- [x] **T005** `src/terezy/core/tax/scheme.py` — `Verdict`, `ComponentRate`,
  `ComponentAmount`, `DeclaredContext`, `RateComponent`, `PeriodicComponent`,
  `TaxationScheme`, `ComponentCharge`, `SchemeCharge`, `PeriodicCharge`, the four refusals,
  `rate_in_force`, `amount_in_force`, `charge_income`, `charge_period`, `charge_periods`,
  `component_standing`. Makes T002–T004 pass. The module docstring states the seam that would
  force a merge with `TaxCharge` (research D4) and nothing else about another module.

---

## Phase 3 — The declaration (US1, US2, US3, US6)

- [x] **T006** [US6] `tests/contract/test_scheme_declaration_loading.py` — SC-006's battery
  against a scratch data root, one case per rule in the contract: empty schedule, duplicate
  effective date, out-of-order entries, negative rate, negative amount, duplicate scheme id
  across files, duplicate component id within a scheme, unknown `period`, unknown
  `declared_for`, unknown currency, a scheme charging no component at all, a context block
  with no `not_applied_because`. Every case names the file and the field; no case substitutes
  a default. Fails with `AttributeError` on the missing loader.
- [x] **T007** `src/terezy/data/declarations/schema.py` — `SchemeTable`,
  `RateComponentTable`, `ComponentRateTable`, `PeriodicComponentTable`,
  `ComponentAmountTable`, `DeclaredContextTable`, `SchemeFile`.
- [x] **T008** `src/terezy/data/declarations/loader.py` — `scheme_from_file`, the schedule
  folds shared between the two component kinds, `_as_fraction` applied exactly once outside
  the non-negative check, every refusal naming file and field path by component id.
- [x] **T009** `src/terezy/data/declarations/resolver.py` — `SCHEMES_DIR = "tax/schemes"`,
  `SchemeDeclarations`, `schemes_from_data_root(root, *, base_currency)` composing
  `ramp_from_data_root`, and the duplicate-identity refusal naming both files.
- [x] **T010** [US1] `data/tax/schemes/ua_fop_group_3.toml` — єдиний податок 5% effective
  2016-01-01 (FR-009; dated by `data/tax/ua.toml`'s own **Rule B2**, which the entry's note
  states, with owner verification task 1 named); військовий збір 1% effective 2025-01-01 with
  the **rate** cited to № 4015-IX and the **commencement** cited to № 4113-IX and 4015-IX
  cited for neither date (FR-008), and its termination as a `context` block cited to
  № 4835-IX (FR-008a); ЄСВ as a periodic component declared explicitly at zero, sourced to the
  owner's own statement of 2026-08-23, `verified_on` empty (FR-021). Every quotation copied
  from `spec.md`; nothing retrieved.
- [x] **T011** [P] `data/tax/schemes/ua_personal_income.toml` — `declared_for = "reading"`:
  ПДФО 18% effective 2022-09-19 under FR-009's own fallback rule with the inference recorded
  **on the entry** and owner verification task 5 named (FR-010a); військовий збір 5% effective
  2024-12-01 with its event-conditioned reversion as a `context` block (FR-010). Declares no
  ЄСВ component at all. The header states that this is **one** declaration consumed by every
  personal-income reading and copied by none, and that no stream may name it.
- [x] **T012** [US2] `tests/contract/test_scheme_declaration_loading.py` (same module) — the
  **shipped** root: both schemes load, the ФОП scheme's ЄСВ nil is a declared zero carrying
  the owner as its source and an empty verification date, and the personal-income scheme
  declares no ЄСВ component, so `component_standing` returns *not charged by this scheme* on
  shipped data rather than only on a fixture.

---

## Phase 4 — Where the income is credited (US1, US6)

- [x] **T013** [US1] `tests/unit/test_crediting_destinations.py` — an INTERPRETED destination
  produces a charge carrying the row's grounds and citations; an UNSETTLED one produces a
  switch whose figure count is the number of computable readings; a reading naming a date the
  caller did not supply refuses naming the reading and the date name; a reading whose rate
  schedule does not reach its date refuses rather than being dropped from the switch; a venue
  with no row refuses in `NO_DECLARED_JUDGEMENT` naming both closures; a row whose every
  candidate is uncomputable refuses in `NO_CANDIDATE_IS_COMPUTABLE` naming them. Fails with
  `AttributeError`.
- [x] **T014** `src/terezy/core/tax/scheme.py` — `Reading`, `CreditingDestination`,
  `ChargedUnderTheScheme`, `ReadingFigure`, `UncomputableCandidate`, `UnsettledDestination`,
  `RefusedState`, `CreditingDestinationRefused`, `ReadingDateUndeclared`, `ReadingRefused`,
  and `apply`. Makes T013 pass.
- [x] **T015** [P] `tests/contract/test_crediting_destination_loading.py` — the contract's
  destination rules against a scratch root: a reading declaring both `scheme` and
  `uncomputable_because`, one declaring neither, an INTERPRETED row with two readings, an
  INTERPRETED row whose one reading is uncomputable, an UNSETTLED row with no readings, a row
  with empty `grounds`, a row whose venue is undeclared, a row whose scheme is undeclared, a
  duplicate `(scheme, venue)` pair across two files, a reading naming a scheme with
  `recognised_on` absent.
- [x] **T016** `src/terezy/data/declarations/schema.py`, `loader.py`, `resolver.py` —
  `DestinationTable`, `ReadingTable`, `DestinationFile`; `destinations_from_file`;
  `DESTINATIONS_DIR = "tax/destinations"` and the venue/scheme cross-checks in
  `schemes_from_data_root`.
- [x] **T017** `data/venues.toml` — `payoneer` and `foreign_bank_usd`, each with a note saying
  what it is, that it exists because the tax question reaches it, and that no route is
  declared to or from it (research D13).
- [x] **T018** `data/tax/destinations/ua.toml` — the normative table, five rows, each carrying
  the recorded judgement and the citations `spec.md` states for it: `fop` INTERPRETED with one
  reading; `payoneer` UNSETTLED with three, the НБУ one carrying `departs_from_source`;
  `monobank_uah` UNSETTLED with one; `coinbase` UNSETTLED with one; `foreign_bank_usd`
  UNSETTLED with two. The header says the verdicts are expected to move and points at
  `features.toml`'s `crediting-destination-verdicts` and at owner verification task 6 — it
  does **not** restate a verdict's history, which is `spec.md`'s register's job.
- [x] **T019** [US6] `tests/contract/test_scheme_data_only.py` — SC-012 and SC-004: a second
  synthetic scheme with a different component set, different schedules and a periodic
  component the first does not have produces complete results from a scratch root with zero
  source lines changed; a legislated change entered as one dated entry takes effect in the
  next run; and a destination row moved from `unsettled` to `interpreted` changes the outcome
  with zero source lines changed.

---

## Phase 5 — The stream migration (US2)

- [x] **T020** [US2] `tests/unit/test_deployable_capacity.py` — rewritten for the new shape.
  SC-005: the undeclared case still yields a result with **no net field at all**, its reason
  names the missing declaration, and no net figure quietly equals a gross one; the declared
  case is net of the scheme's charges with every term of `gross − charged = net` reachable;
  passing a charge for a stream that names no scheme, and omitting one for a stream that does,
  both raise.
- [x] **T021** [US2] `src/terezy/core/streams/streams.py` — `income_tax_rate` retired;
  `credited_to` and `tax_scheme` added; `DeployableCapacity` and `TaxTreatmentUndeclared`
  rewritten; `deployable` takes the charge. The module docstring's provenance section is
  rewritten: a stream no longer carries any legal rate, so the `money.scale` argument it makes
  no longer applies to one — the charge's own lines go through `scale_sourced` in
  `core/tax/scheme.py`.
- [x] **T022** `src/terezy/data/declarations/schema.py`, `loader.py`, `resolver.py` —
  `StreamTable` loses `income_tax_rate_pct` and gains `credited_to` (required) and
  `tax_scheme` (optional); `_stream` builds them; the venue check covers `credited_to`; the
  treatment check refuses a stream naming an unknown scheme or one whose `declared_for` is
  `"reading"`, naming the file, the stream and the treatment (FR-017).
- [x] **T023** [P] [US2] `tests/contract/test_declaration_loading.py`,
  `tests/contract/test_route_declaration_loading.py`, `tests/composed_registries.py`,
  `tests/coverage_registries.py`, `tests/diagram_registries.py`,
  `tests/invariants/route_graphs.py`, `tests/tuple_registries.py`,
  `tests/unit/test_stream_venue_mismatch.py` — every stream fixture and every stream
  declaration in a test gains `credited_to`; the `income_tax_rate_pct` cases become
  `tax_scheme` cases or are deleted with the reason.
- [x] **T024** [US2] `data/streams/owner-001.toml` — `income_tax_rate_pct` removed from both
  streams; `credited_to = "monobank_uah"` on the salary and `credited_to = "fop"` with
  `tax_scheme = "ua_fop_group_3_non_vat"` on the contract income. The header's paragraph
  arguing the omitted rate is replaced by the two facts that are now declared and why neither
  is inferred from the other.
- [x] **T025** [US2] `tests/contract/test_declaration_loading.py` — SC-013a: the shipped
  contract stream's routing origin and crediting destination differ and it charges under
  FR-025 rather than refusing; a stream declaring only one of the two fails at load naming the
  missing field.
- [x] **T026** [P] `data/README.md` and `scripts/check_provenance.py` — the `streams/` row and
  the exemption argument stop covering a legal rate and say what the exemption now covers; the
  script's `EXEMPT_DIRS["streams"]` reason no longer names a field that does not exist. Add
  the `tax/schemes/` and `tax/destinations/` subdirectories to the `tax/` row (FR-018).

---

## Phase 6 — The mandatory sale, and the two figures (US5)

- [x] **T027** [US5] `tests/worked_examples/test_base_versus_received.py` — SC-009: one
  credited amount, the hryvnia received produced by the **existing** costing path over the
  shipped `fop_usd_to_monobank_uah` route, the hryvnia base struck from the official rate;
  recomputing with the sale executed at a different market rate leaves the base bit-identical;
  the difference is signed and carries the not-part-of-the-base label on its face. Fails with
  `AttributeError`.
- [x] **T028** [US5] `src/terezy/core/tax/scheme.py` — `BaseVersusReceived` and
  `base_versus_received`, taking two `Money` and importing nothing from `core.routes`
  (research D15).

---

## Phase 7 — The standing properties (US4, US6)

- [x] **T029** `tests/contract/test_no_scheme_is_named_in_code.py` — SC-002's no-branch clause
  and SC-011: an AST scan over `src/terezy/**/*.py` executable source finds no scheme id, no
  component id, no component name, no destination venue id and no declared date name; the scan
  names the modules it walked and proves itself falsifiable on a planted branch and inert on
  planted prose.
- [x] **T030** [P] `tests/contract/test_readings_never_blend.py` — SC-017 and SC-017a:
  `UnsettledDestination` has no `Money` field, no `total` and no aggregate of any kind,
  asserted by enumerating `dataclasses.fields`; a figure lifted out of the tuple still names
  its reading and carries its citations; `ChargedUnderTheScheme` and `ReadingFigure` are
  unrelated records; an AST containment scan pins which modules may construct a `ReadingFigure`
  and how many sites do, counting `dataclasses.replace`; the personal-income components are
  **one** declaration consumed by every reading that needs them, asserted by identity of the
  resolved scheme object rather than by equality of its rates; the НБУ reading reports its
  `departs_from_source` on the figure; and the shipped counts are three, two, one and one.
- [x] **T031** [P] `tests/contract/test_provenance_propagation.py` — SC-007 and SC-008: no tax
  rate this feature consumes lives in per-owner data; exactly one shipped value is sourced to
  the owner's own statement and it marks every figure it touches; an unverified rate or
  official-rate observation marks 100% of charges derived from it, in both directions.

---

## Phase 8 — Documentation and the graph

- [x] **T032** `docs/METHODOLOGY.md` — §13 rewritten for the new deployable formula (FR-018),
  and a new §33: the scheme and its components, the credit-date base, the periodic component,
  the three nils, a worked example of each, the crediting destination and its labelled switch,
  base against received, and what refuses. In this change, not a follow-up (SC-015). Then
  `uv run python scripts/check_methodology_refs.py`, **read by exit code**.
- [x] **T033** [P] `docs/REQUIRED_TESTS.md` — E10's second exercise recorded beside its row
  (income, against a real statute) without re-flipping it; E8 left open with its structural
  prerequisite named; E7, E4, F1 and G6 left as they are, each with a sentence on what this
  feature did and did not do to them.
- [x] **T034** [P] `specs/features.toml` — 012 `in-progress`, and `done` only at landing.
- [x] **T035** [P] `specs/002-ramp-cost/spec.md` — a ⚙ cross-reference on FR-007 recording that
  this feature supersedes it (FR-018, the pattern 007 used for 001's FR-022).

---

## Phase 9 — Close

- [ ] **T036** Full gates, each **read by exit code**: `ruff check` and `ruff format --check`,
  `mypy`, `pytest --cov`, `lint-imports`, `check_provenance.py`, `check_methodology_refs.py`.
  Any golden whose recorded input digest moves — the coverage golden is the expected one, from
  the two new venues — is regenerated deliberately with the changed lines quoted in the commit
  message.
- [ ] **T037** `/condense` over the branch diff: one fact, one place, in prose and in code,
  re-reading every comment the branch touched.
- [ ] **T038** `/code-review` over the diff that will actually land, iterating until clean.

---

## Dependencies

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 ─┐
                         └→ Phase 5 ───┼→ Phase 7 → Phase 8 → Phase 9
                            Phase 6 ───┘
```

- **Phase 2 blocks everything**: there is no scheme to declare, point at, or apply until it exists.
- **Phase 4 needs Phase 3**: a reading names a scheme, so schemes must resolve first.
- **Phase 5 needs Phase 4**: `deployable` takes a `ChargedUnderTheScheme`, which `apply` produces.
- **Phase 6 is independent of Phases 4 and 5** and may run beside them: it needs only a struck base.
- **Phase 7 needs every record to exist**, because its assertions are over the record set and over the source tree.

## Parallel opportunities

- T003 and T004 are two test modules over one module that does not exist yet — write both before T005.
- T011 beside T010; T015 beside T013.
- Within Phase 7 all three modules are disjoint.
- Within Phase 8 all four files are disjoint.

## Independent test criteria

| Story | Proven by |
|---|---|
| US1 | T002, T013 — hand arithmetic on a synthetic amount and rate; both charges, the base, the rate and the date it belongs to |
| US2 | T020, T025 — 002's undeclared case survives verbatim; a declared treatment nets the regime's charge |
| US3 | T003 — a projection straddling 2025-01-01 charges 1% from it and refuses by name before it |
| US4 | T004, T019 — two schemes differing only in a periodic component's amount; the zero reported as declared |
| US5 | T027 — the existing costing path, the base bit-identical, the gap labelled |
| US6 | T019, T029 — a second scheme is a file; no id reaches executable source |

## Suggested MVP

Phases 1–3 and Phase 5: the scheme, its declaration, and the stream that names it. That is
US1, US2 and US3 — the whole of what makes the owner's contract income a number rather than an
"unknown". Phase 4 is what makes it honest about where the money lands, and is not optional in
this feature, but it is separable work.
