# Feature Specification: The candidate card — why exactly this figure

**Feature Directory**: `specs/027-candidate-card`

**Feature Branch**: `spec/027-candidate-card`

**Created**: 2026-09-07

**Status**: **Drafted** — two clarifications open (below). Planning may not start until both are answered.

**Input**: Owner roadmap, 2026-09-06, step 2 after the answer screen. A card behind a candidate that
says where the money went: a **waterfall** from the amount that left the income stream to the money
that reached home, and a **timeline** of the dated events against the horizon window. *This answers
"why exactly this figure", without which the ranking cannot be trusted.*

---

## Why this feature exists

026 puts the answer on a screen: three horizon columns, a card per non-dominated member, *money
back* and a rate. A reader who does not already trust the engine has no way to check one. The
figures the card shows are conclusions, and every intermediate the engine passed through on the way
to them is thrown away inside the join.

**Measured 2026-09-07** (`answer_question` over the shipped `data/`, question
`fifty-thousand-hryvnia`, `as_of` 2026-09-06): **66 projections are built and discarded** in one
answer, one per ranked outcome — 63 from the bond arm and 3 from the fund. A bond's holds the dated
cash-flow rows with gross, tax and net, the tax charges with their bases and their citations, and
the premium or discount struck at purchase. `_hold` holds one in a
local variable, reads a few totals off it, and returns a `TupleOutcome` that has nowhere to put it —
`core/results/tuple.py` imports no projection record at all.

Required test **E11** has been open since feature 001 for exactly this reason: a reader looking at a
schedule sees `0.00` on every tax row and cannot tell *exempted* from *not applicable*. The engine
has always kept them apart. Measured on the shipped registry: **119 tax charges, every one zero and
every one carrying its exemption's citation**, beside **63 schedule rows whose tax rests on no
source because no rule ran**. 182 rows of `0.00`, two different claims, and no surface has ever
drawn them. 026's own `tasks.md` records that it does not close E11 because it renders no waterfall.
This is that surface.

## What the join drops today

Measured by reading `core/decision/tuple_outcome.py` and `core/results/`, 2026-09-07.

| Dropped | Where it is computed | What the card cannot draw without it |
|---|---|---|
| `Projection.schedule` — every `CashFlowRow`: date, kind, quantity, gross, tax, net, the convention that shaped it, the declaration that caused it | `results/project.py`, held at `tuple_outcome.py:430` | every lifecycle bar, every coupon on the timeline, and E11's two zeros |
| `Projection.charges` beyond `.total` — `pit`, `levy`, `taxable_base`, `tax_class_id`, `charged_for_year` and each charge's own provenance | same | the tax bar's base, and which rule struck it |
| `Projection.at_purchase` — the whole `PurchasePremium` | same | what was paid over or under the paper's principal |
| the clean/accrued split at the **buy** leg | `tuple_outcome.py:999`, summed to a dirty price at `:1009` | the accrued-interest bar the owner named. Kept at the **sell** leg as `SoldEarly`, so the card can draw it going out and not coming in |
| the way-in charge by component and by segment | `OneWayCost.components`, a local in `_assemble` | the entry bar as anything but one number |
| the way-out charge per dated release | `cost_exit(...)` at `tuple_outcome.py:1291` | the exit bar. `Arrival` carries `released` and `amount` and **not the charge between them** |
| the declared `latency_days`, in and out | consumed into two dates at `:426` and `:1320` | the timeline's latency segments |
| the **purchase date** | `:426` | the timeline's first event after the money leaves |
| a `FundProjection`'s dated records — `distributions` and `exit_line` — which the join consumes into the release series and does not keep | `results/fund.py` | a fund's timeline and its lifecycle bars, for a candidate the shipped registry **ranks** |

Two facts the join keeps that must not be mistaken for a waterfall:

- **`TupleOutcome.parts` is an attribution, not an addition.** Its own assembly says so: the six
  parts are in up to three currencies, and `exit_terms` and `lifecycle` describe the same money from
  two sides. Summing them double-counts. It answers *which term dominates*, which is 010 FR-005's
  question and not this one.
- **`reaches` is not the sum of the projection's flows.** Six things happen outside the projection —
  the way-in charge, the way-out charge per date, the remainder's own journey, the netting of
  several events on one date (a date netting to exactly zero is dropped from `arrivals` entirely),
  the tax being subtracted before the percentage exit fee rather than after, and the purchase being
  excluded from the release stream. A waterfall that reconstructs any of them by subtracting two
  served figures is a figure with no owning call and no test.

## The one change, and where it is served

**The core computes nothing new. It stops discarding.** Every amount named below already exists in a
local variable at the moment the outcome is assembled.

**Decision: a separate endpoint, keyed by a key the API publishes.** The alternative — carrying the
projection on `TupleOutcome` — was measured and costs the following.

| | Carried on the record | A per-candidate endpoint |
|---|---|---|
| the answer document | **8 492 187 → 11 707 171 bytes** (+38%): the 63 bond projections encode to 36 407 / 47 249 / 69 857 bytes (min / median / max) and 3 120 700 in total, and the 3 fund projections to 31 428 each and 94 284 in total. The baseline is the served response body; the projections are encoded through the same fold | unchanged |
| what a reader pays for | 66 projections to open one card | one |
| cost of one card | none | one answer plus one evaluation. **The two readings taken on 2026-09-07 disagree by 3×** — four warm in-process runs spanning 0.153–0.195 s, and a second reading of 0.45–0.49 s — so the figure settles this table and settles nothing about how a card feels (plan R3) |
| feasible at all? | **no.** `tests/contract/test_tags_and_unions.py` asserts a record's served fields equal its declared fields, so a field on `TupleOutcome` is on the wire in every response that carries one. There is no serving it in one place and not another | yes |

A third fact settles the shape rather than the size: **`Projection` is not serialisable today.**
`LedgerState.capacity` is keyed by `CapacityKey`, which has no JSON object key form, so the shape
algebra refuses the record outright (reproduced 2026-09-07). What is served is therefore a record of
the flows, not the ledger — and the audit trail survives as each row's `caused_by`, which names the
declaration rather than pointing at an event nobody can fetch.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — He asks where the money went (Priority: P1)

The owner opens a candidate on the answer screen and sees one waterfall: what left his salary, what
the way in charged, what actually bought units, what the holding paid him, what tax was struck on
it, what the way out charged, and what reached his bank. Each bar is a figure the API sent, with its
own mark.

**Why this priority**: it is the feature. **Independent Test**: open a card over the shipped `data/`
and check each bar's amount against the served flow of the same date and kind.

**Acceptance Scenarios**:

1. **Given** a ranked candidate, **When** its card opens, **Then** every bar's amount equals a
   served flow's amount, and no bar is the difference between two other bars.
2. **Given** the shipped registry, **When** a tax bar renders, **Then** a zero carrying its
   exemption's citation is drawn and labelled differently from a zero resting on no source — E11.
3. **Given** a candidate whose way in and way out are in different currencies, **When** the card
   renders, **Then** the bars are grouped per currency with no joined baseline and the reason is
   named; no rate is consulted anywhere.
4. **Given** a bar whose flow the served record does not carry — a fund states no cash-flow
   schedule — **When** the card renders, **Then** that bar is a **refusal bar** naming what is
   missing, never a bar of zero and never an absent bar.

---

### User Story 2 — He asks when it happened (Priority: P1)

Beside the waterfall, a timeline on the horizon axis: the money leaving, the purchase, each coupon,
the redemption or the sale, each arrival at the spendable endpoint, the remainder's own arrival, and
the window's two boundaries.

**Why this priority**: half of *why this figure* is *over what period*, and the rate is measured over
a span that is not the window. **Independent Test**: render each shipped candidate's timeline and
check every marker against a served date.

**Acceptance Scenarios**:

1. **Given** a candidate, **When** the timeline renders, **Then** the horizon's start and end are
   drawn as boundaries and every event is placed by its served date.
2. **Given** a coupon inside the window and one outside it, **When** both render, **Then** the
   second is drawn beyond the boundary and marked as outside, never omitted.
3. **Given** a candidate sold at the window's end and one whose own terms closed it inside,
   **Then** the two are drawn differently, from the served typed fact and not from a sentence.
4. **Given** a date on which the holding paid and the tax charged on it consumed the payment
   exactly, **When** the timeline renders, **Then** the event is on it — the released series drops
   such a date and the schedule does not.
5. **Given** a release and its arrival, **When** the segment between them renders, **Then** its
   length is the served declared latency and the card states it in days.

---

### User Story 3 — He can check the number without leaving the card (Priority: P2)

Each bar names its mark; the full provenance texts sit once behind a disclosure; a tax bar names the
class that struck it and the base it was struck on.

**Why this priority**: a mark that does not travel to the last surface is the top-severity defect
Principle I names. **Independent Test**: strip the styles and read every mark; count the belief
statement's occurrences on the screen.

**Acceptance Scenarios**:

1. **Given** a bar whose amount is marked unverified or stale, **When** it renders, **Then** it
   carries the badge and the mark's own words are reachable in full.
2. **Given** the answer screen already showing the early-exit belief once, **When** a card opens,
   **Then** the card does not repeat the statement; it marks the bars that lean on it.
3. **Given** a projection whose provenance runs to a page — measured, a sample card's served flows
   carry 25 538 characters of citation against 43 094 bytes of body — **Then** it is behind a
   disclosure, never elided to a fixed length.

---

### Edge Cases

- **A key the answer did not publish.** A named state carrying the key; the client composes no key.
- **A remainder that did not come home** (`RemainderStayed`). Its own refused bar, beside a timeline
  with no arrival marker for it — the case 026 FR-017 renders beside the headline.
- **A fund**, which the shipped registry ranks. No cash-flow schedule exists and the dated
  distributions and the exit line do; the bars come from those, and the bars a bond has and a fund
  does not are refusals.
- **A candidate ranked but withheld from the front.** It still opens a card: the reader most needs
  the reason for a figure he was not shown.
- **Two flows on one date.** Two events and two lifecycle bars, never merged — merging is the
  netting the released series does, and it is what hides a coupon consumed by its own tax. Their way
  **out** is one movement and one charge, which is FR-013's last clause and not an exception here.

## Requirements *(mandatory)*

### The core stops discarding

- **FR-001**: The evaluation MUST return the projection it computed beside the outcome, in a
  serialisable record. It MUST NOT recompute, re-derive or re-sum any amount: every figure in it is
  one already held when the outcome is assembled.
- **FR-002**: `TupleOutcome`'s **served field set MUST NOT change** beyond FR-006's key. Measured:
  a field on that record is on the wire in every response that carries one, so the projection may
  not live there.
- **FR-003**: The served projection MUST be a **tagged union with one member per projection kind the
  engine builds**, because the two kinds hold different dated records and neither may be re-shaped
  into the other's. Each member MUST carry, per dated flow: the date, the kind from the engine's own
  closed vocabulary, the quantity where one moved, the gross amount, the tax charged on it, the net,
  the declaration that caused it, and the convention that shaped it where the arm states one — each
  amount with its currency and its own provenance.
- **FR-004**: It MUST carry each tax charge's **base**, its two lines **and their total**, the class
  that struck it, the year it accrues to, and the charge's own provenance. The total is served rather
  than left to be added, because the tax bar is that one figure and summing two lines in the client
  is the derivation FR-013 forbids. Whether it also carries the **rate** is
  [NEEDS CLARIFICATION: CL-1].
- **FR-005**: It MUST carry, because each is computed and dropped today: the **purchase date**; the
  clean/accrued split of the price paid at purchase; the way-in charge **by component and by
  segment**; the way-out charge **per dated release**; the declared latency in and out; and the
  premium or discount struck at purchase. The remainder's record and its journey are already on the
  outcome and MUST NOT be duplicated here.
- **FR-006**: The answer MUST publish a **key per evaluated outcome** that addresses it uniquely
  across sections, and the client MUST NOT compose one. It MUST be derived from the five-term
  candidate identity the engine already fixes, so the identity is not stated twice.
- **FR-007**: A bar or an event an arm carries **no flow for** MUST be a typed absence naming what
  the arm does not state, never an empty record and never a record of zeros. There is deliberately
  **no** *projection could not be produced* refusal: `_hold` returns its refusal before any outcome
  exists, so every evaluated outcome has a projection, and only an evaluated outcome carries FR-006's
  key — a candidate with no projection has no address to ask about. A **fund is not that case**
  either: measured 2026-09-07, `inzhur_miltech` is a ranked candidate in every section and its
  projection is real. It states no cash-flow schedule and, in this window, no distribution — it
  states an exit line — which is what FR-003's union and this absence exist to keep honest.
- **FR-008**: `docs/METHODOLOGY.md` §29 MUST state what the served projection carries and what it
  still does not — the ledger, which is unserialisable, and every term the way-out charge is netted
  against out of order.

### Over HTTP

- **FR-009**: One **GET** endpoint MUST serve one candidate's projection, addressed by FR-006's key
  under the answer it belongs to, taking the same `as_of` the answer took.
- **FR-010**: The endpoint MUST satisfy the wire contracts unchanged: a distinct tag and model name
  per new record, every union of records discriminated, a served field set equal to the declared
  one, provenance on every `Money`, reproducible bytes across hash seeds, and no figure computed in
  the HTTP layer.
- **FR-011**: An unknown **question** and a key naming **no evaluated candidate in this answer** MUST
  be two distinguishable typed results, because the remedies differ — a wrong URL against a stale
  client. There is no third: FR-007 records why a refused candidate has no address.
- **FR-012**: The answer document's size MUST NOT grow beyond FR-006's key. A projection reaches a
  reader only when he opens one.

### The waterfall

- **FR-013**: Bars MUST be in the order the money moved — what left the stream, the way-in charge,
  what arrived, what bought units, what was left over, what the holding released, the tax struck on
  it, the way-out charge, what reached home — and each bar's amount MUST be a **served flow**. The
  client MUST NOT subtract one served figure from another to obtain a bar. The way-out bar is the
  one that is **per dated release rather than per flow**, and MUST say so: the charge is struck once
  on what a date nets, because a flat fee is charged per movement, so two lifecycle flows on one date
  travel home once and share one charge. Splitting it between them would be the derivation this
  requirement forbids; drawing one bar per flow would report the fee twice.
- **FR-014**: The waterfall MUST NOT be built from `TupleOutcome.parts`. Those six are an
  attribution in up to three currencies in which two members describe the same money from two sides;
  read as a waterfall they double-count. Whether the attribution is shown **beside** the waterfall is
  [NEEDS CLARIFICATION: CL-2].
- **FR-015**: Where the bars are not all in one currency the card MUST NOT draw one connected
  waterfall. It groups per currency, states why, and consults **no** rate — the display switch is
  deferred and every declared channel's reference rate is a synthetic fixture.
- **FR-016**: A bar the served record refuses MUST render as a **refusal bar** carrying its reason,
  visually distinct from a bar of zero. A zero is a value; an absence is not.
- **FR-017**: A **tax bar of zero** MUST say which zero it is: exempted, carrying the citation, or
  no rule ran, carrying nothing. This closes required test E11.
- **FR-018**: Every bar MUST carry its own mark. A bar whose amount arrived unmarked while its
  outcome is marked MUST say which mark it wears and whose it is.
- **FR-019**: The card MUST state that the waterfall does not sum to the ranking's rate, and why:
  the rate is measured over the span, and the horizon is the window.

### The timeline

- **FR-020**: Events MUST be placed on an axis carrying the **horizon window's two boundaries**, and
  an event outside the window MUST be drawn outside it and marked, never dropped and never clamped.
- **FR-021**: Every event MUST come from a served date. The vocabulary MUST be closed and rendered
  exhaustively; a kind the client has no label for renders raw, never blank.
- **FR-022**: The timeline MUST draw the events of the **schedule**, not of the released series: a
  date whose payment its own tax consumed exactly is absent from the second and present in the first.
- **FR-023**: A **latency segment** MUST be drawn from the served declared latency — in, between the
  money leaving and the purchase; out, between each release and its arrival — and stated in days.
  Waiting is inside the span the rate is measured over, and a timeline that hides it hides a cost.
- **FR-024**: The remainder's own arrival MUST be a marker of its own where the served record says it
  came home, and a named state where it says it did not.

### Provenance, text, and reach

- **FR-025**: A mark MUST use 026's four-tone badge vocabulary unchanged, and the full provenance
  text MUST sit behind a disclosure, reachable in full, never elided to a length.
- **FR-026**: A belief the answer screen already states once MUST NOT be restated on the card; the
  bars leaning on it carry a mark.
- **FR-027**: Every figure MUST be rendered through 026's one formatting module. No unrounded float
  may reach the document.
- **FR-028**: A card MUST be openable from **any ranked row** of the answer screen, not only from a
  non-dominated member, and MUST be closable back to the reader's place.
- **FR-029**: The card MUST meet 021's accessibility requirements unchanged: keyboard reach with
  visible focus, AA contrast in both themes, and no information carried by colour alone. A waterfall
  and a timeline MUST each be readable as text with every style declaration stripped.
- **FR-030**: A **contract test over the shipped `data/`** MUST assert, for every ranked candidate of
  the owner's declared question and for **both** members of FR-003's union, that the served flows
  account for `reaches` at the imported project tolerance and that every served flow carries a mark.
  Neither a local tolerance nor a second definition of a mark, and no candidate skipped — a ranked
  candidate the assertion cannot reach is FR-007's refusal and is asserted to be one.

## Success Criteria *(mandatory)*

- **SC-001**: For every ranked candidate of the shipped question — **every** member of FR-003's
  union, none skipped — the served flows account for `reaches` at the project tolerance, asserted,
  not inspected.
- **SC-002**: 100% of served flows carry a provenance mark, and no bar on a rendered card is
  unmarked while its flow is marked.
- **SC-003**: E11 is closed: a cited zero and an uncited zero render differently, asserted over the
  rendered card against both cases on the shipped registry.
- **SC-004**: No bar's amount is the arithmetic difference of two others, asserted over the source of
  the drawing components.
- **SC-005**: The answer document's size is unchanged **by this feature** beyond the published key —
  measured on the served response body, against a baseline re-taken on the tree the implementation
  starts from. It is not the 8 492 187 bytes of 2026-09-07: `fix/undeployed-remainder` adds a served
  field to every outcome with a remainder and must land first, so a constant here would be red for a
  reason that is not this feature's.
- **SC-006**: Opening a card issues exactly one request, and its wait has a named state.
- **SC-007**: Every event and boundary the API sends for a candidate is on the timeline; none is
  dropped, clamped or merged.
- **SC-008**: Zero unrounded floats reach the document, and zero AA violations in both themes.

## Clarifications

Two open. Planning may not start until both are answered; the graph carries this feature as
`drafted` until they are.

**CL-1 — Does a tax bar name the rate that struck it?** Measured: the engine records the base, the
two lines, the class id and the citation of the dated entry, and **never the rate**. Options: **(a)**
the bar shows the base and the charge and names the class, and no rate is shown; **(b)** the client
reads the declared class and renders its dated rates beside the bar; **(c)** the charge carries the
entry it applied, which is a wire-visible engine change beyond *stop discarding*.
**Recommendation (a)**, with (c) recorded as a future: every charge the shipped registry produces is
a cited zero under one exempt class, measured above, so a rate renders `0% + 0%` on every bar and the
question only becomes live the day something taxed is ranked.

**CL-2 — Does the six-part attribution appear beside the waterfall?** The attribution answers *which
term dominates* and the waterfall answers *where the money went*; they are different readings of one
candidate and FR-014 forbids merging them. Options: **(a)** the waterfall alone; **(b)** both, each
labelled as its own reading; **(c)** the attribution alone, and no waterfall.
**Recommendation (b)** — 010 FR-005 exists for the first sentence the tool was built to write, *most
of the gap is the ramp, not the asset*, and no surface has ever shown it. Against it: the owner's
complaint about 021 was *overloaded*, and a second chart per card is exactly that risk.

## Out of scope

- **Editing a plan or a question.** A declaration is changed in git and reviewed like code.
- **Scenario comparison** — 028.
- **The interactive graph.** Its `[[future]]` entry stands; this feature draws no edges.
- **The display-currency switch**, deferred by owner decision 2026-09-03. FR-015 is what that costs.
- **A tax payment's own date.** The charge is netted where it accrued; reaching the declared deadline
  needs the filing machinery the join does not carry, and the outcome's `excludes` already says so.
- **Serving the ledger.** Unserialisable as declared, and the audit trail the card needs is each
  row's own `caused_by`.
- **Naming which assumption decides between two candidates** — 019 FR-021 refuses it.

## Assumptions

- 026 is `done` on `main` and supplies the visual language, the badge vocabulary, the formatting
  module and the figure slot.
- **Every measurement here was taken at `e84b3b8`**, the branch point, and `023-cash-instrument`
  landed on `main` while this spec was being written. It adds `CashProjection` — a **third**
  projection arm — so the candidate population, the projection count and the answer's byte size all
  move, and FR-003's union gains a member. The requirements are written per-arm and survive it; the
  figures are dated and must be re-taken on the tree the implementation starts from, which is what
  SC-005 already says of its own baseline.
- **`fix/undeployed-remainder` must land first, and had not on 2026-09-07.** It is 026's blocker too,
  and `needs` cannot name it because it is a fix rather than a feature. Until it lands `reaches` is
  the deployed part alone, `RemainderCameHome` and `RemainderStayed` do not exist on `main`, and
  **every measurement in this spec was taken without it** — which is why SC-005's baseline is a
  method rather than a constant.
- 019, 020 and 021 are unchanged by this feature except for the one endpoint and the published key;
  `as_of` is 021's, and the endpoint reads the clock the answer read.
- The screen shows one declared question, as 026 assumes.
- Every measurement above is reproducible from the shipped `data/` at `as_of` 2026-09-06 and is
  restated nowhere else.
