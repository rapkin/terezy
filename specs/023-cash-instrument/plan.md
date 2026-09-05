# Implementation Plan: Cash as a declared instrument

**Feature**: `023-cash-instrument` | **Date**: 2026-09-06 | **Spec**: [spec.md](./spec.md)

**Branch**: `feat/023-cash-instrument`, landing on `main` by a `--no-ff` merge after a clean
review.

## Summary

Two changes that only work together. A fourth declaration kind, `cash_balance`, whose projection
is a purchase on the horizon's first day and a release of the same amount on its last. And the
mirror of `ExitByIdentity` on the way in, which is what makes a candidate representable at all
when the money is already at the venue that sells the thing.

Neither half is small in reach, and the reach is what the phases are shaped around. Three closed
sets widen and mypy enumerates each one's sites the moment a member joins: the nine `match`
statements over `Declared`, and every function beside them that takes the projection union, every reader of `Tuple.route_in` that today calls a `Candidate`
member on it, and the two-member plan union that the question loader, the digest and the CLI all
match over. A fourth set **narrows** — the no-candidate union — and that one mypy finds only in
`src/`, so the three test modules and the golden that pin it are listed in the spec's table
instead. Two goldens move.

## Technical Context

**Language/Version**: Python 3.13.

**Primary Dependencies**: none new.

**Storage**: version-controlled TOML. One new instrument declaration, one new access row, one new
group id, one new observation kind, one new run plan on the question.

**Testing**: pytest. One worked example (the spec's), one property-based invariant over the
day-count conventions, two regenerated goldens, one widened data-only contract test, four load
refusals.

**Target Platform**: library.

**Project Type**: single Python library, `cli → api → data → core`.

**Constraints**: no fifth plugin interface — `cash_balance` joins `DECLARATION_KINDS` and stays
out of `REGISTRY`, where `collective_investment_fund` already sits. Nothing new imported into
`core/`. `Money` arithmetic only. The project tolerance is imported, never re-invented.

**Scale/Scope**: two new core modules, edits to ten core modules, three data-layer modules and
the CLI, four data files, one methodology section, eight test modules.

## Constitution Check

| Principle | How this feature meets it |
|---|---|
| I — honesty over precision | The naive baseline stops being absent from the comparison, which is the clause's own remedy. The zero rate is a cited claim about a bank product and carries its mark like every other figure (FR-004). No statistical metric is emitted for it. |
| II — framework, not script | A new *class* is a plugin behind the `Instrument` concept, as `enumerated_schedule` and `collective_investment_fund` were; a second *instance* of it is data only (SC-004). No branch on a venue, an id or a jurisdiction. |
| III — pure deterministic core | Pure functions over frozen records. The identity entry is a value, not a `None` the reader has to interpret. |
| IV — stated contracts | Four load refusals name file and field (FR-003, FR-005); the seam check on the identity entry is a typed refusal, not an assumption (FR-013). |
| V — test-first | The worked example is written first and fails with `ImportError` before the module exists. |
| V — a golden is evidence | Both goldens move by design (FR-025), regenerated with their changed lines quoted in the commit message. |
| VI — the whole tuple | Both legs of the round trip are present and both are identity, so the zero is a round-trip figure and not a one-way one (FR-020). Cost stays keyed by `(instrument × stream × route)`; a USD stream against this instrument yields no candidate for the ordinary reason. |
| VII — owner-scoped | No per-owner data is added. `data/spendable/owner-001.toml` is read, not changed. |

No violation to justify. The one thing worth stating: this adds a **declaration kind**, not a
plugin interface, and the argument is the registry module's own — `InstrumentOps` dispatches
kinds whose projection is an event stream, and a balance produces none.

## The work, in phases

**Phase 1 — the class, written test-first.** `core/instruments/cash.py`: `CashDeclaration`
(id, name, class, currency, synthetic flag, groups, the rate and its provenance) and
`CashAssumptions`. `DECLARATION_KINDS` gains the member; `REGISTRY` does not. The data layer
gains a schema model, a loader, a `LOADERS_BY_KIND` entry and a third mapping on the resolved
declarations, plus the load refusals: a rate that is not exactly zero, a missing rate, an
`[access.price]` and an `[access.resale_price]`. The plan vocabulary widens here too — the
declared plan kind, the question schema, the `InstrumentPlan` union and the canonical rendering
that matches over it — because `CashAssumptions` has no producer until it does. A new observation
kind is declared with its threshold and the reason for it. The worked example is written here and
fails on the import.

**Phase 2 — the identity way in.** `EntryByIdentity` beside `ExitByIdentity` in
`core/routes/path.py`, one member, with the same argument against `None` and against an empty
chain. `Tuple.route_in` widens. `core/routes/cost.py` builds the zero-cost inbound walk on the
pattern `_IDENTITY_ROUTE` already sets for the far end. `tuple_outcome` checks the claim at the
seam and refuses with it named. `candidates._walk` constructs it for a pair instead of calling
`compose`, and the entry renders under its own name in both the ordering key and the canonical
record the digest is taken over.

Widening `route_in` is the phase's real cost: every site that calls a `Candidate` member on it
— the segment lists, the funding-stream guard, the destination id, the monthly-cap check, the
route-id collectors, the digest, the CLI and `ramp.py` — is a mypy error until it handles the
sentinel, and each is a decision about what *no route at all* means there.

**Phase 3 — the retirement.** `NothingNeedsToConnect` goes, and with it the CLI arm, the two
tests asserting the union is closed and the golden renderer — all in one commit, because two of
them are `contract` tests and a half-done narrowing is a red compliance suite. The
`ALREADY_ARRIVED` arm of `_about_the_question` is **not** deleted: the match is exhaustive over a
closed enum, so the arm becomes a `raise` naming the invariant that makes it unreachable.
`compose._refusal` is untouched. Third phase rather than second so the member is removed only
once something reaches past it.

**Phase 4 — the projection and the arm.** `core/results/cash.py::project_cash` emits a purchase
on the horizon's first day and a release of the same amount on its last. `_project` gains its
third arm, and the eight other matches over `Declared` gain theirs, along with the ones over the
projection union — mypy lists both sets, so none is found by a reader. `_price_for` returns the identity price rather than reaching for a quote;
`_projection_provenance` carries the rate's mark, which is where a bond's terms already arrive.
`Registries` gains its third mapping and the two lookups that read it — without which a declared
cash balance is skipped by enumeration with no refusal at all — and the manifest's input
references gain their fourth arm, so the file the run read is named.

**Phase 5 — the data.** `data/groups.toml` gains `cash`; `data/instruments/cash_uah_monobank.toml`
and its access row are written, and the question file gains the `cash` run plan its subject
needs — the vocabulary that accepts it landed in Phase 1.

**Phase 6 — the counts and the prose.** Regenerate both goldens and re-measure what the spec's
*Counts that move* names; §29 of `docs/METHODOLOGY.md` gains the cash projection;
`docs/REQUIRED_TESTS.md` I4 records what this closes and what it does not; `specs/features.toml`
gains the feature and loses the `zero-hop-way-in` future. Full gate list.

## Which tests are written by hand

Everything in the spec's *Counts that move* is obtained by regenerating the artefact named
there. These four are new, and only the first carries arithmetic a person computed:

| Test | What it asserts |
|---|---|
| `tests/worked_examples/test_cash_reaches_the_amount.py` | **by hand**, from the spec: 50 000.00 in, 50 000.00 out at each of three horizons, 0.00 % implied, 0.00 round trip |
| `tests/invariants/test_cash_invariants.py` | property-based: over generated amounts and horizons and **every declared day-count convention**, `reaches == outlay` within the project tolerance and the implied rate is zero |
| `tests/unit/test_cash_declaration_loading.py` | the four load refusals, each on the file and field it names |
| `tests/contract/test_no_layer_knows_the_form.py` | re-run: the new class string must reach no sealed tree |

## Decisions a reader will want the reason for

**`CashAssumptions` carries no fields.** 014 FR-003 refuses an instrument with no run plan, so
the plan must exist; nothing about running a balance is chooseable, so it holds nothing. A
consumption method would suggest a choice between lots that cannot arise, and a coupon policy a
coupon that does not exist.

**The day count is the class's, not the declaration's.** `_day_count_of` must return a registered
convention, and with the rate pinned at zero none of them can move the implied rate — which
`tests/invariants/test_cash_invariants.py` asserts over the whole registry rather than a comment
claiming it. Requiring the declarer to state one would be asking for a convention that decides
nothing.

**No minimum ticket and no unit increment.** A balance is not bought in units, so
`_whole_increments` does not apply to it and `undeployed` is `None` rather than a rounding
residue. This is a real difference between a balance and a security, and it is one of the reasons
the class exists.

**The rate's mark arrives through the projection, not through the constraints.** A bond's terms
reach the outcome via `_projection_provenance` and its constraints via `_declaration_provenance`;
putting cash's one citation in the second would move which part of
`tests/contract/test_marks_survive_the_join.py` carries it, for no gain.

**The citation's `retrieved_on` post-dates the answer's `as_of`.** The question is asked as of
2026-08-30 and the owner stated the rate on 2026-09-02, so the source ages to a negative number
and reports current — the right verdict for a source newer than the question, and the reason it
is written down is that a reviewer meeting a negative age would otherwise have to work it out.

**The identity entry is checked at the join, not trusted from the caller.** Exactly the rule
`_identity_way_out` applies to the far end, and for the same reason: derived from the
declarations it is safe by construction, asserted by a caller it is a bare claim about where the
money is.

## Prose this change falsifies, and deletes

`NothingNeedsToConnect`'s docstring in `core/results/candidates.py`, which states the gap this
closes, and the sentence above its construction site saying a refused pair "lands in
`NothingNeedsToConnect` instead"; `core/decision/candidates.py`'s module docstring claiming a
`Tuple` cannot exist without a `route_in`, and its paragraph introducing the `ALREADY_ARRIVED`
arm; the `zero-hop-way-in` note in `specs/features.toml`; and the sentence in
`specs/019-decision-layer/spec.md`'s list of gaps this feature does not close, which is a live
instruction in an unbuilt spec rather than a record. Deleted, not rewritten — with **one
exception**: `data/questions/`'s header says `cash` and `btc` are declared by nothing, and the
`btc` half stays true, so that paragraph and its heading are cut to one word rather than removed.
