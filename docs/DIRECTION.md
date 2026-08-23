# Direction

Where this is going, what it is for, and what it will refuse to become.

This document carries no counts and no dates. Everything measurable lives in
`specs/features.toml` and `docs/REQUIRED_TESTS.md`, which are kept true; a number
repeated here would be a second copy going quietly out of step with them.

## One idea

You do not choose an asset. You choose the **route** by which money becomes that asset
and eventually becomes spendable money again.

Everything else follows. A ticker with a better chart, reached through a corridor that
costs eight percent to enter and is not costed on the way out, is a worse decision than
a duller instrument two blocks away. That comparison is not available in any tool the
owner could find, because every tool starts from the instrument and treats the route as
plumbing.

The route is not plumbing. It is most of the number.

## Why the unglamorous layers exist

The ledger, the tax engine, the provenance marks, the currency-tagged money — none of
these are the product. **They are what make the edges of the graph truthful.**

That sentence came from outside the project, in a conversation about what to build and
what to borrow, and it is a better statement of the architecture than anything written
here before it. It also settles arguments: when a layer is expensive to build and
adds nothing to whether an edge weight can be trusted, it is a candidate for borrowing.
When it is the only thing standing between a figure and a plausible lie, it is not.

Provenance is the second kind. So is the refusal vocabulary.

## What this is, underneath

A constrained multi-objective path problem where the flow being routed is capital and
the edge weights are partly state-dependent and partly time-dependent.

That is not a metaphor. The graph is declared, paths compose at query time, legs carry
cost and latency and ceilings and disruption probabilities, and regimes switch which
edges exist at all. The honest output is not a winner — it is the **non-dominated set**,
with the assumption that separates its members named.

Which is a pleasant discovery rather than a new plan: the constitution already demands
*dominance → distribution → break-even → point estimate, in that order*. Pareto pruning
is not a technique to bolt on later. It is the algorithmic form of a rule that was
written down before anyone thought about algorithms.

There is a lot of interesting work sitting on top of that — label-setting with
Pareto pruning first, and further out approximate dynamic programming, Lagrangian
relaxation, stochastic edge weights. Each of those is a real technique measured against
a real problem instead of optimisation for its own sake. None of it starts until the
edges are trustworthy, because a beautifully optimised path over invented numbers is
just an invented answer with more steps.

## What this will not become

Naming these is more useful than naming ambitions, because each one is a direction
somebody will eventually propose in good faith:

- **A portfolio tracker.** Mature ones exist. Tracking what you hold is a solved
  problem; deciding how the next unit of money should travel is not.
- **A price-ingestion platform.** Market data is a commodity behind a narrow interface.
- **A charting tool.** A chart that cannot express *"this figure refuses to exist, and
  here is why"* is worse than a table that can.
- **A generic optimiser.** Mean-variance over asset returns is a library call. The hard
  part here is the constraint set, not the objective.
- **Advice.** It produces a defensible shortlist under stated objectives, shows which
  assumption decides between the members, and says plainly when nothing beats doing the
  simple thing.

## What we would rather borrow than build

Each of these is worth investigating on its merits, and each has a catch worth stating
in the same breath:

- **Rule engines in the OpenFisca tradition** — legislation as dated, versioned
  parameters, with reforms as explicit alternative parameter sets rather than branches
  in code. The model is directly applicable, particularly to the one problem already
  recorded and deliberately not built: a rate whose effective date is a *regime
  transition* rather than a date. The catch is that the mature implementations are
  class-hierarchical, and this project is free functions over frozen records by owner
  decision. Take the model, not the library.
- **A mature portfolio-accounting engine as an oracle.** Not as a dependency — as a
  second implementation to check the ledger against. Golden files built by agreeing
  with an independent engine are worth more than golden files built by agreeing with
  the arithmetic that produced them.
- **A portfolio-optimisation library** for the decision layer, when it starts. Writing
  Sortino and flow-adjusted returns by hand is how the predecessor got them wrong, and
  the list of those mistakes is checked into this repository. The catch is real and
  constitutional: the core forbids nondeterminism, and stochastic solvers bring it.
  Adopting one turns determinism from a structural guarantee into a seeding discipline.
  That is the owner's decision, not an implementation detail.
- **A local-first application shell**, for the day the interface is chosen. The privacy
  constraints line up well. The catch is the refusal vocabulary again: a tracker's
  interface has no place to put a typed refusal, and flattening one into a blank cell
  is precisely the failure this project exists to prevent.

The exercise none of this substitutes for: comparing the data models directly, field by
field, and deleting whatever turns out to be someone else's solved problem. It is
cheapest to do while the code is small.

## Questions genuinely still open

Not a backlog — things nobody has decided:

- **The interface.** Deliberately unchosen until the result schema has stopped moving
  against real output. The API is built as its only contract so the choice stays cheap.
- **More than one jurisdiction.** The framework is shaped for it and nothing exercises
  it. Whether that ever matters depends on where the owner lives.
- **Beliefs that appear twice.** A war ending switches which routes exist *and* which
  tax rate applies, and today those are two declarations with nothing tying them
  together. A run can assume the war ends for routing and go on charging the wartime
  rate for ever. The fix is a schedule keyed to a state transition rather than a date,
  and that is a modelling question, not a tidy-up.
- **Automated data.** Reserved behind a narrow interface. The hard part was never
  fetching; it is that a machine cannot mark a value verified on a person's behalf.

## The rule that outlives all of it

**Honesty over precision.** A range beats a false point estimate, a refusal with a
reason beats a plausible number, and a figure derived from an unverified input stays
marked all the way to the screen.

Every principle in the constitution is downstream of that one. If some future version
of this project keeps nothing else, it should keep that — because a decision tool that
is confidently wrong is worse than no tool, and confidence is the cheapest thing in
software to fake.
