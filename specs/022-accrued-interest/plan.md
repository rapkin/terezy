# Implementation Plan: Accrued interest on a carried quotation

**Feature**: `022-accrued-interest` | **Date**: 2026-09-05 | **Spec**: [spec.md](./spec.md)

**Branch**: `feat/022-accrued-interest`, landing on `main` by a `--no-ff` merge after a clean
review.

## Summary

A quotation is a dirty price. One function turns a quotation and a date into a clean price and
an accrual; a second turns a clean price and a date back into a price. Both bond legs go
through them — the buy quotation at the purchase, the sell quotation at the sale — and the
detached-coupon subtraction, its residual exclusion and the two `SoldEarly` fields that
explained it are deleted rather than adjusted.

Net of the deletions this is a **small** change with a **wide** blast radius: two goldens, one
rewritten worked example, one belief declaration moved, and one methodology section rewritten.

## Technical Context

**Language/Version**: Python 3.13.

**Primary Dependencies**: none new. `conventions.day_count` already supplies the year fraction;
`terms_of.accrual_periods` already supplies the generative form's periods.

**Storage**: version-controlled TOML. One belief declaration moves and is rewritten; no
instrument declaration changes — `day_count` and every payment date are already there.

**Testing**: pytest. One worked example (the spec's arithmetic), one property-based invariant,
two regenerated goldens, one contract scan for the removed exclusion.

**Target Platform**: library.

**Project Type**: single Python library, `cli → api → data → core`.

**Constraints**: no fifth plugin interface; nothing new imported into `core/`; the accrual
lives beside the schedule readers, not inside the decision layer. `Money` arithmetic only —
no bare floats crossing a currency boundary. The project tolerance is imported, never
re-invented.

**Scale/Scope**: one new core module, edits to five core modules, one data file moved, one
methodology section rewritten, four test modules.

## Constitution Check

| Principle | How this feature meets it |
|---|---|
| I — honesty over precision | The linear-accrual and constant-clean-price assumptions are both declared and both stated on every figure that leans on them (FR-003, FR-016 to FR-020). The replacement exclusion carries **no** direction because rate risk is symmetric; the retired one carried a sign whose warrant this change destroys. |
| II — framework, not script | No branch on an instrument, a venue or a jurisdiction. The day count is a declared choice among registered conventions, and the coupon dates come from the declaration. |
| III — pure deterministic core | Pure functions over frozen records; no I/O, no clock. |
| IV — stated contracts | Two refusals are typed values carrying their reason (FR-008, FR-012); the identity `price(observed_on) == quote` is an invariant, not a comment. |
| V — test-first | The worked example is written first and fails before the module exists. |
| V — a golden is evidence | Both goldens move by design (FR-025), regenerated with their changed lines quoted in the commit message. |
| VI — the whole tuple | The purchase and the sale are priced by one formula, so a round trip is measured on one basis; the spread survives as the difference between the two clean prices and is never reported one-way. |
| VII — owner-scoped | The belief file keeps its `owner_id`; no per-owner data is added. |

No violation to justify.

## The collision this plan resolves

**Two features are open on the same figures.** `019-decision-layer` is planned and not started:
its spec's non-dominated counts of 2, 3 and 10 are pre-fix readings that no test pins, so they
re-measure after this lands and its implementation is not blocked by more than that.
`021-web-declared-data` is in progress and reads the published schema, which moves three ways:
`SoldEarly` loses two required properties and gains two, `InputKind`'s `early_exit_assumption`
member is renamed, and the `early-exit-belief` category's path segment is renamed with it — the
resolver constant behind it is reached by `getattr` on its name, so the two cannot move apart.
The document regenerates under its existing gate and the client's types regenerate from it. No
request parameter is added, and nothing the client computes changes.

## The work, in phases

**Phase 1 — the accrual, written test-first.** `core/instruments/accrual.py`: the period lookup
for both declaration forms, `accrued(t)`, `clean(quote)`, `price(clean, t)`, and the typed
refusal for a date outside every declared period. The worked example fails against it with an
`ImportError` before a line exists. The refusal is reached by three shipped issues, not only by
a fixture — the newly placed ones, whose lists open after the quotation.

**Phase 2 — the purchase leg.** `tuple_outcome._price_for` carries the buy quotation to the
purchase date. This is where the hold-to-maturity overstatement dies — twelve of the
twenty-four issues reach maturity inside the owner's twelve-month horizon and are held to it
(measured 2026-09-05) — and where the belief starts reaching candidates that state no early
exit, so `_rests_on` is widened in the same phase, not later.

**Phase 3 — the sale leg, and the deletions.** `acquire.early_sale` and
`results/project.py::_sold_early` strike the sale at `price(clean, sold_on)`.
`early_exit.detached_since` is deleted, with `SoldEarly.detached_per_unit` and
`skipped_before_purchase`; `SoldEarly` gains `clean_per_unit` and `accrued_per_unit`. The
`enumerated.events` repayment refusal is restated in the accrual's terms.

**Phase 4 — the belief and the exclusions.** `data/scenarios/early_exit/owner-001.toml` moves to
`data/scenarios/quotation/owner-001.toml` with a new `id` and a rewritten `rationale`; the
resolver constant, the HTTP category id, the manifest's `InputKind` member and the manifest ref
follow it, and the first two move together because a `getattr` on the constant's name links
them where no type checker looks. `QuotationHolds` leaves `core/scenarios/early_exit.py` for a
module not named for the exit. `Exclusion.EARLY_EXIT_IGNORES_ACCRUED_INTEREST` and
`Direction.SALE_STRUCK_TOO_LOW` are removed and the unsigned clean-price claim replaces them.

**Phase 5 — the counts and the prose.** Regenerate both goldens, re-measure what the spec's
*Counts that move* names, rewrite §34 of `docs/METHODOLOGY.md` and add the accrual formula,
delete the docstrings this change falsifies (below), and run the full gate list.

## Which tests re-measure, and which are written by hand

Only the worked example carries hand-computed arithmetic. Everything else is measured by the
suite rather than by a person, which is the point of naming them here:

| Test | How its figures are obtained |
|---|---|
| `tests/worked_examples/test_accrued_interest.py` | **by hand**, from the spec's worked example: the three accruals, both clean prices, the purchase and sale prices, and 49 758.37 reached |
| `tests/invariants/test_accrual_invariants.py` | property-based: `price(clean, observed_on) == quote`; `accrued` is non-decreasing within a period and resets at each coupon date; `accrued(c_i) == 0`; `0 <= accrued(t) < C` |
| `tests/golden/the_answer.golden.txt` | regenerated; every early-exit line moves and every accrued-interest exclusion row goes |
| `tests/golden/candidate_set.golden.txt` | regenerated; purchase prices move, unit counts and undeployed remainders may follow |
| `tests/contract/test_the_answer_says_only_what_it_computed.py` | re-measured: the exclusion set shrinks by one and the direction set by one |
| `tests/worked_examples/test_a_coupon_inside_the_window.py` | **replaced** by the first row. Its `DETACHED_PER_HORIZON` and `MULTI_COUPON` measurements lose their subject; `BEFORE_THE_PURCHASE` survives as the purchase-carried-across-a-coupon case |
| `tests/golden/test_enumerated_matches_generative.py` | re-run unchanged — it is the check that FR-007's one rule really is one rule |

## Prose this change falsifies, and deletes

Named here because each states as fact what the change stops honouring, and a stale claim is
found expensively otherwise. `VenueQuote.observed_on`'s docstring (the paragraph beginning
"A quotation carried to a later date"); `_price_for`'s two paragraphs on the quotation being
used as declared; `coupons_per_unit`'s closing paragraph in `enumerated.py`; `SoldEarly`'s
field docstrings for the two removed fields; §31.5 of `docs/METHODOLOGY.md` in full; and
`early_exit.py`'s module docstring. Deleted, not rewritten (constitution, review section).

## Decisions a reader will want the reason for

**One rule for both declaration forms**, rather than the enumerated form alone. The generative
form has a declared `day_count` and already generates its accrual periods, so excluding it
would be a second rule that exists only to be different — and
`test_enumerated_matches_generative.py` would then be pinning a divergence.

**A zero-coupon schedule is a legitimate zero, not a refusal.** Its accrual is zero on every
date by definition and the formula produces the right answer with no special case. Refusing
would refuse a correct figure, which is as much a defect as inventing a wrong one.

**No refusal for a missing day count.** Both terms records require the field, so the guard
would never fire — a false guard by the review's own definition.

**The first coupon period is not opened at `covers_from`.** It is a coverage claim about the
published list, not a declared accrual start, and UA4000236228 shows the cost of pretending
otherwise: 71 days from `covers_from` to a first coupon that pays a full 182-day amount.
