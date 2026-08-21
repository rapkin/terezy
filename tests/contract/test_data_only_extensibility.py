"""A second issue, in data only. **SC-003** and **SC-012**, with the proof stated.

*"A second bond issue with different terms is added and produces a complete result with
**zero** lines of source code changed"* (SC-003), and *"two issues declaring different
coupon periodicities and day-count conventions both produce correct schedules with no
source-code change, and each schedule reports the convention it applied"* (SC-012).

This is the executable form of constitution Principle II -- *"adding an instrument, a
venue, a route, a tax regime or a jurisdiction must be a data-only change; if it requires
an engine edit, the abstraction is wrong"*. It is a compliance test for the constitution
and may not be skipped or deleted without an amendment.

**How "zero lines of source code" is actually proved**, since a claim like that is easy to
assert and easy to fake. Three checks, none of which is a matter of opinion:

1. ``data/instruments/ovdp_synthetic_b.toml`` differs from issue A in periodicity, day
   count, business-day rule, coupon rate, term and minimum ticket, and it produces a
   complete result -- schedule, tax, both return figures.
2. **No module in ``src/`` mentions either instrument's id.** A branch on an id is the
   Principle II violation this whole design exists to prevent, and it is greppable.
3. Both issues dispatch through the *same* single entry in the instrument registry. If a
   second issue had needed a second ``InstrumentOps``, that would be an engine change
   wearing a data change's clothes.

**And the other half, which SC-003 does not say but the design depends on**: the records
the loader builds must behave *identically* to the ones the worked examples build by hand.
``TestTheLoaderAndTheHandBuiltRecordsAgree`` asserts that on the canonical form of a whole
projection -- every event, every amount as ``float.hex()``, every charge, every figure --
so it is bit-for-bit equality of the entire result, not agreement on a headline number.
Without it the loader could be quietly wrong in a way no other test in this suite would
see, because every other test builds its inputs in code.
"""

from __future__ import annotations

import ast
import re
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from terezy.core.instruments import registry as instrument_registry
from terezy.core.instruments.interface import Assumptions, DateRange, Holding
from terezy.core.ledger.events import EventKind
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.rates import RealTermsUnavailable
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results import canonical, project
from terezy.core.results.project import Projection
from terezy.core.tax.interface import TaxableEventKind
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError
from tests import synthetic

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
SOURCE_ROOT = REPO_ROOT / "src" / "terezy"

ISSUE_A = "ovdp_synthetic_a"
ISSUE_B = "ovdp_synthetic_b"

# Issue B, by hand. 30/360 makes every quarter exactly 90/360 = 0.25 of a year, so each
# coupon is face x rate x 0.25 x units:
#     1000.00 x 0.1225 x 0.25 = 30.625 per unit
#     30.625 x 10 units       = 306.25 per coupon
# Three years, four coupons a year, so twelve of them:
#     306.25 x 12 = 3675.00 of interest over the life of the holding.
B_COUPON = 306.25
B_COUPON_COUNT = 12
B_TOTAL_INTEREST = 3675.00

# Issue A, by hand, for contrast: act/365 over a 181/184-day semiannual period makes
# every coupon a *different* amount -- which is the visible consequence of the day count
# and the reason SC-012 asks for two issues rather than one.
A_ANNUAL_INTEREST = 1550.00


def _is_prose(statement: ast.stmt) -> bool:
    """Whether a statement is a bare string expression -- a docstring, and never code.

    Every docstring in this repository is one of these, including the attribute
    docstrings that follow a field, which is why this is broader than
    ``ast.get_docstring``.
    """
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def _strip_prose(source: str) -> str:
    """Source with comments and docstrings removed, so a scan sees only behaviour.

    The scan below asks whether any *module* knows about a specific instrument. Prose
    referring to one is not a Principle II violation -- ``specs/001-ovdp-hurdle-rate`` is
    cited in half the docstrings in the project, and the loader's own docstring uses a
    real file name as its example. What would be a violation is a comparison, a lookup or
    a branch, and those survive this stripping while prose does not.

    Comments disappear because ``ast`` never records them; docstrings are removed
    explicitly. A string literal the code actually *uses* is untouched.
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list) and any(isinstance(item, ast.stmt) for item in block):
                kept = [item for item in block if not _is_prose(item)]
                setattr(node, field, kept or [ast.Pass()])
    return ast.unparse(tree)


def _executable_source(path: Path) -> str:
    return _strip_prose(path.read_text(encoding="utf-8"))


def _declarations() -> resolver.Declarations:
    """Everything under ``data/``, resolved. The whole point is that this is all it takes."""
    return resolver.from_data_root(DATA_ROOT)


def _projection(
    declarations: resolver.Declarations,
    instrument_id: str,
    *,
    quantity: float,
    cost: float,
    purchased_on: date,
    horizon_end: date,
) -> Projection:
    declaration = declarations.instruments[instrument_id]
    outcome = project.project(
        declaration,
        Holding(
            owner_id="owner-1",
            instrument_id=instrument_id,
            quantity=quantity,
            purchased_on=purchased_on,
            cost=Money(cost, Currency.UAH, prov.EMPTY),
        ),
        DateRange(start=purchased_on, end=horizon_end),
        Assumptions(consumption_method="fifo", coupon_policy="hold_cash"),
        tax_classes=declarations.tax_classes,
    )
    assert isinstance(outcome, Projection), f"expected a projection, got {outcome!r}"
    return outcome


def _issue_a() -> Projection:
    return _projection(
        _declarations(),
        ISSUE_A,
        quantity=10.0,
        cost=10_000.0,
        purchased_on=date(2026, 1, 15),
        horizon_end=date(2028, 1, 31),
    )


def _issue_b() -> Projection:
    return _projection(
        _declarations(),
        ISSUE_B,
        quantity=10.0,
        cost=10_000.0,
        purchased_on=date(2026, 3, 2),
        horizon_end=date(2029, 3, 31),
    )


class TestBothIssuesLoadFromTheDataRoot:
    """The data root resolves as one set, with the second issue sharing A's tax class."""

    def test_both_instruments_and_the_one_shared_class_are_declared(self) -> None:
        declarations = _declarations()
        assert set(declarations.instruments) == {ISSUE_A, ISSUE_B}
        assert set(declarations.tax_classes) == {"ua_government_bond"}
        # FR-013's second half: another instrument *sharing an existing tax class* is
        # also a data-only change. Both issues point at the same declared class.
        for instrument in declarations.instruments.values():
            assert set(instrument.tax_classes.values()) == {"ua_government_bond"}

    def test_each_declaration_records_the_file_it_came_from(self) -> None:
        declarations = _declarations()
        assert declarations.instrument_files[ISSUE_B].name == f"{ISSUE_B}.toml"
        assert declarations.tax_class_files["ua_government_bond"].name == "ua.toml"

    def test_an_empty_data_root_is_reported_rather_than_read_as_empty(self, tmp_path: Path) -> None:
        """A mistyped root must not look like a repository that declares nothing."""
        (tmp_path / "instruments").mkdir()
        (tmp_path / "tax").mkdir()
        with pytest.raises(DeclarationError) as raised:
            resolver.from_data_root(tmp_path)
        assert raised.value.file == tmp_path / "instruments"


class TestTheSecondIssueProducesACompleteResult:
    """SC-003: a complete result, from a file, with no engine edit."""

    def test_every_part_of_the_result_is_present(self) -> None:
        projection = _issue_b()
        assert projection.schedule.rows
        assert projection.charges
        assert projection.ledger.applied
        assert projection.hurdle.nominal_ytm.value > 0.0
        assert projection.hurdle.nominal_cash_flow_return.value > 0.0
        # Present and explicitly empty, never absent and never a nominal figure standing
        # in for a real one (SC-011). The isinstance check is the assertion: the two are
        # unrelated types, so this cannot pass by holding a rate.
        assert isinstance(projection.hurdle.real, RealTermsUnavailable)
        assert projection.hurdle.real.reason

    def test_each_coupon_is_the_hand_computed_thirty_three_sixtieths_amount(self) -> None:
        """1000.00 x 0.1225 x 0.25 x 10 = 306.25, twelve times over three years.

        The arithmetic is checked in beside the assertion because that is the only way a
        reader verifies the engine rather than trusting it -- and because a 30/360 quarter
        being *exactly* a quarter is what makes this issue's schedule hand-checkable in a
        way issue A's act/365 schedule deliberately is not.
        """
        coupons = [row for row in _issue_b().schedule.rows if row.kind is EventKind.COUPON]
        assert len(coupons) == B_COUPON_COUNT
        for row in coupons:
            assert_money_close(row.gross, Money(B_COUPON, Currency.UAH, prov.EMPTY))
        assert is_close(sum(row.gross.amount for row in coupons), B_TOTAL_INTEREST)

    def test_the_principal_comes_back_at_face_value(self) -> None:
        principal = [
            row for row in _issue_b().schedule.rows if row.kind is EventKind.PRINCIPAL_REPAYMENT
        ]
        assert len(principal) == 1
        assert_money_close(principal[0].gross, Money(10_000.0, Currency.UAH, prov.EMPTY))

    def test_the_exemption_reaches_the_second_issue_with_no_extra_declaration(self) -> None:
        """SC-002 for issue B: exactly zero, because zeroes were recorded and summed."""
        projection = _issue_b()
        assert projection.hurdle.total_tax.amount == 0.0
        assert projection.charges, "a zero charge is still a charge, and it is recorded"
        for charge in projection.charges:
            assert charge.tax_class_id == "ua_government_bond"
            assert charge.provenance.sources, "the zero cites the exemption it applied"

    def test_the_figure_is_marked_unverified_because_its_terms_are(self) -> None:
        """FR-015 across the loader boundary: the file's empty ``verified_on`` arrives."""
        assert prov.is_unverified(_issue_b().hurdle.provenance)

    def test_the_yield_is_the_quarterly_coupon_compounded_within_a_percentage_point(
        self,
    ) -> None:
        """A par bond paying 12.25% quarterly yields about (1 + 0.1225/4)^4 - 1.

        A sanity bound rather than an exact figure: the internal rate of return measures
        time in 30/360 years from the purchase date, so it is close to the compounded
        coupon and need not equal it. What matters is that it is in the right place --
        a wrong day count or a doubled percent conversion would miss by far more than
        this bound allows.
        """
        compounded = (1.0 + 0.1225 / 4.0) ** 4 - 1.0
        assert abs(_issue_b().hurdle.nominal_ytm.value - compounded) < 0.01


class TestEachScheduleReportsItsOwnConventions:
    """SC-012: two issues, different conventions, each schedule saying which it applied."""

    def test_the_two_schedules_report_different_conventions(self) -> None:
        conventions_a = {row.conventions for row in _issue_a().schedule.rows}
        conventions_b = {row.conventions for row in _issue_b().schedule.rows}
        assert len(conventions_a) == 1, "one issue, one set of conventions"
        assert len(conventions_b) == 1
        applied_a = conventions_a.pop()
        applied_b = conventions_b.pop()

        assert (applied_a.periodicity, applied_a.day_count, applied_a.business_day_rule) == (
            "semiannual",
            "act/365",
            "following",
        )
        assert (applied_b.periodicity, applied_b.day_count, applied_b.business_day_rule) == (
            "quarterly",
            "30/360",
            "modified_following",
        )
        assert applied_a != applied_b, (
            "if these matched, the test would be comparing one issue with itself and "
            "SC-012 would be unproven"
        )

    def test_the_reported_conventions_are_the_declared_ones(self) -> None:
        """Reported, not assumed: the schedule's claim is checked against the file."""
        declarations = _declarations()
        for instrument_id, projection in ((ISSUE_A, _issue_a()), (ISSUE_B, _issue_b())):
            terms = declarations.instruments[instrument_id].terms
            for row in projection.schedule.rows:
                assert row.conventions.periodicity == terms.periodicity
                assert row.conventions.day_count == terms.day_count
                assert row.conventions.business_day_rule == terms.business_day_rule

    def test_the_two_issues_produce_different_schedules_and_different_figures(self) -> None:
        """The conventions have to *matter*, or reporting them proves nothing.

        Issue A's act/365 semiannual coupons are each a different amount; issue B's
        30/360 quarterly coupons are each identical. That difference is the day count
        doing its job.
        """
        coupons_a = [
            row.gross.amount for row in _issue_a().schedule.rows if row.kind is EventKind.COUPON
        ]
        coupons_b = [
            row.gross.amount for row in _issue_b().schedule.rows if row.kind is EventKind.COUPON
        ]
        assert len(set(coupons_a)) > 1, "act/365 periods differ in length, so coupons differ"
        assert len(set(coupons_b)) == 1, "every 30/360 quarter is exactly a quarter"
        assert is_close(sum(coupons_a), 2 * A_ANNUAL_INTEREST)
        assert not is_close(
            _issue_a().hurdle.nominal_ytm.value, _issue_b().hurdle.nominal_ytm.value
        )


class TestNoSourceCodeKnowsAboutEitherIssue:
    """The greppable half of SC-003, and the honest one.

    "Zero lines of source code changed" is a claim about the *engine*, and the way it
    fails is a branch on an instrument id. That is detectable, so it is detected here
    rather than asserted in a commit message.
    """

    def test_no_module_mentions_an_instrument_id(self) -> None:
        pattern = re.compile(f"{ISSUE_A}|{ISSUE_B}|ovdp", re.IGNORECASE)
        found = {
            str(path.relative_to(SOURCE_ROOT))
            for path in sorted(SOURCE_ROOT.rglob("*.py"))
            if pattern.search(_executable_source(path))
        }
        assert not found, (
            "a module names a specific instrument, so that instrument's behaviour is "
            f"code rather than data (Principle II): {sorted(found)}"
        )

    def test_the_scan_would_catch_a_branch_on_an_id(self) -> None:
        """A scan that can never fail protects nothing, so prove it can.

        Also proves the docstring stripping does not throw away real code: a string
        *compared against* survives, while a string that only describes survives nowhere.
        """
        assert re.compile(ISSUE_A).search(
            _strip_prose(f'''
"""A docstring mentioning nothing at all."""
def f(declaration: object) -> bool:
    """Another docstring."""
    return declaration.id == "{ISSUE_A}"
''')
        )
        assert not re.compile(ISSUE_A).search(
            _strip_prose(f'''
"""A module docstring about {ISSUE_A}, which is prose and not behaviour."""
X: int = 1
"""An attribute docstring about {ISSUE_A}."""
# A comment about {ISSUE_A}.
''')
        )

    def test_both_issues_dispatch_through_the_one_registered_class(self) -> None:
        declarations = _declarations()
        classes = {instrument.instrument_class for instrument in declarations.instruments.values()}
        assert classes == {instrument_registry.FIXED_INCOME}
        assert set(instrument_registry.REGISTRY) == {instrument_registry.FIXED_INCOME}, (
            "a second issue that had needed a second registry entry would be an engine "
            "change wearing a data change's clothes"
        )

    def test_adding_a_third_issue_needs_a_file_and_nothing_else(self, tmp_path: Path) -> None:
        """The claim under the loosest possible conditions: a file this repo never saw.

        A copy of issue B with a new id, a different periodicity again and a different
        day count again, written to a scratch directory and projected. Nothing in ``src``
        changes, nothing is registered, and no fixture is edited.
        """
        (tmp_path / "instruments").mkdir()
        (tmp_path / "tax").mkdir()
        text = (
            (DATA_ROOT / "instruments" / f"{ISSUE_B}.toml")
            .read_text(encoding="utf-8")
            .replace(f'id           = "{ISSUE_B}"', 'id           = "ovdp_synthetic_c"')
            .replace('periodicity       = "quarterly"', 'periodicity       = "annual"')
            .replace('day_count         = "30/360"', 'day_count         = "act/act"')
            .replace('business_day_rule = "modified_following"', 'business_day_rule = "none"')
        )
        (tmp_path / "instruments" / "ovdp_synthetic_c.toml").write_text(text, encoding="utf-8")
        (tmp_path / "tax" / "ua.toml").write_text(
            (DATA_ROOT / "tax" / "ua.toml").read_text(encoding="utf-8"), encoding="utf-8"
        )

        projection = _projection(
            resolver.from_data_root(tmp_path),
            "ovdp_synthetic_c",
            quantity=10.0,
            cost=10_000.0,
            purchased_on=date(2026, 3, 2),
            horizon_end=date(2029, 3, 31),
        )
        coupons = [row for row in projection.schedule.rows if row.kind is EventKind.COUPON]
        assert len(coupons) == 3, "annual coupons over a three-year term"
        assert projection.schedule.rows[0].conventions.day_count == "act/act"
        assert projection.hurdle.total_tax.amount == 0.0


class TestTheLoaderAndTheHandBuiltRecordsAgree:
    """The loader's records behave **identically** to the hand-built ones. Bit for bit.

    Everything else in this suite builds its inputs in code, so a loader that attached
    the wrong provenance, divided a percentage twice, or dropped a convention would be
    invisible to all of it. This closes that gap by projecting the *same* purchase twice
    -- once from ``data/instruments/ovdp_synthetic_a.toml``, once from the declaration
    ``tests/synthetic`` builds by hand -- and comparing the canonical form of the whole
    result: every ledger event, every amount as ``float.hex()``, every charge, both return
    figures.

    Equality rather than tolerance, deliberately. The two paths perform the *same*
    arithmetic on the same values, so any difference at all is a difference in the inputs,
    and a tolerance would hide exactly the class of bug this test exists to find. (The
    percent conversion is exact here for the same reason: ``15.5`` is representable, and
    ``15.5 / 100`` rounds to the same double as the literal ``0.155``.)

    The canonical form deliberately excludes provenance, so the marks are asserted
    separately below.
    """

    @staticmethod
    def _hand_built() -> tuple[object, object]:
        loaded = loader.instrument_from_file(DATA_ROOT / "instruments" / f"{ISSUE_A}.toml")
        exempt = replace(synthetic.EXEMPT_CLASS, id="ua_government_bond")
        hand = synthetic.declaration(
            id=loaded.id,
            # Copied rather than restated: the name appears verbatim in the purchase
            # event's causation string, so a differing name would fail this comparison
            # for a reason that is not about the money.
            name=loaded.name,
            tax_classes={
                TaxableEventKind.COUPON: exempt.id,
                TaxableEventKind.DISPOSAL_GAIN: exempt.id,
            },
        )
        holding = synthetic.holding(instrument_id=loaded.id)
        from_file = project.project(
            loaded,
            holding,
            synthetic.horizon(),
            synthetic.assumptions(),
            tax_classes={exempt.id: exempt},
        )
        from_code = project.project(
            hand,
            holding,
            synthetic.horizon(),
            synthetic.assumptions(),
            tax_classes={exempt.id: exempt},
        )
        assert isinstance(from_file, Projection)
        assert isinstance(from_code, Projection)
        return from_file, from_code

    def test_the_two_declarations_are_the_same_record(self) -> None:
        loaded = loader.instrument_from_file(DATA_ROOT / "instruments" / f"{ISSUE_A}.toml")
        hand = synthetic.declaration(id=loaded.id, name=loaded.name)
        assert loaded.terms.coupon_rate == hand.terms.coupon_rate
        assert loaded.terms.face_value == hand.terms.face_value, (
            "money equality ignores provenance, so this compares amount and currency"
        )
        assert loaded.terms.issue_date == hand.terms.issue_date
        assert loaded.terms.maturity_date == hand.terms.maturity_date
        assert loaded.terms.periodicity == hand.terms.periodicity
        assert loaded.terms.day_count == hand.terms.day_count
        assert loaded.terms.business_day_rule == hand.terms.business_day_rule
        assert loaded.constraints.min_ticket == hand.constraints.min_ticket
        assert loaded.constraints.min_unit == hand.constraints.min_unit
        assert loaded.is_synthetic == hand.is_synthetic

    def test_the_whole_projection_is_identical(self) -> None:
        from_file, from_code = self._hand_built()
        assert isinstance(from_file, Projection)
        assert isinstance(from_code, Projection)
        assert canonical.of_projection(from_file) == canonical.of_projection(from_code)

    def test_both_paths_carry_the_unverified_mark_that_provenance_excludes(self) -> None:
        """The one thing the canonical form cannot compare, compared separately.

        Provenance is excluded from the digest on purpose (filling in a ``verified_on``
        must not change a result's identity), so an identical digest says nothing about
        the marks. Both paths declare their terms unverified, and both must say so.
        """
        from_file, from_code = self._hand_built()
        assert isinstance(from_file, Projection)
        assert isinstance(from_code, Projection)
        assert prov.is_unverified(from_file.hurdle.provenance)
        assert prov.is_unverified(from_code.hurdle.provenance)
        # And the loader's marks name where they came from, which the hand-built ones
        # cannot: a figure traces back to the file and table that declared it.
        assert {ref.id for ref in from_file.hurdle.provenance.sources} >= {
            "instruments/ovdp_synthetic_a.toml#instrument.terms"
        }
