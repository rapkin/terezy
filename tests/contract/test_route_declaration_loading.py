"""A battery of deliberately broken route, channel, stream and kind declarations.

**FR-024 and SC-011 in one place**: *"every malformed, unrecognised, missing, duplicated or
non-chaining field in a declaration file produces an error naming the file and the field,
and no such case results in a substituted default"*. The enforced-rules table in
``specs/002-ramp-cost/contracts/declaration-schema.md`` has a row for each class below, and
the rows are the reason the cases exist rather than the other way round.

**Every case is a mutation of a file that is shipped and valid.** The broken variants are
produced by editing the text of the real declarations under ``data/``, so each test also
proves the shipped file contains what the test thinks it contains -- a battery written
against an invented template would keep passing after the shipped format changed underneath
it, which is how a suite like this rots. It is the same construction as
``tests/contract/test_declaration_loading.py`` for feature 001, and the helpers below are
that module's, restated rather than imported so neither battery can break the other.

**What "naming the field" is checked against.** Two assertions, applied to every case by
:func:`_assert_names_file_and_field`: the raised error's ``file`` is the file that was
loaded, and its ``field_path`` locates the problem. A message that named the field but not
the file would satisfy pydantic's default rendering and fail FR-024, which is precisely why
the loader adapts ``ValidationError`` rather than letting it out.

**Cross-file cases load a whole data root.** Duplicate ids, identity collisions, chaining,
venue and channel references, kind resolution, partner pairing and pool agreement are
relations between files, so those cases copy ``data/`` into a scratch directory, break one
line, and resolve the lot. The error still names the file that is wrong -- for a pool
disagreement, both.

**One row of the table is enforced against a scenario file**: a fallback policy of
``deposit``. It is a row of *this* contract's table, so its case is here, even though the
file it breaks is ``data/scenarios/war_end.toml``; the rest of the scenario rules are
``tests/contract/test_scenario_declaration_loading.py``'s.
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path

import pydantic
import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.routes.channels import ChannelSide, FxChannel
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError

pytestmark = pytest.mark.contract

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
KINDS = DATA_ROOT / "observation_kinds.toml"
VENUES = DATA_ROOT / "venues.toml"
CHANNELS = DATA_ROOT / "channels" / "uah_usd.toml"
STREAMS = DATA_ROOT / "streams" / "owner-001.toml"
SCENARIO = DATA_ROOT / "scenarios" / "war_end.toml"
P2P = DATA_ROOT / "routes" / "monobank_to_binance_p2p.toml"
P2P_EXIT = DATA_ROOT / "routes" / "binance_p2p_to_monobank.toml"
DOUBLE = DATA_ROOT / "routes" / "monobank_to_binance_p2p_double.toml"
INZHUR = DATA_ROOT / "routes" / "inzhur_direct.toml"
COINBASE = DATA_ROOT / "routes" / "coinbase_to_ibkr.toml"


def _is_comment(line: str) -> bool:
    """Whether a line is a TOML comment.

    Both helpers below skip comments, and they have to: the shipped fixtures explain
    themselves in prose that quotes their own field names, so a naive text search would edit
    the explanation of ``capacity_pool`` instead of the declaration of it -- leaving the file
    valid and the test asserting an error that never came.
    """
    return line.lstrip().startswith("#")


def _replace(text: str, old: str, new: str) -> str:
    """One textual edit to the first declaring line, refusing to silently do nothing.

    The failure is the point: ``str.replace`` on a string that does not contain the needle
    returns the string unchanged, so without this a renamed field in the shipped file would
    turn every case below into a test of a *valid* file that expects an error -- failing for
    a reason with nothing to do with the rule under test.
    """
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if old in line and not _is_comment(line):
            lines[index] = line.replace(old, new, 1)
            return "".join(lines)
    pytest.fail(f"the shipped fixture no longer declares {old!r}; this test is stale")


def _drop_line(text: str, needle: str) -> str:
    """Remove the **first** declaring line containing ``needle`` -- how a field goes missing.

    Feature 001's version of this helper insisted the needle matched exactly once, which it
    could: an instrument declares each field once. A route file declares ``fee_pct`` once
    *per leg*, so the same insistence here would make every missing-field case unwritable
    against a two-leg route. The anti-stale property is kept -- a needle that matches nothing
    fails the test rather than silently leaving the file valid -- and the first match is the
    one taken, which is leg 0 in every case below and is what the expected field path says.
    """
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if needle in line and not _is_comment(line):
            return "".join(lines[:index] + lines[index + 1 :])
    pytest.fail(f"the shipped fixture no longer declares {needle!r}; this test is stale")


def _broken(tmp_path: Path, source: Path, old: str, new: str, name: str = "broken.toml") -> Path:
    """One shipped file with one line edited, written where a loader can be pointed at it."""
    target = tmp_path / name
    target.write_text(_replace(source.read_text(encoding="utf-8"), old, new), encoding="utf-8")
    return target


def _without(tmp_path: Path, source: Path, needle: str, name: str = "broken.toml") -> Path:
    """One shipped file with one declaring line removed."""
    target = tmp_path / name
    target.write_text(_drop_line(source.read_text(encoding="utf-8"), needle), encoding="utf-8")
    return target


def _set_value(text: str, key: str, literal: str) -> str:
    """Rewrite the first declaring line for ``key`` as ``key = literal``, keeping its indent.

    Needed where the *whole* value has to change and the value is a long sentence -- an
    emptied citation, an emptied note. :func:`_replace` edits a substring, which would leave
    the tail of the old sentence behind and quietly produce a file that is still valid, so
    the case would assert an error that never came.
    """
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.strip().startswith(f"{key} ") and not _is_comment(line):
            indent = line[: len(line) - len(line.lstrip())]
            lines[index] = f"{indent}{key} = {literal}\n"
            return "".join(lines)
    pytest.fail(f"the shipped fixture no longer declares {key!r}; this test is stale")


def _emptied(tmp_path: Path, source: Path, key: str, name: str = "broken.toml") -> Path:
    """One shipped file with one field emptied -- how a citation stops being a citation."""
    target = tmp_path / name
    target.write_text(_set_value(source.read_text(encoding="utf-8"), key, '""'), encoding="utf-8")
    return target


def _set_in_leg(text: str, leg_index: int, key: str, literal: str) -> str:
    """Rewrite one field of the *n*-th ``[[route.leg]]`` block, and only that one.

    Route files declare the same field once per leg, so a needle-based edit hits leg 0 and a
    multi-line needle hits nothing (:func:`_replace` works line by line, deliberately, so it
    can skip comments). The chaining cases need to break a *later* leg, which is what this
    does: split on the leg header, edit inside one block, join it back.
    """
    blocks = text.split("  [[route.leg]]")
    assert len(blocks) > leg_index + 1, f"the fixture has fewer than {leg_index + 1} legs"
    blocks[leg_index + 1] = _set_value(blocks[leg_index + 1], key, literal)
    return "  [[route.leg]]".join(blocks)


def _edit_leg(path: Path, leg_index: int, key: str, literal: str) -> None:
    """Break one field of one leg of a route file inside a scratch data root."""
    path.write_text(
        _set_in_leg(path.read_text(encoding="utf-8"), leg_index, key, literal),
        encoding="utf-8",
    )


def _root(tmp_path: Path) -> Path:
    """A copy of the whole shipped ``data/`` tree, for the cases that span files.

    Copied rather than assembled from templates, for the reason the module docstring gives:
    a case built out of invented files would keep passing after the shipped shape changed.
    """
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _edit(path: Path, old: str, new: str) -> None:
    """Break one line of a file already inside a scratch data root."""
    path.write_text(_replace(path.read_text(encoding="utf-8"), old, new), encoding="utf-8")


def _resolve(root: Path) -> resolver.RampDeclarations:
    """Resolve a whole ramp data root against the base currency the owner earns in."""
    return resolver.ramp_from_data_root(root, base_currency=Currency.UAH)


def _assert_names_file_and_field(
    raised: DeclarationError,
    *,
    file: Path,
    field_path: str,
) -> None:
    """Both halves of FR-024, asserted together because half of it is worthless.

    The rendered message is checked as well as the fields, because the message is what a
    person maintaining a route declaration by hand actually sees.
    """
    assert raised.file == file, f"the error must name the file it came from, got {raised.file}"
    assert raised.field_path == field_path, (
        f"the error must locate the field; expected {field_path!r}, got {raised.field_path!r}"
    )
    rendered = str(raised)
    assert file.name in rendered
    assert field_path in rendered
    assert raised.problem, "an error with no plain-language problem explains nothing"


class TestTheShippedFilesLoad:
    """The baseline. Every broken case below is a mutation of these, so they must work."""

    def test_the_whole_ramp_data_root_resolves(self) -> None:
        declarations = _resolve(DATA_ROOT)
        assert set(declarations.routes) == {
            "inzhur_direct",
            "inzhur_to_monobank",
            "monobank_to_binance_p2p",
            "monobank_to_binance_p2p_double",
            "monobank_to_binance_card",
            "binance_p2p_to_monobank",
            "coinbase_to_ibkr",
            "deel_to_fop",
            "deel_to_coinbase",
            "fop_usd_to_monobank_uah",
        }
        assert set(declarations.channels) == {"p2p", "card", "bank_fop"}
        assert set(declarations.streams) == {"salary_uah", "contract_usd"}
        assert set(declarations.scenarios) == {"war_end"}
        assert declarations.base_currency is Currency.UAH

    def test_a_declared_percentage_reaches_the_engine_as_a_fraction(self) -> None:
        """``fee_pct = 0.5`` in the file is ``0.005`` in the core -- divided once, here.

        Asserted as **exact** equality rather than approximately: 0.5 is exactly
        representable, so IEEE division returns the nearest double to 0.005, which is the
        literal ``0.005`` bit for bit. An approximate assertion would pass just as happily
        on a fee that had been divided twice by a factor near one, and the whole point of
        this line is that the conversion happens exactly once at the boundary.
        """
        leg = loader.route_from_file(COINBASE).legs[0]
        assert leg.fee_pct == 0.005
        assert leg.fee_fixed.amount == 25.0
        assert leg.fee_fixed.currency is Currency.USD

    def test_basis_points_are_not_divided_by_a_hundred(self) -> None:
        """The other half of "exactly once": a bps field must not pass through it.

        ``ChannelSide`` divides by 10 000 itself, beside the channel that uses it. A markup
        of 150 bps reaching the core as 1.5 would look plausible and would price a 1.5% card
        conversion at 0.015%.
        """
        card = next(c for c in loader.channels_from_file(CHANNELS) if c.id == "card")
        assert card.buy_side.markup_bps == 150.0
        assert card.buy_side.premium_per_unit is None

    def test_a_premium_keeps_its_sign_and_its_currency(self) -> None:
        p2p = next(c for c in loader.channels_from_file(CHANNELS) if c.id == "p2p")
        buy = p2p.buy_side.premium_per_unit
        sell = p2p.sell_side.premium_per_unit
        assert buy is not None
        assert sell is not None
        assert (buy.amount, buy.currency) == (3.0, Currency.UAH)
        assert (sell.amount, sell.currency) == (-2.5, Currency.UAH), (
            "a negative premium is legal: a P2P book does trade below the reference, and "
            "clamping or flipping the sign would delete the asymmetry"
        )

    def test_every_declared_route_value_is_marked_unverified(self) -> None:
        """SC-012's precondition. None of §11 item 1's figures has been observed.

        Empty is not absent: the files load, and everything they declare carries a source
        whose verification date is ``None``, which is what makes the mark propagate rather
        than being remembered by whoever read the file.
        """
        declarations = _resolve(DATA_ROOT)
        for route in declarations.routes.values():
            for leg in route.legs:
                assert prov.is_unverified(leg.provenance), route.id
        for channel in declarations.channels.values():
            assert prov.is_unverified(channel.provenance), channel.id

    def test_a_source_ref_names_the_file_the_table_and_the_side(self) -> None:
        """A figure traces back to *where* it was declared, not only to a citation string.

        Three refs per channel, because a reference rate and each side of the quote are three
        observations read off three lines -- and unioning them is what stops a verified
        reference vouching for an unverified side.
        """
        p2p = next(c for c in loader.channels_from_file(CHANNELS) if c.id == "p2p")
        assert {ref.id for ref in p2p.provenance.sources} == {
            "channels/uah_usd.toml#channel[p2p]",
            "channels/uah_usd.toml#channel[p2p].buy_side",
            "channels/uah_usd.toml#channel[p2p].sell_side",
        }
        assert {ref.id for ref in loader.route_from_file(P2P).legs[0].provenance.sources} == {
            "routes/monobank_to_binance_p2p.toml#route.leg[0]"
        }

    def test_an_omitted_tax_scheme_is_none_and_not_a_scheme_charging_zero(self) -> None:
        """012 FR-016's distinction, at the boundary where it is decided.

        The salary names no scheme, so the core sees ``None`` -- *the owner has not named a
        treatment* -- rather than a scheme charging nothing, which would claim his
        employment income is untaxed. The contract income names one.
        """
        streams = loader.streams_from_file(STREAMS)
        assert [stream.tax_scheme for stream in streams] == [None, "ua_fop_group_3_non_vat"]
        assert [stream.amount.amount for stream in streams] == [0.0, 0.0]
        assert streams[0].amount.currency is Currency.UAH
        assert streams[1].amount.currency is Currency.USD

    def test_an_absent_partner_route_is_none_and_the_declared_one_resolves(self) -> None:
        assert loader.route_from_file(COINBASE).partner_route is None
        assert loader.route_from_file(P2P).partner_route == "binance_p2p_to_monobank"


class TestUnrecognisedField:
    """Row 1: an unrecognised field is an error naming file and field (FR-024)."""

    def test_a_misspelt_leg_field_is_refused_not_ignored(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path, P2P, "  latency_days           = 0", "  latency_dayz           = 0"
        )
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="route.leg[0].latency_days"
        )
        assert "latency_dayz" in raised.value.problem, (
            "the misspelt field is refused rather than ignored, and the message lists it "
            "alongside the required field it failed to be -- a reader fixing the file wants "
            "both told, which is why the loader reports every problem in the document and "
            "points ``field_path`` at the first"
        )
        assert "not a field this loader recognises" in raised.value.problem

    def test_an_unknown_channel_side_field_is_refused(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path, CHANNELS, "  premium_per_unit = 3.0", "  premium_per_dollar = 3.0"
        )
        with pytest.raises(DeclarationError) as raised:
            loader.channels_from_file(broken)
        assert raised.value.file == broken
        assert "premium_per_dollar" in raised.value.problem


class TestMissingRequiredField:
    """Row 1 again, and the half FR-024 is emphatic about: nothing is substituted."""

    @pytest.mark.parametrize(
        ("needle", "field_path"),
        [
            ("  fee_pct                = 0.0", "route.leg[0].fee_pct"),
            ("  disruption_probability = 0.05", "route.leg[0].disruption_probability"),
            ('  kind_of_observation    = "regulatory_limit"', "route.leg[0].kind_of_observation"),
            (
                '  source                 = "SYNTHETIC FIXTURE — invented. The 100 000',
                "route.leg[0].source",
            ),
            ('status        = "open"', "route.status"),
        ],
    )
    def test_a_missing_leg_or_route_field_is_reported(
        self, tmp_path: Path, needle: str, field_path: str
    ) -> None:
        broken = _without(tmp_path, P2P, needle)
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path=field_path)
        assert "No default value is substituted" in raised.value.problem

    def test_a_kind_with_no_staleness_days_is_refused(self, tmp_path: Path) -> None:
        """Row: an ``ObservationKind`` with no ``staleness_days``. No permissive default."""
        broken = _without(tmp_path, KINDS, "staleness_days = 7")
        with pytest.raises(DeclarationError) as raised:
            loader.observation_kinds_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="kind[0].staleness_days")

    def test_a_zero_staleness_threshold_is_refused_too(self, tmp_path: Path) -> None:
        """Zero days is not a threshold: it is every value of that kind stale on arrival."""
        broken = _broken(tmp_path, KINDS, "staleness_days = 7", "staleness_days = 0")
        with pytest.raises(DeclarationError) as raised:
            loader.observation_kinds_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="kind[p2p_premium].staleness_days"
        )

    def test_a_kind_with_no_note_is_refused(self, tmp_path: Path) -> None:
        broken = _emptied(tmp_path, KINDS, "note")
        with pytest.raises(DeclarationError) as raised:
            loader.observation_kinds_from_file(broken)
        assert raised.value.field_path == "kind[p2p_premium].note"


class TestWrongType:
    """Row 1's third clause: values are read strictly, and a quoted number is a string."""

    def test_a_quoted_fee_is_not_quietly_a_number(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path, COINBASE, "  fee_pct                = 0.5", '  fee_pct                = "0.5"'
        )
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="route.leg[0].fee_pct")
        assert "not silently converted" in raised.value.problem

    def test_a_wrong_type_inside_an_array_of_tables_names_its_index(self, tmp_path: Path) -> None:
        """A reader counts entries rather than guessing which of four legs is wrong."""
        broken = _broken(
            tmp_path,
            DOUBLE,
            "  index                  = 3",
            '  index                  = "3"',
        )
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="route.leg[3].index")


class TestVerifiedOnMustBePresent:
    """Row: ``verified_on`` absent is an error; empty is fine. Absence is not emptiness."""

    def test_dropping_verified_on_from_a_leg_is_an_error(self, tmp_path: Path) -> None:
        broken = _without(tmp_path, P2P, '  verified_on            = ""')
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        assert raised.value.file == broken
        assert "verified_on" in raised.value.field_path

    def test_an_empty_verified_on_loads_and_marks_the_value(self) -> None:
        route = loader.route_from_file(P2P)
        assert prov.is_unverified(route.legs[0].provenance)

    def test_a_verified_date_loads_and_clears_the_mark(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path,
            P2P,
            '  verified_on            = ""',
            '  verified_on            = "2026-08-22"',
        )
        route = loader.route_from_file(broken)
        assert not prov.is_unverified(route.legs[0].provenance)
        assert next(iter(route.legs[0].provenance.sources)).verified_on == date(2026, 8, 22)


class TestNumericTableWithoutACitation:
    """Row: a table of observed values with no ``source``/``retrieved_on``/``kind``."""

    def test_an_empty_citation_is_not_a_citation(self, tmp_path: Path) -> None:
        broken = _emptied(tmp_path, INZHUR, "source")
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="route.leg[0].source")

    def test_an_empty_kind_is_not_a_kind(self, tmp_path: Path) -> None:
        broken = _emptied(tmp_path, INZHUR, "kind_of_observation")
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        assert raised.value.field_path == "route.leg[0].kind_of_observation"

    def test_a_channel_side_with_no_kind_is_refused(self, tmp_path: Path) -> None:
        """The side is its own observation, so it needs its own kind and its own citation."""
        broken = _without(tmp_path, CHANNELS, '  kind             = "p2p_premium"')
        with pytest.raises(DeclarationError) as raised:
            loader.channels_from_file(broken)
        assert raised.value.file == broken
        assert "kind" in raised.value.problem


class TestUndeclaredObservationKind:
    """Row: a ``kind`` naming an undeclared ``ObservationKind`` (FR-028)."""

    def test_a_leg_naming_an_unknown_kind_is_refused_naming_the_known_ones(
        self, tmp_path: Path
    ) -> None:
        root = _root(tmp_path)
        _edit(
            root / "routes" / "inzhur_direct.toml",
            '  kind_of_observation    = "bank_fee_schedule"',
            '  kind_of_observation    = "bank_fees"',
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        _assert_names_file_and_field(
            raised.value,
            file=root / "routes" / "inzhur_direct.toml",
            field_path="route.leg[0].kind_of_observation",
        )
        assert "bank_fee_schedule" in raised.value.problem, "an unknown kind is usually a typo"

    def test_a_channel_naming_an_unknown_kind_is_refused(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        _edit(
            root / "channels" / "uah_usd.toml",
            'kind           = "p2p_premium"',
            'kind           = "premium"',
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "channel[p2p].kind"

    def test_a_channel_side_naming_an_unknown_kind_is_refused(self, tmp_path: Path) -> None:
        # A **side's** own kind, which is a different check on a different field: a side ages
        # under its own threshold, and a premium aged under the channel's schedule threshold
        # would read fresh long after its own had passed. The resolver has checked this since
        # that defect was found, and until now nothing failed if the check were deleted --
        # which is how the identical hole in the access price got through the round that was
        # supposed to close this class.
        root = _root(tmp_path)
        _edit(
            root / "channels" / "uah_usd.toml",
            '  kind             = "p2p_premium"',
            '  kind             = "p2p_premiums"',
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "channel[p2p].buy_side.kind"
        assert "p2p_premium" in raised.value.problem


class TestDuplicateIdentifiers:
    """Row: a duplicate route id, and a duplicate ``(provider x currency path x venue)``."""

    def test_two_files_declaring_one_route_id_are_refused_naming_both(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        copy = root / "routes" / "aaa_copy.toml"
        copy.write_text(P2P.read_text(encoding="utf-8"), encoding="utf-8")
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "route.id"
        assert "aaa_copy.toml" in str(raised.value) or "monobank_to_binance_p2p.toml" in str(
            raised.value
        )
        assert str(root / "routes") in str(raised.value)

    def test_a_duplicate_identity_triple_is_refused_even_with_a_different_id(
        self, tmp_path: Path
    ) -> None:
        """FR-023: identity is the triple, so a renamed copy is still the same corridor."""
        root = _root(tmp_path)
        copy = root / "routes" / "aaa_same_corridor.toml"
        copy.write_text(
            _replace(
                P2P.read_text(encoding="utf-8"),
                'id            = "monobank_to_binance_p2p"',
                'id            = "monobank_to_binance_p2p_again"',
            ),
            encoding="utf-8",
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "route.provider"
        assert "registry identity" in raised.value.problem
        assert "UAH -> USD -> USD" in raised.value.problem

    def test_two_venues_with_one_id_are_refused(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        _edit(root / "venues.toml", 'id         = "binance"', 'id         = "monobank_uah"')
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "venue[monobank_uah].id"

    def test_two_channels_with_one_id_are_refused(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        _edit(
            root / "channels" / "uah_usd.toml", 'id             = "card"', 'id             = "p2p"'
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "channel[p2p].id"

    def test_two_streams_with_one_id_are_refused(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        _edit(
            root / "streams" / "owner-001.toml",
            'id          = "contract_usd"',
            'id         = "salary_uah"',
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "stream[salary_uah].id"


class TestARouteWithNoLegs:
    """Row: a route with no legs is refused, never costed as free."""

    def test_an_explicitly_empty_leg_list_is_refused(self, tmp_path: Path) -> None:
        """``leg = []`` is a *declaration* that the route moves nothing, and it is refused."""
        head = INZHUR.read_text(encoding="utf-8").split("  [[route.leg]]")[0]
        broken = tmp_path / "broken.toml"
        broken.write_text(f"{head}leg = []\n", encoding="utf-8")
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="route.leg")
        assert "costed as free" in raised.value.problem

    def test_a_route_with_the_leg_table_missing_altogether_is_refused(self, tmp_path: Path) -> None:
        """The other way to declare nothing: no ``[[route.leg]]`` at all, and no default."""
        head = INZHUR.read_text(encoding="utf-8").split("  [[route.leg]]")[0]
        broken = tmp_path / "broken.toml"
        broken.write_text(head, encoding="utf-8")
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="route.leg")
        assert "No default value is substituted" in raised.value.problem


class TestLegsThatDoNotChain:
    """Row: legs that do not chain by venue or by currency, naming file and leg index."""

    def test_a_venue_gap_is_refused_naming_the_later_leg(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        # Coinbase can hold dollars, so the *only* thing wrong is that nothing moved the
        # money there: the can-hold check passes and the chain check is what fires.
        _edit_leg(
            root / "routes" / "monobank_to_binance_p2p_double.toml",
            2,
            "from_venue",
            '"coinbase"',
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "route.leg[2].from_venue"
        assert "chain is broken" in raised.value.problem

    def test_a_currency_gap_is_refused_and_names_the_implicit_conversion(
        self, tmp_path: Path
    ) -> None:
        root = _root(tmp_path)
        # Both currencies on leg 1, so the leg itself stays coherent -- a transfer that
        # converts nothing -- and what is left is a gap only the previous leg can show.
        route = root / "routes" / "monobank_to_binance_p2p.toml"
        _edit_leg(route, 1, "from_ccy", '"UAH"')
        _edit_leg(route, 1, "to_ccy", '"UAH"')
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "route.leg[1].from_ccy"
        assert "mid-rate" in raised.value.problem

    def test_a_leg_index_that_disagrees_with_its_position_is_refused(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path, P2P, "  index                  = 1", "  index                  = 7"
        )
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="route.leg[1].index")


class TestFirstAndLastLeg:
    """Row: the first leg must start at ``origin`` and the last must end at ``destination``."""

    def test_a_first_leg_elsewhere_is_refused(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        _edit(
            root / "routes" / "inzhur_direct.toml",
            'origin        = "monobank_uah"',
            'origin        = "binance"',
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "route.leg[0].from_venue"

    def test_a_last_leg_elsewhere_is_refused(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        _edit(
            root / "routes" / "inzhur_direct.toml",
            'destination   = "inzhur"',
            'destination   = "binance"',
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "route.leg[0].to_venue"
        assert "cost of reaching one place" in raised.value.problem


class TestAVenueThatCannotHoldTheCurrency:
    """Row: a leg moving a currency its venue cannot hold."""

    def test_moving_dollars_through_a_hryvnia_only_venue_is_refused(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        _edit(root / "venues.toml", 'currencies = ["UAH", "USD"]', 'currencies = ["UAH"]')
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert "USD" in raised.value.problem
        assert raised.value.field_path.startswith("route.")


class TestUnknownDeclaredName:
    """Row: an unknown ``leg.kind``, ``channel``, ``venue`` or ``cadence``, with the known ones."""

    def test_an_unknown_leg_kind_names_the_known_kinds(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path,
            INZHUR,
            '  kind                   = "transfer"',
            '  kind                   = "wire"',
        )
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="route.leg[0].kind")
        assert raised.value.remedy is not None
        assert "transfer" in raised.value.remedy
        assert "fx" in raised.value.remedy

    def test_an_unknown_channel_names_the_declared_channels(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        _edit(
            root / "routes" / "monobank_to_binance_p2p.toml",
            '  channel                = "p2p"',
            '  channel                = "peer_to_peer"',
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "route.leg[0].channel"
        assert "'card', 'p2p'" in raised.value.problem or "card" in raised.value.problem

    def test_an_unknown_venue_names_the_declared_venues(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        _edit(
            root / "routes" / "inzhur_direct.toml",
            '  to_venue               = "inzhur"',
            '  to_venue               = "inzhur_fund"',
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "route.leg[0].to_venue"
        assert "inzhur" in raised.value.problem

    def test_an_unknown_cadence_names_the_known_ones(self, tmp_path: Path) -> None:
        broken = _broken(tmp_path, STREAMS, 'cadence     = "monthly"', 'cadence    = "every_month"')
        with pytest.raises(DeclarationError) as raised:
            loader.streams_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="stream[salary_uah].cadence"
        )
        assert raised.value.remedy is not None
        assert "semimonthly" in raised.value.remedy

    def test_an_unknown_direction_is_refused(self, tmp_path: Path) -> None:
        broken = _broken(tmp_path, INZHUR, 'direction     = "inbound"', 'direction     = "in"')
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        assert raised.value.field_path == "route.direction"

    def test_an_unknown_status_is_refused(self, tmp_path: Path) -> None:
        broken = _broken(tmp_path, INZHUR, 'status        = "open"', 'status        = "working"')
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        assert raised.value.field_path == "route.status"

    def test_an_unknown_indexation_policy_is_refused(self, tmp_path: Path) -> None:
        broken = _broken(tmp_path, STREAMS, 'policy = "cpi"', 'policy = "inflation"')
        with pytest.raises(DeclarationError) as raised:
            loader.streams_from_file(broken)
        assert raised.value.field_path == "stream[salary_uah].indexation.policy"


class TestChannelExactlyWhenTheLegConverts:
    """Row: a ``channel`` on a non-``fx`` leg, or missing on an ``fx`` leg (FR-011)."""

    def test_a_transfer_naming_a_channel_is_refused(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path,
            INZHUR,
            '  kind                   = "transfer"',
            '  kind                   = "transfer"\n  channel                = "p2p"',
        )
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="route.leg[0].channel")
        assert "converts nothing" in raised.value.problem

    def test_an_fx_leg_with_no_channel_is_refused(self, tmp_path: Path) -> None:
        broken = _without(tmp_path, P2P, '  channel                = "p2p"')
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="route.leg[0].channel")
        assert "mid-rate" in raised.value.problem

    def test_a_transfer_that_changes_currency_is_refused(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path,
            INZHUR,
            '  to_ccy                 = "UAH"',
            '  to_ccy                 = "USD"',
        )
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        assert raised.value.field_path == "route.leg[0].to_ccy"

    def test_a_channel_that_does_not_quote_the_legs_pair_is_refused(self) -> None:
        """A channel quotes one ordered pair; using it for another would invent a rate.

        ⚙ **Not reachable from a data file today, and the branch is still checked.** The core
        models two currencies, so *every* ``fx`` leg converts UAH against USD and both
        declared channels quote that pair -- in either order, which is legal and means the
        same quote read the other way round. The refusal exists for the day a third currency
        arrives, when a leg could name a channel that quotes a pair it does not touch, so it
        is exercised directly on a channel the loader itself would refuse (a self-quote)
        rather than left as a branch nothing has ever run.
        """
        channel = FxChannel(
            id="self_quote",
            pair=(Currency.UAH, Currency.UAH),
            reference_rate=42.0,
            buy_side=ChannelSide(
                markup_bps=150.0,
                premium_per_unit=None,
                kind="bank_fee_schedule",
                provenance=prov.EMPTY,
            ),
            sell_side=ChannelSide(
                markup_bps=150.0,
                premium_per_unit=None,
                kind="bank_fee_schedule",
                provenance=prov.EMPTY,
            ),
            observed_on=date(2026, 8, 22),
            kind="p2p_premium",
            provenance=prov.EMPTY,
        )
        leg = loader.route_from_file(P2P).legs[0]
        with pytest.raises(DeclarationError) as raised:
            resolver._check_channel(  # the branch under test is private, by design
                replace(leg, channel=channel.id), {channel.id: channel}, path=P2P
            )
        assert raised.value.field_path == "route.leg[0].channel"
        assert "inventing the number that does the converting" in raised.value.problem

    def test_a_pair_of_three_currencies_is_refused(self, tmp_path: Path) -> None:
        """A quote is between exactly two: the price currency and the unit currency."""
        broken = _broken(
            tmp_path,
            CHANNELS,
            'pair           = ["UAH", "USD"]',
            'pair           = ["UAH", "USD", "UAH"]',
        )
        with pytest.raises(DeclarationError) as raised:
            loader.channels_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="channel[p2p].pair")
        assert "exactly two" in raised.value.problem

    def test_an_empty_pair_is_refused(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path, CHANNELS, 'pair           = ["UAH", "USD"]', "pair           = []"
        )
        with pytest.raises(DeclarationError) as raised:
            loader.channels_from_file(broken)
        assert raised.value.field_path == "channel[p2p].pair"

    def test_an_fx_leg_converting_a_currency_into_itself_is_refused(self, tmp_path: Path) -> None:
        """A self-conversion has no side of the channel to take and no spread to cost."""
        broken = _broken(
            tmp_path, P2P, '  to_ccy                 = "USD"', '  to_ccy                 = "UAH"'
        )
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="route.leg[0].to_ccy")

    def test_a_self_quoting_channel_is_refused(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path, CHANNELS, 'pair           = ["UAH", "USD"]', 'pair           = ["UAH", "UAH"]'
        )
        with pytest.raises(DeclarationError) as raised:
            loader.channels_from_file(broken)
        assert raised.value.field_path == "channel[p2p].pair"


class TestAvailabilityWindows:
    """A leg's ``available_from``/``available_until``: parsed here, and a fact with a source.

    Not a row of the enforced-rules table on its own -- it is the "wrong-typed field" row
    applied to a date -- but the *epistemic* half is worth pinning: a window is an observation
    about a corridor and a regime transition is a guess, and the two must never be declarable
    in the same field (research.md D8).
    """

    def test_an_availability_window_is_parsed_as_dates(self, tmp_path: Path) -> None:
        """A leg's window is a **fact** about the corridor, with a source -- so it parses here.

        Never an assumption: a regime transition is scenario data with an explicit assumption
        marker, because burying a guess in a field whose every other value is an observation
        would make the two indistinguishable in every output (research.md D8).
        """
        broken = _broken(
            tmp_path,
            P2P,
            "  latency_days           = 0",
            '  available_from         = "2025-03-01"\n'
            '  available_until        = "2027-12-31"\n'
            "  latency_days           = 0",
        )
        leg = loader.route_from_file(broken).legs[0]
        assert leg.available_from == date(2025, 3, 1)
        assert leg.available_until == date(2027, 12, 31)

    def test_a_window_that_is_not_a_date_is_refused(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path,
            P2P,
            "  latency_days           = 0",
            '  available_from         = "March 2025"\n  latency_days           = 0',
        )
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="route.leg[0].available_from"
        )


class TestStreamIndexationAndTaxTreatment:
    """A stream's declared growth and its declared treatment: read once, never invented.

    ``indexation.rate_pct`` is the one ``_pct`` field left in the per-owner file, so this is
    where "divided by 100 exactly once" is checked for it -- and where the two venues of
    012 FR-024a are checked to be read separately rather than one from the other. **No tax
    rate is read here at all any more**: 012 moved every legal rate out of per-owner data and
    into ``data/tax/schemes/``, where a citation is required.
    """

    def test_a_fixed_rate_indexation_with_no_rate_is_refused(self, tmp_path: Path) -> None:
        """Half a growth assumption is not a growth assumption, and neither reading is free."""
        broken = _broken(tmp_path, STREAMS, 'policy = "cpi"', 'policy = "fixed_rate"')
        with pytest.raises(DeclarationError) as raised:
            loader.streams_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="stream[salary_uah].indexation.rate_pct"
        )
        assert "invented for him" in raised.value.problem

    def test_a_rate_under_a_policy_that_takes_none_is_refused(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path, STREAMS, '  policy = "cpi"', '  policy = "cpi"\n  rate_pct = 8.0'
        )
        with pytest.raises(DeclarationError) as raised:
            loader.streams_from_file(broken)
        assert raised.value.field_path == "stream[salary_uah].indexation.rate_pct"
        assert "refused rather than ignored" in raised.value.problem

    def test_a_fixed_rate_indexation_with_a_rate_becomes_a_fraction(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path,
            STREAMS,
            '  policy = "cpi"',
            '  policy = "fixed_rate"\n  rate_pct = 8.0',
        )
        indexation = loader.streams_from_file(broken)[0].indexation
        assert indexation.policy == "fixed_rate"
        assert indexation.rate == 0.08

    def test_the_two_venues_are_read_separately_and_neither_is_inferred(self) -> None:
        """012 FR-024a: the routing origin and the crediting destination are two facts.

        The shipped contract stream is the case that makes the distinction bite -- routed
        through Deel, credited to the ФОП account -- and reading one as the other would put
        it under a different reading of the law.
        """
        salary, contract = loader.streams_from_file(STREAMS)
        assert (salary.arrives_at, salary.credited_to) == ("monobank_uah", "monobank_uah")
        assert (contract.arrives_at, contract.credited_to) == ("deel", "fop")

    def test_a_stream_missing_its_crediting_destination_fails_at_load(self, tmp_path: Path) -> None:
        broken = _broken(tmp_path, STREAMS, 'credited_to = "monobank_uah"', "")
        with pytest.raises(DeclarationError) as raised:
            loader.streams_from_file(broken)
        assert "credited_to" in str(raised.value)


class TestChannelSideForms:
    """Rows: both or neither of ``markup_bps``/``premium_per_unit``; a side missing entirely."""

    def test_both_forms_on_one_side_are_refused_with_no_precedence_rule(
        self, tmp_path: Path
    ) -> None:
        broken = _broken(
            tmp_path,
            CHANNELS,
            "  premium_per_unit = 3.0",
            "  premium_per_unit = 3.0\n  markup_bps       = 150.0",
        )
        with pytest.raises(DeclarationError) as raised:
            loader.channels_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="channel[p2p].buy_side.markup_bps"
        )
        assert "no precedence rule" in raised.value.problem

    def test_neither_form_is_refused_because_an_empty_side_is_not_zero(
        self, tmp_path: Path
    ) -> None:
        broken = _without(tmp_path, CHANNELS, "  premium_per_unit = 3.0")
        with pytest.raises(DeclarationError) as raised:
            loader.channels_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="channel[p2p].buy_side")
        assert "not a zero" in raised.value.problem

    def test_a_zero_premium_is_legal_and_means_at_the_reference(self, tmp_path: Path) -> None:
        broken = _broken(tmp_path, CHANNELS, "  premium_per_unit = 3.0", "  premium_per_unit = 0.0")
        side = loader.channels_from_file(broken)[0].buy_side
        assert side.premium_per_unit is not None
        assert side.premium_per_unit.amount == 0.0

    @pytest.mark.parametrize(
        ("old", "new", "field"),
        [
            (
                "  premium_per_unit = 3.0",
                "  premium_per_unit = -42.0",
                "channel[p2p].buy_side.premium_per_unit",
            ),
            (
                "  premium_per_unit = -2.5",
                "  premium_per_unit = -45.0",
                "channel[p2p].sell_side.premium_per_unit",
            ),
        ],
    )
    def test_a_premium_that_zeroes_or_inverts_the_effective_rate_is_refused(
        self, tmp_path: Path, old: str, new: str, field: str
    ) -> None:
        """A side that gives away the whole reference (or more) is not a rate.

        ``-42`` on a reference of 42 makes the effective rate zero and the first costing
        divides by it; ``-45`` makes it negative and the conversion refuses the rate
        mid-costing. Both are load-time failures naming the file and the offset, not
        arithmetic errors three layers later. A negative premium stays legal while the
        effective rate stays positive -- the shipped ``-2.5`` is exactly that.
        """
        broken = _broken(tmp_path, CHANNELS, old, new)
        with pytest.raises(DeclarationError) as raised:
            loader.channels_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path=field)
        assert "42.0" in raised.value.problem, "the reason states the reference it is against"
        assert "not a rate" in raised.value.problem

    @pytest.mark.parametrize("bps", ["10000.0", "12000.0"])
    def test_a_sell_markup_of_the_whole_reference_or_more_is_refused(
        self, tmp_path: Path, bps: str
    ) -> None:
        """The markup form of the same defect: 10 000 bps subtracts the whole reference.

        The sell side is ``reference * (1 - m)``, so exactly 10 000 bps is a zero rate and
        anything above it a negative one. The first edit moves the *buy* markup to a
        distinct legal value so the second edit lands on the sell side.
        """
        text = CHANNELS.read_text(encoding="utf-8")
        text = _replace(text, "markup_bps   = 150.0", "markup_bps   = 175.0")
        text = _replace(text, "markup_bps   = 150.0", f"markup_bps   = {bps}")
        broken = tmp_path / "broken.toml"
        broken.write_text(text, encoding="utf-8")
        with pytest.raises(DeclarationError) as raised:
            loader.channels_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="channel[card].sell_side.markup_bps"
        )
        assert "not a rate" in raised.value.problem

    def test_a_huge_buy_markup_is_expensive_but_legal(self, tmp_path: Path) -> None:
        """The bound is on the effective rate per role, not on the declared number.

        12 000 bps on the buy side is a terrible price -- reference * 2.2 -- and still a
        rate. Refusing it would smuggle a plausibility judgement into a structural check.
        """
        broken = _broken(tmp_path, CHANNELS, "markup_bps   = 150.0", "markup_bps   = 12000.0")
        channel = loader.channels_from_file(broken)[1]
        assert channel.buy_side.markup_bps == 12000.0

    def test_a_missing_side_is_refused_and_no_mid_rate_is_synthesised(self, tmp_path: Path) -> None:
        head, _, _ = CHANNELS.read_text(encoding="utf-8").partition("  [channel.sell_side]")
        broken = tmp_path / "broken.toml"
        broken.write_text(head, encoding="utf-8")
        with pytest.raises(DeclarationError) as raised:
            loader.channels_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path="channel[0].sell_side")
        assert "No default value is substituted" in raised.value.problem, (
            "the sell side is not computed from the buy side: deriving it would be a "
            "mid-rate with extra steps, and it would force a symmetric spread on a market "
            "that is routinely asymmetric (FR-010)"
        )


class TestOutOfRangeAndNegativeNumbers:
    """Rows: ``disruption_probability`` outside ``[0, 1]``; negative fees or latency."""

    def test_a_probability_above_one_is_refused_not_clamped(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path,
            INZHUR,
            "  disruption_probability = 0.01",
            "  disruption_probability = 1.5",
        )
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="route.leg[0].disruption_probability"
        )
        assert "clamped" in raised.value.problem

    @pytest.mark.parametrize(
        ("old", "new", "field"),
        [
            (
                "  fee_pct                = 0.5",
                "  fee_pct                = -0.5",
                "route.leg[0].fee_pct",
            ),
            (
                "  fee_fixed              = 25.0",
                "  fee_fixed              = -25.0",
                "route.leg[0].fee_fixed",
            ),
            (
                "  latency_days           = 2",
                "  latency_days           = -2",
                "route.leg[0].latency_days",
            ),
            (
                "  minimum                = 100.0",
                "  minimum                = -100.0",
                "route.leg[0].minimum",
            ),
        ],
    )
    def test_a_negative_declared_number_is_refused(
        self, tmp_path: Path, old: str, new: str, field: str
    ) -> None:
        broken = _broken(tmp_path, COINBASE, old, new)
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        _assert_names_file_and_field(raised.value, file=broken, field_path=field)

    def test_a_zero_fee_is_a_real_declaration(self) -> None:
        """The mirror image: zero is what a free leg says, and it is not a missing value."""
        leg = loader.route_from_file(INZHUR).legs[0]
        assert leg.fee_pct == 0.0
        assert leg.fee_fixed.amount == 0.0
        assert prov.is_unverified(leg.fee_fixed.provenance), (
            "even a zero carries the citation of the table that declared it"
        )


class TestPartnerRoute:
    """Rows: the four things a declared exit route must be (FR-027)."""

    def test_a_dangling_partner_is_refused(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        _edit(
            root / "routes" / "monobank_to_binance_p2p.toml",
            'partner_route = "binance_p2p_to_monobank"',
            'partner_route = "binance_to_monobank"',
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        _assert_names_file_and_field(
            raised.value,
            file=root / "routes" / "monobank_to_binance_p2p.toml",
            field_path="route.partner_route",
        )
        assert "dangling" in raised.value.problem

    def test_an_absent_partner_is_legal_and_is_not_a_dangling_one(self) -> None:
        """The distinction the previous case depends on: omission is a declaration."""
        declarations = _resolve(DATA_ROOT)
        assert declarations.routes["coinbase_to_ibkr"].partner_route is None

    def test_an_inbound_route_as_a_partner_is_refused(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        _edit(
            root / "routes" / "monobank_to_binance_p2p.toml",
            'partner_route = "binance_p2p_to_monobank"',
            'partner_route = "inzhur_direct"',
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "route.partner_route"
        assert "not an exit" in raised.value.problem

    def test_an_exit_that_starts_somewhere_else_is_refused(self, tmp_path: Path) -> None:
        """The sharpest of the four: a pair that does not meet would produce a figure."""
        root = _root(tmp_path)
        _edit(
            root / "routes" / "inzhur_direct.toml",
            'partner_route = "inzhur_to_monobank"',
            'partner_route = "binance_p2p_to_monobank"',
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "route.partner_route"
        assert "two unrelated journeys" in raised.value.problem

    def test_an_exit_starting_in_a_currency_the_inbound_never_delivers_is_refused(
        self, tmp_path: Path
    ) -> None:
        """The seam is a currency as well as a venue, and both halves must meet.

        A pair meeting at the venue but not in the currency loads only if this check is
        missing -- and then costing it dies mid-walk as a raw currency mismatch naming
        neither file. The rewritten exit starts in UAH at binance while every inbound
        route delivers USD there.
        """
        root = _root(tmp_path)
        exit_path = root / "routes" / "binance_p2p_to_monobank.toml"
        text = exit_path.read_text(encoding="utf-8")
        text = _replace(
            text, 'kind                   = "fx"', 'kind                   = "transfer"'
        )
        text = _replace(text, 'from_ccy               = "USD"', 'from_ccy               = "UAH"')
        text = _drop_line(text, 'channel                = "p2p"')
        exit_path.write_text(text, encoding="utf-8")
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "route.partner_route"
        rendered = str(raised.value)
        assert "binance_p2p_to_monobank" in rendered, "the reason must name the partner"
        assert "binance_p2p_to_monobank.toml" in rendered, "and the partner's file"
        assert "UAH" in raised.value.problem
        assert "USD" in raised.value.problem

    def test_an_exit_not_ending_in_the_base_currency_is_refused(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        with pytest.raises(DeclarationError) as raised:
            resolver.ramp_from_data_root(root, base_currency=Currency.USD)
        assert raised.value.field_path == "route.partner_route"
        assert "spendable" in raised.value.problem

    def test_an_exit_route_may_not_declare_a_partner_of_its_own(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path,
            P2P_EXIT,
            'direction   = "exit"',
            'direction   = "exit"\npartner_route = "monobank_to_binance_p2p"',
        )
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        assert raised.value.field_path == "route.partner_route"
        assert "declared once" in raised.value.problem


class TestCapacityPools:
    """Rows: two legs naming one pool with different caps; a cap with no pool."""

    def test_two_files_disagreeing_about_one_rails_cap_are_both_named(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        _edit(
            root / "routes" / "monobank_to_binance_card.toml",
            "  monthly_cap            = 100000.0",
            "  monthly_cap            = 50000.0",
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        rendered = str(raised.value)
        assert "monobank_to_binance_card.toml" in rendered
        assert "monobank_to_binance_p2p" in rendered
        assert "at least one of them is wrong" in raised.value.problem

    def test_one_pool_with_caps_in_two_currencies_is_refused_naming_both_files(
        self, tmp_path: Path
    ) -> None:
        """A rail has one limit in one currency, and the resolver says so with a location.

        The mutation moves the p2p route's pool declaration from its UAH leg to its USD
        leg, so the shared card pool is declared with a UAH cap in one file and a USD cap
        in another. Without this rule the resolver's own comparison dies as a raw
        CurrencyMismatchError naming no file at all -- and so would the ledger fold.
        """
        root = _root(tmp_path)
        route_path = root / "routes" / "monobank_to_binance_p2p.toml"
        text = route_path.read_text(encoding="utf-8")
        text = _drop_line(text, 'capacity_pool          = "monobank_card_uah_usd"')
        text = _drop_line(text, "monthly_cap            = 100000.0")
        text = _replace(
            text,
            'kind                   = "transfer"',
            'kind                   = "transfer"\n'
            '  capacity_pool          = "monobank_card_uah_usd"\n'
            "  monthly_cap            = 100000.0",
        )
        route_path.write_text(text, encoding="utf-8")
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        _assert_names_file_and_field(
            raised.value, file=route_path, field_path="route.leg[1].monthly_cap"
        )
        rendered = str(raised.value)
        assert "monobank_card_uah_usd" in rendered, "the reason names the pool"
        assert "monobank_to_binance_card.toml" in rendered, "and the other file"
        assert "UAH" in raised.value.problem
        assert "USD" in raised.value.problem

    def test_a_cap_with_no_pool_is_refused(self, tmp_path: Path) -> None:
        broken = _without(tmp_path, P2P, '  capacity_pool          = "monobank_card_uah_usd"')
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="route.leg[0].capacity_pool"
        )
        assert "never consumed is not a limit" in raised.value.problem

    def test_a_pool_with_no_cap_is_refused(self, tmp_path: Path) -> None:
        broken = _without(tmp_path, P2P, "  monthly_cap            = 100000.0")
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        assert raised.value.field_path == "route.leg[0].monthly_cap"


class TestFallbackPolicy:
    """Row: a fallback policy of ``deposit`` fails by name, saying which feature brings it."""

    def test_a_deferred_policy_names_the_feature_that_will_bring_it(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path, SCENARIO, 'policy      = "hold_as_cash"', 'policy      = "place_on_deposit"'
        )
        with pytest.raises(DeclarationError) as raised:
            loader.scenario_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="scenario.fallback.policy"
        )
        assert "deposit instrument" in raised.value.problem
        assert "hold_as_cash" in (raised.value.remedy or ""), (
            "a policy that is real but not built yet is a wait, not a typo, and the message "
            "has to say which it is"
        )

    def test_an_unknown_policy_is_refused_naming_the_known_ones(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path, SCENARIO, 'policy      = "hold_as_cash"', 'policy      = "queue"'
        )
        with pytest.raises(DeclarationError) as raised:
            loader.scenario_from_file(broken)
        assert raised.value.field_path == "scenario.fallback.policy"
        assert "hold_as_cash" in (raised.value.remedy or "")


class TestStreamArrivalVenue:
    """Row: a stream's ``arrives_at`` naming an unknown venue."""

    def test_an_unknown_arrival_venue_is_refused(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        _edit(
            root / "streams" / "owner-001.toml",
            'arrives_at  = "monobank_uah"',
            'arrives_at = "monobank"',
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        _assert_names_file_and_field(
            raised.value,
            file=root / "streams" / "owner-001.toml",
            field_path="stream[salary_uah].arrives_at",
        )

    def test_a_stream_whose_venue_cannot_hold_its_currency_is_refused(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        # The dollar stream, whichever venue it declares today: ``inzhur`` holds hryvnia only,
        # so pointing a USD stream at it is the mismatch under test.
        _edit(
            root / "streams" / "owner-001.toml",
            'arrives_at  = "deel"',
            'arrives_at = "inzhur"',
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "stream[contract_usd].arrives_at"
        assert "USD" in raised.value.problem


class TestMalformedFile:
    """Row: malformed TOML, and a missing file, each naming the file."""

    def test_unparseable_toml_names_the_file(self, tmp_path: Path) -> None:
        broken = tmp_path / "broken.toml"
        broken.write_text("[route\nid = ", encoding="utf-8")
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        assert raised.value.file == broken
        assert "not valid TOML" in raised.value.problem

    def test_a_missing_file_is_reported_rather_than_treated_as_empty(self, tmp_path: Path) -> None:
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(tmp_path / "nothing.toml")
        assert raised.value.file == tmp_path / "nothing.toml"

    def test_an_empty_routes_directory_is_reported(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        for path in (root / "routes").glob("*.toml"):
            path.unlink()
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.file == root / "routes"

    def test_an_entirely_empty_file_is_reported_per_declaration_kind(self, tmp_path: Path) -> None:
        """No key at all: the shape validation refuses it, naming the array it wanted."""
        for stem, load in (
            ("kinds", loader.observation_kinds_from_file),
            ("venues", loader.venues_from_file),
            ("channels", loader.channels_from_file),
            ("streams", loader.streams_from_file),
        ):
            empty = tmp_path / f"{stem}.toml"
            empty.write_text("", encoding="utf-8")
            with pytest.raises(DeclarationError) as raised:
                load(empty)
            assert raised.value.file == empty

    def test_an_explicitly_empty_declaration_list_is_reported_too(self, tmp_path: Path) -> None:
        """``kind = []`` is a *declaration* that nothing is declared, and it is refused.

        A separate case from the empty file, because it takes a different path: the shape is
        valid and the emptiness is the problem. Reading either as "nothing ages", "money
        cannot sit anywhere", "this pair cannot be converted" or "no money arrives" would
        make every reference to them fail later, each naming the wrong file.
        """
        for array, stem, load in (
            ("kind", "kinds", loader.observation_kinds_from_file),
            ("venue", "venues", loader.venues_from_file),
            ("channel", "channels", loader.channels_from_file),
            ("stream", "streams", loader.streams_from_file),
        ):
            empty = tmp_path / f"{stem}_list.toml"
            empty.write_text(f"{array} = []\n", encoding="utf-8")
            with pytest.raises(DeclarationError) as raised:
                load(empty)
            _assert_names_file_and_field(raised.value, file=empty, field_path=array)

    def test_a_duplicate_observation_kind_id_is_refused(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        _edit(
            root / "observation_kinds.toml",
            'id             = "bank_fee_schedule"',
            'id             = "p2p_premium"',
        )
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "kind[p2p_premium].id"


class TestNoPydanticTypeEscapes:
    """The boundary rule itself: a ``ValidationError`` reaching a caller is a leak."""

    def test_a_structural_failure_raises_the_projects_own_error_type(self, tmp_path: Path) -> None:
        broken = _broken(
            tmp_path, P2P, "  fee_pct                = 0.0", "  fee_pct                = true"
        )
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        assert not isinstance(raised.value, pydantic.ValidationError)

    def test_the_error_record_carries_all_four_fields(self, tmp_path: Path) -> None:
        broken = _without(tmp_path, P2P, "  fee_fixed              = 0.0")
        with pytest.raises(DeclarationError) as raised:
            loader.route_from_file(broken)
        assert raised.value.file == broken
        assert raised.value.field_path
        assert raised.value.problem
        assert raised.value.remedy is not None


class TestTheBatteryCoversTheContract:
    """The battery is only a proof of SC-011 if it covers every row of the table.

    A list that drifts out of step with the contract is the failure mode here: a row is
    added to ``declaration-schema.md``, no case is written, and the suite stays green while
    the rule goes unenforced. This test cannot detect a *new* row, but it pins the set of
    cases that exist, so removing one is a deliberate act.
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
            "TestUndeclaredObservationKind",
            "TestDuplicateIdentifiers",
            "TestARouteWithNoLegs",
            "TestLegsThatDoNotChain",
            "TestFirstAndLastLeg",
            "TestAVenueThatCannotHoldTheCurrency",
            "TestUnknownDeclaredName",
            "TestChannelExactlyWhenTheLegConverts",
            "TestAvailabilityWindows",
            "TestStreamIndexationAndTaxTreatment",
            "TestChannelSideForms",
            "TestOutOfRangeAndNegativeNumbers",
            "TestPartnerRoute",
            "TestCapacityPools",
            "TestFallbackPolicy",
            "TestStreamArrivalVenue",
            "TestMalformedFile",
            "TestNoPydanticTypeEscapes",
            "TestTheBatteryCoversTheContract",
        }
