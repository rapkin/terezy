# Research: 016-real-ovdp

Every measurement below was made on **2026-08-31** against the live endpoint and the
checked-in observation, and each is reproducible by the script named beside it. The
specification's own measurements were re-derived rather than trusted; where a figure differs
from the spec's, the difference and its cause are stated.

## What the re-derivation confirmed

| Spec claim | Re-derived | |
|---|---|---|
| depository holds 195 issues, 3 634 payment rows | 195 / 3 634 | ✓ |
| 194 rows typed `2`, the rest `1` | 194 / 3 440 | ✓ |
| `val_code` UAH 176, USD 16, EUR 3 | identical | ✓ |
| nominal 1 000 on 186, nominal 1 on 9 | identical | ✓ |
| МФУ named on every row | one distinct `emit_name` | ✓ |
| all 24 active issues listed; 7 of the 8 completed absent | identical, and the 7 are named | ✓ |
| the coupon equals `auk_proc × nominal ÷ 200` exactly on all 24 | zero violations | ✓ |
| every Inzhur amount is exactly 100× the depository's | holds on all 24 | ✓ |
| 15 issues one day early, 9 agreeing | **the same 15 ISINs and the same 9** | ✓ |
| `UA4000235782` publishes `2027-06-03` for `2027-06-02` | identical | ✓ |
| `UA4000235865` publishes its principal `2026-09-15`, out of order, against `2026-09-16` | identical | ✓ |
| `matures_on` equals `pgs_date` on all 24 | no exception | ✓ |
| spread 0.000% to 0.637%, median 0.237%, five issues quoting buy equal to sell | identical, and the five are the named five | ✓ |
| 11 of 24 active issues publish `available_quantity = 0`; completed `UA4000234215` publishes 14 473 | identical | ✓ |
| no payment within two days of a year boundary | the closest is five days (`2027-01-06`, `UA4000230270`) | ✓ |

## D1 — The depository's `date` parameter selects nothing, and the observation must not claim it does

`?json&date=20200101`, `?json&date=20260830`, `?json&date=20260831` and the bare `?json` all
return **byte-identical** payloads (SHA-256 `c6af0ac1…`, 576 037 bytes, 195 issues). The
parameter is accepted and ignored.

**Decision.** The fetcher sends its own retrieval date, and the observation file records the
retrieval date and the URL — never "the register as of" any other date. The finding is
recorded in the script's header so nobody builds a historical query on it.

*Alternative rejected*: omitting the parameter. The spec names the URL with it, and dropping it
would make the recorded citation differ from the one the specification cites.

## D2 — The whole register is snapshotted, not the 24

The endpoint returns 195 issues and 3 634 payment rows; the 24 declared issues account for 158
rows. Writing only those would be a **filter**, and the filter's criterion — "the ISINs a
seller lists as active" — is a judgement, which is precisely what `fetch_inzhur.py`'s own
docstring refuses to let a fetcher make.

**Decision.** The observation is the whole register. It costs about 29 000 lines and 1.3 MB,
roughly doubling `data/`.

Two things need it beyond tidiness. FR-008's refusal is *"an active issue the depository does
not list"*, and an observation restricted to the issues we declared cannot witness an absence —
the check would be circular. And SC-011 asserts that refusal against a scratch register with
one issue removed, which needs the membership to be in the file rather than in the fetcher.

*Alternative rejected*: a compact form with one citation per issue covering an inline array of
payments. `scripts/check_provenance.py::check_table` recurses into arrays of tables and
requires a citation on every one carrying a number, so the compact form is not available under
the gate. Parallel `payment_dates` / `payment_values` arrays would evade it and were rejected
for the reason they evade it: two arrays that can differ in length make a wrong state
representable.

## D3 — `covers_from` is the placement date, and that is not FR-007's forbidden field

The form requires a coverage start and refuses a purchase before it. The obvious candidate —
the earliest payment in the list — breaks: `UA4000239107`'s first payment falls on
`2027-02-10`, while the owner's question buys on `2026-09-01`, so a coverage start there would
refuse a purchase the issue plainly admits.

**Decision.** `covers_from = razm_date`, the depository's placement date, on all 24.

That is what the coverage claim *is*: the spec's own table gives coverage as a retrieved fact
whose warrant is *"depository list runs placement → maturity"*. FR-007 forbids a declaration
carrying a **placement-date field**, and its stated reason is reconstruction — *"`auk_proc`
with `razm_date` in hand is exactly the condition under which someone reconstructs a schedule
the issuer already published"*. `covers_from` reconstructs nothing without a periodicity, and
no periodicity is declared. Every `razm_date` in the 24 falls between `2020-01-28` and
`2026-08-11`, so all are at or before both the earliest payment (SC-005) and the purchase.

## D4 — `published_in_order` is absent from all 24

The field records that a source published its payments in an order other than ascending, and
the loader refuses a list identical to the ascending one as boilerplate. The depository
publishes all 195 schedules in ascending date order, checked.

**Decision.** No declaration carries the field. FR-009a's rule — the field would carry the
**depository's** order, because that is what the schedule is transcribed from — resolves to an
absence rather than to a value, and `UA4000235865`'s out-of-order publication stays where it
belongs, in FR-009's check over the two observation files.

## D5 — The minimum ticket, retrieved (owner verification task 1, closed)

Retrieved 2026-08-31 from `https://www.inzhur.reit/offer/ovdp`, the venue's own offer page for
these issues, in its FAQ:

> «Мінімальний обсяг покупки — від 1 цінного паперу, що дорівнює приблизно 1000 грн.»

and, in the page's summary line, «Початкова інвестиція від 1 облігації».

**Decision.** `min_unit = 1.0` and `min_ticket = 1000.0 UAH`, cited to that page with its own
retrieval date, on all 24. It restates no access price: the buy quotations run from 989.47 to
1 081.23 and no two are alike.

**What the word «приблизно» costs, stated rather than smoothed.** The venue's floor is really
in *units*; the money figure is its own approximation of one unit. One issue — `UA4000207518`,
quoted at 989.47 — is quoted below it, so a purchase of exactly one unit of that issue would be
reported infeasible by 10.53 UAH. That is the venue's published figure rather than this
project's reading, and an overstatement refuses a feasible purchase where FR-018's severity
argument is about the understatement that permits an infeasible one. It is asserted as a test
rather than left in prose, so it cannot go quietly wrong when a quotation moves.

## D6 — The reconciliation is computed against the depository's schedule

FR-017 asks for an internal rate of return over each issue's buy quotation and **its remaining
payments**. The payments a declaration makes are the depository's, so that is what the check
computes over.

Measured over the 24 active issues, act/365, as of the seller's retrieval date 2026-08-24:

- **19 of 24 agree within 0.09 pp**, and all 19 within **0.001 pp**.
- **5 disagree**, ours higher in every case: `UA4000234413` +0.641, `UA4000238281` +0.799,
  `UA4000237416` +0.802, `UA4000236624` +0.910, `UA4000235865` +0.979 pp. They are exactly the
  five with one coupon remaining after the retrieval date.

**This differs from the spec's figures, and the cause is the source, not the method.** The spec
reports 0.756 to 1.662 pp and 7 within 0.001 pp. Computed over the **seller's** schedule the
same code reproduces the spec exactly — 19 within 0.09, 7 within 0.001, residuals 0.756,
0.951, 0.992, 1.237, 1.662. So the spec measured the seller's list, this check measures the
declaration's, and the declaration's reconciles **better**: 19 issues to a thousandth of a
percentage point instead of 7. That is corroboration of the transcription rather than a
discrepancy in it, and it is the direction one would want.

The residual on the five is a convention difference on a short residual maturity, as the spec
established and this re-derivation leaves untouched: the five are exactly the single-coupon
issues under both readings.

## D7 — Where the resale price lives, and what closes

`InstrumentAccess.resale_price` and the `[access.resale_price]` table already exist: 015 built
them and shipped them empty, and `DeclarationMissing(part="access")` is already the refusal.

**Decision.** The seller's observed **sell** quotation is declared there, on the access record,
beside `[access.price]` and with its own citation. `TupleRefused` stays at seventeen and
`DeclarationMissing.part` stays a five-member literal. 015 FR-031's open question closes on the
first of its two branches.

**This overrides 016 FR-014**, which forbids declaring the sell quotation and states its own
condition for doing so: *"Nothing in this engine prices a disposal before the end of a
schedule, so a declared sell price would be read by nothing."* 015 landed `EarlyExit`,
`InstrumentAccess.resale_price` and `[access.resale_price]`, so the condition is gone — and the
repository's own landed data says which feature was expected to fill it, in
`data/scenarios/early_exit/owner-001.toml`: *"The day feature 016 declares a seller's quote,
this is what says the quote may be used for a date nobody has quoted."* FR-014's other half
survives intact and is FR-015: the spread is not the round trip and is never presented as one.

Two success criteria are narrowed with it, and the narrowing is stated rather than assumed:

- **SC-009**'s second clause — *"no declared value anywhere in `data/` equals a published sell
  quotation"* — is the direct statement of FR-014 and falls with it.
- **SC-012** stands as written for the **spread**, which is what FR-015 forbids presenting as a
  round trip. Declaring the two sides of a quotation is not declaring the gap between them, and
  no declaration, result record or rendered figure carries that gap.

**The five drops 015 reports do not close, and could not.** They are
`ovdp_synthetic_a`, `ovdp_synthetic_b`, `ovdp_enumerated_a`, `ovdp_enumerated_mirror` and
`enumerated_out_of_order` — every one a fixture, and no seller quotes a resale price for an
invented bond. Inventing one would put a made-up spread inside the only worked examples a
reader can check on paper. What this feature changes is that the 24 real issues **do not join
them**: they carry an observed sell quotation and are priced at an early exit rather than
refused.

## D8 — Two facts about the shipped access declarations that the 24 must not copy

`bought_at` and `proceeds_to` are both `inzhur` on every shipped entry, and the risk class
`sovereign_debt` is the word the four government-bond fixtures already use. Both are carried
unchanged for the 24: an ОВДП bought at Inzhur is reached exactly the way the fixtures modelled
it, and inventing a new risk word for the real issues would make the fixtures' word mean
something narrower without saying so.

## D9 — The tax classes are the shipped ones and the file states no rate

Every one of the 24 pays coupons and repays principal, so each declaration names
`ua_government_bond` for `coupon` and for `disposal_gain` — the two kinds its payments produce,
which is what the loader requires. No rate, category or treatment is declared here (FR-026).

## Owner verification tasks, after this feature

| Spec task | State |
|---|---|
| 1. the venue's minimum ticket and minimum unit | **closed** by D5's retrieval |
| 2. which date governs a coupon's tax date where the sources disagree | **open**, unreached: the closest payment to a year boundary is five days away |
| 3. whether the depository is sufficient for a completeness claim | **open**, and carried into every declaration's `coverage` verification task |
