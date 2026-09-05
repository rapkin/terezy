# Methodology

How every number this tool reports is computed, in enough detail that you can check it on
paper. The constitution's standard is that *an undocumented formula is an incomplete
feature*; this file is the other half of the code.

It is written for the person deciding whether to believe a figure, not for the person
maintaining the code. Where a formula has a subtlety, the subtlety is stated rather than
smoothed over — that is the whole point.

Every worked example below is checked in as an executable test. Where one is, the test is
named, so you can run it rather than trust the arithmetic in this file:

```bash
uv run pytest -m "worked_example or golden" -v
```

---

## 0. What these figures do **not** account for

Read this first. It is the largest term in the real decision, and the predecessor project's
headline defect was omitting it.

**Route costs are not in any figure.** The hurdle rate reports what a bond pays, from the
moment it is bought to the moment it redeems. It says nothing about the cost of getting
hryvnia into the account that buys it (**funding route cost, in**) or of turning the
proceeds back into spendable money (**exit route cost, out**). For a UAH-funded OVDP
purchase through a domestic broker those happen to be near zero, which is exactly why this
figure is a useful *benchmark* — and exactly why comparing it against an instrument whose
access ramp costs five to ten percent one way, without pricing that ramp, would be wrong by
more than the entire yield.

The result record says so on its face: `HurdleRate.excludes` carries these strings, and
they are printed with the figure.

- `funding route costs (in)`
- `exit route costs (out)`
- `inflation (the figure is nominal)`
- `public holidays (weekends are observed; no holiday calendar is modelled)`

⚙ The count used to be written out as *three* and the fourth line was added without it,
which is the exact staleness shape a count over its own list has. Corrected in 013, in the
same change as the identical count in `core/results/hurdle.py`. A **declaration** can add to
this set, so it is a floor rather than a closed list and the figure prints whatever it
actually carries. No declaration adds one today: the clause the enumerated form used to add —
that its purchase price was a dirty price nobody had separated — went with the separation
arriving (§31.5).

**Both return figures are still nominal, and beside them the real-terms slot now holds two
real figures.** A nominal 16% against double-digit inflation is a materially different
proposition from a real 16%, which is why the slot was reserved in the first place and why it
stayed empty until CPI arrived as declared, dated, cited data. It is filled now — see
[§27](#27-real-terms-the-fisher-relation-and-the-chain-behind-it) — by two figures that
**never mix into one number**: one deflated by declared observations, one by a declared
belief about future inflation. Where either one's inputs are missing, that figure alone is
typed-unavailable and its reason names what is missing. A real rate derived from a *guessed*
inflation rate is still forbidden; a *declared, dated, labelled* belief is a different thing,
and it says so on the face of every figure it touches.

The `excludes` line above is unchanged and still true: the two **nominal** figures exclude
inflation. The real figures are reported beside them, never instead of them.

**Every shipped instrument is real now, and every one of them is still unverified.** Feature
016 declared 24 ОВДП issues whose terms are the National Bank depository's record of what the
Ministry of Finance issued; each carries `is_synthetic = false` and is named for its ISIN.
Since the owner narrowed `data/README.md` rule 5 on 2026-09-02, **an invented instrument may
not ship at all**: `data/instruments/` holds those 24 and the two real Inzhur funds, which
declare `is_assumption_driven = true` because a fund's yield is a range it states about itself.
The invented declarations a test needs live in `tests/fixtures/data/instruments/`, each the only
example of a mechanism, and their terms are **invented** so that a hand-checkable example
exists. **No figure computed from a fixture describes something anyone can buy, and none may be
quoted as if it did.**

**Every `verified_on` in the whole directory is still empty**, and for the 24 the reason is now
one thing rather than everything: the terms could be checked against the issuer's register, and
the price could not. A dated seller's quotation has no independent record and shows a different
number tomorrow, so it stays unverified permanently — and because taint is asymmetric, every
figure a real issue produces carries the mark through the price alone.

Which files are which is a check rather than a sentence, in both directions:
`tests/contract/test_declaration_loading.py::TestEveryDeclaredInstrumentSaysWhetherItIsAFixture`
pins that a declaration's `is_synthetic` agrees with whether its id is an ISIN, and that
`data/instruments/` declares no fixture at all.

**The tax exemption is cited but unverified.** `data/tax/ua.toml` declares the
`ua_government_bond` class with a PIT rate of 0% and a military levy of 0%. The zeroes cite
the primary text, and it takes **two provisions** because the class covers two income kinds:
the coupon is exempt under **пп. 165.1.2 ПКУ** («проценти, що нараховані на державні цінні
папери») and the disposal gain under **пп. 165.1.52** («інвестиційний прибуток від операцій»).
Citing 165.1.52 for a coupon would cite a rule about investment profit for interest income.
The levy reaches neither, but only since **23.05.2020**: until Закон № 466-IX struck it, a
carve-out in пп. 1.7 п. 16-1 підрозділу 10 розділу XX excluded exactly these incomes from the
levy exemption, so ОВДП income bore the levy despite being PIT-exempt. Cited is still not
verified: nobody has checked any of it against the Tax Code on the owner's behalf, so
`verified_on` is empty and every figure derived from the class renders marked. See §11.

**Also absent, deliberately rather than by oversight:** accrued interest settled at
purchase; sale on the secondary market before maturity, and the thin-market haircut that
would apply to one; restructuring and default; pricing future purchases off a yield curve
instead of a single declared yield; any exchange rate at all (there is one currency, and
the core contains no conversion function); the date the tax liability is actually settled,
which the model now has and this figure deliberately does not — the hurdle rate places a
charge at **accrual**, because what a holding earns is a claim about the paper and when the
money leaves is a fact about the owner's tax year (§28.1); loss offset against **other
income** — which пп. 170.2.1 ПКУ forecloses, since the result of investment operations is
accounted for «окремо від інших доходів і витрат»; and public holidays, which are
uncited domain knowledge and therefore data this repository does not yet hold (see §2.3).

---

## 1. The coupon schedule

### 1.1 The formula

For one accrual period, one holding:

```
coupon = face_value × coupon_rate × year_fraction(accrual_start, accrual_end) × units_held
```

- `face_value` and `coupon_rate` are declared **per issue**, in its data file.
- `year_fraction` is the issue's **declared day-count convention** applied to the period
  (§2). It is never a hard-coded 365 anywhere.
- `units_held` is the purchase quantity plus every unit acquired by reinvestment before
  this period began (§7).

The engine evaluates it as `face × (rate × fraction × units)`. The association is worth
knowing about, because it is the reason a tolerance exists at all — see §11.

`coupon_rate` is a **fraction**, always: `0.155`, never `15.5`. Percent exists only in
declaration files, and is converted exactly once, at the data boundary (§9).

A declared coupon rate of **zero** produces no coupon periods at all, not a schedule of
zero-amount rows. That is a valid declaration of a zero-coupon bond, which pays its
principal and nothing else.

### 1.2 Where the coupon dates come from

The declared periodicity fixes a month step — `annual` = 12, `semiannual` = 6,
`quarterly` = 3 — and the dates are generated by **stepping back from the maturity date**,
not forward from the issue date, keeping every date in the half-open interval
`(issue_date, maturity_date]`.

Anchoring on maturity is the right way round because the final coupon is paid together
with the principal. The issue date itself pays nothing, so it is excluded.

Two consequences:

- **A short first period stays short.** If stepping back lands past the issue date, the
  first period is simply shorter than the rest and no coupon is dropped. The day-count
  fraction — not the step — is what makes that first coupon smaller.
- **The schedule cannot drift.** Each step is measured from the anchor (`maturity − n
  months`), never from the previous result, and the day of month is clamped to the target
  month's length. So a quarterly bond maturing on a 31st has coupons on the 31st of every
  long month rather than sliding permanently to the 30th the first time it passes February.

**Coupons dated on or before the purchase date are not this holding's income** — they were
paid to whoever held the bond then. The coupon *straddling* the purchase is nonetheless
paid to this holder **in full**, because accrued interest settled at purchase is a
secondary-market mechanic this feature does not model, and apportioning the coupon without
modelling the settlement that pays for it would invent a cash flow. A unit acquired by
reinvestment is treated the same way: it is the holder of record on the next coupon date,
so it receives that whole coupon.

### 1.3 The unadjusted accrual date and the adjusted payment date

These are two different dates and conflating them is a real bug class, so the engine keeps
them apart:

- **Accrual** is measured between the **unadjusted** scheduled dates. The size of a coupon
  is a property of the paper.
- **Payment** is the date money changes hands, and it is the accrual end date moved by the
  issue's **declared business-day rule**.

If the accrual boundary moved as well, every coupon would depend on where weekends fell,
and two economically identical bonds would pay different amounts. That is not what a
fixed-coupon bond does.

The implemented rules are:

| declared name | behaviour |
| --- | --- |
| `none` | leave the date where the schedule put it — a declared choice, never a fallback |
| `following` | the first business day on or after the date |
| `modified_following` | `following`, unless that leaves the month; then the last business day on or before |

**Weekends only, and uncited.** A public holiday is domain knowledge that arrives as data
with a citation and a verification date, and it now does (METHODOLOGY §35). These three rules consult
none of it, by owner decision CL-1 of 2026-08-30, so a coupon falling on a public holiday is
placed **on the holiday** — wrong in a stated way rather than a hidden one.
`tests/contract/test_no_calendar_free_working_day.py` counts every site that inherits it.

### 1.4 Worked example: synthetic issue A

Checked in as `tests/worked_examples/test_ovdp_schedule.py`, and recorded end to end as
`tests/golden/ovdp_synthetic_a.golden.txt`.

Terms: face 1 000.00 UAH per unit, coupon 15.5% per annum, issued 2026-01-15, maturing
2028-01-15, `semiannual`, `act/365`, `following`. Purchase: 10 units at par on the issue
date, so 10 000.00 UAH of notional and 10 000.00 UAH of cost.

Coupon dates, stepping back from maturity in six-month strides: 2028-01-15, 2027-07-15,
2027-01-15, 2026-07-15. The next stride back lands on the issue date, which pays nothing,
so the schedule is those four dates ascending.

Accrual periods, counted month by month on the **unadjusted** dates:

| accrual period | days |
| --- | --- |
| 2026-01-15 → 2026-07-15 | 31 + 28 + 31 + 30 + 31 + 30 = **181** |
| 2026-07-15 → 2027-01-15 | 31 + 31 + 30 + 31 + 30 + 31 = **184** |
| 2027-01-15 → 2027-07-15 | **181** |
| 2027-07-15 → 2028-01-15 | **184** |

`181 + 184 + 181 + 184 = 730 = 2 × 365`, which is the check that no period was dropped or
double-counted.

A year of interest on 10 000.00 of notional at 15.5% is 1 550.00, so each coupon is
`1 550.00 × days / 365`:

| paid on | days | coupon (UAH) |
| --- | --- | --- |
| 2026-07-15 | 181 | 768.6301369863013 |
| 2027-01-15 | 184 | 781.3698630136987 |
| 2027-07-15 | 181 | 768.6301369863013 |
| **2028-01-17** | 184 | 781.3698630136987 |
| | | **3 100.00 total — exactly two years of interest** |

**2028-01-15 is a Saturday.** (2026-01-01 was a Thursday, 2027-01-01 a Friday, 2028-01-01 a
Saturday, and the 15th is two weeks later.) The declared `following` rule therefore pays
the final coupon **and** the principal on Monday **2028-01-17**. The accrual still runs to
the 15th, so the coupon is the ordinary 184-day amount — only the date moved.

That two-day delay is not cosmetic: it costs about 4 basis points of yield. See §3.4.

---

## 2. The day-count fractions

The *choice* of convention is data, declared per issue. The *algorithms* are code, and
these three are the ones this engine implements. An unrecognised name is a **load-time
failure naming the file and the value** — there is no default convention anywhere, because
silently applying `act/365` to an issue that declared something else produces a schedule
wrong by a fraction of a percent: large enough to change a decision, small enough to look
plausible.

Worked examples for all of the below are checked in as
`tests/worked_examples/test_day_count.py`.

### 2.1 `act/365`

Actual elapsed days over a **fixed** 365-day year.

```
fraction = (end - start).days / 365
```

Leap years are invisible to the denominator. A calendar year containing 29 February comes
to `366 / 365 = 1.00273972…`, **not** 1.0. That is the convention behaving correctly, not a
rounding artefact: a bond on this basis accrues slightly more than a year's coupon over a
leap year.

*Worked:* 2025-01-15 → 2025-07-15 is `31 + 28 + 31 + 30 + 31 + 30 = 181` days, so the
fraction is `181 / 365 = 0.495890…`.

A zero-length period gives exactly `0.0`.

### 2.2 `act/act` (ISDA)

The period is split at every 1 January and each part divided by the length of **its own**
year — 366 in a leap year, 365 otherwise.

```
fraction = Σ over years  (days of the period falling in that year) / (365 or 366)
```

Any whole calendar year therefore comes to exactly 1.0, which is the property this
convention exists to provide.

*Worked:* 2024-12-01 → 2025-03-01 splits at 2025-01-01.

- the 2024 part is 31 days, and 2024 is a leap year → `31 / 366 = 0.084699…`
- the 2025 part is `31 + 28 = 59` days, and 2025 is common → `59 / 365 = 0.161643…`
- total `0.246343…`

Compare with `act/365` over the same dates: 90 actual days over a fixed 365 = `0.246575…`.
The two conventions genuinely disagree, which is why the choice has to be declared.

Note that a whole *half*-year is not exactly 0.5 under `act/act`: 2025-07-01 → 2026-01-01 is
184 days, so `184/365 = 0.504109…`. A July-to-January half year is longer than a
January-to-July one.

### 2.3 `30/360` (US bond basis)

Every month is 30 days and every year 360.

```
d1 = min(start.day, 30)
d2 = end.day, reduced to 30 when d2 == 31 and d1 == 30
days     = 360 × (end.year - start.year) + 30 × (end.month - start.month) + (d2 - d1)
fraction = days / 360
```

The end-of-month asymmetry is what makes two month-end dates six months apart come to
exactly 0.5, so a bond on this basis pays **equal** coupons — which is what a fixed-coupon
bond actually does.

*Worked:* 2025-01-31 → 2025-07-31.

- start day 31 caps to `d1 = 30`
- end day is 31 and `d1` is already 30, so `d2 = 30`
- `360 × 0 + 30 × (7 − 1) + (30 − 30) = 180`, and `180 / 360 = 0.5` **exactly**

*Worked, rule not firing:* 2025-02-28 → 2025-08-31.

- `d1 = 28` (below 30, untouched); `d2` stays 31 because `d1` is not 30
- `30 × (8 − 2) + (31 − 28) = 183`, so `183 / 360 = 0.508333…`

Slightly more than half a year: February's short month is counted as a full 30 days at the
start while August's 31st is counted in full at the end.

*Worked, leap year invisible:* 2024-01-15 → 2025-01-15 is `360 × 1 = 360`, so exactly 1.0
despite 2024 having 366 days.

### 2.4 Why the difference matters

Issue A (`act/365`, semiannual) pays **four different-sized coupons** — 768.63, 781.37,
768.63, 781.37 — because its accrual periods are 181 and 184 days. Issue B (`30/360`,
quarterly) pays **twelve identical coupons** of `1 000.00 × 0.1225 × 0.25 × 10 = 306.25`,
because every 30/360 quarter is exactly a quarter. Same engine, no code difference, and
each schedule states which convention it applied.

---

## 3. Yield to maturity (`nominal_ytm`)

### 3.1 What it is

The annual rate at which the bond's **promised gross** cash flows discount back to what was
paid for them. A property of the terms and the price, and of nothing else.

Cash flows are `(years from the purchase date, signed amount)`. Time is measured with the
issue's **declared day-count convention**, from the purchase date — the same convention
that sized the coupons. A separate hard-coded 365 here would let the yield disagree with
the schedule it came from, in a way that would look like a rounding difference and would
not be one.

```
NPV(r) = Σ  amount_i / (1 + r) ** years_i
YTM    = the r for which NPV(r) = 0
```

The exponent is a **real number**, so this is annual compounding evaluated at fractional
years. It is deliberately *not* continuous compounding (`exp(-r·t)`), which would give a
different rate for the same flows, and it is deliberately not per-period compounding on a
count of whole periods, which would ignore the fact that the periods are unequal.

### 3.2 How the root is found

Bisection, over the bracket `[-0.999999, 100.0]`.

- **Bisection, not Newton.** For a conventional series — one payment out at the start,
  receipts afterwards — the present value is strictly decreasing in the rate, so a bracket
  that straddles zero contains exactly one root and halving it cannot fail. Newton is faster
  and can leave the bracket on a badly conditioned series, which is a *silent wrong answer*
  rather than a slow one.
- **The bottom of the bracket is `-0.999999`, not `-1.0`.** At exactly −1 the discount
  factor is a division by zero for any flow after the purchase. A rate below this is not a
  rate this project will report: it is a total loss, and a total loss is described by saying
  so, not by quoting a percentage.
- **The top is 100.0** — 10 000% per annum. Above that the answer is not a yield.
- **A bracket that does not straddle zero raises.** By the time a series reaches the root
  finder, the purchase cost is known positive and the redemption known positive, which
  guarantees a sign change. A failure therefore means the caller built a series the function
  was never given a definition for, and extrapolating past the bracket would invent a rate.

### 3.3 Why it runs to float collapse rather than to a tuned tolerance

The loop stops when the midpoint of the bracket **equals one of its endpoints** — that is,
when the bracket has collapsed to two adjacent float64 values and halving it again would
return an endpoint unchanged and loop forever. An iteration cap of 200 sits behind that as
a safety net, not as the expected exit: halving a bracket of about 101 down to float
resolution takes roughly sixty steps.

There is no tuned convergence tolerance, and that is a decision rather than an omission.

- **A tuned tolerance would be a second tolerance.** The project has exactly one
  (§11), it is about comparing *money*, and a rate is not money. Introducing a separate
  convergence bound would be the first of the twenty local tolerances the single-tolerance
  rule exists to prevent.
- **There is nothing to trade off.** Sixty iterations of a two-line loop over ten cash
  flows is free. A stopping rule tuned for speed would buy nothing and would need
  justifying every time the number of flows changed.
- **Float collapse is a property of the arithmetic, not a parameter.** It is the same on
  every platform, which matters here more than it usually does: the determinism digest
  (§12) asserts bit-identity, so a stopping rule that depended on a configured value would
  make the digest depend on it too.

### 3.4 It is computed from a **policy-free** event stream

This is the subtlety most worth understanding about this figure.

A contractual yield to maturity is a property of the paper and the price. What the owner
does with the coupons — hold them as cash, reinvest them — is a decision about the
*proceeds*, and it must not move a figure labelled "contractual".

So `nominal_ytm` is **not** computed from the ledger of the run. The engine regenerates a
second, independent event stream with the coupon policy forced to `hold_cash`, and takes
the contractual series from that. Taking it from the folded ledger instead would sweep in
the reinvestment purchases and the larger redemption, and the "contractual" yield would then
change when the owner changed their mind about coupons.

This has been wrong once already, in this repository, and is now asserted:
`tests/unit/test_contractual_yield_is_policy_invariant.py` exists so the regression cannot
come back quietly.

### 3.5 Worked example: issue A

The flows, with time in `act/365` years from 2026-01-15:

| date | years | amount (UAH) |
| --- | --- | --- |
| 2026-01-15 | 0.0 | −10 000.0 |
| 2026-07-15 | 181/365 = 0.4958904109589041 | +768.6301369863013 |
| 2027-01-15 | 365/365 = 1.0 | +781.3698630136987 |
| 2027-07-15 | 546/365 = 1.4958904109589042 | +768.6301369863013 |
| 2028-01-17 | 732/365 = 2.0054794520547947 | +781.3698630136987 |
| 2028-01-17 | 732/365 = 2.0054794520547947 | +10 000.0 |

The root is

```
nominal_ytm = 0.16058553778779106     i.e. 16.0586% per annum
```

and `NPV` at that rate is `1.8e-12` on a 10 000 UAH purchase — about `2e-16` relative,
which is float64's resolution and the sense in which the root has been found exactly.

**A sanity check you can do in your head.** Compounding the two actual half-year periods
gives

```
(1 + 0.155 × 181/365) × (1 + 0.155 × 184/365) − 1
  = 1.0768630136986301 × 1.0781369863013699 − 1
  = 0.16100584…      i.e. 16.1006%
```

The reported yield is **lower**, at 16.0586%. The difference is the business-day rule: the
last coupon and the whole principal arrive on Monday 2028-01-17 instead of Saturday
2028-01-15, so `years = 732/365` rather than `730/365`. Discounting the same money over two
extra days costs about **4.2 basis points**. Running the identical flows on the unadjusted
dates gives `0.16100776…`, which matches the hand-compounded figure to four decimal places.

That gap is the honest answer to "does the weekend matter?" — it does, by about four basis
points, and the figure says so rather than rounding it away.

---

## 4. The cash-flow-weighted return (`nominal_cash_flow_return`)

### 4.1 What it is

The same root-find, applied to a **different series**: every event the ledger actually
folded, net of every tax charge recorded, including the reinvestment purchases and the
larger redemption they produce.

```
nominal_cash_flow_return = the r for which  Σ ledger_amount_i / (1 + r) ** years_i = 0
```

It is the money-weighted (internal) rate of return on what the owner actually did. Where
the contractual yield answers *"what does this bond promise?"*, this answers *"what did this
holding earn me?"*

### 4.2 Why it is kept separate, and is not a substitute

Two figures, never one. They answer different questions and neither stands in for the other.

- The contractual yield is a property of the **paper and the price**. It does not move when
  the coupon policy changes, and it is gross of tax.
- The cash-flow-weighted return is a property of **what happened**. It moves with the coupon
  policy, with the timing of every flow, and with every tax charge.

A money-weighted return can be raised by putting more money in at a favourable moment,
which says nothing about the instrument. Quoting it as "the yield" would attribute the
owner's timing to the bond. Conversely, quoting the contractual yield as "the return"
ignores tax — and between two instruments where one is taxed at 0% and another at 23%, that
omission is the entire decision.

**Under an exempt class the two series are identical and the two figures agree.** For issue
A both come to `0.16058553778779106`. That agreement is *asserted* — see
`tests/golden/test_end_to_end_ovdp.py` — rather than assumed, and it is a fact about the
exemption, not about the code. The moment a taxed instrument arrives the two diverge, and
code that had only ever seen them equal would have picked whichever it happened to store.

Both figures are labelled **nominal**, and both are accompanied by
`HurdleRate.accounts_for`, which states in the output's own words that the figure is net of
*"tax on every taxable event over the holding's life"*.

---

## 5. Tax

No tax rate exists anywhere in the source code. Every rate arrives in a declared `TaxClass`
loaded from `data/tax/` as a **dated schedule**, each entry carrying its own citation,
retrieval date and verification date — and that holds for a rate of **zero** exactly as it
does for a non-zero one. How the entry in force is chosen, and what happens to an event the
schedule does not reach, is §25.

The one rule implemented is a flat rate on a stated base:

```
pit   = taxable_base × pit_rate
levy  = taxable_base × levy_rate
total = pit + levy
```

Four things about this are decisions, not arithmetic:

- **Two lines on two bases, never one blended rate.** The military levy is not a surcharge
  folded into PIT. Both rates are zero today, so adding them would give the same total —
  and would make the two unrecoverable tomorrow, when a foreign withholding credit applies
  against PIT and not against the levy.
- **The taxable base of a coupon is the coupon. The taxable base of a redemption is the
  realised gain**, not the principal returned. For a bond redeemed at par that gain is
  exactly zero; taxing the principal instead would tax the owner's own money back. The gain
  is taken in the **base currency** (UAH), because tax is assessed in UAH — the two coincide
  today and the choice is still made explicitly, because the day they differ (a position
  flat in dollars across a devaluation) the trade-currency figure would be the wrong number
  to tax.
- **Zero is a charge, not an absence.** Every taxable event gets a `TaxCharge`, including one
  whose base is zero and one whose rate is zero, and the charge carries the class's
  provenance. A zero charge that cites its exemption is the *evidence* the exemption was
  applied; a missing charge is indistinguishable from a rule that never ran. Issue A records
  **five** charges — four coupons and the redemption — all zero, and `total_tax` of 0.00 UAH
  is zero *because zeroes were recorded and summed*.
- **A missing rule is never read as an exemption.** An instrument referencing a tax class no
  file declares, or a class whose `applies_to` does not cover the income kind it was
  referenced for, is **reported** — at load time where possible, as a typed failure
  otherwise — and the holding is not projected. Treating the missing rule as an exemption is
  the single most expensive silent default available in this domain: it would flatter every
  after-tax figure by exactly the tax that was not charged.

The tax charge is dated on the date the income arrived, not on a settlement date. When the
liability is actually paid is a timing question this feature does not model, and dating the
charge to an invented payment date would put a fabricated date in the audit trail. The
charge records `charged_for_year` — the tax year the liability accrues to — which is the
fact a later feature needs.

A **negative** base (a realised loss) yields a negative charge, and is deliberately not
clamped to zero *by the rule*. Whether the loss is creditable against other income is a
loss-offset rule this feature does not model; a visible line computed as declared is the
honest way to say so, and a clamp would be a silent one.

⚙ **A fund disposal at a loss is the one place a base is floored, and it is not silent.**
Investment profit tax is charged on profit: a fund redemption that realises a loss has a
taxable base of **zero**, not a negative one, so the charge is exactly zero and never a
refund. The loss itself is not swallowed — `ExitLine.realised_loss` carries it as its own
figure with `carryforward_note` beside it saying that loss offset and carryforward are not
modelled here — and the zero base keeps the gain's provenance, so it still cites what it
was computed from. The flat-rate rule is unchanged; what changed is what the fund
projection hands it, and it hands it a figure with a named line beside it. See §26.

---

## 6. Lots: the pro-rata cost split and the exhausted-lot rule

Every acquisition opens a **lot**: units, an acquisition date, and the cost of the units
remaining, in both the trade currency and the base currency. A position keeps its own
running quantity and basis *beside* its lots, accumulated independently, so the
conservation invariants compare two separately maintained figures rather than a number
against itself.

### 6.1 Which lots a disposal consumes

The selection method is **configured, never defaulted** — `fifo` (oldest first) or `lifo`
(newest first). Both give a different, and both a correct, tax on the same trades, so
picking one silently is a whole class of wrong answers. An unrecognised name raises, naming
the alternatives. Average-cost and specific-lot selection are **not implemented**, and are
absent rather than approximated: an average-cost result computed as FIFO would be a wrong
tax figure that looked right.

Within a method, lots are ordered on `(acquired_on, lot_id)`. The tie-break on `lot_id`
matters: two lots acquired on the same date would otherwise be ordered by sort stability,
and the basis consumed — and therefore the tax — would depend on the order the collection
happened to be built in.

### 6.2 The pro-rata split

When a disposal takes only part of a lot:

```
fraction        = taken / lot.quantity
consumed_basis  = lot.cost × fraction
remaining_basis = lot.cost − consumed_basis        ← subtraction, not a second multiplication
```

The remainder is obtained by **subtracting** the consumed part, not by scaling the lot by
`1 − fraction`. The two are the same in algebra and not in float64: subtracting means the
two halves add back to the original **exactly**, so basis conservation does not depend on
two independent multiplications agreeing in their last bits.

### 6.3 The tolerance-exhausted-lot rule

A lot whose residual quantity after the take would be within the project tolerance is
consumed **whole**, and its **entire** cost is taken with it, rather than being split pro
rata.

```
exhausted = (lot.quantity − taken) ≤ TOLERANCE
if exhausted:  taken = lot.quantity ;  consumed_basis = lot.cost   (in full)
```

The reason is a basis-conservation gap. A lot left holding a residual within the tolerance
is dropped — a lot may not exist at zero, because an empty shell would keep an acquisition
date alive that holds nothing and would take its turn in the consumption order. If its cost
had been split pro rata, the residual's share, `cost × residual / quantity`, would stay in
the position's basis with **no lot to account for it**. On a large lot that is not a small
number.

So the tolerance is spent on the **quantity** and never on the **money**: a near-empty lot
is closed exactly, and the basis stays conserved.

Over-consumption — selling more than is held — **raises**. It is not an owner-facing
outcome the way an unaffordable purchase is: the event stream is generated by this engine
from a validated declaration, so a disposal exceeding the holding is a bug in the generator,
and a ledger that let it through would report a negative position and a basis that was
never paid.

### 6.4 The realised gain

```
realised_gain = proceeds − consumed_basis − allocated_fees
```

recorded in **both** currencies, with every term stored separately rather than only the
result — an identity is only assertable if both sides exist. A zero fee total is a real
value and is recorded as one: recording "no fee" as an absent field rather than a zero is
how a cost becomes invisible.

Fees are attributed to a disposal by a **stored** allocation, not by date adjacency. An
inferred pairing would be a guess dressed as an audit trail, and it would start lying the
first time two events shared a date.

For issue A: 10 units bought for 10 000.00 are redeemed for 10 000.00, with no fees, so the
realised gain is exactly 0.00 UAH — and it is recorded, and taxed at the declared zero rate,
rather than skipped.

---

## 7. Reinvestment

The coupon policy is a declared assumption with two implementations, and **no default**:
what happens to a coupon changes the answer, so a run has to state it.

- **`hold_cash`** — the coupon stays in the cash balance. Buys nothing. This is the
  contractual case by construction.
- **`reinvest`** — the coupon buys whole units at par on the coupon's payment date.

### 7.1 The arithmetic

```
increments   = coupon / (face_value × min_unit)
units_bought = floor(increments) × min_unit
spent        = units_bought × face_value
retained     = coupon − spent
```

A float guard sits on the floor: a ratio within the single project tolerance of a whole
number is treated as that whole number. An exact multiple can land a hair below itself in
binary floating point, and a bare `floor` would then throw away a whole unit the owner
could actually buy — a real unit lost to representation rather than to the minimum-unit
rule.

### 7.2 Why the price is par, and only par

**Par is the only defensible price here.** This feature declares exactly one yield — the
issue's own coupon rate — and has no yield curve. A unit bought at face value is the only
unit that earns exactly the declared rate, so face value is the only price at which "the
declared yield" is the yield actually obtained. Any other price would be a **market quote**,
and there is none to be had; inventing one would put a fabricated number in the middle of
the figure this project exists to produce. Pricing future purchases off a curve is named as
a later feature, not approximated by a guess.

### 7.3 Whole units only, and the remainder is retained

A fractional bond does not exist. The unspent remainder **stays in the cash balance** — it
is never discarded, never rounded away, and never spent on a fraction of a bond. Every
coupon reports the decision explicitly: the units bought, the money spent, the money
retained, and a plain-language reason. A coupon too small to buy anything is therefore a
*stated* outcome carrying its reason, not an absence a reader has to interpret.

Two further refusals, neither of them a property of the policy:

- **The final coupon is never reinvested.** It is paid on the maturity date, and a unit
  bought that day would be redeemed the same day — a round trip that never happened.
- **A reinvestment below the declared minimum ticket buys nothing.** A reinvestment is a
  purchase, and a purchase violating a declared constraint is reported rather than silently
  adjusted to fit. Buying anyway would execute a ticket the venue would refuse; rounding up
  would spend money the owner does not have.

### 7.4 It is sized on the **gross** coupon

An instrument does not know its tax: tax is charged downstream, and the whole point of that
ordering is that a tax rule cannot change the basis it is charged on. Under this feature's
exempt class gross and net coincide, so the distinction costs nothing today. Under a
**taxed** class it would not, and reinvesting the gross coupon would spend money that went
to the tax authority — which appears as a negative cash balance the ledger permits and
never clamps, rather than as a hidden error.

### 7.5 Worked example

Checked in as `tests/worked_examples/test_coupon_reinvestment.py`. Same terms as issue A,
but **100 units** bought at par (100 000.00 UAH) — at ten units the first coupon buys no
whole bond at all, so the interesting case needs a purchase whose coupon exceeds one face
value.

| # | accrual | units held | coupon (UAH) | units bought | spent | retained |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 181 d | 100 | `15 500 × 181/365` = 7 686.301369863 | 7 | 7 000.00 | 686.301369863 |
| 2 | 184 d | 107 | `16 585 × 184/365` = 8 360.657534247 | 8 | 8 000.00 | 360.657534247 |
| 3 | 181 d | 115 | `17 825 × 181/365` = 8 839.246575342 | 8 | 8 000.00 | 839.246575342 |
| 4 | 184 d | 123 | `19 065 × 184/365` = 9 610.849315068 | 0 (maturity) | 0.00 | 9 610.849315068 |

Each division is checkable on paper: `15 500 × 181 = 2 805 500` and
`365 × 7 686 = 2 805 390`, so the first coupon is `7 686 + 110/365`.

**Why the compounding is not a simple square.** The two half-years are 181 and 184 days, so
their growth factors differ: `1.0768630136986301 × 1.0781369863013699 = 1.1610058442484519`,
not `(1 + 0.155/2)² = 1.16005625`. Unrounded, 100 units would compound to 116.1005844 units
after two periods. Whole-unit reinvestment leaves **115** units and
`686.301369863 + 360.657534247 = 1 046.958904110` UAH of retained cash. That gap is the
price of the minimum-unit rule, and the point is that it is *retained* rather than lost.

Totals: coupons received 34 497.05479452055; reinvested 23 000.00; redemption
`123 × 1 000.00 = 123 000.00` on 2028-01-17; terminal cash
`−100 000 + 34 497.05479452055 − 23 000 + 123 000 = 34 497.05479452055`.

The terminal amount equalling the coupon total is not a coincidence: every unit was bought
at par and redeemed at par, so the 23 000.00 put back in came out again unchanged, and what
is left is exactly the interest.

Against the same purchase **held as cash**, four coupons on a flat 100 units come to
`15 500 × 730/365 = 31 000.00` exactly. So reinvestment is worth **3 497.05479452055 UAH**
on this purchase — and the *contractual yield is unchanged*, because reinvesting at par
buys more of the same bond. A reader who expected the rate to rise has misread what
reinvestment does; a reader who expected the amount not to rise has misread compounding.

---

## 8. The cash identity

For **each currency**, on **every date**:

```
inflows − outflows = balance
```

- `inflows` — the total of every positive amount recorded, as a non-negative figure.
- `outflows` — the total of every negative amount recorded, as a **positive magnitude**.
  Stored unsigned so the identity reads the way it is written; a signed total would make it
  `inflows + outflows = balance`, which is the same arithmetic and a worse thing to check.
- `balance` — the accumulated signed net.

All three are accumulated **separately, from the same events**, so the identity compares
three independently maintained numbers. A balance alone would satisfy it trivially: it would
prove that one loop ran.

It holds on every date and not merely at the end. An error that cancels out by maturity — a
coupon credited a day late, a purchase settled a day early — leaves the closing balance
correct and every intermediate balance wrong, so the ledger produces one end-of-day snapshot
per date and the invariant is checked against each. Exactly zero is neither an inflow nor an
outflow, and a zero-amount event is **not** dropped: it stays in the ledger and stays
traceable, which is how a zero tax charge remains visible as a charge rather than becoming
an absence.

**There is no total across currencies, and nowhere to put one.** A single "cash" figure
spanning UAH and USD would conflate two of the three currency roles, and it is unreachable
by construction: adding money of two different currencies raises.

**The balance may go negative, and is never clamped.** No cash deposit funds the purchase in
this feature, because the spec takes the purchase as given and inventing a funding event
would require attributing it to a cause the event vocabulary does not have. So issue A's UAH
balance is **−10 000.00 from 2026-01-15 until the first coupon**, and recovers to +3 100.00
by maturity. An overdraft is a *feasibility* question about a plan — it belongs with the
minimum tickets and the lock-ups, not in the ledger. Clamping it here would make the figures
balance and the plan a fiction.

For issue A, at maturity: `inflows 13 100.00 − outflows 10 000.00 = balance 3 100.00 UAH`.

---

## 9. The percent → fraction boundary

Declaration files state rates as **percent**, in a field whose name ends in `_pct`:
`coupon_rate_pct = 15.5`, `pit_rate_pct = 0.0`.

The core works exclusively in **fractions**: `0.155`, never `15.5`.

The conversion happens in exactly one function, `loader._as_fraction`, and

> **`loader._as_fraction` is the only division by 100 in the project.**

That is a checkable claim, not a convention: every `_pct` field passes through it and no
other code performs the conversion. It matters because doing it twice and not doing it at
all are the two likeliest bugs in the data layer, and **both are invisible in the output** —
a 15.5% coupon read as 0.155% still produces a plausible-looking schedule, just one that is
a hundredfold wrong.

The two halves of the guard are the naming convention (`_pct` in files, bare fractions in
the core, and rate records that document the unit on the field) and the single conversion
site.

---

## 10. Provenance: how a figure traces back to where it was declared

### 10.1 The `SourceRef` id scheme

Each sourced table in a declaration file becomes **one** `SourceRef`, whose id is

```
directory/file#table
```

for example

```
instruments/ovdp_synthetic_a.toml#instrument.terms
instruments/ovdp_synthetic_a.toml#instrument.constraints
tax/ua.toml#jurisdiction.tax_class[ua_government_bond]
```

- The **parent directory** is included because `instruments/ua.toml` and `tax/ua.toml` are
  different facts and the bare file name would collide.
- The **absolute path is deliberately not used.** It would embed one machine's directory
  layout in a source id, so two checkouts of the same commit would describe the same
  declaration differently — and two manifests of the same run would not compare.
- **Per table, not per file.** Two tables in one file are two observations and get two refs.
  Merging them would let a verified minimum ticket vouch for an unverified yield.

Each ref carries `citation` (required non-empty), `retrieved_on` (required) and
`verified_on` (required to be *present*, permitted to be *empty*). An empty `verified_on`
means "nobody has checked this against a primary source" — a recorded state rather than an
oversight, which is why the key may not simply be absent.

### 10.2 How the mark propagates

Provenance is a **set** of source refs, and merging is set union: associative, commutative,
with the empty set as identity. Because it is commutative, evaluation order can never
change a mark — otherwise the mark would become a fact about the code path rather than about
the data.

Every function that combines money unions its operands' provenance, and those functions are
the **only** way to combine money. So there is no way to add two amounts and forget to carry
the mark. Nothing anywhere removes a source, which makes the mark **monotone**: a figure's
provenance grows as it is derived and never shrinks.

**One** unverified source marks the whole figure. A figure is only as trustworthy as its
least-trustworthy input; marking only when *every* input is unverified would let a single
invented number hide behind a crowd of cited ones.

`Money` provenance is excluded from *equality* (two amounts equal in value are equal
regardless of how they were reached) but never from *propagation*.

### 10.3 Following the trail

To check where a figure came from:

1. `HurdleRate.provenance` — the union of every source behind every amount that fed the
   figure. `is_unverified` is true while any of them lacks a verification date.
2. `unverified_sources` names the specific refs responsible for the mark, so the mark can
   say **why**.
3. Each ref's id names the file and table; open it and read the citation, the retrieval date
   and the verification date.
4. Below the figure, the ledger: every reported number resolves to a ledger event, and every
   event carries a `caused_by` reference — the instrument term or the tax rule that produced
   it, with a prose detail stating the arithmetic. The golden artefact in `tests/golden/`
   prints all of them; a sample line reads

   > `coupon at 0.155 per annum on 10.0 unit(s) accrued 2027-07-15 to 2028-01-15 on
   > 'act/365', paid 2028-01-17 under the 'following' rule`

5. The run manifest records the inputs and their versions — each declaration file's name and
   the SHA-256 of its bytes — plus the roll-up of unverified source ids. A file version is
   the digest of the file rather than a hand-maintained number, because a hand-maintained
   version is one somebody has to remember to bump.

**For every figure this tool currently produces, step 2 returns a non-empty answer.** The
synthetic terms and the unverified tax citation both mark the result. That is the honest
state of affairs, not a defect to work around.

---

## 11. The tolerance policy

### 11.1 One constant

```python
TOLERANCE = 1e-9  # applied as BOTH a relative and an absolute bound
```

defined in `terezy.core.primitives.tolerance` and imported everywhere. It is the only
tolerance in the project.

### 11.2 What it is for

Money is `float64`. So the specification's *"reproduces a hand-computed schedule exactly"*
cannot be taken literally: a schedule accumulated in binary floating point and the same
schedule worked out on paper differ in the last bits.

Issue A's first coupon is the concrete case. Worked out by hand as `1 550.00 × 181 / 365`
the answer is

```
768.6301369863014
```

The engine evaluates `face × (rate × fraction × units)` = `1000 × (0.155 × (181/365) × 10)`,
which is

```
768.6301369863013
```

Same money, different last bit, because floating-point multiplication is not associative.
**The tolerance is the width of that irreducible gap, and nothing else.**

It is not slack for a modelling disagreement. A comparison that passes only because the
tolerance absorbed a real difference is a defect wearing a green tick.

The bound is applied as both relative and absolute. Relative alone would be uselessly tight
near zero — a balance that should be zero and lands on `1e-17` would fail. Absolute alone
would be uselessly loose on large balances relative to small ones. On a balance of one
million hryvnia the bound is `1e6 × 1e-9 = 0.001` UAH: a tenth of a kopiyka —
indistinguishable from exact for a decision, and nowhere near loose enough to hide a
modelling error.

Money comparisons go through `assert_money_close`, which checks the **currency** as well as
the amount. Comparing bare amounts would let a UAH figure match a USD one whose number
happened to agree — a currency conflation dressed as a passing tolerance check.

### 11.3 Where a looser bound is legitimately used

Exactly two places, both in tests, both stated as loose at the assertion site rather than
dressed up as the project tolerance. The mechanism is deliberately noisy — a bound written
into the diff, next to a justification — which is why `pytest.approx`, `math.isclose` with a
bound of one's own, and a bare numeric literal used as a bound are all forbidden.

1. **`tests/contract/test_data_only_extensibility.py:266` — `< 0.01`.**
   Issue B's yield is checked against `(1 + 0.1225/4)⁴ − 1`, the naively compounded quarterly
   coupon. *Reason stated:* the internal rate of return measures time in 30/360 years from
   the purchase date, so it is *close* to the compounded coupon and need not equal it. This
   is a sanity band asserting the figure is in the right place; a wrong day count or a
   doubled percent conversion would miss by far more than a percentage point.

2. **`tests/unit/test_policies_differ.py:180` — `< 1e-4`.**
   The cash-flow-weighted return must *move* between the reinvesting and cash-holding
   policies, but only slightly. *Reason stated:* reinvesting at par should barely shift a
   money-weighted return, so this is a sanity band, not a definition of the figure. The
   companion assertion in the same test — that the *contractual* yield does **not** move —
   uses the project tolerance, because there the claim is exact.

Neither is a comparison of money against hand arithmetic. Both are bounds on how far a
derived *rate* may sit from an independently reasoned approximation, which is a different
kind of claim, and saying so out loud is the price of using a different number.

---

## 12. The determinism digest

The same code on the same inputs must produce the same bits. That claim is made checkable
by reducing a whole projection to a digest.

### 12.1 The canonical form

`core.results.canonical.of_projection` renders a projection — the folded ledger, the
schedule, every tax charge and the figures — as nested tuples of `str`, `int` and `None`.
Note what is *not* in that union: `float`.

- **Amounts are `float.hex()`**, exact and round-trippable. So the digest asserts
  **bit-identity** of every amount rather than agreement to some number of decimals.
- **Dates are integer triples**, `(2026, 8, 21)`, not ISO strings — same information, no
  string formatting anywhere in the core.
- **Money carries its currency**, `(hex, "UAH")`. Two identical amounts in different
  currencies are different facts.
- **Mappings are emitted sorted by key** and **frozensets sorted**, so the form is a
  function of the content alone and not of a dict's insertion order or a set's per-process
  iteration order.
- **Causation detail strings are included**, prose and all. They are part of what the audit
  trail *says*, so changing one changes the result a reader is given.
- **The lot order inside a position is *not* normalised.** It is a fact about the history and
  the selection method depends on it, so a form that sorted it away could digest two
  positions identically that would be taxed differently.
- **The capacity accumulator is included**, keys sorted by `(pool, year, month)`. It is
  derived from the events, exactly as the cash balances are, and both are claims the state
  makes about them — a form recording only a fold's inputs would agree between a right fold and
  a wrong one.
- **Provenance is deliberately excluded.** See §12.4.

### 12.2 The encoding

`data.manifest.encode` turns that structure into bytes with a self-delimiting, type-tagged
scheme written by hand:

| value | bytes |
| --- | --- |
| `None` | `n;` |
| integer | `i<decimal>;` |
| string | `s<byte length>:<utf-8 bytes>;` |
| tuple | `t<element count>:<encoded elements>;` |

prefixed with the scheme's name, `terezy-canonical-v3`, and a NUL byte. The version in the
name moves whenever the canonical structure of §12.1 changes shape, so a digest recorded under
one shape can never silently disagree with one taken under another: they visibly belong to
different schemes.

| version | what changed |
| --- | --- |
| v1 | the original structure |
| v2 | the event gained `capacity_pool`; the ledger gained the capacity accumulator |
| v3 | the real-terms slot became **two** tagged figures, each carrying its basis, the series it is real against and its window (§27.5) |

A pinned shape fingerprint in `tests/unit/test_results_canonical.py` fails the build if the
shape moves while the name does not, because a pin over one component leaves the rest free to
move under an unchanged name — which is the v1→v2 failure it exists to prevent. What it covers,
and what it does not yet cover, is recorded there rather than restated here: the pin and the
sentence describing it would otherwise be two facts, and the copy is what drifts.

Bumping the name moves **every** digest taken under it, including
`tests/golden/ramp_comparison.golden.txt`, whose ranking did not change. That is the cost of
one scheme name for the whole project, and it is the intended behaviour: the alternative is a
digest that silently means something else.

**Why it is injective.** Every string carries its byte length and every tuple its element
count, so no two different structures can produce the same bytes:

- `("a", "b")` cannot collide with `("ab",)` — the lengths and counts differ;
- `()` cannot collide with `((),)` — the element count differs;
- `"1"` cannot collide with `1` — the type tag differs.

That injectivity is the whole value of the digest. A collision is not a hash accident: it is
two genuinely different results reported as one. `repr` would be shorter and is not
injective in any documented way; `json` would work and is rejected because it would silently
accept a `float` and choose its own rendering.

Booleans are **refused at runtime**, even though the type does not admit one, because `bool`
is a subclass of `int` in Python and `True` would encode exactly as `1` — a silent collision
between a flag and a count is the precise class of confusion a digest exists to rule out.

The scheme name is part of the encoded bytes, so a digest names the scheme it was taken
under. Without that, changing the encoding would silently invalidate every digest ever
recorded and an older manifest would look like a run that produced different numbers.

The digest itself is `sha256:<hex>` — self-describing, so a stored digest cannot be compared
against one taken with a different algorithm by accident.

Issue A's recorded digest, at the time of writing:

```
sha256:830c330d278ad017205c138559ee7266fbd36c1406543259ea33b7baf1e466c7
```

It is checked in at the foot of `tests/golden/ovdp_synthetic_a.golden.txt`, beside a
readable rendering of the same projection, so that a change to it can be reviewed as a diff
rather than as a changed hash.

### 12.3 Why bit-identity is deliberately stricter than the tolerance

These are two different claims and conflating them would destroy both.

- The **tolerance** exists because hand-computed arithmetic and float arithmetic differ
  (§11.2). It is a statement about comparing a computed figure with an independently derived
  one.
- **Determinism** means the same code on the same inputs produces the same bits. There is no
  irreducible gap to accommodate: any difference at all is a bug.

A digest taken over a rounded rendering would mask any nondeterminism smaller than the
rounding unit — precisely the bug the digest exists to find. So nothing in the digest path
imports the tolerance and nothing in it rounds.

The two are asserted to be different: a test constructs two projections the tolerance calls
equal and shows their digests differ.

There is a related reason the digest is taken in the *data* layer rather than in the core:
hashing implies serialisation, and `hashlib` is on the core's forbidden-import list. What
stays in the core is the part that has to be a domain decision — *which* facts identify a
result, and *how* each is rendered unambiguously. The encoding makes no judgement about what
belongs in it.

### 12.4 Why provenance is excluded, and where the mark is kept instead

Provenance identifies **sources**. If a source's `verified_on` were filled in later, a
digest that covered provenance would change even though **no computed amount moved** — so
the determinism check would fail on a documentation update, and the only available fix would
be to stop trusting it. That is the failure mode the exclusion prevents.

The fact is not thereby lost. The unverified mark is a **separate claim**, asserted
separately: the run manifest records every unverified source id, per input file and as a
roll-up over the figure's own provenance, and a dedicated test suite asserts that every
figure derived from an unverified input carries the mark.

The division of labour: **the digest answers "is this the same arithmetic?"; the manifest
answers "what did it rest on?"**

For the same reason the golden artefact excludes provenance, and asserts that it does:
running the identical projection with every source verified produces a byte-identical file.

---

## 13. Deployable capacity: what a stream can actually fund

### 13.1 The formula

```
gross   = the credited amount, in the tax currency  (§32.2)
charged = what the named taxation scheme charges on it, line by line  (§32.1)
net     = gross − charged
```

`gross` is what an income stream declares arriving per its declared cadence, struck into the
tax currency where it arrived in another one. `charged` is the sum of the scheme's component
lines, never a blended percentage. Implemented as `deployable(stream, charged)` in
`terezy.core.streams.capacity`.

This exists for one reason: **the amount available to invest must never be overstated**
(002 FR-007). Every funding decision downstream reads the net figure, so no other module has
to remember to apply the scheme — which is how a gross amount comes to be treated as
investable.

**Feature 012 replaced a rate with a scheme.** `IncomeStream.income_tax_rate: float | None`
was retired: a scalar cannot carry two components with different commencement dates, an
obligation triggered by a month elapsing rather than by income arriving, or the choice of a
whole scheme. A stream names a declared treatment instead, exactly as feature 006's
instruments name tax classes.

### 13.2 An undeclared treatment produces no net figure at all

The treatment is optional, and omitting it means **the owner has not named one**. That is a
different claim from a scheme that charges nothing, and the two get different types:

| declaration | result | net figure |
| --- | --- | --- |
| `tax_scheme = "ua_fop_group_3_non_vat"` | `DeployableCapacity` | `gross − charged` |
| a scheme whose components come to nothing | `DeployableCapacity` | exactly `gross` — because a declaration says so |
| omitted (`None`) | `TaxTreatmentUndeclared` | **none: the record has no such field** |

Returning the gross in the third case would produce a net figure that quietly equals the
gross — right whenever the charge happens to be nil, wrong by the charge the rest of the
time, and with nothing in the output to say which case a reader is looking at. So the third
case is a typed value carrying the gross, the stream id and the reason *"no tax treatment
declared"*, and carrying no net field for a caller to read. Same shape, and the same
argument, as `RealTermsUnavailable` occupying the real-terms slot and `ExitCostUnknown`
occupying the round-trip slot.

**A charge and a declaration that disagree raise.** Supplying a charge for a stream that
names no treatment, or omitting one for a stream that does, is a programmer error rather than
a case with a default — both available defaults are wrong, one reporting a capacity the
declaration does not support and the other reporting *nobody said* about a stream that did.

**Nothing is clamped.** A declared rate above 1.0 produces a negative net figure and is
reported as such; a range check belongs to the loader, where the error can name the file and
the field. Softening a mis-entered declaration into a plausible zero is predecessor defect
B13 in a new place.

### 13.3 All three figures are in the tax currency, and they had to be

The identity cannot hold across two currencies: the arrival may be in dollars and the charge
is in hryvnia, and `money.sub` raises rather than pretending otherwise. Both ways of forcing
it into the stream's own currency are forbidden, in opposite directions:

- converting the hryvnia charge back at the **official** rate is an official rate pricing a
  realised amount (011 FR-012, §30.1);
- putting it through the **sale channel** is a channel rate deciding a tax figure (§32.7).

So `gross`, `charged` and `net` are all in the tax currency, the foreign arrival that
produced them is on the conversion record beside them (`charge.conversion.amount`), and the
number that is *not* claimed — how many dollars are left — is not claimed at all.

**Where the legal rates went.** A stream carries no `source`/`retrieved_on`/`verified_on`,
and that exemption is argued for an owner's statement about himself. It never covered a tax
*rate*, which is a public legal fact about the Republic — and the retired scalar let one be
written into per-owner data uncited. After 012 the owner declares *which regime he is in* and
the regime's rates live in `data/tax/schemes/` with their citations, where the provenance
gate reads them. There is consequently no arithmetic left in this module that applies a
declared rate: the charge arrives already computed, its lines already carrying the citations
of the entries that produced them, and `deployable` does one subtraction whose `money.sub`
unions both sides' provenance.

### 13.4 Worked example

An invented gross of 100 000 UAH monthly under an invented scheme charging one component at
10% — round numbers chosen to be checkable by eye and deliberately unlike any real Ukrainian
schedule, because this project may not enter a legal rate it has not observed:

```
gross   = 100 000.00 UAH  per month
charged = 100 000 × 0.1 =  10 000.00 UAH
net     = 100 000 − 10 000 = 90 000.00 UAH  per month
```

Checked in `tests/unit/test_deployable_capacity.py`.

---

## 14. Monthly capacity: whose limit it is, and what happens to the excess

### 14.1 The limit belongs to a rail, not to a route

A monthly cap is a property of the **rail** the money crosses — a card, an account, a corridor
under a regulatory ceiling — and a route is a path that *uses* rails. So a leg declares

```toml
capacity_pool = "monobank_card_uah_usd"
monthly_cap   = 100000.0
```

and consumed capacity is accumulated by `(capacity_pool, year, month)`. **Never by route.** Two
different routes both moving money through the owner's Monobank card consume **one** limit;
keying on the route would give each its own full monthly allowance, and Monobank's monthly limit
is one of the four figures `SIMULATOR_SPEC.md` §11 item 1 names as the reason this feature
exists.

Two legs naming one pool must declare the **same** cap. Two numbers for one real limit means at
least one is wrong, and choosing either silently would be a guess. A cap declared with **no**
pool is refused rather than given an invented key: without a rail there is nothing to accumulate
against, so capacity consumed earlier in the month could never reduce it.

### 14.2 No clock

The month comes from a date that arrives as data — a ledger event's `occurred_on`, or the
`on_date` a plan is dated. `datetime.now` is blocked in `core` by `.importlinter`. Consumed
capacity is one more accumulator in the fold that already accumulates cash per currency:

```
LedgerState.capacity : {(pool, year, month) -> Money}
headroom             = cap − consumed(pool, month)
```

An **absent** key means that rail carried nothing that month, which is a different claim from a
zero — so `consumed` returns `None` and the full declared cap is the honest headroom.

The headroom is **not floored at zero**. A rail already over its cap reports a negative figure,
because a floor would hide an overrun some earlier movement caused.

### 14.3 What the cap does *not* do

A cap does not make a route unusable. It makes the route unable to carry the whole amount **at
once**, and the answer to that is the fallback policy — not a refusal, which would deploy
nothing at all. So `cost_one` reports the declared ceiling and never consults the accumulator;
`routes.capacity.deploy` decides what fits.

### 14.4 The three fallbacks, and the fourth by name

Of `SIMULATOR_SPEC.md` §4.3.4's four policies this engine implements **hold as cash**,
**redirect** (to a named destination, which is a required field) and **skip**. All three deploy
the same amount — what the rail allows — and differ in what the record says became of the rest.

*Place on deposit* requires a deposit instrument, which no feature has yet added, so it **fails
by name** saying what it needs. Treating it as "hold as cash" would be a substituted default for
a policy the owner explicitly chose.

"Queue" in §4.3.4 is the same policy as *hold as cash* — §4.3.4's own wording is "queue as UAH
cash". It does **not** mean carrying the excess into next month's capacity: the next calendar
month starts from the full cap.

### 14.5 Worked example

Every figure invented; §11 item 1 records that none of the real route numbers has been observed.

```
declared cap on the card                        100 000 UAH
consumed in August 2026                               0
headroom                                        100 000

plan on 2026-08-21                              150 000
deployed = min(plan, headroom)                  100 000   <- the cap, never the plan
fallback = plan − deployed                       50 000   <- reported, with date and reason

after the movement, consumed in August          100 000
a second plan, on a DIFFERENT route, same card   80 000
headroom                                              0
deployed                                              0   <- one rail, one limit
fallback                                         80 000

occurrences reported                                  2
total deployed in August                        100 000 == the cap
```

Checked in `tests/worked_examples/test_monthly_cap.py`; the accumulator's properties in
`tests/invariants/test_capacity_accumulator.py`.

### 14.6 Executing a costed ramp

`cost_one` prices; `execute` records. `execute` takes the **costed figure** and nothing that
could price anything — no route, no leg, no channel, no amount — so there is no arithmetic in it
that could drift. It emits, from one `RampCost`:

1. the **departure**, `sent − components`, negative, in the sending currency, and the anchor the
   fee lines are allocated to;
2. **one fee line per fee-bearing component**, negative, in the sending currency;
3. the **arrival**, `one_way.arrived`, positive, in the destination currency.

The crossing is a pair because cash accounts are per *currency* and a conversion touches two of
them; expressing it as one event would need a rate, which is what FR-010 forbids leaving
implicit. The agreement

```
Σ(fee events)  ==  Σ(one_way.components)
```

is asserted in `tests/invariants/test_cost_execute_agreement.py`, together with the cash effect
per currency: the sending currency loses exactly `sent`, and the destination gains exactly
`arrived`.

The `capacity_pool` the movement crossed is named on the events denominated in the sending
currency, the fee lines included — the fees came out of the money that crossed, so what the rail
carried is the whole of `sent`.

---

## 15. Regimes: a belief about the future, kept apart from an observation

### 15.1 The two kinds of statement, and why they may not share a field

Two things can shut a corridor, and a report has to be able to say which:

| statement | where it lives | what it carries |
| --- | --- | --- |
| "this corridor closed in March 2025" — a **fact** | `Leg.available_from` / `Leg.available_until` | a source, a retrieval date, a verification date |
| "the war ends mid-2027" — an **assumption** | `RegimeTransition` in scenario data | `is_assumption`, a `rationale`, and no source at all |

Either could produce the same route set on a given date, and the arithmetic would agree to the
last float. What would be lost is the only thing that mattered: written into one field, a
corridor ruled out by a guess and one that genuinely closed appear in the *same shape* — a
`RouteUnusable` whose `binding_constraint` names a declared field — and no reader can tell them
apart. That is `SIMULATOR_SPEC.md` §1.3's distinction, and Principle I is the rule behind it.

So a regime carries **no `Provenance`**, and that is not an omission. Provenance marks an
observation; a belief has nothing to cite, and a fabricated source on one is the top-severity
defect. What a belief carries instead is a marker whose type admits one value —
`is_assumption: Literal[True]` — and the owner's reasoning in words. `data/scenarios/` is
exempt from the citation gate for exactly this reason.

### 15.2 The selection, and the boundary that is decided once

`routes_in_force(regimes, routes, *, transitions, on_date)` returns the routes the scenario
says exist on a date, the regime, the transition that decided it, and the ids it left out.

* **`on_date`, never `as_of`.** `on_date` is when the money moves; `as_of` decides staleness.
  The function has no `as_of` parameter at all, and there is no clock.
* **The transition date belongs to the regime *after* it.** "The war ends on the first of July"
  means the first of July is a day of peace, so the comparison is `on_date >= transition.on_date`.
  Decided in one place, because two comparisons written independently would eventually disagree
  by a day and the disagreement would be invisible.
* **A sequence, folded forward.** A chain of regimes is a sequence of transitions; the regime in
  force is the `after` of the last transition already passed, or the first transition's `before`
  if none has. This feature *declares* one transition, because a second needs a second
  assumption the owner has not stated.

### 15.3 How a regime and a leg window compose

In one direction only, and the order is the guarantee:

1. The regime decides which routes are **candidates**. `routes_in_force` narrows the route
   mapping, `paths_in_force` narrows the funding paths to match, and a route the regime rules
   out never reaches `cost_one` — so it never produces a `RouteUnusable`. What was left out is
   named in `RoutesInForce.excluded`, beside the transition responsible.
2. Each surviving candidate is then costed, and its legs' windows and limits decide whether it
   carries the money on the date — reported as a `RouteUnusable` naming the declared field.

An assumed exclusion therefore appears as a route the regime does not include; an observed one
as a binding constraint on a field with a source. The engine never learns what a regime is: no
module in `core/routes/` imports `core/scenarios/`, which is asserted rather than intended.

A regime is refused outright when it includes a route while excluding the exit route that route
declares as its partner. "There is a way in and none out" is a *fact* about a corridor — a route
declaring `partner_route = null` — so a one-directional regime is expressed as a separately
declared pair, not as half of an existing one (FR-027).

### 15.4 Worked example

Same origin venue, same destination venue, same hryvnia salary, same 10 000 UAH, same reference
rate of 42 out of the same channels mapping. The **only** difference is which corridor the
regime says exists:

```
wartime      P2P book, +3 / -3     price 45 in, 39 back
             in   10 000 / 45          =   222.222222 USD
             out    222.222222 x 39    = 8 666.666666 UAH
             round trip = 1 - 39/45    = 2/15  = 13.3333%    cost 1 333.333333 UAH

normalized   bank, +0.5 / -0.5     price 42.5 in, 41.5 back
             in   10 000 / 42.5        =   235.294117 USD
             out    235.294117 x 41.5  = 9 764.705882 UAH
             round trip = 1 - 41.5/42.5 = 2/85  =  2.3529%    cost   235.294117 UAH

the drop     2/15 - 2/85 = 34/255 - 6/255 = 28/255 = 10.9804%
             1 333.333333 - 235.294117    = 1 098.039215 UAH on 10 000
```

A round trip is what comes back over what went in, so the reference rate cancels out of both
fractions and `28/255` is exact rather than an artefact of the rate chosen. `on_date` moves
fourteen months across the transition while `as_of` does not move at all, so none of the drop is
a staleness artefact.

**1 098 UAH on 10 000 is what the assumption is worth**, and it is worth nothing more than the
assumption is. Checked in `tests/worked_examples/test_regime_transition.py`; the fact/assumption
separation itself in `tests/unit/test_transition_is_an_assumption.py`.

---

## 16. The ramp: what a declared premium actually costs

This is feature 002's headline arithmetic, and it is written out at length because the first
implementation of it was **wrong in a way that looked right**.

### 16.1 The two-sided channel, and why no mid-rate is ever transacted at

A channel is a named rate source with **two sides**, both declared, neither derived from the
other. A P2P book quotes one price to buy dollars and a lower one to sell them; a bank
publishes a markup each way. Computing the sell side from the buy side would be using a
mid-rate with extra steps, which is exactly what FR-010 forbids.

Two declaration forms, because the owner observes two different things:

* `markup_bps` — a **cost magnitude** in basis points, the form a bank publishes. Added on
  the buy side, subtracted on the sell side.
* `premium_per_unit` — a **signed offset** in base currency per unit, the form a P2P screen
  shows. Both sides are `reference + premium`, so a buy side paying 3 UAH over declares `+3`
  and a sell side giving up 2.5 declares `-2.5`. A **negative** buy-side premium is a
  discount and is legal; a **zero** one means the channel is at the reference; a **missing**
  one is refused, because absence and zero are different claims.

The rate actually transacted at:

```
effective_rate  =  reference + premium          (buy, premium form)
                =  reference + premium          (sell, premium form — the sign does the work)
                =  reference × (1 + bps/10000)  (buy, markup form)
                =  reference × (1 − bps/10000)  (sell, markup form)
```

### 16.2 The cost is `p/(r+p)` buying, and `p/r` is a different figure

Both are reported, and only one of them is the cost.

```
loss_fraction         =  1 − reference/effective   (buying)  =  p/(r+p)
                      =  1 − effective/reference   (selling) =  p/r
spread_over_reference =  |effective − reference| / reference  =  p/r
```

Worked, with a premium of +3 against a reference of 42, so the price is **45**:

```
send            10 000.00 UAH
arrive          10 000 / 45          =   222.222222… USD    ← what the venue hands over
worth at ref    222.2222 × 42        = 9 333.333333… UAH
the spread      10 000 − 9 333.33    =   666.666666… UAH
loss_fraction   666.667 / 10 000     = 0.066666…  = 3/45 = 6.67 %   ← the cost
spread/ref                             0.071428…  = 3/42 = 7.14 %   ← §4.3.1's figure
```

**Why both.** `SIMULATOR_SPEC.md` §4.3.1 quotes `p/r` — its "4.8–9.5% one way for +2 to +4"
is `2/42` to `4/42` and nothing else — so that figure has to stay reproducible or the output
loses its link to the claim that motivated the whole feature. But `p/r` is a fraction of a
**rate**, and a cost is a fraction of **money**. On the sell side the two coincide exactly
(`1 − (r−p)/r` is `p/r`); on the buy side they do not.

**The correction, recorded because the wrong version shipped.** FR-004 originally named `p/r`
as *the* cost, on the reading that §4.3.1 defined it. The first implementation charged `p/r`
of the amount and converted the remainder at the reference. That reproduced §4.3.1's
percentage exactly — and reported **221.09 USD arriving where the venue pays 222.22**, an
implied all-in price of `r/(1 − p/r) = 45.23` rather than 45. The arriving amount was wrong,
not merely differently framed, and no amount of internal consistency rescues a figure that
says the owner ends up with less money than he does. §4.3.1 labels its own arithmetic
illustrative — *"substitute the live rate; this is illustrative"* — so reading it as a
definition of cost was the error. The requirement was corrected rather than the arithmetic
bent to it.

### 16.3 Fees, and where the spread applies

Fees come off the amount entering a leg, in the sending currency; the **spread applies to
what is left**, because that is what was actually converted. Attributing it to the full
amount would double-count the fee-bearing slice.

```
10 000.00 UAH, 1 % fee, 50.00 fixed, premium +3
percentage fee  100.00        fixed fee  50.00
after fees      9 850.00
arrive          9 850 / 45   = 218.888889 USD
spread          9 850 × 3/45 = 656.666667 UAH
```

Cost components are a **closed set** — `conversion_spread`, `percentage_fee`, `fixed_fee` — so
a leg cannot hide a charge in an unnamed one, and their sum is checkable against the whole.
Nothing is clamped: if fees exceed the amount, the arriving figure goes to or below zero and
the fraction may exceed 1.0, which is reported rather than capped.

## 17. Round trip, and why it needs a declared exit

Round-trip cost comes from a **separately declared exit route**, never from reversing the way
in. Getting money back has its own chain, its own spreads and its own limits, and the way out
is not the way in run backwards.

For a single conversion each way it reduces to a ratio of the two prices:

```
round trip  =  1 − sell_price / buy_price
            =  1 − 39.0 / 45.0  =  6/45  =  13.33 %      (premia +3 / −3)
```

**It needs no reference rate as an input** — which is what makes it hand-checkable. It is
**not**, however, independent of the reference: the prices are `r ± p`, so the same premia
against a different reference give a different answer (10.98 % at 42, 14.90 % at 30, 8.54 %
at 55 for the war-end example in §15). What a formula does not *take* is not what its answer
does not *depend on*, and an earlier docstring here blurred exactly that.

**Conversions compound, they do not add.** A route crossing three times
(UAH→USD→UAH→USD at 45 / 39.5 / 45) costs 18.07 % one way, not three times 6.67 %.

**A destination whose exit nobody declared has no round-trip figure at all** — it is reported
as *exit cost unknown* and kept out of any ranking. That is the decision working, not a gap:
an asset that cannot be liquidated into spendable base currency at a knowable cost is not
comparison-ready, and promoting the one-way figure into its place would produce a confident
number for a path nobody has ever looked at.

## 18. Staleness: which date ages, and against what

Every observed value declares an **observation kind**, and every kind declares a
`staleness_days` threshold. A P2P premium ages in days; a published bank tariff in a year; a
regulatory limit when the regulator says so. One project-wide threshold would either cry wolf
on tariffs or stay silent on premia, and a staleness warning that is usually wrong is one that
gets ignored — worse than none. A kind with no declared threshold **fails at load**.

```
age      =  as_of − max(verified_on, retrieved_on)
is_stale =  age > kind.staleness_days
```

**The later of the two dates.** Verifying a value against a primary source is the strongest
refresh of confidence there is — stronger than re-fetching — so a value retrieved two years
ago and verified last week is not stale. The asymmetry is deliberate: an **unverified** value
ages from retrieval, which is every value in this project today and the stricter reading.

**`as_of` is an input, never a clock.** The core cannot read the time (`datetime.now` is
blocked by `.importlinter`), so the same inputs produce the same staleness verdicts forever.
It is a different date from `on_date`, which is when money moves and which selects the month
for a capacity limit; conflating them would make a projection into the future report every one
of its inputs as stale, by years.

## 19. Ranking: three keys in order, never combined

Routes are ranked **lexicographically** on `(round-trip cost, ceiling descending, latency)`.
A `None` ceiling sorts **first** — no declared cap is the least constrained a route can be, and
treating an absent cap as zero would rank the freest route last while looking like a sensible
default for a missing value.

**There is no composite score**, and that is a requirement rather than a preference: required
test **B12** forbids a non-standard score from driving the primary ordering, and a weighted
score would have to weight hryvnia against days — a *preference*, not a fact, and precisely the
kind of invented number this project refuses.

**A tie is decided on round-trip cost alone.** Two routes costing the same within the project
tolerance (§11) are reported as tied even where their ceilings or latencies differ: the owner
asked which is cheapest, and "these two cost the same, and here is how they differ" answers
that, while silently preferring one on a tiebreak he did not ask for does not. Tie grouping is
**anchored, not chained** — every member is within one tolerance of the group's first member —
because tolerance equality is not transitive and chaining would let an arbitrarily wide band
become one tie as candidates accumulate.

**Every candidate is costed by the same function as the recommendation**, and the
recommendation is an *index into the costed set* rather than a separate value. A comparison
whose alternatives were priced by a cheaper path than its winner is not a comparison; it is a
recommendation with decoration.

## 20. Comparison-readiness: what the coverage report claims

### 20.1 The rule, in plain language

A destination is **comparison-ready** when the declarations support both halves of the owner's
rule:

> Everything money can be moved into must have a declared way in AND a declared way out — at
> least through one other venue — before it may appear in any comparison.

Matching reads the **endpoints** of a route's chain — the first leg's currency in and the last
leg's currency out — and never its interior. Made checkable, per
`(destination × income stream × regime)`:

- **a way in** — at least one declared route with direction `inbound`, from the stream's arrival
  venue, whose first leg takes in the stream's arrival currency and whose last leg hands out the
  destination's currency. A destination that *is* the stream's arrival venue and currency needs
  no route: the money is born there, and the report says **satisfied by arrival**, which is
  explicitly not the same statement as "satisfied by a route";
- **a way out** — at least one declared route with direction `exit`, from the destination, whose
  last leg lands on a declared **spendable endpoint**. A destination that *is* a declared
  spendable endpoint needs no route: the money is already where it had to come back out to, and
  the report says **satisfied by identity** (owner decision, 2026-08-23). That is the mirror of
  *satisfied by arrival*, and it is reported as its own distinct sentinel for the same reason —
  "already out" is not the claim "a declared route gets it out".

The two route-free forms behave the same way in every consequence. Neither produces a deficit or
a to-do item for the half it satisfies; neither is a route, so neither can be closed and neither
contributes to `rests_on`; and each **supersedes** the routes it stands in for, so a spendable
destination's declared exits are not listed as relied upon. The first reading of the rule
required an exit route without exception, which made the hryvnia balance on the owner's own
salary rail a hole demanding an observation of how to get money out of his own bank account.

A **spendable endpoint** is a declared `(venue × currency)` pair: base currency only, at the
venues the owner actually spends from (`data/spendable/`). Not "UAH anywhere", and not foreign
cash in hand. An exit ending in hryvnia at a venue the list does not name does not get the money
out, exactly as one ending in dollars does not.

The **destination universe is derived**: every declared venue × every currency that venue
declares it can hold — including a venue that appears only as an interior leg endpoint, because
money can sit there too. That is what makes a venue with zero routes visible as a hole the moment
it is declared, rather than invisible until somebody tries to cost it.

### 20.2 The three deficits, and why they are three

They are kept apart because each calls for a **different observation**, and collapsing them into
one "missing route" would tell the owner to go and do the wrong thing:

| deficit | what is true | what to observe |
| --- | --- | --- |
| **no inbound route from this stream** | nothing declared carries this stream's money here | a way **in**, from the stream's arrival venue in its arrival currency |
| **no exit declared** | the destination is reachable and nothing leaves it | a way **out**, to any declared spendable endpoint |
| **exit does not reach a spendable endpoint** | a way out exists and lands somewhere unspendable | a way out **that lands on the list** — the corridor that exists is already observed |

The third carries the exits that *do* exist, so a reader can see that the corridor was looked at
and why it does not count. Without that it would read as the second, and the owner would go and
observe something he had already observed.

**A pair can carry two of them at once** — one on the inbound side and one on the exit side.
That matters for the count below: a destination missing both halves needs two observations, and
a report that listed only one would make the second invisible until the first had been made.

**Nothing is composed.** If a destination's exit lands at a venue that itself has a spendable
exit, a human sees a path home; the report does not, and says the exit does not reach a spendable
endpoint. Composing multi-route paths is deliberately a later feature, and it will arrive as a
distinct *"reachable by composition only"* annotation **beside** the verdict rather than as a
change to what comparison-ready means.

**Declaration, not availability.** A route declared but closed, or outside its window, still
counts as declared: the hole this report exists to surface is a corridor **nobody has observed**,
and the fix for a closed corridor is not an observation. What that leaves owing is discharged by
a `rests_on` field on every ready verdict — `open`, `constrained`, or `closed_only` — so a ready
verdict resting only on closed routes never looks like one resting on open routes.

### 20.3 The blocked-pair count — and why it is pairs, never hryvnia

For each missing declaration the report counts how many `(destination × stream)` pairs it blocks,
per regime, and orders the to-do list by that count descending. A declaration *blocks* a pair
when the pair is not comparison-ready and that declaration is among those required to make it so.

The count is a **plain count of pairs**. `count == len(blocked)`, with no weighting and no
composite score (required test **B12**). Equal counts are reported as a **tie** rather than
broken: the sequence is still ordered so the report is reproducible, but a position in it is not
a claim of precedence — the same separation `Ranking.ties` makes in §19. Where a pair needs two
declarations, both list it and both mark it **not alone sufficient**, so a necessary-but-not-
sufficient observation is never presented as if it would unlock the pair by itself.

**The count is pairs unblocked, and never hryvnia, and that boundary is deliberate.** The obvious
next question — *which observation is worth the most money?* — cannot be answered honestly here.
Valuing a corridor needs costing, and costing needs the very numbers the corridor has not been
observed for: the fee, the spread, the cap. Any figure the report produced would be a cost
computed over a registry that does not contain the observation — an invented number by
construction, and precisely the kind Principle I forbids. Counting what an observation unblocks
needs only declarations, which is why the report can do it at all.

For the same reason the report carries **no cost figure anywhere** — no percentage, no amount,
one way or round trip — and no provenance or staleness mark of its own. It contains no observed
value: the existence of a declaration is a fact about the registry, not an observation of the
world, and a summarized second copy of a provenance mark would drift from the authoritative one.
The guarantee is structural rather than editorial: no field reachable from the report can hold a
`Money`, a `Provenance`, a `StalenessVerdict` or a bare `float`, and a recursive walk over the
whole output asserts it. **This is why the coverage feature imports no tolerance** — there is no
float in it to compare within one.

**The same missing declaration in two regimes is one declaration**, with its count stated per
regime and never summed. Which observation to make is one decision; what it unlocks differs by
regime, and the owner weighs regimes — the tool supplies the per-regime facts and refuses to
weigh them for him.

### 20.4 Advisory, not binding — a dated gap

The verdict **informs and enforces nothing** (owner decision, 2026-08-22). Producing the report
changes no costing and no ranking output. So today a destination whose only exit is
non-spendable still appears in the round-trip ranking of §19 while this report says it should not
be compared.

That gap is deliberate, dated, and stated in the report's own output rather than only here, so a
reader of the artifact sees it. The owner's rule remains the destination: making it binding —
ranking excluding a destination with no spendable way out — is a recorded deferral to a later
feature, not a softer reading of the rule.

## 21. Composed paths: reaching a place nobody declared end to end

### 21.1 What a composed candidate is

A **composed candidate** is an ordered chain of declared routes whose venues, currencies,
directions and regime membership connect end to end, from a stream's arrival venue to a
destination. It exists only at query time: nothing is written back to the registry, nothing
persists between runs, and the registry stays the sole record of what has been observed.

The gap it closes grows with the registry. UAH salary → Binance is declared; Binance → IBKR is
declared; UAH salary → IBKR **via** Binance did not exist until somebody sat down and hand-wrote
the concatenation, and every new venue multiplies the concatenations nobody will write.

The shipped registry gained its first such chain on 2026-08-23, when the owner's contract income
was declared to arrive at Deel rather than at Coinbase. `deel_to_coinbase` is declared and
`coinbase_to_ibkr` is declared; **contract income → IBKR** is neither, and exists only as the
composition of the two. Nothing about the broker corridor changed — it is the arrival venue that
moved one hop upstream, and composition is what keeps the corridor reachable without anybody
writing a third file that duplicates the two.

Note what composition does **not** do: the coverage audit (§20) measures one declared hop from
where the money is and does not chain two, so it reports `(ibkr_usd, USD) × contract_usd` as
short a way in under both declared regimes even though a costable chain reaches it. The audit
answers *what has been declared*; composition answers *what can be costed today*. Reading either
as the other overstates one of them.

**A composed candidate is its own kind of candidate**, not a route with a joined id. Where a
declared route is a `FundingPath`, a chain is a `ComposedPath` carrying its segments in order, and
every ranking, report and recommendation shows it segment by segment with each segment naming the
declared route it *is*. So which comparisons rest on composition, and on which declarations, is
visible wherever a composed candidate appears.

### 21.2 Why every candidate is costed in full

There is **one** costing function, and a chain is not costed *like* a declared route — it is
costed by the same call. `legs_of` turns either kind of candidate into one sequence of legs,
renumbered once across the concatenation, and the existing fold walks that sequence unchanged. A
declared route is a chain of one, and that is not a special case anywhere in the code.

The rejected alternative is the obvious one: cost each segment and add the results. It is a second
arithmetic, and it is wrong in a way no reviewer would see — **the rounding of a sum of sums is
not the rounding of a single fold**, so the cost-attribution invariant would begin failing for
composed candidates only. Slow and honest beats fast and approximate: if enumeration within the
bound is slow, the honest levers are the bound and the registry, both data and both owner-visible.

Composition therefore adds **reach**, never new arithmetic. Provenance, staleness, capacity pools,
latency, status and per-leg disruption all behave exactly as they would on a declared route with
the same concatenated legs, because the fold never knew what a route was.

### 21.3 What a junction does not do

Two segments join only where the destination venue **and** the arriving currency of one equal the
origin venue **and** the departing currency of the next. A junction **converts nothing, charges
nothing and waits for nothing**.

Where the venue matches and the currency does not — one segment arrives in USDT, the next departs
in USD — the chain simply does not exist. It is never bridged by an implicit conversion, because
an implicit conversion is an invented leg at an invented rate. The corridor's absence is a fact
for the coverage report (§20), not something for this feature to paper over.

### 21.4 How the bound bounds reach, and why it is visible

The maximum number of segments in a candidate is **declared as data**, per owner, in
`data/composition/`. There is no default: a registry with no declared bound fails at load naming
the file and the field, by the rule that refuses a default staleness threshold (§18) — a forgotten
line must never read as a chosen policy. `max_segments = 1` means composition is **off**, only
declared routes are candidates, and that is a legal choice; `0` admits nothing at all and is
refused as a broken registry.

Within the bound, enumeration is **exhaustive**: every chain of connectable declared routes up to
that length is a candidate, and nothing is dropped, truncated or deferred without a recorded
reason. Nothing is pruned by cost — no shortest path, no admissible heuristic, no cache of partial
costs, because a partial cost is valid for **one amount only** (minimums, caps and fixed fees are
not linear) and a cache keyed by less than the whole amount would be an invented number the first
time it hit. There is no field anywhere in the feature for a path score, which is required test
**B12** made structural.

**The bound in force travels with the results.** Without it, a corridor needing four hops under a
bound of three is indistinguishable from a corridor nobody declared — and the owner's remedy for
those two is opposite: raise the bound, or write a declaration.

Two rules keep the search finite and honest beside the bound. **No candidate visits a venue
twice**, because venues are the nodes — even in a different currency; a genuinely useful
out-and-back corridor can still be hand-declared as one route, where its terms are observations
rather than search artefacts. And **directions never mix**: the adjacency index is built per
direction, so an inbound enumeration cannot see an exit route. What was observed one way says
nothing about the other way, and treating it as if it did would invent a corridor nobody observed.

**Enumeration order influences nothing.** Each adjacency bucket is sorted by route id and the
emitted candidates are sorted by `(segment count, route ids)`, so the order is a function of the
declarations rather than of dictionary iteration or file load order. Two candidates costing the
same within the project tolerance are a **tie** (§19), never resolved in favour of whichever the
search found first.

### 21.5 Attribution gains a segment axis

Cost is attributed twice over the same total: by **component** — conversion spread, percentage
fee, fixed fee — and by **segment**, one entry per declared route in the chain. Both mappings sum
to the same total within the project tolerance, so a leg cannot hide in either, and a reader can
say both *which term* dominates and *which hop* did.

The two axes are accumulated side by side from the same per-leg figures, never one from the
other. The whole-candidate totals keep the exact addition order feature 002 established, because
reconstructing a total from segment subtotals is the sum of sums §21.2 refuses.

### 21.6 There is no path-level disruption probability

Each leg reports its own declared probability, exactly as it does on a declared route, and the
candidate reports the **largest single leg's** figure — a lower bound, read as *at least this
likely*.

Nothing combines them, and there is **no field** for a combined figure. Compounding
`1 - Π(1 - pᵢ)` would require assuming the legs fail independently, and nobody has declared that.
The structural refusal is worth more than a comment here, because the comment is what gets deleted
by the next contributor who "just needs a single number for the ranking".

### 21.7 What a chain's status reports

A composed candidate's `status` is the **most constrained** status any of its segments declares:
`constrained` if any one is, `open` only if all of them are. A chain is no more usable than its
tightest link, and taking the first segment's status or the last would let a constrained corridor
hide behind an open one — in the field a reader scans to decide whether to trust the figure
beside it. It is the shape the other whole-chain figures already take: the `ceiling` is the
tightest declared cap and the disruption probability the largest single leg.

A `closed` segment never reaches the figure at all: the candidate is excluded with the binding
**segment** named, so a reader of a three-hop chain knows which declaration to open.

**It describes the way in only, and that is a stated gap.** A constrained *exit* segment leaves
the status `open` on a record whose headline number is the round trip. Widening it would change
what the field means for every declared route that already carries one, so the honest fix is a
second field for the way out rather than a quiet redefinition of this one. A **closed** exit
segment is unaffected either way — it produces *exit cost unknown* naming the route, so the
round-trip slot says so in words.

### 21.8 The seam between the way in and the way out

A round trip is **one** journey, so the exit chain is anchored at both ends: it departs from the
venue the inbound chain arrived at, in the currency it arrived in, and it ends at a declared
spendable endpoint.

Neither anchor is decoration. Without the first, an exit chain belonging to one destination can
be paired with a way in to another and walked as though the two met — the money crosses a
junction nobody declared, for free, and what comes out is a coherent-looking round trip over two
unrelated journeys. Without the second, a round trip can "complete" while the money is still
sitting in dollars at an exchange, and the record then carries an arriving amount in one currency
beside a cost fraction computed in another: two figures describing different things.

Feature 002 enforced both at load for a declared `partner_route`. They are enforced again here
because a chain assembled at query time never met the loader, and because the search that would
only ever emit a well-anchored chain is not the only way one arrives.

### 21.9 The way out, in three shapes

A round trip exists when there is a way out, and there are exactly three ways there can be one:

* **a declared exit route** — feature 002's single `partner_route`, unchanged;
* **a chain of declared exit routes** — the owner's decision of 2026-08-22: a chain *satisfies*
  the "separately declared exit route" requirement, because every link of it **is** an
  observation. In 002 the danger was a round-trip figure resting on an exit nobody had looked at,
  namely the inbound route reversed; composing declared exit segments invents nothing, and it is
  the mechanism that makes *"a way out, at least through one other venue"* real;
* **exit by identity** — the destination **is** a declared spendable endpoint, so the money is
  already where it needed to come back out to.

The exit chain is **part of the candidate's identity**. A round-trip figure is keyed per
`(destination × stream × inbound path × exit chain)`, so two exit chains from one destination are
two figures in one ranking, each reported, never blended — and when they agree within the
tolerance they tie, under the same rule as everything else. The alternative shape, one record
holding several round-trip figures, has no defined position in an ordering by round-trip cost, and
picking one to order by is the blend arrived at by accident.

**Exit by identity is a distinct value, never a zero-length chain, and never a promoted one-way
figure.** A round trip that costs nothing *because there is nothing to do* is a different claim
from one whose fees happened to cancel, and only a named value carries the difference. The
round-trip figure equals the one-way figure there — not because a way out was assumed free, but
because there is no way out left to travel.

⚙ **This closes a recorded disagreement.** Feature 003's coverage audit calls a spendable
destination ready by identity, while 002's costing required a declared partner and refused it —
the disagreement 003's own FR-018 says must not exist, recorded in `specs/features.toml` as
`identity-exit-vs-partner-requirement` and naming composition as the thing that would make it
real. The sentinel is that resolution, and the entry comes off the future list with this feature.

**The identity case is derived, not opted into.** Costing reads the same declared spendable
list the coverage report reads, and where the destination is on it the sentinel is the way out —
without a caller passing anything. That is what closes the disagreement rather than merely making
it closable: a reconciliation only a caller can opt into leaves the recorded violation exactly
where it was, because no caller opts in. Identity also **supersedes** a declared partner, which is
the reading feature 003 already took: where the money is already spendable, a further declared hop
is a journey the owner has no reason to make.

**Where nothing chains, the gap stands.** A destination from which no declared exit segments reach
a spendable endpoint still reports *exit cost unknown*, stays out of the round-trip ranking, and
has its one-way figure reported in a field named one way. "Most of the cost" is not the cost.
## 22. Diagrams: the one number rule, and what a mark on a picture claims

Feature 005 renders two things as Mermaid text: the declared route graph for one named regime,
and the path of one costed result. Both are derived — nothing in either is hand-maintained —
and both must be **as honest as the numbers**, because the picture travels further than the
tables. It gets pasted into reports and read by people who never open the TOML.

### 22.1 The number-rendering rule — there is exactly one

Every figure on every diagram is rendered by
`terezy.api.diagrams.numbers`, and by nothing else:

| what | how it renders | example |
| --- | --- | --- |
| a fraction, as a percentage | fixed **two** decimals, then `%` | `0.0666…` → `6.67%` |
| an amount of money | fixed **two** decimals, then the currency **code** | `1234.5678 UAH` → `1234.57 UAH` |
| a quoted rate | fixed two decimals, both currencies named | `42.0` → `42.00 UAH per USD` |
| a premium per unit | fixed two decimals, **always signed** | `+3.00 UAH per USD`, `-2.50 UAH per USD` |
| a markup in basis points | fixed two decimals, in the unit declared | `150.0` → `150.00 bps` |

A rendered premium always names **which side** the leg takes and **which way** the quote is
applied: `(buy side) 150.00 bps, applied above the reference 42.00 UAH per USD`. That is not
decoration. The two declared forms have different sign conventions — `premium_per_unit` is a
signed offset that both sides add, while `markup_bps` is a *cost magnitude* the engine adds on
the buy side and subtracts on the sell side (§16.1). So the identical declared `150.0`
describes an edge charging +1.5% and an edge charging −1.5%, and the number alone renders the
two the same way and the sell side backwards. The direction phrase is taken from
`channels.effective_rate` itself, so the picture and the arithmetic cannot disagree; the
effective rate is *not* rendered, because it is computed rather than declared and FR-008
allows the diagram no figure its input does not carry.

Two decimals, **one** private helper, and all five public functions go through it. This is the
single-tolerance discipline of §11 applied to formatting: defined in one place, imported
everywhere, and a second rule for the same kind of quantity is a **defect** rather than a
preference. `tests/contract/test_diagram_one_number_rule.py` greps the whole `api.diagrams`
package for a second one — `:.2f`, `round(`, `format(`, `%.2f`, `Decimal` — and proves the grep
can fail.

**One rule per kind of quantity, not one function.** A signed offset per unit of another
currency is not an amount of money — it carries a second currency and a mandatory sign — and
basis points are not a percentage. Each gets its own rule in the one module rather than a `+`
prepended or a `/10000` performed at a call site. The sign on a premium is the whole content:
`+3` on the buy side and `-2.5` on the sell side are what make the P2P round trip cost 12.22%,
and two unsigned figures read as two costs of the same shape. `+0.00` means *at the reference*,
which is a declaration the schema accepts and the rendering must not hide.

**Why the rule had to exist at all.** Results carry `float`, and this project's canonical float
form is hexadecimal (§12.2), chosen because determinism means bit-identity. So "the diagram
shows the result's figure" was undefined until a human-readable decimal form was named. That
gap was found on external review and closed by naming this rule rather than by softening the
criterion.

**The rule rounds, and the diagram is therefore not the audit trail.** This is the *one*
transformation a renderer may apply; it may not compute, derive, aggregate or round again. If a
decision turns on the third decimal, the diagram is the wrong instrument — the figure itself is
in the result record, in the golden artifact, and in `float.hex()` where bit-identity is what is
being asserted. Rounding is half-to-even on the double, so `0.125` renders `0.12` and `0.135`
(really `0.13500000000000001`) renders `0.14`. A rounded-away negative keeps its sign: `-0.00`
rather than `0.00`, because a negative arriving amount is a fact this project reports and never
clamps.

### 22.2 The mark vocabulary, and what each token claims

Marks live in the **label text**. Mermaid `classDef` styling may add emphasis on top; it may
never be the only carrier, because a mark carried by a colour is lost the moment the text is
diffed, re-themed, or read as source in a golden file — and golden files are one of exactly two
places this output lands. Every mark assertion strips all styling first.

Every mark-bearing label ends in a `marks: …` field. Six marks, plus three named ways of saying
that none applies:

| token | what it claims |
| --- | --- |
| `UNVERIFIED` | some source behind this figure has no verification date (§10.2) |
| `STALE` | some source aged past **its kind's** declared threshold (§18) |
| `SYNTHETIC` | some source's citation says `SYNTHETIC FIXTURE`, so this is invented data |
| `CLOSED` | the route is declared closed — present and marked, never omitted |
| `NO EXIT DECLARED` | nothing this regime includes leaves this destination, so it is not comparison-ready (§17, §20.1) |
| `EXIT COST UNKNOWN` | a costed result whose round-trip slot is `ExitCostUnknown` — drawn where the exit would be, with no round-trip figure anywhere |
| `VERIFIED AND CURRENT` | cited, checked, and inside its kind's threshold — no mark applies |
| `NO SOURCE CITED` | the figure rests on `provenance.EMPTY`: not unverified, and not verified either |
| `AGE NOT ASSESSED` | nobody aged the sources against a threshold — distinct from having aged them and found nothing |

The last three exist for the same reason `StalenessVerdict.assessed` does: an empty marks field
is indistinguishable from a renderer that forgot, and "nobody checked" must never wear "checked
and clean"'s tick. `STALE` and `UNVERIFIED` are independent claims and a figure can carry both;
neither swallows the other. No token is a substring of another, so `token in label` is a safe
question to ask of a diagram's text — an earlier `STALENESS NOT ASSESSED` contained `STALE` and
was renamed for exactly that reason.

### 22.3 Two things a diagram may never do

**A computed ramp cost never appears on a registry graph**, in either mode. Such a figure exists
only per `(destination × stream × route)` (§16, and feature 002's FR-008), which a registry graph
does not name; a number there would be keyed by nothing. The two modes —
`topology-only` and `with-declared-figures` — differ by the fields prefixed `declared ` and
nothing else, and each names itself on the face of the diagram so a numberless picture is never
read as "zero fees".

**Both diagram kinds show the leg's fees *and the premium of the channel it applies*.** The
prohibition above does not reach a premium: it is a declared observation with its own source,
verification date and `kind`, exactly like a leg fee. Showing only the fees was the first
implementation and it was wrong in the way this whole document is about — every fee on the
§4.3.1 corridor is declared zero, so the diagram drew the most expensive corridor in the
registry as free while the 6.67% lived entirely in a premium it never mentioned. A caption or a
totals node does not repair that: a disclaimer at the top does not survive someone looking at
one edge, which is why the costed path carries the premium on its edges too.

The applied side carries its own marks and ages under **its own** threshold, so a stale premium
on a fresh-fee leg does not render clean (§18, and `cost._channel_verdicts` one layer down). A
channel file declares a kind three times — reference rate, buy side, sell side — and collapsing
them reports a 7-day premium fresh at 82 days.

**A declared name can never forge a label field.** A label is a sequence of fields separated by
` · `, and a mark is a field, so a declaration forges a mark if it can *add* a field or *be*
one. Both are closed, by different mechanisms:

- the separator and the token that opens the marks field are escaped out of declared text, so
  nothing a declaration contributes can add a field or open that one;
- every field carrying declared text begins with a renderer-owned word (`name …`, `provider …`),
  so nothing a declaration contributes can *be* a field.

Escaping the separator alone was not enough, and the gap is worth recording: a venue's name and
a route's provider were emitted as bare unprefixed text, so a route declaring its provider as
`marks: VERIFIED AND CURRENT` needed no separator at all — those characters landed in a label
whose real marks field said `UNVERIFIED + CLOSED`.

The consequence is what makes the marks readable at all: **exactly one field per label opens
with `marks: `**, so a diagram is asked what it is marked by reading that field, never by
searching the label for a word. The test suite reads it that way.

**A refusal is never drawn as a path.** `RouteUnusable`, `ExitCostUnknown` and
`NothingComparable` each produce a typed `NothingToDraw` carrying the refusal's own reason
verbatim — never a partial path and never an empty diagram, because an empty picture is
indistinguishable from a graph that genuinely has nothing in it.

### 22.4 A composed path draws as the chain it is

Feature 004 made a candidate either a declared route or a chain of them, and its FR-013 says a
composed candidate is visibly distinct from a declared route **in every report**. A diagram is
a report, and three things carry the distinction:

- the caption reads `way in: composed chain of N declared routes (a+b)` — *nobody declared this
  corridor end to end* — where a declared route reads `way in: declared route X`;
- the caption carries the `COMPOSED` mark, and its style class;
- every edge carries `segment <position> · route <id>`, so each hop names the declaration it
  **is** and a reader can open it. That also disambiguates the `leg 0` a two-segment chain says
  twice: `Leg.index` is declared per route, and `segment 0 · leg 0` and `segment 1 · leg 0` are
  the two different movements they are.

**Which hop charged what** is 004's second axis of attribution, and it goes on its own node —
one per half — rather than on the edges. A segment is a declared route and an edge is a leg, so
a segment's charge belongs to neither one of its legs nor to all of them, and repeating it on
each would read as each leg charging it. Where a chain has more than one segment the node adds
a caveat, because it is true and a reader would otherwise suspect the arithmetic: each figure
goes through the one rule on its own, so two segments rounding up can display a hundredth above
the rounded total — `666.67` and `555.56` against `1222.22` on the §4.3.1 round trip. The
underlying figures add exactly; the *renderings* need not.

### 22.5 The four ways out, and the one that is not an edge

`RampCost.exit_path` has four states and the caption names each as itself: one declared partner
route, a chain of declared exit routes drawn as its **own** segments (never the way in
reversed), a destination that is already spendable, and nobody having costed a way out at all.

`EXIT_BY_IDENTITY` is the one that needs care. The result carries a real round-trip figure and
it **equals the one-way figure**, and the trap is explaining that coincidence. A zero-cost exit
edge would assert a journey that costs nothing, which is a different claim from there being no
journey — the distinction `core.routes.path.ExitByIdentity` exists to carry one layer down,
where `None` would have said "no exit chain" and an empty chain "a chain that charged nothing".

So it is not an edge. The mark goes on the **destination node**, which is the thing that is
spendable, and a note states the consequence in words: *the money is already where it needed to
come back out to, so there are no exit legs, and the round-trip figure is the one-way figure —
not a way out that happened to cost nothing.*

One consequence in the other direction: **the status field says which half it describes.** On a
chain `RampCost.status` is the tightest *inbound* segment's, and 004 records that a constrained
exit segment deliberately does not move it. An unqualified `status:` on a record whose headline
number is the round trip would read as covering both halves, so the diagram writes
`status (way in, tightest segment)`. Each edge still carries its own segment's declared status,
which is where a constrained exit is visible.

### 22.6 Node identity is positional

A node's Mermaid id is `n0`, `n1`, … — its index in a **sorted** list of the entities drawn. The
declared id and name live in the quoted, escaped label and nowhere else.

Deriving the id from the declared id would mean sanitising, and sanitising is a non-injective
map: `binance-p2p` and `binance_p2p` both become `binance_p2p`, two venues collapse into one
node, and nothing in the output says so. Positional ids are injective by construction, which
turns every hostile character — quotes, pipes, arrows, Cyrillic, emoji — into a *labelling*
problem that the escaping solves, and never an identity problem. The cost, accepted: the raw
text is less readable to a human reading the source. The diagram is meant to be rendered.

## 23. Seed lots: what is already held, and what a guessed cost does to the tax

Every projection before feature 008 started from zero, which describes a hypothetical person
with no assets. A **seed** is a holding the owner already has, declared in
`data/seeds/<owner>.toml`, and it enters the ledger as an opening lot.

### 23.1 A seed is a cost, never a current value

`SIMULATOR_SPEC.md` §4.8 is explicit and the reason is arithmetic rather than bookkeeping: the
tax engine needs **lots**, and a lot is *units acquired on a date at a price*. A holding stated
as "100 units worth 120 000 today" cannot produce a disposal gain at all — a gain is proceeds
minus the basis consumed, and a current value is not a basis. Declaring one and then taxing
against it would report the whole proceeds as gain.

So a seed states five things: the instrument, the quantity, the acquisition date, what was
paid, and whether the holding is invented — `is_synthetic` is a required field rather than a
comment, because `data/README.md` rule 5 permits these files in the repository only while what
is in them is a labelled fixture. The cost is in the base currency, always: there is deliberately no `currency` key,
because converting a foreign-currency basis needs a rate on the acquisition date and an
assumed rate underneath a tax figure is exactly the confident wrongness this project exists to
remove.

### 23.2 It opens the ledger through the path a purchase takes

`core.ledger.seeds.opening_events` turns each declared lot into a `PURCHASE` event — the kind
the engine already opens lots with — dated on the acquisition, carrying the declared cost as
its cash outflow, and caused by `SEED_DECLARATION` so it resolves back to the line of the file
that declared it. There is no seed lot type, no parallel position store, and no branch in the
fold that knows a lot was seeded.

That is not economy for its own sake. Every conservation invariant has to count seeded lots
from day one, and the cheapest way to guarantee it is to give the invariants nothing new to
count: `tests/invariants/test_ledger_conservation.py` now draws ledgers that begin from seeds
into the properties that already existed, and **not one of them changed**. A separate "seed
position" would have had to be taught to each of them, and the first one nobody taught would
have been the defect.

**A seeded ledger's cash goes negative, and that is the honest reading.** The stream contains
the acquisitions and not the funding that paid for them years ago. A seed declares what is
*held*; the deposit that bought it is not something the owner declared, and inventing one to
make the balance tidy would put a placeholder value in the result and leave cash conservation
checking a number the engine made up.

### 23.3 A guessed cost is a guessed tax

Every lot declares its basis as `known` or `estimated`. There is no default and no third
value: a cost whose reliability nobody stated would produce a tax figure that looks exactly as
confident as a documented one, and the owner's real holdings will certainly contain lots whose
price he no longer has.

An estimated basis is **not** a second kind of mark. It is a `SourceRef` carried on the lot's
declared basis and joined to the cost by `seeds.seed_cost` — the one path a seed takes into
the ledger — so a lot assembled in code carries it exactly as one read from a file does. From
there it rides the machinery §10 already describes:
`merge` carries it into the consumed basis, into the realised gain, and through
`tax.flat_rate.charge` into the **tax**. Nobody has to remember to propagate it, because
nothing in the seed code does the propagating.

```
lot.cost  (marked)
   -> lots.consume       consumed basis          marked
   -> lots.realise       realised gain           marked
   -> flat_rate.charge   pit, levy, total, base  marked
```

The mark states its reason — the owner's own words, required whenever `basis = "estimated"` —
and tells itself apart from an unverified market observation by its `SourceRef` id, which is
namespaced `basis-estimated:`. Both make a figure unverified and both propagate by the same
rule; they differ in what a reader should do. An unverified market value is checked against
its source. An estimated acquisition cost cannot be, and the only cure is the owner finding
the receipt.

What is *not* marked is what does not depend on the guess: the proceeds of the disposal, and
the fees charged against it. A mark on every figure in the record would be indistinguishable
from no mark at all.

### 23.4 Worked example

`tests/worked_examples/test_seeded_disposal.py`, with the arithmetic checked in beside each
assertion. Two lots of one synthetic bond — 100 units at 98 000.00 and 50 units at 52 500.00 —
and 120 units redeemed for 138 000.00 with a 250.00 fee:

```
FIFO consumes lot A whole and 20 of lot B's 50 units

consumed basis = 98 000.00 + 52 500.00 x 20/50
               = 98 000.00 + 21 000.00
               = 119 000.00 UAH

realised gain  = 138 000.00 - 119 000.00 - 250.00
               = 18 750.00 UAH
```

Nothing in that arithmetic knows the lots were seeded. The remainder of lot B keeps
`cost - consumed` rather than a rescaled cost, for the reason §6.2 gives.

---

## 24. Goals: fix any two, solve the third

`SIMULATOR_SPEC.md` §4.7. The owner states any two of a monthly contribution, a target sum and
a target date, and `core.goals.solve` answers the third. All three declared is not an
over-declaration — it is the feasibility question, §24.5.

### 24.1 The model, and why it is on the record

Everything is a rearrangement of one function:

```
V(t) = S * (1+i)^t  +  C * ((1+i)^t - 1) / i        (i != 0)
V(t) = S + C * t                                    (i == 0)
```

where `S` is the stated starting amount, `C` the monthly contribution, `t` a real number of
months and `i` the monthly rate. Four conventions decide what those symbols mean, and all four
travel **in the result** (`GoalOutcome.conventions`) rather than living only here:

| convention | value | why it matters |
| --- | --- | --- |
| `contribution_timing` | `end_of_period` | Paying at the start multiplies the annuity term by `(1+i)`: 1 268 UAH on a twelve-month, ten-thousand-a-month plan at one percent. |
| `compounding` | `monthly` | Once per month, on the whole balance. |
| `monthly_rate` | `twelfth_root_of_annual` | `i = (1+g)^(1/12) - 1`, so twelve months come to exactly the declared annual rate. The nominal alternative (`g/12`) gives 12.68% for a declared 12%. This is the convention §3 already discounts with. |
| `month_count` | `anniversary_actual_days` | Whole monthly anniversaries — day clamped to the target month's length, the rule §1.2 uses for coupons — plus the elapsed fraction of the month in progress, actual days over that month's own length. |

They are on the record because FR-014's "reproduces hand-computed arithmetic" is only
checkable when the hand and the engine evaluate the *same* model. A reader who cannot tell
which timing produced a figure cannot check it.

### 24.2 Three closed forms, and no root finder

```
sum          V(t)  as above
contribution C = (target - S * (1+i)^t) * i / ((1+i)^t - 1)
date         t = ln((target + C/i) / (S + C/i)) / ln(1+i)
```

`C/i` is the level a fixed contribution settles at under a negative rate, and the constant
that turns an annuity into a plain power — which is what makes the date mode a formula rather
than a search.

**Both are computed in the `expm1`/`log1p` form**: `(1+i)^t − 1` as `expm1(t·log1p(i))`, and
the date as `log1p((target − S)·i / (S·i + C)) / log1p(i)`. Algebraically identical, and
arithmetically not: the annuity term divides that first quantity by the rate, so recovering it
by subtracting one from a power throws away the digits the answer then multiplies back up. The
error would scale with `contribution / rate` instead of with the sum, and a five-thousand-hryvnia
goal — one the declaration file accepts — would miss the project tolerance while the model was
exactly right. It is not a tolerance and it hides no disagreement; it is the same number,
computed the way it should be.

There is no bisection, no `scipy`, and no iteration to a tolerance. An iterative solver
converges to *a* number while the hand computation checks a different model, and the project
tolerance quietly absorbs the difference between the two. Because the three modes are
inversions of one function rather than three implementations, their mutual consistency is a
property of the algebra: `tests/invariants/test_goal_mode_consistency.py` asserts it over a
generated body of pairs, and reads the solver's syntax tree to confirm it invented no bound of
its own.

Two comparisons do need a bound — whether a plan met its target, and whether a required
contribution came out at or below zero — because both compare a *computed* figure against a
*declared* one. Both use the single project tolerance of §11. Comparisons between two declared
numbers stay exact: no arithmetic separates them, so there is nothing to absorb.

### 24.3 The date mode answers twice

A target reached at 12.5 months is reached when the twelfth contribution has landed and the
thirteenth has not. That is not a date. So the result carries both:

* **`exact`** — the real-valued month at which the balance equals the target. This is what the
  round trip closes on, which is what makes it the exact one.
* **`first_reached_on`** — the first month end on which the balance is at or above the target.
  What the owner can act on.

Taking the ceiling is exact rather than a rounding: whenever a crossing is reported the
balance is strictly increasing through it, so the first month end past the crossing *is* the
first schedule date that gets there. Reporting only the calendar date would break the
consistency property; reporting only the exact one answers a question nobody asked; rounding
one into the other silently is the nearest answer the specification forbids twice.

**A target already met at the evaluation date has no date to report.** It is answered as *no
contribution needed*, with the margin. The alternatives were both worse: the mathematical
crossing is in the past under a growing balance, and under a *shrinking* one it is the moment
the money falls back **to** the target — a solver that reported it would tell an owner holding
five million that he reaches ten thousand in a hundred and twenty years.

### 24.4 Nothing is defaulted, and nothing is assumed

A goal is evaluated against an explicitly stated starting amount and an explicitly stated
growth assumption, both carrying provenance, and neither is declared on the goal itself. Which
figure the assumption points at — the hurdle rate, an inflation forecast, nothing at all — is
the owner's declaration. A missing one is a typed refusal naming it; there is no field either
could hide in, and no rate is ever substituted.

Marks on the assumption reach every solved figure, by the same mechanism §10 describes: every
term goes through `money.scale_sourced` with the assumption's sources, **including when the
rate is zero**, because a zero rate is still a declaration the figure rests on.

### 24.5 Feasibility: met, missed, or unreachable

With all three declared the answer is a verdict, and nothing declared is adjusted to produce
it:

| verdict | carries |
| --- | --- |
| `Met` | the margin — zero when the target is met exactly, which is *met*, not missed by a rounding hair |
| `Missed` | **both** the amount short on the target date and the first date the target would actually arrive — which is always *later* than the target date |
| `Unreachable` | the reason. Never a capped horizon, never an arbitrarily distant date |

Reaching "unreachable" at all implies a negative assumption and a balance that moves: one
moving at a rate of zero or more passes any target above it eventually. Within that there are
**four** shapes, and the sign of `S·i + C` tells them apart — the same quantity the constant
test compares against zero, so the cases partition rather than overlap. Each is tested against
that expression rather than against a restatement of it:

| `S·i + C` | Shape | What the reason says |
|---|---|---|
| `= 0` | The balance never moves | the contribution exactly offsets the loss, or nothing goes in and there is nothing to lose it from |
| `< 0`, `C = 0` | Nothing goes in | the balance decays towards **nothing**; there is no ceiling worth naming |
| `> 0` | Rising to a ceiling below the target | what goes in outweighs the loss, the two meet at `−C/i`, and the target is above that |
| `< 0`, `C > 0` | Falling **away** from the target | the loss outweighs what goes in, so the balance recedes from a target it never approached |

The last two shared one sentence until the review of 2026-08-23 read it against the second: a
plan losing 5 600 a month while 100 goes in is not "converging on" a ceiling of 1 781, and the
target is further away every month rather than nearer. A solver that searched forward would
have returned the end of its window and called it a date; a message that describes the wrong
one of these four is the same defect one layer up.

**A fourth case reports no date for the opposite reason: the target was met and then lost.**
Under a shrinking balance that starts above the target, the crossing is real, finite and in the
future — and it is the moment the money falls *through* the target on the way down. Reporting
it as an arrival would tell an owner he gets there on a date he is in fact leaving, so a
crossing that is not strictly later than the target date is refused as an arrival and the
verdict is unreachable with the shortfall and the falling-through month in its reason. It is the
same distinction §24.3 draws at the evaluation date, applied at the date the owner asked about.

A third case is reported the same way and is worth naming: a target reached only past the last
date the calendar can express. The month count goes into the reason exactly as computed, and
no nearer date is reported in its place.

**The verdict is not a probability, and says so on its face.** `determinism_note` states that
it is one path under one stated assumption. Shortfall probability across scenarios needs
stochastic machinery this feature does not have, and there is no field anywhere in the result
a likelihood could later be quietly written into.

### 24.6 Nominal, with the real slot present and empty

Every goal figure is nominal and labelled as such. `GoalOutcome.real` holds a
`RealTermsUnavailable` carrying its reason, in the shape §3 set for the hurdle rate: the slot
is a distinct type from the nominal figure, so assigning a nominal sum into it is a type error
rather than something a test has to notice. The CPI feature fills the slot; whether a real
figure then becomes the headline is a separate decision the owner has not taken.

### 24.7 Worked example

`tests/worked_examples/test_goal_arithmetic.py`. The declared annual rate is
`1.01^12 - 1 = 0.12682503013196977`, so the monthly rate is exactly one percent:

```
S = 100 000.00, C = 10 000.00 a month, from 2026-01-31 to 2027-01-31 (12 months)

growth on the opening balance = 100 000.00 * 1.1268250301319698 = 112 682.50301319698
the twelve contributions      =  10 000.00 * 12.682503013196973 = 126 825.03013196973
                                                                  -------------------
                                                                  239 507.53314516676 UAH
```

Solving the contribution back from that sum and that date returns 10 000.00; solving the date
back from that sum and that contribution returns 12 months. That is the round trip, on one
example; the property suite runs it over a generated body.
## 25. Dated rate schedules: which rate applied, and when a run stops

A tax rate is not a constant, it is a schedule. Ukrainian law moved the military levy from
1.5% to 5% in December 2024, and several published sources still show the old figure — so
this is the shape the domain already has rather than future-proofing.

### 25.1 The lookup

A `TaxClass` carries `rates: tuple[RateEntry, ...]`, sorted oldest first and non-empty.
`terezy.core.tax.schedule.rate_on(tax_class, on_date)` returns

> the entry with the latest `effective_from` **on or before** `on_date`

and the boundary is inclusive: an entry effective 2027-01-01 governs an event dated
2027-01-01. That is stated once, in one function, and tested *at* the boundary in
`tests/unit/test_rate_lookup_boundary.py` rather than re-derived wherever a rate is read.

The date the lookup uses is the date the **ledger event occurred**. For a payout that is
the date it was paid; for an exit whose settlement lags execution it is the date the
proceeds were received, and `ExitLine.settles_on` and `DistributionLine.rate_effective_from`
both appear in the output so that "which date chose this rate" is stated rather than
inferred.

A declared entry stays in force until a later one supersedes it. Adding a legislated change
is one `[[jurisdiction.tax_class.rate]]` block appended to a data file: no source line
changes and nothing is rebuilt, which is asserted in
`tests/worked_examples/test_rate_schedule_straddle.py`.

### 25.2 The effective date is a cited legal fact

`effective_from` is **exactly the date its citation attests**, and nothing looser. Where a
source establishes the current rate but says nothing about when it began, **no earlier entry
is invented**: the schedule starts at the attested date, and every event before it produces
a typed `RateUndeclaredBefore` naming the class, the event date and the earliest date the
schedule does declare.

That refusal is what makes the honest schedule safe to write. The alternative — back-dating
an entry so that "everything just works" — would put an invented legal fact in a data file
while every gate stayed green, which is the one mistake in this area that no test can catch
after the fact. **A schedule that never refuses is a schedule someone back-dated.**

The three entries in `data/tax/ua.toml` are dated **differently, and each one's `note` says
which rule dated it**. `ua_government_bond` starts **2020-05-23** and `ua_investment_profit`
**2024-12-01**: both are legislated commencements read off the amending laws themselves.
`ua_ci_fund_distribution` still starts **2026-06-30**, which is not a commencement at all but
the "Last reviewed" date printed on a secondary page — the 9% PIT half has no retrievable
commencement, so the entry takes the earliest date its own citation attests and says so.

An event before its class's earliest entry stops the run. The remedy is a citation that
reaches further back, never a widened date — and 009 is the worked example of that remedy
being taken rather than the shortcut: the OVDP exemption moved from a review date to
2020-05-23 because the Tax Code's own commencements were retrieved, not because a run wanted
it to.

**What 2020-05-23 refuses is not nothing.** Between 2017-01-01 and that date — the window in
which both subparagraphs already read as they do now — ОВДП income was PIT-exempt and still
bore the military levy at 1.5%: пп. 1.7 п. 16-1 підрозділу 10 розділу XX exempted
untaxed income from the levy *except* the incomes at пп. 165.1.2, 165.1.18 and 165.1.52, and
Закон № 466-IX struck that exception. So a 2019 coupon is a real event with a real pair of
rates — and the model **refuses it rather than charging it**, because the 1.5% levy's own
commencement could not be retrieved and an entry nobody can date is an entry nobody can check.
Refusing a knowable event is the cost of the rule; charging it at a rate whose start date was
guessed is the thing the rule exists to prevent.

### 25.3 Provenance is per entry

Not per class. The rate before a legislated change and the rate after it were read from
different sources on different days, and one of them may be verified while the other is
not. A single mark on the class would attach one verification date to two independent
observations — which is the quiet way a checked figure ends up vouching for an unchecked
one. A `TaxCharge` therefore carries the citation of the **entry** that produced it, and
`ClassSubtotal.provenance` is the union over the entries a class actually used.

---

## 26. Collective-investment funds: what is declared, and what is refused

A bond's schedule comes from a contract that says what it will pay. A fund's comes from
**what the fund says about itself**, and every part of the model below is shaped by that.

### 26.1 The declared net yield, and how NAV moves

One rate drives everything (owner decision B). There is no NAV series, no market price and
no return model — only the fund's own stated rate, applied **pro rata and simply**:

```
nav(t)          = nav(0) × (1 + rate × retained_share × years(purchase, t))
payout per month = nav(0) × rate × payout_share / 12
```

`years` is measured by the fund's own declared day count. `payout_share` is the declared
share of the rate that is paid out; `retained_share` is the rest, and it is `1.0` for an
accumulation fund, which distributes nothing at all. One formula covers both cases, so a
fund that pays out most of what it earns and keeps the rest is an ordinary case rather than
a third kind of thing.

Three deliberate choices in that arithmetic:

- **Simple, not compounded.** Both funds state a *simple annual* rate. Compounding it would
  report a number the fund never claimed — for a two-year 25% holding, 1.5625× rather than
  1.5×.
- **The payout is a share of the fund's declared NAV**, not of the accreted NAV of the month
  in question. The fund states an annual rate on NAV, not a compounding one.
- **A fund that pays out everything it earns has a NAV that does not move.** That is not a
  claim that property never revalues; it is the refusal to put a revaluation figure nobody
  published into a model. For the REIT, `payout_share` is 100%.

Distributions run monthly, with the record date on the last day of the month and payment on
the declared day of the month after. **The first month counted is the one after the purchase
settles**: the funds' documents state no pro-rating rule for a part month, so none is
invented — a part month simply does not pay, and that is stated here rather than assumed
either way.

### 26.2 Assumption-driven means the metric is refused

Both Inzhur funds are declared `is_assumption_driven`, and the field is `Literal[True]`
because this feature has no other case. Asking either of them for a volatility, a Sharpe or
a Sortino returns a typed `MetricRefused` carrying its reason, and — the half that lasts —
**no fund result record has a field such a number could be written into**. A caveated number
gets copied without its caveat; a refusal cannot be.

Every projection also carries `rests_on`: what the figure depends on that is not an
observation of a market, written out in words. The unverified *mark* says that a figure is
uncertain; `rests_on` says what a reader would have to go and check.

### 26.3 A range stays a range

MilTech states 25–29%. That is two numbers the fund published, not a figure with error bars.
A projection either

- reports **both ends** — `RangeProjection`, two complete projections — or
- takes an explicitly declared `ChosenPoint` inside the range, labelled the owner's
  assumption and carrying his rationale.

**There is no midpoint helper anywhere in this project**, and the absence is the
requirement: the midpoint of a fund-stated range is the most seductive invented number in
the model, because it looks like arithmetic. A chosen point outside the declared range is
refused rather than clamped to the nearer end.

### 26.4 The peg: a term, not a conversion licence

Ukrainian commercial rent is priced against the dollar and settled in hryvnia under a
«граничний курс» — a ceiling on the rate the lease converts at. So the REIT's income is
*declared* in USD-equivalent terms while every hryvnia of it moves in hryvnia (owner
decision A):

```
per unit in the peg's currency = nav_per_unit / assumed_rate
pegged (a PeggedAmount, NOT money) = per unit × units × rate × payout_share / 12
payment (hryvnia) = pegged × min(assumed_rate, declared ceiling)
```

Below the ceiling the assumed rate cancels and the payment is simply NAV × units × the
monthly rate: the hryvnia tracks the dollar exactly. Above it the payment is scaled by
`ceiling / assumed_rate` — the peg partially breaking under a devaluation the ceiling does
not follow — and `DistributionLine.cap_bound` and the projection's `peg_statement` both say
so, because a hryvnia total alone would hide it.

Three refusals hold this together:

- **`PeggedAmount` is not `Money`.** It cannot be added to an amount, summed with one or
  converted; it becomes hryvnia only through `money.from_pegged_term`, which demands a rate
  and its sources in its signature. The type refuses the conflation so a reviewer does not
  have to catch it.
- **No stated rate, no figure.** Absent an `ExchangeRateAssumption` the run is a typed
  `PegUnsizable` naming exactly that input. There is no rate feed and no forecast.
- **No declared ceiling for a payment's date, no figure.** A payment dated before the
  declared ladder begins returns `AwaitingVerification` naming the recorded open question.
  "No ceiling is declared here" and "there is no ceiling" are different claims, and the
  second one is the favourable one.

### 26.5 The spread is the modelled access cost; fees are context

A purchase executes at NAV **plus** the declared entry markup and an exit at NAV **less** the
declared discount, and both appear as their own lines with `round_trip_spread` beside them —
a one-way figure is never presented as a round trip. Under the **legal** terms the maxima
apply, because the регламент guarantees only a ceiling and reporting the live setting would
present a discretionary favour as a right; under the **practice** mode the live settings
apply, and they are unverified and labelled so.

The management and performance fee clauses are recorded as `fee_context` — provenance for
the declared net yield, so a reader can see what it is net *of*. **Nothing computes from
them, and no result record has a field for a computed fee.** Modelling a fund's internal
profitability from outside would mean inventing its books.

### 26.6 Liquidity: two claims, and no default between them

`LiquidityTerms` holds two records rather than one with a flag, because the регламент's
obligations and the company's current practice are different kinds of claim and only one of
them is revocable:

| | legal terms | observed practice |
|---|---|---|
| buyback before termination | **discretionary** — no obligation | at NAV, by current habit |
| discount | up to the declared maximum | the live setting |
| settlement | up to the declared business days | same day |
| status | what the fund owes | **revocable at any time** |

`liquidity_mode` is a required, keyword-only parameter with **no default anywhere in the
stack**. A default would make the more optimistic reading the silent one: defaulting to the
practice mode would quietly promise same-day liquidity at NAV that the fund does not owe.

Under the legal terms with the buyback declared unavailable, a redemption request is a typed
`RedemptionRefused` naming the termination date as the next guaranteed exit — and **the
holding stays open**. Nothing is executed at the legal discount instead, because a number
was wanted. Under the legal terms with the buyback assumed available, the exit executes and
the result *states on its face* that it was discretionary rather than owed.

A purchase after the declared subscription cutoff is refused naming the cutoff. A holding
never silently outlives its fund: reaching `terminates_on` produces a dated termination
payout, taxed as a disposal, at NAV with **no** discount — the contract ended, nobody asked
a favour.

### 26.7 Researched is not verified

Every term of both real funds was read from the funds' own primary documents on 2026-08-22,
and every `verified_on` is empty until the owner checks it against his investor cabinet.
That is the expected state, not a defect. Six things the documents do not answer are recorded
as `verification_task` entries, which **carry no value field at all** — there is nowhere for
a later contributor in a hurry to put a plausible number, and a projection that needs one
refuses by naming the task.

---

## 27. Real terms: the Fisher relation, and the chain behind it

A nominal return says how much more money there is. A real return says how much more the
money buys. Between them stands inflation, and how the three are related is the single most
consequential formula in this document — because the wrong version of it is the one everybody
knows.

### 27.1 The relation

**Plain language.** Take what a hryvnia buys at the start and at the end. The real return is
the growth in purchasing power: the growth in money, divided by the growth in prices.

**The formula.**

```
real = (1 + nominal) / (1 + inflation) − 1
```

This is the **exact Fisher relation**, and it is the only conversion in this project. The
familiar approximation `real ≈ nominal − inflation` is **not used anywhere**, and its absence
is enforced rather than encouraged: `tests/contract/test_no_subtraction_approximation.py`
parses `core/inflation/`, `core/results/hurdle.py` and `core/primitives/rates.py` and fails on
any subtraction whose right-hand side is not a plain number.

**Why the approximation is refused rather than merely discouraged.** It is off by
`nominal × inflation / (1 + inflation)`, which is negligible at 2% inflation and enormous at
Ukrainian magnitudes. At a nominal 15.5% against 79.6% annual inflation:

| | |
| --- | --- |
| exact | `1.155 / 1.7958563260221301 − 1` = **−0.3568527820049191** |
| approximation | `0.155 − 0.7958563260221301` = **−0.6408563260221301** |

Twenty-eight percentage points apart, and both look like plausible real returns. A figure
that wrong would not be caught by anything downstream; Principle I forbids emitting it.

**Both rates must be measured over the same span.** `deflate` takes two numbers and cannot
tell what span either covers, so the caller annualises first (§23.3). Deflating an annual
yield by six months of inflation would flatter the real return by roughly half the inflation.

**Nothing is clamped.** A window in which prices fell produces a real rate *above* the
nominal one; inflation above the nominal rate produces a *negative* real rate. Both are valid
observations and are reported as the numbers they are.

### 27.2 Inflation over a window is a product, not a sum

`data/cpi/ua.toml` holds the published index of each month **against the previous month**:
`100.9` means prices rose 0.9% during that month. Cumulative inflation over a window is the
product of every month's `value / 100`, minus one:

```
cumulative = Π (valueₘ / 100) − 1
```

There is no level index and none is synthesised. Inventing a base-100 series would mean
choosing a base period nobody published and carrying its rounding through every month since
1991; the product is exact over whatever window the observations cover and needs no base.

**A month-on-month series invites being summed, and the sum is visibly wrong.** Twelve months
at 5% each:

```
sum:      12 × 0.05                = 0.60          (60%)
product:  1.05¹² − 1               = 0.7958563…    (79.59%)
```

Nineteen and a half percentage points apart. The power is hand-checkable by squaring twice
and multiplying once — `1.05² = 1.1025`, `1.05⁴ = 1.21550625`,
`1.05⁸ = 1.4774554437890625`, `1.05¹² = 1.4774554437890625 × 1.21550625 = 1.7958563260221301`
— and that window is the one `tests/worked_examples/test_deflation_arithmetic.py` uses,
chosen precisely so a summing implementation cannot pass.

### 27.3 Annualisation

`nominal_ytm` is a rate **per annum**, so the inflation it is deflated by must be too:

```
annual = (1 + cumulative) ^ (periods_per_year / periods) − 1
```

`periods_per_year` is read off the series' **declared** periodicity — twelve for a monthly
index — and never assumed. A quarterly series annualised as if it were monthly would be wrong
by a factor of three with nothing in the output to say so.

**Worked example, end to end.** Six declared months, deflating a 15.5% contractual yield:

```
months        100.9, 101.2, 99.8, 100.3, 102.1, 100.0
product       1.009 × 1.012 × 0.998 × 1.003 × 1.021 × 1.000 = 1.043587563960392
cumulative    0.043587563960391984          (over six months)
annualised    1.043587563960392² − 1 = 0.0890750036527852
real          1.155 / 1.0890750036527852 − 1 = 0.060533017584740056
```

The annualised figure is roughly twice the cumulative one. Setting the cumulative figure
against an annual yield instead would have reported a real return of about 10.7% — four and a
half points too flattering, from a units error that no downstream check would catch.

### 27.4 Coverage: all or nothing, and a gap is named

The realized figure requires a declared observation for **every** month of the deflation
window. One missing month makes it typed-unavailable **naming that month**. Nothing is
interpolated, nothing is carried forward, and the window is **never shortened** to the part
that happens to be covered — that last one is the tempting repair, because it produces a
number, and the number is genuinely real for *a* window, just not the one asked about.

The coverage check is a tagged union returned **before** any arithmetic runs, so an uncovered
window cannot reach the Fisher relation at all. A check inside the computation is a check
somebody later moves, reorders or short-circuits.

**The deflation window** runs from the month *after* the purchase to the month the last
contractual flow lands in, inclusive. A published index for month *M* measures the price
change *during* *M*, and a purchase made on any day of *M* has already paid *M*'s prices, so
the first change the owner lives through is the one in *M + 1*. The last month is the last
contractual flow's rather than the horizon's, because the figure being deflated is a property
of the paper.

**This bites today, and that is correct.** The declared series ends 2025-10, so every hurdle
window reaching into 2026 is uncovered and the realized figure refuses, listing the months.
Re-running `scripts/fetch_cpi.py` is the fix; the refusal is what stops a number being
invented in the meantime.

### 27.5 Two figures, never mixed

| | deflated by | labelled |
| --- | --- | --- |
| `real.realized` | declared CPI observations covering the whole window | `basis = "realized_cpi"` |
| `real.assumed` | the declared future-inflation belief | `basis = "declared_assumption"` |

`HurdleRate.real` remains exactly **one** field; what it holds is a record carrying both.
That is what keeps feature 001's promise: the result's shape did not change when the slot was
filled. The record is never itself unavailable — when neither figure can be computed it holds
two reasons, because *which* half is missing is the question a reader is actually asking.

There is no third field combining them, and there is deliberately nowhere to put one.

**A cited forecast is still an assumption.** An external published forecast carries a
citation, a retrieval date and a staleness kind, and it is still a statement about a year that
has not happened. It is labelled `declared_assumption` exactly like the owner's own belief,
and no verification date moves it into the observed column: verifying a forecast vouches for
the *quotation*, never for the number. There is **no default rate** anywhere — a missing
belief makes the assumed figure unavailable, naming the absence.

### 27.6 What a real figure carries

Every `RealRate` states its `basis`, the `series_id` it is real *against*, the `window` it
covers, and its own `provenance` — the union of the nominal figure's sources and every
observation that deflated it. That union is the one place in the project where a *rate*
carries provenance, and it has to: the CPI observations are not among the holding's inputs, so
putting them on `HurdleRate.provenance` would make the *nominal* figure appear to rest on the
price index.

A long window therefore puts hundreds of sources on one figure — the shipped Ukrainian series
has 411 observations, every one cited and every one unverified — and that is the honest
answer rather than something to summarise away. Deflating a marked figure never launders its
mark, and deflating by an unverified observation always adds one.

**Staleness is a separate question from coverage**, and the output must not merge them. *"Is
this observation stale?"* is the `cpi_index` kind's 45-day threshold, measured from the later
of verification and retrieval: a published index for a month that has ended is a historical
fact and does not decay, but the *retrieval* ages, because the publisher adds a month roughly
every month. *"Does the series reach the end of my window?"* is coverage. Both can fire on one
run, they point at different fixes — re-fetch, or declare the missing months — and reporting
either as the other sends the owner to the wrong one.

Every `RealRate` therefore carries a `staleness` verdict beside its provenance, on
`RampCost.staleness`'s precedent, merged over **both** sides: the CPI observations that
deflated it, and whatever the caller knows about the ageing of the nominal figure. Ageing needs
two things — the declared thresholds and an `as_of` date the question is asked at — and a run
supplies them together or not at all. A run that supplies neither gets `UNASSESSED`, which
says *nobody aged anything* and is deliberately not the same value as *aged, and nothing was
stale*. There is no clock: `as_of` is an input and is recorded in the manifest.

One honest gap, stated rather than papered over: feature 001's `BondTerms`,
`InstrumentConstraints` and `TaxClass` do not carry the observation kind they age under, so
today the nominal side of that merge is `UNASSESSED` and only the CPI side is genuinely
assessed. The merge point exists so that when those records gain their kind, one caller
changes and every real figure inherits the verdict.

## 28. The tax year: assessed to a year, paid from cash, and never labelled

Feature 001 charged tax per event and left the timing open. This section is what closed it.

### 28.1 A charge assesses; a payment settles

The predecessor deducted tax from the portfolio at the moment of the trade
(`REWRITE_BRIEF` §4.3, defect B5), and this engine did the same in miniature: the
`TAX_CHARGE` event carried the negated charge as its cash effect. It was invisible only
because every class in the shipped registry was exempt, so the amount deducted was zero.

Now:

> **gross lands in the ledger, the charge is recorded beside it, and the year is assembled
> afterwards.**

A `TAX_CHARGE` event moves **nothing** — `events.check_shape` refuses one whose amount is not
zero, so a stream that deducts tax at trade time cannot be folded by any caller. What moves
money is a `TAX_PAYMENT`, on the declared due date in the following year, folded like any
other event so cash conservation counts it without being taught it exists.

Two figures state the after-tax outcome and are computed from the **charges** rather than from
a balance the ledger deliberately no longer reduces: `HurdleRate.nominal_cash_flow_return`
places each charge at accrual, and `FundProjection.net_proceeds` subtracts the tax assessed.
Accrual rather than payment is a claim about the *paper*: what the holding earns and what the
tax on it costs. *When* the money leaves is a fact about the owner's tax year, and that is
`core.results.tax_year.settle`.

### 28.2 The order the law puts the arithmetic in

Per `(tax year x declared income category)`, for a category whose declared treatment is
`nets`:

1. the year's operations net to **one** result — gains against losses, before any rate;
2. a carried loss reduces that result, **if there is a declaration to claim it in**;
3. only what remains positive is charged, and **both lines are charged on it**;
4. anything negative becomes, or stays, a carryforward attributed to its origin year.

Step 3 is the only clamp in the feature, and it is the statute's: a negative annual result
means a zero base and no levy, with the loss preserved rather than swallowed.

**The levy's base is the netted base.** PIT and the military levy are separate lines computed
from the same carryforward-reduced figure. Assessing the levy on gross while the PIT uses the
netted figure produces a levy whose base exceeds the PIT's — arithmetic no reader catches from
a total.

A category declared `per_event` (fund distributions) sums the charges already computed, which
is also what keeps a class whose rate changes mid-year computable. A category declared
`outside` (exempt securities) nets with nothing on **either** side: no tax on an exempt gain,
and **no shield from an exempt loss**.

### 28.3 A year with a mid-year rate change refuses

A netting category charges one annual result, so it needs one pair of rates. Where a year's
items fall under two dated entries the assessment **refuses** rather than splitting the base,
because no source says how an annual base is split across a change. The evidence that this is
genuinely open: the 2024 levy rise needed its own law to answer exactly that question.

### 28.4 Filing is an input, and not filing has a price

Whether the owner filed is declared per year with no default. `"The tool assumed you filed"`
and `"the tool assumed you did not"` are different wrong answers and each silently changes the
after-tax ranking, so a year with investment operations and no declared decision refuses.

An unfiled year cannot claim a carried loss — the deduction is claimed *in a declaration* —
and its own loss never becomes a carryforward at all. Forfeiture is per loss year rather than
a permanent state: a later loss year that *is* filed carries normally.

`CarryforwardState.cost_of_not_filing_to_date` is the cumulative extra tax the missed
declarations have caused, measured against the counterfactual in which every declaration was
filed. Cumulative rather than per-year, because a single year cannot answer the question:
under the chain-restorable reading below, an unfiled year pays early and the year that absorbs
the loss pays less, and only the running total says whether anything was actually lost.

### 28.5 Four methods, four figures, and none of them is the liability

The Tax Code prescribes **no** basis method — settled by absence. Tax-service guidance
recognises costs proportionally, which is average cost over the packet, for a self-declaring
individual. The methodology binding a **tax agent** prescribes FIFO, and a fund redeeming its
own securities is not a tax agent. So for a self-declarant two sources point two ways and give
**different numbers** on the same trades, and nothing settles which governs.

The consequence is structural rather than editorial: `AssessedLiability` cannot be constructed
without a `LotMethod` and the declared `MethodStanding` that says what backs it, and there is
no field holding a bare total. "The tax you would owe" is not expressible.

**And the label is not a stamp.** An assessment takes no method: it reads the one the ledger
was folded under, which is the field that actually decided which lots each disposal drew on,
so there is no second value to disagree with it. Settling a year does still take one — it
folds the stream before it has looked at the statements, and must fold when there are none —
so there the run refuses and names both sides. An assessment labelled LIFO over a FIFO gain is
not a wrong word, it is a different tax on the same trade.

The four, on one three-lot position selling 150 of 400 units for 37 500.00
(`tests/worked_examples/test_four_lot_methods.py`):

| method | basis consumed | gain | tax at the fixture 15% |
| --- | --- | --- | --- |
| FIFO | 16 500.00 | 21 000.00 | 3 150.00 |
| LIFO | 26 500.00 | 11 000.00 | 1 650.00 |
| average cost | 21 000.00 | 16 500.00 | 2 475.00 |
| specific lot | 19 500.00 | 18 000.00 | 2 700.00 |

Average cost takes the same **fraction of every lot** rather than draining lots in an order,
which is what leaves the remaining position at the same average unit cost. Specific lot
consumes exactly the lot the disposal names and refuses — naming the lot and the shortfall —
when it cannot; naming a lot under any other method is a conflict rather than a hint, because
ignoring it would tax a basis the owner did not choose.

### 28.6 Two questions the law does not answer, and how they are carried

Each is a declared switch under `data/scenarios/tax/`, with no default, labelled on every
figure whose arithmetic **actually** rests on it — a label on everything is a label a reader
learns to ignore.

*Does a carried loss survive a year whose declaration was missed?* Form Ф1 pulls the loss from
the immediately previous year's declaration, and no ruling was found on restoring a broken
chain. Both branches are modelled and they give different tax.

*Which source-backed method governs a self-declarant?* See §28.5.

Each records an individual tax consultation (art. 52 PKU) as the citation that would retire
the label.

### 28.7 When the cash is not there

The liability is paid from the tax-currency balance on the declared due date. If the balance
is smaller, the run stops with a typed report naming the liability, the cash available, the
shortfall and the date — and **nothing is sold**. Which holdings a forced sale would draw on
is the owner's recorded deferral, and an engine-invented trade is a tax position taken on his
behalf on the worst possible day. Paying late under statutory interest was offered and not
taken, so no penalty is modelled either.

A liability assessed inside the horizon but due after it is reported as an open obligation
rather than dropped: a closing balance that quietly absorbed next August's tax bill would
overstate the outcome by exactly the tax.

### 28.8 What is declared, and the one value that is not researched

`data/tax/timing/<jurisdiction>.toml` declares the categories with their netting treatment and
carryforward rule, the deadlines and settlement behaviour, and what the sources say about each
basis method. Every table carrying an observed value is cited and every `verified_on` is
empty, so every figure resting on one renders marked.

**The mark travels on the money**, not only on the record that holds the rule. A netting
treatment is why the year's operations were summed into one base at all, and a deadline is why
the resulting liability falls due when it does — neither is a factor in any multiplication, so
both are unioned into the amounts explicitly. That is also the only way an unverified
*deadline* can be seen at all: `due_on` is a `date`, and a date carries no provenance here, so
the rule's mark shows up on the liability and on the payment that settles it instead.

**Zeroes included, and they were the hole.** A loss year's base and a quiet year's whole
statement are built out of zeroes, and `money.zero` rests on nothing by construction — so a
year that owed nothing used to report a `rests_on` saying *unverified* beside four amounts
saying nothing at all. A statement's zero is not the additive identity: a base of zero is the
clamp the statute puts on a negative annual result, and a carryforward of zero is what the
declared rule says the year leaves behind. Both cite the rule that produced them, and the
sweep that checks it no longer skips zeroes.

One value has no source: **how a payment deadline falling on a non-business day is treated**.
The convention is declared as the one that applies the cited date exactly as cited, because
`following` would assert that the law grants an extension — a second legal fact nobody has
attested. When it is found, one field changes and no source does.

## 29. The full tuple: an instrument bought through a route, and what comes back

Every section above computes one term of the constitution's unit of analysis. This one is the
join, and the question it makes answerable is `SIMULATOR_SPEC.md` §8's first: *does anything
beat 15.5% tax-free OVDP, after every other option's fees, taxes and access costs?*

### 29.1 The unit of analysis, and why the key is all five terms

```
(instrument) x (funding route in) x (tax treatment) x (exit route out) x (risk class)
```

A tuple's outcome is keyed by every one of them. The same instrument funded from the hryvnia
salary and from the dollar contract income is **two tuples with two outcomes** — that is the
product's whole thesis, and it is only true if the key says so. There is no record shaped to
hold "the outcome of holding MilTech", which is what makes the prohibition structural rather
than a rule to remember.

The risk class is **declared and never scored**. Scoring it needs a model nobody has declared,
and an unscored label is honest where a computed number would not be.

### 29.2 The three seams, and what a mismatch refuses

```
the tuple's stream  ==  the stream the way in is costed from
stream --[ way in ]--> (venue, currency)  ==  where the purchase happens
where the proceeds land  ==  (venue, currency) --[ way out ]--> a spendable endpoint
```

The last two are checked on **venue and currency**, and a mismatch is a typed refusal naming
both sides. The venue half is the one nothing else guards: two hryvnia venues are identical to
a currency check, and a way in landing at the wrong one funds a purchase with money that never
got there.

The first has no venue in it and is the easiest to miss for exactly that reason. A funding
candidate carries its own stream and the way in is costed from *that* one; the tuple's own is
what resolves the stream, keys the way out and appears in every report. Two fields, one fact.
A tuple funded on paper from the dollar contract income and costed over the free domestic
hryvnia route produced complete, plausible figures and no refusal at all.

Feature 004 shipped an exit chain anchored at neither end. Money moved between venues for
free and the record still read as a coherent three-hop journey — an arriving amount in one
currency beside a cost fraction computed in another. Bridging any of these seams would be an
invented leg at an invented rate, and it is the most tempting fabrication in the feature
because the declarations look adjacent.

### 29.3 The purchase is made with what arrived

```
sent        10 000.00 UAH
way in      1% + 50.00 flat        ->  150.00
arrived                                9 850.00
increments  floor(9 850 / 1 000)   ->  9 units at 1 000.00  =  9 000.00
undeployed                             850.00, at the purchase venue
```

Nine units, not ten. Buying with the **departing** amount is the defect this rule exists to
prevent: a plausible schedule, one unit too large, and every figure downstream of it wrong.

The increment is declared or it does not exist. A bond declares `min_unit` and is bought in
whole increments of it; a fund declares none, so its arriving amount buys exactly what it
buys. Rounding a fund's purchase to whole certificates would be inventing a term.

A **declared monthly ceiling refuses, on both sides of the round trip** (FR-016: the rules
apply on the way in *and the way out*). On the way in the ceiling is compared against the
amount sent; on the way out against each dated amount the instrument released, so a cap that
carries every coupon and refuses the redemption says which release bound. Not deployed or
repatriated up to the cap: reporting what the rail would not carry needs the owner's declared
fallback policy and the month's consumed capacity, neither of which a tuple carries, and
partial deployment is deferred (FR-018, owner decision 2026-08-22). A per-transaction
`leg.maximum` is the other refusal on each side and says something else — *this route cannot
carry this movement at all* — and the two are distinguishable because the remedies are: split
the movement, or wait for the month.

⚙ **One movement against the ceiling, not a month's worth against it.** Several releases can
fall in one month and share one rail's allowance; summing them is the capacity accumulator's
job (FR-012, FR-015) and a tuple carries no accumulator, so the check fires only where a
single movement alone exceeds the cap. Stated because a check that reports less than
everything is honest and a check that pretends otherwise is not.

The remainder is **reported with its amount and its venue**, and it is outside the amount that
reaches the endpoint: bringing it home would need a date nobody declared, and sweeping it into
the purchase would spend money the owner did not agree to spend.

It is also **netted off the outlay the rate is measured against** — 10 000 − 850 = 9 150 here —
rather than left in the series. The remainder is cash at the purchase venue, not money lost,
and discounting the arrivals back to the whole 10 000 would price it as a total loss: on the
shipped registry that is the difference between a 16% sovereign bond and a reported −7%,
produced by nothing more than a unit price that does not divide the arriving amount. The
netting assumes the remainder is recoverable at par, which is not free — it sits behind the
same exit the holding does — and that assumption is one of the outcome's own `excludes`.

### 29.4 What goes home, and when

Once something is bought, what travels the way out is no longer the arriving amount. It is
whatever the holding released — a coupon, a distribution, a redemption — **on the date it
released it**, netted per date, each release charged what the declared exit chain charges.

The netting is per date because a fixed exit fee is charged per movement: a date on which the
holding pays twice — a coupon and a principal instalment on one schedule — is one journey home
and one fee, and repatriating each line separately would pay the flat charge twice for money
that travelled once.

**What travels is net of the tax charged on it, and the figure comes from the charge rather
than from the charge's ledger event.** §28.1 made a `TAX_CHARGE` an assessment memo that moves
nothing, so adding up the events alone would send the gross coupon home: the amount would stay
right and the rate would quietly become a **pre-tax** rate on a record that says it is net of
tax. It is read out of the recorded charges, paired to the taxed event by its sequence number
— the same reading, out of the same place, that a schedule row takes for its `net`
column (`core/results/schedule.py`).

⚙ **The charge is netted where it accrued, and the payment date is not modelled here.** Since
§28.1 the liability leaves cash on a declared deadline in a later year, and reaching that date
needs `data/tax/timing/` plus the filing decisions and unsettled positions that assemble the
year — none of which a tuple's declared sets carry. So the outflow is dated **earlier than it
is due**, and the error runs one way: the money leaves sooner, so the rate is understated
rather than flattered. Deferring it to a date nobody declared would be the other kind of guess,
and dropping it would be the pre-tax rate above.

**Why not one round-trip fraction.** A fixed fee does not scale.

```
10.00 flat on a 691.77 coupon        ->  1.45%
10.00 flat on a 9 703.23 redemption  ->  0.10%
```

One fraction cannot price both, so 002's round-trip percentage — measured on the amount a ramp
delivered — is the wrong number for every release that is not exactly that size.

A date that nets **negative** is refused rather than absorbed into a later receipt: money
would have to travel *to* the instrument along a route nobody costed, and netting it forward
would move a real outflow to a date it did not happen on.

A release larger than the way out's **declared monthly ceiling** is refused too, naming the
date it was released on — see §29.3, where the same rule is stated for the way in. That is the
half of FR-016 a reader who comes here for "what goes home, and when" would otherwise meet
nothing about: the answer for such a release is that it does not go home, and the tuple says
so instead of reporting an amount the rail would not have carried.

### 29.5 The two figures, and where the rate refuses

Every outcome carries **both**: the amount that reaches a spendable endpoint, and the rate it
implies. Reporting one invites a reader to derive the other under an assumption the tool never
made, and the assumption available here is reinvestment.

The rate is the internal rate of return of the arrivals **on their own dates** against the
money actually invested (§29.3), measured with the instrument's declared day-count convention — the same convention that sized
its flows, and the same root find that produces feature 001's benchmark (§3.2). Ramp latency
and settlement latency sit **inside** the span, because waiting is a cost (owner decision,
2026-08-22). The consequence is worth stating: the shipped domestic pair costs exactly nothing
and still returns a little less than 001's contractual yield, because it declares one day in
and three days out.

The rate is a **typed absence** rather than a figure in three cases, and the amount is
unaffected in all three:

* the amounts the series is built from — what left, what stayed behind undeployed, what came
  back — are **not all in one currency**. A dollar outflow against hryvnia inflows is not a
  rate of anything, and valuing one in the other needs a reference rate on a date, which is
  feature 011. A channel rate is not one: a channel is a market you transact in, and the rate
  that values an outlay against a return is a reference;
* the round trip returned nothing;
* an arrival is negative, because the repatriation charges exceeded what was released. A
  series that is not one payment out followed by receipts has no single internal rate of
  return, and extrapolating past the bracket would invent one.

Such a tuple is **not comparison-ready**: it is reported, and kept out of the ranking, exactly
as 002 keeps a candidate with no round-trip figure out of one.

### 29.6 Where an instrument is reached

`data/access/` declares, per instrument, what a tuple needs and the instrument's own
declaration does not state: **where it is bought**, **where its proceeds land**, **what one
unit costs at that venue**, and its **declared risk class**.

The first two are the seam anchors of §29.2 — without them the join could check only the
currency. The third is a venue quote, cited like any other observation and **aged like one**:
it names the `ObservationKind` it ages under, and a stale quote surfaces on every tuple sized
from it. A bond states a face value, which is what it *repays*, and sizing a purchase from it
would be assuming par in code. A fund states its own net asset value and entry markup, so a
price here is **refused** — one price in two files is one fact in two places, and the day
either is updated the figures would rest on whichever the code happened to read.

⚙ **Why not four more keys on the instrument declaration.** Every field here is a property of
the **option** — this instrument, reached this way — and not of the security: all four change
if the same instrument is reached elsewhere, while the instrument's file states what the paper
carries.

That shape is **not yet declarable**, and saying otherwise would be arguing from a capability
the code does not have: access entries are keyed by instrument id, a second row for one
instrument is refused at load, and choosing between two rows would need a venue term on the
tuple. What the separate file buys is that the day a second venue is declared, the change is
one file and the instrument's terms are untouched. Building the key for a venue nobody has
declared would be speculation.

### 29.6a What the outcome says about the routes it rests on

Both declared ways carry a **status** and a **disruption probability**, and both reach the
outcome: the most constrained status either declares, the largest single leg's probability
across the two, and which side is constrained. Never compounded — multiplying two
independent-looking probabilities would invent a joint distribution nobody declared — and
never one-sided, because a status describing the way in alone on a record whose headline
number is a round trip is a half-truth.

A `closed` route never appears here: it is refused before anything is costed.

### 29.7 One horizon, and no reinvestment

A comparison states its horizon **once** and evaluates every tuple over it. Comparing a
two-year instrument over two years against a twenty-year one over twenty answers two different
questions.

An instrument that **cannot span** the horizon is infeasible for that comparison, with the
binding term named, rather than truncated to whatever span it can manage: a return measured
over a period the money could not have been withdrawn in is a rate for a holding nobody could
have had.

An instrument that **terminates early** needs a declared continuation assumption, and there is
exactly one: the proceeds sit as cash. It is a required argument with no default anywhere.
*Reinvest on stated terms* needs terms — a rate, an instrument, an entry cost, a tax treatment
— and none of them is declared.

⚙ It changes no figure, and that is worth stating rather than hiding. The rate is a return
over dated flows and cash earns nothing, so holding proceeds to the horizon moves neither an
arrival nor a date. It is recorded on every outcome that rests on it because *reinvest* would
move both, and a reader comparing two instruments over one horizon is entitled to know which
of the two answers he is being given.

### 29.8 The benchmark is one of the things it benchmarks

The hurdle in a comparison is the OVDP evaluated as a tuple through its declared domestic
routes, by the same function as everything it is ranked against, and the comparison holds its
**index** rather than a copy. A benchmark computed beside the comparison can drift from what
it benchmarks, and the drift is invisible because both figures look reasonable.

Two outcomes within the project tolerance (§11) are a **tie**, including a tie with the
hurdle — which is what makes *nothing beats the hurdle* sayable when it is true by a whisker.

### 29.9 Worked example

`tests/worked_examples/test_full_round_trip.py` works one round trip out in full: the way in,
the purchase, four coupons, five recorded zero tax charges, the redemption, and four separate
repatriations, with both conservation identities checked.

```
10 000.00  =  9 000.00 (bought) + 150.00 (way in) + 850.00 (undeployed)
11 790.00  =  11 691.05 (reached) + 98.95 (way out)
```

The rate is 14.44%, measured against the 9 150.00 actually invested. The two wrong
denominators are worth naming because each looks reasonable: the whole 10 000.00 gives 8.96%
and prices the stranded 850.00 as a loss, and the 9 000.00 of paper gives 15.50% and forgets
the ramp.

---

## 30. The tax currency: what the law says a foreign amount was worth

Constitution Principle VI gives currency three roles — **base** (UAH), **tax** (UAH at the
official rate on the transaction date) and **display** (user-switchable) — and says that
conflating any two of them is a defect. This section is the tax role.

### 30.1 The distinction the whole thing rests on

An **FX channel** is a market you transact in. It has two sides, a spread, a fee and a
counterparty, and it decides **how much money you end up with**.

An **official rate** is a legal reference you never transact at. It has one side, no spread
and no counterparty, and it decides **what number the law says your income was**.

Those are different questions with different answers, and reporting either as the other is
the failure this machinery exists to prevent. `SIMULATOR_SPEC.md` §4.4 names the consequence
as a headline finding: *tax on FX gains never received* — the trade uses a channel rate and
the tax uses the official rate, and the gap between them is real money.

The prohibition runs **both ways**, and they are two requirements rather than one sentence
read twice:

- the amount **received** is never computed from an official rate — `core/routes/` may not
  reach the official-rate machinery at all;
- a channel's `reference_rate` is never a **tax** rate — `core/tax/` may not reach the module
  that owns one.

Each is a separate `.importlinter` contract, because one contract naming both would stay
green if either half were deleted. The value-level claim — that no tax figure is *derived*
from a reference rate — is a source scan in
`tests/contract/test_the_rate_you_are_taxed_at.py`.

### 30.2 The base

For an amount denominated in something other than the tax currency:

```
base = amount × rate / quotation_unit
```

where `rate` is the series' declared value **for the event's own date** and `quotation_unit`
is how many units of the foreign currency that value is stated per. Nothing is averaged, no
period rate is used, no neighbouring date is borrowed, and no series the jurisdiction did not
name is consulted.

**The quotation unit has no default.** A published table that quotes some currencies per 1
unit and others per 100 is ordinary, and a value read at the wrong unit is wrong by two orders
of magnitude while looking entirely plausible. A series that omits it fails at load.

What load-time checking does *not* do is verify the unit is the published one. The provenance
gate recognises a sourced table by the observed values it carries, and `quotation_unit` is
the only one in a series' identity table — listing it as structural drops that table's
citation requirement altogether. So the unit is declared, non-defaulted, positive and
**uncited**: a wrong one is caught by a reader or not at all. The data file's own header
says so where a declarer meets it, and `scripts/check_provenance.py` records why the gap is
not closed here.

**The date is the one the taxable event already carries.** This machinery introduces no second
notion of when a taxable event happened: two modules with their own opinion about that is how
a tax figure becomes unreproducible.

**An amount already in the tax currency consults no rate at all**, and no rate-unavailable
reason is attached to it. A refusal for a rate nobody needed trains a reader to ignore true
ones.

### 30.3 Worked example

A synthetic series quoting hryvnia per dollar, one value per date — invented figures, as every
example in this project is:

| date | rate |
| --- | --- |
| 2026-03-02 | 41.50 |
| 2026-03-03 | 42.25 |

A receipt of 1 200.00 USD:

```
on 2026-03-02:   1200.00 × 41.50 = 49 800.00 UAH
on 2026-03-03:   1200.00 × 42.25 = 50 700.00 UAH
difference:      (42.25 − 41.50) × 1200.00 = 900.00 UAH
```

The date is load-bearing, not decorative. And the same rate quoted per a hundred units strikes
the same base:

```
1200.00 × 4150.00 / 100 = 49 800.00 UAH
```

Ignoring the unit would give 4 980 000.00 — not a near miss.
`tests/worked_examples/test_official_rate_base.py` holds the arithmetic.

### 30.4 A date with no declared rate refuses

Where no observation is declared for an event's date, the outcome is a **typed refusal naming
the series, the currency pair and the date**, and the covered window so a reader can see
whether the date is before it, after it or inside a gap.

Nothing interpolates, extrapolates, carries yesterday's value forward, or snaps to the nearest
observation. Each of those produces a number that looks exactly like a correct number, and
every tax figure downstream would inherit the invention with no mark on it. This is the same
answer §27.4 gives for a missing CPI month, for the same reason.

The one sanctioned alternative is a **declared non-publication-day rule**: a cited statement of
which observation governs a date the publisher does not publish for. It is data, it carries its
own citation, and the engine contains no notion of a weekend, a public holiday or a banking
calendar. Where a rule applies, the output states **which observation's date** supplied the
rate beside the event's own, so a Friday rate applied to a Sunday event is visible rather than
implied. Where no rule is declared, the refusal stands: the absence of a rule is not permission
to choose one.

### 30.5 What the Ukrainian series covers, and where its edges come from

`ua_nbu_usd` declares the National Bank of Ukraine's official hryvnia-per-dollar rate for
**every calendar day from 2019-12-28 to the date it was last retrieved**, and declares **no
non-publication-day rule**. Both facts have reasons that are not preferences.

**The lower bound is the publisher's own quotation unit.** USD is published per **100** units
through 2019-12-27 and per **1** from 2019-12-28. A series carries one `quotation_unit` for the
whole of itself and this one declares `1.0`, so an earlier date cannot be carried here without
either a lie about the unit or a value that is not the published one. Reaching back is a
**second series** with its own id and `quotation_unit = 100.0` — a data-only addition — and
none is declared. The fetch script reads the publisher's `units` on every row and **refuses the
whole run** where one differs, rather than normalising: a value divided to fit a declared unit
is no longer what the published table says, and re-deriving a base by eye against the
publisher's own page would stop working.

**The upper bound is the retrieval date, not the publisher's last available date.** The
National Bank publishes one calendar day ahead. An observation dated after its own
`retrieved_on` is refused at load — a rate for a date that has not arrived is a forecast
wearing an observation's clothes — so the script asks for the day ahead and **declines** it,
naming what it dropped. The next run picks it up as an ordinary observation.

**Everything outside that window refuses**, under §30.4, naming the window in real dates. A
projection cannot have a tax base: declared instrument payments reach into 2029, and no
official rate for those dates exists or ever could before they arrive.

**No rule is declared because there is no date for one to speak about.** A non-publication-day
rule is a cited statement of which observation governs a date the publisher does *not* publish
for, and the National Bank returns a rate for every calendar day, dated that day. The value
against a Sunday is retrieved *from the authority, against that Sunday*; each observation's
citation carries the publisher's `calcdate`, the working day whose establishment produced it,
so a weekend value is visibly the publisher's carry rather than this repository's. Declaring it
is entering a published fact; deriving it would be inventing one.

The calendar-free shortcut — *the latest observation on or before the event date* — stays
refused rather than adopted: it cannot tell a weekend from a gap in the series, and it would
make the refusal unreachable for exactly the dates the refusal exists for.

**Nobody has verified any of it.** Every `verified_on` is empty, so every tax figure struck
through one of these rates renders marked. Filling one is an act the owner performs against the
publisher's own presentation of *that date*; a re-fetch preserves an attestation whose value is
unchanged and clears one whose value the publisher has restated, because the attestation was
about a number.

### 30.6 What is **not** converted, and why that is the point

A **realised gain in a foreign currency refuses.** It is not an amount on a date: it is the
difference between proceeds received on one date and a basis struck on another, and each has
its own official rate.

Converting the difference at the disposal date's rate is not an approximation — it is the
arithmetic that deletes the thing being looked for. A position flat in dollars across a
devaluation realises **zero dollars**, and zero at any rate is zero hryvnia. Required test F1
— *a position flat in USD across a devaluation produces a positive taxable gain in UAH* —
would then be unfalsifiable, and it is the test the rewrite exists for.

What that case needs is a per-lot basis carried in both currencies with each leg struck at its
own date's rate, which is `specs/features.toml`'s `fx-tax-asymmetry-f1`. The dated rates it
needed are now here; the two-currency position is not.

### 30.7 The mark, and the age

A base struck through an official rate rests on **both** sides: the amount's own sources and
the rate observation's, unioned by the one function in the project that can produce an amount
in a different currency. An unverified rate marks a base struck from a verified amount, and a
marked amount survives a fully verified rate — neither launders the other.

Official rates age under their own declared kind, `official_rate`, whose threshold is declared
with it (§18). What decays is the **retrieval**: a published rate for a date that has passed is
a historical fact and does not go wrong, but the publisher adds a rate every calendar day, so a
series fetched long ago is short of its own end. Ageing a derived figure goes through each
citation's own kind, because that is the only thing that survives the merge of provenance a tax
base passes through.

---

## 31. A bond declared as the payments it will make

### 31.1 Why there are two forms and not one

§1 computes a schedule **from terms**: a face value, a coupon rate, an issue date, a
periodicity, a day count, a business-day rule. That form says one thing about the world —
*these are the issue's terms, and I know them* — and every figure derived from it is
checkable on paper against the contract.

A secondary-market purchase says the opposite thing. The platform that sells ОВДП publishes,
per issue, a **list of dated amounts**: no coupon rate, no periodicity, no day count, and
**no issue date**. Of those, the issue date is the one that is neither given nor derivable,
and extrapolating one backwards would be inventing a legal fact about a state security —
invisible once made, because a plausible date produces a plausible schedule and nothing ever
contradicts it.

So a declaration can be in one of two forms, and they are two **epistemic situations** rather
than two encodings of one thing:

| | says | states |
| --- | --- | --- |
| `fixed_income` | *I know this issue's full terms* | face, rate, issue date, maturity, periodicity, day count, business-day rule |
| `enumerated_schedule` | *I am buying a stream of dated payments; the issue's history is neither known to me nor relevant to what I will receive* | face, coverage start, the payments, a day count |

The issue date affects **no future cash flow of a purchase made today**, which is why
demanding one would be forcing an invention that changes no figure. What is bought by keeping
the forms apart is that no figure in this system rests on a date nobody published.

### 31.2 The arithmetic, such as it is

There is none. Every amount is

```text
declared amount per unit  x  units held
```

and every date is the date the declaration states. Nothing is generated, nothing is adjusted,
and no convention sizes anything. A payment falling on or before the purchase date went to
whoever held the paper then, exactly as a coupon does in §1.

**Each payment declares what it is** — `coupon` or `principal_repayment` — and that one
label settles two vocabularies at once: what the ledger records as having moved, and which
income kind the tax layer assesses. It is never read off the amount, the date or the position
in the list. `8305, 8305, 8305, 100000` is obviously three coupons and a repayment of
principal to a human and obviously nothing at all to a machine.

**A repayment retires its share of the repayments this holding *receives*** — the ones dated
after the purchase — so the stream as a whole retires the holding as a whole. One repayment
retires everything, which is what §1's redemption does; two equal ones retire half each.

Two things it is deliberately *not* a share of, and each was got wrong once on the way here:

- **Not the face value.** A schedule returning 1 050.00 against a declared face of 1 000.00
  is a bond redeemed above par: it repays the whole of each unit and realises a gain, where
  measuring against face would retire 1.05 units of every 1 held, which the ledger refuses.
- **Not every repayment the declaration lists.** A schedule that had already repaid half its
  principal before this buyer arrived sells units of what **remains**, so the remaining
  repayment retires the whole of what was bought. Measured against every repayment the paper
  ever made it would retire half, leaving basis stranded in a position that never closes —
  and reporting the stranded half as a realised gain on a trade that broke even.

The same reading decides the premium figure of §31.6, and it has to: *paid* versus
*received* would be measuring "received" two different ways in one projection otherwise.

### 31.3 The day count is a convention of computation, not a term of the issue

This is the one field that looks generative and is not, and it is the place this form can
most easily go wrong.

It is **required**, because the contractual yield of §3 cannot be annualised without one and
§3's root find forbids a hard-coded 365 — the yield would then disagree with the schedule it
was computed from. It describes how *we* turn a span of days into a fraction of a year.
Nothing about the paper is claimed by declaring one.

It is an input to **no figure describing the instrument's own terms**: not an amount, not a
date, not a schedule, not an accrual period, and **not a rate**. That last one is the whole
door:

```text
day count + one coupon amount + the interval between two coupons  =>  a coupon rate
a coupon rate + the spacing                                       =>  an issue date
```

— the invented legal fact the form exists to refuse, two steps from a required field. Two
locks hold it shut. `tests/contract/test_day_count_reaches_no_amount.py` changes the declared
convention in a copy of a declaration and asserts that the yield moves while **every
cash-flow amount stays bit-identical**; `tests/contract/test_nothing_is_inferred.py` scans for
the coupon-rate derivation itself. Two, because a guard that believes itself sufficient is
the one nobody adds a second lock to.

### 31.4 What a row says about the conventions that shaped it

§1's rows name three conventions. A row of declared payments names **one** and denies the
other two:

> no periodicity generated this date, no business-day rule moved it, and no day count sized
> this amount — the amount is declared, per unit, and is carried through unchanged. The day
> count named here annualises a span and does nothing else.

Both halves are load-bearing. A row that said *no day count was applied* would be false the
moment a yield is emitted from the same projection; a row that named all three would claim two
conventions that never ran. The canonical form of §12 renders the two statements differently
— three names for a generated schedule, `("declared", <day count>, <what the row says>)` for
a listed one — so a digest can never agree between them. What separates them is the **tag in
slot 0**: both renderings are three entries long, and no key of `PERIODICITY_FNS` may be
spelled `declared`, which is asserted rather than assumed. The three-name rendering is byte-for-byte what it has
always been, so no existing row's digest moved for this.

### 31.5 The accrual: what a dated quotation is worth on another day

A secondary-market price is a **dirty price**: it contains the interest accrued since the last
coupon, and it falls by the whole coupon on the day that coupon detaches. So a quotation read
on one morning is not the price on any other day, and both legs of a round trip are carried:

```text
period(t)   the declared accrual period containing t: [c_i, c_i+1)
accrued(t)  = C_i+1  x  yf(c_i, t) / yf(c_i, c_i+1)   under the declared day count
clean       = quote - accrued(observed_on)
price(t)    = clean + accrued(t)
```

**A period is bounded by two consecutive declared accrual boundaries**, and the two forms
declare a different number of them. §1's form states an issue date and its schedule generator
already opens the first accrual period there, so the period before the first coupon is
declared. A schedule of listed payments states no issue date at all: `covers_from` says where
the published **list** begins, not when interest began, and three shipped issues show the
difference is not academic — UA4000239081 declares 29 days from `covers_from` to a first
coupon of 82.20 that its own next period pays over 182. Opening the first period there would
accrue a whole coupon over a stub, and deriving the true start from the amounts is §31.7's
forbidden step. So a date in no declared period **refuses by name**, and the three leave every
answer as named refusals rather than as a shorter list.

**Worked, on UA4000236228** — coupon 85.50, declared dates 2026-03-11, 2026-09-09 and
2027-03-10 (182 days apart), `act/365`, quoted 2026-08-24 at 1089.32 to buy and 1087.89 to
sell, bought 2026-09-02 and sold 2026-10-01:

```text
accrued(2026-08-24) = 85.50 x 166/182 =   77.98      166 days into [03-11, 09-09)
accrued(2026-09-02) = 85.50 x 175/182 =   82.21      175 days into the same period
accrued(2026-10-01) = 85.50 x  22/182 =   10.34       22 days into [09-09, 03-10)

clean (buy)   = 1089.32 - 77.98 = 1011.34
clean (sell)  = 1087.89 - 77.98 = 1009.91   the two clean prices differ by the whole
                                            1.43 spread, and by nothing else
purchase 2026-09-02 = 1011.34 + 82.21 = 1093.55
sale     2026-10-01 = 1009.91 + 10.34 = 1020.24
```

The identity the whole model reduces to needs no decimals: the clean price cancels between the
legs, so per unit `sale + coupon - purchase = 85.50 x 29/182 - 1.43` — 29 days held at the
issue's own rate, less the round-trip spread.

**One assumption, stated once: the accrual is linear within a period.** The NBU depository
register publishes `pay_date`, `pay_val` and `pay_type` and nothing about how interest builds
between them, so the issuer's own formula is not available and a straight line is a choice. It
is declared with the owner's belief in `data/scenarios/quotation/` and reaches every figure
that leans on it (§34.2).

**The day count enters only as a ratio of two year fractions inside one period**, so §31.3
stands: a ratio yields no coupon rate, and no issue date can be extrapolated from one. It is
still computed with the declared convention rather than as a ratio of day counts, because the
two part company across a year boundary.

**A schedule declaring no coupon accrues nothing on every date**, and that is a figure rather
than a refusal: a zero-coupon bond earns its return in the price, and the formula reproduces
that with no special case.

### 31.6 The premium at purchase, and what governs it

A holding bought above face and held to the end of its schedule returns face, so the ledger
realises a **loss equal to the premium** — years later, at redemption, indistinguishable from
a market movement. That is why the difference is reported as its own figure at purchase:

```text
paid                 what the owner actually paid, in full
principal_returned   the repayments this holding will receive, times quantity
premium_or_discount  paid - principal_returned
                     positive premium, negative discount, zero par
realised_under       the declared class governing a disposal of this instrument
governed_by          the income category that class belongs to
treatment            outside | nets | per_event
```

**Against what comes back, not against the nominal face** (FR-025, amended 2026-08-30). For
a bond that repays its face once the two are the same number, which is every declaration
this repository ships. They part for a schedule that has already repaid part of its
principal: a buyer paying the remaining principal exactly has broken even, and the face-based
reading reported a discount of everything repaid before they arrived — somebody else's trade,
years earlier, named with the tax treatment that governs it. The figure and the ledger now
agree by construction, and a worked example asserts that they do
(`tests/worked_examples/test_enumerated_premium.py`).

The figure is **always present**, carrying a possibly-zero difference, on the same reading
that makes a zero tax charge cite its exemption: an absent figure meaning *bought at par* is a
silent default. And this adds **no premium rule** — no amortisation, no imputation, no branch
of its own. What becomes of the difference is the declared category treatment's business:

- `outside` — the category stands outside the annual calculation on both sides, income and
  costs alike, so the difference reduces no other base. **An exempt loss buys no shield**,
  which is Ukraine's answer for ОВДП and the unwelcome half of the exemption.
- `nets` — the difference reaches the year's netted base, and a negative year carries forward.
- `per_event` — nothing nets; the difference is realised on its own disposal and nowhere else.

The full cost stays the lot's basis. Nothing is amortised, nothing is imputed, and no part of
it is reclassified as accrued interest — even though §31.5 now separates the accrual out of the
price. What the buyer paid is what he paid; how the law treats the accrued interest inside it
is this section's premium figure and its declared category treatment, and nothing else.

### 31.7 What is inferred is declared, and the gate checks it

Four things about a transcribed schedule are nobody's statement, and each is declared **in the
file** as an inference rather than derived in code:

| inference | what it rests on |
| --- | --- |
| the **face value** | reading the largest payment in the list as the redemption amount |
| each payment's **kind** | a human reading a list of numbers that carries no labels |
| any **minor-unit conversion** | comparing a published figure with a buy price |
| the **coverage claim** | nothing the publisher says at all |

Each carries a citation beginning `INFERENCE:`, an empty `verified_on`, and a matching
`[[instrument.verification_task]]` saying what would settle it.
`scripts/check_provenance.py` refuses a declaration missing either half — its first check of a
*relation* rather than of a table's shape. No new kind of mark is introduced: an inference is
an unverified value, and §10.2's propagation carries it.

**Ordering is settled at transcription**, the same declared human step that turns kopecks into
hryvnia. The loader neither sorts an unordered list nor accepts one; where the source published
in an order other than ascending, the declaration **records the order it gave**. That an issuer
publishes the repayment of principal after a coupon dated later than it is a fact about how the
endpoint reports, and sorting the list is precisely the act that would delete it. Declaring the
ascending order is refused, so the field cannot become boilerplate.

### 31.8 Nothing downstream knows which form was used

Three modules outside the instrument layer read a generative field before this landed, and all
three now **ask the declaration a question both forms answer**:

| question | who asks | generative answers | enumerated answers |
| --- | --- | --- | --- |
| from what date are the terms known? | `core/ledger/seeds.py` | its issue date | its coverage start |
| what convention annualises a span? | `core/decision/tuple_outcome.py`, `core/results/project.py` | its day count | its day count |
| what should a row say about conventions? | `core/results/project.py` | three names | the one that annualises |
| what does a figure additionally exclude? | both | nothing | the dirty-price clause |

The observation that made this delegation rather than branching: **`seeds.py` never needed an
issue date.** It needed the earliest date from which the terms are known, and it asked for the
only spelling that existed.

`tests/contract/test_no_layer_knows_the_form.py` asserts that no module under the ledger, the
tax engine, the decision layer or the results names the second form — in code **or in prose**.
The one place that matches on it is `core/instruments/terms.py`, and that is the point:
somebody must answer, and answering once is what stops four modules deciding separately.

The property this buys is asserted end to end by
`tests/golden/test_enumerated_matches_generative.py`: a tuple on a bond declared by its terms
and a tuple on a transcription of that bond's own computed schedule produce equal figures and
tie in the ranking, differing only in identity, provenance, the stated exclusions, the
conventions statement and the causation detail prose.

## 32. The taxation scheme: what a stream is charged, and where it is credited

### 32.1 A scheme is a declared set of components, and one of them can be nothing

A **taxation scheme** is what an income stream is under: an identity, a variant, a reporting
cadence, and the set of separately named charges it levies. ФОП group 3, ФОП group 2 and a
legal entity are three of them, and **which one applies is a declaration** — nothing in the
engine knows any of their names.

Two kinds of component, and they differ in two independent ways:

| | trigger | base | asked about |
| --- | --- | --- | --- |
| **rate component** | income arriving | a share of the taxable base | a **date** |
| **periodic component** | a period elapsing | a statutory sum | a **period** |

A rate-shaped model of a periodic obligation gets the zero-income month wrong: it is owed in
a month with nothing in it. There is no `rate` field on a periodic component and no `amount`
on a rate one, so writing either as the other is an unrecognised field rather than a check
somebody has to remember.

```
charged = Σ over the scheme's rate components of  base × (rate in force on the credit date)
```

**Summed, never blended.** There is no combined-rate field anywhere: 6% of the base is the
same number as 5% + 1% and a different claim, and two components with independent legal lives
cannot be unpicked from a blended figure afterwards. These two have independent legal lives —
a different statute created one of them, on its own date.

### 32.2 The base is the credited amount at the official rate on the credit date

Feature 011's machinery, called unchanged and on a date this feature supplies (§30.2). The
credit date is the caller's fact: there is no clock in the core, no ledger event to read a
date off, and the date money is credited is not the date it is later sold on.

An arrival **already in the tax currency consults no rate at all**, and the currency is
checked before a series is touched — a false rate-unavailable reason on a figure that never
needed a rate trains a reader to ignore the true ones.

### 32.3 Three different ways a nil is nil

| claim | what produces it |
| --- | --- |
| *this scheme charges no such component* | `ComponentNotDeclared` — the scheme does not declare it |
| *it was charged and came to nothing* | a line of zero, **carrying the citation of the entry that produced it** |
| *it is declared and nothing is in force* | `ComponentRateUndeclaredBefore` / `PeriodicAmountNotInForce` |

Three types, so no caller can collapse them by accident. An uncited zero is the figure that
gets believed without checking, which is why the second carries its provenance exactly as a
non-zero value does — and the shipped ЄСВ nil is that case, sourced to **the owner's own
statement of his position** rather than to a public text, and saying so on its face.

### 32.4 A commencement is cited, and an end that is not a date is recorded

An event dated before a component's earliest entry is a typed error naming the component and
the date. It is **not** charged a rate of zero: *the schedule does not reach this date*, *the
rate was nil* and *this scheme charges no such component* are three claims and only the first
is true (§25.2 makes the same argument for an instrument's tax class).

A schedule that declares a commencement and no end **asserts a permanent charge**. Where the
end is real but is conditioned on an event rather than on a date, it is declared as recorded
**context** on the component: visible, cited, and not applied, with the reason it is not
applied required on the record. A comment could not do this — it cannot be rendered beside the
figure it does not move.

### 32.5 Worked example

An invented monthly credit under an invented scheme, at an invented official rate; the shipped
rates carry their citations in `data/tax/schemes/` and the values there are the owner's to
verify.

```
credited        = 2 500.00 USD   on the credit date
official rate   = 42.50 UAH per USD  for that date
base            = 2 500.00 × 42.50 = 106 250.00 UAH

component A 5%  = 106 250.00 × 0.05 =  5 312.50 UAH
component B 1%  = 106 250.00 × 0.01 =  1 062.50 UAH
charged         =  5 312.50 + 1 062.50 = 6 375.00 UAH
```

Checked in `tests/worked_examples/test_fop_scheme_charge.py`.

The periodic component's own example is the one that shows why it is not a rate. An invented
statutory sum of 1 760.00 UAH a month, over a quarter in which the *second* month brought in
nothing at all:

```
2026-01  income 12 000.00 UAH   charged 1 760.00 UAH
2026-02  income      0.00 UAH   charged 1 760.00 UAH   <- the month a rate gets wrong
2026-03  income  9 500.00 UAH   charged 1 760.00 UAH
                                total   5 280.00 UAH
```

The income column is there to be ignored: no income reaches `charge_periods` at all, because
the trigger is the month. Checked in `tests/unit/test_periodic_component.py`.

### 32.6 Where the income is credited decides which reading applies

The **crediting destination** is where income is credited for tax purposes. It is a declared
fact on the stream and it is **not** the routing origin: `arrives_at` is the venue every
funding route starts from, `credited_to` is the tax event's location, and neither is defaulted
from the other in either direction. For the owner today they hold different values — routed
through Deel, credited to a ФОП account — and a default either way would settle the tax
treatment by accident.

A normative table maps `(scheme × venue)` to a **verdict**, in feature 009's vocabulary:

- **INTERPRETED** — answered an inference deep from provisions a reader can go and check.
  Produces **a charge**, carrying the row's recorded judgement and its citations.
- **UNSETTLED** — no authoritative answer. Produces a **labelled scenario switch**: one figure
  per computable reading, each naming its reading and carrying that reading's own citations.
  **None of them is the tax owed**, and there is nowhere on the switch for a number combining
  two of them to live. What settles one is an індивідуальна податкова консультація of the
  owner's own.
- **no row at all** — a typed refusal naming the destination and the scheme. Two things close
  it and they are different: find a source that reaches the destination, and add the row with
  its reasoning.

Each reading recognises income on a date whose **name** is declared — two readings of one
destination can disagree about *when* income arises, and the caller supplies what each name is
worth. A reading whose name the caller did not supply refuses by name rather than borrowing
another reading's date, which would compute the reading it contests.

A candidate that needs a rate nobody declared is **named on the switch as uncomputed with its
reason**, never omitted: an omitted reading is how a switch comes to look complete when it is
not. Where *every* candidate is uncomputable there is no switch at all — a switch of zero
figures is a refusal wearing a switch's clothes.

**The verdicts are expected to move.** They rest on administrative positions rather than
statute. Moving one is a row in `data/tax/destinations/`, and nothing else: the verdict is a
declared word, every reading computes from a declared scheme, and no destination or component
name reaches the engine.

### 32.7 The base against the hryvnia actually received

The dollars on a ФОП account cannot be spent domestically; they are sold for hryvnia through a
declared channel, on a different date, at a different rate. Two numbers:

```
base      = credited amount × official rate on the CREDIT date
received  = what the declared sale produced on the SALE date  (§16, §17)
difference = base − received      signed, and outside the taxable base
```

**Nothing nets them.** The base was fixed at the credit date and no market rate moves it;
reporting only one of the two would hide whichever direction the exposure went in, and
subtracting one from the other as a *deduction* would assert a relief nobody cited. The sale
introduces no leg kind, no channel kind and no cost mechanism — it is an ordinary declared
corridor, and what this feature contributes to it is the tax consequence, which is that there
is none.

**The accepted limitation, stated with its name.** Modelling the sale as an ordinary corridor
means the data records *that* one route leaves the account and not *why* — the compulsion is
invisible. That costs nothing today, because a forced conversion and a chosen one price
identically and the only thing compulsion changes is which routes exist, which a declared
route registry already says. If a later feature needs to tell *nobody declared a route* from
*the law forbids one*, that is §20.2's deficit vocabulary being extended rather than a new
mechanism here.

Checked in `tests/worked_examples/test_base_versus_received.py`.

### 32.8 What is not modelled here

No deduction of any kind is applied to the base. The bank commission is answered at the
INTERPRETED level — the income is the whole invoice amount including it — and its citation
travels with the base; every other candidate deduction is an **absence, recorded** as an owner
verification task. A modelled zero deduction and an unasked question are different claims.

No payment timing, no filing deadline and no cash movement: a liability is recorded against
the period it accrues to, and when it is paid is feature 009's (§28). The reporting cadence is
declared and unused for exactly that reason — so the feature that models payment inherits a
declared fact rather than guessing one.

---

## 33. The candidate set: what the declarations offer, and what fell out of it

Every section above costs a tuple somebody handed the engine. This one **finds** them:
`SIMULATOR_SPEC.md` §4.10.2's *"infeasible candidates are dropped with the reason recorded,
because 'your preferred plan is impossible in March' is itself an output"*, at the tuple level.

### 33.1 What a candidate is, and what it is made of

A candidate is §29's `Tuple`, unchanged — the five declared terms — with one number beside it:
which of the caller's supplied run plans produced it. Both route terms are read off what §21's
`compose` emitted for the pair. Enumeration never chains two routes, extends a chain, or
decides that two routes join; every rule about what connects lives in §21.

The **one** construction it makes is the identity exit. Where an instrument's `proceeds_to` is
itself a declared spendable endpoint, the money has already come back out: there are no exit
legs to walk and none to charge for, and `compose` cannot emit that case because it is a fact
about the owner's declared list rather than anything a search can find (§20).

### 33.2 The question, and why every count carries it

A candidate set is enumerated for one stated question: an amount **per income stream in that
stream's own currency**, one horizon, an as-of date, a continuation assumption, the run plans
per instrument, the declared segment bound and one named regime.

Nothing converts one stream's amount into another's. That would need a rate valuing one
currency in another *for a return*, and neither declared rate is one: a channel rate is a
transaction price (§16) and an official rate is a legal reference for what an income was worth
on a date (§30). Reusing either conflates a currency role rather than filling this one.

The whole question travels with every count, because the question is what determines it.
Refusals turn on the amount, on the horizon and on the as-of date, so two runs over one
registry drop different candidates — and a drop count reported without its inputs is a figure
more confident than they are.

### 33.3 Three columns, and the two identities between them

    pairs considered      = pairs enumerated + pairs yielding no candidate
    candidates enumerated = evaluated        + dropped

Both are asserted, not described. The third column exists because a `Tuple` cannot be built
without a way in, so §29's union was never asked whether one exists — it was handed one. A pair
the routes do not connect is the **absence** of an option, and folding it into the drop count
would give a reader a number to divide by that means nothing.

That column carries a typed reason, and the two members call for opposite actions:

| reason | what it means | the remedy |
| --- | --- | --- |
| nothing connects | no declared route, within the bound, reaches the buying venue or leaves the venue the proceeds land at | declare a corridor |
| nothing needs to connect | the stream already arrives where the purchase happens | none — the money is already there |

Which one fired is read from `compose`'s refusal **record**, never by matching its words: a
sentence edited for clarity must not reclassify a pair whose remedy is the opposite one.

### 33.4 Pruning is §29's, and nothing else

A candidate is dropped only for a member of §29's typed refusal union. There is no feasibility
rule here, no pre-screen and no early exit that skips evaluation: every candidate is evaluated
in full, so nothing is ever excluded by an estimate. That is what makes the search version of
this checkable later — a label-correcting implementation must produce the same non-dominated
set brute force produces, on a registry small enough to run both.

The dropped records are kept whole, with their keys, and the per-reason tally is **derived**
from them on demand rather than stored beside them. Each group names the instruments, streams,
routes and missing declarations its members implicate, so the remedy is readable without
opening every record.

### 33.5 The ceiling refuses; it never truncates

How many candidates one enumeration may produce is declared data with no default, in
`data/candidates/`, on the precedent of the segment bound (§21) and the staleness threshold
(§18). Exceeding it returns **no** candidates and names both the ceiling and the count reached.

A reader's instinct is to cap and carry on, and it is exactly backwards. A truncated set
answers a different question from the one asked, with an audit trail that looks impeccable, and
every later pass over it — dominance, an objective, a stability check — would be a false
optimum. The ceiling exists to say *enumerating this registry has stopped being the right
primitive*, which is a finding the owner acts on and a silent cap would hide.

The other whole-enumeration refusals are the same shape: a reachable instrument with no
supplied run plan, two identical plans for one instrument, a way in or out naming an undeclared
route, and a `compose` refusal that is about the question rather than about one pair.

---

## 34. The question, the answer, and the sale at the window's end

§33 finds candidates for one horizon. This section answers a **question** — an amount, some
subjects, several horizons and a run plan for each — and it is the first output a person reads
rather than a test module.

### 34.1 What a horizon means, and the one figure this adds

A horizon means **the money comes out at its end**. An instrument whose own terms run past the
window is therefore **sold** on the window's last day rather than reported as impossible to
hold. The figure is:

```
price per unit = the declared resale quotation, carried to the sale date (§31.5)
               = clean + accrued(sale date), where clean = quote - accrued(observed_on)
proceeds       = units still held x price per unit
```

where `units still held` is the purchase plus every reinvestment, less whatever payments inside
the window already retired, and the resale quotation is a **declaration** on the access record
beside the purchase quote. The sale is a **disposal**: it consumes basis and realises a gain or
a loss under the instrument's declared disposal-gain class, exactly as a redemption at maturity
does. A sale below basis is what a spread *is*, and reporting it as a cash receipt would make
the cost of the early exit invisible in the ledger.

**Carrying is not a refinement of the quotation; without it the same money is counted twice.**
A quoted bond price falls by its coupon on the day the coupon detaches, so a quotation carried
forward unchanged credits the holding a coupon it collects inside the window *and* sells it at
a price that still contains that coupon. Under §31.5 that drop needs no rule of its own: a
coupon between two dates puts them in different periods, the accrual resets, and the drop falls
out of `price(t)`.

**Both legs are carried, and the purchase leg has no second leg to cancel its error.** The buy
quotation is carried to the settlement date for every bond purchase, including one held to its
own maturity, which is where nothing else would state the difference between the price on the
quotation's day and the price on the day the money arrives.

Payments falling after the window are **absent** from the stream rather than moved. Nothing is
paid early and nothing is folded into the sale.

Where an access declaration carries **no** resale price the early exit refuses by name —
`DeclarationMissing(part="access")`, naming `access.resale_price` — and the
remedy is a file rather than a longer window. The price is not inferred from the face value or
from the purchase quote: either would report a spread of **zero** that nobody observed. Where a
quotation cannot be carried to the date a price is wanted for, the candidate refuses by name
instead, and the remedy is a window rather than a file.

### 34.2 What the figure rests on, and how it errs

That the clean price a quote implies today still holds on another date is nobody's observation.
If a platform committed to its price that would be a *term*, and there would be no assumption;
the assumption exists because none does. It is declared under `data/scenarios/quotation/`, with
no default — an absent belief refuses at load — and every figure computed through it names it
in `TupleOutcome.rests_on`. It is **not the early exit's belief**: both legs of a round trip are
priced from a dated quotation, so a bond bought today and held to its own maturity leans on it
with no early exit anywhere in it.

Four claims travel with an early-exit figure, and **two of them carry no direction**:

| claim | direction | why |
| --- | --- | --- |
| it is a point where the world is a distribution | **more certain than it is** | the optionality is the reason the option was chosen |
| the spread is a seller's quote under today's conditions | **understated** | a seller's quote widens exactly when a forced sale is most likely |
| it carries no rate risk | **none** | rate risk is symmetric: a bond sold after rates rise fetches less than its spread implies, and one sold after rates fall fetches more |
| the clean price is assumed constant, and interest linear within each period | **none** | the clean price moves with the curve, and the curve moves both ways — the same cause as the row above, so it inherits the same silence about direction |

The fourth is on every sale a quotation was carried to, and on no sale struck on the
quotation's own day: nothing was carried there, so there is no claim to make. An approximation
whose sign is unstated is incomplete; one whose sign is asserted without a warrant is a number
more confident than its inputs, which is worse.

### 34.3 What the answer says, and what it refuses to say

One section per declared horizon, each carrying §33's whole survey or the typed refusal that
replaced it. Two rules are this layer's own:

* a candidate whose money the **holding released** after the window's end is **withheld** from
  that section, not labelled. Measured on the shipped registry, a one-month section would
  otherwise be one number — 18.11% over a span running to 2028 — wearing a caveat, and a reader
  takes the number. *Nothing could be ranked at one month, and here is why for each* is only
  available if the figure is withheld. Settlement latency on the way out is **not** what this
  rule is about: it sits inside the span, because waiting is a cost (§29);
* a stated **reserve** produces a verdict per candidate and removes nothing. There are two
  values and the second is a refusal — *a partial exit would be needed, and a partly-liquidated
  holding is not projected*. There is deliberately no third value asserting that a reserve
  *cannot* be met, and a reserve in a currency the arrivals do not deliver is short by the whole
  of it rather than converted at a rate nobody declared.

Nothing here optimises. There is no objective, no scoring weight and no shortlist; ranking is
§29's and the tie rule is §29's.

## 35. The working-day calendar: what a date is, and what it refuses

A **working-day calendar** says which dates a jurisdiction's law calls working. It is a
declaration — `data/calendars/<id>.toml` — and the engine derives nothing about a holiday from
anything.

### 35.1 The four words, and what each means here

| word | meaning |
| --- | --- |
| **rest day** | a weekday the jurisdiction's law makes a day of rest, declared as a pattern |
| **public holiday** | a date the law names as a holiday, declared as one enumerated row |
| **working day** | a date that is neither, including one an executive act moved into that status |
| **pre-holiday day** | a **working** day the law shortens because a holiday follows it |

A pre-holiday day is a working day, always. The answer carries the flag only on its working
member, so a pre-holiday non-working day cannot be built; a file declaring one fails at load,
naming the file and the date.

*Working day* is this section's word and *business day* is §1.3's, and they are not synonyms.
§1.3's means *not Saturday and not Sunday*, is uncited, and knows nothing about holidays. The
two notions coexist by owner decision CL-1 of 2026-08-30, and
`tests/contract/test_no_calendar_free_working_day.py` counts the sites that use the old one so
a fourth cannot appear quietly.

### 35.2 How a pattern and its exceptions combine

Each date inside the window is decided **once**, and the answer says by what:

1. the date's own enumerated row, if it has one — a public holiday, or a day a declared move
   turned into a rest day or a working day;
2. otherwise the declared **weekly rest pattern**.

Nothing else participates. There is no observance rule that shifts a holiday off a rest day and
no computation of a movable feast: whether the law moved a day is itself a declared row with its
own citation, because deriving it would be inventing a legal reading nobody has.

The answer carries the deciding declaration's provenance **and the coverage window's**. The
second is not decoration: *no row for this date* means *the law declared no exception here* only
because somebody read the law for this window. Without that claim it would mean *nobody
transcribed this date*, and the two are opposite.

### 35.3 Past the window it refuses, and says which way it missed

The window is declared as an explicit first and last date, and a question it does not reach
produces a typed refusal rather than a classification. Nothing extends the rest pattern past an
end, repeats the last declared year, or infers from an adjacent one.

| refusal | what it carries |
| --- | --- |
| no calendar with this id | the id wanted, and no window — nothing was found to have one |
| wrong scope | the id, the scope wanted, the scope found |
| out of coverage | the id, the date, the window, and which way it missed |

*Which way* is one of three: **before** the window, **after** it, or **the search ran off an
end** — the last being a date that *was* covered whose answer is not. The first two say the
question was outside what anybody read the law for; the third says it was inside and the answer
is one day past an edge. A next-working-day search that walks past an end, and a
last-working-day-of-the-week question whose week straddles one, both land in the third.

Which end to widen follows from the **question**, not from the reason alone: earlier for
*before the window*, later for *after* it, later for a forwards search that ran off and earlier
for a backwards one — and for the week question, whichever end its week crosses, which is the
one case the reason alone does not settle.

That refusal is the answer to the enumerated form's one weakness. An enumerated calendar goes
stale at its last declared year; declaring the window is what makes the staleness loud instead
of silent.

### 35.4 The shipped Ukrainian calendar declares no holidays

`data/calendars/ua_civil.toml` covers 2025-01-01 to 2026-10-30, rests on **Sunday alone**, and
enumerates **nothing** — because статті 53 і 73 КЗпП, the holiday list and the shortened
pre-holiday day, are not applied during martial law. The file states which provision says each
of those and why the window ends where it does; it is not restated here.

**Nothing consumes this calendar** (017 FR-015). It moves no coupon, no settlement and no
deadline, so no figure in this document changes because it exists.

## 36. Where to look next

| question | file |
| --- | --- |
| Is the schedule right? | `tests/worked_examples/test_ovdp_schedule.py` |
| Is the reinvestment right? | `tests/worked_examples/test_coupon_reinvestment.py` |
| Are the day counts right? | `tests/worked_examples/test_day_count.py` |
| What does a whole run produce? | `tests/golden/ovdp_synthetic_a.golden.txt` |
| Does the ledger conserve? | `tests/invariants/test_ledger_conservation.py` |
| What does a loss year cost if I do not file it? | `tests/worked_examples/test_loss_carryforward.py` |
| What does each basis method actually consume? | `tests/worked_examples/test_four_lot_methods.py` |
| When does the tax money leave? | `tests/worked_examples/test_tax_payment.py` |
| What happens if the cash is not there? | `tests/unit/test_insufficient_cash.py` |
| Can a figure hide which method produced it? | `tests/contract/test_method_is_never_implicit.py` |
| Is an unsettled reading of the law visible on the figure? | `tests/contract/test_unsettled_is_labelled.py` |
| What does the owner's own question actually answer? | `tests/golden/the_answer.golden.txt` |
| Is the arithmetic of a sale at the window's end right? | `tests/worked_examples/test_early_exit_sale.py` |
| Can a group be inferred rather than declared? | `tests/contract/test_group_membership_is_declared.py` |
| Is the run reproducible? | `tests/invariants/test_determinism.py` |
| Does the mark survive? | `tests/contract/test_provenance_propagation.py` |
| Is a new instrument really data-only? | `tests/contract/test_data_only_extensibility.py` |
| Does the ramp cost differ by stream? | `tests/worked_examples/test_two_streams.py` |
| Is deployable capacity honest? | `tests/unit/test_deployable_capacity.py` |
| Does a monthly cap bind, and is the excess reported? | `tests/worked_examples/test_monthly_cap.py` |
| Is anything silently clamped? | `tests/invariants/test_no_silent_clamping.py` |
| Does the ledger agree with the comparison? | `tests/invariants/test_cost_execute_agreement.py` |
| What is a dollar income worth for tax? | `tests/worked_examples/test_official_rate_base.py`, and against the National Bank's own declared rates `tests/worked_examples/test_nbu_official_rate_base.py` |
| What happens on a date the publisher skipped? | `tests/unit/test_official_rate_refusals.py` |
| Is the tax rate kept apart from the trading rate? | `tests/contract/test_the_rate_you_are_taxed_at.py` |
| What does the war ending change? | `tests/worked_examples/test_regime_transition.py` |
| Can an assumption be mistaken for an observation? | `tests/unit/test_transition_is_an_assumption.py` |
| Which comparisons can the declared registry support? | `tests/worked_examples/test_coverage_table.py` |
| Which observation should I make next? | `tests/unit/test_coverage_deficits.py` |
| Does the audit agree with what costing actually does? | `tests/invariants/test_coverage_costing_agreement.py` |
| What options do the declarations actually offer? | `tests/worked_examples/test_candidate_enumeration.py` |
| Does every discard land in the right column? | `tests/worked_examples/test_candidate_accounting.py` |
| Is a pair that connects nothing counted as a rejection? | `tests/unit/test_no_candidate_column.py` |
| Can every one of the seventeen refusals actually be reached? | `tests/unit/test_seventeen_refusals_through_the_loop.py` |
| Does enumeration build a route chain of its own? | `tests/contract/test_candidates_construct_nothing.py` |
| What does the whole candidate set look like? | `tests/golden/candidate_set.golden.txt` |
| Can a cost figure leak into the coverage report? | `tests/contract/test_coverage_no_figures.py` |
| What does a chain nobody declared end to end cost? | `tests/worked_examples/test_composed_arithmetic.py` |
| Does a composed round trip need a declared way out? | `tests/worked_examples/test_composed_exit_chain.py` |
| Do two hops over one card share its limit? | `tests/worked_examples/test_composed_pool.py` |
| Is the search a search rather than a router? | `tests/invariants/test_composition_search.py` |
| Could enumeration order reach the output? | `tests/invariants/test_composition_order.py` |
| Is a chain costed by the same function as a route? | `tests/contract/test_composed_same_costing.py` |
| Is the declared graph what I think it is? | `tests/golden/route_graph_wartime.mmd` |
| What does a destination with no way out look like? | `tests/golden/route_graph_normalized.mmd` |
| What does one costed route look like? | `tests/golden/costed_path_p2p.mmd` |
| Is there a second number-rendering rule? | `tests/contract/test_diagram_one_number_rule.py` |
| Do the marks survive the picture? | `tests/contract/test_diagram_marks.py` |
| Can a hostile venue name break a diagram? | `tests/unit/test_diagram_escaping.py` |
| What does a seeded lot realise on disposal? | `tests/worked_examples/test_seeded_disposal.py` |
| Does a guessed cost reach the tax figure? | `tests/contract/test_estimated_basis_propagates.py` |
| Do the seeded ledgers still conserve? | `tests/invariants/test_ledger_conservation.py` |
| Do the three goal modes agree? | `tests/invariants/test_goal_mode_consistency.py` |
| Is the goal arithmetic right? | `tests/worked_examples/test_goal_arithmetic.py` |
| What happens when a goal cannot be met? | `tests/unit/test_goal_feasibility.py` |
| Which rate applied, and when does a run stop? | `tests/worked_examples/test_rate_schedule_straddle.py` |
| Can two tax classes on one instrument collide? | `tests/worked_examples/test_two_tax_classes.py` |
| What does relying on the legal floor cost? | `tests/worked_examples/test_fund_liquidity.py` |
| What survives the spread and the tax? | `tests/worked_examples/test_declared_yield.py` |
| What happens when the peg's ceiling binds? | `tests/worked_examples/test_pegged_distribution.py` |
| Can a fund be asked for a Sharpe ratio? | `tests/contract/test_assumption_driven_refusal.py` |
| Is the deflation arithmetic right? | `tests/worked_examples/test_deflation_arithmetic.py` |
| What happens when prices fall? | `tests/worked_examples/test_falling_prices.py` |
| Is the subtraction approximation really absent? | `tests/contract/test_no_subtraction_approximation.py` |
| What does a CPI gap do to a real figure? | `tests/unit/test_cpi_coverage.py` |
| Can an assumption be mistaken for an observation? | `tests/contract/test_two_figures_never_blend.py` |
| Does a stale price index reach the real figure? | `tests/unit/test_cpi_staleness.py` |
| What does a whole tuple cost, end to end? | `tests/worked_examples/test_full_round_trip.py` |
| Are all three seams really anchored? | `tests/unit/test_chaining_refusals.py` |
| Is the benchmark the same figure it ranks? | `tests/contract/test_the_hurdle_is_a_tuple.py` |
| Is a new instrument, route, tax class and jurisdiction data-only? | `tests/contract/test_h1_data_only.py` |
| Does the ramp difference reach the holding? | `tests/unit/test_two_streams_two_outcomes.py` |
| What does a bond declared as its payments pay? | `tests/worked_examples/test_enumerated_schedule.py` |
| Do the two declaration forms really agree? | `tests/golden/test_enumerated_matches_generative.py` |
| Does a payment's declared label move a figure? | `tests/unit/test_payment_label_is_load_bearing.py` |
| What does a premium at purchase do? | `tests/worked_examples/test_enumerated_premium.py` |
| Can the day count reach an amount? | `tests/contract/test_day_count_reaches_no_amount.py` |
| Is anything inferred that should be declared? | `tests/contract/test_nothing_is_inferred.py` |
| Does any layer know there are two forms? | `tests/contract/test_no_layer_knows_the_form.py` |
| What does a scheme charge on a month's income? | `tests/worked_examples/test_fop_scheme_charge.py` |
| Is the base really the credit date's? | `tests/worked_examples/test_base_versus_received.py` |
| Can a switch ever hold a blend? | `tests/contract/test_readings_never_blend.py` |
| Does the engine know any scheme by name? | `tests/contract/test_no_scheme_is_named_in_code.py` |
| What is still uncovered? | `docs/REQUIRED_TESTS.md` |

---

The product specification is `docs/reference/SIMULATOR_SPEC.md`; the engine charter and the
audit of the predecessor project is `docs/reference/REWRITE_BRIEF.md`. Both are read-only
input material. The rules governing how any of this may change are in
`.specify/memory/constitution.md`.
