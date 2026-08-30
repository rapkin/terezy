"""Primitives: the leaf of the core. Imports nothing but the standard library.

``Money``, ``Provenance``, ``TOLERANCE``, ``Currency``, the rate records and the
convention registries are imported by every other core package, so they need a home
that cannot import from its siblings. Without that leaf, the first circular import
appears the moment the tax engine needs money and money needs a rate (plan.md,
"Structure Decision").

The rule this package lives by, and which reviewers should hold it to: **a module in
``terezy.core.primitives`` imports the standard library and other modules in this same
package, and nothing else.** It imports no other ``terezy`` package -- not
``terezy.core.ledger``, not ``terezy.core.tax``, not ``terezy.core.results``.
"""
