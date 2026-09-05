# Feature Specification: Accrued interest on a carried quotation

**Feature Branch**: `022-accrued-interest`

**Created**: 2026-09-05

**Status**: Draft

**Input**: The owner, 2026-09-05: «так, треба рахувати правильну дохідність».

## Why this feature exists

An early exit is struck today at the seller's quotation less every coupon that detached while
the holding held the paper. That removes a double count and models **no accrual**, so every
early exit returns the seller's spread and nothing else, whatever the holding period — a
one-month and a three-month hold of UA4000236228 reach the same amount, which
`tests/worked_examples/test_a_coupon_inside_the_window.py` asserts. The purchase leg is worse:
the buy quotation is used unchanged on whatever day the money arrives, and where the window
holds to maturity there is no second leg to cancel the error and nothing states it.

A bond earns interest daily. The price it is bought and sold at carries the interest accrued
since the last coupon, and once the accrual is modelled the coupon subtraction stops being a
rule of its own: **detaching a coupon is the accrual resetting to zero.** This feature closes
the `enumerated-accrued-interest` and `the-buy-quotation-is-not-carried` futures together,
because they are one omission read from two ends.

### What 013 FR-017 forbade, and why it may now be lifted

013 FR-017 forbids an accrued figure or a clean price for an enumerated instrument, on the
ground that two facts are missing: the start of the accrual period containing the date, and
the basis interest accrues on within it. Both are now declared. The transcribed depository
schedule states **every** coupon date, so the dates bracketing any date are read off the list
rather than inferred (016; the issue date is still absent and is still not needed), and the
declaration carries `day_count`.

What remains an assumption, and is stated once rather than hidden: **the accrual is linear
within a coupon period, on the declared day count.** The issuer's own accrual formula is not
published by the NBU depository register — its rows carry `pay_date`, `pay_val` and `pay_type`
and nothing about how interest builds between them — so a linear reading is a choice.

## The model

```text
period(t)      the declared coupon period containing t: [c_i, c_i+1)
                 for consecutive declared coupon dates c_i, c_i+1
accrued(t)     = C_i+1 x  yf(c_i, t) / yf(c_i, c_i+1)      under the declared day count
clean          = quote - accrued(observed_on)               the quotation is a DIRTY price
price(t)       = clean + accrued(t)
```

Three consequences, each a requirement below. **The clean price is what is assumed constant**,
not the quotation, so the owner's declared belief stops being "the quotation holds net of what
detached". **Both legs are carried** by one formula — the buy quotation to `purchased_on`, the
sell quotation to `sold_on`. And **the coupon subtraction disappears**: a coupon between two
dates puts them in different periods, `accrued` resets, and the drop falls out of `price(t)`
rather than standing beside it.

The day count enters **only as a ratio of two year fractions inside one period**, which keeps
013 FR-003b standing: a ratio yields no coupon rate, and so no extrapolated issue date. It is
still computed with the declared convention rather than assumed to be a ratio of day counts,
because the two part company across a year boundary.

## The worked example

UA4000236228, `day_count = "act/365"`, coupon 85.50 per unit, semi-annual. Declared coupon
dates around the trade: **2026-03-11** and **2026-09-09** (182 days), then **2027-03-10**
(182 days). Quotation observed **2026-08-24**: buy 1089.32, sell 1087.89. Purchase
**2026-09-02** (horizon opens 2026-09-01; `inzhur_direct` declares one day of latency), sale
**2026-10-01**.

```text
accrued(2026-08-24) = 85.50 x 166/182 =   77.98      166 days into [03-11, 09-09)
accrued(2026-09-02) = 85.50 x 175/182 =   82.21      175 days into the same period
accrued(2026-10-01) = 85.50 x  22/182 =   10.34       22 days into [09-09, 03-10)

clean (buy)   = 1089.32 - accrued(08-24) = 1011.34
clean (sell)  = 1087.89 - accrued(08-24) = 1009.91   the two clean prices differ by the
                                                     whole 1.43 spread, and by nothing else
purchase price 2026-09-02 = clean(buy)  + accrued(09-02) = 1093.55
sale price     2026-10-01 = clean(sell) + accrued(10-01) = 1020.24

45 units (46 x 1093.55 = 50 303 exceeds the declared 50 000)
   deployed   45 x 1093.55 = 49 209.66      undeployed 790.34
   coupon     45 x   85.50 =  3 847.50      collected 2026-09-09, held as cash
   sale       45 x 1020.24 = 45 910.87
   reaches                   49 758.37
   gain                         548.71  =  +1.1151% over 29 days held
```

**Every figure above is rounded for display and the engine works from the unrounded values**,
so two-decimal columns are a cent apart — 1009.91 + 10.34 reads 1020.25 against a true
1020.2416. What a reader checks by hand instead is the identity the whole model reduces to,
which needs no decimals at all: the clean price cancels, and per unit

```text
sale + coupon - purchase = 85.50 x 29/182 - 1.43 = 13.6236... - 1.43 = 12.1936...
```

29 days held at the issue's own 85.50 per 182 days, less the round-trip spread. Times 45 units
that is 548.71, which is the `gain` line above.

**Annualised: 14.03%** simple (×365/29), **14.98%** compounded. That is the issue's accrual
on the price actually paid — 171.47 a year on 1093.55, **15.68%** — less the round-trip
spread annualised over a one-month hold, **1.65 points**. Today the same candidate returns
**−0.13%** over the month, marked "understated".

The two annualisations are **arithmetic on a 29-day holding period, not the engine's figure**:
`TupleOutcome.implied_rate` is an IRR over its own span (`horizon.start` to the last arrival,
on the declared day count). This spec does not measure it; the golden does.

**Hold to maturity: the exit leg does not change, the entry leg does.** Read in the code rather
than supposed: `enumerated.events` calls `acquire.early_sale` only when an `EarlyExit` exists
**and** a residual survives the window, so a holding that reaches its own maturity is paid the
declared payments — face plus the final coupon — and no quotation is struck. Its **purchase**
price is `tuple_outcome._price_for`, which returns `access.quote.price` unchanged for every
bond: exactly the signed overstatement `the-buy-quotation-is-not-carried` recorded, UA4000231195
reaching 5.8% on a 17.5% coupon. Carrying the buy quotation fixes it, and it moves
hold-to-maturity candidates that name no early-exit belief at all — which is why the assumption
below is its own belief and is **not** the early-exit belief widened.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A month's hold returns a month's interest (Priority: P1)

The owner asks what 50 000 UAH does over one month in UA4000236228 and is told 1.12% for the
month, about 14% annualised, resting on a named belief that the clean price holds.

**Independent Test**: the worked example above, asserted per unit and per 45 units.

1. **Given** the shipped registry and the owner's one-month horizon, **Then**
   UA4000236228's purchase price is 1093.55, its sale price 1020.24, and it reaches 49 758.37.
2. **Given** the same candidate over three months, **Then** it reaches strictly more.

---

### User Story 2 - A bond held to maturity is not bought at the wrong price (Priority: P1)

**Independent Test**: UA4000231195 over the owner's twelve-month horizon, whose coupon of
2026-08-26 falls between the 2026-08-24 quotation and the 2026-09-02 purchase.

1. **Given** a coupon detaching between the quotation and the purchase, **Then** the purchase
   price is the clean price plus the accrual of the **new** period, below the quotation.
2. **Given** a candidate that holds to maturity, **Then** no quotation is read at its exit and
   the proceeds are the declared payments.

---

### User Story 3 - A figure that cannot be computed refuses by name (Priority: P2)

**Independent Test**: a fixture quotation observed before an issue's first declared coupon.

1. **Given** a date in no declared coupon period, **Then** a typed refusal naming the date and
   the coupon dates it falls outside is returned, and no price is emitted.
2. **Given** a schedule declaring no coupon at all, **Then** the accrual is zero and the price
   is the quotation — a figure, not a refusal.

### Edge Cases

- **A date on a coupon date.** `c_i` opens its own period, so `accrued(c_i) = 0`: the coupon
  has just detached. The interval is half-open at the far end so no date belongs to two.
- **A date before the first declared coupon — and it is not hypothetical.** `covers_from` is
  the **placement date**, not a declared accrual start, and the three newly placed issues prove
  it: UA4000239081 declares 29 days from `covers_from` to a first coupon of 82.20 that its own
  next period pays over 182, UA4000239040 155 days to a full 79.25, UA4000239107 183 days to a
  full 80.35 (measured 2026-09-05). Opening the first period at `covers_from` would accrue a
  full coupon over a stub. Deriving the true start from the amounts is 013 FR-021's forbidden
  step, so the figure **refuses**, and the three leave the ranking (below).
- **A quotation dated after the sale.** Carried backwards by the same formula. Whether the
  carried price is above or below the quotation depends on which period each date falls in, so
  no direction is claimed — and no special case is written.
- **A repayment of principal inside the window.** A repayment retires units, so a declared
  coupon amount is per *original* unit while the quotation is per *remaining* one. Already
  refused by `enumerated.events`; the refusal survives, restated in the accrual's terms.
- **A quotation observed on the very day it is used.** `accrued` cancels, the price is the
  quotation, and no assumption was leaned on — so none is stated.

## Requirements *(mandatory)*

### Functional Requirements

**The figure**

- **FR-001**: A **coupon period** MUST be the half-open interval between consecutive declared
  coupon dates, `[c_i, c_i+1)`. Nothing before the first declared coupon date and nothing on
  or after the last belongs to one, and neither `covers_from`, an issue date nor a maturity
  date may stand in for a coupon date.
- **FR-002**: `accrued(t)` MUST be the coupon amount ending the period containing `t`, times
  `yf(c_i, t) / yf(c_i, c_i+1)` under the instrument's **declared** day count. No convention
  is defaulted; the existing no-fallback rule of `conventions.day_count` governs.
- **FR-003**: The accrual MUST be **linear within the period**, and that MUST be stated once,
  in `docs/METHODOLOGY.md` and on the declared belief, as an assumption whose alternative —
  the issuer's own accrual formula — the depository does not publish.
- **FR-004**: `clean` MUST be `quote - accrued(observed_on)`, and the price on any date `t`
  MUST be `clean + accrued(t)`. One function serves every use; a second expression of the
  same identity is what this feature deletes rather than adds.
- **FR-005**: The **buy** quotation MUST be carried to the purchase date by FR-004, for every
  bond purchase, whether or not the horizon ends before the instrument's terms do.
- **FR-006**: The **sell** quotation MUST be carried to the sale date by FR-004. The
  subtraction of whole detached coupons (`early_exit.detached_since`) MUST be **retired**, not
  kept beside the formula: a coupon between the two dates is a period boundary, and its drop
  is `accrued` resetting.
- **FR-007**: Both declaration forms MUST be treated by one rule. The enumerated form reads
  its declared payment dates; the generative form reads the accrual periods it already
  generates (`terms_of.accrual_periods`), through the same declared business-day rule its
  `coupons_per_unit` applies. Two rules would disagree the first time either moved.

**What refuses, and what does not**

- **FR-008**: For a schedule declaring **at least one** coupon, a date in no declared coupon
  period MUST produce a typed refusal naming the date, the instrument and the coupon dates it
  falls outside, and no price. This includes a quotation whose `observed_on` is outside every
  period, which refuses the whole candidate rather than only its sale. FR-009 governs the
  no-coupon case; the two never both apply.
- **FR-009**: A schedule declaring **no coupon** MUST NOT refuse. Its accrual is zero on every
  date by definition, `clean` equals the quotation, and the price is carried unchanged. This
  is a legitimate zero, not an absence: a zero-coupon bond earns its return in the price and
  the model reproduces that with no special case. A refusal here would refuse a correct
  figure, which is the mirror of a silent default.
- **FR-010**: A refusal for a missing day count MUST NOT be written. `EnumeratedTerms.day_count`
  and `BondTerms.day_count` are both required `str` fields, so the state is unrepresentable
  and a guard for it would be a guard that never fires — a false guard, and dead code.
- **FR-011**: Every refusal above MUST be a typed value carrying its reason, and the reason
  MUST surface in the output.
- **FR-012**: The `InconsistentTerms` value `enumerated.events` returns where principal is
  repaid **and** a quotation is carried inside one window MUST survive, restated in the accrual's terms: a
  repayment rebases what a unit is, and one quotation cannot price both sides of it.

**What is lifted, and what stands**

- **FR-013**: 013 FR-017's prohibition MUST be lifted for an instrument whose schedule
  declares every coupon date. The additional exclusion 013 FR-023 puts on an enumerated
  projection's `HurdleRate.excludes` — that the purchase price is a dirty price never
  separated — MUST be removed, because it is no longer true.
- **FR-014**: 013 FR-003b MUST stand. The day count MUST enter the accrual only as a **ratio
  of two year fractions inside one period**, and MUST NOT be used to derive a coupon rate, an
  interval or an issue date.
- **FR-015**: 013 FR-024 MUST stand: the full purchase cost stays the lot's cost basis, and no
  part of it is reclassified as accrued interest. The tax character of accrued interest paid
  at purchase is 013 FR-025's premium figure and its declared category treatment, and this
  feature adds no rule of its own (see `docs/METHODOLOGY.md` §31.6).

**The assumption, and what it is stated on**

- **FR-016**: The declared belief MUST be restated as **the clean price holds**: its `id`
  changes from `quotation_holds_net_of_detached_coupons`, and its `rationale` states the
  constant clean price, the linear intra-period accrual, and that neither is observable.
- **FR-017**: The belief MUST NOT be named for the early exit anywhere it is named. It now
  governs every use of a dated quotation, including purchases that hold to maturity, so **six**
  sites move together: the declaration's directory, the record's core module,
  `resolver.EARLY_EXIT_DIR`, the HTTP category id `early-exit-belief`, `manifest.InputKind`'s
  `early_exit_assumption` member, and `declarations.tuples.early_exit_file`. The constant is
  reached from `api/http/categories.py` by `getattr` on its **name**, which neither `mypy` nor
  `lint-imports` can see, so renaming it without the category raises at request time. The
  absence of the file MUST stay a load-time refusal with no default.
- **FR-018**: Every candidate whose purchase or sale price was carried across a gap MUST name
  the belief in `TupleOutcome.rests_on` — hold-to-maturity candidates included. A candidate
  bought and sold on the quotation's own day carried nothing and MUST NOT name it.
- **FR-019**: `Exclusion.EARLY_EXIT_IGNORES_ACCRUED_INTEREST` and
  `Direction.SALE_STRUCK_TOO_LOW` MUST be **removed**. Their warrant was that whole coupons
  came out where an accrual was in; that is gone, and a claim kept past its warrant is worse
  than one never made.
- **FR-020**: A replacement exclusion MUST state that the clean price is assumed constant, and
  MUST carry **no direction**. Rate risk is symmetric — 015 FR-033's own reasoning — so the
  carried price may err either way, and a sign asserted without a warrant is a number more
  confident than its inputs.
- **FR-021**: The other three claims of 015 FR-033 MUST stand unchanged: the figure is a point
  where the world is a distribution; the spread is a seller's quote and is understated; and no
  rate risk is modelled.

**What is reported, and what it inherits**

- **FR-022**: `SoldEarly` MUST report the **clean price** and the **accrual at the sale date**
  per unit, so a reader holding the quotation and the struck price can tell an accrual from a
  spread. `detached_per_unit` and `skipped_before_purchase` MUST be removed: both exist to
  explain a subtraction that no longer happens.
- **FR-023**: Every carried price MUST inherit the provenance of the quotation **and** of every
  declared coupon amount and date that entered its accrual. A price built by subtracting one
  marked figure from another and adding a third MUST NOT launder any of them (Principle I).
- **FR-024**: `docs/METHODOLOGY.md` MUST carry the formula of FR-001 to FR-004 with its
  worked arithmetic, and §34's early-exit entry MUST be **rewritten** rather than appended to:
  its second paragraph ("the second line is not a refinement") and its four-claim table both
  state as fact what this change falsifies.
- **FR-025**: Goldens the change moves MUST be regenerated **deliberately**, with the diff read
  and the changed figures quoted in the commit message — a golden is evidence, not a freeze
  (Principle V). No golden may be left un-regenerated on the ground that its digest moved.

## Key Entities

- **Coupon period** — a half-open interval between two consecutive declared coupon dates, with
  the amount that ends it. Derived from the declaration; declared nowhere.
- **Clean price** — a quotation net of the accrual on its observation date. The thing assumed
  constant.
- **The clean-price belief** — the owner's declared assumption, with `id`, `is_assumption` and
  `rationale`. No citation: there is nothing for a source to vouch for.

## Success Criteria *(mandatory)*

- **SC-001**: The worked example above reproduces to the project tolerance: `accrued` at the
  three dates, both clean prices, the purchase and sale prices, and the 49 758.37 reached.
- **SC-002**: A three-month hold of UA4000236228 reaches strictly more than a one-month hold.
  Today the two are exactly equal, which is the defect. Its twelve-month section is a different
  case — the issue matures 2027-03-10, inside that horizon, so it is held rather than sold.
- **SC-003**: A hold-to-maturity candidate's implied rate rises materially. UA4000231195
  reaches 5.8% on a 17.5% coupon today, against about 15% at its clean price of roughly 1 023
  (measured 2026-09-05, before this spec was written). The new figure is **measured on the
  run**, and no number is asserted from this line.
- **SC-004**: No result record anywhere carries a detached-coupon figure, and no answer states
  an accrued-interest exclusion — a walk over every field of every result record, which is the
  shape 013's own absence proof already uses.
- **SC-005**: Every early-exit and every carried purchase names the clean-price belief in
  `rests_on`; a trade struck on the quotation's own day names it nowhere.
- **SC-006**: A date outside every declared coupon period refuses by name, and the refusal
  reaches the answer's output rather than only the type.
- **SC-007**: The three newly placed issues are named in the answer as refusals with their
  reason, and the population that dropped is reported rather than inferred from a shorter list.

## Counts that move

Named so the implementer expects them rather than discovering them:

- `tests/golden/the_answer.golden.txt` — every early-exit line, and every accrued-interest
  exclusion row (56 across the three sections, measured 2026-09-05).
- `tests/golden/candidate_set.golden.txt` — purchase prices move, so unit counts and
  undeployed remainders may move with them.
- `tests/worked_examples/test_a_coupon_inside_the_window.py` — rewritten as the worked example
  above. Its `DETACHED_PER_HORIZON`, `MULTI_COUPON` and `BEFORE_THE_PURCHASE` measurements lose
  their subject; the two issues in `BEFORE_THE_PURCHASE` keep theirs, as the case where the
  purchase is carried across a coupon.
- Any test pinning "the month returns exactly the spread" — the identity is gone, and its
  replacement is that the month returns the accrual less the spread.
- `src/terezy/data/manifest.py` — the `early_exit_assumption` ref carries the belief's `id` and
  its file path, and `InputKind` is a closed `Literal` containing that member;
  `tests/unit/test_answer_manifest.py` pins the path string `scenarios/early_exit/owner-001.toml`.
- `src/terezy/api/http/openapi.json` and `tests/golden/test_the_openapi_document.py` — the
  `SoldEarly` schema lists `detached_per_unit` and `skipped_before_purchase` as **required**,
  the `InputKind` enum carries `early_exit_assumption`, and the category id is a path segment.
- **Three issues leave every answer, as named refusals rather than silently.**
  UA4000239040, UA4000239107 and UA4000239081 are newly placed, their depository lists open at
  a first coupon later than the 2026-08-24 quotation, and FR-008 therefore refuses the
  quotation itself. Seventeen lines each in `the_answer.golden.txt` and four each in
  `candidate_set.golden.txt` go (measured 2026-09-05). This is the price of FR-001, it is paid
  deliberately, and FR-011 is what keeps it from being a disappearance.
- `019-decision-layer` is **planned, not started**, and its spec's non-dominated counts of 2, 3
  and 10 are pre-fix readings that no test pins; they re-measure after this lands.
- `021-web-declared-data` is **in progress and is moved, not unaffected.** Its types are
  generated from the OpenAPI document, and that document moves three ways: two `SoldEarly`
  required properties out and two in, one `InputKind` enum member renamed, and one category
  path segment renamed. It regenerates; nothing it computes changes.

## Assumptions

- The accrual is linear within a coupon period on the declared day count (FR-003). The
  depository publishes no accrual formula; this is the assumption, stated once.
- The clean price is constant between the observation and the trade. Unobservable, declared,
  and unsigned.
- Every declared coupon amount is per unit as declared and does not change within its period.
- No shipped issue repays principal inside a window that also strikes a sale, which is why
  FR-012's refusal stays unreached in practice. Twelve of the twenty-four reach maturity inside
  the owner's twelve-month horizon and are held to it rather than sold (measured 2026-09-05),
  so the two mechanisms never meet.

## Out of scope

- **Secondary-market rate risk** — still the `secondary-market-rate-risk` future. This feature
  models how a price moves *with time at a constant clean price*; it does not model the clean
  price moving with the curve.
- **The market-quotation staleness kind** — still the `market-quotation-staleness-kind` future.
  How fast a quotation goes stale is a threshold question, not an accrual one.
- **The tax character of accrued interest paid at purchase** — 013 FR-025 and
  `docs/METHODOLOGY.md` §31.6 govern it, cited rather than restated (FR-015).
- **A fund's entry price** — priced from its declared NAV, not from a dated quotation, and
  untouched here.
