"""A battery of deliberately broken declaration files, one case per enforced rule.

**H2**, FR-014, FR-016 and SC-004 in one place: *"every malformed, unrecognised, missing
or duplicated field in a declaration file produces an error naming the file and the
field, and no such case results in a substituted default"*. The enforced-rules table in
``specs/001-ovdp-hurdle-rate/contracts/declaration-schema.md`` has a row for each case
below, and the rows are the reason the cases exist rather than the other way round.

**Every case is a mutation of a file that is shipped and valid.** The broken variants are
produced by editing the text of ``data/instruments/ovdp_synthetic_a.toml`` and
``data/tax/ua.toml``, so each test also proves the real file contains what the test
thinks it contains -- a battery written against an invented template would keep passing
after the shipped format changed underneath it, which is the way a suite like this rots.

**What "naming the field" is checked against.** Two assertions, applied to every case by
:func:`_assert_names_file_and_field`: the raised error's ``file`` is the file that was
loaded, and its ``field_path`` locates the problem. A message that named the field but
not the file would satisfy pydantic's default rendering and fail FR-016, which is
precisely why the loader adapts ``ValidationError`` rather than letting it out.

**What is deliberately *not* a load-time error.** ``maturity_date`` on or before
``issue_date`` is a well-formed declaration of an impossible instrument. The contract
routes it to a typed ``InconsistentTerms`` failure from the projection, not to a
``DeclarationError``, and the last test here asserts exactly that -- the file loads, and
the *engine* refuses. Moving that check into the loader would put instrument mathematics
in the data layer.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Mapping
from datetime import date, timedelta
from pathlib import Path
from typing import Final

import pydantic
import pytest
from pydantic import BaseModel

from terezy.core.errors import InconsistentTerms
from terezy.core.instruments.interface import Assumptions, DateRange, Holding
from terezy.core.ledger.events import EventKind
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.results import project
from terezy.core.results.project import Projection
from terezy.core.tax.interface import TaxableEventKind
from terezy.core.tax.schedule import RateUndeclaredBefore
from terezy.data.declarations import loader, resolver, schema
from terezy.data.declarations.errors import DeclarationError
from tests import declared_terms

pytestmark = pytest.mark.contract

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
GROUPS = DATA_ROOT / "groups.toml"
INSTRUMENT_A = DATA_ROOT / "instruments" / "ovdp_synthetic_a.toml"
INSTRUMENT_B = DATA_ROOT / "instruments" / "ovdp_synthetic_b.toml"
TAX_UA = DATA_ROOT / "tax" / "ua.toml"


def _is_comment(line: str) -> bool:
    """Whether a line is a TOML comment.

    Both helpers below skip comments, and they have to: the shipped fixtures explain
    themselves in prose that quotes their own field names, so a naive text search would
    edit the explanation of ``is_synthetic`` instead of the declaration of it -- leaving
    the file valid and the test asserting an error that never came.
    """
    return line.lstrip().startswith("#")


GOVERNMENT_BOND: Final = "ua_government_bond"

COUPON: Final = TaxableEventKind.COUPON

EXEMPTION_PROVISIONS: Final = {
    COUPON: "165.1.2",
    TaxableEventKind.DISPOSAL_GAIN: "165.1.52",
}
"""Which subparagraph of the ПКУ exempts each kind of ОВДП income.

Two, and the distinction is the point. пп. 165.1.52 is «інвестиційний прибуток від операцій»
-- a disposal. Interest accrued on state securities is пп. 165.1.2, a different provision
about a different thing, and a class that charges coupons needs it named.
"""

_PROVISION: Final = re.compile(r"\b\d+\.\d+\.\d+(?:\.\d+)?\b")


def _provisions_behind(sources: Provenance) -> set[str]:
    """Every dotted provision number a figure's citations name.

    Extracted rather than substring-matched so that a citation naming 165.1.52 cannot satisfy
    a test looking for 165.1.2 by accident, and so that a citation that named neither would
    have to *invent* a number to pass rather than merely be vague.
    """
    return {found for source in sources.sources for found in _PROVISION.findall(source.citation)}


def _replace(text: str, old: str, new: str) -> str:
    """One textual edit to the first declaring line, refusing to silently do nothing.

    The assertion is the point: ``str.replace`` on a string that does not contain the
    needle returns the string unchanged, so without this a renamed field in the shipped
    file would turn every case below into a test of a *valid* file that expects an
    error -- failing for a reason with nothing to do with the rule under test.
    """
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if old in line and not _is_comment(line):
            lines[index] = line.replace(old, new, 1)
            return "".join(lines)
    pytest.fail(f"the shipped fixture no longer declares {old!r}; this test is stale")


def _drop_line(text: str, needle: str) -> str:
    """Remove the one declaring line containing ``needle`` -- how a field goes missing."""
    lines = text.splitlines(keepends=True)
    matching = [line for line in lines if needle in line and not _is_comment(line)]
    assert len(matching) == 1, f"expected exactly one line declaring {needle!r}, got {matching!r}"
    return "".join(line for line in lines if line not in matching)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    target = tmp_path / name
    target.write_text(text, encoding="utf-8")
    return target


def _instrument(tmp_path: Path, text: str, name: str = "broken.toml") -> Path:
    return _write(tmp_path, name, text)


def _assert_names_file_and_field(
    raised: DeclarationError,
    *,
    file: Path,
    field_path: str,
) -> None:
    """Both halves of FR-016, asserted together because half of it is worthless.

    The rendered message is checked as well as the fields, because the message is what a
    person maintaining the file by hand actually sees.
    """
    assert raised.file == file, "the error must name the file it came from"
    assert raised.field_path == field_path, (
        f"the error must locate the field; expected {field_path!r}, got {raised.field_path!r}"
    )
    rendered = str(raised)
    assert file.name in rendered
    assert field_path in rendered
    assert raised.problem, "an error with no plain-language problem explains nothing"


class TestTheShippedFilesLoad:
    """The baseline. Every broken case below is a mutation of these, so they must work."""

    def test_issue_a_loads_with_its_declared_terms_as_fractions(self) -> None:
        declaration = loader.instrument_from_file(INSTRUMENT_A)
        assert declaration.id == "ovdp_synthetic_a"
        assert declaration.instrument_class == "fixed_income"
        assert declaration.currency is Currency.UAH
        assert declaration.is_synthetic is True
        # 15.5 in the file, 0.155 in the core -- divided by 100 exactly once, at the
        # loader boundary. Asserted as **exact** equality, not approximately: 15.5 is
        # exactly representable, so IEEE division returns the nearest double to 0.155,
        # which is the literal `0.155` bit for bit. An approximate assertion here would
        # pass just as happily on a rate that was off by a rounding step, and the whole
        # point of this line is that the conversion happens once and lands exactly.
        terms = declared_terms.contractual(declaration)
        assert terms.coupon_rate == 0.155
        assert terms.issue_date == date(2026, 1, 15)
        assert terms.maturity_date == date(2028, 1, 15)
        assert terms.periodicity == "semiannual"
        assert terms.day_count == "act/365"
        assert terms.business_day_rule == "following"
        assert declaration.constraints.min_unit == 1.0
        assert declaration.tax_classes == {
            TaxableEventKind.COUPON: "ua_government_bond",
            TaxableEventKind.DISPOSAL_GAIN: "ua_government_bond",
        }

    def test_the_tax_class_loads_its_zero_rates_as_fractions(self) -> None:
        classes = loader.tax_classes_from_file(TAX_UA)
        exempt = next(declared for declared in classes if declared.id == "ua_government_bond")
        (only_entry,) = exempt.rates
        assert only_entry.pit_rate == 0.0
        assert only_entry.levy_rate == 0.0
        assert exempt.applies_to == frozenset(
            {TaxableEventKind.COUPON, TaxableEventKind.DISPOSAL_GAIN}
        )

    def test_an_empty_verified_on_loads_and_marks_the_value_unverified(self) -> None:
        """FR-014's permitted case, and the one FR-015 depends on.

        Empty is not absent. The file loads, and everything it declares carries a source
        whose verification date is ``None``, which is what makes the mark propagate
        rather than being remembered by whoever reads the file.
        """
        declaration = loader.instrument_from_file(INSTRUMENT_A)
        assert prov.is_unverified(declaration.terms.provenance)
        assert prov.is_unverified(declaration.constraints.provenance)
        assert prov.is_unverified(loader.tax_classes_from_file(TAX_UA)[0].rates[0].provenance)

    def test_every_source_ref_names_the_file_and_table_it_came_from(self) -> None:
        """A figure must trace back to *where* it was declared, not just to a citation.

        Two tables in one file are two different observations -- a yield and a minimum
        ticket -- so they get different ids, and each id says which table it came from.
        """
        declaration = loader.instrument_from_file(INSTRUMENT_A)
        terms_ids = {ref.id for ref in declaration.terms.provenance.sources}
        constraint_ids = {ref.id for ref in declaration.constraints.provenance.sources}
        assert terms_ids == {"instruments/ovdp_synthetic_a.toml#instrument.terms"}
        assert constraint_ids == {"instruments/ovdp_synthetic_a.toml#instrument.constraints"}
        exempt = next(
            declared
            for declared in loader.tax_classes_from_file(TAX_UA)
            if declared.id == "ua_government_bond"
        )
        assert {ref.id for ref in exempt.rates[0].provenance.sources} == {
            "tax/ua.toml#jurisdiction.tax_class[ua_government_bond].rate[0]"
        }


class TestUnrecognisedField:
    """Row 1: an unrecognised field is an error naming file and field (FR-016)."""

    def test_an_unknown_field_in_a_nested_table_is_reported(self, tmp_path: Path) -> None:
        text = _replace(
            INSTRUMENT_A.read_text(encoding="utf-8"),
            "min_unit     = 1.0",
            "min_unit     = 1.0\nmin_lot_size = 7.0",
        )
        broken = _instrument(tmp_path, text)
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(broken)
        _assert_names_file_and_field(
            raised.value,
            file=broken,
            field_path="instrument.constraints.min_lot_size",
        )
        assert raised.value.remedy is not None

    def test_an_unknown_top_level_table_is_reported(self, tmp_path: Path) -> None:
        """A whole table nobody reads is the most dangerous kind of typo.

        ``[instrument.limits]`` sitting unread beside ``[instrument.constraints]`` would
        look like a declared limit and be none, which is exactly the silent default
        ``extra="forbid"`` exists to prevent.
        """
        text = INSTRUMENT_A.read_text(encoding="utf-8") + "\n[instrument.limits]\ncap = 5.0\n"
        broken = _instrument(tmp_path, text)
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="instrument.limits")


class TestMissingRequiredField:
    """Row 2: an absent field is an error, and **no default is substituted**."""

    @pytest.mark.parametrize(
        ("needle", "field_path"),
        [
            ("coupon_rate_pct", "instrument.terms.coupon_rate_pct"),
            ("face_value", "instrument.terms.face_value"),
            ("periodicity", "instrument.terms.periodicity"),
            ("day_count", "instrument.terms.day_count"),
            ("business_day_rule", "instrument.terms.business_day_rule"),
            ("is_synthetic", "instrument.is_synthetic"),
            ("min_ticket", "instrument.constraints.min_ticket"),
            ("min_unit", "instrument.constraints.min_unit"),
        ],
    )
    def test_a_missing_field_is_reported_rather_than_defaulted(
        self, tmp_path: Path, needle: str, field_path: str
    ) -> None:
        broken = _instrument(tmp_path, _drop_line(INSTRUMENT_A.read_text(encoding="utf-8"), needle))
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path=field_path)
        assert (
            "default" in raised.value.problem.lower()
            or "default" in (raised.value.remedy or "").lower()
        ), "the message should say plainly that nothing was substituted"

    def test_an_empty_tax_classes_table_is_reported(self, tmp_path: Path) -> None:
        """Present but empty is the same claim as absent, and gets the same answer.

        Declaring the table and then leaving it blank is the more likely mistake of the
        two -- it survives a glance -- so it is refused explicitly rather than falling
        through as "no income kinds to tax".
        """
        text = INSTRUMENT_A.read_text(encoding="utf-8")
        broken = _instrument(
            tmp_path, text[: text.index("[instrument.tax_classes]")] + "[instrument.tax_classes]\n"
        )
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="instrument.tax_classes")

    def test_a_jurisdiction_declaring_no_tax_class_is_reported(self, tmp_path: Path) -> None:
        """An empty rule pack loads to nothing and would fail later, elsewhere.

        Refused here so the message names the file that is empty rather than the
        instrument that happened to be projected first.
        """
        text = TAX_UA.read_text(encoding="utf-8")
        empty = _write(
            tmp_path,
            "ua_empty.toml",
            text[: text.index("[[jurisdiction.tax_class]]")] + "tax_class = []\n",
        )
        with pytest.raises(DeclarationError) as raised:
            loader.tax_classes_from_file(empty)
        _assert_names_file_and_field(raised.value, file=empty, field_path="jurisdiction.tax_class")

    def test_a_missing_tax_classes_table_is_reported(self, tmp_path: Path) -> None:
        """An instrument with no declared tax treatment is not an untaxed instrument.

        Dropping the table entirely is the easy version of the mistake FR-016 and
        Principle I both guard: absence of a rule and a declared exemption are opposite
        claims, and only one of them is cited.
        """
        text = INSTRUMENT_A.read_text(encoding="utf-8")
        broken = _instrument(tmp_path, text[: text.index("[instrument.tax_classes]")])
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="instrument.tax_classes")


class TestWrongType:
    """Row 3: ``strict=True`` means no coercion. ``"15.5"`` is not ``15.5``."""

    @pytest.mark.parametrize(
        ("old", "new", "field_path"),
        [
            (
                "coupon_rate_pct   = 15.5",
                'coupon_rate_pct   = "15.5"',
                "instrument.terms.coupon_rate_pct",
            ),
            (
                "face_value        = 1000.0",
                'face_value        = "1000"',
                "instrument.terms.face_value",
            ),
            ("is_synthetic = true", 'is_synthetic = "true"', "instrument.is_synthetic"),
            ("min_unit     = 1.0", "min_unit     = [1.0]", "instrument.constraints.min_unit"),
            ('id           = "ovdp_synthetic_a"', "id           = 1", "instrument.id"),
        ],
    )
    def test_a_quoted_number_is_not_quietly_a_number(
        self, tmp_path: Path, old: str, new: str, field_path: str
    ) -> None:
        broken = _instrument(tmp_path, _replace(INSTRUMENT_A.read_text(encoding="utf-8"), old, new))
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path=field_path)

    def test_a_wrong_type_inside_an_array_of_tables_names_its_index(self, tmp_path: Path) -> None:
        """``jurisdiction.tax_class[0].rate[0].pit_rate_pct`` -- the index, because that is all
        pydantic has.

        A malformed entry may not carry a usable ``id`` to name it by, so the shape
        errors count entries the way ``scripts/check_provenance.py`` prints them. The
        loader's own semantic errors name the entry by id instead, which is why both
        renderings exist.
        """
        broken = _write(
            tmp_path,
            "ua_wrong_type.toml",
            _replace(
                TAX_UA.read_text(encoding="utf-8"), "pit_rate_pct   = 0.0", 'pit_rate_pct   = "0"'
            ),
        )
        with pytest.raises(DeclarationError) as raised:
            loader.tax_classes_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="jurisdiction.tax_class[0].rate[0].pit_rate_pct"
        )


class TestVerifiedOnMustBePresent:
    """Row 4: empty is fine, absent is not (FR-014)."""

    def test_dropping_verified_on_from_a_sourced_table_is_an_error(self, tmp_path: Path) -> None:
        text = INSTRUMENT_A.read_text(encoding="utf-8")
        # Two tables carry the key; drop the one in [instrument.terms] only.
        head, sep, tail = text.partition("[instrument.constraints]")
        broken = _instrument(tmp_path, _drop_line(head, "verified_on") + sep + tail)
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="instrument.terms.verified_on"
        )

    def test_a_verified_date_loads_and_clears_the_mark(self, tmp_path: Path) -> None:
        """The other direction: filling the key in must actually change the mark.

        Without this the mark could be hard-wired to "always unverified" and every
        propagation test in the suite would still pass.
        """
        text = INSTRUMENT_A.read_text(encoding="utf-8")
        head, sep, tail = text.partition("[instrument.constraints]")
        filled = _instrument(
            tmp_path,
            _replace(head, 'verified_on       = ""', 'verified_on       = "2026-08-21"')
            + sep
            + tail,
        )
        declaration = loader.instrument_from_file(filled)
        assert not prov.is_unverified(declaration.terms.provenance)
        assert prov.is_unverified(declaration.constraints.provenance), (
            "the other table is still unverified; the mark is per source, not per file"
        )

    @pytest.mark.parametrize(
        ("old", "new", "field_path"),
        [
            (
                'retrieved_on      = "2026-08-21"',
                'retrieved_on      = "21/08/2026"',
                "instrument.terms.retrieved_on",
            ),
            (
                'verified_on       = ""',
                'verified_on       = "not yet"',
                "instrument.terms.verified_on",
            ),
            (
                'issue_date        = "2026-01-15"',
                'issue_date        = "2026-13-40"',
                "instrument.terms.issue_date",
            ),
        ],
    )
    def test_a_date_that_is_not_a_date_is_reported(
        self, tmp_path: Path, old: str, new: str, field_path: str
    ) -> None:
        broken = _instrument(tmp_path, _replace(INSTRUMENT_A.read_text(encoding="utf-8"), old, new))
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path=field_path)


class TestNumericTableWithoutACitation:
    """Row 5: a table carrying observed numbers must carry its source (FR-014).

    The same rule ``scripts/check_provenance.py`` enforces over the committed files, at
    the loader this time, so a file that never reaches the gate still cannot get in.
    """

    @pytest.mark.parametrize("needle", ["source", "retrieved_on"])
    def test_a_sourceless_table_of_numbers_cannot_be_loaded(
        self, tmp_path: Path, needle: str
    ) -> None:
        text = INSTRUMENT_A.read_text(encoding="utf-8")
        head, sep, tail = text.partition("[instrument.constraints]")
        broken = _instrument(tmp_path, head + sep + _drop_line(tail, needle))
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path=f"instrument.constraints.{needle}"
        )

    def test_an_empty_citation_is_not_a_citation(self, tmp_path: Path) -> None:
        text = INSTRUMENT_A.read_text(encoding="utf-8")
        head, sep, tail = text.partition("[instrument.constraints]")
        broken = _instrument(
            tmp_path,
            head
            + sep
            + _replace(tail, 'source       = "SYNTHETIC', 'source       = ""  # ("SYNTHETIC'),
        )
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="instrument.constraints.source"
        )


class TestDuplicateIdentifiersAcrossFiles:
    """Row 6: a duplicate id is an error naming **both** files.

    Structurally invisible to pydantic, which sees one file at a time -- so this is the
    resolver's job, and it runs only after every file has parsed on its own.
    """

    def test_two_files_declaring_the_same_instrument_id_are_refused(self, tmp_path: Path) -> None:
        original = INSTRUMENT_A.read_text(encoding="utf-8")
        first = _write(tmp_path, "first.toml", original)
        second = _write(tmp_path, "second.toml", original)
        with pytest.raises(DeclarationError) as raised:
            resolver.resolve(
                instrument_files=(first, second), tax_files=(TAX_UA,), groups_file=GROUPS
            )
        assert raised.value.file == second
        assert str(first) in raised.value.problem, "the error must name both files"
        assert "ovdp_synthetic_a" in raised.value.problem

    def test_two_tax_classes_with_the_same_id_are_refused(self, tmp_path: Path) -> None:
        """Including within a single file: the array of tables makes that easy to do."""
        text = TAX_UA.read_text(encoding="utf-8")
        duplicated = _write(
            tmp_path, "ua_twice.toml", text + text[text.index("[[jurisdiction.tax_class]]") :]
        )
        with pytest.raises(DeclarationError) as raised:
            resolver.resolve(
                instrument_files=(INSTRUMENT_A,), tax_files=(duplicated,), groups_file=GROUPS
            )
        assert raised.value.file == duplicated
        assert "ua_government_bond" in raised.value.problem


class TestUnresolvedTaxClassReference:
    """Row 7: a reference to an undeclared class names the id and the instrument.

    Never treated as an exemption. A missing rule and a declared zero are opposite
    claims and only one of them is cited (Principle I).
    """

    def test_an_undeclared_class_is_refused_naming_it_and_the_referrer(
        self, tmp_path: Path
    ) -> None:
        broken = _instrument(
            tmp_path,
            _replace(
                INSTRUMENT_A.read_text(encoding="utf-8"),
                'coupon        = "ua_government_bond"',
                'coupon        = "ua_deposit_interest"',
            ),
        )
        with pytest.raises(DeclarationError) as raised:
            resolver.resolve(instrument_files=(broken,), tax_files=(TAX_UA,), groups_file=GROUPS)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="instrument.tax_classes.coupon"
        )
        assert "ua_deposit_interest" in raised.value.problem
        assert "ovdp_synthetic_a" in raised.value.problem

    def test_a_class_that_does_not_apply_to_the_declared_kind_is_refused(
        self, tmp_path: Path
    ) -> None:
        """A class that exists but does not cover the income kind is not a match either.

        ``applies_to`` is the class's own statement of what it speaks about, and the tax
        rule refuses a kind outside it. Catching that at load time turns a run-time
        refusal into a message about the file that caused it.
        """
        narrowed = _write(
            tmp_path,
            "ua_coupon_only.toml",
            _replace(
                TAX_UA.read_text(encoding="utf-8"),
                'applies_to = ["coupon", "disposal_gain"]',
                'applies_to = ["coupon"]',
            ),
        )
        with pytest.raises(DeclarationError) as raised:
            resolver.resolve(
                instrument_files=(INSTRUMENT_A,), tax_files=(narrowed,), groups_file=GROUPS
            )
        _assert_names_file_and_field(
            raised.value, file=INSTRUMENT_A, field_path="instrument.tax_classes.disposal_gain"
        )
        assert "disposal_gain" in raised.value.problem

    @pytest.mark.parametrize(
        ("old", "new", "field_path"),
        [
            (
                'coupon        = "ua_government_bond"',
                'dividend      = "ua_government_bond"',
                "instrument.tax_classes.dividend",
            ),
            (
                'applies_to = ["coupon", "disposal_gain"]',
                'applies_to = ["coupon", "windfall"]',
                "jurisdiction.tax_class[ua_government_bond].applies_to",
            ),
        ],
    )
    def test_an_unknown_taxable_event_kind_is_reported(
        self, tmp_path: Path, old: str, new: str, field_path: str
    ) -> None:
        """The event kinds are a closed set in the core, so a typo cannot pass through."""
        if field_path.startswith("instrument"):
            broken = _instrument(
                tmp_path, _replace(INSTRUMENT_A.read_text(encoding="utf-8"), old, new)
            )
            with pytest.raises(DeclarationError) as raised:
                loader.instrument_from_file(broken)
        else:
            broken = _write(
                tmp_path, "ua_bad_kind.toml", _replace(TAX_UA.read_text(encoding="utf-8"), old, new)
            )
            with pytest.raises(DeclarationError) as raised:
                loader.tax_classes_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path=field_path)


class TestUnknownConventionName:
    """Row 8: an unrecognised convention names the file and the value (FR-021).

    ``tests/contract/test_unknown_convention.py`` owns the other half -- that the core
    refuses to invent a convention. This half is the loader naming the file, which is
    the part the core structurally cannot do.
    """

    @pytest.mark.parametrize(
        ("old", "new", "field_path", "value"),
        [
            (
                'day_count         = "act/365"',
                'day_count         = "act/360"',
                "instrument.terms.day_count",
                "act/360",
            ),
            (
                'periodicity       = "semiannual"',
                'periodicity       = "monthly"',
                "instrument.terms.periodicity",
                "monthly",
            ),
            (
                'business_day_rule = "following"',
                'business_day_rule = "preceding"',
                "instrument.terms.business_day_rule",
                "preceding",
            ),
            (
                'class        = "fixed_income"',
                'class        = "equity"',
                "instrument.class",
                "equity",
            ),
            ('currency     = "UAH"', 'currency     = "EUR"', "instrument.currency", "EUR"),
        ],
    )
    def test_an_unknown_declared_name_names_the_file_the_field_and_the_value(
        self, tmp_path: Path, old: str, new: str, field_path: str, value: str
    ) -> None:
        broken = _instrument(tmp_path, _replace(INSTRUMENT_A.read_text(encoding="utf-8"), old, new))
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path=field_path)
        assert value in raised.value.problem, "the message must quote the offending value"
        assert raised.value.remedy, "an unknown name is a typo; the remedy lists what works"


class TestNonPositiveAmounts:
    """Row 10: a face value, minimum ticket or minimum unit of zero or less is refused.

    Not clamped, not defaulted. A zero minimum unit would make the reinvestment
    remainder of FR-020 a division by zero, and a zero face value would make every
    coupon zero while the schedule still looked complete.
    """

    @pytest.mark.parametrize(
        ("old", "new", "field_path"),
        [
            (
                "face_value        = 1000.0",
                "face_value        = 0.0",
                "instrument.terms.face_value",
            ),
            (
                "face_value        = 1000.0",
                "face_value        = -1000.0",
                "instrument.terms.face_value",
            ),
            ("min_ticket   = 1000.0", "min_ticket   = 0.0", "instrument.constraints.min_ticket"),
            ("min_unit     = 1.0", "min_unit     = -1.0", "instrument.constraints.min_unit"),
            (
                "coupon_rate_pct   = 15.5",
                "coupon_rate_pct   = -15.5",
                "instrument.terms.coupon_rate_pct",
            ),
        ],
    )
    def test_a_non_positive_amount_is_refused(
        self, tmp_path: Path, old: str, new: str, field_path: str
    ) -> None:
        broken = _instrument(tmp_path, _replace(INSTRUMENT_A.read_text(encoding="utf-8"), old, new))
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path=field_path)

    def test_a_zero_coupon_rate_is_valid_and_is_not_confused_with_a_missing_one(
        self, tmp_path: Path
    ) -> None:
        """The boundary case, stated so the positivity check cannot creep onto it.

        A zero-coupon bond is a real instrument. What is forbidden is a *negative* rate
        and an *absent* one, and those are different files.
        """
        zero = _instrument(
            tmp_path,
            _replace(
                INSTRUMENT_A.read_text(encoding="utf-8"),
                "coupon_rate_pct   = 15.5",
                "coupon_rate_pct   = 0.0",
            ),
        )
        assert declared_terms.contractual(loader.instrument_from_file(zero)).coupon_rate == 0.0

    @pytest.mark.parametrize(
        ("old", "new", "field_path"),
        [
            (
                "pit_rate_pct   = 0.0",
                "pit_rate_pct   = -18.0",
                "jurisdiction.tax_class[ua_government_bond].rate[0].pit_rate_pct",
            ),
            (
                'applies_to = ["coupon", "disposal_gain"]',
                "applies_to = []",
                "jurisdiction.tax_class[ua_government_bond].applies_to",
            ),
        ],
    )
    def test_a_tax_class_with_an_impossible_field_is_refused(
        self, tmp_path: Path, old: str, new: str, field_path: str
    ) -> None:
        broken = _write(
            tmp_path, "ua_broken.toml", _replace(TAX_UA.read_text(encoding="utf-8"), old, new)
        )
        with pytest.raises(DeclarationError) as raised:
            loader.tax_classes_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path=field_path)


class TestMalformedFile:
    """Rows 11 and 12: broken TOML, and a file that is not there at all."""

    def test_unparseable_toml_names_the_file(self, tmp_path: Path) -> None:
        broken = _instrument(
            tmp_path, "[instrument\nid = 'no closing bracket'\n", name="garbled.toml"
        )
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(broken)
        assert raised.value.file == broken
        assert "TOML" in raised.value.problem or "toml" in raised.value.problem

    def test_a_missing_file_is_reported_rather_than_treated_as_empty(self, tmp_path: Path) -> None:
        absent = tmp_path / "not_there.toml"
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(absent)
        assert raised.value.file == absent

    def test_a_path_that_cannot_be_read_is_reported_as_such(self, tmp_path: Path) -> None:
        """A directory where a file was expected is a read failure, not an empty file.

        Distinct from "there is no such file", because the remedy is different and
        because an unreadable path must never be read as a declaration of nothing.
        """
        directory = tmp_path / "instruments.toml"
        directory.mkdir()
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(directory)
        assert raised.value.file == directory
        assert "read" in raised.value.problem

    def test_a_top_level_table_that_is_not_the_expected_one_is_reported(
        self, tmp_path: Path
    ) -> None:
        """An instrument file whose root table is ``[jurisdiction]`` is not an instrument.

        Worth its own case because the two file shapes live in sibling directories and a
        misplaced file is a plausible mistake, not a contrived one.
        """
        misplaced = _write(tmp_path, "misplaced.toml", TAX_UA.read_text(encoding="utf-8"))
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(misplaced)
        _assert_names_file_and_field(raised.value, file=misplaced, field_path="instrument")


class TestNoPydanticTypeEscapes:
    """The adapter is not optional (research.md D6).

    A raw ``ValidationError`` reaching a caller is a pydantic concept leaking through the
    boundary, and its default rendering does not name the file at all -- which is half of
    what FR-016 asks for. Asserted by *type*, so the check cannot be satisfied by an
    error that merely happens to read well.
    """

    def test_a_structural_failure_raises_the_projects_own_error_type(self, tmp_path: Path) -> None:
        broken = _instrument(
            tmp_path, _drop_line(INSTRUMENT_A.read_text(encoding="utf-8"), "coupon_rate_pct")
        )
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(broken)
        assert not isinstance(raised.value, pydantic.ValidationError)

    def test_the_error_record_carries_all_four_fields(self, tmp_path: Path) -> None:
        broken = _instrument(
            tmp_path, _drop_line(INSTRUMENT_A.read_text(encoding="utf-8"), "min_unit")
        )
        with pytest.raises(DeclarationError) as raised:
            loader.instrument_from_file(broken)
        error = raised.value
        assert isinstance(error.file, Path)
        assert isinstance(error.field_path, str)
        assert isinstance(error.problem, str)
        assert error.remedy is None or isinstance(error.remedy, str)


class TestAnImpossibleInstrumentIsNotALoadError:
    """Row 9: ``maturity_date`` at or before ``issue_date`` is a typed engine failure.

    The file is well formed; the instrument it declares cannot exist. The contract routes
    this to ``InconsistentTerms`` from the projection rather than to a
    ``DeclarationError``, which keeps instrument mathematics out of the data layer -- and
    keeps the loader from having to know what a maturity *means*.
    """

    def test_the_file_loads_and_the_projection_refuses(self, tmp_path: Path) -> None:
        broken = _instrument(
            tmp_path,
            _replace(
                INSTRUMENT_A.read_text(encoding="utf-8"),
                'maturity_date     = "2028-01-15"',
                'maturity_date     = "2025-01-15"',
            ),
        )
        declaration = loader.instrument_from_file(broken)
        impossible = declared_terms.contractual(declaration)
        assert impossible.maturity_date < impossible.issue_date

        outcome = project.project(
            declaration,
            Holding(
                owner_id="owner-1",
                instrument_id=declaration.id,
                quantity=10.0,
                purchased_on=date(2026, 1, 15),
                cost=Money(10_000.0, Currency.UAH, prov.EMPTY),
            ),
            DateRange(start=date(2026, 1, 15), end=date(2028, 1, 31)),
            Assumptions(consumption_method="fifo", coupon_policy="hold_cash"),
            tax_classes={cls.id: cls for cls in loader.tax_classes_from_file(TAX_UA)},
        )
        assert isinstance(outcome, InconsistentTerms)
        assert outcome.first_term == "instrument.maturity_date"
        assert outcome.second_term == "instrument.issue_date"
        assert "2025-01-15" in outcome.reason


class TestDatedRateSchedules:
    """⚙ Feature 006: the schedule's own enforced rules, all naming file and field.

    Five ways a dated schedule can be wrong, and one thing that is *not* wrong. The
    schedule is the shape a tax rate has now (research.md D1), so every one of these is a
    file a maintainer could plausibly write by hand, and every one of them must be caught
    where the file can be named rather than mid-projection.
    """

    def _last_class_id(self) -> str:
        """Which class an entry appended to the end of the shipped file lands under.

        Computed rather than written down: the file gains classes as features land, and a
        hard-coded id would silently start testing a different class than the one the
        appended block actually belongs to.
        """
        return loader.tax_classes_from_file(TAX_UA)[-1].id

    def _last_effective_from(self) -> str:
        """The effective date of that class's last entry, so a duplicate really duplicates.

        Derived for the same reason the id is: the shipped classes are dated by what their
        citations attest, and those dates move when a better citation is found. A literal
        here would quietly stop testing duplication the day one did.
        """
        return loader.tax_classes_from_file(TAX_UA)[-1].rates[-1].effective_from.isoformat()

    def _without_the_schedule(self) -> str:
        """The shipped tax file with its ``[[...rate]]`` block cut off.

        The caller appends ``rate = []`` to it, so the case under test is a schedule
        declared **empty** rather than one whose key is missing. The missing key is
        already covered by ``TestMissingRequiredField``'s rule, and the two failures are
        different: one is a file that forgot a section, the other is a file that says, in
        as many words, that this class has no rates.
        """
        text = TAX_UA.read_text(encoding="utf-8")
        marker = "  [[jurisdiction.tax_class.rate]]"
        assert marker in text, "the shipped fixture no longer declares a rate block"
        return text[: text.index(marker)]

    def _schedule_block(self, effective_from: str) -> str:
        return (
            "\n  [[jurisdiction.tax_class.rate]]\n"
            f'  effective_from = "{effective_from}"\n'
            "  pit_rate_pct   = 0.0\n"
            "  levy_rate_pct  = 0.0\n"
            '  note           = "FIXTURE -- a second entry added by a test."\n'
            '  kind           = "tax_rule"\n'
            '  source         = "FIXTURE -- not an observation."\n'
            '  retrieved_on   = "2026-08-23"\n'
            '  verified_on    = ""\n'
        )

    def test_a_class_with_no_dated_entry_is_refused(self, tmp_path: Path) -> None:
        """A class that can charge nothing must not be readable as an exemption.

        The two are opposite claims: an exemption is a cited zero, and an empty schedule
        is the absence of any citation at all.
        """
        broken = _write(tmp_path, "no_rates.toml", self._without_the_schedule() + "rate = []\n")
        with pytest.raises(DeclarationError) as raised:
            loader.tax_classes_from_file(broken)
        _assert_names_file_and_field(
            raised.value,
            file=broken,
            field_path="jurisdiction.tax_class[ua_government_bond].rate",
        )

    def test_two_entries_with_the_same_effective_date_are_refused(self, tmp_path: Path) -> None:
        """Two rates in force on one date has no meaning, and neither may win by order."""
        # The block lands under the file's *last* class, whichever that is, and repeats
        # that class's own last effective date.
        text = TAX_UA.read_text(encoding="utf-8") + self._schedule_block(
            self._last_effective_from()
        )
        broken = _write(tmp_path, "duplicate_dates.toml", text)
        with pytest.raises(DeclarationError) as raised:
            loader.tax_classes_from_file(broken)
        _assert_names_file_and_field(
            raised.value,
            file=broken,
            field_path=(f"jurisdiction.tax_class[{self._last_class_id()}].rate[1].effective_from"),
        )

    def test_entries_out_of_order_are_refused_rather_than_sorted(self, tmp_path: Path) -> None:
        """Sorting silently was the obvious alternative and it is refused.

        A file whose written order disagrees with its dates is one a human misreads -- and
        the reader is the person who has to check a rate against a statute. Reordering it
        here would make that file loadable, so the error is what stops it existing.

        ⚙ **This test used a literal date and passed for the wrong reason.** It appended
        ``2024-12-01``; when `ua_investment_profit` was re-dated to exactly that day, the
        appended block stopped being *earlier* than the previous entry and became *equal*
        to it, so the duplicate-date branch raised instead and the out-of-order branch lost
        all coverage. Both branches report the same ``field_path``, so an assertion reading
        only the field could never have noticed. Hence two changes: the date is **derived**
        strictly earlier than whatever the file declares, and the assertion reads the
        **message**, which is the only thing that distinguishes the two.
        """
        earlier = date.fromisoformat(self._last_effective_from()) - timedelta(days=1)
        text = TAX_UA.read_text(encoding="utf-8") + self._schedule_block(earlier.isoformat())
        broken = _write(tmp_path, "unsorted.toml", text)
        with pytest.raises(DeclarationError) as raised:
            loader.tax_classes_from_file(broken)
        _assert_names_file_and_field(
            raised.value,
            file=broken,
            field_path=(f"jurisdiction.tax_class[{self._last_class_id()}].rate[1].effective_from"),
        )
        assert "before the previous entry's" in str(raised.value), (
            "this must be the out-of-order refusal, not the duplicate-date one: they emit "
            "the same field path and only the message tells them apart"
        )

    def test_the_two_order_refusals_are_distinguishable_from_each_other(
        self, tmp_path: Path
    ) -> None:
        """The property that makes the two tests above independent, asserted directly.

        Written because they were *not* independent: one silently became a second copy of
        the other. A shared field path is fine, but then something has to differ, and this
        pins what.
        """
        last = date.fromisoformat(self._last_effective_from())
        messages = {}
        for label, when in (("duplicate", last), ("out_of_order", last - timedelta(days=1))):
            broken = _write(
                tmp_path,
                f"{label}.toml",
                TAX_UA.read_text(encoding="utf-8") + self._schedule_block(when.isoformat()),
            )
            with pytest.raises(DeclarationError) as raised:
                loader.tax_classes_from_file(broken)
            messages[label] = str(raised.value)
        assert "repeats" in messages["duplicate"]
        assert "before the previous entry's" in messages["out_of_order"]
        assert messages["duplicate"] != messages["out_of_order"]

    def test_a_negative_levy_rate_on_an_entry_is_refused(self, tmp_path: Path) -> None:
        """A refund is not a charge, and this rule does not model one."""
        broken = _write(
            tmp_path,
            "negative_levy.toml",
            _replace(
                TAX_UA.read_text(encoding="utf-8"), "levy_rate_pct  = 0.0", "levy_rate_pct  = -5.0"
            ),
        )
        with pytest.raises(DeclarationError) as raised:
            loader.tax_classes_from_file(broken)
        _assert_names_file_and_field(
            raised.value,
            file=broken,
            field_path="jurisdiction.tax_class[ua_government_bond].rate[0].levy_rate_pct",
        )

    def test_an_entry_with_no_citation_is_refused(self, tmp_path: Path) -> None:
        """The citation moved onto the entry, and so did the requirement to have one."""
        broken = _write(
            tmp_path,
            "uncited_entry.toml",
            _replace(
                TAX_UA.read_text(encoding="utf-8"), "source         =", "source         = ''  #"
            ),
        )
        with pytest.raises(DeclarationError) as raised:
            loader.tax_classes_from_file(broken)
        _assert_names_file_and_field(
            raised.value,
            file=broken,
            field_path="jurisdiction.tax_class[ua_government_bond].rate[0].source",
        )

    def test_an_entry_with_no_note_is_refused(self, tmp_path: Path) -> None:
        """The effective date is the field a reviewer most needs prose for.

        A rate can be checked against its source at a glance; the date it came into force
        usually cannot, so an entry that explains neither is one nobody can review.
        """
        broken = _write(
            tmp_path,
            "unexplained_entry.toml",
            _replace(
                TAX_UA.read_text(encoding="utf-8"),
                "note           = ",
                'note           = ""  #',
            ),
        )
        with pytest.raises(DeclarationError) as raised:
            loader.tax_classes_from_file(broken)
        _assert_names_file_and_field(
            raised.value,
            file=broken,
            field_path="jurisdiction.tax_class[ua_government_bond].rate[0].note",
        )

    def test_a_schedule_starting_after_an_event_is_not_a_load_error(self, tmp_path: Path) -> None:
        """The one thing here that is not the loader's business, and the reason FR-012 exists.

        A schedule that does not reach back to an event is a perfectly well-formed file --
        it is the *honest* file, when no citation supports an earlier entry. The refusal
        belongs to the projection, which knows the event's date, and it is asserted in
        ``tests/unit/test_schedule_refusals.py``. Catching it here would mean the loader
        deciding which events a run is allowed to contain.
        """
        text = _replace(
            TAX_UA.read_text(encoding="utf-8"),
            'effective_from = "2020-05-23"',
            'effective_from = "2099-01-01"',
        )
        loaded = loader.tax_classes_from_file(_write(tmp_path, "far_future.toml", text))
        (declared,) = [entry for entry in loaded if entry.id == "ua_government_bond"]
        assert declared.rates[0].effective_from == date(2099, 1, 1)


class TestTheRegistryRefusesAnUncoveredEvent:
    """FR-012 through the real loader, resolver and projection, end to end.

    ⚙ **This used to run on the shipped repository as it stood, and no longer can.**
    `ovdp_synthetic_b` pays its first coupon on 2026-06-02, and `ua_government_bond` used to
    reach back only to 2026-06-30 -- a citation-currency date taken off a secondary page,
    because the Tax Code's own commencement had not been retrieved. Feature 009 retrieved it
    (пп. 165.1.2 and пп. 165.1.52 from 2017-01-01; the levy carve-out struck by № 466-IX from
    2020-05-23), so widening the date stopped being the invented legal fact D2 forbids and
    became the fact. The shipped registry now covers that coupon, and the last test below is
    what says so.

    **What must not be lost with it is the demonstration.** So the refusal is watched on a
    copy of the shipped data root with exactly one field changed -- still the real loader,
    the real resolver and the real projection, not a hand-built class. A refusal the wiring
    could swallow is worse than no refusal at all, and that is a property of the wiring
    rather than of any particular date.
    """

    @staticmethod
    def _root_with_the_exemption_pushed_to(tmp_path: Path, earliest: str) -> Path:
        root = tmp_path / "data"
        shutil.copytree(DATA_ROOT, root)
        patched = _replace(
            TAX_UA.read_text(encoding="utf-8"),
            'effective_from = "2020-05-23"',
            f'effective_from = "{earliest}"',
        )
        (root / "tax" / "ua.toml").write_text(patched, encoding="utf-8")
        return root

    @staticmethod
    def _projected(root: Path, purchased_on: date) -> object:
        declarations = resolver.from_data_root(root)
        return project.project(
            declarations.instruments["ovdp_synthetic_b"],
            Holding(
                owner_id="owner-1",
                instrument_id="ovdp_synthetic_b",
                quantity=10.0,
                purchased_on=purchased_on,
                cost=Money(10_000.0, Currency.UAH, prov.EMPTY),
            ),
            DateRange(start=purchased_on, end=date(2029, 3, 31)),
            Assumptions(consumption_method="fifo", coupon_policy="hold_cash"),
            tax_classes=declarations.tax_classes,
        )

    def test_a_holding_bought_at_issue_is_refused_naming_the_class_and_the_date(
        self, tmp_path: Path
    ) -> None:
        root = self._root_with_the_exemption_pushed_to(tmp_path, "2026-06-30")
        outcome = self._projected(root, date(2026, 3, 2))

        assert isinstance(outcome, RateUndeclaredBefore), outcome
        assert outcome.tax_class_id == "ua_government_bond"
        assert outcome.event_date == date(2026, 6, 2)
        assert outcome.earliest_declared == date(2026, 6, 30)

    def test_the_refusal_says_what_a_reader_would_have_to_go_and_find(self, tmp_path: Path) -> None:
        root = self._root_with_the_exemption_pushed_to(tmp_path, "2026-06-30")
        outcome = self._projected(root, date(2026, 3, 2))

        assert isinstance(outcome, RateUndeclaredBefore)
        assert "cited legal fact" in outcome.reason
        assert "dated entry" in outcome.reason

    def test_nothing_is_charged_at_the_earliest_rate_instead(self, tmp_path: Path) -> None:
        """The failure this forecloses: a zero that looks like the exemption applying."""
        root = self._root_with_the_exemption_pushed_to(tmp_path, "2026-06-30")
        outcome = self._projected(root, date(2026, 3, 2))

        assert not hasattr(outcome, "charges")
        assert not hasattr(outcome, "hurdle")

    def test_a_holding_bought_inside_the_covered_window_projects_completely(
        self, tmp_path: Path
    ) -> None:
        """So the refusal is about the date and not about the declaration being broken."""
        root = self._root_with_the_exemption_pushed_to(tmp_path, "2026-06-30")
        outcome = self._projected(root, date(2026, 7, 2))

        assert isinstance(outcome, Projection), outcome
        assert outcome.hurdle.total_tax.amount == 0.0

    def test_the_shipped_registry_now_covers_that_coupon_and_charges_a_cited_zero(self) -> None:
        """The other side of the same fact, on the repository as it stands.

        A coupon that used to have no rate in force is now charged at the declared exemption
        -- zero, citing the provision that grants it. The distinction the whole refusal exists
        to protect is that this zero *cites a rule*, where the refusal cited none.
        """
        outcome = self._projected(DATA_ROOT, date(2026, 3, 2))

        assert isinstance(outcome, Projection), outcome
        assert outcome.hurdle.total_tax.amount == 0.0
        coupons = [
            event
            for event in outcome.ledger.applied
            if event.occurred_on == date(2026, 6, 2) and event.kind is EventKind.COUPON
        ]
        assert len(coupons) == 1, outcome.ledger.applied
        charged = [
            charge for charge in outcome.charges if charge.event_sequence == coupons[0].sequence
        ]
        assert len(charged) == 1, outcome.charges
        assert charged[0].total.amount == 0.0
        assert _provisions_behind(charged[0].provenance) >= {EXEMPTION_PROVISIONS[COUPON]}

    def test_the_exemption_names_a_provision_for_every_kind_of_income_it_covers(self) -> None:
        """The regression guard for the one thing this feature got wrong twice.

        ``ua_government_bond`` charges **two** kinds of income and they rest on **two**
        different subparagraphs: пп. 165.1.2 for the coupon, пп. 165.1.52 for the disposal
        gain. For one round the entry cited 165.1.52 for both -- a provision about investment
        profit standing behind four of the five charges in the checked-in golden run.

        Truthiness on ``provenance.sources`` cannot catch that, and did not: it passes with
        165.1.52 alone and it passes with both provisions replaced by an invented number. So
        the assertion is that the citation the charges actually carry **names every provision
        this test expects**, one per kind the class declares itself to apply to -- which also
        fails if a third kind is added to ``applies_to`` and nobody finds the provision that
        exempts it.

        **What it does not check is which provision goes with which kind**, and there is
        nowhere in the file for that to live: the class has one rate entry, one ``source``
        string and two kinds, so a citation naming both numbers against the wrong kinds passes
        here. The association is this test's own, in :data:`EXEMPTION_PROVISIONS`; the data
        cannot contradict it, only omit a number, which is the defect that happened. Splitting
        the citation per kind would need a per-kind provenance the record has no field for --
        if that field ever arrives, this is where the check belongs.
        """
        (declared,) = [
            entry for entry in loader.tax_classes_from_file(TAX_UA) if entry.id == GOVERNMENT_BOND
        ]
        (rate,) = declared.rates

        assert declared.applies_to == frozenset(EXEMPTION_PROVISIONS), declared.applies_to
        named = _provisions_behind(rate.provenance)
        for kind, provision in sorted(EXEMPTION_PROVISIONS.items(), key=lambda pair: pair[0].value):
            assert provision in named, (kind.value, provision, named)

    def test_issue_a_is_covered_by_fifteen_days_and_that_margin_is_deliberate(self) -> None:
        """Four checked-in runs of issue A depend on this margin. It was luck; make it a claim.

        `ovdp_synthetic_a` is issued 2026-01-15 and pays its first coupon on 2026-07-15,
        fifteen days after the earliest entry the exemption's citation reaches. A purchase
        is not a taxable event, so the January date is irrelevant and the July one is not.

        The runs that rest on this, and would otherwise fail somewhere unhelpful if either
        date moved:

        * `tests/golden/test_end_to_end_ovdp.py`
        * `tests/contract/test_provenance_propagation.py`
        * `tests/invariants/test_determinism.py`
        * `tests/contract/test_data_only_extensibility.py`

        If a better citation moves the exemption **earlier**, this test keeps passing and
        the margin simply widens. If one moves it **later** than 2026-07-15, this fails
        first and says which four modules to re-date — which is the whole point of writing
        the dependency down rather than leaving four suites to discover it separately.
        """
        declarations = resolver.from_data_root(DATA_ROOT)
        exemption = declarations.tax_classes["ua_government_bond"]
        earliest = min(entry.effective_from for entry in exemption.rates)
        first_taxable_event = date(2026, 7, 15)
        assert earliest <= first_taxable_event, (
            f"the exemption now starts {earliest.isoformat()}, after issue A's first "
            f"coupon on {first_taxable_event.isoformat()}. The four modules named in this "
            "test's docstring project issue A and will all fail; re-date their holdings "
            "rather than widening the exemption's effective date."
        )


class TestTheBatteryCoversTheContract:
    """The battery is only a proof of SC-004 if it covers every row of the table.

    A list that drifts out of step with the contract is the failure mode here: a row is
    added to ``declaration-schema.md``, no case is written, and the suite stays green
    while the rule goes unenforced. This test cannot detect a *new* row, but it does
    pin the set of cases that exist, so removing one is a deliberate act.
    """

    def test_every_enforced_rule_has_a_test_class(self) -> None:
        classes = {
            name
            for name, value in globals().items()
            if name.startswith("Test") and isinstance(value, type)
        }
        assert classes == {
            "TestTheShippedFilesLoad",
            "TestUnrecognisedField",
            "TestMissingRequiredField",
            "TestWrongType",
            "TestVerifiedOnMustBePresent",
            "TestNumericTableWithoutACitation",
            "TestDuplicateIdentifiersAcrossFiles",
            "TestUnresolvedTaxClassReference",
            "TestUnknownConventionName",
            "TestNonPositiveAmounts",
            "TestDatedRateSchedules",
            "TestTheRegistryRefusesAnUncoveredEvent",
            "TestMalformedFile",
            "TestNoPydanticTypeEscapes",
            "TestAnImpossibleInstrumentIsNotALoadError",
            "TestTheBatteryCoversTheContract",
            "TestNoFieldDefaultStandsInForAValue",
            "TestEveryShippedInstrumentSaysItIsAFixture",
        }

    def test_the_second_issue_is_a_file_and_not_a_special_case(self) -> None:
        """Both shipped issues load through the same function, with no branch on id."""
        assert loader.instrument_from_file(INSTRUMENT_B).id == "ovdp_synthetic_b"


class TestNoFieldDefaultStandsInForAValue:
    """The schema module's own rule, pinned rather than restated (FR-016).

    A default in pydantic is the only mechanism by which a value no file contains can enter
    the model, so the set of fields that have one is worth knowing exactly. Every entry
    below is a field whose **absence is itself a declaration** — an omitted `[access.price]`
    says *this instrument prices itself*, an omitted `published_in_order` says *the source
    published in date order* — and every one of them defaults to ``None`` rather than to a
    value.

    ⚙ Written after the module docstring was found claiming *"Zero field defaults,
    anywhere"* over eleven of them (2026-08-30). A sentence asserting a mechanical property
    is a test or it is not written.
    """

    OPTIONAL: Final[Mapping[str, frozenset[str]]] = {
        "AccessTable": frozenset({"price"}),
        "ChannelSideTable": frozenset({"markup_bps", "premium_per_unit"}),
        "DistributionTable": frozenset({"peg"}),
        "EnumeratedScheduleTable": frozenset({"published_in_order"}),
        "FundTable": frozenset({"subscription_cutoff", "distribution"}),
        "GoalTable": frozenset({"monthly_contribution", "target_sum", "target_date"}),
        "IndexationTable": frozenset({"rate_pct"}),
        "LegTable": frozenset(
            {
                "channel",
                "capacity_pool",
                "minimum",
                "maximum",
                "monthly_cap",
                "available_from",
                "available_until",
            }
        ),
        # Both arrived with feature 011, and both are the permitted shape rather than the
        # forbidden one: the absence of the key IS the declaration.
        #
        # `non_publication_rule` is the sharper of the two, and 011 turns on it. The rule
        # for a date the National Bank publishes no rate for is written in working days and
        # public holidays, which FR-011 forbids the engine to know about, so the Ukrainian
        # series ships WITHOUT one and every such date refuses. A default here would be a
        # rule nobody declared, applied silently, to the one input that makes a foreign
        # amount a legal one.
        "OfficialRateFile": frozenset({"non_publication_rule"}),
        # A timing table for a jurisdiction whose taxable events are all in the base
        # currency needs no rate series, and saying so by omission is the same shape
        # `StreamTable.tax_scheme` has: omitted means not stated, which is a different claim
        # from stated-as-nothing.
        "TimingTable": frozenset({"official_rate_series"}),
        "RouteTable": frozenset({"partner_route"}),
        "SeedTable": frozenset({"reason"}),
        "StreamTable": frozenset({"tax_scheme"}),
        # A reading declares exactly one of `scheme` and `uncomputable_because`, and
        # `recognised_on` accompanies the first; `departs_from_source` is present only where
        # this system knowingly computes something other than what its source does. Each
        # absence is a declaration, and the loader refuses every combination that is not.
        "ReadingTable": frozenset(
            {"scheme", "recognised_on", "uncomputable_because", "departs_from_source"}
        ),
        # A scheme charging only rates declares no periodic component and vice versa, so
        # each list may be absent; omitting BOTH is the loader's refusal, because only it can
        # say that a scheme charging nothing at all is a file nobody meant to write. A
        # `context` list is absent when nothing is recorded beside a schedule, which is the
        # only other state there is -- unlike a schedule, there is no third reading between
        # nothing was declared and this is what was declared.
        "SchemeTable": frozenset({"rate_component", "periodic_component"}),
        "RateComponentTable": frozenset({"context"}),
        "PeriodicComponentTable": frozenset({"context"}),
    }

    @staticmethod
    def _defaults() -> dict[str, frozenset[str]]:
        return {
            name: frozenset(
                field for field, info in model.model_fields.items() if not info.is_required()
            )
            for name, model in vars(schema).items()
            if isinstance(model, type)
            and issubclass(model, BaseModel)
            and model is not BaseModel
            and any(not info.is_required() for info in model.model_fields.values())
        }

    def test_exactly_these_fields_may_be_omitted(self) -> None:
        assert self._defaults() == dict(self.OPTIONAL), (
            "a field gained or lost an optional marker. Adding one is permitted where the "
            "absence of the key is itself a declaration; it is not permitted as a way of "
            "not writing a value (FR-016), so the decision is taken here"
        )

    def test_and_every_one_of_them_defaults_to_nothing_rather_than_to_a_value(self) -> None:
        """The half that matters. ``None`` is "the key was not written"; anything else is a
        number, a date or a name that no file on disk contains."""
        for name, fields in self._defaults().items():
            model = getattr(schema, name)
            for field in sorted(fields):
                assert model.model_fields[field].default is None, f"{name}.{field}"


class TestEveryShippedInstrumentSaysItIsAFixture:
    """`docs/METHODOLOGY.md` §0's claim about `data/instruments/`, as a check.

    Every declaration this repository ships is invented, and every one of them says so on
    its face — a bond through `is_synthetic`, a fund through `is_assumption_driven` — with
    every `verified_on` empty. §0 tells a reader that no figure computed from any of them
    describes something anyone can buy, and it used to tell them by naming two files by
    hand, which had been wrong since feature 006 added three more.

    ⚙ The correction replaced the count with the property and cited a file that checks no
    such thing (found 2026-08-30). This is that file.
    """

    def test_every_declared_bond_declares_itself_synthetic(self) -> None:
        declared = resolver.from_data_root(DATA_ROOT)
        assert declared.instruments
        for identifier, instrument in sorted(declared.instruments.items()):
            assert instrument.is_synthetic, identifier

    def test_every_declared_fund_declares_itself_assumption_driven(self) -> None:
        declared = resolver.from_data_root(DATA_ROOT)
        assert declared.funds
        for identifier, fund in sorted(declared.funds.items()):
            assert fund.is_assumption_driven, identifier

    def test_and_nothing_they_rest_on_claims_to_have_been_verified(self) -> None:
        """The other half of the sentence. A verified term in a file of invented ones would
        be a claim that somebody checked an invention against a source."""
        declared = resolver.from_data_root(DATA_ROOT)
        for identifier, instrument in sorted(declared.instruments.items()):
            assert prov.is_unverified(instrument.terms.provenance), identifier
            assert prov.is_unverified(instrument.constraints.provenance), identifier
