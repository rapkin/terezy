"""An unrecognised convention name fails loudly. There is no fallback convention.

Part of **FR-021**: *an unrecognised convention name MUST fail at load time naming the
file and the value -- never fall back to a default convention.*

The split of responsibility, since this test only owns half of it. Naming the **file**
is the data layer's job: the loader validates a declared name against the registries
here and reports file and field as a ``DeclarationError`` (FR-016, tested by
``test_declaration_loading.py``). Naming the **value**, and refusing to invent a
convention, is the core's job and is what this test asserts.

Why a fallback would be the worst available outcome: an issue declaring ``"act/360"``
against an engine that quietly applied ``act/365`` would produce a schedule that is
wrong by a fraction of a percent -- large enough to change a decision, small enough to
look entirely plausible, and invisible in every output. The constitution puts a silent
default in the same severity class as a wrong number, and this is why.

Tracked alongside **H2** in ``docs/REQUIRED_TESTS.md``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from typing import Any

import pytest

from terezy.core.primitives import conventions

pytestmark = pytest.mark.contract

RESOLVERS: Mapping[str, tuple[Callable[[str], Any], Mapping[str, Any]]] = {
    "day-count": (conventions.day_count, conventions.DAY_COUNT_FNS),
    "periodicity": (conventions.periodicity, conventions.PERIODICITY_FNS),
    "business-day": (conventions.business_day_rule, conventions.BUSINESS_DAY_FNS),
}

# Names that are plausible, close to a real one, or a different real convention this
# engine has not implemented. Every one of them is the kind of thing that actually
# appears in a declaration file, which is why a fallback would be so damaging.
UNKNOWN_NAMES = ("act/360", "ACT/365", "act365", "thirty/360", "monthly", "preceding", "")


@pytest.mark.parametrize("kind", list(RESOLVERS))
@pytest.mark.parametrize("name", UNKNOWN_NAMES)
def test_an_unknown_name_raises_and_names_the_value(kind: str, name: str) -> None:
    resolve, registry = RESOLVERS[kind]
    if name in registry:
        pytest.fail(f"{name!r} is a known {kind} convention; the test data is stale")

    with pytest.raises(KeyError) as raised:
        resolve(name)

    message = str(raised.value)
    assert repr(name) in message, "the failure must name the offending value"
    assert kind in message, "the failure must say which kind of convention was meant"
    for known in registry:
        assert known in message, "the failure must list the names that would have worked"


@pytest.mark.parametrize("kind", list(RESOLVERS))
def test_every_declared_name_resolves_to_something_callable(kind: str) -> None:
    """The other half: a name in the registry must actually work.

    A registry key pointing at nothing would turn a valid declaration into a crash, and
    is the failure mode a lookup test alone would not catch.
    """
    resolve, registry = RESOLVERS[kind]
    for name in registry:
        assert callable(resolve(name))


@pytest.mark.parametrize("kind", list(RESOLVERS))
def test_there_is_no_default_key_hiding_in_the_registry(kind: str) -> None:
    """No entry named to be selected by omission.

    A key called ``default``, ``""`` or ``None`` would reintroduce the fallback through
    the data rather than the code -- a declaration omitting the field, loaded as an
    empty string, would find a convention waiting for it.
    """
    _, registry = RESOLVERS[kind]
    assert not ({"default", "", "none_specified", "unspecified"} & set(registry) - {"none"})
    assert None not in registry


def test_the_registries_contain_exactly_the_documented_conventions() -> None:
    """The key sets are the engine's published contract, so pin them.

    Data files and the loader's validation both depend on these names. A silent rename
    would break every declaration that used the old one, and a silent addition would let
    a convention into production without a worked example. Changing this assertion
    should be a deliberate act with a hand-computed example arriving alongside it.
    """
    assert set(conventions.DAY_COUNT_FNS) == {"act/365", "act/act", "30/360"}
    assert set(conventions.PERIODICITY_FNS) == {"annual", "semiannual", "quarterly"}
    assert set(conventions.BUSINESS_DAY_FNS) == {"none", "following", "modified_following"}


def test_none_is_a_declared_rule_not_an_absence() -> None:
    """``"none"`` in the business-day registry is a choice, not a missing value.

    Worth stating because it reads like the opposite. An issue whose coupon dates are
    unadjusted must be able to say so, and it says so by naming a rule that does
    nothing. What FR-021 forbids is the engine *selecting* a rule when the declaration
    is silent -- and a silent declaration produces a missing field at the data boundary,
    not this rule.
    """
    unadjusted = conventions.business_day_rule("none")
    saturday = date(2025, 5, 31)
    assert unadjusted(saturday) == saturday
