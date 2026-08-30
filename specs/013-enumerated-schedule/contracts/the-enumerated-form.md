# Contract: the enumerated form

**Feature**: `013-enumerated-schedule` | **Date**: 2026-08-29

What this feature promises to the rest of the engine, in the form a later change can break.

---

## 1. The instrument interface is unchanged

`enumerated_schedule` is an entry in `core.instruments.registry.REGISTRY` beside
`fixed_income`, built from the same three functions with the same signatures:

```python
events(InstrumentDeclaration, Holding, DateRange, Assumptions)
    -> tuple[Event, ...] | InstrumentFailure
tax_classes(InstrumentDeclaration) -> Mapping[TaxableEventKind, str]
constraints(InstrumentDeclaration) -> InstrumentConstraints
```

`InstrumentFailure` is **not widened**. Both new refusals are `InconsistentTerms` — two
declared facts that cannot both hold — which is what `fixed_income` and `seeds.py` already
return for the generative mirror of each. Widening the union is the sentence that would put
a constitution amendment back on the table (FR-013), so `core/errors.py` is untouched.

The three mismatches recorded at `core/instruments/registry.py` that kept a fund out of this
registry are each tested here and none holds: the inputs are identical, the new failures are
members of the existing union, and the answer is one event stream.

## 2. Nothing downstream branches on the form

The guarantee, asserted by `tests/contract/test_no_layer_knows_the_form.py`:

> No module under `core/ledger/`, `core/tax/`, `core/decision/` or `core/results/` — **and
> `core/results/project.py` in particular** — names the enumerated form, in code or in prose.

The scan's stated limit, repeated here so it is not read as complete: a name scan catches
`isinstance(...)` and `case EnumeratedTerms()` because those name the type. It does not catch
`terms.schedule is not None`, a bare `case GenerativeTerms(): ... case _:` pair, or
`if decl.form != "generative"`. That residual is covered by the delegation being *sufficient*
— there is nothing those spellings would buy — and by review.

**The one permitted `match` on the form is `core/instruments/terms.py`.** Asking a
declaration a question both forms answer is not naming it and stays permitted everywhere.

## 3. The questions both forms answer

```python
known_from(BondTerms | EnumeratedTerms) -> TermsKnownFrom
day_count_of(BondTerms | EnumeratedTerms) -> str
face_value_of(BondTerms | EnumeratedTerms) -> Money
principal_returned(BondTerms | EnumeratedTerms, *, bought_on: date) -> Money
conventions_of(BondTerms | EnumeratedTerms) -> ConventionsApplied | AmountsAsDeclared
excludes_of(BondTerms | EnumeratedTerms) -> frozenset[str]
narrowed(InstrumentDeclaration, type[T]) -> T
```

Adding a third form means one more arm each and no call-site change. Adding a question that
only one form can answer is the thing this contract exists to make visible: it would have to
be a refusal in the answer, not an absence at the call site.

**`face_value_of` and `principal_returned` are two questions and not one**, and confusing
them was defect F2. `face_value_of` answers *what does the paper say a unit redeems at*;
`principal_returned` answers *what will this holding actually get back*, and it is the one a
purchase is measured against. For a bond that repays its face once they agree, which is why
the confusion was latent.

**What the union does and does not enumerate.** `InstrumentDeclaration.terms` being
`BondTerms | EnumeratedTerms` makes `mypy --strict` list every site reading a term only one
form declares — five of `BondTerms`' seven fields. It lists **no** site reading `day_count`
or `face_value`, because both forms declare those, and it is `face_value` that F2 read.
Those two are sealed by `tests/contract/test_no_layer_knows_the_form.py` instead.
`provenance` is shared as well and deliberately unsealed: it is the citation rather than a
term.

## 4. The day count reaches no amount

The declared day count of an enumerated instrument appears in exactly two places: the
year-fraction function `results/project.py` builds the contractual-yield series with, and the
one `tuple_outcome._rate` builds the implied-rate series with. It sizes nothing, places
nothing, generates nothing, reconstructs no accrual period, and produces no coupon rate
(FR-003b).

Asserted mechanically by `tests/contract/test_day_count_reaches_no_amount.py`: the same
declaration under two different declared day counts produces two different yields and
**bit-identical** cash-flow amounts, compared through `float.hex()`.

Held shut a second time by `tests/contract/test_nothing_is_inferred.py`, which scans for the
coupon-rate derivation itself (FR-003c, SC-014). Two locks, because a guard that believes
itself sufficient is the one nobody adds a second lock to.

## 5. The canonical form distinguishes the two statements

```
ConventionsApplied  ->  (periodicity, day_count, business_day_rule)
AmountsAsDeclared   ->  ("declared", day_count, reason)
```

**The tag in slot 0 is the separation**, and it is the only one: both renderings are three
entries long. A generative rendering opens with a periodicity, so what keeps the two apart is
that no key of `conventions.PERIODICITY_FNS` may be spelled `"declared"` — asserted by
`tests/unit/test_conventions_statement.py`, because the property is now load-bearing rather
than incidental.

⚙ This paragraph said *"a 2-tuple can never equal a 3-tuple"* until 2026-08-30, and the
declared rendering had by then gained the statement's own words — which it needs, for the
reason the ledger's canonical form includes a causation's `detail`. The arity argument was
true when written and stopped being true in the same branch.

The generative arm is byte-for-byte what it is today, so no generative row's canonical bytes
move.

## 6. What the data boundary promises

Every failure in `data-model.md`'s battery names the file and the offending entry and
substitutes no default. No payment is merged, deduplicated or reordered on the way in — the
loader neither sorts nor accepts an unordered list, because ordering is settled at
transcription and *that the source published a different order* is a fact worth keeping
(FR-020a).

`scripts/check_provenance.py` additionally asserts, for a declaration whose class is
`enumerated_schedule`, that each of the four inference ids has a source carrying the
inference statement, an empty `verified_on`, and a matching verification task.
