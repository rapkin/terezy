"""H1 and SC-006: a new instrument, route, tax class and jurisdiction, in data only.

**The constitution's own acceptance test for Principle II**, and the row that has stayed open
since the first commit because it could not be attempted until a full pipeline existed to run.
Feature 004 came closest -- ``tests/contract/test_composed_data_only.py`` adds one route
declaration and gets a costed, ranked candidate -- and the box stayed shut because H1 asks for
all four kinds through the **whole** pipeline, ending in the comparison.

Everything below is written into a scratch copy of ``data/``. Nothing under ``src/`` is
touched, and the last class proves it from the other end: no shipped module mentions any of
the new ids in executable code, so none of this works because somebody taught the engine
about it.

**What a failure here would have meant.** FR-023: if some addition cannot be data-only, the
gap is recorded as a named defect in the abstraction -- which seam, which declaration kind,
what edit it forced -- and the abstraction is fixed. **Not** a special case inside the join to
keep this green, because that converts the one test able to falsify the architecture into one
that cannot. This feature did hit such a gap and fixed it in the abstraction rather than
around it: nothing declared *where* an instrument is bought, so the join could anchor neither
seam. The fix is a declaration kind (``data/access/``), which is why the new instrument below
needs an access file and gets one -- as data.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Final

import pytest

from terezy.core.decision.compare import compare
from terezy.core.decision.tuple_outcome import Registries
from terezy.core.instruments.interface import DateRange
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.rates import NominalRate
from terezy.core.results.tuple import Comparison, Tuple
from terezy.core.routes.path import FROM_THE_DECLARATION, FundingPath
from terezy.data.declarations import resolver
from tests import source_scan
from tests import tuple_registries as fixtures

pytestmark = pytest.mark.contract

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
SOURCE_ROOT: Final = REPO_ROOT / "src" / "terezy"

VENUE: Final = "h1_desk"
JURISDICTION: Final = "h1_jurisdiction"
COUPON_CLASS: Final = "h1_coupon_class"
DISPOSAL_CLASS: Final = "h1_disposal_class"
INSTRUMENT: Final = "h1_note"
ROUTE_IN: Final = "h1_desk_in"
ROUTE_OUT: Final = "h1_desk_out"

NEW_IDS: Final = (
    VENUE,
    JURISDICTION,
    COUPON_CLASS,
    DISPOSAL_CLASS,
    INSTRUMENT,
    ROUTE_IN,
    ROUTE_OUT,
)

HORIZON: Final = DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END)

_TAX = f"""
# SYNTHETIC FIXTURE JURISDICTION, written by a contract test. Every rate is invented and
# describes no real tax system anywhere. The rates are deliberately unmistakable.

[jurisdiction]
id            = "{JURISDICTION}"
name          = "H1 FIXTURE jurisdiction -- invented rates, not any real law"
base_currency = "UAH"

[[jurisdiction.tax_class]]
id         = "{COUPON_CLASS}"
applies_to = ["coupon"]
note       = "FIXTURE -- an invented coupon class in an invented jurisdiction."

  [[jurisdiction.tax_class.rate]]
  effective_from = "2020-01-01"
  pit_rate_pct   = 6.0
  levy_rate_pct  = 1.0
  note           = "FIXTURE -- invented rates on an invented date."
  kind           = "tax_rule"
  source         = "SYNTHETIC FIXTURE -- not an observation of anything."
  retrieved_on   = "2026-08-23"
  verified_on    = ""

[[jurisdiction.tax_class]]
id         = "{DISPOSAL_CLASS}"
applies_to = ["disposal_gain"]
note       = "FIXTURE -- an invented disposal class in an invented jurisdiction."

  [[jurisdiction.tax_class.rate]]
  effective_from = "2020-01-01"
  pit_rate_pct   = 8.0
  levy_rate_pct  = 2.0
  note           = "FIXTURE -- invented rates on an invented date."
  kind           = "tax_rule"
  source         = "SYNTHETIC FIXTURE -- not an observation of anything."
  retrieved_on   = "2026-08-23"
  verified_on    = ""
"""

_INSTRUMENT = f"""
# SYNTHETIC FIXTURE, written by a contract test. Terms invented; describes no real issue.

[instrument]
id           = "{INSTRUMENT}"
name         = "H1 FIXTURE note -- terms invented"
class        = "fixed_income"
currency     = "UAH"
is_synthetic = true

[instrument.terms]
face_value        = 500.0
coupon_rate_pct   = 20.0
issue_date        = "2026-01-15"
maturity_date     = "2028-01-14"
periodicity       = "quarterly"
day_count         = "act/act"
business_day_rule = "modified_following"
kind              = "bond_terms"
source            = "SYNTHETIC FIXTURE -- invented for the H1 contract test."
retrieved_on      = "2026-08-23"
verified_on       = ""

[instrument.constraints]
min_ticket   = 500.0
min_unit     = 1.0
kind         = "venue_terms"
source       = "SYNTHETIC FIXTURE -- invented for the H1 contract test."
retrieved_on = "2026-08-23"
verified_on  = ""

[instrument.tax_classes]
coupon        = "{COUPON_CLASS}"
disposal_gain = "{DISPOSAL_CLASS}"
"""

_ACCESS = f"""
# SYNTHETIC FIXTURE, written by a contract test.

[[access]]
instrument_id = "{INSTRUMENT}"
bought_at     = "{VENUE}"
proceeds_to   = "{VENUE}"
risk_class    = "h1_fixture"

  [access.price]
  per_unit     = 500.0
  currency     = "UAH"
  kind         = "venue_terms"
  source       = "SYNTHETIC FIXTURE -- an invented quote for an invented note."
  retrieved_on = "2026-08-23"
  verified_on  = ""
"""

_VENUE = f"""
[[venue]]
id         = "{VENUE}"
name       = "H1 FIXTURE desk, hryvnia only"
currencies = ["UAH"]
"""


def _route(route_id: str, origin: str, destination: str, direction: str, partner: str) -> str:
    return f"""
# SYNTHETIC FIXTURE, written by a contract test.

[route]
id            = "{route_id}"
provider      = "H1 FIXTURE desk"
origin        = "{origin}"
destination   = "{destination}"
direction     = "{direction}"
{partner}status        = "open"

  [[route.leg]]
  index                  = 0
  kind                   = "transfer"
  from_venue             = "{origin}"
  to_venue               = "{destination}"
  from_ccy               = "UAH"
  to_ccy                 = "UAH"
  fee_pct                = 0.4
  fee_fixed              = 12.0
  latency_days           = 2
  disruption_probability = 0.0
  kind_of_observation    = "bank_fee_schedule"
  source                 = "SYNTHETIC FIXTURE -- invented, not a tariff."
  retrieved_on           = "2026-08-23"
  verified_on            = ""
"""


def _scratch(tmp_path: Path) -> Path:
    """A copy of ``data/`` with four new declaration kinds added, and nothing else changed."""
    root = tmp_path / "data"
    shutil.copytree(fixtures.DATA_ROOT, root)
    (root / "tax" / "h1_fixture.toml").write_text(_TAX, encoding="utf-8")
    (root / "instruments" / f"{INSTRUMENT}.toml").write_text(_INSTRUMENT, encoding="utf-8")
    (root / "access" / "h1_fixture.toml").write_text(_ACCESS, encoding="utf-8")
    (root / "venues.toml").write_text(
        (root / "venues.toml").read_text(encoding="utf-8") + _VENUE, encoding="utf-8"
    )
    (root / "routes" / f"{ROUTE_IN}.toml").write_text(
        _route(ROUTE_IN, "monobank_uah", VENUE, "inbound", f'partner_route = "{ROUTE_OUT}"\n'),
        encoding="utf-8",
    )
    (root / "routes" / f"{ROUTE_OUT}.toml").write_text(
        _route(ROUTE_OUT, VENUE, "monobank_uah", "exit", ""), encoding="utf-8"
    )
    return root


def _registries(tmp_path: Path) -> Registries:
    return resolver.tuple_from_data_root(
        _scratch(tmp_path), base_currency=Currency.UAH, scenario_id=None
    ).registries


def _new_tuple() -> Tuple:
    return Tuple(
        instrument_id=INSTRUMENT,
        stream_id=fixtures.SALARY,
        route_in=FundingPath(destination_id=VENUE, stream_id=fixtures.SALARY, route_id=ROUTE_IN),
        exit_terms=fixtures.HOLD_TO_MATURITY,
        route_out=FROM_THE_DECLARATION,
    )


def _comparison(tmp_path: Path) -> Comparison:
    comparison = compare(
        (_new_tuple(),),
        benchmark=fixtures.hurdle_tuple(),
        amount=Money(20_000.0, Currency.UAH, prov.EMPTY),
        horizon=HORIZON,
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=_registries(tmp_path),
    )
    assert isinstance(comparison, Comparison), comparison
    return comparison


class TestTheFourNewDeclarationsLoad:
    """Before anything is projected: all four kinds resolved, against each other."""

    def test_the_new_jurisdictions_two_classes_are_declared(self, tmp_path: Path) -> None:
        classes = _registries(tmp_path).tax_classes
        assert COUPON_CLASS in classes
        assert DISPOSAL_CLASS in classes

    def test_the_new_instrument_resolves_to_them(self, tmp_path: Path) -> None:
        declared = _registries(tmp_path).instruments[INSTRUMENT]
        assert set(declared.tax_classes.values()) == {COUPON_CLASS, DISPOSAL_CLASS}

    def test_the_new_venue_and_its_two_routes_are_declared(self, tmp_path: Path) -> None:
        registries = _registries(tmp_path)
        assert ROUTE_IN in registries.routes
        assert ROUTE_OUT in registries.routes
        assert registries.routes[ROUTE_IN].destination == VENUE

    def test_the_new_instrument_declares_where_it_is_reached(self, tmp_path: Path) -> None:
        entry = _registries(tmp_path).access[INSTRUMENT]
        assert entry.bought_at == VENUE
        assert entry.proceeds_to == VENUE
        assert entry.quote is not None


class TestItRunsTheFullPipelineAndAppearsInTheComparison:
    """SC-006's own words, and the reason the row could not be closed before now."""

    def test_the_new_tuple_is_ranked_beside_the_shipped_benchmark(self, tmp_path: Path) -> None:
        comparison = _comparison(tmp_path)
        assert {outcome.key.instrument_id for outcome in comparison.ranked} == {
            INSTRUMENT,
            fixtures.OVDP,
        }
        assert comparison.refused == ()

    def test_its_outcome_is_complete_rather_than_partial(self, tmp_path: Path) -> None:
        # Complete: every part a shipped tuple's outcome has, none of it defaulted or empty.
        # A pipeline that accepted the declarations and then produced half a result would
        # satisfy "it loads" while failing the thing H1 is about.
        outcome = next(
            item for item in _comparison(tmp_path).ranked if item.key.instrument_id == INSTRUMENT
        )
        assert [line.part for line in outcome.parts] == [
            "ramp_in",
            "entry",
            "lifecycle",
            "tax",
            "exit_terms",
            "ramp_out",
        ]
        assert outcome.arrivals
        assert isinstance(outcome.implied_rate, NominalRate)
        assert outcome.risk_class == "h1_fixture"
        assert outcome.rests_on

    def test_the_new_jurisdictions_rates_actually_charged(self, tmp_path: Path) -> None:
        # The tax class is not decoration: a fixture whose rates never applied would prove the
        # file loads and nothing else. Six and one on coupons, eight and two on the disposal,
        # against the shipped OVDP's nil.
        outcome = next(
            item for item in _comparison(tmp_path).ranked if item.key.instrument_id == INSTRUMENT
        )
        charged = next(line.amount for line in outcome.parts if line.part == "tax")
        assert charged.amount < 0.0

    def test_the_new_routes_charge_and_the_figure_shows_it(self, tmp_path: Path) -> None:
        # 0.4% plus 12.00 each way, and two days each way. A pipeline that loaded the routes
        # and then priced the tuple as though it were free would pass every assertion above.
        outcome = next(
            item for item in _comparison(tmp_path).ranked if item.key.instrument_id == INSTRUMENT
        )
        ramp_in = next(line.amount for line in outcome.parts if line.part == "ramp_in")
        ramp_out = next(line.amount for line in outcome.parts if line.part == "ramp_out")
        assert ramp_in.amount == -(20_000.0 * 0.004 + 12.0)
        assert ramp_out.amount < 0.0
        for arrival in outcome.arrivals:
            assert (arrival.arrived_on - arrival.released_on).days == 2


class TestNoShippedModuleKnowsAnyOfThemByName:
    """Principle II's line, from the other end: behaviour comes from terms, never from an id.

    A branch on ``id == "h1_note"`` would be the moment the framework became one person's
    script, and it is the kind of edit that looks harmless in review. Prose is stripped first,
    because a docstring citing a file is not a violation.
    """

    @pytest.mark.parametrize("identifier", NEW_IDS)
    def test_no_module_mentions_it_in_executable_code(self, identifier: str) -> None:
        offenders = [
            str(path.relative_to(SOURCE_ROOT))
            for path in sorted(SOURCE_ROOT.rglob("*.py"))
            if identifier in source_scan.executable_source(path)
        ]
        assert not offenders, (
            f"these modules mention {identifier!r} in code rather than in prose: {offenders}. "
            "An instrument, a route, a tax class and a jurisdiction are declared data."
        )

    def test_the_scan_reaches_the_modules_that_could_hold_such_a_branch(self) -> None:
        # A scan of nothing passes forever. This names what it walked.
        walked = {path.relative_to(SOURCE_ROOT).as_posix() for path in SOURCE_ROOT.rglob("*.py")}
        for expected in (
            "core/decision/tuple_outcome.py",
            "core/decision/compare.py",
            "core/routes/cost.py",
            "data/declarations/resolver.py",
        ):
            assert expected in walked
