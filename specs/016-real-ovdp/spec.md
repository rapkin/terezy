# Feature Specification: The first instruments that are not fixtures

**Feature Directory**: `specs/016-real-ovdp`

**Feature Branch**: `spec/016-real-ovdp`

**Created**: 2026-08-30

**Status**: Ready for planning — no clarifications open (see *Decisions*).

**Input**: Turn the ОВДП observations already retrieved into declared instruments, and settle
what `verified_on` may be filled from. The owner's instruction on 2026-08-30 was that **the
reality of the data comes before any claim about the data** — he deferred an
independent-ledger-oracle feature on exactly that ground, because two implementations
agreeing about invented numbers proves little.

**Revised 2026-08-30**, after a primary source for the issues' terms was found and probed.
The revision changed the answer to the central question rather than decorating it, and it
found two errors in the seller's published data that the first draft would have transcribed.

---

## Why this feature exists

Seven of the nine shipped instruments are fixtures, and **732 values across 31 files carry an
empty `verified_on`** — measured 2026-08-30 over `data/`. Of those, 193 are the observation
file itself, which is evidence rather than declaration; **539 sit in 30 files the engine
loads**. Not one non-empty verification date exists anywhere in the repository. Every figure
this project has ever produced is arithmetic over invented terms, correctly marked as such and
therefore correctly worthless as an answer.

There are now **two** sources, and the whole of this feature turns on keeping them apart.

- **`data/observations/inzhur.toml`**, retrieved 2026-08-24 from
  `https://www.inzhur.reit/_api/assets`: 37 observations — 32 ОВДП issues and 5 funds — with
  ISINs, maturities, two-sided quotations, the platform's own stated yields, and **156 payment
  rows across 32 schedules**. A **seller's** publication.
- **`https://bank.gov.ua/depo_securities?json&date=YYYYMMDD`**, probed 2026-08-30: the
  National Bank's depository record for government securities. **195 issues, 3 634 payment
  rows**, `emit_name` «Міністерство фінансів України» on every one. The **issuer's** record,
  through its depository.

They carry different kinds of fact. The depository has the **terms** — what the paper is and
what it will pay. Inzhur has the **price you can actually transact at**, its spread, its
availability and the route by which it is reached. Neither can answer the other's question,
and a declaration must show which half came from where. That is what provenance is for.

### The two things that make this a feature and not data entry

**A fetcher may not declare.** `scripts/fetch_inzhur.py` says so in its own docstring and
stops on purpose: *"a fetcher that rewrote those files would delete the reasoning and keep the
digits."* The cross-check below is the proof of that claim rather than a restatement of it —
two automatic transcriptions of the same schedule, from two sources, disagree on 15 of 24
issues, and one of the two is wrong in two places. Only a human comparing them finds that.

**Retrieval is not verification — but with a primary source it can become it.** This was the
question the first draft had to leave permanently open, and it is now answerable field by
field. See *The spine*.

---

## The measurement

Every number below was read on **2026-08-30** — the Inzhur figures off the checked-in
observation (retrieved 2026-08-24), the depository figures from a live probe the same day with
`curl --compressed`. All are reproducible.

### The seller's publication

| | |
|---|---|
| observations | **37** — 32 bonds, 5 funds |
| `status = "active"` | **27** — 24 bonds, 3 funds |
| payment rows | **156** across 32 schedules; **133** in the 24 active issues |
| payments per active issue | 3 to 9, median 5 |
| a payment of exactly `100000` | in **32 of 32**, the largest in every one, exactly once each |
| every published amount | an integer; 26 distinct values, from `4895` to `100000` |
| quoted above 1 000.00 | **31 of 32**; the exception is `UA4000207518` at 989.47 |
| published out of ascending date order | **1** — `UA4000235865` |
| a currency, anywhere in the file | **none**, and `scripts/fetch_inzhur.py` reads none from the endpoint |

**The seller's round trip on an immediate resale**, over the 24 active bonds, as
`(buy − sell) / buy`: minimum **0.000%**, maximum **0.637%** (`UA4000239081`), median
**0.237%**, mean 0.237%. **Five active issues quote buy equal to sell** — `UA4000236475`,
`UA4000238281`, `UA4000238968`, `UA4000238976`, `UA4000239016` — and a sixth, completed,
`UA4000230809`. The median is over the 24 active issues; over all 32 it is 0.105%, because the
eight completed ones are inside it.

**Availability contradicts status.** Only **13 of the 24** active issues showed any stock at
retrieval. And one **completed** issue, `UA4000234215` (matured 2026-06-24), showed 14 473
units on offer. Neither field is declared, and `status` decides one thing only — which files
get written.

### The issuer's record

| | |
|---|---|
| issues in the depository | **195** — 186 with a nominal of 1 000, 9 with a nominal of 1 |
| payment rows | **3 634** — 3 440 typed `1`, **194** typed `2` |
| issuer named on every row | «Міністерство фінансів України», `emit_okpo` 00013480 |
| currency, stated explicitly | `val_code`: **UAH 176, USD 16, EUR 3** |
| coupon period | 182 days on 148 issues, 365 on 24, 364 on 23 |
| per issue | `cpcode`, `nominal`, `auk_proc`, `pgs_date`, `razm_date`, `pay_period`, `val_code`, `total_bonds`, `cpcode_cfi`, and a `payments` array of `{pay_date, pay_type, pay_val}` |

**`pay_type` labels the payment kind.** 194 of the 195 issues carry exactly one row typed `2`
against `nominal`; the rest are typed `1`. The kind is stated, not read off the shape of the
numbers. (The one exception, `XS3261834314`, is a foreign-law issue and is not among the 24.)

**Terms of use, read at the texts rather than at the publisher's page.** Two documents, and
they say different things:

- **Стаття 10¹ ч. 2 Закону України «Про доступ до публічної інформації» (№ 2939-VI)** — the
  statute, read at `zakon.rada.gov.ua/laws/show/2939-17` on 2026-08-30: *«Будь-яка особа може
  вільно копіювати, публікувати, поширювати, використовувати, у тому числі в комерційних цілях,
  … публічну інформацію у формі відкритих даних з обов'язковим посиланням на джерело отримання
  такої інформації.»* Free reuse including commercial, **conditional on a reference to the
  source**. The word «гіперпосилання» does not occur anywhere in the Act.
- **Пункт 17 Положення, затвердженого постановою КМУ від 21.10.2015 № 835**, read at
  `zakon.rada.gov.ua/laws/show/835-2015-п` the same day — the source of the hyperlink wording.
  It prescribes *the text of a notice the publisher displays* on each dataset page
  («розпорядник інформації розміщує таку інформацію»), and that notice's third paragraph reads
  *«Умовою будь-якого подальшого використання відкритих даних є обов'язкове посилання на джерело
  їх отримання (у тому числі гіперпосилання на веб-сторінку відкритих даних розпорядника
  інформації)»*.

So the obligation this repository is under is the statutory one — **a reference to the source**.
The hyperlink appears in the wording of a publisher-facing notice and is not a statutory duty on
a reuser, and this specification does not claim otherwise (FR-013). `bank.gov.ua/ua/open-data`
reproduces п. 17's notice under the heading «Відповідно до статті 10-1», which is where the two
can be mistaken for one.

Two details make the reading firm. п. 17's own clause is «**у тому числі** гіперпосилання» — a
hyperlink named as *one way* of referring to the source, not a second obligation beside it, so
even inside the notice it adds nothing to the duty. And the fragments the first draft quoted said
«**зокрема** в комерційних цілях» where the statute says «**у тому числі**» — that one word is the
fingerprint proving both came from № 835 rather than from the Act.

**For whoever retrieves these next: a browser `User-Agent` and `/print`, both.**
Measured on `zakon.rada.gov.ua/laws/show/835-2015-п`, 2026-08-30. Without a `User-Agent`
every path returns **403** with an identical stub carrying **zero** occurrences of the
searched word — `/print` included, so appending it is not the fix on its own. With one, the
bare URL and `/card` return **HTTP 200** carrying a longer page that still has **zero**
occurrences: a success status on an incomplete document, and a far more convincing false
negative than a 403. Only `/print` with a `User-Agent` returns the full text, where the word
appears **seven** times. Both variables, or a reader reproduces the negative result that
misled the earlier hands.

Field documentation exists as `Instr_API_depo_securities.pdf` and `Data_set_fields_OVDP.pdf`
under `https://bank.gov.ua/admin_uploads/article/`, both confirmed reachable on 2026-08-30.

### The cross-check, and what it found

All **24 active** Inzhur issues are in the depository. Of the 32, **25** are present; the
**7 absent are all `completed`**, and one completed issue — `UA4000234215`, the one showing
phantom stock — is still listed. So the scope this specification chose independently, the 24
active issues, is exactly the intersection.

**1. The 100× is real, and it is kopecks — not a hundred-bond lot.** This was reported to this
specification as Inzhur quoting a 100-unit lot. It is not, and the difference matters more than
the agreement does, because the two readings fail in **opposite directions**:

- The depository gives `UA4000234413` a nominal of **1 000** and coupons of **83.05**; Inzhur
  publishes **100000** and **8305**. The ratio is exactly 100 on all 24 issues, which both
  readings predict.
- What separates them is the **price**. Inzhur quotes that issue at **1 025.59**. A hundred
  bonds of 1 000 nominal is a 100 000 nominal, and 1 025.59 would be **one per cent of face** —
  a sovereign in default, not a bond at a 16.61% coupon. One bond of 1 000 nominal at 1 025.59
  is a 2.6% premium, which is what a 16.61% coupon fetches in a ~15% market.
- A second, independent confirmation: across the 24 issues the depository's coupon equals
  `auk_proc × nominal ÷ 200` **exactly**, and the one issue Inzhur quotes **below** par —
  `UA4000207518` at 989.47 — is the one with by far the lowest coupon, 9.79% against 15.15%
  to 18.50% for the other 23. Two sources agreeing on a direction neither was asked about.
- And the reconciliation below already tested it: the internal rate of return computed on
  amount ÷ 100 lands within 0.09 pp of the seller's own stated yield on 19 of 24 issues. On
  the lot reading it would not land anywhere near.

So 013's kopeck reading is right, and **the lot reading would make every declaration a hundred
times too large** — in the cost basis of every figure. The two readings are separated by the
price and by nothing else, which is why the separation is written down rather than assumed.

**2. The dates disagree, on 15 of 24 issues and not on all of them.** Aligning each schedule on
its final payment:

- **15 issues**: every Inzhur date is exactly **one day earlier** than the depository's —
  `UA4000233712`, `UA4000234223`, `UA4000234413`, `UA4000235196`, `UA4000236228`, `UA4000236475`,
  `UA4000236624`, `UA4000237416`, `UA4000237556`, `UA4000237804`, `UA4000238281`, `UA4000238968`,
  `UA4000238976`, `UA4000238992`, `UA4000239008`.
- **9 issues**: the dates agree exactly — `UA4000207518`, `UA4000230270`, `UA4000231195`,
  `UA4000235782`, `UA4000235865`, `UA4000239016`, `UA4000239040`, `UA4000239081`, `UA4000239107`.
- Both sets are named rather than counted because a check asserting only that *fifteen* issues
  carry the offset would pass if the wrong fifteen did (SC-007).
- On **all 24**, Inzhur's own `matures_on` equals the depository's `pgs_date`. So for those 15,
  Inzhur's schedule contradicts **Inzhur's own maturity field** — which is the disagreement 013
  measured from one side (`matures_on` differs from the last published payment in 18 of 32) and
  could not explain.

A rule of "the seller is always one day early" is therefore false, and adopting it would have
been worse than useless, because it would have silently absorbed the next finding.

**3. Two of the schedules are simply wrong, and one of them is load-bearing for 013.**
After shifting each schedule by its own offset, 22 of 24 are an exact subset of the
depository's list. Two are not:

- **`UA4000235782`** — Inzhur publishes `2027-06-03`; the depository says `2027-06-02`. Every
  other date in that schedule matches exactly. A single wrong date inside an otherwise correct
  list.
- **`UA4000235865`** — Inzhur publishes the principal repayment on `2026-09-15`, one day
  **before** the final coupon. The depository puts **both on `2026-09-16`**, the ordinary way a
  bond ends. **So the one issue that publishes its payments out of date order is publishing an
  error**, not a fact about how the issuer pays. 013 built a fixture and a requirement
  (FR-020a) around keeping that ordering as an observation about the source; the mechanism
  stays right and its real-world instance turns out to be a mistake — which is a stronger
  reason to record what a source published, not a weaker one.

**Which date governs a coupon's tax date is not guessed here.** The depository is the issuer's
own record of when it pays and the seller's page is not, but nothing in this repository has
ruled on it. The consequence to hold: at a year boundary the two sources would put a payment in
**different tax years**. Checked, 2026-08-30 — **no payment in the 24 lands within two days of
a year boundary**, so the case is unreached today. It is stated as a rule with its date rather
than left for someone to meet by accident (FR-009).

### Reconciling the seller's own yield against the schedule it published

Each bond carries `return_rate_buy_pct` and `return_rate_sell_pct` — the platform's forecast
about itself, which `scripts/fetch_inzhur.py` carries verbatim and never computes from. That
makes them useless as an input and valuable as a **check**: an internal rate of return over the
buy quotation and the payments falling after the retrieval date, on act/365, is a figure this
project can compute for itself.

Measured over the 24 active issues:

- **19 of 24 agree within 0.09 percentage points**, and 7 of those to within 0.001 pp.
- **5 disagree by 0.756 to 1.662 pp**, our figure higher in every case: `UA4000234413`,
  `UA4000237416`, `UA4000236624`, `UA4000238281`, `UA4000235865`.
- Those five are **exactly** the five issues with only one coupon remaining after the retrieval
  date. On a simple-interest reading the same five reconcile to within 0.1 to 0.6 pp while the
  long-dated issues diverge by up to 3.3 pp, so the residual is a convention difference on a
  short residual maturity and not a transcription error.

That inference — *the residual is a convention, not a mistake* — is what a fetcher cannot make
and a human can, and it is now one of three such judgements this feature records.

---

## Why the enumerated form, now that the terms are known

013 exists because a real ОВДП's schedule *"cannot be derived from a rate and a period"* — no
issue date is published, so the generative form would force one to be invented. The depository
publishes `razm_date`, `auk_proc`, `pay_period` and `nominal`, so a reader will reasonably ask
whether that argument has expired. It has not, and the reason is better than the one it
replaces:

- The depository publishes **the payment list itself**, complete from placement to maturity.
  Deriving a schedule from a rate and a period, when the issuer has published the schedule,
  substitutes our arithmetic for the issuer's statement.
- Doing so would require inventing a convention. On all 24 issues the coupon equals
  `auk_proc × nominal ÷ 200` — a rate halved for a 182-day period, which is neither act/365 nor
  act/act — and **the depository does not name the convention**. A generative declaration would
  have to pick a day count and a business-day rule that happen to reproduce the numbers we
  already have, and the ones we picked would then be an undeclared claim about the paper.

So: enumerated, and the schedule is now a **retrieved statement by the issuer** rather than an
inference from a seller's list. That is what changes the spine.

---

## What a declaration needs, and where each fact comes from

| A declaration needs | Source | Status |
|---|---|---|
| identity | ISIN, both sources agree | carried |
| currency | depository `val_code` | **retrieved fact**, no longer inferred |
| face value | depository `nominal` | **retrieved fact** |
| payment dates and amounts | depository `payments[]` | **retrieved fact**, in major units — no conversion at all |
| payment kinds | depository `pay_type` | **retrieved fact**, labelled by the issuer |
| coverage | depository list runs placement → maturity | **retrieved fact** |
| day count | neither | a project convention (013 FR-003a) |
| purchase price | Inzhur `buy` | a dated seller's quotation — the one value nobody can ever verify |
| minimum ticket, minimum unit | neither | a second cited retrieval of the venue's dealing terms (FR-018) |
| issue date, coupon rate, periodicity, business-day rule | depository has them | **forbidden by the form** (013 FR-003), and not needed |
| maturity date | depository `pgs_date` | forbidden by the form; used only to align the cross-check |
| stated yields, availability, status | Inzhur | declared nowhere (FR-012, FR-017) |

**Every one of 013's four inferences is settled by the depository.** The face value, the payment
kinds, the minor-unit conversion and the coverage claim were inferences because the only source
was a seller's list of unlabelled numbers. They are now the issuer's own statements. That is
the good news, and it collides with the shipped machinery — see FR-011.

---

## The spine: what `verified_on` may be filled from

### What the repository says

`SourceRef.verified_on` in `src/terezy/core/primitives/provenance.py` defines it as *"when the
value was checked against a **primary source**"* — not *checked against the page it was
downloaded from*. `data/README.md` rule 2 requires the key present and permits it empty.

### The answer, field by field

| Class | Values | Primary source | May carry a date? |
|---|---|---|---|
| **Terms of the issue** | currency, face value, payment dates and amounts, payment kinds, coverage | The NBU depository, naming МФУ as issuer on every row | **Yes.** This is the change. |
| **Terms of dealing** | minimum ticket, minimum unit | The venue — it is primary for its own conditions of dealing | **Yes** |
| **The quotation** | the buy price on 2026-08-24 | **None, and there never will be** | **No, permanently** |

The first draft of this specification concluded that *nothing* here could ever carry a
verification date. That conclusion was correct on its premise and the premise is gone: a
maturity, a nominal, a coupon schedule and a currency can now be checked against the issuer's
depository. **The terms are verifiable; the price never is.**

The reason the price is different is not that nobody has got round to it. A dated offer by a
seller has no independent record, and it cannot be re-read afterwards — the page shows a
different number tomorrow — so the field stays empty, as the existing convention already has it.
No rule is built on that: the price came from the nearest real source, it carries that source and
its retrieval date, and that is enough (owner decision, 2026-08-30).

### The consequence

Because taint is asymmetric — one unverified input marks the result — every figure a real ОВДП
tuple produces carries the unverified mark, since the price is in the cost basis of all of them.
What changed is **why**: once the terms are verified against the depository, the mark rests on
the price rather than on everything at once, and the output can say which source is unverified.
That is what feature 015 needs to refuse in parts.

### Where it collides with the shipped machinery

`scripts/check_provenance.py::_uncited_inferences` does two things to **every** enumerated
declaration:

1. it **requires** `[instrument.schedule]` and every `[[instrument.schedule.payment]]` to begin
   its citation `INFERENCE:`; and
2. it **refuses a non-empty `verified_on`** on any of them — *"an inference is unverified by
   construction: what a later reading verifies is the source it rests on, and that is a
   different table."*

Written for a schedule transcribed from a seller, that is exactly right. Applied to a schedule
transcribed from the issuer's depository it is not: the file is forced to declare an inference it
is not making. **Owner decision, 2026-08-30: 016 stays data-only.** FR-011 states what that
costs and what the alternative would be.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A real government bond, declared (Priority: P1)

The owner opens `data/instruments/` and finds a file per active ОВДП issue, each named for its
ISIN, each saying on its face that it is a real security, which facts came from the issuer's
depository and which from the seller, and on what dates each was retrieved. He runs the
comparison and, for the first time, it holds instruments that exist.

**Why this priority**: it is the feature.

**Independent Test**: load `data/`, confirm the declared set is exactly the active bond
observations, project one issue through the full tuple, and check its schedule row by row
against the depository record.

**Acceptance Scenarios**:

1. **Given** the shipped data root, **When** it is loaded, **Then** the set of declared ОВДП
   identities is exactly the set of ISINs the seller's observation carries as active, and the
   assertion names any ISIN on one side and not the other.
2. **Given** one declared issue, **When** its schedule is compared with the depository record,
   **Then** every payment date, amount and kind matches exactly, and the count is equal.
3. **Given** a declared issue and a purchase dated on or after the coverage start, **When** the
   full tuple is evaluated, **Then** it produces an outcome and appears in the comparison, with
   no source-code change made to reach it.
4. **Given** any declared issue, **When** its file is read, **Then** it states that it is not a
   fixture, and names both sources with their retrieval dates and what each supplied.

---

### User Story 2 - Two sources, and the file says which fact came from which (Priority: P1)

The terms come from the issuer's depository; the price, the spread, the availability and the
route come from the seller. The owner reads any figure and can tell which half it rests on, and
the two are never merged into one source note.

**Why this priority**: it is the half a fetcher would delete and the half a careless
transcription collapses. Merging them would let the depository's authority launder the price,
which is the single worst outcome available here.

**Independent Test**: walk the provenance of a projected figure and confirm two distinct
sources with two retrieval dates; assert no source note names both.

**Acceptance Scenarios**:

1. **Given** a declared issue, **When** its provenance is read, **Then** the schedule's citation
   names the depository and the price's citation names the seller, with their own retrieval
   dates, and neither citation mentions the other source.
2. **Given** the depository's licence condition, **When** any declaration transcribed from it is
   read, **Then** it carries a reference to the source, with the endpoint URL.
3. **Given** an active issue the depository does not list, **When** it is transcribed, **Then**
   the outcome is a refusal to declare it, not a fall back to the seller's figures.
4. **Given** the two sources' schedules for one issue, **When** they disagree, **Then** the
   declaration takes the depository's and **records the disagreement**, naming the seller's
   dates — the disagreement is a fact about the seller and is the thing that would otherwise
   silently disappear.

---

### User Story 3 - The quotation is a quotation, and says so (Priority: P1)

The owner reads a figure produced from a real issue and can see that it rests on a price the
seller offered on one morning in August; that nobody has verified it and nobody ever can; and
that the price ages in days rather than in a year.

**Why this priority**: this is now the *only* remaining reason for the mark, which makes it the
one that has to be exactly right.

**Independent Test**: take a projected figure and walk its provenance; assert the price's source
is among the unverified ones.

**Acceptance Scenarios**:

1. **Given** any figure produced from a declared ОВДП, **When** its provenance is read, **Then**
   it carries the unverified mark and the quotation's source is among the sources named
   unverified.
2. **Given** an as-of date beyond the quotation's threshold, **When** a tuple is evaluated,
   **Then** the result carries a staleness verdict naming the quotation and produces figures
   rather than refusing — staleness and verification are separate marks.

---

### User Story 4 - Nothing derives a term it was not given (Priority: P2)

No part of this change reads the seller's stated yield into a figure, computes a coupon rate,
extrapolates an issue date, or lets a script write a declaration.

**Why this priority**: each is a one-line temptation, each is invisible once made, and the
depository arriving with `auk_proc` and `razm_date` in it makes two of them newly tempting.

**Independent Test**: a scan over the source tree and the scripts, plus the reconciliation test.

**Acceptance Scenarios**:

1. **Given** the modules under `core/`, **When** they are scanned, **Then** none reads a stated
   yield, an availability figure, a status, a coupon rate, a placement date or a coupon period,
   and none names an ISIN.
2. **Given** the scripts, **When** they are scanned, **Then** none writes under
   `data/instruments/` or `data/access/`; those that fetch write only under
   `data/observations/`.
3. **Given** the observation files, **When** the reconciliation test runs, **Then** the internal
   rate of return over each active issue's buy quotation and its remaining payments agrees with
   the seller's stated buy yield within a stated tolerance for 19 named issues, and the 5 whose
   residual is larger are named individually with the reason.

---

### User Story 5 - Adding 24 instruments moves every count, and every count moves (Priority: P2)

The comparison stops holding nine candidates. Every pinned count either moves with the registry
or fails naming itself; nothing is left saying nine.

**Why this priority**: a count in prose beside a registry that grew is the exact staleness shape
this repository keeps finding by expensive review, and 014 left several.

**Independent Test**: run the suite before and after; confirm every failure is a count and no
surviving prose states one.

**Acceptance Scenarios**:

1. **Given** the enlarged registry, **When** the candidate suites run, **Then** every pinned
   population count is re-derived and re-recorded in the same change, and the golden set is
   regenerated deliberately with its changed lines quoted in the landing commit.
2. **Given** the landed change, **When** the specifications and tests that state a registry
   count are read, **Then** each states the new count or has been replaced by a derivation.

---

### Edge Cases

- **The eight completed issues.** Every purchase of one dated today receives nothing, and the
  enumerated form refuses that by name. Not declared (FR-001). Seven are also absent from the
  depository, which independently confirms the boundary.
- **`UA4000234215` — completed, 14 473 units on offer, still in the depository.** The seller's
  two fields contradict each other; neither is declared.
- **The eleven active issues with no stock at retrieval.** Declared. The available quantity is
  read by nothing and governs nothing (FR-017a).
- **`UA4000235782` — one wrong date in an otherwise exact schedule.** The depository's date is
  declared and the seller's is recorded as a disagreement (FR-009).
- **`UA4000235865` — the principal published a day early and out of order.** The depository puts
  both final payments on one date. The declaration is in date order with both on that date, and
  the seller's published order is recorded as the disagreement it is.
- **`UA4000207518` — the one issue quoted below face**, and the one with the lowest coupon.
  Declared like the rest; 013's premium figure simply comes out negative.
- **An active issue the depository does not list** — a refusal to declare, never a fall back to
  the seller's terms. Unreached today: all 24 are listed (FR-008).
- **A payment falling within a day of a year boundary**, where the two sources' dates would put
  it in different tax years — unreached today, checked 2026-08-30, and stated as a rule rather
  than left to be met by accident (FR-009).
- **A second declaration for one ISIN** — a load-time collision, and a failure of FR-001's
  boundary assertion.

---

## Requirements *(mandatory)*

### Functional Requirements

**Which issues are declared**

- **FR-001**: The system MUST declare exactly the bond observations carrying `status = "active"`
  at the seller's retrieval date — **24 issues** — and MUST NOT declare the 8 completed ones.
  The boundary MUST be asserted mechanically against the observation file, naming any ISIN
  present on one side and not the other.
- **FR-002**: Each declaration's identity MUST be derived from its ISIN and from nothing else.
  An `isin` field MUST NOT be added to the declaration record: the identity carries it, and adding
  a field is a source change for a fact the identity already holds.
- **FR-003**: Each declaration MUST state that it is not a fixture, and MUST name **both**
  sources with their retrieval dates and what each supplied. These are the first fixed-income
  declarations in this repository that are not synthetic.

**The terms come from the issuer**

- **FR-004**: The currency, face value, payment dates, payment amounts, payment kinds and
  coverage MUST be transcribed from the depository record and from no other source. Each is the
  issuer's own statement — `val_code`, `nominal`, `payments[].pay_date`, `pay_val`, `pay_type`,
  and a list running from placement to maturity — and not one of them MUST be inferred, derived
  or taken from the seller.
- **FR-005**: The depository retrieval MUST be recorded as a dated observation file, written by
  a script, on the same footing and for the same reason as the seller's: so a declaration can be
  checked against what the source actually published, and so the check has a date on it. The
  script MUST NOT write a declaration (FR-019).
- **FR-006**: Payment amounts MUST be transcribed as the depository states them, and **unit
  conversion MUST NOT be performed at all**: the depository publishes major units. The seller
  publishes the same amounts multiplied by 100 and states nowhere that it is quoting kopecks, so
  a transcription from the seller would have to choose a reading; a transcription from the
  depository does not.
- **FR-007**: A declaration MUST NOT carry a maturity date, coupon rate, placement date,
  periodicity or business-day rule, even though the depository publishes all five (013 FR-003).
  The form forbids them, nothing reads them, and `auk_proc` with `razm_date` in hand is exactly
  the condition under which someone reconstructs a schedule the issuer already published.
- **FR-008**: An active issue the depository does not list MUST NOT be declared. The outcome
  MUST be a refusal naming the ISIN and the retrieval date, never a fall back to the seller's
  terms. **FR-008 takes precedence over FR-001**: the declared set is the *intersection* of the
  seller's active issues and the depository's register, and FR-001's boundary assertion is over
  that intersection. This is the register's normal behaviour rather than a hypothetical — 7 of
  the 8 completed issues have already dropped out of it — so an issue leaving the register while
  the seller still lists it as active is a refusal to declare, and the assertion names it.
- **FR-009**: Where the two sources disagree, the declaration MUST take the **depository's**
  figure. The disagreement MUST be recorded **as a check over the two observation files**, not
  as a field on the declaration: a per-issue assertion that the seller's dates differ from the
  depository's by one day on the 15 named issues, that `UA4000235782` differs by a single wrong
  date, and that `UA4000235865` publishes its principal a day early and out of order. It is a
  fact about two sources rather than about one instrument, so it has no home in a declaration —
  and a check is the form this repository prefers for a claim that would otherwise go stale in
  prose. A rule stated once — "the seller is a day early" — is true of 15 and false of 9 and
  would absorb the two errors silently, which is why the check is per issue.
- **FR-009a**: The declaration's existing record of the order a source published in carries the
  **depository's** order, because the depository is what the schedule is transcribed from. It
  MUST NOT be repurposed to carry the seller's ordering: it records an order, not a date, and it
  would answer a question about the wrong source. `UA4000235865`'s out-of-order publication is a
  fact about the seller and lives in FR-009's check.
- **FR-009b**: Which date governs a coupon's **tax date** where the sources disagree MUST NOT be
  guessed. At a year boundary the two would place a payment in different tax years; no payment in
  the 24 falls within two days of one, checked 2026-08-30. Recorded as owner verification task 2.
- **FR-010**: The declared day count MUST be the same across all 24 and MUST be the one the
  shipped fixtures declare, so the yields are comparable. It is a convention of computation and
  claims nothing about the issue (013 FR-003a).
- **FR-011**: **013's four inferences no longer apply to these declarations**, because each is
  now the issuer's stated fact, and a **fifth** inference MUST NOT be added — the currency was a
  candidate while the seller was the only source and is a retrieved fact now. Two paths follow
  and the owner chose the first:
  - **Data-only (chosen, 2026-08-30).** The declarations satisfy the gate as it stands: each
    schedule table carries the `INFERENCE:` marker and an empty verification date. **The cost:
    the citation calls the issuer's published schedule an inference, which is false, and no term
    can be verified while it stands.** The declarations MUST still name the depository as the
    source, so the false word sits beside a true citation rather than replacing it.
  - **The alternative, not taken.** Letting a schedule that cites the depository stand without
    the marker and carry a verification date — a change to one check, not to the loader, the
    declaration record or any interface. Recorded as the `primary-sourced-schedule-may-be-verified`
    future entry, which holds its scope.

**The seller's half, and the round trip**

- **FR-012**: Each declared issue MUST be reached through exactly one access declaration priced
  at the seller's observed **buy** quotation, carrying that observation's retrieval date, and
  naming the venue it is bought at, the venue proceeds land at, and a risk class. The risk class
  MUST remain a declared word no figure is computed from.
- **FR-013**: Every declaration transcribed from the depository MUST carry a reference to the
  source, which is the condition **ст. 10¹ ч. 2 Закону України «Про доступ до публічної
  інформації» (№ 2939-VI)** attaches to reuse of open data. The reference MUST include the
  endpoint URL — required here by this repository's own citation rules rather than by the Act,
  which imposes no hyperlink. A declaration MUST NOT assert that a hyperlink is a statutory
  obligation: the hyperlink wording belongs to **п. 17 Положення, затвердженого постановою КМУ
  від 21.10.2015 № 835**, which prescribes a notice the *publisher* displays.
- **FR-014**: The **sell** quotation MUST NOT be declared. Nothing in this engine prices a
  disposal before the end of a schedule, so a declared sell price would be read by nothing —
  which 013 FR-003 argues is worse than a missing field. The reason MUST be recorded once.
- **FR-015**: The buy-versus-sell spread MUST NOT be presented as the round-trip cost of any
  tuple. It is the seller's round trip on an **immediate resale**, an exit this engine does not
  model. The round trip a comparison reports remains the one Principle VI requires — per
  `(instrument × income stream × route)`, running the way in, the purchase at the buy quotation,
  the schedule to its end, and the way out — and a one-way figure MUST NOT be presented as it.
- **FR-016**: The quotation MUST name the observation kind the shipped access declarations
  already use. **A new kind MUST NOT be opened for it** (owner decision, 2026-08-30). Its
  365-day interval is too long for a price; nothing in the shipped comparison turns on it, and a
  kind of its own is recorded as a future entry rather than asked about here. A tuple evaluated
  beyond that threshold MUST carry a staleness verdict naming the quotation and MUST still
  produce figures: staleness and verification are separate marks and neither refuses a run.
- **FR-017**: The seller's stated yields MUST NOT be an input to any figure. They MUST be used
  exactly once, as a **reconciliation of the transcription** asserted as a test: an internal
  rate of return over each active issue's buy quotation and its remaining payments, compared
  with the stated buy yield, naming a tolerance and naming the five issues whose residual
  exceeds it with the reason.
- **FR-017a**: **The available quantity is not read, and governs nothing.** It MUST NOT be
  declared, and it MUST NOT be an input to any figure. It is a dated snapshot of one
  seller's inventory that decays in hours and is not self-consistent: **11 of the 24** active
  issues publish `0` while being offered for sale, and a **completed** issue publishes 14 473.
  The consequence MUST
  be recorded as a named gap with a future entry — no inventory cap is enforced, so a plan may
  size a purchase larger than the seller had, and constitution Principle VI requires feasibility
  to be enforced rather than assumed. Recording the gap is the answer to feature 015's question
  about this field; taking the number as a cap would be the guess.
- **FR-018**: Minimum ticket and minimum unit MUST come from a cited retrieval of the venue's
  published dealing terms and MUST NOT be inferred. An understated minimum silently permits a
  purchase the venue would refuse, which Principle VI puts in the highest severity class. If the
  dealing terms cannot be retrieved, this feature MUST report that and declare nothing.

**Provenance, the mark, and the sources kept apart**

- **FR-019**: A script MUST NOT write under `data/instruments/` or `data/access/`. This is
  `scripts/fetch_inzhur.py`'s own stated refusal, held today by nothing, and it now governs a
  second fetcher as well.
- **FR-020**: The two sources MUST NOT be merged into one citation. A source note MUST name one
  source, one retrieval date and what it supplied. The failure this prevents is specific: a
  single note mentioning the depository beside a price would let the issuer's authority attach
  to a figure the issuer never made.
- **FR-021**: The quotation's verification date MUST be empty, as the existing convention
  already requires of any value nobody has checked against a primary source. No rule and no test
  asserting that it stays empty: a dated offer has no independent record, which is a fact worth
  one sentence and not a mechanism (owner decision, 2026-08-30).
- **FR-022**: Every figure produced from a declared issue MUST carry the unverified mark while
  the price is unverified, and the quotation's source MUST be among the sources the result names
  as unverified. This MUST be asserted on a full tuple outcome, not only on a projection.
- **FR-023**: A module under `core/` MUST NOT name an ISIN, and MUST NOT read a stated yield, an
  availability figure, a status, a coupon rate, a placement date or a coupon period.
  `data/README.md` records the first of these as *"reviewed rather than enforced"* and names the
  test that would close it; declaring 24 real securities is what makes it worth writing.

**The counts that move, and the prose that goes false**

- **FR-024**: Every count pinned on the shipped registry MUST be re-measured and re-recorded in
  the same change. The sites are enumerated in *Counts that move*, and the enumeration MUST be
  checked by running the suite rather than trusted.
- **FR-025**: Where a count that moved was stated in prose, it MUST be replaced by a derivation
  or an assertion rather than by a new number wherever that is possible.
  `tests/contract/test_the_observation_the_form_rests_on.py` is the precedent.
- **FR-026**: Each declaration MUST name, for each income kind its schedule produces, the tax
  class the shipped Ukrainian rule pack already declares for a government bond, and MUST declare
  no rate, category or treatment of its own.
- **FR-027**: The synthetic fixtures MUST NOT be retired. Several suites depend on them, and a
  fixture whose arithmetic a reader can check on paper is not made redundant by a real security
  whose schedule they cannot.
- **FR-027a**: `enumerated_out_of_order` MUST NOT carry feature 015's `ovdp` group label once
  `UA4000235865` is declared. The fixture's own header says it is *"modelled on a real issue and
  deliberately not it"* and names that ISIN, and 015 resolves the owner's word `ovdp` to a group
  containing both — so the group would hold **one piece of paper twice**, as two candidates with
  two sets of cash flows in one comparison, differing only in that one is invented. 015's
  deduplication cannot catch it: FR-007b deduplicates by **id**, and these are two ids for one
  security. Whichever feature lands second MUST apply this, and the answer's group resolution
  (015 FR-008a) is where a reader would see the count if it were not.
- **FR-028**: Prose this feature falsifies MUST be corrected in the same change. Three pieces are
  known: `data/README.md`'s "reviewed rather than enforced" paragraph, closed by FR-023; 013's
  account of `UA4000235865`, whose out-of-order publication this feature shows to be an error
  rather than an issuer's habit — 013's requirement and fixture stand, its reading of the real
  instance does not; and **`data/instruments/enumerated_out_of_order.toml`'s own header**, which
  says that issue *"publishes the repayment of principal one day BEFORE the final coupon"* and
  calls it *"the one real exception"*, attributing to the security what the depository shows to be
  the seller's transcription error. That one outlives the other two, because FR-027a keeps the
  fixture permanently. No new formula is introduced, so `docs/METHODOLOGY.md` is expected to
  be unchanged and the landing change MUST say so.
- **FR-029**: Adding these declarations MUST NOT introduce a fifth plugin interface, MUST NOT
  widen the instrument failure union, and MUST NOT add a field to the instrument declaration
  record. Under the data-only decision the only source changes it may make are the scans and
  assertions this specification names.

---

## Key Entities

- **Declared ОВДП issue** — one real government bond identified by its ISIN, declared in 013's
  enumerated form, whose terms are the issuer's depository record and whose price is the
  seller's quotation, each carrying its own citation and retrieval date.
- **Source disagreement** — a fact about two observation files rather than about an instrument,
  and therefore a **check** over them rather than anything declared: the one-day offset on 15
  named issues, and the two outright errors.
- **Declared quotation** — the seller's buy price on its retrieval date, carrying that source
  and that date, with an empty verification date as the convention already requires.
- **Reconciliation residual** — the difference between this project's internal rate of return
  and the seller's stated yield, per issue, asserted as a test rather than recorded as a number.
- Reused unchanged: the enumerated declaration form and everything 013 built on it, the access
  declaration, the tax classes and their categories, the ledger, the tuple join, the candidate
  loop, provenance and staleness.

---

## Success Criteria *(mandatory)*

- **SC-001**: Two halves, and the second is the one with content. **(i)** Every ISIN the seller
  carries as active that the depository's register does **not** list is reported as a refusal
  naming it — the assertion FR-008 actually asks for, and the only one that can fail. **(ii)** The
  declared set equals the seller's active ISINs minus those refusals, its size **derived rather
  than written**, so the criterion survives the first issue leaving the register instead of
  breaking on it. *Not* "declared == intersection": the declared set is **defined** as the
  intersection, so that assertion is a tautology and can never name an ISIN on one side and not
  the other. On the shipped observations the refusal set is empty and the declared set is 24.
  (FR-001, FR-008)
- **SC-002**: For every declared issue, every payment date, amount and kind equals the
  depository's, asserted over the whole schedule of all 24 rather than on a sample, and no
  declared amount is a seller's figure divided by anything. (FR-004, FR-006)
- **SC-003**: Every declared issue's currency and face value equal the depository's `val_code`
  and `nominal`, and no file records a currency inference or a settling task for one. (FR-004,
  FR-011)
- **SC-004**: Every declared issue's principal repayments are exactly the depository's
  `pay_type` 2 rows and its coupons exactly the `pay_type` 1 rows; no kind is read off an
  amount, a date or a position. (FR-004)
- **SC-005**: Every declared coverage start is at or before the issue's earliest depository
  payment, and the declared list runs to `pgs_date`. (FR-004)
- **SC-006**: All 24 declarations name one day count and it is the fixtures'; changing it in a
  scratch copy moves that issue's yield and leaves every cash-flow amount bit-identical.
  (FR-010)
- **SC-007**: A check over the two observation files reproduces all three disagreements from one
  pass, **naming the ISINs rather than counting them**: the fifteen issues whose every seller date
  is one day earlier are exactly the set listed under *The cross-check*, the nine that agree are
  its complement, `UA4000235782` differs by a single date (`2027-06-03` against `2027-06-02`), and
  `UA4000235865` publishes its principal on `2026-09-15` against the depository's `2026-09-16`,
  out of order. Asserting only *that fifteen issues have an offset* would pass if the wrong
  fifteen did. Moving a date in a scratch copy of either file fails the check. Nothing is recorded
  on a declaration. (FR-009)
- **SC-008**: A battery of scratch declarations carrying a maturity date, a coupon rate, a
  placement date, a periodicity, a stated yield, an availability figure or a status fails at
  load, each failure naming the file and the field. (FR-007, FR-012)
- **SC-009**: Every declared issue is priced by exactly one access declaration at its observed
  buy quotation, and no declared value anywhere in `data/` equals a published sell quotation.
  (FR-012, FR-014)
- **SC-010**: No source note names both sources, and every declaration transcribed from the
  depository carries a reference to the source with its endpoint URL, and no declaration asserts
  that a hyperlink is a statutory obligation. (FR-013, FR-020)
- **SC-011**: An active issue absent from the depository record produces a refusal naming the
  ISIN and the retrieval date; asserted with a scratch depository observation from which one
  issue has been removed, since the case is unreached in the shipped data. (FR-008)
- **SC-012**: The buy-versus-sell spread appears in no declaration, no result record and no
  rendered figure; asserted by a walk over every result record for a declared issue. (FR-015)
- **SC-013**: A tuple evaluated beyond the quotation's staleness threshold carries a verdict
  naming the quotation and produces figures rather than refusing. (FR-016)
- **SC-014**: The reconciliation test passes on the shipped observations — 19 named issues
  within the stated tolerance, 5 named outside it with their measured residuals — and fails on a
  scratch copy of either observation in which a figure has moved. (FR-017)
- **SC-015**: Every declared minimum ticket and minimum unit carries a citation to the venue's
  published dealing terms with its own retrieval date, and no declared minimum restates the
  access price. No declaration anywhere carries an available quantity, and no result record
  depends on one. (FR-017a, FR-018)
- **SC-016**: 100% of figures produced from a declared issue carry the unverified mark, and the
  quotation's source is among the sources the result names as unverified on a full tuple
  outcome. (FR-022)
- **SC-017**: A scan finds no script writing under `data/instruments/` or `data/access/`, and no
  module under `core/` naming an ISIN or reading a stated yield, an availability figure, a
  status, a coupon rate, a placement date or a coupon period. (FR-019, FR-023)
- **SC-018**: After the declarations land the suite is green, every count named in *Counts that
  move* states a re-measured value or has been replaced by a derivation, and the candidate
  golden was regenerated deliberately with its changed lines quoted. (FR-024, FR-025)
- **SC-019**: Every declared issue names the shipped government-bond tax class for both income
  kinds, and its projected liability for a year is zero with no other category's base moved.
  (FR-026)
- **SC-020**: The synthetic fixtures still load, still project, and their worked examples are
  unchanged; and no group resolves to both `UA4000235865` and `enumerated_out_of_order`. **A green
  result over zero declared labels is not evidence**: where 015's labels are not yet in `data/`
  the criterion MUST be met against a scratch registry that declares the `ovdp` group, so the
  check fails if the fixture keeps the label rather than passing because nothing carries one.
  (FR-027, FR-027a)
- **SC-021**: Adding the 24 declarations required no new plugin interface, no new member of the
  instrument failure union, and no new field on the instrument declaration record. (FR-029)

---

## Which issues are declared, and why that number

**Not all 32.** The 8 completed issues matured before the seller's retrieval date; the
enumerated form refuses any purchase dated on or after every payment a schedule declares.
Declaring them would add 8 instruments that refuse in every candidate survey for ever. The
depository independently confirms the boundary: 7 of the 8 are no longer listed at all.

**Not a smaller subset.** The tempting one is the 13 issues that showed stock. It is wrong
twice: availability decays in hours, so which files exist would encode a two-hour-old
inventory; and one *completed* issue showed stock, so the field is not self-consistent. The
deeper objection is that any subset is the tool narrowing the owner's opportunity set on a
criterion he did not state.

**And the fixture keeps its place while losing its label.** The obvious reading of FR-027a is
that `enumerated_out_of_order` should simply be retired once a real out-of-order schedule exists.
This feature's own cross-check refuses that: the real issue is **not** out of order — the seller
published it wrongly, and the depository puts both final payments on 2026-09-16. So there is no
real instance of the thing 013 FR-020a exists for, and retiring the fixture would remove the only
example of a mechanism that still needs one. **013's mechanism survives its example turning out
to be a seller's error**, which is why the fixture earns its place and its group label does not.

**The burden is smaller than it was.** In the first draft each issue carried six inferences and
24 lookups were needed to settle them. With the depository they are retrieved facts, and what
remains per issue is a comparison a human makes once between two published schedules — which is
the work that found the two errors.

---

## Counts that move

Adding 24 instruments takes the registry from 9 to 33. Feature 014's measurement — **9
instruments, 18 pairs, 9 candidates, 9 pairs yielding none, 7 evaluated, 2 dropped** — describes
a registry that will not exist. The sites, read 2026-08-30:

| Site | What it pins |
|---|---|
| `tests/worked_examples/test_candidate_accounting.py` | the literals 9, 9, 18, 7, 2, 9 |
| `tests/worked_examples/test_candidate_enumeration.py` | "9 instruments with an access declaration", and prose counting nine twice more |
| `tests/golden/candidate_set.golden.txt` | the whole set: 9 plans, the accounting block, one row per candidate |
| `tests/unit/test_seventeen_refusals_through_the_loop.py` | "the same nine candidates the two-currency world yields" |
| `specs/014-candidates/spec.md` | its *measurement* table and four further statements of nine |
| `specs/014-candidates/plan.md` | "the shipped set's nine candidates are a golden" |
| `specs/features.toml` | feature 015's note — "seven of nine instruments are fixtures" |
| `tests/contract/test_the_observation_the_form_rests_on.py` | unmoved: it measures the seller's file, which this feature does not re-fetch |
| `tests/golden/ovdp_synthetic_a.golden.txt` | unmoved: no generative declaration's behaviour changes |

Constitution 1.2.0 Principle V governs the golden: evidence, never a freeze, and a registry that
grew is the direction its digests are supposed to move in.

---

## Assumptions

- **The seller's observation is not re-fetched by this feature.** Every measurement is against
  the 2026-08-24 file, and the checks that pin it fail on a re-fetch by design.
- **The depository is retrieved once, and recorded** (FR-005). It is a live endpoint; what
  ships is the dated snapshot, exactly as for the seller.
- **Nothing prices a secondary-market sale**, unchanged from 013.
- **The premium at purchase is already decided.** 31 of 32 issues quote above face; the
  treatment is cited in `data/tax/timing/ua.toml` and reported by 013 FR-025. Nothing is
  re-derived.
- **The tax classes are the shipped ones.** These are ОВДП; both income kinds fall in the exempt
  category already declared.
- **The auction endpoint is not used.** `https://bank.gov.ua/NBU_ovdp?json` returned **3 rows**
  on 2026-08-30 — the current auction, not a history — and carries primary-market results
  rather than terms. Recorded as measured so nobody re-probes it expecting a series.
- **No delivery surface.** Results are produced and asserted by the test suite.
- **One owner, one venue.** All 24 are reached at the one venue that sells them.

---

## Decisions

All three questions this specification raised were settled by the owner on 2026-08-30. None is
open, and none is to be reopened here.

| | Decision |
|---|---|
| **Whether a primary-sourced schedule may drop the inference marker and carry a verification date** | **016 stays data-only.** The declarations satisfy the gate as it stands. The cost and the minimal alternative are FR-011; the alternative is a future entry, not an argument. |
| **Whether the quotation's verification date should be permanently empty by rule** | **Withdrawn.** The price came from the nearest real source, it carries that source and its retrieval date, and that is enough. No rule, no test (FR-021). |
| **A new staleness kind and threshold for a bond quotation** | **Withdrawn.** No new kind; the quotation names the one the shipped access declarations already use (FR-016). |

### Questions drafted and closed without asking

Closed against the repository or against the depository probe. **Do not restate these in
`specs/features.toml`.**

- **Which issues to declare** — settled by argument, and corroborated: the 24 active, which is
  exactly the set the depository still lists.
- **Whether to declare the sell quotation** — settled by 013: nothing prices a disposal before
  the end of a schedule (FR-014).
- **The tax treatment of a purchase above face** — settled and cited in
  `data/tax/timing/ua.toml`; 013 recorded the same question being withdrawn on the same ground.
- **The day count** — a project convention, not an open question (013 FR-003a); it need only be
  the same across all 24 (FR-010).
- **The minimum ticket** — not a clarification but a retrieval. It could have been inferred and
  must not be: an understated minimum silently permits an infeasible purchase (FR-018).
- **What the available quantity governs** — **nothing**, and the field is not declared (FR-017a).
  Feature 015 flagged it as this feature's to settle; the answer is that it is not read, because
  it decays in hours and contradicts itself in the shipped observation.
- **Whether the currency needs a fifth inference** — **withdrawn.** `val_code` states it — UAH on
  176 issues, USD on 16, EUR on 3 — so it is a retrieved fact (FR-011).
- **Whether the generative form is now possible** — it is, and it is still refused, because the
  issuer publishes the schedule and reproducing it from a rate would mean inventing the
  convention that produced `auk_proc ÷ 2`. Argued under *Why the enumerated form*.

---


## Owner verification tasks

Facts no source in hand settles. Each keeps a value's verification date empty.

1. **The venue's minimum ticket and minimum unit for an ОВДП purchase.** Not in either source.
   One fact for all 24, from the venue's own published dealing terms — the one place the seller
   *is* the primary source. FR-018 forbids declaring without it.
2. **Which date governs a coupon's tax date where the two sources disagree.** The depository is
   the issuer's record of when it pays and the seller's page is not, but nothing here has ruled
   on it, and at a year boundary the choice moves a payment between tax years. Unreached in the
   24 (checked 2026-08-30) and recorded so it is not met by accident.
3. **Whether the owner accepts the depository as sufficient for a completeness claim**, or wants
   a second source per ISIN. Carried forward from 013's own task 3; the depository answers it as
   well as anything can — its list runs placement to maturity and its last payment is `pgs_date`
   on all 24.

---

## Required tests this feature closes

| Row | What this feature does to it |
|---|---|
| **H1** | The data-only extensibility claim gets its first test on **real** instruments, 24 at once. Whether that strengthens H1's own test or sits beside it, as 013's does, is decided at planning — and the data-only decision keeps the claim intact. FR-029 is the narrow claim; SC-021 is its evidence. |
| **D1** | Unchanged. D1 is about a generative bond reproducing a hand-computed schedule, and no generative declaration's behaviour changes. |

---

## Out of scope

**Re-fetching the seller's observation** — the checks that pin its counts fail deliberately when
it runs; the **five funds** in it, whose NAV-versus-price problem is 006's; the **auction
endpoint** and anything about the primary market; **any market price series, yield curve, or
disposal before the end of a schedule**; **accrued interest and the clean/dirty split**, deferred
with its reason in 013 — the depository's `razm_date` and `pay_period` make the previous coupon
date recoverable, which changes that future entry's reasoning and not this feature's scope;
**an inventory cap as a declared term**; **declaring a real taxable
enumerated instrument** — these are exempt on both sides; the display-currency switch; and the
web and command-line interfaces, which are 015's.
