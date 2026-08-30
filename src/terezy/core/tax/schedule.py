"""A tax class's rates as dated entries, and the one function that reads them.

`data/README.md` rule 3 and ``SIMULATOR_SPEC.md`` §4.5.1 have asked for this since before
feature 001: *every rate accepts a dated schedule, so a legislated change is modelled
rather than requiring a rebuild*. Feature 001 shipped a scalar rate per class and recorded
the gap as required test **E10**; this module closes it, and the scalar is **removed**
rather than deprecated (research.md D1) -- a debt paid halfway is a second debt, and the
older code path would have kept working and kept nobody honest.

The shape is deliberately small: a sorted tuple of entries, and a fold that picks the last
one in force. Sorting and overlap checking happen at the **loader**, because that is the
only place that can name the file a broken schedule was written in.

**Provenance is per entry, not per class.** The rate before a legislated change and the
rate after it were read from two sources on two days, and one of them may be verified
while the other is not. A single mark on the class would attach one verification date to
two independent observations, which is the quiet way a checked figure ends up vouching
for an unchecked one.

**``effective_from`` is a cited legal fact.** It is exactly the date its citation attests,
and where a source establishes the current rate but not the date the previous one began,
**no earlier entry is invented** -- the schedule starts at the attested date and
:class:`RateUndeclaredBefore` covers everything before it (research.md D2). The shortcut
this rules out is the dangerous one: back-dating an entry to ``1900-01-01`` so that
"everything just works" would put an invented legal fact in a data file while every test
stayed green. A schedule that never refuses is a schedule someone back-dated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover -- typing only, and an import cycle otherwise
    from terezy.core.primitives.provenance import Provenance
    from terezy.core.tax.interface import TaxClass


@dataclass(frozen=True, slots=True)
class RateEntry:
    """One dated set of rates for one tax class: what was charged, from when, on whose word.

    A record carrying only data. The rates are fractions, not percentages -- the ``_pct``
    fields live in declaration files and are divided by 100 exactly once, at the loader.
    """

    effective_from: date
    """The date this entry comes into force, **inclusive**.

    Exactly the date this entry's citation attests, and nothing looser. See the module
    docstring: this single field is the one place in the feature where an agent's memory
    could put an invented legal fact into a data file and leave every gate green.
    """

    pit_rate: float
    """Personal income tax as a fraction of the taxable base. ``0.0`` for an exemption."""

    levy_rate: float
    """Military levy as a fraction of **its own** base. ``0.0`` for an exemption."""

    provenance: Provenance
    """Where *these* rates came from -- this entry's own citation, retrieval date and
    verification date. Required for a zero exactly as for a non-zero rate."""


@dataclass(frozen=True, slots=True)
class RateUndeclaredBefore:
    """No entry is in force on the event's date, because the schedule starts later.

    Returned instead of a rate. There is deliberately **no rate field on this record**: a
    caller cannot read a defaulted number off a refusal, so "the schedule does not reach
    back this far" can never quietly become "the rate was zero" (FR-012).

    This is not a defect in the data. It is what an honest schedule does when a citation
    establishes today's rate and says nothing about when it began: the owner who needs an
    older event goes and finds the citation, and until then the run stops.
    """

    tax_class_id: str
    """Which class could not answer. Names the file to open."""

    event_date: date
    """The date that could not be charged."""

    earliest_declared: date
    """The first date the schedule *does* declare, so a reader knows how far back a
    citation would have to reach."""

    reason: str
    """Plain-language statement, for the output (FR-017)."""


def rate_on(tax_class: TaxClass, on_date: date) -> RateEntry | RateUndeclaredBefore:
    """The entry in force on ``on_date``: the latest ``effective_from`` on or before it.

    The date is an argument -- there is no clock in the core, and a schedule
    read against "now" would produce a different answer tomorrow from the same inputs.

    The boundary is **inclusive**: an entry effective 2024-12-01 governs an event on
    2024-12-01. Stated once, here, and tested at the boundary itself in
    ``tests/unit/test_rate_lookup_boundary.py`` rather than re-derived at each call site.

    ``tax_class.rates`` is non-empty and sorted by ``effective_from``; both are enforced
    where the file can be named, in ``terezy.data.declarations.loader``. The scan runs
    backwards so the common case -- a recent event under the newest entry -- stops on its
    first comparison, and so that "the last one that applies" is the shape of the code
    rather than a claim in a comment.
    """
    for entry in reversed(tax_class.rates):
        if entry.effective_from <= on_date:
            return entry
    earliest = tax_class.rates[0].effective_from
    return RateUndeclaredBefore(
        tax_class_id=tax_class.id,
        event_date=on_date,
        earliest_declared=earliest,
        reason=(
            f"tax class {tax_class.id!r} declares no rate in force on "
            f"{on_date.isoformat()}: its earliest entry takes effect "
            f"{earliest.isoformat()}. Refused rather than charged at the earliest rate "
            "or at zero -- an effective date is a cited legal fact, and extending one "
            "backwards to cover an event would be inventing legislation. Find a source "
            "for the rate in force on the event's date and add it as a dated entry."
        ),
    )
