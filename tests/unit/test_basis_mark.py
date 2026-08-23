"""FR-008: the estimated-basis mark states its reason and tells itself apart.

Two claims that pull in opposite directions and are both required.

**It must propagate by the same rule as an unverified observation** (FR-007), which is why
it is a ``SourceRef`` and not a second kind of thing: ``provenance.merge`` cannot tell the
two apart, so no transform can carry one and drop the other. That half is asserted where it
matters, in ``tests/contract/test_estimated_basis_propagates.py``.

**It must be distinguishable on inspection**, because a reader should do different things
about the two. An unverified market value is checked against its source; an estimated
acquisition cost cannot be, and the only cure is the owner finding the receipt. That half is
here.
"""

from __future__ import annotations

from datetime import date

from terezy.core.ledger import seeds
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.provenance import SourceRef

REASON = "bought in three tranches in 2024 and the broker statement is gone"

ESTIMATED = seeds.basis_estimated(
    declared_at="seeds/owner-001.toml#seed[1]",
    reason=REASON,
    estimated_for=date(2024, 11, 2),
)

UNVERIFIED_OBSERVATION = SourceRef(
    id="channels/uah_usd.toml#channel[0]",
    citation="SYNTHETIC FIXTURE -- a quoted rate nobody has checked.",
    retrieved_on=date(2026, 8, 1),
    verified_on=None,
)

VERIFIED_OBSERVATION = SourceRef(
    id="tax/ua.toml#jurisdiction.tax_class[0]",
    citation="SYNTHETIC FIXTURE -- a rate somebody checked.",
    retrieved_on=date(2026, 8, 1),
    verified_on=date(2026, 8, 21),
)


def test_the_mark_carries_the_owners_reason() -> None:
    """The reason the owner gives is what the citation says, so the output can show it."""
    assert ESTIMATED.reason == REASON
    assert REASON in ESTIMATED.mark.citation


def test_the_mark_is_unverified_because_nobody_can_verify_a_recollection() -> None:
    """It rides the existing machinery, which means it uses the existing word for it."""
    assert ESTIMATED.mark.verified_on is None
    assert prov.is_unverified(prov.of([ESTIMATED.mark]))


def test_the_mark_points_at_the_declaration_it_came_from() -> None:
    """A mark that cannot name its input is a run-scoped taint flag: unfalsifiable, useless."""
    assert ESTIMATED.mark.id.endswith("seeds/owner-001.toml#seed[1]")


def test_an_estimated_basis_is_distinguishable_from_an_unverified_observation() -> None:
    """FR-008. Both make a figure unverified; only one of them is about the owner's memory."""
    assert seeds.is_basis_estimated(ESTIMATED.mark)
    assert not seeds.is_basis_estimated(UNVERIFIED_OBSERVATION)
    assert not seeds.is_basis_estimated(VERIFIED_OBSERVATION)


def test_the_estimated_sources_of_a_mixed_provenance_are_the_estimated_ones() -> None:
    """The companion of ``provenance.unverified_sources``: *which* input, not merely whether."""
    mixed = prov.of([ESTIMATED.mark, UNVERIFIED_OBSERVATION, VERIFIED_OBSERVATION])
    assert seeds.basis_estimated_sources(mixed) == frozenset({ESTIMATED.mark})
    assert prov.unverified_sources(mixed) == frozenset({ESTIMATED.mark, UNVERIFIED_OBSERVATION})


def test_one_estimated_input_taints_the_figure_and_none_leaves_it_clean() -> None:
    """The same asymmetry ``is_unverified`` has: a figure is as good as its worst input."""
    assert seeds.rests_on_estimated_basis(prov.of([ESTIMATED.mark, VERIFIED_OBSERVATION]))
    assert not seeds.rests_on_estimated_basis(
        prov.of([UNVERIFIED_OBSERVATION, VERIFIED_OBSERVATION])
    )
    assert not seeds.rests_on_estimated_basis(prov.EMPTY)


def test_two_estimates_of_one_lot_are_one_mark_and_two_lots_are_two() -> None:
    """``SourceRef`` equality is by value, so the id is what keeps the set honest.

    Merging a figure with itself must not accumulate duplicates -- provenance is a set of
    facts -- while two different lots the owner guessed at must both be nameable, because
    "which acquisition am I unsure about" is the question the mark exists to answer.
    """
    same = seeds.basis_estimated(
        declared_at="seeds/owner-001.toml#seed[1]",
        reason=REASON,
        estimated_for=date(2024, 11, 2),
    )
    other = seeds.basis_estimated(
        declared_at="seeds/owner-001.toml#seed[2]",
        reason="a different lot, equally forgotten",
        estimated_for=date(2025, 1, 9),
    )
    assert same.mark == ESTIMATED.mark
    merged = prov.merge(prov.of([ESTIMATED.mark, same.mark]), prov.of([other.mark]))
    assert seeds.basis_estimated_sources(merged) == frozenset({ESTIMATED.mark, other.mark})
