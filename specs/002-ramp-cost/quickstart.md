# Quickstart: verifying 002-ramp-cost

**Date**: 2026-08-22

How to confirm this feature works, ordered so problems surface soonest. No implementation
code — see [data-model.md](./data-model.md) and [contracts/](./contracts/) for shapes.

## Prerequisites

```bash
uv sync --all-extras --dev
```

Python 3.13. No network at any point; `tests/conftest.py` blocks sockets.

## The one-command check

```bash
uv run pytest -q
```

## 1. The number the feature exists for

```bash
uv run pytest -m worked_example -k "ramp or stream or regime" -v
```

The §4.3.1 finding, computed instead of asserted:

- **G2** — a +3 UAH premium against a stated reference reproduces `premium / reference`
  exactly, and the round-trip figure is the hand-computed two-way number.
- **G1** — the same USD acquisition funded from the UAH salary and from the USD contract
  income differs by **exactly** the hand-computed ramp cost, and the USD-funded path reports
  a conversion cost of exactly zero, not a small residual.
- **G4** — the route set switches on the regime transition date and round-trip cost drops by
  exactly the hand-computed difference.

If a cost is off by a consistent factor, suspect the percent-to-fraction conversion:
`loader._as_fraction` is the only division by 100 in the project, and doing it twice or not
at all are the two likeliest bugs in a new `_pct` field.

If the P2P figure is off by roughly a factor of the reference rate, suspect
`premium_per_unit` being treated as a fraction rather than as currency per unit.

## 2. The invariants

```bash
uv run pytest -m invariant -v
```

| Covers | Asserts |
|---|---|
| Cost attribution | Components sum to `sent − arrived` over generated routes. A leg cannot hide a cost in an unnamed component — the enumeration is closed. |
| Cost-then-execute | `execute`'s fee events sum to `cost_one`'s figure, and the ledger's arriving amount equals the `RampCost`'s. **This is what allows the comparison to be pure while execution is recorded.** |
| **B13** | Fees exceeding the amount are reported, never clamped. `fraction` may exceed 1.0 on a small amount with a fixed fee. |
| **C1–C6** | Still green — the capacity accumulator is new state in the fold and must not disturb cash, lot or basis conservation. |

## 3. The structural guarantees

```bash
uv run pytest -m contract -v
```

Four things here that no other gate can see:

- **FR-008** — no public function in `core.routes` accepts a destination without a stream
  and a route. A per-destination cost is not discouraged, it has no type. This is the single
  most important test in the feature: quoting one access cost for "buying dollars" hides the
  entire finding.
- **SC-016** — `recommended_cost(r) is r.costed[r.recommended]`. Asserted with `is`, not
  `==`: two numbers that agree today prove nothing about tomorrow.
- **SC-010** — a new provider, venue and corridor rank with zero source lines changed. The
  same test asserts the four plugin interfaces are still four, so a leg kind cannot drift
  into a fifth.
- **FR-028** — two values of the same retrieval date and different kinds go stale at
  different ages; a kind with no threshold fails at load.

## 4. Loud failure

```bash
uv run pytest -m contract -k declaration -v
uv run python scripts/check_provenance.py
```

The battery in `test_route_declaration_loading.py` has one case per row of the
enforced-rules table in `contracts/declaration-schema.md` — including the cross-file ones
pydantic cannot see: leg chaining, duplicate identity triples, dangling `partner_route`, an
exit route pointed at an inbound one, kind resolution.

`check_provenance.py` must report **zero errors**. Expect empty-`verified_on` warnings on
every route and channel value — that is the correct first-run state, since none of the
numbers in §11 item 1 has been observed yet.

## 5. Structural gates

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run lint-imports
```

`mypy` earns its keep twice here: assigning a `OneWayCost` into a round-trip slot is a type
error (FR-030), and so is constructing a `FundingPath` with a part missing (FR-008).
`lint-imports` confirms `core` still has no clock, no `pathlib`, no `pydantic` — if the
loader or a staleness helper drifted into `core`, this is where it shows.

## 6. Coverage

```bash
uv run pytest --cov --cov-report=term-missing
```

90% floor, blocking. Necessary, not sufficient — the eight required-test rows are the real
gate.

## Definition of done

- [ ] `uv run pytest` green with the coverage floor met
- [ ] `ruff`, `mypy`, `lint-imports`, `check_provenance.py` clean
- [ ] Eight rows flipped in `docs/REQUIRED_TESTS.md`: **G1–G6, F5, B13**
- [ ] `docs/METHODOLOGY.md` extended: the premium-to-percentage formula, round-trip
      composition from a declared exit route, the two-sided channel convention, and the
      staleness rule
- [ ] Feature 001's declarations migrated to carry a `kind`
- [ ] Manual review of provenance propagation and tolerance usage — no gate sees either

## What this feature does not tell you

- **It costs the ramp, not the investment.** The destination is a currency balance at a
  venue. What you buy once the money is there, and what it earns, is a later feature.
- **A destination with no declared exit route has no round-trip figure at all**, and is
  reported as *exit cost unknown* rather than compared. That is the decision working, not a
  gap: an asset whose exit nobody has costed is not comparison-ready.
- **Every route number here is unverified.** Monobank's card markup and monthly limit,
  TransferGo's quote, Coinbase's withdrawal fees, the Binance fee tier — none is observed
  (§11 item 1). The marks propagate and the figures say so.
- **The tax asymmetry is absent on purpose.** A position flat in USD across a devaluation
  posting a taxable UAH gain — required test **F1**, which the engine charter calls the
  reason the rewrite exists — needs a taxable foreign instrument and dated official rates.
  This feature builds the channels that make it reachable and stops there.
