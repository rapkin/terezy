# Research: an instrument declared as the payments it will make

**Feature**: `013-enumerated-schedule` | **Date**: 2026-08-29

Ten decisions. Every one of them was reached by reading the code the specification claims
things about; where the reading contradicted the specification, that is recorded as a
finding rather than smoothed over.

---

## D1 — The two forms are two `terms` records under one declaration

**Decision.** `InstrumentDeclaration.terms` becomes `BondTerms | EnumeratedTerms`, and
`[instrument] class` — already the only permitted dispatch key — selects which loader
parses the file and which `InstrumentOps` projects it. `enumerated_schedule` joins
`fixed_income` in `registry.REGISTRY`.

**Rationale.** FR-002 asks for *exactly one declared field* to determine the form and for
the **type checker** to enumerate the sites that must change. A union on `terms` does both:
`declaration.terms.issue_date` stops type-checking the moment the union exists, and mypy
--strict then lists every site. `class` is already the field, already validated against the
registry, already forbidden from being anything else (`registry.py`'s own docstring:
branching on `id` would be the Principle II violation).

**Alternatives rejected.**

- *A second top-level declaration record* (`EnumeratedDeclaration`, as a fund has
  `FundDeclaration`). A fund is a different record because its **projection returns
  something else** — that is mismatch 3 in `registry.py`'s section comment. An enumerated
  bond returns one event stream, takes the same four arguments, and fails with the same
  union. Splitting the record would put `id`, `name`, `currency`, `is_synthetic`,
  `constraints` and `tax_classes` in two places and force every consumer
  (`data.manifest.input_refs`, the resolver's id space, the access registry, the tuple join)
  to handle two shapes for one concept.
- *Optional generative fields* (`issue_date: date | None`). FR-003 forbids exactly this:
  an accepted-and-ignored field is worse than a missing one, and `None` invites
  `if terms.issue_date is None` — the form test SC-003's scan is documented as unable to
  catch.

## D2 — Four questions, asked of the terms, answered by each form

**Decision.** A new module `core/instruments/terms.py` holds four free functions over
`BondTerms | EnumeratedTerms` and is the **only** `match` on the form in `src/`:

| Question | Function | Generative answers | Enumerated answers |
|---|---|---|---|
| From what date are this instrument's terms known? | `known_from` | its issue date | its coverage start |
| What convention annualises a span? | `day_count_of` | `terms.day_count` | `terms.day_count` |
| What conventions shaped this schedule, and what should a row say? | `conventions_of` | `ConventionsApplied(periodicity, day_count, business_day_rule)` | `AmountsAsDeclared(day_count)` |
| What does a figure derived from this instrument additionally exclude? | `excludes_of` | nothing | the dirty-price clause |

**Rationale.** FR-011a's own observation: `seeds.py` never needed an issue date, it needed
the earliest date the terms are known from, and it asked for the only spelling that existed.
Four questions both forms answer means the three call sites keep one question each and gain
an answer rather than a case — which is what keeps SC-003's scan passing, because none of
them ever names the form.

`known_from` returns a small record rather than a bare `date`, because the refusal it feeds
(`seeds.py`) names *two declared facts that cannot both hold* and has to name the second one:
`instrument.terms.issue_date` for one form and `instrument.schedule.covers_from` for the
other. A bare date would leave `seeds.py` to name it, which is a form test written in
strings.

**Alternative rejected.** *Each call site matches the union itself.* Three matches instead
of one, in exactly the three modules FR-012 forbids from testing the form.

## D3 — The conventions statement is a tagged union, and it moves to `primitives`

**Decision.** `ConventionsApplied` moves from `core/results/schedule.py` to
`core/primitives/conventions.py`, gains a sibling `AmountsAsDeclared`, and
`CashFlowRow.conventions` is typed on the union.

**Rationale.** Two constraints meet here. FR-011b requires the **declaration** to answer
what a row should say, so the answer type must be importable by `core/instruments/`.
FR-016 requires a row's statement to live with the row. If the type stays in
`core/results/schedule.py`, then `core/instruments/terms.py` imports upward from a *result*
module into an *instrument* module — no import-linter contract forbids it and every reviewer
would ask why. `core/primitives/conventions.py` already owns the three convention
vocabularies these records name; both layers import downward into it, which is the direction
everything else in the project runs.

FR-016 names `core/results/schedule.py:58-60`'s docstring as one that goes false. It travels
with the record and is corrected at its new home; the claim it made — *"and therefore fixed
each coupon's size"* — is the claim `AmountsAsDeclared` exists to deny.

**Alternative rejected.** *One record with `periodicity: str | None`.* Collapsing a tagged
union into a nullable field is the simplification `CLAUDE.md` names as moving complexity into
the reader's head, and `if row.conventions.periodicity is None` is precisely the form test
SC-003 records its scan as unable to catch.

## D4 — The canonical encoding distinguishes the two by arity, and the generative arm is untagged

**Decision.** `results.canonical.of_conventions` returns `(periodicity, day_count,
business_day_rule)` for `ConventionsApplied` — byte-for-byte what it returns today — and
`("declared", day_count)` for `AmountsAsDeclared`.

**Rationale.** FR-016 and SC-010 require the golden encoding to distinguish the two. A
2-tuple can never equal a 3-tuple, so they are distinguished by shape as well as by the tag.
Leaving the generative arm untagged is what makes SC-017 literally true for the schedule
half of every existing golden: no generative row's canonical bytes move.

⚙ This is the one place a *results* module matches on the union, and it is not the form test
FR-012 forbids. It renders a value it was handed; it does not ask a declaration what it is in
order to decide what to compute. FR-016's requirement that the encoding distinguish the two
statements could not be met by any implementation that refused to look at which statement it
had.

## D5 — A payment kind determines a ledger movement and a taxable kind, in one closed mapping

**Decision.** `PaymentKind` is an `Enum` in `core/instruments/interface.py` with two
members today — `COUPON` and `PRINCIPAL_REPAYMENT` — and a single module-level mapping
`PAYMENT_KINDS: Mapping[PaymentKind, tuple[EventKind, TaxableEventKind]]`.

**Rationale.** FR-007 asks for one declared label to settle both vocabularies. One mapping
rather than two keeps them from disagreeing; the loader reads the taxable half to enforce
FR-009 (an income kind with no declared class fails at load) and the instrument reads the
event half. The set is closed and small, so a third kind — an amortising bond's fee, a
step-up's makewhole — is one entry and one row in the mapping.

## D6 — A repayment retires its share of the repayments declared

**Decision.** A `principal_repayment` event surrenders `quantity_held × (amount_per_unit /
everything the repayments return per unit)`.

**Rationale.** The Edge Cases make several principal repayments valid — an amortising
schedule is representable — and each is a **disposal** in the ledger, consuming basis and
realising a gain. This rule makes the stream as a whole retire the holding as a whole,
once, whatever the shape: one repayment retires everything, which is exactly what the
generative form's redemption does and what SC-002 needs; two equal ones retire half each.

**Alternatives rejected.**

- *Its share of the **face value***. This was the first decision and it was wrong, caught
  by SC-005's relabelling: a schedule returning 1 050.00 against a declared face of 1 000.00
  — a bond redeemed above par, which exists — would retire 1.05 units of every 1 held, and
  `lots.consume` raises on an over-disposal (`lots.py:493`). It needed a typed refusal to
  hold it back, and the refusal was covering for arithmetic run past the thing it was
  describing. Face value is what a redemption is compared **with** (FR-025), never what it
  is divided by; on the share-of-repayments rule the refusal is unnecessary and is gone.
- *Surrender everything on the last principal repayment.* "The last one" is a reading of
  position in the list, which is the shape FR-008 forbids for kinds and SC-014 scans for.

## D7 — Reinvestment refuses, and it refuses in the instrument

**Decision.** `enumerated.events` returns `InconsistentTerms` when
`assumptions.coupon_policy` is `reinvest`, naming the missing fact — the price at which a
coupon buys further units. An unrecognised policy name still raises, through
`fixed_income.coupon_policy`, so the closed set is stated once.

**Rationale.** FR-015. The face value is not substituted, and the reason says why in the
output's own words: for a generative bond face is the price at which a unit earns the
issue's declared rate, and an enumerated instrument declares no rate, so face is a
redemption amount and nothing else. `InconsistentTerms` rather than a new member keeps
FR-013's promise that the failure union is unchanged — two declared facts (this policy, this
declaration) that cannot both hold is exactly what the record means.

## D8 — What is inferred is declared, and the gate checks the declaration

**Decision.** Four inference ids — `face_value`, `payment_kind`, `minor_unit_conversion`,
`coverage` — each requiring, in the file:

- the source of the table carrying the value to begin with `INFERENCE:`,
- an empty `verified_on`,
- a `[[instrument.verification_task]]` entry whose `settles` names the id.

`scripts/check_provenance.py` gains a check that runs on any file whose `[instrument] class`
is `enumerated_schedule` and reports file and field.

**Rationale.** FR-020 and FR-022. A prefix is the mechanical form of *"a source that says it
is an inference"*: a sentence in prose cannot be checked, and a check cannot go stale
silently. No new kind of mark is introduced — an inference is an unverified value and
Principle I's propagation already carries it.

**Note on `kind`.** A payment table cannot spell its coupon-or-principal label `kind`: the
provenance gate reads `kind` as the *observation* kind a table ages under, and a payment that
declared `kind = "coupon"` would be reported as naming an undeclared observation kind — a
true statement about the wrong field. This is the same trap `LEG_KIND_KEY` exists for. The
payment's label is therefore `pays`.

## D9 — The premium is a figure on the projection, and it moves two goldens

**Decision.** `Projection` gains `at_purchase: PurchasePremium` — always present, carrying a
possibly-zero difference, the cost, `face × quantity`, and the treatment of the category the
disposal class belongs to. It is appended to `results.canonical.of_projection`, so the
recorded digests of the existing goldens move by one entry.

**Rationale.** FR-025 conditions the figure on the *amounts* (*"where the purchase cost
differs from face value times quantity"*), not on the form, so a generative projection
carries it too. A zero premium naming its treatment is the same shape as a zero tax charge
citing its exemption, which this repository already chose deliberately (`project.py`:
*"Skipping either would leave the ledger unable to distinguish 'the rule applied and the
answer was nothing' from 'no rule ran here'"*). An **absent** figure meaning "bought at par"
is the silent default the constitution puts at top severity.

⚙ **This contradicts SC-017 in the letter and is reported as a finding.** SC-017 says
feature 001's and 010's goldens are unchanged *"since no generative declaration's behaviour
changes"* — and its reasoning stands: no generative amount, date, tax or rate moves. What
moves is the digest, because a projection now says one more true thing about every holding.
Constitution 1.2.0, Principle V: *a golden file is evidence, never a freeze*, and its input
digests are witnesses rather than terms. The alternative — omitting the premium from the
canonical form to protect a digest — is the exact inversion that principle was amended to
forbid. The goldens are regenerated deliberately and the changed lines are quoted in the
commit.

## D10 — Two synthetic tax classes and a synthetic timing file reach the netting case

**Decision.** FR-010's fixture instrument declares `coupon = "synthetic_enumerated_coupon"`
and `disposal_gain = "synthetic_enumerated_disposal"`, both new entries in
`data/tax/synthetic_fixture.toml` with different invented rates; a new
`data/tax/timing/synthetic_fixture.toml` declares the two categories they belong to, one of
them `treatment = "nets"`, `carryforward = "unlimited"`.

**Rationale.** FR-010 needs two income kinds at **different** rates, FR-026 needs the
disposal class in a **netting** category, and neither may be reached by inventing a
Ukrainian legal value. The existing `synthetic_fixture` jurisdiction is already the place the
repository puts invented rates that must never be mistaken for law, and its rates are chosen
to be unmistakable for that reason.

The existing `synthetic_fund_payout` and `synthetic_fund_disposal` classes are **left
unmapped**, exactly as they are today, so no fund fixture's assessment changes and SC-017
holds for feature 006's and 010's fund results. `resolver._check_timing_classes` runs in one
direction only — every class a timing file *maps* must exist in some rate pack — so leaving
them unmapped is a supported state rather than an omission.

⚙ One existing assertion changes with this file: `tests/contract/test_tax_declaration_loading.py`
pins `sorted(rules) == ["ua"]`, which is a statement about what `data/tax/timing/` contains
rather than about any behaviour. It becomes `["synthetic_fixture", "ua"]`.
