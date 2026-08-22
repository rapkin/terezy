"""C5 -- values in different currencies can never be combined.

Constitution Principle IV ("Money is float64, carried in a currency-tagged immutable
record so values in different currencies can never be silently combined") and FR-007
("Any attempt to add, subtract or compare monetary amounts of different currencies MUST
fail as an error. Implicit conversion MUST NOT occur anywhere.").

Property-based rather than example-based on purpose: the requirement is about *every*
pair of amounts, and a handful of examples would only prove that the cases someone
thought of are guarded. Tracked as C5 in ``docs/REQUIRED_TESTS.md``.

A currency mismatch is one of the few places the constitution asks for a ``raise``
rather than a typed failure result: mixing UAH with USD is a programmer error, not a
business outcome, so it must stop the run instead of flowing into a result.
"""

from __future__ import annotations

import inspect
from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from terezy.core.errors import CurrencyMismatchError
from terezy.core.primitives import money, provenance
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money

_REF = provenance.of(
    [
        provenance.SourceRef(
            id="test/currency_safety",
            citation="synthetic test input",
            retrieved_on=date(2026, 8, 21),
            verified_on=date(2026, 8, 21),
        )
    ]
)

_AMOUNTS = st.floats(
    min_value=-1e9,
    max_value=1e9,
    allow_nan=False,
    allow_infinity=False,
    allow_subnormal=False,
)


def _money(amount: float, currency: Currency) -> Money:
    return Money(amount, currency, _REF)


@pytest.mark.invariant
@given(left=_AMOUNTS, right=_AMOUNTS)
def test_add_across_currencies_always_raises(left: float, right: float) -> None:
    with pytest.raises(CurrencyMismatchError):
        money.add(_money(left, Currency.UAH), _money(right, Currency.USD))
    with pytest.raises(CurrencyMismatchError):
        money.add(_money(left, Currency.USD), _money(right, Currency.UAH))


@pytest.mark.invariant
@given(left=_AMOUNTS, right=_AMOUNTS)
def test_subtract_across_currencies_always_raises(left: float, right: float) -> None:
    with pytest.raises(CurrencyMismatchError):
        money.sub(_money(left, Currency.UAH), _money(right, Currency.USD))
    with pytest.raises(CurrencyMismatchError):
        money.sub(_money(left, Currency.USD), _money(right, Currency.UAH))


@pytest.mark.invariant
@given(left=_AMOUNTS, right=_AMOUNTS)
def test_compare_across_currencies_always_raises(left: float, right: float) -> None:
    with pytest.raises(CurrencyMismatchError):
        money.compare(_money(left, Currency.UAH), _money(right, Currency.USD))


@pytest.mark.invariant
@given(amounts=st.lists(_AMOUNTS, min_size=1, max_size=6))
def test_total_rejects_a_foreign_amount_anywhere_in_the_sum(amounts: list[float]) -> None:
    """A single foreign amount in a list is enough to stop the sum.

    This is the aggregation case, and it is the one that matters: a mismatch guarded
    only on the binary operation would still let a mixed list through if ``total`` had
    its own accumulation loop.
    """
    items = [_money(amount, Currency.UAH) for amount in amounts]
    items.append(_money(1.0, Currency.USD))
    with pytest.raises(CurrencyMismatchError):
        money.total(items, Currency.UAH)


@pytest.mark.invariant
@given(left=_AMOUNTS, right=_AMOUNTS)
def test_same_currency_combines_and_keeps_the_currency(left: float, right: float) -> None:
    """The mismatch guard must not be so eager that matching currencies fail."""
    result = money.add(_money(left, Currency.UAH), _money(right, Currency.UAH))
    assert result.currency is Currency.UAH


@pytest.mark.invariant
def test_conversion_exists_exactly_once_and_cannot_happen_implicitly() -> None:
    """FX has landed, so this assertion is revisited -- deliberately, as it asked to be.

    **What this test used to assert, and why it changed.** Until feature 002 there was no
    conversion function anywhere, and the strongest available proxy for FR-007's *implicit
    conversion MUST NOT occur anywhere* was that ``money`` exposed no conversion at all.
    That proxy's own docstring anticipated this moment: *"When FX lands it will arrive as an
    explicit, dated, provenance-carrying operation... and this assertion will have to be
    revisited deliberately rather than by accident."* This is that deliberate revisit, and
    it is recorded here rather than in a commit message because the reason is the point.

    **Why the conversion is in ``money`` and not in a module of its own**, which is what
    the old docstring imagined. Two compliance tests meet here and only one arrangement
    satisfies both. ``tests/contract/test_money_construction_guard.py`` permits the money
    record to be constructed in exactly two places -- ``money`` itself, where every
    derivation happens and provenance is unioned, and ``data/declarations``, where declared
    values enter. A conversion necessarily *constructs* an amount in a currency other than
    its input's, so a conversion living anywhere else would either have to construct money
    outside those two places or would need the guard's allow-list widened. Both are worse
    than putting the derivation where every other derivation already lives: the guard's
    rule is "money is built where provenance is established", and a dated, sourced
    conversion is exactly that.

    **What is asserted instead is strictly stronger than what was asserted before.** The
    old check said "no conversion exists". These say: there is exactly *one* conversion,
    nothing else in the module converts, it cannot be reached without an explicit rate and
    that rate's sources, no combining function will accept a rate, and the two degenerate
    calls that would let a currency be lost track of are refused. FR-007 forbids
    *implicit* conversion; every clause below is about making the explicit one impossible
    to perform by accident.
    """
    public_names = {name for name in vars(money) if not name.startswith("_")}

    # Exactly one conversion, under its own name. A second one -- or a differently-named
    # synonym -- would be a second place for a rate's provenance to be dropped, and the
    # convenient one would be the one that dropped it.
    conversion_shaped = {"convert", "in_currency", "exchange", "fx", "restate", "as_currency"}
    assert public_names & conversion_shaped == {"convert"}

    # It cannot be called implicitly. The target currency, the rate and the rate's sources
    # are all keyword-only and none has a default, so there is no call to ``convert`` that
    # does not name the rate it used and where that rate came from.
    parameters = inspect.signature(money.convert).parameters
    for required in ("to_currency", "rate", "sources"):
        assert parameters[required].kind is inspect.Parameter.KEYWORD_ONLY
        assert parameters[required].default is inspect.Parameter.empty

    # Nothing that *combines* money will take a rate, so no addition, subtraction,
    # comparison or scaling can quietly become a conversion.
    for name in ("add", "sub", "total", "compare", "scale", "scale_sourced", "zero"):
        assert "rate" not in inspect.signature(getattr(money, name)).parameters

    combining = {name for name in public_names if name in {"add", "sub", "total", "compare"}}
    assert combining == {"add", "sub", "total", "compare"}


@pytest.mark.invariant
@given(amount=_AMOUNTS)
def test_a_conversion_to_the_same_currency_is_refused(amount: float) -> None:
    """The call that would let a lost currency pass through unnoticed.

    Returning the amount unchanged would be the friendly thing to do and would make a bug
    that lost track of a currency invisible -- while collecting the provenance of a rate it
    never applied, which is the worst of both.
    """
    with pytest.raises(ValueError, match="not a conversion"):
        money.convert(
            _money(amount, Currency.UAH), to_currency=Currency.UAH, rate=1.0, sources=_REF
        )


@pytest.mark.invariant
@given(amount=_AMOUNTS, rate=st.floats(min_value=-1e6, max_value=0.0, allow_nan=False))
def test_a_rate_of_zero_or_less_is_refused(amount: float, rate: float) -> None:
    """Zero is not a rate and neither is a negative number.

    A declined question rather than a clamp: nothing is quietly adjusted to make the
    arithmetic work, because the result would look like money.
    """
    with pytest.raises(ValueError, match="not a rate"):
        money.convert(
            _money(amount, Currency.UAH), to_currency=Currency.USD, rate=rate, sources=_REF
        )


@pytest.mark.invariant
@given(amount=_AMOUNTS, rate=st.floats(min_value=1e-6, max_value=1e6, allow_nan=False))
def test_a_conversion_carries_the_rates_sources_into_the_result(amount: float, rate: float) -> None:
    """E5 / FR-015 across a currency boundary, which is where a mark is easiest to drop.

    A converted amount rests on the rate as much as on the amount, so it names both. This
    is the same union every combining function performs, asserted separately because a
    conversion is the one derivation whose second operand is not money.
    """
    rate_source = provenance.of(
        [
            provenance.SourceRef(
                id="test/currency_safety#rate",
                citation="synthetic test rate",
                retrieved_on=date(2026, 8, 21),
                verified_on=None,
            )
        ]
    )
    converted = money.convert(
        _money(amount, Currency.UAH), to_currency=Currency.USD, rate=rate, sources=rate_source
    )
    assert converted.currency is Currency.USD
    assert converted.provenance.sources >= rate_source.sources | _REF.sources
    assert provenance.is_unverified(converted.provenance)
