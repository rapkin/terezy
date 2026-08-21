"""The ``Instrument`` plugin interface and the instrument classes behind it.

One of the four plugin interfaces permitted by Principle II. Instruments are
declared as data under ``data/instruments/``; this package holds only the interface
and the class-level mechanics (contractual schedules, NAV series, outcome
distributions) that the data drives.

Note that tax treatment is *plural* per instrument: the same instrument can be taxed
one way on distributions and another way on disposal (SIMULATOR_SPEC.md §3.2, §4.1).
"""
