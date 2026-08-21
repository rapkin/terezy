"""Pure, deterministic domain core. No I/O, no network, no rendering, no formatting.

Constitution, Principle III: same scenario + same data snapshot produces identical
results; every stochastic path is explicitly seeded and the seed is recorded in the
run manifest.

This package may not import from ``terezy.data``, ``terezy.api`` or ``terezy.cli``,
nor from the standard library's I/O, serialisation or nondeterminism modules. Those
prohibitions are executable contracts in ``.importlinter``, not conventions.
"""
