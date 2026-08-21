"""Nominal and real rates as unrelated types, so one can never stand in for the other.

FR-022: *the hurdle-rate figure MUST be reported in nominal terms in this feature, and
MUST state on its face that it is nominal and excludes inflation. The result structure
MUST carry a defined, currently-unpopulated place for the corresponding
inflation-adjusted figure... The system MUST NOT present a nominal figure as though it
were a real one.*

**These three records are not a hierarchy, and that is the entire design** (research.md
D4). ``NominalRate`` and ``RealRate`` share no base class and no protocol, so assigning
a nominal figure into a slot typed ``RealRate | RealTermsUnavailable`` is a **mypy
strict error** -- caught by the type checker, not by a test someone might forget to
write. Give them a common base and that one-character mistake type-checks cleanly.

The alternative shapes were considered and rejected. ``float`` with a naming convention
has no mechanical guard at all. ``real: float | None`` makes the misassignment
invisible, and ``None`` reads ambiguously as "zero", "missing" and "not applicable" --
three very different claims about inflation. A single ``Rate`` with a
``basis: Literal["nominal", "real"]`` tag is better, but a mistyped tag is still just a
wrong string.

**Why this matters more than it looks.** A nominal 15.5% against double-digit inflation
is a materially different proposition from a real 15.5%, and the spec leaves that gap
open on purpose (spec.md, Clarifications). The output has to say so rather than imply
otherwise, and the shape of these types is what makes the omission impossible to
overlook: the real slot is always present and always says why it is empty.

Rates carry a value and nothing else -- no provenance field. A rate is a *derived*
figure, and the union of its inputs' provenance is carried by the result record that
holds it (``HurdleRate.provenance``), which is also the level at which a reader asks the
question. Duplicating the mark on every intermediate would create a second place for it
to disagree with itself.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NominalRate:
    """An annualised rate in nominal terms: money, not purchasing power.

    Unrelated to :class:`RealRate` by design. See the module docstring.
    """

    value: float
    """The rate as a fraction per annum -- ``0.155``, never ``15.5``.

    Percent lives only in declaration files, where a ``_pct`` suffix names it, and is
    divided by 100 exactly once at the data boundary. A fraction here means no figure
    can be a hundredfold wrong through a missed conversion.
    """


@dataclass(frozen=True, slots=True)
class RealRate:
    """An annualised rate in real terms: purchasing power, net of inflation.

    Nothing in feature 001 produces one of these. It exists so that the slot in the
    result has a type today, and so that the feature which introduces CPI fills the slot
    without changing the shape of the result or anything that consumes it.
    """

    value: float
    """The rate as a fraction per annum, net of measured inflation."""


@dataclass(frozen=True, slots=True)
class RealTermsUnavailable:
    """The real-terms slot, present and explicitly empty, carrying its reason.

    Not an error and not a failure -- a valid, honest occupant of a slot whose value is
    genuinely unknown. FR-017 requires every degraded outcome to carry its reason;
    SC-011 requires the slot to be *present* and *never* filled with a nominal value
    standing in for a real one. This record satisfies both, and being unrelated to
    :class:`RealRate` is what makes it impossible to confuse with a computed figure.

    It deliberately does not live in ``terezy.core.errors``: nothing failed. Inflation
    is simply not modelled yet, and the result says so on its face.
    """

    reason: str
    """Why no real figure is available, in the output's own words.

    For feature 001: inflation is not modelled, so no real figure can be computed and
    none is invented from an assumed inflation rate.
    """
