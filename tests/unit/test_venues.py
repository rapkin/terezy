"""A venue holds the currencies it declares, and no others.

The record exists so that a leg's endpoints are named things with stated capabilities rather
than free strings, and so that "this leg moves dollars into a hryvnia-only card account" is a
question something can answer. That check is what the resolver consults when it validates a
route declaration against the venues it names (FR-024).

**Why the capability is declared and not inferred from the legs that touch a venue.** A route
declaration is written by hand, and the mistake it invites is exactly a leg moving a currency
its endpoint cannot hold. Inferring the venue's capabilities from the legs would make that
mistake self-justifying -- the leg declaring the impossible movement would be the evidence
that it was possible.
"""

from __future__ import annotations

import dataclasses

import pytest

from terezy.core.primitives.currency import Currency
from terezy.core.routes import venues
from terezy.core.routes.venues import Venue

MONOBANK_UAH = Venue(
    id="monobank_uah",
    name="SYNTHETIC FIXTURE -- a hryvnia-only current account",
    currencies=frozenset({Currency.UAH}),
)
BINANCE = Venue(
    id="binance",
    name="SYNTHETIC FIXTURE -- an exchange account holding both",
    currencies=frozenset({Currency.UAH, Currency.USD}),
)


def test_a_venue_holds_what_it_declares() -> None:
    assert venues.can_hold(MONOBANK_UAH, Currency.UAH)
    assert venues.can_hold(BINANCE, Currency.USD)


def test_a_venue_does_not_hold_what_it_does_not_declare() -> None:
    # The answer is ``False`` rather than a raise: the caller that knows which file and
    # which leg index asked the question is the one that must build the error message
    # (FR-024), and it lives in the data layer where this module may not reach.
    assert not venues.can_hold(MONOBANK_UAH, Currency.USD)


def test_the_record_is_frozen_data_with_no_behaviour() -> None:
    assert dataclasses.is_dataclass(Venue)
    assert Venue.__bases__ == (object,)
    with pytest.raises(dataclasses.FrozenInstanceError):
        MONOBANK_UAH.name = "renamed"  # type: ignore[misc]
    assert [
        name for name, value in vars(Venue).items() if callable(value) and not name.startswith("__")
    ] == []
