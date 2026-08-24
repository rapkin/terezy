# terezy

Decision support for a UAH-income investor.

> **"I have a monthly surplus in UAH. Where should the next hryvnia go, and how much
> will I actually keep — after the FX spread to get it there, the fees, the taxes, the
> lock-ups, and inflation?"**

Not "which ticker had the best 2018–2025". An investment option is a **tuple**, and two
options with identical gross returns can differ by several percent a year purely in the
terms that are not the instrument:

```
(instrument) × (funding route in) × (tax treatment) × (exit route out) × (risk class)
```

Modelling all five is the product. The largest single number in the owner's real
decision is not the choice of ETF — it is that the domestic route costs **0%** against
a crypto ramp of **5–10% one way**, and that OVDP is taxed at **0%** against **23%**
elsewhere.

**Status:** two features in. **001 — the OVDP hurdle rate** is complete: an event-sourced
ledger with tax lots, currency-tagged money whose provenance propagates through every
derivation, declared instruments and tax classes, and a hand-verified after-tax return.
**002 — the ramp** is complete: income streams, routes as chains of legs, two-sided FX
channels, monthly limits that belong to a shared rail, war-end regimes kept apart from
observed facts, and the number the whole product turns on — **the same acquisition costs
6.67% funded from the hryvnia salary and exactly 0% funded from the dollar contract.**

The number the tool currently produces is marked **unverified**, and that is the honest
state: the OVDP yield it rests on is an owner-reported observation nobody has checked
against a primary source. The arithmetic is verified; the input is not, and the output
says so.

## What it is, and what it is not

Two halves, deliberately separated:

- **The framework is data.** Instruments, routes, tax packs, scenarios and strategies
  are declarative, versioned, sourced files with four narrow plugin interfaces behind
  them. Adding an instrument, a venue, a tax regime or a country must not require
  touching the engine.
- **The decision layer is search and comparison.** It generates candidate strategies,
  prunes the infeasible ones, scores every survivor under *every* scenario, and returns
  a small shortlist with the trade-offs named.

And the honest bound: **it does not produce *the* optimal strategy.** It produces a
defensible shortlist under objectives and constraints the owner states, shows which
assumption decides between them, reports an indifference band rather than a false
optimum, and says plainly when nothing beats the simple option.

It is **not advice**, not a forecaster, not a trading system, and not a tax filing
tool. Every rate is user-verifiable and user-overridable, and every unverified value
renders marked.

## Documents

| Document | Role |
|---|---|
| [`docs/DIRECTION.md`](docs/DIRECTION.md) | **Where this is going.** The one idea, what it will refuse to become, what is worth borrowing, and what nobody has decided yet. |
| [`.specify/memory/constitution.md`](.specify/memory/constitution.md) | **Governance.** Seven principles, the architecture constraints, and the quality gates. Supersedes other conventions in this repo. |
| [`docs/reference/SIMULATOR_SPEC.md`](docs/reference/SIMULATOR_SPEC.md) | **Product specification.** What the tool is for, what it models, what it must answer. |
| [`docs/reference/REWRITE_BRIEF.md`](docs/reference/REWRITE_BRIEF.md) | **Engine charter and audit** of the predecessor: 12 behaviours to preserve, 18 confirmed defects, the ledger design. |
| [`docs/reference/METHODOLOGY.md`](docs/reference/METHODOLOGY.md) | Formulas as implemented in the predecessor. Port forward and extend. |
| [`docs/reference/LEGACY_REVIEW.md`](docs/reference/LEGACY_REVIEW.md) | The 12 original financial-math bugs — the list of mistakes not to repeat. |
| [`docs/REQUIRED_TESTS.md`](docs/REQUIRED_TESTS.md) | **The standing definition of done.** Every required test, with its status. |
| [`data/README.md`](data/README.md) | The framework surface and the rules that govern every data file. |

`docs/reference/` is input material, carried over from the predecessor project and
treated as read-only. New documentation lives directly in `docs/`.

## Architecture

```
src/terezy/
  core/          pure, deterministic — no I/O, no network, no rendering, no formatting
    instruments/   the Instrument interface and the registry's mechanics
    routes/        funding and exit routes, legs, caps, regimes
    ledger/        event-sourced ledger: events, tax lots, cash accounts, invariants
    tax/           the tax engine and the TaxRule interface
    metrics/       return and risk metrics
    analysis/      projection, Monte Carlo, replay, robustness, attribution
    decision/      candidates, feasibility, objectives, constraints, the shortlist
  data/          providers, caching with provenance, offline snapshot, manifests
  api/           orchestration and the typed result schema
  cli/           a thin, scriptable client over the API
data/            the framework surface — curated, sourced, version-controlled
```

Dependencies point one way only — `cli → api → data → core` — and that is enforced
mechanically by [`.importlinter`](.importlinter) in CI, not by convention. The core may
not import network, filesystem, serialisation, framework or nondeterminism modules;
seeds are explicit and recorded in each run's manifest.

Per owner decision **D-B**, the web UI framework is deliberately unchosen until the
result schema has stabilised against real output. The API is designed as the UI's only
contract so that choice stays cheap.

## Development

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
uv sync --all-extras --dev     # install
uv run pytest                  # tests
uv run pytest --cov            # tests with the coverage floor enforced
uv run ruff check .            # lint
uv run ruff format .           # format
uv run mypy                    # strict typing
uv run lint-imports            # architecture boundaries
uv run python scripts/check_provenance.py    # citations on every curated value
```

All of the above are **blocking** gates in CI. Tests never reach the network: the suite
runs against the checked-in offline snapshot, and `tests/conftest.py` fails loudly on
any socket attempt.

### Working on this project

Work flows through [Spec Kit](https://github.com/github/spec-kit):

```
/speckit-specify   →  /speckit-clarify  →  /speckit-plan  →  /speckit-tasks  →  /speckit-implement
```

A feature without a specification in `specs/` does not get implemented. Ambiguity is
resolved by clarification before planning — and never by guessing, least of all for a
legal or tax value, which must come from a cited source.

Read `.specify/memory/constitution.md` first. It is short, and it is binding.

## Privacy

This system holds a complete picture of one person's finances. No third-party
analytics, no CDN calls, no telemetry, no secrets in the repository. Authentication
must exist **before** the application listens on any interface other than loopback —
that is a blocking release gate, not a backlog item.
