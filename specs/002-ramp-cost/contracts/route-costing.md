# Contract: route costing

**Date**: 2026-08-22

The three functions this feature exposes and the guarantees they carry. No new plugin
interface — routes are data, and leg kinds are an algorithm registry (research.md D1).

---

## The signatures

```python
# --- the ONLY function that costs a route ---


def cost_one(
    path: FundingPath,
    amount: Money,
    *,
    routes: Mapping[str, Route],
    channels: Mapping[str, FxChannel],
    venues: Mapping[str, Venue],
    kinds: Mapping[str, ObservationKind],
    on_date: date,
    as_of: date,
) -> RampCost | RouteUnusable: ...


# ⚙ Corrected after implementation. This first listed `streams` and `capacity_used`, whose
#   types arrive with US2 (T024) and US3 (T029). Both are *feasibility* inputs producing
#   further `RouteUnusable` reasons, not a second arithmetic — and they must be added to
#   `cost_one` and `rank` together, or FR-029 acquires the second code path it forbids.


# --- events derived from a costed figure, never recomputed beside it ---


def execute(cost: RampCost, *, owner_id: str, sequence_from: int) -> tuple[Event, ...]: ...


# --- ranking; the recommendation is an index into what it ranked ---


def rank(
    paths: Sequence[FundingPath],
    amount: Money,
    *,
    routes: Mapping[str, Route],
    channels: Mapping[str, FxChannel],
    venues: Mapping[str, Venue],
    kinds: Mapping[str, ObservationKind],
    on_date: date,
    as_of: date,
) -> Ranking | NothingComparable: ...


# ⚙ The return type gained `NothingComparable` during implementation (research.md D13).
#   `Ranking.recommended` is an `int`, and there is no honest integer for "nothing was
#   comparable". A sentinel would be worse than the gap: `-1` indexes the last element, so a
#   ranking that recommended nothing would silently recommend something.


# ⚙ Spelled out after review. The first draft wrote `**costing_inputs: object`, which
#   would not survive mypy strict and hid every required input behind a bag — sloppy in a
#   document calling itself a contract. The inputs are exactly `cost_one`'s.


# --- leg kinds: an algorithm registry, not an interface ---

LegCostFn = Callable[[Leg, Money, FxChannel | None], LegOutcome]

LEG_COST_FNS: Final[Mapping[str, LegCostFn]] = {
    "transfer": transfer_cost,
    "fx": fx_cost,
    "trade": trade_cost,
    "withdrawal": withdrawal_cost,
}
```

`on_date` and `as_of` are separate arguments and mean different things: `on_date` is when
the money moves (it selects the regime and the month for the cap), `as_of` is when the
question is being asked (it decides staleness). Conflating them would make a projection into
the future report every input as stale.

## Guarantees

**One costing function.** `rank` is defined as costing each path with `cost_one` and sorting
the results. There is no second implementation, no fast path, no summary mode. FR-029.

**Ranking is lexicographic on `(round-trip cost, ceiling descending, latency)`**, with a
`None` ceiling sorting **first** (no declared cap is the least constrained a route can be),
never a composite score — required test **B12** forbids a non-standard score from driving the primary
ordering, and weighting hryvnia against days would be a preference rather than a fact. A
**tie is decided on round-trip cost alone**: two routes costing the same within the project
tolerance are reported tied even where their other keys differ.

**The recommendation is an index.** `Ranking.recommended` is an `int` into
`Ranking.costed`, and `recommended_cost(r)` returns `r.costed[r.recommended]`. The winner
is not compared against the alternatives — it **is** one of them, so SC-016 asserts
*identity* (`is`), not equality. Two numbers that agree today prove nothing; the same object
cannot disagree with itself.

**Purity.** `cost_one` is a pure function of its arguments. No clock — hence `as_of` and
`on_date` as parameters. No I/O. Called twice with equal arguments it returns equal results.

**Provenance and staleness reach the figure.** Every `Money` in a `RampCost` carries the
merged provenance of the declared values behind it, built through `money.*` — including
`money.scale_sourced` wherever a *declared rate or premium* is applied, so the figure admits
which observation it rests on. A route cost that did not name its premium's source would be
the exact defect FR-015 calls top-severity.

**Explicit failure.** A route that cannot carry the amount returns `RouteUnusable` — a
tagged-union member, not an exception — naming the binding constraint and the shortfall. It
never raises, never returns a zero cost, and is never silently dropped from a ranking.

**No clamping.** If fees exceed the amount, `arrived` goes to or below zero and is reported
as such. `fraction` may exceed `1.0`. Nothing is capped: predecessor defect B13 was exactly
a `max(gross − fee, 0)` that made money vanish with no diagnostic.

## `execute` derives; it does not recompute

`execute` walks a `RampCost`'s per-leg attribution and emits one fee event per fee-bearing
component. It takes the **costed figure**, not the route — so there is no arithmetic in it
that could drift from `cost_one`.

The invariant, asserted as a property over generated routes and amounts:

```
sum(fee events from execute(c)) == sum(c.one_way.components.values())
```

⚙ **Corrected after review.** This was written as `sent − arrived`, which does not typecheck
and could not: on an FX route `sent` is UAH and `arrived` is USD, and `money.sub` refuses a
mismatch by design (C5). Restating `arrived` in the sending currency would need a rate, and
the only rate available is a channel side — so "the difference" is not a well-defined
quantity without saying *which side at which reference*, which is precisely what FR-010
forbids leaving implicit.

The invariant is therefore stated over the **components**, which are all in the sending
currency by construction, and closes exactly. Two further clauses carry what the original
wording was reaching for: the arriving amount in the ledger equals `c.one_way.arrived`
currency and all, and `c.one_way.fraction` equals the component total over `sent`. **Cost-then-execute agreement is tested, not assumed** — this is what
allows the comparison to be pure while the execution is recorded (research.md D5).

## What implementations must NOT do

- **Cost a destination without a stream and a route.** There is no signature for it
  (FR-008). A contract test asserts no public function in `core.routes` accepts a
  destination alone.
- **Reverse an inbound route to get a round trip.** Exit routes are declared (FR-027). A
  route with no `partner_route` yields `ExitCostUnknown`, and the one-way figure may not be
  promoted into its place (FR-030).
- **Fold `disruption_probability` into a cost.** The chance a route stops working is a
  different claim from what it charges (FR-026). It rides beside the cost.
- **Compound `disruption_probability` across legs.** `RampCost.disruption_probability` is
  the **maximum** over the route's legs, documented as a *lower bound*. Compounding
  (`1 − Π(1−pᵢ)`) would smuggle in an unstated assumption that leg failures are independent,
  which for two legs at one bank they are not. A lower bound that says it is one is honest;
  a compounded figure that looks exact is not.
- **Report a round-trip latency as if it were one-way.** `RampCost.latency_days` is the sum
  over the **inbound** route's legs. A round-trip comparison sums both routes' latencies, and
  the two figures are separate fields — the same rule as cost (FR-002).
- **Use a mid-rate.** Every conversion picks a side of a two-sided channel quote, and the
  channel used appears in `channels_applied` (FR-010, FR-011).
- **Read a clock.** `datetime.now` is blocked in `core` by `.importlinter`, and the two dates
  that matter are parameters.
- **Branch on a route or venue id.** Behaviour comes from declared fields. A conditional on
  `route.id == "binance_p2p"` is a Principle II violation. Dispatch on `leg.kind` through
  the registry is the only branching permitted, and it selects an algorithm.

## Verified by

| Test | Asserts |
|---|---|
| `tests/worked_examples/test_ramp_p2p_premium.py` | **G2** — a +3 UAH premium at a stated reference reproduces the §4.3.1 percentage |
| `tests/worked_examples/test_two_streams.py` | **G1** — the same acquisition from two streams differs by exactly the hand-computed ramp cost; the USD path converts nothing |
| `tests/worked_examples/test_regime_transition.py` | **G4** — the route set switches on the transition date; cost drops by the hand-computed difference |
| `tests/invariants/test_cost_attribution.py` | Components sum to `sent − arrived`, over generated routes |
| `tests/invariants/test_cost_execute_agreement.py` | `execute`'s events sum to `cost_one`'s figure |
| `tests/invariants/test_no_silent_clamping.py` | **B13** — fees over the amount are reported, never clamped |
| `tests/contract/test_same_code_path.py` | **SC-016** — `recommended_cost(r) is r.costed[r.recommended]` |
| `tests/contract/test_per_destination_cost_unrepresentable.py` | **FR-008** — no public signature takes a destination alone |
| `tests/contract/test_route_data_only.py` | **SC-010** — a new provider, venue and corridor rank with zero source changes; and the four plugin interfaces are still four |
| `tests/contract/test_staleness.py` | **FR-028** — per-kind thresholds; a kind without one fails at load |
| `tests/unit/test_round_trip_types.py` | **G6/FR-030** — a one-way figure cannot occupy the round-trip slot; `ExitCostUnknown` names the missing partner |
