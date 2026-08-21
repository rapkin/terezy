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

Everything here is a frozen record carrying only data, with its operations as free
functions in the same module (constitution, Engineering Standards, owner decision
D-E). There are no methods, no inheritance and no operator dunders: ``money.add(a, b)``,
never ``a + b``. That is not a style preference -- concentrating every combination of
money in one named function is what makes FR-015's provenance union reviewable in one
place instead of auditable across every call site.
"""
