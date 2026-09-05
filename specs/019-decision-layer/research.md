# Research: the decisions this feature takes, and what each was taken against

Feature `019-decision-layer`. Each entry is a decision the specification leaves to the plan,
the alternative that was live, and the reason the alternative was refused. The four the owner
took are in `specs/decisions/2026-09-03-clarify-019.toml` and are not re-argued here.

## D1 — The relation is a function over figure vectors; a criterion is a reader

**Taken against** a relation written directly over two `TupleOutcome` records.

FR-007 requires the definition to live in exactly one place, and SC-004 requires a generated
battery at **three or more** objectives. The closed criterion set has **two** members (D4), so a
battery built out of declared objective sets cannot reach three, and adding a third criterion to
the closed set purely to make a test possible is a source change FR-003 exists to make
deliberate.

So the relation takes a **vector of figures per candidate** plus, per position, a direction and a
width, and knows nothing about instruments. The criteria are the adapter that reads a
`TupleOutcome` into a vector. The battery generates vectors; the pass reads them off the section.

It also settles SC-004a's planted witness cheaply: a non-transitive triple is three vectors, not
three registries.

## D2 — The battery reaches the acyclicity regime by scale, not by a tolerance parameter

**Taken against** threading a `tolerance=` keyword through the relation so the battery can widen
the slack to 1 over figures on `[−6, 6]`.

FR-007's measurement is stated with the slack taken as **1** against figures on `[−6, 6]` — a
spread of twelve slacks. The shipped slack is not a constant (FR-007): it is
`max(TOLERANCE·max(|a|,|b|), TOLERANCE)`, so at money scale the spread is ~2·10⁹ slacks and a
uniform draw never produces a cycle. The regime has to be reached deliberately.

It is reached by **scale**. Where `max(|a|,|b|) ≤ 1` the absolute half of the tolerance dominates
and the slack is exactly `TOLERANCE`, for every pair. Generating figures uniform on
`[−6e−9, 6e−9]` is the measurement's `[−6, 6]` at slack 1, exactly, with the **shipped** comparison
and no parameter.

The rejected alternative puts a test hook in a production signature. The tolerance module's
sanctioned `tolerance=` escape hatch is for an **assertion** that needs a looser bound, not for a
code path that ships with one.

## D3 — `slack` lives beside `is_close`, and `is_close` is not redefined in terms of it

**Taken against** (a) computing the width in `core/decision/`, and (b) rewriting `is_close` as
`abs(left − right) <= slack(left, right)`.

(a) is the second copy of the closeness rule FR-012 forbids, and the spec's Assumptions already
place the function in `core/primitives/tolerance.py`.

(b) is the tempting form — one expression, no way to disagree — and it changes behaviour on
non-finite inputs: `math.isclose(inf, inf)` is `True` while `abs(inf − inf)` is `nan`. The two
functions therefore stand side by side and their agreement is **asserted over generated finite
pairs** rather than obtained by construction. That is a weaker guarantee bought back by a check,
which is the trade this repository already makes for `tied_groups`.

## D4 — Two criteria, and the third a reader expects is not added

**Taken against** a closed set of three, with the rate beside the money and the date.

CL-1 declined the rate as an objective. A criterion nothing declares is a member the manifest and
the loader carry and no run constructs — the shape `InputKind`'s own docstring refuses. The two
criteria are the two figures `TupleOutcome` carries that the owner named:

- `money_at_the_endpoint` reads `TupleOutcome.reaches` — a `Money`, always present.
- `all_money_back_on` reads `TupleOutcome.arrivals[-1].arrived_on` — the field
  `core/decision/answer.py::_arrives_after_horizon` already names *the date its money actually
  arrives*.

SC-002 needs a **disagreeing pair** of objective sets and gets one without a third criterion: the
money alone is a total order and picks one member, while the money and the date pick ten at
twelve months (measurement item 6).

## D5 — The missing figure on the declared objectives is an **empty arrivals tuple**

**Taken against** reading FR-008a's parenthetical — *010's `RateNotComparable`* — as the only
instance.

`RateNotComparable` sits on `implied_rate`, and the rate is not a declared objective (CL-1), so it
decides nothing this pass computes. Of the two declared criteria one reads a field that is always
present and the other reads `arrivals[-1]`, which `_arrives_after_horizon` already guards for
emptiness. So the real missing-figure case is **an outcome with no arrivals**, and that is what
SC-013's fixture must plant. The parenthetical is an instance of the rule and stays true of a rate
criterion the day one is declared.

## D6 — FR-011d: a fraction resolves per **currency**, lazily, once per section

The specification hands three mechanics to this plan. All three are settled here.

### The width is per currency, and it is the question's own stated amount in that currency

`Question.amounts` is a mapping of stream id to `Money` in that stream's currency. A pair is
compared in the currency of `TupleOutcome.reaches`, which is the spendable endpoint's and a
property of the route.

- **Taken against summing** the amounts stated in a currency. Two UAH streams stating 50 000 and
  20 000 would resolve the band against 70 000 — a figure no declaration states and no candidate is
  funded with.
- **Taken against resolving against the candidate's own funding stream's amount.** The stream is a
  term of the candidate key, so per-stream is per-candidate in disguise: two candidates in one
  currency funded from two streams would give the pair two widths and break FR-011's symmetry,
  which is precisely what FR-011d forbids.

So the width for currency *C* is `fraction × amount`, where *amount* is the **one** amount the
question states in *C*.

### Absent and ambiguous are two refusals, and neither is zero

- **No amount stated in *C*** — `NoQuestionAmountInTheCurrencyCompared(criterion, currency)`.
- **More than one amount stated in *C*** — `SeveralQuestionAmountsInTheCurrencyCompared(criterion,
  currency, stream_ids, amounts)`. Naming the streams, because the remedy is a question edit and
  *which two* is the whole of what a reader needs.

Both are members of the `DominanceRefused` union, alongside FR-011c's floor refusal.

**Taken against recording the pair as incomparable** (FR-008a's other shape, which FR-011d offers).
FR-008a's incomparability is a property of two **figures** — one is missing, or they are in two
currencies — and both figures here are present and in one currency. The cause is a declaration, and
a section every pair of which is incomparable reports its whole population *not placed*, which
tells the reader the figures could not be read when what happened is that his own question states
no amount to size the band against. That is a guard whose message is false. FR-026's list of three
refusals is what the specification could enumerate before the records were in front of it; FR-011d
is the clause that says this one is the plan's to place.

**Taken against a load-time check.** FR-011c's argument transfers unchanged: which currency a
candidate delivers in is a property of the route, and a declaration file does not know it.

**What the ambiguous case costs, said plainly.** 015 requires an amount for **every** declared
stream, so a second UAH stream is a routine data edit — and it would put two UAH amounts in the
question, leaving a fraction band with no single width and refusing every section. That is not a
defect in the rule: FR-011's relation has to be symmetric, so one currency admits one width, and
there is genuinely no way to pick between two amounts the owner stated.

It is a cost of the **shape** he chose, and FR-011d already carries the remedy: an **absolute**
money band has no dependence on the question's amounts at all and is unaffected by any number of
streams. The refusal names the streams and the amounts precisely so the remedy is legible from it.

### Resolution is lazy — only for a currency some pair is actually compared in

The owner's question states **1.00 USD** for `contract_usd`, so his 0.01 % resolves there to
0.0001 USD — a width he did not choose, on a token amount the question file states to make an
empty stream visible. The specification records that it does not bite today only because no
candidate delivers USD, *which is a fact about the registry and not a property of the rule*.

Lazy resolution makes **half** of that a property of the rule. A width is computed for currency
*C* only where some pair is actually compared in *C*, so a currency no candidate delivers is never
resolved, never floored and never reported — the token amount cannot produce a width nobody reads.

**It does not close the hazard, and the arithmetic says why.** The day a USD candidate appears the
width resolves to 0.0001 USD and **clears** FR-011c's floor. The floor at two objectives is one
slack, `max(1e−9·|x|, 1e−9)`, so a width of `1e−4` exceeds it for **any** USD figure below 100 000 —
which is every figure a question of this size can produce. So the band applies, and it is a band
nobody chose. FR-011d is hedged for exactly this reason — *a width that would then
have FR-011c's floor **to clear*** — and this plan does not upgrade the hedge.

The remedy is the owner's and is one line in his own question file: a USD amount he means, or an
absolute USD band on the money objective, which FR-011d already permits beside the fraction. It is
recorded here as a named gap rather than guarded against, because a guard would have to decide what
a *token* amount is, and nothing declares that.

### The resolved width is carried once per `(objective, currency)`

FR-023 requires the width beside every population it counts.

- **Taken against a single width on the objective.** Wrong the moment one section compares pairs
  in two currencies.
- **Taken against carrying it on each verdict.** The same fact repeated once per pair; 276 copies
  per section on the owner's registry.

So `DominanceResult.resolved_bands` holds one `ResolvedBand(criterion, currency, from_amount,
width)` per pair actually resolved, ordered by `(criterion, currency)`. An absolute band and a day
band resolve to themselves and are reported in the declared form (FR-023), so `resolved_bands` is
empty for an objective set declaring no fraction.

## D6a — A section with no survey refuses too, and it is a sixth refusal

FR-026 enumerates the refusals the specification could name before the records were in hand, and
FR-011d is the clause establishing that placing one is the plan's job. `SectionOutcome` is
`CandidateSurvey | SurveyRefused | BenchmarkYieldsNoCandidate`, and `HorizonSection`'s own docstring
records that the non-survey arms are reachable rather than theoretical. A section that never
surveyed has no population to run over at all.

`HorizonSection.dominance` is not optional, so something has to go there. `NoSurveyToRunOver`
carries the record that replaced the survey, verbatim.

**Taken against an empty `DominanceResult`.** That is an empty set standing for a failure, which
FR-026 forbids in as many words, and it would be indistinguishable from the legitimate empty set of
a section that evaluated nothing (the specification's own edge case).

## D7 — The acyclicity floor is checked once per objective, against the widest slack in the section

**Taken against** checking the floor per pair, inside the relation.

The slack varies with the magnitudes of the pair being compared, so a per-pair check would let the
floor hold for most pairs and fail for a few — and a cycle is a property of the section, not of a
pair. The floor is therefore checked against `max(slack(x, y))` over the section's figures on that
objective, which is `max(TOLERANCE·max|x|, TOLERANCE)` and bounds every pair. Stricter than
necessary for most pairs, and the strictness is the point: a band that clears it clears every pair.

**Both of FR-011c's conditions, and the second is the one a plan drops.** The floor is
`band > slack` **and** `band >= (p − 1) · slack`, where *p* is the number of declared objectives —
not the first alone. At *p* = 2 the second is implied by the first and looks redundant; at *p* = 3
it is the whole guarantee, and the specification's own verified counterexample is what a floor of
one slack lets through: `(0, 0, 0)`, `(−1.6, 0.8, 0.8)` and `(−0.8, −0.8, 1.6)` at a band of one
and a half slacks form a three-cycle with every candidate placed and the set **empty**. A check
written as `band > max_slack` passes that band. The *(p − 1)* factor is vacuous at one and two
objectives and load-bearing above, which is why it reads as removable and is not.

On a **date** objective the slack is exactly zero (FR-011d) and the floor reduces to FR-011b's
positivity, so no floor check runs there.

## D7a — A figure is tagged, and so is a width; the closeness rule follows the tag

**Taken against** `relates(left: Sequence[float], ..., bands: Sequence[float])`, dates passed as
ordinals.

The weak half's rule is not the same on the two criteria — `is_close` on money, exact comparison on
a date, whose slack FR-011d fixes at **zero** — so a vector of bare floats has to carry that
distinction somewhere else, and an implementation that does not will apply the float comparison to
a date ordinal. At an ordinal near 740 000 that is a slack of ~7.4e−4 days where the contract
promises none. A parallel *is this one a date* flag is the same fact in two places.

So the figure carries its own kind:

```python
Figure = MoneyFigure(amount: Money) | DateFigure(on: date) | FigureUnavailable(what: str)
Width  = MoneyWidth(amount: Money) | DayWidth(days: int)
```

and the rule follows the tag: two `MoneyFigure`s go through `is_close` and a currency check, two
`DateFigure`s compare exactly. A `MoneyFigure` against a `DateFigure` at one position is a
programmer error and **raises** (Principle IV's split: `raise` for a violated invariant, a typed
value for a business result).

It is also what makes `PairVerdict`'s `Incomparable` reachable: it carries the position and the
reason — `FigureMissing` or `DeliveredInTwoCurrencies` — which the pass lifts into an
`IncomparablePair`, adding the criterion the relation has no way to know. Under a bare-float
signature the relation cannot tell the two reasons apart and the member is unconstructible.

## D8 — The declaration, and where *the question names an undeclared set* refuses

The objective set is a per-owner declaration under `data/objectives/`, one file per set, following
the `candidates/` precedent: an empty directory is a **refusal**, not an absence (FR-001's no
default), and two files declaring one id refuse through `resolver._refuse_duplicate`.

The question's `objectives` field is a required `str` on `schema.QuestionTable`, read by
`loader.question_from_document` — the one place the record is built, so the flag-built question
passes the same checks (015 FR-005).

*Names a set the registry does not declare* refuses in **`resolver.check_question`**, which is
already the public cross-file check and already refuses an amount for an undeclared stream. Not as
a typed core outcome beside `BenchmarkOutsideTheSubjects`: FR-026 says so in as many words — a
runtime refusal for it would be a second answer to a question the loader has already refused.

## D9 — The dominance result hangs on `HorizonSection`, and the canonical form encodes it

FR-027 puts it on the section beside the survey. `HorizonSection` gains one field; nothing in the
survey moves, and SC-016a asserts that field for field.

`core/results/canonical.py::of_section` gains one element for it. **This moves every answer
digest**, which is the correct outcome rather than a cost to avoid: the alternative is a digest
blind to the thing the section now reports, which is the defect already recorded as
`the-answer-digest-is-blind-to-the-hurdle`. That entry is **not** closed here — it is about
`benchmark`, `ties` and `beats_benchmark` inside `_of_section_outcome`, and this feature touches
none of the three.

## D9a — The pass takes a section's **parts**, not the section

**Taken against** `dominance(section: HorizonSection, ...)`.

FR-027 puts the result **on** `HorizonSection`, and the record is frozen and built in one call in
`core/decision/answer.py::_section`. A pass taking the finished section could not be called before
the section exists, and the escape routes are both bad: a default on the field, which is the silent
default this repository refuses everywhere else, or a `dataclasses.replace` that builds a section
whose `dominance` is momentarily wrong.

So the pass takes what `_section` already has in hand before it constructs anything — the outcome,
the withheld population and the section's stated exclusions — and `_section` passes the result into
the constructor. The reading functions over a **finished** section (`section_evaluated`,
`section_ties`) are unaffected: they are for readers, not for the pass.

## D10 — `ObjectiveDirection`, not `Direction`, and `TooCloseToCall` beside it

Two names, one rule. `core/results/answer.py` already declares `Direction` over an unrelated closed
set, so the objectives' enum is `ObjectiveDirection`.

The same trap sits **inside** this feature: `Indistinguishable` is the natural name both for the
per-pair verdict the relation returns and for the per-candidate record `DominanceResult` carries,
and an import binding one of the two silently is worse than a collision across modules. The verdict
member is **`TooCloseToCall`** — User Story 2's own words — and the record keeps
`Indistinguishable`.

And the union itself is **`PairVerdict`**, not `Verdict`: `core/tax/scheme.py` declares a `Verdict`
that `data/declarations/resolver.py` imports unqualified, which is the same collision one module
further out.

## D11 — FR-014's single-member reason is derived, not stored

`core/decision/answer.py::subject_counts` is the precedent and 014 FR-011 is the rule: a count
stored beside the list it counts is where the two come to disagree. FR-008's three populations are
on the record; *why the set has one member* is a named function over them returning a tagged union,
and it cannot disagree with the counts because it is computed from them.

## D12 — Implementation starts after two branches that are not on `main`

Stated once, here.

- **`fix/coupon-inside-the-window`** strikes an early exit net of the coupons that detached, which
  **moves `TupleOutcome.reaches`** — the money objective — for every candidate whose window
  contains a coupon. Every non-dominated set over the owner's question is computed from that figure.
- **`feat/real-only-registry`** moves the four fixtures to a test overlay and names `UA4000231195`
  the benchmark. The specification's *shipped registry* **is** that state, and without it every
  section is `BenchmarkUnavailable` and the pass refuses by FR-018 in every test.

So the measurement's counts — **2, 3 and 10** non-dominated at the three horizons, and 13, 18 and
23 beating the hurdle among reported candidates — are read against the *pre*-coupon-fix figures and
are **not to be hard-coded**. SC-001 already requires every count derived from the registry the
test loads; the tasks that re-measure are named in `tasks.md`.

`feat/real-only-registry` also **already renders `Comparison.beats_benchmark`**, resolved to keys
and restricted to the reported population, in `cli/main.py::_beats_line` — FR-029a's rule, applied.
What still reaches no reader after it lands is the **tie groups themselves**: `_beats_line` reads
`Comparison.ties` only to append *at least one candidate ties with it*, so which candidates tie
with which is computed and unrendered. FR-029's CLI task is scoped to that plus the dominance
populations, and extends `_beats_line`'s index-to-key resolution rather than repeating it.
