# Tasks: Inzhur instruments and dated tax schedules

**Input**: Design documents from `specs/006-inzhur-instruments/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md)
(D1–D13), [data-model.md](./data-model.md),
[contracts/tax-schedule.md](./contracts/tax-schedule.md),
[contracts/fund-declaration.md](./contracts/fund-declaration.md)

**Tests**: required. Constitution Principle V is NON-NEGOTIABLE — every financial
behaviour lands with a hand-computed worked example, a property-based invariant or a
golden file, and **the test fails before the implementation exists** (an `ImportError`
counts).

**Organization**: grouped by user story, in the order plan.md's Phase 2 note fixes:
**the schedule migration first, with 001's golden green**, then the fund declaration and
its refusals, then the projection, then the liquidity modes, then the peg.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: US1…US5 from spec.md
- Every task names its file path

## Path conventions

Single Python library, src layout, layered `cli → api → data → core`. Paths are relative
to the worktree root `/Users/rapkin/dev/terezy/.claude/worktrees/006-inzhur-instruments`.

---

## The one thing that must not be guessed

`RateEntry.effective_from` is a **legal fact** and must be exactly what its citation
attests (research.md D2, contracts/tax-schedule.md). T004 exists to settle it *before*
any file is written, and it is the only task in this list whose output may be "stop and
ask the owner".

---

## Phase 1: Setup

**Purpose**: record the baseline the whole feature is measured against, and add the
declaration vocabulary the new data needs.

- [x] T001 Record the pre-change gate baseline (test count, coverage %, provenance
      warnings) in the implementation notes of `specs/006-inzhur-instruments/tasks.md`
      by running `uv run pytest --cov` and `uv run python scripts/check_provenance.py`
      from the worktree root
- [x] T002 [P] Declare the observation kinds the fund and schedule tables age under —
      `fund_terms`, `fund_stated_yield`, `fund_liquidity` — each with `staleness_days`
      and a `note` giving the reason, in `data/observation_kinds.toml`
- [x] T003 [P] Add the `006-inzhur-instruments` banner comment at the end of
      `src/terezy/data/declarations/schema.py`,
      `src/terezy/data/declarations/loader.py` and
      `src/terezy/data/declarations/resolver.py`, matching the existing per-feature
      banners, so feature 004's parallel work on the same files merges as an append

---

## Phase 2: Foundational — dated rate schedules (BLOCKING)

**Purpose**: pay feature 001's recorded debt. `TaxClass.rates` becomes a tuple of dated
entries and the scalar pair is **removed** (research.md D1). Everything in the tax path
depends on this, and a migration that moved a number must be found before any fund
exists (plan.md Phase 2 note, research.md D13).

**⚠️ CRITICAL**: no user story work begins until 001's golden is green again.

- [x] T004 **Settle the effective date before writing anything.** Read
      `docs/reference/SIMULATOR_SPEC.md` §4.5, §4.5.1 and §12 and establish, for each
      class the migration declares, the exact date its citation attests. Record the
      finding — the date, the citation and the sentence that attests it — in the
      implementation notes at the foot of this file. If no citation supports a date on
      or before 001's first taxable event (2026-07-15), **do not widen the date**: stop
      this task, do everything that does not depend on it, and report it as an owner
      question (research.md D2, contracts/tax-schedule.md)
- [x] T005 [P] Write the failing boundary test for `rate_on` — in force **from** the
      effective date inclusive, the latest entry on or before the date, and the entry
      before the boundary on the day before — in `tests/unit/test_rate_lookup_boundary.py`
- [x] T006 [P] Write the failing refusal test — an event dated before the schedule's
      earliest entry returns `RateUndeclaredBefore` naming the class, the event date and
      the earliest declared date, and no rate is defaulted — in
      `tests/unit/test_schedule_refusals.py`
- [x] T007 Implement `RateEntry`, `rate_on` and `RateUndeclaredBefore` in
      `src/terezy/core/tax/schedule.py`, pure and clock-free, with the date as an
      argument (research.md D3, D12)
- [x] T008 Replace `TaxClass.pit_rate` / `TaxClass.levy_rate` with
      `rates: tuple[RateEntry, ...]` in `src/terezy/core/tax/interface.py`, and state in
      the docstring that provenance is **per entry** because two rates cited by two
      sources are two observations (research.md D1, contract G4)
- [x] T009 Migrate `charge` in `src/terezy/core/tax/flat_rate.py` to select the entry in
      force on the event's date and return `RateUndeclaredBefore` where none is, keeping
      the `TaxRule` interface and the two-line PIT/levy split unchanged
- [x] T010 Add `RateUndeclaredBefore` to the `TaxFailure` union in
      `src/terezy/core/errors.py` so every consumer must match it exhaustively
- [x] T011 Migrate the tax-file shape: `[[jurisdiction.tax_class.rate]]` entries with
      `effective_from`, `pit_rate_pct`, `levy_rate_pct` and per-entry provenance,
      replacing the scalar pair, in `src/terezy/data/declarations/schema.py`
- [x] T012 Migrate `_tax_class` in `src/terezy/data/declarations/loader.py` to build the
      sorted entry tuple, converting percent to a fraction exactly once through
      `_as_fraction`, and to refuse an empty schedule, a duplicate `effective_from`, an
      unsorted schedule and a negative rate, each naming the file and the field
      (contracts/tax-schedule.md, loader validation table)
- [x] T013 Migrate `data/tax/ua.toml` to schedule form with the date settled in T004 and
      the citation intact, changing no rate value (FR-014)
- [x] T014 [P] Write the failing load-refusal battery — empty schedule, duplicate
      effective dates, unsorted entries, negative rate, missing `source` on an entry —
      each asserting the file and the field are named, in
      `tests/contract/test_declaration_loading.py`
- [x] T015 Update every existing test that constructs a `TaxClass` with scalar rates to
      the schedule form, across `tests/unit/test_flat_rate.py`, `tests/synthetic.py`,
      `tests/golden/test_end_to_end_ovdp.py`, `tests/contract/*` and
      `tests/invariants/*`
- [x] T016 **Prove the migration moved no figure**: run
      `uv run pytest tests/golden/test_end_to_end_ovdp.py` and confirm every figure,
      schedule row, tax charge and ledger line in
      `tests/golden/ovdp_synthetic_a.golden.txt` is unchanged; record in the
      implementation notes exactly which lines of the artefact did move and why (FR-014,
      SC-006, research.md D13)

**Checkpoint**: rates are dated schedules, the scalar is gone, and 001's figures are
untouched.

---

## Phase 3: User Story 2 — a rate that changes on a date (Priority: P1)

**Goal**: a projection whose events straddle an effective date charges the old rate
before it and the new rate from it, in one run; and a legislated change is one dated
entry in a data file with no source change. Closes required test **E10**.

**Independent Test**: declare a schedule with two dated entries, run a projection with
taxable events on both sides, check both charges by hand; then add a third entry as a
data-only edit and confirm it takes effect.

- [x] T017 [US2] Write the failing hand-computed worked example for the straddle — a
      synthetic two-entry schedule, taxable events before and after the effective date,
      the arithmetic for both charges written out beside the assertion, and the
      difference between the two periods equal to exactly the declared step — in
      `tests/worked_examples/test_rate_schedule_straddle.py` (SC-003)
- [x] T018 [US2] Extend that module with the data-only proof: a third dated entry added
      to a scratch copy of the tax file takes effect in the next run with **zero** source
      lines changed (SC-004, FR-013)
- [x] T019 [US2] Extend `tests/unit/test_schedule_refusals.py` so the refusal is asserted
      end to end — a projection whose first taxable event precedes the earliest entry
      returns the typed error rather than a projection (FR-012, SC-005)
- [x] T020 [US2] Assert the two-class isolation property: editing one class's schedule
      changes only that class's subtotal and leaves the other class's figures
      bit-identical, in `tests/invariants/test_rate_schedule_isolation.py` (SC-002)

**Checkpoint**: E10's behaviour is executable and hand-checked.

---

## Phase 4: User Story 1 — both taxes in one run (Priority: P1) 🎯 MVP

**Goal**: one instrument, two declared tax classes; a distribution taxed under the
fund-distribution class and a redemption of the same units under investment profit, with
per-class subtotals in the output. Closes required test **E1**.

**Independent Test**: project a holding with at least one distribution and one final
redemption and check every charge, and the per-class subtotals, against arithmetic
worked out by hand.

- [x] T021 [P] [US1] Write the failing contract test for fund-declaration loading —
      every refusal in contracts/fund-declaration.md: a valued term with no `source` or
      `retrieved_on`, `tax_classes` naming an undeclared class, a `verification_task`
      carrying a value, a missing `terminates_on`, an extra key, a markup or discount
      outside 0–100%, a termination date before the subscription cutoff — in
      `tests/contract/test_fund_declaration_loading.py` (FR-003)
- [x] T022 [P] [US1] Write the failing hand-computed worked example for the two-class
      split — one distribution, one redemption of the same units, the arithmetic for each
      charge and each per-class subtotal written out beside the assertion, the disposal
      base being proceeds minus basis consumed minus fees allocated, a disposal at a loss
      charging exactly zero and reporting the loss with the carryforward statement — in
      `tests/worked_examples/test_two_tax_classes.py` (SC-001, FR-006–FR-008)
- [x] T023 [US1] Declare the two new tax classes — `ua_ci_fund_distribution` (9% + 5%)
      and `ua_investment_profit` (18% + 5%) — as dated schedules in `data/tax/ua.toml`,
      each rate carrying the citation `SIMULATOR_SPEC.md` §4.5 records for it, its
      retrieval date and an **empty** verification date (FR-009)
- [x] T024 [US1] Add the fund records to `src/terezy/core/instruments/fund.py`:
      `FundDeclaration`, `DeclaredYield`, `DistributionTerms`, `Peg`, `CapEntry`,
      `SpreadTerms`, `LiquidityTerms`, `LegalTerms`, `ObservedPractice`, `FeeFact`,
      `VerificationTask` — frozen, slotted, `is_assumption_driven: Literal[True]`, and
      **no field for a computed fee** (data-model.md, research.md D9, D10)
- [x] T025 [US1] Add the fund event generator to
      `src/terezy/core/instruments/fund.py`: purchase at NAV plus the declared entry
      markup, the declared distributions, and the exit — as ledger events, gross, with
      provenance on every amount and a typed failure where the terms cannot hold
- [x] T026 [US1] Add `EventKind.DISTRIBUTION` to `src/terezy/core/ledger/events.py` and
      map it to `TaxableEventKind.DISTRIBUTION` in the exhaustive match in
      `src/terezy/core/results/project.py`
- [x] T027 [US1] Add the fund tables to `src/terezy/data/declarations/schema.py` under
      the 006 banner: `FundTable` and its sub-tables, `STRICT`, no defaults
- [x] T028 [US1] Add `fund_from_file` and its helpers to
      `src/terezy/data/declarations/loader.py` under the 006 banner, converting percent
      to a fraction exactly once and refusing every condition in T021
- [x] T029 [US1] Teach `src/terezy/data/declarations/resolver.py` to dispatch an
      instrument file to the fund loader by its declared `class`, to key funds by id, to
      refuse a duplicate id across instruments and funds, and to check every fund's tax
      class references resolve **and** cover the kind named
- [x] T030 [US1] Add `FundProjection`, `ClassSubtotal`, `DistributionLine` and the six
      typed refusals to `src/terezy/core/results/fund.py`, with per-class subtotals and
      **no field a statistical metric could sit in** (FR-007, research.md D4, D10)
- [x] T031 [US1] Wire the projection in `src/terezy/core/results/fund.py`: fold the gross
      events, charge every taxable event under the class its kind maps to, interleave the
      charges, fold again, and read every reported figure off the ledger
- [x] T032 [US1] Declare `data/instruments/inzhur_reit.toml` with the researched terms,
      their primary-document citations and empty verification dates (FR-026, FR-027)
- [x] T033 [US1] Extend `src/terezy/data/manifest.py` so a fund declaration is an input
      reference like any other, carrying the ids of its unverified sources

**Checkpoint**: E1's behaviour is executable and hand-checked; the REIT is declared.

---

## Phase 5: User Story 3 — liquidity is a practice, not a right (Priority: P2)

**Goal**: both liquidity modes projectable for one request, the mode always stated, an
exit refused or executed at the declared discount, taxed on the proceeds actually
received. Closes required test **J3**.

**Independent Test**: project the same dated redemption request under the practice mode
and under the legal terms, and check the executed amounts, the refusal case and the tax
on the discounted case by hand.

- [x] T034 [US3] Write the failing hand-computed worked example for the three liquidity
      cases — practice at NAV same-day labelled revocable and unverified; legal terms at
      the declared maximum discount with the declared settlement delay, the discount its
      own line and the disposal tax on the post-discount proceeds; and the refusal naming
      that no buyback obligation exists before the termination date with the holding left
      open — plus the assertion that the two modes differ by exactly the declared spread,
      discount and delay, in `tests/worked_examples/test_fund_liquidity.py` (SC-007)
- [x] T035 [US3] Implement the required, keyword-only `liquidity_mode` parameter with **no
      default** and the mode's execution rules in `src/terezy/core/results/fund.py`
      (research.md D5, FR-015–FR-018)
- [x] T036 [US3] Implement `RedemptionRefused` so the lot stays open and the termination
      date is named as the next guaranteed exit, in `src/terezy/core/results/fund.py`
      (research.md D6, FR-017)
- [x] T037 [US3] Implement the cutoff and termination rules — a purchase after the
      declared subscription cutoff refused naming the cutoff, and a horizon reaching the
      termination date producing a dated termination payout taxed as a disposal — in
      `src/terezy/core/instruments/fund.py` and `src/terezy/core/results/fund.py`
      (FR-019, SC-014)
- [x] T038 [US3] Assert the cutoff refusal, the termination payout and the
      guaranteed-exit feasibility finding in
      `tests/contract/test_fund_declaration_loading.py` and
      `tests/worked_examples/test_fund_liquidity.py` (SC-014)

**Checkpoint**: J3's behaviour is executable and hand-checked.

---

## Phase 6: User Story 4 — MilTech under declared terms only (Priority: P2)

**Goal**: an accumulation fund projected as simple pro-rata arithmetic over a
fund-stated range, with the spread erosion visible and the outcome reported beside 001's
hurdle rate.

**Independent Test**: declare the fund, project a contribution to its termination under
the declared rate, and check the pro-rata accrual, the spread, the disposal tax and the
net outcome by hand.

- [x] T039 [US4] Declare `data/instruments/inzhur_miltech.toml` — minimum ticket, term to
      2029-11-06, subscription cutoff 2026-12-31, the 25–29% fund-stated range, the fee
      facts as recorded context and the commission as a verification task — with
      citations and empty verification dates (FR-026, FR-028)
- [x] T040 [US4] Write the failing worked example for the accumulation projection: no
      invented distribution events, pro-rata accrual over the declared yield, the exit
      taxed under the disposal class, and the round-trip spread erosion reconciling
      exactly with the named lines, in `tests/worked_examples/test_declared_yield.py`
      (SC-012, FR-023, FR-024)
- [x] T041 [US4] Implement the range discipline in `src/terezy/core/results/fund.py`: a
      range projects to a range, an explicitly declared `ChosenPoint` is labelled the
      owner's assumption, and **there is no midpoint helper** (research.md D11, SC-013)
- [x] T042 [US4] Report the after-spread, after-tax outcome beside 001's hurdle rate with
      the route-costs-excluded statement on its face, in
      `src/terezy/core/results/fund.py`, asserted in
      `tests/worked_examples/test_declared_yield.py` (FR-025, SC-013)

**Checkpoint**: MilTech projects, and nothing about it is presented as a promise.

---

## Phase 7: User Story 5 — nothing dressed up as statistics (Priority: P3)

**Goal**: every figure for either fund is labelled assumption-driven and marked
unverified; a statistical metric is a typed refusal; and a pegged payment is money only
under a declared exchange-rate assumption.

**Independent Test**: inspect every output produced for the two funds and confirm no
statistical metric appears; request one explicitly and confirm a typed refusal.

- [x] T043 [P] [US5] Write the failing contract test for the metric refusal — a request
      for volatility, Sharpe or Sortino on an assumption-driven instrument returns
      `MetricRefused` carrying the reason, and `FundProjection` has **no field** such a
      number could sit in — in `tests/contract/test_assumption_driven_refusal.py`
      (SC-009, FR-005)
- [x] T044 [P] [US5] Write the failing worked example for the peg — a payment sized under
      a declared exchange-rate assumption checked by hand, an assumed rate above the
      declared cap sized **at the cap** with the output saying the cap bound, a pegged
      flow with no declared assumption returning `PegUnsizable` naming the missing input,
      and no combination of amounts in different currencies ever succeeding — in
      `tests/worked_examples/test_pegged_distribution.py` (SC-011, FR-020–FR-022)
- [x] T045 [US5] Implement `ExchangeRateAssumption`, the cap-bound sizing and
      `PegUnsizable` in `src/terezy/core/instruments/fund.py` and
      `src/terezy/core/results/fund.py`, keeping a USD-equivalent term from ever being a
      `Money` (research.md D7)
- [x] T046 [US5] Implement `AwaitingVerification` so a projection needing a value recorded
      only as a `VerificationTask` refuses by naming the task, in
      `src/terezy/core/results/fund.py` (research.md D8)
- [x] T047 [US5] Extend `tests/contract/test_provenance_propagation.py` so every fund
      term joins the walk: with any term left unverified, 100% of figures derived from it
      carry the mark and no derived figure appears unmarked (SC-008, FR-002)
- [x] T048 [US5] Declare `data/instruments/synthetic_fund_c.toml` — a third fund with
      different liquidity terms, spread, peg and tax classes — and assert it projects
      completely with zero source lines changed, in
      `tests/contract/test_fund_data_only.py` (SC-010, FR-001)

**Checkpoint**: the refusals are structural, not documentary.

---

## Phase 8: Polish & cross-cutting

- [x] T049 [P] Document in `docs/METHODOLOGY.md`, in the same change as the formulas:
      how a rate schedule is read and why an event before the earliest entry refuses;
      what "assumption-driven" forbids; what the declared net yield is and is not; how
      the peg and its cap are stated; and why no fund-internal fee is modelled
- [x] T050 [P] Flip **E1**, **E10** and **J3** in `docs/REQUIRED_TESTS.md` with their
      test paths recorded, annotating J3's "window" wording per FR-015 ⚙; and flip
      **J4** and **J6** if their test surfaces exist
- [x] T051 [P] Update `data/README.md` rule 3 — the dated-schedule requirement is now
      met, and the "Not yet true" note is removed rather than left contradicting the code
- [x] T052 Flip `006-inzhur-instruments` to `status = "in-progress"` in
      `specs/features.toml` in the first implementation commit
- [x] T053 Run every gate from the worktree root and record the numbers and the delta
      from T001's baseline in the implementation notes below

---

## Dependencies & execution order

### Phase dependencies

- **Setup (Phase 1)** — no dependencies
- **Foundational (Phase 2)** — depends on Setup; **blocks every user story**, because
  every tax figure in the feature is read off a schedule
- **US2 (Phase 3)** — depends on Phase 2 only
- **US1 (Phase 4)** — depends on Phase 2; T023 depends on T004's settled dates
- **US3 (Phase 5)** — depends on US1's fund records and projection
- **US4 (Phase 6)** — depends on US1; independent of US3
- **US5 (Phase 7)** — depends on US1; the peg tasks depend on the REIT declaration (T032)
- **Polish (Phase 8)** — depends on everything it documents

### Within each story

Tests first, and they must fail before the implementation exists. Records before the
functions over them; the loader before the data file it validates; the data file before
the worked example that reads it.

### Parallel opportunities

- T002, T003 in Setup
- T005, T006 in Phase 2 — two test modules, no shared file
- T021, T022 in Phase 4 — a contract test and a worked example
- T043, T044 in Phase 7
- T049, T050, T051 in Phase 8

---

## Implementation notes

*Filled in as the work lands. T001's baseline, T004's finding, and T016's evidence live
here because they are the three facts a reviewer checks first.*

### T001 — baseline, before any change (2026-08-23)

- `uv run pytest --cov`: **1198 passed**, total coverage **99.77%** (floor 90%)
- `uv run python scripts/check_provenance.py`: **0 errors, 24 unverified values**,
  12 data files
- `ruff check`, `ruff format --check`, `mypy`, `lint-imports`: clean

### T004 — the effective dates, and the citation that attests each

**Revised 2026-08-23 after review.** The first pass reported "no citation in hand reaches
further back" having queried four of the six §12 sources. It was wrong: the military levy's
commencement is a matter of published law and it is retrievable.

**Rule A — a pair is dated by the later of its halves.** **Rule B — where a citation attests
a value but not when it commenced**, split into B1 (the choice changes a figure: take the
reading that claims less) and B2 (it changes no figure: take the earliest date the citation
itself asserts, recorded as a citation-currency date). Both rules and the reason they differ
are written into `data/tax/ua.toml`'s header, and **every entry names the rule that dated
it** — that is the review finding generalised: two entries in this repository take opposite
readings of a vague citation, and a reader who cannot see which rule applied cannot tell a
principle from an accident.

| Class | `effective_from` | Rule | What attests it |
|---|---|---|---|
| `ua_investment_profit` (18% / 5%) | **2024-12-01** | A, both halves legally dated | Levy: Закон України № 4015-IX від 10.10.2024, published «Голос України» 30.11.2024 № 179, in force the day after publication; the 5% applies *"до доходів, нарахованих … починаючи з 1 грудня 2024 року"*. PIT: PwC, *"18% PIT starting from 1 January 2016"*. Later of the two = 2024-12-01 |
| `ua_ci_fund_distribution` (9% / 5%) | **2026-06-30** | A over B2 | Levy half legally dated 2024-12-01 as above; **the 9% PIT half has no retrievable commencement**, so B2 dates it at the citation's own "Last reviewed - 30 June 2026". Rule A takes the later. Dating the pair at 2024-12-01 would assert the 9% applied then, which no source says |
| `ua_government_bond` (0% / 0%) | **2026-06-30** | B2 | PwC lists interest on certain state securities among exempt incomes and states the levy follows PIT; no commencement for either, and the Tax Code's own text is not retrievable. B2 rather than B1 because the class has one entry and both halves are zero: the date changes no figure, only how far back a run is possible |

**Sources, and which resolved.** `zakon.rada.gov.ua/laws/show/4015-20` (the law: title,
number, adoption date, the commencement rule, the 5% and its martial-law reversion) and
`ibuhgalter.net/news/25264` (publication date, and the accrual rule) both resolve and are
cited. `tax.gov.ua` returns HTTP 403 and `roedl.ua` presents a bad certificate; `eba.com.ua`
403s and `business.diia.gov.ua` serves no text to a fetcher. `itandem.com.ua` and
`kinto.com` 403 as well. The entries record which could not be retrieved, so the next reader
does not spend the attempts again.

**No earlier entry was written**, and it was tried. A 18% + 1,5% entry needs a commencement
for the 1,5% levy: Закон № 1621-VII (31.07.2014) is listed on the rada portal but the portal
serves no article text for it, and the source attesting the rise attests only that 1,5%
applied *through* November 2024, not from when. So the schedule starts 2024-12-01 and
earlier events refuse — which is the rule working, not a gap.

**The reasoning error the first pass made, recorded because the rule that produced it is
now fixed.** Faced with two attested dates for the exempt class, it chose the earlier and
justified it as "the later one would break 001's golden". That is circular: 2026-08-21 is
not a *widened* date, it is a strictly narrower and better-attested one, and the golden had
no business in the choice. The date it landed on is still 2026-06-30, but now for a stated
reason (B2) that does not mention the golden. `research.md` D13, which invited the
circularity, is rewritten.

**A consequence that is kept rather than fixed.** `data/instruments/ovdp_synthetic_b.toml`
pays its first coupon on 2026-06-02, before the exemption's earliest entry, so a holding
bought at its issue date is refused. The first pass moved the fixture's invented dates to
make that go away; that has been **reverted**, because it removed the only place a reader
can watch FR-012 fire on shipped data — and the disclosure paragraph justifying the move
was wrong on its own terms (30/360 is calendar-independent for accrual, not for
discounting: `modified_following` moves `occurred_on`, the IRR measures to it, and the shift
moved `nominal_ytm` by 1.4e-5 under an assertion band of ±0.01). The refusal is now asserted
in `tests/contract/test_declaration_loading.py::TestTheShippedRegistryRefusesAnUncoveredEvent`.

### T016 — what moved in 001's golden, and why

**No computed figure moved, and the projection digest is unchanged across the whole
feature**: `sha256:395d18a4f5d7e1c73cefa5ecf8e197e747ff6ccb84081075e3f212212e98d406`. Total tax is still exactly `0.0 UAH`, and every figure, schedule row,
tax charge and ledger line in `tests/golden/ovdp_synthetic_a.golden.txt` is byte-identical
to the pre-branch artefact from `== figures ==` to the end.

What did change is the `== inputs ==` block, which records the digest of every declaration
file the run was fed — deliberately, because *"a change to a declaration file **should**
fail this test, loudly, on the line that names the file"* (the module's own docstring).
Re-derived from the files on disk rather than transcribed:

```
tax/ua.toml                       sha256:79af4d487ea3a7cf0366cc1ffbea3b5ff46805bb5c2bc91e18741da16b2ca473
instruments/ovdp_synthetic_b.toml sha256:d28b43c7a66d320ecb7e6f9e5c3195a68f36fb4eb0ad11cf11b688a9c85df0f5
```

plus new `fund` and `tax_class` rows for the declarations this feature adds.
`tests/golden/ramp_comparison.golden.txt` moved on its `observation_kinds` digest for the
same reason, three fund kinds having been declared; its own comparison digest is unchanged.

⚙ **`research.md` D13 originally read "001's golden must not move, and that is the
migration's proof".** Byte-identity was never achievable — the artefact digests its own
inputs — and, worse, the wording turned the golden into a constraint on the dates rather
than a report on the arithmetic. D13 is rewritten to say what is true: the golden is
evidence that a schema change moved no arithmetic, and it is evidence only if the dates were
settled on their own citations first.

### T053 — the gates on the last commit, and the delta from T001

| Gate | Baseline (T001) | Now | Delta |
|---|---|---|---|
| `pytest --cov` | 1198 passed | **1893 passed** | +695 (includes 004, 005 and the CPI series, merged in) |
| coverage (floor 90%) | 99.77% | **99.57%** | −0.20 pt |
| `pytest -m "contract or invariant"` | — | **864 passed**, 1029 deselected | — |
| `check_provenance.py` | 0 errors, 24 unverified, 12 files | **0 errors, 463 unverified, 17 files** | the jump is the merged-in CPI series, which is one cited observation per month |
| `ruff check` / `ruff format --check` | clean | clean | — |
| `mypy` (strict) | clean, 144 files | clean, **189 files** | +45 |
| `lint-imports` | 4 contracts kept | 4 kept, 0 broken | — |

The new unverified values are the expected state, not a regression: every term of both
real funds and every new tax rate entered with a citation and an **empty** verification date
(FR-002). The gate reports them; it does not fail on them.
