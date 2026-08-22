"""Scenario data: what the owner *believes*, kept apart from what the project *observes*.

**A separate package from ``terezy.core.routes``, and the reason is epistemic** (research.md
D8). Everything in ``routes`` is an observation with a source behind it: a fee schedule, a
premium seen on a screen on a date, a corridor that closed in March 2025. Everything here is
a belief about the future that nobody can source: the war ends mid-2027, the corridors that
exist on either side of that date.

Both kinds of statement change what a route costs, and both are needed. What they may never do
is share a field. A leg's ``available_from``/``available_until`` is a *fact*; a regime
transition is an *assumption*. Written into the same field they become indistinguishable, and
then no output can tell "this route is closed because it closed" from "this route is closed
because I guessed a date" -- which is the entire content of ``SIMULATOR_SPEC.md`` §1.3 and of
this feature's User Story 4. The package boundary is that distinction made structural, on
exactly the precedent that split ``core.streams`` from ``core.routes`` for Principle VII.

Two consequences worth stating where the code lives:

* **Nothing here carries ``Provenance``, and that is not an omission.** Provenance marks an
  observation: where it came from, when it was retrieved, when it was last verified. A belief
  has none of those, and attaching a fabricated source to one would be the top-severity defect
  Principle I names. What a belief carries instead is ``is_assumption``, whose type admits one
  value, and a ``rationale`` in the owner's own words. ``data/scenarios/`` is exempt from the
  citation gate for the same reason -- an assumption needs a label and a visible consequence,
  not a source.
* **A scenario is per-owner data**, like a stream and unlike a route. The mirror in the data
  layer is ``data/scenarios/``.

**No clock, ever.** Which regime is in force is decided against ``on_date`` -- the date the
money moves -- passed in by the caller. Never against ``as_of``, which decides staleness, and
never against a clock: a regime that changed with the wall time would make yesterday's run
unreproducible.
"""
