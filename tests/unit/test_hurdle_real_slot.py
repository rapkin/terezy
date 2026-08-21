"""SC-011: the real-terms slot is present, explicitly empty, and carries its reason.

FR-022 leaves a known incompleteness open on purpose. Inflation is not modelled in this
feature, so the hurdle rate is nominal -- and a nominal 15.5% against double-digit
inflation is a materially different proposition from a real one. The requirement is
therefore not "compute a real figure" but "never let a reader mistake the nominal one for
it": the slot must be **present**, **explicitly empty**, and must **say why**.

Three lines of defence, and only two of them are here.

The first is the type system, and it is the real mechanism (research.md D4). ``NominalRate``
and ``RealRate`` are unrelated frozen records, so::

    HurdleRate(..., real=NominalRate(0.16), ...)   # error: incompatible type

is a mypy failure at the assignment. That check cannot be written as a runtime test --
asserting it here would mean asserting that the type checker ran -- so it lives in the
``mypy`` gate, and this module's job is the second line: the runtime shape. The third is
review.
"""

from __future__ import annotations

import pytest

from terezy.core.primitives.rates import NominalRate, RealRate, RealTermsUnavailable
from terezy.core.results import project
from terezy.core.results.hurdle import HurdleRate
from terezy.core.results.project import Projection
from tests import synthetic


def _hurdle() -> HurdleRate:
    outcome = project.project(
        synthetic.declaration(),
        synthetic.holding(),
        synthetic.horizon(),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
    )
    assert isinstance(outcome, Projection)
    return outcome.hurdle


def test_the_real_slot_is_present_and_explicitly_empty() -> None:
    """Never absent. An absent field would read as an oversight; this reads as a decision."""
    assert isinstance(_hurdle().real, RealTermsUnavailable)


def test_the_empty_slot_carries_a_reason_naming_inflation() -> None:
    """FR-017: every degraded outcome carries its reason, and the reason reaches output."""
    real = _hurdle().real
    assert isinstance(real, RealTermsUnavailable)
    assert "inflation" in real.reason
    assert real.reason.strip()


def test_the_slot_never_holds_a_real_rate_this_feature_did_not_compute() -> None:
    """Nothing in feature 001 measures inflation, so nothing may fill this with a number."""
    assert not isinstance(_hurdle().real, RealRate)


def test_the_slot_never_holds_a_nominal_figure_standing_in_for_a_real_one() -> None:
    """The failure SC-011 is actually about: the nominal figure copied into the real slot.

    mypy rejects the assignment outright, which is the guard that matters. This asserts
    the consequence at runtime as well, because the two records are structurally similar
    enough -- both a single ``float`` named ``value`` -- that a dynamic construction could
    still put one where the other belongs.
    """
    assert not isinstance(_hurdle().real, NominalRate)


def test_both_returned_rates_are_labelled_nominal() -> None:
    """SC-011's other half: *every* returned return figure says it is nominal.

    The label is the type, not a string field, so a figure cannot be relabelled by
    mistake -- and the field names say it a second time for a reader.
    """
    hurdle = _hurdle()
    assert isinstance(hurdle.nominal_ytm, NominalRate)
    assert isinstance(hurdle.nominal_cash_flow_return, NominalRate)


@pytest.mark.parametrize(
    ("term", "where"),
    [
        ("tax", "accounts_for"),
        ("route", "excludes"),
        ("inflation", "excludes"),
    ],
)
def test_the_figure_states_its_own_boundaries(term: str, where: str) -> None:
    """The figure says what it is net of and what it is not.

    US1's second acceptance scenario requires the return to **state** that it is after
    tax. A return that does not say whether it is gross or net is the ambiguity
    Principle I exists to prevent -- and between an instrument taxed at 0% and one taxed
    at 23%, that ambiguity is the entire decision.

    Asserted as a pair, because the failure worth catching is not a missing word but a
    term drifting from one set to the other: route costs quietly moving into
    ``accounts_for`` would make an unadjusted figure claim to be comparison-ready.
    """
    stated = " ".join(getattr(_hurdle(), where)).lower()
    other = " ".join(
        getattr(_hurdle(), "excludes" if where == "accounts_for" else "accounts_for")
    ).lower()
    assert term in stated, f"{term!r} is not named in {where}"
    assert term not in other, f"{term!r} appears in both sets, which cannot both be true"
