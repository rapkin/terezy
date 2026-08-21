"""Result records: what a projection returns, and nothing about how it is rendered.

The cash-flow schedule and the hurdle-rate record live here. They are frozen records
of data with free functions to build them, and they are derived from ledger events --
never computed alongside them (research.md D3). Every figure in a result must resolve
back to the events that produced it, because a figure that cannot be traced may not be
reported (constitution, Principle III; FR-008).

Two standing rules for this package:

* **Formatting is not a result.** No currency symbols, no percent signs, no rounding
  for display. A result carries numbers, currencies and provenance; presentation is the
  API layer's job.
* **A degraded outcome is a typed value, not an omission.** A figure the engine cannot
  compute is present and explicitly empty, carrying its reason -- never absent and
  never a nominal figure standing in for a real one (FR-017, FR-022, SC-011).
"""
