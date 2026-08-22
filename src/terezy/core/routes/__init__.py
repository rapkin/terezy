"""Funding and exit routes: ordered chains of legs that move value between venues.

A route is first-class, named, dated and scenario-dependent (SIMULATOR_SPEC.md §4.3).
The registry holds one entry per ``(provider x currency path x venue)``, because the
number of FX conversions is usually the largest difference between two ways of doing
the same thing.

Principle VI: access cost is never quoted per instrument, only per
``(instrument x income stream x route)``, and round-trip cost is what belongs in a
comparison.

**This package adds no plugin interface, and that is a load-bearing claim** (research.md
D1). Principle II permits exactly four -- ``Instrument``, ``Provider``, ``TaxRule``,
``ReturnModel`` -- and a fifth requires a constitutional amendment rather than a pull
request. Nothing here is a fifth, because nothing here has pluggable *behaviour*:

* **Routes, legs, venues and channels are pure declared data.** A leg's cost is arithmetic
  determined entirely by its declared fields; nothing varies but the numbers. A ``Route``
  plugin would let two routes cost the same amount differently, which is precisely what
  FR-029 exists to forbid.
* **Leg *kinds* are an algorithm registry** -- ``LEG_COST_FNS: Mapping[str, LegCostFn]`` in
  ``legs`` -- on the precedent already argued for ``DAY_COUNT_FNS`` in
  ``primitives.conventions``. Principle II requires that adding an *instrument*, *venue*,
  *tax regime* or *jurisdiction* be data-only. A leg kind is none of those four: it is an
  algorithm, and adding an algorithm is code by nature. Adding a leg that *uses* one is
  data, and that is the property the principle protects.
* **``Provider`` stays unimplemented, with its seam named.** An FX channel has two parts: a
  reference rate on a date, and a markup or premium off that reference. The markup is a
  declared observation ("+3 UAH per dollar on Binance P2P"); the reference is what
  ``Provider`` will eventually supply. In this feature it is *also* declared, because there
  is no network, no cache and no rate snapshot -- and inventing a rate source is the one
  thing Principle I forbids most firmly. The function resolving ``(channel, date)`` to a
  two-sided rate is shaped so it can become a ``Provider`` call without changing its
  callers.

**The map of this package**, in dependency order:

``venues``    a place money can sit, and the currencies it can hold.
``channels``  a named two-sided rate source. Never a mid-rate for a transaction (FR-010).
``legs``      one movement, plus the leg-kind algorithm registry.
``path``      ``FundingPath`` -- the ``(destination, stream, route)`` triple with no
              partial form, which is how FR-008 makes a per-destination cost
              *unrepresentable* rather than merely discouraged.
``cost``      ``cost_one``, the **only** function that costs a route (FR-029).

**No clock, ever.** The two dates that matter are parameters and they mean different
things: ``on_date`` is when the money moves, ``as_of`` is when the question is asked.
Conflating them would make a projection into the future report every one of its inputs as
stale (research.md D9).
"""
