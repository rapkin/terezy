"""The official rate: the third currency role, and the one number nobody transacts at.

This module is the **tax** currency role of constitution Principle VI.

## An official rate is not a channel, and the difference is the whole feature

An **FX channel** is a market you transact in: two sides, a spread, a fee, a counterparty,
and it decides how much money you end up with. An **official rate** is a legal reference you
never transact at: one side, no spread, no counterparty, and it decides what number the law
says your income was.

The prohibition runs both ways and they are **two requirements, not one**:

* FR-012 -- the amount *received* is never computed from an official rate. Nothing under
  ``terezy.core.routes`` may import this module.
* FR-013 -- a channel's ``reference_rate`` is never a tax rate. This module may not import
  ``terezy.core.routes.channels``.

Both are ``.importlinter`` contracts, one each, because a single contract naming both would
stay green if either direction were deleted.

## What a date with no declared rate does

It refuses, by name. Nothing here interpolates between observations, extrapolates past
either end, carries a previous date's value forward, or snaps to the nearest -- each of
which produces a number that looks exactly like a correct number, and every tax figure
downstream would inherit the invention with no mark on it (FR-010).

The one sanctioned escape is a **declared** non-publication-day rule: a cited statement of
which observation governs a date the publisher does not publish for. It is data, and this
module contains no notion of a weekend, a public holiday or a banking calendar (FR-011).

**A rule written in working days or public holidays cannot be declared against these
records at all**, because evaluating one needs a working-day and holiday calendar and nothing
declares one. That is the constraint this module imposes; which series it bites and what it
costs them is stated where the absence lives, in the declaration file.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance


@dataclass(frozen=True, slots=True, kw_only=True)
class OfficialRateObservation:
    """One date's published official rate: the atom of the tax currency.

    One value, one side, no spread. Two sides is the defining property of an ``FxChannel``,
    and a rate that acquired one would be a channel with a government's name on it -- which
    is why the declaration has no field for a second side and this record has none either.
    """

    on_date: date
    """The date this rate is the official rate **for** -- not the date it was read."""

    value: float
    """The published figure, strictly positive, checked at the data boundary.

    Units of the series' price currency per :attr:`OfficialRateSeries.quotation_unit` units
    of its unit currency. The value alone is meaningless without that unit, which is why the
    unit may not be defaulted and is reported on every figure it scaled.
    """

    provenance: Provenance
    """Where this date's rate came from. One ``SourceRef`` per observation, so a base names
    the day it rests on rather than the file.

    **There is deliberately no ``kind`` field beside this.** The staleness kind rides on the
    citation (``SourceRef.kind``, stamped by the loader), because that is the only thing that
    survives the merge a derived tax figure passes through: a base rests on the amount's
    sources *and* the rate's, and after that union no record is in hand to name a threshold.
    Feature 010 found that a threshold held on a record does not survive and a kind held on a
    citation does; ``staleness.staleness_of_sources`` is what ages this.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class NonPublicationDay:
    """One row of an enumerated rule: this date's rate governs that date."""

    applies_to: date
    """A date the publisher does not publish for."""

    governed_by: date
    """The declared observation whose rate governs it. Checked at load to be one."""


@dataclass(frozen=True, slots=True, kw_only=True)
class NonPublicationRule:
    """A declared, cited statement of which observation governs an unpublished date.

    **An explicitly enumerated mapping**, one row per date. That form is a statement of the
    kind FR-011 defines and needs no calendar, which is what makes it declarable here; a rule
    written in working days is not, and FR-018 records why.

    A paraphrase is not a citation and may not enter as one (FR-011): the citation names a
    text somebody read, and agreement between secondary sources restating a rule is not a
    substitute for it.
    """

    id: str
    """Named, so a base can say which rule redirected its date."""

    days: tuple[NonPublicationDay, ...]
    """The enumerated mapping. A date it does not list is a date it says nothing about."""

    provenance: Provenance
    """The rule's own citation. Required and non-empty, enforced at the data boundary."""


@dataclass(frozen=True, slots=True, kw_only=True)
class OfficialRateSeries:
    """A declared, identified sequence of single-sided rate observations from one authority."""

    id: str
    """Unique across the data root; a collision names both files."""

    authority: str
    """Who publishes it. Half of what makes a second country's series a data-only addition."""

    pair: tuple[Currency, Currency]
    """``(price, unit)`` -- ``FxChannel.pair``'s convention: :attr:`quotation_unit` units of
    *unit* cost ``value`` of *price*.

    The series converts **unit into price**, and the other direction is not derived. Taking
    ``1 / value`` would be inferring a quote the authority did not publish, which is the same
    refusal ``resolver._check_channel`` makes for a channel asked about another pair.
    """

    quotation_unit: float
    """How many units of the unit currency the value is stated per. Strictly positive.

    **Declared, never defaulted** (FR-002). A published table that quotes some currencies per
    1 and others per 100 is normal, and a value read at the wrong unit is wrong by two orders
    of magnitude while looking entirely plausible; a default here would make that silent.
    """

    rule: NonPublicationRule | None
    """The declared non-publication-day rule, or ``None``.

    ``None`` is a statement and not a gap in this record: absent a rule, a date the series
    does not declare refuses, because the absence of a rule is not permission to choose one.
    """

    observations: tuple[OfficialRateObservation, ...]
    """The declared dates, strictly ascending, without duplicates -- all checked at the data
    boundary, where the file can be named.

    **Gaps are permitted, and so is emptiness.** A date the publisher did not publish for is
    a fact and inventing one is forbidden; and a series with no observations at all is the
    declared shape a fetch script writes into, which is what ships for Ukraine today. Both
    are reported by the request that wanted a rate, naming the date it asked about -- which
    is more use than a load error naming a directory.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class TaxCurrencyConversion:
    """One tax base being struck, with everything needed to re-derive it on paper.

    FR-016: ``base = amount * rate / quotation_unit``. A hryvnia figure gives no hint of
    which dollar amount and which date produced it, so every input is carried rather than
    left for a reader to find in a data file.

    Provenance is **not** a field here. It lives on :attr:`base`, where ``money.convert`` put
    it -- the union of the amount's own sources and the rate observation's, plus the rule's
    when a rule chose the date. A second copy would be a second place for one fact.
    """

    amount: Money
    """What was converted, in the currency the event was denominated in."""

    base: Money
    """The struck base, in the tax currency."""

    series_id: str
    pair: tuple[Currency, Currency]

    event_date: date
    """The date the taxable event carries. This feature introduces no second notion of it
    (FR-008): it consumes the date the event already has and looks the rate up on that."""

    rate_date: date
    """The observation's own date. Equal to :attr:`event_date` unless a rule redirected it,
    so a Friday rate applied to a Sunday event is visible rather than implied."""

    applied_rule: str | None
    """The rule that redirected the date, or ``None`` when the event's own date is declared."""

    rate: float
    quotation_unit: float


@dataclass(frozen=True, slots=True, kw_only=True)
class OfficialRateSeriesUnavailable:
    """No declared series serves this pair: none was given, or the one given quotes another.

    One record for both because the fix is one sentence: name a series that quotes the pair.
    """

    wanted: tuple[Currency, Currency]
    """``(tax currency, the amount's currency)`` -- the quote that would have been needed."""

    series_id: str | None
    """The series that was consulted, or ``None`` when the jurisdiction declared none."""

    quotes: tuple[Currency, Currency] | None
    """What that series quotes instead, or ``None`` when there was no series."""

    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OfficialRateUndeclaredOnDate:
    """The series declares no rate for this date, and no declared rule covers it.

    Not an error, not a zero, and not a number. The remedy is a declared observation or a
    declared, cited rule -- both of which are data.
    """

    series_id: str
    pair: tuple[Currency, Currency]
    on_date: date

    covers: tuple[date, date] | None
    """The declared window, first and last, or ``None`` for a series with no observations.

    Carried so the refusal distinguishes *before the window*, *after it*, *inside a gap* and
    *nothing is declared at all* without the reader opening a file.
    """

    reason: str


type OfficialRateUnavailable = OfficialRateSeriesUnavailable | OfficialRateUndeclaredOnDate
"""Why no base could be struck. Matched with ``match``; each member names its own fix."""


def covered_window(series: OfficialRateSeries) -> tuple[date, date] | None:
    """The first and last dates the series declares, or ``None`` when it declares none.

    Read off the ends rather than by scanning, because the observations are strictly
    ascending by the time they leave the loader.
    """
    if not series.observations:
        return None
    return series.observations[0].on_date, series.observations[-1].on_date


def observation_for(
    series: OfficialRateSeries, on_date: date
) -> tuple[OfficialRateObservation, str | None] | None:
    """The observation governing ``on_date`` and the rule that chose it, or ``None``.

    The series' own declaration for the date wins over any rule. A rule speaks for dates the
    publisher does **not** publish for, so a rule claiming a published date contradicts the
    publication -- refused at load, where the file can be named, and the ordering here is
    what makes that refusal the only way such a rule can exist.
    """
    declared = {observation.on_date: observation for observation in series.observations}
    found = declared.get(on_date)
    if found is not None:
        return found, None
    if series.rule is not None:
        for day in series.rule.days:
            if day.applies_to == on_date:
                governing = declared.get(day.governed_by)
                if governing is None:
                    raise KeyError(
                        f"rule {series.rule.id!r} of series {series.id!r} sends "
                        f"{on_date.isoformat()} to {day.governed_by.isoformat()}, which the "
                        "series does not declare. The loader refuses such a rule and can name "
                        "the file and the row, so reaching here means that check was bypassed "
                        "-- and falling through to 'no rate is declared for this date' would "
                        "blame the date instead of the rule."
                    )
                return governing, series.rule.id
    return None


def strike_base(
    amount: Money,
    series: OfficialRateSeries,
    *,
    tax_currency: Currency,
    on_date: date,
) -> TaxCurrencyConversion | OfficialRateUnavailable:
    """The tax base of ``amount``, at ``series``' declared rate for ``on_date``.

    FR-007: the event's own amount, at the official rate declared for the event's own date.
    Never an average, never a period rate, never a neighbouring date's rate, and never a rate
    from a series the jurisdiction did not name.

    **An amount already in the tax currency raises**, rather than being returned unchanged.
    FR-009 says such an event must not consult a rate at all, so the caller checks first;
    making the call a programmer error is what stops a false rate-unavailable reason ever
    being attached to a figure that never needed one -- and a false refusal trains a reader
    to ignore true ones.

    ``rate / quotation_unit`` is the one place the declared unit is applied, and
    ``money.convert`` takes it as *units of ``tax_currency`` per one unit of
    ``amount.currency``*, which is the direction :attr:`OfficialRateSeries.pair` declares.
    """
    if amount.currency is tax_currency:
        raise ValueError(
            f"an amount already in the tax currency ({tax_currency.value}) needs no official "
            "rate, and asking for one would attach a rate-unavailable reason to a figure that "
            "never needed a rate (FR-009). The caller checks the currency before striking a "
            "base; reaching here means that check was bypassed."
        )
    wanted = (tax_currency, amount.currency)
    if series.pair != wanted:
        return OfficialRateSeriesUnavailable(
            wanted=wanted,
            series_id=series.id,
            quotes=series.pair,
            reason=(
                f"a base in {tax_currency.value} for an amount in {amount.currency.value} "
                f"needs a series quoting {tax_currency.value} per {amount.currency.value}, and "
                f"{series.id!r} quotes {series.pair[0].value} per {series.pair[1].value}. No "
                "rate is inferred for another pair and none is inverted: an authority sets the "
                "quote it publishes, and deriving the other direction would be inventing a "
                "legal value. Name a series that quotes this pair."
            ),
        )
    found = observation_for(series, on_date)
    if found is None:
        window = covered_window(series)
        return OfficialRateUndeclaredOnDate(
            series_id=series.id,
            pair=series.pair,
            on_date=on_date,
            covers=window,
            reason=(
                f"{series.id!r} ({series.pair[0].value} per {series.pair[1].value}) declares "
                f"no official rate for {on_date.isoformat()} "
                + (
                    f"and no non-publication-day rule covering it; it covers "
                    f"{window[0].isoformat()} to {window[1].isoformat()}. "
                    if window is not None
                    else "and declares no observation at all. "
                )
                + "Nothing is interpolated, extrapolated, carried forward or taken from the "
                "nearest date: each of those produces a number indistinguishable from a "
                "correct one, and every tax figure derived from it would inherit the "
                "invention unmarked (FR-010). Declare the observation, or declare a cited "
                "non-publication-day rule saying which date's rate governs this one."
            ),
        )
    observation, rule_id = found
    sources = observation.provenance
    if rule_id is not None and series.rule is not None:
        sources = prov.merge(sources, series.rule.provenance)
    return TaxCurrencyConversion(
        amount=amount,
        base=money.convert(
            amount,
            to_currency=tax_currency,
            rate=observation.value / series.quotation_unit,
            sources=sources,
        ),
        series_id=series.id,
        pair=series.pair,
        event_date=on_date,
        rate_date=observation.on_date,
        applied_rule=rule_id,
        rate=observation.value,
        quotation_unit=series.quotation_unit,
    )
