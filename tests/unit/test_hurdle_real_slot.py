"""SC-011: the real-terms slot is present, says what is in it, and never holds a nominal figure.

FR-022 reserved this slot and required that a reader never mistake the nominal figure for a
real one -- a nominal 15.5% against double-digit inflation being a materially different
proposition. Feature 001 satisfied that by keeping the slot **present**, **explicitly empty**
and **saying why**.

⚙ **Feature 007 filled it, and this module is the record that the promise held.** The slot is
still exactly one field named ``real``; what it holds is now a ``RealTerms`` carrying two
independently typed figures. A projection given no CPI series -- which is what the fixture
below does, calling ``project`` exactly as feature 001 called it -- still produces a
shape-identical result, with both figures unavailable and each naming its own absence
(FR-006, US1 scenario 5). That call being unchanged is the assertion, not an accident of the
fixture.

Three lines of defence, and only two of them are here.

The first is the type system, and it is the real mechanism (research.md D4). ``NominalRate``
and ``RealRate`` are unrelated frozen records, so::

    HurdleRate(..., real=NominalRate(0.16), ...)   # error: incompatible type

is a mypy failure at the assignment, and it survived the slot changing occupant: a
``NominalRate`` is not a ``RealTerms`` either. That check cannot be written as a runtime test
-- asserting it here would mean asserting that the type checker ran -- so it lives in the
``mypy`` gate, and this module's job is the second line: the runtime shape. The third is
review.
"""

from __future__ import annotations

import pytest

from terezy.core.primitives.rates import NominalRate, RealRate, RealTermsUnavailable
from terezy.core.results import project
from terezy.core.results.hurdle import HurdleRate, RealTerms
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


def test_the_real_slot_is_present_and_is_still_exactly_one_field() -> None:
    """Never absent, and never split in two. FR-006's invariance, asserted on the record itself.

    Two figures arrived without the result growing a field, which is the whole content of
    001's reservation: a second field beside ``real`` would have broken every consumer the
    reservation existed to protect.
    """
    hurdle = _hurdle()
    assert isinstance(hurdle.real, RealTerms)
    assert [field for field in HurdleRate.__dataclass_fields__ if "real" in field] == ["real"]


def test_a_projection_given_no_cpi_reports_both_absences_and_neither_as_a_number() -> None:
    """FR-017 and FR-012: every degraded outcome carries a reason, and the reason is specific."""
    real = _hurdle().real
    assert isinstance(real.realized, RealTermsUnavailable)
    assert isinstance(real.assumed, RealTermsUnavailable)
    assert "no CPI series" in real.realized.reason
    assert "assumption" in real.assumed.reason


def test_the_slot_never_holds_a_real_rate_that_was_not_computed_from_declared_data() -> None:
    """No CPI was given, so no number may appear in either half."""
    real = _hurdle().real
    assert not isinstance(real.realized, RealRate)
    assert not isinstance(real.assumed, RealRate)


def test_the_slot_never_holds_a_nominal_figure_standing_in_for_a_real_one() -> None:
    """The failure SC-011 is actually about: the nominal figure copied into the real slot.

    mypy rejects the assignment outright, which is the guard that matters. This asserts
    the consequence at runtime as well, because the rate records are structurally similar
    enough -- each a ``float`` named ``value`` -- that a dynamic construction could still put
    one where the other belongs.

    Written over a widened tuple rather than as three ``isinstance`` calls: mypy proves each
    of those unreachable and, under ``warn_unreachable``, refuses them. That refusal *is* the
    guarantee -- the type checker saying the substitution cannot happen -- and the runtime
    check is kept beside it for the dynamic case the type checker never sees.
    """
    real = _hurdle().real
    occupants: tuple[object, ...] = (real, real.realized, real.assumed)

    assert not any(isinstance(occupant, NominalRate) for occupant in occupants)


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
