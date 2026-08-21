# `data/` — the framework surface

Constitution **Principle II (Framework, Not Script)**: adding an instrument, a venue,
a route, a tax regime or a jurisdiction must be a **data-only change**. If it requires
an engine edit, the abstraction is wrong — and `H1` in `docs/REQUIRED_TESTS.md` is the
executable test of exactly that.

Everything here is versioned, sourced, dated, and reviewed in git like code
(`docs/reference/SIMULATOR_SPEC.md` §4.10.1, §7).

| Directory | Holds |
|---|---|
| `instruments/` | The instrument registry — five classes (spec §3). `instruments/nav/` holds low-frequency dated NAV and distribution series. |
| `routes/` | Funding and exit routes: legs, caps, regimes, one entry per `(provider × currency path × venue)` (spec §4.3). |
| `tax/` | Jurisdiction rule packs with dated rate schedules (spec §4.5). |
| `scenarios/` | FX paths, discrete events, regime transitions, risk assumptions (spec §4.3.4, §4.6). |
| `strategies/` | Named allocations, per income stream (spec §5.1). |
| `objectives/` | Objective + constraint sets (spec §4.10.3–4.10.4). |

## Rules that apply to every file here

1. **Loud failure.** A malformed or unknown field fails at load time, naming the file
   and the field. Silent defaulting is a defect (`H2`).
2. **Provenance on every observed value.** `value`, `source`, `retrieved_on`,
   `verified_on`. An empty `verified_on` is permitted and expected — it must render
   visibly marked, and the mark propagates to everything derived from it. Omitting the
   key is *not* permitted. Enforced by `scripts/check_provenance.py` in CI.
3. **Dated schedules, not constants.** Every rate accepts a dated schedule, so a
   legislated change is modelled rather than requiring a rebuild (spec §4.5.1).
4. **No legal value from memory.** Tax and legal values come from a cited public
   source, entered as data. Not from an implementer, and not from an agent.
5. **Curated vs per-user.** Everything in this directory is curated and shared.
   Per-user data — holdings, goals, assumptions, results — lives outside it and is
   gitignored (`data/user/`). Principle VII depends on that boundary.

## Assumptions are not observations

`scenarios/` and `objectives/` are exempt from the citation requirement by design:
they hold the owner's own stated beliefs — a probability of sovereign restructuring, a
war-end date, a MilTech loss probability. An assumption needs a **label and a visible
consequence**, not a source. Never present one as though it were an observation.
