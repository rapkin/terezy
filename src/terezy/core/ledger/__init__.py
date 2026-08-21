"""Event-sourced ledger: events, tax lots, cash accounts, and their invariants.

The single biggest change from the predecessor project, which had no lots, no cash
account and no ledger (REWRITE_BRIEF.md §4.3, L1) and therefore could not express any
real tax rule.

The invariants in Principle IV are asserted here as property-based tests over
generated event streams: cash conservation per currency per day, lot conservation,
basis conservation, no negative quantities, and realised gain equal to proceeds minus
consumed basis minus allocated fees -- in both currencies.
"""
