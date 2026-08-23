"""Declared regimes reach the audit, and exactly one scenario's do. **FR-013, FR-014, FR-015.**

``coverage()`` has taken a ``regimes`` mapping since the feature landed, and until this module
existed nothing filled it from a data root: ``CoverageDeclarations`` exposed
``ramp.scenarios`` and nothing flattened a scenario's regimes into the shape the audit wants,
so every real-data caller passed ``regimes={}``. On the shipped registry — which declares
``wartime`` and ``normalized`` in ``data/scenarios/war_end.toml`` — that produced a report
marked ``implicit``, over a route set no declared regime believes in. FR-013's per-regime
audit was unreachable from real data, and every regime test hand-built its records.

**The unit of belief is a scenario, not a regime** (research.md D17, owner decision
2026-08-23). A scenario declares the regimes and the transition between them; two scenarios
are two mutually exclusive beliefs about the world, and an audit that pooled their regimes
would state coverage under a world nobody declared. So the loading surface takes one
``scenario_id`` and resolves that scenario's regimes alone — and ``None`` means FR-015's
single implicit regime, chosen out loud rather than arrived at by forgetting an argument.

The four claims below are the whole of that: the shipped registry states both its declared
regimes; a corridor one regime names and the other does not produces two different verdicts
and two different blocked counts; an unknown scenario is refused rather than quietly falling
back to the implicit regime; and a second scenario in the data root changes nothing about the
first, because nothing is merged across the two.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from terezy.core.primitives.currency import Currency
from terezy.core.results.coverage import (
    IMPLICIT_REGIME_ID,
    NO_INBOUND,
    CoverageReport,
    NotReady,
    PairVerdict,
)
from terezy.core.routes.coverage import coverage
from terezy.data.declarations import resolver
from terezy.data.declarations.errors import DeclarationError

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"

IBKR_FROM_CONTRACT = ("ibkr_usd", "USD", "contract_usd")
"""The pair the two shipped regimes disagree about.

``coinbase_to_ibkr`` is named by ``normalized`` and not by ``wartime``, and it is the only way
the dollar contract income reaches ``ibkr_usd``. So the same pair is missing a way *in* under
one belief and not under the other — which is FR-013's requirement in the smallest form the
shipped declarations can state it.
"""


def _report(root: Path, *, scenario_id: str | None) -> CoverageReport:
    """The report the ordinary loading path produces, under one named scenario or none."""
    declarations = resolver.coverage_from_data_root(
        root, base_currency=Currency.UAH, scenario_id=scenario_id
    )
    produced = coverage(
        venues=declarations.ramp.venues,
        streams=declarations.ramp.streams,
        routes=declarations.ramp.routes,
        regimes=declarations.regimes,
        spendable=declarations.spendable,
    )
    assert isinstance(produced, CoverageReport), produced
    return produced


def _verdict(report: CoverageReport, regime_id: str, key: tuple[str, str, str]) -> PairVerdict:
    (block,) = [block for block in report.regimes if block.regime_id == regime_id]
    return next(
        verdict
        for verdict in block.verdicts
        if (verdict.destination.venue_id, verdict.destination.currency.value, verdict.stream_id)
        == key
    )


def test_the_shipped_registry_audited_under_war_end_states_both_declared_regimes() -> None:
    """The first end-to-end exercise of FR-013 through the loader."""
    report = _report(DATA_ROOT, scenario_id="war_end")
    assert [(block.regime_id, block.source) for block in report.regimes] == [
        ("normalized", "declared"),
        ("wartime", "declared"),
    ]
    assert report.audited.regime_ids == ("normalized", "wartime")
    # Each block audits its own regime's route set, and the two are genuinely different.
    wartime, normalized = (
        next(block.route_ids for block in report.regimes if block.regime_id == name)
        for name in ("wartime", "normalized")
    )
    assert set(normalized) - set(wartime) == {"monobank_to_binance_card", "coinbase_to_ibkr"}


def test_a_route_one_regime_names_and_the_other_does_not_gives_two_verdicts() -> None:
    """**FR-013 and FR-014, from declarations rather than from hand-built records.**

    Under ``wartime`` nothing carries the dollar contract income to ``ibkr_usd``, so the pair
    is short a way in. Under ``normalized`` the corridor is named, so that deficit is gone —
    and the missing *exit* remains under both, because no regime declares one. Two verdicts
    for one pair, no blended third.
    """
    report = _report(DATA_ROOT, scenario_id="war_end")

    under_wartime = _verdict(report, "wartime", IBKR_FROM_CONTRACT)
    under_normalized = _verdict(report, "normalized", IBKR_FROM_CONTRACT)
    assert isinstance(under_wartime, NotReady)
    assert isinstance(under_normalized, NotReady)
    assert NO_INBOUND in {deficit.kind for deficit in under_wartime.deficits}
    assert NO_INBOUND not in {deficit.kind for deficit in under_normalized.deficits}

    # And the same missing declaration is recognizably one item with a count per regime,
    # never summed: it blocks a pair under wartime and none under normalized.
    missing_inbound = next(
        deficit.missing for deficit in under_wartime.deficits if deficit.kind == NO_INBOUND
    )
    observation = next(entry for entry in report.to_observe if entry.missing == missing_inbound)
    assert observation.blocked_by_regime == (("normalized", 0), ("wartime", 1))


def test_an_unknown_scenario_is_refused_rather_than_silently_implicit() -> None:
    """Naming a scenario nobody declared is a mistake, and the flattering reading is the
    dangerous one.

    Falling back to the implicit regime would audit **every** declared route under a belief
    the caller did not ask for and did not get — the confident-wrong output this feature
    exists to prevent. The refusal lists what *is* declared, so the caller can correct the
    name from the message.
    """
    with pytest.raises(DeclarationError) as caught:
        resolver.coverage_from_data_root(
            DATA_ROOT, base_currency=Currency.UAH, scenario_id="peace_now"
        )
    assert caught.value.file == DATA_ROOT / resolver.SCENARIOS_DIR
    assert "peace_now" in caught.value.problem
    assert "war_end" in caught.value.problem
    assert "war_end.toml" in caught.value.problem


def test_a_regime_id_is_not_a_scenario_id() -> None:
    """``wartime`` is a regime inside ``war_end``, and naming it here is the same mistake.

    Worth its own case because it is the mistake a reader of the report will actually make:
    the blocks are labelled by regime, so the regime id is the name in front of them.
    """
    with pytest.raises(DeclarationError) as caught:
        resolver.coverage_from_data_root(
            DATA_ROOT, base_currency=Currency.UAH, scenario_id="wartime"
        )
    assert "wartime" in caught.value.problem


def test_no_scenario_named_audits_every_declared_route_under_one_implicit_regime() -> None:
    """**FR-015**, unchanged and now stated by the caller rather than by an empty mapping."""
    report = _report(DATA_ROOT, scenario_id=None)
    (block,) = report.regimes
    assert block.regime_id == IMPLICIT_REGIME_ID
    assert block.source == "implicit"
    declarations = resolver.coverage_from_data_root(
        DATA_ROOT, base_currency=Currency.UAH, scenario_id=None
    )
    assert set(block.route_ids) == set(declarations.ramp.routes)
    assert declarations.regimes == {}
    assert report.audited.regime_ids == ()


SECOND_SCENARIO = """# SYNTHETIC FIXTURE -- a second belief, declared by a contract test.

[scenario]
id       = "capital_controls_lifted"
owner_id = "owner-001"

  [scenario.fallback]
  policy      = "hold_as_cash"
  redirect_to = ""

  [[scenario.regime]]
  id        = "controlled"
  route_ids = ["inzhur_direct", "inzhur_to_monobank"]

  [[scenario.regime]]
  id        = "free"
  route_ids = [
    "inzhur_direct",
    "inzhur_to_monobank",
    "monobank_to_binance_p2p",
    "binance_p2p_to_monobank",
  ]

  [[scenario.transition]]
  on_date       = "2028-01-01"
  before        = "controlled"
  after         = "free"
  is_assumption = true
  rationale     = "SYNTHETIC FIXTURE -- an invented belief, declared so that two \
scenarios exist in one data root. Nobody holds it; it is here to prove that the audit \
refuses to blend two of them."
"""


def test_a_second_scenario_in_the_data_root_changes_nothing_about_the_first(
    tmp_path: Path,
) -> None:
    """**Blending is refused by construction, not merged.**

    Two scenarios are two mutually exclusive beliefs about the world. Pooling their regimes
    would produce a report about a world nobody declared — and worse, it would look like a
    thorough one, with four blocks where the owner holds two beliefs of two regimes each. So
    the audit takes one scenario and the second may as well not be in the root: the blocks,
    their route sets and their verdicts are identical to the shipped registry's.
    """
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    (root / "scenarios" / "capital_controls.toml").write_text(SECOND_SCENARIO, encoding="utf-8")

    with_second = _report(root, scenario_id="war_end")
    shipped = _report(DATA_ROOT, scenario_id="war_end")
    assert with_second.regimes == shipped.regimes
    assert with_second.audited.regime_ids == ("normalized", "wartime")

    # And the other belief is audited only when it is the one asked for.
    other = _report(root, scenario_id="capital_controls_lifted")
    assert [block.regime_id for block in other.regimes] == ["controlled", "free"]
