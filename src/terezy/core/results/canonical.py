"""Canonical form of a whole projection: the ledger's, plus the figures derived from it.

``ledger.canonical.of_result`` is typed on ``LedgerState``, because the ledger existed
before any result record did. It stays that way: widening it to
``LedgerState | Projection`` would make every caller unpack a union to find out which
shape it got back, and a module in ``core.ledger`` would acquire an import from
``core.results`` -- a dependency pointing the wrong way through the layer it sits in.

So this module **composes** it instead. :func:`of_projection` calls the ledger's function
for the ledger part and adds the derived figures beside it, which is the option the data
model left open for this phase (data-model.md, "Canonical form", the ⚙ note). The ledger
keeps one signature and one meaning.

Everything here follows the rules the ledger's canonical module already establishes, and
they are repeated because they are easy to break by accident:

* **Amounts are ``float.hex()``**, exact and round-trippable, so a digest over this form
  asserts bit-identity rather than agreement to some number of decimals (research.md D5).
* **No serialisation and no hashing.** These are nested tuples of primitives. The digest
  lives in ``terezy.data.manifest``, because hashing implies serialisation and ``hashlib``
  is on the core's forbidden-imports list.
* **Provenance is deliberately excluded.** It identifies *sources*, so filling in a
  ``verified_on`` later would change the digest even though no computed amount moved --
  and C4 would then fail on a documentation update, leaving no honest way to fix it except
  to stop trusting C4. The unverified *mark* is a separate claim, asserted separately by
  E5. Do not add provenance here to make some other test easier.
"""

from __future__ import annotations

from typing import assert_never

from terezy.core.ledger import canonical as ledger_canonical
from terezy.core.ledger.canonical import Canonical
from terezy.core.primitives.conventions import AmountsAsDeclared, ConventionsApplied
from terezy.core.primitives.rates import RealRate, RealTermsUnavailable
from terezy.core.results.hurdle import HurdleRate, RealTerms
from terezy.core.results.project import Projection
from terezy.core.results.schedule import CashFlowRow, CashFlowSchedule
from terezy.core.tax.interface import TaxCharge


def of_conventions(value: ConventionsApplied | AmountsAsDeclared) -> tuple[str, ...]:
    """Whichever statement a row makes about what shaped it, rendered so the two differ.

    Part of the identity of a result, not decoration: the same terms under ``act/365`` and
    under ``30/360`` are different schedules, and a digest that ignored the convention
    would call two genuinely different answers the same. The same argument reaches one step
    further -- a schedule whose amounts were **declared** and one whose amounts were
    computed from three conventions are two different claims about where the money came
    from, and a digest agreeing between them would report them as one (013 FR-016).

    A three-name rendering can never equal a two-entry one, so the two are told apart by
    shape as well as by the tag. The three-name arm is deliberately **untagged**: it is
    byte-for-byte what it has always been, so no generative row's digest moves for a reason
    that is not about that row (013 SC-017).
    """
    match value:
        case ConventionsApplied():
            return (value.periodicity, value.day_count, value.business_day_rule)
        case AmountsAsDeclared():
            return ("declared", value.day_count)
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(value)


def of_row(value: CashFlowRow) -> tuple[Canonical, ...]:
    """One schedule line: what moved, what was taxed on it, and what placed the date."""
    return (
        value.sequence,
        ledger_canonical.of_date(value.occurred_on),
        value.kind.value,
        ledger_canonical.of_optional_number(value.quantity),
        ledger_canonical.of_money(value.gross),
        ledger_canonical.of_money(value.tax),
        ledger_canonical.of_money(value.net),
        of_conventions(value.conventions),
        ledger_canonical.of_causation(value.caused_by),
    )


def of_schedule(value: CashFlowSchedule) -> tuple[Canonical, ...]:
    """The schedule: its currency, then its rows in ledger order.

    The rows are **not** re-sorted. Their order is the fold order, which is a fact about
    the stream, and normalising it away could digest two differently-ordered histories
    identically.
    """
    return (value.currency.value, tuple(of_row(row) for row in value.rows))


def of_charge(value: TaxCharge) -> tuple[Canonical, ...]:
    """One tax charge: both lines, their base, the class that produced them, and its year.

    ``tax_class_id`` is included because a zero charged by one class and a zero charged by
    another are different claims about the money, and the whole point of recording zeroes
    is that they name the rule that produced them.
    """
    return (
        value.event_sequence,
        ledger_canonical.of_money(value.pit),
        ledger_canonical.of_money(value.levy),
        ledger_canonical.of_money(value.total),
        ledger_canonical.of_money(value.taxable_base),
        value.tax_class_id,
        value.charged_for_year,
    )


def of_real_figure(value: RealRate | RealTermsUnavailable) -> Canonical:
    """One real figure, tagged so a number can never be confused with its absence.

    ``("real", <hex>, <basis>, <series id>, <first month>, <last month>)`` or
    ``("unavailable", <reason>)``. The tag is what makes the two cases distinguishable in the
    digest: an untagged rendering could let a real rate of zero and "there is no real rate"
    produce the same bytes, and those are opposite statements. The reason is included because
    it is part of what the result *says*.

    ⚙ **The basis, the series and the window are in the digest, and they have to be** (007
    FR-010, FR-011). The same value deflated by observed CPI and by a declared assumption is
    two different claims, and the same value over two different windows is two different
    facts; a digest that agreed between them would report two results as one. Provenance stays
    out, as everywhere else in this module -- filling in a ``verified_on`` must not move a
    digest.
    """
    match value:
        case RealRate():
            return (
                "real",
                ledger_canonical.of_number(value.value),
                value.basis,
                value.series_id,
                value.window.first,
                value.window.last,
            )
        case RealTermsUnavailable():
            return ("unavailable", value.reason)
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(value)


def of_real_terms(value: RealTerms) -> Canonical:
    """The whole real slot: the realized figure and the assumed one, in that order, tagged.

    Two entries, always, even when both are unavailable -- because ``RealTerms`` is never
    itself unavailable and *which* half is missing is part of what the result says. Rendering
    them in a fixed order means the digest depends on which figure is which rather than on
    the order they happened to be built in.
    """
    return (of_real_figure(value.realized), of_real_figure(value.assumed))


def of_hurdle_rate(value: HurdleRate) -> tuple[Canonical, ...]:
    """The figures: both nominal rates, the real slot, the tax total, and both boundary sets.

    Both sets are emitted sorted, so the digest depends on their content and not on the
    iteration order of a ``frozenset``, which is not guaranteed stable across interpreter
    runs.

    ``accounts_for`` was originally omitted, which quietly broke the mechanism its own
    constant claims: naming what is included beside what is excluded is supposed to mean a
    later feature cannot move a term from one set to the other without a reviewer seeing
    both edits. With only ``excludes`` in the digest, a term added to ``accounts_for``
    alone -- a *claim that the figure is now net of something* -- moved nothing. It does
    now.
    """
    return (
        ledger_canonical.of_number(value.nominal_ytm.value),
        ledger_canonical.of_number(value.nominal_cash_flow_return.value),
        of_real_terms(value.real),
        ledger_canonical.of_money(value.total_tax),
        tuple(sorted(value.accounts_for)),
        tuple(sorted(value.excludes)),
    )


def of_projection(value: Projection) -> tuple[Canonical, ...]:
    """A whole projection: the ledger it came from, then everything derived from it.

    The ledger is included in full rather than summarised. The figures are a *claim* about
    those events, and a digest covering only the conclusions would agree between a correct
    projection and an incorrect one that happened to land on the same number.
    """
    return (
        ledger_canonical.of_result(value.ledger),
        of_schedule(value.schedule),
        tuple(of_charge(charge) for charge in value.charges),
        of_hurdle_rate(value.hurdle),
    )
