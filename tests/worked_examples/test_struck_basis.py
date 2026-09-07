"""025 FR-026, SC-005: a dollar cost becoming a hryvnia basis, with the arithmetic here.

The formula is 011's, applied to an acquisition cost for the first time:

    base = cost x rate / quotation_unit

**Every figure is a placeholder.** The quantities and costs below are invented; the owner's
own lots are declared under a gitignored root and no test may pin them (`data/README.md`
rule 5). What is *not* invented is the rate: it is read out of the shipped series rather than
retyped, because a retyped rate is a second copy of a published figure and the two disagree
the day the file is corrected.

    lot   0.5 units, acquired 2021-07-15, cost 1 000.00 USD, basis estimated
    rate  data/official_rates/ua_nbu_usd.toml, quoted UAH per 1 USD

The hand computation is written beside the assertion, and the rate is substituted into it
there.
"""

from __future__ import annotations

import shutil
from datetime import date
from typing import Final

import pytest

from terezy.core.ledger import seeds
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.tolerance import is_close
from terezy.core.tax import official_rate
from terezy.data.declarations import resolver
from tests import data_roots

pytestmark = pytest.mark.worked_example

DATA_ROOT: Final = data_roots.with_fixtures()
ASSET: Final = "synthetic_held_dollar"
ACQUIRED_ON: Final = date(2021, 7, 15)
COST_USD: Final = 1_000.0
QUANTITY: Final = 0.5
SERIES: Final = "ua_nbu_usd"

DECLARATION: Final = f"""\
# SYNTHETIC FIXTURE, written by a test. Every term invented.
[instrument]
id             = "{ASSET}"
name           = "Synthetic dollar-priced held asset -- TEST FIXTURE"
class          = "held_asset"
quantity_unit  = "XBT"
price_currency = "USD"
venue_id       = "binance"
is_synthetic   = true
groups         = []

[instrument.tax_classes]
disposal_gain = "no_pack_declares_this"
"""

LOT: Final = f"""\
[owner]
id = "owner-001"

[[seed]]
is_synthetic  = true
instrument_id = "{ASSET}"
quantity      = {QUANTITY}
acquired_on   = "{ACQUIRED_ON.isoformat()}"
cost          = {COST_USD}
basis         = "estimated"
reason        = "AN INVENTED REASON FOR AN INVENTED LOT"
"""


@pytest.fixture(scope="module")
def struck(tmp_path_factory: pytest.TempPathFactory) -> seeds.SeedLot:
    root = tmp_path_factory.mktemp("struck-basis") / "data"
    shutil.copytree(DATA_ROOT, root)
    (root / "instruments" / f"{ASSET}.toml").write_text(DECLARATION, encoding="utf-8")
    overlay = root / resolver.USER_DIR / resolver.SEEDS_DIR / "owner-001.toml"
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.write_text(LOT, encoding="utf-8")
    resolved = resolver.seeds_and_goals_from_data_roots(
        resolver.data_roots_of(root), base_currency=Currency.UAH
    )
    return next(lot for lot in resolved.seeds if lot.instrument_id == ASSET)


@pytest.fixture(scope="module")
def declared_rate() -> official_rate.OfficialRateObservation:
    """The published rate for the acquisition date, read from the file rather than retyped."""
    series = resolver.official_rates_from_data_root(
        data_roots.SHIPPED,
        resolver._resolved_kinds(data_roots.SHIPPED / "observation_kinds.toml")[0],
    ).series[SERIES]
    found = official_rate.observation_for(series, ACQUIRED_ON)
    assert found is not None, f"{SERIES} declares no rate for {ACQUIRED_ON}"
    return found[0]


def test_the_basis_is_the_cost_at_the_rate_of_the_acquisition_date(
    struck: seeds.SeedLot, declared_rate: official_rate.OfficialRateObservation
) -> None:
    """base = cost x rate / quotation_unit, at the lot's own date.

    With `quotation_unit = 1.0` for this series, the arithmetic is
    ``1 000.00 USD x <rate> = <base> UAH`` -- at the published 2021-07-15 rate of 27.3047,
    27 304.70 UAH.
    """
    assert struck.struck_from is not None
    assert struck.struck_from.quotation_unit == 1.0
    by_hand = COST_USD * declared_rate.value / struck.struck_from.quotation_unit
    assert is_close(struck.cost.amount, by_hand)
    assert struck.cost.currency is Currency.UAH


def test_the_conversion_reports_everything_needed_to_redo_it(
    struck: seeds.SeedLot, declared_rate: official_rate.OfficialRateObservation
) -> None:
    """FR-026: a hryvnia figure gives no hint which dollar amount and which date made it."""
    conversion = struck.struck_from
    assert conversion is not None
    assert conversion.amount.amount == COST_USD
    assert conversion.amount.currency is Currency.USD
    assert conversion.series_id == SERIES
    assert conversion.event_date == ACQUIRED_ON
    assert conversion.rate_date == ACQUIRED_ON, "no rule redirected the date"
    assert conversion.applied_rule is None
    assert conversion.rate == declared_rate.value


def test_the_rate_used_is_the_acquisition_date_and_not_a_neighbours(
    struck: seeds.SeedLot,
) -> None:
    """The off-by-one this feature would otherwise ship: the day before, or the day after.

    A rate a day out is a plausible number that is wrong by a day's move, and nothing
    downstream could tell. Asserted against both neighbours rather than only the value,
    because equality with the right rate is also equality with any day it did not move.
    """
    series = resolver.official_rates_from_data_root(
        data_roots.SHIPPED,
        resolver._resolved_kinds(data_roots.SHIPPED / "observation_kinds.toml")[0],
    ).series[SERIES]
    assert struck.struck_from is not None
    for neighbour in (date(2021, 7, 14), date(2021, 7, 16)):
        found = official_rate.observation_for(series, neighbour)
        assert found is not None
        if found[0].value != struck.struck_from.rate:
            assert not is_close(
                struck.cost.amount, COST_USD * found[0].value / struck.struck_from.quotation_unit
            )
