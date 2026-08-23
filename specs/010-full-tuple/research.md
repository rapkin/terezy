# Phase 0 research: the full tuple

**Feature**: `010-full-tuple` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

This feature joins what the others built. Almost nothing here is new arithmetic — the
decisions are about **where the join lives** and **what it is forbidden to invent**.

---

## D1 — The join is a composition of existing calls, not a new pipeline

**Decision.** `core/decision/tuple_outcome.py` calls, in order: 002's costing for the way in,
006/001's projection for the holding, 009's tax where it applies, and 002/004's costing for
the way out. It computes **no figure of its own** beyond summing what those return.

**Rationale.** FR-002 and FR-005: every term comes from a declaration and each part's
contribution is separately reported. If the join computed anything, that figure would have
no owner and no test would know where to check it. The join's only original content is the
**chaining rule** (D2) and the refusals.

**`core/decision/` is the right home** and it is empty by design: the constitution reserves
it for candidate generation and choice, which is exactly what a comparison of tuples is.

## D2 — Chaining is checked, not assumed, and this is the one place the join can be wrong

**Decision.** The route in must end at the venue and in the currency the instrument is bought
in; the instrument's exit must produce a balance where the exit route begins. A mismatch is a
typed refusal naming both sides.

**Rationale.** FR-004. Feature 004 learned this the expensive way: its exit chain was
anchored at neither end, and money teleported between venues for free with the record still
reading as a coherent journey. The same failure is available here at two more seams. **Anchor
both, name both sides in the refusal, and test each seam with a deliberate mismatch.**

## D3 — The hurdle is produced by the same code path as every tuple

**Decision.** The benchmark in the comparison is not a separately-computed figure. It is the
OVDP evaluated as a tuple through its declared zero-cost domestic routes.

**Rationale.** FR-012 and SC-002/SC-003. A benchmark computed by a different path is a
benchmark that can drift from what it benchmarks — and the drift would be invisible, because
both numbers would look reasonable. Asserted **by construction**, on the precedent of 002's
SC-016 and 004's SC-002.

## D4 — One horizon, declared, for every tuple in a comparison

**Decision.** A comparison states its horizon once; every tuple is evaluated over it. A tuple
whose instrument terminates earlier reports what happens at termination and holds the
proceeds; nothing is reinvested by assumption.

**Rationale.** FR-025. Comparing a two-year instrument against a twenty-year one over their
own lifetimes compares two different questions. And reinvesting the early proceeds would
require a reinvestment assumption nobody declared — the invented number this feature is most
likely to reach for.

## D5 — Keying is per `(instrument × stream × route in × exit terms × route out)`

**Decision.** The tuple's identity carries all five. A cost or an outcome attributed to an
instrument alone stays unrepresentable, as 002 FR-008 and 004 FR-011 already require.

**Rationale.** FR-010. The same instrument funded from two streams is two tuples with two
outcomes (SC-004) — that is the product's whole thesis, and it is only true if the key says
so.

## D6 — H1 is the acceptance test, and a failure is a finding, not a patch

**Decision.** A new instrument, route, tax class and jurisdiction added **in data only** run
the full pipeline and appear in the comparison. If some addition turns out to need an engine
edit, the gap is recorded as a named defect in the abstraction — which seam, which
declaration kind, what edit it forced — and **fixing the abstraction is in scope**.

**Rationale.** FR-021 and FR-023, and the spec says it plainly: *hiding the finding is not*
in scope. This is the constitution's own acceptance test and it cannot be attempted until a
full pipeline exists. If H1 cannot pass, the abstraction is wrong somewhere behind us, and
finding that out is part of this feature's value.

**Do not add a special case inside the join to make H1 pass.** That converts the one test
that can falsify the architecture into a test that cannot.

## D7 — Nothing is rounded, and what cannot be deployed is reported where it sits

**Decision.** An arriving amount below the instrument's minimum ticket makes the tuple
infeasible, named. A remainder the declared increment cannot deploy is reported with its
amount and its venue, kept out of what reaches the endpoint, and **netted off the outlay the
rate is measured against** — it is cash at the purchase venue, and discounting the arrivals
back to the whole outlay would price it as a total loss.

**Rationale.** FR-003, FR-017. Rounding up to the minimum, or silently deploying what fits and
dropping the rest, are both figures more confident than their inputs — and the second is the
one that looks right. Charging the remainder as a loss is the same error mirrored, and it is
the one that actually shipped: 500 UAH stranded at `inzhur` reported a 16% sovereign bond
at −7%.

⚙ **Corrected 2026-08-24.** This decision was written before clarification 3 and said that a
cap forcing a split "reports each tranche and the undeployed remainder", citing FR-018. FR-018
**defers** partial deployment (owner decision, 2026-08-22): this feature evaluates single-shot
acquisitions only, there is no tranche, and `PartiallyDeployable` was never built. The
sentence described the pre-clarification design and is deleted rather than reinterpreted.

## D8 — Two figures per outcome: the amount and the rate, both labelled

**Decision.** Every tuple's outcome is reported **both** as the amount that reaches a
spendable endpoint and as the rate that amount implies, each stating what it accounts for and
what it excludes.

**Rationale.** FR-014, FR-015. The amount is what the owner can spend; the rate is what
compares across horizons. Reporting one invites the reader to derive the other with an
assumption the tool did not make.

## D9 — The risk-class term is declared and not scored

**Decision.** The instrument declares its risk class; this feature carries it into the
comparison and **scores nothing**.

**Rationale.** The spec's own Key Entities say so. Scoring risk needs a model nobody has
declared, and an unscored declared label is honest where a computed score would not be.

## D10 — The boundary: the official rate does not exist yet

**Decision.** A taxable event in a foreign currency **refuses**, naming the missing
official-rate machinery. It does not convert at a channel rate.

**Rationale.** FR-024 requires tax in the tax currency at the declared official rate for the
transaction date, and feature 011 is `drafted`, not built. Every taxable event in the shipped
registry is hryvnia, so the refusal is unreachable today — and it must exist, because a
channel is a market you transact in and the official rate is a legal reference you never
transact at. 002 already refuses that substitution at `legs.py::channel_for`; this feature
must not quietly permit it one layer up.

**Note this dependency is not in `features.toml`'s graph.** 010 `needs` 002 and 006. The
official-rate need is real but conditional — it binds only on a foreign-currency taxable
event, which the shipped data does not produce. Record it as a `[[future]]`-adjacent note
rather than editing the graph's `needs`, which would falsely block this feature.

## D11 — Where the code lives

- `core/decision/tuple_outcome.py` — the join and its refusals.
- `core/decision/compare.py` — the comparison, its ranking and its ties.
- `core/results/tuple.py` — the outcome record, per-part attribution, the typed refusals.

Ties use the imported tolerance and 002's tie rules unchanged (FR-013), including a tie
between a tuple and the hurdle itself.
