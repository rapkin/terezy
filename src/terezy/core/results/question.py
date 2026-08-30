"""The question, as a declaration: what was asked, about what, over which windows.

015 FR-001. **A question is an artefact, not a command line** (owner decision, 2026-08-30,
taken against a command-line-arguments-are-canonical alternative). A file under
``data/questions/`` is diffable, citable and reproducible from a commit; it drops into the
digest machinery that already identifies a declaration by the SHA-256 of its bytes; and a new
kind of question becomes a schema field rather than a CLI option *plus* an API parameter *plus*
a call site. The CLI builds the same record from flags and owns no field the file cannot state.

**``as_of`` is deliberately not here** (FR-006). It decides staleness and nothing else, so a
file whose horizons or amounts moved with the calendar would be a different question every day
under one digest. The manifest records both the file's digest and the as-of date.

**Nothing here adds a term to 010's ``Tuple``.** A question names instruments and windows; what
a candidate *is* stays the five declared terms.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from terezy.core.instruments.interface import DateRange
from terezy.core.primitives.money import Money
from terezy.core.results.tuple import ContinuationAssumption, InstrumentPlan


@dataclass(frozen=True, slots=True, kw_only=True)
class Reserve:
    """An amount the owner may need back, and the date he may need it by (FR-016).

    A *stated need*, never a constraint: it produces a verdict per candidate per horizon and
    removes nothing. Excluding an option for failing to meet it would be a feasibility rule,
    which is 010's union and I3's feature.
    """

    amount: Money
    by: date


@dataclass(frozen=True, slots=True, kw_only=True)
class Question:
    """One question, declared. Canonical; the CLI builds the same record from flags."""

    id: str
    owner_id: str
    asked_on: date
    """When the owner asked. A fact about the question, not the clock the run reads."""

    regime_id: str
    """The one regime every candidate's segments belong to (014 FR-023).

    One per question by design: comparing under two regimes is two questions and a reading
    across their answers, which is what makes the deciding belief readable off the difference.
    """

    continuation: ContinuationAssumption
    """What proceeds arriving before a horizon's end do until it. No default anywhere."""

    amounts: Mapping[str, Money]
    """What leaves each income stream, keyed by stream id, in that stream's own currency.

    Never one figure converted into another (FR-021): a channel rate is a transaction price and
    an official rate is a legal reference for what an income was worth on a date, and neither
    values one currency in another *for a return*.
    """

    subjects: tuple[str, ...]
    """The words the owner wrote, in the order he wrote them (FR-007).

    **Untagged on purpose.** Whether a word is an instrument id, a group id or neither is a
    fact about the registry, and a word that is neither must reach the answer as its own
    population rather than refuse the file (FR-009). Tagging here would need the registry at
    load and would turn the owner's vocabulary into curated data.

    Empty exactly when :attr:`every_declared_instrument` is true.
    """

    every_declared_instrument: bool
    """The explicit token meaning *everything the registry declares* (FR-007).

    Stated rather than implied by an empty subject list: omission must not mean *everything*,
    because "compare cash, OVDP, Inzhur and BTC" is not expressible over a registry-wide default
    and the absence of two of those four is the most useful thing the answer says today.
    """

    horizons: tuple[DateRange, ...]
    """One or more windows, in the order declared, each becoming one section of the answer."""

    benchmark_instrument_id: str
    """What everything is ranked against. Named by instrument id; more than one candidate for
    it refuses rather than settling by file order which figure the rest are measured by."""

    plans: Mapping[str, tuple[InstrumentPlan, ...]]
    """How each **subject** is to be run, keyed by the word the owner wrote.

    Per subject rather than per instrument, and that is what stops the file rotting: feature 016
    declares 24 real issues, and under a per-instrument mapping every one of them would be a
    hand edit. The verb expands these to 014's per-instrument mapping, deduplicating equal plans
    so an id named twice yields one candidate (FR-007b).
    """

    reserves: tuple[Reserve, ...]
    """What he may need back, and when. Empty is a question that states no need."""


__all__ = ["Question", "Reserve"]
