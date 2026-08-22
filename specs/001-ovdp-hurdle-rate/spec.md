# Feature Specification: The OVDP hurdle rate

**Feature Directory**: `specs/001-ovdp-hurdle-rate`

**Feature Branch**: none — the spec-kit git extension is not installed, so no branch was created automatically

**Created**: 2026-08-21

**Status**: Ready for planning — all clarifications resolved 2026-08-21

**Input**: The OVDP hurdle rate — a thin vertical slice that establishes the ledger kernel and makes the project's benchmark number real.

---

## Why this feature exists

`SIMULATOR_SPEC.md` §3.1 makes a claim the whole product rests on: a Ukrainian
government bond bought through Inzhur costs **0% to enter** and is taxed at **0%**, so
its yield is "the hurdle rate every other option must beat". Every later comparison —
crypto ramps, foreign ETFs, Inzhur funds — is measured against that number.

Right now that number exists only in a document. This feature makes it a computed,
traceable, hand-checkable result. It is deliberately the thinnest slice that produces a
figure the owner can act on, and in doing so it forces the foundations everything else
needs — traceable transaction records, per-lot cost basis, currency safety, declared
tax classes, and provenance that propagates — to exist under a test a human can verify
with a calculator.

It answers question 1 of `SIMULATOR_SPEC.md` §8 in its simplest form: *what exactly is
the bar?*

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Know the hurdle rate (Priority: P1)

The owner states a purchase of a specific OVDP issue — how much, on what date, at what
price — and holds it to maturity. The tool returns the complete dated schedule of money
received: each coupon, the principal at maturity, the tax charged on each (zero, because
the issue is exempt), and the resulting effective annual return in hryvnia. The result
is labelled as the benchmark that other options must beat.

**Why this priority**: This is the entire value of the slice. Without it there is no
number, and every later comparison has nothing to compare against. It is also the
smallest thing that is genuinely useful on its own — the owner can read the schedule and
decide whether to buy.

**Independent Test**: State a purchase with known terms, hold to maturity, and check
every cash flow and the final return against arithmetic worked out by hand on paper.
Delivers a decision-ready answer to "what does this bond actually pay me?"

**Acceptance Scenarios**:

1. **Given** an OVDP issue with a stated yield, maturity date and coupon terms, and a
   purchase of a stated amount on a stated date, **When** the holding is projected to
   maturity, **Then** the schedule of coupon payments and principal repayment matches
   the hand-computed schedule, and the total tax charged over the life of the holding is
   exactly zero.
2. **Given** the same holding, **When** the effective annual return is reported,
   **Then** it is expressed in hryvnia, is explicitly identified as the hurdle rate, and
   states that it is an after-tax figure.
3. **Given** a purchase amount below the issue's minimum ticket, **When** the holding is
   projected, **Then** the tool reports the purchase as infeasible and names the minimum
   ticket and the shortfall, and does not silently round the amount up or down.
4. **Given** a maturity date earlier than the purchase date, **When** the holding is
   projected, **Then** the tool reports the inconsistency and produces no schedule.

---

### User Story 2 - Trust the number (Priority: P1)

Every figure the tool shows can be opened up: which payments produced it, which rule
taxed it, where each input value came from, and whether that input has been verified.
An input nobody has verified against a primary source visibly marks the figure it feeds,
and every figure downstream of it.

**Why this priority**: Equal-highest with Story 1, because a number the owner cannot
check is worse than no number — that is precisely the failure the predecessor project
made and this one exists to avoid. The headline 15.5% yield is an owner-reported,
unverified observation, so the very first result this tool produces will carry a mark.
The marking mechanism therefore cannot be deferred; it ships with the first figure.

**Independent Test**: Take any figure in the output and follow it back to the payments
and the rule behind it, then to each input's source and verification date. Deliberately
leave an input unverified and confirm that every figure derived from it is marked.

**Acceptance Scenarios**:

1. **Given** a completed projection, **When** any reported monetary figure is inspected,
   **Then** the transactions that produced it can be enumerated, and each carries the
   rule or instrument term that generated it.
2. **Given** an instrument whose yield has no verification date, **When** the projection
   runs, **Then** the yield, the schedule, the return figure and every other figure
   derived from that yield are all marked as resting on an unverified input.
3. **Given** a tax figure, **When** it is inspected, **Then** it names its tax class,
   its cited source, and its verification date.
4. **Given** an amount in hryvnia and an amount in dollars, **When** something attempts
   to combine them, **Then** the attempt fails as an error and no implicit conversion
   occurs.
5. **Given** an identical set of inputs, **When** the projection is run twice, **Then**
   both runs produce identical results, and each result records the inputs and their
   versions.

---

### User Story 3 - Reinvest the coupons (Priority: P2)

Coupons do not have to sit as idle cash. The owner chooses whether each coupon is held
as cash or used to buy more of the same instrument at the yield available on that date,
and sees the difference the choice makes.

**Why this priority**: Compounding is most of the long-horizon difference between two
otherwise identical fixed-income plans, and `SIMULATOR_SPEC.md` §3.1 requires that
future purchases be priced off a yield curve rather than a single constant. But Story 1
is decision-useful without it, so it follows rather than blocks.

**Independent Test**: Run the same purchase twice, once holding coupons as cash and once
reinvesting them, and check the two-period reinvestment arithmetic by hand.

**Acceptance Scenarios**:

1. **Given** a holding whose coupons are reinvested at the yield available on each
   coupon date, **When** two coupon periods have elapsed, **Then** the resulting position
   matches the hand-computed two-period example.
2. **Given** the same holding with coupons held as cash instead, **When** the projection
   completes, **Then** the terminal amount is lower than the reinvesting case by the
   compounding forgone, and the cash sits in a hryvnia cash balance.
3. **Given** a coupon too small to buy a whole unit of the instrument, **When**
   reinvestment is attempted, **Then** the unbought remainder is reported and held as
   cash rather than silently discarded or silently allowed to buy a fractional unit.

---

### User Story 4 - Add another issue without touching the engine (Priority: P3)

A second OVDP issue — different yield, different maturity, different coupon frequency —
is added by writing a declaration file. No code changes, no new branches in the engine.
It then appears in results exactly like the first.

**Why this priority**: This is the framework claim from the constitution's Principle II,
and the point at which the project stops being one person's script. It is P3 only
because it is verified rather than built: if Stories 1–3 are built correctly, this
already works, and this story's job is to prove it.

**Independent Test**: Add a declaration file for a second issue and run the full
projection on it without editing any source file.

**Acceptance Scenarios**:

1. **Given** a new issue declared purely as data, **When** the projection runs, **Then**
   it produces a complete schedule and return figure with no source-code modification.
2. **Given** a declaration file containing a misspelled or unrecognised field, **When**
   it is loaded, **Then** loading fails with an error naming both the file and the
   offending field, and no default value is substituted.
3. **Given** a declaration referring to a tax class that does not exist, **When** it is
   loaded, **Then** loading fails naming the missing class, rather than treating the
   holding as untaxed.

---

### Edge Cases

- **Purchase below the minimum ticket** — reported as infeasible with the shortfall
  named; never silently adjusted (Story 1, scenario 3).
- **Maturity on or before the purchase date** — an inconsistency, not a zero-length
  schedule.
- **Zero or negative purchase quantity** — rejected as invalid input.
- **A coupon date that is not a business day** — the schedule must state which
  convention it applied rather than silently picking one.
- **An issue whose yield is missing entirely** (not merely unverified) — refused, since
  no schedule can be computed; distinct from the unverified-but-present case, which
  proceeds under a mark.
- **A declaration file that is not valid syntax** — fails naming the file.
- **A tax class declared with a non-zero rate but applied to an exempt instrument** —
  the instrument's declared class governs; any conflict is reported rather than
  silently resolved.
- **Two instruments declaring the same identifier** — a collision, reported at load
  time.
- **A holding still open at the end of the projection horizon** — reported as open with
  its remaining schedule, never implicitly liquidated.

## Requirements *(mandatory)*

### Functional Requirements

**The schedule and the number**

- **FR-001**: The system MUST accept a declared holding of a fixed-income instrument —
  identified issue, purchase amount or quantity, purchase date and cost — and produce the
  complete dated schedule of cash flows from purchase to maturity.
- **FR-002**: Each cash flow in that schedule MUST reproduce hand-computed arithmetic
  within a single project-wide precision tolerance that is defined in exactly one place.
  No individual comparison may define its own tolerance; one that requires a looser
  tolerance MUST state why where the comparison is made.
- **FR-003**: The system MUST apply the tax class declared by the instrument to each cash
  flow, and for a class declared exempt MUST charge exactly zero on both coupon income
  and any gain.
- **FR-004**: The system MUST report the effective annual after-tax return of the holding
  in hryvnia, and MUST label it as the hurdle rate against which other options are
  measured.
- **FR-005**: The system MUST report both a contractual yield-to-maturity and a
  cash-flow-weighted return, kept as separate figures and separately labelled, and MUST
  NOT present either as a substitute for the other.
- **FR-023**: ⚙ **Added after review.** Of the two figures FR-005 requires, the
  **contractual yield-to-maturity** is the hurdle rate that later features compare against,
  and the system MUST identify it as such. The two are not interchangeable and the choice is
  not arbitrary:
  - the contractual yield is a property of the **paper**, invariant to what the owner does
    with the coupons, so it is stable enough to be a benchmark;
  - the cash-flow-weighted return describes **one particular plan** — it moves with the
    coupon policy, the purchase size and the timing — so a comparison against it would
    measure the plan as much as the alternative.

  This ambiguity was real and it had already cost something: `nominal_ytm` shipped moving
  with the coupon policy, correctly computed under a wrong label, and passed review twice
  before implementation of feature 002 caught it. FR-004 speaking of "the hurdle rate" in the
  singular while FR-005 required two figures is what left room for that.
- **FR-022**: The hurdle-rate figure MUST be reported in nominal terms in this feature,
  and MUST state on its face that it is nominal and excludes inflation. The result
  structure MUST carry a defined, currently-unpopulated place for the corresponding
  inflation-adjusted figure, so that adding real terms in a later feature does not change
  the shape of the result or anything that consumes it. The system MUST NOT present a
  nominal figure as though it were a real one, and MUST NOT compute a real figure from an
  assumed inflation rate.

**Money and currency**

- **FR-006**: Every monetary amount in the system MUST carry the currency it is
  denominated in.
- **FR-007**: Any attempt to add, subtract or compare monetary amounts of different
  currencies MUST fail as an error. Implicit conversion MUST NOT occur anywhere.

**Traceability**

- **FR-008**: Every reported figure MUST be traceable to the transaction records that
  produced it, and each such record MUST identify the instrument term or tax rule that
  generated it. A figure that cannot be traced MUST NOT be reported.
- **FR-009**: Cash MUST be conserved: for each currency, on every date, total inflows
  minus total outflows MUST equal the recorded cash balance.
- **FR-010**: Holdings MUST be recorded as individual lots carrying acquisition date and
  cost, and the sum of lot quantities MUST equal the position quantity while the sum of
  lot costs MUST equal the position cost basis, at every point in the projection.
- **FR-011**: When a holding is disposed of, the realised gain MUST equal proceeds minus
  the cost basis consumed minus fees allocated to the disposal, and MUST be computed in
  both the instrument's own currency and the base currency.
- **FR-012**: A projection MUST be reproducible: the same inputs MUST produce identical
  results, and each result MUST record the inputs and their versions.

**Declared knowledge, not coded knowledge**

- **FR-013**: Instruments and tax classes MUST be declared in data files. Adding another
  bond issue, or another instrument sharing an existing tax class, MUST NOT require any
  source-code change.
- **FR-014**: Every observed value in a data file MUST carry the value itself, the source
  it came from, the date it was retrieved, and the date it was verified against a primary
  source. The verification date MAY be empty; the field MUST NOT be absent.
- **FR-015**: A value with an empty verification date MUST be marked as unverified, and
  every figure computed from it MUST carry that mark. A transform that drops the mark is
  a defect of the highest severity.
- **FR-016**: Loading a data file MUST fail loudly on a malformed value, an unrecognised
  field, a missing required field, a duplicate identifier, or a reference to an
  undeclared tax class — naming both the file and the offending field. A default value
  MUST NOT be substituted for anything absent.
- **FR-021**: Coupon periodicity, the day-count convention, and the rule applied when a
  coupon date falls on a non-business day MUST all be declared **per issue** in the
  instrument's data file. They MUST NOT be fixed in the engine, because a second issue
  using different terms has to be a data-only addition (FR-013). The produced schedule
  MUST state which convention it applied, and an unrecognised convention name MUST fail
  at load time naming the file and the value — never fall back to a default convention.

**Explicit failure**

- **FR-017**: Any outcome the system cannot compute normally MUST be returned as a
  typed result carrying the reason, and that reason MUST appear in the output. The
  system MUST NOT clamp a value to zero, substitute a default, or return an empty
  result to represent a failure.
- **FR-018**: A purchase that violates the instrument's declared constraints MUST be
  reported and MUST NOT be silently adjusted to fit. Two cases, kept distinct — the
  first draft of this requirement collapsed them, and implementation showed the
  collapse does not hold:
  - **Below the minimum ticket** — a *shortfall*: the purchase is well-formed and simply
    too small. Reported as infeasible, naming the constraint, the required amount, the
    actual amount and the difference. A larger purchase would succeed.
  - **Non-positive quantity, or dates that contradict each other** — not a shortfall but
    *invalid input*. There is no amount that "would have been enough", and inventing one
    to fill a shortfall field would mean fabricating a price. Reported as inconsistent
    terms, naming what contradicts what. This matches the spec's own Edge Cases, which
    already call these "invalid input" rather than infeasible.

  Both are typed results carrying their reason, so nothing is lost by the distinction —
  what is gained is that neither has to pretend to be the other.

**Reinvestment**

- **FR-019**: The system MUST support a declared coupon policy of at least "hold as
  cash" and "reinvest at the yield available on the coupon date", and the two MUST
  produce different, separately checkable results.
- **FR-020**: When a coupon cannot be fully reinvested because of the instrument's
  minimum unit, the unreinvested remainder MUST be reported and retained as cash.

### Key Entities

- **Instrument declaration** — a data file describing one investable thing: its
  identifier, class, currency, the terms that generate its cash flows, its constraints
  (minimum ticket), and the tax class that applies to each kind of income it produces.
  Every observed value in it carries provenance.
- **Bond issue terms** — for a fixed-income instrument: yield, maturity date, coupon
  frequency, face value and the conventions used to place coupon dates.
- **Tax class** — a named, declared rule stating what is charged on a kind of income,
  with its cited source and verification date. `ua_government_bond` is the exempt class
  this slice needs.
- **Provenance record** — the value, its source, its retrieval date and its verification
  date, attached to every observed input and carried through every derived figure.
- **Holding lot** — a quantity of an instrument acquired on a date at a cost, recorded
  in both the instrument's currency and the base currency. Costs and quantities are
  tracked per lot because tax is computed per disposal, not on an average.
- **Cash balance** — money held, per currency, that is not invested. Coupons land here,
  purchases are paid from here.
- **Transaction record** — one dated, typed event that moved money or changed a holding,
  carrying the rule or term that caused it. The audit trail behind every figure.
- **Cash-flow schedule** — the dated sequence of amounts a holding will pay, with the
  tax charged on each and its provenance marks.
- **Run record** — what a projection was given: which declarations at which versions,
  which policies, and the resulting figures, sufficient to reproduce the result exactly.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a stated OVDP purchase held to maturity, every cash flow in the
  produced schedule matches an independently hand-computed schedule to within the single
  project tolerance, and the arithmetic is recorded alongside the check.
- **SC-002**: The total tax charged across the entire life of a holding in the exempt
  class is exactly zero — not approximately zero.
- **SC-003**: A second bond issue with different terms is added and produces a complete
  result with **zero** lines of source code changed.
- **SC-004**: Every malformed, unrecognised, missing or duplicated field in a
  declaration file produces an error naming the file and the field. No such case
  results in a substituted default — measured across a deliberate battery of broken
  files.
- **SC-005**: With one input left unverified, 100% of figures derived from it carry the
  unverified mark, and no derived figure appears unmarked.
- **SC-006**: Two runs on identical inputs produce identical results, verified by
  comparing a digest of the complete output.
- **SC-007**: Every monetary figure in the output can be resolved to the transaction
  records behind it, and each record to the term or rule that produced it — with no
  unresolvable figures.
- **SC-008**: No combination of amounts in different currencies ever succeeds; every
  attempt is an error.
- **SC-009**: Cash conservation, lot conservation and basis conservation hold across a
  large body of randomly generated valid holdings and dates, not merely on the worked
  examples.
- **SC-010**: The reinvesting and cash-holding coupon policies produce different
  terminal amounts on the same purchase, and the two-period reinvestment case matches
  hand-computed arithmetic.
- **SC-011**: Every returned return figure is labelled nominal, and the slot reserved for
  the inflation-adjusted figure is present and explicitly empty — never absent, and never
  filled with a nominal value standing in for a real one.
- **SC-012**: Two issues declaring different coupon periodicities and day-count
  conventions both produce correct schedules with no source-code change, and each
  schedule reports the convention it applied.

## Assumptions

- **The 15.5% yield is unverified and enters as such.** `SIMULATOR_SPEC.md` §11 item 2
  records that the real issue's yield and maturity are not confirmed. It is entered as
  an owner-reported, dated observation with an empty verification date, and the resulting
  hurdle-rate figure will therefore be marked. This is the expected first-run state, not
  a defect, and no verified figure is invented to avoid it.
- **Hold-to-maturity only.** Secondary-market sale of a bond before maturity, and the
  thin-market haircut that would apply, are out of scope for this slice.
- **No routes, no venues.** The purchase is taken as given. The 0% Inzhur entry fee is
  an instrument-level term here; funding routes, income streams and FX channels are
  later features, and this slice adds no branches for them.
- **Single currency in practice.** Every amount in this slice is hryvnia. Currency
  tagging and the prohibition on mixing currencies are built now because retrofitting
  them later is expensive, but no conversion, rate source, or display switch is part of
  this feature.
- **Nominal figures only.** Per the resolved clarification, inflation is excluded from
  this slice and the figure is labelled nominal. The result keeps a defined empty slot for
  the real figure.
- **The worked example runs against a labelled synthetic issue.** Because the real
  issue's terms are not yet confirmed, the hand-computed acceptance example uses a
  fixture issue whose yield, maturity, periodicity and conventions are stated in the test
  itself and marked plainly as synthetic. This is legitimate: the example tests the
  engine's arithmetic, not the market. The real issue is then added as a data file
  carrying its own provenance, and nothing about it is invented to make the example work.
- **One owner.** Records carry an owner identifier per the constitution, but there is no
  authentication, no second user, and no per-user storage in this slice.
- **No delivery surface.** No web interface and no command-line interface. The result is
  produced and asserted by the test suite; presentation is a later feature.

## Clarifications resolved

Both questions raised during specification were answered by the owner on 2026-08-21.

| # | Question | Decision | Where it landed |
|---|---|---|---|
| 1 | Coupon periodicity, day-count convention, non-business-day handling | **Declared per issue as data**, not fixed in the engine. The worked example runs against a clearly-labelled synthetic issue with stated terms; real issue terms are added as data once confirmed from the Inzhur listing. | FR-021 |
| 2 | Nominal or inflation-adjusted hurdle rate | **Nominal only**, stated as such on its face, with the result structure carrying a defined empty slot for the real figure so a later feature can fill it without changing the result's shape. | FR-022 |

The second decision leaves a known incompleteness on purpose: a nominal 15.5% against
double-digit inflation is a materially different proposition, and the output says so
rather than implying otherwise. Closing that gap is the job of the feature that
introduces CPI.

## Required tests this feature closes

Rows in `docs/REQUIRED_TESTS.md` that must be flipped, with their test paths recorded,
before this feature is done:

| Row | What it asserts |
|---|---|
| **C1** | Cash conservation per currency per day |
| **C2** | Lot conservation |
| **C3** | Basis conservation; realised gain in both currencies |
| **C4** | Determinism — identical inputs, identical output digest |
| **C5** | Currency safety — different currencies never combine |
| **C6** | Every figure traceable to transaction records |
| **D1** | OVDP held to maturity: hand-computed schedule, zero tax |
| **D2** | Coupon reinvestment matches a hand-computed two-period example |
| **E5** | Tax figures carry source and verification date; the mark propagates |
| **H2** | A malformed or unknown field fails loudly, naming file and field |

C1–C6 and H2 are compliance tests for the constitution and may not be skipped, marked
expected-to-fail, or deleted without an amendment.

## Out of scope

Named explicitly so the plan does not drift into them: funding and exit routes, income
streams, FX channels and rate sources, the display-currency switch, inflation and CPI
(pending FR-022), the decision layer and candidate generation, objectives and
constraints, Monte Carlo, historical replay, market-priced instruments and return
models, statistical risk metrics, the web interface, and the command-line interface.
