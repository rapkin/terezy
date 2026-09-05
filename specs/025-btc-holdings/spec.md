# Feature Specification: The BTC he already holds

**Feature Branch**: `025-btc-holdings`

**Created**: 2026-09-06

**Status**: Draft

**Input**: The owner, 2026-09-02 and 2026-09-03 — he holds BTC in two lots, is not selling it,
and wants it counted rather than bought; the price comes from Binance's public API, fetched by a
script; the tax treatment is refused until a cited primary source is entered as data.

## Why this feature exists

Two of the four words in `data/questions/fifty-thousand.toml` resolve to nothing. `btc` is one,
and 015 FR-009 puts it in the answer's undeclared population by the word the owner wrote. 015's
owner verification task 2 says what would close it — an instrument, an access declaration and a
settled tax class, "every part of it a legal or market value that must come from a cited source
entered as data".

He has now supplied the half that is his to supply: a position, in two lots, that he does not
intend to sell. Nobody has supplied how Ukraine taxes its disposal. So this feature closes the
market half and **refuses the legal half by name** — a position whose value is reported and
whose tax is a named refusal tells the truth about both, where one quietly reporting no tax
would flatter it.

Three things stand between the position and a figure, each missing for a different reason: his
real figures may not be committed (`data/README.md` rule 5, and `data/user/` is gitignored but
named in `src/terezy/data/citation_policy.py` as the place a *run* writes its output, read by
nothing); every member of `registry.DECLARATION_KINDS` projects a schedule out of declared terms
and a bitcoin has none; and `src/terezy/data/providers/` is an empty package with a docstring,
`Provider` being one of Principle II's four interfaces that nothing implements.

**A held position is not a candidate.** He is not buying BTC with the 50 000 and not selling what
he holds. Every candidate here is new money deployed — 010's key is `(instrument, stream,
route_in, exit_terms, route_out)` and `route_in` is required — so a holding never funded through
a declared corridor cannot be one without first closing the `zero-hop-way-in` future. That is a
different feature, and it is why FR-029 exists.

## The decisions behind the requirements

**The overlay refuses a collision where the test overlay replaces.** `tests/data_roots.py`
composes the shipped root with a fixture tree, and a fixture *replaces* a shipped file of the
same path — right for a test wanting to plant a malformed instrument over a good one, wrong here:
a private overlay must never let an uncommitted file silently change what a reviewed one said.

**`held_asset` is a fourth declaration kind, not a fifth interface.** Like a fund it stays out of
`registry.REGISTRY`, and for a stronger reason: it projects no event stream at all, so there is
no part of `InstrumentOps` it could satisfy — the ruling the owner made for the fund on
2026-08-23. It declares neither its price (an observation) nor its quantity (the owner's seed
lots); FR-009 has the rest.

**Klines over the ticker.** Binance's public market-data REST was the owner's choice on
2026-09-03: no key and no account, it covers every crypto ticker the same way so a second is
data, and `binance` is already a venue on his route graph. `GET /api/v3/klines` with
`interval=1d` is taken over `GET /api/v3/ticker/price` because a ticker returns one number with
no date on it — it could only become a dated observation by the script stamping a date the
publisher never gave — and a daily close series is what a later return series needs anyway. Both
are documented as requiring neither an API key nor a signature, and klines as returning
twelve-element rows, `[openTime, open, high, low, close, volume, closeTime, quoteAssetVolume,
numberOfTrades, takerBuyBaseAssetVolume, takerBuyQuoteAssetVolume, ignore]` (retrieved
2026-09-06), so the close is element 4 and its date element 0.

**This is the first observation file read at run time**, and `data/README.md` says today that
`observations/` is "read by nothing at run time". That claim becomes false and is corrected. The
Inzhur precedent — a script writes an observation and a human promotes one figure into an access
declaration — works because a fund's NAV is a low-frequency figure with a judgement in it,
between two readings of one number. A daily close has no judgement in it: the publisher publishes
one value per day, and promoting it by hand would be transcription, which is where a wrong number
enters. That is `scripts/fetch_nbu_rates.py`'s own argument for declaring rather than observing,
and `data/observations/` is already scanned by the provenance gate.

**The quote asset is USDT, and USDT is not USD.** `BTCUSDT` is priced in a dollar-referenced
token and nothing here says what one is worth in dollars — Clarification 1, not closed by
assumption.

**008 FR-010 is narrowed, and saying so is the point.** His costs are in dollars, and 008 FR-010
says a seed's cost is in the base currency with no `currency` key. **That rule is narrowed here,
not left unchanged**, and pretending otherwise puts an error the size of the exchange rate under
a straight face: the
loader tags a declared cost `Money(x, base_currency)` today, so a dollar figure declared as it
stands becomes hryvnia and the position's basis is wrong by the exchange rate.

The narrowing: a seed's cost is in the base currency **unless the instrument it names declares a
different price currency**, in which case it is in that one. The fact stays out of the seed file
— 008 FR-010's "no `currency` key" survives, because the currency lives on the instrument, which
is where it belongs and where a second lot cannot contradict it. What changes is the reading of
"base currency", and 008 FR-010's own second sentence anticipated the change: "converting a
foreign-currency basis at the dated official rate arrives with the FX features". 011 and 018 are
those features.

**The strike happens where both facts are in hand**, which is the resolver — it holds the
instrument declarations and can be given the rate series; the loader holds neither, and by the
time a lot reaches the ledger its cost is already tagged. `data/official_rates/ua_nbu_usd.toml`
covers 2019-12-28 to 2026-08-31 with no gaps, and a lot acquired outside that window refuses
under FR-028. Whether either of his falls inside is not a fact this repository holds; what is
certain is that the series stops six days before this was written, so a recent acquisition
refuses — the refusal's live case, not a guard nothing reaches.

## The record shape

The owner's figures are **not reproduced here**. What the file looks like, with placeholders:

```toml
# data/user/seeds/owner-001.toml — GITIGNORED. NEVER COMMITTED.
# Every number below is a PLACEHOLDER. His are in this file on his machine and nowhere else.
[owner]
id = "owner-001"

[[seed]]
is_synthetic  = false
instrument_id = "btc"
quantity      = 0.5
acquired_on   = "2024-02-29"
cost          = 12_345.0
basis         = "estimated"
reason        = "<the owner's own words>"
```

The field names are 008's unchanged. `cost` is read in the instrument's declared currency
(FR-025), `is_synthetic = false` is legal only under this root (FR-005), and this file is the
only place in the system his real numbers exist.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The position is counted (Priority: P1)

He declares his two lots under `data/user/`, runs the fetch script, and asks his question. The
answer states the quantity he holds, what it is worth at the observed price and on what date
that price was observed, what it cost him in hryvnia, and the nominal difference between the
two. Every one of those figures carries both marks it rests on: the basis is his estimate and
the price is unverified.

### User Story 2 - The tax is refused by name (Priority: P1)

The same run reports no tax figure for the position, and says so with the class the instrument
names and the sentence that nothing declares it. It does not report zero, and it does not omit
the row.

`UnresolvedTaxClass` already says why: "treating the holding as untaxed would be the single most
expensive silent default available in this domain", and a crypto disposal in Ukraine is exactly
where the flattering answer is the wrong one.

### User Story 3 - A private figure cannot leak into the repository (Priority: P1)

A real (non-synthetic) seed placed under `data/` fails to load, naming the file. A record present
under both roots fails to load, naming both paths. Running with no `data/user/` at all works and
declares nothing.

The overlay is how real money enters the system, so the gate keeping it out of git belongs in
the loader rather than in a reviewer's attention.

### Edge Cases

- **No observation for the symbol, or none dated `as_of`.** The position reports its quantity
  and refuses its value by name. It does not report zero and does not fall back to the basis.
- **The file has aged past the run.** There is no stale-but-usable price here: a file whose
  newest closed day is older than `as_of` has no row for `as_of` and refuses by name. Ageing and
  refusing are the same event under FR-011 and FR-024, which is why the threshold is inert.
- **The fetch fails or returns a shape the script does not recognise.** Nothing is written and
  the previous observation file stands unchanged, on `scripts/fetch_nbu_rates.py`'s precedent.
- **A seed lot whose acquisition date is outside the official-rate window.** 011 FR-010's typed
  refusal, naming the series and the date. Unreached by his two lots.
- **`data/user/` exists but is empty.** Identical to it not existing.

## Requirements *(mandatory)*

### Functional Requirements

**The private overlay**

- **FR-001**: The declaration loader MUST read a second root, `data/user/`, layered over the
  shipped `data/`, and MUST resolve declarations from the composition of the two.
- **FR-002**: An absent or empty `data/user/` MUST be an ordinary state producing no declaration
  and no warning, on 008 FR-024's precedent.
- **FR-003**: A collision MUST refuse at load naming both paths, and two identities are needed
  because a seed lot has no id. For a declaration carrying one — an instrument, a group — the
  collision is **that id under both roots**, and the overlay MUST NOT override or shadow it.
  For seeds it is **the same owner holding the same instrument in both roots**: two roots
  declaring lots of one instrument cannot both be his position, while lots of *different*
  instruments are two halves of one portfolio and MUST be **unioned**, not one replacing the
  other. `resolver._at_most_one` resolves one seeds file per root, so the overlay's file
  necessarily carries the same name; the union is what makes that not an override.
- **FR-004**: Overlay files MUST be validated by the same schemas and fail as loudly (data rule
  1). The overlay is not a looser dialect.
- **FR-005**: `is_synthetic = false` MUST be accepted only under the overlay; declared under
  `data/` it MUST refuse at load naming the file — rule 5 made mechanical rather than reviewed.
- **FR-006**: The directories the overlay may contain MUST be declared and fail-closed — an
  undeclared one is an error, never a blind spot (`scripts/check_provenance.py`'s rule). This
  feature declares `seeds/` and nothing else.
- **FR-007**: The provenance gate MUST NOT scan the overlay, and `data/user/` MUST remain
  gitignored. Its recorded exemption reason MUST be corrected: it now holds the owner's own
  declarations, exempt for the reason `seeds/` is exempt, rather than run output.
- **FR-008**: The run manifest MUST record the overlay's input on the same terms as every other
  — its path and the digest of its bytes, which `InputRef` requires — under an id prefixed
  `user/`, because `file_name()` renders both roots' seeds file identically and the prefix is the
  only thing telling them apart. It MUST NOT record a declared value. `InputKind` is a closed
  `Literal` with no seed member and MUST gain one; `check_enumerations.py` gates `Literal`
  alternatives, so a forgotten member is a red gate rather than drift.

**The held asset**

- **FR-009**: The system MUST accept a declaration kind for an asset held for its price alone:
  an id, a name, a quantity unit, a price currency, the venue it sits at, groups and a tax class
  reference — no coupon, no maturity, no yield, no schedule. It declares **no access entry**:
  `data/access/` says what a unit costs to buy, and he is not buying.
- **FR-010**: It MUST NOT enter `registry.REGISTRY` and MUST add no fifth plugin interface: it
  projects no event stream, so there is nothing for `InstrumentOps` to hold.
- **FR-011**: Its price MUST come only from the observation dated the run's own `as_of`. A
  declaration stating a price MUST refuse, on the rule `docs/METHODOLOGY.md` §29.6 already applies
  to a fund — one price in two files is one fact in two places — and a date the series does not
  carry MUST refuse by name rather than snap to the nearest one (011 FR-010's rule).
- **FR-012**: Its quantity MUST come only from declared seed lots. Nothing anywhere may infer a
  holding from a price.
- **FR-013**: `btc` MUST be a declared group carried by the instrument as a label. Nothing may
  infer membership from the class, the venue, the tax class or the id (015 FR-007a).
- **FR-014**: The instrument MUST name a tax class that no jurisdiction pack declares. Every tax
  figure for it MUST be the existing typed refusal naming the class and the instrument, and MUST
  reach the reader.
- **FR-015**: That refusal MUST NOT suppress the position's value, its basis or its nominal
  change. A refusal on one figure is not a refusal of the record.
- **FR-016**: No engine code may branch on `btc`, the instrument's id or its symbol. Adding a
  second held asset MUST be a data-only change.

**The provider**

- **FR-017**: `Provider` MUST be a function signature over frozen records — `fetch(kind, symbol,
  as_of)` returning an observation or a typed refusal — and MUST NOT be a class hierarchy or a
  `Protocol` carrying methods (D-E).
- **FR-018**: One implementation MUST read the documented market-data-only host,
  `https://data-api.binance.vision` — "For APIs that only send public market data, please use the
  base endpoint" — with no API key, no signature, no account and no header identifying the owner
  (Principle VII). A `429` or `418` MUST be a refusal that writes nothing, never a retry loop.
- **FR-019**: It MUST use the daily kline endpoint, taking each row's close and open time. The
  single-price ticker MUST NOT be used: it carries no date, and stamping one would put a value in
  the file that the publisher did not state.
- **FR-020**: It MUST write `data/observations/binance_<symbol>.toml` carrying the endpoint, the
  retrieval date, and one dated cited observation per row with an **empty** `verified_on`. It
  MUST NOT fill `verified_on`, ever.
- **FR-021**: It MUST refuse the whole run and write nothing on any shape it does not recognise
  — a row that is not twelve elements, a non-positive price, a gap in the requested window, a
  window ending short of what was asked for, or a body that is not a list — leaving the previous
  file byte-identical. It MUST NOT check the symbol against the body: a klines row carries none,
  and a guard that cannot fire is worse than no guard.
- **FR-022**: Nothing may fetch at run time. The observation file is read as declared data, and
  the core opens no connection.
- **FR-023**: The file MUST record the symbol **as requested**, and MUST NOT split it into a
  base and a quote asset: klines publishes neither, and choosing where `BTCUSDT` divides would be
  the fetcher making a judgement — FR-019's objection to the ticker, in another place. What the
  quote asset is worth in dollars is therefore the owner's declaration, never the fetcher's
  [NEEDS CLARIFICATION: see Clarification 1].
- **FR-024**: Every row MUST be a **closed** day: the script MUST refuse a row dated on or after
  its own retrieval date, because the current day's kline is still open and its close is the last
  trade so far. The newest usable price is the previous day's, and a run whose `as_of` is the
  retrieval day refuses by name under FR-011 rather than reporting an intraday snapshot as a
  daily close. The observation MUST still name a declared staleness kind — a sourced table naming
  none is a load error — and its threshold MUST be recorded as **inert**: staleness is
  `as_of − retrieved_on`, so under this rule and FR-011 a run that produces a price always has a
  negative age, and one that would have a positive age has no row and refuses instead. The kind
  MUST NOT age under `venue_terms`, and `market-quotation-staleness-kind` stays **open**, because
  nothing here can make a threshold fire.

**The basis**

- **FR-025**: A seed lot's cost MUST carry no `currency` key; its currency is the one the
  instrument it names declares. This **narrows** 008 FR-010 — a cost is no longer unconditionally
  in the base currency — and the narrowing MUST be recorded in 008's spec rather than left as a
  contradiction between two live documents.
- **FR-026**: Where that currency is not the base currency, the hryvnia basis MUST be struck at
  the official rate declared for the lot's own acquisition date, through 011's existing
  conversion, reporting the series, the observation date and the arithmetic. It MUST be struck
  **before the cost is tagged with a currency**, at the one place holding both the instrument
  declaration and the rate series.
- **FR-027**: The struck basis MUST carry both marks — the owner's estimate and the official-rate
  observation — and both MUST reach every figure derived from it. A figure showing only one is a
  top-severity defect (008 FR-007, 011 FR-015).
- **FR-028**: With no official rate declared for an acquisition date, the outcome MUST be 011
  FR-010's typed refusal naming the series, the pair and the date. No lot may load with a basis
  struck at a neighbouring date's rate.

**What the answer shows**

- **FR-029**: A subject resolving to a held position MUST reach its own standing, distinguishable
  without reading prose from *undeclared*, *declared but unreached* and *reached* (015 FR-010).
  Reporting it as unreached would name a corridor as the remedy, and the remedy is nothing — he
  already holds it.
- **FR-030**: The answer MUST report, for each held position: the quantity, the observed price
  with its observation date, the value, the hryvnia basis, the nominal change, and — as typed
  refusals or exclusions, never as absences — no tax, no yield and no rank. A held position MUST
  NOT be enumerated as a candidate and MUST NOT be ranked against the benchmark
  [NEEDS CLARIFICATION: see Clarification 2].

## Clarifications the owner must settle

**1. What stands between USDT and USD.** The price this repository can fetch is
`BTCUSDT`; every hryvnia figure downstream needs dollars. Three ways, and no default:

| | What it means | What it costs |
|---|---|---|
| **A** *(recommended)* | A declared belief in `data/scenarios/` that one USDT is one USD, labelled an assumption with the owner's reason | Produces a number. Every BTC figure carries the assumption's mark, so the belief is visible wherever it acted — the shape 015 FR-032 already uses for the quotation belief |
| **B** | Refuse every dollar and hryvnia figure; report the position in USDT only | Honest and useless: the held section states a number he cannot spend and cannot compare to anything |
| **C** | Declare a cited USDT/USD rate as an observation from a source | The most correct, and it needs a source nobody has picked. It is also a second fetch, a second provenance and a second staleness kind |

Recommendation **A**. The peg is what he actually believes, the mark is what makes it a belief
rather than a fact, and B produces an answer that cannot be read against the other three
subjects. C stays open as the widening: swapping a declared belief for a cited observation
changes a data file and nothing else.

**2. Where a held position appears.** It is not a candidate for the 50 000 and cannot be made
one: `Tuple.route_in` is required and there is no zero-hop entry (`zero-hop-way-in`, recorded in
015 for held cash, unchanged here).

| | Shape | What it costs |
|---|---|---|
| **A** *(recommended)* | Its own **held** section, beside the horizon sections, with its own fields | The ranking keeps answering one question — where the 50 000 should go. Held positions are reported in full and never compete with things he could buy |
| **B** | A baseline row inside each horizon's ranking | Needs a purchase price, a funding route and an exit for a purchase that will not happen; every one of them would be invented |
| **C** | Only a subject standing, with no figures | Says he holds it and refuses to say what it is worth, which is the question he asked |

Recommendation **A**. B is the shape that would produce a confident wrong number, which is what
this project exists to remove.

**A third question was asked and withdrawn.** How fast a crypto price goes stale looked like the
owner's line to draw, and it is not a question this design can act on: under FR-011 and FR-024
every run either finds a row with a negative age or finds none and refuses, so no threshold can
fire. FR-024 records the kind as inert and `market-quotation-staleness-kind` stays open. Asking
for a number that changes nothing would have been the more expensive mistake.

## Success Criteria *(mandatory)*

- **SC-001**: The overlay on its own moves nothing: with the shipped data unchanged, declaring a
  private root and reading it leaves every golden byte-identical. Declaring the instrument does
  move the answer golden — `btc` stops being undeclared, which is the feature — and that is the
  only golden this change is permitted to move.
- **SC-002**: With a synthetic held position declared in the test overlay, the answer reports its
  quantity, value, basis and nominal change, and reports its tax as a refusal naming the class.
- **SC-003**: A real (`is_synthetic = false`) seed placed anywhere under `data/` fails the load,
  and a scan of the committed tree finds none.
- **SC-004**: A record declared under both roots fails the load naming both paths.
- **SC-005**: The struck basis reproduces hand-computed arithmetic to the project tolerance —
  `cost × rate ÷ quotation_unit` at the acquisition date — from placeholder figures, not the
  owner's.
- **SC-006**: Every figure derived from a struck estimated basis carries both marks. A walk over
  the result record finds no figure resting on the basis and showing only one.
- **SC-007**: The fetch script, driven by a recorded response fixture, writes an observation file
  whose every `verified_on` is empty; driven by each malformed response, it writes nothing and
  leaves the previous file byte-identical.
- **SC-008**: Adding a second held asset — a second ticker, a second group label, a second seed
  lot — is a data-only change and the full pipeline reports it, with no engine edit (H1's rule).
- **SC-009**: No test reaches the network, and the fetch script's only network call sits behind a
  seam the test replaces.

## Counts that move

- `data/groups.toml` gains `btc`; `data/observation_kinds.toml` gains one inert kind (FR-024);
  `src/terezy/data/citation_policy.py`'s `user` exemption reason changes (FR-007).
- `data/README.md` moves in two rows: `data/user/` stops being what a run produces, and
  `observations/` stops being read by nothing at run time.
- `registry.DECLARATION_KINDS` goes from three members to four. **No gate sees that**:
  `check_enumerations.py` builds its sets from `id =` columns, `Enum` members and `Literal`
  alternatives, and a `frozenset` of `Final` constants is none of those — so prose enumerating
  the kinds goes stale silently and has to be found by reading.
- The answer's subject standings go from four records to five (FR-029), so
  `SubjectCounts`, the OpenAPI document generated from the API's types, and
  `tests/golden/the_answer.golden.txt` all move. `btc` leaves the undeclared population, which
  015 SC-002 pins at two words; that assertion becomes one word, `cash`.
- `docs/REQUIRED_TESTS.md` row **B2** — a provider outage never writes and never reuses
  synthetic data — is reachable for the first time.

## Assumptions

- One owner, one overlay file per declaration kind, matching the shipped roots' shape.
- The daily close is the price of a day. Binance publishes an open, high, low and close; which
  one is *the* price is a choice, and the close is what a return series is built from.
- A held position has no yield and no cash flow. Only the price changes.
- Base currency and tax currency are both hryvnia today, so the struck basis serves both roles.
  They stay distinct concepts (Principle VI); nothing here merges them.

## Out of scope

- **Buying BTC with the 50 000.** It needs the P2P channel rates to be real, and every file in
  `data/channels/` is still an invented corridor (`data/README.md` rule 5); it also needs a spot
  trading fee at Binance, which nothing declares.
- **Selling it.** A disposal needs the tax class this feature refuses.
- **The Ukrainian tax treatment of virtual assets.** An owner verification task below. Not
  researched here and never from memory (Principle I, data rule 4).
- **Other tickers**, and **scheduling fetches** — still the `provider-automation` future: one
  provider run by hand, no cache and no retry policy.
- **A BTC return series, a volatility figure or a Sharpe ratio.** A daily close series makes them
  computable; whether they may be emitted is Principle I's question and a separate feature.

## Owner verification tasks

1. **How Ukraine taxes the disposal of a held virtual asset.** Closed by a primary source — ПКУ,
   a ДПС роз'яснення, or the virtual-assets law — entered as a declared tax class with its
   citation and `effective_from`. The crypto material already here
   (`data/tax/destinations/ua.toml`, the `coinbase` row) is about ФОП income credited to an
   exchange, a different proposition (015, task 2). Until then FR-014 stands.
2. **Whether Binance's terms permit this use of the public endpoint**, and under what attribution
   — the question `scripts/fetch_nbu_rates.py` answers for the NBU's licence in its own header.
3. **The two lots themselves.** Quantities, dates and costs are the owner's to state in
   `data/user/`, and no test may pin them.
