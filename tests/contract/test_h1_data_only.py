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

⚙ **A second FR-023 gap, recorded rather than closed (2026-08-24): the jurisdiction is
validated and then discarded.** The seam is ``data/tax/<pack>.toml``'s ``[jurisdiction]``
table. ``loader.tax_classes_from_file`` checks its ``id``, ``name`` and ``base_currency`` and
returns only the classes; nothing keys a registry by jurisdiction and ``TaxClass`` carries no
jurisdiction field. So the fourth of H1's four declaration kinds is exercised **as a
container** -- a new file with a new id parses and the classes inside it resolve and charge --
and not as a *term*: no figure below would move if this fixture's jurisdiction id were the
shipped one, and its ``base_currency = "UAH"`` matches the shipped pack, so the tax-currency
role is not exercised either. ``data/tax/synthetic_fixture.toml`` already shipped on ``main``,
so "a second tax file parses" was true before this feature.

Closing it is a feature rather than a line: a jurisdiction record carrying the base currency,
keyed in ``Registries``, and a jurisdiction on ``TaxClass`` so a charge can name the pack it
came from and the tax currency can be read from the jurisdiction rather than from
``Registries.base_currency``. It is **not** worked around inside the join.

⚙ **What H1 does not cover, said plainly.** There is no new income stream here: the tuple
below is funded from the shipped ``salary_uah``, so the stream term of Principle VI's tuple is
not among the things this row proves data-only. It is exercised in
``tests/unit/test_two_streams_two_outcomes.py`` instead, against the streams already declared.
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
from terezy.core.primitives.tolerance import is_close
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

RISK_CLASS: Final = "h1_fixture"

NEW_IDS: Final = (
    VENUE,
    JURISDICTION,
    COUPON_CLASS,
    DISPOSAL_CLASS,
    INSTRUMENT,
    ROUTE_IN,
    ROUTE_OUT,
    RISK_CLASS,
)
"""Every string this module invents. The list is the scan below's input, so a new id that is
not here is a new id nothing checks -- which is what happened to the risk class."""

SENT: Final = 20_000.0
FACE: Final = 500.0
QUOTE: Final = 480.0
UNITS: Final = 41.0
"""floor((20 000 - 0.4% - 12.00) / 480) = floor(19 908 / 480) = 41, leaving 228.00 undeployed."""

COUPON_PIT: Final = 0.06
COUPON_LEVY: Final = 0.01
DISPOSAL_PIT: Final = 0.08
DISPOSAL_LEVY: Final = 0.02

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
  pit_rate_pct   = {COUPON_PIT * 100.0}
  levy_rate_pct  = {COUPON_LEVY * 100.0}
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
  pit_rate_pct   = {DISPOSAL_PIT * 100.0}
  levy_rate_pct  = {DISPOSAL_LEVY * 100.0}
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
face_value        = {FACE}
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
#
# The quote is deliberately **below par** -- 480.00 against a face value of 500.00. At par the
# note would be bought and redeemed for the same number, the disposal gain would be exactly
# zero, and the new jurisdiction's disposal class would charge nothing however its rates were
# declared: zeroing them left every assertion in this module green. A 20.00 gain a unit gives
# that class something to bite on and makes it hand-checkable.

[[access]]
instrument_id = "{INSTRUMENT}"
bought_at     = "{VENUE}"
proceeds_to   = "{VENUE}"
risk_class    = "{RISK_CLASS}"

  [access.price]
  per_unit     = {QUOTE}
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
        amount=Money(SENT, Currency.UAH, prov.EMPTY),
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
        assert outcome.risk_class == RISK_CLASS
        assert outcome.rests_on

    def test_the_new_jurisdictions_rates_actually_charged(self, tmp_path: Path) -> None:
        # The tax class is not decoration, and a sign check would not say so: a rate of
        # 0.001% is also negative. Both of the new jurisdiction's classes are pinned by one
        # identity, and every term of it is read off the outcome or hand-computed here.
        #
        #   principal    41 x 500.00                        =  20 500.00
        #   coupons      the lifecycle line, less principal  (7% of it is the coupon class)
        #   gain         41 x (500.00 - 480.00)             =     820.00
        #   disposal     820.00 x (8% + 2%)                 =      82.00
        #
        # Zeroing either pair of rates breaks it, which is what the old assertion could not
        # notice: at par the gain was zero and the disposal class charged nothing either way.
        outcome = next(
            item for item in _comparison(tmp_path).ranked if item.key.instrument_id == INSTRUMENT
        )
        lifecycle = next(line.amount for line in outcome.parts if line.part == "lifecycle")
        charged = next(line.amount for line in outcome.parts if line.part == "tax")
        coupons = lifecycle.amount - UNITS * FACE
        gain = UNITS * (FACE - QUOTE)
        assert is_close(gain, 820.0)
        assert is_close(
            -charged.amount,
            coupons * (COUPON_PIT + COUPON_LEVY) + gain * (DISPOSAL_PIT + DISPOSAL_LEVY),
        )
        assert is_close(gain * (DISPOSAL_PIT + DISPOSAL_LEVY), 82.0)

    def test_the_quote_below_par_is_what_the_purchase_was_sized_from(self, tmp_path: Path) -> None:
        # The precondition of the identity above, and the thing that makes the disposal class
        # reachable at all: the note is bought at the venue's quote and redeemed at its face
        # value, and those are two different numbers.
        outcome = next(
            item for item in _comparison(tmp_path).ranked if item.key.instrument_id == INSTRUMENT
        )
        entry = next(line.amount for line in outcome.parts if line.part == "entry")
        assert is_close(entry.amount, -UNITS * QUOTE)
        assert outcome.undeployed is not None
        assert is_close(outcome.undeployed.amount.amount, SENT - 92.0 - UNITS * QUOTE)

    def test_the_new_routes_charge_and_the_figure_shows_it(self, tmp_path: Path) -> None:
        # 0.4% plus 12.00 each way, and two days each way. A pipeline that loaded the routes
        # and then priced the tuple as though it were free would pass every assertion above.
        outcome = next(
            item for item in _comparison(tmp_path).ranked if item.key.instrument_id == INSTRUMENT
        )
        ramp_in = next(line.amount for line in outcome.parts if line.part == "ramp_in")
        ramp_out = next(line.amount for line in outcome.parts if line.part == "ramp_out")
        assert ramp_in.amount == -(SENT * 0.004 + 12.0)
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
