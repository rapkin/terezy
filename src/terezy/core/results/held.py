"""What a position the owner already holds reports, and what it refuses by name.

025 FR-029, FR-030, answered by the owner on 2026-09-07: a held position gets the answer's own
**held** section, beside the horizon sections, and is never a baseline row in a ranking.

**It is not a candidate and cannot be made one.** ``Tuple.route_in`` is required and there is
no zero-hop entry, so putting a holding in the ranking would need a purchase price, a funding
corridor and an exit for a purchase that will not happen -- three invented numbers for one row.
The ranking keeps answering one question, which is where new money should go.

**Three of the four things a candidate reports are refused here, and each says so as a value.**
No tax, because Ukraine's treatment of a virtual asset is unsettled and nobody has entered a
cited source; no yield, because a held asset declares no rate and no schedule; no rank, for the
reason above. A field holding a record with one inhabitant is a constant, and it is deliberate:
an absent key reads as an oversight, and FR-030 asks for the absence to be *stated*.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from terezy.core.errors import UnresolvedTaxClass
from terezy.core.instruments.quotations import NoQuotationOnDate, Quotation
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.scenarios.quote_asset import QuoteAssetIsWorth
from terezy.core.tax.official_rate import OfficialRateUnavailable, TaxCurrencyConversion


@dataclass(frozen=True, slots=True, kw_only=True)
class HeldLot:
    """One acquisition behind a position: when, how many, and what it cost in the base."""

    lot_id: str
    declared_at: str
    """``seeds/owner-001.toml#seed[0]``, so a figure traces to the line that declared it."""

    acquired_on: date
    quantity: float

    basis: Money
    """What it cost, in the base currency, carrying every mark it rests on."""

    struck_from: TaxCurrencyConversion | None
    """How a foreign cost became that base amount, or ``None`` where it was declared in one
    (025 FR-026). Carried so the arithmetic can be redone from the report."""


@dataclass(frozen=True, slots=True, kw_only=True)
class InBaseCurrency:
    """The position restated in the base currency, and the difference from what it cost.

    **Struck at the official rate for the run's own date, and that is a statement rather than
    a convenience.** It is the only declared UAH-per-USD rate this repository holds. What it is
    *not* is what a sale would fetch: no corridor is priced here and none is modelled, so this
    is a valuation and never a realisable amount (Principle VI's last clause).
    """

    value: Money
    """``quantity x close`` restated in the base currency, carrying the rate's own mark."""

    nominal_change: Money
    """Value less basis. **Nominal**: no inflation, no tax, no cost of getting out, and not a
    return -- a return needs a period and a denominator, and this is a difference."""

    struck: TaxCurrencyConversion | None
    """The conversion in full, so the arithmetic can be redone from the report, or ``None``
    where the price was already in the base currency and no rate was consulted.

    ``None`` is a statement, on ``SeedLot.struck_from``'s reading: it says a rate was not
    needed, and it is required with no default so a value that *was* struck cannot reach a
    reader claiming otherwise."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Valued:
    """The position priced at the close published for the run's own ``as_of``."""

    quotation: Quotation
    """The published close and the day it is the close of."""

    value: Money
    """``quantity x close``, in the currency the belief says the quote asset equals."""

    assumption: QuoteAssetIsWorth
    """The belief that made a token quotation a currency figure, named so a reader can find
    the file (025 FR-023). Required with no default: a valued position that could omit it
    would be a dollar figure resting on an unstated peg."""

    in_base: InBaseCurrency | OfficialRateUnavailable
    """The base-currency restatement, or 011's typed refusal naming the series and the date.

    A refusal here does **not** suppress the price, the quantity or the basis (FR-015): a
    holding whose value cannot be restated in hryvnia today is still a holding whose price and
    cost are known, and reporting nothing about it would be less honest rather than more.
    """


Valuation = Valued | NoQuotationOnDate
"""Whether this position has a price today. One union, so a refusal is stated once rather than
standing in for the value, the change and the price separately."""


@dataclass(frozen=True, slots=True, kw_only=True)
class NoTaxUntilADisposal:
    """The instrument's tax class is declared, and nothing here disposes of anything.

    The other member of the tax union, and it exists because SC-008 requires a second held
    asset to be a data-only addition: one naming a class some pack declares must still not
    report a charge of zero.
    """

    instrument_id: str
    tax_class_id: str
    reason: str


HeldTax = UnresolvedTaxClass | NoTaxUntilADisposal
"""Why no tax figure is reported. Never an absence and never a zero: the exempt case is the
desirable one, so a missing rule read as no charge would flatter the position by exactly the
tax that was never charged."""


@dataclass(frozen=True, slots=True, kw_only=True)
class NoYieldIsDeclared:
    """A held asset declares no rate and no schedule, so there is no yield to report."""

    instrument_id: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class NotRankedAgainstTheBenchmark:
    """A holding is not a candidate for the money the question is about."""

    instrument_id: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class HeldPosition:
    """One declared asset, everything the declarations say about it, and every refusal."""

    instrument_id: str
    name: str
    quantity_unit: str
    """What one unit is called. Reported beside every quantity: a number of units means
    nothing without it."""

    venue_id: str

    quantity: float
    """The total held, summed over the declared lots. Never inferred from a price."""

    lots: tuple[HeldLot, ...]
    """The acquisitions it is made of, in declared order. Carried rather than summarised: two
    lots bought years apart at different rates are why the basis is what it is."""

    basis: Money
    """The hryvnia cost of the whole position, carrying both marks a struck estimate rests on
    -- the owner's estimate and the official-rate observation (FR-027)."""

    valuation: Valuation
    tax: HeldTax
    yields: NoYieldIsDeclared
    rank: NotRankedAgainstTheBenchmark

    provenance: Provenance
    """The union of every mark behind every figure above, so the section can be aged and
    rendered marked without a reader walking the record."""


__all__ = [
    "HeldLot",
    "HeldPosition",
    "HeldTax",
    "InBaseCurrency",
    "NoTaxUntilADisposal",
    "NoYieldIsDeclared",
    "NotRankedAgainstTheBenchmark",
    "Valuation",
    "Valued",
]
