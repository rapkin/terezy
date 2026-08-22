# Feature Specification: The ramp

**Feature Directory**: `specs/002-ramp-cost`

**Feature Branch**: none — this repo works on `main` by design

**Created**: 2026-08-22

**Status**: Ready for planning — all clarifications resolved 2026-08-22

**Input**: The ramp — what it costs to get money where the instrument is, per income stream and per route.

---

## Why this feature exists

`SIMULATOR_SPEC.md` §4.3.1 makes the largest single claim in the whole product:

> A P2P premium of +2 to +4 UAH per dollar is roughly **4.8–9.5% one way and 9–19% round
> trip**, while the Inzhur route costs **0%**. So the crypto ramp alone can consume most
> or all of a year of the risk-free domestic return — and it is invisible in every chart
> the predecessor produced.

Feature 001 made the hurdle real: 15.5%, tax-free, hand-verified. This feature makes the
thing that has to *beat* it real. Until the cost of getting money to an instrument is
computed rather than asserted, every comparison the tool offers is flattering the
expensive options.

It answers question 7 of `SIMULATOR_SPEC.md` §8 in full — *"what does the Binance P2P
spread actually cost me per year?"* — and question 3 in its essential form: *"should my
USD income and my UAH salary go to different places?"*

The structural insight it exists to make computable: **money that arrives in USD needs no
UAH→USD conversion.** The same acquisition is nearly free from one stream and 5–10%
expensive from the other. That makes allocation a per-stream decision, not a
per-portfolio one.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Know what the ramp costs (Priority: P1)

The owner names an amount, where it starts, and where it needs to end up. The tool returns
every route that can carry it, and for each one: what arrives at the far end, the cost as
a percentage one way, the cost **round trip**, the ceiling per month, how long it takes,
and whether the route is open at all.

**Why this priority**: this is the number the feature exists to produce, and the largest
term in the owner's real decision. Without it the tool cannot honestly compare a domestic
instrument against a foreign one.

**Independent Test**: state a UAH amount, a destination holding dollars, and a declared
P2P premium; check the arriving amount and both cost percentages against arithmetic worked
out by hand.

**Acceptance Scenarios**:

1. **Given** a route whose FX leg declares a P2P premium of +3 UAH per dollar against a
   stated reference rate, **When** an amount is costed through it, **Then** the one-way
   cost percentage matches the hand-computed `premium / reference` and the round-trip cost
   matches the hand-computed two-way figure.
2. **Given** the same amount and destination reachable by more than one route, **When**
   the routes are compared, **Then** each is reported with its own total cost, ceiling,
   latency and status, and the comparison names which one is cheapest round trip.
3. **Given** any route comparison, **When** a cost is presented, **Then** it is labelled
   one-way or round-trip explicitly, and a one-way figure is never presented where a
   round-trip figure belongs.
4. **Given** a route whose every leg declares zero fees and no conversion, **When** it is
   costed, **Then** the cost is exactly zero and the arriving amount equals the departing
   amount — the domestic path is the bar the others are measured against.

---

### User Story 2 - Fund it from the right stream (Priority: P1)

The owner's money arrives in two currencies at two places. The tool shows that the same
acquisition costs almost nothing from one and several percent from the other, and reports
cost per `(destination × stream × route)` rather than per destination.

**Why this priority**: equal-highest with Story 1, because a single per-destination cost
figure is not merely less useful — it is **wrong**, and it is the specific error the
constitution's Principle VI forbids. Quoting one access cost for "buying dollars" hides
the entire finding.

**Independent Test**: cost the same USD acquisition from the UAH salary and from the USD
contract income, and confirm the two results differ by exactly the hand-computed ramp
cost.

**Acceptance Scenarios**:

1. **Given** two income streams, one arriving in UAH and one in USD, **When** the same USD
   acquisition is funded from each, **Then** the net amounts differ by exactly the
   hand-computed ramp cost, and the USD-funded route performs no conversion at all.
2. **Given** a request for the cost of reaching a destination, **When** no stream is
   named, **Then** the tool reports a cost per stream rather than one blended figure.
3. **Given** a stream that declares an income-tax rate, **When** deployable capacity is
   reported, **Then** it is net of that rate, so the amount available to invest is not
   overstated.
4. **Given** a route from the USD stream that involves no FX leg, **When** it is costed,
   **Then** the FX component of its cost is exactly zero rather than a small number.

---

### User Story 3 - Respect what the route will actually allow (Priority: P2)

Routes have monthly ceilings, minimums, delays, and months when they are simply closed.
A plan that ignores them is a plan that cannot be executed.

**Why this priority**: an unexecutable plan reported as executable is the defect class the
constitution puts at top severity. But Story 1 is useful without ceilings, so this
follows.

**Independent Test**: plan a contribution larger than a declared monthly cap and confirm
the excess is handled by the declared fallback and reported, with total deployed equal to
the cap.

**Acceptance Scenarios**:

1. **Given** a monthly contribution exceeding a route's declared cap, **When** the plan
   runs, **Then** the amount deployed equals the cap — never the plan — and the excess is
   handled by the declared fallback policy.
2. **Given** any fallback applied, **When** results are reported, **Then** every
   occurrence appears in the output with its date, amount and reason. A silently executed
   infeasible plan is a defect.
3. **Given** an amount below a leg's declared minimum, **When** it is costed, **Then** the
   route is reported as unusable for that amount, naming the minimum and the shortfall,
   and is not silently rounded up.
4. **Given** a route declared closed on the date in question, **When** routes are ranked,
   **Then** it is excluded with its status recorded, and its absence is visible rather
   than silent.

---

### User Story 4 - See what changes when the war ends (Priority: P2)

Route costs and availability are not permanent. The owner states a transition date and two
regimes, and sees what the ramp costs before and after.

**Why this priority**: this converts an unknowable forecast into a testable belief, which
is `SIMULATOR_SPEC.md` §1.3's whole preference order. It answers §8 question 2 — fund now
at wartime cost, or wait — as a break-even rather than a guess.

**Independent Test**: declare two regimes and a transition date; confirm contributions
before and after use different route sets and that the round-trip cost drops by exactly
the hand-computed difference.

**Acceptance Scenarios**:

1. **Given** a scenario with a transition date and a route set for each regime, **When**
   the plan spans that date, **Then** contributions before it use the first set and those
   after use the second.
2. **Given** the transition, **When** costs are reported, **Then** the change in
   round-trip cost equals the hand-computed difference between the two regimes.
3. **Given** a regime transition, **When** results are reported, **Then** the transition
   date is stated as an assumption rather than presented as a known fact.

---

### User Story 5 - Add a venue or a corridor without touching the engine (Priority: P3)

A new bank, a new provider, a new currency path is added by writing a declaration file.

**Why this priority**: the framework claim from Principle II, applied to the layer where
it matters most — corridors get added and dropped constantly, and an engine edit per
corridor would make the tool unmaintainable. P3 because it is verified rather than built.

**Independent Test**: add a route declaration for a new provider and corridor and rank it
against the existing ones with no source edit.

**Acceptance Scenarios**:

1. **Given** a new route declared purely as data, **When** routes are ranked, **Then** it
   appears with a complete cost breakdown and no source-code change was needed.
2. **Given** two routes that differ **only** in how many conversions they perform, **When**
   they are ranked, **Then** the one converting fewer times ranks better, and the
   difference is attributable to the conversion count.
3. **Given** a malformed or unrecognised field in a route, stream or channel declaration,
   **When** it is loaded, **Then** loading fails naming file and field, with no default
   substituted.

---

### Edge Cases

- **A route with no legs** — meaningless; refused at load rather than costed as free.
- **A leg whose currencies do not chain** (a leg ending in EUR followed by one starting in
  USD) — a broken route, reported at load, never silently bridged.
- **A route whose start does not match the stream's arrival venue** — a mismatch, reported
  rather than assumed away.
- **Fees exceeding the amount being moved** — reported as such. **Never clamped to zero**;
  the money must not vanish with no diagnostic (predecessor defect B13).
- **A fixed fee on a very small amount** — cost as a percentage can exceed 100%; reported
  honestly rather than capped.
- **Two routes with identical cost** — a tie, reported as a tie, not broken arbitrarily.
- **A declared premium of zero on a P2P channel** — legal, and means the channel is at the
  reference rate; distinct from a *missing* premium, which is refused.
- **A negative declared premium** (a discount) — permitted with a stated observation date,
  since P2P can trade below the reference rate.
- **A route whose `verified_on` is very old** — usable, but the staleness must surface: a
  silently stale route cost invalidates every comparison built on it.
- **A monthly cap already partly consumed** by an earlier contribution in the same month —
  the remaining headroom is what applies, not the full cap.

## Requirements *(mandatory)*

### Functional Requirements

**Costing a route**

- **FR-001**: The system MUST cost a stated amount through a declared route by applying
  each leg in order, and MUST report what arrives at the far end.
- **FR-002**: The system MUST report cost both **one way** and **round trip**, each
  explicitly labelled, and MUST NOT present a one-way figure where a round-trip figure
  belongs. Round-trip cost is what belongs in a comparison.
- **FR-027**: Round-trip cost MUST be computed from a **separately declared exit route**,
  not by reversing the inbound one. Getting money back into spendable base currency has its
  own chain, its own spreads and its own limits (§4.3.3), and reversing the way in would be
  wrong wherever the way out differs — which it does.
- **FR-030**: A destination with **no declared exit route** therefore has **no round-trip
  cost**, and MUST NOT be presented as comparison-ready. It is reported as *exit cost
  unknown*, naming the missing declaration. This is the honest consequence of FR-027 rather
  than a gap in it: Principle VI holds that an asset which cannot be liquidated into
  spendable base currency at a reasonable cost is not worth its stated value, and a
  destination whose exit nobody has costed is precisely that case. A one-way figure MUST
  NOT be silently promoted to stand in for the missing round trip.
- **FR-003**: The system MUST attribute cost to its components — conversion spread,
  percentage fees, fixed fees — so a reader can see which term dominates. "Most of the gap
  is the ramp, not the asset" is the sentence this feature exists to let the tool write.
- **FR-004**: ⚙ **Corrected during implementation.** A declared premium `p` in base
  currency per unit of foreign currency MUST produce **two** separately labelled figures,
  and the difference between them is not a rounding detail:
  - the **cost** — what fraction of the money was actually lost — is `p / (r + p)` when
    buying the foreign currency and `p / r` when selling. The conversion happens at the
    rate actually transacted at, so the arriving amount is the one the venue would really
    hand over.
  - the **spread over the reference rate** is `p / r`. This is the figure
    `SIMULATOR_SPEC.md` §4.3.1 quotes, and it MUST remain reproducible so the output stays
    traceable to the claim that motivated this feature.

  The first draft of this requirement mandated `p / r` as *the* cost, on the reading that
  §4.3.1 defined it. Implementation showed the consequence: a +3 premium on a reference of
  42 means a P2P price of 45, so 10 000 UAH buys 222.22 USD — but charging `3/42` of the
  amount and converting the remainder at 42 reports **221.09 USD, short by 1.13 USD**. The
  arriving amount was wrong, not merely differently framed. §4.3.1 labels its own arithmetic
  illustrative ("substitute the live rate; this is illustrative"), so reading it as a
  definition of cost was the error. On the **sell** side the two coincide exactly, so the
  correction moved the buy side only.
- **FR-005**: Costs MUST NEVER be silently clamped. If fees exceed the amount, the system
  reports that; the money never vanishes without a diagnostic. Every fee is an explicit
  recorded line, never blended into the outcome.

**Streams**

- **FR-006**: Income streams MUST be declared data carrying currency, amount, cadence,
  arrival venue and indexation policy.
- **FR-007**: A stream MAY declare an income-tax rate, and deployable capacity MUST be
  reported net of it, so the amount available to invest is never overstated.
- **FR-008**: Access cost MUST be reported per `(destination × stream × route)`. A cost
  attributed to a destination alone MUST NOT be representable — not merely discouraged.
- **FR-009**: A route that performs no conversion MUST report a conversion cost of exactly
  zero, not a small residual.

**FX channels**

- **FR-010**: Exchange rates MUST be declared per **channel** — official, interbank, bank
  non-cash, cash desk, card, peer-to-peer — and MUST be two-sided. A single mid-rate MUST
  NEVER be used for a transaction.
- **FR-011**: Which channel a leg uses MUST be part of the leg's declaration, and the
  channel actually applied MUST appear in the attribution, because the choice changes the
  result.

**Feasibility**

- **FR-012**: Declared caps, minimums, latency and status MUST be enforced. Total deployed
  MUST equal what the route allows, never what the plan requested.
- **FR-013**: When a contribution cannot execute, the declared fallback policy MUST be
  applied — hold as cash, place on deposit, redirect to a named destination, or skip — and
  **every occurrence MUST be reported** with its date, amount and reason.
- **FR-014**: A route unusable for a stated amount or date MUST be reported as such with
  the binding constraint named, and MUST NOT be silently adjusted, rounded, or omitted
  from the comparison without a recorded reason.
- **FR-015**: A monthly ceiling MUST account for capacity already consumed in the same
  month.

**Comparison and selection**

- **FR-016**: Given an amount and a destination, the system MUST rank the available routes
  by round-trip cost, ceiling and latency, recommend one, and report what each alternative
  would have cost. Route choice is a modelled comparison, never a configuration constant.
- **FR-029**: Every candidate route MUST be costed **in full, through the same path as the
  recommendation** — never summarised, estimated, or costed by a cheaper approximation.
  A comparison whose alternatives were priced differently from its winner is not a
  comparison; it is a recommendation with decoration, and the discrepancy would surface as
  an unexplained gap the first time someone checked one by hand.
- **FR-017**: Two routes differing only in the number of conversions MUST rank in the
  order that cost implies, and the difference MUST be attributable to the conversion count.
- **FR-018**: A tie MUST be reported as a tie.

**Regimes**

- **FR-019**: A scenario MAY declare a transition date and a route set per regime.
  Contributions before and after MUST use the corresponding set.
- **FR-020**: A transition date MUST be presented as a stated assumption, never as a known
  fact.

**Declared data and provenance**

- **FR-021**: Routes, legs, channels and streams MUST be declared data. Adding a venue, a
  provider or a currency corridor MUST NOT require a source-code change.
- **FR-022**: Every observed value MUST carry its source, retrieval date and verification
  date, and the unverified mark MUST propagate to every figure derived from it — as it
  already does for the OVDP yield.
- **FR-023**: A route registry entry MUST be per `(provider × currency path × venue)`,
  never per provider, because conversion count is usually the largest difference between
  two ways of doing the same thing.
- **FR-024**: A declaration that is malformed, unrecognised, incomplete, duplicated, or
  whose legs do not chain by currency and venue MUST fail at load time naming file and
  field, with no default substituted.
- **FR-025**: Staleness MUST surface. A value whose verification or retrieval date has
  aged past its threshold MUST be reported as stale on every figure derived from it.
  A silently stale route cost invalidates every comparison built on it.
- **FR-028**: The staleness threshold MUST be **per kind of value**, declared alongside the
  kind rather than fixed once for the project. A peer-to-peer premium ages in days; a
  bank's published fee schedule ages in years; a regulatory limit changes when the
  regulator says so. A single threshold would either cry wolf on fee schedules or stay
  silent on premiums, and a staleness warning that is usually wrong is one that gets
  ignored — which is worse than none. A value kind with no declared threshold MUST fail at
  load rather than defaulting to a permissive one.
- **FR-026**: A per-leg disruption probability MUST be declarable and reported, and MUST
  NOT be silently folded into a cost figure — it describes the chance the route stops
  working, which is a different claim from what it charges.

### Key Entities

- **Income stream** — where money arrives and in what currency: amount, cadence, arrival
  venue, indexation, optional income-tax rate. Two exist; the difference between them is
  the finding.
- **Venue** — a place money can sit: a bank account, an exchange account, a broker
  account, a fund platform. Declared, with the currencies it can hold.
- **Route** — an ordered chain of legs from one venue to another, identified by
  `(provider × currency path × venue)`, with a status and an availability window.
- **Leg** — one movement: a transfer, a conversion, a trade, a withdrawal. Carries
  percentage fee, fixed fee, conversion markup, minimum, maximum, monthly cap, latency,
  availability window, disruption probability, and provenance.
- **FX channel** — a named two-sided rate source: official, interbank, bank non-cash, cash
  desk, card, peer-to-peer. A P2P channel is declared as a premium in base currency per
  unit of foreign currency against a stated reference.
- **Regime** — a named set of routes and their terms, effective over a period, with the
  transition between regimes stated as an assumption.
- **Fallback policy** — what happens to money that cannot be deployed: hold as cash,
  deposit, redirect, skip.
- **Ramp cost** — the result: what arrives, cost one way, cost round trip, attributed to
  its components, per `(destination × stream × route)`, carrying provenance and staleness.
- **Feasibility report** — every constraint that bound, every fallback that fired, with
  dates, amounts and reasons.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a stated amount, a declared P2P premium and a stated reference rate, the
  one-way and round-trip cost percentages match independently hand-computed figures to
  within the single project tolerance, with the arithmetic recorded beside the check.
- **SC-002**: A declared premium of +3 UAH against a reference of 42 reproduces
  `SIMULATOR_SPEC.md` §4.3.1's `3/42 = 7.14%` exactly **as the spread over the reference
  rate**, and reports `3/45 = 6.67%` as the cost — with 222.22 USD arriving, which is what
  a P2P screen showing 45 would actually pay. Both figures present, each labelled.
- **SC-003**: The same acquisition funded from the UAH stream and from the USD stream
  differs by exactly the hand-computed ramp cost, and the USD-funded path reports a
  conversion cost of exactly zero.
- **SC-004**: A fully domestic route with zero declared fees costs exactly zero and
  delivers exactly what was sent.
- **SC-005**: No cost figure anywhere in the output is presented without an explicit
  one-way or round-trip label — verified across every reported figure, not sampled.
- **SC-006**: No cost figure is attributable to a destination alone; every one names its
  stream and route.
- **SC-007**: A plan exceeding a monthly cap deploys exactly the cap, and every fallback
  occurrence appears in the output with date, amount and reason. Count of occurrences
  reported is never zero when occurrences happened.
- **SC-008**: Two routes differing only in conversion count rank in the expected order,
  and the cost difference is attributable to the conversions.
- **SC-009**: A regime transition changes the round-trip cost by exactly the hand-computed
  difference between the two regimes.
- **SC-010**: A new provider, venue and corridor are added and ranked with **zero** lines
  of source code changed.
- **SC-011**: Every malformed, unrecognised, missing, duplicated or non-chaining field in
  a route, stream or channel declaration produces an error naming file and field, measured
  across a deliberate battery of broken files. No case results in a substituted default.
- **SC-012**: With one route input left unverified, 100% of figures derived from it carry
  the unverified mark, and a value aged past the staleness threshold is reported as stale
  on every derived figure.
- **SC-013**: Fees exceeding the amount moved are reported as such; no amount is ever
  clamped to zero, and total fees recorded equal total fees applied.
- **SC-014**: A destination with no declared exit route reports *exit cost unknown* and is
  excluded from any round-trip ranking. No one-way figure appears in its place.
- **SC-015**: A value whose kind declares a short threshold is reported stale after a
  shorter age than one whose kind declares a long threshold — verified with two values of
  different kinds and the same retrieval date. A value kind with no declared threshold
  fails at load.
- **SC-016**: The recommended route's cost and every alternative's cost are produced by the
  same function; asserted by construction, not by comparing two numbers that happen to
  agree.

## Assumptions

- **Every observed number here is unverified at first run.** `SIMULATOR_SPEC.md` §11 item
  1 lists what has not been observed: Monobank's card markup and monthly limit,
  TransferGo's live quote, Coinbase withdrawal fees, the Binance fee tier. These enter as
  dated observations with empty verification dates and the marks propagate. No verified
  figure is invented, and no real citation is attached to an invented number.
- **The destination is a currency balance at a venue, not an instrument.** "Move 10 000 UAH
  into USD at Binance" is the shape. Cash and FX are already first-class per §3.6, and the
  ramp is about getting money there, not about what is bought once it arrives. This keeps
  crypto, foreign equities and their return models entirely out of this feature while still
  answering §8 question 7 in full.
- **`G1`'s "same crypto purchase from two streams" is satisfied in its essential form** —
  the same USD acquisition funded from each stream, differing by exactly the ramp cost. The
  crypto instrument itself arrives with a later feature; the ramp cost is the whole content
  of that test.
- **Rates and premiums are declared observations, not a live feed.** No provider, no
  network, no cache. The offline snapshot and hand-maintained files are the source, per §7.
- **Routes are declared in pairs.** FR-027 means an inbound route without a declared exit
  partner yields no round-trip figure, so the registry is populated in pairs before the
  first comparison exists. Accepted cost of the decision.
- **One owner, no authentication.** Records carry an owner identifier as before.
- **No delivery surface.** No web interface, no command-line interface. Results are
  produced and asserted by the test suite.

## Clarifications resolved

All three answered by the owner on 2026-08-22.

| # | Question | Decision | Where it landed |
|---|---|---|---|
| 1 | Round trip by reversing the inbound route, or from a declared exit route? | **Declared exit route**, separate and equally modelled | FR-027, and its consequence FR-030 |
| 2 | One staleness threshold, or per value kind? | **Per value kind**, declared with the kind; no permissive default | FR-028 |
| 3 | Cost every route fully, or cost the recommendation and summarise the rest? | **Every route in full, through the same code path** | FR-029 |

### Correction found during implementation

**FR-004 was wrong and was corrected**, not worked around. It mandated `p / r` as the cost
of a premium, which produced an arriving amount 1.13 USD short of reality on a 10 000 UAH
purchase. The full reasoning is in FR-004 itself; the short version is that `p / r` is a
spread over a *rate* and `p / (r + p)` is a fraction of *money*, and only the second is a
cost. Both are now reported, separately labelled.

This is the second time in this project a figure has been correctly computed under a wrong
label — the first was `nominal_ytm` in feature 001 moving with the coupon policy. Both were
found by implementation rather than by review, and both are recorded rather than quietly
fixed.

**The first decision has a consequence worth stating on its own.** Requiring a declared
exit route means a destination nobody has costed the exit for has **no round-trip figure at
all** — and since FR-002 makes round-trip the number that belongs in a comparison, such a
destination cannot be compared. That is not a hole in the decision; it is the decision
working. Principle VI says an asset that cannot be liquidated into spendable base currency
at a reasonable cost is not worth its stated value, and "we never checked how to get out"
is exactly that situation. The alternative — quietly reversing the inbound route — would
have produced a confident round-trip number for an exit path nobody had ever looked at,
which is the class of figure this whole project exists to refuse.

It does mean the route registry has to be populated in pairs before the first comparison
appears. That cost is accepted.

## Required tests this feature closes## Required tests this feature closes

| Row | What it asserts |
|---|---|
| **G1** | Same acquisition, two streams, differing by exactly the hand-computed ramp cost |
| **G2** | A +3 UAH premium at a stated reference reproduces the §4.3.1 percentage |
| **G3** | A plan over a monthly cap queues the excess and reports every occurrence |
| **G4** | A regime transition switches the route set; cost drops by the hand-computed difference |
| **G5** | Two route variants differing only in conversion count rank as expected |
| **G6** | No comparison reports a one-way cost as round-trip |
| **F5** | Channel selection changes the result and is visible in attribution; no mid-rate |
| **B13** | Costs never silently clamped; fees are explicit lines |

## Out of scope

Named explicitly so the plan does not drift: new instruments of any kind, market prices
and return models, the display-currency switch, inflation and CPI, the decision layer and
candidate generation, objectives and constraints, Monte Carlo, the web interface, and the
command-line interface.

And one boundary worth stating on its own, because it becomes tempting the moment FX
exists: **the tax asymmetry where a position flat in USD across a devaluation posts a
taxable UAH gain** (required test **F1**, which `REWRITE_BRIEF.md` calls "the reason the
rewrite exists"). It needs a taxable foreign instrument and dated official rates for the
tax base, and it belongs with the feature that introduces one. This feature builds the FX
channels that will make it possible and deliberately stops there.
