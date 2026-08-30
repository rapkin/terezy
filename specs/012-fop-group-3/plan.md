# Implementation Plan: The ФОП group 3 regime

**Feature**: `012-fop-group-3` | **Date**: 2026-08-30 | **Spec**: [spec.md](./spec.md)

**Branch**: `feat/012-fop-group-3`, landing on `main` by a `--no-ff` merge after a clean
review pass. Not landed by this plan.

## Summary

The owner's largest cash flow is taxed by a `float | None` on an income stream. This feature
replaces it with the thing the money actually lands in: a **declared taxation scheme** — an
identity, a set of separately named components, each with its own dated cited schedule, a
variant, and a reporting cadence — that an income stream *names* the way feature 006's
instruments name tax classes.

Three things follow, and they are the feature.

**The base is struck at the credit date.** Dollars credited to a ФОП account are converted to
hryvnia at the **official rate on the credit date** through feature 011's machinery, called
unchanged and on a date this feature supplies. The hryvnia the compulsory sale produces is a
different number at a different rate on a different date; both are reported and the gap
between them is labelled as outside the base.

**A component can be nothing, because the scheme says so.** єдиний податок and військовий
збір are rate components on that base. ЄСВ is a **periodic** component — triggered by a month
elapsing, not by income arriving — and the owner's scheme declares it explicitly at zero, with
his own statement as its source. Nothing in the engine evaluates an exemption, and nothing in
the engine knows any of these names.

**Where the money is credited decides which reading applies.** The crediting destination is a
declared fact on the stream, distinct from the routing origin. One destination is INTERPRETED
and produces a charge. Four are UNSETTLED and produce a **labelled scenario switch**: one
figure per computable reading, each naming its reading and carrying that reading's citations,
none labelled the tax owed, and no field anywhere for a blend to live in. A destination the
declared table has no row for **refuses**, naming the destination and the scheme.

**What this feature does not do**: it re-models no funding route, adds no leg kind, channel
kind or cost mechanism, invents no end date for the levy, and researches no legal value. Every
value it enters is quoted in the spec with its citation and an empty `verified_on`.

## Technical Context

**Language/Version**: Python 3.12+. **Primary dependencies**: none new.

**Storage**: version-controlled TOML. Two new directories, both **under `data/tax/`** so the
provenance gate's `rglob` reaches them with no script change (research D2):
`data/tax/schemes/` (two files) and `data/tax/destinations/` (one file).

**Testing**: pytest. Hand-computed charges checked in beside their assertions (SC-001, SC-003,
SC-016); a battery of broken declarations against a scratch data root (SC-006); refusal
coverage (SC-010, SC-013); propagation (SC-007, SC-008); AST source scans for the no-branch
and containment claims (SC-002, SC-011, SC-017); `contract` tests for the Principle II and
Principle I compliance statements (SC-012, SC-017, SC-017a).

**Target platform**: library only. No API, no CLI, no delivery surface — as in every feature
so far.

**Constraints**: core pure, no clock, no I/O; four plugin interfaces and this feature adds
none; frozen records and free functions; the single imported tolerance; the three currency
roles kept apart in both directions.

**Scale/scope**: 1 new core module, 2 new data directories with 3 files, ~8 touched source
files, ~12 test modules. Closes no required-test row; records a second exercise of **E10** and
the structural prerequisite of **E8**.

## Constitution Check

| Principle | Verdict |
|---|---|
| **I — Honesty over precision** | **PASS.** No legal value originates here: every rate, date and rule is quoted in `spec.md` with its citation and enters with an empty `verified_on`. Four destinations produce labelled what-ifs rather than a number, none of them labelled the tax owed, and there is no field for a blend. A destination nothing declared reaches refuses. The 5% єдиний-податок entry is dated by `data/tax/ua.toml`'s own **Rule B2** and says so on the entry, rather than by an implementer's judgement. |
| **II — Framework, not script** | **PASS.** A second scheme with a different component set, and a moved verdict, are data-only changes asserted with zero source lines changed (SC-012, SC-004). No component name, scheme id, destination or date name appears in executable source — asserted by an AST scan with its own falsifiability test. No fifth plugin interface, and no entry added to either existing registry. |
| **III — Pure deterministic core** | **PASS.** `core/tax/scheme.py` reads no clock and does no I/O; every date is an argument. The credit date is a caller's fact and the periods are a caller's `Window`. |
| **IV — Reliability through contracts** | **PASS.** Every degraded outcome is a typed record naming its own fix, and the three nils are three types rather than three readings of one zero. `SchemeCharge.total` is `money.total` over the lines, so no blended percentage exists to be recovered from. The one imported tolerance. |
| **V — Test-first** | **PASS.** Every charge lands with hand arithmetic checked in beside the assertion; every module is preceded by a test that fails with `ImportError`. Any golden whose recorded input digest moves is regenerated deliberately with the changed lines quoted in the commit message — expected for the coverage golden, which two new venues may reach (research D13). |
| **VI — Model the whole tuple** | **PASS.** The tax role strikes the base at the credit date; the transaction role produces the hryvnia received on the sale date; the gap is its own labelled figure and nothing nets them. The one place the spec's own source uses a channel rate in a base is refused, and the refusal is declared on the reading and asserted (SC-017a). |
| **VII — Owner-scoped and private** | **PASS.** The relocation *sharpens* the boundary: the owner declares which scheme he is in (a fact about him, uncited) and the rates move into curated tax data with their sources. `data/README.md`'s citation exemption stops covering a legal rate, because there is no longer one in per-owner data. No network, no new dependency. |
| **Engineering Standards — D-E** | **PASS.** Frozen records, free functions, closed enums, tagged unions matched with `match`. No class carries behaviour. |

### Post-design re-evaluation

Four things the design surfaced, each carried forward rather than worked around:

- **FR-027 names three states and the engine can produce two.** *No source reaches the
  destination* and *a source reaches it and the table has not caught it* are the same
  observation to a program: the table has no row. The refusal reports one state whose reason
  names **both** closures rather than asserting which obtains (research D16). Inventing a
  declaration that says *a source exists for a destination the table does not name* would make
  the third state emittable and would be a claim about the world that nothing checks.
- **Two charge shapes now exist in `core/tax/`.** `TaxCharge` has exactly two fixed lines
  named for PIT and the levy, and FR-006 forbids writing a єдиний податок into either.
  Generalising it would reach `year.py`'s whole netting fold, `AssessedLiability`,
  `results.tax_year` and two goldens for a feature that needs none of it (research D4). The
  seam that would force the merge is stated at the module docstring: an income stream that has
  to be assembled into an annual liability beside instrument charges, which is feature 009's.
- **`deployable` reports in the tax currency, and it had to.** `gross − charged = net` cannot
  hold across two currencies, and both ways of forcing it into the stream's currency are
  forbidden — one by 011 FR-012, the other by this feature's FR-012 (research D14).
- **`deployable` has exactly one caller and it is its own unit test.** Nothing else in the
  repository would notice if FR-016's carefully argued distinction were deleted by the schema
  change. That makes SC-005 a real risk rather than a formality, and it is why the migration
  gets its own phase and its own test module rather than riding along.

## Boundaries this plan must not cross

**Do not re-derive a crediting-destination verdict, do not research a source, and do not add
a destination.** The verdicts are the least settled thing in the feature and are expected to
move; `specs/features.toml`'s `crediting-destination-verdicts` records that moving one is a
row in the table, a row in the register and a line in owner verification task 6. This plan
builds for them moving: the verdict is a declared word, the readings are declared rows, every
reading computes from a declared scheme, and no destination or component name reaches the
engine.

**No legal, tax or fee value from memory, and no retrieval on this feature.** The owner has
ended retrieval here. A value that turns out to be needed and is not in the spec is recorded
as a gap and reported; it is not researched and not guessed. That already bites once: the
VAT-payer 3% rate is deliberately not entered, and the variant field is what makes it a
data-only addition when it is ever cited.

**4015-IX may not be cited for either of the levy's dates.** Its own text says
«з 1 жовтня 2024 року» and «по 31 грудня року, у якому». The rate is 4015-IX's, the start is
4113-IX's, the end is 4835-IX's, and each travels with its own entry.

**Do not invent an end date for the levy, and do not let its absence read as permanence.** The
termination is conditioned on an event, is entered as `DeclaredContext` — recorded, cited, not
applied — and the modelling question stays where it lives, `features.toml`'s
`martial-law-ends-one-belief-two-places`.

## Structure

```text
src/terezy/core/tax/scheme.py                 new — the scheme, its charges, the destinations
src/terezy/core/streams/streams.py            the scalar retired; credited_to; deployable
src/terezy/data/declarations/schema.py        Scheme*/Destination* tables; StreamTable
src/terezy/data/declarations/loader.py        scheme_from_file, destinations_from_file, _stream
src/terezy/data/declarations/resolver.py      SCHEMES_DIR, DESTINATIONS_DIR, the cross-checks
data/tax/schemes/ua_fop_group_3.toml          new
data/tax/schemes/ua_personal_income.toml      new — one declaration, consumed, never copied
data/tax/destinations/ua.toml                 new — the normative table, five rows
data/venues.toml                              + payoneer, + foreign_bank_usd
data/streams/owner-001.toml                   - income_tax_rate_pct, + credited_to, + tax_scheme
data/README.md                                the streams row and the exemption argument
scripts/check_provenance.py                   the streams exemption reason, which names the retired field
docs/METHODOLOGY.md                           §13 rewritten, + §33 the taxation scheme
docs/REQUIRED_TESTS.md                        E10's second exercise, E8's prerequisite
specs/features.toml                           012 status
specs/002-ramp-cost/spec.md                   ⚙ on FR-007: superseded (FR-018)
tests/schemes.py                              new — synthetic fixtures, labelled
```

## Phasing

1. **The scheme in the core** — records, the two lookups, `charge_income`, `charge_period`,
   `component_standing`, the refusals. Tests first, hand arithmetic checked in.
2. **The declaration** — schema, loader, resolver, the two shipped scheme files, the broken-file
   battery.
3. **Where the income is credited** — readings, the switch, `apply`, FR-027's refusal, the
   destinations file, the two venues.
4. **The stream migration** — the scalar retired, `credited_to` and `tax_scheme` added,
   `deployable` rewritten, `data/README.md` and the provenance script's exemption reason.
5. **Base against received** — the two figures and the signed, labelled gap.
6. **The standing properties** — the no-branch scan, data-only extensibility, never-blended,
   never-the-tax-owed, one-declaration-consumed, the SC-017a departure.
7. **Documentation and the graph** — METHODOLOGY §13 and §33, `check_methodology_refs.py` by
   exit code, REQUIRED_TESTS, `features.toml`, the ⚙ on 002's FR-007.
8. **`/condense`, then `/code-review` until clean.**

## Complexity tracking

| Departure | Why | Alternative rejected because |
|---|---|---|
| A second charge record beside `TaxCharge` | `TaxCharge` has two fixed lines named for PIT and the levy; FR-006 forbids putting a єдиний податок in either | Generalising `TaxCharge` reaches the netting fold, `AssessedLiability`, `results.tax_year` and two goldens, for a feature that assembles no annual liability (FR-004 puts that in 009) |
| `RefusedState` has two members where FR-027 names three states | The engine cannot tell *no source exists* from *the table has not caught one*; the second is a reader's determination, as SC-013's own note says | A third member nothing constructs is a member never executed; a two-way split whose reason names both closures is the honest shape |
| `Verdict` has no `SETTLED` member | Nothing here is settled, and a settled destination would want INTERPRETED's wrapper anyway | An unconstructed enum member states a behaviour the code has never had |
| A periodic component's `period` is closed at `"month"` | `core/primitives/periods.py` enumerates months and nothing else; ЄСВ is monthly | Declaring `"quarter"` would need period arithmetic that does not exist — a change to `periods`, not a data entry, and pretending otherwise would make Principle II's data-only claim false for a scheme nobody could actually run |
| Two venues with no declared route | SC-017 pins per-destination figure counts against the **shipped** table; two of its five rows have no venue otherwise | Shipping the table with two rows testable only in a scratch root would make the normative table a fixture |
