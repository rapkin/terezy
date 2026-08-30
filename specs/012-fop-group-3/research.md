# Research: the ФОП group 3 regime

**Feature**: `012-fop-group-3` | **Date**: 2026-08-30 | **Spec**: [spec.md](./spec.md)

Every decision below is about **shape**, not about law. No legal, tax or fee value was
researched here and none was retrieved: the owner has ended retrieval on this feature, every
value this plan enters is quoted in `spec.md` with its citation, and a value the spec does
not carry is recorded as a gap rather than found.

---

## D1 — The word. "Taxation scheme", never "regime"

**Decision**: the core module is `core/tax/scheme.py`, the record is `TaxationScheme`, the
declaration directory is `data/tax/schemes/`, and the stream field is `tax_scheme`.

**Why**: `core/scenarios/regimes.py` already defines `Regime`, `RegimeTransition` and
`routes_in_force` — a *scenario* regime, meaning *which routes exist on a date*, imported
under that name by `resolver.py` and built by `loader._regimes`. A second `Regime` in the
core would collide at the symbol and, worse, at the reader: two unrelated concepts sharing a
name in one package is how a wrong import typechecks. The spec's own Key Entities entry says
"*regime* and *taxation scheme* are one entity under one name"; this plan picks the name that
is free.

**Alternative rejected**: `core/regimes/` as a new package. It would also sit *outside* both
of 011's currency-role contracts, so the channel prohibition would have to be restated as a
third `.importlinter` contract. Under `core/tax/` it is inherited.

## D2 — The directory: `data/tax/schemes/`, a subdirectory, not a new root

**Decision**: schemes in `data/tax/schemes/*.toml`, crediting destinations in
`data/tax/destinations/*.toml`.

**Why**: three separate reasons converge.

1. FR-017's wording is *"a treatment that **no tax file** declares"* — the spec points at
   `data/tax/`, and `data/tax/timing/` is the precedent for a subdirectory holding a
   different kind of tax declaration. `resolver` globs `data/tax/*.toml` non-recursively, so
   a subdirectory cannot be mistaken for a rate pack.
2. `scripts/check_provenance.py` walks `SOURCED_DIRS` with **`rglob`**, so a subdirectory of
   `tax` is scanned with no script change and cannot become a blind spot. A new root
   directory would need an entry in `SOURCED_DIRS` *and* a row in `data/README.md`, and the
   fail-closed `unknown_directories` check makes forgetting either a hard error — cheap to
   satisfy, but two more places holding one fact.
3. The gate then requires exactly what FR-003 requires anyway: every table with a numeric
   leaf carries `kind`, `source`, `retrieved_on` and a present `verified_on`.

## D3 — The observation kind is `tax_rule`, and nothing is added to `observation_kinds.toml`

**Decision**: every citation this feature enters is stamped `kind = "tax_rule"` (180 days).

**Why**: it is what these values are — a rate, a commencement, an administrative position on
where income is recognised. Adding a kind would change `observation_kinds.toml`'s input
digest and move two golden files for a reason that has nothing to do with either run;
011 measured exactly that (`2ff2b9db → 4674f6e9`). A golden is evidence and moving one
deliberately is correct — but moving one for no gain is not evidence of anything.

⚙ The ЄСВ nil's citation is the **owner's own statement** and it ages under `tax_rule` like
every other. That is the right answer rather than a compromise: a person's statement of his
own tax position is exactly the kind of claim that goes stale, and owner verification task 2
is what replaces it.

## D4 — A new charge record, beside `TaxCharge` rather than instead of it

**Decision**: `SchemeCharge` carries a tuple of named `ComponentCharge` lines. It is a new
record in `core/tax/scheme.py`; `core.tax.interface.TaxCharge` is untouched.

**Why**: FR-006 forbids putting a єдиний податок into a field named personal income tax, and
`TaxCharge` has exactly two fixed lines, `pit` and `levy`. The two candidate shapes:

- **Generalise `TaxCharge` to named components.** It reaches `flat_rate`, `tax.year`'s whole
  netting and carryforward fold, `AssessedLiability.pit`/`.levy`, `results.tax_year`,
  `results.hurdle.total_tax`, `results.canonical` and both golden files — for a feature that
  needs none of it. Principle "complexity must be justified" runs the other way here.
- **A second record.** Two charge shapes exist afterwards, and that is the cost.

The cost is paid because they are **two different facts**, not one fact in two places:
`TaxCharge` is what a *tax class* charges on an *instrument's* income under a rule from
`REGISTRY`; `SchemeCharge` is what a *scheme* charges on a *stream's* income. They share no
input, no rate schedule and no consumer. `/condense`'s rule is one fact one place, and a
merger here would be one *name* over two facts.

⚙ What would force the merge: an income stream that has to appear in `tax.year.statements`
alongside instrument charges, netted into one annual liability. FR-004 puts that out of scope
(feature 009 and required test E7 own payment and assembly), so the seam is recorded rather
than built.

## D5 — Where the base is struck, and the date it is struck on

**Decision**: `core.tax.official_rate.strike_base` is called directly from
`core/tax/scheme.py`, on a **credit date supplied by the caller**, and this feature adds no
conversion of its own (FR-011).

**Why**: `year._in_tax_currency` — 011's only call site — hard-wires `on_date=occurred_on`,
the ledger event's date. A scheme charge has no ledger event: nothing in this system turns an
`IncomeStream` into an `Event`, `project()` never sees a stream, and the credit date is the
stream's own fact. So the strike is a second call site with its own date, not a reuse of the
first.

Three properties of `strike_base` this feature relies on and must not weaken:

- an amount **already in the tax currency raises** rather than returning unchanged, so the
  caller checks the currency first (011 FR-009). `charge_income` does that check, and the
  Edge Case *"a stream in the tax currency naming this regime"* is that branch.
- a date with no declared rate returns `OfficialRateUndeclaredOnDate` naming the series, the
  pair and the date. This feature **wraps and reports it**; it does not add a reason of its
  own, because the refusal already names its own fix. That is US1 acceptance scenario 3.
- nothing interpolates, carries forward or snaps to the nearest.

## D6 — Two lookup shapes, and the periodic component is not one of them

**Decision**: a **rate component** carries a dated schedule of rates read by a fold identical
in shape to `schedule.rate_on`; a **periodic component** carries a dated schedule of
**amounts** and is charged once per elapsed period, by a different function taking a period
rather than a base.

**Why**: FR-019's two differences are the trigger and the base, and they are independent. A
rate component asked about a date before its earliest entry refuses
(`ComponentRateUndeclaredBefore`, 006 FR-012's shape). A periodic component asked about a
period with no amount in force refuses (`PeriodicAmountNotInForce`, FR-021) — never a zero.

**Why not reuse `schedule.RateEntry` and `schedule.rate_on`**: `RateEntry` carries `pit_rate`
*and* `levy_rate` — two fixed lines again, and a component has exactly one rate. Reusing it
would mean writing a component's single rate into a field named for personal income tax,
which is FR-006's defect one layer down.

**The period vocabulary**: `core/primitives/periods.py` has months only (`"YYYY-MM"`,
`ordinal`, `next_month`, `months_in`, `Window`). A periodic component therefore declares its
period as `"month"` and is charged over a `Window` of months. Quarters exist in this
repository only as a coupon periodicity and are not reached here; FR-004's **quarterly
reporting cadence is declared and unused**, exactly as the requirement says.

## D7 — Three states for a nil, and the record that makes them three

**Decision**: `component_standing(scheme, component_id, *, on_date, period)` returns a tagged
union — the entry in force where there is one, and a refusal naming its own state where there
is not:

| Return | Means | SC-011's third |
|---|---|---|
| `ComponentNotDeclared` | this scheme charges no such component | *not charged by this scheme* |
| a charge line whose amount is zero, carrying its provenance | it was charged and came to nothing | *charged, came to nothing* |
| `ComponentRateUndeclaredBefore` / `PeriodicAmountNotInForce` | declared, nothing in force | *no amount is declared* |

**Why a function and not three fields**: FR-020 requires the three to be distinguishable *in
the output*, and the question is asked *about a component id*. A record cannot hold an answer
for a component nobody named. `component_standing` is also the only place the first state can
be produced, which keeps it from being spelled as `None` anywhere.

## D8 — The verdict is declared data; the wrapper is a branch on a closed set

**Decision**: a crediting destination declares `verdict = "interpreted" | "unsettled"`,
resolved through `loader._closed_value` against a `Verdict` enum in the core. The engine
branches on the **verdict**, never on the destination, the scheme or a component name.

**Why this is not the branch Principle II forbids**: 009 already does exactly this —
`MethodVerdict` is a closed enum resolved from `data/tax/timing/ua.toml`, and
`SOURCE_BACKED` membership is its whole mechanical meaning. The prohibition is on the engine
knowing that *ФОП group 3* or *військовий збір* exists, and it is asserted over executable
source by the no-branch test. A verdict is a declared property of a row, and moving a row
from `interpreted` to `unsettled` is one word in one file.

**`SETTLED` is not in the enum.** 009's vocabulary has three levels and this feature reaches
two. A `SETTLED` member nothing constructs is a member that has never been executed, and the
day a destination becomes settled it wants the same wrapper `INTERPRETED` has — a charge —
so the enum would gain a value that changes nothing. The level stays in the spec's prose,
where it is a statement about sources, and out of the code, where it would be a statement
about behaviour.

## D9 — What a switch holds, and what makes a blend unrepresentable

**Decision**: the shape is 007's `RealTerms`, not 009's `UnsettledPositions`.

009's switch is **one figure per run** — one declared position per question, and a second
declaration is a load error. FR-026 wants **N figures in one run**. So:

```
UnsettledDestination        figures: tuple[ReadingFigure, ...]        <- no aggregate field
                            uncomputable: tuple[UncomputableCandidate, ...]
                            grounds, resolution_path
ReadingFigure               reading_id, label, scheme_id, recognised_on, charge,
                            departs_from_source, not_the_tax_owed, provenance
ChargedUnderTheScheme       charge, grounds, the INTERPRETED result
```

Four mechanical guarantees, each asserted rather than written down:

1. **No blend has anywhere to live.** `UnsettledDestination` has no `total`, no `mean`, no
   `Money` field at all — asserted by enumerating `dataclasses.fields`, 007's
   `test_the_slot_has_exactly_two_figures_and_no_third_field` applied to a variable-length
   tuple.
2. **The label is on the figure, not on the slot.** A figure lifted out of the tuple still
   names its reading and carries its citations — 007's
   `test_the_basis_travels_with_a_figure_lifted_out_of_the_slot`.
3. **The tax owed is a different type.** `ChargedUnderTheScheme` and `ReadingFigure` are
   unrelated frozen records, so assigning one into the other's slot is a mypy strict error —
   the `OneWayCost`/`RoundTripCost` trade (002 research D4).
4. **Containment.** An AST scan pins the set of modules that may construct a `ReadingFigure`
   and the number of sites that build one, with `dataclasses.replace` counted as a
   construction — 007's `_construction_sites` / `_modules_mentioning`.

## D10 — A reading names a **declared date**, and the caller supplies the dates

**Decision**: a reading declares `recognised_on = "<declared date name>"`. The charge call
takes `on_dates: Mapping[str, date]`. A reading naming a date the caller did not supply is a
typed refusal naming the reading and the date name — never a fallback to another date.

**Why**: FR-026a's НБУ reading is *"the same scheme and the same components, on a **different
date**"*. Without this, that reading is uncomputable and the switch silently holds two figures
where the spec counts three — the exact defect FR-026's third-reading clause exists to
prevent, and the one the spec records as having happened once already.

The engine knows no date name. `"credited"` and `"repatriated"` are strings in a data file
and strings in a caller's mapping; nothing in `core/` compares against either, which the
no-branch scan asserts.

## D11 — An uncomputable candidate is declared as uncomputable, not as a dangling reference

**Decision**: a reading declares **exactly one** of `scheme = "<id>"` or
`uncomputable_because = "<reason>"`, checked at load.

**Why**: Line 3's second sentence needs a candidate that is named and not computed. The
obvious encoding — a reading naming a scheme nobody declared — collides with the standing
rule that an unresolvable reference fails at load (FR-017 for streams, `_check_references`
everywhere else), and weakening that rule to make this one case work would weaken it for the
case it exists for. Declaring the reason instead keeps both: every named scheme resolves, and
an uncomputable candidate says *why* in its own words rather than by being broken.

⚙ The spec records that **no shipped row exercises this** — every reading now computed is a
declared scheme. It is exercised by a synthetic destination (SC-013's third-state case and
SC-017's *named on the switch* clause), which is the only honest way to test a clause the
shipped data does not reach.

## D12 — A crediting destination is a **venue id**, and an unknown one refuses at charge time

**Decision**: `IncomeStream.credited_to` names a venue, checked against `venues.toml` at load
exactly as `arrives_at` is. The destination table maps `(scheme id, venue id) → destination`.
A venue with no row is FR-027's refusal, produced when the charge is attempted.

**Why a venue**: it is the vocabulary the model already has for *where money can sit*, the
spec points at it twice (`monobank_uah` at FR-026b, `data/routes/deel_to_coinbase.toml` and
`data/venues.toml` at FR-027), and SC-013a's case — Deel and the ФОП account — is two venue
ids that differ.

**Why the row is not resolved at load**: if `credited_to` had to name a declared destination,
FR-027 would be unreachable — a stream naming an unrecorded destination would fail to load
and could never produce the refusal that names the destination and the scheme. The reference
that must resolve is to the *venue*; the *judgement* about that venue is looked up when the
charge is struck, and its absence is the feature.

## D13 — Two venues are added, and what that costs

**Decision**: `data/venues.toml` gains `payoneer` (an international payment system, USD) and
`foreign_bank_usd` (a bank account outside Ukraine, USD). No route is declared to or from
either.

**Why**: SC-017 pins per-destination figure counts against the **shipped** normative table —
three for a payment system, two for a foreign bank account. Without venues for those two rows
the table ships incomplete and two of its five rows are testable only in a scratch root,
which would make the normative table a fixture.

**What it costs, stated before it is measured**: `coverage.py` audits every
`(venue × currency)` pair, so two unreachable venues may move the coverage golden's
blocked-pair count. Constitution Principle V: a golden is evidence, never a freeze. If it
moves it is regenerated deliberately with the changed lines quoted in the commit message, and
the fact that two declared destinations have no declared route out of them is a **true**
thing for the audit to report.

## D14 — `deployable` reports in the tax currency, and the conversion travels with it

**Decision**: after the migration, the gross, what was charged and the net are **all in the
tax currency**. `DeployableCapacity` carries the `SchemeCharge` and the `net`, and nothing
else: the gross is `charge.base`, what was charged is `charge.total`, and the arrival that
produced them is `charge.conversion.amount` — `None` for a stream already in the tax
currency. Three numbers, no field holding a copy of any of them.

**Why**: `gross − charged = net` (US2 scenario 1) cannot hold across two currencies —
`money.sub` raises `CurrencyMismatchError`, which is the same wall 011 hit in
`results.project`. The three candidates:

- **net in the stream's currency**, converting the hryvnia charge back at the official rate.
  Forbidden: that is an official rate pricing a realised amount, 011 FR-012 exactly.
- **net in the stream's currency**, converting through the sale channel. Forbidden the other
  way: FR-012 of *this* feature keeps the channel out of the base, and putting the charge
  through the channel would make the deployable figure depend on a market rate on a date the
  sale may not have happened on.
- **everything in the tax currency, with the conversion on the record.** The identity holds
  exactly, the foreign arrival is visible as `conversion.amount` rather than duplicated in a
  second field, and the number that is *not* claimed — how many dollars are left — is not
  claimed at all.

⚙ `deployable` has **one caller in the whole repository and it is its own unit test**. Every
other reference to `IncomeStream` in `core/routes/` is to `arrives_at` or `amount`. So the
migration's blast radius is the record, its test, the loader and the declaration file — which
is why FR-016's *"the same claim, the same shape, the same reason"* is a real risk rather
than a formality: nothing else would notice if it changed.

## D15 — Base against received: two Money values in, no route machinery imported

**Decision**: `base_versus_received(base, received)` takes two `Money` and returns
`BaseVersusReceived(base, received, difference, outside_the_base)`. It imports nothing from
`core.routes`.

**Why**: FR-023 says the sale is an ordinary declared leg through an ordinary declared
channel and this feature adds no mechanism. Taking a `OneWayCost` as an argument would make
`core.tax` import `core.results.ramp` for a subtraction, and would tempt the next reader into
computing the received figure here. The caller passes `cost.one_way.arrived`; the existing
costing path produces it and this feature does not touch it.

`difference = base − received`, **signed and not absolute**: FR-013's note says the exposure
points either way, and an absolute value would hide which.

## D16 — The three states of FR-027, and the one the engine cannot tell apart

**Finding, carried into the plan rather than worked around.**

FR-027 names three states. The engine can produce two of them:

- **state 3** — a row exists and every candidate is uncomputable. Mechanical: the row is in
  hand and its readings all declare `uncomputable_because`.
- **state 1 / state 2** — *no source reaches the destination* and *a source reaches it but no
  row records the judgement* are **the same observation to the engine**: the table has no row.
  Which one it is depends on whether a source exists in the world, which is not in the data
  and, as SC-013's own ⚙ says, is a reviewer's determination.

The refusal therefore reports state 1 **with a reason that does not overclaim**: it says the
declared table has no row for this destination, names both closures — find a source, and add
the row with its reasoning — and says in as many words that where a source already exists and
the table has not caught it, that is state 2 and a reader reclassifies it. SC-013 measures
states 1 and 3, which is what it asks for.

What is *not* done: inventing a data field that declares *a source exists for a destination
the table does not name*, so that state 2 becomes emittable. That would be a declaration
whose only purpose is to make a criterion testable, and it would be a claim about the world
that nothing checks.

## D17 — `IncomeStream.credited_to` is required, on every stream

**Decision**: required, not optional.

**Why**: FR-024a — *"a declaration supplying only one MUST fail at load naming the stream and
the missing field"*. `arrives_at` is already required, so the reverse half of that sentence is
already true, and making `credited_to` required makes the other half true by the same
mechanism. An optional field would have to be checked against `tax_scheme`'s presence, which
puts the rule in two places and makes *the owner forgot* and *the owner declared nothing* look
alike — the distinction `income_tax_rate`'s own docstring spends four paragraphs defending.

The salary stream declares `credited_to = "monobank_uah"` and names no scheme, so nothing
reads its destination. That is not a latent FR-026b switch: the destination is read only where
a scheme is named.

## D18 — The variant is one scheme per file, and the owner names the scheme

**Decision**: `TaxationScheme.variant` is a curated field naming which of the law's
alternative rate sets a file declares. The owner declares which variant he is in by naming
*that scheme* on his stream, in per-owner data. There is no separate `variant` field on a
stream.

**Why, given that FR-002 says the variant "is declared as per-owner data"**: it is — the
`tax_scheme` he names *is* the variant, and the requirement's own second half is satisfied
exactly ("the rates of every variant are public legal facts and live in curated tax data with
citations", one file per variant, each cited). The alternative reading puts a `variant` string
on the stream beside the scheme id, and the two can then disagree: a stream naming the non-VAT
scheme and `variant = "vat_payer"` typechecks and is nonsense. That is the same trade
`IncomeStream` already made when a separate `currency` field was removed in favour of
`amount.currency`.

⚙ **The requirement pulls both ways in two sentences and this records which one was followed.**
FR-002's opening — *"The declaration MUST name which variant of the regime applies"* — and the
sentence in *The verified legal facts* — *"The regime declaration names which variant applies
(FR-002)"* — both put the field on the regime, which is where it is. The clause about per-owner
data is satisfied by the reference rather than by a second copy of the answer.

## D19 — A gap FR-026 and FR-010a do not close, closed here

**Finding, not a design choice.** FR-010a says the personal-income rates "MUST NOT be declared
as a treatment any stream can name", and the loader enforces exactly that. Nothing in the
specification says the same rates may not be reached **through a verdict**: an INTERPRETED row
whose one reading names that scheme produces `ChargedUnderTheScheme` — the tax owed, carrying
no *not the tax owed* label anywhere — and moving a verdict is the operation this feature
advertises as cheap.

Closed by refusing such a row at the **resolver**, not the loader: `declared_for` is another
file's fact, so a per-file validator structurally cannot see it. Found by review, and worth
recording because the prohibition read as enforced while being open at the other door.
