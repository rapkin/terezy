# Feature Specification: Real terms on a tuple

**Feature Directory**: `specs/024-real-terms-tuple`

**Feature Branch**: `spec/024-real-terms` (spec-writing worktree; squash-lands per `specs/README.md`)

**Created**: 2026-09-06

**Status**: Ready for planning — no open clarifications

**Input**: The owner, 2026-09-03, asked whether inflation is next: «по інфляції — так». Every
candidate's figure is nominal while the benchmark it is ranked against can state a real one.
This closes the `real-terms-for-a-tuple` future.

---

## Why this feature exists

`TupleOutcome.implied_rate` is typed `NominalRate | RateNotComparable`. The
`RealRate | RealTermsUnavailable` slot feature 007 built lives on the hurdle record
(`core/results/hurdle.py`) and on nothing the join produces, so a comparison of instruments
answers in nominal terms only while the benchmark states a real figure beside it. 015 recorded
that as a typed exclusion rather than filling it (015 FR-023a, `NO_REAL_TERMS_FIGURE`), which is
why this is a recorded gap and not a silent absence.

**The formula is not re-decided.** 007 chose the exact Fisher relation and forbade the
subtraction approximation (007 FR-008, `docs/METHODOLOGY.md` §27.1). This feature applies the
same function to a second nominal figure; a second deflation site would be two roots of one
equation with two chances to disagree.

## Which inflation deflates a future span, and why it needs no clarification

The horizons run from 2026-09-01 onward and `data/cpi/ua.toml` covers 1991-08 .. 2025-10, so
**no tuple span this feature will ever see is covered by published CPI**. That looks like a
decision — assume the owner's declared belief, carry the last published year forward, or refuse
— and it is not, because the owner already took it on 2026-08-22 for exactly this question
(007's Clarifications resolved, option (c)): **two figures, separately labelled, never mixed
into one number.** One deflated by declared observations, one by a declared future-inflation
assumption, and where either's input is missing, that figure alone is typed-unavailable naming
what is missing.

Applied to a tuple that resolves the whole question: the realized half refuses by name, listing
every month of the window the series does not declare, and the assumed half carries the owner's
declared belief (`data/scenarios/inflation/owner-001.toml`) marked as an assumption. Carrying
the last published month forward was never on the table — 007 FR-004 forbids extrapolation and
carry-forward in as many words — and refusing outright would delete the only figure the owner
asked for.

**The tuple therefore gains the hurdle's whole record, not one slot.** Reusing `RealTerms`
(realized + assumed) keeps 007 FR-009's *never one blended number* true by construction, lets
one function fill both records, and makes the tuple's real figure comparable to the benchmark's
field for field — which is the point, since the answer ranks candidates against the hurdle. A
single-slot alternative would have to choose which of two figures to expose and would be
uncomparable with the benchmark beside it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See what a candidate returns in purchasing power (Priority: P1)

Every evaluated candidate reports, beside its nominal rate, a real rate over the same span:
what the money buys, not what there is more of. Where no deflator covers the span, the slot says
which months are missing rather than going blank.

**Why this priority**: it is the feature, and it is the term the owner named. A candidate at a
nominal 14.9% against a declared 10% belief returns 4.5% in purchasing power — a gap larger than
every route cost in the comparison put together.

**Independent Test**: answer the owner's question over the shipped root and read the
twelve-month section against the worked example below.

**Acceptance Scenarios**:

1. **Given** the shipped root and a declared inflation belief, **When** the owner's question is
   answered, **Then** every evaluated candidate whose span holds at least one elapsed month
   carries a real slot whose assumed half is a real rate matching the hand-computed deflation
   within the project tolerance, and whose realized half names the months of the window the CPI
   series does not declare. A span inside one month refuses on **both** halves for holding no
   elapsed month — the shared refusal, decided before either half is computed.
2. **Given** the same answer, **When** a real figure is read, **Then** it states the window it
   was deflated over, what it is real against, and whether it rests on observed CPI or on a
   declared belief — and it is a different type from the nominal figure beside it.
3. **Given** a candidate whose `implied_rate` is `RateNotComparable`, **When** the outcome is
   read, **Then** both halves of the real slot are typed-unavailable saying there is no nominal
   figure to deflate — distinct from there being no deflator.
4. **Given** a run with no inflation belief declared, **When** a candidate is evaluated,
   **Then** the assumed half is typed-unavailable naming the absent declaration, and no rate is
   assumed, defaulted or carried forward from the last published CPI month.

---

### User Story 2 - The real figure never moves an order (Priority: P1)

Adding the figure changes no ranking, no dominance verdict, no benchmark choice and no amount.
The comparison is ordered by what it was ordered by before; the real rate is reported beside the
nominal one and never sorted on.

**Why this priority**: equal-highest. It is Principle VI's display rule in another shape — a
figure added for the reader must not reorder the answer — and it is the cheapest defect here to
introduce and the hardest to notice.

**Independent Test**: answer with and without a declared belief and confirm the ranking, the
dropped set and every amount are bit-identical while the real slots differ.

**Acceptance Scenarios**:

1. **Given** two runs identical but for the declared inflation belief, **When** both are
   answered, **Then** every ranking, every `reaches`, every `implied_rate` and every refusal is
   bit-identical, and only the real slots differ.
2. **Given** the shipped root, **When** the candidate survey's recorded digest is taken,
   **Then** it is unchanged: that digest covers the key, the amount and the nominal rate, and
   this feature moves none of the three.

---

### User Story 3 - The mark survives the deflation (Priority: P2)

A real figure rests on both the nominal figure's inputs and the deflator's. Every unverified
mark and every staleness report on either side appears on it.

**Why this priority**: P2 only because Story 1's refusals already prevent the worst dishonesty.
Losing a mark in a transform is the top severity class regardless (Principle I).

**Independent Test**: derive a real figure over a marked nominal rate and an unverified belief,
verify one side, and confirm the other's mark survives.

**Acceptance Scenarios**:

1. **Given** an outcome whose provenance carries unverified sources, **When** its real figure is
   read, **Then** the figure carries those sources plus every source of the deflator.
2. **Given** a declared belief with no citation and a nominal figure resting on unverified
   sources, **When** the real figure is read, **Then** it is marked, and the run's manifest
   records which inflation declaration produced it.

---

### Edge Cases

- **A span shorter than one month** — the window contains no elapsed month, and both halves
  refuse by that name rather than by the coverage one; nothing is annualised over a span of no
  time. Not hypothetical: UA4000235865 pays its last coupon and its principal on 2026-09-16, the money
  arrives on 2026-09-19 after the declared exit latency, and the span hits this in all three of
  the owner's sections.
- **A belief above the nominal rate** — the real figure is negative and is reported as such,
  never clamped. That is the finding, not an error.
- **Two CPI series declared and neither named** — the realized half refuses naming both ids
  (FR-013a). Adding a second series stays a data-only change that loads; what it stops doing is
  silently deciding which index a figure is real against.
- **A tuple whose endpoint currency is not the base currency** — its `implied_rate` is already
  `RateNotComparable`, so both halves report there is nothing to deflate; the UA series could
  not have made a non-UAH figure real anyway (007's edge case).

## Requirements *(mandatory)*

### Functional Requirements

**The figure**

- **FR-001**: `TupleOutcome` MUST carry a real-terms slot of the **same record the hurdle
  carries** — a realized figure and an assumed figure, each `RealRate | RealTermsUnavailable`.
  The slot MUST be present on every evaluated outcome and MUST NOT be optional or absent.
- **FR-002**: The nominal figure deflated MUST be `implied_rate` and nothing else. Where
  `implied_rate` is `RateNotComparable`, both halves MUST be typed-unavailable reporting that
  there is no nominal figure to deflate — the reason 007 already distinguishes from "there is
  nothing to deflate by".
- **FR-003**: The tuple's real figure and the hurdle's MUST be produced by **one function**
  (007's `real_terms`). A second deflation site, a copy of the Fisher relation, or a local
  annualisation is a defect of the highest severity, not a refactoring opportunity.
- **FR-004**: Deflation MUST use the exact Fisher relation. The subtraction approximation MUST
  NOT be used, and the existing source scan forbidding it MUST cover every module this feature
  adds arithmetic to.
- **FR-005**: The deflation window MUST be derived by **one function over the two dates a rate
  is measured between**: the month **after** the month the money left, through the month the
  last flow landed in, inclusive. The tuple supplies `span.start` and `span.end` — the period
  `implied_rate` is a rate over — and the hurdle supplies its own pair, so neither caller's
  dates are hard-wired into the rule. The first month is excluded because a published index for
  month *M* measures the price change *during* *M*, and money that left on any day of *M* has
  already met *M*'s prices. The horizon MUST NOT be used: a span that ends early is deflated
  over the span, or the figure is charged for months in which the money was already back.
- **FR-006**: Both rates MUST be measured over the same span and annualised the same way.
  `implied_rate` is already annual; realized CPI is annualised over the window's own months; a
  declared belief is annual by declaration. Deflating an annual rate by a cumulative one is the
  units error this requirement exists to name.

**Which inflation, and what happens when there is none**

- **FR-007**: The two figures MUST NOT be mixed into one number, and neither may stand in for
  the other (007 FR-009, applied unchanged). No field anywhere may hold a number combining
  observed and assumed inflation.
- **FR-008**: Where the declared CPI series does not cover every month of the window, the
  realized half MUST be typed-unavailable **naming the missing months**. Nothing is
  interpolated, extrapolated, carried forward from the last published month, or computed over
  the covered part of the window.
- **FR-009**: Where no future-inflation assumption is declared, the assumed half MUST be
  typed-unavailable naming that absence. There MUST be no default belief, and no run may
  substitute one.
- **FR-010**: A figure resting on a declared belief MUST be labelled assumption-driven wherever
  it appears, and the outcome's stated assumptions MUST name the declaration it used. A cited
  external forecast is still an assumption (007 FR-015).

**Provenance**

- **FR-011**: A real figure MUST carry the union of the nominal figure's provenance and the
  deflator's — every CPI observation used, or the belief's own citation where it has one — and
  the merged staleness verdict over both sides. A transform that drops either is a defect of the
  highest severity.
- **FR-012**: The run manifest MUST record which price series and which declared belief were in
  force for an answered question, as it already does for a projection. Two runs differing only in
  the declared belief are two results, and the manifest is where a reader learns which is which.

**What the declarations do to get there**

- **FR-013**: The CPI series and the inflation assumption MUST reach tuple evaluation as
  **declared inputs**, both able to be absent, on the same record the evaluation already reads
  its other declarations from. Absence is a reported reason, never an error and never a default.
  Adding them MUST NOT require a new plugin interface.
- **FR-013a**: Which declared series deflates a figure MUST NOT be decided by load order, by
  file name, or by there happening to be only one. Where the run declares exactly one series it
  is that one; where it declares none the realized half reports that none was declared; where
  it declares more than one and the run names none, the realized half MUST be typed-unavailable
  saying so and naming the ids it could not choose between. 007 FR-002 makes a second series a
  data-only addition, and a rule that silently picks a deflator would make adding one change a
  figure with nothing to see.
- **FR-013b**: That choice MUST be made **inside** the one function that fills a real slot, not
  by a caller resolving a series before calling it. The refusals that apply to both halves —
  there is no nominal figure, the span holds no elapsed month — are decided first and outrank
  every deflator refusal, and a call site that resolved the series first would report *"could
  not choose a series"* where FR-002 requires *"there is nothing to deflate"*.

**The exclusion this retires, and the one it leaves**

- **FR-014**: The answer-wide `NO_REAL_TERMS_FIGURE` exclusion MUST be retired. It says every
  rate reported is nominal, which stops being true the moment this feature lands, and restating
  it per candidate would duplicate a refusal the figure already carries in more specific words.
  **This is a required change in feature 015**, named here rather than re-decided: 015 FR-023a's
  closed set loses a member and 015 SC-021's walk — which asserts that no real-terms figure
  appears anywhere in the answer — MUST be inverted to assert that every evaluated outcome
  carries one.
- **FR-015**: `TupleOutcome.excludes` MUST stop claiming that every figure it carries is
  nominal. What survives is true and narrower and MUST be stated in its place: the **amounts**
  — the outlay and what reaches a spendable endpoint — remain nominal, and only the rate has a
  real counterpart.
- **FR-016**: `TupleOutcome.accounts_for` MUST NOT gain a line. The nominal figure is not net of
  inflation; a second figure is reported beside it, and claiming otherwise would make the
  nominal rate read as deflated.

**Ranking, and what must not move**

- **FR-017**: The real figure MUST NOT be ranked on, compared on, or used to choose a benchmark.
  Ordering stays on the money and the days it was already on, and adding this field MUST change
  no order, no amount, no tax figure and no refusal. This is Principle VI's display rule in its
  own shape: a figure added for the reader never reorders the answer.
- **FR-018**: The candidate survey's recorded digest MUST NOT move. It covers the candidate key,
  the amount reached and the nominal rate, and this feature moves none of them; a digest that
  moved would mean a ranking input changed.

**What the result carries onward**

- **FR-019**: The real slot MUST enter the canonical form of an outcome, tagged so that a real
  rate and its absence can never produce the same bytes — the shape 007 already established. The
  answer golden's digest therefore moves; the diff MUST be read and the changed lines quoted in
  the landing commit (Principle V: a golden is evidence, never a freeze).
- **FR-020**: The published schema MUST gain the field with no hand-written model: it is derived
  from the annotated types, and every record newly reachable from the answer MUST have an
  injective wire tag. The web client is generated from that schema and reads declared data
  rather than the answer, so this feature requires no change under `web/`.
- **FR-021**: `docs/METHODOLOGY.md` §27 MUST gain the tuple's entry — which nominal figure is
  deflated, over which window, and why the ranking does not use it — in the same change as the
  implementation.

### Key Entities

- **Tuple real slot** — the realized and assumed real counterparts of `implied_rate`, the same
  record the hurdle carries.
- **Tuple deflation window** — the months of `span` (FR-005): the statement of what the figure
  covers, and the thing a reader checks a real rate against.
- **Declared inflation belief** — already declared and already a per-run passable input; this
  feature is its second consumer, not its author.

## The worked example

The owner's question, twelve-month section, UA4000236228 — 50 000 UAH from `salary_uah` through
`inzhur_direct`, out through `inzhur_to_monobank`. Measured over the shipped root at `as_of`
2026-08-30:

| | |
| --- | --- |
| span | 2026-09-01 .. 2027-03-13 (the issue redeems 2027-03-10; three days settle) |
| deflation window | 2026-10 .. 2027-03 — six months |
| nominal `implied_rate` | `0.14949567241454964` |
| declared belief | 10.0% per annum, `owner_placeholder_inflation` |

**Realized half** — the series covers 1991-08 .. 2025-10, so all six months are undeclared and
the figure is typed-unavailable naming 2026-10 through 2027-03.

**Assumed half** — the exact relation, both rates per annum. The numerator is written as the
sum it is computed from, because the decimal literal `1.14949567241454964` is a *different*
double from `1 + 0.14949567241454964` and the check below does not reproduce from it:

```
1 + nominal = 1.1494956724145498
real        = 1.1494956724145498 / 1.10 − 1 = 0.044996065831408805
```

Checkable by multiplying back: `1.10 × 1.044996065831408805 = 1.1494956724145498`, the
numerator exactly.

**And why the approximation is refused.** `0.14949567… − 0.10 = 0.04949567…`, which is
`1.10 ×` the exact figure — the approximation overstates the real return by exactly the
inflation rate, here **0.45 percentage points on a 4.50% figure, a tenth of the number
itself**. Both look like plausible real returns, which is what makes the wrong one dangerous
rather than merely inaccurate.

## Success Criteria *(mandatory)*

- **SC-001**: The worked example above is checked in with its arithmetic beside the assertion,
  and the engine reproduces the real figure within the single project tolerance.
- **SC-002**: Over the shipped root, 100% of evaluated candidates in every section carry a real
  slot — zero blanks, dashes, zeroes or omitted fields — and every realized half is
  typed-unavailable. Each names the months of *its own* window, so a candidate maturing in
  2027-03 and one running to 2027-09 name different sets; the twelve-month section produces at
  least three distinct sets. The exception is a span inside one month, which refuses for having
  no elapsed month and names none.
- **SC-003**: Two answers differing only in the declared belief agree bit-for-bit on every
  ranking, amount, nominal rate and refusal and differ only in their real slots; the candidate
  survey's recorded digest is identical in both and unchanged from before the feature.
- **SC-004**: A run with no belief declared produces a typed-unavailable assumed half on 100%
  of outcomes, naming the absent declaration; zero outcomes report a rate. A run declaring a
  second CPI series and naming neither refuses the realized half naming both ids, and changes no
  other figure.
- **SC-005**: With one input of a nominal figure unverified and the belief uncited, 100% of real
  figures derived from them carry the mark, in either direction.
- **SC-006**: A search of the answer finds no `NO_REAL_TERMS_FIGURE` exclusion and no
  `TupleOutcome` exclusion claiming every figure is nominal, and the walk that formerly asserted
  the absence of a real figure now asserts its presence.
- **SC-007**: The answer golden's digest moves, the diff is read, and every changed line is
  named in the landing commit; the candidate golden is byte-identical.
- **SC-008**: `docs/METHODOLOGY.md` gains the tuple's real-terms entry in the same change that
  implements it — verified by the change's own diff, not by a follow-up.
- **SC-009**: The published schema declares the new field and every newly reachable record has a
  unique tag; zero files under `web/` change.

## Assumptions

- **No new CPI or inflation values enter with this feature.** The series and the belief are
  already declared, and replacing the placeholder belief with the owner's own figure or a cited
  forecast stays a data-only change this feature does not perform.
- **The declared belief is a placeholder and says so** — ten percent, chosen so the arithmetic
  is checkable (`data/scenarios/inflation/owner-001.toml`). Every figure resting on it is
  conditional on it and marked; that is the point of the assumed half, not a weakness of it.
- **Feature 019 is not a dependency.** It ranks on money and days and does not read this figure;
  landing order between them is free.

## Required tests this feature relates to

- **F4** (*"the real-terms view uses UA CPI in the UAH display and US CPI in the USD display"*)
  **stays open**. Its second half is the display switch, which does not exist; this feature adds
  a second consumer of the UA half and closes nothing. No row in `docs/REQUIRED_TESTS.md` flips.

## Out of scope

Named so the plan does not drift into them: a **real-terms benchmark choice** — ranking or
choosing a benchmark on the real figure rather than reporting it; **CPI fetch automation**
(the `provider-automation` future, outside the package by 007's rule); **multi-currency
inflation** — a second series being consumed, and everything F4's display half asks for;
**forecasting of any kind**; real counterparts of any figure other than `implied_rate`, the
amounts included; and any change to how a nominal figure, a tax figure or a ranking is
computed.
