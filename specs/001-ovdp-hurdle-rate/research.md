# Phase 0 research: 001-ovdp-hurdle-rate

**Date**: 2026-08-21

Seven decisions the plan rests on. Each records what was chosen, why, and what was
rejected. No `NEEDS CLARIFICATION` remains: the spec's two clarifications were resolved
before planning, and the questions below are design questions, not owner questions.

---

## D1 — Where the declaration loader lives

**Decision**: The loader lives in `terezy.data.declarations`, never in `terezy.core`.
The split is:

- `core` defines the **domain types** — bond terms, tax classes, provenance, money —
  as plain frozen dataclasses. It knows nothing about files, TOML, or validation
  libraries.
- `data` **reads and validates** files and constructs those core types, raising a typed
  error naming file and field on any problem.

**Rationale**: `.importlinter` forbids `core` from importing `pathlib`, `tomllib`,
`json` and friends, and the layer contract is `cli → api → data → core`, so `data` may
import `core` but not the reverse. Loading is by definition I/O, so it sits in `data`.
The valuable consequence is that the core's bond mathematics can be tested by
constructing terms directly, with no file on disk anywhere near the arithmetic — which
is what makes the D1 worked example a check of the engine rather than of the loader.

**Alternatives rejected**:

- *Loader in `core` with injected file contents.* Would satisfy the letter of the import
  contract by passing a string in, and violate its intent: validation error messages
  naming files are a presentation concern, and the core would grow a TOML schema.
- *A fifth layer for the registry.* Constitution Principle II caps the plugin interfaces
  at four; adding a layer is not forbidden but it is unearned here — `data` is exactly
  the right home and is already described as owning curated files.

## D2 — How provenance propagates

**Decision**: Provenance rides **inside the `Money` record**, as a frozenset-backed
`Provenance` record, and the combining functions in the `money` module union the
operands' provenance. `Provenance` is excluded from equality comparison
(`field(compare=False)`), so it never affects whether two amounts are equal.

Combination goes through free functions — `money.add`, `money.sub`, `money.scale` — not
methods and not operator dunders (owner decision D-E, functional style). That makes the
union site singular and greppable: there is exactly one `add`, and a reviewer checking
FR-015 reads one function rather than auditing every call site.

```
money.add(
    Money(1000.0, UAH, prov={ovdp_terms}),
    Money( 155.0, UAH, prov={ovdp_terms, curve}),
) -> Money(1155.0, UAH, prov={ovdp_terms, curve})
```

A figure is marked unverified when any source in its provenance set has an empty
`verified_on`. Because union happens inside the module's combining functions — the only
way to combine money — **there is no way to add two amounts and forget to carry the
mark**. The failure mode FR-015 calls top-severity becomes structurally unreachable
rather than a thing to remember.

The one remaining hole is direct construction: `Money(...)` is callable anywhere, so code
could build an amount with `Provenance.EMPTY` and launder an unverified input. That is
guarded by a test which scans for `Money(` outside its own module and the loader, plus
manual review — the gates cannot see it.

**Rationale**: FR-015 is the requirement most likely to be violated silently, by any
contributor including a subagent. Making it a property of the type rather than a
discipline is the only mechanism that survives delegation. The cost is real and is
recorded in the plan's Complexity Tracking.

**Alternatives rejected**:

- *Provenance on schedule rows, not on `Money`.* Lighter, but a derived scalar — the
  return figure, a total — is computed from rows and would silently lose the mark unless
  every aggregation remembered to union. That is precisely the defect being guarded
  against.
- *A generic `Sourced[T]` wrapper.* Propagation stays manual: every operation has to
  unwrap and rewrap, and `.value` becomes an easy escape hatch. Would need a lint rule to
  police, which is weaker than making it impossible.
- *Operator dunders (`__add__`) for ergonomics.* Rejected under D-E. They are marginally
  nicer to read but they are methods on a record, and they scatter the union across
  several dunders instead of concentrating it in one named function.
- *Run-scoped taint only* ("if any input to this run is unverified, mark the whole
  result"). Unfalsifiable and cheap, but useless: it cannot tell the owner *which*
  figure rests on an unverified input, so every figure would be marked forever and the
  mark would stop meaning anything.

## D3 — Whether events or the schedule is the source of truth

**Decision**: **Both, in one direction.** The instrument computes its contractual
schedule in closed form from its declared terms — a pure function, no ledger involved.
The engine then **applies that schedule as events** into the ledger, and every reported
figure is derived from the ledger, never from the schedule directly.

```
declared terms  --(closed form)-->  schedule  --(applied)-->  events  -->  ledger  -->  figures
```

**Rationale**: This satisfies two requirements that pull in opposite directions. D1
wants closed-form arithmetic a human can check on paper, which argues for computing the
schedule directly. FR-008 and C6 want every figure traceable to transaction records,
which argues for events being authoritative. Generating the schedule and then applying
it gives both: the schedule is checkable in isolation, and nothing reaches the output
except through the ledger.

It also matches the `Instrument.events(...)` shape the product spec already fixed in
§4.1, so the interface does not have to be reinvented for market instruments later.

**Alternatives rejected**:

- *Schedule is the output; ledger is decorative.* Fastest, and it breaks C1/C6 —
  cash conservation cannot be asserted against a schedule that never touches an account.
- *Events only, no schedule object.* The bond's arithmetic would be entangled with
  ledger folding, making the hand-computed check awkward and the closed form
  non-inspectable.

## D4 — Representing nominal-only so the real slot cannot be misfilled

**Decision**: **Distinct types, not `Optional[float]`.** `NominalRate` and `RealRate`
are separate frozen types, and the result holds:

```
nominal: NominalRate
real:    RealRate | RealTermsUnavailable
```

`RealTermsUnavailable` is a typed value carrying its reason
(`"inflation is not modelled in feature 001"`), which also satisfies FR-017's rule that
every degraded outcome carries a reason.

**Rationale**: With `real: float | None`, assigning the nominal figure into the real slot
is a one-character mistake that type checking cannot see, and `None` reads
ambiguously as "zero", "missing" or "not applicable". With distinct types, assigning
nominal into real is a **mypy strict error** — the guard is the type checker, not a test
someone might not write. SC-011 then asserts the runtime shape as a second line of
defence.

**Alternatives rejected**:

- *`Optional[float]` with a naming convention.* No mechanical guard at all.
- *A single `Rate` type with a `basis: Literal["nominal", "real"]` tag.* Better than
  `Optional`, but a mistyped tag is still just a wrong string, and mypy cannot catch a
  runtime-assigned literal.

## D5 — How determinism is verified, given float64 money

**Decision**: `core.ledger.canonical` provides pure, structural free functions —
`canonical.of_event(e)`, `canonical.of_result(r)` — returning nested tuples of primitives
with amounts rendered by **`float.hex()`**. The **digest** (SHA-256 over a canonical encoding of that tuple)
lives in `terezy.data.manifest`, not in `core`.

**Rationale**, three parts:

1. **`float.hex()` rather than `repr` or rounding.** It is exact and round-trippable, so
   the digest asserts bit-identity of every amount. This is deliberately *stricter* than
   the project tolerance: the tolerance exists because hand-computed arithmetic and float
   arithmetic differ, whereas determinism means the same code on the same inputs must
   produce the same bits. Conflating the two would let a genuine nondeterminism hide
   inside the tolerance band.
2. **Bit-identity is achievable here.** The only threat to float reproducibility is
   reduction order under threaded BLAS. This feature does plain Python arithmetic over
   tens of values — no numpy reductions, no BLAS. When the vectorized fast path arrives
   the digest may need revisiting, and that is noted rather than pre-solved.
3. **The digest lives outside `core`** because hashing requires serialisation, and
   `core` is barred from serialisation modules — `hashlib` is now explicitly on that list.
   Keeping the canonical functions structural (tuples of primitives, no bytes, no
   encoding) leaves the purity contract intact while still making determinism a
   core-defined property.

**Alternatives rejected**:

- *Digest of a rounded decimal rendering.* Would mask nondeterminism smaller than the
  rounding unit — the exact bug the check exists to find.
- *Compare full result objects for equality instead of digesting.* Works for a single
  run pair but gives nothing to record in the manifest for later comparison, which
  FR-012 wants.
- *`hashlib` inside `core`.* Importing it there would argue with the spirit of
  Principle III to save an indirection. `hashlib` and `pydantic` were added to the core's
  forbidden list in `.importlinter` instead, alongside `abc`.

## D6 — pydantic or hand-rolled validation

**Decision**: **pydantic v2**, in `data` only, configured against its own defaults:

```
model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
```

with **no field defaults anywhere**, plus a thin adapter that converts `ValidationError`
into the project's own error type carrying the file path and the field path. Two checks
pydantic structurally cannot do are a separate resolution pass: **duplicate identifiers
across files** and **references to an undeclared tax class**.

**Rationale**: the worry about pydantic is coercion — `"15.5"` quietly becoming `15.5`,
or a missing field quietly becoming a default. Both are configuration, not fate:
`strict=True` disables coercion, and defaults only exist if you write them. What is left
is pydantic's real strength, which happens to be exactly FR-016: `extra="forbid"` *is*
the unrecognised-field rule, and `ValidationError` already carries precise field
locations, which is the part hand-rolling does worst. It is also already a dependency, so
this adds nothing to install.

The adapter is not optional. Raw `ValidationError` is a pydantic concept leaking through
the boundary; the loader's contract is a project error naming file and field.

**Alternatives rejected**:

- *Hand-rolled validation.* Full control, and considerably more code whose weakest point
  would be the error messages — the one thing FR-016 actually specifies.
- *pydantic with defaults for convenience.* Directly violates FR-016's "a default value
  MUST NOT be substituted for anything absent".
- *pydantic types in `core`.* Purity-wise harmless, but it would put a validation
  framework in the domain layer and make the core's types answerable to a library's
  release cycle. Core uses plain frozen dataclasses.

## D7 — Functional style, and what it changes

**Decision** (owner decision D-E, added to the constitution as v1.1.0 mid-planning): free
functions over immutable records. No inheritance, no ABCs, no `Protocol` classes carrying
methods, no operator dunders. Tagged unions for domain outcomes, dispatched with `match`.
Registries are mappings of functions.

**What this changed in the design above, and what it did not.** All six decisions survive
intact — none of them depended on objects. What changed is how each is *expressed*:

| Was | Becomes |
|---|---|
| `Instrument` / `TaxRule` as `Protocol` classes with methods | Named function signatures (`EventsFn`, `ChargeFn`), grouped in a frozen record of functions where several travel together, dispatched from a `dict` registry keyed by instrument class |
| `Money.__add__` unioning provenance | `money.add(a, b)` — one named function, the single union site |
| `event.canonical_tuple()` | `canonical.of_event(event)` |
| Exception hierarchy for failures | Tagged union of frozen records (`InfeasiblePurchase | InconsistentTerms | ...`), matched exhaustively |

**Rationale**: the owner's stated preference, and it happens to reinforce Principle III
rather than fight it. A free function over a frozen record is pure by construction and
needs no reasoning about instance state; the purity contract in `.importlinter` and this
style are pulling the same direction. It also improves the FR-015 guard specifically:
concentrating provenance union in one named function is easier to review than auditing
several dunders.

**One place it costs something.** Exhaustive dispatch over a tagged union needs `match`
plus a `case _:` arm that mypy proves unreachable, which is more ceremony than a virtual
method call. That ceremony is the point: adding a variant then produces a type error at
every site that must handle it, instead of silently inheriting a base-class default —
which is exactly the silent-default failure mode Principle II and FR-016 exist to
prevent.

**Alternatives rejected**:

- *`Protocol` without methods, holding only callables as attributes.* Nearly equivalent,
  and a frozen dataclass of functions says the same thing with less indirection.
- *`functools.singledispatch`.* Idiomatic and functional, but it dispatches on runtime
  type and hides the set of handled cases, so a missing case is a runtime error rather
  than a mypy error. Explicit `match` keeps exhaustiveness checkable.
- *Keeping dunders as a "thin convenience" over the free functions.* Two ways to do the
  same thing, and the convenient one bypasses the reviewable one.

---

## A boundary worth naming explicitly

Day-count conventions, coupon periodicities and business-day rules are **named in data
and implemented in code**: the data says `day_count = "act/365"`, and the engine holds a
registry of the conventions it implements. An unrecognised name fails loudly (FR-021).

This is not a Principle II violation, and it is worth stating because it looks like one.
Principle II requires that adding an **instrument, venue, tax regime or jurisdiction** be
data-only. A day-count convention is none of those four — it is an algorithm, and adding
an algorithm is code by nature. What must stay data-only is the *choice* of convention
per issue, which it is: a second OVDP issue using a different convention is a new file
and no engine edit (SC-012).
