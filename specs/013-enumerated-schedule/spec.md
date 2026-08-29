# Feature Specification: An instrument declared as the payments it will make

**Feature Directory**: `specs/013-enumerated-schedule`

**Feature Branch**: `spec/013-enumerated-schedule`

**Created**: 2026-08-24

**Status**: Ready for planning — no clarifications open (see *The premium, and why it is not a clarification*)

**Input**: Allow an instrument to be declared by an **enumerated schedule** of dated,
typed payments, alongside the generative bond declaration feature 001 introduced. The
motivating data is `data/observations/inzhur.toml`, retrieved 2026-08-24 from
<https://www.inzhur.reit/_api/assets> by `scripts/fetch_inzhur.py`: 32 ОВДП issues, each
published as a list of dated payment amounts, with no coupon rate and no issue date.

---

## Why this feature exists

An instrument declaration describes a bond **generatively**. `data/instruments/ovdp_synthetic_a.toml`
states a face value, a coupon rate, an issue date, a maturity date, a periodicity, a day
count and a business-day rule, and `core.instruments.fixed_income` derives every payment
from them. That form says one thing about the world: *these are the issue's terms, and I
know them.*

Real secondary-market data says the opposite thing. The endpoint publishes, per issue, an
**enumerated list of dated amounts** — and neither of the two anchors the generative form
needs to place a schedule in time.

### The measurement

Read off the 32 bond observations in `data/observations/inzhur.toml` (retrieved
2026-08-24; the analysis is arithmetic over that file and is reproducible from it):

| A generative declaration needs | The endpoint gives |
|---|---|
| `face_value` | **inferable**: 32 of 32 issues publish a payment of exactly `100000`, the largest in every schedule, against buy prices near 1 000 — i.e. kopecks against a 1 000.00 UAH nominal |
| `maturity_date` | given as `matures_on` — and it differs from the last published payment date in **18 of 32** issues, by one day |
| `coupon_rate_pct` | derivable from one coupon amount and the interval between two coupons |
| `periodicity` | derivable only from two or more coupon dates, and two different measures both fall short. **3 of 32** *publish* only one coupon (`UA4000233696`, `UA4000232599`, `UA4000230809` — all matured); a **disjoint 5 of 32** have only one coupon *remaining* after the retrieval date (`UA4000234413`, `UA4000237416`, `UA4000236624`, `UA4000238281`, `UA4000235865`). Eight issues in all, and no issue is in both sets |
| **`issue_date`** | **not given, and not derivable** |
| `day_count`, `business_day_rule` | not given |

Extrapolating an issue date backwards from the remaining coupons would be inventing a
legal fact about a state security. Constitution Principle I forbids it outright, and it is
the kind of invention that is invisible once made: a plausible date produces a plausible
schedule and nothing ever contradicts it.

A second measurement decides the shape of the fix. **The endpoint's published window is
not uniform.** Across the 24 issues with `status = "active"`, the earliest published
payment ranges from 341 days *before* the retrieval date (`UA4000235865`) to 170 days
*after* it (`UA4000239107`); 19 of the 24 publish at least one payment that has already
happened, and 5 publish none. So "these are the remaining payments" is not something the
data says. It is something a reader would assume, and the assumption is wrong for at least
19 issues in one direction and unverifiable in the other.

### The argument this feature rests on

**These are not two ways to declare one thing.** They are two different epistemic
situations, and collapsing them is the change this specification exists to prevent.

- A **generative** declaration says: *I know this instrument's full terms.* Its figures
  are derived from the contract, and the derivation is checkable on paper.
- An **enumerated** declaration says: *I am buying a stream of dated payments on the
  secondary market. The issue's history is neither known to me nor relevant to what I will
  receive.*

The issue date affects **no future cash flow of a purchase made today**. A form that
demands a fact which changes no figure is a form that forces invention — and the invention
lands inside the one number the whole project exists to produce honestly.

The two forms are therefore kept apart deliberately, and the cost of that is real: a second
declaration shape, a second `events` implementation, and a set of figures that one form can
produce and the other must refuse. What is bought with it is that **no figure in this
system rests on a date nobody published**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A bond declared as the payments it will make (Priority: P1)

The owner declares an instrument as a list of dated, per-unit amounts — each one saying
what kind of payment it is — plus a face value, the currency, the date from which the list
is complete, the purchase constraints and a tax class per income kind. He states no coupon
rate, no issue date, no periodicity, no day count and no business-day rule, because he does
not know them and the platform does not publish them. The projection runs, produces the
cash-flow schedule and the after-tax figures, and never asks for a term he did not state.

**Why this priority**: it is the feature. Without it the 32 real issues cannot be declared
at all, and the only way to declare them would be to invent an issue date for each.

**Independent Test**: declare a synthetic enumerated instrument with a schedule small
enough to check on paper, project a purchase of it, and verify the schedule and the total
against arithmetic worked out by hand.

**Acceptance Scenarios**:

1. **Given** an enumerated declaration with four per-unit payments and a purchase of a
   stated number of units at a stated cost, **When** the projection runs, **Then** the
   cash-flow schedule holds exactly those payments, on those dates, scaled by the units
   held, and the totals match hand-computed arithmetic within the single project tolerance.
2. **Given** the same declaration, **When** it is loaded, **Then** no issue date, coupon
   rate, periodicity, day count, business-day rule or maturity date is required, present,
   or substituted by a default.
3. **Given** a declaration that carries a generative term **and** an enumerated schedule,
   or neither, **When** it is loaded, **Then** loading fails naming the file and the field.
4. **Given** two payments on the same date of different kinds — the ordinary way a bond
   ends, and the shape of the observed schedules — **When** the declaration is loaded and
   projected, **Then** both survive as separate payments; they are never merged,
   deduplicated, or summed into one row.
5. **Given** a source that published its payments in an order other than ascending by date
   — the shape of the one observed issue in the Edge Cases below — **When** it is
   transcribed, **Then** the payments are put in date order by the transcriber and the
   declaration records that the source published them in a different order (FR-020a). The
   loader neither sorts nor accepts an unordered list (FR-006).

---

### User Story 2 - Every payment says what it is (Priority: P1)

`8305, 8305, 8305, 100000` is obviously three coupons and a principal repayment to a human
reading it, and obviously nothing at all to a machine. Tax treatment differs between a
coupon and a return of principal, and the endpoint does not label them. So the owner labels
each payment himself, in the declaration, and the engine takes the label as a declared fact
rather than reading the shape of the numbers.

**Why this priority**: it is the difference between a schedule and a taxable schedule, and
the trap is that getting it wrong is currently free. For ОВДП both kinds happen to be
exempt, so a mislabelled payment changes no figure **today**. That is luck rather than
design, and it is exactly the condition under which a defect ships: the first taxable
enumerated instrument makes every earlier mislabelling visible at once.

**Independent Test**: label the same schedule correctly and incorrectly under a synthetic
instrument whose two income kinds are taxed at **different** declared rates, and confirm
the two runs produce different, separately hand-checkable, tax totals.

**Acceptance Scenarios**:

1. **Given** a payment with no declared kind, **When** the declaration is loaded,
   **Then** loading fails naming the file and the payment; no kind is inferred from the
   amount, from the position in the list, or from the date.
2. **Given** a schedule whose payments are labelled coupon and principal repayment,
   **When** the projection runs, **Then** each payment is taxed under the class the
   declaration maps that income kind to, and each tax figure names its class, that class's
   cited source and its verification date.
3. **Given** a synthetic instrument whose coupon class and disposal class carry different
   rates, **When** one payment's label is changed and nothing else is, **Then** the tax
   total changes by exactly the hand-computed difference — proving the label is load-bearing
   rather than decorative.
4. **Given** a declaration whose schedule contains an income kind for which it declares no
   tax class, **When** it is loaded, **Then** loading fails naming the file, the kind and
   the payment.

---

### User Story 3 - Nothing downstream knows which form was used (Priority: P1)

Two declarations describe the same cash flows: one generative, one enumerated. The owner
runs the full tuple on each — the same funding route in, the same tax classes, the same
exit route out, the same horizon — and gets the same figures. Nothing in the ledger, the
tax engine, the tuple join or the ranking knows or cares which form produced the events.

**Why this priority**: it is the property that makes the second form affordable. If the
join, the tax engine or the ranking has to branch on the declaration form, then the two
forms are not two encodings of one thing — they are two different concepts sharing one
interface, and the right response is to stop rather than to add the branch.

**Independent Test**: run one tuple on each form and compare every figure.

**Acceptance Scenarios**:

1. **Given** a generative declaration and an enumerated declaration whose payments are that
   generative declaration's own computed schedule, and identical holdings, routes, tax
   classes and horizons, **When** both tuples are evaluated, **Then** every numeric figure
   agrees within the single project tolerance and the two candidates take the same position
   in the ranking.
2. **Given** the same pair, **When** the two results are compared field by field,
   **Then** the only differences are identity, provenance, the stated exclusions, and the
   schedule's statement of which conventions it applied.
3. **Given** the shipped source tree, **When** the modules under the ledger, the tax engine,
   the decision layer and the tuple, ramp and composed-path results are scanned,
   **Then** none of them names the enumerated form or branches on the declaration form.

---

### User Story 4 - What the form cannot answer, said out loud (Priority: P2)

The owner asks an enumerated instrument for something it cannot know — to project a
purchase dated before its schedule begins, or to reinvest its coupons. He gets a typed
refusal that names the missing fact and what would supply it, not a number computed around
the gap and not a silent zero.

**Why this priority**: a figure silently computed on a missing issue date is the defect this
feature exists to prevent, and a refusal that is not typed is a refusal that gets caught in
review rather than by a test.

**Independent Test**: request each refusable figure and assert on the typed value and its
reason, not on an exception message.

**Acceptance Scenarios**:

1. **Given** an enumerated declaration whose schedule is complete from a stated date,
   **When** a purchase or a declared opening lot is dated before that date, **Then** the
   outcome is a typed refusal naming both dates; the purchase is not re-dated, and no
   projection runs on a schedule that cannot say what that buyer receives.
2. **Given** an enumerated declaration, **When** the coupon policy is reinvestment,
   **Then** the outcome is a typed refusal naming the missing price. The face value is not
   substituted: for a generative bond, face is the price at which a unit earns the issue's
   declared rate, and an enumerated instrument declares no rate, so face is a redemption
   amount and nothing else.
3. **Given** the same declaration under the hold-as-cash policy, **When** the projection
   runs, **Then** it succeeds — the refusal is scoped to the policy that needs a price.
4. **Given** an enumerated projection's cash-flow schedule, **When** a row is read,
   **Then** it states that no periodicity, day count or business-day rule was applied, and
   why. It never names one.
5. **Given** an enumerated projection, **When** the contractual yield is requested,
   **Then** it is produced rather than refused: it is the internal rate of return over the
   purchase cost and the enumerated payments, and needs no generative term.

---

### User Story 5 - What is inferred is written down as an inference (Priority: P2)

The face value of 1 000.00 rests on 32 of 32 schedules publishing a payment of exactly
`100000`, the largest in each. The
principal/coupon split rests on a human reading the last amount. The kopeck scaling rests
on comparing that amount with the buy price. The coverage claim rests on nothing the
endpoint says at all. Each of these is written into the data file as an inference, saying
what it rests on and what would settle it — and none of them is derived in code.

**Why this priority**: an inference derived in code is an inference nobody can see. Written
into the file it is one line a reader and a reviewer both hit; computed in a loader it is a
division by 100 that looks like plumbing.

**Independent Test**: grep the core for the derivations and find none; load a declaration
missing an inference's citation and watch the provenance gate fail.

**Acceptance Scenarios**:

1. **Given** an enumerated declaration, **When** it is loaded, **Then** every inferred
   value carries a source stating that it is an inference, the observation it rests on, and
   an empty verification date, with a matching verification task naming what would settle
   it — and every figure derived from it carries the unverified mark.
2. **Given** the provenance gate, **When** it runs over an enumerated declaration whose
   inferred value lacks the inference statement or the verification task, **Then** it fails
   naming the file and the field.
3. **Given** the source tree, **When** it is scanned, **Then** no module reads the last
   payment as a principal repayment, divides a declared amount by 100, computes a coupon
   rate from an amount and an interval, or infers a coverage window.

---

### Edge Cases

- **A payment dated before the declared coverage start** — a load failure. The declaration
  claims completeness from that date; a payment before it contradicts the claim.
- **Two payments on one date with different kinds** — valid, and required: **31 of the 32**
  observed issues end with the final coupon and the principal repayment on the same date, as
  two entries. ⚙ The 32nd, `UA4000235865`, is the counterexample worth naming: it publishes
  the principal one day *before* the final coupon, which also makes its list the only one not
  in ascending date order — so the single real exception to the pattern is the single issue
  this form would refuse as published. An earlier draft of this spec measured it as 32 of 32,
  and the wrong measurement is exactly what hid it.
- **A schedule with no principal repayment** — a load failure. A stream of coupons that
  never returns anything is not something the observed data contains and not something a
  reader would mean.
- **Several principal repayments** — valid. An amortising schedule is representable, and
  forbidding it would be a constraint invented from a sample where every issue happens to
  repay once.
- **An unordered payment list, a non-positive amount, an unrecognised payment kind, an
  empty schedule** — load failures naming the file and the entry.
- **A declared maturity date** — a load failure, because the enumerated form does not carry
  one. It is given by the endpoint and disagrees with the last published payment date in 18
  of 32 issues; accepting it would import that disagreement in exchange for a field nothing
  reads.
- **A horizon ending before the last enumerated payment** — reported as inconsistent, as it
  is for a generative bond: a truncated schedule's yield is silently wrong, and an implicit
  liquidation at the horizon would be a fabricated cash flow.
- **A purchase cost above the face value** — accepted and recorded in full as the lot's
  basis. It is the ordinary case: 31 of the 32 observed issues quote a buy price above
  1 000.00, the exception being `UA4000207518` at 989.47. What happens to that premium at
  redemption is decided by the declared tax category, not by this feature — see FR-025.
- **Two instruments declaring the same identifier**, in either form — a load-time collision,
  as in feature 001.

## Requirements *(mandatory)*

### Functional Requirements

**The enumerated declaration form**

- **FR-001**: The system MUST accept an instrument declared as an enumerated schedule: an
  identity, a currency, a face value, a coverage start date, an ordered list of per-unit
  dated payments each carrying its kind and its provenance, purchase constraints, and a tax
  class per income kind. Adding such an instrument MUST require no source-code change.
- **FR-002**: A declaration MUST be in exactly one form. Exactly one declared field MUST
  determine which, and a declaration carrying fields of both forms, or of neither, MUST
  fail at load naming the file and the field. The two forms MUST be represented so that
  code reading a generative-only term cannot type-check against an enumerated declaration
  without handling its absence — the type checker, not a reviewer, is what enumerates the
  sites that must change.
- **FR-003**: An enumerated declaration MUST NOT carry an issue date, a coupon rate, a
  periodicity, a business-day rule, or a maturity date. These are forbidden rather than
  optional: an accepted-and-ignored field is worse than a missing one, and each of these
  would be either invented or unread.
- **FR-003a**: An enumerated declaration MUST carry a **day count**, and it is not an
  exception to FR-003. The distinction is what a reader has to be able to make: the
  forbidden five are terms of the **issue** — they describe the paper, and the enumerated
  form does not know them. A day count is a convention of **computation** — it describes
  how *we* turn a span of days into a fraction of a year in order to annualise. Nothing
  about the issue is claimed by declaring one. ⚙ It is required rather than optional
  because the contractual yield cannot be computed without it (FR-018), and a hard-coded
  365 is forbidden at the site that would need it: *"a separate hard-coded 365 here would
  make the yield disagree with the schedule it was computed from"*
  (`core/results/hurdle.py`, `net_present_value`).
- **FR-003b**: The declared day count MUST be an input to **no figure describing the
  instrument's own terms** — not an amount, and **not a rate**. It may annualise spans for
  figures about the *holding's return* (FR-018's contractual yield is the one that exists);
  it MUST NOT size a payment, place a date, generate a schedule, reconstruct an accrual
  period, or produce a coupon rate. ⚙ The boundary is *return figures versus issue terms*,
  not *rates versus amounts*, and the difference is the whole door: day count plus one
  coupon amount plus the interval between two coupons yields a **coupon rate**, and a coupon
  rate plus the spacing yields an extrapolated **issue date** — the invented legal fact this
  entire feature exists to refuse, reached in two steps from a field FR-003a requires. An
  earlier draft wrote this line as "no derivation of any amount" and added that the day count
  "annualises spans for rate figures and does nothing else", which permitted the first step
  in its own sentence.
- **FR-003c**: FR-003b MUST NOT be relied on alone. The same door is also held shut by
  FR-021's prohibition on computing a coupon rate from an amount and an interval, and by
  SC-014's scan for exactly that computation; the requirement and the scan are stated
  together because a guard that believes itself sufficient is the one nobody adds a second
  lock to. ⚙ This is recorded rather than merged into FR-003b because the failure it
  describes already happened once here: FR-003b's first draft claimed to close the door and
  drew its line one category short of it.
- **FR-004**: Payment amounts MUST be per unit and in the instrument's declared currency,
  in that currency's major units. The engine MUST perform no unit scaling of a declared
  amount; a published figure in minor units is converted when it is transcribed into the
  declaration, and the conversion is recorded as an inference (FR-020).
- **FR-005**: A schedule's coverage claim MUST be one-ended — *every payment this
  instrument makes on or after this date, to the end of its life*. A two-ended window MUST
  NOT be representable, so that a schedule truncated at the far end is an unrepresentable
  state rather than a silently short projection.
- **FR-006**: Loading an enumerated declaration MUST fail loudly, naming the file and the
  entry, on: an empty schedule, an unordered payment list, a payment dated before the
  coverage start, a non-positive amount, a missing or unrecognised payment kind, a schedule
  with no principal repayment, a declared maturity date, or a duplicate instrument
  identifier. No default MUST ever be substituted, and no payment MUST be merged,
  deduplicated or reordered on the way in.

**Each payment's tax character**

- **FR-007**: Every payment MUST declare its kind, drawn from a closed set. A payment kind
  MUST determine both what the ledger records as having moved and which income kind the tax
  layer assesses, since those are already two distinct vocabularies in this engine. The
  closed set MUST cover, at minimum, a coupon and a principal repayment.
- **FR-008**: The engine MUST NOT infer a payment's kind. Specifically it MUST NOT read the
  last payment as a principal repayment, MUST NOT read the largest payment as one, and MUST
  NOT derive a kind from the amount, the date or the position in the list.
- **FR-009**: A declaration MUST declare a tax class for every income kind its schedule
  produces; a kind with no declared class MUST fail at load naming the file, the kind and
  the payment.
- **FR-010**: Because both ОВДП income kinds are exempt, a mislabelled payment changes no
  figure on the instruments that motivate this feature. The tests for FR-007 to FR-009
  MUST therefore run on a synthetic instrument whose two income kinds carry **different**
  declared rates, so that the label is proved load-bearing by a figure that moves. That
  instrument's **disposal class MUST be declared in a netting category**, which FR-026 also
  requires — different rates alone do not put it in one, and two per-event classes would
  satisfy the letter of this requirement while leaving FR-026 unreachable.

**One thing downstream, whichever form produced it**

- **FR-011**: Both declaration forms MUST produce the same thing: a stream of dated,
  typed, per-unit-scaled ledger events carrying provenance, gross of tax and free of route
  costs. From that point on **no layer MUST branch on the declaration form**. That is the
  guarantee, and it is deliberately weaker than "the layers are unchanged", which is false:
  **three** modules outside the instrument layer read a generative field directly today, and
  all three MUST change.
- **FR-011a**: All three MUST **ask the declaration** rather than read a field.
  `core/ledger/seeds.py` reads an issue date to refuse an opening lot acquired too early;
  `core/decision/tuple_outcome.py` reads a day count to annualise;
  **`core/results/project.py` reads a day count to build the year fractions the contractual
  yield is computed on, and reads all three conventions to construct `ConventionsApplied`.**
  ⚙ The observation that makes this delegation rather than branching, and the reason the
  change is small: **`seeds.py` never needed an issue date.** It needed *the earliest date
  from which this instrument's terms are known*, and it asked for the only spelling that
  existed. Both forms answer that question — the generative one with its issue date, the
  enumerated one with its coverage start (FR-014) — so the site keeps one question and gains
  an answer, rather than gaining a case.
- **FR-011b**: `core/results/project.py` is the site that MUST be got right, and it MUST NOT
  be reached by testing the declaration's form. It is the **sole** construction site of the
  conventions record, so FR-016 guarantees it changes, and it is where the declared day
  count becomes year fractions, so FR-018 guarantees it too. Because the statement it builds
  genuinely differs between the forms, the natural implementation is a form test — which is
  exactly what FR-012 forbids. The declaration MUST therefore answer *"what conventions
  shaped this schedule, and what should a row say about them"* as one question, with each
  form giving its own answer, so that the module asks rather than decides. ⚙ Named as its
  own requirement because an earlier draft of FR-011 counted two sites and omitted this one:
  the omitted site was the only one that had to make a form-dependent decision, so the
  delegation requirement did not reach the place it exists for.
- **FR-012**: No module in the ledger, the tax engine, the decision layer, or the results —
  **`core/results/project.py` included**, together with the tuple, ramp and composed-path
  results — MUST name the enumerated form. Asking a declaration a
  question both forms answer (FR-011a) does not name it and MUST remain permitted; naming
  it, or testing which form a declaration is in order to decide what to compute, MUST NOT.
  This MUST be asserted by a scan, not by review — and the delegation of FR-011a is what
  keeps the scan passing, which is the practical payoff of choosing it over a case. If the
  property cannot be met, the correct response is to stop and report it: a form that the tax
  engine or the ranking must know about is a second instrument concept wearing one
  interface, which is the situation the four-interface limit of constitution Principle II
  protects against.
- **FR-013**: The enumerated form MUST be a further entry in the existing instrument
  registry under the existing `Instrument` interface: the same function signature, the same
  return type, and the **existing** instrument failure union unchanged. ⚙ Both new refusals
  are `InconsistentTerms` — two declared facts that cannot both hold — which is exactly what
  `core/instruments/fixed_income.py` and `core/ledger/seeds.py` already return for the
  generative mirror of each. Nothing is widened, and the distinction is load-bearing rather
  than pedantic: "different failures" is mismatch 2 of the three that kept a fund out of this
  registry, so a widened union is the sentence that would put a constitution amendment back
  on the table. It MUST NOT
  introduce a fifth plugin interface, and this feature MUST NOT require a constitution
  amendment. ⚙ The three mismatches that kept a fund out of that registry — different
  inputs, different failures, a different arity of answer (recorded at
  `core/instruments/registry.py`) — are each tested here and none holds: the inputs are
  identical, the new failures are members of the existing union, and the answer is one
  event stream.

**What an enumerated instrument must refuse**

- **FR-014**: A purchase, or a declared opening lot, dated before the schedule's coverage
  start MUST produce a typed refusal naming both dates. The date MUST NOT be moved, and no
  projection MUST run on a schedule that cannot state what that buyer receives.
- **FR-015**: A reinvestment coupon policy applied to an enumerated instrument MUST produce
  a typed refusal naming the missing fact — the price at which a coupon buys further units.
  The face value MUST NOT be substituted for it. The hold-as-cash policy MUST be unaffected.
- **FR-016**: A cash-flow schedule row for an enumerated instrument MUST state that no
  periodicity generated its date, no business-day rule moved it, and no day count sized its
  amount — the amount is declared — while naming the day count FR-003a declares, whose only
  effect is to annualise. It MUST NOT name a periodicity or a business-day rule, and the
  canonical encoding used by golden files MUST distinguish this statement from a generative
  row's three named conventions. ⚙ The two halves are separated deliberately: a row that
  said "no day count was applied" would be false the moment a yield is emitted from the same
  projection, and a row that named all three would claim two conventions that never ran.
  ⚙ **Three docstrings go false when this lands and MUST be corrected in the same change**,
  because each states as fact the thing an enumerated row must deny:
  `core/results/schedule.py`'s `ConventionsApplied.day_count` — *"therefore fixed each
  coupon's size"*; `core/results/canonical.py`'s `of_conventions` — *"The three declared
  conventions a schedule applied"*; and `core/decision/tuple_outcome.py`'s `_day_count_of` —
  *"The convention the instrument's own flows were **sized** with"*. Named here rather than
  left to the implementer for the reason FR-023 names its own: a claim about behaviour that
  the code stops honouring is the defect class this repository keeps catching by expensive
  review, and prose that no test reads goes stale silently.
- **FR-017**: No accrued-interest figure, clean price, or any separation of a purchase price
  into a clean part and an accrued part MUST be emitted for an enumerated instrument. Two
  facts are missing and neither may be inferred: the start of the accrual period containing
  the purchase, and the basis on which interest accrues within it. ⚙ No such figure exists
  in the engine today, so this requirement adds a prohibition rather than a refusal; the
  refusal arrives with the figure, if it ever does.
- **FR-018**: The contractual yield MUST NOT refuse for an enumerated instrument. It is the
  internal rate of return over the purchase cost and the enumerated payments, and it needs
  **no issue date** — which is the whole of what the generative form supplies here that the
  enumerated form cannot. It does need a day count to turn each payment date into
  years-from-purchase, and FR-003a supplies one. Stated as a requirement because the obvious
  reading of FR-017 is that every price-derived figure goes, and a refusal that looks like
  caution but is really a missing figure is the worse defect: nobody audits what a careful
  system declines to say.
- **FR-019**: Every refusal named above MUST be a typed value carrying its reason, and the
  reason MUST surface in the output.

**What is inferred is declared, not derived**

- **FR-020**: The face value, each payment's kind, any minor-unit conversion, and the
  coverage claim are inferences rather than statements by an issuer. Each MUST be declared
  in the data file with a source that says it is an inference and what observation it rests
  on, an empty verification date, and a matching verification task saying what would settle
  it. No new kind of mark is introduced: an inference is an unverified value, and Principle
  I's existing propagation carries it.
- **FR-020a**: Where the source published its payments in an order other than ascending by
  date, the declaration MUST **record that it did**, naming the order the source gave.
  Ordering is settled at transcription — the same declared human step that turns kopecks
  into hryvnia — and the loader neither sorts nor accepts an unordered list (FR-006). ⚙ This
  is an observation about the **source**, not about the money, and it is the one that
  silently disappears: that an issuer publishes the principal repayment before the final
  coupon is a fact about how the endpoint reports, and sorting the list is precisely the act
  that would delete it — see the Edge Cases for the observed instance. It is recorded beside
  the inferences rather than among them because nothing is being inferred: a difference is
  being kept.
- **FR-021**: The engine MUST NOT derive any of them. Named explicitly because each is a
  one-line temptation in a loader: no code reads the last payment as principal, divides a
  declared amount by 100, computes a coupon rate from an amount and an interval, or infers
  a coverage window from where a published list happens to begin.
- **FR-022**: The provenance gate (`scripts/check_provenance.py`) MUST assert, for every
  enumerated declaration, that each inferred value's source carries the inference statement
  and that a verification task exists for it. A claim that can go stale silently is worth
  less than a check that cannot.
- **FR-023**: The exclusions a figure states MUST be able to differ by declaration. ⚙ While
  changing that constant, fix the docstring above it: `core/results/hurdle.py` says *"Three
  items"* over a frozenset of **four**. Pre-existing and not this feature's defect, recorded
  here because this is the requirement that sends someone to that line — a count that
  disagrees with its own list is the exact staleness shape `CLAUDE.md` names. An
  enumerated instrument's yield figure MUST state the additional exclusion that its purchase
  price is a dirty price which has not been separated into a clean price and accrued
  interest. ⚙ Today those exclusions are a module-level constant, so this is a real change
  and not a formality.

**The purchase price**

- **FR-024**: The purchase cost MUST be recorded in full as the lot's cost basis, exactly as
  stated. Nothing is amortised, nothing is imputed, and no part of it is reclassified as
  accrued interest — which is the only honest treatment while the two facts FR-017 names
  are missing.
- **FR-025**: Where the purchase cost differs from **the principal this holding will
  receive** times quantity, the difference MUST be reported as its own named figure on the
  projection, so that a premium or discount is visible rather than surfacing only as a
  realised gain or loss at redemption. Its
  treatment MUST be the declared tax category's and nothing else: this feature MUST NOT
  introduce a premium rule, an amortisation, or a branch of its own.
  ⚙ **Amended 2026-08-30, on the owner's decision, from "face value times quantity".** The
  original wording is right for a bond that repays its whole face once and wrong for the
  Edge Case two entries above — *Several principal repayments — valid* — which this same
  specification requires. For a schedule that has already repaid part of its principal
  before the purchase, a unit is a unit of what **remains**: a buyer paying the remaining
  principal exactly has broken even, and measuring them against the nominal face reports a
  discount of everything repaid before they arrived — a figure describing somebody else's
  trade, years earlier, carried into the canonical digest and named with the tax treatment
  that governs it. The amendment also makes this figure agree with the ledger it sits beside:
  **the share of what this holding receives** is already the rule by which a repayment
  retires units, and paid-versus-received measuring "received" differently from the fold
  would be one rule contradicting itself in two places. Where the schedule repays its face
  once — every declaration this repository ships — the two readings give the same number,
  which is why the defect was latent and would have shipped. ⚙ For the **shipped**
  ОВДП declarations that motivate this feature, that treatment is already declared and cited
  — `exempt_securities` is `treatment = "outside"`, `carryforward = "none"`, on пп. 170.2.8
  «б» and its last paragraph, which excludes **both** income and acquisition costs from the
  загальний фінансовий результат. There the premium reduces no other base, and an exempt loss
  buys no shield.
- **FR-026**: The figure MUST state which category treatment governed it, and the netting
  case MUST be **exercised rather than warned about**. The shipped registry also declares
  `investment_profit` — `treatment = "nets"`, `carryforward = "unlimited"` — and the
  synthetic fixture FR-010 already mandates, whose two income kinds carry different declared
  rates, is the instrument that reaches it. So an enumerated purchase at a premium under a
  netting category MUST be projected and asserted: the premium reduces that category's
  netted base by exactly the hand-computed amount, and carries forward when the year is
  negative. ⚙ The fixture MUST therefore put a **same-category gain in the same tax year**
  alongside the redemption. Without one the year's base is simply negative, "reduces the
  netted base by exactly the premium" has nothing to reduce, and the whole assertion
  collapses into the carryforward half — which would test one of the two behaviours while
  reading as though it tested both. ⚙ An earlier draft called this hypothetical and put it out of scope. It is not:
  FR-010's fixture makes it reachable in the same feature, which is strictly better than a
  condition nobody can run — a warning that cannot be exercised is prose, and prose is what
  goes stale. What stays out of scope is declaring a **real** taxable enumerated instrument;
  one declared later brings its own cited category with it.

### Key Entities

- **Enumerated schedule declaration** — one investable thing declared as the payments it
  will make: identity, currency, face value, coverage start, an ordered list of payments,
  purchase constraints, a day count, a tax class per income kind, and the inferences it rests
  on. Carries no issue date, coupon rate, periodicity, business-day rule or maturity date —
  the day count is a convention of computation, not a term of the issue (FR-003a).
- **Scheduled payment** — one dated, per-unit amount with a declared kind and its own
  provenance. Two on one date with different kinds is the normal end of a bond.
- **Payment kind** — a member of a closed set that determines both the ledger movement
  recorded and the income kind assessed. Never inferred.
- **Coverage claim** — the declared date from which the schedule is complete to the end of
  the instrument's life. One-ended by construction, cited, and unverified.
- **Declared inference** — a value nobody stated, entered with what it rests on, what would
  settle it, and an empty verification date. Not a new mechanism: an unverified value and a
  verification task, which both already exist.
- **Premium or discount at purchase** — the difference between what was paid and face times
  quantity, reported as its own figure naming the category treatment that governed it.
- **Typed refusal** — purchase before coverage, reinvestment with no price, and (should the
  figures ever exist) accrued interest and clean price.
- Reused unchanged: the instrument interface and registry, the holding, the ledger, the tax
  classes and their dated schedules, the cash-flow schedule, the hurdle figures, the tuple
  join, provenance and the run manifest.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A synthetic enumerated declaration with a hand-sized schedule projects a
  purchase whose every cash-flow row, tax charge and total matches arithmetic worked out by
  hand and checked into the repository beside the assertion, within the single project
  tolerance. (FR-001, FR-004)
- **SC-002**: A tuple built on an enumerated declaration and a tuple built on a generative
  declaration with the same resulting cash flows — same holding, route in, tax classes,
  route out and horizon — produce figures equal within the single project tolerance and the
  same ranking position. The comparison is field by field, and the only permitted
  differences are identity, provenance, the stated exclusions, the schedule's statement of
  conventions, and **the causation detail prose**. ⚙ The last one is a correct difference
  that would otherwise fail the test: a generative coupon's detail names the rate, the day
  count and the business-day rule it was computed from (`core/instruments/fixed_income.py`),
  an enumerated one has none of the three to name, and that prose is inside the canonical
  form on every row — `core/ledger/canonical.py`'s `of_causation` includes `detail`
  deliberately, because *"a digest that ignored it would call two differently-explained
  results identical"*. ⚙ Tolerance rather than bit-equality because the two forms reach the
  same amount by different arithmetic; that is stated at the assertion site — and the
  enumerated fixture's amounts MUST be transcribed at full float64 precision from the
  generative `face x rate x year_fraction` computation, or the totals miss the tolerance by
  accumulated rounding rather than by anything the test is about. (FR-011)
- **SC-003**: A scan asserts that no module under the ledger, the tax engine, the decision
  layer, or the results — `core/results/project.py` included — names the enumerated form.
  ⚙ **What this scan does not catch, stated so it is not read as complete**: FR-012 forbids
  naming the form *and* testing which form a declaration is, and a name-scan catches the
  usual spellings of the second only because they name the type (`isinstance(...)`,
  `case EnumeratedTerms()`). A form test spelled without the name — `terms.schedule is not
  None`, a `case GenerativeTerms(): ... case _:` pair, `if decl.form != "generative"` — passes
  the scan. That residual is covered by review and by FR-011b's delegation, not by this
  criterion. (FR-012)
- **SC-004**: A third instrument declared in the enumerated form, in data only, runs the
  full pipeline and appears in the comparison with no source-code change. (FR-001, FR-013)
- **SC-005**: On a synthetic instrument whose coupon and disposal classes carry different
  declared rates, relabelling exactly one payment changes the tax total by exactly the
  hand-computed difference, and relabelling it on an exempt-on-both-sides instrument changes
  nothing — the second half proving the first test was necessary. (FR-007, FR-010)
- **SC-006**: A battery of broken declaration files — both forms at once, neither form, an
  empty schedule, an unordered list, a payment before the coverage start, a non-positive
  amount, a missing kind, an unknown kind, no principal repayment, a declared maturity date,
  an income kind with no tax class, a duplicate identifier — fails at load, every failure
  naming the file and the offending entry, and no default is substituted in any case.
  (FR-002, FR-006, FR-009)
- **SC-007**: A schedule declaring two payments on one date with different kinds loads and
  projects as two payments; the count of rows on that date is two, not one. (FR-006)
- **SC-008**: A purchase dated one day before the coverage start produces a typed refusal
  naming both dates; the same purchase dated on the coverage start succeeds. A declared
  opening lot acquired before the coverage start refuses the same way. (FR-014)
- **SC-009**: The reinvestment policy on an enumerated instrument produces a typed refusal
  naming the missing price, while the hold-as-cash policy on the same declaration produces a
  full projection. (FR-015)
- **SC-010**: Every cash-flow row of an enumerated projection states that no periodicity
  generated its date, no business-day rule moved it and no day count sized its amount, while
  naming the declared day count that annualises; no row names a periodicity or a
  business-day rule; and the golden canonical encoding distinguishes this statement from a
  generative row's three named conventions. (FR-016)
- **SC-011**: The contractual yield of an enumerated projection is produced rather than
  refused, and equals the yield of the equivalent generative projection within the single
  project tolerance — which requires the two declarations to name the **same** day count,
  since the yield annualises on it. A pair differing only in that convention produces two
  different yields, and that is correct rather than a defect: it is what makes the day count
  a declared fact instead of a hidden constant. (FR-003a, FR-018)
- **SC-012**: With every inference left unverified — which is their expected first state —
  100% of figures derived from an enumerated declaration carry the unverified mark, and no
  derived figure appears unmarked. (FR-020)
- **SC-013**: The provenance gate fails on an enumerated declaration whose inferred value
  lacks its inference statement or its verification task, naming the file and the field.
  (FR-022)
- **SC-014**: A scan finds no source-code site that reads a last payment as principal,
  reads the largest payment as one, divides a declared amount by 100, derives a coupon rate
  from an amount and an interval, or infers a coverage window. The first two are FR-008's
  prohibitions and the scan is what asserts them: a kind that is never inferred leaves no
  behaviour to observe, so the absence of the code is the only available evidence. It is
  also the second lock FR-003c names, which is why the coupon-rate derivation is scanned for
  here rather than only forbidden there. (FR-003c, FR-008, FR-021)
- **SC-015**: An enumerated projection's yield figure states the dirty-price exclusion, and
  the equivalent generative projection's does not. (FR-023)
- **SC-016**: A purchase above the principal it will get back reports the premium as its own figure, names the
  category treatment that governed it, and records the full cost as the lot's basis. Under
  the exempt category the year's liability is zero, the carryforward is absent, and no other
  category's base moves by any amount. Under the netting category reached by FR-010's
  fixture, the same premium reduces that category's netted base by exactly the hand-computed
  amount and carries forward when the year is negative — the two runs differing only in the
  declared category. (FR-024, FR-025, FR-026)
- **SC-017**: Feature 001's and feature 010's existing **worked examples** are unchanged by
  this feature, since no generative declaration's behaviour changes.
  ⚙ **Amended 2026-08-30. The clause said "and goldens", and that half does not follow from
  its own reason.** FR-025 puts a new figure on every projection, so the one golden
  (`tests/golden/ovdp_synthetic_a.golden.txt` — there is exactly one for this path) says one
  more true thing about every holding and its recorded digest moves. No amount, date, tax or
  rate moves with it, which is the claim the reason actually supports. Constitution 1.2.0,
  Principle V: *a golden file is evidence, never a freeze*, and its digests are witnesses
  rather than terms — shaping the figure around not disturbing one is the inversion that
  amendment exists to forbid. The golden was regenerated deliberately and the changed lines
  are quoted in the landing commits.
- **SC-018**: A **synthetic** fixture transcribed from a declared source that published its
  payments out of date order carries that order as a stated fact; changing the fixture's
  payments to ascending order removes the record, so the field is proved to track the source
  rather than to be boilerplate. ⚙ Synthetic rather than the real issue, and the choice is
  forced: transcribing `UA4000235865` would mean declaring a real ОВДП under
  `data/instruments/`, which this feature puts out of scope. The fixture is modelled on that
  issue — principal a day before the final coupon — and the assertion is about the mechanism,
  not about that ISIN. (FR-020a)
- **SC-019**: A declaration carrying an issue date, a coupon rate, a periodicity, a
  business-day rule or a maturity date fails at load naming the file and the field; one
  carrying no day count fails the same way. (FR-003, FR-003a)
- **SC-020**: A scan finds no site where the declared day count reaches an amount: it
  appears only in annualisation, and every payment amount in an enumerated projection is
  traceable to a declared payment rather than to a computation. Changing the declared day
  count in a test copy moves the yield and leaves every cash-flow amount bit-identical.
  (FR-003b)
- **SC-021**: A declaration attempting a two-ended coverage window — a closing date as well
  as an opening one — cannot be expressed: the field does not exist, and a file supplying
  one fails at load naming it. (FR-005)
- **SC-022**: All three sites that read a generative field today answer for both forms: an
  opening lot acquired before an enumerated instrument's coverage start refuses with the
  same typed failure as one acquired before a generative instrument's issue date; the tuple
  outcome annualises an enumerated instrument; and the projection builds both a conventions
  statement and its year fractions from what the declaration answers. None of the three
  gains a test of which form it was given. (FR-011a, FR-011b, FR-012)
- **SC-023**: No output of an enumerated projection contains an accrued-interest figure, a
  clean price, or any field splitting the purchase cost — asserted by a walk over every
  result record, so the absence is proved rather than assumed. (FR-017)
- **SC-024**: Every refusal this feature adds is a typed value, and its reason appears in
  the rendered output; a battery over each one finds no refusal whose reason is dropped
  between the core and the result. (FR-019)

## Assumptions

- **The motivating data is not wired in.** Every test here runs on labelled synthetic
  enumerated fixtures, following the precedent of `ovdp_synthetic_a.toml`. The 32 real
  issues are quoted as the measurement that justifies the form and are declared later, as a
  data change this feature makes possible.
- **Observed is not verified, and inferred is neither.** `data/observations/inzhur.toml` is
  an observation file with every verification date empty by construction. Nothing in it may
  be treated as checked, and the inferences drawn from it inherit that and add their own
  uncertainty.
- **The endpoint is a seller's publication.** Inzhur publishes the schedule of instruments
  it sells. That is a quotation, not an independent record of the issue's terms, and it is
  the reason the coverage claim needs a citation of its own.
- **Nothing prices a secondary-market sale.** There is no yield curve and no market price
  series in this project. An enumerated instrument is projected to the end of its schedule,
  exactly as a generative bond is projected to maturity; a disposal at an intermediate date
  would need a price nobody has, and inventing one is out of scope in both forms.
- **The accrued/clean split is deferred, not designed away.** The fact that would restore it
  is the start of the accrual period containing the purchase, plus a declared accrual basis.
  For many issues the previous coupon date is in fact inside the published window, so the
  split is recoverable later without an issue date; it is deferred because nothing in the
  engine computes accrued interest today and a refusal for a figure nobody asks for is dead
  code. Recorded as a `[[future]]` entry rather than left implicit.
- **One owner, no delivery surface.** As in 001 and 006: results are produced and asserted
  by the test suite.

## The premium, and why it is not a clarification

This was drafted as an open clarification on 2026-08-24 and **withdrawn the same day**,
because the question had already been answered in this repository and the draft had not read
the answer. Recorded rather than deleted: the reasoning that made it look open is the
reasoning someone will repeat.

**The question as drafted.** A secondary-market ОВДП is usually bought at a dirty price
above face (the Edge Cases carry the count).
Held to the end of its schedule, the principal repayment returns face, so the ledger
realises a loss equal to the premium — around 25.59 per unit for `UA4000234413` at its
observed buy price of 1 025.59. Is that premium a capital loss on disposal, or interest
amortised against the exempt coupon; and may it reduce another base?

**Where the answer already was.** `data/tax/timing/ua.toml` declares `exempt_securities`
with `treatment = "outside"` and `carryforward = "none"`, cited to пп. 170.2.8 «б» ПКУ and
that subpoint's last paragraph — «платник податку не включає до розрахунку загального
фінансового результату операцій з інвестиційними активами суму доходів **та витрат** на
придбання таких інвестиційних активів» — read 2026-08-22 and re-read 2026-08-24. Acquisition
costs are outside the calculation, so the premium reduces nothing. The engine already models
it: `Treatment.OUTSIDE` states the consequence in its own words — an exempt loss buys no
shield — and feature 009 pins it.

**Why the draft mistook a value for a gap.** The second half of the question assumed the
category assignment was open (*"if the exempt class shares a category with a taxable one"*).
It is not open; it is declared, and it is cited. The distinction between the two legal
readings then decides no figure this feature can reach: under `outside` with no
carryforward, both give a zero liability and nothing that travels. A question whose two
answers produce the same number in every reachable case is not a gap in the specification.

**What stays true, and is FR-026 rather than a clarification.** The distinction becomes
live the moment an enumerated instrument is declared under a class whose category **nets** —
and the review found that this feature reaches that case itself: `investment_profit` is
declared `nets`/`unlimited`, and FR-010's mandated fixture, whose two income kinds carry
different rates, lands in it. So FR-026 asserts the netting case rather than warning about
it. It is the same shape as FR-010 — invisible under an exemption, and invisible is where a
defect ships — with the difference that here the invisible half is made to show.

## Owner verification tasks

Four. The premium's treatment is deliberately **not** among them: it is declared and cited
in `data/tax/timing/ua.toml`, whose own empty verification date is that file's outstanding
task and not this feature's to restate.

Facts no source settles, recorded as tasks rather than filled with a guess. Each keeps the
affected value's verification date empty, and the mark propagates.

1. **The face value of 1 000.00 UAH.** It rests on 32 of 32 published schedules carrying a
   payment of exactly `100000` — the largest in each — read against buy prices near 1 000.
   No issuer statement has been read.
   Settled by the issue's own умови розміщення, or the МФУ or НБУ record for the ISIN.
2. **The kopeck scaling.** That `100000` denotes 1 000.00 UAH rather than 100 000.00 UAH
   rests on the same comparison. `scripts/fetch_inzhur.py` carries the endpoint's `amount`
   verbatim and performs no conversion, so the scaling is entirely this project's reading.
   Settled by the same source as task 1.
3. **The coverage claim, per issue.** The endpoint states no window, and the window it in
   fact publishes is not uniform — from 341 days before the retrieval date to 170 days after
   it, across 24 active issues. Whether Inzhur's publication alone is acceptable evidence
   for a completeness claim, or whether a second source is required per ISIN, is the owner's
   call and belongs to the later data change.
4. **The coupon/principal reading.** That the final `100000` is a principal repayment and
   the rest are coupons is a human reading of a list of numbers. Settled by the same source
   as task 1.

## Required tests this feature closes

None outright. `docs/REQUIRED_TESTS.md` has no row for a declaration form, and inventing one
here would be a row written to be flipped by the feature that wrote it.

Two rows are **touched and not claimed**, and the landing change should say so rather than
flip them:

| Row | What this feature adds to it |
|---|---|
| **H1** | The data-only extensibility claim gains a second instrument shape. SC-004 exercises it for an enumerated declaration; whether that strengthens H1's own test or sits beside it is decided at planning. |
| **D1** | Unchanged by design (SC-017). Recorded here because a reader will reasonably expect a schedule feature to move it, and it does not. |

## Out of scope

Named explicitly so the plan does not drift into them: **wiring the 32 real ОВДП issues into
`data/instruments/`** — a later data change, and the thing this feature exists to make
possible; anything about the Inzhur funds, whose NAV-versus-price problem is a different one
and is already handled by feature 006; fetching, refreshing or automating anything —
`scripts/fetch_inzhur.py` exists and is not this feature's business; market prices, a yield
curve, and any disposal at a date other than the end of the schedule; accrued interest and
the clean/dirty split, deferred with its reason above; declaring a **real** taxable
enumerated instrument, which would arrive with its own cited tax category (FR-026 reaches
the netting case through a synthetic fixture instead); the display-currency switch; and the
web and command-line interfaces.

⚙ **Not out of scope, though a reader expects it to be:** the three call sites of FR-011a
and FR-011b. Changing them is required work. What stays out is any change to what a generative
declaration *produces* — SC-017 pins that, and the refactor is deliberately shaped so the
generative answer is the same answer it gives today.
