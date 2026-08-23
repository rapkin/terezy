# Phase 0 research: Inzhur instruments and dated tax schedules

**Feature**: `006-inzhur-instruments` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

All clarifications were resolved by the owner on 2026-08-22, and the product terms were
researched from the funds' primary documents before this plan existed. Nothing here is a
`NEEDS CLARIFICATION`. D2 is the decision that keeps this feature buildable without any
agent inventing a legal fact, and it is the one to read first.

---

## D1 — The dated schedule replaces the scalar; it does not sit beside it

**Decision.** `TaxClass.rates: tuple[RateEntry, ...]` where
`RateEntry(effective_from, pit_rate, levy_rate, provenance)`. The scalar
`pit_rate_pct` / `levy_rate_pct` pair is **removed**, not deprecated, and
`data/tax/ua.toml` is migrated in the same change.

**Rationale.** FR-010 and required test E10. Keeping both shapes would mean two code paths
reading a rate, and the older one would keep working — so nothing would force the migration
and the scalar would outlive the feature that replaced it. `data/README.md` rule 3 and
`SIMULATOR_SPEC.md` §4.5.1 have wanted schedules since before feature 001; this is a debt
being paid, and a debt paid halfway is a second debt.

**Every entry carries its own provenance**, not one mark for the class. A rate that changed
in December 2024 was cited by a different source than the rate before it, and collapsing
them would attach one verification date to two separate observations.

## D2 — An effective date is a cited legal fact; the typed refusal is what makes an unknown one safe

**Decision.** Each `RateEntry.effective_from` is exactly the date its citation attests. Where
a source establishes the current rate but not the date the older one began, **no earlier
entry is invented** — the schedule simply starts at the attested date, and FR-012's typed
error covers every event before it.

**Rationale, and why this is load-bearing.** The migration invites exactly one catastrophic
shortcut: giving the exempt class an `effective_from` of `1900-01-01`, or the date the file
was written, so that "everything just works". That would be an agent inventing a legal fact
— the single thing `CLAUDE.md` and the constitution forbid in the same words — and it would
be invisible, because every test would pass.

FR-012 exists precisely so the honest schedule is also the working one: declare what the
citation supports, and an event dated earlier produces a typed error naming the class and
the date rather than a silently defaulted rate. An owner who then needs an older event goes
and finds the citation. **A schedule that never refuses is a schedule someone back-dated.**

**Consequence to check, not assume:** feature 001's golden run is dated 2026-01-15 to
2028-01-31, and its exempt class must keep charging zero across it. If the attested
effective date for the exempt class is later than 2026-01-15, the migration breaks 001's
golden — and the answer is a citation for the earlier entry, never a widened date. Verify
this before writing the migration, and if no citation can be found, **stop and report it**:
it is an owner question, not an implementer's judgement call.

## D3 — Rate lookup is a pure fold over a sorted tuple

**Decision.** `rate_on(tax_class, on_date)` returns the entry with the latest
`effective_from` on or before `on_date`, or a typed `RateUndeclaredBefore` naming the class
and the date. Entries are sorted and validated non-overlapping at load.

**Rationale.** FR-011. No clock in the core, and the "in force from its effective date
inclusive" boundary is stated once here and tested at the boundary itself rather than
inferred at each call site. Sorting and overlap checking belong at load because that is where
the file can be named.

## D4 — Two tax classes on one instrument exercises 001's machinery; it does not extend it

**Decision.** `InstrumentDeclaration.tax_classes: dict[str, str]` — event kind to class id —
is used as it stands. The projection result gains **per-class subtotals**.

**Rationale.** FR-006's own ⚙ says 001 specified this mapping plural for exactly this case.
The new work is FR-007's reporting requirement: the output must show which class charged
what, or the two-class split is invisible to the reader even when it is correct in the
ledger. That is a result-shape change, not an engine change.

## D5 — Liquidity mode is a required parameter with no default

**Decision.** `LiquidityMode = Literal["practice", "legal"]`, required and keyword-only on
every projection entry point. No default, no inference.

**Rationale.** FR-016 requires every projection to state which mode it assumed, and both to
be projectable for one request so their difference is a visible number. A default would make
the more optimistic mode the silent one — the practice mode is a *revocable company
practice* with an empty verification date, and defaulting to it would quietly promise
same-day NAV liquidity the регламент does not owe. Same discipline as feature 005's required
`as_of`: an unstated assumption is indistinguishable from a checked one.

## D6 — A refused redemption leaves the holding open

**Decision.** Under legal terms with the discretionary buyback declared unavailable, a
redemption request returns a typed refusal naming that no buyback obligation exists before
the declared termination date, and names the termination payout as the next guaranteed exit.
The lot is untouched.

**Rationale.** FR-017. The failure mode this forecloses is the tempting one: executing the
exit anyway "at the legal discount" because a number was wanted. Nothing is silently
executed, adjusted or deferred — and because the holding stays open, a later projection over
the same ledger is still correct.

## D7 — A pegged amount is not money until a declared rate sizes it

**Decision.** The REIT's distribution terms carry a `Peg(currency, cap)` and a
USD-equivalent rate. Sizing requires an explicitly declared `ExchangeRateAssumption`; absent
one, the projection returns a typed degraded result naming that exact missing input. Where
the assumed rate exceeds the declared cap, the payment is sized **at the cap** and the output
says the cap bound.

**Rationale.** FR-020 to FR-022, and owner decision A. The peg is a declared term, not a
conversion licence: a USD-equivalent figure is never itself treated as `Money`, so the type
system refuses the conflation rather than a reviewer catching it. Every output for the
instrument states the peg and the cap, because the whole point of decision A is that the
currency exposure stays visible instead of being lost in a hryvnia figure.

## D8 — A value that was NOT FOUND enters as a question, never as a number

**Decision.** The declaration files carry `[[verification_task]]` entries — a stated open
question with the document searched and the date searched — for the values the primary
documents do not give: the REIT's rate-fixing rule, its current cap values, and the possible
ІНЖУР КЕПІТАЛ commission. Any projection that would need one returns a typed refusal naming
the task.

**Rationale.** FR-027 and FR-028 say these must be recorded as owner-verification tasks and
never invented. A comment would not do it: a comment cannot be reached from a projection, so
the projection would have to substitute something. A declared task can be named in the
refusal, which turns "I cannot compute this" into "go read this document" — the same move
feature 003 makes with a missing route declaration.

**The cap's history is different and enters as data**: 2023 at 37.49 and 2024 at 41.24, with
the +10%/yr ladder as pre-2025 secondary evidence, declared-but-unverified. Known-and-weak is
not the same as absent, and flattening the two would lose real information.

## D9 — Fees are provenance context for the declared yield, not modelled flows

**Decision.** No management-fee accrual, no performance-fee computation, no coupon
reinvestment of the underlying bonds. The researched fee facts live in the declaration as
recorded context attached to the declared net yield. **No field exists for a computed fee.**

**Rationale.** Owner decision B, FR-023, FR-028. Modelling fund-internal profitability would
mean inventing the fund's own books from the outside — every term would be an assumption
wearing the shape of a computation. The declared net yield is what the fund states, marked
fund-stated and unverified, and the access cost this feature models carefully is the
entry/exit spread, which the owner actually pays. The structural absence is the guarantee:
a later contributor cannot "just add" a fee accrual to a record with nowhere to put it.

## D10 — Assumption-driven means the metric is refused, not computed and caveated

**Decision.** Both funds are declared assumption-driven. `volatility`, `sharpe`, `sortino`
and every other statistical metric return a typed refusal naming the instrument and the
reason. There is no field on a fund result where such a number could sit.

**Rationale.** FR-004, FR-005, SC-009 and constitution Principle I in its most literal form:
*refuse to emit a Sharpe ratio rather than computing one from invented data*. A caveated
number gets copied without its caveat; a refusal cannot be.

## D11 — A range is reported as a range, or as an explicitly labelled chosen point

**Decision.** MilTech's 25–29% simple annual enters as a range. A projection either reports
the outcome as a range, or takes an explicitly declared point labelled as the owner's
assumption. Silently choosing the midpoint, the low end or the high end is refused.

**Rationale.** FR-023, SC-013, and Principle I's ordering — dominance, then distribution,
then break-even, then point estimate. A range that survives to the output is more useful than
a false point, and the midpoint is the most seductive invented number in the feature because
it looks like arithmetic.

## D12 — Where the code lives

**Decision.**

- `core/tax/schedule.py` — `RateEntry`, `rate_on`, `RateUndeclaredBefore`.
- `core/tax/flat_rate.py` — migrated to read the schedule; the `TaxRule` interface is
  unchanged, so no fifth plugin interface and no amendment.
- `core/instruments/fund.py` — the collective-investment fund beside `fixed_income.py`,
  implementing the existing `Instrument` interface.
- `core/results/fund.py` — the projection result, per-class subtotals, the peg statement,
  the spread lines, and the typed refusals.
- `data/instruments/inzhur_reit.toml`, `inzhur_miltech.toml`, and a third **synthetic** fund
  with different terms for SC-010.
- `data/tax/ua.toml` — migrated to schedules, plus the two new classes.

**Rationale.** Every one of these is an existing package or an existing directory. The
feature adds two instruments and one rate shape; if it needed a new layer, the plugin
boundary 001 drew would have been wrong.

## D13 — 001's golden is evidence, and only if the dates were chosen first

**Decision (rewritten during implementation, 2026-08-23; the original wording is quoted
below because the reason for the rewrite is worth more than the rule).**
`tests/golden/ovdp_synthetic_a.golden.txt` must show **no change to any computed figure**
after the schedule migration: every figure, every schedule row, every tax charge, the whole
folded ledger and the projection digest identical. Its `== inputs ==` block **will** change,
because it records the digest of every declaration file the run was fed and the migration
edits one of them — that is the artefact working, not the migration leaking.

**And the golden is evidence only in one direction.** It can tell you a schema change moved
no arithmetic. It cannot tell you a *date* is right, and it must never be consulted while
choosing one. The order is: settle every `effective_from` on its own citation (D2), then run
the golden and read what it says.

**The original wording, and why it was wrong.** D13 said *"001's golden must not move, and
that is the migration's proof."* Read as written that makes a green golden a **constraint on
the input** rather than a report on the output — and it worked exactly that way. Faced with
two attested dates for the exempt class, the implementer took the earlier one and recorded
the tiebreaker as "the later one would break 001's golden". The date happened to be
defensible; the reasoning was circular, and a rule that can produce a circular justification
will eventually produce a wrong date with a green suite behind it.

The failure is instructive because nothing caught it: no gate can see a date chosen for the
wrong reason, which is the same blind spot D2 exists to cover from the other side. The
protection is procedural — dates first, artefact second — and it is now stated here rather
than left to whoever reads the golden next.

See D2 for what a legitimate date looks like, and the implementation notes in `tasks.md`
for the citations actually used.
