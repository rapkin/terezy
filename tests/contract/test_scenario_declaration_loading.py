"""A battery of deliberately broken scenario declarations, one case per rule.

The data half of **FR-019** and **FR-020**. ``core/scenarios/regimes.py`` can select a route
set by date; this suite is about whether a regime can be *declared* -- and about every way a
declaration of a belief can be incoherent.

**Why these rules and not others.** A regime is the owner's belief about which corridors
exist, and a transition is a guess about a date. Neither can be checked against the world, so
the only things a loader can check are **coherence** and **completeness**: that the chain of
regimes covers every date exactly once, that every route named exists, that the set is closed
under the pairing FR-027 requires, and that the assumption is marked as one. Every failure is
refused rather than repaired: reordering transitions, bridging a gap or defaulting a policy
would be choosing the owner's belief for him, which is the one thing a tool holding somebody
else's money must not do.

**The core refuses several of these too, by raising.** ``regimes._checked`` and
``regimes.routes_in_force`` raise on an unordered chain, a gap, an undeclared regime and a
partner-orphaned route -- correctly, because reaching them means the load-time check was
bypassed. Checking here is what turns a raise mid-comparison into a message naming this file
and this row, which is the whole division of labour research.md D6 describes.

**Also here: the data-only claim for regimes.** A *third* regime, added as data alone,
narrows the route set with zero source changes. That is Principle II for the one entity this
feature nearly left as code -- ``plan.md`` promised regimes in scenario data and no task
built the loader for them until Phase 7b.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

from terezy.core.primitives.currency import Currency
from terezy.core.routes import capacity
from terezy.core.scenarios import regimes
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError

pytestmark = pytest.mark.contract

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
SCENARIO = DATA_ROOT / "scenarios" / "war_end.toml"

WARTIME_ROUTES = frozenset(
    {
        "inzhur_direct",
        "inzhur_to_monobank",
        "monobank_to_binance_p2p",
        "monobank_to_binance_p2p_double",
        "binance_p2p_to_monobank",
        "deel_to_fop",
        "deel_to_coinbase",
        "fop_usd_to_monobank_uah",
    }
)
"""What the shipped wartime regime believes in. Restated here so a silent change to the
shipped file fails a test rather than quietly changing what every case below assumes."""


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith("#")


def _replace(text: str, old: str, new: str) -> str:
    """One textual edit to the first declaring line, failing loudly if it matches nothing."""
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if old in line and not _is_comment(line):
            lines[index] = line.replace(old, new, 1)
            return "".join(lines)
    pytest.fail(f"the shipped scenario no longer declares {old!r}; this test is stale")


def _broken(tmp_path: Path, old: str, new: str) -> Path:
    """The shipped scenario with one line edited."""
    target = tmp_path / "broken.toml"
    target.write_text(_replace(SCENARIO.read_text(encoding="utf-8"), old, new), encoding="utf-8")
    return target


def _emptied(tmp_path: Path, key: str) -> Path:
    """The shipped scenario with one field emptied, keeping its indent.

    A whole-line rewrite rather than a substring edit: the rationale is a paragraph, and
    replacing part of it would leave the rest of the sentence behind -- a file that is still
    valid, and a case asserting an error that never came.
    """
    lines = SCENARIO.read_text(encoding="utf-8").splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.strip().startswith(f"{key} ") and not _is_comment(line):
            indent = line[: len(line) - len(line.lstrip())]
            lines[index] = f'{indent}{key} = ""\n'
            target = tmp_path / "broken.toml"
            target.write_text("".join(lines), encoding="utf-8")
            return target
    pytest.fail(f"the shipped scenario no longer declares {key!r}; this test is stale")


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _resolve(root: Path) -> resolver.RampDeclarations:
    return resolver.ramp_from_data_root(root, base_currency=Currency.UAH)


def _edit_scenario(root: Path, old: str, new: str) -> None:
    path = root / "scenarios" / "war_end.toml"
    path.write_text(_replace(path.read_text(encoding="utf-8"), old, new), encoding="utf-8")


def _assert_names_file_and_field(raised: DeclarationError, *, file: Path, field_path: str) -> None:
    assert raised.file == file
    assert raised.field_path == field_path, f"expected {field_path!r}, got {raised.field_path!r}"
    assert field_path in str(raised)
    assert raised.problem


class TestTheShippedScenarioLoads:
    """The baseline, and the shape every case below is a mutation of."""

    def test_the_regimes_transitions_and_fallback_are_what_the_file_says(self) -> None:
        scenario = loader.scenario_from_file(SCENARIO)
        assert scenario.id == "war_end"
        assert scenario.owner_id == "owner-001"
        assert [regime.id for regime in scenario.regimes] == ["wartime", "normalized"]
        assert scenario.regimes[0].route_ids == WARTIME_ROUTES
        assert scenario.fallback_policy == capacity.HOLD_AS_CASH
        assert scenario.redirect_to is None

    def test_the_transition_is_a_marked_assumption_with_a_rationale(self) -> None:
        transition = loader.scenario_from_file(SCENARIO).transitions[0]
        assert transition.on_date == date(2027, 6, 30)
        assert (transition.before, transition.after) == ("wartime", "normalized")
        assert transition.is_assumption is True
        assert "ASSUMPTION" in regimes.stated_assumption(transition), (
            "FR-020: the date is presented as a stated assumption, never as a known fact"
        )
        assert transition.rationale in regimes.stated_assumption(transition)

    def test_the_scenario_selects_a_route_set_on_each_side_of_the_date(self) -> None:
        """FR-019 end to end, from the file: two dates, two route sets, one assumption."""
        declarations = _resolve(DATA_ROOT)
        scenario = declarations.scenarios["war_end"]
        by_id = {regime.id: regime for regime in scenario.regimes}
        before = regimes.routes_in_force(
            by_id,
            declarations.routes,
            transitions=scenario.transitions,
            on_date=date(2027, 1, 1),
        )
        after = regimes.routes_in_force(
            by_id,
            declarations.routes,
            transitions=scenario.transitions,
            on_date=date(2027, 7, 1),
        )
        assert before.regime.id == "wartime"
        assert after.regime.id == "normalized"
        assert set(before.routes) == WARTIME_ROUTES
        assert "monobank_to_binance_card" in after.routes
        assert "monobank_to_binance_card" in before.excluded, (
            "an assumption's consequence is named rather than quietly absent"
        )
        assert before.decided_by is scenario.transitions[0]


class TestARegimeMustNameDeclaredRoutes:
    """A regime selects from the declared routes; it declares none of its own."""

    def test_an_unresolved_route_id_is_refused_naming_the_declared_ones(
        self, tmp_path: Path
    ) -> None:
        root = _root(tmp_path)
        _edit_scenario(root, '"inzhur_direct",', '"inzhur_direkt",')
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        _assert_names_file_and_field(
            raised.value,
            file=root / "scenarios" / "war_end.toml",
            field_path="scenario.regime[wartime].route_ids",
        )
        assert "inzhur_direct" in raised.value.problem

    def test_an_empty_route_set_is_refused(self, tmp_path: Path) -> None:
        text = SCENARIO.read_text(encoding="utf-8")
        head, _, tail = text.partition('  [[scenario.regime]]\n  id        = "wartime"')
        broken = tmp_path / "broken.toml"
        broken.write_text(
            head
            + '  [[scenario.regime]]\n  id        = "wartime"\n  route_ids = []\n'
            + tail.partition("  [[scenario.regime]]")[1]
            + tail.partition("  [[scenario.regime]]")[2],
            encoding="utf-8",
        )
        with pytest.raises(DeclarationError) as raised:
            loader.scenario_from_file(broken)
        assert raised.value.field_path == "scenario.regime[wartime].route_ids"


class TestARegimeMustBePartnerClosed:
    """Including a way in while excluding its declared way out is refused (FR-027)."""

    def test_dropping_an_exit_route_from_a_regime_is_refused(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        _edit_scenario(root, '    "binance_p2p_to_monobank",\n', "")
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "scenario.regime[wartime].route_ids"
        assert "one-way" in raised.value.problem
        assert "monobank_to_binance_p2p -> binance_p2p_to_monobank" in raised.value.problem

    def test_the_core_would_have_raised_on_the_same_scenario(self, tmp_path: Path) -> None:
        """Why the load-time check is worth having: the alternative is a raise mid-run.

        Constructed by narrowing a *loaded* regime rather than by loading a broken file,
        because a broken file no longer gets this far -- which is the point.
        """
        declarations = _resolve(DATA_ROOT)
        scenario = declarations.scenarios["war_end"]
        narrowed = regimes.Regime(
            id="wartime",
            route_ids=scenario.regimes[0].route_ids - {"binance_p2p_to_monobank"},
        )
        with pytest.raises(ValueError, match="exit route it excludes"):
            regimes.routes_in_force(
                {"wartime": narrowed, "normalized": scenario.regimes[1]},
                declarations.routes,
                transitions=scenario.transitions,
                on_date=date(2027, 1, 1),
            )


class TestTransitionsMustDescribeOneChain:
    """Ascending, joined, and naming regimes that exist -- or refused, never repaired."""

    def test_transitions_out_of_date_order_are_refused(self, tmp_path: Path) -> None:
        broken = _appended_transition(
            tmp_path, on_date="2026-01-01", before="normalized", after="wartime"
        )
        with pytest.raises(DeclarationError) as raised:
            loader.scenario_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="scenario.transition[1].on_date"
        )
        assert "strictly ascending" in (raised.value.remedy or "")

    def test_a_broken_chain_is_refused_naming_the_gap(self, tmp_path: Path) -> None:
        broken = _appended_transition(
            tmp_path, on_date="2028-01-01", before="wartime", after="normalized"
        )
        with pytest.raises(DeclarationError) as raised:
            loader.scenario_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="scenario.transition[1].before"
        )
        assert "regime nobody declared" in raised.value.problem

    def test_a_transition_naming_an_undeclared_regime_is_refused(self, tmp_path: Path) -> None:
        broken = _broken(tmp_path, 'after         = "normalized"', 'after         = "peacetime"')
        with pytest.raises(DeclarationError) as raised:
            loader.scenario_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="scenario.transition[0].after"
        )
        assert "wartime" in raised.value.problem

    def test_a_transition_from_a_regime_to_itself_is_refused(self, tmp_path: Path) -> None:
        broken = _broken(tmp_path, 'before        = "wartime"', 'before        = "normalized"')
        with pytest.raises(DeclarationError) as raised:
            loader.scenario_from_file(broken)
        assert raised.value.field_path == "scenario.transition[0].after"
        assert "transitions nothing" in raised.value.problem

    def test_a_scenario_with_no_transition_is_refused(self, tmp_path: Path) -> None:
        text = SCENARIO.read_text(encoding="utf-8")
        broken = tmp_path / "broken.toml"
        broken.write_text(text.partition("  [[scenario.transition]]")[0], encoding="utf-8")
        with pytest.raises(DeclarationError) as raised:
            loader.scenario_from_file(broken)
        assert raised.value.field_path == "scenario.transition"

    def test_a_valid_three_segment_chain_loads(self, tmp_path: Path) -> None:
        """The validation loop run to completion on a *valid* chain, not only on broken ones.

        A loop that has only ever been run to its first failure is untested validation: the
        pairwise walk could be off by one and every case above would still pass.
        """
        text = SCENARIO.read_text(encoding="utf-8")
        broken = tmp_path / "three.toml"
        broken.write_text(
            text
            + _transition_text(on_date="2029-01-01", before="normalized", after="wartime")
            + _transition_text(on_date="2031-01-01", before="wartime", after="normalized"),
            encoding="utf-8",
        )
        scenario = loader.scenario_from_file(broken)
        assert [transition.on_date for transition in scenario.transitions] == [
            date(2027, 6, 30),
            date(2029, 1, 1),
            date(2031, 1, 1),
        ]


class TestAnAssumptionMustSayItIsOne:
    """FR-020: a marker that can be switched off is not a marker."""

    def test_is_assumption_false_is_refused(self, tmp_path: Path) -> None:
        broken = _broken(tmp_path, "is_assumption = true", "is_assumption = false")
        with pytest.raises(DeclarationError) as raised:
            loader.scenario_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="scenario.transition[0].is_assumption"
        )
        assert "available_from" in (raised.value.remedy or ""), (
            "the remedy has to name where an observed fact belongs, or the message reads as "
            "'say true and move on'"
        )

    def test_a_missing_rationale_is_refused(self, tmp_path: Path) -> None:
        broken = _emptied(tmp_path, "rationale")
        with pytest.raises(DeclarationError) as raised:
            loader.scenario_from_file(broken)
        assert raised.value.field_path == "scenario.transition[0].rationale"
        assert "carries where an observation carries a source" in raised.value.problem


class TestDuplicateRegimeIds:
    """Two regimes with one id in one file: not merged, and neither preferred."""

    def test_a_duplicate_regime_id_is_refused(self, tmp_path: Path) -> None:
        broken = _broken(tmp_path, 'id        = "normalized"', 'id        = "wartime"')
        with pytest.raises(DeclarationError) as raised:
            loader.scenario_from_file(broken)
        assert raised.value.field_path == "scenario.regime[wartime].id"
        assert "would win by position" in raised.value.problem

    def test_two_scenario_files_with_one_id_are_refused(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        copy = root / "scenarios" / "aaa_copy.toml"
        copy.write_text(SCENARIO.read_text(encoding="utf-8"), encoding="utf-8")
        with pytest.raises(DeclarationError) as raised:
            _resolve(root)
        assert raised.value.field_path == "scenario.id"


class TestTheFallbackPolicy:
    """FR-013's declaration: a named policy, and a named destination when it redirects."""

    def test_a_redirect_with_no_destination_is_refused(self, tmp_path: Path) -> None:
        broken = _broken(tmp_path, 'policy      = "hold_as_cash"', 'policy      = "redirect"')
        with pytest.raises(DeclarationError) as raised:
            loader.scenario_from_file(broken)
        _assert_names_file_and_field(
            raised.value, file=broken, field_path="scenario.fallback.redirect_to"
        )
        assert "named" in raised.value.problem

    def test_a_destination_under_a_policy_that_does_not_redirect_is_refused(
        self, tmp_path: Path
    ) -> None:
        broken = _broken(tmp_path, 'redirect_to = ""', 'redirect_to = "ovdp_synthetic_a"')
        with pytest.raises(DeclarationError) as raised:
            loader.scenario_from_file(broken)
        assert raised.value.field_path == "scenario.fallback.redirect_to"
        assert "refused rather than ignored" in raised.value.problem

    def test_a_redirect_with_a_destination_loads(self, tmp_path: Path) -> None:
        target = tmp_path / "redirecting.toml"
        target.write_text(
            _replace(
                _replace(
                    SCENARIO.read_text(encoding="utf-8"),
                    'policy      = "hold_as_cash"',
                    'policy      = "redirect"',
                ),
                'redirect_to = ""',
                'redirect_to = "ovdp_synthetic_a"',
            ),
            encoding="utf-8",
        )
        scenario = loader.scenario_from_file(target)
        assert scenario.fallback_policy == capacity.REDIRECT
        assert scenario.redirect_to == "ovdp_synthetic_a"

    def test_a_missing_redirect_to_key_is_refused(self, tmp_path: Path) -> None:
        """Present-and-empty, on the ``verified_on`` precedent: absence is not emptiness."""
        text = SCENARIO.read_text(encoding="utf-8")
        broken = tmp_path / "broken.toml"
        broken.write_text(
            "".join(line for line in text.splitlines(keepends=True) if "redirect_to =" not in line),
            encoding="utf-8",
        )
        with pytest.raises(DeclarationError) as raised:
            loader.scenario_from_file(broken)
        assert raised.value.field_path == "scenario.fallback.redirect_to"


class TestAThirdRegimeIsDataOnly:
    """Principle II for the entity this feature nearly left as code.

    A third regime, declared in a file and nowhere else, narrows the route set on a date --
    with no engine edit, no registration, and no branch on a regime id.
    """

    def test_a_third_regime_added_as_data_narrows_the_route_set(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        path = root / "scenarios" / "war_end.toml"
        path.write_text(
            path.read_text(encoding="utf-8") + "\n  [[scenario.regime]]\n"
            '  id        = "domestic_only"\n'
            '  route_ids = ["inzhur_direct", "inzhur_to_monobank"]\n'
            + _transition_text(on_date="2030-01-01", before="normalized", after="domestic_only"),
            encoding="utf-8",
        )
        declarations = _resolve(root)
        scenario = declarations.scenarios["war_end"]
        by_id = {regime.id: regime for regime in scenario.regimes}
        assert set(by_id) == {"wartime", "normalized", "domestic_only"}
        in_force = regimes.routes_in_force(
            by_id,
            declarations.routes,
            transitions=scenario.transitions,
            on_date=date(2030, 6, 1),
        )
        assert set(in_force.routes) == {"inzhur_direct", "inzhur_to_monobank"}
        assert "monobank_to_binance_p2p" in in_force.excluded
        assert in_force.decided_by.on_date == date(2030, 1, 1)

    def test_no_module_in_the_engine_names_a_regime(self) -> None:
        """The greppable half: a branch on a regime id would be the violation."""
        source_root = Path(__file__).resolve().parents[2] / "src" / "terezy"
        found = {
            str(path.relative_to(source_root))
            for path in sorted(source_root.rglob("*.py"))
            if any(
                marker in path.read_text(encoding="utf-8")
                for marker in ('"wartime"', '"normalized"', '"domestic_only"')
            )
        }
        assert not found, (
            "a module names a specific regime, so that regime's meaning is code rather than "
            f"data (Principle II): {sorted(found)}"
        )


def _transition_text(*, on_date: str, before: str, after: str) -> str:
    """One extra ``[[scenario.transition]]`` block, as text.

    Built as text rather than as a record because what is under test is the *file* -- a
    record built in code would skip the shape validation that is half of what these cases
    assert.
    """
    return (
        "\n  [[scenario.transition]]\n"
        f'  on_date       = "{on_date}"\n'
        f'  before        = "{before}"\n'
        f'  after         = "{after}"\n'
        "  is_assumption = true\n"
        '  rationale     = "A second placeholder belief, for a test. Nobody knows this '
        'date either."\n'
    )


def _appended_transition(tmp_path: Path, *, on_date: str, before: str, after: str) -> Path:
    """The shipped scenario with one more transition appended, valid or not."""
    target = tmp_path / "broken.toml"
    target.write_text(
        SCENARIO.read_text(encoding="utf-8")
        + _transition_text(on_date=on_date, before=before, after=after),
        encoding="utf-8",
    )
    return target
