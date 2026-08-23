"""``compose``: chain declared routes into candidates. Enumeration, never routing.

FR-001: *the system MUST enumerate composed candidates for a stated
``(stream, amount, destination)``: ordered chains of declared routes in which each segment's
destination venue and arriving currency match the next segment's origin venue and departing
currency.* FR-003 adds that every one of them is costed in full through the one costing
function, and FR-002 that composition invents no numbers.

## This module is a search, and a search is where a heuristic gets in

Composition is a routing problem, and routing problems attract shortest-path algorithms,
pruning by estimate, partial-cost caches, and tie-breaks by whatever order the search visited
things. Every one of those is a number more confident than its inputs. So the design refuses
each of them structurally rather than by convention:

* **Nothing is pruned by cost.** This module never calls a costing function, holds no ``Money``
  and imports none. There is no field on any record here for a path score, and required test
  **B12** is why: a routing search is exactly where a composite score sneaks into a
  user-visible ordering. Every emitted candidate is costed in full afterwards, by
  :func:`terezy.core.routes.cost.cost_one`, exactly as a declared route is.
* **No partial cost is memoised.** A partial cost is valid for **one amount only**, because
  minimums, caps and fixed fees are not linear. A cache keyed by anything less than the whole
  amount would be an invented number the first time it hit (research.md D5).
* **Order influences nothing.** Each adjacency bucket is sorted by route id, so the walk is a
  function of the declarations rather than of dictionary ordering; and the emitted tuple is
  sorted again by ``(segment count, route ids)``, so even the walk's order does not reach the
  output. SC-003 runs a registry in both declaration orders and compares everything, and it is
  the test that catches a heuristic rather than a flaky ordering.

## Directions never mix, and the check is in the index (research.md D10)

The adjacency index is built **per direction**, so an inbound enumeration cannot see an exit
route: it is not in the index it walks. A post-hoc filter over mixed candidates is the version
that gets one condition wrong under a refactor; an index that never contained the wrong routes
cannot emit them. An observation of a corridor in one direction says nothing about its terms,
its limits, or its existence in the other (FR-022).

## A junction converts nothing, charges nothing and waits for nothing

Two segments join only where the destination venue **and** arriving currency of one equal the
origin venue **and** departing currency of the next. Where the venue matches and the currency
does not, the chain simply does not exist -- it is never bridged by an implicit conversion,
because an implicit conversion is an invented leg at an invented rate (FR-002). The corridor's
absence is a fact for the coverage report, not something to paper over here.

## The regime is the caller's, and this module never hears about it

FR-017 requires every segment of a candidate to belong to the route set of the single regime in
force on the date. The narrowing is :func:`terezy.core.scenarios.regimes.routes_in_force`'s, and
what arrives here is the already-narrowed mapping plus the id it was narrowed for. That is the
same division ``cost_one`` already makes -- and it is load-bearing rather than tidy: the
costing engine has never heard of a regime, so an assumption cannot arrive in the same shape as
an observation, and ``tests/unit/test_transition_is_an_assumption.py`` holds the whole package
to it. A ``regime_id`` string carries the *fact* onto the result without carrying the belief
into the search.

⚙ **This is a departure from ``contracts/composition.md``**, which gives ``compose`` a
``regime: Regime`` parameter. Taking the record would put a second place in the engine that
decides which routes a regime includes, and would breach a landed boundary to do it. The
guarantee G14 asks for is unchanged: it is checked by handing this function a regime's routes
and no others, which is what the caller already has.

## No clock, no I/O, no state

``compose`` is pure. There is no date here at all: availability windows, statuses, caps and
minimums are **feasibility**, and feasibility is costing's answer on a date (FR-015), reported
with the binding segment named. A search that dropped a candidate because a leg was shut would
make an exclusion silent, which is precisely what FR-014 forbids.
"""

from __future__ import annotations
