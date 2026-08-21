"""Funding and exit routes: ordered chains of legs that move value between venues.

A route is first-class, named, dated and scenario-dependent (SIMULATOR_SPEC.md §4.3).
The registry holds one entry per ``(provider x currency path x venue)``, because the
number of FX conversions is usually the largest difference between two ways of doing
the same thing.

Principle VI: access cost is never quoted per instrument, only per
``(instrument x income stream x route)``, and round-trip cost is what belongs in a
comparison.
"""
