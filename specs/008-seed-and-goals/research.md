# Phase 0 research: seeds and goals

**Feature**: `008-seed-and-goals` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

All clarifications were resolved by the owner on 2026-08-22. Nothing here is a
`NEEDS CLARIFICATION`. D3 is the decision the whole feature's honesty rests on and it is
the one to read first.

---

## D1 — Seeds are opening lots the existing ledger already knows how to hold

**Decision.** `core/ledger/seeds.py` turns declared seed lots into the opening events
`core/ledger/engine.py` already consumes. No new lot type, no parallel position store, no
special case in the fold.

**Rationale.** FR-002 and FR-003 require every conservation invariant to count seeded lots
from day one. The cheapest way to guarantee that is to give the invariants nothing new to
count: a seed becomes a `Lot` through the same opening path a purchase takes, and
`test_ledger_conservation`'s existing properties cover it without being told it exists. A
separate "seed position" would need every invariant taught about it, and the first one nobody
taught would be the defect.

**Alternatives rejected.** A current-value seed. The spec's own sentence is the argument: *a
guessed cost is a guessed tax* — the tax engine needs lots (§4.8), and a seed stated as
"I hold 100 units worth X today" cannot produce a disposal gain at all.

## D2 — Seeds and goals are committed per-owner declarations, on the streams precedent

**Decision.** `data/seeds/owner-001.toml` and `data/goals/owner-001.toml`, version-controlled,
beside `data/streams/` and `data/spendable/`. Both directories get `EXEMPT_DIRS` entries in
`scripts/check_provenance.py` with their reason recorded.

**Rationale.** Principle VII, and the precedent already set twice: `data/streams/owner-001.toml`
holds the owner's salary, which is at least as private as a holding, and it is committed. The
repository is designed to hold this person's complete financial picture (CLAUDE.md, Privacy);
the boundary that matters is **curated versus per-owner**, not committed versus not.

**The provenance exemption is the same one `objectives` and `strategies` carry**: what the
owner paid for a lot and what sum he is aiming at are his own records, not observations of
the world, and there is nothing for a source to vouch for. If a market value ever needs to
live here, it moves to a sourced directory rather than the exemption widening.

**What ships is synthetic.** The owner's real figures are unstated (§11 item 3). Every fixture
and every shipped file is labelled `SYNTHETIC FIXTURE` exactly as `data/routes/` and
`data/instruments/` are, and FR-025 makes that a requirement rather than a courtesy.

## D3 — An estimated basis reuses the provenance machinery; it does not get a second marking system

**Decision.** "Basis estimated" is a `SourceRef` with its own kind, carried in the lot's
`Provenance` and flowing through `merge` and `unverified_sources` exactly as an unverified
market value does. No new mark type, no second propagation path, no boolean on `Lot`.

**Rationale, and why this is the feature's spine.** FR-007 says an estimated basis must mark
every downstream figure *exactly as an unverified value does*. There are two ways to read
that: build a second marking system that behaves the same, or use the one that already
behaves that way. The second is the only one that stays true.

A parallel system would need its own `merge`, its own propagation through every transform,
and its own coverage in `tests/contract/test_provenance_propagation.py` — and the constitution
calls a transform that drops a mark a top-severity defect. One system, already tested end to
end, cannot drop a mark in a place the other system remembered.

**The consequence is the point.** A disposal of an estimated-basis lot produces a gain whose
provenance carries the estimate, so the **tax figure** carries it too. That is Principle I
turned on the owner's own declarations rather than only on market data — a guessed cost is a
guessed tax, and the output says so without anyone having to remember to say it.

**FR-008's reason field** rides on the `SourceRef`, which already carries a `source` string.
The reason the owner gives is what goes there.

## D4 — The solver is closed-form arithmetic over a stated convention, not a root finder

**Decision.** Three modes, each a direct formula over a monthly contribution schedule with a
stated compounding convention. No bisection, no `scipy`, no iteration to a tolerance.

**Rationale.** FR-014 requires each solved figure to reproduce hand-computed arithmetic within
the single project tolerance — which is only checkable if the engine and the hand computation
are evaluating the same closed form. An iterative solver would converge to *a* number and the
hand computation would check a different model, with the tolerance quietly absorbing the
difference.

**The conventions travel in the result** (FR-014's second half): when in the period a
contribution lands, and how growth compounds between contributions. Stated on the record, not
implicit in the code, so a reader checking the arithmetic knows what model to check against.

## D5 — The date mode returns two dates, and neither is rounded into the other

**Decision.** Solving for the date returns **both** the exact solution — the real-valued point
at which FR-013's round trip closes — and the first calendar date on which the target is
actually reached, each labelled as what it is.

**Rationale.** FR-015 in as many words, and the reason is worth restating: the exact solution
is what makes the three modes consistent, and the calendar date is what the owner can act on.
They are different facts. Reporting only the calendar date breaks FR-013; reporting only the
exact one answers a question nobody asked. Rounding one into the other silently is the
"nearest answer" this spec forbids twice.

## D6 — Consistency is a property over generated pairs, not a hand-picked round trip

**Decision.** FR-013's three-mode agreement is a Hypothesis property over generated
`(contribution, sum)` pairs, asserted with the imported tolerance.

**Rationale.** SC-001 says *across a generated body — not a single hand-picked pair*. A
round trip that closes for one example is a coincidence until it closes for a thousand, and
the failure mode here — a mode that defines its own epsilon, which FR-013 forbids explicitly —
shows up as a drift that only a range of magnitudes reveals.

## D7 — Every refusal is typed, and each names the missing thing

**Decision.** Six typed results, no exceptions: fewer than two variables declared; a missing
starting amount; a missing growth assumption; a non-base target currency; an unreachable
target; and a solved contribution at or below zero.

**Rationale.** FR-011, FR-012, FR-016, FR-019 and FR-020. Two of them deserve their shape
recorded:

- **A non-base currency is refused as *not yet modelled*, never as invalid** (FR-016). The
  goal record keeps its `currency` field rather than assuming hryvnia, and the message names
  the missing FX modelling. §4.7's point stands — a USD target and a UAH target are different
  goals under devaluation — so the declaration shape must not paint the future as closed.
  `features.toml` already records `multi-currency-goals` as owner-requested future work.
- **A contribution at or below zero is "no contribution needed", with the margin** (FR-020),
  never a negative number presented as an instruction. A negative contribution is arithmetically
  fine and operationally nonsense.

## D8 — Nominal, with a slot for real, and no opt-in to real-by-default

**Decision.** Every goal figure is labelled nominal, and the result carries a defined,
currently-unpopulated real slot in the shape 001's `HurdleRate.real` set.

**Rationale.** FR-017 and owner decision. The slot exists so feature 007 fills it without
changing the result's shape. **The owner explicitly did not opt into real terms becoming the
default** once inflation modelling exists — that would be a new decision, not an implication
of this one, and the docstring says so where a later contributor will read it.

## D9 — No seeds and no goals is a normal run, not a typed outcome

**Decision.** An empty `data/seeds/` or `data/goals/` produces a run with empty positions and
no goal section. It is **not** a refusal and **not** an empty-dimension outcome.

**Rationale.** FR-024. Contrast this deliberately with feature 003, where an empty registry
dimension *is* a typed refusal: there, an empty venue list and a mistyped path are
indistinguishable downstream and one of them is a mistake. Here they are distinguishable and
neither is a mistake — a person who has not declared a goal is an ordinary person, and
refusing to run for him would be the tool inventing a requirement. The rule generalises: refuse
emptiness where it cannot be told from an error, accept it where it can.

## D10 — The feasibility verdict says out loud that it is not a probability

**Decision.** The verdict carries a sentence stating it is deterministic under the stated
assumption. `core/results/goal.py` has no field for a probability.

**Rationale.** FR-021. §4.7's fourth row wants shortfall *probability* across scenarios, which
needs stochastic machinery this feature does not have. A bare "missed by 40 000 UAH" invites
being read as a likelihood; saying it is one path under one stated assumption costs a sentence
and forecloses the misreading.

## D11 — Where the code lives

**Decision.**

- `core/ledger/seeds.py` — declared seed lots to opening events.
- `core/goals/solve.py` — the three modes and the feasibility verdict.
- `core/results/goal.py` — `GoalOutcome`, the conventions record, and the six refusals.
- `data/seeds/owner-001.toml`, `data/goals/owner-001.toml` — synthetic, labelled.

**Rationale.** Seeds belong to the ledger because they *are* ledger citizens (D1). Goals are
not the decision layer: `core/decision/` is reserved for candidate generation and strategy
choice, and a goal solver is arithmetic over a contribution schedule — closer in kind to
`core/analysis/` than to a chooser. Its own small package keeps that distinction legible.
