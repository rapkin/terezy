# Feature Specification: The NBU rate series — filling a declared, empty series

**Feature Directory**: `specs/018-nbu-rate-series`

**Feature Branch**: `spec/018-nbu-rates` (spec-writing worktree; squash-lands per `specs/README.md`)

**Created**: 2026-08-30

**Status**: **Ready for planning** — no open `[NEEDS CLARIFICATION]`. Three **owner verification
tasks** are open and none blocks planning: the behaviour in the absence of each is specified
completely, and each ships its gap in the output rather than only in prose. The publication
question was settled on 2026-08-30 by two independent retrievals, and with it this feature's
dependency on 017 — see FR-013.

**Input**: `data/official_rates/ua_nbu_usd.toml` declares the series `ua_nbu_usd` — authority
Національний банк України, pair `(UAH, USD)`, quotation unit `1.0` — and holds
`observation = []` (that file, line 65). The machinery around it is finished. This feature is
the data, plus the retrieval and provenance discipline that getting it honestly requires.

---

## Why this feature exists

Feature 011 built the tax-currency role and shipped it empty on purpose. The consequence is
not subtle and is worth stating as a number rather than as a mood: **every tax figure struck
from a foreign amount refuses today**, with
`OfficialRateUndeclaredOnDate` (`src/terezy/core/tax/official_rate.py:226`) reporting that the
series *"declares no observation at all"* (that file, line 353).

The thing that refusal blocks is the largest comparison the project has built so far.
Feature 012 declares ФОП group 3 against the personal-income scheme, and the base of a
foreign credit under either is *the credited foreign amount at the official rate on the credit
date* (`specs/features.toml`, the 012 entry). With no observation on any date, the two schemes
cannot be compared on a dollar amount at all — not badly, not approximately: not at all. **This
feature is what makes 012's 6%-versus-23% comparison runnable on a real dollar amount for the
first time.**

### What has been protecting an empty file

Every guard in this repository against conflating the official rate with an exchange rate has,
until now, been guarding nothing. There is one number-producing conversion function in the
codebase — `terezy.core.primitives.money.convert` — and exactly four call sites:

| call site | where its rate comes from | what it produces |
|---|---|---|
| `core/routes/legs.py:369` | a declared two-sided channel | an amount actually received |
| `core/routes/cost.py:545` | a channel's `reference_rate` | a fee valued back into the sending currency |
| `core/tax/official_rate.py:368` | `observation.value / series.quotation_unit` | a tax base |
| `core/tax/year.py:1086` | read *off* the conversion, not looked up again | the PIT and levy lines at the same rate |

Two of those four are the official rate, and both are unreachable today because the series is
empty. The `.importlinter` contracts `official-rate-never-prices-a-leg` (`.importlinter:94`)
and `no-tax-base-from-a-channel` (`.importlinter:111`) hold trivially; the source scan in
`tests/contract/test_the_rate_you_are_taxed_at.py` passes over a path nothing walks. **This
feature is the first time those guards are load-bearing.**

`core/results/tuple.py` states the rule the guards exist for, in its own words (lines 840–843):

> **It must not be satisfied with a channel rate**, and neither must the base itself. A
> channel is a market you transact in; the official rate is a legal reference you never
> transact at, and substituting one for the other would strike a tax base at a price nobody
> was charged.

and again, for the other direction, at lines 453–455:

> The official rate feature 011 brought is a *legal* reference — what the law says an income
> was worth on a date — and reusing it to score a return is the role conflation Principle VI
> names, not a shortcut around it.

The concrete temptation this feature creates has a file name.
`data/channels/uah_usd.toml` declares three channels whose `reference_rate = 42.0` is marked
on every line *SYNTHETIC FIXTURE — invented*, with an empty `verified_on`. Once
`ua_nbu_usd.toml` carries the National Bank's real figures, a real rate will be sitting one
directory away from an invented one, and the cheapest-looking repair in the repository will be
the one the constitution names as a defect. `core/routes/channels.py:149` already notes that
`nbu_official` is a legitimate *channel id* — a channel named for the National Bank may be
declared — and that borrowing the tax series' number to fill it is a different act entirely.
FR-017, FR-018, SC-009 and SC-010 are what stop it, mechanically, rather than this paragraph.

### What this feature does not make possible

It does not make a foreign-currency **projection** computable, and nothing ever will. Declared
instrument payments in `data/` reach `2029-11-06`; a tax base for a credit on that date needs
an official rate for that date, and an official rate for a date that has not arrived is a
forecast wearing an observation's clothes — refused at load already
(`src/terezy/data/declarations/schema.py:2244`). After this feature, such a request refuses
with a *better* message: today it says the series declares nothing, and afterwards it names the
window the series does cover and the date that falls outside it. That improvement is the whole
of what 018 gives a projection.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A dollar credit gets a hryvnia base from a published rate (Priority: P1)

The owner asks what a dollar amount credited on a real date is taxed on. The engine strikes the
base at the National Bank's published official rate for that date, and reports the series, the
date, the value and the quotation unit, so the arithmetic can be redone on paper against the
publisher's own page.

**Why this priority**: it is the feature. Everything else here is the discipline that makes
this one answer trustworthy.

**Independent Test**: pick a date inside the covered window, read the National Bank's published
rate for it by hand, and check the engine's base against hand arithmetic on that figure.

**Acceptance Scenarios**:

1. **Given** the populated `ua_nbu_usd` series and a dollar-denominated taxable event on a date
   inside its covered window, **When** the base is struck, **Then** it equals the event's amount
   times the published rate for that date divided by the declared quotation unit, within the
   single project tolerance.
2. **Given** the same base, **When** it is inspected, **Then** it names `ua_nbu_usd`, the
   observation date, the rate value and the quotation unit, and a reader can re-derive it
   without opening a data file.
3. **Given** the same event under ФОП group 3 and under the personal-income scheme, **When**
   both are charged, **Then** two charges are produced on the same hryvnia base and the
   comparison 012 declares is answerable on a real dollar amount — which it is not today.

---

### User Story 2 - A date outside the covered window refuses by name (Priority: P1)

Asked about a date the series does not cover — earlier than its first observation, or later
than its last — the tool names the series, the pair, the date and the window it does cover, and
produces no number.

**Why this priority**: equal-highest, because populating a series is exactly the change that
makes a refusal look like a bug. A window that reaches from 2019 to last week invites
"surely it can manage 2018", and every one of the four ways to manage it — interpolate,
extrapolate, carry forward, snap to nearest — produces a number indistinguishable from a
correct one (`core/tax/official_rate.py:26-29`).

**Independent Test**: ask for a base on a date before the first observation, on a date after
the last, and on a date in the future that a declared instrument actually pays on; confirm all
three refuse naming the window, and that no flag or option makes any of them return a figure.

**Acceptance Scenarios**:

1. **Given** an event dated before the series' first observation, **When** a base is attempted,
   **Then** `OfficialRateUndeclaredOnDate` names the series, the pair, the date and the covered
   window, and no base is produced.
2. **Given** an event dated after the series' last observation — including a projected coupon
   in 2029 — **When** a base is attempted, **Then** the same refusal, naming the same window.
3. **Given** the covered window in the refusal message, **When** it is read, **Then** it states
   real dates rather than *"declares no observation at all"*, which is the message the shipped
   series produces today.

---

### User Story 3 - The retrieval is reproducible and nobody has verified it (Priority: P1)

The observations arrive by a repository script that fetches the National Bank's own statistics
service, writes each observation with its citation and retrieval date and an **empty**
verification date, and never fills that date. Every tax figure struck from them renders marked
until the owner checks a value against the publisher himself.

**Why this priority**: P1 because it is the difference between data and numbers. A file of
a few thousand plausible rates that nobody can reproduce from a cited source is exactly the artefact
Principle I exists to refuse, and the mark is what says so on every figure downstream.

**Independent Test**: run the script twice on the same day and confirm byte-identical output;
run it against a deliberately altered response shape and confirm it writes nothing at all;
confirm every `verified_on` it writes is empty and that a derived base carries the mark.

**Acceptance Scenarios**:

1. **Given** the fetch script, **When** it runs, **Then** every observation it writes carries a
   non-empty `source`, a `retrieved_on`, and a `verified_on` that is present and empty.
2. **Given** a response whose shape differs from the one the script expects — a missing field, a
   changed `units`, a short range — **When** the script runs, **Then** it fails loudly, names
   what surprised it, and leaves the existing file untouched. It never writes a thinner file.
3. **Given** a base struck from an unverified observation, **When** any figure derived from it
   is rendered, **Then** it carries the unverified mark, and so does everything derived from
   that.
4. **Given** an observation the owner has verified, **When** the script re-runs and that date's
   published value is unchanged, **Then** the verification survives; **and when** the published
   value has changed, **Then** the verification is cleared, because it attested to a different
   number.

---

### User Story 4 - Populating the series moves nothing outside the tax path (Priority: P1)

Filling the series changes tax bases and charges, and changes nothing else. No cost, no route,
no leg, no channel, no ranking figure anywhere in the system moves because a rate series
acquired values.

**Why this priority**: P1, not P3. This is the first moment the role-conflation guards guard
anything real (see "What has been protecting an empty file"), and the failure is silent: a
single substitution reprices a ramp at a rate nobody was charged, and every figure stays
plausible.

**Independent Test**: run every golden before and after the data lands. The only digests that
may move are the ones over tax figures and the input digest of the rate file itself.

**Acceptance Scenarios**:

1. **Given** the golden runs, **When** the series is populated, **Then** every cost, route, leg,
   channel and ranking digest is bit-identical to its value before.
2. **Given** `data/channels/uah_usd.toml`'s synthetic `reference_rate = 42.0`, **When** this
   feature lands, **Then** it is still `42.0` and still marked synthetic: a real official rate
   is not a repair for an invented channel quote, and this feature does not present it as one.
3. **Given** the two `.importlinter` contracts and the source scan, **When** they run against
   the landed feature, **Then** they still pass, over a path that now has values in it.

---

### User Story 5 - A run can say which version of the rates it rested on (Priority: P2)

A result naming a tax base struck at an official rate carries, in its manifest, the series it
used and the version of the file that declared it.

**Why this priority**: P2 only because Stories 1–4 must exist first. The requirement itself is
Principle III: *"Every run emits a manifest: … the version and provenance of every input series
and data file. A result without a manifest is not a result."* Today `InputKind`
(`src/terezy/data/manifest.py:129`) is a closed `Literal` with five members and no
`official_rate` among them, so no manifest can name this series and no golden records its file
version. That is invisible while the series is empty and becomes a reproducibility hole the
moment it is not.

**Independent Test**: produce a result whose tax base was struck at an official rate, read its
manifest, and find the series id and the file's digest in it; change one observation and
confirm the digest moves.

**Acceptance Scenarios**:

1. **Given** a run whose tax base was struck at an official rate, **When** its manifest is read,
   **Then** it names `ua_nbu_usd` and the version of `official_rates/ua_nbu_usd.toml`.
2. **Given** any edit to that file, **When** the manifest is regenerated, **Then** its recorded
   version moves — because the input changed, which is what a witness is for (Principle V).

---

### Edge Cases

- **A weekend or a public holiday.** The National Bank returns a rate for every calendar day,
  dated that day, so the series declares one too and there is no non-publication day to have a
  rule about (FR-013). The value is retrieved against that date, not derived for it.
- **A date in the future that a declared instrument actually pays on.** Refuses, permanently,
  and correctly. No forward official rate exists and one would be a forecast.
- **A date before 2019-12-28.** Refuses, naming the window. It is not a gap in retrieval: it is
  a date the National Bank quoted USD **per 100 units** for, which a series declaring
  `quotation_unit = 1.0` cannot honestly carry (FR-007). The remedy is a second series, not a
  longer one.
- **The publisher restates a past date's rate.** The re-fetch writes the new value, clears that
  observation's `verified_on` (FR-006), and the file's digest moves — which is a golden failing
  on purpose, not a golden to be worked around (Principle V).
- **The publisher's `units` field changes again.** The script refuses the whole run rather than
  normalising (FR-008). A value silently divided by 100 to fit a declared unit is the two-orders-
  of-magnitude failure `data/official_rates/ua_nbu_usd.toml:50-63` warns about, arriving through
  the one door that file did not think to close.
- **The endpoint returns fewer days than the requested range.** A short range is a shape
  surprise, not a set of gaps: the script fails and writes nothing (FR-004).
- **The series has been fetched more than seven days ago.** Every figure struck from it reports
  staleness — `official_rate` carries `staleness_days = 7`
  (`data/observation_kinds.toml:71-74`). That is 011's declared policy and this feature does not
  weaken it. Its uncomfortable consequence is recorded as an observation, not fixed here: see
  "Known consequence: staleness lands on dates it cannot be about".
- **A gap inside the covered window.** Cannot arise from the publisher, which leaves none. It
  can arise from a *partial write*, which is why FR-004 refuses to make one: a hole inside the
  window would refuse under FR-012 naming the series, and blame the publisher for a failed fetch.
  The engine still never tries to tell a gap from a non-publication day
  (`core/tax/official_rate.py:26-29`), and this feature gives it no reason to start.
- **An observation whose date is later than its own `retrieved_on`.** Already refused at load
  (`schema.py:2244-2247`); this feature adds nothing and removes nothing. It is not hypothetical
  here: the publisher offers tomorrow's rate today, so the script has to decline it or write a
  file that does not load (FR-010).

## Requirements *(mandatory)*

### Functional Requirements

**Where the data comes from**

- **FR-001**: Every observation MUST be retrieved from the National Bank of Ukraine's own
  statistics service. No rate value may originate from an implementer's or an agent's memory,
  from a secondary source restating the National Bank, or from a chart. The endpoint used, its
  query parameters, and the retrieval date MUST appear in each observation's citation.

  Two endpoints were reached and read on **2026-08-30**, both HTTP 200:
  `https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?valcode=usd&date=YYYYMMDD&json`
  returns one date and does **not** state the quotation unit;
  `https://bank.gov.ua/NBU_Exchange/exchange_site?start=YYYYMMDD&end=YYYYMMDD&valcode=usd&sort=exchangedate&order=asc&json`
  returns a range and states `units`, `rate_per_unit` and `calcdate` per row. **The range
  endpoint is the one to use, and the reason is `units`** — see FR-008.

  `specs/011-official-rate/spec.md`'s owner verification task records that *"`bank.gov.ua`
  returns **HTTP 403** to automated retrieval"*. That was true of the methodology PDF it was
  about and is **not** true of the statistics endpoints above, tested with plain `curl
  --compressed` on 2026-08-30. Recorded with its date so the next retriever does not spend the
  attempt again.

- **FR-002**: The script MUST **declare**, not merely observe: it writes
  `data/official_rates/ua_nbu_usd.toml` directly, on `scripts/fetch_cpi.py`'s pattern, and does
  **not** write into `data/observations/` for a human to promote.

  This is the one place `scripts/fetch_inzhur.py`'s stricter split — *"it does not verify,
  **and it does not declare**"* (that file, lines 3–17) — deliberately does not apply, and the
  difference is not about trust in the publisher. Inzhur's split exists because promoting one of
  its observations into a declaration is an act of *judgement*: `data/instruments/inzhur_miltech.toml`
  carries a paragraph arguing which of two readings of one observation to take and what it costs
  if that is wrong, and a fetcher rewriting that file *"would delete the reasoning and keep the
  digits"*. Between the National Bank's register and this declaration there is no such
  paragraph to delete: the authority publishes exactly one value per date, there are no
  competing figures to choose between and no reading to argue. The judgement that *does* exist
  here is the quotation unit, and FR-008 keeps it out of the script's hands by making it a
  refusal rather than a choice.

- **FR-003**: The script MUST be **pure of the clock except once**, following `fetch_cpi.py`:
  the rendering function takes the retrieval date as an argument and touches no disk, so the same
  response and the same date render byte-identically. `main` reads the clock once.

- **FR-004**: The script MUST **fail loudly on any shape it did not expect and write nothing at
  all** — a missing field, an unrecognised one, a range shorter than the one requested — naming
  what surprised it. It MUST write **atomically**: built in memory, written to a temporary file,
  renamed, so an interrupted run leaves the previous declaration intact rather than a truncated
  legal series.

  A short range is a shape surprise and not a set of gaps. Writing the short file would turn one
  failed retrieval into a permanent, plausible hole in a legal series, and every date inside it
  would then refuse for a reason that names the series rather than the fetch.

**What `verified_on` means, and what a re-run does to it**

- **FR-005**: The script MUST write `verified_on = ""` on every observation it creates and MUST
  NEVER write a non-empty one. A downloaded number is not a checked number
  (`scripts/fetch_cpi.py:3-10`).

- **FR-006**: `verified_on` on an official-rate observation means: **the owner compared *this
  observation's* value to the National Bank's own published presentation of that date, on that
  day.** It is per observation and says nothing about any other. A re-run MUST therefore:
  - preserve a non-empty `verified_on` on an observation whose `on_date` and `value` are both
    unchanged; and
  - **clear** it when the published value for that date has changed, because the attestation was
    about a different number.

  Stated as a requirement because the alternative reading is the one a reader will assume and
  it is false: at one row per calendar day since 2019-12-28, *"the series is verified"* can never
  be true, and a field
  that means "somebody checked the series" would be a claim nobody could have made. Per-row is
  the only reading under which the field can be honestly filled at all, and it makes a spot-check
  worth performing: the date the owner checked reads verified and every other date reads marked,
  which is a true description of what was done.

- **FR-007**: The **sampling policy** — how many observations the owner spot-checks and by what
  rule they are chosen — MUST be recorded beside the series once he decides it, so the
  marked/unmarked split in any output is explicable rather than arbitrary. It is **owner
  verification task 3**, and it blocks nothing: until it exists, FR-005's empty `verified_on`
  stands on every row and every derived figure renders marked, which is the correct state and the
  one the project already ships everywhere else.

**The quotation unit, and the gap this feature was assigned**

- **FR-008**: The script MUST read the publisher's own `units` field for every row and MUST
  **refuse the whole run** — naming the date, the published unit and the declared one — where any
  row's `units` differs from the series' declared `quotation_unit`. It MUST NOT normalise a value
  to fit the declared unit, and MUST NOT use `rate_per_unit` in place of `rate`.

  This closes the gap `scripts/check_provenance.py:221-241` states and assigns by name: the
  `quotation_unit` exemption drops the citation requirement for the whole `[series]` table, so
  *"nothing verifies it, and a value read as 1 where the publisher quotes per 100 is wrong by two
  orders of magnitude while every figure stays plausible"*, and that comment ends by saying the
  closure *"belongs with whoever builds the fetch script"*. This is that script. The closure is a
  **refusal**, not a conversion: a normalising script would make the declared `value` something
  other than what the published table says, and re-deriving a base by eye against the publisher's
  page — the only check anyone will ever actually perform — would stop working.

  The failure is not hypothetical for this exact series. Read on 2026-08-30 from the range
  endpoint: USD is published with `units = 100` through **2019-12-27** (`rate` 799.3 on
  2014-01-01, i.e. 7.993 UAH per USD) and with `units = 1` from **2019-12-28** onwards. A fetch
  that ignored `units` and reached back into 2019 would write hundreds of rates a hundred times
  too large, and every one of them would look like a rate.

- **FR-009**: Each observation's citation MUST record the publisher's stated `units` for that
  row and the establishment date (`calcdate`) the publisher gives it, in text. The observation
  schema is `extra="forbid"` (`schema.py:2239`) and has no field for either, and adding one is a
  schema change this feature does not need: `data/cpi/ua.toml` already carries its series
  coordinates and the dataset's `metadata_modified` inside the citation string for the same
  reason. Recording `units` per row is what makes the FR-008 refusal auditable after the fact
  rather than only at fetch time.

**The span**

- **FR-010**: The series MUST cover **2019-12-28** through the last date the publisher has
  published at the time of retrieval, and MUST NOT extend in either direction beyond that.

  The lower bound is not a preference. `OfficialRateSeries.quotation_unit` is one value for the
  whole series (`schema.py:2176`), the shipped file declares `1.0`, and 2019-12-28 is the first
  date the National Bank quotes USD per 1 (FR-008's reading). A date before it cannot be carried
  by this series without either a lie about the unit or a value that is not the published one.
  That the bound coincides with the commencement of the Положення that Постанова Правління НБУ
  від 10.12.2019 № 148 approved — *«Постанова набирає чинності з 27 грудня 2019 року»*, quoted in
  `specs/011-official-rate/spec.md`'s owner verification task 1 — is a coherence worth one
  sentence and is **not** the argument; the `units` field is.

  The upper bound is **the retrieval date, not the publisher's last available date**, and the two
  are not the same. The National Bank publishes **one calendar day ahead**: retrieved on
  2026-08-30 the service returns a rate for 31.08.2026 (44.5505, established 28.08.2026) and
  nothing for 01.09.2026. An observation dated after its own `retrieved_on` is refused at load
  (`schema.py:2244-2247`), so a script that simply wrote everything the publisher offered would
  produce a file that **does not load at all**. The script MUST therefore stop at its own
  retrieval date and drop the day the publisher has already set.

  Dropping it costs nothing and is the honest reading twice over: tomorrow's rate is a rate for a
  date that has not arrived, which is the forecast-wearing-an-observation's-clothes case
  `schema.py:2244` is written against, and the next run picks it up as an ordinary observation.

- **FR-011**: Dates before the lower bound MUST refuse rather than being served by a
  reciprocal, a rescale, or a second unit on the same series. If they are ever needed, they are a
  **second series** with its own id and `quotation_unit = 100.0` — a data-only addition under
  011 FR-005 — and this feature declares none.

- **FR-012**: Every date outside the covered window MUST produce `OfficialRateUndeclaredOnDate`
  naming the series id, the pair, the requested date and the covered window
  (`OfficialRateUndeclaredOnDate`'s `reason`, in `core/tax/official_rate.py` — named rather
  than given as a line span, which this feature's own edit to that module would have shifted).
  This feature changes no refusal's shape; it changes what
  the window sentence says, from *"declares no observation at all"* to real dates.

**The publication cadence, and why 017 is not needed**

- **FR-013**: The National Bank returns an official rate for **every calendar day, dated that
  day**, so the declared series MUST carry an observation for every calendar day in its window
  and MUST declare **no** `non_publication_rule`. The rule path in `observation_for`
  (`core/tax/official_rate.py:276-289`) is never reached for this series.

  **This feature therefore requires nothing from `specs/017-working-day-calendar`**, and its
  `needs` entry in `specs/features.toml` was narrowed to `["011-official-rate"]` on the strength
  of the evidence below.

  **The evidence, retrieved twice independently on 2026-08-30.** Range endpoint: 2024-01-01 to
  2024-12-31 returns **366 rows for 366 calendar days, zero missing**; 2022-01-01 to 2026-08-30
  returns **1,703 rows for 1,703 calendar days, zero missing**. Per-date endpoint, retrieved the
  same day by a second retriever: Saturday 2026-08-29 → 44.5445, Sunday 2026-08-30 → 44.5445,
  Monday 2026-08-31 → 44.5505, and the public holiday 2026-01-01 → 42.3532, each row's
  `exchangedate` being the date asked for.

  **The holiday row is not a carry, and that is the interesting part.** 2026-01-01's 42.3532 is
  *not* 31 December's rate — 31.12.2025 was 42.3878 — it is a fresh rate established on
  31 December and dated to the holiday, and 1 January in turn establishes the 42.1701 that
  governs 2–4 January. **Weekends carry; holidays frequently do not.** See FR-015 for what that
  measures.

  **Both retrievals are dated 2026-08-30, and the Monday row is why that has to be said.** The
  31.08.2026 row was *retrieved on* 2026-08-30, because the publisher runs a day ahead (FR-010);
  its `exchangedate` is not the date anybody fetched it. An earlier draft of this specification
  recorded that retrieval as having happened on 2026-08-31 — taking the observation's date for
  the retrieval's — which is `on_date > retrieved_on`, the exact confusion FR-010 refuses at the
  data boundary, committed in this document's own provenance. Corrected before landing. The row
  it concerns is the one FR-010 makes the script drop.

  The one window worth reading in full, because it shows both підпункти of пункт 10 in five rows
  — Thursday 2026-08-27 establishes 44.5445, which is in force on Friday, Saturday and Sunday;
  Friday 2026-08-28 establishes 44.5505, which takes effect on Monday:

  | date in force | rate | `calcdate` | |
  |---|---|---|---|
  | Thu 2026-08-27 | 44.5717 | 2026-08-26 | |
  | Fri 2026-08-28 | 44.5445 | 2026-08-27 | |
  | Sat 2026-08-29 | 44.5445 | 2026-08-27 | |
  | Sun 2026-08-30 | 44.5445 | 2026-08-27 | |
  | Mon 2026-08-31 | 44.5505 | 2026-08-28 | ← published a day ahead; dropped by FR-010 |

  **Why this is not the forbidden shortcut.** 011 FR-018 and
  `data/official_rates/ua_nbu_usd.toml:42-44` refuse the encoding *"the latest observation on or
  before the event date"*, because the engine would be deriving a weekend rate and could not tell
  a weekend from a gap. Nothing here derives anything. The value for a Sunday is **retrieved from
  the authority, against that Sunday**, and `calcdate` records which day's establishment produced
  it. Declaring it is entering a published fact; deriving it would be inventing one. Under 011
  FR-011's own definition a rule is *"a statement of which declared observation governs a date
  the publisher does not publish for"* — and where the publisher publishes for every date, there
  is no such date and nothing for a rule to say.

- **FR-014**: What FR-013 settles is a fact about **publication**, and it MUST NOT be presented
  as more than that. Whether the value returned against a Sunday **is the official rate in force
  on that Sunday in the sense the Tax Code means**, or is Thursday's rate displayed under
  Sunday's date, is a question about legal effect, and the retrieved data is consistent with both
  readings — `calcdate` naming an earlier day is exactly what keeps it live. No legal value may
  rest on an agent's reading (Principle I), so it is **owner verification task 1** and the two
  documents that close it are named there.

  This is not the kind of question the owner's standing instruction is about. It is not an ІПК
  question and not a moving target: it is a fixed provision somebody reads once. It is recorded
  as **unread**, with the texts named — not as unknowable.

- **FR-015**: If owner verification task 1 resolves against the in-force reading, the series
  declares observations only for dates the National Bank *established* a rate on, every other
  date refuses under FR-012, and closing those dates needs the declared working-day and holiday
  calendar of **`specs/017-working-day-calendar`** plus a cited non-publication-day rule evaluated
  against it — which would restore this feature's dependency on 017. This feature MUST NOT design
  that calendar (011 FR-018). SC-018 is that branch's criterion.

  **Any such rule MUST be sourced from пункт 10 and MUST NOT be the last-working-day heuristic**,
  and the reason is a measured number rather than a principle. The owner's declared carry-forward
  rule — *if there is a rate for the day use it, otherwise take the last working day's* — has its
  second clause made unreachable by FR-013. The 018 review checked on 2026-08-30 what would
  happen if it ever fired: on **18 of the 43** fixed-date Ukrainian public holidays between
  2022-01-01 and 2026-08-30, the National Bank publishes a rate that **differs** from the last
  working day's, because it establishes a fresh one for the holiday. **Three of the eighteen are
  1 January and three are 25 December** — precisely the dates where an official rate decides
  which **tax year** an income falls into.

  Two of the eighteen, re-retrieved at source on 2026-08-30: 2026-01-01 published **42.3532**
  against 31 December's **42.3878**; 2026-05-01 published **43.963** against 30 April's
  **44.082** — 0.08% and 0.27% wrong respectively, with every figure staying entirely plausible.

  The count of 18-of-43 is **the review's, carried with its date and not re-derived here**,
  because re-deriving it means declaring which dates are Ukrainian public holidays, and that is
  exactly the declaration 011 FR-011 forbids this feature and `specs/017-working-day-calendar`
  exists to make. The two examples are this specification's own retrieval; the count is cited.

  So retrieving every calendar day and deriving nothing is not merely the tidier option. It is
  the only correct one, and the margin is measurable.

  Stated so the narrowing in `specs/features.toml` is honest about what it rests on: the graph
  was narrowed on the **publication** fact, which is settled, and this is the one reading that
  could put 017 back.

**The prohibition, now that there is something to substitute**

- **FR-016**: Populating the series MUST NOT change any cost, route, leg, channel or ranking
  figure anywhere in the system. Asserted over the goldens rather than argued
  (SC-009).

- **FR-017**: No channel, `reference_rate`, cost model, valuation or return figure may take its
  rate from this series, and this feature MUST add no path — no fallback, no default, no
  "reference" option — by which one could. The `.importlinter` contracts
  `official-rate-never-prices-a-leg` (`.importlinter:94`) and `no-tax-base-from-a-channel`
  (`.importlinter:111`) and the source scan in
  `tests/contract/test_the_rate_you_are_taxed_at.py` MUST remain exactly as they are and MUST
  still pass.

- **FR-018**: `data/channels/uah_usd.toml`'s synthetic `reference_rate` values MUST be left
  untouched, still marked synthetic and still unverified. A real official rate is not a repair
  for an invented channel quote; substituting one would be exactly the conflation FR-017
  forbids, arriving as a tidy-up.

- **FR-019**: The refusals that exist because no valuation rate is declared —
  `RateNotComparable` (`core/results/tuple.py:438`),
  `ForeignGainNotStruckPerDate` (`core/tax/year.py:725`),
  `TaxCurrencyConversionUnavailable` (`core/results/tuple.py:826`) — MUST still refuse after this
  feature. A populated official-rate series is not a valuation rate and does not close any of
  them.

**Provenance, reproducibility and what volume breaks**

- **FR-020**: The run manifest MUST name the official-rate series a result's tax bases rested on
  and the version of the file that declared it. `InputKind` (`src/terezy/data/manifest.py:129`)
  is a closed `Literal` of five members with no official-rate entry, so today no manifest can
  and no golden records it. While the series is empty that is invisible; once a tax base rests on
  it, a result whose manifest cannot name the rate file is not reproducible, which Principle III
  says is not a result.

- **FR-021**: Every figure derived through an official-rate conversion MUST carry the union of
  the converted amount's provenance and the observation's, unchanged from 011 FR-015. This
  feature adds no transform between the observation and the base.

- **FR-022**: Observation lookup MUST NOT be linear in the number of observations per lookup.
  `observation_for` rebuilds a date-keyed dict of every observation on **every call**
  (`core/tax/official_rate.py:272`). At zero observations that is free, which is why it has never
  mattered; at one observation per day since 2019-12-28 and one lookup per taxable event it is
  O(rows × events). This
  is the one place in this feature where row count bites the engine, and it is a defect the empty
  series has been hiding.

- **FR-023**: `scripts/check_provenance.py` MUST report unverified values **per file** rather
  than one line per value. Measured on 2026-08-30: the gate reports **704 unverified values**
  across 32 files in 0.45 s. Adding ~2,400 unverified observations takes it to ~3,100 lines and
  buries the 704 that a human is supposed to read. Runtime is not the problem and never becomes
  one; legibility is, and a gate whose output nobody reads is a gate that is off. Errors stay
  per-value: an error is a thing to be fixed and there will be none of them.

- **FR-024**: The generated file MUST carry a header stating that it was written by the script,
  that it must not be hand-edited, what its coverage window is, and that every `verified_on` is
  empty — `data/cpi/ua.toml:1-17`'s shape. It MUST also keep the two arguments the current file
  carries that survive this feature: that a date outside the window refuses rather than being
  interpolated, and why the *"latest observation on or before"* encoding is refused.

**The licence the data comes under**

- **FR-025**: Every observation's citation MUST carry the **URL it was retrieved from**, and the
  file header MUST name **both** provisions below, distinguishing what each one does. Attribution
  is a **term of reuse, not a courtesy**.

  **Two texts, and they do not say the same thing.** Both were read at source on 2026-08-30 at
  `zakon.rada.gov.ua/laws/show/<id>/print`:

  - **ст. 10¹ ч. 2 абз. 2 ЗУ № 2939-VI «Про доступ до публічної інформації»** — the operative
    term, addressed to *any person*: *«Будь-яка особа може вільно копіювати, публікувати,
    поширювати, використовувати, **у тому числі в комерційних цілях**, у поєднанні з іншою
    інформацією або шляхом включення до складу власного продукту, публічну інформацію у формі
    відкритих даних **з обов'язковим посиланням на джерело отримання такої інформації**.»*
    Free reuse including commercial, conditional on a mandatory reference to the source. **The
    word «гіперпосилання» does not appear anywhere in this act** — zero occurrences in the whole
    text.
  - **п. 17 Положення, затвердженого постановою КМУ від 21.10.2015 № 835** — where the hyperlink
    wording lives, and it is the text of a notice the *розпорядник* must display on each dataset
    page rather than a term addressed to a reuser: *«Умовою будь-якого подальшого використання
    відкритих даних є обов'язкове посилання на джерело їх отримання (**у тому числі
    гіперпосилання** на веб-сторінку відкритих даних розпорядника інформації).»* Note the form:
    «у тому числі» — a hyperlink is named as one way of referring to the source, not as a separate
    requirement.

  **What this feature does about the difference: satisfies both and asserts neither.** A citation
  carrying the retrieval URL is a «посилання на джерело отримання» under ст. 10¹ and is a
  hyperlink besides, so the requirement is met on either reading and this specification does not
  have to decide which text binds a reuser — a question of legal effect it has no standing to
  settle.

  **How the mis-citation entered, recorded so it does not enter again.** The National Bank's own
  page prefixes п. 17's notice with *«Відповідно до статті 10¹»*, so the hyperlink wording reads
  as if it were statutory. An earlier draft of this specification took that reading second-hand
  from feature 016's parallel work and put *"ст. 10¹ … conditional on attribution with a
  hyperlink"* into **every one of ~2,438 observations**, with a success criterion checking
  mechanically that the header said so. A wrong statutory citation would have become a green
  gate — which is worse than an uncited value, because a gate asserts it was checked. Caught in
  review; the fix was reading both texts, which took one retrieval each.

  This also settles a loose end in "The volume, and why the container does not change": a
  per-row citation carrying the retrieval URL means any row quoted anywhere carries its own
  attribution, and the self-citing shape stops being only a provenance preference.

### Key Entities

Every entity this feature touches already exists and is defined in
`specs/011-official-rate/spec.md`. What is new is data and the machinery around retrieval:

- **The retrieval script** — a repository script outside `core/`, reading the National Bank's
  statistics service and writing one declaration file. Retrieves, never verifies; declares,
  because there is no judgement between the register and the declaration (FR-002); refuses on a
  unit mismatch or a shape surprise rather than adapting.
- **The covered window** — the pair of dates the series' first and last observations give,
  already computed by `covered_window` (`core/tax/official_rate.py:251`). Newly meaningful: it is
  what every refusal outside it will now name.
- **The establishment date** — the publisher's `calcdate`, the working day on which a rate was
  set. Not a declared field; carried in each observation's citation (FR-009), where it makes a
  weekend observation visibly the publisher's carry rather than the repository's.
- **An official-rate input reference** — the manifest entry FR-020 requires, so a run can name
  the version of the rates it rested on.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A dollar-denominated taxable event on a date inside the covered window produces a
  hryvnia base matching hand arithmetic on the National Bank's published rate for that date,
  within the single project tolerance, with the arithmetic checked in beside the assertion.
  (FR-001, FR-010)
- **SC-002**: The same dollar credit charged under `ua_fop_group_3` and under
  `ua_personal_income` produces two charges on one hryvnia base, and the resulting comparison is
  produced — where today, on the shipped data, it cannot be produced at all. Demonstrated by a
  test that fails on `main` before this feature with a rate-unavailable refusal. (User Story 1)
- **SC-003**: Across a battery of uncovered dates — before the first observation, after the last,
  and a declared instrument's own 2029 payment date — 100% refuse naming the series, the pair,
  the date and the covered window, and 0% produce a number. No flag, option or configuration
  makes any of them interpolate, extrapolate, carry forward or snap. (FR-012)
- **SC-004**: The script run twice on the same day against the same response produces
  byte-identical files. (FR-003)
- **SC-005**: Given a response carrying any row whose `units` differs from the declared
  `quotation_unit`, the script exits non-zero naming the date and both units, and the existing
  file is byte-identical afterwards. Given a range shorter than requested, likewise. (FR-008,
  FR-004)
- **SC-006**: Every observation in the landed file carries a non-empty `source` naming the
  endpoint, its query and the publisher's stated `units` for that row; a `retrieved_on`; and a
  present, empty `verified_on`. 100% of them, checked mechanically rather than by sampling.
  (FR-001, FR-005, FR-009)
- **SC-007**: With a `verified_on` filled by hand on one observation, a re-run against an
  unchanged published value preserves it; a re-run against a changed value clears it. (FR-006)
- **SC-008**: 100% of tax bases and charges struck from an unverified observation carry the
  unverified mark, and every figure derived from them does too. (FR-021)
- **SC-009**: Every golden's cost, route, leg, channel and ranking digest is bit-identical
  before and after the series is populated; the only digests that move are the input digest of
  the rate file and the tax figures struck through it. Stated as the diff of one commit, not as a
  claim. (FR-016)
- **SC-010**: `data/channels/uah_usd.toml` is unchanged by this feature's diff, and its
  `reference_rate` values still read `42.0` and still carry the synthetic-fixture marking.
  (FR-018)
- **SC-011**: Both `.importlinter` contracts and
  `tests/contract/test_the_rate_you_are_taxed_at.py` pass against the landed feature, over a
  series that now carries values. (FR-017)
- **SC-012**: A result whose tax base was struck at an official rate carries, in its manifest,
  the series id and the file's digest; editing one observation moves that digest. (FR-020)
- **SC-013**: Striking N tax bases against the populated series performs no work proportional to
  N × the number of observations — asserted as a property of the lookup, not by timing.
  (FR-022)
- **SC-014**: `scripts/check_provenance.py` reports the landed file as one summary line, and its
  total output does not grow by more than a constant number of lines because of this feature.
  Errors remain per-value and number zero. (FR-023)
- **SC-015**: `docs/METHODOLOGY.md` gains the covered window, the lower bound's reason (the
  publisher's own unit change) and what falls outside it, in the same change that lands the data.
  (constitution's documentation clause)
- **SC-016**: `docs/REQUIRED_TESTS.md` rows are flipped only for what this feature actually
  closes. F1, F2 and F3 stay open — see "Required tests this feature relates to".
- **SC-017** *(conditional on owner verification task 1 confirming the in-force reading)*: The
  landed series declares an observation for **every calendar day** between its first and its
  last, with zero missing, and declares no `non_publication_rule` — checked by counting, not by
  reading. (FR-013)
- **SC-018** *(conditional on owner verification task 1 resolving the other way)*: The landed
  series declares an observation **only** on dates the publisher's `calcdate` shows a rate was
  established, every intervening date refuses under FR-012 naming the window, and any rule that
  closes those dates cites пункт 10 and is evaluated against 017's declared calendar. **No
  criterion is satisfied by a rule derived from the last-working-day heuristic** — see FR-015 for
  the measured reason. (FR-015)

  SC-017 and SC-018 are **mutually exclusive by construction**, and are written as a pair because
  the alternative was worse: a single unconditional SC-017 would have been a criterion the
  *correct* implementation must fail if task 1 resolved the other way, while FR-015's branch had
  none at all. FR-015 was hedged and its criterion was not.
- **SC-019**: 100% of observations carry the URL they were retrieved from in their citation,
  checked mechanically; and the file header names **both** ст. 10¹ ч. 2 ЗУ № 2939-VI and п. 17
  Положення № 835, saying which is the term on a reuser and which is the notice on the publisher.
  No criterion asserts that either one alone is the source of the hyperlink wording. (FR-025)
- **SC-020**: No observation in the landed file is dated later than its own `retrieved_on`, and
  the file loads. Given a response carrying the publisher's day-ahead rate, the script drops it
  rather than writing a file that fails at load. (FR-010)

## Assumptions

- **One series, one pair, one jurisdiction.** UAH/USD for UA. A second pair or a second authority
  is a data-only addition under 011 FR-005 and is not made here.
- **No new tax behaviour.** Every conversion, refusal, mark and record in the tax path is 011's
  and 012's, called unchanged. What this feature adds is values, a script, a manifest entry, a
  lookup index and a gate's output format.
- **No delivery surface.** As in 011 and 012, results are produced and asserted by the test
  suite. Feature 015 is what puts a question in front of the owner.
- **Tests never reach the network** (constitution, Principle V). The fetch script is exercised
  against checked-in captured responses; the landed data file is the offline snapshot. The
  script's own live run is an operator action, not a test.
- **No fixture may be mistaken for a real rate.** Test fixtures continue to use the synthetic
  series and clearly-labelled invented values that 011 established
  (`tests/official_rates.py`), and no test may take a value from `ua_nbu_usd.toml` and restate it
  as a literal — a literal copied out of a real series is a rate with no citation the moment the
  file moves. Fixtures are the synthetic series; real values are read from the declaration.

## The volume, and why the container does not change

One observation per calendar day from 2019-12-28 to the retrieval date — **2,438 of them for a
run on 2026-08-30**, and one more every day after. Every count in this section is that figure,
and grows with it. That is more rows than
everything under `data/` put together, and a planner will reasonably ask whether a `data/` TOML
file is still the right container. It is. The argument, with the numbers it rests on, is here so
it is not re-derived:

**What volume costs, measured on 2026-08-30:**

- **The goldens: nothing.** `manifest.file_version` (`src/terezy/data/manifest.py:203-221`) is a
  sha256 over the file's bytes, recorded as one line. Two and a half thousand observations cost a golden exactly
  what 0 do. What is *not* free is cadence: any re-fetch rewrites `retrieved_on` and moves that
  digest, so a golden recording this file is regenerated on every re-fetch. Principle V says that
  is correct — an input digest is a witness, not a term — and it is a standing chore rather than
  a reason to hold data out of a file.
- **Runtime: nothing.** `scripts/check_provenance.py` walks 32 files including
  `data/cpi/ua.toml`'s 411 observations in **0.45 s**. Parsing is linear and the constant is
  tiny.
- **The gate's output: this is the real cost.** The gate emits one warning line per unverified
  value and today reports **704** of them. ~2,400 more takes it to ~3,100 lines and buries the
  704 a human is supposed to read. A gate whose output nobody reads is a gate that is off. FR-023
  fixes it, in the script, in one place.
- **The engine: one hidden defect.** `observation_for` rebuilds a date-keyed dict of every
  observation on **every call** (`core/tax/official_rate.py:272`). Free at zero rows, O(rows ×
  events) at 2,438. FR-022 fixes it.
- **The reader and the diff.** In `data/cpi/ua.toml`'s shape — 747 bytes per observation, because
  a ~300-character citation is repeated on every row — the file is roughly **1.8 MB and 19,500
  lines**. Everything under `data/` today is 8,418 lines.

**Two alternatives, and why neither is taken:**

*A compact shape* — a series-level citation inherited by rows, and one line per observation —
would be ~150 KB and ~2,438 lines. It is genuinely smaller and it is refused, because it buys
line count with the one property that matters here: a self-citing row is a row whose provenance
is true on its own, and an inherited one is a row whose citation is correct only if the loader
that assembled it is. This feature's whole claim is that it does not touch the tax path, and
rewriting the schema and the loader that build every rate observation's `SourceRef` is the
largest change it could make to it. `one fact, one place` is also not an argument for
compacting here: it is a rule about facts that can *drift*, and a machine-written file that a
header forbids hand-editing cannot. FR-025 adds a second reason that is not a preference at all:
reuse is conditional on a reference to the source, and a per-row citation carrying the retrieval
URL means any row quoted anywhere carries its own attribution.

*A CSV sidecar with a hash in the TOML* is refused for a stronger reason. `check_provenance.py`
globs `*.toml` under each of its sourced directories and nothing else
(`scripts/check_provenance.py:634`); a CSV is invisible to the one gate
whose entire job is to see that every value carries a citation, and a hash pinning a sidecar
attests that a file did not change, not that its values are cited. That is a real loss of
provenance in exchange for line count, which the first alternative already buys more cheaply.

**And the span is not narrowed to make the file smaller.** A shorter window would work — 2024
onwards is 973 rows — and every date outside it would refuse. But a refusal is supposed to be a
fact about the publisher, not about a line budget, and a coverage window chosen for the tool's
convenience makes every refusal at its edge unexplainable. FR-010's lower bound comes from the
publisher's own `units` field and from nothing else.

## Known consequence: staleness lands on dates it cannot be about

`official_rate` declares `staleness_days = 7` (`data/observation_kinds.toml:71-74`) and its own
note gives the reason: what ages is the **retrieval**, because *"a series fetched a month ago is
a month short of its own end"*. Staleness is then measured per observation, from the later of its
verification and retrieval dates (011 FR-006).

The two do not line up once the series is real. A base struck on a date in the middle of the
covered window is not affected in any way by the series missing its recent end, but it will
report staleness eight days after the fetch all the same, because its observation shares the
file's `retrieved_on`. The mark will be technically true of the observation and irrelevant to the
figure — which is the shape of a warning that trains a reader to ignore warnings.

This feature **does not change it**: the threshold is 011's declared policy, changing it changes
an already-landed behaviour, and getting it right needs a notion of staleness measured against
the *distance from the series' end* rather than against every row's retrieval date. Recorded here
with its date so it is a known consequence rather than a surprise, and recorded as the
`official-rate-staleness-by-distance` `[[future]]` entry in `specs/features.toml` when this spec
lands.

## Clarifications resolved

One question was raised while writing this specification and it is resolved. What remains of it
is a reading, not a design choice, and it is owner verification task 1.

| # | Question | Decision | Where it landed |
|---|---|---|---|
| 1 | Does the National Bank publish a rate for days it does not set one — weekends, holidays — or does the series have gaps a working-day calendar would have to fill? | **It publishes one for every calendar day, dated that day.** Retrieved 2026-08-30 (366 rows for 366 days in 2024; 1,703 for 1,703 days over 2022-01-01..2026-08-30, zero missing) and confirmed independently the same day by a second retriever against the per-date endpoint, for a weekend, the day-ahead Monday and a public holiday. So the series declares every calendar day, declares no non-publication rule, nothing is derived, and **017 is not required by this feature** — its `needs` was narrowed to `["011-official-rate"]` in the same commit. | FR-013, FR-015, SC-017; `specs/features.toml` |

What the retrieval settles is **publication**, and the separate question of legal **effect** — is
the value returned against a Sunday the rate in force on that Sunday in the sense the Tax Code
means — is deliberately not answered by it. That is owner verification task 1.

## Owner verification tasks

Three are open. None blocks planning: the behaviour in the absence of each is specified
completely, and each ships its gap in the output rather than only in prose.

1. **Whether the rate returned against a non-working day is the rate *in force* on that day.**
   The publication fact is settled (FR-013). What is unread is the legal effect, and the data is
   consistent with two readings: the value dated Sunday is the official rate for Sunday, or it is
   Thursday's rate displayed under Sunday's date. `calcdate` naming an earlier day is what keeps
   the question live.

   **Two documents close it, and both are fixed provisions somebody reads once:**
   - the National Bank's regulation on setting the official rate — the Положення that
     **Постанова Правління НБУ від 10.12.2019 № 148** approves, **пункт 10 розділу III**, whose
     text, amendment markers and working retrieval form are quoted in
     `specs/011-official-rate/spec.md`, owner verification task 1. **Deliberately not copied
     here**: 011's copy is the one that is right, and every further copy made so far is what went
     wrong;
   - **пп. 164.4 та п. 292.5 ПКУ** on which date's official rate a taxable amount converts at —
     the general rule and the ФОП-single-tax rule respectively, which is why both are named:
     012's comparison runs one dollar credit through both regimes.

   This is **not** an ІПК question and not a moving target, so the owner's standing instruction
   about questions that do not converge does not apply: it is recorded as **unread**, not as
   unknowable, and it should not take more than one reading.

   Until it is read, FR-013's series ships and every base struck from it is a base struck at the
   rate the National Bank dated that day. If the reading goes the other way, FR-015 says what
   changes and that 017 comes back.

2. **The quotation-unit change date.** That the National Bank moved USD from `units = 100` to
   `units = 1` on 2019-12-28 is read off the publisher's own API and is the load-bearing half of
   FR-010's lower bound. It is worth one confirmation against the National Bank's human-readable
   rate table, because the whole span rests on it and the failure mode is a factor of one
   hundred.

3. **The verification sampling policy** (FR-007): how many observations the owner spot-checks and
   by what rule they are chosen. It is a policy about his own effort, not a fact about the world,
   so no source settles it. Meanwhile every `verified_on` is empty and every derived figure
   renders marked.

## Required tests this feature relates to

- **F1** (*"A position flat in USD across a devaluation produces a positive taxable gain in
  UAH"*) is **not closed**. `specs/features.toml`'s `fx-tax-asymmetry-f1` entry names what
  remains after 011: a per-lot basis carried in both currencies with each leg struck at its own
  date's official rate, and a projection fold that does not sum a hryvnia charge inside a dollar
  holding. This feature supplies neither; it supplies the rates both would read. The refusal
  `ForeignGainNotStruckPerDate` must still refuse (FR-019).
- **F2** (*"Switching display currency changes no realised amount, no tax figure, and no
  after-tax UAH ranking"*) is not closed — there is no display switch — but SC-009 establishes
  the "no cost or ranking figure moves" half against real data for the first time.
- **F3** (*"Historical series convert at per-date rates, never at today's rate"*) is **not
  closed and is deliberately not attempted**, for the reason 011 gives: F3 is about a display
  switch converting a chart, which is a channel-rate question about presentation. Sharing the
  phrase "per-date rates" with this feature is a coincidence of wording, and treating them as
  one requirement would conflate the display and tax roles in the one place the constitution
  names explicitly.
- Per the constitution, the arithmetic lands as a hand-computed worked example (SC-001, SC-002),
  the refusals as refusal coverage (SC-003), the script's failures as load/fetch failure coverage
  (SC-005), the marks as propagation checks (SC-008), and SC-009 and SC-011 as `contract` tests,
  since they are compliance statements about Principle VI rather than assertions about one call
  site.

## Out of scope

Named so the plan does not drift into them: the declared working-day and holiday calendar
(`specs/017-working-day-calendar`), which FR-013 establishes this feature does not need, and any
non-publication-day rule at all; a
second series for the per-100 era; any second currency pair or second authority; the `Provider`
interface and the general automated fetch layer, still the `provider-automation` `[[future]]`
entry — this feature builds one script, not a layer; changing the `official_rate` staleness
threshold or how staleness is measured; a foreign-currency-denominated instrument, a per-lot
two-currency basis, and therefore F1; the FX gain or loss as a named attribution line; the
display-currency switch; any change to how channels, legs, routes or costs are computed, which
this feature explicitly leaves untouched and asserts it has left untouched; and the web and
command-line interfaces.
