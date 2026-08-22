# Feature Specification: Tax depth

**Feature Directory**: `specs/009-tax-depth`

**Feature Branch**: `spec/009-tax-depth`

**Created**: 2026-08-22

**Status**: Ready for planning — all clarifications resolved 2026-08-22

**Legal grounding**: the five questions this spec raised were answered by the owner
and by a research pass over the primary text of the Податковий кодекс України
(`https://zakon.rada.gov.ua/laws/show/2755-17`, accessed 2026-08-22) plus ДПС/ЗІР
guidance. Each legal fact below carries its provision, and a verdict level:
**SETTLED** (the primary text answers it), **INTERPRETED** (guidance or form
mechanics answer it, one inference deep), or **UNSETTLED** (no authoritative answer
found — modelled as an explicit, labelled scenario switch, with an індивідуальна
податкова консультація (ст. 52 ПКУ) recorded as the real resolution path).

**Input**: Tax depth — losses that carry, lots the owner chooses, and tax that is
paid with real money on a real date.

---

## Why this feature exists

Feature 001 built the tax interface and proved it on an exempt class — a flat rate
of zero, charged per event, cited and traceable. That was deliberately the easy
case. Everything hard about Ukrainian personal investment tax is still ahead, and
three pieces of it are named required tests:

- **E2 — loss offset and carryforward.** A loss year followed by a gain year must
  net correctly, and a run that omits the loss-year declaration must forfeit the
  carryforward. Both branches matter, because "the tool assumed you filed" and "the
  tool assumed you did not" are *different wrong answers*, and each silently changes
  the after-tax ranking.
- **E6 — lot selection methods.** FIFO and LIFO exist; average-cost and
  specific-lot were left deliberately absent in 001 rather than approximated — a
  disposal naming a specific lot currently fails loudly, because an average-cost
  result computed as FIFO would be a wrong tax figure that looked right. This
  feature adds the missing two, correctly.
- **E7 — tax timing**, the predecessor's defect B5: its engine silently deducted
  tax from the portfolio at the moment of the trade. In reality tax is assessed to
  a tax year and paid *from cash*, on a declared due date in the following year —
  and a plan whose cash is not there on that date has a problem the tool must
  surface. `TaxCharge` already carries `charged_for_year`; this feature makes the
  payment a ledger event, with everything that implies for cash conservation and
  for how much money a plan actually needs to hold back. When the cash is short on
  the due date, this feature stops with a typed shortfall report; modelling the
  forced sale that would follow is an owner-recorded deferral (FR-010).

Together these are the difference between "a rate applied to a number" and a model
of what the owner's declaration and bank account will actually do. A parallel
feature (006, Inzhur instruments) will supply the first real instrument whose
redemption produces a taxable gain; this specification references it only as
context and depends on nothing unfinished — its own worked examples run on declared
synthetic fixtures.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tax is money leaving on a date (Priority: P1)

The owner runs a scenario containing taxable disposals. No tax is taken out of any
position or any sale's proceeds at the moment of the trade — gross amounts land in
the ledger, with the charge recorded beside them. Each charge is assessed to its
tax year, the year's charges accumulate into an annual statement, and the resulting
liability leaves the cash balance as a single dated payment on the declared due
date in the following year. The owner can see, for every year, what was assessed,
from which events, and when the money actually left.

**Why this priority**: This is defect B5, the structural lie in the predecessor's
numbers: deducting tax at trade time misstates both the position and the cash
timeline, and every plan that needs cash on hand next August is invisible to a tool
that pretends tax was already paid. Both other stories build on the annual
assessment this story introduces.

**Independent Test**: Run a scenario with one taxable gain. Verify by hand that the
position and proceeds are gross, that the liability equals the hand-computed charge
assessed to the gain's year, and that exactly one cash outflow for it occurs on the
declared due date in the following year.

**Acceptance Scenarios**:

1. **Given** a taxable disposal with a gain in year Y, **When** the ledger is
   inspected at the disposal date, **Then** the full gross proceeds are in cash,
   the position reflects only the units sold, and no tax has left any balance.
2. **Given** the same scenario, **When** the projection passes the declared payment
   due date in year Y+1, **Then** a single payment event debits the tax-currency
   cash balance by the hand-computed liability for year Y, and the event names the
   assessment it settles.
3. **Given** a year whose assessed liability is zero (only exempt income, or gains
   exactly offset), **When** the projection completes, **Then** the annual
   statement exists and records the zero with the rule that produced it, and no
   payment event occurs — a zero that is evidence, not an absence.
4. **Given** a scenario whose horizon ends after a taxable year but before that
   year's due date, **When** results are reported, **Then** the assessed-but-unpaid
   liability is reported as an open obligation, never silently dropped — an
   end-of-horizon balance that hides next year's tax bill overstates the outcome.
5. **Given** the due-date rule is absent from the declared data, **When** a
   scenario with a taxable event runs, **Then** the run fails naming the missing
   declaration — it does not assume a date, and it does not fall back to paying at
   trade time.

---

### User Story 2 - A loss is worth something, if you file (Priority: P1)

The owner runs a scenario with a losing year followed by a winning year. Whether
the loss-year declaration was filed is an explicit input to the scenario. In the
filed branch, the carried loss reduces the following year's taxable result
according to the declared carryforward rules and the tax falls accordingly. In the
unfiled branch the carryforward is forfeited, the gain year is taxed in full, and
the output states what the omission cost.

**Why this priority**: Required test E2. The carryforward is real money — 23% of
the netted amount — and its existence hinges on an administrative act the tool
cannot observe. Modelling only one branch bakes in an assumption about the owner's
filing behaviour; the difference between the branches *is* the information.

**Independent Test**: One fixture, two runs differing only in the filing flag.
Check each year's tax by hand in both branches; verify the two differ by exactly
the hand-computed value of the carryforward.

**Acceptance Scenarios**:

1. **Given** a year with a net investment loss and a following year with a gain,
   and a scenario declaring the loss-year declaration filed, **When** the gain year
   is assessed, **Then** the carried loss reduces the taxable result per the
   declared carryforward rules and the tax matches the hand-computed netted figure.
2. **Given** the same two years and a scenario declaring the loss-year declaration
   *not* filed, **When** the gain year is assessed, **Then** the gain is taxed in
   full, and the output names the forfeited carryforward and its amount — the cost
   of not filing is visible, not merely absent.
3. **Given** a scenario that declares no filing behaviour at all, **When** a loss
   year occurs, **Then** the run reports the missing declaration as an explicit
   failure rather than assuming either branch — there is no default filing
   behaviour.
4. **Given** a loss year whose carryforward is never absorbed before the horizon
   ends, **When** results are reported, **Then** the remaining carryforward is
   reported as an open balance with its origin year, never silently discarded.
5. **Given** gains and losses within one year in the same declared income
   category, **When** the year is assessed, **Then** they net to a single annual
   result before any rate applies, per the declared netting rules.
6. **Given** a filed loss year, a following year with investment operations but no
   declaration, and a gain year after that, **When** the gain year is assessed,
   **Then** the scenario's declared chain-continuity switch governs — the
   chain-broken branch forfeits the carryforward, the chain-restorable branch nets
   — and either result is visibly labelled as resting on an unsettled reading of
   the law (FR-015).

---

### User Story 3 - Choose the lots you sell (Priority: P2)

The owner holds a position built from several purchases at different prices and
sells part of it. The scenario declares which lot-selection method governs the
disposal — FIFO, LIFO, average-cost, or a specific named lot — and the taxable gain
follows from that choice. The same trade under different methods produces different
tax, and the tool computes each correctly rather than approximating any of them
with another.

**Why this priority**: Required test E6. The method changes the basis consumed and
therefore the tax, plausibly and silently — which is exactly why 001 refused to
fake the missing two. It is P2 only because Stories 1–2 change *whether the model
is honest at all*, while this story widens a choice that already works correctly
for two of its four values.

**Independent Test**: A three-lot position with a partial sale, run once under each
method; each run's tax is checked against its own hand-computed arithmetic, and the
four results are pairwise different by construction of the fixture.

**Acceptance Scenarios**:

1. **Given** a position of three lots acquired on different dates at different unit
   costs, and a partial disposal, **When** the disposal is taxed under each of
   FIFO, LIFO, average-cost and specific-lot in turn, **Then** each method's
   realised gain and tax match that method's own hand-computed arithmetic.
2. **Given** the specific-lot method and a disposal naming a lot, **When** the
   named lot exists and holds enough units, **Then** exactly that lot's basis is
   consumed — the disposal that 001 refused loudly now executes, correctly.
3. **Given** the specific-lot method and a disposal naming a lot that does not
   exist, is already fully consumed, or holds fewer units than the disposal,
   **When** the disposal is processed, **Then** the run reports the mismatch
   naming the lot and the shortfall — it never falls back to another method.
4. **Given** any method other than specific-lot, **When** a disposal names a
   specific lot anyway, **Then** the conflict is reported rather than the naming
   being silently ignored — ignoring it would tax a different basis than the
   owner asked for.
5. **Given** a scenario that declares no lot-selection method, or an unrecognised
   one, **When** it is loaded, **Then** loading fails naming the known methods —
   there is no default method, because a default is a hidden tax position.
6. **Given** the average-cost method, **When** a partial disposal is processed,
   **Then** lot and basis conservation still hold: the position's lots, quantities
   and remaining basis remain fully accounted for after the pro-rata consumption.

---

### User Story 4 - When the cash is not there (Priority: P2)

On a payment due date the tax-currency cash balance is smaller than the liability.
The tool does not let cash go negative, does not skip or shave the payment, and
does not invent a trade on the owner's behalf: it stops with a typed shortfall
report naming the liability, the cash available, and the difference. Deciding
*what to sell* to cover a tax bill — the forced-sale policy — is an owner decision
that has been explicitly deferred to a later feature, and so has the alternative of
paying late under statutory interest.

**Why this priority**: This is the second half of E7 and the practical payoff of
Story 1: a plan that looks fine gross can be infeasible net simply because the tax
bill lands in a month with no cash. A tool that quietly overdraws — or quietly
forgets to pay, or quietly sells something the owner never chose — hides exactly
the constraint the owner needs to see. Principle VI: an infeasible plan reports
the binding constraint instead of results.

**Independent Test**: Construct a scenario whose year-Y liability exceeds the cash
held on the due date. Verify the run stops on that date with the hand-computed
liability, cash and shortfall in the report, and that no date shows negative cash
and no disposal appears that the scenario did not declare.

**Acceptance Scenarios**:

1. **Given** a due date on which cash is short of the liability, **When** the
   payment is processed, **Then** the run stops with a typed shortfall outcome
   naming the liability, the cash available and the shortfall, and the cash
   balance never goes negative on any date.
2. **Given** the same scenario, **When** the ledger is inspected, **Then** no
   engine-generated disposal exists — the tool has not sold anything the owner
   did not declare, because no forced-sale policy is declared in this feature.
3. **Given** the shortfall outcome, **When** results are reported, **Then** the
   projection up to the failure date is still traceable, and the shortfall reason
   surfaces in the output as a typed result — not an empty result, not a clamp.

---

### User Story 5 - The law changes as data (Priority: P3)

The carryforward rules, the due dates, and the set of permitted lot-selection
methods are all legal facts. Each enters the system as declared data with a cited
source, a retrieval date and a verification date — never as a constant in the
engine. When a rule changes, the owner edits a data file; when a rule's provenance
is unverified, every figure resting on it carries the mark.

**Why this priority**: Principle II — the framework claim. It is P3 because, like
001's Story 4, it is verified rather than separately built: if Stories 1–4 keep
legal values in data, this already works, and this story's job is to prove it.

**Independent Test**: Change a declared due date or carryforward term in data only
and verify the payment events and netting move with it, with no source change.

**Acceptance Scenarios**:

1. **Given** a due-date rule declared in data, **When** the declared date is
   changed in the data file only, **Then** payment events move to the new date
   with no source-code change.
2. **Given** any tax figure produced by this feature, **When** it is inspected,
   **Then** it names the rule, the cited source and the verification date behind
   it, and an empty verification date marks the figure and everything derived
   from it.
3. **Given** a carryforward or due-date declaration with a malformed or
   unrecognised field, **When** it is loaded, **Then** loading fails naming the
   file and the field, and no default is substituted.

---

### Edge Cases

- **A loss year followed by another loss year** — carryforwards accumulate per the
  declared rules, each tracked to its origin year, so a later expiry or partial
  absorption is attributable.
- **A gain exactly absorbed by a carried loss** — the assessed liability is zero;
  the annual statement records the zero *citing the netting*, distinguishable from
  an exempt zero and from "no taxable events" (the E11 distinction, preserved at
  the annual level).
- **The unfiled branch followed by another loss year that is filed** — only the
  filed year's loss carries; forfeiture is per loss year, not a permanent state.
- **An exempt-security loss (OVDP) in a year with taxable gains** — buys no tax
  shield: exempt operations are outside the investment-profit calculation on both
  sides (income and costs), so the taxable result is identical with and without
  the exempt loss, and the output must not suggest otherwise.
- **A missed declaration in a year between a filed loss and a later gain** — the
  law does not settle whether the chain survives; the declared chain-continuity
  switch governs, and both branches are labelled unsettled (FR-015).
- **The due date falls on a non-business day** — the applied convention must be
  declared and stated on the payment event, mirroring 001's coupon-date rule
  (FR-021 there); no silent choice.
- **A disposal larger than the whole position** — already an invariant violation in
  the ledger; remains one under every new method.
- **A specific-lot disposal naming several lots** — either supported with per-lot
  quantities or refused explicitly; never partially honoured.
- **Zero-liability years produce no payment event** — and the absence is checkable,
  because the annual statement still exists and says why nothing was due.
- **The exempt OVDP class throughout** — zero charges continue to be recorded per
  event with the exemption cited; no annual payment event ever arises from a year
  of exempt income; D1's golden behaviour is unchanged.
- **A carryforward rule referenced but not declared** — netting refuses with an
  explicit failure naming the missing rule; it must never quietly tax the gross
  (or quietly net) when the rule is absent.

## Requirements *(mandatory)*

### Functional Requirements

**Assessment to a tax year (E7, defect B5)**

- **FR-001**: Every tax charge MUST be assessed to a tax year, and the charges of a
  year MUST accumulate into an annual statement per declared income category. No
  tax may be deducted from a position, from a disposal's proceeds, or from cash at
  the time of the taxable event: gross amounts land in the ledger and the charge is
  recorded beside them.
- **FR-002**: The annual statement MUST enumerate the charges composing it, each
  traceable to its event and its rule, so the year's liability can be verified from
  the ledger without re-deriving it.
- **FR-003**: The timing behaviour of a tax class — self-assessed and paid the
  following year, versus withheld at source by a tax agent — MUST be a declared
  property of the class, entered as data. This feature exercises the self-assessed
  behaviour; declaring the property is in scope so that a withheld-at-source class
  (e.g. bank deposit interest, per `SIMULATOR_SPEC.md` §4.5) is later a data-only
  addition, but no withheld-at-source class is implemented here.

**Payment as a ledger event (E7)**

- **FR-004**: A year's assessed liability MUST be settled by a dated payment event
  that debits the tax-currency cash balance on the declared payment due date in the
  following year. The payment event MUST name the annual statement it settles, and
  MUST participate in cash conservation and traceability like every other event.
- **FR-005**: Declaration and payment due-date rules are legal values. They MUST be
  declared as data with full provenance (`value`, `source`, `retrieved_on`,
  `verified_on`) and MUST NOT appear as constants in the engine. A scenario with a
  taxable event and no declared due-date rule MUST fail explicitly naming the
  missing declaration. The researched starting values — declare by 1 May, pay by
  1 August of the following year (`SIMULATOR_SPEC.md` §4.5, §12) — enter as data
  under those citations, unverified until the owner verifies them.
- **FR-006**: A year whose assessed liability is zero MUST still produce an annual
  statement recording the zero and the rules that produced it (exemption, netting,
  or no taxable events — each distinguishable), and MUST NOT produce a payment
  event.
- **FR-007**: A liability assessed but not yet due when the projection horizon ends
  MUST be reported as an open obligation with its amount and due date, never
  silently dropped from the outcome.
- **FR-008**: The convention applied when a declared due date falls on a
  non-business day MUST be declared in data and stated on the payment event; an
  unrecognised convention MUST fail at load time naming the file and the value.

**Insufficient cash (E7)**

- **FR-009**: If the tax-currency cash balance is smaller than the liability on the
  due date, the system MUST stop with a typed shortfall outcome naming the
  liability, the cash available, and the shortfall. It MUST NOT record a negative
  balance, MUST NOT skip or partially make the payment, and MUST NOT generate any
  disposal the scenario did not declare.
- **FR-010**: **Stated deferral (owner decision, 2026-08-22).** Modelling the
  forced sale that would cover a shortfall — which holdings are sold, in what
  order, sized how, consuming which basis — is deferred to a later feature; no
  forced-sale ordering policy is declared here. The deferral exists so E7's
  forced-sale clause stays visibly open rather than being approximated by an
  ordering nobody chose: an engine-invented trade is a tax position taken on the
  owner's behalf.
- **FR-011**: **Stated deferral (owner decision, 2026-08-22).** Paying late under
  statutory interest as an alternative to selling was offered to the owner and not
  taken; penalties and late-payment interest are not modelled in this feature. The
  option is recorded here so the deferral is a decision on the record, not a gap.
- **FR-012**: The shortfall outcome is a typed result like every other degraded
  outcome: its reason MUST surface in the output, and the projection up to the
  failure date MUST remain fully traceable. It MUST NOT clamp the payment, invent
  credit, or return an empty result.

**Loss offset and carryforward (E2)**

- **FR-013**: Within a tax year, gains and losses MUST net to an annual result per
  income category according to declared netting rules, before any rate is applied.
  The offset scope is **SETTLED** by the primary text
  (`https://zakon.rada.gov.ua/laws/show/2755-17`, accessed 2026-08-22):
  - an investment loss reduces **only** the investment-operations result of
    following years — investment-profit accounting is kept «окремо від інших
    доходів і витрат» (пп. 170.2.1 ПКУ);
  - ІСІ distributions (пп. 167.5.4 ПКУ, 9%) are a separate kind of passive income
    entirely outside the investment-profit calculation — an investment loss never
    reduces them;
  - operations in exempt securities (OVDP, пп. 165.1.52 ПКУ) are **fully outside**
    the calculation: both their income and their costs are excluded (пп. 170.2.8
    останній абзац, пп. 164.2.9 ПКУ). The consequence MUST be modelled and stated
    explicitly: no tax on an OVDP gain, **and no offset from an OVDP loss** — an
    exempt loss buys no tax shield, and the output must not imply one.
- **FR-014**: Whether the loss-year declaration was filed MUST be an explicit
  scenario input with no default. Both branches MUST be supported: filed (the loss
  carries) and not filed (the carryforward is forfeited). A scenario that reaches a
  loss year without declaring its filing behaviour MUST fail explicitly.
- **FR-015**: In the filed branch, the carried loss MUST reduce later years'
  positive results per the declared carryforward rules. The term is **SETTLED**:
  the carryforward is **unlimited in time** and carries across consecutive years
  until fully absorbed — пп. 170.2.6 ПКУ, абзац третій: «Якщо загальний фінансовий
  результат операцій з інвестиційними активами має від'ємне значення, його сума
  переноситься у зменшення загального фінансового результату операцій з
  інвестиційними активами наступних років до його повного погашення»
  (`https://zakon.rada.gov.ua/laws/show/2755-17`, accessed 2026-08-22). Filing an
  annual declaration is a duty for every year with investment operations
  (пп. 170.2.1 ПКУ).

  One remainder is **UNSETTLED**: whether a loss survives a year whose declaration
  was missed. Form Ф1 mechanically pulls the loss only from the immediately
  previous year's declaration, and no ДПС ruling was found on restoring a broken
  chain via уточнююча декларація. Per the owner's decision (2026-08-22), the
  system MUST model this as an explicit scenario switch — **chain-broken-forfeits**
  versus **chain-restorable** — with no default; every figure produced under
  either branch MUST be labelled as resting on an unsettled reading of the law,
  and the real resolution path is an індивідуальна податкова консультація
  (ст. 52 ПКУ), recorded here so the label can one day be lifted by a citation.
- **FR-016**: In the unfiled branch, later gains MUST be taxed in full and the
  output MUST state the forfeited carryforward and its amount, so the cost of the
  omission is a visible figure rather than a silent absence.
- **FR-017**: The military levy MUST be assessed on the **same netted,
  carryforward-reduced base** as the PIT. The statutory chain is **SETTLED**: the
  levy's object is «доходи, визначені статтею 163» (пп. 1.2 п. 16-1 підрозділу 10
  розділу XX ПКУ), and only the positive net investment result enters taxable
  income (пп. 164.2.9 together with пп. 170.2.6 ПКУ;
  `https://zakon.rada.gov.ua/laws/show/2755-17`, accessed 2026-08-22). The
  confirming form mechanics are **INTERPRETED**: ЗІР, категорія 103.24 shows the
  declaration computing both PIT (row 4) and levy (row 5) from the same row 3.1 —
  the positive result after prior-loss deduction. A negative annual result means a
  zero base and **no levy**. PIT and levy remain separately computed, separately
  reported lines per the 001 contract — same base, never one folded rate.
- **FR-018**: Carryforward and netting rules MUST be declared as data with full
  provenance. An assessment that requires a rule that has not been declared MUST
  refuse with an explicit failure naming the missing rule — it must never quietly
  tax the gross amount, and never quietly net.
- **FR-019**: A carryforward still open at the end of the projection horizon MUST
  be reported as an open balance attributed to its origin year.

**Lot selection methods (E6)**

- **FR-020**: Average-cost and specific-lot MUST join FIFO and LIFO as declared
  lot-selection methods. The method MUST remain a declared choice with no default:
  a scenario that declares no method, or an unrecognised one, MUST fail naming the
  known methods.
- **FR-021**: Under the specific-lot method, a disposal MUST name the lot (or lots,
  with per-lot quantities) it consumes, and exactly that basis MUST be consumed. A
  named lot that does not exist, is already consumed, or holds fewer units than
  requested MUST produce an explicit failure naming the lot and the shortfall —
  never a silent fallback to another method.
- **FR-022**: Under any method other than specific-lot, a disposal that names a
  specific lot MUST be reported as a conflict, never silently ignored — the loud
  refusal 001 established remains the behaviour outside the specific-lot method.
- **FR-023**: Under the average-cost method, the basis consumed by a partial
  disposal MUST follow the declared average-cost definition, and lot, quantity and
  basis conservation MUST continue to hold on the remaining position. The
  arithmetic definition used MUST be stated in the worked example so it is
  hand-checkable.
- **FR-024**: Which methods Ukrainian law permits is resolved as follows (owner
  decision 2026-08-22 plus source analysis), and the texture matters:
  - the ПКУ itself prescribes **no method** — **SETTLED by absence** in п. 170.2
    (`https://zakon.rada.gov.ua/laws/show/2755-17`, accessed 2026-08-22);
  - for a self-declaring individual, ДПС/ЗІР guidance recognises costs
    «пропорційно до частки такого реалізованого активу» — effectively
    **average-cost over the packet** of identical securities (пп. 170.2.7 ПКУ
    defines the investment asset as the whole packet) — **INTERPRETED**;
  - where a tax agent computes the tax, Методика МФУ № 1484 (реєстр. z0100-12),
    п. 3.3, prescribes **FIFO** — **SETTLED for the agent case**;
  - the taxpayer's freedom to choose a method, and any within-year consistency
    requirement, are **UNSETTLED** — awaiting an індивідуальна податкова
    консультація (ст. 52 ПКУ).

  Consequently: all four methods (FIFO, LIFO, average-cost, specific-lot) remain
  computable as **what-if figures**, and **none may be labelled "the tax you would
  owe"** until the ІПК answers. The two source-backed candidates — proportional/
  average-cost for a self-declarant, FIFO where an agent computes — MUST carry
  their citations on their results. The honest gap MUST stay visible: for a
  self-declarant (e.g. with a foreign broker) the two source-backed methods give
  **different numbers**, and which one a "most likely" reading uses is an
  UNSETTLED scenario switch, labelled like the others. Every tax figure MUST state
  the method that produced it, so a figure never hides its basis convention.
- **FR-025**: One fixture — a three-lot position with a partial sale — MUST have
  its realised gain and tax hand-computed under each of the four methods, with the
  fixture constructed so the four results are pairwise distinct.

**Regression and provenance**

- **FR-026**: The exempt OVDP behaviour MUST be unchanged: per-event zero charges
  citing the exemption continue to be recorded, no payment event arises from a year
  of exclusively exempt income, and feature 001's golden results are reproduced
  bit-identically.
- **FR-027**: Every legal value this feature introduces — due dates, carryforward
  rules, netting scope, permitted methods — MUST carry full provenance, and a value
  with an empty verification date MUST mark every figure derived from it, including
  annual statements, payment events and forfeiture figures.

### Key Entities

- **Annual tax statement** — one owner, one tax year, one income category: the
  charges assessed, the netting applied, the carryforward consumed or created, the
  resulting liability, and the provenance marks of everything above. The bridge
  between per-event charges (001) and a dated payment.
- **Tax payment event** — a dated ledger event debiting the tax-currency cash
  balance, caused by an annual statement, participating in cash conservation like
  any other event.
- **Timing rule** — a declared, cited legal value: declaration deadline, payment
  deadline, non-business-day convention, and the class's settlement behaviour
  (self-assessed vs withheld at source).
- **Carryforward balance** — a declared loss's unabsorbed remainder, attributed to
  its origin year, carried per the declared rules, reported when open at horizon
  end.
- **Filing decision** — an explicit per-year scenario input: was the declaration
  for this year filed? No default exists.
- **Lot-selection method declaration** — the scenario's declared choice among
  FIFO, LIFO, average-cost and specific-lot; stated on every figure it produced.
- **Shortfall report** — the typed outcome of a due date whose liability exceeds
  the cash available: the liability, the cash, the difference, and the projection
  up to that date. What the tool produces *instead of* a forced sale, which is a
  recorded deferral.
- **Unsettled-law scenario switch** — an explicit scenario input standing in for a
  legal question no source settles (carryforward chain continuity; the
  self-declarant's method between the two source-backed candidates). Each branch
  is labelled as an unsettled assumption on every figure it touches, and each
  switch records the ІПК (ст. 52 ПКУ) as its resolution path. No switch has a
  default.
- **Fixture instrument** — a clearly-labelled synthetic taxable instrument declared
  in test data, whose terms are stated in the tests, used so this feature's worked
  examples depend on nothing unfinished in feature 006.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a fixture with a loss year then a gain year, the filed and
  unfiled branches each match their own hand-computed tax, and the two differ by
  exactly the hand-computed value of the carryforward (E2, both branches).
- **SC-002**: On one three-lot fixture with a partial sale, the four lot-selection
  methods produce four pairwise-distinct tax figures, each matching its own
  hand-computed arithmetic within the single project tolerance (E6).
- **SC-003**: In a scenario with a taxable gain, no tax leaves any position or
  balance at trade time, and exactly one payment event per positive-liability year
  debits cash on the declared due date of the following year (E7).
- **SC-004**: With insufficient cash on a due date, the run stops with a typed
  shortfall outcome carrying the hand-computed liability, cash available and
  shortfall; across generated scenarios, 0% of shortfall runs end with a negative
  balance, a partial payment, or a disposal the scenario did not declare.
- **SC-005**: A year containing an exempt-security (OVDP) loss alongside taxable
  gains produces the same hand-computed taxable result and tax as the identical
  year without the exempt loss — the exempt loss demonstrably buys no shield, and
  the exempt operations appear nowhere in the netting.
- **SC-006**: Cash, lot and basis conservation hold across a large body of
  generated event streams that include annual assessments and payment events,
  under each of the four lot-selection methods.
- **SC-007**: Every misdeclared input in a deliberate battery — missing method,
  unknown method, missing filing decision, missing due-date rule, malformed
  carryforward declaration — fails naming the file, field or declaration at fault;
  none substitutes a default.
- **SC-008**: Every figure this feature emits — annual liabilities, payment
  amounts, forfeitures, per-method gains — resolves to its events, rules and
  declared legal values, and an unverified legal value marks 100% of the figures
  derived from it.
- **SC-009**: Feature 001's exempt OVDP golden results are reproduced
  bit-identically with this feature present, and a year of exclusively exempt
  income produces an annual statement of zero and no payment event.
- **SC-010**: The unfiled branch's output names the forfeited amount such that a
  reader can quote the cost of not filing directly from one figure, without
  re-running the filed branch.
- **SC-011**: In a year whose gain is reduced by a carried loss, the PIT and the
  military levy are both hand-computed from the same reduced base and reported as
  separate lines; in a year with a negative result, both lines are zero with the
  netting cited.
- **SC-012**: Every figure produced under an unsettled-law scenario switch (chain
  continuity; the self-declarant's method) carries the unsettled label, and 0% of
  the four lot-method figures is presented as "the tax you would owe" rather than
  a what-if.

## Assumptions

- **Synthetic fixtures, labelled as such.** Feature 006's Inzhur instruments will
  be the first real taxable instrument; this feature's worked examples run on a
  declared fixture instrument whose terms are stated in the tests and marked
  synthetic. The examples test the engine's arithmetic, not the market, exactly as
  001's did. Nothing in this feature depends on 006 being finished.
- **Single jurisdiction, single currency in practice.** Everything here is
  Ukrainian tax in hryvnia; the tax currency equals the base currency throughout.
  Multi-jurisdiction (E8), residency change (E9) and the F1 FX asymmetry are out of
  scope, and no structure here may preclude them.
- **The tax year is the calendar year.** Consistent with the declare-by-1-May /
  pay-by-1-August cycle in `SIMULATOR_SPEC.md` §4.5; entered with that citation.
- **Payment is modelled on the declared payment deadline.** The researched values —
  declare by 1 May, pay by 1 August of the following year — enter as data under
  the §12 citations, unverified until verified. The tool pays on the declared
  pay-by date; modelling earlier voluntary payment is not in scope.
- **The filing decision is an input, not a prediction.** The tool never assumes
  the owner filed or did not; the scenario says so per year, and E2's two branches
  are two scenarios.
- **Within-year netting happens inside the investment-operations category only.**
  Settled by пп. 170.2.1/170.2.6 ПКУ (see FR-013): the year's investment
  operations net to one annual result, nothing nets across categories, and exempt
  operations stand entirely outside.
- **No penalties or statutory interest for late payment, and no forced sales.**
  Both are stated deferrals per owner decision 2026-08-22 (FR-010, FR-011); the
  modelled response to insufficient cash is the typed shortfall report (FR-009).
- **The levy rate is in reality a dated schedule.** 1.5% → 5% from 01.12.2024
  (Закон № 4015-IX; пп. 1.3 п. 16-1 підрозділу 10 розділу XX ПКУ), with a
  transition — incomes in the 2024 annual declaration still at 1.5% (Закон
  № 4113-IX) — and a statutory reversion to 1.5% three years after martial law
  ends. That is exactly the E10 dated-rate-schedule shape assigned to feature 006;
  this feature takes the currently-declared rate from data and must not preclude
  the schedule. PIT on investment profit is 18% (п. 167.1, пп. 167.5.1 ПКУ; agent
  withholding under пп. 170.2.9); ІСІ distributions 9% (пп. 167.5.4) plus levy.
- **A better OVDP citation exists than the one behind `data/tax/ua.toml`.** The
  exemption from *both* PIT and the levy rests on пп. 165.1.52 ПКУ, with OVDP
  excluded from the levy's exception list by Закон № 466-IX since 23.05.2020 —
  stronger than the PwC summary currently cited. Recorded here for the
  implementation to upgrade the citation; no data file is edited by this spec.
- **One owner, no delivery surface.** As in 001: results are produced and asserted
  by the test suite; presentation of annual statements is a later feature, except
  where a requirement above says a figure must be *reported* — which binds the
  result structure, not a UI.

## Clarifications resolved

All five answered on 2026-08-22 — by the owner, and by a research pass over the
primary ПКУ text (`https://zakon.rada.gov.ua/laws/show/2755-17`, accessed
2026-08-22) and ДПС/ЗІР guidance. One citation correction from that pass: there is
no пп. 170.2.10 — п. 170.2 ends at 170.2.9; the carryforward provision is
**пп. 170.2.6, абзац третій**.

| # | Question | Decision | Where it landed |
|---|---|---|---|
| 1 | Carryforward term and continuity | **SETTLED**: unlimited, carries until fully absorbed (пп. 170.2.6 абз. 3; annual filing a duty per пп. 170.2.1). **UNSETTLED remainder**: survival across a missed-declaration year — modelled as an explicit scenario switch (chain-broken-forfeits vs chain-restorable), both branches labelled, ІПК (ст. 52 ПКУ) the resolution path | FR-015; US2 scenario 6 |
| 2 | Offset scope | **SETTLED**: only the investment-operations result of following years (пп. 170.2.1 «окремо»); ІСІ dividends (пп. 167.5.4) outside; exempt OVDP operations fully outside on both sides (пп. 165.1.52, 170.2.8 ост. абз., 164.2.9) — an OVDP loss buys no tax shield | FR-013; SC-005 |
| 3 | Levy base under netting | **Resolved**: same netted, carryforward-reduced base as PIT. Statutory chain SETTLED (пп. 1.2 п. 16-1 підрозд. 10 розд. XX; пп. 164.2.9 + 170.2.6); form-mechanics confirmation INTERPRETED (ЗІР 103.24 — PIT row 4 and levy row 5 both from row 3.1). Negative result → zero base, no levy | FR-017; SC-011 |
| 4 | Legally permitted basis methods | Owner: what-if until professional advice. ПКУ prescribes no method (SETTLED by absence); ЗІР's proportional recognition ≈ average-cost over the пп. 170.2.7 packet for a self-declarant (INTERPRETED); Методика МФУ № 1484 (z0100-12) п. 3.3 FIFO for tax agents (SETTLED for the agent case); taxpayer choice and within-year consistency UNSETTLED. All four stay computable what-ifs, none labelled "the tax you would owe"; the self-declarant gap between the two source-backed methods is an unsettled scenario switch | FR-024; SC-012 |
| 5 | Forced-sale ordering and sizing | **Deferred** by the owner: on insufficient cash, the typed shortfall report and stop; no forced-sale policy declared in this feature, and the pay-late-under-statutory-interest alternative was offered and not taken — both recorded as stated deferrals | FR-009–FR-012; US4 |

The UNSETTLED remainders inside decisions 1 and 4 are not open markers: each is an
explicit, defaultless scenario switch whose branches are labelled on every figure
they touch (see Key Entities), and each records the ІПК as the citation that will
one day retire it.

## Required tests this feature closes

Rows in `docs/REQUIRED_TESTS.md` that must be flipped, with their test paths
recorded, before this feature is done:

| Row | What it asserts |
|---|---|
| **E2** | A loss year followed by a gain year nets correctly; omitting the loss-year declaration forfeits the carryforward — both branches tested |
| **E6** | FIFO / LIFO / average / specific on a three-lot position with a partial sale each produce their own hand-computed tax |
| **E7** | Tax paid from cash in the following tax year; insufficient cash forces a sale, which is itself taxed — **partially**: see below |

**E7 flips only in part.** Its first clause — assessed to the year, paid from cash
on the declared due date of the following year — closes here. Its forced-sale
clause is an owner-recorded deferral (FR-010): this feature lands the typed
shortfall report instead, so the E7 row is annotated rather than fully flipped,
and the deferral belongs in `specs/features.toml` as a `[[future]]` entry when
this spec lands, so the open half stays visible in the graph.

The ledger invariant rows C1–C3 already flipped by 001 must *remain* green with the
new event kinds present — annual assessments and payment events extend the
generated event streams those invariants run over, and weakening an invariant
suite to admit them would require a constitution amendment.

## Out of scope

Named explicitly so the plan does not drift into them: multiple jurisdictions and
the jurisdiction-comparison test (E8); residency change by date (E9); the crypto
tax scenarios (E4); foreign withholding credits (E3); the F1 FX asymmetry (a
taxable foreign instrument plus dated official rates — a recorded `[[future]]`
entry); any change to the exempt OVDP behaviour; implementing withheld-at-source
settlement on a real class (the property is declared, per FR-003, but bank-deposit
withholding lands with the feature that models deposits); forced sales to cover a
tax shortfall, and penalties or statutory interest for late payment (both stated
deferrals per owner decision 2026-08-22 — FR-010, FR-011); rates as dated
schedules (E10, assigned to feature 006's scope — see the levy-schedule
cross-reference in Assumptions); and any presentation surface for annual
statements beyond the result structure.
