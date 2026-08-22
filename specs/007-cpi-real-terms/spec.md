# Feature Specification: CPI and the real hurdle rate

**Feature Directory**: `specs/007-cpi-real-terms`

**Feature Branch**: `spec/007-cpi-real-terms` (spec-writing worktree; squash-lands per `specs/README.md`)

**Created**: 2026-08-22

**Status**: Ready for planning — all clarifications resolved 2026-08-22

**Input**: Real terms — filling the slot feature 001 deliberately left empty. CPI enters
as declared, dated, sourced observations; the hurdle-rate result's real slot fills with
a real rate of the same shape, so nothing downstream changes.

---

## Why this feature exists

Feature 001 shipped the hurdle rate labelled **nominal**, with the real-terms slot
occupied by a typed "unavailable" value carrying its reason. That was deliberate
honesty, not an omission: a nominal 15.5% against double-digit inflation is a materially
different proposition, and the output said "not modelled" rather than implying
otherwise. 001's own clarifications record close with: *"Closing that gap is the job of
the feature that introduces CPI."* This is that feature.

The contract was set in advance. 001's FR-022 reserved a defined, typed place for the
inflation-adjusted figure so that filling it later would change neither the shape of the
result nor anything that consumes it. This feature fills the slot and changes nothing
else: CPI enters as declared, dated, sourced observations — the same epistemic category
as every other observed value in the system — and the real figure derived from them
carries every mark its inputs carry.

One rule 001 made collided with what this feature must do, and that collision went to
the owner rather than being resolved by a guess: FR-022 says a real figure MUST NOT be
computed from an assumed inflation rate — yet the hurdle projects into the future,
where only assumptions exist. The owner resolved it on 2026-08-22 (see Clarifications
resolved): **both figures, separately labelled, never mixed into one number** — and
001's prohibition is refined, not repealed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the hurdle rate in purchasing power (Priority: P1)

The owner has declared UA CPI observations — dated, sourced, each carrying its
provenance. For a period those observations cover, the tool reports the hurdle rate in
real terms alongside the nominal figure: the same result, same shape, with the
previously empty real slot now holding a real rate that states what it was deflated by.
Where no covering CPI exists, the slot stays typed-unavailable — but now the reason
names exactly what is missing, not merely "inflation is not modelled".

**Why this priority**: This is the entire value of the feature. The nominal hurdle rate
is the benchmark every other option must beat, and inflation is the largest term it
currently omits. Without the real figure the owner is comparing money amounts, not
purchasing power.

**Independent Test**: Declare a small set of clearly-labelled synthetic CPI observations
covering a known window, deflate a known nominal figure over that window, and check the
resulting real rate against arithmetic worked out by hand on paper.

**Acceptance Scenarios**:

1. **Given** declared CPI observations fully covering a deflation window and a nominal
   hurdle rate, **When** the projection runs, **Then** the real slot holds a real rate
   that matches the hand-computed deflation within the single project tolerance, and the
   nominal figure is unchanged to the last digit.
2. **Given** the same inputs, **When** the real figure is inspected, **Then** it is
   labelled real, names the CPI series that deflated it and the window the observations
   cover, and is visibly distinct from the nominal figure — the two are never presented
   interchangeably.
3. **Given** a deflation window with no covering CPI observations (none declared, or a
   gap in the series), **When** the projection runs, **Then** the real slot is
   typed-unavailable with a reason naming the missing period, and no value is
   interpolated, assumed, or invented to fill the gap.
4. **Given** a window in which prices fell (negative inflation), **When** the real rate
   is computed, **Then** it comes out above the nominal rate, matching the hand-computed
   example — deflation is a valid observation, not an error and not clamped.
5. **Given** a projection identical to one that ran under feature 001 with no CPI data
   declared, **When** it runs under this feature, **Then** the result has exactly the
   same shape, and everything that consumed the 001 result consumes this one unchanged.

---

### User Story 2 - Never mistake an assumption for an observation (Priority: P1)

Every real figure can be opened up: which CPI observations deflated it, where each came
from, when it was retrieved and verified. A figure resting on the declared
future-inflation assumption is visibly an assumption everywhere it appears, and is
never blended with a figure resting on observed CPI into one indistinguishable number.

**Why this priority**: Equal-highest with Story 1, because it is Principle I applied to
the one input where observation and assumption are easiest to confuse. Realized CPI is a
published statistical fact; future inflation is a belief. A tool that lets the second
masquerade as the first is confidently wrong about the exact thing this feature exists
to make honest.

**Independent Test**: Produce a real figure from observed CPI and a real figure from a
declared assumption, then confirm the two are distinguishable at a glance in the output
and that neither's provenance trail leads to the other's inputs.

**Acceptance Scenarios**:

1. **Given** a real figure derived from observed CPI, **When** it is inspected, **Then**
   every CPI observation behind it can be enumerated, each with its value, source,
   retrieval date and verification date.
2. **Given** a CPI observation with an empty verification date, **When** a real figure
   is derived from it, **Then** that figure — and every figure downstream of it — is
   marked as resting on an unverified input.
3. **Given** a nominal figure that already carries an unverified mark (the 001 yield)
   and verified CPI, **When** the real figure is computed, **Then** it carries the
   nominal figure's mark: deflating a marked figure never launders the mark.
4. **Given** a declared future-inflation assumption, **When** any figure touched by it
   is displayed, **Then** it is labelled as assumption-driven, distinguishable from
   every observed-CPI figure, and no single number blends observed and assumed
   inflation.
5. **Given** two runs identical except for the declared inflation assumption — the
   owner's own figure in one, an external published forecast in the other, **When**
   results are compared, **Then** they are two distinct results, each naming the
   assumption it used, and each run's record states which declaration produced it.

---

### User Story 3 - Know when the CPI data has gone stale (Priority: P2)

CPI is published on a schedule, so its freshness has a natural horizon. The owner
declares a staleness threshold for the CPI kind of value — its own kind, with its own
threshold, following the per-kind pattern feature 002 established — and once the data
ages past it, every real figure derived from it says so.

**Why this priority**: A silently stale deflator invalidates the real figure exactly the
way a silently stale route cost invalidates a comparison (002's finding). It is P2 only
because Story 1's marks and typed-unavailable reasons already prevent the worst
dishonesty; staleness sharpens the freshness dimension on top.

**Independent Test**: Declare CPI observations, age them past the declared threshold,
and confirm the derived real figure reports the staleness; declare a CPI kind with no
threshold and confirm loading fails.

**Acceptance Scenarios**:

1. **Given** CPI observations whose age — measured from the later of verification and
   retrieval dates — exceeds the declared CPI staleness threshold, **When** a real
   figure is derived from them, **Then** the figure is reported stale, naming the value
   that aged and its threshold.
2. **Given** a CPI value kind declared with no staleness threshold, **When** the data is
   loaded, **Then** loading fails naming the kind, rather than defaulting to a
   permissive threshold.
3. **Given** fresh CPI observations, **When** a real figure is derived, **Then** no
   staleness warning appears — a warning that fires on fresh data is a warning that gets
   ignored.

---

### User Story 4 - Add CPI data without touching the engine (Priority: P3)

CPI observations are declared in data files, like every other observed value. Extending
the series with new months, correcting a value with a better-sourced one, or — later,
in the display-currency feature — declaring a second country's CPI series, are all
data-only changes.

**Why this priority**: This is Principle II applied to CPI. It is P3 because, as in 001,
it is verified rather than built: if Stories 1–3 are built correctly this already works,
and this story's job is to prove it — including proving the data shape does not paint
the project into a UA-only corner.

**Independent Test**: Extend a declared CPI series and declare a second, differently
identified series purely as data, and confirm both load and the first drives results,
with no source file edited.

**Acceptance Scenarios**:

1. **Given** new CPI observations appended to the declared series as data, **When** the
   projection runs, **Then** they participate in deflation with no source-code change.
2. **Given** a second CPI series with a different identity (a different country's index)
   declared purely as data, **When** it is loaded, **Then** loading succeeds and the
   series is addressable — even though nothing in this feature consumes it — proving the
   shape does not preclude the display-currency feature's second series.
3. **Given** a CPI data file with a malformed value, an unrecognised field, a missing
   required field, a duplicate or overlapping period, or a period that is not
   contiguous with its declared periodicity, **When** it is loaded, **Then** loading
   fails naming the file and the offending field or period, and no default is
   substituted.

---

### Edge Cases

- **A gap inside the CPI series** (declared months 1–3 and 5–6) — a deflation window
  crossing month 4 is typed-unavailable naming the missing period; the system never
  interpolates across the gap.
- **A deflation window partially covered** — partial coverage is not coverage; the
  system must not deflate the covered part and silently annualise as if it covered the
  whole window.
- **Negative inflation over the window** — valid; the real rate exceeds the nominal
  rate (Story 1, scenario 4).
- **Inflation so high the real rate is negative** — valid and expected for the domain;
  reported as negative, never clamped to zero.
- **CPI observations published for a period that has not finished** — rejected at load:
  an observation must cover an elapsed period, or it is a forecast wearing an
  observation's clothes.
- **Duplicate observations for the same period in one series** — a collision, reported
  at load time.
- **Two series declaring the same identity** — a collision, reported at load time.
- **The nominal figure itself unavailable** — no deflation is attempted; the real slot
  reports that there is nothing to deflate, distinct from "no CPI".
- **A real figure requested in a currency the series does not measure** — refused; a
  real number carries the series it is real against, and UA CPI cannot make a USD
  figure "real" (that pairing is the display-currency feature's job).
- **CPI observation with an empty verification date** — proceeds under the unverified
  mark, exactly like the 001 yield; distinct from a missing value, which does not
  proceed at all.

## Requirements *(mandatory)*

### Functional Requirements

**CPI as declared data**

- **FR-001**: UA CPI MUST enter the system as declared, dated observations in data
  files: each observation states the period it covers, the published value for that
  period, its source, its retrieval date and its verification date (which MAY be empty
  but MUST NOT be absent). No CPI value may originate from an implementer's or agent's
  memory — only from a cited public source entered as data.
- **FR-002**: A CPI series MUST declare its own identity — at minimum the country or
  economy it measures and the price index it is — and its observation periodicity. The
  periodicity MUST be declared per series, not fixed in the engine, and observations
  MUST conform to it. Nothing in the system may treat "the CPI" as a singleton: a
  second series with a different identity MUST be a data-only addition that loads and
  is addressable, even though no second series is consumed in this feature.
- **FR-003**: Loading CPI data MUST fail loudly — naming the file and the offending
  field or period — on a malformed value, an unrecognised field, a missing required
  field, a duplicate or overlapping period, a period inconsistent with the declared
  periodicity, a period that has not yet elapsed, or a duplicated series identity. A
  default MUST NOT be substituted for anything absent.
- **FR-004**: The system MUST NOT invent, interpolate, extrapolate or smooth CPI
  values. A period without a declared observation is a gap, and any figure that would
  need it is typed-unavailable naming the missing period.

**Staleness**

- **FR-005**: CPI MUST be a staleness kind of its own, with a threshold declared
  alongside the kind, following 002's FR-028 pattern: per kind of value, no permissive
  default, and a kind with no declared threshold fails at load. Staleness is measured
  from the later of an observation's verification and retrieval dates (002's FR-025
  rule), and once exceeded, every figure derived from the stale observation reports the
  staleness.

**The real figure**

- **FR-006**: When declared CPI observations fully cover the required deflation window,
  the system MUST fill the hurdle-rate result's real-terms slot — the slot 001's FR-022
  reserved — with a real rate. The shape of the result MUST NOT change, and nothing
  that consumed the 001 result may need to change; that invariance was FR-022's whole
  point and this feature MUST prove it holds.
- **FR-007**: The nominal figure that gets deflated is the **contractual
  yield-to-maturity** — the benchmark 001's FR-023 designates — not the
  cash-flow-weighted return. The real figure is the real counterpart of the benchmark,
  and MUST be labelled as such.
- **FR-008**: Deflation MUST use the exact compounding relation between the nominal
  rate, the inflation rate and the real rate (the Fisher relation), never the
  subtraction approximation, because at Ukrainian inflation magnitudes the
  approximation error is itself material. The chosen relation, its plain-language
  definition, and a worked example MUST land in `docs/METHODOLOGY.md` in the same
  change as the formula's implementation, per the constitution.
- **FR-009**: ⚙ **Resolved by the owner 2026-08-22 — option (c), both, separately
  labelled.** The real-terms output MUST carry **two** figures, never mixed into one
  number: a **realized-CPI real figure** for the portion of the horizon covered by
  declared observations, and an **assumption-driven real figure** for the projected
  portion, computed from a declared future-inflation assumption (FR-015). Neither may
  stand in for the other, and where either figure's inputs are missing, that figure —
  and only that figure — is typed-unavailable with its reason (FR-012). This refines
  001's FR-022 prohibition rather than repealing it: FR-022 was written to forbid a
  real figure computed from an *implicit or invented* inflation rate, and that stays
  forbidden; a *declared, dated, labelled owner assumption entered as scenario data* —
  the same epistemic category as 002's regime transition date — is a different thing,
  and is permitted precisely because it is visible as an assumption on every figure it
  touches. When this feature's implementation lands, 001's spec gains a ⚙
  cross-reference at FR-022 recording the refinement (an obligation recorded here; 001's
  spec is not edited from this feature's spec-writing branch).
- **FR-015**: The future-inflation assumption MUST be a **passable input** — a per-run
  scenario declaration, never a constant baked in — so different assumption sources can
  be used per run: the owner's own figure, or an external published forecast (e.g. the
  National Bank's inflation forecast). An external forecast enters with its own
  citation, retrieval date and staleness kind — but it remains epistemically an
  **assumption**: a forecast is not an observation, it is labelled as an assumption,
  and it is never blended with realized CPI. Two runs with two different assumption
  declarations are two results, each naming the assumption it used, and the run
  manifest records which declaration produced each.
- **FR-010**: A figure derived from observed CPI and a figure derived from a declared
  inflation assumption MUST never be indistinguishable (Principle I). Each MUST be
  labelled with its epistemic source — an external published forecast included, which
  is labelled as an assumption, never as an observation — and no single reported number
  may blend observed and assumed inflation.
- **FR-011**: A real figure MUST be labelled real, MUST name the CPI series it is real
  against and the window the observations cover, and MUST NOT be presentable as, or
  confusable with, the nominal figure. The nominal figure remains labelled nominal
  exactly as 001 requires.
- **FR-012**: When a real figure cannot be computed, its place MUST hold a
  typed-unavailable value whose reason states specifically what is missing — the
  uncovered period, the absent series, the absent nominal figure, or, for the projected
  portion, the absence of a declared inflation assumption — never the 001-era generic
  "inflation is not modelled", which stops being true the moment this feature lands.

**Provenance**

- **FR-013**: Every real figure MUST be traceable to the CPI observations that deflated
  it and to the nominal figure it deflates. Its provenance is the union of both sides':
  an unverified mark or a staleness report on any CPI observation used, or on any input
  of the nominal figure, MUST appear on the real figure and on everything derived from
  it. A transform that drops the mark is a defect of the highest severity.

**What must not change**

- **FR-014**: This feature MUST NOT change how any nominal figure is computed, and MUST
  NOT change any realised amount, any tax figure, or any ranking. Filling the real slot
  is additive; every 001 behaviour is preserved bit-for-bit on identical inputs.

### Key Entities

- **CPI series** — a declared, identified sequence of price-index observations for one
  economy: its identity (country, index), its declared periodicity, and its
  observations. Shaped so a second series is a data-only addition.
- **CPI observation** — one period's published price-index value: the period covered,
  the value, source, retrieval date, verification date. The atom of realized inflation.
- **CPI staleness kind** — the declared threshold governing when CPI observations count
  as stale, following 002's per-kind pattern.
- **Deflation window** — the elapsed span a real figure is deflated over, and the test
  of coverage: every period in the window must have exactly one observation.
- **Real rate** — the inflation-adjusted counterpart of the benchmark nominal figure,
  labelled with the series and window that produced it. Fills the slot 001 reserved.
- **Real-terms-unavailable reason** — the typed occupant of the real slot when no real
  figure can be computed, now carrying a specific reason naming what is missing.
- **Owner inflation assumption** — a declared, dated, per-run scenario value for future
  inflation: the owner's own figure, or an external published forecast carrying its own
  citation, retrieval date and staleness kind. Visibly an assumption on every figure it
  touches — a forecast is not an observation — in the same epistemic category as 002's
  regime transition date, never blended with observed CPI. A passable input, never a
  constant; the run manifest records which declaration a result used.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a nominal figure deflated over a window fully covered by
  clearly-labelled synthetic CPI observations, the real rate matches an independently
  hand-computed deflation within the single project tolerance, and the arithmetic is
  recorded alongside the check.
- **SC-002**: On inputs with no CPI declared, the complete result is shape-identical to
  feature 001's output, every consumer of the 001 result runs unchanged, and the only
  difference is the specific wording of the unavailability reason.
- **SC-003**: With one CPI observation left unverified, 100% of real figures derived
  from it carry the unverified mark; with the nominal figure's input unverified and CPI
  fully verified, the real figure still carries the mark. No derived figure appears
  unmarked in either direction.
- **SC-004**: A CPI observation aged past its declared threshold marks every derived
  real figure stale, naming the value and threshold; a CPI kind declared without a
  threshold fails at load; fresh observations produce zero staleness warnings.
- **SC-005**: Across a deliberate battery of broken CPI files — malformed value,
  unknown field, missing field, duplicate period, overlapping periods, wrong
  periodicity, not-yet-elapsed period, duplicated series identity — every case fails
  naming the file and the offending field or period, and no case substitutes a default.
- **SC-006**: Every deflation window with a coverage gap produces a typed-unavailable
  real slot whose reason names the missing period; zero cases interpolate, annualise
  partial coverage, or silently proceed.
- **SC-007**: A negative-inflation window produces a real rate above the nominal rate,
  and a high-inflation window produces a negative real rate, both matching
  hand-computed arithmetic — neither clamped.
- **SC-008**: Every assumption-driven figure is distinguishable from every observed-CPI
  figure in 100% of outputs, no reported number blends the two, and two runs differing
  only in their declared inflation assumption produce two results, each naming the
  assumption it used, with the run manifest recording which.
- **SC-009**: A second CPI series with a distinct identity, declared purely as data,
  loads and is addressable with zero lines of source code changed.
- **SC-010**: `docs/METHODOLOGY.md` gains the deflation formula, its plain-language
  definition and a worked example in the same change that implements it — verified by
  the change's own diff, not by a follow-up.

## Assumptions

- **No real CPI values enter with this spec.** Acceptance examples run against
  clearly-labelled synthetic observations whose values are stated in the test itself,
  exactly as 001 did with its synthetic issue: the examples test the deflation
  arithmetic, not the Ukrainian economy. Real UA CPI observations are added as data
  files carrying their own provenance (source, retrieval date, verification date) from
  the published statistics, and nothing is invented to make an example work.
- **Monthly periodicity is the expected shape but not a hard-wired one.** UA CPI is
  published monthly, and the synthetic examples use monthly periods; per FR-002 the
  periodicity is declared per series, so a differently-published index later is a
  data-only addition.
- **The exact Fisher relation is the default formula** (FR-008), on the grounds that
  the subtraction approximation is materially wrong at double-digit inflation and using
  it would violate Principle I. The owner raised no objection when resolving the
  clarifications, and either way the formula lands in `docs/METHODOLOGY.md`.
- **Only the benchmark figure gets a real counterpart here.** The contractual YTM is
  deflated (FR-007); the cash-flow-weighted return keeps its nominal-only presentation.
  Deflating other figures is not precluded by the shape, just not required by this
  feature.
- **UA CPI only is consumed.** The dual-CPI display rule — US CPI deflating the USD
  view, required test F4 — belongs to the display-currency feature. This feature's
  obligation to it is purely structural: the data shape must not preclude a second
  series (FR-002, SC-009).
- **Hold-to-maturity, single currency, no delivery surface** — all of 001's scope
  assumptions carry over unchanged. This feature adds no routes, no venues, no display
  switch, and no interface.

## Clarifications resolved

The one question raised during specification was answered by the owner on 2026-08-22.

| # | Question | Decision | Where it landed |
|---|---|---|---|
| 1 | Future inflation: realized-CPI-only (a), owner-declared assumption as scenario data (b), or both separately labelled (c)? 001's FR-022 forbids a real figure computed from an assumed inflation rate; the hurdle's horizon is the future, where only assumptions exist. | **(c) Both, separately labelled, never mixed into one number** — a realized-CPI real figure where observations cover, an assumption-driven real figure for the projected portion. The assumption is a **passable per-run input**, never a constant: the owner's own figure, or an external published forecast (e.g. the National Bank's inflation forecast), which enters with its own citation, retrieval date and staleness kind but remains epistemically an assumption — a forecast is not an observation — labelled as such and never blended with realized CPI. Two runs with two different assumption declarations are two results, each naming the assumption it used, with the run manifest recording which. | FR-009, FR-015, FR-010, FR-012, SC-008; the owner-inflation-assumption entity |

The decision **refines 001's FR-022 rather than repealing it**: the prohibition was
written to forbid a real figure computed from an *implicit or invented* inflation rate,
and that stays forbidden. What it now distinguishes is a *declared, dated, labelled
owner assumption entered as scenario data*, which is permitted because it is visible as
an assumption on every figure it touches. When this feature's implementation lands,
001's spec gains a ⚙ cross-reference at FR-022 recording the refinement — noted here as
an obligation, since 001's spec is not edited from this feature's spec-writing branch.

## Required tests this feature relates to

- **F4** (*"The real-terms view uses UA CPI in the UAH display and US CPI in the USD
  display"*) is **not closed** by this feature: its second half is the display-currency
  feature's job. This feature is F4's prerequisite — it builds the UA CPI series, the
  deflation and the real slot that F4's UAH half will exercise — and the row stays
  unflipped until the display-currency feature lands.
- Per the constitution, every financial behaviour above lands with a hand-computed
  worked example (the deflation arithmetic, SC-001, SC-007), load-failure coverage
  (SC-005), and propagation checks (SC-003, SC-004); the shape-invariance claim (SC-002)
  is verified against 001's existing suite running unchanged.

## Out of scope

Named explicitly so the plan does not drift into them: the display-currency switch and
all of required test F4's dual-CPI behaviour; US CPI or any second series being
*consumed* (only its declarability is in scope); forecasting models of any kind —
statistical, extrapolated or otherwise; market-priced instruments and return models;
any change to how nominal figures are computed; indexation of income streams;
real-terms versions of any figure other than the hurdle-rate benchmark; and everything
001 already declared out of scope that this feature does not explicitly pull in.
