# Feature Specification: The full tuple

**Feature Directory**: `specs/010-full-tuple`

**Feature Branch**: none — this repo works on `main` by design

**Created**: 2026-08-22

**Status**: Ready for planning — all clarifications resolved 2026-08-22

**Input**: The full tuple — an instrument bought through a route from a stream, and the
comparison that is finally honest about it.

---

## Why this feature exists

The constitution's Principle VI names the product's unit of analysis:

```
(instrument) × (funding route in) × (tax treatment) × (exit route out) × (risk class)
```

Feature 001 computed the instrument-and-tax terms: an OVDP held to maturity produces a
hand-checkable schedule, exactly zero tax, and a hurdle rate. Feature 002 computed the
route terms: ramp cost per `(destination × stream × route)`, round trip from a declared
exit route, honest refusal where no exit is declared. **Nothing yet joins them.** The
hurdle rate carries an `excludes` field openly admitting it ignores funding and exit
route costs, and every route cost stops at a currency balance sitting at a venue —
nothing is ever *bought* with the money that arrived.

This feature is the join. An acquisition is funded from a declared income stream, moved
through a costed route, and becomes an instrument holding; the holding lives its declared
lifecycle and pays its declared tax; it exits on its own declared terms; and the proceeds
travel a declared exit route back to a spendable endpoint. What reaches that endpoint,
net of every one of those terms, is the tuple's outcome — and with it,
`SIMULATOR_SPEC.md` §8 question 1 — *"does anything beat 15.5% tax-free OVDP, after
every other option's fees, taxes and access costs?"* — finally has a computable answer
instead of a chart that flatters the expensive options.

The join is also where the constitution's own acceptance test lives. Required test
**H1** — a new instrument, route, tax class and jurisdiction added **in data only**
runs the full pipeline and appears in the comparison — cannot be attempted until a full
pipeline exists to run. This feature must close it, and if H1 cannot pass, the
abstraction is wrong somewhere behind us; finding that out is part of this feature's
job, not a risk to it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Compare a tuple against the hurdle, honestly (Priority: P1)

The owner names an amount, a stream, an instrument, a route in and a route out. The tool
runs the whole round trip — ramp in, purchase, lifecycle, tax, instrument exit, ramp out
— and reports what reaches the spendable endpoint, expressed both as an amount and as a
rate comparable against the hurdle, with the hurdle always shown beside it as the
benchmark.

**Why this priority**: this is the number the product exists to produce. Every earlier
feature was scaffolding for exactly this sentence: "after every access cost, this option
returns X against the hurdle's Y."

**Independent Test**: declare a synthetic instrument, a costed route in, and a declared
route out; hand-compute the full round trip — arriving amount, units bought, lifecycle
cash flows, tax, exit proceeds, exit ramp — and check every intermediate figure and the
final outcome against the checked-in arithmetic.

**Acceptance Scenarios**:

1. **Given** a declared stream, instrument, route in and route out, **When** the tuple
   is evaluated, **Then** the outcome equals the hand-computed composition of the four
   parts, and each part's contribution is separately visible in the result.
2. **Given** any tuple evaluation, **When** results are reported, **Then** the hurdle
   appears beside the tuple as the benchmark — always scored, always shown — and when
   the tuple does not beat it, the output says so plainly.
3. **Given** the OVDP bought through its zero-cost domestic route and exited the same
   way, **When** it is evaluated as a tuple through this same pipeline, **Then** its
   outcome agrees with feature 001's hurdle figure within the project tolerance — the
   benchmark is produced by the pipeline, never special-cased beside it.
4. **Given** a tuple whose figures are reported, **When** any figure is read, **Then**
   it states what it accounts for and what it excludes, and a figure net of access
   costs is labelled as such — the `excludes` admission of feature 001 becomes an
   `accounts_for` statement here.
5. **Given** a tuple and the hurdle whose outcomes differ by less than the project
   tolerance, **When** they are compared, **Then** the result is reported as a tie,
   never as a winner by a hair.

---

### User Story 2 - The join invents no numbers and hides no part (Priority: P1)

The round trip composes four declared parts: the route in (feature 002), the
instrument's lifecycle and tax (feature 001 and, later, 006-class instruments), the
instrument's own exit terms (redemption windows, exit commissions, haircuts), and the
route out to a spendable endpoint. Every part comes from a declaration; no part is ever
silently assumed zero or free.

**Why this priority**: equal-highest with Story 1, because a join that quietly zeroes a
missing part reproduces the predecessor's headline defect — a confident figure that
omitted the largest term in the decision. The join's honesty *is* the feature.

**Independent Test**: evaluate a tuple with each part's declaration removed in turn and
confirm each removal produces a typed refusal naming the missing declaration, never an
outcome computed with that part at zero.

**Acceptance Scenarios**:

1. **Given** a tuple whose destination has no declared exit route, **When** it is
   evaluated, **Then** the tuple is reported *exit cost unknown*, is not
   comparison-ready, and no one-way figure is promoted to stand in for the round trip —
   feature 002's FR-030, inherited whole.
2. **Given** a tuple whose instrument declares no exit terms, **When** it is evaluated,
   **Then** the same refusal applies at the instrument level: the way out is undeclared,
   the tuple is not comparison-ready, and the missing declaration is named. Exit is
   undeclared at *either* level, and the two refusals are distinguishable.
3. **Given** an instrument that declares exit terms — an exit commission, a redemption
   window, a haircut — **When** the round trip is computed, **Then** those terms appear
   as explicit recorded lines in the outcome, never blended in or assumed zero.
4. **Given** the arriving amount from the ramp, **When** the purchase is made, **Then**
   what is bought is bought with what actually arrived — never with the amount that
   departed — and any remainder the instrument's minimum ticket leaves unspent is
   reported as undeployed cash, never vanished.
5. **Given** a route whose ending currency or venue does not match what the instrument
   is bought with or where it is bought, **When** the tuple is evaluated, **Then** the
   mismatch is refused with both sides named, never silently bridged by a conversion
   nobody declared.

---

### User Story 3 - Cost stays keyed to the whole tuple (Priority: P1)

The same instrument is cheap from the USD stream and expensive from the UAH one, and the
comparison must carry that distinction all the way through the join. Access cost remains
per `(instrument × stream × route)`, and a per-instrument access cost stays
unrepresentable.

**Why this priority**: Principle VI forbids exactly one thing by name — quoting an
access cost per instrument — and the join is the first place the forbidden shortcut
becomes tempting, because a holding looks like it has "a" cost once the money is spent.

**Independent Test**: evaluate the same instrument purchase funded from the UAH stream
and from the USD stream and confirm the two tuples report different outcomes differing
by exactly the hand-computed ramp difference, and that no result anywhere attributes an
access cost to the instrument alone.

**Acceptance Scenarios**:

1. **Given** the same instrument reachable from two streams, **When** both tuples are
   evaluated, **Then** each carries its own access cost keyed to its stream and route,
   and the outcomes differ by exactly the hand-computed ramp difference.
2. **Given** any reported access-cost figure, **When** it is inspected, **Then** it
   names its instrument, stream and route — a cost attributable to an instrument alone
   is not representable in the result, extending feature 002's FR-008 through the join.
3. **Given** one instrument reachable by more than one route from the same stream,
   **When** the tuples are compared, **Then** each route yields its own tuple with its
   own outcome, and the comparison never collapses them into one figure per instrument.

---

### User Story 4 - Marks survive the join (Priority: P2)

Every part of the round trip rests on declared values with provenance, and the tuple's
outcome inherits the weakest of them. An unverified yield, a stale premium, an
unverified fee — each mark propagates to the final figure and to the ranking built on
it.

**Why this priority**: Principle I's propagation rule is already enforced inside each
part; the join is a new figure-producing site, and a join that launders a mark is a
top-severity defect. P2 only because Stories 1–3 must exist before there is anything to
propagate through.

**Independent Test**: build a tuple with exactly one unverified value in each part in
turn and confirm the outcome carries the unverified mark in every case; age one value
past its declared staleness threshold and confirm the staleness surfaces on the outcome.

**Acceptance Scenarios**:

1. **Given** a tuple with any single unverified value in any of its four parts, **When**
   the outcome is produced, **Then** the outcome carries the unverified mark, and the
   comparison shows it.
2. **Given** a declared value aged past its kind's staleness threshold, **When** a tuple
   resting on it is evaluated, **Then** staleness surfaces on the outcome and on every
   figure derived from it, per feature 002's FR-025/FR-028.
3. **Given** a comparison containing marked and unmarked tuples, **When** it is
   presented, **Then** the marks are visible in the comparison itself, not only on the
   underlying figures.

---

### User Story 5 - H1: a new tuple, in data only (Priority: P2)

A new instrument, a new route, a new tax class and a new jurisdiction are added purely
as declarations — no engine edit — and a tuple built from them runs the full pipeline
and appears in the comparison beside the existing ones.

**Why this priority**: this is required test H1, the constitution's own acceptance test
for Principle II, and this feature exists partly to close it. P2 because the pipeline of
Stories 1–3 must exist before the data-only claim can be tested against it.

**Independent Test**: write declaration files for an instrument class the engine has
never seen, a route, a tax class and a jurisdiction; run the pipeline; confirm the new
tuple appears in the comparison with a complete outcome and that zero lines of source
changed.

**Acceptance Scenarios**:

1. **Given** a new instrument, route, tax class and jurisdiction declared purely as
   data, **When** the pipeline runs, **Then** the new tuple appears in the comparison
   with a complete round-trip outcome, and no source-code change was needed.
2. **Given** the new declarations, **When** any of them is malformed or carries an
   unknown field, **Then** loading fails naming file and field with no default
   substituted — feature 002's FR-024 discipline, applied to every declaration kind this
   feature reads.
3. **Given** that H1 cannot be made to pass for some declaration kind without an engine
   edit, **When** this is discovered, **Then** the finding is recorded as a defect in
   the abstraction behind this feature — a named gap with the offending seam — rather
   than worked around with a special case inside the join.

---

### Edge Cases

- **The ramp eats the advantage** — a tuple whose instrument out-yields the hurdle
  before access costs and under-performs it after. The comparison reports the honest
  verdict; this is the finding the product exists to surface, not an error state.
- **Fees or taxes exceed the amount at any stage** — reported as such, never clamped;
  the money never vanishes without a diagnostic (feature 002 FR-005, extended through
  the join).
- **Arriving amount below the instrument's minimum ticket** — the tuple is infeasible
  for that amount; reported with the minimum and the shortfall named, never rounded up
  and never silently dropped from the comparison.
- **A remainder after buying whole units** — undeployed cash, reported with its amount
  and location; it is part of the outcome (money that made the trip and bought nothing),
  not a discarded rounding artifact.
- **A tuple tied with the hurdle within tolerance** — a tie, reported as a tie. "Nothing
  beats the hurdle" must be sayable when it is true, including when it is true by a
  whisker in either direction.
- **Two tuples differing only in route** — ranked apart, each with its own outcome; the
  difference is attributable to the routes.
- **An instrument exit inside a redemption window versus a forced exit** — where the
  declaration distinguishes them, each is its own declared way out with its own terms; a
  forced-exit haircut is an explicit line, never a silent discount.
- **Exit latency** — the instrument's redemption window and the exit route's declared
  latency delay when money reaches the spendable endpoint; the delay is reported, never
  silently ignored — and it lowers the comparable rate, because the rate's span runs to
  money-at-endpoint (FR-015): waiting is a cost, inside the span, not a footnote beside
  it.
- **A closed or capped route in** — feasibility rules from feature 002 apply unchanged:
  the binding constraint is named, the declared fallback applies, every occurrence is
  reported.
- **The hurdle's own tuple carries an unverified mark** — the benchmark is not exempt
  from honesty rules; its mark shows in the comparison like any other (it is the
  expected first-run state of the OVDP yield).
- **Tax owed in base currency on an instrument held in another** — the tax term is
  computed in the tax currency at the declared official rate for the transaction date,
  per the three-currency-roles rule; a synthetic fixture may exercise this shape, but no
  real tax value is invented for it (see Assumptions).
- **An instrument whose currency the declared routes cannot reach** — no tuple exists;
  the absence is visible as an unreachable combination (feature 003's audit will count
  these), never a silently empty comparison.

## Requirements *(mandatory)*

### Functional Requirements

**The join**

- **FR-001**: The system MUST evaluate a **tuple** — a declared instrument, funded from
  a declared income stream, through a declared route in, exiting on the instrument's
  declared exit terms, through a declared route out to a spendable endpoint — as one
  composed round trip, and MUST report what reaches the endpoint.
- **FR-002**: The join MUST invent no numbers. Every term of the round trip comes from a
  declaration or from a figure an earlier feature already computes; the join composes
  them and MUST NOT introduce a rate, fee, or conversion of its own.
- **FR-003**: The purchase MUST be made with the **arriving** amount from the costed
  route in — never the departing amount — and the units acquired MUST respect the
  instrument's declared minimum ticket and unit size. A remainder the purchase cannot
  deploy MUST be reported as undeployed cash with its amount and location, never
  vanished and never silently swept into the outcome's rate as if invested.
- **FR-004**: A tuple's parts MUST chain: the route in ends where and in the currency
  the instrument is bought; the instrument's exit proceeds start where and in the
  currency the route out begins. A mismatch MUST be refused naming both sides, never
  silently bridged by an undeclared conversion or transfer.
- **FR-005**: Each part's contribution — ramp in, entry fees, lifecycle cash flows, tax,
  instrument exit terms, ramp out — MUST be separately visible in the outcome, so a
  reader can see which term dominates. "Most of the gap is the ramp, not the asset" is
  the sentence this feature exists to let the tool write about a *holding*, not only
  about a currency balance.

**No part silently zero**

- **FR-006**: The four parts MUST all come from declarations, and a missing declaration
  MUST produce a typed refusal naming it — never an outcome computed with the missing
  part assumed zero, free, or instantaneous.
- **FR-007**: A tuple whose destination has no declared exit route inherits feature
  002's FR-030 in full: *exit cost unknown*, not comparison-ready, no one-way figure
  promoted to stand in for the round trip.
- **FR-008**: An instrument with no declared exit terms MUST receive the same treatment
  at the instrument level: the tuple is not comparison-ready, and the refusal names the
  instrument and the missing declaration. The two exit-unknown cases — route-level and
  instrument-level — MUST be distinguishable, because they call for different
  observations.
- **FR-009**: Declared instrument exit terms — exit commissions, redemption windows,
  haircuts — MUST be applied as explicit recorded lines in the round trip. A declared
  zero is a value like any other and appears as a recorded zero line; only an *absent*
  declaration triggers FR-008.

**Keying and comparison**

- **FR-010**: A tuple's cost and outcome MUST be keyed per
  `(instrument × stream × route in × route out)`. A cost or outcome attributable to an
  instrument alone MUST NOT be representable — extending feature 002's FR-008 through
  the join without exception.
- **FR-011**: The comparison MUST rank comparison-ready tuples by after-tax,
  after-access outcome, and the hurdle MUST always be scored and always shown as the
  benchmark, including — especially — when nothing beats it, in which case the output
  says so plainly.
- **FR-012**: The hurdle's own benchmark figure in the comparison MUST be produced by
  this same pipeline — the OVDP evaluated as a tuple through its declared domestic
  routes — and MUST agree with feature 001's hurdle rate within the project tolerance.
  A benchmark computed by a privileged side channel would make the comparison
  unfalsifiable.
- **FR-013**: Outcomes within the project tolerance of each other — including a tuple
  against the hurdle — MUST be reported as ties, never resolved by decoration,
  enumeration order, or a tiebreak the owner did not ask for.
- **FR-014**: Every reported figure MUST state what it accounts for and what it
  excludes. A tuple outcome accounts for funding route costs, instrument fees, tax, the
  instrument's exit terms and the exit route; anything it still excludes (inflation, and
  the risk-class term per this feature's scope) MUST be stated on its face.
- **FR-015**: The comparison MUST present each tuple's outcome both as the amount
  reaching the spendable endpoint and as a rate comparable against the hurdle. That
  rate is a **money-weighted return over the tuple's actual span from first outlay to
  money reaching the spendable endpoint** — ramp latency and redemption latency sit
  *inside* the span, because waiting is a cost (owner decision, 2026-08-22). The
  comparability consequence is stated rather than assumed: the hurdle's benchmark
  figure in the comparison is produced by this same pipeline over the same horizon
  (FR-012), so hurdle-versus-tuple is rate-versus-rate over one span. Feature 001's
  standalone contractual yield-to-maturity remains what it is — a rate on the
  instrument's own dated flows — and is not redefined by this feature.
- **FR-025**: Every tuple in a comparison MUST be evaluated over **one common horizon,
  set by the owner for that comparison** (owner decision, 2026-08-22). The consequences
  are part of the requirement, not fine print:
  - An instrument maturing **before** the horizon needs an **explicitly declared
    continuation assumption** — reinvest on stated terms, or sit as cash — declared per
    comparison, never silently defaulted. Figures resting on it are marked
    assumption-driven, exactly like other stated assumptions.
  - An instrument that **cannot span** the horizon at all — a lock-up reaching past it,
    no way out before or at it — is reported **infeasible for that comparison**, with
    the binding term named, rather than silently truncated to whatever span it can
    manage.

**Feasibility and partial deployment**

- **FR-016**: Feature 002's feasibility rules apply unchanged on the way in and the way
  out: caps, minimums, latency, status and fallback policies bind, every binding
  constraint is named, and every fallback occurrence is reported.
- **FR-017**: An arriving amount below the instrument's declared minimum ticket makes
  the tuple infeasible for that amount; the refusal names the minimum and the shortfall,
  and the tuple's absence from the ranking is visible with its reason, never silent.
- **FR-018**: Partial deployment — a route cap forcing an acquisition to be split across
  multiple months of entries — is **deferred** (owner decision, 2026-08-22). This
  feature evaluates **single-shot acquisitions only**: an amount exceeding a route's
  monthly cap is handled by feature 002's fallback reporting — the excess reported with
  date, amount and reason, never silently deployed — and the tuple's outcome is computed
  on what the route actually allowed through. The seam is the acquisition itself: this
  feature's acquisition is **one dated purchase event**, and the later planning feature
  that brings staggered entry widens it to a dated series of ramp-and-purchase events
  under these same rules, without changing what a tuple or an outcome is.

**Provenance, honesty, data-only extensibility**

- **FR-019**: The unverified mark and staleness MUST propagate from every declared value
  in every part to the tuple's outcome and into the comparison. A join step that drops a
  mark is a top-severity defect.
- **FR-020**: Tax treatment MUST remain declared data — a tax class and jurisdiction
  named in declarations, resolved through the tax rules the pipeline already honours —
  and the tax term of every tuple MUST be traceable to the rule and declaration that
  produced it. No tax value originates in code or in anyone's memory.
- **FR-021**: Adding a new instrument, route, tax class or jurisdiction MUST be a
  data-only change that runs the full pipeline and appears in the comparison (required
  test H1). This MUST be demonstrated by an executable test using declarations the
  engine has never seen, with zero source lines changed.
- **FR-022**: Every declaration kind this feature reads MUST fail loudly at load on
  malformed, unknown, incomplete or duplicated fields, naming file and field, with no
  default substituted — feature 002's FR-024 discipline extended to instrument exit
  terms, tax class and jurisdiction declarations.
- **FR-023**: If closing H1 reveals that some addition cannot be data-only without an
  engine edit, the gap MUST be recorded as a named defect in the abstraction — which
  seam, which declaration kind, what edit it forced — and MUST NOT be papered over with
  a special case inside the join. Fixing the abstraction is in scope for this feature;
  hiding the finding is not.
- **FR-024**: Currency roles stay separate through the join: computation in the amounts'
  own currencies, tax in the tax currency at the declared official rate for the
  transaction date, and no display-currency behaviour of any kind in this feature.
  Amounts in different currencies are never silently combined at the join.

### Key Entities

- **Tuple (candidate)** — the unit of analysis: an instrument, a funding stream, a route
  in, the instrument's exit terms, a route out. The risk-class term is *declared* on the
  instrument but not scored in this feature.
- **Acquisition** — the purchase event: the arriving amount, the units bought, entry
  fees as explicit lines, undeployed remainder, and the dates.
- **Holding** — the instrument position the acquisition creates, living the lifecycle
  feature 001 (and later 006) declares: cash flows, tax events, and the declared ways
  out.
- **Instrument exit terms** — the declared way out of the instrument itself: exit
  commission, redemption window, haircut; possibly several declared ways out, each with
  its own terms. Absent terms mean not comparison-ready, never zero.
- **Round-trip outcome** — what reaches the spendable endpoint, as an amount and as a
  comparable rate; each part's contribution itemised; `accounts_for` and `excludes`
  stated; provenance and staleness carried.
- **Comparison** — the ranked set of comparison-ready tuples over one owner-set
  horizon, with the hurdle always present as the benchmark; ties reported as ties;
  excluded and infeasible tuples listed with their reasons rather than silently absent.
- **Continuation assumption** — what an instrument maturing before the comparison's
  horizon does with its proceeds until the horizon: reinvest on stated terms, or sit as
  cash. Declared per comparison, never defaulted; figures resting on it are marked
  assumption-driven.
- **Tax treatment** — a declared tax class within a declared jurisdiction, resolved to
  the tax term of the round trip; data, never code.
- **Spendable endpoint** — where the round trip ends, as feature 002 defines it (and
  feature 003 declares the list); this feature adds nothing to its definition.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A synthetic tuple's full round trip — ramp in, purchase, lifecycle, tax,
  instrument exit, ramp out — matches a hand-computed worked example, checked in beside
  the assertion, at every intermediate figure and at the outcome, within the single
  project tolerance.
- **SC-002**: The OVDP evaluated as a tuple through its zero-cost domestic routes
  reproduces feature 001's hurdle rate within the project tolerance, through the same
  pipeline as every other tuple.
- **SC-003**: Every comparison produced contains the hurdle as the benchmark — verified
  across every comparison the tests produce, not sampled — and a synthetic case where
  nothing beats it yields the plain honest verdict.
- **SC-004**: The same instrument funded from two streams yields two tuples whose
  outcomes differ by exactly the hand-computed ramp difference, and no figure anywhere
  attributes an access cost or outcome to an instrument alone.
- **SC-005**: Removing any one of the four parts' declarations produces a typed refusal
  naming the missing declaration; across a deliberate battery covering all four parts,
  no case produces an outcome with the missing part at zero. Route-level and
  instrument-level exit-unknown are distinguishable in the output.
- **SC-006**: A new instrument, route, tax class and jurisdiction added in data only run
  the full pipeline and appear in the comparison with zero source lines changed —
  required test H1, closed by an executable test.
- **SC-007**: With exactly one unverified value planted in each of the four parts in
  turn, the tuple's outcome carries the unverified mark in 100% of cases, and a value
  aged past its staleness threshold surfaces as stale on the outcome and in the
  comparison.
- **SC-008**: Two outcomes within the project tolerance — including tuple-versus-hurdle
  — are reported as a tie in every generated case, never as a ranked pair.
- **SC-009**: Every reported figure states what it accounts for and excludes — verified
  across the whole output, not sampled — and no one-way figure is ever presented where a
  round-trip figure belongs.
- **SC-010**: An arriving amount below the minimum ticket, a fee exceeding the amount,
  and a whole-unit remainder each produce the specified honest report — named
  constraint, explicit diagnostic, reported undeployed cash — with nothing clamped,
  rounded, or vanished, across a deliberate battery of such cases.

## Assumptions

- **Synthetic instrument fixtures until feature 006.** The only real instrument today is
  the OVDP. Worked examples and the H1 test use synthetic instruments declared as test
  data — synthetic yields, fees, exit terms and tax rates carrying fixture provenance,
  never a real citation attached to an invented number and never an invented number
  presented as a real one. Real REIT/MilTech declarations arrive with 006 and slot into
  this pipeline unchanged; that unchanged slotting is what H1 asserts.
- **A synthetic tax class is test data, not tax advice.** H1 requires adding a tax class
  and jurisdiction in data only; the fixture's rates are arbitrary and marked as
  fixtures. No real legal or tax value is introduced by this feature.
- **Routes are feature 002's declared routes.** Composed paths (004) will widen the
  candidate route set when they land; this feature takes whatever routes the registry
  can already cost, and nothing here depends on composition.
- **Coverage (003) is the audit, this is the evaluation.** Feature 003 reports which
  `(destination × stream)` pairs are comparison-ready from declarations alone; this
  feature refuses individually, at evaluation time, for the same reasons extended to the
  instrument level. The two must agree where they overlap, but neither depends on the
  other landing first.
- **The risk-class term is declared, not scored.** Tuples carry their instrument's
  declared risk class through to the output so the fifth term of Principle VI's tuple is
  visible, but no risk scoring, no two-tier risk model, and no risk-adjusted ranking
  happens here.
- **The FX tax asymmetry (required test F1) stays with the feature that introduces a
  real taxable foreign instrument.** This feature's synthetic fixtures may have the
  *shape* of a foreign-currency taxable instrument to prove the pipeline carries the tax
  currency correctly, but F1's hand-computed devaluation case needs real dated official
  rates and a real instrument, and is not claimed here.
- **One owner, no authentication; no delivery surface.** Results are produced and
  asserted by the test suite, as in every feature so far.

## Clarifications resolved

All three answered by the owner on 2026-08-22.

| # | Question | Decision | Where it landed |
|---|---|---|---|
| 1 | One common horizon per comparison, or each instrument's own span? | **One common horizon, set by the owner, for every tuple in a comparison.** An instrument maturing earlier needs an explicitly declared continuation assumption — reinvest on stated terms, or sit as cash — per comparison, never defaulted, with the resulting figures marked assumption-driven. An instrument that cannot span the horizon at all is infeasible for that comparison, never silently truncated. | FR-025, and the Continuation assumption entity |
| 2 | What is the comparable rate a rate *of*? | **A money-weighted return over the tuple's actual span from first outlay to money reaching the spendable endpoint** — ramp and redemption latency inside the span, because waiting is a cost. The hurdle's benchmark is the same pipeline over the same horizon (FR-012), so hurdle-versus-tuple is rate-versus-rate over one span; 001's standalone contractual YTM is not redefined. | FR-015, and the exit-latency edge case |
| 3 | Staggered multi-month entry under route caps — here or later? | **Deferred.** Single-shot acquisitions only; a cap-exceeding amount is handled by 002's fallback reporting, never silently deployed. The named seam: the acquisition is one dated purchase event, which the later planning feature widens to a dated series under the same rules. | FR-018 |

**The first decision has a consequence worth stating on its own.** A common horizon
makes the comparison honest about time but forces an assumption wherever maturities
differ — and the decision routes that force into daylight rather than around it. The
continuation assumption is a *stated, editable, visibly consequential* assumption in
exactly §1.3's sense; the alternative — comparing each instrument over its own span —
would have compared rates measured over different times as if they were the same kind
of number, which is quieter and wrong.

## Required tests this feature closes

| Row | What it asserts |
|---|---|
| **H1** | A new instrument, route, tax class and jurisdiction added in data only runs the full pipeline and appears in the comparison |

H1 is a compliance test for Principle II and may not be skipped or weakened without a
constitution amendment. Rows G4–G6 remain with feature 002; I4 (naive baseline
strategies always scored) belongs to the decision layer, though this feature's FR-011
builds the hurdle-always-shown half of its foundation.

## Out of scope

Named explicitly so the plan does not drift: the decision layer and candidate generation
(objectives, constraints, optimisation, Monte Carlo, strategy shortlists); risk classes
as a *modelled* dimension — the tuple's fifth term is declared and displayed, never
scored; the display-currency switch; inflation and real-terms figures (feature 007 fills
the reserved slot); live data of any kind; portfolio-level anything — this feature
evaluates one tuple at a time and compares tuples, not allocations; and any user
interface, web or command-line.

Also out of scope, and stated so the temptation is visible: **automatic route
selection inside the tuple**. Feature 002's FR-016 ranking recommends a route for
moving money; this feature does not fold that recommendation into the tuple silently —
every tuple names its routes explicitly, and comparing an instrument "via its best
route" is candidate generation, which belongs to the decision layer.
