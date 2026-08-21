"""The decision layer: candidate generation, feasibility pruning, objectives,
constraints, robustness scoring, and the shortlist.

Search and comparison -- deliberately separate from the declarative framework
(SIMULATOR_SPEC.md §4.10). It does not produce *the* optimal strategy: it produces a
defensible shortlist, names the deciding belief where nothing dominates, reports an
indifference band rather than a false optimum, and says plainly when nothing beats
the naive baseline.

Principle I governs every output of this package.
"""
