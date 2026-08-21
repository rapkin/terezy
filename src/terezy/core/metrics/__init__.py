"""Return and risk metrics.

The 12 preserved correctness behaviours in REWRITE_BRIEF.md §4.1 are re-derived and
re-tested here; ``docs/REQUIRED_TESTS.md`` tracks which of them have landed. In
particular: flow-adjusted (time-weighted) returns for every risk metric, XIRR kept
separate as the money-weighted outcome, Sortino over the second lower partial moment
across all observations, and periods-per-year measured from the data rather than
assumed.

Principle I: no statistical metric is emitted for an assumption-driven instrument.
"""
