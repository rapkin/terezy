"""Group membership is read from the declared label and from nothing else.

015 SC-032 and SC-033. Four inferences look right on today's registry, and the fixture below
trips **all four at once**: an instrument of the same class, with the same ``ovdp_`` id prefix,
under the same ``ua_government_bond`` tax class, bought at the same ``inzhur`` venue -- and
declaring ``groups = []``. It must be in no group. The test fails if any of the four is ever
consulted.

**The pair is the criterion, not the first half.** Added *without* the label the count is
unchanged; added *with* it the count rises by exactly one. The unchanged half alone passes for
at least three broken implementations -- a resolution that is always empty, one computed once
and cached, and one read from the group declaration file rather than from the labels the
instruments carry, which is a live design fork rather than a hypothetical.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from terezy.core.decision.answer import answer, considered_ids
from terezy.core.primitives.currency import Currency
from terezy.core.results.answer import Answer, DeclaredSubject
from terezy.data.declarations import loader, resolver
from tests import answer_registries as fixtures
from tests import data_roots

pytestmark = pytest.mark.contract

FIXTURE = "enumerated_out_of_order"
MODELLED_ON = "UA4000235865"
"""The fixture and the real issue whose published list it is shaped like."""

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = data_roots.with_fixtures()

LOOKALIKE = "ovdp_lookalike"
"""Named to trip the id-prefix inference: four of the overlay's six bonds are ``ovdp_*``,
and no shipped instrument is."""

ACCESS_ENTRY = """
[[access]]
instrument_id = "ovdp_lookalike"
bought_at     = "inzhur"
proceeds_to   = "inzhur"
risk_class    = "sovereign_debt"

  [access.price]
  per_unit     = 1000.0
  currency     = "UAH"
  kind         = "venue_terms"
  source       = "TEST FIXTURE -- invented price for an instrument that trips four inferences."
  retrieved_on = "2026-08-31"
  verified_on  = ""
"""


def _root_with_lookalike(tmp_path: Path, *, labelled: bool) -> Path:
    """A whole data root plus one instrument that looks like an OVDP and may or may not say so.

    Built by copying and editing a **declared** instrument rather than by writing a template,
    so the fixture cannot drift into a shape the loader would reject for an unrelated reason.
    """
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    source = (root / "instruments" / "ovdp_synthetic_a.toml").read_text(encoding="utf-8")
    added = source.replace('id           = "ovdp_synthetic_a"', f'id           = "{LOOKALIKE}"', 1)
    added = added.replace(
        'groups       = ["ovdp"]',
        'groups       = ["ovdp"]' if labelled else "groups       = []",
        1,
    )
    (root / "instruments" / f"{LOOKALIKE}.toml").write_text(added, encoding="utf-8")
    access = root / "access" / "instruments.toml"
    access.write_text(access.read_text(encoding="utf-8") + ACCESS_ENTRY, encoding="utf-8")
    return root


def _answered(root: Path) -> Answer:
    declarations = resolver.answer_from_data_root(
        root, base_currency=Currency.UAH, scenario_id=None
    )
    question = loader.question_from_file(root / "questions" / "fifty-thousand.toml")
    result = answer(question, fixtures.inputs(declarations), fixtures.AS_OF)
    assert isinstance(result, Answer), result
    return result


def _members(result: Answer, group: str) -> tuple[str, ...]:
    return next(
        item.ids
        for item in result.subjects
        if isinstance(item, DeclaredSubject) and item.named == group
    )


def test_the_fixture_really_does_trip_all_four_inferences(tmp_path: Path) -> None:
    """The discrimination is worthless if the near-miss is not a near miss.

    Asserted before the claim it supports: an instrument that shared *none* of the four
    attributes would leave every one of them untested while the suite went green.
    """
    root = _root_with_lookalike(tmp_path, labelled=False)
    declarations = resolver.answer_from_data_root(
        root, base_currency=Currency.UAH, scenario_id=None
    )
    added = declarations.tuples.registries.instruments[LOOKALIKE]
    reference = declarations.tuples.registries.instruments["ovdp_synthetic_a"]
    assert added.instrument_class == reference.instrument_class
    assert added.id.startswith("ovdp_")
    assert added.tax_classes == reference.tax_classes
    assert declarations.tuples.access[LOOKALIKE].bought_at == "inzhur"
    assert added.groups == ()


def test_an_instrument_that_declares_no_group_is_in_no_group(tmp_path: Path) -> None:
    """SC-032. Class, id prefix, tax class and venue all say *ovdp*, and the label does not."""
    result = _answered(_root_with_lookalike(tmp_path, labelled=False))
    assert LOOKALIKE not in _members(result, fixtures.OVDP)
    assert LOOKALIKE not in _members(result, fixtures.INZHUR)
    assert LOOKALIKE not in considered_ids(result)


def test_the_same_instrument_with_the_label_joins_the_group(tmp_path: Path) -> None:
    """SC-033's second half -- the one that tells *the label is read* from *nothing is read*."""
    without = _answered(_root_with_lookalike(tmp_path / "a", labelled=False))
    with_label = _answered(_root_with_lookalike(tmp_path / "b", labelled=True))

    assert len(_members(with_label, fixtures.OVDP)) == len(_members(without, fixtures.OVDP)) + 1
    assert LOOKALIKE in _members(with_label, fixtures.OVDP)
    assert set(_members(without, fixtures.OVDP)) < set(_members(with_label, fixtures.OVDP))
    assert _members(without, fixtures.INZHUR) == _members(with_label, fixtures.INZHUR)


def test_the_declared_count_is_unchanged_by_an_unlabelled_addition(tmp_path: Path) -> None:
    """SC-033's first half, stated against the registry it is measured from."""
    before = fixtures.answered()
    without = _answered(_root_with_lookalike(tmp_path, labelled=False))
    assert _members(without, fixtures.OVDP) == _members(before, fixtures.OVDP)


def test_no_group_holds_one_piece_of_paper_twice() -> None:
    """016 FR-027a, SC-020. `enumerated_out_of_order` is modelled on `UA4000235865` and names
    that ISIN in its own header; 016 declares the real issue, so a group carrying both would
    hold one security as two candidates with two sets of cash flows in one comparison,
    differing only in that one is invented.

    015 FR-007b's deduplication cannot catch it -- it deduplicates by **id**, and these are two
    ids for one security -- so the remedy is the label rather than the counter.

    **Asserted against a registry that actually declares the group.** A green result over zero
    declared labels would be evidence of nothing, so the fixture's own membership is read back
    and required to be empty rather than merely absent from a resolution.
    """
    labels = fixtures.declared_labels()
    assert labels[FIXTURE] == (), labels[FIXTURE]
    together = {name for name, groups in labels.items() if groups}
    assert MODELLED_ON in together, "the real issue must be labelled for this check to mean any"
    for group in {group for groups in labels.values() for group in groups}:
        members = {name for name, groups in labels.items() if group in groups}
        assert not ({FIXTURE, MODELLED_ON} <= members), group
