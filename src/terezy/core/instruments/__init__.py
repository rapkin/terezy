"""The ``Instrument`` plugin interface and the instrument classes behind it.

One of the four plugin interfaces permitted by Principle II. Instruments are
declared as data under ``data/instruments/``; this package holds only the interface
and the class-level mechanics (contractual schedules, NAV series, outcome
distributions) that the data drives.

**Two declaration kinds live here, and only one of them implements the interface.**
``fixed_income`` does; ``fund`` does not, because a fund's projection needs inputs a bond
has no use for, refuses in ways a bond cannot, and can answer with *two* results where the
interface returns one. That is a second kind under the same concept rather than a fifth
plugin interface -- no new registry and no new dispatch -- and the owner ruled on it on
2026-08-23. The argument is in ``registry.py``'s section comment; the vocabulary of kinds
is ``registry.DECLARATION_KINDS``.

Note that tax treatment is *plural* per instrument: the same instrument can be taxed
one way on distributions and another way on disposal (SIMULATOR_SPEC.md §3.2, §4.1).
"""
