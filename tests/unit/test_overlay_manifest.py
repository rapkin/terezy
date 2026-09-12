"""What the manifest records about a private declaration: that it was read, never what it said.

025 FR-008. `manifest.file_name` renders both roots' seeds file as `seeds/owner-001.toml`, so an
id without a prefix would collide and a reader of a result could not see that a private
declaration was involved. The prefix is on the **id**; the digest is of the file's bytes, and no
declared value crosses into the record.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from terezy.core.primitives.currency import Currency
from terezy.data import manifest as run_manifest
from terezy.data.declarations import resolver
from tests import answer_registries as fixtures

SECRET_QUANTITY = 7.25
"""A quantity chosen to be findable: no other figure in the fixture tree carries it."""

SECRET_COST = 6543.21
SECRET_REASON = "a sentence that appears nowhere else in this repository"
FIXTURE_INSTRUMENT = "ovdp_enumerated_a"
"""Which instrument the lot is of is a *curated* id and appears in the manifest legitimately,
through the access and instrument declarations. What may not appear is the lot's own figures."""


@pytest.fixture(scope="module")
def recorded(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, tuple[run_manifest.InputRef, ...]]:
    """A root whose overlay declares one lot with figures nothing else in the tree carries."""
    root = tmp_path_factory.mktemp("overlay-manifest") / "data"
    shutil.copytree(fixtures.DATA_ROOT, root)
    overlay = root / resolver.USER_DIR / resolver.SEEDS_DIR / "owner-001.toml"
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.write_text(
        '[owner]\nid = "owner-001"\n\n'
        "[[seed]]\n"
        "is_synthetic  = false\n"
        f'instrument_id = "{FIXTURE_INSTRUMENT}"\n'
        f"quantity      = {SECRET_QUANTITY}\n"
        'acquired_on   = "2026-03-14"\n'
        f"cost          = {SECRET_COST}\n"
        'basis         = "estimated"\n'
        f'reason        = "{SECRET_REASON}"\n',
        encoding="utf-8",
    )
    declared = resolver.answer_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)
    return overlay, run_manifest.answer_input_refs(
        declared,
        answered=fixtures.owners_question(),
        declared_in=fixtures.QUESTION_FILE,
        question_version=None,
    )


def test_the_overlay_is_recorded_under_a_prefixed_id(
    recorded: tuple[Path, tuple[run_manifest.InputRef, ...]],
) -> None:
    overlay, refs = recorded
    seeds = {ref.id: ref for ref in refs if ref.kind == "seed"}
    private = f"{run_manifest.OVERLAY_ID_PREFIX}{overlay.stem}"
    assert private in seeds
    assert seeds[private].file == run_manifest.file_name(overlay)
    assert seeds[private].version == run_manifest.file_version(overlay)


def test_both_roots_are_recorded_and_are_told_apart(
    recorded: tuple[Path, tuple[run_manifest.InputRef, ...]],
) -> None:
    """The collision the prefix prevents: two files rendering to one name."""
    _, refs = recorded
    seeds = [ref for ref in refs if ref.kind == "seed"]
    assert len(seeds) == 2, "one input per root"
    assert len({ref.id for ref in seeds}) == 2
    assert len({ref.file for ref in seeds}) == 1, (
        "the two files render to one name, which is why the id carries the prefix"
    )


def test_no_declared_value_reaches_the_manifest(
    recorded: tuple[Path, tuple[run_manifest.InputRef, ...]],
) -> None:
    """FR-008: the record says a private declaration was read, and nothing about its content."""
    _, refs = recorded
    rendered = repr(refs)
    for secret in (str(SECRET_QUANTITY), str(SECRET_COST), SECRET_REASON):
        assert secret not in rendered, f"{secret!r} crossed from the overlay into the manifest"
