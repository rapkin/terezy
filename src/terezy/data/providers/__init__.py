"""The ``Provider`` plugin interface: prices, distributions, fx, cpi, rates.

One of the four plugin interfaces permitted by Principle II. Prices and
distributions are separate series (REWRITE_BRIEF.md §5.7, fixing D1/L3): the
distribution is the taxed and withheld cash flow, so folding it into an adjusted
price makes the taxable event unreachable.
"""
