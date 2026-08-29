# Phase 0 research: the official rate and the tax-currency role

**Feature**: `011-official-rate` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)

Twelve decisions. Every one was taken against the repository as it stands on `a93520d`;
where a decision departs from a precedent the departure is named with the precedent.

---

## D1 — The official rate is a separate thing from an FX channel, enforced by imports

Settled by the spec's clarification 1 and by the constitution's three-roles clause. What
this phase adds is the *mechanism*: the prohibition is bidirectional and the two directions
are **two different requirements**, so they are two different contracts.

- **FR-012** — the amount received is never computed from an official rate:
  `terezy.core.routes` may not import `terezy.core.tax.official_rate`.
- **FR-013** — a channel's `reference_rate` is never a tax rate:
  `terezy.core.tax.official_rate` may not import `terezy.core.routes.channels`.

Two `[importlinter:contract:*]` entries, not one covering "both": a single contract naming
both source modules would go green if either direction were removed, and the requirement
that survived would look enforced. `tests/contract/test_architecture_boundaries.py` already
pins the contract names present in `.importlinter`, so deleting one is a test failure rather
than a silent loosening.

## D2 — The conversion is struck in `core.tax.year._items`, not where the charge is computed

Story 1 reads *"when the charge is computed, the taxable base is the event's amount
converted"*, which suggests striking the base upstream, in `core.results.project` where
`TaxContext(taxable_base=...)` is built. **That site cannot take it**, and the reason is
worth recording because it is required test F1's remaining blocker stated precisely:

`core.results.project.project` computes `base_currency = declaration.currency` and then
`money.total([charge.total for charge in charges], base_currency)`, and interleaves the tax
events into the same ledger it folds under that currency. A hryvnia charge inside a dollar
projection raises `CurrencyMismatchError` at the first sum. So a foreign-currency instrument
is not projectable today for reasons that have nothing to do with the official rate, and
`decision.tuple_outcome._foreign_tax_currency` refuses one before any of this is reached.

`core.tax.year._items` is the one site where a taxable result in a currency the tax is not
assessed in is **already reachable** (`tests/contract/test_tax_declaration_loading.py`
reaches it today) and already refuses for want of an official rate. Replacing that refusal
with the conversion is what makes FR-017's refusal live rather than notional.

**Consequence, recorded rather than hidden**: 011 does not open the tuple path to a
foreign-currency instrument, and the tuple-level refusal stays. Its prose must stop saying
the official rate is what is missing, because after this feature that is false.

## D3 — A disposal's realised gain is **not** converted, and refuses

FR-007's subject is *"that event's own amount"*. A realised gain is not an amount on a date;
it is a difference between proceeds on one date and a basis struck on another.

Striking it at the disposal date's rate is not merely imprecise, it is the exact defect
required test F1 exists to catch: a position flat in dollars across a devaluation realises
`0 USD`, and `0 USD` at any rate is `0 UAH`. The taxable gain F1 demands would be deleted by
the conversion that was supposed to produce it.

So `_items` refuses for `from_disposal=True` with a foreign result, naming what is missing —
a per-lot basis struck at its own date's rate, which is the `fx-tax-asymmetry-f1` future
entry. This **sharpens** F1's remaining blocker rather than closing it: the entry's note says
"a taxable foreign instrument + dated official rates", and after 011 the second is supplied
and the first is understood to include a two-currency basis, not merely a declaration.

## D4 — The whole charge is restated, not only the netting result

`core.tax.year._category_statements` sums `item.charge.pit` and `item.charge.levy` in
`items[0].result.currency`. Converting `result` and leaving `charge` alone raises a currency
mismatch on the first per-event category. So the conversion produces a new `TaxCharge` with
`pit`, `levy` and `taxable_base` converted.

`total` is **recomputed** as `money.add(pit, levy)` rather than converted, so the record's
own identity `total == pit + levy` stays exact rather than holding to a tolerance. Feature
001's `TaxCharge` type is unchanged — the spec's Key Entities require it — and only new
instances of it are built.

## D5 — An observation carries no `kind` field; the kind rides on its citation

`CpiObservation` carries `kind` *and* the loader stamps the same kind on the `SourceRef`.
Feature 010 found why that shape is a trap: a staleness threshold held on a *record* does not
survive a merge of provenance, and by the time a figure rests on five tables the record that
knew each kind is gone. `SourceRef.kind` was added for exactly that, and
`staleness.staleness_of_sources` ages a merged provenance under each citation's own kind.

So `OfficialRateObservation` has **no `kind` field**. The declaration file still declares
`kind` per observation — `scripts/check_provenance.py` requires it and the loader stamps it
onto the citation — and ageing a derived tax figure goes through `staleness_of_sources`,
which is the only call that works after the merge. One fact, one place, and the place is the
one that survives.

## D6 — The Ukrainian series ships with **no observations**

FR-001: no official-rate value may originate from an implementer's or an agent's memory. The
spec's Assumptions: *"No real rate values enter with this spec … Real observations arrive
later as a data file carrying its own provenance from the published source."* Retrieval is
`provider-automation`'s, out of scope here.

So `data/official_rates/ua_nbu_usd.toml` declares the identity — authority, pair, quotation
unit — and no observations and no non-publication rule. Unlike `loader.cpi_from_file`, which
refuses an empty series, an empty official-rate series **loads**: it is the declared shape the
fetch script will write into, and every date asked of it refuses by name meanwhile.

**What this costs, stated plainly.** FR-017 says "every date the National Bank does not
publish for refuses". With no observations shipped, *every* date refuses — a stronger
statement than FR-017's, and a weaker demonstration of it. SC-014's test asserts what
actually ships and says so in its own docstring rather than implying the series has a
published window with holes in it.

## D7 — Two "unavailable" records, and one that is not about the rate

The fixes differ, which is this repository's rule for whether two failures are two records:

| Record | What it says | The fix |
|---|---|---|
| `OfficialRateSeriesUnavailable` | no series serves this pair — none declared, or the declared one quotes something else | declare a series, or name one that quotes the pair |
| `OfficialRateUndeclaredOnDate` | the series has no observation for this date and no rule covering it | declare the observation, or declare a cited rule |
| `ForeignGainNotStruckPerDate` (in `tax.year`) | D3's disposal case | build `fx-tax-asymmetry-f1` |

"The series does not quote this pair" folds into the first rather than becoming a fourth,
because its fix is the same sentence.

## D8 — The non-publication-day rule is an explicitly enumerated per-date mapping

FR-011 defines a rule as *a statement of which declared observation governs a date the
publisher does not publish for*, and forbids the engine any notion of a weekend. An
enumerated mapping — `applies_to` / `governed_by`, one row per date — is such a statement and
needs no calendar. It is what SC-015 exercises and what FR-018 explicitly does not rule out.

Two load-time checks make the lookup total, so the runtime has no half-answers:

- every `governed_by` date **must** be a declared observation of the same series;
- every `applies_to` date **must not** be, because a rule that redirects a date the series
  actually publishes for contradicts the publication.

Nothing here derives the mapping from working days, and nothing may. Ukraine declares no
rule at all (FR-017).

## D9 — `official_rate` is its own staleness kind, at 7 days

FR-006 requires its own kind, not `tax_rule`. The threshold is **policy, not observation** —
`data/observation_kinds.toml` says so in its own header — so it is the owner's statement about
how long he will trust a retrieval, and it carries no citation.

Seven days, on `cpi_index`'s argument applied to a faster publisher: what decays is the
*retrieval*, because the National Bank adds a rate every working day, so a series fetched a
month ago is a month short of its own end. It is not a claim that an old date's rate went
wrong — a published official rate for a date that has passed is a historical fact and never
changes.

## D10 — The series quotes one direction, and the inverse is not inferred

A series declares `pair = [price, unit]` and `quotation_unit`, exactly as `FxChannel` does:
`value` is the number of *price* units per `quotation_unit` units of *unit*. It converts
`unit → price` and nothing else. Asking it for `price → unit` refuses under D7's first
record.

Inverting is inferring, and `resolver._check_channel` already refuses to infer one pair from
another for the same reason. The tax direction is the one the law uses: a dollar income has a
hryvnia base.

`money.convert` takes `rate` as *units of `to_currency` per one unit of `amount.currency`*,
so the division by the quotation unit happens once, in this module, next to the declaration
that supplied the number.

## D11 — SC-009 is asserted as an absence, because there is no display switch

The spec's own "Required tests this feature relates to" says F2 is not closed because there
is no display switch. A test that "switches the display currency" would therefore have to
invent the switch to test it — which would pass for the wrong reason.

What can be asserted honestly, and is: **nothing in the tax-base path can read a display
choice, because no display currency exists in the engine**. A scan over the executable source
(prose stripped, `tests/source_scan.py`) of `terezy.core.tax` finds no display parameter, and
the struck base's currency is the one the jurisdiction declared and the only `Currency` the
conversion is given. The test says which of the two halves of F2 it establishes and which it
does not.

## D12 — `quotation_unit` is structural to the provenance gate

`scripts/check_provenance.py` treats any numeric leaf outside `STRUCTURAL_KEYS` as an
observed value needing a citation and a kind. `quotation_unit` sits on the `[series]` identity
table beside `pair`, which is already structural, and it is the counterpart of
`CpiSeries.base` — a statement of the *form* the values are in, which is a string there and
therefore invisible to the heuristic. It joins `STRUCTURAL_KEYS`; every `value` it scales
carries its own citation on its own observation.

`data/official_rates` joins `SOURCED_DIRS`. The gate is fail-closed on unknown directories,
so this is not optional.

⚙ **The exemption is wider than it looks, and review on 2026-08-29 found the first draft of
this note understating it.** It costs the whole `[series]` table its citation requirement,
not one field. The measurement and what closing it would take are stated at the exemption
itself in `scripts/check_provenance.py`, where whoever next edits that list meets them; they
are deliberately not repeated here.
