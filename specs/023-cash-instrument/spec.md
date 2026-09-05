# Feature Specification: Cash as a declared instrument

**Feature Branch**: `023-cash-instrument`

**Created**: 2026-09-06

**Status**: Draft

**Input**: The owner, 2026-09-02: «Кеш це гривня на Monobank під 0 %».

## Why this feature exists

The owner's question opens with the word `cash`, and the registry declares nothing that word
resolves to. So the answer's first line reads `[subject] cash undeclared`, and every ranking
under it is a ranking of the alternatives to a baseline that is not in the comparison. The
constitution requires the opposite — *naive baselines are always scored and always shown, and
when nothing beats them the tool says so plainly* (Principle I) — and `docs/DIRECTION.md` puts
the same sentence in the product's own terms. `docs/REQUIRED_TESTS.md` I4 records that the row's
own subject is a cash instrument, and 015's owner verification task 1 records that its terms are
his to state. He has now stated them.

Declaring it is **necessary and not sufficient**, and 015 says why: bought at the venue the
money already sits at, a cash instrument reaches `compose`'s *money that is already where it was
wanted*, and stands in 014's no-candidate column because `Tuple.route_in` is required and no
zero-hop way in exists. That is the `zero-hop-way-in` future, recorded as unreachable *until an
instrument is declared bought at `monobank_uah`*. This feature declares exactly that instrument,
so the gap becomes live in the same change that closes it.

## The declaration

A **new instrument class**, `cash_balance`: a balance held at a venue, in one currency, paying a
rate declared to be exactly zero.

```toml
[instrument]
id           = "cash_uah_monobank"
class        = "cash_balance"
currency     = "UAH"
groups       = ["cash"]

[instrument.balance]
rate_pct     = 0.0            # the four citation keys beside it
```

with an access record naming `bought_at = "monobank_uah"`, `proceeds_to = "monobank_uah"` and no
`[access.price]` table, and a `cash` group declared in `data/groups.toml`.

**The alternative was a `fixed_income` declaration with a zero coupon, and it is rejected.** A
bond is declared by a face value it repays, a date it repays on and a periodicity, and cash has
none of the three. Every one is a **required** field, so the declaration could only be written by
inventing them, and each would then be an undeclared value sitting in a sourced directory where
the provenance gate asks it for a citation nobody can give. The same holds for the price: a bond
**must** quote an `[access.price]` and a fund **must not**, and cash is a third answer — one
hryvnia of balance costs one hryvnia, so a declared price would be one fact in two places.

**It is a declaration kind, not a fifth plugin interface.** `InstrumentOps` is the dispatch for
declaration kinds whose projection *is* a stream of ledger events, and a cash balance produces
none — no coupon, no redemption, no accrual. It therefore sits in `DECLARATION_KINDS` and outside
`REGISTRY`, exactly where `collective_investment_fund` sits and for the reason that module already
records. No fifth interface is added and no amendment is required. Adding a *second* cash balance
— a hryvnia balance at another venue — stays a data-only change, and SC-004 is that test.

## The zero-hop way in

The salary arrives in hryvnia at `monobank_uah`; the balance is bought in hryvnia at
`monobank_uah`. Nothing has to move, and **no corridor from a venue to itself is invented**.

The way OUT already has this shape. 003 FR-002 lets a spendable destination satisfy its own exit,
and `ExitByIdentity` is that sentinel — a single-member enum rather than `None` and rather than an
empty chain, because *a round trip that costs nothing because there is nothing to do* is a
different claim from one whose fees cancelled. This feature adds its mirror on the way in, on the
same argument and in the same module, and widens `Tuple.route_in` to admit it.

It is legal on exactly the condition `compose` already computes for its `ALREADY_ARRIVED`
refusal: the stream's arrival venue and currency equal the instrument's buying venue and declared
currency. So the pair that today stands in the no-candidate column carrying
`NothingNeedsToConnect` becomes a candidate, and that column member — whose own docstring says it
exists to make the gap visible "rather than as a permanent answer" — is retired with the gap.
`compose`'s refusal text is untouched: refusing to route money to where it already is stays
correct, and what changes is that enumeration stops asking.

`monobank_uah`/UAH is the owner's **only** declared spendable endpoint, so the way out is
`ExitByIdentity` by the rule that already exists. Both ends of this candidate are identity, which
is what makes it the do-nothing baseline rather than a cheap journey.

## The worked example

50 000.00 UAH, the amount the question states for `salary_uah`, over each declared horizon.

| | |
|---|---|
| way in | entry by identity — 0.00 UAH, 0 days, so `purchased_on` = 2026-09-01 |
| bought | 50 000.00 UAH of balance; nothing undeployed, because there is no unit to round to |
| lifecycle | no coupon, no redemption, no accrual: the rate is zero |
| tax | 0.00 UAH — proceeds equal basis by construction, so no gain and no income arises |
| way out | exit by identity — 0.00 UAH, 0 days |
| reaches | **50 000.00 UAH** on 2026-10-01, on 2026-12-01 and on 2027-09-01 |
| implied rate | **0.00 %** nominal at all three: one outflow and one inflow of equal size |
| round trip | 0.00 UAH, both legs, so it is quotable as a round trip (Principle VI) |

The arithmetic is `reaches = outlay`, and it needs an assertion because every term of it — the
two identity legs, the zero rate, the absent tax — is a separate claim that could be wrong on its
own. Both identity legs declare zero latency, so cash's `span` is exactly the horizon where a
bond's runs three days past it: that does not resolve
`rates-in-one-ranking-span-different-periods`, it means the baseline is the one member of the set
the gap cannot touch.

## What cash carries, and what it does not

**A mark, and the same kind every other figure carries.** There is no venue provenance to
inherit — `data/venues.toml` declares no citation keys at all, holding an id, a name and currency
codes with nothing for a source to vouch for. The one observed value is the rate, and the claim
it makes is not really *zero*: it is that **this Monobank product is a zero-rate balance and not
a deposit**, a fact about a bank that can be wrong. So the rate carries the four citation keys,
`verified_on` is empty until the owner checks the account's terms, and every figure cash produces
renders marked.

**No assumption, and no exclusion beyond the floor.** Cash is struck at no quotation, so none of
the four early-exit exclusions every ranked bond carries attaches to it, and it needs no declared
belief about a future spread. What it does keep is every member of the exclusion floor — above
all *inflation: every figure here is nominal*, which is exactly where a 0.00 % is most easily
misread.

**The `hold_as_cash` continuation is the same fact, stated once.** The question declares that
proceeds arriving before a horizon's end sit as cash and earn nothing. That is what this
instrument declares, so nothing is modelled twice: no candidate's early proceeds are reinvested
into `cash_uah_monobank`, no second zero rate is applied, and the continuation rule is unchanged.

## Requirements

### The declaration

- **FR-001**: `cash_balance` MUST be a declared instrument class in `DECLARATION_KINDS` and MUST
  NOT be in `REGISTRY`. The reason MUST be the one the registry module already states for a fund
  — `InstrumentOps` dispatches kinds whose projection is an event stream, and a balance produces
  none — and not a new one.
- **FR-002**: The declaration MUST state a venue-independent identity: id, name, class, currency,
  synthetic flag and groups, exactly as every other instrument does.
- **FR-002a**: A cash subject MUST be able to carry a **run plan**, which today it cannot: the
  question file's plan vocabulary is closed at two kinds and refuses a third **by name** at load.
  Widening it — the declared kind, the question schema, the plan union and the canonical
  rendering that matches over it — is part of this feature. A run-settings record with no
  producer is a record nothing can build, and 014 FR-003 refuses an instrument with no plan.
- **FR-003**: The rate MUST be stated explicitly and MUST be exactly zero. Any other value MUST
  fail at load naming the file and the field, saying that a balance paying something is a
  **deposit** whose rate, capitalisation, early-withdrawal penalty and interest taxation are the
  bank's terms and must be cited. A missing rate MUST fail the same way; it MUST NOT default.
- **FR-004**: The rate MUST carry `source`, `retrieved_on`, `verified_on` and a declared
  observation kind, and its mark MUST propagate to every figure derived from it (Principle I).
  The kind MUST be **declared for it** rather than borrowed: none of the eleven existing kinds
  covers what a bank pays on a balance — `bank_fee_schedule` is a tariff charged and
  `venue_terms` is a condition of dealing — and a kind with no staleness threshold fails at load,
  so borrowing one would put this figure's expiry under a threshold set for something else.
- **FR-005**: A `cash_balance` access record MUST NOT carry `[access.price]` or
  `[access.resale_price]`; either MUST refuse at load. Sizing is identity — an amount of the
  declared currency buys that amount of balance.
- **FR-006**: The access record MUST declare `bought_at`, `proceeds_to` and a risk-class label,
  and both venues MUST be able to hold the declared currency, on the check that already exists.
  The risk class MUST stay a carried label that nothing scores.
- **FR-007**: `cash` MUST be a declared group in `data/groups.toml` and the instrument MUST carry
  the label. Membership MUST NOT be inferred from the class, the id, the venue or the tax
  treatment (015 FR-007a).
- **FR-008**: Adding a second `cash_balance` at another declared venue MUST be a **data-only**
  change that runs the whole pipeline and appears in the comparison.
- **FR-008a**: The registry the decision layer resolves an id against MUST carry cash. It holds
  exactly two mappings today and looks an id up in both, and an id in **neither is skipped with
  no refusal at all** — so without this a declared cash balance disappears from enumeration
  silently, which is the failure mode Principle IV forbids by name. The third mapping is added
  at the resolver and at the join together.
- **FR-009**: The declaration MUST NOT name a tax class, and the outcome MUST charge zero tax
  **because proceeds equal basis**, stated in its own `accounts_for`. It MUST NOT be recorded as
  an exemption: no legal value is introduced by this feature and none is needed.
- **FR-010**: The class MUST state its day-count convention once, and a declaration MUST NOT
  state one. With the rate pinned at zero no convention can move the implied rate, and SC-006
  asserts that over every declared convention rather than asserting it in prose.
- **FR-011**: A cash balance MUST declare no minimum ticket and no unit increment: any amount of
  the currency is holdable, and the outcome MUST carry **no** undeployed-cash record. A record
  reporting a zero would have to name the constraint that stranded the money, and there is none.

### The zero-hop way in

- **FR-012**: `Tuple.route_in` MUST admit a **named** identity entry — a value, not `None` and
  not an empty chain — carrying the same distinction `ExitByIdentity` carries, and declared
  beside it.
- **FR-013**: The identity entry MUST be legal exactly where the stream's arrival venue and
  currency equal the instrument's buying venue and declared currency, and that claim MUST be
  **checked against the declarations at the join**, not trusted from the caller — the rule
  `_identity_way_out` already applies to the far end. A caller asserting it where it does not
  hold MUST be refused with the seam named.
- **FR-014**: It MUST charge nothing and take no time: the purchase happens on the horizon's
  first day, and the `ramp_in` contribution MUST be a **recorded zero** rather than an omitted
  part.
- **FR-015**: Enumeration MUST construct the identity entry for such a pair instead of asking
  `compose` for a corridor, and MUST NOT declare a route from a venue to itself. `compose`'s own
  `ALREADY_ARRIVED` refusal MUST be left exactly as it is.
- **FR-016**: `NothingNeedsToConnect` MUST be retired from the no-candidate column, because the
  state it names is now a candidate. Its removal is a change to 014's typed union, made and
  reviewed there, and it reaches the CLI, three test modules and a golden as well as the two
  core modules that build it — the *Counts that move* table names them.
- **FR-016a**: Enumeration's match over `compose`'s three refusal cases MUST stay **exhaustive**.
  Deleting the *already arrived* arm would leave a closed enum with an unhandled member; the arm
  MUST instead `raise`, naming the invariant that makes it unreachable — enumeration
  short-circuits on the same venue and currency `compose` compares. That is a programmer error
  by the project's own rule, and it MUST NOT be a candidate-less pair reported as a finding.
- **FR-017**: The candidate ordering (014 FR-016) MUST stay total with an identity entry in the
  key, and loading the declarations in a different file order MUST change neither membership nor
  sequence. The entry has no route id, so it MUST render under **its own** name — the ordering
  key and the canonical record the answer digest is taken over both hold that string, and
  rendering one union member under another's name is what the canonical module's own rule
  forbids.

### The figures

- **FR-018**: The outcome MUST report `reaches` equal to the outlay at every horizon, within the
  project tolerance, and MUST NOT reach that figure through an empty arrival list — the balance
  is released at the horizon's end, so the span is the horizon.
- **FR-019**: The implied rate MUST be a nominal rate of zero **within the project tolerance**,
  not `RateNotComparable`. Cash is comparable; refusing a rate for it would hide the baseline from
  the ranking it exists to anchor. The tolerance is not a hedge: the rate is bisected to a root,
  so an exact-zero assertion would be a test that fails for a reason unrelated to the claim.
- **FR-020**: Round-trip cost MUST be zero and MUST be reported as a **round trip**, both legs
  being identity. A one-way figure MUST NOT stand in for it (Principle VI).
- **FR-021**: The outcome MUST carry no assumption, MUST add **no exclusion beyond the floor
  every outcome already carries**, and MUST carry the declaration's provenance mark. It MUST NOT
  drop a floor member: cash is where a nominal figure is most easily read as a real one, so
  *inflation — every figure here is nominal* has to survive on it above all.
- **FR-022**: The run manifest MUST name the cash declaration's file, which today means a fourth
  arm in the function that builds input references — it reads three declaration maps and a cash
  declaration is in none of them. A file a run read and the manifest does not name is not a
  result (Principle III).
- **FR-023**: No reinvestment MUST be modelled. The question's `hold_as_cash` continuation and
  this instrument state one fact, and the continuation's behaviour MUST NOT change.

### The answer

- **FR-024**: `cash` MUST resolve to the declared group and move from the answer's **undeclared**
  population to **reached**, with the three-state count moving with it (015 FR-010).
- **FR-025**: Every count this feature moves MUST be **re-measured** by regenerating the goldens
  deliberately, with the diff read and the changed lines quoted in the commit message, and MUST
  NOT be hand-edited to a figure somebody expected (Principle V).
- **FR-026**: This feature MUST NOT change the declared benchmark. Naming cash as the benchmark
  is the owner's one-word change to make, and its meaning is stated below.
- **FR-027**: `docs/METHODOLOGY.md` MUST gain the cash projection in the same change, and
  `docs/REQUIRED_TESTS.md` I4 MUST record what this closes and what it does not.

## Success Criteria

- **SC-001**: 50 000.00 UAH reaches 50 000.00 UAH at each of the three declared horizons, in a
  worked example whose arithmetic is checked in beside the assertion.
- **SC-002**: The implied rate is 0.00 % at each of the three horizons, and the round-trip cost
  is 0.00 UAH with both legs present.
- **SC-003**: The answer reports `cash` as a group resolving to one id; the reached count is
  three and the undeclared count is one, `btc` being the remaining word.
- **SC-004**: A second cash balance declared in a scratch data directory — a hryvnia balance at
  another venue — enumerates, evaluates and ranks with **no engine edit**, in the shape
  `tests/contract/test_data_only_extensibility.py` already uses.
- **SC-005**: A declaration stating a non-zero rate, a missing rate, or an `[access.price]` table
  each fails at load naming the file and the field.
- **SC-006**: Cash's implied rate is 0.00 % under **every** declared day-count convention, over
  generated horizons and amounts.
- **SC-007**: Cash's outcome carries exactly the floor exclusion set — every member of it, and
  none of the four early-exit exclusions every ranked bond in the shipped answer carries.
- **SC-008**: With `verified_on` empty, every figure cash produces renders visibly marked; filling
  it in moves no figure and does not move the answer digest.
- **SC-009**: The identity entry names no route id and no route declaration is added under
  `data/routes/`; an identity entry asserted for a pair that does not satisfy FR-013 is refused
  with the seam named.
- **SC-010**: The class string reaches no sealed tree, on the scan
  `tests/contract/test_no_layer_knows_the_form.py` already runs for `enumerated_schedule`.

## Counts that move, and what re-measures them

Only cash's own figures are computed here. Everything below is measured by a named artefact.

| Artefact | What moves |
|---|---|
| `tests/golden/the_answer.golden.txt` | `[considered]`, both `[subject]` populations, `ids=`, `pairs`, `enumerated`, `no_candidate`, `ranked` and the digest |
| `tests/golden/test_the_answer.py` | `test_the_recorded_artefact_ranks_every_bond_against_the_declared_benchmark` asserts the literal `"  ranked 21"` — re-measured, not guessed |
| `tests/golden/candidate_set.golden.txt` | the `[accounting]` block and the `[no candidate]` rows |
| `tests/unit/test_no_candidate_column.py`, `tests/unit/test_candidate_records.py`, `tests/contract/test_tags_and_unions.py`, `tests/golden/test_candidate_set.py`, `src/terezy/cli/main.py` | every consumer of `NothingNeedsToConnect`, retired under FR-016. Two of them assert the union is closed, so this is a `contract` suite that goes red until all five move together |
| `tests/contract/test_data_only_extensibility.py` | pins `DECLARATION_KINDS` at exactly three members and `REGISTRY` at exactly two; the first widens, the second does not |
| `tests/contract/test_marks_survive_the_join.py` | a candidate whose route-in contributes no mark |

## The benchmark

With cash declared, `benchmark = "cash_uah_monobank"` in `data/questions/fifty-thousand.toml`
becomes a one-word change, and `beats_benchmark` would then read literally. **This feature does
not make it.** He chose `UA4000231195` on 2026-09-03 for its date, and replacing that choice is
his to make rather than a consequence of the instrument existing.

## Non-goals

- **A deposit or a savings account.** A balance that pays something needs the bank's cited terms —
  a dated rate schedule, capitalisation, the early-withdrawal penalty, and the tax treatment of
  the interest. FR-003 refuses one by name rather than admitting it silently.
- **Inflation and real terms.** A tuple still has no real-terms rate; that is feature 024.
- **BTC.** The other undeclared word; feature 025.
- **A second cash balance, and idle cash inside another candidate's horizon.** The class admits
  the first and SC-004 proves it in a scratch directory; FR-023 keeps the second where it is.

## Assumptions

- **The 50 000 UAH is at `monobank_uah`.** That is 015's owner verification task 3 and this
  feature does not settle it — it inherits the reading, and if the owner corrects it the identity
  entry stops applying and the candidate becomes an ordinary routed one.
- **`monobank_uah`/UAH is the sole declared spendable endpoint**, read from
  `data/spendable/owner-001.toml`, and the salary stream's own amount is `0.0` — what funds the
  candidate is the amount the question states, as for every other candidate.
- **The venue is a synthetic fixture and the product is real.** `data/venues.toml` labels
  `monobank_uah` SYNTHETIC FIXTURE, so this is a real bank product reached through a fixture
  venue — the standing the 24 real ОВДП already have through invented corridors. The owner's
  2026-09-02 rule that an invented instrument may not ship is satisfied: this is an account he
  holds.

## Owner verification tasks

1. **The citation for the rate.** Either the URL of Monobank's published terms for the account, or
   confirmation that the recorded statement of 2026-09-02 is his own and stands as the source.
   Until one of them, `verified_on` is empty and every cash figure renders marked — which is the
   correct state, not a deficiency to work around.
2. **The benchmark**, above. One word, and his to write.
