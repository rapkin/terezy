# Feature Specification: Inzhur instruments and dated tax schedules

**Feature Directory**: `specs/006-inzhur-instruments`

**Feature Branch**: `spec/006-inzhur-instruments`

**Created**: 2026-08-22

**Status**: Ready for planning — all clarifications resolved 2026-08-22

**Input**: Inzhur instruments — the REIT and MilTech as declared instruments, and tax
rates that change on a date. Declare the two Inzhur products (`SIMULATOR_SPEC.md` §3.2,
§3.3) as data — distribution terms, commissions, liquidity terms, tax treatment — with
one instrument carrying two tax classes at once (required test E1), tax rates as dated
schedules (required test E10), and exits outside the declared terms refused or executed
at the declared haircut (required test J3).

---

## Why this feature exists

Feature 001 proved the instrument machinery on one exempt bond and produced the
benchmark: a tax-free hurdle rate every other option must beat. The registry still
holds nothing to compare it against. The two Inzhur funds are the nearest real
alternatives the owner can actually buy, and they are the first instruments that
exercise the machinery 001 deliberately built wider than it needed: an instrument
whose distributions and redemptions are taxed under *different* classes at once, an
instrument whose income is declared in one currency while its money moves in another,
and product terms that come from fund documents rather than bond arithmetic.

The tax content is the sharp part, and one piece of it is a recorded debt: 001's tax
schema carries a scalar rate per class, while `data/README.md` rule 3 and
`SIMULATOR_SPEC.md` §4.5.1 require every rate to accept a **dated schedule** so a
legislated change is modelled rather than requiring a rebuild. Ukrainian tax law in
exactly this area changed recently — the military levy went from 1.5% to 5% in
December 2024 — so this is not hypothetical future-proofing; it is the shape the
domain already has. This feature pays that debt (required test E10).

The honesty constraints shape everything else. The product terms were researched from
the funds' **primary public documents** — both funds' регламент and проспект, read in
full (accessed 2026-08-22) — but researched is not verified: every value enters the
declarations with its citation and an **empty verification date** until the owner
checks it against his investor cabinet, and the mark propagates
(`SIMULATOR_SPEC.md` §11 item 2). And they are assumption-driven instruments: no
volatility, no Sharpe ratio, no statistical metric may ever be emitted for them
(constitution Principle I). Their projections are contractual arithmetic over declared
terms — nothing more is claimed, and the output says so.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Both taxes in one run (Priority: P1)

The owner states a holding of Inzhur REIT certificates, receives distributions during
the holding period, and redeems the units at the end. The tool taxes the distributions
under the fund-distribution class and the redemption gain under the investment-profit
class — two different treatments, applied in one projection to income from one
instrument — and shows which class charged what, so the owner sees that a fund payout
and a fund exit are not taxed alike.

**Why this priority**: This is the reason the feature exists. The two-class split is
the single largest tax fact about these products (`SIMULATOR_SPEC.md` §3.2, §4.5), it
is required test E1, and 001's per-event-kind tax mapping was built for exactly this
case but has never carried two distinct classes. Without it, any Inzhur figure the
tool showed would be wrong in the way the predecessor was wrong: confidently omitting
the tax split. The REIT's own page corroborates the split — it shows dividend
withholding of 14% (9% PIT + 5% levy), exactly the fund-distribution class.

**Independent Test**: Project a holding with at least one distribution and one final
redemption, and check each charge — and the per-class subtotals — against arithmetic
worked out by hand on paper.

**Acceptance Scenarios**:

1. **Given** a fund holding that declares one tax class for distributions and a
   different one for disposal, **When** a projection includes both a distribution and
   a redemption of the same units, **Then** each event is taxed under its own declared
   class, the per-class subtotals match hand-computed arithmetic, and neither class's
   rate is ever applied to the other's events.
2. **Given** the same projection, **When** the tax on the redemption is computed,
   **Then** its base is the proceeds actually received minus the cost basis consumed
   minus fees allocated to the disposal — not the gross redemption amount.
3. **Given** a redemption at a loss, **When** the disposal tax is computed, **Then**
   the charge is zero — never negative — and the realised loss is reported together
   with an explicit statement that loss carryforward is not modelled in this feature.
4. **Given** any tax figure in the output, **When** it is inspected, **Then** it names
   the tax class that produced it, that class's cited source, and its verification
   date.

---

### User Story 2 - A rate that changes on a date (Priority: P1)

A tax rate is not a constant; it is a schedule. The owner declares that a class's rate
changes on a legislated effective date, and a projection whose events straddle that
date charges the old rate on events before it and the new rate on events from it —
in the same run. When the law changes again, the owner adds one dated entry to a data
file and nothing is rebuilt.

**Why this priority**: Equal-highest with Story 1 because it is a recorded gap, not a
new idea: `data/README.md` rule 3 already states the requirement and admits the schema
does not meet it (required test E10). Every tax figure Story 1 produces becomes
untrustworthy the day a rate changes unless this exists — and rates in exactly this
area changed within the last two years.

**Independent Test**: Declare a schedule with two dated entries, run a projection with
taxable events on both sides of the effective date, and check both charges by hand;
then add a third entry as a data-only edit and confirm it takes effect with no other
change.

**Acceptance Scenarios**:

1. **Given** a tax class whose rates are declared as a dated schedule with an entry
   effective mid-projection, **When** taxable events fall before and after that date,
   **Then** events before the effective date are charged at the earlier entry's rates
   and events on or after it at the later entry's rates, in one run, matching
   hand-computed arithmetic.
2. **Given** a legislated rate change, **When** it is entered, **Then** it is one
   dated entry added to a data file — carrying its own source, retrieval date and
   verification date — with no source-code change.
3. **Given** a taxable event dated before the schedule's earliest entry, **When** the
   projection runs, **Then** the outcome is a typed error naming the tax class and the
   event date; no rate is defaulted and no zero is silently charged.
4. **Given** the existing exempt class carried into schedule form, **When** feature
   001's worked example is re-run, **Then** its results are unchanged and its total
   tax is still exactly zero.
5. **Given** a schedule declaring two entries with the same effective date, or an
   entry with a negative rate, **When** the file is loaded, **Then** loading fails
   naming the file and the offending field.

---

### User Story 3 - Liquidity is a practice, not a right (Priority: P2)

The funds' primary documents show that no redemption windows exist. Legally, neither
fund owes the owner a buyback before its termination date: early exit is at the
manager's discretion, at a discretionary discount, settled in up to 15 business days.
In practice, Inzhur buys certificates back at NAV within hours at zero commission —
but that is a revocable company practice, not a right. The owner declares both, kept
distinguishable, and every projection states which it assumed. An exit outside the
declared terms is refused with the reason named, or executed at the declared discount
— and taxed correctly on the actual proceeds either way.

**Why this priority**: An asset that cannot be liquidated at a reasonable cost is not
worth its NAV (constitution Principle VI), and presenting a revocable practice as a
guarantee is exactly the false confidence this project exists to refuse. This is
required test J3 — its "window" wording generalised to the liquidity terms the funds
actually have. It follows Stories 1–2 because a redemption must first be taxable at
all before its feasibility rules matter.

**Independent Test**: Project the same dated redemption request under the declared
practice mode and under the legal terms, and check the executed amounts, the refusal
case, and the tax on the discounted case by hand; confirm the two modes differ by
exactly the declared spread, discount and settlement delay.

**Acceptance Scenarios**:

1. **Given** the declared practice mode is assumed, **When** a redemption request is
   processed, **Then** it executes at NAV with no discount and same-day settlement,
   and the result is labelled as resting on a revocable, unverified practice.
2. **Given** the legal terms are assumed, **When** a redemption before the fund's
   termination date is processed, **Then** it is never presented as guaranteed: it
   executes at up to the declared maximum discount with settlement up to the declared
   number of business days, the discount appears as its own line, and the disposal
   tax is computed on the post-discount proceeds actually received.
3. **Given** a scenario that declares the discretionary buyback unavailable, **When**
   a redemption is requested, **Then** it is refused as a typed result naming that no
   buyback obligation exists before the declared termination date — the termination
   payout being the next guaranteed exit — and the holding remains open; nothing is
   silently executed or deferred.
4. **Given** a purchase request dated after the fund's declared subscription cutoff,
   **When** it is processed, **Then** it is refused naming the cutoff.
5. **Given** one redemption request projected under both liquidity modes, **When** the
   two results are compared, **Then** they differ by exactly the declared spread,
   discount and settlement delay — the price of relying on the legal floor is
   visible, not implied.
6. **Given** a projection that reaches the fund's termination date with the holding
   open, **When** the projection completes, **Then** the termination payout is a
   dated disposal event taxed under the disposal class — never a silent extension of
   the holding past the fund's declared end.

---

### User Story 4 - MilTech under declared terms only (Priority: P2)

MilTech is an accumulation fund: it owes no dividends, and the coupons of its
underlying bonds reinvest into NAV. The owner declares it — minimum ticket, fund term
to 06.11.2029, subscription cutoff 31.12.2026, tax classes — and projects a
contribution held to the fund's end under the fund-stated rate of 25–29% simple
annual in hryvnia. That rate enters as a fund-stated, unverified declared term — not
a promise — and the tool's job is to show how much of it survives the entry/exit
spread and the tax treatment, next to the tax-free hurdle rate.

**Why this priority**: MilTech is the instrument where honesty is hardest — a
fund-stated 25–29% next to a 15.5% tax-exempt hurdle invites exactly the false
precision this project exists to refuse. The value delivered is the erosion
arithmetic: spread and tax, each visible, applied to a rate clearly labelled as the
fund's own statement.

**Independent Test**: Declare the fund, project a contribution to the fund's
termination under the declared rate, and check the pro-rata accrual, the spread, the
disposal tax and the net outcome by hand; confirm the output labels the rate as
fund-stated and unverified.

**Acceptance Scenarios**:

1. **Given** the declared net yield, **When** a holding is projected, **Then** the
   projection is simple pro-rata arithmetic over that rate: no distribution events
   are invented for an accumulation fund, value accrues to the exit, and the exit is
   taxed under the disposal class.
2. **Given** the fund states a range (25–29%), **When** results are produced, **Then**
   the output is the range — or an explicitly chosen value labelled as the owner's
   assumption — never a silently chosen midpoint.
3. **Given** the researched fee facts (management fee up to 2% of average NAV, no
   performance-fee clause), **When** a projection runs, **Then** no separate fee
   flows are computed from them: they are recorded as provenance context for the
   declared net yield, per the owner's modelling decision.
4. **Given** the net after-spread, after-tax outcome, **When** it is reported,
   **Then** it appears beside the hurdle rate from feature 001 with an explicit
   statement that the comparison excludes funding and exit route costs and rests on
   marked, fund-stated inputs.

---

### User Story 5 - Nothing dressed up as statistics (Priority: P3)

Both Inzhur funds are assumption-driven: no usable market history, no basis for a
volatility or a Sharpe ratio. The owner can see that every figure these instruments
produce is labelled assumption-driven and marked as resting on unverified terms — and
can never, anywhere, obtain a statistical risk metric for them.

**Why this priority**: This is constitution Principle I applied to the first
instruments in the registry for which it bites. It is P3 only because it is mostly a
prohibition — verified rather than built — but it must be verified now, before any
later feature grows a metrics surface that could forget it.

**Independent Test**: Inspect every output produced for the two funds and confirm no
statistical metric appears; request one explicitly and confirm the answer is a typed
refusal naming the reason, not a number.

**Acceptance Scenarios**:

1. **Given** any projection of either fund, **When** its complete output is inspected,
   **Then** it contains no volatility, Sharpe, Sortino or other statistics-derived
   figure, and the instrument is labelled assumption-driven.
2. **Given** a request for a statistical metric on an assumption-driven instrument,
   **When** it is evaluated, **Then** the result is a typed refusal carrying the
   reason, and no metric is computed from invented data.
3. **Given** a fund term with an empty verification date, **When** any figure is
   derived from it, **Then** that figure and everything downstream of it carry the
   unverified mark.
4. **Given** an instrument whose income is declared in USD-equivalent terms while its
   money moves in hryvnia, **When** its results are produced, **Then** they state the
   peg and its declared cap, all monetary amounts are hryvnia, and no amount is ever
   silently converted or combined across currencies.

---

### Edge Cases

- **A taxable event dated exactly on a schedule entry's effective date** — the new
  entry applies; the boundary is declared (effective from that date inclusive), not
  left to chance.
- **A taxable event before the schedule's earliest entry** — a typed error naming the
  class and date; never a default rate, never a silent zero.
- **Two schedule entries with the same effective date, an unordered schedule, or a
  negative rate** — load failure naming the file and field.
- **A markup or discount declared outside 0–100%** — load failure; an exit at exactly
  the declared maximum discount is loadable and executes, with the discount stated.
- **A purchase dated after the declared subscription cutoff** — refused naming the
  cutoff; never silently backdated or queued.
- **A projection horizon extending past the fund's termination date** — the
  termination payout is produced as a dated, taxed disposal event; the holding never
  silently outlives the fund.
- **An exit whose settlement crosses a schedule effective date** — the output states
  which date selected the rate (the declared default: the date the proceeds are
  received), never a silent choice between execution and settlement date.
- **An assumed exchange rate above the declared peg cap** — the pegged payment is
  sized at the cap, and the output states that the cap bound; the peg partially
  breaking under fast devaluation is visible, not lost.
- **A pegged flow projected with no declared exchange-rate assumption** — a typed
  degraded result naming the missing input; never an invented or implicit rate.
- **A scenario declaring the buyback practice revoked** — projections fall back to
  the legal terms; a practice-mode request in that scenario is refused naming the
  revocation.
- **A redemption at a loss** — zero disposal tax, never negative; the loss is
  reported with the statement that carryforward is out of scope here.
- **A fund-stated yield given as a range** — never collapsed to a silent midpoint;
  the range is reported, or an explicitly chosen value is labelled as the owner's
  assumption.
- **A USD-equivalent declared term treated as money** — an error: the peg is a term,
  not an amount, and 001's prohibition on combining currencies applies unchanged.
- **Two instruments declaring the same identifier** — a load-time collision, as in
  001.

## Requirements *(mandatory)*

### Functional Requirements

**Declared fund instruments**

- **FR-001**: The system MUST accept a collective-investment fund instrument declared
  purely as data: identity, unit currency, income declaration currency, distribution
  terms, spread and fee terms, liquidity terms, minimum ticket, subscription cutoff
  and fund termination dates, and a tax class per kind of income event. Adding either
  Inzhur product — or a third fund with different terms — MUST require no source-code
  change and MUST NOT introduce any fund-specific engine behaviour.
- **FR-002**: Every observed product term MUST carry its value, source, retrieval date
  and verification date. An empty verification date is permitted and expected — every
  term of both real Inzhur declarations enters from the funds' primary documents
  (регламент, проспект, fund pages, accessed 2026-08-22) with an empty verification
  date until the owner confirms it against his investor cabinet — and the unverified
  mark MUST propagate to every derived figure, per 001's rules.
- **FR-003**: Loading a fund or tax-schedule declaration MUST fail loudly — naming the
  file and the field — on a malformed value, an unrecognised field, a missing required
  field, a duplicate identifier, a reference to an undeclared tax class, or an
  internally inconsistent declaration (a markup or discount outside 0–100%, a negative
  rate, duplicate or unordered effective dates, a termination date before the
  subscription cutoff). No default MUST ever be substituted.
- **FR-004**: Both funds MUST be declared assumption-driven, and every projected
  figure for an assumption-driven instrument MUST be labelled as resting on declared
  terms and stated assumptions rather than market history.
- **FR-005**: The system MUST NOT emit volatility, Sharpe, Sortino or any other
  statistical metric for an assumption-driven instrument. A request for one MUST
  produce a typed refusal carrying the reason — never a number computed from invented
  data (constitution Principle I).

**Two tax classes on one instrument (E1)**

- **FR-006**: Each kind of income event MUST be taxed under the tax class the
  instrument declares for that kind, and one instrument MUST be able to declare
  different classes for distributions and for disposal. ⚙ 001's per-event-kind
  mapping was specified plural for exactly this case; this feature is the first to
  exercise it with two distinct classes.
- **FR-007**: In a single projection, a distribution and a redemption of the same
  units MUST each be taxed under their own declared class, neither class's rates may
  ever be applied to the other's events, and the output MUST report per-class
  subtotals so a reader can see which class charged what.
- **FR-008**: The disposal tax base MUST be the proceeds actually received (after any
  discount) minus the cost basis consumed minus fees allocated to the disposal; the
  distribution tax base MUST be the distribution amount. A disposal at a loss MUST
  charge exactly zero — never a negative tax — and MUST report the realised loss with
  an explicit statement that loss carryforward is not modelled in this feature.
- **FR-009**: The rates for the fund-distribution and investment-profit classes MUST
  enter as data carrying the citations the reference spec records for them
  (`SIMULATOR_SPEC.md` §4.5, sources §12), with their retrieval dates and empty
  verification dates. No tax rate may originate from an implementer's or agent's
  memory. (The REIT page's shown 14% dividend withholding corroborates the
  fund-distribution class; corroboration is recorded, it is not verification.)

**Dated rate schedules (E10)**

- **FR-010**: A tax class's rates MUST be declarable as a dated schedule: ordered
  entries, each carrying its effective date, its rates, and its own provenance
  (source, retrieval date, verification date). This closes the recorded gap of
  feature 001, whose schema carries a scalar rate per class.
- **FR-011**: The rate applied to a taxable event MUST be the schedule entry in force
  on the event's date — the entry with the latest effective date on or before that
  date, an entry being in force from its effective date inclusive. ⚙ If a cited
  public source establishes a different timing rule for a specific class (for
  example, taxation by accrual rather than by payment date), that rule enters as data
  with its citation; it is not guessed here.
- **FR-012**: A taxable event dated before the schedule's earliest entry MUST produce
  a typed error naming the tax class and the event date. No rate is defaulted, no
  zero is silently charged.
- **FR-013**: A legislated rate change MUST be expressible as adding one dated entry
  to a data file — no source-code change, no rebuild — and a single run whose events
  straddle the effective date MUST charge the old rate before it and the new rate on
  and after it (required test E10).
- **FR-014**: The existing exempt class MUST be carried into schedule form with its
  provenance intact, and feature 001's results MUST be unchanged by the migration —
  the exempt class still charges exactly zero on every event.

**Liquidity terms (J3)**

- **FR-015**: Liquidity terms MUST be declared per instrument as data, with the legal
  terms and the observed practice kept distinguishable: (a) the **legal terms** from
  the fund's регламент — no buyback obligation before the fund's termination date,
  buyback before then at the manager's discretion, an exit discount up to a declared
  maximum, settlement up to a declared number of business days, an entry markup up to
  a declared maximum; (b) the **declared practice** — buyback at NAV, same-day, zero
  commission — labelled a revocable company practice with its own citation and empty
  verification date; and (c) the subscription cutoff and fund termination dates where
  declared. ⚙ Required test J3 and the reference registry speak of "redemption
  windows"; the funds' primary documents show no windows exist. The J3 substance —
  an exit outside the declared terms is refused, or executed at the declared
  haircut, taxed correctly either way — is preserved over these declared liquidity
  terms, and the landing change should annotate the row's wording accordingly.
- **FR-016**: Every projection MUST state which liquidity mode it assumed — practice
  or legal — and both modes MUST be projectable for the same request, so that their
  difference (spread, discount, settlement delay) is a visible, comparable number.
- **FR-017**: Under the legal terms, an exit before the termination date is
  discretionary and MUST never be presented as guaranteed. Where the scenario
  declares the discretionary buyback unavailable, a redemption request MUST be
  refused as a typed result naming that no buyback obligation exists before the
  declared termination date — the termination payout being the next guaranteed exit —
  and the holding remains open; nothing is silently executed, adjusted or deferred.
- **FR-018**: Where an exit executes, it MUST execute at the declared terms of the
  assumed mode — at NAV for the practice mode; at NAV less a discount up to the
  declared maximum, settled up to the declared delay, for the legal terms. The
  discount MUST appear as its own line, and the disposal tax MUST be computed on the
  post-discount proceeds actually received (required test J3, with FR-008).
- **FR-019**: A purchase dated after the declared subscription cutoff MUST be refused
  naming the cutoff. A holding MUST NOT silently extend past the fund's termination
  date: reaching it produces a dated termination payout taxed as a disposal. A plan
  that requires a guaranteed exit before the termination date while assuming only the
  legal terms MUST surface that as a feasibility finding — the exit is discretionary
  — rather than silently assuming the buyback.

**Income declared in USD-equivalent, money in hryvnia**

- **FR-020**: Per owner decision A, the REIT's income is declared in USD-equivalent
  terms while every monetary amount — computation, ledger, tax — is hryvnia. The
  declaration MUST carry the peg and its declared cap (the leases' «граничний
  курс»), and every output for the instrument MUST state the peg and the cap so the
  currency exposure is visible rather than lost. (Full FX attribution is a later
  feature; this feature only guarantees the fact is never hidden.)
- **FR-021**: Sizing a pegged hryvnia payment MUST require an explicitly declared
  exchange-rate assumption, stated as the owner's input. Absent one, the outcome MUST
  be a typed degraded result naming exactly which input is missing — never an
  invented or implicit rate. Where the assumed rate exceeds the declared cap, the
  payment MUST be sized at the cap and the output MUST state that the cap bound.
- **FR-022**: 001's prohibition on combining currencies applies unchanged. The peg is
  a declared term, not a conversion licence: no amount changes currency except
  through the declared sizing of FR-021, and a USD-equivalent term is never itself
  treated as money.

**Declared net yield, and the spread (owner decision B)**

- **FR-023**: A fund projection MUST be simple pro-rata contractual arithmetic over
  the instrument's **declared net yield** — the fund-stated rate, entered with its
  citation and an empty verification date and labelled as fund-stated, not a promise
  (REIT: target 9.5%/yr in USD-equivalent terms; MilTech: 25–29% simple annual in
  hryvnia). The system MUST NOT model fund-internal profitability — management fee
  accrual, performance fees, the underlying bonds' coupon reinvestment — as separate
  computed terms: those researched values enter the declaration as recorded context
  and provenance for the declared rate. No growth, price, distribution or flow is
  invented beyond the declared terms and stated assumptions. A rate stated as a
  range MUST be reported as a range, or projected at an explicitly chosen value
  labelled as the owner's assumption — never a silently chosen point.
- **FR-024**: The entry/exit spread is the access term and MUST be modelled
  carefully: a purchase executes at NAV plus the declared entry markup (up to 1% of
  NAV), an exit at NAV minus the declared discount (up to 1%), and the round-trip
  spread erosion MUST appear as its own line. The live settings are unverified and
  MUST be declared as such — including the recorded arithmetic observation that the
  REIT's live entry price (≈ 11.11 грн against a shown NAV of 10.9975) is consistent
  with the 1% markup being charged while a secondary source claims zero, and that
  MilTech's entry (≈ 1 006.97 against nominal 1 000) is consistent with no markup.
- **FR-025**: A projected fund's after-spread, after-tax outcome MUST be reported
  beside the hurdle rate from feature 001, with an explicit statement that the
  comparison excludes funding and exit route costs (a later feature) and rests on
  marked, fund-stated inputs.

**The real declarations**

- **FR-026**: The real declarations MUST carry the researched terms with their
  primary-document citations and empty verification dates. REIT: minimum one
  certificate (nominal 10 грн, live entry ≈ 11.11 грн), fund term of 20 years ending
  20.05.2045, monthly distributions. MilTech: minimum one certificate (nominal
  1 000 грн, live entry ≈ 1 006.97 грн), registered 06.05.2026, term of 42 months
  ending 06.11.2029, subscription cutoff 31.12.2026, accumulation fund with no
  dividend obligation — the underlying bonds' 35-day coupons reinvesting into NAV
  and maturing July 2029 are recorded context, not modelled flows.
- **FR-027**: The REIT's distribution declaration MUST state: monthly distributions
  of at least 90% of net rental profit; record date the last day of the month; paid
  by the 10th of the following month; paid in hryvnia, USD-linked, subject to the
  declared cap. The declared target is 9.5%/yr in USD-equivalent terms (the shown
  trailing 12 months, 11.52%, is recorded as an observation, not a term). The
  rate-fixing rule converting each pegged payment and the current cap values are
  NOT FOUND in the primary documents and MUST be recorded as owner-verification
  tasks, never invented — the cap's known history (2023: 37.49; 2024: 41.24; a
  +10%/yr ladder, pre-2025 secondary evidence) enters as a declared-but-unverified
  term.
- **FR-028**: The fee declaration follows owner decision B: the spread terms of
  FR-024 are the modelled access cost, and the researched fee facts are recorded as
  provenance context for the declared net yield — REIT: management fee up to 2%/yr
  of NAV (accrued 1/12 monthly, pro-rata reduced in underperforming months),
  performance fee up to 25% of profit above the 9.5%-USD projection hard-capped at
  15% of profit above an NBU-average-key-rate benchmark, other-expense cap 5%;
  MilTech: management fee up to 2%/yr of average NAV (same 1/12 and pro-rata clause,
  benchmark 28%), and no performance-fee clause — a deliberate absence in its
  регламент, recorded as such. The possible ІНЖУР КЕПІТАЛ investment-firm
  commission, amount NOT FOUND, is recorded as an owner-verification task, not a
  number.

### Key Entities

- **Fund instrument declaration** — a data file describing one collective-investment
  fund: identity, unit currency, income declaration currency, distribution terms,
  spread terms with recorded fee context, liquidity terms, minimum ticket,
  subscription cutoff and termination dates, an assumption-driven label, and a tax
  class per kind of income event. Every observed value carries provenance.
- **Distribution terms** — the declared frequency, basis (share of net rental
  profit), record and payment dates, payment currency, and the peg: the currency the
  amounts are sized in, with its declared cap.
- **Declared net yield** — the fund-stated rate a projection accrues pro-rata: a
  cited, unverified declared term, possibly a range, labelled fund-stated and never
  presented as a promise or an observation of the market.
- **Liquidity terms** — two distinguishable declared modes: the legal terms (no
  obligation before termination; discretionary buyback; discount up to a maximum;
  settlement up to a delay; entry markup up to a maximum) and the revocable observed
  practice (buyback at NAV, same-day, zero commission), plus the subscription cutoff
  and termination dates.
- **Entry/exit spread** — the declared markup and discount around NAV; the access
  cost this feature models carefully, with its live setting recorded as unverified.
- **Tax rate schedule** — a tax class's rates as ordered dated entries; each entry
  carries its effective date, its rates, and its own provenance. The successor to
  001's scalar rate.
- **Taxable event** — one dated income event of a declared kind (distribution,
  disposal gain), taxed under the class its instrument maps that kind to, at the
  schedule entry in force on its date.
- **Stated assumption** — an explicitly labelled owner input a projection needs
  because no market or contractual value exists: the exchange-rate assumption that
  sizes pegged payments, a chosen point within a fund-stated range, the availability
  of the discretionary buyback. Never presented as an observation.
- **Typed refusal / degraded result** — the explicit outcome carrying its reason: a
  redemption refused because no obligation exists, a purchase after the cutoff, a
  metric refused for an assumption-driven instrument, a pegged flow that cannot be
  sized without a declared rate assumption, an event before a schedule's earliest
  entry.
- Reused from feature 001 unchanged: provenance record, holding lot, cash balance,
  transaction record, run record.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single projection holding one fund charges a distribution under the
  fund-distribution class and a redemption of the same units under the
  investment-profit class; both per-class subtotals match hand-computed arithmetic
  within the single project tolerance, the arithmetic is recorded alongside the
  check, and every tax figure names its class, that class's cited source and its
  verification date. (FR-006, FR-007, FR-009)
- **SC-002**: Editing one class's schedule in a test copy changes only that class's
  subtotal — the other class's figures are bit-identical — demonstrating the two
  classes cannot collide. (FR-007)
- **SC-003**: A projection straddling a schedule's effective date charges the earlier
  rate before it and the later rate from it, matching a hand-computed worked example;
  the difference between the two periods' charges equals exactly the legislated step.
  (FR-011, FR-013)
- **SC-004**: A legislated change is entered as one dated entry in a data file with
  zero source lines changed, and it takes effect in the next run. (FR-013)
- **SC-005**: A taxable event before a schedule's earliest entry produces a typed
  error naming the class and the date; across a deliberate battery of broken schedule
  files (duplicate effective dates, unordered entries, negative rates), every failure
  names the file and the field and no default is ever substituted. (FR-003, FR-012)
- **SC-006**: Feature 001's exempt worked example passes unchanged after the schedule
  migration, with total tax exactly zero. (FR-014)
- **SC-007**: The liquidity cases each match hand-computed arithmetic: a practice-mode
  exit at NAV, same-day, labelled revocable and unverified; a legal-terms exit at the
  declared maximum discount and settlement delay, taxed on the post-discount
  proceeds; and a refusal naming the absence of any buyback obligation before the
  named termination date. The same request projected under both modes differs by
  exactly the declared spread, discount and delay. (FR-015…FR-018)
- **SC-008**: With any fund term left unverified, 100% of figures derived from it
  carry the unverified mark, and no derived figure appears unmarked. (FR-002)
- **SC-009**: No output produced for either fund contains a volatility, Sharpe,
  Sortino or other statistics-derived figure; every such output is labelled
  assumption-driven; and an explicit request for a statistical metric returns a typed
  refusal, not a number. (FR-004, FR-005)
- **SC-010**: A third synthetic fund with different liquidity terms, spread, peg and
  tax schedule produces complete results with zero lines of source code changed.
  (FR-001)
- **SC-011**: A pegged payment sized under a declared exchange-rate assumption
  matches hand arithmetic; an assumed rate above the declared cap sizes the payment
  at the cap and the output states that the cap bound; a pegged flow with no declared
  assumption yields a typed degraded result naming the missing input; and no
  combination of amounts in different currencies ever succeeds. (FR-020, FR-021,
  FR-022)
- **SC-012**: The round-trip spread erosion and any exit discount each appear as
  their own line, and the net outcome reconciles exactly with the declared-yield
  gross minus the named lines — no unexplained residue. (FR-008, FR-024)
- **SC-013**: Every figure derived from the fund-stated yield or an owner-stated
  assumption is labelled as such; a fund-stated range is never collapsed to a silent
  midpoint; and the net figure appears beside the hurdle rate with the
  route-costs-excluded statement on its face. (FR-023, FR-025)
- **SC-014**: A purchase after the subscription cutoff is refused naming the cutoff;
  a plan requiring a guaranteed exit before termination under legal terms alone
  yields a feasibility finding, not a silent simulation; and a projection reaching
  the termination date produces the dated, taxed termination payout. (FR-019)

## Assumptions

- **Researched is not verified.** Every product term enters from the funds' primary
  public documents with its citation, its retrieval date (2026-08-22) and an empty
  verification date until the owner checks it against his investor cabinet; the mark
  propagates. The hand-computed worked examples for E1, E10 and J3 still run on
  labelled synthetic fixtures, following 001's precedent — they test the engine's
  arithmetic, not Inzhur.
- **Rate selection is by taxable event date.** The schedule entry in force on the
  event's date applies, effective date inclusive (FR-011). Where settlement lags
  execution, the default taxable date is the date the proceeds are received, and the
  output states which date selected the rate; any class-specific legal timing rule
  that contradicts these defaults must arrive as data with a citation.
- **The known historic levy change is expressible but not fabricated.** The schedule
  mechanism can carry the 1.5% → 5% military-levy step, but the historic entry is
  added only with a cited effective date; the E10 worked example uses a synthetic
  schedule instead of guessing legislation dates.
- **Tax is recognised on the event date.** Filing mechanics, payment timing, the
  withheld-at-source versus self-declared distinction, and loss carryforward are
  later features (required tests E2, E7). This feature reports charges, not a filing
  calendar.
- **The declared net yield drives projections** (owner decision B). There is no NAV
  series, no market price and no return model; fund-internal profitability is
  recorded context, not computed terms; and MilTech's outcome distribution and
  probability-of-loss weighting remain explicitly out of scope
  (`SIMULATOR_SPEC.md` §11 item 6).
- **No market FX source.** The peg sizes hryvnia payments only under an explicitly
  declared, owner-stated exchange-rate assumption (FR-021); there is no rate feed,
  no forecast, no display switch. The F1 FX tax asymmetry is a later feature.
- **Contributions are taken as given.** Funding routes and income streams are later
  features; the entry/exit spread is an instrument-level term here, and FR-025's
  comparison states that route costs are excluded.
- **One owner, no delivery surface.** As in 001: results are produced and asserted by
  the test suite; there is no UI and no CLI in this feature.

## Clarifications resolved

All three answered 2026-08-22: the owner supplied two design decisions, and a
research pass over the funds' primary public documents supplied the facts — both
funds' регламент and проспект read in full, plus the fund pages and Inzhur news
(accessed 2026-08-22). Every researched value enters the declarations with these
citations and an empty verification date until the owner checks his cabinet.

**Owner decisions:**

- **A — USD-equivalent declaration, hryvnia money.** In Ukraine all settlements
  happen in hryvnia, but real estate is universally priced in USD-equivalent terms —
  so the REIT's declaration speaks USD while the money is UAH. Computation, ledger
  and tax all run in hryvnia; the peg is a declared term. This resolves the "two
  different declarations" question: a UAH flow sized by a USD peg, never a genuine
  USD flow.
- **B — the spread is the main thing.** The funds' internal profitability
  (management-fee mechanics, performance-fee accrual) is not modelled as separate
  engine terms: the fund-stated rate is the instrument's declared net yield, a
  simple pro-rata model covers shorter horizons, and the entry/exit spread is the
  term that must be modelled carefully. Fee and premium details enter the spec as
  recorded context and provenance for the declared rate.

| # | Question | Decision | Where it landed |
|---|---|---|---|
| 1 | Real redemption terms for both funds | **No windows exist.** Legally no buyback obligation before fund termination; early buyback is discretionary, at a discretionary discount, settled in ≤ 15 business days; the marketed same-day-at-NAV zero-commission buyback is revocable company practice. Declared as two distinguishable liquidity modes. MilTech adds the subscription cutoff (31.12.2026) and term end (06.11.2029) | FR-015…FR-019, FR-026 |
| 2 | REIT distribution terms and the peg | **A UAH flow sized by a capped USD peg** (decision A): monthly, ≥ 90% of net rental profit, record date last day of month, paid by the 10th, target 9.5%/yr USD-equivalent; the cap («граничний курс») is declared but unverified, the per-payment rate-fixing rule is NOT FOUND | FR-020…FR-022, FR-027 |
| 3 | Fee values | **The declared net yield drives projections** (decision B); the entry/exit spread — up to 1% markup / up to 1% discount, live settings unverified — is the modelled access term; management and performance fee facts are recorded as provenance context; the ІНЖУР КЕПІТАЛ commission amount is unknown and stays a verification task | FR-023…FR-025, FR-028 |

**Sources** (all accessed 2026-08-22): fund pages
<https://www.inzhur.reit/offer/inzhur-reit> and
<https://www.inzhur.reit/offer/inzhur-miltech>; Регламент ЗНПІФ «ІНЖУР REIT»
(ред. 07.05.2025) and Проспект (28.05.2025); Регламент ЗНПІФ «Inzhur MilTech»
(ред. 15.07.2026) and Проспект (15.07.2026); Inzhur news 07.04.2025 (buyback
commission cancelled) and 12.08.2026 (MilTech launch). The PDF documents are hosted
on the d2zk2gr3fhkmim.cloudfront.net host linked from the fund pages.

## Owner verification tasks

Six facts the primary documents do not settle. Each is recorded as a task, never
filled with a guess; the affected declared values carry empty verification dates and
the mark propagates until the owner closes them.

1. The rate-fixing rule converting the USD-pegged rent into each hryvnia payment —
   which rate, on which date.
2. The current «граничний курс» values, and whether the +10%/yr ladder (2023: 37.49;
   2024: 41.24 — pre-2025 secondary evidence) survives in the consolidated 2025 fund.
3. Whether the 1% entry markup and exit discount are currently charged — the REIT's
   live entry price ≈ NAV × 1.01 suggests yes while a secondary source claims zero;
   MilTech's ≈ NAV entry suggests no. Verify the live buy and sell prices in the
   cabinet.
4. The ІНЖУР КЕПІТАЛ investment-firm commission amount.
5. A post-launch statement that the zero-buyback-commission practice covers MilTech.
6. Whether any organized secondary market exists for either fund's certificates.

## Required tests this feature closes

Rows in `docs/REQUIRED_TESTS.md` that must be flipped, with their test paths
recorded, before this feature is done:

| Row | What it asserts |
|---|---|
| **E1** | A distribution taxed at the fund-distribution class and a redemption of the same units at the investment-profit class, both in one run from one instrument, without collision |
| **E10** | A rate declared as a dated schedule changes on its effective date — the recorded schema gap of feature 001 is closed |
| **J3** | Redemption outside the declared Inzhur liquidity terms is refused, or executed at the declared haircut when allowed — taxed correctly either way |

⚙ J3's recorded wording says "outside an Inzhur window"; the funds' primary documents
show no windows exist (see FR-015). The row's substance is preserved over the
declared liquidity terms — refuse, or execute at the declared discount, taxed on
actual proceeds either way — and the landing change should annotate the row's wording
when flipping it.

Adjacent but **not claimed**: FR-019 specifies the feasibility behaviour behind
**J4** (a fund whose only guaranteed exit is termination is effectively locked up;
requiring an earlier guaranteed exit is a feasibility finding, not a silent
simulation) and FR-005 the behaviour behind **J6** (no statistical metric for an
assumption-driven instrument). Whether those rows flip in this feature is decided at
planning, when it is known whether their test surfaces exist; this specification
requires the behaviours either way.

## Out of scope

Named explicitly so the plan does not drift into them: funding and exit routes,
income streams and the full tuple; market prices, NAV series and return models;
fund-internal profitability as computed terms — management-fee accrual,
performance-fee accrual, the underlying bonds' coupon mechanics (owner decision B);
MilTech's outcome distribution and probability-of-total-loss modelling (the owner's
assumption, decision layer later); the F1 FX tax asymmetry, market FX rate sources
and any conversion beyond the declared peg sizing of FR-021; the display-currency
switch; loss carryforward, filing mechanics and tax payment timing (E2, E7); the
withheld-at-source versus self-declared timing distinction; crypto tax scenarios;
the decision layer, objectives and candidate generation; any change to how OVDP
works beyond the schedule-form migration, which must leave its results unchanged
(FR-014); the web interface and the command-line interface.
