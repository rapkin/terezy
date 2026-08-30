"""Inflation: the declared price index, and the deflation that turns money into purchasing power.

**A package of its own, not a corner of ``core.metrics`` or ``core.analysis``** (research.md
D9). ``metrics`` is reserved for the preserved return and risk behaviours, and burying a
deflator among Sortino and XIRR would make it look like one of them; ``analysis`` is
projection and replay. Inflation is a small domain with its own declared data, and one
package says so.

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
