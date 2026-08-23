"""Nominal and real rates as unrelated types, so one can never stand in for the other.

FR-022: *the hurdle-rate figure MUST be reported in nominal terms in this feature, and
MUST state on its face that it is nominal and excludes inflation. The result structure
MUST carry a defined, currently-unpopulated place for the corresponding
inflation-adjusted figure... The system MUST NOT present a nominal figure as though it
were a real one.*

⚙ **Feature 007 populated that place, and the last sentence is the one that did not
change.** The nominal figures are still nominal and still say so; what is new is that the
reserved slot now holds two real figures beside them -- one deflated by declared
observations, one by a declared assumption -- and that the two may never be mixed into one
number or mistaken for the nominal ones.

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
is a materially different proposition from a real 15.5%. Feature 001 left the gap open on
purpose and said so on the output's face rather than implying otherwise; feature 007
closes it, and the shape of these types is what carried the promise across the two: the
slot's *type* changed occupant without the result changing shape, and a nominal figure
still cannot be assigned into it.

A **nominal** rate carries a value and nothing else -- no provenance field. It is a
*derived* figure, and the union of its inputs' provenance is carried by the result record
that holds it (``HurdleRate.provenance``), which is also the level at which a reader asks
the question. Duplicating the mark on every intermediate would create a second place for
it to disagree with itself.

⚙ **The real rate is the one exception, added by feature 007, and the exception is the
point** (007 FR-013). A real figure rests on inputs the holding does not have: every CPI
observation that deflated it, or a declared inflation assumption. Those sources are not in
``HurdleRate.provenance`` and must not be put there -- doing so would make the *nominal*
figure appear to rest on the price index, which it does not. So the real rate carries its
own provenance, the union of the nominal figure's and every observation's, and the
"duplicating the mark" argument does not apply because there is nothing to duplicate: this
is the only record that holds those sources at all.

The same reasoning gives :class:`RealRate` its ``basis``, ``series_id`` and ``window``.
FR-011 requires a real figure to say what it is real *against* and over what span, and
FR-010 requires it to say whether it rests on observed CPI or on a declared assumption. A
figure lifted out of ``RealTerms`` and passed on alone still answers all three, because the
answers are on the record rather than inferred from which field was holding it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from terezy.core.primitives.periods import Window
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.staleness import StalenessVerdict

type RealBasis = Literal["realized_cpi", "declared_assumption"]
"""What a real figure rests on: measured price changes, or a declared belief.

A closed set carried **on the figure** rather than inferred from which field of ``RealTerms``
happens to hold it (007 research.md D2). FR-010 forbids the two being indistinguishable, and a
figure that only knew what it was by where it was stored would stop knowing the moment it was
read out and passed on -- which is exactly when a number gets quoted.

Matched with ``match``, never with a boolean ``is_assumed``: a flag has two states and no
name for either, and the day a third epistemic source appears -- a market-implied breakeven,
say -- a flag has nowhere to put it while this type gains a member and every ``match`` on it
becomes a type error.
"""


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


@dataclass(frozen=True, slots=True, kw_only=True)
class RealRate:
    """An annualised rate in real terms: purchasing power, net of inflation.

    Unrelated to :class:`NominalRate` by design -- no shared base class, no shared protocol
    -- so assigning one into the other's slot is a mypy strict error rather than a bug
    somebody has to notice. See the module docstring.

    ⚙ **Feature 007 filled the slot and gave the record the four fields that make a real
    figure self-describing.** Every one of them answers a question FR-010 or FR-011 requires
    the figure to answer without reference to where it was found: what it rests on, what it
    is real against, over what span, and whose sources it inherits.

    Keyword-only, because ``value`` and ``basis`` are now neighbours and a positional
    construction would let a caller put a rate where a basis belongs the day the field order
    changes.
    """

    value: float
    """The rate as a fraction per annum, net of inflation over :attr:`window`.

    May be negative, and is reported as such: inflation above the nominal rate is a real
    loss, and clamping it to zero would delete the finding this feature exists to produce.
    """

    basis: RealBasis
    """Whether measured CPI or a declared assumption produced this figure (FR-010).

    On the record rather than inferred from which ``RealTerms`` field holds it, so a figure
    passed on alone still says what it rests on. **A cited external forecast is
    ``declared_assumption``**: a forecast has a source and a retrieval date and is still a
    statement about a year that has not happened.
    """

    series_id: str
    """What this figure is real *against* (FR-011).

    For ``realized_cpi``, the id of the CPI series whose observations deflated it. For
    ``declared_assumption``, the id of the declared assumption -- the same question answered by
    the only thing there is to answer it with, so that "real against what?" always has an
    answer and never an empty string.

    **Read it with :attr:`basis`, never alone.** The two id spaces are checked for uniqueness
    separately -- one across ``data/cpi/``, one across ``data/scenarios/inflation/`` -- so a
    belief could in principle be named after a series. The pair is what identifies the
    deflator, and it is the pair that goes into the canonical form; a reader or a renderer
    that showed this field without the basis beside it would be showing half an answer.
    """

    window: Window
    """The span the deflation covered, inclusive (FR-011).

    Carried because a real rate without its window is not checkable: the same nominal figure
    deflated over two different spans gives two different answers, and a reader shown one
    number cannot ask which.
    """

    provenance: Provenance
    """The union of the nominal figure's sources and every observation that deflated it.

    FR-013: an unverified mark on *either* side appears here and on everything derived from
    this figure. Deflating a marked figure never launders the mark, and deflating by an
    unverified observation always adds one. Empty only for a figure resting on a bare owner
    belief and a nominal figure that itself rests on nothing.
    """

    staleness: StalenessVerdict
    """Whether anything this figure rests on has aged past its kind's threshold (FR-005).

    The other half of FR-013, on ``RampCost.staleness``'s precedent: an unverified mark and a
    staleness report are different claims about an input and both must reach the figure. A
    real figure over a long window rests on hundreds of observations, and one of them past its
    threshold makes the figure stale -- naming that observation, its kind and the number of
    days it is overdue.

    **Merged, not chosen.** The verdict covers the CPI side and the nominal side together, so
    a caller cannot read one and think it read both.

    :data:`~terezy.core.primitives.staleness.UNASSESSED` means *nobody aged anything*, which
    is deliberately distinguishable from a verdict that aged sources and found none stale. It
    is what a figure carries when the run supplied no ``as_of`` -- ageing needs a date the
    question is asked at, and this project has no clock to invent one from.
    """


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

    ⚙ **Specific since feature 007.** Feature 001 carried one sentence here for every case,
    because there was only one case. FR-012 replaces it: the reason names the uncovered
    months, the absent series, the absent nominal figure, or the absent assumption -- because
    a refusal that names what is missing is an instruction, and one that does not is a shrug.
    The sentences are built by the named functions in ``core.results.hurdle``, so every result
    says it the same way and none of them can improvise.
    """
