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
| `routes/` | Funding and exit routes, **declared in pairs**: legs, caps, rails, one entry per `(provider × currency path × venue)` (spec §4.3). |
| `channels/` | Two-sided FX quotes per named channel — official, interbank, bank non-cash, cash desk, card, peer-to-peer (spec §4.3.1, FR-010). |
| `streams/` | **Per-owner** income streams: currency, amount, cadence, arrival venue, indexation (spec §4.2). |
| `spendable/` | **Per-owner** endpoints where money counts as having come back out: base currency only, at the venues the owner actually spends from (003 FR-004). |
| `composition/` | **Per-owner** reach policy: how many declared routes may be chained into one candidate. No default — a missing bound fails at load (004 FR-006). |
| `seeds/` | **Per-owner** opening lots: what is already held, as units acquired on a date at a price, with the basis declared `known` or `estimated` (008 §4.8). |
| `goals/` | **Per-owner** targets: any two of a monthly contribution, a target sum and a target date, in the base currency (008 §4.7). |
| `tax/` | Jurisdiction rule packs with dated rate schedules (spec §4.5). |
| `scenarios/` | FX paths, discrete events, regime transitions, risk assumptions (spec §4.3.4, §4.6). |
| `strategies/` | Named allocations, per income stream (spec §5.1). |
| `objectives/` | Objective + constraint sets (spec §4.10.3–4.10.4). |

Two files sit at the root rather than in a directory, because each is a single flat list
the whole repository refers to:

| File | Holds |
|---|---|
| `observation_kinds.toml` | One staleness threshold per kind of observed value, with the reason for it. No default: a kind without `staleness_days` fails at load, and so does a sourced table naming a kind that is not declared here (FR-028). |
| `venues.toml` | Where money can sit, and which currencies each place can hold. A leg moving a currency its venue cannot hold is a load-time failure naming the file and the leg index. |

## Rules that apply to every file here

1. **Loud failure.** A malformed or unknown field fails at load time, naming the file
   and the field. Silent defaulting is a defect (`H2`).
2. **Provenance on every observed value.** `value`, `source`, `retrieved_on`,
   `verified_on`. An empty `verified_on` is permitted and expected — it must render
   visibly marked, and the mark propagates to everything derived from it. Omitting the
   key is *not* permitted. Enforced by `scripts/check_provenance.py` in CI.
   Every sourced table also names the **observation kind** it ages under, declared in
   `observation_kinds.toml`; a table naming a kind that file does not declare, and a kind
   with no `staleness_days`, are both errors (FR-028). The script checks that the
   *declaration* is complete and leaves the staleness verdict to the engine, which is
   given an as-of date; the script has none and must not invent one.
3. **Dated schedules, not constants.** Every rate must accept a dated schedule, so a
   legislated change is modelled rather than requiring a rebuild (spec §4.5.1).
   **Not yet true:** as of feature 001 a tax class carries a scalar rate, not a schedule.
   Tracked as **E10** in `docs/REQUIRED_TESTS.md`. This rule states the requirement, and
   the checklist states how far off we are — a rule that quietly contradicted the code
   would be worse than either.
4. **No legal value from memory.** Tax and legal values come from a cited public
   source, entered as data. Not from an implementer, and not from an agent.
5. **Curated vs per-owner.** Most of this directory is curated and shared — instruments,
   routes, channels, tax packs, venues: public facts about the world. The per-owner
   directories (`streams/`, `spendable/`, `composition/`, `seeds/`, `goals/`) hold one
   person's declarations and are committed on the same footing, because the boundary
   Principle VII draws is *curated versus per-owner*, not *committed versus not*. What stays
   outside and gitignored is what a **run produces** rather than what a person declares:
   results, caches and anything under `data/user/`.

## Assumptions are not observations

`scenarios/` and `objectives/` are exempt from the citation requirement by design:
they hold the owner's own stated beliefs — a probability of sovereign restructuring, a
war-end date, a MilTech loss probability. An assumption needs a **label and a visible
consequence**, not a source. Never present one as though it were an observation.

`streams/` carries the **same exemption, for a different reason**: an owner's own salary
is not an observation needing a citation, it is a statement of fact by the only person
who can make it. That covers `income_tax_rate_pct` too, and it needs saying rather than
inheriting silently, because it looks like a tax rate and every *modelled* tax rate must
carry a source. It is exempt because §4.2 puts the owner's own income-tax position
outside the simulator entirely: the tool takes net-of-income-tax amounts as input, and
the field exists only so the deployable figure is not overstated. A rate the engine
*applies to a taxable event* needs a source; a rate the owner states about his own
payslip does not. `scripts/check_provenance.py` therefore scans `tax/`, `instruments/`,
`routes/` and `channels/`, and names `streams/` in its `EXEMPT_DIRS` with that reason
attached. `strategies/` carries the assumption exemption too: a named allocation is the
owner's decision, and a strategy file that ever carries a market observation moves that
value into a sourced directory instead of widening the exemption.

`spendable/` carries the **same exemption as `streams/`**, and it is the narrowest case of
all: an owner id, a venue id and a currency code. Where a person's money counts as having
come back out is a fact about his life, not an observation of the world, and there is no
number in the file for a source to vouch for. It is listed in `EXEMPT_DIRS` by name with
that reason, which is the only way a directory is allowed to go unscanned; if a *number*
ever appears there — a spending limit, a fee — the value moves to a sourced directory
rather than the exemption widening to cover it.

`composition/` carries the **exemption `objectives/` and `strategies/` carry**, and for the same
reason: it is a *policy*, not a belief and not an observation. How many declared routes the owner
is willing to let a search chain into one candidate is a statement about how far he wants to
look, and nothing in the file describes the world — every *number* that describes a corridor
lives on a leg, in `routes/`, cited. It has **no default**: a registry with no declared bound
fails at load naming the file and the field, by the rule that refuses a default staleness
threshold, because a forgotten line must never read as a chosen policy. `max_segments = 1` is the
explicit way to switch composition off and is a legal choice; `0` admits nothing at all and is
refused as a broken registry.

`seeds/` and `goals/` carry the **same exemption, and they are the sharpest case for it**.
What the owner paid for a lot and what sum he is aiming at are his own records: an acquisition
cost is a fact about a transaction he made, and a target is a decision. Neither is an
observation of the world, so there is nothing for a source to vouch for. Where a cost is
genuinely forgotten the answer is **not** an uncited number quietly accepted — the lot declares
`basis = "estimated"` with the owner's reason, and that estimate marks the disposal's gain and
the tax charged on it, everywhere they appear. A mark is what an unverifiable number gets in
place of a citation. If a *market value* ever has to live in either directory it moves to a
sourced one rather than the exemption widening; the growth assumption a goal is evaluated
against is deliberately not declared in the goal file for the same reason (008 FR-012).

The two lists are **exhaustive, and the gate is fail-closed**: every directory under
`data/` is either scanned or exempted *by name with its reason* in the script, files at
the data root (`venues.toml`) are scanned too, and a directory the script does not know
is an error — never a blind spot. A gate that passes over what it never looked at would
be fail-open in the one script whose job is the opposite.

Per-owner data being *inside* `data/` is a narrower claim than it looks, and feature 008
widened it deliberately. `streams/` holds one committed, reviewed declaration of where money
lands and in what currency, with its amounts at `0.0` because the real figures have not been
stated (§11 item 3) — and `seeds/` and `goals/` now hold the owner's holdings and targets on
the same footing, as labelled synthetic fixtures until his real figures arrive. The boundary
that matters is **curated versus per-owner**, not committed versus not: a salary is at least as
private as a holding and has been committed since feature 002, and this repository is designed
to hold one person's complete financial picture under version control (008 research.md D2).

`user/` stays gitignored and outside every gate: computed results, caches, and anything a run
writes rather than a person declares. That is the part rule 5 above is about — what the owner
*declares* is reviewed in git like code, and what the tool *produces* is not.
