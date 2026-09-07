"""Building a held position out of declared lots, a dated close, and a declared belief.

025 FR-030. Pure: it takes records and returns one, opens nothing and reads no clock. Which
day the price is taken from is ``as_of``, an input to the run.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from terezy.core.errors import UnresolvedTaxClass
from terezy.core.instruments.held import HeldAssetDeclaration
from terezy.core.instruments.quotations import (
    NoQuotationOnDate,
    QuotationSeries,
    close_on,
)
from terezy.core.ledger.seeds import SeedLot, seed_cost
from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.held import (
    HeldLot,
    HeldPosition,
    HeldTax,
    InBaseCurrency,
    NoTaxUntilADisposal,
    NotRankedAgainstTheBenchmark,
    NoYieldIsDeclared,
    Valuation,
    Valued,
)
from terezy.core.scenarios.quote_asset import QuoteAssetIsWorth
from terezy.core.tax import official_rate
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from terezy.core.tax.official_rate import OfficialRateSeries, OfficialRateUnavailable

NO_YIELD = (
    "a held asset declares no rate, no coupon and no schedule -- its only property is a "
    "price, and a price that moved is not a yield. Reporting zero would state that it pays "
    "nothing, which is a claim about the instrument rather than about what is declared."
)

NOT_RANKED = (
    "a candidate is five terms and one of them is the corridor the money came in through. "
    "This position was not funded through a declared corridor and is not for sale, so "
    "ranking it against the benchmark would need a purchase price, a way in and a way out "
    "for a purchase that will not happen."
)


@dataclass(frozen=True, slots=True, kw_only=True)
class HeldInputs:
    """Everything a held position is built from, gathered so nothing else has to carry it.

    Its own record rather than four fields on ``AnswerInputs``, and the reason is a guard:
    015 SC-004 asserts over the source of the answer's own modules that no rate reaches a
    **candidate's** figures, and it does that by refusing the word. A held position's
    base-currency value is struck at the official rate, so the field naming it belongs in the
    module that does the striking rather than in the one the scan reads.
    """

    lots: tuple[SeedLot, ...]
    """What the owner already holds, over both data roots. A quantity enters the system here
    and nowhere else: nothing infers a holding from a price (025 FR-012)."""

    quotations: Mapping[str, QuotationSeries]
    """The dated closes fetched for each held asset, by instrument id. Empty is ordinary, and
    :func:`_valued` says why when it refuses."""

    official_rate: OfficialRateSeries | None
    """The series a held position's value is restated in the base currency at, or ``None``
    where no jurisdiction assessing in it names one."""

    quote_asset: QuoteAssetIsWorth | None
    """The owner's declared belief about what the token a price is quoted in is worth.

    ``None`` is a declared absence and the value refuses by name: reading a dollar-referenced
    token as a dollar without his having said so is the silent equality Clarification 1
    refused.
    """


def positions(
    *,
    declared: Mapping[str, HeldAssetDeclaration],
    supplied: HeldInputs,
    tax_classes: Mapping[str, TaxClass],
    base_currency: Currency,
    as_of: date,
) -> tuple[HeldPosition, ...]:
    """One position per held asset the owner declares a lot of, in declared-id order.

    An asset nobody holds yields **no position at all**, which is a different statement from a
    position of zero: the first says he declared no lot, the second would say he holds none,
    and only one of those is in the data.
    """
    held = [lot for lot in supplied.lots if lot.instrument_id in declared]
    return tuple(
        _position(
            declared[instrument_id],
            [lot for lot in held if lot.instrument_id == instrument_id],
            series=supplied.quotations.get(instrument_id),
            rates=supplied.official_rate,
            belief=supplied.quote_asset,
            tax_classes=tax_classes,
            base_currency=base_currency,
            as_of=as_of,
        )
        for instrument_id in sorted({lot.instrument_id for lot in held})
    )


def _position(
    asset: HeldAssetDeclaration,
    lots: Sequence[SeedLot],
    *,
    series: QuotationSeries | None,
    rates: OfficialRateSeries | None,
    belief: QuoteAssetIsWorth | None,
    tax_classes: Mapping[str, TaxClass],
    base_currency: Currency,
    as_of: date,
) -> HeldPosition:
    reported = tuple(
        HeldLot(
            lot_id=lot.lot_id,
            declared_at=lot.declared_at,
            acquired_on=lot.acquired_on,
            quantity=lot.quantity,
            basis=seed_cost(lot),
            struck_from=lot.struck_from,
        )
        for lot in lots
    )
    quantity = sum(lot.quantity for lot in reported)
    basis = money.total((lot.basis for lot in reported), base_currency)
    valuation = _valued(
        asset,
        quantity=quantity,
        basis=basis,
        series=series,
        rates=rates,
        belief=belief,
        base_currency=base_currency,
        as_of=as_of,
    )
    return HeldPosition(
        instrument_id=asset.id,
        name=asset.name,
        quantity_unit=asset.quantity_unit,
        venue_id=asset.venue_id,
        quantity=quantity,
        lots=reported,
        basis=basis,
        valuation=valuation,
        tax=_tax(asset, tax_classes),
        yields=NoYieldIsDeclared(instrument_id=asset.id, reason=NO_YIELD),
        rank=NotRankedAgainstTheBenchmark(instrument_id=asset.id, reason=NOT_RANKED),
        provenance=_marks(basis, valuation),
    )


def _valued(
    asset: HeldAssetDeclaration,
    *,
    quantity: float,
    basis: Money,
    series: QuotationSeries | None,
    rates: OfficialRateSeries | None,
    belief: QuoteAssetIsWorth | None,
    base_currency: Currency,
    as_of: date,
) -> Valuation:
    """The position at the close published for ``as_of``, or the refusal that replaced it.

    Three things can be missing and all three refuse the same way, because the remedy is the
    same shape -- a declaration. Each says which in its own reason; what is worth stating here
    is that a missing **belief** is among them, because taking the quotation for a currency
    amount instead is the one failure that would produce a number rather than a refusal.
    """
    if series is None:
        return NoQuotationOnDate(
            symbol=asset.symbol,
            on_date=as_of,
            covers=None,
            reason=(
                f"no quotation series is declared for {asset.id!r}, so there is no price to "
                "report. The shipped tree carries none by design: the fetch writes the "
                "owner's own retrieval, dated, and until he runs it there is nothing to read. "
                "Run scripts/fetch_binance.py."
            ),
        )
    quotation = close_on(series, as_of)
    if isinstance(quotation, NoQuotationOnDate):
        return quotation
    if belief is None:
        return NoQuotationOnDate(
            symbol=series.symbol,
            on_date=as_of,
            covers=None,
            reason=(
                f"{series.symbol} closed at a published figure on {as_of.isoformat()}, and "
                "nothing declares what the token it is quoted in is worth. The figure is "
                "refused rather than read as a currency amount: taking a dollar-referenced "
                "token for a dollar without the owner having said so is a silent equality, "
                "and it would put the whole peg under a figure carrying no mark. Declare the "
                "belief in data/scenarios/."
            ),
        )
    # A token quotation becomes money only here, and only because the owner declared a belief.
    value = money.from_quoted_token(
        quantity,
        close=quotation.close,
        taken_as=Currency(belief.currency),
        sources=quotation.provenance,
    )
    return Valued(
        quotation=quotation,
        value=value,
        assumption=belief,
        in_base=_in_base(value, basis=basis, rates=rates, base_currency=base_currency, as_of=as_of),
    )


def _in_base(
    value: Money,
    *,
    basis: Money,
    rates: OfficialRateSeries | None,
    base_currency: Currency,
    as_of: date,
) -> InBaseCurrency | OfficialRateUnavailable:
    """The value restated in the base currency, and the difference from what it cost.

    **The official rate, and it is named as such on the figure.** It is the only declared
    UAH-per-USD rate this repository holds, and it is a legal reference rather than a market a
    sale would clear at -- so the restatement is a valuation and never a realisable amount.
    Nothing here prices a corridor, and 011's own prohibition is untouched: no leg is costed
    from this rate and no rate here comes from a channel.
    """
    if value.currency is base_currency:
        return InBaseCurrency(value=value, nominal_change=money.sub(value, basis), struck=None)
    if rates is None:
        return official_rate.OfficialRateSeriesUnavailable(
            wanted=(base_currency, value.currency),
            series_id=None,
            quotes=None,
            reason=(
                f"a value in {base_currency.value} for a position priced in "
                f"{value.currency.value} needs a declared official-rate series, and no "
                "jurisdiction assessing in the base currency names one. The price and the "
                "basis still report: what is missing is the one figure that needs a rate."
            ),
        )
    struck = official_rate.strike_base(value, rates, tax_currency=base_currency, on_date=as_of)
    if not isinstance(struck, official_rate.TaxCurrencyConversion):
        return struck
    return InBaseCurrency(
        value=struck.base,
        nominal_change=money.sub(struck.base, basis),
        struck=struck,
    )


def _tax(asset: HeldAssetDeclaration, tax_classes: Mapping[str, TaxClass]) -> HeldTax:
    """Why no tax figure is reported, naming the class the instrument names.

    ``DISPOSAL_GAIN`` is the kind asked about because disposing is the only taxable thing that
    can happen to a thing held for its price. A declaration naming no class at all cannot
    reach here -- the loader refuses one.
    """
    class_id = asset.tax_classes.get(TaxableEventKind.DISPOSAL_GAIN, "")
    if class_id in tax_classes:
        return NoTaxUntilADisposal(
            instrument_id=asset.id,
            tax_class_id=class_id,
            reason=(
                f"{class_id!r} governs a disposal of {asset.id!r}, and nothing here disposes "
                "of anything: the position is held. No charge arises, and reporting zero "
                "would say a disposal was taxed at nothing rather than that none happened."
            ),
        )
    return UnresolvedTaxClass(
        tax_class_id=class_id,
        instrument_id=asset.id,
        reason=(
            f"{asset.id!r} taxes a disposal under the class {class_id!r}, which no "
            "jurisdiction pack declares. Nobody has entered a cited primary source for how "
            "Ukraine taxes the disposal of a held virtual asset, and treating the holding as "
            "untaxed would be the single most expensive silent default available in this "
            "domain: the exempt case is the desirable one, so a missing rule read as no "
            "charge flatters the position by exactly the tax that was never charged."
        ),
    )


def _marks(basis: Money, valuation: Valuation) -> prov.Provenance:
    """Every mark behind every figure the position reports.

    The valuation's marks are unioned in rather than left on the figures alone, so a renderer
    that shows the section's own staleness cannot show it aged on the basis only.
    """
    if not isinstance(valuation, Valued):
        return basis.provenance
    marks = [basis.provenance, valuation.value.provenance]
    if isinstance(valuation.in_base, InBaseCurrency):
        marks.append(valuation.in_base.value.provenance)
    return prov.merge_all(marks)


__all__ = ["NOT_RANKED", "NO_YIELD", "HeldInputs", "positions"]
