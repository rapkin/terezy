"""Inflation: the declared price index, and the deflation that turns money into purchasing power.

Feature 001 shipped the hurdle rate labelled **nominal** and left the real-terms slot
occupied by a typed "unavailable" carrying its reason. That was deliberate honesty, not an
omission -- a nominal 15.5% against double-digit inflation is a materially different
proposition -- and this package is what fills the slot.

**A package of its own, not a corner of ``core.metrics`` or ``core.analysis``** (research.md
D9). ``metrics`` is reserved for the preserved return and risk behaviours, and burying a
deflator among Sortino and XIRR would make it look like one of them; ``analysis`` is
projection and replay. Inflation is a small domain with its own declared data, and one
package says so.

## The three pieces of arithmetic discipline

* **A window is a product, not a sum** (:mod:`~terezy.core.inflation.series`). The declared
  series is month-on-month -- ``100.9`` means prices rose 0.9% *that month* -- so cumulative
  inflation chains by multiplying. At Ukrainian magnitudes the difference between the sum and
  the product is material, which is the same reason the approximation one level up is
  forbidden.
* **The exact Fisher relation** (:mod:`~terezy.core.inflation.deflate`), and the subtraction
  approximation is not merely discouraged: no function in this package performs it, and
  ``tests/contract/test_no_subtraction_approximation.py`` scans the source to keep it that way.
* **Coverage is all-or-nothing, and it is checked before any arithmetic runs.** ``coverage``
  returns a tagged union, so an uncovered window cannot reach the Fisher relation at all. One
  missing month makes the realized figure unavailable *naming that month*; the window is never
  silently shortened to the part that happens to be covered, because that produces a real
  number for a window nobody asked about.

## What this package deliberately does not do

**No network, no cache, no fetcher.** ``data/cpi/ua.toml`` is a committed declaration, read by
the data layer like every other one. ``scripts/fetch_cpi.py`` put it there, is tooling outside
the package and outside the layers, and nothing here knows it exists (research.md D10,
Principle III).

**No forecasting model, of any kind.** A future inflation rate enters as a *declared*
assumption -- the owner's own figure, or an external published forecast carrying its own
citation -- and is labelled an assumption on every figure it touches. A cited forecast is
still an assumption: the National Bank's number has a source and a retrieval date and is a
forecast, and cited does not make it observed.

**No interpolation, extrapolation, carry-forward or smoothing.** A period with no declared
observation is a gap, and a gap is reported (FR-004).

**No blended figure.** A realized figure and an assumed figure are two figures, and there is
no field anywhere that could hold a number combining them.

**No clock.** Every date is an argument or a declaration.
"""
