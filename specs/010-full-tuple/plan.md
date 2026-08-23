# Implementation Plan: The full tuple

**Feature**: `010-full-tuple` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Branch**: `feat/010-full-tuple`, landing on `main` by a `--no-ff` merge after a clean
review pass.

## Summary

Everything built so far computes one term of the constitution's unit of analysis and admits
in writing that it ignores the others: the hurdle rate carries an `excludes` field saying it
omits route costs, and every route cost stops at a currency balance that never buys anything.
This feature is the join, and with it §8 question 1 — *does anything beat 15.5% tax-free
OVDP after every other option's fees, taxes and access costs?* — becomes computable instead
of a chart that flatters the expensive options.

The shape, decided in [research.md](./research.md): the join **composes existing calls and
computes nothing of its own** beyond summing what they return, because a figure the join
invented would have no owner and no test would know where to check it. Its only original
content is the **chaining rule** and the refusals.

**The chaining rule is where this feature can be wrong.** Feature 004 learned it expensively:
its exit chain was anchored at neither end, so money teleported between venues for free while
the record still read as a coherent journey. The same failure is available here at two more
seams — route-in to purchase, and instrument-exit to route-out. Both get anchored, both sides
named in the refusal, each tested with a deliberate mismatch.

And the acceptance test the constitution has been waiting for: **H1**. A new instrument,
route, tax class and jurisdiction added in data only run the full pipeline and appear in the
comparison. If that cannot pass, the abstraction is wrong somewhere behind us — and finding
that out is part of this feature's value, so the finding is recorded rather than patched.

## Technical Context

**Language/Version**: Python 3.13; CI matrix 3.12 / 3.13 / 3.14.

**Primary Dependencies**: none new.

**Storage**: version-controlled TOML — one new synthetic jurisdiction, instrument, route and
tax class for H1. No network.

**Testing**: pytest. A hand-computed full round trip (SC-001); H1 as a contract test over a
scratch data root; ties and refusals as unit tests; the existing goldens as regressions.

**Target Platform**: library only. No API, no CLI.

**Project Type**: single Python library, `cli → api → data → core`.

**Constraints**: core pure, no clock; exactly four plugin interfaces and **this feature adds
none**; functional style per D-E; one imported tolerance; currency roles separate through the
join and amounts in different currencies never silently combined.

**Scale/Scope**: 3 new core modules, 4 new declaration files for H1, ~10 test modules.
Closes **H1** — or records precisely why it cannot.

## Constitution Check

| Principle | Verdict |
|---|---|
| **I — Honesty over precision** | **PASS.** The join invents nothing: every term comes from a call that owns it, and each part's contribution is separately reported so a reader sees which term dominates. Partial deployment reports the remainder rather than rounding; below-minimum is infeasible and named. Two figures per outcome — the amount and the rate — so neither invites deriving the other under an assumption the tool did not make. |
| **II — Framework, not script** | **PASS, and this feature is where the claim is finally testable.** H1 is the constitution's own acceptance test and it could not be attempted before a full pipeline existed. FR-023 makes a failure a recorded defect in the abstraction rather than a special case in the join — which is the difference between a test that can falsify the architecture and one that cannot. |
| **III — Pure deterministic core** | **PASS.** No clock; the horizon and every date are declared or passed. The join is a fold over calls that are themselves pure. |
| **IV — Reliability through contracts** | **PASS.** Ties use the imported tolerance and 002's rules unchanged, including a tie between a tuple and the hurdle. Every refusal is a typed union member naming both sides of the seam that failed. |
| **V — Test-first** | **PASS.** SC-001's full round trip is hand-computed end to end, which is the only way to catch a join that sums the right parts in the wrong order. |
| **VI — Model the whole tuple** | **PASS — this feature *is* the principle.** Keying carries all five terms; the same instrument from two streams is two tuples with two outcomes; the risk class is declared and deliberately not scored. |
| **Engineering Standards — D-E** | **PASS.** Frozen records, free functions, tagged unions matched with `match`. |
| **VII — Owner-scoped and private** | **PASS.** No new per-owner data; the H1 fixtures are synthetic and labelled. |

### Post-Phase-1 re-evaluation

Three things the design surfaced:

- **The benchmark must come from the same code path as the things it benchmarks.** A
  separately-computed hurdle can drift from the tuples it is compared against, and the drift
  is invisible because both numbers look reasonable. Asserted by construction, on 002 SC-016's
  precedent.
- **One horizon, or the comparison answers two questions.** Evaluating a two-year instrument
  over two years and a twenty-year one over twenty compares different things. And carrying
  early proceeds forward would need a reinvestment assumption nobody declared — the invented
  number this feature is most likely to reach for.
- **H1's value is that it can fail.** The temptation, when a data-only addition needs one
  small engine edit, is to make the edit and keep the test green. That converts the only test
  that can falsify the architecture into one that cannot. FR-023 forbids it; the plan repeats
  it because it will be tempting at exactly the moment nobody is watching.

## A boundary this feature must not cross

**The official rate does not exist yet.** Feature 011 is `drafted`, not built. FR-024
requires tax in the tax currency at the declared official rate for the transaction date. A
foreign-currency taxable event must **refuse**, naming the missing machinery — never convert
at a channel rate. A channel is a market you transact in; the official rate is a legal
reference you never transact at, and 002 already refuses the substitution at
`legs.py::channel_for`.

This dependency is **not** in the graph's `needs`, deliberately: it binds only on a
foreign-currency taxable event, which the shipped registry does not produce. Adding it to
`needs` would falsely block this feature. Record it as a note beside the entry instead.

## Project Structure

```text
src/terezy/core/
├── decision/                        the package the constitution reserved, until now empty
│   ├── tuple_outcome.py             NEW — the join, the chaining rule, the refusals
│   └── compare.py                   NEW — the comparison, ranking, ties
└── results/
    └── tuple.py                     NEW — the outcome, per-part attribution, typed refusals

data/                                four new SYNTHETIC declarations for H1:
                                     one instrument, one route, one tax class, one jurisdiction
```

```text
tests/worked_examples/
└── test_full_round_trip.py          SC-001 — ramp in, purchase, lifecycle, tax, exit, ramp out

tests/contract/
├── test_h1_data_only.py             SC-006 — the constitution's acceptance test
├── test_the_hurdle_is_a_tuple.py    SC-002, SC-003 — same path, by construction
├── test_every_figure_states_its_scope.py  SC-009
└── test_marks_survive_the_join.py   SC-007 — one unverified value planted in each of four parts

tests/unit/
├── test_chaining_refusals.py        FR-004 — a deliberate mismatch at each seam
├── test_two_streams_two_outcomes.py SC-004
└── test_infeasible_tuples.py        SC-010 — below minimum, fee exceeding amount, no exit

tests/golden/                        UNCHANGED FILES — 001, 002 and 007's goldens must not move
```

## Departures from the specification as written

Recorded here rather than only in a test docstring, because a departure a reader of the spec
cannot find is one that gets read as a satisfied criterion.

**SC-002, as literally written, does not hold.** The criterion asks that *the OVDP evaluated
as a tuple through its zero-cost domestic routes reproduces feature 001's hurdle rate within
the project tolerance*. Over the domestic pair **as declared** the two figures are 0.1598 and
0.16059, which is outside the tolerance. The whole gap is the one day in and the three days
out that those routes declare, and FR-015 puts waiting **inside** the span the rate is
measured over — an owner decision of 2026-08-22, not an inference from it. The two claims are
therefore incompatible as stated, and the equality is asserted over a `without_latency`
fixture that zeroes those declarations.

That is the right reading rather than a workaround: the criterion is about the *pipeline*
producing 001's number, and latency is a term 001 never had. But it is an edit to the
declarations, and the criterion does not say so. `tests/contract/test_the_hurdle_is_a_tuple.py`
asserts the equality over the edited pair and, separately, that the shipped pair's gap is four
days of it and nothing else — the amounts are equal at the project tolerance and only the
dates moved.

## Complexity Tracking

| Added complexity | Why | Alternative rejected because |
|---|---|---|
| Both seams anchored with both sides named | 004 shipped an unanchored seam and money moved between venues for free while the record read as coherent | An unanchored join produces a confident wrong number that no structural test catches |
| Two figures per outcome (amount and rate) | Different questions: what can be spent, and what compares across horizons | Reporting one invites deriving the other under an assumption the tool never made |

## Phase 2 note

Order: **the chaining rule and its refusals first**, with a deliberate mismatch at each seam
— that is the part that can be silently wrong, and everything else is a sum of calls that
already work. Then the outcome record and per-part attribution; then the comparison and its
ties; then **H1 last**, because it is the test of everything before it. Tests before
implementation in each group.
